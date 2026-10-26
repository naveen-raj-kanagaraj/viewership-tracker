"""The site's front page (India live streaming, every platform) and one page per category (/c/bgmi, /c/news ...).

Same page for both: CAT is '' on the hub. Data comes from /api/scene?period=&cat= (tracker/scene.py data()).
Share cards are drawn on a canvas in the browser, like the event dashboard's.
"""
import html
import json

from tracker import eventpage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__ | __BRAND__</title>
<meta name="description" content="__DESC__">
<meta property="og:title" content="__TITLE__ | __BRAND__"><meta property="og:description" content="__DESC__">
<meta property="og:type" content="website"><meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--bg2:#121219;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;
--lime:#b6f23a;--purple:#7c5cff;--red:#ff4d5e;--yt:#ff4d5e;--kick:#53fc18;--twitch:#a970ff}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Chakra Petch",system-ui,sans-serif}
body{background:radial-gradient(800px 380px at 80% -15%,rgba(124,92,255,.12),transparent 60%),var(--bg);min-height:100vh}
a{color:inherit}.wrap{max-width:1180px;margin:0 auto;padding:16px}
.mono,.lbl,.chip,th{font-family:"Share Tech Mono",monospace}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;padding:6px 0 12px;border-bottom:1px solid var(--line)}
.brand{color:var(--lime);font:14px "Share Tech Mono",monospace;text-decoration:none}h1{margin:2px 0 0;font-size:24px;letter-spacing:.02em}h1 span{color:var(--muted);font-weight:500}
.chip{font-size:12px;border:1px solid var(--line);padding:4px 9px;color:var(--muted);white-space:nowrap}.chip b{color:var(--ink);font-weight:400}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--red);margin-right:6px;box-shadow:0 0 8px var(--red)}
nav{display:flex;gap:6px;overflow-x:auto;padding:12px 0 2px;scrollbar-width:none}nav::-webkit-scrollbar{display:none}
nav a{flex:none;font:12px "Share Tech Mono",monospace;border:1px solid var(--line);padding:6px 10px;color:var(--muted);text-decoration:none;white-space:nowrap}
nav a b{color:var(--ink);font-weight:400;margin-left:6px}nav a.on{background:var(--lime);color:#0b0b12;border-color:var(--lime)}nav a.on b{color:#0b0b12}
.card{background:var(--card);border:1px solid var(--line);padding:16px;margin-top:12px;min-width:0}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}
.lbl{color:var(--red);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
h2{margin:2px 0 0;font-size:18px}.muted{color:var(--muted)}.sub{color:var(--muted);font-size:12px}
.btn{background:var(--lime);color:#0b0b12;border:0;font:700 12px "Share Tech Mono",monospace;padding:6px 12px;cursor:pointer;clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px)}
.btn.ghost{background:none;color:var(--muted);border:1px solid var(--line);clip-path:none}
.hero{display:grid;grid-template-columns:1.25fr 1fr;gap:12px}.big{font-size:56px;font-weight:700;line-height:1.05;margin-top:6px}
.bar{display:flex;height:10px;margin:14px 0 8px;background:var(--line);overflow:hidden}.bar div{height:100%}
.leg{display:flex;flex-wrap:wrap;gap:6px 16px;font:12px "Share Tech Mono",monospace;color:var(--muted)}.leg b{color:var(--ink);font-weight:400}
.sw{display:inline-block;width:9px;height:9px;margin-right:6px}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.kpi{border-top:1px solid var(--line);padding-top:8px}.kpi .v{font-size:24px;font-weight:700}
.evs{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-top:12px}
.ev{display:block;text-decoration:none;background:var(--card);border:1px solid var(--line);padding:14px;position:relative}
.ev.live{border-color:var(--red)}.ev .st{font:11px "Share Tech Mono",monospace;padding:1px 6px;border:1px solid currentColor}
.ev .st.live{color:var(--red)}.ev .st.upcoming{color:var(--lime)}.ev .st.ended{color:var(--muted)}
.ev .n{font-size:18px;font-weight:700;margin-top:6px}.ev .v{font:22px "Share Tech Mono",monospace;margin-top:4px}.ev .go{position:absolute;right:14px;top:14px;color:var(--muted);font:12px "Share Tech Mono",monospace}
.cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:12px}
.cat{display:block;text-decoration:none;background:var(--card2);border:1px solid var(--line);padding:12px;min-width:0}
.cat:hover{border-color:var(--lime)}.cat .n{font-weight:700;font-size:16px}.cat .v{font:22px "Share Tech Mono",monospace;margin-top:2px}
.cat .s{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cat .t{height:3px;background:var(--line);margin-top:8px}.cat .t i{display:block;height:100%;background:var(--lime)}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}
.seg{display:inline-flex;border:1px solid var(--line)}.seg button{background:none;border:0;color:var(--muted);font:12px "Share Tech Mono",monospace;padding:6px 10px;cursor:pointer}
.seg button.on{background:var(--lime);color:#0b0b12}
input{background:var(--card2);border:1px solid var(--line);color:var(--ink);font:13px "Share Tech Mono",monospace;padding:6px 9px;min-width:0}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;font-weight:400;color:#0b0b12;background:var(--lime);padding:6px 8px;white-space:nowrap}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:middle}.num{text-align:right;font-family:"Share Tech Mono",monospace;white-space:nowrap}
.who{display:flex;align-items:center;gap:8px;min-width:0}.who img,.who .ph{width:26px;height:26px;border-radius:50%;object-fit:cover;flex:none;background:var(--card2);border:1px solid var(--line)}
.nl{display:flex;align-items:center;min-width:0}.who .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;display:block;text-decoration:none}.nl .pf{flex:none}
.who .tt{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:420px;display:block}
.pf{font:10px "Share Tech Mono",monospace;padding:0 5px;border:1px solid currentColor;margin-left:6px;vertical-align:1px}
.pf.youtube{color:var(--yt)}.pf.kick{color:var(--kick)}.pf.twitch{color:var(--twitch)}
.gm{font-size:12px;color:var(--muted);white-space:nowrap;text-decoration:none}a.gm:hover{color:var(--lime)}.rk{font:13px "Share Tech Mono",monospace;color:var(--muted);width:30px}
.rk.t1{color:var(--lime)}.more{display:block;margin:10px auto 0;background:none;border:1px solid var(--line);color:var(--muted);font:12px "Share Tech Mono",monospace;padding:7px 14px;cursor:pointer}
#cv{width:100%;height:260px;display:block;margin-top:10px}
.note{font-size:12px;color:var(--muted);margin-top:16px;line-height:1.6}.note b{color:var(--ink);font-weight:500}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.modal{position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.82);display:none;align-items:center;justify-content:center;padding:16px}
.modal.on{display:flex}.mbox{background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto}
.mbox img{width:100%;display:block;border:1px solid var(--line);margin:10px 0;min-height:120px}.mrow{display:flex;gap:8px;flex-wrap:wrap}#mhint{font-size:12px;color:var(--muted);margin-top:8px}
@media(max-width:900px){.hero{grid-template-columns:1fr}.big{font-size:44px}.hide-m{display:none}.who .tt{max-width:200px}.who .nm{max-width:170px}}
@media(max-width:560px){.wrap{padding:12px}.card{padding:12px}td{padding:7px 4px}th{padding:6px 4px}.rk{width:22px}.num{font-size:13px}
.who{gap:6px}.who img,.who .ph{width:22px;height:22px}.who .nm{max-width:118px;font-size:14px}.who .tt{max-width:150px}.pf{margin-left:4px}
#bt .m{display:none}#bt.s-hw .c-hw,#bt.s-peak .c-peak,#bt.s-avg .c-avg{display:table-cell}.cats{grid-template-columns:1fr 1fr}.cat .v{font-size:18px}#cv{height:200px}}
.topbar{display:flex;align-items:center;gap:20px;padding:10px 0;border-bottom:1px solid var(--line)}.topbar .brand{font-size:16px}
.tlinks{display:flex;gap:16px;flex:1;overflow-x:auto;scrollbar-width:none}.tlinks a{color:var(--muted);text-decoration:none;font-size:14px;white-space:nowrap}.tlinks a:hover{color:var(--ink)}
.heroA{display:grid;grid-template-columns:1.2fr 1fr;gap:28px;align-items:center;padding:30px 0 6px}
.heroA h1{font-size:46px;line-height:1.05;margin:6px 0 10px;letter-spacing:0}.heroA h1 em{font-style:normal;color:#a58bff}.heroA h1 span{color:var(--ink);font-weight:700}
.lead{color:#c9c8d8;font-size:16px;margin:0 0 18px}
.srch{position:relative;max-width:520px}.srch input{width:100%;border-radius:999px;padding:12px 18px;font:15px "Chakra Petch",sans-serif;background:var(--card2)}
.sres{position:absolute;left:0;right:0;top:calc(100% + 6px);background:var(--bg2);border:1px solid var(--line);z-index:20;display:none}.sres.on{display:block}
.sres a{display:flex;justify-content:space-between;gap:10px;padding:9px 14px;text-decoration:none;border-bottom:1px solid var(--line)}.sres a:hover{background:var(--card2)}.sres small{color:var(--muted);font-family:"Share Tech Mono",monospace}
.nowrow{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin-top:22px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.tile{background:var(--card);border:1px solid var(--line);padding:10px;cursor:pointer;text-align:left;color:var(--ink);font:inherit;display:flex;flex-direction:column;gap:6px;align-items:flex-start;min-width:0}
.tile.on{border-color:var(--lime);box-shadow:0 0 0 1px var(--lime) inset}.tile .pi{width:30px;height:30px;border-radius:7px;display:grid;place-items:center;flex:none;font:700 15px "Chakra Petch",sans-serif;color:#0b0b12}
.tile .tn{font-size:12px;color:var(--muted);white-space:nowrap}.tile .tv{font:17px "Share Tech Mono",monospace}
.pertabs{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-top:18px}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:10px}
.col{background:var(--card);border:1px solid var(--line);display:flex;flex-direction:column;min-width:0}
.colh{display:flex;align-items:center;gap:10px;padding:13px 14px;font-weight:600;font-size:16px}.colh .pp{margin-left:auto;color:var(--muted);font-size:13px;font-weight:400;white-space:nowrap}
.colh .ic{width:26px;height:26px;border:1px solid var(--line);display:grid;place-items:center;color:var(--muted);font-size:12px;flex:none}
.cth{display:flex;justify-content:space-between;align-items:center;padding:7px 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font:11px "Share Tech Mono",monospace;color:var(--muted);background:var(--card2)}
.cth .seg button{padding:3px 7px;font-size:11px}
.cr{display:grid;grid-template-columns:18px 36px minmax(0,1fr) auto;gap:10px;align-items:center;padding:9px 14px;text-decoration:none;border-bottom:1px solid #1c1c29}
.cr .r{font:12px "Share Tech Mono",monospace;color:var(--muted)}.cr .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cr .sb{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.av{position:relative;width:36px;height:36px}.av img,.av .ph{width:36px;height:36px;border-radius:50%;object-fit:cover;background:var(--card2);border:1px solid var(--line);display:grid;place-items:center;font:700 12px "Chakra Petch",sans-serif;color:var(--muted)}
.av .ph.sq{border-radius:6px;color:#0b0b12}.av .bd{position:absolute;right:-3px;bottom:-3px;width:15px;height:15px;border-radius:4px;display:grid;place-items:center;font:700 9px "Chakra Petch",sans-serif;color:#0b0b12;border:2px solid var(--card)}
.cv{text-align:right;font:14px "Share Tech Mono",monospace;min-width:84px}.cv i{display:block;height:2px;margin:5px 0 0 auto}
.cf{margin-top:auto;display:block;text-align:center;padding:12px;border-top:1px solid var(--line);text-decoration:none;font-size:14px;background:var(--card2)}.cf:hover{color:var(--lime)}
.hero2{display:grid;grid-template-columns:1.25fr 1fr;gap:12px}
@media(max-width:980px){.heroA{grid-template-columns:1fr;padding-top:18px}.cols{grid-template-columns:1fr}.hero2{grid-template-columns:1fr}.heroA h1{font-size:34px}}
@media(max-width:560px){.tiles{grid-template-columns:1fr 1fr}.topbar{gap:12px;justify-content:space-between}.tlinks{display:none}.heroA .big{font-size:40px}}
</style></head><body><div class="wrap">
<div class="topbar"><a class="brand" href="/">__BRAND__</a><div class="tlinks"><a href="#cols">Rankings</a><a href="#catcard">Categories</a><a href="#evwrap">Tournaments</a><a href="#livecard">Live now</a><a href="#boardcard">Leaderboard</a></div><span class="chip"><span class="dot"></span>UPDATED <b id="upd">-</b></span></div>
<section class="heroA">
 <div><div class="lbl" id="kick">// India // YouTube + Kick + Twitch</div><h1 id="h1"></h1><p class="lead" id="lead"></p>
  <div class="srch"><input id="sq" placeholder="Channel or category..." autocomplete="off"><div class="sres" id="sres"></div></div></div>
 <div><div class="card" style="margin-top:0"><div class="nowrow" style="margin-top:0"><div><div class="lbl" id="wl">// Watching now</div><div class="big mono" id="tot">-</div><div class="muted" id="cnt"></div></div><button class="btn" data-share="now">SHARE</button></div>
  <div class="bar" id="pbar"></div><div class="leg" id="pleg"></div></div>
  <div class="tiles" id="tiles" style="margin-top:10px"></div></div>
</section>
<nav id="nav"></nav>
<div class="pertabs"><div class="seg" id="perG"></div><span class="sub" id="pernote"></span></div>
<div class="cols" id="cols">
 <div class="col"><div class="colh"><span class="ic">&#9673;</span><span id="c1t">Most watched streamers</span><span class="pp" id="c1p"></span></div><div class="cth"><span>CHANNEL</span><span class="seg" id="c1s"></span></div><div id="c1"></div><a class="cf" href="#boardcard" id="c1f">Full leaderboard &rarr;</a></div>
 <div class="col"><div class="colh"><span class="ic">&#9638;</span><span id="c2t">Top categories</span><span class="pp" id="c2p"></span></div><div class="cth"><span id="c2h">CATEGORY</span><span id="c2m">AVERAGE VIEWERS</span></div><div id="c2"></div><a class="cf" href="#gcard" id="c2f">All categories &rarr;</a></div>
 <div class="col"><div class="colh"><span class="ic">&#9654;</span><span id="c3t">Top games</span><span class="pp" id="c3p"></span></div><div class="cth"><span id="c3h">GAME</span><span id="c3m">AVERAGE VIEWERS</span></div><div id="c3"></div><a class="cf" href="#gcard" id="c3f">All games &rarr;</a></div>
</div>
<div id="evwrap"></div>
<div class="hero2">
 <div class="card"><div class="kpis" style="margin-top:0"><div class="kpi" style="border:0;padding:0"><div class="lbl" id="pkl">// Peak, last 24 hours</div><div class="v mono" id="pk">-</div><div class="sub" id="pkw"></div></div>
   <div class="kpi" style="border:0;padding:0"><div class="lbl">// Highest recorded</div><div class="v mono" id="pka">-</div><div class="sub" id="pkaw"></div></div></div></div>
 <div class="card"><div class="lbl">// Biggest stream right now</div><div id="topone" style="margin-top:10px"></div></div>
</div>
<div class="card"><div class="head"><div><div class="lbl">// Viewers over time</div><h2 id="ch">Concurrent viewers</h2></div><div style="display:flex;gap:8px"><div class="seg" id="per1"></div><button class="btn" data-share="chart">SHARE</button></div></div>
 <canvas id="cv"></canvas></div>
<div class="card" id="catcard"><div class="head"><div><div class="lbl">// Games &amp; categories, live now</div><h2>What India is watching</h2><div class="sub">Tap one for its own page: live streams, top streamers, viewers over time.</div></div><button class="btn" data-share="cats">SHARE</button></div>
 <div class="cats" id="cats"></div></div>
<div class="card" id="livecard"><div class="head"><div><div class="lbl">// Live now</div><h2 id="lh">Live streams</h2></div><button class="btn" data-share="live">SHARE</button></div>
 <div class="tools"><div class="seg" id="plat"></div><input id="q" placeholder="Search streamer or title" style="flex:1;min-width:140px"></div>
 <div class="scroll"><table><thead><tr><th>#</th><th>STREAMER</th><th class="hide-m" id="lcat">CATEGORY</th><th class="num">VIEWERS</th></tr></thead><tbody id="live"></tbody></table></div>
 <button class="more" id="lmore"></button></div>
<div class="card" id="boardcard"><div class="head"><div><div class="lbl">// Leaderboard</div><h2 id="bh">Top streamers</h2></div><button class="btn" data-share="board">SHARE</button></div>
 <div class="tools"><div class="seg" id="per"></div><div class="seg" id="sort"></div><div class="seg" id="bplat"></div></div>
 <div class="scroll"><table id="bt" class="s-hw"><thead><tr><th>#</th><th>STREAMER</th><th class="hide-m" id="bcat">MAIN CATEGORY</th><th class="num m c-hw">HOURS WATCHED</th><th class="num m c-peak">PEAK</th><th class="num m c-avg">AVG</th><th class="num hide-m">AIRTIME</th></tr></thead><tbody id="board"></tbody></table></div>
 <button class="more" id="bmore"></button></div>
<div class="card" id="gcard"><div class="lbl">// Categories</div><h2 id="gh">Games &amp; categories by hours watched</h2>
 <div class="scroll" style="margin-top:12px"><table><thead><tr><th>#</th><th>CATEGORY</th><th class="num">HOURS WATCHED</th><th class="num">BIGGEST STREAM</th><th class="num hide-m">STREAMERS</th></tr></thead><tbody id="gboard"></tbody></table></div></div>
<div class="note" id="note"></div>
<div class="foot"><span>Unofficial rankings by __BRAND__. Not affiliated with YouTube, Kick, Twitch or any publisher.</span><span>__SOCIAL__</span></div>
</div>
<div class="modal" id="modal"><div class="mbox"><div class="head"><h2>Share</h2><button class="btn ghost" id="mclose">Close</button></div>
 <img id="mimg" alt="Share card"><div class="mrow"><button class="btn" id="mig">INSTAGRAM</button><button class="btn" id="mxb">X</button><button class="btn ghost" id="mdl">DOWNLOAD</button><button class="btn ghost" id="mcp">COPY LINK</button></div><div id="mhint"></div></div></div>
<script>
const _H={};function setH(id,h){const e=document.getElementById(id);if(e&&_H[id]!==h){_H[id]=h;e.innerHTML=h}}
const CAT=__CAT__,CATNAME=__CATNAME__,SITE='https://live.letsgrowesports.com',PAGEURL=SITE+(CAT?'/c/'+CAT:'/');
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'#ff4d5e',kick:'#53fc18',twitch:'#a970ff'};
let D=null,per='today',sort='hw',plat='all',bplat='all',q='',lAll=false,bAll=false,LOGOS=true;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ist=(ts,o)=>new Date(ts*1000).toLocaleString('en-IN',Object.assign({timeZone:'Asia/Kolkata'},o));
const when=ts=>ts?ist(ts,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST':'';
const PER={today:'last 24 hours','7d':'last 7 days','30d':'last 30 days'},PERB={today:'today (IST)','7d':'last 7 days','30d':'last 30 days'};
const SCOPE=()=>CAT?CATNAME+' in India':'India';
const who=(x,t)=>`<div class="who">${x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph></span>'">`:'<span class="ph"></span>'}<div style="min-width:0"><div class="nl"><a class="nm" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a><span class="pf ${esc(x.platform)}">${esc((NAMES[x.platform]||x.platform||'').toUpperCase())}</span></div>${t?`<span class="tt">${esc(t)}</span>`:''}</div></div>`;
const slug=g=>String(g||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'other';
const catLink=g=>`<a class="gm" href="/c/${esc(slug(g))}">${esc(g)}</a>`;
function seg(id,opts,cur,on){const e=document.getElementById(id);setH(id,opts.map(([v,l])=>`<button data-v="${v}" class="${v===cur?'on':''}">${l}</button>`).join(''));e.onclick=ev=>{const b=ev.target.closest('button');if(b)on(b.dataset.v)}}
setH('h1',CAT?`<em>${esc(CATNAME)}</em> live in India, <span>counted</span>`:'India\'s <em>live streaming</em>, counted and ranked');
const PL=[['all','All platforms','#eeeef5','\u2731'],['youtube','YouTube',COL.youtube,'\u25B6'],['kick','Kick',COL.kick,'K'],['twitch','Twitch',COL.twitch,'T']];
const ini=s=>esc(String(s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const HUE=g=>{let h=0;for(const ch of String(g))h=(h*31+ch.charCodeAt(0))%360;return `hsl(${h} 70% 62%)`};
const avS=x=>`<span class="av">${x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph>${ini(x.name)}</span>'">`:`<span class="ph">${ini(x.name)}</span>`}<span class="bd" style="background:${COL[x.platform]||'#888'}">${(x.platform||'?')[0].toUpperCase()}</span></span>`;
const avC=g=>`<span class="av"><span class="ph sq" style="background:${HUE(g)}">${ini(g)}</span></span>`;
const crow=(i,href,av,name,sub,val,w,col,ext)=>`<a class="cr" href="${esc(href)}"${ext?' target="_blank" rel="noopener"':''}><span class="r">${i+1}</span>${av}<span style="min-width:0"><div class="nm">${esc(name)}</div>${sub?`<div class="sb">${esc(sub)}</div>`:''}</span><span class="cv">${val}<i style="width:${Math.max(4,w*100)}%;background:${col}"></i></span></a>`;
let c1sort='hw';
function renderTop(){const per3=PERB[per];
 document.getElementById('lead').textContent=CAT?`Every ${CATNAME} live stream in India on YouTube, Kick and Twitch: who is live now, who leads ${per3}.`:`YouTube, Kick and Twitch, every game and category. ${full(D.tracked||0)} Indian channels tracked so far, updated every ${Math.round(D.every/60)} minutes.`;
 const byp={};(D.platforms||[]).forEach(p=>byp[p.platform]=p.viewers);
 setH('tiles',PL.map(([k,n,c,ic])=>`<button class="tile${plat===k?' on':''}" data-p="${k}"><span class="pi" style="background:${c}">${ic}</span><span><div class="tn">${n}</div><div class="tv">${fmt(k==='all'?D.live_total:byp[k]||0)}</div></span></button>`).join(''));
 document.querySelectorAll('.tile').forEach(t=>t.onclick=()=>{plat=bplat=t.dataset.p;lAll=bAll=false;render()});
 seg('perG',[['today','TODAY'],['7d','LAST 7 DAYS'],['30d','LAST 30 DAYS']],per,v=>{per=v;bAll=false;load()});
 document.getElementById('pernote').textContent=plat==='all'?'':`Streamers: ${NAMES[plat]} only. Categories count every platform.`;
 const B=D.board.filter(x=>plat==='all'||x.platform===plat).sort((a,b)=>b[c1sort]-a[c1sort]).slice(0,10),m1=B[0]?B[0][c1sort]:1;
 seg('c1s',[['hw','HOURS'],['peak','PEAK']],c1sort,v=>{c1sort=v;renderTop()});
 document.getElementById('c1t').textContent=CAT?`Most watched ${CATNAME} streamers`:'Most watched streamers';document.getElementById('c1p').textContent=per3;
 setH('c1',B.map((x,i)=>crow(i,x.url,avS(x),x.name,CAT?NAMES[x.platform]:x.game,c1sort==='hw'?fmt(x.hw)+'h':fmt(x.peak),x[c1sort]/m1,'#4cc9f0',1)).join('')||'<div class="cr muted" style="display:block">No data for this period yet.</div>');
 if(CAT){const L=liveList().slice(0,10),ml=L[0]?L[0].viewers:1,P=D.board.filter(x=>plat==='all'||x.platform===plat).sort((a,b)=>b.peak-a.peak).slice(0,10),mp=P[0]?P[0].peak:1;
  document.getElementById('c2t').textContent='Live now';document.getElementById('c2p').textContent=`${L.length?D.live.length:0} live`;document.getElementById('c2h').textContent='CHANNEL';document.getElementById('c2m').textContent='VIEWERS';
  setH('c2',L.map((x,i)=>crow(i,x.url,avS(x),x.name,x.title,full(x.viewers),x.viewers/ml,'#ff4d5e',1)).join('')||'<div class="cr muted" style="display:block">Nothing live right now.</div>');
  document.getElementById('c2f').href='#livecard';setH('c2f','All live streams &rarr;');
  document.getElementById('c3t').textContent='Highest peaks';document.getElementById('c3p').textContent=per3;document.getElementById('c3h').textContent='CHANNEL';document.getElementById('c3m').textContent='PEAK VIEWERS';
  setH('c3',P.map((x,i)=>crow(i,x.url,avS(x),x.name,NAMES[x.platform],fmt(x.peak),x.peak/mp,'#b6f23a',1)).join('')||'<div class="cr muted" style="display:block">No data for this period yet.</div>');
  document.getElementById('c3f').href='#boardcard';setH('c3f','Full leaderboard &rarr;');return}
 const CP=D.cat_period||[],A=CP.slice(0,10),G=CP.filter(c=>c.gaming).slice(0,10),ma=A[0]?A[0].avg:1,mg=G[0]?G[0].avg:1;
 document.getElementById('c2p').textContent=per3;document.getElementById('c3p').textContent=per3;
 setH('c2',A.map((c,i)=>crow(i,'/c/'+c.slug,avC(c.game),c.game,'peak '+fmt(c.peak),fmt(c.avg),c.avg/ma,'#ff8a3d')).join('')||'<div class="cr muted" style="display:block">No data for this period yet.</div>');
 setH('c3',G.map((c,i)=>crow(i,'/c/'+c.slug,avC(c.game),c.game,'peak '+fmt(c.peak),fmt(c.avg),c.avg/mg,'#b6f23a')).join('')||'<div class="cr muted" style="display:block">No data for this period yet.</div>');
}
// search: channels and categories in what's loaded
const sq=document.getElementById('sq'),sres=document.getElementById('sres');
sq.oninput=()=>{const v=sq.value.trim().toLowerCase();if(!v||!D){sres.classList.remove('on');return}
 const seen=new Set(),out=[];
 (D.cat_period||[]).concat((D.categories||[]).map(c=>({game:c.game,slug:c.slug}))).forEach(c=>{if(c.game.toLowerCase().includes(v)&&!seen.has('c'+c.slug)){seen.add('c'+c.slug);out.push(`<a href="/c/${esc(c.slug)}"><span>${esc(c.game)}</span><small>CATEGORY</small></a>`)}});
 D.live.concat(D.board).forEach(x=>{if(x.name.toLowerCase().includes(v)&&!seen.has(x.sid)){seen.add(x.sid);out.push(`<a href="${esc(x.url)}" target="_blank" rel="noopener"><span>${esc(x.name)}</span><small>${(NAMES[x.platform]||'').toUpperCase()}${x.game?' // '+esc(x.game):''}</small></a>`)}});
 sres.innerHTML=out.slice(0,10).join('')||'<a><span class="muted">Nothing found yet. Only channels seen live are searchable.</span></a>';sres.classList.add('on')};
document.addEventListener('click',e=>{if(!e.target.closest('.srch'))sres.classList.remove('on')});
if(CAT){['catcard','gcard','lcat','bcat'].forEach(i=>document.getElementById(i).style.display='none')}
function cdTxt(ns){const l=ns-Date.now()/1000;if(l<=0)return 'STARTING SOON';const d=Math.floor(l/86400),h=Math.floor(l%86400/3600),m=Math.floor(l%3600/60),s=Math.floor(l%60),p=n=>String(n).padStart(2,'0');return (d?d+'D ':'')+`${p(h)}:${p(m)}:${p(s)}`}
function renderEvents(){const w=document.getElementById('evwrap'),E=(D.events||[]).filter(e=>e.state!=='off');if(!E.length){w.innerHTML='';return}
 w.innerHTML=`<div class="evs">${E.map(e=>`<a class="ev ${e.state}" href="${esc(e.url)}"><span class="st ${e.state}">${e.state==='live'?'● LIVE NOW':e.state==='upcoming'?'STARTS IN':'FINISHED'}</span><span class="go">${e.state==='ended'?'RESULTS':'OPEN'} &rarr;</span>
  <div class="n">${esc(e.name)}</div><div class="v" data-ns="${e.state==='upcoming'?e.next_start:''}">${e.state==='live'?full(e.now)+' watching':e.state==='upcoming'?cdTxt(e.next_start):'Peak '+fmt(e.peak)}</div><div class="sub">${esc(e.game||'')} // tournament tracker</div></a>`).join('')}</div>`}
const liveList=()=>D.live.filter(x=>(plat==='all'||x.platform===plat)&&(!q||(x.name+' '+x.title).toLowerCase().includes(q)));
const boardList=()=>D.board.filter(x=>bplat==='all'||x.platform===bplat).sort((a,b)=>b[sort]-a[sort]);
function render(){if(!D)return;
 const ago=Math.max(0,Math.round(Date.now()/1000-D.updated));document.getElementById('upd').textContent=D.updated?(ago<90?ago+'s ago':Math.round(ago/60)+' min ago'):'-';
 const C=D.categories||[];
 setH('nav',`<a href="/" class="${CAT?'':'on'}">ALL INDIA<b>${D.fresh?fmt(D.india_total):''}</b></a>`+C.slice(0,14).map(g=>`<a href="/c/${esc(g.slug)}" class="${g.slug===CAT?'on':''}">${esc(g.game.toUpperCase())}<b>${fmt(g.viewers)}</b></a>`).join(''));
 renderEvents();renderTop();
 document.getElementById('wl').textContent=`// Watching now, ${SCOPE()}`;
 document.getElementById('tot').textContent=D.fresh?full(D.live_total):'-';
 document.getElementById('cnt').textContent=D.fresh?`across ${D.live_count} live stream${D.live_count===1?'':'s'}${CAT&&D.india_total?` // ${(100*D.live_total/D.india_total).toFixed(1)}% of India`:''}`:'Waiting for the first scan (every '+D.every+'s)';
 const tot=D.live_total||1;setH('pbar',D.platforms.map(p=>`<div style="width:${100*p.viewers/tot}%;background:${COL[p.platform]}"></div>`).join(''));
 setH('pleg',D.platforms.map(p=>`<span><span class="sw" style="background:${COL[p.platform]}"></span>${p.name.toUpperCase()} <b>${fmt(p.viewers)}</b> (${(100*p.viewers/tot).toFixed(0)}%)</span>`).join(''));
 document.getElementById('pkl').textContent='// Peak, '+PER[per];document.getElementById('pk').textContent=D.peak?fmt(D.peak.viewers):'-';document.getElementById('pkw').textContent=D.peak?when(D.peak.ts):'';
 document.getElementById('pka').textContent=D.peak_all?fmt(D.peak_all.viewers):'-';document.getElementById('pkaw').textContent=D.peak_all?when(D.peak_all.ts):'';
 const t=D.live[0];setH('topone',t?`${who(t,t.title)}<div class="big mono" style="font-size:40px">${full(t.viewers)}</div><div class="muted">${CAT?'':esc(t.game)+' // '}${(100*t.viewers/tot).toFixed(1)}% of ${CAT?esc(CATNAME)+' viewers':'everyone watching'}</div>`:'<span class="muted">Nothing live in the last scan.</span>');
 document.getElementById('ch').textContent=`Concurrent viewers, ${SCOPE()}, ${PER[per]}`;
 seg('per1',[['today','24H'],['7d','7D'],['30d','30D']],per,v=>{per=v;bAll=false;load()});drawChart();
 const gm=C[0]?C[0].viewers:1;
 setH('cats',C.slice(0,24).map(g=>`<a class="cat" href="/c/${esc(g.slug)}"><div class="n">${esc(g.game)}</div><div class="v">${fmt(g.viewers)}</div><div class="s">${g.streams} live // top: ${esc(g.top)}</div><div class="t"><i style="width:${100*g.viewers/gm}%"></i></div></a>`).join('')||'<span class="muted">Nothing live in the last scan.</span>');
 seg('plat',[['all','ALL'],...['youtube','kick','twitch'].map(p=>[p,p.toUpperCase()])],plat,v=>{plat=v;lAll=false;render()});
 const L=liveList(),ll=lAll||q?L:L.slice(0,25);
 document.getElementById('lh').textContent=`Live streams (${L.length})`;
 setH('live',ll.map((x,i)=>`<tr><td class="rk${i<3?' t1':''}">${i+1}</td><td>${who(x,x.title)}</td>${CAT?'':`<td class="hide-m">${catLink(x.game)}</td>`}<td class="num">${full(x.viewers)}</td></tr>`).join('')||'<tr><td colspan=4 class="muted">Nothing live matches.</td></tr>');
 const lm=document.getElementById('lmore');lm.style.display=L.length>25&&!q?'block':'none';lm.textContent=lAll?'SHOW FEWER':`SHOW ALL ${L.length}`;lm.onclick=()=>{lAll=!lAll;render()};
 seg('per',[['today','TODAY'],['7d','7 DAYS'],['30d','30 DAYS']],per,v=>{per=v;bAll=false;load()});
 seg('sort',[['hw','HOURS WATCHED'],['peak','PEAK'],['avg','AVERAGE']],sort,v=>{sort=v;render()});
 seg('bplat',[['all','ALL'],...['youtube','kick','twitch'].map(p=>[p,p.toUpperCase()])],bplat,v=>{bplat=v;bAll=false;render()});
 document.getElementById('bt').className='s-'+sort;
 const B=boardList(),bb=bAll?B:B.slice(0,25);
 document.getElementById('bh').textContent=`Top ${CAT?CATNAME+' ':''}streamers, ${PERB[per]}`;
 setH('board',bb.map((x,i)=>`<tr><td class="rk${i<3?' t1':''}">${i+1}</td><td>${who(x)}</td>${CAT?'':`<td class="hide-m">${catLink(x.game)}</td>`}<td class="num m c-hw">${fmt(x.hw)}h</td><td class="num m c-peak">${fmt(x.peak)}</td><td class="num m c-avg">${fmt(x.avg)}</td><td class="num hide-m">${x.airtime_h}h</td></tr>`).join('')||'<tr><td colspan=7 class="muted">No data for this period yet.</td></tr>');
 const bm=document.getElementById('bmore');bm.style.display=B.length>25?'block':'none';bm.textContent=bAll?'SHOW FEWER':`SHOW ALL ${B.length}`;bm.onclick=()=>{bAll=!bAll;render()};
 document.getElementById('gh').textContent=`Games & categories by hours watched, ${PERB[per]}`;
 setH('gboard',D.games.map((g,i)=>`<tr><td class="rk${i<3?' t1':''}">${i+1}</td><td><a href="/c/${esc(g.slug)}" style="text-decoration:none"><b>${esc(g.game)}</b></a></td><td class="num">${fmt(g.hw)}h</td><td class="num">${fmt(g.peak_stream)}</td><td class="num hide-m">${g.channels}</td></tr>`).join('')||'<tr><td colspan=5 class="muted">No data yet.</td></tr>');
 const miss=['kick','twitch'].filter(p=>!D.keys[p]).map(p=>NAMES[p]);
 setH('note',`<b>How this is counted.</b> A scan every ${Math.round(D.every/60)} minutes: YouTube's Live page for India and live searches for each game, language and category (news, devotional, music, cricket, talk), localised to India, plus hand-added channels; Kick and Twitch streams in ${esc(D.langs.join(', '))} plus hand-added channels. Viewers are each platform's own concurrent count; a channel streaming twice at once is added together; streams under ${D.min} viewers are left out. Categories come from the platform category (Kick, Twitch) or the stream title (YouTube); a title that names none is Other. Hours watched = viewers x time live. <b>Not a census:</b> a stream that doesn't show up in these searches or languages is missed, so totals are a floor, not the whole of India.${miss.length?` ${miss.join(' and ')} language-wide discovery is off until API keys are added; only hand-added channels are counted there.`:''}`);
}
function drawChart(){const cv=document.getElementById('cv'),dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;if(!W)return;
 cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,W,H);plot(x,W,H,D.series||[],1)}
function plot(x,W,H,S,fs){const pl=8*fs,pr=58*fs,pt=12*fs,pb=24*fs;
 x.font=`${11*fs}px "Share Tech Mono",monospace`;x.fillStyle='#8d8ca3';x.textAlign='left';
 if(S.length<2){x.fillText('Not enough readings yet for this period.',pl,H/2);return}
 const t0=S[0][0],t1=S[S.length-1][0],mx=Math.max(...S.map(p=>p[1]))*1.12||1,X=t=>pl+(W-pl-pr)*(t-t0)/((t1-t0)||1),Y=v=>pt+(H-pt-pb)*(1-v/mx);
 x.strokeStyle='#262636';x.lineWidth=1;for(let i=0;i<=4;i++){const y=pt+(H-pt-pb)*i/4;x.beginPath();x.moveTo(pl,y);x.lineTo(W-pr,y);x.stroke();x.fillText(fmt(mx*(1-i/4)),W-pr+6*fs,y+4*fs)}
 const span=t1-t0;for(let i=0;i<=4;i++){const t=t0+span*i/4;x.textAlign=i===0?'left':i===4?'right':'center';x.fillText(span>2*86400?ist(t,{day:'numeric',month:'short'}):ist(t,{hour:'numeric',minute:'2-digit'}),X(t),H-6*fs)}x.textAlign='left';
 const g=x.createLinearGradient(0,pt,0,H-pb);g.addColorStop(0,'rgba(182,242,58,.28)');g.addColorStop(1,'rgba(182,242,58,0)');
 x.beginPath();S.forEach((p,i)=>i?x.lineTo(X(p[0]),Y(p[1])):x.moveTo(X(p[0]),Y(p[1])));x.lineTo(X(t1),H-pb);x.lineTo(X(t0),H-pb);x.closePath();x.fillStyle=g;x.fill();
 x.beginPath();S.forEach((p,i)=>i?x.lineTo(X(p[0]),Y(p[1])):x.moveTo(X(p[0]),Y(p[1])));x.strokeStyle='#b6f23a';x.lineWidth=2.2*fs;x.shadowColor='rgba(182,242,58,.6)';x.shadowBlur=10*fs;x.stroke();x.shadowBlur=0;
 const pk=S.reduce((a,p)=>p[1]>a[1]?p:a,S[0]);x.fillStyle='#b6f23a';x.beginPath();x.arc(X(pk[0]),Y(pk[1]),4*fs,0,7);x.fill();
 x.font=`700 ${12*fs}px "Chakra Petch",sans-serif`;const right=X(pk[0])>W-pr-90*fs;x.textAlign=right?'right':'left';x.fillText('PEAK '+fmt(pk[1]),X(pk[0])+(right?-8:8)*fs,Y(pk[1])-6*fs);x.textAlign='left'}
window.addEventListener('resize',()=>D&&drawChart());
// ---------- share cards (1080x1350, drawn at 2x) ----------
let cur=null;
function loadImg(u){return new Promise(r=>{if(!u||!LOGOS)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
function base(title,sub){const c=document.createElement('canvas');c.width=2160;c.height=2700;const x=c.getContext('2d');x.scale(2,2);
 x.fillStyle='#0b0b12';x.fillRect(0,0,1080,1350);const g=x.createRadialGradient(860,-60,10,860,-60,700);g.addColorStop(0,'rgba(124,92,255,.22)');g.addColorStop(1,'rgba(124,92,255,0)');x.fillStyle=g;x.fillRect(0,0,1080,1350);
 x.fillStyle='#b6f23a';x.font='30px "Share Tech Mono",monospace';x.fillText('letsgrowesports',72,96);
 x.fillStyle='#ffffff';x.font='700 60px "Chakra Petch",sans-serif';x.fillText(title.slice(0,28),72,170);x.fillStyle='#8d8ca3';x.font='28px "Share Tech Mono",monospace';x.fillText(sub.slice(0,60),72,218);
 x.fillStyle='#262636';x.fillRect(72,250,936,2);x.fillStyle='#8d8ca3';x.font='26px "Share Tech Mono",monospace';x.fillText('live.letsgrowesports.com'+(CAT?'/c/'+CAT:''),72,1290);
 x.textAlign='right';x.fillText(ist(Date.now()/1000,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST',1008,1290);x.textAlign='left';return [c,x]}
function listRows(x,R,avs){R.slice(0,10).forEach((r,i)=>{const y=290+i*96;x.fillStyle=i<3?'#b6f23a':'#8d8ca3';x.font='700 34px "Share Tech Mono",monospace';x.fillText(String(i+1).padStart(2,'0'),72,y+46);
  const im=avs&&avs[i];let tx=150;if(im){x.save();x.beginPath();x.arc(178,y+34,28,0,7);x.clip();x.drawImage(im,150,y+6,56,56);x.restore();tx=226}
  x.fillStyle='#ffffff';x.font='700 34px "Chakra Petch",sans-serif';let n=r.name;while(x.measureText(n).width>560-(tx-150)&&n.length>3)n=n.slice(0,-2);if(n!==r.name)n+='…';x.fillText(n,tx,y+32);
  x.font='22px "Share Tech Mono",monospace';x.fillStyle=r.color||'#8d8ca3';x.fillText((r.tag||'').slice(0,46),tx,y+64);
  x.textAlign='right';x.fillStyle='#ffffff';x.font='700 40px "Share Tech Mono",monospace';x.fillText(r.value,1008,y+46);x.textAlign='left';
  x.fillStyle='#1d1d2b';x.fillRect(72,y+84,936,1)})}
async function card(type){let c,x,text;const sc=SCOPE();
 if(type==='now'){[c,x]=base(sc.toUpperCase()+', LIVE NOW',`${D.live_count} live streams // YouTube + Kick + Twitch`);
  x.fillStyle='#ff4d5e';x.font='30px "Share Tech Mono",monospace';x.fillText('// WATCHING RIGHT NOW',72,320);
  x.fillStyle='#ffffff';x.font='700 150px "Chakra Petch",sans-serif';x.fillText(full(D.live_total),64,470);
  const tot=D.live_total||1;let xx=72;D.platforms.forEach(p=>{const w=936*p.viewers/tot;x.fillStyle=COL[p.platform];x.fillRect(xx,540,w,18);xx+=w});
  x.font='26px "Share Tech Mono",monospace';xx=72;D.platforms.forEach(p=>{x.fillStyle=COL[p.platform];x.fillRect(xx,586,16,16);x.fillStyle='#d8d8e4';const s=`${p.name.toUpperCase()} ${fmt(p.viewers)}`;x.fillText(s,xx+26,602);xx+=x.measureText(s).width+60});
  const T=(CAT?D.live.map(s=>[s.name,s.viewers]):D.categories.map(g=>[g.game,g.viewers])).slice(0,5);x.fillStyle='#ff4d5e';x.font='30px "Share Tech Mono",monospace';x.fillText(CAT?'// TOP STREAMS':'// TOP CATEGORIES',72,700);
  T.forEach((r,i)=>{const y=780+i*88;x.fillStyle=i===0?'#b6f23a':'#ffffff';x.font='700 40px "Chakra Petch",sans-serif';x.fillText(`${i+1}. ${r[0]}`.slice(0,30),72,y);x.textAlign='right';x.font='700 40px "Share Tech Mono",monospace';x.fillText(fmt(r[1]),1008,y);x.textAlign='left'});
  text=`${sc} right now: ${full(D.live_total)} watching across ${D.live_count} live streams on YouTube, Kick and Twitch.${T[0]?` Top: ${T[0][0]} ${fmt(T[0][1])}.`:''}`}
 else if(type==='chart'){[c,x]=base(sc.toUpperCase(),`Concurrent viewers, ${PER[per]}`);
  x.fillStyle='#ff4d5e';x.font='30px "Share Tech Mono",monospace';x.fillText('// PEAK, '+PER[per].toUpperCase(),72,320);
  x.fillStyle='#ffffff';x.font='700 130px "Chakra Petch",sans-serif';x.fillText(D.peak?fmt(D.peak.viewers):'-',64,450);x.fillStyle='#8d8ca3';x.font='28px "Share Tech Mono",monospace';x.fillText(D.peak?when(D.peak.ts):'',72,500);
  x.save();x.translate(40,560);plot(x,1000,640,D.series||[],1.7);x.restore();
  text=`${sc}: peak ${D.peak?full(D.peak.viewers):'-'} concurrent viewers in the ${PER[per]}${D.peak?` (${when(D.peak.ts)})`:''}.`}
 else if(type==='cats'){[c,x]=base('WHAT INDIA IS WATCHING','Games & categories, live now');listRows(x,D.categories.slice(0,10).map(g=>({name:g.game,tag:`${g.streams} live // top: ${g.top}`,value:fmt(g.viewers)})));
  text=`What India is watching live right now: ${D.categories.slice(0,3).map((g,i)=>`${i+1}. ${g.game} ${fmt(g.viewers)}`).join(' | ')}.`}
 else if(type==='live'){const L=liveList().slice(0,10);[c,x]=base(sc.toUpperCase(),'Top live streams right now');const avs=await Promise.all(L.map(s=>loadImg(s.logo)));
  listRows(x,L.map(s=>({name:s.name,tag:`${(NAMES[s.platform]||'').toUpperCase()}${CAT?'':' // '+s.game}`,color:COL[s.platform],value:fmt(s.viewers)})),avs);
  text=`Top live streams, ${sc}, right now: ${L.slice(0,3).map((s,i)=>`${i+1}. ${s.name} ${fmt(s.viewers)}`).join(' | ')}.`}
 else{const B=boardList().slice(0,10),lab={hw:'hours watched',peak:'peak viewers',avg:'average viewers'}[sort],val=s=>sort==='hw'?fmt(s.hw)+'h':fmt(s[sort]);
  [c,x]=base('TOP STREAMERS',`${sc} // ${PERB[per]} // ${lab}`);const avs=await Promise.all(B.map(s=>loadImg(s.logo)));
  listRows(x,B.map(s=>({name:s.name,tag:`${(NAMES[s.platform]||'').toUpperCase()}${CAT?'':' // '+s.game}`,color:COL[s.platform],value:val(s)})),avs);
  text=`Top streamers, ${sc}, ${PERB[per]} by ${lab}: ${B.slice(0,3).map((s,i)=>`${i+1}. ${s.name} ${val(s)}`).join(' | ')}.`}
 return [c,text]}
async function openShare(type){if(!D)return;const mi=document.getElementById('mimg');mi.removeAttribute('src');mi.alt='Making the image...';cur=null;document.getElementById('mhint').textContent='';document.getElementById('modal').classList.add('on');
 const name=`${CAT||'india'}-${type}.png`,done=(b,text)=>{cur={blob:b,name,text};mi.src=URL.createObjectURL(b)};
 let [c,text]=await card(type);
 try{c.toBlob(b=>done(b,text),'image/png')}
 catch(e){LOGOS=false;[c,text]=await card(type);LOGOS=true;c.toBlob(b=>done(b,text),'image/png')}}   // a logo without CORS: redraw without logos
document.querySelectorAll('[data-share]').forEach(b=>b.onclick=()=>openShare(b.dataset.share));
document.getElementById('mclose').onclick=()=>document.getElementById('modal').classList.remove('on');
document.getElementById('modal').onclick=e=>{if(e.target.id==='modal')e.target.classList.remove('on')};
document.getElementById('mdl').onclick=()=>{if(!cur)return;const a=document.createElement('a');a.href=URL.createObjectURL(cur.blob);a.download=cur.name;a.click()};
document.getElementById('mcp').onclick=()=>{try{navigator.clipboard.writeText(PAGEURL)}catch(e){}document.getElementById('mhint').textContent='Link copied: '+PAGEURL};
async function shareTo(app){if(!cur)return;const f=new File([cur.blob],cur.name,{type:'image/png'}),t=cur.text+' '+PAGEURL+' @letsgrowesports';
 if(/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)&&navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){if(e&&e.name==='AbortError')return}}
 document.getElementById('mdl').click();
 if(app==='x')window.open('https://x.com/intent/post?text='+encodeURIComponent(cur.text+' '+PAGEURL+' via @letsgrowesports'),'_blank','noopener');
 else{window.open('https://www.instagram.com/','_blank','noopener');document.getElementById('mhint').textContent='Image downloaded. Upload it as a post or story on Instagram.'}}
document.getElementById('mig').onclick=()=>shareTo('ig');document.getElementById('mxb').onclick=()=>shareTo('x');
document.getElementById('q').oninput=e=>{q=e.target.value.trim().toLowerCase();render()};
async function load(){try{const r=await fetch('/api/scene?period='+per+(CAT?'&cat='+CAT:'')+'&t='+Math.floor(Date.now()/20000),{cache:'no-store'});D=await r.json();render()}catch(e){}}
async function loadLive(){if(!D||document.hidden)return;try{const r=await fetch('/api/scene/live'+(CAT?'?cat='+CAT:'')+(CAT?'&':'?')+'t='+Math.floor(Date.now()/2000),{cache:'no-store'});const j=await r.json();
 ['updated','fresh','india_total','live_total','live_count','platforms','categories','live'].forEach(k=>D[k]=j[k]);render()}catch(e){}}
load();setInterval(load,30000);setInterval(loadLive,2000);   // live numbers every 2s, rankings and charts every 30s
setInterval(()=>{if(!D)return;const a=Math.round(Date.now()/1000-D.updated);document.getElementById('upd').textContent=D.updated?(a<90?a+'s ago':Math.round(a/60)+' min ago'):'-';
 document.querySelectorAll('.ev .v[data-ns]').forEach(e=>{if(e.dataset.ns)e.textContent=cdTxt(+e.dataset.ns)})},1000);
</script></body></html>"""


def build_html(cat: str = "", cat_name: str = "") -> str:
    if cat:
        title = f"{cat_name} live in India: top streamers and viewers"
        desc = f"Every {cat_name} live stream in India on YouTube, Kick and Twitch, ranked by viewers and hours watched."
    else:
        title = "India Live Streaming Rankings"
        desc = ("Who is live in India right now on YouTube, Kick and Twitch, by game and category (BGMI, Free Fire, "
                "news and more), and who leads today, this week and this month.")
    return (PAGE.replace("__TITLE__", html.escape(title)).replace("__DESC__", html.escape(desc))
                .replace("__CATNAME__", json.dumps(cat_name)).replace("__CAT__", json.dumps(cat))
                .replace("__BRAND__", html.escape(eventpage.BRAND))
                .replace("__SOCIAL__", " // ".join(f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener">{html.escape(h)}</a>'
                                                     for _, u, h in eventpage.SOCIAL)))
