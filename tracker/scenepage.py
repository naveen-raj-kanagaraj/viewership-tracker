"""/india: who is live in India right now on YouTube, Kick and Twitch, by game, and who leads over a day/week/month."""
import html

from tracker import eventpage

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>India Live Streaming Rankings | __BRAND__</title>
<meta name="description" content="Every Indian live stream we can find on YouTube, Kick and Twitch, by game and category, ranked by viewers and hours watched.">
<meta property="og:title" content="India Live Streaming Rankings | __BRAND__">
<meta property="og:description" content="Who is live in India right now on YouTube, Kick and Twitch, by game, and who leads today, this week and this month.">
<meta name="theme-color" content="#07051a">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#0b0b12;--card:#13131c;--card2:#1a1a26;--ink:#eeeef5;--muted:#8d8ca3;--line:#262636;
--lime:#b6f23a;--purple:#7c5cff;--red:#ff4d5e;--yt:#ff4d5e;--kick:#53fc18;--twitch:#a970ff}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Chakra Petch",system-ui,sans-serif}
body{background:radial-gradient(800px 380px at 80% -15%,rgba(124,92,255,.12),transparent 60%),var(--bg);min-height:100vh}
a{color:inherit}.wrap{max-width:1180px;margin:0 auto;padding:16px}
.mono,.lbl,.chip,th{font-family:"Share Tech Mono",monospace}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;padding:6px 0 14px;border-bottom:1px solid var(--line)}
.brand{color:var(--lime);font:14px "Share Tech Mono",monospace}h1{margin:2px 0 0;font-size:24px;letter-spacing:.02em}h1 span{color:var(--muted);font-weight:500}
.chip{font-size:12px;border:1px solid var(--line);padding:4px 9px;color:var(--muted)}.chip b{color:var(--ink);font-weight:400}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--red);margin-right:6px;box-shadow:0 0 8px var(--red)}
.card{background:var(--card);border:1px solid var(--line);padding:16px;margin-top:12px;min-width:0}
.lbl{color:var(--red);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
h2{margin:2px 0 0;font-size:18px}.muted{color:var(--muted)}.sub{color:var(--muted);font-size:12px}
.hero{display:grid;grid-template-columns:1.2fr 1fr;gap:12px}.big{font-size:56px;font-weight:700;line-height:1.05;margin-top:6px}
.bar{display:flex;height:10px;margin:14px 0 8px;background:var(--line);overflow:hidden}.bar div{height:100%}
.leg{display:flex;flex-wrap:wrap;gap:6px 16px;font:12px "Share Tech Mono",monospace;color:var(--muted)}.leg b{color:var(--ink);font-weight:400}
.sw{display:inline-block;width:9px;height:9px;margin-right:6px}
.grid{display:grid;grid-template-columns:360px 1fr;gap:12px}
.g{display:grid;grid-template-columns:22px 1fr auto;gap:2px 8px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line);cursor:pointer}
.g:last-child{border:0}.g .r{font:12px "Share Tech Mono",monospace;color:var(--muted)}.g .n{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.g .v{font:14px "Share Tech Mono",monospace}.g .s{grid-column:2/4;font-size:11px;color:var(--muted)}
.g .t{grid-column:2/4;height:3px;background:var(--line)}.g .t i{display:block;height:100%;background:var(--lime)}
.g.on .n{color:var(--lime)}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}
.seg{display:inline-flex;border:1px solid var(--line)}.seg button{background:none;border:0;color:var(--muted);font:12px "Share Tech Mono",monospace;padding:6px 10px;cursor:pointer}
.seg button.on{background:var(--lime);color:#0b0b12}
input,select{background:var(--card2);border:1px solid var(--line);color:var(--ink);font:13px "Share Tech Mono",monospace;padding:6px 9px;min-width:0}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;font-weight:400;color:#0b0b12;background:var(--lime);padding:6px 8px;white-space:nowrap}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:middle}.num{text-align:right;font-family:"Share Tech Mono",monospace;white-space:nowrap}
.who{display:flex;align-items:center;gap:8px;min-width:0}.who img,.who .ph{width:26px;height:26px;border-radius:50%;object-fit:cover;flex:none;background:var(--card2);border:1px solid var(--line)}
.nl{display:flex;align-items:center;min-width:0}.who .nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;display:block;text-decoration:none}.nl .pf{flex:none}
.who .tt{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:420px;display:block}
.pf{font:10px "Share Tech Mono",monospace;padding:0 5px;border:1px solid currentColor;margin-left:6px;vertical-align:1px}
.pf.youtube{color:var(--yt)}.pf.kick{color:var(--kick)}.pf.twitch{color:var(--twitch)}
.gm{font-size:12px;color:var(--muted);white-space:nowrap}.rk{font:13px "Share Tech Mono",monospace;color:var(--muted);width:30px}
.rk.t1{color:var(--lime)}.more{display:block;margin:10px auto 0;background:none;border:1px solid var(--line);color:var(--muted);font:12px "Share Tech Mono",monospace;padding:7px 14px;cursor:pointer}
.note{font-size:12px;color:var(--muted);margin-top:16px;line-height:1.6}.note b{color:var(--ink);font-weight:500}
.foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media(max-width:900px){.hero,.grid{grid-template-columns:1fr}.big{font-size:44px}.hide-m{display:none}.who .tt{max-width:200px}.who .nm{max-width:170px}}
@media(max-width:560px){.wrap{padding:12px}.card{padding:12px}td{padding:7px 4px}th{padding:6px 4px}.rk{width:22px}.num{font-size:13px}
.who{gap:6px}.who img,.who .ph{width:22px;height:22px}.who .nm{max-width:118px;font-size:14px}.who .tt{max-width:150px}.pf{margin-left:4px}
#bt .m{display:none}#bt.s-hw .c-hw,#bt.s-peak .c-peak,#bt.s-avg .c-avg{display:table-cell}}
</style></head><body><div class="wrap">
<header><div><div class="brand">__BRAND__</div><h1>INDIA LIVE <span>STREAMING RANKINGS</span></h1></div>
<div style="display:flex;gap:8px;flex-wrap:wrap"><span class="chip"><span class="dot"></span>YOUTUBE + KICK + TWITCH</span><span class="chip">UPDATED <b id="upd">-</b></span></div></header>
<div class="hero">
 <div class="card"><div class="lbl">// Watching now, India</div><div class="big mono" id="tot">-</div><div class="muted" id="cnt"></div>
  <div class="bar" id="pbar"></div><div class="leg" id="pleg"></div></div>
 <div class="card"><div class="lbl">// Biggest stream right now</div><div id="topone" style="margin-top:10px"></div></div>
</div>
<div class="grid">
 <div class="card"><div class="lbl">// Games &amp; categories, live now</div><div class="sub">Tap one to filter the streams.</div><div id="games" style="margin-top:8px"></div></div>
 <div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><div><div class="lbl">// Live now</div><h2 id="lh">Live streams</h2></div></div>
  <div class="tools"><div class="seg" id="plat"></div><select id="gsel"></select><input id="q" placeholder="Search streamer or title" style="flex:1;min-width:140px"></div>
  <div class="scroll"><table><thead><tr><th>#</th><th>STREAMER</th><th class="hide-m">CATEGORY</th><th class="num">VIEWERS</th></tr></thead><tbody id="live"></tbody></table></div>
  <button class="more" id="lmore"></button></div>
</div>
<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><div><div class="lbl">// Leaderboard</div><h2 id="bh">Top streamers</h2></div></div>
 <div class="tools"><div class="seg" id="per"></div><div class="seg" id="sort"></div><div class="seg" id="bplat"></div></div>
 <div class="scroll"><table id="bt" class="s-hw"><thead><tr><th>#</th><th>STREAMER</th><th class="hide-m">MAIN CATEGORY</th><th class="num m c-hw">HOURS WATCHED</th><th class="num m c-peak">PEAK</th><th class="num m c-avg">AVG</th><th class="num hide-m">AIRTIME</th></tr></thead><tbody id="board"></tbody></table></div>
 <button class="more" id="bmore"></button></div>
<div class="card"><div class="lbl">// Categories</div><h2 id="gh">Games &amp; categories by hours watched</h2>
 <div class="scroll" style="margin-top:12px"><table><thead><tr><th>#</th><th>CATEGORY</th><th class="num">HOURS WATCHED</th><th class="num">BIGGEST STREAM</th><th class="num hide-m">STREAMERS</th></tr></thead><tbody id="gboard"></tbody></table></div></div>
<div class="note" id="note"></div>
<div class="foot"><span>Unofficial rankings by __BRAND__. Not affiliated with YouTube, Kick or Twitch.</span><span>__SOCIAL__</span></div>
</div>
<script>
const NAMES={youtube:'YouTube',kick:'Kick',twitch:'Twitch'},COL={youtube:'var(--yt)',kick:'var(--kick)',twitch:'var(--twitch)'};
let D=null,per='today',sort='hw',plat='all',bplat='all',game='',q='',lAll=false,bAll=false;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>{n=+n||0;return n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'K':Math.round(n).toLocaleString('en-IN')};
const full=n=>Math.round(+n||0).toLocaleString('en-IN');
const ini=s=>esc((s||'?').replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase()||'?');
const who=(x,t)=>`<div class="who">${x.logo?`<img src="${esc(x.logo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ph></span>'">`:'<span class="ph"></span>'}<div style="min-width:0"><div class="nl"><a class="nm" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a><span class="pf ${esc(x.platform)}">${esc((NAMES[x.platform]||x.platform||'').toUpperCase())}</span></div>${t?`<span class="tt">${esc(t)}</span>`:''}</div></div>`;
function seg(id,opts,cur,on){const e=document.getElementById(id);e.innerHTML=opts.map(([v,l])=>`<button data-v="${v}" class="${v===cur?'on':''}">${l}</button>`).join('');e.onclick=ev=>{const b=ev.target.closest('button');if(b)on(b.dataset.v)}}
function render(){if(!D)return;
 const ago=Math.max(0,Math.round(Date.now()/1000-D.updated));document.getElementById('upd').textContent=D.updated?(ago<90?ago+'s ago':Math.round(ago/60)+' min ago'):'-';
 document.getElementById('tot').textContent=D.fresh?full(D.live_total):'-';
 document.getElementById('cnt').textContent=D.fresh?`across ${D.live_count} live streams`:'Waiting for the first scan (every '+D.every+'s)';
 const tot=D.live_total||1;document.getElementById('pbar').innerHTML=D.platforms.map(p=>`<div style="width:${100*p.viewers/tot}%;background:${COL[p.platform]}"></div>`).join('');
 document.getElementById('pleg').innerHTML=D.platforms.map(p=>`<span><span class="sw" style="background:${COL[p.platform]}"></span>${p.name.toUpperCase()} <b>${fmt(p.viewers)}</b> (${(100*p.viewers/tot).toFixed(0)}%)</span>`).join('');
 const t=D.live[0];document.getElementById('topone').innerHTML=t?`${who(t,t.title)}<div class="big mono" style="font-size:40px">${full(t.viewers)}</div><div class="muted">${esc(t.game)} // ${(100*t.viewers/tot).toFixed(1)}% of everyone watching</div>`:'<span class="muted">Nothing live in the last scan.</span>';
 const gm=D.games_live[0]?D.games_live[0].viewers:1;
 document.getElementById('games').innerHTML=D.games_live.map((g,i)=>`<div class="g${g.game===game?' on':''}" data-g="${esc(g.game)}"><span class="r">${i+1}</span><span class="n">${esc(g.game)}</span><span class="v">${fmt(g.viewers)}</span><span class="t"><i style="width:${100*g.viewers/gm}%"></i></span><span class="s">${g.streams} stream${g.streams>1?'s':''} // top: ${esc(g.top)}</span></div>`).join('')||'<span class="muted">No live games yet.</span>';
 document.querySelectorAll('.g').forEach(e=>e.onclick=()=>{game=game===e.dataset.g?'':e.dataset.g;lAll=false;render()});
 const gs=document.getElementById('gsel');gs.innerHTML='<option value="">All games &amp; categories</option>'+D.games_live.map(g=>`<option${g.game===game?' selected':''}>${esc(g.game)}</option>`).join('');
 seg('plat',[['all','ALL'],...['youtube','kick','twitch'].map(p=>[p,p.toUpperCase()])],plat,v=>{plat=v;lAll=false;render()});
 const L=D.live.filter(x=>(plat==='all'||x.platform===plat)&&(!game||x.game===game)&&(!q||(x.name+' '+x.title).toLowerCase().includes(q)));
 const ll=lAll||q?L:L.slice(0,25);
 document.getElementById('lh').textContent=`Live streams (${L.length})`;
 document.getElementById('live').innerHTML=ll.map((x,i)=>`<tr><td class="rk${i<3?' t1':''}">${i+1}</td><td>${who(x,x.title)}</td><td class="gm hide-m">${esc(x.game)}</td><td class="num">${full(x.viewers)}</td></tr>`).join('')||'<tr><td colspan=4 class="muted">Nothing live matches.</td></tr>';
 const lm=document.getElementById('lmore');lm.style.display=L.length>25&&!q?'block':'none';lm.textContent=lAll?'SHOW FEWER':`SHOW ALL ${L.length}`;lm.onclick=()=>{lAll=!lAll;render()};
 seg('per',[['today','TODAY'],['7d','7 DAYS'],['30d','30 DAYS']],per,v=>{per=v;bAll=false;load()});
 seg('sort',[['hw','HOURS WATCHED'],['peak','PEAK'],['avg','AVERAGE']],sort,v=>{sort=v;render()});
 seg('bplat',[['all','ALL'],...['youtube','kick','twitch'].map(p=>[p,p.toUpperCase()])],bplat,v=>{bplat=v;bAll=false;render()});
 document.getElementById('bt').className='s-'+sort;
 const B=D.board.filter(x=>bplat==='all'||x.platform===bplat).sort((a,b)=>b[sort]-a[sort]),bb=bAll?B:B.slice(0,25);
 document.getElementById('bh').textContent=`Top streamers, ${per==='today'?'today (IST)':per==='7d'?'last 7 days':'last 30 days'}`;
 document.getElementById('board').innerHTML=bb.map((x,i)=>`<tr><td class="rk${i<3?' t1':''}">${i+1}</td><td>${who(x)}</td><td class="gm hide-m">${esc(x.game)}</td><td class="num m c-hw">${fmt(x.hw)}h</td><td class="num m c-peak">${fmt(x.peak)}</td><td class="num m c-avg">${fmt(x.avg)}</td><td class="num hide-m">${x.airtime_h}h</td></tr>`).join('')||'<tr><td colspan=7 class="muted">No data for this period yet.</td></tr>';
 const bm=document.getElementById('bmore');bm.style.display=B.length>25?'block':'none';bm.textContent=bAll?'SHOW FEWER':`SHOW ALL ${B.length}`;bm.onclick=()=>{bAll=!bAll;render()};
 document.getElementById('gh').textContent=`Games & categories by hours watched, ${per==='today'?'today':per==='7d'?'last 7 days':'last 30 days'}`;
 document.getElementById('gboard').innerHTML=D.games.map((g,i)=>`<tr><td class="rk${i<3?' t1':''}">${i+1}</td><td><b>${esc(g.game)}</b></td><td class="num">${fmt(g.hw)}h</td><td class="num">${fmt(g.peak_stream)}</td><td class="num hide-m">${g.channels}</td></tr>`).join('')||'<tr><td colspan=5 class="muted">No data yet.</td></tr>';
 const miss=['kick','twitch'].filter(p=>!D.keys[p]).map(p=>NAMES[p]);
 document.getElementById('note').innerHTML=`<b>How this is counted.</b> Every ${Math.round(D.every/60)} minutes: YouTube's Live page for India and live searches for each game, language and category (news, devotional, music, cricket, talk), localised to India, plus hand-added channels; Kick and Twitch streams in ${esc(D.langs.join(', '))} plus hand-added channels. Viewers are each platform's own concurrent count; a channel streaming twice at once is added together; streams under ${D.min} viewers are left out. Games and categories come from the platform category (Kick, Twitch) or the stream title (YouTube); a title that names neither is Other. Hours watched = viewers x time live. <b>Not a census:</b> a stream that doesn't show up in these searches or languages is missed, so totals are a floor, not the whole of India.${miss.length?` ${miss.join(' and ')} language-wide discovery is off until API keys are added; only hand-added channels are counted there.`:''}`;
}
async function load(){try{const r=await fetch('/india/data?period='+per+'&t='+Math.floor(Date.now()/30000),{cache:'no-store'});D=await r.json();render()}catch(e){}}
document.getElementById('q').oninput=e=>{q=e.target.value.trim().toLowerCase();render()};
document.getElementById('gsel').onchange=e=>{game=e.target.value;lAll=false;render()};
load();setInterval(load,30000);setInterval(()=>{if(D)document.getElementById('upd').textContent=Math.round(Date.now()/1000-D.updated)<90?Math.round(Date.now()/1000-D.updated)+'s ago':Math.round((Date.now()/1000-D.updated)/60)+' min ago'},1000);
</script></body></html>"""


def build_html() -> str:
    return (PAGE.replace("__BRAND__", html.escape(eventpage.BRAND))
                .replace("__SOCIAL__", " // ".join(f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener">{html.escape(h)}</a>'
                                                     for _, u, h in eventpage.SOCIAL)))
