"""GTA 6 stays hidden until GTA6_SHOW=1. Run: python3 tests/test_gta6.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/g.db"
os.environ.pop("GTA6_SHOW", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, catpage, scenepage
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
assert len({r["vid"] for r in kk}) >= len(scene.SWEEP_KICK_LANGS), len(kk)
print("GTA6 LAUNCH OK")
