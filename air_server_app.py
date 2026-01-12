# product_lines/Air/air_server_app.py
import sys
import os
import aiohttp.web
import asyncio
import time
import json
import mss
import psutil
import websockets
from pathlib import Path

# Local core/utils are now available in sys.path via main.py or current dir
from core.server_app import VeloxFlowServerApp
from core.engine import StreamEngine
from core.adaptive_governor import AdaptiveGovernor

class VeloxAirServerApp(VeloxFlowServerApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Runtime Native Core Detection
        try:
            import velox_core
        except ImportError:
            if self.config['server'].get('optimize_capture_pipeline'):
                self.debug.info("VeloxAir", "Native core not found. Disabling capture optimization (Pure Python Mode).")
                self.config['server']['optimize_capture_pipeline'] = False

        self._start_time = time.time()
        self._dashboards = set()
        self._engine_lock = asyncio.Lock() # Prevent concurrent engine creation
        self._backend_blacklist = {} # monitor_id -> timestamp
        psutil.cpu_percent(interval=None)
        
        # Persistence Setup
        # Use executable directory for persistent data, not _MEIPASS
        base_storage_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        
        self._state_path = os.path.join(base_storage_dir, "metadata", "runtime_state.json")
        os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
        self._load_runtime_state()

        # Setup File Logging for Long-Run Stability
        log_dir = os.path.join(base_storage_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.debug.add_file_handler(os.path.join(log_dir, "VeloxAir_Server.log"))
        self.debug.info("VeloxAir", "File logging initialized with state persistence.")

    def _load_runtime_state(self):
        """Loads persisted user selections."""
        try:
            if os.path.exists(self._state_path):
                with open(self._state_path, 'r') as f:
                    state = json.load(f)
                    last_mon = state.get("last_monitor_id")
                    if last_mon is not None:
                        self.config['server']['monitor_id'] = int(last_mon)
                        self.debug.info("VeloxAir", f"Restored last monitor selection: {last_mon}")
        except Exception as e:
            self.debug.warning("VeloxAir", f"Failed to load runtime state: {e}")

    def _save_runtime_state(self):
        """Persists current user selections."""
        try:
            state = {"last_monitor_id": self.config['server'].get('monitor_id', 0)}
            with open(self._state_path, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.debug.error("VeloxAir", f"Failed to save runtime state: {e}")

    async def _broadcast_event(self, message, level="info"):
        payload = json.dumps({"type": "SYS_EVENT", "message": message, "level": level})
        for ws in list(self._dashboards):
            asyncio.create_task(self._safe_send(ws, payload))

    async def get_or_create_engine(self, monitor_id: int, force_compat=False):
        async with self._engine_lock:
            # Check Blacklist (Cool-down period for failed native backends)
            # Increased to 60s for better driver stability
            if not force_compat and monitor_id in self._backend_blacklist:
                if time.time() - self._backend_blacklist[monitor_id] < 60:
                    self.debug.warning("VeloxAir", f"Monitor {monitor_id} is in cool-down. Forcing compat mode.")
                    force_compat = True

            if monitor_id in self.engines and not force_compat:
                return self.engines[monitor_id]
            
            import copy
            self.debug.info("VeloxAir", f"Creating Engine for Monitor {monitor_id} (force_compat={force_compat})")
            cfg = copy.deepcopy(self.config)
            
            # STABILITY POLICY: Never use DXCAM in Air tier
            cfg['server']['enable_dxcam_fallback'] = False
            
            if force_compat:
                cfg['server']['optimize_capture_pipeline'] = False
            
            cfg['server']['monitor_id'] = monitor_id

            if monitor_id in self.engines:
                old = self.engines.pop(monitor_id)
                old["video_task"].cancel(); old["audio_task"].cancel()
                await old["engine"].stop()
                await asyncio.sleep(0.5) # Driver settling time

            try:
                engine = StreamEngine(cfg, self.debug)
                
                # BLACKLIST TRIGGER: 
                # If we requested optimized capture but got MSS fallback, trigger blacklist
                if not force_compat and cfg['server'].get('optimize_capture_pipeline'):
                    if getattr(engine.capture, 'name', '').startswith("MSS"):
                        self.debug.warning("VeloxAir", f"Native capture requested but MSS returned. Blacklisting Monitor {monitor_id} for 60s.")
                        self._backend_blacklist[monitor_id] = time.time()

                gov = AdaptiveGovernor(self.debug, mode=self.config['server'].get('mode', 'BALANCED').upper(), tier='AIR')
                
                engine_data = {
                    "engine": engine, "clients": set(), "governor": gov,
                    "force_enhancement": True,
                    "video_task": asyncio.create_task(self._engine_broadcast_loop(monitor_id)),
                    "audio_task": asyncio.create_task(self._audio_broadcast_loop(monitor_id))
                }
                self.engines[monitor_id] = engine_data
                return engine_data
            except Exception as e:
                self.debug.error("VeloxAir", f"Engine Init Error for Monitor {monitor_id}: {e}")
                self._backend_blacklist[monitor_id] = time.time()
                if not force_compat:
                    await asyncio.sleep(0.5)
                    return await self.get_or_create_engine(monitor_id, force_compat=True)
                raise

    async def _handle_snapshot_api(self, request):
        """Highly resilient snapshot API that returns a placeholder on failure."""
        try:
            mon_id = int(request.query.get('monitor_id', 0))
            from io import BytesIO
            from PIL import Image, ImageDraw
            
            img = None
            # 1. Try to get from active engine first
            data = self.engines.get(mon_id)
            if data and getattr(data["engine"], 'last_frame', None):
                try:
                    img = data["engine"].last_frame.get_pil_image()
                except: pass
            
            if not img:
                # 2. Isolated Fallback (Direct MSS)
                try:
                    import mss
                    with mss.mss() as sct:
                        idx = mon_id + 1 if (mon_id + 1) < len(sct.monitors) else 1
                        sct_img = sct.grab(sct.monitors[idx])
                        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                except: pass

            # 3. Final Fallback: Generate "No Signal" Placeholder
            if not img:
                img = Image.new('RGB', (480, 270), color='#0f172a')
                d = ImageDraw.Draw(img)
                d.text((180, 130), "WAITING FOR SIGNAL...", fill='#334155')

            img.thumbnail((480, 270))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=40)
            return aiohttp.web.Response(body=buf.getvalue(), content_type="image/jpeg", headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*"
            })
        except:
            # Absolute last resort: empty transparent pixel
            return aiohttp.web.Response(body=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82', content_type="image/png")

    async def _ws_handler(self, websocket):
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        curr_mon = self.config['server'].get('monitor_id', 0)
        lang = self.config['server'].get('language', 'zh_TW')
        try:
            from core.constants import PROTOCOL_VERSION
            # 1. Complete handshake and send version/config immediately
            await websocket.send(json.dumps({
                "type": "VERSION", 
                "version": PROTOCOL_VERSION, 
                "monitor_id": curr_mon, 
                "tier": "AIR",
                "language": lang
            }))
            
            # 2. Register first, then get engine (which might block on lock)
            ed = await self.get_or_create_engine(curr_mon)
            ed["clients"].add(websocket)

            # 3. CRITICAL: Send Initial Keyframe immediately
            # Without this, new clients drop Delta frames until the next full refresh (black screen)
            try:
                init_frame = await asyncio.wait_for(ed["engine"].get_initial_payload(), timeout=2.0)
                await websocket.send(init_frame)
            except Exception as e:
                self.debug.warning("VeloxAir", f"Failed to send initial keyframe: {e}")

            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        if message[0] == 0x03 or message[0] == 0x04:
                            try:
                                self.native_input.inject_binary(message)
                            except Exception as e:
                                self.debug.debug("VeloxAir", f"Input injection failed: {e}")
                    elif isinstance(message, str):
                        data = json.loads(message)
                        if data.get('type') == 'DASHBOARD_IDENT':
                            ed["clients"].discard(websocket); self._dashboards.add(websocket)
                        elif data.get('type') == 'CLIENT_STATS':
                            g = ed["governor"]
                            g.update(data)
                            
                            # Store client info for Dashboard
                            websocket.device_name = data.get('device_name', 'Unknown')
                            
                            # Apply to Engine
                            engine = ed["engine"]
                            engine.encoder._quality = g.get_quality()
                            engine.tile_size = g.get_tile_size()
                            engine.frame_rate = g.get_target_fps()
                            
                        elif data.get('type') == 'DASHBOARD_CMD':
                            cmd = data.get('command')
                            if cmd == 'SOFTWARE_RESET':
                                await self._perform_software_reset()
                            elif cmd == 'FORCE_REFRESH':
                                for e in self.engines.values(): e['force_enhancement'] = True
                                await self._broadcast_event("HD Refresh Triggered", "warning")
                            elif cmd == 'SWITCH_MONITOR': 
                                await self._perform_switch(int(data.get('monitor_id', 0)))
            except (websockets.exceptions.ConnectionClosed, ConnectionResetError, OSError, KeyboardInterrupt):
                # Silently handle abrupt disconnections and manual interrupts
                pass
            except asyncio.CancelledError:
                # Essential for clean shutdown in asyncio
                raise
            except Exception as e:
                self.debug.debug("VeloxAir", f"WS Loop Error: {e}")
        finally:
            for e in self.engines.values(): e["clients"].discard(websocket)
            self._dashboards.discard(websocket)

    async def _perform_software_reset(self):
        """Deep cleaning of the server state to recover from any resource locks or hangs."""
        self.debug.warning("VeloxAir", "🚀 INITIATING SOFTWARE RESET (Buffer Purge Mode)...")
        await self._broadcast_event("SOFTWARE RESET INITIATED", "error")
        
        # 0. Remember current monitor before clearing
        current_mon = self.config['server'].get('monitor_id', 0)
        
        # 1. HARD DISCONNECT all clients to purge OS-level TCP buffers
        # This is the only way to stop 'zombie data' from clogging the pipe
        for mid in list(self.engines.keys()):
            clients = list(self.engines[mid]["clients"])
            for ws in clients:
                try:
                    await ws.close(code=1001, reason="SOFTWARE_RESET")
                except: pass
            self.engines[mid]["clients"].clear()
        
        # 2. Force clear all engines and tasks
        stop_tasks = []
        for mid in list(self.engines.keys()):
            try:
                ed = self.engines.pop(mid)
                ed["video_task"].cancel()
                ed["audio_task"].cancel()
                stop_tasks.append(ed["video_task"])
                stop_tasks.append(ed["audio_task"])
                await ed["engine"].stop()
            except: pass
        
        # 3. Clear the sending task tracking
        self._clients_sending.clear()
        
        # 4. Clear backend blacklist and force GC
        self._backend_blacklist.clear()
        import gc
        gc.collect()
        
        # Wait for tasks to acknowledge cancellation
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        self.debug.info("VeloxAir", "System memory, network queues, and blacklists purged.")
        
        # 5. Settling delay
        await asyncio.sleep(2.0)
        
        # 6. Re-initialize primary engine
        await self.get_or_create_engine(current_mon)
        
        await self._broadcast_event("SYSTEM RECOVERED", "info")
        self.debug.info("VeloxAir", "Software Reset Complete. Clients should auto-reconnect now.")

    async def _perform_switch(self, new_mon):
        # 1. Collect all clients from all active engines
        all_clients = []
        for mid, ed in self.engines.items():
            all_clients.extend(list(ed["clients"]))
            ed["clients"].clear()
        
        # 2. Stop only engines that are NOT the new target monitor
        # This prevents the "stop-then-immediate-restart" race condition for DXGI
        for mid in list(self.engines.keys()):
            if mid != new_mon:
                ed = self.engines.pop(mid)
                ed["video_task"].cancel()
                ed["audio_task"].cancel()
                await ed["engine"].stop()

        # 3. Ensure the target monitor engine exists
        self.config['server']['monitor_id'] = new_mon
        self._save_runtime_state() # PERSISTENCE
        new_data = await self.get_or_create_engine(new_mon)
        
        # 4. Reassign all clients to the target monitor
        for c_ws in all_clients:
            new_data["clients"].add(c_ws)
            try:
                await c_ws.send(json.dumps({"type": "VERSION", "monitor_id": new_mon, "tier": "AIR"}))
            except: pass

    async def _engine_broadcast_loop(self, monitor_id: int):
        last_change, enh_sent = time.time(), False
        try:
            while monitor_id in self.engines:
                data = self.engines[monitor_id]
                engine, clients = data["engine"], data["clients"]
                
                # 1 FPS capture for Dashboard when no clients are connected
                if not clients:
                    try: await engine.get_next_payload(); await asyncio.sleep(1.0)
                    except: await asyncio.sleep(1.0)
                    continue

                # CONGESTION CONTROL: 
                # If ANY client is lagging behind significantly, skip this frame to allow catching up
                if any(ws in self._clients_sending for ws in clients):
                    await asyncio.sleep(0.01)
                    continue

                try:
                    if data.get('force_enhancement'):
                        lossless = await engine.get_initial_payload()
                        if lossless:
                            pkt = bytearray(lossless); pkt[0] = 0x02
                            for ws in list(clients): await self._safe_send(ws, bytes(pkt))
                            enh_sent, data['force_enhancement'] = True, False
                            await asyncio.sleep(0.1); continue

                    payload = await engine.get_next_payload()
                    if payload:
                        last_change, enh_sent = time.time(), False
                        for ws in list(clients):
                            if ws not in self._clients_sending:
                                self._clients_sending[ws] = asyncio.create_task(self._safe_send(ws, payload))
                    else:
                        if not enh_sent and (time.time() - last_change > 2.0):
                            lossless = await engine.get_initial_payload()
                            if lossless:
                                pkt = bytearray(lossless); pkt[0] = 0x02
                                for ws in list(clients): await self._safe_send(ws, bytes(pkt))
                                enh_sent = True
                    await asyncio.sleep(1.0 / getattr(engine, 'frame_rate', 20))
                except Exception as e:
                    if any(x in str(e) for x in ["Access is denied", "0x80070005", "The parameter is incorrect"]):
                        self.debug.warning("VeloxAir", f"Capture error on Monitor {monitor_id}. Fallback to compat.")
                        asyncio.create_task(self.get_or_create_engine(monitor_id, force_compat=True))
                        return
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Silently exit when loop is closing
            pass

    async def _handle_stats_api(self, request):
        details = []
        for mid, data in self.engines.items():
            for ws in data["clients"]:
                g = data["governor"]
                details.append({
                    "id": f"{ws.remote_address[0]}:{ws.remote_address[1]}", 
                    "name": getattr(ws, 'device_name', 'Web Companion'),
                    "fps": getattr(g, 'last_fps', 0), 
                    "battery": getattr(g, 'last_battery', 100), 
                    "is_charging": getattr(g, 'last_is_charging', True), 
                    "mode": getattr(g, 'last_mode', 'UNKNOWN')
                })
        host = {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent, "uptime": int(time.time() - self._start_time)}
        mons = []
        with mss.mss() as sct:
            # monitors[0] is ALL screens. physical screens start from index 1.
            for i, m in enumerate(sct.monitors[1:]):
                mons.append({"id": i, "width": m['width'], "height": m['height']})
        return aiohttp.web.json_response({"clients": len(details), "client_details": details, "monitors": mons, "host": host})

    async def start(self):
        # Suppress noisy handshake errors in logs
        import logging
        logging.getLogger('websockets.server').setLevel(logging.CRITICAL)
        
        app = aiohttp.web.Application()
        app.router.add_get('/api/stats', self._handle_stats_api)
        app.router.add_get('/api/snapshot', self._handle_snapshot_api)
        app.router.add_get('/dashboard', lambda r: aiohttp.web.HTTPFound('/client/dashboard.html'))
        app.router.add_get('/', lambda r: aiohttp.web.HTTPFound('/client/index.html'))
        
        # Calculate static files directory
        if getattr(sys, 'frozen', False):
            # Bundled: web is at the root of sys._MEIPASS
            static_dir = os.path.join(sys._MEIPASS, "web")
        else:
            # Development: web is next to air_server_app.py
            static_dir = os.path.join(os.path.dirname(__file__), "web")
        
        if not os.path.exists(static_dir):
            self.debug.error("VeloxAir", f"CRITICAL: Static directory missing: {static_dir}")
            
        app.router.add_static('/client', static_dir, show_index=True)
        runner = aiohttp.web.AppRunner(app, access_log=None)
        await runner.setup()
        
        # Primary Web Site (HTTPS if certs exist, else HTTP)
        main_web_port = self.config['server']['web_port']
        await aiohttp.web.TCPSite(runner, '0.0.0.0', main_web_port, ssl_context=self.ssl_context).start()
        
        # Secondary Web Site (Always HTTP for legacy support)
        if self.ssl_context:
            http_web_port = main_web_port + 1
            await aiohttp.web.TCPSite(runner, '0.0.0.0', http_web_port).start()
            self.debug.info("VeloxAir", f"Legacy HTTP Web accessible on port {http_web_port}")

        # Primary WebSocket (Secure if possible)
        ws_port = self.config['server']['port']
        ws_server_secure = None
        
        # Port Seeker Loop
        for offset in range(3):
            try:
                target_port = ws_port + offset
                ws_server_secure = await websockets.serve(self._ws_handler, '0.0.0.0', target_port, ssl=self.ssl_context)
                ws_port = target_port # Update final port
                self.config['server']['port'] = ws_port # Sync config
                break
            except OSError as e:
                self.debug.warning("VeloxAir", f"Port {target_port} occupied. Trying next...")
                if offset == 2:
                    self.debug.error("VeloxAir", "CRITICAL: No available ports found after 3 attempts.")
                    raise e
        
        # Secondary WebSocket (Plain WS fallback)
        if self.ssl_context:
            try:
                ws_port_plain = ws_port + 1
                ws_server_plain = await websockets.serve(self._ws_handler, '0.0.0.0', ws_port_plain)
                self.debug.info("VeloxAir", f"Legacy WS accessible on port {ws_port_plain}")
            except OSError:
                self.debug.warning("VeloxAir", f"Could not bind legacy fallback port {ws_port + 1}")

        mode = "HTTPS" if self.ssl_context else "HTTP"
        self.debug.info("VeloxAir", f"Air Server Active on port {ws_port} ({mode})")
        await self.discovery.start(server_name=f"Velox Air ({os.environ.get('COMPUTERNAME', 'Host')})")
        asyncio.create_task(self._clipboard_monitor_loop())
        
        try:
            await ws_server_secure.wait_closed()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass # Normal shutdown

    async def _safe_send(self, websocket, payload):
        try:
            if websocket.state.name == 'OPEN':
                # Use a strict 1.0s timeout for sending to prevent stalls
                await asyncio.wait_for(websocket.send(payload), timeout=1.0)
        except: pass
        finally: self._clients_sending.pop(websocket, None)
