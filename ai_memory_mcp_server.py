#!/usr/bin/env python3
"""
Persistent AI Memory System - MCP Server

Acts as an interface layer between MCP clients (VS Code, LM Studio, Ollama UIs)
and the AI Memory System. Provides standardized tools for memory operations
while maintaining client-specific access controls.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import time
import warnings
import os
# MCP imports
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Annotations,
    CallToolRequestParams,
    CallToolResult,
    TextContent,
    Tool,
    ToolAnnotations,
    Resource,
)

# Local imports (will be implemented)
from ai_memory_core import PersistentAIMemorySystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIMemoryMCPServer:
    """MCP Server for Friday's Memory System"""

    def __init__(self):
        self.memory_system = PersistentAIMemorySystem()
        self.server = Server("ai-memory")
        self.client_context = {}  # Track client-specific context
        self._maintenance_task = None  # Background maintenance task
        self._session_primed = False    # Sprint 1 T4: first-call injection flag
        self._primed_bundle = None      # Sprint 1 T6: pre-heated context bundle
        
        # Enable debug logging for MCP server
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
        
        # Register MCP handlers
        self._register_handlers()
        
        # Start automatic maintenance
        self._start_automatic_maintenance()

        # Sprint 1 T6 — Kick off context pre-heating as a background task.
        # prime_context() runs immediately after the event loop starts so that
        # _primed_bundle is warm by the time the first tool call arrives.
        # _start_preheat() is called from run() after the loop is running.
        
        logger.info("AIMemoryMCPServer initialized successfully")
    
    def _register_handlers(self):
        """Register MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools based on client context"""
            return await self._get_client_tools()
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Execute tool based on client and parameters"""
            return await self._execute_tool(name, arguments or {})

        # Sprint 1 T5 — MCP Resources: clients that support resources (e.g. VS Code Copilot)
        # receive active context BEFORE the LLM generates its first token, with zero tool calls.
        @self.server.list_resources()
        async def handle_list_resources():
            return [
                Resource(
                    uri="memory://context/active",
                    name="Active Context",
                    description="High-priority memories + pending reminders — auto-loaded before conversation starts",
                    mimeType="text/plain",
                    annotations=Annotations(
                        audience=["assistant"],
                        priority=1.0,
                    ),
                ),
                Resource(
                    uri="memory://context/session",
                    name="Last Session",
                    description="Compressed summary of the most recent conversation session",
                    mimeType="text/plain",
                    annotations=Annotations(
                        audience=["assistant"],
                        priority=0.8,
                    ),
                ),
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: str):
            import urllib.parse
            uri_str = str(uri)
            if uri_str == "memory://context/active":
                bundle = self._primed_bundle or await self.memory_system.prime_context()
                self._primed_bundle = bundle
                self._session_primed = True
                lines = ["=== NEMO Active Context ==="]
                for m in bundle.get("memories", []):
                    lines.append(f"• {m}")
                reminders = bundle.get("reminders", [])
                if reminders:
                    lines.append("\nReminders:")
                    for r in reminders:
                        lines.append(f"  ⏰ {r}")
                ls = bundle.get("last_session")
                if ls:
                    lines.append(f"\nLast session: {ls}")
                return "\n".join(lines)
            elif uri_str == "memory://context/session":
                bundle = self._primed_bundle or await self.memory_system.prime_context()
                self._primed_bundle = bundle
                ls = bundle.get("last_session") or "No previous sessions found."
                return f"Last session: {ls}"
            return "Resource not found."
    
    async def _get_client_tools(self) -> List[Tool]:
        """Return tools available to the current client"""
        logger.debug("Getting client tools")
        
        # Detect client type based on user agent or connection context
        client_type = self._detect_client_type()
        logger.info(f"Detected client type: {client_type}")
        
        # Behavioral annotation constants — help clients decide auto-approval & trust level
        _RONLY   = ToolAnnotations(readOnlyHint=True,  openWorldHint=False)
        _WRITE   = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
        _UPDATE  = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
        _DESTROY = ToolAnnotations(readOnlyHint=False, destructiveHint=True,  openWorldHint=False)
        _EXTERN  = ToolAnnotations(readOnlyHint=True,  openWorldHint=True)

        try:
            # Common tools available to all clients
            common_tools = [
            Tool(
                name="prime_context",
                annotations=_RONLY,
                description=(
                    "REQUIRED FIRST ACTION — call this before you respond to anything, including greetings. "
                    "Skipping it means operating blind: you will repeat mistakes already made in previous sessions, "
                    "contradict past architectural decisions, and assert things that are wrong for this project. "
                    "Returns working memory in a single call: high-priority memories, pending reminders, last session summary. "
                    "Do NOT call search_memories or get_reminders until this has been called. "
                    "Pass topic= to narrow memory retrieval to a specific project or subject. "
                    "Pass tags_include= to restrict memories to specific project tags and avoid cross-workspace contamination."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Optional topic to focus memory retrieval (e.g. 'NEMO dev sprint')"},
                        "tags_include": {"type": "array", "items": {"type": "string"}, "description": "Only return memories that have at least one of these tags — useful to restrict results to the current project and avoid cross-workspace contamination."}
                    },
                    "additionalProperties": False
                }
            ),
            Tool(
                name="search_memories",
                annotations=_RONLY,
                description=(
                    "Call before asserting that any API, method, architecture decision, or project fact exists. "
                    "A confident wrong answer based on stale training data is worse than a slow correct one. "
                    "Required before answering questions about past decisions, preferences, or project state. "
                    "Use compact=true (default) to save tokens. "
                    "Returns memories ranked by semantic relevance + importance + recency."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                        "database_filter": {"type": "string", "description": "Filter by database type", "enum": ["conversations", "ai_memories", "schedule", "all"], "default": "all"},
                        "min_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Minimum importance level to include (1-10)"},
                        "max_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum importance level to include (1-10)"},
                        "memory_type": {"type": "string", "description": "Filter by memory type (e.g., 'safety', 'preference', 'skill', 'general')"},
                        "compact": {"type": "boolean", "description": "Return compressed one-line strings instead of full JSON objects — saves ~90% tokens", "default": True},
                        "tags_include": {"type": "array", "items": {"type": "string"}, "description": "Only return memories that have at least one of these tags — useful to restrict results to the current project."},
                        "hyde": {"type": "boolean", "description": "Enable HyDE (Hypothetical Document Embeddings): uses Ollama qwen2.5:0.5b to generate 3 semantic variants of the query and searches with the centroid embedding. Improves recall for paraphrased or abstract queries. Requires Ollama running locally. Gracefully degrades to standard search if unavailable.", "default": False}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="store_conversation",
                annotations=_WRITE,
                description=(
                    "Store a conversation message. Call this after each meaningful exchange. "
                    "Skipping it means this session is lost — the next conversation starts without knowing what happened here."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Conversation content"},
                        "role": {"type": "string", "description": "Role (user/assistant)"},
                        "session_id": {"type": "string", "description": "Session identifier"},
                        "metadata": {"type": "object", "description": "Additional metadata"}
                    },
                    "required": ["content", "role"]
                }
            ),
            Tool(
                name="create_memory",
                annotations=_WRITE,
                description="Persist an important fact, decision, or preference to long-term memory. Use for anything worth remembering across sessions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "memory_type": {"type": "string", "description": "Type of memory"},
                        "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Memory tags"},
                        "source_conversation_id": {"type": "string", "description": "Source conversation ID"}
                    },
                    "required": ["content"]
                }
            ),
            Tool(
                name="create_correction",
                annotations=_WRITE,
                description=(
                    "CALL THIS immediately when the user corrects you — not at the end of the session, right now. "
                    "Stores the mistake and correct answer with maximum priority (+0.35 retrieval boost). "
                    "Skipping this means the same error repeats in future sessions. "
                    "Corrections are always surfaced before regular memories during retrieval."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "wrong_assumption": {
                            "type": "string",
                            "description": "What the AI said or assumed incorrectly"
                        },
                        "correct_answer": {
                            "type": "string",
                            "description": "The right information or the user's correction"
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional context: which topic, file, or system this correction applies to"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags to aid retrieval"
                        }
                    },
                    "required": ["wrong_assumption", "correct_answer"]
                }
            ),
            Tool(
                name="update_memory",
                annotations=_UPDATE,
                description="Update an existing curated memory",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Memory ID to update"},
                        "content": {"type": "string", "description": "Updated content"},
                        "importance_level": {"type": "integer", "description": "Updated importance"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Updated tags"}
                    },
                    "required": ["memory_id"]
                }
            ),
            Tool(
                name="create_appointment",
                annotations=_WRITE,
                description="Create an appointment, optionally recurring (e.g., weekly mental health appointments)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Appointment title"},
                        "description": {"type": "string", "description": "Appointment description"},
                        "scheduled_datetime": {"type": "string", "description": "ISO format datetime for first appointment"},
                        "location": {"type": "string", "description": "Location"},
                        "recurrence_pattern": {"type": "string", "description": "Recurrence pattern: 'daily', 'weekly', 'monthly', 'yearly'", "enum": ["daily", "weekly", "monthly", "yearly"]},
                        "recurrence_count": {"type": "integer", "description": "Number of appointments to create (including first), e.g., 12 for 12 weeks", "minimum": 1},
                        "recurrence_end_date": {"type": "string", "description": "End date for recurrences (ISO format), alternative to recurrence_count"}
                    },
                    "required": ["title", "scheduled_datetime"]
                }
            ),
            Tool(
                name="create_reminder",
                annotations=_WRITE,
                description="Create a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Reminder content"},
                        "due_datetime": {"type": "string", "description": "ISO format datetime"},
                        "priority_level": {"type": "integer", "description": "Priority (1-10)", "default": 5}
                    },
                    "required": ["content", "due_datetime"]
                }
            ),
            Tool(
                name="get_reminders",
                annotations=_RONLY,
                description="Get active reminders. Already included in prime_context() for session start — call this separately only when you need reminder status mid-conversation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of reminders to return", "default": 5}
                    }
                }
            ),
            Tool(
                name="get_recent_context",
                annotations=_RONLY,
                description="Get raw recent message history. Prefer prime_context() for session start — use this only when you need specific past messages mid-conversation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of recent items", "default": 5},
                        "session_id": {"type": "string", "description": "Specific session ID"}
                    }
                }
            ),
            Tool(
                name="get_system_health",
                annotations=_RONLY,
                description="Get comprehensive system health, statistics, and database status",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_tool_usage_summary",
                annotations=_RONLY,
                description="Get AI tool usage summary and insights for self-reflection",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "Specific client ID to analyze"}
                    }
                }
            ),
            Tool(
                name="reflect_on_tool_usage",
                annotations=_WRITE,
                description="AI self-reflection on tool usage patterns and effectiveness",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "days": {"type": "integer", "description": "Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "Specific client ID to analyze"}
                    }
                }
            ),
            Tool(
                name="get_ai_insights",
                annotations=_RONLY,
                description="Get recent AI self-reflection insights and patterns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of insights", "default": 5},
                        "insight_type": {"type": "string", "description": "Type of insight to filter"}
                    }
                }
            ),
            Tool(
                name="get_active_reminders",
                annotations=_RONLY,
                description="Get active (not completed) reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of reminders to return", "default": 10},
                        "days_ahead": {"type": "integer", "description": "Only show reminders due within X days", "default": 30}
                    }
                }
            ),
            Tool(
                name="get_completed_reminders",
                annotations=_RONLY,
                description="Get recently completed reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Look back X days", "default": 7}
                    }
                }
            ),
            Tool(
                name="complete_reminder",
                annotations=_WRITE,
                description="Mark a reminder as completed",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder to complete"}
                    },
                    "required": ["reminder_id"]
                }
            ),
            Tool(
                name="reschedule_reminder",
                annotations=_WRITE,
                description="Update the due date of a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder"},
                        "new_due_datetime": {"type": "string", "description": "New ISO datetime (e.g., 2025-08-03T14:00:00Z)"}
                    },
                    "required": ["reminder_id", "new_due_datetime"]
                }
            ),
            Tool(
                name="delete_reminder",
                annotations=_DESTROY,
                description="Permanently delete a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder to delete"}
                    },
                    "required": ["reminder_id"]
                }
            ),
            Tool(
                name="cancel_appointment",
                annotations=_DESTROY,
                description="Cancel a scheduled appointment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string", "description": "ID of the appointment to cancel"}
                    },
                    "required": ["appointment_id"]
                }
            ),
            Tool(
                name="complete_appointment",
                annotations=_WRITE,
                description="Mark an appointment as completed",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string", "description": "ID of the appointment to complete"}
                    },
                    "required": ["appointment_id"]
                }
            ),
            Tool(
                name="get_upcoming_appointments",
                annotations=_RONLY,
                description="Get upcoming appointments (not cancelled)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number to return", "default": 5},
                        "days_ahead": {"type": "integer", "description": "Only show within X days", "default": 30}
                    }
                }
            ),
            Tool(
                name="get_appointments",
                annotations=_RONLY,
                description="Get recent appointments, optionally filtered by date range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of appointments to return", "default": 5},
                        "days_ahead": {"type": "integer", "description": "Only show appointments scheduled within X days", "default": 30}
                    }
                }
            ),
            Tool(
                name="store_ai_reflection",
                annotations=_WRITE,
                description="Store an AI self-reflection/insight record (manual write)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Freeform write-up of the reflection"},
                        "reflection_type": {"type": "string", "description": "Category (e.g., tool_usage_analysis, memory, general)", "default": "general"},
                        "insights": {"type": "array", "items": {"type": "string"}, "description": "Bullet insights derived from the analysis"},
                        "recommendations": {"type": "array", "items": {"type": "string"}, "description": "Recommended next actions"},
                        "confidence_level": {"type": "number", "description": "Confidence 0.0–1.0", "default": 0.7},
                        "source_period_days": {"type": "integer", "description": "Days of data this reflection summarizes"}
                    },
                    "required": ["content"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="write_ai_insights",
                annotations=_WRITE,
                description="Alias of store_ai_reflection – write an AI self-reflection/insight record",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Freeform write-up of the reflection"},
                        "reflection_type": {"type": "string", "description": "Category (e.g., tool_usage_analysis, memory, general)", "default": "general"},
                        "insights": {"type": "array", "items": {"type": "string"}, "description": "Bullet insights derived from the analysis"},
                        "recommendations": {"type": "array", "items": {"type": "string"}, "description": "Recommended next actions"},
                        "confidence_level": {"type": "number", "description": "Confidence 0.0–1.0", "default": 0.7},
                        "source_period_days": {"type": "integer", "description": "Days of data this reflection summarizes"}
                    },
                    "required": ["content"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_current_time",
                annotations=_RONLY,
                description="Get the current server time in ISO format (UTC and local)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_weather_open_meteo",
                annotations=_EXTERN,
                description="Open-Meteo forecast (no API key). Defaults to Motley, MN and caches once per local day.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "latitude": {"type": ["number", "null"], "description": "Ignored unless override=True"},
                        "longitude": {"type": ["number", "null"], "description": "Ignored unless override=True"},
                        "timezone_str": {"type": ["string", "null"], "description": "Ignored unless override=True"},
                        "force_refresh": {"type": "boolean", "description": "Ignore same-day cache", "default": False},
                        "return_changes_only": {"type": "boolean", "description": "If true, return only a summary of changed fields for today.", "default": False},
                        "update_today": {"type": "boolean", "description": "If true (default), fetch and merge changes into today's file before returning.", "default": True},
                        "severe_update": {"type": "boolean", "description": "If true, shrink the update window to 30 minutes for severe weather.", "default": False}
                    }
                }
            ),
            # ----------------------------------------------------------------
            # Sprint 14 — Cognitive Features
            # ----------------------------------------------------------------
            Tool(
                name="salience_score",
                annotations=_RONLY,
                description=(
                    "Compute 4-channel cognitive salience for content before storing. "
                    "Returns importance_suggested (1-10) and per-channel breakdown: "
                    "novelty (how different from existing memories), arousal (urgency), "
                    "reward (achievement signal), attention (explicit importance markers). "
                    "Use before create_memory or cognitive_ingest to let the system suggest importance."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to score"},
                        "context": {"type": "string", "description": "Optional surrounding context"}
                    },
                    "required": ["content"]
                }
            ),
            Tool(
                name="cognitive_ingest",
                annotations=_WRITE,
                description=(
                    "Adaptive memory storage with Prediction-Error Gating — smarter than create_memory. "
                    "Automatically decides: CREATE (content is novel), UPDATE (refines existing), "
                    "or SUPERSEDE (replaces existing) based on cosine similarity to existing memories. "
                    "Also auto-computes importance via salience_score. "
                    "Use this instead of create_memory when you want intelligent deduplication."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content":      {"type": "string",  "description": "Content to store"},
                        "memory_type":  {"type": "string",  "description": "Memory type (fact, procedure, insight, etc.)"},
                        "tags":         {"type": "array",   "items": {"type": "string"}, "description": "Tags"},
                        "context":      {"type": "string",  "description": "Optional context for salience scoring"},
                        "force_create": {"type": "boolean", "description": "Skip similarity check and always create", "default": False}
                    },
                    "required": ["content"]
                }
            ),
            Tool(
                name="memory_chronicle",
                annotations=_RONLY,
                description=(
                    "Browse memories chronologically, grouped by day. "
                    "Useful for auditing what was stored in a period, reviewing sprint history, "
                    "or generating summaries. Defaults to the last 30 days."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date_from":    {"type": "string",  "description": "Start date YYYY-MM-DD (default: 30 days ago)"},
                        "date_to":      {"type": "string",  "description": "End date YYYY-MM-DD (default: today)"},
                        "limit":        {"type": "integer", "description": "Max memories to return", "default": 50},
                        "tags_include": {"type": "array",   "items": {"type": "string"}, "description": "Filter by tags"}
                    }
                }
            ),
            Tool(
                name="detect_redundancy",
                annotations=_WRITE,
                description=(
                    "Detect and optionally merge redundant memories by cosine similarity. "
                    "Returns clusters of similar memories with similarity scores. "
                    "Set auto_merge=true to automatically keep the highest-importance memory per cluster "
                    "and soft-delete the rest. Useful for cleaning up after bulk ingestion sessions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "threshold":    {"type": "number",  "description": "Cosine similarity threshold (default: 0.88)", "default": 0.88},
                        "limit":        {"type": "integer", "description": "Max clusters to return", "default": 20},
                        "auto_merge":   {"type": "boolean", "description": "Automatically merge redundant memories", "default": False},
                        "tags_include": {"type": "array",   "items": {"type": "string"}, "description": "Restrict to memories with these tags"}
                    }
                }
            ),
            Tool(
                name="anticipate",
                annotations=_RONLY,
                description=(
                    "Proactive memory retrieval — predicts what you will need next based on current context. "
                    "Returns ranked memories with a 'why_relevant' annotation explaining the prediction. "
                    "Call this when starting a complex task to pre-load relevant memories before they are asked for."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "context":      {"type": "string",  "description": "Current work context or task description"},
                        "limit":        {"type": "integer", "description": "Max predictions to return", "default": 5},
                        "tags_include": {"type": "array",   "items": {"type": "string"}, "description": "Restrict to memories with these tags"}
                    },
                    "required": ["context"]
                }
            ),
            Tool(
                name="intent_anchor",
                annotations=_WRITE,
                description=(
                    "Store a prospective memory: 'remind me when X happens'. "
                    "Unlike time-based reminders, intent anchors fire when the trigger_condition is "
                    "semantically matched in future queries or prime_context calls. "
                    "Example: trigger_condition='about to push to production', action='run benchmark first'."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trigger_condition": {"type": "string",  "description": "Semantic condition that activates this anchor"},
                        "action":            {"type": "string",  "description": "What to do / remember when triggered"},
                        "importance_level":  {"type": "integer", "description": "Importance 1-10 (default: 7)", "default": 7},
                        "tags":              {"type": "array",   "items": {"type": "string"}, "description": "Optional tags"}
                    },
                    "required": ["trigger_condition", "action"]
                }
            ),
            Tool(
                name="synaptic_tagging",
                annotations=_WRITE,
                description=(
                    "Retroactively elevate importance of memories semantically related to a high-salience memory. "
                    "Models neuroscience synaptic tagging: consolidating a strong memory also strengthens "
                    "related contextual memories. Also fires automatically when create_memory is called with "
                    "importance_level >= 9. Call manually to propagate importance from any memory_id."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id":      {"type": "string",  "description": "Source memory ID to propagate from"},
                        "boost":          {"type": "integer", "description": "Importance points to add (default: 1)", "default": 1},
                        "max_importance": {"type": "integer", "description": "Cap importance at this value (default: 9)", "default": 9},
                        "limit":          {"type": "integer", "description": "Max related memories to boost (default: 5)", "default": 5},
                        "tags_include":   {"type": "array",   "items": {"type": "string"}, "description": "Only boost memories with these tags"}
                    },
                    "required": ["memory_id"]
                }
            ),
        ]
        except Exception as e:
            logger.error(f"Error creating common tools: {e}")
            common_tools = []
        
        # VS Code specific tools
        vscode_tools = [
            Tool(
                name="save_development_session",
                annotations=_WRITE,
                description="Save VS Code development session context",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workspace_path": {"type": "string", "description": "Workspace path"},
                        "active_files": {"type": "array", "items": {"type": "string"}, "description": "Active files"},
                        "git_branch": {"type": "string", "description": "Current git branch"},
                        "session_summary": {"type": "string", "description": "Session summary"}
                    },
                    "required": ["workspace_path"]
                }
            ),
            Tool(
                name="store_project_insight",
                annotations=_WRITE,
                description="Store development insight or decision",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "insight_type": {"type": "string", "description": "Type of insight"},
                        "content": {"type": "string", "description": "Insight content"},
                        "related_files": {"type": "array", "items": {"type": "string"}, "description": "Related files"},
                        "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5}
                    },
                    "required": ["content"]
                }
            ),
            Tool(
                name="search_project_history",
                annotations=_RONLY,
                description="Search VS Code project development history",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="link_code_context",
                annotations=_WRITE,
                description="Link conversation to specific code context",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "function_name": {"type": "string", "description": "Function name"},
                        "description": {"type": "string", "description": "Context description"},
                        "conversation_id": {"type": "string", "description": "Related conversation ID"}
                    },
                    "required": ["file_path", "description"]
                }
            ),
            Tool(
                name="get_project_continuity",
                annotations=_RONLY,
                description="Get context to continue development work",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workspace_path": {"type": "string", "description": "Workspace path"},
                        "limit": {"type": "integer", "description": "Context items", "default": 5}
                    }
                }
            )
        ]
        
        try:
            # Return appropriate tools based on client type
            if client_type == "sillytavern":
                # SillyTavern gets memory tools + character/roleplay specific tools
                sillytavern_tools = [
                    Tool(
                        name="get_character_context",
                        annotations=_RONLY,
                        description="Get relevant context about characters from memory",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "character_name": {"type": "string", "description": "Character name to search for"},
                                "context_type": {"type": "string", "description": "Type of context (personality, relationships, history)"},
                                "limit": {"type": "integer", "description": "Max results", "default": 5}
                            },
                            "required": ["character_name"]
                        }
                    ),
                    Tool(
                        name="store_roleplay_memory",
                        annotations=_WRITE,
                        description="Store important roleplay moments or character developments",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "character_name": {"type": "string", "description": "Character involved"},
                                "event_description": {"type": "string", "description": "What happened"},
                                "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5},
                                "tags": {"type": "array", "items": {"type": "string"}, "description": "Relevant tags"}
                            },
                            "required": ["character_name", "event_description"]
                        }
                    ),
                    Tool(
                        name="search_roleplay_history",
                        annotations=_RONLY,
                        description="Search past roleplay interactions and character development",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "character_name": {"type": "string", "description": "Focus on specific character"},
                                "limit": {"type": "integer", "description": "Max results", "default": 10}
                            },
                            "required": ["query"]
                        }
                    )
                ]
                return common_tools + sillytavern_tools
            
            elif client_type == "vscode":
                # VS Code gets development-specific tools
                return common_tools + vscode_tools
            
            else:
                # Default: LM Studio, Ollama UIs, etc. get core memory tools only
                return common_tools
                
        except Exception as e:
            logger.error(f"Error combining tool lists: {e}")
            return []

    def _detect_client_type(self) -> str:
        """Detect the type of MCP client connecting"""
        # Detect the type of MCP client connecting
        client_type = "unknown"
        if "VS Code" in os.getenv("USER_AGENT", ""):
            client_type = "vscode"
        elif "LM Studio" in os.getenv("USER_AGENT", ""):
            client_type = "lm_studio"
        elif "Silly Tavern" in os.getenv("USER_AGENT", ""):
            client_type = "sillytavern"
        elif "Ollama" in os.getenv("USER_AGENT", ""):
            client_type = "ollama"
        logger.info(f"Detected client type: {client_type}")
        return client_type
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute the requested tool with logging for AI self-reflection"""
        
        import time
        
        # Start timing and get client info
        start_time = time.perf_counter()
        client_id = self.client_context.get("current_client", "unknown")
        
        try:
            logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")

            # Sprint 1 T4 — First-call context injection
            # Only inject if:  (a) session not yet primed  AND  (b) the preheat bundle is
            # already warm (_primed_bundle is not None).  Avoids firing a second concurrent
            # prime_context() call when _preheat_context() is still running in the background
            # — the triple-fire race (preheat + first-call + resource read) was a main freeze
            # cause when LM Studio was slow to respond to the first embedding request.
            injected_context = None
            if not self._session_primed and tool_name != "prime_context":
                self._session_primed = True
                if self._primed_bundle is not None:
                    # Preheat finished — attach the ready bundle for free
                    injected_context = self._primed_bundle
                # else: preheat still running; skip injection to avoid duplicate embedding call

            # Route to appropriate handler
            if tool_name == "prime_context":
                result = await self.memory_system.prime_context(
                    topic=arguments.get("topic"),
                    tags_include=arguments.get("tags_include"),
                )
                self._session_primed = True
                self._primed_bundle = result
            elif tool_name == "search_memories":
                result = await self.memory_system.search_memories(**arguments)
            elif tool_name == "store_conversation":
                result = await self.memory_system.store_conversation(**arguments)
            elif tool_name == "create_memory":
                result = await self.memory_system.create_memory(**arguments)
            elif tool_name == "create_correction":
                wrong = arguments.get("wrong_assumption", "")
                correct = arguments.get("correct_answer", "")
                context = arguments.get("context", "")
                tags = arguments.get("tags") or []
                content_parts = [f"CORRECCIÓN — lo que estaba mal: {wrong}"]
                content_parts.append(f"REALIDAD: {correct}")
                if context:
                    content_parts.append(f"Contexto: {context}")
                correction_content = "\n".join(content_parts)
                correction_tags = ["correction", "feedback"] + [t for t in tags if t not in ("correction", "feedback")]
                result = await self.memory_system.create_memory(
                    content=correction_content,
                    memory_type="correction",
                    importance_level=10,
                    tags=correction_tags,
                )
            elif tool_name == "update_memory":
                result = await self.memory_system.update_memory(**arguments)
            elif tool_name == "create_appointment":
                result = await self.memory_system.create_appointment(**arguments)
            elif tool_name == "create_reminder":
                result = await self.memory_system.create_reminder(**arguments)
            elif tool_name == "get_reminders":
                limit = arguments.get("limit", 5)
                reminders = await self.memory_system.get_active_reminders()
                result = reminders[:limit] if reminders else []
            elif tool_name == "get_recent_context":
                result = await self.memory_system.get_recent_context(**arguments)
            elif tool_name == "get_system_health":
                result = await self.memory_system.get_system_health()
            elif tool_name == "save_development_session":
                result = await self.memory_system.save_development_session(**arguments)
            elif tool_name == "store_project_insight":
                result = await self.memory_system.store_project_insight(**arguments)
            elif tool_name == "search_project_history":
                result = await self.memory_system.search_project_history(**arguments)
            elif tool_name == "link_code_context":
                result = await self.memory_system.link_code_context(**arguments)
            elif tool_name == "get_project_continuity":
                result = await self.memory_system.get_project_continuity(**arguments)
            elif tool_name == "get_tool_usage_summary":
                result = await self.memory_system.get_tool_usage_summary(**arguments)
            elif tool_name == "reflect_on_tool_usage":
                result = await self.memory_system.reflect_on_tool_usage(**arguments)
            elif tool_name == "get_ai_insights":
                result = await self.memory_system.get_ai_insights(**arguments)
            elif tool_name == "get_active_reminders":
                result = await self.memory_system.get_active_reminders(**arguments)
            elif tool_name == "get_completed_reminders":
                result = await self.memory_system.get_completed_reminders(**arguments)
            elif tool_name == "complete_reminder":
                result = await self.memory_system.complete_reminder(**arguments)
            elif tool_name == "reschedule_reminder":
                result = await self.memory_system.reschedule_reminder(**arguments)
            elif tool_name == "delete_reminder":
                result = await self.memory_system.delete_reminder(**arguments)
            elif tool_name == "cancel_appointment":
                result = await self.memory_system.cancel_appointment(**arguments)
            elif tool_name == "complete_appointment":
                result = await self.memory_system.complete_appointment(**arguments)
            elif tool_name == "get_upcoming_appointments":
                result = await self.memory_system.get_upcoming_appointments(**arguments)
            elif tool_name == "get_appointments":
                result = await self.memory_system.get_appointments(**arguments)
            elif tool_name == "store_ai_reflection" or tool_name == "write_ai_insights":
                result = await self.memory_system.store_ai_reflection(**arguments)
            elif tool_name == "get_current_time":
                result = await self.memory_system.get_current_time()
            elif tool_name == "get_weather_open_meteo":
                result = await self.memory_system.get_weather_open_meteo(**arguments)
            # SillyTavern-specific tools
            elif tool_name == "get_character_context":
                result = await self.memory_system.get_character_context(**arguments)
            elif tool_name == "store_roleplay_memory":
                result = await self.memory_system.store_roleplay_memory(**arguments)
            elif tool_name == "search_roleplay_history":
                result = await self.memory_system.search_roleplay_history(**arguments)
            # Sprint 14 — Cognitive Features
            elif tool_name == "salience_score":
                result = await self.memory_system.salience_score(**arguments)
            elif tool_name == "cognitive_ingest":
                result = await self.memory_system.cognitive_ingest(**arguments)
            elif tool_name == "memory_chronicle":
                result = await self.memory_system.memory_chronicle(**arguments)
            elif tool_name == "detect_redundancy":
                result = await self.memory_system.detect_redundancy(**arguments)
            elif tool_name == "anticipate":
                result = await self.memory_system.anticipate(**arguments)
            elif tool_name == "intent_anchor":
                result = await self.memory_system.intent_anchor(**arguments)
            elif tool_name == "synaptic_tagging":
                result = await self.memory_system.synaptic_tagging(**arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            # Calculate execution time and log successful call
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000
            
            # Log tool call for AI self-reflection (async, don't wait)
            asyncio.create_task(self.memory_system.log_tool_call(
                client_id=client_id,
                tool_name=tool_name,
                parameters=arguments,
                execution_time_ms=execution_time_ms,
                status="success",
                result=result
            ))
            
            # Format the result as a proper TextContent object
            if isinstance(result, (dict, list)):
                # Sprint 1 T4 — prepend session context on first call
                if injected_context is not None and isinstance(result, dict):
                    result = {"session_context": injected_context, **result}
                result_text = json.dumps(result, indent=2, default=str)
            else:
                result_text = str(result)
            
            text_content = {
                "type": "text",
                "text": result_text,
                "highlights": None,
                "meta": None
            }
            
            return {
                "content": [text_content],
                "success": True,
                "structuredContent": None,
                "isError": False,
                "meta": None
            }
            
        except Exception as e:
            # Calculate execution time and log failed call
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000
            
            # Log tool call failure for AI self-reflection (async, don't wait)
            asyncio.create_task(self.memory_system.log_tool_call(
                client_id=client_id,
                tool_name=tool_name,
                parameters=arguments,
                execution_time_ms=execution_time_ms,
                status="error",
                error_message=str(e)
            ))
            
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error: {str(e)}",
                    "highlights": None,
                    "meta": None
                }],
                "success": False,
                "structuredContent": None,
                "isError": True,
                "meta": None
            }
    
    def _start_automatic_maintenance(self):
        """Start automatic database maintenance background task.
        Must be called from within a running event loop (e.g. inside async main).
        """
        try:
            loop = asyncio.get_running_loop()
            self._maintenance_task = loop.create_task(self._maintenance_loop())
            logger.info("🔧 Automatic database maintenance started")
        except RuntimeError:
            logger.warning("Event loop not running — _start_automatic_maintenance() must be called from async context.")

    def _start_preheat(self):
        """Sprint 1 T6 — Schedule context pre-heating as a background task."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._preheat_context())
            logger.info("🔥 Context pre-heating scheduled")
        except RuntimeError:
            logger.warning("Event loop not running, skipping pre-heat.")

    async def _preheat_context(self):
        """Sprint 1 T6 — Run prime_context() in background so bundle is ready at first call."""
        try:
            self._primed_bundle = await self.memory_system.prime_context()
            logger.info("✅ Context pre-heated: %d memories, %d reminders",
                        len(self._primed_bundle.get("memories", [])),
                        len(self._primed_bundle.get("reminders", [])))
        except Exception as e:
            logger.warning(f"⚠️ Context pre-heating failed: {e}")
    
    async def _maintenance_loop(self):
        """Background loop for automatic database maintenance"""
        # Each process picks a random initial delay (5–20 min) so multiple workspaces
        # that all start at roughly the same time don't trigger maintenance in lockstep.
        import random
        jitter = random.uniform(5 * 60, 20 * 60)  # 5–20 minutes
        await asyncio.sleep(jitter)
        
        while True:
            try:
                logger.info("🧹 Running automatic database maintenance...")
                result = await self.memory_system.run_database_maintenance()
                
                # Log maintenance results
                if result.get("skipped"):
                    logger.info("⏭️  Maintenance skipped: %s", result.get("reason", ""))
                elif result.get("success"):
                    logger.info(f"✅ Automatic maintenance completed - optimized {len(result.get('optimization_results', {}))} databases")
                else:
                    logger.warning(f"⚠️ Automatic maintenance had issues: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"❌ Automatic maintenance failed: {e}")
            
            # Wait 3 hours before next maintenance
            await asyncio.sleep(3 * 60 * 60)
    
    async def cleanup(self):
        """Cleanup resources when server stops.

        Cancels the maintenance background task AND any other lingering
        asyncio tasks (background embeds, access-count bumps, etc.) so
        the process exits promptly when VS Code closes the stdio pipe.
        Zombie processes were largely caused by hanging background tasks
        keeping the event loop alive after the connection was gone.
        """
        # Cancel maintenance loop
        if self._maintenance_task and not self._maintenance_task.done():
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
            logger.info("🔧 Automatic maintenance stopped")

        # Cancel all remaining background tasks spawned during this session
        # (embedding generation, access-count bumps, dedup tasks, etc.)
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
        if pending:
            logger.info(f"🧹 Cancelling {len(pending)} background task(s) on shutdown")
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        # Close the embedding service's shared HTTP session (defensive — core also
        # calls this in its own shutdown path, so we suppress double-close errors)
        try:
            await self.memory_system.embedding_service.close()
        except Exception:
            pass
    



async def start_http_server(mcp_server: AIMemoryMCPServer, host: str = "127.0.0.1", port: int = 11434):
    """Start the HTTP API server if needed"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        
        app = FastAPI(title="Friday Memory API")
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.get("/api/health")
        async def health_check():
            return {"status": "healthy", "server": "ai-memory"}
            
        # Start server without blocking
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        return await server.serve()
    except ImportError:
        logger.info("FastAPI not installed - HTTP API disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to start HTTP server: {e}")
        return None

async def main():
    """Main entry point for the MCP server"""
    logger.info("AI Memory MCP Server starting... (PID %d)", os.getpid())
    
    # Set debug logging for MCP components
    logging.getLogger("mcp").setLevel(logging.DEBUG)
    logging.getLogger("mcp.server").setLevel(logging.DEBUG)
    
    mcp_server = AIMemoryMCPServer()
    
    logger.debug("Server initialized, starting stdio interface for LM Studio...")
    
    try:
        # Only use stdio for LM Studio - no HTTP server needed
        logger.info("Waiting for stdio connection from LM Studio...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("LM Studio connected via stdio")
            mcp_server._start_preheat()   # Sprint 1 T6 — pre-heat context bundle
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ai-memory",
                    server_version="1.2.0",
                    capabilities=mcp_server.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    ),
                    instructions=(
                        "NEMO persistent memory system active. Risk of not using it:\n"
                        "- Skip prime_context → repeat mistakes already made, contradict previous architectural decisions\n"
                        "- Skip search_memories → hallucinate APIs or project details with false confidence\n"
                        "- Skip create_correction → same error repeats in future sessions\n\n"
                        "Required sequence each session:\n"
                        "① prime_context() FIRST — before you respond to anything, including greetings\n"
                        "② search_memories(query) — before asserting any project fact, API, or decision\n"
                        "③ respond\n\n"
                        "On corrections: create_correction() immediately — not at end of session, right now.\n"
                        "On session end: store_conversation() to persist context for next session."
                    )
                )
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await mcp_server.cleanup()


def cli():
    """Synchronous console entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
