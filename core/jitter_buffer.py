import collections
import time
from typing import Optional, Tuple, Any, Deque
import bisect

from .debug import Debug
from .performance_metrics import stat_capture

class JitterBuffer:
    """
    A jitter buffer to smooth out variations in network latency for incoming frames.
    It stores frames and releases them at a steady rate, with adaptive sizing and re-ordering.
    """

    def __init__(self, debug: Debug = Debug(), target_fps: int = 30, current_buffer_size_ms: int = 100, max_frames: int = 3):
        self._debug = debug
        self._frames: Deque[Tuple[float, Any]] = collections.deque() # Stores (timestamp, frame_data) tuples
        self._last_playback_time = 0.0 # time.time() when the last frame was played
        self._last_played_frame_data: Optional[Tuple[float, Any]] = None # Stores the data of the last successfully played frame (timestamp, data)
        
        # Fixed buffer parameters
        self._current_buffer_size_ms = current_buffer_size_ms
        self._target_fps = target_fps
        self._max_frames = max(1, max_frames) # Ensure at least 1 frame
        self._debug.info("JitterBuffer", f"Initialized with current_buffer_size_ms={self._current_buffer_size_ms}, target_fps={target_fps}, max_frames={self._max_frames}")

        # Metrics for adaptive adjustment (not used with fixed buffer)
        self._arrival_times = collections.deque(maxlen=10) # Store recent frame arrival times
        self._playback_times = collections.deque(maxlen=10) # Store recent frame playback times

    def _calculate_max_frames(self, buffer_ms: int) -> int:
        if self._target_fps == 0:
            return 1 # Avoid division by zero
        return max(1, int(buffer_ms / (1000 / self._target_fps)))

    def add_frame(self, frame_data: Any, timestamp: float):
        """
        Adds a frame to the jitter buffer, maintaining sorted order by timestamp.
        :param frame_data: The actual frame data (e.g., decoded image).
        :param timestamp: The timestamp when the frame was captured on the server.
        """
        # Insert frame while maintaining sorted order by timestamp
        # bisect_left finds insertion point for new_frame to maintain sorted order
        # We need to convert deque to list for bisect, then back to deque. This is inefficient for very large deques.
        # For typical jitter buffer sizes (e.g., 5-30 frames), this is acceptable.
        new_frame_tuple = (timestamp, frame_data)
        
        # Find insertion point
        insert_index = bisect.bisect_left([f[0] for f in self._frames], timestamp)
        self._frames.insert(insert_index, new_frame_tuple)

        self._arrival_times.append(time.time()) # Record arrival time

        self._debug.debug("JitterBuffer", f"Added frame (ts: {timestamp}). Current buffer size: {len(self._frames)}")

        # If buffer exceeds max_frames + margin, drop the oldest frame
        # Margin allows for temporary bursts without data loss
        overflow_margin = 2
        if len(self._frames) > self._max_frames + overflow_margin:
            dropped_timestamp, _ = self._frames.popleft()
            self._debug.warning("JitterBuffer", f"Buffer overflow: Dropped oldest frame (timestamp: {dropped_timestamp}). Current buffer size: {len(self._frames)}")


    @stat_capture
    def get_frame(self) -> Optional[Tuple[float, Any]]:
        """
        Retrieves a frame from the buffer for playback.
        This method tries to maintain a steady playback rate and compensate for jitter.
        It also implements adaptive buffer sizing.
        """
        current_time = time.time()

        # Adaptive buffer adjustment logic
        self._adjust_buffer_size()

        # If this is the very first frame, play it immediately
        if not self._last_playback_time and self._frames:
            frame_tuple = self._frames.popleft()
            self._last_playback_time = current_time
            self._last_played_frame_data = frame_tuple
            self._playback_times.append(current_time)
            self._debug.info("JitterBuffer", "Playing first frame immediately.")
            return frame_tuple

        # If the buffer is empty, return None (avoid redundant updates)
        if not self._frames:
            self._debug.debug("JitterBuffer", "Buffer empty. Returning None.")
            return None

        # Determine if a frame is ready for playback based on target_fps and current buffer level
        # We want to maintain _current_buffer_size_ms of buffered content
        expected_next_playback_time = self._last_playback_time + (1.0 / self._target_fps)

        # Priority 1: Buffer is nearly full, release immediately to prevent overflow and reduce latency
        if len(self._frames) >= self._max_frames:
            frame_tuple = self._frames.popleft()
            self._last_playback_time = current_time
            self._last_played_frame_data = frame_tuple
            self._playback_times.append(current_time)
            self._debug.debug("JitterBuffer", f"Buffer full ({len(self._frames)+1} frames). Releasing frame to avoid overflow.")
            return frame_tuple

        # Priority 2: It is time for the next frame
        if self._frames and current_time >= expected_next_playback_time:
            frame_tuple = self._frames.popleft()
            self._last_playback_time = current_time
            self._last_played_frame_data = frame_tuple
            self._playback_times.append(current_time)
            return frame_tuple

        # If no frame is ready, return None
        return None

    def _adjust_buffer_size(self):
        """Dynamically adjusts the buffer size based on observed network jitter."""
        if len(self._arrival_times) < 5:
            return

        # Calculate arrival intervals
        intervals = [self._arrival_times[i] - self._arrival_times[i-1] for i in range(1, len(self._arrival_times))]
        
        # Calculate jitter (average absolute difference between consecutive intervals)
        jitter = sum(abs(intervals[i] - intervals[i-1]) for i in range(1, len(intervals))) / (len(intervals) - 1) if len(intervals) > 1 else 0
        
        # Target buffer size should be able to absorb observed jitter
        # A common heuristic is 3-4 times the jitter
        target_buffer_ms = max(50, int(jitter * 4 * 1000))
        target_buffer_ms = min(target_buffer_ms, 400) # Cap at 400ms to avoid too much latency
        
        new_max_frames = self._calculate_max_frames(target_buffer_ms)
        
        # Smoothing: only adjust if change is significant or persistent
        if new_max_frames != self._max_frames:
            self._debug.info("JitterBuffer", f"Adaptive Resize: max_frames {self._max_frames} -> {new_max_frames} (jitter: {jitter*1000:.2f}ms)")
            self._max_frames = new_max_frames
            self._current_buffer_size_ms = target_buffer_ms

    def is_ready(self) -> bool:
        """
        Checks if the buffer has enough frames to start playback.
        """
        return len(self._frames) >= self._max_frames // 2 # Ready when at least half full

    def clear(self):
        """
        Clears all frames from the buffer.
        """
        self._frames.clear()
        self._last_playback_time = 0.0
        self._last_played_frame_data = None
        self._arrival_times.clear()
        self._playback_times.clear()
        self._debug.info("JitterBuffer", "Buffer cleared.")