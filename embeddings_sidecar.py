"""
OpenAI-compatible /v1/embeddings ASGI app powered by fastembed.

Mounted inside nemo_server.py at /embed, so the existing NEMO EmbeddingService
can talk to it as a standard "custom" / "lm_studio" HTTP provider with
``base_url = http://127.0.0.1:${NEMO_PORT}/embed``.

This keeps ai_memory_core.py completely untouched: from its perspective it is
just another OpenAI-compatible embedding server on localhost.

Env knobs:
  EMBEDDING_MODEL   — fastembed model id
                      (default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
  EMBEDDING_CACHE   — directory for downloaded model weights (default: /models)
"""

from __future__ import annotations

import asyncio
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
    """Lazy-loads the fastembed model on first call. One instance per process.

    Initialisation is guarded by an asyncio.Lock so that a burst of concurrent
    requests during the first hit doesn't trigger several parallel weight
    loads (which is expensive and can OOM on small machines).
    """

    _instance = None
    _lock: asyncio.Lock | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        # The lock has to be created lazily on the running loop, not at import.
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def get(cls):
        # Fast path — already loaded, no need to acquire the lock.
        if cls._instance is not None:
            return cls._instance

        async with cls._get_lock():
            # Re-check inside the lock: a previous waiter may have just loaded.
            if cls._instance is None:
                from fastembed import TextEmbedding

                logger.info("Loading fastembed model %s (cache=%s)", DEFAULT_MODEL, CACHE_DIR)
                # The fastembed constructor itself is synchronous and CPU/IO-heavy
                # (it can download weights). Run it off the event loop.
                cls._instance = await asyncio.to_thread(
                    TextEmbedding, model_name=DEFAULT_MODEL, cache_dir=CACHE_DIR
                )
                logger.info("Fastembed model loaded")
        return cls._instance


app = FastAPI(title="NEMO fastembed sidecar", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    try:
        await _FastembedSingleton.get()
        return {"status": "ok", "model": DEFAULT_MODEL}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def _embed_sync(model, texts: List[str]) -> List[List[float]]:
    """Synchronous embedding pass; called via asyncio.to_thread so it doesn't
    block the event loop while the ONNX runtime crunches numbers."""
    return [vec.tolist() for vec in model.embed(texts)]


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
        model = await _FastembedSingleton.get()
        # fastembed's .embed() is synchronous and CPU-heavy; offload it so the
        # SSE / REST handlers on this same uvicorn don't stall.
        vectors = await asyncio.to_thread(_embed_sync, model, texts)
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
