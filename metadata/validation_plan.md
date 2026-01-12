# 🟢 Velox Air - Validation Plan

## 🧪 Test Case A: Battery Endurance
*   **Device:** Tablet (e.g., Samsung Galaxy Tab A 2018).
*   **Procedure:** Stream static documentation for 2 hours.
*   **Success Metric:** Battery drain < 15% per hour; Device temp < 40°C.

## 🧪 Test Case B: Text Integrity
*   **Device:** iPad Air 1 (Legacy LCD).
*   **Procedure:** Open a PDF or documentation website.
*   **Success Metric:** No visible compression artifacts on small fonts (10pt-12pt).

## 🧪 Test Case C: Low-End Stability
*   **Device:** Android 8.0, 2GB RAM.
*   **Procedure:** Force 20 FPS stream.
*   **Success Metric:** Zero OOM (Out of Memory) crashes over 1 hour.

## 🧪 Test Case D: Resilience & Fail-Safes
*   **Scope:** Software Recovery Mechanisms.
*   **Tests:**
    1.  **Network Recovery:** Toggle Client WiFi off/on. Client should auto-reconnect within 3 seconds.
    2.  **Decoder Guard:** Simulate malformed WebP frame. Client should drop frame and continue (not freeze).
    3.  **Port Conflict:** Start Server while port 8765 is busy. Server should bind to 8766/8767 automatically.
    4.  **Initial State:** Connect new client to active stream. Client should receive Keyframe immediately (no black screen).
    5.  **Privacy Block:** Enable "Strict" tracking prevention in browser. Client should still boot (localStorage handled).
