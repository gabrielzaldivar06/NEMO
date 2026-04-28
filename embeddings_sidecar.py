"""
OpenAI-compatible /v1/embeddings ASGI app powered by fastembed.

Mounted inside nemo_server.py at /embed, so the existing NEMO EmbeddingService
can talk to it as a standard "custom" / "lm_studio" HTTP provider with
``base_url = http://127.0.0.1:${NEMO_PORT}/embed``.

This keeps ai_memory_core.py completely untouched: from its perspective it is
just another OpenAI-compatible embedding server on localhost.

Env knobs:
  EMBEDDING_MODEL   — fastembed model id (default: multilingual-e5-small)
  EMBEDDING_CACHE   — directory for downloaded model weights (default: /models)
"""

from __future__ import annotations

import logging
import os
from typing import List, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
CACHE_DIR = os.getenv("EMBEDDING_CACHE", "/models")


class EmbeddingsRequest(BaseModel):
    input: Union[str, List[str]]
    model: str | None = None
    add_special_tokens: bool | None = None


class _FastembedSingleton:
    """Lazy-loads the fastembed model on first call. One instance per process."""

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            from fastembed import TextEmbedding

            logger.info("Loading fastembed model %s (cache=%s)", DEFAULT_MODEL, CACHE_DIR)
            cls._instance = TextEmbedding(model_name=DEFAULT_MODEL, cache_dir=CACHE_DIR)
            logger.info("Fastembed model loaded")
        return cls._instance


app = FastAPI(title="NEMO fastembed sidecar", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    try:
        _FastembedSingleton.get()
        return {"status": "ok", "model": DEFAULT_MODEL}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/v1/embeddings")
async def embeddings(req: EmbeddingsRequest):
    """OpenAI-compatible embeddings endpoint.

    Accepts a single string or a list; returns a `data[].embedding` payload
    matching OpenAI's schema so existing NEMO providers parse it as-is.
    """
    texts: List[str] = [req.input] if isinstance(req.input, str) else list(req.input)
    if not texts:
        raise HTTPException(status_code=400, detail="input must not be empty")

    try:
        model = _FastembedSingleton.get()
        vectors = [vec.tolist() for vec in model.embed(texts)]
    except Exception as exc:
        logger.exception("Embedding failure")
        raise HTTPException(status_code=500, detail=f"embedding failed: {exc}")

    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": v}
            for i, v in enumerate(vectors)
        ],
        "model": req.model or DEFAULT_MODEL,
        "usage": {"prompt_tokens": sum(len(t.split()) for t in texts), "total_tokens": 0},
    }
