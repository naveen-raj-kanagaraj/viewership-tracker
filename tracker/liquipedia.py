"""Which esports tournaments are on: Liquipedia's tournament lists (Upcoming / Ongoing / Completed), one page per game
wiki, read every 6 hours. Streams are matched to a tournament by its name in their titles (scene.tournament), so every
channel broadcasting or co-streaming it, in any country or language, counts towards one combined number.

Liquipedia content is CC-BY-SA 3.0; pages that use it link back to it. Their rules for automated reading: a
descriptive User-Agent, gzip, and no more than one page every 2 seconds (we read one every 4)."""
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from tracker import events, store

UA = "letsgrowesports-live/1.0 (https://live.letsgrowesports.com; live viewership tracker)"
EVERY = 6 * 3600
GAP = 4

# Liquipedia wiki -> (game name used on this site, other names the platforms use for it)
WIKIS = {
    "freefire": ("Free Fire", ["free fire", "garena free fire", "free fire max"]),
    "pubgmobile": ("PUBG Mobile", ["pubg mobile", "bgmi", "battlegrounds mobile india"]),
    "pubg": ("PUBG: Battlegrounds", ["pubg: battlegrounds", "pubg"]),
    "valorant": ("Valorant", ["valorant"]),
    "counterstrike": ("Counter-Strike 2", ["counter-strike", "counter-strike 2", "cs2"]),
    "dota2": ("Dota 2", ["dota 2"]),
    "leagueoflegends": ("League of Legends", ["league of legends"]),
    "wildrift": ("League of Legends: Wild Rift", ["wild rift"]),
    "mobilelegends": ("Mobile Legends", ["mobile legends", "mobile legends: bang bang", "mlbb"]),
    "rainbowsix": ("Rainbow Six Siege", ["rainbow six", "rainbow six siege", "tom clancy's rainbow six siege", "rainbow six siege x"]),
    "rocketleague": ("Rocket League", ["rocket league"]),
    "apexlegends": ("Apex Legends", ["apex legends"]),
    "callofduty": ("Call of Duty", ["call of duty", "cod mobile", "call of duty: warzone", "call of duty: black ops 7",
                                    "call of duty: black ops 6"]),
    "overwatch": ("Overwatch 2", ["overwatch", "overwatch 2"]),
    "fortnite": ("Fortnite", ["fortnite"]),
    "honorofkings": ("Honor of Kings", ["honor of kings"]),
    "marvelrivals": ("Marvel Rivals", ["marvel rivals"]),
    "easportsfc": ("EA Sports FC", ["ea sports fc", "ea sports fc 26", "ea sports fc 25", "fifa"]),
    "brawlstars": ("Brawl Stars", ["brawl stars"]),
    "clashroyale": ("Clash Royale", ["clash royale"]),
    "starcraft2": ("StarCraft II", ["starcraft ii", "starcraft 2"]),
    "deadlock": ("Deadlock", ["deadlock"]),
    "tft": ("Teamfight Tactics", ["teamfight tactics"]),
    "arenaofvalor": ("Arena of Valor", ["arena of valor"]),
    "fighters": ("Fighting games", ["street fighter 6", "tekken 8", "fatal fury", "mortal kombat 1", "2xko"]),
}
_BGMI = re.compile(r"\b(bgmi|bgis|bmps|bmsd|bmic|bmoc|battlegrounds mobile india)\b", re.I)
_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_LOCK = threading.Lock()


def _date(txt: str):
    """'Nov 06' (Liquipedia leaves out the year) -> the nearest date to today."""
    m = re.match(r"\s*([A-Za-z]{3})[a-z]*\s+(\d{1,2})(?:,?\s*(\d{4}))?", txt or "")
    if not m or m.group(1).lower() not in _MON:
        return None
    today = datetime.now(timezone.utc).date()
    mon, day = _MON[m.group(1).lower()], int(m.group(2))
    if m.group(3):
        years = [int(m.group(3))]
    else:
        years = [today.year - 1, today.year, today.year + 1]
    best = None
    for y in years:
        try:
            d = datetime(y, mon, day).date()
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.isoformat() if best else None


def parse(wiki: str, text: str) -> list:
    """The raw Liquipedia:Tournaments page -> [{id, wiki, game, page, name, full, series, status, start, end, url}]."""
    game, _ = WIKIS.get(wiki, (wiki, []))
    out, status = [], None
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("*") and not s.startswith("**"):
            w = s.lstrip("*").strip().lower()
            status = "upcoming" if w.startswith("upcoming") else "ongoing" if w.startswith("ongoing") else \
                "completed" if w.startswith("completed") else None
            continue
        if not s.startswith("**") or not status:
            continue
        parts = [p.strip() for p in s.lstrip("*").split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        page, name = parts[0], parts[1] or parts[0]
        kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
        full = re.sub(r"\s+", " ", page.replace("_", " ").replace("/", " ")).strip()
        series = page.split("/")[0].replace("_", " ").strip()
        g = "BGMI" if wiki == "pubgmobile" and (_BGMI.search(name) or _BGMI.search(full)) else game
        out.append({"id": f"{wiki}/{page}", "wiki": wiki, "game": g, "page": page, "name": name.strip(), "full": full,
                    "series": series, "status": status, "start": _date(kv.get("startdate", "")),
                    "end": _date(kv.get("enddate", "")) or _date(kv.get("startdate", "")),
                    "url": f"https://liquipedia.net/{wiki}/{page}"})
    return out


def fetch_once() -> int:
    """Read every wiki's tournament list (one page every GAP seconds). Keeps the last good list of a wiki that fails."""
    have = store.kv_get("lp_tours") or {}
    by_wiki = {}
    for t in have.get("tours", []):
        by_wiki.setdefault(t["wiki"], []).append(t)
    n = 0
    for wiki in WIKIS:
        try:
            r = events._http.get(f"https://liquipedia.net/{wiki}/Liquipedia:Tournaments", params={"action": "raw"},
                                 headers={"User-Agent": UA, "Accept-Encoding": "gzip"}, timeout=20)
            if r.status_code == 200 and "*" in r.text:
                by_wiki[wiki] = parse(wiki, r.text)
                n += 1
            else:
                print(f"Liquipedia {wiki}: HTTP {r.status_code}")
        except Exception as e:
            print(f"Liquipedia {wiki}: {str(e)[:100]}")
        time.sleep(GAP)
    tours = [t for w in by_wiki.values() for t in w]
    if tours:
        store.kv_set("lp_tours", {"ts": time.time(), "tours": tours})
        _CACHE["ts"] = 0
    return n


def loop():
    time.sleep(20)
    while True:
        have = store.kv_get("lp_tours") or {}
        if time.time() - (have.get("ts") or 0) > EVERY - 60:
            fetch_once()
        time.sleep(600)


_CACHE = {"ts": 0, "all": [], "active": []}


def tours() -> list:
    """Every tournament Liquipedia lists (upcoming, ongoing, recent), from the database, refreshed each minute."""
    if time.time() - _CACHE["ts"] > 60:
        with _LOCK:
            have = store.kv_get("lp_tours") or {}
            allt = have.get("tours") or []
            today = datetime.now(timezone.utc).date()
            act = []
            for t in allt:
                try:
                    s = datetime.fromisoformat(t["start"]).date() if t.get("start") else None
                    e = datetime.fromisoformat(t["end"]).date() if t.get("end") else s
                except ValueError:
                    continue
                if t["status"] == "ongoing" or s and e and s - timedelta(days=1) <= today <= e + timedelta(days=1):
                    act.append(t)
            _CACHE.update(ts=time.time(), all=allt, active=act)
    return _CACHE["all"]


def active() -> list:
    """Tournaments on now (Liquipedia's 'ongoing', or within a day of their dates): the ones streams are matched to."""
    tours()
    return _CACHE["active"]


def game_ok(t: dict, game: str) -> bool:
    """Can a stream filed under `game` be this tournament's broadcast? Unknown games ('', 'Other') can."""
    if not game or game in ("Other", "Other tournaments"):
        return True
    g = game.lower()
    if t["game"] == "BGMI":
        return g in ("bgmi", "pubg mobile")
    _, names = WIKIS.get(t["wiki"], ("", []))
    return g == t["game"].lower() or any(g == n or g.startswith(n) for n in names)


def start():
    threading.Thread(target=loop, daemon=True).start()
