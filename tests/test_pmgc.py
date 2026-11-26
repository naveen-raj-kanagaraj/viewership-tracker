"""PMGC 2026: PUBG MOBILE's own channels are official; watch parties (YouTube search, listed channels, Kick, the live
scan) count when the title names the event, including 'GC League | Gauntlet' titles. Run: python3 tests/test_pmgc.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/p.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, scene
ev = events.create("pmgc")
assert ev["name"] == "PMGC 2026" and events.opt(ev, "game") == "PUBG Mobile"
off = {"vid": "o1", "channel": "PUBG MOBILE Esports", "channel_id": "UCmeeY9kzNswUpbYyJntb3Aw",
       "title": "[EN] 2026 PMGC League | Gauntlet Day 1", "viewers": 90000}
tr = {"vid": "o2", "channel": "PUBG MOBILE Espor Türkiye", "channel_id": "UCtMMTyOYb20ZbYOBfsfQBOw",
      "title": "[TR] 2026 PMGC | Gauntlet 1. Gün", "viewers": 9000}
idn = {"vid": "o3", "channel": "PUBG MOBILE Indonesia", "channel_id": "UCkB_AwGXxPAKdahxGHpeC4Q",
       "title": "[ID] PMGC 2026 GAUNTLET HARI 1", "viewers": 30000}
wp = {"vid": "w1", "channel": "Snax Gaming", "channel_id": "UCQfBN7Ut5TiZJAhMo_Rgfyw",
      "title": "2026 GC League | Gauntlet Day 1 | WATCHPARTY WITH SNAX", "viewers": 4000}
other = {"vid": "x1", "channel": "Snax Gaming", "channel_id": "UCQfBN7Ut5TiZJAhMo_Rgfyw", "title": "BGMI rush gameplay",
         "viewers": 3000}
ffgc = {"vid": "x2", "channel": "FF Guy", "channel_id": "UCff", "title": "Free Fire global championship lol", "viewers": 10}
for s in (off, tr, idn, wp):
    assert events.relevant(ev, s), s["title"]
assert not events.relevant(ev, other) and not events.relevant(ev, ffgc)
kinds = {s["vid"]: events.kind_of(ev, s) for s in (off, tr, idn, wp)}
assert kinds == {"o1": "official", "o2": "official", "o3": "official", "w1": "watch party"}, kinds
kick = {"vid": "kick:snaxgaming", "channel": "snaxgaming", "channel_id": "kick:snaxgaming", "title": "PMGC watch party",
        "viewers": 500}
assert events.relevant(ev, kick) and events.kind_of(ev, kick) == "watch party"
assert not events.relevant(ev, {**kick, "title": "GTA RP"})          # listed on Kick, but only PMGC titles count
scene._LIVE.clear()
scene._LIVE.update({
    "yt:UCa": {"title": "2026 GC League Gauntlet Day 1 Watchparty", "name": "Some Tuber", "streams": {"va": 80}, "india": True},
    "yt:UCb": {"title": "PMGC 2026 live", "name": "Abroad", "streams": {"vb": 80}, "india": False},
    "kick:z": {"title": "BGMI scrims", "name": "z", "streams": {"kick:z": 50}, "india": True},
})
assert {s["vid"] for s in events.scene_matches(ev)} == {"va"}
assert [nm for rx, nm, _ in scene._T_RX if rx.search("2026 GC League | Gauntlet Day 1 | WATCHPARTY WITH SNAX")][:1] == ["PMGC"]
assert events.PRESETS["pmgc"]["next_start"] == "2026-11-26 17:00" and len(events.PRESETS["pmgc"]["official_channels"]) == 11
print("PMGC OK")
