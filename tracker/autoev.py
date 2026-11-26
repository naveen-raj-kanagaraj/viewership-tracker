"""Tournament trackers made automatically from Liquipedia.

Every 6 hours (right after the Liquipedia tournament lists are read) the ongoing and upcoming tournaments are
looked at. The ones that matter here get their own tracker at /e/<key>/, the same as a hand-made one (PMGC, CEGC):
  - games played in India (BGMI, PUBG Mobile, Free Fire, PUBG), starting within 2 days or on now, or
  - any other tournament Indian channels watched (5,000+ viewers at once in India in the last 3 days).
At most AUTO_MAX run at once (the biggest first), so the site's own scans never slow down.

Each tracker then follows the events.poll loop: off air it only checks the official channels (from the
tournament's Liquipedia page: its YouTube, Twitch and Kick links); once one goes live it searches YouTube, Kick
and Twitch (the game's categories) and the site-wide live scan for every other stream carrying it, and counts
all of them every 2 seconds. A tournament with no official channel listed is on air whenever the site's scan sees
streams of it. Streams belong to it when the site's tournament matcher (scene.tournament: its Liquipedia name,
short tag and series) names it in their title, so its numbers agree with its Esports category card.

Hand-made presets win: a tournament already tracked by one (same tag: 'PMGC 2026' -> pmgc) is skipped. The
trackers are kept in kv 'auto_presets' and merged into events.PRESETS at startup and after each check."""
import hashlib
import os
import re
import time
from datetime import date, timedelta

from tracker import events, store

AUTO_MAX = int(os.getenv("AUTO_EVENTS_MAX", "4"))
AUTO_ON = os.getenv("AUTO_EVENTS", "1") == "1"
IN_PEAK = int(os.getenv("AUTO_EVENTS_IN_PEAK", "5000"))
GAMES = {"BGMI", "PUBG Mobile", "Free Fire", "PUBG: Battlegrounds"}
CATS = {   # the game's category on Kick / Twitch (streams in it still need the tournament in their title)
    "BGMI": (["Battlegrounds Mobile India", "PUBG Mobile"], ["Battlegrounds Mobile India", "PUBG MOBILE"]),
    "PUBG Mobile": (["PUBG Mobile"], ["PUBG MOBILE"]),
    "Free Fire": (["Free Fire"], ["Garena Free Fire"]),
    "PUBG: Battlegrounds": (["PUBG: Battlegrounds"], ["PUBG: BATTLEGROUNDS"]),
    "Valorant": (["Valorant"], ["VALORANT"]),
    "Counter-Strike 2": (["Counter-Strike 2"], ["Counter-Strike"]),
    "Dota 2": (["Dota 2"], ["Dota 2"]),
    "League of Legends": (["League of Legends"], ["League of Legends"]),
    "Mobile Legends": (["Mobile Legends: Bang Bang"], ["Mobile Legends: Bang Bang"]),
    "Call of Duty": (["Call of Duty"], ["Call of Duty"]),
}
BASE = {k: v for k, v in events.PRESETS.items() if not v.get("lp")}   # the hand-made presets
_LAST = {"ts": 0}


def key_of(t: dict) -> str:
    sl = re.sub(r"[^a-z0-9]+", "-", t["name"].lower()).strip("-")[:12].strip("-")
    return f"lp-{sl}-{hashlib.md5(t['id'].encode()).hexdigest()[:4]}"


def load() -> dict:
    """Merge the stored automatic trackers into events.PRESETS (a new dict: readers never see it half-built)."""
    auto = store.kv_get("auto_presets") or {}
    for p in auto.values():
        p.pop("links", None)                    # made before 26 Nov carried a Liquipedia link
    events.PRESETS = {**auto, **BASE}
    return auto


def links(text: str) -> dict:
    """Official channels from a Liquipedia page's wikitext: |youtube= |twitch= |kick= (and youtube2=, twitch2= ...).
    Returns {'youtube': [UC id or @handle], 'twitch': [login], 'kick': [slug]}."""
    out = {"youtube": [], "twitch": [], "kick": []}
    for k, v in re.findall(r"^\s*\|\s*(youtube|twitch|kick)\d*\s*=\s*([^\n|}]+)", text or "", re.M | re.I):
        v = v.strip().strip("/")
        if not v:
            continue
        k = k.lower()
        if k == "youtube":
            m = re.search(r"(UC[\w-]{22})", v)
            h = m.group(1) if m else "@" + re.split(r"[/@]", v)[-1].strip()
            if len(h) > 1:
                out[k].append(h)
        else:
            x = re.split(r"/", v)[-1].strip().lower()
            if re.fullmatch(r"[a-z0-9_-]{2,40}", x):
                out[k].append(x)
    return {k: list(dict.fromkeys(v)) for k, v in out.items()}


def _page(t: dict) -> str:
    from tracker import liquipedia
    try:
        r = events._http.get(t["url"], params={"action": "raw"}, timeout=20,
                             headers={"User-Agent": liquipedia.UA, "Accept-Encoding": "gzip"})
        time.sleep(liquipedia.GAP)
        return r.text if r.status_code == 200 else ""
    except Exception as e:
        print(f"Liquipedia page {t['id']}: {str(e)[:100]}")
        return ""


def build(t: dict, page: str) -> dict:
    """A tracker preset for one Liquipedia tournament."""
    from tracker import scene
    name, game = t["name"], t["game"]
    if game == "PUBG Mobile" and re.search(r"\|\s*country\s*=\s*(India|IN)\b|\bBGMI\b|Battlegrounds Mobile India", page or "", re.I):
        game = "BGMI"                           # PUBG Mobile is banned in India: an Indian event on that wiki is BGMI
    tag = scene.tour_tag(name)
    short = next((nm for rx, nm, _ in scene._T_RX if rx.search(name)), None)
    off = links(page)
    k_cat, t_cat = CATS.get(game, ([], []))
    has_off = any(off.values())
    q = [name, f"{short or name} live", f"{short or name} watch party", f"{short or name} watchparty"]
    if t.get("series") and t["series"].lower() != name.lower():
        q.append(t["series"])
    return {
        "name": name, "game": game, "auto": True, "lp": t["id"], "tour": name, "tag": tag,
        "start": t.get("start"), "end": t.get("end"),
        "official_channels": off["youtube"],
        "official": [o.lower() for o in off["youtube"] if o.startswith("UC")],
        "kick": {"official": off["kick"], "category": k_cat},
        "twitch": {"official": off["twitch"], "category": t_cat},
        "official_title": True, "scene_world": True,
        "all_watch": has_off,                   # with an official broadcast every other stream is a co-stream
        "need_official": has_off,               # without one: on air whenever streams of it are live
        "match": [name.lower()], "queries": list(dict.fromkeys(q))[:6],
        "ended": False, "v": 2,                 # no links out: everything stays on the site (owner)
    }


def _india_peaks() -> dict:
    t3 = time.time() - 3 * 86400
    try:
        from tracker import scene
        with store.reading():
            return {n: p for n, p in scene._db().execute(
                "SELECT tour, peak FROM sc_tour WHERE region='in' AND last_ts>=?", (t3,))}
    except Exception:
        return {}


def candidates(tours: list, today: date, peaks: dict) -> list:
    """Tournaments that should have a tracker now, biggest first."""
    from tracker import scene
    taken = {scene.tour_tag(p.get("name") or k) for k, p in BASE.items()}
    out = []
    for t in tours:
        if t.get("status") not in ("ongoing", "upcoming"):
            continue
        try:
            s = date.fromisoformat(t["start"]) if t.get("start") else None
            e = date.fromisoformat(t["end"]) if t.get("end") else s
        except ValueError:
            continue
        if not s or s > today + timedelta(days=2) or (e and e < today):
            continue
        pk = peaks.get(t["name"], 0)
        if t["game"] not in GAMES and pk < IN_PEAK:
            continue
        if scene.tour_tag(t["name"]) in taken:
            continue                          # a hand-made tracker already follows it
        out.append((pk, t["game"] in GAMES, t))
    out.sort(key=lambda x: (-x[0], not x[1]))
    return [t for _, _, t in out]


def sync(force: bool = False) -> dict:
    """Create trackers for new tournaments, finish the ones whose dates are over. Cheap: local data, plus one
    Liquipedia page per new tracker."""
    if not AUTO_ON:
        return {}
    from tracker import liquipedia
    if not force and time.time() - _LAST["ts"] < 6 * 3600:
        return {}
    _LAST["ts"] = time.time()
    auto = load()
    today = date.today()
    changed, made, done = False, [], []
    for k, p in auto.items():                 # over (a day of slack for late finals)
        try:
            over = p.get("end") and date.fromisoformat(p["end"]) < today - timedelta(days=1)
        except ValueError:
            over = False
        if over and not p.get("ended"):
            p["ended"] = True
            changed = True
            done.append(p["name"])
    running = [k for k, p in auto.items() if not p.get("ended")]
    lp = {t["id"]: t for t in liquipedia.tours()}
    for k in running:                         # made before the BGMI check (26 Nov): read the page again once
        p = auto[k]
        if p.get("v") != 2 and p.get("lp") in lp:
            auto[k] = {**build(lp[p["lp"]], _page(lp[p["lp"]])), "start": p.get("start"), "end": p.get("end")}
            changed = True
    for t in candidates(liquipedia.tours(), today, _india_peaks()):
        if len(running) >= AUTO_MAX:
            break
        k = key_of(t)
        if k in auto:
            if not auto[k].get("ended") and k not in running:
                running.append(k)
            continue
        auto[k] = build(t, _page(t))
        running.append(k)
        made.append(t["name"])
        changed = True
    if changed:
        store.kv_set("auto_presets", auto)
        load()
        for k in [k for k in auto if auto[k]["name"] in made]:
            events.create(k)
    if made or done:
        print(f"Auto trackers: new {made or '-'}, finished {done or '-'}")
    return {"new": made, "finished": done, "running": running}
