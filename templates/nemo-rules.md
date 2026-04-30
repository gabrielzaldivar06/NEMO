# NEMO — Persistent Memory for AI Agents

You have a long-term memory server called **NEMO** running locally. Use it.
Without it you operate blind: you repeat past mistakes, contradict prior
decisions in this project, and hallucinate facts the user already taught you.

## Connection

NEMO connects via **MCP stdio** — the tools below appear automatically in your client.
No HTTP server, no URL to configure.

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

### 4. When the user shares a durable fact — `create_memory` / `update_memory`
Preferences, decisions, project facts, working style.
Do not wait until the end of the conversation — write it as soon as you hear it.

- If the fact is **new** → call `detect_redundancy` first, then `create_memory` if no duplicate found.
- If the fact **updates something already stored** (e.g. user changed stack, revised a decision) → call `update_memory` on the existing memory instead of creating a new one.

```
detect_redundancy(content: string, tags?: string[])
create_memory(content: string, memory_type: string, importance_level?: 1-10, tags?: string[])
update_memory(memory_id: string, content?: string, importance_level?: 1-10, tags?: string[])
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

If the MCP tools are unavailable or calls fail:
1. Tell the user once: "NEMO is not reachable — running without persistent memory for this session."
2. Continue normally without trying to call NEMO tools.
3. Do not silently swallow the error.
