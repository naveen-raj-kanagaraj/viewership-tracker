"""Live lists (owner, 26 Nov: no restarts while people are on the site): tracker/live/<event>.json adds YouTube / Kick /
Twitch channels and takes streams off while the tracker runs; autoupdate pulls commits that only touch tracker/live/
without restarting, and code waits for the broadcast to end. Run: python3 tests/test_live_lists.py"""
import json, os, subprocess, sys, tempfile, time, pathlib
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/l.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import events, autoupdate
ev = events.create("pmgc")
d = pathlib.Path(tempfile.mkdtemp())
events.LIVE_DIR = d
(d / "pmgc.json").write_text(json.dumps({"youtube": ["UCnew"], "kick": ["Ghatak"], "exclude": ["badvid", "UCbad"], "count": ["UCforced"]}))
events._LL.clear()
ll = events.live_list("pmgc")
assert ll["youtube"] == ["UCnew"] and ll["kick"] == ["Ghatak"]
assert "ghatak" in events.preset("pmgc")["kick"]["channels"] and "snaxgaming" in events.preset("pmgc")["kick"]["channels"]
s = lambda vid, cid, t: {"vid": vid, "channel": "x", "channel_id": cid, "title": t, "viewers": 5}
assert not events.relevant(ev, s("badvid", "UCok", "PMGC 2026 watch party"))
assert not events.relevant(ev, s("v2", "UCbad", "PMGC 2026 watch party"))
assert events.relevant(ev, s("v3", "UCforced", "BGMI rank push"))          # counted by hand: no checks
assert events.relevant(ev, s("v4", "UCok", "PMGC 2026 watch party"))
assert events.platforms.listed(ev, events.preset("pmgc"), "kick:ghatak")
# a change to the file is read again (no restart)
time.sleep(0.01)
(d / "pmgc.json").write_text(json.dumps({"exclude": []}))
os.utime(d / "pmgc.json", (time.time() + 5, time.time() + 5))
events._LL["pmgc"] = (0, events._LL["pmgc"][1], events._LL["pmgc"][2])
assert events.relevant(events.events()["pmgc"], s("badvid", "UCok", "PMGC 2026 watch party"))

# autoupdate: a commit touching only tracker/live/ is pulled without a restart, even on air; code waits
g = lambda cwd, *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout
root = pathlib.Path(tempfile.mkdtemp())
g(root, "init", "-q", "--bare", "origin.git")
g(root, "clone", "-q", "origin.git", "server")
srv, dev = root / "server", root / "dev"
(srv / "tracker" / "live").mkdir(parents=True)
(srv / "tracker" / "live" / "pmgc.json").write_text("{}")
(srv / "tracker" / "a.py").write_text("x = 1\n")
(srv / "track.py").write_text("y = 1\n")
g(srv, "add", "-A"); g(srv, "commit", "-q", "-m", "start"); g(srv, "push", "-q", "origin", "HEAD:main")
g(srv, "branch", "-q", "-M", "main"); g(srv, "branch", "-q", "--set-upstream-to=origin/main")
g(root, "clone", "-q", "-b", "main", "origin.git", "dev")
autoupdate.ROOT = str(srv)
autoupdate._on_air = lambda: True
execs = []
autoupdate.os.execv = lambda *a: execs.append(a)
(dev / "tracker" / "live" / "pmgc.json").write_text('{"kick": ["ghatak"]}')
g(dev, "commit", "-qam", "add ghatak"); g(dev, "push", "-q", "origin", "main")
r = autoupdate.check_once()
assert r.startswith("live lists updated") and not execs and "ghatak" in (srv / "tracker" / "live" / "pmgc.json").read_text(), r
(dev / "tracker" / "a.py").write_text("x = 2\n")
g(dev, "commit", "-qam", "code change"); g(dev, "push", "-q", "origin", "main")
assert autoupdate.check_once() == "skipped: a tournament broadcast is live" and not execs
autoupdate._on_air = lambda: False
autoupdate.check_once()
assert execs and "x = 2" in (srv / "tracker" / "a.py").read_text()   # off air: code updates and restarts
print("LIVE LISTS OK")
