"""Worldwide "today" is the US Central day: peaks before India's midnight still count. Run: python3 tests/test_ctday.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/c.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, store
scene._db()
c = store.main()
m0 = scene.ct_midnight()
now = time.time()
t_early = m0 + 60                                     # just after Central midnight (before India's midnight)
c.executemany("INSERT INTO sc_channels (sid, platform, name, india) VALUES (?,?,?,?)",
              [("twitch:honey", "twitch", "HoneyMad", 0), ("twitch:rub", "twitch", "Rubius", 0)])
c.executemany("INSERT INTO sc_samples VALUES (?,?,?,?)", [(int(t_early), "twitch:honey", 642000, "GTA 6"),
              (int(m0 - 3600), "twitch:honey", 999999, "GTA 6"),          # yesterday (Central): not counted
              (int(t_early), "twitch:rub", 300000, "GTA 6")])
c.commit()
scene._CTD.update(day=None, m={}, ready=False)
scene.ct_seed()
assert scene._CTD["ready"]
scene._ct_add([{"sid": "twitch:rub", "game": "GTA 6", "viewers": 367000}], now, 120, {})
rows = {r[0]: r for r in scene.ct_rows("GTA 6")}
assert rows["twitch:honey"][2] == 642000 and rows["twitch:rub"][2] == 367000, rows
assert abs(rows["twitch:rub"][4] - (scene.SCENE_SEC / 60 + 2)) < 1e-6          # minutes: seeded scan + this scan
d = scene.data("today", "gta-6" if scene.shown("GTA 6") else "", "global")
b = {x["name"]: x["peak"] for x in d["board"]}
if scene.shown("GTA 6"):
    assert b.get("HoneyMad") == 642000 and b.get("Rubius") == 367000, b
print("CENTRAL DAY OK")
