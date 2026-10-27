"""The site's dashboard pages, one template for all of them:

  /  and /global                 overview: KPIs, sections, top live streams, top streamers today, tournaments, chart
  /s/<section>, /global/s/...    one section (Gaming, Esports, IRL, Just Chatting, News ...) with its games/categories
  /c/<game>, /global/c/...       one game or category

Numbers come from /api/scene (everything, every 30s) and /api/scene/live (what moves, every 2s), see tracker/scene.py.
Share cards are drawn on a canvas in the browser.
"""
import html
import json

from tracker import eventpage, scene

PANEL_CSS = r""".row.x{cursor:pointer}.row.x.open{background:#171722;border-bottom-color:transparent}.row .car{color:var(--muted);font-size:10px;margin-left:6px;display:inline-block;transition:transform .15s}.row.open .car{transform:rotate(90deg);color:var(--lime)}
.cx{background:#0f0f17;border-bottom:1px solid var(--line);border-left:2px solid var(--lime);padding:12px 14px 14px;font-size:13px}
.cxh{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center}.cxh .nm{font-weight:700;font-size:16px}.cxh .ds{font-size:12px;color:var(--muted)}
.cxtt{color:#c9c8d8;font-size:12px;margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cxt{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}.cxt th{font:500 11px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.05em;text-align:right;padding:4px 6px;border-bottom:1px solid var(--line)}
.cxt th:first-child,.cxt td:first-child{text-align:left;padding-left:0;color:var(--muted)}.cxt td{text-align:right;padding:5px 6px;font:600 15px "Barlow Condensed",sans-serif;border-bottom:1px solid #1c1c29}
.cxt td:first-child{font:400 13px "Barlow",sans-serif}.cxt tr td:nth-child(2){color:var(--lime)}
.cxg{margin-top:8px;color:var(--muted);font-size:12px}.cxg b{color:var(--ink);font-weight:500}
.cxs{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-top:10px}.cxs div{background:var(--card);padding:7px 9px;font-size:11px;color:var(--muted)}.cxs b{display:block;font:600 17px "Barlow Condensed",sans-serif;color:var(--ink)}
@media(max-width:600px){.cxs{grid-template-columns:repeat(3,1fr)}}
.cxc{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px}.cxc svg{width:100%;height:80px;display:block;margin-top:6px;background:var(--card)}.cxc .cap{font-size:11px;color:var(--muted);margin-top:4px}
.cxd{display:grid;gap:2px;margin-top:6px}.cxd div{display:grid;grid-template-columns:70px minmax(0,1fr) 80px 70px 60px;gap:8px;font-size:12px;padding:4px 0;border-bottom:1px solid #1c1c29;color:var(--muted)}
.cxd div span:nth-child(2){color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cxd b{color:var(--ink);font-weight:600}"""

PANEL_JS = r"""// ---------- one channel's analytics, opened under its row ----------
const CH={},CHT={};
const MONEY=(typeof REGION!=='undefined'&&REGION==='in')?'inr':'usd';
const money=v=>{v=+v||0;return MONEY==='inr'?'₹'+(v>=1e7?(v/1e7).toFixed(2)+' Cr':v>=1e5?(v/1e5).toFixed(2)+' L':Math.round(v).toLocaleString('en-IN')):'$'+(v>=1e6?(v/1e6).toFixed(2)+'M':v>=1e4?(v/1e3).toFixed(1)+'K':Math.round(v).toLocaleString('en-US'))};
function rowX(list,x,inner){const k=list+':'+x.sid,o=OPEN===k;return `<div class="row x${o?' open':''}" data-k="${esc(k)}">${inner}</div>${o?panel(x.sid):''}`}
function toggleRow(k){OPEN=OPEN===k?null:k;render();if(!OPEN)return;const sid=k.slice(2);if(CH[sid]&&Date.now()-CHT[sid]<30000)return;
 fetch('/api/channel?sid='+encodeURIComponent(sid)).then(r=>r.json()).then(j=>{CH[sid]=j;CHT[sid]=Date.now();render()}).catch(()=>{})}
const dshort=d=>new Date(d+'T12:00:00+05:30').toLocaleDateString('en-IN',{day:'numeric',month:'short'});
function barsSVG(days){const t=new Date(),M={};days.forEach(d=>M[d.day]=d);const L=[];for(let i=29;i>=0;i--){const d=new Date(t.getTime()-i*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'});L.push(M[d]||{day:d,peak:0})}
 const mx=Math.max(1,...L.map(d=>d.peak));return `<svg viewBox="0 0 300 80" preserveAspectRatio="none">${L.map((d,i)=>`<rect x="${i*10+1}" y="${80-76*d.peak/mx}" width="8" height="${76*d.peak/mx}" fill="${d.peak===mx?'#b6f23a':'#7a5cff'}"><title>${dshort(d.day)}: peak ${full(d.peak)}</title></rect>`).join('')}</svg>`}
function lineSVG(S){if(!S||S.length<2)return '<svg viewBox="0 0 300 80"></svg>';const t0=S[0][0],t1=S[S.length-1][0],mx=Math.max(1,...S.map(p=>p[1]));
 const pts=S.map(p=>`${(300*(p[0]-t0)/((t1-t0)||1)).toFixed(1)},${(78-74*p[1]/mx).toFixed(1)}`).join(' ');
 return `<svg viewBox="0 0 300 80" preserveAspectRatio="none"><polygon points="0,80 ${pts} 300,80" fill="rgba(182,242,58,.15)"/><polyline points="${pts}" fill="none" stroke="#b6f23a" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`}
function panel(sid){const c=CH[sid];if(!c)return '<div class="cx"><span class="muted">Loading channel analytics...</span></div>';if(!c.sid)return '<div class="cx"><span class="muted">No history for this channel yet.</span></div>';
 const P=c.periods,cols=[['today','TODAY'],['7d','7 DAYS'],['30d','30 DAYS'],['all','ALL TIME']],now=liveMap()[sid]||c.now,best=(c.days||[]).reduce((a,d)=>d.peak>(a?a.peak:0)?d:a,null);
 const R=[['Peak viewers','peak',fmt],['Average viewers','avg',fmt],['Hours watched','hw',v=>fmt(v)+'h'],['Hours streamed','hours',v=>v+'h'],['Days live','days',v=>v]];
 if(c.superchats){cols.forEach(k=>{P[k[0]].sc=c.superchats[k[0]][MONEY];P[k[0]].scn=c.superchats[k[0]].count;P[k[0]].mem=c.superchats[k[0]].members});
  R.push(['Super Chats','sc',money],['Paid messages','scn',v=>full(v)],['Memberships','mem',v=>full(v)])}
 const S=c.stats,g=(o,k)=>o&&o[k]!=null?(o[k]>=0?'+':'')+fmt(o[k]):'-';
 return `<div class="cx"><div class="cxh"><div style="min-width:0"><div class="ds">${now?`<span class="lv">LIVE</span>${full(now)} watching now`:c.last_live?'Last live '+ago(c.last_live):''}${c.country?' · '+esc(c.country):''}${c.first_seen?' · tracked since '+ist(c.first_seen,{day:'numeric',month:'short'}):''}</div></div><span style="display:flex;gap:6px"><a class="btn" style="text-decoration:none" href="${RP}/ch/${encodeURIComponent(sid)}">FULL STATS</a><button class="btn" data-ch="${esc(sid)}">SHARE</button><a class="btn" style="text-decoration:none;text-align:center" href="${esc(c.url)}" target="_blank" rel="noopener">${now?'WATCH':'OPEN'} ON ${(NAMES[c.platform]||'').toUpperCase()}</a></span></div>
 ${now&&c.title?`<div class="cxtt">${esc(c.title)}</div>`:''}
 <table class="cxt"><thead><tr><th></th>${cols.map(k=>`<th>${k[1]}</th>`).join('')}</tr></thead><tbody>${R.map(r=>`<tr><td>${r[0]}</td>${cols.map(k=>`<td>${r[2](P[k[0]][r[1]])}</td>`).join('')}</tr>`).join('')}</tbody></table>
 ${P['30d'].games.length?`<div class="cxg">Streams: <b>${P['30d'].games.map(esc).join(', ')}</b> (last 30 days)</div>`:''}
 ${c.platform==='youtube'&&!c.superchats?`<div class="cxg">Super Chats: ${c.sc_status==='reading'?'reading this stream\'s chat now; none paid yet.':'none recorded. Chat is read while a stream is among the 50 biggest YouTube streams live.'}</div>`:''}
 ${c.superchats&&c.sc_status==='reading'?'<div class="cxg"><span class="lv">LIVE</span>Reading this stream\'s Super Chats now.</div>':''}
 ${S?`<div class="cxs"><div><b>${S.subs!=null?fmt(S.subs):'hidden'}</b>subscribers</div><div><b>${fmt(S.views)}</b>total views</div><div><b>${full(S.videos||0)}</b>videos</div><div><b>${g(S.gain_1d,'views')}</b>views, last day</div><div><b>${g(S.gain_7d,'views')}</b>views, 7 days</div><div><b>${g(S.gain_7d,'subs')}</b>subs, 7 days</div></div>`:''}
 ${(c.top_superchats||[]).length?`<div class="lbl" style="margin-top:12px">Biggest Super Chats, 30 days</div><div class="cxd">${c.top_superchats.map(t=>`<div><span>${ist(t.ts,{day:'numeric',month:'short'})}</span><span>${esc(t.author)}${t.text?' · '+esc(t.text):''}</span><span><b>${esc(t.currency)} ${full(t.amount)}</b></span><span>${money(t[MONEY])}</span></div>`).join('')}</div>`:''}
 <div class="cxc"><div><div class="lbl">Peak viewers per day, 30 days</div>${barsSVG(c.days||[])}<div class="cap">${best?`Best day ${dshort(best.day)}: ${full(best.peak)} at once`:'No days recorded yet'}</div></div>
  <div><div class="lbl">Viewers, last 3 days</div>${lineSVG(c.recent)}<div class="cap">${(c.recent||[]).length>1?ist(c.recent[0][0],{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' to now':'Not enough readings yet'}</div></div></div>
 <div class="lbl" style="margin-top:12px">Recent days live</div><div class="cxd">${(c.days||[]).slice(-7).reverse().map(d=>`<div><span>${dshort(d.day)}</span><span>${esc(d.game)}</span><span>peak <b>${fmt(d.peak)}</b></span><span>avg ${fmt(d.avg)}</span><span>${d.hours}h live</span></div>`).join('')||'<span class="muted">Nothing recorded yet.</span>'}</div></div>`}
"""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__ | __BRAND__ (beta)</title>
<meta name="description" content="__DESC__">
<meta property="og:title" content="__TITLE__ | __BRAND__"><meta property="og:description" content="__DESC__">
<meta property="og:type" content="website"><meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;
--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e;--yt:#ff4d5e;--kick:#53fc18;--twitch:#a970ff}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
.mono,.lbl,.kpi .k,.lth,.crumb,.seg button,.ev .st,.upd,.rg,.brand,.beta{letter-spacing:.04em}
body{background:radial-gradient(900px 420px at 85% -15%,rgba(124,92,255,.13),transparent 60%),var(--bg);min-height:100vh}
a{color:inherit}.wrap{max-width:1200px;margin:0 auto;padding:0 16px 24px}
.mono,.lbl,th{font-family:"Barlow Condensed",sans-serif}.muted{color:var(--muted)}.sub{color:var(--muted);font-size:13px}
.lbl{color:var(--red);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.top{position:sticky;top:0;z-index:30;background:rgba(11,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1200px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;white-space:nowrap}
.rg{display:inline-flex;border:1px solid var(--line);font:12px "Barlow Condensed",sans-serif;flex:none}.rg a{padding:4px 10px;text-decoration:none;color:var(--muted)}.rg a.on{background:var(--lime);color:#0b0b12}
.upd{margin-left:auto;font:12px "Barlow Condensed",sans-serif;color:var(--muted);white-space:nowrap}.upd b{color:var(--ink);font-weight:400}
.beta{font:700 10px "Barlow Condensed",sans-serif;color:#0b0b12;background:var(--lime);padding:2px 6px;letter-spacing:.08em;margin-left:-6px;flex:none}
.secnav a i{display:none}.gmore{margin-top:12px;border:1px solid var(--line)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--red);margin-right:6px;box-shadow:0 0 8px var(--red);animation:pl 2s infinite}
@keyframes pl{50%{opacity:.35}}
.secnav{max-width:1200px;margin:0 auto;padding:0 16px;display:flex;flex-wrap:wrap;gap:0 2px;scrollbar-width:none}.secnav::-webkit-scrollbar{display:none}
.secnav a{flex:none;padding:9px 10px;text-decoration:none;color:var(--muted);font-size:14px;border-bottom:2px solid transparent;white-space:nowrap}
.secnav a b{font:12px "Barlow Condensed",sans-serif;font-weight:400;margin-left:6px;color:var(--muted)}
.secnav a.on{color:var(--ink);border-bottom-color:var(--lime)}.secnav a:hover{color:var(--ink)}
.crumb{font:12px "Barlow Condensed",sans-serif;color:var(--muted);margin-top:18px}.crumb a{text-decoration:none}.crumb a:hover{color:var(--lime)}
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:6px 0 4px;text-transform:uppercase;letter-spacing:.01em}h1 em{font-style:normal;color:var(--purple)}
.intro{color:#c9c8d8;margin:0;font-size:15px;max-width:780px}
.head .lbl,.head .sub:not(#chs){display:none}.head h2{font-size:20px}
.ic{background:linear-gradient(145deg,var(--c1),var(--c2))!important;color:#0b0b12}.ic svg{width:58%;height:58%}
.dl{font:600 11px "Barlow Condensed",sans-serif;margin-left:6px;letter-spacing:.02em}.dl.up{color:#3ddc84}.dl.dn{color:var(--red)}.dl.nw{color:var(--purple)}
.row .rk.r1{color:#ffd23f}.row .rk.r2{color:#d9dde8}.row .rk.r3{color:#ff9f5a}.row .rk.r1,.row .rk.r2,.row .rk.r3{font-weight:700;font-size:14px}
a.more{text-align:center;text-decoration:none;color:var(--lime)}
.row,.ev,.sc,.gc,.tc{transition:background .2s,border-color .2s}
.hero{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:10px;margin-top:16px}.hero.noglobe{grid-template-columns:1fr}
.kpis{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:10px}.hero:not(.noglobe) .kpis{grid-template-columns:repeat(3,1fr)}.hero:not(.noglobe) .kpi.main{grid-column:1/-1}
.gcard{background:radial-gradient(circle at 50% 58%,#18113d,var(--card) 70%);border:1px solid #3a2f6b;display:flex;flex-direction:column;min-width:0;position:relative}
.gsub{font-size:12px;color:var(--muted);margin-top:2px}.gcard .gh{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;padding:12px 14px 0}.gcard h2{font-size:17px}
.gcard iframe{border:0;width:100%;flex:1;min-height:250px;display:block;background:transparent}
.hchart{height:320px;margin-top:10px}#hc{width:100%;height:100%;display:block}
__PANEL_CSS__
.kpi{background:var(--card);border:1px solid var(--line);padding:14px;min-width:0;position:relative}
.kpi .k{font:11px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.kpi .v{font:700 34px "Barlow Condensed",sans-serif;margin-top:4px;line-height:1.1;white-space:nowrap}.kpi .s{font-size:12px;color:var(--muted);margin-top:4px}
.kpi.main{border-color:#3a2f6b;background:linear-gradient(160deg,rgba(124,92,255,.18),var(--card) 60%)}.kpi.main .v{font-size:50px}
.bar{display:flex;height:6px;margin-top:10px;background:var(--line);overflow:hidden}.bar div{height:100%;transition:width .8s cubic-bezier(.2,.8,.2,1)}
.leg{display:flex;flex-wrap:wrap;gap:4px 12px;font:11px "Barlow Condensed",sans-serif;color:var(--muted);margin-top:6px}.leg b{color:var(--ink);font-weight:400}
.sw{display:inline-block;width:8px;height:8px;margin-right:5px}
.kpi .shr{position:absolute;right:10px;top:10px}
.card{background:var(--card);border:1px solid var(--line);padding:16px;margin-top:12px;min-width:0}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}h2{margin:2px 0 0;font-size:19px;font-weight:700}
.btn{background:var(--lime);color:#0b0b12;border:0;font:700 11px "Barlow Condensed",sans-serif;padding:5px 10px;cursor:pointer;clip-path:polygon(7px 0,100% 0,100% calc(100% - 7px),calc(100% - 7px) 100%,0 100%,0 7px)}
.btn.ghost{background:none;color:var(--muted);border:1px solid var(--line);clip-path:none}
.secs{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:12px}
.sc{display:block;text-decoration:none;background:var(--card2);border:1px solid var(--line);padding:12px;min-width:0;transition:border-color .15s}
.sc:hover{border-color:var(--lime)}.sc .n{display:flex;align-items:center;gap:8px;font-weight:700}.sc .n svg{color:var(--lime);flex:none}
.sc .v{font:22px "Barlow Condensed",sans-serif;margin-top:6px}.sc .s{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc.zero{display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin-top:12px}
.gc{display:flex;gap:10px;align-items:center;text-decoration:none;background:var(--card2);border:1px solid var(--line);padding:10px;min-width:0}
.gc:hover{border-color:var(--lime)}.gc img,.gc .ph{width:42px;height:56px;border-radius:4px;object-fit:cover;flex:none;background:var(--card);display:grid;place-items:center;font-weight:700;color:#0b0b12}
.gc .n{font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gc .v{font:17px "Barlow Condensed",sans-serif}.gc .s{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.list{background:var(--card);border:1px solid var(--line);margin-top:12px;display:flex;flex-direction:column;min-width:0}
.lh{display:flex;align-items:center;gap:8px;padding:13px 14px;flex-wrap:wrap}.lh h2{font-size:17px;margin:0}.lh .r{margin-left:auto;display:flex;gap:6px;align-items:center}
.lth{display:flex;justify-content:space-between;padding:6px 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font:11px "Barlow Condensed",sans-serif;color:var(--muted);background:var(--card2)}
.row{display:grid;grid-template-columns:22px 38px minmax(0,1fr) auto;gap:10px;align-items:center;padding:8px 14px;text-decoration:none;border-bottom:1px solid #1c1c29}
.row:hover{background:#171722}.row .rk{font:12px "Barlow Condensed",sans-serif;color:var(--muted)}.row .rk.t{color:var(--lime)}
.row .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.row .ds{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .vv{text-align:right;font:14px "Barlow Condensed",sans-serif;white-space:nowrap}.row .vv small{display:block;font-size:11px;color:var(--muted)}
.lv{color:var(--red);font:10px "Barlow Condensed",sans-serif;margin-right:4px}.lv:before{content:"\25CF ";}
.av{position:relative;width:38px;height:38px}.av img,.av .ph{width:38px;height:38px;border-radius:50%;object-fit:cover;background:var(--card2);border:1px solid var(--line);display:grid;place-items:center;font:700 12px "Barlow",sans-serif;color:var(--muted)}
.av .bd{position:absolute;right:-3px;bottom:-3px;width:15px;height:15px;border-radius:4px;display:grid;place-items:center;font:700 9px "Barlow",sans-serif;color:#0b0b12;border:2px solid var(--card)}
.more{display:block;width:100%;background:var(--card2);border:0;border-top:1px solid var(--line);color:var(--ink);font:13px "Barlow",sans-serif;padding:11px;cursor:pointer;margin-top:auto}.more:hover{color:var(--lime)}
.seg{display:inline-flex;border:1px solid var(--line)}.seg button{background:none;border:0;color:var(--muted);font:11px "Barlow Condensed",sans-serif;padding:5px 8px;cursor:pointer}.seg button.on{background:var(--lime);color:#0b0b12}
.tools{display:flex;gap:8px;flex-wrap:wrap;padding:0 14px 10px}
input{background:var(--card2);border:1px solid var(--line);color:var(--ink);font:13px "Barlow Condensed",sans-serif;padding:6px 9px;min-width:0;flex:1}
.tours{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin-top:12px}
.tc{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:12px;align-items:center;background:var(--card2);border:1px solid var(--line);padding:12px}
.tc .ta{width:48px;height:64px;object-fit:cover;border-radius:4px;background:var(--card);display:grid;place-items:center;font-weight:700;color:#0b0b12}
.tc .tn{font-weight:700;font-size:16px}.tc .tg{font-size:12px;color:var(--muted);text-decoration:none}.tc .tv{font:20px "Barlow Condensed",sans-serif;text-align:right}.tc .tv small{display:block;font-size:11px;color:var(--muted)}
.tc .ts{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap}.tc .ts a{display:flex;align-items:center;gap:5px;font-size:12px;text-decoration:none;background:var(--card);border:1px solid var(--line);padding:2px 7px 2px 2px;border-radius:99px}
.tc .ts img,.tc .ts .ph{width:18px;height:18px;border-radius:50%;object-fit:cover;background:var(--line)}
.evs{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.ev{flex:1;min-width:240px;display:flex;justify-content:space-between;align-items:center;gap:10px;text-decoration:none;background:var(--card);border:1px solid var(--line);padding:12px 14px}
.ev.live{border-color:var(--red)}.ev .st{font:11px "Barlow Condensed",sans-serif;color:var(--lime)}.ev.live .st{color:var(--red)}.ev.ended .st{color:var(--muted)}
.ev .n{font-weight:700;font-size:16px}.ev .v{font:18px "Barlow Condensed",sans-serif;text-align:right}
#cv{width:100%;height:240px;display:block;margin-top:10px}
.sbtn{background:none;border:1px solid var(--line);color:var(--ink);width:32px;height:28px;display:grid;place-items:center;cursor:pointer;flex:none;padding:0}
.sbtn:hover,.sbtn.on{border-color:var(--lime);color:var(--lime)}
.sbox{display:none;max-width:1200px;margin:0 auto;padding:0 16px 10px;position:relative}.sbox.on{display:block}
.sbox input{width:100%;font:16px "Barlow",sans-serif;padding:10px 12px;border-color:#3a2f6b}
.sres{position:absolute;z-index:40;left:16px;right:16px;top:100%;margin-top:-6px;background:var(--bg2);border:1px solid var(--line);max-height:70vh;overflow:auto;box-shadow:0 20px 40px rgba(0,0,0,.5)}
.sres:empty{display:none}.sres .h{padding:8px 14px 4px;font:12px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.06em}
.sres .gc{margin:4px 14px;background:var(--card)}
.secnav a.mapl{color:var(--lime)}
.hist{margin-top:12px;display:grid;gap:5px}
.hr{display:grid;grid-template-columns:150px minmax(0,1fr) 64px;gap:10px;align-items:center;font-size:13px}
.hr .hb{height:16px;background:var(--line);position:relative}.hr .hb div{height:100%;background:linear-gradient(90deg,#5b47c8,var(--purple))}
.hr.rec .hb div{background:linear-gradient(90deg,#7fb21f,var(--lime))}.hr.cur .hb div{background:linear-gradient(90deg,#b8323f,var(--red))}
.hr .hv{text-align:right;font:600 15px "Barlow Condensed",sans-serif}.hr .hn{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hr.rec .hn,.hr.rec .hv{color:var(--lime)}
#k3p{color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#k3p a{text-decoration:none}#k3p a:hover{color:var(--lime)}
details.how{margin-top:14px;color:var(--muted);font-size:13px;line-height:1.6}details.how summary{cursor:pointer;color:var(--ink)}details.how b{color:var(--ink);font-weight:500}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.empty{padding:14px;color:var(--muted);font-size:14px}
.modal{position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.82);display:none;align-items:center;justify-content:center;padding:16px}
.modal.on{display:flex}.mbox{background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto}
.mbox img{width:100%;display:block;border:1px solid var(--line);margin:10px 0;min-height:120px}.mrow{display:flex;gap:8px;flex-wrap:wrap}#mhint{font-size:12px;color:var(--muted);margin-top:8px}
@media(max-width:1000px){.hero{grid-template-columns:1fr}.kpis{grid-template-columns:1fr 1fr}.kpi.main{grid-column:1/-1}.kpi.topk{grid-column:1/-1}.secs{grid-template-columns:repeat(3,1fr)}.two{grid-template-columns:1fr}}
@media(max-width:600px){
body{font-size:14px}.wrap{padding:0 12px 20px}
.top .in{padding:9px 12px;gap:10px}.brand{font-size:14px}.rg a{padding:3px 8px}.upd span{display:none}.upd{font-size:11px}
.secnav{padding:8px 12px 10px;gap:6px;flex-wrap:nowrap;overflow-x:auto;-webkit-mask-image:linear-gradient(90deg,#000 88%,transparent);mask-image:linear-gradient(90deg,#000 88%,transparent)}
.secnav a{display:flex;align-items:center;gap:6px;padding:6px 11px;border:1px solid var(--line);border-radius:99px;font-size:13px;background:var(--card)}
.secnav a i{display:inline-flex;color:var(--lime)}.secnav a b{margin-left:2px;font-size:11px}
.secnav a.on{background:var(--lime);color:#0b0b12;border-color:var(--lime)}.secnav a.on i,.secnav a.on b{color:#0b0b12}.secnav a.z{opacity:.5}
.crumb{margin-top:12px;font-size:11px}h1{font-size:24px;margin:4px 0}.intro{font-size:13px;color:var(--muted)}
.hero{margin-top:12px;gap:8px}.kpis,.hero:not(.noglobe) .kpis{grid-template-columns:repeat(3,1fr);gap:8px}.gcard iframe{min-height:280px}.hchart{height:250px}
.cx{padding:10px 12px 12px}.cxc{grid-template-columns:1fr}.cxt td{font-size:14px;padding:4px 3px}.cxt th{padding:4px 3px;font-size:10px}.cxt td:first-child{font-size:12px}
.cxd div{grid-template-columns:52px minmax(0,1fr) 64px 50px}.cxd div span:nth-child(5){display:none}.cxh .btn{grid-column:1/-1}.kpi{padding:10px}.kpi.main,.kpi.topk{grid-column:1/-1}.kpi.hwk{grid-column:auto}
.kpi .k{font-size:9.5px;letter-spacing:.03em}.kpi .v{font-size:19px}.kpi .s{display:none}.kpi.main .v{font-size:34px}.kpi.main .leg{font-size:10px}
.kpi.topk .row{grid-template-columns:34px minmax(0,1fr) auto!important}
.card{padding:12px}h2{font-size:16px}.head .sub{display:none}.head .lbl{font-size:10px}
.btn{font-size:10px;padding:4px 8px}
.secs{grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.sc{padding:9px}.sc .n{font-size:12px;gap:5px}.sc .n svg{width:14px;height:14px}
.sc .v{font-size:16px;margin-top:3px}.sc .s{display:none}.sc.zero{display:none}
.grid{display:flex;overflow-x:auto;gap:8px;scroll-snap-type:x mandatory;padding-bottom:4px;margin-right:-12px;scrollbar-width:none}.grid::-webkit-scrollbar{display:none}
.gc{flex:0 0 152px;scroll-snap-align:start;padding:8px;gap:8px}
.gc img,.gc .ph{width:36px;height:48px}.gc .n{font-size:13px}.gc .v{font-size:15px}.gc .s{display:none}
.two{gap:0}.list{margin-top:12px}.lh{padding:11px 12px;gap:6px}.lh h2{font-size:16px}.lh .r{margin-left:0;width:100%;justify-content:space-between}
.tools{padding:0 12px 8px}.seg button{padding:5px 7px;font-size:10px}.lth{padding:5px 12px}
.row{grid-template-columns:18px 34px minmax(0,1fr) auto;gap:8px;padding:8px 12px}.av,.av img,.av .ph{width:34px;height:34px}.row .nm{font-size:14px}.row .ds{font-size:11px}.row .vv{font-size:13px}
.tours{display:flex;overflow-x:auto;gap:8px;scroll-snap-type:x mandatory;margin-right:-12px;scrollbar-width:none}.tours::-webkit-scrollbar{display:none}
.tc{flex:0 0 86%;scroll-snap-align:start}
.evs{gap:8px}.ev{min-width:0;flex:1 1 100%;padding:10px 12px}
#cv{height:190px}details.how{font-size:12px}
.kpi #k3p{display:block;font-size:10.5px;margin-top:3px}.sbox{padding:0 12px 10px}.sres{left:12px;right:12px}
.hr{grid-template-columns:96px minmax(0,1fr) 52px;gap:8px;font-size:12px}.hr .hb{height:13px}.foot{font-size:11px}
}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta" title="Under testing: numbers may be incomplete or change">BETA</span><span class="rg" id="rg"></span><span class="upd"><span class="dot"></span><span>UPDATED </span><b id="upd">-</b></span><button class="sbtn" id="sbtn" aria-label="Search streamers"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg></button></div>
<div class="sbox" id="sbox"><input id="gs" type="search" placeholder="Search a streamer, stream title or game" autocomplete="off"><div class="sres" id="sres"></div></div>
<nav class="secnav" id="secnav"></nav></div>
<div class="wrap">
<div class="crumb" id="crumb"></div>
<h1 id="h1"></h1><p class="intro" id="intro"></p>
<div class="hero" id="hero"><div class="kpis">
 <div class="kpi main"><div class="k" id="k1l">Watching now</div><div class="v mono" id="k1">-</div><div class="bar" id="pbar"></div><div class="leg" id="pleg"></div><button class="btn shr" data-share="now">SHARE</button></div>
 <div class="kpi"><div class="k">Live channels</div><div class="v mono" id="k2">-</div><div class="s" id="k2s">streaming right now</div></div>
 <div class="kpi"><div class="k">Peak today</div><div class="v mono" id="k3">-</div><div class="s" id="k3s"></div><div class="s" id="k3p"></div></div>
 <div class="kpi hwk"><div class="k">Hours watched today</div><div class="v mono" id="k4">-</div><div class="s" id="k4s"></div></div>
 </div>
 <div class="gcard" id="gcardw"><div class="gh"><div><h2>Where the streamers are from</h2><div class="gsub">Viewers by the streamer's country. Grey: no located streamer live.</div></div><a class="btn" href="/map" style="text-decoration:none">OPEN MAP</a></div><iframe id="gframe" title="World map of live viewers" loading="lazy"></iframe></div>
</div>
<div id="evwrap"></div>
<div class="card" id="histcard" style="display:none"><div class="head"><div><div class="lbl" id="hl">Past events</div><h2 id="hh">Peak viewers of past tournaments</h2><div class="sub">Highest number watching at once, official broadcast plus co-streams.</div></div><button class="btn" data-share="hist">SHARE</button></div><div class="hchart"><canvas id="hc"></canvas></div></div>
<div class="card" id="secard"><div class="head"><div><div class="lbl">Sections</div><h2>What people are watching</h2><div class="sub">Viewers right now in each section. Tap one to open it.</div></div><button class="btn" data-share="sections">SHARE</button></div><div class="secs" id="secs"></div></div>
<div class="card" id="gcard"><div class="head"><div><div class="lbl" id="gl">Games</div><h2 id="gh">Games live now</h2><div class="sub">Tap one for its streams and top streamers.</div></div><button class="btn" data-share="cats">SHARE</button></div><div class="grid" id="grid"></div><button class="more gmore" id="gmore"></button></div>
<div class="two">
 <div class="list"><div class="lh"><span class="dot"></span><h2>Top live streams</h2><div class="r"><div class="seg" id="plat"></div><button class="btn" data-share="live">SHARE</button></div></div>
  <div class="lth"><span>STREAM</span><span>WATCHING NOW</span></div><div id="live"></div><button class="more" id="lmore"></button></div>
 <div class="list"><div class="lh"><h2 id="bh">Top streamers today</h2><div class="r"><div class="seg" id="per"></div><button class="btn" data-share="board">SHARE</button></div></div>
  <div class="lth"><span>STREAMER</span><span id="bm">HOURS WATCHED</span></div><div id="board"></div><button class="more" id="bmore"></button><a class="more" id="rlink"></a></div>
</div>
<div class="card" id="tourcard"><div class="head"><div><div class="lbl">Esports</div><h2 id="th">Tournaments live now</h2><div class="sub">Official broadcasts and co-streams added together per tournament.</div></div><button class="btn" data-share="tours">SHARE</button></div><div class="tours" id="tours"></div></div>
<div class="card"><div class="head"><div><div class="lbl">Over time</div><h2 id="ch">Day by day</h2><div class="sub" id="chs"></div></div><div style="display:flex;gap:6px"><div class="seg" id="cmode"></div><button class="btn" data-share="chart">SHARE</button></div></div><canvas id="cv"></canvas></div>
<details class="how"><summary>How these numbers are counted</summary><div id="note"></div></details>
<div class="foot"><span>Unofficial live streaming rankings by __BRAND__. Not affiliated with YouTube, Kick, Twitch or any publisher.</span><span>__SOCIAL__</span></div>
</div>
<div class="modal" id="modal"><div class="mbox"><div class="head"><h2>Share</h2><button class="btn ghost" id="mclose">CLOSE</button></div>
 <img id="mimg" alt="Share card"><div class="mrow"><button class="btn" id="mig">INSTAGRAM</button><button class="btn" id="mxb">X</button><button class="btn ghost" id="mdl">DOWNLOAD</button><button class="btn ghost" id="mcp">COPY LINK</button></div><div id="mhint"></div></div></div>
<script>
const CAT=__CAT__,CATNAME=__CATNAME__,SEC=__SEC__,REGION=__REGION__,SECTIONS=__SECTIONS__,GL=REGION==='global',RP=GL?'':'/india';
const SITE=__SITEURL__,PATH=RP+(CAT?'/c/'+CAT:SEC?'/s/'+SEC:'')||'/',PAGEURL=SITE+PATH;
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'};
const SECNAME=Object.fromEntries(SECTIONS),WHERE=GL?'worldwide':'in India';
let D=null,cmode='days',OPEN=null,per='today',sort='hw',plat='all',bplat='all',q='',lAll=false,bAll=false,LOGOS=true;
const _H={};function setH(id,h){const e=document.getElementById(id);if(e&&_H[id]!==h){_H[id]=h;e.innerHTML=h}}
const RM=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
// numbers count to their new value instead of jumping
const TW={};function tw(id,v,f){const e=document.getElementById(id);if(!e)return;v=+v||0;const o=TW[id];TW[id]=v;if(o===undefined||RM||o===v){e.textContent=f(v);return}
 const t0=performance.now(),st=t=>{if(TW[id]!==v)return;const k=Math.min(1,(t-t0)/700),q=1-Math.pow(1-k,3);e.textContent=f(o+(v-o)*q);if(k<1)requestAnimationFrame(st)};requestAnimationFrame(st)}
// list rows glide to their new rank instead of jumping (FLIP)
function flipH(id,h){const e=document.getElementById(id);if(!e||_H[id]===h)return;const pos={};e.querySelectorAll('[data-k]').forEach(r=>pos[r.dataset.k]=r.getBoundingClientRect().top);setH(id,h);if(RM)return;
 e.querySelectorAll('[data-k]').forEach(r=>{const p=pos[r.dataset.k];if(p===undefined){if(Object.keys(pos).length)r.animate([{opacity:0},{opacity:1}],{duration:450});return}
  const d=p-r.getBoundingClientRect().top;if(Math.abs(d)>1)r.animate([{transform:`translateY(${d}px)`},{transform:'none'}],{duration:550,easing:'cubic-bezier(.2,.8,.2,1)'})})}
function setT(id,t){const e=document.getElementById(id);if(e&&e.textContent!==t)e.textContent=t}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ist=(ts,o)=>new Date(ts*1000).toLocaleString('en-IN',Object.assign({timeZone:'Asia/Kolkata'},o));
const when=ts=>ts?ist(ts,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST':'';
const ago=ts=>{const s=Date.now()/1000-ts;return s<120?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const CU=sl=>RP+'/c/'+sl,SU=k=>RP+'/s/'+k,HOME=GL?'/':'/india';
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const HUE=g=>{let h=0;for(const ch of String(g))h=(h*31+ch.charCodeAt(0))%360;return `hsl(${h} 70% 62%)`};
const PER={today:'last 24 hours','7d':'last 7 days','30d':'last 30 days'},PERB={today:'today','7d':'last 7 days','30d':'last 30 days'};
const SCOPE=()=>(CAT?CATNAME:SEC?SECNAME[SEC]:'Live streaming')+' '+WHERE;
const ICON={overview:'<path d="M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z"/>',gaming:'<path d="M6 11h4M8 9v4M15 12h.01M18 10h.01M17.3 5H6.7a4 4 0 0 0-4 3.6L2 15a3 3 0 0 0 5.2 2L9 15h6l1.8 2a3 3 0 0 0 5.2-2l-.7-6.4A4 4 0 0 0 17.3 5z"/>',
 esports:'<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',irl:'<path d="M12 21s-6-5.3-6-11a6 6 0 0 1 12 0c0 5.7-6 11-6 11z"/><circle cx="12" cy="10" r="2"/>',
 'just-chatting':'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',news:'<path d="M4 5h13v14H6a2 2 0 0 1-2-2zM17 9h3v8a2 2 0 0 1-2 2M7 8h7M7 11h7M7 14h4"/>',
 music:'<path d="M9 18V6l11-2v12M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z"/>',sports:'<circle cx="12" cy="12" r="9"/><path d="M12 3a15 15 0 0 1 0 18M3 12h18"/>',
 devotional:'<path d="M12 3c1.5 2.5 3 4 3 6a3 3 0 0 1-6 0c0-2 1.5-3.5 3-6zM4 15h16l-2 5H6z"/>',podcasts:'<path d="M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/>',other:'<path d="M4 6h16v10H4zM9 20h6M12 16v4"/>',cricket:'<path d="M14.5 3.5l6 6-9.5 9.5-3-3zM8 16l-4.5 4.5M5 13l3 3"/><circle cx="17.5" cy="17.5" r="2.5"/>',
 football:'<circle cx="12" cy="12" r="9"/><path d="M12 7l4 3-1.5 4.5h-5L8 10zM12 7V3M16 10l4-1M14.5 14.5l2.5 3.5M9.5 14.5L7 18M8 10L4 9"/>',
 target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
 broadcast:'<circle cx="12" cy="12" r="2"/><path d="M8.5 15.5a5 5 0 0 1 0-7M15.5 8.5a5 5 0 0 1 0 7M5.6 18.4a9 9 0 0 1 0-12.8M18.4 5.6a9 9 0 0 1 0 12.8"/>',
 rank:'<path d="M5 21V10h4v11M10 21V4h4v17M15 21v-7h4v7"/>',globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>'};
const svg=(k,s)=>`<svg viewBox="0 0 24 24" width="${s||18}" height="${s||18}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[k]||ICON.other}</svg>`;
const av=x=>`<span class="av">${x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph>${ini(x.name)}</span>'">`:`<span class="ph">${ini(x.name)}</span>`}<span class="bd" style="background:${COL[x.platform]||'#888'}">${(x.platform||'?')[0].toUpperCase()}</span></span>`;
const CICON=g=>{const l=String(g).toLowerCase();return /cricket/.test(l)?'cricket':/football|fifa|fc\b|soccer/.test(l)?'football':/call of duty|cod|warzone|shoot|battle/.test(l)?'target':
 l==='news'?'news':l==='music'?'music':l==='devotional'?'devotional':/podcast/.test(l)?'podcasts':l==='irl'?'irl':/chatting/.test(l)?'just-chatting':/sport|kabaddi|tennis|basketball/.test(l)?'sports':l==='other'?'broadcast':/tournament/.test(l)?'esports':'gaming'};
const PAL2=[['#b6f23a','#5fb31f'],['#a58bff','#6b4fe0'],['#4cc9f0','#2a7fd4'],['#ffd23f','#f08c00'],['#ff8a9a','#e0405a'],['#53fc18','#1fae5b'],['#ff9f5a','#e0602a']];
const art=(g,a,cls)=>{if(a)return `<img class="${cls||''}" src="${esc(a)}" alt="" loading="lazy" referrerpolicy="no-referrer">`;let h=0;for(const ch of String(g))h=(h*31+ch.charCodeAt(0))%PAL2.length;
 return `<span class="${cls||''} ph ic" style="--c1:${PAL2[h][0]};--c2:${PAL2[h][1]}" title="${esc(g)}">${svg(CICON(g),24)}</span>`};
function seg(id,opts,cur,on){const e=document.getElementById(id);setH(id,opts.map(([v,l])=>`<button data-v="${v}" class="${v===cur?'on':''}">${l}</button>`).join(''));e.onclick=ev=>{const b=ev.target.closest('button');if(b)on(b.dataset.v)}}
{const tail=CAT?'/c/'+CAT:SEC?'/s/'+SEC:'';setH('rg',`<a href="${tail||'/'}" class="${GL?'on':''}">GLOBAL</a><a href="/india${tail}" class="${GL?'':'on'}">INDIA</a>`)}
setH('crumb',`<a href="${HOME}">${GL?'WORLDWIDE':'INDIA'}</a>`+(SEC||CAT?` / ${SEC?esc(SECNAME[SEC].toUpperCase()):''}${CAT?esc(CATNAME.toUpperCase()):''}`:' / OVERVIEW'));
setH('h1',CAT?`<em>${esc(CATNAME)}</em> live ${WHERE}`:SEC?`<em>${esc(SECNAME[SEC])}</em> live ${WHERE}`:GL?`Live streaming <em>worldwide</em>, right now`:`Live streaming <em>in India</em>, right now`);
setT('intro','YouTube, Kick and Twitch, updated every 2 seconds.');
document.getElementById('secard').style.display='none';
if(GL&&!CAT&&!SEC){document.getElementById('gframe').src='/map?embed=1'}else{document.getElementById('gcardw').remove();document.getElementById('hero').classList.add('noglobe')}
{const sb=document.getElementById('sbox'),gs=document.getElementById('gs'),sr=document.getElementById('sres');let st=null,sq='';
 document.getElementById('sbtn').onclick=()=>{const on=sb.classList.toggle('on');document.getElementById('sbtn').classList.toggle('on',on);if(on)gs.focus()};
 document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){e.preventDefault();sb.classList.add('on');gs.focus()}if(e.key==='Escape'){sb.classList.remove('on');sr.innerHTML=''}});
 gs.oninput=()=>{clearTimeout(st);st=setTimeout(async()=>{const v=gs.value.trim();sq=v;if(v.length<2){sr.innerHTML='';return}
  try{const j=await (await fetch('/api/search?region='+REGION+'&q='+encodeURIComponent(v))).json();if(sq!==v)return;
   const C=j.channels||[],G=j.categories||[];
   sr.innerHTML=(G.length?`<div class="h">GAMES & CATEGORIES</div>`+G.map(g=>`<a class="gc" href="${CU(esc(g.slug))}">${art(g.game,g.art)}<span class="n">${esc(g.game)}</span></a>`).join(''):'')+
    (C.length?`<div class="h">STREAMERS & STREAMS</div>`+C.map(x=>`<a class="row" href="${RP}/ch/${encodeURIComponent(x.sid)}"><span></span>${av(x)}<span style="min-width:0"><div class="nm">${esc(x.name)}</div><div class="ds">${x.now?`<span class="lv">LIVE</span>${full(x.now)} watching`:x.last_live?'Last live '+ago(x.last_live):''}${x.game?' · '+esc(x.game):''}</div>${x.title?`<div class="ds" style="color:${x.by==='title'?'var(--ink)':''}">${esc(x.title)}</div>`:''}</span><span class="vv">${fmt(Math.max(x.peak,x.now))}<small>best peak</small></span></a>`).join(''):'')||
    `<div class="empty">No streamer or stream title matching "${esc(v)}" has been seen live ${WHERE} yet.</div>`}catch(e){}},250)}}
if(CAT)document.getElementById('gcard').style.display='none';
const liveMap=()=>{const m={};(D.live||[]).forEach(x=>m[x.sid]=x.viewers);return m};
const liveList=()=>(D.live||[]).filter(x=>(plat==='all'||x.platform===plat)&&(!q||(x.name+' '+x.title+' '+x.game).toLowerCase().includes(q)));
const dl=d=>d===undefined?'':d===null?'<span class="dl nw">NEW</span>':d>0?`<span class="dl up">&#9650;${d}</span>`:d<0?`<span class="dl dn">&#9660;${-d}</span>`:'';
const boardList=()=>{const lm=liveMap();return (D.board||[]).filter(x=>bplat==='all'||x.platform===bplat).map(x=>({...x,now:lm[x.sid]||x.now||0})).sort((a,b)=>b[sort]-a[sort])};
function render(){if(!D)return;const K=D.kpis||{};
 updLabel();
 const S=D.sections||[];
 setH('secnav',`<a href="${HOME}" class="${!SEC&&!CAT?'on':''}"><i>${svg('overview',14)}</i>Overview<b>${D.fresh?fmt(D.india_total):''}</b></a><a href="/map" class="mapl"><i>${svg('globe',14)}</i>World map</a><a href="${RP}/rankings" class="mapl"><i>${svg('rank',14)}</i>Rankings</a>`+S.slice().sort((a,b)=>b.viewers-a.viewers).map(s=>`<a href="${SU(s.key)}" class="${SEC===s.key?'on':''}${s.viewers?'':' z'}"><i>${svg(s.key,14)}</i>${esc(s.name)}<b>${s.viewers?fmt(s.viewers):''}</b></a>`).join(''));
 if(!window._navScrolled){const on=document.querySelector('.secnav a.on');if(on&&on.scrollIntoView){on.scrollIntoView({inline:'center',block:'nearest'});window._navScrolled=1}}
 setT('k1l','Watching now'+(CAT||SEC?' · '+(CAT?CATNAME:SECNAME[SEC]):''));if(D.fresh)tw('k1',K.watching,full);else setT('k1','-');
 const tot=K.watching||1;setH('pbar',(D.platforms||[]).map(p=>`<div style="width:${100*p.viewers/tot}%;background:${COL[p.platform]}"></div>`).join(''));
 setH('pleg',(D.platforms||[]).map(p=>`<span><span class="sw" style="background:${COL[p.platform]}"></span>${p.name.toUpperCase()} <b>${fmt(p.viewers)}</b></span>`).join(''));
 if(D.fresh)tw('k2',K.live_channels,full);else setT('k2','-');setT('k2s',CAT||SEC?`${D.india_total?(100*K.watching/D.india_total).toFixed(1):0}% of everyone watching ${WHERE}`:'streaming right now');
 tw('k3',K.peak_today,fmt);setT('k3s',K.peak_today_at?'at '+ist(K.peak_today_at,{hour:'numeric',minute:'2-digit'})+' IST':'since midnight IST');
 {const p=K.peak_lead;setH('k3p',p?`led by <a href="${esc(p.url)}" target="_blank" rel="noopener"><b style="color:${COL[p.platform]||'inherit'}">${esc(p.name)}</b></a> ${fmt(p.viewers)}`:'')}
 tw('k4',K.hw_today,v=>fmt(v)+'h');setT('k4s',SEC==='esports'?`${full(K.channels_today||0)} tournaments today`:`${full(K.channels_today||0)} channels streamed today`);
 renderEvents();renderHist();
 setH('secs',S.slice().sort((a,b)=>b.viewers-a.viewers).map(s=>`<a class="sc${s.viewers?'':' zero'}" href="${SU(s.key)}"><div class="n">${svg(s.key)}${esc(s.name)}</div><div class="v">${fmt(s.viewers)}</div><div class="s">${s.channels} live${s.items&&s.items.length?' · '+s.items.map(i=>esc(i.name)).join(', '):''}</div></a>`).join(''));
 const C=(D.categories||[]);
 setT('gl',SEC?''+SECNAME[SEC]:'Games & categories');setT('gh',SEC?`${SECNAME[SEC]} live now, by ${SEC==='gaming'||SEC==='esports'?'game':'category'}`:'Games & categories live now');
 const gAll=window._gAll,gN=window.innerWidth<600?C.length:(gAll?C.length:18);
 setH('grid',C.slice(0,gN).map(g=>`<a class="gc" href="${CU(esc(g.slug))}">${art(g.game,g.art)}<span style="min-width:0"><div class="n">${esc(g.game)}</div><div class="v">${fmt(g.viewers)}</div><div class="s">${g.streams} live · ${esc(g.top)}</div></span></a>`).join('')||'<div class="empty">Nothing live here right now.</div>');
 {const gm=document.getElementById('gmore');gm.style.display=window.innerWidth>=600&&C.length>18?'block':'none';gm.textContent=gAll?'Show top 18':`Show all ${C.length} games & categories`;gm.onclick=()=>{window._gAll=!gAll;render()}}
 seg('plat',[['all','ALL'],['youtube','YT'],['kick','KICK'],['twitch','TWITCH']],plat,v=>{plat=v;lAll=false;render()});
 const L=liveList(),ll=lAll||q?L.slice(0,300):L.slice(0,10);
 flipH('live',ll.map((x,i)=>rowX('l',x,`<span class="rk${i<3?' r'+(i+1):''}">${i+1}</span>${av(x)}<span style="min-width:0"><div class="nm">${esc(x.name)}<span class="car">&#9654;</span></div><div class="ds">${CAT?'':esc(x.game)+' · '}${esc(x.title)}</div></span><span class="vv">${full(x.viewers)}</span>`)).join('')||'<div class="empty">Nothing live right now.</div>');
 const lm=document.getElementById('lmore');lm.style.display=L.length>10&&!q?'block':'none';lm.textContent=lAll?'Show top 10':`Show all ${L.length} live streams`;lm.onclick=()=>{lAll=!lAll;render()};
 seg('per',[['today','TODAY'],['7d','7D'],['30d','30D']],per,v=>{per=v;bAll=false;load()});
 const PH=window.innerWidth<600;
 setT('bh',(SEC==='esports'?'Biggest tournaments ':'Top streamers ')+PERB[per]);setT('bm',SEC==='esports'?'PEAK VIEWERS':{hw:'HOURS WATCHED',peak:'PEAK VIEWERS',avg:'AVERAGE VIEWERS'}[sort]);
 {const rl=document.getElementById('rlink');rl.style.display=SEC==='esports'?'none':'block';rl.href=RP+'/rankings?period='+({today:'day','7d':'week','30d':'month'}[per])+(CAT?'&cat='+CAT:'')+(SEC?'&sec='+SEC:'');rl.textContent='Full rankings: any day, week or month, by category and country'}
 if(SEC==='esports'){const TD=D.tour_day||[];
  setH('board',TD.slice(0,bAll?50:10).map((x,i)=>`<div class="row"><span class="rk${i<3?' t':''}">${i+1}</span><span class="av"><span class="ph">${svg('esports',16)}</span></span><span style="min-width:0"><div class="nm">${esc(x.name)}</div><div class="ds">peak at ${when(x.at)}</div></span><span class="vv">${fmt(x.peak)}</span></div>`).join('')||'<div class="empty">No tournaments seen yet in this period.</div>');
  const bm=document.getElementById('bmore');bm.style.display=TD.length>10?'block':'none';bm.textContent=bAll?'Show top 10':`Show all ${TD.length}`;bm.onclick=()=>{bAll=!bAll;render()}}
 else{const B=boardList(),bb=bAll?B.slice(0,300):B.slice(0,10);
  flipH('board',bb.map((x,i)=>rowX('b',x,`<span class="rk${i<3?' r'+(i+1):''}">${i+1}</span>${av(x)}<span style="min-width:0"><div class="nm">${esc(x.name)}${dl(x.delta)}<span class="car">&#9654;</span></div><div class="ds">${x.now?`<span class="lv">LIVE</span>${full(x.now)} watching`:x.last_live?'Last live '+ago(x.last_live):''}${CAT?'':' · '+esc(x.game)} · peak ${fmt(x.peak)}</div></span><span class="vv">${sort==='hw'?fmt(x.hw)+'h':fmt(x[sort])}<small>${sort==='hw'?'avg '+fmt(x.avg):fmt(x.hw)+'h watched'}</small></span>`)).join('')||'<div class="empty">No streamers recorded in this period yet.</div>');
  document.getElementById('bmore').style.display='none'}
 const T=D.tournaments||[];document.getElementById('tourcard').style.display=(T.length||SEC==='esports')?'':'none';
 setT('th',`Tournaments live now ${WHERE}`);
 setH('tours',T.map(t=>`<div class="tc">${art(t.game,t.art,'ta')}<span style="min-width:0"><div class="tn">${esc(t.name)}</div><a class="tg" href="${CU(esc(t.slug))}">${esc(t.game)}</a></span><span class="tv">${fmt(t.viewers)}<small>${t.streams} stream${t.streams>1?'s':''} · peak ${fmt(t.peak)}</small></span>
  <div class="ts">${t.top.slice(0,5).map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">${x.logo?`<img src="${esc(x.logo)}" alt="" referrerpolicy="no-referrer">`:'<span class="ph"></span>'}${esc(x.name)} <b class="mono" style="font-weight:400">${fmt(x.viewers)}</b></a>`).join('')}</div></div>`).join('')||'<div class="empty">No esports tournament is live right now. They show up here the moment one goes live.</div>');
 setT('ch',cmode==='days'?'Day by day':`Viewers over time, ${PER[per]}`);setT('chs',cmode==='days'?'Most watching at once each day (IST). Hours watched under each bar.':'Everyone watching at once, every scan.');
 seg('cmode',[['days','BY DAY'],['line',{today:'24H','7d':'7D','30d':'30D'}[per]+' LINE']],cmode,v=>{cmode=v;render()});drawChart();
 const miss=['kick','twitch'].filter(p=>!(D.keys||{})[p]).map(p=>NAMES[p]);
 setH('note',`<p><b>Watching now</b> is the number of people watching at this moment, added up across every live stream tracked on YouTube, Kick and Twitch (each platform's own count). <b>Live channels</b> is how many channels are streaming. <b>Peak today</b> is the highest "watching now" since midnight IST. <b>Hours watched</b> is viewers multiplied by time live. <b>Tap any streamer</b> for their peak, average viewers, hours watched and hours streamed today, over 7 and 30 days and all time. <b>Total views</b> are not shown: Kick and Twitch don't publish them for live streams, and for YouTube they count replays too, so they aren't comparable across platforms.</p>
  <p><b>What is tracked.</b> ${GL?`Worldwide: the top 500 live streams on Twitch, the top streams on Kick, YouTube's Live page and searches for every big game, esports and category, plus everything found for India. Streams under ${D.min} viewers are left out.`:`India: channels whose YouTube country is India, or whose stream language, script or title is Indian, plus channels added by hand. Streams under ${D.min} viewers are left out.`} New streams are found every ${Math.round(D.every/60)} minutes. Viewer counts refresh every 2 seconds for every Kick and Twitch stream and the biggest YouTube streams; smaller YouTube streams every ${Math.round(D.every/60)} minutes.</p>
  <p><b>Sections</b> come from the stream's category (Kick, Twitch) or title (YouTube). <b>Esports</b> streams are detected from tournament names in the title (VCT, LCK, IEM, BGIS, PMGC ...) and grouped with their co-streams. <b>Not a census:</b> YouTube has no complete list of live streams, so YouTube totals are a floor.${miss.length?` ${miss.join(' and ')} keys are missing, so those platforms are partly covered.`:''}</p>`);
}
function cdTxt(ns){const l=ns-Date.now()/1000;if(l<=0)return 'STARTING SOON';const d=Math.floor(l/86400),h=Math.floor(l%86400/3600),m=Math.floor(l%3600/60),s=Math.floor(l%60),p=n=>String(n).padStart(2,'0');return (d?d+'D ':'')+`${p(h)}:${p(m)}:${p(s)}`}
function renderEvents(){const E=(D.events||[]).filter(e=>e.state!=='off');
 setH('evwrap',E.length?`<div class="evs">${E.map(e=>`<a class="ev ${e.state}" href="${esc(e.url)}"><span><div class="st">${e.state==='live'?'● LIVE NOW · OUR TRACKER':e.state==='upcoming'?'STARTS IN':'FINISHED'}</div><div class="n">${esc(e.name)}</div></span><span class="v" data-ns="${e.state==='upcoming'?e.next_start:''}">${e.state==='live'?full(e.now):e.state==='upcoming'?cdTxt(e.next_start):'Peak '+fmt(e.peak)}</span></a>`).join('')}</div>`:'')}
function renderHist(){const H=D.history||[];document.getElementById('histcard').style.display=H.length?'':'none';if(!H.length)return;
 setT('hl',''+CATNAME+' viewership till date');setT('hh',`Peak viewers, every ${CATNAME} event`);drawHistCanvas()}
const EIMG={};function elogo(u){if(!u)return null;let im=EIMG[u];if(!im){im=EIMG[u]=new Image();im.onload=()=>drawHistCanvas();im.src=u}return im.complete&&im.naturalWidth?im:null}
function drawHistCanvas(){const cv=document.getElementById('hc');if(!cv||!D||!(D.history||[]).length)return;const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;if(!W)return;
 cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);drawHist(x,W,H,1)}
function drawHist(ctx,W,H,fs){const h=D.history,n=h.length,live=(D.events||[]).find(e=>e.state==='live'),cur=e=>live&&e.name===live.name;
 const pl=34*fs,pr=34*fs,LS=Math.min(48*fs,(W-68*fs)/Math.max(1,n-1)*.86),pt=40*fs,pb=LS+28*fs,cw=W-pl-pr,ch=H-pt-pb,mx=Math.max(...h.map(e=>e.peak))*1.15;
 const X=i=>pl+i*cw/Math.max(1,n-1),Y=v=>pt+ch-v/mx*ch,top=h.reduce((a,e,i)=>e.peak>h[a].peak?i:a,0),small=W/fs<620;
 ctx.strokeStyle='#262636';ctx.lineWidth=1;ctx.fillStyle='#8d8ca3';ctx.font=`${11*fs}px "Barlow Condensed",sans-serif`;ctx.textAlign='left';ctx.textBaseline='bottom';
 const stp=mx>1.5e6?5e5:mx>6e5?2e5:1e5;for(let v=stp;v<mx;v+=stp){ctx.beginPath();ctx.moveTo(pl,Y(v));ctx.lineTo(W-pr,Y(v));ctx.stroke();ctx.textAlign='right';ctx.fillText(Math.round(v/1000)+'K',W-2*fs,Y(v)-2);ctx.textAlign='left'}
 ctx.beginPath();h.forEach((e,i)=>i?ctx.lineTo(X(i),Y(e.peak)):ctx.moveTo(X(i),Y(e.peak)));ctx.lineTo(X(n-1),pt+ch);ctx.lineTo(X(0),pt+ch);ctx.closePath();
 const g=ctx.createLinearGradient(0,pt,0,pt+ch);g.addColorStop(0,'rgba(124,92,255,.45)');g.addColorStop(1,'rgba(124,92,255,0)');ctx.fillStyle=g;ctx.fill();
 ctx.beginPath();h.forEach((e,i)=>i?ctx.lineTo(X(i),Y(e.peak)):ctx.moveTo(X(i),Y(e.peak)));ctx.strokeStyle='#b6f23a';ctx.lineWidth=3*fs;ctx.shadowColor='#b6f23a';ctx.shadowBlur=10*fs;ctx.stroke();ctx.shadowBlur=0;ctx.textAlign='center';
 h.forEach((e,i)=>{const hi=i===top,lv=cur(e);ctx.beginPath();ctx.arc(X(i),Y(e.peak),(hi||lv?6:4)*fs,0,7);ctx.fillStyle=lv?'#ff4d5e':'#b6f23a';ctx.fill();
  if(!small||hi||lv||i%2===0){ctx.fillStyle=lv?'#ff4d5e':hi?'#b6f23a':'#eeeef5';ctx.font=`700 ${(small?11:13)*fs}px "Barlow Condensed",sans-serif`;ctx.textBaseline='bottom';ctx.fillText(Math.round(e.peak/1000)+'K',X(i),Y(e.peak)-8*fs)}
  const im=elogo(e.logo),ly=pt+ch+8*fs;
  if(im){const r=Math.min(LS/im.naturalWidth,LS/im.naturalHeight),w=im.naturalWidth*r,hh=im.naturalHeight*r;ctx.drawImage(im,X(i)-w/2,ly+(LS-hh)/2,w,hh)}
  else{ctx.fillStyle='#8d8ca3';ctx.font=`700 ${(small?8:11)*fs}px "Barlow Condensed",sans-serif`;ctx.textBaseline='middle';ctx.fillText(e.series==='LAUNCH'?(small?'LP':'LAUNCH'):e.series,X(i),ly+LS/2)}
  ctx.textBaseline='top';ctx.fillStyle=lv?'#ff4d5e':hi?'#b6f23a':'#8d8ca3';ctx.font=`${(small?10:12)*fs}px "Barlow Condensed",sans-serif`;ctx.fillText((small?'':e.series==='LAUNCH'?'LAUNCH ':e.series+' ')+`'${e.year}`,X(i),ly+LS+4*fs)});
 ctx.textAlign='left';ctx.textBaseline='top';ctx.fillStyle='#b6f23a';ctx.font=`700 ${14*fs}px "Barlow Condensed",sans-serif`;ctx.fillText(`ALL-TIME HIGH ${fmt(h[top].peak)} · ${h[top].name.toUpperCase()}`,pl,6*fs)}
__PANEL_JS__
['live','board'].forEach(id=>document.getElementById(id).addEventListener('click',e=>{const sh=e.target.closest('[data-ch]');if(sh){SHARESID=sh.dataset.ch;openShare('chan');return}if(e.target.closest('.cx'))return;const r=e.target.closest('.row.x');if(r)toggleRow(r.dataset.k)}));
function drawChart(){const cv=document.getElementById('cv'),dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;if(!W)return;
 cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,W,H);if(cmode==='days')plotDays(x,W,H,D.daily||[],1);else plot(x,W,H,D.series||[],1)}
function plotDays(x,W,H,S,fs){const pl=8*fs,pr=58*fs,pt=22*fs,pb=40*fs;x.font=`${11*fs}px "Barlow Condensed",sans-serif`;x.fillStyle='#8d8ca3';x.textAlign='left';
 if(!S.length){x.fillText('Fills in from the first full day of readings.',pl,H/2);return}
 const n=Math.max(S.length,7),mx=Math.max(...S.map(d=>d.peak))*1.15||1,bw=(W-pl-pr)/n,Y=v=>pt+(H-pt-pb)*(1-v/mx),best=S.reduce((a,d,i)=>d.peak>S[a].peak?i:a,0);
 x.strokeStyle='#262636';x.lineWidth=1;for(let i=0;i<=4;i++){const y=pt+(H-pt-pb)*i/4;x.beginPath();x.moveTo(pl,y);x.lineTo(W-pr,y);x.stroke();x.fillText(fmt(mx*(1-i/4)),W-pr+6*fs,y+4*fs)}
 const every=Math.ceil(S.length/(W/fs<500?6:12));
 S.forEach((d,i)=>{const bx=pl+i*bw+bw*.18,w=bw*.64,y=Y(d.peak),last=i===S.length-1;
  const g=x.createLinearGradient(0,y,0,H-pb);g.addColorStop(0,i===best?'#b6f23a':last?'#c9b8ff':'#7a5cff');g.addColorStop(1,i===best?'rgba(182,242,58,.25)':'rgba(122,92,255,.2)');x.fillStyle=g;x.fillRect(bx,y,w,H-pb-y);
  x.textAlign='center';if(i===best||last||S.length<=10){x.fillStyle=i===best?'#b6f23a':'#eeeef5';x.font=`700 ${12*fs}px "Barlow Condensed",sans-serif`;x.fillText(fmt(d.peak),bx+w/2,y-6*fs)}
  if(i%every===0||last){x.fillStyle='#8d8ca3';x.font=`${11*fs}px "Barlow Condensed",sans-serif`;x.fillText(dshort(d.day),bx+w/2,H-pb+15*fs);x.fillStyle='#5d5c75';x.fillText(fmt(d.hw)+'h',bx+w/2,H-pb+29*fs)}});x.textAlign='left'}
function plot(x,W,H,S,fs){const pl=8*fs,pr=58*fs,pt=14*fs,pb=24*fs;
 x.font=`${11*fs}px "Barlow Condensed",sans-serif`;x.fillStyle='#8d8ca3';x.textAlign='left';
 if(S.length<2){x.fillText('The chart fills in as readings come in (one every 2 minutes).',pl,H/2);return}
 const t0=S[0][0],t1=S[S.length-1][0],mx=Math.max(...S.map(p=>p[1]))*1.12||1,X=t=>pl+(W-pl-pr)*(t-t0)/((t1-t0)||1),Y=v=>pt+(H-pt-pb)*(1-v/mx);
 x.strokeStyle='#262636';x.lineWidth=1;for(let i=0;i<=4;i++){const y=pt+(H-pt-pb)*i/4;x.beginPath();x.moveTo(pl,y);x.lineTo(W-pr,y);x.stroke();x.fillText(fmt(mx*(1-i/4)),W-pr+6*fs,y+4*fs)}
 const span=t1-t0,nt=W<500?2:4;for(let i=0;i<=nt;i++){const t=t0+span*i/nt;x.textAlign=i===0?'left':i===nt?'right':'center';x.fillText(span>2*86400?ist(t,{day:'numeric',month:'short'}):ist(t,{hour:'numeric',minute:'2-digit'}),X(t),H-6*fs)}x.textAlign='left';
 const g=x.createLinearGradient(0,pt,0,H-pb);g.addColorStop(0,'rgba(182,242,58,.28)');g.addColorStop(1,'rgba(182,242,58,0)');
 x.beginPath();S.forEach((p,i)=>i?x.lineTo(X(p[0]),Y(p[1])):x.moveTo(X(p[0]),Y(p[1])));x.lineTo(X(t1),H-pb);x.lineTo(X(t0),H-pb);x.closePath();x.fillStyle=g;x.fill();
 x.beginPath();S.forEach((p,i)=>i?x.lineTo(X(p[0]),Y(p[1])):x.moveTo(X(p[0]),Y(p[1])));x.strokeStyle='#b6f23a';x.lineWidth=2.2*fs;x.shadowColor='rgba(182,242,58,.6)';x.shadowBlur=10*fs;x.stroke();x.shadowBlur=0;
 const pk=S.reduce((a,p)=>p[1]>a[1]?p:a,S[0]);x.fillStyle='#b6f23a';x.beginPath();x.arc(X(pk[0]),Y(pk[1]),4*fs,0,7);x.fill();
 x.font=`700 ${12*fs}px "Barlow",sans-serif`;const right=X(pk[0])>W-pr-90*fs;x.textAlign=right?'right':'left';x.fillText('PEAK '+fmt(pk[1]),X(pk[0])+(right?-8:8)*fs,Y(pk[1])-6*fs);x.textAlign='left'}
window.addEventListener('resize',()=>{if(D){drawChart();drawHistCanvas()}});
let cur=null;
function loadImg(u){return new Promise(r=>{if(!u||!LOGOS)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
function base(title,sub){const c=document.createElement('canvas');c.width=2160;c.height=2700;const x=c.getContext('2d');x.scale(2,2);
 x.fillStyle='#0b0b12';x.fillRect(0,0,1080,1350);const g=x.createRadialGradient(860,-60,10,860,-60,700);g.addColorStop(0,'rgba(124,92,255,.22)');g.addColorStop(1,'rgba(124,92,255,0)');x.fillStyle=g;x.fillRect(0,0,1080,1350);
 x.fillStyle='#b6f23a';x.font='30px "Barlow Condensed",sans-serif';x.fillText('letsgrowesports',72,96);
 x.fillStyle='#ffffff';x.font='700 64px "Barlow Condensed",sans-serif';x.fillText(title.slice(0,28),72,170);x.fillStyle='#8d8ca3';x.font='28px "Barlow Condensed",sans-serif';x.fillText(sub.slice(0,60),72,218);
 x.fillStyle='#262636';x.fillRect(72,250,936,2);x.fillStyle='#8d8ca3';x.font='26px "Barlow Condensed",sans-serif';x.fillText(PAGEURL.replace('https://',''),72,1290);
 x.textAlign='right';x.fillText(ist(Date.now()/1000,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST',1008,1290);x.textAlign='left';return [c,x]}
function listRows(x,R,avs){R.slice(0,10).forEach((r,i)=>{const y=290+i*96;x.fillStyle=i<3?'#b6f23a':'#8d8ca3';x.font='700 34px "Barlow Condensed",sans-serif';x.fillText(String(i+1).padStart(2,'0'),72,y+46);
  const im=avs&&avs[i];let tx=150;if(im){x.save();x.beginPath();x.arc(178,y+34,28,0,7);x.clip();x.drawImage(im,150,y+6,56,56);x.restore();tx=226}
  x.fillStyle='#ffffff';x.font='700 34px "Barlow",sans-serif';let n=r.name;while(x.measureText(n).width>560-(tx-150)&&n.length>3)n=n.slice(0,-2);if(n!==r.name)n+='…';x.fillText(n,tx,y+32);
  x.font='22px "Barlow Condensed",sans-serif';x.fillStyle=r.color||'#8d8ca3';x.fillText((r.tag||'').slice(0,46),tx,y+64);
  x.textAlign='right';x.fillStyle='#ffffff';x.font='700 40px "Barlow Condensed",sans-serif';x.fillText(r.value,1008,y+46);x.textAlign='left';x.fillStyle='#1d1d2b';x.fillRect(72,y+84,936,1)})}
let SHARESID=null;
async function card(type){let c,x,text;const sc=SCOPE(),K=D.kpis||{};
 if(type==='chan'){const ch=CH[SHARESID];if(!ch)return card('board');const P=ch.periods,bi=(D.board||[]).findIndex(b=>b.sid===SHARESID),rk=bi>=0?bi+1:null,now=liveMap()[SHARESID]||ch.now;
  [c,x]=base(ch.name.toUpperCase().slice(0,26),`${(NAMES[ch.platform]||'').toUpperCase()}${ch.country?' · '+ch.country.toUpperCase():''} · ${GL?'WORLDWIDE':'INDIA'}`);
  const im=await loadImg(ch.logo);if(im){x.save();x.beginPath();x.arc(944,150,64,0,7);x.clip();x.drawImage(im,880,86,128,128);x.restore()}
  x.fillStyle='#13131c';x.fillRect(72,290,936,200);x.fillStyle=rk&&rk<=3?['#ffd23f','#d9dde8','#ff9f5a'][rk-1]:'#b6f23a';x.font='700 150px "Barlow Condensed",sans-serif';x.fillText(rk?'#'+rk:'-',100,445);
  x.fillStyle='#8d8ca3';x.font='28px "Barlow Condensed",sans-serif';x.fillText(rk?`RANK ${PERB[per].toUpperCase()} · ${sc.toUpperCase()}`.slice(0,44):'NOT RANKED IN THIS VIEW',340,350);
  x.fillStyle='#ffffff';x.font='700 46px "Barlow Condensed",sans-serif';x.fillText(now?`LIVE · ${full(now)} WATCHING`:`PEAK TODAY ${fmt(P.today.peak)}`,340,410);
  const t=[['PEAK TODAY',fmt(P.today.peak)],['AVG VIEWERS 7D',fmt(P['7d'].avg)],['HOURS WATCHED 30D',fmt(P['30d'].hw)+'h'],['ALL-TIME PEAK',fmt(P.all.peak)],['HOURS STREAMED 30D',P['30d'].hours+'h'],['DAYS LIVE 30D',String(P['30d'].days)]];
  t.forEach(([l,v],i)=>{const X=72+(i%3)*316,Y=520+Math.floor(i/3)*190;x.fillStyle='#13131c';x.fillRect(X,Y,300,170);x.fillStyle='#ff4d5e';x.font='22px "Barlow Condensed",sans-serif';x.fillText(l,X+22,Y+40);x.fillStyle='#ffffff';x.font='700 72px "Barlow Condensed",sans-serif';x.fillText(v,X+22,Y+125)});
  x.fillStyle='#ff4d5e';x.font='24px "Barlow Condensed",sans-serif';x.fillText('PEAK VIEWERS PER DAY · LAST 30 DAYS',72,935);
  const M={};(ch.days||[]).forEach(d=>M[d.day]=d.peak);const L=[];for(let i=29;i>=0;i--)L.push(M[new Date(Date.now()-i*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'})]||0);const mx=Math.max(1,...L);
  L.forEach((v,i)=>{const h=260*v/mx;x.fillStyle=v===mx?'#b6f23a':'#7a5cff';x.fillRect(72+i*31.2,1230-h,24,h)});
  text=`${ch.name}${rk?` is #${rk} ${WHERE} ${PERB[per]}`:''}: peak ${fmt(P.today.peak)} today, all-time peak ${fmt(P.all.peak)}, ${fmt(P['30d'].hw)} hours watched in 30 days.`;return [c,text]}
 if(type==='now'){[c,x]=base((CAT||SEC?(CAT?CATNAME:SECNAME[SEC]):'LIVE STREAMING').toUpperCase(),`${GL?'Worldwide':'India'} · YouTube + Kick + Twitch · right now`);
  const tiles=[['WATCHING NOW',full(K.watching)],['LIVE CHANNELS',full(K.live_channels)],['PEAK TODAY',fmt(K.peak_today)],['HOURS WATCHED TODAY',fmt(K.hw_today)+'h']];
  tiles.forEach(([l,v],i)=>{const X=72+(i%2)*474,Y=300+Math.floor(i/2)*210;x.fillStyle='#13131c';x.fillRect(X,Y,462,190);x.fillStyle='#ff4d5e';x.font='24px "Barlow Condensed",sans-serif';x.fillText(''+l,X+24,Y+44);x.fillStyle='#ffffff';x.font=`700 ${i?72:80}px "Barlow Condensed",sans-serif`;x.fillText(v,X+24,Y+140)});
  const T=(CAT?D.live.map(s=>[s.name,s.viewers]):SEC?(D.categories||[]).map(g=>[g.game,g.viewers]):(D.sections||[]).filter(s=>s.viewers).map(s=>[s.name,s.viewers])).slice(0,5);
  x.fillStyle='#ff4d5e';x.font='28px "Barlow Condensed",sans-serif';x.fillText(CAT?'TOP STREAMS':SEC?'TOP GAMES':'BY SECTION',72,770);
  T.forEach((r,i)=>{const y=840+i*80;x.fillStyle=i===0?'#b6f23a':'#ffffff';x.font='700 40px "Barlow",sans-serif';x.fillText(`${i+1}. ${r[0]}`.slice(0,30),72,y);x.textAlign='right';x.font='700 40px "Barlow Condensed",sans-serif';x.fillText(fmt(r[1]),1008,y);x.textAlign='left'});
  text=`${sc}: ${full(K.watching)} watching right now across ${full(K.live_channels)} live channels on YouTube, Kick and Twitch. Peak today ${fmt(K.peak_today)}.`}
 else if(type==='chart'&&cmode==='days'){const S=D.daily||[],b=S.reduce((a,d)=>d.peak>(a?a.peak:0)?d:a,null);[c,x]=base(sc.toUpperCase(),'Day by day, peak watching at once');x.fillStyle='#ff4d5e';x.font='30px "Barlow Condensed",sans-serif';x.fillText('BEST DAY',72,320);
  x.fillStyle='#ffffff';x.font='700 150px "Barlow Condensed",sans-serif';x.fillText(b?fmt(b.peak):'-',64,460);x.fillStyle='#8d8ca3';x.font='28px "Barlow Condensed",sans-serif';x.fillText(b?dshort(b.day):'',72,505);
  x.save();x.translate(40,560);plotDays(x,1000,640,S,1.7);x.restore();text=`${sc}: best day ${b?fmt(b.peak)+' watching at once on '+dshort(b.day):'-'}.`}
 else if(type==='chart'){[c,x]=base(sc.toUpperCase(),`Viewers over time, ${PER[per]}`);x.fillStyle='#ff4d5e';x.font='30px "Barlow Condensed",sans-serif';x.fillText('PEAK, '+PER[per].toUpperCase(),72,320);
  x.fillStyle='#ffffff';x.font='700 150px "Barlow Condensed",sans-serif';x.fillText(D.peak?fmt(D.peak.viewers):'-',64,450);x.fillStyle='#8d8ca3';x.font='28px "Barlow Condensed",sans-serif';x.fillText(D.peak?when(D.peak.ts):'',72,500);
  x.save();x.translate(40,560);plot(x,1000,640,D.series||[],1.7);x.restore();text=`${sc}: peak ${D.peak?full(D.peak.viewers):'-'} watching at once in the ${PER[per]}.`}
 else if(type==='sections'){[c,x]=base('WHAT PEOPLE ARE WATCHING',`${GL?'Worldwide':'India'} · by section, live now`);const R=(D.sections||[]).filter(s=>s.viewers).slice(0,10);
  listRows(x,R.map(s=>({name:s.name,tag:`${s.channels} live · ${(s.items||[]).map(i=>i.name).join(', ')}`,value:fmt(s.viewers)})));text=`What ${GL?'the world':'India'} is watching live right now: ${R.slice(0,3).map((s,i)=>`${i+1}. ${s.name} ${fmt(s.viewers)}`).join(' | ')}.`}
 else if(type==='cats'){const R=(D.categories||[]).slice(0,10);[c,x]=base((SEC?SECNAME[SEC]:'GAMES').toUpperCase()+' LIVE NOW',GL?'Worldwide':'India');listRows(x,R.map(g=>({name:g.game,tag:`${g.streams} live · top: ${g.top}`,value:fmt(g.viewers)})));
  text=`${SEC?SECNAME[SEC]:'Games'} live now ${WHERE}: ${R.slice(0,3).map((g,i)=>`${i+1}. ${g.game} ${fmt(g.viewers)}`).join(' | ')}.`}
 else if(type==='tours'){const T=(D.tournaments||[]).slice(0,10);[c,x]=base('ESPORTS LIVE NOW',`Tournaments ${WHERE} · official + co-streams`);listRows(x,T.map(t=>({name:t.name,tag:`${t.game} · ${t.streams} streams`,value:fmt(t.viewers)})));
  text=`Esports live now ${WHERE}: ${T.slice(0,3).map((t,i)=>`${i+1}. ${t.name} ${fmt(t.viewers)}`).join(' | ')}.`}
 else if(type==='live'){const L=liveList().slice(0,10);[c,x]=base('TOP LIVE STREAMS',sc);const avs=await Promise.all(L.map(s=>loadImg(s.logo)));
  listRows(x,L.map(s=>({name:s.name,tag:`${(NAMES[s.platform]||'').toUpperCase()} · ${s.game} · PEAK TODAY ${fmt(s.peak||s.viewers)}`,color:COL[s.platform],value:fmt(s.viewers)})),avs);text=`Top live streams ${WHERE} right now: ${L.slice(0,3).map((s,i)=>`${i+1}. ${s.name} ${fmt(s.viewers)}`).join(' | ')}.`}
 else if(type==='hist'){const mx=Math.max(...(D.history||[]).map(h=>h.peak)),r=(D.history||[]).find(h=>h.peak===mx);[c,x]=base(CATNAME.toUpperCase()+' VIEWERSHIP TILL DATE','Peak viewers, every event, official + co-streams');
  x.save();x.translate(40,330);drawHist(x,1000,820,1.7);x.restore();text=`${CATNAME} viewership till date: all-time high ${r?fmt(r.peak)+' ('+r.name+')':''}.`}
 else{const B=boardList().slice(0,10),lab={hw:'hours watched',peak:'peak viewers',avg:'average viewers'}[sort],val=s=>sort==='hw'?fmt(s.hw)+'h':fmt(s[sort]);[c,x]=base('TOP STREAMERS',`${sc} · ${PERB[per]} · ${lab}`);const avs=await Promise.all(B.map(s=>loadImg(s.logo)));
  listRows(x,B.map(s=>({name:s.name,tag:`${s.delta===null?'NEW · ':s.delta>0?'▲'+s.delta+' · ':s.delta<0?'▼'+(-s.delta)+' · ':''}${(NAMES[s.platform]||'').toUpperCase()} · PEAK ${fmt(s.peak)} · AVG ${fmt(s.avg)}`,color:s.delta>0?'#3ddc84':s.delta<0?'#ff4d5e':COL[s.platform],value:val(s)})),avs);text=`Top streamers ${WHERE}, ${PERB[per]} by ${lab}: ${B.slice(0,3).map((s,i)=>`${i+1}. ${s.name} ${val(s)}`).join(' | ')}.`}
 return [c,text]}
async function openShare(type){if(!D)return;try{await document.fonts.ready}catch(e){}const mi=document.getElementById('mimg');mi.removeAttribute('src');mi.alt='Making the image...';cur=null;setT('mhint','');document.getElementById('modal').classList.add('on');
 const name=`${CAT||SEC||(GL?'global':'india')}-${type}.png`,done=(b,text)=>{cur={blob:b,name,text};mi.src=URL.createObjectURL(b)};
 let [c,text]=await card(type);try{c.toBlob(b=>done(b,text),'image/png')}catch(e){LOGOS=false;[c,text]=await card(type);LOGOS=true;c.toBlob(b=>done(b,text),'image/png')}}
document.querySelectorAll('[data-share]').forEach(b=>b.onclick=()=>openShare(b.dataset.share));
document.getElementById('mclose').onclick=()=>document.getElementById('modal').classList.remove('on');
document.getElementById('modal').onclick=e=>{if(e.target.id==='modal')e.target.classList.remove('on')};
document.getElementById('mdl').onclick=()=>{if(!cur)return;const a=document.createElement('a');a.href=URL.createObjectURL(cur.blob);a.download=cur.name;a.click()};
document.getElementById('mcp').onclick=()=>{try{navigator.clipboard.writeText(PAGEURL)}catch(e){}setT('mhint','Link copied: '+PAGEURL)};
async function shareTo(app){if(!cur)return;const f=new File([cur.blob],cur.name,{type:'image/png'}),t=cur.text+' '+PAGEURL+' @letsgrowesports';
 if(/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)&&navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){if(e&&e.name==='AbortError')return}}
 document.getElementById('mdl').click();
 if(app==='x')window.open('https://x.com/intent/post?text='+encodeURIComponent(cur.text+' '+PAGEURL+' via @letsgrowesports'),'_blank','noopener');
 else{window.open('https://www.instagram.com/','_blank','noopener');setT('mhint','Image downloaded. Upload it as a post or story on Instagram.')}}
document.getElementById('mig').onclick=()=>shareTo('ig');document.getElementById('mxb').onclick=()=>shareTo('x');
const QS=()=>'region='+REGION+(SEC?'&sec='+SEC:'')+(CAT?'&cat='+CAT:'');
async function load(){try{const r=await fetch('/api/scene?'+QS()+'&period='+per+'&t='+Math.floor(Date.now()/20000),{cache:'no-store'});D=await r.json();LASTOK=Date.now();render()}catch(e){}}
let LASTOK=0;function updLabel(){const a=LASTOK?Math.round((Date.now()-LASTOK)/1000):null,old=D&&D.updated&&Date.now()/1000-D.updated>600;
 setT('upd',old?'paused '+Math.round((Date.now()/1000-D.updated)/60)+' min':a===null?'-':a+'s ago')}
async function loadLive(){if(!D||document.hidden)return;try{const r=await fetch('/api/scene/live?'+QS()+'&t='+Math.floor(Date.now()/2000),{cache:'no-store'});const j=await r.json();
 ['updated','fresh','india_total','live_total','live_count','kpis','sections','platforms','categories','tournaments','live'].forEach(k=>D[k]=j[k]);LASTOK=Date.now();render()}catch(e){}}
load();setInterval(load,30000);setInterval(loadLive,2000);
setInterval(()=>{if(!D)return;updLabel();
 document.querySelectorAll('.ev .v[data-ns]').forEach(e=>{if(e.dataset.ns)e.textContent=cdTxt(+e.dataset.ns)})},1000);
</script></body></html>"""


def build_html(cat: str = "", cat_name: str = "", region: str = "in", sec: str = "") -> str:
    region = "global" if region == "global" else "in"
    where = "worldwide" if region == "global" else "in India"
    if cat:
        title = f"{cat_name} live {where}: viewers and top streamers"
        desc = f"Every {cat_name} live stream {where} on YouTube, Kick and Twitch: watching now, top streamers today."
    elif sec:
        name = scene.SECTION_NAMES.get(sec, sec)
        title = f"{name} live {where}"
        desc = f"Every {name} live stream {where} on YouTube, Kick and Twitch, updated every 2 seconds."
    else:
        title = "Live Streaming " + ("Worldwide" if region == "global" else "in India") + ", Right Now"
        desc = (f"How many people are watching live streams {where} on YouTube, Kick and Twitch right now: top streams, "
                "top streamers, gaming, esports tournaments, IRL, news and more, updated every 2 seconds.")
    home = "/" if region == "global" else "/india"
    return (PAGE.replace("__PANEL_JS__", PANEL_JS).replace("__PANEL_CSS__", PANEL_CSS).replace("__TITLE__", html.escape(title)).replace("__DESC__", html.escape(desc))
                .replace("__CATNAME__", json.dumps(cat_name)).replace("__CAT__", json.dumps(cat))
                .replace("__SEC__", json.dumps(sec)).replace("__REGION__", json.dumps(region))
                .replace("__SECTIONS__", json.dumps(scene.SECTIONS)).replace("__HOME__", home)
                .replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__SITEURL__", json.dumps(eventpage.SITE_URL))
                .replace("__SOCIAL__", " · ".join(f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener">{html.escape(h)}</a>'
                                                     for _, u, h in eventpage.SOCIAL)))
