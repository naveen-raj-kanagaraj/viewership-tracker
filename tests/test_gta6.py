"""GTA 6 stays hidden until GTA6_SHOW=1. Run: python3 tests/test_gta6.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/g.db"
os.environ.pop("GTA6_SHOW", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, catpage, scenepage
import time as _t
scene.GTA6_RELEASE = _t.time() + 86400        # the test checks the before-release switch, whatever today's date is
assert not scene.gta6_on() and scene.pinned() == []
assert scene.classify("", "GTA 6 SOON | SOULCITY RP") == "GTA V"          # hype titles are GTA V
assert scene.classify("Grand Theft Auto VI", "trailer 3 reaction") == "Other"
assert "Grand Theft Auto VI" not in scene.INDIA_CATS["twitch"] + scene.INDIA_CATS["kick"]
assert not scene.shown("GTA 6") and scene.shown("GTA V")
assert "const G6=false" in catpage.build_html("in") and "const G6=false" in scenepage.build_html()
from tracker.web import app
assert app.test_client().get("/global/c/gta-6").status_code == 404
print("GTA6 HIDDEN OK")

# at release it switches on by itself, and the sweep starts: every stream of it, however small, on all three platforms
scene.GTA6_RELEASE = 0
assert scene.gta6_on() and scene.shown("GTA 6") and scene.pinned() == ["GTA 6"] and scene.sweep_games() == ["GTA 6"]
assert scene.classify("", "GTA 6 FIRST DAY! wanted level 5") == "GTA 6" and scene.classify("Grand Theft Auto VI", "") == "GTA 6"
from tracker import platforms
calls = []
def fake_get(p, url, prm):
    calls.append((p, url, dict(prm)))
    if "games" in url:
        return {"data": [{"id": "999"}]}
    if p == "twitch":
        page = int(prm.get("after") or 0)
        return {"data": [{"user_login": f"s{page}_{i}", "user_name": f"S{page}_{i}", "title": "GTA 6 day one", "viewer_count": i % 5,
                          "game_name": "Grand Theft Auto VI", "language": "en"} for i in range(100)] if page < 3 else [],
                "pagination": {"cursor": str(page + 1)} if page < 3 else {}}
    if "categories" in url:
        return {"data": [{"id": 77, "name": "Grand Theft Auto VI"}]}
    return {"data": [{"slug": f"k{prm.get('language', 'x')}", "stream_title": "GTA 6", "viewer_count": 3,
                      "category": {"name": "Grand Theft Auto VI"}, "language": prm.get("language", "en")}]}
platforms._get = fake_get
platforms._cats.clear()
errs = {}
tw = scene.sweep_platform("twitch", "GTA 6", errs)
assert len(tw) == 300 and all(c[2].get("game_id") == "999" for c in calls if "streams" in c[1]), (len(tw), errs)
scene.time.sleep = lambda *_: None
kk = scene.sweep_platform("kick", "GTA 6", errs)
assert len({r["vid"] for r in kk}) >= 3, len(kk)              # by viewers/newest + 2 languages in turn
langs = set()
for _ in range(len(scene.SWEEP_KICK_LANGS)):
    calls.clear(); scene.sweep_platform("kick", "GTA 6", errs)
    langs |= {c[2].get("language") for c in calls if "livestreams" in c[1] and c[2].get("language")}
    assert sum(1 for c in calls if "livestreams" in c[1] and "category_id" in c[2]) <= 4 * 3
assert langs == set(scene.SWEEP_KICK_LANGS), langs                # every language comes round
from tracker import events as ev
ev._LIVE["cegc"] = {"kick:skyesports": {}}                        # a tournament live on Kick: sweep lists 1 scan in 3
cats = []
for _ in range(6):
    calls.clear(); scene.sweep_platform("kick", "GTA 6", errs)
    cats.append(sum(1 for c in calls if "livestreams" in c[1] and "category_id" in c[2]))
assert sum(1 for x in cats if x) == 2, cats
ev._LIVE.pop("cegc")
print("GTA6 LAUNCH OK")

# Kick has no next page: every stream the sweep found is remembered and re-read by broadcaster until it ends
rnd = {"n": 0}
def fake_kick(p, url, prm):
    if "categories" in url:
        return {"data": [{"id": 77, "name": "Grand Theft Auto VI"}]}
    if isinstance(prm, list):                 # re-read by broadcaster ids
        ids = [v for k, v in prm if k == "broadcaster_user_id"]
        return {"data": [{"slug": f"u{u}", "broadcaster_user_id": u, "stream_title": "GTA 6 grind", "viewer_count": 2,
                          "category": {"name": "Grand Theft Auto VI"}} for u in ids if u % 7]}   # every 7th has ended
    base = rnd["n"] * 1000 + hash(str(sorted(prm.items()))) % 900
    return {"data": [{"slug": f"u{base + i}", "broadcaster_user_id": base + i, "stream_title": "GTA 6", "viewer_count": 1,
                      "category": {"name": "Grand Theft Auto VI"}} for i in range(5)]}
platforms._get = fake_kick
platforms._cats.clear()
scene._SWEEP.pop("kick_known:GTA 6", None)
first = scene.sweep_platform("kick", "GTA 6", {})
rnd["n"] = 1
second = scene.sweep_platform("kick", "GTA 6", {})
v1, v2 = {r["vid"] for r in first}, {r["vid"] for r in second}
still = {v for v in v1 if int(v.split(":u")[1]) % 7}
assert still <= v2, len(still - v2)            # round-1 streams still live are counted in round 2 though the lists changed
assert not ({v for v in v1 if int(v.split(":u")[1]) % 7 == 0} & v2)   # ended ones are not
print("GTA6 KICK MEMORY OK", len(v1), len(v2))

# YouTube: videos search didn't return this time are re-counted from the live counter; ended ones dropped after 3 misses
yt_round = {"n": 0}
scene.yt_search_pages = lambda q, gl, pages: [{"vid": f"v{yt_round['n']}_{q}_{gl}", "channel": "c", "channel_id": f"UC{yt_round['n']}{gl}",
                                               "title": "GTA 6 live", "viewers": 5}]
counts = {}
scene._safe_count = lambda v: counts.get(v, 7)
scene._SWEEP.pop("yt_known:GTA 6", None)
scene._SWEEP["yt_cool"] = 0
a = scene.sweep_youtube("GTA 6", {})
yt_round["n"] = 1
for x in a:
    counts[x["vid"]] = 0 if x["vid"].endswith("_US") else 9
b = scene.sweep_youtube("GTA 6", {})
ids_b = {x["vid"] for x in b}
assert all(x["vid"] in ids_b for x in a if not x["vid"].endswith("_US"))
assert not any(x["vid"] in ids_b for x in a if x["vid"].endswith("_US"))
assert all(x["viewers"] == 9 for x in b if x["vid"].startswith("v0_"))
st = scene.sweep_status()
assert st["games"] == ["GTA 6"] and "youtube known:GTA 6" in st["stats"] and "kick known:GTA 6" in st["stats"], st
from tracker.web import app as app2
assert app2.test_client().get("/api/sweep").json["games"] == ["GTA 6"]
print("GTA6 YOUTUBE MEMORY OK", len(a), len(b))
