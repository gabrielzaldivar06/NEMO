# NEMO start script for Windows (PowerShell) — auto-detects NVIDIA GPU.
#
# Usage:
#   .\start.ps1          # default (fastembed in-process)
#   .\start.ps1 -Build   # rebuild image before starting
#   .\start.ps1 -Down    # stop all containers
#
# If NVIDIA Container Toolkit is detected, activates the GPU profile (Ollama + NVIDIA).
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
    $Profile = "Ollama GPU (NVIDIA)"
} else {
    $ComposeFiles = @("-f", "docker-compose.yml")
    $Profile = "fastembed (default)"
}

Write-Host "[NEMO] Profile: $Profile"

if ($Down) {
    docker compose @ComposeFiles down
    exit 0
}

if ($Build) {
    docker compose @ComposeFiles up -d --build
} else {
    docker compose @ComposeFiles up -d
}

$port = if ($env:NEMO_HOST_PORT) { $env:NEMO_HOST_PORT } else { "8765" }
Write-Host "[NEMO] Server available at http://localhost:$port"
