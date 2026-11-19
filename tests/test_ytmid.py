"""YouTube streams beyond the 2-second set are re-counted every 20 s (middle tier). Run: python3 tests/test_ytmid.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, events
seen = []
events.count_live = lambda vid: seen.append(vid) or 4900
for i in range(120):                          # 120 Indian YouTube streams: 80 in the 2-second set, the rest mid tier
    scene._LIVE[f"yt:c{i}"] = {"platform": "youtube", "viewers": 10000 - i * 50, "india": True, "streams": [f"v{i}"]}
scene._LIVE["yt:small"] = {"platform": "youtube", "viewers": 120, "india": True, "streams": ["vs"]}
scene._YTF.update(next=0, mid=0, slow=0)
scene.yt_fast_once(now=1000)
assert "v119" in seen and "vs" not in seen and len(seen) == 120, len(seen)     # mid tier on its first tick
seen.clear(); scene._YTF["next"] = 0
scene.yt_fast_once(now=1002)
assert len(seen) == scene.YT_FAST_N + scene.YT_FAST_IN and "v119" not in seen  # 2 s later: only the fast set
assert scene._FPEAK["yt:c119"] == 4900                                          # in-between peak kept for the day
print("YT MID OK")
