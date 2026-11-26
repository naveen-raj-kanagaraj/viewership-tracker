"""PMGC Day 1 (26 Nov): streams that had ended kept being counted with the video's TOTAL views (Snax 199,552,
Cr7 HORAA 14,122 flat for 15 minutes), and a regional official stream with 1,282 viewers kept the day on air for
14 minutes after the 136K English stream ended. Run: python3 tests/test_ended_streams.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/e.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, store

events._db()
page = {}


def fake_page(vid):
    v = page[vid]
    if isinstance(v, Exception):
        raise v
    return None if v is None else {"vid": vid, "title": "", "channel": "", "channel_id": "", "viewers": v}


counter = {}


def fake_counter(vid):
    v = counter[vid]
    if isinstance(v, Exception):
        raise v
    return v


events.check_video = fake_page
events._count_live = fake_counter

# live: the counter's number
counter["snax"] = 52000
assert events._count_one("snax")[1] == 52000
# ended: the counter says "views" (None), the watch page still says live with the total views -> ended, not 199,552
events._CL.clear(); events._PAGE.clear()
counter["snax"], page["snax"] = None, 199552
assert events._count_one("snax")[1] is None
# the counter says views, the page says live with a number close to the last live count -> still live
events._CL.clear(); events._PAGE.clear()
counter["lolz"] = 30000
events._count_one("lolz")
events._CL.clear()
counter["lolz"], page["lolz"] = None, 30500
assert events._count_one("lolz")[1] == 30500
# the counter says views and the page can't be read (yt-dlp refuses an ended stream) -> ended, not an error
events._CL.clear(); events._PAGE.clear()
counter["cr7"], page["cr7"] = None, RuntimeError("This live event has ended")
assert events._count_one("cr7")[1] is None
# the counter can't be read at all and the page fails -> an error (try again), never 'ended'
events._CL.clear(); events._PAGE.clear()
counter["x"], page["x"] = RuntimeError("no counter"), RuntimeError("timeout")
assert events._count_one("x")[1] == "err"
# the counter can't be read, the page says live -> the page's number (the counter sometimes stops answering)
events._CL.clear(); events._PAGE.clear()
counter["y"], page["y"] = RuntimeError("no counter"), 8000
assert events._count_one("y")[1] == 8000
print("ENDED STREAMS OK")

# the main official stream ended: under 10% of the broadcast's official peak (once past 20,000) is over
now = time.time()
events._OFFPK.clear()
assert events.broadcast_over("pmgc", 14, now) is False           # pre-show: tiny, still on
assert events.broadcast_over("pmgc", 136290, now) is False
assert events.broadcast_over("pmgc", 32534, now) is False         # the lowest before the end on Day 1 (24%)
assert events.broadcast_over("pmgc", 22069, now) is False         # 16%: regional streams still on
assert events.broadcast_over("pmgc", 1282, now) is True           # only a 1,282 regional stream left
assert events.is_over("pmgc")
assert events.broadcast_over("pmgc", 60000, now) is False and not events.is_over("pmgc")   # back on
# a small event never trips it
events._OFFPK.clear()
assert events.broadcast_over("small", 3000, now) is False and events.broadcast_over("small", 10, now) is False
# after a restart the peak comes from the last 3 hours of readings
with store._lock:
    c = events._db()
    c.execute("INSERT INTO ev_ticks VALUES (?,?,?,?,?,?,?)", ("pmgc", int(now) - 3600, 300000, 50, 136290, 160000, 0))
    c.commit()
events._OFFPK.clear()
assert events.broadcast_over("pmgc", 1282, now) is True
events._OFFPK.clear()
assert events.broadcast_over("pmgc", 1282, now + 5 * 3600) is False   # a new day: nothing in the last 3 hours
print("BROADCAST OVER OK")

# fast_tick: nothing is recorded once only a small regional stream is left
ev = events.create("pmgc")
events._OFFPK.clear()
events._LIVE["pmgc"] = {"en": {"vid": "en", "channel": "PUBG MOBILE Esports", "title": "PMGC", "kind": "official", "viewers": 136000},
                        "lolz": {"vid": "lolz", "channel": "LoLzZz Gaming", "title": "PMGC watch party", "kind": "watch party", "viewers": 30000}}
events.permitted = lambda e, x: True
counter.update(en=136000, lolz=30000)
events._CL.clear(); events._FAST.clear()
r = events.fast_tick(ev, now)
assert r.get("official_live") is True, r
events._LIVE["pmgc"]["en"] = {"vid": "en", "channel": "PUBG MOBILE Esports", "title": "PMGC", "kind": "official", "viewers": 1282}
counter.update(en=1282, lolz=44672)
events._CL.clear(); events._FAST.clear()
r = events.fast_tick(ev, now + 4)
assert r.get("official_live") is False, r
print("FAST TICK STOPS AT THE END OK")
