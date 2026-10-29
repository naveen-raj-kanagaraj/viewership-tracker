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
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}.chips button{background:none;border:1px solid var(--line);color:var(--muted);font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.05em;padding:5px 10px;cursor:pointer}.chips button.on{background:var(--lime);color:#0b0b12;border-color:var(--lime)}
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
@media(max-width:700px){.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.nav{display:none}h1{font-size:28px}.hide{display:none}td,th{padding:8px 4px}.g b{max-width:130px}.card{padding:12px}.rk{display:none}.g img,.g .ph{width:24px;height:32px}.g{gap:7px}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span>
<span class="rg"><a href="/categories" class="__GON__">GLOBAL</a><a href="/india/categories" class="__ION__">INDIA</a></span>
<span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="__RP__/moments">MOMENTS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / CATEGORIES</div>
<h1>Top categories <em>__WHERE__</em></h1>
<p class="intro">Every game and category on YouTube, Twitch and Kick, by how many people are watching right now. Tap one for its page.</p>
<div class="card" id="trcard"><h2>Trending <small>biggest rise in watching against 24 hours ago</small></h2>
<table><thead><tr><th class="l">Category</th><th>24h change</th><th class="hide">Last 48 hours</th><th>Watching now</th></tr></thead><tbody id="tr"><tr><td class="l mu" colspan="4">Loading...</td></tr></tbody></table></div>
<div class="card"><h2>Top categories <small>by watching now</small></h2>
<div class="chips" id="chips"></div>
<table><thead><tr><th class="rk"></th><th class="l">Category</th><th>Watching now</th><th class="hide">Last 30 days</th><th>Peak, 30 days</th><th class="hide">Hours watched, 30 days</th></tr></thead><tbody id="tg"></tbody></table>
<button class="more" id="more" style="display:none"></button>
<div class="note" id="note"></div></div>
</div>
<script>
const RP=__RPJ__,REGION=__REGION__,SECN=__SECN__;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const PAL=[['#b6f23a','#5fb31f'],['#a58bff','#6b4fe0'],['#4cc9f0','#2a7fd4'],['#ffd23f','#f08c00'],['#ff8a9a','#e0405a'],['#53fc18','#1fae5b'],['#ff9f5a','#e0602a']];
const art=r=>{let h=0;for(const ch of r.game)h=(h*31+ch.charCodeAt(0))%PAL.length;const ph=`<span class="ph" style="background:linear-gradient(135deg,${PAL[h][0]},${PAL[h][1]})${r.art?';display:none':''}">${esc(r.game.replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase())}</span>`;
 return r.art?`<img src="${esc(r.art)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'">${ph}`:ph};
function spark(pts,w,h,bars,col){const c=document.createElement('canvas'),d=devicePixelRatio||1;c.width=w*d;c.height=h*d;c.style.width=w+'px';c.style.height=h+'px';const x=c.getContext('2d');x.scale(d,d);
 const vals=pts.filter(v=>v>0);if(!vals.length){x.fillStyle='#8d8ca3';x.font='11px Barlow';x.fillText('filling in',2,h/2+4);return c}
 const mx=Math.max(...vals),mn=bars?0:Math.min(...vals);
 if(bars){const bw=w/pts.length;pts.forEach((v,i)=>{if(!v)return;const bh=Math.max(1,(h-2)*v/mx);x.fillStyle=i===pts.length-1?'#b6f23a':'#5c8a2a';x.fillRect(i*bw+.5,h-bh,Math.max(1,bw-1.5),bh)});return c}
 let first=pts.findIndex(v=>v>0);x.strokeStyle=col;x.lineWidth=1.6;x.beginPath();let on=false;pts.forEach((v,i)=>{if(!v)return;const px=i/(pts.length-1)*w,py=h-2-(h-4)*(v-mn)/((mx-mn)||1);on?x.lineTo(px,py):(x.moveTo(px,py),on=true)});x.stroke();return c}
let J=null,SEC='',ALL=false;
const go=r=>{location.href=RP+'/c/'+r.slug};
function render(){const T=J.rows.filter(r=>J.trending.includes(r.game)&&r.game!=='Other').sort((a,b)=>b.change-a.change);
 const tr=document.getElementById('tr');tr.innerHTML='';document.getElementById('trcard').style.display=T.length?'':'none';
 T.forEach(r=>{const e=document.createElement('tr');e.className='rw';e.onclick=()=>go(r);e.innerHTML=`<td class="l"><div class="g">${art(r)}<b>${esc(r.game)}</b></div></td><td class="up">+${r.change.toLocaleString('en-IN')}%</td><td class="hide"></td><td>${full(r.viewers)}</td>`;e.children[2].appendChild(spark(r.h48,170,30,false,'#b6f23a'));tr.appendChild(e)});
 const secs=[...new Set(J.rows.map(r=>r.section).filter(Boolean))];
 document.getElementById('chips').innerHTML=[['','ALL']].concat(secs.map(s=>[s,(SECN[s]||s).toUpperCase()])).map(([v,l])=>`<button data-v="${v}" class="${v===SEC?'on':''}">${esc(l)}</button>`).join('');
 const L=J.rows.filter(r=>!SEC||r.section===SEC),show=ALL?L:L.slice(0,25),tg=document.getElementById('tg');tg.innerHTML='';
 show.forEach((r,i)=>{const e=document.createElement('tr');e.className='rw';e.onclick=()=>go(r);
  const ch=r.change==null?'':`<div class="${r.change>=0?'up':'dn'}" style="font-size:12px">${r.change>=0?'+':''}${r.change}% 24h</div>`;
  e.innerHTML=`<td class="rk">${i+1}.</td><td class="l"><div class="g">${art(r)}<span style="min-width:0"><b>${esc(r.game)}</b><span class="mu" style="font-size:12px">${full(r.streams)} live</span></span></div></td><td>${full(r.viewers)}${ch}</td><td class="hide"></td><td class="mu">${full(r.peak30)}</td><td class="mu hide">${full(r.hw30)}h</td>`;
  e.children[3].appendChild(spark(r.d30,190,34,true));tg.appendChild(e)});
 if(!show.length)tg.innerHTML='<tr><td class="l mu" colspan="6">Nothing live here right now.</td></tr>';
 const mo=document.getElementById('more');mo.style.display=L.length>25?'block':'none';mo.textContent=ALL?'Show top 25':`Show all ${L.length}`;
 const days=Math.max(1,Math.round((Date.now()/1000-J.since)/86400));
 document.getElementById('note').textContent=`Watching now = everyone watching live streams in that category right now (each platform's own count). Change = against the same time yesterday. 30-day bars = the most watching at once each day (IST); the last bar is today. ${days<30?`This site has been recording for ${days} day${days>1?'s':''}, so the 30-day columns are still filling in.`:''}`}
async function load(){try{J=await (await fetch('/api/cats?region='+REGION)).json();render()}catch(e){setTimeout(load,5000)}}
document.getElementById('chips').onclick=e=>{const b=e.target.closest('button');if(b){SEC=b.dataset.v;ALL=false;render()}};
document.getElementById('more').onclick=()=>{ALL=!ALL;render()};
load();setInterval(()=>{if(!document.hidden)load()},60000);
</script></body></html>"""


def build_html(region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    rp = "/india" if region == "in" else ""
    return (PAGE.replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__RPJ__", json.dumps(rp))
            .replace("__REGION__", json.dumps(region)).replace("__SECN__", json.dumps(scene.SECTION_NAMES))
            .replace("__HOME__", rp or "/").replace("__RP__", rp)
            .replace("__WHERECAP__", "INDIA" if region == "in" else "WORLDWIDE")
            .replace("__WHERE__", "in India" if region == "in" else "worldwide")
            .replace("__GON__", "" if region == "in" else "on").replace("__ION__", "on" if region == "in" else ""))
