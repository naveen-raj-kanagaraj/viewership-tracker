"""/compare?c=yt:UC...,kick:slug: up to four channels side by side (any platform): lifetime counters, posts in the
range, live numbers, ranks, and charts of average views per post and channel views per day. Data: /api/compare."""
import html
import json

from tracker import eventpage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Compare channels | __BRAND__ (beta)</title>
<meta name="description" content="Compare YouTube, Twitch and Kick channels side by side: subscribers, views, engagement, live viewers.">
<meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body{background:radial-gradient(900px 420px at 85% -15%,rgba(124,92,255,.13),transparent 60%),var(--bg);min-height:100vh}a{color:inherit}
.top{position:sticky;top:0;z-index:30;background:rgba(11,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;letter-spacing:.04em;white-space:nowrap}
.beta{font:700 10px "Barlow Condensed",sans-serif;color:#0b0b12;background:var(--lime);padding:2px 6px;letter-spacing:.08em;margin-left:-6px}
.nav{margin-left:auto;display:flex;gap:12px;font:13px "Barlow Condensed",sans-serif;letter-spacing:.04em}.nav a{text-decoration:none;color:var(--muted)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px 28px}
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:18px 0 4px;text-transform:uppercase}h1 em{font-style:normal;color:var(--purple)}
.intro{color:var(--muted);margin:0}
.pick{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;align-items:center;position:relative}
.chip{display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-left:3px solid;padding:5px 8px 5px 6px;font-weight:600}
.chip img,.chip .ph{width:26px;height:26px;border-radius:50%;object-fit:cover;background:var(--card2);display:grid;place-items:center;font-size:10px;color:var(--muted)}
.chip button{background:none;border:0;color:var(--muted);font-size:16px;cursor:pointer;padding:0 2px}
.add{position:relative;flex:1;min-width:220px;max-width:360px}.add input{width:100%;background:var(--card);border:1px solid #3a2f6b;color:var(--ink);font:15px "Barlow",sans-serif;padding:8px 10px}
.res{position:absolute;left:0;right:0;top:100%;z-index:40;background:var(--bg2);border:1px solid var(--line);max-height:60vh;overflow:auto}.res:empty{display:none}
.res a{display:flex;align-items:center;gap:8px;padding:7px 10px;text-decoration:none;border-bottom:1px solid #1c1c29;cursor:pointer}.res a:hover{background:var(--card)}
.res img,.res .ph{width:28px;height:28px;border-radius:50%;object-fit:cover;background:var(--card2)}.res small{color:var(--muted)}
.seg{display:inline-flex;border:1px solid var(--line);background:var(--card);margin-top:12px}.seg button{background:none;border:0;color:var(--muted);font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.04em;padding:6px 10px;cursor:pointer}.seg button.on{background:var(--lime);color:#0b0b12}
.card{background:var(--card);border:1px solid var(--line);margin-top:14px;padding:14px 16px;overflow-x:auto}
.card h2{font-size:19px;margin:0 0 4px}.cap{color:var(--muted);font-size:12px}
table{width:100%;border-collapse:collapse;min-width:520px}th,td{padding:8px 10px;border-bottom:1px solid #1c1c29;text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;color:var(--muted);font-weight:400;position:sticky;left:0;background:var(--card)}
th{font:600 14px "Barlow",sans-serif}td{font:600 17px "Barlow Condensed",sans-serif}td.win{color:var(--lime)}
th .sw{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:middle}
canvas{display:block;width:100%;height:260px;margin-top:10px}
.leg{display:flex;flex-wrap:wrap;gap:12px;font-size:13px;margin-top:6px}.leg span{display:flex;align-items:center;gap:6px}.leg i{width:14px;height:3px;display:inline-block}
.empty{color:var(--muted);padding:18px 0}tr.ml{display:none}
.bar{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap}.shbtn{background:var(--lime);color:#0b0b12;border:0;font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.05em;padding:8px 12px;cursor:pointer;margin-top:12px}
.shbtn.ghost{background:none;color:var(--ink);border:1px solid var(--line)}td small.dl{display:block;font:600 12px "Barlow Condensed",sans-serif}.dl.up{color:#3ddc84}.dl.dn{color:#ff4d5e}
@media(max-width:640px){table{min-width:0;table-layout:fixed}.l{display:none}tr.ml{display:table-row}tr.ml td{position:static;text-align:left;font:12px "Barlow",sans-serif;color:var(--muted);padding:8px 4px 0;border:0}th,td{text-align:left!important;white-space:normal;padding:2px 4px 8px!important;word-break:break-word}th{font-size:13px;vertical-align:bottom}.card{padding:12px}}
@media(max-width:640px){.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.nav{display:none}h1{font-size:28px}canvas{height:210px}td{font-size:15px}th,td{padding:7px 8px}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<h1>Compare <em>channels</em></h1>
<p class="intro">Up to four channels from YouTube, Twitch or Kick, side by side. Best value in each row in green.</p>
<div class="pick" id="pick"></div>
<div class="bar"><div class="seg" id="rng"></div><button class="shbtn" id="share" style="display:none">SHARE CARD</button></div>
<div id="out"></div>
<div id="modal" style="position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.85);display:none;align-items:center;justify-content:center;padding:16px"><div style="background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto">
 <div class="seg" id="mfmt" style="margin:0 0 8px"><button data-f="post" class="on">POST 4:5</button><button data-f="story">STORY 9:16</button></div>
 <img id="mimg" alt="Share card" style="width:100%;max-height:70vh;object-fit:contain;display:block;border:1px solid var(--line);margin-bottom:10px">
 <div style="display:flex;gap:8px"><button class="shbtn" id="mshare">SHARE</button><button class="shbtn ghost" id="mdl">DOWNLOAD</button><button class="shbtn ghost" id="mclose" style="margin-left:auto">CLOSE</button></div></div></div>
</div>
<script>
const RP=__RPJ__,PAL=['#b6f23a','#a58bff','#4cc9f0','#ff9f5a'],NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{if(n==null)return '-';n=+n||0;return n>=1e9?(n/1e9).toFixed(2)+'B':n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const Q=new URLSearchParams(location.search);let C=(Q.get('c')||'').split(',').filter(Boolean).slice(0,4),RNG=Q.get('range')||'90d',J=null;
const KEEP={};   // answers already loaded, per channels + range: switching range is instant
const getC=async(rg,fresh)=>{const k=C.join(',')+'|'+rg;if(!fresh&&KEEP[k])return KEEP[k];const j=await (await fetch('/api/compare?c='+encodeURIComponent(C.join(','))+'&range='+rg)).json();
 if(!j.channels.some(c=>c.loading))KEEP[k]=j;return j};
let PRE='';async function prefetch(){const k=C.join(',');if(PRE===k)return;PRE=k;for(const [rg] of RANGES){if(PRE!==k)return;try{await getC(rg)}catch(e){}}}
const RANGES=[['1d','1D'],['3d','3D'],['7d','7D'],['30d','30D'],['90d','90D'],['6m','6M'],['1y','1Y'],['all','ALL']];
const RL={'1d':'24 hours','3d':'3 days','7d':'7 days','30d':'30 days','90d':'90 days','6m':'6 months','1y':'1 year','all':'all time'};
const PR={'1d':'the day before','3d':'the 3 days before','7d':'the 7 days before','30d':'the 30 days before','90d':'the 90 days before','6m':'the 6 months before','1y':'the year before'};
// rows of the table (and the share card: `card` is its label there, in that order)
const hrs=v=>v==null?'-':fmt(v)+'h';
// rows of the table, in this order; `card` = [place on the share card, its label there]. low: smaller is better (rank).
// Per live day: the range's totals divided by the days the channel went live (10+ minutes), so a daily streamer and
// one who streams twice a month compare fairly (owner, 24 Nov).
const ROWS=R=>[
 {lab:`Rank in its game, by hours watched, ${R}`,card:[1,'RANK'],f:c=>c.rank?c.rank.rank:null,fm:(v,c)=>v==null?'-':'#'+v+(c&&c.rank&&c.rank.where?' '+esc(c.rank.where):''),low:1},
 {lab:'Subscribers / followers',card:[11,'FOLLOWERS / SUBS'],f:c=>c.stats?c.stats.subs:null,fm:fmt},
 {lab:'Lifetime views',f:c=>c.stats?c.stats.views:null,fm:fmt},
 {lab:'Videos, lifetime',f:c=>c.stats?c.stats.videos:null,fm:fmt},
 {lab:`Growth, ${R} (views gained on YouTube, followers on Twitch / Kick)`,card:[5,'GROWTH'],u:1,f:c=>c.growth,fm:v=>v==null?'-':'+'+fmt(v),p:'growth',k:'pace',g:1},
 {lab:`Peak live viewers, ${R}`,card:[2,'PEAK VIEWERS'],f:c=>c.live.peak||null,fm:fmt,p:'peak',k:'peak'},
 {lab:`Average live viewers, ${R}`,card:[3,'AVG LIVE VIEWERS'],f:c=>c.live.avg||null,fm:fmt,p:'lavg',k:'rate'},
 {lab:`Days live, ${R}`,card:[6,'DAYS LIVE'],f:c=>c.live.days||null,fm:fmt,p:'days',k:'pace'},
 {lab:'Average peak per live day',card:[7,'PEAK PER LIVE DAY'],f:c=>c.live.dpeak||null,fm:fmt,p:'dpeak',k:'rate'},
 {lab:'Hours watched per live day',card:[8,'WATCH HRS PER LIVE DAY'],f:c=>c.live.dhw||null,fm:hrs,p:'dhw',k:'rate'},
 {lab:'Hours streamed per live day',f:c=>c.live.dhours||null,fm:v=>v==null?'-':v+'h',p:'dhours',k:'rate'},
 {lab:`Hours watched live, ${R}`,card:[10,'HOURS WATCHED'],f:c=>c.live.hw||null,fm:hrs,p:'hw',k:'pace'},
 {lab:`Hours streamed, ${R}`,card:[12,'HOURS STREAMED'],f:c=>c.live.hours||null,fm:v=>v==null?'-':v+'h',p:'hours',k:'pace'},
 {lab:`Posts, ${R}`,f:c=>c.posts.count,fm:fmt,p:'count',k:'count'},
 {lab:'Views on those posts',f:c=>c.posts.views,fm:fmt,p:'views',k:'postv'},
 {lab:'Average views per post',card:[4,'AVG VIEWS / VIDEO'],f:c=>c.posts.avg,fm:fmt,p:'avg',k:'postv'},
 {lab:'Average views per past stream',card:[9,'AVG VIEWS / STREAM'],f:c=>c.posts.savg,fm:fmt,p:'savg',k:'postv'},
 {lab:'Median views per post',f:c=>c.posts.median,fm:fmt},
 {lab:'Engagement',f:c=>c.posts.engagement,fm:v=>v==null?'-':v+'%'},
 {lab:'Posts per week',f:c=>c.posts.per_week,fm:v=>v==null?'-':v},
 {lab:'Biggest live peak ever (this site)',f:c=>c.live.peak_all||null,fm:fmt}];
// the best value of a row (green): the highest, or the lowest rank
const best=(r,vals)=>{const v=vals.filter(x=>x!=null).map(Number);return v.length?(r.low?Math.min(...v):Math.max(...v)):null};
// % change against the same length of time just before (the arrows). Kept honest: totals are scaled to the days they
// actually cover (today counts in part) before comparing, and not compared when that is under a day; 1D peaks aren't
// compared (2 calendar days against 1); views on recent posts are still growing, so per-post views are compared from
// 90D up; no arrow when the earlier range wasn't fully tracked.
const chg=(c,r,v)=>{if(!r.p||v==null||!J||!J.days)return null;const p=(c.prev||{})[r.p];if(p==null||!(+p>0))return null;
 if(r.k==='postv'&&J.days<90)return null;if(r.k==='peak'&&J.days<2)return null;
 let a=v;if(r.k==='pace'){const d=r.g?J.done_g:J.done;if(!(d>=1))return null;a=v*J.days/d}return Math.round((a-p)/p*100)};
const mixed=L=>!(L.every(c=>c.platform==='youtube')||L.every(c=>c.platform!=='youtube'));
const arrow=d=>d==null?'':d===0?'<small class="dl">= same</small>':`<small class="dl ${d>0?'up':'dn'}">${d>0?'▲':'▼'} ${Math.abs(d)}%</small>`;
function url(){return location.pathname+'?'+new URLSearchParams({c:C.join(','),range:RNG})}
async function load(){history.replaceState(null,'',url());
 document.getElementById('rng').innerHTML=RANGES.map(([v,l])=>`<button data-v="${v}" class="${v===RNG?'on':''}">${l}</button>`).join('');
 if(!C.length){J=null;pick();document.getElementById('out').innerHTML='<div class="empty">Add a channel to start. Tip: open any channel page and press COMPARE.</div>';return}
 const want=C.join(',')+'|'+RNG;if(!KEEP[want])document.getElementById('out').style.opacity=.5;
 try{const j=await getC(RNG,load.again);if(C.join(',')+'|'+RNG!==want)return;J=j}catch(e){return}finally{document.getElementById('out').style.opacity=''}
 pick();render();document.getElementById('share').style.display=J.channels.length?'':'none';
 load.again=J.channels.some(c=>c.loading);if(load.again)setTimeout(load,7000);else setTimeout(prefetch,800)}
function pick(){const L=J?J.channels:[];
 document.getElementById('pick').innerHTML=C.map((sid,i)=>{const c=L.find(x=>x.sid===sid)||{name:J&&(J.missing||[]).includes(sid)?'Not found: '+sid.split(':')[1]:'Loading...'};return `<span class="chip" style="border-left-color:${PAL[i]}">${c.logo?`<img src="${esc(c.logo)}" alt="" referrerpolicy="no-referrer">`:`<span class="ph">${ini(c.name)}</span>`}<a href="${RP}/ch/${encodeURIComponent(sid)}" style="text-decoration:none">${esc(c.name)}</a> <small style="color:var(--muted)">${NAMES[c.platform]||''}</small><button data-rm="${esc(sid)}" aria-label="Remove">&times;</button></span>`}).join('')+
  (C.length<4?`<div class="add"><input id="q" placeholder="Add a channel: search YouTube, Twitch, Kick" autocomplete="off"><div class="res" id="res"></div></div>`:'');
 const q=document.getElementById('q');if(!q)return;let t=null,cur='';
 q.oninput=()=>{clearTimeout(t);t=setTimeout(async()=>{const v=q.value.trim();cur=v;const res=document.getElementById('res');if(v.length<2){res.innerHTML='';return}
  const a=await (await fetch('/api/search?region=global&q='+encodeURIComponent(v))).json();if(cur!==v)return;
  const items=(a.channels||[]).map(x=>({...x}));res.innerHTML=items.map(row).join('');
  if(v.length>=3){const b=await (await fetch('/api/lookup?q='+encodeURIComponent(v))).json();if(cur!==v)return;const seen=new Set(items.map(x=>x.sid));
   for(const p of ['youtube','twitch','kick'])(b[p]||[]).forEach(x=>{if(!seen.has(x.sid)){seen.add(x.sid);res.insertAdjacentHTML('beforeend',row({...x,platform:p}))}})}},250)};
 document.getElementById('pick').onclick=e=>{const r=e.target.closest('[data-rm]');if(r){C=C.filter(x=>x!==r.dataset.rm);load();return}const a=e.target.closest('[data-add]');if(a){e.preventDefault();if(!C.includes(a.dataset.add))C.push(a.dataset.add);load()}}}
const row=x=>`<a data-add="${esc(x.sid)}">${x.logo?`<img src="${esc(x.logo)}" alt="" referrerpolicy="no-referrer">`:`<span class="ph"></span>`}<span>${esc(x.name)} <small>${NAMES[x.platform]||''}${x.subs_text?' · '+esc(x.subs_text):''}</small></span></a>`;
function render(){const L=J.channels;if(!L.length){document.getElementById('out').innerHTML='<div class="empty">None of these channels could be loaded.</div>';return}
 const R_=RL[RNG]||RNG;
 const rows=ROWS(R_);
 const head=`<tr><th class="l"></th>${L.map((c,i)=>`<th><span class="sw" style="background:${PAL[C.indexOf(c.sid)]}"></span>${esc(c.name)}<br><small style="color:var(--muted);font-weight:400">${NAMES[c.platform]||''}${c.country?' · '+esc(c.country):''}</small></th>`).join('')}</tr>`;
 const body=rows.map(r=>{const vals=L.map(r.f);if(vals.every(v=>v==null))return '';const mx=best(r,vals);
  const nw=r.u&&mixed(L);return `<tr class="ml"><td colspan="${L.length}">${r.lab}</td></tr><tr><td class="l">${r.lab}</td>${vals.map((v,i)=>`<td class="${!nw&&v!=null&&L.length>1&&+v===mx&&(r.low||mx>0)?'win':''}">${r.fm(v,L[i])}${arrow(chg(L[i],r,v))}</td>`).join('')}</tr>`}).join('');
 document.getElementById('out').innerHTML=`<div class="card"><table>${head}${body}</table>
  <div class="cap" style="margin-top:8px">${J.days?`Live numbers use the rankings' window: today plus the ${J.days} whole day${J.days>1?'s':''} before (IST). Arrows: change against ${PR[RNG]||'the range before'}, with totals scaled to the days they cover since today isn't over. Views on new posts are still growing, so per-post arrows start at 90D. No arrow where the earlier range wasn't fully recorded. `:''}Rank: place in this site's rankings for the range (hours watched, same platform and country, channels streaming that game). Per live day: totals divided by the days the channel went live (10+ minutes), so a daily streamer and one who streams twice a month compare fairly. Posts = videos, Shorts and past streams posted in the range (YouTube) or past broadcasts (Twitch, Kick); their views are totals so far. Live numbers are recorded by this site. Engagement = (likes + comments) / views.</div></div>
  <div class="card"><h2>Average views per post</h2><div class="cap">Each point is the average over the posts in that slice of the range.</div><canvas id="c1"></canvas><div class="leg" id="l1"></div></div>
  <div class="card"><h2>${L.every(c=>c.platform==='youtube')?'Channel views per day':'Growth per day'}</h2><div class="cap">YouTube: channel views gained per day. Twitch / Kick: followers gained per day. Recorded daily by this site, so it starts when a channel is first tracked.</div><canvas id="c2"></canvas><div class="leg" id="l2"></div></div>`;
 lines('c1','l1',L.map(c=>({c,pts:c.series.map(p=>[p[0],p[1]])})),J.since,Date.now()/1000);
 const days=[...new Set(L.flatMap(c=>(c.views||[]).map(g=>g.day)))].sort();
 lines('c2','l2',L.map(c=>({c,pts:gpts(c)})),days.length?new Date(days[0]+'T00:00:00+05:30').getTime()/1000:Date.now()/1000-30*86400,Date.now()/1000)}
const gpts=c=>(c.views||[]).map(g=>[new Date(g.day+'T12:00:00+05:30').getTime()/1000,c.platform==='youtube'?g.views:g.subs]).filter(p=>p[1]!=null);
function lines(id,lid,S,t0,t1){const cv=document.getElementById(id);const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);
 const pt=10,pb=22,pr=50,all=S.flatMap(s=>s.pts.map(p=>p[1])),mx=Math.max(1,...all)*1.15,X=t=>(W-pr)*(t-t0)/((t1-t0)||1),Y=v=>pt+(H-pt-pb)*(1-v/mx),span=t1-t0;
 x.font='11px "Barlow Condensed",sans-serif';x.strokeStyle='#262636';x.fillStyle='#8d8ca3';
 for(let i=0;i<=3&&all.length;i++){const y=pt+(H-pt-pb)*i/3;x.beginPath();x.moveTo(0,y);x.lineTo(W-pr,y);x.stroke();x.fillText(fmt(mx*(1-i/3)),W-pr+4,y+4)}
 const nt=W<520?3:5;for(let i=0;i<=nt;i++){const t=t0+span*i/nt;x.textAlign=i===0?'left':i===nt?'right':'center';x.fillText(new Date(t*1000).toLocaleDateString('en-IN',span>300*86400?{month:'short',year:'2-digit'}:{day:'numeric',month:'short'}),X(t),H-5)}x.textAlign='left';
 if(!all.length){x.fillText('Not enough data yet.',10,H/2)}
 S.forEach(s=>{const P=s.pts.map(p=>[X(p[0]),Y(p[1])]),col=PAL[C.indexOf(s.c.sid)];if(!P.length)return;x.strokeStyle=col;x.lineWidth=2.2;x.beginPath();x.moveTo(P[0][0],P[0][1]);
  for(let i=1;i<P.length;i++){const a=P[i-1],b=P[i],cx=(a[0]+b[0])/2;x.bezierCurveTo(cx,a[1],cx,b[1],b[0],b[1])}x.stroke();P.forEach(p=>{x.beginPath();x.arc(p[0],p[1],2.5,0,7);x.fillStyle=col;x.fill()})});
 document.getElementById(lid).innerHTML=S.map(s=>`<span><i style="background:${PAL[C.indexOf(s.c.sid)]}"></i>${esc(s.c.name)}</span>`).join('')}
// share card: the channels, the key numbers with arrows and bars, and a chart
let blob=null,FMT='post';
function loadImg(u){return new Promise(r=>{if(!u)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
const CZ=location.pathname.startsWith('/india')?{tz:'Asia/Kolkata',lb:'IST',loc:'en-IN'}:{tz:'America/Chicago',lb:'CT',loc:'en-US'};
async function makeCard(logos){const ST=FMT==='story',H=ST?1920:1350,L=J.channels,n=L.length;
 const c=document.createElement('canvas');c.width=2160;c.height=H*2;const x=c.getContext('2d');x.scale(2,2);
 x.fillStyle='#0b0b12';x.fillRect(0,0,1080,H);const g=x.createRadialGradient(860,ST?120:-60,10,860,ST?120:-60,760);g.addColorStop(0,'rgba(124,92,255,.24)');g.addColorStop(1,'rgba(124,92,255,0)');x.fillStyle=g;x.fillRect(0,0,1080,H);
 const fit=(t,w)=>{t=String(t??'');while(x.measureText(t).width>w&&t.length>2)t=t.slice(0,-1);return t};
 const shrink=(t,w,px,f)=>{t=String(t??'');let k=px;x.font=f.replace('#',k);while(x.measureText(t).width>w&&k>px*.6){k--;x.font=f.replace('#',k)}return fit(t,w)};
 const col=s=>PAL[Math.max(0,C.indexOf(s.sid))];
 const y0=ST?200:60;
 x.fillStyle='#b6f23a';x.font='700 30px "Barlow Condensed",sans-serif';x.fillText('LETSGROWESPORTS',72,y0+26);
 x.fillStyle='#fff';x.fillText(shrink((n===2?L[0].name+' VS '+L[1].name:n>2?'HEAD TO HEAD':L[0].name).toUpperCase(),936,64,'700 #px "Barlow Condensed",sans-serif'),72,y0+100);
 const WM=(location.hostname.endsWith('letsgrowesports.com')?location.host:'live.letsgrowesports.com').replace(/^www\./,'')+location.pathname;
 x.font='600 22px "Barlow Condensed",sans-serif';const wmW=x.measureText(WM).width+28;
 const sub=(RNG==='all'?'ALL TIME':'LAST '+(RL[RNG]||RNG))+(J.days?' · ARROWS VS '+(PR[RNG]||'').replace(/^the /,'THE '):'');
 x.fillStyle='#b6f23a';x.fillText(shrink(sub.toUpperCase(),936-wmW,30,'700 #px "Barlow Condensed",sans-serif'),72,y0+145);
 x.textAlign='right';x.fillStyle='#a9a8be';x.font='600 22px "Barlow Condensed",sans-serif';x.fillText(WM,1008,y0+145);x.textAlign='left';
 x.fillStyle='#262636';x.fillRect(72,y0+170,936,2);
 // channel heads, one column each
 const LW=n>3?210:240,GX=72+LW,CW=(936-LW)/n,ims=logos?await Promise.all(L.map(s=>loadImg(s.logo))):[],r0=n>2?38:44,hy=y0+196;
 L.forEach((s,i)=>{const cx=GX+CW*(i+.5),cy=hy+r0;x.save();x.beginPath();x.arc(cx,cy,r0,0,7);x.fillStyle='#1a1a26';x.fill();
  if(ims[i]){x.clip();x.drawImage(ims[i],cx-r0,cy-r0,2*r0,2*r0)}else{x.fillStyle='#8d8ca3';x.font=`700 ${Math.round(r0*.7)}px "Barlow",sans-serif`;x.textAlign='center';x.fillText(String(s.name||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase(),cx,cy+r0*.25)}x.restore();
  x.beginPath();x.arc(cx,cy,r0,0,7);x.lineWidth=4;x.strokeStyle=col(s);x.stroke();
  x.textAlign='center';x.fillStyle='#fff';x.fillText(shrink(s.name,CW-16,n>2?24:28,'700 #px "Barlow",sans-serif'),cx,cy+r0+34);
  x.fillStyle=col(s);x.font='700 19px "Barlow Condensed",sans-serif';x.fillText(fit([(NAMES[s.platform]||'').toUpperCase(),s.country].filter(Boolean).join(' · '),CW-16),cx,cy+r0+60);x.textAlign='left'});
 // the chart: growth per day when every channel counts the same thing, else average views per post
 const same=L.every(s=>s.platform==='youtube')||L.every(s=>s.platform!=='youtube');
 const ser=[[same?'GROWTH PER DAY'+(L[0].platform==='youtube'?' (VIEWS GAINED)':' (FOLLOWERS GAINED)'):'',s=>gpts(s)],['AVERAGE VIEWS PER POST',s=>s.series.map(p=>[p[0],p[1]])]].filter(z=>z[0]&&L.reduce((a,s)=>a+z[1](s).length,0)>=3)[0];
 const CHH=ST?240:180,foot=H-(ST?264:58),cTop=ser?foot-CHH-96:foot;
 // metric rows
 const RH=ST?88:70,ry=hy+2*r0+78+RH/2,max=Math.max(1,Math.floor((cTop-ry)/RH+.5)),RS=ROWS('').filter(r=>r.card&&L.some(s=>r.f(s)!=null)).sort((a,b)=>a.card[0]-b.card[0]).slice(0,Math.min(max,8));
 const MEDAL=['#ffd23f','#d9dde8','#ff9f5a'];
 RS.forEach((r,k)=>{const y=ry+k*RH,vals=L.map(r.f),mx=best(r,vals);
  x.fillStyle='#1d1d2b';x.fillRect(72,y-RH/2,936,1);const AY=ST?28:24;
  const nw=r.u&&mixed(L),lab=r.u&&!nw?(L[0].platform==='youtube'?'VIEWS GAINED':'FOLLOWERS GAINED'):r.card[1];
  x.fillStyle='#a9a8be';x.fillText(shrink(lab,LW-16,24,'700 #px "Barlow Condensed",sans-serif'),72,y+(nw?0:8));
  if(nw){x.fillStyle='#8d8ca3';x.fillText(shrink('VIEWS (YT) / FOLLOWERS',LW-16,18,'600 #px "Barlow Condensed",sans-serif'),72,y+24)}
  vals.forEach((v,i)=>{const cx=GX+CW*(i+.5),win=!nw&&n>1&&v!=null&&+v===mx&&(r.low||mx>0),d=chg(L[i],r,v);
   if(r.low){x.textAlign='center';x.fillStyle=v==null?'#55546a':MEDAL[v-1]||'#fff';x.font=`700 ${ST?46:40}px "Barlow Condensed",sans-serif`;
    x.fillText(v==null?'-':'#'+v,cx,y+2);if(v!=null&&L[i].rank.where){x.fillStyle='#a9a8be';x.font='700 19px "Barlow Condensed",sans-serif';x.fillText(fit(String(L[i].rank.where).toUpperCase(),CW-16),cx,y+AY)}
    x.textAlign='left';return}
   x.textAlign='center';x.fillStyle=v==null?'#55546a':win?'#b6f23a':'#fff';x.font=`700 ${ST?42:36}px "Barlow Condensed",sans-serif`;
   x.fillText(fit(r.fm(v),CW-12),cx,y+(d==null?12:2));
   if(d!=null){x.font=`700 ${ST?20:18}px "Barlow Condensed",sans-serif`;x.fillStyle=d>0?'#3ddc84':d<0?'#ff4d5e':'#8d8ca3';x.fillText(d===0?'= SAME':(d>0?'▲ ':'▼ ')+Math.abs(d)+'%',cx,y+AY)}
   if(!nw&&v!=null&&mx>0&&!r.low){const bw=(CW-40)*Math.max(0,+v)/mx;x.globalAlpha=.55;x.fillStyle=col(L[i]);x.fillRect(cx-(CW-40)/2,y+RH/2-8,bw,4);x.globalAlpha=1}
   x.textAlign='left'})});
 if(ser){const S=L.map(s=>({s,p:ser[1](s).filter(p=>p[0]>=J.since-86400)})),TS=S.flatMap(z=>z.p.map(p=>p[0])),t0=Math.min(...TS,Math.max(J.since,Math.min(...TS)-43200)),t1=Math.max(Date.now()/1000,...TS),cx0=72,cw=850,cy0=cTop+44,ch=CHH,all=S.flatMap(z=>z.p.map(p=>p[1])),mx=Math.max(1,...all)*1.12;
  x.fillStyle='#a9a8be';x.font='700 24px "Barlow Condensed",sans-serif';x.fillText(ser[0],72,cTop+24);
  const X=t=>cx0+cw*(t-t0)/((t1-t0)||1),Y=v=>cy0+ch*(1-v/mx);x.strokeStyle='#262636';x.lineWidth=1;x.font='18px "Barlow Condensed",sans-serif';x.fillStyle='#8d8ca3';
  for(let i=0;i<=3;i++){const y=cy0+ch*i/3;x.beginPath();x.moveTo(cx0,y);x.lineTo(cx0+cw,y);x.stroke();x.fillText(fmt(mx*(1-i/3)),cx0+cw+10,y+6)}
  const dd=t=>new Date(t*1000).toLocaleDateString(CZ.loc,{timeZone:CZ.tz,day:'numeric',month:'short',...(t1-t0>300*86400?{year:'2-digit'}:{})});
  x.fillText(dd(t0),cx0,cy0+ch+26);x.textAlign='right';x.fillText(dd(t1),cx0+cw,cy0+ch+26);x.textAlign='left';
  S.forEach(z=>{const P=z.p.map(p=>[X(p[0]),Y(Math.max(0,p[1]))]);if(!P.length)return;x.strokeStyle=col(z.s);x.lineWidth=4;x.beginPath();x.moveTo(P[0][0],P[0][1]);
   for(let i=1;i<P.length;i++){const a=P[i-1],b=P[i],m=(a[0]+b[0])/2;x.bezierCurveTo(m,a[1],m,b[1],b[0],b[1])}x.stroke();P.forEach(p=>{x.beginPath();x.arc(p[0],p[1],4,0,7);x.fillStyle=col(z.s);x.fill()})})}
 x.fillStyle='#8d8ca3';x.font='24px "Barlow Condensed",sans-serif';x.fillText('Recorded by '+WM.split('/')[0]+'  ·  '+new Date().toLocaleString(CZ.loc,{timeZone:CZ.tz,day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})+' '+CZ.lb,72,foot+34);
 return new Promise(r=>{try{c.toBlob(r,'image/png')}catch(e){r(null)}})}
async function showCard(){if(!J||!J.channels.length)return;try{await document.fonts.ready}catch(e){}blob=await makeCard(true)||await makeCard(false);
 if(blob){document.getElementById('mimg').src=URL.createObjectURL(blob);document.getElementById('modal').style.display='flex'}}
document.getElementById('share').onclick=showCard;
document.getElementById('mfmt').onclick=e=>{const b=e.target.closest('button');if(!b)return;FMT=b.dataset.f;document.querySelectorAll('#mfmt button').forEach(z=>z.classList.toggle('on',z===b));showCard()};
document.getElementById('mclose').onclick=()=>document.getElementById('modal').style.display='none';
document.getElementById('mdl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='compare.png';a.click()};
document.getElementById('mshare').onclick=async()=>{const f=new File([blob],'compare.png',{type:'image/png'}),t=J.channels.map(c=>c.name).join(' vs ')+', '+(RNG==='all'?'all time':'last '+(RL[RNG]||RNG))+': '+location.href+' @letsgrowesports';
 if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){}}document.getElementById('mdl').click()};
document.getElementById('rng').onclick=e=>{const b=e.target.closest('button');if(b){RNG=b.dataset.v;load()}};
window.addEventListener('resize',()=>{if(J)render()});
load();
</script></body></html>"""


def build_html(region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    return (PAGE.replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__RPJ__", json.dumps("/india" if region == "in" else "/global"))
            .replace("__HOME__", "/india" if region == "in" else "/global").replace("__RP__", "/india" if region == "in" else "/global"))
