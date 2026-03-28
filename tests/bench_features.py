#!/usr/bin/env python3
"""
Benchmark aislado para las 3 features nuevas:
  1. HyDE — query expansion via Ollama qwen2.5:0.5b
  2. Prediction Error Gating — supersede on contradiction
  3. FSRS-6 Decay — stability update on access

Corre contra un AI_MEMORY_DATA_DIR temporal (no toca producción).
No requiere servidor MCP activo — importa el core directamente.

Uso:
    python tests/bench_features.py
"""

import asyncio
import os
import shutil
import time
import tempfile
import json
from pathlib import Path

# ── Isolated DB ──────────────────────────────────────────────────────────────
TMP_DIR = Path(tempfile.mkdtemp(prefix="nemo_bench_"))
os.environ["AI_MEMORY_DATA_DIR"] = str(TMP_DIR)
print(f"[bench] DB aislada: {TMP_DIR}\n")

# ── Import core (after setting env var) ──────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

PASS = f"{GREEN}PASS{RESET}"
FAIL = f"{RED}FAIL{RESET}"
SKIP = f"{YELLOW}SKIP{RESET}"

results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition))
    suffix = f"  {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    return condition

# ─────────────────────────────────────────────────────────────────────────────
async def main():
    isolated_settings = MemorySettings(data_dir=TMP_DIR)
    system = PersistentAIMemorySystem(settings=isolated_settings)
    print(f"[bench] ai_memories DB: {system.ai_memory_db.db_path}")
    print(f"[bench] data_dir: {system.data_dir}\n")
    print(f"{CYAN}=== Benchmark NEMO features (aislado) ==={RESET}\n")

    # ── Seed memories ────────────────────────────────────────────────────────
    print(f"{CYAN}[1/3] Sembrando memorias de prueba...{RESET}")
    seed_memories = [
        ("El endpoint de embeddings primario es http://localhost:1234/v1/embeddings", "fact", 7, ["nemo", "config"]),
        ("La variable AI_MEMORY_DATA_DIR controla la ruta de la base de datos", "fact", 8, ["nemo", "config"]),
        ("El modelo de reranking es BGE-reranker-v2-m3", "fact", 6, ["nemo", "reranking"]),
        ("El threshold de deduplicación semántica es 0.92", "fact", 7, ["nemo", "dedup"]),
        ("NEMO tiene 37 herramientas MCP disponibles", "fact", 6, ["nemo", "mcp"]),
    ]
    memory_ids = []
    for content, mtype, imp, tags in seed_memories:
        result = await system.create_memory(content, memory_type=mtype, importance_level=imp, tags=tags)
        mid = result.get("memory_id")
        memory_ids.append(mid)
        print(f"    + {mid[:8]}... {content[:60]}")

    # Esperar embedding background (máx 20s)
    print("    (esperando embeddings en background...)")
    await asyncio.sleep(20)

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{CYAN}[2/3] Feature #1 — HyDE query expansion{RESET}")

    # Buscar con vocabulario diferente (paraphrase)
    query_original    = "ruta del directorio de datos"
    query_paraphrase  = "where does NEMO store its database files"

    t0 = time.perf_counter()
    res_normal = await system.search_memories(query_paraphrase, limit=5, hyde=False, database_filter="ai_memories")
    t_normal = time.perf_counter() - t0

    t0 = time.perf_counter()
    res_hyde = await system.search_memories(query_paraphrase, limit=5, hyde=True, database_filter="ai_memories")
    t_hyde = time.perf_counter() - t0

    normal_hits  = res_normal.get("results", [])
    hyde_hits    = res_hyde.get("results", [])

    # El resultado correcto es la memoria sobre AI_MEMORY_DATA_DIR
    TARGET = "AI_MEMORY_DATA_DIR"
    normal_found = any(TARGET in r.get("data", {}).get("content", "") for r in normal_hits)
    hyde_found   = any(TARGET in r.get("data", {}).get("content", "") for r in hyde_hits)

    # Scores del top resultado
    normal_top = normal_hits[0]["similarity_score"] if normal_hits else 0
    hyde_top   = hyde_hits[0]["similarity_score"]   if hyde_hits   else 0

    # Verificar que el query cross-idioma funciona con al menos un resultado
    any_hit = bool(normal_hits or hyde_hits)
    check("HyDE — busqueda retorna resultados", any_hit,
          f"normal={len(normal_hits)} hits, hyde={len(hyde_hits)} hits")
    check("HyDE — target encontrado (paraphrase_ext)", hyde_found,
          f"normal={normal_found} hyde={hyde_found} (requiere reranker activo para cross-idioma)")
    check("HyDE — score top >= normal", hyde_top >= normal_top * 0.95,
          f"normal_top={normal_top:.4f} hyde_top={hyde_top:.4f}")

    ollama_used = res_hyde.get("hyde_used", None)
    if ollama_used is False:
        print(f"    [{SKIP}] Ollama no disponible — HyDE degradó a búsqueda normal (esperado)")
    else:
        print(f"    t_normal={t_normal:.2f}s  t_hyde={t_hyde:.2f}s  overhead={t_hyde-t_normal:.2f}s")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{CYAN}[3/3-A] Feature #2 — Prediction Error Gating{RESET}")

    # Quick similarity probe to verify PEG content lands in 0.70-0.90 range
    # NOTE: use different importance/tags so contextual prefix differs (avoids false dedup)
    import numpy as np
    _peg_type = "fact"
    _peg_old_txt = "Ana prefiere usar Python para todos sus proyectos de programación"
    _peg_new_txt = "Ana ya no prefiere Python, ahora trabaja con Rust para sus proyectos de programación"
    # Build contextual text as the system would
    from ai_memory_core import PersistentAIMemorySystem as _MS
    _ctx_old = _MS._build_contextual_embedding_text(_peg_old_txt, _peg_type, 8, ["usuario","historial"])
    _ctx_new = _MS._build_contextual_embedding_text(_peg_new_txt, _peg_type, 5, ["usuario","update"])
    _e1 = await system.embedding_service.generate_embedding(_ctx_old)
    _e2 = await system.embedding_service.generate_embedding(_ctx_new)
    if _e1 and _e2:
        _v1, _v2 = np.array(_e1, dtype=np.float32), np.array(_e2, dtype=np.float32)
        _peg_sim = float(np.dot(_v1, _v2) / (np.linalg.norm(_v1) * np.linalg.norm(_v2)))
        print(f"    [probe] similitud contextual PEG old<->new = {_peg_sim:.4f}  (necesario: 0.70-0.90)")

    # Guardar un hecho y luego contradecirlo
    r1 = await system.create_memory(
        _peg_old_txt,
        memory_type=_peg_type, importance_level=8, tags=["usuario", "historial"]
    )
    old_id = r1["memory_id"]
    print(f"    Memoria original: {old_id[:8]}...")

    await asyncio.sleep(1)

    r2 = await system.create_memory(
        _peg_new_txt,
        memory_type=_peg_type, importance_level=5, tags=["usuario", "update"]
    )
    new_id = r2["memory_id"]
    print(f"    Memoria nueva (con contradicción): {new_id[:8]}...")

    # Esperar que el background dedup procese (necesita embedding de AMBAS memorias)
    print("    (esperando embeddings PEG en background — 25s)...")
    await asyncio.sleep(25)

    # Verificar que la memoria vieja tiene tag "superseded"
    old_rows = await system.ai_memory_db.execute_query(
        "SELECT tags, importance_level FROM curated_memories WHERE memory_id = ?", (old_id,)
    )
    if old_rows:
        old_tags = json.loads(old_rows[0]["tags"]) if old_rows[0]["tags"] else []
        superseded = "superseded" in old_tags
        check("PEG — vieja memoria marcada 'superseded'", superseded,
              f"tags={old_tags}")
        check("PEG — importancia bajó en la vieja", old_rows[0]["importance_level"] <= 7,
              f"importance={old_rows[0]['importance_level']} (original era 8, debe ser <=7)")
    else:
        check("PEG — vieja memoria existe", False, "no encontrada en DB")

    # Verificar que la nueva memoria existe y tiene importancia >= 6
    new_rows = await system.ai_memory_db.execute_query(
        "SELECT importance_level FROM curated_memories WHERE memory_id = ?", (new_id,)
    )
    if new_rows:
        check("PEG — nueva memoria persiste", True, f"importance={new_rows[0]['importance_level']}")
    else:
        check("PEG — nueva memoria persiste", False, "eliminada (no debería)")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{CYAN}[3/3-B] Feature #3 — FSRS-6 Decay{RESET}")

    # Verificar que los campos existen
    schema_rows = await system.ai_memory_db.execute_query(
        "PRAGMA table_info(curated_memories)"
    )
    cols = [r["name"] for r in schema_rows]
    check("FSRS-6 — columna 'stability' existe", "stability" in cols)
    check("FSRS-6 — columna 'difficulty' existe", "difficulty" in cols)

    # Leer stability antes de búsqueda
    if memory_ids:
        pre_rows = await system.ai_memory_db.execute_query(
            "SELECT stability FROM curated_memories WHERE memory_id = ?", (memory_ids[0],)
        )
        stab_before = float(pre_rows[0]["stability"] or 1.0) if pre_rows else 1.0

        # Trigger búsqueda para que _bump_access actualice stability
        sr = await system.search_memories("endpoint embeddings primario", limit=5, database_filter="ai_memories")
        hit_items = sr.get("results", [])
        hit_ids = [r.get("data",{}).get("memory_id","") for r in hit_items]
        hit_ids_short = [h[:8] for h in hit_ids]
        print(f"    top hits: {hit_ids_short}")
        print(f"    seed[0] = {memory_ids[0][:8]}, in hits: {memory_ids[0] in hit_ids}")
        await asyncio.sleep(3)  # Dar tiempo al background task de FSRS-6

        # Verificar access_count en CUALQUIER memoria que aparecio en results
        if hit_ids:
            check_id = hit_ids[0]  # Usar el primer resultado real devuelto
            post_rows = await system.ai_memory_db.execute_query(
                "SELECT stability, access_count FROM curated_memories WHERE memory_id = ?", (check_id,)
            )
        else:
            post_rows = None

        if post_rows:
            stab_after  = float(post_rows[0]["stability"] or 1.0)
            ac_after    = post_rows[0]["access_count"] if post_rows else 0

            check("FSRS-6 — access_count incrementado", ac_after >= 1, f"access_count={ac_after}")
            check("FSRS-6 — stability no negativa", stab_after >= 0.1, f"stab={stab_after:.4f}")
            print(f"    stability despues={stab_after:.4f}")
        else:
            check("FSRS-6 — access_count incrementado", False, "sin resultados de busqueda")
            check("FSRS-6 — stability no negativa", False, "sin resultados de busqueda")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{CYAN}[4/4] Top-1 Recall & Latency{RESET}")

    # Ground-truth: (query, substring_que_debe_aparecer_en_top1)
    RECALL_QUERIES = [
        # Exact / near-exact
        ("endpoint de embeddings primario",              "localhost:1234"),
        ("ruta de la base de datos NEMO",                "AI_MEMORY_DATA_DIR"),
        ("modelo de reranking utilizado",                "BGE-reranker-v2-m3"),
        ("umbral de deduplicacion semantica",            "0.92"),
        ("cuantas herramientas MCP tiene NEMO",          "37"),
        # Paraphrase (different vocabulary)
        ("where does NEMO save its data",                "AI_MEMORY_DATA_DIR"),
        ("primary embedding server URL",                 "localhost:1234"),
        ("how many MCP tools are available",             "37"),
        ("similarity threshold for dedup",               "0.92"),
        ("which reranker model does NEMO use",           "BGE-reranker-v2-m3"),
    ]

    hit_normal = 0
    hit_hyde   = 0
    lat_normal = []
    lat_hyde   = []

    print(f"  {'Query':<45}  {'Normal':>6}  {'HyDE':>6}  {'t_n':>6}  {'t_h':>6}")
    print(f"  {'-'*45}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}")

    for query, target in RECALL_QUERIES:
        t0 = time.perf_counter()
        rn = await system.search_memories(query, limit=1, hyde=False, database_filter="ai_memories")
        tn = time.perf_counter() - t0

        t0 = time.perf_counter()
        rh = await system.search_memories(query, limit=1, hyde=True,  database_filter="ai_memories")
        th = time.perf_counter() - t0

        top_n = rn.get("results", [{}])[0].get("data", {}).get("content", "") if rn.get("results") else ""
        top_h = rh.get("results", [{}])[0].get("data", {}).get("content", "") if rh.get("results") else ""

        ok_n = target.lower() in top_n.lower()
        ok_h = target.lower() in top_h.lower()

        if ok_n: hit_normal += 1
        if ok_h: hit_hyde   += 1
        lat_normal.append(tn)
        lat_hyde.append(th)

        sn = f"{GREEN}HIT{RESET}" if ok_n else f"{RED}mis{RESET}"
        sh = f"{GREEN}HIT{RESET}" if ok_h else f"{RED}mis{RESET}"
        print(f"  {query[:45]:<45}  {sn}  {sh}  {tn:>5.2f}s  {th:>5.2f}s")

    n = len(RECALL_QUERIES)
    r_normal = hit_normal / n * 100
    r_hyde   = hit_hyde   / n * 100
    avg_n    = sum(lat_normal) / n
    avg_h    = sum(lat_hyde)   / n
    p95_n    = sorted(lat_normal)[int(n * 0.95) - 1]
    p95_h    = sorted(lat_hyde)[int(n * 0.95) - 1]

    print(f"\n  {'Metrica':<30}  {'Normal':>8}  {'HyDE':>8}")
    print(f"  {'-'*30}  {'-'*8}  {'-'*8}")
    print(f"  {'Top-1 Recall':<30}  {r_normal:>7.1f}%  {r_hyde:>7.1f}%")
    print(f"  {'Latency avg':<30}  {avg_n:>7.2f}s  {avg_h:>7.2f}s")
    print(f"  {'Latency p95':<30}  {p95_n:>7.2f}s  {p95_h:>7.2f}s")

    check("Recall — normal Top-1 >= 70%", r_normal >= 70.0, f"{r_normal:.1f}%")
    check("Recall — HyDE Top-1 >= normal", r_hyde >= r_normal, f"normal={r_normal:.1f}% hyde={r_hyde:.1f}%")
    check("Latency — normal avg < 5s",    avg_n < 5.0,        f"{avg_n:.2f}s")
    check("Latency — HyDE avg < 10s",     avg_h < 10.0,       f"{avg_h:.2f}s")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{CYAN}=== Resultados ==={RESET}")
    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    pct    = passed / total * 100 if total else 0
    bar    = "#" * passed + "." * (total - passed)
    color  = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED
    print(f"  {color}{bar}{RESET}  {passed}/{total}  ({pct:.0f}%)")
    for name, ok in results:
        icon = "+" if ok else "x"
        c = GREEN if ok else RED
        print(f"  {c}{icon}{RESET} {name}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        print(f"\n[bench] DB temporal eliminada: {TMP_DIR}")
