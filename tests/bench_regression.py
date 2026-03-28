#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression benchmark: NEW (HyDE + PEG + FSRS-6) vs BASELINE (fdf1e5f)

Runs identical query corpus against both versions on identical seed DBs.
Compares: Top-1 Recall, MRR, avg similarity score, latency.

Usage:
    PYTHONIOENCODING=utf-8 python tests/bench_regression.py
"""

import asyncio
import importlib.util
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_DIR     = Path(__file__).parent.parent
BASELINE_DIR = REPO_DIR.parent / "baseline_core"

sys.path.insert(0, str(REPO_DIR))

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Ground-truth corpus ───────────────────────────────────────────────────────
# (query, target_substring_in_correct_memory, rank_weight)
CORPUS = [
    # Exact vocabulary
    ("endpoint de embeddings primario",             "localhost:1234",       1.0),
    ("ruta de la base de datos NEMO",               "AI_MEMORY_DATA_DIR",   1.0),
    ("modelo de reranking utilizado",               "BGE-reranker-v2-m3",   1.0),
    ("umbral de deduplicacion semantica",           "0.92",                 1.0),
    ("cuantas herramientas MCP tiene NEMO",         "37",                   1.0),
    # Paraphrase — same language
    ("URL del servidor de embeddings local",        "localhost:1234",       1.0),
    ("variable de entorno para el directorio",      "AI_MEMORY_DATA_DIR",   1.0),
    ("reranker model name",                         "BGE-reranker-v2-m3",   1.0),
    ("cuantos tools tiene el servidor MCP",         "37",                   1.0),
    # Cross-language (EN -> content in ES)
    ("where does NEMO save its data",               "AI_MEMORY_DATA_DIR",   1.0),
    ("primary embedding server URL",                "localhost:1234",       1.0),
    ("how many MCP tools are available",            "37",                   1.0),
    ("similarity threshold for dedup",              "0.92",                 1.0),
    ("which reranker model does NEMO use",          "BGE-reranker-v2-m3",   1.0),
    # Hard negatives — should NOT return wrong memory as top-1
    ("cuantos idiomas soporta NEMO",                "37",                   0.5),  # ambiguous
]

SEEDS = [
    ("El endpoint de embeddings primario es http://localhost:1234/v1/embeddings", "fact", 7, ["nemo","config"]),
    ("La variable AI_MEMORY_DATA_DIR controla la ruta de la base de datos",       "fact", 8, ["nemo","config"]),
    ("El modelo de reranking es BGE-reranker-v2-m3",                             "fact", 6, ["nemo","reranking"]),
    ("El threshold de deduplicacion semantica es 0.92",                           "fact", 7, ["nemo","dedup"]),
    ("NEMO tiene 37 herramientas MCP disponibles",                               "fact", 6, ["nemo","mcp"]),
]


def _load_module(name: str, core_path: Path, settings_path: Path):
    """Dynamically load ai_memory_core from any directory."""
    # Load settings first (each version may differ)
    spec_s = importlib.util.spec_from_file_location(f"{name}_settings", settings_path)
    mod_s  = importlib.util.module_from_spec(spec_s)
    sys.modules[f"{name}_settings"] = mod_s
    # Patch the settings module name so ai_memory_core can import it
    spec_s.loader.exec_module(mod_s)

    spec = importlib.util.spec_from_file_location(name, core_path)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    # Override the settings import inside ai_memory_core
    # by injecting it before exec
    import builtins
    _real_import = builtins.__import__

    def _patched_import(import_name, *args, **kwargs):
        if import_name == "settings" and name in sys.modules:
            return mod_s
        return _real_import(import_name, *args, **kwargs)

    builtins.__import__ = _patched_import
    try:
        spec.loader.exec_module(mod)
    finally:
        builtins.__import__ = _real_import
    return mod, mod_s


async def run_variant(label: str, core_mod, settings_mod, tmp_dir: Path) -> dict:
    """Seed a fresh DB and run the entire corpus. Returns metrics dict."""
    MemorySettings        = settings_mod.MemorySettings
    PersistentAIMemory    = core_mod.PersistentAIMemorySystem

    isolated = MemorySettings(data_dir=tmp_dir)
    system   = PersistentAIMemory(settings=isolated)

    # ── Seed ─────────────────────────────────────────────────────────────────
    mem_ids = []
    for content, mtype, imp, tags in SEEDS:
        r = await system.create_memory(content, memory_type=mtype, importance_level=imp, tags=tags)
        mem_ids.append(r.get("memory_id",""))

    # Wait for background embeddings
    await asyncio.sleep(22)

    # ── Run corpus ────────────────────────────────────────────────────────────
    top1_hits = 0
    mrr_sum   = 0.0
    score_sum = 0.0
    latencies = []
    per_query = []

    for query, target, weight in CORPUS:
        # Check if hyde param supported
        try:
            t0 = time.perf_counter()
            res = await system.search_memories(query, limit=5, database_filter="ai_memories")
            lat = time.perf_counter() - t0
        except Exception as e:
            per_query.append({"query": query, "hit1": False, "rr": 0.0, "score": 0.0, "lat": 0.0})
            continue

        items   = res.get("results", [])
        latencies.append(lat)

        # Top-1
        top1_content = items[0].get("data",{}).get("content","") if items else ""
        hit1 = target.lower() in top1_content.lower()
        if hit1:
            top1_hits += 1 * weight

        # MRR (up to rank 5)
        rr = 0.0
        for rank, item in enumerate(items, 1):
            if target.lower() in item.get("data",{}).get("content","").lower():
                rr = 1.0 / rank
                break
        mrr_sum += rr * weight

        # avg similarity score
        top_score = items[0].get("similarity_score", 0.0) if items else 0.0
        score_sum += top_score

        per_query.append({
            "query": query, "target": target,
            "hit1": hit1,  "rr": rr,
            "score": top_score, "lat": lat,
        })

    n    = len(CORPUS)
    wsum = sum(w for _, _, w in CORPUS)
    return {
        "label":     label,
        "recall@1":  top1_hits / wsum * 100,
        "mrr":       mrr_sum   / wsum,
        "avg_score": score_sum / n,
        "lat_avg":   sum(latencies) / len(latencies) if latencies else 0,
        "lat_p95":   sorted(latencies)[int(len(latencies)*0.95)-1] if latencies else 0,
        "per_query": per_query,
    }


async def run_hyde_variant(label: str, core_mod, settings_mod, tmp_dir: Path) -> dict:
    """Same as run_variant but uses hyde=True for search (new version only)."""
    MemorySettings        = settings_mod.MemorySettings
    PersistentAIMemory    = core_mod.PersistentAIMemorySystem

    isolated = MemorySettings(data_dir=tmp_dir)
    system   = PersistentAIMemory(settings=isolated)

    mem_ids = []
    for content, mtype, imp, tags in SEEDS:
        r = await system.create_memory(content, memory_type=mtype, importance_level=imp, tags=tags)
        mem_ids.append(r.get("memory_id",""))

    await asyncio.sleep(22)

    top1_hits = 0
    mrr_sum   = 0.0
    score_sum = 0.0
    latencies = []
    per_query = []

    for query, target, weight in CORPUS:
        try:
            t0  = time.perf_counter()
            res = await system.search_memories(query, limit=5, hyde=True, database_filter="ai_memories")
            lat = time.perf_counter() - t0
        except Exception as e:
            per_query.append({"query": query, "hit1": False, "rr": 0.0, "score": 0.0, "lat": 0.0})
            continue

        items = res.get("results", [])
        latencies.append(lat)

        top1_content = items[0].get("data",{}).get("content","") if items else ""
        hit1 = target.lower() in top1_content.lower()
        if hit1:
            top1_hits += 1 * weight

        rr = 0.0
        for rank, item in enumerate(items, 1):
            if target.lower() in item.get("data",{}).get("content","").lower():
                rr = 1.0 / rank
                break
        mrr_sum += rr * weight

        top_score = items[0].get("similarity_score", 0.0) if items else 0.0
        score_sum += top_score
        per_query.append({"query": query, "target": target, "hit1": hit1,
                          "rr": rr, "score": top_score, "lat": lat})

    n    = len(CORPUS)
    wsum = sum(w for _, _, w in CORPUS)
    return {
        "label":     label,
        "recall@1":  top1_hits / wsum * 100,
        "mrr":       mrr_sum   / wsum,
        "avg_score": score_sum / n,
        "lat_avg":   sum(latencies) / len(latencies) if latencies else 0,
        "lat_p95":   sorted(latencies)[int(len(latencies)*0.95)-1] if latencies else 0,
        "per_query": per_query,
    }


def print_comparison(baseline: dict, new_normal: dict, new_hyde: dict):
    w = 32

    def delta(new_val, base_val, higher_is_better=True, fmt="{:.1f}"):
        diff = new_val - base_val
        if higher_is_better:
            color = GREEN if diff > 0 else (RED if diff < 0 else YELLOW)
            sign  = "+" if diff >= 0 else ""
        else:
            color = GREEN if diff < 0 else (RED if diff > 0 else YELLOW)
            sign  = "+" if diff >= 0 else ""
        return f"{color}{sign}{fmt.format(diff)}{RESET}"

    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  Regression Report: BASELINE vs NEW (normal) vs NEW (HyDE){RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"  Corpus: {len(CORPUS)} queries  |  Seeds: {len(SEEDS)} memories")
    print(f"  Baseline commit : fdf1e5f  (pre-HyDE/PEG/FSRS)")
    print(f"  New commit      : HEAD (HyDE + PEG + FSRS-6 + bugfixes)")
    print()

    header = f"  {'Metrica':<28}  {'Baseline':>10}  {'New(norm)':>10}  {'d(norm)':>10}  {'New(HyDE)':>10}  {'d(hyde)':>10}"
    print(header)
    print(f"  {'-'*28}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*10}")

    def row(label, key, fmt, higher_is_better=True, scale=1):
        b = baseline[key]   * scale
        n = new_normal[key] * scale
        h = new_hyde[key]   * scale
        dn = delta(n, b, higher_is_better, fmt)
        dh = delta(h, b, higher_is_better, fmt)
        print(f"  {label:<28}  {fmt.format(b):>10}  {fmt.format(n):>10}  {dn:>18}  {fmt.format(h):>10}  {dh:>18}")

    row("Top-1 Recall (%)",  "recall@1",  "{:.1f}",  higher_is_better=True)
    row("MRR",               "mrr",       "{:.3f}",  higher_is_better=True)
    row("Avg sim score",     "avg_score", "{:.4f}",  higher_is_better=True)
    row("Latency avg (s)",   "lat_avg",   "{:.2f}",  higher_is_better=False)
    row("Latency p95 (s)",   "lat_p95",   "{:.2f}",  higher_is_better=False)

    print()

    # Per-query delta table
    print(f"  {BOLD}Per-query Top-1 detail{RESET}")
    print(f"  {'Query':<45}  {'Base':>4}  {'New':>4}  {'HyDE':>4}")
    print(f"  {'-'*45}  {'-'*4}  {'-'*4}  {'-'*4}")
    base_by_q = {p["query"]: p for p in baseline["per_query"]}
    new_by_q  = {p["query"]: p for p in new_normal["per_query"]}
    hyde_by_q = {p["query"]: p for p in new_hyde["per_query"]}
    for query, target, _ in CORPUS:
        b_hit = base_by_q.get(query, {}).get("hit1", False)
        n_hit = new_by_q.get(query,  {}).get("hit1", False)
        h_hit = hyde_by_q.get(query, {}).get("hit1", False)
        mark  = lambda ok: f"{GREEN}HIT{RESET}" if ok else f"{RED}mis{RESET}"
        print(f"  {query[:45]:<45}  {mark(b_hit)}  {mark(n_hit)}  {mark(h_hit)}")

    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}\n")


async def main():
    if not BASELINE_DIR.exists():
        print(f"{RED}ERROR: baseline worktree not found at {BASELINE_DIR}{RESET}")
        print("Run:  git worktree add ../baseline_core fdf1e5f --detach")
        sys.exit(1)

    # Load baseline module
    baseline_core_path     = BASELINE_DIR / "ai_memory_core.py"
    baseline_settings_path = BASELINE_DIR / "settings.py"
    if not baseline_core_path.exists():
        print(f"{RED}ERROR: {baseline_core_path} not found{RESET}")
        sys.exit(1)

    print(f"{CYAN}Loading modules...{RESET}")
    baseline_mod, baseline_settings = _load_module(
        "baseline_core", baseline_core_path, baseline_settings_path
    )
    # New version is just the current imports
    from settings import MemorySettings as NewSettings
    import ai_memory_core as new_core
    # Wrap new settings for run_variant signature
    class _NewSettingsmock:
        MemorySettings = NewSettings
    new_settings_mock = _NewSettingsmock()

    # ── Create 3 isolated DBs ─────────────────────────────────────────────────
    tmp_base  = Path(tempfile.mkdtemp(prefix="nemo_reg_base_"))
    tmp_new   = Path(tempfile.mkdtemp(prefix="nemo_reg_new_"))
    tmp_hyde  = Path(tempfile.mkdtemp(prefix="nemo_reg_hyde_"))

    print(f"  baseline DB : {tmp_base}")
    print(f"  new DB      : {tmp_new}")
    print(f"  new+hyde DB : {tmp_hyde}\n")

    try:
        print(f"{CYAN}[1/3] Running BASELINE variant...{RESET}")
        result_base = await run_variant(
            "BASELINE", baseline_mod, baseline_settings, tmp_base
        )

        print(f"{CYAN}[2/3] Running NEW (normal search) variant...{RESET}")
        result_new = await run_variant(
            "NEW (normal)", new_core, new_settings_mock, tmp_new
        )

        print(f"{CYAN}[3/3] Running NEW (HyDE) variant...{RESET}")
        result_hyde = await run_hyde_variant(
            "NEW (HyDE)", new_core, new_settings_mock, tmp_hyde
        )

        print_comparison(result_base, result_new, result_hyde)

    finally:
        for d in (tmp_base, tmp_new, tmp_hyde):
            shutil.rmtree(d, ignore_errors=True)
        print(f"[bench] Temporary DBs removed.")


if __name__ == "__main__":
    asyncio.run(main())
