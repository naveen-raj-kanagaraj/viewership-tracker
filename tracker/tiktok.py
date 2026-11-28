"""TikTok Live across the site (owner, 28 Nov: "track TikTok for all, not just PMGC, on the main pages too").

TikTok has no way to list live streams without signing in, so the site follows accounts it knows:
  - the official game accounts in SEED,
  - every TikTok account linked from a channel the site already follows (Kick / Twitch profiles, YouTube About links),
  - tracker/live/tiktok_scene.json {"add": [...], "remove": [...]} (read again when it changes, no restart).
Each account is checked through TikTok's public room data (platforms._tt_room): live ones about every minute, the rest
in turn, about two requests a second in all, on this thread only (pages read the result from memory, so nothing waits
on TikTok). TikTok is banned in India, so its streams are never counted as Indian (scene.india_why)."""
import json
import pathlib
import re
import threading
import time

from tracker import platforms, store

SEED = ["pubgmobile", "pubgmobileesports", "pubgmobilethailand", "pubgmobile.latam", "pubgmobile.esports.id",
        "pubgmobile.vng", "pubgmobile.esports.my", "pubgmobile_br"]
FILE = pathlib.Path(__file__).resolve().parent / "live" / "tiktok_scene.json"
RATE = 2.0            # requests a second at most
LIVE_EVERY = 60       # a live account is re-read this often (seconds)
FRESH = 240           # a reading older than this is not shown as live
_H = re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{2,24})", re.I)
_S = {"rows": {}, "seen": {}, "handles": [], "h_at": 0, "file_mt": None, "i": 0, "ok": 0, "err": 0, "last_err": "",
      "pause_until": 0, "started": 0}
_lock = threading.Lock()


def _clean(h: str) -> str:
    h = (h or "").strip()
    m = _H.search(h)
    if m:
        h = m.group(1)
    h = h.lstrip("@").split("?")[0].split("/")[0].lower()
    return h if re.fullmatch(r"[a-z0-9_.]{2,24}", h) else ""


def _file() -> dict:
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {}


def handles() -> list:
    """Every account to follow (refreshed every 30 minutes, or when the hand list changes)."""
    try:
        mt = FILE.stat().st_mtime if FILE.exists() else 0
    except OSError:
        mt = 0
    if _S["handles"] and time.time() - _S["h_at"] < 1800 and mt == _S["file_mt"]:
        return _S["handles"]
    f = _file()
    hs = [_clean(x) for x in SEED + list(f.get("add") or [])]
    try:
        with store.reading():
            c = store.conn()
            try:
                for (ln,) in c.execute("SELECT links FROM ch_profile WHERE links LIKE '%tiktok%'"):
                    try:
                        v = (json.loads(ln or "{}") or {}).get("tiktok")
                    except ValueError:
                        v = None
                    if v:
                        hs.append(_clean(str(v)))
            except Exception:
                pass
            for (v,) in c.execute("SELECT value FROM kv WHERE key LIKE 'ev_about:%' AND value LIKE '%tiktok.com/@%'"):
                hs += [_clean(m) for m in _H.findall(v or "")]
    except Exception as e:
        print(f"TikTok accounts: {str(e)[:120]}")
    drop = {_clean(x) for x in f.get("remove") or []}
    out = [h for h in dict.fromkeys(hs) if h and h not in drop]
    _S.update(handles=out, h_at=time.time(), file_mt=mt)
    return out


def _check(h: str):
    try:
        r = platforms._tt_room(h)
        _S["ok"] += 1
    except Exception as e:
        _S["err"] += 1
        _S["last_err"] = f"{h}: {str(e)[:100]}"
        if _S["err"] > 20 and _S["err"] > _S["ok"]:     # refused again and again: wait instead of hammering
            _S["pause_until"] = time.time() + 600
        return
    now = time.time()
    with _lock:
        _S["seen"][h] = now
        if r:
            r["at"] = now
            r["logo"] = platforms.logo(r["vid"])
            _S["rows"][h] = r
        else:
            _S["rows"].pop(h, None)


def loop():
    _S["started"] = time.time()
    time.sleep(40)
    while True:
        try:
            if time.time() < _S["pause_until"]:
                time.sleep(30)
                continue
            hs = handles()
            now = time.time()
            with _lock:
                live = [h for h in _S["rows"] if now - _S["seen"].get(h, 0) >= LIVE_EVERY]
            if live:                                   # live ones first, about every minute
                h = live[0]
            elif hs:                                   # the rest in turn
                h = hs[_S["i"] % len(hs)]
                _S["i"] += 1
            else:
                time.sleep(10)
                continue
            _check(h)
            time.sleep(1.0 / RATE)
        except Exception as e:
            print(f"TikTok loop: {str(e)[:150]}")
            time.sleep(5)


def rows() -> list:
    """TikTok streams live now (readings from the last few minutes)."""
    now = time.time()
    with _lock:
        return [dict(r) for r in _S["rows"].values() if now - r.get("at", 0) < FRESH]


def status() -> dict:
    return {"accounts": len(_S["handles"]), "live": len(rows()), "ok": _S["ok"], "errors": _S["err"],
            "last_error": _S["last_err"], "paused": _S["pause_until"] > time.time(),
            "round_min": round(len(_S["handles"]) / RATE / 60, 1)}


def start():
    threading.Thread(target=loop, daemon=True).start()
