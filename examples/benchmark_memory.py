#!/usr/bin/env python3
"""Benchmark de memoria semantica para Persistent AI Memory System.

Soporta dos perfiles:
- baseline: corrida corta y estratificada para comparar modelos rapidamente.
- stress: corrida grande y ruidosa para medir ranking bajo ambiguedad.
"""

import argparse
import asyncio
import json
import random
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings


ANCHOR_MEMORIES = [
    {
        "key": "tz_windows_fix",
        "content": "En Windows corregimos el problema de timezone usando datetime.now().astimezone().tzinfo y UTC como fallback para evitar errores con ZoneInfo.",
        "memory_type": "project_decision",
        "importance_level": 10,
        "tags": ["windows", "timezone", "bugfix", "python"],
        "query_variants": [
            "como arreglamos el timezone en windows",
            "como resolvimos el error de zona horaria en winodws",
            "fix del timezone fallback para windows",
        ],
    },
    {
        "key": "lmstudio_endpoint",
        "content": "El proveedor local de embeddings usa la base URL http://localhost:1234 y el cliente agrega internamente /v1/embeddings.",
        "memory_type": "configuration",
        "importance_level": 9,
        "tags": ["lm_studio", "embeddings", "endpoint", "configuration"],
        "query_variants": [
            "cual es el endpoint local de embeddings",
            "localhost 1234 embeddings endpoint real",
            "que url usa lm sutdio para embeddings",
        ],
    },
    {
        "key": "qwen_identifier",
        "content": "El identificador cargado en LM Studio para embeddings es qwen3-embed-4b y se configura como modelo principal del proyecto.",
        "memory_type": "configuration",
        "importance_level": 10,
        "tags": ["qwen3", "lm_studio", "embedding_model"],
        "query_variants": [
            "que modelo de embeddings quedo cargado",
            "identificador del modelo qwen de embeddings",
            "como se llama el modelo qewn3 embed 4b en lm studio",
        ],
    },
    {
        "key": "ps1_fallback",
        "content": "El script start_qwen_embedding_server.ps1 usa lms.exe automaticamente cuando llama-server no esta en PATH y deja el servidor listo en localhost:1234.",
        "memory_type": "operations",
        "importance_level": 8,
        "tags": ["powershell", "lm_studio", "llama_cpp", "startup"],
        "query_variants": [
            "como arranca powershell si no existe llama-server",
            "script ps1 fallback a lms.exe",
            "como inicia el servidor con poweshell cuando falta llama server",
        ],
    },
    {
        "key": "health_check",
        "content": "La prueba tests/test_health_check.py valida imports, archivos JSON, inicializacion de bases de datos y conectividad del proveedor de embeddings.",
        "memory_type": "testing",
        "importance_level": 8,
        "tags": ["testing", "health_check", "validation"],
        "query_variants": [
            "que valida el health check",
            "para que sirve tests test health check py",
            "q valida el helth chekc del sistema",
        ],
    },
    {
        "key": "mcp_entrypoint",
        "content": "El entrypoint instalable del servidor MCP es pams-server y arranca ai_memory_mcp_server usando stdio para clientes MCP.",
        "memory_type": "integration",
        "importance_level": 8,
        "tags": ["mcp", "packaging", "entrypoint", "stdio"],
        "query_variants": [
            "como se lanza el servidor mcp instalable",
            "entrypoint del mcp server",
            "como arrancar pams sevrer",
        ],
    },
    {
        "key": "semantic_search",
        "content": "search_memories hace busqueda semantica sobre memorias, conversaciones, agenda y contexto de proyecto, y ordena el ranking por similarity_score.",
        "memory_type": "feature",
        "importance_level": 7,
        "tags": ["semantic_search", "retrieval", "ranking"],
        "query_variants": [
            "como funciona la busqueda semantica",
            "search memories ranking similarity score",
            "como trabaja la busqueda semantca del proyecto",
        ],
    },
    {
        "key": "tool_reflection",
        "content": "El sistema puede registrar tool calls MCP, resumir el uso de herramientas y generar reflexion sobre patrones de comportamiento del asistente.",
        "memory_type": "feature",
        "importance_level": 7,
        "tags": ["mcp", "tool_logging", "reflection"],
        "query_variants": [
            "puede reflexionar sobre uso de herramientas",
            "tool logging y reflexion de patrones",
            "el sistema analiza tools calls o no",
        ],
    },
    {
        "key": "fallback_ollama",
        "content": "Si el proveedor principal falla, el fallback configurado es Ollama con el modelo nomic-embed-text en localhost:11434.",
        "memory_type": "configuration",
        "importance_level": 7,
        "tags": ["ollama", "fallback", "embeddings"],
        "query_variants": [
            "que fallback de embeddings tenemos",
            "si lm studio cae que usa el sistema",
            "fallbak ollama nomic embed text",
        ],
    },
    {
        "key": "project_continuity",
        "content": "El sistema puede guardar sesiones de desarrollo, insights de proyecto y continuidad de trabajo por workspace para retomar contexto tecnico.",
        "memory_type": "feature",
        "importance_level": 7,
        "tags": ["vscode", "workspace", "continuity"],
        "query_variants": [
            "como guarda continuidad por workspace",
            "sesiones de desarrollo e insights de proyecto",
            "continudad de trabajo por worksapce",
        ],
    },
    {
        "key": "conversation_store",
        "content": "store_conversation guarda mensajes con role, session_id y metadata, y genera embeddings para recuperacion posterior.",
        "memory_type": "feature",
        "importance_level": 6,
        "tags": ["conversation", "storage", "embeddings"],
        "query_variants": [
            "como se almacenan los turnos de conversacion",
            "store conversation role session id metadata",
            "como guarda conversaciones con sessoin id",
        ],
    },
    {
        "key": "memory_create",
        "content": "create_memory permite guardar memorias curadas con memory_type, importance_level y tags para recuperarlas semanticamente.",
        "memory_type": "feature",
        "importance_level": 6,
        "tags": ["memory", "curation", "tags"],
        "query_variants": [
            "como se crean memorias curadas con tags",
            "create memory importance level tags",
            "como guardar memorias semanticas con typ y tags",
        ],
    },
]

FILLER_TOPICS = [
    "deploy docker compose con healthcheck de base de datos",
    "ajuste de logs para depurar errores de importacion en python",
    "estrategia de tags para memorias de usuario y preferencias",
    "control de sesiones de desarrollo por workspace en vscode",
    "mejora de relevancia en busqueda semantica con similarity score",
    "documentacion de fallback de embeddings y tolerancia a fallos",
    "optimizacion de consultas sqlite para historial de conversaciones",
    "flujo de carga de modelos en LM Studio y uso del servidor local",
    "pruebas de smoke para instalaciones windows con powershell",
    "integracion MCP por stdio y empaquetado con entrypoints",
]

FILLER_CONTEXTS = [
    "registro interno de cambios del proyecto",
    "nota de soporte para repeticion de incidentes",
    "resumen tecnico de una sesion de debugging",
    "apunte de arquitectura y decisiones operativas",
    "observacion sobre rendimiento y latencia local",
]

TYPO_REPLACEMENTS = {
    "windows": "winodws",
    "studio": "sutdio",
    "server": "sevrer",
    "semantic": "semantca",
    "workspace": "worksapce",
    "health": "helth",
    "fallback": "fallbak",
    "qwen": "qewn",
    "session": "sessoin",
}


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def apply_typos(text):
    result = text
    for good, typo in TYPO_REPLACEMENTS.items():
        result = result.replace(good, typo)
    return result


def infer_query_category(query):
    lowered = query.lower()
    if any(typo in lowered for typo in TYPO_REPLACEMENTS.values()):
        return "typo"
    if any(token in lowered for token in ["cual", "como", "que", "sirve", "funciona"]):
        return "clean"
    return "paraphrase"


def build_benchmark_queries(query_mode="all"):
    queries = []
    for anchor in ANCHOR_MEMORIES:
        variants = anchor["query_variants"]
        if query_mode == "baseline":
            variants = [variants[0]]
        for variant in variants:
            queries.append(
                {
                    "query": variant,
                    "expected": [anchor["key"]],
                    "category": infer_query_category(variant),
                }
            )
    return queries


def resolve_profile(profile, corpus_size, batch_size, concurrency, limit, query_mode):
    if profile == "baseline":
        return {
            "profile": "baseline",
            "corpus_size": corpus_size or 240,
            "batch_size": batch_size or 50,
            "concurrency": concurrency or 8,
            "limit": limit or 5,
            "query_mode": query_mode or "baseline",
        }

    return {
        "profile": "stress",
        "corpus_size": corpus_size or 10000,
        "batch_size": batch_size or 100,
        "concurrency": concurrency or 8,
        "limit": limit or 10,
        "query_mode": query_mode or "all",
    }


def build_baseline_corpus(target_count, seed):
    random.seed(seed)
    corpus = []

    for anchor in ANCHOR_MEMORIES:
        corpus.append(
            {
                "key": anchor["key"],
                "content": anchor["content"],
                "memory_type": anchor["memory_type"],
                "importance_level": anchor["importance_level"],
                "tags": anchor["tags"],
                "is_anchor": True,
            }
        )

    filler_index = 0
    while len(corpus) < target_count:
        topic = random.choice(FILLER_TOPICS)
        context = random.choice(FILLER_CONTEXTS)
        content = (
            f"Memoria baseline {filler_index}: {context}. Tema principal: {topic}."
            f" Prioridad operacional: {random.choice(['baja', 'media', 'alta'])}."
            " Fuente: lote baseline de comparacion rapida."
        )

        corpus.append(
            {
                "key": f"baseline_filler_{filler_index}",
                "content": content,
                "memory_type": random.choice(["noise", "support_note", "ops_note", "project_note"]),
                "importance_level": random.randint(2, 7),
                "tags": [
                    random.choice(["baseline", "benchmark", "ops", "support"]),
                    random.choice(["memory", "search", "server", "workspace", "debug"]),
                ],
                "is_anchor": False,
            }
        )
        filler_index += 1

    return corpus[:target_count]


def build_stress_corpus(target_count, seed):
    random.seed(seed)
    corpus = []

    for anchor in ANCHOR_MEMORIES:
        corpus.append(
            {
                "key": anchor["key"],
                "content": anchor["content"],
                "memory_type": anchor["memory_type"],
                "importance_level": anchor["importance_level"],
                "tags": anchor["tags"],
                "is_anchor": True,
            }
        )

        corpus.append(
            {
                "key": f"{anchor['key']}_near_duplicate",
                "content": f"Resumen operativo: {anchor['content']} Esta nota se usa como recordatorio de soporte y checklist interno.",
                "memory_type": anchor["memory_type"],
                "importance_level": max(4, anchor["importance_level"] - 2),
                "tags": anchor["tags"] + ["near_duplicate", "support"],
                "is_anchor": False,
            }
        )

        corpus.append(
            {
                "key": f"{anchor['key']}_typo_variant",
                "content": apply_typos(anchor["content"]),
                "memory_type": anchor["memory_type"],
                "importance_level": max(3, anchor["importance_level"] - 3),
                "tags": anchor["tags"] + ["typo_variant"],
                "is_anchor": False,
            }
        )

        ambiguous_prefix = random.choice([
            "Nota ambigua de operaciones:",
            "Apunte parcial del proyecto:",
            "Resumen mezclado de soporte:",
        ])
        corpus.append(
            {
                "key": f"{anchor['key']}_ambiguous",
                "content": f"{ambiguous_prefix} {anchor['content']} Tambien se comparo con fallback, latencia y estado del servidor local.",
                "memory_type": "mixed_context",
                "importance_level": max(3, anchor["importance_level"] - 4),
                "tags": anchor["tags"] + ["ambiguous", "mixed_context"],
                "is_anchor": False,
            }
        )

    filler_index = 0
    while len(corpus) < target_count:
        topic = random.choice(FILLER_TOPICS)
        context = random.choice(FILLER_CONTEXTS)
        anchor = random.choice(ANCHOR_MEMORIES)
        include_overlap = filler_index % 3 == 0
        overlap_text = ""
        if include_overlap:
            overlap_text = (
                f" Se comparo con {random.choice(anchor['tags'])}, {random.choice(anchor['tags'])} y una referencia indirecta a {anchor['key'].replace('_', ' ')}."
            )
        typo_suffix = ""
        if filler_index % 7 == 0:
            typo_suffix = " " + apply_typos(topic)

        content = (
            f"Memoria sintetica {filler_index}: {context}. Tema principal: {topic}."
            f" Prioridad operacional: {random.choice(['baja', 'media', 'alta'])}."
            f" Fuente: lote benchmark unico.{overlap_text}{typo_suffix}"
        )

        corpus.append(
            {
                "key": f"filler_{filler_index}",
                "content": content,
                "memory_type": random.choice(["noise", "support_note", "ops_note", "project_note"]),
                "importance_level": random.randint(2, 8),
                "tags": [
                    random.choice(["noise", "benchmark", "ops", "support", "mixed"]),
                    random.choice(["memory", "search", "server", "workspace", "debug"]),
                ],
                "is_anchor": False,
            }
        )
        filler_index += 1

    return corpus[:target_count]


def build_corpus(target_count, seed, profile):
    if profile == "baseline":
        return build_baseline_corpus(target_count, seed)
    return build_stress_corpus(target_count, seed)


async def populate_corpus(memory, corpus, batch_size, concurrency):
    key_to_memory_id = {}
    store_latencies_ms = []
    semaphore = asyncio.Semaphore(concurrency)

    async def embed_one(memory_id, content):
        async with semaphore:
            await memory._add_embedding_to_memory(memory_id, content)

    for start in range(0, len(corpus), batch_size):
        batch = corpus[start:start + batch_size]
        tasks = []
        for entry in batch:
            started = time.perf_counter()
            memory_id = await memory.ai_memory_db.create_memory(
                entry["content"],
                entry["memory_type"],
                entry["importance_level"],
                entry["tags"],
                None,
            )
            store_latencies_ms.append((time.perf_counter() - started) * 1000)
            key_to_memory_id[entry["key"]] = memory_id
            tasks.append(embed_one(memory_id, entry["content"]))
        await asyncio.gather(*tasks)
        print(f"Embedded batch {start + len(batch)}/{len(corpus)}")

    return key_to_memory_id, store_latencies_ms


async def run_benchmark(
    keep_data: bool,
    profile: str,
    limit: int | None,
    corpus_size: int | None,
    batch_size: int | None,
    concurrency: int | None,
    query_mode: str | None,
):
    config = resolve_profile(profile, corpus_size, batch_size, concurrency, limit, query_mode)
    benchmark_dir = Path(tempfile.mkdtemp(prefix=f"pam_benchmark_{config['profile']}_"))
    settings = MemorySettings(data_dir=benchmark_dir, enable_file_monitoring=False)
    memory = PersistentAIMemorySystem(settings=settings, enable_file_monitoring=False)
    queries = build_benchmark_queries(query_mode=config["query_mode"])
    corpus = build_corpus(config["corpus_size"], seed=42, profile=config["profile"])

    try:
        health = await memory.get_system_health()
        if health.get("embedding_service", {}).get("status") != "healthy":
            raise RuntimeError(
                f"El proveedor principal de embeddings no esta sano: {health.get('embedding_service')}"
            )

        key_to_memory_id, store_latencies_ms = await populate_corpus(
            memory,
            corpus,
            config["batch_size"],
            config["concurrency"],
        )

        query_details = []
        top1_hits = 0
        recall_at_3_hits = 0
        recall_at_5_hits = 0
        recall_at_10_hits = 0
        reciprocal_ranks = []
        search_latencies_ms = []
        category_totals = {}
        category_hits = {}

        for item in queries:
            started = time.perf_counter()
            result = await memory.search_memories(
                item["query"],
                limit=config["limit"],
                database_filter="ai_memories",
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            search_latencies_ms.append(elapsed_ms)

            results = result.get("results", [])
            ranked_memory_ids = [
                entry.get("data", {}).get("memory_id")
                for entry in results
                if entry.get("type") == "ai_memory"
            ]
            expected_ids = [key_to_memory_id[key] for key in item["expected"]]

            first_match_rank = None
            for index, memory_id in enumerate(ranked_memory_ids, start=1):
                if memory_id in expected_ids:
                    first_match_rank = index
                    break

            if first_match_rank == 1:
                top1_hits += 1
            if any(memory_id in expected_ids for memory_id in ranked_memory_ids[:3]):
                recall_at_3_hits += 1
            if any(memory_id in expected_ids for memory_id in ranked_memory_ids[:5]):
                recall_at_5_hits += 1
            if any(memory_id in expected_ids for memory_id in ranked_memory_ids[:10]):
                recall_at_10_hits += 1

            reciprocal_ranks.append(1.0 / first_match_rank if first_match_rank else 0.0)
            category = item.get("category", "uncategorized")
            category_totals[category] = category_totals.get(category, 0) + 1
            if first_match_rank == 1:
                category_hits[category] = category_hits.get(category, 0) + 1
            query_details.append(
                {
                    "query": item["query"],
                    "category": category,
                    "expected_keys": item["expected"],
                    "first_match_rank": first_match_rank,
                    "latency_ms": round(elapsed_ms, 2),
                    "top_results": [
                        {
                            "rank": idx,
                            "memory_id": entry.get("data", {}).get("memory_id"),
                            "content": entry.get("data", {}).get("content", "")[:140],
                            "similarity_score": round(entry.get("similarity_score", 0.0), 4),
                        }
                        for idx, entry in enumerate(results[:10], start=1)
                    ],
                }
            )

        summary = {
            "benchmark_data_dir": str(benchmark_dir),
            "profile": config["profile"],
            "single_run": True,
            "memory_count": len(corpus),
            "query_count": len(queries),
            "metrics": {
                "top1_accuracy": round(top1_hits / len(queries), 4),
                "recall_at_3": round(recall_at_3_hits / len(queries), 4),
                "recall_at_5": round(recall_at_5_hits / len(queries), 4),
                "recall_at_10": round(recall_at_10_hits / len(queries), 4),
                "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
                "avg_search_latency_ms": round(statistics.mean(search_latencies_ms), 2),
                "median_search_latency_ms": round(statistics.median(search_latencies_ms), 2),
                "p95_search_latency_ms": round(percentile(search_latencies_ms, 0.95), 2),
                "avg_store_latency_ms": round(statistics.mean(store_latencies_ms), 2),
            },
            "category_top1_accuracy": {
                category: round(category_hits.get(category, 0) / total, 4)
                for category, total in sorted(category_totals.items())
            },
            "queries": query_details,
        }

        report_path = benchmark_dir / "benchmark_report.json"
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

        print("Persistent AI Memory Benchmark")
        print("=" * 60)
        print(f"Data dir: {benchmark_dir}")
        print(f"Profile: {summary['profile']}")
        print(f"Single run: {summary['single_run']}")
        print(f"Memories: {summary['memory_count']}")
        print(f"Queries: {summary['query_count']}")
        print(f"Top-1 accuracy: {summary['metrics']['top1_accuracy']:.2%}")
        print(f"Recall@3: {summary['metrics']['recall_at_3']:.2%}")
        print(f"Recall@5: {summary['metrics']['recall_at_5']:.2%}")
        print(f"Recall@10: {summary['metrics']['recall_at_10']:.2%}")
        print(f"MRR: {summary['metrics']['mrr']:.4f}")
        print(f"Avg search latency: {summary['metrics']['avg_search_latency_ms']:.2f} ms")
        print(f"Median search latency: {summary['metrics']['median_search_latency_ms']:.2f} ms")
        print(f"P95 search latency: {summary['metrics']['p95_search_latency_ms']:.2f} ms")
        print(f"Avg store latency: {summary['metrics']['avg_store_latency_ms']:.2f} ms")
        if summary["category_top1_accuracy"]:
            print("Category Top-1:")
            for category, accuracy in summary["category_top1_accuracy"].items():
                print(f"  {category}: {accuracy:.2%}")
        print(f"Report: {report_path}")

        print("\nPer-query summary")
        print("-" * 60)
        for item in query_details:
            rank_display = item["first_match_rank"] if item["first_match_rank"] is not None else "miss"
            print(f"rank={rank_display:>4} latency={item['latency_ms']:>8.2f} ms query={item['query']}")

        return summary
    finally:
        if not keep_data and benchmark_dir.exists():
            shutil.rmtree(benchmark_dir, ignore_errors=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark de memoria para Persistent AI Memory System")
    parser.add_argument(
        "--profile",
        choices=["baseline", "stress"],
        default="baseline",
        help="Perfil de benchmark a ejecutar",
    )
    parser.add_argument("--keep-data", action="store_true", help="Conserva la carpeta temporal y el JSON del benchmark")
    parser.add_argument("--limit", type=int, default=None, help="Numero de resultados a recuperar por consulta")
    parser.add_argument("--corpus-size", type=int, default=None, help="Tamano total del corpus sintetico")
    parser.add_argument("--batch-size", type=int, default=None, help="Tamano de lote para insertar y embeber memorias")
    parser.add_argument("--concurrency", type=int, default=None, help="Concurrencia de generacion de embeddings por lote")
    parser.add_argument(
        "--query-mode",
        choices=["baseline", "all"],
        default=None,
        help="Cantidad de variantes por ancla: baseline usa menos consultas, all usa todas",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    asyncio.run(
        run_benchmark(
            keep_data=args.keep_data,
            profile=args.profile,
            limit=args.limit,
            corpus_size=args.corpus_size,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
            query_mode=args.query_mode,
        )
    )


if __name__ == "__main__":
    main()