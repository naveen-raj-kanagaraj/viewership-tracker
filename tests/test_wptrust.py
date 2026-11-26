"""Watch-party trust (owner, 26 Nov): channels that carried PUBG Mobile / BGMI tournaments before are trusted and
their chat is not read; channels with no such history are 'new' and only those get the chat check.
Run: python3 tests/test_wptrust.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/w.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, store, wptrust, ytextra
ev = events.create("pmgc")
events.create("bmsd")
# what this site recorded: a BMSD watch party is trusted, a PMGC 2026 stream (not verified yet) is not
with store._lock:
    c = events._db()
    c.executemany("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?)",
                  [("bmsd", "b1", "Snax", "UCsnaxsnaxsnaxsnaxsnax1", "BMSD watch party", "watch party", 1, 1, 10, 1),
                   ("pmgc", "p1", "Random", "UCrandomrandomrandomra1", "PMGC 2026 live", "watch party", 1, 1, 10, 1)])
    c.commit()
wptrust._from_db()
assert wptrust.status("UCsnaxsnaxsnaxsnaxsnax1") == "trusted" and "BMSD" in wptrust.why("UCsnaxsnaxsnaxsnaxsnax1")
assert wptrust.status("UCrandomrandomrandomra1") == "unchecked"
# a channel's Live tab: past PUBG Mobile tournaments -> trusted; only gameplay / other games -> new (sus)
TABS = {"UCwp": [{"title": "PMSL SEA Fall 2026 Day 3 LIVE watch party", "when": "Streamed 3 weeks ago"}],
        "UCgame": [{"title": "BGMI rank push live", "when": "Streamed 1 day ago"}, {"title": "GTA RP", "when": "2 days ago"}],
        "UCbgis": [{"title": "BGIS 2026 Grand Finals Day 2 | Hindi", "when": "Streamed 2 months ago"}]}
ytextra._yt_past = lambda cid, tab="streams": TABS[cid]
for cid in TABS:
    wptrust.check_channel(cid, cid)
assert [wptrust.status(c) for c in TABS] == ["trusted", "new", "trusted"]
# YouTube search results: past live streams of last year's PMGC are trusted; uploads (highlights) and official channels are not
RES = [{"vid": "a", "channel": "Mortal", "channel_id": "UCmortal", "title": "PMGC 2025 Grand Finals Watch Party", "when": "Streamed 1 year ago", "live": False},
       {"vid": "b", "channel": "Clips", "channel_id": "UCclips", "title": "PMGC 2025 best moments", "when": "11 months ago", "live": False},
       {"vid": "c", "channel": "PUBG MOBILE Esports", "channel_id": "UCmeeY9kzNswUpbYyJntb3Aw", "title": "PMGC 2025 Grand Finals", "when": "Streamed 1 year ago", "live": False},
       {"vid": "d", "channel": "Nobar ID", "channel_id": "UCnobar", "title": "NOBAR PMGC 2025 HARI 3", "when": "Streamed 1 year ago", "live": False}]
wptrust._search_past = lambda q, gl, pages=2: RES
wptrust._from_youtube()
assert [wptrust.status(c) for c in ("UCmortal", "UCclips", "UCmeeY9kzNswUpbYyJntb3Aw", "UCnobar")] == ["trusted", "unchecked", "unchecked", "trusted"]
# only 'new' channels get their chat read
mk = lambda vid, cid: {"vid": vid, "channel": cid, "channel_id": cid, "title": "PMGC 2026 Gauntlet Day 1 LIVE", "viewers": 100, "kind": "watch party"}
events._LIVE["pmgc"] = {"v1": mk("v1", "UCwp"), "v2": mk("v2", "UCgame"), "v3": mk("v3", "UCunknown"), "v4": mk("v4", "UCmortal")}
assert [d[2] for d in events.chat_due()] == ["v2"]
# a restart keeps it
wptrust.save()
wptrust._T.update(ch={}, checked={})
wptrust.load()
assert wptrust.status("UCwp") == "trusted" and wptrust.status("UCgame") == "new"
assert wptrust.PAST_RX.search("PMGC 2025 League Stage") and not wptrust.PAST_RX.search("Free Fire World Series 2026")
events._HANDLE["@SnaxGaming"] = "UCsnaxhandle"
wptrust._from_lists()
assert wptrust.status("UCsnaxhandle") == "trusted" and wptrust.status("UC27pyUnJTUyxe_z_0WxxNXw") == "trusted"   # listed by hand
print("WP TRUST OK")

# scheduled streams (owner, 26 Nov): found by the plain search before they go live, title-checked, their channel's
# history read before the start, counted from their first live minute
now = time.time()
UP = [{"vid": "s1", "channel": "Mortal", "channel_id": "UCmortal", "title": "PMGC 2026 GAUNTLET DAY 1 WATCH PARTY", "when": "", "live": False, "upcoming": True, "start": int(now + 1800)},
      {"vid": "s2", "channel": "Rando", "channel_id": "UCrando", "title": "PMGC 2026 Day 1 LIVE", "when": "", "live": False, "upcoming": True, "start": int(now + 1500)},
      {"vid": "s3", "channel": "Scrim guy", "channel_id": "UCscrim", "title": "PMGC teams scrims live", "when": "", "live": False, "upcoming": True, "start": int(now + 900)},
      {"vid": "s4", "channel": "Old", "channel_id": "UCold", "title": "PMGC 2026 Grand Finals watch party", "when": "", "live": False, "upcoming": True, "start": int(now + 15 * 86400)},
      {"vid": "s5", "channel": "Up", "channel_id": "UCup", "title": "PMGC 2025 highlights", "when": "1 year ago", "live": False, "upcoming": False, "start": 0},
      {"vid": "s6", "channel": "PUBG MOBILE Esports", "channel_id": "UCmeeY9kzNswUpbYyJntb3Aw", "title": "PMGC 2026 Gauntlet Day 1", "when": "", "live": False, "upcoming": True, "start": int(now + 1800)}]
wptrust._search_past = lambda q, gl, pages=2: UP
assert events.scheduled_search(events.events()["pmgc"]) == 2
assert set(events._SCHED["pmgc"]) == {"s1", "s2"}                    # scrims left out, a later stage's stream and uploads skipped, official polled anyway
assert "scrims" in events._REJ["pmgc"]["s3"]["why"]
cands = [c for c, _ in wptrust._candidates()]
assert "UCrando" in cands and "UCmortal" not in cands                # unknown scheduled channels get their history read before the start
assert events.set_stream("pmgc", "s2", False) and "s2" not in events._SCHED["pmgc"]
print("SCHEDULED OK")
