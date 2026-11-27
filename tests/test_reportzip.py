"""Weekly / monthly data zip: every table's rows in the period as CSV, private tables left out, due dates in IST."""
import os, sys, tempfile, time, zipfile
from datetime import datetime
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/r.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import store, events, scene, reportzip
events._db(); scene._db()
reportzip.OUT = tempfile.mkdtemp()
now = int(time.time())
with store._lock:
    c = store.conn()
    c.execute("INSERT INTO ev_ticks VALUES ('pmgc',?,100,2,50,50,0)", (now - 100,))
    c.execute("INSERT INTO ev_ticks VALUES ('pmgc',?,100,2,50,50,0)", (now - 40 * 86400,))
    c.executemany("INSERT INTO sc_samples (ts, sid, viewers, game) VALUES (?,?,?,?)",
                  [(now - 100 - i * 60, "yt:UCa", 100 + i, "BGMI") for i in range(30)])
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT)")
    c.execute("INSERT INTO users (email) VALUES ('a@b.c')")
    c.commit()
paths = reportzip.build(now - 7 * 86400, now + 60, "test-week")
assert len(paths) == 1
z = zipfile.ZipFile(paths[0])
names = z.namelist()
assert "README.txt" in names and "ev_ticks.csv" in names and "sc_samples_hourly.csv" in names, names
assert "users.csv" not in names and "kv.csv" not in names and "ev_fine.csv" not in names, names
rows = z.read("ev_ticks.csv").decode().strip().splitlines()
assert len(rows) == 2 and rows[0].startswith("time_ist,event,ts"), rows        # the old tick is outside the week
hr = z.read("sc_samples_hourly.csv").decode().strip().splitlines()
assert 2 <= len(hr) <= 3, hr
# due: Sunday 00:05 IST -> weekly; 1st of the month 00:05 IST -> monthly first
sun = datetime(2026, 11, 29, 0, 5, tzinfo=reportzip.IST).timestamp()
d = reportzip.due(sun)
assert d[0] == "weekly" and d[3] == "letsgrowesports-week-2026-11-22-to-2026-11-28", d
first = datetime(2026, 12, 1, 0, 5, tzinfo=reportzip.IST).timestamp()
d = reportzip.due(first)
assert d[0] == "monthly" and d[3] == "letsgrowesports-month-2026-11", d
assert reportzip.due(datetime(2026, 11, 30, 10, 0, tzinfo=reportzip.IST).timestamp()) is None
print("REPORT ZIP OK")
