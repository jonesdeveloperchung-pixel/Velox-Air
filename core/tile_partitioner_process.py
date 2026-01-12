import multiprocessing
import time
from queue import Empty

from .tile_partitioner import TilePartitioner
from .debug import Debug
from .streamable import ScreenFrame, DeltaFrame

def tile_partitioner_process_main(input_queue: multiprocessing.Queue, output_queue: multiprocessing.Queue, 
                                  tile_size: int, force_full_frame: bool, log_level: str):
    """Main function for the tile partitioner process."""
    debug = Debug(log_level)
    tile_partitioner = TilePartitioner(tile_size=tile_size, debug=debug, force_full_frame=force_full_frame)
    debug.info("TilePartitionerProcess", "Tile partitioner process started.")

    while True:
        try:
            screen_frame = input_queue.get(timeout=1) # Wait for a screen frame
            if screen_frame is None: # Sentinel value for shutdown
                debug.info("TilePartitionerProcess", "Received shutdown signal. Exiting.")
                break
            
            delta_frame = tile_partitioner.partition_and_detect_changes(screen_frame)
            output_queue.put(delta_frame)
            debug.debug("TilePartitionerProcess", f"Partitioned frame and put into output queue (tiles: {len(delta_frame.changed_tiles)}).")
        except Empty:
            # No frame in queue, continue looping to check for shutdown signal
            pass
        except KeyboardInterrupt:
            debug.info("TilePartitionerProcess", "KeyboardInterrupt received. Exiting.")
            break
        except Exception as e:
            debug.error("TilePartitionerProcess", f"Error in tile partitioner process: {e}", exc_info=True)
            # Optionally put an error signal into output_queue
            output_queue.put(None) # Indicate an error or corrupted frame

    debug.info("TilePartitionerProcess", "Tile partitioner process stopped.")
