"""The PMGC 2026 Gauntlet Predict & Win page (/predict/pmgc). One static page (cached), everything personal comes
from /predict/pmgc/api/state. Phone first: bottom-sheet team picker with logos, sticky submit bar that only
enables when all 8 answers and the Instagram ID are in, draft kept in the browser so a refresh loses nothing."""
from tracker import eventpage

TITLE = "PMGC 2026 Gauntlet · Predict & Win"
DESC = "Call the 6 Grand Finals qualifiers, the Gauntlet #1, the top 3, chicken dinners and the peak viewership. Free to play."

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title><meta name="description" content="__DESC__"><meta name="theme-color" content="#07070b">
<meta property="og:type" content="website"><meta property="og:site_name" content="letsgrowesports"><meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__"><meta property="og:url" content="__SITE__/predict/pmgc"><meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet">
<style>
:root{color-scheme:dark;--bg:#07070b;--card:#0f0f16;--card2:#14141d;--line:#20202c;--mut:#8f8ea6;--ink:#f1f0f7;--lime:#b6f23a;--red:#ff4d5e;--gold:#f5c542}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Barlow,system-ui,-apple-system,"Segoe UI",sans-serif;padding-bottom:110px}
button{font:inherit;color:inherit}a{color:var(--lime)}
.top{border-bottom:1px solid var(--line);background:rgba(7,7,11,.92);backdrop-filter:blur(8px);position:sticky;top:0;z-index:20}
.top .in{max-width:760px;margin:0 auto;padding:11px 16px;display:flex;align-items:center;gap:10px}
.brand{color:var(--lime);font:700 17px "Barlow Condensed",sans-serif;letter-spacing:.06em;text-decoration:none;text-transform:uppercase}
.pill{font:700 11px "Barlow Condensed",sans-serif;letter-spacing:.08em;padding:2px 7px;border-radius:4px;background:var(--lime);color:#0b0b12;white-space:nowrap}
main{max-width:760px;margin:0 auto;padding:0 16px}
.hero{padding:26px 0 8px}.kick{font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.14em;color:var(--lime)}
h1{font:700 40px/1.02 "Barlow Condensed",sans-serif;letter-spacing:.01em;margin:6px 0 8px;text-transform:uppercase}h1 span{color:var(--lime)}
.facts{color:var(--mut);font-size:15px}.facts b{color:var(--ink);font-weight:600}
.lock{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0 4px;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:12px}
.lock .l{font:700 12px "Barlow Condensed",sans-serif;letter-spacing:.1em;color:var(--mut)}.lock b{font:700 26px "Barlow Condensed",sans-serif;font-variant-numeric:tabular-nums;color:var(--lime)}
.lock .w{color:var(--mut);font-size:12.5px;margin-left:auto;text-align:right;line-height:1.35}@media(max-width:480px){.lock .w{margin-left:0;text-align:left}}.lock.shut b{color:var(--red);font-size:20px}
.prize{color:var(--mut);font-size:13.5px;margin:10px 2px 0}
.prz{margin-top:12px;padding:16px;border-radius:14px;background:linear-gradient(135deg,rgba(182,242,58,.10),rgba(245,197,66,.07) 60%,rgba(165,139,255,.08));border:1px solid #2d3a17}
.pzh{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.pzw{font:700 13px "Barlow Condensed",sans-serif;letter-spacing:.14em;background:var(--gold);color:#2b1d00;padding:2px 8px;border-radius:5px}
.pzh b{font:700 22px "Barlow Condensed",sans-serif;letter-spacing:.01em}
.pzg{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}.pz{display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 6px;border-radius:12px;background:rgba(7,7,11,.55);border:1px solid #25252f;font-weight:700;font-size:13px;text-align:center}
@media(max-width:420px){.pzg{gap:6px}.pz{font-size:12px;padding:10px 4px}.pzh b{font-size:19px}}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:14px 0}
.gate h2{font:700 24px "Barlow Condensed",sans-serif;margin:0 0 6px;text-transform:uppercase}.gate p{color:var(--mut);margin:0 0 14px}
.gbtn{display:flex;align-items:center;justify-content:center;gap:10px;background:#fff;color:#1f1f1f;border-radius:11px;padding:13px;font-weight:700;text-decoration:none;font-size:16px}
.ff{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:560px){.ff{grid-template-columns:1fr}}
label.f{display:block;font:700 12px "Barlow Condensed",sans-serif;letter-spacing:.1em;color:var(--mut);margin-bottom:6px}
.inp{display:flex;align-items:center;background:var(--card2);border:1px solid var(--line);border-radius:10px;overflow:hidden}.inp:focus-within{border-color:var(--lime)}
.inp i{font-style:normal;color:var(--mut);padding:0 0 0 12px}.inp input{flex:1;min-width:0;background:none;border:0;color:var(--ink);font:inherit;padding:12px;outline:none}
.note{color:var(--mut);font-size:13px;margin-top:10px}
.who{display:flex;align-items:center;gap:10px;margin-bottom:14px;color:var(--mut);font-size:14px}.who img{width:30px;height:30px;border-radius:50%}
.q{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0;transition:border-color .2s}
.q.ok{border-color:#3a5a12}.qh{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.qn{font:700 12px "Barlow Condensed",sans-serif;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:var(--card2);color:var(--mut);flex:none}
.q.ok .qn{background:var(--lime);color:#0b0b12}.tag{font:700 12px "Barlow Condensed",sans-serif;letter-spacing:.1em;color:var(--lime)}
.qt{font-weight:700;font-size:18px;line-height:1.3}.qs{color:var(--mut);font-size:13.5px;margin-top:3px}
.fld{margin-top:12px;width:100%;display:flex;align-items:center;gap:10px;min-height:54px;padding:8px 12px;background:var(--card2);border:1px solid var(--line);border-radius:11px;cursor:pointer;text-align:left}
.fld:hover{border-color:#34344a}.fld .ph{color:var(--mut);flex:1}.fld .v{flex:1;display:flex;align-items:center;gap:10px;font-weight:700;min-width:0}
.fld .v span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.fld svg{flex:none;color:var(--mut)}
.chips{flex:1;display:flex;flex-wrap:wrap;gap:6px}.chip{display:inline-flex;align-items:center;gap:6px;background:#1b1b27;border-radius:8px;padding:4px 8px 4px 5px;font-size:13.5px;font-weight:600}
.lg{width:34px;height:34px;flex:none;display:grid;place-items:center}.lg img{width:100%;height:100%;object-fit:contain}
.chip .lg{width:22px;height:22px}.ini{width:100%;height:100%;border-radius:8px;display:grid;place-items:center;background:linear-gradient(135deg,#2a2a3a,#191924);font:700 12px "Barlow Condensed",sans-serif;color:#cfcfe0}
.yn{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.yn button{padding:14px;border-radius:11px;border:1px solid var(--line);background:var(--card2);font-weight:700;font-size:17px;cursor:pointer}
.yn button.on{background:var(--lime);color:#0b0b12;border-color:var(--lime)}
.slots{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}.slot{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:8px 6px;border-radius:11px;background:var(--card2);border:1px dashed #33334a;min-height:96px;font-weight:700;font-size:12.5px;line-height:1.2;text-align:center;min-width:0}
.slot.f{border-style:solid;border-color:#3a5a12;background:#141c0b}.slot .r{font:700 15px "Barlow Condensed",sans-serif;color:var(--gold)}.slot .lg{width:32px;height:32px}.slot .nm{max-width:100%;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.slot .e{color:var(--mut);font-weight:500}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}@media(max-width:420px){.grid{gap:6px}}
.tile{position:relative;display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 4px 8px;border-radius:11px;border:1px solid var(--line);background:var(--card2);cursor:pointer;font-size:12px;font-weight:600;line-height:1.15;text-align:center;transition:transform .12s,border-color .12s}
.tile:active{transform:scale(.96)}.tile .lg{width:42px;height:42px}.tile.on{border-color:var(--lime);background:#16200a}
.tile .b{position:absolute;top:5px;right:5px;width:20px;height:20px;border-radius:50%;background:var(--lime);color:#0b0b12;font:700 12px "Barlow Condensed",sans-serif;display:grid;place-items:center}
.tile[disabled]{cursor:default}
.res{margin-top:10px;display:flex;flex-direction:column;gap:6px}.bar{position:relative;display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:9px;background:var(--card2);overflow:hidden;font-size:14px}
.bar .fill{position:absolute;inset:0 auto 0 0;background:#1d2a10;z-index:0}.bar>*:not(.fill){position:relative;z-index:1}.bar .pc{margin-left:auto;font-weight:700}
.bar.mine{outline:1px solid var(--lime)}.bar.right .pc{color:var(--lime)}.mypick{margin-top:10px;font-size:14px;color:var(--mut)}.mypick b{color:var(--ink)}
.ok-t{color:var(--lime);font-weight:700}.no-t{color:var(--red);font-weight:700}
.sbar{position:fixed;left:0;right:0;bottom:0;z-index:30;background:rgba(10,10,16,.96);backdrop-filter:blur(10px);border-top:1px solid var(--line);padding:10px 16px calc(10px + env(safe-area-inset-bottom))}
.sbar .in{max-width:760px;margin:0 auto;display:flex;align-items:center;gap:14px}.prog{flex:1;min-width:0}.prog .t{font-size:13px;color:var(--mut);margin-bottom:5px}.prog .t b{color:var(--ink)}
.prog .tr{height:6px;border-radius:6px;background:#1d1d28;overflow:hidden}.prog .tr i{display:block;height:100%;background:var(--lime);border-radius:6px;transition:width .25s}
.sub{background:var(--lime);color:#0b0b12;border:0;border-radius:11px;padding:13px 22px;font-weight:800;font-size:16px;cursor:pointer;white-space:nowrap}
.sub:disabled{background:#2a2a36;color:#6f6e84;cursor:not-allowed}
.done h2{font:700 26px "Barlow Condensed",sans-serif;margin:0 0 4px;text-transform:uppercase;color:var(--lime)}.done p{color:var(--mut);margin:0 0 12px}
.row{display:flex;gap:10px;flex-wrap:wrap}.btn{display:inline-flex;align-items:center;gap:8px;background:var(--card2);border:1px solid #2c2c3c;border-radius:10px;padding:10px 14px;font-weight:700;font-size:14px;cursor:pointer;text-decoration:none;color:var(--ink)}
.btn.l{background:var(--lime);color:#0b0b12;border-color:var(--lime)}
.sum{display:grid;gap:8px;margin:14px 0}.sum div{display:flex;gap:10px;justify-content:space-between;font-size:14px;border-bottom:1px solid var(--line);padding-bottom:8px}.sum span{color:var(--mut)}.sum b{text-align:right}
.lbt{width:100%;border-collapse:collapse}.lbt td{padding:9px 6px;border-bottom:1px solid var(--line)}.lbt .rk{font:700 18px "Barlow Condensed",sans-serif;color:var(--mut);width:34px}.lbt tr:nth-child(-n+3) .rk{color:var(--gold)}.lbt .p{text-align:right;font-weight:700}
.win .kick{margin-bottom:2px}.win h2{font:700 30px/1.05 "Barlow Condensed",sans-serif;margin:0 0 12px;text-transform:uppercase;letter-spacing:.01em}
.wr{display:flex;align-items:center;gap:12px;padding:10px 2px;border-top:1px solid var(--line)}
.wr .rk{font:700 22px "Barlow Condensed",sans-serif;width:30px;color:var(--mut);font-variant-numeric:tabular-nums}
.wr .nm{flex:1;min-width:0}.wr .nm b{display:block;font-weight:700;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wr .nm span{color:var(--mut);font-size:13px}
.wr .pt{font:700 24px "Barlow Condensed",sans-serif;color:var(--lime);font-variant-numeric:tabular-nums}.wr .pt small{font:600 12px Barlow,sans-serif;color:var(--mut);margin-left:3px}
.by{color:var(--mut);font-size:12px;margin-top:10px}
.rules{color:var(--mut);font-size:13.5px}.rules li{margin:4px 0}
.sh{position:fixed;inset:0;z-index:50;background:rgba(3,3,6,.7);display:flex;align-items:center;justify-content:center;padding:16px;opacity:0;pointer-events:none;transition:opacity .18s}
.sh.open{opacity:1;pointer-events:auto}.shb{background:var(--card);border:1px solid #2a2a3a;border-radius:16px;width:100%;max-width:440px;max-height:min(680px,86vh);display:flex;flex-direction:column;transform:translateY(14px);transition:transform .22s}
.sh.open .shb{transform:none}.shh{display:flex;align-items:center;gap:10px;padding:16px 16px 10px}.shh b{font-size:17px;flex:1}.shh .c{font:700 14px "Barlow Condensed",sans-serif;color:var(--lime)}
.shh button{background:none;border:0;color:var(--mut);font-size:26px;line-height:1;cursor:pointer;padding:0 2px}
.shs{padding:0 16px 8px}.shs input{width:100%;background:var(--card2);border:1px solid var(--line);border-radius:10px;color:var(--ink);font:inherit;padding:10px 12px;outline:none}.shs input:focus{border-color:var(--lime)}
.shl{overflow-y:auto;padding:4px 8px 8px;-webkit-overflow-scrolling:touch;overscroll-behavior:contain}
.opt{width:100%;display:flex;align-items:center;gap:12px;padding:9px 10px;border-radius:10px;border:0;background:none;cursor:pointer;text-align:left;font-weight:600;font-size:15.5px}
.opt:hover{background:var(--card2)}.opt.on{background:#16200a}.opt .ck{margin-left:auto;width:22px;height:22px;border-radius:6px;border:1.5px solid #3a3a50;display:grid;place-items:center;flex:none}
.opt.on .ck{background:var(--lime);border-color:var(--lime);color:#0b0b12}.one .ck{border-radius:50%}.opt.dim{opacity:.4}.opt .num{font:700 18px "Barlow Condensed",sans-serif;width:34px;color:var(--lime)}
.shf{padding:10px 16px 14px;border-top:1px solid var(--line)}.shf .sub{width:100%}
@media(max-width:600px){.sh{align-items:flex-end;padding:0}.shb{max-width:none;border-radius:18px 18px 0 0;max-height:88vh;transform:translateY(40px)}.shf{padding-bottom:calc(14px + env(safe-area-inset-bottom))}h1{font-size:34px}}
.toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:#22222f;border:1px solid #33334a;color:var(--ink);padding:10px 16px;border-radius:10px;font-size:14px;z-index:60;display:none;max-width:calc(100vw - 32px);text-align:center}
.toast.err{border-color:#5a1f28;color:#ffb3bb}
.skel{height:90px;border-radius:14px;background:linear-gradient(90deg,#0f0f16,#151520,#0f0f16);background-size:200% 100%;animation:sk 1.2s infinite;margin:12px 0}@keyframes sk{to{background-position:-200% 0}}
</style><script src="/brand/strap.js?v=1"></script></head><body>
<div class="top"><div class="in"><a class="brand" href="/india">letsgrowesports</a><span class="pill">PREDICT &amp; WIN</span></div></div>
<main>
<section class="hero"><div class="kick">PMGC 2026 · ISTANBUL · THE GAUNTLET</div><h1>Predict <span>&amp;</span> Win</h1>
<div class="facts"><b>26-27 Nov</b> · 16 teams · 12 matches · the top 6 go straight to the Grand Finals</div>
<div class="lock" id="lock"><span class="l">PICKS LOCK IN</span><b id="cd">--:--:--</b><span class="w"><span id="lockw"></span></span></div>
<div class="prz"><div class="pzh"><span class="pzw">WIN</span><b>Free UC, cash, gift cards &amp; coupons</b></div>
<div class="pzg"><div class="pz"><svg viewBox="0 0 48 48" width="34" height="34"><defs><linearGradient id="gU" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe27a"/><stop offset="1" stop-color="#e0a400"/></linearGradient></defs><circle cx="24" cy="24" r="20" fill="url(#gU)"/><circle cx="24" cy="24" r="15" fill="none" stroke="#a87700" stroke-width="2"/><text x="24" y="29.5" text-anchor="middle" font-family="Barlow Condensed,Arial" font-weight="700" font-size="15" fill="#5a3e00">UC</text></svg><span>Free UC</span></div>
<div class="pz"><svg viewBox="0 0 48 48" width="34" height="34"><rect x="4" y="12" width="40" height="24" rx="4" fill="#3ccf7a"/><rect x="8" y="16" width="32" height="16" rx="2" fill="none" stroke="#0e5c30" stroke-width="2"/><text x="24" y="29" text-anchor="middle" font-family="Arial" font-weight="700" font-size="13" fill="#0e5c30">&#8377;</text></svg><span>Cash prizes</span></div>
<div class="pz"><svg viewBox="0 0 48 48" width="34" height="34"><rect x="5" y="12" width="38" height="25" rx="4" fill="#a58bff"/><rect x="21" y="12" width="6" height="25" fill="#ff5d8f"/><path d="M24 12c-3-6-11-5-9 0 1 2 6 1 9 0zm0 0c3-6 11-5 9 0-1 2-6 1-9 0z" fill="#ff5d8f"/></svg><span>Gift cards</span></div>
<div class="pz"><svg viewBox="0 0 48 48" width="34" height="34"><path d="M6 14h36v7a3 3 0 0 0 0 6v7H6v-7a3 3 0 0 0 0-6z" fill="#ffb347"/><path d="M30 15v18" stroke="#8a4b00" stroke-width="2" stroke-dasharray="3 3"/><text x="18" y="28" text-anchor="middle" font-family="Arial" font-weight="700" font-size="10" fill="#8a4b00">%</text></svg><span>Coupons</span></div></div>
<div class="prize" id="prize"></div></div></section>
<div id="app"><div class="skel"></div><div class="skel"></div><div class="skel"></div></div>
<section class="card"><div class="tag" style="margin-bottom:6px">HOW IT WORKS</div><ul class="rules">
<li>Sign in with Google and add your Instagram ID (that's how we reach winners).</li>
<li>Answer all 8 questions. You can change your picks until they lock.</li>
<li>A right answer earns 100 points plus a bonus for calling what few others did. Finalists and the top 3 earn points for each right team.</li>
<li>Ties go to more right answers, then whoever submitted first. One entry per person.</li></ul></section>
</main>
<div class="sbar" id="sbar" style="display:none"><div class="in"><div class="prog"><div class="t" id="pt"></div><div class="tr"><i id="pb" style="width:0"></i></div></div><button class="sub" id="go" disabled>Submit picks</button></div></div>
<div class="sh" id="sh" aria-hidden="true"><div class="shb" role="dialog" aria-modal="true"><div class="shh"><b id="sht"></b><span class="c" id="shc"></span><button id="shx" aria-label="Close">&times;</button></div>
<div class="shs" id="shs"><input id="shq" placeholder="Search teams" autocomplete="off"></div><div class="shl" id="shl"></div><div class="shf" id="shf"><button class="sub" id="shd">Done</button></div></div></div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let S=null,P={},F={handle:'',name:''},EDIT=false,OFF=0,SHQ=null,SHSEL=[];
const store={get(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(e){return null}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const DK='pmgc26g_draft';
function toast(t,err){const e=$('toast');e.textContent=t;e.className='toast'+(err?' err':'');e.style.display='block';clearTimeout(toast.h);toast.h=setTimeout(()=>e.style.display='none',2600)}
const TM=()=>Object.fromEntries((S?S.teams:[]).map(t=>[t.n,t]));
function ini(n){return n.replace(/^(the|team)\s+/i,'').split(/\s+/).map(w=>w[0]).join('').slice(0,3).toUpperCase()}
function lg(n,cls){const t=TM()[n];return `<span class="lg ${cls||''}">${t&&t.logo?`<img src="${esc(t.logo)}" alt="" loading="lazy" decoding="async" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ini',textContent:'${esc(ini(n))}'}))">`:`<span class="ini">${esc(ini(n))}</span>`}</span>`}
const CHEV='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg>';
const G='<svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.6 13.2l7.9 6.2C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 7l7.2 5.6c4.2-3.9 7.1-9.6 7.1-17.1z"/><path fill="#FBBC05" d="M10.5 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.2C1 16.4 0 20.1 0 24s1 7.6 2.6 10.8l7.9-6.2z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.2-5.6c-2 1.4-4.7 2.3-8.7 2.3-6.3 0-11.6-4.1-13.5-9.9l-7.9 6.2C6.6 42.6 14.6 48 24 48z"/></svg>';
const done=q=>{const v=P[q.id];return q.kind==='multi'||q.kind==='rank'?Array.isArray(v)&&v.length===q.pick:!!v};
const handleOk=()=>/^@?[a-zA-Z0-9._]{1,30}$/.test(F.handle.trim())&&/[a-zA-Z0-9]/.test(F.handle);
function nDone(){return S.questions.filter(done).length}
function shut(){return S&&S.closed}
async function load(){try{const r=await fetch('/predict/pmgc/api/state',{cache:'no-store',credentials:'same-origin'});S=await r.json();OFF=S.now*1000-Date.now()}catch(e){$('app').innerHTML='<div class="card">Could not load. Check your connection and refresh.</div>';return}
 const me=S.me;const d=store.get(DK)||{};
 if(me&&me.picks&&!EDIT){P=JSON.parse(JSON.stringify(me.picks))}else if(d.p){P=d.p}
 F.handle=(me&&me.handle)||d.h||'';F.name=(me&&me.display)||d.n||(me&&me.name)||'';
 $('prize').textContent=S.prize||'';$('lockw').textContent=S.lock_text;render();tick()}
function save(){store.set(DK,{p:P,h:F.handle,n:F.name})}
function tick(){if(!S)return;const left=Math.max(0,S.lock*1000-(Date.now()+OFF));const l=$('lock');
 if(left<=0){l.classList.add('shut');$('cd').textContent='LOCKED';l.querySelector('.l').textContent='PICKS ARE';l.querySelector('.w').textContent='Locked '+S.lock_text;if(!S.closed){S.closed=true;render()}return}
 const h=Math.floor(left/3.6e6),m=Math.floor(left%3.6e6/6e4),s=Math.floor(left%6e4/1e3);$('cd').textContent=(h>47?Math.floor(h/24)+'d ':'')+String(h>47?h%24:h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');setTimeout(tick,1000-((Date.now()+OFF)%1000))}
function render(){setTimeout(()=>{const w=$('wshare');if(w)w.onclick=shareWin},0);const a=$('app');const me=S.me;let h='';
 if(!S.auth){a.innerHTML='<div class="card gate"><h2>Opening soon</h2><p>Sign-in isn\'t switched on yet. Check back in a bit.</p></div>';$('sbar').style.display='none';return}
 if(!me&&shut()){a.innerHTML=winners()+resultsHead()+S.questions.map((q,i)=>qcard(q,i,true)).join('')+lb();$('sbar').style.display='none';return}
 if(!me){h+=`<div class="card gate"><h2>Sign in to play</h2><p>It's free. Sign in with Google, then add your Instagram ID so we can reach you if you win.</p><a class="gbtn" href="/auth/google?next=%2Fpredict%2Fpmgc">${G} Continue with Google</a></div>`;
  h+=S.questions.map((q,i)=>qcard(q,i,true)).join('');a.innerHTML=h;$('sbar').style.display='none';return}
 if(me.hidden){a.innerHTML='<div class="card gate"><h2>Entry removed</h2><p>This entry was removed from the game. DM @letsgrowesports.igc on Instagram if you think that\'s a mistake.</p></div>';$('sbar').style.display='none';return}
 const sub=!!me.picks;
 if(shut()){h+=winners();h+=resultsHead();h+=S.questions.map((q,i)=>qcard(q,i,true)).join('');h+=lb();a.innerHTML=h;$('sbar').style.display='none';return}
 if(sub&&!EDIT){h+=doneCard();h+=lb();a.innerHTML=h;$('sbar').style.display='none';bindDone();return}
 h+=`<div class="card"><div class="who">${me.picture?`<img src="${esc(me.picture)}" alt="" referrerpolicy="no-referrer">`:''}<span>Signed in as <b style="color:var(--ink)">${esc(me.name||'you')}</b></span></div>
 <div class="ff"><div><label class="f" for="ih">INSTAGRAM ID</label><div class="inp"><i>@</i><input id="ih" inputmode="text" autocapitalize="none" autocomplete="off" spellcheck="false" maxlength="40" placeholder="yourhandle" value="${esc(F.handle.replace(/^@/,''))}"></div></div>
 <div><label class="f" for="nm">DISPLAY NAME</label><div class="inp"><input id="nm" maxlength="32" placeholder="Shown on the leaderboard" value="${esc(F.name)}"></div></div></div>
 <div class="note">Your Instagram ID, name and picks are shown publicly after picks lock. We DM winners on Instagram.</div></div>`;
 h+=S.questions.map((q,i)=>qcard(q,i,false)).join('');a.innerHTML=h;
 $('ih').oninput=e=>{F.handle=e.target.value.trim().replace(/^@/,'');save();bar()};$('nm').oninput=e=>{F.name=e.target.value;save()};
 bindQs();$('sbar').style.display='';bar()}
function fieldV(q){const v=P[q.id];if(q.kind==='multi'){return v&&v.length?`<span class="chips">${v.map(n=>`<span class="chip">${lg(n)}${esc(n)}</span>`).join('')}</span>`:`<span class="ph">Select ${q.pick} teams</span>`}
 if(q.kind==='team')return v?`<span class="v">${lg(v)}<span>${esc(v)}</span></span>`:'<span class="ph">Select a team</span>';
 return v?`<span class="v"><span>${esc(v)}</span></span>`:`<span class="ph">${q.id==='q6'?'Select a range':'Select a number'}</span>`}
function qcard(q,i,ro){const ok=!ro&&done(q);let body='';const mine=S.me&&S.me.picks?S.me.picks[q.id]:undefined;
 if(ro){body=roBody(q,mine)}
 else if(q.kind==='yesno'){body=`<div class="yn">${q.options.map(o=>`<button type="button" class="${P[q.id]===o?'on':''}" data-yn="${q.id}" data-o="${o}">${o}</button>`).join('')}</div>`}
 else if(q.kind==='rank'){const v=P[q.id]||[];body=`<div class="slots">${[0,1,2].map(k=>v[k]?`<div class="slot f"><span class="r">#${k+1}</span>${lg(v[k])}<span class="nm">${esc(v[k])}</span></div>`:`<div class="slot"><span class="r">#${k+1}</span><span class="e">Tap a team below</span></div>`).join('')}</div>
  <div class="grid">${S.teams.map(t=>{const k=v.indexOf(t.n);return `<button type="button" class="tile ${k>=0?'on':''}" data-rk="${esc(t.n)}">${k>=0?`<span class="b">${k+1}</span>`:''}${lg(t.n)}<span>${esc(t.n)}</span></button>`}).join('')}</div>`}
 else{body=`<button type="button" class="fld" data-f="${q.id}">${fieldV(q)}${CHEV}</button>`}
 return `<div class="q ${ok?'ok':''}" id="c_${q.id}"><div class="qh"><span class="qn">${ok?'✓':i+1}</span><span class="tag">${esc(q.tag)}</span></div><div class="qt">${esc(q.title)}</div>${q.sub?`<div class="qs">${esc(q.sub)}</div>`:''}${body}</div>`}
function isRight(q,o){const a=S.answers[q.id];if(a==null)return false;return Array.isArray(a)?a.includes(o):a===o}
function roBody(q,mine){const pc=(S.crowd||{})[q.id]||{},a=S.answers[q.id];let h='';
 if(mine!==undefined){const mv=Array.isArray(mine)?mine:[mine];let verdict='';if(a!=null&&(Array.isArray(a)?a.length:a)){if(q.kind==='rank'){const n=mv.filter((t,k)=>a[k]===t).length;verdict=n?`<span class="ok-t">${n}/3 in the right spot</span>`:'<span class="no-t">0/3</span>'}else if(q.kind==='multi'){const n=mv.filter(t=>a.includes(t)).length;verdict=`<span class="${n?'ok-t':'no-t'}">${n}/6 right</span>`}else verdict=isRight(q,mv[0])?'<span class="ok-t">Right</span>':'<span class="no-t">Wrong</span>'}
  h+=`<div class="mypick">Your pick: <b>${mv.map((x,k)=>(q.kind==='rank'?'#'+(k+1)+' ':'')+esc(x)).join(', ')}</b> ${verdict}</div>`}
 if(a!=null&&(Array.isArray(a)?a.length:a))h+=`<div class="mypick">Answer: <b class="ok-t">${(Array.isArray(a)?a:[a]).map((x,k)=>(q.kind==='rank'?'#'+(k+1)+' ':'')+esc(x)).join(', ')}</b></div>`;
 const src=q.kind==='rank'?(S.crowd||{}).q8_first||{}:pc;const ent=Object.entries(src).filter(e=>e[1]>0);
 if(S.closed&&ent.length)h+=`<div class="qs" style="margin-top:12px">${q.kind==='rank'?'Everyone\'s pick for #1':q.kind==='multi'?'Share of players who picked each team':'Everyone\'s picks'}</div><div class="res">${ent.map(([o,n])=>`<div class="bar ${(Array.isArray(mine)?(q.kind==='rank'?mine[0]===o:mine.includes(o)):mine===o)?'mine':''} ${isRight(q,o)&&q.kind!=='rank'?'right':''}"><div class="fill" style="width:${n}%"></div>${S.teams.some(t=>t.n===o)?lg(o,''):''}<span>${esc(o)}</span><span class="pc">${n}%</span></div>`).join('')}</div>`;
 else if(S.closed&&!mine)h+='<div class="qs" style="margin-top:10px">The crowd split shows once 20 people have played.</div>';
 if(!S.closed&&!S.me)h+=`<button type="button" class="fld" onclick="location.href='/auth/google?next=%2Fpredict%2Fpmgc'"><span class="ph">Sign in to answer</span>${CHEV}</button>`;
 return h}
function resultsHead(){const me=S.me;if(!me||!me.picks)return `<div class="card gate"><h2>Overall results</h2><p>Picks are locked: the Gauntlet is on. Here's what everyone predicted, question by question.</p></div>`;
 return `<div class="card done"><h2>${S.answers&&Object.keys(S.answers).length?(me.pts||0)+' points':'You\'re in'}</h2><p>${Object.keys(S.answers||{}).length?(me.right||0)+(S.final?' right answers. Final results.':' right answers so far. Results fill in as the Gauntlet finishes.'):'Picks are locked. Results come in after the Gauntlet on 27 Nov.'} Playing as <b style="color:var(--ink)">@${esc(me.handle)}</b>.</p></div>`}
function winners(){if(!S.final||!S.show_lb||!S.leaderboard.length)return '';
 return `<div class="card win"><div class="kick">GAUNTLET · FINAL RESULTS</div><h2>Predict &amp; Win: top 10</h2>
 ${S.leaderboard.map(r=>`<div class="wr"><span class="rk">${r.rank}</span><div class="nm"><b>${esc(r.name||r.handle)}</b><span>@${esc(r.handle)} · ${r.right} right</span></div><span class="pt">${r.pts}<small>pts</small></span></div>`).join('')}
 <div class="by">by letsgrowesports · winners get a DM on Instagram</div><div class="row" style="margin-top:12px"><button class="btn l" id="wshare">Share card</button></div></div>`}
// the winners as a share card, the same look as the tracker's cards (1080 x 1350, green strap)
async function winCard(){if(!window.lgeStrap){window.STRAP_H=130;window.lgeStrap=()=>{};window.lgeWhen=()=>''}const W=1080,H=1350,SC=2,c=document.createElement('canvas');c.width=W*SC;c.height=H*SC;const x=c.getContext('2d');x.scale(SC,SC);
 if(window.lgeReady)await lgeReady();
 const g=x.createRadialGradient(W*.8,0,40,W*.8,0,1200);g.addColorStop(0,'#1f1a3d');g.addColorStop(1,'#0b0b12');x.fillStyle=g;x.fillRect(0,0,W,H);
 x.fillStyle='rgba(255,255,255,.02)';for(let yy=0;yy<H;yy+=4)x.fillRect(0,yy,W,1);
 x.strokeStyle='#b6f23a';x.lineWidth=5;x.beginPath();x.moveTo(40,80);x.lineTo(40,40);x.lineTo(80,40);x.stroke();
 const T=(t,X,Y,f,col,al,mw)=>{x.font=f;if(mw){const w=x.measureText(t).width;if(w>mw){const m=f.match(/(\d+)px/);x.font=f.replace(/\d+px/,Math.max(10,Math.floor(+m[1]*mw/w))+'px')}}x.fillStyle=col;x.textAlign=al||'left';x.textBaseline='top';x.fillText(t,X,Y)};
 const M=n=>`600 ${n}px "Barlow Condensed",sans-serif`,N=n=>`700 ${n}px "Barlow Condensed",sans-serif`,B=n=>`700 ${n}px "Barlow",sans-serif`;
 T('PMGC 2026 GAUNTLET // PREDICT & WIN',80,92,N(64),'#ffffff','left',W-160);T('by letsgrowesports',80,162,M(24),'#a9a8be');
 T('// FINAL TOP 10',80,215,M(30),'#ff4d5e');T('POINTS',W-80,220,M(24),'#8d8ca3','right');
 const L=S.leaderboard.slice(0,10),y0=268,rh=(H-STRAP_H-40-y0)/10;
 L.forEach((r,i)=>{const y=y0+i*rh;if(i){x.fillStyle='#232333';x.fillRect(80,y,W-160,1)}
  T(String(r.rank),80,y+rh/2-24,N(48),'#8d8ca3');T(r.name||r.handle,160,y+rh/2-30,B(34),'#eeeef5','left',620);
  T('@'+r.handle+' · '+r.right+' right',160,y+rh/2+10,M(24),'#8d8ca3','left',620);T(String(r.pts),W-80,y+rh/2-28,N(56),'#b6f23a','right')});
 lgeStrap(x,W,H,{when:lgeWhen()});return c}
async function shareWin(){const b=$('wshare');b.disabled=true;try{const c=await winCard();const blob=await new Promise(r=>c.toBlob(r,'image/png'));
 const f=new File([blob],'pmgc-predict-win-winners.png',{type:'image/png'});
 if(/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)&&navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:'PMGC 2026 Gauntlet Predict & Win: final top 10 '+location.origin+'/predict/pmgc @letsgrowesports'});return}catch(e){if(e&&e.name==='AbortError')return}}
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=f.name;a.click()}finally{b.disabled=false}}
function lb(){if(S.final)return '';if(!S.show_lb||!S.leaderboard.length)return '';return `<div class="card"><div class="tag" style="margin-bottom:8px">LEADERBOARD</div><table class="lbt">${S.leaderboard.map(r=>`<tr><td class="rk">${r.rank}</td><td><b>${esc(r.name||r.handle)}</b><div class="qs" style="margin:0">@${esc(r.handle)} · ${r.right} right</div></td><td class="p">${r.pts}</td></tr>`).join('')}</table></div>`}
function doneCard(){const me=S.me,p=me.picks;const show=q=>{const v=p[q.id];return Array.isArray(v)?v.map((x,k)=>(q.kind==='rank'?'#'+(k+1)+' ':'')+x).join(', '):v};
 return `<div class="card done"><h2>You're in!</h2><p>Picks saved for <b style="color:var(--ink)">@${esc(me.handle)}</b>. You can change them until they lock at ${esc(S.lock_text)}.</p>
 <div class="sum">${S.questions.map(q=>`<div><span>${esc(q.tag)}</span><b>${esc(show(q))}</b></div>`).join('')}</div>
 <div class="row"><button class="btn" id="edit">Change picks</button><button class="btn l" id="share">Challenge friends</button></div></div>`}
function bindDone(){$('edit').onclick=()=>{EDIT=true;P=JSON.parse(JSON.stringify(S.me.picks));render();scrollTo({top:0})};$('share').onclick=share}
async function share(){const u=location.origin+'/predict/pmgc',t='I just made my PMGC 2026 Gauntlet predictions. Think you can call it better?';
 if(navigator.share){try{await navigator.share({title:'PMGC Predict & Win',text:t,url:u});return}catch(e){}}
 try{await navigator.clipboard.writeText(t+' '+u);toast('Link copied')}catch(e){location.href='https://wa.me/?text='+encodeURIComponent(t+' '+u)}}
function bindQs(){document.querySelectorAll('[data-yn]').forEach(b=>b.onclick=()=>{P[b.dataset.yn]=b.dataset.o;upd(b.dataset.yn)});
 document.querySelectorAll('[data-f]').forEach(b=>b.onclick=()=>openSheet(S.questions.find(q=>q.id===b.dataset.f)));
 document.querySelectorAll('[data-rk]').forEach(b=>b.onclick=()=>{const v=P.q8||[];const n=b.dataset.rk,k=v.indexOf(n);if(k>=0)v.splice(k,1);else if(v.length<3)v.push(n);else{toast('Top 3 is full. Tap a picked team to remove it.');return}P.q8=v;upd('q8')})}
function upd(id){save();const i=S.questions.findIndex(q=>q.id===id);const el=$('c_'+id);const tmp=document.createElement('div');tmp.innerHTML=qcard(S.questions[i],i,false);el.replaceWith(tmp.firstChild);bindQs();bar()}
function bar(){const n=nDone(),t=S.questions.length,hk=handleOk();$('pt').innerHTML=`<b>${n} of ${t}</b> answered${n===t&&!hk?' · add your Instagram ID':''}`;$('pb').style.width=(100*n/t)+'%';const g=$('go');g.disabled=!(n===t&&hk);g.textContent=S.me&&S.me.picks?'Save changes':'Submit picks'}
function openSheet(q){SHQ=q;const multi=q.kind==='multi';SHSEL=multi?[...(P[q.id]||[])]:[P[q.id]].filter(Boolean);
 $('sht').textContent=q.tag.charAt(0)+q.tag.slice(1).toLowerCase();$('shs').style.display=q.options.length>8&&(q.kind==='team'||multi)?'':'none';$('shq').value='';$('shf').style.display=multi?'':'none';
 drawSheet();const sh=$('sh');sh.classList.add('open');sh.setAttribute('aria-hidden','false');document.body.style.overflow='hidden'}
function closeSheet(){const sh=$('sh');sh.classList.remove('open');sh.setAttribute('aria-hidden','true');document.body.style.overflow=''}
function sheetState(){const q=SHQ,multi=q.kind==='multi';$('shc').textContent=multi?SHSEL.length+' / '+q.pick:'';
 $('shd').disabled=multi&&SHSEL.length!==q.pick;$('shd').textContent=multi?(SHSEL.length===q.pick?'Done':`Pick ${q.pick-SHSEL.length} more`):'Done';
 $('shl').querySelectorAll('[data-o]').forEach(b=>{const on=SHSEL.includes(b.dataset.o);b.classList.toggle('on',on);b.classList.toggle('dim',multi&&!on&&SHSEL.length>=q.pick);b.querySelector('.ck').textContent=on?'✓':''})}
function drawSheet(){const q=SHQ,multi=q.kind==='multi',f=$('shq').value.trim().toLowerCase(),team=q.kind==='team'||multi;$('shl').classList.toggle('one',!multi);
 $('shl').innerHTML=q.options.filter(o=>!f||o.toLowerCase().includes(f)).map(o=>`<button type="button" class="opt" data-o="${esc(o)}">${team?lg(o):q.id==='q7'?`<span class="num">${esc(o)}</span>`:''}<span>${q.id==='q7'?(o==='1'?'1 team':o+' different teams'):esc(o)}</span><span class="ck"></span></button>`).join('')||'<div class="qs" style="padding:12px">No team matches.</div>';
 $('shl').querySelectorAll('[data-o]').forEach(b=>b.onclick=()=>{const o=b.dataset.o;if(!multi){P[q.id]=o;SHSEL=[o];sheetState();setTimeout(()=>{closeSheet();upd(q.id)},120);return}
  const k=SHSEL.indexOf(o);if(k>=0)SHSEL.splice(k,1);else if(SHSEL.length<q.pick)SHSEL.push(o);else{toast(`That's ${q.pick} already. Untick one to swap.`);return}sheetState()});sheetState()}
$('shq').oninput=drawSheet;$('shx').onclick=closeSheet;$('sh').onclick=e=>{if(e.target===$('sh'))closeSheet()};
$('shd').onclick=()=>{if(SHQ.kind==='multi'&&SHSEL.length===SHQ.pick){P[SHQ.id]=[...SHSEL];closeSheet();upd(SHQ.id)}};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSheet()});
$('go').onclick=async()=>{const g=$('go');if(g.disabled)return;g.disabled=true;g.textContent='Saving...';
 try{const r=await fetch('/predict/pmgc/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({handle:F.handle,name:F.name,picks:P})});const j=await r.json();
  if(!r.ok){toast(j.error||'Could not save. Try again.',true);g.disabled=false;bar();return}
  toast(j.edited?'Changes saved':'You\'re in! Picks saved');EDIT=false;await load();scrollTo({top:0,behavior:'smooth'})}catch(e){toast('No connection. Try again.',true);g.disabled=false;bar()}};
load();setInterval(()=>{if(S&&(S.closed||!S.me||(S.me.picks&&!EDIT)))load()},60000);
setInterval(async()=>{if(!S||S.closed)return;try{const j=await (await fetch('/predict/pmgc/api/state',{cache:'no-store',credentials:'same-origin'})).json();if(j.closed){S=j;render();toast('Picks are locked')}else if(j.lock!==S.lock){S.lock=j.lock;S.lock_text=j.lock_text;$('lockw').textContent=j.lock_text}}catch(e){}},20000);
</script></body></html>"""


def build_html() -> str:
    return (PAGE.replace("__TITLE__", TITLE).replace("__DESC__", DESC)
            .replace("__SITE__", eventpage.SITE_URL))
