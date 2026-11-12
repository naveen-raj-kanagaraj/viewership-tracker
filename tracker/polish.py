"""Site-wide finishing layer, injected into every HTML page by web._html (after each page's own styles, so it wins).

Answers the BMIC fan feedback (993 responses, Nov 2026): "feels a bit clustered", "improve the lighter fonts",
"colour contrast", "add some animations", "looks AI generated". Same theme and colours; what changes:
  - grey text brighter (contrast), lines softer
  - cards without hard outlines, rounded, more space between them
  - segmented controls scroll sideways on phones instead of wrapping into stacks
  - quiet motion: cards fade up once on load (never rows, which the pages rebuild every few seconds), hover and
    press feedback, visible keyboard focus; nothing moves for people who ask their device for reduced motion
"""

import os

THEME = os.getenv("SITE_THEME", "clean")      # clean (Streams Charts-style type and tables) | classic (previous look)

# The clean look: Figtree sentence-case type, near-black ground, quiet bordered panels, compact controls.
# Everything is scoped to html:not(.classic), so a visitor (?theme=classic, remembered) or the server
# (SITE_THEME=classic) gets the previous look back instantly; canvas share cards draw their own fonts.
CLEAN = """<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script>(function(){try{var q=new URLSearchParams(location.search).get('theme');if(q==='classic'||q==='clean')localStorage.setItem('lge_theme',q);
if((localStorage.getItem('lge_theme')||'__THEME__')==='classic')document.documentElement.classList.add('classic')}catch(e){}})()</script>
<style id="lgeclean">
html:not(.classic){--bg:#060609!important;--card:#0d0d13!important;--card2:#14141c!important;--line:#1c1c26!important;--muted:#9a9aa8!important;--ink:#ffffff!important}
html:not(.classic),html:not(.classic) body{background:#060609!important}
html:not(.classic) body,html:not(.classic) body *:not(svg):not(path){font-family:Figtree,system-ui,sans-serif!important}
html:not(.classic) body{font-variant-numeric:tabular-nums}
html:not(.classic) h1{text-transform:none!important;letter-spacing:-.015em!important;font-weight:700!important;font-size:clamp(24px,3.4vw,32px)!important;line-height:1.2!important}
html:not(.classic) h2,html:not(.classic) h3{text-transform:none!important;letter-spacing:-.005em!important;font-weight:700!important}
html:not(.classic) .card,html:not(.classic) .kpi,html:not(.classic) .list,html:not(.classic) .sc,html:not(.classic) .gc,html:not(.classic) .z,html:not(.classic) .tc{background-color:#0d0d13!important;border:1px solid #1a1a23!important;border-radius:10px!important}
html:not(.classic) .seg,html:not(.classic) .rg{border-radius:8px!important;border-color:#1f1f29!important;background:#111118!important}
html:not(.classic) .seg button,html:not(.classic) .seg a,html:not(.classic) .rg a,html:not(.classic) .rg button{letter-spacing:0!important;text-transform:none!important;font-weight:600!important}
</style>"""


def head() -> str:
    return CLEAN.replace("__THEME__", "classic" if THEME == "classic" else "clean") + CSS


THEME_LINK = """ &middot; <a href="#" id="lgetheme" style="color:inherit">Classic look</a><script>(function(){var a=document.getElementById('lgetheme');if(!a)return;
var c=document.documentElement.classList.contains('classic');a.textContent=c?'New look':'Classic look';
a.onclick=function(e){e.preventDefault();try{localStorage.setItem('lge_theme',c?'clean':'classic')}catch(x){}location.reload()}})()</script>"""

CSS = """<style id="lgepolish">
:root{--muted:#a9a8be!important;--line:#232331!important}
body{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility}
.card,.kpi,.list,.main,.sc,.gc,.z,.mbox,.tc,.pd,.p1,.p2,.p3{border-radius:14px!important}
.card,.kpi,.list,.sc,.gc,.z,.tc{border-color:transparent!important;background-color:#13131d!important}
.card{box-shadow:inset 0 1px 0 rgba(255,255,255,.03)}
.card+.card,.list{margin-top:18px}
.kpi{padding:16px 18px!important}
select,input[type=text],input[type=search],input[type=email],input:not([type]),textarea{border-radius:10px!important;border-color:#2a2a3a!important}
.seg,.rg{border-radius:10px!important}
@media (max-width:700px){.seg{flex-wrap:nowrap!important;overflow-x:auto;scrollbar-width:none;max-width:100%}.seg::-webkit-scrollbar{display:none}.seg>*{flex:none}}
.list a:hover,.row:hover{background:#191926!important}
a,button{transition:background-color .15s ease,color .15s ease,transform .1s ease,border-color .15s ease}
button:active,.btn:active{transform:scale(.97)}
:focus-visible{outline:2px solid #b6f23a;outline-offset:2px}
@keyframes lgeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:no-preference){.card,.kpi,.main{animation:lgeUp .45s cubic-bezier(.2,.7,.2,1) both}
 .kpi:nth-child(2){animation-delay:.05s}.kpi:nth-child(3){animation-delay:.1s}.kpi:nth-child(4){animation-delay:.15s}}
@media print{.card,.kpi{animation:none!important}}
</style>"""
