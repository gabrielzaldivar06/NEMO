<!-- BEGIN NEMO RULES v1 -->
# NEMO — Persistent Memory for AI Agents

You have a long-term memory server called **NEMO** running locally. Use it.
Without it you operate blind: you repeat past mistakes, contradict prior
decisions in this project, and hallucinate facts the user already taught you.

## Connection

- **MCP (preferred):** `http://localhost:8765/mcp/sse`
- **REST fallback:** `http://localhost:8765/api/...` — see `http://localhost:8765/openapi.json`

If your client speaks MCP, the tools below appear automatically.
If you can only call HTTP, use `POST /api/tools/{tool_name}` with `{"arguments": {...}}`.

## Required call sequence

### 1. Start of every session — `prime_context`
**Call this FIRST**, before responding to anything, including greetings.
It returns: high-importance memories, pending reminders, and the last session summary.
Skipping it means you operate without context.

```
prime_context(topic?: string, tags_include?: string[])
```

### 2. Before asserting any project-specific fact — `search_memories`
Call this before stating an API exists, a decision was made, a preference is set, etc.
A confident wrong answer is worse than a slow correct one.

```
search_memories(query: string, limit?: number, tags_include?: string[], compact?: boolean)
```

Use specific queries (`"Python Flask API project"`, not `"programming"`).
If the first query returns nothing relevant, retry with a broader synonym.

### 3. The moment the user corrects you — `create_correction`
Not at end of session. **Right then.**
Corrections get a permanent +0.35 retrieval boost so the same error never repeats.

```
create_correction(wrong_assumption: string, correct_answer: string, context?: string, tags?: string[])
```

### 4. When the user shares a durable fact — `create_memory`
Preferences, decisions, project facts, working style.
Do not wait until the end of the conversation — write it as soon as you hear it.

```
create_memory(content: string, memory_type: string, importance_level?: 1-10, tags?: string[])
```

### 5. End of meaningful session — `store_conversation`
Persists the exchange so the next session has context.

```
store_conversation(content: string, role: "user"|"assistant", session_id?: string)
```

## Memory types — pick one

| Type          | When to use                                             |
|---------------|---------------------------------------------------------|
| `preference`  | User states a personal preference, working style, taste |
| `fact`        | Factual info about user, project, domain                |
| `procedure`   | Step-by-step process the user wants remembered          |
| `insight`     | Non-obvious conclusion drawn during conversation        |
| `correction`  | User corrected an error — use `create_correction` tool  |
| `episodic`    | Specific event or decision at a point in time           |

**Importance scale 1–10.** Default to `6` for durable facts.
Reserve `8–10` for things the user explicitly says are critical.

## Tags

Always tag memories with 2–5 relevant keywords. At minimum include:
- A project tag (e.g. the repo or product name)
- A type tag (`preference`, `decision`, `bug`, `idea`, etc.)
- Optional: a domain tag (`backend`, `infra`, `personal`, `study`)

Tags are how you avoid cross-project contamination. When you call
`prime_context` or `search_memories`, pass `tags_include: ["this-project"]`
to scope retrieval to the current work.

## Reminders & schedule

- When the user mentions a deadline, task, or recurring commitment → call `create_reminder` or `create_appointment`.
- Reminders due soon are already in `prime_context` output — don't fetch them separately.
- Recurring patterns: `daily`, `weekly`, `monthly`, `yearly`.

## Hard rules

- **Never fabricate memories.** If `search_memories` returns nothing, say so. Don't invent past context.
- **No duplicates.** NEMO deduplicates at write-time (cosine > 0.92). Don't call `create_memory` twice for the same fact in one conversation.
- **Retrieval before writing.** When the user asks "do you remember…", search NEMO first; do not say "I don't know" without checking.
- **Same language as the user.** Store memories in the language the user used.
- **One project = one tag set.** Always pass project-scoped `tags_include` so memories from other projects don't bleed in.

## When NEMO is unreachable

If you cannot reach `http://localhost:8765/health` (timeout, connection refused, etc.):
1. Tell the user once: "NEMO is not reachable — running without persistent memory for this session."
2. Continue normally without trying to call NEMO tools.
3. Do not silently swallow the error.
<!-- END NEMO RULES -->

<!-- ──────────────────────────────────────────────────────────────────────── -->
<!-- The block below is specific to the NEMO source repo and is intentionally -->
<!-- OUTSIDE the NEMO RULES markers, so future `nemo-attach` upgrades do not  -->
<!-- touch it.                                                                 -->
<!-- ──────────────────────────────────────────────────────────────────────── -->

## Working on the NEMO source code itself

If you are an AI agent editing **this repository** (not an arbitrary user
project that happens to use NEMO), the rules above still apply — but a few
extras matter for contributing here.

### How to run locally

```bash
docker compose up -d --build       # one image, embedding sidecar baked in
curl http://localhost:8765/health  # verify
```

For the GPU profile (Ollama as embeddings sidecar):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

To attach NEMO rules to a sandbox project (used during smoke tests):

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  -v "$PWD":/workdir nemo:local nemo-attach
```

### Architecture at a glance

- `ai_memory_core.py` — original 5-database core (conversations, ai_memories,
  schedule, vscode_project, mcp_tool_calls) + EmbeddingService + RerankingService.
  **Do not modify directly** unless a bug fix specifically requires it; prefer
  composition.
- `ai_memory_mcp_server.py` — original MCP-stdio entry point. Exposes ~42 tools
  (number depends on detected client via `USER_AGENT`). **Do not modify
  directly**; the universal HTTP server reuses its `_execute_tool` and `server`.
- `nemo_server.py` — universal HTTP server (FastAPI) added by the Docker
  deployment. Mounts `/mcp/sse`, `/api/*`, `/embed/*`, `/health`.
- `embeddings_sidecar.py` — in-process fastembed-backed `/v1/embeddings` server,
  mounted at `/embed`. Lets the existing EmbeddingService talk to a local
  OpenAI-compatible provider with zero core changes.
- `bin/nemo_attach.py` + `templates/nemo-rules.md` — the canonical-template
  installer used to drop these rule files into any project.
- `nemo_daemon.py` + `start_nemo_daemon.{ps1,bat}` — Windows-friendly daemon
  wrapper added by the upstream author. Independent from the Docker path.

### What not to touch (and why)

| File | Reason |
|---|---|
| `ai_memory_core.py` | The author's curated core. All Docker work is composed on top via env-var-driven config and FastAPI mounts. |
| `ai_memory_mcp_server.py` | Same. `nemo_server.py` reuses it via `AIMemoryMCPServer()`. |
| `embedding_config.json` (host file) | Inside the container, this is **regenerated** at startup by `docker/generate_config.py` from env vars. The host file is for plain-Python use only. |
| `.github/copilot-instructions.md` | Author's hand-curated Copilot instructions. The other rule files in this repo were generated by `nemo-attach`; this one predates it. |

### PR conventions seen in history

- `feat:` for new functionality, `fix:` for bug fixes, `docs:` for doc-only
  changes, `perf:` for performance work.
- Address review comments in **follow-up PRs**, not by force-pushing over a
  merged commit. The branch `fix/copilot-review-feedback` is the canonical
  example.
- Smoke tests are run by hand (no CI for the Docker stack yet). The expected
  baseline: container reaches `healthy`, `/health` returns `{"status":"ok"}`,
  `/api/tools` returns >= 30 tools, `/mcp/sse` returns 200 with
  `Content-Type: text/event-stream`.
