/* letsgrowesports share cards: the bottom strap (the green bar: site, time, handle), the same on every card.
   lgeStrap(ctx, W, H, {when}) draws it over the last STRAP_H px of a W x H card; await lgeReady() first so the
   card fonts are loaded. */
(function () {
  // the card fonts in every weight the cards use (a font the page hasn't drawn yet would otherwise fall back to Arial
  // on the first card)
  var FONTS = ['400 24px "Barlow Condensed"', '600 24px "Barlow Condensed"', '700 24px "Barlow Condensed"', '700 24px "Barlow"', '600 24px "Barlow"'];
  window.lgeReady = function () {
    var fl = document.fonts && document.fonts.load ? Promise.all(FONTS.map(function (f) { return document.fonts.load(f).catch(function () {}); })) : Promise.resolve();
    return Promise.race([fl, new Promise(function (r) { setTimeout(r, 4000); })]);
  };
  window.STRAP_H = 130;
  var LIME = '#b6f23a', HANDLE = '@letsgrowesports';

  function txt(x, t, X, Y, f, col, al) { x.save(); x.font = f; x.fillStyle = col; x.textAlign = al || 'left'; x.textBaseline = 'middle'; x.fillText(t, X, Y); x.restore(); }

  var S = {
    // the green bar (owner, 27 Nov: better than the five new straps, and the brand once is enough)
    old: function (x, W, H, o) {
      x.fillStyle = LIME; x.fillRect(0, H - 130, W, 130);
      txt(x, 'LIVE.LETSGROWESPORTS.COM', 80, H - 86, '700 44px "Barlow",sans-serif', '#0a0a14');
      txt(x, (o.when ? o.when + ' // ' : '') + HANDLE, 80, H - 40, '24px "Barlow Condensed",sans-serif', '#0a0a14');
    }
  };
  window.lgeStrap = function (x, W, H, o) {
    o = o || {}; var s = o.style || window.LGE_STRAP || 'old';
    x.save(); x.textBaseline = 'alphabetic'; (S[s] || S.old)(x, W, H, o); x.restore();
  };
  window.lgeWhen = function () {
    try { return new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' IST'; } catch (e) { return ''; }
  };
})();
