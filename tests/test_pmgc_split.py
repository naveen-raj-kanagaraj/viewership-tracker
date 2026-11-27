"""PMGC watch-party rankings split India / outside India (owner, 27 Nov): each stream carries 'in' from the site's
India rules; only worldwide events (scene_world) get the split; PMGC's Kick list and official channels no longer make
a channel Indian on the India pages. Run: python3 tests/test_pmgc_split.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/s.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, store, scene, eventpage
scene._db()
events._PREF.update(["kick:amigomvp", "kick:snaxgaming"])   # no Kick profile lookups from the test
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

# accuracy: the YouTube channel's own country decides; a Kick channel with the same name as a YouTube one takes its
# country; the owner's live list decides over everything
events._INC.clear(); events._ICTX.clear()
with store._lock:
    c = store.conn()
    c.execute("INSERT OR REPLACE INTO sc_channels (sid, platform, name, country) VALUES (?,?,?,?)", ("yt:UCsnax0000000000000000", "youtube", "Snax Gaming", "IN"))
    c.execute("INSERT OR REPLACE INTO sc_channels (sid, platform, name, country) VALUES (?,?,?,?)", ("yt:UCnerx0000000000000000", "youtube", "NERXOxLive", "TR"))
    c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              ("pmgc", "kick:snaxgaming", "snaxgaming", "kick:snaxgaming", "PMGC watch party", "watch party", now - 7200, now - 3600, 50, now - 5000))
    c.commit()
scene._LIVE.clear()
assert events.stream_india("a", "UCsnax0000000000000000", "x", "Snax Gaming") is True
assert events.stream_india("b", "UCnerx0000000000000000", "Team India 🇮🇳 PMGC", "NERXOxLive") is False   # country beats the title
assert events.stream_india("kick:snaxgaming", "kick:snaxgaming", "PMGC", "snaxgaming") is True          # same name as the YouTube channel
events.LIVE_DIR = __import__("pathlib").Path(tempfile.mkdtemp())
(events.LIVE_DIR / "pmgc.json").write_text('{"not_india": ["UCsnax0000000000000000"]}')
events._LL.clear()
assert events.stream_india("a", "UCsnax0000000000000000", "x", "Snax Gaming") is False                  # the owner's list wins
print("PMGC SPLIT ACCURACY OK")

# the channel's own bio decides over its country setting (Ansh YT: country India, "Nepali Esports Talent"), and the
# same streamer on YouTube and Kick is one streamer: same name, the YouTube About link to kick.com, or the Kick
# profile's YouTube link (owner, 27 Nov)
from tracker import profiles
(events.LIVE_DIR / "pmgc.json").write_text("{}")
events._LL.clear(); events._INC.clear(); events._ICTX.clear(); events._WHO.clear()
rows = [("v1", "Ansh YT", "UCansh0000000000000000"), ("kick:anshyt", "anshyt", "kick:anshyt"),
        ("v2", "Big Streamer", "UCbig00000000000000000"), ("kick:bigkick99", "bigkick99", "kick:bigkick99"),
        ("v3", "Handle Guy", "UChand0000000000000000"), ("kick:otherslug", "otherslug", "kick:otherslug"),
        ("v4", "Both Places", "UCboth0000000000000000"), ("kick:solo", "solo", "kick:solo")]
with store._lock:
    c = store.conn()
    for vid, ch, cid in rows:
        c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("pmgc", vid, ch, cid, "PMGC 2026 watch party", "watch party", now - 7200, now - 3600, 80, now - 5000))
        c.executemany("INSERT INTO ev_samples VALUES (?,?,?,?)", [("pmgc", ts, vid, 80) for ts in range(now - 7200, now - 3600, 60)])
    for cid in ("UCansh0000000000000000", "UCbig00000000000000000", "UChand0000000000000000", "UCboth0000000000000000"):
        c.execute("INSERT OR REPLACE INTO sc_channels (sid, platform, name, country) VALUES (?,?,?,?)", ("yt:" + cid, "youtube", "x", "IN"))
    c.commit()
about = {"UCansh0000000000000000": {"desc": "Nepali Esports Talent | PUBG Mobile", "links": [], "handle": "@AnshYT"},
         "UCbig00000000000000000": {"desc": "Gaming every day", "links": ["kick.com/bigkick99", "instagram.com/big"], "handle": "@BigStreamer"},
         "UChand0000000000000000": {"desc": "", "links": [], "handle": "@HandleGuyOfficial"},
         "UCboth0000000000000000": {"desc": "Indian streamer, big fan of Nepal's teams", "links": [], "handle": "@BothPlaces"}}
for cid, a in about.items():
    store.kv_set(f"ev_about:{cid}", {"ts": time.time(), "country": "", **a})
events._PREF.update(r[0] for r in rows if r[0].startswith("kick:"))   # no Kick lookups from the test
with profiles._L:
    profiles._P["kick:otherslug"] = ("", {"youtube": "https://youtube.com/@HandleGuyOfficial"})
    profiles._P["kick:solo"] = ("Streamer from Dhaka, Bangladesh", {})
    for s in ("kick:anshyt", "kick:bigkick99"):
        profiles._P[s] = ("", {})
wm = events.who_map("pmgc")
assert wm["kick:anshyt"] == "yt:UCansh0000000000000000", wm       # same name
assert wm["kick:bigkick99"] == "yt:UCbig00000000000000000", wm    # the YouTube About links to kick.com/bigkick99
assert wm["kick:otherslug"] == "yt:UChand0000000000000000", wm    # the Kick profile links to the YouTube handle
assert wm["kick:solo"] == "kick:solo" and wm["kick:snaxgaming"] == "yt:UCsnax0000000000000000", wm
assert events.stream_india("v1", "UCansh0000000000000000", "PMGC watch party", "Ansh YT") is False         # bio: Nepali
assert events.stream_india("kick:anshyt", "kick:anshyt", "PMGC watch party", "anshyt") is False            # his YouTube bio
assert events.stream_india("v2", "UCbig00000000000000000", "PMGC", "Big Streamer") is True                 # country IN, no bio hint
assert events.stream_india("v4", "UCboth0000000000000000", "PMGC", "Both Places") is True                  # says Indian
assert events.stream_india("kick:solo", "kick:solo", "PMGC", "solo") is False                              # Kick bio: Bangladesh
# a YouTube About page not read yet: the answer is kept a minute, not 30
events._INC.clear(); events._ABBUSY.add("UCbig00000000000000000")
events.stream_india("v2", "UCbig00000000000000000", "PMGC", "Big Streamer")
assert time.time() - events._INC["yt:UCbig00000000000000000"][0] > 1700
events._ABBUSY.discard("UCbig00000000000000000")
# the page: each stream carries its streamer, so the leaderboard shows Ansh once (YouTube + Kick)
events._INC.clear(); eventpage._CACHE.clear() if hasattr(eventpage, "_CACHE") else None
d = eventpage._build(events.get("pmgc"))
who = {x["vid"]: x["who"] for x in d["last_broadcast"]["streams"]}
assert who["kick:anshyt"] == who["v1"] == "yt:UCansh0000000000000000" and who["kick:solo"] == "kick:solo", who
ins = {x["vid"]: x["in"] for x in d["last_broadcast"]["streams"]}
assert ins["v1"] == 0 and ins["kick:anshyt"] == 0 and ins["v2"] == 1, ins
print("PMGC BIOS + SAME STREAMER OK")

# the daily CSV for the owner's Telegram bot: one row per stream, region column on worldwide events, sent once
from tracker import eventlog
data, cap, start = eventlog.day_csv("pmgc")
txt = data.decode("utf-8-sig").splitlines()
assert txt[0].startswith("Date,Rank,Channel,Platform,Type,Region,Peak viewers"), txt[0]
assert len(txt) > 5 and "PMGC" in cap, (len(txt), cap)
sent = []
eventlog._send = lambda t, d=None, n="": sent.append(n) or "ok"
eventlog.CSV_AFTER_MIN = 0
eventlog.send_day_csv(events.get("pmgc")); eventlog.send_day_csv(events.get("pmgc"))
assert len(sent) == 1 and sent[0].endswith("-viewership.csv"), sent
print("DAILY CSV OK")
