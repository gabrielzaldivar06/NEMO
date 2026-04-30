# NEMO start script for Windows (PowerShell) — picks the right compose profile.
#
# Usage:
#   .\start.ps1              # fastembed (default, no extra deps)
#   .\start.ps1 -Ollama      # Ollama CPU (better embeddings, works on any machine)
#   .\start.ps1 -Build       # rebuild image before starting
#   .\start.ps1 -Down        # stop all containers
#
# GPU auto-detection: if NVIDIA Container Toolkit is present and no explicit
# profile flag is given, the GPU profile (Ollama + NVIDIA) is activated.
param(
    [switch]$Build,
    [switch]$Down,
    [switch]$Ollama
)

Set-Location $PSScriptRoot

# ── Pick compose profile ─────────────────────────────────────────────────────
function Test-NvidiaGpu {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $false }
    $dockerInfo = docker info 2>$null
    return ($dockerInfo -match "nvidia")
}

if ($Ollama) {
    $ComposeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.ollama.yml")
    $Profile = "Ollama CPU"
} elseif (Test-NvidiaGpu) {
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

$BuildArg = if ($Build) { "--build" } else { $null }
if ($BuildArg) {
    docker compose @ComposeFiles up -d $BuildArg
} else {
    docker compose @ComposeFiles up -d
}

$port = if ($env:NEMO_HOST_PORT) { $env:NEMO_HOST_PORT } else { "8765" }
Write-Host "[NEMO] Server available at http://localhost:$port"
