"""Manual decisions about channels, from the daily review (docs/DAILY_REVIEW.md): who is Indian or not, who is
blocked (viewbots, banned, fake, scams), and which category a channel belongs in.

They live in overrides.json in the GitHub repo, so a review only commits that file: the server re-reads it from
GitHub every 10 minutes (no deploy), keeps the last good copy in data/overrides.json, and falls back to the copy in
the code checkout. The rankings process reads the same local copy.

overrides.json:
  {"india": ["twitch:invadingdarkness"], "not_india": [...], "block": ["twitch:sazof36", ...],
   "category": {"yt:UC...": "Gaming"}, "reviewed": {"twitch:x": "2026-11-24"}, "notes": {"twitch:x": "why"}}
"""
import json
import os
import re
import threading
import time

from tracker import store

URL = os.getenv("OVERRIDES_URL",
                "https://raw.githubusercontent.com/naveen-raj-kanagaraj/viewership-tracker/main/overrides.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(os.path.dirname(os.path.abspath(store.DB_PATH)), "overrides.json")
_O = {"at": 0, "d": None}


def _norm(d: dict) -> dict:
    low = lambda xs: {str(x).strip().lower() if not str(x).startswith("yt:") else str(x).strip() for x in xs or []}
    return {"india": low(d.get("india")), "not_india": low(d.get("not_india")), "block": low(d.get("block")),
            "category": {(k if k.startswith("yt:") else k.lower()): v for k, v in (d.get("category") or {}).items() if v}}


def _read(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return _norm(json.load(f))
    except (OSError, ValueError):
        return None


def get() -> dict:
    if _O["d"] is None or time.time() - _O["at"] > 60:
        _O["d"] = _read(LOCAL) or _read(os.path.join(ROOT, "overrides.json")) or _norm({})
        _O["at"] = time.time()
    return _O["d"]


def india() -> set:
    return get()["india"]


def not_india() -> set:
    return get()["not_india"]


def blocked(sid: str) -> bool:
    return (sid if sid.startswith("yt:") else sid.lower()) in get()["block"]


def blocked_names() -> set:
    """Kick / Twitch logins of blocked channels, normalised like scene.name_blocked."""
    return {re.sub(r"[^a-z0-9]", "", s.split(":", 1)[1]) for s in get()["block"] if not s.startswith("yt:")}


def category(sid: str) -> str:
    return get()["category"].get(sid if sid.startswith("yt:") else sid.lower(), "")


def fetch() -> bool:
    """Pull the latest overrides.json from GitHub into data/overrides.json (only if it parses)."""
    from tracker import events
    try:
        r = events._http.get(URL, timeout=15, headers={"Cache-Control": "no-cache"})
        if r.status_code != 200:
            return False
        d = json.loads(r.text)
        if not isinstance(d, dict):
            return False
        tmp = LOCAL + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(r.text)
        os.replace(tmp, LOCAL)
        _O["at"] = 0
        return True
    except Exception as e:
        print(f"Overrides: {str(e)[:100]}")
        return False


def run_forever():
    while True:
        before = json.dumps({k: sorted(v) if isinstance(v, set) else v for k, v in get().items()}, sort_keys=True)
        if fetch():
            after = json.dumps({k: sorted(v) if isinstance(v, set) else v for k, v in get().items()}, sort_keys=True)
            if after != before:
                print("Overrides: new decisions loaded from GitHub")
                try:
                    from tracker import scene
                    scene._KNOWN["at"] = 0
                    threading.Thread(target=scene.mark_known_india, daemon=True).start()   # apply India flags now
                except Exception as e:
                    print(f"Overrides apply: {str(e)[:100]}")
        time.sleep(600)


def start():
    threading.Thread(target=run_forever, daemon=True, name="overrides").start()
