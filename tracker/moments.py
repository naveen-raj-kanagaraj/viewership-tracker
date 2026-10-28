"""Moments: sudden jumps in a live stream's viewers, with a link (and an on-site player) at that second, and a real
Twitch clip when a Twitch account is connected.

Detection runs on the 2-second readings (scene._FASTV: the top Kick/Twitch channels and the biggest YouTube channels).
A moment is when a stream that has been live for a while jumps well above where it was a minute or two earlier:
    base  = lowest reading 45 to 120 seconds ago (at least MIN_BASE watching)
    jump  = now - base, at least max(MIN_JUMP, JUMP_PCT of base), seen on two readings in a row
Then the peak is followed for 3 minutes. One moment per channel per COOLDOWN.

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
MIN_JUMP = int(os.getenv("MOMENT_MIN_JUMP", "1500"))       # and jumps smaller than this
JUMP_PCT = float(os.getenv("MOMENT_JUMP_PCT", "0.25"))     # ... or than this share of the base
COOLDOWN = int(os.getenv("MOMENT_COOLDOWN", "900"))        # seconds between two moments of one channel
FOLLOW = 180                                               # seconds to keep updating a moment's peak
CLIPS_PER_HOUR = int(os.getenv("TWITCH_CLIPS_PER_HOUR", "20"))
LEAD = 30                                                  # links start this many seconds before the jump

_SCHEMA = """
CREATE TABLE IF NOT EXISTS moments (id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, platform TEXT, name TEXT, logo TEXT,
    game TEXT, title TEXT, vid TEXT, ts INTEGER, base INTEGER, peak INTEGER, peak_ts INTEGER, link TEXT, embed TEXT,
    embed_id TEXT, embed_t INTEGER, clip_url TEXT, thumb TEXT, india INTEGER);
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
        _ready = True
    return c


# ---------- detection ----------

def _check(sid: str, h: deque, now: float):
    """A new moment for this channel? Returns (start ts, base, current) or None."""
    if len(h) < 20 or now - h[0][0] < 300:
        return None                           # needs ~5 minutes of readings: no "stream just started" ramps
    old = [v for t, v in h if now - 120 <= t <= now - 45]
    if len(old) < 5:
        return None
    base = min(old)
    last2 = [v for t, v in list(h)[-2:]]
    need = max(MIN_JUMP, base * JUMP_PCT)
    if base < MIN_BASE or len(last2) < 2 or min(last2) - base < need:
        return None
    start = next((t for t, v in h if t >= now - 120 and v > base + need * .3), h[-1][0])
    return start, base, last2[-1]


def observe(now: float = None):
    """Called every 2 seconds with the fresh readings."""
    from tracker import scene
    now = now or time.time()
    with scene._lock:
        live = {sid: dict(x) for sid, x in scene._LIVE.items()}
    for sid, f in list(scene._FASTV.items()):
        ts, v = f[0], f[1]
        if not v or now - ts > 10 or sid not in live:
            continue
        h = _HIST.setdefault(sid, deque(maxlen=240))
        if h and h[-1][0] >= ts:
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
        hit = _check(sid, h, now)
        if hit:
            _LAST[sid] = now
            _new(sid, live[sid], *hit, now)
    for sid in [s for s in _HIST if s not in scene._FASTV]:
        _HIST.pop(sid, None)


def _new(sid, x, start, base, cur, now):
    vid = max(x.get("streams") or {"": 0}, key=lambda k: (x.get("streams") or {}).get(k, 0)) if x.get("streams") else ""
    plat = x.get("platform") or platforms.platform_of(sid.replace("yt:", ""))
    with store._lock:
        c = _db()
        india = (c.execute("SELECT COALESCE(india,1) FROM sc_channels WHERE sid=?", (sid,)).fetchone() or [1])[0]
        cur_ = c.execute("""INSERT INTO moments (sid, platform, name, logo, game, title, vid, ts, base, peak, peak_ts, link,
                            embed, embed_id, embed_t, clip_url, thumb, india) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (sid, plat, x.get("name"), x.get("logo") or "", x.get("game"), x.get("title"), vid, int(start), int(base),
                          int(cur), int(now), x.get("url") or "", "", "", 0, "", "", india))
        mid = cur_.lastrowid
        c.commit()
    _OPEN[sid] = {"id": mid, "until": now + FOLLOW, "peak": cur}
    print(f"Moment: {x.get('name')} {base:,} -> {cur:,} ({plat})", flush=True)
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
        rows = [dict(r) for r in _db().execute(q + " ORDER BY (peak - base) DESC, ts DESC LIMIT ?", (*a, limit))]
        games = [g for (g,) in _db().execute("SELECT game FROM moments WHERE ts>=? GROUP BY game ORDER BY COUNT(*) DESC LIMIT 30", (t0,))]
    for r in rows:
        r["jump"] = r["peak"] - r["base"]
        r["pct"] = round(100 * r["jump"] / r["base"]) if r["base"] else 0
        r["secs"] = max(2, (r["peak_ts"] or r["ts"]) - r["ts"])
    if not sid:
        rows.sort(key=lambda r: -r["jump"])
    return {"moments": rows, "games": [g for g in games if g], "clips": bool(_user().get("refresh"))}
