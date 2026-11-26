"""Which channels really carry PUBG Mobile / BGMI tournaments (owner, 26 Nov: "check the channels before the stream
goes live, and check chat only for channels that seem sus").

A YouTube channel is trusted when it has carried a PUBG Mobile or BGMI tournament before:
  1. this site's own trackers (BMSD, BMIC, PIC ...): a stream counted as a watch party (ev_streams),
  2. this site's tournament matcher: streams of PUBG Mobile / BGMI tournaments the live scan filed (sc_tour_ch),
  3. YouTube: past live streams ("Streamed ... ago") found by searching last year's and this year's events in each
     region's own words (PMGC 2025 / 2024 watch parties, nobar PMGC 2025, PMGC 2025 canli, PMWC, PMSL, PMPL, BGIS,
     BMPS ...), read before the broadcast and again once a day,
  4. a channel that shows up live and isn't known yet: its Live tab (its last ~30 past streams), read once.
Trusted channels skip the chat check (the title check still applies to everyone). A channel with no such history is
'new' (sus): events.run_chat_checks reads its chat, and it comes off the count if the chat is not about the match.
Kept in kv 'wp_trust' so a restart doesn't search again."""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from tracker import events, store

PAST_RX = re.compile(r"\bpm(gc|wc|sl|pl|co|nc|rc|ps|go|cl|jl|es|wi)\b|pmgc|pmwc|\bbgis\b|\bbgms\b|\bbmps\b|\bbmic\b|\bbmsd\b|"
                     r"\bbgmi\s*(series|showdown|pro|masters|invitational|championship|cup)|"
                     r"pubg\s*m(obile)?\s*(global|world|super\s*league|pro\s*league|national|club|champions|esports|invitational)|"
                     r"global\s*championship", re.I)
QUERIES = [("PMGC 2025 watch party", "IN"), ("PMGC 2025 watchparty", "IN"), ("PMGC 2025 live", "IN"),
           ("PMGC 2025 Grand Finals live", "US"), ("PMGC 2025 live", "US"), ("nobar PMGC 2025", "ID"), ("PMGC 2025", "ID"),
           ("PMGC 2025 canlı", "TR"), ("PMGC 2025 ao vivo", "BR"), ("PMGC 2025 en vivo", "MX"), ("PMGC 2025 مباشر", "SA"),
           ("PMGC 2025", "TH"), ("PMGC 2025", "VN"), ("PMGC 2025", "PK"), ("PMGC 2025", "NP"), ("PMGC 2025", "MN"),
           ("PMGC 2025", "BD"), ("PMGC 2025", "RU"), ("PMGC 2025", "MY"), ("PMGC 2025", "PH"), ("PMGC 2025", "UZ"),
           ("PMGC 2024 watch party", "IN"), ("PMGC 2024 live", "US"), ("PMWC 2026 live", "US"), ("PMWC 2025 watch party", "IN"),
           ("PMSL 2026 live", "ID"), ("PMSL 2026 live", "TR"), ("PMPL 2026 live", "PK"), ("PMNC 2026 live", "BD"),
           ("BGIS 2026 watch party", "IN"), ("BMPS 2026 watch party", "IN"), ("BGIS 2026 live", "IN"), ("BMPS 2026 live", "IN")]
_T = {"ch": {}, "checked": {}, "ts": 0}    # ch: {channel id: [name, why]}; checked: {channel id: [ts, trusted 0/1]}
_L = threading.Lock()
_DIRTY = [False]


def load():
    d = store.kv_get("wp_trust") or {}
    with _L:
        _T.update(ch=d.get("ch") or {}, checked=d.get("checked") or {}, ts=d.get("ts") or 0)


def save():
    with _L:
        d = {"ch": dict(_T["ch"]), "checked": dict(_T["checked"]), "ts": _T["ts"]}
        _DIRTY[0] = False
    store.kv_set("wp_trust", d)


def _add(cid: str, name: str, why: str):
    if not cid or not cid.startswith("UC"):
        return
    with _L:
        if cid not in _T["ch"]:
            _T["ch"][cid] = [name or "", why[:140]]
            _DIRTY[0] = True


def why(cid: str) -> str:
    x = _T["ch"].get(cid or "")
    return x[1] if x else ""


def status(cid: str) -> str:
    """'trusted', 'new' (checked: no PUBG Mobile / BGMI tournament before) or 'unchecked'."""
    if not cid:
        return "unchecked"
    if cid in _T["ch"]:
        return "trusted"
    c = _T["checked"].get(cid)
    return "new" if c else "unchecked"


def _from_db():
    """Sources 1 and 2: what this site already recorded."""
    n = 0
    try:
        from tracker import scene
        with store.reading():
            rows = list(events._db().execute(
                "SELECT event, channel_id, channel, title FROM ev_streams WHERE kind='watch party' AND channel_id LIKE 'UC%' "
                "AND event != 'pmgc'"))
            tours = list(scene._db().execute("SELECT DISTINCT tour, sid FROM sc_tour_ch WHERE sid LIKE 'yt:UC%'"))
        for ev, cid, name, title in rows:
            g = (events.PRESETS.get(ev) or {}).get("game") or ""
            if g in ("BGMI", "PUBG Mobile") or PAST_RX.search(title or ""):
                _add(cid, name, f"watch party of {(events.PRESETS.get(ev) or {}).get('name') or ev.upper()} on this site")
                n += 1
        for tour, sid in tours:
            if PAST_RX.search(tour or "") and not re.search(r"pmgc.*2026|2026.*pmgc", tour or "", re.I):
                _add(sid[3:], "", f"streamed {tour} (this site)")
                n += 1
    except Exception as e:
        print(f"Watch-party trust (database): {str(e)[:120]}")
    return n


def _from_lists():
    """The watch-party streamers listed by hand in the presets (always_check), once their @handle is resolved."""
    for p in events.PRESETS.values():
        if not p.get("verify"):
            continue
        for h in p.get("always_check") or []:
            cid = h if h.startswith("UC") else events._HANDLE.get(h)
            if cid and cid not in _T["ch"]:
                _add(cid, h, "listed watch-party streamer")


def _search_past(q: str, gl: str, pages: int = 2) -> list:
    """A plain YouTube search (not live-only): [{vid, channel, channel_id, title, when}]."""
    from tracker import scene
    hdr = {"User-Agent": events._UA, "Content-Type": "application/json", "Origin": "https://www.youtube.com"}
    url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
    r = events._http.post(url, json={"context": {"client": scene._itv(gl)}, "query": q}, headers=hdr, timeout=10)
    r.raise_for_status()
    j = r.json()
    items = scene._renderers(j)
    for _ in range(pages - 1):
        tok = scene._continuation(j)
        if not tok:
            break
        r = events._http.post(url, json={"context": {"client": scene._itv(gl)}, "continuation": tok}, headers=hdr, timeout=10)
        if r.status_code >= 400:
            break
        j = r.json()
        items += scene._renderers(j)
    out = []
    for v in items:
        by = (v.get("ownerText") or v.get("longBylineText") or v.get("shortBylineText") or {}).get("runs") or [{}]
        cid = ((by[0].get("navigationEndpoint") or {}).get("browseEndpoint") or {}).get("browseId", "")
        ued = v.get("upcomingEventData") or {}
        out.append({"vid": v.get("videoId") or "", "channel": by[0].get("text", ""), "channel_id": cid,
                    "title": scene._text(v.get("title")), "when": scene._text(v.get("publishedTimeText")),
                    "live": "watching" in scene._text(v.get("viewCountText")).lower(),
                    "upcoming": bool(ued), "start": int(ued.get("startTime") or 0) if str(ued.get("startTime") or "").isdigit() else 0})
    return out


def _official(cid: str) -> bool:
    return any(cid.lower() in [o.lower() for o in (p.get("official") or [])] for p in events.PRESETS.values())


def _from_youtube() -> int:
    """Source 3: past live streams of last year's / this year's events, every region."""
    n = 0

    def one(a):
        try:
            return _search_past(*a)
        except Exception:
            return []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for res in pool.map(one, QUERIES):
            for x in res:
                streamed = x["when"].lower().startswith("streamed") or x["live"]
                if x["channel_id"] and streamed and PAST_RX.search(x["title"]) and not _official(x["channel_id"]):
                    _add(x["channel_id"], x["channel"], f'streamed "{x["title"][:90]}" ({x["when"] or "live"})')
                    n += 1
    return n


def check_channel(cid: str, name: str = ""):
    """Source 4: a channel's own Live tab, once."""
    from tracker import ytextra
    try:
        past = ytextra._yt_past(cid, "streams")
    except Exception:
        return None
    hit = next((p for p in past if PAST_RX.search(p.get("title") or "")), None)
    if hit:
        _add(cid, name, f'streamed "{hit["title"][:90]}" ({hit.get("when") or "before"})')
    with _L:
        _T["checked"][cid] = [int(time.time()), 1 if hit else 0]
        _DIRTY[0] = True
    return bool(hit)


def build(force: bool = False):
    if not force and time.time() - (_T["ts"] or 0) < 20 * 3600 and _T["ch"]:
        return
    a = _from_db()
    b = _from_youtube()
    _T["ts"] = time.time()
    save()
    print(f"Watch-party trust: {len(_T['ch'])} channels ({a} from this site, {b} from YouTube searches)")


def _candidates() -> list:
    """Unknown channels that are live or scheduled (checked before they go live), biggest first."""
    out = []
    for key, live in list(events._LIVE.items()) + [(k, v) for k, v in list(events._SCHED.items())]:
        if not (events.PRESETS.get(key) or {}).get("verify"):
            continue
        for vid, s in list(live.items()):
            cid = s.get("channel_id") or ""
            if cid.startswith("UC") and s.get("kind") != "official" and status(cid) == "unchecked":
                out.append((int(s.get("viewers") or 0), cid, s.get("channel") or ""))
    out.sort(reverse=True)
    return list({c: (c, n) for _, c, n in out}.values())


def run():
    """Startup: load, build if a day old; then every 15 s check the Live tab of channels that showed up unknown."""
    try:
        load()
        build()
    except Exception as e:
        print(f"Watch-party trust: {str(e)[:150]}")
    while True:
        time.sleep(15)
        try:
            _from_lists()
            todo = _candidates()[:6]
            if todo:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    list(pool.map(lambda c: check_channel(*c), todo))
            if _DIRTY[0]:
                save()
            if time.time() - (_T["ts"] or 0) > 24 * 3600:
                _T["ts"] = time.time()            # once a day (the thread searches again)
                threading.Thread(target=build, args=(True,), daemon=True).start()
        except Exception as e:
            print(f"Watch-party trust loop: {str(e)[:150]}")
