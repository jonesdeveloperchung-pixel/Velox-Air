# core/server_app.py

import asyncio
import os
import json
import time
import websockets
import aiohttp.web
import mss
import pyperclip
from io import BytesIO
from .engine import StreamEngine
from .debug import Debug
from .telemetry import telemetry
from .constants import PROTOCOL_VERSION
from .performance_metrics import flush_to_telemetry, analyze_log
from utils.paths import get_resource_path

from .webrtc_manager import WebRTCManager
from .adaptive_governor import AdaptiveGovernor
from .discovery import DiscoveryManager

try:
    from velox_core import NativeInput
except ImportError:
    class NativeInput:
        def inject_binary(self, data): pass
        def inject_mouse(self, x, y, button): pass
        def inject_keyboard(self, key, down): pass

class VeloxFlowServerApp:
    def __init__(self, config: dict, debug: Debug, ssl_context):
        self.config = config
        self.debug = debug
        self.ssl_context = ssl_context
        
        # Multi-Monitor Matrix
        self.engines = {} 
        
        self.webrtc = WebRTCManager(debug)
        self.discovery = DiscoveryManager(config['server'].get('port', 8765), debug)
        self.native_input = NativeInput()
        self._clients_monitor = {} # websocket -> monitor_id
        self._clients_sending = {} 
        self._last_clipboard = ""
        
        self.web_runner = None
        self.enable_input_control = config['server'].get('enable_input_control', True)

    async def get_or_create_engine(self, monitor_id: int):
        if monitor_id in self.engines:
            return self.engines[monitor_id]
        
        self.debug.info("Server", f"Initializing Engine for Monitor {monitor_id}")
        
        # Create a specific config for this engine
        engine_config = self.config.copy()
        engine_config['server']['monitor_id'] = monitor_id
        
        engine = StreamEngine(engine_config, self.debug)
        
        mode = self.config['server'].get('mode', 'BALANCED').upper()
        tier = self.config['server'].get('tier', 'WARP').upper()
        governor = AdaptiveGovernor(self.debug, mode=mode, tier=tier)
        
        engine_data = {
            "engine": engine,
            "clients": set(),
            "governor": governor,
            "video_task": asyncio.create_task(self._engine_broadcast_loop(monitor_id)),
            "audio_task": asyncio.create_task(self._audio_broadcast_loop(monitor_id))
        }
        
        self.engines[monitor_id] = engine_data
        return engine_data

    async def _safe_send(self, websocket, payload):
        """High-performance wrapper to send data and catch network-level exceptions."""
        try:
            if websocket.state.name == 'OPEN':
                await websocket.send(payload)
        except (websockets.exceptions.ConnectionClosed, OSError, ConnectionResetError):
            # Network name no longer available or connection reset - expected in wireless environments
            pass
        except Exception as e:
            # Only log unexpected errors
            msg = str(e).lower()
            if "closed" not in msg and "reset" not in msg and "broken pipe" not in msg:
                self.debug.debug("Server", f"Send Error: {e}")
        finally:
            self._clients_sending.pop(websocket, None)

    async def _handle_input_binary(self, data: bytes):
        if not self.enable_input_control or len(data) < 8:
            return
        try:
            self.native_input.inject_binary(data)
        except Exception as e:
            self.debug.debug("Server", f"Binary input failed: {e}")

    async def _ws_handler(self, websocket):
        client_addr = websocket.remote_address
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        self.debug.info("Server", f"Client Connected: {client_addr}")
        
        current_monitor = self.config['server'].get('monitor_id', 0)
        
        try:
            # 1. Handshake
            await websocket.send(json.dumps({
                "type": "VERSION", 
                "version": PROTOCOL_VERSION,
                "monitor_id": current_monitor
            }))

            # 2. Assign to Default Monitor
            engine_data = await self.get_or_create_engine(current_monitor)
            engine_data["clients"].add(websocket)
            self._clients_monitor[websocket] = current_monitor

            # 3. Initial Frame
            initial_frame = await engine_data["engine"].get_initial_payload()
            await websocket.send(initial_frame)

            # 4. Handle messages
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        if message[0] == 0x03 or message[0] == 0x04:
                            await self._handle_input_binary(message)
                    elif isinstance(message, str):
                        try:
                            data = json.loads(message)
                            if data.get('type') == 'JOIN_MONITOR':
                                new_mon = int(data.get('monitor_id', 0))
                                if new_mon != current_monitor:
                                    # Switch Engine
                                    self.engines[current_monitor]["clients"].discard(websocket)
                                    current_monitor = new_mon
                                    engine_data = await self.get_or_create_engine(current_monitor)
                                    engine_data["clients"].add(websocket)
                                    self._clients_monitor[websocket] = current_monitor
                                    
                                    # Send fresh full frame for new monitor
                                    full_frame = await engine_data["engine"].get_initial_payload()
                                    await websocket.send(full_frame)
                                    self.debug.info("Server", f"Client {client_id} joined Monitor {new_mon}")

                            elif data.get('type') == 'WEBRTC_OFFER':
                                answer = await self.webrtc.handle_offer(client_id, data['sdp'], on_message_callback=self._handle_input_binary)
                                await websocket.send(json.dumps({
                                    "type": "WEBRTC_ANSWER",
                                    "sdp": answer["sdp"]
                                }))
                            elif data.get('type') == 'CLIENT_STATS':
                                # Feed stats to Governor of the current engine
                                engine_data["governor"].update(data)
                                new_quality = engine_data["governor"].get_quality()
                                new_tile_size = engine_data["governor"].get_tile_size()
                                
                                # Only apply if changed to avoid unnecessary re-configuration overhead
                                if new_quality != engine_data["engine"].encoder._quality:
                                    engine_data["engine"].encoder._quality = new_quality
                                    self.debug.debug("Server", f"Governor applied new quality: {new_quality}")
                                    
                                if new_tile_size != engine_data["engine"].tile_size:
                                    engine_data["engine"].tile_size = new_tile_size
                                    self.debug.debug("Server", f"Governor applied new tile size: {new_tile_size}")

                            elif data.get('type') == 'HEARTBEAT':
                                await websocket.send(json.dumps({
                                    "type": "HEARTBEAT_ACK",
                                    "timestamp": data.get('timestamp')
                                }))
                        except Exception: pass
            except websockets.exceptions.ConnectionClosed:
                pass # Expected when client leaves

        finally:
            # Cleanup
            if current_monitor in self.engines:
                self.engines[current_monitor]["clients"].discard(websocket)
            self._clients_monitor.pop(websocket, None)
            task = self._clients_sending.pop(websocket, None)
            if task: task.cancel()
            await self.webrtc.close_client(client_id)
            self.debug.info("Server", f"Client Disconnected: {client_addr}")

    async def _engine_broadcast_loop(self, monitor_id: int):
        """Dedicated loop for each monitor engine."""
        self.debug.info("Server", f"Broadcast loop for Monitor {monitor_id} active.")
        
        while monitor_id in self.engines:
            engine_data = self.engines[monitor_id]
            engine = engine_data["engine"]
            clients = engine_data["clients"]
            
            if not clients:
                # Idle if no clients, but keep engine alive for quick resume
                await asyncio.sleep(0.5)
                continue

            try:
                # 1. Congestion Check (Simplified for Multi-Engine)
                # If any client of this monitor is backpressured, we skip
                has_congestion = any(ws in self._clients_sending for ws in clients)
                
                if has_congestion:
                    await asyncio.sleep(0.01)
                    # continue # Optional: skip frame or send anyway? 
                    # For now, let's just proceed, _safe_send handles individual dropping

                # 2. CAPTURE
                payload = await engine.get_next_payload()

                if payload:
                    # Broadcast to WebRTC (UDP)
                    # Note: currently WebRTC is global, we should eventually route by monitor_id
                    # For now, broadcast to all WebRTC channels
                    asyncio.create_task(self.webrtc.broadcast_binary(payload))

                    # Broadcast to WebSocket (TCP)
                    for ws in list(clients):
                        if ws not in self._clients_sending:
                            self._clients_sending[ws] = asyncio.create_task(self._safe_send(ws, payload))

                await asyncio.sleep(0.001) 
            except Exception as e:
                self.debug.error("Server", f"Engine {monitor_id} loop error: {e}")
                await asyncio.sleep(0.1)

    async def start(self):
        # 1. Start Web Server
        app = aiohttp.web.Application()
        client_dir = get_resource_path("web_client")
        
        tier = self.config['server'].get('tier', 'WARP').upper()
        default_index = 'air.html' if tier == 'AIR' else 'index.html'
        
        app.router.add_static('/client', client_dir, show_index=True)
        app.router.add_get('/api/stats', self._handle_stats_api)
        app.router.add_get('/api/snapshot', self._handle_snapshot_api)
        app.router.add_get('/', lambda r: aiohttp.web.HTTPFound(f'/client/{default_index}'))

        self.web_runner = aiohttp.web.AppRunner(app, access_log=None)
        await self.web_runner.setup()
        web_site = aiohttp.web.TCPSite(self.web_runner, '0.0.0.0', self.config['server']['web_port'], ssl_context=self.ssl_context)
        await web_site.start()

        # 2. Start WebSocket Server
        ws_server = await websockets.serve(
            self._ws_handler, '0.0.0.0', self.config['server']['port'], 
            ssl=self.ssl_context,
            ping_interval=10, 
            ping_timeout=20, # Increased to handle mobile network jitter
            max_size=16 * 1024 * 1024 # 16MB limit for high-res frames
        )

        self.debug.info("Server", f"Multi-Monitor Server Active on port {self.config['server']['port']}")
        
        # Start mDNS advertisement (Async)
        await self.discovery.start(server_name=f"Velox-Warp ({os.environ.get('COMPUTERNAME', 'Host')})")
        
        # Start clipboard monitor
        asyncio.create_task(self._clipboard_monitor_loop())
        
        await ws_server.wait_closed()

    async def _clipboard_monitor_loop(self):
        """Monitors local system clipboard and pushes changes to all clients."""
        while True:
            try:
                current = pyperclip.paste()
                if current != self._last_clipboard:
                    self._last_clipboard = current
                    payload = json.dumps({"type": "CLIPBOARD", "text": current})
                    for ws in list(self._clients_monitor.keys()):
                        await ws.send(payload)
                    self.debug.debug("Server", "System clipboard pushed to clients")
            except Exception: pass
            await asyncio.sleep(1.0) # Check every second

    async def _handle_stats_api(self, request):
        return aiohttp.web.json_response({
            "engines": len(self.engines),
            "monitors": [m for m in self.engines.keys()],
            "version": PROTOCOL_VERSION
        })

    async def _handle_snapshot_api(self, request):
        # Default to monitor 0 for now
        if 0 not in self.engines: return aiohttp.web.Response(status=404)
        engine = self.engines[0]["engine"]
        if not engine.last_frame: return aiohttp.web.Response(status=404)
        
        pil_img = engine.last_frame.get_pil_image()
        pil_img.thumbnail((640, 360))
        buf = BytesIO()
        pil_img.save(buf, format="JPEG", quality=70)
        return aiohttp.web.Response(body=buf.getvalue(), content_type="image/jpeg")

    async def _audio_broadcast_loop(self, monitor_id: int):
        """Dedicated loop for audio streaming."""
        while monitor_id in self.engines:
            engine_data = self.engines[monitor_id]
            if not engine_data["clients"]:
                await asyncio.sleep(0.5)
                continue
            
            payload = await engine_data["engine"].get_audio_payload()
            if payload:
                # Send to all monitor clients
                for ws in list(engine_data["clients"]):
                    try:
                        if ws.state.name == 'OPEN':
                            await ws.send(payload)
                    except (websockets.exceptions.ConnectionClosed, OSError):
                        pass # Client likely disconnected abruptly
                    except: pass
            
            await asyncio.sleep(0.01) # Low latency audio pacing

    async def stop(self):
        await self.discovery.stop()
        for data in self.engines.values():
            if "video_task" in data: data["video_task"].cancel()
            if "audio_task" in data: data["audio_task"].cancel()
            if "task" in data: data["task"].cancel()
            await data["engine"].stop()
        if self.web_runner: await self.web_runner.cleanup()