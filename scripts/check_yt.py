"""Read-only: what the server sees on YouTube for a channel's streams since GTA 6's release.
    venv/bin/python scripts/check_yt.py "channel name" [...]
Per stream: our readings (first, last, peak, number of readings) and what the watch page says (game card, title,
live / premiere flags). Changes nothing."""
import os, re, sqlite3, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TRACKER_DB", "data/tracker.db")
from tracker import scene, events
IST = timezone(timedelta(hours=5, minutes=30))
f = lambda t: datetime.fromtimestamp(t, IST).strftime("%d %b %H:%M")
c = sqlite3.connect("file:data/tracker.db?mode=ro", uri=True, timeout=60)
for nm in sys.argv[1:]:
    for sid, name, ind in c.execute("SELECT sid, name, india FROM sc_channels WHERE lower(name) LIKE ? AND sid LIKE 'yt:%' LIMIT 3",
                                    (f"%{nm.lower()}%",)):
        print(f"\n{name} ({sid}) india={ind}")
        for vid, a, b, pk, n in c.execute("SELECT vid, first_ts, last_ts, peak, n FROM sc_vstreams WHERE sid=? AND last_ts>=? ORDER BY first_ts",
                                          (sid, scene.GTA6_RELEASE)):
            gaps = [t for t, in c.execute("SELECT DISTINCT ts FROM sc_samples WHERE sid=? AND ts BETWEEN ? AND ? ORDER BY ts", (sid, a, b))]
            step = (sorted(y - x for x, y in zip(gaps, gaps[1:]))[len(gaps) // 2] / 60) if len(gaps) > 2 else 0
            try:
                h = events._http.get(f"https://www.youtube.com/watch?v={vid}", timeout=10,
                                     headers={"User-Agent": events._UA, "Accept-Language": "en"}).text
                flags = {k: (f'"{k}":true' in h) for k in ("isLiveContent", "isLive", "isUpcoming", "isPremiere")}
                page = "ok" if "ytInitialData" in h else "NOT A WATCH PAGE (blocked/consent)"
            except Exception as e:
                flags, page = {}, f"error {str(e)[:60]}"
            print(f"  {vid}: {f(a)} -> {f(b)} IST, peak {pk:,}, {n} readings, typical gap {step:.1f} min | page {page} "
                  f"| card {scene._yt_game(vid)} | {flags}")
