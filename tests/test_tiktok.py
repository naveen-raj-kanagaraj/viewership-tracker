"""TikTok live counts (owner, 28 Nov: track TikTok and Facebook like Esports Charts). Run: python3 tests/test_tiktok.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/t.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import platforms, events


class R:
    def __init__(self, j, code=200):
        self.j, self.status_code = j, code
    def json(self):
        if isinstance(self.j, Exception):
            raise self.j
        return self.j


ROOMS = {
    "pubgmobile": {"statusCode": 0, "data": {"user": {"uniqueId": "pubgmobile", "nickname": "PUBG MOBILE", "status": 2,
                   "avatarThumb": "https://p16/x.jpg"}, "liveRoom": {"status": 2, "title": "PMGC League The Gauntlet D2",
                   "liveRoomStats": {"userCount": 48210, "enterCount": 139594}, "startTime": 1795779284}}},
    "pubgmobilethailand": {"statusCode": 0, "data": {"user": {"uniqueId": "pubgmobilethailand", "nickname": "PUBG Mobile Thailand"},
                           "liveRoom": {"status": 4, "title": "old", "liveRoomStats": {"userCount": 1}}}},
    "promo": {"statusCode": 0, "data": {"user": {"uniqueId": "promo", "nickname": "PUBG MOBILE"},
              "liveRoom": {"status": 2, "title": "New skin giveaway", "liveRoomStats": {"userCount": 9000}}}},
    "gone": {"statusCode": 19881007, "message": "user_not_found", "data": {}},
}
calls = []
def fake_get(url, params=None, headers=None, timeout=None):
    calls.append(params["uniqueId"])
    return R(ROOMS[params["uniqueId"]])
platforms._http.get = fake_get

assert platforms.split("tiktok:pubgmobile.esports.id") == ("tiktok", "pubgmobile.esports.id")
assert platforms.link("tiktok:pubgmobile") == "https://www.tiktok.com/@pubgmobile/live"
rows = platforms._tt_handles(["pubgmobile", "pubgmobilethailand", "gone"])
assert [r["vid"] for r in rows] == ["tiktok:pubgmobile"] and rows[0]["viewers"] == 48210, rows   # userCount, not enterCount
assert platforms.logo("tiktok:pubgmobile") == "https://p16/x.jpg"

# counting: one request per account per 10 s
calls.clear()
assert platforms.count("tiktok:pubgmobile") == 48210
assert platforms.count("tiktok:pubgmobile") == 48210 and calls.count("pubgmobile") == 1
assert platforms.count("tiktok:pubgmobilethailand") is None

# all refused (captcha page, not JSON): raises, so the counter keeps its last good reading
platforms._http.get = lambda *a, **k: R(ValueError("not json"))
try:
    platforms._tt_handles(["pubgmobile"]); raise SystemExit("should raise")
except RuntimeError:
    pass
platforms._http.get = fake_get

# event: official TikTok counts only while the title names the event
ev = {"key": "pmgc", "match": events.PRESETS["pmgc"]["match"], "videos": [], "excluded": []}
pr = events.preset("pmgc")
assert "pubgmobile" in platforms.cfg(ev, pr, "tiktok")["official"]
assert "tiktok" in platforms.enabled(ev, pr)
assert events.relevant(ev, {"vid": "tiktok:pubgmobile", "title": "PMGC League The Gauntlet D2", "channel": "PUBG MOBILE"})
assert not events.relevant(ev, {"vid": "tiktok:pubgmobile", "title": "New skin giveaway", "channel": "PUBG MOBILE"})
assert platforms.official(ev, pr, "tiktok:pubgmobile")
print("TIKTOK OK")

# ---- site-wide TikTok (tracker/tiktok.py) ----
from tracker import tiktok, store, scene
import json as _j
c = store.main()
c.execute("CREATE TABLE IF NOT EXISTS ch_profile (sid TEXT PRIMARY KEY, bio TEXT, links TEXT, checked INTEGER, followers INTEGER, src INTEGER)")
c.execute("INSERT INTO ch_profile (sid, bio, links, checked) VALUES ('kick:abc','', ?, 0)", (_j.dumps({"tiktok": "https://www.tiktok.com/@Some.Creator?lang=en"}),))
c.commit()
store.kv_set("ev_about:UCx", {"links": ["instagram.com/x", "https://tiktok.com/@other_one"], "ts": 1})
tiktok.FILE = __import__("pathlib").Path(tempfile.mkdtemp()) / "t.json"
tiktok.FILE.write_text(_j.dumps({"add": ["@Handadded"], "remove": ["pubgmobile_br"]}))
hs = tiktok.handles()
assert "some.creator" in hs and "other_one" in hs and "handadded" in hs and "pubgmobile" in hs and "pubgmobile_br" not in hs, hs
tiktok._check("pubgmobile")
assert [r["vid"] for r in tiktok.rows()] == ["tiktok:pubgmobile"]
tiktok._check("pubgmobilethailand")            # not live: no row
assert len(tiktok.rows()) == 1
assert scene.india_why({"sid": "tiktok:x", "platform": "tiktok", "title": "BGMI hindi live"})[0] is False
print("TIKTOK SCENE OK")
