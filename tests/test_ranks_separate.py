"""The rankings job in its own process gives the same rankings as in the tracker's process.
Run: python3 tests/test_ranks_separate.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, ranks, events, ytextra, deep
scene._db(); ytextra._db(); deep._db()
c = store.main()
d = datetime.now(events.REPORT_TZ).date().strftime("%Y-%m-%d")
c.executemany("INSERT INTO sc_channels (sid, platform, name, india) VALUES (?,?,?,?)",
              [("yt:a", "youtube", "A", 1), ("twitch:b", "twitch", "B", 0), ("kick:c", "kick", "C", 1)])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(d, "yt:a", "GTA 6", 900, 1, 60, 500), (d, "twitch:b", "GTA 6", 5000, 1, 60, 3000),
                                                              (d, "kick:c", "BGMI", 2000, 1, 60, 1000)])
c.commit()
ranks.compute()
inproc = ranks.top("all", "peak_7d")["rows"]
ranks._R.update(at=0, rows={}, rank={}, tot={})
ranks.SEPARATE = True
n = ranks.compute()
assert n == 3 and ranks.STATUS.get("error") is None, (n, ranks.STATUS)
sep = ranks.top("all", "peak_7d")["rows"]
assert [(r["name"], r["peak_7d"]) for r in sep] == [(r["name"], r["peak_7d"]) for r in inproc] == [("B", 5000), ("C", 2000), ("A", 900)], sep
assert ranks._R["at"] > 0
print("RANKS SEPARATE OK")
