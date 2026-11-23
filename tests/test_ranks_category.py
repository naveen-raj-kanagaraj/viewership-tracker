"""A YouTube streamer's category is what it streams, whatever YouTube's own label. Run: python3 tests/test_ranks_category.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, ranks, events, ytextra
scene._db(); ytextra._db()
c = store.main()
d = datetime.now(events.REPORT_TZ).date().strftime("%Y-%m-%d")
c.executemany("INSERT INTO sc_channels (sid, platform, name, country, india, ytcat) VALUES (?,?,?,?,?,?)",
              [("yt:carry", "youtube", "CarryisLive", "IN", 1, "Entertainment"), ("yt:cric", "youtube", "CricTalks", "IN", 1, "Gaming"),
               ("yt:music", "youtube", "Music guy", "IN", 1, "Music")])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(d, "yt:carry", "GTA 6", 100000, 0, 300, 90000),
                                                              (d, "yt:cric", "Cricket", 50000, 0, 300, 40000),
                                                              (d, "yt:music", "Other", 500, 0, 60, 300)])
c.commit()
ranks.compute()
cat = {sid: r["category"] for sid, r in ranks._R["rows"].items()}
assert cat == {"yt:carry": "Gaming", "yt:cric": "Sports", "yt:music": "Music"}, cat
assert [r["name"] for r in ranks.top("youtube", "peak_7d", "IN", "Gaming")["rows"]] == ["CarryisLive"]
print("RANKS CATEGORY OK")
