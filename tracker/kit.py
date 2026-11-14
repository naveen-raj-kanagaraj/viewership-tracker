"""Creator media kits, shortlists and the paid data feed for agencies.

  /kit/<sid>         one page per creator for brands: audience size and growth, engagement against peers, live
                     viewing, chat (activity, languages, mood, what viewers talk about), viewer spending during
                     streams, audience overlap with other creators, this year by month, best recent videos.
                     "Download PDF" prints the page (print stylesheet, A4).
  /shortlist         creators saved from kits (kept in the visitor's browser), side by side, with CSV export.
  /api/v1/...        the data feed: same data as JSON for agencies, with an API key (X-API-Key header or ?key=).
                     Keys: python track.py apikey create "Agency name" [calls per day] / list / revoke <prefix>.
                     Docs at /api/docs.
"""
import hashlib
import html
import json
import secrets
import time

from tracker import eventpage, store

API_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (khash TEXT PRIMARY KEY, prefix TEXT, name TEXT, daily INTEGER, created INTEGER, active INTEGER);
CREATE TABLE IF NOT EXISTS api_use (khash TEXT, day TEXT, calls INTEGER, PRIMARY KEY (khash, day));
"""
_ready = False


def _db():
    global _ready
    from tracker import ytextra
    c = ytextra._db()
    if not _ready:
        c = store.main()          # tables are made on the read-write connection
        c.executescript(API_SCHEMA)
        c.commit()
        _ready = True
    return store.conn()


# ---------- the data behind a kit ----------

def data(sid: str) -> dict:
    from tracker import deep, chatstats, ranks, ytextra
    with store.reading():
        c = _db()
        ch = c.execute("SELECT * FROM sc_channels WHERE sid=?", (sid,)).fetchone()
        if not ch:
            return {}
        ch = dict(ch)
        st = c.execute("SELECT subs, views, videos, day FROM sc_chstats WHERE sid=? ORDER BY day DESC LIMIT 1", (sid,)).fetchone()
        since = ytextra._day(time.time() - 30 * 86400)
        lv = c.execute("""SELECT COUNT(DISTINCT day), SUM(mins), SUM(hw), MAX(peak) FROM sc_daily WHERE sid=? AND day>=?""",
                       (sid, since)).fetchone()
        games = c.execute("""SELECT game, SUM(hw) h FROM sc_daily WHERE sid=? AND day>=? GROUP BY game ORDER BY h DESC LIMIT 4""",
                          (sid, since)).fetchall()
    rk = (ranks._R.get("rows") or {}).get(sid) or {}
    hours = (lv[1] or 0) / 60
    out = {"sid": sid, "name": ch.get("name") or sid, "platform": ch.get("platform"), "url": ch.get("url"),
           "logo": ch.get("logo") or "", "country": ch.get("country") or ("IN" if ch.get("india") else ""),
           "category": ch.get("ytcat") or ch.get("topic") or "", "game": ch.get("game") or "",
           "audience": {"subscribers": st["subs"] if st else None, "total_views": st["views"] if st else None,
                        "videos": st["videos"] if st else None, "as_of": st["day"] if st else None,
                        "views_24h": rk.get("vday"), "views_7d": rk.get("v7"), "views_30d": rk.get("growth")},
           "live_30d": {"days_live": lv[0] or 0, "hours": round(hours, 1), "hours_watched": round(lv[2] or 0),
                        "avg_viewers": round((lv[2] or 0) / hours) if hours else None, "peak_viewers": lv[3],
                        "games": [{"game": g, "hours_watched": round(h or 0)} for g, h in games]},
           "updated": int(time.time())}
    if sid.startswith("yt:"):
        out["engagement"] = deep.standing(sid)
        out["monthly"] = deep.monthly(sid)
        perf = deep.performance(sid)
        with store.reading():
            vids = {r[0]: dict(r) for r in _db().execute(
                "SELECT vid, title, ts, views, likes, comments FROM yt_videos WHERE sid=? AND ts>?", (sid, time.time() - 90 * 86400))}
        out["best_videos"] = [{**vids[v], "index": p} for v, p in sorted(perf.items(), key=lambda x: -x[1]) if v in vids][:5]
        out["chat_30d"] = chatstats.summary(sid)
    return out


# ---------- pages ----------

HEAD = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title><meta name="theme-color" content="#07051a">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
a{color:inherit}.top{border-bottom:1px solid var(--line)}.top .in{max-width:1000px;margin:0 auto;padding:10px 16px;display:flex;gap:14px;align-items:center}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;letter-spacing:.04em}
.wrap{max-width:1000px;margin:0 auto;padding:0 16px 40px}h1{font:700 40px/1.05 "Barlow Condensed",sans-serif;margin:0;text-transform:uppercase}
h2{font:700 20px "Barlow Condensed",sans-serif;text-transform:uppercase;margin:0 0 4px;letter-spacing:.02em}
.cap{color:var(--muted);font-size:12px;margin-bottom:10px}.card{background:var(--card);border:1px solid var(--line);padding:16px;margin-top:14px;break-inside:avoid}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.k{background:var(--card2);padding:10px 12px}
.k b{display:block;font:700 26px "Barlow Condensed",sans-serif}.k span{color:var(--muted);font-size:12px}
.btn{font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.05em;text-transform:uppercase;border:1px solid var(--line);background:var(--card2);color:var(--ink);padding:9px 14px;cursor:pointer;text-decoration:none;display:inline-block}
.btn.p{background:var(--lime);color:#0b0b12;border-color:var(--lime)}.row{display:flex;gap:8px;flex-wrap:wrap}
table{border-collapse:collapse;width:100%;font-size:13px}th{color:var(--muted);font-weight:500;font-size:11px;text-align:right;padding:6px 8px}
td{text-align:right;padding:6px 8px;border-top:1px solid var(--line);white-space:nowrap}th:first-child,td:first-child{text-align:left;white-space:normal}
.tbl{overflow-x:auto}.chip{display:inline-block;background:var(--card2);padding:3px 8px;margin:0 6px 6px 0;font-size:13px}
.bar{height:8px;background:var(--card2);position:relative;margin-top:4px}.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--lime)}
.note{color:var(--muted);font-size:11px;margin-top:16px;line-height:1.5}
@media print{#wip,#legal,.bk,#bk{display:none!important}:root{--bg:#fff;--card:#fff;--card2:#f3f3f6;--ink:#111;--muted:#555;--line:#ddd;--lime:#3c7a00}
 html,body{background:#fff}.noprint{display:none!important}.card{border-color:#ddd}@page{size:A4;margin:12mm}}
</style></head><body>
<div class="top noprint"><div class="in"><a class="brand" href="/">__BRAND__</a><a class="btn" href="/shortlist" style="margin-left:auto">Shortlist <span id="scount"></span></a></div></div>
"""

KIT = HEAD + r"""<div class="wrap" id="app"><div class="cap" style="margin-top:20px">Loading media kit...</div></div>
<script>
const SID=__SID__,SITE=__SITE__,BRAND=__BRANDJS__;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>n==null?'-':Math.abs(n)>=1e9?(n/1e9).toFixed(2)+'B':Math.abs(n)>=1e6?(n/1e6).toFixed(Math.abs(n)>=1e7?1:2)+'M':Math.abs(n)>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN');
const pc=x=>x==null?'-':(x*100).toFixed(x<.1?2:1)+'%',usd=x=>'$'+(x||0).toLocaleString('en-US',{maximumFractionDigits:0});
const SL=()=>{try{return JSON.parse(localStorage.getItem('lge_shortlist')||'[]')}catch(e){return[]}},SSL=l=>{try{localStorage.setItem('lge_shortlist',JSON.stringify(l))}catch(e){}};
const cnt=()=>{document.getElementById('scount').textContent=SL().length?'('+SL().length+')':''};cnt();
(async()=>{let D;try{D=await (await fetch('/api/kit?sid='+encodeURIComponent(SID))).json()}catch(e){}
 const A=document.getElementById('app');if(!D||!D.sid){A.innerHTML='<p>Not found.</p>';return}
 const a=D.audience||{},L=D.live_30d||{},E=(D.engagement||{}).formats||{},C=D.chat_30d,S=C&&C.spending;
 const ef=E.long||E.short||E.live,efn=E.long?'videos':E.short?'Shorts':'streams';
 const inList=()=>SL().some(x=>x.sid===SID);
 let h=`<div style="display:flex;gap:16px;align-items:center;margin-top:20px">${D.logo?`<img src="${esc(D.logo)}" style="width:84px;height:84px;border-radius:50%;object-fit:cover" referrerpolicy="no-referrer">`:''}
  <div style="min-width:0"><div class="cap" style="margin:0">MEDIA KIT · ${esc((D.platform||'').toUpperCase())}${D.category?' · '+esc(D.category):''}${D.game&&D.game!=='Other'?' · '+esc(D.game):''}${D.country?' · '+esc(D.country):''}</div>
  <h1>${esc(D.name)}</h1><div class="cap" style="margin:4px 0 0"><a href="${esc(D.url)}" target="_blank" rel="noopener">${esc(D.url)}</a></div></div></div>
  <div class="row noprint" style="margin-top:14px"><button class="btn p" onclick="window.print()">Download PDF</button><button class="btn" id="sl">${inList()?'In shortlist':'Add to shortlist'}</button><button class="btn" id="cp">Copy link</button></div>`;
 h+=`<div class="card"><h2>Audience</h2><div class="cap">${a.as_of?'Read '+esc(a.as_of):''}</div><div class="grid">
  <div class="k"><b>${fmt(a.subscribers)}</b><span>${D.platform==='youtube'?'subscribers':'followers'}</span></div><div class="k"><b>${fmt(a.total_views)}</b><span>total views</span></div>
  <div class="k"><b>${fmt(a.views_30d)}</b><span>views, last 30 days</span></div><div class="k"><b>${fmt(a.views_7d)}</b><span>views, last 7 days</span></div></div></div>`;
 if(ef)h+=`<div class="card"><h2>Engagement</h2><div class="cap">Medians of the last 30 ${efn} aged 3 to 90 days. This site's calculation from public counts.</div><div class="grid">
  <div class="k"><b>${pc(ef.eng_rate)}</b><span>engagement (likes + comments / views)</span></div><div class="k"><b>${pc(ef.like_rate)}</b><span>like rate</span></div>
  <div class="k"><b>${fmt(ef.med_views)}</b><span>typical views per post</span></div><div class="k"><b>${(ef.per_week||0).toFixed(1)}</b><span>posts a week</span></div></div>
  ${(ef.peers||[]).map(p=>`<div style="margin-top:10px;font-size:13px">${p.pct>=50?'<b>Top '+(100-p.pct)+'%</b>':'Bottom '+(p.pct||1)+'%'} of ${esc(p.group)}${p.scope==='in'?' (India)':''} channels with ${esc(p.size)} subscribers <span class="cap">(${p.n} channels, median ${pc(p.p50)})</span></div>`).join('')}</div>`;
 if(L.hours)h+=`<div class="card"><h2>Live, last 30 days</h2><div class="grid"><div class="k"><b>${fmt(L.avg_viewers)}</b><span>average viewers</span></div><div class="k"><b>${fmt(L.peak_viewers)}</b><span>peak viewers</span></div>
  <div class="k"><b>${fmt(L.hours)}</b><span>hours live (${L.days_live} days)</span></div><div class="k"><b>${fmt(L.hours_watched)}</b><span>hours watched</span></div></div>
  ${(L.games||[]).length?`<div style="margin-top:10px">${L.games.map(g=>`<span class="chip">${esc(g.game)} · ${fmt(g.hours_watched)}h watched</span>`).join('')}</div>`:''}</div>`;
 if(C&&C.messages)h+=`<div class="card"><h2>Live chat, last 30 days</h2><div class="cap">From ${C.streams} streams whose chat this site read.</div><div class="grid">
  <div class="k"><b>${fmt(C.messages)}</b><span>chat messages</span></div><div class="k"><b>${fmt(C.msgs_per_hour)}</b><span>messages per hour live</span></div>
  <div class="k"><b>${fmt(C.avg_chatters)}</b><span>chatters per stream</span></div><div class="k"><b>${fmt(C.unique_chatters)}</b><span>different chatters (estimate)</span></div></div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:12px">
  <div><div class="cap" style="margin:0">CHAT LANGUAGES (BY SCRIPT)</div>${C.languages.map(l=>`<div style="font-size:13px;margin-top:6px">${esc(l.name)} <span class="cap">${pc(l.pct)}</span><div class="bar"><i style="width:${l.pct*100}%"></i></div></div>`).join('')}</div>
  <div><div class="cap" style="margin:0">MOOD (APPROXIMATE)</div>${[['Positive',C.mood.positive],['Neutral',C.mood.neutral],['Negative',C.mood.negative]].map(([n,v])=>`<div style="font-size:13px;margin-top:6px">${n} <span class="cap">${pc(v)}</span><div class="bar"><i style="width:${v*100}%"></i></div></div>`).join('')}</div></div>
  <div style="margin-top:12px"><div class="cap" style="margin:0 0 6px">WHAT VIEWERS SAY</div>${C.words.map(w=>`<span class="chip">${esc(w)}</span>`).join('')}</div>
  ${C.emotes.length?`<div><div class="cap" style="margin:6px 0">TOP EMOTES</div>${C.emotes.map(w=>`<span class="chip">${esc(w)}</span>`).join('')}</div>`:''}</div>`;
 if(S&&(S.total_usd||S.new_members))h+=`<div class="card"><h2>Viewer spending during streams, last 30 days</h2><div class="cap">What viewers paid in chat, before YouTube's cut. Super Chats and Stickers are exact amounts converted at each day's rate; memberships are counted exactly and valued at the lowest common price ($${S.member_price_usd}), so that part is an estimate.</div><div class="grid">
  <div class="k"><b>${usd(S.total_usd)}</b><span>total (estimate)</span></div><div class="k"><b>${usd((S.superchat||{}).usd)}</b><span>${fmt((S.superchat||{}).count||0)} Super Chats</span></div>
  <div class="k"><b>${usd((S.sticker||{}).usd)}</b><span>${fmt((S.sticker||{}).count||0)} Super Stickers</span></div><div class="k"><b>${fmt(S.new_members)}</b><span>new members</span></div>
  <div class="k"><b>${fmt(S.gifted)}</b><span>gifted memberships</span></div></div></div>`;
 if(C&&C.overlap&&C.overlap.length)h+=`<div class="card"><h2>Audience overlap</h2><div class="cap">Share of this creator's chatters (last 30 days) who also chatted with these creators. Counted from anonymised totals; no viewer is identified.</div>
  ${C.overlap.map(o=>`<div style="font-size:13px;margin-top:8px"><a href="/kit/${encodeURIComponent(o.sid)}">${esc(o.name)}</a> <span class="cap">${pc(o.pct)}</span><div class="bar"><i style="width:${Math.min(100,o.pct*100)}%"></i></div></div>`).join('')}</div>`;
 const M=D.monthly||[];if(M.length)h+=`<div class="card"><h2>This year, month by month</h2><div class="cap">Posts published each month, with the views, likes and comments they have now.</div><div class="tbl"><table><tr><th>Month</th><th>Videos</th><th>Shorts</th><th>Streams</th><th>Views</th><th>Likes</th><th>Comments</th><th>Engagement</th></tr>
  ${M.map(m=>`<tr><td>${new Date(m.month+'-01T00:00:00').toLocaleDateString('en-IN',{month:'short',year:'numeric'})}</td><td>${m.videos}</td><td>${m.shorts}</td><td>${m.streams}</td><td>${fmt(m.views)}</td><td>${fmt(m.likes)}</td><td>${fmt(m.comments)}</td><td>${pc(m.eng_rate)}</td></tr>`).join('')}</table></div></div>`;
 const B=D.best_videos||[];if(B.length)h+=`<div class="card"><h2>Best recent videos</h2><div class="cap">Last 90 days. Index = the video's views / this creator's typical views.</div>${B.map(v=>`<div style="display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid var(--line);font-size:13px"><span>${esc(v.title)}<span class="cap"> · ${fmt(v.views)} views</span></span><b>${v.index.toFixed(1)}x</b></div>`).join('')}</div>`;
 h+=`<div class="note">Prepared ${new Date().toLocaleDateString('en-IN',{day:'numeric',month:'long',year:'numeric'})} by ${esc(BRAND)} · ${esc(SITE.replace('https://',''))}/kit/${esc(SID)}. Public YouTube, Twitch and Kick data; engagement, benchmarks, chat analysis, overlap and spending are this site's own calculations. Not affiliated with YouTube, Twitch or Kick.</div>`;
 A.innerHTML=h;document.title=D.name+' media kit | '+BRAND;
 document.getElementById('sl').onclick=e=>{let l=SL();if(inList())l=l.filter(x=>x.sid!==SID);else l.push({sid:SID,name:D.name});SSL(l.slice(-20));e.target.textContent=inList()?'In shortlist':'Add to shortlist';cnt()};
 document.getElementById('cp').onclick=e=>{navigator.clipboard&&navigator.clipboard.writeText(location.href);e.target.textContent='Copied'};
})();
</script></body></html>"""

SHORT = HEAD + r"""<div class="wrap"><h1 style="margin-top:20px">Shortlist</h1><div class="cap">Creators you added from their media kits, side by side. Saved in this browser.</div>
<div class="row noprint"><button class="btn p" id="csv">Export CSV</button><button class="btn" onclick="window.print()">Download PDF</button><button class="btn" id="clr">Clear</button></div>
<div class="card tbl" id="t"><div class="cap">Loading...</div></div></div>
<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>n==null?'-':Math.abs(n)>=1e9?(n/1e9).toFixed(2)+'B':Math.abs(n)>=1e6?(n/1e6).toFixed(2)+'M':Math.abs(n)>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN');
const pc=x=>x==null?'-':(x*100).toFixed(x<.1?2:1)+'%',usd=x=>x==null?'-':'$'+Math.round(x).toLocaleString('en-US');
const SL=()=>{try{return JSON.parse(localStorage.getItem('lge_shortlist')||'[]')}catch(e){return[]}};
document.getElementById('scount').textContent=SL().length?'('+SL().length+')':'';
const ROWS=[['Platform',d=>(d.platform||'').toUpperCase()],['Category',d=>d.category||'-'],['Country',d=>d.country||'-'],
 ['Subscribers / followers',d=>fmt((d.audience||{}).subscribers),d=>(d.audience||{}).subscribers],['Views, 30 days',d=>fmt((d.audience||{}).views_30d),d=>(d.audience||{}).views_30d],
 ['Typical views per post',d=>fmt((F(d)||{}).med_views),d=>(F(d)||{}).med_views],['Engagement',d=>pc((F(d)||{}).eng_rate),d=>(F(d)||{}).eng_rate],['Like rate',d=>pc((F(d)||{}).like_rate),d=>(F(d)||{}).like_rate],
 ['Posts a week',d=>((F(d)||{}).per_week??'-'),d=>(F(d)||{}).per_week],['Peer standing',d=>{const p=((F(d)||{}).peers||[])[0];return p?(p.pct>=50?'Top '+(100-p.pct)+'%':'Bottom '+(p.pct||1)+'%')+' of '+p.group:'-'}],
 ['Avg live viewers (30d)',d=>fmt((d.live_30d||{}).avg_viewers),d=>(d.live_30d||{}).avg_viewers],['Peak live viewers (30d)',d=>fmt((d.live_30d||{}).peak_viewers),d=>(d.live_30d||{}).peak_viewers],
 ['Hours live (30d)',d=>fmt((d.live_30d||{}).hours),d=>(d.live_30d||{}).hours],['Chat messages per hour',d=>fmt((d.chat_30d||{}).msgs_per_hour),d=>(d.chat_30d||{}).msgs_per_hour],
 ['Positive chat mood',d=>pc(((d.chat_30d||{}).mood||{}).positive),d=>((d.chat_30d||{}).mood||{}).positive],['Viewer spending (30d, est.)',d=>usd(((d.chat_30d||{}).spending||{}).total_usd),d=>((d.chat_30d||{}).spending||{}).total_usd]];
const F=d=>{const e=(d.engagement||{}).formats||{};return e.long||e.short||e.live};
let DATA=[];
(async()=>{const L=SL();if(!L.length){document.getElementById('t').innerHTML='<div class="cap">Nothing here yet. Open a creator\'s media kit (from their channel page) and press "Add to shortlist".</div>';return}
 DATA=(await Promise.all(L.map(x=>fetch('/api/kit?sid='+encodeURIComponent(x.sid)).then(r=>r.json()).catch(()=>null)))).filter(d=>d&&d.sid);
 const best=ROWS.map(r=>r[2]?Math.max(...DATA.map(d=>r[2](d)??-1)):null);
 document.getElementById('t').innerHTML=`<table><tr><th></th>${DATA.map(d=>`<th style="text-align:right"><a href="/kit/${encodeURIComponent(d.sid)}">${esc(d.name)}</a></th>`).join('')}</tr>${ROWS.map((r,i)=>`<tr><td>${r[0]}</td>${DATA.map(d=>`<td${r[2]&&best[i]>0&&r[2](d)===best[i]&&DATA.length>1?' style="color:var(--lime);font-weight:700"':''}>${esc(r[1](d))}</td>`).join('')}</tr>`).join('')}</table>`})();
document.getElementById('csv').onclick=()=>{const q=v=>'"'+String(v).replace(/"/g,'""')+'"';const lines=[['Metric',...DATA.map(d=>d.name)].map(q).join(','),...ROWS.map(r=>[r[0],...DATA.map(d=>r[1](d))].map(q).join(','))];
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['﻿'+lines.join('\n')],{type:'text/csv'}));a.download='shortlist.csv';a.click()};
document.getElementById('clr').onclick=()=>{try{localStorage.removeItem('lge_shortlist')}catch(e){}location.reload()};
</script></body></html>"""

DOCS = HEAD + r"""<div class="wrap"><h1 style="margin-top:20px">Data API</h1><div class="cap">For agencies and brands. JSON over HTTPS. Ask us for a key.</div>
<div class="card"><h2>Authentication</h2><p>Send your key in the <code>X-API-Key</code> header (or <code>?key=</code>). Each key has a daily call limit; the current count comes back in the <code>X-Calls-Today</code> and <code>X-Calls-Limit</code> headers.</p></div>
<div class="card"><h2>Endpoints</h2>
<p><code>GET /api/v1/creator?sid=yt:UC...</code><br>Everything on a media kit: audience, engagement and peer standing, live (30 days), chat (30 days), viewer spending, audience overlap, monthly history, best videos. <code>sid</code> is <code>yt:</code>+channel id, <code>twitch:</code>+login or <code>kick:</code>+slug.</p>
<p><code>GET /api/v1/rankings?platform=youtube&amp;metric=vday&amp;country=IN&amp;category=Gaming&amp;game=BGMI&amp;limit=1000</code><br>Channel rankings. metric: size, views, vday, v7, growth, eng, likes, medv, live.</p>
<p><code>GET /api/v1/streamers?region=in&amp;period=week&amp;metric=peak&amp;cat=bgmi</code><br>Live streamer rankings (hours watched, peak, average viewers, hours live) by day, week or month.</p>
<p><code>GET /api/v1/live?region=global</code><br>What's live right now, with viewers.</p>
<p><code>GET /api/v1/search?q=name</code><br>Find a creator's sid.</p></div>
<div class="card"><h2>Notes</h2><p class="cap">Public platform data. Engagement, benchmarks, chat analysis, audience overlap and spending are our own calculations and must be credited to __BRAND__ when shown. Not affiliated with YouTube, Twitch or Kick.</p></div></div></body></html>"""


def _page(tpl: str, **kw) -> str:
    out = tpl.replace("__BRAND__", html.escape(eventpage.BRAND))
    for k, v in kw.items():
        out = out.replace(k, v)
    return out


def kit_html(sid: str, name: str) -> str:
    return _page(KIT, __TITLE__=html.escape(f"{name} media kit | {eventpage.BRAND}"), __SID__=json.dumps(sid),
                 __SITE__=json.dumps(eventpage.SITE_URL), __BRANDJS__=json.dumps(eventpage.BRAND))


def shortlist_html() -> str:
    return _page(SHORT, __TITLE__=html.escape(f"Shortlist | {eventpage.BRAND}"))


def docs_html() -> str:
    return _page(DOCS, __TITLE__=html.escape(f"Data API | {eventpage.BRAND}"))


# ---------- API keys ----------

def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def key_create(name: str, daily: int = 10000) -> str:
    key = "lge_" + secrets.token_urlsafe(24)
    with store._lock:
        c = _db()
        c.execute("INSERT INTO api_keys VALUES (?,?,?,?,?,1)", (_hash(key), key[:10], name[:80], int(daily), int(time.time())))
        c.commit()
    return key


def key_list() -> list:
    from tracker import ytextra
    with store._lock:
        return [dict(r) | {"today": (_db().execute("SELECT calls FROM api_use WHERE khash=? AND day=?", (r["khash"], ytextra._day())).fetchone() or [0])[0]}
                for r in _db().execute("SELECT * FROM api_keys ORDER BY created")]


def key_revoke(prefix: str) -> int:
    with store._lock:
        c = _db()
        n = c.execute("UPDATE api_keys SET active=0 WHERE prefix=?", (prefix,)).rowcount
        c.commit()
    return n


def key_check(key: str):
    """(ok, calls today, limit, name). Counts the call when ok."""
    from tracker import ytextra
    if not key or not key.startswith("lge_"):
        return False, 0, 0, ""
    kh, day = _hash(key), ytextra._day()
    with store._lock:
        c = _db()
        k = c.execute("SELECT * FROM api_keys WHERE khash=? AND active=1", (kh,)).fetchone()
        if not k:
            return False, 0, 0, ""
        used = (c.execute("SELECT calls FROM api_use WHERE khash=? AND day=?", (kh, day)).fetchone() or [0])[0]
        if used >= k["daily"]:
            return False, used, k["daily"], k["name"]
        c.execute("INSERT INTO api_use VALUES (?,?,1) ON CONFLICT(khash, day) DO UPDATE SET calls=calls+1", (kh, day))
        c.commit()
    return True, used + 1, k["daily"], k["name"]
