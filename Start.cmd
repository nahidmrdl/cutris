@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run Setup.cmd first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" desktop.py
if errorlevel 1 pause
