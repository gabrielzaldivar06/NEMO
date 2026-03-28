"""
sse_bus.py — Shared in-process SSE event bus for NEMO real-time dashboard.

Usage:
    from sse_bus import emit_event, subscribe, EventBus

    # Emit from anywhere (MCP tool hooks):
    emit_event("memory_created", {"id": "abc", "content": "...", "type": "fact", "importance": 8})

    # Consume in an async SSE endpoint:
    async for event in subscribe():
        yield f"data: {event}\n\n"
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ── Global event bus ─────────────────────────────────────────────────────────

_subscribers: list[asyncio.Queue] = []
_MAX_QUEUE = 100  # max buffered events per subscriber before dropping oldest


def emit_event(event_type: str, payload: dict) -> None:
    """
    Emit a real-time event to all active SSE subscribers.
    Safe to call from sync or async code — fires-and-forgets.
    """
    data = json.dumps({"type": event_type, **payload}, ensure_ascii=False, default=str)
    dead: list[asyncio.Queue] = []
    for q in list(_subscribers):
        try:
            if q.maxsize and q.qsize() >= q.maxsize:
                # Drop oldest to make room
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(data)
        except Exception:
            dead.append(q)
    for q in dead:
        _subscribers.remove(q)


async def subscribe() -> AsyncGenerator[str, None]:
    """
    Async generator that yields raw SSE data strings.
    Registers a new queue, yields events, cleans up on disconnect.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    _subscribers.append(q)
    logger.debug("SSE subscriber connected. Total: %d", len(_subscribers))
    try:
        while True:
            data = await q.get()
            yield data
    finally:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass
        logger.debug("SSE subscriber disconnected. Total: %d", len(_subscribers))
