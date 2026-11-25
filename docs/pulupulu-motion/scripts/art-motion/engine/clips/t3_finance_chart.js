// Clip · finance chart (t3): layout first → axes → the data grows in → annotate one thing only. Driven by real data; unit / source / badge all read from data.
// data: { title, unit (subtitle: the metric and its unit), source (bottom left), badge? (the bottom-right badge is only drawn when written, e.g. "Illustrative data"),
//         chart: 'bar'|'line'|'candle', series: [{label, value}] or candles [{label, o, h, l, c}], decimals=1, prefix='', suffix='',
//         highlight?: {index, text, sub}, colors?: {main, accent, dim}, upDown?: 'cn' (red up, green down — the default) |'us', theme? }
// Theme (a chart shot has to stay inside the film's world, so its ground shares the colour family of the shots either side): spec.theme or data.theme,
//   a film-wide palette name (paper / poster / ink / navy / bauhaus / snow / wood / chalk, see lib/palettes.js) → coloured from ctx.pal: ground bg, text ink, secondary text and ticks sub,
//     line / annotation / big number accent, bars accent2; candle up/down still uses red and green per upDown (semantic colour).
//   The old spelling still works: 'light' (white ground, the default) | 'dark' (dark ground, light text) | an object {bg, ink, sub, src, tick, xlab, grid, red, bar, dim} (with bg written, the light or dark set is picked from its luminance, then each item overrides).
//   'paper' is now the film-wide palette 'paper' (it used to be FT salmon pink).
//   No theme written but spec.safe.fill carries the film's ground: the chart uses that, and a dark ground switches to dark-ground/light-text automatically — no more white card popping up inside a dark film.
// cues (at in seconds): title (layout) · bar|line|candle (data grows in from at; dur defaults to the count; a bar chart may carry several bar cues, each with data.index (a number or an array) = these bars only grow at that moment, so each bar lands on its own word)
//         each series item may carry color (that bar's own colour, matching how the same quantity is coloured elsewhere in the film) · highlight (on this frame the annotation dot pops; text/sub override data.highlight, data.index picks which bar)
//         number (big number: data {value, prefix, suffix, decimals}, at = the moment it settles, counting starts 0.9s earlier)
// Rule: bars always start at 0; when a line / candle y-axis doesn't start at 0, "y-axis does not start at 0" is appended to the subtitle automatically.
CLIPS.t3_finance_chart = (() => {
const { clamp, lerp } = U;
const THEMES = {
  light: { bg: '#FFFFFF', ink: '#0C0C0C', sub: '#4F5B61', src: '#7c868b', tick: '#5b666b', xlab: '#3a4246', grid: 'rgba(12,12,12,0.13)', red: '#E3120B', bar: '#006BA2', dim: '#C6D2D8' },
  dark:  { bg: '#0E1116', ink: '#F2F4F5', sub: '#A7B2B8', src: '#848F95', tick: '#9AA5AB', xlab: '#C3CBD0', grid: 'rgba(255,255,255,0.14)', red: '#FF4B3E', bar: '#3EBCD2', dim: '#3A4650' },
};
const lum = col => { const m = String(col).trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i); if (!m) return 1;
  const h = m[1].length === 3 ? [...m[1]].map(x => x + x).join('') : m[1], [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
// The old theme spelling ('light' / 'dark' / an object without palette keys) is not resolved as a film-wide palette (clip.js checks for this hook)
const legacy = th => th === 'light' || th === 'dark' || (!!th && typeof th === 'object' && !Array.isArray(th) && th.name == null && !['surface', 'accent', 'accent2'].some(k => k in th));
// Film-wide palette → a whole colour set for the chart: every secondary colour derived from 6 palette keys
const fromPal = p => ({ bg: p.bg, ink: p.ink, sub: p.sub, src: PAL.mix(p.sub, p.bg, 0.2), tick: p.sub, xlab: PAL.mix(p.ink, p.sub, 0.45), grid: PAL.alpha(p.ink, 0.13),
  red: p.accent, bar: p.accent2, dim: PAL.mix(p.bg, p.sub, 0.3), dark: PAL.dark(p) });
function palette(ctx) {
  if (ctx.pal) return fromPal(ctx.pal);
  const T = (typeof ctx.theme === 'string' || (ctx.theme && Object.keys(ctx.theme).length)) ? ctx.theme : ctx.data.theme;
  if (typeof T === 'string' && !legacy(T) && window.PALETTES[T]) return fromPal(PAL.resolve(T));   // data.theme named a palette
  if (typeof T === 'string') return { ...(THEMES[T] || THEMES.light) };
  const bg = (T && T.bg) || (ctx.safe && ctx.safe.fill) || null;
  const base = bg ? (lum(bg) < 0.45 ? THEMES.dark : THEMES.light) : THEMES.light;
  return { ...base, ...(bg ? { bg } : {}), ...(T || {}) };
}
let RED, INK, SUB, GRID, P;
const CN = '"PuHui-Medium"', CNB = '"PuHui-Bold"', NUM = '"RobotoCondensed", "PuHui-Medium"';
let L, BUF;
const fmtv = (d, v) => (d.prefix || '') + TY.fmt(v, d.decimals ?? 1) + (d.suffix || '');
return {
  fonts: ['PuHui-Medium', 'PuHui-Bold'],
  safe: true,
  legacyTheme: legacy,
  init(ctx) {
    P = palette(ctx); RED = P.red; INK = P.ink; SUB = P.sub; GRID = P.grid;
    const { W, H, u, data: d } = ctx, m = (ctx.portrait ? 70 : 90) * u, c = document.createElement('canvas').getContext('2d');
    const kind = (ctx.of('bar', 'line', 'candle')[0] || {}).kind || d.chart || 'bar';
    const S = d.series || [];
    const vals = kind === 'candle' ? S.flatMap(r => [r.h, r.l]) : S.map(r => r.value);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    let zeroBased = kind === 'bar' || lo <= 0 || (hi - lo) / hi > 0.6;
    if (zeroBased) lo = Math.min(0, lo);
    const pad = (hi - lo) * 0.08, ticks = CH.ticks(zeroBased ? lo : lo - pad, hi + pad, ctx.portrait ? 5 : 4);
    const step = ticks[1] - ticks[0];                                     // the ticks have to enclose the data (CH.ticks only returns round ticks within the range)
    while (ticks[ticks.length - 1] < hi + pad * 0.5) ticks.push(+(ticks[ticks.length - 1] + step).toFixed(10));
    while (ticks[0] > (zeroBased ? lo : lo - pad * 0.5)) ticks.unshift(+(ticks[0] - step).toFixed(10));
    const titleSz = (ctx.portrait ? 64 : 58) * u, t = TY.fit(c, d.title || '', W - 2 * m, titleSz, 'PuHui-Bold', { maxLines: ctx.portrait ? 3 : 2, weight: '700 ' });
    const sub = (d.unit || '') + (!zeroBased ? (d.unit ? ' ' : '') + 'y-axis does not start at 0' : '');
    // subtitle and source line: shrink a little if they don't fit, then wrap to two lines (long qualifiers overflow the frame in portrait); the source line must clear the bottom-right badge
    const fsz = ctx.portrait ? 1.2 : 1, subF = TY.fit(c, sub, W - 2 * m, 32 * u * fsz, 'PuHui-Medium', { maxLines: 2, min: 0.8 });
    c.font = `700 ${28 * u}px "PuHui-Medium"`; const badgeW = d.badge ? c.measureText(d.badge).width + 28 + 30 * u : 0;
    const srcF = TY.fit(c, d.source || '', W - 2 * m - badgeW, 26 * u * fsz, 'PuHui-Medium', { maxLines: 2, min: 0.8 });
    const top = ctx.safe.top + 80 * u + t.lines.length * t.size * 1.25 + 60 * u + (subF.lines.length - 1) * subF.size * 1.3;
    const band = ctx.of('number').length ? 150 * u : 0;                 // with a number: reserve a strip of its own so it doesn't sit on the plot (a rising line ends up exactly in the top-right corner)
    const F = { x: m + 20 * u, y: top + 40 * u + band, w: W - 2 * m - 40 * u, h: H - top - 40 * u - band - (ctx.portrait ? 260 : 190) * u - ctx.safe.bottom - (srcF.lines.length - 1) * srcF.size * 1.3 };   // safe.bottom: give the whole caption band a clear strip; the source line sits just above it
    const n = S.length, slot = (F.w - 80 * u) / n, xs = S.map((_, i) => F.x + slot * (i + 0.5));   // leave 80px on the right for the tick values so they don't sit on the last bar
    // x axis: a time series (line / candle, or data.xAxis:'time') is thinned by interval; categories (the bar default) each need a name — shrink the type, and if it still doesn't fit split onto two lines
    const category = (d.xAxis || (kind === 'bar' ? 'category' : 'time')) === 'category';
    const fs0 = ctx.portrait ? 1.2 : 1, xf = 30 * u * fs0;
    c.font = `400 ${xf}px "RobotoCondensed", "PuHui-Medium"`;
    const maxW = Math.max(1, ...S.map(r => c.measureText(String(r.label ?? '')).width));
    const xScale = category ? clamp(slot * 0.94 / maxW, 0.7, 1) : 1, stagger = category && slot * 0.94 < maxW * 0.7;
    // tick labels take their decimals from the step: a step of 2.5 needs 1 place, or −2.5/2.5/7.5 get rounded, printed as −3/3/8 (ticks that lie)
    let tdec = 0; while (tdec < 4 && Math.abs(step * 10 ** tdec - Math.round(step * 10 ** tdec)) > 1e-6) tdec++;
    if (kind === 'bar' && Math.min(...vals) < 0) {                       // a negative bar's value goes below the bar's base: reserve a line under the lowest bar so it doesn't land on the category name
      const vmin = Math.min(...vals), need = 56 * u * fs0;
      while ((vmin - ticks[0]) / (ticks[ticks.length - 1] - ticks[0]) * F.h < need) ticks.unshift(+(ticks[0] - step).toFixed(10));
    }
    const qh1 = ctx.of('highlight')[0], H1 = d.highlight || {}, hiI = qh1 ? (qh1.data && qh1.data.index != null ? qh1.data.index : (H1.index != null ? H1.index : S.length - 1)) : -1;
    if (kind === 'bar' && hiI >= 0 && S[hiI] && S[hiI].value >= 0 && S.some((r, j) => j !== hiI && r.value >= S[hiI].value)) {   // the annotated bar isn't the tallest: the text block has to clear the neighbouring bars, so reserve a block on top (add a tick step if it doesn't fit)
      const nL = [C(qh1.text, H1.text), C(qh1.sub, H1.sub)].filter(Boolean).length, need = (52 * nL + 44 + 30) * u * fs0, vmax = Math.max(...vals);
      while ((ticks[ticks.length - 1] - vmax) / (ticks[ticks.length - 1] - ticks[0]) * F.h < need) ticks.push(+(ticks[ticks.length - 1] + step).toFixed(10));
    }
    L = { subF, srcF, m, kind, S, zeroBased, ticks, tdec, yS: CH.lin(ticks[0], ticks[ticks.length - 1], F.y + F.h, F.y), F, xs, slot, t, sub, band, category, xFont: xf * xScale, stagger,
      every: category ? 1 : Math.max(1, Math.ceil(n / (ctx.portrait ? 6 : 10))) };
    const main = (d.colors && d.colors.main) || (kind === 'bar' ? P.bar : RED);
    L.col = { main, accent: (d.colors && d.colors.accent) || main, dim: (d.colors && d.colors.dim) || P.dim };
    const up = P.dark != null ? (P.dark ? '#FF4B3E' : '#E3120B') : RED;   // up/down is a semantic colour: even with a film-wide palette (where accent may not be red) it stays red/green
    L.updown = d.upDown === 'us' ? ['#1B9E5A', up] : [up, '#1B9E5A'];
  },
  draw(c0, t, ctx) {
    // alpha: text and lines can disappear over other footage. Draw into a buffer first, then composite with a halo in the theme's ground colour (same trick as t1; the default black on white gets a white halo)
    const c = ctx.alpha ? (BUF = BUF || document.createElement('canvas'), BUF.width = ctx.W, BUF.height = ctx.H, BUF.getContext('2d')) : c0;
    const { W, H, u, data: d } = ctx, { m, F, yS, xs, S, kind } = L, fs = ctx.portrait ? 1.2 : 1;   // portrait is watched on a phone: small type goes up 20%
    const qt = ctx.of('title')[0] || { at: 0 }, lt = ctx.lt(t, qt.at);
    if (!ctx.alpha) { c.fillStyle = P.bg; c.fillRect(0, 0, W, H); }
    // ---- layout: top rule → kicker → title → subtitle (unit / qualifier) → source → badge ----
    if (lt > 0) {
      const p = MO.quintOut(MO.seg(lt, 0, 0.45));
      c.fillStyle = RED; c.fillRect(0, 0, W * p, 8 * u); CH.tag(c, m, ctx.safe.top + 52 * u, 96 * p * u, 22 * u, RED);
      c.save(); c.textBaseline = 'alphabetic'; c.textAlign = 'left';
      const tp = MO.quintOut(MO.seg(lt, 0.05, 0.5)); c.globalAlpha = tp; c.fillStyle = INK; c.font = `700 ${L.t.size}px ${CNB}`;
      L.t.lines.forEach((ln, i) => c.fillText(ln, m, ctx.safe.top + 80 * u + (i + 1) * L.t.size * 1.2 + (1 - tp) * 18 * u));
      const sp = MO.quintOut(MO.seg(lt, 0.15, 0.6)), sy = ctx.safe.top + 80 * u + L.t.lines.length * L.t.size * 1.2 + 54 * u;
      c.globalAlpha = sp; c.font = `400 ${L.subF.size}px ${CN}`; c.fillStyle = SUB; L.subF.lines.forEach((ln, k) => c.fillText(ln, m, sy + k * L.subF.size * 1.3 + (1 - sp) * 14 * u));
      c.globalAlpha = MO.seg(lt, 0.2, 0.6); c.font = `400 ${L.srcF.size}px ${CN}`; c.fillStyle = P.src;
      L.srcF.lines.forEach((ln, k, a) => c.fillText(ln, m, H - 40 * u - ctx.safe.bottom - (a.length - 1 - k) * L.srcF.size * 1.3));
      c.restore();
      if (d.badge) { c.save(); c.globalAlpha = MO.seg(lt, 0.2, 0.6); CH.demoBadge(c, d.badge, { x: W - m, y: H - 50 * u - ctx.safe.bottom, font: `700 ${28 * u}px ${CN}`, col: RED, box: tint(RED, 0.06) }); c.restore(); }
    }
    // ---- axes (0.25s after the layout) ----
    const qd = ctx.of('bar', 'line', 'candle')[0] || { at: qt.at + 0.75 }, gStart = Math.min(qt.at + 0.25, qd.at - 0.4);
    const gp = MO.seg(ctx.lt(t, gStart), 0, 0.6);
    const fmtTick = v => TY.fmt(v, L.tdec);
    CH.grid(c, F, L.ticks, yS, gp, { col: GRID, zeroCol: L.zeroBased ? INK : GRID, font: `400 ${28 * u * fs}px ${NUM}`, labelCol: P.tick, side: 'right', lw: 1.5 * u, zeroLw: 3 * u, fmt: fmtTick, labelDy: -10 * u });
    const qh0 = ctx.of('highlight')[0], hi0 = qh0 ? (qh0.data && qh0.data.index != null ? qh0.data.index : (d.highlight && d.highlight.index != null ? d.highlight.index : S.length - 1)) : -1;
    const keep = i => i % L.every === 0 || i === hi0 || (i === S.length - 1 && (S.length - 1) % L.every >= L.every / 2);   // the annotated bar always gets a name; the last label is dropped rather than crammed when it's too close to the previous one
    const xp = MO.seg(ctx.lt(t, gStart + 0.15), 0, 0.5), xy = F.y + F.h + 46 * u, xo = { font: `400 ${L.xFont}px ${NUM}`, col: P.xlab };
    if (!L.stagger) CH.xLabels(c, S.map((r, i) => ({ x: xs[i], label: keep(i) ? String(r.label ?? '') : '' })), xy, xp, xo);
    else { CH.xLabels(c, S.map((r, i) => ({ x: xs[i], label: i % 2 ? '' : String(r.label ?? '') })), xy, xp, xo); CH.xLabels(c, S.map((r, i) => ({ x: xs[i], label: i % 2 ? String(r.label ?? '') : '' })), xy + L.xFont * 1.15, xp, xo); }
    // ---- data ----
    const n = S.length, ddur = qd.dur || Math.min(2.2, Math.max(0.9, n * (kind === 'bar' ? 0.22 : 0.06)));
    const dp = ctx.p(t, qd.at, ddur);
    const qh = ctx.of('highlight')[0], hi = qh ? (qh.data && qh.data.index != null ? qh.data.index : (d.highlight && d.highlight.index != null ? d.highlight.index : n - 1)) : -1;
    const hiP = qh ? MO.smooth(ctx.p(t, qh.at, 0.4)) : 0;
    let anchor = null;
    if (kind === 'bar') {
      const bw = Math.min(150 * u, L.slot * 0.62);
      const on = qh && ctx.lt(t, qh.at) > 0, opt = { col: L.col.main, hiP, hiCol: L.col.accent, dimCol: L.col.dim,
        fmt: v => fmtv(d, v), font: `600 ${Math.max(24 * u * fs, Math.min(34 * u * fs, L.slot * 0.3))}px ${NUM}`, labelCol: INK, label: n <= 14 };
      const own = {};                                                      // a bar cue with data.index: just those bars grow on their own from its at
      for (const q of ctx.of('bar')) if (q.data && q.data.index != null) [].concat(q.data.index).forEach(i => { own[i] = q; });
      let tops;
      if (!Object.keys(own).length && !S.some(r => r.color)) tops = CH.bars(c, S.map((r, i) => ({ x: xs[i], v: r.value })), yS, bw, dp, { ...opt, lag: Math.min(0.22, 2 / n), hi: on ? hi : -1 });
      else tops = S.map((r, i) => {
        const q = own[i], p = q ? ctx.p(t, q.at, q.dur || 0.7) : MO.lagged(i, n, dp, Math.min(0.22, 2 / n));
        const col = r.color || L.col.main;
        return CH.bars(c, [{ x: xs[i], v: r.value }], yS, bw, p, { ...opt, lag: 0, col, hiCol: col, hi: on ? (i === hi ? 0 : 1) : -1 })[0];
      });
      if (hi >= 0) anchor = [xs[hi], tops[hi][1]];
      L.neg = hi >= 0 && S[hi].value < 0; L.tops = tops;
      L.barAbove = hi >= 0 && S[hi].value >= 0 && S.some((r, j) => j !== hi && r.value > S[hi].value * 1.5);   // a much taller bar sits alongside: put the annotation directly above this bar rather than on top of another one
    } else if (kind === 'line') {
      const pts = S.map((r, i) => [xs[i], yS(r.value)]);
      const lp = MO.smooth(dp);
      const hp = CH.line(c, pts, lp, { col: L.col.main, lw: 5 * u, headR: 9 * u, area: { top: F.y, base: F.y + F.h, c0: tint(RED, 0.12), c1: tint(RED, 0) } });
      if (hp && lp < 1) { const v = yS.inv(hp[1]); c.save(); c.font = `700 ${36 * u}px ${NUM}`; c.fillStyle = L.col.main; c.textAlign = 'left'; c.textBaseline = 'middle'; TY.tabular(c, fmtv(d, v), hp[0] + 20 * u, hp[1] - 4 * u); c.restore(); }
      else if (lp >= 1) { const v = S[n - 1].value; c.save(); c.font = `700 ${36 * u}px ${NUM}`; c.fillStyle = L.col.main; c.textAlign = 'right'; c.textBaseline = 'alphabetic'; TY.tabular(c, fmtv(d, v), pts[n - 1][0], pts[n - 1][1] - 24 * u, { align: 'right' }); c.restore(); }
      if (hi >= 0) anchor = pts[hi];
    } else {
      const cw = Math.min(30 * u, L.slot * 0.6);
      CH.candles(c, S, xs, yS, cw, dp, { up: L.updown[0], down: L.updown[1], lag: Math.min(0.06, 1.5 / n) });
      if (hi >= 0) anchor = [xs[hi], yS(S[hi].c)];
    }
    // ---- annotation: one shot annotates one thing ----
    let above = L.barAbove;
    if (qh && anchor && kind === 'bar' && !above && !L.neg) {             // dry-run the diagonal annotation box: if it lands on another bar or its value, move it directly above this bar instead
      const H0 = d.highlight || {}, ls = [C(qh.text, H0.text), C(qh.sub, H0.sub)].filter(Boolean);
      const ax = anchor[0] - Math.min(150 * u, L.slot * 0.62) / 2, right = ax > F.x + F.w * 0.55, tx = right ? ax - 60 * u : ax + 60 * u, ty = Math.max(F.y + 60 * u, anchor[1] - 140 * u);
      c.save(); c.font = `700 ${50 * u}px ${NUM}`; let tw = c.measureText(ls[0] || '').width; c.font = `400 ${28 * u * fs}px ${CN}`; if (ls[1]) tw = Math.max(tw, c.measureText(ls[1]).width); c.restore();
      const bx0 = right ? tx - 12 - tw : tx + 12, bx1 = bx0 + tw, by1 = ty + (ls.length > 1 ? 56 : 16) * u;
      above = L.tops.some(([bx, by], j) => j !== hi && bx + L.slot * 0.45 > bx0 && bx - L.slot * 0.45 < bx1 && by - 44 * u * fs < by1);
    }
    if (qh && anchor && kind === 'bar' && above) {
      const H0 = d.highlight || {}, lines = [C(qh.text, H0.text), C(qh.sub, H0.sub)].filter(Boolean), k = ctx.lt(t, qh.at);
      if (k > 0) {
        const s = MO.spring(k, { duration: 0.45, bounce: 0.25 }), lp = MO.quintOut(MO.seg(k, 0.12, 0.45)), fp = MO.quintOut(MO.seg(k, 0.3, 0.7));
        // text block directly above this bar: measure its width, clamp it horizontally inside the plot, then raise it above every bar it spans (value labels included), with a leader running up from this bar's value label
        const [x, y] = anchor, lh = 52 * u * fs, vlab = 44 * u * fs;
        c.save(); c.font = `700 ${50 * u * fs}px ${NUM}`; let tw = c.measureText(lines[0]).width; c.font = `400 ${28 * u * fs}px ${CN}`; if (lines[1]) tw = Math.max(tw, c.measureText(lines[1]).width);
        const cx = clamp(x, F.x + tw / 2, F.x + F.w - 80 * u - tw / 2);
        const cover = L.tops.filter(([bx]) => bx > cx - tw / 2 - L.slot / 2 && bx < cx + tw / 2 + L.slot / 2).map(([, by]) => by);
        const bottom = Math.max(F.y + lh * lines.length, Math.min(y, ...cover) - vlab - 18 * u);   // text block's bottom edge
        c.fillStyle = RED; c.beginPath(); c.arc(x, y - 4 * u, 9 * u * Math.max(0, s), 0, 7); c.fill();
        const y0 = y - vlab, y1 = bottom + 8 * u;
        if (y0 - y1 > 6 * u) { c.strokeStyle = INK; c.lineWidth = 2 * u; c.beginPath(); c.moveTo(x, y0); c.lineTo(lerp(x, cx, lp), lerp(y0, y1, lp)); c.stroke(); }
        c.globalAlpha = fp; c.fillStyle = INK; c.textAlign = 'center'; c.textBaseline = 'alphabetic';
        lines.forEach((ln, i) => { c.font = i === 0 ? `700 ${50 * u * fs}px ${NUM}` : `400 ${28 * u * fs}px ${CN}`; c.fillText(ln, cx, bottom - (lines.length - 1 - i) * lh * (i === 0 ? 1 : 0.62) + (1 - fp) * 12 * u); });
        c.restore();
      }
    } else if (qh && anchor) {
      if (kind === 'bar') anchor = [anchor[0] - Math.min(150 * u, L.slot * 0.62) / 2, anchor[1]];
      const H0 = d.highlight || {}, lines = [C(qh.text, H0.text), C(qh.sub, H0.sub)].filter(Boolean);
      const right = anchor[0] > F.x + F.w * 0.55, tx = right ? anchor[0] - 60 * u : anchor[0] + 60 * u;
      const ty = L.neg ? Math.min(F.y + F.h - 90 * u, anchor[1] + 70 * u) : Math.max(F.y + 60 * u, anchor[1] - 140 * u);   // negative bar: the annotation goes downward instead of back over the bars above the zero line
      CH.callout(c, ctx.lt(t, qh.at), 0, { x: anchor[0], y: anchor[1], tx, ty, lines, col: INK, dotCol: RED, font: `700 ${50 * u}px ${NUM}`, font2: `400 ${28 * u * fs}px ${CN}`, align: right ? 'right' : 'left', r: 9 * u });
    }
    // ---- big number (number cue: at = the moment it settles) ----
    for (const q of ctx.of('number')) {
      const nd = q.data || {}, k = MO.expoOut(clamp((t - (q.at - 0.9)) / 0.9)); if (t < q.at - 0.9) continue;
      c.save(); c.globalAlpha = clamp((t - (q.at - 0.9)) / 0.2); c.font = `700 ${120 * u}px ${NUM}`; c.fillStyle = RED; c.textAlign = 'right'; c.textBaseline = 'alphabetic';
      const numStr = (nd.prefix || '') + TY.fmt((nd.value || 0) * k, nd.decimals ?? 0) + (nd.suffix || ''), by = F.y - 62 * u;   // lands in the strip reserved above the plot (clear of the top tick value)
      const nw = c.measureText((nd.prefix || '') + TY.fmt(nd.value || 0, nd.decimals ?? 0) + (nd.suffix || '')).width;
      TY.tabular(c, numStr, W - m, by, { align: 'right' });
      const cap = q.text ?? q.sub; if (cap) { c.font = `400 ${30 * u * fs}px ${CN}`; c.fillStyle = SUB; c.textAlign = 'right'; c.fillText(cap, W - m - nw - 24 * u, by - 10 * u); }
      c.restore();
    }
    if (ctx.alpha) { c0.save(); c0.shadowColor = P.bg; for (const b of [8, 3, 1.5]) { c0.shadowBlur = b * ctx.u; c0.drawImage(BUF, 0, 0); } c0.restore(); }   // three passes from wide to tight: soft outer halo plus a solid edge hugging the glyphs
  },
};
function C(...a) { return a.find(v => v != null && v !== ''); }
function tint(col, a) { const m = String(col).trim().match(/^#([0-9a-f]{6})$/i); if (!m) return a ? 'rgba(227,18,11,' + a + ')' : 'rgba(227,18,11,0)';
  const n = parseInt(m[1], 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
})();
