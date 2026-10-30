"""Owner-only Predict & Win dashboard: /admin/predict?key=<ADMIN_KEY>.

Players (with IP addresses), picks, crowd split per question, feedback, and the controls to set answers, change
the lock time, show the leaderboard and remove fake accounts. Every change is a POST to /admin/predict/act.
"""
import csv
import html
import io
import json
import time
from collections import Counter
from datetime import datetime

from tracker import predict, store

E = lambda x: html.escape(str(x if x is not None else ""), quote=True)


def _t(ts):
    return datetime.fromtimestamp(ts, predict.IST).strftime("%d %b %I:%M %p") if ts else "-"


def _players():
    with store._lock:
        rows = [dict(r) for r in predict._db().execute(
            "SELECT p.id, p.handle, p.name, p.created, p.hidden, p.ip, p.last_ip, p.last_ts, p.token_hash IS NOT NULL bound, "
            "(SELECT COUNT(*) FROM pw_picks k WHERE k.player_id=p.id) picks, "
            "(SELECT MIN(ts) FROM pw_picks k WHERE k.player_id=p.id) sub_ts FROM pw_players p ORDER BY p.created DESC")]
    return rows


def data() -> dict:
    qs = predict.questions()
    qmap = {q["id"]: q for q in qs}
    players, sc, st, _ = predict._scores()
    rows = _players()
    since = store.kv_get("pw_bmsd_archived") or 0
    ipc = Counter(r["ip"] for r in rows if r.get("ip"))
    for r in rows:
        r["pts"] = sc.get(r["id"], {}).get("all", [0, 0])[0]
        r["same_ip"] = ipc.get(r.get("ip"), 0) if r.get("ip") else 0
    fbq = [q for q in qs if q["kind"] == "feedback"]
    fb = []
    if fbq:
        with store._lock:
            fb = [dict(r) for r in predict._db().execute(
                "SELECT p.handle, p.ip, k.option, k.ts FROM pw_picks k JOIN pw_players p ON p.id=k.player_id "
                "WHERE k.qid=? ORDER BY k.ts DESC", (fbq[0]["id"],))]
    return {"qs": qs, "st": st, "rows": rows, "fb": fb, "since": since, "settings": predict.settings(),
            "ranked": predict._ranked(players, sc, "all")[:25], "qmap": qmap}


def _qblock(q, s, key) -> str:
    n = (s or {}).get("n", 0)
    inc = (s or {}).get("inc", {})
    names = (s or {}).get("names", {})
    split = sorted(inc.items(), key=lambda kv: -kv[1])[:30]
    bars = "".join(f'<div class="b"><span class="k">{E(names.get(k, k))}</span><span class="t"><i style="width:{100 * v / max(n, 1):.1f}%"></i></span>'
                   f'<span class="v">{v:,}<small>{100 * v / max(n, 1):.0f}%</small></span></div>' for k, v in split)
    ans = ", ".join(predict.ans_list(q))
    if q["kind"] == "feedback":
        form = '<div class="e">Not scored. Responses are listed under Feedback.</div>'
    else:
        if q["kind"] == "multi":
            inp = (f'<select name="value" multiple size="6">' +
                   "".join(f'<option {"selected" if o in predict.ans_list(q) else ""}>{E(o)}</option>' for o in q["options"]) + "</select>"
                   f'<span class="e">Hold Ctrl / Cmd to pick {q["meta"].get("pick")}.</span>')
        elif q["kind"] == "text":
            inp = f'<input name="value" value="{E(ans)}" placeholder="Accepted spellings, comma separated">'
        else:
            inp = '<select name="value"><option value="">Pick the answer</option>' + "".join(
                f'<option {"selected" if o == q.get("answer") else ""}>{E(o)}</option>' for o in q["options"]) + "</select>"
        form = (f'<form method="post" action="/admin/predict/act" class="f"><input type="hidden" name="key" value="{E(key)}">'
                f'<input type="hidden" name="qid" value="{q["id"]}"><input type="hidden" name="action" value="answer">{inp}'
                f'<button>Set answer</button></form>'
                f'<form method="post" action="/admin/predict/act" class="f"><input type="hidden" name="key" value="{E(key)}">'
                f'<input type="hidden" name="qid" value="{q["id"]}"><button name="action" value="unresolve" class="g">Clear answer</button>'
                f'<button name="action" value="{"unvoid" if q["void"] else "void"}" class="g">{"Un-cancel" if q["void"] else "Cancel question"}</button></form>')
    return (f'<div class="c q"><div class="qh"><span class="tag">{E(q["tag"])}</span><b>{E(q["title"])}</b>'
            f'<span class="e">{n:,} answered · locks {_t(q["close_ts"])} IST{" · CANCELLED" if q["void"] else ""}</span></div>'
            f'{"<div class=ans>Answer: " + E(ans) + "</div>" if ans else ""}'
            f'{bars if q["kind"] != "feedback" else ""}{form}</div>')


def _warn(r) -> str:
    return f'<br><b class="warn">{r["same_ip"]} accounts on this IP</b>' if r["same_ip"] > 1 else ""


def build_html(key: str, flt: str = "") -> str:
    d = data()
    s = d["settings"]
    rows = d["rows"]
    joined = [r for r in rows if r["created"] >= d["since"]]
    subm = [r for r in rows if r["picks"]]
    lock = min((q["close_ts"] for q in d["qs"]), default=0)
    lock_val = datetime.fromtimestamp(lock, predict.IST).strftime("%Y-%m-%dT%H:%M") if lock else ""
    f = (flt or "").strip().lower()
    shown = [r for r in rows if not f or f in (r["handle"] or "") or f in (r["ip"] or "") or f in (r["last_ip"] or "") or f in (r["name"] or "").lower()]
    shown = sorted(shown, key=lambda r: (-(r["picks"] > 0), -(r["sub_ts"] or 0), -r["created"]))[:400]
    K = E(key)
    act = lambda pid, a, label, cls="g": (f'<form method="post" action="/admin/predict/act" style="display:inline"><input type="hidden" name="key" value="{K}">'
                                          f'<input type="hidden" name="pid" value="{pid}"><button name="action" value="{a}" class="{cls}">{label}</button></form>')
    prow = "".join(
        f'<tr class="{"hid" if r["hidden"] else ""}"><td><a href="https://www.instagram.com/{E(r["handle"])}/" target="_blank" rel="noopener">@{E(r["handle"])}</a>'
        f'{"<br><small>" + E(r["name"]) + "</small>" if r["name"] and r["name"] != r["handle"] else ""}</td>'
        f'<td>{_t(r["created"])}</td><td>{_t(r["sub_ts"]) if r["sub_ts"] else "-"}</td><td class="n">{r["picks"]}</td><td class="n">{r["pts"]}</td>'
        f'<td class="ip">{E(r["ip"] or "-")}{"<br><small>now " + E(r["last_ip"]) + "</small>" if r["last_ip"] and r["last_ip"] != r["ip"] else ""}'
        f'{_warn(r)}</td>'
        f'<td>{act(r["id"], "unhide" if r["hidden"] else "hide", "Restore" if r["hidden"] else "Remove")}{act(r["id"], "release", "Release")}</td></tr>'
        for r in shown)
    fb = "".join(f'<tr><td>@{E(x["handle"])}</td><td>{E(x["option"])}</td><td class="ip">{E(x["ip"] or "-")}</td><td>{_t(x["ts"])}</td></tr>' for x in d["fb"])
    lb = "".join(f'<tr><td class="n">{r["rank"]}</td><td>@{E(r["handle"])}</td><td class="n">{r["pts"]}</td><td class="n">{r["correct"]}</td></tr>'
                 for r in d["ranked"] if r["pts"] > 0) or '<tr><td colspan="4" class="e">No points yet: set answers after the finals.</td></tr>'
    qb = "".join(_qblock(q, d["st"].get(q["id"]), key) for q in d["qs"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Predict & Win | owner</title>
<style>:root{{color-scheme:dark;--bg:#0b0b12;--c:#13131c;--l:#262636;--m:#8d8ca3;--i:#eeeef5;--a:#b6f23a}}
@media(prefers-color-scheme:light){{:root{{color-scheme:light;--bg:#f4f4f8;--c:#fff;--l:#d9d9e3;--m:#5d5c70;--i:#14141e;--a:#4d8a00}}}}
body{{margin:0;background:var(--bg);color:var(--i);font:14px/1.45 system-ui,sans-serif}}main{{max-width:1150px;margin:0 auto;padding:18px 14px 50px}}
h1{{font-size:24px;margin:0}}h2{{font-size:16px;margin:22px 0 8px}}.e,small{{color:var(--m);font-size:12px}}a{{color:var(--a)}}
.k4{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}}.c{{background:var(--c);border:1px solid var(--l);padding:12px;min-width:0}}
.k4 b{{display:block;font-size:28px}}.k4 span{{color:var(--m);font-size:12px}}
.qs{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.qh{{display:flex;flex-direction:column;gap:2px;margin-bottom:8px}}
.tag{{font-size:11px;letter-spacing:.06em;color:#ff4d5e;font-weight:700}}.ans{{color:var(--a);font-weight:600;margin-bottom:6px}}
.b{{display:grid;grid-template-columns:130px minmax(0,1fr) 70px;gap:8px;align-items:center;font-size:12px;padding:2px 0}}.k{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.t{{background:var(--l);height:8px}}.t i{{display:block;height:100%;background:var(--a)}}.v{{text-align:right}}.v small{{margin-left:4px}}
.f{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;align-items:center}}input,select,button{{font:inherit;color:var(--i);background:var(--bg);border:1px solid var(--l);padding:6px 8px}}
select[multiple]{{min-width:220px}}button{{background:var(--a);color:#0a0a14;border:0;font-weight:700;cursor:pointer}}button.g{{background:transparent;color:var(--i);border:1px solid var(--l);font-weight:500;font-size:12px;padding:4px 8px}}
.tw{{overflow-x:auto;border:1px solid var(--l)}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--l);vertical-align:top}}
th{{color:var(--m);font-weight:600;font-size:12px;position:sticky;top:0;background:var(--c)}}td.n{{text-align:right}}.ip{{font-family:ui-monospace,monospace;font-size:12px;word-break:break-all}}
.warn{{color:#ff8a3d;font-size:11px}}tr.hid td{{opacity:.45}}
@media(max-width:760px){{.k4{{grid-template-columns:1fr 1fr}}.qs{{grid-template-columns:1fr}}}}</style></head><body><main>
<h1>Predict &amp; Win: BMIC 2026</h1><div class="e">Owner only. IST times. <a href="/admin/predict?key={K}">Refresh</a> · <a href="/admin/predict.csv?key={K}">Download players + picks (CSV)</a> · <a href="/predict" target="_blank">Public page</a> · <a href="/predict/bmsd" target="_blank">BMSD results</a></div>
<div class="k4"><div class="c"><b>{len(subm):,}</b><span>submitted picks</span></div><div class="c"><b>{len(joined):,}</b><span>joined for BMIC</span></div>
<div class="c"><b>{len(rows):,}</b><span>players, all time (BMSD + BMIC)</span></div><div class="c"><b>{len(d['fb']):,}</b><span>feedback responses</span></div></div>
<h2>Settings</h2><div class="c">
<form method="post" action="/admin/predict/act" class="f"><input type="hidden" name="key" value="{K}"><input type="hidden" name="action" value="lock_at">
<label>Picks lock at (IST) <input type="datetime-local" name="value" value="{lock_val}"></label><button>Save lock time</button></form>
<form method="post" action="/admin/predict/act" class="f"><input type="hidden" name="key" value="{K}">
<button name="action" value="lock_now" class="g">Lock all picks now</button>
<button name="action" value="{'lb_off' if s.get('show_leaderboard') else 'lb_on'}" class="g">{'Hide' if s.get('show_leaderboard') else 'Show'} public leaderboard</button></form>
<form method="post" action="/admin/predict/act" class="f"><input type="hidden" name="key" value="{K}"><input type="hidden" name="action" value="prize">
<label>Prize line <input name="value" size="60" value="{E(s.get('prize'))}"></label><button>Save</button></form></div>
<h2>Questions and crowd split</h2><div class="qs">{qb or '<div class="e">No questions yet.</div>'}</div>
<h2>Leaderboard (top 25)</h2><div class="tw"><table><tr><th>#</th><th>Player</th><th>Points</th><th>Correct</th></tr>{lb}</table></div>
<h2>Feedback ({len(d['fb']):,})</h2><div class="tw" style="max-height:480px"><table><tr><th>Player</th><th>Feedback</th><th>IP</th><th>When</th></tr>{fb or '<tr><td colspan="4" class="e">None yet.</td></tr>'}</table></div>
<h2>Players</h2><form method="get" action="/admin/predict" class="f"><input type="hidden" name="key" value="{K}"><input name="q" value="{E(flt)}" placeholder="Search handle, name or IP"><button>Search</button></form>
<div class="e" style="margin:6px 0">Showing {len(shown):,} of {len(rows):,} (submitted first). "Remove" hides a fake account from the game and leaderboard; "Release" lets the handle sign in again on another device.</div>
<div class="tw" style="max-height:640px"><table><tr><th>Instagram</th><th>Joined</th><th>Submitted</th><th>Picks</th><th>Pts</th><th>IP</th><th></th></tr>{prow}</table></div>
</main></body></html>"""


def act(form) -> None:
    a = form.get("action", "")
    if a in ("answer", "unresolve", "void", "unvoid"):
        q = predict.get_question(int(form.get("qid")))
        if a == "answer":
            v = form.getlist("value") if q["kind"] == "multi" else form.get("value", "")
            if q["kind"] == "multi" and len(v) != int(q["meta"].get("pick") or 0):
                raise predict.GameError(f"Pick exactly {q['meta'].get('pick')} for this question.")
            predict.update_question(q["id"], "answer", v)
        else:
            predict.update_question(q["id"], a)
    elif a in ("hide", "unhide", "release"):
        predict.player_action(int(form.get("pid")), a)
    elif a == "lock_at":
        ts = datetime.strptime(form.get("value", ""), "%Y-%m-%dT%H:%M").replace(tzinfo=predict.IST).timestamp()
        for q in predict.questions():
            predict.update_question(q["id"], "close_ts", ts)
            if q["locked"] and ts > time.time() and not q["answer"]:
                with store._lock:
                    predict._db().execute("UPDATE pw_questions SET locked=0 WHERE id=?", (q["id"],))
                    predict._db().commit()
    elif a == "lock_now":
        for q in predict.questions():
            predict.update_question(q["id"], "lock")
    elif a in ("lb_on", "lb_off"):
        predict.save_settings(show_leaderboard=(a == "lb_on"))
    elif a == "prize":
        predict.save_settings(prize=form.get("value", "").strip()[:200])
    else:
        raise predict.GameError("Unknown action.")
    predict._bust()


def csv_text() -> str:
    qs = predict.questions()
    _, sc, _, _ = predict._scores()
    with store._lock:
        picks = predict._db().execute("SELECT player_id, qid, option FROM pw_picks").fetchall()
    by = {}
    for k in picks:
        by.setdefault(k["player_id"], {})[k["qid"]] = k["option"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["instagram", "name", "joined_ist", "submitted_ist", "ip", "last_ip", "removed", "points"] + [q["tag"] or q["title"] for q in qs])
    for r in _players():
        if not r["picks"]:
            continue
        mine = by.get(r["id"], {})
        w.writerow([r["handle"], r["name"], _t(r["created"]), _t(r["sub_ts"]), r["ip"] or "", r["last_ip"] or "", r["hidden"],
                    sc.get(r["id"], {}).get("all", [0, 0])[0]] +
                   [", ".join(json.loads(mine[q["id"]])) if q["kind"] == "multi" and q["id"] in mine else mine.get(q["id"], "") for q in qs])
    return out.getvalue()
