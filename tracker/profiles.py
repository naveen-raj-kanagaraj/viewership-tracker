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

SCHEMA = "CREATE TABLE IF NOT EXISTS ch_profile (sid TEXT PRIMARY KEY, bio TEXT, links TEXT, checked INTEGER)"
EVERY = 7 * 86400
_P = {}                   # sid -> (bio, links dict)
_L = threading.Lock()


def bio(sid: str) -> str:
    with _L:
        return (_P.get(sid) or ("", {}))[0]


def links(sid: str) -> dict:
    with _L:
        return dict((_P.get(sid) or ("", {}))[1])


def _db():
    with store._lock:
        store.main().execute(SCHEMA)
        store.main().commit()


def load():
    try:
        _db()
        with store.reading():
            rows = store.conn().execute("SELECT sid, bio, links FROM ch_profile").fetchall()
        with _L:
            for sid, b, l in rows:
                try:
                    _P[sid] = (b or "", json.loads(l or "{}"))
                except ValueError:
                    _P[sid] = (b or "", {})
    except Exception as e:
        print(f"Profiles load: {str(e)[:100]}")


def _twitch(logins: list) -> dict:
    from tracker import platforms
    out = {}
    for i in range(0, len(logins), 100):
        j = platforms._get("twitch", "https://api.twitch.tv/helix/users", [("login", x) for x in logins[i:i + 100]])
        for u in j.get("data") or []:
            out["twitch:" + u["login"].lower()] = (u.get("description") or "", {})
    return out


def _kick(slugs: list) -> dict:
    from tracker import platforms, ytextra
    out = {}
    for i in range(0, len(slugs), 50):
        try:
            j = platforms._get("kick", "https://api.kick.com/public/v1/channels", [("slug", x) for x in slugs[i:i + 50]])
            for c in j.get("data") or []:
                out["kick:" + (c.get("slug") or "").lower()] = (c.get("channel_description") or "", {})
        except Exception as e:
            print(f"Kick profiles: {str(e)[:100]}")
    for s in slugs:                                   # kick.com's own JSON: the bio and social handles
        u = (ytextra.kick_info(s) or {}).get("user") or {}
        if u:
            b0, _ = out.get("kick:" + s, ("", {}))
            ln = {k: u.get(k) for k in ("instagram", "twitter", "youtube", "tiktok", "facebook", "discord") if u.get(k)}
            out["kick:" + s] = (" ".join(x for x in (b0, u.get("bio") or "") if x), ln)
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
    rows = [(sid, got.get(sid, ("", {}))[0], json.dumps(got.get(sid, ("", {}))[1]), now) for sid in sids]
    with _L:
        for sid, b, l, _ in rows:
            _P[sid] = (b, json.loads(l))
    store.write_slices("INSERT INTO ch_profile VALUES (?,?,?,?) ON CONFLICT(sid) DO UPDATE SET bio=excluded.bio, "
                       "links=excluded.links, checked=excluded.checked", rows, n=200)
    return len(got)


def due(limit: int = 400) -> list:
    """Channels that may be Indian whose profile is missing or a week old: flagged Indian, or live with a hint."""
    from tracker import scene
    with store.reading():
        c = store.conn()
        checked = dict(c.execute("SELECT sid, checked FROM ch_profile").fetchall())
        flagged = [r[0] for r in c.execute("SELECT sid FROM sc_channels WHERE platform IN ('kick','twitch') AND india=1 "
                                           "AND last_live > ?", (time.time() - 30 * 86400,))]
    with scene._lock:
        live = [sid for sid, x in scene._LIVE.items() if x["platform"] != "youtube" and x.get("india_hint")]
    want = list(dict.fromkeys(live + flagged))
    return [s for s in want if time.time() - (checked.get(s) or 0) > EVERY][:limit]


def run_forever():
    load()
    time.sleep(120)
    while True:
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
