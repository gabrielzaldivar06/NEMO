"""
Sprint 2 — Unit tests for Sprint 1 features + Sprint 2 additions.

Tests:
  T1a  compact=True in search_memories (main semantic path)
  T1b  compact=True falls back through _text_based_search
  T1c  prime_context returns expected structure
  T1d  prime_context accepts topic param (narrowed query)
  T2a  update_memory: content update
  T2b  update_memory: importance + tags update
  T2c  update_memory: no fields → returns error
  T2d  update_memory: unknown memory_id → returns error
  T3   close() exists and is awaitable

All tests use isolated in-memory / temp SQLite databases (no production data).
Embeddings irrelevant → EmbeddingService stubbed to return None (forces text fallback).
"""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings() -> MemorySettings:
    """Create a MemorySettings object pointing to a temporary directory."""
    tmpdir = tempfile.mkdtemp(prefix="nemo_sprint2_test_")
    return MemorySettings(data_dir=tmpdir, enable_file_monitoring=False)


def _make_system(settings: Settings) -> PersistentAIMemorySystem:
    """Instantiate system with embedding + reranking stubbed out."""
    sys_obj = PersistentAIMemorySystem(settings=settings, enable_file_monitoring=False)

    # Stub embedding service so we don't need a live LM Studio
    mock_embed = AsyncMock()
    mock_embed.generate_embedding = AsyncMock(return_value=None)  # forces text fallback
    sys_obj.embedding_service = mock_embed

    mock_rerank = MagicMock()
    mock_rerank.rerank = AsyncMock(return_value=None)
    sys_obj.reranking_service = mock_rerank

    return sys_obj


async def _seed_memory(ms: PersistentAIMemorySystem, content: str,
                       importance: int = 8, tags: list = None) -> str:
    """Insert a memory directly into the DB and return its memory_id."""
    mid = await ms.ai_memory_db.create_memory(
        content=content,
        memory_type="preference",
        importance_level=importance,
        tags=tags or ["test"],
    )
    return mid


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCompactFormat(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.settings = _make_settings()
        self.ms = _make_system(self.settings)

    async def asyncSetUp(self):
        await _seed_memory(self.ms, "User prefers dark mode everywhere", importance=8, tags=["ui"])
        await _seed_memory(self.ms, "Project NEMO uses SQLite for persistence", importance=9, tags=["nemo", "db"])

    async def test_T1a_compact_true_returns_strings(self):
        """compact=True must return strings, not dicts."""
        result = await self.ms.search_memories(query="dark mode", compact=True)
        self.assertEqual(result.get("compact"), True)
        for item in result["results"]:
            self.assertIsInstance(item, str, msg=f"Expected string, got {type(item)}: {item}")

    async def test_T1a_compact_false_returns_dicts(self):
        """compact=False must return raw result dicts."""
        result = await self.ms.search_memories(query="dark mode", compact=False)
        self.assertNotEqual(result.get("compact"), True)
        for item in result["results"]:
            self.assertIsInstance(item, dict, msg=f"Expected dict, got {type(item)}: {item}")

    async def test_T1a_compact_string_format(self):
        """Compact strings must follow '[score|imp:N|type] snippet (date)' pattern."""
        result = await self.ms.search_memories(query="nemo sqlite", compact=True)
        for line in result["results"]:
            self.assertTrue(
                line.startswith("["),
                msg=f"Compact string missing '[' prefix: {line!r}",
            )
            self.assertIn("|imp:", line, msg=f"Compact string missing 'imp:' field: {line!r}")

    async def test_T1b_compact_through_text_fallback(self):
        """compact=True must also work when embedding returns None (text-based fallback)."""
        # embedding already stubbed to None in setUp
        result = await self.ms.search_memories(query="dark mode", compact=True)
        self.assertEqual(result.get("compact"), True)
        for item in result["results"]:
            self.assertIsInstance(item, str)


class TestPrimeContext(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.settings = _make_settings()
        self.ms = _make_system(self.settings)

    async def test_T1c_returns_expected_keys(self):
        """prime_context must return status, primed_at, memories, reminders, last_session, hint."""
        result = await self.ms.prime_context()
        for key in ("status", "primed_at", "memories", "reminders", "hint"):
            self.assertIn(key, result, msg=f"prime_context missing key: {key}")
        self.assertEqual(result["status"], "success")

    async def test_T1d_topic_param_accepted(self):
        """prime_context(topic=...) must not raise and must return status=success."""
        result = await self.ms.prime_context(topic="NEMO dev sprint")
        self.assertEqual(result["status"], "success")
        # memories should be a list (possibly empty in test env)
        self.assertIsInstance(result.get("memories"), list)


class TestUpdateMemory(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.settings = _make_settings()
        self.ms = _make_system(self.settings)

    async def asyncSetUp(self):
        self.mid = await _seed_memory(
            self.ms,
            "Original content about project X",
            importance=5,
            tags=["project"],
        )

    async def test_T2a_content_update(self):
        """update_memory should update content and return success."""
        result = await self.ms.update_memory(self.mid, content="Updated content about project X v2")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["memory_id"], self.mid)
        # Verify DB was actually updated
        rows = await self.ms.ai_memory_db.execute_query(
            "SELECT content FROM curated_memories WHERE memory_id = ?", (self.mid,)
        )
        self.assertEqual(rows[0]["content"], "Updated content about project X v2")

    async def test_T2b_importance_and_tags_update(self):
        """update_memory should update importance_level and tags."""
        result = await self.ms.update_memory(self.mid, importance_level=9, tags=["project", "critical"])
        self.assertEqual(result["status"], "success")
        rows = await self.ms.ai_memory_db.execute_query(
            "SELECT importance_level, tags FROM curated_memories WHERE memory_id = ?", (self.mid,)
        )
        self.assertEqual(rows[0]["importance_level"], 9)
        stored_tags = json.loads(rows[0]["tags"])
        self.assertIn("critical", stored_tags)

    async def test_T2c_no_fields_returns_error(self):
        """update_memory with no fields should return status=error, not raise."""
        result = await self.ms.update_memory(self.mid)
        self.assertEqual(result["status"], "error")

    async def test_T2d_unknown_id_returns_error(self):
        """update_memory with a nonexistent memory_id should return status=error."""
        result = await self.ms.update_memory("nonexistent-id-000", content="whatever")
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result.get("message", "").lower())


class TestClose(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.settings = _make_settings()
        self.ms = _make_system(self.settings)

    async def test_T3_close_is_awaitable(self):
        """close() must exist and be awaitable without raising."""
        self.assertTrue(asyncio.iscoroutinefunction(self.ms.close))
        await self.ms.close()  # should not raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
