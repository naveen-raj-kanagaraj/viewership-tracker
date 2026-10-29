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
@media(max-width:640px){table{min-width:0;table-layout:fixed}.l{display:none}tr.ml{display:table-row}tr.ml td{position:static;text-align:left;font:12px "Barlow",sans-serif;color:var(--muted);padding:8px 4px 0;border:0}th,td{text-align:left!important;white-space:normal;padding:2px 4px 8px!important;word-break:break-word}th{font-size:13px;vertical-align:bottom}.card{padding:12px}}
@media(max-width:640px){.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.nav{display:none}h1{font-size:28px}canvas{height:210px}td{font-size:15px}th,td{padding:7px 8px}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="__RP__/moments">MOMENTS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<h1>Compare <em>channels</em></h1>
<p class="intro">Up to four channels from YouTube, Twitch or Kick, side by side. Best value in each row in green.</p>
<div class="pick" id="pick"></div>
<div class="seg" id="rng"></div>
<div id="out"></div>
</div>
<script>
const RP=__RPJ__,PAL=['#b6f23a','#a58bff','#4cc9f0','#ff9f5a'],NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{if(n==null)return '-';n=+n||0;return n>=1e9?(n/1e9).toFixed(2)+'B':n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const Q=new URLSearchParams(location.search);let C=(Q.get('c')||'').split(',').filter(Boolean).slice(0,4),RNG=Q.get('range')||'90d',J=null;
const RANGES=[['30d','30D'],['90d','90D'],['6m','6M'],['1y','1Y'],['all','ALL']];
function url(){return location.pathname+'?'+new URLSearchParams({c:C.join(','),range:RNG})}
async function load(){history.replaceState(null,'',url());
 document.getElementById('rng').innerHTML=RANGES.map(([v,l])=>`<button data-v="${v}" class="${v===RNG?'on':''}">${l}</button>`).join('');
 if(!C.length){J=null;pick();document.getElementById('out').innerHTML='<div class="empty">Add a channel to start. Tip: open any channel page and press COMPARE.</div>';return}
 try{J=await (await fetch('/api/compare?c='+encodeURIComponent(C.join(','))+'&range='+RNG)).json()}catch(e){return}
 pick();render();if(J.channels.some(c=>c.loading))setTimeout(load,7000)}
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
 const gain30=c=>{const G=c.views||[];if(!G.length)return null;return c.platform==='youtube'?G.reduce((a,g)=>a+(g.views||0),0):G.reduce((a,g)=>a+(g.subs||0),0)};
 const rows=[['Subscribers / followers',c=>c.stats?c.stats.subs:((c.views||[]).length?null:null),fmt],
  ['Lifetime views',c=>c.stats?c.stats.views:null,fmt],['Videos, lifetime',c=>c.stats?c.stats.videos:null,fmt],
  ['Channel growth, last 30 days',gain30,v=>v==null?'-':'+'+fmt(v)],
  ['Posts in range',c=>c.posts.count,fmt],['Views on those posts',c=>c.posts.views,fmt],['Average per post',c=>c.posts.avg,fmt],['Median per post',c=>c.posts.median,fmt],
  ['Engagement',c=>c.posts.engagement,v=>v==null?'-':v+'%'],['Posts per week',c=>c.posts.per_week,v=>v==null?'-':v],
  ['Peak live viewers, 30 days',c=>c.live.peak||null,fmt],['Average live viewers, 30 days',c=>c.live.avg||null,fmt],['Hours watched live, 30 days',c=>c.live.hw||null,v=>v==null?'-':fmt(v)+'h'],
  ['Biggest live peak ever (this site)',c=>c.live.peak_all||null,fmt]];
 const head=`<tr><th class="l"></th>${L.map((c,i)=>`<th><span class="sw" style="background:${PAL[C.indexOf(c.sid)]}"></span>${esc(c.name)}<br><small style="color:var(--muted);font-weight:400">${NAMES[c.platform]||''}${c.country?' · '+esc(c.country):''}</small></th>`).join('')}</tr>`;
 const body=rows.map(([lab,f,fm])=>{const vals=L.map(f),mx=Math.max(...vals.filter(v=>v!=null).map(Number));return `<tr class="ml"><td colspan="${L.length}">${lab}</td></tr><tr><td class="l">${lab}</td>${vals.map(v=>`<td class="${v!=null&&L.length>1&&+v===mx&&mx>0?'win':''}">${fm(v)}</td>`).join('')}</tr>`}).join('');
 const rk=L.map(c=>{const r=(c.ranks||[]).filter(r=>r.metric==='size').sort((a,b)=>a.rank/a.of-b.rank/b.of)[0];return r?`#${r.rank} ${esc(r.where)} <small style="color:var(--muted)">of ${r.of}</small>`:'-'});
 document.getElementById('out').innerHTML=`<div class="card"><table>${head}${body}<tr class="ml"><td colspan="${L.length}">Best rank (size)</td></tr><tr><td class="l">Best rank (size)</td>${rk.map(x=>`<td style="font-size:14px">${x}</td>`).join('')}</tr></table>
  <div class="cap" style="margin-top:8px">Posts = videos, Shorts and past streams posted in the range (YouTube) or past broadcasts (Twitch, Kick); their views are totals so far. Live numbers are recorded by this site. Engagement = (likes + comments) / views.</div></div>
  <div class="card"><h2>Average views per post</h2><div class="cap">Each point is the average over the posts in that slice of the range.</div><canvas id="c1"></canvas><div class="leg" id="l1"></div></div>
  <div class="card"><h2>${L.every(c=>c.platform==='youtube')?'Channel views per day':'Growth per day'}</h2><div class="cap">YouTube: channel views gained per day. Twitch / Kick: followers gained per day. Recorded daily by this site, so it starts when a channel is first tracked.</div><canvas id="c2"></canvas><div class="leg" id="l2"></div></div>`;
 lines('c1','l1',L.map(c=>({c,pts:c.series.map(p=>[p[0],p[1]])})),J.since,Date.now()/1000);
 const days=[...new Set(L.flatMap(c=>(c.views||[]).map(g=>g.day)))].sort();
 lines('c2','l2',L.map(c=>({c,pts:(c.views||[]).map(g=>[new Date(g.day+'T12:00:00+05:30').getTime()/1000,c.platform==='youtube'?g.views:(g.subs||0)])})),days.length?new Date(days[0]+'T00:00:00+05:30').getTime()/1000:Date.now()/1000-30*86400,Date.now()/1000)}
function lines(id,lid,S,t0,t1){const cv=document.getElementById(id);const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);
 const pt=10,pb=22,pr=50,all=S.flatMap(s=>s.pts.map(p=>p[1])),mx=Math.max(1,...all)*1.15,X=t=>(W-pr)*(t-t0)/((t1-t0)||1),Y=v=>pt+(H-pt-pb)*(1-v/mx),span=t1-t0;
 x.font='11px "Barlow Condensed",sans-serif';x.strokeStyle='#262636';x.fillStyle='#8d8ca3';
 for(let i=0;i<=3&&all.length;i++){const y=pt+(H-pt-pb)*i/3;x.beginPath();x.moveTo(0,y);x.lineTo(W-pr,y);x.stroke();x.fillText(fmt(mx*(1-i/3)),W-pr+4,y+4)}
 const nt=W<520?3:5;for(let i=0;i<=nt;i++){const t=t0+span*i/nt;x.textAlign=i===0?'left':i===nt?'right':'center';x.fillText(new Date(t*1000).toLocaleDateString('en-IN',span>300*86400?{month:'short',year:'2-digit'}:{day:'numeric',month:'short'}),X(t),H-5)}x.textAlign='left';
 if(!all.length){x.fillText('Not enough data yet.',10,H/2)}
 S.forEach(s=>{const P=s.pts.map(p=>[X(p[0]),Y(p[1])]),col=PAL[C.indexOf(s.c.sid)];if(!P.length)return;x.strokeStyle=col;x.lineWidth=2.2;x.beginPath();x.moveTo(P[0][0],P[0][1]);
  for(let i=1;i<P.length;i++){const a=P[i-1],b=P[i],cx=(a[0]+b[0])/2;x.bezierCurveTo(cx,a[1],cx,b[1],b[0],b[1])}x.stroke();P.forEach(p=>{x.beginPath();x.arc(p[0],p[1],2.5,0,7);x.fillStyle=col;x.fill()})});
 document.getElementById(lid).innerHTML=S.map(s=>`<span><i style="background:${PAL[C.indexOf(s.c.sid)]}"></i>${esc(s.c.name)}</span>`).join('')}
document.getElementById('rng').onclick=e=>{const b=e.target.closest('button');if(b){RNG=b.dataset.v;load()}};
window.addEventListener('resize',()=>{if(J)render()});
load();
</script></body></html>"""


def build_html(region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    return (PAGE.replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__RPJ__", json.dumps("/india" if region == "in" else ""))
            .replace("__HOME__", "/india" if region == "in" else "/").replace("__RP__", "/india" if region == "in" else ""))
