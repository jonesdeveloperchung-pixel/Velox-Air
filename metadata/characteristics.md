# 🟢 Velox Air - Technical Profile

## 🎯 Positioning: "The Eco-Monitor"
*   **Target Device:** Legacy tablets (5-8+ years old) & Mobile Phones.
*   **Core Purpose:** Passive information display (Documentation, Spotify, Logs).
*   **Release Status:** **v1.0 (Stable)** - Standalone Executable.

## ✨ Implemented Characteristics
### 1. UX Experience: "Passive & Invisible"
*   **Access:** Zero-Install Web Client (PWA Capable).
*   **Visuals:** Optimized for Text Clarity (WebP Q85).
*   **Mode:** **Eco-Locked (20 FPS)**.
*   **Input:** Optional Touch-to-Mouse (can be disabled).

### 2. Resilience Strategy (The Fail-Safes)
*   **Browser Hardening:**
    *   **Storage:** Try-Catch blocks around `localStorage` to support "Strict" privacy browsers.
    *   **Decoding:** Watchdog timer (2000ms) prevents corrupted frames from freezing the stream.
*   **Network:**
    *   **Port Seeker:** Server auto-binds to `8766`, `8767` if `8765` is busy.
    *   **Keyframe Injection:** Forces full-frame capture immediately on client join.

### 3. Technical Constraints
*   **Resolution:** Mirrors host (scaled down on client via Canvas).
*   **Latency:** Non-critical (~50-100ms acceptable).
*   **Audio:** Disabled by default in Air tier to save bandwidth.

## 📦 Distribution
*   **Format:** Single File Executable (`VeloxAir_Server.exe`).
*   **Size:** ~15-20MB (Pure Python Mode).
*   **Dependencies:** None (Bundled).