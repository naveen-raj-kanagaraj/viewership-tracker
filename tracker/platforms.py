"""Kick and Twitch next to YouTube.

A stream from another platform gets a prefixed id, so it flows through the same tables, live counter and pages as
a YouTube video id without any schema change:

    kick:<channel slug>        e.g. kick:xqc
    twitch:<login>             e.g. twitch:shroud

One id per channel: every broadcast on that channel during the event is the same "stream" (per-day numbers still
come from the timestamps).

Event config (in a preset or on the event itself):

    "kick":   {"official": ["slug"], "channels": ["slug", ...], "category": "PUBG Mobile"},
    "twitch": {"official": ["login"], "channels": ["login", ...], "category": "VALORANT"},

official   always counted, as the official broadcast
channels   counted while their title matches the event's match words (all titles with "any_title": True)
category   live streams in that game/category, same title rule (top 100 by viewers)

Keys go in .env (never commit them):
    TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET     dev.twitch.tv/console, an app with the client-credentials flow
    KICK_CLIENT_ID, KICK_CLIENT_SECRET         kick.com developer settings, an app (client credentials)
Twitch needs its keys. Kick works without keys through its public channel pages (unofficial, may be blocked or
change); with keys it uses the official API.
"""
import os
import threading
import time

import requests

NAMES = {"youtube": "YouTube", "kick": "Kick", "twitch": "Twitch"}
COUNT_TTL = float(os.getenv("PLATFORM_COUNT_SEC", "15"))   # Kick/Twitch update their counts about every 30-60s
_http = requests.Session()
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
       "Version/17.0 Safari/605.1.15")
_tok = {}                 # platform -> (token, expiry)
_known = {}               # platform -> set of ids the live counter should re-count
_snap = {}                # platform -> {"ts": epoch, "data": {vid: stream dict}}
_lock = threading.Lock()
_logos = {}               # channel_id -> logo url
_cats = {}                # (platform, name) -> category id


def split(vid: str):
    """('kick', 'xqc') for 'kick:xqc', ('youtube', vid) for a YouTube id."""
    p, sep, rest = (vid or "").partition(":")
    return (p, rest) if sep and p in ("kick", "twitch") else ("youtube", vid)


def platform_of(vid: str) -> str:
    return split(vid)[0]


def is_other(vid: str) -> bool:
    return platform_of(vid) != "youtube"


def link(vid: str) -> str:
    p, x = split(vid)
    return {"kick": f"https://kick.com/{x}", "twitch": f"https://www.twitch.tv/{x}"}.get(p, f"https://youtu.be/{vid}")


def logo(cid: str) -> str:
    return _logos.get(cid, "")


def cfg(ev: dict, preset: dict, platform: str) -> dict:
    c = ev.get(platform) or preset.get(platform) or {}
    return {"official": [x.lower().lstrip("@") for x in c.get("official", [])],
            "channels": [x.lower().lstrip("@") for x in c.get("channels", [])],
            "category": c.get("category") or ""}


def listed(ev: dict, preset: dict, vid: str) -> bool:
    p, x = split(vid)
    if p == "youtube":
        return False
    c = cfg(ev, preset, p)
    return x in c["official"] or x in c["channels"]


def official(ev: dict, preset: dict, vid: str) -> bool:
    p, x = split(vid)
    return p != "youtube" and x in cfg(ev, preset, p)["official"]


def enabled(ev: dict, preset: dict) -> list:
    return [p for p in ("kick", "twitch") if any(cfg(ev, preset, p).values())]


def status() -> dict:
    """Which connectors can run (no secret values)."""
    return {"twitch": "official API" if _keys("twitch") else "needs TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET",
            "kick": "official API" if _keys("kick") else "public channel pages (no keys, unofficial)"}


# ---------- auth ----------

def _keys(p):
    i, s = os.getenv(f"{p.upper()}_CLIENT_ID", ""), os.getenv(f"{p.upper()}_CLIENT_SECRET", "")
    return (i, s) if i and s else None


def _token(p):
    t = _tok.get(p)
    if t and t[1] > time.time() + 60:
        return t[0]
    i, s = _keys(p)
    url = "https://id.twitch.tv/oauth2/token" if p == "twitch" else "https://id.kick.com/oauth/token"
    r = _http.post(url, data={"client_id": i, "client_secret": s, "grant_type": "client_credentials"}, timeout=10)
    r.raise_for_status()
    j = r.json()
    _tok[p] = (j["access_token"], time.time() + int(j.get("expires_in") or 3600))
    return j["access_token"]


def _get(p, url, params):
    for attempt in (0, 1):
        h = {"Authorization": f"Bearer {_token(p)}"}
        if p == "twitch":
            h["Client-Id"] = _keys(p)[0]
        r = _http.get(url, params=params, headers=h, timeout=10)
        if r.status_code == 401 and not attempt:
            _tok.pop(p, None)            # expired or revoked: fetch a new app token once
            continue
        r.raise_for_status()
        return r.json()


# ---------- Twitch (Helix) ----------

def _tw_streams(params) -> list:
    j = _get("twitch", "https://api.twitch.tv/helix/streams", params)
    out = []
    for s in j.get("data") or []:
        if s.get("type") != "live":
            continue
        login = (s.get("user_login") or "").lower()
        out.append({"vid": f"twitch:{login}", "channel_id": f"twitch:{login}", "channel": s.get("user_name") or login,
                    "title": s.get("title") or "", "viewers": int(s.get("viewer_count") or 0),
                    "category": s.get("game_name") or "", "platform": "twitch"})
    return out


def _tw_logins(logins) -> list:
    out = []
    for i in range(0, len(logins), 100):
        out += _tw_streams([("user_login", x) for x in logins[i:i + 100]] + [("first", 100)])
    return out


def _tw_category(name) -> list:
    gid = _cats.get(("twitch", name.lower()))
    if gid is None:
        g = (_get("twitch", "https://api.twitch.tv/helix/games", {"name": name}).get("data") or [])
        gid = _cats[("twitch", name.lower())] = g[0]["id"] if g else ""
    return _tw_streams({"game_id": gid, "first": 100}) if gid else []


def _tw_logos(logins):
    need = [x for x in logins if f"twitch:{x}" not in _logos]
    for i in range(0, len(need), 100):
        j = _get("twitch", "https://api.twitch.tv/helix/users", [("login", x) for x in need[i:i + 100]])
        for u in j.get("data") or []:
            _logos[f"twitch:{u['login'].lower()}"] = u.get("profile_image_url") or ""


# ---------- Kick ----------

def _kick_row(slug, title, viewers, name="", category="", pic=""):
    slug = slug.lower()
    if pic:
        _logos[f"kick:{slug}"] = pic
    return {"vid": f"kick:{slug}", "channel_id": f"kick:{slug}", "channel": name or slug, "title": title or "",
            "viewers": int(viewers or 0), "category": category or "", "platform": "kick"}


def _kick_api_slugs(slugs) -> list:
    out = []
    for i in range(0, len(slugs), 50):
        j = _get("kick", "https://api.kick.com/public/v1/channels", [("slug", x) for x in slugs[i:i + 50]])
        for c in j.get("data") or []:
            st = c.get("stream") or {}
            if st.get("is_live"):
                out.append(_kick_row(c.get("slug") or "", c.get("stream_title"), st.get("viewer_count"),
                                     category=(c.get("category") or {}).get("name", "")))
    return out


def _kick_page(slug):
    """Unofficial public endpoint the kick.com site itself uses. None when offline."""
    r = _http.get(f"https://kick.com/api/v2/channels/{slug}", headers={"User-Agent": _UA, "Accept": "application/json"},
                  timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    j = r.json()
    ls = j.get("livestream") or {}
    pic = (j.get("user") or {}).get("profile_pic") or ""
    if pic:
        _logos[f"kick:{slug.lower()}"] = pic
    if not ls or ls.get("is_live") is False:
        return None
    cats = ls.get("categories") or []
    return _kick_row(j.get("slug") or slug, ls.get("session_title"), ls.get("viewer_count"),
                     name=(j.get("user") or {}).get("username") or "", category=cats[0].get("name", "") if cats else "",
                     pic=pic)


def _kick_slugs(slugs) -> list:
    if _keys("kick"):
        return _kick_api_slugs(slugs)
    from concurrent.futures import ThreadPoolExecutor
    out, errs = [], 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for r in pool.map(lambda s: _try(_kick_page, s), slugs):
            if r == "err":
                errs += 1
            elif r:
                out.append(r)
    if slugs and errs == len(slugs):
        raise RuntimeError("Kick channel pages refused every request (blocked); add KICK_CLIENT_ID/SECRET")
    return out


def _kick_category(name) -> list:
    if not _keys("kick"):
        return []            # category discovery needs the official API
    cid = _cats.get(("kick", name.lower()))
    if cid is None:
        c = _get("kick", "https://api.kick.com/public/v1/categories", {"q": name}).get("data") or []
        hit = next((x for x in c if (x.get("name") or "").lower() == name.lower()), c[0] if c else None)
        cid = _cats[("kick", name.lower())] = hit["id"] if hit else ""
    if not cid:
        return []
    j = _get("kick", "https://api.kick.com/public/v1/livestreams",
             {"category_id": cid, "sort": "viewer_count", "limit": 100})
    return [_kick_row(s.get("slug") or "", s.get("stream_title"), s.get("viewer_count"),
                      category=(s.get("category") or {}).get("name", ""), pic=s.get("profile_picture") or "")
            for s in j.get("data") or [] if s.get("slug")]


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"{fn.__name__} failed: {str(e)[:120]}")
        return "err"


# ---------- what events.py calls ----------

def _by_ids(p, ids) -> list:
    if not ids:
        return []
    if p == "twitch":
        if not _keys("twitch"):
            raise RuntimeError("Twitch needs TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env")
        return _tw_logins(ids)
    return _kick_slugs(ids)


def discover(ev: dict, preset: dict) -> list:
    """Every stream live now on the event's Kick/Twitch channels and categories. Each dict is shaped like a YouTube
    search result plus 'platform', 'official' (bool) and 'listed' (bool)."""
    out = {}
    for p in enabled(ev, preset):
        c = cfg(ev, preset, p)
        ids = list(dict.fromkeys(c["official"] + c["channels"]))
        try:
            for s in _by_ids(p, ids):
                out[s["vid"]] = s
        except Exception as e:
            print(f"{NAMES[p]} channel check failed: {str(e)[:150]}")
        if c["category"]:
            try:
                for s in (_tw_category if p == "twitch" else _kick_category)(c["category"]):
                    out.setdefault(s["vid"], s)
            except Exception as e:
                print(f"{NAMES[p]} category check failed: {str(e)[:150]}")
        if p == "twitch" and _keys("twitch"):
            try:
                _tw_logos([split(v)[1] for v in out if v.startswith("twitch:")])
            except Exception:
                pass
    for s in out.values():
        s["official"] = official(ev, preset, s["vid"])
        s["listed"] = listed(ev, preset, s["vid"])
    with _lock:
        for v, s in out.items():
            p = s["platform"]
            _known.setdefault(p, set()).add(v)
            snap = _snap.setdefault(p, {"ts": 0, "data": {}})
            snap["data"][v] = s
    return list(out.values())


def count(vid: str):
    """Current viewers for a Kick/Twitch id (None if not live). One batched request per platform every COUNT_TTL
    seconds covers every tracked channel, however often the live counter asks."""
    p, _ = split(vid)
    with _lock:
        snap = _snap.setdefault(p, {"ts": 0, "data": {}})
        _known.setdefault(p, set()).add(vid)
        if time.time() - snap["ts"] >= COUNT_TTL:
            ids = sorted(split(v)[1] for v in _known[p])
            rows = _by_ids(p, ids)            # raises on failure: the caller keeps the last good reading
            snap["data"] = {s["vid"]: s for s in rows}
            snap["ts"] = time.time()
        s = snap["data"].get(vid)
    return s["viewers"] if s else None


def forget(vid: str):
    with _lock:
        _known.get(platform_of(vid), set()).discard(vid)
