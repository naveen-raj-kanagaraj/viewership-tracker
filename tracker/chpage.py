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
.rks{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.rk{background:var(--card);border:1px solid var(--line);padding:5px 10px;font-size:12px;color:var(--muted);text-decoration:none}
.rk b{font:700 17px "Barlow Condensed",sans-serif;color:var(--ink);margin-right:4px}.rk.g1 b{color:#ffd23f}.rk.g2 b{color:#d9dde8}.rk.g3 b{color:#ff9f5a}.rk:hover{border-color:var(--lime)}
.vk{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:12px 16px 0}.vk div{background:var(--card2);padding:10px 12px;font-size:12px;color:var(--muted)}
.vk b{display:block;font:700 24px "Barlow Condensed",sans-serif;color:var(--ink)}.vk b.up{color:var(--lime)}
.vseg{display:inline-flex;border:1px solid var(--line);margin:12px 16px 0}.vseg button{background:none;border:0;color:var(--muted);font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.04em;padding:6px 10px;cursor:pointer}.vseg button.on{background:var(--lime);color:#0b0b12}
#vchart{display:block;width:calc(100% - 32px);height:200px;margin:10px 16px 0}
.vtools{display:flex;flex-wrap:wrap;gap:0 8px}.vtools .vseg{margin-right:0}
#vidchart{display:block;width:calc(100% - 32px);height:260px;margin:12px 16px 0;cursor:crosshair}
.vtip{position:fixed;pointer-events:none;background:rgba(18,18,25,.96);border:1px solid var(--line);padding:6px 9px;font-size:12px;max-width:280px;display:none;z-index:50}
.vtip b{font:700 15px "Barlow Condensed",sans-serif}
.vl a,.vl .hdr{grid-template-columns:70px minmax(0,1fr) 70px 64px 70px 60px 60px!important}
.vhead{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding-right:16px}.vhead .btn{margin-top:14px;flex:none}
.vk.life div{background:linear-gradient(160deg,rgba(124,92,255,.16),var(--card2) 70%)}.vk.life b{font-size:28px}
.ins{display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:8px;padding:12px 16px 0}.ins>div{background:var(--card2);padding:10px 12px;font-size:12px;color:var(--muted)}
.ins h4{margin:0 0 6px;font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.05em;color:var(--red);text-transform:uppercase}
.wk{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;align-items:end;height:64px}.wk span{display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;font-size:10px}
.wk i{display:block;width:100%;background:#4a3a9a;border-radius:2px 2px 0 0}.wk span.best i{background:var(--lime)}.wk span.best{color:var(--lime)}
.fr{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1c1c29}.fr b{color:var(--ink);font:600 14px "Barlow Condensed",sans-serif}
.xm{color:var(--lime)}
.lvtag{color:var(--red);font:600 10px "Barlow Condensed",sans-serif;margin-right:4px;letter-spacing:.04em}
.vm{padding:8px 16px 16px;display:flex;flex-wrap:wrap;gap:6px}.vm span{background:var(--card2);padding:5px 9px;font-size:12px;color:var(--muted)}.vm b{color:var(--ink);font-weight:600}
__PANEL_CSS__
@media(max-width:640px){#vidchart{height:210px}.vtools{gap:0}.vseg button{padding:6px 8px;font-size:11px}.vk b{font-size:20px}.vk div{padding:8px 10px}
.ins{grid-template-columns:1fr;padding:10px 12px 0}.vhead{padding-right:12px}.vk.life b{font-size:22px}
#vidchart{width:calc(100% - 24px);margin:10px 12px 0;height:180px}.vtools{padding:0}
.vl a,.vl .hdr{grid-template-columns:52px minmax(0,1fr) 58px 44px!important}.vl a>:nth-child(n+4):not(:last-child),.vl .hdr>:nth-child(n+4):not(:last-child){display:none}
.vk{grid-template-columns:repeat(2,1fr);padding:10px 12px 0}.vk div:last-child{grid-column:1/-1}#vchart{width:calc(100% - 24px);margin:10px 12px 0;height:170px}.vseg{margin:10px 12px 0}.vm{padding:8px 12px 12px}
.wrap{padding:0 12px 20px}.top .in{padding:9px 12px}.brand{font-size:15px}.nav{display:none}
.hd .act{display:flex;gap:8px}.hd .act .btn{flex:1}.hd{grid-template-columns:60px minmax(0,1fr);gap:12px}.hd img,.hd .ph{width:60px;height:60px}h1{font-size:28px}.hd .act{grid-column:1/-1}.hd .act .btn{width:100%;text-align:center}
.cx{padding:4px 12px 12px}.cxc{grid-template-columns:1fr}.cxt td{font-size:14px;padding:4px 3px}.cxt th{padding:4px 3px;font-size:10px}.cxd div{grid-template-columns:52px minmax(0,1fr) 64px 50px}.cxd div span:nth-child(5){display:none}
.ps{padding:4px 12px 12px}.ps a,.ps .hdr{grid-template-columns:62px minmax(0,1fr) 64px}.ps a>:nth-child(3),.ps .hdr>:nth-child(3),.ps a>:nth-child(5),.ps .hdr>:nth-child(5){display:none}}
.hd .act{grid-column:1/-1}.plats{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.plats>*{font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.05em;text-transform:uppercase;padding:5px 12px;border:1px solid;border-left-width:3px;text-decoration:none;color:var(--muted)}.plats .on{color:var(--ink);background:var(--card2)}.act{display:flex;gap:8px;flex-wrap:wrap}.btn.ghost{background:transparent;border:1px solid var(--line);color:var(--ink)}
.bopts{display:flex;flex-wrap:wrap;gap:6px;margin:12px 16px 0}.bopts button{background:var(--card2);border:1px solid var(--line);color:var(--muted);font:600 12px "Barlow Condensed",sans-serif;letter-spacing:.03em;padding:6px 10px;cursor:pointer;text-align:left}.bopts button.on{border-color:var(--lime);color:var(--ink)}.bopts b{color:var(--lime);margin-right:4px}
.bprev{margin:14px 16px 0;padding:18px;background:repeating-conic-gradient(#15151f 0 25%,#101018 0 50%) 0 0/16px 16px;border:1px solid var(--line);display:flex;justify-content:center;overflow:hidden}.bprev img{max-width:100%;height:auto;display:block}
.bcode{margin:4px 16px 16px}.bcode textarea{width:100%;margin-top:8px;background:#0b0b12;color:var(--ink);border:1px solid var(--line);font:12px ui-monospace,Menlo,monospace;padding:8px;resize:none}.brow{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
#vidcard.ld>:not(.vhead){display:none}#vidcard.ld .vhead .btn{display:none}#vidcard.ld .vhead{padding-bottom:16px}
</style></head><body>
<div class="top"><div class="in"><a class="brand" href="__HOME__">__BRAND__</a><span class="beta">BETA</span><span class="nav"><a href="__HOME__">DASHBOARD</a><a href="__RP__/rankings">RANKINGS</a><a href="/map">MAP</a></span></div></div>
<div class="wrap">
<div class="crumb"><a href="__HOME__">__WHERECAP__</a> / CHANNEL</div>
<div class="hd" id="hd"><span class="ph">..</span><div><h1>__NAME__</h1><div class="meta">Loading...</div></div></div>
<div class="card" id="vidcard" style="display:none"><div class="vhead"><div><h2>Channel performance</h2><div class="cap" id="vidcap"></div></div><button class="btn" id="vshare">SHARE</button></div>
 <div class="vk life" id="lifek"></div>
 <div class="vtools"><div class="vseg" id="vrange"></div><div class="vseg" id="vkind"></div><div class="vseg" id="vmetric"></div></div>
 <div class="vk" id="vidk"></div><canvas id="vidchart"></canvas><div class="vtip" id="vtip"></div>
 <div class="ins" id="vins"></div>
 <div class="ps" id="vidlist"></div></div>
<div id="smodal" style="position:fixed;inset:0;z-index:60;background:rgba(3,2,12,.85);display:none;align-items:center;justify-content:center;padding:16px"><div style="background:var(--bg2);border:1px solid var(--line);padding:14px;max-width:440px;width:100%;max-height:94vh;overflow:auto">
 <img id="simg" alt="Share card" style="width:100%;display:block;border:1px solid var(--line);margin-bottom:10px"><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" id="sgo">SHARE</button><button class="btn" id="sdl">DOWNLOAD</button><button class="btn" id="sx" style="background:none;color:var(--muted);border:1px solid var(--line)">CLOSE</button></div></div></div>
<div class="card" id="bcard" style="display:none"><div class="vhead"><div><h2>Creator badge</h2><div class="cap">A live badge for your website, link page or press kit. It updates itself as the rank changes. Pick which rank to show.</div></div></div>
 <div class="bopts" id="bopts"></div><div class="bprev"><img id="bimg" alt="Badge preview"></div>
 <div class="bcode"><div class="vseg" id="bfmt" style="margin:8px 0 0"></div><textarea id="btxt" readonly rows="3"></textarea><div class="brow"><button class="btn" id="bcopy">COPY CODE</button><button class="btn ghost" id="bpng">DOWNLOAD PNG</button></div></div></div>
<div class="card" id="vcard" style="display:none"><h2>Channel views per day</h2><div class="cap">The channel's public counters on YouTube (total views of all its videos, live and uploaded; subscribers), recorded once a day by this site. Views gained = how much the total grew between two days.</div><div id="views"></div></div>
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
let VR=30,VRANGE='30d',VKIND='all',VMET='views',VID=null,CDATA=null;
const RANGES=[['7d','7D'],['30d','30D'],['90d','90D'],['6m','6M'],['ytd','YTD'],['1y','1Y'],['all','ALL TIME']];
const KINDC={uploads:'#a58bff',shorts:'#4cc9f0',live:'#ff4d5e'},kindOf=v=>v.live?'live':v.short?'shorts':'uploads',KINDN={uploads:'Videos',shorts:'Shorts',live:'Live'};
const engOf=v=>v.likes!=null&&v.views?100*((v.likes||0)+(v.comments||0))/v.views:null;
const MET={views:['Views',v=>v.views||0,fmt],likes:['Likes',v=>v.likes||0,fmt],comments:['Comments',v=>v.comments||0,fmt],eng:['Engagement',v=>engOf(v)||0,v=>v.toFixed(1)+'%']};
const RNAME={'7d':'last 7 days','30d':'last 30 days','90d':'last 90 days','1w':'last week','1m':'last month','3m':'last 3 months','6m':'last 6 months','ytd':'this year','1y':'last 12 months','all':'all time'};
function renderLife(){const c=CDATA,j=VID;if(!c||!j)return;const S=c.stats||{},V=c.views||{},G=V.gains||[],sum=n=>G.filter(g=>g.day>=new Date(Date.now()-n*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'})).reduce((a,g)=>a+g.views,0);
 if(c.platform!=='youtube'){const sn=V.snapshots||[],f=(sn[sn.length-1]||{}).subs,fg=n=>G.filter(g=>g.subs!=null&&g.day>=new Date(Date.now()-n*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'})).reduce((a,g)=>a+g.subs,0),P=c.periods||{};
  document.getElementById('lifek').innerHTML=`<div><b>${f!=null?fmt(f):'-'}</b>followers</div><div><b class="up">${G.length?(fg(30)>=0?'+':'')+fmt(fg(30)):'-'}</b>followers, 30 days</div><div><b>${P.all&&P.all.peak?fmt(P.all.peak):'-'}</b>peak live viewers (this site)</div><div><b>${P['30d']?fmt(P['30d'].hw)+'h':'-'}</b>hours watched, 30 days</div><div><b>${full(j.count)}</b>broadcasts listed</div>`;return}
 document.getElementById('lifek').innerHTML=`<div><b>${S.views!=null?fmt(S.views):'-'}</b>lifetime views</div><div><b>${S.subs!=null?fmt(S.subs):'hidden'}</b>subscribers</div><div><b>${S.videos!=null?full(S.videos):'-'}</b>videos, lifetime</div>${G.length?`<div><b class="up">+${fmt(sum(30))}</b>channel views, ${G.length>=30?'30 days':'since '+dshortD(V.first)}</div><div><b class="up">+${fmt((G[G.length-1]||{}).views||0)}</b>channel views, last day</div>`:RVo(V)}`}
function RVo(V){const R=V.recent||{};if(R.views==null)return `<div><b>...</b>channel views per day: first readings taken, the next one within the hour</div>`;
 const h=R.hours>=1?Math.round(R.hours)+' hours':Math.round(R.hours*60)+' min';
 return `<div><b class="up">+${fmt(R.views)}</b>channel views, last ${h}</div>${R.hours>=3?`<div><b class="up">~+${fmt(R.views*24/R.hours)}</b>per day at this pace (estimate)</div>`:''}`}
const YT=SID.startsWith('yt:'),VURL=v=>v.url||'https://www.youtube.com/watch?v='+v.vid;
async function videos(){try{const j=await (await fetch(`/api/videos?sid=${encodeURIComponent(SID)}&range=${VRANGE}&kind=${VKIND}`)).json();VID=j;
 const box=document.getElementById('vidcard');if(!j.oldest){if(j.loading&&(window._vp=(window._vp||0)+1)<40){box.style.display='';box.classList.add('ld');document.getElementById('vidcap').textContent='Reading every video, Short and live stream of this channel from '+(YT?'YouTube':NAMES[CDATA?CDATA.platform:'twitch']||'the platform')+'. This takes a few seconds the first time.';setTimeout(videos,4000)}else box.style.display='none';return}box.style.display='';box.classList.remove('ld');renderLife();
 if(!YT){document.getElementById('vidcap').textContent=`Past broadcasts, highlights and uploads as ${NAMES[CDATA?CDATA.platform:'twitch']||''} lists them, with their total views (replays included). ${SID.startsWith('twitch')?'Twitch keeps past broadcasts for 7 to 60 days, so older streams only show if saved as highlights.':"Read from kick.com's public data (unofficial)."} Likes and comments aren't published.`}else
 document.getElementById('vidcap').textContent=`Lifetime numbers are the channel's own counters. Below: every video, Short and live stream posted in the range, with its totals so far (YouTube, refreshed every 6 hours). Premieres count as videos.`+(j.exact?'':' Dates are approximate ("3 weeks ago") and likes and comments need a YouTube API key on the server.');
 const sg=(id,opts,cur,on)=>{const e=document.getElementById(id);e.innerHTML=opts.map(([v,l])=>`<button data-v="${v}" class="${v===cur?'on':''}">${l}</button>`).join('');e.onclick=ev=>{const b=ev.target.closest('button');if(b)on(b.dataset.v)}};
 sg('vrange',RANGES,VRANGE,v=>{VRANGE=v;videos()});
 sg('vkind',YT?[['all','ALL'],['uploads','VIDEOS'],['shorts','SHORTS'],['live','LIVE']]:[['all','ALL'],['live','PAST BROADCASTS'],['uploads','HIGHLIGHTS & UPLOADS']],VKIND,v=>{VKIND=v;videos()});
 if(YT)sg('vmetric',[['views','VIEWS'],['likes','LIKES'],['comments','COMMENTS'],['eng','ENGAGEMENT']],VMET,v=>{VMET=v;drawVids();topList()});else{VMET='views';document.getElementById('vmetric').style.display='none'}
 document.getElementById('vidk').innerHTML=`<div><b>${full(j.count)}</b>posted, ${RNAME[VRANGE]} · ${j.per_week}/week</div><div><b class="up">${fmt(j.views)}</b>views on them</div><div><b>${fmt(j.avg)}</b>average per post</div><div><b>${fmt(j.median)}</b>median per post</div><div><b>${j.engagement!=null?j.engagement+'%':'-'}</b>engagement${j.likes!=null?` · ${fmt(j.likes)} likes · ${fmt(j.comments)} comments`:''}</div>`;
 document.getElementById('vidk').insertAdjacentHTML('beforeend',`<div style="grid-column:1/-1;background:none;padding:0 2px">${j.bucket&&j.bucket!=='post'?`Chart: average per post, by ${j.bucket}; purple bars = posts that ${j.bucket}.`:'Chart: one point per post.'}${j.loading?' <span style="color:var(--lime)">Pulling the full history from '+(YT?'YouTube':NAMES[CDATA?CDATA.platform:'twitch'])+'... updates by itself.</span>':''}</div>`);
 drawVids();insights();topList();
 clearTimeout(window._vpoll);if(j.loading)window._vpoll=setTimeout(videos,6000)}catch(e){}}
function topList(){const j=VID;if(!j)return;const m=MET[VMET],med=j.median||1;
 const L=(j.videos||[]).slice().sort((a,b)=>m[1](b)-m[1](a)).slice(0,15);
 document.getElementById('vidlist').className='ps vl';
 document.getElementById('vidlist').innerHTML=L.length?`<div class="hdr"><span>POSTED</span><span>TOP BY ${m[0].toUpperCase()}</span><span>VIEWS</span><span>LIKES</span><span>COMMENTS</span><span>ENGAGE</span><span>VS MEDIAN</span></div>${L.map(v=>`<a href="${esc(VURL(v))}" target="_blank" rel="noopener"><span class="d">${v.ts?(v.approx?'~':'')+ist(v.ts,{day:'numeric',month:'short'}):''}</span><span class="t"><span class="lvtag" style="color:${KINDC[kindOf(v)]}">${KINDN[kindOf(v)].toUpperCase()}</span>${esc(v.title)}</span><span class="n">${fmt(v.views)}</span><span class="n">${v.likes!=null?fmt(v.likes):'-'}</span><span class="n">${v.comments!=null?fmt(v.comments):'-'}</span><span class="n">${engOf(v)!=null?engOf(v).toFixed(1)+'%':'-'}</span><span class="n ${(v.views||0)>=2*med?'xm':''}">${((v.views||0)/med).toFixed(1)}x</span></a>`).join('')}`:'<div class="empty">Nothing posted in this range.</div>'}
function insights(){const I=(VID&&VID.insights)||{},el=document.getElementById('vins');if(!I.weekday){el.innerHTML='';return}
 const DAYS=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],wd=I.weekday,mxw=Math.max(1,...DAYS.map(d=>(wd[d]||{}).avg||0)),bestD=DAYS.reduce((a,d)=>((wd[d]||{}).avg||0)>((wd[a]||{}).avg||0)?d:a,'Mon');
 const hs=Object.entries(I.time||{}).sort((a,b)=>b[1].avg-a[1].avg),fm=I.format||{};
 el.innerHTML=`<div><h4>Best day to post</h4><div class="wk">${DAYS.map(d=>`<span class="${d===bestD?'best':''}" title="${(wd[d]||{}).n||0} posts"><i style="height:${Math.max(3,58*(((wd[d]||{}).avg||0)/mxw))}px"></i>${d[0]}${d[1]}</span>`).join('')}</div><div style="margin-top:6px">${bestD}: <b style="color:var(--ink)">${fmt((wd[bestD]||{}).avg)}</b> average views (IST)</div></div>
  <div><h4>Best time to post (IST)</h4>${hs.slice(0,4).map(([k,o],i)=>`<div class="fr"><span${i?'':' style="color:var(--lime)"'}>${k} · ${o.n}</span><b>${fmt(o.avg)}</b></div>`).join('')}</div>
  <div><h4>Average views by format</h4>${['uploads','shorts','live'].filter(k=>fm[k]).map(k=>`<div class="fr"><span style="color:${KINDC[k]}">${KINDN[k]} (${fm[k].n})</span><b>${fmt(fm[k].avg)}</b></div>`).join('')}</div>`}
const dlab=(t,span)=>new Date(t*1000).toLocaleDateString('en-IN',span>300*86400?{month:'short',year:'2-digit'}:{day:'numeric',month:'short'});
function drawVids(){const cv=document.getElementById('vidchart'),j=VID;if(!cv||!j)return;const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;const x=cv.getContext('2d');x.scale(dpr,dpr);
 const m=MET[VMET],B=j.bucket&&j.bucket!=='post',PH=W<520,t0=j.since,t1=Date.now()/1000,span=t1-t0,pt=14,pb=PH?20:24,pr=PH?44:54;
 // per post, or per week/month: average per post in that bucket
 const pv=B?{views:z=>z.avg,likes:z=>z.likes/z.posts,comments:z=>z.comments/z.posts,eng:z=>z.eng||0}[VMET]:m[1];
 const L=B?(j.series||[]):(j.videos||[]).filter(v=>v.ts).slice().sort((a,b)=>a.ts-b.ts);
 const vals=L.map(pv),mx=Math.max(1e-9,...vals)*1.15,X=t=>(W-pr)*(t-t0)/(t1-t0||1),Y=v=>pt+(H-pt-pb)*(1-v/mx);
 x.font=`${PH?10:11}px "Barlow Condensed",sans-serif`;x.strokeStyle='#262636';x.fillStyle='#8d8ca3';x.lineWidth=1;
 for(let i=0;i<=3;i++){const y=pt+(H-pt-pb)*i/3;x.beginPath();x.moveTo(0,y);x.lineTo(W-pr,y);x.stroke();x.fillText(m[2](mx*(1-i/3)),W-pr+4,y+4)}
 const nt=PH?3:6;for(let i=0;i<=nt;i++){const t=t0+span*i/nt;x.textAlign=i===0?'left':i===nt?'right':'center';x.fillText(dlab(t,span),X(t),H-5)}x.textAlign='left';
 if(!L.length){x.fillText('Nothing posted in this range.',10,H/2);cv._pts=[];return}
 if(B){const mp=Math.max(1,...L.map(z=>z.posts)),bw=Math.max(1.5,(W-pr)/L.length*.6);x.fillStyle='rgba(165,139,255,.18)';L.forEach(z=>{const h=(H-pt-pb)*.22*z.posts/mp;x.fillRect(X(z.ts)-bw/2,H-pb-h,bw,h)})}
 const P=L.map(v=>[X(v.ts),Y(pv(v)),v]);
 const path=()=>{x.beginPath();x.moveTo(P[0][0],P[0][1]);for(let i=1;i<P.length;i++){const a=P[i-1],b=P[i],cx=(a[0]+b[0])/2;x.bezierCurveTo(cx,a[1],cx,b[1],b[0],b[1])}};
 const g=x.createLinearGradient(0,pt,0,H-pb);g.addColorStop(0,'rgba(182,242,58,.28)');g.addColorStop(1,'rgba(182,242,58,0)');
 path();x.lineTo(P[P.length-1][0],H-pb);x.lineTo(P[0][0],H-pb);x.closePath();x.fillStyle=g;x.fill();
 path();x.strokeStyle='#b6f23a';x.lineWidth=PH?1.8:2.2;x.stroke();
 const sv=vals.slice().sort((a,b)=>a-b),md=sv[Math.floor(sv.length/2)];x.setLineDash([4,4]);x.strokeStyle='rgba(165,139,255,.6)';x.beginPath();x.moveTo(0,Y(md));x.lineTo(W-pr,Y(md));x.stroke();x.setLineDash([]);
 x.fillStyle='#a58bff';x.fillText('median '+m[2](md),4,Y(md)-4);
 const bi=vals.indexOf(Math.max(...vals)),dots=P.length<=(PH?40:70);
 P.forEach((p,i)=>{if(!dots&&i!==bi)return;x.beginPath();x.arc(p[0],p[1],i===bi?5:3,0,7);x.fillStyle=i===bi?'#b6f23a':B?'#a58bff':KINDC[kindOf(p[2])];x.fill();x.strokeStyle='#0b0b12';x.lineWidth=1.5;x.stroke()});
 const b=P[bi],right=b[0]>W-pr-110;x.font='700 12px "Barlow Condensed",sans-serif';x.fillStyle='#b6f23a';x.textAlign=right?'right':'left';x.fillText('BEST '+m[2](vals[bi]),b[0]+(right?-8:8),Math.max(12,b[1]-8));x.textAlign='left';
 cv._pts=P;const tip=document.getElementById('vtip');
 const near=e=>{const r=cv.getBoundingClientRect(),mx_=e.clientX-r.left;let best=null,d=1e9;for(const p of cv._pts){const dd=Math.abs(p[0]-mx_);if(dd<d){d=dd;best=p}}return d<30?best:null};
 const show=(e,p)=>{if(!p){tip.style.display='none';return}const v=p[2];
  tip.innerHTML=B?`${j.bucket==='month'?'Month of':'Week of'} ${new Date(v.ts*1000).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}<br><b>${v.posts}</b> posts · <b>${fmt(v.views)}</b> views · ${fmt(v.avg)} per post${v.eng!=null?' · '+v.eng+'%':''}`
   :`<span class="lvtag" style="color:${KINDC[kindOf(v)]}">${KINDN[kindOf(v)].toUpperCase()}</span>${esc(v.title)}<br><b>${fmt(v.views)}</b> views${v.likes!=null?' · '+fmt(v.likes)+' likes · '+fmt(v.comments)+' comments':''}${engOf(v)!=null?' · '+engOf(v).toFixed(1)+'%':''}<br>${v.approx?'~':''}${ist(v.ts,{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})} IST`;
  tip.style.display='block';tip.style.left=Math.min(e.clientX+12,innerWidth-290)+'px';tip.style.top=(e.clientY+12)+'px'};
 cv.onmousemove=e=>show(e,near(e));cv.onmouseleave=()=>{tip.style.display='none'};
 cv.onclick=e=>{const p=near(e);if(!p)return;if(B||matchMedia('(hover:none)').matches&&tip.style.display!=='block'){show(e,p);return}window.open(VURL(p[2]),'_blank','noopener')}}
window.addEventListener('resize',()=>{drawVids();if(CDATA)viewsCard(CDATA)});
// ---- share card: the channel's performance as an image
function loadImg(u){return new Promise(r=>{if(!u)return r(null);const i=new Image();i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(null);i.src=u})}
async function shareCard(withLogo){const c=CDATA,j=VID,S=(c&&c.stats)||{};const cv=document.createElement('canvas');cv.width=2160;cv.height=2700;const x=cv.getContext('2d');x.scale(2,2);
 x.fillStyle='#0b0b12';x.fillRect(0,0,1080,1350);const g=x.createRadialGradient(860,-60,10,860,-60,720);g.addColorStop(0,'rgba(124,92,255,.24)');g.addColorStop(1,'rgba(124,92,255,0)');x.fillStyle=g;x.fillRect(0,0,1080,1350);
 x.fillStyle='#b6f23a';x.font='700 30px "Barlow Condensed",sans-serif';x.fillText('LETSGROWESPORTS',72,96);
 const im=withLogo?await loadImg(c.logo):null;let tx=72;if(im){x.save();x.beginPath();x.arc(132,190,60,0,7);x.clip();x.drawImage(im,72,130,120,120);x.restore();tx=220}
 x.fillStyle='#fff';x.font='700 64px "Barlow Condensed",sans-serif';let n=c.name.toUpperCase();while(x.measureText(n).width>1008-tx&&n.length>3)n=n.slice(0,-2);x.fillText(n,tx,195);
 x.fillStyle='#8d8ca3';x.font='28px "Barlow Condensed",sans-serif';x.fillText(`YOUTUBE · ${RNAME[VRANGE].toUpperCase()}${VKIND!=='all'?' · '+KINDN[VKIND].toUpperCase():''}`,tx,240);
 const T=[['LIFETIME VIEWS',S.views!=null?fmt(S.views):'-'],['SUBSCRIBERS',S.subs!=null?fmt(S.subs):'-'],['POSTED',full(j.count)],['VIEWS ON THEM',fmt(j.views)],['AVG PER POST',fmt(j.avg)],['ENGAGEMENT',j.engagement!=null?j.engagement+'%':'-']];
 T.forEach(([l,v],i)=>{const X0=72+(i%3)*316,Y0=290+Math.floor(i/3)*170;x.fillStyle='#13131c';x.fillRect(X0,Y0,300,150);x.fillStyle='#ff4d5e';x.font='22px "Barlow Condensed",sans-serif';x.fillText(l,X0+22,Y0+38);x.fillStyle='#fff';x.font='700 64px "Barlow Condensed",sans-serif';x.fillText(v,X0+22,Y0+112)});
 x.fillStyle='#ff4d5e';x.font='24px "Barlow Condensed",sans-serif';x.fillText(MET[VMET][0].toUpperCase()+' PER POST',72,670);
 const L=(j.videos||[]).filter(v=>v.ts).slice().sort((a,b)=>a.ts-b.ts),m=MET[VMET],vals=L.map(m[1]),mx=Math.max(1e-9,...vals)*1.12,t0=j.since,t1=Date.now()/1000,CX=72,CY=690,CW=936,CH_=330;
 const PX=t=>CX+CW*(t-t0)/(t1-t0),PY=v=>CY+CH_*(1-v/mx);
 x.strokeStyle='#262636';x.lineWidth=1;for(let i=0;i<=3;i++){const y=CY+CH_*i/3;x.beginPath();x.moveTo(CX,y);x.lineTo(CX+CW,y);x.stroke()}
 if(L.length){const P=L.map(v=>[PX(v.ts),PY(m[1](v))]);const path=()=>{x.beginPath();x.moveTo(P[0][0],P[0][1]);for(let i=1;i<P.length;i++){const a=P[i-1],b=P[i],cx=(a[0]+b[0])/2;x.bezierCurveTo(cx,a[1],cx,b[1],b[0],b[1])}};
  const gg=x.createLinearGradient(0,CY,0,CY+CH_);gg.addColorStop(0,'rgba(182,242,58,.35)');gg.addColorStop(1,'rgba(182,242,58,0)');path();x.lineTo(P[P.length-1][0],CY+CH_);x.lineTo(P[0][0],CY+CH_);x.closePath();x.fillStyle=gg;x.fill();
  path();x.strokeStyle='#b6f23a';x.lineWidth=4;x.stroke()}
 const best=L.reduce((a,v)=>(v.views||0)>((a&&a.views)||0)?v:a,null);
 if(best){x.fillStyle='#13131c';x.fillRect(72,1060,936,150);x.fillStyle='#ff4d5e';x.font='22px "Barlow Condensed",sans-serif';x.fillText('TOP POST',96,1098);
  x.fillStyle='#fff';x.font='600 32px "Barlow",sans-serif';let t=best.title;while(x.measureText(t).width>660&&t.length>3)t=t.slice(0,-2);if(t!==best.title)t+='…';x.fillText(t,96,1145);
  x.fillStyle='#b6f23a';x.font='700 56px "Barlow Condensed",sans-serif';x.textAlign='right';x.fillText(fmt(best.views),984,1160);x.font='22px "Barlow Condensed",sans-serif';x.fillStyle='#8d8ca3';x.fillText('VIEWS',984,1190);x.textAlign='left'}
 x.fillStyle='#8d8ca3';x.font='26px "Barlow Condensed",sans-serif';x.fillText((location.host+location.pathname),72,1290);x.textAlign='right';x.fillText(new Date().toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}),1008,1290);x.textAlign='left';
 return new Promise(r=>{try{cv.toBlob(r,'image/png')}catch(e){r(null)}})}
let SBLOB=null;
document.getElementById('vshare').onclick=async()=>{if(!VID||!CDATA)return;try{await document.fonts.ready}catch(e){}SBLOB=await shareCard(true)||await shareCard(false);if(!SBLOB)return;
 document.getElementById('simg').src=URL.createObjectURL(SBLOB);document.getElementById('smodal').style.display='flex'};
document.getElementById('sx').onclick=()=>document.getElementById('smodal').style.display='none';
document.getElementById('sdl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(SBLOB);a.download=(CDATA.name||'channel').replace(/\W+/g,'-')+'.png';a.click()};
document.getElementById('sgo').onclick=async()=>{const f=new File([SBLOB],'channel.png',{type:'image/png'}),t=`${CDATA.name}: ${fmt(VID.views)} views on ${VID.count} posts, ${RNAME[VRANGE]}. ${location.href} @letsgrowesports`;
 if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){}}document.getElementById('sdl').click()};
function viewsCard(c){const V=c.views,S=c.stats;const box=document.getElementById('vcard');if(!V||!(V.snapshots||[]).length){box.style.display='none';return}box.style.display='';
 if(c.platform!=='youtube')return followersCard(c);
 const G=V.gains||[],sum=n=>G.filter(g=>g.day>=new Date(Date.now()-n*864e5).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'})).reduce((a,g)=>a+g.views,0),last=G[G.length-1];
 const sg=G.filter(g=>g.subs!=null).slice(-7).reduce((a,g)=>a+g.subs,0);
 const RV=V.recent||{},snap=(V.snapshots||[])[V.snapshots.length-1]||{},tv=(S&&S.views)||snap.views;
 const fh=h=>h>=1?Math.round(h)+(Math.round(h)===1?' hour':' hours'):Math.round(h*60)+' min';
 document.getElementById('views').innerHTML=`<div class="vk"><div><b>${tv!=null?fmt(tv):'-'}</b>total views, lifetime</div>${!last&&RV.views!=null?`<div><b class="up">+${fmt(RV.views)}</b>views, last ${fh(RV.hours)}</div>`:''}<div><b class="up">${last?'+'+fmt(last.views):'-'}</b>views, last day</div><div><b class="up">${G.length?'+'+fmt(sum(7)):'-'}</b>views, 7 days</div><div><b class="up">${G.length?'+'+fmt(sum(30)):'-'}</b>views, 30 days${G.length?'':''}</div></div>
  ${G.length?`<div class="vseg" id="vseg">${[[7,'1W'],[30,'1M'],[91,'3M'],[182,'6M'],[Math.ceil((Date.now()-new Date(new Date().getFullYear(),0,1))/864e5),'YTD'],[365,'1Y']].map(([v,l])=>`<button data-v="${v}" class="${v===VR?'on':''}">${l}</button>`).join('')}</div><canvas id="vchart"></canvas>
  <div class="vm">${(V.months||[]).slice(-6).map(m=>`<span>${new Date(m.month+'-15').toLocaleDateString('en-IN',{month:'short',year:'numeric'})} <b>+${fmt(m.views)}</b> views</span>`).join('')}${sg?`<span>Subscribers, 7 days <b>${sg>=0?'+':''}${fmt(sg)}</b></span>`:''}<span>Recorded since ${dshortD(V.first)}</span></div>`
  :`<div class="empty">${RV.views!=null?`+${full(RV.views)} views in the last ${fh(RV.hours)}${RV.subs?` and ${RV.subs>0?'+':''}${full(RV.subs)} subscribers`:''}, from readings this site took since ${ist(RV.since,{hour:'numeric',minute:'2-digit'})} IST.`:`First reading taken ${RV.since?ist(RV.since,{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})+' IST':dshortD(V.first)}. The next one is taken within the hour, then views gained show here.`} YouTube doesn't publish a channel's past daily views, so per-day history starts from the day this site began following the channel; tomorrow the daily, weekly and monthly totals start.</div>`}`;
 if(!last&&RV.views==null&&!window._rvp){window._rvp=1;setTimeout(()=>{window._rvp=0;load()},60000)}
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
 const S=G.slice(-VR),pt=10,pb=22,pr=50,mx=Math.max(1,...S.map(g=>g.views))*1.15,n=Math.max(S.length-1,1),X=i=>(W-pr)*i/n,Y=v=>pt+(H-pt-pb)*(1-v/mx);
 x.font='11px "Barlow Condensed",sans-serif';x.fillStyle='#8d8ca3';x.strokeStyle='#262636';x.lineWidth=1;
 for(let i=0;i<=3;i++){const y=pt+(H-pt-pb)*i/3;x.beginPath();x.moveTo(0,y);x.lineTo(W-pr,y);x.stroke();x.fillText('+'+fmt(mx*(1-i/3)),W-pr+4,y+4)}
 if(!S.length)return;const P=S.map((g,i)=>[S.length===1?(W-pr)/2:X(i),Y(g.views)]),best=S.reduce((a,g,i)=>g.views>S[a].views?i:a,0);
 const path=()=>{x.beginPath();x.moveTo(P[0][0],P[0][1]);for(let i=1;i<P.length;i++){const a=P[i-1],b=P[i],cx=(a[0]+b[0])/2;x.bezierCurveTo(cx,a[1],cx,b[1],b[0],b[1])}};
 const g=x.createLinearGradient(0,pt,0,H-pb);g.addColorStop(0,'rgba(165,139,255,.35)');g.addColorStop(1,'rgba(165,139,255,0)');
 path();x.lineTo(P[P.length-1][0],H-pb);x.lineTo(P[0][0],H-pb);x.closePath();x.fillStyle=g;x.fill();path();x.strokeStyle='#a58bff';x.lineWidth=2.2;x.stroke();
 P.forEach((p,i)=>{if(i===best||i===P.length-1){x.beginPath();x.arc(p[0],p[1],4,0,7);x.fillStyle=i===best?'#b6f23a':'#eeeef5';x.fill();x.textAlign='center';x.fillText('+'+fmt(S[i].views),p[0],Math.max(10,p[1]-8));x.textAlign='left'}});
 S.forEach((g,i)=>{if(i%Math.ceil(S.length/7)===0||i===S.length-1){x.fillStyle='#8d8ca3';x.textAlign=i===0?'left':i===S.length-1?'right':'center';x.fillText(new Date(g.day+'T12:00:00+05:30').toLocaleDateString('en-IN',{day:'numeric',month:'short'}),P[i][0],H-6)}});x.textAlign='left'}
function rankBadges(c){const R=c.ranks||[];if(!R.length)return '';const yt_=c.platform==='youtube',ML={size:yt_?'subscribers':'followers',views:'total views',vday:yt_?'views today':'followers gained today',v7:yt_?'views, 7 days':'followers gained, 7 days',growth:yt_?'views, 30 days':'follower growth, 30 days',live:'live hours, 30 days'};
 const best={};R.forEach(r=>{const k=r.scope;if(!best[k]||r.rank/Math.max(r.of,1)<best[k].rank/Math.max(best[k].of,1))best[k]=r});
 const order=['country','category','game','world'].filter(k=>best[k]);
 return `<div class="rks" style="grid-column:1/-1">${order.map(k=>{const r=best[k],q=new URLSearchParams({mode:'channels',platform:c.platform,metric:r.metric,...(k==='country'?{country:c.country_code||''}:{}),...(k==='category'?{category:r.where}:{})});
  return `<a class="rk g${r.rank<=3?r.rank:0}" href="${RP}/rankings?${q}" title="${r.rank} of ${r.of} tracked ${NAMES[c.platform]} channels"><b>#${full(r.rank)}</b>${esc(r.where)} · ${ML[r.metric]} <span style="opacity:.7">of ${full(r.of)}</span></a>`}).join('')}</div>`}
const hm=s=>{s=+s||0;const h=Math.floor(s/3600),m=Math.round(s%3600/60);return h?`${h}h ${m}m`:`${m}m`};
async function load(){try{const c=await (await fetch('/api/channel?sid='+encodeURIComponent(SID)+'&t='+Math.floor(Date.now()/15000))).json();if(!c.sid)return;CH[SID]=c;
 const now=c.now,S=c.stats;
 document.getElementById('hd').className='hd'+(now?' live':'');
 document.getElementById('hd').innerHTML=`${av(c)}<div style="min-width:0"><h1>${esc(c.name)}</h1><div class="meta"><b style="color:${COL[c.platform]}">${NAMES[c.platform]||''}</b>${c.country?' · '+esc(c.country):''}${S&&S.subs!=null?' · <b>'+fmt(S.subs)+'</b> subscribers':''}${now||c.last_live?' · ':''}${now?`<span class="lv">LIVE</span><b>${full(now)}</b> watching${c.game?' · '+esc(c.game):''}`:c.last_live?'last live '+ago(c.last_live):''}</div>${now&&c.title?`<div class="meta" style="margin-top:6px">${esc(c.title)}</div>`:''}</div>
  ${rankBadges(c)}
  ${(c.linked||[]).length?`<div class="plats" style="grid-column:1/-1"><span class="on" style="border-color:${COL[c.platform]}">${NAMES[c.platform]}</span>${c.linked.map(l=>`<a href="${RP}/ch/${encodeURIComponent(l.sid)}" style="border-color:${COL[l.platform]||'#262636'}">${NAMES[l.platform]||l.platform}</a>`).join('')}</div>`:''}
  <div class="act"><a class="btn${now?' red':''}" href="${esc(c.url)}" target="_blank" rel="noopener">${now?'WATCH LIVE':'OPEN'} ON ${(NAMES[c.platform]||'').toUpperCase()}</a><a class="btn ghost" href="${RP}/compare?c=${encodeURIComponent([SID,...(c.linked||[]).map(l=>l.sid)].join(','))}">COMPARE</a></div>`;
 CDATA=c;viewsCard(c);renderLife();
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
const SITE=__SITEURL__;
async function badges(){try{const O=await (await fetch('/api/badges?sid='+encodeURIComponent(SID))).json();if(!O.length)return;
 document.getElementById('bcard').style.display='';let k=0,f='html';
 const url=o=>SITE+'/badge/'+SID+'.svg?m='+o.m+'&s='+o.s,page=SITE+RP+'/ch/'+SID,alt=o=>`Ranked #${o.rank} ${o.title} ${o.by}`;
 const code=o=>f==='html'?`<a href="${page}" target="_blank" rel="noopener"><img src="${url(o)}" alt="${esc(alt(o))}" height="80"></a>`:f==='md'?`[![${alt(o)}](${url(o)})](${page})`:page;
 const draw=()=>{const o=O[k];document.getElementById('bopts').innerHTML=O.slice(0,12).map((x,i)=>`<button data-i="${i}" class="${i===k?'on':''}"><b>#${full(x.rank)}</b>${esc(x.title)} · ${esc(x.by)}</button>`).join('');
  document.getElementById('bimg').src='/badge/'+SID+'.svg?m='+o.m+'&s='+o.s;
  const fe=document.getElementById('bfmt');fe.innerHTML=[['html','HTML'],['md','MARKDOWN'],['link','LINK']].map(([v,l])=>`<button data-v="${v}" class="${v===f?'on':''}">${l}</button>`).join('');
  document.getElementById('btxt').value=code(o)};
 document.getElementById('bopts').onclick=e=>{const b=e.target.closest('button');if(b){k=+b.dataset.i;draw()}};
 document.getElementById('bfmt').onclick=e=>{const b=e.target.closest('button');if(b){f=b.dataset.v;draw()}};
 document.getElementById('bcopy').onclick=async e=>{const t=document.getElementById('btxt');try{await navigator.clipboard.writeText(t.value)}catch(_){t.select();document.execCommand('copy')}e.target.textContent='COPIED';setTimeout(()=>e.target.textContent='COPY CODE',1500)};
 document.getElementById('bpng').onclick=()=>{const im=new Image();im.onload=()=>{const c=document.createElement('canvas'),s=3;c.width=im.naturalWidth*s;c.height=im.naturalHeight*s;const x=c.getContext('2d');x.scale(s,s);x.drawImage(im,0,0);
  c.toBlob(b=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=(CDATA&&CDATA.name||'badge').replace(/[^\w-]+/g,'_')+'_rank.png';a.click()},'image/png')};im.src=document.getElementById('bimg').src};
 draw()}catch(e){}}
load();past();moms();videos();badges();setInterval(()=>{if(!document.hidden)load()},15000);
</script></body></html>"""


def build_html(sid: str, name: str, region: str = "global") -> str:
    region = "in" if region == "in" else "global"
    return (PAGE.replace("__PANEL_JS__", scenepage.PANEL_JS).replace("__PANEL_CSS__", scenepage.PANEL_CSS)
            .replace("__NAME__", html.escape(name)).replace("__BRAND__", html.escape(eventpage.BRAND))
            .replace("__SID__", json.dumps(sid)).replace("__SITEURL__", json.dumps(eventpage.SITE_URL)).replace("__REGION__", json.dumps(region))
            .replace("__RP__", "/india" if region == "in" else "").replace("__HOME__", "/india" if region == "in" else "/")
            .replace("__WHERECAP__", "INDIA" if region == "in" else "WORLDWIDE"))
