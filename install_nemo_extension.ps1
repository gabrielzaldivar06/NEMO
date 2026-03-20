# NEMO V1.0 — Instalador de extensión VS Code
# Copia la extensión a ~/.vscode/extensions/ y recarga VS Code

$src  = "$PSScriptRoot\nemo-vscode"
$dest = "$env:USERPROFILE\.vscode\extensions\nemo-memory-1.0.0"

Write-Host "NEMO V1.0 — Instalando extensión VS Code..." -ForegroundColor Cyan

if (Test-Path $dest) {
    Remove-Item $dest -Recurse -Force
    Write-Host "  → Versión anterior eliminada" -ForegroundColor DarkGray
}

Copy-Item $src $dest -Recurse -Force
Write-Host "  → Copiado a: $dest" -ForegroundColor Green

Write-Host ""
Write-Host "✓ Extensión instalada." -ForegroundColor Green
Write-Host "  Recarga VS Code: Ctrl+Shift+P → 'Developer: Reload Window'" -ForegroundColor Yellow
Write-Host "  El icono NEMO aparecerá en la barra lateral izquierda." -ForegroundColor Yellow
