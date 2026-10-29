"""Owner-only visitors page (/admin/visitors?key=...): who is on the site now and today. Same numbers as
`track.py visitors`, counted without cookies or IP addresses (one browser tab = one visitor)."""
import html
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Kolkata")
FLAG = lambda c: "".join(chr(0x1F1E6 + ord(x) - 65) for x in c) if len(c) == 2 and c.isalpha() and c.isupper() and c != "XX" else ""


def _bars(pairs, total, fmt=lambda k: k):
    if not pairs:
        return '<div class="e">Nobody yet.</div>'
    top = max(v for _, v in pairs) or 1
    return "".join(f'<div class="b"><span class="k">{html.escape(fmt(k))}</span><span class="t"><i style="width:{100 * v / top:.1f}%"></i></span>'
                   f'<span class="v">{v:,}<small>{100 * v / max(total, 1):.0f}%</small></span></div>' for k, v in pairs)


def build_html(s: dict) -> str:
    pk = s.get("peak") or {}
    when = datetime.fromtimestamp(pk["ts"], TZ).strftime("%d %b, %I:%M %p IST") if pk.get("ts") else "-"
    days = list((s.get("days") or {}).items())[-30:]
    dmax = max([n for _, n in days] or [1]) or 1
    ctry = lambda c: f"{FLAG(c)} {c}" if c != "??" else "Unknown"
    tod = s.get("today", 0)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><meta http-equiv="refresh" content="30"><title>Visitors | owner only</title>
<style>:root{{color-scheme:dark}}body{{margin:0;background:#0b0b12;color:#eeeef5;font:15px/1.45 system-ui,sans-serif}}main{{max-width:1000px;margin:0 auto;padding:18px 16px 40px}}
h1{{font-size:26px;margin:0 0 2px}}.sub{{color:#8d8ca3;font-size:13px}}.k4{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}}
.c{{background:#13131c;border:1px solid #262636;padding:14px}}.c b{{display:block;font-size:30px;font-variant-numeric:tabular-nums}}.c span{{color:#8d8ca3;font-size:13px}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}}h2{{font-size:15px;margin:0 0 8px}}
.b{{display:grid;grid-template-columns:120px minmax(0,1fr) 74px;gap:8px;align-items:center;font-size:13px;padding:3px 0}}.k{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.t{{background:#1a1a26;height:10px}}.t i{{display:block;height:100%;background:#b6f23a}}.v{{text-align:right;font-variant-numeric:tabular-nums}}.v small{{color:#8d8ca3;margin-left:5px}}
.d{{display:flex;align-items:flex-end;gap:3px;height:120px;margin-top:8px}}.d div{{flex:1;background:#a58bff;min-height:2px;position:relative}}.d div span{{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);font-size:10px;color:#8d8ca3}}
.dl{{display:flex;justify-content:space-between;color:#8d8ca3;font-size:11px;margin-top:4px}}.e{{color:#8d8ca3;font-size:13px}}
@media(max-width:700px){{.k4{{grid-template-columns:1fr 1fr}}.g{{grid-template-columns:1fr}}}}</style></head><body><main>
<h1>Visitors</h1><div class="sub">Owner only, refreshes every 30 s. One browser tab = one visitor; no cookies, no IP addresses. Days are IST.</div>
<div class="k4"><div class="c"><b>{s.get('active', 0):,}</b><span>on the site now</span></div><div class="c"><b>{tod:,}</b><span>visitors today</span></div>
<div class="c"><b>{pk.get('n', 0):,}</b><span>most at once ({html.escape(when)})</span></div><div class="c"><b>{s.get('avg_min', 0)} min</b><span>average time on site today</span></div></div>
<div class="sub" style="margin-top:8px">YouTube API used today: {(s.get('ytq') or (0, 0))[0]:,} of {(s.get('ytq') or (0, 0))[1]:,} units (resets at midnight Pacific).</div>
<div class="c" style="margin-top:10px"><h2>Visitors per day, last 30 days</h2><div class="d">{''.join(f'<div style="height:{100 * n / dmax:.0f}%" title="{d}: {n:,}"><span>{n if n * 6 >= dmax else ""}</span></div>' for d, n in days) or '<div class="e">No history yet.</div>'}</div>
<div class="dl"><span>{days[0][0][5:] if days else ''}</span><span>{days[-1][0][5:] if days else ''}</span></div></div>
<div class="g"><div class="c"><h2>On the site now, by country</h2>{_bars(s.get('active_all_countries', []), s.get('active', 0), ctry)}</div>
<div class="c"><h2>On the site now, by city</h2>{_bars(s.get('active_places', []), s.get('active', 0))}</div>
<div class="c"><h2>Today, by country</h2>{_bars(s.get('all_countries', [])[:15], tod, ctry)}</div>
<div class="c"><h2>Today, by city</h2>{_bars(s.get('places', [])[:15], tod)}</div>
<div class="c"><h2>Where they came from</h2>{_bars(s.get('refs', []), tod)}</div>
<div class="c"><h2>Device</h2>{_bars(s.get('devices', []), tod)}</div></div>
</main></body></html>"""
