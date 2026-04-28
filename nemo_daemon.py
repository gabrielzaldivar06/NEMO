#!/usr/bin/env python3
"""Background daemon for NEMO.

Runs periodic maintenance plus reflection-driven incremental learning even when
no interactive MCP session is active.
"""

import argparse
import asyncio
import json
import logging
import signal
import time
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ai_memory_core import PersistentAIMemorySystem


logger = logging.getLogger(__name__)


class JsonlAuditLogger:
    """Append structured daemon events to a JSONL audit file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def write_event(self, event_type: str, **payload) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event_type": event_type,
            **payload,
        }
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


AUDIT_LOGGER: JsonlAuditLogger | None = None


def configure_logging() -> Path:
    """Configure console + rotating file logging for daemon auditing."""
    global AUDIT_LOGGER
    project_dir = Path(__file__).resolve().parent
    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "nemo_daemon.log"
    jsonl_path = log_dir / "nemo_daemon.jsonl"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    AUDIT_LOGGER = JsonlAuditLogger(jsonl_path)
    logger.info("Daemon logging configured at %s", log_path)
    logger.info("Daemon JSONL audit configured at %s", jsonl_path)
    AUDIT_LOGGER.write_event("daemon_logging_configured", log_path=str(log_path), jsonl_path=str(jsonl_path))
    return log_path


def log_audit(event_type: str, **payload) -> None:
    if AUDIT_LOGGER is None:
        return
    AUDIT_LOGGER.write_event(event_type, **payload)


def summarize_learning_result(result: dict) -> str:
    learned_patterns = result.get("learned_patterns") or []
    runtime_adjustments = result.get("runtime_adjustments") or {}
    applied = runtime_adjustments.get("applied") or {}

    pattern_summary = ", ".join(
        f"{item.get('signal')} x{item.get('frequency')}"
        for item in learned_patterns[:5]
    ) or "none"
    adjustment_summary = ", ".join(
        f"{key}={value}"
        for key, value in applied.items()
    ) or "none"

    return (
        f"learned_patterns=[{pattern_summary}] | "
        f"applied_adjustments=[{adjustment_summary}]"
    )


class NEMODaemon:
    def __init__(
        self,
        maintenance_interval_seconds: int = 3 * 60 * 60,
        reflection_interval_seconds: int = 60 * 60,
        learning_interval_seconds: int = 2 * 60 * 60,
        reflection_window_days: int = 7,
    ):
        self.memory_system = PersistentAIMemorySystem()
        self.maintenance_interval_seconds = maintenance_interval_seconds
        self.reflection_interval_seconds = reflection_interval_seconds
        self.learning_interval_seconds = learning_interval_seconds
        self.reflection_window_days = reflection_window_days
        self._shutdown = asyncio.Event()
        self._tasks = []

    def _log_cycle_header(self, name: str) -> None:
        logger.info("========== %s cycle ==========" , name.upper())

    def _log_cycle_footer(self, name: str) -> None:
        logger.info("========== end %s cycle ==========" , name.upper())

    async def _run_loop(self, name: str, worker, interval_seconds: int, initial_delay_seconds: int = 5):
        await asyncio.sleep(max(0, initial_delay_seconds))
        while not self._shutdown.is_set():
            started = time.perf_counter()
            try:
                self._log_cycle_header(name)
                logger.info("[%s] cycle started", name)
                log_audit("cycle_started", cycle=name, interval_seconds=interval_seconds)
                result = await worker()
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                if name == "learning" and isinstance(result, dict):
                    logger.info("[learning] summary | %s", summarize_learning_result(result))
                logger.info("[%s] cycle finished | elapsed_ms=%s | result=%s", name, elapsed_ms, result)
                log_audit("cycle_finished", cycle=name, elapsed_ms=elapsed_ms, result=result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[%s] cycle failed: %s", name, exc)
                log_audit("cycle_failed", cycle=name, error=str(exc))
            finally:
                self._log_cycle_footer(name)

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _maintenance_worker(self):
        return await self.memory_system.run_database_maintenance(force=False)

    async def _reflection_worker(self):
        return await self.memory_system.reflect_on_tool_usage(days=self.reflection_window_days)

    async def _learning_worker(self):
        return await self.memory_system.run_incremental_learning_cycle(days=self.reflection_window_days)

    async def start(self):
        logger.info("Starting NEMO daemon")
        log_audit("daemon_starting")
        logger.info(
            "Intervals configured | maintenance=%ss reflection=%ss learning=%ss days=%s",
            self.maintenance_interval_seconds,
            self.reflection_interval_seconds,
            self.learning_interval_seconds,
            self.reflection_window_days,
        )
        try:
            adjustments = await self.memory_system.apply_reflection_learnings(days=self.reflection_window_days)
            logger.info("[startup] applied reflection learnings: %s", adjustments)
            log_audit("startup_reflection_learning_applied", adjustments=adjustments)
        except Exception as exc:
            logger.warning("[startup] failed to apply reflection learnings: %s", exc)
            log_audit("startup_reflection_learning_failed", error=str(exc))
        self._tasks = [
            asyncio.create_task(
                self._run_loop("maintenance", self._maintenance_worker, self.maintenance_interval_seconds, 15),
                name="nemo-daemon-maintenance",
            ),
            asyncio.create_task(
                self._run_loop("reflection", self._reflection_worker, self.reflection_interval_seconds, 30),
                name="nemo-daemon-reflection",
            ),
            asyncio.create_task(
                self._run_loop("learning", self._learning_worker, self.learning_interval_seconds, 45),
                name="nemo-daemon-learning",
            ),
        ]

        await self._shutdown.wait()

    async def stop(self):
        if self._shutdown.is_set():
            return
        logger.info("Stopping NEMO daemon")
        log_audit("daemon_stopping")
        self._shutdown.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.memory_system.close()
        log_audit("daemon_stopped")


async def _main_async(args):
    daemon = NEMODaemon(
        maintenance_interval_seconds=args.maintenance_interval,
        reflection_interval_seconds=args.reflection_interval,
        learning_interval_seconds=args.learning_interval,
        reflection_window_days=args.days,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(daemon.stop()))

    try:
        await daemon.start()
    finally:
        await daemon.stop()


def build_parser():
    parser = argparse.ArgumentParser(description="Run the NEMO background daemon")
    parser.add_argument("--maintenance-interval", type=int, default=3 * 60 * 60, help="Seconds between maintenance cycles")
    parser.add_argument("--reflection-interval", type=int, default=60 * 60, help="Seconds between reflection cycles")
    parser.add_argument("--learning-interval", type=int, default=2 * 60 * 60, help="Seconds between incremental learning cycles")
    parser.add_argument("--days", type=int, default=7, help="Lookback window for reflection analysis")
    return parser


def cli():
    args = build_parser().parse_args()
    configure_logging()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    cli()