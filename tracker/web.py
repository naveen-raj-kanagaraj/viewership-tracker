"""Public, read-only live dashboard for the tracked events (only public stream numbers, nothing about users).

/            the home event (preset "home": True, or `track.py home <key>`)
/e/<key>/    any event's own dashboard (same page; its relative fetches resolve under /e/<key>/)
/events      every event, with links

Runs on its own port (EVENT_WEB_PORT, default 8092, this computer only) so the owner dashboard on 8090 is never
exposed. core/tunnel.py gives it a public https link that opens on any device.
"""
import gzip
import json
import logging
import os
import threading
import time
import queue

from flask import Flask, Response, request

from tracker import eventpage, predict, predictpage, visitors

PORT = int(os.getenv("EVENT_WEB_PORT", "8092"))
app = Flask(__name__)


CACHE = {"/api/cats": 60, "/api/catmonths": 600, "/categories": 300, "/india/categories": 300, "/privacy": 3600, "/terms": 3600, "/api/chlive": 2, "/badge": 1800, "/api/badges": 600, "/api/home": 120, "/api/compare": 30, "/compare": 300, "/india/compare": 300, "/api/topch": 120, "/api/videos": 300, "/api/lookup": 600, "/api/moments": 20, "/moments": 300, "/india/moments": 300, "/api/ytsearch": 600, "/api/past": 600, "/api/rank": 30, "/rankings": 300, "/india/rankings": 300, "/api/channel": 20, "/map": 300, "/api/geo": 5, "/api/search": 30, "/india": 30, "/india/data": 20, "/api/scene": 20, "/api/scene/live": 2, "/": 5, "/data": 2, "/series": 60, "/predict": 30, "/predict/api/board": 5, "/predict/og.png": 3600}   # seconds Cloudflare (or any CDN) may reuse a response



@app.before_request
def _predict_closed():
    # Predict & Win is off the public site unless PREDICT_OPEN=1. Players' data stays in the database and the
    # 10-minute exports (exports/predict, exports/private); only the pages and API are hidden.
    if request.path.startswith("/predict") and os.getenv("PREDICT_OPEN", "0") != "1":
        if os.getenv("PREDICT_SPLIT", "1") == "1" and request.method == "GET":
            if request.path in ("/predict", "/predict/"):      # the game is closed: show what the community predicted
                from tracker import crowdpage
                try:
                    r = _memo("/predict-results", 60, crowdpage.build_html, "text/html")
                except Exception as e:
                    print(f"Predict results page failed: {str(e)[:150]}")
                    return Response("Not found", status=404, mimetype="text/plain")
                r.headers["Cache-Control"] = "public, max-age=30, s-maxage=30"
                return r
            if request.path == "/predict/og.png":
                return None
        return Response("Not found", status=404, mimetype="text/plain")

@app.after_request
def _headers(resp):
    path = request.path
    if path.startswith("/e/"):                       # /e/<key>/data caches like /data
        parts = path.split("/", 3)                   # ['', 'e', key, rest]
        path = "/" + (parts[3] if len(parts) > 3 else "")
    elif path.startswith(("/ch/", "/india/ch/")):
        path = "/map"
    elif path.startswith("/badge/"):
        path = "/badge"
    elif path.startswith(("/c/", "/s/", "/india/c/", "/india/s/")):
        path = "/india"
    secs = CACHE.get(path)
    if resp.headers.pop("X-Short-Cache", None):
        secs = 3
    if request.path.startswith("/predict/api/profile/") and request.method == "GET":
        secs = 15
    if request.method != "GET" or resp.status_code >= 400:
        secs = None                       # POSTs, personal and error responses are never cached
    if request.path.startswith(("/elogo/", "/tlogo/", "/pimg/", "/tmark/", "/gameart/")):
        return resp
    resp.headers["Cache-Control"] = f"public, max-age={secs}, s-maxage={secs}" if secs else "no-store"
    if secs:   # Cloudflare's Browser Cache TTL can override max-age; this one it passes through for its own cache
        resp.headers["CDN-Cache-Control"] = f"max-age={secs}"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    if (resp.status_code == 200 and not resp.direct_passthrough and "Content-Encoding" not in resp.headers and "gzip" in request.headers.get("Accept-Encoding", "")
            and len(resp.get_data()) > 1024):
        resp.set_data(gzip.compress(resp.get_data(), 5))
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Vary"] = "Accept-Encoding"
    return resp


# ---- in-memory response cache: thousands of viewers poll the same numbers, so each response is built once
# per TTL (one thread builds it, the rest wait for that copy) and handed out as ready-made gzip bytes.
_MEMO, _MLOCK = {}, {}


_STALE_MAX = 600      # an expired response is still served (and rebuilt in the background) for up to this long


def _memo_build(key, build):
    body = build()
    if isinstance(body, str):
        body = body.encode()
    hit = (time.time(), body, gzip.compress(body, 5) if len(body) > 1024 else None)
    if len(_MEMO) > 3000:                     # search keys are open-ended: drop stale entries
        for k in [k for k, v in list(_MEMO.items()) if time.time() - v[0] > _STALE_MAX]:
            _MEMO.pop(k, None)
            _MLOCK.pop(k, None)
    _MEMO[key] = hit
    return hit


# Instant page changes: Chrome/Edge prerender a link when you hover or press it (speculation rules); other browsers
# (Safari) fetch the page early on touch/hover, so the click finds it ready.
FASTNAV = """<script type="speculationrules">{"prerender":[{"where":{"and":[{"href_matches":"/*"},{"not":{"href_matches":"/api/*"}},{"not":{"href_matches":"/e/*"}}]},"eagerness":"moderate"}]}</script>
<script>(function(){var done={};function pf(e){var a=e.target.closest&&e.target.closest('a[href^="/"]');if(!a||a.target||done[a.href]||HTMLScriptElement.supports&&HTMLScriptElement.supports('speculationrules'))return;done[a.href]=1;var l=document.createElement('link');l.rel='prefetch';l.href=a.href;document.head.appendChild(l)}
document.addEventListener('touchstart',pf,{passive:true});document.addEventListener('mouseover',pf,{passive:true})})()</script>
<script>(function(){var p=location.pathname.replace(/\\/+$/,'')||'/',bar=document.querySelector('.top .in')||document.querySelector('.bar .in');
if(p==='/'||p==='/india'||/[?&]embed=/.test(location.search)||!bar)return;
var home=(p.indexOf('/india')===0||p.indexOf('/e/')===0)?'/india':'/',st=document.createElement('style');
st.textContent='.bk{display:inline-flex;align-items:center;gap:6px;flex:none;height:32px;padding:0 10px 0 6px;margin-right:2px;border:1px solid #262636;background:#13131c;color:#eeeef5;text-decoration:none;font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.06em}.bk:hover{border-color:#b6f23a;color:#b6f23a}.bk svg{flex:none}@media(max-width:640px){.bk{padding:0 7px}.bk span{display:none}}@media(max-width:420px){.top .beta{display:none}.top .in{gap:8px!important}.top .rg a{padding-left:7px!important;padding-right:7px!important}.top .upd{display:none!important}}';
document.head.appendChild(st);var a=document.createElement('a');a.className='bk';a.href=home;a.setAttribute('aria-label','Back');
a.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg><span>BACK</span>';
a.onclick=function(e){var r=document.referrer;if(r&&r.indexOf(location.origin+'/')===0&&history.length>1){e.preventDefault();history.back()}};
bar.insertBefore(a,bar.firstChild)})()</script>
<script>(function(){if(/[?&]embed=/.test(location.search)||location.pathname.indexOf('/e/')===0)return;var k;try{k=sessionStorage.getItem('lge_s');if(!k){k=Math.random().toString(36).slice(2)+Date.now().toString(36);sessionStorage.setItem('lge_s',k)}}catch(e){k=Math.random().toString(36).slice(2)}
var r=document.referrer&&document.referrer.indexOf(location.origin)!==0?document.referrer:'';
function ping(){if(document.hidden)return;try{fetch('/hit',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:k,ref:r,w:innerWidth})}).catch(function(){})}catch(e){}}
ping();setInterval(ping,30000);document.addEventListener('visibilitychange',ping);
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('.rg a');if(!a)return;var h=a.getAttribute('href')||'';try{localStorage.setItem('lge_region',h.indexOf('/india')===0?'in':'global')}catch(x){}},true)})()</script>"""
# Site-wide notice while the data is still being built up (owner, 29 Oct). Hidden in embeds.
WIP = """<div id="wip" style="background:#ffd23f;color:#0b0b12;font:600 12px/1.35 'Barlow',system-ui,sans-serif;text-align:center;padding:6px 12px;position:relative;z-index:80"><b style="font-family:'Barlow Condensed',sans-serif;letter-spacing:.08em">UNDER CONSTRUCTION</b> &middot; Live viewer numbers are accurate and update every few seconds. Channel history and rankings are still being filled in.</div><script>if(/[?&]embed=/.test(location.search)){var w=document.getElementById('wip');w&&w.remove()}</script>"""

LEGAL = """<div id="legal" style="max-width:1100px;margin:0 auto;padding:14px 16px 64px;font:12px/1.6 system-ui,sans-serif;color:#8d8ca3;text-align:center">Uses <a href="https://www.youtube.com/t/terms" style="color:inherit">YouTube API Services</a> &middot; <a href="/terms" style="color:inherit">Terms</a> &middot; <a href="/privacy" style="color:inherit">Privacy</a> &middot; <a href="https://policies.google.com/privacy" style="color:inherit">Google Privacy Policy</a> &middot; Not affiliated with YouTube, Twitch or Kick</div><script>if(/[?&]embed=/.test(location.search)){var l=document.getElementById('legal');l&&l.remove()}</script>"""

# India visitors land on /india (device time zone = India, unless they chose Global on the site). Runs before the page
# draws, and works with the CDN cache (the same cached page for everyone; the choice is made in the browser).
REGIONJS = """<script>(function(){try{if(location.pathname!=='/'||location.search||localStorage.getItem('lge_region'))return;
var z=Intl.DateTimeFormat().resolvedOptions().timeZone||'';if(z==='Asia/Kolkata'||z==='Asia/Calcutta')location.replace('/india')}catch(e){}})()</script>"""


def _html(build):
    def b():
        h = build()
        if isinstance(h, bytes):
            h = h.decode()
        if "<head>" in h:
            h = h.replace("<head>", "<head>" + REGIONJS, 1)
        h = __import__("re").sub(r"(<body[^>]*>)", lambda m: m.group(1) + WIP, h, count=1)
        return h.replace("</body>", LEGAL + FASTNAV + "</body>", 1) if "</body>" in h else h
    return b


def _memo(key, ttl, build, mimetype):
    """Stale-while-revalidate: a fresh copy is served as is; an expired one is served immediately while one
    background thread rebuilds it, so nobody waits on a slow build except the very first visitor."""
    if mimetype == "text/html":
        build = _html(build)
    hit = _MEMO.get(key)
    now = time.time()
    if hit and now - hit[0] >= ttl and now - hit[0] < _STALE_MAX:
        lock = _MLOCK.setdefault(key, threading.Lock())
        if lock.acquire(blocking=False):
            def bg():
                try:
                    _memo_build(key, build)
                except Exception as e:
                    print(f"Rebuild {key[:60]}: {str(e)[:120]}")
                finally:
                    lock.release()
            threading.Thread(target=bg, daemon=True).start()
    elif not hit or now - hit[0] >= ttl:
        lock = _MLOCK.setdefault(key, threading.Lock())
        with lock:
            hit = _MEMO.get(key)
            if not (hit and time.time() - hit[0] < ttl):
                hit = _memo_build(key, build)
    _, body, gz = hit
    if gz is not None and "gzip" in request.headers.get("Accept-Encoding", ""):
        r = Response(gz, mimetype=mimetype)
        r.headers["Content-Encoding"] = "gzip"
        r.headers["Vary"] = "Accept-Encoding"
        return r
    return Response(body, mimetype=mimetype)


def _jdump(fn):
    return lambda: json.dumps(fn(), separators=(",", ":"))


def _file(path):
    return lambda: open(path, "rb").read()


def _json(obj):
    return Response(json.dumps(obj, separators=(",", ":")), mimetype="application/json")


@app.route("/")
def index():
    """The worldwide hub, unless `track.py home <event>` made an event the front page (e.g. on a tournament day).
    India lives under /india (/india/s/<section>, /india/c/<game>)."""
    from tracker import events, store
    home = store.kv_get("site_home") or "hub"
    if home != "hub" and events.get(home):
        return _memo("/:" + home, 5, lambda: eventpage.build_html(live=True), "text/html")
    return global_hub()


@app.route("/data")
def data():
    return _memo("/data", 1, _jdump(eventpage.live_data), "application/json")


@app.route("/daystreams/<date>")
def daystreams(date):
    import re as _re
    from tracker import events
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return Response(status=404)
    ev = events.get(None)
    if not ev:
        return _json({})
    r = _memo("/daystreams/" + date, 30, _jdump(lambda: events.day_streams(ev["key"], date)), "application/json")
    r.headers["Cache-Control"] = "public, max-age=30, s-maxage=30"
    return r


@app.route("/series")
def series():
    return _memo("/series", 20, _jdump(eventpage.series_data), "application/json")


_KEY = __import__("re").compile(r"[a-z0-9_-]{1,20}")


def _ev(key):
    from tracker import events
    return events.get(key) if _KEY.fullmatch(key or "") else None


@app.route("/e/<key>")
def ev_bare(key):
    from flask import redirect
    return redirect(f"/e/{key}/", code=301) if _ev(key) else Response("Not found", status=404, mimetype="text/plain")


@app.route("/e/<key>/")
def ev_index(key):
    if not _ev(key):
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/e/{key}/", 5, lambda: eventpage.build_html(key, live=True), "text/html")


@app.route("/e/<key>/data")
def ev_data(key):
    if not _ev(key):
        return Response(status=404)
    return _memo(f"/e/{key}/data", 1, _jdump(lambda: eventpage.live_data(key)), "application/json")


@app.route("/e/<key>/series")
def ev_series(key):
    if not _ev(key):
        return Response(status=404)
    return _memo(f"/e/{key}/series", 20, _jdump(lambda: eventpage.series_data(key)), "application/json")


@app.route("/e/<key>/daystreams/<date>")
def ev_daystreams(key, date):
    import re as _re
    from tracker import events
    if not _ev(key) or not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return Response(status=404)
    r = _memo(f"/e/{key}/daystreams/{date}", 30, _jdump(lambda: events.day_streams(key, date)), "application/json")
    r.headers["Cache-Control"] = "public, max-age=30, s-maxage=30"
    return r


@app.route("/e/<key>/hit", methods=["POST"])
def ev_hit(key):
    return hit()


@app.route("/e/<key>/elogo/<name>")
def ev_elogo(key, name):
    return elogo(name)


@app.route("/india")
def india():
    from tracker import scenepage
    return _memo("/india", 300, scenepage.build_html, "text/html")


def global_hub():
    """Everything live worldwide on YouTube, Kick and Twitch (the front page)."""
    from tracker import scenepage
    return _memo("/global", 300, lambda: scenepage.build_html(region="global"), "text/html")


@app.route("/global")
@app.route("/global/")
@app.route("/global/<path:rest>")
def global_old(rest=""):
    """Old /global links: worldwide is the front page now."""
    from flask import redirect
    return redirect("/" + rest, code=301)


def _cat_page(cat, region):
    from tracker import scene, scenepage
    if not __import__("re").fullmatch(r"[a-z0-9-]{1,40}", cat or ""):
        return Response("Not found", status=404, mimetype="text/plain")
    name = scene.category_name(cat)
    if not name:
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/c/{region}/{cat}", 300, lambda: scenepage.build_html(cat, name, region), "text/html")


@app.route("/c/<cat>")
def category(cat):
    """One game or category worldwide: /c/bgmi, /c/free-fire, /c/news ..."""
    return _cat_page(cat, "global")


@app.route("/india/c/<cat>")
def category_india(cat):
    return _cat_page(cat, "in")


def _scene_args():
    from tracker import scene
    cat = request.args.get("cat", "")
    cat = cat if __import__("re").fullmatch(r"[a-z0-9-]{1,40}", cat) and scene.category_name(cat) else ""
    region = request.args.get("region", "in")
    sec = request.args.get("sec", "")
    return cat, region if region in scene.REGIONS else "in", sec if sec in scene.SECTION_NAMES else ""


def _sec_page(sec, region):
    from tracker import scene, scenepage
    if sec not in scene.SECTION_NAMES:
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/s/{region}/{sec}", 300, lambda: scenepage.build_html(region=region, sec=sec), "text/html")


@app.route("/s/<sec>")
def section(sec):
    """A section worldwide: /s/gaming, /s/esports, /s/irl, /s/just-chatting, /s/news ..."""
    return _sec_page(sec, "global")


@app.route("/india/s/<sec>")
def section_india(sec):
    return _sec_page(sec, "in")


@app.route("/api/scene/live")
def scene_live():
    """The 2-second part: totals, platforms, live categories, tournaments, live streams."""
    from tracker import scene
    cat, region, sec = _scene_args()
    return _memo(f"/api/scene/live:{region}:{sec}:{cat}", 1.5, _jdump(lambda: scene.live_data(cat, region, sec)),
                 "application/json")


@app.route("/api/scene")
@app.route("/india/data")
def india_data():
    from tracker import scene
    per = request.args.get("period", "today")
    per = per if per in scene.PERIODS else "today"
    cat, region, sec = _scene_args()
    return _memo(f"/api/scene:{region}:{sec}:{per}:{cat}", 20, _jdump(lambda: scene.data(per, cat, region, sec)),
                 "application/json")


@app.route("/api/search")
def scene_search():
    """Any streamer ever seen live, plus games/categories: /api/search?q=mortal&region=global"""
    from tracker import scene
    q = (request.args.get("q") or "").strip().lower()[:60]
    region = request.args.get("region", "global")
    region = region if region in scene.REGIONS else "global"
    return _memo(f"/api/search:{region}:{q}", 20, _jdump(lambda: scene.search(q, region)), "application/json")


@app.route("/api/channel")
def scene_channel():
    """One channel's analytics: /api/channel?sid=yt:UC..."""
    from tracker import scene
    sid = (request.args.get("sid") or "")[:120]
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid):
        return Response("{}", status=404, mimetype="application/json")
    def build():
        try:
            return scene.channel(sid)
        except Exception as e:                # never leave the page on "Loading...": send what the database has
            print(f"Channel {sid}: {str(e)[:150]}")
            with __import__("tracker").store._lock:
                r = scene._db().execute("SELECT sid, platform, name, url, logo, title, game FROM sc_channels WHERE sid=?", (sid,)).fetchone()
            return {**dict(r), "now": 0, "periods": {}, "days": [], "recent": [], "ranks": [], "linked": []} if r else {}
    return _memo(f"/api/channel:{sid}", 15, _jdump(build), "application/json")


@app.route("/api/chlive")
def scene_chlive():
    """A live channel's viewers for its page, every 2 seconds: /api/chlive?sid="""
    from tracker import scene
    sid = (request.args.get("sid") or "")[:120]
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid):
        return Response("{}", status=404, mimetype="application/json")
    return _memo(f"/api/chlive:{sid}", 1.5, _jdump(lambda: scene.live_now(sid)), "application/json")


@app.route("/api/cats")
def scene_cats():
    """Games and categories, player-chart style: /api/cats?region=global|in"""
    from tracker import scene
    region = request.args.get("region", "global") if request.args.get("region") in scene.REGIONS else "global"
    return _memo(f"/api/cats:{region}", 60, _jdump(lambda: scene.categories(region)), "application/json")


@app.route("/api/catmonths")
def scene_catmonths():
    """One category by month: /api/catmonths?cat=<slug>&region="""
    from tracker import scene
    region = request.args.get("region", "global") if request.args.get("region") in scene.REGIONS else "global"
    cat = request.args.get("cat", "")
    game = scene.category_name(cat) if __import__("re").fullmatch(r"[a-z0-9-]{1,60}", cat or "") else None
    if not game:
        return Response("{}", status=404, mimetype="application/json")
    return _memo(f"/api/catmonths:{region}:{game}", 600, _jdump(lambda: scene.category_months(game, region)), "application/json")


@app.route("/categories")
@app.route("/india/categories")
def categories_page():
    from tracker import catpage
    region = "in" if request.path.startswith("/india") else "global"
    return _memo(f"/categories:{region}", 300, lambda: catpage.build_html(region), "text/html")


@app.route("/api/rank")
def scene_rank():
    """Leaderboards: /api/rank?region=global&metric=hw|peak|avg|hours&period=day|week|month&date=&cat=&country=&platform=&sec="""
    from tracker import scene
    g = request.args.get
    re_ = __import__("re")
    args = dict(region=g("region", "global"), metric=g("metric", "hw"), period=g("period", "day"),
                date=g("date", "") if re_.fullmatch(r"\d{4}-\d{2}-\d{2}", g("date", "")) else "",
                cat=g("cat", "") if re_.fullmatch(r"[a-z0-9-]{0,40}", g("cat", "")) else "",
                country=(g("country", "") or "")[:2].upper() if re_.fullmatch(r"[A-Za-z]{0,2}", g("country", "")) else "",
                platform=g("platform", "") if g("platform", "") in ("youtube", "kick", "twitch") else "",
                sec=g("sec", "") if g("sec", "") in scene.SECTION_NAMES else "")
    key = "/api/rank:" + ":".join(f"{k}={v}" for k, v in sorted(args.items()))
    return _memo(key, 25, _jdump(lambda: scene.rankings(**args)), "application/json")


def _rank_page(region):
    from tracker import rankpage
    return _memo(f"/rankings:{region}", 300, lambda: rankpage.build_html(region), "text/html")


@app.route("/rankings")
def rankings_page():
    return _rank_page("global")


@app.route("/india/rankings")
def rankings_page_india():
    return _rank_page("in")


@app.route("/api/lookup")
def scene_lookup():
    """Channels on YouTube, Twitch and Kick for a name, for channels this site hasn't seen live: /api/lookup?q="""
    from tracker import scene, ytextra
    q = (request.args.get("q") or "").strip()[:60]
    if len(q) < 3:
        return Response('{"youtube":[],"twitch":[],"kick":[]}', mimetype="application/json")

    def build():
        res = ytextra.lookup(q)
        allsids = [x["sid"] for L in res.values() for x in L]
        with __import__("tracker").store._lock:
            known = {r[0] for r in scene._db().execute(
                f"SELECT sid FROM sc_channels WHERE sid IN ({','.join('?' * len(allsids)) or 'NULL'})", allsids)}
        try:
            ytextra.track_found(res)            # every channel found is followed from now on (daily stats)
        except Exception as e:
            print(f"Track found: {str(e)[:100]}")
        return {k: [{**x, "known": x["sid"] in known} for x in L] for k, L in res.items()}
    return _memo(f"/api/lookup:{q.lower()}", 600, _jdump(build), "application/json")


@app.route("/api/ytsearch")
def scene_ytsearch():
    """YouTube's channel search, for channels this site hasn't seen live: /api/ytsearch?q=garena free fire india"""
    from tracker import scene, ytextra
    q = (request.args.get("q") or "").strip()[:60]
    if len(q) < 3:
        return Response('{"channels":[]}', mimetype="application/json")

    def build():
        try:
            res = ytextra.yt_channel_search(q)
        except Exception as e:
            return {"channels": [], "error": str(e)[:80]}
        with __import__("tracker").store._lock:
            known = {r[0] for r in scene._db().execute(
                f"SELECT sid FROM sc_channels WHERE sid IN ({','.join('?' * len(res)) or 'NULL'})", [x["sid"] for x in res])}
        return {"channels": [{**x, "known": x["sid"] in known} for x in res]}
    return _memo(f"/api/ytsearch:{q.lower()}", 600, _jdump(build), "application/json")


@app.route("/api/moments")
def api_moments():
    """Sudden viewer jumps: /api/moments?region=global|in&period=today|7d|30d&game=&sid="""
    from tracker import moments, scene
    g = request.args.get
    region = g("region", "global") if g("region") in scene.REGIONS else "global"
    period = g("period", "7d") if g("period") in ("today", "7d", "30d") else "7d"
    game, sid = (g("game") or "")[:60], (g("sid") or "")[:120]
    sort = g("sort", "views") if g("sort") in ("views", "jump", "hype", "new") else "views"
    return _memo(f"/api/moments:{region}:{period}:{game}:{sid}:{sort}", 10,
                 _jdump(lambda: moments.recent(region, period, game, sid, sort=sort)), "application/json")


@app.route("/moments")
def moments_page():
    from tracker import momentpage
    return _memo("/moments:global", 300, lambda: momentpage.build_html("global"), "text/html")


@app.route("/india/moments")
def moments_page_india():
    from tracker import momentpage
    return _memo("/moments:in", 300, lambda: momentpage.build_html("in"), "text/html")


@app.route("/api/videos")
def api_videos():
    """A YouTube channel's uploads and past live streams in a range: /api/videos?sid=yt:UC...&range=1w|1m|3m|6m|ytd|1y&kind=all|uploads|live"""
    from tracker import ytextra
    sid = (request.args.get("sid") or "")[:60]
    rng = request.args.get("range", "30d") if request.args.get("range") in ytextra.RANGES else "30d"
    kind = request.args.get("kind", "all") if request.args.get("kind") in ("all", "uploads", "shorts", "live") else "all"
    if not __import__("re").fullmatch(r"(yt:UC[\w-]{22}|(twitch|kick):[a-z0-9_-]{2,40})", sid):
        return Response("{}", status=404, mimetype="application/json")
    key = f"/api/videos:{sid}:{rng}:{kind}"
    r = _memo(key, 8, _jdump(lambda: ytextra.videos_summary(sid, rng, kind)), "application/json")
    body = (_MEMO.get(key) or (0, b""))[1]
    if b'"loading":true' in body or b'"oldest":null' in body:
        r.headers["X-Short-Cache"] = "1"        # still reading the channel: don't let the CDN keep this copy
    return r


@app.route("/api/topch")
def api_topch():
    """Top channels: /api/topch?platform=youtube|twitch|kick&metric=size|views|vday|v7|growth|live&country=IN&category=Gaming&game=BGMI"""
    from tracker import ranks
    g = request.args.get
    plat = g("platform", "youtube") if g("platform") in ("youtube", "twitch", "kick") else "youtube"
    metric = g("metric", "size") if g("metric") in ranks.METRICS else "size"
    country = (g("country") or "")[:2].upper()
    category, game = (g("category") or "")[:40], (g("game") or "")[:60]
    return _memo(f"/api/topch:{plat}:{metric}:{country}:{category}:{game}", 120,
                 _jdump(lambda: ranks.top(plat, metric, country, category, game=game)), "application/json")


SID_RX = r"(yt:UC[\w-]{22}|(twitch|kick):[a-z0-9_-]{2,40})"


@app.route("/api/home")
def api_home():
    """Top channels today (views gained, YouTube), trending videos (last 3 days), biggest channels, for a region and
    one game (?cat=<slug>) or one YouTube category (?topic=People%20%26%20Blogs)"""
    from tracker import scene, ytextra
    region = request.args.get("region", "global") if request.args.get("region") in scene.REGIONS else "global"
    cat = request.args.get("cat", "")
    topic = request.args.get("topic", "") if request.args.get("topic") in ytextra.CATEGORIES else ""
    game = None if topic else scene.category_name(cat) if __import__("re").fullmatch(r"[a-z0-9-]{1,40}", cat or "") else None
    return _memo(f"/api/home:{region}:{game}:{topic}", 120, _jdump(lambda: {
        **ytextra.home_lists(region, game or "", 50, topic), "topics": ytextra.CATEGORIES,
        "channels": ytextra.category_channels(game or "", region, 50, topic) if (game or topic) else []}), "application/json")


@app.route("/badge/<path:sid>.svg")
def badge_svg(sid):
    """Creator badge image: /badge/yt:UC....svg?m=size&s=game (default: the channel's best rank)."""
    from tracker import badge
    re_ = __import__("re")
    if not re_.fullmatch(SID_RX, sid):
        return Response("Not found", status=404, mimetype="text/plain")
    m, s_ = (request.args.get("m") or "")[:10], (request.args.get("s") or "")[:10]
    return _memo(f"/badge:{sid}:{m}:{s_}", 1800, lambda: badge.svg(sid, m, s_), "image/svg+xml")


@app.route("/api/badges")
def api_badges():
    """The ranks a channel can show on a badge: /api/badges?sid="""
    from tracker import badge
    sid = request.args.get("sid") or ""
    if not __import__("re").fullmatch(SID_RX, sid):
        return Response("[]", mimetype="application/json")
    return _memo(f"/api/badges:{sid}", 600, _jdump(lambda: badge.options(sid)), "application/json")


@app.route("/api/compare")
def api_compare():
    """Channels side by side: /api/compare?c=yt:UC...,kick:slug&range=90d"""
    from tracker import ytextra
    re_ = __import__("re")
    sids = [x for x in (request.args.get("c") or "").split(",") if re_.fullmatch(SID_RX, x)][:4]
    rng = request.args.get("range", "90d") if request.args.get("range") in ytextra.RANGES else "90d"
    return _memo(f"/api/compare:{','.join(sids)}:{rng}", 30, _jdump(lambda: ytextra.compare(sids, rng)), "application/json")


@app.route("/compare")
@app.route("/india/compare")
def compare_page():
    from tracker import comparepage
    region = "in" if request.path.startswith("/india") else "global"
    return _memo(f"/compare:{region}", 300, lambda: comparepage.build_html(region), "text/html")


@app.route("/api/past")
def scene_past():
    """A channel's streams in the last 30 days from the platform itself: /api/past?sid=yt:UC..."""
    from tracker import ytextra
    sid = (request.args.get("sid") or "")[:120]
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid):
        return Response("{}", status=404, mimetype="application/json")
    return _memo(f"/api/past:{sid}", 600, _jdump(lambda: ytextra.past_streams(sid)), "application/json")


def _ch_page(sid, region):
    from tracker import chpage, scene
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid or ""):
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import ytextra
    with __import__("tracker").store._lock:
        row = scene._db().execute("SELECT name FROM sc_channels WHERE sid=?", (sid,)).fetchone()
    if not row and ytextra.ensure_any(sid):           # a channel found through YouTube / Twitch / Kick lookup
        with __import__("tracker").store._lock:
            row = scene._db().execute("SELECT name FROM sc_channels WHERE sid=?", (sid,)).fetchone()
    if not row:
        return Response("Not found", status=404, mimetype="text/plain")
    threading.Thread(target=ytextra.ensure_any, args=(sid,), daemon=True).start()   # follow it daily from now on
    return _memo(f"/ch/{region}/{sid}", 120, lambda: chpage.build_html(sid, row[0] or sid, region), "text/html")


@app.route("/ch/<path:sid>")
def channel_page(sid):
    return _ch_page(sid, "global")


@app.route("/india/ch/<path:sid>")
def channel_page_india(sid):
    return _ch_page(sid, "in")


@app.route("/api/geo")
def scene_geo():
    """Live viewers by streamer country, for the globe."""
    from tracker import scene
    return _memo("/api/geo", 4, _jdump(lambda: scene.geo("global")), "application/json")


@app.route("/map")
def world_map():
    from tracker import mappage
    embed = request.args.get("embed") == "1"
    return _memo(f"/map:{embed}", 300, lambda: mappage.build_html(embed), "text/html")


@app.route("/india/map")
def world_map_india():
    from flask import redirect
    return redirect("/map", code=302)


@app.route("/events")
def events_index():
    return _memo("/events", 30, _events_html, "text/html")


def _events_html():
    import html as _h
    from tracker import events, platforms
    rows = []
    for ev in sorted(events.events().values(), key=lambda e: -(e.get("created") or 0)):
        pr = events.preset(ev["key"])
        state = "ended" if pr.get("ended") else "live tracking" if ev.get("active") else "paused"
        plats = ["YouTube"] + [platforms.NAMES[p] for p in platforms.enabled(ev, pr)]
        rows.append(f'<a class="r" href="/e/{_h.escape(ev["key"])}/"><b>{_h.escape(ev["name"])}</b>'
                    f'<span>{_h.escape(pr.get("game") or "")}</span><span>{_h.escape(" + ".join(plats))}</span>'
                    f'<i class="{state.split()[0]}">{state.upper()}</i></a>')
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            "initial-scale=1'><title>Events</title><style>:root{color-scheme:dark}body{margin:0;background:#0b0b12;"
            "color:#eee;font:15px system-ui,sans-serif}main{max-width:760px;margin:0 auto;padding:24px 16px}"
            "h1{font-size:22px}.r{display:grid;grid-template-columns:1fr auto auto auto;gap:12px;align-items:center;"
            "padding:14px;border:1px solid #23233a;margin:8px 0;color:inherit;text-decoration:none;background:#12121c}"
            ".r span{color:#9a9ab0;font-size:13px}.r i{font:normal 11px monospace;padding:2px 6px;border:1px solid}"
            ".live{color:#b6f23a}.ended{color:#9a9ab0}.paused{color:#f5a524}@media(max-width:560px){.r{grid-template-"
            "columns:1fr auto}.r span{display:none}}</style></head><body><main><h1>Tracked events</h1>"
            + ("".join(rows) or "<p>No events yet.</p>")
            + '<a class="r" href="/india"><b>India live streaming rankings</b><span>every game</span><span>YouTube + Kick + Twitch</span>'
            '<i class="live">ALWAYS ON</i></a></main></body></html>')


@app.route("/privacy")
def privacy_page():
    from tracker import legalpage
    return _memo("/privacy", 3600, legalpage.privacy_html, "text/html")


@app.route("/terms")
def terms_page():
    from tracker import legalpage
    return _memo("/terms", 3600, legalpage.terms_html, "text/html")


@app.route("/admin/visitors")
def admin_visitors():
    """Owner-only traffic page: /admin/visitors?key=<ADMIN_KEY from .env>. 404 for anyone else (and if no key is set)."""
    import hmac
    want = os.getenv("ADMIN_KEY", "")
    if len(want) < 16 or not hmac.compare_digest(want, request.args.get("key", "")):
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import visitorspage
    from tracker import events as ev_
    used = ev_._YTQ["n"] if ev_._YTQ["day"] else 0
    from tracker import scene as sc_
    with sc_._lock:
        by = {}
        for x in sc_._LIVE.values():
            z = by.setdefault(x["platform"], [0, 0])
            z[0] += 1
            z[1] += x.get("viewers") or 0
    src = {"errors": dict(sc_._STATE.get("errors") or {}), "last": sc_._STATE.get("last"), "by": by, "twitch_full": dict(sc_._TWFULL)}
    r = Response(visitorspage.build_html({**visitors.stats(), "ytq": (used, ev_.YT_QUOTA), "sources": src}), mimetype="text/html")
    r.headers["X-Robots-Tag"] = "noindex"
    return r


@app.route("/hit", methods=["POST"])
def hit():
    j = request.get_json(silent=True) or {}
    try:
        from urllib.parse import unquote
        _HITS.put_nowait((str(j.get("sid", "")), request.headers.get("CF-IPCountry", ""), str(j.get("ref", "")),
                          request.headers.get("User-Agent", ""), int(j.get("w") or 0),
                          unquote(request.headers.get("cf-ipcity", "")), unquote(request.headers.get("cf-region", ""))))
    except Exception:
        pass                                  # queue full: drop the visit count, never slow the page
    return Response(status=204)


_HITS = queue.Queue(maxsize=20000)


def _hit_writer():   # visitor counts are written here, one at a time, so page requests never wait on the database
    while True:
        a = _HITS.get()
        try:
            visitors.hit(*a)
        except Exception:
            pass


threading.Thread(target=_hit_writer, daemon=True).start()


@app.route("/gameart/<name>")
def gameart(name):
    """Game covers the owner placed in static/gameart (they win over Twitch/Kick art)."""
    import re as _re
    from tracker import scene
    m = _re.fullmatch(r"([a-z0-9-]{1,40})\.(webp|png|jpg)", name)
    path = os.path.join(scene.ART_DIR, name)
    if not m or not os.path.isfile(path):
        return Response(status=404)
    r = _memo(path, 3600, _file(path), {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg"}[m.group(2)])
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.route("/elogo/<name>")
def elogo(name):
    import re as _re
    if not _re.fullmatch(r"[A-Z0-9]+\.webp", name):
        return Response(status=404)
    path = os.path.join(eventpage.ELOGO_DIR, name)
    if not os.path.isfile(path):
        return Response(status=404)
    r = _memo(path, 3600, _file(path), "image/webp")
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


# ---------------- Predict & Win ----------------
_joins = {}   # in-memory only (never written to disk): hashed client address -> recent join attempts


def _throttle(limit=8, window=600) -> bool:
    import hashlib
    import time as _t
    who = hashlib.sha256((request.headers.get("CF-Connecting-IP") or request.remote_addr or "").encode()).hexdigest()[:16]
    now = _t.time()
    hits = [t for t in _joins.get(who, []) if now - t < window]
    if len(_joins) > 5000:
        _joins.clear()
    _joins[who] = hits + [now]
    return len(hits) >= limit


def _err(e):
    return Response(json.dumps({"error": str(e)}), status=getattr(e, "code", 400), mimetype="application/json")


def _tok():
    return request.headers.get("X-PW-Token", "")


@app.route("/predict")
def predict_page():
    return _memo("/predict", 20, predictpage.build_html, "text/html")


@app.route("/predict/og.png")
def predict_og():
    path = os.path.join(os.path.dirname(eventpage.ELOGO_DIR), "predict_og.png")
    if not os.path.isfile(path):
        return Response(status=404)
    return _memo(path, 3600, _file(path), "image/png")


@app.route("/predict/api/board")
def predict_board():
    return _memo("/board", 3, _jdump(predict.board), "application/json")


@app.route("/predict/api/profile/<handle>")
def predict_profile(handle):
    try:
        return _json(predict.profile(handle))
    except predict.GameError as e:
        return _err(e)


@app.route("/predict/api/join", methods=["POST"])
def predict_join():
    if _throttle():
        return _err(predict.GameError("Too many attempts. Try again in a few minutes.", 429))
    j = request.get_json(silent=True) or {}
    try:
        ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or ""
        return _json(predict.join(str(j.get("handle", "")), str(j.get("name", "")), bool(j.get("consent")), ip))
    except predict.GameError as e:
        return _err(e)


@app.route("/predict/api/me", methods=["POST"])
def predict_me():
    try:
        return _json(predict.me(_tok()))
    except predict.GameError as e:
        return _err(e)


@app.route("/predict/api/submit", methods=["POST"])
def predict_submit():
    j = request.get_json(silent=True) or {}
    picks = j.get("picks") if isinstance(j.get("picks"), dict) else {}
    clean = {}
    for k, v in list(picks.items())[:50]:
        clean[str(k)] = [str(x) for x in v][:20] if isinstance(v, list) else str(v)[:60]
    try:
        return _json(predict.submit_all(_tok(), clean))
    except predict.GameError as e:
        return _err(e)


@app.route("/tmark/<name>")
def tmark(name):
    import re as _re
    from tracker import crowdpage
    if not _re.fullmatch(r"[A-Z0-9]+\.webp", name):
        return Response(status=404)
    path = os.path.join(crowdpage.MDIR, name)
    if not os.path.isfile(path):
        return Response(status=404)
    r = _memo(path, 3600, _file(path), "image/webp")
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.route("/pimg/<name>")
def pimg(name):
    import re as _re
    from tracker import crowdpage
    if not _re.fullmatch(r"[A-Za-z0-9]+(_h)?\.webp", name):
        return Response(status=404)
    path = os.path.join(crowdpage.PDIR, name)
    if not os.path.isfile(path):
        return Response(status=404)
    r = _memo(path, 3600, _file(path), "image/webp")
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.route("/tlogo/<name>")
def tlogo(name):
    import re as _re
    if not _re.fullmatch(r"[A-Z0-9]+\.webp", name):
        return Response(status=404)
    path = os.path.join(predictpage.TLOGO_DIR, name)
    if not os.path.isfile(path):
        return Response(status=404)
    r = _memo(path, 3600, _file(path), "image/webp")
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


WARM = ["/", "/india", "/api/cats?region=global", "/api/cats?region=in", "/api/home?region=global", "/api/home?region=in", "/api/scene?region=global&period=today", "/api/scene?region=in&period=today",
        "/api/scene/live?region=global", "/api/scene/live?region=in", "/rankings", "/api/rank?region=global&period=day&metric=hw",
        "/api/rank?region=in&period=day&metric=hw", "/map", "/api/geo", "/moments", "/api/moments?region=global&period=7d"]


def _warm_forever():
    """Keep the busiest pages built, so a visitor never waits for one to be computed."""
    time.sleep(30)
    c = app.test_client()
    while True:
        for u in WARM:
            try:
                c.get(u, headers={"Accept-Encoding": "gzip"})
            except Exception:
                pass
        time.sleep(10)


def run():
    print(f"Event dashboard: http://localhost:{PORT}")
    threading.Thread(target=_warm_forever, daemon=True).start()
    try:
        from waitress import serve   # production server if installed (pip install waitress)
        serve(app, host="127.0.0.1", port=PORT, threads=48, connection_limit=2000, channel_timeout=30, _quiet=True)
    except ImportError:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False, threaded=True)
