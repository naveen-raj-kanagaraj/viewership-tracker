"""Can the server read live viewer counts from TikTok, Facebook, Loco and Rooter? (owner, 28 Nov: "track Facebook,
TikTok and other sites, not just YouTube, Kick and Twitch"; Esports Charts' PMGC peak includes Facebook and TikTok.)

Plain public page / JSON requests, the same a logged-out browser makes. Nothing is bypassed: a login wall, a
captcha or a refusal is recorded as such and that platform is not used. Results: kv 'plat_probe', /api/health
'platform_probe'. Runs at start and every 30 minutes."""
import re
import threading
import time

import requests

from tracker import store

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

CHECKS = [
    ("tiktok_room_api", "https://www.tiktok.com/api-live/user/room/?aid=1988&app_language=en&app_name=tiktok_web"
                        "&uniqueId=pubgmobile&sourceType=54", r'"liveRoom"|"status"'),
    ("tiktok_live_page", "https://www.tiktok.com/@pubgmobile/live", r"SIGI_STATE|liveRoomStats|__UNIVERSAL_DATA"),
    ("facebook_page", "https://www.facebook.com/PUBGMOBILE/", r'"pageID"|"userID"|PUBG MOBILE'),
    ("facebook_live_tab", "https://www.facebook.com/PUBGMOBILE/live_videos/", r"live_video|LiveVideo"),
    ("facebook_mobile", "https://m.facebook.com/PUBGMOBILE/", r"PUBG MOBILE"),
    ("loco_home", "https://loco.com/", r"__NEXT_DATA__|viewer"),
    ("rooter_home", "https://www.rooter.gg/", r"__NEXT_DATA__|viewer|live"),
]
WALL = re.compile(r"log ?in to facebook|you must log in|login_form|captcha|verify you are human|"
                  r"cf-chl|challenge-platform|access denied", re.I)


def probe() -> dict:
    out = {}
    for name, url, ok in CHECKS:
        t0 = time.time()
        try:
            r = requests.get(url, headers=H, timeout=12, allow_redirects=True)
            body = r.text or ""
            out[name] = {"http": r.status_code, "bytes": len(body), "ms": int((time.time() - t0) * 1000),
                         "final": r.url[:120], "marker": bool(re.search(ok, body)),
                         "wall": (WALL.search(body).group(0) if WALL.search(body) else ""),
                         "type": (r.headers.get("content-type") or "")[:40], "head": body[:160].replace("\n", " ")}
        except Exception as e:
            out[name] = {"error": str(e)[:160]}
    out["tiktok_handles"] = tiktok_handles()
    store.kv_set("plat_probe", {"ts": int(time.time()), "checks": out})
    return out


TT_CANDIDATES = ["pubgmobile", "pubgmobileesports", "pubgmobile.esports", "pubgmobile_esports", "pubgm.esports",
                 "pubgmobile.id", "pubgmobileid", "pubgmobile_id", "pubgmobileesports.id", "pubgmobile.vn", "pubgmobilevn",
                 "pubgmobilevietnam", "pubgmobile.th", "pubgmobileth", "pubgmobilethailand", "pubgmobile.mena",
                 "pubgmobilemena", "pubgmobile.arabia", "pubgmobilearabia", "pubgmobile.tr", "pubgmobiletr",
                 "pubgmobileturkiye", "pubgmobile.pk", "pubgmobilepk", "pubgmobilepakistan", "pubgmobile.my",
                 "pubgmobilemy", "pubgmobile.ph", "pubgmobileph", "pubgmobile.br", "pubgmobilebr", "pubgmobile.latam",
                 "pubgmobilelatam", "pubgmobile.ru", "pubgmobileru", "pubgmobile.jp", "pubgmobile.kr", "pmgc", "krafton",
                 "kraftonesports", "pubgmobile.esports.id", "pubgmobileesports.tr", "pubgmobile.esports.tr"]


def _keys(o, pre="", out=None, depth=0):
    out = [] if out is None else out
    if isinstance(o, dict) and depth < 4:
        for k, v in o.items():
            out.append(pre + k + (":" + str(v)[:40] if not isinstance(v, (dict, list)) else ""))
            _keys(v, pre + k + ".", out, depth + 1)
    return out


CAND_FILE = __import__("pathlib").Path(__file__).resolve().parent / "live" / "tiktok_check.json"


def _candidates() -> list:
    """Handles to check: tracker/live/tiktok_check.json {"check": [...]} (changes apply within a minute, no restart)."""
    try:
        import json as _j
        extra = [str(x).strip().lstrip("@").lower() for x in (_j.loads(CAND_FILE.read_text()).get("check") or []) if str(x).strip()]
    except Exception:
        extra = []
    return list(dict.fromkeys(extra or TT_CANDIDATES))


def tiktok_handles() -> dict:
    """Which candidate handles exist on TikTok, are live, and how many watch (the room JSON's shape kept once)."""
    res, shape = {}, None
    for h in _candidates():
        try:
            r = requests.get("https://www.tiktok.com/api-live/user/room/", headers=H, timeout=10,
                             params={"aid": 1988, "app_language": "en", "app_name": "tiktok_web", "uniqueId": h, "sourceType": 54})
            j = r.json()
            d = j.get("data") or {}
            u, lr = d.get("user") or {}, d.get("liveRoom") or {}
            if shape is None and u:
                shape = [k for k in _keys(d) if not k.startswith(("user.avatar", "liveRoom.coverUrl", "liveRoom.squareCoverImg"))][:120]
            if not u.get("uniqueId"):
                res[h] = "not found"
                continue
            res[h] = {"code": j.get("statusCode"), "msg": (j.get("message") or "")[:40], "exists": bool(u.get("uniqueId")),
                      "name": u.get("nickname") or "", "room": u.get("roomId") or "", "ustatus": u.get("status"),
                      "lstatus": lr.get("status"), "viewers": (lr.get("liveRoomStats") or {}).get("userCount"),
                      "title": (lr.get("title") or "")[:60]}
        except Exception as e:
            res[h] = {"error": str(e)[:80]}
        time.sleep(0.4)
    return {"handles": res, "shape": shape}


def loop():
    time.sleep(30)
    last, mt = 0, None
    while True:
        try:
            m = CAND_FILE.stat().st_mtime if CAND_FILE.exists() else 0
            if time.time() - last > 1800 or m != mt:
                last, mt = time.time(), m
                probe()
        except Exception as e:
            print(f"Platform probe: {str(e)[:150]}")
        time.sleep(60)


def start():
    threading.Thread(target=loop, daemon=True).start()
