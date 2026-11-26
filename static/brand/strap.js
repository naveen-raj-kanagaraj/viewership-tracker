/* letsgrowesports share cards: the bottom strap (logo left; site, X and Instagram right), the same on every card.
   lgeStrap(ctx, W, H, {when, style}) draws it over the last STRAP_H px of a W x H card; await lgeReady() first so
   the logo (same origin, never taints the canvas) is loaded. window.LGE_STRAP picks the style (owner chooses). */
(function () {
  var LOGO = new Image(), ok = false, wait = [];
  LOGO.onload = function () { ok = true; wait.splice(0).forEach(function (f) { f(); }); };
  LOGO.onerror = function () { wait.splice(0).forEach(function (f) { f(); }); };
  LOGO.src = '/brand/lge-white.png?v=1';
  // the logo, and the card fonts in every weight the cards use (a font the page hasn't drawn yet would otherwise fall
  // back to Arial on the first card)
  var FONTS = ['400 24px "Barlow Condensed"', '600 24px "Barlow Condensed"', '700 24px "Barlow Condensed"', '700 24px "Barlow"', '600 24px "Barlow"'];
  window.lgeReady = function () {
    var lg = ok || LOGO.complete ? Promise.resolve() : new Promise(function (r) { wait.push(r); setTimeout(r, 3000); });
    var fl = document.fonts && document.fonts.load ? Promise.all(FONTS.map(function (f) { return document.fonts.load(f).catch(function () {}); })) : Promise.resolve();
    return Promise.race([Promise.all([lg, fl]), new Promise(function (r) { setTimeout(r, 4000); })]);
  };
  window.STRAP_H = 130;
  var XP = new Path2D('M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z');
  var LIME = '#b6f23a', SITE = 'live.letsgrowesports.com', HANDLE = '@letsgrowesports';
  var C = function (w, s) { return w + ' ' + s + 'px "Barlow Condensed",sans-serif'; };

  function icoX(x, cx, cy, s, col) { x.save(); x.translate(cx - s / 2, cy - s / 2); x.scale(s / 24, s / 24); x.fillStyle = col; x.fill(XP); x.restore(); }
  function icoIG(x, cx, cy, s, col) {
    var h = s / 2, r = s * .28; x.save(); x.strokeStyle = col; x.fillStyle = col; x.lineWidth = Math.max(1.6, s / 11);
    x.beginPath(); x.moveTo(cx - h + r, cy - h); x.arcTo(cx + h, cy - h, cx + h, cy + h, r); x.arcTo(cx + h, cy + h, cx - h, cy + h, r);
    x.arcTo(cx - h, cy + h, cx - h, cy - h, r); x.arcTo(cx - h, cy - h, cx + h, cy - h, r); x.closePath(); x.stroke();
    x.beginPath(); x.arc(cx, cy, s * .24, 0, 7); x.stroke(); x.beginPath(); x.arc(cx + s * .27, cy - s * .27, s * .06, 0, 7); x.fill(); x.restore();
  }
  function logo(x, X, cy, h, al) {     // the wordmark, h px tall, vertically centred on cy
    if (!(ok || LOGO.complete) || !LOGO.naturalWidth) {
      x.save(); x.font = C(700, h * 1.25); x.fillStyle = '#fff'; x.textAlign = al || 'left'; x.textBaseline = 'middle'; x.fillText('letsgrowesports', X, cy); x.restore();
      x.font = C(700, h * 1.25); return x.measureText('letsgrowesports').width;
    }
    var w = h * LOGO.naturalWidth / LOGO.naturalHeight, x0 = al === 'center' ? X - w / 2 : al === 'right' ? X - w : X;
    x.drawImage(LOGO, x0, cy - h / 2, w, h); return w;
  }
  // "X  IG  @letsgrowesports", right-aligned at R (or left at L when al = 'left'); returns its width
  function handles(x, P, cy, s, col, al, f) {
    x.save(); x.font = f || C(600, s * 1.05); x.textBaseline = 'middle';
    var tw = x.measureText(HANDLE).width, w = s + s * .55 + s + s * .5 + tw, x0 = al === 'left' ? P : al === 'center' ? P - w / 2 : P - w;
    icoX(x, x0 + s / 2, cy, s * .92, col); icoIG(x, x0 + s * 1.55 + s / 2, cy, s * .9, col);
    x.fillStyle = col; x.textAlign = 'left'; x.fillText(HANDLE, x0 + s * 3.05, cy + 1); x.restore(); return w;
  }
  function fade(x, W, H, top, to) {  // the card darkens into the strap
    var g = x.createLinearGradient(0, top - 70, 0, top + 30); g.addColorStop(0, 'rgba(8,8,13,0)'); g.addColorStop(1, to);
    x.fillStyle = g; x.fillRect(0, top - 70, W, 100);
  }
  function txt(x, t, X, Y, f, col, al) { x.save(); x.font = f; x.fillStyle = col; x.textAlign = al || 'left'; x.textBaseline = 'middle'; x.fillText(t, X, Y); x.restore(); }

  var S = {
    // the green bar the cards had until the owner picks a new strap
    old: function (x, W, H, o) {
      x.fillStyle = LIME; x.fillRect(0, H - 130, W, 130);
      txt(x, 'LIVE.LETSGROWESPORTS.COM', 80, H - 86, '700 44px "Barlow",sans-serif', '#0a0a14');
      txt(x, (o.when ? o.when + ' // ' : '') + HANDLE, 80, H - 40, '24px "Barlow Condensed",sans-serif', '#0a0a14');
    },
    // A: solid dark bar (Esports Charts): logo left; "More stats on live.letsgrowesports.com" and X / Instagram right
    a: function (x, W, H, o) {
      var h = STRAP_H, y = H - h; fade(x, W, H, y, '#0d0d14');
      x.fillStyle = '#0d0d14'; x.fillRect(0, y, W, h); x.fillStyle = 'rgba(255,255,255,.08)'; x.fillRect(0, y, W, 1);
      logo(x, 72, y + h / 2 - (o.when ? 10 : 0), 40);
      if (o.when) txt(x, o.when, 72, y + h / 2 + 34, C(600, 20), '#6f6e85');
      x.save(); x.font = C(700, 30); var b = x.measureText(SITE).width; x.restore();
      txt(x, SITE, W - 72, y + 46, C(700, 30), '#ffffff', 'right'); txt(x, 'More stats on', W - 72 - b - 10, y + 47, C(600, 26), '#a9a8be', 'right');
      handles(x, W - 72, y + 88, 22, '#a9a8be', 'right');
    },
    // B: fade with a lime glow on the right and the site in a lime pill (Streams Charts)
    b: function (x, W, H, o) {
      var h = STRAP_H, y = H - h; fade(x, W, H, y, '#0b0b12');
      x.fillStyle = '#0b0b12'; x.fillRect(0, y, W, h);
      var gl = x.createRadialGradient(W + 40, y + h / 2, 10, W + 40, y + h / 2, 520); gl.addColorStop(0, 'rgba(182,242,58,.38)'); gl.addColorStop(1, 'rgba(182,242,58,0)');
      x.fillStyle = gl; x.fillRect(W - 560, y, 560, h);
      logo(x, 72, y + 44, 36); handles(x, 72, y + 92, 20, '#a9a8be', 'left');
      x.save(); x.font = C(700, 28); var pw = x.measureText(SITE).width + 48, px = W - 72 - pw, py = y + 52 - 24; x.restore();
      x.save(); x.beginPath(); if (x.roundRect) x.roundRect(px, py, pw, 48, 24); else x.rect(px, py, pw, 48);
      var pg = x.createLinearGradient(px, 0, px + pw, 0); pg.addColorStop(0, '#d4ff5c'); pg.addColorStop(1, LIME); x.fillStyle = pg; x.fill(); x.restore();
      txt(x, SITE, px + pw / 2, py + 25, C(700, 28), '#0a0a14', 'center');
      txt(x, 'More stats on', px - 16, py + 25, C(600, 24), '#a9a8be', 'right');
      if (o.when) txt(x, o.when, W - 72, y + 102, C(600, 19), '#8d8ca3', 'right');
    },
    // C: dark fade, a thin lime line on top; site in lime on the right
    c: function (x, W, H, o) {
      var h = STRAP_H, y = H - h; fade(x, W, H, y, '#09090e');
      x.fillStyle = '#09090e'; x.fillRect(0, y, W, h);
      var lg = x.createLinearGradient(0, 0, W, 0); lg.addColorStop(0, 'rgba(182,242,58,0)'); lg.addColorStop(.25, LIME); lg.addColorStop(.75, LIME); lg.addColorStop(1, 'rgba(182,242,58,0)');
      x.fillStyle = lg; x.fillRect(0, y, W, 3);
      logo(x, 72, y + h / 2 - (o.when ? 10 : 0), 40); if (o.when) txt(x, o.when, 72, y + h / 2 + 34, C(600, 20), '#6f6e85');
      txt(x, SITE.toUpperCase(), W - 72, y + 48, C(700, 32), LIME, 'right'); handles(x, W - 72, y + 90, 22, '#c9c8d8', 'right');
    },
    // D: a glass panel inside the card, purple glow behind the logo
    d: function (x, W, H, o) {
      var y = H - STRAP_H + 14, h = STRAP_H - 40, X = 40, w = W - 80; fade(x, W, H, H - STRAP_H, 'rgba(11,11,18,.9)');
      x.save(); var gl = x.createRadialGradient(X + 160, y + h / 2, 10, X + 160, y + h / 2, 360); gl.addColorStop(0, 'rgba(124,92,255,.30)'); gl.addColorStop(1, 'rgba(124,92,255,0)');
      x.beginPath(); if (x.roundRect) x.roundRect(X, y, w, h, 18); else x.rect(X, y, w, h); x.fillStyle = 'rgba(20,20,32,.92)'; x.fill(); x.clip(); x.fillStyle = gl; x.fillRect(X, y, w, h); x.restore();
      x.save(); x.beginPath(); if (x.roundRect) x.roundRect(X + .5, y + .5, w - 1, h - 1, 18); else x.rect(X, y, w, h); x.strokeStyle = 'rgba(255,255,255,.12)'; x.lineWidth = 1.5; x.stroke(); x.restore();
      logo(x, X + 36, y + h / 2 - (o.when ? 12 : 0), 34); if (o.when) txt(x, o.when, X + 36, y + h / 2 + 26, C(600, 18), '#8d8ca3');
      txt(x, SITE, X + w - 36, y + h / 2 - 16, C(700, 28), '#ffffff', 'right');
      handles(x, X + w - 36, y + h / 2 + 20, 19, '#a9a8be', 'right');
    },
    // E: centred: logo, then site and handles on one line
    e: function (x, W, H, o) {
      var h = STRAP_H, y = H - h; fade(x, W, H, y, '#0b0b12');
      x.fillStyle = '#0b0b12'; x.fillRect(0, y, W, h); x.fillStyle = 'rgba(255,255,255,.07)'; x.fillRect(120, y, W - 240, 1);
      logo(x, W / 2, y + 36, 34, 'center');
      x.save(); x.font = C(700, 24); var sw = x.measureText(SITE).width; x.font = C(600, 22); var hw = 22 * 3.05 + x.measureText(HANDLE).width; x.restore();
      var tot = sw + 40 + hw, x0 = W / 2 - tot / 2;
      txt(x, SITE, x0, y + 80, C(700, 24), LIME, 'left'); txt(x, '·', x0 + sw + 20, y + 80, C(700, 24), '#6f6e85', 'center');
      handles(x, x0 + sw + 40, y + 80, 21, '#c9c8d8', 'left');
      if (o.when) txt(x, o.when, W / 2, y + 112, C(600, 17), '#6f6e85', 'center');
    }
  };
  window.lgeStrap = function (x, W, H, o) {
    o = o || {}; var s = o.style || window.LGE_STRAP || 'old';
    x.save(); x.textBaseline = 'alphabetic'; (S[s] || S.a)(x, W, H, o); x.restore();
  };
  window.lgeWhen = function () {
    try { return new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' IST'; } catch (e) { return ''; }
  };
})();
