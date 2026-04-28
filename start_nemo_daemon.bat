@echo off
set PROJECT_ROOT=%~dp0
for %%I in ("%PROJECT_ROOT%..") do set WORKSPACE_ROOT=%%~fI
set PYTHON_EXE=%WORKSPACE_ROOT%\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
  echo No se encontro el Python del venv en "%PYTHON_EXE%"
  exit /b 1
)

echo Iniciando NEMO daemon en background...
start "NEMO Daemon" /min "%PYTHON_EXE%" "%PROJECT_ROOT%nemo_daemon.py"