"""Bios decide who is Indian when the chat hasn't; Indians abroad count. Run: python3 tests/test_profiles.py"""
import os, sys, tempfile
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/a.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import scene, profiles, platforms, ytextra, store
scene._db(); ytextra._db(); profiles._db()
W = lambda sid, title, bio: scene.india_why({"sid": sid, "platform": sid.split(":")[0], "title": title, "name": sid.split(":")[1], "bio": bio})
assert W("twitch:a", "GTA 6 Live", "Mumbai based gamer | business: a@b.com") == (True, "bio: 'Mumbai'")
assert W("twitch:b", "GTA 6 Live", "Streamer from Toronto 🇨🇦") == (False, "bio shows another country")
assert W("twitch:c", "GTA 6 Live", "British Indian gamer girl 🇬🇧🇮🇳")[0] is True
assert W("kick:d", "GTA 6 Live", "हिंदी गेमिंग चैनल") == (True, "bio: written in an Indian script")
assert W("twitch:e", "GTA 6 Live", "just vibes")[0] is False
assert W("twitch:f", "Playing GTA 6 | 🇬🇧🇮🇳 British Indian Gamergirl", "")[0] is True      # diaspora in the title
assert scene.foreign_sign("Streaming from London 🇬🇧") and not scene.foreign_sign("🇬🇧🇮🇳 London")
# fetch: Twitch description, Kick description + kick.com bio and social handles
platforms._get = lambda p, url, params: {"data": [{"login": "a", "description": "Delhi | GTA RP"}]} if p == "twitch" else \
    {"data": [{"slug": "k", "channel_description": "Hindi streams"}]}
ytextra.kick_info = lambda s: {"user": {"bio": "gaming daily", "instagram": "k_insta", "twitter": "k_x"}}
assert profiles.refresh(["twitch:a", "kick:k"]) == 2
assert profiles.bio("twitch:a") == "Delhi | GTA RP" and profiles.bio("kick:k") == "Hindi streams gaming daily"
assert profiles.links("kick:k") == {"instagram": "k_insta", "twitter": "k_x"}
profiles._P.clear(); profiles.load()
assert profiles.bio("kick:k") == "Hindi streams gaming daily"
assert scene.india_why({"sid": "kick:k", "platform": "kick", "title": "GTA 6", "name": "k"}) == (True, "bio: 'Hindi'")
print("PROFILES OK")
