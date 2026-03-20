@echo off
title NEMO V1.0
cd /d "%~dp0"
start "" "c:\dev\memory persistence\.venv\Scripts\pythonw.exe" "%~dp0status_monitor.py"
