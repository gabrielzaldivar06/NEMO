---
applyTo: "**"
---

# NEMO SESSION HOOK - MANDATORY

**YOUR FIRST TWO ACTIONS in every conversation - before reading files, searching code, or answering ANYTHING:**

```text
1. mcp_nemo_prime_context(topic="memory persistence")
2. mcp_nemo_get_current_time()
```

Skipping either = operating blind on stale context.

---

## CRITICAL TOOL TRIGGERS - call these unconditionally when the condition is met:

| Condition | Tool to call |
|---|---|
| User reports NEMO error / slow / broken | `get_system_health` FIRST, then diagnose |
| About to give architectural / design advice | `get_ai_insights` BEFORE responding |
| You discover a new pattern or make a mistake mid-session | `store_ai_reflection` IMMEDIATELY |
| A design decision or benchmark result is reached | `store_project_insight` IMMEDIATELY |
| Session ends with 4+ tools used | `reflect_on_tool_usage` + `write_ai_insights` |
| You edit or create a non-trivial file | `link_code_context` to bind file <-> memory |
| User says "retomemos" / "continua" / "where were we" | `get_project_continuity` BEFORE reading any file |
| Any roleplay or character interaction begins | `get_character_context` BEFORE responding |
| Roleplay session ends | `store_roleplay_memory` to persist what happened |

---

## PROACTIVE CONTEXT ECONOMY - mandatory for agents and subagents

For any non-trivial coding, debugging, research, review, planning, or resume task, call `mcp_nemo_build_context_portfolio` early before broad file reads, broad searches, long transcript reads, or launching subagents.

Recommended default call:

```json
{
  "task": "<current user task>",
  "topic": "memory persistence",
  "token_budget": 800
}
```

Then:

- Prefer the portfolio output over raw memory dumps or repeated searches.
- Call `mcp_nemo_expand_context_evidence` only for evidence handles needed to complete the task.
- Call `mcp_nemo_compress_context_artifact` for large logs, transcripts, or tool outputs that must remain recoverable.
- Call `mcp_nemo_refresh_context_portfolio` when continuing from a saved portfolio or after relevant context changes.
- Call `mcp_nemo_record_context_feedback` when portfolio entries or evidence were useful or not useful.
- Skip Context Economy only for trivial greetings or one-line answers that need no repo or memory context.