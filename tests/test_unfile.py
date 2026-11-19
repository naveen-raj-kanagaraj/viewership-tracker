"""One-time repair: GTA 6 YouTube streams filed as Other on 19 Nov go back to GTA 6. Run: python3 tests/test_unfile.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import store, scene
scene._db(); c = store.main()
c.executemany("INSERT INTO sc_channels (sid, platform, name, title, india) VALUES (?,?,?,?,1)",
              [("yt:case", "youtube", "Casetoo", "Playing GTA 6 Until i Finish It - GTA 6 Marathon Day 1"),
               ("yt:wait", "youtube", "Waiter", "waiting for GTA 6 | chill")])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [("2026-11-19", "yt:case", "Other", 9000, 1, 300, 20000),
              ("2026-11-19", "yt:case", "GTA 6", 15700, 1, 100, 9000), ("2026-11-19", "yt:wait", "Other", 500, 1, 60, 300)])
c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (1795050000, "yt:case", 9000, "Other")); c.commit()
assert scene.unfile_g6() == 1
r = c.execute("SELECT game, peak, mins, hw FROM sc_daily WHERE sid='yt:case'").fetchall()
assert [tuple(x) for x in r] == [("GTA 6", 15700, 400, 29000)], [tuple(x) for x in r]
assert c.execute("SELECT game FROM sc_daily WHERE sid='yt:wait'").fetchone()[0] == "Other"
assert c.execute("SELECT game FROM sc_samples WHERE sid='yt:case'").fetchone()[0] == "GTA 6"
print("UNFILE OK")
