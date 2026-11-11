"""Bare 'PUBG' titles are PUBG: Battlegrounds (PC), not BGMI; and re-filing a channel's past readings moves its
daily rows, readings and category totals. Run: python tests/test_pubg.py (temp database)."""
import os
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/p.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, store  # noqa: E402

cl = scene.classify
assert cl("", "PUBG ME DIWALI CELEBRATION | NO PROMOTIONS") == "PUBG: Battlegrounds"
assert cl("", "AFTER RETIREMENT PUBG CELEBRATION") == "PUBG: Battlegrounds"
assert cl("", "BGMI LIVE | rush gameplay") == "BGMI"
assert cl("", "PUBG MOBILE LIVE conqueror push") == "PUBG Mobile"
assert cl("", "BGMI vs PUBG which is better") == "BGMI"
assert cl("PUBG: BATTLEGROUNDS", "") == "PUBG: Battlegrounds"
assert cl("Battlegrounds Mobile India", "pubg") == "BGMI"
assert cl("", "PMGC 2026 finals") == "PUBG Mobile"
assert cl("", "MEREKO NAHI KHELNA INKE SAATH AB") == "Other"

sid = scene.PUBG_PC_FIX[0]
c = scene._db()
c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(100, sid, 9000, "BGMI"), (220, sid, 9447, "BGMI"), (220, "yt:x", 500, "BGMI")])
c.executemany("INSERT INTO sc_cat VALUES (?,?,?,?)", [(100, "BGMI", 10000, 3), (220, "BGMI", 12000, 4), (220, "PUBG: Battlegrounds", 50, 1)])
c.executemany("INSERT INTO sc_reg VALUES (?,?,?,?,?)", [(100, "global", "BGMI", 20000, 9), (220, "global", "BGMI", 22000, 9)])
c.execute("INSERT INTO sc_daily VALUES ('2026-11-09',?,'BGMI',9447,220,4,1400)", (sid,))
c.execute("INSERT INTO sc_daily VALUES ('2026-11-09',?,'PUBG: Battlegrounds',3000,50,2,100)", (sid,))
c.commit()
store.kv_set("scene_mig_pubgpc", False)
scene._COLS.clear()
c = scene._db()
q = lambda sql, *a: [tuple(r) for r in c.execute(sql, a).fetchall()]
assert q("SELECT COUNT(*) FROM sc_samples WHERE sid=? AND game='BGMI'", sid)[0][0] == 0
assert q("SELECT viewers, streams FROM sc_cat WHERE ts=220 AND game='BGMI'") == [(2553, 3)], q("SELECT * FROM sc_cat")
assert q("SELECT viewers, streams FROM sc_cat WHERE ts=220 AND game='PUBG: Battlegrounds'") == [(9497, 2)]
assert q("SELECT viewers FROM sc_cat WHERE ts=100 AND game='BGMI'") == [(1000,)]
assert q("SELECT viewers FROM sc_reg WHERE ts=100 AND game='PUBG: Battlegrounds'") == [(9000,)]
assert q("SELECT game, peak, mins, hw FROM sc_daily WHERE sid=?", sid) == [("PUBG: Battlegrounds", 9447, 6.0, 1500.0)]
r = scene.rankings(cat="bgmi", period="week", date="2026-11-09")
assert not any(x["sid"] == sid for x in r["rows"]), r["rows"]
print("PUBG OK")
