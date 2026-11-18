"""2-second reads: top Twitch/Kick channels plus the biggest Indian ones; Kick failing (429) never stops Twitch, and
Kick's list halves for 10 minutes. Run: python3 tests/test_fast.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/f.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, platforms
scene._LIVE.clear()
for i in range(1500):
    scene._LIVE[f"twitch:t{i}"] = {"platform": "twitch", "viewers": 100000 - i, "india": i >= 1400, "streams": {}}
for i in range(800):
    scene._LIVE[f"kick:k{i}"] = {"platform": "kick", "viewers": 50000 - i, "india": i >= 700, "streams": {}}
platforms._keys = lambda p: True
asked = {}
mode = {"kick": "ok"}
def by_ids(p, ids):
    asked[p] = list(ids)
    if p == "kick" and mode["kick"] == "429":
        raise RuntimeError("Kick HTTP 429 Too Many Requests")
    return [{"vid": f"{p}:{x}", "viewers": 5} for x in ids]
platforms._by_ids = by_ids
n = scene.fast_once()
assert len(asked["twitch"]) == 1000 + 100 and len(asked["kick"]) == 300 + 100, (len(asked["twitch"]), len(asked["kick"]))
assert "t1499" in asked["twitch"] and "k799" in asked["kick"]           # Indian ones beyond the top list are read too
mode["kick"] = "429"
n = scene.fast_once()
assert n == 1100, n                                                      # Twitch still read every 2 seconds
assert scene._KFAST["cap"] == 150
mode["kick"] = "ok"
scene.fast_once()
assert len(asked["kick"]) == 150 + 100, len(asked["kick"])               # halved list for 10 minutes (+ Indian ones)
print("FAST OK")
