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

# ── 3. Cargar modelo de embedding principal ────────────────────────────────────
Log "Cargando Qwen3-Embedding-4B..."
lms load text-embedding-qwen3-embedding-4b -y 2>&1 | ForEach-Object { Log "  lms: $_" }
Start-Sleep -Seconds 3

# ── 4. Cargar reranker ─────────────────────────────────────────────────────────
Log "Cargando BGE-reranker-v2-m3..."
lms load text-embedding-bge-reranker-v2-m3 -y 2>&1 | ForEach-Object { Log "  lms: $_" }
Start-Sleep -Seconds 2

# ── 5. Iniciar NEMO monitor (bandeja del sistema) ─────────────────────────────
Log "Iniciando NEMO monitor..."
$nemoProc = Get-Process -Name "pythonw" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*status_monitor*" }

if ($nemoProc) {
    Log "  → NEMO ya estaba corriendo (PID $($nemoProc.Id))"
} else {
    Start-Process "$VENV\pythonw.exe" -ArgumentList "`"$PROJECT\status_monitor.py`"" -WindowStyle Hidden
    Log "  → NEMO monitor iniciado"
}

Log "=== Sistema NEMO listo ==="
Log "    Embedding : http://localhost:1234/v1/embeddings"
Log "    Reranker  : http://localhost:1234/v1/rerank"
Log "    MCP NEMO  : se activa con VS Code"
