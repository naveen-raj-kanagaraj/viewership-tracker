"""The owner's admin portal at /admin: one clean place for everything the owner checks.

Sign in with Google with an admin email and it opens (no key in the address). The first time, open
/admin?key=<ADMIN_KEY> while signed in: that binds your Google account (kv admin_emails); after that the key isn't
needed. ADMIN_EMAILS in .env also works. Without sign-in configured, /admin?key=<ADMIN_KEY> still works.

Tabs: Overview (visitors now / today, sign-ups, weekly-report list, site health, trackers on air), People (every
account, search, CSV of the weekly-report list), Trackers (every tournament tracker: on air or watching, streams,
viewers, peak), and the existing pages: Traffic (/admin/visitors), Health (/admin/health), Predict & Win."""
import html
import time
from datetime import datetime, timedelta, timezone

E = html.escape
IST = timezone(timedelta(hours=5, minutes=30))


def _fmt(n) -> str:
    n = n or 0
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}K" if n >= 1e4 else f"{n:,}"


def _ago(ts) -> str:
    if not ts:
        return "-"
    s = time.time() - ts
    return "now" if s < 90 else f"{int(s // 60)} min ago" if s < 3600 else f"{int(s // 3600)} h ago" if s < 86400 else \
        datetime.fromtimestamp(ts, IST).strftime("%d %b")


CSS = """:root{color-scheme:dark;--bg:#07070b;--card:#0f0f16;--line:#1d1d28;--mut:#8d8ca3;--lime:#b6f23a;--red:#ff4d5e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#ececf3;font:14px/1.5 Figtree,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:inherit}.top{border-bottom:1px solid var(--line);background:#0a0a10;position:sticky;top:0;z-index:5}
.top .in{max-width:1160px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{color:var(--lime);font-weight:800;letter-spacing:.05em;text-decoration:none;text-transform:uppercase}.tag{font-size:11px;font-weight:700;color:#0b0b12;background:var(--lime);padding:2px 6px;border-radius:4px}
.tabs{display:flex;gap:4px;overflow-x:auto;margin-left:8px}.tabs a{padding:7px 12px;border-radius:8px;text-decoration:none;color:var(--mut);font-weight:600;white-space:nowrap}
.tabs a:hover{color:#fff;background:#15151e}.tabs a.on{color:#0b0b12;background:var(--lime)}.who{margin-left:auto;color:var(--mut);font-size:13px;display:flex;gap:10px;align-items:center}
.who img{width:26px;height:26px;border-radius:50%}main{max-width:1160px;margin:0 auto;padding:22px 20px 60px}h1{font-size:24px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 18px}
.k{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-bottom:18px}.c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.c .l{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);font-weight:700}.c b{display:block;font-size:26px;line-height:1.2;margin-top:4px}.c small{color:var(--mut)}
.c.bad{border-color:#5a1f28}.c.bad b{color:var(--red)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:820px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}.card h2{font-size:15px;margin:0 0 10px;display:flex;justify-content:space-between;align-items:center}
.card h2 a{font-size:12px;color:var(--lime);text-decoration:none;font-weight:600}table{width:100%;border-collapse:collapse}th{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--mut);text-align:left;font-weight:700;padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:middle}td.n,th.n{text-align:right;white-space:nowrap}tr:last-child td{border-bottom:0}.mut{color:var(--mut)}
.pill{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:20px}.p-live{background:var(--red);color:#fff}.p-w{background:#1d1d28;color:var(--mut)}.p-ok{background:#203214;color:var(--lime)}
.bars{display:flex;align-items:flex-end;gap:4px;height:70px}.bars div{flex:1;background:#2a3a14;border-radius:3px 3px 0 0;min-height:2px;position:relative}.bars div.t{background:var(--lime)}
.bl{display:flex;gap:4px;font-size:10px;color:var(--mut)}.bl span{flex:1;text-align:center;overflow:hidden;white-space:nowrap}
input[type=search]{background:#0b0b11;border:1px solid var(--line);color:#fff;border-radius:9px;padding:9px 12px;width:280px;max-width:100%;font:inherit}
.btn{display:inline-block;background:#15151e;border:1px solid #2a2a38;color:#fff;border-radius:9px;padding:8px 13px;text-decoration:none;font-weight:600;font-size:13px}.btn.l{background:var(--lime);color:#0b0b12;border-color:var(--lime)}
.u{display:flex;gap:10px;align-items:center}.u img,.u .ph{width:28px;height:28px;border-radius:50%;flex:none;background:#1d1d28}.ov{overflow-x:auto}
@media(max-width:600px){main{padding:16px 12px 50px}.top .in{padding:10px 12px}.c b{font-size:22px}.hide{display:none}}"""


def page(tab: str, title: str, body: str, me: dict = None, key: str = "") -> str:
    q = f"?key={E(key)}" if key else ""
    tabs = [("overview", "Overview", "/admin"), ("people", "People", "/admin/people"), ("trackers", "Trackers", "/admin/trackers"),
            ("traffic", "Traffic", "/admin/visitors"), ("health", "Health", "/admin/health"), ("predict", "Predict & Win", "/admin/predict")]
    nav = "".join(f'<a href="{u}{q}" class="{"on" if t == tab else ""}">{n}</a>' for t, n, u in tabs)
    who = ""
    if me:
        pic = f'<img src="{E(me.get("picture") or "")}" alt="" referrerpolicy="no-referrer">' if me.get("picture") else ""
        who = f'<span class="who">{pic}<span class="hide">{E(me.get("email") or "")}</span><a class="btn" href="/">Site</a></span>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{E(title)} | Admin</title><style>{CSS}</style></head><body>
<div class="top"><div class="in"><a class="brand" href="/admin{q}">letsgrowesports</a><span class="tag">ADMIN</span><nav class="tabs">{nav}</nav>{who}</div></div>
<main>{body}</main></body></html>"""


def _trackers() -> list:
    from tracker import events, store
    out = []
    with store.reading():
        c = events._db()
        for key, ev in events.events().items():
            pr = events.PRESETS.get(key, {})
            if not ev.get("active"):
                continue
            live = events._LIVE.get(key) or {}
            pk = c.execute("SELECT MAX(total) FROM ev_ticks WHERE event=?", (key,)).fetchone()[0] or 0
            ph = events._PHASE.get(key) or {}
            out.append({"key": key, "name": ev.get("name") or key, "game": pr.get("game") or "", "ended": bool(pr.get("ended")),
                        "auto": bool(pr.get("lp")), "mode": ph.get("mode") or "-", "streams": len(live),
                        "viewers": sum(int(s.get("viewers") or 0) for s in live.values()),
                        "official": sum(1 for s in live.values() if s.get("kind") == "official"), "peak": pk,
                        "start": pr.get("start"), "end": pr.get("end"), "next": events.next_start(key)})
    out.sort(key=lambda t: (t["ended"], -t["viewers"], -t["peak"]))
    return out


def _tracker_rows(ts: list) -> str:
    rows = ""
    for t in ts:
        st = ('<span class="pill p-w">ENDED</span>' if t["ended"] else '<span class="pill p-live">ON AIR</span>' if t["streams"]
              else '<span class="pill p-ok">SEARCHING</span>' if t["mode"] == "full" else '<span class="pill p-w">WATCHING OFFICIAL</span>')
        when = (f'starts {datetime.fromtimestamp(t["next"], IST).strftime("%d %b %H:%M")} IST' if t["next"] else
                (f'{t["start"]} to {t["end"]}' if t["start"] else ""))
        rows += (f'<tr><td><a href="/e/{E(t["key"])}/" target="_blank"><b>{E(t["name"])}</b></a><div class="mut">{E(t["game"])}'
                 f'{" · from Liquipedia" if t["auto"] else ""}{" · " + E(when) if when else ""}</div></td><td>{st}</td>'
                 f'<td class="n">{t["streams"]}<div class="mut">{t["official"]} official</div></td><td class="n"><b>{_fmt(t["viewers"])}</b></td>'
                 f'<td class="n">{_fmt(t["peak"])}</td></tr>')
    return (f'<table><tr><th>Tracker</th><th>Status</th><th class="n">Streams</th><th class="n">Watching</th><th class="n">Peak</th></tr>{rows}</table>'
            if rows else '<div class="mut">No trackers running.</div>')


def overview(health: dict, vis: dict, me: dict = None, key: str = "") -> str:
    from tracker import auth
    u = auth.counts() if auth.ENABLED else None
    h, s = health or {}, (health or {}).get("scan") or {}
    mem = (h.get("memory_mb") or {}).get("MemAvailable") or 0
    cards = (f'<div class="c"><div class="l">On the site now</div><b>{vis.get("active", 0)}</b><small>{vis.get("today", 0)} visitors today</small></div>'
             + (f'<div class="c"><div class="l">Accounts</div><b>{u["total"]:,}</b><small>+{u["today"]} today · +{u["week"]} in 7 days</small></div>'
                f'<div class="c"><div class="l">Weekly report list</div><b>{u["weekly"]:,}</b><small>{round(100 * u["weekly"] / u["total"]) if u["total"] else 0}% of accounts</small></div>'
                if u else '<div class="c"><div class="l">Accounts</div><b>off</b><small>sign-in keys not set</small></div>')
             + f'<div class="c {"bad" if (s.get("last_saved_min_ago") or 0) > 8 else ""}"><div class="l">Live scan</div><b>{(str(s.get("last_saved_min_ago")) + " min") if (s.get("last_saved_min_ago") or 0) < 1440 else "none yet"}</b><small>since the last save · took {s.get("last_took_s") or "-"} s</small></div>'
             + f'<div class="c {"bad" if (h.get("load") or [0])[0] > 6 else ""}"><div class="l">Server load</div><b>{(h.get("load") or [0])[0]:.1f}</b><small>{mem:,} MB memory free · {h.get("disk_free_gb", "-")} GB disk</small></div>'
             + f'<div class="c"><div class="l">Code</div><b style="font-size:20px">{E(str(h.get("code") or "-"))}</b><small>up {h.get("up_min", "-")} min</small></div>')
    signup = ""
    if u:
        mx = max([n for _, n in u["days"]] or [1]) or 1
        bars = "".join(f'<div class="{"t" if i == len(u["days"]) - 1 else ""}" style="height:{max(3, 100 * n / mx)}%" title="{d}: {n}"></div>' for i, (d, n) in enumerate(u["days"]))
        lbl = "".join(f'<span>{d if i % 3 == 0 or i == len(u["days"]) - 1 else ""}</span>' for i, (d, _) in enumerate(u["days"]))
        recent = "".join(f'<tr><td><div class="u">{_avatar(p)}<div><b>{E(p["name"] or "")}</b><div class="mut">{E(p["email"])}</div></div></div></td>'
                         f'<td class="n mut">{_ago(p["created"])}</td></tr>' for p in auth.people(limit=6))
        signup = (f'<div class="card"><h2>Sign-ups, last 14 days <a href="/admin/people{("?key=" + E(key)) if key else ""}">All people</a></h2><div class="bars">{bars}</div><div class="bl">{lbl}</div></div>'
                  f'<div class="card"><h2>Newest accounts</h2><table>{recent or "<tr><td class=mut>No accounts yet.</td></tr>"}</table></div>')
    top = "".join(f'<tr><td>{E(c or "-")}</td><td class="n">{n}</td></tr>' for c, n in (vis.get("countries") or [])[:6])
    refs = "".join(f'<tr><td>{E(r or "direct")}</td><td class="n">{n}</td></tr>' for r, n in (vis.get("refs") or [])[:6])
    body = (f'<h1>Overview</h1><p class="sub">{datetime.now(IST).strftime("%a %d %b, %I:%M %p")} IST</p><div class="k">{cards}</div>'
            f'<div class="card"><h2>Tournament trackers <a href="/admin/trackers{("?key=" + E(key)) if key else ""}">All trackers</a></h2><div class="ov">{_tracker_rows([t for t in _trackers() if not t["ended"]][:6])}</div></div>'
            f'<div class="grid"><div>{signup}</div><div><div class="card"><h2>Visitors today by country <a href="/admin/visitors{("?key=" + E(key)) if key else ""}">Traffic</a></h2><table>{top or "<tr><td class=mut>-</td></tr>"}</table></div>'
            f'<div class="card"><h2>Where they came from</h2><table>{refs or "<tr><td class=mut>-</td></tr>"}</table></div></div></div>')
    return page("overview", "Overview", body, me, key)


def _avatar(p) -> str:
    return (f'<img src="{E(p["picture"])}" alt="" referrerpolicy="no-referrer" loading="lazy">' if p.get("picture")
            else '<span class="ph"></span>')


YES = '<span class="pill p-ok">YES</span>'
NO = '<span class="mut">no</span>'


def people_page(q: str, me: dict = None, key: str = "") -> str:
    from tracker import auth
    if not auth.ENABLED:
        return page("people", "People", '<h1>People</h1><p class="sub">Sign-in is off (no Google keys in .env).</p>', me, key)
    u, rows = auth.counts(), auth.people(q, 1000)
    kq = ("&key=" + E(key)) if key else ""
    tr = "".join(f'<tr><td><div class="u">{_avatar(p)}<div><b>{E(p["name"] or "")}</b><div class="mut">{E(p["email"])}</div></div></div></td>'
                 f'<td>{YES if p["weekly"] else NO}</td><td class="hide">{E(p["region"] or "-")}</td>'
                 f'<td class="n mut">{datetime.fromtimestamp(p["created"], IST).strftime("%d %b %Y")}</td><td class="n mut hide">{_ago(p["last_seen"])}</td></tr>' for p in rows)
    body = (f'<h1>People</h1><p class="sub">{u["total"]:,} accounts · {u["weekly"]:,} want the weekly report · {u["active_today"]:,} used the site today</p>'
            f'<div class="card"><form method="get" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px">'
            f'{("<input type=hidden name=key value=" + chr(34) + E(key) + chr(34) + ">") if key else ""}<input type="search" name="q" value="{E(q)}" placeholder="Search name or email">'
            f'<button class="btn">Search</button><span style="flex:1"></span><a class="btn l" href="/admin/people.csv?weekly=1{kq}">Weekly report list (CSV)</a>'
            f'<a class="btn" href="/admin/people.csv?all=1{kq}">Everyone (CSV)</a></form>'
            f'<div class="ov"><table><tr><th>Person</th><th>Weekly</th><th class="hide">Country</th><th class="n">Joined</th><th class="n hide">Last seen</th></tr>'
            f'{tr or "<tr><td colspan=5 class=mut>No one yet.</td></tr>"}</table></div></div>')
    return page("people", "People", body, me, key)


def people_csv(weekly_only: bool) -> str:
    import csv
    import io
    from tracker import auth
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "name", "weekly_report", "country", "joined_ist", "last_seen_ist", "unsubscribe_link"])
    for p in auth.people(limit=100000):
        if weekly_only and not p["weekly"]:
            continue
        t = lambda ts: datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M") if ts else ""
        w.writerow([p["email"], p["name"], "yes" if p["weekly"] else "no", p["region"] or "", t(p["created"]), t(p["last_seen"]),
                    auth.unsub_link(p["id"])])
    return out.getvalue()


def trackers_page(me: dict = None, key: str = "") -> str:
    ts = _trackers()
    body = (f'<h1>Tournament trackers</h1><p class="sub">Off air a tracker only watches the official channels; once one is live '
            f'(or 30 minutes before the start) it searches YouTube, Kick and Twitch for every stream and counts each every 2 seconds.</p>'
            f'<div class="card ov">{_tracker_rows(ts)}</div>')
    return page("trackers", "Trackers", body, me, key)
