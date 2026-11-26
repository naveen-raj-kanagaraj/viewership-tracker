"""Who is watching the public dashboard: counts by a random per-tab id (no cookies). The IP address of each
visit is kept in memory for the owner's page (recent visitors) and dropped after 2 days; it is never written to disk.

Country comes from Cloudflare's CF-IPCountry header. Live = pinged in the last 75s (pages ping every 30s).
"""
import os
import threading
import time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from tracker import store

TZ = ZoneInfo("Asia/Kolkata")
ACTIVE_SEC = 75
_lock = threading.Lock()
_sess = {}            # sid -> {"first", "last", "country", "ref", "device", "day"}
_flush = {"ts": 0.0}
BOTS = ("bot", "crawl", "spider", "slurp", "preview", "headless", "facebookexternalhit", "whatsapp", "telegram")


def _day(ts=None):
    return datetime.fromtimestamp(ts or time.time(), TZ).strftime("%Y-%m-%d")


def hit(sid: str, country: str = "", ref: str = "", ua: str = "", width: int = 0, city: str = "", region: str = "",
        ip: str = "", _path: str = "", page: str = "", member: bool = False):
    sid = (sid or "")[:40]
    ua_l = (ua or "").lower()
    if not sid or any(b in ua_l for b in BOTS):
        return
    now = time.time()
    with _lock:
        s = _sess.get(sid)
        if not s:
            if len(_sess) > 300000:
                return
            device = "mobile" if ("mobi" in ua_l or (width and width < 700)) else "desktop"
            ref = (ref or "").lower().replace("www.", "")[:60] or "direct"
            if "letsgrowesports" in ref:
                ref = "direct"
            s = _sess[sid] = {"first": now, "last": now, "country": (country or "??").upper()[:2], "ref": ref,
                              "device": device, "day": _day(now), "city": (city or "")[:40], "region": (region or "")[:40],
                              "ip": (ip or "")[:64], "page": (page or "")[:80]}
        s["last"] = now
        if member:
            s["member"] = True                     # signed in (the site's lge_in cookie), sticky for the tab
        if page:
            s["page"] = page[:80]
        due = now - _flush["ts"] > 30
        if due:
            _flush["ts"] = now
            active = sum(1 for x in _sess.values() if now - x["last"] < ACTIVE_SEC)
            today = _day(now)
            todays = sum(1 for x in _sess.values() if x["day"] == today)
            members = sum(1 for x in _sess.values() if x["day"] == today and x.get("member"))
            for k in [k for k, x in _sess.items() if now - x["last"] > 2 * 86400]:   # forget old tabs
                _sess.pop(k, None)
    # Database writes outside the lock, at most every 30 s (20 Nov: they ran inside it on every hit, so the owner's
    # visitors page waited behind the tracker's database writes and the per-hit count of every session)
    if due:
        best = store.kv_get("visitors_peak", {}) or {}
        if active > best.get("n", 0):
            store.kv_set("visitors_peak", {"n": active, "ts": int(now)})
        hist = store.kv_get("visitors_days", {}) or {}
        hist[today] = max(hist.get(today, 0), todays)
        store.kv_set("visitors_days", dict(sorted(hist.items())[-60:]))
        mh = store.kv_get("visitors_member_days", {}) or {}
        mh[today] = max(mh.get(today, 0), members)
        store.kv_set("visitors_member_days", dict(sorted(mh.items())[-60:]))


def _pg(p: str) -> str:
    """A page as the owner reads it: the path without the query string."""
    p = (p or "").split("?")[0].split("#")[0]
    return p or "/"


def stats() -> dict:
    now = time.time()
    today = _day(now)
    with _lock:
        vals = list(_sess.values())
    act = [x for x in vals if now - x["last"] < ACTIVE_SEC]
    tod = [x for x in vals if x["day"] == today]
    return {"active": len(act), "today": max(len(tod), (store.kv_get("visitors_days", {}) or {}).get(today, 0)),
            "peak": store.kv_get("visitors_peak", {}) or {},
            "countries": Counter(x["country"] for x in tod).most_common(8),
            "refs": Counter(x["ref"] for x in tod).most_common(8),
            "devices": Counter(x["device"] for x in tod).most_common(),
            "active_countries": Counter(x["country"] for x in act).most_common(5),
            "places": Counter(", ".join(p for p in (x.get("city"), x.get("region")) if p) or "-" for x in tod).most_common(30),
            "active_places": Counter(", ".join(p for p in (x.get("city"), x.get("region")) if p) or "-" for x in act).most_common(15),
            "all_countries": Counter(x["country"] for x in tod).most_common(),
            "active_all_countries": Counter(x["country"] for x in act).most_common(),
            "avg_min": round(sum(x["last"] - x["first"] for x in tod) / len(tod) / 60, 1) if tod else 0,
            "days": store.kv_get("visitors_days", {}) or {}, "since": min((x["first"] for x in vals), default=now),
            "ips": Counter(x.get("ip") for x in tod if x.get("ip")).most_common(15),
            "active_members": sum(1 for x in act if x.get("member")), "today_members": sum(1 for x in tod if x.get("member")),
            "member_days": store.kv_get("visitors_member_days", {}) or {},
            "hours": Counter(datetime.fromtimestamp(x["first"], TZ).hour for x in tod),
            "pages_now": Counter(_pg(x.get("page")) for x in act).most_common(10),
            "pages_today": Counter(_pg(x.get("page")) for x in tod).most_common(12),
            "recent": [{k: x.get(k) for k in ("ip", "country", "city", "region", "device", "ref", "page", "first", "last")}
                       for x in sorted(vals, key=lambda x: -x["last"])[:150]]}


def summary() -> str:
    s = stats()
    pk = s["peak"]
    when = datetime.fromtimestamp(pk["ts"], TZ).strftime("%d %b, %I:%M %p IST") if pk.get("ts") else "-"
    fmtc = lambda pairs: ", ".join(f"{k} {v}" for k, v in pairs) or "-"
    lines = [f"Dashboard visitors ({(os.getenv('EVENT_PUBLIC_URL') or 'https://live.letsgrowesports.com').split('//')[-1]})",
             f"\nOn the page now: {s['active']}" + (f" ({fmtc(s['active_countries'])})" if s["active"] else ""),
             f"Visitors today (IST): {s['today']}",
             f"Most at once: {pk.get('n', 0)} at {when}",
             f"Average time on page today: {s['avg_min']} min",
             f"\nCountries today: {fmtc(s['countries'])}",
             f"Came from: {fmtc(s['refs'])}",
             f"Devices: {fmtc(s['devices'])}"]
    days = list(s["days"].items())[-7:]
    if len(days) > 1:
        lines.append("\nLast days: " + ", ".join(f"{d[5:]} {n}" for d, n in days))
    lines.append("\nCounted without cookies or IP addresses. A visitor = one browser tab session.")
    return "\n".join(lines)
