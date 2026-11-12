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
import os
import pickle
import threading
import time
from datetime import datetime, timedelta

from tracker import events, store

_R = {"at": 0, "rank": {}, "tot": {}, "rows": {}}
_lock = threading.Lock()
_YT_FROM_SEC = {"gaming": "Gaming", "esports": "Gaming", "news": "News & Politics", "music": "Music", "sports": "Sports",
                "irl": "People & Blogs", "just-chatting": "People & Blogs", "devotional": "People & Blogs", "podcasts": "Entertainment"}
RATE_METRICS = ("eng", "likes")          # rates rank only channels big enough for them to mean something
RATE_MIN_SUBS = int(os.getenv("RATE_MIN_SUBS", "10000"))
METRICS = ("size", "views", "vday", "v7", "growth", "live", "eng", "likes", "medv")
# Any metric over any period: <base>_<period>. Bases: views (YouTube views gained; "all" = lifetime total), subs
# (subscribers / followers gained; "all" = current count), live (hours watched live, recorded by this site), and from
# the channel's posts in the period (deep.period_metrics): eng, likes, medv. Gains can only start at the channel's
# first daily reading: a period longer than that history shows the change since then (top() reports "history_from").
PERIODS = ("24h", "3d", "7d", "30d", "3m", "6m", "ytd", "1y", "all")
PERIOD_DAYS = {"24h": 1, "3d": 3, "7d": 7, "30d": 30, "3m": 90, "6m": 180, "1y": 365}
BASES = ("views", "subs", "live", "eng", "likes", "medv")
PMETRICS = tuple(f"{b}_{p}" for b in BASES for p in PERIODS)
GAIN_BASES = ("views", "subs")


def period_start(p: str):
    today = datetime.now(events.REPORT_TZ).date()
    if p == "ytd":
        return today.replace(month=1, day=1)
    if p == "all":
        return None
    return today - timedelta(days=PERIOD_DAYS[p])


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
        starts = {p: period_start(p).strftime("%Y-%m-%d") for p in PERIODS if p not in ("24h", "all")}
        firsts = {p: first_since(d) for p, d in starts.items() if p not in ("7d", "30d")}
        firsts["7d"], firsts["30d"] = old7, old
        pcols = [p for p in PERIODS if p != "all"]
        sums = ", ".join(f"SUM(CASE WHEN day>=? THEN hw END)" for _ in pcols)
        hwp = {r[0]: dict(zip(pcols + ["all"], r[1:])) for r in c.execute(
            f"SELECT sid, {sums}, SUM(hw) FROM sc_daily GROUP BY sid",
            [(period_start(p) if p != "24h" else today - timedelta(days=1)).strftime("%Y-%m-%d") for p in pcols])}
        first_day = c.execute("SELECT MIN(day) FROM sc_chstats").fetchone()[0]
        top_game = {}
        for sid, g, h in c.execute("SELECT sid, game, SUM(hw) FROM sc_daily WHERE day>=? GROUP BY sid, game", (d30,)):
            if h and (sid not in top_game or h > top_game[sid][1]):
                top_game[sid] = (g, h)
        chans = {r["sid"]: dict(r) for r in c.execute(
            "SELECT sid, platform, name, logo, url, country, COALESCE(india,0) india, game, topic, ytcat FROM sc_channels")}
    day1 = ytextra._latest_gains()
    per = {}                                          # (sid, period) -> (eng, likes, medv) from deep.period_metrics
    try:
        from tracker import deep
        with store._lock:
            for sid, pp, e, lk, mv in deep._db().execute("SELECT sid, period, eng_rate, like_rate, med_views FROM ch_period"):
                per[(sid, pp)] = (e, lk, mv)
    except Exception as ex:
        print(f"Ranks periods: {str(ex)[:80]}")
    eng = {}                                          # this site's medians from the channel's recent posts (deep.py)
    try:
        from tracker import deep
        with store._lock:
            for sid, fmt, e, lk, mv, n in deep._db().execute(
                    "SELECT sid, fmt, eng_rate, like_rate, med_views, n FROM ch_metrics WHERE fmt IN ('long','short')"):
                if sid not in eng or (fmt == "long" and n >= 5):
                    eng[sid] = (e, lk, mv)
    except Exception as ex:
        print(f"Ranks engagement: {str(ex)[:80]}")
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
        g = "" if g == "Other" else g                 # "Other" is not a game: no rank for it
        sec = scene.section_of(g) if g else ""
        if ch["platform"] == "youtube":          # YouTube's own categories only (until known: nearest one to what they stream)
            cat = next((x for x in (ch["ytcat"], ch["topic"]) if x and x != "Other"), "") or _YT_FROM_SEC.get(sec, "")
        else:
            cat = scene.SECTION_NAMES.get(sec, "") if sec != "other" else ""
        pm = {}
        for p in PERIODS:
            A = firsts.get(p, {}).get(sid) if p not in ("24h", "all") else None

            def dg(i, A=A):
                if not (L and A) or L[i] is None or A[i] is None:
                    return None
                d = L[i] - A[i]
                return d if abs(d) <= .25 * max(L[i], 1000) or i == 1 and d >= 0 else None
            if p == "24h":
                pm["views_24h"], pm["subs_24h"] = (g1[0], g1[1]) if g1 else (None, None)
            elif p == "all":
                pm["views_all"], pm["subs_all"] = (L[1], L[0]) if L else (None, None)
            else:
                pm["views_" + p], pm["subs_" + p] = dg(1), dg(0)
            if ch["platform"] != "youtube":
                pm["views_" + p] = None
            h = (hwp.get(sid) or {}).get(p)
            pm["live_" + p] = round(h) if h else None
            e = per.get((sid, p))
            pm["eng_" + p], pm["likes_" + p], pm["medv_" + p] = e if e else (None, None, None)
        rows.append({**pm, "sid": sid, "platform": ch["platform"], "name": ch["name"], "logo": ch["logo"], "url": ch["url"],
                     "country": ct[0] if ct else "", "country_name": ct[2] if ct else "", "category": cat or "", "game": g,
                     "size": size, "views": views, "vday": vday, "v7": v7, "growth": growth, "live": round(live),
                     "eng": (eng.get(sid) or (None,))[0], "likes": (eng.get(sid) or (None, None))[1],
                     "medv": (eng.get(sid) or (None, None, None))[2]})
    _R["first_day"] = first_day
    return rows


def compute():
    rows = _rows()
    rank, tot = {}, {}
    for m in METRICS:
        for scope in ("world", "country", "category", "game"):
            groups = {}
            for r in rows:
                if r[m] is None or (m in ("live", "views") and not r[m]) or (m in ("growth", "vday", "v7") and r[m] <= 0) \
                        or (m in RATE_METRICS and (r["size"] or 0) < RATE_MIN_SUBS):
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
        _R.update(at=time.time(), rank=rank, tot=tot, rows={r["sid"]: r for r in rows}, first_day=_R.get("first_day"))
    try:                                   # kept on disk so a restart (every update) serves rankings instantly
        tmp = CACHE + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(dict(_R), f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, CACHE)
    except Exception as e:
        print(f"Ranks cache: {str(e)[:100]}")
    return len(rows)


CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ranks_cache.pkl")


def load_cache() -> bool:
    try:
        with open(CACHE, "rb") as f:
            d = pickle.load(f)
        if time.time() - d.get("at", 0) < 2 * 86400:
            with _lock:
                _R.update(d)
            return True
    except Exception:
        pass
    return False


def run_forever():
    load_cache()
    time.sleep(5 if _R["at"] else 20)
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


def _keep(r, metric):
    v = r.get(metric)
    if v is None:
        return False
    base = metric.split("_")[0] if "_" in metric else metric
    if metric in ("growth", "vday", "v7") or (base in GAIN_BASES and "_" in metric and not metric.endswith("_all")):
        return v > 0
    if metric in ("live", "views") or base == "live" or metric in ("views_all", "subs_all"):
        return bool(v)
    if metric in RATE_METRICS or base in ("eng", "likes"):
        return (r["size"] or 0) >= RATE_MIN_SUBS
    return True


def top(platform: str = "youtube", metric: str = "size", country: str = "", category: str = "", limit: int = 100, game: str = "") -> dict:
    from tracker import scene
    with _lock:
        rows = [r for r in _R["rows"].values() if r["platform"] == platform and _keep(r, metric)
                and (not country or r["country"] == country) and (not category or r["category"] == category)
                and (not game or r["game"] == game)]
        cats = sorted({r["category"] for r in _R["rows"].values() if r["platform"] == platform and r["category"]}, key=str.lower)
        ctrs = sorted({(r["country"], r["country_name"]) for r in _R["rows"].values() if r["platform"] == platform and r["country"]},
                      key=lambda x: x[1])
        at = _R["at"]
    rows.sort(key=lambda r: -r[metric])
    # games: real games only (not News, Music, Devotional, Cricket ...), and only those of the chosen category
    with _lock:
        pool = [r["game"] for r in _R["rows"].values() if r["platform"] == platform and r["game"]
                and (not category or r["category"] == category) and (not country or r["country"] == country)]
    games = sorted({g for g in pool if scene.section_of(g) in ("gaming", "esports")}, key=str.lower)
    if category and category != "Gaming" and platform == "youtube":
        games = []
    return {"platform": platform, "metric": metric, "total": len(rows), "updated": at, "games": games,
            "history_from": _R.get("first_day"),
            "rows": [{**r, "rank": i + 1} for i, r in enumerate(rows[:limit])],
            "categories": cats, "countries": [{"code": a, "name": b} for a, b in ctrs]}
