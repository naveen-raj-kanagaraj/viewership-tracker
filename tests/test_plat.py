"""Platform connectors and per-event pages, against mocked Kick/Twitch/YouTube. Run: python tests/test_plat.py"""
import os, sys, time, json, subprocess
import tempfile; T = tempfile.mkdtemp()
os.environ["TRACKER_DB"] = T + "/t.db"
for f in ("t.db", "t.db-wal", "t.db-shm"):
    try: os.remove(T + "/" + f)
    except FileNotFoundError: pass
os.environ.update(TWITCH_CLIENT_ID="x", TWITCH_CLIENT_SECRET="y")
os.environ.pop("KICK_CLIENT_ID", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(sys.path[0])
from tracker import events, platforms, eventpage, store, web

KV = {"tarik": 900, "valorant": 30000}
TV = {"valorant": 52000, "shroud": 4000}
class R:
    def __init__(s, j, code=200): s._j, s.status_code = j, code
    def json(s): return s._j
    def raise_for_status(s):
        if s.status_code >= 400: raise RuntimeError(s.status_code)
calls = []
def post(url, data=None, **k):
    calls.append(("POST", url)); return R({"access_token": "tok", "expires_in": 3600})
def get(url, params=None, headers=None, **k):
    calls.append(("GET", url))
    if "kick.com/api/v2/channels/" in url:
        slug = url.rsplit("/", 1)[1]
        if slug not in KV: return R({"slug": slug, "user": {"username": slug, "profile_pic": "https://k/p.png"}, "livestream": None})
        return R({"slug": slug, "user": {"username": slug.title(), "profile_pic": f"https://k/{slug}.png"},
                  "livestream": {"is_live": True, "viewer_count": KV[slug], "session_title": f"VCT Pacific day 1 {slug}",
                                 "categories": [{"name": "VALORANT"}]}})
    if url.endswith("/helix/streams"):
        ps = params if isinstance(params, list) else list(params.items())
        logins = [v for k_, v in ps if k_ == "user_login"]
        if any(k_ == "game_id" for k_, _ in ps):
            logins = ["randomguy", "valorant"]
            TV.setdefault("randomguy", 700)
        return R({"data": [{"type": "live", "user_login": l, "user_name": l.title(), "title": ("VCT Pacific " if l != "randomguy" else "ranked grind ") + l,
                            "viewer_count": TV[l], "game_name": "VALORANT"} for l in logins if l in TV]})
    if url.endswith("/helix/games"): return R({"data": [{"id": "516575", "name": "VALORANT"}]})
    if url.endswith("/helix/users"): return R({"data": [{"login": v, "profile_image_url": f"https://t/{v}.png"} for k_, v in params]})
    raise AssertionError(url)
platforms._http.post, platforms._http.get = post, get
events.search_live = lambda q: []
events.channel_live_all = lambda c, limit=8: []
events.check_channel = lambda h: None

# custom event via CLI
env = dict(os.environ)
def cli(*a):
    r = subprocess.run([sys.executable, "track.py", *a], capture_output=True, text=True, env=env)
    print("$ track.py", *a, "\n", r.stdout.strip(), r.stderr.strip()); assert r.returncode == 0
cli("new", "valo", "VCT Pacific", "--game", "Valorant", "--match", "vct,pacific", "--queries", "VCT Pacific")
cli("kick", "valo", "official", "https://kick.com/valorant")
cli("kick", "valo", "add", "tarik")
cli("kick", "valo", "add", "nobody")
cli("twitch", "valo", "official", "valorant")
cli("twitch", "valo", "add", "shroud")
cli("twitch", "valo", "category", "VALORANT")
cli("platforms")
ev = events.get("valo")
assert ev["game"] == "Valorant" and ev["kick"]["official"] == ["valorant"], ev
assert events.get(None) is not None

r = events.poll(ev)
vids = {s["vid"]: (s["viewers"], s["kind"]) for s in r["streams"]}
print("poll:", vids)
assert vids == {"kick:valorant": (30000, "official"), "kick:tarik": (900, "watch party") if events.allowed_list(ev) else (900, "community"),
                "twitch:valorant": (52000, "official"), "twitch:shroud": (4000, "community")}, vids
assert "twitch:randomguy" not in vids        # category stream whose title doesn't match is ignored
# live counter: batched, cached
n0 = len([c for c in calls if "helix/streams" in c[1]])
t = time.time()
for i in range(5):
    out = events.fast_tick(ev, now=t + i * 2)
n1 = len([c for c in calls if "helix/streams" in c[1]])
print("fast_tick:", out, "twitch calls during 5 ticks:", n1 - n0)
assert out["total"] == 30000 + 900 + 52000 + 4000 and out["official_live"], out
assert n1 - n0 <= 2, n1 - n0
TV["valorant"] = 61000
platforms._snap["twitch"]["ts"] = 0
out = events.fast_tick(ev, now=t + 20)
assert out["total"] == 30000 + 900 + 61000 + 4000, out
# stream goes offline on Kick
del KV["tarik"]; platforms._snap["kick"]["ts"] = 0
for i in range(4):
    platforms._snap["kick"]["ts"] = 0
    out = events.fast_tick(ev, now=t + 30 + i * 2)
print("after tarik offline:", out)
assert out["total"] == 30000 + 61000 + 4000, out
st = events.stats("valo", until=t + 100)
print("platforms:", st["platforms"], st["platform_names"])
print("peak", st["peak"]); assert {x["platform"] for x in st["platforms"]} == {"kick", "twitch"} and st["peak"] == 30000 + 900 + 61000 + 4000 and {x["platform"]: x["peak"] for x in st["platforms"]} == {"twitch": 65000, "kick": 30900}
d = eventpage.data("valo")
assert all(x["platform"] in ("kick", "twitch") for x in d["live"]) and d["live"][0]["url"].startswith("https://www.twitch.tv/")
assert d["live"][0]["logo"] == "https://t/valorant.png", d["live"][0]
print("live:", [(x["channel"], x["platform"], x["viewers"], x["url"]) for x in d["live"]])
print(events.summary("valo"))
# web routes
c = web.app.test_client()
h = c.get("/e/valo/"); assert h.status_code == 200
assert b"const ENDED=false, CUR=[], GAME=\"Valorant\", NEEDOFF=true" in h.data
j = c.get("/e/valo/data", headers={"Accept-Encoding": ""}); assert j.status_code == 200
jj = json.loads(j.data); assert jj["platform_names"] == ["Kick", "Twitch"] and jj["name"] == "VCT Pacific", jj.get("platform_names")
print("cache header /e/valo/data:", j.headers["Cache-Control"])
assert c.get("/e/valo/series").status_code == 200
day = time.strftime("%Y-%m-%d", time.localtime(t + 5.5 * 3600 - time.localtime().tm_gmtoff))
ds = json.loads(c.get(f"/e/valo/daystreams/{events.datetime.fromtimestamp(t, events.REPORT_TZ).strftime('%Y-%m-%d')}").data)
print("daystreams:", [(x["channel"], x["platform"]) for x in ds["official"] + ds["watch"]])
assert c.get("/e/nope/").status_code == 404 and c.get("/e/valo").status_code == 301
assert c.get("/events").status_code == 200 and b"VCT Pacific" in c.get("/events").data
# BMIC home + unchanged YouTube path
cli("create", "bmic")
assert events.get(None)["key"] == "bmic", events.get(None)["key"]      # home preset wins over the newer valo
assert b"Live Streaming Worldwide" in c.get("/").data and b"Live Streaming in India" in c.get("/india").data; cli("home", "bmic"); hb = c.get("/").data
assert b"CUR=[\"BMIC\", \"26\"]" in hb
assert events._count_one.__name__ and events.yt_link("abcdefghijk") == "https://youtu.be/abcdefghijk"
cli("kick", "valo", "remove", "tarik")
assert events.get("valo")["kick"]["channels"] == ["nobody"]
print("ALL OK")
