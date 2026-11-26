"""PMGC: a title naming the event is not enough (owner, 26 Nov). Streams that play ranked, run custom rooms or scrims,
talk predictions, play another game, or name PMGC only in hashtags / the channel name are left out (with the reason,
for the admin page); watch parties in any of the main languages count; the owner can count or exclude any stream.
Run: python3 tests/test_pmgc_verify.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/p.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, scene
ev = events.create("pmgc")
n = [0]


def s(title, ch="Streamer", cid="UCx", vid=None):
    n[0] += 1
    return {"vid": vid or f"v{n[0]}", "channel": ch, "channel_id": cid, "title": title, "viewers": 100}


YES = ["PMGC 2026 GAUNTLET DAY 1 WATCH PARTY LIVE | SouL TX", "NOBAR PMGC 2026 GAUNTLET HARI 1",
       "PMGC 2026 Gauntlet Day 1 LIVE | SouL, Orangutan", "PMGC 2026 watch party + predictions",
       "2026 GC League | Gauntlet Day 1 | WATCHPARTY WITH SNAX", "PMGC 2026 canlı izliyoruz", "Assistindo PMGC 2026 ao vivo",
       "PMGC 2026 Co-Stream | Day 1", "PMGC 2026 Hindi commentary live", "Watch party #pmgc",
       "PMGC 2026 GAUNTLET DAY 1 LIVE | PREDICTION GIVEAWAY", "PMGC 2026 Day 1 | SouL road to Grand Finals", "PMGC 2026 Day 1 live analysis"]
NO = {"BGMI LIVE RANK PUSH #pmgc #bgmi": "hashtags", "PMGC Qualified Team Scrims | BGMI Live": "scrims",
      "Road to PMGC | conqueror push": "road to", "PMGC 2026 Predictions & Tier List LIVE": "tier list",
      "Free Fire live PMGC 2026": "free fire", "PMGC custom rooms live | UC giveaway": "custom rooms",
      "Playing with subs after PMGC 2026": "playing with subs", "PMGC 2026 1v4 rush gameplay": "1v4", "PMGC 2026 gameplay live": "gameplay"}
for t in YES:
    assert events.relevant(ev, s(t)), t
for t, why in NO.items():
    x = s(t)
    assert not events.relevant(ev, x), t
    r = events._REJ["pmgc"][x["vid"]]
    assert why in r["why"].lower() or (why == "hashtags" and "hashtags" in r["why"]), (t, r["why"])
assert not events.relevant(ev, s("Live stream tonight", ch="PMGC Fans"))          # the channel's name is not the title
# official channels skip the check (their preview shows and talk shows are the broadcast)
assert events.relevant(ev, s("PMGC 2026 Gauntlet Preview Show", ch="PUBG MOBILE Esports", cid="UCmeeY9kzNswUpbYyJntb3Aw"))
# YouTube's game card: another game is out, PUBG Mobile / BGMI / none stays
scene._YCARD.update({"g1": "Minecraft", "g2": "PUBG MOBILE", "g3": ""})
assert not events.relevant(ev, s("PMGC 2026 live", vid="g1")) and "Minecraft" in events._REJ["pmgc"]["g1"]["why"]
assert events.relevant(ev, s("PMGC 2026 live", vid="g2")) and events.relevant(ev, s("PMGC 2026 live", vid="g3"))
found = {"g1": s("PMGC 2026 live", vid="g1"), "g2": s("PMGC 2026 live", vid="g2")}
scene._card_get = lambda vids, n=4: 0                                              # no network in the test
events._card_filter(ev, found)
assert set(found) == {"g2"}
# Kick / Twitch go through the same title check
assert not events.relevant(ev, {"vid": "kick:a", "channel": "a", "channel_id": "kick:a", "title": "BGMI scrims PMGC teams", "viewers": 5})
# the owner counts one the check left out, and excludes one it counted
bad = s("PMGC Qualified Team Scrims | BGMI Live", vid="sc1")
assert not events.relevant(ev, bad)
assert events.set_stream("pmgc", "sc1", True)
ev = events.events()["pmgc"]
assert events.relevant(ev, bad) and "sc1" not in events._REJ["pmgc"] and "sc1" in events._LIVE["pmgc"]
good = s("PMGC 2026 watch party", vid="wp9")
events._LIVE["pmgc"]["wp9"] = good
assert events.set_stream("pmgc", "wp9", False)
ev = events.events()["pmgc"]
assert not events.relevant(ev, good) and "wp9" not in events._LIVE["pmgc"]
assert events.set_stream("pmgc", "wp9", True) and events.relevant(events.events()["pmgc"], good)   # and back
assert len(events.PRESETS["pmgc"]["world_queries"]) >= 20 and {g for _, g in events.PRESETS["pmgc"]["world_queries"]} >= {"ID", "TR", "BR", "PK", "MN", "VN", "TH"}
# the chat check: a chat about room IDs / nothing related takes a stream off; a chat about the match keeps it;
# chats in other scripts are not judged; the owner's Count it wins
chats = {
    "c_play": [(f"m{i}", t) for i, t in enumerate(["bhai room id do", "custom room kab", "rank push karo", "pass bhejo", "nice bro",
                                                   "hello", "sensi code?", "op bhai"] * 6)],
    "c_wp": [(f"w{i}", t) for i, t in enumerate(["SouL jeetegi aaj", "MongolZ op", "chicken dinner!!", "gg", "nice"] * 9)],
    "c_thai": [(f"t{i}", "สวัสดีครับ เชียร์เต็มที่") for i in range(60)],
    "c_few": [("f1", "hello"), ("f2", "hi")],
}
events._chat_texts = lambda vid: chats[vid]
for vid in chats:
    x = s("PMGC 2026 Gauntlet Day 1 LIVE", vid=vid)
    assert events.relevant(ev, x)
    events._LIVE["pmgc"][vid] = {**x, "kind": "watch party"}
    events._chat_check("pmgc", vid)
V = {v: events._CHATV[v]["verdict"] for v in chats}
assert V == {"c_play": "no", "c_wp": "yes", "c_thai": "", "c_few": ""}, V
assert "c_play" not in events._LIVE["pmgc"] and {"c_wp", "c_thai", "c_few"} <= set(events._LIVE["pmgc"])
assert "chat never mentions" in events._REJ["pmgc"]["c_play"]["why"] and "rooms" in events._REJ["pmgc"]["c_play"]["why"]
assert not events.relevant(ev, s("PMGC 2026 Gauntlet Day 1 LIVE", vid="c_play"))        # the next search can't re-add it
assert events.set_stream("pmgc", "c_play", True) and events.relevant(events.events()["pmgc"], s("PMGC 2026 Gauntlet Day 1 LIVE", vid="c_play"))
assert events.chat_judge([(False, False, True)] * 39)[0] == "" and events.chat_judge([(False, False, True)] * 40)[0] == "no"
assert events.chat_judge([(True, False, True)] * 2 + [(False, False, True)] * 80)[0] == "yes"
print("PMGC VERIFY OK")
