"""Kick / Twitch past broadcasts get their peak from the channel's day totals, only when that's exact.
Run: python3 tests/test_broadcast_peak.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, ytextra, events
scene._db(); ytextra._db()
c = store.main()
IST = events.REPORT_TZ
T = lambda d, h: datetime(2026, 11, d, h, tzinfo=IST).timestamp()
# 20 Nov: one broadcast 18:00-22:00, peak 21:00 -> shown. 21 Nov: two broadcasts -> not split. 22 Nov: one broadcast
# 10:00-12:00 but the day's peak was at 20:00 (a stream with no VOD) -> not shown.
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [
    ("2026-11-20", "kick:sky", "BGMI", 23000, int(T(20, 21)), 240, 60000), ("2026-11-20", "kick:sky", "Just Chatting", 9000, int(T(20, 18)), 30, 3000),
    ("2026-11-21", "kick:sky", "BGMI", 20000, int(T(21, 20)), 300, 50000),
    ("2026-11-22", "kick:sky", "BGMI", 15000, int(T(22, 20)), 120, 20000)])
for vid, ts, secs in (("k1", T(20, 18), 4 * 3600), ("k2", T(21, 12), 3600), ("k3", T(21, 19), 3 * 3600), ("k4", T(22, 10), 2 * 3600)):
    c.execute("INSERT INTO yt_videos (vid, sid, ts, title, views, live, secs) VALUES (?,?,?,?,?,1,?)", (vid, "kick:sky", int(ts), "", 50000, secs))
c.commit()
L = [{"vid": v, "live": 1, "ts": int(ts), "secs": s} for v, ts, s in (("k1", T(20, 18), 4 * 3600), ("k2", T(21, 12), 3600),
                                                                     ("k3", T(21, 19), 3 * 3600), ("k4", T(22, 10), 2 * 3600))]
ytextra._broadcast_peaks("kick:sky", L)
got = {v["vid"]: v.get("peak") for v in L}
assert got == {"k1": 23000, "k2": None, "k3": None, "k4": None}, got
assert L[0]["live_hours"] == 4.5 and L[0]["hw"] == 63000
print("BROADCAST PEAK OK")
