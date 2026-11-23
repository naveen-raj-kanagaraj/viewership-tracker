"""An empty rankings answer (built before the rankings loaded after a restart) is never kept, here or at Cloudflare.
22 Nov: the page showed 0 channels for hours. Run: python3 tests/test_topch_empty.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, ranks, events, ytextra, web
scene._db(); ytextra._db()
cl = web.app.test_client()
u = "/api/topch?platform=kick&metric=peak_7d&country=IN"
r = cl.get(u)
assert r.json["total"] == 0 and r.json["updated"] == 0
assert "max-age=3" in r.headers.get("Cache-Control", "") or "s-maxage=3" in r.headers.get("Cache-Control", ""), r.headers
assert not [k for k in web._MEMO if k.startswith("/api/topch:kick:peak_7d:IN")], "empty answer kept"
c = store.main()
d = datetime.now(events.REPORT_TZ).date().strftime("%Y-%m-%d")
c.execute("INSERT INTO sc_channels (sid, platform, name, india, country) VALUES ('kick:c','kick','C',1,'IN')")
c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (d, "kick:c", "BGMI", 2000, 1, 60, 1000)); c.commit()
ranks.compute()
# an empty copy left from before (e.g. restored from disk) is dropped once the rankings exist
key = f"/api/topch:kick:peak_7d:IN:::100:{scene.RULES_V}:{int(ranks._R['at'])}"
web._MEMO[key] = (0, b'{"platform":"kick","metric":"peak_7d","total":0,"updated":0,"games":[],"rows":[]}', None)
j = cl.get(u).json
assert j["total"] >= 1 and j["updated"], j
# new rankings: the old answer is never served again
old = cl.get(u).json["updated"]
c.execute("INSERT INTO sc_channels (sid, platform, name, india, country) VALUES ('kick:e','kick','E',1,'IN')")
c.execute("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", (d, "kick:e", "BGMI", 9000, 1, 60, 1000)); c.commit()
import time; time.sleep(1.1); ranks.compute()
j = cl.get(u).json
assert j["updated"] > old and j["rows"][0]["name"] == "E", j["rows"]
print("TOPCH EMPTY OK")
