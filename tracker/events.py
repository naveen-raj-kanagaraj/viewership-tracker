"""Live viewership tracker for events (tournaments) across every YouTube stream: official broadcast, watch parties
and community streams. Esports-Charts-style numbers: peak viewers, average viewers, hours watched, airtime, per
day, per channel.

How it works, every POLL_SEC seconds while an event is active:
  1. YouTube live search for the event's phrases (yt-dlp, no API key): finds new streams and gives their current
     viewer counts.
  2. Streams seen recently but missing from search this time are checked directly, so a stream dropping in the
     search ranking isn't counted as zero.
  3. With YOUTUBE_API_KEY set, every known stream's count comes from the official API instead (more exact; 1 quota
     unit per 50 streams).
Each poll stores one sample per live stream and one total ("tick").
"""
import os
import pathlib
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests

from tracker import platforms, store

# A browser-exported cookies.txt at the repo root unblocks Instagram and age-gated streams.
COOKIES_FILE = pathlib.Path(__file__).resolve().parent.parent / "cookies.txt"

POLL_SEC = int(os.getenv("EVENT_POLL_SEC", "60"))          # discovery: search YouTube for new streams
FAST_SEC = float(os.getenv("EVENT_FAST_SEC", "2"))          # live counter: re-count live streams this often
MINOR_SEC = 30                                              # streams under MINOR_VIEWERS are re-counted less often
MINOR_VIEWERS = 50
ALL_FAST_MAX = int(os.getenv("EVENT_ALL_FAST_MAX", "150"))   # up to this many live streams, all every FAST_SEC
SAMPLE_EVERY = 30
ANOM_MIN = int(os.getenv("EVENT_ANOMALY_MIN", "2000"))      # a jump/drop this big ...
ANOM_PCT = float(os.getenv("EVENT_ANOMALY_PCT", "0.15"))    # ... and at least this share of the stream, within ~15s                                           # per-stream history is stored every 30s
_LIVE = {}      # event -> {vid: stream dict} from the latest discovery
_FAST = {}      # event -> {vid: {"viewers", "ts", "misses"}}
_FASTSTATE = {"method": "", "ok_ts": 0.0, "errors": 0}
_HIST = {}      # event -> {vid: deque[(ts, viewers)]} every live-counter reading (last ~3h), for streamer graphs
_MEMT = {}      # event -> deque[(ts, total, live, official, watch party, community)]: the last ~10 min of totals, in memory
_LASTSAMPLE = {}
_MEMROWS = {}   # event -> (ts, [stream rows with current viewers]) from the latest 2-second count
import queue as _queue
_WQ = _queue.Queue()    # database writes from the 2-second counter: done by one writer thread, so a busy write lock
                        # elsewhere (the site-wide scan storing 100,000 streams) never delays a count


def _writer():
    """Everything queued is written in one go under one hold of the write lock (26 Nov, PMGC Day 1: with 130 streams
    one write per 2-second reading fell behind by 15+ minutes while other work held the lock)."""
    while True:
        batch = [_WQ.get()]
        while len(batch) < 200:
            try:
                batch.append(_WQ.get_nowait())
            except _queue.Empty:
                break
        try:
            with store._lock:
                for fn in batch:
                    try:
                        fn()
                    except Exception as e:
                        print(f"Event write failed: {str(e)[:150]}")
        finally:
            for _ in batch:
                _WQ.task_done()
        if _WQ.qsize() > 300:
            print(f"Event writes behind: {_WQ.qsize()} queued")


def flush():
    """Wait until the 2-second counter's queued database writes are done (tests, shutdown)."""
    _WQ.join()


threading.Thread(target=_writer, daemon=True, name="event-writer").start()
_PKMEM = {}     # event -> {vid: highest viewers written to ev_streams}: only a new peak is written every 2 s
_BEST = {}      # event -> {"total"}: the peak whose make-up is stored (kv event_peak_break), without reading kv every 2 s
_ENDED = {}     # vid -> time the live counter saw it end (search results lag, so don't re-add it)
RECHECK_MIN = 15          # re-check streams seen live within this many minutes that vanished from search
MAX_DIRECT_CHECKS = 20
REPORT_TZ = ZoneInfo(os.getenv("EVENT_TZ", "Asia/Kolkata"))
LIVE_FILTER = "EgJAAQ%253D%253D"     # YouTube search filter: live now
WATCH_PARTY = re.compile(r"watch\s*-?\s*party|co-?\s*stream|watch\s*-?\s*along|reaction|reacting|live\s+react", re.I)

PRESETS = {
    "bmsd": {
        "name": "BMSD 2026",
        "game": "BGMI",
        # only these watch-party channels are permitted to restream; everyone else is ignored (with official channels kept)
        "allowed": ["dynamo", "bixi", "zgod", "neyoo", "mizo", "mrspike", "lolzz", "sharkshe", "mafianinja", "ruthless",
                    "rakazone", "ansh", "casetoo", "sheek", "ipreeet", "shreeman", "mortal", "vaadhiyaar", "regaltos",
                    "snax", "sriop", "neonxpawan", "pawanop", "ladypredator", "soulaman"],
        "videos_extra": ["kf7OYvjee_k"],        # specific streams to track (Soul Aman's finals stream)
        # checked directly every minute, even if search misses them
        "official_channels": ["UCugG6-k5QGbq_iDEPAnG4NQ"],   # KRAFTON INDIA ESPORTS: every live stream is tracked
        "always_check": ["@shreemanlegendliveofficial", "@Casetoolive", "@ShreemanLegend", "@VAADHIYAAR", "@SoulAman", "@DynamoGaming", "@TheBixiOP", "@ZGODGAMING", "@NEYOOGAMINGYT", "@MizoPlays", "@MrSpike", "@LoLzZzGaming",
                         "@SHARKSHE", "@MafiaNinja", "@ImRuthlessceopubg", "@RakaZoneGaming", "@AnshYT", "@casetooop",
                         "@thecasetoopapa", "@sheekgaming", "@IPREEET.69", "@MortaLyt", "@soulregaltos9810", "@SnaxGaming",
                         "@sriop-sr70", "@NEONXPAWANOP", "@LadyPredatorGaming", "@LadyPredator"],
        "ended": True,                          # tournament over: nothing is recorded, the site shows history + by day
        "next_start": None,
        "hist": ["BMSD", "26"],
        "roster": True,
        "match": ["bmsd", "bgmi showdown", "battlegrounds mobile india showdown", "battlegrounds mobile showdown",
                  "bgmi show down", "bm showdown"],
        "queries": ["BMSD", "BMSD 2026", "BGMI Showdown", "Battlegrounds Mobile India Showdown", "BMSD watch party"],
        "official": ["krafton india esports", "battlegrounds mobile india"],
        "links": {"Esports Charts (official numbers, all platforms)":
                  "https://escharts.com/tournaments/bgmi/battlegrounds-mobile-india-showdown-2026-bgmi"},
        "predict": True,                        # Predict & Win banner and pages belong to this event
    },
    "bmic": {
        "name": "BMIC 2026",
        "game": "BGMI",
        "home": True,                           # the event shown at / (every event also has its own page at /e/<key>/)
        "hist": ["BMIC", "26"],                 # its place in the BGMI history chart (series key, 2-digit year)
        "predict": True,                        # Predict & Win banner (tracker/predict.py, EVENT_KEY "bmic")
        "hero": "BMIC26",                       # key art + logo at the top of the page (static/eventlogos)
        "roster": True,                         # show the watch-party roster (ROSTERS["bmic"]) and send the NOT LIVE alert
        # Watch-party streamers for BMIC: none yet. Until the list is added only the official broadcast counts.
        # permitted watch parties (owner's list, 29 Oct): channel-name tokens; their channels are also checked
        # directly every minute (events.roster, handles found by search when not given)
        "allowed": ["snax", "mrspike", "soulaman", "bixi", "hrishav", "8bitbeg", "ipreeet", "ladypredator", "cyanide",
                    "manfster", "warriorislive", "ravensharp", "iflicks", "aaru", "mafianinja", "gamezo", "stone",
                    "juniorgaming", "engineer", "sriop", "lolzz", "shreeman"],
        "official_channels": ["UCugG6-k5QGbq_iDEPAnG4NQ"],   # KRAFTON INDIA ESPORTS: every live stream is tracked
        "always_check": ["@ShreemanLegend", "@LadyPredator"],   # second channels; the rest come from the roster
        "ended": True,                          # finished Sun 1 Nov 2026
        "next_start": None,       # IST; countdown until the official stream goes live
        "match": ["bmic", "bgmi international cup", "battlegrounds mobile india international cup",
                  "bgmi international championship", "bm international cup"],
        "queries": ["BMIC", "BMIC 2026", "BGMI International Cup", "Battlegrounds Mobile India International Cup",
                    "BMIC watch party"],
        "official": ["krafton india esports", "battlegrounds mobile india"],
    },
    "pic": {
        "name": "PIC 2026",                     # PUBG India Cup (PUBG: Battlegrounds, PC), KRAFTON India Esports
        "game": "PUBG: Battlegrounds",
        "auto": True,                           # created on startup; tracking began Day 2 (13 Nov 2026)
        "official_channels": ["UCugG6-k5QGbq_iDEPAnG4NQ"],   # KRAFTON INDIA ESPORTS: Hindi, English and map streams
        "allowed": [],                          # no watch parties listed yet: only the official broadcast counts
        "next_start": None,
        "match": ["pic 2026", "pic26", "pubg india cup"],
        "queries": ["PIC 2026", "PUBG India Cup", "PUBG India Cup 2026"],
        "official": ["krafton india esports"],
    },
    "cegc": {
        "name": "CEGC",
        "game": "BGMI",
        "hist": ["CEGC", "26"],                 # in the BGMI tournaments chart (owner, 20 Nov)
        "auto": True,                           # created on startup if missing (no command needed)
        "home": True,                           # the event at / while it runs
        # official broadcast on Kick (Sky Esports). Permitted watch parties (owner's list, 3 Nov) stream only on Kick.
        "kick": {"official": ["skyesports", "skyesports_2", "skyesports-2"],     # Sky Esports only (owner, 17 Nov)
                 # exact channels from the owner (3 Nov); Kick slugs use "-" where the URL shows "_"
                 "channels": ["cegc", "sheekgaming", "snaxgaming", "lolzzzgaming", "ravensharplive", "mazyislive", "soulaman",
                              "vaadhiyaar", "neyoo_gaming", "neyoo-gaming", "sharkshe", "shreemanlegend", "tagkiolmao",
                              "therawknee", "pardhan", "kushalmahajan", "mizo", "jabakumargaming", "vinogaminglive",
                              "mrspikeyt"]},
        "any_title": True,                      # the listed channels count whatever their stream title says
        # Owner, 17 Nov 2026: official = Sky Esports' channels only; every other stream carrying CEGC is a watch party,
        # listed or not, on Kick or YouTube. Unlisted ones are found in the site's live scan by their title.
        "all_watch": True,
        "scene_match": r"\bcegc\b|\bc e g c\b",
        "allowed": [],
        "ended": False,
        "next_start": "2026-11-03 13:30",       # IST; countdown until the broadcast goes live
        "match": ["cegc", "c e g c", "sky esports", "skyesports", "watch party", "watchparty", "watch along", "watchalong"],
        "queries": [],                          # no YouTube search (a Portuguese channel is also called CEGC)
        "official": ["sky esports"],
    },
    "pmgc": {
        "name": "PMGC 2026",                    # PUBG MOBILE Global Championship, Istanbul. Gauntlet 26-27 Nov (Team SouL
        "game": "PUBG Mobile",                  # plays), groups 29-30 Nov + 2-3 Dec, Last Chance 5-6 Dec, finals 11-13 Dec
        "auto": True,                           # created on startup; shows in Esports > tournaments while it runs
        # PUBG MOBILE's own channels (main English one + language/region channels): every live stream whose title names
        # the event is tracked and counted as official. Checked by channel every poll (found 25 Nov 2026).
        "official_channels": ["UCmeeY9kzNswUpbYyJntb3Aw",   # PUBG MOBILE Esports (@PUBGMOBILEEsports)
                              "UCTal2V5RbkPNUWUa2E6RPEA",   # PUBG MOBILE Esports Pakistan (Urdu)
                              "UCMus-ap67HdQVz_QMHtaxXw",   # PUBG MOBILE Esports South Asia
                              "UCvTg9BK7sRKwu1H9_VDPYIQ",   # PUBG MOBILE Esports MEA (Arabic)
                              "UCqFXoUdIMsNg_ZHb_zyuBew",   # PUBG MOBILE Esports NA
                              "UCBFhZyGQUIpvwcD_OGyT0XA",   # PUBG Mobile Esports Viet Nam
                              "UCtMMTyOYb20ZbYOBfsfQBOw",   # PUBG MOBILE Espor Turkiye
                              "UCkB_AwGXxPAKdahxGHpeC4Q",   # PUBG MOBILE Indonesia
                              "UCtXuFMDmBedKwy77VAZY8eg",   # PUBG MOBILE Thailand
                              "UCaLKRJaDrQhPb59lHslFmgA",   # PUBG MOBILE LATAM (Spanish)
                              "UCH2Wx7hyam0P5M6kbrzQwSQ"],  # PUBG MOBILE Brasil (Portuguese)
        # watch-party streamers, checked directly every poll even if YouTube search misses them. Indian ones found on
        # YouTube 25 Nov 2026 (watch parties of PMGC 2025 / other PUBG Mobile events), then other regions.
        "always_check": ["@SnaxGaming", "@LoLzZzGaming", "@NEYOOGAMINGYT", "@Jokerkihavelii", "@mrspike_gaming",
                         "@sheekgaming", "@ayogi", "@S8ULSID", "@EngineerYTGaming", "@sparkakhil1", "@crypto5775",
                         "@SoulAman", "@MortaLyt", "@DynamoGaming", "@TheBixiOP", "@ShreemanLegend", "@VAADHIYAAR",
                         "@MizoPlays", "@IPREEET.69", "@LadyPredatorGaming",
                         "UC27pyUnJTUyxe_z_0WxxNXw",    # Cr7 HORAA
                         "UCvkP3KlQJL1XcXKQLGK7DrA",    # SleepyyHORAA
                         "UCrhssMVNygNbAxDtFRIRzOg",    # SkyHORAA
                         "UCgA44b8KQQFC71Ma72tglRg",    # Xifan
                         "UC8Xqz9d9yD-Yp6E7I6gut9Q",    # RawalPINDIZ (Pakistan)
                         # live PMGC watch parties the searches missed on Day 1 (checked by hand, 26 Nov 17:15 IST)
                         "UCwFRGieumnh1MrM5F3D65Tg",    # SOUL Regaltos
                         "UCqNH56x9g4QYVpzmWTzqVYg",    # Dynamo Gaming
                         "UCpThfYzX13SYyK1znEI3bWg",    # Amya plays
                         "UCIljGW0RiiHml1DcY7eE62w",    # Kafan Gaming Official (Urdu)
                         "UCni34U-sGh9QB5UVo5INl2g",    # OSAL (Korea)
                         "UCTbETTu3HNzQaZSprwNMjGQ",    # SiNiSTER PLAYS
                         "UCztyilUG9uQ_0JK_ClEDCpg",    # NERXOxLive (Turkey)
                         "UC_osE0Pz8LGu76uC95NlOAQ",    # MAFIA_IS_LIVE
                         "UC5P0A2CuylcWNcsnAhOhsMg",    # DELTA pubgm
                         "UCDjKNAnpHrYQ5k8hPVhiq-g",    # ROBIN SA
                         "UC44sKYlN-IHlUy5MG-W-5lQ",    # DrChemist
                         "UCZBdYvW1sI0Ui6ZFmkD10-w",    # DOBBY IS LIVE
                         "UCKB8eEbP9JH4SWkBGKdKp1g",    # Anny Gaming
                         "UCzSSlpIMNlsEuCtrlxEhNuw"],   # SAVA GAMING (Pakistan)
        # PUBG MOBILE's own regional channels (YouTube, Twitch, Kick) are official broadcasts, not watch parties
        "official_rx": r"^(pubg\s*mobile|pubgm\b)|배틀그라운드\s*모바일|ببجي\s*موبايل",
        # the same Indian streamers on Kick (one API call): counted when the title names the event
        "kick": {"channels": ["snaxgaming", "sheekgaming", "lolzzzgaming", "soulaman", "neyoo_gaming", "neyoo-gaming",
                              "mrspikeyt", "vaadhiyaar", "shreemanlegend", "sharkshe", "mizo", "ravensharplive",
                              "mazyislive", "kushalmahajan", "ghatak", "mortal", "sinisterplayss", "mafianinja",
                              "deltapubgm", "engineerytgaming", "amigomvp", "3lok", "bloodthrust", "rohanmodhera",
                              "leovent18", "regaltos", "dynamo", "8bitthug", "lolzzzgaming"],
                 "category": ["PUBG Mobile", "Battlegrounds Mobile India"]},   # + every stream in these categories
        "twitch": {"category": ["PUBG MOBILE"]},  # titled with the event (Twitch: top 100 by viewers)
        # official PUBG MOBILE TikTok accounts that carried the Gauntlet (checked 28 Nov: their last lives were PMGC
        # Gauntlet Day 2); counted only while the title names PMGC. More: live list "tiktok".
        "tiktok": {"official": ["pubgmobile", "pubgmobileesports", "pubgmobilethailand", "pubgmobile.latam",
                                "pubgmobile.esports.id", "pubgmobile.vng", "pubgmobile.esports.my", "pubgmobile_br"]},
        "official_title": True,                 # official channels count only streams whose title names the event
        "verify": True,                         # a PMGC title is not enough: wp_check (gameplay, scrims, other games out)
        # worldwide: the same search from each region's YouTube, in its own words (nobar = watch party in Indonesian,
        # izle = watch in Turkish, ao vivo = live in Portuguese ...). All of them every poll in the first hour on air,
        # then four at a time in turn (each one about every 5 minutes)
        "world_queries": [("PMGC 2026", "ID"), ("nobar PMGC", "ID"), ("PMGC 2026", "MY"), ("PMGC 2026", "TH"),
                          ("PMGC 2026", "VN"), ("PMGC 2026 canlı", "TR"), ("PMGC izle", "TR"), ("PMGC 2026", "SA"),
                          ("PMGC مباشر", "AE"), ("PMGC 2026 ao vivo", "BR"), ("PMGC en vivo", "MX"), ("PMGC 2026", "PK"),
                          ("PMGC 2026", "NP"), ("PMGC 2026", "BD"), ("PMGC 2026", "MN"), ("PMGC 2026", "RU"),
                          ("PMGC 2026", "UZ"), ("PMGC 2026", "PH"), ("PMGC 2026", "US"), ("PMGC watch party", "US"),
                          ("PUBG Mobile Global Championship", "GB")],
        "scene_world": True,                    # worldwide YouTube from the site-wide scan too (not only Indian)
        "all_watch": True,                      # every non-official stream carrying it is a watch party
        "scene_match": r"\bpmgc\b|pubg mobile global championship|\bgc (league|gauntlet)\b|\b20\d\d gc (league|gauntlet|group|last chance|grand finals?)\b",
        "allowed": [],
        "ended": False,
        "next_start": "2026-11-26 17:00",       # IST (owner, 25 Nov); countdown until the official stream goes live
        "match": ["pmgc", "pubg mobile global championship", "pubgm global championship", "gc league", "gc gauntlet",
                  "2026 gc"],
        # the first four run every poll; the rest two at a time in turn (all of them in the first hour on air)
        "queries": ["PMGC 2026", "PMGC live", "PMGC watch party", "PUBG Mobile Global Championship",
                    "PMGC watchparty", "PMGC 2026 Gauntlet", "PMGC 2026 live stream", "PMGC Team SouL",
                    "GC League Gauntlet", "PMGC co stream"],
        "official": ["pubg mobile esports", "pubg mobile espor"] + [c.lower() for c in (
            "UCmeeY9kzNswUpbYyJntb3Aw", "UCTal2V5RbkPNUWUa2E6RPEA", "UCMus-ap67HdQVz_QMHtaxXw", "UCvTg9BK7sRKwu1H9_VDPYIQ",
            "UCqFXoUdIMsNg_ZHb_zyuBew", "UCBFhZyGQUIpvwcD_OGyT0XA", "UCtMMTyOYb20ZbYOBfsfQBOw", "UCkB_AwGXxPAKdahxGHpeC4Q",
            "UCtXuFMDmBedKwy77VAZY8eg", "UCaLKRJaDrQhPb59lHslFmgA", "UCH2Wx7hyam0P5M6kbrzQwSQ")],
    },
}


def yt_link(vid: str) -> str:
    """Watch link for any tracked stream (YouTube id, or kick:/twitch: id)."""
    return platforms.link(vid)


def preset(key: str) -> dict:
    """The event's preset, with the Kick / Twitch channels of its live list (tracker/live/<key>.json) added."""
    p = PRESETS.get(key or "", {})
    ll = live_list(key)
    if not (ll.get("kick") or ll.get("twitch") or ll.get("tiktok")):
        return p
    out = dict(p)
    for plat in ("kick", "twitch", "tiktok"):
        if ll.get(plat):
            c = dict(p.get(plat) or {})
            c["channels"] = list(dict.fromkeys(list(c.get("channels") or []) + [x.lower().lstrip("@") for x in ll[plat]]))
            out[plat] = c
    return out


# ---------- live lists (owner, 26 Nov: "update it while it runs, no restarts") ----------
# tracker/live/<event>.json: {"youtube": [UC id or @handle], "kick": [slug], "twitch": [login], "exclude": [video id,
# channel id, kick:slug / twitch:login], "count": [video or channel id counted without the checks]}. Read again whenever
# the file changes; autoupdate pulls commits that only touch tracker/live/ without restarting, so a watch party can be
# added or removed during a broadcast in about a minute.
LIVE_DIR = pathlib.Path(__file__).resolve().parent / "live"
_LL = {}        # event -> (checked at, mtime, dict)


def live_list(key: str) -> dict:
    if not key:
        return {}
    now = time.time()
    hit = _LL.get(key)
    if hit and now - hit[0] < 10:
        return hit[2]
    f = LIVE_DIR / f"{key}.json"
    try:
        mt = f.stat().st_mtime
    except OSError:
        _LL[key] = (now, 0, {})
        return {}
    if hit and hit[1] == mt:
        _LL[key] = (now, mt, hit[2])
        return hit[2]
    try:
        import json as _json
        d = _json.loads(f.read_text())
        d = {k: [str(x).strip() for x in (d.get(k) or []) if str(x).strip()]
             for k in ("youtube", "kick", "twitch", "tiktok", "exclude", "count", "india", "not_india", "import")}
        print(f"Live list {key}: " + ", ".join(f"{k} {len(v)}" for k, v in d.items()))
    except Exception as e:
        print(f"Live list {key}: {str(e)[:120]}")
        d = hit[2] if hit else {}
    _LL[key] = (now, mt, d)
    return d


SETTINGS = ("game", "need_official", "any_title", "official_only", "kick", "twitch")   # can live on the event itself (track.py new/kick/twitch)


def opt(ev: dict, name: str, default=None):
    """An event setting: the event's own value (set from the CLI), else its preset's."""
    if ev and name in ev:
        return ev[name]
    return preset((ev or {}).get("key")).get(name, default)


def need_official(ev: dict) -> bool:
    """Most events only record while the official broadcast is live. "need_official": False (say, a game category
    with no single broadcast) records whenever any of its streams is live."""
    return bool(opt(ev, "need_official", True))


# ---------- storage ----------

_SCHEMA_OK = {}


def _db():
    if _SCHEMA_OK.get(store.DB_PATH):
        return store.conn()
    with store._lock:
        _schema(store.main())
        _SCHEMA_OK[store.DB_PATH] = True
    return store.conn()


def _schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS ev_streams (event TEXT, vid TEXT, channel TEXT, channel_id TEXT, title TEXT, kind TEXT,
        first_seen REAL, last_seen REAL, peak INTEGER DEFAULT 0, peak_at REAL, PRIMARY KEY (event, vid));
    CREATE TABLE IF NOT EXISTS ev_samples (event TEXT, ts INTEGER, vid TEXT, viewers INTEGER);
    CREATE INDEX IF NOT EXISTS ev_samples_ix ON ev_samples(event, ts);
    CREATE TABLE IF NOT EXISTS ev_anomalies (event TEXT, ts INTEGER, vid TEXT, channel TEXT, kind TEXT, before INTEGER,
        after INTEGER, change INTEGER, pct REAL, seconds INTEGER);
    CREATE TABLE IF NOT EXISTS ev_fine (event TEXT, ts INTEGER, vid TEXT, viewers INTEGER);
    CREATE INDEX IF NOT EXISTS ev_fine_ix ON ev_fine(event, ts);
    CREATE TABLE IF NOT EXISTS ev_ticks (event TEXT, ts INTEGER, total INTEGER, live INTEGER, official INTEGER,
        watch INTEGER, community INTEGER, PRIMARY KEY (event, ts));
    """)
    if not _CLEANED[0]:
        _CLEANED[0] = True
        if not store.kv_get("ev_cegc_clean_v1"):    # 3 Nov: drop a Portuguese YouTube channel ("... CEGC") counted by mistake
            t0 = int(datetime(2026, 11, 3, 13, 0, tzinfo=REPORT_TZ).timestamp())
            for t in ("ev_samples", "ev_fine", "ev_anomalies", "ev_ticks"):
                c.execute(f"DELETE FROM {t} WHERE event='cegc' AND ts<?", (t0,))
            c.execute("DELETE FROM ev_streams WHERE event='cegc' AND vid NOT LIKE 'kick:%'")
            c.commit()
            store.kv_set("ev_cegc_clean_v1", 1)
        if not store.kv_get("ev_pmgc_clean_v1"):    # 26 Nov 06:53 IST: PUBG MOBILE Brasil's 'Power Camp' (another
            t0 = int(datetime(2026, 11, 26, 12, 0, tzinfo=REPORT_TZ).timestamp())   # show) was counted as PMGC
            for t in ("ev_samples", "ev_fine", "ev_anomalies", "ev_ticks"):
                c.execute(f"DELETE FROM {t} WHERE event='pmgc' AND ts<?", (t0,))
            c.execute("DELETE FROM ev_streams WHERE event='pmgc' AND first_seen<?", (t0,))
            c.commit()
            if (store.kv_get("event_peak_break:pmgc") or {}).get("ts", 0) < t0:
                store.kv_set("event_peak_break:pmgc", {})
            store.kv_set("ev_pmgc_clean_v1", 1)
    return c


_CLEANED = [False]


def backfill_pic_day1():
    """PIC 2026 tracking began on Day 2 (13 Nov). Day 1 (12 Nov, 6 pm to 11 pm IST) is added once from the site's own
    readings of KRAFTON INDIA ESPORTS (all its streams together, every 2 minutes, kept 3 days), so the tournament peak
    and day-by-day include it. Watch parties weren't followed that day, so it is official streams only."""
    if store.kv_get("pic_day1_v1") or not get("pic"):
        return
    t0 = int(datetime(2026, 11, 12, 17, 0, tzinfo=REPORT_TZ).timestamp())
    t1 = int(datetime(2026, 11, 13, 1, 0, tzinfo=REPORT_TZ).timestamp())
    try:
        from tracker import scene
        with store.reading():
            have = _db().execute("SELECT COUNT(*) FROM ev_ticks WHERE event='pic' AND ts BETWEEN ? AND ?", (t0, t1)).fetchone()[0]
            rows = scene._db().execute("""SELECT ts, MAX(viewers) FROM sc_samples WHERE sid='yt:UCugG6-k5QGbq_iDEPAnG4NQ'
                                          AND ts BETWEEN ? AND ? AND viewers>0 GROUP BY ts ORDER BY ts""", (t0, t1)).fetchall()
        if have or not rows:
            if have:
                store.kv_set("pic_day1_v1", True)
            return
        with store._lock:
            c = _db()
            c.executemany("INSERT OR IGNORE INTO ev_ticks VALUES ('pic',?,?,?,?,0,0)", [(ts, v, 3, v) for ts, v in rows])
            c.commit()
        store.kv_set("pic_day1_v1", True)
        print(f"PIC 2026 Day 1: {len(rows)} readings added, peak {max(v for _, v in rows)}")
    except Exception as e:
        print(f"PIC Day 1: {str(e)[:120]}")


def events() -> dict:
    evs = store.kv_get("events", {})
    for k, ev in evs.items():  # events created before a preset gained new fields get them
        for field, val in PRESETS.get(k, {}).items():
            if field == "links" and not ev.get("links"):
                ev["links"] = dict(val)
    return evs


def save_events(evs: dict):
    store.kv_set("events", evs)


def get(key: str = None):
    evs = events()
    if key:
        return evs.get(key.lower())
    active = [e for e in evs.values() if e.get("active")]
    live = [e for e in active if not PRESETS.get(e["key"], {}).get("ended")]   # a running event wins over a finished one
    home = store.kv_get("event_home") or next((e["key"] for e in live if preset(e["key"]).get("home")), None)
    if home and any(e["key"] == home for e in active):
        return evs[home]
    pick = live or active
    return pick[-1] if pick else (list(evs.values())[-1] if evs else None)


def create(key: str, name: str = None, match: list = None, queries: list = None, official: list = None) -> dict:
    key = re.sub(r"[^a-z0-9_-]", "", key.lower())[:20] or "event"
    preset = PRESETS.get(key, {})
    ev = {"key": key, "name": name or preset.get("name") or key.upper(),
          "match": [m.lower() for m in (match or preset.get("match") or [key])],
          "queries": queries or preset.get("queries") or [key],
          "official": [o.lower() for o in (official or preset.get("official") or [])],
          "links": dict(preset.get("links") or {}),
          "channels": [], "videos": [], "excluded": [], "active": True, "created": time.time()}
    evs = events()
    if key in evs:
        evs[key].update(active=True)
        ev = evs[key]
    else:
        evs[key] = ev
    save_events(evs)
    return ev


def update(key: str, **fields):
    evs = events()
    if key in evs:
        evs[key].update(fields)
        save_events(evs)


# ---------- fetching ----------

class _QuietLog:
    """yt-dlp prints "ERROR: ... is not currently live" for every offline channel checked; that's expected, not a fault.
    The caller still gets the exception and handles it."""
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _ydl(flat=True):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20, "logger": _QuietLog()}
    if flat:
        opts.update(extract_flat="in_playlist", playlistend=80)
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return yt_dlp.YoutubeDL(opts)


def search_live(query: str) -> list:
    """[{vid, title, channel, channel_id, viewers}] currently live for a search."""
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={LIVE_FILTER}"
    with _ydl() as y:
        info = y.extract_info(url, download=False)
    out = []
    for e in info.get("entries") or []:
        if not e or e.get("live_status") != "is_live" or not e.get("id") or e.get("concurrent_view_count") is None:
            continue  # only streams live right now with a live "watching" count
        out.append({"vid": e["id"], "title": e.get("title") or "", "channel": e.get("channel") or "",
                    "channel_id": e.get("channel_id") or "", "viewers": int(e.get("concurrent_view_count") or 0)})
    return out


def check_video(vid: str):
    """Direct check of one stream: dict if live now, else None."""
    with _ydl(flat=False) as y:
        i = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    if not i.get("is_live") or i.get("live_status") not in (None, "is_live"):
        return None
    return {"vid": vid, "title": i.get("title") or "", "channel": i.get("channel") or i.get("uploader") or "",
            "channel_id": i.get("channel_id") or "", "viewers": int(i.get("concurrent_view_count") or 0)}


def check_channel(handle: str):
    """A channel's current live stream, if any (@handle, channel URL or id)."""
    h = handle.strip()
    if h.startswith("http"):
        base = re.sub(r"/(live|streams|videos|featured)/?$", "", h.rstrip("/"))
    elif h.startswith("UC") and len(h) == 24:
        base = f"https://www.youtube.com/channel/{h}"
    else:
        base = f"https://www.youtube.com/@{h.lstrip('@')}"
    try:
        with _ydl(flat=False) as y:
            i = y.extract_info(base + "/live", download=False)
    except Exception:
        return None
    if not i.get("is_live"):
        return None
    return {"vid": i["id"], "title": i.get("title") or "", "channel": i.get("channel") or "",
            "channel_id": i.get("channel_id") or "", "viewers": int(i.get("concurrent_view_count") or 0)}


def channel_live_all(channel: str, limit: int = 8) -> list:
    """Every stream that is live right now on a channel (an official channel runs Hindi, English and map streams
    at once; /live only returns one of them)."""
    base = f"https://www.youtube.com/channel/{channel}" if channel.startswith("UC") else \
        f"https://www.youtube.com/@{channel.lstrip('@')}"
    with _ydl(flat=True) as y:
        info = y.extract_info(base + "/streams", download=False)
    out = []
    for e in (info.get("entries") or [])[:limit]:
        vid = e.get("id")
        if not vid or e.get("live_status") in ("was_live", "is_upcoming", "not_live", "post_live"):
            continue
        try:
            n = count_live(vid)
        except Exception:
            n = None
        if n is None:
            continue
        out.append({"vid": vid, "title": e.get("title") or "", "channel": info.get("channel") or info.get("uploader") or "",
                    "channel_id": info.get("channel_id") or (channel if channel.startswith("UC") else ""),
                    "viewers": int(n)})
    return out


def api_counts(vids: list) -> dict:
    """{vid: viewers or None if not live} from the YouTube Data API (needs YOUTUBE_API_KEY)."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key or not vids:
        return {}
    out = {}
    for i in range(0, len(vids), 50):
        r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                         params={"part": "liveStreamingDetails,snippet", "id": ",".join(vids[i:i + 50]), "key": key},
                         timeout=15)
        r.raise_for_status()
        for it in r.json().get("items", []):
            d = it.get("liveStreamingDetails") or {}
            live = d.get("actualStartTime") and not d.get("actualEndTime")
            out[it["id"]] = int(d["concurrentViewers"]) if live and d.get("concurrentViewers") else (0 if live else None)
    return out


# ---------- classification ----------

def _norm(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (x or "").lower())


def allowed_list(ev: dict) -> list:
    return ev.get("allowed") or PRESETS.get(ev.get("key", ""), {}).get("allowed") or []


def permitted(ev: dict, s: dict) -> bool:
    """With an allow-list: only official channels and the listed watch-party channels count."""
    if platforms.listed(ev, preset(ev.get("key")), s.get("vid", "")):
        return True                              # named in the event's Kick/Twitch config
    if s.get("vid") in PRESETS.get(ev.get("key", ""), {}).get("videos_extra", []):
        return True
    if opt(ev, "official_only"):                 # no watch parties permitted (yet): official channels only
        ch = s.get("channel", "").lower()
        return any(o and o in ch for o in ev.get("official", [])) or (s.get("channel_id") or "").lower() in ev.get("official", [])
    al = allowed_list(ev)
    if not al or s.get("vid") in PRESETS.get(ev.get("key", ""), {}).get("videos_extra", []):
        return True
    ch = s.get("channel", "").lower()
    if any(o and o in ch for o in ev.get("official", [])) or (s.get("channel_id") or "").lower() in ev.get("official", []):
        return True
    n = _norm(s.get("channel", ""))
    return any(_norm(a) in n for a in al)


def taken_off(key: str, s: dict) -> bool:
    """Taken off by hand (live list exclude: video id or channel id): off the leaderboards too, not only the count
    (owner, 26 Nov: Gamezo Tech is not a watch party; it still showed on Day 1's board from before it was taken off)."""
    ex = live_list(key).get("exclude") or []
    return bool(ex) and (s.get("vid") in ex or (s.get("channel_id") or "-") in ex)


def relevant(ev: dict, s: dict) -> bool:
    pr = PRESETS.get(ev.get("key", ""), {})
    if pr.get("kick_only") and not str(s.get("vid", "")).startswith("kick:"):
        return False                             # this event is on Kick only: nothing from YouTube or Twitch
    if not permitted(ev, s):
        return False
    if s["vid"] in ev.get("excluded", []) or (s.get("channel_id") and s["channel_id"] in ev.get("excluded", [])) \
            or s.get("channel", "").lower() in ev.get("excluded", []):
        return False
    ll = live_list(ev.get("key", ""))
    if ll.get("exclude") and (s["vid"] in ll["exclude"] or (s.get("channel_id") or "-") in ll["exclude"]):
        return False                             # taken off by hand (live list)
    if ll.get("count") and (s["vid"] in ll["count"] or (s.get("channel_id") or "-") in ll["count"]):
        return True
    if s["vid"] in ev.get("videos", []) + PRESETS.get(ev.get("key", ""), {}).get("videos_extra", []) or _forced_channel(ev, s):
        return True
    if pr.get("lp"):                             # someone playing the game who names the event is not broadcasting it
        from tracker import scene as _sc         # ('12 H DE FREE FIRE !! HOY FINAL FFWS', rank push, scrims ...)
        if _sc._T_NOT.search(s.get("title") or ""):
            return False
    if platforms.platform_of(s["vid"]) == "tiktok" and not any(m in f"{s.get('title', '')}".lower() for m in
                                                               set(ev["match"]) | {m.lower() for m in pr.get("match", [])}):
        return False                             # a TikTok account (official too) counts only while its title names the event
    if platforms.official(ev, preset(ev.get("key")), s["vid"]) or \
            (platforms.is_other(s["vid"]) and opt(ev, "any_title")):
        return True
    if not_live_coverage(ev, s.get("title", "")):
        return False                             # a replay, highlights, or last year's edition re-streamed
    text = f"{s.get('title', '')} {s.get('channel', '')}".lower()
    terms = set(ev["match"]) | {m.lower() for m in PRESETS.get(ev.get("key", ""), {}).get("match", [])}   # preset edits apply to existing events
    if any(m in text for m in terms):
        if pr.get("verify") and not _official_s(ev, s):
            why = wp_check(ev, s) or chat_says_no(ev, s)
            if why:
                _reject(ev, s, why)
                return False
        return True
    tour = opt(ev, "tour")                       # a tracker made from Liquipedia: the site's own tournament matcher
    if tour:
        try:
            from tracker import scene
            return scene.tournament(s.get("title", ""), s.get("category") or opt(ev, "game") or "") == tour
        except Exception:
            return False
    return False


# ---------- is it really a watch party? (owner, 26 Nov) ----------
# A title naming the event is not enough: some streamers put PMGC in the title, or only in its hashtags, while they
# play ranked, run custom rooms or scrims, talk predictions, or play another game. For presets with "verify" a stream
# that is not official counts only when its title names the event outside hashtags and nothing in it says it is
# something else; a title that says watch party / co-stream / watching (in the main languages) always counts.
# YouTube's game card, once read, must be PUBG Mobile / BGMI (or none). Official channels, and streams the owner
# counted by hand (admin page), skip the check. Rejected streams are kept for the admin page (_REJ).
WP_SAYS = re.compile(r"watch\s*-?\s*part(y|ies)|watch\s*-?\s*along|co-?\s*stream|\bwp\b|reaction|reacting|live\s*react|"
                     r"commentary|\bnobar\b|nonton\s*bareng|izliyoruz|\bizle\b|assistindo|reagindo|\bviendo\b|смотрим|"
                     r"xem\s+c[uù]ng|مشاهدة|بث\s*مشترك|dekh\s*(rahe|te|enge)|watching", re.I)
NOT_WP = re.compile(r"rank\s*push|\branked\b|gameplay|rush\s*game\s*play|\brushing\b|conqueror|ace\s*(master|dominator)|"
                    r"custom\s*rooms?|room\s*cards?|\bscrims?\b|\bt\.?d\.?m\b|classic\s*(match|games?)|solo\s*vs\s*squad|"
                    r"\b1\s*v\s*[234]\b|road\s*to\s*(pmgc|conq|ace|crown|top\s*\d)|play(ing)?\s+with\s+(subs|subscribers|viewers|fans|you)|"
                    r"\bgrind|podcast|tier\s*list|\bpreview\b|practice|bootcamp|24\s*[x/]\s*7|non-?stop|lo-?fi|free\s*fire|"
                    r"\bff\s*(max|live)\b|valorant|minecraft|\bgta\b|cod\s*mobile|\bcodm\b|fortnite|roblox|clash\s*(of|royale)|"
                    r"mobile\s*legends|\bmlbb\b|\bleaks?\b|\bclassic\b|shorts\s*live|#shorts", re.I)
GAME_OK = re.compile(r"pubg|battlegrounds", re.I)
# another game or show named next to the event: not a watch party even when the title also says "watch party"
# (owner, 28 Nov: "most streams are not doing watch party"; e.g. "PMGC AND BIGBOSS WATCHPARTY", "PMGC watch Party | LAST OF US")
OTHER_SHOW = re.compile(r"bigg?\s*boss|last\s*of\s*us|vanguard|뱅가드|upskill|\bffws\b|free\s*fire|valorant|\bgta\s*(v|5|6)\b|minecraft|"
                        r"\bcodm?\b|fortnite|roblox|mobile\s*legends|\bmlbb\b|rank\s*push|conqueror", re.I)
_REJ = {}       # event -> {vid: {channel, channel_id, title, viewers, why, ts}}: candidates the check left out (last hour)


def _official_s(ev: dict, s: dict) -> bool:
    offs = set(ev.get("official", [])) | set(PRESETS.get(ev.get("key", ""), {}).get("official", []))
    ch = (s.get("channel") or "").lower()
    orx = PRESETS.get(ev.get("key", ""), {}).get("official_rx")
    return bool(s.get("from_official")) or any(o and o in ch for o in offs) or (s.get("channel_id") or "").lower() in offs \
        or bool(orx and re.search(orx, ch.strip(), re.I))


def wp_check(ev: dict, s: dict) -> str:
    """'' when a stream that names the event is really carrying it, else why not (shown on the admin page)."""
    pr = PRESETS.get(ev.get("key", ""), {})
    if s.get("vid") in ev.get("videos", []) + pr.get("videos_extra", []) or _forced_channel(ev, s):
        return ""                                # counted by hand
    ti = s.get("title") or ""
    m = OTHER_SHOW.search(ti)
    if m:
        return f'the title also names "{m.group(0).strip()}"'
    if WP_SAYS.search(ti):
        return ""
    terms = set(ev.get("match") or []) | {m.lower() for m in pr.get("match", [])}
    bare = re.sub(r"#\S+", " ", ti).lower()
    if not any(m in bare for m in terms):
        return "the title names it only in hashtags or the channel name"
    m = NOT_WP.search(ti)
    if m:
        return f'the title says "{m.group(0).strip()}"'
    if not platforms.is_other(s.get("vid", "")):
        try:
            from tracker import scene
            g = scene._YCARD.get(s.get("vid", "")) or ""
        except Exception:
            g = ""
        if g and not GAME_OK.search(g):
            return f"YouTube shows the game as {g}"
    return ""


def _reject(ev: dict, s: dict, why: str):
    r = _REJ.setdefault(ev["key"], {})
    now = time.time()
    r[s["vid"]] = {"vid": s["vid"], "channel": s.get("channel") or "", "channel_id": s.get("channel_id") or "",
                   "title": s.get("title") or "", "viewers": int(s.get("viewers") or 0), "why": why, "ts": now}
    if len(r) > 400:
        for v in [v for v, x in r.items() if now - x["ts"] > 3600]:
            r.pop(v, None)


def _card_filter(ev: dict, found: dict):
    """YouTube's game card for new candidates (one watch page each, then cached): another game is not a watch party."""
    try:
        from tracker import scene
    except Exception:
        return
    yt = [v for v, s in found.items() if not platforms.is_other(v) and not _official_s(ev, s)
          and not WP_SAYS.search(s.get("title") or "")]
    yt = [v for v in yt if v not in ev.get("videos", []) and not _forced_channel(ev, found[v])]
    try:
        scene._card_get(yt[:10], 4)
    except Exception as e:
        print(f"{ev['key']}: game cards: {str(e)[:100]}")
    for v in yt:
        g = scene._YCARD.get(v) or ""
        if g and not GAME_OK.search(g):
            _reject(ev, found[v], f"YouTube shows the game as {g}")
            found.pop(v, None)


# ---------- the chat check (owner, 26 Nov: "read the chat", then "only for channels that seem sus") ----------
# In a real watch party the chat talks about the match: PMGC, the Gauntlet, team names, chicken dinners. A stream that
# only has PMGC in its title chats about room IDs, custom rooms, rank push, or nothing related. Only channels with no
# PUBG Mobile / BGMI tournament behind them (wptrust: 'new') are read; trusted ones are not. Their recent live chat
# (the chat popout page, as the Super Chat reader does; no API quota) every 3 minutes, the last 150 messages kept. It only ever takes a
# stream off: 40+ readable messages with no word about the event or any team, or 20+ with none and 3+ about rooms /
# IDs / rank push. Chats mostly in Arabic, Thai, Cyrillic, Devanagari or Bengali script are not judged (team names
# may be written in that script). Kick / Twitch: title check only.
CHAT_EVENT = re.compile(r"pmgc|gauntlet|global\s*champ|grand\s*finals?|\bfinals?\b|qualif|points?\s*table|leader\s*board|"
                        r"\bwwcd\b|chicken|dinner|istanbul|\bgc\b|\bpts\b|krafton|tencent|level\s*infinite|"
                        r"soul|mongol|aurora|\b4k\b|s2g|ikurd|kurd|gaming\s*stars|hustler|hatyara|wolves|\brow\b|x\s*force|"
                        r"rejects|all\s*gamers|red\s*force|\bns\b|sharper|thrive|ak\s*gold|falcons|alpha\s*7|vampire|\bihc\b|"
                        r"\bdrx\b|nigma|fluxo|talon|bigetron|\bbtr\b|stalwart|dplus|yoodo|regnum|\bteam\b", re.I)
CHAT_PLAY = re.compile(r"room\s*id|custom\s*room|\bid\s*(pass|do|de|bhej)|\bpass(word)?\b|rank\s*push|\buid\b|add\s*me|"
                       r"join\s*(me|kar)|squad\s*(me|mein|join)|\blobby\b|sensi(tivity)?\b|\btdm\b", re.I)
_OTHER_SCRIPT = re.compile(r"[؀-ۿ฀-๿Ѐ-ӿऀ-ॿঀ-৿᠀-᢯぀-ヿ一-鿿가-힯]")
_CHATV = {}     # vid -> {"seen": set of message ids, "msgs": deque[(hit, play, readable)], "ts", "verdict", "n", "hits", "err"}


def chat_judge(msgs) -> tuple:
    """('no' | 'yes' | '', readable messages, about the event, about rooms/IDs) from [(hit, play, readable)]."""
    rd = [m for m in msgs if m[2]]
    n, hits, play = len(rd), sum(1 for m in msgs if m[0]), sum(1 for m in rd if m[1])
    if hits >= 2:
        return "yes", n, hits, play
    if hits == 0 and (n >= 40 or (n >= 20 and play >= 3)):
        return "no", n, hits, play
    return "", n, hits, play


def chat_says_no(ev: dict, s: dict) -> str:
    st = _CHATV.get(s.get("vid", ""))
    if not st or st.get("verdict") != "no" or s.get("vid") in ev.get("videos", []) or _forced_channel(ev, s):
        return ""
    return f'the chat never mentions PMGC or a team ({st["n"]} messages read{", talk of rooms / IDs" if st.get("play") else ""})'


def _chat_texts(vid: str) -> list:
    from tracker import ytextra
    got = ytextra._chat_start(vid)
    out = []
    for a in got["actions"]:
        it = (a.get("addChatItemAction") or {}).get("item") or {}
        r = it.get("liveChatTextMessageRenderer") or it.get("liveChatPaidMessageRenderer")
        if r:
            out.append((r.get("id") or "", ytextra._text(r.get("message"))))
    return out


def _chat_check(key: str, vid: str):
    st = _CHATV.setdefault(vid, {"seen": set(), "msgs": deque(maxlen=150), "ts": 0, "verdict": "", "n": 0, "hits": 0})
    st["ts"] = time.time()
    try:
        texts = _chat_texts(vid)
        st.pop("err", None)
    except Exception as e:
        st["err"] = str(e)[:100]
        return
    for mid, t in texts:
        if not t or (mid and mid in st["seen"]):
            continue
        if mid:
            st["seen"].add(mid)
        st["msgs"].append((bool(CHAT_EVENT.search(t)), bool(CHAT_PLAY.search(t)),
                           bool(re.search(r"[A-Za-z]{2}", t)) and not _OTHER_SCRIPT.search(t)))
    if len(st["seen"]) > 2000:
        st["seen"] = set()
    st["verdict"], st["n"], st["hits"], st["play"] = chat_judge(st["msgs"])
    if st["verdict"] == "no":
        ev = events().get(key) or {}
        s = (_LIVE.get(key) or {}).get(vid)
        if s and not (vid in ev.get("videos", []) or _forced_channel(ev, s)):
            _reject(ev, s, chat_says_no(ev, s))
            (_LIVE.get(key) or {}).pop(vid, None)     # off the 2-second counter now
            (_FAST.get(key) or {}).pop(vid, None)


def chat_due(now: float = None) -> list:
    """[(viewers, event, vid)] of sus watch parties (wptrust 'new') whose chat is due: 3 min, 10 min once it is about
    the match. Trusted channels (carried PUBG Mobile / BGMI before) and ones whose history isn't read yet are skipped."""
    from tracker import wptrust
    now = now or time.time()
    due = []
    evs = events()
    for key, live in list(_LIVE.items()):
        pr = PRESETS.get(key, {})
        ev = evs.get(key)
        if not pr.get("verify") or not ev:
            continue
        for vid, s in list(live.items()):
            if platforms.is_other(vid) or s.get("kind") == "official" or _official_s(ev, s) \
                    or vid in ev.get("videos", []) or _forced_channel(ev, s):
                continue
            if wptrust.status(s.get("channel_id") or "") != "new":
                continue
            st = _CHATV.get(vid)
            if not st or now - st["ts"] > (600 if st.get("verdict") == "yes" else 180):
                due.append((int(s.get("viewers") or 0), key, vid))
    return sorted(due, reverse=True)


def run_chat_checks():
    """Every 15 s: the due sus watch parties, biggest first, 12 at a time."""
    while True:
        time.sleep(15)
        try:
            due = chat_due()
            if due:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(lambda d: _safe(_chat_check, d[1], d[2]), due[:6]))
            if len(_CHATV) > 3000:
                now = time.time()
                for v in [v for v, x in _CHATV.items() if now - x["ts"] > 6 * 3600]:
                    _CHATV.pop(v, None)
        except Exception as e:
            print(f"Chat check: {str(e)[:120]}")


# ---------- scheduled streams (owner, 26 Nov: "those with scheduled streams, add them now") ----------
# Most watch parties are scheduled on YouTube before they go live. A plain YouTube search (not live-only) lists them
# with their start time; the ones whose title passes the check are kept here and asked for their live count every
# poll, so each one is counted from its first live minute even when the live search ranks it low. Their channels'
# history is read before they start (wptrust). Searched on the first poll and every 5th poll from 3 hours before
# the start, and while on air.
_SCHED = {}     # event -> {vid: {vid, channel, channel_id, title, start, ts, viewers: 0}}
SCHED_MAX = 200


def _event_channels(key: str, now: float) -> list:
    """YouTube channels that carried this event in the last day (their next stream after a break is found by feed)."""
    hit = _ECH.get(key)
    if hit and now - hit[0] < 300:
        return hit[1]
    try:
        with store.reading():
            rows = [r[0] for r in _db().execute(
                "SELECT channel_id FROM ev_streams WHERE event=? AND last_seen>? AND channel_id LIKE 'UC%' AND kind!='official' "
                "GROUP BY channel_id ORDER BY MAX(peak) DESC LIMIT 120", (key, now - 86400))]
    except Exception:
        rows = []
    _ECH[key] = (now, rows)
    return rows


def _trusted_slice(pr: dict, n: int) -> list:
    """Channels with a PUBG Mobile / BGMI tournament behind them (wptrust), 30 a poll in turn."""
    if not pr.get("verify"):
        return []
    try:
        from tracker import wptrust
        ids = sorted(wptrust._T["ch"])
    except Exception:
        return []
    if not ids:
        return []
    k = (n * 10) % len(ids)
    return (ids[k:] + ids[:k])[:10]


_ECH = {}


def scheduled_search(ev: dict) -> int:
    from tracker import wptrust
    pr = PRESETS.get(ev["key"], {})
    qs = [(q, "IN") for q in (pr.get("queries") or ev.get("queries") or [])[:6]] + list(pr.get("world_queries") or [])
    now = time.time()
    sch = _SCHED.setdefault(ev["key"], {})
    n = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(lambda a: _safe(wptrust._search_past, a[0], a[1], 2), qs):
            for x in res or []:
                if not x.get("vid") or not x.get("upcoming") or x["vid"] in sch:
                    continue
                if x.get("start") and not (now - 3 * 3600 < x["start"] < now + 6 * 3600):
                    continue                    # another day's stream
                st = {"vid": x["vid"], "channel": x.get("channel") or "", "channel_id": x.get("channel_id") or "",
                      "title": x.get("title") or "", "viewers": 0}
                if _official_s(ev, st) or not relevant(ev, st):
                    continue                    # official channels are polled anyway; the title check applies
                sch[x["vid"]] = {**st, "start": x.get("start") or 0, "ts": now}
                n += 1
    for v in [v for v, x in sch.items() if x.get("start") and now - x["start"] > 3 * 3600]:
        sch.pop(v, None)                        # never went live
    while len(sch) > SCHED_MAX:
        sch.pop(next(iter(sch)))
    if n:
        print(f"{ev['key']}: {n} scheduled streams added ({len(sch)} waiting)")
    return n


def set_stream(key: str, vid: str, count: bool):
    """Admin: count a stream the check left out, or stop counting one (by video). Takes effect at once."""
    ev = events().get(key)
    if not ev or not vid:
        return False
    vids = [v for v in ev.get("videos", []) if v != vid]
    exc = [v for v in ev.get("excluded", []) if v != vid]
    if count:
        vids.append(vid)
        r = (_REJ.get(key) or {}).pop(vid, None)
        if r:                                   # back on the counter right away
            _LIVE.setdefault(key, {})[vid] = {**r, "kind": "watch party"}
    else:
        exc.append(vid)
        (_LIVE.get(key) or {}).pop(vid, None)
        (_FAST.get(key) or {}).pop(vid, None)
        (_SCHED.get(key) or {}).pop(vid, None)
    update(key, videos=vids, excluded=exc)
    return True


REPLAY = re.compile(r"\b(replay|re-?run|re-?telecast|rebroadcast|re-?stream of|highlights?|recap|full match|vod)\b", re.I)
_YEAR = re.compile(r"\b(20[1-3]\d)\b")


def not_live_coverage(ev: dict, title: str) -> bool:
    """A stream that is not this edition live: a replay or highlights, or a title naming another year only (a
    '2025 PMGC Grand Finals' loop during PMGC 2026). Counting those would repeat old matches as new viewers."""
    t = title or ""
    if REPLAY.search(t):
        return True
    y = re.findall(r"\b(20[2-3]\d)\b", f"{ev.get('name', '')} {opt(ev, 'tour') or ''}")
    if y:
        yrs = set(_YEAR.findall(t))
        if yrs and not (yrs & set(y)) and not yrs & {str(int(y[0]) + 1)}:   # 'PMGC 2026' only; 2026-27 seasons kept
            return True
    return False


def _forced_channel(ev, s) -> bool:
    chans = [c.lower().lstrip("@") for c in ev.get("channels", [])]
    return bool(s.get("channel_id") and s["channel_id"].lower() in chans) or s.get("channel", "").lower() in chans


def scene_matches(ev: dict) -> list:
    """Live streams in the site-wide scan (YouTube, Kick, Twitch) whose title names the event (preset "scene_match",
    a regex). YouTube ones must be Indian channels (a Portuguese church channel is also called CEGC)."""
    rx = PRESETS.get(ev.get("key", ""), {}).get("scene_match")
    tour = opt(ev, "tour")
    if not rx and not tour:
        return []
    world = bool(opt(ev, "scene_world"))
    try:
        from tracker import scene
        with scene._lock:
            items = [(sid, dict(x), dict(x.get("streams") or {})) for sid, x in scene._LIVE.items()]
    except Exception:
        return []
    out = []
    for sid, x, streams in items:
        ti = x.get("title") or ""
        if rx and not re.search(rx, ti, re.I):
            if not tour or scene.tournament(ti, x.get("game") or "") != tour:
                continue
        elif not rx and scene.tournament(ti, x.get("game") or "") != tour:
            continue
        if sid.startswith("yt:") and not x.get("india") and not world:
            continue
        for vid, v in streams.items():
            out.append({"vid": vid, "channel": x.get("name") or sid, "channel_id": sid[3:] if sid.startswith("yt:") else sid,
                        "title": x.get("title") or "", "viewers": int(v or 0)})
    return out


def relabel_once(ev: dict) -> int:
    """Stored streams of an automatic tracker get their kind again by kind_of (28 Nov: Liquipedia-listed creators had
    been stored as official). Once per event (kv ev_relabel:<key>)."""
    pr = PRESETS.get(ev.get("key", ""), {})
    flag = f"ev_relabel3:{ev['key']}"
    if not pr.get("official_strict") or store.kv_get(flag):
        return 0
    with store.reading():
        rows = _db().execute("SELECT vid, channel, channel_id, title, kind FROM ev_streams WHERE event=?", (ev["key"],)).fetchall()
    ch = [(kind_of(ev, {"vid": r[0], "channel": r[1], "channel_id": r[2], "title": r[3]}), ev["key"], r[0])
          for r in rows if r[4] in ("official", "watch party", "community")]
    ch = [c for c, r in zip(ch, rows) if c[0] != r[4]]
    if ch:
        with store._lock:
            c = _db()
            c.executemany("UPDATE ev_streams SET kind=? WHERE event=? AND vid=?", ch)
            c.commit()
        for k in [k for k in _DAYS if k[0] == ev["key"]]:
            _DAYS.pop(k, None)
    store.kv_set(flag, {"changed": len(ch), "ts": int(time.time())})
    print(f"Relabel {ev['key']}: {len(ch)} streams")
    return len(ch)


def kind_of(ev: dict, s: dict) -> str:
    pr = PRESETS.get(ev.get("key", ""), {})
    if pr.get("official_strict"):            # automatic trackers: official = the publisher's channels, by name only;
        orx = pr.get("official_rx")         # Liquipedia-listed creators and everyone else are watch parties
        if orx and re.search(orx, (s.get("channel") or "").strip(), re.I):
            return "official"
        return "watch party"
    if s.get("from_official") or platforms.official(ev, preset(ev.get("key")), s.get("vid", "")):
        return "official"
    orx = pr.get("official_rx")
    if orx and re.search(orx, (s.get("channel") or "").strip(), re.I):
        return "official"
    ch = s.get("channel", "").lower()
    if any(o and o in ch for o in ev.get("official", [])) or (s.get("channel_id") or "").lower() in ev.get("official", []):
        return "official"
    if allowed_list(ev) or opt(ev, "all_watch") or WATCH_PARTY.search(s.get("title", "")):
        return "watch party"
    return "community"


# ---------- one poll ----------

_ITV = {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": "IN"}
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) "
       "Version/17.0 Safari/605.1.15")
_http = requests.Session()

# YouTube Data API quota: every call this site makes is 1 unit (channels, videos, playlistItems lists). The daily
# allowance (10,000 by default, resets at midnight Pacific) is metered here so optional work (hourly readings,
# prefetching channel histories, the watch list) stops before the essential daily stats run out.
YT_QUOTA = int(os.getenv("YOUTUBE_QUOTA", "10000"))
_YTQ = {"day": "", "n": 0}
_http_get = _http.get


def _metered_get(url, *a, **k):
    if "googleapis.com/youtube/" in str(url):
        d = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
        if _YTQ["day"] != d:
            _YTQ.update(day=d, n=(store.kv_get("ytq") or {}).get(d, 0))
        _YTQ["n"] += 1
        if _YTQ["n"] % 25 == 0:
            try:
                store.kv_set("ytq", {d: _YTQ["n"]})
            except Exception:
                pass
    return _http_get(url, *a, **k)


_http.get = _metered_get


def yt_quota_left(share: float = 1.0) -> bool:
    """True while today's YouTube API use is below `share` of the daily allowance."""
    d = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    used = _YTQ["n"] if _YTQ["day"] == d else (store.kv_get("ytq") or {}).get(d, 0)
    return used < share * YT_QUOTA


_CL = {}       # vid -> (time, viewers): one live-counter reading shared by the site-wide counter and the trackers


def count_live(vid: str):
    """Current concurrent viewers from YouTube's live counter (what the player shows). None if not live.
    Raises if it can't be read (then the caller falls back to reading the page). A reading under 1.5 s old is
    reused: the site's 2-second counter and a tournament tracker counting the same stream make one request."""
    hit = _CL.get(vid)
    if hit and time.time() - hit[0] < 1.5:
        return hit[1]
    n = _count_live(vid)
    if len(_CL) > 20000:
        _CL.clear()
    _CL[vid] = (time.time(), n)
    return n


def _count_live(vid: str):
    r = _http.post("https://www.youtube.com/youtubei/v1/updated_metadata?prettyPrint=false",
                   json={"context": {"client": _ITV}, "videoId": vid},
                   headers={"User-Agent": _UA, "Content-Type": "application/json", "Origin": "https://www.youtube.com"},
                   timeout=6)
    r.raise_for_status()
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "videoViewCountRenderer" in o:
                found.append(o["videoViewCountRenderer"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(r.json())
    for vc in found:
        txt = (vc.get("viewCount") or {}).get("simpleText") or "".join(
            x.get("text", "") for x in (vc.get("viewCount") or {}).get("runs", []))
        # Only "N watching" is a live concurrent count. After a stream ends YouTube shows "N views" and
        # originalViewCount becomes TOTAL views (that's how 2.3M got in), so anything else = not live.
        if vc.get("isLive") is False or "watching" not in txt.lower():
            return None
        shown = platforms.parse_count(txt) or 0
        raw = vc.get("originalViewCount")
        # originalViewCount is the exact live count; trust it when it agrees with the text (which may be rounded:
        # "10.5K watching"). Agreement guards against it being total views after the stream ended.
        if raw is not None and str(raw).isdigit() and abs(int(raw) - shown) <= max(1000, shown * .1):
            return int(raw)
        return shown
    raise ValueError("no live counter in response")


def _count_one(vid: str):
    """Live counter first; if it has no 'watching' count (or fails), read the watch page before calling it ended.
    The counter sometimes stops answering for one big stream while the stream is still live."""
    if platforms.is_other(vid):                 # Kick / Twitch: one batched API call per platform covers every stream
        p = platforms.platform_of(vid)
        try:
            return vid, platforms.count(vid), f"{platforms.NAMES[p]} API"
        except Exception as e:
            print(f"{platforms.NAMES[p]} count failed for {vid}: {str(e)[:120]}")
            return vid, "err", ""
    said = False                                # the live counter answered and says not live ("N views")
    try:
        n = count_live(vid)
        if n:                                   # 0 / None: confirm on the watch page (cached 10s, it is slow)
            if len(_LASTC) > 20000:
                _LASTC.clear()
            _LASTC[vid] = (time.time(), n)
            return vid, n, "YouTube live counter"
        said = n is None
    except Exception:
        pass
    hit = _PAGE.get(vid)
    if hit and time.time() - hit[0] < 10:
        return vid, hit[1], "watch page (slower)"
    try:
        s = check_video(vid)
        v = (s["viewers"] or None) if s is not None else None
        if said and v:
            # Right after a stream ends the watch page can still say live, with the video's TOTAL views as the count
            # (PMGC Day 1: Snax 199,552, Cr7 HORAA 14,122 flat for 15 minutes after their streams ended). Once the
            # counter says "views", the page's number counts only when it is close to the last live count.
            last = _LASTC.get(vid)
            if not last or time.time() - last[0] > 600 or v > max(last[1] * 1.3, last[1] + 300):
                print(f"Ended: {vid} (counter says views; page shows {v}, last live count {last[1] if last else '-'})")
                v = None
        _PAGE[vid] = (time.time(), v)
        if v is None:
            print(f"Live counter and watch page show no viewers for {vid}")
        return vid, v, "watch page (slower)"
    except Exception as e:
        if said:                                # the counter says not live and the page can't say otherwise: ended
            _PAGE[vid] = (time.time(), None)
            return vid, None, "watch page (slower)"
        print(f"Watch page check failed for {vid}: {str(e)[:120]}")
        return vid, "err", ""


_LASTC = {}      # vid -> (time, viewers) of its last live-counter reading


_PAGE = {}
_INFLIGHT = {}   # vid -> count still running from an earlier tick
_JUMP = {}       # vid -> (ts, viewers) of an unconfirmed big jump from the watch page


_fast_pool = ThreadPoolExecutor(max_workers=24)
FAST_BUDGET = int(os.getenv("EVENT_FAST_BUDGET", "160"))   # YouTube live-counter requests per 2-second round, all trackers
_BUDGET = {"left": FAST_BUDGET}


def paused(key: str) -> bool:
    """Owner said the broadcast is over (kv event_stop:<key> = epoch): record nothing and show off-air until then,
    even if an official stream is still up (post-show, end screen)."""
    return bool(PRESETS.get(key, {}).get("ended")) or (store.kv_get(f"event_stop:{key}") or 0) > time.time()


OVER_PCT = float(os.getenv("EVENT_OVER_PCT", "0.10"))
OVER_MIN = 20000
_OFFPK = {}      # event -> [this broadcast's official peak, last time the broadcast was on]


def broadcast_over(key: str, official: int, now: float) -> bool:
    """The main official broadcast has ended: official viewers fell under 10% of this broadcast's official peak (once
    it passed 20,000). PMGC Day 1: the 136K English stream ended at 22:33 IST, a regional stream with 1,282 viewers
    kept the day 'on air' until 22:47 and watch parties that had moved on (LoLzZz: scrims) kept being counted.
    On Day 1 the official never fell under 24% of its peak before the end, so a break never stops the count.
    The peak comes from the last 3 hours of readings after a restart."""
    op = _OFFPK.get(key)
    if op is None:
        pk = 0
        try:
            with store.reading():
                pk = _db().execute("SELECT MAX(official) FROM ev_ticks WHERE event=? AND ts>?",
                                   (key, now - 3 * 3600)).fetchone()[0] or 0
        except Exception:
            pass
        op = _OFFPK[key] = [int(pk), now, False]
    if op[0] < OVER_MIN or official >= op[0] * OVER_PCT:
        op[0] = max(op[0], int(official))
        op[1], op[2] = now, False
        return False
    op[2] = True
    return True


# ---------- streams the event counter missed, filled in from the live scan ----------
# live list "import": [yt:UC id / kick:slug]. Owner, 28 Nov: MazyisLive's PMGC streams ("Global Championship Day 1",
# "GC DAY 1": no "PMGC" in the titles) were not counted, but the site-wide live scan has his readings (every few
# minutes). For every broadcast day that ended, the scan readings inside the broadcast window are copied into the
# event's readings, so the streamer is on the day boards, the share cards and the CSV. The totals (ev_ticks) are not
# changed. Once per streamer per day; where the counter has readings they stay (only the gaps are filled).
IMPORT_PAD = (1800, 600)
GAP = 300                      # a scan reading within 5 minutes of a counter reading is not needed       # from 30 minutes before the official stream to 10 minutes after it
_IMP_AT = {}


def broadcast_windows(key: str) -> list:
    """[(IST day, start, end)]: per day, the first official reading to the last one at 10% or more of that day's
    official peak (a regional stream's tail is not the broadcast)."""
    with store.reading():
        rows = _db().execute("SELECT ts, official FROM ev_ticks WHERE event=? AND official>0 ORDER BY ts", (key,)).fetchall()
    days = {}
    for ts, off in rows:
        d = datetime.fromtimestamp(ts, REPORT_TZ).strftime("%Y-%m-%d")
        days.setdefault(d, []).append((ts, off))
    out = []
    for d, xs in sorted(days.items()):
        pk = max(o for _, o in xs)
        out.append((d, xs[0][0], max(t for t, o in xs if o >= pk * OVER_PCT)))
    return out


def import_scan(key: str, now: float = None, force: bool = False) -> list:
    """Fills in the live list's "import" streamers from the scan; returns [(sid, day, readings)] imported."""
    sids = live_list(key).get("import") or []
    now = now or time.time()
    if not sids or (not force and now - _IMP_AT.get(key, 0) < 600):
        return []
    _IMP_AT[key] = now
    done = []
    for day, b0, b1 in broadcast_windows(key):
        if now - b1 < 1800:                       # still on air or just ended
            continue
        t0, t1 = b0 - IMPORT_PAD[0], b1 + IMPORT_PAD[1]
        for sid in sids:
            flag = f"ev_imp:{key}:{sid}:{day}"
            if store.kv_get(flag):
                continue
            n = _import_one(key, sid, t0, t1)
            store.kv_set(flag, {"readings": n, "ts": int(now)})
            done.append((sid, day, n))
            print(f"Import {key} {sid} {day}: {n} readings")
    if done:
        for k in [k for k in _DAYS if k[0] == key]:
            _DAYS.pop(k, None)
        _WHO.pop(key, None)
    return done


def _import_one(key: str, sid: str, t0: float, t1: float) -> int:
    with store.reading():
        c = _db()
        pts = c.execute("SELECT ts, MAX(viewers) FROM sc_samples WHERE sid=? AND ts BETWEEN ? AND ? AND viewers>0 "
                        "GROUP BY ts ORDER BY ts", (sid, t0, t1)).fetchall()
        if not pts:
            return 0
        ch = c.execute("SELECT name, title FROM sc_channels WHERE sid=?", (sid,)).fetchone()
        name, title = (ch[0], ch[1]) if ch else (sid.split(":", 1)[1], "")
        if sid.startswith("yt:"):
            cid = sid[3:]
            v = c.execute("SELECT vid FROM sc_vstreams WHERE sid=? AND first_ts<=? AND last_ts>=? ORDER BY peak DESC LIMIT 1",
                          (sid, t1, t0)).fetchone()
            if not v:
                return 0
            vid = v[0]
            try:
                r = c.execute("SELECT title FROM yt_videos WHERE vid=?", (vid,)).fetchone()
                title = (r and r[0]) or title
            except Exception:
                pass
        else:
            cid = vid = sid.lower()
        # where the counter already has this streamer (any of their streams), its readings stay: the scan fills only
        # the gaps (e.g. before the live list added him mid-broadcast)
        hv = c.execute("SELECT s.ts, s.vid FROM ev_samples s JOIN ev_streams e ON e.event=s.event AND e.vid=s.vid "
                                        "WHERE s.event=? AND s.ts BETWEEN ? AND ? AND (s.vid=? OR e.channel_id=?) ORDER BY s.ts",
                                        (key, t0 - 300, t1 + 300, vid, cid)).fetchall()
        fine = c.execute("SELECT 1 FROM ev_fine WHERE event=? AND ts BETWEEN ? AND ? LIMIT 1", (key, t0, t1)).fetchone()
    have = [r[0] for r in hv]
    if have:
        vid = hv[-1][1]                           # the counter's own stream id, so it stays one row
        import bisect
        def near(t):
            i = bisect.bisect_left(have, t - GAP)
            return i < len(have) and have[i] <= t + GAP
        pts = [p for p in pts if not near(p[0])]
        if not pts:
            return 0
    pk = max(pts, key=lambda p: p[1])
    with store._lock:
        c = _db()
        c.executemany("INSERT INTO ev_samples (event, ts, vid, viewers) VALUES (?,?,?,?)", [(key, int(t), vid, int(v)) for t, v in pts])
        if fine:     # the day boards read ev_fine when the day has it (never start ev_fine for a day without it)
            c.executemany("INSERT INTO ev_fine (event, ts, vid, viewers) VALUES (?,?,?,?)", [(key, int(t), vid, int(v)) for t, v in pts])
        c.execute("""INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen, peak, peak_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(event, vid) DO UPDATE SET
                     first_seen=MIN(ev_streams.first_seen, excluded.first_seen),
                     last_seen=MAX(ev_streams.last_seen, excluded.last_seen),
                     peak_at=CASE WHEN excluded.peak > ev_streams.peak THEN excluded.peak_at ELSE ev_streams.peak_at END,
                     peak=MAX(ev_streams.peak, excluded.peak)""",
                  (key, vid, name, cid, title or "", "watch party", pts[0][0], pts[-1][0], int(pk[1]), pk[0]))
        c.commit()
    return len(pts)


def is_over(key: str) -> bool:
    """broadcast_over said so at the last count (the page shows off air, not a regional stream's leftovers)."""
    op = _OFFPK.get(key)
    return bool(op and op[2])


def fast_tick(ev: dict, now: float = None) -> dict:
    """Re-count every live stream from its own live counter and record one total. Big streams every FAST_SEC,
    tiny ones every MINOR_SEC. Returns {'total', 'live'} or {} if nothing is known to be live."""
    key = ev["key"]
    now = now or time.time()
    if paused(key):
        return {}
    live = {v: x for v, x in _LIVE.get(key, {}).items() if permitted(ev, x)}
    if not live:
        return {}
    fast = _FAST.setdefault(key, {})
    due = []
    crowd = sum(len(v) for v in _LIVE.values()) > ALL_FAST_MAX   # every stream every 2 s; past this many live in all
                                                                  # trackers together, the under-50 ones every 30 s
    for vid, st in live.items():
        f = fast.get(vid)
        big = not crowd or (f["viewers"] if f else st.get("viewers", 0)) >= MINOR_VIEWERS or st.get("kind") == "official"
        if not f or now - f["ts"] >= (FAST_SEC * .75 if big else MINOR_SEC):   # .75: a tick 1.99s later still counts
            due.append(vid)
    # one budget of YouTube counts per 2-second round across every tracker (Kick/Twitch are batched, free):
    # official streams first, then the ones counted longest ago, then the biggest
    yt = [v for v in due if not platforms.is_other(v)]
    if len(yt) > _BUDGET["left"]:
        yt.sort(key=lambda v: (live[v].get("kind") != "official", -(now - fast.get(v, {}).get("ts", 0) > MINOR_SEC),
                               -(fast.get(v, {}).get("viewers") or live[v].get("viewers", 0))))
        keep = set(yt[:max(0, _BUDGET["left"])])
        due = [v for v in due if platforms.is_other(v) or v in keep]
    _BUDGET["left"] -= sum(1 for v in due if not platforms.is_other(v))
    methods, errs, anomalies = [], 0, []
    # Never let one slow stream hold the tick: give the counts ~1.5s, use what's back, and pick up the rest next tick.
    for vid in due:
        if vid not in _INFLIGHT:
            _INFLIGHT[vid] = _fast_pool.submit(_count_one, vid)
    pending = [_INFLIGHT[v] for v in due if v in _INFLIGHT]
    if pending:
        wait(pending, timeout=max(0.5, FAST_SEC * .75))
    results = []
    for v, fu in list(_INFLIGHT.items()):
        if fu.done():
            _INFLIGHT.pop(v, None)
            try:
                results.append(fu.result())
            except Exception:
                results.append((v, "err", ""))
    for vid, n, how in results:
        if n == "err":
            _FASTSTATE["errors"] += 1
            if not platforms.is_other(vid):   # only YouTube refusals slow the loop; a Kick/Twitch hiccup must not
                errs += 1
            continue
        if n is None:
            f = fast.setdefault(vid, {"viewers": 0, "ts": now, "misses": 0})
            f["misses"] += 1
            if f["misses"] >= (10 if live.get(vid, {}).get("kind") == "official" else 3):   # ended
                _ENDED[vid] = now
                live.pop(vid, None)
                _LIVE.get(key, {}).pop(vid, None)
                fast.pop(vid, None)
            continue
        f = fast.get(vid)
        base = f["viewers"] if f else live.get(vid, {}).get("viewers", 0)
        jump = (base >= 500 and n > base * 2.5) or (base > 0 and n >= 20000 and n > base * 2.5)
        if jump and how not in ("YouTube live counter", "Kick API", "Twitch API"):
            # A big jump from the watch page can be total views after the stream ended. Accept it only when the next
            # reading agrees. (The live counter only returns "N watching", so its jumps are real: a stream going
            # from 16K to 100K when the matches start is normal and was wrongly being thrown away.)
            p = _JUMP.get(vid)
            if not (p and now - p[0] < 60 and abs(n - p[1]) <= max(2000, p[1] * .25)):
                _JUMP[vid] = (now, n)
                print(f"Holding a jump for {vid}: {base} -> {n} ({how}), waiting for a second reading")
                continue
        if jump:
            print(f"Accepted a jump for {vid}: {base} -> {n} ({how})")
        _JUMP.pop(vid, None)
        if f and not f.get("misses") and now - f["ts"] <= 15 and f["viewers"]:
            d = n - f["viewers"]
            if abs(d) >= ANOM_MIN and abs(d) >= f["viewers"] * ANOM_PCT:   # sudden bulk jump or drop
                anomalies.append((key, int(now), vid, live.get(vid, {}).get("channel", ""), live.get(vid, {}).get("kind", ""),
                                  f["viewers"], n, d, round(100 * d / f["viewers"], 1), int(now - f["ts"])))
        fast[vid] = {"viewers": n, "ts": now, "misses": 0}
        methods.append(how)
    if methods:
        _FASTSTATE.update(method=max(set(methods), key=methods.count), ok_ts=now)
    # if YouTube starts refusing (rate limit), slow down automatically; speed back up once it's fine
    if due and errs > len(due) // 2:
        _FASTSTATE["slow"] = min(_FASTSTATE.get("slow", 0) + 1, 3)
    elif due and not errs:
        _FASTSTATE["slow"] = max(_FASTSTATE.get("slow", 0) - 1, 0)
    rows = []
    for vid, st in live.items():
        f = fast.get(vid)
        if f and f["misses"]:
            v = 0                      # its counter says it's not live (ended or about to be dropped)
        else:
            v = f["viewers"] if f and now - f["ts"] < MINOR_SEC * 3 else st.get("viewers", 0)
        rows.append({**st, "viewers": v})
    if not rows:
        return {}
    total = sum(r["viewers"] for r in rows)
    by = {k: sum(r["viewers"] for r in rows if r["kind"] == k) for k in ("official", "watch party", "community")}
    if by["official"] <= 0 and (need_official(ev) or total <= 0):
        _OFFPK.pop(key, None)            # official off: the next start reads its peak again (a new day starts from 0)
        return {"total": total, "live": len(rows), "official_live": False}   # only record while the official broadcast is live
    if need_official(ev) and broadcast_over(key, by["official"], now):
        return {"total": total, "live": len(rows), "official_live": False}   # the main official stream has ended
    hist = _HIST.setdefault(key, {})
    for r in rows:
        if r["viewers"] > 0:
            hist.setdefault(r["vid"], deque(maxlen=5400)).append((int(now), r["viewers"]))
    tick = (int(now), total, len(rows), by["official"], by["watch party"], by["community"])
    _MEMT.setdefault(key, deque(maxlen=400)).append(tick)        # the live page reads this: never waits on the database
    _MEMROWS[key] = (now, [dict(r) for r in rows])
    write_samples = now - _LASTSAMPLE.get(key, 0) >= SAMPLE_EVERY
    if write_samples:
        _LASTSAMPLE[key] = now
    snap = [(r["vid"], r["viewers"], r.get("channel", ""), r.get("title", ""), r["kind"]) for r in rows]

    pkm = _PKMEM.setdefault(key, {})
    upd = [(vid, v) for vid, v, _, _, _ in snap if write_samples or v > pkm.get(vid, -1)]   # a new peak, or every 30 s
    for vid, v in upd:
        pkm[vid] = max(v, pkm.get(vid, 0))

    def write():
        with store._lock:
            c = _db()
            c.execute("INSERT OR REPLACE INTO ev_ticks VALUES (?,?,?,?,?,?,?)", (key,) + tick[:2] + tick[2:])
            c.executemany("""UPDATE ev_streams SET last_seen=?, peak_at=CASE WHEN ? > peak THEN ? ELSE peak_at END,
                             peak=MAX(peak, ?) WHERE event=? AND vid=?""",
                          [(now, v, now, v, key, vid) for vid, v in upd])
            if write_samples:
                c.executemany("INSERT INTO ev_samples VALUES (?,?,?,?)", [(key, int(now), vid, v) for vid, v, _, _, _ in snap])
            # every stream at full resolution (every reading, ~2s), kept for later analysis; nothing on the site reads it
            c.executemany("INSERT INTO ev_fine VALUES (?,?,?,?)", [(key, int(now), vid, v) for vid, v, _, _, _ in snap])
            c.commit()
        if write_samples:
            store.kv_set(f"event_last_sample:{key}", now)
        best = _BEST.get(key)
        if best is None:
            best = _BEST[key] = store.kv_get(f"event_peak_break:{key}") or {}
        if total > best.get("total", -1):  # remember exactly who made up the peak
            _BEST[key] = {"total": total}
            store.kv_set(f"event_peak_break:{key}", {"ts": int(now), "total": total, "streams": sorted(
                [{"vid": vid, "viewers": v, "channel": ch, "title": ti, "kind": k} for vid, v, ch, ti, k in snap if v > 0],
                key=lambda x: -x["viewers"])})
    if anomalies:
        an = list(anomalies)

        def write_an():
            with store._lock:
                c = _db()
                c.executemany("INSERT INTO ev_anomalies VALUES (?,?,?,?,?,?,?,?,?,?)", an)
                c.commit()
        _WQ.put(write_an)
    _WQ.put(write)
    return {"total": total, "live": len(rows), "official_live": True}


def repair(key: str) -> dict:
    """One-time cleanup: drop readings where an ended stream's TOTAL views were counted as viewers, and every
    reading taken while the official broadcast wasn't live. Then recompute each stream's peak."""
    with store._lock:
        c = _db()
        rows = c.execute("SELECT rowid, ts, vid, viewers FROM ev_samples WHERE event=? ORDER BY vid, ts", (key,)).fetchall()
        kinds = dict(c.execute("SELECT vid, kind FROM ev_streams WHERE event=?", (key,)).fetchall())
        bad, badv, prev, run = [], {}, {}, {}
        since_fast = 1791713000   # live-counter era (11 Oct 2026); older search-based counts often repeat while live

        def mark(rid, vid, ts, v):
            bad.append(rid)
            badv.setdefault(vid, []).append((ts, v))
        last_ts = {}
        for rid, ts, vid, v in rows:
            p = prev.get(vid)
            gap = ts - last_ts.get(vid, ts)
            last_ts[vid] = ts
            if p is not None and v >= 20000 and v > max(p, 1) * 2.5 and gap <= 180:   # jump = total views after the stream ended
                mark(rid, vid, ts, v)
                continue
            # a live count always moves; the same big number 4+ readings in a row is a finished video's view count
            r = run.get(vid)
            if r and r["v"] == v and v >= 1000 and ts >= since_fast:
                r["items"].append((rid, ts))
                if len(r["items"]) == 4:
                    for x in r["items"]:
                        mark(x[0], vid, x[1], v)
                elif len(r["items"]) > 4:
                    mark(rid, vid, ts, v)
                continue
            run[vid] = {"v": v, "items": [(rid, ts)]}
            prev[vid] = v
        badset = set(bad)
        good = {}
        for rid, ts, vid, v in rows:
            if rid not in badset:
                good.setdefault(vid, []).append(ts)
        for i in range(0, len(bad), 500):
            c.execute(f"DELETE FROM ev_samples WHERE rowid IN ({','.join('?' * len(bad[i:i + 500]))})", bad[i:i + 500])
        # take those bogus numbers back out of the totals recorded at the same moments
        col = {"official": "official", "watch party": "watch", "community": "community"}
        fixed = 0
        for vid, pts in badv.items():
            k = col.get(kinds.get(vid, "community"), "community")
            pts.sort()
            for tid, tts in c.execute("SELECT rowid, ts FROM ev_ticks WHERE event=? AND ts BETWEEN ? AND ?",
                                      (key, pts[0][0] - 35, pts[-1][0] + 35)).fetchall():
                near = min(pts, key=lambda q: abs(q[0] - tts))
                good_near = min((abs(g - tts) for g in good.get(vid, [])), default=10 ** 9)
                if abs(near[0] - tts) <= 35 and abs(near[0] - tts) < good_near:   # this moment's reading was the bogus one
                    c.execute(f"UPDATE ev_ticks SET total=MAX(0,total-?), {k}=MAX(0,{k}-?), live=MAX(0,live-1) WHERE rowid=?",
                              (near[1], near[1], tid))
                    fixed += 1
        dropped = 0
        dropped += c.execute("DELETE FROM ev_ticks WHERE event=? AND official<=0", (key,)).rowcount
        # single readings far above their neighbours (a counter blip between two per-stream samples)
        tk = c.execute("SELECT rowid, ts, total FROM ev_ticks WHERE event=? ORDER BY ts", (key,)).fetchall()
        spikes, j0 = [], 0
        for i, (rid, ts, tot) in enumerate(tk):
            while tk[j0][1] < ts - 60:
                j0 += 1
            near = []
            j = j0
            while j < len(tk) and tk[j][1] <= ts + 60:
                if j != i:
                    near.append(tk[j][2])
                j += 1
            if len(near) >= 4:
                near.sort()
                med = near[len(near) // 2]
                if tot > med * 1.6 and tot - med > 20000:
                    spikes.append(rid)
        for i in range(0, len(spikes), 500):
            c.execute(f"DELETE FROM ev_ticks WHERE rowid IN ({','.join('?' * len(spikes[i:i + 500]))})", spikes[i:i + 500])
        dropped += len(spikes)
        # samples taken when no official reading exists close by
        c.execute("""DELETE FROM ev_samples WHERE event=? AND NOT EXISTS (SELECT 1 FROM ev_ticks t WHERE t.event=ev_samples.event
                     AND t.ts BETWEEN ev_samples.ts - 40 AND ev_samples.ts + 40)""", (key,))
        c.execute("UPDATE ev_streams SET peak=0 WHERE event=?", (key,))
        c.execute("""UPDATE ev_streams SET peak=(SELECT MAX(viewers) FROM ev_samples s WHERE s.event=ev_streams.event AND s.vid=ev_streams.vid),
                     peak_at=(SELECT ts FROM ev_samples s WHERE s.event=ev_streams.event AND s.vid=ev_streams.vid ORDER BY viewers DESC LIMIT 1)
                     WHERE event=? AND EXISTS (SELECT 1 FROM ev_samples s WHERE s.event=ev_streams.event AND s.vid=ev_streams.vid)""", (key,))
        c.commit()
    store.kv_set(f"event_peak_break:{key}", {})
    return {"bad_samples": len(bad), "totals_fixed": fixed, "readings_without_official_dropped": dropped}


def purge_unpermitted(key: str) -> dict:
    ev = get(key)
    if not ev or not allowed_list(ev):
        return {}
    with store._lock:
        c = _db()
        streams = c.execute("SELECT vid, channel, channel_id, kind FROM ev_streams WHERE event=?", (key,)).fetchall()
        bad = {r[0]: r[3] for r in streams if not permitted(ev, {"vid": r[0], "channel": r[1], "channel_id": r[2]})}
        col = {"official": "official", "watch party": "watch", "community": "community"}
        fixed = 0
        for vid, kind in bad.items():
            pts = c.execute("SELECT ts, viewers FROM ev_samples WHERE event=? AND vid=? ORDER BY ts", (key, vid)).fetchall()
            if not pts:
                continue
            k = col.get(kind, "community")
            for tid, tts in c.execute("SELECT rowid, ts FROM ev_ticks WHERE event=? AND ts BETWEEN ? AND ?",
                                      (key, pts[0][0] - 35, pts[-1][0] + 35)).fetchall():
                near = min(pts, key=lambda q: abs(q[0] - tts))
                if abs(near[0] - tts) <= 35 and near[1] > 0:
                    c.execute(f"UPDATE ev_ticks SET total=MAX(0,total-?), {k}=MAX(0,{k}-?), live=MAX(0,live-1) WHERE rowid=?",
                              (near[1], near[1], tid))
                    fixed += 1
        for vid in bad:
            c.execute("DELETE FROM ev_samples WHERE event=? AND vid=?", (key, vid))
            c.execute("DELETE FROM ev_streams WHERE event=? AND vid=?", (key, vid))
        # the permitted ones are watch parties
        for r in streams:
            if r[0] not in bad and r[3] == "community":
                c.execute("UPDATE ev_streams SET kind='watch party' WHERE event=? AND vid=?", (key, r[0]))
        c.execute("UPDATE ev_ticks SET watch=watch+community, community=0 WHERE event=? AND community>0", (key,))
        c.commit()
    store.kv_set(f"event_peak_break:{key}", {})
    return {"removed_streams": len(bad), "totals_fixed": fixed}


def repair_once():
    for k, ev in events().items():
        flag = f"event_repair_v2:{k}"
        if not store.kv_get(flag):
            try:
                print(f"Event {k} cleanup: {repair(k)}")
            except Exception as e:
                print(f"Event {k} cleanup failed: {str(e)[:150]}")
            store.kv_set(flag, True)
        flag = f"event_allow_v1:{k}"
        if not store.kv_get(flag):
            try:
                print(f"Event {k} allow-list cleanup: {purge_unpermitted(k)}")
            except Exception as e:
                print(f"Event {k} allow-list cleanup failed: {str(e)[:150]}")
            store.kv_set(flag, True)


_INC = {}       # sid -> (checked at, Indian?)
_ICTX = {}      # event -> (loaded at, {sid: country}, {sid: india verdict of the live scan}, {name: country})


def _norm_name(n: str) -> str:
    return re.sub(r"(official|live|gaming|yt|tv|is|casts?)$", "", re.sub(r"[^a-z0-9]", "", (n or "").lower())) or (n or "").lower()


def _india_ctx(key: str) -> tuple:
    """What the site knows about this event's channels, loaded once every 10 minutes: each channel's country
    (sc_channels: the YouTube channel's own setting), the live scan's India verdict for the tournament's streams
    (sc_tour_ch: country, chat language, BGMI ...), and YouTube channel names -> country, so a Kick / Twitch channel
    with the same name as a YouTube one (anshyt / Ansh YT, mortal / MortaL) gets that country."""
    hit = _ICTX.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit
    ctry, verd, names = {}, {}, {}
    try:
        tour = (PRESETS.get(key) or {}).get("tag") or (PRESETS.get(key) or {}).get("name") or key
        with store.reading():
            c = _db()
            rows = c.execute("SELECT vid, channel_id, channel FROM ev_streams WHERE event=?", (key,)).fetchall()
            sids = {(v.lower() if platforms.is_other(v) else "yt:" + (ci or "")): ch for v, ci, ch in rows}
            q = ",".join("?" * len(sids))
            if sids:
                for sid, cc in c.execute(f"SELECT sid, country FROM sc_channels WHERE sid IN ({q})", list(sids)):
                    if cc:
                        ctry[sid] = cc
                for sid, iv in c.execute(f"SELECT sid, MAX(india) FROM sc_tour_ch WHERE sid IN ({q}) AND tour LIKE ? GROUP BY sid",
                                         list(sids) + [f"%{str(tour).split()[0]}%"]):
                    verd[sid] = bool(iv)
        for sid, ch in sids.items():
            if sid.startswith("yt:") and ctry.get(sid) not in (None, "", "-"):
                names.setdefault(_norm_name(ch), ctry[sid])
    except Exception as e:
        print(f"India context {key}: {str(e)[:120]}")
    _ICTX[key] = (time.time(), ctry, verd, names)
    return _ICTX[key]


# ---------- who a channel is: its bio, and the same streamer on YouTube and Kick (owner, 27 Nov) ----------
# A YouTube channel's country setting is often wrong: Nepali streamers set India (Ansh YT: "Nepali Esports Talent",
# Cr7 HORAA, SuKu "from Nepal"). The channel's own description, and a Kick bio, decide first. The same streamer on
# YouTube and Kick is one row on the leaderboard: the YouTube About links (kick.com/<slug>), the Kick profile's YouTube
# handle, or the same name.
BIO_ABROAD = re.compile(r"\b(nepal|nepali|nepalese|kathmandu|pokhara|bangladesh|bangladeshi|dhaka|pakistan|pakistani|"
                        r"lahore|karachi|islamabad|sri\s*lanka|lankan|bhutan|bhutanese|a1\s*esports)\b|\U0001F1F3\U0001F1F5|"
                        r"\U0001F1E7\U0001F1E9|\U0001F1F5\U0001F1F0|\U0001F1F1\U0001F1F0", re.I)
BIO_INDIA = re.compile(r"\b(india|indian|mumbai|delhi|noida|gurgaon|bangalore|bengaluru|kolkata|chennai|hyderabad|pune|"
                       r"jaipur|lucknow|ahmedabad|kerala|assam|tamil|telugu|kannada|marathi|hindi|krafton\s*india)\b|"
                       r"\U0001F1EE\U0001F1F3", re.I)
_ABQ, _ABBUSY, _ABL, _ABRUN = [], set(), threading.Lock(), [False]


def yt_about(cid: str) -> dict:
    """{desc, country, links, handle} of a YouTube channel's About page (kv, 7 days; read in the background)."""
    if not (cid or "").startswith("UC"):
        return {}
    v = store.kv_get(f"ev_about:{cid}")
    if v and time.time() - v.get("ts", 0) < 7 * 86400:
        return v
    with _ABL:
        if cid not in _ABBUSY and len(_ABBUSY) < 400:
            _ABBUSY.add(cid)
            _ABQ.append(cid)
            if not _ABRUN[0]:
                _ABRUN[0] = True
                threading.Thread(target=_about_loop, daemon=True).start()
    return v or {}


def about_pending(cid: str) -> bool:
    """The About page of this YouTube channel is queued and not read yet."""
    return cid in _ABBUSY


def _about_loop():
    while True:
        with _ABL:
            if not _ABQ:
                _ABRUN[0] = False
                return
            cid = _ABQ.pop(0)
        try:
            r = _http.get(f"https://www.youtube.com/channel/{cid}/about", headers={"User-Agent": _UA, "Accept-Language": "en"},
                          cookies={"CONSENT": "YES+", "SOCS": "CAI"}, timeout=15)
            m = re.search(r"var ytInitialData\s*=\s*(\{.+?\});</script>", r.text, re.S)
            out = {"ts": time.time(), "desc": "", "country": "", "links": [], "handle": ""}
            if m:
                import json as _json
                stack = [_json.loads(m.group(1))]
                while stack:
                    o = stack.pop()
                    if isinstance(o, dict):
                        a = o.get("aboutChannelViewModel")
                        if isinstance(a, dict):
                            out.update(desc=(a.get("description") or "")[:2000], country=a.get("country") or "",
                                       links=[((l.get("channelExternalLinkViewModel") or {}).get("link") or {}).get("content", "")
                                              for l in a.get("links") or []],
                                       handle=(a.get("displayCanonicalChannelUrl") or a.get("canonicalChannelUrl") or "").split("/")[-1])
                            break
                        stack.extend(o.values())
                    elif isinstance(o, list):
                        stack.extend(o)
            store.kv_set(f"ev_about:{cid}", out)
        except Exception as e:
            print(f"YouTube about {cid}: {str(e)[:100]}")
        finally:
            with _ABL:
                _ABBUSY.discard(cid)
        time.sleep(1.5)


def _bio_of(sid: str) -> tuple:
    """(the channel's own words about itself, its links / handles) for yt:/kick:/twitch: sids."""
    if sid.startswith("yt:"):
        a = yt_about(sid[3:])
        return a.get("desc") or "", " ".join(a.get("links") or [])
    try:
        from tracker import profiles
        ln = profiles.links(sid)
        return profiles.bio(sid) or "", " ".join(str(v) for v in ln.values())
    except Exception:
        return "", ""


_WHO = {}       # event -> (built at, {stream sid: merged streamer key})
_PREF = set()   # Kick / Twitch profiles already asked for


def who_map(key: str) -> dict:
    """Stream sid -> the streamer it belongs to (a YouTube sid when the same streamer is on YouTube and Kick / Twitch).
    Built every 10 minutes from the event's channels: a YouTube channel's About links to kick.com/<slug> or
    twitch.tv/<login>, a Kick profile's YouTube handle, or the same name."""
    hit = _WHO.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    out = {}
    try:
        with store.reading():
            rows = _db().execute("SELECT DISTINCT vid, channel_id, channel FROM ev_streams WHERE event=?", (key,)).fetchall()
        yts = {}                                  # yt sid -> (name, about)
        others = {}                               # kick/twitch sid -> name
        for vid, cid, ch in rows:
            if platforms.is_other(vid):
                others[vid.lower()] = ch or vid.split(":", 1)[1]
            elif (cid or "").startswith("UC"):
                yts["yt:" + cid] = (ch, yt_about(cid))
        by_link, by_handle, by_name = {}, {}, {}
        for sid, (ch, ab) in yts.items():
            for l in ab.get("links") or []:
                m = re.search(r"(kick\.com|twitch\.tv)/([A-Za-z0-9_-]+)", l or "", re.I)
                if m:
                    by_link[("kick:" if "kick" in m.group(1).lower() else "twitch:") + m.group(2).lower()] = sid
            if ab.get("handle"):
                by_handle[_norm_name(ab["handle"].lstrip("@"))] = sid
            by_name.setdefault(_norm_name(ch), sid)
        try:
            from tracker import profiles
        except Exception:
            profiles = None
        for sid, nm in others.items():
            yh = str(((profiles.links(sid) if profiles else {}) or {}).get("youtube") or "").rstrip("/").split("/")[-1].split("?")[0]
            out[sid] = by_link.get(sid) or (by_handle.get(_norm_name(str(yh).lstrip("@"))) if yh else None) \
                or by_name.get(_norm_name(nm)) or by_name.get(_norm_name(sid.split(":", 1)[1])) or sid
        for sid in yts:
            out[sid] = sid
        if profiles:                              # Kick bios / YouTube handles of the event's Kick channels (once)
            miss = [s for s in others if s not in _PREF and not profiles.bio(s) and not profiles.links(s)][:60]
            _PREF.update(miss)
            if miss:
                threading.Thread(target=profiles.refresh, args=(miss,), daemon=True).start()
    except Exception as e:
        print(f"Same streamer map {key}: {str(e)[:120]}")
    wait = any(about_pending(s[3:]) for s in out if s.startswith("yt:"))   # About pages still being read: again in a minute
    _WHO[key] = (time.time() - (540 if wait else 0), out)
    return out


def stream_sid(vid: str, channel_id: str = "") -> str:
    return vid.lower() if platforms.is_other(vid) else ("yt:" + channel_id if (channel_id or "").startswith("UC") else "")


def stream_india(vid: str, channel_id: str = "", title: str = "", channel: str = "", key: str = "pmgc") -> bool:
    """Is this stream's channel Indian? (owner, 27 Nov: PMGC watch-party rankings split India / outside India.)
    In order: the owner's live list (india / not_india: video, channel id, kick:slug, for the streamer's YouTube or
    Kick), the channel's own bio (YouTube description, Kick / Twitch bio: Nepal, Bangladesh, Pakistan ... outside),
    the same streamer's YouTube channel for Kick / Twitch, the YouTube channel's country setting, the live scan's
    verdict for the tournament (chat language ...), the scan's current verdict, then the site's India rules on the
    title and name. Cached 30 minutes per channel."""
    plat = platforms.platform_of(vid)
    sid = stream_sid(vid, channel_id)
    if not sid:
        return False
    who = who_map(key).get(sid) or sid
    ll = live_list(key)
    ids = {vid, channel_id or "-", sid, who, who[3:] if who.startswith("yt:") else who}
    if ids & set(ll.get("not_india") or []):
        return False
    if ids & set(ll.get("india") or []):
        return True
    now = time.time()
    hit = _INC.get(sid)
    if hit and now - hit[0] < 1800:
        return hit[1]
    try:
        from tracker import scene
        bios = " ".join(_bio_of(s)[0] for s in {sid, who})
        _, ctry, verd, names = _india_ctx(key)
        cc = ctry.get(who) or ctry.get(sid) or (scene._CTRY.get(who[3:]) if who.startswith("yt:") else None)
        if BIO_ABROAD.search(bios) and not re.search(r"\b(india|indian)\b|\U0001F1EE\U0001F1F3", bios, re.I):
            v = False                             # the streamer says where they're from
        elif BIO_INDIA.search(bios) and not BIO_ABROAD.search(bios):
            v = True
        elif cc and cc != "-":
            v = cc == "IN"
        elif plat in ("kick", "twitch") and names.get(_norm_name(channel or sid.split(":", 1)[-1])):
            v = names[_norm_name(channel or sid.split(":", 1)[-1])] == "IN"
        elif sid in verd:
            v = verd[sid]
        elif "india" in (scene._LIVE.get(sid) or {}):
            v = bool(scene._LIVE[sid]["india"])
        else:
            x = {"sid": sid, "platform": plat, "title": title or "", "name": channel or ""}
            v = bool(scene.india_why(x, None, scene.india_known())[0])
    except Exception:
        v = False
    # a YouTube About page still being read: decide again in a minute instead of keeping this answer for 30
    wait = any(about_pending(s[3:]) for s in {sid, who} if s.startswith("yt:"))
    _INC[sid] = (now - (1800 - 60 if wait else 0), v)
    if len(_INC) > 20000:
        _INC.clear()
    return v


def recover_once():
    """PMGC Day 1 (26 Nov): the 2-second readings from 16:55 IST were queued in memory faster than they were written,
    and the restart that fixed it dropped the queue. The site's own live readings, saved from its public data every
    2 minutes while that happened (tracker/recover/*.json: each the last ~90 totals and every live stream's viewers),
    are written back once: totals into ev_ticks where no reading exists, each stream's viewers into ev_samples, and
    stream peaks into ev_streams."""
    import glob
    import json as _json
    for f in sorted(glob.glob(str(pathlib.Path(__file__).resolve().parent / "recover" / "*.json"))):
        flag = "event_recover_v1:" + pathlib.Path(f).stem
        if store.kv_get(flag):
            continue
        try:
            d = _json.load(open(f))
            key = d["key"]
            ticks, samples = d.get("ticks") or [], d.get("samples") or []
            with store._lock:
                c = _db()
                have = {r[0] for r in c.execute("SELECT ts FROM ev_ticks WHERE event=? AND ts BETWEEN ? AND ?",
                                                (key, min((t[0] for t in ticks), default=0) - 1, max((t[0] for t in ticks), default=0) + 1))}
                new = [t for t in ticks if t[0] not in have and t[0] - 1 not in have and t[0] + 1 not in have]
                c.executemany("INSERT OR IGNORE INTO ev_ticks VALUES (?,?,?,?,?,?,?)",
                              [(key, int(t[0]), int(t[1]), int(t[5]) if len(t) > 5 else 0, int(t[2]), int(t[3]), int(t[4])) for t in new])
                c.executemany("INSERT INTO ev_samples VALUES (?,?,?,?)", [(key, int(ts), vid, int(v)) for ts, vid, v in samples])
                c.executemany("""UPDATE ev_streams SET peak_at=CASE WHEN ? > peak THEN ? ELSE peak_at END, peak=MAX(peak, ?)
                                 WHERE event=? AND vid=?""", [(int(v), int(ts), int(v), key, vid) for ts, vid, v in samples])
                c.commit()
            store.kv_set(flag, True)
            print(f"Recovered {key}: {len(new)} readings, {len(samples)} stream readings from {pathlib.Path(f).name}")
        except Exception as e:
            print(f"Recover {f}: {str(e)[:150]}")


def fast_healthy() -> bool:
    return time.time() - _FASTSTATE["ok_ts"] < max(FAST_SEC * 2 ** _FASTSTATE.get("slow", 0) * 5, 20)


def run_fast_forever():
    """Background thread: live counters for every active event."""
    repair_once()
    recover_once()

    def minutely():   # alerts and the 10-minute data export run on their own thread so they never delay a count
        while True:
            try:
                from tracker import eventlog, dataexport
                try:
                    from tracker import reportzip
                    reportzip.tick()       # weekly / monthly data zip for the owner (own thread)
                except Exception as e:
                    print(f"Report zip: {str(e)[:150]}")
                evs = [ev for ev in events().values() if ev.get("active")]
                for ev in evs:       # automatic trackers: official / watch party by the publisher-name rule (once)
                    try:
                        relabel_once(ev)
                    except Exception as e:
                        print(f"Relabel {ev.get('key')}: {str(e)[:150]}")
                try:                 # the one-time tournament clean-up (waits for Liquipedia to load)
                    from tracker import scene as _sc
                    _sc.fix_tours_once()
                except Exception as e:
                    print(f"Tournament clean-up: {str(e)[:150]}")
                    store.kv_set("scene_fix_tours_err", {"error": str(e)[:200], "ts": int(time.time())})
                for ev in evs:       # streams missed by the counter, from the scan (off air, every 10 minutes)
                    try:
                        import_scan(ev["key"])
                    except Exception as e:
                        print(f"Import {ev.get('key')}: {str(e)[:150]}")
                for ev in evs:       # the daily CSV first: it is quick and must not wait behind the slower jobs
                    try:
                        eventlog.send_day_csv(ev)
                    except Exception as e:
                        print(f"Event log {ev.get('key')} send_day_csv: {str(e)[:150]}")
                for ev in evs:
                    if ev.get("active"):
                        for f in (eventlog.check, eventlog.check_roster, dataexport.tick):
                            try:     # one failing step (or event) no longer skips the rest, e.g. the daily CSV
                                f(ev)
                            except Exception as e:
                                print(f"Event log {ev.get('key')} {f.__name__}: {str(e)[:150]}")
            except Exception as e:
                print(f"Event log failed: {str(e)[:150]}")
            time.sleep(60)
    threading.Thread(target=minutely, daemon=True).start()
    while True:
        t0 = time.time()
        _BUDGET["left"] = FAST_BUDGET
        for ev in sorted(events().values(), key=lambda e: bool(PRESETS.get(e["key"], {}).get("lp"))):   # hand-made first
            if ev.get("active") and _LIVE.get(ev["key"]):
                try:
                    fast_tick(ev)
                except Exception as e:
                    print(f"Live counter failed for {ev['key']}: {str(e)[:150]}")
        time.sleep(max(0.3, FAST_SEC * 2 ** _FASTSTATE.get("slow", 0) - (time.time() - t0)))


def _search(q: str, gl: str = "IN", pages: int = 3) -> list:
    """YouTube live search: the site's light search (about 20 streams a page, several pages) first, yt-dlp if it fails."""
    try:
        from tracker import scene
        return scene.yt_search_pages(q, gl, pages)
    except Exception:
        return search_live(q)


GRACE_SEC = 20 * 60        # official off air this long (a break, a restart) still counts as the broadcast day
FIRST_HOUR = 3600          # after the official goes live: every search, every poll (late starters)
PRE_SEC = 30 * 60          # before the scheduled start: full search too (watch parties start early)
_PHASE = {}                # event -> {"off_ts": last seen live, "on_ts": went live, "n": polls}


def on_air(ev: dict, now: float, official_found: bool) -> str:
    """'full' (search everything) or 'watch' (official channels only). Off air the poll costs a few requests."""
    ph = _PHASE.setdefault(ev["key"], {"off_ts": 0, "on_ts": 0, "n": 0})
    if official_found:
        if now - ph["off_ts"] > GRACE_SEC:
            ph["on_ts"] = now                   # a new broadcast day
        ph["off_ts"] = now
    ns = next_start(ev["key"])
    if official_found or now - ph["off_ts"] < GRACE_SEC or (ns and ns - now < PRE_SEC):
        return "full"
    if not need_official(ev):                   # no official channel known: on air while the site's scan sees it live
        return "full" if scene_matches(ev) else "watch"
    return "watch"


_HANDLE = {}               # @handle -> channel id (UC...)
_NOTLIVE = {}              # vid -> time its counter said not live (feed entries that are uploads / ended streams)


def _channel_id(h: str):
    """@handle -> UC id, from the channel page once (kept in the database)."""
    h = h.strip()
    if h.startswith("UC") and len(h) == 24:
        return h
    if h in _HANDLE:
        return _HANDLE[h]
    ids = store.kv_get("ev_handle_ids") or {}
    if h in ids:
        _HANDLE[h] = ids[h]
        return ids[h]
    try:
        r = _http.get(f"https://www.youtube.com/@{h.lstrip('@')}", headers={"User-Agent": _UA}, timeout=10)
        m = re.search(r'"externalId":"(UC[\w-]{22})"', r.text) or re.search(r'<meta itemprop="identifier" content="(UC[\w-]{22})"', r.text) \
            or re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
        cid = m.group(1) if m else None
    except Exception:
        return None
    _HANDLE[h] = cid
    if cid:
        ids[h] = cid
        store.kv_set("ev_handle_ids", ids)
    return cid


def feed_live(h: str) -> list:
    """Streams live now on a channel from its public feed (a small XML file) + the live counter: no yt-dlp, no
    API quota. The feed lists a stream from when it is scheduled or starts."""
    cid = _channel_id(h)
    if not cid:
        return []
    try:
        r = _http.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", timeout=8, headers={"User-Agent": _UA})
        if r.status_code != 200:
            return []
    except Exception:
        return []
    import html as _html
    out, now = [], time.time()
    name = re.search(r"<author>\s*<name>([^<]+)</name>", r.text)
    for e in re.findall(r"<entry>(.*?)</entry>", r.text, re.S)[:5]:
        v = re.search(r"<yt:videoId>([\w-]{11})</yt:videoId>", e)
        pub = re.search(r"<published>([^<]+)</published>", e)
        ti = re.search(r"<title>([^<]*)</title>", e)
        if not v or not pub:
            continue
        vid = v.group(1)
        try:
            ts = datetime.fromisoformat(pub.group(1).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if now - ts > 7 * 86400 or now - _NOTLIVE.get(vid, 0) < 600:
            continue
        try:
            n = count_live(vid)
        except Exception:
            n = None
        if n is None:
            _NOTLIVE[vid] = now
            continue
        out.append({"vid": vid, "title": _html.unescape(ti.group(1)) if ti else "", "channel": _html.unescape(name.group(1)) if name else "",
                    "channel_id": cid, "viewers": int(n)})
    return out


def poll(ev: dict, now: int = None) -> dict:
    """Find live streams, record viewers. Returns {'total', 'live', 'streams': [...]}.

    Off air only the official channels are checked (every poll). When one goes live (or the scheduled start is under
    30 minutes away) the full search runs every poll: YouTube searches, the listed channels, Kick and Twitch
    channels and categories, and the site-wide live scan; every query each poll for the first hour (streamers who
    start late), then the main queries every poll and the rest in turn. It keeps going 20 minutes after the official
    stream goes off air (breaks between days, restarts)."""
    now = now or int(time.time())
    found = {}
    errors = 0
    pr = PRESETS.get(ev["key"], {})
    official_now = set()
    ocs = pr.get("official_channels", [])
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(ocs)))) as pool:   # PMGC has 11 language channels
        for res in pool.map(lambda oc: _safe(channel_live_all, oc), ocs):
            for s in res or []:
                if not pr.get("official_title") or relevant(ev, s):   # PMGC: a channel's other shows don't count
                    s["from_official"] = True
                    official_now.add(s["vid"])
                    found[s["vid"]] = s
    for v in official_now:           # the channel itself says these are live: never drop them as ended
        _ENDED.pop(v, None)
    plat = []
    if platforms.enabled(ev, preset(ev["key"])):
        plat = [s for s in platforms.discover(ev, preset(ev["key"])) if relevant(ev, s)]
    off_found = bool(official_now) or any(s.get("official") for s in plat)
    mode = on_air(ev, now, off_found)
    ph = _PHASE[ev["key"]]
    ph["n"] += 1
    ph["mode"] = mode
    ns = next_start(ev["key"])
    if pr.get("verify") and ph["n"] % 5 == 1 and (mode == "full" or (ns and 0 < ns - now < 3 * 3600)):
        threading.Thread(target=_safe, args=(scheduled_search, ev), daemon=True).start()
    for s in plat:
        if mode == "full" or s.get("official"):
            found[s["vid"]] = s
            _ENDED.pop(s["vid"], None)       # the platform API says it's live now (no search lag to guard against)
    if mode == "full":
        qs = list(pr.get("queries") or ev["queries"])[:10]
        core, rest = qs[:4], qs[4:]
        if rest and now - ph["on_ts"] > FIRST_HOUR:
            k = ph["n"] % len(rest)
            rest = (rest[k:] + rest[:k])[:2]       # two of the others each poll, in turn
        jobs = [(q, "IN") for q in core + rest]
        if opt(ev, "scene_world"):
            jobs += [(q, "US") for q in core[:2]]  # the worldwide edition ranks other countries' streams
        wq = list(pr.get("world_queries") or [])
        if wq:                                   # each region's YouTube in its own words (2 pages each), 7 a poll in turn
            k = (ph["n"] * 7) % len(wq)          # (all every poll put too much on the server on Day 1)
            jobs += [(q, gl, 2) for q, gl in (wq[k:] + wq[:k])[:7]]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for res in pool.map(lambda a: _safe(_search, *a), jobs):
                if res is None:
                    errors += 1
                    continue
                for s in res:
                    if relevant(ev, s) and s["viewers"] >= found.get(s["vid"], {}).get("viewers", -1):
                        found[s["vid"]] = s
        for s in scene_matches(ev):              # streams carrying it that only the site-wide live scan saw
            if s["vid"] not in found and relevant(ev, s):
                found[s["vid"]] = s
                _ENDED.pop(s["vid"], None)
        listed = list(dict.fromkeys(ev.get("channels", []) + pr.get("always_check", []) + live_list(ev["key"]).get("youtube", [])
                                    + [h for _, _, h in roster(ev["key"]) if h]))
        chans = list(dict.fromkeys(listed + _event_channels(ev["key"], now) + _trusted_slice(pr, ph["n"])))[:110]
        with ThreadPoolExecutor(max_workers=8) as pool:       # every listed channel's feed, every poll (cheap): the
            for res in pool.map(lambda h: _safe(feed_live, h), chans):   # listed streamers, every channel that has
                for s in res or []:                                      # carried this event (a new stream after a
                    if s["vid"] not in found and relevant(ev, s):        # break is found within a minute) and the
                        found[s["vid"]] = s                              # trusted ones in turn
        third = [h for i, h in enumerate(listed) if i % 4 == ph["n"] % 4 and not any(
            (x.get("channel_id") or "") == h for x in found.values())][:10]   # a few listed ones not found through their
        with ThreadPoolExecutor(max_workers=4) as pool:                       # /live page (a feed can lag)
            for s in pool.map(check_channel, third):
                if s and s["vid"] not in found and relevant(ev, s):
                    found[s["vid"]] = s
        sch = [x for v, x in list((_SCHED.get(ev["key"]) or {}).items()) if v not in found
               and (not x.get("start") or now - 5400 < x["start"] < now + 1200)]     # due now (start -90..+20 min)
        if sch and fast_healthy():               # scheduled watch parties: counted from their first live minute
            sch.sort(key=lambda x: x.get("start") or 0)
            with ThreadPoolExecutor(max_workers=8) as pool:
                for x, n in zip(sch[:60], pool.map(lambda x: _safe(count_live, x["vid"]), sch[:60])):
                    if n and relevant(ev, x):
                        found[x["vid"]] = {**x, "viewers": int(n)}
                        _ENDED.pop(x["vid"], None)
        if pr.get("verify"):
            _card_filter(ev, found)              # another game on YouTube's card: not a watch party
    with store.reading():
        c = _db()
        recent = [dict(r) for r in c.execute(
            "SELECT vid, channel, channel_id, title FROM ev_streams WHERE event=? AND last_seen>?",
            (ev["key"], now - RECHECK_MIN * 60))]
    vids = ev.get("videos", []) + pr.get("videos_extra", [])
    recent = [r for r in recent if not platforms.is_other(r["vid"])]   # Kick/Twitch are re-checked by discover()
    if pr.get("verify"):                         # a title changed, or the owner left it out: not carried over
        recent = [r for r in recent if r["vid"] in official_now or relevant(ev, r)]
    if mode != "full":
        recent = [r for r in recent if r["vid"] in official_now]
    # Streams found before that this poll's searches missed: the 2-second counter already knows if they are live
    # (no request at all); the rest get one live-counter request each. The Data API is only the fallback when
    # the counter is failing, so the quota is kept for the site's daily stats.
    fast = _FAST.get(ev["key"], {})
    ask = []
    for r in recent:
        if r["vid"] in found:
            continue
        f = fast.get(r["vid"])
        if f and not f.get("misses") and now - f["ts"] < 15 and f["viewers"]:
            found[r["vid"]] = {**r, "viewers": f["viewers"]}
        else:
            ask.append(r)
    ask += [{"vid": v, "channel": "", "channel_id": "", "title": ""} for v in vids if v not in found]
    if ask and fast_healthy():
        with ThreadPoolExecutor(max_workers=8) as pool:
            for r, n in zip(ask, pool.map(lambda r: _safe(count_live, r["vid"]), ask)):
                if n:
                    found[r["vid"]] = {**r, "viewers": int(n)}
    elif ask:
        try:
            api = api_counts([r["vid"] for r in ask])
        except Exception as e:
            api = {}
            print(f"YouTube API failed: {str(e)[:120]}")
        for r in ask:
            v = api.get(r["vid"])
            if v:
                found[r["vid"]] = {**r, "viewers": v}
        if not api:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for s in pool.map(lambda r: _safe(check_video, r["vid"]), ask[:MAX_DIRECT_CHECKS]):
                    if s:
                        found[s["vid"]] = s
    for vid in [v for v in found if time.time() - _ENDED.get(v, 0) < 900]:
        found.pop(vid)                       # the live counter already saw these end
    streams = []
    fast = _FAST.get(ev["key"], {})
    for s in found.values():
        s["kind"] = kind_of(ev, s)
        f = fast.get(s["vid"])
        if f and now - f["ts"] < MINOR_SEC * 3:
            s["viewers"] = f["viewers"]      # the live counter is fresher than search results
        streams.append(s)
    _LIVE[ev["key"]] = {s["vid"]: s for s in streams}
    total = sum(s["viewers"] for s in streams)
    by = {k: sum(s["viewers"] for s in streams if s["kind"] == k) for k in ("official", "watch party", "community")}
    official_live = (by["official"] > 0 or (not need_official(ev) and total > 0)) and not paused(ev["key"])
    if official_live and need_official(ev) and broadcast_over(ev["key"], by["official"], now):
        official_live = False                # the main official stream has ended (a regional one is still on)
    with store._lock:
        c = _db()
        for s in streams:
            c.execute("""INSERT INTO ev_streams (event, vid, channel, channel_id, title, kind, first_seen, last_seen,
                         peak, peak_at) VALUES (?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(event, vid) DO UPDATE SET last_seen=excluded.last_seen, title=excluded.title,
                         kind=excluded.kind,
                         peak_at=CASE WHEN excluded.peak > ev_streams.peak THEN excluded.peak_at ELSE ev_streams.peak_at END,
                         peak=MAX(ev_streams.peak, excluded.peak)""",
                      (ev["key"], s["vid"], s["channel"], s["channel_id"], s["title"], s["kind"], now, now,
                       s["viewers"] if official_live else 0, now))
        record = official_live and not fast_healthy()  # live counter records while it works; nothing when official is off
        if record:
            c.executemany("INSERT INTO ev_samples VALUES (?,?,?,?)", [(ev["key"], now, s["vid"], s["viewers"]) for s in streams])
        if record and (streams or errors < len(ev["queries"][:8])):  # never a fake zero
            c.execute("INSERT OR REPLACE INTO ev_ticks VALUES (?,?,?,?,?,?,?)",
                      (ev["key"], now, total, len(streams), by["official"], by["watch party"], by["community"]))
        c.commit()
    store.kv_set(f"event_last_poll:{ev['key']}", now)
    return {"total": total, "live": len(streams), "streams": sorted(streams, key=lambda s: -s["viewers"])}


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def run_all():
    """Scheduler job: poll every active event (and, every 6 hours, make trackers for new Liquipedia tournaments)."""
    try:
        from tracker import autoev
        autoev.sync()
    except Exception as e:
        print(f"Auto trackers failed: {str(e)[:200]}")
    try:
        from tracker import scene
        busy = scene.overloaded()
    except Exception:
        busy = False
    _RUNS[0] += 1
    todo = [ev for ev in events().values() if ev.get("active") and not PRESETS.get(ev["key"], {}).get("ended")
            and not ((busy or (_PHASE.get(ev["key"]) or {}).get("mode") == "watch")    # automatic trackers off air, or
                     and PRESETS.get(ev["key"], {}).get("lp") and _RUNS[0] % 3)]       # the server busy: every 3rd minute

    def one(ev):
        try:
            poll(ev)
        except Exception as e:
            print(f"Event {ev['key']} poll failed: {str(e)[:200]}")
    with ThreadPoolExecutor(max_workers=3) as pool:     # one slow tracker never delays the others
        list(pool.map(one, todo))


_RUNS = [0]


# ---------- numbers ----------

def stats(key: str, since: float = 0, until: float = None) -> dict:
    """Peak, average, hours watched, airtime, by kind, by day, by channel, live now."""
    until = until or time.time() + 1
    with store.reading():
        c = _db()
        ticks = [dict(r) for r in c.execute("SELECT * FROM ev_ticks WHERE event=? AND ts>=? AND ts<=? ORDER BY ts",
                                             (key, since, until))]
        samples = [dict(r) for r in c.execute(
            "SELECT s.ts, s.vid, s.viewers, t.channel, t.title, t.kind, t.channel_id FROM ev_samples s JOIN ev_streams t "
            "ON t.event=s.event AND t.vid=s.vid WHERE s.event=? AND s.ts>=? AND s.ts<=? ORDER BY s.ts",
            (key, since, until))]
    out = {"ticks": len(ticks)}
    if not ticks:
        return out
    gap_cap = POLL_SEC * 3
    hw, air = 0.0, 0
    for i, t in enumerate(ticks):
        dt = min((ticks[i + 1]["ts"] - t["ts"]) if i + 1 < len(ticks) else POLL_SEC, gap_cap)
        if t["live"] > 0:
            hw += t["total"] * dt / 3600
            air += dt
    peak = max(ticks, key=lambda t: t["total"])
    out.update(peak=peak["total"], peak_at=peak["ts"], peak_split={k: peak[k] for k in ("official", "watch", "community")},
               hours_watched=hw, airtime_h=air / 3600, avg=(hw / (air / 3600)) if air else 0,
               last=ticks[-1], first_ts=ticks[0]["ts"])
    # per stream
    per = {}
    times = sorted({s["ts"] for s in samples})
    nxt = {t: min((times[i + 1] - t) if i + 1 < len(times) else POLL_SEC, gap_cap) for i, t in enumerate(times)}
    for s in samples:
        p = per.setdefault(s["vid"], {"vid": s["vid"], "channel": s["channel"], "title": s["title"], "kind": s["kind"],
                                      "platform": platforms.platform_of(s["vid"]), "peak": 0, "hw": 0.0, "air": 0})
        p["peak"] = max(p["peak"], s["viewers"])
        p["hw"] += s["viewers"] * nxt[s["ts"]] / 3600
        p["air"] += nxt[s["ts"]]
    chans = {}
    for p in per.values():
        ch = chans.setdefault((p["platform"], p["channel"]), {"channel": p["channel"], "kind": p["kind"],
                                             "platform": p["platform"], "peak": 0, "hw": 0.0, "streams": 0, "air": 0})
        if p["hw"] >= ch.get("best_hw", -1):
            ch["best_hw"], ch["url"], ch["title"] = p["hw"], yt_link(p["vid"]), p["title"]
        ch["peak"] = max(ch["peak"], p["peak"])
        ch["hw"] += p["hw"]
        ch["streams"] += 1
        ch["air"] += p["air"]
    for ch in chans.values():
        ch["avg"] = ch["hw"] / (ch["air"] / 3600) if ch["air"] else 0
    out["channels"] = sorted(chans.values(), key=lambda c: -c["hw"])
    out["by_kind_hw"] = {k: sum(c["hw"] for c in chans.values() if c["kind"] == k)
                         for k in ("official", "watch party", "community")}
    # per platform: hours watched, own peak (from the 30s per-stream readings) and share of the event peak
    plat, pts, one = {}, {}, {(s["ts"], s["vid"]): s["viewers"] for s in samples}   # one reading per stream per second
    for (ts, vid), v in one.items():
        k = (ts, platforms.platform_of(vid))
        pts[k] = pts.get(k, 0) + v
    for (ts, pl), v in pts.items():
        x = plat.setdefault(pl, {"platform": pl, "name": platforms.NAMES[pl], "peak": 0, "peak_at": ts, "hw": 0.0})
        if v > x["peak"]:
            x.update(peak=v, peak_at=ts)
    for c_ in chans.values():
        if c_["platform"] in plat:
            plat[c_["platform"]]["hw"] += c_["hw"]
    out["platforms"] = sorted(plat.values(), key=lambda x: -x["hw"])
    # per day (event's local time)
    days, dayname = {}, {}

    def tday(t):   # one date conversion per half hour (IST is +5:30), not per 2s reading
        h = int(t["ts"]) // 1800
        if h not in dayname:
            dayname[h] = datetime.fromtimestamp(h * 1800, REPORT_TZ).strftime("%a %d %b")
        return dayname[h]
    for i, t in enumerate(ticks):
        d = tday(t)
        dd = days.setdefault(d, {"day": d, "peak": 0, "hw": 0.0, "air": 0})
        dt = min((ticks[i + 1]["ts"] - t["ts"]) if i + 1 < len(ticks) else POLL_SEC, gap_cap)
        dd["peak"] = max(dd["peak"], t["total"])
        if t["live"]:
            dd["hw"] += t["total"] * dt / 3600
            dd["air"] += dt
    for dd in days.values():
        dd["avg"] = dd["hw"] / (dd["air"] / 3600) if dd["air"] else 0
    out["days"] = list(days.values())
    # live now (last tick, if recent)
    last_ts = ticks[-1]["ts"]
    live_now = [s for s in samples if s["ts"] == last_ts] if time.time() - last_ts < POLL_SEC * 3 else []
    out["live_now"] = sorted((s for s in live_now if s["viewers"] > 0), key=lambda s: -s["viewers"])  # 0 = nobody watching
    # concurrent-viewer view: who made up the peak, each stream's own peak, averages while the official stream was on
    brk = store.kv_get(f"event_peak_break:{key}") or {}
    if brk.get("total") == peak["total"]:
        out["at_peak"] = brk["streams"]
    else:
        near = min({s["ts"] for s in samples} or {peak["ts"]}, key=lambda t: abs(t - peak["ts"]))
        out["at_peak"] = sorted((s for s in samples if s["ts"] == near), key=lambda s: -s["viewers"])
    fl = _FAST.get(key, {})
    if _LIVE.get(key) and fast_healthy():
        out["live_now"] = sorted(({**st, "viewers": fl[v]["viewers"]} for v, st in _LIVE[key].items()
                                  if v in fl and fl[v]["viewers"] > 0), key=lambda s: -s["viewers"])
    evx = get(key)
    if evx:
        out["live_now"] = [x for x in out["live_now"] if permitted(evx, x)]
    recent = time.time() - ticks[-1]["ts"] < 90 and not (_LIVE.get(key) and fast_healthy())
    if not out["live_now"] and recent:   # between per-stream saves: use each stream's latest saved reading
        lastv = {}
        for x in samples:
            if x["ts"] >= ticks[-1]["ts"] - 120:
                lastv[x["vid"]] = x
        out["live_now"] = sorted((x for x in lastv.values() if x["viewers"] > 0 and (not evx or permitted(evx, x))),
                                 key=lambda x: -x["viewers"])
    out["official_live"] = (recent and ticks[-1]["official"] > 0) or any(x["kind"] == "official" for x in out["live_now"]) \
        or (not need_official(evx) and bool(out["live_now"]))
    if paused(key) or (need_official(evx) and is_over(key)):
        out["official_live"] = False
    if not out["official_live"]:
        out["live_now"] = []          # only show streams while the official broadcast is on
    # broadcasts: runs of readings with no gap over 1 hour (restarts leave short gaps) (readings only exist while official was live)
    sess, cur = [], None
    for t in ticks:
        if cur and t["ts"] - cur["end"] <= 3600:
            cur["end"] = t["ts"]
            if t["total"] > cur["peak"]:
                cur.update(peak=t["total"], peak_at=t["ts"], split={k: t[k] for k in ("official", "watch", "community")})
        else:
            cur = {"start": t["ts"], "end": t["ts"], "peak": t["total"], "peak_at": t["ts"],
                   "split": {k: t[k] for k in ("official", "watch", "community")}}
            sess.append(cur)
    if sess:
        ls = dict(sess[-1])
        per, sums = {}, {}
        for x in samples:
            if ls["start"] - 60 <= x["ts"] <= ls["end"] + 60 and x["viewers"] > 0:
                a = sums.setdefault(x["vid"], [0, 0])
                a[0] += x["viewers"]
                a[1] += 1
            if ls["start"] - 60 <= x["ts"] <= ls["end"] + 60 and x["viewers"] > per.get(x["vid"], {}).get("peak", 0):
                per[x["vid"]] = {"vid": x["vid"], "channel": x["channel"], "title": x["title"], "kind": x["kind"],
                                 "platform": platforms.platform_of(x["vid"]),
                                 "channel_id": x.get("channel_id") or "",
                                 "peak": x["viewers"], "peak_at": x["ts"]}
        for v, p_ in per.items():
            p_["avg"] = round(sums[v][0] / sums[v][1]) if v in sums else 0
        ls["streams"] = sorted((p for p in per.values() if not taken_off(key, p)), key=lambda p: -p["peak"])
        bt = [t for t in ticks if ls["start"] <= t["ts"] <= ls["end"]]
        hw = air = 0.0
        for i, t in enumerate(bt):
            dt = min((bt[i + 1]["ts"] - t["ts"]) if i + 1 < len(bt) else POLL_SEC, gap_cap)
            hw += t["total"] * dt
            air += dt
        ls["avg"] = hw / air if air else 0
        ls["peak_official"] = max((t["official"] for t in bt), default=0)
        ls["peak_watch"] = max((t["watch"] for t in bt), default=0)
        out["last_broadcast"] = ls
    pl_used = sorted({platforms.platform_of(s["vid"]) for s in samples} - {"youtube"})
    out["platform_names"] = ["YouTube"] * any(not platforms.is_other(s["vid"]) for s in samples) + \
        [platforms.NAMES[p] for p in pl_used]
    out["method"] = (f"{_FASTSTATE['method']}, every {FAST_SEC * 2 ** _FASTSTATE.get('slow', 0):g}s" if fast_healthy()
                     else f"search results, every {POLL_SEC}s")
    with store.reading():
        out["stream_peaks"] = [dict(r) for r in _db().execute(
            "SELECT vid, channel, title, kind, peak, peak_at FROM ev_streams WHERE event=? AND peak>0 ORDER BY peak DESC",
            (key,))]
    bc = [(t, min((ticks[i + 1]["ts"] - t["ts"]) if i + 1 < len(ticks) else POLL_SEC, gap_cap))
          for i, t in enumerate(ticks) if t["official"] > 0]
    secs = sum(dt for _, dt in bc)
    out["avg_broadcast"] = sum(t["total"] * dt for t, dt in bc) / secs if secs else out["avg"]
    out["avg_official"] = sum(t["official"] * dt for t, dt in bc) / secs if secs else 0
    out["peak_official"] = max((t["official"] for t in ticks), default=0)
    out["peak_watch"] = max((t["watch"] for t in ticks), default=0)
    for d in out["days"]:
        day_bc = [(t, dt) for t, dt in bc if tday(t) == d["day"]]
        ds = sum(dt for _, dt in day_bc)
        d["avg_broadcast"] = sum(t["total"] * dt for t, dt in day_bc) / ds if ds else d["avg"]
        day_ticks = [t for t in ticks if tday(t) == d["day"]]
        top = max(day_ticks, key=lambda t: t["total"]) if day_ticks else None
        d["peak_at"] = top["ts"] if top else None
        d["split"] = {k: top[k] for k in ("official", "watch")} if top else {"official": 0, "watch": 0}
    out["series"] = [(t["ts"], t["total"], t["official"], t["watch"], t["community"]) for t in ticks]
    return out


_AV_BUSY = set()


def avatar(cid: str) -> str:
    """Channel logo URL (cached). Unknown ones are fetched in the background."""
    if not cid:
        return ""
    if platforms.is_other(cid):
        u = platforms.logo(cid)
        if u:
            if store.kv_get(f"ev_avatar:{cid}") != u:
                store.kv_set(f"ev_avatar:{cid}", u)
            return u
        return store.kv_get(f"ev_avatar:{cid}") or ""
    u = store.kv_get(f"ev_avatar:{cid}")
    if u is None and cid not in _AV_BUSY:
        _AV_BUSY.add(cid)

        def fetch():
            try:
                r = _http.get(f"https://www.youtube.com/channel/{cid}", headers={"User-Agent": _UA, "Accept-Language": "en"}, timeout=10)
                m = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
                store.kv_set(f"ev_avatar:{cid}", re.sub(r"=s\d+.*$", "=s88-c-k-c0x00ffffff-no-rj", m.group(1)) if m else "")
            except Exception:
                pass
            _AV_BUSY.discard(cid)
        _fast_pool.submit(fetch)
    return u or ""


def stream_series(key: str, vids: list, t0: float, t1: float, limit: int = 600) -> dict:
    """Per-stream viewer history (stored every ~30s) for the given streams."""
    if not vids:
        return {}
    with store.reading():
        rows = _db().execute(f"SELECT vid, ts, viewers FROM ev_samples WHERE event=? AND ts BETWEEN ? AND ? "
                             f"AND vid IN ({','.join('?' * len(vids))}) ORDER BY ts", (key, t0, t1, *vids)).fetchall()
    out = {}
    for vid, ts, v in rows:
        out.setdefault(vid, []).append([ts, v])
    for vid, pts in out.items():
        step = max(1, len(pts) // limit)
        out[vid] = pts[::step] + (pts[-1:] if (len(pts) - 1) % step else [])
    return out


_DAYS = {}


def day_streams(key: str, date: str) -> dict:
    """One IST day: every stream's peak (with time) and average while live, split into official/live streams and
    watch parties. Uses the full-resolution readings when that day has them, else the 30s samples."""
    try:
        d0 = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=REPORT_TZ).timestamp()
    except ValueError:
        return {}
    hit = _DAYS.get((key, date))
    today = datetime.now(REPORT_TZ).strftime("%Y-%m-%d")
    if hit and (date != today or time.time() - hit[0] < 30):
        return hit[1]
    d1 = d0 + 86400
    with store.reading():
        c = _db()
        table = "ev_fine" if c.execute("SELECT 1 FROM ev_fine WHERE event=? AND ts BETWEEN ? AND ? LIMIT 1",
                                       (key, d0, d1)).fetchone() else "ev_samples"
        rows = c.execute(f"SELECT vid, MAX(viewers) AS peak, ts AS at, AVG(viewers) AS avg FROM {table} "
                         f"WHERE event=? AND ts BETWEEN ? AND ? AND viewers>0 GROUP BY vid", (key, d0, d1)).fetchall()
        meta = {r["vid"]: dict(r) for r in c.execute("SELECT vid, channel, channel_id, title, kind FROM ev_streams WHERE event=?",
                                                    (key,))}
    out = {"date": date, "official": [], "watch": []}
    g = ((get(key) or {}).get("game") or PRESETS.get(key, {}).get("game") or "").lower()
    pubg = g in ("pubg mobile", "bgmi", "pubg: battlegrounds") or key in ("pmgc",)
    for r in sorted(rows, key=lambda r: -r["peak"]):
        m = meta.get(r["vid"], {})
        if not m or taken_off(key, {"vid": r["vid"], "channel_id": m.get("channel_id")}):
            continue
        name = m.get("channel", "")
        tag = re.search(r"\[([^\]]{2,20})\]", m.get("title", "")) if m.get("kind") == "official" else None
        if tag and pubg:   # KRAFTON's channel runs several language streams at once: say which one
            name = f"KRAFTON {tag.group(1).upper()}"
        elif tag and f"[{tag.group(1).upper()}]" not in name.upper():   # other publishers keep their own name (28 Nov: FFWS
            name = f"{name} [{tag.group(1).upper()}]"                  # showed 'KRAFTON PT-BR' for Garena's channels)
        x = {"vid": r["vid"], "channel": name, "title": m.get("title", ""), "kind": m.get("kind", ""),
             "platform": platforms.platform_of(r["vid"]),
             "logo": avatar(m.get("channel_id", "")), "url": yt_link(r["vid"]), "peak": int(r["peak"]),
             "at": datetime.fromtimestamp(r["at"], REPORT_TZ).strftime("%I:%M %p"), "avg": int(round(r["avg"] or 0))}
        out["watch" if x["kind"] == "watch party" else "official"].append(x)
    _DAYS[(key, date)] = (time.time(), out)
    return out


def stream_tail(key: str, vids: list, n: int = 90) -> dict:
    h = _HIST.get(key, {})
    return {v: [list(x) for x in list(h[v])[-n:]] for v in vids if v in h}


ROSTER = [  # BMSD 2026: (match token, display name, channel handle) of the permitted watch-party streamers
    ("dynamo", "Dynamo Gaming", "@DynamoGaming"), ("bixi", "Bixi", "@TheBixiOP"), ("zgod", "ZGOD Gaming", "@ZGODGAMING"),
    ("neyoo", "Neyoo Gaming", "@NEYOOGAMINGYT"), ("mizo", "Mizo Plays", "@MizoPlays"), ("mrspike", "Mr Spike", "@MrSpike"),
    ("lolzz", "LoLzZz Gaming", "@LoLzZzGaming"), ("sharkshe", "Sharkshe", "@SHARKSHE"), ("mafianinja", "Mafia Ninja", "@MafiaNinja"),
    ("ruthless", "Im Ruthless", "@ImRuthlessceopubg"), ("rakazone", "RakaZone Gaming", "@RakaZoneGaming"), ("ansh", "Ansh YT", "@AnshYT"),
    ("casetoo", "Casetoo", "@Casetoolive"), ("sheek", "Sheek Gaming", "@sheekgaming"), ("ipreeet", "iPreeet", "@IPREEET.69"),
    ("shreeman", "Shreeman Legend", "@shreemanlegendliveofficial"), ("mortal", "MortaL", "@MortaLyt"), ("vaadhiyaar", "Vaadhiyaar", "@VAADHIYAAR"),
    ("regaltos", "Soul Regaltos", "@soulregaltos9810"), ("snax", "Snax Gaming", "@SnaxGaming"), ("sriop", "SRI OP", "@sriop-sr70"),
    ("neonxpawan", "Neon X Pawan", "@NEONXPAWANOP"),
    ("ladypredator", "Lady Predator", "@LadyPredatorGaming"), ("soulaman", "Soul Aman", "@SoulAman")]
ROSTER_BMIC = [  # BMIC 2026 permitted watch parties (owner's list, 29 Oct). None = handle found by YouTube search on startup
    ("snax", "Snax Gaming", "@SnaxGaming"), ("mrspike", "Mr Spike", "@MrSpike"), ("soulaman", "Soulaman", "@SoulAman"),
    ("bixi", "Bixi Op", "@TheBixiOP"), ("hrishav", "HYDRA HRISHAV", None), ("8bitbeg", "8bitBEG4MERCY", None),
    ("ipreeet", "ipreeet", "@IPREEET.69"), ("ladypredator", "Lady Predator", "@LadyPredatorGaming"),
    ("cyanide", "CYANIDE GAMING", None), ("manfster", "MANFSTER", None), ("warriorislive", "WarriorislivE", None),
    ("ravensharp", "RavenSharp", None), ("iflicks", "iFlicks", None), ("aaru", "Aaru", None), ("mafianinja", "Mafianinja", "@MafiaNinja"),
    ("gamezo", "GAMEZO TECH", None), ("stone", "STONE BGMI", None), ("juniorgaming", "Junior Gaming", None),
    ("engineer", "Engineer YT", None), ("sriop", "SRI OP", "@sriop-sr70"), ("lolzz", "Lolzzz Gaming", "@LoLzZzGaming"),
    ("shreeman", "Shreeman Legend", "@shreemanlegendliveofficial")]
ROSTERS = {"bmsd": ROSTER, "bmic": ROSTER_BMIC}   # per event
_RRES = {"at": 0.0}


def _resolve_roster(key: str):
    """Find the YouTube channel of every roster streamer listed without a handle (YouTube's own channel search, no
    API quota). Kept in kv roster_ids:<key>; a name that isn't found is retried every hour."""
    from tracker import ytextra
    ids = store.kv_get(f"roster_ids:{key}") or {}
    for token, name, handle in ROSTERS.get(key, []):
        if handle or ids.get(token):
            continue
        try:
            for x in ytextra.yt_channel_search(name, gl="IN")[:6]:
                if token in _norm(x.get("name", "")) or token in _norm(x.get("handle", "")):
                    ids[token] = x["sid"][3:]
                    break
        except Exception as e:
            print(f"Roster {name}: {str(e)[:80]}")
    store.kv_set(f"roster_ids:{key}", ids)


def roster(key: str) -> list:
    """[(token, name, handle or channel id)] of an event's permitted watch-party streamers."""
    L = ROSTERS.get(key, [])
    ids = store.kv_get(f"roster_ids:{key}") or {}
    if any(h is None and not ids.get(t) for t, _, h in L) and time.time() - _RRES["at"] > 3600:
        _RRES["at"] = time.time()
        threading.Thread(target=_resolve_roster, args=(key,), daemon=True).start()
    return [(t, n, h or ids.get(t)) for t, n, h in L]


_RBUSY = set()


def channel_card(handle: str) -> dict:
    """{name, logo} for a channel handle (cached; fetched in the background the first time)."""
    if not handle:
        return {}
    v = store.kv_get(f"ev_rcard:{handle}")
    if v is None and handle not in _RBUSY:
        _RBUSY.add(handle)

        def fetch():
            try:
                r = _http.get(f"https://www.youtube.com/channel/{handle}" if handle.startswith("UC") else f"https://www.youtube.com/{handle}", headers={"User-Agent": _UA, "Accept-Language": "en"}, timeout=10)
                img = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
                name = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
                store.kv_set(f"ev_rcard:{handle}", {
                    "logo": re.sub(r"=s\d+.*$", "=s88-c-k-c0x00ffffff-no-rj", img.group(1)) if img else "",
                    "name": name.group(1).replace("&amp;", "&") if name else ""})
            except Exception:
                pass
            _RBUSY.discard(handle)
        _fast_pool.submit(fetch)
    return v or {}


def next_start(key: str):
    """Next scheduled official start (epoch) if it's in the future: else the preset."""
    if PRESETS.get(key, {}).get("ended"):
        return None
    v = store.kv_get(f"event_next:{key}") or PRESETS.get(key, {}).get("next_start")
    if not v:
        return None
    try:
        ts = datetime.strptime(v, "%Y-%m-%d %H:%M").replace(tzinfo=REPORT_TZ).timestamp() if isinstance(v, str) else float(v)
    except ValueError:
        return None
    return ts if ts > time.time() else None


def fmt_n(n) -> str:
    n = float(n or 0)
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e4:
        return f"{n / 1e3:.1f}K"
    return f"{int(round(n)):,}"


def _when(ts) -> str:
    return datetime.fromtimestamp(ts, REPORT_TZ).strftime("%a %d %b, %I:%M %p IST")


def _ptag(vid: str) -> str:
    p = platforms.platform_of(vid)
    return "" if p == "youtube" else f"{platforms.NAMES[p]}, "


def summary(key: str = None, top: int = 10) -> str:
    ev = get(key)
    if not ev:
        return "No event is being tracked. Start one with: python track.py create bmsd"
    st = stats(ev["key"])
    if not st.get("ticks"):
        return (f"{ev['name']}: tracking, but no data yet. The first numbers appear within {POLL_SEC}s of a "
                "live stream being found.")
    lines = [f"{ev['name']}: concurrent viewers ({', '.join(st.get('platform_names') or ['YouTube'])}, all streams)"]
    if st["live_now"]:
        lines.append(f"\nLIVE NOW: {fmt_n(sum(s['viewers'] for s in st['live_now']))} viewers across "
                     f"{len(st['live_now'])} streams")
        for s in st["live_now"]:
            lines.append(f"  {fmt_n(s['viewers'])}  {s['channel']} ({_ptag(s['vid'])}{s['kind']})\n     {yt_link(s['vid'])}")
    else:
        lines.append("\nOfficial broadcast is offline (numbers are recorded only while it's live).")
        lb = st.get("last_broadcast")
        if lb:
            lines.append(f"\nLAST BROADCAST ({_when(lb['start'])} to {datetime.fromtimestamp(lb['end'], REPORT_TZ).strftime('%I:%M %p')}):"
                         f"\n  peak {fmt_n(lb['peak'])} concurrent at {_when(lb['peak_at'])}")
            for x in lb["streams"][:8]:
                lines.append(f"  {fmt_n(x['peak'])}  {x['channel']} ({_ptag(x['vid'])}{x['kind']})\n     {yt_link(x['vid'])}")
    sp = st["peak_split"]
    lines += [f"\nPEAK CONCURRENT: {fmt_n(st['peak'])} at {_when(st['peak_at'])}",
              f"  official {fmt_n(sp['official'])}, watch parties {fmt_n(sp['watch'])}, community {fmt_n(sp['community'])}"]
    lines += [f"\nAverage concurrent while the official broadcast was live: {fmt_n(st['avg_broadcast'])}",
              f"Official streams: peak {fmt_n(st['peak_official'])}, average {fmt_n(st['avg_official'])}",
              f"Watch parties combined: peak {fmt_n(st['peak_watch'])}"]
    if len(st["days"]) > 1:
        lines.append("\nBy day (IST): peak / average concurrent")
        lines += [f"  {d['day']}: {fmt_n(d['peak'])} / {fmt_n(d['avg_broadcast'])}" for d in st["days"]]
    if len(st.get("platforms") or []) > 1:
        lines.append("\nBy platform: peak / hours watched")
        lines += [f"  {x['name']}: {fmt_n(x['peak'])} / {fmt_n(x['hw'])}h" for x in st["platforms"]]
    lines.append(f"\nCounted from: {st.get('method')}.")
    for label, url in (ev.get("links") or {}).items():
        lines.append(f"{label}: {url}")
    return "\n".join(lines)


def tool_event_stats(name: str = "") -> str:
    """For the agent: 'what's the peak so far?'"""
    return summary(name or None, top=15)
