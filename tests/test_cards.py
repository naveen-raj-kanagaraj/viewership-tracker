"""YouTube game cards decide the game; past GTA VI streams filed as Other are moved. Run: python3 tests/test_cards.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, events
scene._db(); c = store.main(); R = scene.GTA6_RELEASE + 86400
d = datetime.fromtimestamp(R, events.REPORT_TZ).strftime("%Y-%m-%d")
c.execute("INSERT INTO sc_channels (sid, platform, name, india, title) VALUES ('yt:red','youtube','Red parasite',1,'I EXPLORED VICE CITY FOR THE FIRST TIME! (LIVE) #3')")
c.execute("INSERT INTO sc_channels (sid, platform, name, india, title) VALUES ('yt:bg','youtube','BGMI guy',1,'rush gameplay')")
c.executemany("INSERT INTO sc_vstreams VALUES (?,?,?,?,?,?,?,?)", [("vr", "yt:red", R, R + 1500, 1746, R, 1, 1),
              ("vb", "yt:bg", R, R + 1500, 900, R, 1, 1)])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(d, "yt:red", "Other", 1746, R, 25, 659), (d, "yt:bg", "Other", 900, R, 25, 300)])
c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (R + 60, "yt:red", 1746, "Other")); c.commit()
scene._yt_game = lambda v: {"vr": ("Grand Theft Auto VI", "x"), "vb": ("Battlegrounds Mobile India", "y")}[v]
assert scene.refile_cards(since=R - 10) == 1
assert [tuple(r) for r in c.execute("SELECT game, peak FROM sc_daily WHERE sid='yt:red'")] == [("GTA 6", 1746)]
assert c.execute("SELECT game FROM sc_daily WHERE sid='yt:bg'").fetchone()[0] == "Other"
assert c.execute("SELECT game FROM sc_samples WHERE sid='yt:red'").fetchone()[0] == "GTA 6"
# live: the card decides the game even when the title never says GTA 6
scene._LIVE.clear(); scene._LIVE["yt:red"] = {"platform": "youtube", "viewers": 2000, "india": True, "streams": {"vr2": 2000}}
scene._yt_game = lambda v: ("Grand Theft Auto VI", "")
assert scene.cards_once() == 1 and scene._YCARD["vr2"] == "Grand Theft Auto VI"
assert scene.classify(scene._YCARD["vr2"], "I EXPLORED VICE CITY") == "GTA 6"
assert "eaglegaming" in scene.ALWAYS["kick"]
print("CARDS OK")
assert scene.not_in_game("DD News", "GTA 6") and scene.not_in_game("Bangla Tribune", "GTA 6") and not scene.not_in_game("Republic of Games", "GTA 6")
print("NEWS NAMES OK")
