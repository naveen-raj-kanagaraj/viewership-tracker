"""Predict & Win (BMIC 2026): BMSD archive, question set, countries x2, feedback privacy, owner dashboard."""
import os, sys, tempfile, json, time
T = tempfile.mkdtemp(); os.environ["TRACKER_DB"] = T + "/t.db"; os.environ["ADMIN_KEY"] = "k" * 20
sys.path.insert(0, os.getcwd())
from tracker import store
c = store.conn()
# fake an old BMSD game
c.executescript("""CREATE TABLE pw_players (id INTEGER PRIMARY KEY AUTOINCREMENT, handle TEXT UNIQUE NOT NULL, name TEXT NOT NULL, token_hash TEXT, created REAL NOT NULL, hidden INTEGER DEFAULT 0);
CREATE TABLE pw_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, tag TEXT, title TEXT NOT NULL, day INTEGER DEFAULT 0, style TEXT DEFAULT 'buttons', options TEXT NOT NULL, close_ts REAL NOT NULL, locked INTEGER DEFAULT 0, answer TEXT, void INTEGER DEFAULT 0, meta TEXT DEFAULT '{}', sort INTEGER DEFAULT 0, created REAL NOT NULL, resolved_ts REAL);
CREATE TABLE pw_picks (player_id INTEGER NOT NULL, qid INTEGER NOT NULL, option TEXT NOT NULL, ts REAL NOT NULL, PRIMARY KEY (player_id, qid));""")
c.execute("INSERT INTO pw_players (handle,name,token_hash,created) VALUES ('old','old','x',1)")
c.execute("INSERT INTO pw_questions (kind,tag,title,options,close_ts,created) VALUES ('team','CHAMPION','Who will win the BMSD 2026 Grand Finals?','[\"A\",\"B\"]',1,1)")
c.execute("INSERT INTO pw_picks VALUES (1,1,'A',1)"); c.commit()
from tracker import predict
qs = predict.questions()
print([ (q["kind"], q["style"], q["title"][:30]) for q in qs])
assert len(qs) == 9 and c.execute("SELECT COUNT(*) FROM pw_bmsd_picks").fetchone()[0] == 1
assert store.kv_get("pw_bmsd_crowd")
import tracker.predict as P
P.MAX_PER_NET = 5
now = qs[0]["close_ts"] - 3600
tok = predict.join("@fan_1", "Fan", True, "1.2.3.4")["token"]
byk = {q["tag"]: q for q in qs}
picks = {str(byk["CHAMPION"]["id"]): "DRX", str(byk["PMGC"]["id"]): ["DRX", "iQOO SOUL"], str(byk["TOP 3"]["id"]): ["DRX", "VALOR", "FOCUS"],
         str(byk["PMGC COUNTRIES"]["id"]): "India + India", str(byk["TOURNAMENT MVP"]["id"]): "Nakul", str(byk["BEST IGL"]["id"]): "Goblin",
         str(byk["BEST CLUTCH"]["id"]): "Jonathan", str(byk["PEAK VIEWERS"]["id"]): byk["PEAK VIEWERS"]["options"][3],
         str(byk["FEEDBACK"]["id"]): "Add a dark mode toggle please"}
print(predict.submit_all(tok, picks, now=now, ip="5.6.7.8"))
b = predict.board(now=now)
fbq = [q for q in b["questions"] if q["kind"] == "feedback"][0]
assert fbq["pct"] == {}
predict.update_question(byk["PMGC COUNTRIES"]["id"], "answer", "India + India")
predict.update_question(byk["CHAMPION"]["id"], "answer", "DRX")
m = predict.me(tok); print(m["pts"])
assert m["pts"][str(byk["PMGC COUNTRIES"]["id"])] > 0
from tracker import predictadmin
h = predictadmin.build_html("k"*20)
assert "5.6.7.8" in h or "1.2.3.4" in h and "Add a dark mode" in h
print(predictadmin.csv_text()[:300])
from tracker.web import app
cl = app.test_client()
assert cl.get("/admin/predict?key=bad").status_code == 404
assert cl.get("/admin/predict?key=" + "k"*20).status_code == 200
r = cl.post("/admin/predict/act", data={"key": "k"*20, "action": "lock_at", "value": "2026-10-31T12:00"}); print(r.status_code, r.headers.get("Location"))
assert cl.get("/predict").status_code == 200 and cl.get("/predict/bmsd").status_code == 200
assert cl.get("/predict/api/board").status_code == 200
print("PREDICT OK")
