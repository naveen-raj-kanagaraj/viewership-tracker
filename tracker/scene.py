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
import html
import functools
import json
import os
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from tracker import events, platforms, store

SCENE_SEC = int(os.getenv("SCENE_SEC", "120"))
FRESH_SEC = int(os.getenv("SCENE_FRESH_SEC", "3600"))     # a late scan never blanks the pages (25 Nov: 14-minute scans
                                                           # crossed the old 15-minute line and every live number showed 0)
SCENE_YT_SEC = int(os.getenv("SCENE_YT_SEC", "300"))
MIN_VIEWERS = int(os.getenv("SCENE_MIN_VIEWERS", "20"))
KEEP_DAYS = int(os.getenv("SCENE_KEEP_DAYS", "3"))         # raw per-scan readings; per-day totals are kept for good
GLOBAL_MIN = int(os.getenv("SCENE_GLOBAL_MIN", "100"))     # non-Indian streams smaller than this are left out
TWITCH_PAGES = int(os.getenv("SCENE_TWITCH_PAGES", "20"))  # global Twitch: top 100 x this many (stops below GLOBAL_MIN)
_KICK_COOL = [0.0]
KICK_CATS = int(os.getenv("SCENE_KICK_CATS", "8"))         # global Kick: top 100 overall + top 100 in this many categories
YT_LIVE_PAGES = int(os.getenv("SCENE_YT_LIVE_PAGES", "4"))  # YouTube Live page: first page + this many "more" pages
YT_RECOUNT = int(os.getenv("SCENE_YT_RECOUNT", "400"))     # YouTube streams re-counted each scan (biggest first)
FAST_MAX = int(os.getenv("SCENE_FAST_MAX", "300"))         # (old single cap, kept for the env name)
# Re-read every 2 seconds, biggest first, plus the biggest Indian ones on top (GTA 6 launch, 18 Nov 2026):
FAST_TW = int(os.getenv("SCENE_FAST_TW", "1000"))         # Twitch: 100 a call, 10 calls / 2 s = 300 a minute of 800
FAST_KICK = int(os.getenv("SCENE_FAST_KICK", "300"))      # Kick: 50 a call; halves for 10 minutes if Kick says 429
FAST_IN = {"twitch": int(os.getenv("SCENE_FAST_IN_TW", "300")),   # extra Indian channels beyond the top list
           "kick": int(os.getenv("SCENE_FAST_IN_KICK", "200"))}
_KFAST = {"cap": None, "until": 0.0}
LANGS = [x.strip() for x in os.getenv("SCENE_LANGS", "hi").split(",") if x.strip()]
# Twitch streams swept by language to find small Indian streams (they're judged by their chat after that)
SWEEP_LANGS = [x.strip() for x in os.getenv("SCENE_SWEEP_LANGS", "hi,ta,te,ml,kn,mr,gu,or").split(",") if x.strip()]
LANG_PAGES = int(os.getenv("SCENE_LANG_PAGES", "5"))
# Kick and Twitch have no country filter. Besides the India languages above, the top streams overall and in the
# categories Indians stream most are read, and a stream counts as Indian if its title is written in an Indian script
# or says so (hindi, india, desi, tamil, bgmi ...).
INDIA_MARK = re.compile(r"[\u0900-\u0D7F]|\b(hindi|india|indian|desi|bharat|hinglish|tamil|telugu|kannada|malayalam|"
                        r"marathi|bengali|bangla|punjabi|gujarati|odia|assamese|bgmi|bmps|bgis|bmsd|bmic|"
                        r"soulcity|yatrarp|yatra rp|mumbai|delhi|bangalore|bengaluru|hyderabad|chennai|kolkata|pune)\b", re.I)
INDIA_CATS = {"kick": [x.strip() for x in os.getenv("SCENE_KICK_CATS", "PUBG Mobile,Free Fire,Grand Theft Auto V,"
                                                   "Valorant,Just Chatting,Battlegrounds Mobile India").split(",") if x.strip()],
              "twitch": [x.strip() for x in os.getenv("SCENE_TWITCH_CATS", "PUBG MOBILE,Garena Free Fire,Grand Theft Auto V,"
                                                     "VALORANT,Just Chatting,Battlegrounds Mobile India").split(",") if x.strip()]}
# GTA 6: hidden until it releases (owner, 12 Nov 2026), then shown everywhere and swept worldwide (every stream on
# Twitch, Kick and YouTube). It releases at midnight local time, first in New Zealand: 18 Nov 2026, 11:00 UTC.
# GTA6_SHOW=1 shows it now, GTA6_SHOW=0 keeps it hidden; unset = automatic at release.
GTA6_RELEASE = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc).timestamp()   # an hour early: nobody is missed


def gta6_on() -> bool:
    v = os.getenv("GTA6_SHOW", "")
    return v == "1" or (v != "0" and time.time() >= GTA6_RELEASE)


GTA6_SHOW = gta6_on()                     # at start (old name, kept for callers)


def _hidden() -> set:
    return set() if gta6_on() else {"GTA 6", "Grand Theft Auto VI"}


def shown(g) -> bool:
    return (g if isinstance(g, str) else (g or {}).get("game")) not in _hidden()


def pinned() -> list:                     # always first in Categories
    return [g.strip() for g in os.getenv("SCENE_PINNED", "GTA 6" if gta6_on() else "").split(",") if g.strip()]


# Titles in Chinese, Japanese, Korean, Thai, Arabic or Cyrillic script are not Indian streams even when the
# streamer tagged them Hindi (it happens on Twitch).
# Hinglish: Indian streamers on Kick/Twitch often title in English letters ("aaj kya khelenge bhai"). Urdu speakers use the
# same words, so a title that says Pakistan is not counted.
HINGLISH = re.compile(r"\b(bhai|bhaiyo|bhaiya|yaar|dosto|aaj|kya|nahi|karenge|khelenge|chalo|masti|pagal|paisa|dhamaka|"
                      r"bigg? ?boss|ipl|gareeb|jeetenge)\b", re.I)
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
            if r.status_code >= 400:          # keep YouTube's reason (quotaExceeded, keyInvalid ...) in the error
                raise RuntimeError(f"YouTube API {r.status_code}: {(r.json().get('error') or {}).get('errors', [{}])[0].get('reason', '') if r.headers.get('content-type', '').startswith('application/json') else r.text[:80]}")
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
    with store.reading():
        for sid, ctry in _db().execute("SELECT sid, country FROM sc_channels WHERE platform='youtube' AND country IS NOT NULL"):
            _CTRY[sid[3:]] = ctry
    _CTRY.setdefault("", "-")


def allowed() -> set:
    return set(store.kv_get("scene_allowed") or [])


_KNOWN = {"at": 0, "set": frozenset()}


def india_known() -> frozenset:
    """Channels known to be Indian from what they did, each with its reason (_KNOWN['why']): the official channels of
    this site's Indian event trackers and their streams whose title names the event (BMSD, BMIC, CEGC ... / BGMI), the
    events' own Kick lists, every channel that has streamed BGMI (only played in India), past broadcast titles.
    Not every stream an event tracker came across: on 23 Nov that let in Greek ('NA LCQ MP FINALS WATCH PARTY', Apex)."""
    if time.time() - _KNOWN["at"] < 3600:
        return _KNOWN["set"]
    why = {}
    try:
        for k, v in events.PRESETS.items():
            kk = v.get("kick") or {}
            for slug_ in list(kk.get("official") or []) + list(kk.get("channels") or []):
                why.setdefault("kick:" + slug_.lower(), f"on the {k.upper()} event's channel list")
        with store.reading():
            c = store.conn()
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='ev_streams'").fetchone():
                for ev, vid, cid, kind, title in c.execute("SELECT event, vid, channel_id, kind, title FROM ev_streams"):
                    if kind != "official" and not INDIA_STRONG.search(title or ""):
                        continue                  # a stream the tracker came across, not about the Indian event
                    sid = vid.lower() if vid and vid.startswith(("kick:", "twitch:")) else \
                        "yt:" + cid if cid and cid.startswith("UC") else None
                    if sid:
                        why.setdefault(sid, f"streamed the {str(ev).upper()} event ('{(title or '')[:40]}')")
            for (sid,) in c.execute("SELECT DISTINCT sid FROM sc_daily WHERE game='BGMI'"):
                why.setdefault(sid, "streamed BGMI (only played in India)")
        for sid in _past_titles_india():
            why.setdefault(sid, "2+ past broadcast titles in Hindi / Indian languages / about Indian events")
        for k in seeds().get("kick", []):
            why.setdefault("kick:" + k.lower(), "on the hand-made list of Indian streamers")
        for sid in allowed():
            why.setdefault(sid, "allowed by hand")
    except Exception as e:
        print(f"Known Indian channels: {str(e)[:100]}")
        return _KNOWN["set"]
    _KNOWN.update(at=time.time(), set=frozenset(why), why=why)
    return _KNOWN["set"]


def _past_titles_india() -> set:
    """Kick / Twitch channels whose past broadcasts (their VOD lists) say India at least twice: in Hindi or another
    Indian script, 'Hindi stream', Bigg Boss watch party, BGMI ..., with none of them clearly from another country.
    So a channel whose latest title is just 'GTA 6 Live' still counts (owner, 23 Nov: Indian streamers only, but all of them)."""
    hits, bad, tot = {}, set(), {}
    with store.reading():
        c = store.conn()
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='yt_videos'").fetchone():
            return set()
        for lo, hi in (("kick:", "kick;"), ("twitch:", "twitch;")):
            for sid, title in c.execute("SELECT sid, title FROM yt_videos WHERE sid >= ? AND sid < ?", (lo, hi)):
                t = title or ""
                tot[sid] = tot.get(sid, 0) + 1
                if foreign_sign(t):
                    bad.add(sid)
                elif _ind_script(t) or INDIA_STRONG.search(t) or _hindi_words(t) >= 2:
                    hits[sid] = hits.get(sid, 0) + 1
    # 2+ titles AND a fifth of them: 2 odd titles among 910 Apex streams made Greek 'Indian' (23 Nov)
    return {sid for sid, n in hits.items() if n >= 2 and n >= 0.2 * tot[sid] and sid not in bad}


def mark_known_india() -> int:
    """Flag the known Indian channels as Indian in sc_channels, so their past days count in India's rankings, and
    re-judge every Kick / Twitch channel from its last title with today's rules (the scan does the same each time a
    channel is live; this applies a rule change to channels that are offline now). Judged outside the write lock."""
    known = india_known()
    if not known:
        return 0
    wrong, right = [], []
    with store.reading():
        rows = store.conn().execute("SELECT sid, name, title, country, language, COALESCE(india,0), game, tags FROM sc_channels "
                                    "WHERE platform IN ('kick','twitch') AND COALESCE(title,'')<>''").fetchall()
    _PREV_IND["set"] = frozenset(r[0] for r in rows if r[5])
    for sid, nm, tt, ct, lg, ind, gm, tg in rows:   # known ones too: a clearly foreign title beats an old BGMI stream
        v = verdict({"sid": sid, "platform": sid.split(":")[0], "name": nm or "", "title": tt or "", "language": lg or "",
                     "game": gm or "", "tags": tg or ""}, ct, known)
        if ind and not v:
            wrong.append(sid)
        elif v and not ind:
            right.append(sid)
    from tracker import langsig
    langsig.yt_load()
    with store.reading():
        yrows = store.conn().execute("SELECT sid, COALESCE(india,0) FROM sc_channels WHERE platform='youtube' "
                                     "AND COALESCE(country,'-') IN ('-','')").fetchall()
    for sid, ind in yrows:                    # YouTube channels with no country: their chat decides when it can
        cv = langsig.yt_verdict(sid)
        if cv is True and not ind:
            right.append(sid)
        elif cv is False and ind and sid not in _curated():
            wrong.append(sid)
    n = 0
    with store._lock:
        c = store.main()
        L = sorted(set(known) - set(wrong) - {r[0] for r in rows if r[5] == 0 and r[0] not in right})
        for i in range(0, len(L), 500):
            part = L[i:i + 500]
            n += c.execute(f"UPDATE sc_channels SET india=1 WHERE COALESCE(india,0)=0 AND sid IN ({','.join('?' * len(part))})",
                           part).rowcount
        for flag, ids in ((1, right), (0, wrong)):
            for i in range(0, len(ids), 500):
                part = ids[i:i + 500]
                c.execute(f"UPDATE sc_channels SET india=? WHERE sid IN ({','.join('?' * len(part))})", [flag] + part)
        c.commit()
    if wrong:
        print(f"Unmarked {len(wrong)} channels no longer counted as Indian: {', '.join(wrong[:10])}")
    return n + len(right) + len(wrong)


_IND_LETTERS = re.compile(r"[\u0900-\u0D7F]")
_IND_SYMBOLS = "\u0950\u0AD0\u0BD0\u0964\u0965"     # Om signs and danda: decoration, used by non-Indian streamers too


_INDW = re.compile(r"[\u0900-\u0D7F]+")
_BENGALI = re.compile(r"[\u0980-\u09FF]")


def _ind_letters(t: str) -> str:
    """Real letters of Indian scripts that form words (2+ in a row): digits (୨୧, ੭), symbols (৻, ॐ, ।) and kaomoji
    eyes (ಠ_ಠ) are decoration used by streamers everywhere (23 Nov: OlivesCrossing, mochi_miu, DerDummbabbler were
    counted as Indian because of them)."""
    import unicodedata
    out = []
    t = (t or "").replace("\u0D26\u0D4D\u0D26\u0D3F", " ")      # 'ദ്ദി(' is a kaomoji arm (TheClumsyFellow, Pamiette)
    for w in _INDW.findall(t):
        w = "".join(ch for ch in w if unicodedata.category(ch)[0] in "LM" and ch != "\u0CA0" and ch not in _IND_SYMBOLS)
        if len(w) >= 2:
            out.append(w)
    return "".join(out)


def _ind_script(t: str) -> bool:
    """Written in an Indian script: at least 3 real Indian letters in words, and more of them than letters in another
    non-Latin script ('ૐ Витус Бритва' is Russian)."""
    import unicodedata
    n = sum(1 for ch in _ind_letters(t) if unicodedata.category(ch)[0] == "L")
    return n >= 4 and n > len(FOREIGN.findall(t or ""))


IND_LANGS = set(LANGS) | {"hi", "ta", "te", "kn", "ml", "mr", "gu", "or", "hindi", "tamil", "telugu", "kannada",
                          "malayalam", "marathi", "gujarati", "odia"}    # stream language tags (not Bengali / Punjabi / Urdu)


def india_hint(x: dict) -> bool:
    """Anything that might make a Kick / Twitch channel Indian: its chat is then read to decide (langsig)."""
    s_ = (x.get("title") or "") + " " + (x.get("tags") or "") + " " + (x.get("name") or "")
    return bool(_INDW.search(s_) or _hindi_words(s_) or INDIA_STRONG.search(s_) or INDIA_WEAK.search(s_)
                or "\U0001F1EE\U0001F1F3" in s_ or (x.get("language") or "").lower() in IND_LANGS
                or x.get("sid") in _PREV_IND["set"])


_PREV_IND = {"set": frozenset()}         # channels flagged Indian in the database (refreshed hourly)

# Not Indian, says the owner (23 Nov), whatever their titles say
NOT_INDIA_SIDS = {"twitch:guddu_kim", "twitch:olivescrossing", "twitch:sig07tv", "twitch:nozygoat"}
# Indian, says the owner (23 Nov), whatever their titles say ('🇬🇧🇮🇳 British Indian Gamergirl')
INDIA_SIDS = {"twitch:invadingdarkness"}

_FLAG = re.compile(r"([\U0001F1E6-\U0001F1FF]{2})")
NOT_INDIA = re.compile(r"\b(pakistan|pakistani|karachi|lahore|islamabad|urdu|bangladesh|bangladeshi|dhaka|nepal|nepali|"
                       r"kathmandu|sri ?lanka|lankan)\b", re.I)
# Words that only appear in titles written in Portuguese, Spanish, French or German (none are Hindi / English words)
_OTHER_LANG_WORDS = set("""uma dando jogando jogo você voce não nao agora hoje vamos então galera los las con jugando
ahora hoy una del pero también tambien siempre nosotros und mit ich nicht heute wir spielen avec les une aujourd nous
pour sur très tres""".split())
# Indians abroad count (owner, 23 Nov: 'InvadingDarkness is British Indian, add her')
DIASPORA = re.compile(r"\b(british[- ]indian|indian[- ](american|canadian|australian|origin)|indo[- ](canadian|american)|nri)\b", re.I)
# Words that alone say a stream is Indian (languages, Indian games / events / servers)
INDIA_STRONG = re.compile(r"\b(hindi|hinglish|tamil|telugu|kannada|malayalam|marathi|gujarati|assamese|bhojpuri|haryanvi|"
                          r"bgmi|bmps|bgis|bmsd|bmic|cegc|soulcity|lifeinsoulcity|yatrarp|yatra rp|showtown|s8ul|upthrust|"
                          r"battlin|sc[o0]ut ?op|bigg ?boss|bigg?bos\w*|big boss (20|19|tamil|telugu|kannada|malayalam|marathi)|"
                          r"weekend ka vaar|india|bharat|indian(?! (tts|accent|voice|ocean))|"
                          r"indian (streamer|gamer|gaming|girl|boy|guy|creator|audience)|ind vs (nz|aus|eng|sa|pak|wi|sl|ban))\b", re.I)
# Another language's tag: 'EN / DE', '[GER/ENG]', 'ENG/ESP' ('Hindi man Yes' in a German title is a joke)
_LANG_TAG = re.compile(r"(\[|\b)(ger|deu|esp|es|pt|br|fr|vtafr|ita|tr|ru|my)\s*(/|\])|\b(en|eng)\s*/\s*(de|ger|es|esp|pt|br|fr|my)\b", re.I)
# Words that need a second sign (travellers say 'India', diaspora says 'Indian', Pakistanis say 'desi')
INDIA_WEAK = re.compile(r"\b(mumbai|delhi|bangalore|bengaluru|hyderabad|chennai|kolkata|pune)\b", re.I)
HINDI_WORDS = set("""aaj aaja aajao abhi acha accha apna apne aapka aapke aur baad baat bahot bahut bhai bhaiyo bhaiyon bhaiya
bhi bhot bilkul bohot chalo chalte chalenge dekho dekhte dekhenge didi dobara dost dosto doston dhamaka gareeb gaya gayi gye
hamara hamare hai hain hoga hogi humko jaldi jeet jeetenge jyada zyada kaha kahan kaise kaisa karenge karna karne karo karte
karu krte khatam khelenge khelo khelna khelte kitna kitne kuch kya kyun kyunki lekin logo logon magar masti matlab mera meri
milte milenge mujhe nahi nahin nhi paaji pagal paisa pakka patakhe pehle phir raha rahe rhe saath sabke sabko sabse sach shuru
suno tera teri thoda tujhe tumhara unka unke wala wale wali wapas yaar yaaro yaaron""".split())


def _hindi_words(t: str) -> int:
    w = set(re.findall(r"[a-z]+", (t or "").lower()))
    return len(w & HINDI_WORDS) + (1 if re.search(r"\bbig boss\b", t or "", re.I) else 0)


def _name_india(n: str) -> bool:
    """A channel name that says India: ends in india / indian ('focusedindian'), starts with 'india_' / 'indian_', or
    has an Indian esports / server name in it. Not just 'india' anywhere: 'indialovewestbrooks', 'Lzindiario',
    'IndiaGutierDj', 'BigBossRobinson' are not Indian (23 Nov)."""
    k = re.sub(r"[\d_]+$", "", (n or "").lower())
    return bool(re.search(r"indian?$|^indian?_|^desi_|bgmi|s8ul|scoutop|soulcity|bharat", k))


def _bio_india(b: str) -> str:
    """What in a streamer's own bio says India ('' if nothing): a bio is about the person, so a city or 'India' there
    means where they're from, unlike a stream title ('Kochi, India' from a traveller)."""
    m = DIASPORA.search(b) or INDIA_STRONG.search(b) or INDIA_WEAK.search(b) or re.search(r"\+91[\s-]?\d", b)
    if m:
        return f"'{m.group(0)}'"
    if "\U0001F1EE\U0001F1F3" in b:
        return "India's flag"
    if _ind_script(b):
        return "written in an Indian script"
    if _hindi_words(b) >= 2:
        return "written in Hindi"
    return ""


def foreign_sign(t: str, n: str = "") -> bool:
    """Clear sign of another country: a flag that isn't India's, Pakistan / Bangladesh / Nepal ..., another script,
    or Bengali without anything Indian (on Kick / Twitch Bengali streams are almost all from Bangladesh, e.g. FFWS
    watch parties; 23 Nov kuttush17, raadvai_yt)."""
    s = (t or "") + " " + (n or "")
    flags = [f for f in _FLAG.findall(s) if f != "\U0001F1EE\U0001F1F3"]
    vs = re.search(r"\b(india|ind)\b.{0,12}\bvs?\b|\bvs?\b.{0,12}\b(india|ind)\b", s, re.I)   # 'India vs Pakistan': a match
    if DIASPORA.search(s):
        return False
    if len(set(re.findall(r"[a-zà-ÿ]+", s.lower())) & _OTHER_LANG_WORDS) >= 2:
        return True                           # a title in Portuguese / Spanish / French / German ('Dando uma volta em
                                              # Vice city': India_Noob_ is Brazilian, 23 Nov)
    if (flags and not vs and "\U0001F1EE\U0001F1F3" not in s) or (NOT_INDIA.search(s) and not vs) or _LANG_TAG.search(s):
        return True                           # 🇬🇧🇮🇳 together: an Indian abroad, not a foreign channel
    if FOREIGN.search(s) and not _ind_script(s):
        return True
    ind = _ind_letters(s)
    if ind and all(_BENGALI.match(ch) for ch in ind) and "\U0001F1EE\U0001F1F3" not in s and not INDIA_STRONG.search(s) \
            and not INDIA_WEAK.search(s):
        return True
    return False


def verdict(x: dict, country: str = None, allow: set = frozenset()) -> bool:
    """True if this live channel counts as Indian."""
    return india_why(x, country, allow)[0]


_TAG_LANG = re.compile(r"\b(hindi|tamil|telugu|kannada|malayalam|marathi|gujarati|bhojpuri|haryanvi|hinglish)\b", re.I)


def india_why(x: dict, country: str = None, allow: set = frozenset()) -> tuple:
    """(Indian?, the reason in words). The reason is shown with the channel's data, so every flag can be checked."""
    sid, t, n = x.get("sid", ""), x.get("title") or "", x.get("name") or ""
    tags = x.get("tags") or ""
    from tracker import overrides
    if sid.lower() in NOT_INDIA_SIDS or sid.lower() in overrides.not_india() or sid in overrides.not_india():
        return False, "owner: not Indian"
    if sid.lower() in INDIA_SIDS or sid.lower() in overrides.india() or sid in overrides.india():
        return True, "owner: Indian"
    if x.get("seeded") or sid in _curated():
        return True, "added by hand / event channel list"
    if x.get("platform") == "youtube":
        if country == "IN":
            return True, "YouTube channel country: India"
        if country and country != "-":
            return False, f"YouTube channel country: {country}"
        from tracker import langsig
        cv = langsig.yt_verdict(sid)
        if cv is not None:
            return cv, "live chat " + ("is" if cv else "is not") + " in Hindi / Hinglish / Indian languages"
    if foreign_sign(t + " " + tags, n):
        return False, "title / tags show another country"
    if x.get("platform") in ("kick", "twitch"):
        from tracker import langsig
        cv = langsig.verdict(sid)
        if cv is not None:
            a_, b_ = langsig.counts(sid)
            if cv is False and langsig.pakistani(sid):
                return False, "chat is Urdu spelled the Pakistani way ('kia', 'hy', 'bohat')"
            return cv, f"chat: {round(100 * a_ / max(1, a_ + b_))}% of {a_ + b_} messages in Hindi / Hinglish / Indian languages"
    if x.get("platform") in ("kick", "twitch"):
        from tracker import profiles
        b = x.get("bio") if "bio" in x else profiles.bio(sid)
        if b:
            bi = _bio_india(b)
            if bi:
                return True, f"bio: {bi}"
            if foreign_sign(b):
                return False, "bio shows another country"
    if x.get("game") == "BGMI":
        return True, "streams BGMI (India only)"
    if sid in allow:
        return True, (_KNOWN.get("why") or {}).get(sid) or "known Indian channel"
    # Twitch / Kick language setting: only languages spoken just in India decide. 'Hindi' alone doesn't: Twitch has no
    # Urdu, so Pakistani streamers pick Hindi (owner, 23 Nov: sig07tv, nozyGOAT are Hindi channels, not Indian); it
    # gets the chat read instead (india_hint).
    if x.get("platform") in ("kick", "twitch") and (x.get("language") or "").lower() in IND_LANGS - {"hi", "hindi"}:
        return True, f"stream language: {x.get('language')}"
    # A 'Hindi' / 'Tamil' tag alone doesn't decide: English-language channels use them too (drtyeyeball, a Tarkov
    # streamer in a US tattoo studio, tagged 'Hindi'; 23 Nov). It only gets the channel's chat read (india_hint).
    travel = (x.get("category") or x.get("game") or "").lower() in ("irl", "travel & outdoors")
    if travel and not (_ind_script(t) or _hindi_words(t) >= 2):
        return False, "travel stream: being in India isn't being Indian"
    if _ind_script(t + " " + n):
        return True, "title written in an Indian script"
    m = DIASPORA.search(t) or INDIA_STRONG.search(t)
    if m:
        return True, f"title: '{m.group(0)}'"
    if "\U0001F1EE\U0001F1F3" in t + n:
        return True, "India's flag in the title / name"
    if _name_india(n):
        return True, "channel name"
    weak = bool(INDIA_WEAK.search(t))
    hw = _hindi_words(t)
    ok = (weak or hw >= 1) if x.get("platform") == "youtube" else (hw >= 2 or (weak and hw >= 1))
    return ok, (f"{hw} Hindi words in the title" if ok else "nothing Indian found")


_CUR = {"at": 0, "set": frozenset()}


def _curated() -> frozenset:
    """Channels marked Indian by hand: allowed ones, the seed lists, the events' own Kick lists."""
    if time.time() - _CUR["at"] < 300:
        return _CUR["set"]
    out = set()
    try:
        out |= allowed()
        out |= {"kick:" + k.lower() for k in seeds().get("kick", [])} | {"twitch:" + k.lower() for k in seeds().get("twitch", [])}
        for v in events.PRESETS.values():
            kk = v.get("kick") or {}
            out |= {"kick:" + s_.lower() for s_ in list(kk.get("official") or []) + list(kk.get("channels") or [])}
    except Exception:
        return _CUR["set"]
    _CUR.update(at=time.time(), set=frozenset(out))
    return _CUR["set"]


def _kick_live(params) -> list:
    j = platforms._get("kick", "https://api.kick.com/public/v1/livestreams", {"sort": "viewer_count", "limit": 100, **params})
    return [platforms._kick_row(s.get("slug") or "", s.get("stream_title"), s.get("viewer_count"),
                                category=(s.get("category") or {}).get("name", ""), pic=s.get("profile_picture") or "",
                                language=s.get("language") or "", uid=s.get("broadcaster_user_id"),
                                tags=s.get("custom_tags") or s.get("tags") or [])
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
                                 "category": s_.get("game_name") or "", "language": s_.get("language") or "",
                                 "tags": " ".join(s_.get("tags") or [])})
                after = (j.get("pagination") or {}).get("cursor")
                if not after or (j.get("data") and j["data"][-1].get("viewer_count", 0) < GLOBAL_MIN):
                    break
            rows += platforms._tw_logins(ESPORTS_TWITCH)
        else:
            top = _kick_live({})
            rows += top
            # Kick lists only 100 per call: also the top 100 in each of the biggest categories
            cats = []
            for x in top:
                if x.get("category") and x["category"] not in cats:
                    cats.append(x["category"])
            if time.time() < _KICK_COOL[0]:       # Kick said "rate limit exceeded": rest the category calls
                cats = []
            for name in cats[:KICK_CATS]:
                try:
                    cid = _category_id("kick", name)
                    if cid:
                        rows += _kick_live({"category_id": cid})
                    time.sleep(0.4)
                except Exception as e:
                    if "429" in str(e):
                        _KICK_COOL[0] = time.time() + 600
                        errors["kick categories"] = "Kick rate limit: category lists paused for 10 minutes (top 100 still counted)"
                        break
                    errors[f"kick category {name}"] = str(e)[:80]
    except Exception as e:
        errors[f"{p} global"] = str(e)[:120]
    return rows


# ---------- worldwide sweep: every stream of a launch game ----------
# For a game everyone streams at once (GTA 6 at release), the usual "biggest streams" reads would miss most of them.
# The sweep reads the game's whole category on Twitch (every page) and Kick (by viewers, newest, and per language),
# and YouTube searches in the main languages and countries with several pages each. Every stream with a viewer
# counts, whatever its size or country.
SWEEP_YT = [("GTA 6", "US", 6), ("GTA 6 live", "US", 6), ("GTA VI", "US", 4), ("Grand Theft Auto VI", "US", 3),
            ("GTA 6 live", "IN", 5), ("GTA 6 live hindi", "IN", 4), ("GTA 6 live tamil", "IN", 2), ("GTA 6 live telugu", "IN", 2),
            ("GTA 6 live bangla", "BD", 2), ("GTA 6 live", "PK", 2), ("GTA 6 en vivo", "MX", 4), ("GTA 6 en directo", "ES", 2),
            ("GTA 6 en vivo", "AR", 2), ("GTA 6 ao vivo", "BR", 5), ("GTA 6 canlı", "TR", 3), ("GTA 6 стрим", "RU", 3),
            ("GTA 6 live deutsch", "DE", 2), ("GTA 6 live français", "FR", 2), ("GTA 6 live italiano", "IT", 2),
            ("GTA 6 live polska", "PL", 2), ("GTA 6 live", "ID", 3), ("GTA 6 live", "PH", 3), ("GTA 6 trực tiếp", "VN", 2),
            ("GTA 6 ไลฟ์", "TH", 2), ("GTA 6 ライブ", "JP", 2), ("GTA 6 생방송", "KR", 2), ("GTA 6 بث مباشر", "SA", 2),
            ("GTA 6 live", "GB", 3), ("GTA 6 live", "CA", 2), ("GTA 6 live", "AU", 2), ("GTA 6 live", "NG", 2), ("GTA 6 live", "EG", 2)]
SWEEP_GAMES = {"GTA 6": {"twitch": ["Grand Theft Auto VI"], "kick": ["Grand Theft Auto VI", "GTA VI", "GTA 6"], "yt": SWEEP_YT}}
SWEEP_TW_PAGES = int(os.getenv("SCENE_SWEEP_TW_PAGES", "400"))     # up to 40,000 Twitch streams of the game
SWEEP_KICK_LANGS = ["en", "es", "pt", "tr", "ar", "ru", "de", "fr", "it", "pl", "id", "hi", "ja", "ko", "th", "vi"]
_SWEEP = {"yt_cool": 0.0, "stats": {}}


def sweep_status() -> dict:
    """What the launch sweep is doing (for /api/sweep): games on, and per source when it last ran and what it found."""
    return {"games": sweep_games(), "release": GTA6_RELEASE, "shown": gta6_on(),
            "yt_resting": max(0, round(_SWEEP["yt_cool"] - time.time())), "kick_resting": max(0, round(_KICK_COOL[0] - time.time())),
            "stats": {k: {"ago": round(time.time() - v[0]), "found": v[1], **({"read_now": v[2]} if len(v) > 2 else {})}
                      for k, v in _SWEEP["stats"].items()}}


def sweep_games() -> list:
    """Games being swept now: GTA 6 from its release (or GTA6_SWEEP=1)."""
    on = os.getenv("GTA6_SWEEP", "") == "1" or (os.getenv("GTA6_SWEEP", "") != "0" and gta6_on() and time.time() >= GTA6_RELEASE)
    return ["GTA 6"] if on else []


def sweep_platform(p: str, game: str, errors: dict) -> list:
    """Every live stream of the game on Twitch (all pages) or Kick (several orderings and languages)."""
    cfg, rows = SWEEP_GAMES[game], []
    if p == "twitch":
        cid = next((c for c in (_category_id("twitch", n) for n in cfg["twitch"]) if c), "")
        if not cid:
            errors[f"sweep twitch {game}"] = "category not found"
            return rows
        after = None
        for _ in range(SWEEP_TW_PAGES):
            j = platforms._get("twitch", "https://api.twitch.tv/helix/streams", {"first": 100, "game_id": cid, **({"after": after} if after else {})})
            d = j.get("data") or []
            for s_ in d:
                login = (s_.get("user_login") or "").lower()
                rows.append({"vid": f"twitch:{login}", "channel": s_.get("user_name") or login, "title": s_.get("title") or "",
                             "viewers": int(s_.get("viewer_count") or 0), "category": s_.get("game_name") or "",
                             "language": s_.get("language") or "", "tags": " ".join(s_.get("tags") or [])})
            after = (j.get("pagination") or {}).get("cursor")
            if not after or not d:
                break
            time.sleep(0.2)                   # <= 300 calls a minute: Twitch allows 800, the 2-second reads need 300
    else:
        if time.time() < _KICK_COOL[0]:
            return rows
        cids = [c for c in dict.fromkeys(_category_id("kick", n) for n in cfg["kick"]) if c]
        # Kick's rate limit is shared with the tournament trackers' 2-second counts (CEGC on Kick went stale when the
        # sweep read 18 lists per category every scan). Each scan: by viewers, newest, and 2 of the languages in turn;
        # streams found once are re-read by broadcaster (_kick_known). While a tracked tournament is live on Kick, the
        # category lists are read every 3rd scan only.
        n_ = _SWEEP["kick_n"] = _SWEEP.get("kick_n", 0) + 1
        if _event_on_kick() and n_ % 3:
            cids = []
        langs = [SWEEP_KICK_LANGS[(n_ * 2 + i) % len(SWEEP_KICK_LANGS)] for i in range(2)]
        for cid in cids:
            for prm in [{}, {"sort": "started_at"}] + [{"language": lg} for lg in langs]:
                try:
                    rows += _kick_live({"category_id": cid, **prm})
                    time.sleep(0.35)
                except Exception as e:
                    if "429" in str(e):
                        _KICK_COOL[0] = time.time() + 300
                        errors["sweep kick"] = "Kick rate limit: sweep resumes in 5 minutes"
                        return rows
                    errors[f"sweep kick {prm}"] = str(e)[:80]
    if p == "kick":
        rows += _kick_known(game, rows, errors)
    _SWEEP["stats"][f"{p}:{game}"] = (time.time(), len(rows))
    return rows


KNOWN_KEEP = 6 * 3600          # a swept stream is re-read for 6 hours after it was last seen live
YT_RECOUNT_MAX = int(os.getenv("SCENE_SWEEP_YT_RECOUNT", "800"))   # YouTube streams re-counted per scan beyond search


def _kick_known(game: str, rows: list, errors: dict) -> list:
    """Kick lists at most 100 streams per query and has no next page, so a launch with thousands of streams can't be
    read from the category alone. Every stream the sweep has ever found is remembered and re-read by broadcaster
    (50 per call) until it ends, so a small stream found once (in 'newest' or a language list) stays counted."""
    known = _SWEEP.setdefault(f"kick_known:{game}", {})
    now = time.time()
    seen = set()
    for r in rows:
        uid = platforms._kick_uid.get(r["vid"])
        if uid:
            known[uid] = now
            seen.add(uid)
    for uid in [u for u, t in known.items() if now - t > KNOWN_KEEP]:
        known.pop(uid, None)
    ask = [u for u in sorted(known, key=lambda u: -known[u]) if u not in seen][:(500 if not _event_on_kick() else 200)]
    out = []
    for i in range(0, len(ask), 50):
        if time.time() < _KICK_COOL[0]:
            break
        part = ask[i:i + 50]
        try:
            j = platforms._get("kick", "https://api.kick.com/public/v1/livestreams",
                               [("broadcaster_user_id", u) for u in part] + [("limit", 100)])
        except Exception as e:
            if "429" in str(e):
                _KICK_COOL[0] = time.time() + 300
            errors["sweep kick known"] = str(e)[:80]
            break
        for s_ in j.get("data") or []:
            if not s_.get("slug"):
                continue
            cat = (s_.get("category") or {}).get("name", "")
            if classify(cat, s_.get("stream_title") or "") != game:
                continue                      # switched game: no longer this sweep's
            known[s_.get("broadcaster_user_id")] = now
            out.append(platforms._kick_row(s_["slug"], s_.get("stream_title"), s_.get("viewer_count"), category=cat,
                                           pic=s_.get("profile_picture") or "", language=s_.get("language") or "",
                                           uid=s_.get("broadcaster_user_id")))
        time.sleep(0.35)
    _SWEEP["stats"][f"kick known:{game}"] = (now, len(known), len(out))
    return out


def yt_search_pages(query: str, gl: str, pages: int) -> list:
    """A live search and its next pages (each about 20 streams)."""
    hdr = {"User-Agent": events._UA, "Content-Type": "application/json", "Origin": "https://www.youtube.com"}
    r = events._http.post("https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
                          json={"context": {"client": _itv(gl)}, "query": query, "params": _SEARCH_LIVE}, headers=hdr, timeout=10)
    r.raise_for_status()
    j = r.json()
    items = _renderers(j)
    for _ in range(pages - 1):
        tok = _continuation(j)
        if not tok:
            break
        r = events._http.post("https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
                              json={"context": {"client": _itv(gl)}, "continuation": tok}, headers=hdr, timeout=10)
        if r.status_code >= 400:
            break
        j = r.json()
        got = _renderers(j)
        if not got:
            break
        items += got
    return _parse(items)


def sweep_youtube(game: str, errors: dict) -> list:
    """YouTube: the game's searches in the main languages and countries, several pages each, in parallel."""
    if time.time() < _SWEEP["yt_cool"]:
        return []
    jobs = SWEEP_GAMES[game]["yt"]
    res = list(_YPOOL.map(lambda a: _try(yt_search_pages, *a), jobs))
    bad = sum(1 for r_ in res if r_ == "err")
    if bad > len(jobs) // 2:                  # YouTube is refusing: rest 5 minutes rather than get blocked
        _SWEEP["yt_cool"] = time.time() + 300
        errors[f"sweep youtube {game}"] = f"{bad}/{len(jobs)} searches failed; resting 5 minutes"
    # a "GTA 6 live" search also returns streams of other games (a BGMI stream): keep those whose title names this
    # game or no game at all (a GTA 6 stream titled "Vice City day 1"), drop ones clearly about another game
    out = [s_ for r_ in res if r_ != "err" for s_ in r_ if classify("", s_.get("title") or "") in (game, "", "Other")]
    out += _yt_known(game, out)
    _SWEEP["stats"][f"youtube:{game}"] = (time.time(), len(out))
    return out


def _yt_known(game: str, found: list) -> list:
    """YouTube search shows each query's top results only. Every live video the sweep has found is remembered and,
    when this scan's searches didn't return it, re-counted from YouTube's live counter (no API quota), the biggest
    first, up to YT_RECOUNT_MAX a scan. A video with no live count three times running has ended and is dropped."""
    known = _SWEEP.setdefault(f"yt_known:{game}", {})
    now = time.time()
    got = set()
    for s_ in found:
        known[s_["vid"]] = {**s_, "seen": now, "miss": 0}
        got.add(s_["vid"])
    for v in [v for v, k in known.items() if now - k["seen"] > KNOWN_KEEP or k["miss"] >= 3]:
        known.pop(v, None)
    ask = sorted((v for v in known if v not in got), key=lambda v: -(known[v].get("viewers") or 0))[:YT_RECOUNT_MAX]
    out, errs = [], 0
    for v, n in zip(ask, _YPOOL.map(_safe_count, ask)):
        k = known.get(v)
        if n == "err":
            errs += 1
        if k is None or n == "err":
            continue
        if n:
            k.update(viewers=n, seen=now, miss=0)
            out.append({x: k[x] for x in k if x not in ("seen", "miss")})
        else:
            k["miss"] += 1
    if ask and errs > len(ask) // 2:          # YouTube refusing: rest like the searches do
        _SWEEP["yt_cool"] = time.time() + 300
    _SWEEP["stats"][f"youtube known:{game}"] = (now, len(known), len(out))
    return out


def platform_india(p: str, errors: dict) -> list:
    """Indian live streams on Kick or Twitch: the India languages, plus the top streams overall and in the main
    Indian categories whose language or title marks them as Indian."""
    rows, wide = [], []
    get = (lambda prm: platforms._tw_streams({"first": 100, **prm})) if p == "twitch" else _kick_live
    for lang in (SWEEP_LANGS if p == "twitch" else LANGS):
        try:
            if p == "twitch":                 # every live stream in an Indian language, not just the first 100
                after = None
                for _ in range(LANG_PAGES):
                    j = platforms._get("twitch", "https://api.twitch.tv/helix/streams",
                                       {"first": 100, "language": lang, **({"after": after} if after else {})})
                    got = [r for r in platforms._tw_rows(j) if r["viewers"] >= MIN_VIEWERS]
                    rows += got
                    after = (j.get("pagination") or {}).get("cursor")
                    if not after or len(got) < len(j.get("data") or []):
                        break
            else:
                rows += get({"language": lang})
        except Exception as e:
            errors[f"{p} language {lang}"] = str(e)[:120]
    try:
        wide += get({})
    except Exception as e:
        errors[f"{p} top streams"] = str(e)[:120]
    for name in INDIA_CATS[p] + (["Grand Theft Auto VI"] if gta6_on() else []):
        try:
            cid = _category_id(p, name)
            if cid:
                wide += get({"game_id": cid} if p == "twitch" else {"category_id": cid})
        except Exception as e:
            errors[f"{p} category {name}"] = str(e)[:120]
    return [r for r in rows + wide if indian(r)]

# (game, words in a platform category or a stream title). Order matters: the first match wins.
GAMES = [
    ("PUBG: Battlegrounds", ["pubg: battlegrounds", "pubg pc", "pubg battlegrounds", "pubg steam", "playerunknown"]),
    ("BGMI", ["bgmi", "battlegrounds mobile india", "bmps", "bgis", "bmsd", "bmic", "bmoc"]),
    ("PUBG Mobile", ["pubg mobile", "pmgc", "pmwi", "pmsl", "pmpl", "pmrc", "battlegrounds mobile"]),
    # a bare "PUBG" (no "mobile", no "BGMI") is the PC game: CarryMinati's "PUBG ME DIWALI CELEBRATION" is
    # PLAYERUNKNOWN'S BATTLEGROUNDS on PC, and BGMI streamers write BGMI
    ("PUBG: Battlegrounds", ["pubg", "pubg india cup", " pic 2026", "|pic 2026", "pic26"]),
    ("Mobile Legends", ["mobile legends", "mlbb", "mpl ", "msc "]),
    ("Rocket League", ["rocket league", "rlcs"]),
    ("Overwatch 2", ["overwatch", "owcs"]),
    ("Free Fire", ["free fire", "freefire", "ff max", "garena"]),
    ("GTA 6", ["gta 6", "gta6", "gta vi ", "gta vi:", "gta vi|", "gta vi!", "gta vi,", "gta vi.", "gta vi-", "gta vi)",
               "#gtavi ", "grand theft auto vi", "grand theft auto 6"]),  # before GTA V
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
    ("Chess", ["chess"]),
    ("Among Us", ["among us"]),
    ("Cricket", ["ipl", "live cricket", "cricket live", "ind vs", "india vs", "t20", " odi ", "test match", "real cricket",
                 "cricket 24", "cricket 22", "world cricket championship", "wcc3", "cricket"]),   # always Sports (owner, 8 Nov)
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
    (r"\bpmgc\b|pubg mobile global championship|\bgc (league|gauntlet)\b|\b20\d\d gc (league|gauntlet|group|last chance|grand finals?)\b", "PMGC", None), (r"\bpmwi\b", "PMWI", None),
    (r"\bpmsl\b", "PMSL", None), (r"\bpmpl\b", "PMPL", None), (r"\bpmrc\b", "PMRC", None),
    (r"\bbgis\b", "BGIS", None), (r"\bbmps\b", "BMPS", None), (r"\bbmsd\b", "BMSD", None), (r"\bbmic\b", "BMIC", None),
    (r"\bbmoc\b", "BMOC", None), (r"\bffws\b|free fire world series", "FFWS", None), (r"\bffic\b", "FFIC", None),
    (r"\bmpl\b", "MPL", None), (r"\bmsc\b", "MSC", None), (r"\bm[5-9] world championship", "MLBB M-Series", None),
    (r"\brlcs\b", "RLCS", None), (r"\bcdl\b|call of duty league", "CDL", None), (r"\bowcs\b", "OWCS", None),
    (r"\balgs\b", "ALGS", None), (r"\bfncs\b", "FNCS", None), (r"\bdreamhack\b", "DreamHack", None),
    (r"\bcegc\b", "CEGC", None)]    # organisers (Sky Esports, Upthrust Esports) are not tournaments (owner, 26 Nov)
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


_LPM = {"ts": -1, "m": [], "games": set()}


def _norm(t: str) -> str:
    return " " + re.sub(r"[^0-9a-z]+", " ", (t or "").lower()).strip() + " "


def _lp_matchers():
    """Liquipedia's current tournaments as (tournament, [(phrase, strength)]): its name, its name without the year,
    its series' full name, and its short tag (FFWS, BGIS ...)."""
    from tracker import liquipedia
    act = liquipedia.active()
    if _LPM["ts"] == liquipedia._CACHE["ts"]:
        return _LPM["m"]
    m = []
    for t in act:
        ph = []
        nm = _norm(t["name"])
        noyear = re.sub(r" (19|20)\d\d ", " ", nm)
        for p_, w in ((nm, 4), (noyear, 3), (_norm(t["series"]), 3), (_norm(t["full"]), 4)):
            if len(p_.strip()) >= 6 and (p_, w) not in ph:
                ph.append((p_, w))
        tag = t["name"].split()[0] if t["name"].split() else ""
        if re.fullmatch(r"[A-Z0-9]{3,8}", tag) and not tag.isdigit():
            ph.append((_norm(tag), 1))
        m.append((t, ph, set(nm.split()) - {"2025", "2026", "2027"}))
    _LPM.update(ts=liquipedia._CACHE["ts"], m=m, games={liquipedia.WIKIS[w][0] for w in liquipedia.WIKIS} | {"BGMI"})
    _tour_cached.cache_clear()
    return m


_LP_GENERIC = {"major", "minor", "finals", "final", "global", "season", "split", "stage", "cup", "league", "series",
               "championship", "championships", "open", "masters", "s1", "s2", "s3", "s4", "qualifier", "qualifiers",
               "playoffs", "group", "world", "pro", "the", "of", "and", "spring", "summer", "fall", "winter", "week",
               "day", "phase", "showdown", "invitational", "challenge", "esports", "tournament", "grand"}


def _lp_match(title: str, game: str):
    from tracker import liquipedia
    nt = _norm(title)
    best, bs = None, 0
    for t, ph, toks in _lp_matchers():
        if not liquipedia.game_ok(t, game):
            continue
        w = max((w for p_, w in ph if p_ in nt), default=0)
        if not w and game and game != "Other":      # co-streams name it loosely ("SEMI FINAL MAJOR OSAKA"): two of
            hit = {k for k in toks if f" {k} " in nt}     # its words, one of them its own (not "major", "finals" ...)
            if len(hit) >= 2 and hit - _LP_GENERIC:
                w = 2
        if not w:
            continue
        if w == 1 and (not game or game == "Other") and len(next(p_ for p_, ww in ph if ww == 1).strip()) < 4:
            continue                       # a three-letter tag alone, with no game to confirm it, is too weak
        score = w * 10 + sum(1 for k in toks if f" {k} " in nt) + (1 if t["status"] == "ongoing" else 0)
        if score > bs:
            best, bs = t, score
    return best


def _canon(name: str, title: str = "", game: str = "") -> str:
    """A known league name ('FFWS', 'CEGC', 'LoL Worlds', 'VCT') is the same tournament as the edition on now
    ('FFWS Global Finals 2026', 'CEGC 2026', 'Worlds 2026'): use that one, so one event never shows twice. When
    several editions are on (MPL Indonesia, MPL Philippines ...), the one whose words the title shares most wins;
    if none stands out, the league name stays."""
    from tracker import liquipedia
    rx = next((r for r, n, _ in _T_RX if n == name), None)
    if rx is None:
        return name
    cands = [t for t in liquipedia.active() if rx.search(t["name"] + " " + t["full"]) and liquipedia.game_ok(t, game)]
    if not cands:                        # just finished (replays, recap streams): the edition that ended in the last week
        d7 = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
        cands = [t for t in liquipedia.tours() if t["status"] == "completed" and (t.get("end") or "") >= d7
                 and rx.search(t["name"] + " " + t["full"]) and liquipedia.game_ok(t, game)]
    if not cands:
        return name
    if len(cands) == 1:
        return cands[0]["name"]
    nt = _norm(title)
    sc = sorted(((sum(1 for k in set(_norm(t["name"]).split()) - _LP_GENERIC if f" {k} " in nt), t) for t in cands),
                key=lambda x: -x[0])
    return sc[0][1]["name"] if sc[0][0] > 1 and sc[0][0] > sc[1][0] else name


def _start_ts(name: str):
    """00:00 IST on the Liquipedia start date of an edition, or None."""
    from tracker import liquipedia
    t = next((t for t in liquipedia.tours() if t["name"] == name and t.get("start")), None)
    if not t:
        return None
    try:
        d = datetime.fromisoformat(t["start"]).date()
    except ValueError:
        return None
    return int(datetime.combine(d, datetime.min.time(), events.REPORT_TZ).timestamp())


def _rehome(c, src: str, dst: str, lo: int, hi: int) -> bool:
    """Move a tournament's readings with lo <= ts < hi (channel days likewise) from src to dst, both regions;
    hours watched move in proportion to the viewers moved; peaks and spans are recomputed."""
    any_ = False
    for region in ("global", "in"):
        rg = f"tour:{region}"
        tot, part = c.execute("SELECT SUM(viewers), SUM(CASE WHEN ts>=? AND ts<? THEN viewers ELSE 0 END) FROM sc_reg "
                              "WHERE region=? AND game=?", (lo, hi, rg, src)).fetchone()
        if not part:
            continue
        any_ = True
        c.execute("""INSERT INTO sc_reg (ts, region, game, viewers, streams)
                     SELECT ts, region, ?, viewers, streams FROM sc_reg WHERE region=? AND game=? AND ts>=? AND ts<? AND true
                     ON CONFLICT(region, game, ts) DO UPDATE SET viewers=sc_reg.viewers+excluded.viewers,
                     streams=sc_reg.streams+excluded.streams""", (dst, rg, src, lo, hi))
        c.execute("DELETE FROM sc_reg WHERE region=? AND game=? AND ts>=? AND ts<?", (rg, src, lo, hi))
        hw = {n: (r[0] if r else 0) or 0 for n in (src, dst)
              for r in [c.execute("SELECT hw FROM sc_tour WHERE region=? AND tour=?", (region, n)).fetchone()]}
        mv = hw[src] * part / tot if tot else 0
        for n, h in ((src, hw[src] - mv), (dst, hw[dst] + mv)):
            c.execute("DELETE FROM sc_tour WHERE region=? AND tour=?", (region, n))
            pk = c.execute("SELECT ts, viewers FROM sc_reg WHERE region=? AND game=? ORDER BY viewers DESC LIMIT 1", (rg, n)).fetchone()
            span = c.execute("SELECT MIN(ts), MAX(ts) FROM sc_reg WHERE region=? AND game=?", (rg, n)).fetchone()
            if pk:
                c.execute("INSERT INTO sc_tour VALUES (?,?,?,?,?,?,?)", (n, region, pk[1], pk[0], span[0], span[1], max(0, h)))
    d_lo = datetime.fromtimestamp(lo, events.REPORT_TZ).strftime("%Y-%m-%d") if lo > 0 else "0000"
    d_hi = datetime.fromtimestamp(hi, events.REPORT_TZ).strftime("%Y-%m-%d") if hi < 4e9 else "9999"
    c.execute("""INSERT INTO sc_tour_ch (tour, sid, day, peak, peak_at, mins, hw, india)
                 SELECT ?, sid, day, peak, peak_at, mins, hw, india FROM sc_tour_ch WHERE tour=? AND day>=? AND day<? AND true
                 ON CONFLICT(tour, sid, day) DO UPDATE SET peak=MAX(sc_tour_ch.peak, excluded.peak),
                 mins=sc_tour_ch.mins+excluded.mins, hw=sc_tour_ch.hw+excluded.hw""", (dst, src, d_lo, d_hi))
    c.execute("DELETE FROM sc_tour_ch WHERE tour=? AND day>=? AND day<?", (src, d_lo, d_hi))
    return any_


def merge_aliases() -> int:
    """Readings already filed under a league name that is really the edition on now ('FFWS' -> 'FFWS Global Finals
    2026', 'CEGC' -> 'CEGC 2026') are moved onto that edition, from its Liquipedia start date on: per-scan totals
    added together, channel peaks merged, all-time numbers recomputed. Readings from before the start stay with the
    league (26 Nov: a month of 'PMGC' mentions, BMIC's PMGC slots and qualifiers, had moved onto PMGC 2026 and gave
    it a 26K peak before it began); ones already moved go back. Safe to run again (it is, after every refresh)."""
    with store.reading():
        names = [n for (n,) in _db().execute("SELECT DISTINCT tour FROM sc_tour")]
    moved = 0
    for old in names:
        new = _canon(old, "", TOUR_GAME.get(old, ""))
        if new != old:
            lo = _start_ts(new) or 0
            with store._lock:
                c = _db()
                if _rehome(c, old, new, lo, 1 << 40):
                    moved += 1
                    print(f"Tournament {old!r} merged into {new!r}")
                c.commit()
    for ed in names:                          # an edition holding readings from before it began: back to its league
        league = next((n for rx, n, _ in _T_RX if rx.search(ed)), None)
        lo = _start_ts(ed)
        if not league or league == ed or not lo:
            continue
        with store._lock:
            c = _db()
            if _rehome(c, ed, league, 0, lo):
                print(f"Tournament {ed!r}: readings before its start moved back to {league!r}")
            c.commit()
    return moved


def tournament_info(name: str):
    """The Liquipedia entry behind a tournament name, if any."""
    from tracker import liquipedia
    for t in liquipedia.active() + liquipedia.tours():
        if t["name"] == name:
            return t
    return None


def esports_game(game: str) -> bool:
    _lp_matchers()
    return bool(game) and (game in _LPM["games"] or game in TOUR_GAME.values())


def tournament(title: str, game: str = ""):
    """The tournament a stream is broadcasting or co-streaming, or None. Liquipedia's current tournaments first (so
    every channel showing it, in any language, adds up to one number), then known league names, then, for esports
    games only, '<game> tournaments' for other competitive broadcasts."""
    _lp_matchers()
    return _tour_cached(title or "", game or "", _LPM["ts"])


@functools.lru_cache(maxsize=50000)
def _tour_cached(title: str, game: str, _ts):
    t = title
    if _T_NOT.search(t):
        return None
    lp = _lp_match(t, game)
    if lp:
        return lp["name"]
    low = t.lower()
    for rx, name, g in _T_RX:
        if rx.search(t) and (not g or g == game or g.lower() in low or g == "League of Legends" and re.search(r"\blol\b", low)):
            return _canon(name, t, game or TOUR_GAME.get(name, ""))
    if _T_GENERIC.search(t) and _T_MATCH.search(t) and esports_game(game):
        return f"{game} tournaments"
    return None


SEEDS = {"kick": ["skyesports", "cegc"], "twitch": [],
         "youtube": ["@SoulAman", "@DynamoGaming", "@TheBixiOP", "@ZGODGAMING", "@NEYOOGAMINGYT", "@MizoPlays",
                     "@MrSpike", "@LoLzZzGaming", "@SHARKSHE", "@MafiaNinja", "@ImRuthlessceopubg", "@RakaZoneGaming",
                     "@AnshYT", "@Casetoolive", "@sheekgaming", "@IPREEET.69", "@shreemanlegendliveofficial",
                     "@MortaLyt", "@VAADHIYAAR", "@soulregaltos9810", "@SnaxGaming", "@sriop-sr70", "@NEONXPAWANOP",
                     "@LadyPredatorGaming"]}

_KSEED = set()        # Kick seed slugs (always Indian), refreshed every scan
_SEEDED = set()       # YouTube channels found through hand-added @handles: always Indian
_LIVE = {}            # sid -> {"sid","platform","name","url","logo","game","title","streams": {vid: viewers},"seen","errs"}
_STATE = {"last": 0.0, "yt": 0.0, "seeds": 0.0, "errors": {}, "running": False}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=8)
_YFPOOL = ThreadPoolExecutor(max_workers=int(os.getenv("SCENE_YT_POOL", "16")))  # YouTube's 2-second counts (own threads: never wait behind a scan)
_YPOOL = ThreadPoolExecutor(max_workers=6)   # sweep searches on YouTube
CYCLE = {}           # the scan loop: when the current/last scan started, how long it took (health page)
MOMENTS_ON = os.getenv("MOMENTS", "0") == "1"
_SCANMEM = {"ts": 0, "rows": None}
_FASTAT = [0.0]      # when the last 2-second round started        # the latest scan, as stored (pages read it from here, not the database)
SAMPLE_MIN = int(os.getenv("SCENE_SAMPLE_MIN", "10"))   # swept streams below this aren't written to the per-scan table
_SPOOL = ThreadPoolExecutor(max_workers=4)   # the launch-game sweep (its own threads, so scans don't wait)



_SCHEMA_OK = {}


def _db():
    """The connection to use: tables are created (and migrations run) once per database file, not on every call;
    inside store.reading() this is the thread's own read-only connection."""
    if _SCHEMA_OK.get(store.DB_PATH):
        return store.conn()
    with store._lock:
        _schema(store.main())
        _SCHEMA_OK[store.DB_PATH] = True
    return store.conn()


def _schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS sc_channels (sid TEXT PRIMARY KEY, platform TEXT, name TEXT, url TEXT, logo TEXT,
        first_seen REAL, last_live REAL, title TEXT, game TEXT);
    CREATE TABLE IF NOT EXISTS sc_samples (ts INTEGER, sid TEXT, viewers INTEGER, game TEXT);
    CREATE TABLE IF NOT EXISTS yt_card (vid TEXT PRIMARY KEY, game TEXT, ts INTEGER);
    CREATE TABLE IF NOT EXISTS sc_vstreams (vid TEXT PRIMARY KEY, sid TEXT, first_ts INTEGER, last_ts INTEGER,
        peak INTEGER, peak_at INTEGER, hw REAL, n INTEGER);
    CREATE INDEX IF NOT EXISTS sc_vstreams_sid ON sc_vstreams(sid, first_ts);
    CREATE INDEX IF NOT EXISTS sc_samples_ix ON sc_samples(ts);
    CREATE TABLE IF NOT EXISTS sc_reg_day (region TEXT, game TEXT, day TEXT, peak INTEGER, PRIMARY KEY (region, game, day));
    CREATE TABLE IF NOT EXISTS sc_tour_ch (tour TEXT, sid TEXT, day TEXT, peak INTEGER, peak_at INTEGER, mins REAL,
        hw REAL, india INTEGER, PRIMARY KEY (tour, sid, day));
    CREATE INDEX IF NOT EXISTS sc_tour_ch_day ON sc_tour_ch(day);
    CREATE TABLE IF NOT EXISTS sc_tour (tour TEXT, region TEXT, peak INTEGER, peak_at INTEGER, first_ts INTEGER,
        last_ts INTEGER, hw REAL, PRIMARY KEY (tour, region));
    CREATE TABLE IF NOT EXISTS sc_daily (day TEXT, sid TEXT, game TEXT, peak INTEGER, peak_at INTEGER, mins REAL,
        hw REAL, PRIMARY KEY (day, sid, game));
    CREATE INDEX IF NOT EXISTS sc_daily_game ON sc_daily(game, day);
    CREATE INDEX IF NOT EXISTS sc_daily_sid ON sc_daily(sid, day);
    CREATE INDEX IF NOT EXISTS sc_samples_sid ON sc_samples(sid, ts);
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
    if not _COLS and not store.kv_get("scene_mig_pubgpc"):   # bare "PUBG" titles were filed as BGMI: move them
        for sid in PUBG_PC_FIX:
            try:
                _move_game(c, sid, "BGMI", "PUBG: Battlegrounds")
            except Exception as e:
                print(f"PUBG fix {sid}: {e}")
        c.commit()
        store.kv_set("scene_mig_pubgpc", True)
    if not _COLS and not store.kv_get("scene_mig_cricket"):   # one Cricket category, under Sports
        old = "('Cricket games','Cricket (live)')"
        for t, key in (("sc_cat", "ts"), ("sc_reg", "ts, region")):
            try:
                c.execute(f"""INSERT INTO {t} ({key}, game, viewers, streams)
                              SELECT {key}, 'Cricket', SUM(viewers), SUM(streams) FROM {t} WHERE game IN {old} GROUP BY {key}
                              ON CONFLICT DO UPDATE SET viewers=viewers+excluded.viewers, streams=streams+excluded.streams""")
                c.execute(f"DELETE FROM {t} WHERE game IN {old}")
            except Exception as e:
                print(f"Cricket merge {t}: {e}")
        for t in ("sc_samples", "sc_daily", "sc_channels"):
            try:
                c.execute(f"UPDATE OR IGNORE {t} SET game='Cricket' WHERE game IN {old}")
                c.execute(f"DELETE FROM {t} WHERE game IN {old}") if t == "sc_daily" else None
            except Exception as e:
                print(f"Cricket merge {t}: {e}")
        c.commit()
        store.kv_set("scene_mig_cricket", True)
    if not _COLS:
        have = {r[1] for r in c.execute("PRAGMA table_info(sc_channels)")}
        for col, typ in (("country", "TEXT"), ("india", "INTEGER"), ("language", "TEXT"), ("tracked", "INTEGER"), ("topic", "TEXT"), ("ytcat", "TEXT"), ("tags", "TEXT")):
            if col not in have:
                c.execute(f"ALTER TABLE sc_channels ADD COLUMN {col} {typ}")
        c.commit()
        _COLS.append(1)
    return c


_COLS = []
PUBG_PC_FIX = ["yt:UC0IWRLai-BAwci_e9MylNGw"]      # CarryisLive: PUBG PC streams that were counted as BGMI


def _move_game(c, sid: str, old: str, new: str):
    """Re-file one channel's readings from game `old` to `new`: its per-scan readings, daily rows, and the
    category totals those readings were added to (India totals and worldwide per-game totals)."""
    for ts, v in c.execute("SELECT ts, viewers FROM sc_samples WHERE sid=? AND game=?", (sid, old)).fetchall():
        for t, key, args in (("sc_cat", "ts", (ts,)), ("sc_reg", "ts, region", (ts, "global"))):
            where = "ts=?" + (" AND region=?" if t == "sc_reg" else "")
            if not c.execute(f"SELECT 1 FROM {t} WHERE {where} AND game=?", (*args, old)).fetchone():
                continue                    # not counted there (e.g. a channel outside India in sc_cat)
            c.execute(f"UPDATE {t} SET viewers=MAX(0, viewers-?), streams=MAX(0, streams-1) WHERE {where} AND game=?",
                      (v, *args, old))
            c.execute(f"""INSERT INTO {t} ({key}, game, viewers, streams) VALUES ({','.join('?' * len(args))}, ?, ?, 1)
                          ON CONFLICT DO UPDATE SET viewers=viewers+excluded.viewers, streams=streams+1""", (*args, new, v))
    c.execute("UPDATE sc_samples SET game=? WHERE sid=? AND game=?", (new, sid, old))
    for day, peak, pat, mins, hw in c.execute("SELECT day, peak, peak_at, mins, hw FROM sc_daily WHERE sid=? AND game=?",
                                              (sid, old)).fetchall():
        c.execute("""INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                     peak_at=CASE WHEN excluded.peak > sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                     peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                  (day, sid, new, peak, pat, mins, hw))
    c.execute("DELETE FROM sc_daily WHERE sid=? AND game=?", (sid, old))
    c.execute("UPDATE sc_channels SET game=? WHERE sid=? AND game=?", (new, sid, old))


@functools.lru_cache(maxsize=100000)
def slug(game: str) -> str:
    """URL name of a category: 'Free Fire' -> 'free-fire'."""
    return re.sub(r"[^a-z0-9]+", "-", (game or "").lower()).strip("-") or "other"


ALL = "__all__"          # the India-wide total in sc_cat
NON_GAMING = {"News", "Devotional", "Music", "Podcast / Talk", "Just Chatting", "IRL", "Cricket", "Other"}
CRICKET_OLD = ("Cricket games", "Cricket (live)")
# Top-level sections shown in the site's menu. A stream's section comes from its tournament (Esports) or its game/category.
SECTIONS = [("gaming", "Gaming"), ("esports", "Esports"), ("irl", "IRL"), ("just-chatting", "Just Chatting"),
            ("news", "News"), ("music", "Music"), ("sports", "Sports"), ("devotional", "Devotional"),
            ("podcasts", "Podcasts & Talk"), ("other", "Other")]
SECTION_NAMES = dict(SECTIONS)
_SEC_FIXED = {"Just Chatting": "just-chatting", "IRL": "irl", "News": "news", "Music": "music",
              "Cricket": "sports", "Devotional": "devotional", "Podcast / Talk": "podcasts", "Other": "other",
              # YouTube's own categories, for streams that name no game (they were all "Other" before, 25 Nov)
              "Sports": "sports", "Entertainment": "other", "People & Blogs": "irl", "Comedy": "other", "Education": "other",
              "Film & Animation": "other", "Science & Technology": "other", "Howto & Style": "irl", "Autos & Vehicles": "other",
              "Pets & Animals": "irl", "Nonprofits & Activism": "other", "Travel & Events": "irl"}
YT_CAT_GAME = {"News & Politics": "News", "Gaming": ""}     # YouTube category -> the name filed; "" = stays Other
_YTC = {"at": 0, "m": {}, "busy": False}


def _ytcat_load():
    try:
        with store.reading():
            m = {sid: c for sid, c in _db().execute(
                "SELECT sid, COALESCE(NULLIF(ytcat,''), topic) FROM sc_channels WHERE platform='youtube' "
                "AND COALESCE(NULLIF(ytcat,''), topic) IS NOT NULL AND COALESCE(NULLIF(ytcat,''), topic) NOT IN ('', 'Other')")}
        _YTC.update(at=time.time(), m=m)
    except Exception as e:
        print(f"YouTube categories: {str(e)[:100]}")
    finally:
        _YTC["busy"] = False


def yt_category_game(sid: str) -> str:
    """What to file a YouTube stream under when its title and game card name no game: the channel's YouTube category
    ('Sports', 'Entertainment', 'News' ...), not 'Other'."""
    if time.time() - _YTC["at"] > 1800 and not _YTC["busy"]:
        _YTC["busy"] = True
        threading.Thread(target=_ytcat_load, daemon=True).start()
    c = _YTC["m"].get(sid) or ""
    return YT_CAT_GAME.get(c, c)
_SEC_WORDS = [("irl", ("irl", "travel", "outdoor", "food", "cooking", "vlog")), ("sports", ("sport", "football", "cricket",
              "basketball", "wrestling", "racing")), ("music", ("music", "dj", "concert")), ("podcasts", ("podcast", "talk")),
              ("news", ("news", "politic")), ("other", ("slots", "casino", "pools", "asmr", "art", "special events"))]


@functools.lru_cache(maxsize=100000)
def section_of(game: str, tour=None) -> str:
    if game == "Cricket" or "cricket" in (game or "").lower():
        return "sports"                  # never Gaming or Esports, even inside a tournament
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
_NON_GAMING_WORDS = ("irl", "chatting", "music", "talk", "sports", "cricket", "slots", "casino", "pools", "asmr", "travel",
                     "podcast", "news", "special events", "art", "food", "politics")


# Cover art for each game: the name it has on Twitch (tried in order), else Kick's category image.
# Cover art, exact names only. Each game is looked up by the name it has on Twitch, then on Kick; a name that does
# not match exactly gives no art (an initials tile) rather than another game's cover. BGMI, PUBG: Battlegrounds and
# PUBG Mobile are three different games with three different covers. A file in static/gameart/<slug>.webp|png|jpg
# (slug: 'bgmi', 'free-fire' ...) overrides everything.
TWITCH_NAMES = {"Overwatch 2": ["Overwatch 2", "Overwatch"], "Rainbow Six Siege": ["Tom Clancy's Rainbow Six Siege", "Rainbow Six Siege X"],
                "BGMI": ["Battlegrounds Mobile India"], "PUBG: Battlegrounds": ["PUBG: BATTLEGROUNDS"],
                "PUBG Mobile": ["PUBG MOBILE"], "Free Fire": ["Garena Free Fire", "Free Fire"],
                "GTA 6": ["Grand Theft Auto VI"], "GTA V": ["Grand Theft Auto V"], "Valorant": ["VALORANT"], "COD Mobile": ["Call of Duty: Mobile"],
                "Call of Duty: Warzone": ["Call of Duty: Warzone"], "Call of Duty: Black Ops 7": ["Call of Duty: Black Ops 7"],
                "Call of Duty: Black Ops 6": ["Call of Duty: Black Ops 6"], "Counter-Strike 2": ["Counter-Strike"],
                "Pokemon Unite": ["Pokémon UNITE"], "Mobile Legends": ["Mobile Legends: Bang Bang"],
                "Indus": ["Indus Battle Royale"], "IRL": ["IRL"], "Just Chatting": ["Just Chatting"], "Music": ["Music"]}
KICK_NAMES = {"BGMI": ["Battlegrounds Mobile India"], "PUBG Mobile": ["PUBG Mobile"], "Free Fire": ["Free Fire", "Garena Free Fire"],
              "GTA 6": ["Grand Theft Auto VI"], "GTA V": ["Grand Theft Auto V (GTA)", "Grand Theft Auto V"], "Counter-Strike 2": ["Counter-Strike 2"],
              "Indus": ["Indus Battle Royale", "Indus"], "PUBG: Battlegrounds": ["PUBG: Battlegrounds", "PUBG"]}
NO_ART = {"Call of Duty", "EA Sports FC", "Other", "Other tournaments"}   # several games share these names
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


_ARTC = {}
_ART_TRY = {}
ART_AS = {"Call of Duty": "Call of Duty: Black Ops 7", "EA Sports FC": "EA Sports FC 26", "Fighting games": "Street Fighter 6"}


def tour_art(game: str) -> str:
    """Cover for a tournament's game (a series that spans games uses its current one)."""
    return cat_art(ART_AS.get(game, game)) if game else ""


def cat_art(game: str) -> str:
    """Cover art URL for a game or platform category, remembered for 10 minutes (pages ask for it once per stream)."""
    hit = _ARTC.get(game)
    if hit and time.time() - hit[1] < 600:
        return hit[0]
    v = _cat_art(game)
    if len(_ARTC) > 20000:
        _ARTC.clear()
    _ARTC[game] = (v, time.time() if v and not v.startswith("/caticon/") else time.time() - 540)   # no art yet: ask again in a minute
    return v


def _cat_art(game: str) -> str:
    """Cover art URL for a game or platform category (cached; looked up in the background the first time)."""
    from tracker import caticon
    fb = caticon.url(section_of(game)) if game else ""      # icon tile, never initials
    if not game or game in NO_ART or game in NON_GAMING - {"Just Chatting", "IRL", "Music"}:
        return fb
    local = _local_art(game)
    if local:
        return local
    k = f"cat_art2:{game}"
    v = store.kv_get(k)
    retry = v == "" and time.time() - (_ART_TRY.get(game) or 0) > 86400   # found nothing before: ask again daily
    if (v is None or retry) and game not in _ART_BUSY:
        _ART_BUSY.add(game)
        _ART_TRY[game] = time.time()

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
    return v or fb


def is_gaming(game: str) -> bool:
    """Games vs everything else (news, music, devotional, chatting ...). Unknown Kick/Twitch categories count as
    games unless their name says otherwise."""
    if game in NON_GAMING:
        return False
    if any(g == game for g, _ in GAMES):
        return True
    return not any(w in (game or "").lower() for w in _NON_GAMING_WORDS)


_G6RX = re.compile(r"\bgta ?(vi|6)\b|grand theft auto (vi|6)\b")
# Titles that only talk about GTA 6 while playing something else (19 Nov: Indian channels in the GTA 6 list that never
# played it). Only for titles: a platform category of GTA VI always counts.
_G6NOT = re.compile(r"\b(waiting|wait for|countdown|trailer|react|reaction|reacting|leaks?|news|rumou?rs?|"
                    r"days? (left|to go)|hours? (left|to go)|release date|price|preload|pre-?order|predictions?)\b")
# Coverage, not play: these always win, even with "live" or "launch" in the title (19 Nov: news channels' "GTA 6
# launch LIVE" bulletins were counted as GTA 6 streams).
_G6NEWS = re.compile(r"\b(news|bulletin|debate|live updates?|trailer|reaction|react|reacts|reacting|leaks?|explained|"
                     r"price in india|launch event|store|stores|queue|crowd)\b")
_NEWSW = ("khabar", "samachar", "headlines", "breaking", "aaj tak", "ndtv", "republic", "tv9", "abp ", "zee ", "india tv")
# Words that mean the stream is playing it: they win over the words above ("until", "before", "giveaway" were removed
# on 19 Nov: "Playing GTA 6 Until i Finish It" was filed as Other and Casetoo dropped out of the GTA 6 lists).
_G6PLAY = re.compile(r"\b(gameplay|playing|plays|played|walkthrough|part ?\d+|episode|ep ?\d+|epi ?\d+|mission|marathon|"
                     r"story ?mode|free ?roam|first (look|day|hour|time|stream|live)|is here|launch|day ?\d+|finish|"
                     r"100%|speedrun|online|exploring|exploration|vice city)\b")


def classify(category: str, title: str) -> str:
    cat = (category or "").lower()
    if cat:
        for g, words in GAMES:
            if any(w in cat for w in words):
                return g if g not in _hidden() else "Other"      # GTA VI category before release: reaction streams
        return category.strip()[:40]        # the platform's own category name
    t = f" {(title or '').lower()} "
    for g, words in GAMES:
        if g in _hidden():
            continue                        # "GTA 6 soon" titles before release are GTA V
        if g == "GTA 6":                    # "#gta6" tags on a GTA V short are not GTA 6
            t6 = re.sub(r"#\S+", " ", t)
            if not (any(w in t6 for w in words) or _G6RX.search(t6)):
                continue
        if any(w in t for w in words) or (g == "GTA 6" and _G6RX.search(t)):   # "GTA VI🌴": an emoji right after
            if g == "GTA 6" and (_G6NEWS.search(t) or any(w in t for w in _NEWSW)):
                return "News" if (re.search(r"\b(news|bulletin|debate|live updates?)\b", t) or any(w in t for w in _NEWSW)) \
                    else "Other"            # news / reaction / trailer coverage of GTA 6: never GTA 6 (owner, 19 Nov)
            if g == "GTA 6" and _G6NOT.search(t) and not _G6PLAY.search(t):   # talking about it, not playing it
                return "GTA V" if re.search(r"\bgta ?(v|5)\b|\brp\b|roleplay|soul ?city", t) else "Other"
            return g
    return "Other"


ALWAYS = {"kick": ["skyesports", "cegc", "rntxrohit", "jonathangaming", "kaashplays", "regaltos", "neyoo_gaming", "rakazone", "tbone_gaming", "eaglegaming"]}   # Indian Kick channels: tracked (and Indian) even if the seed list was edited


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


# Removed by the owner from every list (not streamers / scams), matched by name on any platform. 19 Nov: Dino Prasad.
NAME_BLOCK = {"dinoprasad",
              # Twitch channels checked on twitch.tv 24 Nov: live viewers far above their followers (viewbots), or
              # banned: sazof36 (634 followers, '17,184' peak), pepewwwpew (124, avg 454), crazystuff21 (410, avg 438),
              # kendra_shepard992 (63, peak 251), biggbosstelugulives (337, peak 996), sane1oo (971, avg 467),
              # venomstechgaming (987, avg 288), rexar_live (banned / deleted)
              "sazof36", "pepewwwpew", "crazystuff21", "kendrashepard992", "biggbosstelugulives", "sane1oo",
              "venomstechgaming", "rexarlive"}


def name_blocked(name) -> bool:
    from tracker import overrides
    k = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return k in NAME_BLOCK or k in overrides.blocked_names()      # + the daily review's blocks (overrides.json)


# Channels the owner checked did not play a game, kept out of that game's lists only (19 Nov: Willy Gaming, GTA 6).
GAME_NOT = {"GTA 6": {"willygaming", "vizagpropertyfinder", "arpitachoudhury", "omstudiocreation", "ajaykhutail",
                      "crushziytgaming", "asaddangerlive"}}   # owner, 19 Nov: not GTA 6 streamers (copied titles, fake "launch day live")


# News / TV channel names (19 Nov: DD News and Bangla Tribune ran GTA 6 launch bulletins whose titles had no news word)
_NEWSNAME = re.compile(r"\b(news|tribune|times|samachar|khabar|doordarshan|dd \w+|aaj tak|ndtv|tv ?9|zee|abp|republic (bharat|tv|world|bangla)|somoy|jamuna|ekattor|channel ?24|ntv|rtv|atn bangla|dbc|"
                       r"express|herald|gazette|chronicle|bbc|cnn|reuters|al jazeera|sky news|fox|cnbc|wion|india tv|"
                       r"news ?18|live ?news|24x7|24 ?news|television|broadcast|media|patrika|jagran|bhaskar|prothom alo)\b|"
                       r"সংবাদ|খবর|সময়|টিভি|समाचार|ख़बर|खबर|न्यूज़|न्यूज|టీవీ|வார்த்தை|செய்தி", re.I)


def news_name(name) -> bool:
    return bool(name and _NEWSNAME.search(name))


def not_in_game(name, game, sid: str = "") -> bool:
    if not game:
        return False
    if news_name(name) and game not in ("News", "Other"):
        return True                         # a news channel is never in a game's lists
    if game == "GTA 6" and sid and (sid in _g6_not() or sid in _news_sids()):
        return True
    return re.sub(r"[^a-z0-9]", "", (name or "").lower()) in GAME_NOT.get(game, ())


_G6N = {"at": 0, "v": set()}
_NS = {"at": 0, "v": set()}


def _news_sids() -> set:
    """Channels that run news or devotional streams (any such day since 1 Nov): never in a game's lists. Read in the
    background through the (game, day) index; a request never waits for it (19 Nov: an inline full read of sc_daily
    made the GTA 6 rankings time out)."""
    if time.time() - _NS["at"] > 600 and not _NS.get("busy"):
        _NS["busy"] = True
        threading.Thread(target=_news_read, daemon=True).start()
    return _NS["v"]


def _news_read():
    try:
        with store.reading():
            _NS["v"] = {r[0] for r in store.conn().execute(
                "SELECT DISTINCT sid FROM sc_daily WHERE game IN ('News','Devotional') AND day>='2026-11-01'")}
        _NS["at"] = time.time()
    except Exception as e:
        print(f"News channels: {str(e)[:80]}")
    finally:
        _NS["busy"] = False


def _g6_not() -> set:
    if time.time() - _G6N["at"] > 60:
        _G6N["v"] = {s for s, x in (store.kv_get("g6_check3") or {}).items() if not x[0]}
        _G6N["at"] = time.time()
    return _G6N["v"]


_BOXART = re.compile(r'"RICH_METADATA_RENDERER_STYLE_BOX_ART"')
_SIMPLE = re.compile(r'"title":\{"simpleText":"((?:[^"\\]|\\.)*)"')
_MTITLE = re.compile(r'<meta name="title" content="([^"]*)"|<meta property="og:title" content="([^"]*)"|<title>([^<]*?)(?: - YouTube)?</title>')


def _yt_game(vid: str):
    """(game YouTube shows under the video or '', title) from the watch page. None if the page could not be read."""
    try:
        r = events._http.get(f"https://www.youtube.com/watch?v={vid}", timeout=10,
                             headers={"User-Agent": events._UA, "Accept-Language": "en"})
        if r.status_code != 200:
            return None
        h = r.text
    except Exception:
        return None
    if "ytInitialData" not in h:
        return None                             # consent / bot page: not a real answer
    game = ""
    m = _BOXART.search(h)
    if m:
        g = _SIMPLE.search(h, m.end(), m.end() + 4000)
        game = json.loads('"' + g.group(1) + '"') if g else ""
    t = _MTITLE.search(h)
    title = html.unescape(next((g for g in t.groups() if g), "")).strip() if t else ""
    return game, title


_YCARD = {}          # YouTube video -> the game YouTube shows under it ("" = none shown); read once per video
_YCARD_TRY = {}      # video -> when an unreadable page was last tried


def _card_load():
    """Game cards already read (kept in yt_card, so a restart doesn't read them again)."""
    if _YCARD_TRY.get("_loaded"):
        return
    _YCARD_TRY["_loaded"] = 1
    try:
        with store.reading():
            for v, g in _db().execute("SELECT vid, game FROM yt_card WHERE ts>?", (time.time() - 60 * 86400,)):
                _YCARD.setdefault(v, g or "")
    except Exception as e:
        print(f"Game cards load: {str(e)[:100]}")


def _card_get(vids, n: int = 4) -> int:
    from concurrent.futures import ThreadPoolExecutor
    _card_load()
    vids = [v for v in vids if v not in _YCARD and time.time() - _YCARD_TRY.get(v, 0) > 1800]
    if not vids:
        return 0
    with ThreadPoolExecutor(n) as ex:
        res = list(ex.map(_yt_game, vids))
    new = []
    for v, r in zip(vids, res):
        if r is None:
            _YCARD_TRY[v] = time.time()
        else:
            _YCARD[v] = r[0] or ""
            new.append((v, r[0] or "", int(time.time())))
    if new:
        with store._lock:
            c = _db()
            c.executemany("INSERT OR REPLACE INTO yt_card VALUES (?,?,?)", new)
            c.commit()
    if len(_YCARD) > 120000:
        _YCARD.clear()
        _YCARD_TRY.pop("_loaded", None)
    return len(vids)


def refile_games(days: int = 30, max_vids: int = 2500, pace=None) -> int:
    """What Indian YouTube channels really streamed, by the game YouTube shows under each stream (the streamer picks
    it), not the title's words (owner, 25 Nov: Free Fire / BGMI streamers filed as GTA after a 'GTA 6' title). A
    channel's day is moved to the card's game when every stream that day has a card and they all name one game."""
    since = time.time() - days * 86400
    with store.reading():
        rows = store.conn().execute("""SELECT v.vid, v.sid, v.first_ts, v.last_ts FROM sc_vstreams v JOIN sc_channels ch
            ON ch.sid=v.sid WHERE v.last_ts>=? AND COALESCE(ch.india,0)=1 AND v.peak>=100 ORDER BY v.peak DESC LIMIT ?""",
                                    (since, max_vids)).fetchall()
    for i in range(0, len(rows), 40):          # a few at a time, waiting while the machine is behind
        while pace and pace():
            time.sleep(30)
        _card_get([r[0] for r in rows[i:i + 40]])
    card = lambda v: classify(_YCARD[v], "") if _YCARD.get(v) else None
    day = lambda ts: datetime.fromtimestamp(ts, events.REPORT_TZ).strftime("%Y-%m-%d")
    by = {}
    for vid, sid, a, b in rows:
        for d in {day(a), day(b)}:
            by.setdefault((sid, d), []).append(vid)
    moved, todo = 0, []
    for (sid, d), vs in by.items():
        gs = {card(v) for v in vs}
        if None in gs or len(gs) != 1:
            continue                           # a stream without a card, or two games that day: left as filed
        g = gs.pop()
        if g and g != "Other":
            todo.append((sid, d, g))
    moved = _move_days(todo, pace)
    # streams that name no game: filed under the channel's YouTube category ('Sports', 'Entertainment') not 'Other'
    _ytcat_load()
    d0 = day(since)
    with store.reading():
        oth = store.conn().execute("SELECT DISTINCT sid, day FROM sc_daily WHERE game='Other' AND day>=? AND sid LIKE 'yt:%'",
                                   (d0,)).fetchall()
    todo2 = [(sid, d, yt_category_game(sid), "Other") for sid, d in oth if yt_category_game(sid)]
    moved2 = _move_days(todo2, pace)
    print(f"Game cards: {len(rows)} Indian YouTube streams of {days} days read, {moved} channel-day rows moved to their "
          f"card's game, {moved2} 'Other' rows to the channel's YouTube category")
    return moved + moved2


def _move_days(todo, pace=None) -> int:
    """[(sid, day, to_game[, from_game])]: merge that day's rows of other games (or just from_game) into to_game."""
    moved = 0
    for i in range(0, len(todo), 20):
        while pace and pace():
            time.sleep(30)
        with store._lock:
            c = store.main()
            for t in todo[i:i + 20]:
                sid, d, g = t[:3]
                other = c.execute("SELECT game, peak, peak_at, mins, hw FROM sc_daily WHERE day=? AND sid=? AND game!=?"
                                  + (" AND game=?" if len(t) > 3 else ""), (d, sid, g, *t[3:])).fetchall()
                for og, pk, pat, mn, hw in other:
                    c.execute("""INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                                 peak_at=CASE WHEN excluded.peak>sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                                 peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                              (d, sid, g, pk, pat, mn, hw))
                    c.execute("DELETE FROM sc_daily WHERE day=? AND sid=? AND game=?", (d, sid, og))
                    moved += 1
            c.commit()
    return moved


def cards_once(limit: int = 150) -> int:
    """Live YouTube streams that matter (Indian ones, or 1,000+ watching): read the game YouTube shows under each
    once, so the next scan files it by that game instead of guessing from the title (19 Nov: Red parasite's "I
    EXPLORED VICE CITY FOR THE FIRST TIME" never says GTA 6 and was filed as Other)."""
    with _lock:
        cand = sorted(((x["viewers"], v) for sid, x in _LIVE.items() if x.get("platform") == "youtube"
                       and (x.get("india") or x["viewers"] >= 1000) for v in x.get("streams", {})), reverse=True)
    return _card_get([v for _, v in cand][:limit])


def refile_cards(since: int = None, max_vids: int = 2000) -> int:
    """Past streams since GTA 6's release by Indian YouTube channels (100+ peak): read each one's game card, and where
    YouTube says Grand Theft Auto VI, move that channel's Other readings of the stream, and its Other day row when
    every stream that day is GTA VI, to GTA 6."""
    since = since or GTA6_RELEASE
    with store.reading():
        rows = store.conn().execute("""SELECT v.vid, v.sid, v.first_ts, v.last_ts FROM sc_vstreams v JOIN sc_channels ch
            ON ch.sid=v.sid WHERE v.last_ts>=? AND COALESCE(ch.india,0)=1 AND v.peak>=100 ORDER BY v.peak DESC LIMIT ?""",
                                    (since, max_vids)).fetchall()
    _card_get([r[0] for r in rows])
    g6 = lambda v: classify(_YCARD.get(v) or "", "") == "GTA 6" if _YCARD.get(v) else None
    day = lambda ts: datetime.fromtimestamp(ts, events.REPORT_TZ).strftime("%Y-%m-%d")
    by = {}
    for vid, sid, a, b in rows:
        for d in {day(a), day(b)}:
            by.setdefault((sid, d), []).append((vid, a, b))
    moved = 0
    for (sid, d), vs in by.items():
        if not any(g6(v) for v, _, _ in vs):
            continue
        with store._lock:
            c = store.main()
            for v, a, b in vs:
                if g6(v):
                    c.execute("UPDATE sc_samples SET game='GTA 6' WHERE sid=? AND ts BETWEEN ? AND ? AND game='Other'", (sid, a, b))
            if all(g6(v) is not False for v, _, _ in vs):
                r = c.execute("SELECT peak, peak_at, mins, hw FROM sc_daily WHERE day=? AND sid=? AND game='Other'", (d, sid)).fetchone()
                if r:
                    c.execute("""INSERT INTO sc_daily VALUES (?,?,'GTA 6',?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                                 peak_at=CASE WHEN excluded.peak>sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                                 peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                              (d, sid, *tuple(r)))
                    c.execute("DELETE FROM sc_daily WHERE day=? AND sid=? AND game='Other'", (d, sid))
                    moved += 1
            c.commit()
    print(f"GTA 6 game cards: {len(rows)} past Indian YouTube streams read, {moved} channel-days moved from Other to GTA 6")
    return moved


def _samples_regame(sids, since: int, old: str, new: str, per: int = 10):
    """Re-label one channel's readings at a time through the (sid, ts) index, a few channels per hold of the write
    lock (19 Nov: one UPDATE over all channels went through the ts index, held the lock for minutes and paused scans)."""
    for i in range(0, len(sids), per):
        with store._lock:
            c = store.main()
            for sid in sids[i:i + per]:
                c.execute("UPDATE sc_samples INDEXED BY sc_samples_sid SET game=? WHERE sid=? AND ts>=? AND game=?",
                          (new, sid, since, old))
            c.commit()


def unnews_g6(since_day: str = "2026-11-18") -> int:
    """One-time repair (19 Nov): news / devotional channels whose GTA 6 coverage was counted as GTA 6 (title rule of
    19 Nov morning, and unfile_g6) get those day rows and readings back under News."""
    _news_read()
    ns = _NS["v"]
    with store.reading():
        c = store.conn()
        sids = [r[0] for r in c.execute("SELECT DISTINCT sid FROM sc_daily WHERE day>=? AND game='GTA 6'", (since_day,))]
        more = [r[0] for r in c.execute("SELECT sid, title FROM sc_channels WHERE sid IN (SELECT DISTINCT sid FROM sc_daily "
                                        "WHERE day>=? AND game='GTA 6')", (since_day,))
                if r[1] and classify("", r[1]) == "News"]
    bad = sorted({s for s in sids if s in ns} | set(more))
    t0 = int(datetime.strptime(since_day, "%Y-%m-%d").replace(tzinfo=events.REPORT_TZ).timestamp())
    for i in range(0, len(bad), 200):
        part = bad[i:i + 200]
        q = ",".join("?" * len(part))
        with store._lock:
            c = store.main()
            for day, sid, pk, pa, mn, hw in c.execute(f"SELECT day, sid, peak, peak_at, mins, hw FROM sc_daily WHERE day>=? AND "
                                                      f"game='GTA 6' AND sid IN ({q})", (since_day, *part)).fetchall():
                c.execute("""INSERT INTO sc_daily VALUES (?,?,'News',?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                             peak_at=CASE WHEN excluded.peak>sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                             peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                          (day, sid, pk, pa, mn, hw))
            c.execute(f"DELETE FROM sc_daily WHERE day>=? AND game='GTA 6' AND sid IN ({q})", (since_day, *part))
            c.commit()
        _samples_regame(part, t0, "GTA 6", "News")
    print(f"GTA 6 news repair: {len(bad)} news/devotional channels moved out of GTA 6")
    return len(bad)


def fix_switch_peaks(since: int = None) -> int:
    """One-time repair (19 Nov): GTA 6 day peaks that came from another game's stream on the same day (the channel
    switched category between two scans and the in-between peak was booked to GTA 6). Where a GTA 6 day peak is over
    1.25x every GTA 6 reading of that day AND the channel had a reading in another game that day at 80%+ of that peak,
    the peak is set to the highest GTA 6 reading."""
    since = since or GTA6_RELEASE
    day = lambda ts: datetime.fromtimestamp(ts, events.REPORT_TZ).strftime("%Y-%m-%d")
    g6, other = {}, {}
    with store.reading():
        c = store.conn()
        for ts, sid, v, g in c.execute("SELECT ts, sid, viewers, game FROM sc_samples WHERE ts>=? AND viewers>=1000", (since,)):
            k = (sid, day(ts))
            d = g6 if g == "GTA 6" else other
            if v > d.get(k, (0, 0))[0]:
                d[k] = (v, ts)
        rows = c.execute("SELECT day, sid, peak FROM sc_daily WHERE game='GTA 6' AND day>=? AND peak>=1000", (day(since),)).fetchall()
    fix = [(g6[(sid, d)][0], g6[(sid, d)][1], d, sid) for d, sid, pk in rows
           if (sid, d) in g6 and pk > 1.25 * g6[(sid, d)][0] and other.get((sid, d), (0,))[0] >= 0.8 * pk]
    with store._lock:
        c = store.main()
        c.executemany("UPDATE sc_daily SET peak=?, peak_at=? WHERE day=? AND sid=? AND game='GTA 6'", fix)
        c.commit()
    print(f"GTA 6 peak repair: {len(fix)} channel-days had another game's peak; set to their highest GTA 6 reading")
    return len(fix)


def fix_switch_peaks2(since: int = None) -> int:
    """One-time repair (20 Nov): a GTA 6 day peak taken in the first SWITCH_GRACE seconds after the channel switched to
    GTA 6 from another category mid-stream (the old stream's audience) is replaced by its highest GTA 6 reading after
    that window."""
    since = since or GTA6_RELEASE
    day = lambda ts: datetime.fromtimestamp(ts, events.REPORT_TZ).strftime("%Y-%m-%d")
    with store.reading():
        c = store.conn()
        sids = [r[0] for r in c.execute("SELECT DISTINCT sid FROM sc_daily WHERE game='GTA 6' AND day>=? AND peak>=1000", (day(since),))]
        rows = {(r[0], r[1]): r[2] for r in c.execute("SELECT day, sid, peak FROM sc_daily WHERE game='GTA 6' AND day>=? AND peak>=1000",
                                                       (day(since),))}
        samp = {}
        for sid in sids:
            samp[sid] = c.execute("SELECT ts, viewers, game FROM sc_samples INDEXED BY sc_samples_sid WHERE sid=? AND ts>=? ORDER BY ts",
                                  (sid, since - 3600)).fetchall()
    fix = []
    for sid, S in samp.items():
        best, early, pg, pts, sw = {}, {}, None, 0, None
        for ts, v, g in S:
            if g == "GTA 6" and pg not in (None, "GTA 6") and ts - pts < 3600:
                sw = ts
            elif g != "GTA 6":
                sw = None
            if g == "GTA 6" and ts >= since:
                d = (day(ts), sid)
                tgt = early if (sw and ts - sw < SWITCH_GRACE) else best
                tgt[d] = max(tgt.get(d, 0), v)
            pg, pts = g, ts
        for d, e in early.items():
            pk = rows.get(d)
            if pk and d in best and pk > best[d] and e >= 0.9 * pk:
                fix.append((best[d], d[0], sid))
    with store._lock:
        c = store.main()
        c.executemany("UPDATE sc_daily SET peak=? WHERE day=? AND sid=? AND game='GTA 6'", fix)
        c.commit()
    print(f"GTA 6 switch-peak repair: {len(fix)} channel-days had a peak from just after switching to GTA 6: "
          + ", ".join(f"{s} {d} -> {p:,}" for p, d, s in fix[:12]))
    return len(fix)


def unfile_g6(since: int = 1795046400) -> int:
    """One-time repair (19 Nov): from 19 Nov 00:00 UTC the stricter title rule filed real GTA 6 YouTube streams such as
    "Playing GTA 6 Until i Finish It" as Other. For YouTube channels whose current title is GTA 6 under the corrected
    rule, that period's Other readings and day rows go back to GTA 6 (merged with any GTA 6 row of the same day)."""
    day0 = datetime.fromtimestamp(since, events.REPORT_TZ).strftime("%Y-%m-%d")
    with store.reading():
        c = store.conn()
        cand = c.execute("""SELECT DISTINCT d.sid, ch.title FROM sc_daily d JOIN sc_channels ch ON ch.sid=d.sid
                            WHERE d.day>=? AND d.game='Other' AND d.sid LIKE 'yt:%'""", (day0,)).fetchall()
    sids = [s for s, t in cand if t and classify("", t) == "GTA 6"]
    for i in range(0, len(sids), 200):
        part = sids[i:i + 200]
        q = ",".join("?" * len(part))
        with store._lock:
            c = store.main()
            rows = c.execute(f"SELECT day, sid, peak, peak_at, mins, hw FROM sc_daily WHERE day>=? AND game='Other' "
                             f"AND sid IN ({q})", (day0, *part)).fetchall()
            for day, sid, pk, pts, mn, hw in rows:
                c.execute("""INSERT INTO sc_daily VALUES (?,?,'GTA 6',?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                             peak_at=CASE WHEN excluded.peak>sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                             peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                          (day, sid, pk, pts, mn, hw))
            c.execute(f"DELETE FROM sc_daily WHERE day>=? AND game='Other' AND sid IN ({q})", (day0, *part))
            c.commit()
        _samples_regame(part, since, "Other", "GTA 6")
    print(f"GTA 6 repair: {len(sids)} YouTube channels moved back from Other to GTA 6 since {day0}")
    return len(sids)


def verify_g6(limit: int = 400, recheck: int = 6 * 3600) -> int:
    """Checks each YouTube channel in the GTA 6 lists against its own streams since launch (owner, 19 Nov: channels
    that never played it were listed). A stream counts when YouTube's game card says Grand Theft Auto VI, or, with no
    card, when its title is about playing GTA 6. A channel with none of those is kept out of GTA 6 lists."""
    if not gta6_on():
        return 0
    day0 = datetime.fromtimestamp(GTA6_RELEASE, events.REPORT_TZ).strftime("%Y-%m-%d")
    with store.reading():
        c = store.conn()
        sids = [r[0] for r in c.execute("SELECT sid, MAX(peak) p FROM sc_daily WHERE game='GTA 6' AND day>=? AND sid LIKE 'yt:%' "
                                         "GROUP BY sid ORDER BY p DESC LIMIT ?", (day0, limit))]
    chk = store.kv_get("g6_check3") or {}
    todo = [s for s in sids if s not in chk or time.time() - chk[s][1] > recheck]
    if not todo:
        return 0

    def one(sid):
        with store.reading():
            vids = [r[0] for r in store.conn().execute(
                "SELECT vid FROM sc_vstreams WHERE sid=? AND last_ts>=? ORDER BY peak DESC LIMIT 4", (sid, GTA6_RELEASE))]
        seen, games, titles = 0, set(), []
        for v in vids:
            x = _yt_game(v)
            if x is None:
                continue
            seen += 1
            if x[0]:
                games.add(x[0].lower())
            if x[1]:
                titles.append(x[1])
        if not seen:
            return None                         # could not check: leave as is
        if any("grand theft auto vi" in g or "gta vi" in g or "gta 6" in g for g in games):
            return True
        if games:
            return False                        # YouTube says another game on every stream
        if not titles:
            return None                         # nothing to judge by: keep (only clear evidence removes a channel)
        t6 = [t for t in titles if classify("", t) == "GTA 6"]
        return ("title", re.sub(r"\W+", " ", t6[0].lower()).strip()) if t6 else False

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, todo))
    # Re-streams copy a bigger channel's title word for word: with no game card, only the biggest channel (sids are
    # in peak order) keeps a title shared with other channels.
    taken = {}
    keys = {sid: ok[1] for sid, ok in zip(todo, res) if isinstance(ok, tuple)}
    keys.update({s: x[2] for s, x in chk.items() if len(x) > 2 and x[2] and s not in keys and s in sids})
    for sid in sorted(keys, key=sids.index):
        taken.setdefault(keys[sid], sid)
    res = [(taken.get(ok[1]) == sid) if isinstance(ok, tuple) else ok for sid, ok in zip(todo, res)]
    now, bad = time.time(), []
    for sid, ok in zip(todo, res):
        if ok is not None:
            chk[sid] = [bool(ok), now, keys.get(sid, "")]
            if not ok:
                bad.append(sid)
    store.kv_set("g6_check3", chk)
    _G6N["at"] = 0
    print(f"GTA 6 check: {len(todo)} channels checked, {len(bad)} kept out: {', '.join(bad[:15])}")
    return len(bad)


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
    j = r.json()
    items = _renderers(j)
    for _ in range(YT_LIVE_PAGES):            # the page loads more streams as you scroll: follow its continuations
        tok = _continuation(j)
        if not tok:
            break
        try:
            r = events._http.post("https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
                                  json={"context": {"client": _itv(gl)}, "continuation": tok},
                                  headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                           "Origin": "https://www.youtube.com"}, timeout=10)
            if r.status_code >= 400:          # keep YouTube's reason (quotaExceeded, keyInvalid ...) in the error
                raise RuntimeError(f"YouTube API {r.status_code}: {(r.json().get('error') or {}).get('errors', [{}])[0].get('reason', '') if r.headers.get('content-type', '').startswith('application/json') else r.text[:80]}")
            j = r.json()
        except Exception:
            break
        items += _renderers(j)
    return _parse(items)


def _continuation(j):
    """The last 'load more' token in a YouTube browse response, or None."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            c = (((o.get("continuationItemRenderer") or {}).get("continuationEndpoint") or {}).get("continuationCommand") or {})
            if c.get("token"):
                out.append(c["token"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(j)
    return out[-1] if out else None


_YTITLE = {}          # vid -> stream title (from search, the API or oEmbed), so a reading without one keeps it


def _oembed_title(vid: str) -> str:
    """A live video's title from YouTube's oEmbed (free, no API quota)."""
    try:
        r = events._http.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}",
                             "format": "json"}, timeout=6, headers={"User-Agent": events._UA})
        return (r.json().get("title") or "") if r.status_code == 200 else ""
    except Exception:
        return ""


def refile_gta6(since_day: str = "2026-11-18") -> int:
    """One-time repair (18 Nov 2026): YouTube streams read without a title were filed under 'Other' on GTA 6 launch
    day. Days since `since_day` filed 'Other' for YouTube channels whose title now says GTA 6 move to 'GTA 6'
    (peak = the higher, minutes and hours watched added)."""
    if not gta6_on():
        return 0
    with store.reading():
        c = store.conn()
        rows = c.execute("SELECT d.day, d.sid, d.peak, d.peak_at, d.mins, d.hw, c.title FROM sc_daily d JOIN sc_channels c "
                         "ON c.sid=d.sid WHERE d.game='Other' AND d.day>=? AND d.sid LIKE 'yt:%'", (since_day,)).fetchall()
    move = [r for r in rows if classify("", r[6] or "") == "GTA 6"]
    if not move:
        return 0
    with store._lock:
        c = store.main()
        for day, sid, pk, pa, mins, hw, _ in move:
            have = c.execute("SELECT peak, peak_at, mins, hw FROM sc_daily WHERE day=? AND sid=? AND game='GTA 6'", (day, sid)).fetchone()
            if have:
                bp, bpa = (pk, pa) if (pk or 0) > (have[0] or 0) else (have[0], have[1])
                c.execute("UPDATE sc_daily SET peak=?, peak_at=?, mins=?, hw=? WHERE day=? AND sid=? AND game='GTA 6'",
                          (bp, bpa, (have[2] or 0) + (mins or 0), (have[3] or 0) + (hw or 0), day, sid))
            else:
                c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (day, sid, "GTA 6", pk, pa, mins, hw))
            c.execute("DELETE FROM sc_daily WHERE day=? AND sid=? AND game='Other'", (day, sid))
        c.commit()
    print(f"Moved {len(move)} launch-day YouTube channel-days from Other to GTA 6: "
          f"{', '.join(sorted({r[1] for r in move})[:10])}")
    return len(move)


def fill_titles(found: dict, limit: int = 60) -> int:
    """YouTube streams found without a title (Kai Cenat and TheBurntPeanut came in from the Live page with none and
    were filed under Other, not GTA 6): look the title up, biggest first."""
    need = sorted(((sid, x) for sid, x in found.items() if x["platform"] == "youtube" and not x.get("title") and x["streams"]),
                  key=lambda kv: -sum(kv[1]["streams"].values()))[:limit]
    vids = [max(x["streams"], key=x["streams"].get) for _, x in need]
    vids = [v for v in vids if v not in _YTITLE and _NOTITLE.get(v, 0) < time.time() - 1800]
    n = 0
    for v, t in zip(vids, _pool.map(_oembed_title, vids)):
        if t:
            _YTITLE[v] = t
        else:
            _NOTITLE[v] = time.time()
    for sid, x in need:
        v = max(x["streams"], key=x["streams"].get)
        if _YTITLE.get(v):
            x["title"] = _YTITLE[v]
            n += 1
    if len(_YTITLE) > 50000:
        _YTITLE.clear()
    return n


_NOTITLE = {}


def _yt_add(found: dict, s: dict, logo: str = ""):
    sid = f"yt:{s['channel_id']}"
    x = found.setdefault(sid, {"sid": sid, "platform": "youtube", "name": s.get("channel", ""), "logo": logo or s.get("logo", ""),
                               "url": f"https://youtu.be/{s['vid']}", "title": s.get("title", ""), "category": "",
                               "streams": {}})
    x["streams"][s["vid"]] = int(s.get("viewers") or 0)
    if s.get("title"):
        _YTITLE[s["vid"]] = s["title"]
    if x["streams"][s["vid"]] >= max(x["streams"].values()):
        # a reading without a title (YouTube's Live page, the live counter) never wipes the title we know
        x.update(url=f"https://youtu.be/{s['vid']}", title=s.get("title") or _YTITLE.get(s["vid"]) or x.get("title", ""))
    if not x.get("logo") and (logo or s.get("logo")):
        x["logo"] = logo or s.get("logo")


# Known channels' own feeds: YouTube search and the Live page miss many streams (a BGMI streamer live with 2,000
# watching often isn't in any search). Every 4 minutes the RSS feed of each watched channel is read (free, ~10 KB)
# and new videos are checked once with the API (videos.list, 1 unit per 50): live ones join the scan, the rest are
# remembered as done. Watched: Indian channels live in the last 14 days, followed channels and tournament rosters.
WATCH_N = int(os.getenv("SCENE_WATCH_N", "400"))
WATCH_SEC = int(os.getenv("SCENE_WATCH_SEC", "240"))
_WSEEN = {}           # vid -> (state "live"/"done", ts)


def _rss(cid: str) -> list:
    try:
        r = events._http.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", timeout=8,
                             headers={"User-Agent": events._UA})
        if r.status_code != 200:
            return []
        out = []
        for e in re.findall(r"<entry>(.*?)</entry>", r.text, re.S)[:4]:
            v = re.search(r"<yt:videoId>([\w-]{11})</yt:videoId>", e)
            pub = re.search(r"<published>([^<]+)</published>", e)
            name = re.search(r"<name>([^<]+)</name>", e)
            if v and pub:
                ts = datetime.fromisoformat(pub.group(1).replace("Z", "+00:00")).timestamp()
                out.append((v.group(1), ts, html.unescape(name.group(1)) if name else ""))
        return out
    except Exception:
        return []


def watch_list() -> list:
    """Channel ids whose feeds are read: tournament rosters, followed channels, Indian channels live lately."""
    ids = []
    for key in events.ROSTERS:
        ids += [h for _, _, h in events.roster(key) if h and h.startswith("UC")]
    with store.reading():
        c = _db()
        ids += [r[0][3:] for r in c.execute(
            """SELECT c.sid FROM sc_channels c LEFT JOIN (SELECT sid, SUM(hw) hw FROM sc_daily WHERE day>=? GROUP BY sid) d ON d.sid=c.sid
               WHERE c.platform='youtube' AND (COALESCE(c.india,0)=1 OR COALESCE(c.tracked,0)=1) AND (c.last_live>? OR COALESCE(c.tracked,0)=1)
               ORDER BY COALESCE(d.hw,0) DESC LIMIT ?""",
            ((datetime.now(events.REPORT_TZ).date() - timedelta(days=14)).strftime("%Y-%m-%d"), time.time() - 14 * 86400, WATCH_N))]
    return list(dict.fromkeys(ids))[:WATCH_N + 60]


def yt_watch_once(found: dict, errors: dict) -> int:
    now = time.time()
    for v in [v for v, (st, t) in _WSEEN.items() if now - t > 3 * 86400]:
        _WSEEN.pop(v, None)
    cand = {}
    ids = watch_list()
    for cid, items in zip(ids, _pool.map(_rss, ids)):
        for vid, ts, name in items:
            if now - ts < 2 * 86400 and _WSEEN.get(vid, ("", 0))[0] != "done":
                cand[vid] = (cid, name)
    if not cand:
        return 0
    key, n = (os.getenv("YOUTUBE_API_KEY") if events.yt_quota_left(.9) else None), 0
    vids = list(cand)
    if key:
        for i in range(0, len(vids), 50):
            try:
                j = events._http.get("https://www.googleapis.com/youtube/v3/videos", timeout=10,
                                     params={"part": "snippet,liveStreamingDetails", "id": ",".join(vids[i:i + 50]), "key": key}).json()
            except Exception as e:
                errors["youtube watch list"] = str(e)[:100]
                continue
            got = {it["id"]: it for it in j.get("items") or []}
            for vid in vids[i:i + 50]:
                it = got.get(vid) or {}
                ls, sn = it.get("liveStreamingDetails") or {}, it.get("snippet") or {}
                if ls.get("actualStartTime") and not ls.get("actualEndTime"):
                    _WSEEN[vid] = ("live", now)
                    _yt_add(found, {"vid": vid, "channel": sn.get("channelTitle") or cand[vid][1], "channel_id": cand[vid][0],
                                    "title": sn.get("title") or "", "viewers": int(ls.get("concurrentViewers") or 0)})
                    n += 1
                elif not ls or ls.get("actualEndTime"):
                    _WSEEN[vid] = ("done", now)        # an upload or a finished stream: never checked again
    else:
        for vid in vids[:30]:
            c_ = _safe_count(vid)
            if c_ and c_ != "err":
                _yt_add(found, {"vid": vid, "channel": cand[vid][1], "channel_id": cand[vid][0], "title": "", "viewers": c_})
                n += 1
            elif c_ is None or c_ == 0:
                _WSEEN[vid] = ("done", now)
    return n


def _event_on_kick() -> bool:
    """A tracked tournament has a live stream on Kick right now (its 2-second counts come first)."""
    return any(str(v).startswith("kick:") for d in events._LIVE.values() for v in d)


def _event_on_air() -> bool:
    return any(s.get("kind") == "official" for d in events._LIVE.values() for s in d.values())


# ---------- one cycle ----------

def cycle(now: float = None) -> dict:
    now = now or time.time()
    found, errors = {}, {}
    blk = blocked()
    sd = seeds()
    _KSEED.clear()
    _KSEED.update(x.lower() for x in sd.get("kick", []))
    sw_jobs = [(p_, g_, _SPOOL.submit(sweep_platform, p_, g_, errors)) for g_ in sweep_games()
               for p_ in ("twitch", "kick") if platforms._keys(p_)] + \
              [("youtube", g_, _SPOOL.submit(sweep_youtube, g_, errors)) for g_ in sweep_games()]   # in parallel

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
                          "streams": {sid: r["viewers"]}, "language": r.get("language", ""), "tags": r.get("tags", ""),
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
    yt_every = SCENE_YT_SEC                   # same pace during tournaments (owner, 13 Nov 2026)
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
    for p_, g_, fu in sw_jobs:               # the launch-game sweep, read in parallel with all of the above
        try:
            got = fu.result(timeout=SCENE_SEC)
        except Exception as e:
            errors[f"sweep {p_} {g_}"] = str(e)[:100]
            continue
        if p_ == "youtube":
            for s_ in got:
                if f"yt:{s_['channel_id']}" not in found or s_["vid"] not in found[f"yt:{s_['channel_id']}"]["streams"]:
                    _yt_add(found, s_)
            continue
        if p_ == "twitch":                   # pictures for the bigger ones only (one call per 100 channels)
            try:
                platforms._tw_logos(sorted({platforms.split(r["vid"])[1] for r in sorted(got, key=lambda r: -r["viewers"])[:1000]}))
            except Exception:
                pass
        for r in sorted(got, key=lambda r: r["viewers"]):
            sid = r["vid"]
            if sid in found and found[sid]["streams"].get(sid, 0) >= r["viewers"]:
                continue
            found[sid] = {"sid": sid, "platform": p_, "name": r["channel"], "url": platforms.link(sid),
                          "logo": platforms.logo(sid), "title": r["title"], "category": r.get("category", ""),
                          "streams": {sid: r["viewers"]}, "language": r.get("language", ""), "tags": r.get("tags", ""),
                          "seeded": (found.get(sid) or {}).get("seeded", False) or sid.split(":", 1)[1] in _KSEED}
    if now - _STATE.get("watch", 0) >= WATCH_SEC:
        _STATE["watch"] = now
        try:
            _STATE["watch_found"] = yt_watch_once(found, errors)
        except Exception as e:
            errors["youtube watch list"] = str(e)[:120]
    if sd["youtube"] and now - _STATE["seeds"] >= yt_every * 2:
        _STATE["seeds"] = now
        for s in _pool.map(lambda h: events._safe(events.check_channel, h), sd["youtube"]):
            if s and s.get("channel_id"):
                _yt_add(found, s)
                _SEEDED.add(f"yt:{s['channel_id']}")

    # Indian or not: look up the country of YouTube channels not seen before (cached in sc_channels)
    try:
        fill_titles(found)
    except Exception as e:
        errors["youtube titles"] = str(e)[:100]
    _load_countries()
    new = [sid[3:] for sid in found if sid.startswith("yt:") and sid[3:] not in _CTRY][:200]
    if new:
        try:
            _CTRY.update(yt_countries(new))
        except Exception as e:
            errors["youtube country lookup"] = str(e)[:120]
    allow = allowed() | _SEEDED | india_known()
    sweeping = set(sweep_games())             # every stream of these counts, however small
    # classify, filter, store
    rows, rejected = [], []
    for sid, x in found.items():
        x["viewers"] = sum(x["streams"].values())
        swept = bool(sweeping) and classify(x.get("category", ""), x.get("title", "")) in sweeping
        if sid in blk or x["viewers"] < (1 if swept else MIN_VIEWERS):
            continue
        x["country"] = _CTRY.get(sid[3:]) if sid.startswith("yt:") else None
        if x["platform"] == "youtube" and not x.get("category"):       # the game YouTube shows under the video
            card = next((_YCARD[v] for v in sorted(x["streams"], key=lambda v: -x["streams"][v]) if _YCARD.get(v)), "")
            if card:
                x["category"] = card
        x["game"] = classify(x.get("category", ""), x.get("title", ""))   # first pass (BGMI streams are Indian)
        x["india"] = verdict(x, x["country"], allow)
        if x["platform"] != "youtube":
            x["india_hint"] = bool(x["india"]) or india_hint(x)     # its chat is read to confirm or rule it out
        if not x["india"] and x["viewers"] < GLOBAL_MIN and not swept and not x.get("india_hint"):
            rejected.append(x)                # too small to matter worldwide; remembered so it isn't looked up again
            continue
        x["game"] = classify(x.get("category", ""), x.get("title", ""))
        if x["platform"] == "youtube" and x["game"] == "Other":
            x["game"] = yt_category_game(sid) or "Other"
        x["tour"] = tournament(x.get("title", ""), x["game"])
        if x["tour"] and TOUR_GAME.get(x["tour"]):
            x["game"] = TOUR_GAME[x["tour"]]          # a VCT broadcast or co-stream is Valorant, whatever the category says
        elif x["tour"] and x["game"] in ("", "Other"):
            lp = tournament_info(x["tour"])           # a Liquipedia tournament's game, for streams with no category
            if lp and lp["game"] != "Fighting games":
                x["game"] = "BGMI" if lp["game"] == "BGMI" else lp["game"]
        if x["india"] and x["game"] == "PUBG Mobile" and not x["tour"]:
            x["game"] = "BGMI"                        # PUBG Mobile is banned in India; Indian streams of it are BGMI
        if not x.get("logo"):                 # the channel's real picture: YouTube channel page / Kick / Twitch
            x["logo"] = events.avatar(sid[3:]) if x["platform"] == "youtube" else platforms.logo(sid)
        x["seen"] = now
        rows.append(x)
    _SCANMEM.update(ts=int(now), rows=[{"sid": x["sid"], "viewers": x["viewers"], "game": x["game"], "platform": x["platform"],
                                        "name": x["name"], "url": x["url"], "logo": x.get("logo") or "", "title": x.get("title", ""),
                                        "country": x.get("country"), "language": x.get("language") or "",
                                        "india": 1 if x.get("india", True) else 0, "tour": x.get("tour"),
                                        "section": section_of(x["game"], x.get("tour"))} for x in rows])
    with _lock:
        last = _STATE["last"]
        _LIVE.clear()
        _LIVE.update({x["sid"]: x for x in rows})
        _STATE["last"] = now
        _STATE["errors"] = errors
    t_st = time.time()
    CYCLE["fetch_s"] = round(t_st - (CYCLE.get("started") or t_st))      # health page: reading the platforms
    _store(rows, now, last)
    _SCANMEM["saved"] = time.time()
    CYCLE["store_s"] = round(time.time() - t_st)                          # health page: writing it down
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


# Worldwide pages count "today" in US Central time (owner, 18 Nov 2026: the GTA 6 card said "today" but started at
# 12:30 PM CT, India's midnight, and missed the morning's peaks). sc_daily is per IST day, so the Central day is kept
# in memory: per (channel, game) peak, minutes live and hours watched since Central midnight, updated every scan and
# rebuilt from sc_samples after a restart.
from zoneinfo import ZoneInfo as _ZI
CT = _ZI("America/Chicago")
_CTD = {"day": None, "m": {}, "ready": False}


def ct_midnight(ts: float = None) -> float:
    d = datetime.fromtimestamp(ts or time.time(), CT)
    return datetime(d.year, d.month, d.day, tzinfo=CT).timestamp()


def _ct_add(rows, now, dt, fpk):
    day = datetime.fromtimestamp(now, CT).strftime("%Y-%m-%d")
    if _CTD["day"] != day:
        _CTD.update(day=day, m={})
    m = _CTD["m"]
    for x in rows:
        k = (x["sid"], x["game"])
        e = m.get(k)
        if e is None:
            e = m[k] = [0, 0, 0.0, 0.0]
        pk = max(x["viewers"], fpk.get(x["sid"], 0))
        if pk > e[0]:
            e[0], e[1] = pk, int(now)
        e[2] += dt / 60
        e[3] += x["viewers"] * dt / 3600


def ct_seed():
    """After a restart: the Central day so far from the per-scan readings (sc_samples), merged with what the scans
    added since the start."""
    t0, t1 = ct_midnight(), time.time()
    got = {}
    # Read in 10-minute slices along the ts index and add up here: one GROUP BY over a day of readings (10M+ rows)
    # made SQLite sort them on disk for minutes and stalled the scans after a restart (18 Nov 2026).
    try:
        a = t0
        while a < t1:
            b = min(a + 600, t1)
            with store.reading():
                for sid, game, v, ts in store.conn().execute(
                        "SELECT sid, game, viewers, ts FROM sc_samples WHERE ts>=? AND ts<?", (a, b)):
                    e = got.get((sid, game))
                    if e is None:
                        e = got[(sid, game)] = [0, 0, 0.0, 0.0]
                    if v > e[0]:
                        e[0], e[1] = v, ts
                    e[2] += SCENE_SEC / 60
                    e[3] += v * SCENE_SEC / 3600
            a = b
            time.sleep(0.05)                  # let the scans and pages run in between
    except Exception as e:
        print(f"Central day seed: {str(e)[:120]}")
    day = datetime.fromtimestamp(t1, CT).strftime("%Y-%m-%d")
    if _CTD["day"] not in (None, day):
        return
    _CTD["day"] = day
    m = _CTD["m"]
    for k, v in got.items():
        e = m.get(k)
        if e is None:
            m[k] = v
        else:
            if v[0] > e[0]:
                e[0], e[1] = v[0], v[1]
            e[2] += v[2]
            e[3] += v[3]
    _CTD["ready"] = True


def ct_rows(game=None) -> list:
    """[(sid, game, peak, peak_at, mins, hw)] for the Central day so far (one game if given)."""
    return [(k[0], k[1], *v) for k, v in list(_CTD["m"].items()) if not game or k[1] == game]


_CHSIG = {}          # sid -> (what was last written to sc_channels, when)
_DBUF = {}           # sc_daily rows added up in memory between writes
DAILY_FLUSH = int(os.getenv("SCENE_DAILY_FLUSH", "0"))     # 0 = every scan (boards stay live); raise if writes get slow


def _flush_daily(c):
    """Write the buffered daily totals (caller holds the write lock)."""
    buf = _DBUF.pop("rows", {})
    if buf:
        c.executemany("""INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(day, sid, game) DO UPDATE SET
                         peak_at=CASE WHEN excluded.peak > sc_daily.peak THEN excluded.peak_at ELSE sc_daily.peak_at END,
                         peak=MAX(sc_daily.peak, excluded.peak), mins=sc_daily.mins+excluded.mins, hw=sc_daily.hw+excluded.hw""",
                      [(k[0], k[1], k[2], *v) for k, v in buf.items()])


def _store(rows, now, last):
    if not rows:
        return
    dt = min(now - last, SCENE_SEC * 2) if last else SCENE_SEC
    day = datetime.fromtimestamp(now, events.REPORT_TZ).strftime("%Y-%m-%d")
    fpk = dict(_FPEAK)                        # 2-second readings since the last scan: the true peak in between
    _FPEAK.clear()
    grace = set()
    for x in rows:                            # a channel that switched game mid-stream: for SWITCH_GRACE seconds the
        sid = x["sid"]                        # audience is still the old stream's, so it doesn't set the new game's peak
        pg, seen = _PREVGAME.get(sid, (None, 0))  # (19 Nov: neyoo went from a 47K watch party to GTA 6 and the first
        if pg is not None and pg != x["game"] and now - seen < 1800:     # GTA 6 reading, 46K, became his GTA 6 peak)
            _SWITCH[sid] = (x["game"], now)
        sw_ = _SWITCH.get(sid)
        if sw_ and sw_[0] == x["game"] and now - sw_[1] < SWITCH_GRACE:
            grace.add(sid)
            fpk.pop(sid, None)
        _PREVGAME[sid] = (x["game"], now)
    if len(_PREVGAME) > 400000:
        _PREVGAME.clear()
        _SWITCH.clear()
    vpk = dict(_VPEAK)
    _VPEAK.clear()
    try:
        _ct_add(rows, now, dt, fpk)
    except Exception as e:
        print(f"Central day: {str(e)[:100]}")
    with store._lock:
        c = _db()
        sw = set(sweep_games())               # a launch game's thousands of tiny streams: counted everywhere (totals, daily
        c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)",          # peaks, live lists) but not kept scan by scan
                      [(int(now), x["sid"], x["viewers"], x["game"]) for x in rows if x["viewers"] >= SAMPLE_MIN or x["game"] not in sw])
        # Channels: only new or changed ones are written, plus everyone's last_live every 10 minutes (with 100,000+
        # live streams on GTA 6 launch day, rewriting every channel every scan held the write lock for a minute).
        chg = []
        for x in rows:
            sig = (x["name"], x["url"], x.get("logo") or "", x.get("title", ""), x["game"], x.get("country"),
                   1 if x.get("india", True) else 0, x.get("language") or "", x.get("tags") or "")
            old_ = _CHSIG.get(x["sid"])
            if old_ is None or old_[0] != sig or now - old_[1] >= 600:
                chg.append((x["sid"], x["platform"], x["name"], x["url"], x.get("logo") or "", now, now, x.get("title", ""),
                            x["game"], x.get("country"), 1 if x.get("india", True) else 0, x.get("language") or "",
                            x.get("tags") or ""))
                _CHSIG[x["sid"]] = (sig, now)
        if len(_CHSIG) > 400000:
            _CHSIG.clear()
        c.executemany("""INSERT INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                         country, india, language, tags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sid) DO UPDATE SET
                         name=excluded.name, url=excluded.url,
                         logo=CASE WHEN excluded.logo!='' THEN excluded.logo ELSE sc_channels.logo END,
                         last_live=excluded.last_live, title=excluded.title, game=excluded.game,
                         country=COALESCE(excluded.country, sc_channels.country), india=excluded.india,
                         language=excluded.language, tags=excluded.tags""", chg)
        # Daily totals: added up in memory and written every DAILY_FLUSH seconds (and at the day's change)
        buf = _DBUF.setdefault("rows", {})
        for x in rows:
            k = (day, x["sid"], x["game"])
            pk = 0 if x["sid"] in grace else max(x["viewers"], fpk.get(x["sid"], 0))
            e = buf.get(k)
            if e is None:
                buf[k] = [pk, int(now), dt / 60, x["viewers"] * dt / 3600]
            else:
                if pk > e[0]:
                    e[0], e[1] = pk, int(now)
                e[2] += dt / 60
                e[3] += x["viewers"] * dt / 3600
        if now - _DBUF.get("at", 0) >= DAILY_FLUSH or _DBUF.get("day") not in (None, day):
            _flush_daily(c)
            _DBUF.update(at=now, day=day)
        for x in rows:                        # each YouTube stream on its own: peak CCV, hours watched, duration
            if not x["sid"].startswith("yt:"):
                continue
            for vid, v in (x.get("streams") or {}).items():
                pk = max(int(v or 0), vpk.get(vid, 0))
                if pk <= 0:
                    continue
                c.execute("""INSERT INTO sc_vstreams VALUES (?,?,?,?,?,?,?,1) ON CONFLICT(vid) DO UPDATE SET
                             last_ts=excluded.last_ts, n=sc_vstreams.n+1, hw=sc_vstreams.hw+excluded.hw,
                             peak_at=CASE WHEN excluded.peak > sc_vstreams.peak THEN excluded.peak_at ELSE sc_vstreams.peak_at END,
                             peak=MAX(sc_vstreams.peak, excluded.peak)""",
                          (vid, x["sid"], int(now), int(now), pk, int(now), int(v or 0) * dt / 3600))
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
        c.executemany("""INSERT INTO sc_reg_day VALUES (?,?,?,?) ON CONFLICT(region, game, day) DO UPDATE SET
                         peak=MAX(sc_reg_day.peak, excluded.peak)""",      # each day's peak: the category page's bars
                      [(r_[0], r_[1], day, r_[2]) for r_ in reg if r_[0] == "global"] +
                      [("in", g, day, v) for g, (v, n) in cats.items()])
        for x in rows:                        # each channel's part in each tournament, per day
            if x.get("tour"):
                c.execute("""INSERT INTO sc_tour_ch VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(tour, sid, day) DO UPDATE SET
                             peak_at=CASE WHEN excluded.peak > sc_tour_ch.peak THEN excluded.peak_at ELSE sc_tour_ch.peak_at END,
                             peak=MAX(sc_tour_ch.peak, excluded.peak), mins=sc_tour_ch.mins+excluded.mins,
                             hw=sc_tour_ch.hw+excluded.hw""",
                          (x["tour"], x["sid"], day, max(x["viewers"], fpk.get(x["sid"], 0)), int(now), dt / 60,
                           x["viewers"] * dt / 3600, 1 if x.get("india", True) else 0))
        for region, t, v, n in reg:           # each tournament's all-time numbers (all channels together)
            if region.startswith("tour:"):
                c.execute("""INSERT INTO sc_tour VALUES (?,?,?,?,?,?,?) ON CONFLICT(tour, region) DO UPDATE SET
                             peak_at=CASE WHEN excluded.peak > sc_tour.peak THEN excluded.peak_at ELSE sc_tour.peak_at END,
                             peak=MAX(sc_tour.peak, excluded.peak), last_ts=excluded.last_ts, hw=sc_tour.hw+excluded.hw""",
                          (t, region[5:], v, int(now), int(now), int(now), v * dt / 3600))
        if int(now) % 3600 < SCENE_SEC:          # about once an hour: drop raw readings older than KEEP_DAYS
            c.execute("DELETE FROM sc_samples WHERE ts < ?", (now - KEEP_DAYS * 86400,))
            c.execute("DELETE FROM sc_reg WHERE ts < ? AND region LIKE 'tour:%' AND game LIKE '% tournaments'", (now - 30 * 86400,))
            c.execute("DELETE FROM sc_reg WHERE ts < ? AND region LIKE 'tour:%'", (now - 400 * 86400,))
        c.commit()


FAST_SEC = float(os.getenv("SCENE_FAST_SEC", "2"))
_FASTV = {}          # sid -> [ts, viewers or None, misses]: Kick/Twitch re-read every FAST_SEC between scans
_PREVGAME = {}       # sid -> (its game, when) at the last stored scan
_SWITCH = {}         # sid -> (game switched to mid-stream, when)
SWITCH_GRACE = int(os.getenv("SCENE_SWITCH_GRACE", "900"))
_FPEAK = {}          # sid -> highest 2-second reading since the last scan was stored (so daily peaks catch short spikes)
_VPEAK = {}          # YouTube video id -> highest 2-second reading since the last scan (per-stream peak CCV)


def _fast_seen(sid: str, v: int):
    if v and v > _FPEAK.get(sid, 0):
        _FPEAK[sid] = v


YT_FAST_N = int(os.getenv("SCENE_YT_FAST_N", "40"))   # biggest YouTube channels re-counted every FAST_SEC
YT_FAST_IN = int(os.getenv("SCENE_YT_FAST_IN", "40"))  # plus the biggest Indian ones (most of this site's audience)
_YTF = {"next": 0.0, "slow": 0, "mid": 0.0}
# Middle tier (19 Nov: Red parasite peaked near 4,900 between scans and the site showed ~2,200): the next YouTube streams,
# Indian ones from 300 watching and others from 2,000, re-counted every YT_MID_SEC so their peaks are caught too.
YT_MID_N = int(os.getenv("SCENE_YT_MID_N", "400"))
YT_MID_SEC = int(os.getenv("SCENE_YT_MID_SEC", "20"))


HOT = {}              # sid -> until: channels whose page someone has open; their YouTube count is read every 2 s too


def live_now(sid: str) -> dict:
    """A live channel's numbers for its page, every 2 seconds: watching now, this stream's readings so far."""
    from tracker import moments
    t = time.time()
    HOT[sid] = t + 30
    for k in [k for k, v in HOT.items() if v < t]:
        HOT.pop(k, None)
    with _lock:
        x = dict(_LIVE.get(sid) or {})
    f = _FASTV.get(sid)
    now_v = f[1] if f and f[1] is not None and t - f[0] < 30 else (x.get("viewers") or 0)
    if not x:
        now_v = 0
    with store.reading():
        S = _db().execute("SELECT ts, MAX(viewers) FROM sc_samples WHERE sid=? AND ts>=? GROUP BY ts ORDER BY ts",
                          (sid, t - 12 * 3600)).fetchall()
    S = [[a, b] for a, b in S]
    start = None                              # this stream: back from now to the last gap of over 15 minutes
    for i in range(len(S) - 1, 0, -1):
        if S[i][0] - S[i - 1][0] > 900:
            start = S[i][0]
            break
    if S and start is None:
        start = S[0][0]
    S = [r for r in S if start is None or r[0] >= start]
    fast = [[int(a), b] for a, b in list(moments._HIST.get(sid) or []) if not S or a > S[-1][0] - 1]
    ser = S + fast
    if start is None and ser:
        start = ser[0][0]
    if now_v and (not ser or t - ser[-1][0] > 1):
        ser.append([int(t), now_v])
    vals = [v for _, v in ser if v]
    return {"sid": sid, "live": bool(now_v), "now": now_v, "ts": int(f[0]) if f else int(t), "title": x.get("title", ""),
            "url": x.get("url", ""), "game": x.get("game", ""), "start": start, "series": ser[-1500:],
            "peak": max(vals, default=0), "avg": round(sum(vals) / len(vals)) if vals else 0,
            "every": 2 if f and t - f[0] < 15 else SCENE_SEC}


def yt_fast_once(now: float = None) -> int:
    """Re-count the biggest live YouTube channels from YouTube's live counter (the method the tournament tracker uses
    every 2s). They hold most of the viewers, so totals move every 2 seconds; the rest are re-counted each scan.
    Every 2 seconds, also during tournaments; backs off only if YouTube refuses."""
    t = now or time.time()
    if t < _YTF["next"]:
        return 0
    with _lock:
        top = [(sid, list(x["streams"])) for sid, x in sorted(_LIVE.items(), key=lambda kv: -kv[1]["viewers"])
               if x["platform"] == "youtube"]
        rest = top[YT_FAST_N:]
        top = top[:YT_FAST_N] + [(sid, v) for sid, v in rest if _LIVE[sid].get("india")][:YT_FAST_IN]
        have = {sid for sid, _ in top}
        if t >= _YTF["mid"]:
            _YTF["mid"] = t + YT_MID_SEC * (2 ** _YTF["slow"])
            top += [(sid, v) for sid, v in rest if sid not in have and
                    _LIVE[sid]["viewers"] >= (300 if _LIVE[sid].get("india") else 2000)][:YT_MID_N]
            have = {sid for sid, _ in top}
        top += [(sid, list(_LIVE[sid]["streams"])) for sid, exp in list(HOT.items())   # channel pages open right now
                if exp > t and sid in _LIVE and sid not in have and sid.startswith("yt:")][:20]
    jobs = [(sid, vid, _YFPOOL.submit(_safe_count, vid)) for sid, vids in top for vid in vids]
    got, errs = {}, 0
    for sid, vid, fu in jobs:
        n = fu.result()
        if n == "err":
            errs += 1
            got.setdefault(sid, None)
            continue
        if n and n > _VPEAK.get(vid, 0):
            _VPEAK[vid] = n
        got[sid] = (got.get(sid) or 0) + (n or 0)
    for sid, v in got.items():
        f = _FASTV.setdefault(sid, [t, None, 0])
        if v is None:
            continue                          # couldn't read: keep the last value
        if v > 0:
            f[:] = [t, v, 0]
            _fast_seen(sid, v)
        else:
            f[0], f[2] = t, f[2] + 1
            if f[2] >= 3:                     # no 'watching' count three times running: ended
                f[1] = 0
    _YTF["slow"] = min(_YTF["slow"] + 1, 4) if jobs and errs > len(jobs) // 2 else max(_YTF["slow"] - 1, 0)
    base = FAST_SEC                           # every 2 s, tournament or not (owner, 13 Nov 2026); backs off only if YouTube refuses
    _YTF["next"] = t + base * (2 ** _YTF["slow"])
    _YTF["last"] = {"n": len(jobs), "errs": errs, "took": round(time.time() - t, 2), "slow": _YTF["slow"]}
    return len(got)


def fast_once(now: float = None) -> int:
    """Re-read every live Kick/Twitch channel (one batched request per platform). Returns how many were read."""
    t_ = time.time()
    _FASTAT[0] = t_
    kcap = _KFAST["cap"] if _KFAST["cap"] and t_ < _KFAST["until"] else FAST_KICK
    cap = {"twitch": FAST_TW, "kick": kcap}
    with _lock:
        ids = {}
        for p in ("kick", "twitch"):
            L = [(sid, x) for sid, x in sorted(_LIVE.items(), key=lambda kv: -kv[1]["viewers"]) if x["platform"] == p]
            top = [sid for sid, _ in L[:cap[p]]]
            top += [sid for sid, x in L[cap[p]:] if x.get("india")][:FAST_IN[p]]
            ids[p] = top
    n, fails = 0, []
    for p, sids in ids.items():
        if not sids or not platforms._keys(p):
            continue
        try:                                  # one platform failing must not stop the other's 2-second reads
            rows = platforms._by_ids(p, [platforms.split(s)[1] for s in sids])
        except Exception as e:
            fails.append(f"{p}: {str(e)[:100]}")
            if p == "kick" and "429" in str(e):
                _KFAST.update(cap=max(100, kcap // 2), until=time.time() + 600)
                print(f"Kick 2-second reads: rate limited, reading the top {_KFAST['cap']} for 10 minutes")
            continue
        got = {r["vid"]: r["viewers"] for r in rows}
        t = now or time.time()
        for s in sids:
            f = _FASTV.setdefault(s, [t, None, 0])
            if s in got:
                f[:] = [t, got[s], 0]
                _fast_seen(s, got[s])
                n += 1
            else:
                f[0], f[2] = t, f[2] + 1
                if f[2] >= 3:                 # gone from the platform's live list three times running: ended
                    f[1] = 0
    if fails and not n:
        raise RuntimeError("; ".join(fails))
    if fails:
        print(f"Kick/Twitch fast count partly failed: {'; '.join(fails)}")
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
        if MOMENTS_ON:                        # Moments: off since 21 Nov (owner); MOMENTS=1 in .env turns it back on
            try:
                from tracker import moments
                moments.observe()             # sudden jumps in viewers -> Moments
            except Exception as e:
                print(f"Moments: {str(e)[:120]}")
        time.sleep(max(0.2, wait - (time.time() - t0)))


COMPACT_AFTER = int(os.getenv("SCENE_COMPACT_DAYS", "35"))   # per-scan totals older than this: one per 10 minutes


def compact(now: float = None, max_days: int = 3) -> int:
    """Keep only the highest reading per 10 minutes in sc_cat / sc_reg for days older than COMPACT_AFTER (charts that
    old don't need 2-minute detail; peaks are kept). A few days per call so the database is never locked for long."""
    now = now or time.time()
    done = store.kv_get("scene_compacted") or 0
    stop = now - COMPACT_AFTER * 86400
    n, t = 0, max(done, 0)
    with store._lock:
        c = _db()
        if not t:
            t = (c.execute("SELECT MIN(ts) FROM sc_cat").fetchone()[0] or stop)
        for _ in range(max_days):
            if t >= stop:
                break
            t1 = min(t + 86400, stop)
            for tbl, key in (("sc_cat", "game"), ("sc_reg", "region, game")):
                n += c.execute(f"""DELETE FROM {tbl} WHERE ts >= ? AND ts < ? AND rowid NOT IN
                                   (SELECT rowid FROM (SELECT rowid, MAX(viewers) FROM {tbl} WHERE ts >= ? AND ts < ?
                                    GROUP BY {key}, ts / 600))""", (t, t1, t, t1)).rowcount
            t = t1
        c.commit()
    store.kv_set("scene_compacted", t)
    return n


# Twitch's whole audience: the scan keeps the biggest ~2,000 streams (100+ viewers); the long tail of small streams
# holds a large share of Twitch viewers. Every 5 minutes every live stream is paged through (about 1,000 API calls,
# well inside Twitch's 800 per minute) and the full total replaces the tracked one in the worldwide "watching now".
_TWFULL = {"viewers": 0, "streams": 0, "ts": 0.0}
TWITCH_FULL_EVERY = int(os.getenv("SCENE_TWITCH_FULL_SEC", "300"))


def twitch_full_once() -> dict:
    after, tot, n = None, 0, 0
    for _ in range(3000):
        j = platforms._get("twitch", "https://api.twitch.tv/helix/streams", {"first": 100, **({"after": after} if after else {})})
        d = j.get("data") or []
        tot += sum(int(x.get("viewer_count") or 0) for x in d)
        n += len(d)
        after = (j.get("pagination") or {}).get("cursor")
        if not after or not d:
            break
        time.sleep(0.25 if sweep_games() else 0.12)   # ~500 calls a minute at most (~240 during a launch sweep)
    with _lock:                               # the part of Twitch this site doesn't track one by one (the long tail):
        tracked = sum(x["viewers"] for x in _LIVE.values() if x.get("platform") == "twitch")
        tn = sum(1 for x in _LIVE.values() if x.get("platform") == "twitch")
    _TWFULL.update(viewers=tot, streams=n, ts=time.time(), tail=max(0, tot - tracked), tail_n=max(0, n - tn))
    return dict(_TWFULL)


def run_twitch_full():
    time.sleep(60)
    while True:
        try:
            if platforms._keys("twitch"):
                twitch_full_once()
        except Exception as e:
            print(f"Twitch full count: {str(e)[:150]}")
        time.sleep(TWITCH_FULL_EVERY * (4 if sweep_games() else 1))   # launch sweep on: every 20 min, Twitch calls go to it


def _with_full(out: dict, region: str, game, sec: str) -> dict:
    """Worldwide overview only: Twitch = every live stream (from the 5-minute full count), not only the tracked ones."""
    f = dict(_TWFULL)
    every = TWITCH_FULL_EVERY * (4 if sweep_games() else 1)     # how often it is counted (20 min during a sweep)
    if region != "global" or game or sec or not f["viewers"] or time.time() - f["ts"] > 2 * every + 300:
        return out            # (25 Nov: kept for 15 min but counted every 20, so Twitch fell to the tracked 1.49M of 2.14M)
    pl = out.get("platforms") or []
    tw = next((x for x in pl if x["platform"] == "twitch"), None)
    # Twitch total = the tracked streams as they are now (2-second readings) + the long tail from the last full count
    # (thousands of small streams that move slowly), so the total moves live instead of every 20 minutes
    full = (tw["viewers"] if tw else 0) + f.get("tail", 0) if "tail" in f else f["viewers"]
    extra = full - (tw["viewers"] if tw else 0)
    if extra <= 0:
        return out
    if tw:
        tw["viewers"] = full
    else:
        pl.append({"platform": "twitch", "name": platforms.NAMES["twitch"], "viewers": full})
    pl.sort(key=lambda x: -x["viewers"])
    k = out.get("kpis") or {}
    if "watching" in k:
        k["watching"] += extra
        day = datetime.now(events.REPORT_TZ).strftime("%Y-%m-%d")
        best = store.kv_get("allpeak") or {}
        if best.get("day") != day or k["watching"] > best.get("v", 0):
            best = {"day": day, "v": k["watching"], "ts": int(time.time())}
            store.kv_set("allpeak", best)
        if best["v"] > (k.get("peak_today") or 0):
            k["peak_today"], k["peak_today_at"] = best["v"], best["ts"]
    out["india_total"] = (out.get("india_total") or 0) + extra
    out["twitch_full"] = {"viewers": full, "streams": f["streams"], "ts": int(f["ts"]), "counted": f["viewers"]}
    return out


def overloaded() -> bool:
    """The machine is behind: load well above its cores, or the scan running past twice its pace. Background warm-ups
    pause then, so the scan and visitors' pages get the CPU (25 Nov: load 21 on 4 cores, scans 14 min, pages 10 min)."""
    try:
        if os.getloadavg()[0] > 2.5 * (os.cpu_count() or 4):
            return True
    except OSError:
        pass
    return bool(CYCLE.get("running") and time.time() - (CYCLE.get("started") or time.time()) > 2 * SCENE_SEC)


def run_forever():
    if _STATE["running"]:
        return
    _STATE["running"] = True
    threading.Thread(target=ct_seed, daemon=True).start()   # the US Central day so far (worldwide "today")
    threading.Thread(target=run_fast, daemon=True).start()
    threading.Thread(target=run_twitch_full, daemon=True).start()
    time.sleep(20)                           # let the event counter start first
    while True:
        t0 = time.time()
        try:
            if int(time.time()) % 3600 < SCENE_SEC:
                compact()
        except Exception as e:
            print(f"Compaction: {str(e)[:120]}")
        try:
            CYCLE.update(started=t0, running=True)
            r = cycle()
            took = time.time() - t0
            CYCLE.update(running=False, took=round(took), done=time.time(), live=r.get("live"))
            if took > SCENE_SEC * 2:
                print(f"Scan took {took:.0f}s ({r.get('live')} live)")
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
SERIES_NAMES = {"LAUNCH": "BGMI Launch Party", "INKR": "INKR Invitational", "CEGC": "CEGC"}


def game_history(game: str) -> list:
    """[{name, peak}] oldest first, with tracked tournaments' recorded peaks added or updated."""
    hist = [list(x) for x in GAME_HISTORY.get(game, [])]
    if not hist:
        return []
    with store.reading():
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
    with store.reading():
        c = events._db()
        for ev in sorted(events.events().values(), key=lambda e: -(e.get("created") or 0)):
            pr = events.preset(ev["key"])
            if pr.get("hidden"):
                continue
            peak = c.execute("SELECT MAX(total) FROM ev_ticks WHERE event=?", (ev["key"],)).fetchone()[0] or 0
            last = c.execute("SELECT ts, total, official FROM ev_ticks WHERE event=? ORDER BY ts DESC LIMIT 1",
                             (ev["key"],)).fetchone()
            live = bool(last and time.time() - last[0] < 120 and not events.paused(ev["key"]))
            state = "ended" if pr.get("ended") else "live" if live else "upcoming" if events.next_start(ev["key"]) else "off"
            out.append({"key": ev["key"], "name": ev["name"], "game": events.opt(ev, "game", ""), "state": state,
                        "next_start": events.next_start(ev["key"]), "now": last[1] if live else 0, "peak": peak,
                        "url": f"/e/{ev['key']}/"})
    order = {"live": 0, "upcoming": 1, "off": 2, "ended": 3}
    return sorted(out, key=lambda e: (order[e["state"]], (e["next_start"] or 9e18) if e["state"] == "upcoming" else 0))   # soonest first


def category_name(cat: str):
    """Display name for a category slug, or None if nothing in it has ever been seen."""
    for g, _ in GAMES:
        if slug(g) == cat:
            return g
    with store.reading():
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


_LB = {}
_LBL = threading.Lock()


def _live_base(region: str):
    """Everyone live in a region with 2-second viewers, built once per 2 seconds for all pages (19 Nov: every page
    and section built it on its own, 7-12 s each under load)."""
    sk = (_SCANMEM.get("ts"), len(_FASTV), frozenset(blocked()))    # a new scan or a block rebuilds it at once
    hit = _LB.get(region)
    if hit and time.time() - hit[0] < 2 and hit[2] == sk:
        return hit[1]
    with _LBL:
        hit = _LB.get(region)
        if hit and time.time() - hit[0] < 2 and hit[2] == sk:
            return hit[1]
        v = _live_base_build(region)
        _LB[region] = (time.time(), v, sk)
        return v


def _live_part(game=None, region: str = "in", sec: str = "") -> dict:
    """Who is live now in a region (and section or game): the latest scan (read from the database once per scan) with
    Kick/Twitch viewers replaced by the 2-second readings when they're fresh."""
    blk, last, fresh, now, live0, region_total, now_map, secs0 = _live_base(region)
    live = [dict(x) for x in live0 if not sec or x["section"] == sec]
    secs = {k: {**z, "top": list(z["top"]), "items": dict(z["items"])} for k, z in secs0.items()}
    return _live_rest(live, secs, blk, last, fresh, now, region_total, now_map, game, sec)


_PEAKBG = {}


def _scan_peaks():
    try:
        day = datetime.now(events.REPORT_TZ).strftime("%Y-%m-%d")
        with store.reading():
            _SCAN["peak"] = dict(_db().execute("SELECT sid, MAX(peak) FROM sc_daily WHERE day=? GROUP BY sid", (day,)).fetchall())
    except Exception as e:
        print(f"Scan peaks: {str(e)[:80]}")
    finally:
        _PEAKBG["busy"] = False


def _live_base_build(region: str):
    blk = blocked()
    mem = _SCANMEM.get("rows")
    with store.reading():
        c = _db()
        last = _SCANMEM["ts"] if mem else (c.execute("SELECT MAX(ts) FROM sc_samples").fetchone()[0] or 0)
        if _SCAN["ts"] != last and mem:       # the scan this process just made: straight from memory (every stream,
            _SCAN["rows"] = sorted((dict(r) for r in mem), key=lambda r: -r["viewers"])     # small ones included)
            if not _PEAKBG.get("busy"):         # today's peaks: read in the background (every page waited 30 s+ on it)
                _PEAKBG["busy"] = True
                threading.Thread(target=_scan_peaks, daemon=True).start()
            _SCAN["ts"] = last
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
    # Shown up to 15 minutes after the last full scan (19 Nov: a scan after a restart or under load took over 6 minutes
    # and pages showed "-" and "Nothing live"). Kick/Twitch viewers are the 2-second readings anyway, and streams that
    # ended there drop out at once; only YouTube numbers can be up to one scan old.
    fresh = time.time() - last < max(SCENE_SEC * 3, FRESH_SEC)
    now, seen, live = time.time(), set(), []
    for r in (_SCAN["rows"] if fresh else []):
        if r["sid"] in blk or r["sid"] in seen or (region == "in" and not r["india"]) or name_blocked(r.get("name")):
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
    return blk, last, fresh, now, live, region_total, now_map, secs


def _live_rest(live, secs, blk, last, fresh, now, region_total, now_map, game, sec):
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
            # When the numbers on the page last changed: the 2-second readings, else the last saved scan. The scan's
            # own stamp is when it started (4-10 min before it is saved), which showed "paused" while it was live.
            "updated": max(last, _SCANMEM.get("saved") or 0, _FASTAT[0] if time.time() - _FASTAT[0] < 60 else 0),
            "fresh": fresh, "india_total": region_total, "region_total": region_total,
            "live_total": sum(x["viewers"] for x in live), "now": now}


def named_tour(name: str) -> bool:
    """A real tournament (Liquipedia or a known league), not a '<game> tournaments' catch-all."""
    return bool(name) and not name.endswith(" tournaments")


_TRK = {"ts": 0, "v": []}


INDIA_GAMES = {"BGMI", "PUBG Mobile", "Free Fire", "Valorant", "PUBG: Battlegrounds"}   # India's esports list (owner)
_LPN = {"ts": -1, "m": {}}


def _lp_named(name: str):
    """The Liquipedia tournament with this exact name (ongoing, upcoming or recent), or None."""
    from tracker import liquipedia
    liquipedia.tours()
    if _LPN["ts"] != liquipedia._CACHE["ts"]:
        _LPN.update(ts=liquipedia._CACHE["ts"], m={t["name"]: t for t in liquipedia._CACHE["all"]})
    return _LPN["m"].get(name)


def tour_show(name: str, region: str, game: str = None) -> bool:
    """Is this a tournament to list? A real edition (on Liquipedia: 'PGL Major Singapore 2026', not the organiser
    'PGL' or the league 'VCT' added up over months) or one of this site's trackers; in India, only the games India
    plays (BGMI, PUBG Mobile, Free Fire, Valorant, PUBG)."""
    if not named_tour(name):
        return False
    lp = _lp_named(name)
    trk = next((e for e in _tracked_events("in") if e["name"] == name or e.get("tour") == name), None)
    if not lp and not trk:
        return False
    if region == "in":
        g = (trk or {}).get("game") or (lp or {}).get("game") or game or ""
        return g in INDIA_GAMES
    return True


def _tracked_events(region: str) -> list:
    """This site's own tournament trackers (/e/<key>/) that are running: CEGC, PIC ... with their numbers (30 s)."""
    if region != "in":
        return []
    if time.time() - _TRK["ts"] < 30:
        return _TRK["v"]
    out = []
    try:
        for key, pr in list(events.PRESETS.items()):
            if pr.get("ended") or not events.get(key) or (pr.get("game") or "") not in INDIA_GAMES | {""}:
                continue
            with store.reading():
                c = events._db()
                pk = c.execute("SELECT ts, total, official, watch FROM ev_ticks WHERE event=? ORDER BY total DESC LIMIT 1", (key,)).fetchone()
                nw = c.execute("SELECT ts, total FROM ev_ticks WHERE event=? ORDER BY ts DESC LIMIT 1", (key,)).fetchone()
            live = bool(nw and time.time() - nw[0] < 300 and nw[1])
            out.append({"name": pr.get("name") or key.upper(), "game": pr.get("game") or "", "url": f"/e/{key}/",
                        "tracked": True, "viewers": nw[1] if live else 0, "live": live, "lp": bool(pr.get("lp")),
                        "tour": pr.get("tour"), "start": pr.get("start"), "end": pr.get("end"),
                        "peak": pk[1] if pk else 0, "peak_at": pk[0] if pk else None, "art": tour_art(pr.get("game") or "")})
    except Exception as e:
        print(f"Tracked events: {str(e)[:100]}")
    _TRK.update(ts=time.time(), v=out)
    return out


def tour_tag(n: str) -> str:
    """One word naming an event: 'PUBG Mobile Global Championship 2026' and 'PMGC 2026' are both 'pmgc'."""
    n = next((nm for rx, nm, _ in _T_RX if rx.search(n or "")), n)
    return (_norm(n).split() or [""])[0]


def tours_overview(region: str = "global") -> dict:
    """The esports page's tournament table (Esports Charts style): every real tournament on now or in the last 3
    days, this site's trackers among them (India), with the same columns for all: watching now, peak, hours
    watched, dates; then the ones on now with no stream seen yet, and the next two weeks. Organisers, leagues added
    up over months and '<game> tournaments' buckets are not listed (tour_show); India lists India's games only."""
    from tracker import liquipedia
    region = _region(region)
    lv = _live_part(None, region)
    live = {k: t for k, t in lv["_tours"].items()}
    t3 = time.time() - 3 * 86400
    today = datetime.now(events.REPORT_TZ).date().isoformat()
    with store.reading():
        c = _db()
        rec = {r[0]: r for r in c.execute("SELECT tour, peak, peak_at, first_ts, last_ts, hw FROM sc_tour WHERE region=? AND last_ts>=?",
                                          (region, t3))}
    rows = []
    for name in set(live) | set(rec):
        t, r = live.get(name), rec.get(name)
        info = _lp_named(name) or {}
        g = info.get("game") or (max(t["games"], key=t["games"].get) if t else "") or ""
        if not tour_show(name, region, g):
            continue
        rows.append({"name": name, "slug": slug(name), "game": g, "art": tour_art(g), "viewers": t["viewers"] if t else 0,
                     "streams": len(t["streams"]) if t else 0, "live": bool(t),
                     "peak": max(r[1] if r else 0, t["viewers"] if t else 0), "peak_at": r[2] if r else None,
                     "hw": round(r[5]) if r else 0, "start": info.get("start"), "end": info.get("end"),
                     "done": bool(info.get("end") and info["end"] < today and not t), "liquipedia": info.get("url")})
    have0 = {x["name"] for x in rows}
    with store.reading():
        allt = {r[0]: r for r in _db().execute("SELECT tour, peak, peak_at, first_ts, last_ts, hw FROM sc_tour WHERE region=?", (region,))}
    for t in liquipedia.active():          # on now, streamed earlier but not in the last 3 days: still a row with its numbers
        r = allt.get(t["name"])
        if not r or t["name"] in have0 or t["status"] != "ongoing" or not tour_show(t["name"], region, t["game"]):
            continue
        rows.append({"name": t["name"], "slug": slug(t["name"]), "game": t["game"], "art": tour_art(t["game"]), "viewers": 0,
                     "streams": 0, "live": False, "peak": r[1], "peak_at": r[2], "hw": round(r[5] or 0), "start": t.get("start"),
                     "end": t.get("end"), "done": False})
        have0.add(t["name"])
    trk = [dict(e) for e in _tracked_events(region)]
    for e in trk:                        # this site's own tracker is the same event: one row, best of both numbers
        same = [x for x in rows if x["name"] in (e["name"], e.get("tour")) or
                (not e.get("lp") and tour_tag(x["name"]) == tour_tag(e["name"]))]
        for x in same:
            rows.remove(x)
            e["game"] = e.get("game") or x["game"]
            e["start"], e["end"] = e.get("start") or x.get("start"), e.get("end") or x.get("end")
            e["peak"] = max(e.get("peak") or 0, x["peak"])
            e["hw"] = max(e.get("hw") or 0, x["hw"])
            if x["live"] and x["viewers"] > (e["viewers"] if e["live"] else 0):
                e["viewers"], e["live"] = x["viewers"], True
            e["streams"] = max(e.get("streams") or 0, x["streams"])
            e["slug"] = x["slug"]
            if _lp_named(x["name"]) and len(x["name"]) > len(e["name"]):
                e["name"] = x["name"]                 # 'CEGC' tracker shows as its edition, 'CEGC 2026' (26 Nov)
        e["art"] = tour_art(e["game"]) if e.get("game") else e.get("art")
        e.setdefault("hw", 0)
        e.setdefault("streams", 0)
        e["done"] = False
    rows = trk + rows
    rows.sort(key=lambda x: (-(x["peak"] or 0), -(x["viewers"] or 0)))
    rows.sort(key=lambda x: (-(x["peak"] or 0), -(x["viewers"] or 0)))
    have = {x["name"] for x in rows} | {x.get("tour") for x in rows if x.get("tour")}
    tags = {tour_tag(e["name"]) for e in trk if not e.get("lp")}   # a hand-made tracker covers its edition's name too
    other, upcoming = [], []
    soon = (datetime.now(events.REPORT_TZ).date() + timedelta(days=14)).isoformat()
    act = {t["id"] for t in liquipedia.active()}
    for t in liquipedia.tours():
        if t["name"] in have or tour_tag(t["name"]) in tags or not tour_show(t["name"], region, t["game"]):
            continue
        row = {"name": t["name"], "slug": slug(t["name"]), "game": t["game"], "art": tour_art(t["game"]), "start": t["start"],
               "end": t["end"], "liquipedia": t["url"]}
        if t["id"] in act and (t["status"] == "ongoing" or (t.get("start") or "9") <= today <= (t.get("end") or today)):
            other.append(row)
        elif t["status"] == "upcoming" and t.get("start") and today < t["start"] <= soon:
            upcoming.append(row)
        have.add(t["name"])
    upcoming.sort(key=lambda x: x["start"])
    return {"tracked": [], "tournaments": rows, "ongoing_no_streams": other[:60], "upcoming": upcoming[:30],
            "live": sum(1 for x in rows if x["live"])}


def tour_name(sl: str):
    """The tournament behind a URL slug."""
    from tracker import liquipedia
    for t in liquipedia.active() + liquipedia.tours():
        if slug(t["name"]) == sl:
            return t["name"]
    with store.reading():
        for (n,) in _db().execute("SELECT DISTINCT tour FROM sc_tour"):
            if slug(n) == sl:
                return n
    return None


def tour_data(name: str, region: str = "global") -> dict:
    """One tournament, every channel broadcasting or co-streaming it added up: watching now, its peak with all of
    them at once, today's line, peak by day, hours watched, every channel's own peak, and languages."""
    region = _region(region)
    lv = _live_part(None, region)
    live = sorted((x for x in lv["_live"] if x.get("tour") == name), key=lambda x: -x["viewers"])
    d0 = datetime.combine(datetime.now(events.REPORT_TZ).date(), datetime.min.time(), events.REPORT_TZ).timestamp()
    reg = f"tour:{region}"
    with store.reading():
        c = _db()
        tot = c.execute("SELECT peak, peak_at, first_ts, last_ts, hw FROM sc_tour WHERE tour=? AND region=?", (name, region)).fetchone()
        today = c.execute("SELECT ts, viewers FROM sc_reg WHERE region=? AND game=? AND ts>=? ORDER BY ts", (reg, name, d0)).fetchall()
        days = c.execute("""SELECT date(ts + 19800, 'unixepoch') d, MAX(viewers), COUNT(*) FROM sc_reg WHERE region=? AND game=?
                            GROUP BY d ORDER BY d""", (reg, name)).fetchall()
        ch = c.execute(f"""SELECT t.sid, MAX(t.peak), SUM(t.hw), SUM(t.mins), COUNT(DISTINCT t.day), c.name, c.logo, c.platform,
                           c.url, c.country, c.language FROM sc_tour_ch t LEFT JOIN sc_channels c ON c.sid=t.sid
                           WHERE t.tour=? {"AND t.india=1" if region == "in" else ""} GROUP BY t.sid ORDER BY 2 DESC LIMIT 300""",
                       (name,)).fetchall()
    nowv = sum(x["viewers"] for x in live)
    pk = max((tot[0] if tot else 0), nowv)
    step = max(1, len(today) // 600)
    langs = {}
    for r in ch:
        lg = (r[10] or "").split("-")[0].lower() or "unknown"
        langs[lg] = langs.get(lg, 0) + (r[2] or 0)
    info = tournament_info(name) or {}
    g = info.get("game") or (live[0]["game"] if live else "")
    ev = next((e for e in _tracked_events("in") if e["name"].lower() in name.lower() or name.lower() in e["name"].lower()), None)
    trk = {"url": ev["url"], "name": ev["name"]} if ev else None
    if ev:
        # this site's own tracker of the event (official channels + every watch party, curated lists) knows it best:
        # its game (CEGC is BGMI, not Liquipedia's 'PUBG Mobile') and its peak (23 Nov: 48,736 here vs 1.17 lakh there)
        g = ev.get("game") or g
        if (ev.get("peak") or 0) > (pk or 0):
            pk, tot = ev["peak"], (ev["peak"], ev.get("peak_at")) + tuple(tot[2:] if tot else (None, None, None))
    return {"name": name, "slug": slug(name), "region": region, "game": g, "art": cat_art(g) if g else "",
            "liquipedia": info.get("url"), "start": info.get("start"), "end": info.get("end"), "status": info.get("status"),
            "now": nowv, "live_count": len(live), "peak": pk, "peak_at": tot[1] if tot else None,
            "peak_today": max([v for _, v in today] + [nowv]) if today or nowv else 0,
            "hw": round(tot[4] or 0) if tot else 0, "first_ts": tot[2] if tot else None, "last_ts": tot[3] if tot else None,
            "series": [[a_, b_] for a_, b_ in today[::step]], "days": [{"day": d, "peak": v} for d, v, _ in days],
            "live": [{"sid": x["sid"], "name": x["name"], "platform": x["platform"], "url": x["url"], "logo": _logo(x),
                      "title": x.get("title") or "", "viewers": x["viewers"], "language": x.get("language") or "",
                      "country": x.get("country") or ""} for x in live[:200]],
            "channels": [{"sid": r[0], "peak": r[1] or 0, "hw": round(r[2] or 0), "hours": round((r[3] or 0) / 60, 1),
                          "days": r[4], "name": r[5] or r[0], "logo": _logo({"sid": r[0], "logo": r[6]}), "platform": r[7] or "",
                          "url": r[8] or "", "country": r[9] or "", "language": r[10] or "", "live": any(x["sid"] == r[0] for x in live)}
                         for r in ch],
            "languages": sorted(({"lang": k, "hw": round(v)} for k, v in langs.items() if v), key=lambda x: -x["hw"])[:12],
            "tracker": trk, "updated": time.time()}


def _tour_list(tours: dict, region: str) -> list:
    """Live tournaments, biggest first, with today's peak (IST day) from the per-scan totals."""
    d0 = datetime.combine(datetime.now(events.REPORT_TZ).date(), datetime.min.time(), events.REPORT_TZ).timestamp()
    with store.reading():
        pk = {r[0]: (r[1], r[2]) for r in _db().execute(
            "SELECT game, MAX(viewers), ts FROM sc_reg WHERE region=? AND ts>=? GROUP BY game", (f"tour:{region}", d0))}
    out = []
    for t in tours.values():
        g = (_lp_named(t["name"]) or {}).get("game") or max(t["games"], key=t["games"].get)
        if not tour_show(t["name"], region, g):
            continue
        st = sorted(t["streams"], key=lambda s_: -s_["viewers"])
        out.append({"name": t["name"], "tslug": slug(t["name"]), "named": named_tour(t["name"]),
                    "game": g, "slug": slug(g), "art": tour_art(g), "viewers": t["viewers"],
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


def _kpis(c, region: str, sec: str, game, lv: dict, ct: bool = False) -> dict:
    """The headline numbers: watching now, live channels, today's peak and hours watched today (IST day; the US
    Central day on worldwide pages when ct)."""
    tbl, w, a, key = _scope(region, sec, game)
    d0 = datetime.fromtimestamp(time.time() - 86400, events.REPORT_TZ)          # the last 24 hours
    pk = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY viewers DESC LIMIT 1",
                   (key, d0.timestamp(), *a)).fetchone()
    # hours watched today: every scan's total x the time between scans (works the same for sections and tournaments)
    rows = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY ts", (key, d0.timestamp(), *a)).fetchall()
    hw = sum(v * min(rows[i + 1][0] - ts if i + 1 < len(rows) else SCENE_SEC, SCENE_SEC * 2) for i, (ts, v) in enumerate(rows)) / 3600
    air = None
    if sec == "esports":
        chans = sum(1 for (n,) in c.execute("SELECT DISTINCT game FROM sc_reg WHERE region=? AND ts>=?",
                                            (f"tour:{region}", d0.timestamp())) if tour_show(n, region))
    else:
        q = """SELECT COUNT(DISTINCT d.sid), SUM(d.mins) FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid
               WHERE d.day=?""" + (" AND COALESCE(c.india,1)=1" if region == "in" else "")
        args = [datetime.now(events.REPORT_TZ).strftime("%Y-%m-%d")]
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


_P30 = {"key": None, "m": {}}
_PB = {"day": None, "m": {}, "busy": False}


def _prev30() -> dict:
    """{sid: viewers} at the scan closest to 30 minutes ago (once per scan)."""
    k = _SCANMEM.get("ts")
    if _P30["key"] == k:
        return _P30["m"]
    _P30["key"] = k
    try:
        with store.reading():
            c = _db()
            t = c.execute("SELECT MAX(ts) FROM sc_samples WHERE ts<=?", ((k or time.time()) - 1800,)).fetchone()[0]
            _P30["m"] = dict(c.execute("SELECT sid, MAX(viewers) FROM sc_samples WHERE ts=? GROUP BY sid", (t,)).fetchall()) if t else {}
    except Exception as e:
        print(f"Live 30 min ago: {str(e)[:100]}")
    return _P30["m"]


def _pb_build(day):
    """Each channel's best day before today (the rankings' peak rule), over the last year, for 'new personal best'."""
    try:
        d0 = (datetime.now(events.REPORT_TZ).date() - timedelta(days=365)).strftime("%Y-%m-%d")
        with store.reading():
            m = dict(_db().execute("""SELECT sid, MAX(CASE WHEN COALESCE(mins,0)>=10 AND NOT (mins>=30 AND hw>0 AND peak > 8*hw*60/mins)
                THEN peak END) FROM sc_daily WHERE day>=? AND day<? GROUP BY sid HAVING COUNT(DISTINCT day)>=5""", (d0, day)).fetchall())
        _PB.update(day=day, m={s: v for s, v in m.items() if v})
    except Exception as e:
        print(f"Personal bests: {str(e)[:100]}")
    finally:
        _PB["busy"] = False


def personal_best(sid: str):
    """The channel's best peak before today, or None (not known yet / under 5 days of history)."""
    day = datetime.now(events.REPORT_TZ).strftime("%Y-%m-%d")
    if _PB["day"] != day and not _PB["busy"]:
        _PB["busy"] = True
        threading.Thread(target=_pb_build, args=(day,), daemon=True).start()
    return _PB["m"].get(sid) if _PB["day"] == day else None


def _norm30() -> dict:
    try:
        from tracker import ranks
        return ranks._R.get("rows") or {}
    except Exception:
        return {}


_EVT = re.compile(r"([A-Za-zÀ-ÿ0-9.'&\- ]{2,40}?)\s+(?:x|vs\.?|v)\s+([A-Za-zÀ-ÿ0-9.'&\- ]{2,40})", re.I)
_EVT_DROP = re.compile(r"\b(live|ao vivo|en vivo|en directo|watch ?along|watch ?party|reaction|stream|streaming|hoje|today|"
                       r"agora|now|full|match|highlights?|jogo|partida|campeonato|brasileir[aã]o|libertadores|"
                       r"premier league|la liga|serie a|ipl|odi|t20|test|final|semi|quarter)\b", re.I)


_EVT_STOP = {"com", "con", "imagens", "imagenes", "ao", "vivo", "en", "live", "e", "y", "and", "na", "no", "on", "in", "at",
             "asia", "world", "cup", "trophy", "league", "series", "champions"}


def _event_key(title: str):
    """('Atlético-MG x Corinthians', key) when a title names a match 'A x B' / 'A vs B', else None."""
    m = _EVT.search(re.sub(r"[|•·:\[\]()🔴⚽🏏#!]+", " | ", title or ""))
    if not m:
        return None
    a = _EVT_DROP.sub(" | ", m.group(1)).split("|")[-1].split()
    b = _EVT_DROP.sub(" | ", m.group(2)).split("|")[0].split()
    stop = lambda w: any(ch.isdigit() for ch in w) or w.lower() in _EVT_STOP
    for i in range(len(b)):                    # 'Palmeiras COM IMAGENS', 'Australia 3rd': the team ends there
        if stop(b[i]):
            b = b[:i]
            break
    for i in range(len(a) - 1, -1, -1):
        if stop(a[i]):
            a = a[i + 1:]
            break
    a, b = " ".join(a[-3:]), " ".join(b[:3])
    if len(a) < 2 or len(b) < 2 or a.isdigit() or b.isdigit():
        return None
    k = tuple(sorted(re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()) for t in (a, b)))
    if not all(k):
        return None
    return f"{a.strip()} x {b.strip()}", "|".join(k)


def _parties(live: list, mark: dict = None) -> list:
    """Watch parties live now, grouped by what they're watching: a tournament, or a match named in the title
    ('Atlético-MG x Corinthians: 6 streams, 182K')."""
    ev = {}
    for x in live:
        if x.get("tour"):
            name, key, kind = x["tour"], "t:" + x["tour"], "esports"
        else:
            if x.get("section") not in ("sports", "other", "just-chatting", "irl") and x.get("game") not in ("Sports", "Cricket", "Football"):
                continue
            e = _event_key(x.get("title") or "")
            if not e:
                continue
            name, key, kind = e[0], "m:" + e[1], "match"
        g = ev.setdefault(key, {"event": name, "kind": kind, "viewers": 0, "streams": 0, "game": x.get("game"), "top": []})
        if mark is not None:
            mark[x["sid"]] = (g["event"], kind)
        g["viewers"] += x["viewers"]
        g["streams"] += 1
        if len(g["top"]) < 4:
            g["top"].append({k: x.get(k) for k in ("sid", "platform", "name", "logo", "viewers", "url")})
    out = [g for g in ev.values() if g["kind"] == "esports" or g["streams"] >= 2 or g["viewers"] >= 5000]
    return sorted(out, key=lambda g: -g["viewers"])[:30]


def _common(lv: dict, region: str) -> dict:
    p30, R30 = _prev30(), _norm30()

    def row(x):
        r = {k: x.get(k) for k in ("sid", "platform", "name", "url", "logo", "game", "title", "viewers", "section", "peak")}
        r["prev"] = p30.get(x["sid"])                 # watching 30 minutes ago
        n = (R30.get(x["sid"]) or {}).get("avg_30d")
        r["norm"] = n if n and n >= 50 else None      # its usual audience: 30-day average live viewers
        pb = personal_best(x["sid"])
        r["pb"] = bool(pb and pb >= 100 and max(x.get("peak") or 0, x["viewers"]) > pb)
        r["was"] = pb if r["pb"] else None
        r["event"], r["ekind"] = ev.get(x["sid"], (None, None))
        return r
    ev = {}
    parties = _parties(lv["_live"], ev)
    return {"updated": lv["updated"], "fresh": lv["fresh"], "india_total": lv["region_total"],
            "live_total": lv["live_total"], "live_count": len(lv["_live"]), "now": lv["now"], "sections": lv["sections"],
            "platforms": [{"platform": k, "name": platforms.NAMES[k], "viewers": v}
                          for k, v in sorted(lv["_by_plat"].items(), key=lambda kv: -kv[1])],
            "categories": sorted(filter(shown, lv["_by_game"].values()), key=lambda g: -g["viewers"])[:200],
            "tournaments": _tour_list(lv["_tours"], region),
            "live": [row(x) for x in lv["_live"][:300]],
            "parties": parties}


def _sec(sec: str) -> str:
    return sec if sec in SECTION_NAMES else ""


def live_data(cat: str = "", region: str = "in", sec: str = "") -> dict:
    """The part of the page that moves every 2 seconds: KPIs, sections, categories, tournaments, live streams."""
    region, sec = _region(region), _sec(sec)
    game = category_name(cat) if cat else None
    lv = _live_part(game, region, sec)
    with store.reading():
        k = _kpis(_db(), region, sec, game, lv, ct=region == "global" and _CTD["ready"])   # worldwide: Central day
    return _with_full({**_common(lv, region), "kpis": k}, region, game, sec)


_DR = {}
_DRL = threading.Lock()
_DRK = {}
_CS = {}
_CSL = threading.Lock()


def _day_rows(c, d0: str, region: str, game):
    """Per channel and game since d0, for channel-games that reached RANK_MIN_PEAK viewers. Read once per scan and
    shared by the overview and every section; while a new scan's rows are being read, pages get the previous ones
    (21 Nov: the global read took minutes, every section page waited on it and timed out)."""
    k = (d0, region, game)
    hit = _DR.get(k)
    cur = _SCANMEM.get("ts")
    if hit and hit[2] == cur:
        return hit[1]
    if hit and len(hit[1]) > 20000:           # older scan and a big read: answer now, read the new one in the background
        if not _DRB.get(k):
            _DRB[k] = True
            threading.Thread(target=_day_rows_bg, args=(d0, region, game), daemon=True).start()
        return hit[1]
    with _DRL:
        lk = _DRK.setdefault(k, threading.Lock())
    with lk:
        hit = _DR.get(k)
        if hit and hit[2] == cur:
            return hit[1]
        return _day_rows_read(c, d0, region, game)


_DRB = {}


def _day_rows_bg(d0, region, game):
    try:
        with store.reading():
            _day_rows_read(_db(), d0, region, game)
    except Exception as e:
        print(f"Day rows: {str(e)[:80]}")
    finally:
        _DRB.pop((d0, region, game), None)


def _day_rows_read(c, d0: str, region: str, game):
    cur = _SCANMEM.get("ts")
    q = """SELECT d.sid, d.game, MAX(d.peak) peak, SUM(d.mins) mins, SUM(d.hw) hw, c.name, c.platform,
           c.url, c.logo, c.last_live FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid WHERE d.day >= ?"""
    q += " AND COALESCE(c.india, 1)=1" if region == "in" else ""
    rows = [dict(r) for r in (c.execute(q + " AND d.game = ? GROUP BY d.sid, d.game HAVING MAX(d.peak) >= ?",
                                        (d0, game, RANK_MIN_PEAK)) if game
                              else c.execute(q + " GROUP BY d.sid, d.game HAVING MAX(d.peak) >= ?", (d0, RANK_MIN_PEAK)))]
    for r in rows:                            # worked out once per scan, not on every page build
        r["_sec"] = section_of(r["game"])
        r["_bad"] = name_blocked(r["name"]) or not_in_game(r["name"], r["game"], r["sid"])
    for kk in [kk for kk, v in list(_DR.items()) if time.time() - v[0] > 3600]:
        _DR.pop(kk, None)
    _DR[(d0, region, game)] = (time.time(), rows, cur)
    return rows


def data(period: str = "today", cat: str = "", region: str = "in", sec: str = "") -> dict:
    """Everything a page shows: the overview (no cat/sec), a section (sec) or one game (cat), for India or the world."""
    period = period if period in PERIODS else "today"
    region, sec = _region(region), _sec(sec)
    game = category_name(cat) if cat else None
    T = [("start", time.time())]
    lv = _live_part(game, region, sec)
    T.append(("live", time.time()))
    blk, live = lv["_blk"], lv["_live"]
    today = datetime.now(events.REPORT_TZ).date()
    # "today" is the last 24 hours on every page and card (owner, 19 Nov: a calendar day starting at midnight showed
    # only the last hour after midnight and disagreed with the 24-hour rankings). Channel peaks come from the daily
    # rows of yesterday and today, as the rankings' 24h does; totals and the peak from the exact last 24 hours.
    d0 = (today - timedelta(days=max(1, PERIODS[period]))).strftime("%Y-%m-%d")
    tbl, w, a, key = _scope(region, sec, game)
    ctday = False
    with store.reading():
        c = _db()
        if ctday:
            cr = ct_rows(game)
            keep = {r[0] for r in sorted(cr, key=lambda r: -r[5])[:3000]} | {r[0] for r in sorted(cr, key=lambda r: -r[2])[:3000]}
            info = {}
            L = sorted(keep)
            for i in range(0, len(L), 900):
                part = L[i:i + 900]
                for r in c.execute(f"SELECT sid, name, platform, url, logo, last_live FROM sc_channels WHERE sid IN "
                                   f"({','.join('?' * len(part))})", part):
                    info[r[0]] = r
            rows = [{"sid": sid, "game": g, "peak": pk, "mins": mn, "hw": hw, "name": (info.get(sid) or [None] * 6)[1],
                     "platform": (info.get(sid) or [None] * 6)[2], "url": (info.get(sid) or [None] * 6)[3],
                     "logo": (info.get(sid) or [None] * 6)[4], "last_live": (info.get(sid) or [None] * 6)[5]}
                    for sid, g, pk, pa, mn, hw in cr if sid in keep]
        else:
            rows = _day_rows(c, d0, region, game)
        T.append(("daily_rows", time.time()))
        series = _series_any(c, tbl, w, a, key, period)
        T.append(("series", time.time()))
        daily = _daily(c, tbl, w, a, key)
        T.append(("daily", time.time()))
        p0 = time.time() - 86400 if period == "today" else \
            datetime.combine(today - timedelta(days=PERIODS[period]), datetime.min.time(), events.REPORT_TZ).timestamp()
        rt, rw, ra = _totals_sql(region)
        scans = c.execute(f"SELECT COUNT(*) FROM {rt} WHERE game=? AND ts>=?{rw}", (ALL, p0, *ra)).fetchone()[0] or 0
        T.append(("scans", time.time()))
        ck = (region, period, _SCANMEM.get("ts"))   # same for every section and game of a region: once per scan
        hit = _CS.get(ck)
        if hit and time.time() - hit[0] < 300:
            cstats = hit[1]
        else:
            with _CSL:
                hit = _CS.get(ck)
                if hit and time.time() - hit[0] < 300:
                    cstats = hit[1]
                else:
                    cstats = [dict(r) for r in c.execute(
                        f"SELECT game, SUM(viewers) s, MAX(viewers) pk FROM {rt} WHERE ts>=? AND game!=?{rw} GROUP BY game",
                        (p0, ALL, *ra))]
                    for kk in [kk for kk, v in list(_CS.items()) if time.time() - v[0] > 900]:
                        _CS.pop(kk, None)
                    _CS[ck] = (time.time(), cstats)
        T.append(("cstats", time.time()))
        tracked = c.execute("SELECT COUNT(*) FROM sc_channels" + (" WHERE COALESCE(india,1)=1" if region == "in" else "")
                            ).fetchone()[0]
        pk = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=? AND ts>=?{w} ORDER BY viewers DESC LIMIT 1",
                       (key, time.time() - SERIES_SEC[period], *a)).fetchone()
        T.append(("tracked_pk", time.time()))
        pk_all = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=?{w} ORDER BY viewers DESC LIMIT 1", (key, *a)).fetchone()
        T.append(("pk_all", time.time()))
        tour_day = [{"name": r[0], "tslug": slug(r[0]), "named": True, "peak": r[1], "at": r[2]} for r in c.execute(
            "SELECT game, MAX(viewers), ts FROM sc_reg WHERE region=? AND ts>=? GROUP BY game ORDER BY MAX(viewers) DESC LIMIT 80",
            (f"tour:{region}", p0)) if tour_show(r[0], region)][:20]
        T.append(("tours", time.time()))
        kp = _kpis(c, region, sec, game, lv, ct=ctday)
        T.append(("kpis", time.time()))
    if T[-1][1] - T[0][1] > 5:                # which step is slow (19 Nov: 20-40 s builds)
        print("Slow scene.data " + f"{region}:{sec}:{game}:{period} " + " ".join(f"{n}={b - a_:.1f}" for (_, a_), (n, b) in zip(T, T[1:])))
    ch, games = {}, {}
    for r in rows:
        if r["sid"] in blk or r.get("_bad") or (sec and sec != "esports" and r.get("_sec") != sec):
            continue
        g = games.get(r["game"])
        if g is None:
            g = games[r["game"]] = {"game": r["game"], "slug": slug(r["game"]), "hw": 0.0, "peak_stream": 0,
                                    "channels": 0, "art": cat_art(r["game"]), "section": r.get("_sec") or section_of(r["game"])}
        g["hw"] += r["hw"]
        g["peak_stream"] = max(g["peak_stream"], r["peak"])
        g["channels"] += 1
        if (r["peak"] or 0) < RANK_MIN_PEAK:  # tiny streams count in the totals above, not in the boards
            continue
        x = ch.setdefault(r["sid"], {"sid": r["sid"], "name": r["name"] or r["sid"], "platform": r["platform"] or "",
                                      "url": r["url"] or "", "logo": _logo({"sid": r["sid"], "logo": r["logo"]}),
                                      "peak": 0, "mins": 0.0, "hw": 0.0, "games": {}, "last_live": r["last_live"]})
        x["peak"] = max(x["peak"], r["peak"])
        x["mins"] += r["mins"]
        x["hw"] += r["hw"]
        x["games"][r["game"]] = x["games"].get(r["game"], 0) + r["hw"]
    board = []
    for x in ch.values():
        x["avg"] = round(x["hw"] * 60 / x["mins"]) if x["mins"] else 0
        x["game"] = max(x["games"], key=x["games"].get) if x["games"] else ""
        x["hw"], x["airtime_h"] = round(x["hw"]), round(x["mins"] / 60, 1)
        del x["games"], x["mins"]
        board.append(x)
    board.sort(key=lambda x: -x["hw"])
    with store.reading():
        prev = _prev_ranks(_db(), region, game, sec, period)
    for i, x in enumerate(board):
        x["rank"] = i + 1
        x["delta"] = (prev[x["sid"]] - x["rank"]) if x["sid"] in prev else None   # None = new in the ranking
        pb = personal_best(x["sid"])
        x["pb"] = bool(pb and pb >= 100 and x["peak"] > pb)                       # beat its best day today
        x["was"] = pb if x["pb"] else None
    for x in board:
        x["now"] = lv["_now"].get(x["sid"], 0)   # live right now (in any section), else last_live says when
    if sec == "esports":
        board = []                            # esports is ranked by tournament (tour_day), not by channel
    cat_period = [{"game": r["game"], "slug": slug(r["game"]), "avg": round(r["s"] / scans) if scans else 0, "peak": r["pk"],
                   "gaming": is_gaming(r["game"]), "section": section_of(r["game"]), "art": cat_art(r["game"])}
                  for r in cstats]
    if sec:
        cat_period = [x for x in cat_period if x["section"] == sec]
    return _with_full({**_common(lv, region), "kpis": kp, "period": period, "every": SCENE_SEC, "region": region,
            "sec": sec, "sec_name": SECTION_NAMES.get(sec, ""), "cat": cat if game else "", "cat_name": game or "",
            "peak": {"viewers": pk[1], "ts": pk[0]} if pk else None,
            "peak_all": {"viewers": pk_all[1], "ts": pk_all[0]} if pk_all else None,
            "series": series, "daily": daily, "board": board[:300], "tour_day": tour_day,
            "games": [{**g, "hw": round(g["hw"]), "rank": i + 1,
                       "delta": ((prev.get("__games__") or {})[g["game"]] - i - 1) if g["game"] in (prev.get("__games__") or {}) else None}
                      for i, g in enumerate(sorted(games.values(), key=lambda g: -g["hw"])[:60])],
            "events": ([] if region != "in" else         # tournaments are India events: India pages only
                       [e for e in _events() if e["state"] in ("live", "upcoming")] if not (game or sec)
                       else [e for e in _events() if game and e["game"] == game]),
            "history": game_history(game) if game else (game_history("BGMI") if sec == "esports" and region == "in" else []),
            "history_game": game or ("BGMI" if sec == "esports" and region == "in" else ""),
            "cat_period": sorted(cat_period, key=lambda x: -x["avg"]), "tracked": tracked,
            "langs": LANGS, "min": MIN_VIEWERS if region == "in" else GLOBAL_MIN,
            "keys": {p: bool(platforms._keys(p)) for p in ("kick", "twitch")}}, region, game, sec)


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
    key = (region, game, sec, period, args[0])   # the period before doesn't change: read once an hour
    hit = _PR.get(key)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    tot, gt = {}, {}
    for r in c.execute(q + " GROUP BY d.sid, d.game HAVING MAX(d.peak) >= ?", args + [RANK_MIN_PEAK]):
        if sec and sec != "esports" and section_of(r["game"]) != sec:
            continue
        tot[r["sid"]] = tot.get(r["sid"], 0) + (r["hw"] or 0)
        gt[r["game"]] = gt.get(r["game"], 0) + (r["hw"] or 0)
    out = {sid: i + 1 for i, (sid, _) in enumerate(sorted(tot.items(), key=lambda kv: -kv[1]))}
    out["__games__"] = {g: i + 1 for i, (g, _) in enumerate(sorted(gt.items(), key=lambda kv: -kv[1]))}
    if len(_PR) > 400:
        _PR.clear()
    _PR[key] = (time.time(), out)
    return out


_PR = {}


RANK_PERIODS = {"day": 1, "3d": 3, "week": 7, "month": 30, "3m": 91, "6m": 182, "1y": 365, "all": 3650}


_RB = {}          # rankings: raw per-channel-per-game rows for a date window, shared by every filter combination
_RB_LOCK = threading.Lock()


def _rank_base(d0: str, d1: str, current: bool) -> list:
    """sc_daily rows for days d0..d1 joined with their channel, cached (90 s while the window includes today,
    an hour for past windows). Game, platform, section, country and region filters are applied in memory, so
    changing a filter never touches the database."""
    key, now = ("base", d0, d1), time.time()
    hit = _RB.get(key)
    if hit and now - hit[0] < (300 if current else 3600):
        return hit[1]
    if hit and now - hit[0] < 3 * 3600:          # a bit old: answer now, refresh in the background (one at a time)
        if not _RB_BUSY.get(key):
            _RB_BUSY[key] = True

            def bg():
                try:
                    _rank_base_build(key, d0, d1)
                finally:
                    _RB_BUSY.pop(key, None)
            threading.Thread(target=bg, daemon=True).start()
        return hit[1]
    return _rank_base_build(key, d0, d1, current)


_RB_BUSY = {}
# Rankings leave out channel-game rows that never reached this many viewers at once. Since the GTA 6 sweep (every
# stream from 1 viewer) a 7- or 30-day window was millions of rows, copied and looped in Python on every rankings
# request; that kept the page builders busy and timed out category pages (21 Nov, measured on /admin/health).
RANK_MIN_PEAK = int(os.getenv("RANK_MIN_PEAK", "10"))


def _rank_base_build(key, d0, d1, current=None) -> list:
    with _RB_LOCK:
        hit = _RB.get(key)
        if current is not None and hit and time.time() - hit[0] < (300 if current else 3600):
            return hit[1]
        with store.reading():
            rows = [dict(r) for r in _db().execute(
                """SELECT d.sid, d.game, MAX(d.peak) peak, SUM(d.mins) mins, SUM(d.hw) hw, c.name, c.platform, c.url, c.logo,
                   c.country, COALESCE(c.india,1) india, c.last_live FROM sc_daily d LEFT JOIN sc_channels c ON c.sid=d.sid
                   WHERE d.day BETWEEN ? AND ? GROUP BY d.sid, d.game HAVING MAX(d.peak) >= ?""", (d0, d1, RANK_MIN_PEAK))]
        _RB[key] = (time.time(), rows)
        for k in [k for k, v in _RB.items() if isinstance(v, tuple) and time.time() - v[0] > 3 * 3600]:
            _RB.pop(k, None)
    return rows


def _rank_extra(metric: str, d0: str, d1: str, current: bool) -> dict:
    """Super Chats or views gained for a window, cached like _rank_base."""
    from tracker import ytextra
    key, now = (metric, d0, d1), time.time()
    hit = _RB.get(key)
    if hit and now - hit[0] < (300 if current else 3600):
        return hit[1]
    with _RB_LOCK:
        val = ytextra.window_superchats(d0, d1) if metric == "sc" else ytextra.window_views(d0, d1)
        _RB[key] = (time.time(), val)
    return val


def rankings(region="global", metric="hw", period="day", date="", cat="", country="", platform="", sec="", limit=100):
    """Leaderboard of channels for one day / the 7 or 30 days ending on `date` (IST), by hours watched, peak or
    average viewers, filtered by game, section, streamer country and platform, with each channel's move against the
    period before."""
    region = _region(region)
    metric = metric if metric in ("hw", "peak", "avg", "hours", "sc", "vg") else "hw"
    today = datetime.now(events.REPORT_TZ).date()
    try:
        end = min(datetime.strptime(date, "%Y-%m-%d").date(), today) if date else today
    except ValueError:
        end = today
    n = (end - end.replace(month=1, day=1)).days + 1 if period == "ytd" else RANK_PERIODS.get(period, 1)
    game = category_name(cat) if cat else None
    sec = _sec(sec)
    ctry = country_of(country) if country else None

    def window(e):
        s_ = e - timedelta(days=n - 1)
        args = [s_.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")]
        rows = _rank_base(args[0], args[1], e >= today)       # cached; every filter below runs in memory
        out, games, ctrs = {}, {}, {}
        blk = blocked()
        secs, cts = {}, {}
        tot = {}                              # each channel's hours watched in the period, every game
        for r in rows:
            tot[r["sid"]] = tot.get(r["sid"], 0) + (r["hw"] or 0)
        for r in rows:
            sid, g = r["sid"], r["game"]
            if sid in blk or (region == "in" and not r["india"]) or (game and g != game) \
                    or (platform in platforms.NAMES and r["platform"] != platform):
                continue
            if sec:
                if g not in secs:
                    secs[g] = section_of(g)
                if secs[g] != sec:
                    continue
            ck = (r["country"], r["india"])
            if ck not in cts:
                cts[ck] = country_of(r["country"]) or (country_of("IN") if r["india"] else None)
            ct = cts[ck]
            if ct:
                ctrs[ct[0]] = ct[2]
            if ctry and (not ct or ct[0] != ctry[0]):
                continue
            x = out.get(sid)
            if x is None:
                x = out[sid] = {"sid": sid, "name": r["name"] or sid, "platform": r["platform"] or "",
                                "url": r["url"] or "", "logo": _logo({"sid": sid, "logo": r["logo"]}),
                                "country": ct[0] if ct else "", "country_name": ct[2] if ct else "",
                                "last_live": r["last_live"], "peak": 0, "mins": 0.0, "hw": 0.0, "g": {}}
            x["peak"] = max(x["peak"], r["peak"] or 0)
            x["mins"] += r["mins"] or 0
            x["hw"] += r["hw"] or 0
            x["g"][g] = x["g"].get(g, 0) + (r["hw"] or 0)
            games[g] = games.get(g, 0) + (r["hw"] or 0)
        # Super Chats and views gained come from their own tables (read only when ranking by them);
        # channels not live in the period still rank by them
        d0, d1 = args[0], args[1]
        extra = {"sc": {}, "vg": {}}
        if metric in ("sc", "vg"):
            extra[metric] = _rank_extra(metric, d0, d1, e >= today)
        if metric in ("sc", "vg") and extra[metric]:
            missing = [sid for sid in extra[metric] if sid not in out and sid not in blk]
            for i in range(0, len(missing), 500):
                part = missing[i:i + 500]
                with store.reading():
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
        if game and metric not in ("sc", "vg"):   # a game's board: channels that really streamed it in this period, a
            from tracker import ranks             # quarter of their watch time or more, or it's their game (owner, 25 Nov)
            ranked = [x for x in ranked if x["hw"] >= ranks.GAME_SHARE * tot.get(x["sid"], 0) or ranks.plays(x["sid"], game)]
        if not platform:                      # all platforms: the same creator on YouTube and Kick once (owner, 24 Nov)
            from tracker import ytextra
            ranked = ytextra.one_per_creator(ranked, metric)
        return ranked, games, ctrs
    cur, games, ctrs = window(end)
    prev = {x["sid"]: i + 1 for i, x in enumerate(window(end - timedelta(days=n))[0])}
    now = _live_part(None, "global")["_now"]
    for i, x in enumerate(cur):
        x["rank"] = i + 1
        x["delta"] = prev[x["sid"]] - x["rank"] if x["sid"] in prev else None
        x["now"] = now.get(x["sid"], 0)
    if not _RB.get("first"):
        with store.reading():
            _RB["first"] = _db().execute("SELECT MIN(day) FROM sc_daily").fetchone()[0]
    first = _RB["first"]
    return {"region": region, "metric": metric, "period": period, "date": end.strftime("%Y-%m-%d"),
            "start": (end - timedelta(days=n - 1)).strftime("%Y-%m-%d"), "first_day": first, "today": today.strftime("%Y-%m-%d"),
            "total": len(cur), "rows": cur[:limit],
            "categories": [{"game": g, "slug": slug(g), "hw": round(v)} for g, v in sorted(games.items(), key=lambda kv: -kv[1]) if shown(g)][:80],
            "countries": [{"code": k, "name": v} for k, v in sorted(ctrs.items(), key=lambda kv: kv[1])],
            "totals": {"hw": sum(x["hw"] + sum(a.get("hw") or 0 for a in x.get("also") or []) for x in cur),
                       "channels": sum(1 + len(x.get("also") or []) for x in cur)}, "money": "INR" if region == "in" else "USD"}


_DY = {}


def _daily(c, tbl, w, a, key, days: int = 30) -> list:
    """Per IST day for the last `days` days (cached until the next scan: 4-17 s under load on 19 Nov)."""
    k = (tbl, w, a, key, days, _SCANMEM.get("ts"))
    hit = _DY.get(k)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    v = _daily_read(c, tbl, w, a, key, days)
    if len(_DY) > 2000:
        _DY.clear()
    _DY[k] = (time.time(), v)
    return v


def _daily_read(c, tbl, w, a, key, days: int = 30) -> list:
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


CAT_RANGES = {"24h": -1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "ytd": None, "1y": 365, "all": 0}


_FIRST = {}
_REGDAY_OK = {}


def _first_ts(c, tbl, w, a, now):
    """When the region's records begin (a scan of the whole table, so remembered for an hour)."""
    k = (store.DB_PATH, tbl, a)
    hit = _FIRST.get(k)
    if hit and time.time() - hit[1] < 3600:
        return hit[0]
    v = c.execute(f"SELECT MIN(ts) FROM {tbl} WHERE 1=1{w}", a).fetchone()[0] or now
    _FIRST[k] = (v, time.time())
    return v


def backfill_reg_day():
    """Once: each day's peak per category from the per-scan totals already stored (sc_reg_day is then kept up by
    every scan). Runs in the background at start; until it finishes the category page reads the raw totals."""
    if store.kv_get("reg_day_v1"):
        _REGDAY_OK[store.DB_PATH] = True
        return
    try:
        for region, tbl, w, a in (("global", "sc_reg", " AND region=?", ("global",)), ("in", "sc_cat", "", ())):
            with store.reading():
                rows = _db().execute(f"""SELECT game, date(ts + 19800, 'unixepoch') d, MAX(viewers) FROM {tbl}
                                         WHERE 1=1{w} GROUP BY game, d""", a).fetchall()
            with store._lock:
                c = _db()
                c.executemany("""INSERT INTO sc_reg_day VALUES (?,?,?,?) ON CONFLICT(region, game, day) DO UPDATE SET
                                 peak=MAX(sc_reg_day.peak, excluded.peak)""", [(region, g, d, v) for g, d, v in rows])
                c.commit()
        store.kv_set("reg_day_v1", True)
        _REGDAY_OK[store.DB_PATH] = True
        print("Category daily peaks: filled in")
    except Exception as e:
        print(f"Category daily peaks: {str(e)[:120]}")


def categories(region: str = "global", limit: int = 60, rng: str = "1m") -> dict:
    """Games and categories like a player-count chart: watching now, change against 24 hours earlier, the last 48
    hours, daily peaks for 30 days, 30-day peak and hours watched. Trending = biggest rise in 24 hours among
    categories big enough to matter."""
    region = _region(region)
    lv = _live_part(None, region)
    cur = {g: dict(x) for g, x in lv["_by_game"].items() if g and g != ALL}
    top = sorted(cur.values(), key=lambda x: -x["viewers"])[:limit]
    names = [x["game"] for x in top]
    tbl, w, a = _totals_sql(region)
    now = time.time()
    rng = rng if rng in CAT_RANGES else "1m"
    today = datetime.now(events.REPORT_TZ).date()
    q = ",".join("?" * len(names)) or "NULL"
    with store.reading():
        c = _db()
        first = _first_ts(c, tbl, w, a, now)
        n = CAT_RANGES[rng]
        start_day = (date(today.year, 1, 1) if n is None else today - timedelta(days=n - 1) if n else
                     datetime.fromtimestamp(first, events.REPORT_TZ).date())
        t30 = datetime.combine(start_day, datetime.min.time(), events.REPORT_TZ).timestamp()
        d30 = start_day.strftime("%Y-%m-%d")
        ndays = (today - start_day).days + 1
        bd = max(1, -(-ndays // 30))                 # days per bar: at most 30 bars whatever the range
        span = bd * 86400
        if n == -1:                                  # last 24 hours: one bar per hour
            t30, span, ndays, bd = (int(now // 3600) - 23) * 3600, 3600, 1, 0
            d30 = datetime.fromtimestamp(t30, events.REPORT_TZ).strftime("%Y-%m-%d")
        ago = dict(c.execute(f"SELECT game, MAX(viewers) FROM {tbl} WHERE ts BETWEEN ? AND ?{w} AND game IN ({q}) GROUP BY game",
                             (now - 86400 - 900, now - 86400 + 900, *a, *names)).fetchall())
        h48 = c.execute(f"SELECT game, CAST(ts/3600 AS INT) h, MAX(viewers) FROM {tbl} WHERE ts>=?{w} AND game IN ({q}) GROUP BY game, h",
                        (now - 48 * 3600, *a, *names)).fetchall()
        if n == -1 or not _REGDAY_OK.get(store.DB_PATH):
            d = c.execute(f"SELECT game, CAST((ts-?)/? AS INT) dd, MAX(viewers) FROM {tbl} WHERE ts>=?{w} AND game IN ({q}) GROUP BY game, dd",
                          (t30, span, t30, *a, *names)).fetchall()
        else:                                        # from each day's stored peak: 30 rows a game instead of 21,600
            dk = {}
            for g_, dy, v in c.execute(f"SELECT game, day, peak FROM sc_reg_day WHERE region=? AND day>=? AND game IN ({q})",
                                       (region, d30, *names)):
                k_ = ((date.fromisoformat(dy) - start_day).days) // max(bd, 1)
                if v > dk.get((g_, k_), -1):
                    dk[(g_, k_)] = v
            d = [(g_, k_, v) for (g_, k_), v in dk.items()]
        hwq = """SELECT d.game, SUM(d.hw) FROM sc_daily d""" + (" JOIN sc_channels c ON c.sid=d.sid AND COALESCE(c.india,0)=1" if region == "in" else "")
        if n == -1:                                  # hours watched in 24 h: each reading stands for one scan interval
            hw = dict(c.execute(f"SELECT game, SUM(viewers) * {SCENE_SEC} / 3600.0 FROM {tbl} WHERE ts>=?{w} AND game IN ({q}) GROUP BY game",
                                (t30, *a, *names)).fetchall())
        else:
            hw = dict(c.execute(hwq + f" WHERE d.day>=? AND d.game IN ({q}) GROUP BY d.game", (d30, *names)).fetchall())
    s48, s30 = {}, {}
    for g, h, v in h48:
        s48.setdefault(g, {})[h] = v
    for g, dd, v in d:
        s30.setdefault(g, {})[dd] = v
    h0, nb = int((now - 48 * 3600) / 3600), (24 if CAT_RANGES[rng] == -1 else -(-ndays // bd))
    rows = []
    for x in top:
        g = x["game"]
        if not shown(g):
            continue
        b = ago.get(g)
        rows.append({"game": g, "slug": x["slug"], "art": x.get("art", ""), "section": x.get("section", ""),
                     "viewers": x["viewers"], "streams": x["streams"], "ago": b,
                     "change": round(100 * (x["viewers"] - b) / b, 1) if b else None,
                     "h48": [s48.get(g, {}).get(h, 0) for h in range(h0, h0 + 49)],
                     "d30": [s30.get(g, {}).get(k, 0) for k in range(nb)],
                     "peak30": max(s30.get(g, {}).values(), default=x["viewers"]), "hw30": round(hw.get(g) or 0)})
    for p in reversed(pinned()):            # pinned categories on top, even before their first live stream
        hit = next((r for r in rows if r["game"] == p), None)
        if hit:
            rows.remove(hit)
        else:
            hit = {"game": p, "slug": slug(p), "art": cat_art(p), "section": section_of(p), "viewers": 0, "streams": 0,
                   "ago": None, "change": None, "h48": [0] * 49, "d30": [0] * nb, "peak30": 0, "hw30": 0}
        hit["pinned"] = True
        rows.insert(0, hit)
    big = 300 if region == "in" else 2000
    trend = sorted([r for r in rows if r["change"] is not None and r["viewers"] >= big and (r["ago"] or 0) >= big / 4],
                   key=lambda r: -r["change"])[:5]
    return {"region": region, "updated": lv.get("updated"), "since": first, "rows": rows, "range": rng,
            "bar_days": bd, "start": d30, "days": ndays,
            "trending": [r["game"] for r in trend if r["change"] > 0]}


def category_months(game: str, region: str = "global") -> dict:
    """One category month by month: average watching (hours watched / hours tracked), gain on the month before,
    peak, hours watched; plus a last-30-days row and the all-time peak."""
    region = _region(region)
    tbl, w, a = _totals_sql(region)
    now = time.time()
    with store.reading():
        c = _db()
        first = c.execute(f"SELECT MIN(ts) FROM {tbl} WHERE game=?{w}", (game, *a)).fetchone()[0]
        if not first:
            return {"game": game, "months": [], "peak_all": None}
        pk = c.execute(f"SELECT ts, viewers FROM {tbl} WHERE game=?{w} ORDER BY viewers DESC LIMIT 1", (game, *a)).fetchone()
        mm = c.execute(f"SELECT strftime('%Y-%m', ts+19800, 'unixepoch') m, MAX(viewers), AVG(viewers) FROM {tbl} WHERE game=?{w} GROUP BY m",
                       (game, *a)).fetchall()
        mp, ma = {r[0]: r[1] for r in mm}, {r[0]: r[2] for r in mm}
        hwq = "SELECT substr(d.day,1,7) m, SUM(d.hw) FROM sc_daily d" + (" JOIN sc_channels c ON c.sid=d.sid AND COALESCE(c.india,0)=1" if region == "in" else "")
        mh = dict(c.execute(hwq + " WHERE d.game=? GROUP BY m", (game,)).fetchall())
        d30 = (datetime.now(events.REPORT_TZ).date() - timedelta(days=29)).strftime("%Y-%m-%d")
        h30 = c.execute(hwq.replace("substr(d.day,1,7) m, ", "") + " WHERE d.game=? AND d.day>=?", (game, d30)).fetchone()[0] or 0
        p30 = c.execute(f"SELECT MAX(viewers) FROM {tbl} WHERE game=? AND ts>=?{w}", (game, now - 30 * 86400, *a)).fetchone()[0] or 0
    out = []
    for m in sorted(set(mp) | set(mh)):
        y, mo = int(m[:4]), int(m[5:])
        start = datetime(y, mo, 1, tzinfo=events.REPORT_TZ).timestamp()
        end = datetime(y + (mo == 12), mo % 12 + 1, 1, tzinfo=events.REPORT_TZ).timestamp()
        hours = max(1.0, (min(end, now) - max(start, first)) / 3600)
        hw_ = mh.get(m) or 0
        out.append({"month": m, "avg": round(hw_ / hours) if hw_ else round(ma.get(m) or 0), "peak": mp.get(m) or 0, "hw": round(hw_),
                    "partial": start < first or end > now})
    out.reverse()                                  # newest first
    for i, r in enumerate(out):
        prev = out[i + 1]["avg"] if i + 1 < len(out) else None
        r["gain"] = r["avg"] - prev if prev else None
        r["pct"] = round(100 * (r["avg"] - prev) / prev, 2) if prev else None
    hrs30 = max(1.0, (now - max(now - 30 * 86400, first)) / 3600)
    last30 = {"avg": round(h30 / hrs30), "peak": p30, "hw": round(h30)}
    return {"game": game, "months": out, "last30": last30, "since": first,
            "peak_all": {"viewers": pk[1], "ts": pk[0]} if pk else None}


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


_SIDX = {"ts": 0, "rows": [], "games": [], "busy": False}
SEARCH_EVERY = 300


def _search_build():
    """Everything search looks at, in memory: every channel's name (and its last stream title if it was live in the
    last 30 days), its best peak and the game names. Rebuilt every 5 minutes in the background from a read-only
    connection, so a search is a scan of a list (milliseconds), not a database query per keystroke."""
    if _SIDX["busy"]:
        return
    _SIDX["busy"] = True
    try:
        t30 = time.time() - 30 * 86400
        with store.reading():
            c = _db()
            peak = dict(c.execute("SELECT sid, MAX(peak) FROM sc_daily GROUP BY sid").fetchall())
            rows = []
            for r in c.execute("SELECT sid, name, platform, url, logo, last_live, game, title, COALESCE(india,1) FROM sc_channels"):
                if not r[1]:
                    continue
                recent = (r[5] or 0) >= t30
                rows.append((r[0], r[1], r[1].lower(), (r[7] or "").lower() if recent else "", r[2], r[3], r[4], r[5],
                             r[6], r[7] if recent else "", r[8], peak.get(r[0]) or 0))
            d0 = (datetime.now(events.REPORT_TZ).date() - timedelta(days=120)).strftime("%Y-%m-%d")
            games = [g for (g,) in c.execute("SELECT DISTINCT game FROM sc_daily WHERE day>=? AND game!=''", (d0,))]
        rows.sort(key=lambda x: -x[11])                  # biggest first, so the first matches are the ones to show
        _SIDX.update(rows=rows, games=sorted(set(games) | {g for g, _ in GAMES}), ts=time.time())
    except Exception as e:
        print(f"Search index: {str(e)[:150]}")
    finally:
        _SIDX["busy"] = False


def search_index_loop():
    while True:
        _search_build()
        time.sleep(SEARCH_EVERY)


def search(q: str, region: str = "in", limit: int = 20) -> dict:
    """Any channel ever seen live whose name or recent stream title contains q (live titles included), plus matching
    games/categories. Channels whose name matches come first, biggest first."""
    q = (q or "").strip().lower()[:60]
    if len(q) < 2:
        return {"channels": [], "categories": []}
    region = _region(region)
    if not _SIDX["ts"]:
        _search_build()
    with _lock:
        live = {sid: x for sid, x in _LIVE.items()}
    by_name, by_title = [], []
    for r in _SIDX["rows"]:
        if region == "in" and not r[10]:
            continue
        lv = live.get(r[0])
        if q in r[2]:
            if len(by_name) < limit:
                by_name.append(r)
        elif len(by_title) < limit and (q in r[3] or lv and q in (lv.get("title") or "").lower()):
            by_title.append(r)
        if len(by_name) >= limit and len(by_title) >= limit:
            break
    have = {r[0] for r in by_name + by_title}
    for sid, x in live.items():                       # live right now but newer than the index
        if sid in have or region == "in" and not x.get("india", True):
            continue
        nm, tt = (x.get("name") or "").lower(), (x.get("title") or "").lower()
        if q in nm or q in tt:
            (by_name if q in nm else by_title).append((sid, x.get("name") or "", nm, tt, x.get("platform"), x.get("url"),
                                                       x.get("logo") or "", x.get("seen"), x.get("game"), x.get("title") or "",
                                                       1, x.get("viewers") or 0))
    out = []
    for r in by_name[:limit] + by_title[:limit]:
        lv = live.get(r[0]) or {}
        out.append({"sid": r[0], "name": r[1], "platform": r[4], "url": r[5], "logo": _logo({"sid": r[0], "logo": r[6]}),
                    "last_live": r[7], "game": lv.get("game") or r[8], "title": lv.get("title") or r[9],
                    "by": "name" if q in r[2] else "title", "peak": r[11], "now": lv.get("viewers") or 0})
    games = [g for g in _SIDX["games"] if q in g.lower() and g not in (ALL, "Other") and shown(g)][:8]
    return {"channels": out, "categories": [{"game": g, "slug": slug(g), "art": cat_art(g)} for g in games],
            "tournaments": search_tours(q, region)}


def search_tours(q: str, region: str = "global", limit: int = 6) -> list:
    """Tournaments whose name (or short tag: 'pmgc') matches q: this site's trackers (their own page), editions on
    Liquipedia and every tournament streamed here (its category page), plus Predict & Win when it fits."""
    from tracker import liquipedia
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    rp = "/india" if region == "in" else ""
    today = datetime.now(events.REPORT_TZ).date().isoformat()
    out, tags = [], set()
    hit = lambda n: q in n.lower() or q == tour_tag(n) or q.replace(" ", "") in n.lower().replace(" ", "")
    for key, pr in list(events.PRESETS.items()):
        nm = pr.get("name") or key.upper()
        if pr.get("ended") or not (hit(nm) or q == key) or (region == "in" and (pr.get("game") or "") not in INDIA_GAMES | {""}):
            continue
        g = pr.get("game") or ""
        out.append({"name": nm, "game": g, "art": tour_art(g), "url": f"/e/{key}/", "status": "tracked", "start": pr.get("start"),
                    "end": pr.get("end"), "rank": 0})
        tags.add(tour_tag(nm))
    with store.reading():
        rec = {r[0]: r[1] for r in _db().execute("SELECT tour, MAX(peak) FROM sc_tour WHERE region=? GROUP BY tour", (region,))}
    lp = {t["name"]: t for t in liquipedia.tours()}
    for name in set(lp) | set(rec):
        if not hit(name) or tour_tag(name) in tags:
            continue
        t = lp.get(name) or {}
        g = t.get("game") or ""
        if not tour_show(name, region, g):
            continue
        st = "upcoming" if t.get("status") == "upcoming" and (t.get("start") or "") > today else \
            "ended" if t.get("end") and t["end"] < today else "on"
        out.append({"name": name, "game": g, "art": tour_art(g), "url": f"{rp}/t/{slug(name)}", "status": st, "start": t.get("start"),
                    "end": t.get("end"), "peak": rec.get(name) or 0, "rank": {"on": 1, "upcoming": 2, "ended": 3}[st]})
    out.sort(key=lambda x: (x["rank"], -(x.get("peak") or 0), x["name"]))
    try:
        from tracker import pmgc
        if "predict" in q or q in ("pmgc", "pmgc 2026", "gauntlet", "predict & win"):
            out.insert(0, {"name": "PMGC Gauntlet: Predict & Win", "game": "PUBG Mobile", "art": tour_art("PUBG Mobile"),
                           "url": "/predict/pmgc", "status": "locked" if pmgc.closed() else "predict", "rank": -1})
    except Exception:
        pass
    return out[:limit]


def peak_ok(pk, hw, mins) -> bool:
    """The rankings' rule for a day's peak: 10+ minutes live, and not 8x+ that day's own average (a 5-minute spike or a
    viewbot burst is not a peak). Shared by the channel page and compare, so all three show the same peak."""
    return bool(pk) and not ((mins is not None and mins < 10) or (hw and mins and mins >= 30 and pk > 8 * hw * 60 / mins))


def channel(sid: str) -> dict:
    """One channel's analytics: now, today / 7 / 30 days / all time (peak, average, hours watched, hours live,
    days live), day by day for 30 days, and its viewers over the last 3 days."""
    with store.reading():
        c = _db()
        ch = c.execute("SELECT * FROM sc_channels WHERE sid=?", (sid,)).fetchone()
        if not ch:
            return {}
        days = c.execute("SELECT day, game, peak, peak_at, mins, hw FROM sc_daily WHERE sid=? ORDER BY day", (sid,)).fetchall()
        t3 = time.time() - 3 * 86400
        samp = c.execute("SELECT ts, MAX(viewers) FROM sc_samples WHERE sid=? AND ts>=? GROUP BY ts ORDER BY ts", (sid, t3)).fetchall()
    today = datetime.now(events.REPORT_TZ).date()
    now = _live_part(None, "global")["_now"].get(sid, 0)
    td = today.strftime("%Y-%m-%d")
    by = {}
    for r in days:
        z = by.setdefault(r["day"], {"day": r["day"], "peak": 0, "at": None, "mins": 0.0, "hw": 0.0, "games": {}})
        # a stream live right now counts from its first minutes (the rankings wait 10 minutes)
        ok = peak_ok(r["peak"], r["hw"], r["mins"]) or (now and r["day"] == td and (r["mins"] or 0) < 10 and r["peak"])
        if ok and r["peak"] > z["peak"]:
            z["peak"], z["at"] = r["peak"], r["peak_at"]
        z["mins"] += r["mins"] or 0
        z["hw"] += r["hw"] or 0
        z["games"][r["game"]] = z["games"].get(r["game"], 0) + (r["hw"] or 0)

    def agg(n):
        # today: today only; 7 / 30 days: the rankings' window (today and the n days before), so the numbers match
        d0 = (today - timedelta(days=0 if n == 1 else n)).strftime("%Y-%m-%d") if n else ""
        zs = [z for d, z in by.items() if d >= d0]
        mins, hw = sum(z["mins"] for z in zs), sum(z["hw"] for z in zs)
        g = {}
        for z in zs:
            for k, v in z["games"].items():
                g[k] = g.get(k, 0) + v
        return {"peak": max((z["peak"] for z in zs), default=0), "avg": round(hw * 60 / mins) if mins else 0,
                "hw": round(hw), "hours": round(mins / 60, 1), "days": len(zs),
                "games": [k for k, _ in sorted(g.items(), key=lambda kv: -kv[1])][:4]}
    step = max(1, len(samp) // 240)
    return {"sid": sid, "name": ch["name"], "platform": ch["platform"], "url": ch["url"],
            "logo": _logo({"sid": sid, "logo": ch["logo"]}), "title": ch["title"], "game": ch["game"],
            "country": (country_of(ch["country"]) or ("", 0, ""))[2] or ("India" if ch["india"] else ""),
            "country_code": (country_of(ch["country"]) or ("", 0, ""))[0] or ("IN" if ch["india"] else ""),
            "india_why": _why(dict(ch)),
            "profile": _profile(sid),
            "first_seen": ch["first_seen"], "last_live": ch["last_live"], "now": now,
            "periods": {"today": agg(1), "7d": agg(7), "30d": agg(30), "all": agg(0)},
            "days": [{"day": z["day"], "peak": z["peak"], "at": z["at"], "hours": round(z["mins"] / 60, 1),
                      "hw": round(z["hw"]), "avg": round(z["hw"] * 60 / z["mins"]) if z["mins"] else 0,
                      "game": max(z["games"], key=z["games"].get) if z["games"] else ""}
                     for d, z in sorted(by.items()) if d >= (today - timedelta(days=29)).strftime("%Y-%m-%d")],
            "recent": [[r[0], r[1]] for r in samp[::step]], "ranks": _ranks_of(sid), "linked": _linked(sid),
            **(_yt_extra(sid) if sid.startswith("yt:") else _other_extra(sid))}


def _profile(sid: str) -> dict:
    from tracker import profiles
    f, gone = profiles.followers(sid)
    return {"bio": profiles.bio(sid), "links": profiles.links(sid), "followers": f, "gone": bool(gone)}


def _why(ch: dict) -> str:
    """Why this channel counts as Indian or not, in words (owner, 23 Nov: 'on what basis did you add it?')."""
    try:
        ok, why = india_why({"sid": ch["sid"], "platform": ch["platform"], "title": ch.get("title") or "",
                             "name": ch.get("name") or "", "language": ch.get("language") or "", "game": ch.get("game") or "",
                             "tags": ch.get("tags") or ""}, _norm_country(ch.get("country")) if ch.get("country") else None,
                            india_known())
        return ("Indian: " if ok else "Not Indian: ") + why
    except Exception as e:
        return f"unknown ({str(e)[:60]})"


def _linked(sid: str) -> list:
    from tracker import ytextra
    try:
        return ytextra.linked(sid)
    except Exception:
        return []


def _ranks_of(sid: str) -> list:
    from tracker import ranks
    try:
        return ranks.for_channel(sid)
    except Exception:
        return []


def _other_extra(sid: str) -> dict:
    from tracker import ytextra
    try:
        return {"superchats": None, "top_superchats": [], "stats": None, "views": ytextra.views_series(sid)}
    except Exception:
        return {"superchats": None, "top_superchats": [], "stats": None}


def _yt_extra(sid: str) -> dict:
    from tracker import ytextra
    try:
        return {**ytextra.channel_extra(sid), "views": ytextra.views_series(sid)}
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
    with store.reading():
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
    for p in ("kick", "twitch"):                # the worldwide lists behind the Global page
        if not platforms._keys(p):
            continue
        errs = {}
        rows = list({r["vid"]: r for r in platform_global(p, errs)}.values())
        lines.append(f"{platforms.NAMES[p]} worldwide: {len(rows)} live, {sum(r['viewers'] for r in rows):,} watching" +
                     (", top " + ", ".join(f"{r['channel']} {r['viewers']:,}" for r in sorted(rows, key=lambda r: -r["viewers"])[:3]) if rows else ""))
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


# Changes whenever the rules for who is listed change, so saved ranking answers made under older rules are never shown.
import hashlib as _hl
RULES_V = _hl.md5(repr((sorted((k, sorted(v)) for k, v in GAME_NOT.items()), sorted(NAME_BLOCK), _NEWSNAME.pattern,
                        _G6NEWS.pattern, _G6NOT.pattern, _G6PLAY.pattern)).encode()).hexdigest()[:8]
