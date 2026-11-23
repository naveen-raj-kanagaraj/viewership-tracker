"""Rankings run every 30 minutes and always at 00:05 India time. Run: python3 tests/test_ranks_daily.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import ranks, events
ist = events.REPORT_TZ
t = lambda *a: datetime(2026, 11, 23, *a, tzinfo=ist).timestamp()
assert ranks._next_wait(t(23, 50)) == 15 * 60            # 23:50 IST -> 00:05
assert ranks._next_wait(t(0, 4, 30)) == 30               # 00:04:30 -> 00:05
assert ranks._next_wait(t(0, 5)) == 1800                 # just ran at 00:05 -> every 30 min
assert ranks._next_wait(t(14, 0)) == 1800
print("RANKS DAILY OK")
