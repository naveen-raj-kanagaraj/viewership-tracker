"""YouTube extras: Super Chats on the biggest live streams, and daily channel stats (subscribers, total views,
videos) for every YouTube channel the site has seen live.

Super Chats
  The live chat of the top SUPERCHAT_TOP YouTube streams (by viewers, any country) is read the way the YouTube
  player reads it: the chat popout page gives the first continuation, then youtubei/v1/live_chat/get_live_chat
  returns new chat actions and the next continuation every few seconds. Paid items are stored once each (by their
  chat id) in sc_superchat:
    superchat  liveChatPaidMessageRenderer       amount shown on the message ("₹500.00", "$5.00", "CA$10.00")
    sticker    liveChatPaidStickerRenderer       amount shown on the sticker
    member     liveChatMembershipItemRenderer     a new or renewing member (YouTube shows no amount)
    gift       ...GiftPurchaseAnnouncementRenderer  memberships gifted (count, no amount)
  Amounts are converted to USD and INR with that day's exchange rates (open.er-api.com, else a built-in table).
  They are what viewers paid, before YouTube's cut.

Channel stats
  Once a day (IST) per channel: YouTube Data API channels.list (statistics) when YOUTUBE_API_KEY is set, else the
  channel's About page. Stored in sc_chstats (day, sid, subs, views, videos); views gained = difference between days.
"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from tracker import events, platforms, store

SUPERCHAT_TOP = int(os.getenv("SUPERCHAT_TOP", "50"))       # how many of the biggest YouTube streams to read chat for
SUPERCHAT_ON = os.getenv("SUPERCHAT", "true").lower() == "true"
STATS_ON = os.getenv("CHANNEL_STATS", "true").lower() == "true"
STATS_MAX = int(os.getenv("CHANNEL_STATS_MAX", "50000" if os.getenv("YOUTUBE_API_KEY") else "3000"))     # channels snapshotted per day, most watched first
_pool = ThreadPoolExecutor(6)

# ---------- storage ----------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sc_superchat (id TEXT PRIMARY KEY, sid TEXT, vid TEXT, ts INTEGER, day TEXT, kind TEXT,
    author TEXT, amount REAL, currency TEXT, usd REAL, inr REAL, n INTEGER, text TEXT);
CREATE INDEX IF NOT EXISTS sc_superchat_ix ON sc_superchat(sid, day);
CREATE INDEX IF NOT EXISTS sc_superchat_day ON sc_superchat(day);
CREATE TABLE IF NOT EXISTS sc_chstats (day TEXT, sid TEXT, subs INTEGER, views INTEGER, videos INTEGER, ts INTEGER,
    PRIMARY KEY (day, sid));
CREATE INDEX IF NOT EXISTS sc_chstats_sid ON sc_chstats(sid, day);
CREATE TABLE IF NOT EXISTS yt_videos (vid TEXT PRIMARY KEY, sid TEXT, ts INTEGER, title TEXT, views INTEGER, likes INTEGER,
    comments INTEGER, secs INTEGER, live INTEGER, approx INTEGER, updated INTEGER);
CREATE INDEX IF NOT EXISTS yt_videos_sid ON yt_videos(sid, ts);
CREATE TABLE IF NOT EXISTS sc_intra (sid TEXT, ts INTEGER, subs INTEGER, views INTEGER, PRIMARY KEY (sid, ts));
"""
_ready = False


def _db():
    global _ready
    from tracker import scene
    c = scene._db()
    if not _ready:
        c.executescript(_SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(yt_videos)")}
        if "short" not in cols:
            c.execute("ALTER TABLE yt_videos ADD COLUMN short INTEGER DEFAULT 0")
        if "url" not in cols:
            c.execute("ALTER TABLE yt_videos ADD COLUMN url TEXT DEFAULT ''")
        if "game" not in cols:
            c.execute("ALTER TABLE yt_videos ADD COLUMN game TEXT DEFAULT ''")
            c.execute("CREATE INDEX IF NOT EXISTS yt_videos_game ON yt_videos(game, ts)")
        if "cat" not in cols:
            c.execute("ALTER TABLE yt_videos ADD COLUMN cat INTEGER")
        if not store.kv_get("topics_v2"):                       # old coarse names -> YouTube's own category names
            for a, b in (("News & politics", "News & Politics"), ("Lifestyle", "People & Blogs"), ("Religion", "People & Blogs"), ("Other", "")):
                c.execute("UPDATE sc_channels SET topic=? WHERE topic=?", (b, a))
            c.commit()
            store.kv_set("topics_v2", True)
        if not store.kv_get("ytv_fix_premieres"):
            c.execute("UPDATE yt_videos SET updated=0")          # re-read: premieres were counted as live
            c.commit()
            store.kv_set("ytv_fix_premieres", True)
        if not store.kv_get("chstats_fix_about") and not os.getenv("YOUTUBE_API_KEY"):
            c.execute("DELETE FROM sc_chstats WHERE sid LIKE 'yt:%'")      # the old reader could store a video's views
            c.commit()
            store.kv_set("chstats_fix_about", True)
        _ready = True
    return c


def _day(ts=None) -> str:
    return datetime.fromtimestamp(ts or time.time(), events.REPORT_TZ).strftime("%Y-%m-%d")


# ---------- money ----------

_SYM = {"₹": "INR", "$": "USD", "US$": "USD", "CA$": "CAD", "A$": "AUD", "AU$": "AUD", "NZ$": "NZD", "HK$": "HKD",
        "NT$": "TWD", "MX$": "MXN", "R$": "BRL", "€": "EUR", "£": "GBP", "¥": "JPY", "JP¥": "JPY", "CN¥": "CNY",
        "₩": "KRW", "₱": "PHP", "₫": "VND", "฿": "THB", "₽": "RUB", "₺": "TRY", "₪": "ILS", "zł": "PLN", "Rp": "IDR",
        "RM": "MYR", "S$": "SGD", "SGD": "SGD", "kr": "SEK", "CHF": "CHF", "R": "ZAR", "E£": "EGP", "₦": "NGN",
        "Rs": "PKR", "৳": "BDT", "₴": "UAH", "₸": "KZT"}
# units per 1 USD, used when the live rates can't be fetched (approximate, 2026)
_FX_FALLBACK = {"USD": 1, "INR": 88, "EUR": .92, "GBP": .78, "JPY": 150, "CAD": 1.37, "AUD": 1.52, "NZD": 1.67,
                "HKD": 7.8, "TWD": 32, "MXN": 18.5, "BRL": 5.4, "KRW": 1380, "PHP": 57, "VND": 25500, "THB": 35,
                "RUB": 90, "TRY": 41, "ILS": 3.7, "PLN": 3.9, "IDR": 16300, "MYR": 4.4, "SGD": 1.32, "SEK": 10.5,
                "NOK": 10.7, "DKK": 6.9, "CHF": .86, "ZAR": 18, "EGP": 48, "NGN": 1500, "PKR": 281, "BDT": 120,
                "UAH": 41, "KZT": 500, "CNY": 7.2, "AED": 3.67, "SAR": 3.75, "ARS": 1000, "CLP": 950, "COP": 4000,
                "PEN": 3.7, "CZK": 23, "HUF": 360, "RON": 4.6, "LKR": 300, "NPR": 140, "QAR": 3.64, "KWD": .31}
_FX = {"day": "", "rates": dict(_FX_FALLBACK)}


def _rates() -> dict:
    d = _day()
    if _FX["day"] != d:
        _FX["day"] = d
        try:
            r = events._http.get("https://open.er-api.com/v6/latest/USD", timeout=10)
            got = r.json().get("rates") or {}
            if got.get("INR"):
                _FX["rates"] = {**_FX_FALLBACK, **{k: float(v) for k, v in got.items()}}
        except Exception as e:
            print(f"Exchange rates: using the built-in table ({str(e)[:80]})")
    return _FX["rates"]


def parse_money(txt: str):
    """'₹1,000.00' -> (1000.0, 'INR'); 'CA$5.00' -> (5.0, 'CAD'); 'PHP 100.00' -> (100.0, 'PHP'). None if unreadable."""
    t = (txt or "").replace(" ", " ").replace(" ", " ").strip()
    m = re.match(r"^\s*([^\d\s.,]*)\s*([\d.,]+)\s*([^\d\s.,]*)\s*$", t)
    if not m:
        return None
    pre, num, post = m.group(1), m.group(2), m.group(3)
    cur_s = pre or post
    cur = _SYM.get(cur_s) or (cur_s.upper() if re.fullmatch(r"[A-Za-z]{3}", cur_s or "") else None)
    if not cur:
        return None
    if re.search(r",\d{2}$", num) and "." not in num:          # 5,00 (decimal comma)
        num = num.replace(".", "").replace(",", ".")
    else:
        num = num.replace(",", "")
    try:
        return float(num), cur
    except ValueError:
        return None


def to_usd(amount: float, cur: str) -> float:
    r = _rates().get(cur)
    return amount / r if r else 0.0


# ---------- live chat ----------

_CHAT = {}            # vid -> {sid, cont, key, ver, next, fails, seen}
_SC_STATE = {"running": False}


def _text(o) -> str:
    if not o:
        return ""
    return o.get("simpleText") or "".join(r.get("text") or (r.get("emoji") or {}).get("shortcuts", [""])[0] for r in o.get("runs", []))


def _cont_of(conts) -> tuple:
    for c in conts or []:
        for k in ("invalidationContinuationData", "timedContinuationData", "reloadContinuationData"):
            if k in c:
                return c[k].get("continuation"), int(c[k].get("timeoutMs") or 8000)
    return None, 8000


def _chat_start(vid: str) -> dict:
    """The chat popout page: first continuation, API key and client version, plus the chat already on screen."""
    r = events._http.get("https://www.youtube.com/live_chat", params={"is_popout": "1", "v": vid}, timeout=15,
                         headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                         cookies={"CONSENT": "YES+", "SOCS": "CAI"})
    r.raise_for_status()
    h = r.text
    m = re.search(r'(?:window\["ytInitialData"\]|var ytInitialData)\s*=\s*(\{.+?\})\s*;\s*</script>', h, re.S)
    if not m:
        raise ValueError("no chat data (chat off or stream not live)")
    data = json.loads(m.group(1))
    key = (re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', h) or [None, ""])[1]
    ver = (re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION"\s*:\s*"([^"]+)"', h) or
           re.search(r'"clientVersion"\s*:\s*"([^"]+)"', h) or [None, "2.20251001.00.00"])[1]
    lcr = ((data.get("contents") or {}).get("liveChatRenderer") or {})
    cont, wait = _cont_of(lcr.get("continuations"))
    if not cont:
        raise ValueError("chat has no continuation")
    return {"cont": cont, "key": key, "ver": ver, "wait": wait, "actions": lcr.get("actions") or []}


def _chat_next(st: dict) -> dict:
    r = events._http.post("https://www.youtube.com/youtubei/v1/live_chat/get_live_chat",
                          params={"prettyPrint": "false", **({"key": st["key"]} if st.get("key") else {})},
                          json={"context": {"client": {"clientName": "WEB", "clientVersion": st["ver"], "hl": "en", "gl": "US"}},
                                "continuation": st["cont"]},
                          headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                   "Origin": "https://www.youtube.com"}, timeout=15)
    r.raise_for_status()
    lcc = ((r.json().get("continuationContents") or {}).get("liveChatContinuation") or {})
    cont, wait = _cont_of(lcc.get("continuations"))
    return {"cont": cont, "wait": wait, "actions": lcc.get("actions") or []}


def paid_items(actions: list) -> list:
    """Paid things in a batch of chat actions: [{id, ts, kind, author, amount, currency, n, text}]."""
    out = []
    for a in actions or []:
        it = (a.get("addChatItemAction") or {}).get("item") or {}
        for kind, key in (("superchat", "liveChatPaidMessageRenderer"), ("sticker", "liveChatPaidStickerRenderer"),
                          ("member", "liveChatMembershipItemRenderer"),
                          ("gift", "liveChatSponsorshipsGiftPurchaseAnnouncementRenderer")):
            r = it.get(key)
            if not r:
                continue
            x = {"id": r.get("id") or "", "ts": int(r.get("timestampUsec") or time.time() * 1e6) // 1_000_000,
                 "kind": kind, "author": _text(r.get("authorName")), "amount": 0.0, "currency": "", "n": 1,
                 "text": _text(r.get("message"))[:200]}
            if kind in ("superchat", "sticker"):
                pm = parse_money(_text(r.get("purchaseAmountText")))
                if not pm:
                    continue
                x["amount"], x["currency"] = pm
            elif kind == "gift":
                hdr = ((r.get("header") or {}).get("liveChatSponsorshipsHeaderRenderer") or {})
                x["author"] = x["author"] or _text(hdr.get("authorName"))
                n = re.search(r"(\d+)", _text(hdr.get("primaryText")))
                x["n"] = int(n.group(1)) if n else 1
            if x["id"]:
                out.append(x)
    return out


def _store(vid: str, sid: str, items: list):
    if not items:
        return
    rows = []
    for x in items:
        usd = to_usd(x["amount"], x["currency"]) if x["amount"] else 0.0
        rows.append((x["id"], sid, vid, x["ts"], _day(x["ts"]), x["kind"], x["author"], x["amount"], x["currency"],
                     round(usd, 4), round(usd * _rates()["INR"], 2), x["n"], x["text"]))
    with store._lock:
        c = _db()
        c.executemany("INSERT OR IGNORE INTO sc_superchat VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        c.commit()


def _count_chat(sid: str, actions: list):
    """Chat speed for Moments: one count per chat item, at the time YouTube stamped it."""
    from tracker import chat
    for a in actions or []:
        it = (a.get("addChatItemAction") or {}).get("item") or {}
        for r in it.values():
            if isinstance(r, dict) and r.get("timestampUsec"):
                chat.add(sid, 1, int(r["timestampUsec"]) / 1e6)
                break


def _targets() -> dict:
    """{video id: channel sid} for the biggest YouTube streams in the latest scan."""
    from tracker import scene
    rows = [r for r in scene._SCAN.get("rows") or [] if r.get("platform") == "youtube" and (r.get("url") or "").startswith("https://youtu.be/")]
    rows.sort(key=lambda r: -(r.get("viewers") or 0))
    return {r["url"].rsplit("/", 1)[-1]: r["sid"] for r in rows[:SUPERCHAT_TOP]}


def _poll(vid: str):
    st = _CHAT[vid]
    try:
        if not st.get("cont"):
            got = _chat_start(vid)
            st.update(cont=got["cont"], key=got["key"], ver=got["ver"])
        else:
            got = _chat_next(st)
            st["cont"] = got["cont"]
        _store(vid, st["sid"], paid_items(got["actions"]))
        _count_chat(st["sid"], got["actions"])
        st["fails"] = 0
        st["next"] = time.time() + min(15, max(5, got["wait"] / 1000))
        if not st["cont"]:                    # chat ended or turned off: start over later
            st["next"] = time.time() + 300
    except Exception as e:
        st["fails"] = st.get("fails", 0) + 1
        st["cont"] = None
        st["next"] = time.time() + min(900, 30 * 2 ** min(st["fails"], 5))
        st["err"] = str(e)[:120]
    finally:
        st["busy"] = False


def run_superchats():
    if _SC_STATE["running"] or not SUPERCHAT_ON:
        return
    _SC_STATE["running"] = True
    time.sleep(60)                            # after the first scan
    while True:
        try:
            want = _targets()
            now = time.time()
            for vid, sid in want.items():
                _CHAT.setdefault(vid, {"sid": sid, "cont": None, "next": 0, "fails": 0, "busy": False})["seen"] = now
            for vid in [v for v, s in _CHAT.items() if now - s.get("seen", 0) > 300 and not s.get("busy")]:
                del _CHAT[vid]
            for vid, st in list(_CHAT.items()):
                if not st["busy"] and st["next"] <= now:
                    st["busy"] = True
                    _pool.submit(_poll, vid)
        except Exception as e:
            print(f"Super Chat loop: {str(e)[:150]}")
        time.sleep(1)


# ---------- channel stats ----------

def _about_stats(cid: str):
    """(subs, views, videos) from the channel's About page, or None."""
    r = events._http.get(f"https://www.youtube.com/channel/{cid}/about", timeout=12,
                         headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                         cookies={"CONSENT": "YES+", "SOCS": "CAI"})
    if r.status_code != 200:
        return None
    i = r.text.find('"aboutChannelViewModel"')
    if i < 0:
        return None                           # no About panel in the page: better nothing than a wrong number
    h = r.text[i:i + 30000]                   # only the About panel: video tiles elsewhere have their own view counts

    def grab(name):
        m = re.search(r'"%s"\s*:\s*(?:"([^"]+)"|\{"(?:simpleText|content)"\s*:\s*"([^"]+)")' % name, h)
        return (m.group(1) or m.group(2)) if m else ""
    vt = grab("viewCountText")
    if "view" not in vt.lower():
        return None
    views = platforms.parse_count(vt)
    if views is None:
        return None
    grab_n = lambda n: platforms.parse_count(grab(n))
    return grab_n("subscriberCountText"), views, grab_n("videoCountText")
    return grab("subscriberCountText"), views, grab("videoCountText")


_META = {}            # channel id -> {topic, country, name, logo} from the last API read
# YouTube's own video categories (videos.list snippet.categoryId). A channel's category is the one most of its
# recent videos are filed under; until its videos are read, it's derived from the channel's topic tags.
YT_CATS = {1: "Film & Animation", 2: "Autos & Vehicles", 10: "Music", 15: "Pets & Animals", 17: "Sports", 19: "Travel & Events",
           20: "Gaming", 22: "People & Blogs", 23: "Comedy", 24: "Entertainment", 25: "News & Politics", 26: "Howto & Style",
           27: "Education", 28: "Science & Technology", 29: "Nonprofits & Activism"}
CATEGORIES = sorted(set(YT_CATS.values()))
_TOPICS = [("Gaming", r"game|gaming|esport"), ("Music", r"music|jazz|reggae"),
           ("Sports", r"sport|football|cricket|basketball|tennis|racing|boxing|golf|baseball|hockey|volleyball|mixed_martial"),
           ("Comedy", r"humour"), ("Film & Animation", r"film"), ("Pets & Animals", r"\bpet\b"), ("Autos & Vehicles", r"vehicle"),
           ("Travel & Events", r"tourism"), ("Science & Technology", r"technology"),
           ("Howto & Style", r"fashion|physical_attractiveness|food|fitness|hobby|health"), ("News & Politics", r"politic|military"),
           ("Education", r"knowledge|business"), ("People & Blogs", r"lifestyle|religion"),
           ("Entertainment", r"entertainment|television|performing_arts|wrestling"), ("People & Blogs", r"society")]


def topic_of(urls: list) -> str:
    """YouTube's topic tags (Wikipedia links like .../Action_game) -> the nearest YouTube category."""
    names = " ".join(u.rsplit("/", 1)[-1].lower() for u in urls)
    for cat, rx in _TOPICS:
        if re.search(rx, names):
            return cat
    return ""


def cat_of(row) -> str:
    """A channel's category: from its videos when known, else from its topic tags."""
    return (row["ytcat"] if "ytcat" in row.keys() and row["ytcat"] else row["topic"]) or ""


def channel_stats(cids: list) -> dict:
    """{channel id: (subs, views, videos)}. YouTube Data API (exact views; 1 quota unit per 50) when
    YOUTUBE_API_KEY is set, else About pages."""
    key, out = os.getenv("YOUTUBE_API_KEY"), {}
    if key:
        for i in range(0, len(cids), 50):
            r = events._http.get("https://www.googleapis.com/youtube/v3/channels",
                                 params={"part": "statistics,topicDetails,snippet", "id": ",".join(cids[i:i + 50]), "key": key}, timeout=15)
            r.raise_for_status()
            for it in r.json().get("items", []):
                s = it.get("statistics") or {}
                _META[it["id"]] = {"topic": topic_of((it.get("topicDetails") or {}).get("topicCategories") or []),
                                   "country": (it.get("snippet") or {}).get("country") or "",
                                   "name": (it.get("snippet") or {}).get("title") or "",
                                   "logo": (((it.get("snippet") or {}).get("thumbnails") or {}).get("medium") or {}).get("url") or ""}
                out[it["id"]] = (None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount") or 0),
                                 int(s.get("viewCount") or 0), int(s.get("videoCount") or 0))
        return out

    def one(cid):
        try:
            return cid, _about_stats(cid)
        except Exception:
            return cid, None
    for cid, v in _pool.map(one, cids):
        if v:
            out[cid] = v
    return out


def stats_once(limit: int = 300) -> int:
    """Snapshot up to `limit` YouTube channels that have none for today yet, most watched first."""
    d = _day()
    since = (datetime.now(events.REPORT_TZ).date() - timedelta(days=30)).strftime("%Y-%m-%d")
    with store._lock:
        c = _db()
        todo = [r[0] for r in c.execute(
            """SELECT c.sid FROM sc_channels c LEFT JOIN (SELECT sid, SUM(hw) hw FROM sc_daily WHERE day>=? GROUP BY sid) d
               ON d.sid=c.sid WHERE c.platform='youtube' AND c.sid NOT IN (SELECT sid FROM sc_chstats WHERE day=?)
               ORDER BY COALESCE(c.tracked,0) DESC, COALESCE(d.hw,0) DESC LIMIT ?""", (since, d, STATS_MAX)).fetchall()]
        done_today = c.execute("SELECT COUNT(*) FROM sc_chstats WHERE day=?", (d,)).fetchone()[0]
    todo = todo[:max(0, min(limit, STATS_MAX - done_today))]
    if not todo:
        return 0
    got = channel_stats([s[3:] for s in todo])
    now = int(time.time())
    with store._lock:
        c = _db()
        c.executemany("INSERT OR REPLACE INTO sc_chstats VALUES (?,?,?,?,?,?)",
                      [(d, "yt:" + cid, s, v, n, now) for cid, (s, v, n) in got.items()])
        c.executemany("INSERT OR IGNORE INTO sc_intra VALUES (?,?,?,?)", [("yt:" + cid, now, s, v) for cid, (s, v, n) in got.items()])
        c.execute("DELETE FROM sc_intra WHERE ts<?", (now - 3 * 86400,))
        meta = [(m["topic"], m["country"], m["name"], m["logo"], "yt:" + cid) for cid, m in _META.items() if cid in got]
        c.executemany("""UPDATE sc_channels SET topic=COALESCE(NULLIF(?,''), topic),
                         country=CASE WHEN ?!='' THEN ? ELSE country END, name=COALESCE(NULLIF(?,''), name),
                         logo=COALESCE(NULLIF(?,''), logo) WHERE sid=?""",
                      [(t, ct, ct, n, lg, sid) for t, ct, n, lg, sid in meta])
        c.execute("UPDATE sc_channels SET india=1 WHERE country='IN' AND platform='youtube' AND COALESCE(india,0)=0")
        c.commit()
    _META.clear()
    return len(got)


def run_stats():
    if not STATS_ON:
        return
    time.sleep(120)
    while True:
        try:
            stats_once(2000 if os.getenv("YOUTUBE_API_KEY") else 120)
            discover_once()
            prefetch_once(8 if os.getenv("YOUTUBE_API_KEY") else 2)
            followers_once(100)
        except Exception as e:
            print(f"Channel stats: {str(e)[:150]}")
        time.sleep(900)                       # every 15 min, until every channel has today's numbers


def start():
    threading.Thread(target=run_superchats, daemon=True).start()
    threading.Thread(target=run_stats, daemon=True).start()


# ---------- numbers for the pages ----------

def _since(n: int) -> str:
    return (datetime.now(events.REPORT_TZ).date() - timedelta(days=n - 1)).strftime("%Y-%m-%d") if n else ""


def channel_extra(sid: str) -> dict:
    """Super Chats (today / 7 / 30 days / all time, biggest ones) and channel stats (latest, gains) for one channel."""
    with store._lock:
        c = _db()
        sc = {}
        for k, n in (("today", 1), ("7d", 7), ("30d", 30), ("all", 0)):
            r = c.execute("""SELECT SUM(usd), SUM(inr), SUM(CASE WHEN kind IN ('superchat','sticker') THEN 1 ELSE 0 END),
                             SUM(CASE WHEN kind IN ('member','gift') THEN n ELSE 0 END) FROM sc_superchat WHERE sid=? AND day>=?""",
                          (sid, _since(n))).fetchone()
            sc[k] = {"usd": round(r[0] or 0, 2), "inr": round(r[1] or 0), "count": r[2] or 0, "members": r[3] or 0}
        top = [dict(r) for r in c.execute("""SELECT author, amount, currency, usd, inr, ts, text FROM sc_superchat
                                             WHERE sid=? AND day>=? AND kind IN ('superchat','sticker') ORDER BY usd DESC LIMIT 5""",
                                          (sid, _since(30)))]
        st = [dict(r) for r in c.execute("SELECT day, subs, views, videos FROM sc_chstats WHERE sid=? ORDER BY day DESC LIMIT 31", (sid,))]
    stats = None
    if st:
        last = st[0]

        def gain(n):
            old = next((x for x in st if x["day"] <= (datetime.strptime(last["day"], "%Y-%m-%d").date()
                                                     - timedelta(days=n)).strftime("%Y-%m-%d")), None)
            return None if not old else {"views": (last["views"] or 0) - (old["views"] or 0),
                                         "subs": (last["subs"] or 0) - (old["subs"] or 0) if last["subs"] is not None and old["subs"] is not None else None}
        stats = {"day": last["day"], "subs": last["subs"], "views": last["views"], "videos": last["videos"],
                 "gain_1d": gain(1), "gain_7d": gain(7), "gain_30d": gain(30),
                 "days": [{"day": x["day"], "views": x["views"], "subs": x["subs"]} for x in reversed(st)]}
    has_sc = any(v["count"] or v["members"] for v in sc.values())
    reading = any(st.get("sid") == sid and st.get("cont") for st in list(_CHAT.values()))
    return {"superchats": sc if has_sc else None, "top_superchats": top, "stats": stats,
            "sc_status": "reading" if reading else ("recorded" if has_sc else ("off" if not SUPERCHAT_ON else "not_top"))}


def window_superchats(d0: str, d1: str) -> dict:
    """{sid: {usd, inr, count}} for days d0..d1."""
    with store._lock:
        rows = _db().execute("""SELECT sid, SUM(usd), SUM(inr), SUM(CASE WHEN kind IN ('superchat','sticker') THEN 1 ELSE 0 END)
                                FROM sc_superchat WHERE day BETWEEN ? AND ? GROUP BY sid""", (d0, d1)).fetchall()
    return {r[0]: {"usd": round(r[1] or 0, 2), "inr": round(r[2] or 0), "count": r[3] or 0} for r in rows}


def window_views(d0: str, d1: str) -> dict:
    """{sid: {views gained, subs gained, subs, views}} between the last snapshot before d0 (or on it) and the last on
    or before d1. Channels with a single snapshot in reach have no gain yet."""
    prev = (datetime.strptime(d0, "%Y-%m-%d").date() - timedelta(days=1)).strftime("%Y-%m-%d")
    with store._lock:
        rows = _db().execute("""SELECT sid, day, subs, views FROM sc_chstats WHERE day BETWEEN ? AND ? ORDER BY sid, day""",
                             ((datetime.strptime(prev, "%Y-%m-%d").date() - timedelta(days=3)).strftime("%Y-%m-%d"), d1)).fetchall()
    by = {}
    for r in rows:
        by.setdefault(r[0], []).append(r)
    out = {}
    for sid, L in by.items():
        start = [x for x in L if x[1] <= prev] or [x for x in L if x[1] <= d0]
        if not start:
            continue
        a, b = start[-1], L[-1]
        if a[1] == b[1]:
            continue
        out[sid] = {"vg": max(0, (b[3] or 0) - (a[3] or 0)), "sg": (b[2] - a[2]) if a[2] is not None and b[2] is not None else None,
                    "subs": b[2], "views": b[3]}
    return out


def probe_chat(vid: str, seconds: int = 60) -> str:
    """Read one stream's chat for a while and list what was found (for checking from the command line)."""
    vid = vid.strip().rstrip("/").rsplit("/", 1)[-1].split("v=")[-1].split("&")[0]
    try:
        st = _chat_start(vid)
    except Exception as e:
        return f"Could not open the chat of {vid}: {e}"
    lines = [f"Chat opened for {vid} (client {st['ver']}, key {'yes' if st['key'] else 'no'}). On screen now: {len(st['actions'])} items."]
    found = paid_items(st["actions"])
    t_end, polls = time.time() + seconds, 0
    while time.time() < t_end and st.get("cont"):
        time.sleep(min(10, max(4, st["wait"] / 1000)))
        try:
            nx = _chat_next(st)
        except Exception as e:
            lines.append(f"Poll failed: {e}")
            break
        polls += 1
        st.update(cont=nx["cont"], wait=nx["wait"])
        found += paid_items(nx["actions"])
        lines.append(f"poll {polls}: {len(nx['actions'])} chat actions")
    for x in found:
        usd = to_usd(x["amount"], x["currency"]) if x["amount"] else 0
        lines.append(f"  {x['kind']:9} {x['author'][:24]:24} {x['amount']:>10.2f} {x['currency']:3}  = ${usd:,.2f}  x{x['n']}")
    lines.append(f"{len(found)} paid items found in {seconds}s." + ("" if found else " (None is normal if nobody paid in that time.)"))
    return "\n".join(lines)


def resolve_handle(chan: str):
    """'@handle', a channel URL or a UC id -> the channel's UC id. YouTube Data API forHandle when a key is set
    (exact), else the channel page's canonical link (not the first id on the page: pages list other channels too)."""
    x = chan.strip().rstrip("/").rsplit("/", 1)[-1]
    if re.fullmatch(r"UC[\w-]{22}", x):
        return x
    h = "@" + x.lstrip("@")
    key = os.getenv("YOUTUBE_API_KEY")
    try:
        if key:
            j = events._http.get("https://www.googleapis.com/youtube/v3/channels",
                                 params={"part": "id", "forHandle": h, "key": key}, timeout=12).json()
            if j.get("items"):
                return j["items"][0]["id"]
        r = events._http.get(f"https://www.youtube.com/{h}", timeout=12,
                             headers={"User-Agent": events._UA}, cookies={"CONSENT": "YES+", "SOCS": "CAI"})
        m = (re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', r.text)
             or re.search(r'"externalId"\s*:\s*"(UC[\w-]{22})"', r.text))
        return m.group(1) if m else None
    except Exception:
        return None


def probe_stats(chan: str) -> str:
    cid = resolve_handle(chan)
    if not cid:
        return f"Could not find {chan}."
    got = channel_stats([cid]).get(cid)
    if not got:
        return f"No stats read for {cid} ({'YouTube Data API' if os.getenv('YOUTUBE_API_KEY') else 'About page'})."
    s, v, n = got
    return f"{cid}: subscribers {s if s is not None else 'hidden'}, total views {v:,}, videos {n}  (via {'YouTube Data API' if os.getenv('YOUTUBE_API_KEY') else 'About page'})"


# ---------- past streams (last 30 days), from the platforms themselves ----------

_PAST = {}            # sid -> (time fetched, result)


def _ago_to_ts(txt: str):
    """'Streamed 2 days ago' / '3 weeks ago' -> approximate unix time."""
    m = re.search(r"(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?|months?|years?|mo|s|m|h|d|w|y)\s+ago", (txt or "").lower())
    if not m:
        return None
    sec = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000, "year": 31536000,
           "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000}
    u = m.group(2)
    return int(time.time() - int(m.group(1)) * sec[u if u in sec else u.rstrip("s")])


def _dur(txt: str) -> int:
    """'3:45:12' -> seconds; Twitch '3h2m1s' -> seconds."""
    if not txt:
        return 0
    if ":" in txt:
        n = 0
        for p in txt.split(":"):
            n = n * 60 + int(p or 0)
        return n
    return sum(int(v) * {"h": 3600, "m": 60, "s": 1}[u] for v, u in re.findall(r"(\d+)([hms])", txt))


def _walk(o, key, out):
    if isinstance(o, dict):
        if key in o:
            out.append(o[key])
        for v in o.values():
            _walk(v, key, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, key, out)
    return out


def _yt_past(cid: str, tab: str = "streams") -> list:
    """Videos on a channel tab: 'streams' (past live streams) or 'videos' (uploads)."""
    r = events._http.get(f"https://www.youtube.com/channel/{cid}/{tab}", timeout=15,
                         headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                         cookies={"CONSENT": "YES+", "SOCS": "CAI"})
    r.raise_for_status()
    m = re.search(r'var ytInitialData\s*=\s*(\{.+?\})\s*;\s*</script>', r.text, re.S)
    if not m:
        return []
    return _parse_tab(json.loads(m.group(1)))


def _parse_tab(data) -> list:
    out = []
    # newer layout: lockupViewModel (title, "2M" views with "2 million views" label, "Streamed 16h ago", duration badge)
    for v in _walk(data, "lockupViewModel", []):
        if v.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO") or not v.get("contentId"):
            continue
        md = ((v.get("metadata") or {}).get("lockupMetadataViewModel") or {})
        parts = [p for row in (((md.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or [])
                 for p in (row.get("metadataParts") or [])]
        labels = [(p.get("accessibilityLabel") or ((p.get("text") or {}).get("content") or "")) for p in parts]
        views = next((x for x in labels if "view" in x.lower()), "")
        when = next((x for x in labels if "ago" in x.lower()), "")
        if any("watching" in x.lower() for x in labels):
            continue
        badge = next((b.get("thumbnailBadgeViewModel", {}).get("text") for o in _walk(v.get("contentImage") or {}, "badges", [])
                      for b in o if b.get("thumbnailBadgeViewModel")), "")
        out.append({"id": v["contentId"], "title": (md.get("title") or {}).get("content") or "", "ts": _ago_to_ts(when),
                    "when": when, "views": platforms.parse_count(views),
                    "secs": _dur(badge) if badge and re.fullmatch(r"[\d:]+", badge) else 0,
                    "url": f"https://www.youtube.com/watch?v={v['contentId']}"})
    for v in _walk(data, "videoRenderer", []):
        when = (v.get("publishedTimeText") or {}).get("simpleText") or ""
        views = (v.get("viewCountText") or {}).get("simpleText") or _text(v.get("viewCountText"))
        if "watching" in (views or "").lower():
            continue                              # live right now: that's on the live part of the page
        ts = _ago_to_ts(when)
        out.append({"id": v.get("videoId"), "title": _text(v.get("title")), "ts": ts, "when": when,
                    "views": platforms.parse_count(views), "secs": _dur((v.get("lengthText") or {}).get("simpleText")),
                    "url": f"https://www.youtube.com/watch?v={v.get('videoId')}"})
    return out


def _tw_past(login: str) -> list:
    u = platforms._get("twitch", "https://api.twitch.tv/helix/users", {"login": login}).get("data") or []
    if not u:
        return []
    j = platforms._get("twitch", "https://api.twitch.tv/helix/videos", {"user_id": u[0]["id"], "type": "archive", "first": 50})
    out = []
    for v in j.get("data") or []:
        try:
            ts = int(datetime.fromisoformat(v["created_at"].replace("Z", "+00:00")).timestamp())
        except Exception:
            ts = None
        out.append({"id": v.get("id"), "title": v.get("title") or "", "ts": ts, "when": "", "views": v.get("view_count"),
                    "secs": _dur(v.get("duration")), "url": v.get("url") or ""})
    return out


def past_streams(sid: str) -> dict:
    """The channel's streams in the last 30 days as the platform lists them (title, date, length, total views), joined
    with the peak we recorded that day. YouTube: the channel's Live tab; Twitch: its past broadcasts; Kick: not
    available. Cached for an hour."""
    hit = _PAST.get(sid)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    plat, _, ident = sid.partition(":")
    res = {"source": "", "streams": [], "note": ""}
    try:
        if plat == "yt":
            res.update(source="YouTube channel, Live tab", streams=_yt_past(ident))
        elif plat == "twitch":
            res.update(source="Twitch past broadcasts", streams=_tw_past(ident))
        else:
            res["note"] = "Kick doesn't list past streams publicly; only what this site recorded is shown."
    except Exception as e:
        res["note"] = f"Couldn't read past streams right now ({str(e)[:80]})."
    cut = time.time() - 30 * 86400
    res["streams"] = [x for x in res["streams"] if not x["ts"] or x["ts"] >= cut][:40]
    with store._lock:
        peaks = dict(_db().execute("SELECT day, MAX(peak) FROM sc_daily WHERE sid=? GROUP BY day", (sid,)).fetchall())
    for x in res["streams"]:
        x["day"] = _day(x["ts"]) if x["ts"] else ""
        x["peak_day"] = peaks.get(x["day"]) if x["day"] else None
    _PAST[sid] = (time.time(), res)
    if len(_PAST) > 2000:
        for k in sorted(_PAST, key=lambda k: _PAST[k][0])[:500]:
            _PAST.pop(k, None)
    return res


# ---------- any YouTube channel: search, add, track daily ----------

_YTS = {}             # query -> (time, results)


def yt_channel_search(q: str, gl: str = "IN") -> list:
    """YouTube's own channel search: [{sid, name, logo, subs_text, handle}]. Cached 10 minutes."""
    q = (q or "").strip()[:60]
    hit = _YTS.get(q.lower())
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    r = events._http.post("https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
                          json={"context": {"client": {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": gl}},
                                "query": q, "params": "EgIQAg=="},          # filter: channels
                          headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                   "Origin": "https://www.youtube.com"}, timeout=10)
    r.raise_for_status()
    out = []
    for ch in _walk(r.json(), "channelRenderer", []):
        cid = ch.get("channelId") or ""
        if not cid.startswith("UC"):
            continue
        texts = [_text(ch.get(k)) for k in ("subscriberCountText", "videoCountText")]
        subs = next((t for t in texts if "subscriber" in t.lower()), "")
        handle = next((t for t in texts if t.startswith("@")), "")
        th = ((ch.get("thumbnail") or {}).get("thumbnails") or [{}])[-1].get("url", "")
        out.append({"sid": "yt:" + cid, "name": _text(ch.get("title")), "logo": ("https:" + th) if th.startswith("//") else th,
                    "subs_text": subs, "handle": handle})
    _YTS[q.lower()] = (time.time(), out[:10])
    if len(_YTS) > 1000:
        _YTS.clear()
    return out[:10]


def _channel_info(cid: str) -> dict:
    """Name, avatar and country from the channel's page."""
    r = events._http.get(f"https://www.youtube.com/channel/{cid}/about", timeout=12,
                         headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                         cookies={"CONSENT": "YES+", "SOCS": "CAI"})
    r.raise_for_status()
    h = r.text
    meta = lambda p: (re.search(r'<meta property="%s" content="([^"]*)"' % p, h) or [None, ""])[1]
    import html as _html
    m = re.search(r'"country"\s*:\s*"([^"]+)"', h)
    return {"name": _html.unescape(meta("og:title")), "logo": meta("og:image"), "country": m.group(1) if m else ""}


def ensure_channel(sid: str, name: str = "", logo: str = "") -> bool:
    """Make sure a YouTube channel is in sc_channels and followed daily (tracked=1), even if it has never been seen
    live. Takes its first stats snapshot right away. False if the channel can't be found."""
    from tracker import scene
    if not re.fullmatch(r"yt:UC[\w-]{22}", sid or ""):
        return False
    with store._lock:
        row = _db().execute("SELECT sid, tracked, EXISTS(SELECT 1 FROM sc_chstats WHERE sid=?) FROM sc_channels WHERE sid=?", (sid, sid)).fetchone()
    if row and row[1] and row[2]:
        return True
    cid = sid[3:]
    if not row:
        try:
            info = _channel_info(cid)
        except Exception:
            info = {"name": name, "logo": logo, "country": ""}
        nm = info.get("name") or name
        if not nm:
            return False
        ctry = scene._norm_country(info.get("country"))
        with store._lock:
            c = _db()
            c.execute("""INSERT OR IGNORE INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                         country, india, language, tracked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                      (sid, "youtube", nm, f"https://www.youtube.com/channel/{cid}", info.get("logo") or logo, time.time(),
                       None, "", "", ctry, 1 if ctry == "IN" else 0, ""))
            c.commit()
    else:
        with store._lock:
            c = _db()
            c.execute("UPDATE sc_channels SET tracked=1 WHERE sid=?", (sid,))
            c.commit()
    try:
        got = channel_stats([cid]).get(cid)
        if got:
            with store._lock:
                c = _db()
                c.execute("INSERT OR REPLACE INTO sc_chstats VALUES (?,?,?,?,?,?)", (_day(), sid, *got, int(time.time())))
                c.execute("INSERT OR IGNORE INTO sc_intra VALUES (?,?,?,?)", (sid, int(time.time()), got[0], got[1]))
                c.commit()
    except Exception as e:
        print(f"First stats for {sid}: {str(e)[:100]}")
    return True


def views_series(sid: str, days: int = 90) -> dict:
    """Daily snapshots and the views / subscribers gained between them, plus 7 / 30 day and per-month totals."""
    with store._lock:
        st = [dict(r) for r in _db().execute("SELECT day, subs, views, videos FROM sc_chstats WHERE sid=? ORDER BY day DESC LIMIT ?",
                                             (sid, days + 1))]
    st.reverse()
    gains = []
    for a, b in zip(st, st[1:]):
        gap = (datetime.strptime(b["day"], "%Y-%m-%d") - datetime.strptime(a["day"], "%Y-%m-%d")).days or 1
        gains.append({"day": b["day"], "views": max(0, (b["views"] or 0) - (a["views"] or 0)), "days": gap,
                      "subs": (b["subs"] - a["subs"]) if a["subs"] is not None and b["subs"] is not None else None})
    months = {}
    for g in gains:
        months[g["day"][:7]] = months.get(g["day"][:7], 0) + g["views"]
    return {"first": st[0]["day"] if st else None, "snapshots": st, "gains": gains,
            "months": [{"month": k, "views": v} for k, v in sorted(months.items())], "recent": recent_views(sid)}


_IBUSY = set()


def recent_views(sid: str) -> dict:
    """Views gained over the last hours, from readings taken during the day: shows a newly followed channel's views
    the same day instead of waiting for tomorrow's snapshot. Opening the page takes a fresh reading at most once an
    hour (1 YouTube API unit)."""
    with store._lock:
        R = _db().execute("SELECT ts, subs, views FROM sc_intra WHERE sid=? AND ts>? ORDER BY ts", (sid, time.time() - 26 * 3600)).fetchall()
    if sid.startswith("yt:") and os.getenv("YOUTUBE_API_KEY") and (not R or time.time() - R[-1][0] > 3600) and sid not in _IBUSY:
        _IBUSY.add(sid)

        def read():
            try:
                got = channel_stats([sid[3:]]).get(sid[3:])
                if got:
                    with store._lock:
                        c = _db()
                        c.execute("INSERT OR IGNORE INTO sc_intra VALUES (?,?,?,?)", (sid, int(time.time()), got[0], got[1]))
                        c.commit()
            except Exception:
                pass
            finally:
                _IBUSY.discard(sid)
                _META.clear()
        threading.Thread(target=read, daemon=True).start()
    if len(R) < 2 or R[-1][0] - R[0][0] < 1800 or R[0][2] is None or R[-1][2] is None or R[-1][2] < R[0][2]:
        return {"since": R[0][0] if R else None}
    return {"since": R[0][0], "ts": R[-1][0], "hours": round((R[-1][0] - R[0][0]) / 3600, 1), "views": R[-1][2] - R[0][2],
            "subs": (R[-1][1] - R[0][1]) if R[0][1] is not None and R[-1][1] is not None else None}


def track_found(res: dict) -> int:
    """Follow every channel a search turned up (daily stats start without anyone opening them). Only adds rows:
    the stats loop reads them in batches (YouTube: 1 API unit per 50 channels)."""
    from tracker import scene
    rows = []
    for plat, L in res.items():
        for x in L:
            sid = x.get("sid") or ""
            if not re.fullmatch(r"(yt:UC[\w-]{22}|(twitch|kick):[a-z0-9_-]{2,40})", sid):
                continue
            url = (f"https://www.youtube.com/channel/{sid[3:]}" if sid.startswith("yt:") else
                   f"https://www.twitch.tv/{sid[7:]}" if sid.startswith("twitch:") else f"https://kick.com/{sid[5:]}")
            rows.append((sid, sid.split(":")[0].replace("yt", "youtube"), x.get("name") or sid.split(":", 1)[1], url, x.get("logo") or "", time.time()))
    if not rows:
        return 0
    with store._lock:
        c = _db()
        n0 = c.total_changes
        c.executemany("""INSERT OR IGNORE INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game, tracked)
                         VALUES (?,?,?,?,?,?,NULL,'','',1)""", rows)
        c.executemany("UPDATE sc_channels SET tracked=1 WHERE sid=? AND COALESCE(tracked,0)=0", [(r[0],) for r in rows])
        c.commit()
        return c.total_changes - n0


# ---------- Twitch and Kick channels (lookup, followers) ----------

_KINFO = {}           # kick slug -> (time, json from kick.com/api/v2/channels/<slug>) ; shared with chat.py's chatroom ids


def kick_info(slug: str) -> dict:
    """Kick's own channel JSON (followers_count, chatroom id, user, livestream). Unofficial; Kick may block it."""
    hit = _KINFO.get(slug)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    j = {}
    try:
        r = events._http.get(f"https://kick.com/api/v2/channels/{slug}", timeout=10,
                             headers={"User-Agent": events._UA, "Accept": "application/json"})
        if r.status_code == 200:
            j = r.json()
    except Exception:
        pass
    _KINFO[slug] = (time.time(), j)
    return j


def lookup(q: str) -> dict:
    """Channels matching q on YouTube (channel search), Twitch (channel search) and Kick (exact channel name)."""
    out = {"youtube": [], "twitch": [], "kick": []}
    try:
        out["youtube"] = yt_channel_search(q)
    except Exception:
        pass
    if platforms._keys("twitch"):
        try:
            for x in (platforms._get("twitch", "https://api.twitch.tv/helix/search/channels", {"query": q, "first": 6}).get("data") or []):
                out["twitch"].append({"sid": "twitch:" + x["broadcaster_login"].lower(), "name": x.get("display_name") or x["broadcaster_login"],
                                      "logo": x.get("thumbnail_url") or "", "live": bool(x.get("is_live")),
                                      "subs_text": x.get("game_name") or "", "handle": x["broadcaster_login"]})
        except Exception:
            pass
    slug = re.sub(r"[^a-z0-9_-]", "", q.lower().replace(" ", ""))[:40]
    if slug and platforms._keys("kick"):
        try:
            for x in (platforms._get("kick", "https://api.kick.com/public/v1/channels", [("slug", slug)]).get("data") or []):
                live = (x.get("stream") or {}).get("is_live")
                out["kick"].append({"sid": "kick:" + x["slug"].lower(), "name": x["slug"], "logo": "", "live": bool(live),
                                    "subs_text": (x.get("category") or {}).get("name") or "", "handle": x["slug"]})
        except Exception:
            pass
    return out


def _twitch_users(logins: list) -> dict:
    out = {}
    for i in range(0, len(logins), 100):
        for u in platforms._get("twitch", "https://api.twitch.tv/helix/users", [("login", x) for x in logins[i:i + 100]]).get("data") or []:
            out[u["login"].lower()] = u
    return out


def twitch_followers(logins: list) -> dict:
    """{login: followers}. Needs the connected Twitch account (track.py twitch-login); Twitch only gives follower totals
    to logged-in accounts."""
    from tracker import moments
    tok = moments._user_token()
    if not tok or not logins:
        return {}
    cid = (platforms._keys("twitch") or ("",))[0]
    users, out = _twitch_users(logins), {}
    for login, u in users.items():
        r = platforms._http.get("https://api.twitch.tv/helix/channels/followers", params={"broadcaster_id": u["id"], "first": 1},
                                headers={"Authorization": f"Bearer {tok}", "Client-Id": cid}, timeout=10)
        if r.status_code == 200:
            out[login] = int(r.json().get("total") or 0)
    return out


def ensure_any(sid: str) -> bool:
    """Like ensure_channel, for Twitch and Kick: add the channel, follow it daily, take its first follower count."""
    if sid.startswith("yt:"):
        return ensure_channel(sid)
    plat, _, ident = sid.partition(":")
    if plat not in ("twitch", "kick") or not re.fullmatch(r"[a-z0-9_-]{2,40}", ident or ""):
        return False
    with store._lock:
        row = _db().execute("SELECT tracked, EXISTS(SELECT 1 FROM sc_chstats WHERE sid=?) FROM sc_channels WHERE sid=?", (sid, sid)).fetchone()
    if row and row[0] and row[1]:
        return True
    if not row:
        name, logo = ident, ""
        try:
            if plat == "twitch":
                u = _twitch_users([ident]).get(ident)
                if not u:
                    return False
                name, logo = u.get("display_name") or ident, u.get("profile_image_url") or ""
            else:
                j = platforms._get("kick", "https://api.kick.com/public/v1/channels", [("slug", ident)]).get("data") or []
                if not j:
                    return False
                name = j[0].get("slug") or ident
                logo = ((kick_info(ident).get("user") or {}).get("profile_pic")) or ""
        except Exception:
            return False
        url = f"https://www.twitch.tv/{ident}" if plat == "twitch" else f"https://kick.com/{ident}"
        with store._lock:
            c = _db()
            c.execute("""INSERT OR IGNORE INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                         country, india, language, tracked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                      (sid, plat, name, url, logo, time.time(), None, "", "", None, 0, ""))
            c.commit()
    else:
        with store._lock:
            c = _db()
            c.execute("UPDATE sc_channels SET tracked=1 WHERE sid=?", (sid,))
            c.commit()
    try:
        _follower_snapshot([sid])
    except Exception as e:
        print(f"First followers for {sid}: {str(e)[:100]}")
    return True


def _follower_snapshot(sids: list) -> int:
    """Today's follower count for Twitch / Kick channels into sc_chstats (subs column = followers)."""
    tw = [s.split(":", 1)[1] for s in sids if s.startswith("twitch:")]
    kk = [s.split(":", 1)[1] for s in sids if s.startswith("kick:")]
    got = {f"twitch:{k}": v for k, v in twitch_followers(tw).items()}
    for slug in kk:
        f = (kick_info(slug) or {}).get("followers_count") or ((kick_info(slug) or {}).get("followersCount"))
        if f is not None:
            got[f"kick:{slug}"] = int(f)
    if got:
        with store._lock:
            c = _db()
            c.executemany("INSERT OR REPLACE INTO sc_chstats VALUES (?,?,?,?,?,?)",
                          [(_day(), sid, n, None, None, int(time.time())) for sid, n in got.items()])
            c.commit()
    return len(got)


def followers_once(limit: int = 300) -> int:
    """Daily follower counts for Twitch/Kick channels: followed (tracked) ones first, then the most watched."""
    d = _day()
    since = (datetime.now(events.REPORT_TZ).date() - timedelta(days=30)).strftime("%Y-%m-%d")
    with store._lock:
        todo = [r[0] for r in _db().execute(
            """SELECT c.sid FROM sc_channels c LEFT JOIN (SELECT sid, SUM(hw) hw FROM sc_daily WHERE day>=? GROUP BY sid) d
               ON d.sid=c.sid WHERE c.platform IN ('twitch','kick') AND c.sid NOT IN (SELECT sid FROM sc_chstats WHERE day=?)
               ORDER BY COALESCE(c.tracked,0) DESC, COALESCE(d.hw,0) DESC LIMIT ?""", (since, d, limit)).fetchall()]
    return _follower_snapshot(todo) if todo else 0


# ---------- a channel's videos (uploads and past live streams) ----------

def _iso_dur(t: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", t or "")
    return sum(int(v or 0) * k for v, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else 0


def _yt_tab_all(cid: str, tab: str, since: float, pages: int = 12) -> list:
    """Every video on a channel tab back to `since`, following the tab's "load more" pages."""
    from tracker import scene
    r = events._http.get(f"https://www.youtube.com/channel/{cid}/{tab}", timeout=15,
                         headers={"User-Agent": events._UA, "Accept-Language": "en-US,en;q=0.9"},
                         cookies={"CONSENT": "YES+", "SOCS": "CAI"})
    r.raise_for_status()
    m = re.search(r'var ytInitialData\s*=\s*(\{.+?\})\s*;\s*</script>', r.text, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    out = _parse_tab(data)
    for _ in range(pages):
        if not out or min((x["ts"] or time.time()) for x in out) < since:
            break
        tok = scene._continuation(data)
        if not tok:
            break
        r = events._http.post("https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
                              json={"context": {"client": {"clientName": "WEB", "clientVersion": "2.20251001.00.00", "hl": "en", "gl": "US"}},
                                    "continuation": tok},
                              headers={"User-Agent": events._UA, "Content-Type": "application/json",
                                       "Origin": "https://www.youtube.com"}, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        more = _parse_tab(data)
        if not more:
            break
        out += more
    return out


def _playlist_ids(pid: str, since: float, key: str, pages: int = 20) -> list:
    """Video ids in a playlist (newest first) published since `since`. Missing playlists give []."""
    ids, tok = [], None
    for _ in range(pages):
        p = {"part": "contentDetails", "playlistId": pid, "maxResults": 50, "key": key, **({"pageToken": tok} if tok else {})}
        j = events._http.get("https://www.googleapis.com/youtube/v3/playlistItems", params=p, timeout=15).json()
        old = False
        for it in j.get("items") or []:
            pub = (it.get("contentDetails") or {}).get("videoPublishedAt")
            ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp() if pub else None
            if ts and ts < since:
                old = True
                continue
            ids.append(it["contentDetails"]["videoId"])
        tok = j.get("nextPageToken")
        if old or not tok:
            break
    return ids


def _api_videos(cid: str, since: float, key: str, pages: int = 20) -> list:
    """YouTube Data API: the uploads playlist (newest first) back to `since`, with exact dates, views, likes,
    comments and length. What kind each video is comes from YouTube's own per-channel playlists: UULV<id> holds the
    channel's live streams and UUSH<id> its Shorts. A premiere is a normal video (it's in neither), even though the
    API gives it live-stream details too. About 1 quota unit per 50 videos."""
    j = events._http.get("https://www.googleapis.com/youtube/v3/channels",
                         params={"part": "contentDetails", "id": cid, "key": key}, timeout=15).json()
    up = (((j.get("items") or [{}])[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    if not up:
        return []
    ids = _playlist_ids(up, since, key, pages)
    lives, shorts = set(_playlist_ids("UULV" + cid[2:], since, key, pages)), set(_playlist_ids("UUSH" + cid[2:], since, key, pages))
    out = []
    for i in range(0, len(ids), 50):
        j = events._http.get("https://www.googleapis.com/youtube/v3/videos",
                             params={"part": "snippet,statistics,contentDetails,liveStreamingDetails", "id": ",".join(ids[i:i + 50]),
                                     "key": key}, timeout=15).json()
        for v in j.get("items") or []:
            st, sn, ls = v.get("statistics") or {}, v.get("snippet") or {}, v.get("liveStreamingDetails") or {}
            pub = ls.get("actualStartTime") or sn.get("publishedAt")
            out.append({"id": v["id"], "title": sn.get("title") or "", "short": 1 if v["id"] in shorts else 0,
                        "ts": int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()) if pub else None,
                        "views": int(st["viewCount"]) if "viewCount" in st else None,
                        "likes": int(st["likeCount"]) if "likeCount" in st else None,
                        "comments": int(st["commentCount"]) if "commentCount" in st else None,
                        "secs": _iso_dur((v.get("contentDetails") or {}).get("duration")), "live": 1 if v["id"] in lives else 0, "approx": 0,
                        "cat": int(sn["categoryId"]) if str(sn.get("categoryId") or "").isdigit() else None})
    return out


def _tw_videos(login: str, since: float) -> list:
    """Twitch: past broadcasts, highlights and uploads (title, date, views, length). Twitch keeps past broadcasts for
    7 to 60 days, so older streams only appear if the streamer saved them as highlights."""
    u = (platforms._get("twitch", "https://api.twitch.tv/helix/users", {"login": login}).get("data") or [{}])[0]
    if not u.get("id"):
        return []
    out, cur = [], None
    for _ in range(10):
        j = platforms._get("twitch", "https://api.twitch.tv/helix/videos",
                           {"user_id": u["id"], "type": "all", "first": 100, **({"after": cur} if cur else {})})
        for v in j.get("data") or []:
            ts = int(datetime.fromisoformat(v["created_at"].replace("Z", "+00:00")).timestamp()) if v.get("created_at") else None
            if ts and ts < since:
                continue
            out.append({"id": "tw:" + v["id"], "title": v.get("title") or "", "ts": ts, "views": v.get("view_count"),
                        "likes": None, "comments": None, "secs": _dur(v.get("duration")), "live": 1 if v.get("type") == "archive" else 0,
                        "short": 0, "approx": 0, "url": v.get("url") or ""})
        cur = (j.get("pagination") or {}).get("cursor")
        if not cur:
            break
    return out


def _kick_videos(slug: str, since: float) -> list:
    """Kick: past broadcasts from kick.com's channel videos list (unofficial; Kick may block it)."""
    r = events._http.get(f"https://kick.com/api/v2/channels/{slug}/videos", timeout=12,
                         headers={"User-Agent": events._UA, "Accept": "application/json"})
    if r.status_code != 200:
        return []
    out = []
    for v in r.json() if isinstance(r.json(), list) else []:
        ls = v.get("livestream") or {}
        created = v.get("created_at") or ls.get("created_at") or ls.get("start_time")
        try:
            ts = int(datetime.fromisoformat(str(created).replace("Z", "+00:00").replace(" ", "T")).timestamp()) if created else None
        except ValueError:
            ts = None
        if ts and ts < since:
            continue
        uid = v.get("uuid") or v.get("id")
        out.append({"id": f"kk:{uid}", "title": ls.get("session_title") or v.get("title") or "", "ts": ts,
                    "views": v.get("views") or ls.get("views"), "likes": None, "comments": None,
                    "secs": int((ls.get("duration") or 0) / 1000) if (ls.get("duration") or 0) > 10000 else int(ls.get("duration") or 0),
                    "live": 1, "short": 0, "approx": 0, "url": f"https://kick.com/{slug}/videos/{uid}"})
    return out


_VBUSY = set()


def _refresh_videos(sid: str, full: bool):
    """Fetch the channel's videos (everything on a full pass, the last 60 days otherwise) and store them."""
    if sid in _VBUSY:
        return
    _VBUSY.add(sid)
    try:
        plat, _, ident = sid.partition(":")
        since = 0 if full else time.time() - 60 * 86400
        key = os.getenv("YOUTUBE_API_KEY")
        if plat == "yt":
            if key:
                vids = _api_videos(ident, since, key, pages=60 if full else 3)
            else:
                vids = [{**x, "live": 0, "approx": 1} for x in _yt_tab_all(ident, "videos", since, pages=30 if full else 3)]
                vids += [{**x, "live": 1, "approx": 1} for x in _yt_tab_all(ident, "streams", since, pages=15 if full else 2)]
        elif plat == "twitch":
            vids = _tw_videos(ident, since)
        elif plat == "kick":
            vids = _kick_videos(ident, since)
        else:
            vids = []
        now = int(time.time())
        from tracker import scene
        rows = [(v["id"], sid, v["ts"], v["title"], v.get("views"), v.get("likes"), v.get("comments"), v.get("secs") or 0,
                 v.get("live", 0), v.get("approx", 1), now, v.get("short", 0), v.get("url") or "",
                 scene.classify("", v.get("title") or ""), v.get("cat")) for v in vids if v.get("id")]
        with store._lock:
            c = _db()
            if rows:
                # without the API a date is only "3 days ago": keep the first (closer) estimate once we have one
                c.executemany("""INSERT INTO yt_videos (vid, sid, ts, title, views, likes, comments, secs, live, approx, updated, short, url, game, cat)
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(vid) DO UPDATE SET game=excluded.game,
                                 cat=COALESCE(excluded.cat, yt_videos.cat),
                                 title=excluded.title, views=excluded.views,
                                 likes=COALESCE(excluded.likes, yt_videos.likes), comments=COALESCE(excluded.comments, yt_videos.comments),
                                 secs=CASE WHEN excluded.secs>0 THEN excluded.secs ELSE yt_videos.secs END,
                                 live=CASE WHEN excluded.approx=0 THEN excluded.live ELSE MAX(excluded.live, yt_videos.live) END,
                                 short=CASE WHEN excluded.approx=0 THEN excluded.short ELSE yt_videos.short END,
                                 ts=CASE WHEN excluded.approx=0 OR yt_videos.ts IS NULL THEN excluded.ts ELSE yt_videos.ts END,
                                 approx=MIN(excluded.approx, yt_videos.approx), updated=excluded.updated,
                                 url=CASE WHEN excluded.url!='' THEN excluded.url ELSE yt_videos.url END""", rows)
            # what the channel makes: the game of most of its last 40 posts (for uploaders never seen live)
            gs = [g for (g,) in c.execute("SELECT game FROM yt_videos WHERE sid=? ORDER BY ts DESC LIMIT 40", (sid,))]
            named = [g for g in gs if g and g != "Other"]
            if named:
                top = max(set(named), key=named.count)
                if named.count(top) >= .3 * len(gs):
                    c.execute("UPDATE sc_channels SET game=? WHERE sid=? AND (COALESCE(game,'') IN ('', 'Other') OR last_live IS NULL)", (top, sid))
            cs = [k for (k,) in c.execute("SELECT cat FROM yt_videos WHERE sid=? AND cat IS NOT NULL ORDER BY ts DESC LIMIT 40", (sid,))]
            if len(cs) >= 3:
                c.execute("UPDATE sc_channels SET ytcat=? WHERE sid=?", (YT_CATS.get(max(set(cs), key=cs.count), ""), sid))
            c.commit()
        m = store.kv_get(f"vids:{sid}") or {}
        m["recent"] = now
        if full:
            m["full"] = now
        store.kv_set(f"vids:{sid}", m)
    except Exception as e:
        print(f"Videos of {sid}: {str(e)[:120]}")
    finally:
        _VBUSY.discard(sid)


def channel_videos(sid: str, force: bool = False) -> list:
    """Every stored video / Short / past stream of the channel. The first visit fetches the whole history (YouTube with
    YOUTUBE_API_KEY: up to 3,000 videos, exact; without it: what the channel tabs show, dates approximate). After that
    the page is served from the database at once, while the last 60 days are refreshed in the background every 6 hours
    and the whole history weekly."""
    m = store.kv_get(f"vids:{sid}") or {}
    now = time.time()
    if force:
        _refresh_videos(sid, full=True)
    elif not m.get("full"):
        # first visit: the last 60 days now (a second or two), the whole history in the background
        if not m.get("recent") and sid not in _VBUSY:
            _refresh_videos(sid, full=False)
        if sid not in _VBUSY:
            threading.Thread(target=_refresh_videos, args=(sid, True), daemon=True).start()
    elif now - m["full"] > 7 * 86400:
        threading.Thread(target=_refresh_videos, args=(sid, True), daemon=True).start()
    elif now - m.get("recent", 0) > 6 * 3600:
        threading.Thread(target=_refresh_videos, args=(sid, False), daemon=True).start()
    with store._lock:
        return [dict(r) for r in _db().execute("SELECT * FROM yt_videos WHERE sid=? ORDER BY ts DESC", (sid,))]


RANGES = {"7d": 7, "30d": 30, "90d": 90, "6m": 182, "ytd": None, "1y": 365, "all": 0,
          "1w": 7, "1m": 30, "3m": 91}                       # (old names still accepted)


def history_loading(sid: str) -> bool:
    return sid in _VBUSY or not (store.kv_get(f"vids:{sid}") or {}).get("full")


def prefetch_once(n: int = 5) -> int:
    """Pull the full video history of a few channels that don't have it yet (followed ones first, then the biggest),
    so their pages are complete before anyone opens them."""
    with store._lock:
        cand = [r[0] for r in _db().execute(
            """SELECT c.sid FROM sc_channels c LEFT JOIN (SELECT s.sid, s.subs FROM sc_chstats s JOIN
               (SELECT sid, MAX(day) d FROM sc_chstats GROUP BY sid) m ON m.sid=s.sid AND m.d=s.day) t ON t.sid=c.sid
               WHERE c.platform IN ('youtube','twitch','kick') ORDER BY COALESCE(c.tracked,0) DESC, COALESCE(t.subs,0) DESC LIMIT 2000""")]
    done = 0
    for sid in cand:
        if done >= n:
            break
        if (store.kv_get(f"vids:{sid}") or {}).get("full") or sid in _VBUSY:
            continue
        _refresh_videos(sid, full=True)
        done += 1
    return done


def videos_summary(sid: str, rng: str = "3m", kind: str = "all") -> dict:
    """Uploads and past live streams published in the range, with totals: count, views, average and median views per
    video, likes, comments, engagement ((likes + comments) / views) and the best video."""
    vids = channel_videos(sid)
    now = datetime.now(events.REPORT_TZ)
    days = RANGES.get(rng, 91)
    t0 = (datetime(now.year, 1, 1, tzinfo=events.REPORT_TZ).timestamp() if days is None else
          min((v["ts"] for v in vids if v["ts"]), default=time.time()) if days == 0 else time.time() - days * 86400)
    kind_of = lambda v: "live" if v["live"] else "shorts" if v.get("short") else "uploads"
    L = [v for v in vids if (v["ts"] or 0) >= t0 and (kind == "all" or kind_of(v) == kind)]
    views = [v["views"] or 0 for v in L]
    lk = [v for v in L if v["likes"] is not None]
    eng = (sum((v["likes"] or 0) + (v["comments"] or 0) for v in lk) / max(1, sum(v["views"] or 0 for v in lk))) if lk else None
    srt = sorted(views)
    return {"range": rng, "kind": kind, "since": int(t0), "count": len(L), "views": sum(views),
            "avg": round(sum(views) / len(L)) if L else 0, "median": srt[len(srt) // 2] if srt else 0,
            "likes": sum(v["likes"] or 0 for v in lk) if lk else None, "comments": sum(v["comments"] or 0 for v in lk) if lk else None,
            "engagement": round(100 * eng, 2) if eng is not None else None,
            "uploads": sum(1 for v in L if kind_of(v) == "uploads"), "lives": sum(1 for v in L if v["live"]),
            "shorts": sum(1 for v in L if kind_of(v) == "shorts"),
            "per_week": round(len(L) / max(1, (time.time() - t0) / 604800), 1),
            "best": max(L, key=lambda v: v["views"] or 0) if L else None,
            "exact": bool(os.getenv("YOUTUBE_API_KEY")), "oldest": min((v["ts"] for v in vids if v["ts"]), default=None),
            "loading": history_loading(sid), "insights": _insights(L, kind_of), **_chart(L, t0)}


def _insights(L: list, kind_of) -> dict:
    """Average views by weekday and time of day (IST) and by format, over every post in the range (exact dates only)."""
    P = [v for v in L if v["ts"] and not v["approx"]]
    if len(P) < 5:
        return {}
    def avg_by(f):
        m = {}
        for v in P:
            m.setdefault(f(v), []).append(v["views"] or 0)
        return {k: {"avg": round(sum(a) / len(a)), "n": len(a)} for k, a in m.items()}
    dt = lambda v: datetime.fromtimestamp(v["ts"], events.REPORT_TZ)
    slot = lambda h: "Late night (0-6)" if h < 6 else "Morning (6-12)" if h < 12 else "Afternoon (12-17)" if h < 17 else "Evening (17-21)" if h < 21 else "Night (21-24)"
    return {"weekday": avg_by(lambda v: dt(v).strftime("%a")), "time": avg_by(lambda v: slot(dt(v).hour)), "format": avg_by(kind_of)}


def _chart(L: list, t0: float) -> dict:
    """What the chart and the lists need. Up to ~120 posts: every post. More (long ranges, busy channels): one point
    per week or month (posts, total views, average per post), so the line stays readable; the lists then get the
    top posts by each measure instead of all of them."""
    span = time.time() - t0
    pts = [v for v in L if v["ts"]]
    if len(pts) <= 120:
        return {"bucket": "post", "videos": L}
    size = 30 * 86400 if span > 2 * 365 * 86400 else 7 * 86400
    b = {}
    for v in pts:
        k = int(v["ts"] // size * size)
        z = b.setdefault(k, {"ts": k, "posts": 0, "views": 0, "likes": 0, "comments": 0, "lk": 0})
        z["posts"] += 1
        z["views"] += v["views"] or 0
        if v["likes"] is not None:
            z["likes"] += v["likes"] or 0
            z["comments"] += v["comments"] or 0
            z["lk"] += v["views"] or 0
    series = [{**z, "avg": round(z["views"] / z["posts"]), "eng": round(100 * (z["likes"] + z["comments"]) / z["lk"], 2) if z["lk"] else None}
              for _, z in sorted(b.items())]
    keep = {}
    for key in (lambda v: v["views"] or 0, lambda v: v["likes"] or 0, lambda v: v["comments"] or 0,
                lambda v: ((v["likes"] or 0) + (v["comments"] or 0)) / v["views"] if v["views"] and v["likes"] is not None and v["views"] > 1000 else 0):
        for v in sorted(L, key=key, reverse=True)[:30]:
            keep[v["vid"]] = v
    return {"bucket": "month" if size > 7 * 86400 else "week", "series": series,
            "videos": sorted(keep.values(), key=lambda v: -(v["ts"] or 0))}


# ---------- discovery: grow the list of channels so ranks mean something ----------

DISCOVER = ["BGMI", "Free Fire", "GTA 5 RP", "Valorant", "Minecraft", "Fortnite", "COD Mobile", "PUBG Mobile", "Roblox",
            "Clash of Clans", "Pokemon Unite", "Mobile Legends", "Counter Strike 2", "League of Legends", "Genshin Impact",
            "gaming", "esports", "live gaming", "news", "music", "comedy", "vlog", "tech", "cricket", "devotional",
            "podcast", "education", "cooking", "movie review", "kids"]
DISCOVER_GL = [("IN", " india"), ("IN", " tamil"), ("IN", " telugu"), ("IN", " hindi"), ("US", ""), ("BR", ""), ("ID", ""),
               ("PH", ""), ("PK", ""), ("BD", ""), ("GB", "")]


def discover_once(n: int = 2) -> int:
    """A couple of YouTube channel searches per run (rotating through games/topics x countries); new channels are
    added untracked and picked up by the daily stats. Free: uses YouTube's site search, not the API allowance."""
    i = store.kv_get("discover_i") or 0
    added = 0
    for k in range(n):
        q, (gl, suffix) = DISCOVER[(i + k) % len(DISCOVER)], DISCOVER_GL[((i + k) // len(DISCOVER)) % len(DISCOVER_GL)]
        try:
            res = yt_channel_search(q + suffix, gl)
        except Exception:
            continue
        with store._lock:
            c = _db()
            for x in res:
                cur = c.execute("""INSERT OR IGNORE INTO sc_channels (sid, platform, name, url, logo, first_seen, last_live, title, game,
                                   country, india, language, tracked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                                (x["sid"], "youtube", x["name"], f"https://www.youtube.com/channel/{x['sid'][3:]}", x["logo"], time.time(),
                                 None, "", "", None, 0, ""))
                added += cur.rowcount
            c.commit()
    store.kv_set("discover_i", i + n)
    return added


# ---------- the same creator on several platforms ----------

_NN = {"at": 0, "map": {}}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def linked(sid: str) -> list:
    """The same creator's channels on the other platforms: links set by hand (track.py scene link ...), else channels
    whose name matches exactly once spaces and symbols are dropped (e.g. "Soul Aman" on YouTube and "soulaman" on Kick)."""
    groups = store.kv_get("chan_links") or []
    for g in groups:
        if sid in g:
            others = [x for x in g if x != sid]
            break
    else:
        if time.time() - _NN["at"] > 600:
            m = {}
            with store._lock:
                for s_, n in _db().execute("SELECT sid, name FROM sc_channels"):
                    k = _norm(n)
                    if len(k) >= 5:
                        m.setdefault(k, []).append(s_)
            _NN.update(at=time.time(), map=m)
        with store._lock:
            row = _db().execute("SELECT name FROM sc_channels WHERE sid=?", (sid,)).fetchone()
        mine = sid.split(":", 1)[0]
        others = [x for x in _NN["map"].get(_norm(row[0] if row else ""), []) if x.split(":", 1)[0] != mine]
        if sid.startswith(("kick:", "twitch:")):                    # a Kick slug / Twitch login equal to a name elsewhere
            others += [x for x in _NN["map"].get(_norm(sid.split(":", 1)[1]), []) if x.split(":", 1)[0] != mine and x not in others]
    if not others:
        return []
    with store._lock:
        rows = _db().execute(f"SELECT sid, platform, name, logo FROM sc_channels WHERE sid IN ({','.join('?' * len(others))})", others).fetchall()
    best = {}
    for r in rows:                                               # one per platform
        best.setdefault(r["platform"], dict(r))
    return list(best.values())


def link(a: str, b: str, on: bool = True) -> list:
    groups = [set(g) for g in (store.kv_get("chan_links") or [])]
    ga = next((g for g in groups if a in g), None)
    gb = next((g for g in groups if b in g), None)
    if on:
        new = (ga or {a}) | (gb or {b})
        groups = [g for g in groups if g is not ga and g is not gb] + [new]
    else:
        for g in groups:
            g.discard(b if a in g else a)
        groups = [g for g in groups if len(g) > 1]
    store.kv_set("chan_links", [sorted(g) for g in groups])
    return [sorted(g) for g in groups]


# ---------- home page and game pages: channels and videos, not only live ----------

def _latest_gains(day_back: int = 1) -> dict:
    """{sid: (views gained, subs gained)} between each channel's last two daily snapshots (the newest no older than
    two days)."""
    d0 = (datetime.now(events.REPORT_TZ).date() - timedelta(days=2)).strftime("%Y-%m-%d")
    out = {}
    with store._lock:
        rows = _db().execute("SELECT sid, day, subs, views FROM sc_chstats WHERE day >= ? ORDER BY sid, day",
                             ((datetime.now(events.REPORT_TZ).date() - timedelta(days=4)).strftime("%Y-%m-%d"),)).fetchall()
    by = {}
    for r in rows:
        by.setdefault(r[0], []).append(r)
    for sid, L in by.items():
        if len(L) >= 2 and L[-1][1] >= d0:
            a, b = L[-2], L[-1]
            gap = max(1, (datetime.strptime(b[1], "%Y-%m-%d") - datetime.strptime(a[1], "%Y-%m-%d")).days)   # per day
            ok = a[3] is not None and b[3] is not None and 0 <= b[3] - a[3] <= 0.25 * max(b[3], 1)   # skip misread snapshots
            out[sid] = (round((b[3] - a[3]) / gap) if ok else None,
                        round((b[2] - a[2]) / gap) if a[2] is not None and b[2] is not None and abs(b[2] - a[2]) <= .25 * max(b[2], 1000) else None)
    return out


def _chan_rows(sids: list) -> dict:
    if not sids:
        return {}
    with store._lock:
        return {r["sid"]: dict(r) for r in _db().execute(
            f"SELECT sid, platform, name, logo, url, game, COALESCE(NULLIF(ytcat,''), topic) topic, country, COALESCE(india,0) india FROM sc_channels WHERE sid IN ({','.join('?' * len(sids))})", sids)}


def home_lists(region: str = "global", game: str = "", n: int = 25, topic: str = "") -> dict:
    """Top channels by views gained in their last day (YouTube) and the most-viewed videos posted in the last 3 days,
    for a region and optionally one game or one YouTube category."""
    g = _latest_gains()
    ch = _chan_rows([s for s, (v, _) in g.items() if v])
    top = []
    for sid, (v, sg) in sorted(g.items(), key=lambda kv: -(kv[1][0] or 0)):
        c = ch.get(sid)
        if not c or not v or (region == "in" and not c["india"]) or (game and c["game"] != game) or (topic and c["topic"] != topic):
            continue
        top.append({**c, "views_day": v, "subs_day": sg})
        if len(top) >= n:
            break
    subs = []
    for sid, (v, sg) in sorted(g.items(), key=lambda kv: -(kv[1][1] or 0)):
        if not sg or sg <= 0:
            break
        c = ch.get(sid) or _chan_rows([sid]).get(sid)
        if not c or (region == "in" and not c["india"]) or (game and c["game"] != game) or (topic and c["topic"] != topic):
            continue
        subs.append({**c, "views_day": v, "subs_day": sg})
        if len(subs) >= n:
            break
    t0 = time.time() - 3 * 86400
    q = """SELECT v.vid, v.sid, v.title, v.ts, v.views, v.likes, v.comments, v.live, v.short, v.url, v.game, c.name, c.logo, c.platform
           FROM yt_videos v JOIN sc_channels c ON c.sid=v.sid WHERE v.ts >= ? AND v.approx=0"""
    a = [t0]
    if region == "in":
        q += " AND COALESCE(c.india,0)=1"
    if game:
        q += " AND v.game=?"
        a.append(game)
    if topic:
        ids = [k for k, v in YT_CATS.items() if v == topic]
        q += f" AND (v.cat IN ({','.join('?' * len(ids)) or 'NULL'}) OR (v.cat IS NULL AND COALESCE(NULLIF(c.ytcat,''), c.topic)=?))"
        a += ids + [topic]
    with store._lock:
        vids = [dict(r) for r in _db().execute(q + " ORDER BY v.views DESC LIMIT ?", (*a, n))]
        live_sids = [r[0] for r in _db().execute("SELECT sid FROM sc_channels WHERE COALESCE(NULLIF(ytcat,''), topic)=? AND last_live>?",
                                                  (topic, time.time() - 2 * 86400))] if topic else []
    return {"channels_today": top, "subs_today": subs, "trending": vids, "live_sids": live_sids}


def category_channels(game: str, region: str = "global", n: int = 25, topic: str = "") -> list:
    """Channels whose main game is this one, or in this YouTube category (streamers and uploaders), biggest first,
    with today's views gained."""
    with store._lock:
        rows = [dict(r) for r in _db().execute(
            """SELECT c.sid, c.platform, c.name, c.logo, c.url, c.game, COALESCE(c.india,0) india, s.subs, s.views
               FROM sc_channels c JOIN (SELECT s.sid, s.subs, s.views FROM sc_chstats s JOIN (SELECT sid, MAX(day) d FROM sc_chstats GROUP BY sid) m
               ON m.sid=s.sid AND m.d=s.day) s ON s.sid=c.sid WHERE """ + ("COALESCE(NULLIF(c.ytcat,''), c.topic)=?" if topic else "c.game=?") +
            (" AND COALESCE(c.india,0)=1" if region == "in" else "") + " ORDER BY COALESCE(s.subs,0) DESC LIMIT ?", (topic or game, n))]
    g = _latest_gains()
    for r in rows:
        r["views_day"] = (g.get(r["sid"]) or (None, None))[0]
    return rows


def compare(sids: list, rng: str = "90d") -> dict:
    """Side by side: lifetime counters, posts in the range, live numbers, ranks and a common chart (average views
    per post per period)."""
    from tracker import scene
    days = RANGES.get(rng, 90) or 0
    t0 = (datetime(datetime.now().year, 1, 1).timestamp() if RANGES.get(rng, 90) is None else
          time.time() - (days or 3650) * 86400)
    size = max(86400, (time.time() - t0) / 14)                  # ~14 points whatever the range
    out, missing = [], []
    for sid in sids[:4]:
        try:
            ch = scene.channel(sid)
        except Exception:
            ch = {}
        if not ch:
            missing.append(sid)
            continue
        sm = videos_summary(sid, rng)
        snaps = (ch.get("views") or {}).get("snapshots") or []
        stats = ch.get("stats") or ({"subs": snaps[-1].get("subs")} if snaps and snaps[-1].get("subs") is not None else None)
        vids = channel_videos(sid)
        b = {}
        for v in vids:
            if v["ts"] and v["ts"] >= t0:
                k = int((v["ts"] - t0) // size)
                z = b.setdefault(k, [0, 0])
                z[0] += v["views"] or 0
                z[1] += 1
        series = [[int(t0 + (k + .5) * size), round(z[0] / z[1])] for k, z in sorted(b.items())]
        P = ch.get("periods") or {}
        out.append({"sid": sid, "name": ch.get("name"), "logo": ch.get("logo"), "platform": ch.get("platform"), "url": ch.get("url"),
                    "country": ch.get("country"), "stats": stats, "views": (ch.get("views") or {}).get("gains", [])[-30:],
                    "posts": {k: sm.get(k) for k in ("count", "views", "avg", "median", "engagement", "per_week", "likes", "comments")},
                    "live": {"peak": (P.get("30d") or {}).get("peak", 0), "avg": (P.get("30d") or {}).get("avg", 0),
                             "hw": (P.get("30d") or {}).get("hw", 0), "hours": (P.get("30d") or {}).get("hours", 0),
                             "peak_all": (P.get("all") or {}).get("peak", 0)},
                    "ranks": ch.get("ranks") or [], "series": series, "loading": sm.get("loading")})
    return {"range": rng, "since": int(t0), "channels": out, "missing": missing}
