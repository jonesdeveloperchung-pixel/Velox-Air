from abc import ABC, abstractmethod
import struct
from io import BytesIO
from typing import Any, List

from PIL import Image

from .streamable import Streamable, ScreenFrame, DeltaFrame, Tile
from .debug import Debug

class Decoder(ABC):
    """An interface for decoding streamable data."""

    @abstractmethod
    def decode(self, data: bytes) -> Streamable:
        """Decode the raw bytes into streamable data."""
        pass

class JpegDecoder(Decoder):
    """A class for decoding JPEG images."""

    def __init__(self, debug: Debug = Debug()):
        self._debug = debug

    def decode(self, data: bytes) -> tuple[Streamable, float]:
        """Decode the JPEG bytes into a ScreenFrame and return the timestamp."""
        # Extract timestamp (first 8 bytes for a double)
        timestamp = struct.unpack('<d', data[:8])[0]
        jpeg_data = data[8:]

        self._debug.debug("JpegDecoder", f"Received jpeg_data starting with: {jpeg_data[:10].hex()}")

        img = Image.open(BytesIO(jpeg_data))
        return ScreenFrame(img), timestamp

class WebPDecoder(Decoder):
    """A class for decoding WebP images."""

    def __init__(self, debug: Debug = Debug()):
        self._debug = debug

    def decode(self, data: bytes) -> tuple[Streamable, float]:
        """Decode the WebP bytes into a ScreenFrame and return the timestamp."""
        # Extract timestamp (first 8 bytes for a double)
        timestamp = struct.unpack('<d', data[:8])[0]
        webp_data = data[8:]

        self._debug.debug("WebPDecoder", f"Received webp_data starting with: {webp_data[:10].hex()}")

        img = Image.open(BytesIO(webp_data))
        return ScreenFrame(img), timestamp

class WebPDeltaDecoder(Decoder):
    """A class for decoding WebP DeltaFrame payloads."""

    def __init__(self, debug: Debug = Debug()):
        self._debug = debug

    def decode(self, data: bytes) -> tuple[DeltaFrame, float]:
        """Decode the binary payload into a DeltaFrame and return the timestamp."""
        self._debug.debug("WebPDeltaDecoder", f"Decoding payload of size {len(data)}.")
        offset = 0

        # Extract timestamp (8 bytes i64 milliseconds)
        raw_ts = struct.unpack('<q', data[offset:offset+8])[0]
        timestamp = raw_ts / 1000.0 # Convert to float seconds for JitterBuffer
        offset += 8

        # Extract number of tiles (4 bytes)
        num_tiles = struct.unpack('<i', data[offset:offset+4])[0]
        offset += 4

        self._debug.debug("WebPDeltaDecoder", f"Payload contains timestamp={timestamp}, num_tiles={num_tiles}.")

        changed_tiles: List[Tile] = []
        full_frame_fallback = False

        if num_tiles == 0: # This indicates a full frame fallback
            full_frame_fallback = True
            # Read full frame dimensions
            full_width, full_height = struct.unpack('<ii', data[offset:offset+8])
            offset += 8
            # Read full image data length
            full_image_data_length = struct.unpack('<i', data[offset:offset+4])[0]
            offset += 4
            # Read full image data
            full_image_data = data[offset:offset+full_image_data_length]
            offset += full_image_data_length

            try:
                img = Image.open(BytesIO(full_image_data))
                changed_tiles.append(Tile(0, 0, full_width, full_height, img)) # Single tile for full screen
                self._debug.debug("WebPDeltaDecoder", f"Decoded full frame fallback {full_width}x{full_height}.")
            except Exception as e:
                self._debug.error("WebPDeltaDecoder", f"Error decoding full frame: {e}")

        else:
            for i in range(num_tiles):
                # Extract tile metadata (4 ints = 16 bytes)
                x, y, width, height = struct.unpack('<iiii', data[offset:offset+16])
                offset += 16

                # Extract tile data length (4 bytes)
                tile_data_length = struct.unpack('<i', data[offset:offset+4])[0]
                offset += 4

                # Extract tile data
                tile_data = data[offset:offset+tile_data_length]
                offset += tile_data_length

                # Decode WebP tile data
                try:
                    img = Image.open(BytesIO(tile_data))
                    changed_tiles.append(Tile(x, y, width, height, img))
                    self._debug.debug("WebPDeltaDecoder", f"Decoded tile {i+1}/{num_tiles} at {x},{y} {width}x{height}.")
                except Exception as e:
                    self._debug.error("WebPDeltaDecoder", f"Error decoding tile {i+1}/{num_tiles}: {e}")
                    # Optionally, handle corrupted tile (e.g., skip or use a placeholder)

            self._debug.debug("WebPDeltaDecoder", f"Decoded {len(changed_tiles)} changed tiles from payload.")
        
        return DeltaFrame(frame_number=0, changed_tiles=changed_tiles, full_frame_fallback=full_frame_fallback), timestamp
