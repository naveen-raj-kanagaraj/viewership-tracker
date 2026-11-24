"""Rankings leave out viewbotted and banned channels, one-reading spikes and fragments. Share slides 11-30 ...
Run: python3 tests/test_bots.py"""
import os, sys, tempfile, json
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from tracker import store, scene, ranks, events, ytextra, profiles, platforms
scene._db(); ytextra._db(); profiles._db()
c = store.main()
D = lambda n: (datetime.now(events.REPORT_TZ).date() - timedelta(days=n)).strftime("%Y-%m-%d")
chans = [("twitch:real", "Real"), ("twitch:botty", "Botty"), ("twitch:spiky", "Spiky"), ("twitch:frag", "Frag"),
         ("twitch:banned", "Banned"), ("twitch:nofol", "NoFollowersYet")]
c.executemany("INSERT INTO sc_channels (sid, platform, name, india, country) VALUES (?,'twitch',?,1,'IN')", chans)
c.executemany("INSERT INTO sc_daily VALUES (?,?,?,?,?,?,?)", [
    (D(1), "twitch:real", "GTA 6", 4000, 0, 240, 10000),        # avg 2,500, 121K followers: real
    (D(1), "twitch:botty", "Just Chatting", 600, 0, 240, 1800),  # avg 450, 124 followers: viewbots
    (D(2), "twitch:spiky", "Other", 17184, 0, 90, 2886),         # avg 1,924, one reading at 17,184: spike ignored
    (D(3), "twitch:spiky", "Free Fire", 900, 0, 60, 700),        # a normal day: this is its peak
    (D(1), "twitch:frag", "Just Chatting", 996, 0, 6, 100),      # one 6-minute reading: not a stream
    (D(1), "twitch:banned", "GTA 6", 300, 0, 120, 400),
    (D(1), "twitch:nofol", "GTA 6", 200, 0, 120, 300)])
c.executemany("INSERT INTO ch_profile (sid, bio, links, checked, followers, gone) VALUES (?,?,?,?,?,?)", [
    ("twitch:real", "", "{}", 1, 121000, 0), ("twitch:botty", "", "{}", 1, 124, 0), ("twitch:spiky", "", "{}", 1, 50000, 0),
    ("twitch:banned", "", "{}", 1, None, 1), ("twitch:nofol", "", "{}", 1, None, 0)])
c.commit()
ranks.compute()
R = ranks._R["rows"]
assert set(R) == {"twitch:real", "twitch:spiky", "twitch:nofol"}, sorted(R)
assert R["twitch:spiky"]["peak_30d"] == 900, R["twitch:spiky"]["peak_30d"]
assert ranks._viewbot(634, 3088, 840) and ranks._viewbot(971, 589, 467) and not ranks._viewbot(53300, 4152, 1291)
assert not ranks._viewbot(40, 20, 12)                            # tiny streams are left alone
# the hand-checked bots are blocked by name everywhere
assert all(scene.name_blocked(n) for n in ("sazof36", "pepewwwpew", "kendra_shepard992", "rexar_live"))
# profiles: Twitch followers via the owner's login, banned logins marked gone
platforms._get = lambda p, url, params: {"data": [{"login": "real", "id": "1", "description": "x"}]}
platforms.twitch_followers = lambda uid: 121000 if uid == "1" else None
profiles.refresh(["twitch:real", "twitch:ghost"])
assert profiles.followers("twitch:real") == (121000, 0) and profiles.followers("twitch:ghost") == (None, 1)
print("BOTS OK")
