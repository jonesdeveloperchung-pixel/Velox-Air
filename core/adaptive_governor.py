import time

class AdaptiveGovernor:
    """
    Adaptive Governor for Velox-Warp Streaming.
    
    Adjusts stream parameters (WebP Quality, Tile Size) based on client feedback
    to maintain target performance characteristics.
    """
    
    MODES = {
        "GAMING": {"fps": 60, "min_q": 30, "max_q": 80, "target_q": 65},
        "BALANCED": {"fps": 45, "min_q": 20, "max_q": 90, "target_q": 75},
        "STUDIO": {"fps": 30, "min_q": 50, "max_q": 100, "target_q": 95}
    }

    def __init__(self, debug, mode="BALANCED", tier="WARP"):
        self.debug = debug
        self.mode = mode if mode in self.MODES else "BALANCED"
        self.tier = tier.upper()
        
        cfg = self.MODES[self.mode]
        
        # AIR Tier Enforcement: Always cap at 20 FPS for battery saving
        self.target_fps = 20 if self.tier == "AIR" else cfg["fps"]
        self.target_frame_time = 1000 / self.target_fps
        
        self.current_quality = float(cfg["target_q"])
        self.min_quality = cfg["min_q"]
        self.max_quality = cfg["max_q"]
        
        self.current_tile_size = 128
        
        # Horizon for smoothing updates
        self.horizon = 10 
        self.last_update_time = time.time()
        
        # Stabilization State
        self.last_applied_quality = self.current_quality
        self.quality_deadband = 5.0 # Minimum change required to trigger update
        
        # AIR Tier Extras
        self.last_mode = "NORMAL"
        self.last_battery = 100
        self.last_is_charging = True
        self.last_fps = 0
        
        # Foveated Tracking
        self._cursor_pos = (0, 0)
        self._foveated_radius = 200 # 400x400 box base
        self._min_foveated_radius = 80
        self._max_foveated_radius = 400

    def update_cursor(self, x: int, y: int):
        self._cursor_pos = (x, y)

    def get_foveated_radius(self) -> int:
        return self._foveated_radius

    def is_in_foveated_region(self, tx: int, ty: int, tw: int, th: int) -> bool:
        cx, cy = self._cursor_pos
        # Check if tile overlaps with the foveated box
        return not (tx + tw < cx - self._foveated_radius or \
                   tx > cx + self._foveated_radius or \
                   ty + th < cy - self._foveated_radius or \
                   ty > cy + self._foveated_radius)

    def update(self, client_stats: dict):
        """
        Updates the governor state based on client stats.
        
        Args:
            client_stats: dict containing 'fps', 'avg_decode_ms', 'pending_tiles', 'mode'
        """
        now = time.time()
        # Rate limit updates to avoid oscillation
        if now - self.last_update_time < 0.5:
            return

        fps = client_stats.get('fps', 60)
        decode_ms = client_stats.get('avg_decode_ms', 0)
        pending = client_stats.get('pending_tiles', 0)
        mode = client_stats.get('mode', 'NORMAL')
        self.last_mode = mode
        self.last_battery = client_stats.get('battery', 100)
        self.last_is_charging = client_stats.get('is_charging', True)
        self.last_fps = fps
        
        # 1. Update Target FPS based on Mode
        if self.tier == "AIR":
            if mode == "SUPER_ECO":
                self.target_fps = 10
            else:
                self.target_fps = 20
        
        self.target_frame_time = 1000 / self.target_fps

        # 1. Calculate Error Metric
        # Primary signal: Pending Queue (Backpressure)
        # Secondary signal: Decode Time vs Target Frame Time
        
        # If queue is building up, we are sending too fast or too heavy
        queue_pressure = max(0, pending - 20) / 50.0 # Normalized pressure (0.0 - 1.0+)
        
        # If decode time is high, client CPU is struggling -> Reduce Quality/Resolution
        decode_pressure = max(0, decode_ms - 10) / 20.0 
        
        # New: Use real-time bandwidth to optimize Draw Call overhead
        bandwidth_kbps = client_stats.get('bandwidth_kbps', 0)
        if bandwidth_kbps > 5000:
            # If bandwidth is high, client is likely receiving many small tiles. 
            # Force a larger tile size to reduce decoding iterations.
            decode_pressure += 0.3

        # New: Direct Backpressure Signal from Client
        if client_stats.get('backpressure') == 'heavy':
            decode_pressure += 0.5 

        total_pressure = queue_pressure + decode_pressure
        
        # 2. Update Foveated Radius (Control Variable 0 - Flow specific)
        if self.tier == "FLOW":
            old_radius = self._foveated_radius
            if total_pressure > 0.3:
                self._foveated_radius = max(self._min_foveated_radius, self._foveated_radius - 40)
            elif total_pressure < 0.05:
                self._foveated_radius = min(self._max_foveated_radius, self._foveated_radius + 10)
            
            if self.debug and old_radius != self._foveated_radius:
                self.debug.debug("Governor", f"Foveated Radius adjusted: {old_radius} -> {self._foveated_radius}")

        # 3. Update Quality (Control Variable 1)
        # Multiplicative adjustment logic
        new_quality = self.current_quality
        
        if total_pressure > 0.1:
            # Drop quality significantly to recover
            drop_factor = 1.0 + min(total_pressure, 0.5) # 1.1 to 1.5x drop speed
            new_quality /= drop_factor
        else:
            # Recover slowly
            new_quality += 2.0
            
        # Clamp
        new_quality = max(self.min_quality, min(self.max_quality, new_quality))
        
        # 3. Hysteresis Check
        # Only apply if change > deadband OR we are hitting limits
        if abs(new_quality - self.last_applied_quality) > self.quality_deadband or \
           (new_quality == self.min_quality and self.last_applied_quality != self.min_quality) or \
           (new_quality == self.max_quality and self.last_applied_quality != self.max_quality):
            self.current_quality = new_quality
            self.last_applied_quality = new_quality
        else:
            # Keep current (damping)
            pass

        # 4. Update Tile Size (Control Variable 2)
        # If pressure is EXTREME, increase tile size (coarser updates = less overhead)
        # OR if decode pressure is high (too many small tiles), increase tile size.
        if decode_pressure > 0.5:
             # Increase tile size to reduce overhead per tile
             self.current_tile_size = 512 if decode_pressure > 0.8 else 256
        elif total_pressure < 0.05:
             # Relax back to fine-grained
             self.current_tile_size = 128
             
        self.last_update_time = now
        
        if self.debug and abs(self.current_quality - self.last_applied_quality) > 0.1:
             self.debug.debug("Governor", f"Stats: Q={pending}, Dec={decode_ms}ms, Mode={mode} -> New Quality: {int(self.current_quality)}, Tile: {self.current_tile_size}, FPS: {self.target_fps}")

    def get_quality(self) -> int:
        return int(self.current_quality)
    
    def get_tile_size(self) -> int:
        return self.current_tile_size

    def get_target_fps(self) -> int:
        return self.target_fps
