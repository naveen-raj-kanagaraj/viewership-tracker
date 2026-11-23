"""Is a Kick / Twitch channel's chat Indian? The strongest sign of an Indian streamer when the title says nothing
(Kick and Twitch give no country, and many Indian streamers title in English).

chat.py hands every chat message it reads to add(). Each message is judged on the spot and only two counters per
channel are kept: messages in Hindi / Hinglish / an Indian script, and messages in anything else. No text is stored.
Counts are halved once a channel passes KEEP messages, so they follow the channel's recent chat.
"""
import re
import threading
import time
import unicodedata

from tracker import store

KEEP = 3000
MIN_MSGS = 150            # judged after this many messages with words in them
IND_SHARE = 0.20          # 20%+ of messages Indian: an Indian channel
NOT_SHARE = 0.03          # under 3% Indian (after 300+ messages): not an Indian channel

# Hindi in English letters: words that are Hindi and nothing else ('hai' alone is also Italian, so it needs a partner)
HI_STRONG = set("""bhai bhaiya bhaiyo bhaiyon kya kyu kyun nahi nhi nahin bahut bohot bhot yaar yr accha acha achha kaise
kaisa matlab kuch karo karna raha rahi rha rhi mera meri tera teri apna apni wala wali wale haan aur hain bilkul pakka
jaldi dekho bolo suno chalo sabko sahi mast bekar bakwas ghatiya zabardast badhiya shandaar kamaal""".split())
HI_WEAK = set("hai ho toh ka ki ke ko se me mein tum aap yeh ye wo woh bhi sab par pe tha thi".split())
_IND = re.compile(r"[ऀ-ॿ਀-ൿ]")         # Devanagari, Gurmukhi ... Malayalam (not Bengali: Bangladesh)
_WORD = re.compile(r"[a-z]+")

_C = {}                   # sid -> [indian, other]
_L = threading.Lock()
_DIRTY = set()


def kind(text: str):
    """'in' (Hindi / Hinglish / Indian script), 'other' (words in anything else) or None (emotes, links, numbers)."""
    t = text or ""
    ind = sum(1 for ch in _IND.findall(t) if unicodedata.category(ch)[0] == "L")
    if ind >= 2:
        return "in"
    words = _WORD.findall(t.lower())
    if not words and not any(ch.isalpha() for ch in t):
        return None
    w = set(words)
    if w & HI_STRONG or len(w & HI_WEAK) >= 2:
        return "in"
    if sum(1 for x in words if len(x) >= 2) < 2 and not any(ch.isalpha() and not ch.isascii() for ch in t):
        return None                                   # 'gg', 'KEKW', 'w': one word or an emote says nothing
    return "other"


WANT = set()              # channels whose chat is judged: possibly Indian ones (chat.py fills it)
_N = {}


def add(sid: str, text: str):
    if sid not in WANT:
        return
    n = _N[sid] = _N.get(sid, 0) + 1
    c = _C.get(sid)
    if c and c[0] + c[1] >= 1000 and n % 5:
        return                                        # plenty read already: every 5th message keeps it current
    k = kind(text)
    if k is None:
        return
    with _L:
        c = _C.setdefault(sid, [0, 0])
        c[0 if k == "in" else 1] += 1
        if c[0] + c[1] > KEEP:
            c[0], c[1] = c[0] // 2, c[1] // 2
        _DIRTY.add(sid)


def verdict(sid: str):
    """True: the chat is Indian; False: clearly not; None: not enough chat read yet."""
    with _L:
        c = _C.get(sid)
    if not c:
        return None
    n = c[0] + c[1]
    if n < MIN_MSGS:
        return None
    share = c[0] / n
    if share >= IND_SHARE:
        return True
    if n >= 300 and share < NOT_SHARE:
        return False
    return None


def counts(sid: str):
    with _L:
        return tuple(_C.get(sid) or (0, 0))


# YouTube: the live chat the site already reads (chatstats, Super Chat reader) records each message's language
_YT = {}                  # sid -> [indian, other] over the last 30 days
_YT_IND = {"Hindi / Marathi (Devanagari)", "Punjabi", "Gujarati", "Odia", "Tamil", "Telugu", "Kannada", "Malayalam",
           "Hinglish"}


def yt_load():
    """Each YouTube channel's chat languages over its streams of the last 30 days (refreshed hourly)."""
    import json
    out = {}
    try:
        with store.reading():
            c = store.conn()
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='chat_stream'").fetchone():
                return
            since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 30 * 86400))
            for sid, langs in c.execute("SELECT sid, langs FROM chat_stream WHERE day >= ?", (since,)):
                try:
                    L = json.loads(langs or "{}")
                except ValueError:
                    continue
                a = out.setdefault(sid, [0, 0])
                for k, n in L.items():
                    if k in _YT_IND:
                        a[0] += n
                    elif k:
                        a[1] += n
    except Exception as e:
        print(f"YouTube chat languages: {str(e)[:100]}")
        return
    _YT.clear()
    _YT.update(out)


def yt_verdict(sid: str):
    c = _YT.get(sid)
    if not c or c[0] + c[1] < MIN_MSGS:
        return None
    share = c[0] / (c[0] + c[1])
    return True if share >= IND_SHARE else False if c[0] + c[1] >= 300 and share < NOT_SHARE else None


SCHEMA = "CREATE TABLE IF NOT EXISTS chat_lang (sid TEXT PRIMARY KEY, ind INTEGER, oth INTEGER, updated INTEGER)"


def load():
    try:
        with store._lock:
            store.main().execute(SCHEMA)
            store.main().commit()
        with store.reading():
            rows = store.conn().execute("SELECT sid, ind, oth FROM chat_lang").fetchall()
        with _L:
            for sid, a, b in rows:
                _C.setdefault(sid, [a, b])
    except Exception as e:
        print(f"Chat languages load: {str(e)[:100]}")


def save():
    with _L:
        rows = [(sid, _C[sid][0], _C[sid][1], int(time.time())) for sid in _DIRTY if sid in _C]
        _DIRTY.clear()
    if rows:
        store.write_slices("INSERT INTO chat_lang VALUES (?,?,?,?) ON CONFLICT(sid) DO UPDATE SET ind=excluded.ind, "
                           "oth=excluded.oth, updated=excluded.updated", rows, n=500)


def run_forever():
    load()
    while True:
        time.sleep(300)
        try:
            save()
        except Exception as e:
            print(f"Chat languages save: {str(e)[:100]}")


def start():
    threading.Thread(target=run_forever, daemon=True, name="chat-lang").start()
