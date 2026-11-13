"""GTA 6 stays hidden until GTA6_SHOW=1. Run: python3 tests/test_gta6.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/g.db"
os.environ.pop("GTA6_SHOW", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, catpage, scenepage
assert not scene.GTA6_SHOW and scene.PINNED == []
assert scene.classify("", "GTA 6 SOON | SOULCITY RP") == "GTA V"          # hype titles are GTA V
assert scene.classify("Grand Theft Auto VI", "trailer 3 reaction") == "Other"
assert "Grand Theft Auto VI" not in scene.INDIA_CATS["twitch"] + scene.INDIA_CATS["kick"]
assert not scene.shown("GTA 6") and scene.shown("GTA V")
assert "const G6=false" in catpage.build_html("in") and "const G6=false" in scenepage.build_html()
from tracker.web import app
assert app.test_client().get("/global/c/gta-6").status_code == 404
print("GTA6 HIDDEN OK")
