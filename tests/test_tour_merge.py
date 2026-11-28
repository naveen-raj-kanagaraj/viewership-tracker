"""Tournament pages and the esports table show the same streams and numbers as the site's tracker of the event
(28 Nov audit: FFWS 63 streams on its tournament page, 145 on the tracker; worldwide numbers on India's table).
Run: python3 tests/test_tour_merge.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/m.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, scene

K = "lp-ffws-t"
events.PRESETS[K] = {"name": "FFWS Global Finals 2026", "scene_world": True, "tour": "FFWS Global Finals 2026", "lp": True}
IND = {"UCin1"}
events.stream_india = lambda vid, cid="", title="", ch="", key="": cid in IND
events.avatar = lambda cid: "a:" + cid
rows = [{"vid": "v1", "channel": "Free Fire Esports Brasil", "channel_id": "UCbr1", "title": "FFWS", "kind": "official", "viewers": 100000},
        {"vid": "v2", "channel": "Nonstop Gaming", "channel_id": "UCin1", "title": "FFWS WP", "kind": "watch party", "viewers": 40000},
        {"vid": "v3", "channel": "TheDonato", "channel_id": "UCmx1", "title": "FFWS", "kind": "watch party", "viewers": 7000},
        {"vid": "v4", "channel": "TheDonato", "channel_id": "UCmx1", "title": "FFWS 2", "kind": "watch party", "viewers": 600},
        {"vid": "tiktok:ffesportsbr", "channel": "Free Fire Esports BR", "channel_id": "", "title": "FFWS", "kind": "official", "viewers": 12000},
        {"vid": "v5", "channel": "Ended", "channel_id": "UCx", "title": "FFWS", "kind": "watch party", "viewers": 0}]
events._MEMROWS[K] = (time.time(), rows)
E = {"key": K, "world": True, "name": "FFWS Global Finals 2026", "tour": "FFWS Global Finals 2026", "peak": 633000, "url": "/e/x/"}
scan = [{"sid": "yt:UCbr1", "name": "FF Brasil", "viewers": 95000, "logo": "L", "language": "pt", "country": "BR"},
        {"sid": "yt:UCzz9", "name": "Left out by the tracker", "viewers": 5000}]

# worldwide tracker, worldwide page: its streams are the list (the scan-only one it left out is not), counts its own
m, ok = scene._trk_merge(E, "global", scan)
assert ok and [x["sid"] for x in m] == ["yt:UCbr1", "yt:UCin1", "tiktok:ffesportsbr", "yt:UCmx1"], [x["sid"] for x in m]
assert m[0]["viewers"] == 100000 and m[0]["language"] == "pt" and m[0]["logo"] == "L"     # scan's details, tracker's count
assert next(x for x in m if x["sid"] == "yt:UCmx1")["viewers"] == 7600                   # two streams, one channel
assert sum(x["viewers"] for x in m) == 159600
# India page: only its Indian streams, and not its worldwide peak
m, ok = scene._trk_merge(E, "in", scan)
assert not ok and [x["sid"] for x in m] == ["yt:UCin1"], m
# an India tracker on a worldwide page adds to the scan's list
E2 = dict(E, world=False)
events.PRESETS[K]["scene_world"] = False
m, ok = scene._trk_merge(E2, "global", scan)
assert ok and "yt:UCzz9" in {x["sid"] for x in m} and len(m) == 5, m
m, ok = scene._trk_merge(E2, "in", scan)
assert ok and "yt:UCzz9" not in {x["sid"] for x in m}
events.PRESETS[K]["scene_world"] = True
# not counting (no official broadcast): nothing from the tracker
events._MEMROWS[K] = (time.time() - 60, rows)
assert scene._trk_merge(E, "global", scan)[0] is None
events._MEMROWS[K] = (time.time(), rows)

# the tournament page: worldwide = the tracker's streams, India = its Indian ones with India's own peak
scene._tracked_events = lambda r: [dict(E)] if r == "global" else [dict(E)]
scene.tournament_info = lambda n: {"game": "Free Fire"}
g = scene.tour_data("FFWS Global Finals 2026", "global")
assert g["now"] == 159600 and g["live_count"] == 4 and g["peak"] == 633000, (g["now"], g["live_count"], g["peak"])
i = scene.tour_data("FFWS Global Finals 2026", "in")
assert i["now"] == 40000 and i["live_count"] == 1 and i["peak"] == 40000, (i["now"], i["live_count"], i["peak"])
# peak by day and today's line from the tracker's page copy (worldwide page only for a worldwide tracker)
from tracker import eventpage
now = time.time()
eventpage._cache[K] = (now, {"days": [{"date": "2026-11-27", "peak": 462201}], "series_all": [[now - 90, 500000, 0, 0, 0]],
                             "series_recent": [[now - 30, 600000, 0, 0, 0], [now - 10, 610000, 0, 0, 0]]})
g = scene.tour_data("FFWS Global Finals 2026", "global")
assert {"day": "2026-11-27", "peak": 462201} in g["days"] and [p[1] for p in g["series"]] == [500000, 600000, 610000], g["series"]
assert g["peak_today"] == 610000
i = scene.tour_data("FFWS Global Finals 2026", "in")
assert {"day": "2026-11-27", "peak": 462201} not in i["days"] and 610000 not in [p[1] for p in i["series"]]

# a TikTok stream counts when the site's tournament matcher puts its title on the event
ev = {"key": K, "match": ["ffws global finals 2026"], "videos": [], "excluded": [], "tour": "FFWS Global Finals 2026"}
scene.tournament = lambda t, g="": "FFWS Global Finals 2026" if "ffws" in t.lower() else None
assert events._tour_named(ev, {"vid": "tiktok:x", "title": "CHUNG KẾT THẾ GIỚI FFWS GF 2026"})
assert not events._tour_named(ev, {"vid": "tiktok:x", "title": "ranked free fire"})
print("TOUR MERGE OK")
