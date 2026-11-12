"""Site-wide finishing layer, injected into every HTML page by web._html (after each page's own styles, so it wins).

Answers the BMIC fan feedback (993 responses, Nov 2026): "feels a bit clustered", "improve the lighter fonts",
"colour contrast", "add some animations", "looks AI generated". Same theme and colours; what changes:
  - grey text brighter (contrast), lines softer
  - cards without hard outlines, rounded, more space between them
  - segmented controls scroll sideways on phones instead of wrapping into stacks
  - quiet motion: cards fade up once on load (never rows, which the pages rebuild every few seconds), hover and
    press feedback, visible keyboard focus; nothing moves for people who ask their device for reduced motion
"""

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
