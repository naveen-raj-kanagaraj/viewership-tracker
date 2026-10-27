"""India scan, hub and category pages, against mocked YouTube/Kick/Twitch. Run: python tests/test_scene.py"""
import os, sys, time, json
import tempfile; T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/sc.db"
for f in ("sc.db", "sc.db-wal", "sc.db-shm"):
    try: os.remove(T + "/" + f)
    except FileNotFoundError: pass
os.environ.update(TWITCH_CLIENT_ID="x", TWITCH_CLIENT_SECRET="y", KICK_CLIENT_ID="k", KICK_CLIENT_SECRET="s")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(sys.path[0])
from tracker import events, platforms, scene, store, web

def vr(vid, ch, cid, title, watching, logo="//yt3.ggpht.com/a.jpg"):
    return {"videoRenderer": {"videoId": vid, "title": {"runs": [{"text": title}]},
            "ownerText": {"runs": [{"text": ch, "navigationEndpoint": {"browseEndpoint": {"browseId": cid}}}]},
            "viewCountText": {"runs": [{"text": f"{watching:,}"}, {"text": " watching"}]},
            "channelThumbnailSupportedRenderers": {"channelThumbnailWithLinkRenderer": {"thumbnail": {"thumbnails": [{"url": logo}]}}}}}
SEARCH = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": [
    {"itemSectionRenderer": {"contents": [
        vr("v1", "Soul Aman", "UCaman", "BGMI LIVE scrims day 2", 41000),
        vr("v2", "Total Gaming", "UCtg", "FREE FIRE MAX live rush", 88000),
        vr("v3", "Soul Aman", "UCaman", "BGMI second cam", 2000),
        vr("v4", "Tiny", "UCtiny", "bgmi live", 5),
        vr("v6", "Citizen TV Kenya", "UCkenya", "Citizen Live news", 9000),
        vr("v7", "Desi Vlogs", "UCnoctry", "हिंदी लाइव", 800),
        vr("v8", "Mystery Gamer", "UCnoctry2", "ranked grind", 700),
        {"videoRenderer": {"videoId": "v5", "title": {"runs": [{"text": "replay"}]}, "viewCountText": {"simpleText": "1.2M views"},
                           "ownerText": {"runs": [{"text": "X", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCx"}}}]}}}]}}]}}}}}
class R:
    def __init__(s, j): s._j = j; s.status_code = 200
    def json(s): return s._j
    def raise_for_status(s): pass
events._http.post = lambda url, json=None, **k: R(SEARCH)
LIVE = {"v1": 42000, "v2": 90000, "v3": 2100}
events.count_live = lambda vid: LIVE.get(vid)
def pget(url, params=None, headers=None, **k):
    if url.endswith("/oauth/token") or "oauth2" in url: return R({"access_token": "t", "expires_in": 3600})
    if url.endswith("/public/v1/livestreams"):
        return R({"data": [{"slug": "skyesports", "stream_title": "BMIC qualifiers", "viewer_count": 3200, "category": {"name": "PUBG Mobile"}, "language": "hi"},
                           {"slug": "desichatter", "stream_title": "chill stream", "viewer_count": 700, "category": {"name": "Just Chatting"}, "language": "hi"}]})
    if url.endswith("/public/v1/channels"):
        return R({"data": [{"slug": "skyesports", "stream_title": "BMIC qualifiers", "stream": {"is_live": True, "viewer_count": 3200}, "category": {"name": "PUBG Mobile"}}]})
    if url.endswith("/helix/streams"):
        return R({"data": [{"type": "live", "user_login": "indiavalo", "user_name": "IndiaValo", "title": "ranked", "viewer_count": 1500, "game_name": "VALORANT", "language": "hi"},
                           {"type": "live", "user_login": "smallguy", "user_name": "small", "title": "x", "viewer_count": 3, "game_name": "Minecraft", "language": "hi"}]})
    if url.endswith("/helix/users"): return R({"data": [{"login": "indiavalo", "profile_image_url": "https://t/iv.png"}]})
    raise AssertionError(url)
platforms._http.get = pget
platforms._http.post = lambda url, data=None, **k: R({"access_token": "t", "expires_in": 3600})
events.check_channel = lambda h: {"vid": "v9", "title": "Dynamo BGMI live", "channel": "Dynamo Gaming", "channel_id": "UCdyn", "viewers": 15000} if h == "@DynamoGaming" else None
LIVE["v9"] = 15500

LIVE.update({"v6": 9100, "v7": 820, "v8": 710})
CTRY = {"UCaman": "IN", "UCtg": "IN", "UCkenya": "KE", "UCnoctry": "-", "UCnoctry2": "-", "UCdyn": "IN"}
scene.yt_countries = lambda ids: {i: CTRY.get(i, "-") for i in ids}
t = time.time()
r = scene.cycle(now=t); print("cycle1:", r)
_names = {x["name"] for x in scene.data("today")["live"]}
assert "Citizen TV Kenya" not in _names and "Mystery Gamer" not in _names and "Desi Vlogs" in _names, _names
for x, ctry, exp in [({"platform": "youtube", "title": "FREE FIRE rush", "name": "TG"}, "IN", True),
                     ({"platform": "youtube", "title": "IND vs PAK live", "name": "PTV"}, "PK", False),
                     ({"platform": "youtube", "title": "BGMI live", "name": "x"}, "-", True),
                     ({"platform": "twitch", "title": "ranked", "name": "a", "language": "en"}, None, False),
                     ({"platform": "twitch", "title": "ranked", "name": "a", "language": "hi"}, None, True),
                     ({"platform": "kick", "title": "ranked", "name": "七兔", "language": "hi"}, None, False)]:
    assert scene.verdict(x, ctry) == exp, (x, ctry)
print("VERDICT OK")
d = scene.data("today")
print([(x["name"], x["platform"], x["game"], x["viewers"]) for x in d["live"]])
names = {x["name"]: x for x in d["live"]}
assert names["Soul Aman"]["viewers"] == 43000 and names["Soul Aman"]["game"] == "BGMI"     # two streams summed
assert names["Total Gaming"]["game"] == "Free Fire" and names["Total Gaming"]["logo"].startswith("https://")
assert names["skyesports"]["game"] == "BGMI" and names["skyesports"]["platform"] == "kick"
assert names["IndiaValo"]["game"] == "Valorant" and "Tiny" not in names and "small" not in names and "X" not in names
assert names["Dynamo Gaming"]["viewers"] == 15000
assert d["platforms"][0]["platform"] == "youtube"
# second cycle: YouTube re-counted from the live counter, no new search
LIVE["v2"] = 120000; del LIVE["v3"]
r = scene.cycle(now=t + 120); print("cycle2:", r)
d = scene.data("today"); names = {x["name"]: x for x in d["live"]}
assert names["Total Gaming"]["viewers"] == 120000 and names["Soul Aman"]["viewers"] == 42000, names["Soul Aman"]
b = {x["name"]: x for x in d["board"]}
print("board:", [(x["name"], x["hw"], x["peak"], x["avg"], x["airtime_h"]) for x in d["board"][:5]])
assert b["Total Gaming"]["peak"] == 120000 and b["Total Gaming"]["airtime_h"] == 0.1
print("games:", d["categories"][:3])
print(scene.top())
# CLI-equivalent: block
store.kv_set("scene_blocked", ["kick:desichatter"])
assert all(x["sid"] != "kick:desichatter" for x in scene.data()["live"])
c = web.app.test_client()
assert c.get("/india").status_code == 200
jj = json.loads(c.get("/india/data?period=7d", headers={"Accept-Encoding": ""}).data); assert jj["period"] == "7d" and jj["board"]
assert c.get("/india/data?period=evil").status_code == 200
print("SCENE OK")
# hub / categories
from tracker import scene as sc
d = sc.data("today", "bgmi"); print("bgmi:", d["cat_name"], d["live_total"], [x["name"] for x in d["live"]], len(d["series"]), d["peak"])
assert d["cat_name"] == "BGMI" and all(x["game"] == "BGMI" for x in d["live"]) and d["events"] == []
assert all(x["game"] == "BGMI" for x in d["board"]) and len(d["series"]) == 2 and d["india_total"] >= d["live_total"]
h = sc.data("today"); assert h["series"] and {c["slug"] for c in h["categories"]} >= {"bgmi", "free-fire"}
c = web.app.test_client()
for u, code in [("/", 200), ("/c/bgmi", 200), ("/c/free-fire", 200), ("/c/nonexistent", 404), ("/c/../x", 404), ("/api/scene?cat=bgmi", 200), ("/india", 200)]:
    r = c.get(u); assert r.status_code == code, (u, r.status_code)
assert b"Live Streaming Worldwide" in c.get("/").data and b"Live Streaming in India" in c.get("/india").data
store.kv_set("site_home", "nope"); assert c.get("/").status_code == 200
print("HUB OK")
# Kick/Twitch India detection: Hindi-language streams plus Indian-titled streams from top/category lists
_saved = sc._kick_live
sc._kick_live = lambda prm: ([{"vid": "kick:hindi1", "title": "chill", "viewers": 50, "language": "hi", "channel": "h"}] if prm.get("language")
                             else [{"vid": "kick:en1", "title": "BGMI rush with squad", "viewers": 900, "language": "en", "channel": "a"},
                                   {"vid": "kick:us1", "title": "ranked grind", "viewers": 9000, "language": "en", "channel": "b"},
                                   {"vid": "kick:dev", "title": "आज का स्ट्रीम", "viewers": 300, "language": "en", "channel": "c"}])
sc._category_id = lambda p, n: ""
got = {r["vid"] for r in sc.platform_india("kick", {})}
sc._kick_live = _saved
print("kick india:", sorted(got)); assert got == {"kick:hindi1", "kick:en1", "kick:dev"}
print("INDIA FILTER OK")
# 2-second Kick/Twitch readings override the scan values; ended channels drop out
sc.cycle(now=time.time())
_by = platforms._by_ids
platforms._by_ids = lambda p, ids: ([{"vid": "kick:skyesports", "viewers": 4100, "channel": "skyesports"}] if p == "kick"
                                    else [{"vid": "twitch:indiavalo", "viewers": 1750, "channel": "IndiaValo"}])
for k in range(3):
    sc.fast_once()
platforms._by_ids = _by
lv = {x["sid"]: x["viewers"] for x in sc.live_data()["live"]}
print("2s overlay:", {k: v for k, v in lv.items() if not k.startswith("yt:")})
assert lv["kick:skyesports"] == 4100 and lv["twitch:indiavalo"] == 1750 and "kick:desichatter" not in lv
assert all(x["logo"] for x in sc.live_data()["live"] if x["sid"].startswith("twitch:indiavalo"))
r = web.app.test_client().get("/api/scene/live?cat=bgmi", headers={"Accept-Encoding": ""})
assert r.status_code == 200 and all(x["game"] == "BGMI" for x in json.loads(r.data)["live"])
print("FAST OK")
# clean(): a channel found to be foreign leaves the India view (totals rebuilt) but stays in the global view
with store._lock:
    cc = sc._db(); cc.execute("UPDATE sc_channels SET country='US' WHERE sid='yt:UCtg'"); cc.commit()
res = sc.clean(); print("clean:", res)
assert "Total Gaming" in res["examples_not_indian"]
with store._lock:
    cc = sc._db()
    assert cc.execute("SELECT COUNT(*) FROM sc_cat WHERE game='Free Fire'").fetchone()[0] == 0
assert all(x["name"] != "Total Gaming" for x in sc.data("7d")["board"])
assert any(x["name"] == "Total Gaming" for x in sc.data("7d", region="global")["board"])
print("CLEAN OK")

# global view and tournaments
for title, game, exp in [("VCT Masters Toronto - Grand Final", "Valorant", "VCT"), ("LCK Spring Week 3 T1 vs GEN", "League of Legends", "LCK"),
                         ("BGIS 2026 Grand Finals Day 2", "BGMI", "BGIS"), ("ranked grind to radiant", "Valorant", None),
                         ("Worlds 2026 Finals", "League of Legends", "LoL Worlds"), ("Minecraft worlds tour", "Minecraft", None),
                         ("Regional Championship Day 2 | Team A vs Team B", "Free Fire", "Free Fire tournaments"),
                         ("BGMI scrims finals", "BGMI", None), ("having a blast lol", "Fortnite", None)]:
    assert sc.tournament(title, game) == exp, (title, sc.tournament(title, game))
SEARCH["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"].append(
    vr("v10", "VALORANT Esports", "UCvct", "VCT Champions 2026 - Grand Final - FNC vs SEN", 250000))
LIVE["v10"] = 251000; CTRY["UCvct"] = "US"
sc._STATE["yt"] = 0
r = sc.cycle(now=t + 240); print("global cycle:", r)
g = sc.data("today", region="global"); i_ = sc.data("today")
gn = {x["name"] for x in g["live"]}
assert "VALORANT Esports" in gn and "Citizen TV Kenya" in gn and "VALORANT Esports" not in {x["name"] for x in i_["live"]}
assert g["live_total"] > i_["live_total"] and g["tournaments"][0]["name"] == "VCT", g["tournaments"][:1]
print("tournaments:", [(t["name"], t["viewers"], t["streams"]) for t in g["tournaments"]])
c = web.app.test_client()
for u in ["/", "/c/valorant", "/india/c/bgmi", "/api/scene?region=global", "/api/scene/live?region=global&cat=valorant"]:
    assert c.get(u).status_code == 200, u
lv = json.loads(c.get("/api/scene/live?region=global", headers={"Accept-Encoding": ""}).data)
assert lv["tournaments"] and lv["live_total"] >= 250000
print("GLOBAL OK")
# sections, KPIs, section pages
d = sc.data("today", region="global")
secs = {s["key"]: s for s in d["sections"]}
assert [s["key"] for s in d["sections"]] == [k for k, _ in sc.SECTIONS]
assert secs["esports"]["viewers"] >= 250000 and secs["gaming"]["viewers"] > 0 and secs["news"]["viewers"] > 0
k = d["kpis"]; print("kpis:", {x: k[x] for x in ("watching", "live_channels", "peak_today", "hw_today", "channels_today")})
assert k["watching"] == d["live_total"] and k["live_channels"] == len(d["live"]) and k["peak_today"] >= k["watching"]
g = sc.data("today", region="global", sec="gaming")
assert all(x["section"] == "gaming" for x in g["live"]) and g["kpis"]["watching"] < k["watching"]
e = sc.data("today", region="global", sec="esports")
assert e["board"] == [] and e["tour_day"] and e["tour_day"][0]["name"] == "VCT"
lvd = sc.live_data(region="in", sec="news"); assert all(x["section"] == "news" for x in lvd["live"]) and "kpis" in lvd
assert all("last_live" in x for x in sc.data("7d")["board"])
c = web.app.test_client()
for u, code in [("/s/gaming", 200), ("/s/esports", 200), ("/india/s/gaming", 200), ("/global/s/esports", 301), ("/global", 301), ("/s/nope", 404), ("/api/scene?sec=irl", 200), ("/api/scene/live?region=global&sec=esports", 200)]:
    assert c.get(u).status_code == code, u
print("SECTIONS OK")
# cover art: exact names only, BGMI never gets PUBG's cover
def art_get(url, params=None, headers=None, **k):
    if url.endswith("/helix/games"):
        n = params["name"]
        return R({"data": [{"name": n, "box_art_url": f"https://tw/{n}-{{width}}x{{height}}.jpg"}]} if n in ("PUBG MOBILE", "PUBG: BATTLEGROUNDS") else {"data": []})
    if url.endswith("/public/v1/categories"):
        return R({"data": [{"name": "PUBG Mobile", "thumbnail": "https://k/pubgm.jpg"},
                           {"name": "Battlegrounds Mobile India", "thumbnail": "https://k/bgmi.jpg"}] if "Battlegrounds" in params["q"] or "PUBG" in params["q"]
                          else [{"name": "Something Else", "thumbnail": "https://k/x.jpg"}]})
    raise AssertionError(url)
platforms._http.get = art_get
assert sc.resolve_art("BGMI") == ("https://k/bgmi.jpg", "Kick 'Battlegrounds Mobile India'"), sc.resolve_art("BGMI")
assert sc.resolve_art("PUBG Mobile")[0] == "https://tw/PUBG MOBILE-144x192.jpg"
assert sc.resolve_art("PUBG: Battlegrounds")[0] == "https://tw/PUBG: BATTLEGROUNDS-144x192.jpg"
assert sc.resolve_art("Hollow Knight") == ("", "none")          # inexact search results are never used
assert sc.cat_art("Call of Duty") == "" and sc.cat_art("Cricket games") == ""
print("ART OK")
r = web.app.test_client().get("/global/c/bgmi"); assert r.status_code == 301 and r.headers["Location"].endswith("/c/bgmi")
print("ROUTES OK")
# biggest YouTube channels re-counted every 2s
sc._YTF["next"] = 0
events.count_live = lambda vid: {"v10": 260000, "v2": 125000}.get(vid, 0)
n = sc.yt_fast_once(); lv = {x["sid"]: x["viewers"] for x in sc.live_data(region="global")["live"]}
print("yt fast:", n, lv.get("yt:UCvct"), lv.get("yt:UCtg"))
assert lv["yt:UCvct"] == 260000 and lv["yt:UCtg"] == 125000
print("YT FAST OK")
# search any channel ever seen, the globe, peak leader, game history, CEGC
assert "cegc" in sc.seeds()["kick"] and "skyesports" in sc.seeds()["kick"]
assert sc.tournament("CEGC 2026 day 3 | BGMI", "BGMI") == "CEGC"
j = c.get("/api/search?q=soul&region=global").get_json()
assert any(x["name"] == "Soul Aman" for x in j["channels"]), j
assert c.get("/api/search?q=bgm&region=in").get_json()["categories"][0]["game"] == "BGMI"
assert c.get("/api/search?q=a").get_json() == {"channels": [], "categories": []}
g = c.get("/api/geo").get_json()
assert any(z["country"] == "IN" and z["num"] == 356 and z["top"] for z in g["countries"]), g
assert sc.country_of("United States") == ("US", 840, "United States") and sc.country_of("-") is None
k = sc.data("today", region="global")["kpis"]
assert k["peak_lead"] and k["peak_lead"]["name"], k
b = sc.data("today", "bgmi", "in")
assert b["history"] and b["history"][-1]["name"].startswith("BMSD") and all(e["game"] == "BGMI" for e in b["events"])
assert all(e["state"] in ("live", "upcoming") for e in sc.data("today", region="in")["events"])
for u in ("/map", "/india/c/bgmi"):
    assert c.get(u).status_code == 200, u
print("SEARCH/GEO/HISTORY OK")
ca = c.get("/api/channel?sid=yt:UCaman").get_json()
assert ca["name"] == "Soul Aman" and ca["periods"]["today"]["peak"] > 0 and ca["days"] and set(ca["periods"]) == {"today", "7d", "30d", "all"}, ca
assert c.get("/api/channel?sid=bad").status_code == 404
assert "daily" in sc.data("today", region="global") and c.get("/map?embed=1").status_code == 200
print("CHANNEL OK")
