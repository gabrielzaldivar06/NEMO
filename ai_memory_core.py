#!/usr/bin/env python3
"""
Persistent AI Memory System - Core Module

A comprehensive memory system designed for long-term persistence, semantic search,
and AI assistant augmentation. This standalone version includes all core functionality
with enhanced features for broader use.

Key Features:
- Specialized Database Architecture:
  * Conversations with automatic session management
  * AI-curated memories with importance levels and tags
  * Appointment and reminder scheduling
  * VS Code project context and development tracking
  * MCP tool call logging with AI self-reflection

- Advanced Search and Retrieval:
  * Vector-based semantic search across all databases
  * Project-specific search capabilities
  * Code context linking and retrieval
  * Importance-weighted memory search
  * Fallback text-based search when embeddings unavailable

- Enhanced AI Capabilities:
  * Automatic embedding generation
  * Usage pattern detection and analysis
  * AI self-reflection on tool usage
  * Pattern-based recommendations
  * Confidence scoring for insights

- Real-time Monitoring:
  * Conversation file monitoring
  * Multiple chat source support (VS Code, LM Studio, ChatGPT, etc.)
  * Deduplication across sources
  * MCP server integration
  
- System Management:
  * Comprehensive health monitoring
  * Automated database maintenance
  * Error tracking and logging
  * Performance optimization

- Development Tools:
  * Project continuity tracking
  * Code context management
  * Development session history
  * Insight storage and retrieval

All timestamps are stored in the local timezone using ISO format. This ensures
that timestamps are correctly displayed and interpreted in the local time context.

For usage examples and integration guides, see the documentation in /docs.
"""

import asyncio
import sqlite3
import json
import uuid
import logging
import aiohttp
import numpy as np
import hashlib
import os
import re
import time
import socket
import difflib
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

# Get local timezone
def get_local_timezone() -> tzinfo:
    """Get local timezone based on system settings"""
    try:
        import time
        return ZoneInfo(time.tzname[0])
    except Exception:
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz is not None:
            return local_tz
        return timezone.utc
    
def get_current_timestamp() -> str:
    """Get current timestamp in local timezone ISO format"""
    return datetime.now(get_local_timezone()).isoformat()
    
def datetime_to_local_isoformat(dt: datetime) -> str:
    """Convert any datetime to local timezone ISO format"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_local_timezone())
    return dt.astimezone(get_local_timezone()).isoformat()

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib
import sqlite3
import json
import uuid
import hashlib
import asyncio
import aiohttp
import logging
import os
import re
import time
import socket
import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from database_maintenance import DatabaseMaintenance
from settings import get_settings

# Configure logging with minimal output
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
# Only show important messages and errors
logger.setLevel(logging.WARNING)

SEARCH_STOPWORDS = {
    "a", "al", "and", "como", "con", "cual", "cuál", "de", "del", "el",
    "en", "for", "how", "la", "las", "los", "para", "por", "q", "que",
    "qué", "se", "si", "the", "to", "usa", "using", "y",
}

SEARCH_TOKEN_ALIASES = {
    "embeddings": "embedding",
    "fallbak": "fallback",
    "helth": "health",
    "llamacpp": "llama_cpp",
    "lmstudio": "lm_studio",
    "poweshell": "powershell",
    "qewn": "qwen",
    "semantca": "semantic",
    "sessoin": "session",
    "sevrer": "server",
    "sutdio": "studio",
    "v1embeddings": "v1_embeddings",
    "winodws": "windows",
    "worksapce": "workspace",
}


class DatabaseManager:
    """Base database manager for common operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.ensure_database_exists()
    
    def ensure_database_exists(self):
        """Ensure the database file and directory exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        return conn
    
    def _execute_query_sync(self, query: str, params: Tuple) -> List[sqlite3.Row]:
        """Synchronous SELECT — run via asyncio.to_thread to avoid blocking the event loop."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()

    async def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query without blocking the async event loop."""
        return await asyncio.to_thread(self._execute_query_sync, query, params)

    def _execute_update_sync(self, query: str, params: Tuple) -> int:
        """Synchronous INSERT/UPDATE/DELETE — run via asyncio.to_thread."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
        finally:
            conn.close()

    async def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query without blocking the async event loop."""
        return await asyncio.to_thread(self._execute_update_sync, query, params)
                
    def parse_timestamp(self, timestamp: Union[str, int, float, None], fallback: Optional[datetime] = None) -> str:
        """Parse various timestamp formats into ISO format string.
        
        Args:
            timestamp: Input timestamp (string, unix timestamp, or None)
            fallback: Optional fallback datetime if parsing fails
            
        Returns:
            ISO format datetime string
        """
        if not timestamp:
            return (fallback or datetime.now(get_local_timezone())).isoformat()
            
        try:
            if isinstance(timestamp, (int, float)):
                # Unix timestamp
                dt = datetime.fromtimestamp(timestamp, timezone.utc)
            elif isinstance(timestamp, str):
                # Try various string formats
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    # Try parsing with dateutil as fallback
                    from dateutil import parser
                    dt = parser.parse(timestamp)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
            else:
                raise ValueError(f"Unsupported timestamp format: {type(timestamp)}")
                
            return dt.isoformat()
            
        except Exception as e:
            logger.warning(f"Error parsing timestamp {timestamp}: {e}")
            return (fallback or datetime.now(get_local_timezone())).isoformat()


class MCPToolCallDatabase(DatabaseManager):
    """Tracks all MCP tool calls for reflection and debugging"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(get_settings().mcp_db_path)
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tool call tracking tables"""
        with self.get_connection() as conn:
            # Tool calls table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_calls (
                    call_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    client_id TEXT,
                    tool_name TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    result TEXT,
                    status TEXT NOT NULL,
                    execution_time_ms INTEGER,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tool usage statistics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_usage_stats (
                    stat_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    call_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    avg_execution_time_ms REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tool_name, date)
                )
            """)
            
            # AI reflections table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_reflections (
                    reflection_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    reflection_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    insights TEXT,
                    recommendations TEXT,
                    confidence_level REAL DEFAULT 0.5,
                    source_period_days INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Usage patterns table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    analysis_period_days INTEGER NOT NULL,
                    confidence_score REAL DEFAULT 0.5,
                    supporting_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    async def log_tool_call(self, tool_name: str, parameters: Dict, result: Any = None, 
                           status: str = "success", execution_time_ms: float = None,
                           error_message: str = None, client_id: str = None) -> str:
        """Log a tool call with all relevant details"""
        
        call_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        # Store the tool call
        await self.execute_update(
            """INSERT INTO tool_calls 
               (call_id, timestamp, client_id, tool_name, parameters, result, 
                status, execution_time_ms, error_message) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (call_id, timestamp, client_id, tool_name, 
             json.dumps(parameters), json.dumps(result) if result else None,
             status, int(execution_time_ms) if execution_time_ms else None, error_message)
        )
        
        # Update daily statistics
        await self._update_tool_stats(tool_name, status, execution_time_ms)
        
        return call_id
    
    async def _update_tool_stats(self, tool_name: str, status: str, execution_time_ms: float):
        """Update daily usage statistics for a tool"""
        today = datetime.now(get_local_timezone()).date().isoformat()
        
        # Check if stat record exists for today
        existing = await self.execute_query(
            "SELECT * FROM tool_usage_stats WHERE tool_name = ? AND date = ?",
            (tool_name, today)
        )
        
        if existing:
            # Update existing record
            stat = existing[0]
            new_call_count = stat["call_count"] + 1
            new_success_count = stat["success_count"] + (1 if status == "success" else 0)
            new_error_count = stat["error_count"] + (1 if status == "error" else 0)
            
            # Calculate new average execution time
            if execution_time_ms and stat["avg_execution_time_ms"]:
                new_avg = ((stat["avg_execution_time_ms"] * stat["call_count"]) + execution_time_ms) / new_call_count
            elif execution_time_ms:
                new_avg = execution_time_ms
            else:
                new_avg = stat["avg_execution_time_ms"]
            
            await self.execute_update(
                """UPDATE tool_usage_stats 
                   SET call_count = ?, success_count = ?, error_count = ?, avg_execution_time_ms = ?
                   WHERE tool_name = ? AND date = ?""",
                (new_call_count, new_success_count, new_error_count, new_avg, tool_name, today)
            )
        else:
            # Create new record
            stat_id = str(uuid.uuid4())
            await self.execute_update(
                """INSERT INTO tool_usage_stats 
                   (stat_id, tool_name, date, call_count, success_count, error_count, avg_execution_time_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (stat_id, tool_name, today, 1,
                 1 if status == "success" else 0,
                 1 if status == "error" else 0,
                 execution_time_ms or 0)
            )
    
    async def get_tool_usage_summary(self, days: int = 7) -> Dict:
        """Get tool usage summary for the last N days"""
        
        # Get recent tool calls
        recent_calls = await self.execute_query(
            """SELECT tool_name, status, COUNT(*) as count
               FROM tool_calls 
               WHERE timestamp >= datetime('now', '-{} days')
               GROUP BY tool_name, status
               ORDER BY count DESC""".format(days)
        )
        
        # Get daily stats
        daily_stats = await self.execute_query(
            """SELECT * FROM tool_usage_stats 
               WHERE date >= date('now', '-{} days')
               ORDER BY date DESC, call_count DESC""".format(days)
        )
        
        # Get most used tools
        most_used = await self.execute_query(
            """SELECT tool_name, COUNT(*) as total_calls
               FROM tool_calls 
               WHERE timestamp >= datetime('now', '-{} days')
               GROUP BY tool_name
               ORDER BY total_calls DESC
               LIMIT 10""".format(days)
        )
        
        return {
            "recent_calls": [dict(row) for row in recent_calls],
            "daily_stats": [dict(row) for row in daily_stats],
            "most_used_tools": [dict(row) for row in most_used],
            "period_days": days
        }
    
    async def get_tool_call_history(self, tool_name: str = None, limit: int = 50) -> List[Dict]:
        """Get recent tool call history, optionally filtered by tool name"""
        
        if tool_name:
            query = """SELECT * FROM tool_calls 
                      WHERE tool_name = ? 
                      ORDER BY timestamp DESC 
                      LIMIT ?"""
            params = (tool_name, limit)
        else:
            query = """SELECT * FROM tool_calls 
                      ORDER BY timestamp DESC 
                      LIMIT ?"""
            params = (limit,)
        
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]
        
    async def store_ai_reflection(self, reflection_type: str, content: str,
                                insights: List[str] = None, recommendations: List[str] = None,
                                confidence_level: float = 0.5, source_period_days: int = None) -> str:
        """Store AI self-reflection on tool usage and patterns.
        
        Args:
            reflection_type: Type of reflection (e.g., usage_patterns, performance, suggestions)
            content: Main reflection content
            insights: List of specific insights gained
            recommendations: List of action recommendations
            confidence_level: Confidence in the reflection (0-1)
            source_period_days: Period of data analyzed
            
        Returns:
            str: Reflection ID
        """
        reflection_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        await self.execute_update(
            """INSERT INTO ai_reflections 
               (reflection_id, timestamp, reflection_type, content, insights, 
                recommendations, confidence_level, source_period_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (reflection_id, timestamp, reflection_type, content,
             json.dumps(insights) if insights else None,
             json.dumps(recommendations) if recommendations else None,
             confidence_level, source_period_days)
        )
        
        return reflection_id
        
    async def store_usage_pattern(self, pattern_type: str, insight: str, 
                                analysis_period_days: int, confidence_score: float = 0.5,
                                supporting_data: Dict = None) -> str:
        """Store identified usage pattern from AI analysis.
        
        Args:
            pattern_type: Type of usage pattern
            insight: Description of the pattern
            analysis_period_days: Period analyzed to identify pattern
            confidence_score: Confidence in pattern (0-1)
            supporting_data: Additional data supporting the pattern
            
        Returns:
            str: Pattern ID
        """
        pattern_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        await self.execute_update(
            """INSERT INTO usage_patterns
               (pattern_id, timestamp, pattern_type, insight, analysis_period_days,
                confidence_score, supporting_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pattern_id, timestamp, pattern_type, insight, analysis_period_days,
             confidence_score, json.dumps(supporting_data) if supporting_data else None)
        )
        
        return pattern_id
        
    async def get_recent_reflections(self, limit: int = 5, reflection_type: str = None) -> List[Dict]:
        """Get recent AI reflections, optionally filtered by type.
        
        Args:
            limit: Maximum number of reflections to return
            reflection_type: Optional filter by reflection type
            
        Returns:
            List of reflection entries
        """
        if reflection_type:
            query = """SELECT * FROM ai_reflections
                      WHERE reflection_type = ?
                      ORDER BY timestamp DESC
                      LIMIT ?"""
            params = (reflection_type, limit)
        else:
            query = """SELECT * FROM ai_reflections
                      ORDER BY timestamp DESC
                      LIMIT ?"""
            params = (limit,)
            
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]


class ConversationDatabase(DatabaseManager):
    """Manages conversation auto-save database"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(get_settings().conversations_db_path)
        super().__init__(db_path)
        self.initialize_tables()

    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # --- Migration logic for messages table ---
            expected_columns = [
                'message_id', 'conversation_id', 'timestamp', 'role', 'content', 'source_type',
                'source_id', 'source_url', 'source_metadata', 'sync_status', 'last_sync',
                'metadata', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(messages)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in expected_columns:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating messages table to new schema!")
                old_rows = conn.execute("SELECT * FROM messages").fetchall()
                conn.execute("DROP TABLE IF EXISTS messages")
                conn.execute("""
                    CREATE TABLE messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_type TEXT,
                        source_id TEXT,
                        source_url TEXT,
                        source_metadata TEXT,
                        sync_status TEXT,
                        last_sync TEXT,
                        metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in expected_columns:
                        if col not in row_dict:
                            row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO messages ({', '.join(expected_columns)}) VALUES ({', '.join(['?' for _ in expected_columns])})",
                        tuple(row_dict[col] for col in expected_columns)
                    )
                print(f"Restored {len(old_rows)} messages after migration.")
            else:
                # Create table if not exists (normal path)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_type TEXT,
                        source_id TEXT,
                        source_url TEXT,
                        source_metadata TEXT,
                        sync_status TEXT,
                        last_sync TEXT,
                        metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                """)

            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT,
                    context TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Conversations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT,
                    topic_summary TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)

            # Source metadata table for tracking chat sources
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_tracking (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_path TEXT,
                    last_check TEXT NOT NULL,
                    last_sync TEXT,
                    status TEXT NOT NULL,
                    error_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Cross-source relationships table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    source_conversation_id TEXT NOT NULL,
                    related_conversation_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_conversation_id) REFERENCES conversations (conversation_id),
                    FOREIGN KEY (related_conversation_id) REFERENCES conversations (conversation_id)
                )
            """)

            conn.commit()
    
    async def store_message(self, content: str, role: str, session_id: str = None, 
                          conversation_id: str = None, metadata: Dict = None) -> Dict[str, str]:
        """Store a message and auto-manage sessions/conversations with duplicate detection"""
        timestamp = get_current_timestamp()
        message_id = str(uuid.uuid4())

        # Advanced duplicate detection: check for existing message with same content, role, and session in last hour
        if session_id:
            existing = await self.execute_query(
                """SELECT message_id FROM messages 
                   WHERE conversation_id IN (
                       SELECT conversation_id FROM conversations WHERE session_id = ?
                   ) AND role = ? AND content = ? 
                   AND datetime(timestamp) > datetime('now', '-1 hour')""",
                (session_id, role, content)
            )
            if existing:
                print(f"Skipping duplicate message in session {session_id}")
                return {
                    "message_id": existing[0]["message_id"],
                    "conversation_id": None,
                    "session_id": session_id,
                    "duplicate": True
                }

        # Auto-create session if not provided or doesn't exist
        if not session_id:
            session_id = str(uuid.uuid4())
            await self.execute_update(
                "INSERT INTO sessions (session_id, start_timestamp, context) VALUES (?, ?, ?)",
                (session_id, timestamp, "auto-created")
            )
        else:
            existing_session = await self.execute_query(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            if not existing_session:
                await self.execute_update(
                    "INSERT INTO sessions (session_id, start_timestamp, context) VALUES (?, ?, ?)",
                    (session_id, timestamp, "imported-session")
                )

        # Auto-create conversation if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            await self.execute_update(
                "INSERT INTO conversations (conversation_id, session_id, start_timestamp) VALUES (?, ?, ?)",
                (conversation_id, session_id, timestamp)
            )

        # Store the message
        await self.execute_update(
            """INSERT INTO messages 
               (message_id, conversation_id, timestamp, role, content, metadata) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (message_id, conversation_id, timestamp, role, content, 
             json.dumps(metadata) if metadata else None)
        )

        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "duplicate": False
        }
    
    async def get_recent_messages(self, limit: int = 10, session_id: str = None) -> List[Dict]:
        """Get recent messages, optionally filtered by session"""
        
        if session_id:
            query = """
                SELECT m.*, c.session_id 
                FROM messages m 
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE c.session_id = ?
                ORDER BY m.timestamp DESC 
                LIMIT ?
            """
            params = (session_id, limit)
        else:
            query = """
                SELECT m.*, c.session_id 
                FROM messages m 
                JOIN conversations c ON m.conversation_id = c.conversation_id
                ORDER BY m.timestamp DESC 
                LIMIT ?
            """
            params = (limit,)
        
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]


class AIMemoryDatabase(DatabaseManager):
    """Manages AI-curated memories database with enhanced operations"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(get_settings().ai_memories_db_path)
        super().__init__(db_path)
        self.initialize_tables()

    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            expected_columns = [
                'memory_id', 'timestamp_created', 'timestamp_updated', 'source_conversation_id',
                'source_message_ids', 'memory_type', 'content', 'importance_level', 'tags',
                'embedding', 'created_at', 'access_count', 'last_accessed_at',
                'stability', 'difficulty'
            ]
            cur = conn.execute("PRAGMA table_info(curated_memories)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in expected_columns:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating curated_memories table to new schema!")
                old_rows = conn.execute("SELECT * FROM curated_memories").fetchall()
                conn.execute("DROP TABLE IF EXISTS curated_memories")
                conn.execute("""
                    CREATE TABLE curated_memories (
                        memory_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        timestamp_updated TEXT NOT NULL,
                        source_conversation_id TEXT,
                        source_message_ids TEXT,
                        memory_type TEXT,
                        content TEXT NOT NULL,
                        importance_level INTEGER DEFAULT 5,
                        tags TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 0,
                        last_accessed_at TEXT,
                        stability REAL DEFAULT 1.0,
                        difficulty REAL DEFAULT 0.3
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in expected_columns:
                        if col not in row_dict:
                            row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO curated_memories ({', '.join(expected_columns)}) VALUES ({', '.join(['?' for _ in expected_columns])})",
                        tuple(row_dict[col] for col in expected_columns)
                    )
                print(f"Restored {len(old_rows)} curated memories after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS curated_memories (
                        memory_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        timestamp_updated TEXT NOT NULL,
                        source_conversation_id TEXT,
                        source_message_ids TEXT,
                        memory_type TEXT,
                        content TEXT NOT NULL,
                        importance_level INTEGER DEFAULT 5,
                        tags TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 0,
                        last_accessed_at TEXT,
                        stability REAL DEFAULT 1.0,
                        difficulty REAL DEFAULT 0.3
                    )
                """)
                # Sprint 9 — add access_count / last_accessed_at if missing (live migration)
                cur2 = conn.execute("PRAGMA table_info(curated_memories)")
                live_cols = [r[1] for r in cur2.fetchall()]
                if 'access_count' not in live_cols:
                    conn.execute("ALTER TABLE curated_memories ADD COLUMN access_count INTEGER DEFAULT 0")
                if 'last_accessed_at' not in live_cols:
                    conn.execute("ALTER TABLE curated_memories ADD COLUMN last_accessed_at TEXT")
                # FSRS-6 — stability and difficulty fields
                if 'stability' not in live_cols:
                    conn.execute("ALTER TABLE curated_memories ADD COLUMN stability REAL DEFAULT 1.0")
                if 'difficulty' not in live_cols:
                    conn.execute("ALTER TABLE curated_memories ADD COLUMN difficulty REAL DEFAULT 0.3")
            conn.commit()

    async def create_memory(self, content: str, memory_type: str = None, 
                          importance_level: int = 5, tags: List[str] = None,
                          source_conversation_id: str = None) -> str:
        """Create a new curated memory with duplicate detection"""
        memory_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()

        # Advanced duplicate detection: check for existing memory with same content, type, and source
        existing = await self.execute_query(
            """SELECT memory_id FROM curated_memories 
                   WHERE content = ? AND memory_type = ? AND source_conversation_id IS ?""",
            (content, memory_type, source_conversation_id)
        )
        if existing:
            print("Skipping duplicate curated memory entry.")
            return existing[0]["memory_id"]

        await self.execute_update(
            """INSERT INTO curated_memories 
               (memory_id, timestamp_created, timestamp_updated, source_conversation_id, 
                memory_type, content, importance_level, tags) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, timestamp, timestamp, source_conversation_id, 
             memory_type, content, importance_level, 
             json.dumps(tags) if tags else None)
        )
        return memory_id
        """Run database maintenance tasks.
        
        Args:
            force: Whether to force maintenance even if recent
            
        Returns:
            Dict containing maintenance results
        """
        try:
            # Check last maintenance
            last_maintenance = await self.execute_query(
                "SELECT value FROM metadata WHERE key = 'last_maintenance'"
            )
            
            if not force and last_maintenance:
                last_time = datetime.fromisoformat(last_maintenance[0]["value"])
                if datetime.now(get_local_timezone()) - last_time < timedelta(days=7):
                    return {
                        "status": "skipped",
                        "message": "Maintenance ran recently",
                        "last_run": last_time.isoformat()
                    }
            
            with self.get_connection() as conn:
                # Optimize indexes
                conn.execute("ANALYZE")
                
                # Clean up any orphaned records
                conn.execute("""
                    DELETE FROM curated_memories 
                    WHERE source_conversation_id NOT IN (
                        SELECT conversation_id FROM conversations
                    ) AND source_conversation_id IS NOT NULL
                """)
                
                # Update metadata
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("last_maintenance", get_current_timestamp())
                )
                
                conn.commit()
                
            return {
                "status": "success",
                "message": "Maintenance completed successfully",
                "timestamp": get_current_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Maintenance error: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": get_current_timestamp()
            }
    
    def initialize_tables(self):
        """Create tables if they don't exist, and add new columns via live migration."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curated_memories (
                    memory_id TEXT PRIMARY KEY,
                    timestamp_created TEXT NOT NULL,
                    timestamp_updated TEXT NOT NULL,
                    source_conversation_id TEXT,
                    source_message_ids TEXT,
                    memory_type TEXT,
                    content TEXT NOT NULL,
                    importance_level INTEGER DEFAULT 5,
                    tags TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at TEXT,
                    stability REAL DEFAULT 1.0,
                    difficulty REAL DEFAULT 0.3
                )
            """)
            # Sprint 9 T2 — live-migration for databases created before this sprint
            cur = conn.execute("PRAGMA table_info(curated_memories)")
            existing_cols = [r[1] for r in cur.fetchall()]
            if 'access_count' not in existing_cols:
                conn.execute("ALTER TABLE curated_memories ADD COLUMN access_count INTEGER DEFAULT 0")
            if 'last_accessed_at' not in existing_cols:
                conn.execute("ALTER TABLE curated_memories ADD COLUMN last_accessed_at TEXT")
            # FSRS-6 — stability and difficulty fields
            if 'stability' not in existing_cols:
                conn.execute("ALTER TABLE curated_memories ADD COLUMN stability REAL DEFAULT 1.0")
            if 'difficulty' not in existing_cols:
                conn.execute("ALTER TABLE curated_memories ADD COLUMN difficulty REAL DEFAULT 0.3")
            # Sprint 11 — FTS5 virtual table for sparse BM25 retrieval (hybrid dense+sparse)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS curated_memories_fts
                USING fts5(
                    memory_id UNINDEXED,
                    content,
                    tags,
                    tokenize='unicode61 remove_diacritics 1'
                )
            """)
            # Backfill any rows not yet indexed (safe to run repeatedly)
            conn.execute("""
                INSERT INTO curated_memories_fts(memory_id, content, tags)
                SELECT memory_id, content, COALESCE(tags, '')
                FROM curated_memories
                WHERE memory_id NOT IN (SELECT memory_id FROM curated_memories_fts)
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_memories_ai
                AFTER INSERT ON curated_memories BEGIN
                    INSERT INTO curated_memories_fts(memory_id, content, tags)
                    VALUES (new.memory_id, new.content, COALESCE(new.tags, ''));
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_memories_au
                AFTER UPDATE ON curated_memories BEGIN
                    DELETE FROM curated_memories_fts WHERE memory_id = old.memory_id;
                    INSERT INTO curated_memories_fts(memory_id, content, tags)
                    VALUES (new.memory_id, new.content, COALESCE(new.tags, ''));
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS fts_memories_ad
                AFTER DELETE ON curated_memories BEGIN
                    DELETE FROM curated_memories_fts WHERE memory_id = old.memory_id;
                END
            """)
            conn.commit()
    
    @staticmethod
    def _build_fts_query(text: str) -> str:
        """Convert free-text to an FTS5 MATCH expression (broad OR of significant tokens)."""
        import re
        tokens = re.findall(r'[a-z\u00e0-\u00fc\u00c0-\u00dc0-9_]{3,}', text, re.IGNORECASE)
        if not tokens:
            return ""
        return " OR ".join(f'"{t}"' for t in dict.fromkeys(t.lower() for t in tokens))

    async def search_fts(self, query: str, limit: int = 20) -> List[Dict]:
        """BM25 sparse retrieval from FTS5 index.

        Returns ranked list of row dicts (metadata only, no embedding BLOB).
        Embeddings are fetched separately by callers that need them, avoiding
        fetching large BLOBs for the many results that turn out to be duplicates
        of the dense candidate pool.
        SQLite FTS5 bm25() returns negative values — ORDER BY ASC = best first.
        """
        fts_expr = self._build_fts_query(query)
        if not fts_expr:
            return []
        try:
            rows = await self.execute_query(
                """SELECT cm.memory_id, cm.content, cm.importance_level, cm.memory_type,
                          cm.timestamp_created, cm.tags, cm.access_count,
                          bm25(curated_memories_fts) AS bm25_score
                   FROM curated_memories_fts
                   JOIN curated_memories cm USING (memory_id)
                   WHERE curated_memories_fts MATCH ?
                   ORDER BY bm25_score
                   LIMIT ?""",
                (fts_expr, limit),
            )
        except Exception as e:
            logger.warning(f"FTS search error (non-fatal): {e}")
            return []
        return [
            {
                "memory_id": row["memory_id"],
                "content": row["content"],
                "importance_level": row["importance_level"],
                "memory_type": row["memory_type"],
                "timestamp_created": row["timestamp_created"],
                "tags": row["tags"],
                "access_count": row["access_count"] or 0,
                "bm25": float(row["bm25_score"]),
            }
            for row in rows
        ]

    async def get_embeddings_by_ids(self, memory_ids: List[str]) -> Dict[str, bytes]:
        """Fetch embedding BLOBs for a specific set of memory_ids."""
        if not memory_ids:
            return {}
        placeholders = ",".join("?" * len(memory_ids))
        rows = await self.execute_query(
            f"SELECT memory_id, embedding FROM curated_memories WHERE memory_id IN ({placeholders})",
            tuple(memory_ids),
        )
        return {
            row["memory_id"]: bytes(row["embedding"])
            for row in rows
            if row["embedding"]
        }

    async def create_memory(self, content: str, memory_type: str = None, 
                          importance_level: int = 5, tags: List[str] = None,
                          source_conversation_id: str = None) -> str:
        """Create a new curated memory with duplicate detection"""
        
        memory_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()

        existing = await self.execute_query(
            """SELECT memory_id FROM curated_memories
               WHERE content = ? AND memory_type = ? AND source_conversation_id IS ?""",
            (content, memory_type, source_conversation_id)
        )
        if existing:
            return existing[0]["memory_id"]
        
        await self.execute_update(
            """INSERT INTO curated_memories 
               (memory_id, timestamp_created, timestamp_updated, source_conversation_id, 
                memory_type, content, importance_level, tags) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, timestamp, timestamp, source_conversation_id, 
             memory_type, content, importance_level, 
             json.dumps(tags) if tags else None)
        )
        
        return memory_id


class ScheduleDatabase(DatabaseManager):
    """Manages appointments and reminders database"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(get_settings().schedule_db_path)
        super().__init__(db_path)
        self.initialize_tables()

    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # Appointments table migration
            appointments_expected = [
                'appointment_id', 'timestamp_created', 'scheduled_datetime', 'title', 'description',
                'location', 'cancelled_at', 'completed_at', 'status', 'source_conversation_id', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(appointments)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in appointments_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating appointments table to new schema!")
                old_rows = conn.execute("SELECT * FROM appointments").fetchall()
                conn.execute("DROP TABLE IF EXISTS appointments")
                conn.execute("""
                    CREATE TABLE appointments (
                        appointment_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        scheduled_datetime TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        location TEXT,
                        status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'cancelled', 'completed')),
                        cancelled_at TEXT,
                        completed_at TEXT,
                        source_conversation_id TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in appointments_expected:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'scheduled_datetime' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            elif col == 'status':
                                row_dict[col] = 'scheduled'  # Default status for migrated appointments
                            elif col == 'cancelled_at' or col == 'completed_at':
                                row_dict[col] = None  # Default to None for new timestamp columns
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO appointments ({', '.join(appointments_expected)}) VALUES ({', '.join(['?' for _ in appointments_expected])})",
                        tuple(row_dict[col] for col in appointments_expected)
                    )
                print(f"Restored {len(old_rows)} appointments after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS appointments (
                        appointment_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        scheduled_datetime TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        location TEXT,
                        status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'cancelled', 'completed')),
                        cancelled_at TEXT,
                        completed_at TEXT,
                        source_conversation_id TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Reminders table migration
            reminders_expected = [
                'reminder_id', 'timestamp_created', 'due_datetime', 'content', 'priority_level',
                'completed', 'is_completed', 'completed_at', 'source_conversation_id', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(reminders)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in reminders_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating reminders table to new schema!")
                old_rows = conn.execute("SELECT * FROM reminders").fetchall()
                conn.execute("DROP TABLE IF EXISTS reminders")
                conn.execute("""
                    CREATE TABLE reminders (
                        reminder_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        due_datetime TEXT NOT NULL,
                        content TEXT NOT NULL,
                        priority_level INTEGER DEFAULT 5,
                        completed INTEGER DEFAULT 0,
                        is_completed INTEGER DEFAULT 0,
                        completed_at TEXT,
                        source_conversation_id TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in reminders_expected:
                        if col not in row_dict:
                            if col == 'is_completed':
                                row_dict[col] = row_dict.get('completed', 0)
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO reminders ({', '.join(reminders_expected)}) VALUES ({', '.join(['?' for _ in reminders_expected])})",
                        tuple(row_dict[col] for col in reminders_expected)
                    )
                print(f"Restored {len(old_rows)} reminders after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        reminder_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        due_datetime TEXT NOT NULL,
                        content TEXT NOT NULL,
                        priority_level INTEGER DEFAULT 5,
                        completed INTEGER DEFAULT 0,
                        is_completed INTEGER DEFAULT 0,
                        completed_at TEXT,
                        source_conversation_id TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
    
    async def create_appointment(self, title: str, scheduled_datetime: str, 
                               description: str = None, location: str = None,
                               source_conversation_id: str = None,
                               recurrence_pattern: str = None,
                               recurrence_count: int = None,
                               recurrence_end_date: str = None) -> Union[str, List[str]]:
        """Create a new appointment, optionally recurring
        
        Args:
            title: Appointment title
            scheduled_datetime: ISO format datetime for first appointment
            description: Optional description
            location: Optional location
            source_conversation_id: Optional source conversation ID
            recurrence_pattern: Optional recurrence pattern ('weekly', 'monthly', 'daily')
            recurrence_count: Optional number of recurrences (including first appointment)
            recurrence_end_date: Optional end date for recurrences (ISO format)
            
        Returns:
            Single appointment_id if no recurrence, list of appointment_ids if recurring
        """
        from dateutil.relativedelta import relativedelta
        from dateutil.parser import parse as parse_date
        
        appointment_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()

        # Duplicate detection: check for existing appointment with same title, datetime, location, and source
        existing = await self.execute_query(
            """SELECT appointment_id FROM appointments 
                   WHERE title = ? AND scheduled_datetime = ? AND location IS ? AND source_conversation_id IS ?""",
            (title, scheduled_datetime, location, source_conversation_id)
        )
        if existing:
            print("Skipping duplicate appointment entry.")
            return existing[0]["appointment_id"]

        await self.execute_update(
            """INSERT INTO appointments 
               (appointment_id, timestamp_created, scheduled_datetime, title, description, location, source_conversation_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (appointment_id, timestamp, scheduled_datetime, title, description, location, source_conversation_id)
        )
        
        appointment_ids = [appointment_id]
        
        # Handle recurring appointments
        if recurrence_pattern and (recurrence_count or recurrence_end_date):
            try:
                base_datetime = parse_date(scheduled_datetime)
                if recurrence_end_date:
                    end_date = parse_date(recurrence_end_date)
                else:
                    end_date = None
                
                # Determine the increment pattern
                if recurrence_pattern.lower() == 'daily':
                    delta = relativedelta(days=1)
                elif recurrence_pattern.lower() == 'weekly':
                    delta = relativedelta(weeks=1)
                elif recurrence_pattern.lower() == 'monthly':
                    delta = relativedelta(months=1)
                elif recurrence_pattern.lower() == 'yearly':
                    delta = relativedelta(years=1)
                else:
                    raise ValueError(f"Unsupported recurrence pattern: {recurrence_pattern}")
                
                current_datetime = base_datetime
                created_count = 1  # Already created the first one
                
                # Create recurring appointments
                while True:
                    # Check if we should stop
                    if recurrence_count and created_count >= recurrence_count:
                        break
                    if end_date and current_datetime >= end_date:
                        break
                    
                    # Calculate next occurrence
                    current_datetime += delta
                    
                    # Check end date again after increment
                    if end_date and current_datetime > end_date:
                        break
                    
                    # Skip duplicate detection for recurring appointments
                    # Create the recurring appointment
                    recurring_id = str(uuid.uuid4())
                    recurring_datetime = current_datetime.isoformat()
                    
                    await self.execute_update(
                        """INSERT INTO appointments 
                           (appointment_id, timestamp_created, scheduled_datetime, title, description, location, source_conversation_id) 
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (recurring_id, timestamp, recurring_datetime, title, description, location, source_conversation_id)
                    )
                    
                    appointment_ids.append(recurring_id)
                    created_count += 1
                    
            except Exception as e:
                logger.error(f"Error creating recurring appointments: {e}")
                # Return the first appointment ID even if recurring failed
                return appointment_id
        
        # Return single ID if no recurrence, list if recurring
        return appointment_id if len(appointment_ids) == 1 else appointment_ids
    
    async def create_reminder(self, content: str, due_datetime: str, 
                            priority_level: int = 5, source_conversation_id: str = None) -> str:
        """Create a new reminder with duplicate detection"""
        reminder_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()

        # Duplicate detection: check for existing reminder with same content, due_datetime, and source
        existing = await self.execute_query(
            """SELECT reminder_id FROM reminders 
                   WHERE content = ? AND due_datetime = ? AND source_conversation_id IS ?""",
            (content, due_datetime, source_conversation_id)
        )
        if existing:
            print("Skipping duplicate reminder entry.")
            return existing[0]["reminder_id"]

        await self.execute_update(
            """INSERT INTO reminders 
               (reminder_id, timestamp_created, due_datetime, content, priority_level, source_conversation_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (reminder_id, timestamp, due_datetime, content, priority_level, source_conversation_id)
        )
        return reminder_id
    
    async def get_upcoming_appointments(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming appointments within specified days"""
        
        future_date = datetime.now(get_local_timezone()) + timedelta(days=days_ahead)
        
        rows = await self.execute_query(
            """SELECT * FROM appointments 
               WHERE scheduled_datetime >= ? AND scheduled_datetime <= ?
               ORDER BY scheduled_datetime ASC""",
            (get_current_timestamp(), future_date.isoformat())
        )
        
        return [dict(row) for row in rows]
    
    async def get_active_reminders(self) -> List[Dict]:
        """Get all uncompleted reminders"""
        
        rows = await self.execute_query(
            "SELECT * FROM reminders WHERE completed = 0 ORDER BY due_datetime ASC"
        )
        
        return [dict(row) for row in rows]

    async def auto_complete_overdue_reminders(self) -> Dict[str, int]:
        """
        Auto-complete overdue reminders at midnight.
        Returns count of reminders that were auto-completed.
        """
        current_time = datetime.now()
        
        # Find overdue reminders that aren't already completed
        overdue_reminders = await self.execute_query(
            """SELECT reminder_id, content, due_datetime 
               FROM reminders 
               WHERE due_datetime < ? 
               AND completed = 0 
               AND is_completed = 0""",
            (current_time.isoformat(),)
        )
        
        completed_count = 0
        for reminder in overdue_reminders:
            # Mark as completed
            await self.execute_update(
                """UPDATE reminders 
                   SET completed = 1, is_completed = 1, completed_at = ?
                   WHERE reminder_id = ?""",
                (current_time.isoformat(), reminder['reminder_id'])
            )
            completed_count += 1
            
            logger.info(f"Auto-completed overdue reminder: {reminder['content']}")
        
        return {
            "completed_count": completed_count,
            "processed_at": current_time.isoformat()
        }


class VSCodeProjectDatabase(DatabaseManager):
    """Manages VS Code project context and development sessions"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(get_settings().vscode_db_path)
        super().__init__(db_path)
        self.initialize_tables()

    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # Project sessions table migration
            sessions_expected = [
                'session_id', 'start_timestamp', 'end_timestamp', 'workspace_path', 'active_files',
                'git_branch', 'session_summary', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(project_sessions)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in sessions_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating project_sessions table to new schema!")
                old_rows = conn.execute("SELECT * FROM project_sessions").fetchall()
                conn.execute("DROP TABLE IF EXISTS project_sessions")
                conn.execute("""
                    CREATE TABLE project_sessions (
                        session_id TEXT PRIMARY KEY,
                        start_timestamp TEXT NOT NULL,
                        end_timestamp TEXT,
                        workspace_path TEXT NOT NULL,
                        active_files TEXT,
                        git_branch TEXT,
                        session_summary TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in sessions_expected:
                        if col not in row_dict:
                            row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO project_sessions ({', '.join(sessions_expected)}) VALUES ({', '.join(['?' for _ in sessions_expected])})",
                        tuple(row_dict[col] for col in sessions_expected)
                    )
                print(f"Restored {len(old_rows)} project sessions after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS project_sessions (
                        session_id TEXT PRIMARY KEY,
                        start_timestamp TEXT NOT NULL,
                        end_timestamp TEXT,
                        workspace_path TEXT NOT NULL,
                        active_files TEXT,
                        git_branch TEXT,
                        session_summary TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Project insights table migration
            insights_expected = [
                'insight_id', 'timestamp_created', 'timestamp_updated', 'insight_type', 'content',
                'related_files', 'source_conversation_id', 'importance_level', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(project_insights)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in insights_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating project_insights table to new schema!")
                old_rows = conn.execute("SELECT * FROM project_insights").fetchall()
                conn.execute("DROP TABLE IF EXISTS project_insights")
                conn.execute("""
                    CREATE TABLE project_insights (
                        insight_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        timestamp_updated TEXT NOT NULL,
                        insight_type TEXT,
                        content TEXT NOT NULL,
                        related_files TEXT,
                        source_conversation_id TEXT,
                        importance_level INTEGER DEFAULT 5,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in insights_expected:
                        if col not in row_dict:
                            row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO project_insights ({', '.join(insights_expected)}) VALUES ({', '.join(['?' for _ in insights_expected])})",
                        tuple(row_dict[col] for col in insights_expected)
                    )
                print(f"Restored {len(old_rows)} project insights after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS project_insights (
                        insight_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        timestamp_updated TEXT NOT NULL,
                        insight_type TEXT,
                        content TEXT NOT NULL,
                        related_files TEXT,
                        source_conversation_id TEXT,
                        importance_level INTEGER DEFAULT 5,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Code context table migration
            codectx_expected = [
                'context_id', 'timestamp', 'file_path', 'function_name', 'description', 'purpose',
                'related_insights', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(code_context)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in codectx_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating code_context table to new schema!")
                old_rows = conn.execute("SELECT * FROM code_context").fetchall()
                conn.execute("DROP TABLE IF EXISTS code_context")
                conn.execute("""
                    CREATE TABLE code_context (
                        context_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        function_name TEXT,
                        description TEXT NOT NULL,
                        purpose TEXT,
                        related_insights TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in codectx_expected:
                        if col not in row_dict:
                            row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO code_context ({', '.join(codectx_expected)}) VALUES ({', '.join(['?' for _ in codectx_expected])})",
                        tuple(row_dict[col] for col in codectx_expected)
                    )
                print(f"Restored {len(old_rows)} code contexts after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS code_context (
                        context_id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        function_name TEXT,
                        description TEXT NOT NULL,
                        purpose TEXT,
                        related_insights TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Development conversations table migration
            devcon_expected = [
                'conversation_id', 'session_id', 'timestamp', 'chat_context_id', 'conversation_content',
                'decisions_made', 'code_changes', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(development_conversations)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in devcon_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                print("Migrating development_conversations table to new schema!")
                old_rows = conn.execute("SELECT * FROM development_conversations").fetchall()
                conn.execute("DROP TABLE IF EXISTS development_conversations")
                conn.execute("""
                    CREATE TABLE development_conversations (
                        conversation_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        timestamp TEXT NOT NULL,
                        chat_context_id TEXT,
                        conversation_content TEXT NOT NULL,
                        decisions_made TEXT,
                        code_changes TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES project_sessions (session_id)
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in devcon_expected:
                        if col not in row_dict:
                            row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO development_conversations ({', '.join(devcon_expected)}) VALUES ({', '.join(['?' for _ in devcon_expected])})",
                        tuple(row_dict[col] for col in devcon_expected)
                    )
                print(f"Restored {len(old_rows)} development conversations after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS development_conversations (
                        conversation_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        timestamp TEXT NOT NULL,
                        chat_context_id TEXT,
                        conversation_content TEXT NOT NULL,
                        decisions_made TEXT,
                        code_changes TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES project_sessions (session_id)
                    )
                """)

            conn.commit()
    
    async def save_development_session(self, workspace_path: str, active_files: List[str] = None,
                                     git_branch: str = None, session_summary: str = None) -> str:
        """Save a development session"""
        
        session_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        await self.execute_update(
            """INSERT INTO project_sessions 
               (session_id, start_timestamp, workspace_path, active_files, git_branch, session_summary) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, timestamp, workspace_path, 
             json.dumps(active_files) if active_files else None,
             git_branch, session_summary)
        )
        
        return session_id
    
    async def store_development_conversation(self, content: str, session_id: str = None,
                                          chat_context_id: str = None, decisions_made: str = None,
                                          code_changes: Dict = None) -> str:
        """Store a development conversation from VS Code
        
        Args:
            content: The conversation content
            session_id: Optional project session ID (will create new if none)
            chat_context_id: Optional VS Code chat context ID
            decisions_made: Summary of decisions made in conversation
            code_changes: Dictionary of files changed and their changes
        """
        conversation_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        # Create session if none provided
        if not session_id:
            session_id = await self.save_development_session(
                workspace_path=os.getcwd(),  # Current workspace
                session_summary="Auto-created session for development conversation"
            )
        
        # Store conversation
        await self.execute_update(
            """INSERT INTO development_conversations 
               (conversation_id, session_id, timestamp, chat_context_id,
                conversation_content, decisions_made, code_changes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (conversation_id, session_id, timestamp, chat_context_id,
             content, decisions_made, json.dumps(code_changes) if code_changes else None)
        )
        
        return conversation_id

    async def store_project_insight(self, content: str, insight_type: str = None,
                                  related_files: List[str] = None, importance_level: int = 5,
                                  source_conversation_id: str = None) -> str:
        """Store a project insight with duplicate detection"""
        insight_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()

        # Duplicate detection: check for existing insight with same content, type, and source
        existing = await self.execute_query(
            """SELECT insight_id FROM project_insights 
                   WHERE content = ? AND insight_type IS ? AND source_conversation_id IS ?""",
            (content, insight_type, source_conversation_id)
        )
        if existing:
            print("Skipping duplicate project insight entry.")
            return existing[0]["insight_id"]

        await self.execute_update(
            """INSERT INTO project_insights 
               (insight_id, timestamp_created, timestamp_updated, insight_type, content, 
                related_files, source_conversation_id, importance_level) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (insight_id, timestamp, timestamp, insight_type, content,
             json.dumps(related_files) if related_files else None,
             source_conversation_id, importance_level)
        )
        return insight_id


class ConversationFileMonitor:
    def __init__(self, memory_system, watch_directories):
        self.memory_system = memory_system
        self.watch_directories = watch_directories
        self.vscode_db = memory_system.vscode_db
        self.conversations_db = memory_system.conversations_db  # Add this to maintain compatibility
        self.curated_db = memory_system.curated_db  # Add this to maintain compatibility
        # Do NOT start file monitoring or background tasks automatically here
        
    def _parse_character_ai_format(self, data: Dict) -> List[Dict]:
        """Parse Character.ai conversation format (list of messages under 'conversation')"""
        conversations = []
        try:
            messages = data.get('conversation', [])
            for msg in messages:
                if isinstance(msg, dict) and 'content' in msg:
                    conversations.append({
                        'role': msg.get('character', msg.get('role', 'unknown')),
                        'content': msg['content'],
                        'timestamp': msg.get('timestamp')
                    })
        except Exception as e:
            logger.error(f"Error parsing Character.ai format: {e}")
        return conversations

    def _parse_text_gen_format(self, data: Dict) -> List[Dict]:
        """Parse text-generation-webui format (list of messages under 'history')"""
        conversations = []
        try:
            history = data.get('history', [])
            for msg in history:
                if isinstance(msg, dict) and 'content' in msg:
                    conversations.append({
                        'role': msg.get('role', 'unknown'),
                        'content': msg['content'],
                        'timestamp': msg.get('timestamp')
                    })
        except Exception as e:
            logger.error(f"Error parsing text-generation-webui format: {e}")
        return conversations
    """Monitors files for conversation changes and auto-imports them.
    
    Features:
    - Automatic MCP server detection to avoid duplicate message processing
    - Real-time file monitoring with hash-based change detection
    - Support for VS Code, LM Studio, and Ollama chat files
    - Message deduplication across sources
    """
    
    def __init__(self, memory_system, watch_directories: List[str] = None, mcp_port: int = 1234):
        self.memory_system = memory_system
        self.watch_directories = watch_directories or []
        self.observer = None
        self.processed_files = set()  # Track processed files to avoid duplicates
        self.file_hashes = {}  # Track file content hashes to detect changes
        self.processed_messages = {}  # Track processed messages per file: {file_path: set(message_hashes)}
        self.mcp_port = mcp_port  # Port to check for MCP server
        self.mcp_server_running = False  # Will be updated periodically
        self.last_mcp_check = 0  # Timestamp of last MCP server check
        
    def _get_default_chat_directories(self) -> List[str]:
        """Get default chat storage directories for different platforms"""
        home = Path.home()
        documents = home / "Documents"
        downloads = home / "Downloads"
        directories = []
        
        # NOTE: ChatGPT and Claude desktop apps DO NOT store conversations locally
        # They are cloud-only applications. Removed these paths after verification.
        
        # LM Studio conversation directories
        lm_studio_paths = [
            home / ".lmstudio" / "conversations",  # Windows/Linux/macOS (new location)
            home / "AppData" / "Roaming" / "LM Studio" / "conversations",  # Windows (old location)
            home / ".config" / "lm-studio" / "conversations",  # Linux (old location)
            home / "Library" / "Application Support" / "LM Studio" / "conversations"  # macOS (old location)
        ]
        
        # Ollama database paths (SQLite database instead of files)
        ollama_db_paths = [
            home / "AppData" / "Local" / "Ollama" / "db.sqlite",  # Windows
            home / ".local" / "share" / "ollama" / "db.sqlite",  # Linux
            home / "Library" / "Application Support" / "Ollama" / "db.sqlite"  # macOS
        ]
        
        # Additional popular chat platforms
        perplexity_paths = [
            home / "AppData" / "Roaming" / "Perplexity" / "conversations",  # Windows
            home / ".config" / "perplexity" / "conversations",  # Linux
            home / "Library" / "Application Support" / "Perplexity" / "conversations"  # macOS
        ]
        
        jan_ai_paths = [
            home / "AppData" / "Roaming" / "Jan" / "conversations",  # Windows
            home / ".config" / "jan" / "conversations",  # Linux
            home / "Library" / "Application Support" / "Jan" / "conversations"  # macOS
        ]
        
        open_webui_paths = [
            home / ".open-webui" / "data" / "chats",  # All platforms
            home / "open-webui" / "data" / "chats",  # Alternative location
        ]
        
        # OpenWebUI database paths (SQLite database)
        open_webui_db_paths = [
            home / ".open-webui" / "data" / "webui.db",  # Default location
            home / "open-webui" / "data" / "webui.db",  # Alternative location
            home / "OpenWebUI" / "data" / "webui.db",  # Capitalized variant
            documents / "OpenWebUI" / "data" / "webui.db",  # Documents folder
            downloads / "OpenWebUI" / "data" / "webui.db",  # Downloads folder
        ]
        
        # Text generation WebUI paths  
        text_gen_webui_paths = [
            home / "text-generation-webui" / "logs",
            home / "text-generation-webui" / "characters",
            home / "Documents" / "text-generation-webui" / "logs"
        ]
        
        # SillyTavern paths (requested by Reddit community)
        sillytavern_paths = [
            home / "SillyTavern" / "data" / "chats",  # Default installation
            home / "AppData" / "Roaming" / "SillyTavern" / "chats",  # Windows
            home / ".config" / "sillytavern" / "chats",  # Linux
            home / "Library" / "Application Support" / "SillyTavern" / "chats",  # macOS
            documents / "SillyTavern" / "chats",  # User documents
            downloads / "SillyTavern" / "data" / "chats"  # Downloaded version
        ]
        
        # Gemini CLI paths (requested by Reddit community)
        gemini_cli_paths = [
            home / ".gemini" / "conversations",  # Linux/macOS
            home / "AppData" / "Roaming" / "gemini-cli" / "conversations",  # Windows
            home / ".config" / "gemini" / "conversations",  # Linux alternative
            home / "Library" / "Application Support" / "Gemini" / "conversations"  # macOS
        ]
        
        # VS Code workspace storage directories
        vscode_base_paths = [
            home / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage",  # Windows
            home / ".config" / "Code" / "User" / "workspaceStorage",  # Linux
            home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"  # macOS
        ]
        
        # Helper function to add paths with logging
        def add_paths_if_exist(paths: List[Path], app_name: str):
            for path in paths:
                if path.exists():
                    directories.append(str(path))
                    logger.info(f"Found {app_name} conversations: {path}")
        
        # Add paths for each application (ChatGPT and Claude removed - cloud-only)
        add_paths_if_exist(lm_studio_paths, "LM Studio")
        add_paths_if_exist(perplexity_paths, "Perplexity")
        add_paths_if_exist(jan_ai_paths, "Jan AI")
        add_paths_if_exist(open_webui_paths, "Open WebUI")
        add_paths_if_exist(text_gen_webui_paths, "Text Generation WebUI")
        add_paths_if_exist(sillytavern_paths, "SillyTavern")
        add_paths_if_exist(gemini_cli_paths, "Gemini CLI")
        
        # Special handling for Ollama database
        for db_path in ollama_db_paths:
            if db_path.exists():
                directories.append(str(db_path))
                logger.info(f"Found Ollama database: {db_path}")
        
        # Special handling for OpenWebUI database
        for db_path in open_webui_db_paths:
            if db_path.exists():
                directories.append(str(db_path))
                logger.info(f"Found OpenWebUI database: {db_path}")
        
        # Add VS Code workspace storage paths - find specific workspace hashes
        for vscode_base in vscode_base_paths:
            if vscode_base.exists():
                try:
                    # Look for workspace hashes (directories with chatSessions folders)
                    for workspace_hash in vscode_base.iterdir():
                        if workspace_hash.is_dir():
                            chat_sessions_dir = workspace_hash / "chatSessions"
                            if chat_sessions_dir.exists():
                                directories.append(str(chat_sessions_dir))
                                logger.info(f"Found VS Code chat sessions: {chat_sessions_dir}")
                except Exception as e:
                    logger.error(f"Error scanning VS Code workspace storage: {e}")
        
        return directories

    def _check_mcp_server(self) -> bool:
        """Check if an MCP server is running by attempting a connection.

        NOTE: The socket check is intentionally non-blocking (no timeout wait)
        so it does not stall the asyncio event loop when called from a coroutine.
        The result is cached for 60 seconds to minimise overhead.
        """
        # Only check every 60 seconds to avoid overhead
        current_time = time.time()
        if current_time - self.last_mcp_check < 60:
            return self.mcp_server_running

        try:
            # Use a non-blocking connect attempt instead of a blocking timeout so
            # the event loop is never stalled for up to 1 second.
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            err = sock.connect_ex(("localhost", self.mcp_port))
            sock.close()
            # 0 = connected immediately (port open), EINPROGRESS/EWOULDBLOCK = connecting
            import errno
            self.mcp_server_running = err in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EAGAIN)
        except Exception:
            self.mcp_server_running = False

        self.last_mcp_check = current_time
        return self.mcp_server_running
        
    async def _is_message_in_mcp(self, msg_hash: str) -> bool:
        """Check if a message was manually stored through MCP server.
        
        Args:
            msg_hash: Hash of the message content to check
            
        Returns:
            bool: True if message exists in MCP storage, False otherwise
        """
        try:
            # Connect to MCP server
            reader, writer = await asyncio.open_connection('localhost', self.mcp_port)
            
            # Send check request
            request = json.dumps({
                'type': 'check_message',
                'hash': msg_hash
            }).encode() + b'\n'
            writer.write(request)
            await writer.drain()
            
            # Get response
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            # Parse response
            result = json.loads(response.decode())
            return result.get('exists', False)
            
        except Exception as e:
            logger.debug(f"Failed to check message in MCP: {e}")
            return False  # If check fails, assume message doesn't exist
    
    def _get_mcp_start_time(self) -> Optional[datetime]:
        """Get the start time of the MCP server if running.
        
        Returns:
            Optional[datetime]: Server start time if available, None otherwise
        """
        if not self._check_mcp_server():
            return None
            
        try:
            # Use asyncio.to_thread-friendly blocking socket instead of the
            # 1-second-blocking socket.create_connection.
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)  # very short timeout — fire-and-forget check
            sock.connect(("localhost", self.mcp_port))
            sock.sendall(b"GET_START_TIME\n")
            response = sock.recv(1024).decode().strip()
            sock.close()
            if response and response != "ERROR":
                return datetime.fromisoformat(response)
        except Exception as e:
            logger.debug(f"Failed to get MCP start time: {e}")
        return None

    async def start_monitoring(self):
        """Start monitoring conversation files"""
        if not self.watch_directories:
            logger.info("No watch directories specified for file monitoring")
            return
            
        # Store reference to the current event loop
        self.loop = asyncio.get_running_loop()
        
        self.observer = Observer()
        
        for directory in self.watch_directories:
            if os.path.exists(directory):
                
                class ConversationFileHandler(FileSystemEventHandler):
                    def __init__(self, monitor):
                        self.monitor = monitor
                    
                    def on_modified(self, event):
                        if not event.is_directory:
                            try:
                                # Get the event loop from the main thread
                                loop = self.monitor.loop
                                if loop and loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        self.monitor._process_file_change(event.src_path), 
                                        loop
                                    )
                            except Exception as e:
                                print(f"Error scheduling file change processing: {e}")
                    
                    def on_created(self, event):
                        if not event.is_directory:
                            try:
                                # Get the event loop from the main thread
                                loop = self.monitor.loop
                                if loop and loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        self.monitor._process_file_change(event.src_path), 
                                        loop
                                    )
                            except Exception as e:
                                print(f"Error scheduling file change processing: {e}")
                
                handler = ConversationFileHandler(self)
                self.observer.schedule(handler, directory, recursive=True)
                logger.info(f"Started monitoring directory: {directory}")
        
        self.observer.start()
        logger.info("File monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring conversation files"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("File monitoring stopped")
    
    def add_watch_directory(self, directory: str):
        """Add a directory to monitor"""
        if directory not in self.watch_directories:
            self.watch_directories.append(directory)
            logger.info(f"Added watch directory: {directory}")
    
    async def _process_file_change(self, file_path: str):
        """Process a changed conversation file with MCP-aware deduplication"""
        try:
            # Check if file is a conversation file (JSON, txt, etc.)
            if not any(file_path.endswith(ext) for ext in ['.json', '.txt', '.md', '.log']):
                return
            
            # Calculate file hash to detect actual content changes
            file_content = await asyncio.to_thread(Path(file_path).read_bytes)
            current_hash = hashlib.md5(file_content).hexdigest()
            
            # Skip if we've already processed this exact content
            if file_path in self.file_hashes and self.file_hashes[file_path] == current_hash:
                return
                
            self.file_hashes[file_path] = current_hash
            
            # Initialize message tracking for this file if needed
            if file_path not in self.processed_messages:
                self.processed_messages[file_path] = set()
            
            # Read and parse conversation content
            conversations = await self._extract_conversations(file_path)
            
            # Check with MCP server for manually stored messages
            if self._check_mcp_server():
                try:
                    filtered_conversations = []
                    for conv in conversations:
                        # Create a hash of the message content and metadata
                        msg_hash = hashlib.md5(
                            f"{conv['role']}:{conv['content']}".encode()
                        ).hexdigest()
                        
                        # Check if this exact message was manually stored
                        if not await self._is_message_in_mcp(msg_hash):
                            filtered_conversations.append(conv)
                    conversations = filtered_conversations
                except Exception as e:
                    logger.debug(f"Failed to check MCP messages: {e}")
                    # If we can't check MCP server, process all messages
            
            # For VS Code chat files, handle development conversations
            is_vscode_chat = 'vscode' in file_path.lower() or 'chatsessions' in file_path.lower()
            if is_vscode_chat:
                # Create development session
                dev_session_id = await self.memory_system.vscode_db.save_development_session(
                    workspace_path=os.path.dirname(file_path),
                    session_summary=f"Imported VS Code chat session from {os.path.basename(file_path)}"
                )
                full_conversation = []
            
            # Store conversations in database
            for conv in conversations:
                result = await self.memory_system.store_conversation(
                    content=conv['content'],
                    role=conv['role'],
                    metadata={'source_file': file_path, 'imported_at': get_current_timestamp()},
                    session_id=current_hash  # Use file hash as session ID for grouping
                )
                
                if is_vscode_chat and not result.get("duplicate", False):
                    # Add to development conversation
                    full_conversation.append(f"{conv['role'].title()}: {conv['content']}")
            
            # Store development conversation if this is a VS Code chat
            if is_vscode_chat and full_conversation:
                await self.memory_system.vscode_db.store_development_conversation(
                    content="\n\n".join(full_conversation),
                    session_id=dev_session_id,
                    chat_context_id=self._get_file_hash(file_path)
                )
            
            logger.info(f"Imported {len(conversations)} conversations from {file_path}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash of file content for duplicate detection"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return str(hash(file_path))
    
    async def _extract_conversations(self, file_path: str) -> List[Dict]:
        """Extract conversations from various file formats with timestamps, using registry-based extensibility and robust deduplication"""
        conversations = []
        try:
            # Special handling for Ollama SQLite database
            if file_path.lower().endswith('db.sqlite') and 'ollama' in file_path.lower():
                conversations.extend(await asyncio.to_thread(self._extract_ollama_database, file_path))
                return conversations
            
            # Special handling for OpenWebUI SQLite database
            if (file_path.lower().endswith('webui.db') or 
                (file_path.lower().endswith('.db') and 'openwebui' in file_path.lower()) or
                (file_path.lower().endswith('.db') and 'open-webui' in file_path.lower())):
                conversations.extend(await asyncio.to_thread(self._extract_openwebui_database, file_path))
                return conversations
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            fallback_time = datetime.fromtimestamp(
                os.path.getmtime(file_path),
                timezone.utc
            ).isoformat()

            # Registry of format handlers: (predicate, handler)
            format_handlers = [
                (lambda fn, _: fn.endswith('.json'), self._handle_json_formats),
                (lambda fn, _: fn.endswith(('.txt', '.md', '.log')), self._parse_text_format),
            ]

            handled = False
            for predicate, handler in format_handlers:
                if predicate(file_path, content):
                    if handler == self._handle_json_formats:
                        conversations.extend(handler(content))
                    else:
                        conversations.extend(handler(content))
                    handled = True
                    break

            if not handled:
                logger.warning(f"No format handler found for {file_path}")

            # Ensure all conversations have timestamps
            for conv in conversations:
                if 'timestamp' not in conv or not conv['timestamp']:
                    conv['timestamp'] = fallback_time

            # Robust deduplication: by id (if present), timestamp (if present), and content hash
            seen = set()
            deduped = []
            for conv in conversations:
                # Use id if present, else None
                cid = conv.get('id') or conv.get('message_id') or None
                ts = conv.get('timestamp') or None
                content_hash = hashlib.md5(conv.get('content', '').encode('utf-8')).hexdigest()
                dedup_key = (cid, ts, content_hash)
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    deduped.append(conv)
            return deduped
        except Exception as e:
            logger.error(f"Error extracting conversations from {file_path}: {e}")
            return []

    def _handle_json_formats(self, content: str) -> List[Dict]:
        """Handle all supported JSON conversation formats (add new ones here)"""
        conversations = []
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                if self._is_lmstudio_format(data):
                    conversations.extend(self._parse_lmstudio_format(data))
                elif ('messages' in data or 'chat' in data) and self._is_sillytavern_format(data):
                    conversations.extend(self._parse_sillytavern_format(data))
                elif ('conversation' in data or ('messages' in data and self._is_gemini_cli_format(data))):
                    conversations.extend(self._parse_gemini_cli_format(data))
            elif isinstance(data, list):
                conversations.extend(self._parse_simple_array(data))
        except Exception as e:
            logger.error(f"Error handling JSON formats: {e}")
        return conversations
    
    def _parse_simple_array(self, data: List) -> List[Dict]:
        """Parse simple conversation array format with timestamps"""
        conversations = []
        
        for item in data:
            if isinstance(item, dict) and 'content' in item:
                # Look for timestamp in various formats
                timestamp = None
                for key in ['timestamp', 'time', 'created_at', 'date']:
                    if key in item:
                        try:
                            # Handle both ISO format strings and Unix timestamps
                            if isinstance(item[key], (int, float)):
                                timestamp = datetime.fromtimestamp(item[key], timezone.utc).isoformat()
                            else:
                                timestamp = datetime.fromisoformat(str(item[key])).isoformat()
                            break
                        except (ValueError, TypeError):
                            continue
                
                conversations.append({
                    'role': item.get('role', 'user'),
                    'content': str(item['content']),
                    'timestamp': timestamp
                })
        
        return conversations
    
    def _is_lmstudio_format(self, data: Dict) -> bool:
        """Check if data is in LM Studio format (has messages with versions structure)"""
        try:
            messages = data.get('messages', [])
            if not messages:
                return False
            # Check if first message has the LM Studio structure
            first_msg = messages[0] if isinstance(messages, list) else None
            return (isinstance(first_msg, dict) and 
                    'versions' in first_msg and 
                    'currentlySelected' in first_msg)
        except:
            return False

    def _is_sillytavern_format(self, data: Dict) -> bool:
        """Check if data is in SillyTavern format"""
        if not isinstance(data, dict):
            return False
        
        # SillyTavern specific indicators
        if 'messages' in data:
            messages = data.get('messages', [])
            if isinstance(messages, list) and messages:
                first_msg = messages[0]
                if isinstance(first_msg, dict):
                    # SillyTavern specific fields
                    return 'is_user' in first_msg or 'mes' in first_msg or 'send_date' in first_msg
        
        # Alternative SillyTavern format
        if 'chat' in data:
            chat = data.get('chat', [])
            if isinstance(chat, list) and chat:
                first_msg = chat[0]
                if isinstance(first_msg, dict):
                    return 'is_user' in first_msg or 'mes' in first_msg
        
        return False

    def _is_gemini_cli_format(self, data: Dict) -> bool:
        """Check if data is in Gemini CLI format"""
        if not isinstance(data, dict):
            return False
        
        # Gemini CLI specific structure
        if 'conversation' in data:
            return True
        
        # Check for Gemini-specific message format
        if 'messages' in data:
            messages = data.get('messages', [])
            if isinstance(messages, list) and messages:
                first_msg = messages[0]
                if isinstance(first_msg, dict):
                    # Gemini uses 'parts' array or 'model' role
                    return ('parts' in first_msg or 
                           first_msg.get('role') == 'model' or
                           'response' in first_msg)
        
        return False

    def _parse_lmstudio_format(self, data: Dict) -> List[Dict]:
        """Parse LM Studio conversation format with versions and complex content structure"""
        conversations = []
        try:
            messages = data.get('messages', [])
            conversation_timestamp = data.get('createdAt')
            base_timestamp = None
            
            if conversation_timestamp:
                try:
                    # LM Studio uses millisecond timestamps
                    base_timestamp = datetime.fromtimestamp(conversation_timestamp / 1000, timezone.utc)
                except (ValueError, TypeError):
                    pass
            
            for i, msg in enumerate(messages):
                if not isinstance(msg, dict) or 'versions' not in msg:
                    continue
                
                versions = msg.get('versions', [])
                current_version = msg.get('currentlySelected', 0)
                
                if 0 <= current_version < len(versions):
                    version = versions[current_version]
                    
                    role = version.get('role', 'unknown')
                    content_parts = version.get('content', [])
                    
                    # Extract text content from LM Studio's complex content structure
                    text_content = []
                    for part in content_parts:
                        if isinstance(part, dict):
                            if part.get('type') == 'text':
                                text_content.append(part.get('text', ''))
                            elif part.get('type') == 'file':
                                # Handle file attachments
                                file_info = f"[File: {part.get('fileIdentifier', 'unknown')}]"
                                text_content.append(file_info)
                        elif isinstance(part, str):
                            text_content.append(part)
                    
                    # For assistant messages, handle multi-step responses
                    if version.get('type') == 'multiStep' and 'steps' in version:
                        for step in version.get('steps', []):
                            if step.get('type') == 'contentBlock':
                                step_content = step.get('content', [])
                                for step_part in step_content:
                                    if isinstance(step_part, dict) and step_part.get('type') == 'text':
                                        text_content.append(step_part.get('text', ''))
                    
                    final_content = ' '.join(text_content).strip()
                    if final_content:
                        # Calculate approximate timestamp for each message
                        timestamp = None
                        if base_timestamp:
                            # Spread messages over time based on their position
                            message_time = base_timestamp + timedelta(minutes=i * 2)
                            timestamp = message_time.isoformat()
                        
                        conversations.append({
                            'role': role,
                            'content': final_content,
                            'timestamp': timestamp,
                            'metadata': {
                                'source': 'LM_Studio',
                                'model': data.get('lastUsedModel', {}).get('name', 'unknown'),
                                'conversation_name': data.get('name', 'Unknown'),
                                'version_index': current_version,
                                'message_index': i
                            }
                        })
        except Exception as e:
            logger.error(f"Error parsing LM Studio format: {e}")
        
        return conversations
    
    def _extract_ollama_database(self, db_path: str) -> List[Dict]:
        """Extract conversations from Ollama SQLite database."""
        conversations = []
        try:
            import sqlite3
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all chats with their messages
            cursor.execute("""
                SELECT c.id, c.title, c.created_at,
                       m.role, m.content, m.model_name, m.created_at as message_created_at
                FROM chats c
                LEFT JOIN messages m ON c.id = m.chat_id
                ORDER BY c.created_at, m.created_at
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                logger.debug(f"No conversations found in Ollama database: {db_path}")
                return conversations
            
            # Group messages by chat and convert to conversation format
            chats = {}
            for row in rows:
                chat_id, title, chat_created_at, role, content, model_name, msg_created_at = row
                
                if chat_id not in chats:
                    chats[chat_id] = {
                        'title': title,
                        'created_at': chat_created_at,
                        'messages': []
                    }
                
                if role and content:  # Only add if message exists
                    # Convert timestamp if needed
                    timestamp = None
                    if msg_created_at:
                        try:
                            # Parse ISO format timestamp
                            timestamp = datetime.fromisoformat(msg_created_at.replace('Z', '+00:00')).isoformat()
                        except (ValueError, TypeError):
                            pass
                    
                    conversations.append({
                        'role': role,
                        'content': content,
                        'timestamp': timestamp,
                        'metadata': {
                            'source': 'Ollama',
                            'model': model_name or 'unknown',
                            'chat_id': chat_id,
                            'chat_title': title
                        }
                    })
            
            logger.info(f"Extracted {len(conversations)} messages from {len(chats)} Ollama chats")
            
        except Exception as e:
            logger.error(f"Error extracting Ollama database {db_path}: {e}")
        
        return conversations
    
    def _extract_openwebui_database(self, db_path: str) -> List[Dict]:
        """Extract conversations from OpenWebUI SQLite database."""
        conversations = []
        try:
            import sqlite3
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all chats with their messages
            cursor.execute("""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       m.id as message_id, m.role, m.content, m.created_at as message_created_at
                FROM chat c
                LEFT JOIN message m ON c.id = m.chat_id
                ORDER BY c.created_at, m.created_at
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                logger.debug(f"No conversations found in OpenWebUI database: {db_path}")
                return conversations
            
            # Convert to conversation format
            for row in rows:
                chat_id, title, chat_created_at, chat_updated_at, message_id, role, content, msg_created_at = row
                
                if role and content:  # Only add if message exists
                    # Convert timestamp if needed
                    timestamp = None
                    if msg_created_at:
                        try:
                            # Parse timestamp (OpenWebUI typically uses ISO format)
                            if isinstance(msg_created_at, (int, float)):
                                timestamp = datetime.fromtimestamp(msg_created_at).isoformat()
                            else:
                                timestamp = datetime.fromisoformat(str(msg_created_at).replace('Z', '+00:00')).isoformat()
                        except (ValueError, TypeError):
                            pass
                    
                    conversations.append({
                        'role': role,
                        'content': content,
                        'timestamp': timestamp,
                        'metadata': {
                            'source': 'OpenWebUI',
                            'chat_id': chat_id,
                            'chat_title': title or f'Chat {chat_id}',
                            'message_id': message_id
                        }
                    })
            
            logger.info(f"Extracted {len(conversations)} messages from OpenWebUI database")
            
        except Exception as e:
            logger.error(f"Error extracting OpenWebUI database {db_path}: {e}")
        
        return conversations
    
    def _parse_text_format(self, content: str) -> List[Dict]:
        """Parse text-based conversation formats with timestamp detection"""
        conversations = []
        lines = content.split('\n')
        
        current_role = 'user'
        current_content = []
        current_timestamp = None
        
        # Common timestamp patterns
        timestamp_patterns = [
            r'\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]',  # ISO format
            r'\[(\d{2}:\d{2}(?::\d{2})?)\]',  # Time only
            r'\[(\d{4}-\d{2}-\d{2})\]',  # Date only
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to extract timestamp
            for pattern in timestamp_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        ts = match.group(1)
                        # Handle time-only format by adding today's date
                        if re.match(r'\d{2}:\d{2}(?::\d{2})?$', ts):
                            ts = f"{datetime.now().date()}T{ts}"
                        current_timestamp = datetime.fromisoformat(ts).isoformat()
                        line = line[match.end():].strip()
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Detect role markers
            if line.lower().startswith(('user:', 'human:', 'me:')):
                if current_content:
                    conversations.append({
                        'role': current_role,
                        'content': '\n'.join(current_content),
                        'timestamp': current_timestamp
                    })
                    current_content = []
                current_role = 'user'
                content_part = line.split(':', 1)[1].strip() if ':' in line else line
                if content_part:
                    current_content.append(content_part)
                    
            elif line.lower().startswith(('assistant:', 'ai:', 'bot:', 'friday:')):
                if current_content:
                    conversations.append({
                        'role': current_role,
                        'content': '\n'.join(current_content)
                    })
                    current_content = []
                current_role = 'assistant'
                content_part = line.split(':', 1)[1].strip() if ':' in line else line
                if content_part:
                    current_content.append(content_part)
            else:
                current_content.append(line)
        
        # Add the last conversation
        if current_content:
            conversations.append({
                'role': current_role,
                'content': '\n'.join(current_content)
            })
        
        return conversations

    def _parse_sillytavern_format(self, data: Dict) -> List[Dict]:
        """Parse SillyTavern conversation format"""
        conversations = []
        
        try:
            # SillyTavern typically stores chats in nested format
            if 'messages' in data:
                for msg in data['messages']:
                    # SillyTavern message format
                    role = 'user' if msg.get('is_user', False) else 'assistant'
                    content = msg.get('mes', msg.get('message', ''))
                    timestamp = msg.get('send_date', msg.get('timestamp'))
                    
                    if content:
                        conversations.append({
                            'role': role,
                            'content': str(content),
                            'timestamp': self.parse_timestamp(timestamp),
                            'metadata': {'source_type': 'sillytavern'}
                        })
            
            # Alternative format for SillyTavern exports
            elif 'chat' in data and isinstance(data['chat'], list):
                for msg in data['chat']:
                    conversations.append({
                        'role': 'user' if msg.get('is_user') else 'assistant',
                        'content': str(msg.get('mes', '')),
                        'timestamp': self.parse_timestamp(msg.get('send_date')),
                        'metadata': {'source_type': 'sillytavern'}
                    })
                    
        except Exception as e:
            logger.warning(f"Error parsing SillyTavern format: {e}")
        
        return conversations

    def _parse_gemini_cli_format(self, data: Dict) -> List[Dict]:
        """Parse Gemini CLI conversation format"""
        conversations = []
        
        try:
            # Gemini CLI format (assuming similar to other CLI tools)
            if 'conversation' in data and isinstance(data['conversation'], list):
                for turn in data['conversation']:
                    # User input
                    if 'input' in turn:
                        conversations.append({
                            'role': 'user',
                            'content': str(turn['input']),
                            'timestamp': self.parse_timestamp(turn.get('timestamp')),
                            'metadata': {'source_type': 'gemini_cli'}
                        })
                    
                    # Assistant response
                    if 'response' in turn:
                        conversations.append({
                            'role': 'assistant',
                            'content': str(turn['response']),
                            'timestamp': self.parse_timestamp(turn.get('timestamp')),
                            'metadata': {'source_type': 'gemini_cli'}
                        })
            
            # Alternative format with messages array
            elif 'messages' in data:
                for msg in data['messages']:
                    role = msg.get('role', 'user')
                    if role == 'model':  # Gemini uses 'model' instead of 'assistant'
                        role = 'assistant'
                    
                    content = ''
                    if 'parts' in msg and isinstance(msg['parts'], list):
                        # Gemini format with parts array
                        content = ' '.join(str(part.get('text', part)) for part in msg['parts'])
                    else:
                        content = str(msg.get('content', msg.get('text', '')))
                    
                    if content:
                        conversations.append({
                            'role': role,
                            'content': content,
                            'timestamp': self.parse_timestamp(msg.get('timestamp')),
                            'metadata': {'source_type': 'gemini_cli'}
                        })
                        
        except Exception as e:
            logger.warning(f"Error parsing Gemini CLI format: {e}")
        
        return conversations


class EmbeddingService:
    """Intelligent embedding service that preserves existing embeddings while optimizing for quality"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize embedding service with intelligent configuration
        
        Args:
            config: Optional configuration dictionary. If None, loads from embedding_config.json
        """
        if config:
            self.primary_config = config
            self.fallback_config = config.get("fallback", {})
            self.full_config = {"primary": config, "fallback": self.fallback_config}
        else:
            self.full_config = self._load_full_config()
            self.primary_config = self.full_config.get("primary", {})
            self.fallback_config = self.full_config.get("fallback", {})

        self.embeddings_endpoint = self._build_embeddings_endpoint(self.primary_config)

        # Shared aiohttp session — created lazily on first use, reused across all
        # embedding calls so each generate_embedding() doesn't open a new TCP connection.
        self._session: Optional["aiohttp.ClientSession"] = None

        # Semaphore: at most 2 concurrent embedding requests to avoid overwhelming
        # LM Studio when many background tasks fire simultaneously (e.g. bulk create_memory).
        # Created lazily in generate_embedding() because __init__ may run before the loop.
        self._embed_semaphore: Optional[asyncio.Semaphore] = None

        self.provider_availability = {
            "lm_studio": None,  # Will be tested on first use
            "ollama": None,
            "openai": None,
            "llama_cpp": None,
            "custom": None,
        }
        
        # Log configuration
        print("Intelligent Embedding Service Configuration")
        primary_provider = self.primary_config.get('provider', 'llama_cpp')
        primary_model = self.primary_config.get('model', 'qwen3-embedding-4b-q8_0.gguf')
        fallback_provider = self.fallback_config.get('provider', 'ollama')
        fallback_model = self.fallback_config.get('model', 'nomic-embed-text')
        
        print(f"Primary: {primary_provider} ({primary_model})")
        print(f"Fallback: {fallback_provider} ({fallback_model})")
        print(f"Preserving existing 768D embeddings, using best available for new ones")
        print("To customize, edit embedding_config.json in the project directory")

    def _build_embeddings_endpoint(self, config: Dict[str, Any]) -> str:
        """Build the effective embeddings endpoint for health checks and diagnostics."""
        provider = config.get("provider", "llama_cpp")
        base_url = config.get("base_url", "http://localhost:1234").rstrip("/")
        if provider == "ollama":
            return f"{base_url}/api/embeddings"
        return f"{base_url}/v1/embeddings"
    
    @property
    def config(self) -> Dict[str, Any]:
        """Backward compatibility property - returns primary config as expected format"""
        return {
            "provider": self.primary_config.get("provider"),
            "model": self.primary_config.get("model"),
            "base_url": self.primary_config.get("base_url"),
            "api_key": self.primary_config.get("api_key"),
            "embeddings_endpoint": self.embeddings_endpoint,
            "fallback_provider": self.fallback_config.get("provider"),
            "fallback_model": self.fallback_config.get("model"),
            "fallback_base_url": self.fallback_config.get("base_url"),
            "fallback_api_key": self.fallback_config.get("api_key")
        }
    
    def _load_full_config(self) -> dict:
        """Load complete embedding configuration from JSON file"""
        try:
            config_path = Path(__file__).parent / "embedding_config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    return config_data.get("embedding_configuration", {})
        except Exception as e:
            logger.warning(f"Failed to load embedding config: {e}, using defaults")
        
        # Return default configuration
        return {
            "primary": {
                "provider": "llama_cpp",
                "model": "qwen3-embedding-4b-q8_0.gguf",
                "base_url": "http://localhost:1234",
                "description": "Local llama.cpp embeddings server using Qwen3-Embedding-4B-Q8_0-GGUF"
            },
            "fallback": {
                "provider": "ollama",
                "model": "nomic-embed-text", 
                "base_url": "http://localhost:11434",
                "description": "Fast local Ollama embeddings"
            }
        }
    
    @classmethod
    def create_with_user_config(cls) -> 'EmbeddingService':
        """Create embedding service with user configuration prompt"""
        try:
            print("[Embedding Service Configuration]")
            print("Loading configuration from embedding_config.json...")
            return cls()  # Use config file
            
        except Exception as e:
            logger.warning(f"Failed to get user config, using defaults: {e}")
            return cls()  # Fallback to defaults

    # Default timeout for embedding HTTP requests: 30s total, 5s connect.
    # Prevents infinite freeze when LM Studio is busy loading a model or saturated.
    _SESSION_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5)

    async def _get_session(self) -> "aiohttp.ClientSession":
        """Return the shared aiohttp session, creating it lazily on first call."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._SESSION_TIMEOUT)
        return self._session

    async def close(self) -> None:
        """Close the shared HTTP session. Call when shutting down."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def generate_embedding(self, text: str, model: str = None) -> List[float]:
        """Generate embedding using intelligent provider selection with preservation strategy.

        A semaphore (max 2 concurrent) limits parallel requests to LM Studio so a burst
        of background embed tasks doesn't cascade into timeouts across all workspaces.
        """
        # Lazy semaphore init — must happen inside a running event loop
        if self._embed_semaphore is None:
            self._embed_semaphore = asyncio.Semaphore(2)

        async with self._embed_semaphore:
            return await self._generate_embedding_inner(text, model)

    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a *search query* using the model's instruction prefix.

        Qwen3-Embedding was trained asymmetrically:
          - Documents are embedded as-is (or with our compact contextual prefix).
          - Queries benefit from a task instruction prefix of the form:
              ``Instruct: {task}\\nQuery:{query}``
        Without this prefix the model cannot distinguish a paraphrased query from an
        unrelated passage, causing ~5-15% Top-1 regression on extreme paraphrase sets.

        The instruction is read from ``embedding_config.json`` → primary.query_instruction.
        If not configured (or empty string), falls back to plain generate_embedding() so
        models that are not instruction-aware are unaffected.
        """
        instruction = self.primary_config.get("query_instruction", "").strip()
        if instruction:
            # Official Qwen3-Embedding format: no space after "Query:"
            instructed_text = f"Instruct: {instruction}\nQuery:{query}"
        else:
            instructed_text = query

        if self._embed_semaphore is None:
            self._embed_semaphore = asyncio.Semaphore(2)

        async with self._embed_semaphore:
            return await self._generate_embedding_inner(instructed_text)

    async def generate_document_embedding(self, text: str) -> List[float]:
        """Generate embedding for a *stored document/memory* with optional instruction prefix.

        Companion to generate_query_embedding() for the document side of asymmetric
        retrieval.  When ``document_instruction`` is set in embedding_config.json the
        text is wrapped as:
            ``Instruct: {instruction}\\nDocument:{text}``

        This helps instruction-aware models (e.g. Qwen3-Embedding) understand that
        stored memories contain specific technical names and implementation details
        which should be matched against more abstract queries.  Falls back to plain
        generate_embedding() when document_instruction is absent so models that are
        not instruction-aware are unaffected.
        """
        instruction = self.primary_config.get("document_instruction", "").strip()
        if instruction:
            instructed_text = f"Instruct: {instruction}\nDocument:{text}"
        else:
            instructed_text = text

        if self._embed_semaphore is None:
            self._embed_semaphore = asyncio.Semaphore(2)

        async with self._embed_semaphore:
            return await self._generate_embedding_inner(instructed_text)

    async def _generate_embedding_inner(self, text: str, model: str = None) -> List[float]:
        """Internal: generate embedding (called under semaphore)."""
        # Try primary provider first
        primary_provider = self.primary_config.get("provider", "llama_cpp")
        self.embeddings_endpoint = self._build_embeddings_endpoint(self.primary_config)
        
        try:
            if primary_provider in {"lm_studio", "llama_cpp", "custom"}:
                result = await self._generate_lm_studio_embedding(text)
                if result:
                    self.provider_availability[primary_provider] = True
                    return result
                else:
                    self.provider_availability[primary_provider] = False
                    logger.warning(f"{primary_provider} unavailable, trying fallback")
                    
            elif primary_provider == "ollama":
                result = await self._generate_ollama_embedding(text)
                if result:
                    self.provider_availability["ollama"] = True
                    return result
                else:
                    self.provider_availability["ollama"] = False
                    logger.warning("Ollama unavailable, trying fallback")
                    
            elif primary_provider == "openai":
                result = await self._generate_openai_embedding(text)
                if result:
                    self.provider_availability["openai"] = True
                    return result
                else:
                    self.provider_availability["openai"] = False
                    logger.warning("OpenAI unavailable, trying fallback")
                    
        except Exception as e:
            logger.warning(f"Primary provider {primary_provider} failed: {e}")
        
        # Try fallback provider
        fallback_provider = self.fallback_config.get("provider")
        if fallback_provider and fallback_provider != primary_provider:
            try:
                if fallback_provider in {"lm_studio", "llama_cpp", "custom"}:
                    self.embeddings_endpoint = self._build_embeddings_endpoint(self.fallback_config)
                    result = await self._generate_lm_studio_embedding(text, fallback=True)
                    if result:
                        self.provider_availability[fallback_provider] = True
                        logger.info(f"Using {fallback_provider} fallback for embedding")
                        return result
                        
                elif fallback_provider == "ollama":
                    result = await self._generate_ollama_embedding(text, fallback=True)
                    if result:
                        self.provider_availability["ollama"] = True
                        logger.info("Using Ollama fallback for embedding")
                        return result
                        
                elif fallback_provider == "openai":
                    result = await self._generate_openai_embedding(text, fallback=True)
                    if result:
                        self.provider_availability["openai"] = True
                        logger.info("Using OpenAI fallback for embedding")
                        return result
                        
            except Exception as e:
                logger.error(f"Fallback provider {fallback_provider} also failed: {e}")
        
        # If both primary and fallback fail, log the issue
        logger.error("All embedding providers failed - semantic search will be unavailable")
        return []

    async def _generate_openai_compatible_embedding(self, text: str, config: Dict[str, Any], provider_name: str) -> List[float]:
        """Generate embedding using an OpenAI-compatible /v1/embeddings endpoint.

        Passes ``add_special_tokens: true`` to llama-server / LM Studio so that
        the tokenizer wraps each input with the model's BOS and EOS tokens
        (Qwen3:  <|im_start|> … <|im_end|>).  Without this flag llama.cpp emits
        a SEP/EOS warning and produces slightly open-ended vectors that are more
        prone to colliding with semantically adjacent documents.

        The flag is a llama.cpp extension to the OpenAI spec; pure OpenAI or
        other providers silently ignore it, so it is safe to always include.
        """
        base_url = config.get("base_url", "http://localhost:1234").rstrip("/")
        model = config.get("model", "qwen3-embedding-4b-q8_0.gguf")
        headers = {}

        api_key = config.get("api_key")
        if api_key and api_key not in {"", "lm_studio", "llama_cpp"}:
            headers["Authorization"] = f"Bearer {api_key}"

        self.embeddings_endpoint = f"{base_url}/v1/embeddings"

        # add_special_tokens: true → tokenizer adds BOS + EOS around each input.
        # Default True for local providers; can be overridden per-provider in
        # embedding_config.json via  "add_special_tokens": false.
        add_special_tokens = config.get("add_special_tokens", True)

        try:
            session = await self._get_session()
            payload = {"model": model, "input": text, "add_special_tokens": add_special_tokens}
            async with session.post(self.embeddings_endpoint, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "data" in data and len(data["data"]) > 0:
                        embedding = data["data"][0].get("embedding")
                        if embedding:
                            return embedding
                    logger.error(f"Invalid {provider_name} response format: {data}")
                    return None

                error_text = await response.text()
                logger.error(f"{provider_name} API error {response.status}: {error_text}")
                return None
        except asyncio.CancelledError as e:
            logger.error(f"{provider_name} embedding error: {e}")
            return None
        except Exception as e:
            logger.error(f"{provider_name} embedding error: {e}")
            return None
    
    async def _generate_ollama_embedding(self, text: str, fallback: bool = False) -> List[float]:
        """Generate embedding using Ollama"""
        if fallback:
            config = self.fallback_config
        else:
            config = self.primary_config if self.primary_config.get("provider") == "ollama" else self.fallback_config
            
        base_url = config.get("base_url", "http://localhost:11434")
        model = config.get("model", "nomic-embed-text")
        self.embeddings_endpoint = f"{base_url.rstrip('/')}/api/embeddings"
        
        try:
            session = await self._get_session()
            payload = {"model": model, "prompt": text}
            async with session.post(self.embeddings_endpoint, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("embedding")
                else:
                    error_text = await response.text()
                    logger.error(f"Ollama API error {response.status}: {error_text}")
                    return None
        except asyncio.CancelledError as e:
            logger.error(f"Ollama embedding error: {e}")
            return None
        except Exception as e:
            logger.error(f"Ollama embedding error: {e}")
            return None
    
    async def _generate_lm_studio_embedding(self, text: str, fallback: bool = False) -> List[float]:
        """Generate embedding using any OpenAI-compatible local endpoint."""
        if fallback:
            config = self.fallback_config
        else:
            config = self.primary_config if self.primary_config.get("provider") in {"lm_studio", "llama_cpp", "custom"} else self.fallback_config

        provider_name = config.get("provider", "lm_studio")
        return await self._generate_openai_compatible_embedding(text, config, provider_name)
    
    async def _generate_openai_embedding(self, text: str, fallback: bool = False) -> List[float]:
        """Generate embedding using OpenAI"""
        if fallback:
            config = self.fallback_config
        else:
            config = self.primary_config if self.primary_config.get("provider") == "openai" else self.fallback_config
            
        api_key = config.get("api_key")
        if not api_key or api_key == "your-openai-api-key-here":
            logger.error("OpenAI API key not configured")
            return None
            
        model = config.get("model", "text-embedding-3-small")
        
        try:
            session = await self._get_session()
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"model": model, "input": text}
            async with session.post("https://api.openai.com/v1/embeddings",
                                    json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "data" in data and len(data["data"]) > 0:
                        return data["data"][0].get("embedding")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error {response.status}: {error_text}")
                    return None
        except asyncio.CancelledError as e:
            logger.error(f"OpenAI embedding error: {e}")
            return None
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return None


class RerankingService:
    """Optional reranking service abstraction kept separate from first-stage retrieval."""

    # Shared timeout for all rerank HTTP requests — matches EmbeddingService.
    _SESSION_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5)

    def __init__(self, config: Dict[str, Any] = None):
        self._session: Optional["aiohttp.ClientSession"] = None
        if config:
            self.primary_config = config
            self.fallback_config = config.get("fallback", {})
            self.full_config = {"primary": config, "fallback": self.fallback_config}
        else:
            self.full_config = self._load_full_config()
            self.primary_config = self.full_config.get("primary", {})
            self.fallback_config = self.full_config.get("fallback", {})

        self.rerank_endpoint = self._build_rerank_endpoint(self.primary_config)
        self.provider_availability = {
            "llama_cpp": None,
            "custom": None,
            "cohere": None,
            "jina": None,
        }
        self.provider_retry_after = {}
        self.last_reranking_latency_ms = 0.0
        self.last_candidate_count = 0
        self.last_reranking_applied = False
        self._generative_reranker_detected = False

        print("Reranking Service Configuration")
        print(
            f"Primary: {self.primary_config.get('provider', 'disabled')} "
            f"({self.primary_config.get('model', 'none')})"
        )
        print(f"Enabled: {self.primary_config.get('enabled', False)}")

    def _load_full_config(self) -> dict:
        """Load complete reranking configuration from the shared JSON file."""
        try:
            config_path = Path(__file__).parent / "embedding_config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    return config_data.get("reranking_configuration", {})
        except Exception as e:
            logger.warning(f"Failed to load reranking config: {e}, using defaults")

        return {
            "primary": {
                "enabled": False,
                "provider": "llama_cpp",
                "model": "Qwen.Qwen3-Reranker-4B.Q4_K_S.gguf",
                "base_url": "http://localhost:8080",
                "rerank_path": "/rerank",
                "description": "Local GGUF reranker endpoint"
            },
            "fallback": {}
        }

    @classmethod
    def create_with_user_config(cls) -> 'RerankingService':
        """Create reranking service with config file defaults."""
        return cls()

    async def _get_session(self) -> "aiohttp.ClientSession":
        """Return the shared aiohttp session, creating it lazily on first call."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._SESSION_TIMEOUT)
        return self._session

    async def close(self) -> None:
        """Close the shared HTTP session. Call on shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _build_rerank_endpoint(self, config: Dict[str, Any]) -> str:
        """Build the effective rerank endpoint for diagnostics and requests."""
        custom_endpoint = config.get("rerank_endpoint")
        if custom_endpoint:
            return custom_endpoint.rstrip("/")

        base_url = config.get("base_url", "http://localhost:8080").rstrip("/")
        rerank_path = config.get("rerank_path", "/rerank")
        if not rerank_path.startswith("/"):
            rerank_path = f"/{rerank_path}"
        return f"{base_url}{rerank_path}"

    def is_enabled(self) -> bool:
        """Whether reranking is enabled in config."""
        return bool(self.primary_config.get("enabled", False))

    def get_candidate_limit(self, default: int = 30) -> int:
        """Return the configured bounded candidate count for production reranking."""
        try:
            value = int(self.primary_config.get("candidate_count", default))
        except (TypeError, ValueError):
            value = default
        return max(1, value)

    def get_final_result_count(self, default: int = 5) -> int:
        """Return the configured final top-N after reranking."""
        try:
            value = int(self.primary_config.get("final_top_n", default))
        except (TypeError, ValueError):
            value = default
        return max(1, value)

    def get_timeout_seconds(self, default: float = 5.0) -> float:
        """Return the configured reranking timeout for HTTP requests."""
        try:
            value = float(self.primary_config.get("timeout_seconds", default))
        except (TypeError, ValueError):
            value = default
        return max(0.5, value)

    def get_retry_cooldown_seconds(self, default: float = 30.0) -> float:
        """Return cooldown applied after reranker endpoint failures."""
        try:
            value = float(self.primary_config.get("unavailable_retry_seconds", default))
        except (TypeError, ValueError):
            value = default
        return max(1.0, value)

    def get_confidence_bypass_threshold(self) -> float:
        """Return the top-1 similarity score above which BGE reranking is skipped.

        When the highest-scoring candidate after semantic + lexical hybrid rescoring
        already exceeds this threshold, the result is considered high-confidence and
        the cross-encoder HTTP call (~1500ms) is bypassed entirely.

        Set to 1.1 in config to always rerank; set to 0.0 to disable the bypass.
        Default 0.92 is conservative: only very clean, unambiguous queries skip BGE.
        """
        try:
            value = float(self.primary_config.get("confidence_bypass_threshold", 0.92))
        except (TypeError, ValueError):
            value = 0.92
        return max(0.0, min(1.5, value))

    def _provider_is_in_cooldown(self, provider_name: str) -> bool:
        """Check whether failed provider should be skipped temporarily."""
        retry_after = self.provider_retry_after.get(provider_name, 0.0)
        return retry_after > time.time()

    def _mark_provider_unavailable(self, provider_name: str):
        """Record provider failure and defer the next network retry."""
        self.provider_availability[provider_name] = False
        self.provider_retry_after[provider_name] = time.time() + self.get_retry_cooldown_seconds()

    def _mark_provider_available(self, provider_name: str):
        """Clear provider cooldown after a successful rerank request."""
        self.provider_availability[provider_name] = True
        self.provider_retry_after.pop(provider_name, None)

    @property
    def config(self) -> Dict[str, Any]:
        """Expose current reranker configuration for diagnostics."""
        return {
            "enabled": self.primary_config.get("enabled", False),
            "provider": self.primary_config.get("provider"),
            "model": self.primary_config.get("model"),
            "base_url": self.primary_config.get("base_url"),
            "rerank_endpoint": self.rerank_endpoint,
            "fallback_provider": self.fallback_config.get("provider"),
            "fallback_model": self.fallback_config.get("model"),
            "last_reranking_latency_ms": self.last_reranking_latency_ms,
            "last_candidate_count": self.last_candidate_count,
            "last_reranking_applied": self.last_reranking_applied,
        }

    def _build_headers(self, config: Dict[str, Any]) -> Dict[str, str]:
        """Build auth headers for reranking providers when needed."""
        headers = {"Content-Type": "application/json"}
        api_key = config.get("api_key")
        if api_key and api_key not in {"", "your-api-key-here", "lm_studio", "llama_cpp"}:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _normalize_rerank_response(self, payload: Dict[str, Any], documents: List[str]) -> List[Dict[str, Any]]:
        """Normalize common rerank response shapes into a stable ranked list."""
        candidates = payload.get("results") or payload.get("data") or payload.get("rankings") or []
        if isinstance(payload, list):
            candidates = payload

        normalized_results = []
        for fallback_index, item in enumerate(candidates):
            if not isinstance(item, dict):
                continue
            index = item.get("index", item.get("document_index", fallback_index))
            if not isinstance(index, int) or index < 0 or index >= len(documents):
                continue

            score = item.get("relevance_score", item.get("score", item.get("relevance", 0.0)))
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0

            normalized_results.append(
                {
                    "index": index,
                    "relevance_score": score,
                    "document": documents[index],
                }
            )

        normalized_results.sort(key=lambda item: item["relevance_score"], reverse=True)
        return normalized_results

    async def _rerank_with_http_endpoint(
        self,
        query: str,
        documents: List[str],
        config: Dict[str, Any],
        provider_name: str,
        top_n: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Rerank documents against a generic JSON endpoint."""
        endpoint = self._build_rerank_endpoint(config)
        headers = self._build_headers(config)
        payload = {
            "model": config.get("model"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        started = time.perf_counter()
        try:
            timeout = aiohttp.ClientTimeout(total=self.get_timeout_seconds())
            session = await self._get_session()
            async with session.post(endpoint, json=payload, headers=headers, timeout=timeout) as response:
                self.last_reranking_latency_ms = (time.perf_counter() - started) * 1000
                self.last_candidate_count = len(documents)
                self.rerank_endpoint = endpoint

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"{provider_name} rerank API error {response.status}: {error_text}")
                    return None

                raw_text = await response.text()
                import json as _json
                payload = _json.loads(raw_text)
                # LM Studio returns HTTP 200 with {"error": "..."} for unsupported endpoints
                if isinstance(payload, dict) and "error" in payload and not any(
                    k in payload for k in ("results", "data", "rankings")
                ):
                    logger.error(f"{provider_name} rerank endpoint not supported: {payload['error']}")
                    return None
                normalized_results = self._normalize_rerank_response(payload, documents)
                if normalized_results:
                    return normalized_results[:top_n]

                logger.error(f"Invalid {provider_name} rerank response format: {payload}")
                return None
        except asyncio.CancelledError as e:
            logger.error(f"{provider_name} rerank request cancelled: {e}")
            return None
        except Exception as e:
            import traceback as _tb
            logger.error(f"{provider_name} rerank error [{type(e).__name__}]: {e}\n{_tb.format_exc()}")
            return None

    def _default_pass_through_ranking(self, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Return original ordering when reranking is unavailable or disabled."""
        self.last_reranking_applied = False
        limited_documents = documents[:top_n]
        return [
            {"index": index, "relevance_score": 0.0, "document": document}
            for index, document in enumerate(limited_documents)
        ]

    async def rerank_documents(self, query: str, documents: List[str], top_n: int = None) -> List[Dict[str, Any]]:
        """Rerank a candidate list using the configured provider, with graceful fallback."""
        if not documents:
            return []

        top_n = top_n or len(documents)
        if not self.is_enabled():
            return self._default_pass_through_ranking(documents, top_n)

        primary_provider = self.primary_config.get("provider", "llama_cpp")
        if self._generative_reranker_detected or self._provider_is_in_cooldown(primary_provider):
            return self._default_pass_through_ranking(documents, top_n)
        result = await self._rerank_with_http_endpoint(query, documents, self.primary_config, primary_provider, top_n)
        if result:
            max_score = max(r["relevance_score"] for r in result)
            # BGE-style rerankers return logits in range ~[-12, 12] — max can be negative.
            # Qwen3-generative rerankers via pooling=rank yield near-zero positive values
            # like 6e-24. Detect by checking absolute max < 1e-10 (catches only truly
            # near-zero positive floats, not meaningful negative logits).
            abs_max = max(abs(r["relevance_score"]) for r in result)
            if abs_max < 1e-10:
                # Generative reranker (e.g. Qwen3) served via pooling=rank yields
                # near-zero scores — ordering is not meaningful. Fall through to
                # lexical hybrid without marking the provider unavailable.
                self._generative_reranker_detected = True
                logger.warning(
                    f"{primary_provider} produced near-zero relevance scores "
                    f"(abs_max={abs_max:.2e}). Reranker may be a generative model "
                    f"incompatible with pooling=rank. Using lexical hybrid fallback "
                    f"for this session."
                )
                return self._default_pass_through_ranking(documents, top_n)
            self._mark_provider_available(primary_provider)
            self.last_reranking_applied = True
            return result

        self._mark_provider_unavailable(primary_provider)
        fallback_provider = self.fallback_config.get("provider")
        if fallback_provider and self.fallback_config.get("enabled", False):
            if self._provider_is_in_cooldown(fallback_provider):
                return self._default_pass_through_ranking(documents, top_n)
            result = await self._rerank_with_http_endpoint(query, documents, self.fallback_config, fallback_provider, top_n)
            if result:
                self._mark_provider_available(fallback_provider)
                self.last_reranking_applied = True
                return result
            self._mark_provider_unavailable(fallback_provider)

        return self._default_pass_through_ranking(documents, top_n)

    async def smoke_test(self) -> Dict[str, Any]:
        """Run a minimal reranking smoke test when enabled."""
        if not self.is_enabled():
            return {
                "status": "disabled",
                "enabled": False,
                "endpoint": self.rerank_endpoint,
            }

        sample_documents = [
            "Persistent memory configuration for embeddings and reranking.",
            "Appointment reminder and schedule entry.",
        ]
        results = await self.rerank_documents("embedding reranker configuration", sample_documents, top_n=2)
        return {
            "status": "healthy" if results else "unhealthy",
            "enabled": True,
            "endpoint": self.rerank_endpoint,
            "result_count": len(results),
            "last_reranking_latency_ms": round(self.last_reranking_latency_ms, 2),
        }


class PersistentAIMemorySystem:
    """Main memory system that coordinates all databases and operations - FULL FEATURED VERSION"""
    
    def __init__(self, settings=None, enable_file_monitoring: bool = None, 
                 watch_directories: List[str] = None):
        # Use provided settings or get global settings
        if settings is None:
            settings = get_settings()
        self.settings = settings
        self.data_dir = settings.data_dir
        # Expose memory_data_path for maintenance and other systems
        self.memory_data_path = Path(settings.data_dir)
        
        # Override file monitoring setting if explicitly provided
        if enable_file_monitoring is None:
            enable_file_monitoring = settings.enable_file_monitoring
        
        # Initialize all 5 databases using settings paths
        self.conversations_db = ConversationDatabase(db_path=str(settings.conversations_db_path))
        self.ai_memory_db = AIMemoryDatabase(db_path=str(settings.ai_memories_db_path))
        self.schedule_db = ScheduleDatabase(db_path=str(settings.schedule_db_path))
        self.vscode_db = VSCodeProjectDatabase(db_path=str(settings.vscode_db_path))
        self.mcp_db = MCPToolCallDatabase(db_path=str(settings.mcp_db_path))
        
        # Initialize embedding service with user-configurable options
        self.embedding_service = EmbeddingService.create_with_user_config()
        self.reranking_service = RerankingService.create_with_user_config()
        
        # ---------------------------------------------------------------------------
        # Sprint 8: In-session search cache (feature #4 — Semantic Query Cache)
        # key: frozenset of (query_text_key, database_filter, limit)
        # value: (embedding_vec, result_payload, timestamp)
        # Cleared on demand; max 32 entries (LRU-ish, FIFO eviction)
        # ---------------------------------------------------------------------------
        self._search_cache: dict = {}
        # _CACHE_MAX and cache eviction logic live inside the search function that uses it.

        # ---------------------------------------------------------------------------
        # Multi-workspace freeze prevention: cap the total number of *pending*
        # background embedding tasks.  Each workspace spawns its own Python process;
        # without a cap, a burst of write operations (or the file-monitor importing
        # history) can enqueue hundreds of concurrent embedding requests to LM Studio,
        # saturating the GPU and freezing the PC.
        # At most _BG_EMBED_MAX tasks wait in the background at any moment.
        # When the cap is reached, new embedding requests are dropped gracefully —
        # text-only search still works as fallback.
        # ---------------------------------------------------------------------------
        self._BG_EMBED_MAX = 6
        self._bg_embed_semaphore = asyncio.Semaphore(self._BG_EMBED_MAX)

        # ---------------------------------------------------------------------------
        # Sprint 8: Memory Consolidation threshold (feature #6)
        # Memories with cosine > this at write-time are flagged as near-duplicates
        # even if below the hard dedup threshold (0.92). Range: (dedup_thresh, 0.92)
        # ---------------------------------------------------------------------------
        self._consolidation_threshold: float = 0.82

        # Initialize file monitoring
        self.file_monitor = None
        if enable_file_monitoring:
            # Use watch_directories parameter or fall back to settings
            watch_dirs = watch_directories or settings.watch_directories
            self.file_monitor = ConversationFileMonitor(self, watch_dirs)
    
    async def start_file_monitoring(self):
        """Start monitoring conversation files"""
        if self.file_monitor:
            await self.file_monitor.start_monitoring()
            logger.info("File monitoring started")
    
    async def stop_file_monitoring(self):
        """Stop monitoring conversation files"""
        if self.file_monitor:
            await self.file_monitor.stop_monitoring()
            logger.info("File monitoring stopped")
    
    def add_watch_directory(self, directory: str):
        """Add a directory to monitor for conversation files"""
        if self.file_monitor:
            self.file_monitor.add_watch_directory(directory)

    def _schedule_bg_embed(self, coro) -> None:
        """Schedule a background embedding coroutine with a concurrency cap.

        Multiple VS Code workspaces each spawn their own MCP server process.  Each
        process can fire dozens of fire-and-forget embedding tasks (e.g. during file
        monitor imports).  Without a cap, these flood LM Studio and saturate the GPU.

        This method wraps `coro` in a guard that tries to acquire
        `_bg_embed_semaphore` (non-blocking).  If the semaphore is full (meaning
        _BG_EMBED_MAX tasks are already pending), the new embedding is **skipped**
        rather than queued — text-only search still works as a fallback.
        """
        async def _guarded():
            acquired = self._bg_embed_semaphore._value > 0  # fast check without blocking
            if not acquired:
                logger.debug("⏭️  Background embed skipped — cap of %d reached", self._BG_EMBED_MAX)
                return
            async with self._bg_embed_semaphore:
                await coro

        asyncio.create_task(_guarded())

    # =============================================================================
    # CONVERSATION OPERATIONS
    # =============================================================================
    
    async def store_conversation(self, content: str, role: str, session_id: str = None,
                               conversation_id: str = None, metadata: Dict = None) -> Dict:
        """Store a conversation message with automatic embedding generation"""
        
        result = await self.conversations_db.store_message(
            content, role, session_id, conversation_id, metadata
        )
        
        # Generate and store embedding asynchronously (cap enforced by _schedule_bg_embed)
        self._schedule_bg_embed(self._add_embedding_to_message(result["message_id"], content))
        
        return {
            "status": "success",
            "message_id": result["message_id"],
            "conversation_id": result["conversation_id"],
            "session_id": result["session_id"]
        }
    
    async def get_conversation_history(self, limit: int = 20, session_id: str = None) -> List[Dict]:
        """Get recent conversation history"""
        
        messages = await self.conversations_db.get_recent_messages(limit, session_id)
        return [dict(msg) for msg in messages]

    async def get_recent_context(self, limit: int = 10, session_id: str = None) -> Dict:
        """Retrieve recent conversation context, optionally filtered by session."""
        try:
            if session_id:
                query = """
                    SELECT m.*, c.session_id 
                    FROM messages m 
                    JOIN conversations c ON m.conversation_id = c.conversation_id
                    WHERE c.session_id = ?
                    ORDER BY m.timestamp DESC 
                    LIMIT ?
                """
                params = (session_id, limit)
            else:
                query = """
                    SELECT m.*, c.session_id 
                    FROM messages m 
                    JOIN conversations c ON m.conversation_id = c.conversation_id
                    ORDER BY m.timestamp DESC 
                    LIMIT ?
                """
                params = (limit,)

            rows = await self.conversations_db.execute_query(query, params)
            return {
                "status": "success",
                "recent_context": [dict(row) for row in rows]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    async def prime_context(self, topic: str = None, tags_include: List[str] = None) -> Dict:
        """Sprint 1 T3 / Sprint 2 T3 — Compound context bundle for session start.

        Executes in parallel:
          1. Top-5 high-importance memories (compact, min_importance=7)
             Uses optional `topic` to narrow the query (e.g. "NEMO dev sprint")
             Uses optional `tags_include` to restrict results to specific project tags.
          2. Active reminders (up to 3)
          3. Last session summary (most recent conversation timestamp + snippet)

        Returns a compressed bundle (~120 tokens) so the LLM has full working
        memory loaded in a single tool call with no planning overhead.
        """
        import asyncio as _asyncio

        async def _get_top_memories():
            try:
                base_query = "active projects recent decisions preferences"
                search_query = f"{topic} {base_query}" if topic else base_query
                result = await self.search_memories(
                    query=search_query,
                    limit=5,
                    min_importance=7,
                    compact=True,
                    tags_include=tags_include,
                )
                return result.get("results", [])
            except Exception:
                return []

        async def _get_reminders():
            try:
                reminders = await self.get_active_reminders(limit=3)
                if isinstance(reminders, list):
                    return [
                        f"[{r.get('priority_level','?')}] {r.get('content','')[:80]} — {(r.get('due_datetime') or '')[:10]}"
                        for r in reminders[:3]
                    ]
                return []
            except Exception:
                return []

        async def _get_last_session():
            try:
                # When a topic is provided, prefer a recent message that
                # mentions the topic so we don't surface another project's
                # last conversation as context.
                if topic:
                    topic_words = topic.split()[:3]  # use first 3 words max
                    conditions = " OR ".join(["LOWER(m.content) LIKE ?" for _ in topic_words])
                    topic_params = [f"%{w.lower()}%" for w in topic_words]
                    rows = await self.conversations_db.execute_query(
                        f"SELECT m.timestamp, m.content FROM messages m "
                        f"JOIN conversations c ON m.conversation_id = c.conversation_id "
                        f"WHERE ({conditions}) "
                        f"ORDER BY m.timestamp DESC LIMIT 1",
                        topic_params,
                    )
                    if not rows:
                        # No topic-specific message found — fall back to most recent
                        rows = await self.conversations_db.execute_query(
                            "SELECT m.timestamp, m.content FROM messages m "
                            "JOIN conversations c ON m.conversation_id = c.conversation_id "
                            "ORDER BY m.timestamp DESC LIMIT 1"
                        )
                else:
                    rows = await self.conversations_db.execute_query(
                        "SELECT m.timestamp, m.content FROM messages m "
                        "JOIN conversations c ON m.conversation_id = c.conversation_id "
                        "ORDER BY m.timestamp DESC LIMIT 1"
                    )
                if rows:
                    row = dict(rows[0])
                    ts = (row.get("timestamp") or "")[:10]
                    snippet = (row.get("content") or "")[:100]
                    return f"{ts}: {snippet}"
                return None
            except Exception:
                return None

        async def _get_session_stats():
            try:
                from datetime import timedelta
                now = datetime.now(get_local_timezone())
                week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
                rows = await self.ai_memory_db.execute_query(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN DATE(timestamp_created) >= ? THEN 1 ELSE 0 END) as recent_7d "
                    "FROM curated_memories WHERE importance_level > 0",
                    (week_ago,)
                )
                if rows:
                    r = dict(rows[0])
                    return {"total_memories": r.get("total", 0), "added_last_7d": r.get("recent_7d", 0)}
                return {}
            except Exception:
                return {}

        async def _get_intent_anchors():
            """Surface intent_anchor memories relevant to this topic."""
            try:
                if not topic:
                    return []
                result = await self.search_memories(
                    query=topic,
                    limit=3,
                    memory_type="intent_anchor",
                    compact=False,
                    tags_include=tags_include,
                )
                anchors = []
                for r in result.get("results", []):
                    data = r.get("data", {})
                    try:
                        parsed = json.loads(data.get("content", "{}"))
                        anchors.append({
                            "trigger": parsed.get("trigger", ""),
                            "action":  parsed.get("action", ""),
                            "id":      data.get("memory_id", "")[:8],
                        })
                    except Exception:
                        pass
                return anchors
            except Exception:
                return []

        memories, reminders, last_session, session_stats, intent_anchors = await _asyncio.gather(
            _get_top_memories(),
            _get_reminders(),
            _get_last_session(),
            _get_session_stats(),
            _get_intent_anchors(),
        )

        return {
            "status": "success",
            "primed_at": get_current_timestamp(),
            "memories": memories,
            "reminders": reminders,
            "last_session": last_session,
            "session_stats": session_stats,
            "intent_anchors": intent_anchors,
            "hint": "Context loaded. You may now answer or call search_memories(compact=true) for topic-specific retrieval.",
        }

    # =============================================================================
    # AI MEMORY OPERATIONS
    # =============================================================================
    
    async def create_memory(self, content: str, memory_type: str = None,
                          importance_level: int = 5, tags: List[str] = None,
                          source_conversation_id: str = None) -> Dict:
        """Create a curated AI memory with non-blocking embedding generation.

        The memory is inserted immediately so the caller gets an instant response.
        Embedding generation and semantic deduplication run in the background —
        avoiding the GPU/CPU spike from the embedding model blocking the event loop
        and freezing the host system during inference.

        Exact-text deduplication is still synchronous (cheap DB query) to prevent
        trivially identical entries before the background task runs.
        """
        # Fast exact-text dedup synchronously — no embedding needed
        existing = await self.ai_memory_db.execute_query(
            "SELECT memory_id FROM curated_memories WHERE content = ? AND memory_type IS ?",
            (content, memory_type)
        )
        if existing:
            return {
                "status": "deduplicated",
                "memory_id": existing[0]["memory_id"],
                "similarity": 1.0,
                "existing_content": content[:120],
                "message": "An identical memory already exists. No new entry was created."
            }

        # Insert immediately — user gets instant response
        memory_id = await self.ai_memory_db.create_memory(
            content, memory_type, importance_level, tags, source_conversation_id
        )

        # Embedding + semantic dedup run in background (non-blocking).
        # Use _schedule_bg_embed so the semaphore cap (_BG_EMBED_MAX) is respected
        # — raw asyncio.create_task() would bypass the cap and flood LM Studio.
        contextual_text = self._build_contextual_embedding_text(
            content, memory_type, importance_level, tags or []
        )
        self._schedule_bg_embed(
            self._background_embed_and_dedup(memory_id, content, contextual_text)
        )

        return {
            "status": "success",
            "memory_id": memory_id,
            "contextual_prefix": contextual_text[:80],
            "consolidation_warning": None,
        }

    async def _background_embed_and_dedup(
        self, memory_id: str, content: str, contextual_text: str
    ) -> None:
        """Background task: generate embedding, run semantic dedup, update or remove.

        Runs after create_memory returns so the caller is never blocked by
        embedding model inference. If a semantic duplicate is found the newly
        inserted memory is deleted to keep the corpus clean.
        """
        try:
            embedding = await self.embedding_service.generate_embedding(contextual_text)
            if not embedding:
                return

            new_vec = np.array(embedding, dtype=np.float32)
            new_norm = float(np.linalg.norm(new_vec))
            if new_norm == 0:
                return

            # Vectorized cosine similarity against all stored embeddings
            rows = await self.ai_memory_db.execute_query(
                "SELECT memory_id, content, embedding FROM curated_memories "
                "WHERE embedding IS NOT NULL AND memory_id != ?",
                (memory_id,)
            )

            best_sim = 0.0
            best_match = None
            if rows:
                # CPU-bound numpy ops — run off the event loop to avoid freezing.
                def _compute_best_match():
                    blobs = [r["embedding"] for r in rows]
                    matrix = np.vstack([np.frombuffer(b, dtype=np.float32) for b in blobs])
                    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                    norms = np.where(norms == 0, 1.0, norms)
                    sims = (matrix / norms) @ (new_vec / new_norm)
                    idx = int(np.argmax(sims))
                    return float(sims[idx]), idx
                best_sim, best_idx = await asyncio.to_thread(_compute_best_match)
                best_match = rows[best_idx]

            if best_sim >= 0.92 and best_match:
                # Semantic duplicate found — remove the just-inserted memory
                await self.ai_memory_db.execute_update(
                    "DELETE FROM curated_memories WHERE memory_id = ?",
                    (memory_id,)
                )
                logger.info(
                    f"Background dedup removed {memory_id} (sim={best_sim:.4f} "
                    f"vs {best_match['memory_id']})"
                )
                return

            # ------------------------------------------------------------------
            # Prediction Error Gating
            # If the new memory is semantically near (0.70 ≤ sim < 0.92) but
            # contains contradiction signals, supersede the old memory by tagging
            # it as outdated and boosting the new one's importance.
            # Contradiction signals: negation words adjacent to overlapping nouns,
            # or explicit update phrases ("ya no", "ahora", "cambiado", "corregido",
            # "actually", "instead", "no longer", "updated to", "changed to").
            # ------------------------------------------------------------------
            _CONTRADICTION_PHRASES = {
                "ya no", "ahora es", "cambiado a", "corregido", "en realidad",
                "actually", "instead", "no longer", "updated to", "changed to",
                "replaced by", "reemplazado por", "nuevo valor", "now is",
            }
            _CONTRADICTION_THRESHOLD_LOW = 0.70
            _CONTRADICTION_THRESHOLD_HIGH = 0.90

            if (best_match and _CONTRADICTION_THRESHOLD_LOW <= best_sim < _CONTRADICTION_THRESHOLD_HIGH):
                content_lower = content.lower()
                old_content_lower = (best_match["content"] or "").lower()
                has_contradiction = any(phrase in content_lower for phrase in _CONTRADICTION_PHRASES)
                if has_contradiction:
                    old_id = best_match["memory_id"]
                    # old content via direct index (sqlite3.Row doesn't support .get())
                    try:
                        _ = best_match["content"]
                    except Exception:
                        pass
                    logger.info(
                        f"Prediction Error Gating: new={memory_id} supersedes old={old_id} "
                        f"(sim={best_sim:.4f}, contradiction signal detected)"
                    )
                    # Mark old memory as superseded (lower importance, add tag)
                    old_tags_row = await self.ai_memory_db.execute_query(
                        "SELECT tags, importance_level FROM curated_memories WHERE memory_id = ?",
                        (old_id,)
                    )
                    if old_tags_row:
                        old_tags = json.loads(old_tags_row[0]["tags"]) if old_tags_row[0]["tags"] else []
                        if "superseded" not in old_tags:
                            old_tags.append("superseded")
                        new_imp = max(1, int(old_tags_row[0]["importance_level"] or 5) - 2)
                        await self.ai_memory_db.execute_update(
                            "UPDATE curated_memories SET tags=?, importance_level=?, timestamp_updated=? WHERE memory_id=?",
                            (json.dumps(old_tags), new_imp, get_current_timestamp(), old_id)
                        )
                    # Boost the new memory's importance slightly
                    await self.ai_memory_db.execute_update(
                        "UPDATE curated_memories SET importance_level = MIN(10, COALESCE(importance_level,5)+1) WHERE memory_id=?",
                        (memory_id,)
                    )

            # No duplicate — store the embedding
            embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
            await self.ai_memory_db.execute_update(
                "UPDATE curated_memories SET embedding = ? WHERE memory_id = ?",
                (embedding_blob, memory_id)
            )

            # Advisory consolidation warning (logged only — not surfaced to caller
            # since we're in background)
            if self._consolidation_threshold <= best_sim < 0.92 and best_match:
                logger.info(
                    f"Near-duplicate advisory: {memory_id} sim={best_sim:.4f} "
                    f"vs {best_match['memory_id']} — consider merging"
                )

            # Synaptic tagging: if this memory is high-importance (≥9),
            # propagate importance boost to semantically related memories.
            imp_rows = await self.ai_memory_db.execute_query(
                "SELECT importance_level FROM curated_memories WHERE memory_id = ?",
                (memory_id,)
            )
            if imp_rows and int(imp_rows[0]["importance_level"] or 0) >= 9:
                asyncio.create_task(
                    self.synaptic_tagging(memory_id, boost=1, max_importance=9)
                )

        except Exception as e:
            logger.error(f"Background embed/dedup failed for {memory_id}: {e}")

    async def update_memory(self, memory_id: str, content: str = None,
                            importance_level: int = None, tags: List[str] = None) -> Dict:
        """Update content, importance, or tags of an existing curated memory.

        Only provided fields are updated. If content changes, the embedding is
        regenerated asynchronously so retrieval quality stays fresh.
        """
        if not any([content is not None, importance_level is not None, tags is not None]):
            return {"status": "error", "message": "No fields to update"}

        sets, params = [], []
        ts = get_current_timestamp()
        if content is not None:
            sets.append("content = ?")
            params.append(content)
        if importance_level is not None:
            sets.append("importance_level = ?")
            params.append(importance_level)
        if tags is not None:
            sets.append("tags = ?")
            params.append(json.dumps(tags) if isinstance(tags, list) else tags)
        sets.append("timestamp_updated = ?")
        params.append(ts)
        params.append(memory_id)

        rows = await self.ai_memory_db.execute_update(
            f"UPDATE curated_memories SET {', '.join(sets)} WHERE memory_id = ?",
            tuple(params)
        )
        if rows == 0:
            return {"status": "error", "message": f"Memory {memory_id} not found"}

        # Regenerate embedding asynchronously when content changes
        if content is not None:
            self._schedule_bg_embed(self._add_embedding_to_memory(memory_id, content))

        return {"status": "success", "memory_id": memory_id}

    async def close(self) -> None:
        """Graceful shutdown — cancel background tasks and close shared HTTP session."""
        if hasattr(self, 'file_monitor') and self.file_monitor:
            try:
                self.file_monitor.stop()
            except Exception:
                pass
        if hasattr(self, 'embedding_service'):
            try:
                await self.embedding_service.close()
            except Exception:
                pass
        if hasattr(self, 'reranking_service'):
            try:
                await self.reranking_service.close()
            except Exception:
                pass

    # =============================================================================
    # SCHEDULE OPERATIONS
    # =============================================================================
    
    async def create_appointment(self, title: str, scheduled_datetime: str, 
                               description: str = None, location: str = None,
                               source_conversation_id: str = None) -> Dict:
        """Create an appointment with automatic embedding generation"""
        
        appointment_id = await self.schedule_db.create_appointment(
            title, scheduled_datetime, description, location, source_conversation_id
        )
        
        # Generate embedding for search (combine title and description)
        content_for_embedding = f"{title}"
        if description:
            content_for_embedding += f" {description}"
        
        self._schedule_bg_embed(self._add_embedding_to_appointment(appointment_id, content_for_embedding))
        
        return {
            "status": "success",
            "appointment_id": appointment_id
        }
    
    async def create_reminder(self, content: str, due_datetime: str, 
                            priority_level: int = 5, source_conversation_id: str = None) -> Dict:
        """Create a reminder with automatic embedding generation"""
        
        reminder_id = await self.schedule_db.create_reminder(
            content, due_datetime, priority_level, source_conversation_id
        )
        
        # Generate and store embedding for the reminder content
        self._schedule_bg_embed(self._add_embedding_to_reminder(reminder_id, content))
        
        return {
            "status": "success",
            "reminder_id": reminder_id
        }
    
    async def get_upcoming_schedule(self, days_ahead: int = 7) -> Dict:
        """Get upcoming appointments and reminders"""
        
        appointments = await self.schedule_db.get_upcoming_appointments(days_ahead)
        reminders = await self.schedule_db.get_active_reminders()
        
        return {
            "status": "success",
            "appointments": appointments,
            "active_reminders": reminders,
            "period_days": days_ahead
        }

    # =============================================================================
    # VSCODE PROJECT OPERATIONS
    # =============================================================================
    
    async def save_development_session(self, workspace_path: str, active_files: List[str] = None,
                                     git_branch: str = None, session_summary: str = None) -> Dict:
        """Save development session"""
        
        session_id = await self.vscode_db.save_development_session(
            workspace_path, active_files, git_branch, session_summary
        )
        
        return {
            "status": "success",
            "session_id": session_id
        }
    
    async def store_project_insight(self, content: str, insight_type: str = None,
                                  related_files: List[str] = None, importance_level: int = 5,
                                  source_conversation_id: str = None) -> Dict:
        """Store project insight with automatic embedding generation"""
        
        insight_id = await self.vscode_db.store_project_insight(
            content, insight_type, related_files, importance_level, source_conversation_id
        )
        
        # Generate and store embedding for the insight content
        self._schedule_bg_embed(self._add_embedding_to_project_insight(insight_id, content))
        
        return {
            "status": "success",
            "insight_id": insight_id
        }

    # =============================================================================
    # MCP TOOL CALL OPERATIONS
    # =============================================================================
    
    async def log_tool_call(self, tool_name: str, parameters: Dict = None,
                          execution_time_ms: float = None, status: str = "success",
                          result: Any = None, error_message: str = None, client_id: str = None) -> str:
        """Log an MCP tool call for analysis and debugging"""
        
        return await self.mcp_db.log_tool_call(
            tool_name, parameters, result, status, execution_time_ms, error_message, client_id
        )
    
    async def get_tool_usage_summary(self, days: int = 7) -> Dict:
        """Get comprehensive tool usage summary"""
        
        return await self.mcp_db.get_tool_usage_summary(days)

    async def get_ai_insights(self, limit: int = 10, reflection_type: str = None, insight_type: str = None) -> Dict:
        """Unified method to retrieve AI insights and reflections from both MCP and VS Code project databases."""
        results = []
        
        # Get MCP reflections
        mcp_reflections = await self.mcp_db.get_recent_reflections(limit=limit, reflection_type=reflection_type)
        for reflection in mcp_reflections:
            results.append({
                "source": "mcp_reflection",
                "reflection_id": reflection.get("reflection_id"),
                "timestamp": reflection.get("timestamp"),
                "reflection_type": reflection.get("reflection_type"),
                "content": reflection.get("content"),
                "insights": json.loads(reflection["insights"]) if reflection.get("insights") else None,
                "recommendations": json.loads(reflection["recommendations"]) if reflection.get("recommendations") else None,
                "confidence_level": reflection.get("confidence_level"),
                "source_period_days": reflection.get("source_period_days")
            })
        
        # Get VS Code project insights
        query = "SELECT * FROM project_insights"
        params = []
        where_clauses = []
        
        if insight_type:
            where_clauses.append("insight_type = ?")
            params.append(insight_type)
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " ORDER BY timestamp_created DESC LIMIT ?"
        params.append(limit)
        
        project_insights = await self.vscode_db.execute_query(query, tuple(params))
        for insight in project_insights:
            results.append({
                "source": "project_insight",
                "insight_id": insight.get("insight_id"),
                "timestamp_created": insight.get("timestamp_created"),
                "timestamp_updated": insight.get("timestamp_updated"),
                "insight_type": insight.get("insight_type"),
                "content": insight.get("content"),
                "related_files": json.loads(insight["related_files"]) if insight.get("related_files") else None,
                "importance_level": insight.get("importance_level"),
                "source_conversation_id": insight.get("source_conversation_id")
            })
        
        # Sort by timestamp (descending)
        results.sort(key=lambda x: x.get("timestamp", x.get("timestamp_created", "")), reverse=True)
        
        return {
            "status": "success",
            "count": len(results),
            "results": results[:limit]
        }

    # =============================================================================
    # ADVANCED SEARCH OPERATIONS
    # =============================================================================
    
    async def search_project_history(self, query: str, limit: int = 10) -> Dict:
        """Search project development history including conversations and insights.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            Dict containing search results from project context
        """
        query_embedding = await self.embedding_service.generate_query_embedding(query)
        if not query_embedding:
            return await self._text_based_project_search(query, limit)
            
        results = []
        
        # Search development conversations
        conv_results = await self._search_development_conversations(query_embedding, limit)
        results.extend(conv_results)
        
        # Search project insights
        insight_results = await self._search_project_insights(query_embedding, limit)
        results.extend(insight_results)
        
        # Search code context
        context_results = await self._search_code_context(query_embedding, limit)
        results.extend(context_results)
        
        # Sort by relevance and return
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return {
            "status": "success",
            "query": query,
            "results": results[:limit],
            "count": len(results[:limit])
        }
        
    async def link_code_context(self, file_path: str, description: str,
                              function_name: str = None, conversation_id: str = None) -> Dict:
        """Link conversation context to specific code location.
        
        Args:
            file_path: Path to the code file
            description: Description of the code context
            function_name: Optional function/method name
            conversation_id: Optional related conversation ID
            
        Returns:
            Dict containing the created context link
        """
        context_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        await self.vscode_db.execute_update(
            """INSERT INTO code_context 
               (context_id, timestamp, file_path, function_name, description)
               VALUES (?, ?, ?, ?, ?)""",
            (context_id, timestamp, file_path, function_name, description)
        )
        
        if conversation_id:
            await self.vscode_db.execute_update(
                """UPDATE development_conversations
                   SET chat_context_id = ?
                   WHERE conversation_id = ?""",
                (context_id, conversation_id)
            )
            
        # Generate embedding for search
        self._schedule_bg_embed(self._add_embedding_to_code_context(context_id, description))
        
        return {
            "status": "success",
            "context_id": context_id
        }
        
    async def get_project_continuity(self, workspace_path: str = None, limit: int = 5) -> Dict:
        """Get context for continuing development work.
        
        Args:
            workspace_path: Optional workspace path filter
            limit: Maximum number of context items
            
        Returns:
            Dict containing recent development context
        """
        # Get recent development sessions
        sessions_query = """
            SELECT * FROM project_sessions
            WHERE end_timestamp IS NULL
        """
        if workspace_path:
            sessions_query += " AND workspace_path = ?"
            sessions = await self.vscode_db.execute_query(
                sessions_query + " ORDER BY start_timestamp DESC LIMIT ?",
                (workspace_path, limit)
            )
        else:
            sessions = await self.vscode_db.execute_query(
                sessions_query + " ORDER BY start_timestamp DESC LIMIT ?",
                (limit,)
            )
            
        # Get associated conversations and insights
        context = {
            "active_sessions": [dict(session) for session in sessions],
            "recent_conversations": [],
            "relevant_insights": []
        }
        
        for session in sessions:
            # Get conversations for this session
            convs = await self.vscode_db.execute_query(
                """SELECT * FROM development_conversations
                   WHERE session_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (session["session_id"], limit)
            )
            context["recent_conversations"].extend([dict(conv) for conv in convs])
            
            # Get insights mentioning active files
            if session["active_files"]:
                active_files = json.loads(session["active_files"])
                for file in active_files:
                    insights = await self.vscode_db.execute_query(
                        """SELECT * FROM project_insights
                           WHERE related_files LIKE ?
                           ORDER BY timestamp_created DESC LIMIT ?""",
                        (f"%{file}%", limit)
                    )
                    context["relevant_insights"].extend([dict(insight) for insight in insights])
        
        return {
            "status": "success",
            "context": context
        }
            
    # =========================================================================
    # Sprint 8 helpers
    # =========================================================================

    def _classify_query_intent(self, query: str) -> str:
        """Feature #3 — lightweight 20-rule query intent microclassifier.

        Returns one of:
          'factual'    — precise lookup, exact facts (definitions, numbers, commands)
          'procedural' — how-to, sequence of steps
          'contextual' — broad / open-ended recall

        The classification adjusts reranker strategy hints and tie-breaking
        weights in _get_intent_tiebreak_multiplier().
        """
        q = query.lower()
        factual_signals = [
            r"\bwhat is\b", r"\bwhat are\b", r"\bdefine\b", r"\bdefinition\b",
            r"\bcommand\b", r"\bsyntax\b", r"\berror code\b", r"\bversion\b",
            r"\bwhen did\b", r"\bwhen was\b", r"\bwho is\b",
        ]
        procedural_signals = [
            r"\bhow (to|do|does|can|should)\b", r"\bsteps?\b", r"\bprocess\b",
            r"\binstall\b", r"\bsetup\b", r"\bconfigure\b", r"\bdeploy\b",
            r"\btutorial\b", r"\bguide\b",
        ]
        factual_hits = sum(1 for p in factual_signals if re.search(p, q))
        procedural_hits = sum(1 for p in procedural_signals if re.search(p, q))
        if factual_hits > procedural_hits:
            return "factual"
        if procedural_hits > factual_hits:
            return "procedural"
        return "contextual"

    def _get_intent_tiebreak_multiplier(self, result: Dict, intent: str) -> float:
        """Feature #3 helper — per-result score multiplier based on query intent.

        Factual queries slightly favour clean, high-importance short memories.
        Procedural queries favour procedural/guide memory types.
        Contextual queries apply no extra bias.
        """
        if intent == "factual":
            imp = result.get("data", {}).get("importance_level", 5)
            return 1.0 + (imp - 5) * 0.004          # ±0.02 for imp 0-10
        if intent == "procedural":
            mtype = (result.get("data", {}).get("memory_type") or "").lower()
            if any(k in mtype for k in ("procedure", "guide", "howto", "step", "process")):
                return 1.01
        return 1.0

    def _apply_temporal_decay(self, results: List[Dict], half_life_days: float = 60.0) -> List[Dict]:
        """Feature #5 — Temporal Relevance Decay + Sprint 9 T4 Recency Bonus.

        Applies a gentle exponential decay: score *= e^(-lambda * age_days)
        where lambda = ln(2) / half_life_days.  Half-life default 60 days means
        a 60-day-old memory retains 50 % of its recency bonus, a year-old memory
        retains ~11 %.  The decay is bounded to [0.80, 1.0] so old memories stay
        retrievable.

        Sprint 9 T4 — Recency Bonus: memories created in the last 3 days receive a
        +2 % boost (× 1.02).  This gives the system a notion of "now" — not just
        "how old" — and surfaces fresh information for queries about current state.
        """
        import math
        lam = math.log(2) / half_life_days
        now = datetime.now(timezone.utc)
        for r in results:
            ts_str = r.get("data", {}).get("timestamp_created") or r.get("timestamp_created")
            if not ts_str:
                continue
            try:
                # Support both "Z" suffix ISO and "+HH:MM" offsets
                ts_str_clean = ts_str.replace("Z", "+00:00")
                mem_dt = datetime.fromisoformat(ts_str_clean)
                if mem_dt.tzinfo is None:
                    mem_dt = mem_dt.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (now - mem_dt).total_seconds() / 86400.0)
                if age_days < 3:
                    # T4: Recency bonus — fresher than 3 days
                    multiplier = 1.02
                else:
                    decay = max(0.80, math.exp(-lam * age_days))
                    multiplier = decay
                r["similarity_score"] = r["similarity_score"] * multiplier
            except (ValueError, TypeError):
                pass
        return results

    async def _hyde_expand_query(self, query: str) -> List[str]:
        """
        HyDE — Hypothetical Document Embeddings.
        Calls Ollama qwen2.5:0.5b to generate 3 semantic variants of the query.
        Returns the original query + variants (gracefully degrades to [query] on failure).
        """
        ollama_base = self.embedding_service.fallback_config.get("base_url", "http://localhost:11434")
        prompt = (
            f"Generate exactly 3 short rephrased versions of this search query. "
            f"Return ONLY the 3 rephrases, one per line, no numbering, no explanation.\n"
            f"Query: {query}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{ollama_base}/api/generate",
                    json={"model": "qwen2.5:0.5b", "prompt": prompt, "stream": False},
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data.get("response", "")
                        variants = [line.strip() for line in raw.strip().splitlines() if line.strip()][:3]
                        if variants:
                            logger.debug(f"HyDE variants for '{query}': {variants}")
                            return [query] + variants
        except Exception as e:
            logger.debug(f"HyDE expansion skipped (Ollama unavailable): {e}")
        return [query]

    async def _get_centroid_embedding(self, queries: List[str]) -> List[float]:
        """
        Generate embeddings for multiple queries and return the centroid (mean vector).
        Used by HyDE to merge query variants into a single representative embedding.
        """
        embeddings = []
        for q in queries:
            emb = await self.embedding_service.generate_query_embedding(q)
            if emb:
                embeddings.append(np.array(emb, dtype=np.float32))
        if not embeddings:
            return []
        centroid = np.mean(np.stack(embeddings), axis=0)
        # Re-normalize to unit vector
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        return centroid.tolist()

    async def search_memories(self, query: str, limit: int = 10, 
                            min_importance: int = None, max_importance: int = None,
                            memory_type: str = None, database_filter: str = "all",
                            compact: bool = False,
                            tags_include: List[str] = None,
                            hyde: bool = False) -> Dict:
        """Advanced semantic search across all databases with filtering"""

        # ------------------------------------------------------------------
        # Feature HyDE — Query expansion via Ollama qwen2.5:0.5b
        # When hyde=True, generate semantic variants and search with centroid embedding.
        # Gracefully degrades to standard search if Ollama is unavailable.
        # ------------------------------------------------------------------
        if hyde:
            queries = await self._hyde_expand_query(query)
            if len(queries) > 1:
                query_embedding = await self._get_centroid_embedding(queries)
            else:
                query_embedding = await self.embedding_service.generate_query_embedding(query)
        else:
            query_embedding = None  # will be set below

        # ------------------------------------------------------------------
        # Feature #3 — Query Intent classification (used for tie-breaks below)
        # ------------------------------------------------------------------
        query_intent = self._classify_query_intent(query)

        # Generate embedding for the search query (instruction-prefixed for Qwen3)
        if not hyde or not query_embedding:
            query_embedding = await self.embedding_service.generate_query_embedding(query)
        if not query_embedding:
            # Fallback to text-based search if embedding fails
            result = await self._text_based_search(query, limit, database_filter, min_importance, max_importance, memory_type, tags_include)
            if compact:
                result = self._apply_compact_format(result)
            return result

        # ------------------------------------------------------------------
        # Feature #4 — Semantic Query Cache
        # Check whether a semantically near-identical query was already answered
        # this session (cosine ≥ 0.97 against a cached embedding).
        # We only cache when no narrowing filters are active so the cached result
        # set is equivalent to what would be freshly computed.
        # ------------------------------------------------------------------
        _CACHE_SIM_THRESHOLD = 0.97
        _CACHE_TTL_SECONDS = 300        # 5-minute TTL per entry
        _CACHE_MAX = 32
        _tags_key = tuple(sorted(tags_include)) if tags_include else None
        cache_key_params = (database_filter, limit, min_importance, max_importance, memory_type, _tags_key)
        cache_hit_payload = None
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec))

        if q_norm > 0:
            now_ts = time.monotonic()
            expired_keys = [k for k, (_, _, ts) in self._search_cache.items()
                            if now_ts - ts > _CACHE_TTL_SECONDS]
            for k in expired_keys:
                self._search_cache.pop(k, None)

            for ck, (c_vec, c_payload, c_ts) in list(self._search_cache.items()):
                if ck[1:] != cache_key_params:     # params must match exactly
                    continue
                if now_ts - c_ts > _CACHE_TTL_SECONDS:
                    continue
                c_norm = float(np.linalg.norm(c_vec))
                if c_norm == 0:
                    continue
                sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
                if sim >= _CACHE_SIM_THRESHOLD:
                    cache_hit_payload = dict(c_payload)
                    cache_hit_payload["cache_hit"] = True
                    cache_hit_payload["cache_similarity"] = round(sim, 4)
                    break

        if cache_hit_payload is not None:
            return cache_hit_payload

        all_results = []
        candidate_limit = max(limit * 4, 20)
        reranking_candidate_limit = min(candidate_limit, self.reranking_service.get_candidate_limit(default=30))
        reranking_final_top_n = min(limit, self.reranking_service.get_final_result_count(default=limit))
        
        # Search AI memories — hybrid dense + sparse (Sprint 11)
        if database_filter in ["all", "ai_memories"]:
            # Run dense vector search and FTS sparse search in parallel to
            # avoid adding FTS latency on top of dense latency.
            memory_results, sparse_rows = await asyncio.gather(
                self._search_ai_memories(query_embedding, candidate_limit, min_importance, max_importance, memory_type),
                self.ai_memory_db.search_fts(query, candidate_limit // 2),
            )
            all_results.extend(memory_results)

            # FTS sparse pool expansion: surface candidates that fell below the
            # cosine 0.3 threshold but are keyword-relevant.  We compute their
            # actual cosine similarity and add them to the candidate pool so the
            # downstream rescoring + optional reranker can evaluate them.
            # (We intentionally do NOT boost existing dense results here, as the
            # type-quality composite scoring is already carefully calibrated.)
            if sparse_rows:
                dense_ids = {r["data"]["memory_id"] for r in memory_results}
                new_candidates = [s for s in sparse_rows if s["memory_id"] not in dense_ids]
                if new_candidates:
                    embed_map = await self.ai_memory_db.get_embeddings_by_ids(
                        [s["memory_id"] for s in new_candidates]
                    )
                    for srow in new_candidates:
                        emb_bytes = embed_map.get(srow["memory_id"])
                        if not emb_bytes:
                            continue
                        stored_emb = np.frombuffer(emb_bytes, dtype=np.float32).tolist()
                        cosine = self._calculate_cosine_similarity(query_embedding, stored_emb)
                        all_results.append({
                            "type": "ai_memory",
                            "similarity_score": cosine,
                            "_raw_similarity": cosine,
                            "_embedding": stored_emb,
                            "data": {
                                "memory_id": srow["memory_id"],
                                "content": srow["content"],
                                "importance_level": srow["importance_level"],
                                "memory_type": srow["memory_type"],
                                "timestamp_created": srow["timestamp_created"],
                                "tags": json.loads(srow["tags"]) if srow["tags"] else [],
                                "access_count": srow["access_count"],
                            }
                        })

        # Search conversations
        if database_filter in ["all", "conversations"]:
            conversation_results = await self._search_conversations(query_embedding, candidate_limit)
            all_results.extend(conversation_results)
        
        # Search schedule items
        if database_filter in ["all", "schedule"]:
            schedule_results = await self._search_schedule(query_embedding, candidate_limit)
            all_results.extend(schedule_results)
        
        # Search project insights
        if database_filter in ["all", "projects"]:
            project_results = await self._search_project_insights(query_embedding, candidate_limit)
            all_results.extend(project_results)

        # tags_include post-filter: keep only results whose tags list has any overlap
        if tags_include:
            _tag_set = {t.lower() for t in tags_include}
            all_results = [
                r for r in all_results
                if any(str(t).lower() in _tag_set for t in r.get("data", {}).get("tags", []))
            ]

        for result in all_results:
            result["similarity_score"] = self._apply_lightweight_hybrid_rescoring(query, result)

        # ------------------------------------------------------------------
        # Feature #5 — Temporal Relevance Decay (applied before sorting so
        # boosted + decayed scores are compared together)
        # ------------------------------------------------------------------
        all_results = self._apply_temporal_decay(all_results)

        # ------------------------------------------------------------------
        # Feature #3 — intent tie-break multiplier (micro-adjustment, post-decay)
        # ------------------------------------------------------------------
        for r in all_results:
            r["similarity_score"] *= self._get_intent_tiebreak_multiplier(r, query_intent)

        # Sort all results by similarity score and return top results
        all_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        reranking_applied = False
        confidence_bypassed = False
        gap_bypassed = False

        if all_results:
            top_raw = all_results[0].get("_raw_similarity", all_results[0]["similarity_score"])

            # ------------------------------------------------------------------
            # Feature #1 — Adaptive Bypass Calibration
            # Instead of a fixed 0.92 threshold on raw cosine, compute the
            # threshold dynamically as:  median(raw_cosines) + 1.5 * std(raw_cosines)
            # clamped to [0.80, 0.95].  This self-calibrates to the score
            # distribution of the actual result set rather than a hand-tuned
            # constant, recovering bypass behaviour even when typical scores drift.
            # ------------------------------------------------------------------
            raw_scores = [r.get("_raw_similarity", r["similarity_score"]) for r in all_results]
            if len(raw_scores) >= 4:
                arr = np.array(raw_scores, dtype=np.float32)
                adaptive_threshold = float(np.median(arr) + 1.5 * np.std(arr))
                adaptive_threshold = max(0.80, min(0.95, adaptive_threshold))
            else:
                adaptive_threshold = self.reranking_service.get_confidence_bypass_threshold()

            # ------------------------------------------------------------------
            # Feature #2 — Score-Gap Tiebreaker Router
            # When the gap between #1 and #2 is wide (top_raw clearly dominant)
            # skip the expensive cross-encoder — the ordering is unambiguous.
            # Gap threshold 0.07 is calibrated to production score distributions.
            # ------------------------------------------------------------------
            _GAP_BYPASS_THRESHOLD = 0.05  # Sprint 10: lowered from 0.07 → bypass more, cut P95
            if len(all_results) >= 2:
                second_raw = all_results[1].get("_raw_similarity", all_results[1]["similarity_score"])
                score_gap = top_raw - second_raw
                gap_bypass = score_gap >= _GAP_BYPASS_THRESHOLD
            else:
                gap_bypass = True   # single result — nothing to reorder

            bypass_threshold = adaptive_threshold
            if self.reranking_service.is_enabled() and (top_raw >= bypass_threshold or gap_bypass):
                confidence_bypassed = True
                gap_bypassed = gap_bypass
            else:
                rerank_candidates = all_results[:reranking_candidate_limit]
                reranked_prefix = await self.rerank_search_results(query, rerank_candidates, top_n=len(rerank_candidates))
                reranking_applied = self.reranking_service.last_reranking_applied
                if reranked_prefix:
                    all_results = reranked_prefix + all_results[reranking_candidate_limit:]

        # Strip internal Sprint 8A field before returning to callers
        for r in all_results:
            r.pop("_raw_similarity", None)

        payload = {
            "status": "success",
            "query": query,
            "results": all_results[:reranking_final_top_n],
            "count": len(all_results[:reranking_final_top_n]),
            "search_type": "semantic" if query_embedding else "text_based",
            "candidate_count_before_reranking": min(len(all_results), reranking_candidate_limit),
            "reranking_enabled": self.reranking_service.is_enabled(),
            "reranking_applied": reranking_applied,
            "confidence_bypassed": confidence_bypassed,
            "gap_bypassed": gap_bypassed,
            "query_intent": query_intent,
            "cache_hit": False,
            "reranking_latency_ms": round(self.reranking_service.last_reranking_latency_ms, 2),
        }

        # Feature #4 — store result in session cache
        if q_norm > 0:
            if len(self._search_cache) >= _CACHE_MAX:
                # FIFO eviction: drop oldest entry
                oldest_key = next(iter(self._search_cache))
                self._search_cache.pop(oldest_key, None)
            cache_entry_key = (query[:120], *cache_key_params)
            self._search_cache[cache_entry_key] = (q_vec, payload, time.monotonic())

        # Sprint 9 T2 — Fire-and-forget access_count increment for top results
        # Increments access_count for every ai_memory result that surfaces in the
        # final payload so the boost grows with real usage.  Runs as a background
        # task to avoid blocking the caller.
        top_results = payload.get("results", [])
        memory_ids_to_bump = [
            r["data"]["memory_id"]
            for r in top_results
            if r.get("type") == "ai_memory" and r.get("data", {}).get("memory_id")
        ]
        if memory_ids_to_bump:
            ts_now = get_current_timestamp()
            async def _bump_access(mids, ts):
                # Single batch UPDATE instead of N separate queries.
                placeholders = ",".join("?" * len(mids))
                try:
                    # Read current stability + last_accessed_at for FSRS-6 update
                    rows_fsrs = await self.ai_memory_db.execute_query(
                        f"SELECT memory_id, stability, last_accessed_at FROM curated_memories WHERE memory_id IN ({placeholders})",
                        tuple(mids)
                    )
                    now_dt = datetime.now(get_local_timezone())
                    for r in rows_fsrs:
                        mid = r["memory_id"]
                        s = float(r["stability"] or 1.0)
                        last_str = r["last_accessed_at"]
                        # FSRS-6 simplified: R(t,s) = 0.9^(t/s), new_s = s * (1 + 0.1*(1-R))
                        try:
                            last_dt = datetime.fromisoformat(last_str) if last_str else now_dt
                            t_days = max(0.0, (now_dt - last_dt).total_seconds() / 86400.0)
                        except Exception:
                            t_days = 0.0
                        R = 0.9 ** (t_days / max(s, 0.1))
                        new_s = max(0.1, s * (1.0 + 0.1 * (1.0 - R)))
                        await self.ai_memory_db.execute_update(
                            "UPDATE curated_memories SET access_count = COALESCE(access_count,0)+1, last_accessed_at=?, stability=? WHERE memory_id=?",
                            (ts, round(new_s, 4), mid)
                        )
                except Exception:
                    # Fallback: plain access_count bump
                    try:
                        await self.ai_memory_db.execute_update(
                            f"UPDATE curated_memories SET access_count = COALESCE(access_count,0)+1, last_accessed_at=? WHERE memory_id IN ({placeholders})",
                            (ts, *mids)
                        )
                    except Exception:
                        pass
            asyncio.ensure_future(_bump_access(memory_ids_to_bump, ts_now))

        # Sprint 1 T2 — Compact format: convert full result objects to compressed one-liners
        # "[score|imp:N|type|tag1,tag2] Content snippet (date)"
        # Saves ~90% tokens per result. Default=True since LLMs rarely need raw embedding fields.
        if compact:
            payload = self._apply_compact_format(payload)

        return payload

    def _apply_compact_format(self, payload: Dict) -> Dict:
        """Sprint 1/2 — Convert full result dicts to compressed one-liner strings.

        Format: "[score|imp:N|type|tag1,tag2] snippet (date)"
        Saves ~90% tokens vs full JSON objects. Called by search_memories and
        _text_based_search so compact=True always works regardless of search path.
        """
        import json as _json
        compact_results = []
        for r in payload.get("results", []):
            score = round(r.get("similarity_score", 0), 2)
            data = r.get("data", r)
            imp = data.get("importance_level", "?")
            rtype = r.get("type", data.get("memory_type", "mem"))
            tags = data.get("tags", [])
            if isinstance(tags, str):
                try:
                    tags = _json.loads(tags)
                except Exception:
                    tags = [tags]
            tag_str = ",".join(tags[:3]) if tags else ""
            content = data.get("content", data.get("message_content", ""))
            snippet = (content[:120] + "…") if len(content) > 120 else content
            ts = data.get("timestamp_created", data.get("timestamp", ""))
            date_str = ts[:10] if ts else ""
            tag_part = f"|{tag_str}" if tag_str else ""
            date_part = f" ({date_str})" if date_str else ""
            compact_results.append(f"[{score}|imp:{imp}|{rtype}{tag_part}] {snippet}{date_part}")
        result = dict(payload)
        result["results"] = compact_results
        result["compact"] = True
        return result

    async def rerank_search_results(self, query: str, results: List[Dict[str, Any]], top_n: int = None) -> List[Dict[str, Any]]:
        """Reranks candidates using Rank-Weighted Fusion (RWF): 70% semantic rank + 30% BGE rank.

        Pure BGE reranking can hurt quality when near-duplicate documents share the same base
        content as the canonical answer plus extra keywords that raise BGE scores artificially.
        RWF prevents the cross-encoder from completely overriding a strong semantic ranking while
        still letting BGE provide a meaningful signal where semantic retrieval is uncertain.

        final_score(d) = 0.7 / semantic_rank(d) + 0.3 / bge_rank(d)
        """
        if not results:
            return []

        top_n = top_n or len(results)
        candidate_texts = [self._build_searchable_text(result) for result in results]
        bge_candidates = await self.reranking_service.rerank_documents(query, candidate_texts, top_n=len(results))

        reranking_applied = self.reranking_service.last_reranking_applied

        if not reranking_applied or not bge_candidates:
            # Fall-through: pass-through in original semantic order
            reranked_results = []
            for i, result in enumerate(results[:top_n]):
                r = dict(result)
                r["reranker_score"] = 0.0
                r["search_stage"] = "candidate"
                reranked_results.append(r)
            return reranked_results

        # Build BGE rank lookup: original_index -> 1-based BGE rank
        bge_rank_of = {}
        for bge_pos, rc in enumerate(bge_candidates, start=1):
            orig_idx = rc.get("index")
            if orig_idx is not None and 0 <= orig_idx < len(results):
                bge_rank_of[orig_idx] = bge_pos
                bge_rank_of.setdefault(orig_idx, bge_pos)  # noqa: keep first assignment

        n_candidates = len(results)
        fallback_bge_rank = n_candidates + 1  # penalty rank for candidates not returned by BGE

        # Compute Rank-Weighted Fusion score for every candidate
        scored = []
        for sem_rank_0, result in enumerate(results):
            sem_rank = sem_rank_0 + 1  # 1-based
            bge_rank = bge_rank_of.get(sem_rank_0, fallback_bge_rank)
            rwf_score = 0.7 / sem_rank + 0.3 / bge_rank
            scored.append((rwf_score, sem_rank_0, result))

        scored.sort(key=lambda x: -x[0])

        reranked_results = []
        for rwf_score, orig_idx, result in scored[:top_n]:
            r = dict(result)
            bge_entry = next(
                (rc for rc in bge_candidates if rc.get("index") == orig_idx),
                None,
            )
            r["reranker_score"] = bge_entry["relevance_score"] if bge_entry else 0.0
            r["rwf_score"] = round(rwf_score, 6)
            r["search_stage"] = "reranked"
            reranked_results.append(r)

        return reranked_results

    # =============================================================================
    # SYSTEM HEALTH AND MONITORING
    # =============================================================================
    
    async def get_system_health(self) -> Dict:
        """Get comprehensive system health and statistics"""
        health_data = {
            "status": "healthy",
            "timestamp": get_current_timestamp(),
            "databases": {},
            "file_monitoring": {},
            "embedding_service": {},
            "reranking_service": {}
        }
        
        try:
            # Check conversations database
            conversations_count = await self.conversations_db.execute_query(
                "SELECT COUNT(*) as count FROM messages"
            )
            sessions_count = await self.conversations_db.execute_query(
                "SELECT COUNT(*) as count FROM sessions"
            )
            health_data["databases"]["conversations"] = {
                "status": "healthy",
                "message_count": conversations_count[0]["count"] if conversations_count else 0,
                "session_count": sessions_count[0]["count"] if sessions_count else 0,
                "database_path": self.conversations_db.db_path
            }
            
            # Check AI memories database
            memories_count = await self.ai_memory_db.execute_query(
                "SELECT COUNT(*) as count FROM curated_memories"
            )
            high_importance_count = await self.ai_memory_db.execute_query(
                "SELECT COUNT(*) as count FROM curated_memories WHERE importance_level >= 7"
            )
            health_data["databases"]["ai_memories"] = {
                "status": "healthy",
                "memory_count": memories_count[0]["count"] if memories_count else 0,
                "high_importance_count": high_importance_count[0]["count"] if high_importance_count else 0,
                "database_path": self.ai_memory_db.db_path
            }
            
            # Check schedule database
            appointments_count = await self.schedule_db.execute_query(
                "SELECT COUNT(*) as count FROM appointments"
            )
            reminders_count = await self.schedule_db.execute_query(
                "SELECT COUNT(*) as count FROM reminders"
            )
            health_data["databases"]["schedule"] = {
                "status": "healthy",
                "appointment_count": appointments_count[0]["count"] if appointments_count else 0,
                "reminder_count": reminders_count[0]["count"] if reminders_count else 0,
                "database_path": self.schedule_db.db_path
            }
            
            # Check VS Code project database
            project_sessions_count = await self.vscode_db.execute_query(
                "SELECT COUNT(*) as count FROM project_sessions"
            )
            insights_count = await self.vscode_db.execute_query(
                "SELECT COUNT(*) as count FROM project_insights"
            )
            health_data["databases"]["vscode_project"] = {
                "status": "healthy",
                "session_count": project_sessions_count[0]["count"] if project_sessions_count else 0,
                "insight_count": insights_count[0]["count"] if insights_count else 0,
                "database_path": self.vscode_db.db_path
            }
            
            # Check MCP tool calls database
            tool_calls_count = await self.mcp_db.execute_query(
                "SELECT COUNT(*) as count FROM tool_calls"
            )
            health_data["databases"]["mcp_tool_calls"] = {
                "status": "healthy",
                "total_tool_calls": tool_calls_count[0]["count"] if tool_calls_count else 0,
                "database_path": self.mcp_db.db_path
            }
            
            # Check file monitoring status
            if self.file_monitor:
                health_data["file_monitoring"] = {
                    "status": "enabled",
                    "watch_directories": len(self.file_monitor.watch_directories),
                    "directories": self.file_monitor.watch_directories
                }
            else:
                health_data["file_monitoring"] = {
                    "status": "disabled",
                    "message": "File monitoring is not enabled"
                }
            
            # Check embedding service
            try:
                # Try a simple ping to the embedding service
                test_embedding = await self.embedding_service.generate_embedding("test")
                if test_embedding:
                    health_data["embedding_service"] = {
                        "status": "healthy",
                        "endpoint": self.embedding_service.embeddings_endpoint,
                        "embedding_dimensions": len(test_embedding)
                    }
                else:
                    health_data["embedding_service"] = {
                        "status": "unhealthy",
                        "endpoint": self.embedding_service.embeddings_endpoint,
                        "error": "Failed to generate test embedding"
                    }
            except Exception as e:
                health_data["embedding_service"] = {
                    "status": "unhealthy",
                    "endpoint": self.embedding_service.embeddings_endpoint,
                    "error": str(e)
                }

            try:
                rerank_health = await self.reranking_service.smoke_test()
                rerank_health["provider"] = self.reranking_service.config.get("provider")
                rerank_health["model"] = self.reranking_service.config.get("model")
                health_data["reranking_service"] = rerank_health
            except Exception as e:
                health_data["reranking_service"] = {
                    "status": "unhealthy",
                    "enabled": self.reranking_service.is_enabled(),
                    "endpoint": self.reranking_service.rerank_endpoint,
                    "error": str(e)
                }
            
            # Overall system status
            unhealthy_components = []
            if health_data["embedding_service"]["status"] == "unhealthy":
                unhealthy_components.append("embedding_service")
            if (
                health_data["reranking_service"].get("enabled")
                and health_data["reranking_service"].get("status") == "unhealthy"
            ):
                unhealthy_components.append("reranking_service")
            
            if unhealthy_components:
                health_data["status"] = "degraded"
                health_data["issues"] = unhealthy_components
            
        except Exception as e:
            health_data["status"] = "error"
            health_data["error"] = str(e)
            logger.error(f"Error getting system health: {e}")
        
        return health_data

    # =============================================================================
    # INTERNAL HELPER METHODS
    # =============================================================================
    
    async def _search_ai_memories(self, query_embedding: List[float], limit: int,
                                min_importance: int = None, max_importance: int = None,
                                memory_type: str = None) -> List[Dict]:
        """Search AI curated memories using semantic similarity"""
        
        # Build SQL query with optional filters
        sql = "SELECT * FROM curated_memories WHERE embedding IS NOT NULL"
        params = []
        
        if min_importance is not None:
            sql += " AND importance_level >= ?"
            params.append(min_importance)
            
        if max_importance is not None:
            sql += " AND importance_level <= ?"
            params.append(max_importance)
            
        if memory_type is not None:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        
        rows = await self.ai_memory_db.execute_query(sql, params)
        results = []

        if rows:
            q_arr = np.array(query_embedding, dtype=np.float32)
            rows_list = list(rows)

            def _batch_cosine_ai(rows_inner, q_arr_inner):
                valid = [
                    (row, np.frombuffer(row["embedding"], dtype=np.float32))
                    for row in rows_inner if row["embedding"]
                ]
                if not valid:
                    return []
                valid_rows, embeds = zip(*valid)
                matrix = np.vstack(embeds)
                q_norm = float(np.linalg.norm(q_arr_inner))
                if q_norm < 1e-9:
                    return []
                norms = np.linalg.norm(matrix, axis=1)
                norms = np.where(norms < 1e-9, 1.0, norms)
                sims = (matrix @ q_arr_inner) / (norms * q_norm)
                return [
                    (valid_rows[j], embeds[j], float(sims[j]))
                    for j in range(len(valid_rows)) if sims[j] > 0.3
                ]

            for row, emb_arr, similarity in await asyncio.to_thread(_batch_cosine_ai, rows_list, q_arr):
                # FSRS-6 retention factor: R(t,s) = 0.9^(t/s), modulates final score
                _stability = float(row["stability"] if "stability" in row.keys() and row["stability"] else 1.0)
                _last_str = row["last_accessed_at"] if "last_accessed_at" in row.keys() else None
                try:
                    _now = datetime.now(get_local_timezone())
                    _last = datetime.fromisoformat(_last_str) if _last_str else _now
                    _t = max(0.0, (_now - _last).total_seconds() / 86400.0)
                except Exception:
                    _t = 0.0
                _retention = 0.9 ** (_t / max(_stability, 0.1))  # 1.0 when just accessed, decays over time
                _fsrs_boost = (_retention - 0.5) * 0.06  # ±0.03 max delta — subtle, doesn't override cosine

                results.append({
                    "type": "ai_memory",
                    "similarity_score": similarity + _fsrs_boost,
                    "_raw_similarity": similarity,  # Sprint 8A: pre-boost cosine for bypass gate
                    "_embedding": emb_arr,  # Sprint 7: retained for cross-result cluster pass (ndarray)
                    "data": {
                        "memory_id": row["memory_id"],
                        "content": row["content"],
                        "importance_level": row["importance_level"],
                        "memory_type": row["memory_type"],
                        "timestamp_created": row["timestamp_created"],
                        "tags": json.loads(row["tags"]) if row["tags"] else [],
                        "access_count": row["access_count"] if "access_count" in row.keys() else 0,
                    }
                })
        
        # Sprint 6: Type-Quality Composite Boost
        # --------------------------------------------------------------------
        # Replaces the flat importance_level boost with a 2D composite:
        #   quality_boost = type_weight  × (importance_level/10) × SCALE
        #
        # type_weight encodes how "information-dense" each memory type is:
        #   - Anchor types (feature/testing/configuration): 0.9
        #   - Noise / synthetic filler types: 0.1–0.2
        #
        # This creates a 4–7× gap between anchor memories and filler memories
        # even when filler content has higher raw embedding similarity to the
        # query (e.g., a generic "busqueda semantica" filler vs the specific
        # search_memories feature anchor).  The correction type retains its
        # existing +0.35 flat bonus on top of the composite boost.
        _TYPE_QUALITY_WEIGHT = {
            "correction":       1.0,
            "feature":          0.9,
            "testing":          0.9,
            "configuration":    0.9,
            "integration":      0.9,  # Sprint 10: MCP entrypoints, service wiring
            "project_decision": 0.9,  # Sprint 10: architectural/technology decisions
            "operations":       0.8,
            "ai_memory":        0.8,
            "general":          0.7,
            "mixed_context":    0.5,
            "project_note":     0.4,
            "ops_note":         0.3,
            "support_note":     0.2,
            "noise":            0.1,
        }
        _BOOST_SCALE = 0.10  # Sprint 9: reduced so semantic cosine dominates; max boost = 0.10
        for result in results:
            mt = result["data"].get("memory_type", "general")
            imp = result["data"]["importance_level"]
            try:
                imp = int(imp) if imp is not None else 5
            except (ValueError, TypeError):
                imp = 5
            type_weight = _TYPE_QUALITY_WEIGHT.get(mt, 0.5)
            quality_boost = type_weight * (imp / 10.0) * _BOOST_SCALE
            result["similarity_score"] += quality_boost
            # Self-Correction boost: corrections are always surfaced first when relevant.
            if result["data"].get("memory_type") == "correction":
                result["similarity_score"] += 0.35
        
        # Sprint 9 T2 — Access Count Feedback Boost
        # Memories that have answered queries before earn a small boost that
        # compounds with usage.  Floor is 0, ceiling is +0.04 at ~1000 accesses.
        import math as _math
        for result in results:
            ac = result["data"].get("access_count", 0) or 0
            if ac > 0:
                result["similarity_score"] += min(0.04, _math.log1p(ac) * 0.02)

        results.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Sprint 7: Importance-Preferent Near-Duplicate Suppression
        # -----------------------------------------------------------------------
        # After scoring, clusters of near-duplicate docs collapse to the
        # highest-importance representative. Prevents keyword-rich near-dups
        # from blocking the authoritative anchor memory from reaching top-1.
        #
        # Algorithm: greedy pass over sorted results; when a candidate's
        # cross-result cosine with an already-selected doc exceeds the
        # threshold, the higher-importance doc wins. Equal importance → first
        # in sort order (higher score) wins.
        #
        # Why proxy via stored contextual embeddings instead of content diff:
        # Contextual embeddings (numeric prefix format) preserve importance
        # distinctness while content near-dups still cluster at cosine > 0.88.
        _NEAR_DUP_THRESHOLD = 0.95
        _WEAK_DUP_THRESHOLD = 0.80  # Sprint 10 rev: 0.85 too tight — imp(9) escaped suppression; ≥3 tags keeps precision
        pool = results[:50]  # anchors always land here after Sprint 6 boost

        def _run_dedup(pool_inner, near_thresh, weak_thresh):
            def _meta_cluster_inner(a_data, b_data):
                """True when two memories share the same topic: same memory_type AND ≥3 common tags."""
                if a_data.get("memory_type") != b_data.get("memory_type"):
                    return False
                a_tags = set(a_data.get("tags") or [])
                b_tags = set(b_data.get("tags") or [])
                return len(a_tags & b_tags) >= 3  # Sprint 10: raised from ≥2 for precision

            survivors_inner = []
            for candidate in pool_inner:
                c_emb = candidate.get("_embedding")
                c_imp = candidate["data"]["importance_level"]
                c_ts  = candidate["data"].get("timestamp_created") or ""
                cluster_hit = -1
                is_weak_dup = False
                if c_emb is not None:
                    c_norm = float(np.linalg.norm(c_emb))
                    for i, sel in enumerate(survivors_inner):
                        s_emb = sel.get("_embedding")
                        if s_emb is not None:
                            s_norm = float(np.linalg.norm(s_emb))
                            if c_norm > 1e-9 and s_norm > 1e-9:
                                cross = float(np.dot(c_emb, s_emb)) / (c_norm * s_norm)
                            else:
                                cross = 0.0
                            if cross > near_thresh:
                                cluster_hit = i
                                is_weak_dup = False
                                break
                            elif (cross > weak_thresh
                                  and cluster_hit == -1
                                  and _meta_cluster_inner(candidate["data"], sel["data"])):
                                cluster_hit = i
                                is_weak_dup = True
                                # Do NOT break — a strong dup may still be found further in the list
                if cluster_hit == -1:
                    survivors_inner.append(candidate)
                elif is_weak_dup:
                    # Sprint 9 T5 — Metadata-Aware Weak Supersession
                    # Same type + same tags + semantically similar → the OLDER memory is the
                    # canonical representative of this topic cluster.  Inherit the cluster's
                    # top score so rank position is preserved after the final re-sort.
                    s_ts = survivors_inner[cluster_hit]["data"].get("timestamp_created") or ""
                    if c_ts and s_ts and c_ts < s_ts:
                        candidate["similarity_score"] = survivors_inner[cluster_hit]["similarity_score"]
                        survivors_inner[cluster_hit] = candidate
                    # else: candidate is newer → silently dropped (existing is canonical)
                else:
                    # Strong near-dup (cosine > 0.95) — Sprint 7 + T1 logic
                    s_imp = survivors_inner[cluster_hit]["data"]["importance_level"]
                    s_ts  = survivors_inner[cluster_hit]["data"].get("timestamp_created") or ""
                    imp_diff = abs(c_imp - s_imp)
                    if c_imp > s_imp:
                        # Higher-importance doc from same cluster displaces current representative
                        survivors_inner[cluster_hit] = candidate
                    elif imp_diff <= 1:
                        # Sprint 9 T1 — Creation-Order Tiebreaker
                        # When importance is tied (≤1 point gap), the OLDER memory is the
                        # canonical original; the newer one is the imposter/copy.
                        # Lexicographic ISO string comparison works because our timestamps are
                        # zero-padded UTC (e.g. "2026-03-20T10:00:00+00:00").
                        if c_ts and s_ts and c_ts < s_ts:
                            survivors_inner[cluster_hit] = candidate
                    # else: candidate importance is clearly lower → silently dropped
            survivors_inner.sort(key=lambda x: x["similarity_score"], reverse=True)
            return survivors_inner

        survivors = await asyncio.to_thread(_run_dedup, pool, _NEAR_DUP_THRESHOLD, _WEAK_DUP_THRESHOLD)
        for r in survivors:
            r.pop("_embedding", None)
            # _raw_similarity is retained: needed by search_memories() bypass gate (Sprint 8A)
        return survivors[:limit]

    async def _search_conversations(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search conversation messages using semantic similarity"""
        
        query = """
            SELECT message_id, conversation_id, timestamp, role, content, metadata, embedding
            FROM messages 
            WHERE embedding IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1000
        """
        
        rows = await self.conversations_db.execute_query(query)
        results = []

        if rows:
            q_arr = np.array(query_embedding, dtype=np.float32)

            def _batch_cosine_conv(rows_inner, q_arr_inner):
                valid = [
                    (row, np.frombuffer(row["embedding"], dtype=np.float32))
                    for row in rows_inner if row["embedding"]
                ]
                if not valid:
                    return []
                valid_rows, embeds = zip(*valid)
                matrix = np.vstack(embeds)
                q_norm = float(np.linalg.norm(q_arr_inner))
                if q_norm < 1e-9:
                    return []
                norms = np.linalg.norm(matrix, axis=1)
                norms = np.where(norms < 1e-9, 1.0, norms)
                sims = (matrix @ q_arr_inner) / (norms * q_norm)
                return [(valid_rows[j], float(sims[j])) for j in range(len(valid_rows)) if sims[j] > 0.3]

            for row, similarity in await asyncio.to_thread(_batch_cosine_conv, list(rows), q_arr):
                results.append({
                    "type": "conversation",
                    "similarity_score": similarity,
                    "data": {
                        "message_id": row["message_id"],
                        "conversation_id": row["conversation_id"],
                        "timestamp": row["timestamp"],
                        "role": row["role"],
                        "content": row["content"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else None
                    }
                })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _search_schedule(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search appointments and reminders using semantic similarity"""
        
        results = []
        
        # Search appointments
        appointment_query = """
            SELECT appointment_id, timestamp_created, scheduled_datetime, title, 
                   description, location, source_conversation_id, embedding
            FROM appointments 
            WHERE embedding IS NOT NULL
        """
        
        q_arr_sched = np.array(query_embedding, dtype=np.float32)

        def _batch_cosine_sched(rows_inner, q_arr_inner):
            valid = [
                (row, np.frombuffer(row["embedding"], dtype=np.float32))
                for row in rows_inner if row["embedding"]
            ]
            if not valid:
                return []
            valid_rows, embeds = zip(*valid)
            matrix = np.vstack(embeds)
            q_norm = float(np.linalg.norm(q_arr_inner))
            if q_norm < 1e-9:
                return []
            norms = np.linalg.norm(matrix, axis=1)
            norms = np.where(norms < 1e-9, 1.0, norms)
            sims = (matrix @ q_arr_inner) / (norms * q_norm)
            return [(valid_rows[j], float(sims[j])) for j in range(len(valid_rows)) if sims[j] > 0.3]

        appt_rows = await self.schedule_db.execute_query(appointment_query)
        for row, similarity in await asyncio.to_thread(_batch_cosine_sched, list(appt_rows), q_arr_sched):
            results.append({
                "type": "appointment",
                "similarity_score": similarity,
                "data": {
                    "appointment_id": row["appointment_id"],
                    "scheduled_datetime": row["scheduled_datetime"],
                    "title": row["title"],
                    "description": row["description"],
                    "location": row["location"]
                }
            })

        # Search reminders
        reminder_query = """
            SELECT reminder_id, timestamp_created, due_datetime, content, 
                   priority_level, completed, source_conversation_id, embedding
            FROM reminders 
            WHERE embedding IS NOT NULL
        """

        rem_rows = await self.schedule_db.execute_query(reminder_query)
        for row, similarity in await asyncio.to_thread(_batch_cosine_sched, list(rem_rows), q_arr_sched):
            results.append({
                "type": "reminder",
                "similarity_score": similarity,
                "data": {
                    "reminder_id": row["reminder_id"],
                    "due_datetime": row["due_datetime"],
                    "content": row["content"],
                    "priority_level": row["priority_level"],
                    "completed": bool(row["completed"])
                }
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _search_project_insights(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search project insights using semantic similarity"""
        
        query = """
            SELECT insight_id, timestamp_created, insight_type, content, 
                   related_files, importance_level, embedding
            FROM project_insights 
            WHERE embedding IS NOT NULL
        """
        
        rows = await self.vscode_db.execute_query(query)
        results = []

        if rows:
            q_arr_pi = np.array(query_embedding, dtype=np.float32)

            def _batch_cosine_pi(rows_inner, q_arr_inner):
                valid = [
                    (row, np.frombuffer(row["embedding"], dtype=np.float32))
                    for row in rows_inner if row["embedding"]
                ]
                if not valid:
                    return []
                valid_rows, embeds = zip(*valid)
                matrix = np.vstack(embeds)
                q_norm = float(np.linalg.norm(q_arr_inner))
                if q_norm < 1e-9:
                    return []
                norms = np.linalg.norm(matrix, axis=1)
                norms = np.where(norms < 1e-9, 1.0, norms)
                sims = (matrix @ q_arr_inner) / (norms * q_norm)
                return [(valid_rows[j], float(sims[j])) for j in range(len(valid_rows)) if sims[j] > 0.3]

            for row, similarity in await asyncio.to_thread(_batch_cosine_pi, list(rows), q_arr_pi):
                results.append({
                    "type": "project_insight",
                    "similarity_score": similarity,
                    "data": {
                        "insight_id": row["insight_id"],
                        "timestamp_created": row["timestamp_created"],
                        "insight_type": row["insight_type"],
                        "content": row["content"],
                        "related_files": json.loads(row["related_files"]) if row["related_files"] else None,
                        "importance_level": row["importance_level"]
                    }
                })

        # Boost results based on importance level
        for result in results:
            importance_boost = result["data"]["importance_level"] / 10.0 * 0.15
            result["similarity_score"] += importance_boost
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    def _tokenize_search_text(self, text: str) -> List[str]:
        """Tokenize text for lightweight lexical ranking signals."""
        if not text:
            return []
        normalized = text.lower().replace("_", " ").replace("-", " ")
        tokens = re.findall(r"[a-z0-9:/.]+", normalized)
        return [
            token for token in tokens
            if token not in SEARCH_STOPWORDS and (len(token) >= 3 or any(char.isdigit() for char in token))
        ]

    def _normalize_search_token(self, token: str) -> str:
        """Normalize technical aliases and typo variants to a canonical search token."""
        if not token:
            return ""
        compact_token = re.sub(r"[^a-z0-9]+", "", token.lower())
        alias_value = SEARCH_TOKEN_ALIASES.get(compact_token)
        if alias_value:
            return alias_value
        return token.lower()

    def _build_normalized_token_set(self, text: str) -> set[str]:
        """Build normalized single-token and compound-token features for cheap hybrid matching."""
        raw_tokens = self._tokenize_search_text(text)
        if not raw_tokens:
            return set()

        normalized_tokens = {self._normalize_search_token(token) for token in raw_tokens}
        normalized_tokens = {token for token in normalized_tokens if token}

        for window_size in (2, 3):
            for start_index in range(len(raw_tokens) - window_size + 1):
                compound_token = "".join(raw_tokens[start_index:start_index + window_size])
                normalized_compound = self._normalize_search_token(compound_token)
                if normalized_compound:
                    normalized_tokens.add(normalized_compound)

        return normalized_tokens

    def _build_searchable_text(self, result: Dict[str, Any]) -> str:
        """Build a unified textual representation for hybrid rescoring."""
        data = result.get("data", {})
        text_parts = [
            data.get("content", ""),
            data.get("title", ""),
            data.get("description", ""),
            data.get("location", ""),
            data.get("memory_type", ""),
            data.get("insight_type", ""),
            data.get("role", ""),
        ]

        tags = data.get("tags") or []
        if isinstance(tags, list):
            text_parts.extend(str(tag) for tag in tags)

        related_files = data.get("related_files") or []
        if isinstance(related_files, list):
            text_parts.extend(str(path) for path in related_files)

        return " ".join(part for part in text_parts if part)

    def _calculate_lexical_match_score(self, query: str, result: Dict[str, Any]) -> float:
        """Compute inexpensive lexical and fuzzy-match signals for reranking."""
        searchable_text = self._build_searchable_text(result).lower()
        if not searchable_text:
            return 0.0

        query_tokens = self._tokenize_search_text(query)
        if not query_tokens:
            return 0.0

        normalized_query_tokens = self._build_normalized_token_set(query)
        searchable_tokens = self._build_normalized_token_set(searchable_text)
        exact_matches = sum(1 for token in normalized_query_tokens if token in searchable_tokens)
        fuzzy_matches = 0
        for token in normalized_query_tokens:
            if token in searchable_tokens or len(token) < 5:
                continue
            if any(difflib.SequenceMatcher(None, token, candidate).ratio() >= 0.84 for candidate in searchable_tokens):
                fuzzy_matches += 1

        normalized_query_count = max(len(normalized_query_tokens), 1)
        token_coverage = exact_matches / normalized_query_count
        fuzzy_coverage = fuzzy_matches / normalized_query_count
        phrase_boost = 0.18 if query.lower() in searchable_text else 0.0

        identifier_tokens = {
            token for token in normalized_query_tokens
            if any(char.isdigit() for char in token) or any(char in token for char in (":", "/", ".")) or len(token) >= 10
        }
        identifier_overlap = len(identifier_tokens & searchable_tokens)
        identifier_boost = min(identifier_overlap * 0.05, 0.15)

        tags = result.get("data", {}).get("tags") or []
        tag_tokens = set()
        for tag in tags:
            if not tag:
                continue
            tag_tokens.update(self._build_normalized_token_set(str(tag)))
        tag_overlap = len(normalized_query_tokens & tag_tokens)
        tag_boost = min(tag_overlap * 0.04, 0.12)

        return min((token_coverage * 0.22) + (fuzzy_coverage * 0.12) + phrase_boost + identifier_boost + tag_boost, 0.55)

    def _apply_lightweight_hybrid_rescoring(self, query: str, result: Dict[str, Any]) -> float:
        """Blend semantic score with lightweight lexical signals without external dependencies."""
        base_score = float(result.get("similarity_score", 0.0))
        lexical_boost = self._calculate_lexical_match_score(query, result)
        return base_score + lexical_boost

    def _calculate_cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def _text_based_search(self, query: str, limit: int, database_filter: str,
                               min_importance: int = None, max_importance: int = None,
                               memory_type: str = None,
                               tags_include: List[str] = None) -> Dict:
        """Fallback text-based search when embeddings are unavailable"""
        
        query_words = query.lower().split()
        results = []
        
        if database_filter in ["all", "ai_memories"]:
            # Search AI memories with text matching and filters
            sql = "SELECT * FROM curated_memories WHERE 1=1"
            params = []

            # SQL-level tags filter (belt): when tags_include is specified,
            # restrict at the DB level so unrelated-project rows are never fetched.
            # SQLite tags column stores JSON arrays like '["DVE","water"]'; we
            # match case-insensitively with LIKE on the lowercased column value.
            if tags_include:
                tag_conditions = ["LOWER(tags) LIKE ?" for _ in tags_include]
                sql += f" AND ({' OR '.join(tag_conditions)})"
                for t in tags_include:
                    params.append(f"%{t.lower()}%")
            
            # Add content search
            content_conditions = []
            for word in query_words:
                content_conditions.append("LOWER(content) LIKE ?")
                params.append(f"%{word}%")
            
            if content_conditions:
                sql += f" AND ({' OR '.join(content_conditions)})"
            
            # Add importance filters
            if min_importance is not None:
                sql += " AND importance_level >= ?"
                params.append(min_importance)
                
            if max_importance is not None:
                sql += " AND importance_level <= ?"
                params.append(max_importance)
                
            if memory_type is not None:
                sql += " AND memory_type = ?"
                params.append(memory_type)
            
            sql += " ORDER BY importance_level DESC LIMIT ?"
            params.append(limit)
            
            rows = await self.ai_memory_db.execute_query(sql, params)
            for row in rows:
                results.append({
                    "type": "ai_memory",
                    "similarity_score": 0.5,
                    "data": dict(row)
                })
        
        if database_filter in ["all", "conversations"]:
            # Search conversations with text matching
            for word in query_words:
                rows = await self.conversations_db.execute_query(
                    "SELECT * FROM messages WHERE LOWER(content) LIKE ? ORDER BY timestamp DESC LIMIT ?",
                    (f"%{word}%", limit)
                )
                for row in rows:
                    results.append({
                        "type": "conversation",
                        "similarity_score": 0.5,
                        "data": dict(row)
                    })
        
        # Apply tags_include filter if specified
        if tags_include:
            import json as _json
            _tag_set = {t.lower() for t in tags_include}
            filtered = []
            for r in results:
                raw_tags = r.get("data", {}).get("tags", "[]")
                if isinstance(raw_tags, str):
                    try:
                        tag_list = _json.loads(raw_tags)
                    except Exception:
                        tag_list = []
                else:
                    tag_list = raw_tags or []
                if any(str(t).lower() in _tag_set for t in tag_list):
                    filtered.append(r)
            results = filtered

        # Remove duplicates and limit results
        seen = set()
        unique_results = []
        for result in results:
            key = f"{result['type']}_{result['data'].get('memory_id', result['data'].get('message_id', ''))}"
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        return {
            "status": "success",
            "query": query,
            "results": unique_results[:limit],
            "count": len(unique_results[:limit]),
            "search_type": "text_based",
            "note": "Used text-based search (embeddings unavailable)"
        }
    
    # SillyTavern-specific methods
    async def get_character_context(self, character_name: str, context_type: str = None, limit: int = 5) -> Dict:
        """Get relevant context about characters from memory"""
        try:
            # Search for character-specific memories
            query = f"character {character_name}"
            if context_type:
                query += f" {context_type}"
            
            # Search memories and conversations
            memories = await self.search_memories(query, limit=limit)
            
            # Filter and format results
            character_context = {
                "character_name": character_name,
                "context_type": context_type,
                "memories": memories.get("results", []),
                "total_found": len(memories.get("results", [])),
                "timestamp": get_current_timestamp()
            }
            
            logger.info(f"Retrieved {len(memories.get('results', []))} memories for character: {character_name}")
            return character_context
            
        except Exception as e:
            logger.error(f"Error getting character context: {e}")
            return {"error": str(e), "character_name": character_name}

    async def store_roleplay_memory(self, character_name: str, event_description: str, 
                                    importance_level: int = 5, tags: List[str] = None) -> Dict:
        """Store important roleplay moments or character developments"""
        try:
            # Format the memory content
            content = f"Character: {character_name}\nEvent: {event_description}"
            
            # Add roleplay-specific tags
            if tags is None:
                tags = []
            tags.extend(["roleplay", "character", character_name.lower()])
            
            # Create the memory
            result = await self.create_memory(
                content=content,
                memory_type="roleplay",
                importance_level=importance_level,
                tags=tags
            )
            
            logger.info(f"Stored roleplay memory for character: {character_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error storing roleplay memory: {e}")
            return {"error": str(e), "character_name": character_name}

    async def search_roleplay_history(self, query: str, character_name: str = None, limit: int = 10) -> Dict:
        """Search past roleplay interactions and character development"""
        try:
            # Build search query
            search_query = f"roleplay {query}"
            if character_name:
                search_query += f" character {character_name}"
            
            # Search with roleplay memory type filter
            results = await self.search_memories(
                query=search_query,
                limit=limit,
                memory_type="roleplay"
            )
            
            # Add roleplay-specific formatting
            results["search_type"] = "roleplay_history"
            results["character_filter"] = character_name
            results["original_query"] = query
            
            logger.info(f"Found {len(results.get('results', []))} roleplay history results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching roleplay history: {e}")
            return {"error": str(e), "query": query}

    # System maintenance
    async def run_database_maintenance(self, force: bool = False) -> Dict:
        """Run maintenance on all databases using the DatabaseMaintenance class.
        
        This includes:
        - Optimizing indexes
        - Cleaning up orphaned records
        - Updating statistics
        - Validating data consistency
        - Applying retention policies
        - Removing duplicates
        
        Args:
            force: Whether to force maintenance even if recent
            
        Returns:
            Dict containing maintenance results
        """
        try:
            # Create and use DatabaseMaintenance instance
            maintenance = DatabaseMaintenance(self)
            results = await maintenance.run_maintenance(force)
            return results
                
        except Exception as e:
            error_result = {
                "status": "error",
                "message": str(e),
                "timestamp": get_current_timestamp()
            }
            logger.error(f"System maintenance error: {e}")
            return error_result
    
    # Embedding helper methods (async background tasks)
    async def _add_embedding_to_message(self, message_id: str, content: str):
        """Add embedding to a message (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.conversations_db.execute_update(
                    "UPDATE messages SET embedding = ? WHERE message_id = ?",
                    (embedding_blob, message_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to message {message_id}: {e}")
    
    @staticmethod
    def _build_contextual_embedding_text(
        content: str,
        memory_type: str | None,
        importance_level: int | None,
        tags: list | None,
        created_at: str | None = None,
    ) -> str:
        """Build enriched text for embedding via Contextual Retrieval (Sprint 5).

        Prepends a short context prefix before the raw content so that
        semantically similar memories with different roles, importance, or tags
        produce discriminative vectors.  The prefix is never shown to the user.

        Format:  "{type} | importancia:{level} | [{tag1},{tag2}]: {content}"

        Rationale:
        - memory_type  : anchors the vector in the correct thematic cluster
          (testing vs configuration vs feature).
        - importance_level : numeric identifier — "importancia:8" vs "importancia:6"
          creates distinct token identities, discriminating anchors (8) from
          near-duplicates (6) in embedding space.
        - tags          : surface canonical identifiers before the prose; the
          model sees "health_check, validation" before a typo-heavy sentence.

        NOTE (Sprint 6 analysis): a natural-language prefix ("feature del sistema,
        importancia alta") was tested and caused catastrophic regression (-36pp
        Top-1).  Natural language shares too many tokens between anchor prefix
        and near-dup prefix, collapsing the distinction.  The compact numeric
        format below is intentionally kept.
        """
        type_str = (memory_type or "general").lower().strip()
        imp_str = str(importance_level) if importance_level is not None else "5"
        tag_list = tags if tags else []
        tag_str = ",".join(str(t).lower().strip() for t in tag_list[:5])
        # Sprint 9 T3 — Epoch Token (Sprint 10: opt-in for memories older than 7 days).
        # Encoding the ISO year-week creates divergent vectors for memories from different
        # project phases.  For fresh memories (< 7 days), it adds noise with zero benefit
        # because they all share the same week token → omit to preserve semantic clarity.
        epoch_str = None
        if created_at:
            try:
                _ts = created_at.replace("Z", "+00:00")
                _dt = datetime.fromisoformat(_ts)
                if _dt.tzinfo is None:
                    _dt = _dt.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - _dt).total_seconds() / 86400.0
                if age_days >= 7:
                    epoch_str = _dt.strftime("%Y-W%V")
            except (ValueError, AttributeError):
                pass
        if epoch_str:
            prefix = f"{type_str} | importancia:{imp_str} | epoca:{epoch_str} | [{tag_str}]: "
        else:
            prefix = f"{type_str} | importancia:{imp_str} | [{tag_str}]: "
        return prefix + content

    async def _add_embedding_to_memory(self, memory_id: str, content: str):
        """Add contextually-enriched embedding to a memory.

        Fetches the memory row to obtain metadata (memory_type, importance_level,
        tags) and prepends a context prefix before embedding.  This implements
        the Contextual Retrieval principle: enrich document representations
        without changing the query path, producing more discriminative vectors.
        """
        try:
            # Fetch metadata for contextual enrichment
            rows = await self.ai_memory_db.execute_query(
                "SELECT memory_type, importance_level, tags, timestamp_created FROM curated_memories WHERE memory_id = ?",
                (memory_id,)
            )
            if rows:
                row = rows[0]
                tags_raw = row["tags"]
                tags = json.loads(tags_raw) if tags_raw else []
                contextual_text = self._build_contextual_embedding_text(
                    content,
                    row["memory_type"],
                    row["importance_level"],
                    tags,
                    created_at=row["timestamp_created"],
                )
            else:
                contextual_text = content

            embedding = await self.embedding_service.generate_embedding(contextual_text)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.ai_memory_db.execute_update(
                    "UPDATE curated_memories SET embedding = ? WHERE memory_id = ?",
                    (embedding_blob, memory_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to memory {memory_id}: {e}")
    
    async def _add_embedding_to_appointment(self, appointment_id: str, content: str):
        """Add embedding to an appointment (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.schedule_db.execute_update(
                    "UPDATE appointments SET embedding = ? WHERE appointment_id = ?",
                    (embedding_blob, appointment_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to appointment {appointment_id}: {e}")
    
    async def _add_embedding_to_reminder(self, reminder_id: str, content: str):
        """Add embedding to a reminder (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.schedule_db.execute_update(
                    "UPDATE reminders SET embedding = ? WHERE reminder_id = ?",
                    (embedding_blob, reminder_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to reminder {reminder_id}: {e}")
    
    async def _add_embedding_to_project_insight(self, insight_id: str, content: str):
        """Add embedding to a project insight (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE project_insights SET embedding = ? WHERE insight_id = ?",
                    (embedding_blob, insight_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to project insight {insight_id}: {e}")

    # =============================================================================
    # ADDITIONAL REMINDER AND APPOINTMENT METHODS
    # =============================================================================
    
    async def get_active_reminders(self, limit: int = 10, days_ahead: int = 30) -> List[Dict]:
        """Get active (not completed) reminders"""
        try:
            from datetime import datetime, timedelta
            end_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
            
            rows = await self.schedule_db.execute_query(
                """SELECT * FROM reminders 
                   WHERE is_completed = 0 AND due_datetime <= ? 
                   ORDER BY due_datetime ASC LIMIT ?""",
                (end_date, limit)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting active reminders: {e}")
            return []
    
    async def get_completed_reminders(self, days: int = 7) -> List[Dict]:
        """Get recently completed reminders"""
        try:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            rows = await self.schedule_db.execute_query(
                """SELECT * FROM reminders 
                   WHERE is_completed = 1 AND completed_at >= ? 
                   ORDER BY completed_at DESC""",
                (start_date,)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting completed reminders: {e}")
            return []
    
    async def complete_reminder(self, reminder_id: str) -> Dict:
        """Mark a reminder as completed"""
        try:
            from datetime import datetime
            completed_at = datetime.now().isoformat()
            
            await self.schedule_db.execute_update(
                "UPDATE reminders SET is_completed = 1, completed_at = ? WHERE reminder_id = ?",
                (completed_at, reminder_id)
            )
            return {"status": "success", "reminder_id": reminder_id, "completed_at": completed_at}
        except Exception as e:
            logger.error(f"Error completing reminder {reminder_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def reschedule_reminder(self, reminder_id: str, new_due_datetime: str) -> Dict:
        """Update the due date of a reminder"""
        try:
            await self.schedule_db.execute_update(
                "UPDATE reminders SET due_datetime = ? WHERE reminder_id = ?",
                (new_due_datetime, reminder_id)
            )
            return {"status": "success", "reminder_id": reminder_id, "new_due_datetime": new_due_datetime}
        except Exception as e:
            logger.error(f"Error rescheduling reminder {reminder_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_reminder(self, reminder_id: str) -> Dict:
        """Permanently delete a reminder"""
        try:
            await self.schedule_db.execute_update(
                "DELETE FROM reminders WHERE reminder_id = ?",
                (reminder_id,)
            )
            return {"status": "success", "reminder_id": reminder_id}
        except Exception as e:
            logger.error(f"Error deleting reminder {reminder_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_appointment(self, appointment_id: str) -> Dict:
        """Cancel an appointment"""
        result = await self.schedule_db.execute_update(
            "UPDATE appointments SET status = 'cancelled', cancelled_at = ? WHERE appointment_id = ?",
            (get_current_timestamp(), appointment_id)
        )
        if result > 0:
            return {"status": "success", "message": f"Appointment {appointment_id} cancelled"}
        else:
            return {"status": "error", "message": "Appointment not found"}

    async def complete_appointment(self, appointment_id: str) -> Dict:
        """Mark an appointment as completed"""
        result = await self.schedule_db.execute_update(
            "UPDATE appointments SET status = 'completed', completed_at = ? WHERE appointment_id = ?",
            (get_current_timestamp(), appointment_id)
        )
        if result > 0:
            return {"status": "success", "message": f"Appointment {appointment_id} marked as completed"}
        else:
            return {"status": "error", "message": "Appointment not found"}
    
    async def get_upcoming_appointments(self, limit: int = 5, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming appointments (not cancelled)"""
        try:
            from datetime import datetime, timedelta
            end_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
            
            rows = await self.schedule_db.execute_query(
                """SELECT * FROM appointments 
                   WHERE is_cancelled = 0 AND scheduled_datetime <= ? 
                   ORDER BY scheduled_datetime ASC LIMIT ?""",
                (end_date, limit)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting upcoming appointments: {e}")
            return []
    
    async def get_appointments(self, limit: int = 5, days_ahead: int = 30) -> List[Dict]:
        """Get recent appointments, optionally filtered by date range"""
        try:
            from datetime import datetime, timedelta
            end_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
            
            rows = await self.schedule_db.execute_query(
                """SELECT * FROM appointments 
                   WHERE scheduled_datetime <= ? 
                   ORDER BY scheduled_datetime DESC LIMIT ?""",
                (end_date, limit)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting appointments: {e}")
            return []
    
    async def store_ai_reflection(self, content: str, reflection_type: str = "general", 
                                insights: List[str] = None, recommendations: List[str] = None,
                                confidence_level: float = 0.7, source_period_days: int = None) -> Dict:
        """Store an AI self-reflection/insight record"""
        try:
            reflection_id = await self.mcp_db.store_ai_reflection(
                content, reflection_type, insights, recommendations, confidence_level, source_period_days
            )
            return {"status": "success", "reflection_id": reflection_id}
        except Exception as e:
            logger.error(f"Error storing AI reflection: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_current_time(self) -> Dict:
        """Get the current server time in ISO format (UTC and local)"""
        try:
            from datetime import datetime, timezone
            import time
            
            utc_time = datetime.now(timezone.utc)
            local_time = datetime.now()
            timezone_name = time.tzname[0]
            
            return {
                "utc_time": utc_time.isoformat(),
                "local_time": local_time.isoformat(),
                "timezone": timezone_name,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting current time: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_weather_open_meteo(self, latitude: float = None, longitude: float = None,
                                   timezone_str: str = None, force_refresh: bool = False,
                                   return_changes_only: bool = False, update_today: bool = True,
                                   severe_update: bool = False) -> Dict:
        """Open-Meteo forecast (no API key). Defaults to Motley, MN and caches once per local day.

        Uses aiohttp (non-blocking) instead of requests.get() so the asyncio event loop
        is never frozen while waiting for the HTTP response.
        """
        try:
            from datetime import datetime, timedelta

            # Default location (Motley, MN)
            lat = latitude if latitude is not None else 46.3436
            lon = longitude if longitude is not None else -94.6297
            tz = timezone_str if timezone_str is not None else "America/Chicago"

            # Create cache directory
            cache_dir = Path("weather_cache")
            cache_dir.mkdir(exist_ok=True)

            today = datetime.now().strftime("%Y-%m-%d")
            cache_file = cache_dir / f"weather_{today}.json"

            # Check cache unless forced refresh
            if not force_refresh and cache_file.exists():
                cached_data = await asyncio.to_thread(
                    lambda: json.loads(cache_file.read_text(encoding="utf-8"))
                )

                if return_changes_only:
                    return {"status": "cached", "message": "Using cached weather data"}
                else:
                    return cached_data

            # Fetch from Open-Meteo API using aiohttp (non-blocking)
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "timezone": tz,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "forecast_days": 7
            }

            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    weather_data = await response.json()

            weather_data["cached_at"] = datetime.now().isoformat()
            weather_data["location"] = {"latitude": lat, "longitude": lon, "timezone": tz}

            # Save to cache (non-blocking write)
            await asyncio.to_thread(
                lambda: cache_file.write_text(json.dumps(weather_data, indent=2), encoding="utf-8")
            )

            return weather_data

        except Exception as e:
            logger.error(f"Error getting weather: {e}")
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # SPRINT 14 — COGNITIVE FEATURES
    # Renamed from VESTIGE concepts to avoid license conflicts.
    # =========================================================================

    async def salience_score(self, content: str, context: str = None) -> Dict:
        """Compute 4-channel cognitive salience for incoming content.

        Channels (each 0.0–1.0, combined to importance 1-10):
          novelty   — how different from nearest existing memory (1 - top cosine)
          arousal   — urgency/emotional intensity (keyword heuristic)
          reward    — achievement / positive signal (keyword heuristic)
          attention — explicit importance markers in the text

        Returns composite importance_suggested (1-10) plus per-channel breakdown.
        """
        try:
            AROUSAL_TERMS  = {"urgent","critical","error","fail","bug","broken","crash","blocker","deadline","asap","emergency"}
            REWARD_TERMS   = {"success","done","fixed","solved","deployed","merged","shipped","achieved","completed","win"}
            ATTENTION_TERMS= {"important","remember","never forget","always","required","mandatory","key","essential","note"}

            lower = content.lower()
            words = set(lower.split())

            arousal   = min(1.0, sum(1 for t in AROUSAL_TERMS  if t in lower) * 0.25)
            reward    = min(1.0, sum(1 for t in REWARD_TERMS   if t in lower) * 0.25)
            attention = min(1.0, sum(1 for t in ATTENTION_TERMS if t in lower) * 0.30)

            # novelty — compare against existing memories
            novelty = 0.7  # default if no embedding available
            try:
                emb = await self.embedding_service.generate_query_embedding(content)
                if emb:
                    top = await self._search_ai_memories(emb, limit=1)
                    if top:
                        raw_sim = top[0].get("_raw_similarity", top[0].get("similarity_score", 0.3))
                        novelty = max(0.0, 1.0 - float(raw_sim))
            except Exception:
                pass

            composite = (novelty * 0.35 + arousal * 0.25 + reward * 0.15 + attention * 0.25)
            importance_suggested = max(1, min(10, round(composite * 9) + 1))

            return {
                "status": "success",
                "importance_suggested": importance_suggested,
                "channels": {
                    "novelty":   round(novelty,   3),
                    "arousal":   round(arousal,   3),
                    "reward":    round(reward,    3),
                    "attention": round(attention, 3),
                },
                "composite": round(composite, 3),
            }
        except Exception as e:
            logger.error(f"salience_score error: {e}")
            return {"status": "error", "message": str(e)}

    async def cognitive_ingest(self, content: str, memory_type: str = None,
                               tags: List[str] = None, context: str = None,
                               force_create: bool = False) -> Dict:
        """Adaptive memory ingestion with Prediction-Error Gating.

        Replaces naive create_memory with a 3-path decision:
          CREATE    — content is novel  (nearest cosine < 0.75)
          UPDATE    — content refines   (cosine 0.75–0.949)
          SUPERSEDE — content replaces  (cosine >= 0.95)

        Setting force_create=True skips the comparison and always creates.

        Returns: action, memory_id, similarity (float), nearest_memory_id
        """
        try:
            action = "CREATE"
            nearest_id = None
            similarity = 0.0

            if not force_create:
                try:
                    emb = await self.embedding_service.generate_query_embedding(content)
                    if emb:
                        top = await self._search_ai_memories(emb, limit=1)
                        if top:
                            similarity = float(top[0].get("_raw_similarity",
                                                          top[0].get("similarity_score", 0.0)))
                            nearest_id = top[0].get("data", {}).get("memory_id")
                            if similarity >= 0.95:
                                action = "SUPERSEDE"
                            elif similarity >= 0.75:
                                action = "UPDATE"
                except Exception:
                    pass  # fallback to CREATE

            # Compute salience for auto-importance
            sal = await self.salience_score(content, context)
            auto_importance = sal.get("importance_suggested", 6)

            if action == "CREATE":
                result = await self.create_memory(
                    content=content,
                    memory_type=memory_type or "fact",
                    importance_level=auto_importance,
                    tags=tags or [],
                )
                return {
                    "status": "success",
                    "action": "CREATE",
                    "memory_id": result.get("memory_id"),
                    "similarity": similarity,
                    "importance_assigned": auto_importance,
                }

            elif action in ("UPDATE", "SUPERSEDE") and nearest_id:
                # Merge tags
                existing_rows = await self.ai_memory_db.execute_query(
                    "SELECT tags, importance_level FROM curated_memories WHERE memory_id = ?",
                    (nearest_id,)
                )
                existing_tags = []
                existing_importance = auto_importance
                if existing_rows:
                    row = dict(existing_rows[0])
                    try:
                        existing_tags = json.loads(row.get("tags") or "[]")
                    except Exception:
                        pass
                    existing_importance = row.get("importance_level", auto_importance)

                merged_tags = list(set(existing_tags + (tags or [])))
                new_importance = max(existing_importance, auto_importance)

                await self.ai_memory_db.execute_update(
                    "UPDATE curated_memories SET content=?, importance_level=?, tags=?, "
                    "last_accessed_at=? WHERE memory_id=?",
                    (content, new_importance, json.dumps(merged_tags),
                     get_current_timestamp(), nearest_id)
                )
                return {
                    "status": "success",
                    "action": action,
                    "memory_id": nearest_id,
                    "similarity": similarity,
                    "importance_assigned": new_importance,
                }

            # Fallback
            result = await self.create_memory(content=content,
                                              memory_type=memory_type or "fact",
                                              importance_level=auto_importance,
                                              tags=tags or [])
            return {"status": "success", "action": "CREATE",
                    "memory_id": result.get("memory_id"), "similarity": 0.0,
                    "importance_assigned": auto_importance}

        except Exception as e:
            logger.error(f"cognitive_ingest error: {e}")
            return {"status": "error", "message": str(e)}

    async def memory_chronicle(self, date_from: str = None, date_to: str = None,
                               limit: int = 50, tags_include: List[str] = None) -> Dict:
        """Browse memories chronologically grouped by day.

        date_from / date_to: ISO date strings (YYYY-MM-DD). Defaults to last 30 days.
        Returns a dict keyed by date with lists of compact memory entries.
        """
        try:
            from datetime import timedelta

            now = datetime.now(get_local_timezone())
            if not date_to:
                date_to = now.strftime("%Y-%m-%d")
            if not date_from:
                date_from = (now - timedelta(days=30)).strftime("%Y-%m-%d")

            rows = await self.ai_memory_db.execute_query(
                "SELECT memory_id, content, memory_type, importance_level, tags, "
                "timestamp_created FROM curated_memories "
                "WHERE SUBSTR(timestamp_created, 1, 10) >= ? AND SUBSTR(timestamp_created, 1, 10) <= ? "
                "ORDER BY timestamp_created DESC LIMIT ?",
                (date_from, date_to, limit)
            )

            grouped: Dict[str, list] = {}
            for row in (rows or []):
                row = dict(row)
                # tags filter
                if tags_include:
                    try:
                        row_tags = [t.lower() for t in json.loads(row.get("tags") or "[]")]
                    except Exception:
                        row_tags = []
                    if not any(t.lower() in row_tags for t in tags_include):
                        continue

                day_key = (row.get("timestamp_created") or "unknown")[:10]
                grouped.setdefault(day_key, []).append({
                    "id":         row.get("memory_id", "")[:8],
                    "type":       row.get("memory_type", ""),
                    "importance": row.get("importance_level", 5),
                    "content":    (row.get("content") or "")[:120],
                    "tags":       json.loads(row.get("tags") or "[]"),
                })

            return {
                "status": "success",
                "date_from": date_from,
                "date_to": date_to,
                "total": sum(len(v) for v in grouped.values()),
                "days": grouped,
            }
        except Exception as e:
            logger.error(f"memory_chronicle error: {e}")
            return {"status": "error", "message": str(e)}

    async def detect_redundancy(self, threshold: float = 0.88, limit: int = 20,
                                auto_merge: bool = False,
                                tags_include: List[str] = None) -> Dict:
        """Detect and optionally merge redundant memories.

        Loads embeddings for all memories (up to 500), computes pairwise cosine,
        groups pairs above `threshold` into clusters.

        When auto_merge=True: keeps the highest-importance memory per cluster
        and soft-deletes the rest (sets importance_level=0 and tags it 'merged').
        Returns the detected clusters with similarity scores.
        """
        try:
            rows = await self.ai_memory_db.execute_query(
                "SELECT memory_id, content, importance_level, tags, embedding "
                "FROM curated_memories WHERE embedding IS NOT NULL "
                "ORDER BY importance_level DESC, timestamp_created DESC LIMIT 500"
            )
            if not rows:
                return {"status": "success", "clusters": [], "total_redundant": 0}

            rows = list(rows)

            # tags filter
            if tags_include:
                _tag_set = {t.lower() for t in tags_include}
                filtered = []
                for row in rows:
                    try:
                        row_tags = {t.lower() for t in json.loads(row["tags"] or "[]")}
                    except Exception:
                        row_tags = set()
                    if row_tags & _tag_set:
                        filtered.append(row)
                rows = filtered

            if len(rows) < 2:
                return {"status": "success", "clusters": [], "total_redundant": 0}

            def _find_clusters(rows_inner, thresh):
                valid = [(r, np.frombuffer(r["embedding"], dtype=np.float32)) for r in rows_inner]
                n = len(valid)
                matrix = np.vstack([e for _, e in valid])
                norms = np.linalg.norm(matrix, axis=1)
                norms = np.where(norms < 1e-9, 1.0, norms)
                normed = matrix / norms[:, None]
                sim_matrix = normed @ normed.T

                visited = set()
                clusters = []
                for i in range(n):
                    if i in visited:
                        continue
                    cluster = [i]
                    for j in range(i + 1, n):
                        if j not in visited and float(sim_matrix[i, j]) >= thresh:
                            cluster.append(j)
                            visited.add(j)
                    if len(cluster) > 1:
                        visited.add(i)
                        clusters.append([
                            {"index": idx,
                             "memory_id": valid[idx][0]["memory_id"],
                             "importance": valid[idx][0]["importance_level"],
                             "content_preview": (valid[idx][0]["content"] or "")[:80],
                             "sim_to_centroid": round(float(sim_matrix[cluster[0]][idx]), 3)}
                            for idx in cluster
                        ])
                return clusters

            clusters = await asyncio.to_thread(_find_clusters, rows, threshold)

            merged_count = 0
            if auto_merge:
                for cluster in clusters:
                    sorted_c = sorted(cluster, key=lambda x: x["importance"], reverse=True)
                    to_delete = sorted_c[1:]  # keep highest importance
                    for item in to_delete:
                        await self.ai_memory_db.execute_update(
                            "UPDATE curated_memories SET importance_level=0, tags=JSON_INSERT(COALESCE(tags,'[]'), '$[#]', 'merged') "
                            "WHERE memory_id=?",
                            (item["memory_id"],)
                        )
                        merged_count += 1

            return {
                "status": "success",
                "clusters": clusters[:limit],
                "total_clusters": len(clusters),
                "total_redundant": sum(len(c) - 1 for c in clusters),
                "auto_merged": merged_count,
                "threshold_used": threshold,
            }
        except Exception as e:
            logger.error(f"detect_redundancy error: {e}")
            return {"status": "error", "message": str(e)}

    async def anticipate(self, context: str, limit: int = 5,
                         tags_include: List[str] = None) -> Dict:
        """Proactive memory retrieval — predict what is needed next.

        Combines current context with recent conversation to build a forward-looking
        query, then returns ranked memories with a brief 'why_relevant' annotation.
        Useful for pre-loading context before the user asks.
        """
        try:
            # Augment context with last conversation snippet
            recent = ""
            try:
                recent_rows = await self.conversations_db.execute_query(
                    "SELECT content FROM messages ORDER BY timestamp DESC LIMIT 3"
                )
                if recent_rows:
                    recent = " ".join((dict(r).get("content") or "")[:60] for r in recent_rows)
            except Exception:
                pass

            predictive_query = f"upcoming next needed: {context} {recent}".strip()

            result = await self.search_memories(
                query=predictive_query,
                limit=limit,
                compact=False,
                tags_include=tags_include,
            )

            memories = result.get("results", [])
            annotated = []
            for mem in memories:
                data = mem.get("data", {})
                score = mem.get("similarity_score", 0.0)
                content = (data.get("content") or "")[:100]
                mtype = data.get("memory_type", "")
                tags_list = data.get("tags", [])

                # Heuristic: explain why it's predicted relevant
                why = "matches current context"
                if score > 0.85:
                    why = "highly relevant to active context"
                elif mtype == "correction":
                    why = "past correction — likely to apply again"
                elif "decision" in mtype or "procedure" in mtype:
                    why = "known procedure for this task"
                elif tags_list and any(t.lower() in context.lower() for t in tags_list):
                    why = f"tagged with relevant topic: {tags_list[0]}"

                annotated.append({
                    "memory_id":    data.get("memory_id", "")[:8],
                    "content":      content,
                    "type":         mtype,
                    "score":        round(score, 3),
                    "why_relevant": why,
                    "tags":         tags_list,
                })

            return {
                "status":  "success",
                "context": context[:100],
                "predictions": annotated,
                "count":   len(annotated),
            }
        except Exception as e:
            logger.error(f"anticipate error: {e}")
            return {"status": "error", "message": str(e)}

    async def intent_anchor(self, trigger_condition: str, action: str,
                            importance_level: int = 7,
                            tags: List[str] = None) -> Dict:
        """Store a prospective memory: fires when trigger condition is semantically matched.

        Unlike time-based reminders, intent anchors are recalled when their
        trigger_condition is semantically similar to the current query/context.
        They surface automatically during prime_context and anticipate().

        Example: trigger_condition="about to push to production", action="run benchmark first"
        """
        try:
            content = json.dumps({
                "trigger": trigger_condition,
                "action":  action,
            }, ensure_ascii=False)

            result = await self.create_memory(
                content=content,
                memory_type="intent_anchor",
                importance_level=importance_level,
                tags=["intent_anchor"] + (tags or []),
            )
            return {
                "status":            "success",
                "intent_anchor_id":  result.get("memory_id"),
                "trigger_condition": trigger_condition,
                "action":            action,
            }
        except Exception as e:
            logger.error(f"intent_anchor error: {e}")
            return {"status": "error", "message": str(e)}

    async def synaptic_tagging(self, memory_id: str, boost: int = 1,
                               max_importance: int = 9, limit: int = 5,
                               tags_include: List[str] = None) -> Dict:
        """Retroactively elevate importance of memories related to a high-salience memory.

        When a memory is stored with high importance (≥9), this method finds the
        top semantically related memories and boosts their importance_level by
        `boost` points (default +1), capped at `max_importance` (default 9).

        This models the neuroscience concept of synaptic tagging: consolidating
        a strong memory also strengthens related contextual memories.

        Can be called manually for any memory_id, or fires automatically in
        background when create_memory is called with importance_level >= 9.

        Returns: {status, memory_id, boosted: [{id, old_importance, new_importance, content_preview}]}
        """
        try:
            # Load the source memory and its embedding
            rows = await self.ai_memory_db.execute_query(
                "SELECT memory_id, content, embedding, importance_level "
                "FROM curated_memories WHERE memory_id = ?",
                (memory_id,)
            )
            if not rows:
                return {"status": "error", "message": f"Memory {memory_id} not found"}

            source = dict(rows[0])
            if not source.get("embedding"):
                return {"status": "error", "message": "Source memory has no embedding yet — retry after background embed completes"}

            src_vec = np.frombuffer(source["embedding"], dtype=np.float32).copy()
            src_norm = float(np.linalg.norm(src_vec))
            if src_norm == 0:
                return {"status": "error", "message": "Source embedding is zero vector"}
            src_vec /= src_norm

            # Load candidate memories with embeddings (exclude source)
            query = (
                "SELECT memory_id, content, embedding, importance_level, tags "
                "FROM curated_memories "
                "WHERE embedding IS NOT NULL AND memory_id != ? AND "
                "COALESCE(importance_level, 1) < ?"
            )
            params = [memory_id, max_importance]
            candidates = await self.ai_memory_db.execute_query(query, tuple(params))

            if not candidates:
                return {"status": "success", "memory_id": memory_id, "boosted": [], "message": "No candidates found"}

            # Apply tags_include filter
            if tags_include:
                filtered = []
                for c in candidates:
                    try:
                        ctags = [t.lower() for t in json.loads(c["tags"] or "[]")]
                    except Exception:
                        ctags = []
                    if any(t.lower() in ctags for t in tags_include):
                        filtered.append(c)
                candidates = filtered

            if not candidates:
                return {"status": "success", "memory_id": memory_id, "boosted": [], "message": "No candidates after tag filter"}

            # Compute cosine similarities
            def _compute_sims():
                blobs = [c["embedding"] for c in candidates]
                matrix = np.vstack([np.frombuffer(b, dtype=np.float32) for b in blobs])
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                return (matrix / norms) @ src_vec  # (N,)

            sims = await asyncio.to_thread(_compute_sims)

            # Pick top-K above threshold 0.65
            THRESHOLD = 0.65
            indexed = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
            top = [(candidates[i], float(s)) for i, s in indexed if s >= THRESHOLD][:limit]

            if not top:
                return {"status": "success", "memory_id": memory_id, "boosted": [],
                        "message": f"No related memories above threshold {THRESHOLD}"}

            # Boost importance
            boosted = []
            for cand, sim in top:
                old_imp = int(cand["importance_level"] or 5)
                new_imp = min(old_imp + boost, max_importance)
                if new_imp > old_imp:
                    await self.ai_memory_db.execute_update(
                        "UPDATE curated_memories SET importance_level = ? WHERE memory_id = ?",
                        (new_imp, cand["memory_id"])
                    )
                    boosted.append({
                        "id":               cand["memory_id"][:8],
                        "old_importance":   old_imp,
                        "new_importance":   new_imp,
                        "similarity":       round(sim, 4),
                        "content_preview":  (cand["content"] or "")[:80],
                    })

            logger.info(
                f"synaptic_tagging: source={memory_id[:8]} boosted {len(boosted)} related memories"
            )
            return {
                "status":    "success",
                "memory_id": memory_id,
                "source_importance": int(source.get("importance_level") or 0),
                "boosted":   boosted,
                "candidates_evaluated": len(top),
            }
        except Exception as e:
            logger.error(f"synaptic_tagging error: {e}")
            return {"status": "error", "message": str(e)}


# =============================================================================
# MCP SERVER INTEGRATION (Optional - for Model Context Protocol support)
# =============================================================================

# The following code provides MCP server functionality when needed
# To use as MCP server, run: python ai_memory_core.py

async def main():
    """Main entry point - can be used for testing or as MCP server"""
    
    # Initialize the memory system
    memory = PersistentAIMemorySystem()
    
    # Example usage
    print("Persistent AI Memory System - Enhanced Version")
    print("=" * 50)
    
    # Test system health
    health = await memory.get_system_health()
    print(f"System Status: {health['status']}")
    print(f"Databases: {len(health['databases'])} active")
    
    # Test memory creation
    result = await memory.create_memory(
        "This is a test memory with high importance",
        memory_type="test",
        importance_level=8,
        tags=["test", "demo"]
    )
    print(f"Created memory: {result['memory_id']}")
    
    # Test search
    search_results = await memory.search_memories("test memory", limit=5)
    print(f"Found {search_results['count']} memories matching 'test memory'")
    
    print("\nMemory system is ready for use!")
    print("Features available:")
    print("   - 5 specialized databases")
    print("   - Vector semantic search")
    print("   - Real-time file monitoring")
    print("   - Schedule management")
    print("   - Project context tracking")
    print("   - MCP tool call logging")

if __name__ == "__main__":
    asyncio.run(main())
