"""One-shot helper: delete all memories with memory_type='stress_test'."""
import sqlite3, pathlib

DB = pathlib.Path("C:/Users/gabri/.ai_memory/ai_memories.db")
if not DB.exists():
    print("DB not found:", DB); raise SystemExit(1)

con = sqlite3.connect(DB)
cur = con.cursor()
# discover tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)
# find memory table
mem_table = next((t for t in tables if 'memor' in t.lower()), None)
if not mem_table:
    print("No memory table found"); con.close(); raise SystemExit(1)

# discover columns
cur.execute(f"PRAGMA table_info({mem_table})")
cols = [r[1] for r in cur.fetchall()]
print(f"Table '{mem_table}' columns:", cols)

type_col = next((c for c in cols if 'type' in c.lower()), None)
print(f"Type column: {type_col}")
if type_col:
    cur.execute(f"SELECT COUNT(*) FROM {mem_table} WHERE {type_col}='stress_test'")
    n = cur.fetchone()[0]
    print(f"stress_test memories found: {n}")
    cur.execute(f"DELETE FROM {mem_table} WHERE {type_col}='stress_test'")
    con.commit()
    print(f"Deleted: {cur.rowcount}")
con.close()
