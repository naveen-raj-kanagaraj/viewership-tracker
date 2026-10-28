"""/ch/<sid> and /india/ch/<sid>: one channel's page. Everything the site recorded (scenepage.PANEL_JS: today / 7 / 30
days / all time, Super Chats, subscribers and views), plus its streams in the last 30 days as the platform lists them
(/api/past, ytextra.past_streams). Search results open here; the Watch button goes to the stream."""
import html
import json

from tracker import eventpage, scenepage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__NAME__ live stats | __BRAND__ (beta)</title>
<meta name="description" content="__NAME__: live viewers, peak, average viewers, hours watched, Super Chats and past streams.">
<meta property="og:title" content="__NAME__ live stats | __BRAND__"><meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body{background:radial-gradient(900px 420px at 85% -15%,rgba(124,92,255,.13),transparent 60%),var(--bg);min-height:100vh}a{color:inherit}
.top{position:sticky;top:0;z-index:30;background:rgba(11,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1000px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;letter-spacing:.04em;white-space:nowrap}
.beta{font:700 10px "Barlow Condensed",sans-serif;color:#0b0b12;background:var(--lime);padding:2px 6px;letter-spacing:.08em;margin-left:-6px}
.nav{margin-left:auto;display:flex;gap:12px;font:13px "Barlow Condensed",sans-serif;letter-spacing:.04em}.nav a{text-decoration:none;color:var(--muted)}.nav a:hover{color:var(--lime)}
.wrap{max-width:1000px;margin:0 auto;padding:0 16px 28px}
.crumb{font:12px "Barlow Condensed",sans-serif;color:var(--muted);margin-top:18px;letter-spacing:.04em}.crumb a{text-decoration:none}
.hd{display:grid;grid-template-columns:84px minmax(0,1fr) auto;gap:16px;align-items:center;margin-top:12px}
.hd img,.hd .ph{width:84px;height:84px;border-radius:50%;object-fit:cover;border:2px solid var(--line);background:var(--card2);display:grid;place-items:center;font:700 26px "Barlow",sans-serif;color:var(--muted)}
.hd.live img,.hd.live .ph{border-color:var(--red);box-shadow:0 0 0 3px rgba(255,77,94,.25)}
h1{font:700 40px/1.05 "Barlow Condensed",sans-serif;margin:0;text-transform:uppercase;word-break:break-word}
.meta{color:var(--muted);font-size:14px;margin-top:4px}.meta b{color:var(--ink);font-weight:600}
.btn{background:var(--lime);color:#0b0b12;border:0;font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.05em;padding:9px 16px;cursor:pointer;text-decoration:none;display:inline-block;white-space:nowrap}
.btn.red{background:var(--red);color:#fff}
.card{background:var(--card);border:1px solid var(--line);margin-top:14px}
.card h2{font-size:19px;margin:0;padding:14px 16px 0}.card .cap{color:var(--muted);font-size:12px;padding:2px 16px 0}
.lv{color:var(--red);font:600 11px "Barlow Condensed",sans-serif;margin-right:4px}.lv:before{content:"\25CF ";}
.av{position:relative;width:38px;height:38px}.av img,.av .ph{width:38px;height:38px;border-radius:50%;object-fit:cover}.av .bd{display:none}
.lbl{color:var(--red);font:12px "Barlow Condensed",sans-serif;letter-spacing:.06em;text-transform:uppercase}.muted{color:var(--muted)}
.cx{border-left:0;background:transparent;padding:6px 16px 16px}.cx .cxh,.cx .cxtt{display:none}
.ps{padding:6px 16px 14px}.ps a{display:grid;grid-template-columns:96px minmax(0,1fr) 80px 80px 90px;gap:10px;padding:9px 0;border-bottom:1px solid #1c1c29;text-decoration:none;align-items:center}
.ps a:hover .t{color:var(--lime)}.ps .d{color:var(--muted);font-size:12px}.ps .t{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ps .n{text-align:right;font:600 15px "Barlow Condensed",sans-serif}.ps .n small{display:block;font:400 11px "Barlow",sans-serif;color:var(--muted)}
.ps .hdr{display:grid;grid-template-columns:96px minmax(0,1fr) 80px 80px 90px;gap:10px;font:500 11px "Barlow Condensed",sans-serif;color:var(--muted);letter-spacing:.05em;padding:4px 0;border-bottom:1px solid var(--line)}
.ps .hdr span:nth-child(n+3){text-align:right}
.empty{color:var(--muted);padding:12px 16px 16px}
.vk{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:12px 16px 0}.vk div{background:var(--card2);padding:10px 12px;font-size:12px;color:var(--muted)}
.vk b{display:block;font:700 24px "Barlow Condensed",sans-serif;color:var(--ink)}.vk b.up{color:var(--lime)}
.vseg{display:inline-flex;border:1px solid var(--line);margin:12px 16px 0}.vseg button{background:none;border:0;color:var(--muted);font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.04em;padding:6px 10px;cursor:pointer}.vseg button.on{background:var(--lime);color:#0b0b12}
#vchart{display:block;width:calc(100% - 32px);height:200px;margin:10px 16px 0}
.vtools{display:flex;flex-wrap:wrap;gap:0 8px}.vtools .vseg{margin-right:0}
#vidchart{display:block;width:calc(100% - 32px);height:220px;margin:12px 16px 0;cursor:crosshair}
.vtip{position:fixed;pointer-events:none;background:rgba(18,18,25,.96);border:1px solid var(--line);padding:6px 9px;font-size:12px;max-width:280px;display:none;z-index:50}
.vtip b{font:700 15px "Barlow Condensed",sans-serif}
.vl a{grid-template-columns:70px minmax(0,1fr) 70px 70px 70px 64px!important}.vl .hdr{grid-template-columns:70px minmax(0,1fr) 70px 70px 70px 64px!important}
.lvtag{color:var(--red);font:600 10px "Barlow Condensed",sans-serif;margin-right:4px;letter-spacing:.04em}
.vm{padding:8px 16px 16px;display:flex;flex-wrap:wrap;gap:6px}.vm span{background:var(--card2);padding:5px 9px;font-size:12px;color:var(--muted)}.vm b{color:var(--ink);font-weight:600}
__PANEL_CSS__
@media(max-width:640px){#vidchart{width:calc(100% - 24px);margin:10px 12px 0;height:180px}.vtools{padding:0}
.vl a,.vl .hdr{grid-template-columns:58px minmax(0,1fr) 62px!important}.vl a>:nth-child(n+4),.vl .hdr>:nth-child(n+4){display:none}
.vk{grid-template-columns:repeat(2,1fr);padding:10px 12px 0}.vk div:last-child{grid-column:1/-1}#vchart{width:calc(100% - 24px);margin:10px 12px 0;height:170px}.vseg{margin:10px 12px 0}.vm{padding:8px 12px 12px}
.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.brand{font-size:15px}.nav{gap:8px}
.hd{grid-template-columns:60px minmax(0,1fr);gap:12px}.hd img,.hd .ph{width:60px;height:60px}h1{font-size:28px}.hd .act{grid-column:1/-1}.hd .act .btn{width:100%;text-align:center}
.cx{padding:4px 12px 12px}.cxc{grid-template-columns:1fr}.cxt td{font-size:14px;padding:4px 3px}.cxt th{padding:4px 3px;font-size:10px}.cxd div{grid-template-columns:52px minmax(0,1fr) 64px 50px}.cxd div span:nth-child(5){display:none}
.ps{padding:4px 12px 12px}.ps a,.ps .hdr{grid-template-columns:62px minmax(0,1fr) 64px}.ps a>:nth-child(3),.ps .hdr>:nth-child(3),.ps a>:nth-child(5),.ps .hdr>:nth-child(5){display:none}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / CHANNEL</div>
<div class="hd" id="hd"><span class="ph">..</span><div><h1>__NAME__</h1><div class="meta">Loading...</div></div></div>
<div class="card" id="vidcard" style="display:none"><h2>Videos and streams</h2><div class="cap" id="vidcap"></div>
 <div class="vtools"><div class="vseg" id="vrange"></div><div class="vseg" id="vkind"></div></div>
 <div class="vk" id="vidk"></div><canvas id="vidchart"></canvas><div class="vtip" id="vtip"></div>
 <div class="ps" id="vidlist"></div></div>
<div class="card" id="vcard" style="display:none"><h2>Channel views on YouTube</h2><div class="cap">The channel's public counters on YouTube (total views of all its videos, live and uploaded; subscribers), recorded once a day by this site. Views gained = how much the total grew between two days.</div><div id="views"></div></div>
<div class="card" id="lcard"><h2>Live stats on this site</h2><div class="cap">Recorded by this site every 2 seconds while the channel is live.</div><div id="stats"></div></div>
<div class="card" id="mcard" style="display:none"><h2>Moments</h2><div class="cap">Sudden jumps in viewers on this channel, newest first. Opens at the moment.</div><div class="ps" id="moms"></div></div>
<div class="card"><h2>Streams, last 30 days</h2><div class="cap" id="pcap">From the platform's own list of past streams.</div><div id="past"><div class="empty">Loading...</div></div></div>
</div>
<script>
const SID=__SID__,REGION=__REGION__,RP=REGION==='in'?'/india':'';
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e9?(n/1e9).toFixed(2)+'B':n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ist=(ts,o)=>new Date(ts*1000).toLocaleString('en-IN',Object.assign({timeZone:'Asia/Kolkata'},o));
const ago=ts=>{const s=Date.now()/1000-ts;return s<120?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const av=x=>x.logo?`<img src="${esc(x.logo)}" alt="" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph>${ini(x.name)}</span>'">`:`<span class="ph">${ini(x.name)}</span>`;
const liveMap=()=>({});let OPEN=null;function render(){}
__PANEL_JS__
let VR=30,VRANGE='3m',VKIND='all',VID=null;
const RANGES=[['1w','1W'],['1m','1M'],['3m','3M'],['6m','6M'],['ytd','YTD'],['1y','1Y']];
async function videos(){if(!SID.startsWith('yt:'))return;try{const j=await (await fetch(`/api/videos?sid=${encodeURIComponent(SID)}&range=${VRANGE}&kind=${VKIND}`)).json();VID=j;
 const box=document.getElementById('vidcard');if(!j.oldest){box.style.display='none';return}box.style.display='';
 document.getElementById('vidcap').textContent=`Every upload and past live stream on the channel, by the day it was posted. Views, likes and comments are their totals so far, from YouTube (refreshed every 6 hours).`+(j.exact?'':' Dates are approximate ("3 weeks ago") and likes and comments need a YouTube API key on the server.');
 const sg=(id,opts,cur,on)=>{const e=document.getElementById(id);e.innerHTML=opts.map(([v,l])=>`<button data-v="${v}" class="${v===cur?'on':''}">${l}</button>`).join('');e.onclick=ev=>{const b=ev.target.closest('button');if(b)on(b.dataset.v)}};
 sg('vrange',RANGES,VRANGE,v=>{VRANGE=v;videos()});sg('vkind',[['all','ALL'],['uploads','UPLOADS'],['live','LIVE STREAMS']],VKIND,v=>{VKIND=v;videos()});
 document.getElementById('vidk').innerHTML=`<div><b>${full(j.count)}</b>videos${j.lives&&VKIND==='all'?` (${j.lives} live)`:''} · ${j.per_week}/week</div><div><b class="up">${fmt(j.views)}</b>views on them</div><div><b>${fmt(j.avg)}</b>average per video</div><div><b>${fmt(j.median)}</b>median per video</div><div><b>${j.engagement!=null?j.engagement+'%':'-'}</b>engagement${j.likes!=null?` · ${fmt(j.likes)} likes, ${fmt(j.comments)} comments`:''}</div>`;
 drawVids();
 const L=(j.videos||[]).slice().sort((a,b)=>(b.views||0)-(a.views||0)).slice(0,15);
 document.getElementById('vidlist').className='ps vl';
 document.getElementById('vidlist').innerHTML=L.length?`<div class="hdr"><span>POSTED</span><span>TOP VIDEOS IN THIS RANGE</span><span>VIEWS</span><span>LIKES</span><span>COMMENTS</span><span>ENGAGE</span></div>${L.map(v=>`<a href="https://www.youtube.com/watch?v=${esc(v.vid)}" target="_blank" rel="noopener"><span class="d">${v.ts?(v.approx?'~':'')+ist(v.ts,{day:'numeric',month:'short'}):''}</span><span class="t">${v.live?'<span class="lvtag">LIVE</span>':''}${esc(v.title)}</span><span class="n">${fmt(v.views)}</span><span class="n">${v.likes!=null?fmt(v.likes):'-'}</span><span class="n">${v.comments!=null?fmt(v.comments):'-'}</span><span class="n">${v.likes!=null&&v.views?(100*((v.likes||0)+(v.comments||0))/v.views).toFixed(1)+'%':'-'}</span></a>`).join('')}`:'<div class="empty">Nothing posted in this range.</div>'}catch(e){}}
function drawVids(){const cv=document.getElementById('vidchart'),j=VID;if(!cv||!j)return;const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);
 const L=(j.videos||[]).filter(v=>v.ts),t0=j.since,t1=Date.now()/1000,pb=22,pr=50,mx=Math.max(1,...L.map(v=>v.views||0))*1.12,X=t=>(W-pr)*(t-t0)/(t1-t0),Y=v=>(H-pb)*(1-v/mx);
 x.font='11px "Barlow Condensed",sans-serif';x.strokeStyle='#262636';x.fillStyle='#8d8ca3';
 for(let i=0;i<=3;i++){const y=(H-pb)*i/3;x.beginPath();x.moveTo(0,y);x.lineTo(W-pr,y);x.stroke();x.fillText(fmt(mx*(1-i/3)),W-pr+4,y+10)}
 const nt=W<500?3:6;for(let i=0;i<=nt;i++){const t=t0+(t1-t0)*i/nt;x.textAlign=i===0?'left':i===nt?'right':'center';x.fillText(new Date(t*1000).toLocaleDateString('en-IN',{day:'numeric',month:'short'}),X(t),H-6)}x.textAlign='left';
 const bw=Math.max(2,Math.min(14,(W-pr)/Math.max(L.length,1)*.7)),best=L.reduce((a,v)=>(v.views||0)>((a&&a.views)||0)?v:a,null);
 cv._pts=L.map(v=>{const px=X(v.ts),py=Y(v.views||0);x.fillStyle=v===best?'#b6f23a':v.live?'#ff4d5e':'#7a5cff';x.fillRect(px-bw/2,py,bw,H-pb-py);return [px,py,v]});
 const tip=document.getElementById('vtip');cv.onmousemove=e=>{const r=cv.getBoundingClientRect(),mxp=e.clientX-r.left;let b=null,d=1e9;for(const p of cv._pts){const dd=Math.abs(p[0]-mxp);if(dd<d){d=dd;b=p}}
  if(!b||d>20){tip.style.display='none';return}const v=b[2];tip.innerHTML=`${v.live?'<span class="lvtag">LIVE</span>':''}${esc(v.title)}<br><b>${fmt(v.views)}</b> views${v.likes!=null?' · '+fmt(v.likes)+' likes':''} · ${v.approx?'~':''}${ist(v.ts,{day:'numeric',month:'short',year:'numeric'})}`;tip.style.display='block';tip.style.left=Math.min(e.clientX+12,innerWidth-290)+'px';tip.style.top=(e.clientY+12)+'px'};
 cv.onmouseleave=()=>{tip.style.display='none'};cv.onclick=e=>{const r=cv.getBoundingClientRect(),mxp=e.clientX-r.left;const b=cv._pts.reduce((a,p)=>!a||Math.abs(p[0]-mxp)<Math.abs(a[0]-mxp)?p:a,null);if(b&&Math.abs(b[0]-mxp)<20)window.open('https://www.youtube.com/watch?v='+b[2].vid,'_blank','noopener')}}
window.addEventListener('resize',()=>{drawVids()});
function viewsCard(c){const V=c.views,S=c.stats;const box=document.getElementById('vcard');if(!V||!(V.snapshots||[]).length){box.style.display='none';return}box.style.display='';
 if(c.platform!=='youtube')return followersCard(c);
 const G=V.gains||[],sum=n=>G.filter(g=>g.day>=new Date(Date.now()-n*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'})).reduce((a,g)=>a+g.views,0),last=G[G.length-1];
 const sg=G.filter(g=>g.subs!=null).slice(-7).reduce((a,g)=>a+g.subs,0);
 document.getElementById('views').innerHTML=`<div class="vk"><div><b>${S&&S.views!=null?fmt(S.views):'-'}</b>total views</div><div><b>${S&&S.subs!=null?fmt(S.subs):'hidden'}</b>subscribers</div>
  <div><b class="up">${last?'+'+fmt(last.views):'-'}</b>views, last day</div><div><b class="up">${G.length?'+'+fmt(sum(7)):'-'}</b>views, 7 days</div><div><b class="up">${G.length?'+'+fmt(sum(30)):'-'}</b>views, 30 days${G.length?'':''}</div></div>
  ${G.length?`<div class="vseg" id="vseg">${[[7,'1W'],[30,'1M'],[91,'3M'],[182,'6M'],[Math.ceil((Date.now()-new Date(new Date().getFullYear(),0,1))/864e5),'YTD'],[365,'1Y']].map(([v,l])=>`<button data-v="${v}" class="${v===VR?'on':''}">${l}</button>`).join('')}</div><canvas id="vchart"></canvas>
  <div class="vm">${(V.months||[]).slice(-6).map(m=>`<span>${new Date(m.month+'-15').toLocaleDateString('en-IN',{month:'short',year:'numeric'})} <b>+${fmt(m.views)}</b> views</span>`).join('')}${sg?`<span>Subscribers, 7 days <b>${sg>=0?'+':''}${fmt(sg)}</b></span>`:''}<span>Recorded since ${dshortD(V.first)}</span></div>`
  :`<div class="empty">First snapshot taken ${dshortD(V.first)}. Views gained per day start showing tomorrow, and weekly and monthly totals build up from there.</div>`}`;
 const sg_=document.getElementById('vseg');if(sg_)sg_.onclick=e=>{const b=e.target.closest('button');if(b){VR=+b.dataset.v;viewsCard(c)}};drawViews(G)}
function followersCard(c){const V=c.views,P=NAMES[c.platform]||'';
 document.querySelector('#vcard h2').textContent='Followers on '+P;
 document.querySelector('#vcard .cap').textContent=`The channel's follower count on ${P}, recorded once a day by this site. Followers gained = how much it grew between two days. `+(c.platform==='kick'?"Kick doesn't publish this officially: it's read from Kick's public channel data.":'Twitch only shows follower totals to logged-in accounts: read with the account connected to this site.');
 const G=(V.gains||[]).filter(g=>g.subs!=null).map(g=>({day:g.day,views:Math.max(0,g.subs)})),sum=n=>G.filter(g=>g.day>=new Date(Date.now()-n*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'})).reduce((a,g)=>a+g.views,0),last=G[G.length-1],tot=(V.snapshots[V.snapshots.length-1]||{}).subs;
 document.getElementById('views').innerHTML=`<div class="vk"><div><b>${tot!=null?fmt(tot):'-'}</b>followers</div><div><b class="up">${last?'+'+fmt(last.views):'-'}</b>followers, last day</div><div><b class="up">${G.length?'+'+fmt(sum(7)):'-'}</b>followers, 7 days</div><div><b class="up">${G.length?'+'+fmt(sum(30)):'-'}</b>followers, 30 days</div><div><b>${dshortD(V.first)}</b>recorded since</div></div>
  ${G.length?`<div class="vseg" id="vseg">${[[7,'7D'],[30,'30D'],[90,'90D']].map(([v,l])=>`<button data-v="${v}" class="${v===VR?'on':''}">${l}</button>`).join('')}</div><canvas id="vchart"></canvas><div class="vm"></div>`
  :`<div class="empty">First count taken ${dshortD(V.first)}. Followers gained per day start showing tomorrow.</div>`}`;
 const sg_=document.getElementById('vseg');if(sg_)sg_.onclick=e=>{const b=e.target.closest('button');if(b){VR=+b.dataset.v;followersCard(c)}};drawViews(G)}
const dshortD=d=>d?new Date(d+'T12:00:00+05:30').toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}):'';
function drawViews(G){const cv=document.getElementById('vchart');if(!cv)return;const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);
 const S=G.slice(-VR),mx=Math.max(1,...S.map(g=>g.views))*1.15,pb=22,pr=46,bw=(W-pr)/Math.max(S.length,7),best=S.reduce((a,g,i)=>g.views>S[a].views?i:a,0);
 x.font='11px "Barlow Condensed",sans-serif';x.fillStyle='#8d8ca3';x.strokeStyle='#262636';
 for(let i=0;i<=3;i++){const y=6+(H-pb-6)*i/3;x.beginPath();x.moveTo(0,y);x.lineTo(W-pr,y);x.stroke();x.fillText('+'+fmt(mx*(1-i/3)),W-pr+4,y+4)}
 S.forEach((g,i)=>{const h=(H-pb-6)*g.views/mx,bx=i*bw+bw*.15;x.fillStyle=i===best?'#b6f23a':'#7a5cff';x.fillRect(bx,H-pb-h,bw*.7,h);
  if(i===best||i===S.length-1||S.length<=8){x.fillStyle=i===best?'#b6f23a':'#eeeef5';x.textAlign='center';x.fillText('+'+fmt(g.views),bx+bw*.35,H-pb-h-4)}
  if(i%Math.ceil(S.length/7)===0||i===S.length-1){x.fillStyle='#8d8ca3';x.textAlign='center';x.fillText(new Date(g.day+'T12:00:00+05:30').toLocaleDateString('en-IN',{day:'numeric',month:'short'}),bx+bw*.35,H-6)}x.textAlign='left'})}
const hm=s=>{s=+s||0;const h=Math.floor(s/3600),m=Math.round(s%3600/60);return h?`${h}h ${m}m`:`${m}m`};
async function load(){try{const c=await (await fetch('/api/channel?sid='+encodeURIComponent(SID)+'&t='+Math.floor(Date.now()/15000))).json();if(!c.sid)return;CH[SID]=c;
 const now=c.now,S=c.stats;
 document.getElementById('hd').className='hd'+(now?' live':'');
 document.getElementById('hd').innerHTML=`${av(c)}<div style="min-width:0"><h1>${esc(c.name)}</h1><div class="meta"><b style="color:${COL[c.platform]}">${NAMES[c.platform]||''}</b>${c.country?' · '+esc(c.country):''}${S&&S.subs!=null?' · <b>'+fmt(S.subs)+'</b> subscribers':''}${now||c.last_live?' · ':''}${now?`<span class="lv">LIVE</span><b>${full(now)}</b> watching${c.game?' · '+esc(c.game):''}`:c.last_live?'last live '+ago(c.last_live):''}</div>${now&&c.title?`<div class="meta" style="margin-top:6px">${esc(c.title)}</div>`:''}</div>
  <div class="act"><a class="btn${now?' red':''}" href="${esc(c.url)}" target="_blank" rel="noopener">${now?'WATCH LIVE':'OPEN'} ON ${(NAMES[c.platform]||'').toUpperCase()}</a></div>`;
 viewsCard(c);
 const seen=c.periods&&c.periods.all&&c.periods.all.days;
 document.getElementById('stats').innerHTML=seen?panel(SID):`<div class="empty">This site hasn't seen ${esc(c.name)} live yet. Live numbers (watching now, peak, hours watched) start the first time they stream; their YouTube channel views above are recorded every day.</div>`}catch(e){}}
async function past(){try{const j=await (await fetch('/api/past?sid='+encodeURIComponent(SID))).json();const L=j.streams||[];
 const U=[];if(U.length){
  document.getElementById('ups').innerHTML=`<div class="ps"><div class="hdr"><span>POSTED</span><span>VIDEO</span><span>LENGTH</span><span>VIEWS</span><span></span></div>${U.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener"><span class="d">${x.ts?ist(x.ts,{day:'numeric',month:'short'}):''}${x.when?'<br>'+esc(x.when.replace('Streamed ','')):''}</span><span class="t">${esc(x.title)}</span><span class="n">${x.secs?hm(x.secs):'-'}</span><span class="n">${x.views!=null?fmt(x.views):'-'}</span><span></span></a>`).join('')}</div>`}
 document.getElementById('pcap').textContent=(j.source?'From '+j.source+'. Views = total views of the stream, including replays. Peak = the most watching at once that day, recorded by this site.':'')+(j.note?' '+j.note:'');
 document.getElementById('past').innerHTML=L.length?`<div class="ps"><div class="hdr"><span>DATE</span><span>STREAM</span><span>LENGTH</span><span>VIEWS</span><span>PEAK THAT DAY</span></div>${L.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener"><span class="d">${x.ts?ist(x.ts,{day:'numeric',month:'short'}):esc(x.when)}${x.when&&/ago/.test(x.when)?'<br>'+esc(x.when.replace('Streamed ','')):''}</span><span class="t">${esc(x.title)}</span><span class="n">${x.secs?hm(x.secs):'-'}</span><span class="n">${x.views!=null?fmt(x.views):'-'}</span><span class="n">${x.peak_day?fmt(x.peak_day):'-'}</span></a>`).join('')}</div>`:`<div class="empty">${j.note?'Nothing to show here.':'No past streams listed in the last 30 days.'}</div>`}catch(e){document.getElementById('past').innerHTML='<div class="empty">Couldn\'t load past streams right now.</div>'}}
async function moms(){try{const j=await (await fetch('/api/moments?sid='+encodeURIComponent(SID))).json();const L=j.moments||[];if(!L.length)return;
 document.getElementById('mcard').style.display='';
 document.getElementById('moms').innerHTML=L.slice(0,20).map(m=>`<a href="${esc(m.link||c_url)}" target="_blank" rel="noopener"><span class="d">${ist(m.ts,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})}</span><span class="t">${esc(m.title)}</span><span class="n" style="color:var(--lime)">+${fmt(m.peak-m.base)}</span><span class="n">${fmt(m.peak)}<small>peak</small></span><span class="n">${m.embed==='tw_clip'?'clip':m.embed?'replay':'channel'}</span></a>`).join('')}catch(e){}}
let c_url='#';
load();past();moms();videos();setInterval(()=>{if(!document.hidden)load()},15000);
</script></body></html>"""


def build_html(sid: str, name: str, region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    return (PAGE.replace("__PANEL_JS__", scenepage.PANEL_JS).replace("__PANEL_CSS__", scenepage.PANEL_CSS)
            .replace("__NAME__", html.escape(name)).replace("__BRAND__", html.escape(eventpage.BRAND))
            .replace("__SID__", json.dumps(sid)).replace("__REGION__", json.dumps(region))
            .replace("__RP__", "/india" if region == "in" else "").replace("__HOME__", "/india" if region == "in" else "/")
            .replace("__WHERECAP__", "INDIA" if region == "in" else "WORLDWIDE"))
