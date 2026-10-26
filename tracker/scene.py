"""India live streaming: every stream we can find on YouTube, Kick and Twitch, sorted into games and ranked.

Not tied to an event. Every SCENE_SEC (120s):
  1. Kick and Twitch: every live stream in the India languages (SCENE_LANGS, default hi), top 100 per language
     (needs the platform keys), plus the channels added by hand (Kick works without keys).
  2. YouTube: India-localised live searches for each game (every SCENE_YT_SEC, 300s; every 15 min while an event's
     official broadcast is live so the event counter keeps priority), plus the channels added by hand. Streams already
     found are re-counted every cycle from YouTube's live counter.
  3. Each channel's viewers are stored (sc_samples, kept SCENE_KEEP_DAYS) and rolled up per IST day (sc_daily, kept).

A streamer is one channel on one platform: yt:<channel id>, kick:<slug>, twitch:<login>. Two streams at once on the
same channel are added together. Streams under SCENE_MIN_VIEWERS are ignored.

Discovery is not a census: a YouTube stream that never appears in these searches and isn't added by hand is missed,
and Kick/Twitch are filtered by stream language. The page says so.
"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from tracker import events, platforms, store

SCENE_SEC = int(os.getenv("SCENE_SEC", "120"))
SCENE_YT_SEC = int(os.getenv("SCENE_YT_SEC", "300"))
MIN_VIEWERS = int(os.getenv("SCENE_MIN_VIEWERS", "20"))
KEEP_DAYS = int(os.getenv("SCENE_KEEP_DAYS", "14"))
LANGS = [x.strip() for x in os.getenv("SCENE_LANGS", "hi").split(",") if x.strip()]

# (game, words in a platform category or a stream title). Order matters: the first match wins.
GAMES = [
    ("PUBG PC", ["pubg: battlegrounds", "pubg pc", "pubg battlegrounds", "pubg steam"]),
    ("BGMI", ["bgmi", "battlegrounds mobile", "pubg mobile", "pubg", "bmps", "bgis", "bmsd", "bmic", "bmoc"]),
    ("Free Fire", ["free fire", "freefire", "ff max", "garena"]),
    ("GTA V", ["gta", "grand theft auto", "soulcity", "soul city rp"]),
    ("Valorant", ["valorant", "valo "]),
    ("Minecraft", ["minecraft"]),
    ("COD Mobile", ["cod mobile", "call of duty mobile", "codm", "call of duty: mobile"]),
    ("Call of Duty", ["call of duty", "warzone"]),
    ("Counter-Strike 2", ["counter-strike", "counter strike", "cs2", "csgo", "cs:go"]),
    ("Indus", ["indus battle royale", "indus game"]),
    ("Clash of Clans", ["clash of clans"]),
    ("Clash Royale", ["clash royale"]),
    ("Pokemon Unite", ["pokemon unite", "pokémon unite"]),
    ("Fortnite", ["fortnite"]),
    ("Apex Legends", ["apex legends"]),
    ("Roblox", ["roblox"]),
    ("Dota 2", ["dota"]),
    ("League of Legends", ["league of legends"]),
    ("EA Sports FC", ["ea sports fc", "ea fc", "fifa"]),
    ("Cricket games", ["real cricket", "cricket 24", "cricket 22", "world cricket championship", "wcc3"]),
    ("Chess", ["chess"]),
    ("Among Us", ["among us"]),
    ("Cricket (live)", ["ipl", "live cricket", "cricket live", "ind vs", "india vs", "t20", " odi ", "test match"]),
    ("News", ["news", "khabar", "samachar", "headlines", "breaking", "aaj tak", "ndtv", "republic", "tv9", "abp ",
              "zee ", "india tv", "lok sabha", "rajya sabha", "sansad"]),
    ("Devotional", ["bhajan", "aarti", "kirtan", "gurbani", "darshan", "katha", "satsang", "mandir", "temple", "puja",
                    "pooja", "mantra", "chalisa", "namaz", "jagran"]),
    ("Music", ["songs", "song", "music", "lofi", "lo-fi", "radio", "jukebox"]),
    ("Podcast / Talk", ["podcast", "talk show", "interview", "debate"]),
    ("Just Chatting", ["just chatting", "irl", "chatting", "q&a", "q & a"]),
]
# YouTube searches (India region). Each finds up to ~20 live streams.
QUERIES = ["BGMI live", "BGMI live tamil", "BGMI live telugu", "Free Fire live", "Free Fire max live hindi",
           "GTA 5 live hindi", "GTA 5 roleplay live hindi", "Valorant live hindi", "Minecraft live hindi",
           "COD mobile live india", "Indus battle royale live", "Pokemon Unite live hindi", "CS2 live hindi",
           "Clash of Clans live hindi", "Real cricket live", "hindi gaming live", "tamil gaming live",
           "telugu gaming live", "PUBG PC live hindi", "Roblox live hindi",
           # beyond gaming: everything live in India
           "live hindi", "live stream india", "news live hindi", "news live", "live tamil", "live telugu", "live bengali",
           "live marathi", "live kannada", "live malayalam", "live gujarati", "live punjabi", "bhajan live",
           "live darshan", "cricket live", "podcast live hindi", "live chat hindi", "music live hindi"]
LIVE_PAGE = "UC4R8DWoMoI7CAwX8_LjQHig"   # YouTube's own "Live" page, India edition: what's trending live now
SEEDS = {"kick": ["skyesports"], "twitch": [],
         "youtube": ["@SoulAman", "@DynamoGaming", "@TheBixiOP", "@ZGODGAMING", "@NEYOOGAMINGYT", "@MizoPlays",
                     "@MrSpike", "@LoLzZzGaming", "@SHARKSHE", "@MafiaNinja", "@ImRuthlessceopubg", "@RakaZoneGaming",
                     "@AnshYT", "@Casetoolive", "@sheekgaming", "@IPREEET.69", "@shreemanlegendliveofficial",
                     "@MortaLyt", "@VAADHIYAAR", "@soulregaltos9810", "@SnaxGaming", "@sriop-sr70", "@NEONXPAWANOP",
                     "@LadyPredatorGaming"]}

_LIVE = {}            # sid -> {"sid","platform","name","url","logo","game","title","streams": {vid: viewers},"seen","errs"}
_STATE = {"last": 0.0, "yt": 0.0, "seeds": 0.0, "errors": {}, "running": False}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=8)


def _db():
    c = store.conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS sc_channels (sid TEXT PRIMARY KEY, platform TEXT, name TEXT, url TEXT, logo TEXT,
        first_seen REAL, last_live REAL, title TEXT, game TEXT);
    CREATE TABLE IF NOT EXISTS sc_samples (ts INTEGER, sid TEXT, viewers INTEGER, game TEXT);
    CREATE INDEX IF NOT EXISTS sc_samples_ix ON sc_samples(ts);
    CREATE TABLE IF NOT EXISTS sc_daily (day TEXT, sid TEXT, game TEXT, peak INTEGER, peak_at INTEGER, mins REAL,
        hw REAL, PRIMARY KEY (day, sid, game));
    CREATE INDEX IF NOT EXISTS sc_daily_game ON sc_daily(game, day);
    CREATE TABLE IF NOT EXISTS sc_cat (ts INTEGER, game TEXT, viewers INTEGER, streams INTEGER, PRIMARY KEY (game, ts));
    """)
    return c


def slug(game: str) -> str:
    """URL name of a category: 'Free Fire' -> 'free-fire'."""
    return re.sub(r"[^a-z0-9]+", "-", (game or "").lower()).strip("-") or "other"


ALL = "__all__"          # the India-wide total in sc_cat
NON_GAMING = {"News", "Devotional", "Music", "Podcast / Talk", "Just Chatting", "Cricket (live)", "Other"}
_NON_GAMING_WORDS = ("irl", "chatting", "music", "talk", "sports", "slots", "casino", "pools", "asmr", "travel",
                     "podcast", "news", "special events", "art", "food", "politics")


def is_gaming(game: str) -> bool:
    """Games vs everything else (news, music, devotional, chatting ...). Unknown Kick/Twitch categories count as
    games unless their name says otherwise."""
    if game in NON_GAMING:
        return False
    if any(g == game for g, _ in GAMES):
        return True
    return not any(w in (game or "").lower() for w in _NON_GAMING_WORDS)


def classify(category: str, title: str) -> str:
    cat = (category or "").lower()
    if cat:
        for g, words in GAMES:
            if any(w in cat for w in words):
                return g
        return category.strip()[:40]        # the platform's own category name
    t = f" {(title or '').lower()} "
    for g, words in GAMES:
        if any(w in t for w in words):
            return g
    return "Other"


def seeds() -> dict:
    s = store.kv_get("scene_seeds")
    if s is None:
        s = {k: list(v) for k, v in SEEDS.items()}
    return {k: list(s.get(k, [])) for k in ("youtube", "kick", "twitch")}


def blocked() -> set:
    return set(store.kv_get("scene_blocked") or [])


# ---------- YouTube ----------

_SEARCH_LIVE = "EgJAAQ=="       # search filter: live now
_ITV_IN = {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": "IN"}


def _num(txt: str):
    d = re.sub(r"[^\d]", "", txt or "")
    return int(d) if d else None


def _text(o) -> str:
    if not o:
        return ""
    return o.get("simpleText") or "".join(r.get("text", "") for r in o.get("runs", []))


def yt_search(query: str) -> list:
    """Live streams for a search, localised to India. [{vid, channel, channel_id, title, viewers, logo}]"""
    r = events._http.post("https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
                          json={"context": {"client": _ITV_IN}, "query": query, "params": _SEARCH_LIVE},
                          headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                   "Origin": "https://www.youtube.com"}, timeout=10)
    r.raise_for_status()
    return _parse(_renderers(r.json()))


def _parse(found: list) -> list:
    out = []
    for v in found:
        watching = _text(v.get("viewCountText"))
        if "watching" not in watching.lower():
            continue                            # not live now (premieres, replays)
        by = (v.get("ownerText") or v.get("longBylineText") or v.get("shortBylineText") or {}).get("runs") or [{}]
        cid = ((by[0].get("navigationEndpoint") or {}).get("browseEndpoint") or {}).get("browseId", "")
        th = (((v.get("channelThumbnailSupportedRenderers") or {}).get("channelThumbnailWithLinkRenderer") or {})
              .get("thumbnail") or {}).get("thumbnails") or [{}]
        logo = th[0].get("url", "")
        if logo.startswith("//"):
            logo = "https:" + logo
        if v.get("videoId") and cid:
            out.append({"vid": v["videoId"], "channel": by[0].get("text", ""), "channel_id": cid,
                        "title": _text(v.get("title")), "viewers": _num(watching) or 0, "logo": logo})
    return out


def _renderers(j) -> list:
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k in ("videoRenderer", "gridVideoRenderer"):
                if k in o:
                    found.append(o[k])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(j)
    return found


def yt_live_page() -> list:
    """YouTube's Live page for India (the streams YouTube itself features as live now)."""
    r = events._http.post("https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
                          json={"context": {"client": _ITV_IN}, "browseId": LIVE_PAGE},
                          headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                   "Origin": "https://www.youtube.com"}, timeout=10)
    r.raise_for_status()
    return _parse(_renderers(r.json()))


def _yt_add(found: dict, s: dict, logo: str = ""):
    sid = f"yt:{s['channel_id']}"
    x = found.setdefault(sid, {"sid": sid, "platform": "youtube", "name": s.get("channel", ""), "logo": logo or s.get("logo", ""),
                               "url": f"https://youtu.be/{s['vid']}", "title": s.get("title", ""), "category": "",
                               "streams": {}})
    x["streams"][s["vid"]] = int(s.get("viewers") or 0)
    if x["streams"][s["vid"]] >= max(x["streams"].values()):
        x.update(url=f"https://youtu.be/{s['vid']}", title=s.get("title", ""))
    if not x.get("logo") and (logo or s.get("logo")):
        x["logo"] = logo or s.get("logo")


def _event_on_air() -> bool:
    return any(s.get("kind") == "official" for d in events._LIVE.values() for s in d.values())


# ---------- one cycle ----------

def cycle(now: float = None) -> dict:
    now = now or time.time()
    found, errors = {}, {}
    blk = blocked()
    sd = seeds()

    # Kick / Twitch: the whole language, plus hand-added channels
    for p in ("kick", "twitch"):
        rows = []
        if platforms._keys(p):
            for lang in LANGS:
                try:
                    if p == "twitch":
                        rows += platforms._tw_streams({"language": lang, "first": 100})
                    else:
                        j = platforms._get("kick", "https://api.kick.com/public/v1/livestreams",
                                           {"language": lang, "sort": "viewer_count", "limit": 100})
                        rows += [platforms._kick_row(s.get("slug") or "", s.get("stream_title"), s.get("viewer_count"),
                                                     category=(s.get("category") or {}).get("name", ""),
                                                     pic=s.get("profile_picture") or "")
                                 for s in j.get("data") or [] if s.get("slug")]
                except Exception as e:
                    errors[f"{p} {lang}"] = str(e)[:120]
        if sd[p] and (p == "kick" or platforms._keys(p)):
            try:
                rows += platforms._by_ids(p, [x.lower() for x in sd[p]])
            except Exception as e:
                errors[f"{p} channels"] = str(e)[:120]
        if p == "twitch" and rows:
            try:
                platforms._tw_logos(sorted({platforms.split(r["vid"])[1] for r in rows}))
            except Exception:
                pass
        for r in rows:
            sid = r["vid"]
            found[sid] = {"sid": sid, "platform": p, "name": r["channel"], "url": platforms.link(sid),
                          "logo": platforms.logo(sid), "title": r["title"], "category": r.get("category", ""),
                          "streams": {sid: r["viewers"]}}

    # YouTube: streams already live are re-counted every cycle; searches and hand-added channels less often
    with _lock:
        prev_yt = {k: dict(v) for k, v in _LIVE.items() if v["platform"] == "youtube"}
    jobs = {(sid, vid): _pool.submit(_safe_count, vid) for sid, x in prev_yt.items() for vid in x["streams"]}
    for (sid, vid), fu in jobs.items():
        n = fu.result()
        x = prev_yt[sid]
        if n == "err":
            if x.get("errs", 0) < 3:            # keep the last reading through a few failed reads
                _yt_add(found, {"vid": vid, "channel": x["name"], "channel_id": sid[3:], "title": x["title"],
                                "viewers": x["streams"][vid]}, x.get("logo", ""))
                found[sid]["errs"] = x.get("errs", 0) + 1
        elif n:
            _yt_add(found, {"vid": vid, "channel": x["name"], "channel_id": sid[3:], "title": x["title"], "viewers": n},
                    x.get("logo", ""))
    yt_every = SCENE_YT_SEC * (3 if _event_on_air() else 1)
    if now - _STATE["yt"] >= yt_every:
        _STATE["yt"] = now
        res_live = _try(yt_live_page)
        if res_live == "err":
            errors["youtube live page"] = "failed"
        for q, res in [("live page", res_live)] + list(zip(QUERIES, _pool.map(lambda q: _try(yt_search, q), QUERIES))):
            if res == "err":
                errors[f"youtube '{q}'"] = "search failed"
                continue
            for s in res:
                if f"yt:{s['channel_id']}" not in found or s["vid"] not in found[f"yt:{s['channel_id']}"]["streams"]:
                    _yt_add(found, s)
    if sd["youtube"] and now - _STATE["seeds"] >= yt_every * 2:
        _STATE["seeds"] = now
        for s in _pool.map(lambda h: events._safe(events.check_channel, h), sd["youtube"]):
            if s and s.get("channel_id"):
                _yt_add(found, s)

    # classify, filter, store
    rows = []
    for sid, x in found.items():
        x["viewers"] = sum(x["streams"].values())
        if sid in blk or x["viewers"] < MIN_VIEWERS:
            continue
        x["game"] = classify(x.get("category", ""), x.get("title", ""))
        x["seen"] = now
        rows.append(x)
    with _lock:
        last = _STATE["last"]
        _LIVE.clear()
        _LIVE.update({x["sid"]: x for x in rows})
        _STATE["last"] = now
        _STATE["errors"] = errors
    _store(rows, now, last)
    return {"live": len(rows), "viewers": sum(x["viewers"] for x in rows), "errors": errors}


def _safe_count(vid):
    try:
        return events.count_live(vid)
    except Exception:
        return "err"


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"Scene: {fn.__name__} failed: {str(e)[:120]}")
        return "err"


def _store(rows, now, last):
    if not rows:
        return
    dt = min(now - last, SCENE_SEC * 2) if last else SCENE_SEC
    day = datetime.fromtimestamp(now, events.REPORT_TZ).strftime("%Y-%m-%d")
    with store._lock:
        c = _db()
        c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(int(now), x["sid"], x["viewers"], x["game"]) for x in rows])
        for x in rows:
            c.execute("""INSERT INTO sc_channels VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(sid) DO UPDATE SET name=excluded.name,
                         url=excluded.url, logo=CASE WHEN excluded.logo!='' THEN excluded.logo ELSE sc_channels.logo END,
                         last_live=excluded.last_live, title=excluded.title, game=excluded.game""",
                      (x["sid"], x["platform"], x["name"], x["url"], x.get("logo") or "", now, now, x.get("title", ""),
                       x["game"]))
            c.execute("""INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                         peak_at=CASE WHEN excluded.peak > sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                         peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                      (day, x["sid"], x["game"], x["viewers"], int(now), dt / 60, x["viewers"] * dt / 3600))
        cats = {}
        for x in rows:
            a = cats.setdefault(x["game"], [0, 0])
            a[0] += x["viewers"]
            a[1] += 1
        cats[ALL] = [sum(x["viewers"] for x in rows), len(rows)]
        c.executemany("INSERT OR REPLACE INTO sc_cat VALUES (?,?,?,?)", [(int(now), g, v, n) for g, (v, n) in cats.items()])
        if int(now) % 3600 < SCENE_SEC:          # about once an hour: drop raw readings older than KEEP_DAYS
            c.execute("DELETE FROM sc_samples WHERE ts < ?", (now - KEEP_DAYS * 86400,))
        c.commit()


def run_forever():
    if _STATE["running"]:
        return
    _STATE["running"] = True
    time.sleep(20)                           # let the event counter start first
    while True:
        t0 = time.time()
        try:
            r = cycle()
            if r["errors"]:                  # shown in the tracker window so a failing source is visible
                print("India scan problems: " + "; ".join(f"{k}: {v}" for k, v in list(r["errors"].items())[:6]))
        except Exception as e:
            print(f"Scene cycle failed: {str(e)[:200]}")
        time.sleep(max(10, SCENE_SEC - (time.time() - t0)))


# ---------- numbers for the page ----------

PERIODS = {"today": 0, "7d": 6, "30d": 29}


SERIES_SEC = {"today": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


def _series(c, game: str, period: str) -> list:
    """[[ts, viewers]] for the chart: the category (or India) total each scan, thinned to about 600 points by
    keeping each bucket's highest reading (so peaks survive)."""
    t0 = time.time() - SERIES_SEC[period]
    rows = c.execute("SELECT ts, viewers FROM sc_cat WHERE game=? AND ts>=? ORDER BY ts", (game, t0)).fetchall()
    if len(rows) <= 600:
        return [[r[0], r[1]] for r in rows]
    step = (rows[-1][0] - rows[0][0]) / 600 or 1
    out, b = [], {}
    for ts, v in rows:
        k = int((ts - rows[0][0]) / step)
        if k not in b or v > b[k][1]:
            b[k] = [ts, v]
    return [b[k] for k in sorted(b)]


def _events() -> list:
    """Tracked tournaments for the hub: live now / countdown / finished, with their peak."""
    out = []
    with store._lock:
        c = events._db()
        for ev in sorted(events.events().values(), key=lambda e: -(e.get("created") or 0)):
            pr = events.preset(ev["key"])
            peak = c.execute("SELECT MAX(total) FROM ev_ticks WHERE event=?", (ev["key"],)).fetchone()[0] or 0
            last = c.execute("SELECT ts, total, official FROM ev_ticks WHERE event=? ORDER BY ts DESC LIMIT 1",
                             (ev["key"],)).fetchone()
            live = bool(last and time.time() - last[0] < 120 and not events.paused(ev["key"]))
            state = "ended" if pr.get("ended") else "live" if live else "upcoming" if events.next_start(ev["key"]) else "off"
            out.append({"key": ev["key"], "name": ev["name"], "game": events.opt(ev, "game", ""), "state": state,
                        "next_start": events.next_start(ev["key"]), "now": last[1] if live else 0, "peak": peak,
                        "url": f"/e/{ev['key']}/"})
    order = {"live": 0, "upcoming": 1, "off": 2, "ended": 3}
    return sorted(out, key=lambda e: order[e["state"]])


def category_name(cat: str):
    """Display name for a category slug, or None if nothing in it has ever been seen."""
    for g, _ in GAMES:
        if slug(g) == cat:
            return g
    with store._lock:
        for (g,) in _db().execute("SELECT DISTINCT game FROM sc_cat WHERE game != ?", (ALL,)):
            if slug(g) == cat:
                return g
    return None


def data(period: str = "today", cat: str = "") -> dict:
    """Everything the hub (cat='') or a category page shows."""
    period = period if period in PERIODS else "today"
    game = category_name(cat) if cat else None
    blk = blocked()
    with store._lock:      # the latest scan, from the database, so the CLI sees what the running tracker sees
        c = _db()
        last = (c.execute("SELECT MAX(ts) FROM sc_samples").fetchone()[0] or 0)
        live = [dict(r) for r in c.execute(
            """SELECT s.sid, s.viewers, s.game, c.platform, c.name, c.url, c.logo, c.title FROM sc_samples s
               LEFT JOIN sc_channels c ON c.sid=s.sid WHERE s.ts=? ORDER BY s.viewers DESC""", (last,))]
    fresh = time.time() - last < SCENE_SEC * 3
    seen = set()
    live = [x for x in live if x["sid"] not in blk and not (x["sid"] in seen or seen.add(x["sid"]))] if fresh else []
    india_total = sum(x["viewers"] for x in live)
    by_game = {}
    for x in live:
        g = by_game.setdefault(x["game"], {"game": x["game"], "slug": slug(x["game"]), "viewers": 0, "streams": 0,
                                           "top": x["name"], "top_logo": x.get("logo") or "", "top_viewers": x["viewers"]})
        g["viewers"] += x["viewers"]
        g["streams"] += 1
    if game:
        live = [x for x in live if x["game"] == game]
    tot = sum(x["viewers"] for x in live)
    by_plat = {}
    for x in live:
        by_plat[x["platform"]] = by_plat.get(x["platform"], 0) + x["viewers"]
    today = datetime.now(events.REPORT_TZ).date()
    d0 = (today - timedelta(days=PERIODS[period])).strftime("%Y-%m-%d")
    key = game or ALL
    with store._lock:
        c = _db()
        q = """SELECT d.sid, d.game, MAX(d.peak) peak, SUM(d.mins) mins, SUM(d.hw) hw, c.name, c.platform,
               c.url, c.logo FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid WHERE d.day >= ?"""
        rows = c.execute(q + (" AND d.game = ?" if game else "") + " GROUP BY d.sid, d.game",
                         (d0, game) if game else (d0,)).fetchall()
        series = _series(c, key, period)
        p0 = datetime.combine(today - timedelta(days=PERIODS[period]), datetime.min.time(), events.REPORT_TZ).timestamp()
        scans = c.execute("SELECT COUNT(*) FROM sc_cat WHERE game=? AND ts>=?", (ALL, p0)).fetchone()[0] or 0
        cstats = c.execute("SELECT game, SUM(viewers) s, MAX(viewers) pk FROM sc_cat WHERE ts>=? AND game!=? GROUP BY game",
                           (p0, ALL)).fetchall()
        tracked = c.execute("SELECT COUNT(*) FROM sc_channels").fetchone()[0]
        pk = c.execute("SELECT ts, viewers FROM sc_cat WHERE game=? AND ts>=? ORDER BY viewers DESC LIMIT 1",
                       (key, time.time() - SERIES_SEC[period])).fetchone()
        pk_all = c.execute("SELECT ts, viewers FROM sc_cat WHERE game=? ORDER BY viewers DESC LIMIT 1", (key,)).fetchone()
    ch, games = {}, {}
    for r in rows:
        if r["sid"] in blk:
            continue
        x = ch.setdefault(r["sid"], {"sid": r["sid"], "name": r["name"] or r["sid"], "platform": r["platform"] or "",
                                      "url": r["url"] or "", "logo": r["logo"] or "", "peak": 0, "mins": 0.0, "hw": 0.0,
                                      "games": {}})
        x["peak"] = max(x["peak"], r["peak"])
        x["mins"] += r["mins"]
        x["hw"] += r["hw"]
        x["games"][r["game"]] = x["games"].get(r["game"], 0) + r["hw"]
        g = games.setdefault(r["game"], {"game": r["game"], "slug": slug(r["game"]), "hw": 0.0, "peak_stream": 0,
                                         "channels": 0})
        g["hw"] += r["hw"]
        g["peak_stream"] = max(g["peak_stream"], r["peak"])
        g["channels"] += 1
    board = []
    for x in ch.values():
        x["avg"] = round(x["hw"] * 60 / x["mins"]) if x["mins"] else 0
        x["game"] = max(x["games"], key=x["games"].get) if x["games"] else ""
        x["hw"], x["airtime_h"] = round(x["hw"]), round(x["mins"] / 60, 1)
        del x["games"], x["mins"]
        board.append(x)
    board.sort(key=lambda x: -x["hw"])
    return {"updated": last, "fresh": fresh, "period": period, "every": SCENE_SEC,
            "cat": cat if game else "", "cat_name": game or "",
            "live_total": tot, "live_count": len(live), "india_total": india_total,
            "peak": {"viewers": pk[1], "ts": pk[0]} if pk else None,
            "peak_all": {"viewers": pk_all[1], "ts": pk_all[0]} if pk_all else None,
            "series": series,
            "platforms": [{"platform": k, "name": platforms.NAMES[k], "viewers": v}
                          for k, v in sorted(by_plat.items(), key=lambda kv: -kv[1])],
            "categories": sorted(by_game.values(), key=lambda g: -g["viewers"])[:40],
            "live": [{k: x.get(k) for k in ("sid", "platform", "name", "url", "logo", "game", "title", "viewers")}
                     for x in live[:300]],
            "board": board[:300],
            "games": [{**g, "hw": round(g["hw"])} for g in sorted(games.values(), key=lambda g: -g["hw"])][:40],
            "events": [] if game else _events(),
            # per category over the period: average concurrent viewers (missing scans count as 0) and peak
            "cat_period": sorted(({"game": r["game"], "slug": slug(r["game"]), "avg": round(r["s"] / scans) if scans else 0,
                                   "peak": r["pk"], "gaming": is_gaming(r["game"])} for r in cstats),
                                 key=lambda x: -x["avg"]),
            "tracked": tracked,
            "langs": LANGS, "min": MIN_VIEWERS, "keys": {p: bool(platforms._keys(p)) for p in ("kick", "twitch")}}


def probe() -> str:
    """One check of every source, for setting up (no secret values printed)."""
    lines = []
    try:
        res = yt_live_page()
        lines.append(f"YouTube Live page (India): {len(res)} live streams" +
                     (f", top {res[0]['channel']} {res[0]['viewers']:,}" if res else ""))
    except Exception as e:
        lines.append(f"YouTube Live page failed: {str(e)[:150]}")
    try:
        res = yt_search(QUERIES[0])
        lines.append(f"YouTube search '{QUERIES[0]}': {len(res)} live streams" +
                     (f", top {res[0]['channel']} {res[0]['viewers']:,}" if res else ""))
    except Exception as e:
        lines.append(f"YouTube search failed: {str(e)[:150]}")
    for lang in LANGS:                      # the language-wide discovery the India page uses
        for p in ("twitch", "kick"):
            if not platforms._keys(p):
                lines.append(f"{platforms.NAMES[p]} '{lang}' streams: no keys")
                continue
            try:
                if p == "twitch":
                    rows = platforms._tw_streams({"language": lang, "first": 100})
                else:
                    j = platforms._get("kick", "https://api.kick.com/public/v1/livestreams",
                                       {"language": lang, "sort": "viewer_count", "limit": 100})
                    rows = j.get("data") or []
                    rows = [{"channel": r.get("slug", ""), "viewers": r.get("viewer_count") or 0} for r in rows]
                top = max(rows, key=lambda r: r["viewers"]) if rows else None
                lines.append(f"{platforms.NAMES[p]} '{lang}' streams: {len(rows)} live" +
                             (f", top {top['channel']} {top['viewers']:,}" if top else ""))
            except Exception as e:
                r = getattr(e, "response", None)
                body = (r.text[:200] if r is not None else "")
                lines.append(f"{platforms.NAMES[p]} '{lang}' streams FAILED: {str(e)[:150]} {body}")
    for p in ("kick", "twitch"):
        st = platforms.status()[p]
        try:
            ids = seeds()[p] or (["skyesports"] if p == "kick" else [])
            if ids and (p == "kick" or platforms._keys(p)):
                r = platforms._by_ids(p, ids)
                lines.append(f"{platforms.NAMES[p]} channels {ids}: {len(r)} live ({st})")
            else:
                lines.append(f"{platforms.NAMES[p]}: {st}")
        except Exception as e:
            lines.append(f"{platforms.NAMES[p]} failed: {str(e)[:150]} ({st})")
    return "\n".join(lines)


def top(period: str = "today", n: int = 20) -> str:
    d = data(period)
    out = [f"India live now: {events.fmt_n(d['live_total'])} viewers across {d['live_count']} streams"]
    out += [f"  {events.fmt_n(x['viewers']):>7}  {x['name']} ({platforms.NAMES.get(x['platform'], '')}, {x['game']})"
            for x in d["live"][:n]]
    out.append(f"\nTop streamers, {period}: hours watched / peak / average")
    out += [f"  {i + 1:>3}. {x['name']} ({platforms.NAMES.get(x['platform'], '')}, {x['game']}): "
            f"{events.fmt_n(x['hw'])}h / {events.fmt_n(x['peak'])} / {events.fmt_n(x['avg'])}"
            for i, x in enumerate(d["board"][:n])]
    return "\n".join(out)
