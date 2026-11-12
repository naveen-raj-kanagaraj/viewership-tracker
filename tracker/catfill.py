"""Top Indian YouTube channels in every YouTube category.

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
SEARCH_PAGES = int(os.getenv("FILL_SEARCH_PAGES", "12"))      # free search pages per run (20 channels each)
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
_S = {}           # query -> {"page": n, "token": continuation} (memory only; restarts begin again, duplicates are ignored)


def counts() -> dict:
    """{category: Indian YouTube channels with numbers in the last 3 days}."""
    since = ytextra._day(time.time() - 3 * 86400)
    with store._lock:
        rows = ytextra._db().execute(
            """SELECT COALESCE(NULLIF(c.ytcat,''), c.topic) cat, COUNT(*) n FROM sc_channels c
               WHERE c.platform='youtube' AND COALESCE(c.india,0)=1
               AND EXISTS (SELECT 1 FROM sc_chstats s WHERE s.sid=c.sid AND s.day>=?) GROUP BY cat""", (since,)).fetchall()
    out = {cat: 0 for cat in QUERIES}
    for cat, n in rows:
        if cat in out:
            out[cat] = n
    return out


def _known(cids: list) -> set:
    if not cids:
        return set()
    sids = ["yt:" + c for c in cids]
    with store._lock:
        c = ytextra._db()
        return {r[0][3:] for i in range(0, len(sids), 500)
                for r in c.execute(f"SELECT sid FROM sc_channels WHERE sid IN ({','.join('?' * len(sids[i:i + 500]))})", sids[i:i + 500])}


def admit(found: dict) -> int:
    """found: {channel id: category or ''}. Adds channels the site doesn't know and reads their numbers now."""
    known = _known(list(found))
    new = [cid for cid in found if cid not in known][:MAX_NEW]
    if not new:
        return 0
    now = time.time()
    with store._lock:
        c = ytextra._db()
        c.executemany("""INSERT OR IGNORE INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                         country, india, language, tracked, ytcat) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
                      [("yt:" + cid, "youtube", "", f"https://www.youtube.com/channel/{cid}", "", now, None, "", "", None, 0, "",
                        found[cid] or "") for cid in new])
        c.commit()
    if os.getenv("YOUTUBE_API_KEY") and events.yt_quota_left(.9):
        got = ytextra._sane(ytextra.channel_stats(new))
        ytextra.save_stats(got, {cid: found[cid] for cid in new})
        # keep only the Indian ones: the rest would cost a daily reading each for a ranking this job isn't building
        sids = ["yt:" + c for c in new]
        with store._lock:
            c = ytextra._db()
            for i in range(0, len(sids), 500):
                part, q = sids[i:i + 500], ",".join("?" * len(sids[i:i + 500]))
                drop = [r[0] for r in c.execute(f"""SELECT sid FROM sc_channels WHERE sid IN ({q}) AND COALESCE(india,0)=0
                                                    AND last_live IS NULL AND COALESCE(tracked,0)=0""", part)]
                if drop:
                    dq = ",".join("?" * len(drop))
                    for t in ("sc_chstats", "sc_intra", "sc_channels"):
                        c.execute(f"DELETE FROM {t} WHERE sid IN ({dq})", drop)
            c.commit()
    with store._lock:
        kept = ytextra._db().execute(f"SELECT COUNT(*) FROM sc_channels WHERE sid IN ({','.join('?' * min(len(new), 900))})",
                                     ["yt:" + x for x in new[:900]]).fetchone()[0]
    return kept


def charts(hungry: list) -> int:
    """YouTube's India most-popular videos per category -> their channels, category known."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key or not events.yt_quota_left(.8):
        return 0
    last = store.kv_get("fill_chart_at") or {}
    found = {}
    for cat in hungry:
        if time.time() - last.get(cat, 0) < CHART_EVERY_H * 3600 or cat not in CAT_IDS:
            continue
        last[cat] = time.time()
        tok = ""
        for _ in range(4):                                  # the chart holds up to 200 videos
            r = events._http.get("https://www.googleapis.com/youtube/v3/videos", timeout=15, params={
                "part": "snippet", "chart": "mostPopular", "regionCode": "IN", "videoCategoryId": CAT_IDS[cat],
                "maxResults": 50, "pageToken": tok, "key": key})
            if r.status_code >= 400:                        # some categories have no chart in India
                break
            j = r.json()
            for it in j.get("items", []):
                cid = (it.get("snippet") or {}).get("channelId") or ""
                if cid.startswith("UC"):
                    found.setdefault(cid, cat)
            tok = j.get("nextPageToken") or ""
            if not tok:
                break
    store.kv_set("fill_chart_at", last)
    return admit(found)


def _search_page(q: str) -> list:
    """One page (about 20) of YouTube's channel search for q in India; continues where the last call stopped."""
    st = _S.setdefault(q, {"page": 0, "token": ""})
    ctx = {"client": {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": "IN"}}
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


def search(hungry: list) -> int:
    found, left = {}, SEARCH_PAGES
    for cat in hungry:
        for q in QUERIES[cat]:
            if left <= 0:
                break
            if _S.get(q, {}).get("page", 0) >= 25:          # 25 pages (~500 channels) per query is plenty
                continue
            try:
                for cid in _search_page(q):
                    found.setdefault(cid, "")
            except Exception as e:
                print(f"Category fill search '{q}': {str(e)[:80]}")
                _S.setdefault(q, {})["page"] = 99
            left -= 1
    return admit(found)


def links(hungry: list) -> int:
    """Channels listed on the Channels tab of the biggest Indian channels in hungry categories."""
    done = set(store.kv_get("fill_links_done") or [])
    with store._lock:
        rows = ytextra._db().execute(
            f"""SELECT c.sid FROM sc_channels c JOIN (SELECT sid, MAX(subs) subs FROM sc_chstats GROUP BY sid) s ON s.sid=c.sid
                WHERE c.platform='youtube' AND COALESCE(c.india,0)=1
                AND COALESCE(NULLIF(c.ytcat,''), c.topic) IN ({','.join('?' * len(hungry))})
                ORDER BY s.subs DESC LIMIT 3000""", hungry).fetchall()
    todo = [r[0][3:] for r in rows if r[0] not in done][:LINK_PAGES]
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
    found = {}
    for cid, got in zip(todo, ytextra._pool.map(one, todo)):
        done.add("yt:" + cid)
        for x in got:
            found.setdefault(x, "")
    store.kv_set("fill_links_done", list(done)[-40000:])
    return admit(found)


def run_once() -> dict:
    n = counts()
    hungry = sorted([c for c, k in n.items() if k < CAND], key=lambda c: n[c])
    if not hungry:                                          # every category full: keep catching newcomers lightly
        hungry, scale = sorted(n, key=lambda c: n[c])[:3], 0.25
    else:
        scale = 1
    added = {"charts": charts(hungry if scale == 1 else list(n)), "search": 0, "links": 0}
    global SEARCH_PAGES, LINK_PAGES
    sp, lp = SEARCH_PAGES, LINK_PAGES
    SEARCH_PAGES, LINK_PAGES = max(2, int(sp * scale)), max(5, int(lp * scale))
    try:
        added["search"] = search(hungry)
        added["links"] = links(hungry)
    finally:
        SEARCH_PAGES, LINK_PAGES = sp, lp
    if any(added.values()):
        print(f"Category fill: +{sum(added.values())} channels {added}; hungriest: "
              + ", ".join(f"{c} {n[c]}" for c in hungry[:4]))
    return added


def report() -> str:
    n = counts()
    return "\n".join(f"{c:24s} {k:6d} / {TARGET}" + ("  done" if k >= TARGET else "") for c, k in sorted(n.items(), key=lambda x: -x[1]))
