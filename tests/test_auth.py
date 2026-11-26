"""Sign in with Google: the OAuth flow (state, nonce, PKCE, claims), visitor vs signed-in answers of the locked APIs,
Cloudflare-safe caching, weekly-report consent, unsubscribe, export and delete. No network. Run: python3 tests/test_auth.py"""
import base64, json, os, sys, tempfile
from urllib.parse import urlparse, parse_qs
d = tempfile.mkdtemp()
os.environ.update(TRACKER_DB=d + "/t.db", USERS_DB=d + "/u.db", GOOGLE_CLIENT_ID="cid.apps.googleusercontent.com",
                  GOOGLE_CLIENT_SECRET="test-secret", SESSION_SECRET="x" * 40, ADMIN_KEY="k" * 20, SITE_URL="https://live.example.test")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import auth, ranks, web
assert auth.ENABLED
ranks.top = lambda *a, **k: {"platform": "youtube", "total": 100, "updated": 1, "rows": [{"sid": f"yt:{i}", "rank": i + 1} for i in range(100)]}
web._MEMO.clear()
c = web.app.test_client()

# visitor: top 25, says so, cacheable; no session cookie handed out
r = c.get("/api/topch?platform=youtube&metric=size")
j = r.get_json()
assert len(j["rows"]) == 25 and j["locked"]["what"] == "rows" and j["locked"]["total"] == 100, j.get("locked")
assert "public" in r.headers["Cache-Control"] and "Set-Cookie" not in r.headers
r = c.get("/api/topch?platform=youtube&metric=size&auth=1")            # asking for more without signing in
assert len(r.get_json()["rows"]) == 25 and "no-store" in r.headers["Cache-Control"]
assert c.get("/api/compare?c=yt:UCaaaaaaaaaaaaaaaaaaaaaa").get_json()["locked"]["what"] == "compare"
assert c.get("/auth/me").get_json() == {"enabled": True, "signed_in": False}

# sign in: redirect to Google with state, nonce and PKCE
r = c.get("/auth/google?next=/global/rankings")
assert r.status_code == 302 and r.location.startswith(auth.AUTH_URL)
q = {k: v[0] for k, v in parse_qs(urlparse(r.location).query).items()}
assert q["client_id"] == auth.CLIENT_ID and q["redirect_uri"] == "https://live.example.test/auth/google/callback"
assert q["scope"] == "openid email profile" and q["code_challenge_method"] == "S256" and q["state"] and q["nonce"]

def tok(**claims):
    b = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()
    full = {"iss": "https://accounts.google.com", "aud": auth.CLIENT_ID, "exp": 9e9, "nonce": q["nonce"], "sub": "1234",
            "email": "Fan@Example.com", "email_verified": True, "name": "A Fan", "picture": "https://lh3.googleusercontent.com/a/x"}
    full.update(claims)
    return {"id_token": f"{b({'alg': 'RS256'})}.{b(full)}.sig"}
import requests
sent = {}
class R:
    def __init__(self, j): self.j = j
    def json(self): return self.j
def post(url, data=None, timeout=None):
    sent.update(url=url, **data)
    return R(TOK)
requests.post = post

TOK = tok(aud="someone-else")                                               # token for another app: refused
r = c.get(f"/auth/google/callback?state={q['state']}&code=abc")
assert "e=failed" in r.location and c.get("/auth/me").get_json()["signed_in"] is False
r = c.get("/auth/google?next=/global/rankings")
q = {k: v[0] for k, v in parse_qs(urlparse(r.location).query).items()}
TOK = tok()
assert "e=failed" in c.get("/auth/google/callback?state=wrong&code=abc").location   # forged state
r = c.get("/auth/google?next=/global/rankings")
q = {k: v[0] for k, v in parse_qs(urlparse(r.location).query).items()}
TOK = tok()
r = c.get(f"/auth/google/callback?state={q['state']}&code=abc")
assert r.status_code == 302 and r.location.endswith("/global/rankings"), r.location
assert sent["url"] == auth.TOKEN_URL and sent["code_verifier"] and sent["client_secret"] == "test-secret"
assert "lge_in=1" in " ".join(r.headers.getlist("Set-Cookie"))
me = c.get("/auth/me").get_json()
assert me["signed_in"] and me["email"] == "fan@example.com" and me["weekly"] is True

# signed in: the full answer, only with auth=1, never cached
r = c.get("/api/topch?platform=youtube&metric=size&auth=1")
assert len(r.get_json()["rows"]) == 100 and "locked" not in r.get_json() and "no-store" in r.headers["Cache-Control"]
r = c.get("/api/topch?platform=youtube&metric=size")                    # the shared URL stays the visitor copy
assert len(r.get_json()["rows"]) == 25 and "public" in r.headers["Cache-Control"]

# channel trims, page script, open-redirect guard
from datetime import date, timedelta
ch = {"sid": "yt:x", "periods": {"today": {}, "7d": {"peak": 1}, "30d": {"peak": 5}, "all": {"peak": 9}},
      "days": [{"day": (date.today() - timedelta(days=i)).isoformat()} for i in range(30)]}
t = auth.trim_channel(ch)
assert len(t["days"]) == 7 and t["periods"]["30d"] is None and t["periods"]["7d"] == {"peak": 1} and t["locked"]
assert auth._safe_next("//evil.com") == "/" and auth._safe_next("/global/ch/yt:x") == "/global/ch/yt:x"
assert "lge_in" in auth.page_js() and "/api/topch" in auth.page_js()

# admin portal: 404 for a signed-in non-admin; the key once binds the account; then it opens without the key
assert c.get("/admin").status_code == 404 and c.get("/admin/people").status_code == 404
r = c.get("/admin?key=" + "k" * 20)
assert r.status_code == 302 and r.location.endswith("/admin")
for path, want in (("/admin", "Overview"), ("/admin/people", "fan@example.com"), ("/admin/trackers", "Tournament trackers"),
                   ("/admin/visitors", "lgeadm"), ("/admin/health", "lgeadm"), ("/admin/people.csv?weekly=1", "fan@example.com")):
    r = c.get(path)
    assert r.status_code == 200 and want in r.get_data(as_text=True), path
    assert "no-store" in r.headers["Cache-Control"], path
assert "unsubscribe_link" in c.get("/admin/people.csv?all=1").get_data(as_text=True)
other = web.app.test_client()
assert other.get("/admin").status_code == 404 and other.get("/admin/people.csv?weekly=1").status_code == 404
assert other.get("/admin?key=wrong").status_code == 404
assert other.get("/admin?key=" + "k" * 20).status_code == 302              # not signed in: sign in first
assert "lgeadm" not in other.get("/admin/health").get_data(as_text=True)    # public health page stays plain

# account: weekly list, unsubscribe link, export, delete
assert [e for _, e, _ in auth.weekly_list()] == ["fan@example.com"]
uid = auth.weekly_list()[0][0]
assert c.get(f"/auth/unsub?u={uid}&t=bad").status_code == 400
assert c.get(f"/auth/unsub?u={uid}&t={auth.unsub_token(uid)}").status_code == 200 and auth.weekly_list() == []
assert json.loads(c.get("/auth/export").data)["email"] == "fan@example.com"
# signing in again after unsubscribing keeps you unsubscribed
r = c.get("/auth/google?next=/")
q = {k: v[0] for k, v in parse_qs(urlparse(r.location).query).items()}
TOK = tok()
c.get(f"/auth/google/callback?state={q['state']}&code=abc")
assert c.get("/auth/me").get_json()["weekly"] is False
# the visitor popup is in every page's script, with Google straight from it
js = auth.page_js()
assert "lgepop" in js and "/auth/google?next=" in js and "sessionStorage" in js
c.post("/auth/delete")
assert c.get("/auth/me").get_json()["signed_in"] is False
assert len(c.get("/api/topch?platform=youtube&metric=size&auth=1").get_json()["rows"]) == 25
print("AUTH OK")
