# 🟢 Velox Air - 隨行夥伴 (v1.0)

**「透過環保效能，重賦舊硬體新生。」**

Velox Air 是 Velox Studio 產品組合中的被動式網頁層級方案。它能將舊平板和手機轉變為輔助資訊顯示器，且無需安裝任何應用程式。

## ✨ 主要特色
*   **免安裝**：透過任何現代瀏覽器（Chrome, Safari, Edge）即可連線。
*   **節能模式 (20 FPS)**：硬性限制幀率，防止舊設備電池耗盡或過熱。
*   **類 App 體驗**：支援「加入主畫面」(PWA)，可全螢幕執行並隱藏瀏覽器介面。
*   **強韌連線**：
    *   Wi-Fi 斷線時自動重連。
    *   即使在瀏覽器啟用「嚴格」隱私/追蹤防護下也能運作。
    *   自動連接埠搜尋（8765 -> 8766 -> 8767），若預設連接埠被佔用會自動切換。
*   **跨平台**：支援 Windows、Linux 與 macOS。

## 🚀 快速開始 (執行檔)
1.  從 [Releases 頁面](../../releases) 下載適用於您作業系統的最新版本。
2.  執行程式：
    *   **Windows**: `VeloxAir_Server_Windows.exe`
    *   **Linux**: `./VeloxAir_Server_Linux` (請先執行 `chmod +x` 賦予執行權限)
    *   **macOS**: `./VeloxAir_Server_macOS` (您可能需要在安全性設定中允許執行)
3.  確認您的電腦與平板位於**同一個 Wi-Fi 網路**。
4.  在平板上：
    *   掃描伺服器儀表板上顯示的 **QR Code**。
    *   或開啟控制台視窗中顯示的網址（例如：`http://192.168.1.X:8765`）。

## 🛠️ 從原始碼建置

### 事前準備
*   **Python 3.11+**
*   **Git**

### 1. 複製專案 (Clone)
```bash
git clone https://github.com/YourUsername/Velox-Air.git
cd Velox-Air
```

### 2. 安裝相依套件
```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 3. 建置執行檔
**Windows:**
執行建置腳本：
```cmd
build_air.bat
```
*或手動執行：*
```bash
pyinstaller --clean velox_air.spec
```

**Linux / macOS:**
```bash
pyinstaller --clean velox_air.spec
```

產出的執行檔將位於 `dist/` 目錄中。

### 4. 從原始碼執行 (開發模式)
如果您偏好不打包直接執行 Python 腳本：
```bash
python main.py
```

## 📱 客戶端指南
### 全螢幕模式
*   **Android (Chrome):** 點擊選單 (⋮) -> 「加到主畫面」。開啟新產生的圖示即可享受完整 App 體驗。
*   **iOS (Safari):** 點擊分享按鈕 -> 「加入主畫面」。
*   **手動:** 點擊上方導覽列的「全螢幕」按鈕。

### 控制功能
*   **? (說明):** 查看操作規則與提示。
*   **縮放:** 切換 Contain (適應)、Cover (填滿) 與 Stretch (拉伸) 模式。
*   **控制開關:** 啟用/停用觸控輸入 (模擬滑鼠)。

## 🔧 架構
*   **後端:** 純 Python (AsyncIO + Aiohttp) 搭配 MSS/DXCAM (Windows) 螢幕擷取。
*   **前端:** 原生 JS + Canvas 2D (無笨重框架)。
*   **通訊協定:** WebSocket (二進位協定 v1.0)。

---
*Built for PixelMirror Studio | 2026*
