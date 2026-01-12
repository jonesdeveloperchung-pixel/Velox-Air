import asyncio
import json
import websockets
import ssl
import time
from typing import Callable, Coroutine, Set, Dict, Optional, Any
import struct
import socket

from .debug import Debug
from .encoder import Encoder
from .capture import ScreenCapture
from .jitter_buffer import JitterBuffer
from .tile_partitioner import TilePartitioner
from .streamable import ScreenFrame, DeltaFrame
from .constants import PROTOCOL_VERSION

class ServerNetworkManager:
    """Manages WebSocket connections and data sending for the server."""
    def __init__(self, host: str, port: int, debug: Debug, 
                 capture_instance: ScreenCapture, 
                 encoder_instance: Encoder, 
                 tile_partitioner_instance: TilePartitioner, 
                 ssl_context: ssl.SSLContext):
        self._host = host
        self._port = port
        self._debug = debug
        self._clients: Set[Any] = set()
        self._ssl_context = ssl_context
        self._capture = capture_instance
        self._encoder = encoder_instance
        self._tile_partitioner = tile_partitioner_instance
        self._heartbeat_interval = 5.0
        self._loop = asyncio.get_event_loop()
        self._broadcast_task = None
        self._bytes_sent = 0
        self._kbps = 0.0
        self._last_kbps_update = time.time()

    async def _handler(self, websocket):
        self._debug.info("ServerNetworkManager", f"Client connected: {websocket.remote_address}")
        try:
            await websocket.send(json.dumps({"type": "VERSION", "version": PROTOCOL_VERSION}))
            self._clients.add(websocket)
            receive_task = asyncio.create_task(self._receive_control_messages(websocket))
            heartbeat_task = asyncio.create_task(self._heartbeat_sender(websocket))
            await websocket.wait_closed()
        except Exception as e:
            self._debug.error("ServerNetworkManager", f"Handler error: {e}")
        finally:
            if websocket in self._clients: self._clients.remove(websocket)
            self._debug.info("ServerNetworkManager", f"Client disconnected: {websocket.remote_address}")

    async def _broadcast_loop(self):
        try:
            async for frame in self._capture.capture_gen():
                if not self._clients:
                    await asyncio.sleep(0.1)
                    continue
                delta_frame = await self._loop.run_in_executor(None, self._tile_partitioner.partition_and_detect_changes, frame)
                if delta_frame.changed_tiles or delta_frame.full_frame_fallback:
                    encoded_frame = await self._loop.run_in_executor(None, self._encoder.encode, delta_frame)
                    # 添加類型字節 0x01
                    final_msg = b'\x01' + encoded_frame
                    send_tasks = [ws.send(final_msg) for ws in self._clients if getattr(ws, 'open', True) and str(getattr(ws, 'state', 'OPEN')) == 'OPEN']
                    if send_tasks: await asyncio.gather(*send_tasks, return_exceptions=True)
        except Exception as e:
            self._debug.error("ServerNetworkManager", f"Broadcast loop error: {e}")

    async def _receive_control_messages(self, websocket):
        try:
            async for message in websocket:
                if isinstance(message, str):
                    data = json.loads(message)
                    if data.get("type") == "HEARTBEAT":
                        await websocket.send(json.dumps({"type": "HEARTBEAT_ACK", "timestamp": data.get("timestamp")}))
        except: pass

    async def _heartbeat_sender(self, websocket):
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                if getattr(websocket, 'open', True) and str(getattr(websocket, 'state', 'OPEN')) == 'OPEN':
                    await websocket.send(json.dumps({"type": "HEARTBEAT", "timestamp": time.time()}))
                else: break
        except: pass

    async def start(self):
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        async with websockets.serve(self._handler, self._host, self._port, ssl=self._ssl_context):
            await asyncio.Future()

    async def stop(self):
        if self._broadcast_task: self._broadcast_task.cancel()
        for ws in self._clients: await ws.close()

class ClientNetworkManager:
    """Manages WebSocket connection and data receiving for the client."""
    def __init__(self, host: str, port: int, 
                 decoder_func: Callable[[bytes], DeltaFrame], 
                 on_status_update: Callable[[str], None], 
                 on_latency_update: Callable[[float], None],
                 jitter_buffer: JitterBuffer,
                 debug: Debug, 
                 ssl_context: ssl.SSLContext):
        self._host = host
        self._port = port
        self._decoder_func = decoder_func
        self._on_status_update = on_status_update
        self._on_latency_update = on_latency_update
        self._jitter_buffer = jitter_buffer
        self._debug = debug
        self._ssl_context = ssl_context
        self._websocket = None

    async def start(self):
        # 先嘗試 WSS，如果失敗則降級到 WS
        for protocol in ["wss", "ws"]:
            url = f"{protocol}://{self._host}:{self._port}"
            self._debug.info("ClientNetworkManager", f"Connecting to {url}...")
            self._on_status_update(f"Connecting ({protocol.upper()})...")
            
            try:
                ssl_ctx = self._ssl_context if protocol == "wss" else None
                async with websockets.connect(
                    url, 
                    ssl=ssl_ctx,
                    open_timeout=5
                ) as websocket:
                    self._websocket = websocket
                    self._debug.info("ClientNetworkManager", f"Connected via {protocol.upper()}")
                    self._on_status_update("Connected")
                    await websocket.send(json.dumps({"type": "VERSION", "version": PROTOCOL_VERSION}))
                    await self._receive_loop()
                    return # 成功後退出
            except Exception as e:
                self._debug.warning("ClientNetworkManager", f"{protocol.upper()} failed: {e}")
                if protocol == "ws":
                    self._debug.error("ClientNetworkManager", "All connection attempts failed.")
                    self._on_status_update(f"Error: {type(e).__name__}")

    async def _receive_loop(self):
        while self._websocket:
            if not (getattr(self._websocket, 'open', True) and str(getattr(self._websocket, 'state', 'OPEN')) == 'OPEN'):
                break
            try:
                message = await self._websocket.recv()
                if isinstance(message, bytes):
                    msg_type = message[0]
                    payload = message[1:]
                    if msg_type == 0x01: # WebP Delta
                        decoded_frame, timestamp = self._decoder_func(payload)
                        self._jitter_buffer.add_frame(decoded_frame, timestamp)
                elif isinstance(message, str):
                    data = json.loads(message)
                    if data.get("type") == "HEARTBEAT":
                        await self._websocket.send(json.dumps({"type": "HEARTBEAT_ACK", "timestamp": data.get("timestamp")}))
                    elif data.get("type") == "HEARTBEAT_ACK":
                        latency = (time.time() - data.get("timestamp", 0)) * 1000
                        self._on_latency_update(latency)
            except Exception as e:
                self._debug.error("ClientNetworkManager", f"Receive error: {e}")
                break

    async def stop(self):
        if self._websocket: await self._websocket.close()

# TCP/UDP Managers kept minimal for brevity but fixed structures
class TCPServerNetworkManager:
    def __init__(self, *args, **kwargs): pass
    async def start(self): pass
    async def stop(self): pass

class TCPClientNetworkManager:
    def __init__(self, *args, **kwargs): pass
    async def start(self): pass
    async def stop(self): pass

class UDPServerNetworkManager:
    def __init__(self, *args, **kwargs): pass
    async def start(self): pass
    async def stop(self): pass

class UDPClientNetworkManager:
    def __init__(self, *args, **kwargs): pass
    async def start(self): pass
    async def stop(self): pass