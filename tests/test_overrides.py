"""The daily review's decisions (overrides.json) apply without a deploy. Run: python3 tests/test_overrides.py"""
import os, sys, tempfile, json
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from tracker import store, scene, ranks, events, ytextra, overrides
scene._db(); ytextra._db()
# the repo copy is valid and has today's decisions
repo = overrides._read(os.path.join(overrides.ROOT, "overrides.json"))
assert "twitch:sazof36" in repo["block"] and "twitch:invadingdarkness" in repo["india"]
# a fetched copy (from GitHub) wins over the repo copy
class R:
    status_code = 200
    text = json.dumps({"india": ["kick:newin"], "not_india": ["Twitch:NotIn"], "block": ["kick:Botter", "yt:UCbad"],
                       "category": {"yt:UCcarry": "Gaming", "Kick:Mix": "Sports"}})
events._http.get = lambda url, **k: R()
assert overrides.fetch()
assert overrides.blocked("kick:botter") and overrides.blocked("yt:UCbad") and not overrides.blocked("yt:ucbad")
assert scene.name_blocked("Botter") and not scene.name_blocked("sazof36_fan")
assert scene.india_why({"sid": "kick:newin", "platform": "kick", "title": "x", "name": "newin"}) == (True, "owner: Indian")
assert scene.india_why({"sid": "twitch:notin", "platform": "twitch", "title": "Hindi stream", "name": "notin"}) == (False, "owner: not Indian")
# rankings: blocked channels out, category overrides in
c = store.main()
d = datetime.now(events.REPORT_TZ).date().strftime("%Y-%m-%d")
c.executemany("INSERT INTO sc_channels (sid, platform, name, india, country, ytcat) VALUES (?,?,?,1,'IN',?)",
              [("yt:UCcarry", "youtube", "CarryisLive", "Entertainment"), ("yt:UCbad", "youtube", "Bad", "Gaming"),
               ("kick:mix", "kick", "mix", None), ("kick:botter", "kick", "Botter", None)])
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [(d, s, "Other", 1000, 0, 120, 1500) for s in ("yt:UCcarry", "yt:UCbad", "kick:mix", "kick:botter")])
c.commit()
ranks.compute()
R_ = ranks._R["rows"]
assert set(R_) == {"yt:UCcarry", "kick:mix"}, sorted(R_)
assert R_["yt:UCcarry"]["category"] == "Gaming" and R_["kick:mix"]["category"] == "Sports"
# a broken download never replaces the last good copy
R.text = "not json"
assert not overrides.fetch() and overrides.blocked("kick:botter")
print("OVERRIDES OK")
