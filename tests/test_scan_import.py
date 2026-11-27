"""Owner, 28 Nov: MazyisLive's PMGC streams were not counted (titles say 'Global Championship' / 'GC DAY 1', no
PMGC); the live scan has his readings. Live list "import" copies them into the event for each broadcast day that
ended. Run: python3 tests/test_scan_import.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/e.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import events, store, scene

events._db()
c = store.main()
scene._schema(c) if hasattr(scene, "_schema") else None
c.executescript("""CREATE TABLE IF NOT EXISTS sc_channels (sid TEXT PRIMARY KEY, platform TEXT, name TEXT, url TEXT, logo TEXT,
    first_seen REAL, last_live REAL, title TEXT, game TEXT);
CREATE TABLE IF NOT EXISTS sc_samples (ts INTEGER, sid TEXT, viewers INTEGER, game TEXT);
CREATE TABLE IF NOT EXISTS sc_vstreams (vid TEXT PRIMARY KEY, sid TEXT, first_ts INTEGER, last_ts INTEGER,
    peak INTEGER, peak_at INTEGER, hw REAL, n INTEGER);""")
K = "pmgc"
d0 = datetime(2026, 11, 26, 17, 0, tzinfo=events.REPORT_TZ).timestamp()
D = 86400
for day in (0, 1):                         # official 17:00 to 22:30, then a regional tail until 23:30
    for m in range(0, 390, 1):
        ts = d0 + day * D + m * 60
        off = 100000 if m <= 330 else 2000
        c.execute("INSERT INTO ev_ticks VALUES (?,?,?,?,?,?,?)", (K, int(ts), off, 1, off, 0, 0))
c.execute("INSERT INTO sc_channels (sid, platform, name, title) VALUES ('yt:UCmazy','youtube','MazyisLive','now title')")
c.execute("INSERT INTO sc_channels (sid, platform, name, title) VALUES ('kick:mazyislive','kick','mazyislive','GC DAY 1')")
c.execute("INSERT INTO sc_vstreams VALUES ('v2','yt:UCmazy',?,?,7642,?,0,1)", (int(d0 + D + 3600), int(d0 + D + 18000), int(d0 + D + 9000)))
for i in range(0, 300, 5):                 # Day 2 YouTube readings every 5 minutes, and one after the broadcast
    c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (int(d0 + D + 3600 + i * 60), "yt:UCmazy", 4000 + i * 10, "BGMI"))
c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (int(d0 + D + 23000 + 3600), "yt:UCmazy", 99999, "BGMI"))
for i in range(0, 60, 5):                  # Day 1 Kick
    c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (int(d0 + 1800 + i * 60), "kick:mazyislive", 300 + i, "BGMI"))
c.commit()

w = events.broadcast_windows(K)
assert [x[0] for x in w] == ["2026-11-26", "2026-11-27"], w
assert w[0][2] == int(d0 + 330 * 60), "the regional tail is not the broadcast"

events._LL[K] = (time.time() + 1e9, 0, {"import": ["yt:UCmazy", "kick:mazyislive"]})
done = events.import_scan(K, now=d0 + 3 * D, force=True)
got = {(s, d): n for s, d, n in done}
assert got[("yt:UCmazy", "2026-11-27")] == 57, got
assert got[("kick:mazyislive", "2026-11-26")] == 12, got
assert got[("yt:UCmazy", "2026-11-26")] == 0 and got[("kick:mazyislive", "2026-11-27")] == 0
r = c.execute("SELECT channel, channel_id, kind, peak FROM ev_streams WHERE event=? AND vid='v2'", (K,)).fetchone()
assert tuple(r) == ("MazyisLive", "UCmazy", "watch party", 6800), tuple(r)   # 99,999 after the broadcast left out
ds = events.day_streams(K, "2026-11-27")
assert [x["channel"] for x in ds["watch"]] == ["MazyisLive"] and ds["watch"][0]["peak"] == 6800, ds
assert events.day_streams(K, "2026-11-26")["watch"][0]["vid"] == "kick:mazyislive"
# once only
assert events.import_scan(K, now=d0 + 3 * D, force=True) == []
assert c.execute("SELECT COUNT(*) FROM ev_samples WHERE vid='v2'").fetchone()[0] == 57
# a streamer the counter already tracked that day is left alone
c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) "
          "VALUES (?,?,?,?,?,?,?,?,?,?)", (K, "v9", "Other", "UCother", "", "watch party", d0, d0, 10, d0))
c.execute("INSERT INTO ev_samples VALUES (?,?,?,?)", (K, int(d0 + 3600), "v9", 10))
c.execute("INSERT INTO sc_vstreams VALUES ('v9','yt:UCother',?,?,10,?,0,1)", (int(d0), int(d0 + 7200), int(d0)))
c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (int(d0 + 3600), "yt:UCother", 50, "BGMI"))
c.commit()
events._LL[K] = (time.time() + 1e9, 0, {"import": ["yt:UCother"]})
assert events.import_scan(K, now=d0 + 3 * D, force=True)[0][2] == 0
# a day still on air is not imported yet
events._LL[K] = (time.time() + 1e9, 0, {"import": ["yt:UCnew"]})
assert [d for _, d, _ in events.import_scan(K, now=d0 + D + 340 * 60, force=True)] == ["2026-11-26"]

# eventpage disk copy
from tracker import eventpage
eventpage.DISK = tempfile.mkdtemp()
eventpage._disk_save("pmgc", {"name": "PMGC", "x": 1})
assert eventpage._disk_load("pmgc") == {"name": "PMGC", "x": 1}
eventpage._disk_save("pmgc", {"name": "changed"})          # within a minute: not rewritten
assert eventpage._disk_load("pmgc")["name"] == "PMGC"
print("ok")

# the counter picked him up mid-broadcast: the scan fills the earlier gap into the counter's own stream
c.execute("INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at) "
          "VALUES (?,?,?,?,?,?,?,?,?,?)", (K, "c3", "Late", "UClate", "", "watch party", d0, d0, 900, d0))
for i in range(120, 300, 1):
    c.execute("INSERT INTO ev_samples VALUES (?,?,?,?)", (K, int(d0 + i * 60), "c3", 900))
c.execute("INSERT INTO sc_vstreams VALUES ('c3scan','yt:UClate',?,?,10,?,0,1)", (int(d0), int(d0 + 18000), int(d0)))
for i in range(0, 300, 5):
    c.execute("INSERT INTO sc_samples VALUES (?,?,?,?)", (int(d0 + i * 60), "yt:UClate", 1200, "BGMI"))
c.commit()
events._LL[K] = (time.time() + 1e9, 0, {"import": ["yt:UClate"]})
n = dict(((s_, d), x) for s_, d, x in events.import_scan(K, now=d0 + 3 * D, force=True))[("yt:UClate", "2026-11-26")]
assert n == 23, n          # minutes 0..110 (before the counter's first reading at 120, minus 5 minutes)
assert c.execute("SELECT COUNT(*) FROM ev_samples WHERE vid='c3scan'").fetchone()[0] == 0
assert c.execute("SELECT peak FROM ev_streams WHERE vid='c3'").fetchone()[0] == 1200
print("ok 2")
