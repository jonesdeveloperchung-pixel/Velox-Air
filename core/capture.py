import time
import os
import platform
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Tuple, Any
from PIL import Image, ImageDraw
import asyncio
import functools
import pyautogui

import mss
import numpy as np

from .streamable import Streamable, ScreenFrame
from .debug import Debug
from .performance_metrics import stat_capture

class BaseCapture(ABC):
    """Abstract Base Class for all Capture Backends."""
    def __init__(self, monitor_id: int, frame_rate: int, resolution: str, debug: Debug, loop: asyncio.AbstractEventLoop, optimize_pipeline: bool = True):
        self._monitor_id = monitor_id
        self._frame_rate = frame_rate
        self._resolution = resolution
        self._debug = debug
        self._loop = loop
        self._optimize_pipeline = optimize_pipeline
        self.draw_cursor = True
        
        self.actual_width = 0
        self.actual_height = 0
        self._target_width = None
        self._target_height = None

        # Metrics
        self._fps = 0.0
        self._frame_count = 0
        self._last_fps_update = time.time()

    @abstractmethod
    async def capture_gen(self) -> AsyncIterator[Streamable]:
        pass

    def set_frame_rate(self, frame_rate: int):
        """Update the target frame rate dynamically."""
        self._frame_rate = max(1, min(120, frame_rate))
        self._debug.debug("Capture", f"Target frame rate updated to {self._frame_rate}")

    def stop(self):
        """Explicitly release backend resources."""
        pass

    def _resolve_resolution(self):
        if self._resolution == "full":
            self._target_width = self.actual_width
            self._target_height = self.actual_height
        else:
            try:
                w, h = map(int, self._resolution.split('x'))
                self._target_width, self._target_height = w, h
            except ValueError:
                self._target_width, self._target_height = self.actual_width, self.actual_height

    def _draw_cursor(self, frame: Any, monitor_bounds: dict):
        """Standardized cursor overlay supporting both PIL Image and NumPy array."""
        if not self.draw_cursor:
            return
        try:
            cursor_x, cursor_y = pyautogui.position()
            # Check if cursor is within current monitor bounds
            if (monitor_bounds['left'] <= cursor_x < monitor_bounds['left'] + monitor_bounds['width'] and 
                monitor_bounds['top'] <= cursor_y < monitor_bounds['top'] + monitor_bounds['height']):    

                rel_x = cursor_x - monitor_bounds['left']
                rel_y = cursor_y - monitor_bounds['top']

                # Scale cursor position if resolution is different from actual
                if self._target_width and self.actual_width:
                    scale_x = self._target_width / self.actual_width
                    scale_y = self._target_height / self.actual_height
                    rel_x = int(rel_x * scale_x)
                    rel_y = int(rel_y * scale_y)

                if isinstance(frame, Image.Image):
                    # PIL drawing logic (High quality)
                    draw = ImageDraw.Draw(frame)
                    # Simple arrow shape
                    arrow = [(rel_x, rel_y), (rel_x, rel_y + 15), (rel_x + 4, rel_y + 11), (rel_x + 10, rel_y + 10)]
                    draw.polygon(arrow, fill="white", outline="black")
                elif isinstance(frame, np.ndarray):
                    # NumPy drawing logic (Zero-copy optimization)
                    # Draw a simple 10x10 cursor block with black border
                    h, w = frame.shape[:2]
                    size = 10
                    # Boundary checks
                    y_start, y_end = max(0, rel_y), min(h, rel_y + size)
                    x_start, x_end = max(0, rel_x), min(w, rel_x + size)

                    if y_end > y_start and x_end > x_start:
                        # Draw white square
                        frame[y_start:y_end, x_start:x_end] = [255, 255, 255]
                        # Draw black border (1px)
                        frame[y_start:y_start+1, x_start:x_end] = [0, 0, 0]
                        frame[y_end-1:y_end, x_start:x_end] = [0, 0, 0]
                        frame[y_start:y_end, x_start:x_start+1] = [0, 0, 0]
                        frame[y_start:y_end, x_end-1:x_end] = [0, 0, 0]
        except Exception: pass

class MSSCapture(BaseCapture):
    """Cross-platform fallback capture using mss."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "MSS (CPU)"
        with mss.mss() as sct:
            mon = sct.monitors[self._monitor_id]
            self.actual_width, self.actual_height = mon['width'], mon['height']
        self._resolve_resolution()
        self._debug.info("MSSCapture", f"Initialized: {self.actual_width}x{self.actual_height} @ {self._frame_rate}fps")

    @stat_capture
    def _grab_frame(self):
        with mss.mss() as sct:
            mon = sct.monitors[self._monitor_id]
            sct_img = sct.grab(mon)
            pil_img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            self._draw_cursor(pil_img, mon)
            if self._target_width != self.actual_width:
                pil_img = pil_img.resize((self._target_width, self._target_height), Image.BILINEAR)       
            return pil_img

    async def capture_gen(self) -> AsyncIterator[Streamable]:
        last_time = 0
        processing_lock = asyncio.Lock()

        while True:
            wait = (1 / self._frame_rate) - (time.time() - last_time)
            if wait > 0: await asyncio.sleep(wait)

            if processing_lock.locked():
                continue

            async with processing_lock:
                frame = await self._loop.run_in_executor(None, self._grab_frame)
                last_time = time.time()

                # Update metrics
                self._frame_count += 1
                if time.time() - self._last_fps_update >= 1.0:
                    self._fps = self._frame_count / (time.time() - self._last_fps_update)
                    self._frame_count = 0
                    self._last_fps_update = time.time()

                yield ScreenFrame(frame)

class DXCAMCapture(BaseCapture):
    """High-performance Windows capture using GPU."""
    def __init__(self, dxcam_device_idx: int, dxcam_output_idx: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "DXCAM (GPU)"
        import dxcam
        self.camera = dxcam.create(device_idx=dxcam_device_idx, output_idx=dxcam_output_idx, output_color="RGB")
        self.actual_width, self.actual_height = self.camera.width, self.camera.height

        with mss.mss() as sct:
            self.monitor_bounds = sct.monitors[self._monitor_id]

        self._resolve_resolution()
        self._debug.info("DXCAMCapture", f"Initialized GPU capture: {self.actual_width}x{self.actual_height}")

    async def capture_gen(self) -> AsyncIterator[Streamable]:
        self.camera.start(target_fps=self._frame_rate)
        processing_lock = asyncio.Lock()
        try:
            while True:
                if processing_lock.locked():
                    await asyncio.sleep(0.01)
                    continue

                async with processing_lock:
                    frame_np = self.camera.get_latest_frame()
                    if frame_np is not None:
                        self._frame_count += 1
                        if time.time() - self._last_fps_update >= 1.0:
                            self._fps = self._frame_count / (time.time() - self._last_fps_update)
                            self._frame_count = 0
                            self._last_fps_update = time.time()

                        if self._target_width != self.actual_width:
                             pil_img = Image.fromarray(frame_np)
                             self._draw_cursor(pil_img, self.monitor_bounds)
                             pil_img = pil_img.resize((self._target_width, self._target_height), Image.BILINEAR)
                             yield ScreenFrame(pil_img)
                        else:
                             self._draw_cursor(frame_np, self.monitor_bounds)
                             yield ScreenFrame(frame_np)

                await asyncio.sleep(1 / self._frame_rate)
        finally:
            if hasattr(self.camera, 'stop'):
                try: self.camera.stop()
                except: pass

class VeloxRustCapture(BaseCapture):
    """High-performance Cross-Platform capture using Rust."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "VeloxRust (Native)"
        import velox_core

        rust_idx = self._monitor_id
        self.capturer = velox_core.VeloxCapturer(rust_idx)
        self.actual_width = self.capturer.width
        self.actual_height = self.capturer.height

        self.hw_width = 1920
        self.hw_height = 1080
        self.aligned_width = 1920
        self.aligned_height = 1088

        try:
            with mss.mss() as sct:
                self.monitor_bounds = sct.monitors[self._monitor_id]
        except:
            self.monitor_bounds = {'left': 0, 'top': 0, 'width': self.actual_width, 'height': self.actual_height}

        self._resolve_resolution()
        self._debug.info(self.name, f"Initialized Rust Capture: {self.actual_width}x{self.actual_height}")

    def capture_h264_payload(self, quality: float = 95.0) -> bytes:
        if hasattr(self.capturer, "capture_h264_payload"):
            return self.capturer.capture_h264_payload(quality)
        return self.capturer.capture_h265_payload(quality)

    def capture_h265_payload(self, quality: float = 95.0) -> bytes:
        return self.capturer.capture_h265_payload(quality)

    def stop(self):
        if hasattr(self, 'capturer'):
            self._debug.info(self.name, "Explicitly dropping Rust capturer...")
            del self.capturer

    async def capture_gen(self) -> AsyncIterator[Streamable]:
        processing_lock = asyncio.Lock()

        while True:
            if processing_lock.locked():
                 await asyncio.sleep(0.001)
                 continue

            async with processing_lock:
                try:
                    raw_bytes = await self._loop.run_in_executor(None, self.capturer.capture_frame_bytes) 
                    
                    frame_np = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((self.actual_height, self.actual_width, 4))
                    
                    # Detect format: Explicit 'BGRA' or implicit Windows DXGI (which is always BGRA)
                    is_bgra = False
                    if hasattr(self.capturer, "get_format"):
                        if self.capturer.get_format() == "BGRA": is_bgra = True
                    elif platform.system() == "Windows":
                        is_bgra = True

                    if is_bgra:
                        rgb_frame = frame_np[:, :, [2, 1, 0]]
                    else:
                        rgb_frame = frame_np[:, :, :3]

                    self._draw_cursor(rgb_frame, self.monitor_bounds)

                    self._frame_count += 1
                    if time.time() - self._last_fps_update >= 1.0:
                        self._fps = self._frame_count / (time.time() - self._last_fps_update)
                        self._frame_count = 0
                        self._last_fps_update = time.time()

                    if self._target_width != self.actual_width:
                        pil_img = Image.fromarray(rgb_frame)
                        pil_img = pil_img.resize((self._target_width, self._target_height), Image.BILINEAR)
                        yield ScreenFrame(pil_img)
                    else:
                        yield ScreenFrame(rgb_frame)

                except Exception as e:
                    msg = str(e)
                    if "Access is denied" in msg or "0x80070005" in msg:
                        self._debug.warning(self.name, "Workstation locked or UAC active. Waiting for access...")
                        await asyncio.sleep(2.0)
                        continue
                    
                    self._debug.error(self.name, f"Capture error: {e}")
                    await asyncio.sleep(1)

                await asyncio.sleep(1 / self._frame_rate)

class CaptureFactory:
    """Factory to create the best capture instance for the environment."""
    @staticmethod
    def create(monitor_id: int = 0, frame_rate: int = 30, resolution: str = "full", debug: Debug = Debug(), loop: asyncio.AbstractEventLoop = None, optimize_pipeline: bool = True, enable_dxcam: bool = False) -> BaseCapture:
        system = platform.system()
        loop = loop or asyncio.get_event_loop()

        try:
            import velox_core
            return VeloxRustCapture(monitor_id, frame_rate, resolution, debug, loop, optimize_pipeline)   
        except:
            debug.warning("CaptureFactory", "Native core failed. Falling back to MSS.")

        final_mss_idx = monitor_id + 1
        return MSSCapture(final_mss_idx, frame_rate, resolution, debug, loop, optimize_pipeline)

# Compatibility Alias
ScreenCapture = CaptureFactory.create
