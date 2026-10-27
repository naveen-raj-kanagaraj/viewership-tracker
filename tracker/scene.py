"""India live streaming: every stream we can find on YouTube, Kick and Twitch, sorted into games and ranked.

Not tied to an event. Every SCENE_SEC (120s):
  1. Kick and Twitch: every live stream in the India languages (SCENE_LANGS, default hi), top 100 per language
     (needs the platform keys), plus the channels added by hand (Kick works without keys).
  2. YouTube: India-localised live searches for each game (every SCENE_YT_SEC, 300s; every 15 min while an event's
     official broadcast is live so the event counter keeps priority), plus the channels added by hand. Streams already
     found are re-counted every cycle from YouTube's live counter.
  3. Each channel's viewers are stored (sc_samples, kept SCENE_KEEP_DAYS) and rolled up per IST day (sc_daily, kept).

A streamer is one channel on one platform: yt:<channel id>, kick:<slug>, twitch:<login>. Two streams at once on the
same channel are added together. Streams under SCENE_MIN_VIEWERS are ignored.

Discovery is not a census: a YouTube stream that never appears in these searches and isn't added by hand is missed,
and Kick/Twitch are filtered by stream language. The page says so.
"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from tracker import events, platforms, store

SCENE_SEC = int(os.getenv("SCENE_SEC", "120"))
SCENE_YT_SEC = int(os.getenv("SCENE_YT_SEC", "300"))
MIN_VIEWERS = int(os.getenv("SCENE_MIN_VIEWERS", "20"))
KEEP_DAYS = int(os.getenv("SCENE_KEEP_DAYS", "3"))         # raw per-scan readings; per-day totals are kept for good
GLOBAL_MIN = int(os.getenv("SCENE_GLOBAL_MIN", "100"))     # non-Indian streams smaller than this are left out
TWITCH_PAGES = int(os.getenv("SCENE_TWITCH_PAGES", "5"))   # global Twitch: top 100 x this many
YT_RECOUNT = int(os.getenv("SCENE_YT_RECOUNT", "400"))     # YouTube streams re-counted each scan (biggest first)
FAST_MAX = int(os.getenv("SCENE_FAST_MAX", "300"))         # Kick/Twitch channels re-read every 2s (biggest first)
LANGS = [x.strip() for x in os.getenv("SCENE_LANGS", "hi").split(",") if x.strip()]
# Kick and Twitch have no country filter. Besides the India languages above, the top streams overall and in the
# categories Indians stream most are read, and a stream counts as Indian if its title is written in an Indian script
# or says so (hindi, india, desi, tamil, bgmi ...).
INDIA_MARK = re.compile(r"[\u0900-\u0D7F]|\b(hindi|india|indian|desi|bharat|hinglish|tamil|telugu|kannada|malayalam|"
                        r"marathi|bengali|bangla|punjabi|gujarati|odia|assamese|bgmi|bmps|bgis|bmsd|bmic|"
                        r"soulcity|mumbai|delhi|bangalore|bengaluru|hyderabad|chennai|kolkata|pune)\b", re.I)
INDIA_CATS = {"kick": [x.strip() for x in os.getenv("SCENE_KICK_CATS", "PUBG Mobile,Free Fire,Grand Theft Auto V,"
                                                   "Valorant,Just Chatting,Battlegrounds Mobile India").split(",") if x.strip()],
              "twitch": [x.strip() for x in os.getenv("SCENE_TWITCH_CATS", "PUBG MOBILE,Garena Free Fire,Grand Theft Auto V,"
                                                     "VALORANT,Just Chatting,Battlegrounds Mobile India").split(",") if x.strip()]}


# Titles in Chinese, Japanese, Korean, Thai, Arabic or Cyrillic script are not Indian streams even when the
# streamer tagged them Hindi (it happens on Twitch).
FOREIGN = re.compile(r"[\u0400-\u04FF\u0600-\u06FF\u0E00-\u0E7F\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]")


def indian(row: dict) -> bool:
    t = row.get("title") or ""
    if FOREIGN.search(t + " " + (row.get("channel") or "")) and not INDIA_MARK.search(t):
        return False
    return (row.get("language") or "").lower() in LANGS or bool(INDIA_MARK.search(t))


# ---------- is this channel Indian? ----------
# YouTube: the channel's own country setting decides (India = yes, any other country = no). Only when a channel has
# set no country do the signals below decide: an Indian script or Indian words in the title or name. Kick and
# Twitch expose no country, so they always go by the stream's language tag (hi ...) and the same signals.
# Channels added by hand (`scene add`) or allowed (`scene allow`) always count; blocked ones never do.
_CTRY = {}      # YouTube channel id -> 'IN', another code, or '-' (looked up, none set)


def _norm_country(v: str) -> str:
    v = (v or "").strip()
    return "IN" if v.lower() in ("in", "india") else (v or "-")


def yt_countries(cids: list) -> dict:
    """Country each YouTube channel has set. YouTube Data API when YOUTUBE_API_KEY is set (1 quota unit per 50
    channels), else the channel's About page. Missing entries mean the lookup failed (tried again later)."""
    out, key = {}, os.getenv("YOUTUBE_API_KEY")
    if not cids:
        return out
    if key:
        for i in range(0, len(cids), 50):
            r = events._http.get("https://www.googleapis.com/youtube/v3/channels",
                                 params={"part": "snippet", "id": ",".join(cids[i:i + 50]), "key": key}, timeout=15)
            r.raise_for_status()
            got = {it["id"]: _norm_country((it.get("snippet") or {}).get("country")) for it in r.json().get("items", [])}
            for cid in cids[i:i + 50]:
                out[cid] = got.get(cid, "-")
        return out

    def page(cid):
        try:
            r = events._http.get(f"https://www.youtube.com/channel/{cid}/about", timeout=10,
                                 headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                                 cookies={"CONSENT": "YES+", "SOCS": "CAI"})
            if r.status_code != 200:
                return cid, None
            m = re.search(r'"country"\s*:\s*"([^"]+)"', r.text)
            return cid, _norm_country(m.group(1) if m else "")
        except Exception:
            return cid, None
    for cid, v in _pool.map(page, cids):
        if v is not None:
            out[cid] = v
    return out


def _load_countries():
    if _CTRY:
        return
    with store._lock:
        for sid, ctry in _db().execute("SELECT sid, country FROM sc_channels WHERE platform='youtube' AND country IS NOT NULL"):
            _CTRY[sid[3:]] = ctry
    _CTRY.setdefault("", "-")


def allowed() -> set:
    return set(store.kv_get("scene_allowed") or [])


def verdict(x: dict, country: str = None, allow: set = frozenset()) -> bool:
    """True if this live channel counts as Indian."""
    sid, t, n = x.get("sid", ""), x.get("title") or "", x.get("name") or ""
    if sid in allow or x.get("seeded"):
        return True
    if x.get("platform") == "youtube":
        if country == "IN":
            return True
        if country and country != "-":
            return False                      # the channel says it is from another country
    elif (x.get("language") or "").lower() in LANGS and not FOREIGN.search(t + " " + n):
        return True
    if FOREIGN.search(t + " " + n) and not re.search(r"[\u0900-\u0D7F]", t + n):
        return False
    return bool(re.search(r"[\u0900-\u0D7F]", t + " " + n) or INDIA_MARK.search(t) or INDIA_MARK.search(n))


def _kick_live(params) -> list:
    j = platforms._get("kick", "https://api.kick.com/public/v1/livestreams", {"sort": "viewer_count", "limit": 100, **params})
    return [platforms._kick_row(s.get("slug") or "", s.get("stream_title"), s.get("viewer_count"),
                                category=(s.get("category") or {}).get("name", ""), pic=s.get("profile_picture") or "",
                                language=s.get("language") or "", uid=s.get("broadcaster_user_id"))
            for s in j.get("data") or [] if s.get("slug")]


def _category_id(p: str, name: str):
    k = (p, name.lower())
    if k not in platforms._cats:
        if p == "twitch":
            g = platforms._get("twitch", "https://api.twitch.tv/helix/games", {"name": name}).get("data") or []
            platforms._cats[k] = g[0]["id"] if g else ""
        else:
            c = platforms._get("kick", "https://api.kick.com/public/v1/categories", {"q": name}).get("data") or []
            hit = next((x for x in c if (x.get("name") or "").lower() == name.lower()), c[0] if c else None)
            platforms._cats[k] = hit["id"] if hit else ""
    return platforms._cats[k]


def platform_global(p: str, errors: dict) -> list:
    """The biggest live streams anywhere on Kick or Twitch, plus the official esports channels on Twitch."""
    rows = []
    try:
        if p == "twitch":
            after = None
            for _ in range(TWITCH_PAGES):
                prm = {"first": 100, **({"after": after} if after else {})}
                j = platforms._get("twitch", "https://api.twitch.tv/helix/streams", prm)
                for s_ in j.get("data") or []:
                    login = (s_.get("user_login") or "").lower()
                    rows.append({"vid": f"twitch:{login}", "channel": s_.get("user_name") or login,
                                 "title": s_.get("title") or "", "viewers": int(s_.get("viewer_count") or 0),
                                 "category": s_.get("game_name") or "", "language": s_.get("language") or ""})
                after = (j.get("pagination") or {}).get("cursor")
                if not after or (j.get("data") and j["data"][-1].get("viewer_count", 0) < GLOBAL_MIN):
                    break
            rows += platforms._tw_logins(ESPORTS_TWITCH)
        else:
            rows += _kick_live({})
    except Exception as e:
        errors[f"{p} global"] = str(e)[:120]
    return rows


def platform_india(p: str, errors: dict) -> list:
    """Indian live streams on Kick or Twitch: the India languages, plus the top streams overall and in the main
    Indian categories whose language or title marks them as Indian."""
    rows, wide = [], []
    get = (lambda prm: platforms._tw_streams({"first": 100, **prm})) if p == "twitch" else _kick_live
    for lang in LANGS:
        try:
            rows += get({"language": lang})
        except Exception as e:
            errors[f"{p} language {lang}"] = str(e)[:120]
    try:
        wide += get({})
    except Exception as e:
        errors[f"{p} top streams"] = str(e)[:120]
    for name in INDIA_CATS[p]:
        try:
            cid = _category_id(p, name)
            if cid:
                wide += get({"game_id": cid} if p == "twitch" else {"category_id": cid})
        except Exception as e:
            errors[f"{p} category {name}"] = str(e)[:120]
    return [r for r in rows + wide if indian(r)]

# (game, words in a platform category or a stream title). Order matters: the first match wins.
GAMES = [
    ("PUBG: Battlegrounds", ["pubg: battlegrounds", "pubg pc", "pubg battlegrounds", "pubg steam"]),
    ("BGMI", ["bgmi", "battlegrounds mobile india", "bmps", "bgis", "bmsd", "bmic", "bmoc"]),
    ("PUBG Mobile", ["pubg mobile", "pmgc", "pmwi", "pmsl", "pmpl", "pmrc", "battlegrounds mobile", "pubg"]),
    ("Mobile Legends", ["mobile legends", "mlbb", "mpl ", "msc "]),
    ("Rocket League", ["rocket league", "rlcs"]),
    ("Overwatch 2", ["overwatch", "owcs"]),
    ("Free Fire", ["free fire", "freefire", "ff max", "garena"]),
    ("GTA V", ["gta", "grand theft auto", "soulcity", "soul city rp"]),
    ("Valorant", ["valorant", "valo "]),
    ("Minecraft", ["minecraft"]),
    ("COD Mobile", ["cod mobile", "call of duty mobile", "codm", "call of duty: mobile"]),
    ("Call of Duty: Warzone", ["warzone"]),
    ("Call of Duty: Black Ops 7", ["black ops 7", "bo7"]),
    ("Call of Duty: Black Ops 6", ["black ops 6", "bo6"]),
    ("Call of Duty", ["call of duty"]),
    ("Counter-Strike 2", ["counter-strike", "counter strike", "cs2", "csgo", "cs:go"]),
    ("Indus", ["indus battle royale", "indus game"]),
    ("Clash of Clans", ["clash of clans"]),
    ("Clash Royale", ["clash royale"]),
    ("Pokemon Unite", ["pokemon unite", "pokémon unite"]),
    ("Fortnite", ["fortnite"]),
    ("Apex Legends", ["apex legends"]),
    ("Roblox", ["roblox"]),
    ("Dota 2", ["dota"]),
    ("League of Legends", ["league of legends"]),
    ("EA Sports FC", ["ea sports fc", "ea fc", "fifa"]),
    ("Cricket games", ["real cricket", "cricket 24", "cricket 22", "world cricket championship", "wcc3"]),
    ("Chess", ["chess"]),
    ("Among Us", ["among us"]),
    ("Cricket (live)", ["ipl", "live cricket", "cricket live", "ind vs", "india vs", "t20", " odi ", "test match"]),
    ("News", ["news", "khabar", "samachar", "headlines", "breaking", "aaj tak", "ndtv", "republic", "tv9", "abp ",
              "zee ", "india tv", "lok sabha", "rajya sabha", "sansad"]),
    ("Devotional", ["bhajan", "aarti", "kirtan", "gurbani", "darshan", "katha", "satsang", "mandir", "temple", "puja",
                    "pooja", "mantra", "chalisa", "namaz", "jagran"]),
    ("Music", ["songs", "song", "music", "lofi", "lo-fi", "radio", "jukebox"]),
    ("Podcast / Talk", ["podcast", "talk show", "interview", "debate"]),
    ("IRL", ["irl", "vlog", "travel", "walking tour", "road trip", "outdoors", "food & drink", "cooking"]),
    ("Just Chatting", ["just chatting", "chatting", "q&a", "q & a"]),
]
# YouTube searches (India region). Each finds up to ~20 live streams.
QUERIES = ["BGMI live", "BGMI live tamil", "BGMI live telugu", "Free Fire live", "Free Fire max live hindi",
           "GTA 5 live hindi", "GTA 5 roleplay live hindi", "Valorant live hindi", "Minecraft live hindi",
           "COD mobile live india", "Indus battle royale live", "Pokemon Unite live hindi", "CS2 live hindi",
           "Clash of Clans live hindi", "Real cricket live", "hindi gaming live", "tamil gaming live",
           "telugu gaming live", "PUBG PC live hindi", "Roblox live hindi",
           # beyond gaming: everything live in India
           "live hindi", "live stream india", "news live hindi", "live tamil", "live telugu", "live bengali",
           "live marathi", "live kannada", "live malayalam", "live gujarati", "live punjabi", "bhajan live",
           "live darshan", "cricket live", "podcast live hindi", "live chat hindi", "music live hindi"]
LIVE_PAGE = "UC4R8DWoMoI7CAwX8_LjQHig"   # YouTube's own "Live" page, India edition: what's trending live now
# Global YouTube searches (run from the US edition of YouTube): every big game, esports, and the main non-gaming
# categories. Each finds up to ~20 live streams.
YT_GL = [g.strip().upper() for g in os.getenv("SCENE_YT_COUNTRIES", "BR,MX,AR,ES,GB,DE,FR,TR,RU,ID,PH,VN,TH,JP,KR,PK,BD,SA,EG,NG").split(",") if g.strip()]
GLOBAL_QUERIES = ["live gaming", "esports live", "tournament live", "grand finals live", "valorant live", "vct live",
                  "league of legends live", "lck live", "counter strike live", "cs2 major", "dota 2 live",
                  "fortnite live", "minecraft live", "gta rp live", "call of duty live", "apex legends live",
                  "pubg mobile live", "free fire live", "mobile legends live", "mpl live", "roblox live",
                  "ea fc live", "rocket league live", "overwatch live", "chess live", "pokemon live",
                  "just chatting live", "irl stream", "news live", "music live", "sports live", "podcast live"]
ESPORTS_TWITCH = ["riotgames", "valorant", "lck", "lec", "lcs", "lolesports", "eslcs", "esl_csgo", "blastpremier",
                  "pgl", "pgl_cs2", "esl_dota2", "pgl_dota2", "rainbow6", "playapex", "rocketleague", "ewc",
                  "callofdutyleague", "overwatchleague", "esl_sc2", "fortnite", "valorant_americas", "valorant_emea",
                  "valorant_pacific", "dreamhackcs", "pubg_battlegrounds"]
# Tournaments: (pattern, name, game it must be, if any). Specific names first.
TOURNAMENTS = [
    (r"\bvct\b.*challengers|valorant challengers", "VCT Challengers", None), (r"game changers", "VCT Game Changers", None),
    (r"\bvct\b|valorant champions tour|valorant masters|valorant champions\b", "VCT", None),
    (r"\blck\b", "LCK", None), (r"\blec\b", "LEC", None), (r"\blcs\b", "LCS", None), (r"\blpl\b", "LPL", None),
    (r"\bmsi\b", "MSI", "League of Legends"), (r"\bworlds\b", "LoL Worlds", "League of Legends"),
    (r"esl pro league", "ESL Pro League", None), (r"\biem\b|intel extreme masters", "IEM", None),
    (r"blast (premier|open|slam|bounty|major|austin)|blast\.tv", "BLAST", None), (r"\bpgl\b", "PGL", None),
    (r"\bcct\b", "CCT", None), (r"\besl\b", "ESL", None),
    (r"the international|\bti ?20\d\d\b", "The International", "Dota 2"),
    (r"esports world cup|\bewc\b", "Esports World Cup", None),
    (r"\bpmgc\b|pubg mobile global championship", "PMGC", None), (r"\bpmwi\b", "PMWI", None),
    (r"\bpmsl\b", "PMSL", None), (r"\bpmpl\b", "PMPL", None), (r"\bpmrc\b", "PMRC", None),
    (r"\bbgis\b", "BGIS", None), (r"\bbmps\b", "BMPS", None), (r"\bbmsd\b", "BMSD", None), (r"\bbmic\b", "BMIC", None),
    (r"\bbmoc\b", "BMOC", None), (r"\bffws\b|free fire world series", "FFWS", None), (r"\bffic\b", "FFIC", None),
    (r"\bmpl\b", "MPL", None), (r"\bmsc\b", "MSC", None), (r"\bm[5-9] world championship", "MLBB M-Series", None),
    (r"\brlcs\b", "RLCS", None), (r"\bcdl\b|call of duty league", "CDL", None), (r"\bowcs\b", "OWCS", None),
    (r"\balgs\b", "ALGS", None), (r"\bfncs\b", "FNCS", None), (r"\bdreamhack\b", "DreamHack", None),
    (r"\bcegc\b", "CEGC", None), (r"sky ?esports", "Sky Esports", None), (r"upthrust", "Upthrust Esports", None)]
_T_RX = [(re.compile(p, re.I), n, g) for p, n, g in TOURNAMENTS]
_T_GENERIC = re.compile(r"\b(championship|grand finals?|finals|playoffs|qualifiers?|tournament|invitational|world cup|"
                        r"league|major|showdown)\b", re.I)
_T_MATCH = re.compile(r"\b(vs\.?|day \d+|week \d+|match \d+|stage|group [a-z0-9]|round|semi ?finals?|quarter ?finals?|"
                      r"bracket|map \d)\b", re.I)
_T_NOT = re.compile(r"\bscrims?\b|\branked\b|\bcustom room|\bpublic match", re.I)


TOUR_GAME = {"VCT": "Valorant", "VCT Challengers": "Valorant", "VCT Game Changers": "Valorant",
             "LCK": "League of Legends", "LEC": "League of Legends", "LCS": "League of Legends", "LPL": "League of Legends",
             "MSI": "League of Legends", "LoL Worlds": "League of Legends", "ESL Pro League": "Counter-Strike 2",
             "IEM": "Counter-Strike 2", "BLAST": "Counter-Strike 2", "PGL": "Counter-Strike 2", "CCT": "Counter-Strike 2",
             "The International": "Dota 2", "PMGC": "PUBG Mobile", "PMWI": "PUBG Mobile", "PMSL": "PUBG Mobile",
             "PMPL": "PUBG Mobile", "PMRC": "PUBG Mobile", "BGIS": "BGMI", "BMPS": "BGMI", "BMSD": "BGMI", "BMIC": "BGMI",
             "BMOC": "BGMI", "FFWS": "Free Fire", "FFIC": "Free Fire", "MPL": "Mobile Legends", "MSC": "Mobile Legends",
             "MLBB M-Series": "Mobile Legends", "RLCS": "Rocket League", "CDL": "Call of Duty", "OWCS": "Overwatch 2",
             "ALGS": "Apex Legends", "FNCS": "Fortnite"}


def tournament(title: str, game: str = ""):
    """The tournament a stream is broadcasting or co-streaming, or None."""
    t = title or ""
    if _T_NOT.search(t):
        return None
    for rx, name, g in _T_RX:
        if rx.search(t) and (not g or g == game or game in ("", "Other")):
            return name
    if _T_GENERIC.search(t) and _T_MATCH.search(t):
        return f"{game} tournaments" if game and game != "Other" else "Other tournaments"
    return None
SEEDS = {"kick": ["skyesports", "cegc"], "twitch": [],
         "youtube": ["@SoulAman", "@DynamoGaming", "@TheBixiOP", "@ZGODGAMING", "@NEYOOGAMINGYT", "@MizoPlays",
                     "@MrSpike", "@LoLzZzGaming", "@SHARKSHE", "@MafiaNinja", "@ImRuthlessceopubg", "@RakaZoneGaming",
                     "@AnshYT", "@Casetoolive", "@sheekgaming", "@IPREEET.69", "@shreemanlegendliveofficial",
                     "@MortaLyt", "@VAADHIYAAR", "@soulregaltos9810", "@SnaxGaming", "@sriop-sr70", "@NEONXPAWANOP",
                     "@LadyPredatorGaming"]}

_SEEDED = set()       # YouTube channels found through hand-added @handles: always Indian
_LIVE = {}            # sid -> {"sid","platform","name","url","logo","game","title","streams": {vid: viewers},"seen","errs"}
_STATE = {"last": 0.0, "yt": 0.0, "seeds": 0.0, "errors": {}, "running": False}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=8)


def _db():
    c = store.conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS sc_channels (sid TEXT PRIMARY KEY, platform TEXT, name TEXT, url TEXT, logo TEXT,
        first_seen REAL, last_live REAL, title TEXT, game TEXT);
    CREATE TABLE IF NOT EXISTS sc_samples (ts INTEGER, sid TEXT, viewers INTEGER, game TEXT);
    CREATE INDEX IF NOT EXISTS sc_samples_ix ON sc_samples(ts);
    CREATE TABLE IF NOT EXISTS sc_daily (day TEXT, sid TEXT, game TEXT, peak INTEGER, peak_at INTEGER, mins REAL,
        hw REAL, PRIMARY KEY (day, sid, game));
    CREATE INDEX IF NOT EXISTS sc_daily_game ON sc_daily(game, day);
    CREATE TABLE IF NOT EXISTS sc_cat (ts INTEGER, game TEXT, viewers INTEGER, streams INTEGER, PRIMARY KEY (game, ts));
    CREATE TABLE IF NOT EXISTS sc_reg (ts INTEGER, region TEXT, game TEXT, viewers INTEGER, streams INTEGER,
        PRIMARY KEY (region, game, ts));
    """)
    if not _COLS and not store.kv_get("scene_mig_pubg"):
        for t in ("sc_samples", "sc_daily", "sc_cat", "sc_reg", "sc_channels"):
            try:
                c.execute(f"UPDATE OR IGNORE {t} SET game='PUBG: Battlegrounds' WHERE game='PUBG PC'")
            except Exception:
                pass
        c.commit()
        store.kv_set("scene_mig_pubg", True)
    if not _COLS:
        have = {r[1] for r in c.execute("PRAGMA table_info(sc_channels)")}
        for col, typ in (("country", "TEXT"), ("india", "INTEGER"), ("language", "TEXT")):
            if col not in have:
                c.execute(f"ALTER TABLE sc_channels ADD COLUMN {col} {typ}")
        c.commit()
        _COLS.append(1)
    return c


_COLS = []


def slug(game: str) -> str:
    """URL name of a category: 'Free Fire' -> 'free-fire'."""
    return re.sub(r"[^a-z0-9]+", "-", (game or "").lower()).strip("-") or "other"


ALL = "__all__"          # the India-wide total in sc_cat
NON_GAMING = {"News", "Devotional", "Music", "Podcast / Talk", "Just Chatting", "IRL", "Cricket (live)", "Other"}
# Top-level sections shown in the site's menu. A stream's section comes from its tournament (Esports) or its game/category.
SECTIONS = [("gaming", "Gaming"), ("esports", "Esports"), ("irl", "IRL"), ("just-chatting", "Just Chatting"),
            ("news", "News"), ("music", "Music"), ("sports", "Sports"), ("devotional", "Devotional"),
            ("podcasts", "Podcasts & Talk"), ("other", "Other")]
SECTION_NAMES = dict(SECTIONS)
_SEC_FIXED = {"Just Chatting": "just-chatting", "IRL": "irl", "News": "news", "Music": "music",
              "Cricket (live)": "sports", "Devotional": "devotional", "Podcast / Talk": "podcasts", "Other": "other"}
_SEC_WORDS = [("irl", ("irl", "travel", "outdoor", "food", "cooking", "vlog")), ("sports", ("sport", "football", "cricket",
              "basketball", "wrestling", "racing")), ("music", ("music", "dj", "concert")), ("podcasts", ("podcast", "talk")),
              ("news", ("news", "politic")), ("other", ("slots", "casino", "pools", "asmr", "art", "special events"))]


def section_of(game: str, tour=None) -> str:
    if tour:
        return "esports"
    if game in _SEC_FIXED:
        return _SEC_FIXED[game]
    if any(g == game for g, _ in GAMES):
        return "gaming"
    low = (game or "").lower()
    for sec, words in _SEC_WORDS:
        if any(w in low for w in words):
            return sec
    return "gaming" if game else "other"
_NON_GAMING_WORDS = ("irl", "chatting", "music", "talk", "sports", "slots", "casino", "pools", "asmr", "travel",
                     "podcast", "news", "special events", "art", "food", "politics")


# Cover art for each game: the name it has on Twitch (tried in order), else Kick's category image.
# Cover art, exact names only. Each game is looked up by the name it has on Twitch, then on Kick; a name that does
# not match exactly gives no art (an initials tile) rather than another game's cover. BGMI, PUBG: Battlegrounds and
# PUBG Mobile are three different games with three different covers. A file in static/gameart/<slug>.webp|png|jpg
# (slug: 'bgmi', 'free-fire' ...) overrides everything.
TWITCH_NAMES = {"BGMI": ["Battlegrounds Mobile India"], "PUBG: Battlegrounds": ["PUBG: BATTLEGROUNDS"],
                "PUBG Mobile": ["PUBG MOBILE"], "Free Fire": ["Garena Free Fire", "Free Fire"],
                "GTA V": ["Grand Theft Auto V"], "Valorant": ["VALORANT"], "COD Mobile": ["Call of Duty: Mobile"],
                "Call of Duty: Warzone": ["Call of Duty: Warzone"], "Call of Duty: Black Ops 7": ["Call of Duty: Black Ops 7"],
                "Call of Duty: Black Ops 6": ["Call of Duty: Black Ops 6"], "Counter-Strike 2": ["Counter-Strike"],
                "Pokemon Unite": ["Pokémon UNITE"], "Mobile Legends": ["Mobile Legends: Bang Bang"],
                "Indus": ["Indus Battle Royale"], "IRL": ["IRL"], "Just Chatting": ["Just Chatting"], "Music": ["Music"]}
KICK_NAMES = {"BGMI": ["Battlegrounds Mobile India"], "PUBG Mobile": ["PUBG Mobile"], "Free Fire": ["Free Fire", "Garena Free Fire"],
              "GTA V": ["Grand Theft Auto V (GTA)", "Grand Theft Auto V"], "Counter-Strike 2": ["Counter-Strike 2"],
              "Indus": ["Indus Battle Royale", "Indus"], "PUBG: Battlegrounds": ["PUBG: Battlegrounds", "PUBG"]}
NO_ART = {"Call of Duty", "EA Sports FC", "Cricket games", "Other", "Other tournaments"}   # several games share these names
ART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "gameart")
_ART_BUSY = set()


def _local_art(game: str) -> str:
    for ext in ("webp", "png", "jpg"):
        if os.path.isfile(os.path.join(ART_DIR, f"{slug(game)}.{ext}")):
            return f"/gameart/{slug(game)}.{ext}"
    return ""


def resolve_art(game: str):
    """(url, where it came from) for a game's cover, exact names only; ('', 'none') if nothing matches exactly."""
    if platforms._keys("twitch"):
        for name in TWITCH_NAMES.get(game, [game]):
            g = platforms._get("twitch", "https://api.twitch.tv/helix/games", {"name": name}).get("data") or []
            g = [x for x in g if (x.get("name") or "").lower() == name.lower() and x.get("box_art_url")]
            if g:
                return g[0]["box_art_url"].replace("{width}", "144").replace("{height}", "192"), f"Twitch '{g[0]['name']}'"
    if platforms._keys("kick"):
        for name in KICK_NAMES.get(game, [game]):
            c = platforms._get("kick", "https://api.kick.com/public/v1/categories", {"q": name}).get("data") or []
            hit = next((x for x in c if (x.get("name") or "").lower() == name.lower()), None)
            if hit and hit.get("thumbnail"):
                return hit["thumbnail"], f"Kick '{hit['name']}'"
    return "", "none"


def cat_art(game: str) -> str:
    """Cover art URL for a game or platform category (cached; looked up in the background the first time)."""
    if not game or game in NO_ART or game in NON_GAMING - {"Just Chatting", "IRL", "Music"}:
        return ""
    local = _local_art(game)
    if local:
        return local
    k = f"cat_art2:{game}"
    v = store.kv_get(k)
    if v is None and game not in _ART_BUSY:
        _ART_BUSY.add(game)

        def fetch():
            try:
                url, _src = resolve_art(game)
                store.kv_set(k, url)
                if not url:
                    print(f"No exact cover art found for {game}: showing initials (add static/gameart/{slug(game)}.png to fix)")
            except Exception as e:
                print(f"Cover art for {game} failed: {str(e)[:100]}")
            _ART_BUSY.discard(game)
        _pool.submit(fetch)
    return v or ""


def is_gaming(game: str) -> bool:
    """Games vs everything else (news, music, devotional, chatting ...). Unknown Kick/Twitch categories count as
    games unless their name says otherwise."""
    if game in NON_GAMING:
        return False
    if any(g == game for g, _ in GAMES):
        return True
    return not any(w in (game or "").lower() for w in _NON_GAMING_WORDS)


def classify(category: str, title: str) -> str:
    cat = (category or "").lower()
    if cat:
        for g, words in GAMES:
            if any(w in cat for w in words):
                return g
        return category.strip()[:40]        # the platform's own category name
    t = f" {(title or '').lower()} "
    for g, words in GAMES:
        if any(w in t for w in words):
            return g
    return "Other"


ALWAYS = {"kick": ["skyesports", "cegc"]}      # Sky Esports' Kick channels: tracked even if the seed list was edited


def seeds() -> dict:
    s = store.kv_get("scene_seeds")
    if s is None:
        s = {k: list(v) for k, v in SEEDS.items()}
    out = {k: list(s.get(k, [])) for k in ("youtube", "kick", "twitch")}
    for k, v in ALWAYS.items():
        out[k] += [x for x in v if x.lower() not in [y.lower() for y in out[k]]]
    return out


def blocked() -> set:
    return set(store.kv_get("scene_blocked") or [])


# ---------- YouTube ----------

_SEARCH_LIVE = "EgJAAQ=="       # search filter: live now
_ITV_IN = {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": "IN"}


def _num(txt: str):
    return platforms.parse_count(txt)


def _text(o) -> str:
    if not o:
        return ""
    return o.get("simpleText") or "".join(r.get("text", "") for r in o.get("runs", []))


def _itv(gl: str) -> dict:
    return {**_ITV_IN, "gl": gl}


def yt_search(query: str, gl: str = "IN") -> list:
    """Live streams for a search (gl: which country's YouTube). [{vid, channel, channel_id, title, viewers, logo}]"""
    r = events._http.post("https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
                          json={"context": {"client": _itv(gl)}, "query": query, "params": _SEARCH_LIVE},
                          headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                   "Origin": "https://www.youtube.com"}, timeout=10)
    r.raise_for_status()
    return _parse(_renderers(r.json()))


def _parse(found: list) -> list:
    out = []
    for v in found:
        watching = _text(v.get("viewCountText"))
        if "watching" not in watching.lower():
            continue                            # not live now (premieres, replays)
        by = (v.get("ownerText") or v.get("longBylineText") or v.get("shortBylineText") or {}).get("runs") or [{}]
        cid = ((by[0].get("navigationEndpoint") or {}).get("browseEndpoint") or {}).get("browseId", "")
        th = (((v.get("channelThumbnailSupportedRenderers") or {}).get("channelThumbnailWithLinkRenderer") or {})
              .get("thumbnail") or {}).get("thumbnails") or [{}]
        logo = th[0].get("url", "")
        if logo.startswith("//"):
            logo = "https:" + logo
        if v.get("videoId") and cid:
            out.append({"vid": v["videoId"], "channel": by[0].get("text", ""), "channel_id": cid,
                        "title": _text(v.get("title")), "viewers": _num(watching) or 0, "logo": logo})
    return out


def _renderers(j) -> list:
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k in ("videoRenderer", "gridVideoRenderer"):
                if k in o:
                    found.append(o[k])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(j)
    return found


def yt_live_page(gl: str = "IN") -> list:
    """YouTube's Live page (the streams YouTube itself features as live now) for a country's edition."""
    r = events._http.post("https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
                          json={"context": {"client": _itv(gl)}, "browseId": LIVE_PAGE},
                          headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                   "Origin": "https://www.youtube.com"}, timeout=10)
    r.raise_for_status()
    return _parse(_renderers(r.json()))


def _yt_add(found: dict, s: dict, logo: str = ""):
    sid = f"yt:{s['channel_id']}"
    x = found.setdefault(sid, {"sid": sid, "platform": "youtube", "name": s.get("channel", ""), "logo": logo or s.get("logo", ""),
                               "url": f"https://youtu.be/{s['vid']}", "title": s.get("title", ""), "category": "",
                               "streams": {}})
    x["streams"][s["vid"]] = int(s.get("viewers") or 0)
    if x["streams"][s["vid"]] >= max(x["streams"].values()):
        x.update(url=f"https://youtu.be/{s['vid']}", title=s.get("title", ""))
    if not x.get("logo") and (logo or s.get("logo")):
        x["logo"] = logo or s.get("logo")


def _event_on_air() -> bool:
    return any(s.get("kind") == "official" for d in events._LIVE.values() for s in d.values())


# ---------- one cycle ----------

def cycle(now: float = None) -> dict:
    now = now or time.time()
    found, errors = {}, {}
    blk = blocked()
    sd = seeds()

    # Kick / Twitch: the whole language, plus hand-added channels
    for p in ("kick", "twitch"):
        rows = []
        if platforms._keys(p):
            rows += platform_india(p, errors) + platform_global(p, errors)
        if sd[p] and (p == "kick" or platforms._keys(p)):
            try:
                rows += platforms._by_ids(p, [x.lower() for x in sd[p]])
            except Exception as e:
                errors[f"{p} channels"] = str(e)[:120]
        if p == "twitch" and rows:
            try:
                platforms._tw_logos(sorted({platforms.split(r["vid"])[1] for r in rows}))
            except Exception:
                pass
        if p == "kick" and rows:
            platforms.kick_logos([r["vid"] for r in rows])
        for r in sorted(rows, key=lambda r: r["viewers"]):   # duplicates: the latest (largest) reading wins
            sid = r["vid"]
            found[sid] = {"sid": sid, "platform": p, "name": r["channel"], "url": platforms.link(sid),
                          "logo": platforms.logo(sid), "title": r["title"], "category": r.get("category", ""),
                          "streams": {sid: r["viewers"]}, "language": r.get("language", ""),
                          "seeded": sid.split(":", 1)[1] in [x.lower() for x in sd[p]]}

    # YouTube: streams already live are re-counted every cycle; searches and hand-added channels less often
    with _lock:
        prev_yt = dict(sorted(((k, dict(v)) for k, v in _LIVE.items() if v["platform"] == "youtube"),
                              key=lambda kv: -kv[1]["viewers"])[:YT_RECOUNT])
    jobs = {(sid, vid): _pool.submit(_safe_count, vid) for sid, x in prev_yt.items() for vid in x["streams"]}
    for (sid, vid), fu in jobs.items():
        n = fu.result()
        x = prev_yt[sid]
        if n == "err":
            if x.get("errs", 0) < 3:            # keep the last reading through a few failed reads
                _yt_add(found, {"vid": vid, "channel": x["name"], "channel_id": sid[3:], "title": x["title"],
                                "viewers": x["streams"][vid]}, x.get("logo", ""))
                found[sid]["errs"] = x.get("errs", 0) + 1
        elif n:
            _yt_add(found, {"vid": vid, "channel": x["name"], "channel_id": sid[3:], "title": x["title"], "viewers": n},
                    x.get("logo", ""))
    yt_every = SCENE_YT_SEC * (3 if _event_on_air() else 1)
    if now - _STATE["yt"] >= yt_every:
        _STATE["yt"] = now
        res_live = _try(yt_live_page)
        if res_live == "err":
            errors["youtube live page"] = "failed"
        res_glob = _try(yt_live_page, "US")
        # YouTube's Live page in more countries' editions: finds the big local streams there (Brazil, Indonesia ...)
        pages = list(zip([f"live page {g}" for g in YT_GL], _pool.map(lambda g: _try(yt_live_page, g), YT_GL)))
        jobs_ = [(q, "IN") for q in QUERIES] + [(q, "US") for q in GLOBAL_QUERIES]
        for q, res in [("live page", res_live), ("live page US", res_glob)] + pages + \
                list(zip([q for q, _ in jobs_], _pool.map(lambda a: _try(yt_search, *a), jobs_))):
            if res == "err":
                errors[f"youtube '{q}'"] = "search failed"
                continue
            for s in res:
                if f"yt:{s['channel_id']}" not in found or s["vid"] not in found[f"yt:{s['channel_id']}"]["streams"]:
                    _yt_add(found, s)
    if sd["youtube"] and now - _STATE["seeds"] >= yt_every * 2:
        _STATE["seeds"] = now
        for s in _pool.map(lambda h: events._safe(events.check_channel, h), sd["youtube"]):
            if s and s.get("channel_id"):
                _yt_add(found, s)
                _SEEDED.add(f"yt:{s['channel_id']}")

    # Indian or not: look up the country of YouTube channels not seen before (cached in sc_channels)
    _load_countries()
    new = [sid[3:] for sid in found if sid.startswith("yt:") and sid[3:] not in _CTRY][:200]
    if new:
        try:
            _CTRY.update(yt_countries(new))
        except Exception as e:
            errors["youtube country lookup"] = str(e)[:120]
    allow = allowed() | _SEEDED
    # classify, filter, store
    rows, rejected = [], []
    for sid, x in found.items():
        x["viewers"] = sum(x["streams"].values())
        if sid in blk or x["viewers"] < MIN_VIEWERS:
            continue
        x["country"] = _CTRY.get(sid[3:]) if sid.startswith("yt:") else None
        x["india"] = verdict(x, x["country"], allow)
        if not x["india"] and x["viewers"] < GLOBAL_MIN:
            rejected.append(x)                # too small to matter worldwide; remembered so it isn't looked up again
            continue
        x["game"] = classify(x.get("category", ""), x.get("title", ""))
        x["tour"] = tournament(x.get("title", ""), x["game"])
        if x["tour"] and TOUR_GAME.get(x["tour"]):
            x["game"] = TOUR_GAME[x["tour"]]          # a VCT broadcast or co-stream is Valorant, whatever the category says
        if x["india"] and x["game"] == "PUBG Mobile" and not x["tour"]:
            x["game"] = "BGMI"                        # PUBG Mobile is banned in India; Indian streams of it are BGMI
        if not x.get("logo"):                 # the channel's real picture: YouTube channel page / Kick / Twitch
            x["logo"] = events.avatar(sid[3:]) if x["platform"] == "youtube" else platforms.logo(sid)
        x["seen"] = now
        rows.append(x)
    with _lock:
        last = _STATE["last"]
        _LIVE.clear()
        _LIVE.update({x["sid"]: x for x in rows})
        _STATE["last"] = now
        _STATE["errors"] = errors
    _store(rows, now, last)
    if rejected:                              # remember them (and their country) so they aren't looked up again
        with store._lock:
            c = _db()
            c.executemany("""INSERT INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                             country, india, language) VALUES (?,?,?,?,?,?,?,?,?,?,0,?) ON CONFLICT(sid) DO UPDATE SET
                             country=COALESCE(excluded.country, sc_channels.country), india=0, title=excluded.title""",
                          [(x["sid"], x["platform"], x["name"], x["url"], x.get("logo") or "", now, now, x.get("title", ""),
                            "", x.get("country"), x.get("language") or "") for x in rejected])
            c.commit()
    ind = [x for x in rows if x["india"]]
    return {"live": len(rows), "india": len(ind), "rejected": len(rejected), "viewers": sum(x["viewers"] for x in rows),
            "india_viewers": sum(x["viewers"] for x in ind), "errors": errors}


def _safe_count(vid):
    try:
        return events.count_live(vid)
    except Exception:
        return "err"


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"Scene: {fn.__name__} failed: {str(e)[:120]}")
        return "err"


def _store(rows, now, last):
    if not rows:
        return
    dt = min(now - last, SCENE_SEC * 2) if last else SCENE_SEC
    day = datetime.fromtimestamp(now, events.REPORT_TZ).strftime("%Y-%m-%d")
    with store._lock:
        c = _db()
        c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(int(now), x["sid"], x["viewers"], x["game"]) for x in rows])
        for x in rows:
            c.execute("""INSERT INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                         country, india, language) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sid) DO UPDATE SET
                         name=excluded.name, url=excluded.url,
                         logo=CASE WHEN excluded.logo!='' THEN excluded.logo ELSE sc_channels.logo END,
                         last_live=excluded.last_live, title=excluded.title, game=excluded.game,
                         country=COALESCE(excluded.country, sc_channels.country), india=excluded.india,
                         language=excluded.language""",
                      (x["sid"], x["platform"], x["name"], x["url"], x.get("logo") or "", now, now, x.get("title", ""),
                       x["game"], x.get("country"), 1 if x.get("india", True) else 0, x.get("language") or ""))
            c.execute("""INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                         peak_at=CASE WHEN excluded.peak > sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                         peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                      (day, x["sid"], x["game"], x["viewers"], int(now), dt / 60, x["viewers"] * dt / 3600))
        def totals(rs, key):
            out = {}
            for x in rs:
                k = x.get(key)
                if k:
                    a = out.setdefault(k, [0, 0])
                    a[0] += x["viewers"]
                    a[1] += 1
            return out
        ind = [x for x in rows if x.get("india", True)]
        cats = totals(ind, "game")
        cats[ALL] = [sum(x["viewers"] for x in ind), len(ind)]
        c.executemany("INSERT OR REPLACE INTO sc_cat VALUES (?,?,?,?)", [(int(now), g, v, n) for g, (v, n) in cats.items()])
        reg = [("global", g, v, n) for g, (v, n) in totals(rows, "game").items()]
        reg.append(("global", ALL, sum(x["viewers"] for x in rows), len(rows)))
        reg += [("tour:global", t, v, n) for t, (v, n) in totals(rows, "tour").items()]
        for x in rows:
            x["section"] = section_of(x["game"], x.get("tour"))
        reg += [("sec:global", t, v, n) for t, (v, n) in totals(rows, "section").items()]
        reg += [("sec:in", t, v, n) for t, (v, n) in totals(ind, "section").items()]
        reg += [("tour:in", t, v, n) for t, (v, n) in totals(ind, "tour").items()]
        c.executemany("INSERT OR REPLACE INTO sc_reg VALUES (?,?,?,?,?)", [(int(now), *r_) for r_ in reg])
        if int(now) % 3600 < SCENE_SEC:          # about once an hour: drop raw readings older than KEEP_DAYS
            c.execute("DELETE FROM sc_samples WHERE ts < ?", (now - KEEP_DAYS * 86400,))
            c.execute("DELETE FROM sc_reg WHERE ts < ? AND region LIKE 'tour:%'", (now - 30 * 86400,))
        c.commit()


FAST_SEC = float(os.getenv("SCENE_FAST_SEC", "2"))
_FASTV = {}          # sid -> [ts, viewers or None, misses]: Kick/Twitch re-read every FAST_SEC between scans


YT_FAST_N = int(os.getenv("SCENE_YT_FAST_N", "25"))   # biggest YouTube channels re-counted every FAST_SEC
_YTF = {"next": 0.0, "slow": 0}


def yt_fast_once(now: float = None) -> int:
    """Re-count the biggest live YouTube channels from YouTube's live counter (the method the tournament tracker uses
    every 2s). They hold most of the viewers, so totals move every 2 seconds; the rest are re-counted each scan.
    Slows to every 10s while a tournament broadcast is live (it has priority) and backs off if YouTube refuses."""
    t = now or time.time()
    if t < _YTF["next"]:
        return 0
    with _lock:
        top = [(sid, list(x["streams"])) for sid, x in sorted(_LIVE.items(), key=lambda kv: -kv[1]["viewers"])
               if x["platform"] == "youtube"][:YT_FAST_N]
    jobs = [(sid, vid, _pool.submit(_safe_count, vid)) for sid, vids in top for vid in vids]
    got, errs = {}, 0
    for sid, vid, fu in jobs:
        n = fu.result()
        if n == "err":
            errs += 1
            got.setdefault(sid, None)
            continue
        got[sid] = (got.get(sid) or 0) + (n or 0)
    for sid, v in got.items():
        f = _FASTV.setdefault(sid, [t, None, 0])
        if v is None:
            continue                          # couldn't read: keep the last value
        if v > 0:
            f[:] = [t, v, 0]
        else:
            f[0], f[2] = t, f[2] + 1
            if f[2] >= 3:                     # no 'watching' count three times running: ended
                f[1] = 0
    _YTF["slow"] = min(_YTF["slow"] + 1, 4) if jobs and errs > len(jobs) // 2 else max(_YTF["slow"] - 1, 0)
    base = 10 if _event_on_air() else FAST_SEC
    _YTF["next"] = t + base * (2 ** _YTF["slow"])
    return len(got)


def fast_once(now: float = None) -> int:
    """Re-read every live Kick/Twitch channel (one batched request per platform). Returns how many were read."""
    with _lock:
        ids = {p: [sid for sid, x in sorted(_LIVE.items(), key=lambda kv: -kv[1]["viewers"]) if x["platform"] == p][:FAST_MAX]
               for p in ("kick", "twitch")}
    n = 0
    for p, sids in ids.items():
        if not sids or not platforms._keys(p):
            continue
        rows = platforms._by_ids(p, [platforms.split(s)[1] for s in sids])
        got = {r["vid"]: r["viewers"] for r in rows}
        t = now or time.time()
        for s in sids:
            f = _FASTV.setdefault(s, [t, None, 0])
            if s in got:
                f[:] = [t, got[s], 0]
                n += 1
            else:
                f[0], f[2] = t, f[2] + 1
                if f[2] >= 3:                 # gone from the platform's live list three times running: ended
                    f[1] = 0
    return n


def run_fast():
    wait = FAST_SEC
    while True:
        t0 = time.time()
        try:
            fast_once()
            wait = FAST_SEC
        except Exception as e:                # rate limited or a network blip: back off, up to 30s
            wait = min(wait * 2, 30)
            print(f"Kick/Twitch fast count failed (next in {wait:g}s): {str(e)[:120]}")
        try:
            yt_fast_once()
        except Exception as e:
            print(f"YouTube fast count failed: {str(e)[:120]}")
        time.sleep(max(0.2, wait - (time.time() - t0)))


def run_forever():
    if _STATE["running"]:
        return
    _STATE["running"] = True
    threading.Thread(target=run_fast, daemon=True).start()
    time.sleep(20)                           # let the event counter start first
    while True:
        t0 = time.time()
        try:
            r = cycle()
            if r["errors"]:                  # shown in the tracker window so a failing source is visible
                print("India scan problems: " + "; ".join(f"{k}: {v}" for k, v in list(r["errors"].items())[:6]))
        except Exception as e:
            print(f"Scene cycle failed: {str(e)[:200]}")
        time.sleep(max(10, SCENE_SEC - (time.time() - t0)))


# ---------- numbers for the page ----------

PERIODS = {"today": 0, "7d": 6, "30d": 29}


SERIES_SEC = {"today": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


REGIONS = ("in", "global")
# Peak concurrent viewers of past tournaments (thousands), per game: [series, 2-digit year, peak K]. Shown on that
# game's page. Tournaments tracked here add their own peak automatically (see game_history()).
GAME_HISTORY = {"BGMI": [["LAUNCH", "21", 540], ["BGIS", "21", 460], ["BMPS", "22", 305], ["BMSD", "22", 315],
                         ["BGIS", "23", 235], ["BMPS", "23", 201], ["INKR", "23", 178], ["BGIS", "24", 275],
                         ["BMPS", "24", 495], ["BGIS", "25", 485], ["BMPS", "25", 320], ["BMSD", "25", 380],
                         ["BMIC", "25", 372], ["BGIS", "26", 578], ["BMPS", "26", 730], ["BMSD", "26", 653]]}
SERIES_NAMES = {"LAUNCH": "BGMI Launch Party", "INKR": "INKR Invitational"}


def game_history(game: str) -> list:
    """[{name, peak}] oldest first, with tracked tournaments' recorded peaks added or updated."""
    hist = [list(x) for x in GAME_HISTORY.get(game, [])]
    if not hist:
        return []
    with store._lock:
        c = events._db()
        for ev in events.events().values():
            pr = events.preset(ev["key"])
            h = pr.get("hist")
            if events.opt(ev, "game", "") != game or not h:
                continue
            pk = c.execute("SELECT MAX(total) FROM ev_ticks WHERE event=?", (ev["key"],)).fetchone()[0] or 0
            if not pk:
                continue
            row = next((x for x in hist if x[0] == h[0] and x[1] == h[1]), None)
            if row:
                row[2] = max(row[2], round(pk / 1000))
            else:
                hist.append([h[0], h[1], round(pk / 1000)])
    logos = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "eventlogos")
    have = set(os.listdir(logos)) if os.path.isdir(logos) else set()
    return [{"name": f"{SERIES_NAMES.get(a, a)} 20{b}", "series": a, "year": b, "peak": k * 1000,
             "logo": f"/elogo/{a}{b}.webp" if f"{a}{b}.webp" in have else ""} for a, b, k in hist]


def _totals_sql(region: str):
    """(table, extra WHERE, args) for the per-scan totals of a region: India in sc_cat, the rest in sc_reg."""
    if region == "in":
        return "sc_cat", "", ()
    return "sc_reg", " AND region=?", (region,)


def _series(c, game: str, period: str, region: str = "in") -> list:
    """[[ts, viewers]] for the chart: the category (or whole region) total each scan, thinned to about 600 points by
    keeping each bucket's highest reading (so peaks survive)."""
    tbl, w, a = _totals_sql(region)
    t0 = time.time() - SERIES_SEC[period]
    rows = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY ts", (game, t0, *a)).fetchall()
    if len(rows) <= 600:
        return [[r[0], r[1]] for r in rows]
    step = (rows[-1][0] - rows[0][0]) / 600 or 1
    b = {}
    for ts, v in rows:
        k = int((ts - rows[0][0]) / step)
        if k not in b or v > b[k][1]:
            b[k] = [ts, v]
    return [b[k] for k in sorted(b)]


def _events() -> list:
    """Tracked tournaments for the hub: live now / countdown / finished, with their peak."""
    out = []
    with store._lock:
        c = events._db()
        for ev in sorted(events.events().values(), key=lambda e: -(e.get("created") or 0)):
            pr = events.preset(ev["key"])
            peak = c.execute("SELECT MAX(total) FROM ev_ticks WHERE event=?", (ev["key"],)).fetchone()[0] or 0
            last = c.execute("SELECT ts, total, official FROM ev_ticks WHERE event=? ORDER BY ts DESC LIMIT 1",
                             (ev["key"],)).fetchone()
            live = bool(last and time.time() - last[0] < 120 and not events.paused(ev["key"]))
            state = "ended" if pr.get("ended") else "live" if live else "upcoming" if events.next_start(ev["key"]) else "off"
            out.append({"key": ev["key"], "name": ev["name"], "game": events.opt(ev, "game", ""), "state": state,
                        "next_start": events.next_start(ev["key"]), "now": last[1] if live else 0, "peak": peak,
                        "url": f"/e/{ev['key']}/"})
    order = {"live": 0, "upcoming": 1, "off": 2, "ended": 3}
    return sorted(out, key=lambda e: order[e["state"]])


def category_name(cat: str):
    """Display name for a category slug, or None if nothing in it has ever been seen."""
    for g, _ in GAMES:
        if slug(g) == cat:
            return g
    with store._lock:
        c = _db()
        for (g,) in c.execute("SELECT DISTINCT game FROM sc_cat WHERE game != ? UNION SELECT DISTINCT game FROM sc_reg "
                              "WHERE region='global' AND game != ?", (ALL, ALL)):
            if slug(g) == cat:
                return g
    return None


_SCAN = {"ts": None, "rows": []}


def _logo(x: dict) -> str:
    if x.get("logo"):
        return x["logo"]
    sid = x.get("sid", "")
    return events.avatar(sid[3:]) if sid.startswith("yt:") else platforms.logo(sid)


def _live_part(game=None, region: str = "in", sec: str = "") -> dict:
    """Who is live now in a region (and section or game): the latest scan (read from the database once per scan) with
    Kick/Twitch viewers replaced by the 2-second readings when they're fresh."""
    blk = blocked()
    with store._lock:
        c = _db()
        last = (c.execute("SELECT MAX(ts) FROM sc_samples").fetchone()[0] or 0)
        if _SCAN["ts"] != last:
            _SCAN["rows"] = [dict(r) for r in c.execute(
                """SELECT s.sid, s.viewers, s.game, c.platform, c.name, c.url, c.logo, c.title, c.country, c.language,
                   COALESCE(c.india, 1) AS india FROM sc_samples s LEFT JOIN sc_channels c ON c.sid=s.sid
                   WHERE s.ts=? ORDER BY s.viewers DESC""", (last,))]
            day = datetime.now(events.REPORT_TZ).strftime("%Y-%m-%d")
            _SCAN["peak"] = dict(c.execute("SELECT sid, MAX(peak) FROM sc_daily WHERE day=? GROUP BY sid", (day,)).fetchall())
            for r in _SCAN["rows"]:
                r["tour"] = tournament(r.get("title") or "", r["game"])
                r["section"] = section_of(r["game"], r["tour"])
            _SCAN["ts"] = last
    fresh = time.time() - last < SCENE_SEC * 3
    now, seen, live = time.time(), set(), []
    for r in (_SCAN["rows"] if fresh else []):
        if r["sid"] in blk or r["sid"] in seen or (region == "in" and not r["india"]):
            continue
        seen.add(r["sid"])
        x = dict(r)
        f = _FASTV.get(x["sid"])
        if f and f[1] is not None and now - f[0] < 15:
            x["viewers"] = f[1]
        if x["viewers"] <= 0:
            continue                          # ended since the scan
        x["logo"] = _logo(x)
        x["peak"] = max(_SCAN.get("peak", {}).get(x["sid"]) or 0, x["viewers"])
        live.append(x)
    live.sort(key=lambda x: -x["viewers"])
    region_total = sum(x["viewers"] for x in live)
    now_map = {x["sid"]: x["viewers"] for x in live}      # everyone live in the region, before any section filter
    secs = {}
    for x in live:
        z = secs.setdefault(x["section"], {"key": x["section"], "name": SECTION_NAMES[x["section"]], "viewers": 0,
                                           "channels": 0, "top": [], "items": {}})
        z["viewers"] += x["viewers"]
        z["channels"] += 1
        if len(z["top"]) < 3:
            z["top"].append({"name": x["name"], "viewers": x["viewers"], "logo": x["logo"], "platform": x["platform"]})
        k = x["tour"] if x["section"] == "esports" else x["game"]
        z["items"][k] = z["items"].get(k, 0) + x["viewers"]
    if sec:
        live = [x for x in live if x["section"] == sec]
    by_game = {}
    for x in live:
        g = by_game.setdefault(x["game"], {"game": x["game"], "slug": slug(x["game"]), "viewers": 0, "streams": 0,
                                           "top": x["name"], "top_logo": x.get("logo") or "", "top_viewers": x["viewers"],
                                           "art": cat_art(x["game"]), "section": section_of(x["game"])})
        g["viewers"] += x["viewers"]
        g["streams"] += 1
    tours = {}
    for x in live:
        if not x.get("tour"):
            continue
        t = tours.setdefault(x["tour"], {"name": x["tour"], "viewers": 0, "streams": [], "games": {}})
        t["viewers"] += x["viewers"]
        t["games"][x["game"]] = t["games"].get(x["game"], 0) + x["viewers"]
        t["streams"].append({k: x.get(k) for k in ("sid", "platform", "name", "url", "logo", "title", "viewers")})
    if game:
        live = [x for x in live if x["game"] == game]
        tours = {k: t for k, t in tours.items() if max(t["games"], key=t["games"].get) == game}
    by_plat = {}
    for x in live:
        by_plat[x["platform"]] = by_plat.get(x["platform"], 0) + x["viewers"]
    sections = []
    for k, name in SECTIONS:
        z = secs.get(k) or {"key": k, "name": name, "viewers": 0, "channels": 0, "top": [], "items": {}}
        z["items"] = [{"name": n, "viewers": v} for n, v in sorted(z["items"].items(), key=lambda kv: -kv[1])[:3]]
        sections.append(z)
    return {"_blk": blk, "_live": live, "_by_game": by_game, "_by_plat": by_plat, "_tours": tours, "sections": sections,
            "_now": now_map,
            "updated": last, "fresh": fresh, "india_total": region_total, "region_total": region_total,
            "live_total": sum(x["viewers"] for x in live), "now": now}


def _tour_list(tours: dict, region: str) -> list:
    """Live tournaments, biggest first, with today's peak (IST day) from the per-scan totals."""
    d0 = datetime.combine(datetime.now(events.REPORT_TZ).date(), datetime.min.time(), events.REPORT_TZ).timestamp()
    with store._lock:
        pk = {r[0]: (r[1], r[2]) for r in _db().execute(
            "SELECT game, MAX(viewers), ts FROM sc_reg WHERE region=? AND ts>=? GROUP BY game", (f"tour:{region}", d0))}
    out = []
    for t in tours.values():
        g = max(t["games"], key=t["games"].get)
        st = sorted(t["streams"], key=lambda s_: -s_["viewers"])
        out.append({"name": t["name"], "game": g, "slug": slug(g), "art": cat_art(g), "viewers": t["viewers"],
                    "streams": len(st), "top": st[:6], "peak": max((pk.get(t["name"]) or (0,))[0], t["viewers"])})
    return sorted(out, key=lambda t: -t["viewers"])[:24]


def _region(region: str) -> str:
    return region if region in REGIONS else "in"


def _scope(region: str, sec: str, game):
    """(totals table, extra WHERE, args, key) for the chart/peak numbers of what a page shows."""
    if game:
        tbl, w, a = _totals_sql(region)
        return tbl, w, a, game
    if sec:
        return "sc_reg", " AND region=?", (f"sec:{region}",), sec
    tbl, w, a = _totals_sql(region)
    return tbl, w, a, ALL


def _kpis(c, region: str, sec: str, game, lv: dict) -> dict:
    """The headline numbers: watching now, live channels, today's peak (IST day) and hours watched today."""
    tbl, w, a, key = _scope(region, sec, game)
    d0 = datetime.combine(datetime.now(events.REPORT_TZ).date(), datetime.min.time(), events.REPORT_TZ)
    pk = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY viewers DESC LIMIT 1",
                   (key, d0.timestamp(), *a)).fetchone()
    # hours watched today: every scan's total x the time between scans (works the same for sections and tournaments)
    rows = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY ts", (key, d0.timestamp(), *a)).fetchall()
    hw = sum(v * min(rows[i + 1][0] - ts if i + 1 < len(rows) else SCENE_SEC, SCENE_SEC * 2) for i, (ts, v) in enumerate(rows)) / 3600
    air = None
    if sec == "esports":
        chans = c.execute("SELECT COUNT(DISTINCT game) FROM sc_reg WHERE region=? AND ts>=?", (f"tour:{region}", d0.timestamp())
                          ).fetchone()[0]
    else:
        q = """SELECT COUNT(DISTINCT d.sid), SUM(d.mins) FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid
               WHERE d.day=?""" + (" AND COALESCE(c.india,1)=1" if region == "in" else "")
        args = [d0.strftime("%Y-%m-%d")]
        if game:
            q += " AND d.game=?"
            args.append(game)
        elif sec:
            games = [g for (g,) in c.execute("SELECT DISTINCT game FROM sc_daily WHERE day=?", (args[0],)) if section_of(g) == sec]
            q += f" AND d.game IN ({','.join('?' * len(games)) or 'NULL'})"
            args += games
        chans, air = c.execute(q, args).fetchone()
        air = round((air or 0) / 60, 1)          # total hours live, every channel added up
    top = lv["_live"][0] if lv["_live"] else None
    lead = None
    if pk:                                    # which channel was biggest at the moment of today's peak
        for r in c.execute("""SELECT s.sid, s.viewers, s.game, c.name, c.platform, c.url, c.logo, c.title,
                              COALESCE(c.india,1) AS india FROM sc_samples s LEFT JOIN sc_channels c ON c.sid=s.sid
                              WHERE s.ts=? ORDER BY s.viewers DESC""", (pk[0],)):
            if region == "in" and not r["india"]:
                continue
            if game and r["game"] != game:
                continue
            if sec and section_of(r["game"], tournament(r["title"] or "", r["game"])) != sec:
                continue
            lead = {"name": r["name"], "viewers": r["viewers"], "platform": r["platform"], "url": r["url"],
                    "logo": _logo({"sid": r["sid"], "logo": r["logo"]})}
            break
    if top and (not pk or lv["live_total"] >= pk[1]):     # the peak is right now
        lead = {k: top.get(k) for k in ("name", "viewers", "platform", "url", "logo")}
    return {"watching": lv["live_total"], "live_channels": len(lv["_live"]), "peak_lead": lead,
            "peak_today": max(pk[1] if pk else 0, lv["live_total"]), "peak_today_at": pk[0] if pk else None,
            "hw_today": round(hw), "channels_today": chans, "air_today": air,
            "avg_today": round(hw / ((rows[-1][0] - rows[0][0] + SCENE_SEC) / 3600)) if rows else 0,
            "top": {k: top.get(k) for k in ("name", "viewers", "platform", "url", "logo", "game", "title")} if top else None}


def _common(lv: dict, region: str) -> dict:
    return {"updated": lv["updated"], "fresh": lv["fresh"], "india_total": lv["region_total"],
            "live_total": lv["live_total"], "live_count": len(lv["_live"]), "now": lv["now"], "sections": lv["sections"],
            "platforms": [{"platform": k, "name": platforms.NAMES[k], "viewers": v}
                          for k, v in sorted(lv["_by_plat"].items(), key=lambda kv: -kv[1])],
            "categories": sorted(lv["_by_game"].values(), key=lambda g: -g["viewers"])[:200],
            "tournaments": _tour_list(lv["_tours"], region),
            "live": [{k: x.get(k) for k in ("sid", "platform", "name", "url", "logo", "game", "title", "viewers", "section", "peak")}
                     for x in lv["_live"][:300]]}


def _sec(sec: str) -> str:
    return sec if sec in SECTION_NAMES else ""


def live_data(cat: str = "", region: str = "in", sec: str = "") -> dict:
    """The part of the page that moves every 2 seconds: KPIs, sections, categories, tournaments, live streams."""
    region, sec = _region(region), _sec(sec)
    game = category_name(cat) if cat else None
    lv = _live_part(game, region, sec)
    with store._lock:
        k = _kpis(_db(), region, sec, game, lv)
    return {**_common(lv, region), "kpis": k}


def data(period: str = "today", cat: str = "", region: str = "in", sec: str = "") -> dict:
    """Everything a page shows: the overview (no cat/sec), a section (sec) or one game (cat), for India or the world."""
    period = period if period in PERIODS else "today"
    region, sec = _region(region), _sec(sec)
    game = category_name(cat) if cat else None
    lv = _live_part(game, region, sec)
    blk, live = lv["_blk"], lv["_live"]
    today = datetime.now(events.REPORT_TZ).date()
    d0 = (today - timedelta(days=PERIODS[period])).strftime("%Y-%m-%d")
    tbl, w, a, key = _scope(region, sec, game)
    with store._lock:
        c = _db()
        q = """SELECT d.sid, d.game, MAX(d.peak) peak, SUM(d.mins) mins, SUM(d.hw) hw, c.name, c.platform,
               c.url, c.logo, c.last_live FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid WHERE d.day >= ?"""
        q += " AND COALESCE(c.india, 1)=1" if region == "in" else ""
        rows = c.execute(q + (" AND d.game = ?" if game else "") + " GROUP BY d.sid, d.game",
                         (d0, game) if game else (d0,)).fetchall()
        series = _series_any(c, tbl, w, a, key, period)
        daily = _daily(c, tbl, w, a, key)
        p0 = datetime.combine(today - timedelta(days=PERIODS[period]), datetime.min.time(), events.REPORT_TZ).timestamp()
        rt, rw, ra = _totals_sql(region)
        scans = c.execute(f"SELECT COUNT(*) FROM {rt} WHERE game=? AND ts>=?{rw}", (ALL, p0, *ra)).fetchone()[0] or 0
        cstats = c.execute(f"SELECT game, SUM(viewers) s, MAX(viewers) pk FROM {rt} WHERE ts>=? AND game!=?{rw} GROUP BY game",
                           (p0, ALL, *ra)).fetchall()
        tracked = c.execute("SELECT COUNT(*) FROM sc_channels" + (" WHERE COALESCE(india,1)=1" if region == "in" else "")
                            ).fetchone()[0]
        pk = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY viewers DESC LIMIT 1",
                       (key, time.time() - SERIES_SEC[period], *a)).fetchone()
        pk_all = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=?{w} ORDER BY viewers DESC LIMIT 1", (key, *a)).fetchone()
        tour_day = [{"name": r[0], "peak": r[1], "at": r[2]} for r in c.execute(
            "SELECT game, MAX(viewers), ts FROM sc_reg WHERE region=? AND ts>=? GROUP BY game ORDER BY MAX(viewers) DESC LIMIT 20",
            (f"tour:{region}", p0))]
        kp = _kpis(c, region, sec, game, lv)
    ch, games = {}, {}
    for r in rows:
        if r["sid"] in blk or (sec and sec != "esports" and section_of(r["game"]) != sec):
            continue
        x = ch.setdefault(r["sid"], {"sid": r["sid"], "name": r["name"] or r["sid"], "platform": r["platform"] or "",
                                      "url": r["url"] or "", "logo": _logo({"sid": r["sid"], "logo": r["logo"]}),
                                      "peak": 0, "mins": 0.0, "hw": 0.0, "games": {}, "last_live": r["last_live"]})
        x["peak"] = max(x["peak"], r["peak"])
        x["mins"] += r["mins"]
        x["hw"] += r["hw"]
        x["games"][r["game"]] = x["games"].get(r["game"], 0) + r["hw"]
        g = games.setdefault(r["game"], {"game": r["game"], "slug": slug(r["game"]), "hw": 0.0, "peak_stream": 0,
                                         "channels": 0, "art": cat_art(r["game"]), "section": section_of(r["game"])})
        g["hw"] += r["hw"]
        g["peak_stream"] = max(g["peak_stream"], r["peak"])
        g["channels"] += 1
    board = []
    for x in ch.values():
        x["avg"] = round(x["hw"] * 60 / x["mins"]) if x["mins"] else 0
        x["game"] = max(x["games"], key=x["games"].get) if x["games"] else ""
        x["hw"], x["airtime_h"] = round(x["hw"]), round(x["mins"] / 60, 1)
        del x["games"], x["mins"]
        board.append(x)
    board.sort(key=lambda x: -x["hw"])
    with store._lock:
        prev = _prev_ranks(_db(), region, game, sec, period)
    for i, x in enumerate(board):
        x["rank"] = i + 1
        x["delta"] = (prev[x["sid"]] - x["rank"]) if x["sid"] in prev else None   # None = new in the ranking
    for x in board:
        x["now"] = lv["_now"].get(x["sid"], 0)   # live right now (in any section), else last_live says when
    if sec == "esports":
        board = []                            # esports is ranked by tournament (tour_day), not by channel
    cat_period = [{"game": r["game"], "slug": slug(r["game"]), "avg": round(r["s"] / scans) if scans else 0, "peak": r["pk"],
                   "gaming": is_gaming(r["game"]), "section": section_of(r["game"]), "art": cat_art(r["game"])}
                  for r in cstats]
    if sec:
        cat_period = [x for x in cat_period if x["section"] == sec]
    return {**_common(lv, region), "kpis": kp, "period": period, "every": SCENE_SEC, "region": region,
            "sec": sec, "sec_name": SECTION_NAMES.get(sec, ""), "cat": cat if game else "", "cat_name": game or "",
            "peak": {"viewers": pk[1], "ts": pk[0]} if pk else None,
            "peak_all": {"viewers": pk_all[1], "ts": pk_all[0]} if pk_all else None,
            "series": series, "daily": daily, "board": board[:300], "tour_day": tour_day,
            "games": [{**g, "hw": round(g["hw"])} for g in sorted(games.values(), key=lambda g: -g["hw"])][:60],
            "events": ([e for e in _events() if e["state"] in ("live", "upcoming")] if not (game or sec)
                       else [e for e in _events() if game and e["game"] == game]),
            "history": game_history(game) if game else [],
            "cat_period": sorted(cat_period, key=lambda x: -x["avg"]), "tracked": tracked,
            "langs": LANGS, "min": MIN_VIEWERS if region == "in" else GLOBAL_MIN,
            "keys": {p: bool(platforms._keys(p)) for p in ("kick", "twitch")}}


def _prev_ranks(c, region, game, sec, period) -> dict:
    """{sid: rank by hours watched} for the period just before this one (yesterday for today), for rank arrows."""
    n = PERIODS[period] + 1                   # days in the period (today = 1)
    today = datetime.now(events.REPORT_TZ).date()
    p1 = today - timedelta(days=n)
    p0 = p1 - timedelta(days=n - 1)
    q = """SELECT d.sid, d.game, SUM(d.hw) hw FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid
           WHERE d.day BETWEEN ? AND ?""" + (" AND COALESCE(c.india,1)=1" if region == "in" else "")
    args = [p0.strftime("%Y-%m-%d"), p1.strftime("%Y-%m-%d")]
    if game:
        q += " AND d.game=?"
        args.append(game)
    tot = {}
    for r in c.execute(q + " GROUP BY d.sid, d.game", args):
        if sec and sec != "esports" and section_of(r["game"]) != sec:
            continue
        tot[r["sid"]] = tot.get(r["sid"], 0) + (r["hw"] or 0)
    return {sid: i + 1 for i, (sid, _) in enumerate(sorted(tot.items(), key=lambda kv: -kv[1]))}


RANK_PERIODS = {"day": 1, "week": 7, "month": 30}


def rankings(region="global", metric="hw", period="day", date="", cat="", country="", platform="", sec="", limit=100):
    """Leaderboard of channels for one day / the 7 or 30 days ending on `date` (IST), by hours watched, peak or
    average viewers, filtered by game, section, streamer country and platform, with each channel's move against the
    period before."""
    region = _region(region)
    metric = metric if metric in ("hw", "peak", "avg", "hours", "sc", "vg") else "hw"
    n = RANK_PERIODS.get(period, 1)
    today = datetime.now(events.REPORT_TZ).date()
    try:
        end = min(datetime.strptime(date, "%Y-%m-%d").date(), today) if date else today
    except ValueError:
        end = today
    game = category_name(cat) if cat else None
    sec = _sec(sec)
    ctry = country_of(country) if country else None

    def window(e):
        s_ = e - timedelta(days=n - 1)
        q = """SELECT d.sid, d.game, MAX(d.peak) peak, SUM(d.mins) mins, SUM(d.hw) hw, c.name, c.platform, c.url, c.logo,
               c.country, COALESCE(c.india,1) india, c.last_live FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid
               WHERE d.day BETWEEN ? AND ?""" + (" AND COALESCE(c.india,1)=1" if region == "in" else "")
        args = [s_.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")]
        if game:
            q += " AND d.game=?"
            args.append(game)
        if platform in platforms.NAMES:
            q += " AND c.platform=?"
            args.append(platform)
        with store._lock:
            rows = _db().execute(q + " GROUP BY d.sid, d.game", args).fetchall()
        out, games, ctrs = {}, {}, {}
        blk = blocked()
        for r in rows:
            if r["sid"] in blk or (sec and section_of(r["game"]) != sec):
                continue
            ct = country_of(r["country"]) or (country_of("IN") if r["india"] else None)
            if ct:
                ctrs[ct[0]] = ct[2]
            if ctry and (not ct or ct[0] != ctry[0]):
                continue
            x = out.setdefault(r["sid"], {"sid": r["sid"], "name": r["name"] or r["sid"], "platform": r["platform"] or "",
                                          "url": r["url"] or "", "logo": _logo({"sid": r["sid"], "logo": r["logo"]}),
                                          "country": ct[0] if ct else "", "country_name": ct[2] if ct else "",
                                          "last_live": r["last_live"], "peak": 0, "mins": 0.0, "hw": 0.0, "g": {}})
            x["peak"] = max(x["peak"], r["peak"] or 0)
            x["mins"] += r["mins"] or 0
            x["hw"] += r["hw"] or 0
            x["g"][r["game"]] = x["g"].get(r["game"], 0) + (r["hw"] or 0)
            games[r["game"]] = games.get(r["game"], 0) + (r["hw"] or 0)
        # Super Chats and views gained come from their own tables; channels not live in the period still rank by them
        from tracker import ytextra
        d0, d1 = args[0], args[1]
        extra = {"sc": ytextra.window_superchats(d0, d1), "vg": ytextra.window_views(d0, d1)}
        if metric in ("sc", "vg") and extra[metric]:
            missing = [sid for sid in extra[metric] if sid not in out and sid not in blk]
            for i in range(0, len(missing), 500):
                part = missing[i:i + 500]
                with store._lock:
                    chs = _db().execute(f"SELECT * FROM sc_channels WHERE sid IN ({','.join('?' * len(part))})", part).fetchall()
                for r in chs:
                    if region == "in" and not r["india"]:
                        continue
                    if platform in platforms.NAMES and r["platform"] != platform:
                        continue
                    if game and r["game"] != game:
                        continue
                    if sec and section_of(r["game"]) != sec:
                        continue
                    ct = country_of(r["country"]) or (country_of("IN") if r["india"] else None)
                    if ct:
                        ctrs[ct[0]] = ct[2]
                    if ctry and (not ct or ct[0] != ctry[0]):
                        continue
                    out[r["sid"]] = {"sid": r["sid"], "name": r["name"] or r["sid"], "platform": r["platform"] or "",
                                     "url": r["url"] or "", "logo": _logo({"sid": r["sid"], "logo": r["logo"]}),
                                     "country": ct[0] if ct else "", "country_name": ct[2] if ct else "",
                                     "last_live": r["last_live"], "peak": 0, "mins": 0.0, "hw": 0.0, "g": {r["game"] or "": 0}}
        money = "inr" if region == "in" else "usd"
        for x in out.values():
            s_ = extra["sc"].get(x["sid"]) or {}
            v_ = extra["vg"].get(x["sid"]) or {}
            x["sc"], x["sc_count"] = s_.get(money, 0), s_.get("count", 0)
            x["vg"], x["sg"], x["subs"] = v_.get("vg", 0), v_.get("sg"), v_.get("subs")
        for x in out.values():
            x["avg"] = round(x["hw"] * 60 / x["mins"]) if x["mins"] else 0
            x["hours"] = round(x["mins"] / 60, 1)
            x["hw"] = round(x["hw"])
            x["game"] = max(x["g"], key=x["g"].get) if x["g"] else ""
            del x["g"], x["mins"]
        ranked = sorted((x for x in out.values() if metric not in ("sc", "vg") or x[metric] > 0), key=lambda x: -x[metric])
        return ranked, games, ctrs
    cur, games, ctrs = window(end)
    prev = {x["sid"]: i + 1 for i, x in enumerate(window(end - timedelta(days=n))[0])}
    now = _live_part(None, "global")["_now"]
    for i, x in enumerate(cur):
        x["rank"] = i + 1
        x["delta"] = prev[x["sid"]] - x["rank"] if x["sid"] in prev else None
        x["now"] = now.get(x["sid"], 0)
    with store._lock:
        first = _db().execute("SELECT MIN(day) FROM sc_daily").fetchone()[0]
    return {"region": region, "metric": metric, "period": period, "date": end.strftime("%Y-%m-%d"),
            "start": (end - timedelta(days=n - 1)).strftime("%Y-%m-%d"), "first_day": first, "today": today.strftime("%Y-%m-%d"),
            "total": len(cur), "rows": cur[:limit],
            "categories": [{"game": g, "slug": slug(g), "hw": round(v)} for g, v in sorted(games.items(), key=lambda kv: -kv[1])[:80]],
            "countries": [{"code": k, "name": v} for k, v in sorted(ctrs.items(), key=lambda kv: kv[1])],
            "totals": {"hw": sum(x["hw"] for x in cur), "channels": len(cur)}, "money": "INR" if region == "in" else "USD"}


def _daily(c, tbl, w, a, key, days: int = 30) -> list:
    """Per IST day for the last `days` days: peak watching at once, when, and hours watched. Oldest first."""
    t0 = datetime.combine(datetime.now(events.REPORT_TZ).date() - timedelta(days=days - 1), datetime.min.time(),
                          events.REPORT_TZ).timestamp()
    rows = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY ts", (key, t0, *a)).fetchall()
    out = {}
    for i, (ts, v) in enumerate(rows):
        d = datetime.fromtimestamp(ts, events.REPORT_TZ).strftime("%Y-%m-%d")
        z = out.setdefault(d, {"day": d, "peak": 0, "at": ts, "hw": 0.0})
        if v > z["peak"]:
            z["peak"], z["at"] = v, ts
        z["hw"] += v * min(rows[i + 1][0] - ts if i + 1 < len(rows) else SCENE_SEC, SCENE_SEC * 2) / 3600
    return [{**z, "hw": round(z["hw"])} for _, z in sorted(out.items())]


def _series_any(c, tbl, w, a, key, period) -> list:
    t0 = time.time() - SERIES_SEC[period]
    rows = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY ts", (key, t0, *a)).fetchall()
    if len(rows) <= 600:
        return [[r[0], r[1]] for r in rows]
    step = (rows[-1][0] - rows[0][0]) / 600 or 1
    b = {}
    for ts, v in rows:
        k = int((ts - rows[0][0]) / step)
        if k not in b or v > b[k][1]:
            b[k] = [ts, v]
    return [b[k] for k in sorted(b)]


def search(q: str, region: str = "in", limit: int = 20) -> dict:
    """Any channel ever seen live whose name or stream title contains q (live titles included), plus matching
    games/categories. Channels whose name matches come first."""
    q = (q or "").strip().lower()[:60]
    if len(q) < 2:
        return {"channels": [], "categories": []}
    region = _region(region)
    lv = _live_part(None, region)
    now = lv["_now"]
    live_title = {x["sid"]: x.get("title") or "" for x in lv["_live"]}
    hits_live = [sid for sid, t in live_title.items() if q in t.lower()]
    with store._lock:
        c = _db()
        reg = "AND COALESCE(c.india,1)=1 " if region == "in" else ""
        sel = """SELECT c.sid, c.name, c.platform, c.url, c.logo, c.last_live, c.game, c.title,
                 (SELECT MAX(peak) FROM sc_daily d WHERE d.sid=c.sid) peak FROM sc_channels c """
        rows = c.execute(sel + "WHERE LOWER(c.name) LIKE ? " + reg + "ORDER BY peak DESC NULLS LAST LIMIT ?",
                         (f"%{q}%", limit)).fetchall()
        seen = {r["sid"] for r in rows}
        more = c.execute(sel + "WHERE LOWER(c.title) LIKE ? " + reg + "ORDER BY peak DESC NULLS LAST LIMIT ?",
                         (f"%{q}%", limit)).fetchall()
        extra = [x for x in hits_live if x not in seen and x not in {r["sid"] for r in more}][:limit]
        if extra:
            more += c.execute(sel + f"WHERE c.sid IN ({','.join('?' * len(extra))})", extra).fetchall()
        games = [g for (g,) in c.execute("SELECT DISTINCT game FROM sc_cat WHERE LOWER(game) LIKE ? AND game != ? "
                                         "UNION SELECT DISTINCT game FROM sc_reg WHERE region='global' AND LOWER(game) LIKE ? "
                                         "AND game != ? LIMIT 8", (f"%{q}%", ALL, f"%{q}%", ALL))]
    out = []
    for r in list(rows) + [r for r in more if r["sid"] not in seen]:
        if not r["name"] or any(o["sid"] == r["sid"] for o in out):
            continue
        title = live_title.get(r["sid"]) or r["title"] or ""
        out.append({"sid": r["sid"], "name": r["name"], "platform": r["platform"], "url": r["url"],
                    "logo": _logo({"sid": r["sid"], "logo": r["logo"]}), "last_live": r["last_live"], "game": r["game"],
                    "title": title, "by": "name" if q in r["name"].lower() else "title",
                    "peak": r["peak"] or 0, "now": now.get(r["sid"], 0)})
    return {"channels": out[:limit * 2], "categories": [{"game": g, "slug": slug(g), "art": cat_art(g)} for g in games]}


def channel(sid: str) -> dict:
    """One channel's analytics: now, today / 7 / 30 days / all time (peak, average, hours watched, hours live,
    days live), day by day for 30 days, and its viewers over the last 3 days."""
    with store._lock:
        c = _db()
        ch = c.execute("SELECT * FROM sc_channels WHERE sid=?", (sid,)).fetchone()
        if not ch:
            return {}
        days = c.execute("SELECT day, game, peak, peak_at, mins, hw FROM sc_daily WHERE sid=? ORDER BY day", (sid,)).fetchall()
        t3 = time.time() - 3 * 86400
        samp = c.execute("SELECT ts, MAX(viewers) FROM sc_samples WHERE sid=? AND ts>=? GROUP BY ts ORDER BY ts", (sid, t3)).fetchall()
    today = datetime.now(events.REPORT_TZ).date()
    by = {}
    for r in days:
        z = by.setdefault(r["day"], {"day": r["day"], "peak": 0, "at": None, "mins": 0.0, "hw": 0.0, "games": {}})
        if r["peak"] > z["peak"]:
            z["peak"], z["at"] = r["peak"], r["peak_at"]
        z["mins"] += r["mins"] or 0
        z["hw"] += r["hw"] or 0
        z["games"][r["game"]] = z["games"].get(r["game"], 0) + (r["hw"] or 0)

    def agg(n):
        d0 = (today - timedelta(days=n - 1)).strftime("%Y-%m-%d") if n else ""
        zs = [z for d, z in by.items() if d >= d0]
        mins, hw = sum(z["mins"] for z in zs), sum(z["hw"] for z in zs)
        g = {}
        for z in zs:
            for k, v in z["games"].items():
                g[k] = g.get(k, 0) + v
        return {"peak": max((z["peak"] for z in zs), default=0), "avg": round(hw * 60 / mins) if mins else 0,
                "hw": round(hw), "hours": round(mins / 60, 1), "days": len(zs),
                "games": [k for k, _ in sorted(g.items(), key=lambda kv: -kv[1])][:4]}
    now = _live_part(None, "global")["_now"].get(sid, 0)
    step = max(1, len(samp) // 240)
    return {"sid": sid, "name": ch["name"], "platform": ch["platform"], "url": ch["url"],
            "logo": _logo({"sid": sid, "logo": ch["logo"]}), "title": ch["title"], "game": ch["game"],
            "country": (country_of(ch["country"]) or ("", 0, ""))[2] or ("India" if ch["india"] else ""),
            "first_seen": ch["first_seen"], "last_live": ch["last_live"], "now": now,
            "periods": {"today": agg(1), "7d": agg(7), "30d": agg(30), "all": agg(0)},
            "days": [{"day": z["day"], "peak": z["peak"], "at": z["at"], "hours": round(z["mins"] / 60, 1),
                      "hw": round(z["hw"]), "avg": round(z["hw"] * 60 / z["mins"]) if z["mins"] else 0,
                      "game": max(z["games"], key=z["games"].get) if z["games"] else ""}
                     for d, z in sorted(by.items()) if d >= (today - timedelta(days=29)).strftime("%Y-%m-%d")],
            "recent": [[r[0], r[1]] for r in samp[::step]],
            **(_yt_extra(sid) if sid.startswith("yt:") else {"superchats": None, "top_superchats": [], "stats": None})}


def _yt_extra(sid: str) -> dict:
    from tracker import ytextra
    try:
        return ytextra.channel_extra(sid)
    except Exception as e:
        print(f"Channel extras for {sid}: {str(e)[:120]}")
        return {"superchats": None, "top_superchats": [], "stats": None}


_COUNTRIES = None
# Kick/Twitch give no country, only the stream language. These languages are spoken mainly in one country, so a
# stream in them is placed there (shown on the map as estimated). English, Spanish, Arabic, Chinese stay unknown.
LANG_COUNTRY = {"ko": "KR", "ja": "JP", "th": "TH", "vi": "VN", "tr": "TR", "pl": "PL", "uk": "UA", "it": "IT",
                "cs": "CZ", "hu": "HU", "id": "ID", "el": "GR", "fi": "FI", "sv": "SE", "da": "DK", "no": "NO",
                "ro": "RO", "bg": "BG", "he": "IL", "hi": "IN", "ta": "IN", "te": "IN", "bn": "IN",
                "pt": "BR", "de": "DE", "fr": "FR", "ru": "RU", "nl": "NL"}   # Portuguese live streams are overwhelmingly Brazilian


def country_of(v: str):
    """('IN', 356, 'India') for a YouTube country code or name, or None."""
    global _COUNTRIES
    if _COUNTRIES is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "countries.json"), encoding="utf-8") as f:
            raw = json.load(f)
        _COUNTRIES = {}
        for code, (num, *names) in raw.items():
            _COUNTRIES[code.lower()] = (code, num, names[0])
            for n in names:
                _COUNTRIES.setdefault(n.lower(), (code, num, names[0]))
    v = (v or "").strip().lower()
    return _COUNTRIES.get(v) if v and v != "-" else None


def geo(region: str = "global") -> dict:
    """Live viewers by the streamer's country, for the globe. Country = the YouTube channel's own setting, or India
    for channels judged Indian. Kick/Twitch expose no country, so their non-Indian streams are 'unknown'."""
    region = _region(region)
    lv = _live_part(None, region)
    out, unknown, known, est = {}, 0, 0, 0
    for x in lv["_live"]:
        ct = country_of(x.get("country")) or (country_of("IN") if x.get("india") else None)
        if not ct and LANG_COUNTRY.get((x.get("language") or "").lower()[:2]):
            ct = country_of(LANG_COUNTRY[(x.get("language") or "").lower()[:2]])
            est += x["viewers"]
        if not ct:
            unknown += x["viewers"]
            continue
        known += x["viewers"]
        z = out.setdefault(ct[0], {"country": ct[0], "num": ct[1], "name": ct[2], "viewers": 0, "channels": 0,
                                   "games": {}, "top": []})
        z["viewers"] += x["viewers"]
        z["channels"] += 1
        z["games"][x["game"]] = z["games"].get(x["game"], 0) + x["viewers"]
        if len(z["top"]) < 60:
            z["top"].append({k: x.get(k) for k in ("sid", "name", "platform", "url", "logo", "game", "viewers", "section")})
    for z in out.values():
        z["games"] = [{"game": g, "slug": slug(g), "viewers": v, "section": section_of(g)}
                      for g, v in sorted(z["games"].items(), key=lambda kv: -kv[1])[:12]]
        named = [g for g in z["games"] if g["game"] != "Other"]
        z["label"] = named[0]["game"] if named else (z["top"][0]["name"] if z["top"] else "")
    return {"updated": lv["updated"], "countries": sorted(out.values(), key=lambda z: -z["viewers"]),
            "known": known, "unknown": unknown, "estimated": est}


def clean() -> dict:
    """Re-judge every channel seen so far as Indian or not (looking up YouTube countries not yet known) and rebuild
    the India totals from the raw readings. Nothing is deleted: non-Indian channels stay in the global view.
    Run on the Mac (the tracker can keep running)."""
    with store._lock:
        chans = [dict(r) for r in _db().execute("SELECT sid, platform, name, title, country, language FROM sc_channels")]
    need = [x["sid"][3:] for x in chans if x["platform"] == "youtube" and not x["country"]]
    found = yt_countries(need) if need else {}
    allow, bad, checked = allowed(), [], 0
    with store._lock:
        c = _db()
        for x in chans:
            if x["platform"] == "youtube" and not x["country"] and x["sid"][3:] in found:
                x["country"] = found[x["sid"][3:]]
                checked += 1
            ok = verdict(x, x["country"], allow)
            c.execute("UPDATE sc_channels SET india=?, country=COALESCE(?, country) WHERE sid=?",
                      (1 if ok else 0, x["country"], x["sid"]))
            if not ok:
                bad.append(x["sid"])
        t0 = c.execute("SELECT MIN(ts) FROM sc_samples").fetchone()[0] or 0
        c.execute("DELETE FROM sc_cat WHERE ts >= ?", (t0,))
        ind = "FROM sc_samples s JOIN sc_channels c ON c.sid=s.sid WHERE COALESCE(c.india,1)=1"
        c.execute(f"INSERT OR REPLACE INTO sc_cat SELECT s.ts, s.game, SUM(s.viewers), COUNT(*) {ind} GROUP BY s.ts, s.game")
        c.execute(f"INSERT OR REPLACE INTO sc_cat SELECT s.ts, ?, SUM(s.viewers), COUNT(*) {ind} GROUP BY s.ts", (ALL,))
        c.commit()
    _SCAN["ts"] = None
    return {"channels": len(chans), "not_indian": len(bad), "countries_looked_up": checked,
            "examples_not_indian": [x["name"] for x in chans if x["sid"] in set(bad)][:15]}


def probe() -> str:
    """One check of every source, for setting up (no secret values printed)."""
    lines = []
    try:
        res = yt_live_page()
        lines.append(f"YouTube Live page (India): {len(res)} live streams" +
                     (f", top {res[0]['channel']} {res[0]['viewers']:,}" if res else ""))
        ids = list(dict.fromkeys(r["channel_id"] for r in res))[:8]
        got = yt_countries(ids)
        names = {r["channel_id"]: r["channel"] for r in res}
        lines.append(f"YouTube channel countries ({'Data API' if os.getenv('YOUTUBE_API_KEY') else 'About pages'}): " +
                     ", ".join(f"{names[c]} {got.get(c, 'failed')}" for c in ids))
    except Exception as e:
        lines.append(f"YouTube Live page failed: {str(e)[:150]}")
    try:
        res = yt_search(QUERIES[0])
        lines.append(f"YouTube search '{QUERIES[0]}': {len(res)} live streams" +
                     (f", top {res[0]['channel']} {res[0]['viewers']:,}" if res else ""))
    except Exception as e:
        lines.append(f"YouTube search failed: {str(e)[:150]}")
    for g in ("BGMI", "PUBG Mobile", "PUBG: Battlegrounds", "Free Fire", "GTA V", "Valorant"):
        try:
            loc = _local_art(g)
            url, src = (loc, "static/gameart") if loc else resolve_art(g)
            lines.append(f"Cover art {g}: {src}" + ("" if url else " (initials shown; add static/gameart/" + slug(g) + ".png)"))
        except Exception as e:
            lines.append(f"Cover art {g} failed: {str(e)[:100]}")
    for p in ("twitch", "kick"):            # the India-wide discovery the page uses
        if not platforms._keys(p):
            lines.append(f"{platforms.NAMES[p]} India streams: no keys")
            continue
        errs = {}
        rows = {r["vid"]: r for r in platform_india(p, errs)}.values()
        top = sorted(rows, key=lambda r: -r["viewers"])[:3]
        lines.append(f"{platforms.NAMES[p]} India streams: {len(rows)} live" +
                     (", top " + ", ".join(f"{r['channel']} {r['viewers']:,} ({r.get('category') or '-'})" for r in top) if top else ""))
        for k, v in errs.items():
            lines.append(f"  {k} FAILED: {v}")
    for p in ("kick", "twitch"):
        st = platforms.status()[p]
        try:
            ids = seeds()[p] or (["skyesports"] if p == "kick" else [])
            if ids and (p == "kick" or platforms._keys(p)):
                r = platforms._by_ids(p, ids)
                lines.append(f"{platforms.NAMES[p]} channels {ids}: {len(r)} live ({st})")
            else:
                lines.append(f"{platforms.NAMES[p]}: {st}")
        except Exception as e:
            lines.append(f"{platforms.NAMES[p]} failed: {str(e)[:150]} ({st})")
    return "\n".join(lines)


def top(period: str = "today", n: int = 20) -> str:
    d = data(period)
    out = [f"India live now: {events.fmt_n(d['live_total'])} viewers across {d['live_count']} streams"]
    out += [f"  {events.fmt_n(x['viewers']):>7}  {x['name']} ({platforms.NAMES.get(x['platform'], '')}, {x['game']})"
            for x in d["live"][:n]]
    out.append(f"\nTop streamers, {period}: hours watched / peak / average")
    out += [f"  {i + 1:>3}. {x['name']} ({platforms.NAMES.get(x['platform'], '')}, {x['game']}): "
            f"{events.fmt_n(x['hw'])}h / {events.fmt_n(x['peak'])} / {events.fmt_n(x['avg'])}"
            for i, x in enumerate(d["board"][:n])]
    return "\n".join(out)
