"""All-platform lists show each creator once (owner, 24 Nov: LoLzZz Gaming on YouTube and lolzzzgaming on Kick were #2
and #3). Run: python3 tests/test_one_creator.py"""
import os, sys, tempfile, time
os.environ["TRACKER_DB"] = tempfile.mkdtemp() + "/o.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import ranks, scene, store, ytextra as yx

with store._lock:
    scene._db(); yx._db()
rows = [{"sid": "kick:jonathangaming", "platform": "kick", "name": "jonathangaming", "peak_7d": 27800},
        {"sid": "yt:UClolz", "platform": "youtube", "name": "LoLzZz Gaming", "peak_7d": 26700},
        {"sid": "kick:lolzzzgaming", "platform": "kick", "name": "lolzzzgaming", "peak_7d": 22900},
        {"sid": "twitch:sky", "platform": "twitch", "name": "skyesports", "peak_7d": 19700},
        {"sid": "kick:skyesports", "platform": "kick", "name": "SkyEsports", "peak_7d": 9000},
        {"sid": "yt:UCother", "platform": "youtube", "name": "LoLzZz Gaming", "peak_7d": 500},      # same platform: kept
        {"sid": "kick:abc", "platform": "kick", "name": "abc", "peak_7d": 400},                      # short names never merge
        {"sid": "yt:UCabc", "platform": "youtube", "name": "ABC", "peak_7d": 300}]
out = yx.one_per_creator(rows, "peak_7d")
assert [r["sid"] for r in out] == ["kick:jonathangaming", "yt:UClolz", "twitch:sky", "yt:UCother", "kick:abc", "yt:UCabc"], [r["sid"] for r in out]
assert out[1]["also"] == [{"sid": "kick:lolzzzgaming", "platform": "kick", "name": "lolzzzgaming", "value": 22900, "hw": None}]
assert [a["sid"] for a in out[2]["also"]] == ["kick:skyesports"] and out[0]["also"] == []
assert "also" not in rows[1]                                          # the rankings' own rows are not changed

# hand links count too
store.kv_set("chan_links", [["kick:abc", "yt:UCabc"]])
out = yx.one_per_creator(rows, "peak_7d")
assert [a["sid"] for a in next(r for r in out if r["sid"] == "kick:abc")["also"]] == ["yt:UCabc"]
store.kv_set("chan_links", [])

# ranks.top: all platforms folded, one platform untouched
base = {"country": "IN", "country_name": "India", "category": "Gaming", "game": "BGMI"}
ranks._R.update(at=time.time(), rows={r["sid"]: {**base, **r} for r in rows[:5]}, rank={}, tot={})
t = ranks.top("all", "peak_7d", "IN", limit=10)
assert [r["sid"] for r in t["rows"]] == ["kick:jonathangaming", "yt:UClolz", "twitch:sky"] and t["total"] == 3, t["rows"]
assert [r["rank"] for r in t["rows"]] == [1, 2, 3] and t["rows"][1]["also"][0]["platform"] == "kick"
assert [r["sid"] for r in ranks.top("kick", "peak_7d", "IN", limit=10)["rows"]] == ["kick:jonathangaming", "kick:lolzzzgaming", "kick:skyesports"]
print("ONE PER CREATOR OK")
