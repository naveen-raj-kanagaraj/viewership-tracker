"""PMGC watch-party rankings split India / outside India (owner, 27 Nov): each stream carries 'in' from the site's
India rules; only worldwide events (scene_world) get the split; PMGC's Kick list and official channels no longer make
a channel Indian on the India pages. Run: python3 tests/test_pmgc_split.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/s.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, store, scene, eventpage
scene._db()
ev = events.create("pmgc")
events.create("bmsd")
now = int(time.time())
with store._lock:
    c = events._db()
    for vid, ch, cid, kind in [("a", "Snax Gaming", "UCsnax0000000000000000", "watch party"),
                               ("b", "NERXOxLive", "UCnerx0000000000000000", "watch party"),
                               ("kick:amigomvp", "amigomvp", "kick:amigomvp", "watch party"),
                               ("o", "PUBG MOBILE Türkiye", "UCturk0000000000000000", "official")]:
        c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("pmgc", vid, ch, cid, "PMGC 2026 watch party", kind, now - 7200, now - 3600, 100, now - 5000))
    for ts in range(now - 7200, now - 3600, 60):
        c.execute("INSERT INTO ev_ticks VALUES (?,?,?,?,?,?,?)", ("pmgc", ts, 400, 4, 100, 300, 0))
        c.executemany("INSERT INTO ev_samples VALUES (?,?,?,?)", [("pmgc", ts, v, 100) for v in ("a", "b", "kick:amigomvp", "o")])
    c.commit()
scene._LIVE["yt:UCsnax0000000000000000"] = {"india": True}
scene._LIVE["yt:UCnerx0000000000000000"] = {"india": False}
scene._LIVE["kick:amigomvp"] = {"india": False}
d = eventpage._build(events.get("pmgc"))
assert d["split_in"] is True
flags = {x["channel"]: x["in"] for x in d["last_broadcast"]["streams"]}
assert flags == {"Snax Gaming": 1, "NERXOxLive": 0, "amigomvp": 0, "PUBG MOBILE Türkiye": 0}, flags
assert eventpage._build(events.get("bmsd")).get("split_in") is False
# PMGC (worldwide) lists don't mark channels Indian on the India pages any more
scene._CUR["at"] = 0
assert "kick:amigomvp" not in scene._curated()
scene._KNOWN["at"] = 0
assert "kick:amigomvp" not in scene.india_known() and "yt:UCturk0000000000000000" not in scene.india_known()
print("PMGC SPLIT OK")
