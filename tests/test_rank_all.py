"""ALL PLATFORMS channel rankings: YouTube, Twitch and Kick in one list for live numbers. Run: python3 tests/test_rank_all.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, ranks, events, ytextra, web
scene._db(); ytextra._db()
c = store.main()
d = datetime.now(events.REPORT_TZ).date().strftime("%Y-%m-%d")
c.executemany("INSERT INTO sc_channels (sid, platform, name, india) VALUES (?,?,?,?)",
              [("yt:a", "youtube", "A", 1), ("twitch:b", "twitch", "B", 0), ("kick:c", "kick", "C", 1)])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(d, "yt:a", "GTA 6", 900, 1, 60, 500), (d, "twitch:b", "GTA 6", 5000, 1, 60, 3000),
                                                              (d, "kick:c", "BGMI", 2000, 1, 60, 1000)])
c.commit(); ranks.compute()
t = ranks.top("all", "peak_7d")
assert [r["name"] for r in t["rows"]] == ["B", "C", "A"] and {r["platform"] for r in t["rows"]} == {"youtube", "twitch", "kick"}, t["rows"]
assert [r["name"] for r in ranks.top("all", "peak_7d", game="GTA 6")["rows"]] == ["B", "A"]
ind = ranks.top("all", "peak_7d", country="IN")["rows"]
assert [r["name"] for r in ind] == ["C", "A"] and [r["world_rank"] for r in ind] == [2, 3], ind      # India cards show the place worldwide
assert [r["world_rank"] for r in ranks.top("all", "peak_7d", country="IN", game="GTA 6")["rows"]] == [2]
assert "world_rank" not in ranks.top("all", "peak_7d")["rows"][0]
j = web.app.test_client().get("/api/topch?platform=all&metric=peak_7d").json
assert j["platform"] == "all" and j["total"] == 3, j
c.execute("INSERT INTO sc_channels (sid, platform, name, india) VALUES ('kick:d','kick','Dino Prasad',1)")
c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (d, "kick:d", "GTA 6", 99999, 1, 60, 500)); c.commit(); ranks.compute()
assert all(r["name"] != "Dino Prasad" for r in ranks.top("all", "peak_7d", country="IN")["rows"])     # removed by the owner
print("ALL PLATFORMS OK")
