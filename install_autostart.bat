@echo off
title NEMO — Instalar Autostart
echo.
echo  NEMO V1.0 ^| Instalando inicio automatico con Windows...
echo.

set "SCRIPT=c:\dev\memory persistence\persistent-ai-memory\start_nemo_system.ps1"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP%\NEMO System.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s  = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath    = 'powershell.exe'; ^
   $s.Arguments     = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%SCRIPT%\"'; ^
   $s.WorkingDirectory = 'c:\dev\memory persistence\persistent-ai-memory'; ^
   $s.Description   = 'NEMO System Autostart'; ^
   $s.Save()"

if exist "%SHORTCUT%" (
    echo  OK - Acceso directo creado en Startup:
    echo     %SHORTCUT%
    echo.
    echo  El sistema NEMO iniciara automaticamente al iniciar sesion.
    echo  Incluye: LM Studio server + Embedding + Reranker + Monitor NEMO
) else (
    echo  ERROR - No se pudo crear el acceso directo.
    pause
)
echo.
pause
