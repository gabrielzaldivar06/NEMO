@echo off
setlocal

set "MODEL_PATH=%USERPROFILE%\.lmstudio\models\miloK1\Qwen3-Embedding-4B-Q8_0-GGUF\qwen3-embedding-4b-q8_0.gguf"
set "LMS_PATH=%LOCALAPPDATA%\Programs\LM Studio\resources\app\.webpack\lms.exe"
set "MODEL_KEY=text-embedding-qwen3-embedding-4b"
set "MODEL_IDENTIFIER=qwen3-embed-4b"
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

if not "%LLAMA_SERVER_PATH%"=="" (
    if not exist "%MODEL_PATH%" (
        echo No se encontro el modelo en:
        echo %MODEL_PATH%
        exit /b 1
    )

    echo Iniciando llama.cpp embeddings server con:
    echo %MODEL_PATH%
    "%LLAMA_SERVER_PATH%" -m "%MODEL_PATH%" --embeddings -c 2048 --port 1234
    exit /b %ERRORLEVEL%
)

if not exist "%LMS_PATH%" (
    echo No se encontro llama-server en PATH ni lms.exe en:
    echo %LMS_PATH%
    exit /b 1
)

echo llama-server no esta en PATH. Usando LM Studio CLI...
"%LMS_PATH%" server start --port 1234
if errorlevel 1 exit /b %ERRORLEVEL%

"%LMS_PATH%" ps | findstr /C:"%MODEL_IDENTIFIER%" >nul
if errorlevel 1 (
    "%LMS_PATH%" load %MODEL_KEY% --identifier %MODEL_IDENTIFIER% -y
    if errorlevel 1 exit /b %ERRORLEVEL%
) else (
    echo El modelo %MODEL_IDENTIFIER% ya esta cargado en LM Studio.
)

echo Servidor listo en http://localhost:1234 con modelo %MODEL_IDENTIFIER%