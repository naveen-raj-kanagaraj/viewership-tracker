"""Read connections close with their thread (28 Nov, FFWS final: every short-lived pool thread's read connection stayed
open, "Too many open files" an hour after each start, the site stopped answering, the watchdog restarted it).
Run: python3 tests/test_reader_leak.py"""
import gc, os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/r.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ThreadPoolExecutor
from tracker import store

store.main()


def fds():
    return len(os.listdir("/proc/self/fd"))


def job(_):
    with store.reading():
        return store.conn().execute("SELECT 1").fetchone()[0]


base = fds()
for _ in range(60):                                  # what each poll does: a new pool, threads that read, then end
    with ThreadPoolExecutor(8) as p:
        assert list(p.map(job, range(16))) == [1] * 16
gc.collect()
assert len(store._READERS) == 0, len(store._READERS)                          # every one closed with its thread
assert not [o for o in gc.get_objects() if isinstance(o, store._RConn)]
assert fds() - base < 200, (base, fds())        # SQLite holds a few closed handles to reuse (before: ~8 per pool, no end)
# a long-lived thread keeps its connection, and the checkpointer can still reach it
with store.reading():
    c = store.conn()
    assert c in store._READERS and c.execute("SELECT 1").fetchone()[0] == 1
    assert store.conn() is c
print("READER LEAK OK")
