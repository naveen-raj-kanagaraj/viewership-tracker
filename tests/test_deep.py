"""Deep data: ranked set, 1-3 hour refresh, history backfill, metrics, benchmarks, standing, monthly, comments.
YouTube is faked. Run: python tests/test_deep.py"""
import os
import sys
import tempfile
import time

T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/d.db"
os.environ["YOUTUBE_API_KEY"] = "test"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import deep, events, ranks, scene, store, ytextra  # noqa: E402

scene._db()
c = deep._db()
now = time.time()
day = ytextra._day()
cid = lambda i: "UC" + f"{i:022d}"
calls = {"channels": 0, "comments": 0}


class R:
    def __init__(self, j, code=200):
        self._j, self.status_code, self.headers = j, code, {"content-type": "application/json"}

    def json(self):
        return self._j


def fake_get(url, *a, params=None, **k):
    params = params or {}
    if "youtube/v3/channels" in url:
        calls["channels"] += 1
        return R({"items": [{"id": x, "statistics": {"subscriberCount": "500000", "viewCount": str(10 ** 10), "videoCount": "50"},
                             "snippet": {"title": "X", "country": "IN"}} for x in params["id"].split(",")]})
    if "commentThreads" in url:
        calls["comments"] += 1
        return R({"items": [{"snippet": {"topLevelComment": {"snippet": {"authorDisplayName": "@fan", "textDisplay": "great video",
                                                                           "likeCount": 120, "publishedAt": "2026-11-10T10:00:00Z"}}}}]})
    return R({}, 404)


events._http.get = fake_get

# 60 Indian gaming channels (BGMI), sizes 20K to 1.2M; each with 12 long videos over the last 80 days
vids = []
for i in range(60):
    sid = "yt:" + cid(i)
    subs = 20_000 + i * 20_000
    c.execute("""INSERT INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game, country, india,
                 language, tracked, ytcat) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
              (sid, "youtube", f"Ch{i}", "", "", now, None, "", "BGMI", "IN", 1, "", "Gaming"))
    c.execute("INSERT INTO sc_chstats VALUES (?,?,?,?,?,?)", (day, sid, subs, subs * 100, 50, int(now)))
    for j in range(12):
        v = 10_000 + i * 1000 + j * 10
        vids.append((f"v{i:03d}{j:02d}x", sid, int(now - (5 + j * 6) * 86400), f"video {j}", v, int(v * (0.02 + i / 6000)),
                     int(v * 0.002), 600, 0, 0, int(now), 0, "", "BGMI", 20))
    vids.append((f"v{i:03d}99x", sid, int(now - 2 * 86400), "new one", 30_000, 900, 50, 600, 0, 0, int(now), 0, "", "BGMI", 20))
c.executemany("""INSERT INTO yt_videos (vid, sid, ts, title, views, likes, comments, secs, live, approx, updated, short, url, game, cat)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vids)
c.commit()

a, b = deep.ranked_set(force=True)
assert len(a) == 60 and a[0] == "yt:" + cid(59), (len(a), a[:2])            # biggest first

# refresh: all due now, none due again right after
n = deep.refresh_once()
assert n == 60 and calls["channels"] == 2, (n, calls)
assert deep.refresh_once() == 0
assert c.execute("SELECT COUNT(*) FROM sc_intra").fetchone()[0] == 60

# metrics and benchmarks
assert deep.metrics_once() >= 60
m = c.execute("SELECT * FROM ch_metrics WHERE sid=? AND fmt='long'", ("yt:" + cid(30),)).fetchone()
assert m["n"] == 12 and abs(m["like_rate"] - (0.02 + 30 / 6000)) < 1e-4, dict(m)
assert abs(m["eng_rate"] - (0.02 + 30 / 6000 + 0.002)) < 1e-4
b = c.execute("SELECT * FROM ch_bench WHERE scope='in' AND kind='game' AND grp='BGMI' AND size='' AND fmt='long' AND metric='eng_rate'").fetchone()
assert b and b["n"] == 60 and b["p25"] < b["p50"] < b["p75"] < b["p90"], dict(b)
st = deep.standing("yt:" + cid(59))
f = st["formats"]["long"]
assert f["peers"] and all(p["pct"] >= 50 for p in f["peers"]), f["peers"]                 # most engaged: top half
assert deep.standing("yt:" + cid(0))["formats"]["long"]["peers"][0]["pct"] <= 25
assert st["size_band"] == "100K-1M"          # the refresh read 500K subscribers

# performance index: the new 2-day-old video at 30K vs a median of about 69K -> under 1
perf = deep.performance("yt:" + cid(59))
assert 0.3 < perf[f"v05999x"] < 0.6, perf.get("v05999x")

# monthly history
mon = deep.monthly("yt:" + cid(1), since=now - 100 * 86400)
assert sum(x["videos"] for x in mon) == 13 and all(x["eng_rate"] for x in mon)

# ranks: engagement metric for channels with 10K+ subscribers
ranks.compute()
t = ranks.top("youtube", "eng", country="IN")
assert t["rows"] and t["rows"][0]["sid"] == "yt:" + cid(59) and t["rows"][0]["eng"] > t["rows"][-1]["eng"]

# backfill: channels without history since January are fetched, biggest first
done = []
ytextra._refresh_videos = lambda sid, full, since_ts=None: (done.append((sid, since_ts)),
                                                           store.kv_set(f"vids:{sid}", {"since": since_ts}))
assert deep.backfill_once(n_api=5, n_free=0) == 5 and done[0] == ("yt:" + cid(59), deep.BACKFILL_FROM)
assert deep.backfill_once(n_api=5, n_free=0) == 5 and done[5][0] == "yt:" + cid(54)
assert deep.backfill_progress()["with_history"] == 10

# top comments on videos 1-8 days old, once each; text expires after 30 days
got = deep.comments_once(max_calls=10)
assert got == 10 and deep.comments_once(max_calls=10) == 10 and calls["comments"] == 20
assert deep.top_comments("yt:" + cid(59))[0]["text"] == "great video"
c.execute("UPDATE yt_comments SET fetched=?", (now - 31 * 86400,))
c.commit()
deep.comments_once(max_calls=0)
assert c.execute("SELECT COUNT(*) FROM yt_comments").fetchone()[0] == 0
print("DEEP OK")
