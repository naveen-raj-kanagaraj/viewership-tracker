"""Read-only accuracy audit of the GTA 6 data (India focus). Run on the server from the repo folder:
    venv/bin/python scripts/audit_gta6.py [name ...]
Opens the database read-only; changes nothing. Prints where numbers can be wrong and why."""
import json, os, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TRACKER_DB", "data/tracker.db")
from tracker import scene                          # classify() only; no database writes

REL = scene.GTA6_RELEASE
IST = timezone(timedelta(hours=5, minutes=30))
c = sqlite3.connect("file:data/tracker.db?mode=ro", uri=True, timeout=60)
day0 = datetime.fromtimestamp(REL, IST).strftime("%Y-%m-%d")
f = lambda ts: datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M IST")


def head(t):
    print(f"\n=== {t}")


head("1. Scans since launch (gaps = minutes with no reading for streams outside the 2-second set)")
ts = [r[0] for r in c.execute("SELECT ts FROM sc_reg WHERE region='global' AND game='__all__' AND ts>=? ORDER BY ts", (REL,))]
gaps = [(a, b) for a, b in zip(ts, ts[1:]) if b - a > 600]
print(f"{len(ts)} scans, median gap {sorted(b - a for a, b in zip(ts, ts[1:]))[len(ts) // 2] / 60:.1f} min" if len(ts) > 2 else "no scans")
for a, b in gaps:
    print(f"  GAP {f(a)} -> {f(b)}: {(b - a) / 60:.0f} min with no scan")

head("2. Peaks that are too low: a stream's own highest reading is above its day's peak in the rankings")
q = """SELECT ch.name, v.sid, MAX(v.peak), (SELECT MAX(peak) FROM sc_daily d WHERE d.sid=v.sid AND d.day>=? AND d.game='GTA 6')
       FROM sc_vstreams v JOIN sc_channels ch ON ch.sid=v.sid WHERE v.last_ts>=? AND COALESCE(ch.india,0)=1
       GROUP BY v.sid HAVING MAX(v.peak) > 1.1 * COALESCE((SELECT MAX(peak) FROM sc_daily d WHERE d.sid=v.sid AND d.day>=? AND d.game='GTA 6'), 0)
       AND MAX(v.peak) >= 1000 ORDER BY MAX(v.peak) DESC LIMIT 40"""
for n, sid, vp, dp in c.execute(q, (day0, REL, day0)):
    print(f"  {n} ({sid}): stream peak {vp:,} vs ranking peak {dp or 0:,}")

head("3. Indian channels live since launch whose title says GTA 6 but with no GTA 6 day row (filed under another game)")
for sid, n, t, ll in c.execute("""SELECT ch.sid, ch.name, ch.title, ch.last_live FROM sc_channels ch WHERE COALESCE(ch.india,0)=1
        AND ch.last_live>=? AND NOT EXISTS (SELECT 1 FROM sc_daily d WHERE d.sid=ch.sid AND d.day>=? AND d.game='GTA 6')""", (REL, day0)):
    if t and scene.classify("", t) == "GTA 6":
        print(f"  {n} ({sid}) last live {f(ll)}: {t[:80]}")

head("4. GTA 6 channels with 1,000+ peak NOT counted as Indian (check: Indian streamers missing from India lists)")
for sid, n, ctry, pk, t in c.execute("""SELECT d.sid, ch.name, ch.country, MAX(d.peak), ch.title FROM sc_daily d JOIN sc_channels ch ON ch.sid=d.sid
        WHERE d.day>=? AND d.game='GTA 6' AND COALESCE(ch.india,0)=0 GROUP BY d.sid HAVING MAX(d.peak)>=1000 ORDER BY 4 DESC LIMIT 400""", (day0,)):
    if scene._ind_script(f"{n} {t or ''}") or (ctry or "").upper() == "IN" or any(w in f"{n} {t}".lower() for w in
                                                                                 ("india", "hindi", "tamil", "telugu", "desi", "bhai")):
        print(f"  {n} ({sid}) country={ctry} peak {pk:,}: {(t or '')[:70]}")

head("5. Channels kept out of GTA 6 lists by the stream check")
chk = c.execute("SELECT value FROM kv WHERE key='g6_check3'").fetchone()
bad = [s for s, x in (json.loads(chk[0]) if chk else {}).items() if not x[0]]
for s in bad[:60]:
    r = c.execute("SELECT name, title FROM sc_channels WHERE sid=?", (s,)).fetchone()
    print(f"  {r[0] if r else s} ({s}): {(r[1] or '')[:70] if r else ''}")
print(f"  {len(bad)} in total")

names = [a.lower() for a in sys.argv[1:]]
if names:
    head("6. Named channels")
    for nm in names:
        for sid, n, pl, ind, t, ll in c.execute("""SELECT sid, name, platform, india, title, last_live FROM sc_channels
                WHERE lower(name) LIKE ? ORDER BY last_live DESC LIMIT 5""", (f"%{nm}%",)):
            print(f"  {n} ({sid}, {pl}) india={ind} last live {f(ll) if ll else '-'}: {(t or '')[:70]}")
            for d, g, pk, mn, hw in c.execute("SELECT day, game, peak, mins, hw FROM sc_daily WHERE sid=? AND day>=? ORDER BY day, peak DESC",
                                              (sid, day0)):
                print(f"      {d} {g}: peak {pk:,}, {mn:.0f} min, {hw:,.0f} h watched")
            for vid, a, b, pk in c.execute("SELECT vid, first_ts, last_ts, peak FROM sc_vstreams WHERE sid=? AND last_ts>=? ORDER BY first_ts",
                                           (sid, REL)):
                print(f"      stream {vid} {f(a)} -> {f(b)} peak {pk:,}")
