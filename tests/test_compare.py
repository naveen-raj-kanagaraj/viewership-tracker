"""Compare page numbers: growth only from full readings, the arrows' earlier range, today's part day. Run:
python3 tests/test_compare.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/c.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from tracker import events, scene, store, ytextra as yx

today = datetime.now(events.REPORT_TZ).date()
D = lambda n: (today - timedelta(days=n)).strftime("%Y-%m-%d")
with store._lock:
    c = scene._db()
    yx._db()
    # yt:A tracked 20 days: +1,000 views a day for the last 7 days, +500 a day the 7 before; one missed reading (day 10)
    for n in range(20, -1, -1):
        if n == 10:
            continue
        v = 10**7 + sum(1000 if k < 7 else 500 for k in range(n, 20))
        c.execute("INSERT INTO sc_chstats VALUES (?,?,?,?,?,?)", (D(n), "yt:A", 5000, v, 50, 0))
    # yt:B tracked 3 days only, its first reading broken (0 views): no 7-day growth, no 1-billion jump
    for n, v in ((3, 0), (2, 5 * 10**8), (1, 5 * 10**8 + 900), (0, 5 * 10**8 + 1900)):
        c.execute("INSERT INTO sc_chstats VALUES (?,?,?,?,?,?)", (D(n), "yt:B", 100, v, 10, 0))
    # live days: twitch:t tracked 30 days (peak 400 this week, 300 the week before); twitch:n first seen 3 days ago
    for sid, fs in (("twitch:t", time.time() - 30 * 86400), ("twitch:n", time.time() - 3 * 86400), ("yt:A", time.time() - 20 * 86400)):
        c.execute("INSERT INTO sc_channels (sid, platform, name, first_seen) VALUES (?,?,?,?)", (sid, sid.split(":")[0], sid, fs))
    for n in range(14):
        pk = 400 if n < 7 else 300
        c.execute("INSERT INTO sc_daily (day, sid, game, peak, peak_at, mins, hw) VALUES (?,?,?,?,?,?,?)",
                  (D(n), "twitch:t", "Just Chatting", pk, 0, 120, pk * .5 * 2))
        if n < 3:
            c.execute("INSERT INTO sc_daily (day, sid, game, peak, peak_at, mins, hw) VALUES (?,?,?,?,?,?,?)",
                      (D(n), "twitch:n", "BGMI", 50, 0, 60, 40))
    # a 5-minute spike is not a peak (same rule as the rankings)
    c.execute("INSERT INTO sc_daily (day, sid, game, peak, peak_at, mins, hw) VALUES (?,?,?,?,?,?,?)",
              (D(1), "twitch:t", "IRL", 90000, 0, 5, 10))
    c.commit()

G = yx.views_series("yt:A", 60)["gains"]
assert yx._gain(G, True, 7) == 7000, yx._gain(G, True, 7)
assert yx._gain(G, True, 7, 1) == 3500, yx._gain(G, True, 7, 1)          # day 10 missed: its 2-day gain split across
assert yx._gain(G, True, 30, 1) is None                                   # not tracked back then
GB = yx.views_series("yt:B", 60)["gains"]
assert GB[0]["views"] is None and yx._gain(GB, True, 7) is None, GB       # broken first reading, 3 days only
assert yx._gain(GB, True, 1) == 1000 and yx._gain(GB, True, 3) is None   # 2 of 3 days read: not enough

w = yx._window("twitch:t", 7)
assert w["peak"] == 400 and w["hours"] == 16.1, w      # the rankings' 7 days: today + 7 before; the spike adds time, not a peak
w1 = yx._window("twitch:t", 7, 1)
assert w1["peak"] == 300 and w1["hours"] == 12.0, w1                   # days 8-14 (only 8-13 recorded)
assert scene.channel("twitch:t")["periods"]["7d"]["peak"] == 400       # channel page: same window, same rule
ch = scene.channel("twitch:t")["periods"]
assert ch["7d"]["hours"] == 16.1 and ch["today"]["hours"] == 2.0 and ch["all"]["peak"] == 400, ch

# compare() with the channel page and video list stubbed
vid = lambda days, v: {"ts": time.time() - days * 86400, "views": v}
VIDS = {"yt:A": [vid(1, 100), vid(3, 300), vid(9, 1000), vid(12, 2000)], "twitch:t": [vid(2, 50), vid(9, 70)], "twitch:n": []}
scene.channel = lambda sid: {"name": sid, "platform": "youtube" if sid.startswith("yt:") else "twitch", "stats": None,
                             "periods": {"all": {"peak": 9}}}
yx.channel_videos = lambda sid: VIDS.get(sid, [])
yx.videos_summary = lambda sid, rng: {"count": 1}
J = yx.compare(["yt:A", "twitch:t", "twitch:n"], "7d")
A, T, N = J["channels"]
assert 7 <= J["done"] <= 8 and 6 <= J["done_g"] <= 7 and J["days"] == 7, J
assert A["growth"] == 7000 and A["prev"]["growth"] == 3500
assert A["prev"]["count"] == 2 and A["prev"]["views"] == 3000             # YouTube: the posts of the 7 days before
assert "count" not in T["prev"]                                           # Twitch VODs expire: no posts arrow
assert T["live"]["peak"] == 400 and T["prev"]["peak"] == 300 and T["prev"]["hours"] == 12.0
assert N["prev"]["peak"] is None and N["live"]["peak"] == 50              # first seen 3 days ago: no earlier week
assert yx.compare(["yt:A"], "all")["channels"][0]["prev"] == {} and yx.compare(["yt:A"], "all")["done"] == 0
J1 = yx.compare(["twitch:t"], "1d")
assert J1["days"] == 1 and 1 <= J1["done"] <= 2 and J1["channels"][0]["live"]["peak"] == 400

from tracker import comparepage
h = comparepage.build_html("in")
for k in ("['1d','1D']", "['3d','3D']", "['7d','7D']", "makeCard", "id=\"share\"", "id=\"mfmt\"", "const chg="):
    assert k in h, k
assert "__" not in h.replace("__name__", "")
print("COMPARE OK")
