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
assert {s["vid"] for s in events.scene_matches(ev)} == {"va", "vb"}   # worldwide YouTube too (scene_world)
assert [nm for rx, nm, _ in scene._T_RX if rx.search("2026 GC League | Gauntlet Day 1 | WATCHPARTY WITH SNAX")][:1] == ["PMGC"]
assert events.PRESETS["pmgc"]["next_start"] == "2026-11-26 17:00" and len(events.PRESETS["pmgc"]["official_channels"]) == 11
print("PMGC OK")

# replays and last year's edition never count
for t in ("PMGC 2025 Grand Finals FULL REPLAY", "2025 PMGC League | Gauntlet Day 1", "PMGC 2026 Day 1 Highlights"):
    assert not events.relevant(ev, {**wp, "vid": "r", "title": t}), t
assert events.relevant(ev, {**wp, "vid": "r2", "title": "PMGC 2026 Gauntlet Day 1 LIVE | TEAM SOUL"})

# the poll loop: off air only the official channels are read; once one is live everything is searched
calls = {"search": 0, "feed": 0, "page": 0, "official": 0}
OFF_LIVE = []
def fake_off(oc):
    calls["official"] += 1
    return [dict(x) for x in OFF_LIVE] if oc == "UCmeeY9kzNswUpbYyJntb3Aw" else []
def fake_search(q, gl="IN", pages=3):
    calls["search"] += 1
    return [dict(wp)] if q == "PMGC 2026" else []
events.channel_live_all = fake_off
events._search = fake_search
events.feed_live = lambda h: calls.__setitem__("feed", calls["feed"] + 1) or []
events.check_channel = lambda h: calls.__setitem__("page", calls["page"] + 1) or None
events.platforms.discover = lambda e, p: []
events.next_start = lambda k: None
events.count_live = lambda vid: None
scene._LIVE.clear()
r = events.poll(ev, now=1_900_000_000)
assert calls["official"] == 11 and calls["search"] == calls["feed"] == calls["page"] == 0 and r["live"] == 0, calls
OFF_LIVE.append(off)
r = events.poll(ev, now=1_900_000_060)
assert calls["search"] >= 8 and calls["feed"] == len(events.PRESETS["pmgc"]["always_check"]) and 1 <= calls["page"] <= 10, calls
got = {s["vid"]: s["kind"] for s in r["streams"]}
assert got == {"o1": "official", "w1": "watch party"}, got
# official off air: searching goes on for 20 minutes (a break), then stops
OFF_LIVE.clear()
n = calls["search"]
events.poll(ev, now=1_900_000_060 + 600)
assert calls["search"] > n
n = calls["search"]
events.poll(ev, now=1_900_000_060 + 1500)
assert calls["search"] == n
print("PMGC LOOP OK")
