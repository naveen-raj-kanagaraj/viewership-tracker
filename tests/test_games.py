"""A channel counts in a game's lists only if it really streams that game; YouTube streams are filed by the game
YouTube shows under them; YouTube viewbots are left out (owner, 25 Nov). Run: python3 tests/test_games.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/g.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from tracker import events, ranks, scene, store, ytextra as yx

today = datetime.now(events.REPORT_TZ).date()
D = lambda n: (today - timedelta(days=n)).strftime("%Y-%m-%d")
with store._lock:
    c = scene._db(); yx._db()
    # ff: Free Fire every day, one 1-hour GTA 6 stream; g6: GTA 6 every day; mix: half and half
    for n in range(10):
        c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (D(n), "yt:ff", "Free Fire", 5000, 0, 240, 16000))
        c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (D(n), "yt:g6", "GTA 6", 3000, 0, 240, 9000))
        c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (D(n), "yt:mix", "BGMI" if n % 2 else "GTA 6", 2000, 0, 240, 6000))
    c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (D(2), "yt:ff", "GTA 6", 9000, 0, 60, 7000))
    c.commit()
base = {"platform": "youtube", "country": "IN", "country_name": "India", "category": "Gaming", "size": 100000}
ranks._R.update(at=time.time(), rank={}, tot={}, rows={
    "yt:ff": {**base, "sid": "yt:ff", "name": "FF Guy", "game": "Free Fire", "live_7d": 112000 + 7000, "live_30d": 167000},
    "yt:g6": {**base, "sid": "yt:g6", "name": "G6 Guy", "game": "GTA 6", "live_7d": 63000, "live_30d": 90000},
    "yt:mix": {**base, "sid": "yt:mix", "name": "Mix Guy", "game": "BGMI", "live_7d": 42000, "live_30d": 60000}})
ranks._GL.clear()
assert not ranks.plays("yt:ff", "GTA 6") and ranks.plays("yt:g6", "GTA 6") and ranks.plays("yt:mix", "GTA 6")
t = ranks.top("youtube", "peak_30d", "IN", game="GTA 6")
assert [r["sid"] for r in t["rows"]] == ["yt:g6", "yt:mix"], [r["sid"] for r in t["rows"]]    # FF Guy's one GTA stream: not listed
assert [r["sid"] for r in ranks.top("youtube", "peak_30d", "IN", game="Free Fire")["rows"]] == ["yt:ff"]

# YouTube game cards file a day by the game YouTube shows (here a 'GTA 6' title on a Free Fire stream)
now = time.time()
with store._lock:
    c = scene._db()
    c.execute("INSERT INTO sc_channels (sid, platform, name, india) VALUES ('yt:cb','youtube','Clickbait',1)")
    c.execute("INSERT INTO sc_vstreams VALUES ('v1','yt:cb',?,?,4000,?,0,0)", (int(now - 7200), int(now - 600), int(now - 3600)))
    c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (scene.datetime.fromtimestamp(now - 3600, events.REPORT_TZ).strftime("%Y-%m-%d"), "yt:cb", "GTA 6", 4000, 0, 100, 5000))
    c.commit()
scene._yt_game = lambda vid: ("Garena Free Fire", "GTA 6 LIVE 🔥 free fire rush")
d0 = scene.datetime.fromtimestamp(now - 3600, events.REPORT_TZ).strftime("%Y-%m-%d")
d1 = scene.datetime.fromtimestamp(now - 600, events.REPORT_TZ).strftime("%Y-%m-%d")
assert scene.refile_games(1) >= 1
with store.reading():
    g = store.conn().execute("SELECT game, peak FROM sc_daily WHERE sid='yt:cb'").fetchall()
assert [tuple(x) for x in g] == [("Free Fire", 4000)], [tuple(x) for x in g]
with store.reading():
    assert store.conn().execute("SELECT game FROM yt_card WHERE vid='v1'").fetchone()[0] == "Garena Free Fire"   # kept for restarts

# a YouTube channel with more watching than subscribers is a viewbot
assert ranks._viewbot(800, 2500, 900) and not ranks._viewbot(500000, 20000, 9000)
print("GAMES OK")

# watch parties: streams of the same match grouped, whatever the title's extra words
L = [{"sid": f"yt:{i}", "title": t, "viewers": v, "section": "sports", "game": "Sports"} for i, (t, v) in enumerate([
    ("🔴 Atlético-MG x Corinthians | Brasileirão AO VIVO", 105534), ("ATLÉTICO-MG X CORINTHIANS AO VIVO COM IMAGENS", 40000),
    ("Corinthians x Atlético-MG - jogo ao vivo", 36000), ("Flamengo x Palmeiras", 900), ("bate papo", 5000)])]
P = scene._parties(L)
assert P[0]["event"] == "Atlético-MG x Corinthians" and P[0]["streams"] == 3 and P[0]["viewers"] == 181534, P
assert len(P) == 1                                           # one small single stream is not a watch party
# YouTube streams that name no game go under the channel's YouTube category, not 'Other'
scene._YTC.update(at=time.time(), m={"yt:s": "Sports", "yt:n": "News & Politics", "yt:g": "Gaming"})
assert scene.yt_category_game("yt:s") == "Sports" and scene.yt_category_game("yt:n") == "News" and scene.yt_category_game("yt:g") == ""
assert scene.section_of("Sports") == "sports" and scene.section_of("Entertainment") == "other" and scene.section_of("People & Blogs") == "irl"
print("PARTIES AND CATEGORIES OK")
