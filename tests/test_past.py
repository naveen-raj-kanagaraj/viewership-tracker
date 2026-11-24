"""A channel's past streams: exact start dates and the peak of the stream's own days (owner, 24 Nov: '2 weeks ago'
put Jonathan's 4 Nov stream on 11 Nov with peak '-', and a stream that had just ended wasn't listed). Run:
python3 tests/test_past.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/p.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, scene, store, ytextra as yx

now = time.time()
SID = "yt:UCjon"
from datetime import datetime, timedelta
t8 = (datetime.now(events.REPORT_TZ) - timedelta(days=20)).replace(hour=22, minute=0, second=0, microsecond=0).timestamp()
tb = now - 25468 - 600                                    # 8 MILLION SPECIAL 22:00 IST (YouTube's exact start); Bentley
d8, d8b = yx._day(t8), yx._day(t8 + 19870)
with store._lock:
    c = scene._db()
    yx._db()
    c.execute("INSERT INTO yt_videos (vid, sid, ts, title, views, live, approx, updated) VALUES (?,?,?,?,?,?,?,?)",
              ("v8m", SID, int(t8), "8 MILLION SPECIAL", 4200000, 1, 0, int(now)))
    c.execute("INSERT INTO yt_videos (vid, sid, ts, title, views, live, approx, updated) VALUES (?,?,?,?,?,?,?,?)",
              ("vbent", SID, int(now - 3.5 * 86400), "BENTLEY CRATE OPENING", 2400000, 1, 0, int(now - 5 * 3600)))   # scheduled date
    c.execute("INSERT INTO sc_vstreams VALUES (?,?,?,?,?,?,?,?)", ("vbent", SID, int(tb), int(now - 600), 98634, int(tb + 3600), 0, 0))
    assert d8 != d8b
    for d, pk, mins in ((d8, 86886, 120), (d8b, 115243, 210)):      # it ran past midnight: its peak came the next day
        c.execute("INSERT OR REPLACE INTO sc_daily (day, sid, game, peak, peak_at, mins, hw) VALUES (?,?,?,?,?,?,?)",
                  (d, SID, "BGMI", pk, 0, mins, pk * mins / 60 * .7))
    c.commit()

yx._yt_past = lambda cid, tab="streams": [
    {"id": "vbent", "title": "BENTLEY CRATE OPENING", "ts": int(now - 540), "when": "Streamed 9 minutes ago", "views": 2400000, "secs": 25468, "url": ""},
    {"id": "v8m", "title": "8 MILLION SPECIAL", "ts": int(now - 14 * 86400), "when": "Streamed 2 weeks ago", "views": 4200000, "secs": 19870, "url": ""}]
P = yx.past_streams(SID)["streams"]
assert [x["id"] for x in P] == ["vbent", "v8m"]
B, M = P
assert B["ts"] == int(tb) and B["day"] == yx._day(tb) and B["peak"] == 98634       # when this site saw it go live
assert M["ts"] == int(t8) and M["day"] == d8, (M["day"], d8)                        # YouTube's exact start, not '2 weeks ago'
assert M["peak_day"] == 115243 and M["peak"] is None                                # its own day's peak, not '-'
assert yx._PAST[SID][2] == 600                                                      # just streamed: kept 10 minutes, not an hour

# a 'N ago' text that doesn't fit the stored date keeps the text's date (a re-used id, a wrong record)
yx._PAST.clear()
yx._yt_past = lambda cid, tab="streams": [{"id": "v8m", "title": "x", "ts": int(now - 2 * 86400), "when": "Streamed 2 days ago",
                                           "views": 1, "secs": 60, "url": ""}]
assert yx.past_streams(SID)["streams"][0]["ts"] == int(now - 2 * 86400)

# the stats reader picks the stream that just ended first (its stored date is the day it was scheduled)
os.environ["YOUTUBE_API_KEY"] = "test"
events.yt_quota_left = lambda *a: False
assert yx.video_stats_once(1) == 0
print("PAST OK")
