@echo off
title Velox Air - Eco Monitor Server
echo Starting Velox Air...
echo Project Root: %~dp0
cd /d %~dp0
..\..\.venv312\Scripts\python.exe main.py
pause
