"""/global/t/<tournament> and /india/t/<tournament>: one esports tournament with every channel that broadcasts or
co-streams it added together (official channels in every country and language, and creators' watch parties): watching
now, peak with all of them at once, today's line, peak by day, hours watched, each channel's own peak, languages, and
a share card. The tournament list comes from Liquipedia (CC-BY-SA). Data: /api/tour."""
import html
import json

from tracker import eventpage, scene

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__ live viewers __WHERE__ | __BRAND__ (beta)</title>
<meta name="description" content="__TITLE__: viewers across every channel streaming it, peak concurrent viewers, hours watched and each channel's numbers.">
<meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e;--orange:#ff8a3d;--blue:#4cc9f0}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 "Barlow",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body{background:radial-gradient(900px 420px at 85% -15%,rgba(124,92,255,.13),transparent 60%),var(--bg);min-height:100vh}a{color:inherit}
.top{position:sticky;top:0;z-index:30;background:rgba(11,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:14px}
.brand{color:var(--lime);font:700 18px "Barlow Condensed",sans-serif;text-transform:uppercase;text-decoration:none;letter-spacing:.04em;white-space:nowrap}
.beta{font:700 10px "Barlow Condensed",sans-serif;color:#0b0b12;background:var(--lime);padding:2px 6px;letter-spacing:.08em;margin-left:-6px}
.rg{display:inline-flex;border:1px solid var(--line)}.rg a{padding:4px 10px;font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.05em;text-decoration:none;color:var(--muted)}.rg a.on{background:var(--lime);color:#0b0b12}
.nav{margin-left:auto;display:flex;gap:12px;font:13px "Barlow Condensed",sans-serif;letter-spacing:.04em}.nav a{text-decoration:none;color:var(--muted)}.nav a:hover{color:var(--lime)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px 28px}
.crumb{font:12px "Barlow Condensed",sans-serif;letter-spacing:.08em;color:var(--muted);margin-top:16px;text-transform:uppercase}.crumb a{text-decoration:none}
.hd{display:flex;gap:16px;align-items:center;margin-top:8px}.hd img{width:54px;height:72px;object-fit:cover;border-radius:4px;flex:none;background:var(--card2)}
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:0;text-transform:uppercase}
.sub{color:var(--muted);margin:4px 0 0;font-size:14px}.sub a{color:var(--lime);text-decoration:none}
.lv{display:inline-block;background:var(--red);color:#fff;font:700 11px "Barlow Condensed",sans-serif;letter-spacing:.08em;padding:1px 6px;margin-right:6px;vertical-align:2px}
.trk[hidden],.hd img[hidden]{display:none!important}.trk{display:inline-block;margin-top:10px;background:var(--lime);color:#0b0b12;font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.06em;padding:7px 12px;text-decoration:none}
.kp{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:14px}.kp div{background:var(--card);border:1px solid var(--line);padding:12px 14px}
.kp b{display:block;font:700 30px "Barlow Condensed",sans-serif;line-height:1.05}.kp span{color:var(--muted);font-size:12px}.kp .big b{color:var(--lime)}
.card{background:var(--card);border:1px solid var(--line);margin-top:14px;padding:14px 16px}
h2{font:700 22px "Barlow Condensed",sans-serif;margin:0 0 8px;text-transform:uppercase;letter-spacing:.02em}h2 small{color:var(--muted);font:500 13px "Barlow",sans-serif;text-transform:none;margin-left:6px;letter-spacing:0}
table{width:100%;border-collapse:collapse}th{font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;text-align:right;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:8px;border-bottom:1px solid #1c1c29;text-align:right;white-space:nowrap}th.l,td.l{text-align:left}td a{text-decoration:none}
.c{display:flex;align-items:center;gap:10px;min-width:0}.c img,.c .ph{width:30px;height:30px;border-radius:50%;flex:none;object-fit:cover;background:var(--card2)}
.c b{font-weight:600;overflow:hidden;text-overflow:ellipsis;max-width:280px;display:block}.c small{display:block;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;max-width:420px}
.pf{font:600 10px "Barlow Condensed",sans-serif;letter-spacing:.06em;color:var(--muted);border:1px solid var(--line);padding:0 4px;margin-left:6px;vertical-align:1px}
.mu{color:var(--muted)}.empty{color:var(--muted);padding:12px 0}.note{color:var(--muted);font-size:12px;margin-top:10px}.note a{color:var(--muted)}
.bars .r{display:grid;grid-template-columns:110px 1fr 70px;gap:10px;align-items:center;padding:4px 0;font-size:13px}.bars i{display:block;height:10px;background:var(--lime)}.bars b{text-align:right}
canvas{display:block;width:100%}
.shb{float:right;background:var(--lime);color:#0b0b12;border:0;font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.06em;padding:6px 12px;cursor:pointer}
.modal{position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.82);display:none;align-items:center;justify-content:center;padding:16px}
.modal .bx{background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto}
.modal img{width:100%;max-height:68vh;object-fit:contain;display:block;border:1px solid var(--line);margin:8px 0 10px}
.mb{display:flex;gap:8px}.mb button{flex:1;background:var(--card2);border:1px solid var(--line);color:var(--ink);font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.06em;padding:9px;cursor:pointer}.mb button.p{background:var(--lime);color:#0b0b12;border-color:var(--lime)}
@media(max-width:760px){.kp{grid-template-columns:repeat(2,1fr)}.kp .big{grid-column:1/-1}.nav{display:none}h1{font-size:28px}.hide{display:none}td,th{padding:8px 4px}.c b{max-width:150px}.c small{max-width:190px}.wrap{padding:0 12px 20px}.bars .r{grid-template-columns:80px 1fr 56px}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span>
<span class="rg"><a href="/global/t/__SLUG__" class="__GON__">GLOBAL</a><a href="/india/t/__SLUG__" class="__ION__">INDIA</a></span>
<span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/s/esports">ESPORTS</a><a href="__RP__/rankings">RANKINGS</a><a href="__RP__/categories">CATEGORIES</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / <a href="__RP__/s/esports">ESPORTS</a> / TOURNAMENT</div>
<div class="hd"><img id="art" alt="" hidden><div><h1 id="h1">__TITLE__</h1><p class="sub" id="sub"></p></div></div>
<a class="trk" id="trk" hidden></a>
<div class="kp"><div class="big"><b id="k1">-</b><span>peak viewers, every channel at once</span></div><div><b id="k2">-</b><span>watching now</span></div>
<div><b id="k3">-</b><span>peak today</span></div><div><b id="k4">-</b><span>hours watched</span></div><div><b id="k5">-</b><span>channels</span></div></div>
<div class="card"><button class="shb" id="shb">SHARE</button><h2>Viewers today <small>all channels together, India time</small></h2><canvas id="ch" height="220"></canvas><div class="note" id="days"></div></div>
<div class="card"><h2>Live now <small id="lvn"></small></h2><table><thead><tr><th class="l">Channel</th><th class="hide">Language</th><th>Watching</th></tr></thead><tbody id="lv"></tbody></table></div>
<div class="card"><h2>Every channel <small>its own peak while showing this tournament</small></h2><table><thead><tr><th class="l">Channel</th><th class="hide">Language</th><th class="hide">Hours watched</th><th class="hide">Days</th><th>Peak</th></tr></thead><tbody id="chs"></tbody></table></div>
<div class="card" id="lgc"><h2>Languages <small>share of hours watched</small></h2><div class="bars" id="lg"></div></div>
<p class="note" id="src">A stream counts when its title names the tournament. Numbers are this site's readings of YouTube, Twitch and Kick. Tournament list: <a href="https://liquipedia.net" target="_blank" rel="noopener">Liquipedia</a> (CC-BY-SA).</p>
</div>
<div class="modal" id="modal"><div class="bx"><img id="mimg" alt="Share card"><div class="mb"><button class="p" id="msh">SHARE</button><button id="mdl">DOWNLOAD</button><button id="mcl">CLOSE</button></div></div></div>
<script>
const REGION=__REGIONJ__,RP=__RPJ__,SLUG=__SLUGJ__;let D=__DATA__,BLOB=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e6?(n/1e6).toFixed(n>=1e7?1:2)+'M':n>=1e3?(n/1e3).toFixed(n>=1e4?1:1)+'K':String(Math.round(n))};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ist=(t,o)=>new Date(t*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',...o});
const PF={youtube:'YouTube',twitch:'Twitch',kick:'Kick'};
const LN=new Intl.DisplayNames(['en'],{type:'language'});const lang=l=>{if(!l||l==='unknown')return 'Unknown';try{return LN.of(l.split('-')[0])}catch(e){return l}};
const dd=s=>s?new Date(s+'T12:00:00').toLocaleDateString('en-IN',{day:'numeric',month:'short'}):'';
const av=x=>x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">`:'<span class="ph"></span>';
function draw(){const cv=document.getElementById('ch'),W=cv.clientWidth||900,H=220,dp=devicePixelRatio||1;cv.width=W*dp;cv.height=H*dp;const x=cv.getContext('2d');x.scale(dp,dp);
 const P=(D.series||[]).filter(p=>p[1]>0);x.clearRect(0,0,W,H);if(P.length<2){x.fillStyle='#8d8ca3';x.font='14px Barlow';x.fillText('No viewers recorded today yet.',8,24);return}
 const t0=P[0][0],t1=P[P.length-1][0],mx=Math.max(...P.map(p=>p[1]))*1.15,X=t=>8+(W-70)*(t-t0)/((t1-t0)||1),Y=v=>H-24-(H-40)*v/mx;
 x.strokeStyle='rgba(255,255,255,.06)';x.fillStyle='#8d8ca3';x.font='12px "Barlow Condensed"';for(let k=0;k<=3;k++){const v=mx*k/3,y=Y(v);x.beginPath();x.moveTo(8,y);x.lineTo(W-62,y);x.stroke();x.fillText(fmt(v),W-56,y+4)}
 const g=x.createLinearGradient(0,0,0,H);g.addColorStop(0,'rgba(182,242,58,.28)');g.addColorStop(1,'rgba(182,242,58,0)');x.beginPath();x.moveTo(X(t0),H-24);P.forEach(p=>x.lineTo(X(p[0]),Y(p[1])));x.lineTo(X(t1),H-24);x.fillStyle=g;x.fill();
 x.beginPath();P.forEach((p,i)=>i?x.lineTo(X(p[0]),Y(p[1])):x.moveTo(X(p[0]),Y(p[1])));x.strokeStyle='#b6f23a';x.lineWidth=2.5;x.stroke();
 const pk=P.reduce((a,p)=>p[1]>a[1]?p:a,P[0]);x.beginPath();x.arc(X(pk[0]),Y(pk[1]),5,0,7);x.fillStyle='#ff4d5e';x.fill();
 x.fillStyle='#8d8ca3';for(let k=0;k<4;k++){const t=t0+(t1-t0)*k/3;x.textAlign=k===0?'left':k===3?'right':'center';x.fillText(ist(t,{hour:'numeric',minute:'2-digit'}),Math.min(X(t),W-62),H-6)}x.textAlign='left'}
function render(){const d=D;document.title=d.name+' live viewers | letsgrowesports (beta)';
 if(d.art){const a=document.getElementById('art');a.src=d.art;a.hidden=false}
 document.getElementById('sub').innerHTML=[d.live_count?`<span class="lv">LIVE</span>${d.live_count} channel${d.live_count>1?'s':''} streaming now`:'',esc(d.game),d.start?dd(d.start)+(d.end&&d.end!==d.start?' to '+dd(d.end):''):'',d.liquipedia?`<a href="${esc(d.liquipedia)}" target="_blank" rel="noopener">Liquipedia</a>`:''].filter(Boolean).join(' · ');
 if(d.tracker){const t=document.getElementById('trk');t.href=d.tracker.url;t.textContent='OFFICIAL AND WATCH PARTY TRACKER: '+d.tracker.name.toUpperCase()+' >';t.hidden=false}
 document.getElementById('k1').textContent=d.peak?full(d.peak):'-';document.getElementById('k2').textContent=d.now?full(d.now):'0';
 document.getElementById('k3').textContent=d.peak_today?full(d.peak_today):'-';document.getElementById('k4').textContent=d.hw?fmt(d.hw):'-';document.getElementById('k5').textContent=(d.channels||[]).length||'-';
 document.getElementById('days').textContent=(d.days||[]).length>1?'Peak by day: '+d.days.slice(-14).map(x=>dd(x.day)+' '+fmt(x.peak)).join(' · '):(d.peak_at?'Peak '+full(d.peak)+' at '+ist(d.peak_at,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST':'');
 const L=d.live||[];document.getElementById('lvn').textContent=L.length?`${L.length} channels, ${full(d.now)} watching`:'';
 document.getElementById('lv').innerHTML=L.length?L.map(x=>`<tr><td class="l"><a class="c" href="${RP}/ch/${encodeURIComponent(x.sid)}">${av(x)}<span><b>${esc(x.name)}<span class="pf">${PF[x.platform]||''}</span></b><small>${esc(x.title)}</small></span></a></td><td class="hide mu">${esc(lang(x.language))}</td><td><b>${full(x.viewers)}</b></td></tr>`).join(''):'<tr><td class="l empty" colspan="3">Nobody is streaming it right now.</td></tr>';
 const C=d.channels||[];document.getElementById('chs').innerHTML=C.length?C.slice(0,100).map(x=>`<tr><td class="l"><a class="c" href="${RP}/ch/${encodeURIComponent(x.sid)}">${av(x)}<span><b>${esc(x.name)}<span class="pf">${PF[x.platform]||''}</span>${x.live?' <span class="lv">LIVE</span>':''}</b></span></a></td><td class="hide mu">${esc(lang(x.language))}</td><td class="hide">${fmt(x.hw)}</td><td class="hide">${x.days}</td><td><b>${full(x.peak)}</b></td></tr>`).join(''):'<tr><td class="l empty" colspan="5">No channel recorded yet.</td></tr>';
 const G=d.languages||[],tot=G.reduce((a,x)=>a+x.hw,0)||1;document.getElementById('lgc').style.display=G.length>1?'':'none';
 document.getElementById('lg').innerHTML=G.map(x=>`<div class="r"><span>${esc(lang(x.lang))}</span><i style="width:${Math.max(1,100*x.hw/tot)}%"></i><b>${Math.round(100*x.hw/tot)}%</b></div>`).join('');draw()}
render();addEventListener('resize',draw);
setInterval(async()=>{if(document.hidden)return;try{D=await (await fetch(`/api/tour?region=${REGION}&t=${SLUG}`)).json();render()}catch(e){}},15000);
// share card, tournament-card layout
function loadImg(u){return new Promise(r=>{if(!u)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
async function card(){const d=D,W=1080,H=1350,cv=document.createElement('canvas');cv.width=W*2;cv.height=H*2;const x=cv.getContext('2d');x.scale(2,2);
 const g=x.createRadialGradient(W*.8,0,40,W*.8,0,1200);g.addColorStop(0,'#1f1a3d');g.addColorStop(1,'#0b0b12');x.fillStyle=g;x.fillRect(0,0,W,H);
 x.fillStyle='rgba(255,255,255,.02)';for(let y=0;y<H;y+=4)x.fillRect(0,y,W,1);x.strokeStyle='#b6f23a';x.lineWidth=5;x.beginPath();x.moveTo(40,80);x.lineTo(40,40);x.lineTo(80,40);x.stroke();
 const T=(t,X,Y,f,c,al,mw)=>{x.font=f;if(mw){const w=x.measureText(t).width;if(w>mw){const m=f.match(/(\d+)px/);x.font=f.replace(/\d+px/,Math.max(10,Math.floor(+m[1]*mw/w))+'px')}}x.fillStyle=c;x.textAlign=al||'left';x.textBaseline='top';x.fillText(t,X,Y)};
 const M=s=>`${s}px "Barlow Condensed",sans-serif`,B=s=>`700 ${s}px "Barlow",sans-serif`;
 const SITE=(location.hostname.endsWith('letsgrowesports.com')?location.host:'live.letsgrowesports.com').replace(/^www\./,'')+RP;
 const dl=new Date().toLocaleDateString('en-GB',{weekday:'short',day:'2-digit',month:'short',timeZone:'Asia/Kolkata'}).replace(',','').toUpperCase();
 T('letsgrowesports',80,78,M(30),'#b6f23a');T(`${d.name.toUpperCase()} // ${dl}`,80,118,B(50),'#eeeef5','left',W-160);
 x.font=M(24);const wm='For more: '+SITE,ww=x.measureText(wm).width;T('// PEAK CONCURRENT VIEWERS',80,205,M(30),'#ff4d5e','left',W-160-ww-30);T(wm,W-80,210,M(24),'#a9a8be','right');
 x.shadowColor='rgba(182,242,58,.35)';x.shadowBlur=30;T(full(d.peak),72,245,B(170),'#ffffff');x.shadowBlur=0;
 const bw=(W-200)/3,box=(X,l,v,s,c)=>{x.fillStyle='rgba(26,26,38,.9)';x.fillRect(X,490,bw,170);x.strokeStyle='#262636';x.lineWidth=2;x.strokeRect(X,490,bw,170);T(l,X+22,510,M(24),'#ff4d5e','left',bw-44);T(v,X+22,544,B(56),c,'left',bw-44);T(s,X+22,616,M(22),'#8d8ca3','left',bw-44)};
 box(80,'WATCHING NOW',fmt(d.now),'all channels','#b6f23a');box(80+bw+20,'CHANNELS',String((d.channels||[]).length),'official + co-streams','#ff8a3d');box(80+2*(bw+20),'HOURS WATCHED',fmt(d.hw),'so far','#4cc9f0');
 const P=(d.series||[]).filter(p=>p[1]>0),X0=60,Y0=730,CW=W-250,CH=250;
 if(P.length>1){const t0=P[0][0],t1=P[P.length-1][0],mx=Math.max(...P.map(p=>p[1]))*1.2,X=t=>X0+CW*(t-t0)/((t1-t0)||1),Y=v=>Y0+CH-CH*v/mx;
  x.strokeStyle='rgba(255,255,255,.06)';x.lineWidth=1;for(let k=0;k<=4;k++){const v=mx*k/4,y=Y(v);x.beginPath();x.moveTo(X0,y);x.lineTo(X0+CW,y);x.stroke();T(k?fmt(v):'0',X0+CW+12,y-12,M(22),'#8d8ca3')}
  x.save();x.shadowColor='rgba(182,242,58,.8)';x.shadowBlur=18;x.beginPath();P.forEach((p,i)=>i?x.lineTo(X(p[0]),Y(p[1])):x.moveTo(X(p[0]),Y(p[1])));x.strokeStyle='#b6f23a';x.lineWidth=5;x.stroke();x.restore();
  const pk=P.reduce((a,p)=>p[1]>a[1]?p:a,P[0]);x.beginPath();x.arc(X(pk[0]),Y(pk[1]),11,0,7);x.fillStyle='#ff4d5e';x.fill();
  for(let k=0;k<5;k++){const t=t0+(t1-t0)*k/4;T(ist(t,{hour:'2-digit',minute:'2-digit',hour12:true}).toLowerCase(),X(t),Y0+CH+16,M(24),'#8d8ca3',k===0?'left':k===4?'right':'center')}}
 let ly=1035;T('// BIGGEST CHANNELS (PEAK)',80,ly,M(26),'#ff4d5e');ly+=42;(d.channels||[]).slice(0,3).forEach((c,k)=>{T(`${k+1}. ${String(c.name).toUpperCase()}`.slice(0,30),80,ly,B(34),k?'#eeeef5':'#b6f23a','left',W-420);T(full(c.peak),W-80,ly,B(34),k?'#eeeef5':'#b6f23a','right');ly+=46});
 x.fillStyle='#b6f23a';x.fillRect(0,H-130,W,130);T(('LIVE.LETSGROWESPORTS.COM'+RP).toUpperCase(),80,H-108,B(44),'#0a0a14','left',W-160);
 T(ist(Date.now()/1000,{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:true})+' IST // @letsgrowesports',80,H-52,M(24),'#0a0a14');
 return new Promise(r=>cv.toBlob(r,'image/png'))}
document.getElementById('shb').onclick=async()=>{try{await document.fonts.ready}catch(e){}BLOB=await card();document.getElementById('mimg').src=URL.createObjectURL(BLOB);document.getElementById('modal').style.display='flex'};
document.getElementById('mcl').onclick=()=>document.getElementById('modal').style.display='none';
document.getElementById('mdl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(BLOB);a.download=SLUG+'.png';a.click()};
document.getElementById('msh').onclick=async()=>{const f=new File([BLOB],SLUG+'.png',{type:'image/png'});if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:`${D.name}: peak ${full(D.peak)} watching across every channel. ${location.href} @letsgrowesports`});return}catch(e){}}document.getElementById('mdl').click()};
</script></body></html>"""


def build_html(name: str, region: str) -> str:
    d = scene.tour_data(name, region)
    rp = "/india" if region == "in" else "/global"
    sl = scene.slug(name)
    data = json.dumps(d, separators=(",", ":")).replace("</", "<\\/")
    return (PAGE.replace("__TITLE__", html.escape(name)).replace("__BRAND__", html.escape(eventpage.BRAND))
            .replace("__WHERE__", "in India" if region == "in" else "worldwide")
            .replace("__WHERECAP__", "INDIA" if region == "in" else "WORLDWIDE").replace("__HOME__", rp).replace("__RP__", rp)
            .replace("__SLUG__", sl).replace("__GON__", "" if region == "in" else "on").replace("__ION__", "on" if region == "in" else "")
            .replace("__REGIONJ__", json.dumps(region)).replace("__RPJ__", json.dumps(rp)).replace("__SLUGJ__", json.dumps(sl))
            .replace("__DATA__", data))
