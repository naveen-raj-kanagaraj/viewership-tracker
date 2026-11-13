"""Channel page tournaments (official broadcaster), BGMI history, tournament numbers on the live-day card.
Run: python3 tests/test_chevents.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/e.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import events, eventpage

K = "yt:UCugG6-k5QGbq_iDEPAnG4NQ"
t = datetime(2026, 11, 1, 19, 0, tzinfo=events.REPORT_TZ).timestamp()
with events.store._lock:
    c = events._db()
    c.executemany("INSERT INTO ev_ticks VALUES (?,?,?,?,?,?,?)", [("bmic", int(t + i * 60), 300000 + i * 1000, 5, 200000, 100000 + i * 1000, 0) for i in range(100)])
    c.execute("INSERT INTO ev_streams VALUES ('bmic','w1','SNAX','UCx','BMIC watch party','watch party',?,?,90000,?)", (t, t + 6000, t + 3000))
    c.execute("INSERT INTO ev_samples VALUES ('bmic',?, 'w1', 90000)", (int(t + 3000),))
    c.commit()
j = eventpage.channel_events(K)
names = [e["name"] for e in j["events"]]
assert names[:2] == ["BMIC 2026", "BMSD 2026"] and "PIC 2026" in names, names     # BGMI first, newest first
b = j["events"][0]
assert b["peak"] == 399000 and b["official_at_peak"] == 200000 and b["watch_at_peak"] == 199000 and b["watch_parties"][0]["channel"] == "SNAX"
assert j["bgmi_history"][0]["name"].startswith("BMIC 2026") and j["bgmi_history"][0]["peak"] == 399000
d = eventpage.day_event(K, "2026-11-01")
assert d["key"] == "bmic" and d["peak"] == 399000 and d["watch"] == 199000 and d["watch_parties"][0]["peak"] == 90000
assert eventpage.day_event(K, "2026-11-12") == {}
assert eventpage.channel_events("yt:UCsomeoneelse")["events"] == []
assert "__HISTBASE__" not in eventpage.build_html("bmic")
print("CHEVENTS OK")
