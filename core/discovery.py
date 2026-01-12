# core/discovery.py

import socket
import asyncio
from zeroconf import IPVersion, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf
from .debug import Debug

def get_local_ip():
    """Gets the local LAN IP address of the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class DiscoveryManager:
    """Manages mDNS (Zeroconf) service advertisement using AsyncZeroconf."""
    def __init__(self, port: int, debug: Debug = Debug()):
        self.port = port
        self.debug = debug
        self.aio_zeroconf = None
        self.service_info = None
        self.local_ip = get_local_ip()

    async def start(self, server_name: str = "Velox Warp-Server"):
        """Starts advertising the mirroring service on the local network (Async)."""
        if self.aio_zeroconf:
            return

        desc = {'version': '1.0.0', 'path': '/client/index.html'}
        self.aio_zeroconf = AsyncZeroconf(ip_version=IPVersion.V4Only)

        # Attempt registration with retries for name collision
        for i in range(1, 6):
            try:
                name_suffix = "" if i == 1 else f"-{i}"
                current_name = f"{server_name}{name_suffix}"
                
                self.service_info = ServiceInfo(
                    "_veloxwarp._tcp.local.",
                    f"{current_name}.{socket.gethostname()}._veloxwarp._tcp.local.",
                    addresses=[socket.inet_aton(self.local_ip)],
                    port=self.port,
                    properties=desc,
                    server=f"{socket.gethostname()}.local.",
                )
                
                # Use await for asynchronous registration
                await self.aio_zeroconf.zeroconf.async_register_service(self.service_info)
                self.debug.info("Discovery", f"mDNS Service registered: {current_name} at {self.local_ip}:{self.port}")
                return
            except Exception as e:
                self.debug.warning("Discovery", f"Attempt {i} failed: {e}")
                continue
        
        self.debug.error("Discovery", "Failed to register mDNS service after multiple attempts.")

    async def stop(self):
        """Stops the mDNS advertisement (Async)."""
        if self.aio_zeroconf:
            try:
                await self.aio_zeroconf.zeroconf.async_unregister_service(self.service_info)
                await self.aio_zeroconf.close()
            except Exception: pass
            self.aio_zeroconf = None
            self.debug.info("Discovery", "mDNS Service stopped.")