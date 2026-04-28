#!/usr/bin/env bash
# Container entrypoint.
#
# Writes embedding_config.json from env vars (so ai_memory_core.py picks up the
# right provider without modification), then execs the main command.

set -euo pipefail

# Server-mode bootstrap only runs when we're starting the actual NEMO server.
# One-shot commands like `nemo-attach` skip this so output stays clean.
case "${1:-}" in
    python|python3|uvicorn|gunicorn)
        echo "[nemo] Provider=${EMBEDDING_PROVIDER:-custom}  BaseURL=${EMBEDDING_BASE_URL:-http://127.0.0.1:${NEMO_PORT:-8765}/embed}"

        if [[ -z "${EMBEDDING_BASE_URL:-}" ]]; then
            export EMBEDDING_BASE_URL="http://127.0.0.1:${NEMO_PORT:-8765}/embed"
        fi
        if [[ -z "${EMBEDDING_PROVIDER:-}" ]]; then
            export EMBEDDING_PROVIDER="custom"
        fi

        python /app/docker/generate_config.py
        mkdir -p /app/.ai_memory 2>/dev/null || true
        ;;
esac

exec "$@"
