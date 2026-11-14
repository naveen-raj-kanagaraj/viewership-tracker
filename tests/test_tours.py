"""Esports tournaments from Liquipedia: matching stream titles in any language, one combined number per tournament,
tournament pages and the esports page list; search from memory; read-only connections.
Run: python3 tests/test_tours.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/t.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import liquipedia, scene, store

RAW = {"freefire": """*Upcoming
** Battle_of_Morocco/2026 | BOM 2026 | startdate=Dec 04 | enddate=Dec 12
*Ongoing
** Free_Fire_World_Series/2026 | FFWS Global Finals 2026 | startdate=%s | enddate=%s
*Completed
** Free_Fire_World_Series/Brazil/2026/Split_2 | FFWS BR 2026 S2 | startdate=Sep 01 | enddate=Oct 01
""", "rainbowsix": """*Ongoing
** BLAST/Major/2026/Osaka | BLAST R6 Major Osaka 2026 | startdate=%s | enddate=%s
"""}
from datetime import datetime, timedelta, timezone
d = datetime.now(timezone.utc)
a, b = (d - timedelta(days=3)).strftime("%b %d"), (d + timedelta(days=5)).strftime("%b %d")
T = []
for w, raw in RAW.items():
    T += liquipedia.parse(w, raw % (a, b) if "%s" in raw else raw)
store.kv_set("lp_tours", {"ts": time.time(), "tours": T})
assert {t["name"] for t in liquipedia.active()} == {"FFWS Global Finals 2026", "BLAST R6 Major Osaka 2026"}

tm = scene.tournament
assert tm("FFWS GLOBAL FINALS 2026 | নকআউট ফেজ ১ |উইক ২ ডে ২", "Free Fire") == "FFWS Global Finals 2026"
assert tm("Free Fire World Series 2026 - Global Finals Dia 3", "Other") == "FFWS Global Finals 2026"
assert tm("BLAST R6 Osaka Major | Team Falcons vs. FaZe Clan | Playoffs - Day 2", "Rainbow Six Siege") == "BLAST R6 Major Osaka 2026"
assert tm("FAZE CLAN vs FALCONS - SEMI FINAL MAJOR OSAKA", "Rainbow Six Siege") == "BLAST R6 Major Osaka 2026"
assert tm("【Shadowverse: Worlds Beyond】Shadowverse Premier Series WGP Qualifier 2026", "Other") is None
assert tm("Shakey's Super League Unity Cup 2026 | PLAYOFFS | FEU vs. ATENEO", "Other") is None     # volleyball
assert tm("radio rwanda championship final vs", "Other") is None
assert tm("ranked push", "Valorant") is None

# three national Free Fire channels show the same tournament: one combined number
now = time.time()
mk = lambda sid, v, title, lang, india: {"sid": sid, "platform": "youtube", "name": sid[3:], "url": "", "logo": "", "game": "Free Fire",
                                         "title": title, "viewers": v, "streams": {sid + "v": v}, "india": india, "language": lang}
rows = [mk("yt:ffid", 40000, "FFWS GLOBAL FINALS 2026 | Indonesia", "id", False), mk("yt:ffbr", 30000, "FFWS Global Finals 2026 ao vivo", "pt", False),
        mk("yt:ffin", 12000, "FFWS GLOBAL FINALS 2026 Hindi", "hi", True), mk("yt:other", 5000, "rank push", "hi", True)]
for x in rows:
    x["tour"] = tm(x["title"], x["game"])
scene._store(rows, now, None)
for x in rows:
    x["viewers"] += 1000
scene._store(rows, now + 120, now)
d = scene.tour_data("FFWS Global Finals 2026", "global")
assert d["peak"] == 85000, d["peak"]                                # 41K + 31K + 13K at once
assert [c["sid"] for c in d["channels"]] == ["yt:ffid", "yt:ffbr", "yt:ffin"] and d["channels"][0]["peak"] == 41000
assert {l["lang"] for l in d["languages"]} == {"id", "pt", "hi"}
di = scene.tour_data("FFWS Global Finals 2026", "in")
assert di["peak"] == 13000 and [c["sid"] for c in di["channels"]] == ["yt:ffin"]
o = scene.tours_overview("global")
assert o["tournaments"][0]["name"] == "FFWS Global Finals 2026" and o["tournaments"][0]["peak"] == 85000
assert any(t["name"] == "BLAST R6 Major Osaka 2026" for t in o["ongoing_no_streams"])
assert scene.tour_name("ffws-global-finals-2026") == "FFWS Global Finals 2026"

from tracker.web import app
c = app.test_client()
r = c.get("/global/t/ffws-global-finals-2026"); assert r.status_code == 200 and b"FFWS Global Finals 2026" in r.data
assert c.get("/india/t/ffws-global-finals-2026").status_code == 200
assert c.get("/t/ffws-global-finals-2026").status_code == 301
assert c.get("/global/t/no-such-thing").status_code == 404
j = c.get("/api/tour?region=global&t=ffws-global-finals-2026").get_json(); assert j["peak"] == 85000
j = c.get("/api/tours?region=global").get_json(); assert j["tournaments"][0]["slug"] == "ffws-global-finals-2026"

# search: from memory, names before titles, biggest first, India filter
scene._search_build()
r = scene.search("ff", "global")
assert r["channels"] and r["channels"][0]["sid"] in ("yt:ffid", "yt:ffbr", "yt:ffin")
assert all(x["sid"] in ("yt:ffin", "yt:other") for x in scene.search("ff", "in")["channels"])
assert any(g["game"] == "Free Fire" for g in scene.search("free", "global")["categories"])

# read-only connections: a read block reads, a write inside it fails, a write under the lock still works
with store.reading():
    assert scene._db().execute("SELECT COUNT(*) FROM sc_channels").fetchone()[0] >= 4
    try:
        scene._db().execute("DELETE FROM sc_channels"); raise SystemExit("write allowed")
    except Exception as e:
        assert "readonly" in str(e)
    with store._lock:
        store.kv_set("x", 1)
# category bars from each day's stored peak give the same answer as from the raw totals
a_ = scene.categories("global", 60, "1m")
scene.backfill_reg_day()
b_ = scene.categories("global", 60, "1m")
assert [(r["game"], r["d30"], r["peak30"]) for r in a_["rows"]] == [(r["game"], r["d30"], r["peak30"]) for r in b_["rows"]]
assert scene._REGDAY_OK.get(store.DB_PATH)

# PIC Day 1 from the channel's own readings
from datetime import datetime as _dt
from tracker import events
t = int(_dt(2026, 11, 12, 19, 37, tzinfo=events.REPORT_TZ).timestamp())
with store._lock:
    c_ = scene._db()
    c_.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(t - 120, "yt:UCugG6-k5QGbq_iDEPAnG4NQ", 16000, "PUBG: Battlegrounds"),
                                                               (t, "yt:UCugG6-k5QGbq_iDEPAnG4NQ", 17448, "PUBG: Battlegrounds")])
    c_.commit()
events.get = lambda k=None: {"key": "pic"}
events.backfill_pic_day1()
assert events._db().execute("SELECT MAX(total) FROM ev_ticks WHERE event='pic'").fetchone()[0] == 17448
print("TOURS OK")
