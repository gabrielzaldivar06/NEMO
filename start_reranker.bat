@echo off
title NEMO — Iniciando Reranker
echo.
echo  NEMO V1.0 ^| Cargando BGE-reranker-v2-m3 en LM Studio...
echo.
lms load text-embedding-bge-reranker-v2-m3 -y
if %ERRORLEVEL% EQU 0 (
    echo.
    echo  OK - Reranker cargado. Endpoint: http://localhost:1234/v1/rerank
) else (
    echo.
    echo  ERROR - Verifica que LM Studio este ejecutandose.
    pause
)
