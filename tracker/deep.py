"""Deep data for the channels that matter: the ranked set (top 1,000 per YouTube category and per game / topic,
worldwide and in India, plus the top 1,000 overall and everyone live).

  refresh_once()   subscribers and total views: top 1,000 overall (world and India) and live channels every hour,
                   the rest of the ranked set every 3 hours (YouTube Data API, 1 unit per 50 channels). Readings go to
                   sc_intra (kept INTRA_DAYS) and today's sc_chstats row.
  backfill_once()  every video, Short and past live stream since BACKFILL_FROM (default 1 Jan 2026) for ranked
                   channels, biggest first (API about 1 unit per 50 videos; free channel pages when the allowance is
                   spent, with approximate dates). Monthly history on channel pages comes from these.
  metrics_once()   per channel and format (long videos, Shorts, live): medians of views, like rate, comment rate and
                   engagement over the last 30 posts aged 3 to 90 days, uploads per week; then benchmarks: 25th, 50th,
                   75th and 90th percentiles per category / game, size band and scope (world / India).
  comments_once()  YouTube's top comments on new videos of ranked channels (commentThreads, order=relevance,
                   1 unit each), kept 30 days (YouTube's rule for text).

These are this site's own calculations from YouTube's public numbers; pages label them as such.
"""
import os
import statistics
import time
from datetime import datetime

from tracker import events, store, ytextra

BACKFILL_FROM = datetime.fromisoformat(os.getenv("BACKFILL_FROM", "2026-01-01")).timestamp()
TOP_N = int(os.getenv("DEEP_TOP_N", "1000"))
TIER_A_H, TIER_B_H = float(os.getenv("DEEP_TIER_A_H", "1")), float(os.getenv("DEEP_TIER_B_H", "3"))
COMMENTS_KEEP_DAYS = 30
SIZES = [(0, "under 10K"), (10_000, "10K-100K"), (100_000, "100K-1M"), (1_000_000, "1M-10M"), (10_000_000, "10M+")]
FORMATS = {"long": "COALESCE(short,0)=0 AND COALESCE(live,0)=0", "short": "COALESCE(short,0)=1", "live": "COALESCE(live,0)=1"}
_SET = {"at": 0, "a": [], "b": []}
_LAST = {}            # sid -> last refresh (memory; seeded from sc_intra on first use)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ch_metrics (sid TEXT, fmt TEXT, n INTEGER, med_views REAL, like_rate REAL, comment_rate REAL,
    eng_rate REAL, per_week REAL, views_per_sub REAL, updated INTEGER, PRIMARY KEY (sid, fmt));
CREATE TABLE IF NOT EXISTS ch_bench (scope TEXT, kind TEXT, grp TEXT, size TEXT, fmt TEXT, metric TEXT, n INTEGER,
    p25 REAL, p50 REAL, p75 REAL, p90 REAL, updated INTEGER, PRIMARY KEY (scope, kind, grp, size, fmt, metric));
CREATE TABLE IF NOT EXISTS yt_comments (vid TEXT, rank INTEGER, author TEXT, text TEXT, likes INTEGER, ts INTEGER,
    fetched INTEGER, PRIMARY KEY (vid, rank));
"""
_ready = False


def _db():
    global _ready
    c = ytextra._db()
    if not _ready:
        c.executescript(SCHEMA)
        c.commit()
        _ready = True
    return c


def size_band(subs) -> str:
    out = SIZES[0][1]
    for lo, name in SIZES:
        if (subs or 0) >= lo:
            out = name
    return out


# ---------- the ranked set ----------

def ranked_set(force: bool = False) -> tuple:
    """(tier A sids, tier B sids). A: top TOP_N by subscribers worldwide and in India, and YouTube channels live now.
    B: top TOP_N per YouTube category and per game / topic, worldwide and in India. Rebuilt hourly."""
    if not force and time.time() - _SET["at"] < 3600 and _SET["a"]:
        return _SET["a"], _SET["b"]
    since = ytextra._day(time.time() - 4 * 86400)
    with store._lock:
        rows = _db().execute(
            """SELECT c.sid, COALESCE(NULLIF(c.ytcat,''), c.topic) cat, c.game, COALESCE(c.india,0) india, s.subs
               FROM sc_channels c JOIN (SELECT sid, MAX(subs) subs FROM sc_chstats WHERE day>=? GROUP BY sid) s ON s.sid=c.sid
               WHERE c.platform='youtube' AND s.subs IS NOT NULL ORDER BY s.subs DESC""", (since,)).fetchall()
    a, b, groups = [], set(), {}
    a += [r[0] for r in rows[:TOP_N]] + [r[0] for r in rows if r[3]][:TOP_N]
    try:
        from tracker import scene
        a += [sid for sid, x in list(scene._LIVE.items()) if sid.startswith("yt:")]
    except Exception:
        pass
    for sid, cat, game, india, subs in rows:
        for key in ([("world", "cat", cat), ("world", "game", game)]
                    + ([("in", "cat", cat), ("in", "game", game)] if india else [])):
            if key[2] and key[2] != "Other":
                g = groups.setdefault(key, [])
                if len(g) < TOP_N:
                    g.append(sid)
                    b.add(sid)
    a = list(dict.fromkeys(a))
    sa = set(a)
    _SET.update(at=time.time(), a=a, b=[s for s in (r[0] for r in rows) if s in b and s not in sa])
    return _SET["a"], _SET["b"]


# ---------- refresh every 1-3 hours ----------

def refresh_once(max_channels: int = 4000) -> int:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key or not events.yt_quota_left(.85):
        return 0
    a, b = ranked_set()
    if not _LAST:
        with store._lock:
            _LAST.update(dict(_db().execute("SELECT sid, MAX(ts) FROM sc_intra WHERE ts>? GROUP BY sid",
                                            (time.time() - 86400,)).fetchall()))
    now = time.time()
    due = [s for s in a if now - _LAST.get(s, 0) >= TIER_A_H * 3600 - 300]
    due += [s for s in b if now - _LAST.get(s, 0) >= TIER_B_H * 3600 - 300]
    due = due[:max_channels]
    if not due:
        return 0
    got = ytextra._sane(ytextra.channel_stats([s[3:] for s in due]))
    ytextra.save_stats(got)
    for cid in got:
        _LAST["yt:" + cid] = now
    for s in due:                                  # not returned (deleted, hidden): don't ask again for a while
        _LAST.setdefault(s, now)
    return len(got)


# ---------- history since BACKFILL_FROM ----------

BACKFILL = {"done": 0, "last": 0}


def backfill_once(n_api: int = 30, n_free: int = 8) -> int:
    """Videos since BACKFILL_FROM for ranked channels that don't have them yet, biggest first."""
    a, b = ranked_set()
    key = os.getenv("YOUTUBE_API_KEY")
    api = api_n = free_n = 0
    for sid in a + b:
        if api_n >= n_api and free_n >= n_free:
            break
        m = store.kv_get(f"vids:{sid}") or {}
        if (m.get("since") or 9e12) <= BACKFILL_FROM + 86400 or m.get("full") or sid in ytextra._VBUSY \
                or time.time() - ytextra._VFAIL.get(sid, 0) < 6 * 3600:
            continue
        use_api = bool(key) and events.yt_quota_left(.7)
        if use_api and api_n < n_api:
            api_n += 1
        elif not use_api and free_n < n_free:
            free_n += 1
        else:
            continue
        ytextra._refresh_videos(sid, full=True, since_ts=BACKFILL_FROM)
        api += 1
    BACKFILL.update(done=BACKFILL["done"] + api, last=int(time.time()))
    return api


def backfill_progress() -> dict:
    a, b = ranked_set()
    allc = a + b
    have = sum(1 for s in allc if ((store.kv_get(f"vids:{s}") or {}).get("since") or 9e12) <= BACKFILL_FROM + 86400
               or (store.kv_get(f"vids:{s}") or {}).get("full"))
    return {"ranked": len(allc), "with_history": have}


# ---------- metrics and benchmarks ----------

def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def channel_metrics(sid: str, subs=None) -> dict:
    """{fmt: {...}} from the channel's stored posts: the last 30 aged 3 to 90 days (views settle after a few days;
    older posts are a different era of the channel)."""
    now = time.time()
    out = {}
    with store._lock:
        c = _db()
        for fmt, cond in FORMATS.items():
            rows = c.execute(f"""SELECT views, likes, comments, ts FROM yt_videos WHERE sid=? AND {cond}
                                 AND ts BETWEEN ? AND ? AND views>0 ORDER BY ts DESC LIMIT 30""",
                             (sid, now - 90 * 86400, now - 3 * 86400)).fetchall()
            per_week = c.execute(f"SELECT COUNT(*) FROM yt_videos WHERE sid=? AND {cond} AND ts>?",
                                 (sid, now - 90 * 86400)).fetchone()[0] / (90 / 7)
            if len(rows) < 3:
                continue
            mv = _med([r[0] for r in rows])
            out[fmt] = {"n": len(rows), "med_views": mv,
                        "like_rate": _med([r[1] / r[0] for r in rows if r[1] is not None]),
                        "comment_rate": _med([r[2] / r[0] for r in rows if r[2] is not None]),
                        "eng_rate": _med([((r[1] or 0) + (r[2] or 0)) / r[0] for r in rows if r[1] is not None]),
                        "per_week": round(per_week, 2), "views_per_sub": (mv / subs) if subs else None}
    return out


def metrics_once(limit: int = 20000) -> int:
    """Recompute ch_metrics for ranked channels with posts, then the benchmarks. Every 3 hours."""
    a, b = ranked_set()
    sids = (a + b)[:limit]
    since = ytextra._day(time.time() - 4 * 86400)
    with store._lock:
        subs = dict(_db().execute("SELECT sid, MAX(subs) FROM sc_chstats WHERE day>=? GROUP BY sid", (since,)).fetchall())
    now, rows = int(time.time()), []
    for sid in sids:
        for fmt, m in channel_metrics(sid, subs.get(sid)).items():
            rows.append((sid, fmt, m["n"], m["med_views"], m["like_rate"], m["comment_rate"], m["eng_rate"], m["per_week"],
                         m["views_per_sub"], now))
    with store._lock:
        c = _db()
        c.executemany("INSERT OR REPLACE INTO ch_metrics VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        c.commit()
    benchmarks()
    return len(rows)


BENCH_METRICS = ("eng_rate", "like_rate", "comment_rate", "med_views", "views_per_sub", "per_week")


def _pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def benchmarks() -> int:
    """Percentiles per (scope, kind, group, size band, format, metric), from channels with at least 3 posts."""
    since = ytextra._day(time.time() - 4 * 86400)
    with store._lock:
        c = _db()
        rows = c.execute(f"""SELECT m.*, COALESCE(NULLIF(ch.ytcat,''), ch.topic) cat, ch.game, COALESCE(ch.india,0) india, s.subs
                             FROM ch_metrics m JOIN sc_channels ch ON ch.sid=m.sid
                             LEFT JOIN (SELECT sid, MAX(subs) subs FROM sc_chstats WHERE day>=? GROUP BY sid) s ON s.sid=m.sid""",
                          (since,)).fetchall()
    buckets = {}
    for r in rows:
        band = size_band(r["subs"])
        keys = [("world", "all", "", band), ("world", "all", "", "")]
        for kind, g in (("cat", r["cat"]), ("game", r["game"])):
            if g and g != "Other":
                keys += [("world", kind, g, band), ("world", kind, g, "")]
        if r["india"]:
            keys += [("in",) + k[1:] for k in keys]
        for k in keys:
            for met in BENCH_METRICS:
                if r[met] is not None:
                    buckets.setdefault(k + (r["fmt"], met), []).append(r[met])
    now = int(time.time())
    out = [k + (len(v), _pct(v, .25), _pct(v, .5), _pct(v, .75), _pct(v, .9), now) for k, v in buckets.items() if len(v) >= 5]
    with store._lock:
        c = _db()
        c.execute("DELETE FROM ch_bench")
        c.executemany("INSERT INTO ch_bench VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", out)
        c.commit()
    return len(out)


def standing(sid: str) -> dict:
    """The channel's metrics per format with where it stands among peers (same category, game and size band,
    worldwide and in India), as a percentile: 90 = better than 90% of them."""
    since = ytextra._day(time.time() - 4 * 86400)
    with store._lock:
        c = _db()
        ch = c.execute("SELECT COALESCE(NULLIF(ytcat,''), topic) cat, game, COALESCE(india,0) india FROM sc_channels WHERE sid=?",
                       (sid,)).fetchone()
        subs = c.execute("SELECT MAX(subs) FROM sc_chstats WHERE sid=? AND day>=?", (sid, since)).fetchone()[0]
        mets = {r["fmt"]: dict(r) for r in c.execute("SELECT * FROM ch_metrics WHERE sid=?", (sid,))}
    if not ch or not mets:
        live = channel_metrics(sid, subs)
        mets = {f: {**m, "fmt": f} for f, m in live.items()}
    if not mets:
        return {}
    band = size_band(subs)
    peers = [("world", "cat", ch["cat"] if ch else ""), ("world", "game", ch["game"] if ch else "")]
    if ch and ch["india"]:
        peers += [("in", "cat", ch["cat"]), ("in", "game", ch["game"])]
    peers = [p for p in peers if p[2] and p[2] != "Other"] + [("world", "all", "")]
    out = {"size_band": band, "subs": subs, "formats": {}}
    with store._lock:
        c = _db()
        for fmt, m in mets.items():
            f = {k: m.get(k) for k in ("n", "med_views", "like_rate", "comment_rate", "eng_rate", "per_week", "views_per_sub")}
            f["peers"] = []
            for scope, kind, grp in peers:
                b = c.execute("""SELECT * FROM ch_bench WHERE scope=? AND kind=? AND grp=? AND size=? AND fmt=? AND metric='eng_rate'""",
                              (scope, kind, grp, band, fmt)).fetchone()
                if b and m.get("eng_rate") is not None:
                    f["peers"].append({"scope": scope, "kind": kind, "group": grp or "All channels", "size": band, "n": b["n"],
                                       "p25": b["p25"], "p50": b["p50"], "p75": b["p75"], "p90": b["p90"],
                                       "pct": _where(m["eng_rate"], b)})
            out["formats"][fmt] = f
    return out


def _where(x, b) -> int:
    """Approximate percentile of x from the stored quartiles."""
    pts = [(0, 0), (25, b["p25"]), (50, b["p50"]), (75, b["p75"]), (90, b["p90"])]
    if x >= b["p90"]:
        return 95 if x > b["p90"] * 1.2 else 90
    for (pa, va), (pb, vb) in zip(pts, pts[1:]):
        if va <= x <= vb:
            return int(pa + (pb - pa) * ((x - va) / (vb - va) if vb > va else 0))
    return 0


def performance(sid: str, fmt: str = "long") -> dict:
    """{video id: performance index}: the video's views / the channel's median views for the same format (posts aged
    3 to 90 days). 2.0 = twice what this channel usually gets."""
    m = channel_metrics(sid).get(fmt) or {}
    mv = m.get("med_views")
    if not mv:
        return {}
    with store._lock:
        rows = _db().execute(f"SELECT vid, views FROM yt_videos WHERE sid=? AND {FORMATS[fmt]} AND ts>? AND views>0",
                             (sid, time.time() - 365 * 86400)).fetchall()
    return {v: round(n / mv, 2) for v, n in rows}


def monthly(sid: str, since: float = None) -> list:
    """Per month since BACKFILL_FROM: posts by format, views / likes / comments of that month's posts (as of now),
    median engagement, hours streamed."""
    since = since or BACKFILL_FROM
    with store._lock:
        rows = _db().execute("SELECT ts, views, likes, comments, secs, live, short FROM yt_videos WHERE sid=? AND ts>=? ORDER BY ts",
                             (sid, since)).fetchall()
    months = {}
    for ts, v, lk, cm, secs, live, short in rows:
        k = datetime.fromtimestamp(ts).strftime("%Y-%m")
        m = months.setdefault(k, {"month": k, "videos": 0, "shorts": 0, "streams": 0, "views": 0, "likes": 0, "comments": 0,
                                  "stream_hours": 0.0, "_eng": []})
        m["streams" if live else "shorts" if short else "videos"] += 1
        m["views"] += v or 0
        m["likes"] += lk or 0
        m["comments"] += cm or 0
        if live:
            m["stream_hours"] += (secs or 0) / 3600
        if v and lk is not None:
            m["_eng"].append(((lk or 0) + (cm or 0)) / v)
    out = []
    for k in sorted(months):
        m = months[k]
        m["eng_rate"] = _med(m.pop("_eng"))
        m["stream_hours"] = round(m["stream_hours"], 1)
        out.append(m)
    return out


# ---------- top comments ----------

def comments_once(max_calls: int = 60) -> int:
    """Top comments of ranked channels' videos posted 1 to 8 days ago, once per video. Text kept 30 days."""
    key = os.getenv("YOUTUBE_API_KEY")
    with store._lock:
        c = _db()
        c.execute("DELETE FROM yt_comments WHERE fetched<?", (time.time() - COMMENTS_KEEP_DAYS * 86400,))
        c.commit()
    if not key or not events.yt_quota_left(.75):
        return 0
    a, b = ranked_set()
    top = (a + b)[:5000]
    now = time.time()
    with store._lock:
        c = _db()
        vids = []
        for i in range(0, len(top), 500):
            part = top[i:i + 500]
            vids += c.execute(f"""SELECT v.vid, v.views FROM yt_videos v WHERE v.sid IN ({','.join('?' * len(part))})
                                  AND v.ts BETWEEN ? AND ? AND COALESCE(v.comments, 1)>0
                                  AND NOT EXISTS (SELECT 1 FROM yt_comments k WHERE k.vid=v.vid)""",
                              part + [now - 8 * 86400, now - 86400]).fetchall()
    vids = [v for v, _ in sorted(vids, key=lambda x: -(x[1] or 0))][:max_calls]
    done = 0
    for vid in vids:
        if not events.yt_quota_left(.75):
            break
        try:
            r = events._http.get("https://www.googleapis.com/youtube/v3/commentThreads", timeout=15, params={
                "part": "snippet", "videoId": vid, "order": "relevance", "maxResults": 10, "textFormat": "plainText", "key": key})
        except Exception:
            break
        items = r.json().get("items", []) if r.status_code == 200 else []
        rows = []
        for i, it in enumerate(items):
            sn = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
            pub = sn.get("publishedAt")
            rows.append((vid, i + 1, (sn.get("authorDisplayName") or "")[:80], (sn.get("textDisplay") or "")[:500],
                         int(sn.get("likeCount") or 0),
                         int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()) if pub else None, int(now)))
        if not rows:                                    # comments off or none: remember, don't ask again
            rows = [(vid, 0, "", "", 0, None, int(now))]
        with store._lock:
            c = _db()
            c.executemany("INSERT OR REPLACE INTO yt_comments VALUES (?,?,?,?,?,?,?)", rows)
            c.commit()
        done += 1
    return done


def top_comments(sid: str, n: int = 12) -> list:
    with store._lock:
        rows = _db().execute("""SELECT k.vid, k.author, k.text, k.likes, k.ts, v.title FROM yt_comments k JOIN yt_videos v ON v.vid=k.vid
                                WHERE v.sid=? AND k.rank>0 ORDER BY k.likes DESC LIMIT ?""", (sid, n)).fetchall()
    return [dict(r) for r in rows]


# ---------- scheduler ----------

def run_forever():
    time.sleep(180)
    last_metrics = 0
    while True:
        for name, fn in (("refresh", refresh_once), ("backfill", backfill_once), ("comments", comments_once)):
            try:
                fn()
            except Exception as e:
                print(f"Deep {name}: {str(e)[:150]}")
        if time.time() - last_metrics > 3 * 3600:
            try:
                metrics_once()
                last_metrics = time.time()
            except Exception as e:
                print(f"Deep metrics: {str(e)[:150]}")
        time.sleep(600)


def start():
    import threading
    threading.Thread(target=run_forever, daemon=True).start()
