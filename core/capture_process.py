import multiprocessing
import time
from queue import Empty
import asyncio

from .streamable import ScreenFrame
from .debug import Debug
from .capture import ScreenCapture

# Main function for the capture process
def capture_process_main(output_queue: multiprocessing.Queue, shutdown_event: multiprocessing.Event,
                           monitor_id: int, frame_rate: int, resolution: str, log_level: str):
    debug = Debug(log_level)
    debug.info("CaptureProcess", "Capture process started.")
    
    loop = asyncio.get_event_loop()
    capture_impl = ScreenCapture(monitor_id=monitor_id, frame_rate=frame_rate, resolution=resolution, debug=debug, loop=loop)
    
    try:
        async def _run_capture():
            async for screen_frame in capture_impl.capture_gen():
                if shutdown_event.is_set():
                    break
                output_queue.put(screen_frame)
        
        loop.run_until_complete(_run_capture())
    except asyncio.CancelledError:
        debug.info("CaptureProcess", "Capture process cancelled.")
    except KeyboardInterrupt:
        debug.info("CaptureProcess", "KeyboardInterrupt received. Exiting.")
    except Exception as e:
        debug.error("CaptureProcess", f"Error in capture process: {e}", exc_info=True)
    finally:
        debug.info("CaptureProcess", "Capture process stopped.")