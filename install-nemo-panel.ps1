# install-nemo-panel.ps1
# Packages the nemo-panel VS Code extension and installs it locally.
# Requires: Node.js (node + npx) to be on PATH.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$extDir    = Join-Path $scriptDir "nemo-panel"

Write-Host "[NEMO] Packaging extension..." -ForegroundColor Cyan
Push-Location $extDir

try {
    # Use npx so @vscode/vsce doesn't need to be globally installed
    npx --yes @vscode/vsce package --no-dependencies --allow-missing-repository 2>&1 | Tee-Object -Variable vsceOut
    $vsix = Get-ChildItem -Filter "nemo-panel-*.vsix" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $vsix) {
        Write-Error "[NEMO] .vsix not found after packaging. vsce output:`n$vsceOut"
    }

    Write-Host "[NEMO] Installing $($vsix.Name) ..." -ForegroundColor Cyan
    code --install-extension $vsix.FullName --force

    Write-Host ""
    Write-Host "[NEMO] Done! Reload VS Code (Ctrl+Shift+P -> 'Developer: Reload Window')." -ForegroundColor Green
    Write-Host "       Then look for the brain icon in the Activity Bar on the left." -ForegroundColor Green
} finally {
    Pop-Location
}
