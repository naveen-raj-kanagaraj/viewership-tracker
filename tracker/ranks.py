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

from tracker import overrides, events, store

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


def _viewbot(followers: int, peak, avg) -> bool:
    """Live viewers that a channel's followers can't explain: a peak above its follower count, or an average above a
    quarter of it. Real channels average about 1-5% of their followers (24 Nov, checked on twitch.tv: Rachitroo_1 121K
    followers / 2,476 avg; pepewwwpew 124 followers / 454 avg). Tiny streams (avg < 30, peak < 50) are left alone."""
    return bool((peak or 0) >= 50 and peak > followers) or bool((avg or 0) >= 30 and avg > 0.25 * followers)


def _tuples(c, sql, args=()):
    """Plain tuples (not sqlite3.Row objects) for reads of millions of rows: about twice as fast to go through."""
    cur = c.cursor()
    cur.row_factory = None
    return cur.execute(sql, args)


def _rows():
    from tracker import scene, ytextra
    today = datetime.now(events.REPORT_TZ).date()
    d30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    with store.reading():
        c = scene._db()
        ytextra._db()
        # One straight read of sc_chstats: each channel's latest reading and its first reading since each period start.
        # (Seven GROUP BY queries each walked the whole (sid, day) index: 2+ minutes apiece on 23 Nov.)
        starts = {p: period_start(p).strftime("%Y-%m-%d") for p in PERIODS if p not in ("24h", "all")}
        d7 = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        keys = sorted(set(starts.values()) | {d30, d7})
        lo = keys[0]
        latest, firstd = {}, {k: {} for k in keys}
        for sid, day, subs, views in _tuples(c, "SELECT sid, day, subs, views FROM sc_chstats NOT INDEXED"):
            L = latest.get(sid)
            if L is None or day > L[2]:
                latest[sid] = (subs, views, day)
            if day < lo:
                continue
            for k in keys:
                if day >= k:
                    f = firstd[k].get(sid)
                    if f is None or day < f[2]:
                        firstd[k][sid] = (subs, views, day)
        latest = {sid: (v[0], v[1]) for sid, v in latest.items()}
        old, old7 = firstd[d30], firstd[d7]
        firsts = {p: firstd[d] for p, d in starts.items()}
        pcols = [p for p in PERIODS if p != "all"]
        pstarts = [(period_start(p) if p != "24h" else today - timedelta(days=1)).strftime("%Y-%m-%d") for p in pcols]
        # One straight read of sc_daily (rows that reached 10 viewers; the rest can't rank), summed here. Three GROUP BY
        # queries walked the (sid, day) index row by row through millions of 1-viewer rows: 22 Nov the rankings job sat
        # on the first one for 20+ minutes on every run and the rankings stayed 57 hours old.
        hw, top_game, acc = {}, {}, {}
        tg = {}
        for sid, day, game, h, pk, mn in _tuples(c, "SELECT sid, day, game, hw, peak, mins FROM sc_daily WHERE peak >= 10"):
            # A peak only counts from a real stream: 10+ minutes live, and not 8x+ the day's own average (24 Nov:
            # sazof36 '17,184' on a day it averaged 1,924; biggbosstelugulives one 6-minute reading). A long stream
            # with a short big final can reach 5-6x its average, so the line is 8x.
            if (mn is not None and mn < 10) or (h and mn and mn >= 30 and pk > 8 * h * 60 / mn):
                pk = None
            a = acc.get(sid)
            if a is None:
                a = acc[sid] = [[None, None, None] for _ in range(len(pcols) + 1)]
            for i in range(len(pcols) + 1):
                if i < len(pcols) and day < pstarts[i]:
                    continue
                x = a[i]
                if h is not None:
                    x[0] = (x[0] or 0) + h
                if pk is not None and (x[1] is None or pk > x[1]):
                    x[1] = pk
                if mn is not None:
                    x[2] = (x[2] or 0) + mn
            if day >= d30 and h:
                hw[sid] = hw.get(sid, 0) + h
                tg[(sid, game)] = tg.get((sid, game), 0) + h
        hwp, pkp, avp = {}, {}, {}           # per period: hours watched, peak live viewers, average live viewers
        for sid, a in acc.items():
            for i, p in enumerate(pcols + ["all"]):
                h, pk, mn = a[i]
                hwp.setdefault(sid, {})[p] = h
                pkp.setdefault(sid, {})[p] = pk
                avp.setdefault(sid, {})[p] = round(h * 60 / mn) if h and mn else None
        for (sid, g), h in tg.items():
            if sid not in top_game or h > top_game[sid][1]:
                top_game[sid] = (g, h)
        first_day = c.execute("SELECT MIN(day) FROM sc_chstats").fetchone()[0]
        bad = set()
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='ch_profile'").fetchone():
            cols = [r[1] for r in c.execute("PRAGMA table_info(ch_profile)")]
            if "followers" in cols:
                for sid, f, gone in _tuples(c, "SELECT sid, followers, COALESCE(gone,0) FROM ch_profile"):
                    if gone:
                        bad.add(sid)          # Twitch no longer has it: banned or deleted
                    elif f is not None and _viewbot(f, (pkp.get(sid) or {}).get("30d"), (avp.get(sid) or {}).get("30d")):
                        bad.add(sid)
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
        top = (pkp.get(sid) or {}).get("all") or 0
        if sid in bad or overrides.blocked(sid):
            continue                          # banned / deleted, viewbots, or blocked by the daily review
        if ch["platform"] == "youtube" and size and _viewbot(size, (pkp.get(sid) or {}).get("30d"), (avp.get(sid) or {}).get("30d")):
            continue                          # YouTube viewbots: more watching than subscribers can explain (25 Nov)
        if top < 10:                          # never streamed live to 10+ viewers on our records: not ranked. The
                                              # rankings are of streamers only (owner, 23 Nov: Short Malouniya, an
                                              # uploader with no live streams, was #2 in India's YouTube Gaming).
            continue                          # (22 Nov: the GTA 6 sweep added every 1-viewer channel; ranking them all
                                              # took hours per metric, and the rankings stopped updating for 2 days)
        ct = scene.country_of(ch["country"]) or (scene.country_of("IN") if ch["india"] else None)
        g = (top_game.get(sid) or (ch["game"], 0))[0] or ""
        g = "" if g == "Other" else g                 # "Other" is not a game: no rank for it
        sec = scene.section_of(g) if g else ""
        if ch["platform"] == "youtube":          # YouTube's own categories only (until known: nearest one to what they stream)
            cat = next((x for x in (ch["ytcat"], ch["topic"]) if x and x != "Other"), "") or _YT_FROM_SEC.get(sec, "")
            want = _YT_FROM_SEC.get(sec, "") if live else ""
            if want:
                cat = want            # what they actually stream wins, both ways: a cricket channel tagged Gaming is
                                      # Sports, and CarryisLive (YouTube category Entertainment, streams GTA 6 / PUBG)
                                      # is Gaming (owner, 23 Nov)
        else:
            cat = scene.SECTION_NAMES.get(sec, "") if sec != "other" else ""
        pm = {}
        for p in PERIODS:
            A = firsts.get(p, {}).get(sid) if p not in ("24h", "all") else None

            def dg(i, A=A):
                if not (L and A) or L[i] is None or A[i] is None:
                    return None
                d = L[i] - A[i]
                if i == 1:                   # views gained: needs a real starting count, and a channel can't gain more
                    return d if A[1] > 0 and 0 <= d <= .6 * L[1] else None   # than ~60% of its lifetime views in the
                return d if abs(d) <= .25 * max(L[i], 1000) else None        # period (22 Nov: new channels showed total
                                                                              # views as "views gained", e.g. +368M of 368M)
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
                     "country": ct[0] if ct else "", "country_name": ct[2] if ct else "", "category": overrides.category(sid) or cat or "", "game": g,
                     "size": size, "views": views, "vday": vday, "v7": v7, "growth": growth, "live": round(live),
                     "eng": (eng.get(sid) or (None,))[0], "likes": (eng.get(sid) or (None, None))[1],
                     "medv": (eng.get(sid) or (None, None, None))[2]})
    _R["first_day"] = first_day
    return rows


STATUS = {}


# On the server the job runs in its own Python process (track.py sets this): inside the tracker it shared one CPU core
# (Python's GIL) with ~100 other threads, and on 23 Nov one read of channel stats took 12+ minutes there.
SEPARATE = False


def _child():
    """Entry point of the separate process: read-only work, then the result goes to the cache file."""
    from tracker import scene, ytextra, deep
    scene._SCHEMA_OK[store.DB_PATH] = True     # the tracker made the tables; the child never writes the database
    ytextra._ready = deep._ready = True
    before = os.path.getmtime(CACHE) if os.path.exists(CACHE) else 0
    n = _compute()
    if not os.path.exists(CACHE) or os.path.getmtime(CACHE) == before:
        raise SystemExit("rankings cache was not written")
    print(f"Ranks: {n} channels ranked (separate process)", flush=True)


def _compute_separate():
    import subprocess, sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-c", "from tracker import ranks; ranks._child()"], cwd=root,
                       timeout=4 * 3600, capture_output=True, text=True)
    for line in (r.stdout or "").splitlines()[-5:]:
        print(line)
    if r.returncode != 0:
        raise RuntimeError(f"rankings process failed: {(r.stderr or '').strip().splitlines()[-1:] or r.returncode}")
    if not load_cache():
        raise RuntimeError("rankings cache unreadable")
    return len(_R["rows"])


def compute():
    STATUS.update(started=time.time(), error=None)
    t0 = time.time()
    try:
        with store.protected():
            n = _compute_separate() if SEPARATE else _compute()
        STATUS.update(done=time.time(), took=round(time.time() - t0), rows=n)
        return n
    except Exception as e:
        STATUS.update(error=str(e)[:200], failed=time.time())
        raise


def _compute():
    rows = _rows()
    _clean({i: r for i, r in enumerate(rows)})
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


def _clean(rows: dict) -> int:
    """Views gained can't be (nearly) the channel's lifetime views: that means the period's first reading was missing
    and the whole total was counted (22 Nov: Rajat khiladi +2.29B of 2.29B, MinevidZ +368M of 368M in 7 days).
    Cleans rankings saved by older code, so they are right the moment they load."""
    n = 0
    for r in rows.values():
        tot = r.get("views_all") or r.get("views") or 0
        for k in [k for k in r if k.startswith("views_") and k != "views_all"]:
            v = r.get(k)
            if v and r.get("platform") == "youtube" and (not tot or v > .6 * tot):
                r[k] = None
                n += 1
    return n


def load_cache() -> bool:
    try:
        with open(CACHE, "rb") as f:
            d = pickle.load(f)
        n = _clean(d.get("rows") or {})
        if n:
            print(f"Ranks cache: {n} impossible views-gained values removed")
        with _lock:                          # any age: last known rankings beat an empty page while they're recomputed
            _R.update(d)
        return True
    except Exception:
        pass
    return False


EVERY = 1800                              # seconds between runs
DAILY_AT = (0, 5)                         # and always a run at 00:05 India time, when the day's numbers roll over (owner, 23 Nov)


def _next_wait(now: float) -> float:
    """Seconds to the next run: EVERY from now, or 00:05 India time if that comes first."""
    t = datetime.fromtimestamp(now, events.REPORT_TZ)
    at = t.replace(hour=DAILY_AT[0], minute=DAILY_AT[1], second=0, microsecond=0)
    if at <= t:
        at += timedelta(days=1)
    return max(1.0, min(EVERY, at.timestamp() - now))


def run_forever():
    load_cache()
    time.sleep(5 if _R["at"] else 20)
    while True:
        try:
            compute()
        except Exception as e:
            print(f"Ranks: {str(e)[:150]}")
        time.sleep(_next_wait(time.time()))


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


GAME_SHARE = .25


def plays(sid: str, game: str, gv: dict = None, r: dict = None, period: str = "") -> bool:
    """Is `game` really what this channel streams? Its main game over 30 days, or a quarter or more of its hours
    watched over the last 7 or 30 days (owner, 25 Nov: channels that stream Free Fire / BGMI showed in GTA lists after
    one GTA stream; this replaces 18 Nov's 'one stream is enough')."""
    if r is None:
        r = _R["rows"].get(sid)
    if not r:
        return False
    if r.get("game") == game:
        return True
    if gv is None:
        gv = game_live(game).get(sid) or {}
    for p in dict.fromkeys([period, "7d", "30d"] if period else ["7d", "30d"]):     # the list's own period too
        tot, part = r.get("live_" + p), gv.get("live_" + p)
        if tot and part and part >= GAME_SHARE * tot:
            return True
    return False


def game_live(game: str) -> dict:
    """Peak / hours watched / average viewers of every channel WHILE STREAMING `game`, per period, from sc_daily's
    rows of that game only (its index): one stream of the game is enough to be counted (owner, 18 Nov 2026)."""
    hit = _GL.get(game)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    if hit:                                   # expired: answer with the last one, refresh once in the background
        if not _GLB.get(game):
            _GLB[game] = True
            threading.Thread(target=_gl_refresh, args=(game,), daemon=True).start()
        return hit[1]
    with _GLL.setdefault(game, threading.Lock()):  # first build: one thread builds, the others wait for it
        hit = _GL.get(game)
        if hit:
            return hit[1]
        return _gl_build(game)


_GLB, _GLL = {}, {}


def _gl_refresh(game):
    try:
        _gl_build(game)
    finally:
        _GLB[game] = False


def _gl_build(game: str) -> dict:
    from tracker import scene
    today = datetime.now(events.REPORT_TZ).date()
    pcols = [p for p in PERIODS if p != "all"]
    starts = [(period_start(p) if p != "24h" else today - timedelta(days=1)).strftime("%Y-%m-%d") for p in pcols]
    ok = "COALESCE(mins,0)>=10 AND NOT (mins>=30 AND hw>0 AND peak > 8*hw*60/mins)"     # the rankings' peak rule
    sums = ", ".join(f"SUM(CASE WHEN day>=? THEN hw END), MAX(CASE WHEN day>=? AND {ok} THEN peak END), SUM(CASE WHEN day>=? THEN mins END)"
                     for _ in pcols)
    out = {}
    with store.reading():
        for r in scene._db().execute(f"SELECT sid, {sums}, SUM(hw), MAX(CASE WHEN {ok} THEN peak END), SUM(mins) FROM sc_daily WHERE game=? GROUP BY sid",
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


def _world50(platform, metric, category, game, gl, by_game) -> dict:
    """sid -> rank for the top 50 worldwide of the same list. Only the top values are sorted (heapq), not 100k rows
    (19 Nov: building the whole world list for every India request made cold loads hang)."""
    import heapq
    from tracker import scene
    cand = []
    with _lock:
        for r in _R["rows"].values():
            if not (platform == "all" or r["platform"] == platform) or (category and r["category"] != category):
                continue
            if by_game:
                gv = gl.get(r["sid"]) or {}
                v = gv.get(metric) if gv and plays(r["sid"], game, gv, r) else None
            else:
                if not _keep(r, metric) or (game and not (r["game"] == game or (r["sid"] in gl and plays(r["sid"], game, gl[r["sid"]], r)))):
                    continue
                v = r.get(metric)
            if v:
                cand.append((v, r["sid"], r.get("name")))
    out = []
    for v, sid, name in heapq.nlargest(80, cand):
        if not scene.name_blocked(name) and not scene.not_in_game(name, game, sid):
            out.append({"sid": sid, "name": name, "platform": sid.split(":", 1)[0].replace("yt", "youtube"), metric: v})
    if platform == "all":                     # the same creator once, as in the list itself
        from tracker import ytextra
        out = ytextra.one_per_creator(out, metric)
    return {x["sid"]: i + 1 for i, x in enumerate(out[:50])}


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
                        and (not category or r["category"] == category) and plays(r["sid"], game, gv, r, metric.partition("_")[2]):
                    rows.append({**r, **gv})
        else:
            rows = [r for r in _R["rows"].values() if (platform == "all" or r["platform"] == platform) and _keep(r, metric)
                    and (not country or r["country"] == country) and (not category or r["category"] == category)
                    and (not game or r["game"] == game or (r["sid"] in gl and plays(r["sid"], game, gl[r["sid"]], r)))]
            if game:                          # one stream of the game is enough to be in its list (owner, 18 Nov)
                rows = [{**r, "game": game} for r in rows]
        cats = [] if platform == "all" else \
            sorted({r["category"] for r in _R["rows"].values() if r["platform"] == platform and r["category"]}, key=str.lower)
        ctrs = sorted({(r["country"], r["country_name"]) for r in _R["rows"].values() if (platform == "all" or r["platform"] == platform) and r["country"]},
                      key=lambda x: x[1])
        at = _R["at"]
    rows = [r for r in rows if not scene.name_blocked(r.get("name")) and not scene.not_in_game(r.get("name"), game, r.get("sid", ""))]
    rows.sort(key=lambda r: -r[metric])
    if platform == "all":                     # the same creator on YouTube and Kick: once, with the other as 'also'
        from tracker import ytextra
        rows = ytextra.one_per_creator(rows, metric)
    if country and rows:                      # each channel's place worldwide in the same list (India cards show it)
        try:
            wr = _world50(platform, metric, category, game, gl, by_game)
            rows = [{**r, "world_rank": wr.get(r["sid"]) if (wr.get(r["sid"]) or 99) <= 50 else None} for r in rows]   # top 50 worldwide only
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
