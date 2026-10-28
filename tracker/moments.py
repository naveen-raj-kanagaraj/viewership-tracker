"""Moments: sudden jumps in a live stream's viewers, with a link (and an on-site player) at that second, and a real
Twitch clip when a Twitch account is connected.

Two signals, judged against each stream's own normal (not a flat percentage):
    chat     messages per second (tracker/chat.py: Twitch IRC, Kick websocket, YouTube live chat). A burst is the last
             15 seconds well above the stream's median of the previous 10 minutes (robust z-score >= CHAT_Z and at
             least 2.5x the median). Chat reacts within seconds, so it pins the time.
    viewers  the 2-second readings (scene._FASTV). A spike is the rise over the last ~1-2 minutes well beyond the
             stream's usual one-minute swings over the last 30 minutes (z >= VIEW_Z), and at least 3% / 500 viewers.
             Viewer counts lag the moment (platforms update them late, people arrive late), so a viewers-only
             moment starts 60 seconds earlier.
Not moments: the first 10 minutes of a stream, Twitch raids (seen in chat), and viewers coming back to a level the
stream already had in the last 30 minutes (after a break). A chat burst counts even then.
Score ("hype") = chat z + viewer z. One moment per channel per COOLDOWN; the peak is followed for 3 minutes.

Where it links:
    YouTube  youtu.be/<video>?t=<seconds since the stream started - 30>  (start time from the watch page)
    Twitch   a clip made on the spot (POST helix/clips with the connected account), else the replay at that time
    Kick     the channel (Kick has no way to link to a time)

Twitch clips need a Twitch account connected once: `python track.py twitch-login` (device code: open
twitch.tv/activate and type the code). Tokens are kept in the database (kv twitch_user), never in git.
"""
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from tracker import events, platforms, store

MIN_BASE = int(os.getenv("MOMENT_MIN_BASE", "1000"))       # ignore streams smaller than this
MIN_JUMP = int(os.getenv("MOMENT_MIN_JUMP", "500"))        # viewer spikes smaller than this are ignored
JUMP_PCT = float(os.getenv("MOMENT_JUMP_PCT", "0.03"))     # ... or smaller than this share of the base
CHAT_Z = float(os.getenv("MOMENT_CHAT_Z", "5"))
VIEW_Z = float(os.getenv("MOMENT_VIEW_Z", "5"))
COOLDOWN = int(os.getenv("MOMENT_COOLDOWN", "600"))        # seconds between two moments of one channel
VIEW_LAG = 60                                              # viewer counts trail the moment by about this much
FOLLOW = 180                                               # seconds to keep updating a moment's peak
CLIPS_PER_HOUR = int(os.getenv("TWITCH_CLIPS_PER_HOUR", "20"))
LEAD = 30                                                  # links start this many seconds before the jump

_SCHEMA = """
CREATE TABLE IF NOT EXISTS moments (id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, platform TEXT, name TEXT, logo TEXT,
    game TEXT, title TEXT, vid TEXT, ts INTEGER, base INTEGER, peak INTEGER, peak_ts INTEGER, link TEXT, embed TEXT,
    embed_id TEXT, embed_t INTEGER, clip_url TEXT, thumb TEXT, india INTEGER, kind TEXT, score REAL,
    chat_base REAL, chat_peak REAL);
CREATE INDEX IF NOT EXISTS moments_ts ON moments(ts);
CREATE INDEX IF NOT EXISTS moments_sid ON moments(sid, ts);
"""
_ready = False
_HIST = {}            # sid -> deque[(ts, viewers)]
_LAST = {}            # sid -> ts of its last moment
_OPEN = {}            # sid -> {id, until, peak}
_CLIPS = deque(maxlen=200)
_YT_START = {}        # video id -> stream start (unix) or 0 if unknown


def _db():
    global _ready
    from tracker import scene
    c = scene._db()
    if not _ready:
        c.executescript(_SCHEMA)
        have = {r[1] for r in c.execute("PRAGMA table_info(moments)")}
        for col, typ in (("kind", "TEXT"), ("score", "REAL"), ("chat_base", "REAL"), ("chat_peak", "REAL")):
            if col not in have:
                c.execute(f"ALTER TABLE moments ADD COLUMN {col} {typ}")
        c.commit()
        _ready = True
    return c


# ---------- detection ----------

def _med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def chat_burst(sid: str, now: float, lag: int = 0):
    """(burst start ts, z, rate now, baseline rate) or None. lag: seconds to leave out at the end (YouTube's chat
    arrives in batches up to 15 s late)."""
    from tracker import chat
    if not chat.covered(sid, now):
        return None
    S = chat.series(sid, now - lag)
    if len(S) < 70:
        return None
    rec, hist = S[-3:], [n / chat.BUCKET for b, n in S[-123:-12]]      # last 15 s vs the 10 minutes before the last minute
    if len(hist) < 60:
        return None
    rate = sum(n for _, n in rec) / (len(rec) * chat.BUCKET)
    base = _med(hist)
    mad = _med([abs(x - base) for x in hist]) * 1.4826
    z = (rate - base) / max(mad, .25 * base, .2)
    if z < CHAT_Z or rate < max(2.5 * base, .6):
        return None
    lim = base + .5 * (rate - base)
    start = next((b for b, n in S[-12:] if n / chat.BUCKET > lim), rec[0][0])
    return start, round(z, 1), rate, base


def viewer_spike(sid: str, h: deque, now: float):
    """(rise start ts, z, base, now, is_recovery) or None."""
    pts = list(h)
    if len(pts) < 30 or now - pts[0][0] < 600:
        return None                           # first 10 minutes of watching this stream: ramps, not moments
    win = [v for t, v in pts if now - 150 <= t <= now - 60]
    if len(win) < 5:
        return None
    v0, v = min(win), pts[-1][1]
    last2 = [x for _, x in pts[-2:]]
    d = min(last2) - v0
    if v0 < MIN_BASE or d < max(MIN_JUMP, JUMP_PCT * v0):
        return None
    # this stream's usual one-minute swing over the last 30 minutes
    by_t = [(t, x) for t, x in pts if t >= now - 1800]
    deltas, j = [], 0
    for i, (t, x) in enumerate(by_t):
        while j < i and by_t[j][0] < t - 60:
            j += 1
        if t - by_t[j][0] >= 50 and t < now - 150:
            deltas.append(x - by_t[j][1])
    if len(deltas) < 20:
        return None
    md = _med(deltas)
    spread = _med([abs(x - md) for x in deltas]) * 1.4826
    z = d / max(spread, .01 * v0, 30)
    if z < VIEW_Z:
        return None
    earlier = [x for t, x in pts if now - 1800 <= t < now - 150]
    recovery = bool(earlier) and max(earlier) >= .97 * v
    start = next((t for t, x in pts if t >= now - 150 and x > v0 + .3 * d), pts[-1][0])
    return start, round(z, 1), v0, v, recovery


def observe(now: float = None):
    """Called every 2 seconds with the fresh readings."""
    from tracker import chat, scene
    now = now or time.time()
    with scene._lock:
        live = {sid: dict(x) for sid, x in scene._LIVE.items()}
    for sid, f in list(scene._FASTV.items()):
        ts, v = f[0], f[1]
        if not v or now - ts > 10 or sid not in live:
            continue
        h = _HIST.setdefault(sid, deque(maxlen=700))          # ~40 minutes at one reading per 4 s
        if h and ts - h[-1][0] < 3.5:
            continue
        h.append((ts, v))
        op = _OPEN.get(sid)
        if op:
            if now > op["until"]:
                _OPEN.pop(sid, None)
            elif v > op["peak"]:
                op["peak"] = v
                with store._lock:
                    c = _db()
                    c.execute("UPDATE moments SET peak=?, peak_ts=? WHERE id=?", (v, int(ts), op["id"]))
                    c.commit()
            continue
        if now - _LAST.get(sid, 0) < COOLDOWN:
            continue
        cb = chat_burst(sid, now, lag=15 if sid.startswith("yt:") else 0)
        vs = viewer_spike(sid, h, now)
        rd = chat.raid(sid)
        raided = bool(rd and now - rd[0] < 180)
        if cb:
            kind = "both" if vs else "chat"
            start, score = cb[0], cb[1] + (vs[1] if vs else 0)
            base = vs[2] if vs else min((x for t, x in h if now - 150 <= t <= now - 60), default=v)
        elif vs and not vs[4] and not raided:
            kind, start, score, base = "viewers", vs[0] - VIEW_LAG, vs[1], vs[2]
        else:
            continue
        _LAST[sid] = now
        _new(sid, live[sid], int(start), int(base), v, now, kind, score, cb[3] if cb else None, cb[2] if cb else None)
    for sid in [s for s in _HIST if s not in scene._FASTV]:
        _HIST.pop(sid, None)


def _new(sid, x, start, base, cur, now, kind="viewers", score=0.0, chat_base=None, chat_peak=None):
    vid = max(x.get("streams") or {"": 0}, key=lambda k: (x.get("streams") or {}).get(k, 0)) if x.get("streams") else ""
    plat = x.get("platform") or platforms.platform_of(sid.replace("yt:", ""))
    with store._lock:
        c = _db()
        india = (c.execute("SELECT COALESCE(india,1) FROM sc_channels WHERE sid=?", (sid,)).fetchone() or [1])[0]
        cur_ = c.execute("""INSERT INTO moments (sid, platform, name, logo, game, title, vid, ts, base, peak, peak_ts, link,
                            embed, embed_id, embed_t, clip_url, thumb, india, kind, score, chat_base, chat_peak)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (sid, plat, x.get("name"), x.get("logo") or "", x.get("game"), x.get("title"), vid, int(start), int(base),
                          int(cur), int(now), x.get("url") or "", "", "", 0, "", "", india, kind, round(score, 1), chat_base, chat_peak))
        mid = cur_.lastrowid
        c.commit()
    _OPEN[sid] = {"id": mid, "until": now + FOLLOW, "peak": cur}
    print(f"Moment ({kind}, hype {score:.0f}): {x.get('name')} {base:,} -> {cur:,} ({plat})", flush=True)
    threading.Thread(target=_links, args=(mid, sid, plat, vid, int(start)), daemon=True).start()


# ---------- links, players, clips ----------

def _yt_start(vid: str) -> int:
    if vid in _YT_START:
        return _YT_START[vid]
    st = 0
    try:
        r = events._http.get("https://www.youtube.com/watch", params={"v": vid}, timeout=12,
                             headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                             cookies={"CONSENT": "YES+", "SOCS": "CAI"})
        m = re.search(r'"startTimestamp"\s*:\s*"([^"]+)"', r.text)
        if m:
            st = int(datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).timestamp())
    except Exception as e:
        print(f"Moment: no start time for {vid}: {str(e)[:80]}")
    _YT_START[vid] = st
    if len(_YT_START) > 2000:
        _YT_START.clear()
    return st


def _hms(sec: int) -> str:
    sec = max(0, int(sec))
    return f"{sec // 3600}h{sec % 3600 // 60}m{sec % 60}s"


def _links(mid, sid, plat, vid, start):
    upd = {}
    try:
        if plat == "youtube" and vid:
            s0 = _yt_start(vid)
            off = max(0, start - s0 - LEAD) if s0 else 0
            upd = {"link": f"https://youtu.be/{vid}" + (f"?t={off}" if s0 else ""), "embed": "yt", "embed_id": vid,
                   "embed_t": off, "thumb": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"}
        elif plat == "twitch":
            login = sid.split(":", 1)[1]
            uid = (platforms._get("twitch", "https://api.twitch.tv/helix/users", {"login": login}).get("data") or [{}])[0].get("id")
            clip = _clip(uid) if uid else None
            if clip:
                upd = {"link": f"https://clips.twitch.tv/{clip}", "clip_url": f"https://clips.twitch.tv/{clip}",
                       "embed": "tw_clip", "embed_id": clip}
            if uid:
                v = (platforms._get("twitch", "https://api.twitch.tv/helix/videos",
                                    {"user_id": uid, "type": "archive", "first": 1}).get("data") or [{}])[0]
                if v.get("id") and v.get("created_at"):
                    s0 = int(datetime.fromisoformat(v["created_at"].replace("Z", "+00:00")).timestamp())
                    if s0 <= start:
                        off = max(0, start - s0 - LEAD)
                        upd.setdefault("link", f"{v.get('url')}?t={_hms(off)}")
                        upd.setdefault("embed", "tw_vod")
                        upd.setdefault("embed_id", v["id"])
                        upd["embed_t"] = off
                        th = (v.get("thumbnail_url") or "").replace("%{width}", "320").replace("%{height}", "180")
                        if th and "_404" not in th:
                            upd["thumb"] = th
    except Exception as e:
        print(f"Moment links for {sid}: {str(e)[:120]}")
    if upd:
        with store._lock:
            c = _db()
            c.execute(f"UPDATE moments SET {', '.join(k + '=?' for k in upd)} WHERE id=?", (*upd.values(), mid))
            c.commit()


# ---------- Twitch account (for clips) ----------

def _user() -> dict:
    return store.kv_get("twitch_user") or {}


def _user_token():
    u = _user()
    if not u.get("refresh"):
        return None
    if time.time() < u.get("exp", 0) - 120:
        return u["access"]
    cid, sec = platforms._keys("twitch") or (os.getenv("TWITCH_CLIENT_ID", ""), "")
    data = {"grant_type": "refresh_token", "refresh_token": u["refresh"], "client_id": cid}
    if sec:
        data["client_secret"] = sec
    r = platforms._http.post("https://id.twitch.tv/oauth2/token", data=data, timeout=15)
    if r.status_code >= 400:
        print(f"Twitch login expired ({r.status_code}): run  python track.py twitch-login  again")
        return None
    j = r.json()
    u.update(access=j["access_token"], refresh=j.get("refresh_token", u["refresh"]), exp=time.time() + int(j.get("expires_in", 3600)))
    store.kv_set("twitch_user", u)
    return u["access"]


def _clip(broadcaster_id: str):
    """Clip the last ~30 seconds of a live Twitch stream. Returns the clip id or None."""
    now = time.time()
    if sum(1 for t in _CLIPS if now - t < 3600) >= CLIPS_PER_HOUR:
        return None
    tok = _user_token()
    if not tok:
        return None
    cid = (platforms._keys("twitch") or ("",))[0]
    r = platforms._http.post("https://api.twitch.tv/helix/clips", params={"broadcaster_id": broadcaster_id},
                             headers={"Authorization": f"Bearer {tok}", "Client-Id": cid}, timeout=15)
    _CLIPS.append(now)
    if r.status_code >= 400:
        print(f"Twitch clip failed ({r.status_code}): {r.text[:120]}")
        return None
    d = (r.json().get("data") or [{}])[0]
    return d.get("id")


def twitch_login() -> str:
    """Connect a Twitch account once (device code flow), so the site can make clips."""
    cid, sec = platforms._keys("twitch") or (os.getenv("TWITCH_CLIENT_ID", ""), "")
    if not cid:
        return "TWITCH_CLIENT_ID isn't set in .env."
    r = platforms._http.post("https://id.twitch.tv/oauth2/device", data={"client_id": cid, "scopes": "clips:edit"}, timeout=15)
    if r.status_code >= 400:
        return f"Twitch said no ({r.status_code}): {r.text[:200]}"
    d = r.json()
    print(f"\nOn any device, open {d.get('verification_uri', 'https://www.twitch.tv/activate')}\n"
          f"log in with the account that should make the clips, and enter this code:\n\n    {d['user_code']}\n\nWaiting...", flush=True)
    t_end, wait = time.time() + int(d.get("expires_in", 1800)), int(d.get("interval", 5))
    while time.time() < t_end:
        time.sleep(wait)
        data = {"client_id": cid, "scopes": "clips:edit", "device_code": d["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}
        if sec:
            data["client_secret"] = sec
        t = platforms._http.post("https://id.twitch.tv/oauth2/token", data=data, timeout=15)
        j = t.json() if t.headers.get("content-type", "").startswith("application/json") else {}
        if t.status_code == 200 and j.get("access_token"):
            v = platforms._http.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {j['access_token']}"}, timeout=15).json()
            store.kv_set("twitch_user", {"access": j["access_token"], "refresh": j.get("refresh_token"),
                                         "exp": time.time() + int(j.get("expires_in", 3600)), "login": v.get("login"), "id": v.get("user_id")})
            return f"Connected as {v.get('login')}. Big Twitch spikes will now be clipped automatically (up to {CLIPS_PER_HOUR} an hour)."
        if "pending" not in (j.get("message") or "").lower():
            return f"Login didn't finish: {j.get('message') or t.text[:200]}"
    return "The code expired. Run it again."


# ---------- for the pages ----------

def recent(region: str = "global", period: str = "today", game: str = "", sid: str = "", limit: int = 60) -> dict:
    days = {"today": 1, "7d": 7, "30d": 30}.get(period, 1)
    if period == "today":
        t0 = datetime.combine(datetime.now(events.REPORT_TZ).date(), datetime.min.time(), events.REPORT_TZ).timestamp()
    else:
        t0 = time.time() - days * 86400
    q = "SELECT * FROM moments WHERE ts>=?"
    a = [t0]
    if region == "in":
        q += " AND india=1"
    if game:
        q += " AND game=?"
        a.append(game)
    if sid:
        q = "SELECT * FROM moments WHERE sid=?"
        a = [sid]
    with store._lock:
        rows = [dict(r) for r in _db().execute(q + " ORDER BY COALESCE(score, 0) DESC, ts DESC LIMIT ?", (*a, limit))]
        games = [g for (g,) in _db().execute("SELECT game FROM moments WHERE ts>=? GROUP BY game ORDER BY COUNT(*) DESC LIMIT 30", (t0,))]
    for r in rows:
        r["jump"] = r["peak"] - r["base"]
        r["pct"] = round(100 * r["jump"] / r["base"]) if r["base"] else 0
        r["secs"] = max(2, (r["peak_ts"] or r["ts"]) - r["ts"])
    if sid:
        rows.sort(key=lambda r: -r["ts"])
    return {"moments": rows, "games": [g for g in games if g], "clips": bool(_user().get("refresh"))}
