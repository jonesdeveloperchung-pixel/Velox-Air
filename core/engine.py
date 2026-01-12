# core/engine.py

import asyncio
import time
import struct
from typing import Optional
from io import BytesIO
from .capture import CaptureFactory
from .tile_partitioner import TilePartitioner
from .encoder import WebPEncoder
from .streamable import DeltaFrame, ScreenFrame
from .debug import Debug

class StreamEngine:
    """The high-performance core that handles the capture-to-payload pipeline."""
    def __init__(self, config: dict, debug: Debug):
        self.config = config
        self.debug = debug
        self.capture = CaptureFactory.create(
            monitor_id=config['server'].get('monitor_id', 0),
            frame_rate=config['server'].get('frame_rate', 30),
            resolution=config['server'].get('resolution', 'full'),
            debug=debug,
            optimize_pipeline=config['server'].get('optimize_capture_pipeline', True),
            enable_dxcam=config['server'].get('enable_dxcam_fallback', False)
        )
        self.partitioner = TilePartitioner(debug=debug)
        self.encoder = WebPEncoder(
            quality=config['server'].get('webp_quality', 70),
            debug=debug
        )
        self._tile_size = 128 # Default
        self._last_encoded_payload = None
        self.audio = None
        
        # Initialize Audio for High-End tiers (Skip for FLOW as it is dropped)
        tier = config['server'].get('tier', 'WARP').upper()
        if tier != "FLOW":
            try:
                import velox_core
                self.audio = velox_core.VeloxAudio()
                debug.info("StreamEngine", "Native Audio Engine Initialized")
            except Exception as e:
                debug.warning("StreamEngine", f"Native Audio not available: {e}")

        self._lock = asyncio.Lock()
        self.last_frame: Optional[ScreenFrame] = None
        self._capture_iter = None

    @property
    def tile_size(self):
        return self._tile_size

    @tile_size.setter
    def tile_size(self, value):
        self._tile_size = value
        if hasattr(self, 'partitioner'):
            self.partitioner.tile_size = value

    async def _get_frame(self):
        async with self._lock:
            if self._capture_iter is None:
                self._capture_iter = self.capture.capture_gen()
            try:
                return await self._capture_iter.__anext__()
            except StopAsyncIteration:
                self._capture_iter = self.capture.capture_gen()
                return await self._capture_iter.__anext__()

    async def get_next_payload(self, force_full: bool = False):
        """Captures, partitions, and encodes the next frame."""
        t_start = time.perf_counter()
        from .performance_metrics import TelemetryLogger

        # 1. OPTIMIZED FAST PATH: Use Rust Native Pipeline if available
        from .capture import VeloxRustCapture
        if isinstance(self.capture, VeloxRustCapture):
            loop = asyncio.get_event_loop()
            try:
                if force_full:
                    self.capture.capturer.force_full_refresh()

                # Adaptive call to handle different versions of velox_core
                try:
                    payload = await loop.run_in_executor(
                        None, 
                        self.capture.capturer.capture_delta_payload, 
                        self.tile_size, 
                        self.encoder._quality,
                        0, 0, 0,
                        1.0, # Default scale
                        1    # Default bg_skip
                    )
                except TypeError:
                    payload = await loop.run_in_executor(
                        None, 
                        self.capture.capturer.capture_delta_payload, 
                        self.tile_size, 
                        self.encoder._quality,
                        0, 0, 0
                    )
                
                if payload:
                    import struct
                    ts = struct.unpack('<q', payload[1:9])[0]
                    TelemetryLogger.log_frame(ts, "HOST_PIPELINE", (time.perf_counter() - t_start) * 1000)
                    return payload
                return None
            except Exception as e:
                self.debug.error("StreamEngine", f"Native pipeline failed: {e}")

        # 2. LEGACY PATH
        frame = await self._get_frame()
        self.last_frame = frame 
        
        loop = asyncio.get_event_loop()
        if force_full:
            delta_frame = self.partitioner.create_full_frame_delta(frame)
        else:
            delta_frame = await loop.run_in_executor(
                None, self.partitioner.partition_and_detect_changes, frame
            )
        
        if delta_frame.changed_tiles or delta_frame.full_frame_fallback:
            payload = await loop.run_in_executor(
                None, self.encoder.encode, delta_frame
            )
            # Legacy encoder also has the timestamp at index 1
            import struct
            ts = struct.unpack('<q', payload[1:9])[0]
            TelemetryLogger.log_frame(ts, "HOST_PIPELINE_LEGACY", (time.perf_counter() - t_start) * 1000)
            return payload 
        return None

    async def get_initial_payload(self):
        """Generates a full-frame payload for new connections."""
        frame = await self._get_frame()
        self.last_frame = frame # Ensure last_frame is populated for snapshots
        delta = self.partitioner.create_full_frame_delta(frame)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.encoder.encode, delta)

    async def get_snapshot_image(self):
        """Returns a PIL Image snapshot of the current screen for the dashboard."""
        if self.last_frame:
            try:
                # ScreenFrame might store PIL or NumPy depending on capture source
                from PIL import Image
                data = self.last_frame.get_data()
                if isinstance(data, np.ndarray):
                    return Image.fromarray(data)
                return data # Already PIL
            except Exception as e:
                self.debug.debug("StreamEngine", f"Snapshot extraction failed: {e}")
        
        # Fallback: Trigger a legacy capture if last_frame is missing
        # Try a few times to account for engine startup
        for _ in range(3):
            try:
                frame = await asyncio.wait_for(self._get_frame(), timeout=2.0)
                if frame:
                    self.last_frame = frame
                    return frame.get_pil_image()
            except:
                await asyncio.sleep(0.5)
        return None

    async def stop(self):
        """Properly shuts down the engine and its capture backend."""
        async with self._lock:
            if self._capture_iter:
                try:
                    await self._capture_iter.aclose()
                except Exception as e:
                    self.debug.error("StreamEngine", f"Error closing capture generator: {e}")
                self._capture_iter = None
            
            # Explicitly stop the capture backend
            if hasattr(self.capture, 'stop'):
                self.capture.stop()
                
        self.debug.info("StreamEngine", "Engine stopped.")

    async def get_audio_payload(self):
        """Retrieves the next chunk of audio. Warp tier uses raw PCM for Web compatibility."""
        if not self.audio:
            return None
        
        loop = asyncio.get_event_loop()
        try:
            tier = self.config['server'].get('tier', 'WARP').upper()
            
            if tier == "WARP" and hasattr(self.audio, 'get_audio_packet_raw'):
                # Send Raw PCM for Web Client compatibility
                packet = await loop.run_in_executor(None, self.audio.get_audio_packet_raw)
            else:
                # Send Opus for Native/Flow clients
                packet = await loop.run_in_executor(None, self.audio.get_audio_packet)
                
            if packet:
                # Wrap in binary protocol header: [Type(1)] [Size(4)] [Data(N)]
                header = struct.pack('<BI', 0x05, len(packet))
                return header + packet
            return None
        except Exception as e:
            self.debug.error("StreamEngine", f"Audio capture failed: {e}")
            return None
