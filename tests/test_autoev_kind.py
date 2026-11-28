"""Automatic trackers: official = the publisher's channels by name; Liquipedia-listed creators are watch parties;
players naming the event are not counted (owner, 28 Nov, FFWS). Run: python3 tests/test_autoev_kind.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/k.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import autoev, events, store

t = {"id": "x1", "name": "FFWS Global Finals 2026", "game": "Free Fire", "series": "FFWS", "start": "2026-11-20", "end": "2026-11-28"}
p = autoev.build(t, "|youtube=UCaaaaaaaaaaaaaaaaaaaaaa\n|youtube2=UCbbbbbbbbbbbbbbbbbbbbbb")
assert p["official_strict"] and p["v"] == 3
assert ("mundial free fire", "BR") in p["world_queries"] and ("FFWS", "BR") in p["world_queries"], p["world_queries"]
K = "lp-ffws-test"
events.PRESETS[K] = p
ev = {"key": K, "match": p["match"], "videos": [], "excluded": [], "tour": p["tour"]}
k = lambda ch, **kw: events.kind_of(ev, {"vid": "v", "channel": ch, "title": "FFWS", **kw})
assert k("Free Fire Esports Brasil #FREEFIRE", from_official=True) == "official"
assert k("Garena Free Fire LATAM") == "official"
assert k("RAADVAI YT", from_official=True) == "watch party"       # listed by Liquipedia, still a creator
assert k("JotinhaTM") == "watch party"
assert k("FreeFireEsportsTH") == "official"
# a player naming the event is not counted
assert not events.relevant(ev, {"vid": "kick:zelika", "title": "12 H DE FREE FIRE !! HOY FINAL FFWS APARTE", "channel": "zelika"})

# stored streams re-labelled once
c = events._db()
c = store.main()
for vid, ch, kind in [("a", "RAADVAI YT", "official"), ("b", "Free Fire India Esports", "official"), ("c", "BAK", "official")]:
    c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) "
              "VALUES (?,?,?,?,?,?,?,?,?,?)", (K, vid, ch, "", "FFWS", kind, 1, 2, 10, 1))
c.commit()
assert events.relabel_once(ev) == 2
assert dict(c.execute("SELECT vid, kind FROM ev_streams WHERE event=?", (K,)).fetchall()) == {"a": "watch party", "b": "official", "c": "watch party"}
assert events.relabel_once(ev) == 0
# hand-made presets (PMGC) keep their own rules
assert not events.PRESETS["pmgc"].get("official_strict")
print("AUTOEV KIND OK")
