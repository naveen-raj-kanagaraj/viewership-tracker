"""Chat analytics, audience overlap, viewer spending, media kit data, shortlist / docs pages and the data API.
Run: python tests/test_kit.py"""
import json
import os
import sys
import tempfile
import time

T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/k.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import chatstats, kit, scene, ytextra  # noqa: E402

scene._db()
c = chatstats._db()
now = int(time.time())
A, B = "yt:UC" + "a" * 22, "yt:UC" + "b" * 22
for sid, nm in ((A, "Alpha Gaming"), (B, "Beta Live")):
    c.execute("INSERT INTO sc_channels (sid, platform, name, url, logo, first_seen, india) VALUES (?,?,?,?,?,?,1)",
              (sid, "youtube", nm, "https://youtube.com/x", "", now))
c.commit()


def msg(author, text, emojis=(), ts=None):
    runs = [{"text": text}] + [{"emoji": {"shortcuts": [e]}} for e in emojis]
    return {"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {
        "authorExternalChannelId": author, "message": {"runs": runs}, "timestampUsec": str((ts or now) * 1_000_000)}}}}


# language, mood
assert chatstats.lang_of("bhai kya game hai") == "Hinglish"
assert chatstats.lang_of("what a play") == "English / other Latin"
assert chatstats.lang_of("बहुत बढ़िया खेल") == "Hindi / Marathi (Devanagari)"
assert chatstats.lang_of("சூப்பர் ஆட்டம்") == "Tamil"
assert chatstats.mood_of(["op", "gg"], ["🔥"]) == 1 and chatstats.mood_of(["lag", "worst"], []) == -1 and chatstats.mood_of(["ok"], []) == 0

# 400 chatters on A, 200 on B, 100 shared (users 0-99 chat on both)
acts_a = [msg(f"UCuser{i}", "bhai op gameplay 🔥", [":fire:"], now - 3000 + i) for i in range(400)]
acts_a += [msg("UCuser1", "worst lag bro", ts=now - 100)]
acts_b = [msg(f"UCuser{i}", "nice stream bgmi", ts=now - 2000 + i) for i in range(100)] + \
         [msg(f"UCother{i}", "बहुत बढ़िया", ts=now - 1500 + i) for i in range(100)]
chatstats.add("vidA", A, acts_a)
chatstats.add("vidB", B, acts_b)
assert chatstats.flush() == 2
r = dict(c.execute("SELECT * FROM chat_stream WHERE vid='vidA'").fetchone())
assert r["msgs"] == 401 and r["chatters"] == 400, r
assert json.loads(r["words"]).get("gameplay") == 400 and "bhai" not in json.loads(r["words"])
assert r["pos"] == 400 and r["neg"] == 1
langs = json.loads(dict(c.execute("SELECT langs FROM chat_stream WHERE vid='vidB'").fetchone())["langs"])
assert langs == {"English / other Latin": 100, "Hindi / Marathi (Devanagari)": 100}, langs
# restart mid-stream: counts carry on from what was saved
chatstats._ACC.clear()
chatstats.add("vidA", A, [msg("UCuser999", "gg", ts=now - 50)])
chatstats.flush()
assert c.execute("SELECT msgs FROM chat_stream WHERE vid='vidA'").fetchone()[0] == 402

# overlap (sampled: roughly a quarter of hashes kept, so counts are estimates)
chatstats.OVERLAP_TOP = 10
assert chatstats.overlap_once() == 2
pct_b = c.execute("SELECT pct FROM chat_overlap WHERE a=? AND b=?", (B, A)).fetchone()[0]
pct_a = c.execute("SELECT pct FROM chat_overlap WHERE a=? AND b=?", (A, B)).fetchone()[0]
assert 0.3 < pct_b < 0.7 and 0.1 < pct_a < 0.45, (pct_a, pct_b)            # true values 0.5 and 0.25

# spending: Super Chats exact, memberships counted (renewals apart), gifts by units
day = ytextra._day()
c.executemany("INSERT INTO sc_superchat VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("p1", A, "vidA", now, day, "superchat", "x", 500, "INR", 6.0, 500, 1, ""),
    ("p2", A, "vidA", now, day, "sticker", "y", 100, "INR", 1.2, 100, 1, ""),
    ("p3", A, "vidA", now, day, "member", "z", 0, "", 0, 0, 1, ""),
    ("p4", A, "vidA", now, day, "milestone", "z", 0, "", 0, 0, 1, ""),
    ("p5", A, "vidA", now, day, "gift", "w", 0, "", 0, 0, 5, "")])
c.commit()
s = chatstats.summary(A)
sp = s["spending"]
assert sp["superchat"]["usd"] == 6.0 and sp["new_members"] == 1 and sp["renewals"] == 1 and sp["gifted"] == 5
assert abs(sp["members_usd_est"] - 6 * 0.71) < .01 and abs(sp["total_usd"] - (7.2 + 6 * 0.71)) < .02
assert s["messages"] == 402 and s["overlap"][0]["name"] == "Beta Live" and s["words"][0] == "gameplay"

# member renewal is told apart in parsing
items = ytextra.paid_items([{"addChatItemAction": {"item": {"liveChatMembershipItemRenderer": {
    "id": "m1", "timestampUsec": "1", "authorName": {"simpleText": "z"}, "headerPrimaryText": {"runs": [{"text": "Member for 6 months"}]}}}}},
    {"addChatItemAction": {"item": {"liveChatMembershipItemRenderer": {
        "id": "m2", "timestampUsec": "1", "authorName": {"simpleText": "q"}, "headerSubtext": {"simpleText": "Welcome to Alpha!"}}}}}])
assert [i["kind"] for i in items] == ["milestone", "member"], items

# kit data
d = kit.data(A)
assert d["name"] == "Alpha Gaming" and d["chat_30d"]["spending"]["gifted"] == 5 and "engagement" in d

# pages and data API through the web app
from tracker import web  # noqa: E402
cl = web.app.test_client()
assert cl.get(f"/global/kit/{A}").status_code == 200 and b"media kit" in cl.get(f"/global/kit/{A}").data
assert cl.get("/global/kit/yt:UCnope").status_code == 404
assert cl.get("/shortlist").status_code == 200 and cl.get("/api/docs").status_code == 200
assert json.loads(cl.get(f"/api/kit?sid={A}").data)["name"] == "Alpha Gaming"
assert cl.get(f"/api/v1/creator?sid={A}").status_code == 401
key = kit.key_create("Test Agency", 2)
r1 = cl.get(f"/api/v1/creator?sid={A}", headers={"X-API-Key": key})
assert r1.status_code == 200 and json.loads(r1.data)["name"] == "Alpha Gaming" and r1.headers["X-Calls-Today"] == "1"
assert cl.get(f"/api/v1/search?q=alpha&key={key}").status_code == 200
assert cl.get(f"/api/v1/creator?sid={A}", headers={"X-API-Key": key}).status_code == 429          # limit 2 a day
assert kit.key_revoke(key[:10]) == 1 and not kit.key_check(key)[0]
print("KIT OK")
