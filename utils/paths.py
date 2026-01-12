import os
import sys

def get_resource_path(relative_path):
    """
    獲取資源的絕對路徑，支援開發環境與 PyInstaller 打包環境。
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 運行時的臨時解壓路徑
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_app_data_path():
    """
    獲取使用者數據存儲路徑 (SQLite, Logs)，支援跨平台標準。
    """
    app_name = "VeloxFlow"
    if sys.platform == "win32":
        path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), app_name)
    elif sys.platform == "darwin":
        path = os.path.join(os.path.expanduser("~"), "Library", "Application Support", app_name)
    else:
        path = os.path.join(os.path.expanduser("~"), ".local", "share", app_name)
    
    os.makedirs(path, exist_ok=True)
    return path
