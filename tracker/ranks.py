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
BASES = ("views", "subs", "live", "peak", "avg", "eng", "likes", "medv")
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
    with store.reading():
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
        sums = ", ".join(f"SUM(CASE WHEN day>=? THEN hw END), MAX(CASE WHEN day>=? THEN peak END), SUM(CASE WHEN day>=? THEN mins END)"
                         for _ in pcols)
        pstarts = [(period_start(p) if p != "24h" else today - timedelta(days=1)).strftime("%Y-%m-%d") for p in pcols]
        hwp, pkp, avp = {}, {}, {}           # per period: hours watched, peak live viewers, average live viewers
        for r in c.execute(f"SELECT sid, {sums}, SUM(hw), MAX(peak), SUM(mins) FROM sc_daily GROUP BY sid",
                           [d for d in pstarts for _ in range(3)]):
            v = list(r[1:])
            for i, p in enumerate(pcols + ["all"]):
                h, pk, mn = v[3 * i], v[3 * i + 1], v[3 * i + 2]
                hwp.setdefault(r[0], {})[p] = h
                pkp.setdefault(r[0], {})[p] = pk
                avp.setdefault(r[0], {})[p] = round(h * 60 / mn) if h and mn else None
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
        with store.reading():
            for sid, pp, e, lk, mv in deep._db().execute("SELECT sid, period, eng_rate, like_rate, med_views FROM ch_period"):
                per[(sid, pp)] = (e, lk, mv)
    except Exception as ex:
        print(f"Ranks periods: {str(ex)[:80]}")
    eng = {}                                          # this site's medians from the channel's recent posts (deep.py)
    try:
        from tracker import deep
        with store.reading():
            for sid, fmt, e, lk, mv, n in deep._db().execute(
                    "SELECT sid, fmt, eng_rate, like_rate, med_views, n FROM ch_metrics WHERE fmt IN ('long','short')"):
                if sid not in eng or (fmt == "long" and n >= 5):
                    eng[sid] = (e, lk, mv)
    except Exception as ex:
        print(f"Ranks engagement: {str(ex)[:80]}")
    vod = {}                                 # Kick / Twitch: total views of past broadcasts per period (their VOD lists)
    try:
        with store.reading():
            c = ytextra._db()
            for p in PERIODS:
                d0 = period_start(p)
                t0 = 0 if p == "all" else time.time() - 86400 if p == "24h" else \
                    datetime(d0.year, d0.month, d0.day, tzinfo=events.REPORT_TZ).timestamp()
                for sid, v in c.execute("""SELECT v.sid, SUM(v.views) FROM yt_videos v JOIN sc_channels c ON c.sid=v.sid
                                           WHERE c.platform IN ('kick','twitch') AND v.ts>=? AND v.views IS NOT NULL
                                           GROUP BY v.sid""", (t0,)):
                    vod.setdefault(sid, {})[p] = v
    except Exception as ex:
        print(f"Ranks VOD views: {str(ex)[:80]}")
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
            want = _YT_FROM_SEC.get(sec, "") if live else ""
            if want and cat == "Gaming" and want != "Gaming":
                cat = want            # what they actually stream wins: a cricket channel tagged Gaming is Sports
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
            if ch["platform"] != "youtube":          # Kick / Twitch: views of the past broadcasts streamed in the period
                pm["views_" + p] = (vod.get(sid) or {}).get(p)
            h = (hwp.get(sid) or {}).get(p)
            pm["live_" + p] = round(h) if h else None
            pm["peak_" + p] = (pkp.get(sid) or {}).get(p) or None
            pm["avg_" + p] = (avp.get(sid) or {}).get(p) or None
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
    if metric in ("live", "views") or base in ("live", "peak", "avg") or metric in ("views_all", "subs_all"):
        return bool(v)
    if metric in RATE_METRICS or base in ("eng", "likes"):
        return (r["size"] or 0) >= RATE_MIN_SUBS
    return True


def _now_live(sid: str) -> int:
    """Watching this channel live right now (0 if not live), from the site-wide scan."""
    try:
        from tracker import scene
        x = scene._LIVE.get(sid)
        return int(x["viewers"]) if x else 0
    except Exception:
        return 0


_GS = {"at": 0, "games": []}


def _games_streamed() -> list:
    """Every game streamed in the last 30 days (for the game list), 10-minute cache."""
    if time.time() - _GS["at"] > 600:
        from tracker import scene
        d0 = (datetime.now(events.REPORT_TZ).date() - timedelta(days=30)).strftime("%Y-%m-%d")
        with store.reading():
            _GS.update(at=time.time(), games=[r[0] for r in scene._db().execute(
                "SELECT DISTINCT game FROM sc_daily WHERE day>=? AND game NOT IN ('','Other')", (d0,))])
    return _GS["games"]


_GL = {}      # game -> (ts, {sid: {metric: value}}) live numbers while streaming that game, 10-minute cache


def game_live(game: str) -> dict:
    """Peak / hours watched / average viewers of every channel WHILE STREAMING `game`, per period, from sc_daily's
    rows of that game only (its index): one stream of the game is enough to be counted (owner, 18 Nov 2026)."""
    hit = _GL.get(game)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    from tracker import scene
    today = datetime.now(events.REPORT_TZ).date()
    pcols = [p for p in PERIODS if p != "all"]
    starts = [(period_start(p) if p != "24h" else today - timedelta(days=1)).strftime("%Y-%m-%d") for p in pcols]
    sums = ", ".join("SUM(CASE WHEN day>=? THEN hw END), MAX(CASE WHEN day>=? THEN peak END), SUM(CASE WHEN day>=? THEN mins END)"
                     for _ in pcols)
    out = {}
    with store.reading():
        for r in scene._db().execute(f"SELECT sid, {sums}, SUM(hw), MAX(peak), SUM(mins) FROM sc_daily WHERE game=? GROUP BY sid",
                                     [d for d in starts for _ in range(3)] + [game]):
            v, d = list(r[1:]), {}
            for i, p in enumerate(pcols + ["all"]):
                h, pk, mn = v[3 * i], v[3 * i + 1], v[3 * i + 2]
                if h or pk:
                    d["live_" + p] = round(h) if h else None
                    d["peak_" + p] = pk or None
                    d["avg_" + p] = round(h * 60 / mn) if h and mn else None
            if d:
                out[r[0]] = d
    _GL[game] = (time.time(), out)
    return out


def top(platform: str = "youtube", metric: str = "size", country: str = "", category: str = "", limit: int = 100, game: str = "") -> dict:
    from tracker import scene
    by_game = bool(game) and metric.split("_")[0] in ("peak", "avg", "live")
    gl = game_live(game) if game else {}
    with _lock:
        if by_game:                           # live metrics with a game: what each channel did while streaming it
            rows = []
            for r in _R["rows"].values():
                gv = gl.get(r["sid"]) or {}
                if (platform == "all" or r["platform"] == platform) and gv.get(metric) and (not country or r["country"] == country) \
                        and (not category or r["category"] == category):
                    rows.append({**r, **gv})
        else:
            rows = [r for r in _R["rows"].values() if (platform == "all" or r["platform"] == platform) and _keep(r, metric)
                    and (not country or r["country"] == country) and (not category or r["category"] == category)
                    and (not game or r["game"] == game or r["sid"] in gl)]
            if game:                          # one stream of the game is enough to be in its list (owner, 18 Nov)
                rows = [{**r, "game": game} for r in rows]
        cats = [] if platform == "all" else \
            sorted({r["category"] for r in _R["rows"].values() if r["platform"] == platform and r["category"]}, key=str.lower)
        ctrs = sorted({(r["country"], r["country_name"]) for r in _R["rows"].values() if (platform == "all" or r["platform"] == platform) and r["country"]},
                      key=lambda x: x[1])
        at = _R["at"]
    rows = [r for r in rows if not scene.name_blocked(r.get("name"))]
    rows.sort(key=lambda r: -r[metric])
    if country and rows:                      # each channel's place worldwide in the same list (India cards show it)
        try:
            w = top(platform, metric, "", category, limit=100000, game=game)["rows"]
            wr = {r["sid"]: r["rank"] for r in w}
            rows = [{**r, "world_rank": wr.get(r["sid"])} for r in rows]
        except Exception as e:
            print(f"World ranks: {str(e)[:80]}")
    # games: real games only (not News, Music, Devotional, Cricket ...), and only those of the chosen category
    with _lock:
        pool = [r["game"] for r in _R["rows"].values() if (platform == "all" or r["platform"] == platform) and r["game"] and scene.shown(r["game"])
                and (not category or r["category"] == category) and (not country or r["country"] == country)]
    pool += [g for g in _games_streamed() if scene.shown(g)]
    games = sorted({g for g in pool if scene.section_of(g) in ("gaming", "esports")}, key=str.lower)
    if category and category != "Gaming" and platform == "youtube":
        games = []
    return {"platform": platform, "metric": metric, "total": len(rows), "updated": at, "games": games,
            "history_from": _R.get("first_day"),
            "rows": [{**r, "game": game or r["game"], "rank": i + 1, "now": _now_live(r["sid"])} for i, r in enumerate(rows[:limit])],
            "categories": cats, "countries": [{"code": a, "name": b} for a, b in ctrs]}
