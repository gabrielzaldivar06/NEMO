#!/usr/bin/env bash
# NEMO start script — auto-detects NVIDIA GPU and picks the right compose profile.
#
# Usage:
#   ./start.sh          # default (fastembed in-process)
#   ./start.sh --build  # rebuild image before starting
#   ./start.sh --down   # stop all containers
#
# If NVIDIA Container Toolkit is detected, activates the GPU profile (Ollama + NVIDIA).
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
  COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.gpu.yml)
  PROFILE="Ollama GPU (NVIDIA)"
else
  COMPOSE_FILES=(-f docker-compose.yml)
  PROFILE="fastembed (default)"
fi

echo "[NEMO] Profile: $PROFILE"

if [[ -n "$DOWN_FLAG" ]]; then
  docker compose "${COMPOSE_FILES[@]}" down
  exit 0
fi

docker compose "${COMPOSE_FILES[@]}" up -d $BUILD_FLAG

echo "[NEMO] Server available at http://localhost:${NEMO_HOST_PORT:-8765}"
