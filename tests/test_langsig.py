"""Chat language decides Indian or not on Kick / Twitch. Run: python3 tests/test_langsig.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import langsig, scene, store
scene._db()
K = langsig.kind
assert K("bhai kya shot tha") == "in" and K("नमस्ते भाई") == "in" and K("op bhai") == "in" and K("tum kaha se ho") == "in"
assert K("that was insane lol") == "other" and K("que buena jugada") == "other" and K("hai fatto bene") == "other"   # Italian 'hai'
assert K("টিম বাংলাদেশ") == "other"                     # Bengali chat: not counted as Indian (Bangladesh)
assert K("gg") is None and K("KEKW") is None and K("🔥🔥") is None and K("?") is None
langsig.WANT.update({"twitch:indguy", "twitch:euguy", "twitch:guddu_kim"})
langsig.add("twitch:notwanted", "bhai kya")
assert langsig.counts("twitch:notwanted") == (0, 0)
for i in range(200):
    langsig.add("twitch:indguy", "bhai kya game hai" if i % 3 == 0 else "lets gooo")
    langsig.add("twitch:euguy", "nice play" if i % 50 else "bhai")
    langsig.add("twitch:euguy", "what a clutch")
assert langsig.verdict("twitch:indguy") is True and langsig.verdict("twitch:euguy") is False, (langsig.counts("twitch:indguy"), langsig.counts("twitch:euguy"))
assert langsig.verdict("twitch:nobody") is None
# the chat beats a plain English title either way; a foreign flag / owner's list still wins
v = lambda sid, t: scene.verdict({"sid": sid, "platform": "twitch", "title": t, "name": sid.split(":")[1]})
assert v("twitch:indguy", "GTA 6 Live") is True
assert v("twitch:euguy", "BIGG BOSS LIVE Hindi") is False
for i in range(300):
    langsig.add("twitch:guddu_kim", "bhai kya")
assert v("twitch:guddu_kim", "aaj sabko giveaway") is False
# counts survive a restart
langsig.load(); langsig.save(); langsig._C.clear(); langsig.load()
assert langsig.verdict("twitch:indguy") is True
# tags: Twitch's 'Hindi' tag counts; 'India vs Pakistan' is a match, not a foreign channel
assert scene.verdict({"sid": "twitch:t1", "platform": "twitch", "title": "GTA 6 day 3", "name": "t1", "tags": "Hindi English"})
assert scene.verdict({"sid": "kick:t2", "platform": "kick", "title": "India vs Pakistan live reaction", "name": "t2"})
assert not scene.verdict({"sid": "kick:t3", "platform": "kick", "title": "Pakistan zindabad stream", "name": "t3"})
print("LANGSIG OK")
# past broadcasts: two Indian titles make a channel Indian even when today's title is plain English
from tracker import ytextra
ytextra._db(); c = store.main()
c.executemany("INSERT INTO yt_videos (vid, sid, ts, title) VALUES (?,?,?,?)",
              [("kv1", "kick:pastind", 1, "GTA 5 RP Hindi stream"), ("kv2", "kick:pastind", 2, "bhai log aaj khelenge"),
               ("kv3", "kick:once", 1, "Hindi stream"), ("kv4", "kick:bd", 1, "Hindi stream"), ("kv5", "kick:bd", 2, "Hindi"),
               ("kv6", "kick:bd", 3, "টিম বাংলাদেশ 🇧🇩")]); c.commit()
got = scene._past_titles_india()
assert got == {"kick:pastind"}, got
# chat targets: the biggest channels plus possibly-Indian ones not judged yet
from tracker import chat
scene._LIVE.clear()
scene._LIVE.update({f"twitch:big{i}": {"platform": "twitch", "viewers": 10000 - i} for i in range(3)})
scene._LIVE["twitch:hinty"] = {"platform": "twitch", "viewers": 40, "india_hint": True}
scene._LIVE["twitch:indguy"] = {"platform": "twitch", "viewers": 30, "india": True}      # already judged by chat
scene._LIVE["twitch:plain"] = {"platform": "twitch", "viewers": 50}
assert chat._targets("twitch", 2) == ["big0", "big1", "hinty"], chat._targets("twitch", 2)
print("PAST TITLES + CHAT TARGETS OK")
# YouTube channels with no country: their live chat's languages (chatstats) decide
import json
from tracker import chatstats
c.executescript(chatstats.SCHEMA); c.commit()
day = __import__("time").strftime("%Y-%m-%d")
c.execute("INSERT INTO chat_stream (vid, sid, day, langs) VALUES ('y1','yt:UCnocountry',?,?)", (day, json.dumps({"Hinglish": 120, "English / other Latin": 200, "Tamil": 20})))
c.execute("INSERT INTO chat_stream (vid, sid, day, langs) VALUES ('y2','yt:UCforeign',?,?)", (day, json.dumps({"English / other Latin": 900, "Hinglish": 5})))
c.execute("INSERT INTO sc_channels (sid, platform, name, country, india) VALUES ('yt:UCnocountry','youtube','a','-',0), ('yt:UCforeign','youtube','b','-',1)")
c.commit()
scene.mark_known_india()
got = dict(c.execute("SELECT sid, india FROM sc_channels WHERE sid IN ('yt:UCnocountry','yt:UCforeign')").fetchall())
assert got == {"yt:UCnocountry": 1, "yt:UCforeign": 0}, got
assert scene.verdict({"sid": "yt:UCforeign", "platform": "youtube", "title": "Hindi stream", "name": "b"}, "-") is False
assert scene.verdict({"sid": "yt:UCforeign", "platform": "youtube", "title": "x", "name": "b"}, "IN") is True     # its country setting wins
print("YOUTUBE CHAT OK")
# small chats are decided as soon as they're clear (owner, 23 Nov: small channels never reach 150 messages)
assert langsig._decide(5, 15) is True and langsig._decide(12, 20) is True
assert langsig._decide(0, 45) is False and langsig._decide(2, 100) is False
assert langsig._decide(3, 30) is None and langsig._decide(2, 10) is None
print("SMALL CHATS OK")
