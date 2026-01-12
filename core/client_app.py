# core/client_app.py

import asyncio
import tkinter as tk
import threading
import time
from .network_manager import ClientNetworkManager, TCPClientNetworkManager, UDPClientNetworkManager
from .decoder import WebPDeltaDecoder
from .jitter_buffer import JitterBuffer
from .debug import Debug
from .client_ui import ClientUI

class VeloxFlowClientApp:
    def __init__(self, config: dict, debug: Debug, ssl_context):
        self.config = config
        self.debug = debug
        self.ssl_context = ssl_context
        self.root = tk.Tk()
        self.ui = None
        self.decoder = WebPDeltaDecoder(debug=debug)
        self.jitter_buffer = JitterBuffer(debug=debug, target_fps=15, max_frames=5)
        self.asyncio_loop = asyncio.new_event_loop()
        self.network_manager = self._init_network_manager()

    def _init_network_manager(self):
        protocol = self.config['client']['protocol']
        host = self.config['client']['host']
        if protocol == "udp" and host == "localhost": host = "127.0.0.1"
        
        params = {
            "host": host,
            "port": self.config['client']['port'],
            "decoder_func": self.decoder.decode,
            "on_status_update": lambda s: self.ui.update_connection_status(s) if self.ui else None,
            "on_latency_update": lambda l: self.ui.update_latency(l) if self.ui else None,
            "jitter_buffer": self.jitter_buffer,
            "debug": self.debug
        }
        
        if protocol == "websocket": return ClientNetworkManager(**params, ssl_context=self.ssl_context)
        if protocol == "tcp": return TCPClientNetworkManager(**params, ssl_context=self.ssl_context)
        if protocol == "udp": return UDPClientNetworkManager(**params)
        raise ValueError(f"Unsupported protocol: {protocol}")

    def _process_jitter_buffer(self):
        frame_tuple = self.jitter_buffer.get_frame()
        if frame_tuple and self.ui:
            ts, data = frame_tuple
            self.ui.update_frame(data)
            self.ui.update_latency((time.time() - ts) * 1000)
        self.root.after(50, self._process_jitter_buffer)

    async def start(self):
        self.ui = ClientUI(self.root, debug=self.debug)
        self.root.after(100, self._process_jitter_buffer)
        
        def run_loop(): asyncio.set_event_loop(self.asyncio_loop); self.asyncio_loop.run_until_complete(self.network_manager.start())
        threading.Thread(target=run_loop, daemon=True).start()
        self.root.mainloop()

    async def stop(self):
        if self.network_manager: await self.network_manager.stop()
        self.root.destroy()
