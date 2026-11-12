"""Top YouTube channels in every YouTube category and every game / topic (BGMI, PUBG Mobile, Free Fire, GTA V,
Cricket, News ...), in India and worldwide.

Goal: for each YouTube category (Music, Entertainment, Gaming, News & Politics ...) the site should know at least the
biggest FILL_TARGET (1,000) Indian channels. To be sure the top 1,000 really are the top, it keeps finding channels
until a category has FILL_TARGET x 1.5 Indian channels with numbers, then only tops up with newcomers.

Where channels come from (every 15 minutes, hungriest categories first):
  1. YouTube's India "most popular" chart per category (Data API, 1 unit per 50 videos, each category every 6 h).
     The category is known for certain: it's the chart's.
  2. YouTube's own channel search, many pages deep, with keywords per category in English and Indian languages
     (free: the website search, not the API allowance).
  3. Channels that big Indian channels link to on their Channels tab (free, website pages).
New channels get their numbers straight away (Data API, 1 unit per 50 channels) and then every day like the rest.
Indian = channel country India, or no country set and an Indian default language / mostly Indian-script name and
description (ytextra.looks_indian).
Check progress: python track.py scene catfill
"""
import os
import re
import time

from tracker import events, store, ytextra

TARGET = int(os.getenv("FILL_TARGET", "1000"))
CAND = int(TARGET * 1.5)
SEARCH_PAGES = int(os.getenv("FILL_SEARCH_PAGES", "24"))      # free search pages per run (20 channels each)
LINK_PAGES = int(os.getenv("FILL_LINK_PAGES", "40"))          # Channels tabs read per run
CHART_EVERY_H = 6
MAX_NEW = int(os.getenv("FILL_MAX_NEW", "3000"))              # new channels read per call (1 API unit per 50)

CAT_IDS = {v: k for k, v in ytextra.YT_CATS.items()}
QUERIES = {
    "Music": ["hindi songs", "punjabi songs", "tamil songs", "telugu songs", "bhojpuri songs", "haryanvi songs",
              "marathi songs", "kannada songs", "malayalam songs", "bollywood music", "bhajan", "indian music label",
              "indie music india", "gujarati songs", "rajasthani songs", "lofi hindi songs"],
    "Entertainment": ["hindi serial", "hindi web series", "bollywood news", "tamil serial", "telugu serial",
                      "hindi short film", "prank video hindi", "reaction video hindi", "dance video india",
                      "celebrity interview hindi", "kannada serial", "malayalam serial", "bengali serial"],
    "People & Blogs": ["hindi vlog", "family vlog india", "village vlog", "tamil vlog", "telugu vlogs", "couple vlog india",
                       "motivational video hindi", "daily vlog india", "kannada vlog", "malayalam vlog", "marathi vlog"],
    "Gaming": ["bgmi", "free fire india", "gta 5 hindi", "minecraft hindi", "gaming hindi", "tamil gaming",
               "telugu gaming", "mobile gaming india", "gta 6 india", "valorant india", "bgmi tamil", "free fire tamil"],
    "News & Politics": ["hindi news", "tamil news", "telugu news", "marathi news", "kannada news", "malayalam news",
                        "gujarati news", "punjabi news", "odia news", "bengali news india", "news live india",
                        "political analysis hindi", "assamese news"],
    "Comedy": ["comedy video hindi", "stand up comedy india", "funny video hindi", "tamil comedy", "telugu comedy",
               "comedy sketch india", "roast video india", "haryanvi comedy", "bhojpuri comedy"],
    "Film & Animation": ["hindi dubbed movies", "south indian movies hindi", "cartoon hindi", "animation hindi",
                         "tamil movies", "telugu movies", "movie review hindi", "kids cartoon hindi", "horror stories hindi",
                         "moral stories hindi"],
    "Education": ["upsc preparation", "ssc exam", "neet preparation", "jee preparation", "class 10 hindi medium",
                  "english speaking hindi", "gk in hindi", "coding in hindi", "current affairs hindi",
                  "stock market hindi", "personal finance hindi", "tnpsc", "appsc", "study tamil"],
    "Howto & Style": ["cooking hindi", "indian recipes", "makeup tutorial hindi", "fashion india", "fitness hindi",
                      "mehndi design", "diy hindi", "tamil cooking", "telugu cooking", "home remedies hindi",
                      "kannada cooking", "malayalam cooking", "yoga hindi"],
    "Sports": ["cricket hindi", "cricket news india", "kabaddi", "wwe hindi", "football india", "cricket tamil",
               "sports news hindi", "ipl analysis", "cricket telugu"],
    "Science & Technology": ["tech hindi", "mobile review hindi", "tech tamil", "tech telugu", "science hindi",
                             "gadgets india", "ai tools hindi", "unboxing hindi", "tech kannada"],
    "Travel & Events": ["travel vlog india", "travel hindi", "tamil travel vlog", "bike ride india", "temple travel",
                        "foreign travel hindi", "telugu travel vlog", "malayalam travel vlog"],
    "Pets & Animals": ["dog video india", "pets hindi", "animals hindi", "birds india", "animal rescue india",
                       "dairy farm india"],
    "Autos & Vehicles": ["car review hindi", "bike review hindi", "modified cars india", "truck driver vlog india",
                         "electric scooter india", "tractor video india"],
    "Nonprofits & Activism": ["satsang", "spiritual hindi", "pravachan", "ngo india", "social awareness hindi",
                              "katha live"],
}
# worldwide keywords per YouTube category (searched in many countries)
WORLD_QUERIES = {
    "Music": ["official music video", "music", "hip hop", "pop music", "kpop", "latin music", "rap", "reggaeton", "afrobeats",
              "rock music", "edm", "lofi", "gospel music", "country music", "jpop", "arabic music", "funk brasileiro"],
    "Entertainment": ["entertainment", "tv show", "reality show", "celebrity", "prank", "challenge video", "reaction",
                      "late night show", "trailer", "talk show", "dance"],
    "People & Blogs": ["vlog", "family vlog", "daily vlog", "lifestyle", "storytime", "motivation", "couple vlog", "shorts creator"],
    "Gaming": ["gaming", "gameplay", "lets play", "game walkthrough", "speedrun", "esports", "mobile gaming", "game review"],
    "News & Politics": ["news", "breaking news", "news live", "politics", "world news", "noticias", "berita", "haber"],
    "Comedy": ["comedy", "stand up comedy", "funny videos", "sketch comedy", "parody", "memes"],
    "Film & Animation": ["animation", "cartoon", "movies", "short film", "anime", "kids cartoon", "movie recap", "3d animation"],
    "Education": ["education", "science explained", "history documentary", "learn english", "math tutorial", "finance",
                  "investing", "study with me", "language learning", "kids learning"],
    "Howto & Style": ["cooking", "recipes", "makeup tutorial", "fashion", "diy", "fitness", "home workout", "crafts",
                      "skincare", "hair tutorial"],
    "Sports": ["football highlights", "nba highlights", "cricket", "ufc", "wwe", "formula 1", "tennis", "boxing", "sports news"],
    "Science & Technology": ["tech review", "smartphone review", "unboxing", "pc build", "ai tools", "science", "space",
                             "engineering", "gadgets"],
    "Travel & Events": ["travel vlog", "travel guide", "street food tour", "van life", "backpacking", "city walk"],
    "Pets & Animals": ["dogs", "cats", "animals", "wildlife", "pet care", "animal rescue", "farm animals"],
    "Autos & Vehicles": ["car review", "supercars", "motorcycle", "car detailing", "trucks", "ev review", "car restoration"],
    "Nonprofits & Activism": ["charity", "nonprofit", "sermon", "church live", "documentary activism", "islamic lecture"],
}
REGIONS = ["IN", "US", "BR", "ID", "MX", "PH", "GB", "JP", "KR", "DE", "FR", "TR", "VN", "TH", "SA", "PK", "BD", "NG",
           "CA", "AU", "ES", "IT", "RU", "EG", "AR", "CO"]
SEARCH_GL = ["US", "IN", "BR", "ID", "PH", "GB", "MX", "TR", "VN", "TH", "JP", "KR", "DE", "FR", "SA", "PK"]
NOT_GAMES = {"Other", "Just Chatting", "IRL", "Podcast / Talk"}
WORLD_MIN_SUBS = int(os.getenv("FILL_WORLD_MIN_SUBS", "50000"))   # worldwide finds kept only from this size up
WORLD_ON = os.getenv("FILL_WORLD", "1") != "0"
_S = {}           # (query, gl) -> {"page": n, "token": continuation} (memory only; restarts begin again)


def games() -> list:
    """Subcategories: every game and topic the site classifies streams into (BGMI, PUBG Mobile, Free Fire, GTA V,
    Cricket, News, Devotional ...), from scene.GAMES."""
    from tracker import scene
    return [g for g in dict.fromkeys(g for g, _ in scene.GAMES) if g not in NOT_GAMES]


def groups() -> list:
    """[(scope, kind, name)]: scope 'in' (India) or 'world'; kind 'cat' (YouTube category) or 'game' (subcategory)."""
    out = [("in", "cat", c) for c in QUERIES] + [("in", "game", g) for g in games()]
    if WORLD_ON:
        out += [("world", "cat", c) for c in WORLD_QUERIES] + [("world", "game", g) for g in games()]
    return out


def counts() -> dict:
    """{(scope, kind, name): channels with numbers in the last 3 days} (India: Indian channels only)."""
    since = ytextra._day(time.time() - 3 * 86400)
    out = {g: 0 for g in groups()}
    with store._lock:
        c = ytextra._db()
        for kind, col in (("cat", "COALESCE(NULLIF(c.ytcat,''), c.topic)"), ("game", "c.game")):
            for scope, cond in (("in", "AND COALESCE(c.india,0)=1"), ("world", "")):
                for name, n in c.execute(
                        f"""SELECT {col} g, COUNT(*) FROM sc_channels c WHERE c.platform='youtube' {cond}
                            AND EXISTS (SELECT 1 FROM sc_chstats s WHERE s.sid=c.sid AND s.day>=?) GROUP BY g""", (since,)):
                    if (scope, kind, name) in out:
                        out[(scope, kind, name)] = n
    return out


def _known(cids: list) -> set:
    if not cids:
        return set()
    sids = ["yt:" + c for c in cids]
    with store._lock:
        c = ytextra._db()
        return {r[0][3:] for i in range(0, len(sids), 500)
                for r in c.execute(f"SELECT sid FROM sc_channels WHERE sid IN ({','.join('?' * len(sids[i:i + 500]))})", sids[i:i + 500])}


def admit(found: dict, scope: str = "in") -> int:
    """found: {channel id: (category or '', game or '')}. Adds channels the site doesn't know and reads their numbers
    now. Kept: Indian channels; worldwide (scope 'world') also any channel with WORLD_MIN_SUBS+ subscribers."""
    found = {k: (v if isinstance(v, tuple) else (v or "", "")) for k, v in found.items()}
    known = _known(list(found))
    new = [cid for cid in found if cid not in known][:MAX_NEW]
    if not new:
        return 0
    now = time.time()
    with store._lock:
        c = ytextra._db()
        c.executemany("""INSERT OR IGNORE INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                         country, india, language, tracked, ytcat) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
                      [("yt:" + cid, "youtube", "", f"https://www.youtube.com/channel/{cid}", "", now, None, "", found[cid][1],
                        None, 0, "", found[cid][0]) for cid in new])
        c.commit()
    if os.getenv("YOUTUBE_API_KEY") and events.yt_quota_left(.6):
        got = ytextra._sane(ytextra.channel_stats(new))
        ytextra.save_stats(got, {cid: found[cid][0] for cid in new})
        # keep what this job is for; the rest would cost a reading every day for nothing
        sids = ["yt:" + c for c in new]
        big = {"yt:" + cid for cid, (s, v, n) in got.items() if (s or 0) >= WORLD_MIN_SUBS} if scope == "world" else set()
        with store._lock:
            c = ytextra._db()
            for i in range(0, len(sids), 500):
                part, q = sids[i:i + 500], ",".join("?" * len(sids[i:i + 500]))
                drop = [r[0] for r in c.execute(f"""SELECT sid FROM sc_channels WHERE sid IN ({q}) AND COALESCE(india,0)=0
                                                    AND last_live IS NULL AND COALESCE(tracked,0)=0""", part) if r[0] not in big]
                if drop:
                    dq = ",".join("?" * len(drop))
                    for t in ("sc_chstats", "sc_intra", "sc_channels"):
                        c.execute(f"DELETE FROM {t} WHERE sid IN ({dq})", drop)
            c.commit()
    with store._lock:
        return ytextra._db().execute(f"SELECT COUNT(*) FROM sc_channels WHERE sid IN ({','.join('?' * min(len(new), 900))})",
                                     ["yt:" + x for x in new[:900]]).fetchone()[0]


def charts(hungry: list) -> int:
    """YouTube's most-popular videos per category and country -> their channels, category known. India every
    6 hours, other countries daily (1 API unit per 50 videos)."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key or not events.yt_quota_left(.5):
        return 0
    last = store.kv_get("fill_chart_at") or {}
    found = {"in": {}, "world": {}}
    cats = [(s, n) for s, k, n in hungry if k == "cat" and n in CAT_IDS]
    jobs = [(s, "IN" if s == "in" else rg, n) for s, n in cats for rg in (["IN"] if s == "in" else REGIONS)]
    calls = 0
    for scope, rg, cat in jobs:
        k = f"{rg}:{cat}"
        if time.time() - last.get(k, 0) < (CHART_EVERY_H if rg == "IN" else 24) * 3600 or calls >= 120:
            continue
        last[k] = time.time()
        tok = ""
        for _ in range(4):                                  # a chart holds up to 200 videos
            calls += 1
            r = events._http.get("https://www.googleapis.com/youtube/v3/videos", timeout=15, params={
                "part": "snippet", "chart": "mostPopular", "regionCode": rg, "videoCategoryId": CAT_IDS[cat],
                "maxResults": 50, "pageToken": tok, "key": key})
            if r.status_code >= 400:                        # some categories have no chart in some countries
                break
            j = r.json()
            for it in j.get("items", []):
                cid = (it.get("snippet") or {}).get("channelId") or ""
                if cid.startswith("UC"):
                    found[scope].setdefault(cid, (cat, ""))
            tok = j.get("nextPageToken") or ""
            if not tok:
                break
    store.kv_set("fill_chart_at", last)
    return admit(found["in"], "in") + admit(found["world"], "world")


def _search_page(q: str, gl: str = "IN") -> list:
    """One page (about 20) of YouTube's channel search; continues where the last call for (q, gl) stopped."""
    st = _S.setdefault((q, gl), {"page": 0, "token": ""})
    ctx = {"client": {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": gl}}
    body = {"context": ctx, "continuation": st["token"]} if st["token"] else {"context": ctx, "query": q, "params": "EgIQAg=="}
    r = events._http.post("https://www.youtube.com/youtubei/v1/search?prettyPrint=false", json=body, timeout=12,
                          headers={"User-Agent": events._UA, "Content-Type": "application/json", "Origin": "https://www.youtube.com"})
    r.raise_for_status()
    j = r.json()
    cids = [ch.get("channelId") for ch in ytextra._walk(j, "channelRenderer", []) if (ch.get("channelId") or "").startswith("UC")]
    toks = [x.get("token") for x in ytextra._walk(j, "continuationCommand", []) if isinstance(x, dict) and x.get("token")]
    st["page"] += 1
    st["token"] = toks[-1] if toks else ""
    if not st["token"] or not cids:
        st["page"] = 99                                     # this query is used up
    return cids


def _queries(scope: str, kind: str, name: str) -> list:
    """[(query, gl)] for a group."""
    if kind == "cat":
        if scope == "in":
            return [(q, "IN") for q in QUERIES.get(name, [])]
        return [(q, gl) for q in WORLD_QUERIES.get(name, []) for gl in SEARCH_GL[:6]]
    base = [name, f"{name} gameplay", f"{name} live", f"{name} highlights", f"{name} tips"]
    if scope == "in":
        return [(q, "IN") for q in base + [f"{name} hindi", f"{name} tamil", f"{name} telugu", f"{name} india"]]
    return [(q, gl) for q in base for gl in SEARCH_GL]


def search(hungry: list) -> int:
    found, left = {"in": {}, "world": {}}, SEARCH_PAGES
    while left > 0:
        progressed = False
        for scope, kind, name in hungry:
            if left <= 0:
                break
            q = next(((q, gl) for q, gl in _queries(scope, kind, name) if _S.get((q, gl), {}).get("page", 0) < 25), None)
            if not q:                                       # 25 pages (~500 channels) per query and country is plenty
                continue
            try:
                for cid in _search_page(*q):
                    found[scope].setdefault(cid, ("", name if kind == "game" else ""))
            except Exception as e:
                print(f"Category fill search '{q[0]}': {str(e)[:80]}")
                _S.setdefault(q, {})["page"] = 99
            left -= 1
            progressed = True
        if not progressed:
            break
    return admit(found["in"], "in") + admit(found["world"], "world")


def links(hungry: list) -> int:
    """Channels listed on the Channels tab of the biggest channels in hungry groups (Indian ones for India)."""
    done = set(store.kv_get("fill_links_done") or [])
    seeds = []
    with store._lock:
        c = ytextra._db()
        for scope, kind, name in hungry[:8]:
            col = "COALESCE(NULLIF(c.ytcat,''), c.topic)" if kind == "cat" else "c.game"
            seeds += [(r[0], scope) for r in c.execute(
                f"""SELECT c.sid FROM sc_channels c JOIN (SELECT sid, MAX(subs) subs FROM sc_chstats GROUP BY sid) s ON s.sid=c.sid
                    WHERE c.platform='youtube' AND {col}=? {"AND COALESCE(c.india,0)=1" if scope == "in" else ""}
                    ORDER BY s.subs DESC LIMIT 400""", (name,))]
    todo = [(sid[3:], scope) for sid, scope in dict.fromkeys(seeds) if sid not in done][:LINK_PAGES]
    if not todo:
        return 0

    def one(cid):
        try:
            r = events._http.get(f"https://www.youtube.com/channel/{cid}/channels", timeout=12,
                                 headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                                 cookies={"CONSENT": "YES+", "SOCS": "CAI"})
            if r.status_code != 200:
                return []
            return [x for x in dict.fromkeys(re.findall(r'"channelId":"(UC[\w-]{22})"', r.text)) if x != cid][:80]
        except Exception:
            return []
    found = {"in": {}, "world": {}}
    for (cid, scope), got in zip(todo, ytextra._pool.map(one, [t[0] for t in todo])):
        done.add("yt:" + cid)
        for x in got:
            found[scope].setdefault(x, ("", ""))
    store.kv_set("fill_links_done", list(done)[-60000:])
    return admit(found["in"], "in") + admit(found["world"], "world")


def run_once() -> dict:
    n = counts()
    hungry = sorted([g for g, k in n.items() if k < CAND], key=lambda g: (n[g], g[0] != "in"))
    scale = 1
    if not hungry:                                          # every group full: keep catching newcomers lightly
        hungry, scale = sorted(n, key=lambda g: n[g])[:6], 0.25
    global SEARCH_PAGES, LINK_PAGES
    sp, lp = SEARCH_PAGES, LINK_PAGES
    SEARCH_PAGES, LINK_PAGES = max(2, int(sp * scale)), max(5, int(lp * scale))
    added = {}
    try:
        added["charts"] = charts(hungry if scale == 1 else list(n))
        added["search"] = search(hungry)
        added["links"] = links(hungry)
    finally:
        SEARCH_PAGES, LINK_PAGES = sp, lp
    if any(added.values()):
        print(f"Category fill: +{sum(added.values())} channels {added}; hungriest: "
              + ", ".join(f"{s}/{nm} {n[(s, k, nm)]}" for s, k, nm in hungry[:4]))
    return added


def report() -> str:
    n = counts()
    lines = []
    for scope in ("in", "world"):
        for kind in ("cat", "game"):
            part = sorted(((nm, k) for (s, kd, nm), k in n.items() if s == scope and kd == kind), key=lambda x: -x[1])
            if part:
                lines.append(f"\n{'INDIA' if scope == 'in' else 'WORLDWIDE'} - {'YouTube categories' if kind == 'cat' else 'games and topics'}")
                lines += [f"  {nm:26s} {k:6d} / {TARGET}" + ("  done" if k >= TARGET else "") for nm, k in part]
    return "\n".join(lines)
