import asyncio
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from .debug import Debug
from .discovery import get_local_ip

class WebRTCManager:
    def __init__(self, debug: Debug):
        self.debug = debug
        self.pcs = {} 
        self.data_channels = {} 
        self.local_ip = get_local_ip()

    async def handle_offer(self, client_id, sdp, on_message_callback=None):
        """Handles a WebRTC Offer from a client and returns an Answer."""
        # Use a specific configuration to help mobile devices
        config = RTCConfiguration(iceServers=[
            RTCIceServer(urls=["stun:stun.l.google.com:19302"])
        ])
        pc = RTCPeerConnection(configuration=config)
        self.pcs[client_id] = pc

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            self.debug.info("WebRTC", f"PC {client_id} state is {pc.connectionState}")
            if pc.connectionState in ["failed", "closed"]:
                await self.close_client(client_id)

        @pc.on("datachannel")
        def on_datachannel(channel):
            self.debug.info("WebRTC", f"Data Channel '{channel.label}' opened by {client_id}")
            if channel.label == "screen_data":
                self.data_channels[client_id] = channel
                
                @channel.on("message")
                async def on_message(message):
                    # HIGH PERFORMANCE PATH: Receive UDP Input
                    if on_message_callback and isinstance(message, bytes):
                        await on_message_callback(message)

                @channel.on("close")
                def on_close():
                    self.data_channels.pop(client_id, None)

        # Set Remote Description (The Offer)
        offer = RTCSessionDescription(sdp=sdp, type="offer")
        await pc.setRemoteDescription(offer)

        # Create Answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

    async def close_client(self, client_id):
        """Closes connection for a specific client."""
        pc = self.pcs.pop(client_id, None)
        if pc:
            await pc.close()
        self.data_channels.pop(client_id, None)

    async def broadcast_binary(self, data):
        """Broadcasts binary payload over all open WebRTC Data Channels."""
        if not self.data_channels:
            return

        for client_id, channel in self.data_channels.items():
            if channel.readyState == "open":
                # WebRTC Data Channel has a bufferedAmount limit (typically 16MB)
                if channel.bufferedAmount < 1024 * 1024: # 1MB safety limit for high-frequency
                    try: channel.send(data)
                    except: pass
                else:
                    self.debug.debug("WebRTC", f"Backpressure: Skipping frame for {client_id}")

    async def send_to_client(self, client_id, data):
        """Sends binary payload to a specific client."""
        channel = self.data_channels.get(client_id)
        if channel and channel.readyState == "open":
             if channel.bufferedAmount < 1024 * 1024:
                 try: channel.send(data)
                 except: pass

        
    async def stop(self):
        """Shutdown all connections."""
        for client_id in list(self.pcs.keys()):
            await self.close_client(client_id)
        self.debug.info("WebRTCManager", "All WebRTC connections stopped")
