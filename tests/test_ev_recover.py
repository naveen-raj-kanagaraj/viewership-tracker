"""PMGC Day 1: the event writer writes everything queued in one go, and readings saved from the site's public data
are written back once after a restart. Run: python3 tests/test_ev_recover.py"""
import json, os, sys, tempfile, time, pathlib
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/r.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, store
ev = events.create("pmgc")
with store._lock:
    c = events._db()
    c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              ("pmgc", "v1", "Snax", "UCs", "PMGC watch party", "watch party", 1, 1, 100, 1))
    c.execute("INSERT INTO ev_ticks VALUES (?,?,?,?,?,?,?)", ("pmgc", 1000, 5, 1, 1, 4, 0))
    c.commit()
# the writer: 50 queued writes go in one batch
done = []
for i in range(50):
    events._WQ.put(lambda i=i: done.append(i))
events.flush()
assert done == list(range(50))
# recovery file: ticks where none exist, stream readings, stream peaks; once only
rd = pathlib.Path(events.__file__).resolve().parent / "recover"
created = not rd.exists()
rd.mkdir(exist_ok=True)
f = rd / "zz_test_recover.json"
f.write_text(json.dumps({"key": "pmgc", "ticks": [[1000, 9, 1, 8, 0, 1], [1002, 150743, 33752, 116991, 0, 131]],
                         "samples": [[1002, "v1", 63682]]}))
try:
    events.recover_once()
    events.recover_once()
    with store.reading():
        c = events._db()
        t = c.execute("SELECT ts, total FROM ev_ticks WHERE event='pmgc' AND ts < 5000 ORDER BY ts").fetchall()
        sm = c.execute("SELECT COUNT(*) FROM ev_samples WHERE event='pmgc' AND vid='v1'").fetchone()[0]
        pk = c.execute("SELECT peak FROM ev_streams WHERE event='pmgc' AND vid='v1'").fetchone()[0]
    assert [tuple(x) for x in t] == [(1000, 5), (1002, 150743)], t     # the existing reading is kept
    assert sm == 1 and pk == 63682
    assert events.stats("pmgc")["peak"] >= 150743
finally:
    f.unlink()
    if created:
        rd.rmdir()
print("EV RECOVER OK")
