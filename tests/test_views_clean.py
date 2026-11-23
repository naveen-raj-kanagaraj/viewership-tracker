"""Saved rankings with views gained = lifetime views are cleaned when loaded. Run: python3 tests/test_views_clean.py"""
import os, sys, tempfile, pickle
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import ranks
ranks.CACHE = tempfile.mkdtemp() + "/r.pkl"
base = {"platform": "youtube", "country": "IN", "country_name": "India", "category": "Gaming", "game": "", "size": 1,
        "views": None, "name": "x", "logo": "", "url": "", "vday": None, "v7": None, "growth": None, "live": 0}
rows = {"yt:bad": {**base, "sid": "yt:bad", "name": "Rajat", "views_7d": 2290600869, "views_30d": 2290600869, "views_all": 2290955112, "views_24h": 34301},
        "yt:ok": {**base, "sid": "yt:ok", "name": "PAJI", "views_7d": 88372003, "views_30d": 237621732, "views_all": 706062016, "views_24h": 12724056},
        "kick:k": {**base, "platform": "kick", "sid": "kick:k", "name": "K", "views_7d": 500, "views_all": None}}
pickle.dump({"at": 1.0, "rank": {}, "tot": {}, "rows": rows}, open(ranks.CACHE, "wb"))
assert ranks.load_cache()
t = ranks.top("youtube", "views_7d", "IN", "Gaming")
assert [r["name"] for r in t["rows"]] == ["PAJI"], t["rows"]
assert ranks._R["rows"]["yt:bad"]["views_24h"] == 34301 and ranks._R["rows"]["yt:bad"]["views_30d"] is None
assert ranks._R["rows"]["kick:k"]["views_7d"] == 500          # Kick / Twitch views are past broadcasts, not totals
print("VIEWS CLEAN OK")
