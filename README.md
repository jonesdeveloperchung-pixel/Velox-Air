# 🟢 Velox Air - The Companion (v1.0)

**"Reclaiming legacy hardware through eco-friendly performance."**

Velox Air is the passive, web-based tier of the Velox Studio portfolio. It turns old tablets and phones into auxiliary information displays without requiring any app installation.

## ✨ Key Features
*   **Zero-Install**: Connect via any modern browser (Chrome, Safari, Edge).
*   **Eco-Mode (20 FPS)**: Hard-capped frame rate to prevent battery drain and overheating on older devices.
*   **App-Like Experience**: Support for "Add to Home Screen" (PWA) to run fullscreen without browser UI.
*   **Resilient Connectivity**:
    *   Auto-reconnects on Wi-Fi drops.
    *   Works even with "Strict" Browser Privacy/Tracking Prevention enabled.
    *   Automatic Port Seeker (8765 -> 8766 -> 8767) if the default port is busy.

## 🚀 Quick Start (Standalone)
1.  Run **`VeloxAir_Server.exe`** on your Windows PC.
2.  Ensure your PC and Tablet are on the **same Wi-Fi network**.
3.  On your Tablet:
    *   Scan the **QR Code** displayed on the Server Dashboard.
    *   Or open the URL shown in the console (e.g., `http://192.168.1.X:8080`).

## 📱 Client Guide
### Fullscreen Mode
*   **Android (Chrome):** Tap menu (⋮) -> "Add to Home Screen". Open the new icon for a full app experience.
*   **iOS (Safari):** Tap Share button -> "Add to Home Screen".
*   **Manual:** Tap the "Fullscreen" button in the top navigation bar.

### Controls
*   **? (Help):** View operational rules and tips.
*   **Scaling:** Toggle between Contain (Fit), Cover (Fill), and Stretch.
*   **Control Toggle:** Enable/Disable touch input (Mouse simulation).

## 🛠️ Advanced Maintenance
### Troubleshooting
*   **"Waiting for Signal...":** The server is running but hasn't captured a frame yet. This usually resolves in <1 second. If stuck, refresh the page.
*   **Black Screen:** If using an ultra-old device, ensure it supports WebP images.
*   **Port Error:** The server will automatically try the next available port if 8765 is taken. Check the console window for the active address.

### Architecture
*   **Backend:** Pure Python (MSS Fallback) or Native Rust (Velox Core) if available.
*   **Frontend:** Vanilla JS + Canvas 2D (No heavy frameworks).
*   **Protocol:** WebSocket (Binary Protocol v1.0).

---
*Built for PixelMirror Studio | 2026*