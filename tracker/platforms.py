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

NAMES = {"youtube": "YouTube", "kick": "Kick", "twitch": "Twitch", "tiktok": "TikTok"}
OTHER = ("kick", "twitch", "tiktok")
# Re-read Kick/Twitch counts this often (one batched request per platform covers every stream). The platforms
# themselves refresh a stream's viewer count roughly every 30-60s, so most 2s readings repeat the last value.
COUNT_TTL = float(os.getenv("PLATFORM_COUNT_SEC", "2"))
# TikTok: one public room request per account (no batch call), so every 10 seconds is plenty (TikTok refreshes its
# live viewer count about that often).
TTL = {"tiktok": float(os.getenv("TIKTOK_COUNT_SEC", "10"))}
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
    return (p, rest) if sep and p in OTHER else ("youtube", vid)


def platform_of(vid: str) -> str:
    return split(vid)[0]


def is_other(vid: str) -> bool:
    return platform_of(vid) != "youtube"


def link(vid: str) -> str:
    p, x = split(vid)
    return {"kick": f"https://kick.com/{x}", "twitch": f"https://www.twitch.tv/{x}",
            "tiktok": f"https://www.tiktok.com/@{x}/live"}.get(p, f"https://youtu.be/{vid}")


def logo(cid: str) -> str:
    return _logos.get(cid, "")


def cfg(ev: dict, preset: dict, platform: str) -> dict:
    c = ev.get(platform) or preset.get(platform) or {}
    return {"official": [x.lower().lstrip("@") for x in c.get("official", [])],
            "channels": [x.lower().lstrip("@") for x in c.get("channels", [])],
            "category": c.get("category") or ""}     # one name or a list


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
    return [p for p in OTHER if any(cfg(ev, preset, p).values())]


def status() -> dict:
    """Which connectors can run (no secret values)."""
    return {"twitch": "official API" if _keys("twitch") else "needs TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET",
            "kick": "official API" if _keys("kick") else "public channel pages (no keys, unofficial)",
            "tiktok": "public live room data (no keys, unofficial; listed accounts only)"}


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


# ---------- the owner's Twitch login (read-only, no scopes) ----------
# Follower counts need a logged-in user's token on Twitch (an app token can't read them). The owner connects once at
# /admin/twitch-connect?key=...; the refresh token is kept in the private database (kv 'twitch_user'), never in git.

def twitch_user_token():
    """A user access token from the owner's connected Twitch account, refreshed when needed; None if not connected."""
    from tracker import store
    import json as _j
    t = _tok.get("twitch_user")
    if t and t[1] > time.time() + 60:
        return t[0]
    try:
        saved = _j.loads(store.kv_get("twitch_user") or "{}")
    except ValueError:
        saved = {}
    if not saved.get("refresh") or not _keys("twitch"):
        return None
    i, s = _keys("twitch")
    r = _http.post("https://id.twitch.tv/oauth2/token", data={"client_id": i, "client_secret": s, "grant_type": "refresh_token",
                                                               "refresh_token": saved["refresh"]}, timeout=10)
    if r.status_code != 200:
        print(f"Twitch login: refresh failed (HTTP {r.status_code}); reconnect at /admin/twitch-connect")
        return None
    j = r.json()
    store.kv_set("twitch_user", _j.dumps({**saved, "refresh": j.get("refresh_token") or saved["refresh"]}))
    _tok["twitch_user"] = (j["access_token"], time.time() + int(j.get("expires_in") or 3600))
    return j["access_token"]


def twitch_followers(user_id: str):
    """Total followers of a Twitch channel (needs the owner's connected login), or None."""
    tok = twitch_user_token()
    if not tok or not user_id:
        return None
    r = _http.get("https://api.twitch.tv/helix/channels/followers", params={"broadcaster_id": user_id, "first": 1},
                  headers={"Authorization": f"Bearer {tok}", "Client-Id": _keys("twitch")[0]}, timeout=10)
    if r.status_code == 401:
        _tok.pop("twitch_user", None)
        return None
    if r.status_code != 200:
        return None
    return r.json().get("total")


def _get(p, url, params):
    for attempt in (0, 1, 2):
        h = {"Authorization": f"Bearer {_token(p)}"}
        if p == "twitch":
            h["Client-Id"] = _keys(p)[0]
        r = _http.get(url, params=params, headers=h, timeout=10)
        if r.status_code == 401 and not attempt:
            _tok.pop(p, None)            # expired or revoked: fetch a new app token once
            continue
        if r.status_code == 429 and attempt < 2:   # Twitch's per-minute budget: wait for its reset, then try again
            try:
                wait = float((getattr(r, "headers", None) or {}).get("Ratelimit-Reset") or 0) - time.time()
            except ValueError:
                wait = 2
            time.sleep(min(15, max(1, wait)))
            continue
        if p == "twitch":                # nearly out of budget: slow down a little instead of being refused
            try:
                if int((getattr(r, "headers", None) or {}).get("Ratelimit-Remaining") or 999) < 40:
                    time.sleep(1)
            except ValueError:
                pass
        if r.status_code >= 400:          # keep the platform's own reason in the error (shown by scene probe)
            raise RuntimeError(f"HTTP {r.status_code} from {url.split('/')[2]}: {r.text[:160]}")
        return r.json()


# ---------- Twitch (Helix) ----------

def _tw_streams(params) -> list:
    return _tw_rows(_get("twitch", "https://api.twitch.tv/helix/streams", params))


def _tw_rows(j: dict) -> list:
    out = []
    for s in j.get("data") or []:
        if s.get("type") != "live":
            continue
        login = (s.get("user_login") or "").lower()
        out.append({"vid": f"twitch:{login}", "channel_id": f"twitch:{login}", "channel": s.get("user_name") or login,
                    "title": s.get("title") or "", "viewers": int(s.get("viewer_count") or 0),
                    "category": s.get("game_name") or "", "platform": "twitch", "language": s.get("language") or "",
                    "tags": " ".join(s.get("tags") or [])})
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

def _kick_row(slug, title, viewers, name="", category="", pic="", language="", uid=None, tags=None):
    slug = slug.lower()
    if pic:
        _logos[f"kick:{slug}"] = pic
    if uid:
        _kick_uid[f"kick:{slug}"] = uid
    return {"vid": f"kick:{slug}", "channel_id": f"kick:{slug}", "channel": name or slug, "title": title or "",
            "viewers": int(viewers or 0), "category": category or "", "platform": "kick", "language": language or "",
            "tags": " ".join(str(t_) for t_ in (tags or []) if isinstance(t_, str))}


def _kick_api_slugs(slugs) -> list:
    out = []
    for i in range(0, len(slugs), 50):
        j = _get("kick", "https://api.kick.com/public/v1/channels", [("slug", x) for x in slugs[i:i + 50]])
        for c in j.get("data") or []:
            st = c.get("stream") or {}
            if st.get("is_live"):
                out.append(_kick_row(c.get("slug") or "", c.get("stream_title"), st.get("viewer_count"),
                                     category=(c.get("category") or {}).get("name", ""),
                                     uid=c.get("broadcaster_user_id"), tags=st.get("custom_tags") or c.get("custom_tags")))
    return out


_kick_uid = {}            # kick:<slug> -> broadcaster user id (for profile pictures)
_logo_tried = set()


def kick_logos(vids):
    """Profile pictures for Kick channels that don't have one yet: official users endpoint (by user id), else the
    public channel page. Each channel is tried once per run."""
    need = [v for v in vids if v.startswith("kick:") and not _logos.get(v) and v not in _logo_tried]
    if not need:
        return
    _logo_tried.update(need)
    ids = {_kick_uid[v]: v for v in need if _kick_uid.get(v)}
    if ids and _keys("kick"):
        try:
            for i in range(0, len(ids), 50):
                part = list(ids)[i:i + 50]
                j = _get("kick", "https://api.kick.com/public/v1/users", [("id", x) for x in part])
                for u in j.get("data") or []:
                    v = ids.get(u.get("user_id"))
                    if v and u.get("profile_picture"):
                        _logos[v] = u["profile_picture"]
        except Exception as e:
            print(f"Kick profile pictures failed: {str(e)[:120]}")
    for v in [v for v in need if not _logos.get(v)][:20]:
        try:
            _kick_page(split(v)[1])          # fills _logos from the public page when it isn't blocked
        except Exception:
            pass


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
                      category=(s.get("category") or {}).get("name", ""), pic=s.get("profile_picture") or "",
                      uid=s.get("broadcaster_user_id"))
            for s in j.get("data") or [] if s.get("slug")]


# ---------- TikTok ----------
# The public room data TikTok's own website reads for a profile's live badge (no login, no keys):
#   GET https://www.tiktok.com/api-live/user/room/?aid=1988&uniqueId=<handle>&sourceType=54
#   data.liveRoom.status 2 = live (4 = ended), data.liveRoom.liveRoomStats.userCount = watching now.
# Checked from the server on 28 Nov: 200 JSON (the /@handle/live page itself shows a captcha: not used). TikTok has no
# search for live streams without signing in, so only listed accounts are followed (live list "tiktok", presets).
_TT_H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/130.0.0.0 Safari/537.36", "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"}


def _tt_room(handle):
    """The account's live stream as a row, None when it isn't live; raises when TikTok refuses or changes."""
    r = _http.get("https://www.tiktok.com/api-live/user/room/", headers=_TT_H, timeout=10,
                  params={"aid": 1988, "app_language": "en", "app_name": "tiktok_web", "uniqueId": handle, "sourceType": 54})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from tiktok.com")
    j = r.json()                                   # not JSON (a captcha page): raises, the last reading is kept
    if j.get("statusCode") not in (0, None):
        if j.get("statusCode") == 19881007:         # user_not_found
            return None
        raise RuntimeError(f"TikTok {j.get('statusCode')}: {(j.get('message') or '')[:60]}")
    d = j.get("data") or {}
    u, lr = d.get("user") or {}, d.get("liveRoom") or {}
    pic = u.get("avatarThumb") or u.get("avatarMedium") or ""
    h = (u.get("uniqueId") or handle).lower()
    if pic:
        _logos[f"tiktok:{h}"] = pic
    if lr.get("status") != 2:
        return None
    return {"vid": f"tiktok:{h}", "channel_id": f"tiktok:{h}", "channel": u.get("nickname") or h,
            "title": lr.get("title") or "", "viewers": int((lr.get("liveRoomStats") or {}).get("userCount") or 0),
            "category": "", "platform": "tiktok", "language": "", "tags": "", "started": lr.get("startTime")}


def _tt_handles(handles) -> list:
    from concurrent.futures import ThreadPoolExecutor
    out, errs = [], 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for r in pool.map(lambda h: _try(_tt_room, h), handles):
            if r == "err":
                errs += 1
            elif r:
                out.append(r)
    if handles and errs == len(handles):
        raise RuntimeError("TikTok refused every request (blocked or changed)")
    return out


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
    if p == "tiktok":
        return _tt_handles(ids)
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
        for cat in ([c["category"]] if isinstance(c["category"], str) else c["category"]):
            if not cat or p == "tiktok":          # TikTok: listed accounts only
                continue
            try:
                for s in (_tw_category if p == "twitch" else _kick_category)(cat):
                    out.setdefault(s["vid"], s)
            except Exception as e:
                print(f"{NAMES[p]} category check failed: {str(e)[:150]}")
        if p == "twitch" and _keys("twitch"):
            try:
                _tw_logos([split(v)[1] for v in out if v.startswith("twitch:")])
            except Exception:
                pass
        if p == "kick":
            kick_logos([v for v in out if v.startswith("kick:")])
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
        if time.time() - snap["ts"] >= TTL.get(p, COUNT_TTL):
            ids = sorted(split(v)[1] for v in _known[p])
            rows = _by_ids(p, ids)            # raises on failure: the caller keeps the last good reading
            snap["data"] = {s["vid"]: s for s in rows}
            snap["ts"] = time.time()
        s = snap["data"].get(vid)
    return s["viewers"] if s else None


def forget(vid: str):
    with _lock:
        _known.get(platform_of(vid), set()).discard(vid)


_MULT = {"k": 1e3, "m": 1e6, "b": 1e9, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "l": 1e5, "crore": 1e7, "cr": 1e7,
         "thousand": 1e3, "million": 1e6, "billion": 1e9}


def parse_count(txt: str):
    """'10,560 watching' -> 10560, '10.5K watching' -> 10500, '1.2M' -> 1200000, '1.5 lakh' -> 150000.
    None if there is no number. (Stripping non-digits turned '10.56K' into 1056: never do that.)"""
    import re as _re
    t = (txt or "").lower().replace("\u00a0", " ").replace("\u202f", " ")
    m = _re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion|k|m|b|lakhs?|lac|l|crore|cr)?\b", t)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return int(round(n * _MULT.get(m.group(2) or "", 1)))


def is_abbrev(txt: str) -> bool:
    """True when the count is rounded ('10.5K', '1.2M', '1 lakh'), i.e. not the exact number."""
    import re as _re
    return bool(_re.search(r"\d\s*(k|m|b|lakhs?|lac|l|crore|cr)\b", (txt or "").lower()))
