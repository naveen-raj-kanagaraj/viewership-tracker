"""A reader that keeps an old snapshot can't stop the database log from resetting. Run: python3 tests/test_wal_interrupt.py"""
import os, sys, tempfile, time, threading
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import store
c = store.main(); c.execute("CREATE TABLE t(x)"); c.executemany("INSERT INTO t VALUES (?)", [("x" * 200,)] * 5000); c.commit()
hold = {}
def pin():                                   # a page read that runs for minutes keeps an old snapshot the whole time
    with store.reading():
        try:
            store.conn().execute("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<2000000000) "
                                 "SELECT COUNT(*) FROM n, (SELECT COUNT(*) FROM t)").fetchone()
        except Exception as e:
            hold["err"] = str(e)
threading.Thread(target=pin, daemon=True).start(); time.sleep(0.5)
for i in range(30):
    with store._lock:
        c.executemany("INSERT INTO t VALUES (?)", [("y" * 200,)] * 500); c.commit()
w0 = os.path.getsize(store.DB_PATH + "-wal")
store.checkpointer(every=0.2)
time.sleep(14)
w1 = os.path.getsize(store.DB_PATH + "-wal")
print("wal before", w0, "after", w1, hold)
assert w1 < w0 / 10, (w0, w1)
with store.reading():                         # reads still work afterwards
    assert store.conn().execute("SELECT COUNT(*) FROM t").fetchone()[0] == 20000
print("WAL INTERRUPT OK")
