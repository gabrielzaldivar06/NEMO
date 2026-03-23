# NEMO System Autostart
# Inicia LM Studio server + modelos de embedding/reranker + monitor NEMO
# Se ejecuta al iniciar sesión en Windows vía la carpeta Startup

$PROJECT = "C:\dev\memory persistence\persistent-ai-memory"
$VENV    = "C:\dev\memory persistence\.venv\Scripts"
$LOG     = "$PROJECT\logs\autostart.log"

# Crear carpeta de logs si no existe
New-Item -ItemType Directory -Force -Path "$PROJECT\logs" | Out-Null

function Log($msg) {
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$ts  $msg" | Tee-Object -FilePath $LOG -Append | Out-Null
    Write-Host "$ts  $msg"
}

Log "=== NEMO System Autostart ==="

# ── 1. Esperar un poco para que el escritorio cargue completamente ─────────────
Start-Sleep -Seconds 8

# ── 2. Arrancar LM Studio server (si no está corriendo) ───────────────────────
Log "Iniciando LM Studio server..."
$serverStatus = lms server status 2>&1
if ($serverStatus -match "running|activo|started") {
    Log "  → LM Studio ya estaba activo"
} else {
    lms server start --port 1234 2>&1 | ForEach-Object { Log "  lms: $_" }
    Start-Sleep -Seconds 5
    Log "  → LM Studio server iniciado"
}

# ── 3. Cargar modelo de embedding principal (solo si no está ya cargado) ────────
$loadedModels = lms ps 2>&1 | Out-String

if ($loadedModels -notmatch "text-embedding-qwen3-embedding-4b") {
    Log "Cargando Qwen3-Embedding-4B..."
    lms load text-embedding-qwen3-embedding-4b -y 2>&1 | ForEach-Object { Log "  lms: $_" }
    Start-Sleep -Seconds 3
    Log "  → Qwen3 embedding cargado"
} else {
    Log "  → Qwen3-Embedding-4B ya estaba cargado, omitiendo"
}

# ── 4. Reranker: arrancar llama-server en :8080 (LM Studio NO implementa /v1/rerank) ──
$rerankerAlive = $false
try {
    $resp = [System.Net.WebRequest]::Create("http://localhost:8080/health")
    $resp.Timeout = 2000
    $resp.GetResponse().Close()
    $rerankerAlive = $true
} catch {}

if ($rerankerAlive) {
    Log "  → Reranker llama-server ya estaba corriendo en :8080"
} else {
    Log "Iniciando BGE-reranker-v2-m3 via llama-server en :8080..."
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c `"$PROJECT\start_qwen_reranker_server.bat`"" `
        -WindowStyle Minimized
    Start-Sleep -Seconds 6
    Log "  → Reranker iniciado (endpoint: http://localhost:8080/v1/rerank)"
}

# ── 5. MCP Server arranca automáticamente por VS Code (stdio) ─────────────────
Log "=== Sistema NEMO listo ==="
Log "    Embedding : http://localhost:1234/v1/embeddings  (LM Studio)"
Log "    Reranker  : http://localhost:8080/v1/rerank      (llama-server)"
Log "    MCP NEMO  : stdio — se activa automáticamente con VS Code/Copilot"
