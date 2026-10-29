"""Channel ranks: where a channel stands among every channel this site tracks on its platform, worldwide, in its
country and in its category. Recomputed every 30 minutes in the background (one pass over the latest daily
snapshot of each channel), so pages read them instantly.

Metrics
    size     subscribers (YouTube) / followers (Twitch, Kick): the latest daily snapshot
    views    YouTube: total channel views (lifetime)
    vday     YouTube: channel views gained in the last day; Twitch / Kick: followers gained
    v7       the same over 7 days
    growth   the same over 30 days
    live     hours watched live in the last 30 days (recorded by this site)
Country: YouTube's channel country, or India for channels detected as Indian. Category: YouTube's own category
(Gaming, People & Blogs, Music ...) for YouTube channels, the section of their most-streamed game for Twitch / Kick.
"""
import threading
import time
from datetime import datetime, timedelta

from tracker import events, store

_R = {"at": 0, "rank": {}, "tot": {}, "rows": {}}
_lock = threading.Lock()
_YT_FROM_SEC = {"gaming": "Gaming", "esports": "Gaming", "news": "News & Politics", "music": "Music", "sports": "Sports",
                "irl": "People & Blogs", "just-chatting": "People & Blogs", "devotional": "People & Blogs", "podcasts": "Entertainment"}
METRICS = ("size", "views", "vday", "v7", "growth", "live")


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
        def first_since(d):
            return {r[0]: (r[1], r[2], r[3]) for r in c.execute(
                """SELECT s.sid, s.subs, s.views, s.day FROM sc_chstats s JOIN (SELECT sid, MIN(day) d FROM sc_chstats WHERE day>=? GROUP BY sid) m
                   ON m.sid=s.sid AND m.d=s.day""", (d,))}
        old, old7 = first_since(d30), first_since((today - timedelta(days=7)).strftime("%Y-%m-%d"))
        hw = dict(c.execute("SELECT sid, SUM(hw) FROM sc_daily WHERE day>=? GROUP BY sid", (d30,)).fetchall())
        top_game = {}
        for sid, g, h in c.execute("SELECT sid, game, SUM(hw) FROM sc_daily WHERE day>=? GROUP BY sid, game", (d30,)):
            if h and (sid not in top_game or h > top_game[sid][1]):
                top_game[sid] = (g, h)
        chans = {r["sid"]: dict(r) for r in c.execute(
            "SELECT sid, platform, name, logo, url, country, COALESCE(india,0) india, game, topic, ytcat FROM sc_channels")}
    day1 = ytextra._latest_gains()
    rows = []
    for sid, ch in chans.items():
        L, O, O7 = latest.get(sid), old.get(sid), old7.get(sid)
        size = L[0] if L else None
        k = 1 if ch["platform"] == "youtube" else 0          # YouTube: views; Twitch / Kick: followers

        def gain(A):
            if not (L and A and L[k] is not None and A[k] is not None) or L[k] - A[k] < 0:
                return None
            return L[k] - A[k] if k == 0 or L[k] - A[k] <= .25 * max(L[k], 1) else None    # skip misread snapshots
        growth, v7 = gain(O), gain(O7)
        g1 = day1.get(sid)
        vday = g1[0 if k else 1] if g1 else None
        views = L[1] if k and L else None
        live = hw.get(sid) or 0
        if size is None and not live:
            continue
        ct = scene.country_of(ch["country"]) or (scene.country_of("IN") if ch["india"] else None)
        g = (top_game.get(sid) or (ch["game"], 0))[0] or ""
        sec = scene.section_of(g) if g else ""
        if ch["platform"] == "youtube":          # YouTube's own categories only (until known: nearest one to what they stream)
            cat = next((x for x in (ch["ytcat"], ch["topic"]) if x and x != "Other"), "") or _YT_FROM_SEC.get(sec, "")
        else:
            cat = scene.SECTION_NAMES.get(sec, "") if sec != "other" else ""
        rows.append({"sid": sid, "platform": ch["platform"], "name": ch["name"], "logo": ch["logo"], "url": ch["url"],
                     "country": ct[0] if ct else "", "country_name": ct[2] if ct else "", "category": cat or "", "game": g,
                     "size": size, "views": views, "vday": vday, "v7": v7, "growth": growth, "live": round(live)})
    return rows


def compute():
    rows = _rows()
    rank, tot = {}, {}
    for m in METRICS:
        for scope in ("world", "country", "category", "game"):
            groups = {}
            for r in rows:
                if r[m] is None or (m in ("live", "views") and not r[m]) or (m in ("growth", "vday", "v7") and r[m] <= 0):
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


def top(platform: str = "youtube", metric: str = "size", country: str = "", category: str = "", limit: int = 100, game: str = "") -> dict:
    with _lock:
        rows = [r for r in _R["rows"].values() if r["platform"] == platform and r[metric] is not None
                and (metric not in ("growth", "vday", "v7") or r[metric] > 0) and (metric not in ("live", "views") or r[metric])
                and (not country or r["country"] == country) and (not category or r["category"] == category)
                and (not game or r["game"] == game)]
        cats = sorted({r["category"] for r in _R["rows"].values() if r["platform"] == platform and r["category"]}, key=str.lower)
        ctrs = sorted({(r["country"], r["country_name"]) for r in _R["rows"].values() if r["platform"] == platform and r["country"]},
                      key=lambda x: x[1])
        at = _R["at"]
    rows.sort(key=lambda r: -r[metric])
    games = sorted({r["game"] for r in _R["rows"].values() if r["platform"] == platform and r["game"] and r["game"] != "Other"}, key=str.lower)
    return {"platform": platform, "metric": metric, "total": len(rows), "updated": at, "games": games,
            "rows": [{**r, "rank": i + 1} for i, r in enumerate(rows[:limit])],
            "categories": cats, "countries": [{"code": a, "name": b} for a, b in ctrs]}
