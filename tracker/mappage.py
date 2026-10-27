"""/map: a 3D globe of who is watching what, by the streamer's country (data from /api/geo, see scene.geo()).

Drag to spin, pinch or scroll to zoom, tap a country for its top games and channels. Drawn on a canvas with d3's
orthographic projection; the country shapes are Natural Earth 1:110m from the world-atlas package.
"""
import html

from tracker import eventpage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>World map of live streaming | __BRAND__ (beta)</title>
<meta name="description" content="A live 3D globe of what the world is watching on YouTube, Kick and Twitch: viewers by country, top games and top streamers, updated every few seconds.">
<meta property="og:title" content="World map of live streaming | __BRAND__"><meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;
--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e;--kick:#53fc18;--twitch:#a970ff}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body{background:radial-gradient(900px 420px at 85% -15%,rgba(124,92,255,.13),transparent 60%),var(--bg);min-height:100vh}
a{color:inherit}.C{font-family:"Barlow Condensed",sans-serif;letter-spacing:.04em}
.top{position:sticky;top:0;z-index:30;background:rgba(11,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1200px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;white-space:nowrap;letter-spacing:.04em}
.beta{font:700 10px "Barlow Condensed",sans-serif;color:#0b0b12;background:var(--lime);padding:2px 6px;letter-spacing:.08em;margin-left:-6px}
.rg{display:inline-flex;border:1px solid var(--line);font:12px "Barlow Condensed",sans-serif;letter-spacing:.04em}.rg a{padding:4px 10px;text-decoration:none;color:var(--muted)}.rg a.on{background:var(--lime);color:#0b0b12}
.upd{margin-left:auto;font:12px "Barlow Condensed",sans-serif;color:var(--muted);white-space:nowrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--red);margin-right:6px;box-shadow:0 0 8px var(--red);animation:pl 2s infinite}@keyframes pl{50%{opacity:.35}}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px 24px}
.crumb{font:12px "Barlow Condensed",sans-serif;color:var(--muted);margin-top:18px;letter-spacing:.04em}.crumb a{text-decoration:none}
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:6px 0 4px;text-transform:uppercase}h1 em{font-style:normal;color:var(--purple)}
.intro{color:#c9c8d8;margin:0;max-width:780px}
.stage{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:12px;margin-top:14px}
.globe{position:relative;align-self:start;background:radial-gradient(circle at 50% 45%,#141032 0,#0b0b12 70%);border:1px solid var(--line);min-width:0;touch-action:none;user-select:none}
#gl{display:block;width:100%;height:min(72vh,640px);cursor:grab}#gl:active{cursor:grabbing}
.gtools{position:absolute;right:10px;bottom:10px;display:flex;flex-direction:column;gap:6px}
.gtools button{width:34px;height:34px;background:rgba(19,19,28,.9);border:1px solid var(--line);color:var(--ink);font:700 18px "Barlow",sans-serif;cursor:pointer}
.gtools button:hover{border-color:var(--lime);color:var(--lime)}
.tip{position:absolute;pointer-events:none;background:rgba(18,18,25,.95);border:1px solid var(--line);padding:6px 9px;font-size:13px;display:none;white-space:nowrap}
.tip b{font:700 16px "Barlow Condensed",sans-serif}
.legend{position:absolute;left:12px;bottom:12px;font:11px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.05em}
.legend .bar{width:140px;height:6px;background:linear-gradient(90deg,#3a2f6b,#7a5cff,#b6f23a);margin:4px 0 2px}
.legend .ends{display:flex;justify-content:space-between}
.side{display:flex;flex-direction:column;gap:12px;min-width:0}
.card{background:var(--card);border:1px solid var(--line);padding:14px;min-width:0}
.lbl{color:var(--red);font:12px "Barlow Condensed",sans-serif;letter-spacing:.06em;text-transform:uppercase}
h2{margin:2px 0 0;font-size:20px}.big{font:700 44px/1 "Barlow Condensed",sans-serif;margin-top:6px}.sub{color:var(--muted);font-size:13px}
.kv{display:flex;gap:16px;margin-top:6px}.kv div{font:600 18px "Barlow Condensed",sans-serif}.kv small{display:block;font:11px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.05em}
.gm{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.gm a{font-size:12px;text-decoration:none;background:var(--card2);border:1px solid var(--line);padding:3px 8px;border-radius:99px}.gm a b{font-weight:600;color:var(--lime);margin-left:4px}
.row{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:9px;align-items:center;padding:7px 0;text-decoration:none;border-bottom:1px solid #1c1c29}
.row:last-child{border-bottom:0}.row .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.row .ds{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .vv{font:600 16px "Barlow Condensed",sans-serif;text-align:right}
.av{position:relative;width:34px;height:34px}.av img,.av .ph{width:34px;height:34px;border-radius:50%;object-fit:cover;background:var(--card2);border:1px solid var(--line);display:grid;place-items:center;font:700 11px "Barlow",sans-serif;color:var(--muted)}
.av .bd{position:absolute;right:-3px;bottom:-3px;width:14px;height:14px;border-radius:4px;display:grid;place-items:center;font:700 8px "Barlow",sans-serif;color:#0b0b12;border:2px solid var(--card)}
.rank{margin-top:8px;display:grid;gap:2px}
.cr{display:grid;grid-template-columns:22px minmax(0,1fr) 70px;gap:8px;align-items:center;padding:6px 6px;cursor:pointer;border:1px solid transparent;font-size:14px}
.cr:hover,.cr.on{background:var(--card2);border-color:var(--line)}.cr.on{border-color:var(--lime)}
.cr .rk{font:12px "Barlow Condensed",sans-serif;color:var(--muted)}.cr .n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cr .b{grid-column:2/4;height:3px;background:var(--line)}.cr .b div{height:100%;background:var(--purple)}
.cr .v{text-align:right;font:600 16px "Barlow Condensed",sans-serif}
.note{color:var(--muted);font-size:12px;margin-top:12px;line-height:1.6}
.empty{color:var(--muted);font-size:14px;padding:6px 0}
@media(max-width:900px){.stage{grid-template-columns:1fr}#gl{height:min(62vh,460px)}}
@media(max-width:600px){.wrap{padding:0 12px 20px}.top .in{padding:9px 12px;gap:10px}.brand{font-size:15px}.upd span{display:none}h1{font-size:26px}.intro{font-size:13px;color:var(--muted)}
.crumb{margin-top:12px;font-size:11px}#gl{height:380px}.big{font-size:36px}.legend .bar{width:100px}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="/">__BRAND__</a><span class="beta">BETA</span><span class="rg"><a href="/">GLOBAL</a><a href="/india">INDIA</a><a href="/map" class="on">MAP</a></span><span class="upd"><span class="dot"></span><span>LIVE </span><b id="upd">-</b></span></div></div>
<div class="wrap">
<div class="crumb"><a href="/">WORLDWIDE</a> / WORLD MAP</div>
<h1>Who the world is <em>watching</em>, right now</h1>
<p class="intro">Live viewers on YouTube, Kick and Twitch by the streamer's country. Drag to spin, pinch to zoom, tap a country to see its top games and streamers.</p>
<div class="stage">
 <div class="globe" id="gwrap"><canvas id="gl"></canvas><div class="tip" id="tip"></div>
  <div class="legend"><div>VIEWERS WATCHING</div><div class="bar"></div><div class="ends"><span>fewer</span><span>most</span></div></div>
  <div class="gtools"><button id="zin" aria-label="Zoom in">+</button><button id="zout" aria-label="Zoom out">&minus;</button><button id="spin" aria-label="Spin" title="Spin">&#8635;</button></div></div>
 <div class="side">
  <div class="card" id="sel"></div>
  <div class="card"><div class="lbl">// Countries</div><h2>Most watched now</h2><div class="rank" id="rank"></div></div>
 </div>
</div>
<div class="note" id="note"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js"></script>
<script>
const COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const av=x=>`<span class="av">${x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph>${ini(x.name)}</span>'">`:`<span class="ph">${ini(x.name)}</span>`}<span class="bd" style="background:${COL[x.platform]||'#888'}">${(x.platform||'?')[0].toUpperCase()}</span></span>`;
const cv=document.getElementById('gl'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let W=0,H=0,R=0,zoom=1,rot=[-78,-18,0],spin=true,idleT=0,G=null,BY={},MAX=1,LAND=null,FEATS=[],sel=null,hover=null,anim=null;
const proj=d3.geoOrthographic().clipAngle(90).precision(.4),path=d3.geoPath(proj,ctx),grat=d3.geoGraticule10(),SPHERE={type:'Sphere'};
const shade=d3.scaleLinear().domain([0,.5,1]).range(['#3a2f6b','#7a5cff','#b6f23a']).interpolate(d3.interpolateRgb).clamp(true);
const lvl=v=>v>0?Math.log1p(v)/Math.log1p(MAX):0;
function size(){const r=cv.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,2);W=r.width;H=r.height;cv.width=W*dpr;cv.height=H*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);R=Math.min(W,H)/2-14;draw()}
function draw(){if(!W)return;proj.translate([W/2,H/2]).scale(R*zoom).rotate(rot);ctx.clearRect(0,0,W,H);
 const cx=W/2,cy=H/2,rr=R*zoom;
 const glow=ctx.createRadialGradient(cx,cy,rr*.9,cx,cy,rr*1.18);glow.addColorStop(0,'rgba(124,92,255,.35)');glow.addColorStop(1,'rgba(124,92,255,0)');ctx.fillStyle=glow;ctx.beginPath();ctx.arc(cx,cy,rr*1.18,0,7);ctx.fill();
 const sea=ctx.createRadialGradient(cx-rr*.35,cy-rr*.4,rr*.1,cx,cy,rr);sea.addColorStop(0,'#1d1745');sea.addColorStop(1,'#0c0a1f');
 ctx.beginPath();path(SPHERE);ctx.fillStyle=sea;ctx.fill();
 ctx.beginPath();path(grat);ctx.strokeStyle='rgba(165,139,255,.08)';ctx.lineWidth=.6;ctx.stroke();
 for(const f of FEATS){const d=BY[f.id];ctx.beginPath();path(f);
  ctx.fillStyle=d?shade(lvl(d.viewers)):'#1c1a2e';ctx.fill();
  ctx.strokeStyle=(sel&&sel===f.id)?'#ffffff':(hover===f.id?'#b6f23a':'rgba(11,11,18,.9)');ctx.lineWidth=(sel===f.id||hover===f.id)?1.6:.5;ctx.stroke()}
 const t=performance.now()/1000,c0=[-rot[0],-rot[1]];
 for(const d of (G?G.countries:[])){const f=FEATS.find(f=>f.id===d.id);if(!f)continue;const c=f.c;if(d3.geoDistance(c,c0)>1.45)continue;
  const p=proj(c),r=Math.max(2.5,Math.sqrt(d.viewers/MAX)*18)*Math.sqrt(zoom),ph=(t*.8+d.num%7/7)%1;
  ctx.beginPath();ctx.arc(p[0],p[1],r*(1+ph*1.6),0,7);ctx.strokeStyle=`rgba(182,242,58,${.5*(1-ph)})`;ctx.lineWidth=1.2;ctx.stroke();
  ctx.beginPath();ctx.arc(p[0],p[1],Math.max(2,r*.45),0,7);ctx.fillStyle='#eaffc0';ctx.shadowColor='#b6f23a';ctx.shadowBlur=10;ctx.fill();ctx.shadowBlur=0}
 const hi=ctx.createRadialGradient(cx-rr*.4,cy-rr*.45,0,cx,cy,rr);hi.addColorStop(0,'rgba(255,255,255,.07)');hi.addColorStop(.6,'rgba(255,255,255,0)');hi.addColorStop(1,'rgba(0,0,0,.35)');
 ctx.beginPath();path(SPHERE);ctx.fillStyle=hi;ctx.fill();ctx.strokeStyle='rgba(165,139,255,.35)';ctx.lineWidth=1;ctx.stroke()}
let last=performance.now();
function tick(now){const dt=Math.min(.05,(now-last)/1000);last=now;
 if(anim){const k=Math.min(1,(now-anim.t0)/900),e=d3.easeCubicInOut(k);rot=anim.i(e);if(k>=1)anim=null}
 else if(spin&&now>idleT)rot=[rot[0]+dt*5,rot[1],0];draw();requestAnimationFrame(tick)}
function at(e){const r=cv.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]}
function featAt(p){const ll=proj.invert(p);if(!ll||d3.geoDistance(ll,[-rot[0],-rot[1]])>Math.PI/2)return null;return FEATS.find(f=>d3.geoContains(f,ll))||null}
const P=new Map();let moved=0,pinch0=null;
cv.addEventListener('pointerdown',e=>{cv.setPointerCapture(e.pointerId);P.set(e.pointerId,at(e));moved=0;anim=null;idleT=performance.now()+8000;
 if(P.size===2){const [a,b]=[...P.values()];pinch0={d:Math.hypot(a[0]-b[0],a[1]-b[1]),z:zoom}}});
cv.addEventListener('pointermove',e=>{const p=at(e);
 if(!P.has(e.pointerId)){const f=featAt(p);const id=f?f.id:null;if(id!==hover){hover=id}showTip(f,p);return}
 const q=P.get(e.pointerId);P.set(e.pointerId,p);
 if(P.size===2&&pinch0){const [a,b]=[...P.values()];zoom=Math.max(.8,Math.min(6,pinch0.z*Math.hypot(a[0]-b[0],a[1]-b[1])/pinch0.d));return}
 const dx=p[0]-q[0],dy=p[1]-q[1];moved+=Math.abs(dx)+Math.abs(dy);const k=75/(R*zoom);
 rot=[rot[0]+dx*k,Math.max(-80,Math.min(80,rot[1]-dy*k)),0];idleT=performance.now()+8000});
function up(e){const p=at(e);P.delete(e.pointerId);if(P.size<2)pinch0=null;if(moved<6&&P.size===0){const f=featAt(p);if(f)select(f.id,false)}}
cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',e=>{P.delete(e.pointerId);pinch0=null});
cv.addEventListener('pointerleave',()=>{hover=null;tip.style.display='none'});
cv.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.8,Math.min(6,zoom*Math.exp(-e.deltaY*.0015)));idleT=performance.now()+8000},{passive:false});
document.getElementById('zin').onclick=()=>{zoom=Math.min(6,zoom*1.4)};document.getElementById('zout').onclick=()=>{zoom=Math.max(.8,zoom/1.4)};
document.getElementById('spin').onclick=()=>{spin=!spin;idleT=0};
function showTip(f,p){if(!f||window.matchMedia('(hover:none)').matches){tip.style.display='none';return}const d=BY[f.id];
 tip.innerHTML=`${esc(f.properties.name)}<br><b>${d?full(d.viewers):'0'}</b> <span style="color:#8d8ca3">watching${d?' // '+d.channels+' live':''}</span>`;tip.style.display='block';
 const x=Math.min(p[0]+14,W-tip.offsetWidth-6);tip.style.left=x+'px';tip.style.top=(p[1]+14)+'px'}
function flyTo(id){const f=FEATS.find(f=>f.id===id);if(!f)return;const to=[-f.c[0],Math.max(-60,Math.min(60,-f.c[1])),0];
 const from=rot.slice();if(to[0]-from[0]>180)to[0]-=360;if(from[0]-to[0]>180)to[0]+=360;anim={t0:performance.now(),i:d3.interpolate(from,to)};idleT=performance.now()+12000}
function select(id){sel=id;flyTo(id);renderSide();renderRank()}
function renderSide(){const box=document.getElementById('sel');if(!G){box.innerHTML='<div class="empty">Loading...</div>';return}
 const d=sel&&BY[sel],f=sel&&FEATS.find(f=>f.id===sel);
 if(!d){const tot=G.known+G.unknown;box.innerHTML=`<div class="lbl">// Worldwide</div><h2>${f?esc(f.properties.name)+': nothing live tracked':'Everyone we track'}</h2>
  <div class="big">${full(tot)}</div><div class="sub">watching live right now</div>
  <div class="kv"><div>${G.countries.length}<small>COUNTRIES</small></div><div>${tot?Math.round(100*G.known/tot):0}%<small>LOCATION KNOWN</small></div></div>
  <div class="sub" style="margin-top:10px">Tap a country on the globe or in the list.</div>`;return}
 const tot=G.known+G.unknown;
 box.innerHTML=`<div class="lbl">// ${esc(d.country)}</div><h2>${esc(d.name)}</h2><div class="big">${full(d.viewers)}</div><div class="sub">watching streamers from ${esc(d.name)} right now</div>
  <div class="kv"><div>${d.channels}<small>LIVE CHANNELS</small></div><div>${tot?(100*d.viewers/tot).toFixed(1):0}%<small>OF WORLD TRACKED</small></div></div>
  <div class="gm">${d.games.map(g=>`<a href="/c/${esc(g.slug)}">${esc(g.game)}<b>${fmt(g.viewers)}</b></a>`).join('')}</div>
  <div style="margin-top:10px">${d.top.map(x=>`<a class="row" href="${esc(x.url)}" target="_blank" rel="noopener">${av(x)}<span style="min-width:0"><div class="nm">${esc(x.name)}</div><div class="ds">${esc(x.game)}</div></span><span class="vv">${full(x.viewers)}</span></a>`).join('')}</div>
  ${d.country==='IN'?'<div class="sub" style="margin-top:8px"><a href="/india" style="color:#b6f23a">Full India dashboard &rarr;</a></div>':''}`}
function renderRank(){const C=(G?G.countries:[]).slice(0,25);
 document.getElementById('rank').innerHTML=C.map((d,i)=>`<div class="cr${sel===d.id?' on':''}" data-id="${d.id}"><span class="rk">${i+1}</span><span class="n">${esc(d.name)} <span style="color:#8d8ca3;font-size:12px">${d.games[0]?esc(d.games[0].game):''}</span></span><span class="v">${fmt(d.viewers)}</span><span></span><span class="b"><div style="width:${(100*d.viewers/MAX).toFixed(1)}%"></div></span></div>`).join('')||'<div class="empty">Nothing live with a known location yet.</div>';
 document.querySelectorAll('.cr').forEach(e=>e.onclick=()=>select(e.dataset.id))}
async function load(){try{const j=await (await fetch('/api/geo?t='+Math.floor(Date.now()/5000),{cache:'no-store'})).json();
 j.countries.forEach(d=>d.id=String(d.num).padStart(3,'0'));G=j;BY=Object.fromEntries(j.countries.map(d=>[d.id,d]));MAX=Math.max(1,...j.countries.map(d=>d.viewers));
 const tot=j.known+j.unknown;document.getElementById('upd').textContent=new Date().toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit',second:'2-digit'});
 document.getElementById('note').innerHTML=`<b style="color:#eeeef5">How location is known.</b> A YouTube channel's own country setting; streams detected as Indian count as India; Kick and Twitch give no country, so a stream in a language spoken mainly in one country (Korean, Japanese, Turkish, Polish, Thai ...) is placed there (${fmt(j.estimated)} viewers estimated this way). The rest (${fmt(j.unknown)} viewers, ${tot?Math.round(100*j.unknown/tot):0}% of everyone tracked, mostly English and Spanish streams on Kick and Twitch) have no location and are not on the map. Streams are those tracked on the <a href="/" style="color:#b6f23a">live dashboard</a>.`;
 renderSide();renderRank()}catch(e){}}
(async()=>{const w=await (await fetch('https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json')).json();
 LAND=topojson.feature(w,w.objects.countries);FEATS=LAND.features.filter(f=>f.id&&f.id!=='010');FEATS.forEach(f=>f.c=d3.geoCentroid(f));
 size();renderSide();await load();requestAnimationFrame(tick);setInterval(()=>{if(!document.hidden)load()},5000)})();
window.addEventListener('resize',size);
</script></body></html>"""


def build_html() -> str:
    return PAGE.replace("__BRAND__", html.escape(eventpage.BRAND))
