"""Channel ranks: where a channel stands among every channel this site tracks on its platform, worldwide, in its
country and in its category. Recomputed every 30 minutes in the background (one pass over the latest daily
snapshot of each channel), so pages read them instantly.

Metrics
    size     subscribers (YouTube) / followers (Twitch, Kick): the latest daily snapshot
    growth   YouTube: channel views gained in the last 30 days; Twitch / Kick: followers gained in 30 days
    live     hours watched live in the last 30 days (recorded by this site)
Country: YouTube's channel country, or India for channels detected as Indian. Category: YouTube's topic tags
(Gaming, Music, Sports ...) for YouTube channels, the section of their most-streamed game for Twitch / Kick.
"""
import threading
import time
from datetime import datetime, timedelta

from tracker import events, store

_R = {"at": 0, "rank": {}, "tot": {}, "rows": {}}
_lock = threading.Lock()
METRICS = ("size", "growth", "live")


def _rows():
    from tracker import scene, ytextra
    today = datetime.now(events.REPORT_TZ).date()
    d30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    with store._lock:
        c = scene._db()
        ytextra._db()
        latest = {r[0]: (r[1], r[2]) for r in c.execute(
            """SELECT s.sid, s.subs, s.views FROM sc_chstats s JOIN (SELECT sid, MAX(day) d FROM sc_chstats GROUP BY sid) m
               ON m.sid=s.sid AND m.d=s.day""")}
        old = {r[0]: (r[1], r[2]) for r in c.execute(
            """SELECT s.sid, s.subs, s.views FROM sc_chstats s JOIN (SELECT sid, MIN(day) d FROM sc_chstats WHERE day>=? GROUP BY sid) m
               ON m.sid=s.sid AND m.d=s.day""", (d30,))}
        hw = dict(c.execute("SELECT sid, SUM(hw) FROM sc_daily WHERE day>=? GROUP BY sid", (d30,)).fetchall())
        top_game = {}
        for sid, g, h in c.execute("SELECT sid, game, SUM(hw) FROM sc_daily WHERE day>=? GROUP BY sid, game", (d30,)):
            if h and (sid not in top_game or h > top_game[sid][1]):
                top_game[sid] = (g, h)
        chans = {r["sid"]: dict(r) for r in c.execute(
            "SELECT sid, platform, name, logo, url, country, COALESCE(india,0) india, game, topic FROM sc_channels")}
    rows = []
    for sid, ch in chans.items():
        L, O = latest.get(sid), old.get(sid)
        size = L[0] if L else None
        if ch["platform"] == "youtube":
            growth = (L[1] - O[1]) if L and O and L[1] is not None and O[1] is not None else None
        else:
            growth = (L[0] - O[0]) if L and O and L[0] is not None and O[0] is not None else None
        live = hw.get(sid) or 0
        if size is None and not live:
            continue
        ct = scene.country_of(ch["country"]) or (scene.country_of("IN") if ch["india"] else None)
        g = (top_game.get(sid) or (ch["game"], 0))[0] or ""
        cat = ch["topic"] if ch["platform"] == "youtube" and ch["topic"] else (scene.SECTION_NAMES.get(scene.section_of(g), "") if g else "")
        rows.append({"sid": sid, "platform": ch["platform"], "name": ch["name"], "logo": ch["logo"], "url": ch["url"],
                     "country": ct[0] if ct else "", "country_name": ct[2] if ct else "", "category": cat or "", "game": g,
                     "size": size, "growth": growth, "live": round(live)})
    return rows


def compute():
    rows = _rows()
    rank, tot = {}, {}
    for m in METRICS:
        for scope in ("world", "country", "category", "game"):
            groups = {}
            for r in rows:
                if r[m] is None or (m == "live" and not r[m]) or (m == "growth" and r[m] <= 0):
                    continue
                key = {"world": "", "country": r["country"], "category": r["category"], "game": r["game"]}[scope]
                if scope != "world" and not key:
                    continue
                groups.setdefault((r["platform"], scope, key), []).append(r)
            for gk, L in groups.items():
                L.sort(key=lambda r: -r[m])
                tot[(m,) + gk] = len(L)
                for i, r in enumerate(L):
                    rank[(r["sid"], m, gk[1])] = i + 1
    with _lock:
        _R.update(at=time.time(), rank=rank, tot=tot, rows={r["sid"]: r for r in rows})
    return len(rows)


def run_forever():
    time.sleep(90)
    while True:
        try:
            compute()
        except Exception as e:
            print(f"Ranks: {str(e)[:150]}")
        time.sleep(1800)


def start():
    threading.Thread(target=run_forever, daemon=True).start()


def for_channel(sid: str) -> list:
    """[{metric, scope, rank, of, where}] for one channel, best ranks first."""
    with _lock:
        r = _R["rows"].get(sid)
        if not r:
            return []
        out = []
        for m in METRICS:
            for scope, key in (("world", ""), ("country", r["country"]), ("category", r["category"]), ("game", r["game"])):
                k = (sid, m, scope)
                if k in _R["rank"]:
                    where = {"world": "worldwide", "country": r["country_name"], "category": key, "game": key}[scope]
                    out.append({"metric": m, "scope": scope, "rank": _R["rank"][k],
                                "of": _R["tot"].get((m, r["platform"], scope, key), 0), "where": where})
    return out


def top(platform: str = "youtube", metric: str = "size", country: str = "", category: str = "", limit: int = 100) -> dict:
    with _lock:
        rows = [r for r in _R["rows"].values() if r["platform"] == platform and r[metric] is not None
                and (metric != "growth" or r[metric] > 0) and (metric != "live" or r[metric])
                and (not country or r["country"] == country) and (not category or r["category"] == category)]
        cats = sorted({r["category"] for r in _R["rows"].values() if r["platform"] == platform and r["category"]})
        ctrs = sorted({(r["country"], r["country_name"]) for r in _R["rows"].values() if r["platform"] == platform and r["country"]},
                      key=lambda x: x[1])
        at = _R["at"]
    rows.sort(key=lambda r: -r[metric])
    return {"platform": platform, "metric": metric, "total": len(rows), "updated": at,
            "rows": [{**r, "rank": i + 1} for i, r in enumerate(rows[:limit])],
            "categories": cats, "countries": [{"code": a, "name": b} for a, b in ctrs]}
