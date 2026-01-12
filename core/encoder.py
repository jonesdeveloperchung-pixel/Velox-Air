from abc import ABC, abstractmethod
import time
import struct
from io import BytesIO
import concurrent.futures
import os

from PIL import Image

from .streamable import Streamable, DeltaFrame, Tile
from .debug import Debug
from .performance_metrics import stat_capture

class Encoder(ABC):
    """An interface for encoding streamable data."""

    @abstractmethod
    def encode(self, data: DeltaFrame) -> bytes:
        """Encode the streamable data."""
        pass

class JpegEncoder(Encoder):
    """A class for encoding images as JPEGs."""

    def __init__(self, quality: int = 70, debug: Debug = Debug()):
        self._quality = quality
        self._debug = debug

    def encode(self, data: DeltaFrame) -> bytes:
        self._debug.warning("JpegEncoder", "Warning: JpegEncoder is not fully implemented for DeltaFrames.")
        return b""

class H265Encoder(Encoder):
    """Hardware accelerated H.265 encoder using PyAV/ffmpeg."""
    def __init__(self, quality: int = 25, debug: Debug = Debug()):
        self._quality = quality
        self._debug = debug
        self._codec = None
        self._container = None
        self._stream = None
        self._init_av()

    def _init_av(self):
        try:
            import av
            self._container = av.open(BytesIO(), mode='w', format='hevc')
            self._stream = self._container.add_stream('hevc', rate=60)
            self._stream.width = 1920
            self._stream.height = 1080
            self._stream.pix_fmt = 'yuv420p'
            self._stream.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'crf': str(self._quality)}
            self._debug.info("H265Encoder", "HEVC Hardware Encoder Ready")
        except Exception as e:
            self._debug.warning("H265Encoder", f"Failed to init HEVC: {e}")

    def encode(self, delta_frame: DeltaFrame) -> bytes:
        # Prepend Type 0x01 for Video
        return b"\x01" + b"" 

class WebPEncoder(Encoder):
    """A class for encoding images as WebP."""

    def __init__(self, quality: int = 70, method: int = 0, lossless: bool = False, debug: Debug = Debug()):
        self._quality = quality
        self._method = method
        self._lossless = lossless
        self._debug = debug
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) + 4))

    @stat_capture
    def _encode_tile(self, tile: Tile) -> bytes:
        """Helper to encode a single tile, intended for use with an executor."""
        with BytesIO() as buf:
            tile.image_data.save(buf, format="WEBP", quality=self._quality, method=self._method, lossless=self._lossless)
            return buf.getvalue()

    @stat_capture
    def encode(self, delta_frame: DeltaFrame) -> bytes:
        """Encode the DeltaFrame (changed tiles) as a single WebP payload."""
        payload_parts = []

        # Prepend timestamp in milliseconds (Int64)
        timestamp_ms = int(time.time() * 1000)
        timestamp_bytes = struct.pack('<q', timestamp_ms) # '<q' for Int64, little-endian
        payload_parts.append(timestamp_bytes)

        if delta_frame.full_frame_fallback:
            if not delta_frame.changed_tiles or len(delta_frame.changed_tiles) != 1:
                return b""
            
            full_screen_tile = delta_frame.changed_tiles[0]
            encoded_full_frame_data = self._encode_tile(full_screen_tile)
            
            payload_parts.append(struct.pack('<i', 0)) 
            payload_parts.append(struct.pack('<ii', full_screen_tile.width, full_screen_tile.height)) 
            payload_parts.append(struct.pack('<i', len(encoded_full_frame_data))) 
            payload_parts.append(encoded_full_frame_data)

        else:
            payload_parts.append(struct.pack('<i', len(delta_frame.changed_tiles))) 

            if len(delta_frame.changed_tiles) > 1:
                encoded_tiles_data = list(self._executor.map(self._encode_tile, delta_frame.changed_tiles))
            elif len(delta_frame.changed_tiles) == 1:
                encoded_tiles_data = [self._encode_tile(delta_frame.changed_tiles[0])]
            else:
                encoded_tiles_data = []

            for i, tile in enumerate(delta_frame.changed_tiles):
                encoded_tile_data = encoded_tiles_data[i]
                payload_parts.append(struct.pack('<iiii', tile.x, tile.y, tile.width, tile.height)) 
                payload_parts.append(struct.pack('<i', len(encoded_tile_data))) 
                payload_parts.append(encoded_tile_data)

        # PREPEND TYPE 0x01
        return b"\x01" + b"".join(payload_parts)