"""
NEMO universal server — single process, single port.

Serves on the same port:
  /mcp/sse            MCP over Server-Sent Events   (Claude, Cursor, Windsurf, Cline, VS Code …)
  /mcp/messages/      MCP POST sink for SSE clients
  /api/*              REST API + OpenAPI schema     (ChatGPT custom GPTs, Gemini, LangChain, curl …)
  /embed/v1/…         In-process fastembed sidecar  (only used when EMBEDDING_PROVIDER=custom)
  /health             Liveness + readiness probe

Run:
  python nemo_server.py                  # defaults to 0.0.0.0:8765
  NEMO_PORT=9000 python nemo_server.py
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from ai_memory_mcp_server import AIMemoryMCPServer
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport
from mcp.server import NotificationOptions

logger = logging.getLogger(__name__)
# Normalise to upper-case so users can pass `info`/`INFO`/`Info` interchangeably
# from .env or compose without tripping Python's case-sensitive level lookup.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


# ─── SSE transport is safe to build at module load (no async required) ──────
sse_transport = SseServerTransport("/mcp/messages/")

# ─── NEMO core is built in the lifespan handler (needs a running loop) ──────
nemo: AIMemoryMCPServer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build NEMO inside the running event loop."""
    global nemo

    logger.info("Booting NEMO core…")
    nemo = AIMemoryMCPServer()

    # Pre-heat in the background (same behaviour as the stdio entry point).
    try:
        nemo._start_preheat()
    except Exception as exc:  # non-fatal
        logger.warning("Pre-heat failed: %s", exc)

    try:
        yield
    finally:
        logger.info("Shutting NEMO down…")
        try:
            await nemo.cleanup()
        except Exception:
            logger.exception("Cleanup raised — continuing")


app = FastAPI(
    title="NEMO — Universal Memory Server",
    description=(
        "Persistent semantic memory for AI agents. Exposes an MCP-over-SSE endpoint "
        "for MCP-native clients (Claude, Cursor, VS Code, Cline…) and an OpenAPI-"
        "described REST surface for everything else (ChatGPT GPTs, Gemini, LangChain…)."
    ),
    version=os.getenv("NEMO_VERSION", "1.5.0"),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("NEMO_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── fastembed sidecar (mounted unconditionally; lazy-imports on first call) ─
try:
    from embeddings_sidecar import app as embeddings_app  # type: ignore

    app.mount("/embed", embeddings_app)
    logger.info("Mounted fastembed sidecar at /embed")
except Exception as exc:
    logger.info("fastembed sidecar unavailable (%s) — /embed disabled", exc)


# ─── Health ─────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health():
    if nemo is None:
        raise HTTPException(status_code=503, detail="NEMO not ready")
    try:
        info = await nemo.memory_system.get_system_health()
        return {"status": "ok", "nemo": info}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "error": str(exc)})


# ─── REST: generic tool dispatcher ──────────────────────────────────────────
class ToolCallBody(BaseModel):
    arguments: Dict[str, Any] = {}


@app.get("/api/tools", tags=["tools"])
async def list_tools():
    """List every NEMO tool with its input schema. Mirrors the MCP tool list."""
    if nemo is None:
        raise HTTPException(status_code=503, detail="NEMO not ready")
    tools = await nemo._get_client_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in tools
        ]
    }


@app.post("/api/tools/{tool_name}", tags=["tools"])
async def call_tool(tool_name: str, body: ToolCallBody | None = None):
    """Call any NEMO tool by name. Arguments match the tool's MCP input schema."""
    if nemo is None:
        raise HTTPException(status_code=503, detail="NEMO not ready")
    try:
        arguments = body.arguments if body else {}
        result = await nemo._execute_tool(tool_name, arguments)
        return {"ok": True, "result": _mcp_result_to_json(result)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


def _mcp_result_to_json(result: Any) -> Any:
    """Normalise a CallToolResult into plain JSON-serialisable data."""
    if hasattr(result, "content"):
        out = []
        for item in result.content:
            if hasattr(item, "text"):
                out.append(item.text)
            elif hasattr(item, "model_dump"):
                out.append(item.model_dump())
            else:
                out.append(str(item))
        return out[0] if len(out) == 1 else out
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


# ─── REST: convenience shortcuts for the most common operations ─────────────
class StoreConversationBody(BaseModel):
    content: str
    role: str = "user"
    session_id: str | None = None
    metadata: Dict[str, Any] | None = None


@app.post("/api/memory/conversation", tags=["memory"])
async def store_conversation(body: StoreConversationBody):
    return await nemo.memory_system.store_conversation(
        content=body.content,
        role=body.role,
        session_id=body.session_id,
        metadata=body.metadata,
    )


class CreateMemoryBody(BaseModel):
    content: str
    memory_type: str | None = None
    importance_level: int = 5
    tags: list[str] | None = None


@app.post("/api/memory", tags=["memory"])
async def create_memory(body: CreateMemoryBody):
    return await nemo.memory_system.create_memory(
        content=body.content,
        memory_type=body.memory_type,
        importance_level=body.importance_level,
        tags=body.tags,
    )


class SearchBody(BaseModel):
    query: str
    limit: int = 10
    min_importance: int | None = None
    tags_include: list[str] | None = None
    compact: bool = True


@app.post("/api/memory/search", tags=["memory"])
async def search_memories(body: SearchBody):
    return await nemo.memory_system.search_memories(
        query=body.query,
        limit=body.limit,
        min_importance=body.min_importance,
        tags_include=body.tags_include,
        compact=body.compact,
    )


@app.get("/api/memory/prime", tags=["memory"])
async def prime_context(topic: str | None = None):
    return await nemo.memory_system.prime_context(topic=topic)


# ─── MCP over SSE ───────────────────────────────────────────────────────────
# Why this handler accesses ``request._send``:
#
#   The MCP SDK's ``SseServerTransport.connect_sse(scope, receive, send)``
#   context manager needs the raw ASGI ``send`` callable to stream events back
#   to the client. Starlette's ``Request`` exposes ``scope`` and ``receive``
#   as public attributes but stores the ASGI ``send`` as ``_send`` (set in
#   ``Request.__init__``).  This attribute is stable across Starlette versions
#   and is the pattern documented in the official MCP Python SDK README:
#       https://github.com/modelcontextprotocol/python-sdk
#       (search “SseServerTransport” in the README — the example handler does
#        ``request.scope, request.receive, request._send``).
#
#   An earlier iteration of this server mounted the SSE handler as a raw ASGI
#   callable to avoid the underscore-prefixed attribute, but Starlette's Mount
#   semantics caused a 307 redirect on ``/mcp/sse`` → ``/mcp/sse/`` that
#   confuses several MCP clients on long-lived SSE connections. Going back to
#   ``add_route`` with ``request._send`` matches the SDK example exactly,
#   keeps the URL clean (no redirect), and is what the rest of the ecosystem
#   does.
#
# Why we do *not* propagate the User-Agent header into client detection:
#
#   ``AIMemoryMCPServer._detect_client_type()`` reads
#   ``os.environ["USER_AGENT"]`` — a process-global. Setting it per request
#   would race between overlapping SSE connections (one client could observe
#   another client's tool set). The universal HTTP server therefore exposes
#   the common tool set to every caller; client-specific extras still apply
#   in the legacy stdio entry point, where ``USER_AGENT`` is set once at
#   startup by the launching client.
@app.get("/mcp/sse", include_in_schema=False)
async def mcp_sse_endpoint(request: Request) -> Response:
    if nemo is None:
        raise HTTPException(status_code=503, detail="MCP not ready")

    init_options = InitializationOptions(
        server_name="nemo",
        server_version=os.getenv("NEMO_VERSION", "1.5.0"),
        capabilities=nemo.server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
        instructions=(
            "NEMO persistent memory active. Call prime_context before responding, "
            "search_memories before asserting project facts, create_correction the "
            "moment a user corrects you, and store_conversation at session end."
        ),
    )

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await nemo.server.run(read_stream, write_stream, init_options)
    return Response()


# POST sink for MCP SSE clients. Mounted as an ASGI sub-app because
# SseServerTransport.handle_post_message is itself an ASGI callable.
app.mount("/mcp/messages/", sse_transport.handle_post_message)


def main() -> None:
    import uvicorn

    host = os.getenv("NEMO_HOST", "0.0.0.0")
    port = int(os.getenv("NEMO_PORT", "8765"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    uvicorn.run("nemo_server:app", host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
