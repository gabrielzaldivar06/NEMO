$ProjectRoot = $PSScriptRoot
$WorkspaceRoot = Split-Path $ProjectRoot -Parent
$VenvPython = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "No se encontro el Python del venv en $VenvPython" -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando NEMO daemon en background..." -ForegroundColor Green
Write-Host "Mantendra mantenimiento, reflexiones y aprendizaje incremental." -ForegroundColor Cyan

Start-Process -FilePath $VenvPython `
    -ArgumentList "nemo_daemon.py" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Minimized

Write-Host "NEMO daemon lanzado." -ForegroundColor Green