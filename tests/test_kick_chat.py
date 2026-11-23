"""Kick chat reader (Centrifugo, Nov 2026): guest token, subscribe to chatrooms, count + judge messages.
Run: python3 tests/test_kick_chat.py"""
import os, sys, tempfile, json
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import chat, langsig, events
langsig.WANT.add("kick:neyoo_gaming")
inner = json.dumps({"id": "x", "chatroom_id": 104926659, "content": "bhai kya clutch tha [emote:37226:KEKW]", "type": "message"})
line = json.dumps({"push": {"channel": "chatrooms.104926659.v2", "pub": {"data": {"event": "App\\Events\\ChatMessageEvent", "data": inner}}}})
chat._kick_push(line, {104926659: "neyoo_gaming"})
assert langsig.counts("kick:neyoo_gaming") == (1, 0) and chat._C.get("kick:neyoo_gaming"), langsig.counts("kick:neyoo_gaming")
chat._kick_push(line, {})                                       # not one of ours: ignored
assert langsig.counts("kick:neyoo_gaming") == (1, 0)
# the loop: token, connect, subscribe, ping answered, pushes counted
sent = []
class FakeWS:
    def __init__(s, url): s.q = ['{"id":1,"connect":{"client":"c"}}', "{}", line + "\n" + line]; assert url == chat.KICK_RT
    def send(s, t): sent.append(t)
    def recv(s):
        if s.q: return s.q.pop(0)
        raise ConnectionError("done")
class R:
    status_code = 200
    def json(s): return {"data": {"token": "tok"}}
events._http.post = lambda url, **k: R()
chat._WS = FakeWS
chat._kick_targets = lambda: ["neyoo_gaming"]
chat._ROOMS["neyoo_gaming"] = 104926659
import threading, time
threading.Thread(target=chat.run_kick, daemon=True).start()
time.sleep(1.5)
assert json.loads(sent[0]) == {"id": 1, "connect": {"token": "tok", "name": "js"}}, sent[:2]
assert any('"subscribe": {"channel": "chatrooms.104926659.v2"}' in x for x in sent), sent
assert "{}" in sent and langsig.counts("kick:neyoo_gaming") == (3, 0), (sent, langsig.counts("kick:neyoo_gaming"))
print("KICK CHAT OK")
