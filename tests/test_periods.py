"""Rankings periods (24h .. lifetime) and games-only filter. Run: python3 tests/test_periods.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/t.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from tracker import events, ranks, scene, store

today = datetime.now(events.REPORT_TZ).date()
D = lambda n: (today - timedelta(days=n)).strftime("%Y-%m-%d")
with store._lock:
    c = scene._db()
    from tracker import ytextra; ytextra._db()
    cols = {r[1] for r in c.execute("PRAGMA table_info(sc_channels)")}
    for sid, name, cat, game in (("yt:a", "Funny", "Comedy", "BGMI"), ("yt:b", "Gamer", "Gaming", "BGMI"), ("yt:c", "Newsy", "News & Politics", "")):
        row = {"sid": sid, "platform": "youtube", "name": name, "country": "IN", "india": 1, "ytcat": cat, "game": game}
        row = {k: v for k, v in row.items() if k in cols}
        c.execute(f"INSERT INTO sc_channels ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
        for n, (s, v) in {100: (1000, 10000), 20: (1500, 50000), 5: (1900, 80000), 0: (2000, 100000)}.items():
            mult = {"yt:a": 1, "yt:b": 2, "yt:c": 3}[sid]
            c.execute("INSERT INTO sc_chstats (sid, day, subs, views) VALUES (?,?,?,?)", (sid, D(n), s * mult, v * mult))
    c.commit()
ranks.compute()
r = ranks.top("youtube", "views_7d")
assert [x["sid"] for x in r["rows"]] == ["yt:c", "yt:b", "yt:a"], r["rows"]
assert r["rows"][0]["views_7d"] == 60000, r["rows"][0]["views_7d"]       # 300000 - 240000 (first reading inside 7 days)
assert ranks.top("youtube", "views_30d")["rows"][0]["views_30d"] == 150000
assert ranks.top("youtube", "views_all")["rows"][0]["views_all"] == 300000
assert ranks.top("youtube", "subs_3m")["rows"][0]["subs_3m"] == 6000 - 4500
assert r["history_from"] == D(100)
# games: only real games, and none when a non-gaming YouTube category is chosen
assert ranks.top("youtube", "views_7d", category="Comedy")["games"] == []
assert ranks.top("youtube", "views_7d", category="Gaming")["games"] == ["BGMI"]
assert "" not in ranks.top("youtube", "views_7d")["games"]
assert all(p in ranks.PERIODS for p in ("24h", "3d", "7d", "30d", "3m", "6m", "ytd", "1y", "all"))
# live rankings accept every period
for p in ("day", "3d", "week", "month", "3m", "6m", "ytd", "1y", "all"):
    scene.rankings(region="global", period=p)
# Kick / Twitch: views = their past broadcasts' views in the period
import time as _t
with store._lock:
    c = scene._db()
    row = {k: v for k, v in {"sid": "kick:anshyt", "platform": "kick", "name": "anshyt", "country": "IN", "india": 1, "game": "GTA V"}.items() if k in cols}
    c.execute(f"INSERT INTO sc_channels ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    c.execute("INSERT INTO sc_chstats (sid, day, subs, views) VALUES ('kick:anshyt', ?, 60000, NULL)", (D(0),))
    for vid, age, v in (("k1", 2, 30000), ("k2", 20, 50000), ("k3", 200, 70000)):
        c.execute("INSERT INTO yt_videos (vid, sid, ts, title, views, live, approx) VALUES (?,?,?,?,?,1,0)", (vid, "kick:anshyt", int(_t.time() - age * 86400), vid, v))
    c.commit()
ranks.compute()
k = ranks.top("kick", "views_7d")["rows"][0]
assert k["views_7d"] == 30000 and ranks.top("kick", "views_30d")["rows"][0]["views_30d"] == 80000 and k["views_all"] == 150000, k
print("PERIODS OK")
