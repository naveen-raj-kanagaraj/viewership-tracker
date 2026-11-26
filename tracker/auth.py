"""Sign in with Google: visitors see the live site and the top of every list; signed-in people see everything
(top 100+, channel history beyond 7 days, compare). Their email comes with consent for the weekly report.

Off until GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are in .env (docs/SIGNIN.md): then nothing is locked and no
sign-in button shows, so deploying this changes nothing.

How it works
  - OpenID Connect code flow with PKCE, state and nonce. The ID token comes straight from Google's token endpoint
    over TLS (OpenID Connect Core 3.1.3.7 allows that instead of a signature check); its issuer, audience, expiry,
    nonce and verified email are checked. Scopes: openid email profile (no Google API access, no passwords).
  - People are kept in data/users.db (not tracker.db: personal data apart from the public numbers, private like
    all of data/). The browser holds a signed, HttpOnly, Secure cookie with the user id (30 days) and a plain
    'lge_in=1' cookie so the page knows to ask for the full data.
  - Cloudflare caches API answers by URL and can't tell people apart, so the full answer has its own URL: the page
    adds auth=1 to the locked APIs when signed in; that answer is never cached (no-store). Without auth=1 (or
    without a valid session) the API gives the visitor version, which caches as before. The locks are on the
    server, so the data can't be pulled around them.
  - The weekly email: the sign-in screen and the popup say every account gets it; every email carries a one-click
    unsubscribe link (signed, no login needed), and /account switches it off. A returning person who unsubscribed
    stays unsubscribed. People can download or delete their data at /account.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import Response, redirect, request, session

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
ENABLED = bool(CLIENT_ID and CLIENT_SECRET) and os.getenv("SIGNIN", "1") == "1"
SITE = os.getenv("SITE_URL", "https://live.letsgrowesports.com").rstrip("/")
REDIRECT = SITE + "/auth/google/callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.getenv("USERS_DB") or os.path.join(DATA, "users.db")
DAYS = 30                                     # how long a sign-in lasts

# What a visitor (not signed in) gets; signed in: everything
FREE_ROWS = 25          # rankings: the default view's top 25 (no filters; owner 26 Nov: limit, but not growth)
FREE_DAYS = 7
FREE_STREAMS = 3        # a channel's last 3 streams
FREE_RANGES = ("1d", "3d", "7d")

_lock = threading.Lock()
_conn = {}


def _db():
    c = _conn.get("c")
    if c is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, sub TEXT UNIQUE NOT NULL, email TEXT,
                     name TEXT, picture TEXT, created INTEGER, last_seen INTEGER, weekly INTEGER DEFAULT 0,
                     weekly_ts INTEGER, region TEXT, sess INTEGER DEFAULT 1)""")
        c.commit()
        try:
            os.chmod(DB_PATH, 0o600)
        except OSError:
            pass
        _conn["c"] = c
    return c


def secret_key() -> bytes:
    """The key that signs session cookies: SESSION_SECRET in .env, else made once and kept in data/ (private)."""
    k = os.getenv("SESSION_SECRET", "").strip()
    if k:
        return k.encode()
    path = os.path.join(DATA, ".session_key")
    try:
        with open(path, "rb") as f:
            v = f.read().strip()
            if len(v) >= 32:
                return v
    except OSError:
        pass
    os.makedirs(DATA, exist_ok=True)
    v = secrets.token_hex(32).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(v)
    return v


def setup(app):
    app.secret_key = secret_key()
    app.config.update(SESSION_COOKIE_NAME="lge_s", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=SITE.startswith("https"), PERMANENT_SESSION_LIFETIME=DAYS * 86400,
                      SESSION_REFRESH_EACH_REQUEST=False)   # never a Set-Cookie on a cacheable answer
    for rule, fn, methods in ((("/signin"), signin_page, ["GET"]), ("/auth/google", start, ["GET"]),
                              ("/auth/google/callback", callback, ["GET"]), ("/auth/signout", signout, ["POST"]),
                              ("/auth/me", me, ["GET"]), ("/account", account_page, ["GET"]),
                              ("/auth/prefs", prefs, ["POST"]), ("/auth/export", export, ["GET"]),
                              ("/auth/delete", delete, ["POST"]), ("/auth/unsub", unsub, ["GET", "POST"])):
        app.add_url_rule(rule, "auth_" + fn.__name__, fn, methods=methods)


# ---- who is asking -------------------------------------------------------------------------------------------

def user():
    """The signed-in person (a dict) or None. Reads the session only when asked, so visitors get no cookie."""
    uid, ver = session.get("uid"), session.get("v")
    if not uid:
        return None
    with _lock:
        r = _db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not r or r["sess"] != ver:
            return None
        if time.time() - (r["last_seen"] or 0) > 3600:
            _db().execute("UPDATE users SET last_seen=? WHERE id=?", (int(time.time()), uid))
            _db().commit()
    return dict(r)


def full() -> bool:
    """Does this request get everything? Yes when sign-in is off; else only signed in and asking with auth=1."""
    if not ENABLED:
        return True
    return request.args.get("auth") == "1" and user() is not None


def lock_info(what: str, shown=None, total=None) -> dict:
    return {"what": what, "shown": shown, "total": total, "signin": "/signin"}


# ---- trimming the visitor versions ---------------------------------------------------------------------------

def trim_rows(d: dict, what: str = "rows") -> dict:
    """Lists: the first FREE_ROWS."""
    if not isinstance(d, dict) or not isinstance(d.get("rows"), list):
        return d
    n = len(d["rows"])
    if n <= FREE_ROWS:
        return d
    small = {k: [] for k in ("games",) if k in d}             # the filter lists visitors can't use (most of the bytes)
    return {**d, **small, "rows": d["rows"][:FREE_ROWS], "locked": lock_info(what, FREE_ROWS, d.get("total") or n)}


def trim_videos(d: dict) -> dict:
    """A channel's videos / past streams for visitors: the newest FREE_STREAMS, no history chart."""
    if not isinstance(d, dict):
        return d
    vids = d.get("videos") if isinstance(d.get("videos"), list) else []
    return {**d, "videos": sorted(vids, key=lambda v: -(v.get("ts") or 0))[:FREE_STREAMS], "series": [],
            "locked": lock_info("history", FREE_STREAMS)}


def trim_channel(d: dict) -> dict:
    """A channel page for visitors: who it is, live now, today and the last 7 days (what Google indexes and what a
    shared link shows); 30-day and all-time totals, older days, views history and Super Chats need sign-in (their
    last 3 streams come from /api/past)."""
    if not isinstance(d, dict) or not d.get("sid"):
        return d
    per = d.get("periods") or {}
    p = {k: (v if k in ("today", "7d") else None) for k, v in per.items()}
    from tracker import events
    since = (datetime.now(events.REPORT_TZ).date() - timedelta(days=FREE_DAYS)).isoformat()   # the 7d window (scene.channel)
    days = [x for x in (d.get("days") or []) if isinstance(x, dict) and str(x.get("day") or "") >= since]
    out = {**d, "periods": p, "days": days, "seen": bool((per.get("all") or {}).get("days")),
           "locked": lock_info("history", FREE_STREAMS)}
    if isinstance(d.get("views"), list):
        out["views"] = []
    if "top_superchats" in d:
        out["top_superchats"] = []
    if "superchats" in d:
        out["superchats"] = None
    return out


def trim_past(d: dict) -> dict:
    """Past streams for visitors: the newest FREE_STREAMS."""
    if not isinstance(d, dict) or not isinstance(d.get("streams"), list):
        return d
    keep = sorted(d["streams"], key=lambda s: -(s.get("ts") or s.get("start") or 0))[:FREE_STREAMS]
    if len(keep) == len(d["streams"]):
        return d
    return {**d, "streams": keep, "locked": lock_info("history", FREE_STREAMS)}


def default_ranking(platform: str, metric: str, country: str, category: str, game: str) -> bool:
    """The rankings visitors get: every platform over 7 days, worldwide or India, by peak, average or hours watched
    (owner, 26 Nov: let them switch the measure); other platforms, periods, games and countries need sign-in."""
    return (platform == "all" and metric in ("peak_7d", "avg_7d", "live_7d") and country in ("", "IN")
            and not category and not game)


# ---- pages and endpoints ---------------------------------------------------------------------------------------

def _safe_next(n: str) -> str:
    n = (n or "/").strip()
    return n if n.startswith("/") and not n.startswith("//") and "\\" not in n and len(n) < 400 else "/"


def _page(title: str, body: str) -> str:
    from tracker import eventpage
    import html
    b = html.escape(eventpage.BRAND)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | {b}</title><meta name="robots" content="noindex"><meta name="theme-color" content="#060609">
<style>:root{{color-scheme:dark}}body{{margin:0;background:#060609;color:#fff;font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}}
.top{{border-bottom:1px solid #1c1c26}}.top .in{{max-width:560px;margin:0 auto;padding:12px 16px}}.brand{{color:#b6f23a;font-weight:800;text-decoration:none;letter-spacing:.04em;text-transform:uppercase}}
main{{max-width:560px;margin:0 auto;padding:28px 16px 64px}}h1{{font-size:28px;line-height:1.2;margin:0 0 8px}}p{{color:#b4b3c4}}
.box{{background:#0d0d13;border:1px solid #1a1a23;border-radius:12px;padding:22px}}ul{{color:#d8d7e4;padding-left:20px}}li{{margin:5px 0}}
.g{{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;background:#fff;color:#1f1f1f;border:0;border-radius:10px;padding:13px 16px;font:600 16px system-ui,sans-serif;cursor:pointer;text-decoration:none;margin-top:14px}}
.g:hover{{background:#f1f1f1}}label{{display:flex;gap:10px;align-items:flex-start;color:#d8d7e4;font-size:14px;margin-top:16px;cursor:pointer}}input[type=checkbox]{{margin-top:4px;width:17px;height:17px;accent-color:#b6f23a}}
.small{{font-size:13px;color:#8d8ca3}}a{{color:#b6f23a}}.btn{{background:#1a1a24;color:#fff;border:1px solid #2a2a38;border-radius:9px;padding:9px 14px;font:600 14px system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-block}}
.danger{{color:#ff6b78;border-color:#4a2028}}.row{{display:flex;gap:12px;align-items:center}}.row img{{width:44px;height:44px;border-radius:50%}}.err{{background:#2a1218;border:1px solid #4a2028;color:#ffb3bb;padding:10px 12px;border-radius:9px;margin-bottom:14px;font-size:14px}}</style></head>
<body><div class="top"><div class="in"><a class="brand" href="/">{b}</a></div></div><main>{body}</main></body></html>"""


G_LOGO = """<svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.6 13.2l7.9 6.2C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 7l7.2 5.6c4.2-3.9 7.1-9.6 7.1-17.1z"/><path fill="#FBBC05" d="M10.5 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.2C1 16.4 0 20.1 0 24s1 7.6 2.6 10.8l7.9-6.2z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.2-5.6c-2 1.4-4.7 2.3-8.7 2.3-6.3 0-11.6-4.1-13.5-9.9l-7.9 6.2C6.6 42.6 14.6 48 24 48z"/></svg>"""


def signin_page():
    import html
    nxt = _safe_next(request.args.get("next"))
    if not ENABLED:
        return redirect(nxt)
    err = {"denied": "Sign-in was cancelled.", "failed": "Google sign-in didn't go through. Please try again.",
           "email": "That Google account has no verified email."}.get(request.args.get("e", ""), "")
    body = f"""<div class="box"><h1>Sign in, it's free</h1><p>See everything on the site:</p>
<ul><li>Full rankings: top 100 and beyond, every platform, game and country</li><li>Every channel's full history: 30 days, all-time peaks, past streams</li>
<li>Compare up to 4 channels side by side</li></ul>{f'<div class="err">{err}</div>' if err else ''}
<form method="get" action="/auth/google" style="margin-top:6px"><input type="hidden" name="next" value="{html.escape(nxt)}">
<button class="g" type="submit">{G_LOGO} Continue with Google</button></form>
<p class="small" style="margin-top:10px">We get your name, email and profile picture from Google, nothing else (no passwords, no access to your YouTube or Gmail). See the <a href="/privacy">Privacy Policy</a>; you can download or delete your data any time.</p></div>"""
    return Response(_page("Sign in", body), mimetype="text/html")


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def start():
    if not ENABLED:
        return redirect("/")
    st, nonce, ver = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    session["oauth"] = {"state": st, "nonce": nonce, "ver": ver, "next": _safe_next(request.args.get("next")),
                        "weekly": True, "ts": int(time.time())}   # new accounts get the weekly email (said on the
                                                                           # sign-in screen; unsubscribe any time)
    q = {"client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code", "scope": "openid email profile",
         "state": st, "nonce": nonce, "prompt": "select_account",
         "code_challenge": _b64(hashlib.sha256(ver.encode()).digest()), "code_challenge_method": "S256"}
    return redirect(AUTH_URL + "?" + urlencode(q))


def _claims(id_token: str) -> dict:
    parts = id_token.split(".")
    if len(parts) != 3:
        raise ValueError("bad token")
    pad = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(pad))


def callback():
    import requests
    o = session.pop("oauth", None) or {}
    nxt = o.get("next") or "/"
    if request.args.get("error"):
        return redirect("/signin?e=denied&next=" + nxt)
    if not o or not hmac.compare_digest(str(request.args.get("state", "")), str(o.get("state", ""))) \
            or time.time() - o.get("ts", 0) > 900:
        return redirect("/signin?e=failed&next=" + nxt)
    try:
        r = requests.post(TOKEN_URL, data={"code": request.args.get("code", ""), "client_id": CLIENT_ID,
                                           "client_secret": CLIENT_SECRET, "redirect_uri": REDIRECT,
                                           "grant_type": "authorization_code", "code_verifier": o["ver"]}, timeout=15)
        tok = r.json()
        c = _claims(tok["id_token"])
    except Exception as e:
        print(f"Sign-in token exchange failed: {str(e)[:120]}")
        return redirect("/signin?e=failed&next=" + nxt)
    if c.get("iss") not in ISSUERS or c.get("aud") != CLIENT_ID or c.get("exp", 0) < time.time() \
            or not hmac.compare_digest(str(c.get("nonce", "")), str(o["nonce"])) or not c.get("sub"):
        print("Sign-in rejected: token claims did not match")
        return redirect("/signin?e=failed&next=" + nxt)
    if not c.get("email") or not c.get("email_verified"):
        return redirect("/signin?e=email&next=" + nxt)
    now = int(time.time())
    with _lock:
        db = _db()
        row = db.execute("SELECT id, sess, weekly FROM users WHERE sub=?", (c["sub"],)).fetchone()
        if row:
            db.execute("UPDATE users SET email=?, name=?, picture=?, last_seen=? WHERE id=?",
                       (c["email"].lower(), c.get("name", "")[:120], c.get("picture", "")[:500], now, row["id"]))
            uid, ver = row["id"], row["sess"]
        else:
            cur = db.execute("INSERT INTO users (sub, email, name, picture, created, last_seen, weekly, weekly_ts, region, sess) "
                             "VALUES (?,?,?,?,?,?,?,?,?,1)",
                             (c["sub"], c["email"].lower(), c.get("name", "")[:120], c.get("picture", "")[:500], now, now,
                              1 if o.get("weekly") else 0, now if o.get("weekly") else None,
                              (request.headers.get("CF-IPCountry") or "")[:2]))
            uid, ver = cur.lastrowid, 1
        db.commit()
    session.clear()
    session.permanent = True
    session["uid"], session["v"] = uid, ver
    resp = redirect(nxt)
    resp.set_cookie("lge_in", "1", max_age=DAYS * 86400, secure=SITE.startswith("https"), samesite="Lax")
    return resp


def _out(resp):
    session.clear()
    resp.delete_cookie("lge_in")
    resp.delete_cookie("lge_s")
    return resp


def signout():
    return _out(redirect(_safe_next(request.form.get("next") or request.args.get("next"))))


def me():
    u = user() if ENABLED else None
    body = {"enabled": ENABLED, "signed_in": bool(u)}
    if u:
        body.update(name=u["name"], email=u["email"], picture=u["picture"], weekly=bool(u["weekly"]))
    resp = Response(json.dumps(body), mimetype="application/json")
    if ENABLED and not u and request.cookies.get("lge_in"):
        resp.delete_cookie("lge_in")          # signed out elsewhere or deleted: stop asking for full data
    return resp


def account_page():
    import html
    if not ENABLED:
        return redirect("/")
    u = user()
    if not u:
        return redirect("/signin?next=/account")
    e = html.escape
    pic = f'<img src="{e(u["picture"])}" alt="" referrerpolicy="no-referrer">' if u["picture"] else ""
    body = f"""<div class="box"><div class="row">{pic}<div><b>{e(u['name'] or '')}</b><div class="small">{e(u['email'])}</div></div></div>
<form method="post" action="/auth/prefs"><label><input type="checkbox" name="weekly" value="1" {'checked' if u['weekly'] else ''} onchange="this.form.submit()"> <span>Email me the weekly report</span></label></form>
<p class="small">Signed in since {time.strftime('%d %b %Y', time.localtime(u['created']))}.</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px"><a class="btn" href="/">Back to the site</a>
<form method="post" action="/auth/signout"><button class="btn">Sign out</button></form>
<a class="btn" href="/auth/export">Download my data</a>
<form method="post" action="/auth/delete" onsubmit="return confirm('Delete your account and everything we keep about you? This cannot be undone.')"><button class="btn danger">Delete my account</button></form></div></div>"""
    return Response(_page("Your account", body), mimetype="text/html")


def prefs():
    u = user()
    if not u:
        return redirect("/signin?next=/account")
    on = request.form.get("weekly") == "1"
    with _lock:
        _db().execute("UPDATE users SET weekly=?, weekly_ts=? WHERE id=?", (1 if on else 0, int(time.time()), u["id"]))
        _db().commit()
    return redirect("/account")


def export():
    u = user()
    if not u:
        return redirect("/signin?next=/account")
    keep = {k: u[k] for k in ("email", "name", "picture", "created", "last_seen", "weekly", "weekly_ts", "region")}
    r = Response(json.dumps(keep, indent=2), mimetype="application/json")
    r.headers["Content-Disposition"] = "attachment; filename=letsgrowesports-account.json"
    return r


def delete():
    u = user()
    if u:
        with _lock:
            _db().execute("DELETE FROM users WHERE id=?", (u["id"],))
            _db().commit()
    return _out(Response(_page("Account deleted", '<div class="box"><h1>Account deleted</h1><p>Everything we kept about you is gone.</p><a class="btn" href="/">Back to the site</a></div>'), mimetype="text/html"))


def unsub_token(uid: int) -> str:
    return hmac.new(secret_key(), f"unsub:{uid}".encode(), hashlib.sha256).hexdigest()[:32]


def unsub_link(uid: int) -> str:
    return f"{SITE}/auth/unsub?u={uid}&t={unsub_token(uid)}"


def unsub():
    """One click from an email, no sign-in (also answers mail apps' one-click POST, RFC 8058)."""
    try:
        uid = int(request.values.get("u", "0"))
    except ValueError:
        uid = 0
    if uid and hmac.compare_digest(unsub_token(uid), request.values.get("t", "")):
        with _lock:
            _db().execute("UPDATE users SET weekly=0, weekly_ts=? WHERE id=?", (int(time.time()), uid))
            _db().commit()
        return Response(_page("Unsubscribed", '<div class="box"><h1>Unsubscribed</h1><p>You won\'t get the weekly report any more.</p><a class="btn" href="/">Back to the site</a></div>'), mimetype="text/html")
    return Response(_page("Link not valid", '<div class="box"><h1>That link is not valid</h1><p>Sign in and change it on your account page.</p><a class="btn" href="/account">Your account</a></div>'), mimetype="text/html", status=400)


def admins() -> set:
    """Emails allowed into /admin: ADMIN_EMAILS in .env (comma separated) plus the ones bound with the admin key."""
    from tracker import store
    env = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    return env | set(store.kv_get("admin_emails") or [])


def make_admin(email: str):
    from tracker import store
    cur = set(store.kv_get("admin_emails") or [])
    cur.add(email.lower())
    store.kv_set("admin_emails", sorted(cur))


def is_admin() -> bool:
    if not ENABLED:
        return False
    u = user()
    return bool(u and u["email"] and u["email"].lower() in admins())


def people(q: str = "", limit: int = 500) -> list:
    """Signed-up people, newest first (admin portal)."""
    sql, args = "SELECT id, email, name, picture, created, last_seen, weekly, region FROM users", []
    if q:
        sql += " WHERE email LIKE ? OR name LIKE ?"
        args += [f"%{q}%", f"%{q}%"]
    with _lock:
        return [dict(r) for r in _db().execute(sql + " ORDER BY created DESC LIMIT ?", (*args, limit))]


def counts() -> dict:
    from datetime import datetime, timedelta, timezone
    ist = timezone(timedelta(hours=5, minutes=30))
    d0 = datetime.now(ist).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    with _lock:
        c = _db()
        one = lambda sql, *a: c.execute(sql, a).fetchone()[0] or 0
        days = [(datetime.fromtimestamp(d0 - i * 86400, ist).strftime("%d %b"),
                 one("SELECT COUNT(*) FROM users WHERE created>=? AND created<?", d0 - i * 86400, d0 - (i - 1) * 86400))
                for i in range(13, -1, -1)]
        return {"total": one("SELECT COUNT(*) FROM users"), "today": one("SELECT COUNT(*) FROM users WHERE created>=?", d0),
                "week": one("SELECT COUNT(*) FROM users WHERE created>=?", d0 - 6 * 86400),
                "weekly": one("SELECT COUNT(*) FROM users WHERE weekly=1"),
                "active_today": one("SELECT COUNT(*) FROM users WHERE last_seen>=?", d0), "days": days,
                "countries": [tuple(r) for r in c.execute("SELECT COALESCE(NULLIF(region,''),'-'), COUNT(*) FROM users GROUP BY 1 ORDER BY 2 DESC LIMIT 8")]}


def weekly_list() -> list:
    """Who asked for the weekly report: [(id, email, name)] (for the sender, once an email service is set up)."""
    with _lock:
        return [tuple(r) for r in _db().execute("SELECT id, email, name FROM users WHERE weekly=1 ORDER BY id")]


# ---- the bit every page carries --------------------------------------------------------------------------------

LOCKED_API = ("/api/rank", "/api/topch", "/api/channel", "/api/past", "/api/videos", "/api/compare", "/api/deep")


def page_js() -> str:
    """Injected into every page: the Sign in / account button in the header, auth=1 on locked APIs when signed in,
    and a sign-in bar when an answer says part of it is locked."""
    if not ENABLED:
        return "<script>window.LGE_AUTH={on:false,in:false}</script>"
    return """<script>(function(){var IN=/(?:^|; )lge_in=1/.test(document.cookie);window.LGE_AUTH={on:true,in:IN};
var L=%s;function gated(u){try{var x=new URL(u,location.href);return x.origin===location.origin&&L.some(function(p){return x.pathname===p})}catch(e){return false}}
var F=window.fetch;window.fetch=function(u,o){var s=typeof u==='string'?u:(u&&u.url)||'';if(!gated(s))return F.apply(this,arguments);
 if(IN){var x=new URL(s,location.href);x.searchParams.set('auth','1');s=x.pathname+x.search}
 return F.call(this,s,o).then(function(r){try{r.clone().json().then(function(j){if(j&&j.locked)lgeLocked(j.locked)}).catch(function(){})}catch(e){}return r})};
var nx=function(){return encodeURIComponent(location.pathname+location.search)};
var LS={g:function(k){try{return localStorage.getItem(k)}catch(e){return null}},s:function(k,v){try{localStorage.setItem(k,v)}catch(e){}}},DAY=new Date().toDateString();
window.lgeLocked=function(k){if(IN||document.getElementById('lgelock')||k.what==='compare'||LS.g('lgeBarX')===DAY)return;var t={rows:'You are seeing the top '+(k.shown||10)+(k.total?' of '+k.total:'')+'.',filters:'Filters and other rankings need a free account.',history:'You are seeing the last 7 days and 3 streams.',compare:'Comparing channels needs a free account.'}[k.what]||'Part of this page needs a free account.';
 var d=document.createElement('div');d.id='lgelock';d.innerHTML='<span>'+t+' <b>Sign in free</b> to see everything.</span><a href="/signin?next='+nx()+'">Sign in</a><button aria-label="Close">&times;</button>';
 d.querySelector('button').onclick=function(){d.remove();LS.s('lgeBarX',DAY)};document.body.appendChild(d)};
function btn(){var top=document.querySelector('.top .in')||document.querySelector('.top');if(!top||document.getElementById('lgeacct'))return;var a=document.createElement('a');a.id='lgeacct';
 if(top.querySelector('.sbtn,.upd'))a.className='nx';
 if(IN){a.href='/account';a.title='Your account';a.textContent='Account';fetch('/auth/me').then(function(r){return r.json()}).then(function(j){if(!j.signed_in){document.cookie='lge_in=; Max-Age=0; path=/';a.href='/signin?next='+nx();a.textContent='Sign in';return}
  if(j.picture){a.textContent='';var i=document.createElement('img');i.src=j.picture;i.alt='';i.referrerPolicy='no-referrer';a.appendChild(i)}}).catch(function(){})}
 else{a.href='/signin?next='+nx();a.setAttribute('aria-label','Sign in');a.innerHTML='<span class="t">Sign in</span><svg class="i" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>'}top.appendChild(a)}
// The sign-in popup, without wearing people out (owner, 26 Nov): never on the page someone lands on (they see the
// numbers first; Google also demotes pages that cover what a search result promised), on their second page of a
// visit or after 30 s on the first, at most once a day; never for bots and link previews.
function pop(){if(IN)return;var now=Date.now(),v={};try{v=JSON.parse(LS.g('lgeVisit')||'{}')||{}}catch(e){}
 if(!v.t||now-v.t>18e5)v={n:0};v.n=(v.n||0)+1;v.t=now;LS.s('lgeVisit',JSON.stringify(v));   // a visit: pages less than 30 min apart
 var p=location.pathname.replace(/^\\/(global|india)(?=\\/|$)/,'')||'/';
 if(/^\\/(signin|account|admin|auth|privacy|terms|embed|badge|predict)/.test(p))return;
 if(/bot|crawl|spider|slurp|facebookexternalhit|whatsapp|telegram|lighthouse|headless/i.test(navigator.userAgent)||navigator.webdriver)return;
 var due=function(){return Date.now()-(+LS.g('lgePopAt')||0)>864e5};if(!due())return;
 var w=function(){if(document.hidden){setTimeout(w,4000);return}if(due())show()};setTimeout(w,v.n>=2?1500:30000)}
function show(){if(IN||document.getElementById('lgepop'))return;LS.s('lgePopAt',String(Date.now()));
 var n=nx(),m=document.createElement('div');m.id='lgepop';m.setAttribute('role','dialog');m.setAttribute('aria-modal','true');m.setAttribute('aria-label','Sign in');
 m.innerHTML='<div class="bx"><button class="x" aria-label="Close">&times;</button><div class="h">Sign in to see the full stats</div>'
 +'<ul><li>Full rankings: top 100 and beyond, every platform and game</li><li>30-day and all-time stats for every channel, with every past stream</li><li>Compare channels side by side</li><li>The week\\'s top stats in your inbox</li></ul>'
 +'<a class="g" href="/auth/google?next='+n+'">'+%s+' Continue with Google</a><button class="later">Maybe later</button>'
 +'<div class="s">Free · <a href="/privacy">Privacy Policy</a></div></div>';
 var close=function(){m.remove()};
 m.querySelector('.x').onclick=close;m.querySelector('.later').onclick=close;m.addEventListener('click',function(e){if(e.target===m)close()});
 document.addEventListener('keydown',function k(e){if(e.key==='Escape'){close();document.removeEventListener('keydown',k)}});document.body.appendChild(m)}
function go(){var fr=false;try{fr=window.top!==window.self}catch(e){fr=true}if(fr)return;btn();pop()}   // not inside the map frame
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go()})()</script>
<style>#lgeacct{margin-left:auto;flex:none;align-self:center;background:#b6f23a;color:#0b0b12!important;font:700 13px Figtree,system-ui,sans-serif;padding:7px 13px;border-radius:8px;text-decoration:none;white-space:nowrap}
#lgeacct.nx{margin-left:8px}#lgeacct img{width:26px;height:26px;border-radius:50%%;display:block}
#lgeacct .i{display:none}
@media(max-width:600px){#lgeacct{padding:0;width:32px;height:32px;display:grid;place-items:center;border-radius:50%%}#lgeacct .t{display:none}#lgeacct .i{display:block}
 .top .in .beta,.top .in .upd{display:none!important}.top .in{gap:8px!important}}
@media(max-width:420px){.top .in .brand{font-size:15px!important;letter-spacing:.02em!important;white-space:nowrap}}#lgeacct:has(img){background:none;padding:0}
#lgelock{position:fixed;left:50%%;transform:translateX(-50%%);bottom:16px;z-index:90;display:flex;gap:12px;align-items:center;background:#14141c;border:1px solid #2a2a38;border-radius:12px;padding:10px 12px 10px 16px;box-shadow:0 10px 30px rgba(0,0,0,.5);color:#e6e6ef;font:14px/1.4 Figtree,system-ui,sans-serif;max-width:calc(100vw - 24px);box-sizing:border-box}
#lgelock a{background:#b6f23a;color:#0b0b12;font-weight:700;padding:8px 14px;border-radius:8px;text-decoration:none;white-space:nowrap}#lgelock button{background:none;border:0;color:#8d8ca3;font-size:20px;cursor:pointer;padding:0 4px}
@media(max-width:600px){#lgelock{font-size:13px;bottom:10px;width:calc(100vw - 20px)}}
#lgepop{position:fixed;inset:0;z-index:100;background:rgba(4,4,8,.72);display:flex;align-items:center;justify-content:center;padding:16px;animation:lgef .18s ease-out}
#lgepop .bx{position:relative;background:#0f0f16;border:1px solid #2a2a38;border-radius:16px;padding:26px 24px 20px;max-width:420px;width:100%%;color:#ececf3;font:15px/1.5 Figtree,system-ui,sans-serif;box-shadow:0 24px 60px rgba(0,0,0,.6)}
#lgepop .h{font-size:22px;font-weight:800;line-height:1.25;margin:0 28px 10px 0}#lgepop ul{margin:0 0 16px;padding-left:20px;color:#c9c8d6}#lgepop li{margin:4px 0}
#lgepop .g{display:flex;align-items:center;justify-content:center;gap:10px;background:#fff;color:#1f1f1f;border-radius:10px;padding:12px;font-weight:700;text-decoration:none}
#lgepop .later{display:block;width:100%%;background:none;border:0;color:#8d8ca3;font:600 14px Figtree,system-ui,sans-serif;padding:12px 0 4px;cursor:pointer}
#lgepop .x{position:absolute;top:10px;right:12px;background:none;border:0;color:#8d8ca3;font-size:24px;cursor:pointer;line-height:1}
#lgepop .s{font-size:12px;color:#8d8ca3;text-align:center;margin-top:8px}#lgepop .s a{color:#b6f23a}
@keyframes lgef{from{opacity:0}to{opacity:1}}
@media(max-width:600px){#lgepop{align-items:flex-end;padding:0}#lgepop .bx{border-radius:16px 16px 0 0;max-width:none;padding:22px 18px 16px}#lgepop .h{font-size:20px}#lgepop ul{font-size:14px}}</style>""" % (json.dumps(list(LOCKED_API)), json.dumps(G_LOGO))
