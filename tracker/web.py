"""Public, read-only live dashboard for the tracked events (only public stream numbers, nothing about users).

/            the home event (preset "home": True, or `track.py home <key>`)
/e/<key>/    any event's own dashboard (same page; its relative fetches resolve under /e/<key>/)
/events      every event, with links

Runs on its own port (EVENT_WEB_PORT, default 8092, this computer only) so the owner dashboard on 8090 is never
exposed. core/tunnel.py gives it a public https link that opens on any device.
"""
import gzip
import hmac
import json
import logging
import os
import sys
import threading
import time
import queue
from urllib.parse import quote

from flask import Flask, Response, redirect, request

from tracker import eventpage, predict, predictpage, store, visitors

PORT = int(os.getenv("EVENT_WEB_PORT", "8092"))
app = Flask(__name__)
from tracker import auth as _auth          # Sign in with Google (off until its keys are in .env): tracker/auth.py
_auth.setup(app)


def _gate(key, ttl, build, trim, mimetype="application/json"):
    """A locked API: signed-in people asking with auth=1 get the full answer (never cached by Cloudflare); everyone
    else the visitor version (trim), cached under its own key."""
    if _auth.full():
        return _memo(key, ttl, _jdump(build), mimetype)

    def vis():                             # trimmed from the full answer: one build serves both (single-flight in _memo)
        _memo(key, ttl, _jdump(build), mimetype)
        hit = _MEMO.get(key)
        if hit:
            try:
                return trim(json.loads(gzip.decompress(hit[1]) if hit[1][:2] == b"\x1f\x8b" else hit[1]))
            except Exception:
                pass
        return trim(build())
    return _memo(key + ":visitor", ttl, _jdump(vis), mimetype)


class _GlobalPaths:
    """Worldwide pages live under /global, like India's under /india: /global/categories is served by the
    /categories handler. Old worldwide links (/categories, /c/bgmi, /ch/yt:...) redirect to their /global address."""
    OLD = ("/categories", "/rankings", "/moments", "/compare")    # /map stays: it shows the whole world
    OLD_PRE = ("/c/", "/ch/", "/s/", "/kit/", "/t/")

    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start):
        p = environ.get("PATH_INFO", "")
        if p == "/global/":
            environ["PATH_INFO"] = "/global"
        elif p.startswith("/global/"):
            environ["PATH_INFO"] = p[len("/global"):]
        elif environ.get("REQUEST_METHOD") in ("GET", "HEAD") and (p in self.OLD or p.startswith(self.OLD_PRE)):
            qs = environ.get("QUERY_STRING", "")
            start("301 Moved Permanently", [("Location", "/global" + p + ("?" + qs if qs else "")),
                                            ("Cache-Control", "public, max-age=3600"), ("Content-Length", "0")])
            return [b""]
        return self.wsgi(environ, start)


app.wsgi_app = _GlobalPaths(app.wsgi_app)


CACHE = {"/global": 5, "/api/cats": 60, "/api/catmonths": 600, "/categories": 300, "/india/categories": 300, "/privacy": 3600, "/terms": 3600, "/api/chlive": 2, "/badge": 1800, "/api/badges": 600, "/api/home": 120, "/api/compare": 30, "/compare": 300, "/india/compare": 300, "/api/topch": 120, "/api/videos": 300, "/api/lookup": 600, "/api/moments": 20, "/moments": 300, "/india/moments": 300, "/api/ytsearch": 600, "/api/past": 300, "/api/rank": 30, "/rankings": 300, "/india/rankings": 300, "/api/channel": 20, "/map": 300, "/api/geo": 5, "/api/search": 30, "/india": 30, "/india/data": 20, "/api/scene": 20, "/api/scene/live": 2, "/": 5, "/data": 2, "/series": 60, "/predict": 30, "/predict/api/board": 5, "/predict/og.png": 3600}   # seconds Cloudflare (or any CDN) may reuse a response



@app.before_request
def _predict_closed():
    # Predict & Win is off the public site unless PREDICT_OPEN=1. Players' data stays in the database and the
    # 10-minute exports (exports/predict, exports/private); only the pages and API are hidden.
    if request.path == "/predict/bmsd" and request.method == "GET":     # BMSD 2026 results, frozen when BMIC began
        from tracker import crowdpage
        snap = __import__("tracker").store.kv_get("pw_bmsd_crowd")
        if not snap:
            return Response("Not found", status=404, mimetype="text/plain")
        r = _memo("/predict-bmsd", 3600, lambda: crowdpage.build_html(snap), "text/html")
        r.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"
        return r
    if request.path.startswith("/predict/pmgc"):         # PMGC 2026 Gauntlet game: its own switch (tracker/pmgc.py)
        return None
    if request.path.startswith("/predict") and not eventpage.predict_open():
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
    if request.method != "GET" or resp.status_code >= 400 or request.args.get("auth") == "1":
        secs = None                       # POSTs, signed-in (auth=1), personal and error responses are never cached
    if request.path.startswith(("/elogo/", "/tlogo/", "/pimg/", "/tmark/", "/gameart/", "/pmgc/logo/", "/brand/")):
        return resp
    swr = min(600, max(30, secs * 10)) if secs else 0      # an expired copy is shown at once while a fresh one loads
    resp.headers["Cache-Control"] = f"public, max-age={secs}, s-maxage={secs}, stale-while-revalidate={swr}" if secs else "no-store"
    if secs:   # Cloudflare's Browser Cache TTL can override max-age; this one it passes through for its own cache
        resp.headers["CDN-Cache-Control"] = f"max-age={secs}, stale-while-revalidate={swr}"
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


_STALE_MAX = 600      # live responses (ttl under 30 s): an expired copy is served, and rebuilt in the background, this long
_STALE_PAGE = 1800    # page data (ttl 10-29 s, e.g. /api/scene, a 20-40 s build): served this old while it rebuilds
_STALE_LONG = 6 * 3600   # everything else: a page or API answer up to 6 hours old is shown at once while it rebuilds
_MEMO_TTL = {}
_MSIZE = [0]
_MEMO_BYTES = int(os.getenv("MEMO_MB", "500")) * 1024 * 1024
_MEMO_FILE = os.path.join(os.path.dirname(os.path.abspath(store.DB_PATH)), "memo_cache.pkl")


_CODE = {}


def _code() -> str:
    """The running code's git commit (cached)."""
    if "sha" not in _CODE:
        import subprocess
        try:
            _CODE["sha"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5,
                                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).stdout.strip()
        except Exception:
            _CODE["sha"] = ""
    return _CODE["sha"]


def _memo_save():
    """Every 10 minutes: the built pages and API answers (not the live ones) to disk, so after a restart or deploy
    visitors get them instantly (and they rebuild in the background) instead of every page being cold."""
    import pickle
    n = 0
    while True:
        time.sleep(60)
        n += 1
        try:                                  # every minute: page data (/api/scene ...), so a restart never shows blanks
            now, out = time.time(), []
            for k, (ts, body, gz) in list(_MEMO.items()):
                if 10 <= _MEMO_TTL.get(k, 0) < 30 and now - ts < _STALE_PAGE:
                    out.append((k, ts, body, gz, _MEMO_TTL[k]))
            with open(_MEMO_FILE + ".live.tmp", "wb") as f:
                pickle.dump({"code": _code(), "rows": out}, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(_MEMO_FILE + ".live.tmp", _MEMO_FILE + ".live")
        except Exception as e:
            print(f"Memo save (live): {str(e)[:120]}")
        if n % 10:
            continue
        try:
            now, out, size = time.time(), [], 0
            for k, (ts, body, gz) in sorted(list(_MEMO.items()), key=lambda kv: -kv[1][0]):
                if _MEMO_TTL.get(k, 0) < 30 or now - ts > _STALE_LONG:
                    continue
                size += len(body) + len(gz or b"")
                if size > 200 * 1024 * 1024:
                    break
                out.append((k, ts, body, gz, _MEMO_TTL.get(k, 60)))
            tmp = _MEMO_FILE + ".tmp"
            with open(tmp, "wb") as f:
                pickle.dump({"code": _code(), "rows": out}, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, _MEMO_FILE)
        except Exception as e:
            print(f"Memo save: {str(e)[:120]}")


def _memo_load():
    import pickle
    for path, age in ((_MEMO_FILE + ".live", _STALE_PAGE), (_MEMO_FILE, _STALE_LONG)):
        try:
            with open(path, "rb") as f:
                saved = pickle.load(f)
            rows = saved.get("rows", []) if isinstance(saved, dict) else saved
            same = isinstance(saved, dict) and saved.get("code") == _code()
            now, n = time.time(), 0
            for k, ts, body, gz, ttl in rows:
                if not same and not k.startswith("/api/"):
                    continue                  # a page built by older code: never show the old page after a deploy
                if now - ts < age and k not in _MEMO:   # (23 Nov: removed buttons kept showing on CarryisLive's page)
                    _MEMO[k], _MEMO_TTL[k] = (ts, body, gz), ttl
                    n += 1
            print(f"Memo: {n} of {len(rows)} saved responses loaded from {os.path.basename(path)}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Memo load: {str(e)[:120]}")


def _memo_build(key, build):
    t0 = time.time()
    body = build()
    took = time.time() - t0
    if took > 2:
        print(f"Slow page build: {took:.1f}s {key[:120]}")
    if isinstance(body, str):
        body = body.encode()
    hit = (time.time(), body, gzip.compress(body, 5) if len(body) > 1024 else None)
    if len(_MEMO) > 6000:                     # search keys are open-ended: drop stale entries
        for k in [k for k, v in list(_MEMO.items()) if time.time() - v[0] > (_STALE_MAX if _MEMO_TTL.get(k, 0) < 30 else _STALE_LONG)
                  or k.startswith("/api/search:") and time.time() - v[0] > 120]:
            _MEMO.pop(k, None)
            _MLOCK.pop(k, None)
    _MEMO[key] = hit
    _MSIZE[0] += len(body) + len(hit[2] or b"")
    if _MSIZE[0] > _MEMO_BYTES:               # memory: 9 GB RSS on 19 Nov left no page cache for the database
        tot, keep = 0, {}
        for k, v in sorted(list(_MEMO.items()), key=lambda kv: -kv[1][0]):
            tot += len(v[1]) + len(v[2] or b"")
            if tot > _MEMO_BYTES * 0.7 and _MEMO_TTL.get(k, 0) >= 10:
                _MEMO.pop(k, None)
                _MLOCK.pop(k, None)
        _MSIZE[0] = sum(len(v[1]) + len(v[2] or b"") for v in list(_MEMO.values()))
    return hit


# Instant page changes: Chrome/Edge prerender a link when you hover or press it (speculation rules); other browsers
# (Safari) fetch the page early on touch/hover, so the click finds it ready.
FASTNAV = """<script type="speculationrules">{"prerender":[{"where":{"and":[{"href_matches":"/*"},{"not":{"href_matches":"/api/*"}},{"not":{"href_matches":"/e/*"}}]},"eagerness":"moderate"}]}</script>
<script>(function(){var done={};function pf(e){var a=e.target.closest&&e.target.closest('a[href^="/"]');if(!a||a.target||done[a.href]||HTMLScriptElement.supports&&HTMLScriptElement.supports('speculationrules'))return;done[a.href]=1;var l=document.createElement('link');l.rel='prefetch';l.href=a.href;document.head.appendChild(l)}
document.addEventListener('touchstart',pf,{passive:true});document.addEventListener('mouseover',pf,{passive:true})})()</script>
<script>(function(){var p=location.pathname.replace(/\\/+$/,'')||'/',bar=document.querySelector('.top .in')||document.querySelector('.bar .in');
if(p==='/'||p==='/india'||/[?&]embed=/.test(location.search)||!bar)return;
var home=p.indexOf('/predict')===0?'/e/bmic/':(p.indexOf('/india')===0||p.indexOf('/e/')===0)?'/india':'/',st=document.createElement('style');
st.textContent='.bk{display:inline-flex;align-items:center;gap:6px;flex:none;height:32px;padding:0 10px 0 6px;margin-right:2px;border:1px solid #262636;background:#13131c;color:#eeeef5;text-decoration:none;font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.06em}.bk:hover{border-color:#b6f23a;color:#b6f23a}.bk svg{flex:none}@media(max-width:640px){.bk{padding:0 7px}.bk span{display:none}}@media(max-width:420px){.top .beta{display:none}.top .in{gap:8px!important}.top .rg a{padding-left:7px!important;padding-right:7px!important}.top .upd{display:none!important}}';
document.head.appendChild(st);var a=document.createElement('a');a.className='bk';a.href=home;a.setAttribute('aria-label','Back');
a.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg><span>BACK</span>';
a.onclick=function(e){var r=document.referrer;if(r&&r.indexOf(location.origin+'/')===0&&history.length>1){e.preventDefault();history.back()}};
bar.insertBefore(a,bar.firstChild)})()</script>
<script>(function(){if(/[?&]embed=/.test(location.search)||location.pathname.indexOf('/e/')===0)return;var k;try{k=sessionStorage.getItem('lge_s');if(!k){k=Math.random().toString(36).slice(2)+Date.now().toString(36);sessionStorage.setItem('lge_s',k)}}catch(e){k=Math.random().toString(36).slice(2)}
var r=document.referrer&&document.referrer.indexOf(location.origin)!==0?document.referrer:'';
function ping(){if(document.hidden)return;try{fetch('/hit',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:k,ref:r,w:innerWidth,p:location.pathname})}).catch(function(){})}catch(e){}}
ping();setInterval(ping,30000);document.addEventListener('visibilitychange',ping);
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('.rg a');if(!a)return;var h=a.getAttribute('href')||'';try{localStorage.setItem('lge_region',h.indexOf('/india')===0?'in':'global')}catch(x){}},true)})()</script>"""
# Site-wide notice while the data is still being built up (owner, 29 Oct). Hidden in embeds.
WIP = """<div id="wip" style="background:#ffd23f;color:#0b0b12;font:600 12px/1.35 'Barlow',system-ui,sans-serif;text-align:center;padding:6px 12px;position:relative;z-index:80"><b style="font-family:'Barlow Condensed',sans-serif;letter-spacing:.08em">UNDER CONSTRUCTION</b> &middot; Live viewer numbers are accurate and update every few seconds. Channel history and rankings are still being filled in.</div><script>if(/[?&]embed=/.test(location.search)){var w=document.getElementById('wip');w&&w.remove()}</script>"""

LEGAL = """<div id="legal" style="max-width:1100px;margin:0 auto;padding:14px 16px 64px;font:12px/1.6 system-ui,sans-serif;color:#8d8ca3;text-align:center">Uses <a href="https://www.youtube.com/t/terms" style="color:inherit">YouTube API Services</a> &middot; <a href="/terms" style="color:inherit">Terms</a> &middot; <a href="/privacy" style="color:inherit">Privacy</a> &middot; <a href="https://policies.google.com/privacy" style="color:inherit">Google Privacy Policy</a> &middot; Not affiliated with YouTube, Twitch or Kick</div><script>if(/[?&]embed=/.test(location.search)){var l=document.getElementById('legal');l&&l.remove()}</script>"""

# India visitors land on /india (device time zone = India, unless they chose Global on the site). Runs before the page
# draws, and works with the CDN cache (the same cached page for everyone; the choice is made in the browser).
REGIONJS = """<script>(function(){try{if(location.pathname==='/'&&!location.search&&history.replaceState)history.replaceState(null,'','/global'+location.hash)}catch(e){}})()</script><script>(function(){try{if(location.pathname!=='/global'||location.search||localStorage.getItem('lge_region')||(document.referrer||'').indexOf(location.host)>-1)return;
var z=Intl.DateTimeFormat().resolvedOptions().timeZone||'';if(z==='Asia/Kolkata'||z==='Asia/Calcutta')location.replace('/india')}catch(e){}})()</script>"""


def _html(build):
    def b():
        h = build()
        if isinstance(h, bytes):
            h = h.decode()
        if "<head>" in h:
            h = h.replace("<head>", "<head>" + REGIONJS, 1)
        if "</head>" in h and 'id="lgepolish"' not in h:
            from tracker import polish
            h = h.replace("</head>", polish.head() + _auth.page_js() + "</head>", 1)
        h = __import__("re").sub(r"(<body[^>]*>)", lambda m: m.group(1) + WIP, h, count=1)
        from tracker import polish as _p
        legal = LEGAL.replace(" &middot; Not affiliated", _p.THEME_LINK + " &middot; Not affiliated", 1)
        return h.replace("</body>", legal + FASTNAV + "</body>", 1) if "</body>" in h else h
    return b


from concurrent.futures import ThreadPoolExecutor as _TPE
_LIVE_POOL = _TPE(max_workers=6, thread_name_prefix="memo-live")
_FAST_POOL = _TPE(max_workers=4, thread_name_prefix="memo-fast")      # 2-second answers never queue behind page builds
_SLOW_POOL = _TPE(max_workers=4, thread_name_prefix="memo-slow")      # pages visitors asked for
_WARM_POOL = _TPE(max_workers=3, thread_name_prefix="memo-warm")      # the background warm-up


def _is_warm() -> bool:
    try:
        return request.headers.get("X-Warm") == "1"
    except Exception:
        return False


def _memo(key, ttl, build, mimetype):
    """Stale-while-revalidate: a fresh copy is served as is; an expired one is served immediately while one
    background thread rebuilds it, so nobody waits on a slow build except the very first visitor."""
    if mimetype == "text/html":
        build = _html(build)
    hit = _MEMO.get(key)
    now = time.time()
    _MEMO_TTL[key] = ttl
    stale_max = _STALE_MAX if ttl < 10 else _STALE_PAGE if ttl < 30 else _STALE_LONG
    if hit and now - hit[0] >= ttl and now - hit[0] < stale_max:
        lock = _MLOCK.setdefault(key, threading.Lock())
        warm = _is_warm()
        if warm and _WARM_POOL._work_queue.qsize() > 20:
            pass                              # the warm-up is behind: don't pile up more (visitors' rebuilds go first)
        elif lock.acquire(blocking=False):
            def bg():
                try:
                    _memo_build(key, build)
                except Exception as e:
                    print(f"Rebuild {key[:60]}: {str(e)[:120]}")
                finally:
                    lock.release()
            # Bounded pools: after a restart every cached page is stale at once, and one thread per page (hundreds)
            # made every build take minutes (420 s), freezing live pages like the CEGC tracker. Live answers have
            # their own pool so they never queue behind channel pages.
            # Pages a visitor asked for and the background warm-up have separate pools, so a long warm-up queue
            # (hundreds of channel pages) never leaves a visitor's page hours old.
            (_FAST_POOL if ttl < 10 else _LIVE_POOL if ttl < 30 else _WARM_POOL if warm else _SLOW_POOL).submit(bg)
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
    return global_hub()          # same page as /global; the address bar is switched to /global in the browser


@app.route("/global")
def global_home():
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
    return _json(eventpage.live_data(key))     # cheap: full stats cached and rebuilt in the background, live numbers from memory


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


def _cat_page(cat, region):
    from tracker import scene, scenepage
    if not __import__("re").fullmatch(r"[a-z0-9-]{1,40}", cat or ""):
        return Response("Not found", status=404, mimetype="text/plain")
    name = scene.category_name(cat)
    if not name or not scene.shown(name):
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/c/{region}/{cat}", 300, lambda: scenepage.build_html(cat, name, region), "text/html")


@app.route("/c/<cat>")
def category(cat):
    """One game or category worldwide: /c/bgmi, /c/free-fire, /c/news ..."""
    return _cat_page(cat, "global")


@app.route("/india/c/<cat>")
def category_india(cat):
    return _cat_page(cat, "in")


def _tour_page(sl: str, region: str):
    from tracker import scene, tourpage
    if not __import__("re").fullmatch(r"[a-z0-9-]{1,80}", sl or ""):
        return Response("Not found", status=404, mimetype="text/plain")
    name = scene.tour_name(sl)
    if not name or not scene.named_tour(name):
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/t/{region}/{sl}", 15, lambda: tourpage.build_html(name, region), "text/html")


@app.route("/t/<sl>")
def tour_global(sl):
    """One esports tournament worldwide, every channel streaming it together: /global/t/ffws-global-finals-2026"""
    return _tour_page(sl, "global")


@app.route("/india/t/<sl>")
def tour_india(sl):
    return _tour_page(sl, "in")


@app.route("/api/tour")
def api_tour():
    """/api/tour?region=global|in&t=<slug>: one tournament (see scene.tour_data)."""
    from tracker import scene
    sl, region = request.args.get("t", ""), request.args.get("region", "global")
    region = region if region in ("global", "in") else "global"
    name = scene.tour_name(sl) if __import__("re").fullmatch(r"[a-z0-9-]{1,80}", sl or "") else None
    if not name:
        return Response("{}", status=404, mimetype="application/json")
    return _memo(f"/api/tour:{region}:{sl}", 10, _jdump(lambda: scene.tour_data(name, region)), "application/json")


class _Tee:
    """Keeps the last warning lines the tracker prints (slow locks, slow scans, failures) for the health page."""
    PAT = ("Slow write lock", "Scan took", "WAL checkpoint", "failed", "Traceback", "Error", "repair", "Slow page build: ",
           "Ranks")

    def __init__(self, out):
        self.out, self.lines = out, __import__("collections").deque(maxlen=120)

    def write(self, s):
        if any(p in s for p in self.PAT) and not s.startswith("Slow page build: 2") and not s.startswith("Slow page build: 3"):
            self.lines.append((time.time(), s.strip()[:220]))
        return self.out.write(s)

    def flush(self):
        return self.out.flush()

    def __getattr__(self, k):
        return getattr(self.out, k)


if not isinstance(sys.stdout, _Tee):
    sys.stdout = _Tee(sys.stdout)


def _health() -> dict:
    """Where the tracker is right now: scans, the write lock, the database log, disk, memory, what each busy thread is
    doing, and the latest warnings. No secrets and no data."""
    import shutil, threading as th
    from tracker import scene as sc_
    now = time.time()
    db = store.DB_PATH
    wal = os.path.getsize(db + "-wal") if os.path.exists(db + "-wal") else 0
    du = shutil.disk_usage(os.path.dirname(db) or ".")
    mem = {}
    try:
        for ln in open("/proc/meminfo"):
            k, v = ln.split(":")
            if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                mem[k] = int(v.split()[0]) // 1024
    except Exception:
        pass
    cyc = dict(sc_.CYCLE)
    frames, names = sys._current_frames(), {t.ident: t.name for t in th.enumerate()}
    busy = []
    for tid, f in frames.items():
        stack, g = [], f
        while g:
            fn = g.f_code.co_filename
            if "/tracker/" in fn:
                stack.append(f"{os.path.basename(fn)}:{g.f_lineno} {g.f_code.co_name}")
            g = g.f_back
        if stack and not any(w in stack[0] for w in ("sleep", "_health")):
            busy.append({"thread": names.get(tid, str(tid)), "at": stack[:4]})
    h = dict(store.HOLDER)
    return {
        "code": api_version().get_json().get("code"), "up_min": round((now - _STARTED) / 60),
        "scan": {"last_saved_min_ago": round((now - (sc_._SCANMEM.get("saved") or sc_._SCANMEM.get("ts") or 0)) / 60, 1),
                 "running_for_s": round(now - cyc["started"]) if cyc.get("running") else 0,
                 "last_took_s": cyc.get("took"), "live": cyc.get("live"), "fetch_s": cyc.get("fetch_s"),
                 "store_s": cyc.get("store_s"), "overloaded": sc_.overloaded()},
        "write_lock": {"held_s": round(now - h["at"], 1), "by": h.get("where"), "thread": h.get("thread")} if h.get("at") else "free",
        "wal_mb": round(wal / 1e6), "db_mb": round(os.path.getsize(db) / 1e6) if os.path.exists(db) else 0,
        "disk_free_gb": round(du.free / 1e9, 1), "disk_used_pct": round(100 * du.used / du.total),
        "memory_mb": mem, "load": os.getloadavg(),
        "youtube_2s": sc_._YTF.get("last"),
        "rankings": {"updated_min_ago": round((now - (__import__("tracker.ranks", fromlist=["x"])._R.get("at") or 0)) / 60),
                     **{k: (round((now - v) / 60) if k in ("started", "done", "failed") and v else v)
                        for k, v in __import__("tracker.ranks", fromlist=["x"]).STATUS.items()}},
        "chat_lang": _chat_lang(),
        "busy_threads": busy[:40],
        "recent": [f"{time.strftime('%H:%M:%S', time.gmtime(t))}Z {s}" for t, s in list(sys.stdout.lines)[-40:]]
                  if isinstance(sys.stdout, _Tee) else [],
    }


@app.route("/api/health")
def api_health():
    return _json(_health())


@app.route("/admin/health")
def admin_health():
    """Owner page: the same as /api/health, refreshed every 5 seconds, with problems in red."""
    r = Response(_HEALTH_PAGE, mimetype="text/html")
    return _admin_bar(r, "health") if _owner() else r


def _admin_bar(r, tab):
    """The portal's top bar on the older owner pages (Traffic, Health, Predict & Win), so they are one place."""
    from tracker import adminpage
    key = "" if _auth.is_admin() else request.values.get("key", "")
    bar = adminpage.page(tab, "", "", _auth.user() if _auth.ENABLED else None, key)
    top = bar[bar.index('<div class="top">'):bar.index("<main>")]
    css = ("<style>.lgeadm{all:initial;display:block;font:14px/1.5 Figtree,system-ui,sans-serif;margin:0 0 16px}"
           ".lgeadm .top{border-bottom:1px solid #1d1d28;background:#0a0a10}.lgeadm .in{max-width:1160px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}"
           ".lgeadm .brand{color:#b6f23a;font-weight:800;letter-spacing:.05em;text-decoration:none;text-transform:uppercase}.lgeadm .tag{font-size:11px;font-weight:700;color:#0b0b12;background:#b6f23a;padding:2px 6px;border-radius:4px}"
           ".lgeadm .tabs{display:flex;gap:4px;overflow-x:auto}.lgeadm .tabs a{padding:7px 12px;border-radius:8px;text-decoration:none;color:#8d8ca3;font-weight:600;white-space:nowrap}"
           ".lgeadm .tabs a.on{color:#0b0b12;background:#b6f23a}.lgeadm .who{margin-left:auto;color:#8d8ca3;font-size:13px;display:flex;gap:10px;align-items:center}.lgeadm .who img{width:26px;height:26px;border-radius:50%}"
           ".lgeadm .btn{background:#15151e;border:1px solid #2a2a38;color:#fff;border-radius:9px;padding:6px 12px;text-decoration:none;font-weight:600;font-size:13px}"
           "@media(max-width:600px){.lgeadm .hide{display:none}}</style>")
    h = r.get_data(as_text=True)
    i = h.find("<body")
    if i >= 0:
        j = h.find(">", i) + 1
    else:                                       # a page with no <body> tag (Health): after its styles
        j = h.find("</style>") + 8 if "</style>" in h else 0
    r.set_data(h[:j] + css + f'<div class="lgeadm">{top}</div>' + h[j:])
    return r


_HEALTH_PAGE = r"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Tracker health</title><style>body{background:#0e0e14;color:#e8e8f0;font:14px/1.45 system-ui;margin:16px;max-width:1000px}
h1{font-size:20px}.k{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}.c{background:#16161f;border:1px solid #2a2a3a;
border-radius:10px;padding:10px}.c b{display:block;font-size:22px}.bad{border-color:#ff5d5d}.bad b{color:#ff5d5d}.ok b{color:#b6f23a}
pre{background:#16161f;border:1px solid #2a2a3a;border-radius:10px;padding:10px;white-space:pre-wrap;font-size:12px}</style>
<h1>Tracker health <span id=t style="font-size:13px;color:#8d8ca3"></span></h1><div class=k id=k></div><h3>Busy threads</h3><pre id=b></pre>
<h3>Recent warnings (UTC)</h3><pre id=r></pre><script>
const card=(n,v,bad)=>`<div class="c ${bad?'bad':'ok'}">${n}<b>${v}</b></div>`;
async function go(){try{const d=await fetch('/api/health',{cache:'no-store'}).then(r=>r.json());const s=d.scan,w=d.write_lock;
document.getElementById('k').innerHTML=card('Last scan saved',s.last_saved_min_ago+' min ago',s.last_saved_min_ago>8)
+card('Scan running for',s.running_for_s+' s',s.running_for_s>480)+card('Last scan took',(s.last_took_s??'-')+' s',s.last_took_s>400)
+card('Write lock',w==='free'?'free':w.held_s+' s · '+w.by,w!=='free'&&w.held_s>5)+card('Database log (WAL)',d.wal_mb+' MB',d.wal_mb>1500)
+card('Disk free',d.disk_free_gb+' GB',d.disk_free_gb<5)+card('Memory free',(d.memory_mb.MemAvailable||0)+' MB',(d.memory_mb.MemAvailable||0)<2000)
+card('Load (1 min)',d.load[0].toFixed(1),d.load[0]>6)+card('YouTube 2s round',d.youtube_2s?d.youtube_2s.took+' s · '+d.youtube_2s.errs+' errors':'-',d.youtube_2s&&d.youtube_2s.errs>5)
+card('Code',d.code+' · up '+d.up_min+' min',false);
document.getElementById('b').textContent=d.busy_threads.map(x=>x.thread+'\n   '+x.at.join('\n   ')).join('\n');
document.getElementById('r').textContent=d.recent.slice().reverse().join('\n');document.getElementById('t').textContent='updated '+new Date().toLocaleTimeString()}
catch(e){document.getElementById('t').textContent='no answer: '+e}}go();setInterval(go,5000)</script>"""


@app.route("/api/version")
def api_version():
    """Which code is running and which one-time repairs have finished (public: no secrets, no data)."""
    sha = _code()
    rep = {k: bool(store.kv_get(k)) for k in ("g6_peaks_v2", "g6_peaks_v1", "g6_unnews_v1", "g6_unfile_v1", "g6_cards_v1")}
    return _json({"code": sha, "started": _STARTED, "repairs": rep})


_STARTED = time.time()


@app.route("/api/sweep")
def api_sweep():
    """Launch sweep status: which games are swept and how many streams each source found (no secrets)."""
    from tracker import scene
    return _json({**scene.sweep_status(), "yt_fast": scene._YTF.get("last"),
                  "yt_fast_set": {"global": scene.YT_FAST_N, "india": scene.YT_FAST_IN, "mid": scene.YT_MID_N}})


@app.route("/api/tours")
def api_tours():
    """/api/tours?region=global|in: tournaments on now (this site's trackers, Liquipedia's, all channels together)."""
    from tracker import scene
    region = request.args.get("region", "global")
    region = region if region in ("global", "in") else "global"
    return _memo(f"/api/tours:{region}", 15, _jdump(lambda: scene.tours_overview(region)), "application/json")


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


# ---------- media kits, shortlist, data API (tracker/kit.py) ----------

def _sid_ok(sid):
    return bool(__import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid or ""))


@app.route("/kit/<path:sid>")
@app.route("/india/kit/<path:sid>")
def kit_page(sid):
    from tracker import kit, scene
    if not _sid_ok(sid):
        return Response("Not found", status=404, mimetype="text/plain")
    with __import__("tracker").store.reading():
        row = scene._db().execute("SELECT name FROM sc_channels WHERE sid=?", (sid,)).fetchone()
    if not row:
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/kit/{sid}", 300, lambda: kit.kit_html(sid, row[0] or sid), "text/html")


@app.route("/shortlist")
def shortlist_page():
    from tracker import kit
    return _memo("/shortlist", 3600, kit.shortlist_html, "text/html")


@app.route("/api/docs")
def api_docs():
    from tracker import kit
    return _memo("/api/docs", 3600, kit.docs_html, "text/html")


@app.route("/api/kit")
def api_kit():
    from tracker import kit
    sid = request.args.get("sid", "")
    if not _sid_ok(sid):
        return Response('{"error":"bad sid"}', status=400, mimetype="application/json")
    return _memo(f"/api/kit:{sid}", 600, _jdump(lambda: kit.data(sid)), "application/json")


def _v1(build):
    """Data API: key check, daily limit, JSON."""
    from tracker import kit
    key = request.headers.get("X-API-Key") or request.args.get("key") or ""
    ok, used, limit, _ = kit.key_check(key)
    if not ok:
        msg = "daily limit reached" if limit else "missing or invalid API key (see /api/docs)"
        return Response(json.dumps({"error": msg}), status=429 if limit else 401, mimetype="application/json")
    try:
        body = json.dumps(build(), separators=(",", ":"))
    except ValueError as e:
        return Response(json.dumps({"error": str(e)}), status=400, mimetype="application/json")
    r = Response(body, mimetype="application/json")
    r.headers["X-Calls-Today"], r.headers["X-Calls-Limit"] = str(used), str(limit)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.route("/api/v1/creator")
def v1_creator():
    from tracker import kit
    sid = request.args.get("sid", "")

    def build():
        if not _sid_ok(sid):
            raise ValueError("bad sid")
        return kit.data(sid) or {"error": "not found"}
    return _v1(build)


@app.route("/api/v1/rankings")
def v1_rankings():
    from tracker import ranks
    g = request.args.get

    def build():
        plat = g("platform", "youtube")
        if plat not in ("youtube", "twitch", "kick") or g("metric", "vday") not in ranks.METRICS + ranks.PMETRICS:
            raise ValueError("bad platform or metric")
        return ranks.top(plat, g("metric", "vday"), (g("country", "") or "")[:2].upper(), g("category", "")[:60],
                         limit=max(1, min(1000, int(g("limit") or 100))), game=g("game", "")[:60])
    return _v1(build)


@app.route("/api/v1/streamers")
def v1_streamers():
    from tracker import scene
    g = request.args.get
    re_ = __import__("re")

    def build():
        return scene.rankings(region=g("region", "global"), metric=g("metric", "hw"), period=g("period", "day"),
                              date=g("date", "") if re_.fullmatch(r"\d{4}-\d{2}-\d{2}", g("date", "")) else "",
                              cat=g("cat", "") if re_.fullmatch(r"[a-z0-9-]{0,40}", g("cat", "")) else "",
                              country=(g("country", "") or "")[:2].upper(),
                              platform=g("platform", "") if g("platform", "") in ("youtube", "kick", "twitch") else "")
    return _v1(build)


@app.route("/api/v1/live")
def v1_live():
    from tracker import scene
    region = request.args.get("region", "global")
    region = region if region in scene.REGIONS else "global"
    return _v1(lambda: scene.data("today", "", region, ""))


@app.route("/api/v1/search")
def v1_search():
    from tracker import scene
    q = (request.args.get("q") or "").strip().lower()[:60]
    return _v1(lambda: scene.search(q, "global"))


@app.route("/api/deep")
def api_deep():
    """A channel's metrics and where it stands among peers, history by month since January, best-performing
    recent videos and top comments: /api/deep?sid=yt:UC..."""
    import re as _re
    from tracker import deep
    sid = request.args.get("sid", "")
    if not _re.fullmatch(r"yt:UC[\w-]{22}", sid):
        return Response('{"error":"bad sid"}', status=400, mimetype="application/json")

    def build():
        perf = deep.performance(sid)
        with __import__("tracker").store.reading():
            vids = {r[0]: dict(r) for r in deep._db().execute(
                "SELECT vid, title, ts, views, likes, comments FROM yt_videos WHERE sid=? AND ts>?", (sid, time.time() - 90 * 86400))}
        best = sorted(((v, p) for v, p in perf.items() if v in vids), key=lambda x: -x[1])[:5]
        return {"standing": deep.standing(sid), "monthly": deep.monthly(sid), "since": deep.BACKFILL_FROM,
                "best": [{**vids[v], "index": p} for v, p in best], "comments": deep.top_comments(sid)}
    return _gate(f"/api/deep:{sid}", 600, build, lambda d: {"locked": _auth.lock_info("history", _auth.FREE_DAYS)})


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
            with __import__("tracker").store.reading():
                r = scene._db().execute("SELECT sid, platform, name, url, logo, title, game FROM sc_channels WHERE sid=?", (sid,)).fetchone()
            return {**dict(r), "now": 0, "periods": {}, "days": [], "recent": [], "ranks": [], "linked": []} if r else {}
    return _gate(f"/api/channel:{sid}", 15, build, _auth.trim_channel)


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
    rng = request.args.get("range", "24h") if request.args.get("range") in scene.CAT_RANGES else "24h"
    return _memo(f"/api/cats:{region}:{rng}", 60, _jdump(lambda: scene.categories(region, limit=200, rng=rng)), "application/json")


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


@app.route("/caticon/<sec>.svg")
def caticon_svg(sec):
    from tracker import caticon
    return Response(caticon.svg(sec), mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=604800"})


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
    if not _auth.full():                         # visitors: the channel rankings' default view only (/api/topch)
        return _json({"rows": [], "locked": _auth.lock_info("filters")})
    return _gate(key, 25, lambda: scene.rankings(**args), lambda d: _auth.trim_rows(d))


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
        with __import__("tracker").store.reading():
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
        with __import__("tracker").store.reading():
            known = {r[0] for r in scene._db().execute(
                f"SELECT sid FROM sc_channels WHERE sid IN ({','.join('?' * len(res)) or 'NULL'})", [x["sid"] for x in res])}
        return {"channels": [{**x, "known": x["sid"] in known} for x in res]}
    return _memo(f"/api/ytsearch:{q.lower()}", 600, _jdump(build), "application/json")


@app.route("/api/moments")
def api_moments():
    """Sudden viewer jumps: /api/moments?region=global|in&period=today|7d|30d&game=&sid="""
    from tracker import scene as _sc
    if not _sc.MOMENTS_ON:
        return _json({"moments": [], "removed": True})   # Moments off (owner, 21 Nov); MOMENTS=1 in .env restores it
    from tracker import moments, scene
    g = request.args.get
    region = g("region", "global") if g("region") in scene.REGIONS else "global"
    period = g("period", "7d") if g("period") in ("today", "7d", "30d") else "7d"
    game, sid = (g("game") or "")[:60], (g("sid") or "")[:120]
    sort = g("sort", "views") if g("sort") in ("views", "jump", "hype", "new") else "views"
    return _memo(f"/api/moments:{region}:{period}:{game}:{sid}:{sort}", 10,
                 _jdump(lambda: moments.recent(region, period, game, sid, sort=sort)), "application/json")


@app.route("/moments")
@app.route("/global/moments")
def moments_page():
    from tracker import scene as _sc
    if not _sc.MOMENTS_ON:
        return redirect("/global", 302)      # Moments off (owner, 21 Nov)
    from tracker import momentpage
    return _memo("/moments:global", 300, lambda: momentpage.build_html("global"), "text/html")


@app.route("/india/moments")
def moments_page_india():
    from tracker import scene as _sc
    if not _sc.MOMENTS_ON:
        return redirect("/india", 302)
    from tracker import momentpage
    return _memo("/moments:in", 300, lambda: momentpage.build_html("in"), "text/html")


@app.route("/api/videos")
def api_videos():
    """A YouTube channel's uploads and past live streams in a range: /api/videos?sid=yt:UC...&range=1w|1m|3m|6m|ytd|1y&kind=all|uploads|live"""
    from tracker import ytextra
    sid = (request.args.get("sid") or "")[:60]
    rng = request.args.get("range", "30d") if request.args.get("range") in ytextra.RANGES else "30d"
    vis_lock = not _auth.full()
    if vis_lock and rng not in _auth.FREE_RANGES:
        rng = "7d"                                # visitors: their last 3 videos / streams (the answer says so)
    kind = request.args.get("kind", "all") if request.args.get("kind") in ("all", "uploads", "shorts", "live") else "all"
    if not __import__("re").fullmatch(r"(yt:UC[\w-]{22}|(twitch|kick):[a-z0-9_-]{2,40})", sid):
        return Response("{}", status=404, mimetype="application/json")
    key = f"/api/videos:{sid}:{rng}:{kind}" + (":visitor" if vis_lock else "")
    r = _memo(key, 8, _jdump(lambda: _auth.trim_videos(ytextra.videos_summary(sid, rng, kind)) if vis_lock
                             else ytextra.videos_summary(sid, rng, kind)), "application/json")
    body = (_MEMO.get(key) or (0, b""))[1]
    if b'"loading":true' in body or b'"oldest":null' in body:
        r.headers["X-Short-Cache"] = "1"        # still reading the channel: don't let the CDN keep this copy
    return r


def _chat_lang() -> dict:
    """Chat-language check of Kick / Twitch channels (is the chat Indian?): reader status and how many are decided."""
    try:
        from tracker import chat, langsig
        with langsig._L:
            sids = list(langsig._C)
        v = [langsig.verdict(s_) for s_ in sids]
        return {"twitch": chat.STATUS.get("twitch"), "kick": chat.STATUS.get("kick"), "watching": len(langsig.WANT),
                "indian": v.count(True), "not_indian": v.count(False), "undecided": v.count(None)}
    except Exception as e:
        return {"error": str(e)[:100]}


@app.route("/api/topch")
def api_topch():
    """Top channels: /api/topch?platform=youtube|twitch|kick&metric=size|views|vday|v7|growth|live&country=IN&category=Gaming&game=BGMI"""
    from tracker import ranks
    g = request.args.get
    plat = g("platform", "youtube") if g("platform") in ("youtube", "twitch", "kick", "all") else "youtube"
    metric = g("metric", "size") if g("metric") in ranks.METRICS + ranks.PMETRICS else "size"
    country = (g("country") or "")[:2].upper()
    category, game = (g("category") or "")[:40], (g("game") or "")[:60]
    try:
        limit = max(10, min(1000, int(g("limit") or 100)))
    except ValueError:
        limit = 100
    if not _auth.full() and not _auth.default_ranking(plat, metric, country, category, game):
        return _json({"platform": plat, "metric": metric, "rows": [], "updated": int(ranks._R.get("at") or 1), "total": 0,
                      "categories": [], "countries": [], "locked": _auth.lock_info("filters")})   # visitors: the default view only
    from tracker import scene as sc_
    # the rankings' own time is in the key: new rankings are served the moment they exist, never a copy of the old ones
    # (23 Nov: fresh rankings were ready but the page kept the pre-restart copy while the rebuild queue was busy)
    key = f"/api/topch:{plat}:{metric}:{country}:{category}:{game}:{limit}:{sc_.RULES_V}:{int(ranks._R['at'])}"
    hit = _MEMO.get(key)
    if hit and b'"updated":0,' in hit[1] and ranks._R["at"]:
        _MEMO.pop(key, None)                  # built before the rankings loaded: never serve that empty answer again
    r = _gate(key, 120, lambda: ranks.top(plat, metric, country, category, limit=limit, game=game),
              lambda d: _auth.trim_rows(d))
    if b'"updated":0,' in (_MEMO.get(key) or (0, b""))[1]:
        _MEMO.pop(key, None)                  # rankings not loaded yet: don't keep it here or at Cloudflare (22 Nov: 0 channels for hours)
        r.headers["X-Short-Cache"] = "1"
    return r


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
    if not _auth.full():                          # comparing needs a free account
        return Response(json.dumps({"locked": _auth.lock_info("compare")}), mimetype="application/json")
    if request.args.get("ranges") == "all":       # every range at once, per channel: the page switches range instantly
        return _memo(f"/api/compare-all:{','.join(sids)}", 20, _jdump(lambda: ytextra.compare_all(sids)), "application/json")
    rng = request.args.get("range", "90d") if request.args.get("range") in ytextra.RANGES else "90d"
    return _memo(f"/api/compare:{','.join(sids)}:{rng}", 30, _jdump(lambda: ytextra.compare(sids, rng)), "application/json")


@app.route("/compare")
@app.route("/india/compare")
def compare_page():
    from tracker import comparepage
    region = "in" if request.path.startswith("/india") else "global"
    return _memo(f"/compare:{region}", 300, lambda: comparepage.build_html(region), "text/html")


@app.route("/api/chevents")
def api_chevents():
    """Tournaments this channel broadcast officially, and BGMI's history for BGMI organisers: /api/chevents?sid=yt:UC..."""
    from tracker import eventpage
    sid = request.args.get("sid", "")
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid):
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/api/chevents:{sid}", 300, _jdump(lambda: eventpage.channel_events(sid)), "application/json")


@app.route("/api/streamday")
def api_streamday():
    """A channel's live day (all its streams) for the share card: /api/streamday?sid=yt:UC...&day=2026-11-12"""
    from tracker import ytextra
    sid, day = request.args.get("sid", ""), request.args.get("day", "")
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid) or not __import__("re").fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return Response("Not found", status=404, mimetype="text/plain")
    return _memo(f"/api/streamday:{sid}:{day}", 120, _jdump(lambda: ytextra.stream_day(sid, day)), "application/json")


_LOGO = {}          # sid -> (time, fresh picture url or "")


def fresh_logo(sid: str) -> str:
    """A channel's current profile picture, read from the platform now (an avatar changed since we stored it leaves
    a dead link: 25 Nov, Princess Gaming showed initials). Kept a day, and written back to sc_channels."""
    from tracker import events, platforms
    hit = _LOGO.get(sid)
    if hit and time.time() - hit[0] < 86400:
        return hit[1]
    u = ""
    try:
        if sid.startswith("yt:"):
            r = events._http.get(f"https://www.youtube.com/channel/{sid[3:]}", timeout=8,
                                 headers={"User-Agent": events._UA, "Accept-Language": "en"})
            m = __import__("re").search(r'<meta property="og:image" content="([^"]+)"', r.text)
            u = __import__("re").sub(r"=s\d+.*$", "=s88-c-k-c0x00ffffff-no-rj", m.group(1)) if m else ""
        elif sid.startswith("twitch:") and platforms._keys("twitch"):
            platforms._logos.pop(sid, None)
            platforms._tw_logos([sid[7:]])
            u = platforms.logo(sid)
        elif sid.startswith("kick:"):
            platforms._logos.pop(sid, None)
            platforms._kick_page(sid[5:])
            u = platforms.logo(sid)
    except Exception as e:
        print(f"Fresh logo {sid}: {str(e)[:80]}")
    _LOGO[sid] = (time.time(), u)
    if u:
        try:
            store.write_slices("UPDATE sc_channels SET logo=? WHERE sid=?", [(u, sid)])
        except Exception:
            pass
    return u


@app.route("/api/logo")
def api_logo():
    """/api/logo?sid=yt:UC...: redirects to the channel's current picture (pages use it when a stored one fails)."""
    sid = (request.args.get("sid") or "")[:120]
    if not __import__("re").fullmatch(SID_RX, sid):
        return Response(status=404)
    u = fresh_logo(sid)
    if not u:
        return Response(status=404)
    r = redirect(u, code=302)
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.route("/api/past")
def scene_past():
    """A channel's streams in the last 30 days from the platform itself: /api/past?sid=yt:UC..."""
    from tracker import ytextra
    sid = (request.args.get("sid") or "")[:120]
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid):
        return Response("{}", status=404, mimetype="application/json")
    return _gate(f"/api/past:{sid}", 300, lambda: ytextra.past_streams(sid), _auth.trim_past)


def _ch_page(sid, region):
    from tracker import chpage, scene
    if not __import__("re").fullmatch(r"(yt|kick|twitch):[A-Za-z0-9_.-]{1,100}", sid or ""):
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import ytextra
    with __import__("tracker").store.reading():
        row = scene._db().execute("SELECT name FROM sc_channels WHERE sid=?", (sid,)).fetchone()
    if not row and ytextra.ensure_any(sid):           # a channel found through YouTube / Twitch / Kick lookup
        with __import__("tracker").store.reading():
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


def _key_ok() -> bool:
    want = os.getenv("ADMIN_KEY", "")
    return len(want) >= 16 and hmac.compare_digest(want, request.values.get("key", ""))


def _admin_page(r):
    r.headers["X-Robots-Tag"] = "noindex"
    r.headers["Cache-Control"] = "no-store"
    return r


@app.route("/admin")
@app.route("/admin/")
def admin_home():
    """The owner's portal (tracker/adminpage.py). Signed in with an admin Google account it just opens; the first
    time, /admin?key=<ADMIN_KEY> while signed in makes your account an admin. Anyone else: 404."""
    from tracker import adminpage
    if _auth.ENABLED and _key_ok():
        me = _auth.user()
        if not me:
            return redirect("/signin?next=" + quote("/admin?key=" + request.args.get("key", ""), safe=""))
        _auth.make_admin(me["email"])
        return redirect("/admin")              # the key leaves the address bar
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    return _admin_page(Response(adminpage.overview(_health(), visitors.stats(), _auth.user() if _auth.ENABLED else None,
                                                   "" if _auth.is_admin() else request.args.get("key", "")), mimetype="text/html"))


@app.route("/admin/people")
def admin_people():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import adminpage
    return _admin_page(Response(adminpage.people_page(request.args.get("q", "")[:80], _auth.user() if _auth.ENABLED else None,
                                                      "" if _auth.is_admin() else request.args.get("key", "")), mimetype="text/html"))


@app.route("/admin/people.csv")
def admin_people_csv():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import adminpage
    r = Response(adminpage.people_csv(request.args.get("weekly") == "1"), mimetype="text/csv")
    r.headers["Content-Disposition"] = "attachment; filename=" + ("weekly-report-list.csv" if request.args.get("weekly") == "1" else "accounts.csv")
    return _admin_page(r)


@app.route("/admin/trackers")
def admin_trackers():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import adminpage
    return _admin_page(Response(adminpage.trackers_page(_auth.user() if _auth.ENABLED else None,
                                                        "" if _auth.is_admin() else request.args.get("key", "")), mimetype="text/html"))


@app.route("/admin/trackers/<tk>")
def admin_tracker(tk):
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import adminpage
    return _admin_page(Response(adminpage.tracker_page(tk[:40], _auth.user() if _auth.ENABLED else None,
                                                       "" if _auth.is_admin() else request.args.get("key", ""),
                                                       request.args.get("msg", "")[:200]), mimetype="text/html"))


@app.route("/admin/trackers/<tk>/act", methods=["POST"])
def admin_tracker_act(tk):
    """Count a stream the watch-party check left out, or stop counting one."""
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import events
    f = request.form
    vid = (f.get("vid") or "")[:80]
    a = f.get("action")
    ok = a in ("include", "exclude") and events.set_stream(tk[:40], vid, a == "include")
    msg = ("Counted. It is on the counter now." if a == "include" else "Excluded. It is off the counter now.") if ok else "Not changed."
    key = "" if _auth.is_admin() else f.get("key", "")
    return redirect(f"/admin/trackers/{quote(tk[:40])}?" + "&".join(x for x in (f"key={quote(key)}" if key else "", "msg=" + quote(msg)) if x))


@app.route("/admin/pmgc")
def admin_pmgc():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import adminpage
    return _admin_page(Response(adminpage.pmgc_page(_auth.user() if _auth.ENABLED else None,
                                                    "" if _auth.is_admin() else request.args.get("key", ""),
                                                    request.args.get("q", "")[:60], request.args.get("msg", "")[:200]), mimetype="text/html"))


@app.route("/admin/pmgc.csv")
def admin_pmgc_csv():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import pmgc
    r = Response(pmgc.csv_text(), mimetype="text/csv")
    r.headers["Content-Disposition"] = "attachment; filename=pmgc-gauntlet-predict.csv"
    return _admin_page(r)


@app.route("/admin/pmgc/act", methods=["POST"])
def admin_pmgc_act():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import pmgc
    f = request.form
    msg = "Saved."
    try:
        a = f.get("action")
        if a == "answers":
            pmgc.set_answers(f)
            msg = "Results saved. Points are updated."
        elif a == "settings":
            from datetime import datetime as _dt
            lock = _dt.strptime(f.get("lock", ""), "%Y-%m-%dT%H:%M").replace(tzinfo=pmgc.IST).timestamp()
            pmgc.save(lock=lock, show_lb=f.get("show_lb") == "1", prize=f.get("prize", "")[:200])
            msg = f"Settings saved. Picks lock {pmgc.fmt_ist(lock)}."
        elif a == "logos":
            urls = {t[1]: f.get("logo_" + t[1], "").strip() for t in pmgc.TEAMS}
            urls = {k: v for k, v in urls.items() if v.startswith("https://")}
            pmgc.save(logo_urls={**(pmgc.settings().get("logo_urls") or {}), **urls})
            threading.Thread(target=pmgc.fetch_logos, daemon=True).start()
            msg = "Fetching logos in the background. Refresh in a minute or two."
        elif a in ("hide", "unhide", "delete"):
            pmgc.entry_action(int(f.get("uid", "0")), a)
        else:
            msg = "Unknown action."
    except (pmgc.GameError, ValueError) as e:
        msg = f"Not saved: {e}"
    key = "" if _auth.is_admin() else f.get("key", "")
    return redirect("/admin/pmgc?" + "&".join(x for x in (f"key={quote(key)}" if key else "", "msg=" + quote(msg)) if x))


@app.route("/admin/visitors")
def admin_visitors():
    """Owner-only traffic page (admin Google account, or ?key=<ADMIN_KEY>). 404 for anyone else."""
    if not _owner():
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
    try:
        from tracker import ytextra as yx_
        cov = yx_.coverage()
    except Exception as e:
        cov = {"error": str(e)[:100]}
    r = Response(visitorspage.build_html({**visitors.stats(), "ytq": (used, ev_.YT_QUOTA), "sources": src, "coverage": cov}), mimetype="text/html")
    return _admin_page(_admin_bar(r, "traffic"))


def _owner() -> bool:
    """The owner: signed in with an admin Google account, or the ADMIN_KEY in the address."""
    return _key_ok() or _auth.is_admin()


@app.route("/admin/twitch-connect")
def admin_twitch_connect():
    """Owner-only: connect the owner's Twitch account (no permissions asked) so the site can read follower counts,
    which tell real channels from viewbotted ones. Needs this callback URL added to the Twitch app at
    dev.twitch.tv: <site>/admin/twitch-callback."""
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    import secrets, urllib.parse
    from tracker import platforms, eventpage
    if not platforms._keys("twitch"):
        return Response("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET missing in .env", status=500, mimetype="text/plain")
    st = secrets.token_urlsafe(24)
    store.kv_set("twitch_oauth_state", json.dumps({"s": st, "t": time.time()}))
    q = urllib.parse.urlencode({"client_id": platforms._keys("twitch")[0], "response_type": "code", "scope": "",
                                "redirect_uri": eventpage.SITE_URL + "/admin/twitch-callback", "state": st})
    return redirect("https://id.twitch.tv/oauth2/authorize?" + q)


@app.route("/admin/twitch-callback")
def admin_twitch_callback():
    import html as _h
    from tracker import platforms, eventpage
    try:
        saved = json.loads(store.kv_get("twitch_oauth_state") or "{}")
    except ValueError:
        saved = {}
    st = request.args.get("state", "")
    if not saved.get("s") or not hmac.compare_digest(saved["s"], st) or time.time() - saved.get("t", 0) > 600:
        return Response("Not found", status=404, mimetype="text/plain")
    store.kv_set("twitch_oauth_state", "{}")
    code = request.args.get("code", "")
    if not code:
        return Response("Twitch didn't connect: " + _h.escape(request.args.get("error_description", "cancelled")), mimetype="text/plain")
    i, sec = platforms._keys("twitch")
    r = platforms._http.post("https://id.twitch.tv/oauth2/token", timeout=10, data={
        "client_id": i, "client_secret": sec, "code": code, "grant_type": "authorization_code",
        "redirect_uri": eventpage.SITE_URL + "/admin/twitch-callback"})
    if r.status_code != 200:
        return Response(f"Twitch didn't connect (HTTP {r.status_code}). Check the callback URL in the Twitch app.", mimetype="text/plain")
    j = r.json()
    v = platforms._http.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": "OAuth " + j["access_token"]}, timeout=10)
    login = (v.json() if v.status_code == 200 else {}).get("login", "?")
    store.kv_set("twitch_user", json.dumps({"refresh": j["refresh_token"], "login": login}))
    platforms._tok["twitch_user"] = (j["access_token"], time.time() + int(j.get("expires_in") or 3600))
    return Response(f"Twitch connected as {_h.escape(login)}. Follower counts will be read within 30 minutes. You can close this tab.",
                    mimetype="text/plain")


@app.route("/admin/predict")
def admin_predict():
    """Owner-only Predict & Win dashboard: /admin/predict?key=<ADMIN_KEY from .env>."""
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import predictadmin
    r = Response(predictadmin.build_html(request.args.get("key", ""), request.args.get("q", "")), mimetype="text/html")
    return _admin_page(_admin_bar(r, "predict"))


@app.route("/admin/predict.csv")
def admin_predict_csv():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import predictadmin
    r = Response(predictadmin.csv_text(), mimetype="text/csv")
    r.headers["Content-Disposition"] = "attachment; filename=predict_bmic2026.csv"
    r.headers["Cache-Control"] = "no-store"
    return r


@app.route("/admin/predict/act", methods=["POST"])
def admin_predict_act():
    if not _owner():
        return Response("Not found", status=404, mimetype="text/plain")
    from tracker import predictadmin
    from urllib.parse import quote
    try:
        predictadmin.act(request.form)
    except (predict.GameError, ValueError) as e:
        return Response(f"{e}. Go back and try again.", status=400, mimetype="text/plain")
    return Response(status=303, headers={"Location": "/admin/predict?key=" + quote(request.form.get("key", ""))})


@app.route("/hit", methods=["POST"])
def hit():
    j = request.get_json(silent=True) or {}
    try:
        from urllib.parse import unquote
        _HITS.put_nowait((str(j.get("sid", "")), request.headers.get("CF-IPCountry", ""), str(j.get("ref", "")),
                          request.headers.get("User-Agent", ""), int(j.get("w") or 0),
                          unquote(request.headers.get("cf-ipcity", "")), unquote(request.headers.get("cf-region", "")),
                          request.headers.get("CF-Connecting-IP") or request.remote_addr or "", request.path,
                          str(j.get("p", ""))[:80], request.cookies.get("lge_in") == "1"))
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
threading.Thread(target=__import__("tracker.scene", fromlist=["scene"]).search_index_loop, daemon=True).start()   # search in memory


@app.route("/brand/<name>")
def brand(name):
    """The letsgrowesports wordmark and the share-card strap (static/brand): same origin, so a share card can draw the
    logo without tainting its canvas."""
    import re as _re
    m = _re.fullmatch(r"([a-z0-9-]{1,40})\.(png|js)", name)
    path = os.path.join(os.path.dirname(eventpage.ELOGO_DIR), "brand", name)
    if not m or not os.path.isfile(path):
        return Response(status=404)
    r = _memo(path, 600, _file(path), {"png": "image/png", "js": "application/javascript"}[m.group(2)])
    r.headers["Cache-Control"] = "public, max-age=600"
    return r


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


@app.route("/predict/pmgc")
@app.route("/predict/pmgc/")
def pmgc_page():
    """PMGC 2026 Gauntlet Predict & Win (tracker/pmgc.py, tracker/pmgcpage.py)."""
    from tracker import pmgcpage
    return _memo("/predict/pmgc", 60, pmgcpage.build_html, "text/html")


@app.route("/predict/pmgc/api/state")
def pmgc_state():
    from tracker import pmgc
    u = _auth.user() if _auth.ENABLED else None
    r = Response(json.dumps({**pmgc.state(u), "auth": _auth.ENABLED}), mimetype="application/json")
    r.headers["Cache-Control"] = "no-store"
    return r


@app.route("/predict/pmgc/api/submit", methods=["POST"])
def pmgc_submit():
    from tracker import pmgc
    if _throttle(limit=30, window=600):
        return Response(json.dumps({"error": "Too many tries. Wait a few minutes."}), status=429, mimetype="application/json")
    u = _auth.user() if _auth.ENABLED else None
    j = request.get_json(silent=True) or {}
    picks = j.get("picks") if isinstance(j.get("picks"), dict) else {}
    picks = {str(k)[:4]: ([str(x)[:60] for x in v][:8] if isinstance(v, list) else str(v)[:60]) for k, v in list(picks.items())[:12]}
    try:
        return _json(pmgc.submit(u, str(j.get("handle", ""))[:80], str(j.get("name", ""))[:64], picks))
    except pmgc.GameError as e:
        return Response(json.dumps({"error": str(e)}), status=e.code, mimetype="application/json")


@app.route("/pmgc/logo/<slug>")
def pmgc_logo(slug):
    from tracker import pmgc
    if slug not in {t[1] for t in pmgc.TEAMS}:
        return Response(status=404)
    f = pmgc.logo_file(slug)
    if not f:
        return Response(status=404)
    ext = os.path.splitext(f)[1]
    ct = {".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[ext]
    with open(f, "rb") as fh:
        r = Response(fh.read(), mimetype=ct)
    r.headers["Cache-Control"] = "public, max-age=86400, s-maxage=86400"   # the ?v= in the address changes with the file
    if ext == ".svg":
        r.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return r


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
        clean[str(k)] = [str(x) for x in v][:20] if isinstance(v, list) else str(v)[:500]
    try:
        return _json(predict.submit_all(_tok(), clean, ip=request.headers.get("CF-Connecting-IP") or request.remote_addr or ""))
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


WARM = ["/global", "/india", "/api/cats?region=global&range=24h", "/api/cats?region=in&range=24h", "/global/categories", "/india/categories", "/api/home?region=global", "/api/home?region=in", "/api/scene?region=global&period=today", "/api/scene?region=in&period=today",
        "/api/scene/live?region=global", "/api/scene/live?region=in", "/global/rankings", "/api/rank?region=global&period=day&metric=hw",
        "/api/rank?region=in&period=day&metric=hw", "/map", "/api/geo", "/e/pic/data",
        "/india/rankings", "/api/rank?region=in&period=week&metric=peak", "/api/rank?region=global&period=week&metric=hw",
        "/api/topch?platform=youtube&metric=views_7d", "/api/topch?platform=youtube&metric=views_7d&country=IN",
        "/api/topch?platform=twitch&metric=subs_7d&country=IN", "/api/topch?platform=kick&metric=subs_7d&country=IN"] + (
        ["/global/c/gta-6", "/india/c/gta-6", "/api/scene?region=global&cat=gta-6&period=today", "/api/scene?region=in&cat=gta-6&period=today"]
        + [f"/api/topch?platform=all&metric={m}_{p}{c}&game=GTA%206" for m in ("peak", "avg", "live") for p in ("24h", "7d")
           for c in ("&country=IN", "")]          # the GTA 6 rankings people share
        if __import__("tracker.scene", fromlist=["x"]).gta6_on() else [])


def _warm_more():
    """Beyond the fixed list: every few minutes, build the pages people open next: the 40 biggest categories and
    every section and live tournament in both regions, and the biggest channels' pages. Pages already built are
    skipped by the cache, so this only costs work for what has expired."""
    from tracker import scene
    time.sleep(90)
    c = app.test_client()
    H = {"Accept-Encoding": "gzip", "X-Warm": "1"}
    while True:
        t0 = time.time()
        if scene.overloaded():                # behind: visitors' pages and the scan first
            time.sleep(60)
            continue
        try:
            for region, rp in (("in", "/india"), ("global", "/global")):
                lv = scene._live_part(None, region)
                cats = sorted(lv["_by_game"].values(), key=lambda g: -g["viewers"])[:15 if region == "in" else 10]
                urls = []
                for g in cats:
                    sl = scene.slug(g["game"])
                    urls += [f"{rp}/c/{sl}", f"/api/scene?region={region}&cat={sl}&period=today", f"/api/catmonths?cat={sl}&region={region}"]
                for sec, _ in scene.SECTIONS:
                    urls += [f"{rp}/s/{sec}", f"/api/scene?region={region}&sec={sec}&period=today"]
                for t in list(lv["_tours"].values())[:30]:
                    sl = scene.slug(t["name"])
                    urls += [f"{rp}/t/{sl}", f"/api/tour?region={region}&t={sl}"]
                top = sorted(lv["_live"], key=lambda x: -x["viewers"])[:40]
                for x in top:
                    urls += [f"/api/channel?sid={x['sid']}"]
                for u in urls:
                    if scene.overloaded():
                        break
                    try:
                        c.get(u, headers=H)
                    except Exception:
                        pass
                    time.sleep(0.2)
        except Exception as e:
            print(f"Warm more: {str(e)[:120]}")
        time.sleep(max(30, 240 - (time.time() - t0)))


def _warm_forever():
    """Keep the busiest pages built, so a visitor never waits for one to be computed."""
    from tracker import scene
    time.sleep(30)
    c = app.test_client()
    while True:
        for i, u in enumerate(WARM):
            if i >= 12 and scene.overloaded():      # behind: only the front pages stay warm
                break
            try:
                c.get(u, headers={"Accept-Encoding": "gzip", "X-Warm": "1"})
            except Exception:
                pass
        time.sleep(30 if scene.overloaded() else 10)


def run():
    print(f"Event dashboard: http://localhost:{PORT}")
    _memo_load()
    store.checkpointer()
    threading.Thread(target=_memo_save, daemon=True).start()
    try:
        from tracker import pmgc as _pg
        _pg.logo_loop()                       # PMGC team logos from Liquipedia, once (data/teamlogos/)
    except Exception as e:
        print(f"PMGC logos: {str(e)[:100]}")
    def once():
        from tracker import events as ev_, scene as sc_, ytextra as yx_
        time.sleep(20)
        yx_._nn_build()
        ev_.backfill_pic_day1()
        sc_.backfill_reg_day()
        def g6_refile():                     # after a few scans have looked up the missing titles
            time.sleep(420)
            try:
                if False and not store.kv_get("refile_g6_v1"):   # off: it used today's title for past days (19 Nov)
                    sc_.refile_gta6()
                    store.kv_set("refile_g6_v1", time.time())
            except Exception as e:
                print(f"GTA 6 refile: {str(e)[:120]}")
        threading.Thread(target=g6_refile, daemon=True).start()

        def g6_verify():                     # every 15 min: YouTube channels in GTA 6 lists checked against their streams
            time.sleep(90)
            try:
                if not store.kv_get("g6_peaks_v2"):
                    sc_.fix_switch_peaks2()
                    store.kv_set("g6_peaks_v2", time.time())
                    from tracker import ranks as rk2_
                    rk2_.compute()
                if not store.kv_get("g6_peaks_v1"):
                    sc_.fix_switch_peaks()
                    store.kv_set("g6_peaks_v1", time.time())
                if not store.kv_get("g6_unnews_v1"):
                    sc_.unnews_g6()
                    store.kv_set("g6_unnews_v1", time.time())
                    from tracker import ranks as rk_
                    rk_.compute()
            except Exception as e:
                print(f"GTA 6 news repair: {str(e)[:120]}")
            try:
                if not store.kv_get("g6_unfile_v1"):
                    sc_.unfile_g6()
                    store.kv_set("g6_unfile_v1", time.time())
                    from tracker import ranks as rk_
                    rk_.compute()
            except Exception as e:
                print(f"GTA 6 repair: {str(e)[:120]}")
            while True:
                try:
                    sc_.verify_g6()
                except Exception as e:
                    print(f"GTA 6 check: {str(e)[:120]}")
                time.sleep(900)
        threading.Thread(target=g6_verify, daemon=True).start()

        def drop_moments():                  # Moments removed by the owner (21 Nov): its stored data goes too
            time.sleep(120)
            try:
                if not store.kv_get("moments_dropped"):
                    with store._lock:
                        c = store.main()
                        c.execute("DROP TABLE IF EXISTS moments")
                        c.commit()
                    store.kv_set("moments_dropped", time.time())
                    print("Moments: table dropped")
            except Exception as e:
                print(f"Moments drop: {str(e)[:120]}")
        threading.Thread(target=drop_moments, daemon=True).start()

        def yt_cards():                      # the game YouTube shows under each stream: read once per stream
            time.sleep(60)
            try:
                if not store.kv_get("g6_cards_v1"):
                    sc_.refile_cards()
                    store.kv_set("g6_cards_v1", time.time())
                    from tracker import ranks as rk_
                    rk_.compute()
            except Exception as e:
                print(f"GTA 6 game cards: {str(e)[:120]}")
            def refile():                    # every stream's game from YouTube's card: 30 days once, then 3 days daily
                while True:
                    try:
                        full = not store.kv_get("games_refile_v1")
                        sc_.refile_games(30 if full else 3, 2500 if full else 600, pace=sc_.overloaded)
                        if full:
                            store.kv_set("games_refile_v1", time.time())
                    except Exception as e:
                        print(f"Game refile: {str(e)[:120]}")
                    time.sleep(86400)
            threading.Thread(target=refile, daemon=True).start()
            while True:
                try:
                    sc_.cards_once()
                except Exception as e:
                    print(f"Game cards: {str(e)[:120]}")
                time.sleep(60)
        threading.Thread(target=yt_cards, daemon=True).start()
        try:
            sc_.merge_aliases()
        except Exception as e:
            print(f"Tournament merge: {str(e)[:120]}")
    threading.Thread(target=once, daemon=True).start()

    def india_marks():                       # channels known Indian from events / BGMI: counted in India's rankings
        from tracker import scene as sc_
        time.sleep(40)
        while True:
            try:
                n = sc_.mark_known_india()
                if n:
                    print(f"India flags changed on {n} channels (event trackers, BGMI, seeds); recomputing ranks")
                    from tracker import ranks as rk_
                    rk_.compute()                    # India's channel rankings show it now, not in 30 minutes
            except Exception as e:
                print(f"India marks: {str(e)[:120]}")
            time.sleep(3600)
    threading.Thread(target=india_marks, daemon=True).start()
    threading.Thread(target=_warm_forever, daemon=True).start()
    threading.Thread(target=_warm_more, daemon=True).start()
    try:
        from waitress import serve   # production server if installed (pip install waitress)
        serve(app, host="127.0.0.1", port=PORT, threads=48, connection_limit=2000, channel_timeout=30, _quiet=True)
    except ImportError:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False, threaded=True)
