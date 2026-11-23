"""Chat speed of live streams (messages per second), the fast signal for Moments.

    Twitch   anonymous read-only IRC (irc.chat.twitch.tv:6697, user justinfan...), the top CHAT_TWITCH channels.
             Also sees raids (USERNOTICE msg-id=raid), so a raid's viewer jump isn't taken for a highlight.
    Kick     Kick's chat websocket (Centrifugo with a guest token, as kick.com does; unofficial, may change), the top CHAT_KICK
             channels. Needs each channel's chatroom id from kick.com/api/v2/channels/<slug>; if Kick blocks that,
             Kick moments fall back to viewers only.
    YouTube  counted from the live chat already read for Super Chats (ytextra), the top SUPERCHAT_TOP streams.

Only counts are kept (per 5-second bucket, for the last 40 minutes); message text is never stored.
Standard library only (socket + ssl), so the server needs no new packages.
"""
import base64
import json
import os
import random
import re
import socket
import ssl
import struct
import threading
import time
from collections import deque

from tracker import events, langsig, platforms

CHAT_TWITCH = int(os.getenv("CHAT_TWITCH", "150"))
CHAT_KICK = int(os.getenv("CHAT_KICK", "80"))
CHAT_IN = int(os.getenv("CHAT_IN", "250"))     # plus this many possibly-Indian channels per platform: their chat language
                                               # decides if they count as Indian (langsig)
CHAT_ON = os.getenv("CHAT", "true").lower() == "true"
BUCKET = 5
KEEP = 480                                   # buckets: 40 minutes

_C = {}            # sid -> deque[[bucket_ts, n]]
_RAID = {}         # sid -> (ts, viewers) of the last raid in
_L = threading.Lock()
STATUS = {"twitch": "off", "kick": "off", "youtube": "via Super Chat reader"}


def add(sid: str, n: int = 1, ts: float = None):
    b = int((ts or time.time()) // BUCKET * BUCKET)
    with _L:
        d = _C.setdefault(sid, deque(maxlen=KEEP))
        if d and d[-1][0] == b:
            d[-1][1] += n
        elif not d or b > d[-1][0]:
            d.append([b, n])
        else:                                 # an older bucket (YouTube batches arrive late): find it
            for x in reversed(d):
                if x[0] == b:
                    x[1] += n
                    break


def series(sid: str, now: float = None):
    """[(bucket_ts, msgs)] for the last 40 minutes, gaps filled with 0, ending at the last complete bucket."""
    now = now or time.time()
    with _L:
        d = list(_C.get(sid) or [])
    if not d:
        return []
    m = dict((b, n) for b, n in d)
    end = int(now // BUCKET * BUCKET) - BUCKET
    start = max(d[0][0], end - (KEEP - 1) * BUCKET)
    return [(b, m.get(b, 0)) for b in range(start, end + 1, BUCKET)]


def covered(sid: str, now: float = None) -> bool:
    """True if we've been reading this channel's chat long enough to judge a burst."""
    with _L:
        d = _C.get(sid)
        return bool(d) and (now or time.time()) - d[0][0] > 300


def raid(sid: str):
    return _RAID.get(sid)


# ---------- Twitch (IRC) ----------

def _targets(platform: str, top: int) -> list:
    """The biggest live channels, plus the live ones that may be Indian (flagged Indian, or a hint of it) whose chat
    hasn't been judged yet or is close to the line."""
    from tracker import scene, langsig
    with scene._lock:
        L = sorted(((sid, x["viewers"], x.get("india") or x.get("india_hint")) for sid, x in scene._LIVE.items()
                    if x["platform"] == platform), key=lambda kv: -kv[1])
    out = [sid for sid, _, _ in L[:top]]
    cand = [sid for sid, v, h in L[top:] if h and v >= 5 and langsig.verdict(sid) is None]
    langsig.WANT.update({sid for sid, _, h in L if h})        # only these chats are judged (CPU)
    return [sid.split(":", 1)[1] for sid in out + cand[:CHAT_IN]]


def _twitch_targets():
    return _targets("twitch", CHAT_TWITCH)


def run_twitch():
    while True:
        try:
            raw = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=30)
            s = ssl.create_default_context().wrap_socket(raw, server_hostname="irc.chat.twitch.tv")
            s.settimeout(1.0)
            nick = f"justinfan{random.randint(10000, 99999)}"
            s.sendall(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n" + f"NICK {nick}\r\n".encode())
            joined, buf, last_sync = set(), b"", 0
            STATUS["twitch"] = "connected"
            while True:
                now = time.time()
                if now - last_sync > 30:          # follow the biggest live Twitch channels
                    last_sync = now
                    want = set(_twitch_targets())
                    for ch in list(joined - want):
                        s.sendall(f"PART #{ch}\r\n".encode())
                        joined.discard(ch)
                    new = list(want - joined)
                    for i in range(0, min(len(new), 18), 18):       # Twitch allows ~20 joins per 10 seconds
                        s.sendall(f"JOIN {','.join('#' + c for c in new[i:i + 18])}\r\n".encode())
                        joined.update(new[i:i + 18])
                    STATUS["twitch"] = f"connected, reading {len(joined)} channels"
                try:
                    chunk = s.recv(65536)
                    if not chunk:
                        raise ConnectionError("closed")
                    buf += chunk
                except socket.timeout:
                    continue
                *lines, buf = buf.split(b"\r\n")
                for ln in lines:
                    t = ln.decode("utf-8", "replace")
                    if t.startswith("PING"):
                        s.sendall(b"PONG :tmi.twitch.tv\r\n")
                        continue
                    m = re.search(r" (PRIVMSG|USERNOTICE) #(\w+)", t)
                    if not m:
                        continue
                    sid = "twitch:" + m.group(2).lower()
                    if m.group(1) == "PRIVMSG":
                        add(sid)
                        langsig.add(sid, t.split(f" PRIVMSG #{m.group(2)} :", 1)[-1])
                    elif "msg-id=raid" in t:
                        v = re.search(r"msg-param-viewerCount=(\d+)", t)
                        _RAID[sid] = (time.time(), int(v.group(1)) if v else 0)
        except Exception as e:
            STATUS["twitch"] = f"reconnecting ({str(e)[:60]})"
            time.sleep(15)


# ---------- Kick (chat websocket: Centrifugo) ----------

_ROOMS = {}        # slug -> chatroom id (0 = couldn't get it)


def _room(slug: str) -> int:
    if slug not in _ROOMS:
        from tracker import ytextra
        _ROOMS[slug] = int(((ytextra.kick_info(slug).get("chatroom") or {}).get("id")) or 0)
    return _ROOMS[slug]


class _WS:
    """Just enough of a websocket client for Pusher: text frames, ping/pong, close."""

    def __init__(self, url: str):
        m = re.match(r"wss://([^/]+)(/.*)", url)
        host, path = m.group(1), m.group(2)
        raw = socket.create_connection((host, 443), timeout=20)
        self.s = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: https://kick.com\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.s.recv(4096)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(head[:80])
        self.buf = head.split(b"\r\n\r\n", 1)[1]
        self.s.settimeout(1.0)

    def send(self, text: str, op: int = 1):
        data = text.encode()
        mask = os.urandom(4)
        n = len(data)
        hdr = bytes([0x80 | op]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _need(self, k):
        while len(self.buf) < k:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk

    def recv(self):
        """The next text message, or None on timeout."""
        try:
            self._need(2)
        except socket.timeout:
            return None
        self.s.settimeout(10)
        try:
            op, n = self.buf[0] & 0x0F, self.buf[1] & 0x7F
            i = 2
            if n == 126:
                self._need(4)
                n, i = struct.unpack(">H", self.buf[2:4])[0], 4
            elif n == 127:
                self._need(10)
                n, i = struct.unpack(">Q", self.buf[2:10])[0], 10
            self._need(i + n)
            data, self.buf = self.buf[i:i + n], self.buf[i + n:]
        finally:
            self.s.settimeout(1.0)
        if op == 9:
            self.send(data.decode("utf-8", "replace"), op=10)
            return None
        if op == 8:
            raise ConnectionError("closed by server")
        return data.decode("utf-8", "replace") if op == 1 else None


def _kick_targets():
    return _targets("kick", CHAT_KICK)


KICK_RT = os.getenv("KICK_REALTIME", "wss://realtime.us-west-2.platform.kick.com/connection/websocket")
KICK_RT_AUTH = os.getenv("KICK_REALTIME_AUTH", "https://web.kick.com/api/v1/realtime/auth/connection")
_EMOTE = re.compile(r"\[emote:\d+:[^\]]*\]")


def _kick_token() -> str:
    """A guest token for Kick's chat (Centrifugo since Nov 2026; the old Pusher key is gone): what kick.com itself does
    for a visitor who isn't logged in."""
    import uuid
    r = events._http.post(KICK_RT_AUTH, json={"client_id": str(uuid.uuid4())}, timeout=15,
                          headers={"User-Agent": events._UA, "Accept": "application/json", "Origin": "https://kick.com",
                                   "Referer": "https://kick.com/"})
    if r.status_code != 200:
        raise ConnectionError(f"token HTTP {r.status_code}")
    return r.json()["data"]["token"]


def _kick_push(line: str, rooms: dict):
    """One message from Kick's chat socket: count it (chat speed) and judge its language (langsig)."""
    try:
        j = json.loads(line)
    except ValueError:
        return
    p = j.get("push") or {}
    m = re.match(r"chatrooms\.(\d+)\.v2", p.get("channel") or "")
    d = (p.get("pub") or {}).get("data") or {}
    if not m or "ChatMessageEvent" not in (d.get("event") or ""):
        return
    slug = rooms.get(int(m.group(1)))
    if not slug:
        return
    add("kick:" + slug)
    try:
        text = (json.loads(d.get("data") or "{}") or {}).get("content") or ""
    except (ValueError, AttributeError):
        text = ""
    langsig.add("kick:" + slug, _EMOTE.sub(" ", text))


def run_kick():
    while True:
        try:
            tok = _kick_token()
            ws = _WS(KICK_RT)
            ws.send(json.dumps({"id": 1, "connect": {"token": tok, "name": "js"}}))
            subs, last_sync, started, nid = {}, 0, time.time(), 10
            STATUS["kick"] = "connected"
            while time.time() - started < 2400:           # the guest token lasts ~45 minutes: reconnect before
                now = time.time()
                if now - last_sync > 60:
                    last_sync = now
                    want = _kick_targets()
                    added = 0
                    for slug in want:
                        if slug in subs or added >= 30:   # each new one needs a chatroom lookup: 30 a minute
                            continue
                        added += 1
                        rid = _room(slug)
                        if rid:
                            nid += 1
                            ws.send(json.dumps({"id": nid, "subscribe": {"channel": f"chatrooms.{rid}.v2"}}))
                            subs[slug] = rid
                    for slug in [s_ for s_ in subs if s_ not in want]:
                        nid += 1
                        ws.send(json.dumps({"id": nid, "unsubscribe": {"channel": f"chatrooms.{subs[slug]}.v2"}}))
                        subs.pop(slug)
                    blocked = sum(1 for s_ in want if _ROOMS.get(s_) == 0)
                    STATUS["kick"] = f"connected, reading {len(subs)} channels" + (f" ({blocked} chatroom ids blocked by Kick)" if blocked else "")
                msg = ws.recv()
                if not msg:
                    continue
                rooms = {r: s_ for s_, r in subs.items()}
                for line in msg.split("\n"):
                    if line.strip() == "{}":
                        ws.send("{}")                       # Centrifugo's ping
                    elif '"push"' in line:
                        _kick_push(line, rooms)
                    elif '"error"' in line and '"id":1,' in line:
                        raise ConnectionError(line[:80])
        except Exception as e:
            STATUS["kick"] = f"reconnecting ({str(e)[:60]})"
            time.sleep(20)


def start():
    if not CHAT_ON:
        return
    langsig.start()
    threading.Thread(target=run_twitch, daemon=True).start()
    threading.Thread(target=run_kick, daemon=True).start()
