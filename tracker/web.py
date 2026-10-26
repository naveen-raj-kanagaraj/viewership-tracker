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


CACHE = {"/india": 30, "/india/data": 20, "/api/scene": 20, "/api/scene/live": 2, "/": 5, "/data": 2, "/series": 60, "/predict": 30, "/predict/api/board": 5, "/predict/og.png": 3600}   # seconds Cloudflare (or any CDN) may reuse a response



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
    elif path.startswith(("/c/", "/s/", "/global")):
        path = "/india"
    secs = CACHE.get(path)
    if request.path.startswith("/predict/api/profile/") and request.method == "GET":
        secs = 15
    if request.method != "GET" or resp.status_code >= 400:
        secs = None                       # POSTs, personal and error responses are never cached
    if request.path.startswith(("/elogo/", "/tlogo/", "/pimg/", "/tmark/")):
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


def _memo(key, ttl, build, mimetype):
    hit = _MEMO.get(key)
    if not (hit and time.time() - hit[0] < ttl):
        lock = _MLOCK.setdefault(key, threading.Lock())
        with lock:
            hit = _MEMO.get(key)
            if not (hit and time.time() - hit[0] < ttl):
                body = build()
                if isinstance(body, str):
                    body = body.encode()
                hit = (time.time(), body, gzip.compress(body, 5) if len(body) > 1024 else None)
                _MEMO[key] = hit
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
    """The India hub, unless `track.py home <event>` made an event the front page (e.g. on a tournament day)."""
    from tracker import events, store
    home = store.kv_get("site_home") or "hub"
    if home != "hub" and events.get(home):
        return _memo("/:" + home, 5, lambda: eventpage.build_html(live=True), "text/html")
    return india()


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


@app.route("/global")
def global_hub():
    """Everything live worldwide on YouTube, Kick and Twitch."""
    from tracker import scenepage
    return _memo("/global", 300, lambda: scenepage.build_html(region="global"), "text/html")


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
    """One game or category in India: /c/bgmi, /c/free-fire, /c/news ..."""
    return _cat_page(cat, "in")


@app.route("/global/c/<cat>")
def category_global(cat):
    return _cat_page(cat, "global")


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
    """A section in India: /s/gaming, /s/esports, /s/irl, /s/just-chatting, /s/news ..."""
    return _sec_page(sec, "in")


@app.route("/global/s/<sec>")
def section_global(sec):
    return _sec_page(sec, "global")


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


def run():
    print(f"Event dashboard: http://localhost:{PORT}")
    try:
        from waitress import serve   # production server if installed (pip install waitress)
        serve(app, host="127.0.0.1", port=PORT, threads=48, connection_limit=2000, channel_timeout=30, _quiet=True)
    except ImportError:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False, threaded=True)
