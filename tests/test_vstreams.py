"""Per-stream live numbers (peak CCV, hours watched), upcoming streams kept out of stats, PIC preset.
Run: python3 tests/test_vstreams.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/v.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, ytextra, events

sid, now = "yt:UCk", time.time() - 3600
row = lambda a, b: {"sid": sid, "platform": "youtube", "name": "K", "url": "", "game": "PUBG: Battlegrounds", "title": "PIC 2026",
                    "viewers": a + b, "streams": {"hin": a, "eng": b}, "india": True}
scene._store([row(500000, 60000)], now, None)
scene._VPEAK["hin"] = 812000                  # a 2-second reading between scans
scene._store([row(700000, 80000)], now + 120, now)
with scene.store._lock:
    r = dict((v, (pk, n)) for v, pk, n in scene._db().execute("SELECT vid, peak, n FROM sc_vstreams"))
assert r == {"hin": (812000, 2), "eng": (80000, 2)}, r
V = lambda vid, views, live, ts: {"vid": vid, "title": vid, "views": views, "likes": 10, "comments": None, "live": live,
                                   "short": False, "ts": ts, "approx": True}
ytextra.channel_videos = lambda s, force=False: [V("hin", 799000, True, now), V("eng", 85000, True, now), V("up1", 0, True, now + 86400),
                                                 V("old", 40000, False, now - 86400 * 3)]
j = ytextra.videos_summary(sid, "30d", "all")
assert [u["vid"] for u in j["upcoming"]] == ["up1"] and j["count"] == 3 and j["median"] == 85000, (j["count"], j["median"])
h = next(v for v in j["videos"] if v["vid"] == "hin")
assert h["peak"] == 812000 and h["hw"] > 0 and h["live_hours"] > 0
assert j["live_days"][0]["peak"] == 780000, j["live_days"]
assert "pic" in events.PRESETS and events.PRESETS["pic"]["auto"]
assert scene.classify("", "[HINDI] PIC 2026 | League Stage | Group A & B") == "PUBG: Battlegrounds"
print("VSTREAMS OK")
