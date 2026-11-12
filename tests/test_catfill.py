"""Category fill: charts, deep search and Channels-tab links add Indian channels with their numbers and category.
YouTube is faked. Run: python tests/test_catfill.py"""
import os
import sys
import tempfile

T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/f.db"
os.environ["YOUTUBE_API_KEY"] = "test"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import catfill, events, scene, store, ytextra  # noqa: E402

scene._db()
cid = lambda i: "UC" + f"{i:022d}"


class R:
    def __init__(self, j, code=200, text=""):
        self._j, self.status_code, self.text, self.headers = j, code, text, {"content-type": "application/json"}

    def json(self):
        return self._j

    def raise_for_status(self):
        pass


def fake_get(url, *a, params=None, **k):
    params = params or {}
    if "videos" in url and params.get("chart") == "mostPopular":
        if params["videoCategoryId"] == 29:
            return R({"error": {}}, 404)
        base = params["videoCategoryId"] * 1000
        return R({"items": [{"snippet": {"channelId": cid(base + i)}} for i in range(3)]})
    if "/channels?" in url or url.endswith("/channels") and "googleapis" in url:
        pass
    if "googleapis.com/youtube/v3/channels" in url:
        items = []
        for c in params["id"].split(","):
            n = int(c[2:])
            country = "IN" if n % 3 == 0 else ("" if n % 3 == 1 else "US")
            desc = "हिंदी गाने और भजन हर दिन नया वीडियो" if n % 3 == 1 else "english channel"
            items.append({"id": c, "statistics": {"subscriberCount": str(1000 + n), "viewCount": str(10 ** 6 + n), "videoCount": "10"},
                          "snippet": {"title": f"Ch {n}", "country": country, "description": desc},
                          "topicDetails": {"topicCategories": ["https://en.wikipedia.org/wiki/Music"]}})
        return R({"items": items})
    if url.endswith("/channels") and "youtube.com/channel/" in url:
        me = url.split("/channel/")[1].split("/")[0]
        return R({}, 200, f'"channelId":"{me}" "channelId":"{cid(900001)}" "channelId":"{cid(900003)}"')
    return R({}, 404)


def fake_post(url, json=None, **k):
    if json.get("continuation") == "TOK2":
        return R({"contents": [{"channelRenderer": {"channelId": cid(800003)}}]})
    return R({"contents": [{"channelRenderer": {"channelId": cid(800000)}}, {"channelRenderer": {"channelId": cid(800001)}}],
              "x": {"continuationCommand": {"token": "TOK2"}}})


events._http.get = fake_get
events._http.post = fake_post

# India detection
assert ytextra.looks_indian({"text": "हिंदी गाने और भजन हर दिन नया वीडियो"})
assert ytextra.looks_indian({"lang": "ta", "text": "x"})
assert not ytextra.looks_indian({"text": "english channel about cars"})
assert not ytextra.looks_indian({"text": "বাংলা গান প্রতিদিন নতুন ভিডিও"})     # Bengali alone: could be Bangladesh

# charts: category from the chart, Indian by country or script; category 29 has no chart
catfill.WORLD_ON = False
n = catfill.charts([("in", "cat", "Music"), ("in", "cat", "Nonprofits & Activism")])
assert n == 2, n                                               # the US channel is not kept
c = ytextra._db()
rows = {r[0]: (r[1], r[2], r[3]) for r in c.execute("SELECT sid, ytcat, india, country FROM sc_channels")}
assert rows["yt:" + cid(10002)] == ("Music", 1, "IN"), rows   # country India
assert rows["yt:" + cid(10000)][:2] == ("Music", 1)            # no country, Hindi text
assert "yt:" + cid(10001) not in rows                          # US: dropped
assert c.execute("SELECT COUNT(*) FROM sc_chstats").fetchone()[0] == 2
assert catfill.charts([("in", "cat", "Music")]) == 0                         # not again within 6 hours

# deep search: page 1 then continuation page 2
catfill.SEARCH_PAGES = 2
added = catfill.search([("in", "cat", "Music")]) + catfill.search([("in", "cat", "Music")])  # one page per query per run, rotating
assert added == 1, added                                       # 800001 (India) kept; 800000 and 800003 (US) dropped
assert catfill._S[("hindi songs", "IN")]["page"] >= 2

# Channels-tab links from Indian Music channels
added = catfill.links([("in", "cat", "Music")])
assert added == 2, added                                      # 900001 (Hindi, no country) and 900003 (India); never itself


print(catfill.report())
assert catfill.counts()[("in", "cat", "Music")] >= 4, catfill.counts()
# worldwide: a big US channel is kept, a small one dropped; game search seeds the game
catfill.WORLD_ON = True
assert ("world", "game", "BGMI") in catfill.groups() and ("in", "game", "Free Fire") in catfill.groups()
kept = catfill.admit({cid(700002): ("", "BGMI"), cid(700005): ("", "")}, "world")
r2 = {r[0]: r[1] for r in c.execute("SELECT sid, game FROM sc_channels WHERE sid IN (?,?)", ("yt:" + cid(700002), "yt:" + cid(700005)))}
assert kept >= 1 and r2.get("yt:" + cid(700002)) == "BGMI", r2
catfill.run_once()
print("CATFILL OK")
