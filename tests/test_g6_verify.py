"""GTA 6 lists keep only channels whose streams are GTA 6 (YouTube game card or title). Run: python3 tests/test_g6_verify.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
os.environ["GTA6_SHOW"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import store, scene, ranks, events
scene._db()
c = store.main()
d = time.strftime("%Y-%m-%d")
day0 = max(d, __import__("datetime").datetime.fromtimestamp(scene.GTA6_RELEASE, events.REPORT_TZ).strftime("%Y-%m-%d"))
ch = [("yt:UCa", "Real Gamer"), ("yt:UCb", "Fake Restream"), ("yt:UCc", "No Card Talker"), ("yt:UCd", "No Card Player"),
      ("yt:UCe", "Title Copier")]
c.executemany("INSERT INTO sc_channels (sid, platform, name, india) VALUES (?,?,?,1)", [(s, "youtube", n) for s, n in ch])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(day0, s, "GTA 6", 1000 - i, 1, 60, 500) for i, (s, _) in enumerate(ch)])
c.executemany("INSERT INTO sc_vstreams VALUES (?,?,?,?,?,?,?,?)",
              [("v" + s[-1], s, scene.GTA6_RELEASE + 60, scene.GTA6_RELEASE + 3600, 900, 0, 1, 1) for s, _ in ch])
c.commit()
PAGES = {"va": ("Grand Theft Auto VI", "GTA 6 LIVE"), "vb": ("Minecraft", "GTA 6 Is Here! Launch Day Live"),
         "vc": ("", "waiting for GTA 6 #gta6"), "vd": ("", "GTA 6 FIRST DAY LIVE"), "ve": ("", "GTA 6 first day live!!")}
scene._yt_game = lambda v: PAGES[v]
assert scene.verify_g6() == 3
ranks.compute()
names = [r["name"] for r in ranks.top("all", "peak_7d", country="IN", game="GTA 6")["rows"]]
assert names == ["Real Gamer", "No Card Player"], names
h = 'var ytInitialData = {"style":"RICH_METADATA_RENDERER_STYLE_BOX_ART","thumbnail":{},"title":{"simpleText":"Grand Theft Auto VI"}...<meta name="title" content="GTA 6 &amp; chill">'
class R: status_code = 200; text = h
events._http.get = lambda *a, **k: R()
import importlib; importlib.reload(scene)
assert scene._yt_game("x") == ("Grand Theft Auto VI", "GTA 6 & chill"), scene._yt_game("x")
class J: status_code = 200; text = "<html>consent</html>"
events._http.get = lambda *a, **k: J()
assert scene._yt_game("x") is None                       # not a real watch page: unknown, never "not GTA 6"
class N: status_code = 200; text = 'var ytInitialData = {};<meta property="og:title" content="GTA 6 LIVE">'
events._http.get = lambda *a, **k: N()
assert scene._yt_game("x") == ("", "GTA 6 LIVE")
assert scene.classify("", "Gta v Panther live #shorts #gtav #gta6") == "GTA V"
print("GTA 6 VERIFY OK")
