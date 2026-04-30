# syntax=docker/dockerfile:1.6
#
# NEMO universal server — single image, two usable profiles.
#
# Default profile (no extra services):  embedding runs in-process via fastembed.
# GPU profile (docker-compose.gpu.yml):  embedding runs in Ollama sidecar; this
#                                        image still ships fastembed as a fallback.
#
# Build:   docker build -f docker/Dockerfile -t nemo:local .
# Run:     docker compose up

ARG PYTHON_VERSION=3.11

# ── Stage 1 — build wheels & cache model weights ──────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt ./
COPY docker/requirements-docker.txt ./requirements-docker.txt

RUN pip install --prefix=/install -r requirements.txt \
    && pip install --prefix=/install -r requirements-docker.txt

# Pre-download the default multilingual embedding model into /models so the
# first container run is offline-capable and fast.
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
# Resolve site-packages deterministically from the running interpreter.
# Notes on why this is computed at runtime instead of using ${PYTHON_VERSION}:
#   - The python:slim base image sets ENV PYTHON_VERSION to the *patch-level*
#     version (e.g. 3.11.15). That ENV shadows the build ARG `PYTHON_VERSION`
#     (which only carries `3.11`), so `${PYTHON_VERSION}` here would resolve
#     to `3.11.15` and the resulting path `/install/lib/python3.11.15/...`
#     does not exist (pip uses major.minor for the directory name).
#   - Using a shell glob would also work but Copilot flagged it as fragile.
#   - Asking the interpreter directly (`%d.%d` % sys.version_info) is
#     unambiguous, escape-friendly (single quotes only), and survives any
#     future bump of the base image patch level.
RUN mkdir -p /models \
    && PY_MM="$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')" \
    && PYTHONPATH="/install/lib/python${PY_MM}/site-packages" \
       python -c "import os; from fastembed import TextEmbedding; TextEmbedding(model_name=os.environ['EMBEDDING_MODEL'], cache_dir='/models'); print('fastembed weights cached for', os.environ['EMBEDDING_MODEL'])"


# ── Stage 2 — minimal runtime ────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EMBEDDING_CACHE=/models \
    EMBEDDING_CONFIG_PATH=/app/embedding_config.json \
    NEMO_HOST=0.0.0.0 \
    NEMO_PORT=8765

# Default UID/GID 1000 matches the typical first user on Linux desktops,
# WSL, and macOS Docker Desktop, so bind-mounted volumes are writable by
# the in-container user out of the box. Override at build time with
# --build-arg NEMO_UID=$(id -u) --build-arg NEMO_GID=$(id -g) for other UIDs.
ARG NEMO_UID=1000
ARG NEMO_GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${NEMO_GID} nemo \
    && useradd  --uid ${NEMO_UID} --gid ${NEMO_GID} -d /app -s /bin/bash nemo \
    && mkdir -p /models /app /app/.ai_memory && chown -R nemo:nemo /models /app

COPY --from=builder /install /usr/local
COPY --from=builder /models /models

WORKDIR /app
COPY --chown=nemo:nemo . /app

# Install the user-facing helpers on PATH so the CLI works as `nemo-attach`.
RUN chmod +x /app/docker/entrypoint.sh /app/docker/nemo-attach \
    && cp /app/docker/nemo-attach /usr/local/bin/nemo-attach

USER nemo

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "ai_memory_mcp_server.py"]
