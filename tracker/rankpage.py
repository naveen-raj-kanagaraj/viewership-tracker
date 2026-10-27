"""/rankings and /india/rankings: leaderboards of channels for any day, week or month (IST), by hours watched, peak
or average viewers or hours streamed, filtered by category, streamer country and platform, with rank moves against
the period before. Data: /api/rank (scene.rankings). Tap a channel for its full analytics (shared with the
dashboard, scenepage.PANEL_JS)."""
import html
import json

from tracker import eventpage, scenepage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__ | __BRAND__ (beta)</title>
<meta name="description" content="Top live streamers __WHERE__ on YouTube, Kick and Twitch for any day, week or month: hours watched, peak and average viewers, by category and country.">
<meta property="og:title" content="__TITLE__ | __BRAND__"><meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body{background:radial-gradient(900px 420px at 85% -15%,rgba(124,92,255,.13),transparent 60%),var(--bg);min-height:100vh}a{color:inherit}
.top{position:sticky;top:0;z-index:30;background:rgba(11,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1200px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;letter-spacing:.04em;white-space:nowrap}
.beta{font:700 10px "Barlow Condensed",sans-serif;color:#0b0b12;background:var(--lime);padding:2px 6px;letter-spacing:.08em;margin-left:-6px}
.rg{display:inline-flex;border:1px solid var(--line);font:12px "Barlow Condensed",sans-serif;letter-spacing:.04em}.rg a{padding:4px 10px;text-decoration:none;color:var(--muted)}.rg a.on{background:var(--lime);color:#0b0b12}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 28px}
.crumb{font:12px "Barlow Condensed",sans-serif;color:var(--muted);margin-top:18px;letter-spacing:.04em}.crumb a{text-decoration:none}
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:6px 0 4px;text-transform:uppercase}h1 em{font-style:normal;color:var(--purple)}
.intro{color:var(--muted);margin:0}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;align-items:center}
.seg{display:inline-flex;border:1px solid var(--line);background:var(--card)}.seg button{background:none;border:0;color:var(--muted);font:600 13px "Barlow Condensed",sans-serif;letter-spacing:.04em;padding:7px 11px;cursor:pointer}.seg button.on{background:var(--lime);color:#0b0b12}
select,.dt input{background:var(--card);border:1px solid var(--line);color:var(--ink);font:500 14px "Barlow",sans-serif;padding:6px 9px;max-width:220px}
.dt{display:inline-flex;align-items:center;border:1px solid var(--line);background:var(--card)}.dt input{border:0;color-scheme:dark}.dt button{background:none;border:0;color:var(--ink);font-size:16px;padding:4px 10px;cursor:pointer}.dt button:disabled{opacity:.3;cursor:default}
.span{color:var(--muted);font-size:13px;margin-top:10px}
.podium{display:grid;grid-template-columns:1fr 1.12fr 1fr;gap:10px;margin-top:14px;align-items:end}
.pd{background:var(--card);border:1px solid var(--line);padding:16px 12px 14px;text-align:center;text-decoration:none;position:relative;cursor:pointer;transition:transform .2s,border-color .2s}
.pd:hover{transform:translateY(-3px)}.pd.p1{border-color:#ffd23f;background:linear-gradient(180deg,rgba(255,210,63,.12),var(--card) 60%);padding-top:22px}.pd.p2{border-color:#9aa0b4}.pd.p3{border-color:#c46a2c}
.pd .md{font:700 28px "Barlow Condensed",sans-serif}.pd.p1 .md{color:#ffd23f;font-size:34px}.pd.p2 .md{color:#d9dde8}.pd.p3 .md{color:#ff9f5a}
.pd img,.pd .ph{width:64px;height:64px;border-radius:50%;object-fit:cover;display:grid;place-items:center;margin:6px auto;background:var(--card2);border:2px solid var(--line);font:700 18px "Barlow",sans-serif;color:var(--muted)}.pd.p1 img,.pd.p1 .ph{width:80px;height:80px;border-color:#ffd23f}
.pd .n{font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pd .v{font:700 30px "Barlow Condensed",sans-serif;margin-top:2px}.pd .s{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.list{background:var(--card);border:1px solid var(--line);margin-top:12px}
.lth{display:grid;grid-template-columns:44px 38px minmax(0,1fr) 90px 90px 90px;gap:10px;padding:8px 14px;border-bottom:1px solid var(--line);font:500 12px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.05em;background:var(--card2)}
.lth span:nth-child(n+3){text-align:right}
.row{display:grid;grid-template-columns:44px 38px minmax(0,1fr) 90px 90px 90px;gap:10px;align-items:center;padding:8px 14px;border-bottom:1px solid #1c1c29}
.row:hover{background:#171722}.rk{font:700 16px "Barlow Condensed",sans-serif;color:var(--muted);display:flex;flex-direction:column;line-height:1.1}
.row .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.row .ds{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .c{text-align:right;font:600 16px "Barlow Condensed",sans-serif}.row .c.m{color:var(--lime)}.row .c small{display:block;font:400 11px "Barlow",sans-serif;color:var(--muted)}
.lth .lc{grid-column:2 / span 2}
.dl{font:600 11px "Barlow Condensed",sans-serif}.dl.up{color:#3ddc84}.dl.dn{color:var(--red)}.dl.nw{color:var(--purple)}
.lv{color:var(--red);font:600 10px "Barlow Condensed",sans-serif;margin-right:4px}.lv:before{content:"\25CF ";}
.av{position:relative;width:38px;height:38px}.av img,.av .ph{width:38px;height:38px;border-radius:50%;object-fit:cover;background:var(--card2);border:1px solid var(--line);display:grid;place-items:center;font:700 12px "Barlow",sans-serif;color:var(--muted)}
.av .bd{position:absolute;right:-3px;bottom:-3px;width:15px;height:15px;border-radius:4px;display:grid;place-items:center;font:700 9px "Barlow",sans-serif;color:#0b0b12;border:2px solid var(--card)}
.btn{background:var(--lime);color:#0b0b12;border:0;font:700 12px "Barlow Condensed",sans-serif;letter-spacing:.04em;padding:6px 11px;cursor:pointer;text-decoration:none}
.more{display:block;width:100%;background:var(--card2);border:0;color:var(--ink);font:14px "Barlow",sans-serif;padding:11px;cursor:pointer}.more:hover{color:var(--lime)}
.empty{padding:18px 14px;color:var(--muted)}.lbl{color:var(--red);font:12px "Barlow Condensed",sans-serif;letter-spacing:.06em;text-transform:uppercase}.muted{color:var(--muted)}
.cx [data-ch]{display:none}
.note{color:var(--muted);font-size:12px;margin-top:14px;line-height:1.6}
__PANEL_CSS__
@media(max-width:700px){.wrap{padding:0 12px 20px}.top .in{padding:9px 12px;gap:10px}.brand{font-size:15px}h1{font-size:28px}
.filters{gap:6px}.seg button{padding:6px 8px;font-size:12px}select{max-width:48%}
.podium{gap:6px}.pd{padding:12px 6px}.pd img,.pd .ph{width:48px;height:48px}.pd.p1 img,.pd.p1 .ph{width:58px;height:58px}.pd .v{font-size:22px}.pd .md{font-size:22px}.pd.p1 .md{font-size:26px}.pd .s{display:none}
.lth{grid-template-columns:34px 34px minmax(0,1fr) 72px;gap:8px;padding:7px 10px}.lth span:nth-child(n+4){display:none}
.row{grid-template-columns:34px 34px minmax(0,1fr) 72px;gap:8px;padding:8px 10px}.row .c.x2,.row .c.x3{display:none}.av,.av img,.av .ph{width:34px;height:34px}
.cx{padding:10px 12px 12px}.cxc{grid-template-columns:1fr}.cxt td{font-size:14px;padding:4px 3px}.cxt th{padding:4px 3px;font-size:10px}.cxd div{grid-template-columns:52px minmax(0,1fr) 64px 50px}.cxd div span:nth-child(5){display:none}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="rg"><a href="/rankings" class="__GON__">GLOBAL</a><a href="/india/rankings" class="__ION__">INDIA</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / RANKINGS</div>
<h1>Top streamers <em>__WHERE__</em></h1>
<p class="intro" id="intro">Ranked by what people actually watched live. Tap a streamer for their full numbers.</p>
<div class="filters">
 <div class="seg" id="period"></div>
 <div class="dt"><button id="prev" aria-label="Earlier">&#8249;</button><input type="date" id="date"><button id="next" aria-label="Later">&#8250;</button></div>
 <div class="seg" id="metric"></div>
 <select id="cat"><option value="">All categories</option></select>
 <select id="country"><option value="">All countries</option></select>
 <div class="seg" id="plat"></div>
 <button class="btn" id="share">SHARE TOP 10</button>
</div>
<div class="span" id="span"></div>
<div class="podium" id="podium"></div>
<div class="list"><div class="lth"><span>#</span><span class="lc">STREAMER</span><span id="h1c">HOURS WATCHED</span><span id="h2c">PEAK</span><span id="h3c">AVG</span></div><div id="rows"></div><button class="more" id="more"></button></div>
<div class="note">Hours watched = viewers x time live. Peak = most people watching at once. Average = hours watched / hours live. Days run midnight to midnight IST. Rank arrows compare with the period before (yesterday, last week, last month). Total views aren't published by Kick and Twitch for live streams, so they're not ranked here.</div>
</div>
<div class="modal" id="modal" style="position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.82);display:none;align-items:center;justify-content:center;padding:16px"><div style="background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto">
 <img id="mimg" alt="Share card" style="width:100%;display:block;border:1px solid var(--line);margin-bottom:10px"><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" id="mshare">SHARE</button><button class="btn" id="mdl">DOWNLOAD</button><button class="btn" id="mclose" style="background:none;color:var(--muted);border:1px solid var(--line)">CLOSE</button></div></div></div>
<script>
const REGION=__REGION__,GL=REGION==='global',RP=GL?'':'/india',SITE=__SITEURL__,WHERE=GL?'worldwide':'in India';
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'},MEDAL=['#ffd23f','#d9dde8','#ff9f5a'];
const MET={hw:['HOURS WATCHED',v=>fmt(v)+'h'],peak:['PEAK VIEWERS',v=>fmt(v)],avg:['AVG VIEWERS',v=>fmt(v)],hours:['HOURS LIVE',v=>v+'h']};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ist=(ts,o)=>new Date(ts*1000).toLocaleString('en-IN',Object.assign({timeZone:'Asia/Kolkata'},o));
const ago=ts=>{const s=Date.now()/1000-ts;return s<120?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const av=x=>`<span class="av">${x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph>${ini(x.name)}</span>'">`:`<span class="ph">${ini(x.name)}</span>`}<span class="bd" style="background:${COL[x.platform]||'#888'}">${(x.platform||'?')[0].toUpperCase()}</span></span>`;
const dl=d=>d===null?'<span class="dl nw">NEW</span>':d>0?`<span class="dl up">&#9650;${d}</span>`:d<0?`<span class="dl dn">&#9660;${-d}</span>`:'<span class="dl" style="color:var(--muted)">=</span>';
const liveMap=()=>{const m={};(R?R.rows:[]).forEach(x=>{if(x.now)m[x.sid]=x.now});return m};
const Q=new URLSearchParams(location.search);
let S={period:['day','week','month'].includes(Q.get('period'))?Q.get('period'):'day',metric:Q.get('metric')||'hw',date:Q.get('date')||'',cat:Q.get('cat')||'',country:Q.get('country')||'',platform:Q.get('platform')||'',sec:Q.get('sec')||''};
let R=null,OPEN=null,ALL=false;
function seg(id,opts,cur,on){const e=document.getElementById(id);e.innerHTML=opts.map(([v,l])=>`<button data-v="${v}" class="${v===cur?'on':''}">${l}</button>`).join('');e.onclick=ev=>{const b=ev.target.closest('button');if(b)on(b.dataset.v)}}
const shift=(d,n)=>{const t=new Date(d+'T12:00:00Z');t.setUTCDate(t.getUTCDate()+n);return t.toISOString().slice(0,10)};
const dshortD=d=>new Date(d+'T12:00:00+05:30').toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'});
__PANEL_JS__
function rowsHTML(){const L=(R.rows||[]).slice(3,ALL?100:25),M=MET[S.metric];
 return L.map(x=>rowX('r',x,`<span class="rk">${x.rank}${dl(x.delta)}</span>${av(x)}<span style="min-width:0"><div class="nm">${esc(x.name)}<span class="car">&#9654;</span></div><div class="ds">${x.now?`<span class="lv">LIVE</span>${full(x.now)} · `:''}${esc(x.game)}${x.country_name?' · '+esc(x.country_name):''}</div></span>`+
  cols(x).map((c,i)=>`<span class="c${i===0?' m':''} x${i+1}">${c}</span>`).join(''))).join('')}
function cols(x){const order=[S.metric,...['hw','peak','avg','hours'].filter(m=>m!==S.metric)].slice(0,3);return order.map(m=>MET[m][1](x[m]))}
function render(){if(!R)return;const order=[S.metric,...['hw','peak','avg','hours'].filter(m=>m!==S.metric)].slice(0,3);
 ['h1c','h2c','h3c'].forEach((id,i)=>document.getElementById(id).textContent=MET[order[i]][0]);
 const lab={day:'',week:'7 days to ',month:'30 days to '}[S.period];
 document.getElementById('span').textContent=`${R.total} streamers · ${lab}${dshortD(R.date)}${R.date===R.today&&S.period==='day'?' (today, so far)':''} · ranked by ${MET[S.metric][0].toLowerCase()}`;
 const P=(R.rows||[]).slice(0,3),ord=P.length===3?[P[1],P[0],P[2]]:P;
 document.getElementById('podium').innerHTML=ord.map(x=>`<div class="pd p${x.rank}" data-sid="${esc(x.sid)}"><div class="md">#${x.rank} ${dl(x.delta)}</div>${x.logo?`<img src="${esc(x.logo)}" alt="" referrerpolicy="no-referrer">`:`<span class="ph">${ini(x.name)}</span>`}<div class="n">${esc(x.name)}</div><div class="v">${MET[S.metric][1](x[S.metric])}</div><div class="s">${esc(x.game)} · peak ${fmt(x.peak)}</div></div>`).join('');
 document.querySelectorAll('.pd').forEach(e=>e.onclick=()=>{const k='r:'+e.dataset.sid;if(OPEN!==k)toggleRow(k);setTimeout(()=>{const r=document.querySelector(`[data-k="${CSS.escape(k)}"]`);if(r)r.scrollIntoView({behavior:'smooth',block:'center'})},50)});
 // the top 3 also get a row (hidden behind the podium) so their analytics can open in the list
 const top3=(R.rows||[]).slice(0,3).filter(x=>OPEN==='r:'+x.sid).map(x=>rowX('r',x,`<span class="rk" style="color:${MEDAL[x.rank-1]}">${x.rank}${dl(x.delta)}</span>${av(x)}<span style="min-width:0"><div class="nm">${esc(x.name)}</div><div class="ds">${esc(x.game)}</div></span>`+cols(x).map((c,i)=>`<span class="c${i===0?' m':''} x${i+1}">${c}</span>`).join(''))).join('');
 document.getElementById('rows').innerHTML=(top3+rowsHTML())||(R.rows.length>3?'':`<div class="empty">${R.rows.length?'':'Nobody recorded for this '+(S.period==='day'?'day':'period')+' with these filters.'}</div>`);
 const m=document.getElementById('more');m.style.display=(R.rows||[]).length>25?'block':'none';m.textContent=ALL?'Show top 25':`Show top ${Math.min(100,R.rows.length)}`;m.onclick=()=>{ALL=!ALL;render()}}
function controls(){seg('period',[['day','DAY'],['week','WEEK'],['month','MONTH']],S.period,v=>{S.period=v;go()});
 seg('metric',[['hw','HOURS WATCHED'],['peak','PEAK'],['avg','AVERAGE'],['hours','HOURS LIVE']],S.metric,v=>{S.metric=v;go()});
 seg('plat',[['','ALL'],['youtube','YT'],['kick','KICK'],['twitch','TWITCH']],S.platform,v=>{S.platform=v;go()});
 const di=document.getElementById('date');if(R){di.max=R.today;di.min=R.first_day||'';di.value=R.date;
  document.getElementById('prev').disabled=!!R.first_day&&R.start<=R.first_day;document.getElementById('next').disabled=R.date>=R.today}
 const cs=document.getElementById('cat');cs.innerHTML='<option value="">All categories</option>'+((R&&R.categories)||[]).map(g=>`<option value="${esc(g.slug)}"${g.slug===S.cat?' selected':''}>${esc(g.game)}</option>`).join('')+(S.cat&&R&&!R.categories.some(g=>g.slug===S.cat)?`<option value="${esc(S.cat)}" selected>${esc(S.cat)}</option>`:'');
 const co=document.getElementById('country');co.style.display=GL?'':'none';co.innerHTML='<option value="">All countries</option>'+((R&&R.countries)||[]).map(c=>`<option value="${c.code}"${c.code===S.country?' selected':''}>${esc(c.name)}</option>`).join('')}
document.getElementById('date').onchange=e=>{S.date=e.target.value;go()};
document.getElementById('prev').onclick=()=>{S.date=shift(R.date,-({day:1,week:7,month:30}[S.period]));go()};
document.getElementById('next').onclick=()=>{S.date=shift(R.date,{day:1,week:7,month:30}[S.period]);if(S.date>R.today)S.date='';go()};
document.getElementById('cat').onchange=e=>{S.cat=e.target.value;go()};document.getElementById('country').onchange=e=>{S.country=e.target.value;go()};
document.getElementById('rows').addEventListener('click',e=>{if(e.target.closest('.cx'))return;const r=e.target.closest('.row.x');if(r)toggleRow(r.dataset.k)});
async function go(){const p=new URLSearchParams({region:REGION,period:S.period,metric:S.metric});['date','cat','country','platform','sec'].forEach(k=>{if(S[k])p.set(k,S[k])});
 const u=new URLSearchParams(p);u.delete('region');history.replaceState(null,'',location.pathname+(u.toString()?'?'+u:''));
 try{R=await (await fetch('/api/rank?'+p)).json()}catch(e){return}OPEN=null;ALL=false;controls();render()}
controls();go();setInterval(()=>{if(!document.hidden&&R&&R.date===R.today)go()},60000);
// share: top 10 as an image
let blob=null;
function loadImg(u){return new Promise(r=>{if(!u)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
async function makeCard(logos){const c=document.createElement('canvas');c.width=2160;c.height=2700;const x=c.getContext('2d');x.scale(2,2);
 x.fillStyle='#0b0b12';x.fillRect(0,0,1080,1350);const g=x.createRadialGradient(860,-60,10,860,-60,700);g.addColorStop(0,'rgba(124,92,255,.22)');g.addColorStop(1,'rgba(124,92,255,0)');x.fillStyle=g;x.fillRect(0,0,1080,1350);
 x.fillStyle='#b6f23a';x.font='700 30px "Barlow Condensed",sans-serif';x.fillText('LETSGROWESPORTS',72,96);
 const cat=S.cat?(R.categories.find(g=>g.slug===S.cat)||{}).game||S.cat:'';
 x.fillStyle='#fff';x.font='700 64px "Barlow Condensed",sans-serif';x.fillText(('TOP STREAMERS '+(cat?'· '+cat.toUpperCase():GL?'WORLDWIDE':'INDIA')).slice(0,30),72,170);
 x.fillStyle='#8d8ca3';x.font='28px "Barlow Condensed",sans-serif';x.fillText(document.getElementById('span').textContent.toUpperCase().slice(0,62),72,215);x.fillStyle='#262636';x.fillRect(72,245,936,2);
 const L=R.rows.slice(0,10),ims=logos?await Promise.all(L.map(s=>loadImg(s.logo))):[];
 L.forEach((s,i)=>{const y=285+i*96;x.fillStyle=i<3?MEDAL[i]:'#8d8ca3';x.font='700 40px "Barlow Condensed",sans-serif';x.fillText(String(i+1).padStart(2,'0'),72,y+46);
  if(ims[i]){x.save();x.beginPath();x.arc(180,y+34,30,0,7);x.clip();x.drawImage(ims[i],150,y+4,60,60);x.restore()}
  x.fillStyle='#fff';x.font='700 36px "Barlow",sans-serif';let n=s.name;while(x.measureText(n).width>470&&n.length>3)n=n.slice(0,-2);x.fillText(n,232,y+30);
  x.font='600 22px "Barlow Condensed",sans-serif';x.fillStyle=s.delta>0?'#3ddc84':s.delta<0?'#ff4d5e':'#a58bff';x.fillText((s.delta===null?'NEW':s.delta>0?'▲'+s.delta:s.delta<0?'▼'+(-s.delta):'=')+'  ',232,y+64);
  x.fillStyle='#8d8ca3';x.fillText(`${(NAMES[s.platform]||'').toUpperCase()} · PEAK ${fmt(s.peak)} · AVG ${fmt(s.avg)}`,300,y+64);
  x.textAlign='right';x.fillStyle='#fff';x.font='700 44px "Barlow Condensed",sans-serif';x.fillText(MET[S.metric][1](s[S.metric]),1008,y+46);x.textAlign='left';x.fillStyle='#1d1d2b';x.fillRect(72,y+84,936,1)});
 x.fillStyle='#8d8ca3';x.font='26px "Barlow Condensed",sans-serif';x.fillText((SITE+location.pathname).replace('https://',''),72,1300);
 return new Promise(r=>{try{c.toBlob(r,'image/png')}catch(e){r(null)}})}
document.getElementById('share').onclick=async()=>{if(!R||!R.rows.length)return;try{await document.fonts.ready}catch(e){}blob=await makeCard(true)||await makeCard(false);
 document.getElementById('mimg').src=URL.createObjectURL(blob);document.getElementById('modal').style.display='flex'};
document.getElementById('mclose').onclick=()=>document.getElementById('modal').style.display='none';
document.getElementById('mdl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='rankings.png';a.click()};
document.getElementById('mshare').onclick=async()=>{const f=new File([blob],'rankings.png',{type:'image/png'}),t=`Top streamers ${WHERE}: `+R.rows.slice(0,3).map((s,i)=>`${i+1}. ${s.name}`).join(' | ')+' '+SITE+location.pathname+location.search+' @letsgrowesports';
 if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){}}document.getElementById('mdl').click()};
</script></body></html>"""


def build_html(region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    where = "worldwide" if region == "global" else "in India"
    return (PAGE.replace("__PANEL_JS__", scenepage.PANEL_JS).replace("__PANEL_CSS__", scenepage.PANEL_CSS)
            .replace("__TITLE__", f"Top streamers {where}: daily, weekly, monthly rankings")
            .replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__REGION__", json.dumps(region))
            .replace("__SITEURL__", json.dumps(eventpage.SITE_URL)).replace("__WHERECAP__", "WORLDWIDE" if region == "global" else "INDIA")
            .replace("__WHERE__", where).replace("__HOME__", "/" if region == "global" else "/india")
            .replace("__GON__", "on" if region == "global" else "").replace("__ION__", "on" if region == "in" else ""))
