@echo off
setlocal

set "MODEL_PATH=C:\Users\gabri\.lmstudio\models\gpustack\bge-reranker-v2-m3-GGUF\bge-reranker-v2-m3-Q4_K_M.gguf"
set "LLAMA_SERVER_PATH="
if not "%~1"=="" set "MODEL_PATH=%~1"

where llama-server >nul 2>nul
if not errorlevel 1 (
    set "LLAMA_SERVER_PATH=llama-server"
)

if "%LLAMA_SERVER_PATH%"=="" (
    set "WINGET_LLAMA_SERVER=%LOCALAPPDATA%\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
    if exist "%WINGET_LLAMA_SERVER%" (
        set "LLAMA_SERVER_PATH=%WINGET_LLAMA_SERVER%"
    )
)

if "%LLAMA_SERVER_PATH%"=="" (
    echo No se encontro llama-server en PATH ni en la instalacion de winget.
    exit /b 1
)

if not exist "%MODEL_PATH%" (
    echo No se encontro el modelo de reranking en:
    echo %MODEL_PATH%
    exit /b 1
)

echo Iniciando llama.cpp reranker server con:
echo %MODEL_PATH%
echo Endpoint esperado: http://localhost:8080/v1/rerank
rem --ctx-size 2048: cada par query+documento raramente supera 500 tokens
rem --parallel 2: dos slots son suficientes, libera KV cache (~11 GB sin esto en Intel Arc UMA)
"%LLAMA_SERVER_PATH%" -m "%MODEL_PATH%" --reranking --embedding --pooling rank --alias bge-reranker-v2-m3 --port 8080 --ctx-size 2048 --parallel 4