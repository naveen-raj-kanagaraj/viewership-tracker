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
    store.kv_set("plat_probe", {"ts": int(time.time()), "checks": out})
    return out


def loop():
    time.sleep(30)
    while True:
        try:
            probe()
        except Exception as e:
            print(f"Platform probe: {str(e)[:150]}")
        time.sleep(1800)


def start():
    threading.Thread(target=loop, daemon=True).start()
