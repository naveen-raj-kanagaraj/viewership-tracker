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
scene._PREVGAME["kick:x"] = "Just Chatting"; scene._FPEAK["kick:x"] = 40000
row = {"sid": "kick:x", "platform": "kick", "name": "x", "url": "", "game": "GTA 6", "viewers": 9000}
scene._store([row], R + 1000, R + 820); scene._flush_daily(store.main()); store.main().commit()
assert c.execute("SELECT peak FROM sc_daily WHERE sid='kick:x' AND game='GTA 6'").fetchone()[0] == 9000
print("SWITCH PEAK OK")
