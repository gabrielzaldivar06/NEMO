@echo off
title NEMO V1.0 - System Monitor
cd /d "%~dp0"

REM Try pythonw in the local venv first (no console window)
if exist "%~dp0..\.venv\Scripts\pythonw.exe" (
    start "" "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0status_monitor.py"
) else (
    REM Fall back to system pythonw
    start "" pythonw "%~dp0status_monitor.py"
)
