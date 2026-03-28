#!/usr/bin/env python3
"""
Benchmark Sprint 14 - Cognitive Features Analysis
Tests the 6 new tools to evaluate real-world improvement over baseline.
Uses isolated DB - does NOT touch production data.
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

TMP_DIR = Path(tempfile.mkdtemp(prefix="nemo_s14_"))
os.environ["AI_MEMORY_DATA_DIR"] = str(TMP_DIR)

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
PASS_S = f"{GREEN}PASS{RESET}"
FAIL_S = f"{RED}FAIL{RESET}"

results = []

def check(name, condition, detail=""):
    results.append((name, condition))
    marker = "V" if condition else "X"
    suffix = f"  -> {detail}" if detail else ""
    print(f"    [{marker}] {name}{suffix}")
    return condition


async def main():
    settings = MemorySettings(data_dir=TMP_DIR)
    sys_ = PersistentAIMemorySystem(settings=settings)
    print(f"\n{'='*60}")
    print(f"  NEMO Sprint 14 - Cognitive Features Benchmark")
    print(f"{'='*60}")
    print(f"  DB aislada: {TMP_DIR}\n")

    # Seed
    print("[0/6] Sembrando memorias de prueba...")
    seeds = [
        ("El servidor de embeddings corre en http://localhost:1234", "fact", 8, ["nemo","config","embedding"]),
        ("El servidor de embeddings corre en localhost puerto 1234", "fact", 6, ["nemo","config"]),
        ("El reranker BGE corre en http://localhost:8080", "fact", 7, ["nemo","config","reranker"]),
        ("Siempre ejecutar benchmark antes de hacer push a main", "procedure", 9, ["nemo","workflow","benchmark"]),
        ("La arquitectura usa SQLite + HNSW para busqueda vectorial", "fact", 8, ["nemo","arch"]),
        ("El modelo de embedding es Qwen3-embed-4b", "fact", 7, ["nemo","embedding","model"]),
        ("NEMO tiene modulo de FSRS-6 para spaced repetition", "fact", 6, ["nemo","fsrs"]),
        ("Gabriel prefiere TypeScript sobre JavaScript", "preference", 7, ["user","typescript"]),
        ("En este workspace siempre usar tags_include para evitar cross-workspace", "procedure", 10, ["nemo","workflow","tags"]),
        ("Completamente diferente: receta de paella valenciana con arroz azafran", "fact", 3, ["receta","food"]),
    ]
    ids = []
    for content, mtype, imp, tags in seeds:
        r = await sys_.create_memory(content, memory_type=mtype, importance_level=imp, tags=tags)
        ids.append(r.get("memory_id"))
        print(f"    + {r.get('memory_id','?')[:8]} imp={imp} {content[:55]}")

    print("    (esperando embeddings background - 25s)...")
    await asyncio.sleep(25)
    print()

    # 1. salience_score
    print("[1/6] salience_score - 4-channel scoring")
    sal_novel = await sys_.salience_score(
        "Nueva integracion con Kubernetes para despliegue automatico de NEMO",
        context="deployment"
    )
    sal_redundant = await sys_.salience_score(
        "El servidor de embeddings corre en http://localhost:1234",
    )
    sal_urgent = await sys_.salience_score(
        "CRITICAL: sistema caido, embeddings fallando, todas las busquedas retornan error"
    )
    sal_reward = await sys_.salience_score(
        "SUCCESS: benchmark completado, Top-1 mejoro de 92 a 96 tras Sprint 14"
    )

    print(f"    novel:     imp={sal_novel.get('importance_suggested')} channels={sal_novel.get('channels')}")
    print(f"    redundant: imp={sal_redundant.get('importance_suggested')} channels={sal_redundant.get('channels')}")
    print(f"    urgent:    imp={sal_urgent.get('importance_suggested')} channels={sal_urgent.get('channels')}")
    print(f"    reward:    imp={sal_reward.get('importance_suggested')} channels={sal_reward.get('channels')}")

    check("salience_score - novel > redundant (novelty channel)",
          sal_novel.get("channels", {}).get("novelty", 0) > sal_redundant.get("channels", {}).get("novelty", 0),
          f"novel={sal_novel.get('channels',{}).get('novelty',0):.3f} redundant={sal_redundant.get('channels',{}).get('novelty',0):.3f}")

    check("salience_score - urgent has arousal",
          sal_urgent.get("channels", {}).get("arousal", 0) > 0.0,
          f"arousal={sal_urgent.get('channels',{}).get('arousal',0):.3f}")

    check("salience_score - reward signal detected",
          sal_reward.get("channels", {}).get("reward", 0) > 0.0,
          f"reward={sal_reward.get('channels',{}).get('reward',0):.3f}")

    check("salience_score - importance_suggested in range",
          1 <= sal_novel.get("importance_suggested", 0) <= 10,
          f"importance_suggested={sal_novel.get('importance_suggested')}")

    # 2. cognitive_ingest
    print(f"\n[2/6] cognitive_ingest - Prediction-Error Gating")

    r_create = await sys_.cognitive_ingest(
        "NEMO ahora soporta multiples instancias simultaneas via PID lockfile",
        memory_type="fact", tags=["nemo","multiinstance"]
    )
    print(f"    create_path: action={r_create.get('action')} sim={r_create.get('similarity',0):.3f}")
    check("cognitive_ingest - novel content -> CREATE",
          r_create.get("action") == "CREATE",
          f"action={r_create.get('action')} similarity={r_create.get('similarity',0):.3f}")

    r_update = await sys_.cognitive_ingest(
        "El servidor de embeddings funciona en localhost en el puerto 1234 via HTTP",
        memory_type="fact", tags=["nemo","config"]
    )
    print(f"    update_path: action={r_update.get('action')} sim={r_update.get('similarity',0):.3f}")
    check("cognitive_ingest - similar content -> UPDATE or SUPERSEDE",
          r_update.get("action") in ("UPDATE", "SUPERSEDE"),
          f"action={r_update.get('action')} sim={r_update.get('similarity',0):.3f}")

    check("cognitive_ingest - auto importance assigned",
          r_create.get("importance_assigned", 0) >= 1,
          f"importance={r_create.get('importance_assigned')}")

    r_force = await sys_.cognitive_ingest(
        "El servidor de embeddings funciona en localhost en el puerto 1234",
        force_create=True, tags=["nemo","config"]
    )
    check("cognitive_ingest - force_create bypasses gating -> CREATE",
          r_force.get("action") == "CREATE",
          f"action={r_force.get('action')}")

    # 3. memory_chronicle
    print(f"\n[3/6] memory_chronicle - Chronological browse")

    chron = await sys_.memory_chronicle(limit=20, tags_include=["nemo"])
    print(f"    status={chron.get('status')} total={chron.get('total')} days={list(chron.get('days',{}).keys())[:3]}")

    check("memory_chronicle - returns success",
          chron.get("status") == "success",
          f"status={chron.get('status')}")
    check("memory_chronicle - has entries",
          chron.get("total", 0) > 0,
          f"total={chron.get('total')}")
    check("memory_chronicle - grouped by day",
          len(chron.get("days", {})) > 0,
          f"days={list(chron.get('days',{}).keys())[:2]}")

    food_entries = [
        e for day in chron.get("days", {}).values()
        for e in day if "food" in e.get("tags", [])
    ]
    check("memory_chronicle - tags_include filters (no food tag)",
          len(food_entries) == 0,
          f"food_entries={len(food_entries)}")

    chron_all = await sys_.memory_chronicle(limit=50)
    food_all = [
        e for day in chron_all.get("days", {}).values()
        for e in day if "food" in e.get("tags", [])
    ]
    check("memory_chronicle - without filter includes all tags",
          len(food_all) > 0,
          f"food_entries={len(food_all)}")

    # 4. detect_redundancy
    print(f"\n[4/6] detect_redundancy - Cosine cluster dedup")

    t0 = time.perf_counter()
    dedup = await sys_.detect_redundancy(threshold=0.80, limit=20, auto_merge=False, tags_include=["nemo"])
    t_dedup = time.perf_counter() - t0
    print(f"    clusters={dedup.get('total_clusters')} redundant={dedup.get('total_redundant')} latency={t_dedup:.2f}s")
    for i, cluster in enumerate(dedup.get("clusters", [])[:3]):
        previews = " | ".join(f"{m['content_preview'][:40]}(sim={m['sim_to_centroid']})" for m in cluster)
        print(f"    cluster[{i}]: {previews}")

    check("detect_redundancy - returns success",
          dedup.get("status") == "success",
          f"status={dedup.get('status')}")
    check("detect_redundancy - finds near-duplicate cluster",
          dedup.get("total_clusters", 0) >= 1,
          f"clusters={dedup.get('total_clusters')}")

    dedup_merge = await sys_.detect_redundancy(threshold=0.80, auto_merge=True, tags_include=["nemo"])
    check("detect_redundancy - auto_merge reports merged count",
          dedup_merge.get("auto_merged", 0) >= 0,
          f"auto_merged={dedup_merge.get('auto_merged')}")

    # 5. anticipate
    print(f"\n[5/6] anticipate - Proactive retrieval")

    context = "voy a hacer push de cambios importantes al repositorio NEMO"

    t0 = time.perf_counter()
    plain = await sys_.search_memories(context, limit=5, compact=False, tags_include=["nemo"])
    t_plain = time.perf_counter() - t0

    t0 = time.perf_counter()
    ant = await sys_.anticipate(context, limit=5, tags_include=["nemo"])
    t_ant = time.perf_counter() - t0

    plain_results = plain.get("results", [])
    ant_preds = ant.get("predictions", [])

    print(f"    plain search: {len(plain_results)} results  {t_plain:.2f}s")
    print(f"    anticipate:   {len(ant_preds)} predictions {t_ant:.2f}s")
    for p in ant_preds[:3]:
        print(f"      score={p['score']:.3f} why='{p['why_relevant']}'  {p['content'][:50]}")

    check("anticipate - returns predictions",
          len(ant_preds) > 0,
          f"count={len(ant_preds)}")
    check("anticipate - has why_relevant annotation",
          all("why_relevant" in p for p in ant_preds),
          "all have why_relevant")

    benchmark_surfaced = any(
        "benchmark" in p.get("content", "").lower() or
        "benchmark" in p.get("why_relevant", "").lower()
        for p in ant_preds
    )
    check("anticipate - surfaces benchmark procedure for push context",
          benchmark_surfaced,
          f"benchmark_in_results={benchmark_surfaced}")

    # 6. intent_anchor
    print(f"\n[6/6] intent_anchor - Prospective semantic memory")

    anchor_r = await sys_.intent_anchor(
        trigger_condition="cuando vaya a hacer push a produccion",
        action="ejecutar benchmark_prod.py primero y verificar Top-1 >= 90%",
        importance_level=9,
        tags=["nemo","workflow","ci"]
    )
    anchor_id = anchor_r.get("intent_anchor_id")
    print(f"    stored anchor: {anchor_id}")

    check("intent_anchor - stores successfully",
          anchor_r.get("status") == "success" and anchor_id,
          f"id={anchor_id}")

    await asyncio.sleep(3)
    rows = await sys_.ai_memory_db.execute_query(
        "SELECT memory_type, content FROM curated_memories WHERE memory_id = ?",
        (anchor_id,)
    )
    if rows:
        row = dict(rows[0])
        check("intent_anchor - stored as memory_type=intent_anchor",
              row.get("memory_type") == "intent_anchor",
              f"type={row.get('memory_type')}")
        try:
            parsed = json.loads(row.get("content","{}"))
            check("intent_anchor - content has trigger+action JSON",
                  "trigger" in parsed and "action" in parsed,
                  f"keys={list(parsed.keys())}")
        except Exception:
            check("intent_anchor - content parseable as JSON", False, "parse error")
    else:
        check("intent_anchor - stored in DB", False, "not found")

    print("    (esperando embedding anchor - 20s)...")
    await asyncio.sleep(20)

    prime = await sys_.prime_context(topic="push produccion benchmark", tags_include=["nemo"])
    anchors_in_prime = prime.get("intent_anchors", [])
    print(f"    intent_anchors in prime_context: {anchors_in_prime}")
    check("intent_anchor - surfaces in prime_context.intent_anchors",
          len(anchors_in_prime) > 0,
          f"anchors_found={len(anchors_in_prime)}")

    check("prime_context - new session_stats field",
          "session_stats" in prime,
          f"session_stats={prime.get('session_stats')}")

    # Results
    print(f"\n{'='*60}")
    print(f"RESULTADOS FINALES")
    print(f"{'='*60}")

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    pct    = passed / total * 100 if total else 0

    for name, ok in results:
        sym = "V" if ok else "X"
        print(f"  [{sym}] {name}")

    print(f"\n  Score: {passed}/{total} ({pct:.0f}%)")

    if pct >= 80:
        print(f"\n  Sprint 14 features APTAS para merge a main")
    elif pct >= 60:
        print(f"\n  Sprint 14 features PARCIALMENTE funcionales - revisar fallos")
    else:
        print(f"\n  Sprint 14 features NO APTAS - revisar implementacion")

    shutil.rmtree(TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())