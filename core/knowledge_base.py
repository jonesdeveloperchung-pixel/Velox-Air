# core/knowledge_base.py

TROUBLESHOOTING_RULES = [
    {
        "id": "port_occupied",
        "pattern": "address already in use",
        "title": "埠位已被佔用",
        "advice": "看起來 8765 或 8080 埠位已被其他程式使用。請嘗試關閉其他 Velox Warp 視窗，或是更換埠位設定。"
    },
    {
        "id": "cert_issue",
        "pattern": "ssl.SSLCertVerificationError",
        "title": "SSL 憑證驗證失敗",
        "advice": "瀏覽器不信任自簽章憑證。請造訪 https://localhost:8765 並選擇『繼續前往』，或是安裝專案提供的根憑證。"
    },
    {
        "id": "capture_failed",
        "pattern": "mss.exception.ScreenShotError",
        "title": "螢幕擷取失敗",
        "advice": "無法擷取螢幕。請檢查是否已給予 Python 錄製螢幕的權限（MacOS 系統尤其需要）。"
    },
    {
        "id": "network_unreachable",
        "pattern": "WinError 10061",
        "title": "連線被拒絕",
        "advice": "伺服器未啟動或防火牆阻擋了連線。請確保伺服器端的 main.py 正在執行中。"
    }
]

class KnowledgeBase:
    def __init__(self):
        self.rules = TROUBLESHOOTING_RULES

    def query(self, error_msg: str):
        """Finds the best matching advice based on error string."""
        for rule in self.rules:
            if rule["pattern"].lower() in error_msg.lower():
                return {
                    "level": "Standard",
                    "title": rule["title"],
                    "content": rule["advice"]
                }
        
        # Default fallback
        return {
            "level": "Basic",
            "title": "一般性建議",
            "content": "建議檢查網路連線、防火牆設定，並確保伺服器與客戶端版本一致。若持續發生，請聯繫開發者。"
        }
