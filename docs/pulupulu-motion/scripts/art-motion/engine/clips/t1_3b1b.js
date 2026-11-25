// Clip · 3b1b / manim-style explainer (t1): pure black ground, only ever one thing on screen at a time — the one being talked about; text and equations are both Write (stroke first, then fill), and every ease is smooth.
// The signature move is Transform: the previous concept becomes the next one directly — no cut, no fade out and start over.
// cues: title (starts its Write on this frame; when another title arrives the old one FadeOuts and slides up; if too long, shrink the type first, then wrap to two lines)
//       equation (data.tokens = a DG.math token array, or just pass text; colour = concept name: col takes a manim colour name such as 'BLUE_C' or a #hex)
//                 every equation after the first is not Written again — it Transforms in from the previous one (TransformMatchingTex: same-named symbols move to their new position, unmatched ones fade out/in; 1.5s by default)
//       point (one bullet per line, Write; when a new bullet arrives the old ones turn grey)
//       line (Create the axes first, then draw the curve: data.values = [y...] (evenly spaced) or data.points = [[x,y]...]; text = curve label; data.color)
//            every line after the first is a Transform: the previous curve morphs into this one point by point (resampled by arc length), colour and label change with it, the axes stay put
//       highlight (Indicate + a yellow box that stays: data.index = which bullet (counts points only, 0-based; defaults to the newest); data.target = 'equation' boxes the equation)
// Layout: with a line, landscape puts text left / plot right, portrait puts plot on top / text below; the bullet block is vertically centred in the remaining height. safe: content is laid out only between top..H−bottom.
// An over-wide equation shrinks as a whole (every equation shares one size so the Transform doesn't jump), and long equations stay inside the frame in portrait.
// Glyphs: CMU italic draws θ as ϑ, so θ switches to EB Garamond italic (a closed θ); runs of two or more letters (softmax, ReLU) are set as upright words, only single letters are italic variables.
// alpha: on a transparent ground the text gets a dark outline so it stays readable over bright footage.
// spec.theme (the film-wide palette, ctx.pal): bg ground, ink text, sub for dimmed old bullets and the axes, accent for the emphasis box and Indicate, accent2 for the default curve colour;
//   manim colour names written in cues also map into the palette (YELLOW/GOLD/ORANGE/RED/MAROON/PINK → accent, BLUE/TEAL/GREEN/PURPLE → accent2, GREY → sub, WHITE → ink), and a #hex is used as written.
CLIPS.t1_3b1b = (() => {
const { clamp, lerp } = U;
let M, L, INK = '#fff';
const col = v => !v ? null : M[v] || v;
// With a film-wide palette, manim colour names → palette colours (only names present in DG.MANIM are recognised; #hex as-is)
const palMap = p => { const m = { ...DG.MANIM };
  for (const k in m) m[k] = /^(YELLOW|GOLD|ORANGE|RED|MAROON|PINK)/.test(k) ? p.accent : /^(BLUE|TEAL|GREEN|PURPLE)/.test(k) ? p.accent2 : /^GRE[YA]_[AB]$/.test(k) ? PAL.mix(p.sub, p.ink, 0.4) : /^GRE[YA]/.test(k) ? p.sub : k === 'WHITE' ? p.ink : k === 'BLACK' ? p.bg : m[k];
  return m; };
const isZh = ch => ch.codePointAt(0) >= 0x2E80;
// A run of text → tokens: CJK / full-width glyphs use PuHui; a run of ≥2 letters is a word (upright); a single letter is italic; everything else (digits, symbols, Greek letters) is upright
const toks = text => (String(text).match(/[A-Za-z]{2,}|./gu) || []).flatMap(s => s.length > 1 && !/[a-z]/.test(s) ? [...s] : [s])   // an all-caps run (QK) is several variables — split it up
  .map(s => ({ s, zh: isZh(s), it: /^[a-zA-Z]$/.test(s), gap: 0 }));
// θ is drawn in EB Garamond italic (CMU's θ is the ϑ glyph). Only this one token changes font: call DG.math per token, overriding DG.FONT for the duration
const THETA = /[θΘ]/;
const withFont = (tk, fn) => { if (!THETA.test(tk.s)) return fn(tk); const o = { ...DG.FONT }; DG.FONT.it = DG.FONT.rm = 'EBGaramond-400i';
  try { return fn({ ...tk, zh: false, it: true }); } finally { Object.assign(DG.FONT, o); } };
const layoutT = (c, tokens, size) => { let x = 0; return tokens.map(tk => { const w = withFont(tk, t2 => DG.layout(c, [{ ...t2, gap: 0 }], size)[0].w), sz = (tk.size || 1) * size;
  const r = { x, w }; x += w + (tk.gap != null ? tk.gap : sz * 0.06); return r; }); };
const widthT = (c, tokens, size) => { const l = layoutT(c, tokens, size); return l.length ? l[l.length - 1].x + l[l.length - 1].w : 0; };
// Write a run of tokens (equivalent to one DG.math call on the whole string: tokens stagger like manim's LaggedStart), returns each token's screen {x, w}
const writeT = (c, tokens, x, y, size, p, { align = 'center', col: cl = '#fff' } = {}) => {
  const Lt = layoutT(c, tokens, size), tot = Lt.length ? Lt[Lt.length - 1].x + Lt[Lt.length - 1].w : 0, x0 = align === 'center' ? x - tot / 2 : align === 'right' ? x - tot : x;
  const n = tokens.length, r = Math.min(4 / (n + 1), 0.2);
  tokens.forEach((tk, i) => { const q = MO.lagged(i, n, clamp(p), r); if (q > 0) withFont(tk, t2 => DG.math(c, [t2], x0 + Lt[i].x, y, size, { p: q, align: 'left', col: cl })); });
  return Lt.map(l => ({ x: x0 + l.x, w: l.w }));
};
// Resample to n points evenly by arc length (before a Transform two curves need the same point count and aligned starts)
const resample = (pts, n) => { const cum = DG.cum(pts), T = cum[cum.length - 1]; return Array.from({ length: n }, (_, i) => DG.pointAt(pts, cum, T * i / (n - 1))); };
// Wrap, but with every line the same length (never strand a single letter/word on the next line)
const balance = (g, text, maxW, font) => { const n = TY.wrap(g, text, maxW, font).length; if (n < 2) return [text];
  let lo = maxW * 0.4, hi = maxW; for (let k = 0; k < 14; k++) { const m = (lo + hi) / 2; if (TY.wrap(g, text, m, font).length > n) lo = m; else hi = m; } return TY.wrap(g, text, hi, font); };
// Title: shrink the type until it fits on one line (0.75 minimum), otherwise wrap into balanced lines (3 max in portrait, 2 in landscape), then shrink until every line fits
const titleLines = (c, text, maxW, size, maxLines) => {
  let s = size; while (s > size * 0.75 && widthT(c, toks(text), s) > maxW) s *= 0.95;
  if (widthT(c, toks(text), s) <= maxW) return { size: s, lines: [text] };
  s = size * 0.9; let lines = balance(c, text, maxW, `${s}px "PuHui-Medium"`);
  while (lines.length > maxLines) { s *= 0.94; lines = balance(c, text, maxW, `${s}px "PuHui-Medium"`); }
  while (s > size * 0.45 && Math.max(...lines.map(l => widthT(c, toks(l), s))) > maxW) s *= 0.95;
  return { size: s, lines };
};
let BUF;
return {
  fonts: ['PuHui-Medium'],
  safe: true,
  init(ctx) {
    M = ctx.pal ? palMap(ctx.pal) : DG.MANIM; INK = ctx.pal ? ctx.pal.ink : '#fff'; DG.FONT.zh = 'PuHui-Medium';                         // any CJK: PuHui (the Source Han Serif subset only carries the glyphs the demo film uses)
    const { W, H, u, safe } = ctx, g = document.createElement('canvas').getContext('2d');
    const pad = (ctx.portrait ? 70 : 140) * u, yTop = safe.top, yBot = H - safe.bottom - (ctx.portrait ? 90 : 70) * u;
    const hasLine = ctx.of('line').length > 0, hasEq = ctx.of('equation').length > 0;
    // title
    const titles = ctx.of('title').map(q => ({ q, ...titleLines(g, q.text || '', W - 2 * pad, (ctx.portrait ? 72 : 62) * u, ctx.portrait ? 3 : 2) }));
    const tH = titles.length ? Math.max(...titles.map(z => z.lines.length * z.size * 1.25)) : 0;
    const titleY = yTop + (ctx.portrait ? 170 : 130) * u;
    let y = titles.length ? titleY + tH : yTop + 90 * u;
    let eqSz = (ctx.portrait ? 72 : 66) * u;
    for (const q of ctx.of('equation')) { const tk = q.data && q.data.tokens ? q.data.tokens : toks(q.text || ''), w = widthT(g, tk, eqSz) + 60 * u; if (w > W - 2 * pad) eqSz *= (W - 2 * pad) / w; }
    const eqY = y + eqSz * (titles.length ? 1.15 : 0.9);
    if (hasEq) y = eqY + eqSz * 0.6;
    y += 30 * u;
    // bullets: pre-wrap them (each may span several lines)
    const size0 = (hasLine ? (ctx.portrait ? 56 : 50) : (ctx.portrait ? 62 : 58)) * u;
    let text, plot = null;
    if (hasLine && ctx.portrait) { plot = { x: pad + 20 * u, y: y + 20 * u, w: W - 2 * pad - 20 * u, h: (yBot - y) * 0.5 }; text = { x: pad, y0: plot.y + plot.h + 70 * u, y1: yBot, w: W - 2 * pad }; }
    else if (hasLine) { plot = { x: W * 0.52, y: y + 20 * u, w: W * 0.48 - pad, h: yBot - y - 40 * u }; text = { x: pad, y0: y, y1: yBot, w: W * 0.47 - pad }; }
    else text = { x: pad, y0: y, y1: yBot, w: W - 2 * pad };
    // bullets don't fit (portrait, curve present, many bullets): first let the curve give way (portrait 50% → 30% minimum), then shrink the type (0.6× floor) — never push into safe.bottom
    let points, blockH, size = size0; const gapP = 36 * u, room = yBot - y;
    for (let k = 1; ; k *= 0.94) {
      size = size0 * k;
      points = ctx.of('point').map(q => { const lines = balance(g, q.text || '', text.w - 50 * u, `${size}px "PuHui-Medium"`); return { q, lines, h: lines.length * size * 1.35 }; });
      blockH = points.reduce((s, p) => s + p.h + gapP, 0) - gapP;
      if (plot && ctx.portrait) { plot.h = Math.max(room * 0.3, Math.min(room * 0.5, room - 110 * u - blockH)); text.y0 = plot.y + plot.h + 70 * u; }
      if (blockH <= text.y1 - text.y0 || k < 0.6) break;
    }
    if (blockH > text.y1 - text.y0 + 1) console.warn(`t1: ${points.length} bullets still don't fit at 0.6× type (overflowing by ${Math.round(blockH - (text.y1 - text.y0))}px): when a new bullet arrives the whole block scrolls up and the earliest fades out — to keep them all on screen delete a few or split into two segments`);
    let py = text.y0 + Math.max(0, (text.y1 - text.y0 - blockH) / 2) * (hasLine && !ctx.portrait ? 1 : 0.6);   // bullet block vertically centred (slightly high in portrait)
    for (const p of points) { p.y = py + size; py += p.h + gapP; p.need = Math.max(0, py - gapP - text.y1); }   // need: how far the block must scroll up when this bullet arrives so it doesn't cross y1
    // curve: coordinates use the data range across all lines (so the axes don't move during a Transform)
    const lines = ctx.of('line').map(q => { const d = q.data || {}; return { q, d, pts0: d.points || (d.values || []).map((v, i) => [i, v]) }; }).filter(l => l.pts0.length >= 2);
    if (plot && lines.length) {
      const all = lines.flatMap(l => l.pts0), xs = all.map(p => p[0]), ys = all.map(p => p[1]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys); let y1 = Math.max(...ys); if (y1 === y0) y1 = y0 + 1;
      plot.X = v => plot.x + (v - x0) / ((x1 - x0) || 1) * plot.w; plot.Y = v => plot.y + plot.h - (v - y0) / (y1 - y0) * plot.h * 0.9;
      for (const l of lines) { const [lx0, lx1] = [Math.min(...l.pts0.map(p => p[0])), Math.max(...l.pts0.map(p => p[0]))];
        // each curve stretches across the full plot width (different lines may measure x in different units: loss-parameter → loss-step)
        l.scr = l.pts0.map(([px, py]) => [plot.x + (px - lx0) / ((lx1 - lx0) || 1) * plot.w, plot.Y(py)]); l.rs = resample(l.scr, 160); }
    }
    L = { titleY, titles, eqY, eqSz, text, plot, points, size, lines };
  },
  draw(c0, t, ctx) {
    const { W, H, u } = ctx;
    const c = ctx.alpha ? (BUF = BUF || document.createElement('canvas'), BUF.width = W, BUF.height = H, BUF.getContext('2d')) : c0;
    if (!ctx.alpha) { c.fillStyle = ctx.pal ? ctx.pal.bg : '#000'; c.fillRect(0, 0, W, H); }
    // ---- title (only one at a time; changing title = the old one slides up and fades out, the new one Writes) ----
    L.titles.forEach((z, i) => {
      const q = z.q, nx = L.titles[i + 1], out = nx ? MO.smooth(MO.seg(t, nx.q.at - 0.45, nx.q.at)) : 0; if (out >= 1 || ctx.lt(t, q.at) <= 0) return;
      const n = [...(q.text || '')].length, dur = q.dur || clamp(n / 14, 0.6, 1.6);
      c.save(); c.globalAlpha = 1 - out; c.translate(0, -50 * u * out);
      z.lines.forEach((ln, k) => writeT(c, toks(ln), W / 2, L.titleY + k * z.size * 1.25, z.size, ctx.p(t, q.at + k * dur / z.lines.length, dur / z.lines.length), { col: col(q.data && q.data.color) || INK }));
      c.restore();
    });
    // ---- equations: the first is Written, each later one Transforms in from the previous via TransformMatchingTex ----
    let eqBox = null;
    const eqs = ctx.of('equation').map(q => (q.data && q.data.tokens ? q.data.tokens : toks(q.text || '')).map(k => ({ ...k, col: col(k.col) })));
    const eqCues = ctx.of('equation'), sz = L.eqSz;
    let k = -1; eqCues.forEach((q, i) => { if (ctx.lt(t, q.at) > 0) k = i; });
    if (k >= 0) {
      const q = eqCues[k], tk = eqs[k], Ln = layoutT(c, tk, sz), tot = Ln.length ? Ln[Ln.length - 1].x + Ln[Ln.length - 1].w : 0, x0 = W / 2 - tot / 2;
      if (k === 0) writeT(c, tk, W / 2, L.eqY, sz, ctx.p(t, q.at, q.dur || 1.2), { col: INK });
      else {
        const p = MO.smooth(ctx.p(t, q.at, q.dur || 1.5)), old = eqs[k - 1], Lo = layoutT(c, old, sz), toto = Lo.length ? Lo[Lo.length - 1].x + Lo[Lo.length - 1].w : 0, xo = W / 2 - toto / 2;
        const used = new Set(), from = tk.map(nt => { const j = old.findIndex((ot, jj) => !used.has(jj) && ot.s === nt.s && (ot.sub || '') === (nt.sub || '') && (ot.sup || '') === (nt.sup || '')); if (j >= 0) used.add(j); return j; });
        const one = (tok, x, a, cl) => { if (a <= 0) return; c.save(); c.globalAlpha *= a; withFont(tok, t2 => DG.math(c, [{ ...t2, col: cl }], x, L.eqY, sz, { p: 1, align: 'left' })); c.restore(); };
        old.forEach((ot, j) => { if (!used.has(j)) { c.save(); c.translate(0, -30 * u * p); one(ot, xo + Lo[j].x, 1 - clamp(p * 1.6), ot.col || INK); c.restore(); } });   // unmatched old symbols: fade out and slide up
        tk.forEach((nt, i) => { const j = from[i];
          if (j >= 0) one(nt, lerp(xo + Lo[j].x, x0 + Ln[i].x, p), 1, DG.mix(old[j].col || INK, nt.col || INK, p));    // same-named symbol: move to its new position, colour interpolated
          else { c.save(); c.translate(0, 30 * u * (1 - p)); one(nt, x0 + Ln[i].x, clamp((p - 0.35) / 0.65), nt.col || INK); c.restore(); } });   // new symbol: fade in
      }
      if (Ln.length) eqBox = { x: x0 - 20 * u, y: L.eqY - sz * 0.95, w: tot + 40 * u, h: sz * 1.35 };
    }
    // ---- axes + curve: the first is Created, each later one morphs point by point from the previous ----
    const P = L.plot;
    if (P && L.lines.length) {
      const l0 = L.lines[0];
      if (ctx.lt(t, l0.q.at) > 0) {
        const ap = MO.smooth(ctx.p(t, l0.q.at, 0.6)), lw = 3 * u;
        c.save(); c.strokeStyle = M.GREY_B; c.lineWidth = lw; c.lineCap = 'round';
        c.beginPath(); c.moveTo(P.x, P.Y(0)); c.lineTo(P.x + P.w * ap, P.Y(0)); c.moveTo(P.x, P.y + P.h); c.lineTo(P.x, P.y + P.h - P.h * ap); c.stroke();
        c.globalAlpha = ap; for (let kk = 1; kk <= 4; kk++) { const xx = P.x + P.w * kk / 4; c.beginPath(); c.moveTo(xx, P.Y(0) - 8 * u); c.lineTo(xx, P.Y(0) + 8 * u); c.stroke(); }
        c.restore();
        let j = 0; L.lines.forEach((l, i) => { if (ctx.lt(t, l.q.at) > 0) j = i; });
        const l = L.lines[j], lc = col(l.d.color) || M.BLUE_C;
        c.save(); c.lineWidth = 5 * u; c.lineJoin = 'round'; c.lineCap = 'round';
        if (j === 0) {
          const cp = MO.smooth(ctx.p(t, l.q.at + 0.5, l.q.dur || 1.4));
          if (cp > 0) { const cum = DG.cum(l.scr); c.strokeStyle = lc; const tip = DG.drawPartial(c, l.scr, cum, cum[cum.length - 1] * cp);
            if (cp < 1) DG.neuron(c, tip[0], tip[1], 10 * u, 1, { fill: lc, stroke: INK, lw: 2 * u }); }
          label(c, l, MO.smooth(MO.seg(cp, 0.8, 1)), lc, u);
        } else {
          const pv = L.lines[j - 1], p = MO.smooth(ctx.p(t, l.q.at, l.q.dur || 1.5)), pc = col(pv.d.color) || M.BLUE_C;
          const pts = DG.morph(pv.rs, l.rs, p); c.strokeStyle = DG.mix(pc, lc, p); c.beginPath(); pts.forEach((q, i) => i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1])); c.stroke();
          label(c, pv, 1 - clamp(p * 2), pc, u); label(c, l, clamp(p * 2 - 1), lc, u);
        }
        c.restore();
      }
    }
    // ---- bullets ----
    const hl = ctx.of('highlight'), size = L.size;
    const target = h => h.data && h.data.target === 'equation' ? -2 : h.data && h.data.index != null ? h.data.index : L.points.filter(p => p.q.at <= h.at).length - 1;
    const roll = Math.max(0, ...L.points.map(p => p.need * MO.smooth(ctx.p(t, p.q.at - 0.3, 0.4))));   // when they don't fit: 0.3s before a new bullet the block scrolls up and whatever crosses the top fades out
    L.points.forEach((it0, i) => {
      const q = it0.q; if (ctx.lt(t, q.at) <= 0) return;
      const it = roll ? { ...it0, y: it0.y - roll } : it0, over = L.text.y0 - (it.y - size);
      if (over > 0 && clamp(1 - over / (size * 1.2)) <= 0) return;
      c.save(); if (over > 0) c.globalAlpha *= clamp(1 - over / (size * 1.2));
      const nx = L.points[i + 1], h = [...hl].reverse().find(z => target(z) === i && t >= z.at - 1e-6) || null, hOther = hl.some(z => t >= z.at && target(z) !== i && z.at > (h ? h.at : -1));
      const dimN = nx ? MO.smooth(ctx.p(t, nx.q.at, 0.4)) : 0;
      const n = [...(q.text || '')].length, dur = q.dur || clamp(n / 16, 0.6, 1.8);
      // Indicate: scale to 1.2, tint yellow, come back; afterwards this bullet stays yellow (the emphasis is kept) while the rest go grey
      const ip = h && !hOther ? ctx.p(t, h.at, 0.8) : 0, ind = DG.indicate(ip), keep = h && !hOther ? MO.smooth(clamp(ip * 2)) : 0;
      const dim = keep > 0 ? 0 : dimN;
      const base = DG.mixA(DG.mixA(INK, M.GREY_C, dim), M.YELLOW, Math.max(keep, ind.k)), colr = DG.rgba(base);
      const bx = L.text.x + 14 * u, by = it.y - size * 0.36;
      c.save(); c.translate(bx, by); c.scale(ind.s, ind.s); c.translate(-bx, -by);
      DG.neuron(c, bx, by, 12 * u, 1 - dim * 0.6, { lw: 2 * u, stroke: colr, fill: col(q.data && q.data.color) || M.BLUE_C, sa: MO.smooth(ctx.p(t, q.at, 0.3)) });
      let wMax = 0;
      it.lines.forEach((ln, kk) => { const r = writeT(c, toks(ln), L.text.x + 50 * u, it.y + kk * size * 1.35, size, ctx.p(t, q.at + kk * dur / it.lines.length, dur / it.lines.length), { align: 'left', col: colr });
        if (r.length) wMax = Math.max(wMax, r[r.length - 1].x + r[r.length - 1].w - (L.text.x + 50 * u)); });
      c.restore();
      if (h && !hOther) box(c, L.text.x - 16 * u, it.y - size * 1.05, wMax + 90 * u, it.lines.length * size * 1.35 + 18 * u, ctx.lt(t, h.at), u);
      c.restore();
    });
    const he = [...hl].reverse().find(z => target(z) === -2 && t >= z.at);
    if (he && eqBox && !hl.some(z => t >= z.at && z.at > he.at)) box(c, eqBox.x, eqBox.y, eqBox.w, eqBox.h, ctx.lt(t, he.at), u);
    if (ctx.alpha) { c0.save(); c0.shadowColor = 'rgba(0,0,0,0.9)'; c0.shadowBlur = 10 * u; c0.drawImage(BUF, 0, 0); c0.shadowBlur = 3 * u; c0.drawImage(BUF, 0, 0); c0.restore(); }
  },
};
// curve label: sits above the end of the curve
function label(c, l, a, colr, u) { if (!l.q.text || a <= 0) return; const e = l.scr[l.scr.length - 1];
  c.save(); c.globalAlpha *= a; c.font = `${40 * u}px "PuHui-Medium"`; c.fillStyle = colr; c.textAlign = 'right'; c.fillText(l.q.text, e[0], e[1] - 30 * u); c.restore(); }
// emphasis box: Circumscribe runs a lap first (1s) while SurroundingRectangle draws itself and stays (final frame holds the focus)
function box(c, x, y, w, h, lt, u) {
  if (lt <= 0) return; DG.circumscribe(c, x - 8 * u, y - 8 * u, w + 16 * u, h + 16 * u, MO.seg(lt, 0, 1.0), { lw: 4 * u, col: M.YELLOW });
  const p = MO.smooth(MO.seg(lt, 0.3, 1.0)); if (p <= 0) return;
  const pts = DG.rectPts(x + w / 2, y + h / 2, w, h, 120); c.save(); c.strokeStyle = M.YELLOW; c.lineWidth = 3 * u; c.lineJoin = 'round';
  DG.drawPartial(c, [...pts, pts[0]], DG.cum([...pts, pts[0]]), DG.len([...pts, pts[0]]) * p); c.restore();
}
})();
