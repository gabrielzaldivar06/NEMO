# NEMO — Persistent AI Memory System

## What is NEMO

NEMO is a long-term memory MCP server for AI agents. It persists conversations,
semantic memories, schedules, and corrections across sessions using SQLite + vector
embeddings. The MCP server name is `nemo`. All memory lives in `~/.ai_memory/`.

## Memory Workflow

### On every new conversation
1. Call `search_memories` with the main topic or user name to retrieve relevant context.
2. Call `get_recent_context` to surface recent activity (last 24–72 h).
3. If the user mentions their name or key preferences and they are not already stored,
   call `create_memory` with `memory_type = "preference"`.

### During conversation
- When the user shares something new and durable (preference, fact, project detail),
  call `create_memory` immediately — do **not** wait until the end.
- When the user **corrects** something you said, call `create_correction` right away.
  Corrections receive a permanent +0.35 relevance boost and take priority in future recall.
- Tag memories with 2–5 relevant keywords using the `tags` field.

### At end of a long session
- Call `store_conversation` to persist the full session summary.
- Call `reflect_on_tool_usage` if multiple tools were used, to improve future behaviour.

## Memory Types — When to Use Each

| Type | Use when |
|------|----------|
| `preference` | User states a personal preference, working style, or taste |
| `fact` | Factual information about the user, project, or domain |
| `procedure` | Step-by-step process the user wants remembered |
| `insight` | Non-obvious conclusion from a conversation |
| `correction` | User corrects an error you made — use `create_correction` tool |
| `episodic` | Specific event or decision that happened at a point in time |

Importance scale: `1`–`10`. Use `8–10` only for information the user explicitly
says is critical. Default to `6` for most durable facts.

## Scheduling & Reminders

- When the user mentions a task, deadline, or recurring commitment, offer to store it
  via `create_reminder` or `create_appointment`.
- Check `get_upcoming_appointments` at session start if the user asks about their schedule.
- Recurring patterns: `daily`, `weekly`, `monthly`, `yearly`.

## Search Strategy

- Use **specific queries** over generic ones: `"Python project Flask API"` beats `"programming"`.
- If the first search returns no relevant results, retry with a broader or synonym query.
- `search_memories` accepts `memory_type` filter — use it when the query clearly targets
  one type (e.g., looking for a procedure).

## Conventions

- **Never fabricate memories.** If `search_memories` returns nothing relevant, say so —
  do not invent past context.
- **No duplicate creation.** NEMO deduplicates at write-time (cosine > 0.92), but avoid
  calling `create_memory` for the same fact in the same conversation.
- **Retrieval before writing.** When the user asks "do you remember…", search first
  before stating you don't know.
- **Spanish or English.** Store memories in the language the user used to express them.

## Architecture (quick reference)

- `ai_memory_mcp_server.py` — MCP entry point, 31 exposed tools
- `ai_memory_core.py` — Core logic: 11-phase semantic search, embeddings, reranking
- `settings.py` — All config via `AI_MEMORY_*` env vars
- `embedding_config.json` — Primary: LM Studio Qwen3-4B @ :1234 | Fallback: Ollama nomic
- Reranker: BGE-reranker-v2-m3 via LM Studio `/v1/rerank`

See [NEMO_TECHNICAL_REFERENCE.md](../NEMO_TECHNICAL_REFERENCE.md) for full technical documentation.
