from typing import Dict, Tuple, List
import numpy as np
from .streamable import ScreenFrame, Tile, DeltaFrame
from .debug import Debug
from .performance_metrics import stat_capture

class TilePartitioner:
    def __init__(self, tile_size: int = 64, debug: Debug = Debug(), force_full_frame: bool = False):
        self._tile_size = tile_size
        self._debug = debug
        self._last_frame_np = None # Store the last frame as a NumPy array for fast comparison
        self._frame_number = 0
        self._last_full_frame_data = None # Initialize
        self._full_frame_counter = 0 # Initialize
        self._full_frame_interval = 30 # Initialize
        self._force_full_frame = force_full_frame
        self._debug.debug("TilePartitioner", f"TilePartitioner initialized with _force_full_frame={self._force_full_frame}")

    @property
    def tile_size(self):
        return self._tile_size
    
    @tile_size.setter
    def tile_size(self, value):
        if self._tile_size != value:
            self._debug.debug("TilePartitioner", f"Tile size updated to {value}")
            self._tile_size = value

    @stat_capture
    def partition_and_detect_changes(self, current_frame: ScreenFrame) -> DeltaFrame:
        """
        Partitions the current frame into tiles, compares them with the previous frame
        using NumPy for performance, and returns a DeltaFrame containing only the changed tiles.
        """
        self._frame_number += 1
        changed_tiles: List[Tile] = []
        full_frame_fallback = False
        
        curr_np = current_frame.get_np_array()

        # If no last frame or resolution changed, force full frame
        if self._last_frame_np is None or self._last_frame_np.shape != curr_np.shape:
            self._debug.info("TilePartitioner", "Forcing full frame for initial capture or resolution change.")
            full_frame_fallback = True
            # Create a single tile representing the entire screen
            changed_tiles.append(current_frame.get_tile(0, 0, current_frame.width, current_frame.height))
            # Store current frame for next comparison
            self._last_frame_np = curr_np.copy()
        else:
            # Iterate through the frame in tile_size chunks and compare using NumPy slices
            for y in range(0, current_frame.height, self._tile_size):
                for x in range(0, current_frame.width, self._tile_size):
                    # Ensure tile doesn't go out of bounds
                    tile_width = min(self._tile_size, current_frame.width - x)
                    tile_height = min(self._tile_size, current_frame.height - y)

                    if tile_width <= 0 or tile_height <= 0: # Skip if tile is empty
                        continue

                    # Fast comparison using NumPy array_equal on slices
                    if not np.array_equal(
                        curr_np[y:y+tile_height, x:x+tile_width],
                        self._last_frame_np[y:y+tile_height, x:x+tile_width]
                    ):
                        changed_tiles.append(current_frame.get_tile(x, y, tile_width, tile_height))
            
            # Update last frame for next comparison
            self._last_frame_np = curr_np.copy()
        
        self._debug.debug("TilePartitioner", f"Frame {self._frame_number}: Detected {len(changed_tiles)} changed tiles (Full frame fallback: {full_frame_fallback}).")

        return DeltaFrame(self._frame_number, changed_tiles, full_frame_fallback=full_frame_fallback)

    def create_full_frame_delta(self, screen_frame: ScreenFrame) -> DeltaFrame:
        """
        Creates a DeltaFrame representing a full screen update from a given ScreenFrame.
        This is used for initial client connections.
        """
        self._debug.debug("TilePartitioner", "Creating explicit full frame delta.")
        full_screen_tile = screen_frame.get_tile(0, 0, screen_frame.width, screen_frame.height)
        delta_frame = DeltaFrame(0, [full_screen_tile], full_frame_fallback=True) # Frame number 0 for initial frame
        
        # Also update last_frame_np to ensure subsequent deltas are correct
        self._last_frame_np = screen_frame.get_np_array().copy()
        
        return delta_frame

    def reset(self):
        """
        Resets the partitioner's state, clearing last frame data.
        """
        self._last_frame_np = None
        self._frame_number = 0
        self._debug.info("TilePartitioner", "Resetting tile partitioner state.")