"""/categories (and /india/categories): every game and category, the way player-count charts show games:
watching now, change against 24 hours earlier, the last 48 hours, daily peaks for 30 days, 30-day peak and hours
watched; trending first. Data: /api/cats."""
import html
import json

from tracker import eventpage, scene

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Top categories __WHERE__ | __BRAND__ (beta)</title>
<meta name="description" content="Every game and category on YouTube, Twitch and Kick by viewers right now: trending, 24-hour change, 30-day peak and hours watched.">
<meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;--lime:#b6f23a;--purple:#a58bff;--red:#ff4d5e}
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
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:6px 0 4px;text-transform:uppercase}h1 em{font-style:normal;color:var(--purple)}
.intro{color:var(--muted);margin:0}
.card{background:var(--card);border:1px solid var(--line);margin-top:14px;padding:14px 16px}
h2{font:700 24px "Barlow Condensed",sans-serif;margin:0 0 8px;text-transform:uppercase;letter-spacing:.02em}h2 small{color:var(--muted);font:500 14px "Barlow",sans-serif;text-transform:none;margin-left:6px;letter-spacing:0}
#cq{width:100%;max-width:420px;background:#0e0e16;border:1px solid var(--line);color:var(--text,#fff);font:15px Barlow,sans-serif;padding:9px 12px;margin:2px 0 10px;outline:none}#cq:focus{border-color:#b6f23a}.chips{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}.chips .g6{display:inline-flex;align-items:center;background:#ff2d78;color:#fff;font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.06em;padding:7px 12px;text-decoration:none;border-radius:2px}.chips button{background:none;border:1px solid var(--line);color:var(--muted);font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.05em;padding:5px 10px;cursor:pointer}.chips button.on{background:var(--lime);color:#0b0b12;border-color:var(--lime)}
table{width:100%;border-collapse:collapse}th{font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;text-align:right;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:8px;border-bottom:1px solid #1c1c29;text-align:right;white-space:nowrap}th.l,td.l{text-align:left}
tr.rw{cursor:pointer}tr.rw:hover td{background:#171722}
.g{display:flex;align-items:center;gap:10px;min-width:0}.g b{font-weight:600;overflow:hidden;text-overflow:ellipsis;max-width:260px;display:block}
.g img,.g .ph{width:30px;height:40px;border-radius:3px;flex:none;object-fit:cover;background:var(--card2)}
.g .ph{display:grid;place-items:center;font:700 11px "Barlow Condensed",sans-serif;color:#0b0b12}
.up{color:var(--lime)}.dn{color:var(--red)}.mu{color:var(--muted)}.rk{color:var(--muted);width:28px;text-align:left}
canvas{display:block}.empty{color:var(--muted);padding:14px 0}
.more{display:block;width:100%;background:var(--card2);border:0;border-top:1px solid var(--line);color:var(--ink);font:13px "Barlow",sans-serif;padding:11px;cursor:pointer;margin-top:8px}
.note{color:var(--muted);font-size:12px;margin-top:10px}
canvas.mob{display:none}@media(max-width:700px){canvas.mob{display:block;margin-top:4px}.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.nav{display:none}h1{font-size:28px}.hide{display:none}td,th{padding:8px 4px}.g b{max-width:130px}.card{padding:12px}.rk{display:none}.g img,.g .ph{width:24px;height:32px}.g{gap:7px}}
.shb{float:right;background:var(--lime);color:#0b0b12;border:0;font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.06em;padding:6px 12px;cursor:pointer;margin-top:2px}
.modal{position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.82);display:none;align-items:center;justify-content:center;padding:16px}
.modal .bx{background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto}
.modal img{width:100%;max-height:68vh;object-fit:contain;display:block;border:1px solid var(--line);margin:8px 0 10px}
.mb{display:flex;gap:8px;flex-wrap:wrap}.mb button,.fm button{flex:1;background:var(--card2);border:1px solid var(--line);color:var(--ink);font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.06em;padding:9px;cursor:pointer}
.mb button.p{background:var(--lime);color:#0b0b12;border-color:var(--lime)}.fm{display:flex;gap:6px}.fm button.on{background:var(--lime);color:#0b0b12}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span>
<span class="rg"><a href="/global/categories" class="__GON__">GLOBAL</a><a href="/india/categories" class="__ION__">INDIA</a></span>
<span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="__RP__/moments">MOMENTS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / CATEGORIES</div>
<h1>Top categories <em>__WHERE__</em></h1>
<p class="intro">Every game and category on YouTube, Twitch and Kick, by how many people are watching right now. Tap one for its page.</p>
<div class="card" id="trcard"><button class="shb" data-k="tr">SHARE</button><h2>Trending <small>biggest rise in watching against 24 hours ago</small></h2>
<table><thead><tr><th class="l">Category</th><th>24h change</th><th class="hide">Last 48 hours</th><th>Watching now</th></tr></thead><tbody id="tr"><tr><td class="l mu" colspan="4">Loading...</td></tr></tbody></table></div>
<div class="card"><button class="shb" data-k="top">SHARE</button><h2>Top categories <small>by watching now</small></h2>
<div class="chips" id="rng"></div><input id="cq" type="search" placeholder="Search categories: Valorant, BGMI, Just Chatting..." autocomplete="off"><div class="chips" id="chips"></div>
<table><thead><tr><th class="rk"></th><th class="l">Category</th><th>Watching now</th><th class="hide" id="hb">Last 24 hours</th><th id="hp">Peak, 24 hours</th><th class="hide" id="hh">Hours watched, 24 hours</th></tr></thead><tbody id="tg"></tbody></table>
<button class="more" id="more" style="display:none"></button>
<div class="note" id="note"></div></div>
</div>
<div class="modal" id="modal"><div class="bx"><div class="fm" id="mfmt"><button data-f="post" class="on">POST 4:5</button><button data-f="story">STORY 9:16</button></div>
<img id="mimg" alt="Share card"><div class="mb"><button class="p" id="mshare">SHARE</button><button id="mdl">DOWNLOAD</button><button id="mclose">CLOSE</button></div></div></div>
<script>const G6=__G6__;
const RP=__RPJ__,REGION=__REGION__,SECN=__SECN__;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const PAL=[['#b6f23a','#5fb31f'],['#a58bff','#6b4fe0'],['#4cc9f0','#2a7fd4'],['#ffd23f','#f08c00'],['#ff8a9a','#e0405a'],['#53fc18','#1fae5b'],['#ff9f5a','#e0602a']];
const art=r=>{let h=0;for(const ch of r.game)h=(h*31+ch.charCodeAt(0))%PAL.length;const ph=`<span class="ph" style="background:linear-gradient(135deg,${PAL[h][0]},${PAL[h][1]})${r.art?';display:none':''}">${esc(r.game.replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase())}</span>`;
 return r.art?`<img src="${esc(r.art)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'">${ph}`:ph};
function spark(pts,w,h,bars,col,now){col=col||'#b6f23a';const c=document.createElement('canvas'),d=devicePixelRatio||1;c.width=w*d;c.height=h*d;c.style.width=w+'px';c.style.height=h+'px';const x=c.getContext('2d');x.scale(d,d);
 let vals=pts.filter(v=>v>0);if(!vals.length&&now>0){pts=[now];vals=[now]}if(!vals.length)return c;
 if(vals.length===1&&!bars){x.strokeStyle=col;x.globalAlpha=.35;x.lineWidth=1.6;x.beginPath();x.moveTo(0,h/2);x.lineTo(w-4,h/2);x.stroke();x.globalAlpha=1;x.fillStyle=col;x.beginPath();x.arc(w-4,h/2,3,0,7);x.fill();return c}
 const mx=Math.max(...vals),mn=bars?0:Math.min(...vals);
 if(bars){const bw=w/pts.length;pts.forEach((v,i)=>{if(!v)return;const bh=Math.max(1,(h-2)*v/mx);x.fillStyle=i===pts.length-1?'#b6f23a':'#5c8a2a';x.fillRect(i*bw+.5,h-bh,Math.max(1,bw-1.5),bh)});return c}
 let first=pts.findIndex(v=>v>0);x.strokeStyle=col;x.lineWidth=1.6;x.beginPath();let on=false;pts.forEach((v,i)=>{if(!v)return;const px=i/(pts.length-1)*w,py=h-2-(h-4)*(v-mn)/((mx-mn)||1);on?x.lineTo(px,py):(x.moveTo(px,py),on=true)});x.stroke();return c}
let J=null,SEC='',ALL=false,RNG='24h';
const RN=[['24h','24H','24 hours'],['7d','7D','7 days'],['1m','1M','30 days'],['3m','3M','3 months'],['6m','6M','6 months'],['ytd','YTD','this year'],['1y','1Y','12 months'],['all','ALL TIME','all time']];
const go=r=>{location.href=RP+'/c/'+r.slug};
function render(){const T=J.rows.filter(r=>J.trending.includes(r.game)&&r.game!=='Other').sort((a,b)=>b.change-a.change);
 const tr=document.getElementById('tr');tr.innerHTML='';document.getElementById('trcard').style.display=T.length?'':'none';
 T.forEach(r=>{const e=document.createElement('tr');e.className='rw';e.onclick=()=>go(r);e.innerHTML=`<td class="l"><div class="g">${art(r)}<b>${esc(r.game)}</b></div></td><td class="up">+${r.change.toLocaleString('en-IN')}%</td><td class="hide"></td><td>${full(r.viewers)}</td>`;e.children[2].appendChild(spark(r.h48,170,30,false,'#b6f23a',r.viewers));{const mb=spark(r.h48,110,18,false,'#b6f23a',r.viewers);mb.classList.add('mob');e.querySelector('.g').appendChild(mb)}tr.appendChild(e)});
 const secs=[...new Set(J.rows.map(r=>r.section).filter(Boolean))];
 document.getElementById('chips').innerHTML=(G6?`<a class="g6" href="${RP}/c/gta-6">GTA 6</a>`:'')+[['','ALL']].concat(secs.map(s=>[s,(SECN[s]||s).toUpperCase()])).map(([v,l])=>`<button data-v="${v}" class="${v===SEC?'on':''}">${esc(l)}</button>`).join('');
 const QQ=document.getElementById('cq').value.trim().toLowerCase(),L=J.rows.filter(r=>(!SEC||r.section===SEC)&&(!QQ||r.game.toLowerCase().includes(QQ))),show=ALL||QQ?L:L.slice(0,25),tg=document.getElementById('tg');tg.innerHTML='';
 show.forEach((r,i0)=>{const i=J.rows.indexOf(r);const e=document.createElement('tr');e.className='rw';e.onclick=()=>go(r);
  const ch=r.change==null?'':`<div class="${r.change>=0?'up':'dn'}" style="font-size:12px">${r.change>=0?'+':''}${r.change}% 24h</div>`;
  e.innerHTML=`<td class="rk">${r.pinned?'<span style="font:700 11px Barlow Condensed;background:#b6f23a;color:#0a0a14;padding:2px 5px">NEW</span>':(i+1-J.rows.filter(x=>x.pinned).length)+'.'}</td><td class="l"><div class="g">${art(r)}<span style="min-width:0"><b>${esc(r.game)}</b><span class="mu" style="font-size:12px">${full(r.streams)} live</span></span></div></td><td>${full(r.viewers)}${ch}</td><td class="hide"></td><td class="mu">${full(r.peak30)}</td><td class="mu hide">${full(r.hw30)}h</td>`;
  const mk=(w,h)=>r.d30.some(v=>v>0)?spark(r.d30,w,h,true):spark(r.h48,w,h,false,'#b6f23a',r.viewers);e.children[3].appendChild(mk(190,34));const mb=mk(110,18);mb.classList.add('mob');e.querySelector('.g>span:last-child').appendChild(mb);e.children[5].textContent=full(r.hw30)+'h';e.children[4].textContent=full(r.peak30);tg.appendChild(e)});
 if(!show.length)tg.innerHTML=`<tr><td class="l mu" colspan="6">${QQ?'No category matching "'+esc(QQ)+'" is live right now.':'Nothing live here right now.'}</td></tr>`;
 const mo=document.getElementById('more');mo.style.display=L.length>25&&!QQ?'block':'none';mo.textContent=ALL?'Show top 25':`Show all ${L.length}`;
 const hist=(Date.now()/1000-J.since)/86400,jan=(Date.now()-new Date(new Date().getFullYear(),0,1))/864e5;
 // a range appears only once the site has recorded that much history (no duplicate numbers under a longer label)
 const NEED={'24h':0,'7d':0,'1m':0,'3m':85,'6m':175,'ytd':jan-2,'1y':355,'all':32},RV=RN.filter(x=>hist>=NEED[x[0]]||x[0]===RNG);
 const rl=(RN.find(x=>x[0]===RNG)||RN[0])[2];document.getElementById('rng').innerHTML=RV.map(([v,l])=>`<button data-v="${v}" class="${v===RNG?'on':''}">${l}</button>`).join('')+
  (RV.length<RN.length?`<span class="mu" style="font-size:12px;align-self:center;margin-left:4px">Longer ranges appear here as we keep recording. Check back soon.</span>`:'');
 document.getElementById('hb').textContent=J.bar_days===0?`${rl}, hourly bars`:J.bar_days>1?`${rl}, ${J.bar_days}-day bars`:rl;document.getElementById('hp').textContent='Peak, '+rl;document.getElementById('hh').textContent='Hours watched, '+rl;
 const days=Math.max(1,Math.round((Date.now()/1000-J.since)/86400));
 document.getElementById('note').textContent=`Watching now = everyone watching live streams in that category right now (each platform's own count). Change = against the same time yesterday. Bars = the most watching at once in each ${J.bar_days===0?'hour':J.bar_days>1?J.bar_days+'-day stretch':'day'}${J.bar_days===0?'':' (IST)'}; the last bar is the latest. ${days<365?`We started recording ${days} day${days>1?'s':''} ago and add a reading every 2 minutes, so 3-month, 6-month and 1-year views unlock as the history builds up.`:''}`}
async function load(){try{const r=await fetch('/api/cats?region='+REGION+'&range='+RNG);if(!r.ok)throw 0;J=await r.json();render()}catch(e){setTimeout(load,5000)}}
document.getElementById('rng').onclick=e=>{const b=e.target.closest('button');if(b){RNG=b.dataset.v;load()}};
document.getElementById('chips').onclick=e=>{const b=e.target.closest('button');if(b){SEC=b.dataset.v;ALL=false;render()}};
document.getElementById('cq').oninput=()=>{if(J)render()};
document.getElementById('more').onclick=()=>{ALL=!ALL;render()};

// share cards: the same table as the page (art, watching now, change, bars / 48-hour line), site address on the subtitle line
let BLOB=null,KIND='top',FMT='post';
function loadImg(u){return new Promise(r=>{if(!u)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
const ICON=s=>'/caticon/'+(s||'other')+'.svg';
async function makeCard(){const ST=FMT==='story',W=1080,H=ST?1920:1350,c=document.createElement('canvas');c.width=W*2;c.height=H*2;const x=c.getContext('2d');x.scale(2,2);
 x.fillStyle='#0b0b12';x.fillRect(0,0,W,H);const g=x.createRadialGradient(860,-60,10,860,-60,760);g.addColorStop(0,'rgba(124,92,255,.24)');g.addColorStop(1,'rgba(124,92,255,0)');x.fillStyle=g;x.fillRect(0,0,W,H);
 const T0=KIND==='tr',QQ=document.getElementById('cq').value.trim().toLowerCase();
 const L=(T0?J.rows.filter(r=>r.game!=='Other'&&r.change!=null&&(J.trending.includes(r.game)||r.change>0)).sort((a,b)=>(J.trending.includes(b.game)-J.trending.includes(a.game))||b.change-a.change):J.rows.filter(r=>(!SEC||r.section===SEC)&&(!QQ||r.game.toLowerCase().includes(QQ)))).slice(0,10);
 const top=ST?260:0,fit=(t,w)=>{t=String(t||'');while(x.measureText(t).width>w&&t.length>2)t=t.slice(0,-1);return t};
 const rl=(RN.find(r=>r[0]===RNG)||RN[0])[2];
 x.textBaseline='alphabetic';x.fillStyle='#b6f23a';x.font='700 30px "Barlow Condensed",sans-serif';x.fillText('LETSGROWESPORTS',72,top+86);
 x.fillStyle='#eeeef5';x.font='700 72px "Barlow Condensed",sans-serif';x.fillText(T0?'TRENDING CATEGORIES':'TOP CATEGORIES',72,top+160);
 const WM='For more: '+(location.hostname.endsWith('letsgrowesports.com')?location.host:'live.letsgrowesports.com').replace(/^www\./,'')+RP;x.font='600 22px "Barlow Condensed",sans-serif';const wmW=x.measureText(WM).width;
 x.textAlign='right';x.fillStyle='#a9a8be';x.fillText(WM,W-72,top+204);x.textAlign='left';
 const sub=[REGION==='in'?'INDIA':'WORLDWIDE',SEC?(SECN[SEC]||SEC).toUpperCase():'',T0?'RISE VS 24 HOURS AGO':'WATCHING NOW'].filter(Boolean).join(' · ');
 x.fillStyle='#b6f23a';x.font='600 32px "Barlow Condensed",sans-serif';x.fillText(fit(sub,W-144-wmW-24),72,top+204);
 x.fillStyle='#262636';x.fillRect(72,top+226,W-144,2);
 x.fillStyle='#8d8ca3';x.font='600 20px "Barlow Condensed",sans-serif';x.fillText('CATEGORY',72,top+262);x.fillText(T0?'LAST 48 HOURS':document.getElementById('hb').textContent.toUpperCase(),560,top+262);x.textAlign='right';x.fillText('WATCHING NOW',W-72,top+262);x.textAlign='left';
 const yA=top+282,avail=(ST?1600:H-80)-yA,rh=Math.min(L.length<10?120:96,avail/Math.max(1,L.length)),y0=yA;
 const imgs=await Promise.all(L.map(async r=>await loadImg(r.art)||await loadImg(ICON(r.section))));
 L.forEach((r,i)=>{const y=y0+i*rh,cy=y+rh/2;if(i%2===0){x.fillStyle='rgba(255,255,255,.025)';x.fillRect(64,y+2,W-128,rh-4)}
  x.fillStyle=i<3?'#b6f23a':'#8d8ca3';x.font='700 30px "Barlow Condensed",sans-serif';x.textAlign='right';x.fillText(i+1,108,cy+10);x.textAlign='left';
  const ah=Math.min(rh-22,110),aw=ah*.75,ax=124,ay=cy-ah/2;x.save();x.beginPath();x.roundRect?x.roundRect(ax,ay,aw,ah,5):x.rect(ax,ay,aw,ah);x.clip();x.fillStyle='#1a1a26';x.fillRect(ax,ay,aw,ah);if(imgs[i]){const im=imgs[i],s=Math.max(aw/im.width,ah/im.height);x.drawImage(im,ax+(aw-im.width*s)/2,ay+(ah-im.height*s)/2,im.width*s,im.height*s)}x.restore();
  const tx=ax+aw+18;x.fillStyle='#eeeef5';x.font='600 32px "Barlow",sans-serif';x.fillText(fit(r.game,560-tx-24),tx,cy-2);
  x.fillStyle='#8d8ca3';x.font='500 21px "Barlow",sans-serif';x.fillText(fit(full(r.streams)+' live',560-tx-24),tx,cy+28);
  {const bars=!T0&&r.d30.some(v=>v>0),pts=bars?r.d30:r.h48,X=560,w=240,h=rh*.56,Y=cy-h/2,vals=pts.filter(v=>v>0);
   if(vals.length){const mx=Math.max(...vals),mn=bars?0:Math.min(...vals);
    if(bars){const bw=w/pts.length;pts.forEach((v,k)=>{if(!v)return;const bh=Math.max(2,h*v/mx);x.fillStyle=k===pts.length-1?'#b6f23a':'#5c8a2a';x.fillRect(X+k*bw+.5,Y+h-bh,Math.max(1.5,bw-2),bh)})}
    else{x.strokeStyle='#b6f23a';x.lineWidth=3;x.lineJoin='round';x.beginPath();let on=false;pts.forEach((v,k)=>{if(!v)return;const px=X+k/Math.max(1,pts.length-1)*w,py=Y+h-(h-4)*(v-mn)/((mx-mn)||1)-2;on?x.lineTo(px,py):(x.moveTo(px,py),on=true)});x.stroke()}}}
  x.textAlign='right';x.fillStyle='#eeeef5';x.font='700 36px "Barlow Condensed",sans-serif';x.fillText(full(r.viewers),W-72,cy+4);
  if(r.change!=null){x.fillStyle=r.change>=0?'#b6f23a':'#ff4d5e';x.font='600 21px "Barlow Condensed",sans-serif';x.fillText((r.change>=0?'+':'')+r.change.toLocaleString('en-IN')+'% in 24h',W-72,cy+30)}x.textAlign='left'});
 x.fillStyle='#8d8ca3';x.font='24px "Barlow Condensed",sans-serif';x.fillText(((location.hostname.endsWith('letsgrowesports.com')?location.host:'live.letsgrowesports.com')+location.pathname).replace(/^www\./,'')+'  ·  '+new Date().toLocaleString('en-IN',{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'}),72,H-(ST?200:34));
 return new Promise(r=>c.toBlob(r,'image/png'))}
async function openCard(){try{await document.fonts.ready}catch(e){}BLOB=await makeCard();document.getElementById('mimg').src=URL.createObjectURL(BLOB);document.getElementById('modal').style.display='flex'}
document.querySelectorAll('.shb').forEach(b=>b.onclick=()=>{if(!J)return;KIND=b.dataset.k;openCard()});
document.getElementById('mfmt').onclick=e=>{const b=e.target.closest('button');if(!b)return;FMT=b.dataset.f;document.querySelectorAll('#mfmt button').forEach(z=>z.classList.toggle('on',z===b));openCard()};
document.getElementById('mclose').onclick=()=>document.getElementById('modal').style.display='none';
document.getElementById('mdl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(BLOB);a.download='categories.png';a.click()};
document.getElementById('mshare').onclick=async()=>{const f=new File([BLOB],'categories.png',{type:'image/png'}),t=(KIND==='tr'?'Trending categories':'Top categories')+(REGION==='in'?' in India':'')+' right now '+location.href+' @letsgrowesports';
 if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){}}document.getElementById('mdl').click()};
load();setInterval(()=>{if(!document.hidden)load()},60000);
</script></body></html>"""


def build_html(region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    rp = "/india" if region == "in" else "/global"
    return (PAGE.replace("__G6__", "true" if __import__("tracker").scene.GTA6_SHOW else "false").replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__RPJ__", json.dumps(rp))
            .replace("__REGION__", json.dumps(region)).replace("__SECN__", json.dumps(scene.SECTION_NAMES))
            .replace("__HOME__", rp).replace("__RP__", rp)
            .replace("__WHERECAP__", "INDIA" if region == "in" else "WORLDWIDE")
            .replace("__WHERE__", "in India" if region == "in" else "worldwide")
            .replace("__GON__", "" if region == "in" else "on").replace("__ION__", "on" if region == "in" else ""))
