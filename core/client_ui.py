import tkinter as tk
from PIL import Image, ImageTk
from io import BytesIO
import threading
import queue
import time

from .debug import Debug
from .streamable import DeltaFrame, Tile

class ClientUI:
    def __init__(self, root, initial_width: int = 800, initial_height: int = 600, debug: Debug = Debug()):
        self.root = root
        self.root.title("Velox Warp Client (Python Fallback)")
        # 設定畫布背景為黑色，避免看到全白
        self.canvas = tk.Canvas(root, width=initial_width, height=initial_height, bg='black', highlightthickness=0)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.image_item = self.canvas.create_image(0, 0, anchor=tk.NW)
        self.photo = None
        self._photo_cache = []
        self._debug = debug
        self.screen_buffer: Image.Image = Image.new("RGB", (initial_width, initial_height), color = 'black')
        
        # --- 流水線優化 ---
        self.decode_queue = queue.Queue(maxsize=5)
        self.render_queue = queue.Queue(maxsize=5)
        self.stop_threads = False
        self.decode_thread = threading.Thread(target=self._decode_worker, daemon=True)
        self.decode_thread.start()
        
        self._is_destroying = False
        self._buffer_initialized = True

        # Status bar
        self.status_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.connection_status_label = tk.Label(self.status_frame, text="Status: Disconnected", anchor=tk.W)
        self.connection_status_label.pack(side=tk.LEFT, padx=5)
        self.latency_label = tk.Label(self.status_frame, text="Latency: N/A", anchor=tk.E)
        self.latency_label.pack(side=tk.RIGHT, padx=5)

        # 定期檢查渲染隊列
        self.root.after(10, self._render_loop)

    def _decode_worker(self):
        """背景解碼執行緒：負責處理 DeltaFrame 並更新緩衝區"""
        while not self.stop_threads:
            try:
                delta_frame = self.decode_queue.get(timeout=1)
                
                # 1. 處理解析度變更 (全幀回退)
                if delta_frame.full_frame_fallback and len(delta_frame.changed_tiles) == 1:
                    tile = delta_frame.changed_tiles[0]
                    if self.screen_buffer.size != (tile.width, tile.height):
                        self._debug.info("ClientUI", f"Dynamic Resolution Change: {tile.width}x{tile.height}")
                        self.screen_buffer = Image.new("RGB", (tile.width, tile.height), color='black')
                        # 這裡不能直接修改 UI 元件，必須透過 queue 或 after，但 buffer 是我們私有的，可以直接替換

                # 2. 合併瓦片
                for tile in delta_frame.changed_tiles:
                    img = tile.image_data
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    if tile.x + tile.width <= self.screen_buffer.width and tile.y + tile.height <= self.screen_buffer.height:
                        self.screen_buffer.paste(img, (tile.x, tile.y))
                
                # 3. 提交快照到渲染隊列
                if not self.render_queue.full():
                    self.render_queue.put(self.screen_buffer.copy())
                
            except queue.Empty:
                continue
            except Exception as e:
                self._debug.error("ClientUI", f"Decode Worker Error: {e}")

    def _render_loop(self):
        if self._is_destroying: return
            
        try:
            latest_image = None
            # 獲取最新的畫面，丟棄積壓的舊畫面
            while not self.render_queue.empty():
                latest_image = self.render_queue.get_nowait()
            
            if latest_image:
                # 檢查 Canvas 大小是否需要同步
                if self.canvas.winfo_width() != latest_image.width or self.canvas.winfo_height() != latest_image.height:
                    self.canvas.config(width=latest_image.width, height=latest_image.height)

                self.photo = ImageTk.PhotoImage(latest_image)
                self.canvas.itemconfig(self.image_item, image=self.photo)
                self._photo_cache.append(self.photo)
                if len(self._photo_cache) > 2:
                    self._photo_cache.pop(0)
        except Exception as e:
            self._debug.error("ClientUI", f"Render Loop Error: {e}")
            
        self.root.after(10, self._render_loop)

    def update_frame(self, delta_frame: DeltaFrame):
        if not delta_frame.changed_tiles: return
        try:
            self.decode_queue.put_nowait(delta_frame)
        except queue.Full:
            pass # 捨棄過時幀

    def update_connection_status(self, status: str):
        if self._is_destroying: return
        try:
            self.connection_status_label.config(text=f"Status: {status}")
        except: pass

    def update_latency(self, latency_ms: float):
        if self._is_destroying: return
        try:
            self.latency_label.config(text=f"Latency: {latency_ms:.2f} ms")
        except: pass
