#!/usr/bin/env python3
"""benchmark_prod.py — Ultra-fast production-condition benchmark for Persistent AI Memory.

Objetivo: validar las condiciones REALES de produccion en ~45-60 segundos.
No hay filler sintetico: el corpus replica el estado de una memoria curada real.

Corpus (24 memorias):
  12 anchors   — memorias canonicas, imp=6-10, typos=produccion real
  12 imposters — mismo memory_type + mismos tags, imp=9, contenido diferente

Queries (24 = 2 variantes x 12 anchors):
  clean       — query directa, vocabulario del anchor, caso mas frecuente en produccion
  confusory   — menciona tags del anchor pero pregunta desde otro angulo (caso dificil)

Metricas clave de produccion:
  top1_clean          — recuperacion limpia (objetivo: ≥90%)
  top1_confusory      — recuperacion adversarial (objetivo: ≥75%)
  imposter_intercept  — % rank=1 es imposter (objetivo: ≤15%)
  avg/p95 latency     — latencia de respuesta (objetivo p95 ≤4s)
  score_confidence    — gap promedio rank1-rank2 (objetivo: ≥0.10)

Ventajas vs benchmark_memory2 (entropy):
  - Sin filler: 24 memorias en vez de 120 → embedding phase 5x mas rapido
  - 24 queries en vez de 48 → search phase 2x mas rapida
  - Resultado en ~45-60s vs ~3-4 minutos
"""

import argparse
import asyncio
import json
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings


# ---------------------------------------------------------------------------
# Production anchor definitions — identical to entropy benchmark
# ---------------------------------------------------------------------------
PROD_ANCHORS = [
    {
        "anchor_content": (
            "En Windows corregimos el problema de timezone usando datetime.now().astimezone().tzinfo "
            "y UTC como fallback para evitar errores con ZoneInfo."
        ),
        "anchor_type": "project_decision",
        "anchor_imp": 10,
        "anchor_tags": ["windows", "timezone", "bugfix", "python"],
        "imposter_content": (
            "En Windows Server el servicio W32tm requiere configuracion manual del registro "
            "para sincronizar zonas horarias no estandar en redes corporativas aisladas de internet."
        ),
        "query_clean":     "como arreglamos el timezone en windows",
        "query_confusory": "uso de datetime astimezone para calcular diferencias de hora en produccion windows",
    },
    {
        "anchor_content": (
            "El proveedor local de embeddings usa la base URL http://localhost:1234 "
            "y el cliente agrega internamente /v1/embeddings."
        ),
        "anchor_type": "configuration",
        "anchor_imp": 9,
        "anchor_tags": ["lm_studio", "embeddings", "endpoint", "configuration"],
        "imposter_content": (
            "LM Studio expone un endpoint compatible con la API de OpenAI en el puerto 1234, "
            "permitiendo usar la SDK oficial de openai apuntando a http://localhost:1234/v1."
        ),
        "query_clean":     "cual es el endpoint local de embeddings",
        "query_confusory": "como apuntar el cliente openai sdk a localhost en lm studio",
    },
    {
        "anchor_content": (
            "El identificador cargado en LM Studio para embeddings es qwen3-embed-4b "
            "y se configura como modelo principal del proyecto."
        ),
        "anchor_type": "configuration",
        "anchor_imp": 10,
        "anchor_tags": ["qwen3", "lm_studio", "embedding_model"],
        "imposter_content": (
            "El modelo qwen3-embed-4b esta disponible en LM Studio como archivo GGUF de "
            "aproximadamente 2.5 GB y requiere al menos 4 GB de VRAM para inferencia eficiente."
        ),
        "query_clean":     "que modelo de embeddings quedo cargado",
        "query_confusory": "cuanto ocupa qwen3 embed 4b en vram y que hardware requiere en lm studio",
    },
    {
        "anchor_content": (
            "El script start_qwen_embedding_server.ps1 usa lms.exe automaticamente cuando "
            "llama-server no esta en PATH y deja el servidor listo en localhost:1234."
        ),
        "anchor_type": "operations",
        "anchor_imp": 8,
        "anchor_tags": ["powershell", "lm_studio", "llama_cpp", "startup"],
        "imposter_content": (
            "El script de inicio de LM Studio en PowerShell puede registrarse como tarea "
            "programada de Windows para arranque automatico al iniciar sesion del usuario."
        ),
        "query_clean":     "como arranca powershell si no existe llama-server",
        "query_confusory": "como instalar llama-server en windows con powershell usando lm studio",
    },
    {
        "anchor_content": (
            "La prueba tests/test_health_check.py valida imports, archivos JSON, "
            "inicializacion de bases de datos y conectividad del proveedor de embeddings."
        ),
        "anchor_type": "testing",
        "anchor_imp": 8,
        "anchor_tags": ["testing", "health_check", "validation"],
        "imposter_content": (
            "Los tests de health check deben ejecutarse antes de cada deploy y pueden "
            "integrarse en pipelines de CI/CD usando pytest con el flag --tb=short para salida compacta."
        ),
        "query_clean":     "que valida el health check",
        "query_confusory": "como ejecutar los tests de validacion con pytest y agregar nuevos casos",
    },
    {
        "anchor_content": (
            "El entrypoint instalable del servidor MCP es pams-server y arranca "
            "ai_memory_mcp_server usando stdio para clientes MCP."
        ),
        "anchor_type": "integration",
        "anchor_imp": 8,
        "anchor_tags": ["mcp", "packaging", "entrypoint", "stdio"],
        "imposter_content": (
            "El protocolo MCP soporta multiples transportes: stdio para procesos locales y "
            "HTTP/SSE para servicios remotos, usando el mismo esquema JSON-RPC en ambos casos."
        ),
        "query_clean":     "como se lanza el servidor mcp instalable",
        "query_confusory": "diferencias entre transporte stdio y http en el protocolo mcp para servidores locales",
    },
    {
        "anchor_content": (
            "search_memories hace busqueda semantica sobre memorias, conversaciones, agenda y "
            "contexto de proyecto, y ordena el ranking por similarity_score."
        ),
        "anchor_type": "feature",
        "anchor_imp": 7,
        "anchor_tags": ["semantic_search", "retrieval", "ranking"],
        "imposter_content": (
            "La busqueda semantica con embeddings densos supera a BM25 en recall para queries "
            "en lenguaje natural pero puede ser superada por busqueda hibrida en consultas con terminos tecnicos exactos."
        ),
        "query_clean":     "como funciona la busqueda semantica",
        "query_confusory": "como ajustar el umbral de similarity score para filtrar resultados irrelevantes",
    },
    {
        "anchor_content": (
            "El sistema puede registrar tool calls MCP, resumir el uso de herramientas "
            "y generar reflexion sobre patrones de comportamiento del asistente."
        ),
        "anchor_type": "feature",
        "anchor_imp": 7,
        "anchor_tags": ["mcp", "tool_logging", "reflection"],
        "imposter_content": (
            "El logging de tool calls MCP puede implementarse como middleware que intercepta "
            "cada invocacion, registra parametros y resultado en SQLite y genera metricas de uso mensual."
        ),
        "query_clean":     "puede reflexionar sobre uso de herramientas",
        "query_confusory": "donde se persisten los logs de tool calls mcp en el sistema de archivos",
    },
    {
        "anchor_content": (
            "Si el proveedor principal falla, el fallback configurado es Ollama "
            "con el modelo nomic-embed-text en localhost:11434."
        ),
        "anchor_type": "configuration",
        "anchor_imp": 7,
        "anchor_tags": ["ollama", "fallback", "embeddings"],
        "imposter_content": (
            "Ollama soporta mas de 50 modelos de embeddings incluyendo nomic-embed-text, mxbai-embed "
            "y all-minilm, y puede configurarse con multiples instancias en GPU para alta disponibilidad."
        ),
        "query_clean":     "que fallback de embeddings tenemos",
        "query_confusory": "que modelos de embedding admite ollama y como se instala en windows",
    },
    {
        "anchor_content": (
            "El sistema puede guardar sesiones de desarrollo, insights de proyecto y "
            "continuidad de trabajo por workspace para retomar contexto tecnico."
        ),
        "anchor_type": "feature",
        "anchor_imp": 7,
        "anchor_tags": ["vscode", "workspace", "continuity"],
        "imposter_content": (
            "VS Code permite guardar el estado completo del workspace incluyendo tabs abiertos, "
            "breakpoints y configuracion de debug en .vscode/settings.json para sincronizacion en git."
        ),
        "query_clean":     "como guarda continuidad por workspace",
        "query_confusory": "que configuracion de vscode se requiere para activar rastreo de workspace",
    },
    {
        "anchor_content": (
            "store_conversation guarda mensajes con role, session_id y metadata, "
            "y genera embeddings para recuperacion posterior."
        ),
        "anchor_type": "feature",
        "anchor_imp": 6,
        "anchor_tags": ["conversation", "storage", "embeddings"],
        "imposter_content": (
            "Los embeddings de mensajes de conversacion pueden precalcularse en batch offline "
            "reduciendo latencia interactiva; el proceso puede programarse como cron job nocturno."
        ),
        "query_clean":     "como se almacenan los turnos de conversacion",
        "query_confusory": "cuanto espacio ocupan los embeddings de conversaciones en la base de datos",
    },
    {
        "anchor_content": (
            "create_memory permite guardar memorias curadas con memory_type, importance_level "
            "y tags para recuperarlas semanticamente."
        ),
        "anchor_type": "feature",
        "anchor_imp": 6,
        "anchor_tags": ["memory", "curation", "tags"],
        "imposter_content": (
            "Los sistemas de memoria con tags jerarquicos permiten navegacion taxonomica y pueden "
            "exportarse como grafos de conocimiento en formato RDF o JSON-LD para integracion externa."
        ),
        "query_clean":     "como se crean memorias curadas con tags",
        "query_confusory": "cuantos tags puede tener una memoria y hay limite de longitud de campo",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p(values: list, frac: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((len(s) - 1) * frac))))
    return s[idx]


def _bar(frac: float, width: int = 20) -> str:
    filled = round(frac * width)
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Corpus population
# ---------------------------------------------------------------------------

async def populate(memory_system, concurrency: int = 8):
    """Store 12 anchors + 12 imposters, embed concurrently."""
    semaphore = asyncio.Semaphore(concurrency)
    anchor_ids: list[str] = []
    imposter_ids: set[str] = set()
    store_latencies: list[float] = []

    async def embed_one(mid, content):
        async with semaphore:
            await memory_system._add_embedding_to_memory(mid, content)

    tasks = []
    for a in PROD_ANCHORS:
        t0 = time.perf_counter()
        anchor_id = await memory_system.ai_memory_db.create_memory(
            a["anchor_content"], a["anchor_type"], a["anchor_imp"], a["anchor_tags"], None
        )
        store_latencies.append((time.perf_counter() - t0) * 1000)
        anchor_ids.append(anchor_id)
        tasks.append(embed_one(anchor_id, a["anchor_content"]))

        t0 = time.perf_counter()
        imp_id = await memory_system.ai_memory_db.create_memory(
            a["imposter_content"], a["anchor_type"], 9, a["anchor_tags"], None
        )
        store_latencies.append((time.perf_counter() - t0) * 1000)
        imposter_ids.add(imp_id)
        tasks.append(embed_one(imp_id, a["imposter_content"]))

    await asyncio.gather(*tasks)
    print(f"[setup] {len(PROD_ANCHORS) * 2} memorias embebidas ({len(PROD_ANCHORS)} anchors + {len(PROD_ANCHORS)} imposters)")
    return anchor_ids, imposter_ids, store_latencies


# ---------------------------------------------------------------------------
# Query loop
# ---------------------------------------------------------------------------

async def run_queries(memory_system, anchor_ids: list[str], imposter_ids: set[str], limit: int = 10):
    queries = []
    for i, a in enumerate(PROD_ANCHORS):
        queries.append({"text": a["query_clean"],     "category": "clean",     "anchor_id": anchor_ids[i]})
        queries.append({"text": a["query_confusory"], "category": "confusory", "anchor_id": anchor_ids[i]})

    results_detail = []
    latencies: list[float] = []

    for q in queries:
        t0 = time.perf_counter()
        resp = await memory_system.search_memories(q["text"], limit=limit, database_filter="ai_memories")
        elapsed = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed)

        ai_results = [r for r in resp.get("results", []) if r.get("type") == "ai_memory"]
        ranked_ids = [r.get("data", {}).get("memory_id") for r in ai_results]
        first_match = next((i + 1 for i, mid in enumerate(ranked_ids) if mid == q["anchor_id"]), None)

        rank1_id = ranked_ids[0] if ranked_ids else None
        rank1_is_imposter = rank1_id in imposter_ids
        gap = None
        if len(ai_results) >= 2:
            gap = round(ai_results[0].get("similarity_score", 0) - ai_results[1].get("similarity_score", 0), 4)

        results_detail.append({
            "query":        q["text"],
            "category":     q["category"],
            "anchor_id":    q["anchor_id"],
            "rank":         first_match,
            "rank1_imp":    rank1_is_imposter,
            "gap":          gap,
            "latency_ms":   round(elapsed, 1),
        })

    return results_detail, latencies


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_benchmark(limit: int = 10, keep_data: bool = False):
    benchmark_dir = Path(tempfile.mkdtemp(prefix="pam_benchmark_prod_"))
    settings = MemorySettings(data_dir=benchmark_dir, enable_file_monitoring=False)
    memory_system = PersistentAIMemorySystem(settings=settings, enable_file_monitoring=False)

    try:
        health = await memory_system.get_system_health()
        if health.get("embedding_service", {}).get("status") != "healthy":
            raise RuntimeError(f"Embedding service unavailable: {health.get('embedding_service')}")

        t_total = time.perf_counter()

        anchor_ids, imposter_ids, store_lats = await populate(memory_system)
        results_detail, latencies = await run_queries(memory_system, anchor_ids, imposter_ids, limit)

        elapsed_total = time.perf_counter() - t_total

        # ----------------------------------------------------------------
        # Aggregate
        # ----------------------------------------------------------------
        n = len(results_detail)
        clean_items     = [r for r in results_detail if r["category"] == "clean"]
        confusory_items = [r for r in results_detail if r["category"] == "confusory"]

        top1_total    = sum(1 for r in results_detail if r["rank"] == 1)
        top1_clean    = sum(1 for r in clean_items     if r["rank"] == 1)
        top1_conf     = sum(1 for r in confusory_items if r["rank"] == 1)
        recall3_total = sum(1 for r in results_detail  if r["rank"] is not None and r["rank"] <= 3)
        mrr           = sum((1.0 / r["rank"]) if r["rank"] else 0.0 for r in results_detail) / n
        imp_intercept = sum(1 for r in results_detail if r["rank1_imp"])
        gaps          = [r["gap"] for r in results_detail if r["gap"] is not None]
        avg_gap       = statistics.mean(gaps) if gaps else 0.0

        avg_lat  = statistics.mean(latencies)
        p50_lat  = _p(latencies, 0.50)
        p95_lat  = _p(latencies, 0.95)

        # Thresholds for pass/fail visual
        def ok(v, thr, hi=True): return "✓" if (v >= thr if hi else v <= thr) else "✗"

        # ----------------------------------------------------------------
        # Output
        # ----------------------------------------------------------------
        sep = "=" * 62
        print(sep)
        print("  Persistent AI Memory — Production Benchmark")
        print(sep)
        print(f"  Corpus  : {len(PROD_ANCHORS) * 2} memorias  "
              f"(12 anchors + 12 imposters, sin filler)")
        print(f"  Queries : {n}  (12 clean + 12 confusory)")
        print(f"  Límite  : top-{limit}")
        print(sep)

        print()
        print("  CALIDAD DE RECUPERACIÓN")
        print(f"  {'Top-1 global':<28}  {top1_total}/{n} = {top1_total/n:.0%}  "
              f"[{_bar(top1_total/n)}]  {ok(top1_total/n, 0.83)}")
        print(f"  {'Top-1 clean':<28}  {top1_clean}/{len(clean_items)} = {top1_clean/len(clean_items):.0%}  "
              f"[{_bar(top1_clean/len(clean_items))}]  {ok(top1_clean/len(clean_items), 0.90)}")
        print(f"  {'Top-1 confusory (adversarial)':<28}  {top1_conf}/{len(confusory_items)} = {top1_conf/len(confusory_items):.0%}  "
              f"[{_bar(top1_conf/len(confusory_items))}]  {ok(top1_conf/len(confusory_items), 0.75)}")
        print(f"  {'Recall@3':<28}  {recall3_total}/{n} = {recall3_total/n:.0%}  "
              f"[{_bar(recall3_total/n)}]  {ok(recall3_total/n, 0.90)}")
        print(f"  {'MRR':<28}  {mrr:.4f}  {ok(mrr, 0.85)}")

        print()
        print("  PROTECCIÓN ANTI-IMPOSTER")
        imp_rate = imp_intercept / n
        print(f"  {'Imposter intercept rate':<28}  {imp_intercept}/{n} = {imp_rate:.0%}  "
              f"[{_bar(1.0 - imp_rate)}]  {ok(imp_rate, 0.15, hi=False)}")
        print(f"  {'Score gap avg (rank1-rank2)':<28}  {avg_gap:.4f}  {ok(avg_gap, 0.10)}")

        print()
        print("  LATENCIA")
        print(f"  {'Promedio':<28}  {avg_lat:>7.1f} ms  {ok(avg_lat, 4000, hi=False)}")
        print(f"  {'Mediana (P50)':<28}  {p50_lat:>7.1f} ms  {ok(p50_lat, 3500, hi=False)}")
        print(f"  {'P95':<28}  {p95_lat:>7.1f} ms  {ok(p95_lat, 4000, hi=False)}")
        print(f"  {'Tiempo total':<28}  {elapsed_total:>7.1f} s")

        print()
        print("  DETALLE POR QUERY")
        print(f"  {'Cat':<10}  {'Rk':>3}  {'Gap':>7}  {'Lat(ms)':>8}  {'Imposter':>9}  {'Query (50c max)'}")
        print("  " + "-" * 58)
        for r in results_detail:
            rk_str = str(r["rank"]) if r["rank"] else "—"
            gap_str = f"{r['gap']:+.4f}" if r["gap"] is not None else "  N/A "
            imp_str = "IMPOSTER⚠" if r["rank1_imp"] else ""
            print(f"  {r['category']:<10}  {rk_str:>3}  {gap_str:>7}  "
                  f"{r['latency_ms']:>8.1f}  {imp_str:>9}  {r['query'][:50]}")

        print(sep)

        # ----------------------------------------------------------------
        # Pass / fail summary
        # ----------------------------------------------------------------
        checks = [
            ("Top-1 clean ≥90%",          top1_clean / len(clean_items) >= 0.90),
            ("Top-1 confusory ≥75%",       top1_conf  / len(confusory_items) >= 0.75),
            ("Imposter intercept ≤15%",    imp_rate   <= 0.15),
            ("Score gap avg ≥0.10",        avg_gap    >= 0.10),
            ("P95 latency ≤4 000 ms",      p95_lat    <= 4000),
        ]
        passed = sum(1 for _, ok_val in checks if ok_val)
        print(f"\n  Resultado: {passed}/{len(checks)} checks superados")
        for label, ok_val in checks:
            print(f"    {'✓' if ok_val else '✗'}  {label}")
        print()

        # ----------------------------------------------------------------
        # JSON report
        # ----------------------------------------------------------------
        report = {
            "corpus_size": len(PROD_ANCHORS) * 2,
            "query_count": n,
            "metrics": {
                "top1_global":         round(top1_total / n, 4),
                "top1_clean":          round(top1_clean / len(clean_items), 4),
                "top1_confusory":      round(top1_conf  / len(confusory_items), 4),
                "recall_at_3":         round(recall3_total / n, 4),
                "mrr":                 round(mrr, 4),
                "imposter_intercept":  round(imp_rate, 4),
                "avg_score_gap":       round(avg_gap, 4),
                "avg_latency_ms":      round(avg_lat, 1),
                "p50_latency_ms":      round(p50_lat, 1),
                "p95_latency_ms":      round(p95_lat, 1),
                "total_elapsed_s":     round(elapsed_total, 1),
            },
            "checks": {label: bool(ok_val) for label, ok_val in checks},
            "queries": results_detail,
        }
        report_path = benchmark_dir / "benchmark_prod_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"  Informe: {report_path}")

        return report

    finally:
        if not keep_data and benchmark_dir.exists():
            shutil.rmtree(benchmark_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Ultra-fast production benchmark for Persistent AI Memory")
    p.add_argument("--limit", type=int, default=10, help="Results per query (default: 10)")
    p.add_argument("--keep-data", action="store_true", help="Keep temp dir and JSON report")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_benchmark(limit=args.limit, keep_data=args.keep_data))
