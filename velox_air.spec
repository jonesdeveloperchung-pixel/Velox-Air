# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

# Calculate paths
air_root = os.path.abspath(".")
project_root = air_root # Self-contained

added_files = [
    ('web', 'web'),
    ('config', 'config'),
    ('core', 'core'),
    ('utils', 'utils'),
]

# Include the native Rust extension binary properly
binaries = []
try:
    import velox_core
    velox_core_path = os.path.dirname(velox_core.__file__)
    # Scan for .pyd files in the velox_core directory
    import glob
    pyd_files = glob.glob(os.path.join(velox_core_path, "*.pyd"))
    for f in pyd_files:
        binaries.append((f, 'velox_core'))
    print(f"✅ Found velox_core binaries: {binaries}")
except ImportError:
    print("⚠️  velox_core not found. Building in Pure Python mode (No Native Acceleration).")

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=binaries,
    datas=added_files,
    hiddenimports=['websockets.legacy.server', 'aiohttp', 'mss', 'psutil', 'pyperclip', 'PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VeloxAir_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='air_icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VeloxAir_Server',
)