#!/usr/bin/env python3
"""
Stress test: 50 escrituras + 20 búsquedas + prime_context + limpieza.
Usa la DB real pero borra las memorias de prueba al terminar.
No requiere LM Studio (sin embeddings en create_memory por defecto).
"""
import asyncio
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_memory_core import PersistentAIMemorySystem
from settings import MemorySettings


def _sql_cleanup_stress() -> int:
    """Borra directamente por SQL todas las memorias de tipo stress_test."""
    try:
        db_path = MemorySettings().data_dir / "ai_memories.db"
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("DELETE FROM curated_memories WHERE memory_type='stress_test'")
        n = cur.rowcount
        con.commit()
        con.close()
        return n
    except Exception:
        return 0

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

async def stress_test():
    print(f"\n{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  STRESS TEST — ai_memory_core{RESET}")
    print(f"{'='*55}")

    ms = PersistentAIMemorySystem(enable_file_monitoring=False)

    # ── 1. Escritura masiva ───────────────────────────────────────────
    print(f"\n  [1/4] Escritura masiva: 50 memorias...")
    t0 = time.perf_counter()
    ids = []
    errors_w = 0
    for i in range(50):
        try:
            r = await ms.create_memory(
                content=f"stress_test_{i}: contenido de prueba numero {i} "
                        f"con texto largo para simular una memoria real de usuario",
                memory_type="stress_test",
                importance_level=(i % 10) + 1,
                tags=[f"tag_{i % 5}", "stress"],
            )
            mid = r.get("memory_id") or r.get("id") or r.get("data", {}).get("id")
            ids.append(mid)
        except Exception as e:
            errors_w += 1
    write_ms = (time.perf_counter() - t0) * 1000
    status_w = GREEN + "OK" + RESET if errors_w == 0 else RED + f"{errors_w} errores" + RESET
    print(f"     {write_ms:.0f}ms total  ({write_ms/50:.1f}ms/op)  [{status_w}]")

    # ── 2. Búsquedas por texto ────────────────────────────────────────
    print(f"\n  [2/4] Búsquedas por texto: 20 queries...")
    t0 = time.perf_counter()
    errors_s = 0
    total_hits = 0
    for i in range(20):
        try:
            r = await ms.search_memories(query=f"stress_test_{i*2}", limit=5)
            total_hits += len(r.get("results", []))
        except Exception:
            errors_s += 1
    read_ms = (time.perf_counter() - t0) * 1000
    status_s = GREEN + "OK" + RESET if errors_s == 0 else RED + f"{errors_s} errores" + RESET
    print(f"     {read_ms:.0f}ms total  ({read_ms/20:.1f}ms/query)  hits={total_hits}  [{status_s}]")

    # ── 3. prime_context ─────────────────────────────────────────────
    print(f"\n  [3/4] prime_context...")
    t0 = time.perf_counter()
    errors_pc = 0
    try:
        bundle = await ms.prime_context()
        mems = bundle.get("memories", [])
    except Exception as e:
        errors_pc += 1
        mems = []
        print(f"     {RED}ERROR: {e}{RESET}")
    pc_ms = (time.perf_counter() - t0) * 1000
    status_pc = GREEN + "OK" + RESET if errors_pc == 0 else RED + "FALLO" + RESET
    print(f"     {pc_ms:.0f}ms  |  {len(mems)} memorias en bundle  [{status_pc}]")

    # ── 4. Semaphore concurrencia: 10 búsquedas simultáneas ──────────
    print(f"\n  [4/5] Concurrencia: 10 búsquedas async simultáneas...")
    t0 = time.perf_counter()
    tasks = [ms.search_memories(query=f"stress_test_{i}", limit=3) for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    conc_ms = (time.perf_counter() - t0) * 1000
    errors_c = sum(1 for r in results if isinstance(r, Exception))
    status_c = GREEN + "OK" + RESET if errors_c == 0 else RED + f"{errors_c} errores" + RESET
    print(f"     {conc_ms:.0f}ms  [{status_c}]")

    # ── 5. Limpieza ───────────────────────────────────────────────────
    print(f"\n  [5/5] Limpieza (borrando memorias de stress)...")
    await ms.close()
    deleted = _sql_cleanup_stress()
    print(f"     {deleted} memorias borradas, cierre OK")

    # ── Resumen ───────────────────────────────────────────────────────
    total = write_ms + read_ms + pc_ms + conc_ms
    total_errors = errors_w + errors_s + errors_pc + errors_c
    passed = total_errors == 0 and total < 60000

    print(f"\n{'='*55}")
    print(f"  Escritura 50 mems:         {write_ms:>6.0f}ms  ({write_ms/50:.1f}ms/op)")
    print(f"  Búsqueda  20 queries:      {read_ms:>6.0f}ms  ({read_ms/20:.1f}ms/q)")
    print(f"  prime_context:             {pc_ms:>6.0f}ms")
    print(f"  Concurrencia 10 async:     {conc_ms:>6.0f}ms")
    print(f"  TOTAL:                     {total:>6.0f}ms")
    print(f"  Errores:                   {total_errors}")

    color = GREEN if passed else (YELLOW if total_errors == 0 else RED)
    verdict = "PASS" if passed else ("LENTO" if total_errors == 0 else "FAIL")
    print(f"\n  Resultado: {color}{BOLD}{verdict}{RESET}")
    print(f"{'='*55}\n")
    return passed


if __name__ == "__main__":
    ok = asyncio.run(stress_test())
    sys.exit(0 if ok else 1)
