"""Channel rankings with a game chosen rank live metrics by what each channel did while streaming that game
(GamerFleet: 90K peak in GTA 6 though most of his week was GTA V). Run: python3 tests/test_rank_game.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/r.db"
os.environ["GTA6_SHOW"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from tracker import store, scene, ranks, events, ytextra
scene.GTA6_RELEASE = 0
scene._db(); ytextra._db()
c = store.main()
today = datetime.now(events.REPORT_TZ).date()
D = lambda n: (today - timedelta(days=n)).strftime("%Y-%m-%d")
c.executemany("INSERT INTO sc_channels (sid, platform, name, country, india) VALUES (?,?,?,?,?)",
              [("yt:gf", "youtube", "GamerFleet", "IN", 1), ("yt:my", "youtube", "Mythpat", "IN", 1), ("yt:va", "youtube", "Vanoss", "US", 0)])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [
    (D(3), "yt:gf", "GTA V", 13414, 1, 990, 111143), (D(0), "yt:gf", "GTA 6", 89929, 2, 156, 131778),
    (D(0), "yt:my", "GTA 6", 125360, 3, 600, 544489), (D(1), "yt:my", "Minecraft", 200000, 4, 60, 100000),
    (D(0), "yt:va", "GTA 6", 71700, 5, 120, 80000)])
c.commit()
ranks.compute()
t = ranks.top("youtube", "peak_7d", game="GTA 6")
got = [(r["name"], r["peak_7d"]) for r in t["rows"]]
assert got == [("Mythpat", 125360), ("GamerFleet", 89929), ("Vanoss", 71700)], got      # Mythpat's 200K was Minecraft
assert "GTA 6" in t["games"]
a = ranks.top("youtube", "avg_7d", game="GTA 6")
assert {r["name"]: r["avg_7d"] for r in a["rows"]}["GamerFleet"] == round(131778 * 60 / 156)
assert ranks.top("youtube", "peak_7d")["rows"][0]["peak_7d"] == 200000                      # no game: every game
print("RANK BY GAME OK")
