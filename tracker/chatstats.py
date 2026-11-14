"""Live chat analytics for every YouTube stream whose chat the site reads (ytextra._poll feeds add()).

Per stream (chat_stream): messages, unique chatters, top words, top emotes, chat language mix (by writing script,
plus Hinglish for Hindi written in English letters), mood (positive / negative / neutral share from a word and emoji
list; approximate by nature).
Audience (chat_aud): a salted one-way hash of each chatter's channel id, per channel, for the last 30 days. Only a
fixed quarter of all hashes is kept (the same quarter for every channel, so overlaps stay accurate) and counts are
scaled up by 4. Nobody's name or id is stored or shown; only totals and shares.
Overlap (chat_overlap): daily, for the biggest chat audiences: what share of channel A's chatters also chatted with
channel B in the last 30 days.
"""
import hashlib
import json
import os
import re
import secrets
import threading
import time
from collections import Counter

from tracker import store

SAMPLE = 4                          # keep hashes where h % SAMPLE == 0
AUD_DAYS = 30
OVERLAP_TOP = int(os.getenv("OVERLAP_TOP", "300"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_stream (vid TEXT PRIMARY KEY, sid TEXT, day TEXT, msgs INTEGER, chatters INTEGER,
    words TEXT, emotes TEXT, langs TEXT, pos INTEGER, neg INTEGER, neu INTEGER, first_ts INTEGER, last_ts INTEGER,
    updated INTEGER);
CREATE INDEX IF NOT EXISTS chat_stream_sid ON chat_stream(sid, day);
CREATE TABLE IF NOT EXISTS chat_aud (sid TEXT, h INTEGER, day TEXT, PRIMARY KEY (sid, h));
CREATE INDEX IF NOT EXISTS chat_aud_h ON chat_aud(h);
CREATE TABLE IF NOT EXISTS chat_overlap (a TEXT, b TEXT, shared INTEGER, pct REAL, updated INTEGER, PRIMARY KEY (a, b));
"""
_ready = False
_ACC = {}                           # vid -> accumulator while the stream is live
_LOCK = threading.Lock()

STOP = set("""the and you for are but not this that with have was what your all can just how why who its it's
get got will lol yes yeah you're dont don't she him her his they them then than too very from out our has had were
when there here been also into more some like one two hai hain bhai bro kya nahi nhi aur toh hi ho ka ki ke ko se me
mein main tum aap yeh ye wo woh kar karo raha rahe rha kuch sab bhi koi par pe tha thi hua hue gaya gya bas abhi""".split())
POS = set("""love loved lovely best great good nice awesome amazing op gg ggs wow wp pog poggers lit fire goat legend
king queen super superb mast jhakaas zabardast badhiya bdhiya shandaar kamaal kamal mazaa maza beautiful insane epic
congrats congratulations thanks thank respect proud happy haha hahaha lmao funny""".split())
NEG = set("""hate worst bad trash boring lag lagging scam fake noob cringe sad angry stupid idiot useless waste
bekar bakwas ghatiya chor cheater cheat toxic disappointed unfair rigged fraud""".split())
POS_E = set("😂🤣❤️😍🔥👏💯😁😀😃😄😊🥰😘💖💕🙏🎉🥳🤩👍🫡💪❤🩷💙💚")
NEG_E = set("😡🤬😠👎💩😢😭😤🤮😒🙄")
SCRIPTS = [("Hindi / Marathi (Devanagari)", "ऀ", "ॿ"), ("Bengali", "ঀ", "৿"), ("Punjabi", "਀", "੿"),
           ("Gujarati", "઀", "૿"), ("Odia", "଀", "୿"), ("Tamil", "஀", "௿"),
           ("Telugu", "ఀ", "౿"), ("Kannada", "ಀ", "೿"), ("Malayalam", "ഀ", "ൿ"),
           ("Arabic / Urdu", "؀", "ۿ"), ("Thai", "฀", "๿"), ("Korean", "가", "힯"),
           ("Japanese", "぀", "ヿ"), ("Chinese", "一", "鿿"), ("Russian (Cyrillic)", "Ѐ", "ӿ")]
HINGLISH = set("""hai hain bhai kya nahi nhi aur kaise kaisa kaun kyun kyu acha accha bahut bohot bhot yaar yr matlab
haan ha nahin karo kar raha rahi kuch sab bhi abhi tum aap mera meri tera teri apna wala wali ji""".split())
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿❤]")
WORD = re.compile(r"[^\W\d_]{3,}", re.U)


def _db():
    global _ready
    from tracker import ytextra
    c = ytextra._db()
    if not _ready:
        c = store.main()          # tables are made on the read-write connection
        c.executescript(SCHEMA)
        c.commit()
        _ready = True
    return store.conn()


def _salt() -> bytes:
    s = os.getenv("CHAT_SALT") or store.kv_get("chat_salt")
    if not s:
        s = secrets.token_hex(16)
        store.kv_set("chat_salt", s)
    return s.encode()


_SALT = None


def _h(author_id: str) -> int:
    global _SALT
    if _SALT is None:
        _SALT = _salt()
    return int.from_bytes(hashlib.blake2b(_SALT + author_id.encode(), digest_size=7).digest(), "big")


def lang_of(text: str) -> str:
    counts = Counter()
    for ch in text:
        if ch.isalpha():
            for name, lo, hi in SCRIPTS:
                if lo <= ch <= hi:
                    counts[name] += 1
                    break
            else:
                if ch.isascii():
                    counts["latin"] += 1
    if not counts:
        return ""
    top = counts.most_common(1)[0][0]
    if top != "latin":
        return top
    words = set(w.lower() for w in WORD.findall(text))
    return "Hinglish" if words & HINGLISH else "English / other Latin"


def mood_of(words: list, emojis: list) -> int:
    """1 positive, -1 negative, 0 neutral."""
    p = sum(w in POS for w in words) + sum(e in POS_E for e in emojis)
    n = sum(w in NEG for w in words) + sum(e in NEG_E for e in emojis)
    return 1 if p > n else -1 if n > p else 0


def _message(it: dict):
    """(author id, text, [emote names]) of a chat message item, or None."""
    for key in ("liveChatTextMessageRenderer", "liveChatPaidMessageRenderer"):
        r = it.get(key)
        if r:
            text, emotes = [], []
            for run in ((r.get("message") or {}).get("runs") or []):
                if "text" in run:
                    text.append(run["text"])
                elif run.get("emoji"):
                    e = run["emoji"]
                    sc = (e.get("shortcuts") or [None])[0]
                    emotes.append(sc or e.get("emojiId") or "")
            return r.get("authorExternalChannelId") or "", "".join(text), [e for e in emotes if e]
    return None


def add(vid: str, sid: str, actions: list):
    from tracker import ytextra
    with _LOCK:
        a = _ACC.get(vid)
        if a is None:
            a = _ACC[vid] = {"sid": sid, "day": ytextra._day(), "msgs": 0, "who": set(), "words": Counter(), "emotes": Counter(),
                             "langs": Counter(), "pos": 0, "neg": 0, "neu": 0, "first": 0, "last": 0, "aud": set(), "base": None}
        for act in actions or []:
            it = (act.get("addChatItemAction") or {}).get("item") or {}
            m = _message(it)
            if not m:
                continue
            author, text, emotes = m
            ts = 0
            for r in it.values():
                if isinstance(r, dict) and r.get("timestampUsec"):
                    ts = int(r["timestampUsec"]) // 1_000_000
            a["msgs"] += 1
            a["first"] = a["first"] or ts
            a["last"] = max(a["last"], ts)
            if author:
                h = _h(author)
                a["who"].add(h)
                if h % SAMPLE == 0:
                    a["aud"].add(h)
            words = [w.lower() for w in WORD.findall(text)]
            uni = EMOJI.findall(text)
            a["words"].update(w for w in words if w not in STOP and len(w) <= 20)
            a["emotes"].update(emotes + uni)
            lg = lang_of(text)
            if lg:
                a["langs"][lg] += 1
            md = mood_of(words, uni + [e.strip(":") for e in emotes])
            a["pos" if md > 0 else "neg" if md < 0 else "neu"] += 1


def flush(ended_after: int = 900):
    """Write accumulators to the database; drop streams with no new chat for ended_after seconds."""
    from tracker import ytextra
    now = int(time.time())
    with _LOCK:
        items = list(_ACC.items())
    rows, aud = [], []
    for vid, a in items:
        if not a["msgs"]:
            continue
        if a["base"] is None:                     # restarted mid-stream: carry on from what was saved
            with store._lock:
                r = _db().execute("SELECT * FROM chat_stream WHERE vid=?", (vid,)).fetchone()
            a["base"] = dict(r) if r else {}
        b = a["base"]
        bw = Counter(json.loads(b.get("words") or "{}"))
        be = Counter(json.loads(b.get("emotes") or "{}"))
        bl = Counter(json.loads(b.get("langs") or "{}"))
        rows.append((vid, a["sid"], b.get("day") or a["day"], (b.get("msgs") or 0) + a["msgs"],
                     max(b.get("chatters") or 0, len(a["who"])),
                     json.dumps(dict((bw + a["words"]).most_common(40)), ensure_ascii=False),
                     json.dumps(dict((be + a["emotes"]).most_common(25)), ensure_ascii=False),
                     json.dumps(dict(bl + a["langs"]), ensure_ascii=False),
                     (b.get("pos") or 0) + a["pos"], (b.get("neg") or 0) + a["neg"], (b.get("neu") or 0) + a["neu"],
                     b.get("first_ts") or a["first"], max(b.get("last_ts") or 0, a["last"]), now))
        aud += [(a["sid"], h, a["day"]) for h in a["aud"]]
        a["aud"] = set()
    if not rows:
        return 0
    with store._lock:
        c = _db()
        c.executemany("INSERT OR REPLACE INTO chat_stream VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        c.executemany("INSERT INTO chat_aud VALUES (?,?,?) ON CONFLICT(sid, h) DO UPDATE SET day=excluded.day", aud)
        c.commit()
    with _LOCK:
        for vid, a in items:
            if now - (a["last"] or now) > ended_after and _ACC.get(vid) is a:
                del _ACC[vid]
    return len(rows)


def overlap_once() -> int:
    """Shares of audience between the OVERLAP_TOP biggest chat audiences of the last 30 days."""
    from tracker import ytextra
    since = ytextra._day(time.time() - AUD_DAYS * 86400)
    with store._lock:
        c = _db()
        c.execute("DELETE FROM chat_aud WHERE day<?", (since,))
        top = [r[0] for r in c.execute("SELECT sid FROM chat_aud GROUP BY sid ORDER BY COUNT(*) DESC LIMIT ?", (OVERLAP_TOP,))]
        if len(top) < 2:
            c.commit()
            return 0
        q = ",".join("?" * len(top))
        size = dict(c.execute(f"SELECT sid, COUNT(*) FROM chat_aud WHERE sid IN ({q}) GROUP BY sid", top).fetchall())
        pairs = c.execute(f"""SELECT a.sid, b.sid, COUNT(*) FROM chat_aud a JOIN chat_aud b ON a.h=b.h AND a.sid<>b.sid
                              WHERE a.sid IN ({q}) AND b.sid IN ({q}) GROUP BY a.sid, b.sid""", top + top).fetchall()
        now = int(time.time())
        c.execute("DELETE FROM chat_overlap")
        c.executemany("INSERT INTO chat_overlap VALUES (?,?,?,?,?)",
                      [(a, b, n * SAMPLE, n / size[a], now) for a, b, n in pairs if size.get(a)])
        c.commit()
    return len(pairs)


MEMBER_PRICE_USD = {"in": 0.71, "world": 4.99}   # lowest common membership level: Rs 59 in India, $4.99 elsewhere


def summary(sid: str, days: int = 30) -> dict:
    """Chat and viewer-spending summary of a channel's streams over the last `days` days."""
    from tracker import ytextra
    since = ytextra._day(time.time() - days * 86400)
    with store._lock:
        c = _db()
        rows = c.execute("SELECT * FROM chat_stream WHERE sid=? AND day>=?", (sid, since)).fetchall()
        paid = c.execute("""SELECT kind, COUNT(*), SUM(n), SUM(usd), SUM(inr) FROM sc_superchat WHERE sid=? AND day>=?
                            GROUP BY kind""", (sid, since)).fetchall()
        aud = c.execute("SELECT COUNT(*) FROM chat_aud WHERE sid=? AND day>=?", (sid, since)).fetchone()[0]
        ov = c.execute("""SELECT o.b, o.pct, o.shared, ch.name, ch.logo FROM chat_overlap o LEFT JOIN sc_channels ch ON ch.sid=o.b
                          WHERE o.a=? ORDER BY o.pct DESC LIMIT 8""", (sid,)).fetchall()
        india = (c.execute("SELECT COALESCE(india,0) FROM sc_channels WHERE sid=?", (sid,)).fetchone() or [0])[0]
    words, emotes, langs = Counter(), Counter(), Counter()
    msgs = chatters = pos = neg = neu = secs = 0
    for r in rows:
        words += Counter(json.loads(r["words"] or "{}"))
        emotes += Counter(json.loads(r["emotes"] or "{}"))
        langs += Counter(json.loads(r["langs"] or "{}"))
        msgs += r["msgs"] or 0
        chatters += r["chatters"] or 0
        pos, neg, neu = pos + (r["pos"] or 0), neg + (r["neg"] or 0), neu + (r["neu"] or 0)
        secs += max(0, (r["last_ts"] or 0) - (r["first_ts"] or 0))
    p = {k: {"count": n or 0, "units": u or 0, "usd": round(usd or 0, 2), "inr": round(inr or 0)} for k, n, u, usd, inr in paid}
    price = MEMBER_PRICE_USD["in" if india else "world"]
    new_members = p.get("member", {}).get("count", 0)
    gifted = p.get("gift", {}).get("units", 0)
    member_est = round((new_members + gifted) * price, 2)
    tot_l = sum(langs.values()) or 1
    tot_m = (pos + neg + neu) or 1
    return {"days": days, "streams": len(rows), "messages": msgs, "msgs_per_hour": round(msgs / (secs / 3600), 1) if secs > 600 else None,
            "avg_chatters": round(chatters / len(rows)) if rows else 0, "unique_chatters": aud * SAMPLE,
            "languages": [{"name": k, "pct": round(v / tot_l, 3)} for k, v in langs.most_common(8)],
            "mood": {"positive": round(pos / tot_m, 3), "negative": round(neg / tot_m, 3), "neutral": round(neu / tot_m, 3)},
            "words": [k for k, _ in words.most_common(25)], "emotes": [k for k, _ in emotes.most_common(15)],
            "spending": {"superchat": p.get("superchat", {}), "sticker": p.get("sticker", {}),
                         "new_members": new_members, "renewals": p.get("milestone", {}).get("count", 0), "gifted": gifted,
                         "members_usd_est": member_est, "member_price_usd": price,
                         "total_usd": round(p.get("superchat", {}).get("usd", 0) + p.get("sticker", {}).get("usd", 0) + member_est, 2)},
            "overlap": [{"sid": b, "name": n or b, "logo": lg or "", "pct": round(pc, 3), "shared": sh} for b, pc, sh, n, lg in ov]}


def run_forever():
    last_overlap = 0
    while True:
        time.sleep(300)
        try:
            flush()
        except Exception as e:
            print(f"Chat stats: {str(e)[:150]}")
        if time.time() - last_overlap > 24 * 3600:
            try:
                overlap_once()
                last_overlap = time.time()
            except Exception as e:
                print(f"Chat overlap: {str(e)[:150]}")


def start():
    threading.Thread(target=run_forever, daemon=True).start()
