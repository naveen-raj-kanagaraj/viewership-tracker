"""/moments and /india/moments: the biggest sudden jumps in live viewers, each with a player starting at that second
(YouTube embed at the time, a Twitch clip, or the Twitch replay at the time). Data: /api/moments (moments.recent)."""
import html
import json

from tracker import eventpage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Moments __WHERE__ | __BRAND__ (beta)</title>
<meta name="description" content="The biggest sudden jumps in live viewers __WHERE__ on YouTube, Kick and Twitch, with the moment it happened.">
<meta property="og:title" content="Moments __WHERE__ | __BRAND__"><meta name="theme-color" content="#07051a">
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
.rg{display:inline-flex;border:1px solid var(--line);font:12px "Barlow Condensed",sans-serif;letter-spacing:.04em}.rg a{padding:4px 10px;text-decoration:none;color:var(--muted)}.rg a.on{background:var(--lime);color:#0b0b12}
.nav{margin-left:auto;display:flex;gap:12px;font:13px "Barlow Condensed",sans-serif;letter-spacing:.04em}.nav a{text-decoration:none;color:var(--muted)}.nav a:hover{color:var(--lime)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px 28px}
.crumb{font:12px "Barlow Condensed",sans-serif;color:var(--muted);margin-top:18px;letter-spacing:.04em}.crumb a{text-decoration:none}
h1{font:700 38px/1.05 "Barlow Condensed",sans-serif;margin:6px 0 4px;text-transform:uppercase}h1 em{font-style:normal;color:var(--purple)}
.intro{color:var(--muted);margin:0;max-width:760px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.seg{display:inline-flex;flex-wrap:wrap;border:1px solid var(--line);background:var(--card)}.seg button{background:none;border:0;color:var(--muted);font:600 13px "Barlow Condensed",sans-serif;letter-spacing:.04em;padding:7px 11px;cursor:pointer}.seg button.on{background:var(--lime);color:#0b0b12}
select{background:var(--card);border:1px solid var(--line);color:var(--ink);font:500 14px "Barlow",sans-serif;padding:6px 9px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;margin-top:14px}
.m{background:var(--card);border:1px solid var(--line);display:flex;flex-direction:column;transition:border-color .2s,transform .2s}
.m:hover{border-color:#3a2f6b;transform:translateY(-2px)}
.th{position:relative;aspect-ratio:16/9;background:#0f0d22;cursor:pointer;overflow:hidden}
.th img.bg{width:100%;height:100%;object-fit:cover;display:block;opacity:.85}
.th .av{position:absolute;inset:0;display:grid;place-items:center}.th .av img,.th .av span{width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--line);background:var(--card2);display:grid;place-items:center;font:700 22px "Barlow",sans-serif;color:var(--muted)}
.th .jmp{position:absolute;left:10px;bottom:10px;z-index:1;background:rgba(11,11,18,.85);padding:4px 9px;font:700 22px "Barlow Condensed",sans-serif;color:var(--lime)}
.th .jmp small{font:500 12px "Barlow Condensed",sans-serif;color:var(--muted);margin-left:6px}
.th .pl{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:44px;height:44px;border-radius:50%;background:rgba(182,242,58,.92);display:grid;place-items:center}
.th .pl:after{content:"";border-left:14px solid #0b0b12;border-top:9px solid transparent;border-bottom:9px solid transparent;margin-left:4px}
.th .tag{position:absolute;left:10px;top:10px;font:700 11px "Barlow Condensed",sans-serif;letter-spacing:.05em;padding:3px 7px;color:#0b0b12}
.th iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.bd{padding:10px 12px 12px;display:flex;flex-direction:column;gap:3px}
.bd .n{font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bd .n a{text-decoration:none}.bd .n a:hover{color:var(--lime)}
.bd .t{font-size:13px;color:#c9c8d8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bd .s{font-size:12px;color:var(--muted)}
.bd .s a{color:var(--lime);text-decoration:none}
.empty{color:var(--muted);padding:24px 0}
.note{color:var(--muted);font-size:12px;margin-top:16px;line-height:1.6}
.chips{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;margin-top:10px;padding-bottom:2px}.chips::-webkit-scrollbar{display:none}
.chips button{flex:none;background:var(--card2);border:0;color:var(--ink);font:600 14px "Barlow",sans-serif;padding:7px 13px;border-radius:8px;cursor:pointer;white-space:nowrap}.chips button.on{background:var(--ink);color:#0b0b12}
.th .dur{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.82);color:#fff;font:700 13px "Barlow",sans-serif;padding:2px 6px;border-radius:4px}
.row{display:flex;gap:10px;padding:10px 12px 14px}.row a{text-decoration:none}.row .ava{flex:none;width:36px;height:36px;border-radius:50%;object-fit:cover;background:var(--card2);display:grid;place-items:center;font:700 13px "Barlow";color:var(--muted);overflow:hidden}
.row .tx{min-width:0;flex:1}.row .tt{font-weight:600;font-size:15px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.row .mt{font-size:13px;color:var(--muted);margin-top:3px;line-height:1.35}.row .mt b{color:var(--lime);font-weight:600}.row .mt a{color:var(--muted);text-decoration:none}
@media(max-width:640px){.wrap{padding:0 0 20px}.crumb,h1,.intro,.filters,.chips,.note{padding-left:12px;padding-right:12px}.top .in{padding:9px 12px;gap:10px}.brand{font-size:15px}.nav{display:none}h1{font-size:28px}
 .grid{grid-template-columns:1fr;gap:6px}.m{border:0;background:none}.m:hover{transform:none}.th .jmp{font-size:16px;left:8px;bottom:8px;padding:2px 7px;border-radius:4px}.th .jmp small{display:none}.th .pl{display:none}.th .tag{top:8px;left:8px;border-radius:4px}.filters{margin-top:10px}.filters .seg{display:none}}
@media(min-width:641px){.chips .mob{display:none}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="rg"><a href="/moments" class="__GON__">GLOBAL</a><a href="/india/moments" class="__ION__">INDIA</a></span><span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / MOMENTS</div>
<h1>Moments <em>__WHERE__</em></h1>
<p class="intro">When a live stream suddenly jumps in viewers, something happened. Tap one to watch from just before the jump.</p>
<div class="filters"><div class="seg" id="per"></div><div class="seg" id="sort"></div><select id="game"><option value="">All games & categories</option></select></div>
<div class="chips" id="chips"></div>
<div class="grid" id="grid"></div>
<div class="note" id="note"></div>
</div>
<script>
const REGION=__REGION__,RP=REGION==='in'?'/india':'',HOST=location.hostname;
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e9?(n/1e9).toFixed(2)+'B':n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const ago=ts=>{const s=Date.now()/1000-ts;return s<120?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const ist=ts=>new Date(ts*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST';
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const hms=s=>`${Math.floor(s/3600)}h${Math.floor(s%3600/60)}m${s%60}s`;
const Q=new URLSearchParams(location.search);let FOCUS=Q.get('id')||'';let per=['today','7d','30d'].includes(Q.get('period'))?Q.get('period'):'7d',game=Q.get('game')||'',M=[];
function player(m){if(m.embed==='yt'&&(m.live_now||!m.embed_t))return '';if(m.embed==='tw_vod'&&!m.embed_t)return '';if(m.embed==='yt')return `https://www.youtube.com/embed/${encodeURIComponent(m.embed_id)}?start=${m.embed_t||0}&autoplay=1`;
 if(m.embed==='tw_clip')return `https://clips.twitch.tv/embed?clip=${encodeURIComponent(m.embed_id)}&parent=${HOST}&autoplay=true`;
 if(m.embed==='tw_vod')return `https://player.twitch.tv/?video=${encodeURIComponent(m.embed_id)}&time=${hms(m.embed_t||0)}&parent=${HOST}&autoplay=true`;return ''}
const thumb=m=>m.thumb||(m.platform==='youtube'&&(m.embed_id||m.vid)&&!/:/.test(m.embed_id||m.vid)?`https://i.ytimg.com/vi/${encodeURIComponent(m.embed_id||m.vid)}/hqdefault.jpg`:'');
function card(m,i){m.thumb=thumb(m);const p=player(m),tag=m.embed==='tw_clip'?['CLIP','#a970ff']:p?['PLAYS AT THE MOMENT','#b6f23a']:m.live_now?['STILL LIVE: REPLAY WHEN IT ENDS','#ff4d5e']:['OPENS THE STREAM','#8d8ca3'];
 return `<div class="m"><div class="th" data-i="${i}">${m.thumb?`<img class="bg" src="${esc(m.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`:`<div class="av">${m.logo?`<img src="${esc(m.logo)}" alt="" referrerpolicy="no-referrer">`:`<span>${ini(m.name)}</span>`}</div>`}
  <span class="tag" style="background:${tag[1]}">${tag[0]}</span><span class="jmp">${m.kind==='chat'||m.kind==='both'?`${m.chat_base?Math.max(2,Math.round(m.chat_peak/Math.max(m.chat_base,.1))):''}x chat`:'+'+fmt(m.jump)}<small>${m.kind==='both'?'+'+fmt(m.jump)+' viewers · ':m.kind==='chat'?'':`in ${m.secs<120?m.secs+'s':Math.round(m.secs/60)+' min'} · ${m.pct}% · `}hype ${Math.round(m.score||0)}</small></span>${p||m.link?'<span class="pl"></span>':''}<span class="dur">${fmt(m.peak)} watching</span></div>

  <div class="row"><a href="${RP}/ch/${encodeURIComponent(m.sid)}">${m.logo?`<img class="ava" src="${esc(m.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:`<span class="ava">${ini(m.name)}</span>`}</a>
  <div class="tx"><div class="tt">${esc(m.title||m.name)}</div><div class="mt"><a href="${RP}/ch/${encodeURIComponent(m.sid)}">${esc(m.name)}</a> · <span style="color:${COL[m.platform]}">${NAMES[m.platform]||''}</span> · ${esc(m.game)}<br><b>+${fmt(m.jump)}</b> viewers${m.kind==='chat'?'':` in ${m.secs<120?m.secs+'s':Math.round(m.secs/60)+' min'}`} · ${fmt(m.base)} to ${fmt(m.peak)} · ${ago(m.ts)}</div></div></div></div>`}
let sort=['views','jump','hype','new'].includes(Q.get('sort'))?Q.get('sort'):'views';
async function load(){const p=new URLSearchParams({region:REGION,period:per,sort});if(game)p.set('game',game);
 const so=document.getElementById('sort');so.innerHTML=[['views','MOST WATCHED'],['jump','BIGGEST JUMP'],['hype','HYPE'],['new','NEWEST']].map(([v,l])=>`<button data-v="${v}" class="${v===sort?'on':''}">${l}</button>`).join('');so.onclick=e=>{const b=e.target.closest('button');if(b){sort=b.dataset.v;load()}};history.replaceState(null,'',location.pathname+'?'+new URLSearchParams({period:per,sort,...(game?{game}:{})}));
 try{const j=await (await fetch('/api/moments?'+p)).json();M=j.moments||[];
  document.getElementById('per').innerHTML=[['today','TODAY'],['7d','7 DAYS'],['30d','30 DAYS']].map(([v,l])=>`<button data-v="${v}" class="${v===per?'on':''}">${l}</button>`).join('');
  document.getElementById('chips').innerHTML=[['p:today','Today',per==='today'],['p:7d','7 days',per==='7d'],['p:30d','30 days',per==='30d']].map(([v,l,on])=>`<button class="mob ${on?'on':''}" data-v="${v}">${l}</button>`).join('')+
   [['','All',!game],...(j.games||[]).slice(0,15).map(g=>[g,g,g===game])].map(([v,l,on])=>`<button class="${on?'on':''}" data-g="${esc(v)}">${esc(l)}</button>`).join('');
  const gs=document.getElementById('game');gs.innerHTML='<option value="">All games & categories</option>'+(j.games||[]).map(g=>`<option${g===game?' selected':''}>${esc(g)}</option>`).join('');
  setTimeout(()=>{if(!FOCUS)return;const i=M.findIndex(m=>String(m.id)===FOCUS);FOCUS='';const t=document.querySelector(`#grid .th[data-i="${i}"]`);if(i<0||!t)return;const cd=t.parentElement;cd.scrollIntoView({block:'center'});cd.style.outline='2px solid var(--lime)';if(player(M[i]))t.click()},0);
  document.getElementById('grid').innerHTML=M.map(card).join('')||'<div class="empty">No moments yet in this period. They appear when a stream with 1,000+ watching suddenly jumps.</div>';
  document.getElementById('note').innerHTML=`How it works: for the biggest Kick, Twitch and YouTube streams, chat speed and viewers are read every few seconds. A moment is a chat explosion (far above that stream's usual chat speed) and/or a jump in viewers far beyond that stream's usual swings. Raids, stream starts and people returning after a break don't count. Chat pins the time within seconds; viewer counts lag, so viewers-only moments start earlier. Hype = how far above normal it was. Players start 30 seconds before. ${j.clips?'Big Twitch jumps are clipped automatically.':''} Kick has no way to link to a time, so Kick moments open the channel. Replays can be missing if the streamer turned them off or deleted them.`}catch(e){}}
document.getElementById('per').onclick=e=>{const b=e.target.closest('button');if(b){per=b.dataset.v;load()}};
document.getElementById('chips').onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.v)per=b.dataset.v.slice(2);else game=b.dataset.g||'';load()};
document.getElementById('game').onchange=e=>{game=e.target.value;load()};
document.getElementById('grid').onclick=e=>{const t=e.target.closest('.th');if(!t)return;const m=M[+t.dataset.i],p=player(m);
 if(p){t.innerHTML=`<iframe src="${p}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`}else if(m.link)window.open(m.link,'_blank','noopener')};
load();setInterval(()=>{if(!document.hidden&&per==='today'&&!document.querySelector('.th iframe'))load()},60000);
</script></body></html>"""


def build_html(region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    where = "worldwide" if region == "global" else "in India"
    return (PAGE.replace("__BRAND__", html.escape(eventpage.BRAND)).replace("__REGION__", json.dumps(region))
            .replace("__WHERECAP__", "WORLDWIDE" if region == "global" else "INDIA").replace("__WHERE__", where)
            .replace("__HOME__", "/" if region == "global" else "/india").replace("__RP__", "/india" if region == "in" else "")
            .replace("__GON__", "on" if region == "global" else "").replace("__ION__", "on" if region == "in" else ""))
