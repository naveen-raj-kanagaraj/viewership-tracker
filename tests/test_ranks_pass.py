"""ranks._rows reads sc_chstats / sc_daily in one pass each; the results match the old GROUP BY queries.
Run: python3 tests/test_ranks_pass.py"""
import os, sys, tempfile, random
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from tracker import store, scene, ranks, events, ytextra
scene._db(); ytextra._db(); c = store.main()
random.seed(1)
t = datetime.now(events.REPORT_TZ).date()
days = [(t - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(400)]
sids = [f"yt:{i}" for i in range(60)] + [f"kick:{i}" for i in range(40)]
c.executemany("INSERT INTO sc_channels (sid, platform, name, india) VALUES (?,?,?,1)",
              [(s, {"yt": "youtube"}.get(s.split(":")[0], s.split(":")[0]), s) for s in sids])
st, dl = [], []
for s in sids:
    base = random.randint(10**5, 10**8)
    for d in sorted(random.sample(days, 40)):
        base += random.randint(0, 10**4)
        st.append((d, s, random.randint(1000, 10**6), base, 1, 0))
    for d in random.sample(days, 30):
        dl.append((d, s, random.choice(["BGMI", "GTA 6"]), random.choice([5, 50, 900]), 0, random.randint(10, 300), random.random() * 50))
c.executemany("INSERT INTO sc_chstats (day, sid, subs, views, videos, ts) VALUES (?,?,?,?,?,?)", st)
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", dl); c.commit()
rows = {r["sid"]: r for r in ranks._rows()}
def first_since(d):
    return {r[0]: (r[1], r[2]) for r in c.execute("""SELECT s.sid, s.subs, s.views FROM sc_chstats s JOIN (SELECT sid, MIN(day) d
        FROM sc_chstats WHERE day>=? GROUP BY sid) m ON m.sid=s.sid AND m.d=s.day""", (d,))}
latest = {r[0]: (r[1], r[2]) for r in c.execute("""SELECT s.sid, s.subs, s.views FROM sc_chstats s JOIN (SELECT sid, MAX(day) d
        FROM sc_chstats GROUP BY sid) m ON m.sid=s.sid AND m.d=s.day""")}
n = 0
for p in ("3d", "7d", "30d", "3m", "6m", "ytd", "1y"):
    F = first_since(ranks.period_start(p).strftime("%Y-%m-%d"))
    for s in sids:
        r = rows.get(s)
        if not r or not s.startswith("yt:"):
            continue
        L, A = latest.get(s), F.get(s)
        d = L[1] - A[1] if L and A else None
        exp = d if d is not None and A[1] > 0 and 0 <= d <= .6 * L[1] else None
        assert r["views_" + p] == exp, (s, p, r["views_" + p], exp)
        n += 1
for p in ("7d", "30d", "1y"):
    d0 = ranks.period_start(p).strftime("%Y-%m-%d")
    pk = dict(c.execute("SELECT sid, MAX(peak) FROM sc_daily WHERE day>=? AND peak>=10 GROUP BY sid", (d0,)).fetchall())
    for s, r in rows.items():
        assert r["peak_" + p] == pk.get(s), (s, p, r["peak_" + p], pk.get(s))
assert n > 100, n
print("RANKS PASS OK", n)
