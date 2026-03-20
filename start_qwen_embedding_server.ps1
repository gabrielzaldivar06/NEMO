$modelPath = "$env:USERPROFILE\.lmstudio\models\miloK1\Qwen3-Embedding-4B-Q8_0-GGUF\qwen3-embedding-4b-q8_0.gguf"
$lmsPath = "$env:LOCALAPPDATA\Programs\LM Studio\resources\app\.webpack\lms.exe"
$modelKey = "text-embedding-qwen3-embedding-4b"
$modelIdentifier = "qwen3-embed-4b"
$llamaServerPath = $null

if ($args.Count -gt 0 -and $args[0]) {
    $modelPath = $args[0]
}

$llamaCommand = Get-Command llama-server -ErrorAction SilentlyContinue
if ($llamaCommand) {
    $llamaServerPath = $llamaCommand.Source
} else {
    $wingetCandidate = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
    if (Test-Path $wingetCandidate) {
        $llamaServerPath = $wingetCandidate
    }
}

if ($llamaServerPath) {
    if (-not (Test-Path $modelPath)) {
        Write-Error "No se encontro el modelo en: $modelPath"
        exit 1
    }

    Write-Host "Iniciando llama.cpp embeddings server con: $modelPath"
    & $llamaServerPath -m $modelPath --embeddings -c 2048 --port 1234
    exit $LASTEXITCODE
}

if (-not (Test-Path $lmsPath)) {
    Write-Error "No se encontro llama-server en PATH ni lms.exe en: $lmsPath"
    exit 1
}

Write-Host "llama-server no esta en PATH. Usando LM Studio CLI..."
& $lmsPath server start --port 1234 | Out-Host
$loadedModels = & $lmsPath ps
if ($loadedModels -match [regex]::Escape($modelIdentifier)) {
    Write-Host "El modelo $modelIdentifier ya esta cargado en LM Studio."
} else {
    & $lmsPath load $modelKey --identifier $modelIdentifier -y | Out-Host
}
Write-Host "Servidor listo en http://localhost:1234 con modelo $modelIdentifier"