"""A tournament page uses this site's own tracker when there is one: its game and its (bigger) peak.
Run: python3 tests/test_tour_tracker.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, store
scene._db()
scene._tracked_events = lambda r: [{"name": "CEGC", "game": "BGMI", "url": "/e/cegc/", "peak": 117200, "peak_at": 1795001000}]
scene.tournament_info = lambda n: {"game": "PUBG Mobile", "url": "https://liquipedia.net/pubgmobile/CEGC"}
d = scene.tour_data("CEGC 2026", "in")
assert d["game"] == "BGMI" and d["peak"] == 117200 and d["peak_at"] == 1795001000 and d["tracker"]["url"] == "/e/cegc/", d
print("TOUR TRACKER OK")
