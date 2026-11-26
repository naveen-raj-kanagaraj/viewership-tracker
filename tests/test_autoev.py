"""Trackers made from Liquipedia: which tournaments get one, their official channels, and hand-made presets
winning. Run: python3 tests/test_autoev.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
from tracker import autoev, events, store, liquipedia

today = date(2026, 11, 25)
T = lambda name, game, st, s, e, wiki="freefire": {"id": f"{wiki}/{name.replace(' ', '_')}", "wiki": wiki, "game": game,
    "page": name.replace(" ", "_"), "name": name, "full": name, "series": name.split()[0], "status": st, "start": s, "end": e,
    "url": f"https://liquipedia.net/{wiki}/{name.replace(' ', '_')}"}
tours = [T("FFWS Global Finals 2026", "Free Fire", "ongoing", "2026-11-06", "2026-11-28"),
         T("PMGC 2026", "PUBG Mobile", "upcoming", "2026-11-26", "2026-12-13", "pubgmobile"),       # pmgc preset has it
         T("PGL Major Singapore 2026", "Counter-Strike 2", "ongoing", "2026-11-20", "2026-11-30", "counterstrike"),
         T("BLAST SLAM IX", "Dota 2", "ongoing", "2026-11-20", "2026-11-29", "dota2"),
         T("FFICC S2", "Free Fire", "upcoming", "2026-12-20", "2026-12-30"),                       # too far ahead
         T("Old Cup", "Free Fire", "completed", "2026-10-01", "2026-10-05")]
c = autoev.candidates(tours, today, {"PGL Major Singapore 2026": 9000, "BLAST SLAM IX": 800})
assert [t["name"] for t in c] == ["PGL Major Singapore 2026", "FFWS Global Finals 2026"], [t["name"] for t in c]

page = """{{Infobox league
|name=FFWS Global Finals 2026
|youtube=@FreeFireEsports
|youtube2=channel/UCaaaaaaaaaaaaaaaaaaaaaa
|twitch=https://www.twitch.tv/FreeFireEsports
|kick=
}}"""
assert autoev.links(page) == {"youtube": ["@FreeFireEsports", "UCaaaaaaaaaaaaaaaaaaaaaa"], "twitch": ["freefireesports"], "kick": []}
p = autoev.build(tours[0], page)
assert p["tour"] == "FFWS Global Finals 2026" and p["need_official"] and p["all_watch"]
assert p["kick"]["category"] == ["Free Fire"] and p["twitch"]["official"] == ["freefireesports"]
q = autoev.build(tours[2], "")
assert not q["need_official"] and not q["official_channels"]       # no official listed: on air whenever it is live

# sync: makes trackers (capped), merges them into PRESETS, events exist; finished ones are marked ended
store.kv_set("lp_tours", {"ts": 1, "tours": tours})
liquipedia._CACHE["ts"] = 0
autoev._page = lambda t: page
autoev._india_peaks = lambda: {"PGL Major Singapore 2026": 9000}
autoev.date = type("D", (date,), {"today": staticmethod(lambda: today)})
r = autoev.sync(force=True)
assert set(r["new"]) == {"PGL Major Singapore 2026", "FFWS Global Finals 2026"}, r
k = autoev.key_of(tours[0])
assert k in events.PRESETS and events.get(k) and len(k) <= 20 and "pmgc" in events.PRESETS
assert events.PRESETS["pmgc"].get("official_channels")                 # hand-made presets untouched
ev = events.get(k)
assert events.relevant(ev, {"vid": "a", "channel": "X", "channel_id": "UCx", "title": "FFWS Global Finals 2026 Day 3 LIVE", "viewers": 9})
assert not events.relevant(ev, {"vid": "b", "channel": "X", "channel_id": "UCx", "title": "FFWS 2025 Global Finals replay", "viewers": 9})
autoev.date = type("D", (date,), {"today": staticmethod(lambda: date(2026, 12, 5))})
r = autoev.sync(force=True)
assert "FFWS Global Finals 2026" in r["finished"] and events.PRESETS[k]["ended"] and events.paused(k)
print("AUTO TRACKERS OK")
