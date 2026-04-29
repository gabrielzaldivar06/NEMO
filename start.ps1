# NEMO start script for Windows (PowerShell) — auto-detects NVIDIA GPU.
# Usage: .\start.ps1 [-Build] [-Down]
param(
    [switch]$Build,
    [switch]$Down
)

Set-Location $PSScriptRoot

# ── Detect NVIDIA Container Toolkit ─────────────────────────────────────────
function Test-NvidiaGpu {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $false }
    $dockerInfo = docker info 2>$null
    return ($dockerInfo -match "nvidia")
}

if (Test-NvidiaGpu) {
    $ComposeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml")
    $Profile = "GPU (Ollama + NVIDIA)"
} else {
    $ComposeFiles = @()
    $Profile = "CPU (fastembed in-process)"
}

Write-Host "[NEMO] Profile detected: $Profile"

if ($Down) {
    docker compose @ComposeFiles down
    exit 0
}

$BuildArg = if ($Build) { "--build" } else { "" }
docker compose @ComposeFiles up -d $BuildArg

$port = if ($env:NEMO_HOST_PORT) { $env:NEMO_HOST_PORT } else { "8765" }
Write-Host "[NEMO] Server available at http://localhost:$port"
