@echo off
REM ── NEMO Installer Build Script ───────────────────────────────────────────
REM Compiles nemo_installer.py into a single portable .exe (Windows x64)
REM
REM  Prerequisites:
REM    pip install pyinstaller
REM  Optional (for the taskbar icon):
REM    Place nemo.ico in this folder before building.
REM ─────────────────────────────────────────────────────────────────────────

setlocal EnableDelayedExpansion

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   NEMO Installer — Build Script      ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── Check PyInstaller ────────────────────────────────────────────────────
python -m pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] PyInstaller no encontrado. Instalando...
    pip install pyinstaller --quiet
    if %errorlevel% neq 0 (
        echo [!] Error instalando PyInstaller. Aborting.
        pause
        exit /b 1
    )
)

REM ── Generate nemo.ico from embedded generator ─────────────────────────────
echo [*] Generando icono nemo.ico...
python -c "
import base64, sys
from pathlib import Path
# Extract ICO bytes directly from gen_icon.py output approach
exec(open('gen_icon.py').read().replace('print(', 'data=(').replace('decode())', 'decode()); Path(\"nemo.ico\").write_bytes(base64.b64decode(data))'))
" 2>nul
if not exist nemo.ico (
    echo [!] No se pudo generar nemo.ico ^(opcional^). Continuando sin icono personalizado.
) else (
    echo [OK] nemo.ico generado.
)
echo.

REM ── Clean previous build ─────────────────────────────────────────────────
if exist dist\  rd /s /q dist
if exist build\ rd /s /q build
if exist "NEMO Installer.spec" del /f "NEMO Installer.spec"

REM ── Build ─────────────────────────────────────────────────────────────────
echo [*] Compilando...
echo.

REM Add --icon nemo.ico if the file exists
set ICON_FLAG=
if exist nemo.ico set ICON_FLAG=--icon nemo.ico

python -m pyinstaller ^
  --onefile ^
  --windowed ^
  --name "NEMO Installer" ^
  --hidden-import winreg ^
  --hidden-import tkinter ^
  --hidden-import tkinter.ttk ^
  --hidden-import tkinter.filedialog ^
  --hidden-import tkinter.messagebox ^
  --hidden-import tkinter.scrolledtext ^
  %ICON_FLAG% ^
  nemo_installer.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Compilacion fallida. Revisa el error anterior.
    pause
    exit /b 1
)

echo.
echo  ─────────────────────────────────────────────────────
echo  [OK] Instalador creado: dist\NEMO Installer.exe
echo  Tamaño aproximado: 10-20 MB
echo  ─────────────────────────────────────────────────────
echo.
echo  Para probar antes de distribuir:
echo    dist\NEMO Installer.exe
echo.

REM ── Optional: copy to project root ────────────────────────────────────────
copy /y "dist\NEMO Installer.exe" "..\NEMO Installer.exe" >nul
echo  Copiado a: ..\NEMO Installer.exe
echo.

pause
