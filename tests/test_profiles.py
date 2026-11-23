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
# a Twitch 'Hindi' tag alone doesn't decide; Portuguese / Spanish titles are foreign
assert W("twitch:dr", "🔥[FREE + SUB DROPS]🔥 GRAND THEFT AUTO VI", "")[0] is False
assert scene.india_why({"sid": "twitch:dr", "platform": "twitch", "title": "GTA VI", "name": "dr", "tags": "English Hindi", "bio": ""})[0] is False
assert scene.india_hint({"sid": "twitch:dr", "title": "GTA VI", "tags": "English Hindi", "name": "dr"})      # its chat gets read
assert scene.india_why({"sid": "twitch:india_noob_", "platform": "twitch", "title": "Live 812 -  Dando uma volta em Vice city",
                        "name": "India_Noob_", "bio": ""}) == (False, "title / tags show another country")
assert not scene.foreign_sign("bhai log aaj GTA 6 khelenge") and not scene.foreign_sign("Hindi stream de do like")
print("TAGS + OTHER LANGUAGES OK")
# Twitch 'Hindi' language setting alone: not Indian (Pakistani streamers pick it), but its chat gets read;
# a language only spoken in India still decides; the owner's list wins
x = {"sid": "twitch:hi1", "platform": "twitch", "title": "GTA 6", "name": "hi1", "language": "hi", "bio": ""}
assert scene.india_why(x)[0] is False and scene.india_hint(x)
assert scene.india_why({**x, "sid": "twitch:ml1", "language": "ml"}) == (True, "stream language: ml")
assert scene.india_why({**x, "sid": "twitch:sig07tv"}) == (False, "owner: not Indian")
# the Twitch language sweep pages through every Indian-language stream down to the minimum viewers
pages = []
def fake(p, url, params):
    pages.append(params.get("language"))
    n = len([q for q in pages if q == params.get("language")])
    return {"data": [{"type": "live", "user_login": f"{params['language']}{n}{i}", "viewer_count": 50 if n < 3 else 1,
                      "title": "t", "game_name": "GTA 6", "language": params["language"]} for i in range(3)],
            "pagination": {"cursor": "c"}}
platforms._get = fake
scene._category_id = lambda p, n: None
rows = scene.platform_india("twitch", {})
assert pages.count("hi") == 3 and pages.count("ta") == 3, pages          # stops at the page with small streams
print("LANGUAGE SWEEP OK")
