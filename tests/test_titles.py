"""YouTube streams read without a title keep the title we know, and missing titles are looked up (oEmbed) so big
streams are filed under the right game. Run: python3 tests/test_titles.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/t.db"
os.environ["GTA6_SHOW"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene
scene.GTA6_RELEASE = 0
found = {}
scene._yt_add(found, {"vid": "a1", "channel": "Peanut", "channel_id": "UCp", "title": "GTA 6 | BUNGULATION", "viewers": 100})
scene._yt_add(found, {"vid": "a1", "channel": "Peanut", "channel_id": "UCp", "title": "", "viewers": 120})   # Live page: no title
assert found["yt:UCp"]["title"] == "GTA 6 | BUNGULATION", found["yt:UCp"]
scene._yt_add(found, {"vid": "k1", "channel": "Kai", "channel_id": "UCk", "title": "", "viewers": 115000})
scene._oembed_title = lambda v: {"k1": "GTA 6 DAY 1 ft. everyone"}.get(v, "")
assert scene.fill_titles(found) == 1 and found["yt:UCk"]["title"] == "GTA 6 DAY 1 ft. everyone"
assert scene.classify("", found["yt:UCk"]["title"]) == "GTA 6"
assert scene.classify("", "CEKAMO IZLAZAK GTA VI🌴") == "GTA 6" and scene.classify("", "GTA Vice City RP") == "GTA V"
print("TITLES OK")

# launch-day repair: 'Other' days of YouTube channels whose title says GTA 6 move to GTA 6
from tracker import store
scene._db()
c = store.main()
c.execute("INSERT INTO sc_channels (sid, platform, name, title) VALUES ('yt:UCk','youtube','Kai','GTA 6 DAY 1'),('yt:UCx','youtube','X','Just chatting')")
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [("2026-11-18", "yt:UCk", "Other", 111000, 1, 60, 90000),
              ("2026-11-18", "yt:UCk", "GTA 6", 115000, 2, 30, 50000), ("2026-11-18", "yt:UCx", "Other", 500, 1, 60, 400),
              ("2026-11-17", "yt:UCk", "Other", 9000, 1, 60, 5000)])
c.commit()
assert scene.refile_gta6() == 1
rows = {(r[0], r[1], r[2]): tuple(r[3:]) for r in c.execute("SELECT * FROM sc_daily")}
assert rows[("2026-11-18", "yt:UCk", "GTA 6")] == (115000, 2, 90, 140000), rows
assert ("2026-11-18", "yt:UCk", "Other") not in rows and ("2026-11-18", "yt:UCx", "Other") in rows and ("2026-11-17", "yt:UCk", "Other") in rows
print("REFILE OK")
