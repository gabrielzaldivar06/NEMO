$modelPath = "C:\Users\gabri\.lmstudio\models\gpustack\bge-reranker-v2-m3-GGUF\bge-reranker-v2-m3-Q4_K_M.gguf"
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

if (-not $llamaServerPath) {
    Write-Error "No se encontro llama-server en PATH ni en la instalacion de winget."
    exit 1
}

if (-not (Test-Path $modelPath)) {
    Write-Error "No se encontro el modelo de reranking en: $modelPath"
    exit 1
}

Write-Host "Iniciando llama.cpp reranker server con: $modelPath"
Write-Host "Endpoint esperado: http://localhost:8080/v1/rerank"
# --ctx-size 2048: cada par query+documento raramente supera 500 tokens;
#   mantener el default 40960 x4 slots reserva ~11 GB de RAM (UMA en Intel Arc).
# --parallel 2: dos slots son suficientes para el benchmark; libera KV cache.
& $llamaServerPath -m $modelPath --reranking --embedding --pooling rank --alias bge-reranker-v2-m3 --port 8080 --ctx-size 2048 --parallel 4
