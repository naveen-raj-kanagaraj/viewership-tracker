"""PMGC 2026 Gauntlet Predict & Win: sign-in required, all 8 answers required and valid, edits until the lock,
one entry per Google account and per Instagram ID, scoring with the underdog bonus, ties, results from the admin
form, the routes. No network. Run: python3 tests/test_pmgc_game.py"""
import json, os, sys, tempfile, time
d = tempfile.mkdtemp()
os.environ.update(TRACKER_DB=d + "/t.db", USERS_DB=d + "/u.db", GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="s",
                  SESSION_SECRET="x" * 40, ADMIN_KEY="k" * 20)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import pmgc, auth, web
T = pmgc.TEAM_NAMES
assert len(T) == 16 and len(set(T)) == 16 and "Team SouL" in T and len(pmgc.QUESTIONS) == 8
assert pmgc.PEAKS[4] == "650K-750K" and pmgc.QMAP["q7"]["options"][-1] == "12"
pmgc.save(lock=time.time() + 3600)

def picks(top6, first, soul, most, three, peak, n, top3):
    return {"q1": top6, "q2": first, "q3": soul, "q4": most, "q5": three, "q6": peak, "q7": n, "q8": top3}
A = picks(T[:6], T[0], "Yes", T[1], "No", "550K-650K", "8", [T[0], T[1], T[2]])
U1 = {"id": 1, "email": "a@x.com", "name": "Ann"}
U2 = {"id": 2, "email": "b@x.com", "name": "Bob"}
U3 = {"id": 3, "email": "c@x.com", "name": "Cy"}

def err(fn, *a):
    try:
        fn(*a)
    except pmgc.GameError as e:
        return str(e)
    raise AssertionError("expected an error")
assert "Sign in" in err(pmgc.submit, None, "ann", "Ann", A)
assert "Instagram" in err(pmgc.submit, U1, "a b!", "Ann", A)
assert "pick exactly 6" in err(pmgc.submit, U1, "ann", "Ann", {**A, "q1": T[:5]})
assert "pick exactly 6" in err(pmgc.submit, U1, "ann", "Ann", {**A, "q1": T[:5] + [T[0]]})
assert "choose an answer" in err(pmgc.submit, U1, "ann", "Ann", {**A, "q6": "2M"})
assert "pick exactly 3" in err(pmgc.submit, U1, "ann", "Ann", {**A, "q8": [T[0], T[0], T[1]]})
assert "choose an answer" in err(pmgc.submit, U1, "ann", "Ann", {k: v for k, v in A.items() if k != "q3"})
assert pmgc.submit(U1, "@Ann.Plays", "Ann", A) == {"ok": True, "edited": False}
assert pmgc.entry(1)["handle"] == "ann.plays"
assert pmgc.submit(U1, "ann.plays", "Ann P", {**A, "q3": "No"})["edited"] is True       # edits until the lock
assert pmgc.entry(1)["picks"]["q3"] == "No"
assert "already playing" in err(pmgc.submit, U2, "https://instagram.com/ann.plays/", "Bob", A)
B = picks(T[:5] + [T[6]], T[1], "Yes", T[1], "Yes", "450K-550K", "9", [T[1], T[0], T[2]])
pmgc.submit(U2, "bob", "Bob", B)
pmgc.submit(U3, "cy", "Cy", picks(T[10:16], T[5], "No", T[5], "No", "1M+", "3", [T[5], T[6], T[7]]))
st = pmgc.state(U1)
assert st["me"]["handle"] == "ann.plays" and st["me"]["picks"]["q3"] == "No" and not st["closed"] and st["crowd"] == {}
assert len(st["teams"]) == 16 and st["teams"][0]["logo"] == ""            # no logo yet: initials on the page

# results: Ann 6/6 finalists, #1, top 3 exact; Bob 5/6, 3+ dinners, #1 slot wrong
pmgc.save(lock=time.time() - 1, answers={"q1": T[:6], "q2": T[0], "q3": "Yes", "q4": [T[1], T[5]], "q5": "Yes",
                                          "q6": "550K-650K", "q7": "8", "q8": [T[0], T[1], T[2]]})
assert pmgc.closed()
assert "locked" in err(pmgc.submit, U1, "ann.plays", "Ann", A)
es = {e["handle"]: e for e in pmgc.admin_entries()}
a, b, c = es["ann.plays"], es["bob"], es["cy"]
assert a["pts"] > b["pts"] > c["pts"] > 0, (a["pts"], b["pts"], c["pts"])
assert c["right"] == 1                                                     # Cy: only q4 (a tie, either team counts)
q2 = 100 + 100 * (1 - 1 / 3)                                               # Ann alone called the #1
assert a["pts"] >= round(q2)
pmgc.save(show_lb=True)
lb = pmgc.board()["leaderboard"]
assert [r["handle"] for r in lb] == ["ann.plays", "bob", "cy"] and lb[0]["rank"] == 1
assert "ann.plays" in pmgc.csv_text() and "a@x.com" in pmgc.csv_text()
pmgc.entry_action(3, "hide")
assert [r["handle"] for r in pmgc.board(time.time() + 10)["leaderboard"]] == ["ann.plays", "bob"]
assert pmgc.peak_bucket(612000) == "550K-650K" and pmgc.peak_bucket(1_200_000) == "1M+" and pmgc.peak_bucket(980000) == "950K-1M"
assert pmgc._file_url("Team SouL 2023 allmode.png").startswith("https://liquipedia.net/commons/images/")

# admin results form
class F(dict):
    def getlist(self, k):
        v = self.get(k, [])
        return v if isinstance(v, list) else [v]
pmgc.set_answers(F(q1=T[:6], q2=T[3], q3="No", q4=[T[2]], q5="No", q6="1M+", q7="5", q8_0=T[0], q8_1=T[1], q8_2=T[2]))
assert pmgc.settings()["answers"]["q2"] == T[3] and pmgc.settings()["answers"]["q8"] == T[:3]
try:
    pmgc.set_answers(F(q1=T[:4]))
    raise AssertionError
except pmgc.GameError:
    pass

# routes: page, state (no-store), submit needs sign-in, admin pages
cl = web.app.test_client()
r = cl.get("/predict/pmgc")
assert r.status_code == 200 and b"Predict" in r.data
r = cl.get("/predict/pmgc/api/state")
j = r.get_json()
assert r.headers["Cache-Control"] == "no-store" and j["me"] is None and j["auth"] is True and len(j["questions"]) == 8
pmgc.save(lock=time.time() + 3600)
r = cl.post("/predict/pmgc/api/submit", json={"handle": "x", "picks": A})
assert r.status_code == 401
assert cl.get("/pmgc/logo/nope").status_code == 404 and cl.get("/pmgc/logo/team-soul").status_code == 404
os.makedirs(pmgc.LOGO_DIR, exist_ok=True)
pmgc._save_logo("team-soul", b"\x89PNG" + b"0" * 300, ".png")
r = cl.get("/pmgc/logo/team-soul")
assert r.status_code == 200 and r.mimetype == "image/png" and "86400" in r.headers["Cache-Control"]
assert pmgc.teams()[14]["logo"].startswith("/pmgc/logo/team-soul?v=")
os.remove(pmgc.logo_file("team-soul"))
k = "k" * 20
assert cl.get("/admin/pmgc").status_code == 404 and cl.get(f"/admin/pmgc?key={k}").status_code == 200
assert b"PMGC Gauntlet" in cl.get(f"/admin/pmgc?key={k}").data
r = cl.post("/admin/pmgc/act", data={"key": k, "action": "settings", "lock": "2026-11-26T17:00", "prize": "UC for the top 3", "show_lb": "1"})
assert r.status_code == 302 and pmgc.settings()["prize"] == "UC for the top 3"
assert abs(pmgc.settings()["lock"] - 1795692600) < 1                       # 26 Nov 2026 17:00 IST
assert cl.get(f"/admin/pmgc.csv?key={k}").status_code == 200
print("PMGC GAME OK")
