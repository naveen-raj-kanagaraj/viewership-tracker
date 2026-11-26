"""The owner's admin portal at /admin: one clean place for everything the owner checks.

Sign in with Google with an admin email and it opens (no key in the address). The first time, open
/admin?key=<ADMIN_KEY> while signed in: that binds your Google account (kv admin_emails); after that the key isn't
needed. ADMIN_EMAILS in .env also works. Without sign-in configured, /admin?key=<ADMIN_KEY> still works.

Tabs: Overview (visitors now / today, sign-ups, weekly-report list, site health, trackers on air), People (every
account, search, CSV of the weekly-report list), Trackers (every tournament tracker: on air or watching, streams,
viewers, peak), and the existing pages: Traffic (/admin/visitors), Health (/admin/health), Predict & Win."""
import html
import re
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
.btn{display:inline-block;background:#15151e;border:1px solid #2a2a38;color:#fff;border-radius:9px;padding:8px 13px;text-decoration:none;font-weight:600;font-size:13px}.btn.l{background:var(--lime);color:#0b0b12;border-color:var(--lime)}button.btn{cursor:pointer;font-family:inherit}.btn.bad{color:#ff8a95;border-color:#5a1f28}.msg{background:#16210a;border:1px solid #3d5a12;color:#d9f99d;border-radius:10px;padding:10px 14px;margin:0 0 14px}
.u{display:flex;gap:10px;align-items:center}.u img,.u .ph{width:28px;height:28px;border-radius:50%;flex:none;background:#1d1d28}.ov{overflow-x:auto}
@media(max-width:600px){main{padding:16px 12px 50px}.top .in{padding:10px 12px}.c b{font-size:22px}.hide{display:none}.k{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.c{padding:12px}}"""


def page(tab: str, title: str, body: str, me: dict = None, key: str = "") -> str:
    q = f"?key={E(key)}" if key else ""
    tabs = [("overview", "Overview", "/admin"), ("people", "People", "/admin/people"), ("trackers", "Trackers", "/admin/trackers"),
            ("traffic", "Traffic", "/admin/visitors"), ("health", "Health", "/admin/health"), ("pmgc", "PMGC Predict", "/admin/pmgc"), ("predict", "BMIC Predict", "/admin/predict")]
    nav = "".join(f'<a href="{u}{q}" class="{"on" if t == tab else ""}">{n}</a>' for t, n, u in tabs)
    who = ""
    if me:
        pic = f'<img src="{E(me.get("picture") or "")}" alt="" referrerpolicy="no-referrer">' if me.get("picture") else ""
        who = f'<span class="who" title="{E(me.get("email") or "")}">{pic}<a class="btn" href="/">Site</a></span>'
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
        rows += (f'<tr><td><a href="/admin/trackers/{E(t["key"])}"><b>{E(t["name"])}</b></a><div class="mut">{E(t["game"])}'
                 f'{" · from Liquipedia" if t["auto"] else ""}{" · " + E(when) if when else ""}</div></td><td>{st}</td>'
                 f'<td class="n">{t["streams"]}<div class="mut">{t["official"]} official</div></td><td class="n"><b>{_fmt(t["viewers"])}</b></td>'
                 f'<td class="n">{_fmt(t["peak"])}</td></tr>')
    return (f'<table><tr><th>Tracker</th><th>Status</th><th class="n">Streams</th><th class="n">Watching</th><th class="n">Peak</th></tr>{rows}</table>'
            if rows else '<div class="mut">No trackers running.</div>')


def _bars(items: list, hl_last: bool = True, every: int = 3, fmt=str) -> str:
    """[(label, value)] as a small bar chart (labels every few bars)."""
    if not items:
        return '<div class="mut">No data yet.</div>'
    mx = max([v for _, v in items] or [1]) or 1
    b = "".join(f'<div class="{"t" if hl_last and i == len(items) - 1 else ""}" style="height:{max(3, 100 * v / mx)}%" title="{E(str(l))}: {fmt(v)}">'
                f'<i>{fmt(v) if v else ""}</i></div>' for i, (l, v) in enumerate(items))
    lb = "".join(f'<span>{E(str(l)) if i % every == 0 or i == len(items) - 1 else ""}</span>' for i, (l, _) in enumerate(items))
    return f'<div class="bars">{b}</div><div class="bl">{lb}</div>'


def _rows(pairs: list, empty="-", pct_of: int = 0) -> str:
    if not pairs:
        return f'<tr><td class="mut">{empty}</td></tr>'
    return "".join(f'<tr><td>{E(str(k or "-"))}</td><td class="n"><b>{v:,}</b>{f" <span class=mut>{round(100 * v / pct_of)}%</span>" if pct_of else ""}</td></tr>'
                   for k, v in pairs)


def _pages(pairs: list) -> list:
    """Page paths as the owner reads them: channel pages by the channel's name."""
    from urllib.parse import unquote
    sids = {}
    for p, _ in pairs:
        m = re.search(r"/ch/([^/?#]+)", unquote(p or ""))
        if m:
            sids[p] = m.group(1)
    names = {}
    if sids:
        try:
            from tracker import scene, store
            with store.reading():
                q = ",".join("?" * len(set(sids.values())))
                names = {r[0]: r[1] for r in scene._db().execute(f"SELECT sid, name FROM sc_channels WHERE sid IN ({q})", list(set(sids.values())))}
        except Exception:
            names = {}
    out = []
    for p, n in pairs:
        sid = sids.get(p)
        out.append((f"Channel: {names[sid]}" if sid and names.get(sid) else unquote(p or "/"), n))
    return out


def _card(label, value, small="", bad=False) -> str:
    return f'<div class="c{" bad" if bad else ""}"><div class="l">{label}</div><b>{value}</b><small>{small}</small></div>'


def overview(health: dict, vis: dict, me: dict = None, key: str = "") -> str:
    """Everything at a glance: traffic (now, today, members vs visitors, by hour and day, countries, sources,
    devices, pages), accounts (sign-ups, sign-up rate, newest), Predict & Win (entries, by hour, the crowd's picks),
    tournament trackers, and the site's health."""
    from tracker import auth
    kq = ("?key=" + E(key)) if key else ""
    u = auth.counts() if auth.ENABLED else None
    h, s = health or {}, (health or {}).get("scan") or {}
    mem = (h.get("memory_mb") or {}).get("MemAvailable") or 0
    now_ist = datetime.now(IST)
    today = now_ist.strftime("%Y-%m-%d")
    act, tod = vis.get("active", 0), vis.get("today", 0)
    pk = vis.get("peak") or {}
    try:
        from tracker import pmgc
        pg = pmgc.admin_stats()
    except Exception:
        pg = None
    try:
        from tracker import events as ev_
        ytq = (ev_._YTQ["n"] if ev_._YTQ["day"] else 0, ev_.YT_QUOTA)
    except Exception:
        ytq = (0, 0)
    left = (pg["lock"] - time.time()) if pg else 0
    lock_txt = ("locked" if pg and pg["closed"] else f"locks in {int(left // 3600)}h {int(left % 3600 // 60)}m") if pg else ""
    # ---- headline numbers
    cards = (_card("On the site now", f"{act:,}", f'{vis.get("active_members", 0):,} signed in · {max(0, act - vis.get("active_members", 0)):,} visitors')
             + _card("Visitors today", f"{tod:,}", f'{vis.get("today_members", 0):,} signed in · avg {vis.get("avg_min", 0)} min on site')
             + (_card("Most at once", f"{act:,}", "right now") if act >= pk.get("n", 0) else
                _card("Most at once", f'{pk.get("n", 0):,}', datetime.fromtimestamp(pk["ts"], IST).strftime("%d %b, %I:%M %p") if pk.get("ts") else "-"))
             + (_card("Accounts", f'{u["total"]:,}', f'+{u["today"]} today · +{u["week"]} in 7 days')
                + _card("Sign-up rate today", f'{round(100 * u["today"] / tod, 1) if tod else 0}%', f'{u["today"]} of {tod:,} visitors made an account')
                + _card("Signed in today", f'{u["active_today"]:,}', f'{u["weekly"]:,} on the weekly email list')
                if u else _card("Accounts", "off", "sign-in keys not set"))
             + (_card("PMGC Predict & Win", f'{pg["total"]:,}', f'+{pg["today"]} today · +{pg["hour"]} last hour · {lock_txt}') if pg else "")
             + (_card("Live scan", f'{s.get("last_saved_min_ago")} min ago', f'took {s.get("last_took_s") or "-"} s · {s.get("live") or 0:,} live',
                      (s.get("last_saved_min_ago") or 0) > 8)
                if isinstance(s.get("last_saved_min_ago"), (int, float)) and s["last_saved_min_ago"] < 1440
                else _card("Live scan", "none yet", "waiting for the first scan", True))
             + _card("Server load", f'{(h.get("load") or [0])[0]:.1f}', f'{mem:,} MB free · {h.get("disk_free_gb", "-")} GB disk', (h.get("load") or [0])[0] > 6)
             + _card("YouTube quota", f"{ytq[0]:,}", f"of {ytq[1]:,} today", ytq[1] and ytq[0] > 0.9 * ytq[1])
             + _card("Code", E(str(h.get("code") or "-")), f'up {h.get("up_min", "-")} min'))
    # ---- traffic
    dd = dict(vis.get("days") or {})
    dd[datetime.now(IST).strftime("%Y-%m-%d")] = max(tod, dd.get(datetime.now(IST).strftime("%Y-%m-%d"), 0))
    days = sorted(dd.items())[-14:]
    md = dict(vis.get("member_days") or {})
    md[datetime.now(IST).strftime("%Y-%m-%d")] = max(vis.get("today_members", 0), md.get(datetime.now(IST).strftime("%Y-%m-%d"), 0))
    day_rows = "".join(f'<tr><td>{datetime.strptime(d, "%Y-%m-%d").strftime("%a %d %b")}</td><td class="n"><b>{n:,}</b></td>'
                       f'<td class="n">{md.get(d, 0):,}</td><td class="n mut">{round(100 * md.get(d, 0) / n) if n else 0}%</td></tr>'
                       for d, n in reversed(days[-7:]))
    hrs = vis.get("hours") or {}
    hour_bars = _bars([(f"{hh:02d}", hrs.get(hh, 0)) for hh in range(0, now_ist.hour + 1)], every=3)
    dev = vis.get("devices") or []
    day_bars = _bars([(datetime.strptime(d, "%Y-%m-%d").strftime("%d %b"), n) for d, n in days], fmt=lambda v: f"{v:,}")
    traffic = (f'<div class="grid"><div class="card"><h2>Visitors, last 14 days <a href="/admin/visitors{kq}">Traffic</a></h2>'
               f'{day_bars}'
               f'<table style="margin-top:12px"><tr><th>Day</th><th class="n">Visitors</th><th class="n">Signed in</th><th class="n">Share</th></tr>{day_rows or "<tr><td class=mut>-</td></tr>"}</table></div>'
               f'<div class="card"><h2>New visitors today by hour (IST)</h2>{hour_bars}'
               f'<div class="grid" style="margin-top:12px;gap:10px"><div><div class="sl">Devices</div><table>{_rows(dev, pct_of=tod)}</table></div>'
               f'<div><div class="sl">On the site now, by country</div><table>{_rows((vis.get("active_countries") or [])[:5])}</table></div></div></div></div>'
               f'<div class="grid"><div class="card"><h2>Countries today</h2><table>{_rows((vis.get("countries") or [])[:8], pct_of=tod)}</table></div>'
               f'<div class="card"><h2>Where visitors came from today</h2><table>{_rows((vis.get("refs") or [])[:8], pct_of=tod)}</table></div></div>'
               f'<div class="grid"><div class="card"><h2>Pages people are on now</h2><table>{_rows(_pages(vis.get("pages_now") or []), "Nobody right now")}</table></div>'
               f'<div class="card"><h2>Most visited pages today</h2><table>{_rows(_pages(vis.get("pages_today") or []))}</table></div></div>')
    # ---- accounts
    accounts = ""
    if u:
        recent = "".join(f'<tr><td><div class="u">{_avatar(p)}<div><b>{E(p["name"] or "")}</b><div class="mut">{E(p["email"])}</div></div></div></td>'
                         f'<td class="mut hide">{E(p["region"] or "-")}</td><td class="n mut">{_ago(p["created"])}</td></tr>' for p in auth.people(limit=8))
        accounts = (f'<div class="grid"><div class="card"><h2>Sign-ups, last 14 days <a href="/admin/people{kq}">All people</a></h2>{_bars(u["days"])}'
                    f'<div class="sl" style="margin-top:12px">Accounts by country</div><table>{_rows(u["countries"], pct_of=u["total"])}</table></div>'
                    f'<div class="card"><h2>Newest accounts <a href="/admin/people.csv?weekly=1{("&key=" + E(key)) if key else ""}">Email list (CSV)</a></h2><table>{recent or "<tr><td class=mut>No accounts yet.</td></tr>"}</table></div></div>')
    # ---- predict & win
    predict = ""
    if pg:
        pct = lambda pairs: [(k, v) for k, v in pairs]
        newest = "".join(f'<tr><td><b>@{E(e["handle"])}</b><div class="mut">{E(e["name"])} · {E(e["email"] or "")}</div></td><td class="n mut">{_ago(e["t"])}</td></tr>'
                         for e in pg["newest"])
        hrs_p = _bars([(f"{hh:02d}", pg["hours"].get(hh, 0)) for hh in range(0, now_ist.hour + 1)], every=3)
        pcards = (_card("Entries", f'{pg["total"]:,}', f'{pg["hidden"]} hidden') + _card("Today", f'{pg["today"]:,}', "new entries")
                  + _card("Last hour", f'{pg["hour"]:,}', "new entries") + _card("Changed their picks", f'{pg["edited"]:,}', "after submitting")
                  + _card("Picks", "Locked" if pg["closed"] else "Open", ("locked " if pg["closed"] else "lock ") + pmgc_lock_text(pg["lock"])))
        predict = (f'<div class="card"><h2>PMGC Gauntlet: Predict &amp; Win <a href="/admin/pmgc{kq}">Manage</a></h2>'
                   f'<div class="k" style="margin-bottom:12px">{pcards}</div>'
                   f'<div class="grid"><div><div class="sl">Entries today by hour (IST)</div>{hrs_p}<div class="sl" style="margin-top:14px">Newest entries</div>'
                   f'<table>{newest or "<tr><td class=mut>No entries yet.</td></tr>"}</table></div>'
                   f'<div><div class="grid" style="gap:12px"><div><div class="sl">Gauntlet #1</div><table>{_rows(pct(pg["first"]), pct_of=pg["total"])}</table></div>'
                   f'<div><div class="sl">#1 in their top 3</div><table>{_rows(pct(pg["top1"]), pct_of=pg["total"])}</table></div>'
                   f'<div><div class="sl">Team SouL to the finals?</div><table>{_rows(pct(pg["soul"]), pct_of=pg["total"])}</table></div>'
                   f'<div><div class="sl">Most chicken dinners</div><table>{_rows(pct(pg["dinners"]), pct_of=pg["total"])}</table></div>'
                   f'<div><div class="sl">Most picked finalists</div><table>{_rows(pct(pg["finalists"]), pct_of=pg["total"])}</table></div>'
                   f'<div><div class="sl">Peak viewers</div><table>{_rows(pct(pg["peak"]), pct_of=pg["total"])}</table></div></div></div></div></div>')
    # ---- health
    warn = "".join(f"<div>{E(x)}</div>" for x in (h.get("recent") or [])[-8:])
    rk = h.get("rankings") or {}
    wl = h.get("write_lock")
    ru = rk.get("updated_min_ago")
    hcards = (_card("Rankings updated", f"{ru} min ago" if isinstance(ru, (int, float)) and ru < 10000 else "not yet", "", isinstance(ru, (int, float)) and 120 < ru)
              + _card("Database log", f'{h.get("wal_mb", 0) or 0:,} MB', "WAL", (h.get("wal_mb") or 0) > 1500)
              + _card("Write lock", "free" if wl == "free" else f'{(wl or {}).get("held_s")} s', "" if wl == "free" else E(str((wl or {}).get("by"))))
              + _card("Memory", f"{mem:,} MB", "available"))
    health_card = (f'<div class="card"><h2>Site health <a href="/admin/health{kq}">Live health</a></h2>'
                   f'<div class="k" style="margin-bottom:10px">{hcards}</div><div class="sl">Latest warnings (UTC)</div><div class="log">{warn or "<div class=mut>None</div>"}</div></div>')
    body = (f'<h1>Overview</h1><p class="sub">{now_ist.strftime("%a %d %b, %I:%M %p")} IST · refreshes every minute</p><div class="k">{cards}</div>'
            + predict + traffic + accounts +
            f'<div class="card"><h2>Tournament trackers <a href="/admin/trackers{kq}">All trackers</a></h2><div class="ov">{_tracker_rows([t for t in _trackers() if not t["ended"]][:8])}</div></div>'
            + health_card +
            '<style>.sl{font:700 11px Figtree,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin:4px 0 6px}'
            '.bars div i{position:absolute;top:-16px;left:0;right:0;text-align:center;font-size:10px;font-style:normal;color:var(--mut)}.bars{margin-top:18px}'
            '.log{font:12px ui-monospace,Menlo,monospace;color:#b4b3c4;white-space:pre-wrap;line-height:1.6}</style>'
            '<script>setTimeout(()=>location.reload(),60000)</script>')
    return page("overview", "Overview", body, me, key)


def pmgc_lock_text(ts: float) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%d %b, %I:%M %p IST")


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


def tracker_page(tk: str, me: dict = None, key: str = "", msg: str = "") -> str:
    """One tracker's streams right now: what it counts (with Exclude) and what the watch-party check left out, with
    the reason (with Count it). Changes take effect at the next 2-second count."""
    from tracker import events
    ev = events.events().get(tk)
    if not ev:
        return page("trackers", "Tracker", '<h1>Not found</h1>', me, key)
    kf = f'<input type="hidden" name="key" value="{E(key)}">' if key else ""
    live = sorted((events._LIVE.get(tk) or {}).values(), key=lambda x: -int(x.get("viewers") or 0))
    now = time.time()
    rej = sorted((x for x in (events._REJ.get(tk) or {}).values() if now - x["ts"] < 1800 and x["vid"] not in (events._LIVE.get(tk) or {})),
                 key=lambda x: -x["viewers"])
    ph = events._PHASE.get(tk) or {}
    link = lambda x: (f'https://www.youtube.com/watch?v={E(x["vid"])}' if not str(x["vid"]).startswith(("kick:", "twitch:"))
                      else f'https://{"kick.com" if str(x["vid"]).startswith("kick:") else "twitch.tv"}/{E(str(x["vid"]).split(":")[1])}')
    btn = lambda x, act, label: (f'<form method="post" action="/admin/trackers/{E(tk)}/act" style="margin:0">{kf}'
                                 f'<input type="hidden" name="vid" value="{E(x["vid"])}"><input type="hidden" name="action" value="{act}">'
                                 f'<button class="btn{" bad" if act == "exclude" else ""}">{label}</button></form>')
    plat = lambda x: "Kick" if str(x["vid"]).startswith("kick:") else "Twitch" if str(x["vid"]).startswith("twitch:") else "YouTube"
    rows_l = "".join(f'<tr><td><a href="{link(x)}" target="_blank" rel="noopener"><b>{E(x.get("channel") or "-")}</b></a>'
                     f'<div class="mut">{plat(x)} · {E((x.get("title") or "")[:110])}</div></td>'
                     f'<td>{E(x.get("kind") or "")}</td><td class="n"><b>{_fmt(x.get("viewers") or 0)}</b></td>'
                     f'<td>{"" if x.get("kind") == "official" else btn(x, "exclude", "Exclude")}</td></tr>' for x in live)
    rows_r = "".join(f'<tr><td><a href="{link(x)}" target="_blank" rel="noopener"><b>{E(x["channel"] or "-")}</b></a>'
                     f'<div class="mut">{plat(x)} · {E(x["title"][:110])}</div></td><td class="mut">{E(x["why"])}</td>'
                     f'<td class="n">{_fmt(x["viewers"])}</td><td>{btn(x, "include", "Count it")}</td></tr>' for x in rej)
    tot = sum(int(x.get("viewers") or 0) for x in live)
    body = (f'<h1>{E(ev.get("name") or tk)}</h1><p class="sub">{"Searching YouTube (India and worldwide), Kick and Twitch" if ph.get("mode") == "full" else "Watching the official channels; the full search starts 30 minutes before the start or when one goes live"}. '
            f'<a href="/e/{E(tk)}/" target="_blank">Public page</a></p>'
            + (f'<div class="msg">{E(msg)}</div>' if msg else "")
            + f'<div class="k">{_card("Counted now", str(len(live)), _fmt(tot) + " watching")}{_card("Left out by the check", str(len(rej)), "last 30 minutes")}</div>'
            f'<div class="card"><h2>Counted now</h2><table><tr><th>Stream</th><th>Kind</th><th class="n">Watching</th><th></th></tr>'
            f'{rows_l or "<tr><td class=mut colspan=4>Nothing live yet.</td></tr>"}</table></div>'
            f'<div class="card"><h2>Left out: names the event but is not a watch party</h2><p class="sub">Gameplay, custom rooms, scrims, talk shows, '
            f'another game, or the event only in hashtags. If one is really a watch party, Count it.</p><table><tr><th>Stream</th><th>Why</th><th class="n">Watching</th><th></th></tr>'
            f'{rows_r or "<tr><td class=mut colspan=4>Nothing left out.</td></tr>"}</table></div>'
            '<script>setTimeout(function(){location.reload()},30000)</script>')
    return page("trackers", ev.get("name") or tk, body, me, key)


def pmgc_page(me: dict = None, key: str = "", q: str = "", msg: str = "") -> str:
    """PMGC 2026 Gauntlet Predict & Win: entries, results, lock time, leaderboard switch, team logos."""
    from tracker import pmgc
    s = pmgc.settings()
    a = s["answers"]
    es = pmgc.admin_entries(q)
    kf = f'<input type="hidden" name="key" value="{E(key)}">' if key else ""
    kq = ("?key=" + E(key)) if key else ""
    T = pmgc.TEAM_NAMES
    sel = lambda name, opts, cur: (f'<select name="{name}"><option value="">-</option>' +
                                   "".join(f'<option{" selected" if o == cur else ""}>{E(o)}</option>' for o in opts) + "</select>")
    boxes = lambda name, cur: "".join(f'<label class="cb"><input type="checkbox" name="{name}" value="{E(t)}"{" checked" if t in (cur or []) else ""}> {E(t)}</label>' for t in T)
    q8 = a.get("q8") or ["", "", ""]
    tp = pmgc.tracker_peak()
    form = (f'<form method="post" action="/admin/pmgc/act">{kf}<input type="hidden" name="action" value="answers">'
            f'<div class="ql"><b>1. The 6 Grand Finals qualifiers</b><div class="cbs">{boxes("q1", a.get("q1"))}</div></div>'
            f'<div class="ql"><b>2. Gauntlet #1</b> {sel("q2", T, a.get("q2"))}</div>'
            f'<div class="ql"><b>3. Team SouL to the Grand Finals?</b> {sel("q3", pmgc.YN, a.get("q3"))}</div>'
            f'<div class="ql"><b>4. Most chicken dinners</b> <span class="mut">(tick more than one for a tie)</span><div class="cbs">{boxes("q4", a.get("q4"))}</div></div>'
            f'<div class="ql"><b>5. Any team 3+ chicken dinners?</b> {sel("q5", pmgc.YN, a.get("q5"))}</div>'
            f'<div class="ql"><b>6. Peak live viewership</b> {sel("q6", pmgc.PEAKS, a.get("q6"))} <span class="mut">tracker peak over 26-27 Nov: '
            f'{_fmt(tp) + " = " + pmgc.peak_bucket(tp) if tp else "no reading yet"}</span></div>'
            f'<div class="ql"><b>7. Different chicken dinner winners</b> {sel("q7", [str(i) for i in range(1, 13)], a.get("q7"))}</div>'
            f'<div class="ql"><b>8. Top 3 in order</b> #1 {sel("q8_0", T, q8[0] if q8 else "")} #2 {sel("q8_1", T, q8[1] if len(q8) > 1 else "")} '
            f'#3 {sel("q8_2", T, q8[2] if len(q8) > 2 else "")}</div>'
            f'<button class="btn l">Save results</button> <span class="mut">Points update at once. Leave a question on "-" until it is settled.</span></form>')
    lock_ist = datetime.fromtimestamp(float(s["lock"]), IST).strftime("%Y-%m-%dT%H:%M")
    sets = (f'<form method="post" action="/admin/pmgc/act" class="row">{kf}<input type="hidden" name="action" value="settings">'
            f'<label>Picks lock (IST) <input type="datetime-local" name="lock" value="{lock_ist}"></label>'
            f'<label><input type="checkbox" name="show_lb" value="1"{" checked" if s["show_lb"] else ""}> Show the leaderboard</label>'
            f'<label style="flex:1;min-width:260px">Prize line <input type="text" name="prize" value="{E(s["prize"])}" style="width:100%"></label>'
            f'<button class="btn l">Save</button></form>')
    st = pmgc.logo_status()
    logos = "".join(
        f'<tr><td><div class="u">{f"<img src={chr(34)}/pmgc/logo/{t[1]}{chr(34)} style={chr(34)}border-radius:4px;object-fit:contain;background:#1d1d28{chr(34)}>" if pmgc.logo_file(t[1]) else "<span class=ph></span>"}<b>{E(t[0])}</b></div></td>'
        f'<td class="mut">{E((st.get(t[1]) or {}).get("result") or ("ok" if pmgc.logo_file(t[1]) else "waiting"))}</td>'
        f'<td><input type="url" name="logo_{t[1]}" placeholder="Paste an image link to replace" style="width:100%"></td></tr>' for t in pmgc.TEAMS)
    logo_form = (f'<form method="post" action="/admin/pmgc/act">{kf}<input type="hidden" name="action" value="logos">'
                 f'<div class="ov"><table><tr><th>Team</th><th>Logo</th><th>Replace with</th></tr>{logos}</table></div>'
                 f'<button class="btn l" style="margin-top:10px">Fetch logos now</button> <span class="mut">Missing logos are fetched from Liquipedia; pasted links replace a logo.</span></form>')
    rows = ""
    for i, e in enumerate(es, 1):
        p = e["picks"]
        act = "unhide" if e["hidden"] else "hide"
        rows += (f'<tr{" style=opacity:.45" if e["hidden"] else ""}><td class="n">{i}</td><td><b>@{E(e["handle"])}</b><div class="mut">{E(e["name"])} · {E(e["email"] or "")}</div></td>'
                 f'<td class="mut hide">{E(", ".join(p.get("q8") or []))}</td><td class="n"><b>{e["pts"]}</b><div class="mut">{e["right"]} right</div></td>'
                 f'<td class="n mut hide">{datetime.fromtimestamp(e["updated"], IST).strftime("%d %b %H:%M")}</td>'
                 f'<td><form method="post" action="/admin/pmgc/act" style="display:inline">{kf}<input type="hidden" name="action" value="{act}">'
                 f'<input type="hidden" name="uid" value="{e["uid"]}"><button class="btn">{act.title()}</button></form></td></tr>')
    body = (f'<h1>PMGC Gauntlet: Predict &amp; Win</h1><p class="sub">{len(es)} entries · picks {"locked" if pmgc.closed() else "lock"} '
            f'{E(pmgc.fmt_ist(float(s["lock"])))} · <a href="/predict/pmgc" target="_blank">Public page</a> · '
            f'<a href="/admin/pmgc.csv{kq}">Download entries (CSV)</a></p>'
            + (f'<div class="card" style="border-color:#3a5a12">{E(msg)}</div>' if msg else "") +
            f'<div class="card"><h2>Settings</h2>{sets}</div><div class="card"><h2>Results</h2>{form}</div>'
            f'<div class="card"><h2>Entries <form method="get" style="display:flex;gap:8px">{kf}<input type="search" name="q" value="{E(q)}" placeholder="Search"></form></h2>'
            f'<div class="ov"><table><tr><th class="n">#</th><th>Player</th><th class="hide">Top 3</th><th class="n">Points</th><th class="n hide">Saved</th><th></th></tr>'
            f'{rows or "<tr><td colspan=6 class=mut>No entries yet.</td></tr>"}</table></div></div>'
            f'<div class="card"><h2>Team logos</h2>{logo_form}</div>')
    css = ("<style>.ql{padding:10px 0;border-bottom:1px solid var(--line)}.cbs{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:6px}.cb{font-size:13px}"
           "select,input[type=text],input[type=url],input[type=datetime-local]{background:#0b0b11;border:1px solid var(--line);color:#fff;border-radius:8px;padding:7px 9px;font:inherit}"
           ".row{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.u img{width:28px;height:28px}</style>")
    return page("pmgc", "PMGC Predict", css + body, me, key)
