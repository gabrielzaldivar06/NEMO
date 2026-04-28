"""
Generate embedding_config.json at container startup from env vars.

This lets a single Docker image serve two very different embedding setups
(the default in-process fastembed sidecar, or an external Ollama service)
without touching ai_memory_core.py. The existing EmbeddingService picks up
whatever is written here.

Env vars consumed:
  EMBEDDING_PROVIDER    custom | ollama | lm_studio | openai       (default: custom)
  EMBEDDING_MODEL       model identifier understood by the provider
  EMBEDDING_BASE_URL    e.g. http://127.0.0.1:8765/embed or http://ollama:11434
  EMBEDDING_API_KEY     only used when provider=openai
  RERANK_ENABLED        true/false                                 (default: false)
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_config() -> dict:
    provider = os.getenv("EMBEDDING_PROVIDER", "custom").strip()
    model = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    base_url = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:8765/embed").rstrip("/")
    api_key = os.getenv("EMBEDDING_API_KEY", "")
    rerank_enabled = _bool(os.getenv("RERANK_ENABLED"), default=False)

    primary = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "description": f"Auto-configured at container startup (provider={provider})",
    }
    if api_key:
        primary["api_key"] = api_key

    # Keep a sane disabled fallback so the circuit-breaker has something to read.
    fallback = {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "description": "Same as primary (fallback disabled in Docker)",
    }

    return {
        "embedding_configuration": {
            "primary": primary,
            "fallback": fallback,
            "options": {},
        },
        "reranking_configuration": {
            "primary": {
                "enabled": rerank_enabled,
                "provider": "custom",
                "model": os.getenv("RERANK_MODEL", ""),
                "base_url": os.getenv("RERANK_BASE_URL", ""),
                "rerank_path": "/v1/rerank",
                "candidate_count": 15,
                "final_top_n": 5,
                "timeout_seconds": 20,
                "description": "Reranking is disabled by default in Docker. Enable via RERANK_ENABLED=true.",
            },
            "fallback": {"enabled": False},
        },
        "instructions": {
            "setup": ["Config auto-generated — edit via .env and restart the container."],
        },
    }


def main() -> None:
    target = Path(os.getenv("EMBEDDING_CONFIG_PATH", "/app/embedding_config.json"))
    config = build_config()
    target.write_text(json.dumps(config, indent=2))
    provider = config["embedding_configuration"]["primary"]["provider"]
    base_url = config["embedding_configuration"]["primary"]["base_url"]
    print(f"[nemo-docker] Wrote {target} (provider={provider}, base_url={base_url})")


if __name__ == "__main__":
    main()
