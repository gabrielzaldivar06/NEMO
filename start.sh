#!/usr/bin/env bash
# NEMO start script — auto-detects NVIDIA GPU and picks the right compose profile.
# Usage: ./start.sh [--build] [--down]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_FLAG=""
DOWN_FLAG=""
for arg in "$@"; do
  case "$arg" in
    --build) BUILD_FLAG="--build" ;;
    --down)  DOWN_FLAG="true" ;;
  esac
done

# ── Detect NVIDIA Container Toolkit ─────────────────────────────────────────
has_nvidia_gpu() {
  command -v nvidia-smi &>/dev/null || return 1
  docker info 2>/dev/null | grep -qi "nvidia" || return 1
  return 0
}

if has_nvidia_gpu; then
  COMPOSE_CMD=(docker compose -f docker-compose.yml -f docker-compose.gpu.yml)
  PROFILE="GPU (Ollama + NVIDIA)"
else
  COMPOSE_CMD=(docker compose)
  PROFILE="CPU (fastembed in-process)"
fi

echo "[NEMO] Profile detected: $PROFILE"

if [[ -n "$DOWN_FLAG" ]]; then
  "${COMPOSE_CMD[@]}" down
  exit 0
fi

"${COMPOSE_CMD[@]}" up -d $BUILD_FLAG

echo "[NEMO] Server available at http://localhost:${NEMO_HOST_PORT:-8765}"
