"""CEGC: Sky Esports' channels are official; every other stream carrying CEGC (listed or found by title in the live
scan, Kick or Indian YouTube) is a watch party. Run: python3 tests/test_cegc_watch.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/c.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, scene
ev = events.create("cegc")
scene._LIVE.clear()
scene._LIVE.update({
    "kick:skyesports": {"title": "CEGC 2026 - BGMI DAY 12", "name": "skyesports", "streams": {"kick:skyesports": 7900}, "india": True},
    "kick:jasleenplayz": {"title": "CEGC watchparty #bgmi", "name": "jasleenplayz", "streams": {"kick:jasleenplayz": 43}, "india": True},
    "yt:UCwp": {"title": "CEGC 2026 || WATCH PARTY", "name": "Some Tuber", "streams": {"vidwp": 62}, "india": True},
    "yt:UCpt": {"title": "Culto CEGC domingo", "name": "Igreja CEGC", "streams": {"vidpt": 300}, "india": False},
    "kick:random": {"title": "Bigg Boss watch party", "name": "random", "streams": {"kick:random": 900}, "india": True},
})
got = {s["vid"]: s for s in events.scene_matches(ev)}
assert set(got) == {"kick:skyesports", "kick:jasleenplayz", "vidwp"}, set(got)
for v in got:
    assert events.relevant(ev, got[v]), v
kinds = {v: events.kind_of(ev, got[v]) for v in got}
assert kinds == {"kick:skyesports": "official", "kick:jasleenplayz": "watch party", "vidwp": "watch party"}, kinds
listed = {"vid": "kick:soulaman", "channel": "soulaman", "channel_id": "kick:soulaman", "title": "GTA marathon", "viewers": 170}
assert events.relevant(ev, listed) and events.kind_of(ev, listed) == "watch party"
print("CEGC WATCH PARTIES OK")
