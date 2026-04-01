#!/usr/bin/env python3
"""Competitive benchmark suite for Persistent AI Memory System.

This suite aligns NEMO with the public benchmark categories emphasized by
Mem0 and Zep:

* Top-1 accuracy
* Recall@k
* MRR
* Median retrieval latency
* P95 retrieval latency
* End-to-end latency
* Tokens per query / conversation
* Accuracy vs context size
* Accuracy vs retrieval latency
* Adversarial hit rate / imposter intercept rate

The suite reuses the existing benchmark profiles already in this repository and
adds a production-like context sweep to expose the accuracy/latency/context
frontier in a single report.

Usage examples:

  python examples/benchmark_nemo_suite.py
  python examples/benchmark_nemo_suite.py --preset full --keep-temp-data
  python examples/benchmark_nemo_suite.py --sweep-limits 1,3,5,10,15

Optional answer-generation stage for true end-to-end latency:

  set NEMO_BENCH_CHAT_BASE_URL=http://localhost:1234/v1
  set NEMO_BENCH_CHAT_MODEL=gpt-4.1-mini
  set NEMO_BENCH_CHAT_API_KEY=local-or-real-key
  python examples/benchmark_nemo_suite.py --enable-answer-stage

If the answer stage is not configured, the suite still reports end-to-end
latency as retrieval + context assembly, which is useful for comparing memory
layer efficiency independent of a downstream chat model.
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings

from benchmark_memory import run_benchmark as run_memory_benchmark
from benchmark_memory2 import run_benchmark as run_entropy_benchmark
from benchmark_prod import PROD_ANCHORS, populate as populate_prod_corpus


async def _prewarm_embedding_provider() -> bool:
    """Sprint A E3 — Reset circuit-breaker and confirm embedding provider health.

    After heavy benchmark phases (e.g. stress with 5K memories), the embedding
    provider may sit in a 45s cooldown.  This function creates a throwaway
    PersistentAIMemorySystem, clears the cooldown timestamps, executes a single
    warm-up embedding call, and reports whether the provider is alive.

    Returns True if the provider responded successfully, False otherwise.
    """
    print("[suite] Pre-warming embedding provider between phases...")
    try:
        mem = PersistentAIMemorySystem(enable_file_monitoring=False)
        # Clear any circuit-breaker cooldowns and failure counts (Sprint B — B1)
        mem.embedding_service._embed_retry_after.clear()
        mem.embedding_service._embed_failure_count.clear()
        # Single lightweight embedding call to verify provider health
        result = await mem.embedding_service.generate_embedding("benchmark warmup probe")
        alive = bool(result)
        if alive:
            print("[suite] Embedding provider is healthy.")
        else:
            print("[suite] WARNING: Embedding provider returned empty — phase may fall back to text search.")
        await mem.close()
        return alive
    except Exception as e:
        print(f"[suite] WARNING: Embedding pre-warm failed: {e}")
        return False


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


class TokenEstimator:
    """Best-effort token counting.

    We intentionally avoid a hard dependency on provider-specific tokenizers so
    the suite remains runnable on any installation. Counts are deterministic and
    good enough for benchmark comparisons. The report labels them as estimates.
    """

    _TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_:/.-]+|[^\w\s]", re.UNICODE)

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._TOKEN_PATTERN.findall(text))


class AnswerStageClient:
    """Optional OpenAI-compatible answer-generation client."""

    def __init__(self, base_url: str, model: str, api_key: str, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "AnswerStageClient | None":
        base_url = os.getenv("NEMO_BENCH_CHAT_BASE_URL", "").strip()
        model = os.getenv("NEMO_BENCH_CHAT_MODEL", "").strip()
        api_key = os.getenv("NEMO_BENCH_CHAT_API_KEY", "").strip() or "local-key"
        if not base_url or not model:
            return None
        return cls(base_url=base_url, model=model, api_key=api_key)

    async def generate(self, query: str, context_block: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are answering using a memory retrieval benchmark context. "
                        "Use only the provided context facts. If the answer is missing, say so briefly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {query}\n\n"
                        f"Context:\n{context_block}\n\n"
                        "Answer in 2-4 concise sentences."
                    ),
                },
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            started = time.perf_counter()
            async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                response.raise_for_status()
                body = await response.json()
            elapsed_ms = (time.perf_counter() - started) * 1000

        choice = ((body.get("choices") or [{}])[0] or {}).get("message", {})
        usage = body.get("usage") or {}
        return {
            "latency_ms": elapsed_ms,
            "content": choice.get("content", ""),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        }


def expand_queries(queries: list[dict[str, Any]], multiplier: float = 1.0) -> list[dict[str, Any]]:
    if multiplier <= 1.0 or not queries:
        return list(queries)

    expanded = list(queries)
    base_count = len(queries)
    target_count = max(base_count, int(round(base_count * multiplier)))
    extra_count = target_count - base_count

    for extra_index in range(extra_count):
        source_index = int(extra_index * base_count / extra_count)
        source = dict(queries[source_index])
        source["repeat_index"] = extra_index + 1
        expanded.append(source)

    return expanded


def build_prod_queries(anchor_ids: list[str], query_multiplier: float = 1.0) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for index, anchor in enumerate(PROD_ANCHORS):
        queries.append(
            {
                "text": anchor["query_clean"],
                "category": "clean",
                "anchor_id": anchor_ids[index],
            }
        )
        queries.append(
            {
                "text": anchor["query_confusory"],
                "category": "confusory",
                "anchor_id": anchor_ids[index],
            }
        )
    return expand_queries(queries, multiplier=query_multiplier)


def assemble_context_block(ai_results: list[dict[str, Any]]) -> str:
    blocks = []
    for index, result in enumerate(ai_results, start=1):
        data = result.get("data", {})
        score = result.get("similarity_score", 0.0)
        blocks.append(
            "\n".join(
                [
                    f"[rank={index} score={score:.4f}]",
                    data.get("content", ""),
                    f"tags={','.join(map(str, data.get('tags', [])))}",
                ]
            )
        )
    return "\n\n".join(blocks)


async def run_context_sweep(
    sweep_limits: list[int],
    keep_temp_data: bool,
    answer_client: AnswerStageClient | None,
    query_multiplier: float,
) -> dict[str, Any]:
    benchmark_dir = Path(tempfile.mkdtemp(prefix="pam_benchmark_suite_sweep_"))
    settings = MemorySettings(data_dir=benchmark_dir, enable_file_monitoring=False)
    memory_system = PersistentAIMemorySystem(settings=settings, enable_file_monitoring=False)
    token_estimator = TokenEstimator()

    try:
        health = await memory_system.get_system_health()
        if health.get("embedding_service", {}).get("status") != "healthy":
            raise RuntimeError(f"Embedding service unavailable: {health.get('embedding_service')}")

        anchor_ids, imposter_ids, store_latencies = await populate_prod_corpus(memory_system)
        queries = build_prod_queries(anchor_ids, query_multiplier=query_multiplier)

        sweep_points = []
        for limit in sweep_limits:
            retrieval_latencies = []
            e2e_latencies = []
            query_token_counts = []
            context_token_counts = []
            prompt_token_counts = []
            completion_token_counts = []
            total_token_counts = []
            top1_hits = 0
            recall_hits = 0
            reciprocal_ranks = []
            clean_hits = 0
            confusory_hits = 0
            imposter_hits = 0

            for query in queries:
                total_started = time.perf_counter()
                retrieval_started = time.perf_counter()
                response = await memory_system.search_memories(
                    query["text"],
                    limit=limit,
                    database_filter="ai_memories",
                )
                retrieval_elapsed_ms = (time.perf_counter() - retrieval_started) * 1000
                retrieval_latencies.append(retrieval_elapsed_ms)

                ai_results = [r for r in response.get("results", []) if r.get("type") == "ai_memory"]
                ranked_ids = [r.get("data", {}).get("memory_id") for r in ai_results]
                first_match_rank = next(
                    (index + 1 for index, memory_id in enumerate(ranked_ids) if memory_id == query["anchor_id"]),
                    None,
                )

                if first_match_rank == 1:
                    top1_hits += 1
                    if query["category"] == "clean":
                        clean_hits += 1
                    else:
                        confusory_hits += 1

                if first_match_rank is not None and first_match_rank <= limit:
                    recall_hits += 1
                reciprocal_ranks.append(1.0 / first_match_rank if first_match_rank else 0.0)

                if ranked_ids and ranked_ids[0] in imposter_ids:
                    imposter_hits += 1

                context_block = assemble_context_block(ai_results)
                query_tokens = token_estimator.count(query["text"])
                context_tokens = token_estimator.count(context_block)
                query_token_counts.append(query_tokens)
                context_token_counts.append(context_tokens)

                prompt_tokens = query_tokens + context_tokens
                completion_tokens = 0
                total_tokens = prompt_tokens

                if answer_client is not None:
                    answer_response = await answer_client.generate(query["text"], context_block)
                    usage = answer_response["usage"]
                    if usage.get("prompt_tokens") is not None:
                        prompt_tokens = int(usage["prompt_tokens"])
                    if usage.get("completion_tokens") is not None:
                        completion_tokens = int(usage["completion_tokens"])
                    else:
                        completion_tokens = token_estimator.count(answer_response.get("content", ""))
                    if usage.get("total_tokens") is not None:
                        total_tokens = int(usage["total_tokens"])
                    else:
                        total_tokens = prompt_tokens + completion_tokens

                prompt_token_counts.append(prompt_tokens)
                completion_token_counts.append(completion_tokens)
                total_token_counts.append(total_tokens)
                e2e_latencies.append((time.perf_counter() - total_started) * 1000)

            point = {
                "limit": limit,
                "query_count": len(queries),
                "top1_accuracy": round(top1_hits / len(queries), 4),
                "recall_at_limit": round(recall_hits / len(queries), 4),
                "mrr": round(sum(reciprocal_ranks) / len(queries), 4),
                "adversarial_hit_rate": round(confusory_hits / (len(queries) // 2), 4),
                "imposter_intercept_rate": round(imposter_hits / len(queries), 4),
                "clean_top1_accuracy": round(clean_hits / (len(queries) // 2), 4),
                "median_latency_ms": round(statistics.median(retrieval_latencies), 2),
                "p95_latency_ms": round(percentile(retrieval_latencies, 0.95), 2),
                "end_to_end_latency_ms": {
                    "mode": (
                        "retrieval_plus_answer_generation"
                        if answer_client is not None
                        else "retrieval_plus_context_assembly"
                    ),
                    "median": round(statistics.median(e2e_latencies), 2),
                    "p95": round(percentile(e2e_latencies, 0.95), 2),
                },
                "token_metrics": {
                    "mode": "provider_usage" if answer_client is not None else "estimated",
                    "avg_query_tokens": round(statistics.mean(query_token_counts), 2),
                    "avg_context_tokens": round(statistics.mean(context_token_counts), 2),
                    "avg_prompt_tokens": round(statistics.mean(prompt_token_counts), 2),
                    "avg_completion_tokens": round(statistics.mean(completion_token_counts), 2),
                    "avg_total_tokens": round(statistics.mean(total_token_counts), 2),
                },
            }
            sweep_points.append(point)

        return {
            "benchmark_data_dir": str(benchmark_dir),
            "store_latency_ms": {
                "avg": round(statistics.mean(store_latencies), 2),
                "median": round(statistics.median(store_latencies), 2),
            },
            "points": sweep_points,
            "accuracy_vs_context_size": [
                {
                    "limit": point["limit"],
                    "accuracy": point["top1_accuracy"],
                    "avg_context_tokens": point["token_metrics"]["avg_context_tokens"],
                    "avg_total_tokens": point["token_metrics"]["avg_total_tokens"],
                }
                for point in sweep_points
            ],
            "accuracy_vs_retrieval_latency": [
                {
                    "limit": point["limit"],
                    "accuracy": point["top1_accuracy"],
                    "median_latency_ms": point["median_latency_ms"],
                    "p95_latency_ms": point["p95_latency_ms"],
                }
                for point in sweep_points
            ],
        }
    finally:
        if not keep_temp_data and benchmark_dir.exists():
            shutil.rmtree(benchmark_dir, ignore_errors=True)


def build_scorecard(results: dict[str, Any], context_sweep: dict[str, Any]) -> dict[str, Any]:
    production_metrics = results["production"]["metrics"]
    entropy_metrics = results["entropy"]["metrics"]
    baseline_metrics = results["baseline"]["metrics"]
    best_frontier = max(context_sweep["points"], key=lambda point: point["top1_accuracy"])

    return {
        "top1_accuracy": {
            "baseline": baseline_metrics["top1_accuracy"],
            "production": production_metrics["top1_global"],
            "entropy": entropy_metrics["top1_accuracy"],
        },
        "recall_at_k": {
            "baseline_recall_at_5": baseline_metrics["recall_at_5"],
            "entropy_recall_at_10": entropy_metrics["recall_at_10"],
            "best_sweep_recall_at_limit": best_frontier["recall_at_limit"],
            "best_sweep_limit": best_frontier["limit"],
        },
        "mrr": {
            "baseline": baseline_metrics["mrr"],
            "production": production_metrics["mrr"],
            "entropy": entropy_metrics["mrr"],
        },
        "median_latency_ms": {
            "baseline": baseline_metrics["median_search_latency_ms"],
            "production": production_metrics["p50_latency_ms"],
            "entropy": entropy_metrics["median_search_latency_ms"],
        },
        "p95_latency_ms": {
            "baseline": baseline_metrics["p95_search_latency_ms"],
            "production": production_metrics["p95_latency_ms"],
            "entropy": entropy_metrics["p95_search_latency_ms"],
        },
        "end_to_end_latency": {
            "mode": best_frontier["end_to_end_latency_ms"]["mode"],
            "median_ms": best_frontier["end_to_end_latency_ms"]["median"],
            "p95_ms": best_frontier["end_to_end_latency_ms"]["p95"],
        },
        "tokens_per_query": {
            "mode": best_frontier["token_metrics"]["mode"],
            "avg_query_tokens": best_frontier["token_metrics"]["avg_query_tokens"],
            "avg_context_tokens": best_frontier["token_metrics"]["avg_context_tokens"],
            "avg_total_tokens": best_frontier["token_metrics"]["avg_total_tokens"],
        },
        "accuracy_vs_context_size": context_sweep["accuracy_vs_context_size"],
        "accuracy_vs_retrieval_latency": context_sweep["accuracy_vs_retrieval_latency"],
        "adversarial_metrics": {
            "production_adversarial_hit_rate": best_frontier["adversarial_hit_rate"],
            "production_imposter_intercept_rate": best_frontier["imposter_intercept_rate"],
            "entropy_top1_adversarial": entropy_metrics["top1_adversarial"],
            "entropy_imposter_intercept_rate": entropy_metrics["imposter_intercept_rate"],
        },
    }


async def run_suite(
    preset: str,
    keep_temp_data: bool,
    sweep_limits: list[int],
    enable_answer_stage: bool,
    output_dir: Path,
    query_multiplier: float,
) -> dict[str, Any]:
    answer_client = AnswerStageClient.from_env() if enable_answer_stage else None
    if enable_answer_stage and answer_client is None:
        raise RuntimeError(
            "Answer stage requested but NEMO_BENCH_CHAT_BASE_URL and NEMO_BENCH_CHAT_MODEL are not configured."
        )

    # Quick preset: small baseline (50 memories), skip stress, mini sweep
    quick_mode = preset == "quick"
    baseline_corpus = 50 if quick_mode else None  # None → profile default (240)
    print(f"[suite] Running baseline benchmark ({baseline_corpus or 240} memories)...")
    baseline_summary = await run_memory_benchmark(
        keep_data=keep_temp_data,
        profile="baseline",
        limit=5,
        corpus_size=baseline_corpus,
        batch_size=None,
        concurrency=None,
        query_mode="all",
        query_multiplier=query_multiplier,
    )

    stress_summary = None
    if preset == "full":
        await _prewarm_embedding_provider()  # Sprint A E3
        print("[suite] Running stress benchmark for large noisy corpus behavior...")
        stress_summary = await run_memory_benchmark(
            keep_data=keep_temp_data,
            profile="stress",
            limit=10,
            corpus_size=5000,
            batch_size=100,
            concurrency=8,
            query_mode="all",
            query_multiplier=query_multiplier,
        )
    elif not quick_mode:
        pass  # demo mode: skip stress silently

    await _prewarm_embedding_provider()  # Sprint A E3
    print("[suite] Running production benchmark for compact, realistic retrieval quality...")
    from benchmark_prod import run_benchmark as run_production_benchmark

    production_summary = await run_production_benchmark(
        limit=10,
        keep_data=keep_temp_data,
        query_multiplier=query_multiplier,
    )

    await _prewarm_embedding_provider()  # Sprint A E3
    print("[suite] Running entropy benchmark for adversarial ranking behavior...")
    entropy_summary = await run_entropy_benchmark(
        keep_data=keep_temp_data,
        limit=10,
        query_multiplier=query_multiplier,
    )

    await _prewarm_embedding_provider()  # Sprint A E3
    effective_sweep_limits = [1, 5] if quick_mode else sweep_limits
    print(f"[suite] Running context sweep (limits={effective_sweep_limits})...")
    context_sweep = await run_context_sweep(
        sweep_limits=effective_sweep_limits,
        keep_temp_data=keep_temp_data,
        answer_client=answer_client,
        query_multiplier=query_multiplier,
    )

    suite_payload = {
        "suite": "nemo_competitive_benchmark",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preset": preset,
        "query_multiplier": query_multiplier,
        "answer_stage_enabled": answer_client is not None,
        "runs": {
            "baseline": baseline_summary,
            "production": production_summary,
            "entropy": entropy_summary,
        },
        "context_sweep": context_sweep,
    }
    if stress_summary is not None:
        suite_payload["runs"]["stress"] = stress_summary

    suite_payload["scorecard"] = build_scorecard(suite_payload["runs"], context_sweep)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"nemo_benchmark_suite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(suite_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    suite_payload["output_path"] = str(output_path)

    print("\n[suite] Benchmark suite complete")
    print(f"[suite] Report: {output_path}")
    print("[suite] Scorecard summary:")
    print(json.dumps(suite_payload["scorecard"], indent=2, ensure_ascii=True))
    return suite_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competitive benchmark suite for Persistent AI Memory")
    parser.add_argument(
        "--preset",
        choices=["quick", "demo", "full"],
        default="demo",
        help=(
            "quick = small baseline (50 mem) + production + entropy + mini sweep (~5 min); "
            "demo = baseline (240 mem) + production + entropy + context sweep (~20 min); "
            "full = demo + large stress profile (5K mem) (~40 min)"
        ),
    )
    parser.add_argument(
        "--sweep-limits",
        default="1,3,5,10",
        help="Comma-separated result limits for the context sweep",
    )
    parser.add_argument(
        "--keep-temp-data",
        action="store_true",
        help="Keep temporary benchmark data directories created by the suite",
    )
    parser.add_argument(
        "--enable-answer-stage",
        action="store_true",
        help="Include downstream answer generation for true end-to-end latency if an OpenAI-compatible chat endpoint is configured",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks",
        help="Directory where the consolidated JSON report will be written",
    )
    parser.add_argument(
        "--query-multiplier",
        type=float,
        default=1.0,
        help="Multiply benchmark query volume while keeping the same corpus and metrics definitions",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sweep_limits = [int(item.strip()) for item in args.sweep_limits.split(",") if item.strip()]
    asyncio.run(
        run_suite(
            preset=args.preset,
            keep_temp_data=args.keep_temp_data,
            sweep_limits=sweep_limits,
            enable_answer_stage=args.enable_answer_stage,
            output_dir=Path(args.output_dir),
            query_multiplier=max(1.0, args.query_multiplier),
        )
    )


if __name__ == "__main__":
    main()