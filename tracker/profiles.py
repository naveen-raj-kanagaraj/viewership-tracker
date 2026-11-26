"""Channel profiles: the bio and social links a Kick / Twitch streamer wrote about themselves, kept to decide who
is Indian (owner, 23 Nov: check their profiles, not just stream titles).

Twitch: the official API's user description. Kick: the official API's channel description, plus kick.com's own
channel JSON (bio and Instagram / X / YouTube / TikTok handles). Instagram and X themselves can't be read by a server
(they block it; X needs a paid API), so only the handles the streamer linked are kept, for the owner's manual checks.

Refreshed weekly for channels that may be Indian (flagged, hinted, or in the India rankings). Stored in ch_profile.
"""
import json
import re
import threading
import time

from tracker import store

SCHEMA = ("CREATE TABLE IF NOT EXISTS ch_profile (sid TEXT PRIMARY KEY, bio TEXT, links TEXT, checked INTEGER, "
          "followers INTEGER, gone INTEGER)")
EVERY = 7 * 86400
_P = {}                   # sid -> (bio, links dict)
_F = {}                   # sid -> (followers, gone)
_L = threading.Lock()


def bio(sid: str) -> str:
    with _L:
        return (_P.get(sid) or ("", {}))[0]


def links(sid: str) -> dict:
    with _L:
        return dict((_P.get(sid) or ("", {}))[1])


def _db():
    with store._lock:
        m = store.main()
        m.execute(SCHEMA)
        have = [r[1] for r in m.execute("PRAGMA table_info(ch_profile)")]
        for col in ("followers", "gone"):
            if col not in have:
                m.execute(f"ALTER TABLE ch_profile ADD COLUMN {col} INTEGER")
        m.commit()


def load():
    try:
        _db()
        with store.reading():
            rows = store.conn().execute("SELECT sid, bio, links, followers, COALESCE(gone,0) FROM ch_profile").fetchall()
        with _L:
            for sid, b, l, f, gone in rows:
                try:
                    _P[sid] = (b or "", json.loads(l or "{}"))
                except ValueError:
                    _P[sid] = (b or "", {})
                _F[sid] = (f, gone)
    except Exception as e:
        print(f"Profiles load: {str(e)[:100]}")


def _twitch(logins: list) -> dict:
    """sid -> (bio, links, followers, gone). A login Twitch no longer returns is banned or deleted (gone)."""
    from tracker import platforms
    out = {}
    for i in range(0, len(logins), 100):
        part = logins[i:i + 100]
        j = platforms._get("twitch", "https://api.twitch.tv/helix/users", [("login", x) for x in part])
        seen = set()
        for u in j.get("data") or []:
            lg = u["login"].lower()
            seen.add(lg)
            out["twitch:" + lg] = (u.get("description") or "", {}, platforms.twitch_followers(u.get("id")), 0)
        for lg in part:
            if lg.lower() not in seen:
                out["twitch:" + lg.lower()] = ("", {}, None, 1)
    return out


def _kick(slugs: list) -> dict:
    from tracker import platforms, ytextra
    out = {}
    for i in range(0, len(slugs), 50):
        try:
            j = platforms._get("kick", "https://api.kick.com/public/v1/channels", [("slug", x) for x in slugs[i:i + 50]])
            for c in j.get("data") or []:
                out["kick:" + (c.get("slug") or "").lower()] = (c.get("channel_description") or "", {}, None, 0)
        except Exception as e:
            print(f"Kick profiles: {str(e)[:100]}")
    for s in slugs:                                   # kick.com's own JSON: bio, social handles, followers
        ki = ytextra.kick_info(s) or {}
        u = ki.get("user") or {}
        if u:
            b0 = out.get("kick:" + s, ("", {}, None, 0))[0]
            ln = {k: u.get(k) for k in ("instagram", "twitter", "youtube", "tiktok", "facebook", "discord") if u.get(k)}
            f = ki.get("followers_count") or ki.get("followersCount")
            out["kick:" + s] = (" ".join(x for x in (b0, u.get("bio") or "") if x), ln, int(f) if f else None, 0)
    return out


def refresh(sids: list):
    tw = [s.split(":", 1)[1] for s in sids if s.startswith("twitch:")]
    kk = [s.split(":", 1)[1] for s in sids if s.startswith("kick:")]
    got = {}
    try:
        got.update(_twitch(tw))
    except Exception as e:
        print(f"Twitch profiles: {str(e)[:100]}")
    got.update(_kick(kk))
    now = int(time.time())
    rows = []
    for sid in sids:
        b, l, f, gone = got.get(sid, ("", {}, None, 0))
        rows.append((sid, b, json.dumps(l), now, f, gone))
    with _L:
        for sid, b, l, _, f, gone in rows:
            _P[sid] = (b, json.loads(l))
            _F[sid] = (f, gone)
    store.write_slices("INSERT INTO ch_profile (sid, bio, links, checked, followers, gone) VALUES (?,?,?,?,?,?) "
                       "ON CONFLICT(sid) DO UPDATE SET bio=excluded.bio, links=excluded.links, checked=excluded.checked, "
                       "followers=COALESCE(excluded.followers, ch_profile.followers), gone=excluded.gone", rows, n=200)
    return len(got)


def followers(sid: str):
    """(followers or None, gone 0/1)."""
    with _L:
        return _F.get(sid, (None, 0))


def due(limit: int = 400) -> list:
    """Channels that may be Indian whose profile is missing or a week old: flagged Indian, or live with a hint."""
    from tracker import scene
    with store.reading():
        c = store.conn()
        checked = {sid: (t if f is not None or g else min(t or 0, time.time() - EVERY + 6 * 3600))   # no follower count yet:
                   for sid, t, f, g in c.execute("SELECT sid, checked, followers, COALESCE(gone,0) FROM ch_profile")}   # retry in 6 h
        flagged = [r[0] for r in c.execute("SELECT sid FROM sc_channels WHERE platform IN ('kick','twitch') AND india=1 "
                                           "AND last_live > ?", (time.time() - 30 * 86400,))]
    with scene._lock:
        live = [sid for sid, x in scene._LIVE.items() if x["platform"] != "youtube" and x.get("india_hint")]
    want = list(dict.fromkeys(live + flagged))
    return [s for s in want if time.time() - (checked.get(s) or 0) > EVERY][:limit]


def logo_fill(limit: int = 1000) -> int:
    """Twitch / Kick channels seen live lately with no profile picture stored (25 Nov: Twitch rows showed initials):
    read them (Twitch: 100 per API call) and keep them in sc_channels, so boards and rankings have them too."""
    from tracker import platforms
    with store.reading():
        L = [r[0] for r in store.conn().execute(
            "SELECT sid FROM sc_channels WHERE platform IN ('twitch','kick') AND COALESCE(logo,'')='' AND last_live>? "
            "ORDER BY last_live DESC LIMIT ?", (time.time() - 14 * 86400, limit))]
    tw = [s.split(":", 1)[1] for s in L if s.startswith("twitch:")]
    if tw and platforms._keys("twitch"):
        try:
            platforms._tw_logos(tw)
        except Exception as e:
            print(f"Twitch logos: {str(e)[:100]}")
    kk = [s for s in L if s.startswith("kick:")]
    if kk:
        try:
            platforms.kick_logos(kk)
        except Exception as e:
            print(f"Kick logos: {str(e)[:100]}")
    rows = [(platforms.logo(s), s) for s in L if platforms.logo(s)]
    if rows:
        store.write_slices("UPDATE sc_channels SET logo=? WHERE sid=?", rows, n=200)
    return len(rows)


def run_forever():
    load()
    time.sleep(120)
    while True:
        try:
            n = logo_fill()
            if n:
                print(f"Logos: {n} Twitch / Kick profile pictures stored")
        except Exception as e:
            print(f"Logos: {str(e)[:150]}")
        try:
            todo = due()
            if todo:
                n = refresh(todo)
                print(f"Profiles: {n} of {len(todo)} Kick / Twitch profiles read")
        except Exception as e:
            print(f"Profiles: {str(e)[:150]}")
        time.sleep(1800)


def start():
    threading.Thread(target=run_forever, daemon=True, name="profiles").start()
