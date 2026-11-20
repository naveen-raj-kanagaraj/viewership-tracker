"""A peak from another game before a category switch is not booked to the new game. Run: python3 tests/test_switch_peak.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, events
scene._db(); c = store.main(); R = scene.GTA6_RELEASE + 3 * 86400
d = datetime.fromtimestamp(R, events.REPORT_TZ).strftime("%Y-%m-%d")
c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(R, "kick:neyoo", 41000, "Just Chatting"), (R + 200, "kick:neyoo", 9000, "GTA 6"),
              (R + 400, "kick:neyoo", 8000, "GTA 6"), (R, "kick:jon", 20000, "GTA 6")])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(d, "kick:neyoo", "GTA 6", 46043, R + 200, 60, 9000),
              (d, "kick:jon", "GTA 6", 23772, R, 60, 20000)]); c.commit()
assert scene.fix_switch_peaks(since=R - 10) == 1
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:neyoo'").fetchone()[0] == 9000
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:jon'").fetchone()[0] == 23772     # a real spike stays
# going forward: the in-between reading before a switch is dropped
scene._PREVGAME["kick:x"] = ("Just Chatting", R + 820); scene._FPEAK["kick:x"] = 40000
row = {"sid": "kick:x", "platform": "kick", "name": "x", "url": "", "game": "GTA 6", "viewers": 9000}
scene._store([row], R + 1000, R + 820); scene._flush_daily(store.main()); store.main().commit()
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:x' AND game='GTA 6'").fetchone()[0] == 0     # in the grace window
row2 = dict(row, viewers=7000); scene._store([row2], R + 2000, R + 1000); scene._flush_daily(store.main()); store.main().commit()
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:x' AND game='GTA 6'").fetchone()[0] == 7000     # after it
# neyoo's real 19 Nov readings (IST): watch party to 47K, switch, first GTA 6 reading 46,043, later GTA 6 readings lower
from datetime import timezone, timedelta
I = timezone(timedelta(hours=5, minutes=30)); t = lambda h, m: int(datetime(2026, 11, 19, h, m, tzinfo=I).timestamp())
seq = [(21, 2, 33303, "Just Chatting"), (21, 41, 47151, "Just Chatting"), (22, 15, 46043, "GTA 6"), (22, 18, 44000, "GTA 6"),
       (22, 35, 26000, "GTA 6"), (23, 30, 19000, "GTA 6")]
c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(t(h, m), "kick:neyoo_gaming", v, g) for h, m, v, g in seq])
c.execute("INSERT INTO sc_daily VALUES ('2026-11-19','kick:neyoo_gaming','GTA 6',46043,?,361,90000)", (t(22, 15),)); c.commit()
assert scene.fix_switch_peaks2(since=t(20, 0)) == 1
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:neyoo_gaming' AND game='GTA 6'").fetchone()[0] == 26000
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:jon'").fetchone()[0] == 23772
print("SWITCH PEAK OK")
