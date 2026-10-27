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
__PANEL_CSS__
@media(max-width:640px){.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.brand{font-size:15px}.nav{gap:8px}
.hd{grid-template-columns:60px minmax(0,1fr);gap:12px}.hd img,.hd .ph{width:60px;height:60px}h1{font-size:28px}.hd .act{grid-column:1/-1}.hd .act .btn{width:100%;text-align:center}
.cx{padding:4px 12px 12px}.cxc{grid-template-columns:1fr}.cxt td{font-size:14px;padding:4px 3px}.cxt th{padding:4px 3px;font-size:10px}.cxd div{grid-template-columns:52px minmax(0,1fr) 64px 50px}.cxd div span:nth-child(5){display:none}
.ps{padding:4px 12px 12px}.ps a,.ps .hdr{grid-template-columns:62px minmax(0,1fr) 64px}.ps a>:nth-child(3),.ps .hdr>:nth-child(3),.ps a>:nth-child(5),.ps .hdr>:nth-child(5){display:none}}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / CHANNEL</div>
<div class="hd" id="hd"><span class="ph">..</span><div><h1>__NAME__</h1><div class="meta">Loading...</div></div></div>
<div class="card"><h2>Live stats on this site</h2><div class="cap">Recorded by this site every 2 seconds while the channel is live.</div><div id="stats"></div></div>
<div class="card"><h2>Streams, last 30 days</h2><div class="cap" id="pcap">From the platform's own list of past streams.</div><div id="past"><div class="empty">Loading...</div></div></div>
</div>
<script>
const SID=__SID__,REGION=__REGION__,RP=REGION==='in'?'/india':'';
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e7?(n/1e6).toFixed(1)+'M':n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ist=(ts,o)=>new Date(ts*1000).toLocaleString('en-IN',Object.assign({timeZone:'Asia/Kolkata'},o));
const ago=ts=>{const s=Date.now()/1000-ts;return s<120?'just now':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const av=x=>x.logo?`<img src="${esc(x.logo)}" alt="" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph>${ini(x.name)}</span>'">`:`<span class="ph">${ini(x.name)}</span>`;
const liveMap=()=>({});let OPEN=null;function render(){}
__PANEL_JS__
const hm=s=>{s=+s||0;const h=Math.floor(s/3600),m=Math.round(s%3600/60);return h?`${h}h ${m}m`:`${m}m`};
async function load(){try{const c=await (await fetch('/api/channel?sid='+encodeURIComponent(SID)+'&t='+Math.floor(Date.now()/15000))).json();if(!c.sid)return;CH[SID]=c;
 const now=c.now,S=c.stats;
 document.getElementById('hd').className='hd'+(now?' live':'');
 document.getElementById('hd').innerHTML=`${av(c)}<div style="min-width:0"><h1>${esc(c.name)}</h1><div class="meta"><b style="color:${COL[c.platform]}">${NAMES[c.platform]||''}</b>${c.country?' · '+esc(c.country):''}${S&&S.subs!=null?' · <b>'+fmt(S.subs)+'</b> subscribers':''} · ${now?`<span class="lv">LIVE</span><b>${full(now)}</b> watching${c.game?' · '+esc(c.game):''}`:c.last_live?'last live '+ago(c.last_live):''}</div>${now&&c.title?`<div class="meta" style="margin-top:6px">${esc(c.title)}</div>`:''}</div>
  <div class="act"><a class="btn${now?' red':''}" href="${esc(c.url)}" target="_blank" rel="noopener">${now?'WATCH LIVE':'OPEN'} ON ${(NAMES[c.platform]||'').toUpperCase()}</a></div>`;
 document.getElementById('stats').innerHTML=panel(SID)}catch(e){}}
async function past(){try{const j=await (await fetch('/api/past?sid='+encodeURIComponent(SID))).json();const L=j.streams||[];
 document.getElementById('pcap').textContent=(j.source?'From '+j.source+'. Views = total views of the stream, including replays. Peak = the most watching at once that day, recorded by this site.':'')+(j.note?' '+j.note:'');
 document.getElementById('past').innerHTML=L.length?`<div class="ps"><div class="hdr"><span>DATE</span><span>STREAM</span><span>LENGTH</span><span>VIEWS</span><span>PEAK THAT DAY</span></div>${L.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener"><span class="d">${x.ts?ist(x.ts,{day:'numeric',month:'short'}):esc(x.when)}${x.when&&/ago/.test(x.when)?'<br>'+esc(x.when.replace('Streamed ','')):''}</span><span class="t">${esc(x.title)}</span><span class="n">${x.secs?hm(x.secs):'-'}</span><span class="n">${x.views!=null?fmt(x.views):'-'}</span><span class="n">${x.peak_day?fmt(x.peak_day):'-'}</span></a>`).join('')}</div>`:`<div class="empty">${j.note||'No past streams listed in the last 30 days.'}</div>`}catch(e){document.getElementById('past').innerHTML='<div class="empty">Couldn\'t load past streams right now.</div>'}}
load();past();setInterval(()=>{if(!document.hidden)load()},15000);
</script></body></html>"""


def build_html(sid: str, name: str, region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    return (PAGE.replace("__PANEL_JS__", scenepage.PANEL_JS).replace("__PANEL_CSS__", scenepage.PANEL_CSS)
            .replace("__NAME__", html.escape(name)).replace("__BRAND__", html.escape(eventpage.BRAND))
            .replace("__SID__", json.dumps(sid)).replace("__REGION__", json.dumps(region))
            .replace("__RP__", "/india" if region == "in" else "").replace("__HOME__", "/india" if region == "in" else "/")
            .replace("__WHERECAP__", "INDIA" if region == "in" else "WORLDWIDE"))
