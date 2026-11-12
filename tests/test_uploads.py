"""New uploads keep arriving when YouTube's channel feeds are down: the uploads playlist page is read instead, Shorts
are marked from the Shorts playlist, and new videos are re-read every 3 hours for 2 days. Run: python tests/test_uploads.py"""
import json
import os
import sys
import tempfile
import time

T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/u.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, scene, ytextra  # noqa: E402

scene._db()
c = ytextra._db()
CID = "UC" + "1" * 22
c.execute("INSERT INTO sc_channels (sid, platform, name, url, logo, first_seen) VALUES (?,?,?,?,?,?)",
          ("yt:" + CID, "youtube", "News Ch", "", "", time.time()))
c.execute("INSERT INTO yt_videos (vid, sid, ts, title, views, likes, comments, secs, live, approx, updated, short, url, game, cat) "
          "VALUES ('oldvideo001','yt:" + CID + "',?, 'old', 5, 1, 0, 60, 0, 0, ?, 0, '', 'Other', 25)",
          (int(time.time() - 3 * 86400), int(time.time() - 86400 * 2)))
c.commit()


def lockup(vid, title, ago, views):
    return {"lockupViewModel": {"contentId": vid, "contentType": "LOCKUP_CONTENT_TYPE_VIDEO", "metadata": {"lockupMetadataViewModel": {
        "title": {"content": title}, "metadata": {"contentMetadataViewModel": {"metadataRows": [
            {"metadataParts": [{"text": {"content": "News Ch"}}]},
            {"metadataParts": [{"text": {"content": views}}, {"text": {"content": ago}}]}]}}}}}}


UU = {"contents": [lockup("newvideo001", "Breaking", "2 hours ago", "12K views"), lockup("newshort001", "Clip", "5 hours ago", "90K views"),
                   lockup("oldvideo001", "old", "3 days ago", "5 views")]}
SH = {"contents": [{"x": {"videoId": "newshort001"}}]}


class R:
    def __init__(self, code, text=""):
        self.status_code, self.text = code, text


def fake_get(url, *a, **k):
    if "feeds/videos.xml" in url:
        return R(404, "Not Found")
    if "playlist?list=UUSH" in url:
        return R(200, "<script>var ytInitialData = " + json.dumps(SH) + ";</script>")
    if "playlist?list=UU" in url:
        return R(200, "<script>var ytInitialData = " + json.dumps(UU) + ";</script>")
    return R(404)


events._http.get = fake_get
for i in range(25):                                   # 20 failures switch the feed off for 30 minutes
    ytextra._latest_posts("yt:UC" + f"{i:022d}")
assert ytextra._FEED["down_at"] > 0
got = {v["id"]: v for v in ytextra._latest_posts("yt:" + CID)}
assert set(got) == {"newvideo001", "newshort001", "oldvideo001"}, got
assert got["newshort001"]["short"] == 1 and got["newvideo001"]["short"] == 0
assert time.time() - got["newvideo001"]["ts"] < 3 * 3600

ytextra._RSSTRIED.clear()
assert ytextra.rss_once(10) >= 1
rows = {r[0]: (r[1], r[2]) for r in c.execute("SELECT vid, short, comments FROM yt_videos")}
assert rows["newvideo001"] == (0, None) and rows["newshort001"][0] == 1, rows

# exact stats: new videos first; a 1-day-old video read 4 hours ago is re-read, the 3-day-old one read 2 days ago too
os.environ["YOUTUBE_API_KEY"] = "test"
asked = []


class J(R):
    def __init__(self, ids):
        super().__init__(200)
        self.ids = ids

    def json(self):
        return {"items": [{"id": i, "statistics": {"viewCount": "100", "likeCount": "5", "commentCount": "1"},
                           "snippet": {"publishedAt": "2026-11-11T10:00:00Z", "categoryId": "25"},
                           "contentDetails": {"duration": "PT1M"}} for i in self.ids]}


events._http.get = lambda url, *a, params=None, **k: (asked.append(params["id"]), J(params["id"].split(",")))[1]
ytextra.video_stats_once(5)
assert "newvideo001" in asked[0] and "oldvideo001" in asked[0], asked
c.execute("UPDATE yt_videos SET updated=?, ts=? WHERE vid='newvideo001'", (int(time.time() - 4 * 3600), int(time.time() - 86400)))
c.commit()
asked.clear()
ytextra.video_stats_once(5)
assert asked and "newvideo001" in asked[0], asked                       # under 2 days old, last read 4 h ago
print("UPLOADS OK")
