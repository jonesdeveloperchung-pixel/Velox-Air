import multiprocessing
import time
from queue import Empty

from .encoder import WebPEncoder
from .debug import Debug
from .streamable import DeltaFrame

def encoder_process_main(input_queue: multiprocessing.Queue, output_queue: multiprocessing.Queue, 
                          quality: int, method: int, lossless: bool, log_level: str):
    """Main function for the encoder process."""
    debug = Debug(log_level)
    encoder = WebPEncoder(quality=quality, method=method, lossless=lossless, debug=debug)
    debug.info("EncoderProcess", "Encoder process started.")

    while True:
        try:
            delta_frame = input_queue.get(timeout=1) # Wait for a delta frame
            if delta_frame is None: # Sentinel value for shutdown
                debug.info("EncoderProcess", "Received shutdown signal. Exiting.")
                break
            
            encoded_frame = encoder.encode(delta_frame)
            output_queue.put(encoded_frame)
            debug.debug("EncoderProcess", f"Encoded frame and put into output queue (size: {len(encoded_frame)}).")
        except Empty:
            # No frame in queue, continue looping to check for shutdown signal
            pass
        except KeyboardInterrupt:
            debug.info("EncoderProcess", "KeyboardInterrupt received. Exiting.")
            break
        except Exception as e:
            debug.error("EncoderProcess", f"Error in encoder process: {e}", exc_info=True)
            # Optionally put an error signal into output_queue
            output_queue.put(None) # Indicate an error or corrupted frame

    debug.info("EncoderProcess", "Encoder process stopped.")
