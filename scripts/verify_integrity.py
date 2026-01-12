import os
import sys
import yaml
import socket
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
AIR_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = AIR_ROOT.parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

def check_path(path, description):
    if not os.path.exists(path):
        print(f"❌ MISSING {description}: {path}")
        return False
    print(f"✅ FOUND {description}: {os.path.basename(path)}")
    return True

def verify_integrity():
    print("=== Velox Air Integrity Check ===")
    
    # 1. File Structure
    checks = [
        (AIR_ROOT / "main.py", "Entry Point"),
        (AIR_ROOT / "air_server_app.py", "Server App Logic"),
        (AIR_ROOT / "web" / "index.html", "Client UI"),
        (AIR_ROOT / "web" / "js" / "air_logic.js", "Client Logic"),
        (AIR_ROOT / "web" / "manifest.json", "Web App Manifest"),
        (AIR_ROOT / "config" / "air_settings.yaml", "Configuration"),
    ]
    
    all_passed = True
    for path, desc in checks:
        if not check_path(path, desc):
            all_passed = False
            
    # 2. Config Validation
    try:
        config_path = AIR_ROOT / "config" / "air_settings.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        assert config['server']['tier'] == 'AIR'
        assert config['server']['frame_rate'] <= 30 # Eco constraint
        print(f"✅ CONFIG VALID: Tier={config['server']['tier']}, FPS={config['server']['frame_rate']}")
    except Exception as e:
        print(f"❌ CONFIG ERROR: {e}")
        all_passed = False

    # 3. Import Test (Simulate Startup)
    try:
        print("⏳ Testing Imports...", end="", flush=True)
        from product_lines.Air.air_server_app import VeloxAirServerApp
        from core.engine import StreamEngine
        print(" OK")
        print("✅ IMPORTS VALID")
    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {e}")
        all_passed = False
        
    if all_passed:
        print("\n🎉 INTEGRITY CHECK PASSED. Ready for Build.")
        sys.exit(0)
    else:
        print("\n⚠️ INTEGRITY CHECK FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    verify_integrity()
