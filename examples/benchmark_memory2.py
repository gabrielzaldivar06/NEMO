#!/usr/bin/env python3
"""benchmark_memory2.py — Profile 'entropy' para Persistent AI Memory System.

Objetivo: estresar el ranking con adversariales de alta precision en lugar de
volumen. El corpus es intencionalmente pequeno (120 memorias) pero con 4 tipos
de ruido dirigido:

  12 anchors       — contenido canonico identico al profile stress
  12 imposters     — imp=9, mismo memory_type+tags, contenido DIFERENTE al anchor
  12 distractores  — mismo memory_type+tags, tema genuinamente distinto, imp=5
  12 cross-topic   — mezclan keywords de 2 anchors adyacentes, imp=5-7
  72 filler        — ruido sintetico estandar

Queries (48 = 4 variantes × 12 anchors):
  clean             — query canonica, vocabulario igual al contenido
  typo_severe       — 2-3 errores tipograficos simultaneos
  paraphrase_extreme — cero palabras en comun con el contenido del anchor
  confusory         — menciona tags del anchor pero pregunta desde otro angulo

Metricas adicionales vs benchmark_memory.py:
  top1_adversarial      — Top-1 exclusivamente sobre queries confusorias (12)
  imposter_intercept_rate — % de queries donde rank=1 es un imposter (no anchor)
  avg_score_gap         — promedio (similarity_score rank1 - similarity_score rank2)
                          valores bajos indican que el sistema esta inseguro

Motivacion: el profile stress actual tiene Top-1=94.44% con thresholds bien
ajustados. Este benchmark prueba si esa precision se mantiene cuando los
imposters tienen la misma firma de metadatos que el anchor y las queries no
comparten vocabulario con el contenido almacenado.
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


# ---------------------------------------------------------------------------
# Anchor definitions — contenido canonico + 4 variantes de query cada uno
# ---------------------------------------------------------------------------
ENTROPY_ANCHORS = [
    {
        "key": "tz_windows_fix",
        "content": "En Windows corregimos el problema de timezone usando datetime.now().astimezone().tzinfo y UTC como fallback para evitar errores con ZoneInfo.",
        "memory_type": "project_decision",
        "importance_level": 10,
        "tags": ["windows", "timezone", "bugfix", "python"],
        "variants": {
            "clean":              "como arreglamos el timezone en windows",
            "typo_severe":        "cmo arreglammso el tmiezone en wndwos pytohn",
            "paraphrase_extreme": "solventar desfase horario en sistema operativo microsoft",
            "confusory":          "uso de datetime astimezone para calcular diferencias de hora en produccion windows",
        },
        "imposter_content": (
            "En Windows Server el servicio W32tm requiere configuracion manual del registro "
            "para sincronizar zonas horarias no estandar en redes corporativas aisladas de internet."
        ),
        "distractor_content": (
            "Decidimos usar Python 3.12 en Windows como version minima del proyecto para "
            "aprovechar mejoras de rendimiento del interprete y evitar bugs de timezone anteriores."
        ),
    },
    {
        "key": "lmstudio_endpoint",
        "content": "El proveedor local de embeddings usa la base URL http://localhost:1234 y el cliente agrega internamente /v1/embeddings.",
        "memory_type": "configuration",
        "importance_level": 9,
        "tags": ["lm_studio", "embeddings", "endpoint", "configuration"],
        "variants": {
            "clean":              "cual es el endpoint local de embeddings",
            "typo_severe":        "cuall es el endpoit locla de embeddigns",
            "paraphrase_extreme": "direccion del servicio de vectorizacion en red interna",
            "confusory":          "como apuntar el cliente openai sdk a localhost en lm studio",
        },
        "imposter_content": (
            "LM Studio expone un endpoint compatible con la API de OpenAI en el puerto 1234, "
            "permitiendo usar la SDK oficial de openai apuntando a http://localhost:1234/v1."
        ),
        "distractor_content": (
            "La configuracion de LM Studio permite cambiar el puerto de escucha desde preferencias "
            "de red, util cuando el puerto 1234 esta ocupado por otro servicio del sistema."
        ),
    },
    {
        "key": "qwen_identifier",
        "content": "El identificador cargado en LM Studio para embeddings es qwen3-embed-4b y se configura como modelo principal del proyecto.",
        "memory_type": "configuration",
        "importance_level": 10,
        "tags": ["qwen3", "lm_studio", "embedding_model"],
        "variants": {
            "clean":              "que modelo de embeddings quedo cargado",
            "typo_severe":        "qe modleo de embeddigns queddo cragado",
            "paraphrase_extreme": "nombre del transformador vectorizador activo en el servidor",
            "confusory":          "cuanto ocupa qwen3 embed 4b en vram y que hardware requiere en lm studio",
        },
        "imposter_content": (
            "El modelo qwen3-embed-4b esta disponible en LM Studio como archivo GGUF de "
            "aproximadamente 2.5 GB y requiere al menos 4 GB de VRAM para inferencia eficiente."
        ),
        "distractor_content": (
            "El modelo de chat cargado en LM Studio es qwen3-8b-instruct, separado del modelo "
            "de embeddings y gestionado desde la pestana de modelos activos en LM Studio."
        ),
    },
    {
        "key": "ps1_fallback",
        "content": "El script start_qwen_embedding_server.ps1 usa lms.exe automaticamente cuando llama-server no esta en PATH y deja el servidor listo en localhost:1234.",
        "memory_type": "operations",
        "importance_level": 8,
        "tags": ["powershell", "lm_studio", "llama_cpp", "startup"],
        "variants": {
            "clean":              "como arranca powershell si no existe llama-server",
            "typo_severe":        "coomo arracna pwershell si no exste llma-srevr",
            "paraphrase_extreme": "arranque alternativo del proceso de inferencia cuando falta el binario principal",
            "confusory":          "como instalar llama-server en windows con powershell usando lm studio",
        },
        "imposter_content": (
            "El script de inicio de LM Studio en PowerShell puede registrarse como tarea "
            "programada de Windows para arranque automatico al iniciar sesion del usuario."
        ),
        "distractor_content": (
            "En PowerShell, lms.exe acepta flags de linea de comandos para especificar el modelo "
            "y el puerto, util para automatizar distintas configuraciones de servidor local."
        ),
    },
    {
        "key": "health_check",
        "content": "La prueba tests/test_health_check.py valida imports, archivos JSON, inicializacion de bases de datos y conectividad del proveedor de embeddings.",
        "memory_type": "testing",
        "importance_level": 8,
        "tags": ["testing", "health_check", "validation"],
        "variants": {
            "clean":              "que valida el health check",
            "typo_severe":        "qe valdida el helath chck del systema",
            "paraphrase_extreme": "que aspectos verifica el test de inicializacion del sistema al arrancar",
            "confusory":          "como ejecutar los tests de validacion con pytest y agregar nuevos casos",
        },
        "imposter_content": (
            "Los tests de health check deben ejecutarse antes de cada deploy y pueden "
            "integrarse en pipelines de CI/CD usando pytest con el flag --tb=short para salida compacta."
        ),
        "distractor_content": (
            "El proyecto incluye pruebas de integracion que validan el flujo completo de "
            "insercion y recuperacion de memorias con corpus reales en bases de datos aisladas."
        ),
    },
    {
        "key": "mcp_entrypoint",
        "content": "El entrypoint instalable del servidor MCP es pams-server y arranca ai_memory_mcp_server usando stdio para clientes MCP.",
        "memory_type": "integration",
        "importance_level": 8,
        "tags": ["mcp", "packaging", "entrypoint", "stdio"],
        "variants": {
            "clean":              "como se lanza el servidor mcp instalable",
            "typo_severe":        "coomo se lnaza el srevdor mpc instalble",
            "paraphrase_extreme": "punto de arranque del proceso que expone capacidades al orquestador",
            "confusory":          "diferencias entre transporte stdio y http en el protocolo mcp para servidores locales",
        },
        "imposter_content": (
            "El protocolo MCP soporta multiples transportes: stdio para procesos locales y "
            "HTTP/SSE para servicios remotos, usando el mismo esquema JSON-RPC en ambos casos."
        ),
        "distractor_content": (
            "El paquete pams puede instalarse via pip y expone el comando pams-server en el "
            "PATH del entorno virtual, configurable desde cualquier cliente MCP compatible."
        ),
    },
    {
        "key": "semantic_search",
        "content": "search_memories hace busqueda semantica sobre memorias, conversaciones, agenda y contexto de proyecto, y ordena el ranking por similarity_score.",
        "memory_type": "feature",
        "importance_level": 7,
        "tags": ["semantic_search", "retrieval", "ranking"],
        "variants": {
            "clean":              "como funciona la busqueda semantica",
            "typo_severe":        "cmo funcina la bsuqueda semnatica del syistema",
            "paraphrase_extreme": "algoritmo de recuperacion de informacion por proximidad vectorial",
            "confusory":          "como ajustar el umbral de similarity score para filtrar resultados irrelevantes",
        },
        "imposter_content": (
            "La busqueda semantica con embeddings densos supera a BM25 en recall para queries "
            "en lenguaje natural pero puede ser superada por busqueda hibrida en consultas con terminos tecnicos exactos."
        ),
        "distractor_content": (
            "El sistema implementa busqueda hibrida que combina embeddings densos con tokenizacion "
            "lexical, ponderando ambas senales mediante rank-weighted fusion para mayor precision."
        ),
    },
    {
        "key": "tool_reflection",
        "content": "El sistema puede registrar tool calls MCP, resumir el uso de herramientas y generar reflexion sobre patrones de comportamiento del asistente.",
        "memory_type": "feature",
        "importance_level": 7,
        "tags": ["mcp", "tool_logging", "reflection"],
        "variants": {
            "clean":              "puede reflexionar sobre uso de herramientas",
            "typo_severe":        "puedde reflexionr sobre eso de herraminetas mcp",
            "paraphrase_extreme": "introspeccion sobre invocaciones de funciones externas y su frecuencia",
            "confusory":          "donde se persisten los logs de tool calls mcp en el sistema de archivos",
        },
        "imposter_content": (
            "El logging de tool calls MCP puede implementarse como middleware que intercepta "
            "cada invocacion, registra parametros y resultado en SQLite y genera metricas de uso mensual."
        ),
        "distractor_content": (
            "La reflexion sobre patrones de herramientas se complementa con un sistema de feedback "
            "que permite al asistente ajustar estrategias de llamada segun el historial de sesion."
        ),
    },
    {
        "key": "fallback_ollama",
        "content": "Si el proveedor principal falla, el fallback configurado es Ollama con el modelo nomic-embed-text en localhost:11434.",
        "memory_type": "configuration",
        "importance_level": 7,
        "tags": ["ollama", "fallback", "embeddings"],
        "variants": {
            "clean":              "que fallback de embeddings tenemos",
            "typo_severe":        "qe falback de embeddigns teneemos kand falla",
            "paraphrase_extreme": "alternativa de vectorizacion ante caida del servicio primario",
            "confusory":          "que modelos de embedding admite ollama y como se instala en windows",
        },
        "imposter_content": (
            "Ollama soporta mas de 50 modelos de embeddings incluyendo nomic-embed-text, mxbai-embed "
            "y all-minilm, y puede configurarse con multiples instancias en GPU para alta disponibilidad."
        ),
        "distractor_content": (
            "La configuracion de fallback incluye reintentos automaticos con backoff exponencial "
            "antes de conmutar al proveedor secundario, minimizando interrupciones de servicio."
        ),
    },
    {
        "key": "project_continuity",
        "content": "El sistema puede guardar sesiones de desarrollo, insights de proyecto y continuidad de trabajo por workspace para retomar contexto tecnico.",
        "memory_type": "feature",
        "importance_level": 7,
        "tags": ["vscode", "workspace", "continuity"],
        "variants": {
            "clean":              "como guarda continuidad por workspace",
            "typo_severe":        "coomo guarda continudad por workspce de vsocde",
            "paraphrase_extreme": "persistir el estado de trabajo entre distintas aperturas del editor",
            "confusory":          "que configuracion de vscode se requiere para activar rastreo de workspace",
        },
        "imposter_content": (
            "VS Code permite guardar el estado completo del workspace incluyendo tabs abiertos, "
            "breakpoints y configuracion de debug en .vscode/settings.json para sincronizacion en git."
        ),
        "distractor_content": (
            "La continuidad de sesiones incluye el historial de comandos ejecutados y las decisiones "
            "de arquitectura tomadas, exportables como resumen markdown por workspace activo."
        ),
    },
    {
        "key": "conversation_store",
        "content": "store_conversation guarda mensajes con role, session_id y metadata, y genera embeddings para recuperacion posterior.",
        "memory_type": "feature",
        "importance_level": 6,
        "tags": ["conversation", "storage", "embeddings"],
        "variants": {
            "clean":              "como se almacenan los turnos de conversacion",
            "typo_severe":        "coomo se amlcneaan los truonos de conversacoin",
            "paraphrase_extreme": "registro persistente de intercambios entre participantes con metadatos",
            "confusory":          "cuanto espacio ocupan los embeddings de conversaciones en la base de datos",
        },
        "imposter_content": (
            "Los embeddings de mensajes de conversacion pueden precalcularse en batch offline "
            "reduciendo latencia interactiva; el proceso puede programarse como cron job nocturno."
        ),
        "distractor_content": (
            "El esquema de conversaciones incluye indice por session_id para recuperar el hilo "
            "completo y por timestamp para ordenar cronologicamente los intercambios de una sesion."
        ),
    },
    {
        "key": "memory_create",
        "content": "create_memory permite guardar memorias curadas con memory_type, importance_level y tags para recuperarlas semanticamente.",
        "memory_type": "feature",
        "importance_level": 6,
        "tags": ["memory", "curation", "tags"],
        "variants": {
            "clean":              "como se crean memorias curadas con tags",
            "typo_severe":        "coomo se crean memroias curdaas con tasg",
            "paraphrase_extreme": "como persistir fragmentos de conocimiento categorizados con relevancia",
            "confusory":          "cuantos tags puede tener una memoria y hay limite de longitud de campo",
        },
        "imposter_content": (
            "Los sistemas de memoria con tags jerarquicos permiten navegacion taxonomica y pueden "
            "exportarse como grafos de conocimiento en formato RDF o JSON-LD para integracion externa."
        ),
        "distractor_content": (
            "El campo importance_level va de 1 a 10 y afecta el boost de recuperacion; "
            "niveles 8-10 se reservan para hechos criticos validados del sistema en produccion."
        ),
    },
]

FILLER_TOPICS = [
    "deploy docker compose con healthcheck de base de datos postgres",
    "ajuste de logs para depurar errores de importacion en python",
    "estrategia de tags para memorias de usuario y preferencias personales",
    "mejora de relevancia en busqueda semantica con reranking externo",
    "documentacion de fallback y tolerancia a fallos en servicios de inferencia",
    "optimizacion de consultas sqlite para historial de conversaciones largas",
    "flujo de carga de modelos en LM Studio y configuracion del servidor local",
    "pruebas de smoke para instalaciones windows con powershell y pip",
    "integracion MCP por stdio y empaquetado de herramientas con entrypoints pip",
    "configuracion de embeddings de alta dimension para corpus de documentos grandes",
]


# ---------------------------------------------------------------------------
# Corpus builder
# ---------------------------------------------------------------------------

def build_entropy_corpus(seed: int = 42):
    """Construye corpus de 120 memorias con 4 tipos de adversariales dirigidos.

    Returns:
        corpus: list of dicts
        imposter_ids_set: set of anchor keys that are imposters (filled after populate)
    """
    random.seed(seed)
    corpus = []

    for anchor in ENTROPY_ANCHORS:
        # -- Anchor canonico
        corpus.append({
            "key": anchor["key"],
            "content": anchor["content"],
            "memory_type": anchor["memory_type"],
            "importance_level": anchor["importance_level"],
            "tags": anchor["tags"],
            "role": "anchor",
        })

        # -- Imposter: imp=9, mismo memory_type+tags, contenido diferente
        corpus.append({
            "key": f"{anchor['key']}_imposter",
            "content": anchor["imposter_content"],
            "memory_type": anchor["memory_type"],
            "importance_level": 9,
            "tags": anchor["tags"],
            "role": "imposter",
        })

        # -- Distractor: mismo memory_type+tags, tema diferente, imp=5
        corpus.append({
            "key": f"{anchor['key']}_distractor",
            "content": anchor["distractor_content"],
            "memory_type": anchor["memory_type"],
            "importance_level": 5,
            "tags": anchor["tags"],
            "role": "distractor",
        })

    # -- Cross-topic: mezcla keywords de anchor[i] + anchor[(i+1)%n]
    n = len(ENTROPY_ANCHORS)
    for i in range(n):
        a1 = ENTROPY_ANCHORS[i]
        a2 = ENTROPY_ANCHORS[(i + 1) % n]
        a1_words = a1["content"].split()
        a2_words = a2["content"].split()
        half1 = " ".join(a1_words[: len(a1_words) // 2])
        half2 = " ".join(a2_words[: len(a2_words) // 2])
        corpus.append({
            "key": f"cross_{a1['key']}_{a2['key']}",
            "content": f"{half1}, y ademas {half2} segun configuracion del sistema.",
            "memory_type": random.choice([a1["memory_type"], a2["memory_type"]]),
            "importance_level": random.randint(5, 7),
            "tags": a1["tags"][:2] + a2["tags"][:2],
            "role": "cross_topic",
        })

    # -- Filler estandar hasta completar 120
    filler_index = 0
    target = 120
    while len(corpus) < target:
        topic = random.choice(FILLER_TOPICS)
        corpus.append({
            "key": f"filler_{filler_index}",
            "content": (
                f"Nota tecnica {filler_index}: {topic}. "
                f"Contexto: {random.choice(['operaciones', 'soporte', 'arquitectura', 'debugging'])}. "
                f"Prioridad: {random.choice(['baja', 'media', 'alta'])}."
            ),
            "memory_type": random.choice(["noise", "support_note", "ops_note", "project_note"]),
            "importance_level": random.randint(2, 6),
            "tags": [
                random.choice(["noise", "benchmark", "ops", "support"]),
                random.choice(["memory", "search", "server", "workspace"]),
            ],
            "role": "filler",
        })
        filler_index += 1

    return corpus[:target]


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def build_entropy_queries():
    """48 queries: 4 variantes × 12 anchors."""
    queries = []
    category_order = ["clean", "typo_severe", "paraphrase_extreme", "confusory"]
    for anchor in ENTROPY_ANCHORS:
        for category in category_order:
            queries.append({
                "query": anchor["variants"][category],
                "expected": [anchor["key"]],
                "category": category,
            })
    return queries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


# ---------------------------------------------------------------------------
# Populate corpus
# ---------------------------------------------------------------------------

async def populate_corpus(memory_system, corpus, batch_size=50, concurrency=8):
    key_to_memory_id = {}
    role_map = {}          # memory_id -> role
    store_latencies_ms = []
    semaphore = asyncio.Semaphore(concurrency)

    async def embed_one(memory_id, content):
        async with semaphore:
            await memory_system._add_embedding_to_memory(memory_id, content)

    for start in range(0, len(corpus), batch_size):
        batch = corpus[start : start + batch_size]
        tasks = []
        for entry in batch:
            t0 = time.perf_counter()
            memory_id = await memory_system.ai_memory_db.create_memory(
                entry["content"],
                entry["memory_type"],
                entry["importance_level"],
                entry["tags"],
                None,
            )
            store_latencies_ms.append((time.perf_counter() - t0) * 1000)
            key_to_memory_id[entry["key"]] = memory_id
            role_map[memory_id] = entry.get("role", "filler")
            tasks.append(embed_one(memory_id, entry["content"]))
        await asyncio.gather(*tasks)
        print(f"Embedded batch {start + len(batch)}/{len(corpus)}")

    return key_to_memory_id, role_map, store_latencies_ms


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

async def run_benchmark(keep_data: bool, limit: int = 10):
    benchmark_dir = Path(tempfile.mkdtemp(prefix="pam_benchmark_entropy_"))
    settings = MemorySettings(data_dir=benchmark_dir, enable_file_monitoring=False)
    memory_system = PersistentAIMemorySystem(
        settings=settings, enable_file_monitoring=False
    )
    corpus = build_entropy_corpus(seed=42)
    queries = build_entropy_queries()

    # Role sets — populated after corpus insertion
    imposter_role = "imposter"

    try:
        health = await memory_system.get_system_health()
        if health.get("embedding_service", {}).get("status") != "healthy":
            raise RuntimeError(
                f"Embedding service no disponible: {health.get('embedding_service')}"
            )

        key_to_memory_id, role_map, store_latencies_ms = await populate_corpus(
            memory_system, corpus, batch_size=50, concurrency=8
        )

        # Build set of imposter memory_ids for intercept tracking
        imposter_memory_ids = {
            mid for mid, role in role_map.items() if role == imposter_role
        }

        # ----------------------------------------------------------------
        # Query loop
        # ----------------------------------------------------------------
        query_details = []
        top1_hits = 0
        recall_at_3_hits = 0
        recall_at_5_hits = 0
        recall_at_10_hits = 0
        reciprocal_ranks = []
        search_latencies_ms = []
        score_gaps = []
        imposter_intercept_count = 0

        category_totals: dict[str, int] = {}
        category_hits: dict[str, int] = {}

        for item in queries:
            t0 = time.perf_counter()
            result = await memory_system.search_memories(
                item["query"],
                limit=limit,
                database_filter="ai_memories",
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            search_latencies_ms.append(elapsed_ms)

            results = result.get("results", [])
            ai_results = [r for r in results if r.get("type") == "ai_memory"]
            ranked_ids = [r.get("data", {}).get("memory_id") for r in ai_results]
            expected_ids = [key_to_memory_id[k] for k in item["expected"]]

            # -- Rank detection
            first_match_rank = None
            for idx, mid in enumerate(ranked_ids, start=1):
                if mid in expected_ids:
                    first_match_rank = idx
                    break

            if first_match_rank == 1:
                top1_hits += 1
            if any(mid in expected_ids for mid in ranked_ids[:3]):
                recall_at_3_hits += 1
            if any(mid in expected_ids for mid in ranked_ids[:5]):
                recall_at_5_hits += 1
            if any(mid in expected_ids for mid in ranked_ids[:10]):
                recall_at_10_hits += 1

            reciprocal_ranks.append(1.0 / first_match_rank if first_match_rank else 0.0)

            # -- Score gap (rank1 score - rank2 score)
            if len(ai_results) >= 2:
                s1 = ai_results[0].get("similarity_score", 0.0)
                s2 = ai_results[1].get("similarity_score", 0.0)
                score_gaps.append(s1 - s2)

            # -- Imposter intercept: rank=1 is an imposter
            if ranked_ids and ranked_ids[0] in imposter_memory_ids:
                imposter_intercept_count += 1

            # -- Category tracking
            cat = item.get("category", "uncategorized")
            category_totals[cat] = category_totals.get(cat, 0) + 1
            if first_match_rank == 1:
                category_hits[cat] = category_hits.get(cat, 0) + 1

            query_details.append({
                "query": item["query"],
                "category": cat,
                "expected_keys": item["expected"],
                "first_match_rank": first_match_rank,
                "latency_ms": round(elapsed_ms, 2),
                "rank1_role": role_map.get(ranked_ids[0], "unknown") if ranked_ids else "no_results",
                "score_gap": round(score_gaps[-1], 4) if score_gaps else None,
                "top_results": [
                    {
                        "rank": idx,
                        "memory_id": r.get("data", {}).get("memory_id"),
                        "role": role_map.get(r.get("data", {}).get("memory_id"), "unknown"),
                        "content": r.get("data", {}).get("content", "")[:120],
                        "similarity_score": round(r.get("similarity_score", 0.0), 4),
                    }
                    for idx, r in enumerate(ai_results[:5], start=1)
                ],
            })

        n_queries = len(queries)
        n_confusory = category_totals.get("confusory", 0)
        confusory_hits = category_hits.get("confusory", 0)

        summary = {
            "benchmark_data_dir": str(benchmark_dir),
            "profile": "entropy",
            "corpus_size": len(corpus),
            "corpus_breakdown": {
                "anchors": 12,
                "imposters": 12,
                "distractors": 12,
                "cross_topic": 12,
                "filler": len(corpus) - 48,
            },
            "query_count": n_queries,
            "metrics": {
                "top1_accuracy":           round(top1_hits / n_queries, 4),
                "recall_at_3":             round(recall_at_3_hits / n_queries, 4),
                "recall_at_5":             round(recall_at_5_hits / n_queries, 4),
                "recall_at_10":            round(recall_at_10_hits / n_queries, 4),
                "mrr":                     round(sum(reciprocal_ranks) / n_queries, 4),
                "top1_adversarial":        round(confusory_hits / n_confusory, 4) if n_confusory else 0.0,
                "imposter_intercept_rate": round(imposter_intercept_count / n_queries, 4),
                "avg_score_gap":           round(statistics.mean(score_gaps), 4) if score_gaps else 0.0,
                "avg_search_latency_ms":   round(statistics.mean(search_latencies_ms), 2),
                "median_search_latency_ms":round(statistics.median(search_latencies_ms), 2),
                "p95_search_latency_ms":   round(percentile(search_latencies_ms, 0.95), 2),
                "avg_store_latency_ms":    round(statistics.mean(store_latencies_ms), 2),
            },
            "category_top1": {
                cat: round(category_hits.get(cat, 0) / total, 4)
                for cat, total in sorted(category_totals.items())
            },
            "queries": query_details,
        }

        report_path = benchmark_dir / "benchmark_entropy_report.json"
        report_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
        )

        # ----------------------------------------------------------------
        # Output
        # ----------------------------------------------------------------
        print("Persistent AI Memory — Entropy Benchmark")
        print("=" * 60)
        print(f"Data dir: {benchmark_dir}")
        print(f"Corpus: {len(corpus)} memorias  "
              f"(12 anchors / 12 imposters / 12 distractors / 12 cross-topic / {len(corpus)-48} filler)")
        print(f"Queries: {n_queries}  (clean=12, typo_severe=12, paraphrase_extreme=12, confusory=12)")
        print()
        print(f"Top-1 accuracy:           {summary['metrics']['top1_accuracy']:.2%}")
        print(f"Recall@3:                 {summary['metrics']['recall_at_3']:.2%}")
        print(f"Recall@5:                 {summary['metrics']['recall_at_5']:.2%}")
        print(f"Recall@10:                {summary['metrics']['recall_at_10']:.2%}")
        print(f"MRR:                      {summary['metrics']['mrr']:.4f}")
        print()
        print(f"Top-1 adversarial (confusory): {summary['metrics']['top1_adversarial']:.2%}")
        print(f"Imposter intercept rate:       {summary['metrics']['imposter_intercept_rate']:.2%}")
        print(f"Avg score gap (rank1-rank2):   {summary['metrics']['avg_score_gap']:.4f}")
        print()
        print(f"Avg search latency:  {summary['metrics']['avg_search_latency_ms']:.2f} ms")
        print(f"Median latency:      {summary['metrics']['median_search_latency_ms']:.2f} ms")
        print(f"P95 latency:         {summary['metrics']['p95_search_latency_ms']:.2f} ms")
        print()
        print("Category Top-1:")
        for cat, acc in summary["category_top1"].items():
            marker = " ** ADVERSARIAL **" if cat == "confusory" else ""
            print(f"  {cat:<22}: {acc:.2%}{marker}")
        print(f"\nReport: {report_path}")

        print("\nPer-query summary")
        print("-" * 60)
        for item in query_details:
            rank_display = item["first_match_rank"] if item["first_match_rank"] is not None else "miss"
            role_display = item["rank1_role"]
            intercept_flag = " *** IMPOSTER ***" if role_display == "imposter" else ""
            print(
                f"rank={rank_display:>4}  [{item['category'][:10]:<10}]  "
                f"gap={item['score_gap'] if item['score_gap'] is not None else 'N/A':>6}  "
                f"r1={role_display:<10}  "
                f"query={item['query'][:50]}{intercept_flag}"
            )

        return summary

    finally:
        if not keep_data and benchmark_dir.exists():
            shutil.rmtree(benchmark_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark de entropia para Persistent AI Memory System"
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Conserva la carpeta temporal y el JSON del benchmark",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Numero de resultados a recuperar por consulta (default: 10)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    asyncio.run(run_benchmark(keep_data=args.keep_data, limit=args.limit))


if __name__ == "__main__":
    main()
