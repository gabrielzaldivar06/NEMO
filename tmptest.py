import sys, tempfile, sqlite3, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, '.')
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
from ai_memory_core import AIMemoryDatabase
db = AIMemoryDatabase(str(tmp / 'test.db'))
cols = [r[1] for r in sqlite3.connect(str(tmp / 'test.db')).execute('PRAGMA table_info(curated_memories)').fetchall()]
print('access_count present:', 'access_count' in cols)
