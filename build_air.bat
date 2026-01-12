@echo off
title Velox Air - Standalone Builder
echo ========================================
echo   Velox Air Standalone Builder
echo ========================================

cd /d %~dp0

:: Check for PyInstaller
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
)

echo [*] Cleaning previous builds...
if exist build rd /s /q build
if exist dist rd /s /q dist

echo [*] Running PyInstaller...
pyinstaller --clean velox_air.spec

echo.
if %errorlevel% equ 0 (
    echo [OK] Build Successful! 
    echo [OK] Executable is located at: %~dp0dist\VeloxAir_Server.exe
) else (
    echo [!] Build Failed.
)

pause
