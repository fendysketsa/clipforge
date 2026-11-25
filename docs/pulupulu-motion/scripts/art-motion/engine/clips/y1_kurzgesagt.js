// Clip · Kurzgesagt-style flat explainer (y1): a deep-ink flat ground (when no theme is written; no more an indigo-purple gradient night sky), the flat centrepiece = the concept being explained; each bullet is a satellite node
// that pops out with a label capsule (108% overshoot) while signal flows along the connector. The ambient layer (twinkles, particles, signal pulses) always drifts gently; the centrepiece, nodes and labels hold still once settled,
// and the camera never slow-pushes uniformly: it pushes in about 30% only at a highlight moment, trucks across at the same magnification for consecutive highlights, then holds.
// spec-level data.camera 'smooth' (default — push 0.9s, node change 0.7s, sineInOut) | 'snap' (accent: fast push 0.28s, lateral truck 0.30s).
// The signature is a scale traverse: enter drives the camera logarithmically into a satellite until its colour fills the screen, then pulls out from a new centrepiece of the same colour — 'what is inside this'.
// cues: title (top title floats up letter by letter; text) · point (one satellite node on the current layer + label: text; data.color changes the accent colour)
//       highlight (the camera pushes into node data.index (counts points on the current layer only, 0-based; defaults to the newest) while the other nodes and labels dim; the push takes 1.2s)
//       enter (dive into node data.index (default the newest): push in → same colour fills the screen → pull out from a new centrepiece; text = the new centre's name (defaults to that node's name);
//              every point after it is a satellite of the new layer; dur defaults to 1.6s, and the push starts on this frame)
// data.center: the name of the first centrepiece. data.center_style: { color, shape: 'circle'|'rounded'|'hex'|'diamond', ring: true (adds an orbital ring) },
//   otherwise a neutral style is generated from the name (colour and shape come from the text, so the same name gives the same style; no orbital ring). data.image: puts an image inside the centrepiece (screenshot, photo, cropped to the shape), and the name moves into the capsule below.
//   A new layer's (entered) centrepiece takes that node's colour, with its shape likewise generated from the name; data.style on the enter cue can override.
// data.flow:true: nodes chain in order (centre→1→2→3), the signal runs through them in turn, and nodes carry sequence numbers — use it when explaining 'first, then'.
// Node placement is identical in landscape and portrait: ≤3 sit on the upper half-circle (left to right), ≥4 go all the way round (clockwise from the left). safe: layout sits only between top..H−bottom.
// spec.theme (film-wide palette, ctx.pal): flat bg ground (no gradient, no glow), twinkles and specks in sub at low opacity, connectors sub, signal accent2,
//   node colours accent / accent2 and their shades (data.color used as written), the centrepiece defaults to accent2, label capsules use the light palette's surface ground with ink text and the dark palette's ink ground with bg text, title in ink.
CLIPS.y1_kurzgesagt = (() => {
const { clamp, lerp, rng } = U;
// Default (no theme): deep-ink ground with barely visible tonal shading of the same hue; node / centrepiece colours avoid purple, magenta and violet-blue
const P0 = { sky: ['#0F1114', '#121417', '#171A1E'], star: '#F2EFE8', line: 'rgba(125,211,220,.35)', pulse: '#32BAEE', pulseCore: '#e9fdff', mote: '#fff6d0', pill: '#ffffff', pillInk: '#1B1A17', title: '#fff', ring: 'rgba(255,230,190,.55)', arrow: 'rgba(125,211,220,.7)', shadow: 'rgba(20,40,20,.25)' };
const ACC0 = ['#32BAEE', '#FACC12', '#E07A3F', '#5CD0B3', '#FC6255', '#A3B84B'];
// Neutral style for the centrepiece: colour and shape hashed from the name (same name, same style), no orbital ring
const CPAL0 = ['#4F86C6', '#3FA796', '#D99A3A', '#C8574A', '#5BA4CF', '#6FAF5A'], SHAPES = ['circle', 'rounded', 'hex'];
let P = P0, ACC = ACC0, CPAL = CPAL0, PL = null;
// Film-wide palette → this grammar's colour set (derived from 6 keys only)
const fromPal = p => { const dk = PAL.dark(p), spot = dk ? p.ink : p.sub;
  return { P: { sky: [p.bg], star: spot, line: PAL.alpha(p.sub, 0.5), pulse: p.accent2, pulseCore: PAL.mix(p.accent2, p.surface, 0.6), mote: spot, pill: dk ? p.ink : p.surface, pillInk: dk ? p.bg : p.ink, title: p.ink,
      ring: PAL.alpha(p.ink, 0.4), arrow: PAL.alpha(p.sub, 0.85), shadow: PAL.alpha(dk ? '#000000' : p.ink, dk ? 0.3 : 0.14) },
    ACC: [p.accent, p.accent2, PAL.mix(p.accent, p.ink, 0.35), PAL.mix(p.accent2, p.ink, 0.35), PAL.mix(p.accent, p.bg, 0.3), PAL.mix(p.accent2, p.bg, 0.3)],
    CPAL: [p.accent2] }; };
const hashStr = s => { let h = 2166136261; for (const ch of String(s)) h = Math.imul(h ^ ch.codePointAt(0), 16777619); return h >>> 0; };
const styleFor = (name, over = {}, col) => { const h = hashStr(name || '·'); return { color: over.color || col || CPAL[h % CPAL.length], shape: over.shape || SHAPES[(h >>> 8) % SHAPES.length], ring: !!over.ring }; };
const shapePath = (kind, x, y, R) => { const p = new Path2D();
  if (kind === 'rounded') p.roundRect(x - R * 0.92, y - R * 0.92, R * 1.84, R * 1.84, R * 0.36);
  else if (kind === 'hex') for (let i = 0; i <= 6; i++) { const a = Math.PI / 6 + i * Math.PI / 3; i ? p.lineTo(x + Math.cos(a) * R * 1.06, y + Math.sin(a) * R * 1.06) : p.moveTo(x + Math.cos(a) * R * 1.06, y + Math.sin(a) * R * 1.06); }
  else if (kind === 'diamond') { p.moveTo(x, y - R * 1.2); p.lineTo(x + R * 1.2, y); p.lineTo(x, y + R * 1.2); p.lineTo(x - R * 1.2, y); p.closePath(); }
  else p.arc(x, y, R, 0, Math.PI * 2);
  return p; };
const dark = (col, k = 0.72) => PAINT.rgb(PAINT.hex(col).map(v => v * k)), light = col => PAINT.rgb(PAINT.hex(col).map(v => v + (255 - v) * 0.4));
let S, levels, flow;
return {
  fonts: ['PuHui-Heavy', 'PuHui-Medium'],
  safe: true,
  init(ctx) {
    const { W, H, u, safe } = ctx, r = rng(11);
    PL = ctx.pal; if (PL) ({ P, ACC, CPAL } = fromPal(PL)); else { P = P0; ACC = ACC0; CPAL = CPAL0; }
    flow = !!ctx.data.flow;
    const y0 = safe.top + (ctx.of('title').length ? (ctx.portrait ? 300 : 210) * u : 60 * u), y1 = H - safe.bottom - 40 * u;
    const R = (ctx.portrait ? 160 : 140) * u, cx = W / 2, cy = (y0 + y1) / 2 + (ctx.portrait ? 0 : 30 * u);
    S = { cx, cy, R, stars: Array.from({ length: 160 }, () => ({ x: r() * W * 1.4 - W * 0.2, y: r() * H * 1.4 - H * 0.2, r: (0.8 + r() * r() * 3) * u, ph: r() * 6.28, sp: 1 + r() * 2.5 })),
      bokeh: Array.from({ length: 10 }, () => ({ x: r() * W * 1.3 - W * 0.15, y: r() * H * 1.3 - H * 0.15, r: (60 + r() * 150) * u, ph: r() * 6.28, a: 0.035 + r() * 0.04 })),
      motes: Array.from({ length: 24 }, () => ({ x: r() * W, y: r() * H, ph: r() * 6.28, d: 0.8 + r() * 0.5, s: (2 + r() * 3) * u })) };
    // layers: enter puts the points after it into a new layer
    const cs0 = styleFor(ctx.data.center || '', ctx.data.center_style || {});
    levels = [{ start: 0, center: ctx.data.center || '', col: cs0.color, style: cs0, img: ctx.data.image ? ctx.IMG[ctx.data.image] : null, pts: [], hls: [] }];
    for (const q of ctx.cues) {
      const L = levels[levels.length - 1];
      if (q.kind === 'point') L.pts.push(q);
      else if (q.kind === 'highlight') L.hls.push(q);
      else if (q.kind === 'enter') { const D = q.dur || 1.6; L.exit = { q, at: q.at, D, sw: q.at + D * 0.55, idx: q.data && q.data.index };
        levels.push({ start: q.at + D * 0.55, end0: q.at + D, center: '', col: null, pts: [], hls: [], from: L }); }
    }
    // node positions per layer (same angles in landscape and portrait: ≤3 on the upper half-circle left→right, ≥4 clockwise from the left through a full circle)
    const lab = 46 * u + 70 * u + 45 * u;                               // node radius + label offset + half a label height: even the bottom-most label has to stay above y1
    const rx = ctx.portrait ? W * 0.34 : Math.min(W * 0.32, 640 * u), ryHalf = Math.min(y1 - y0, H) * (ctx.portrait ? 0.3 : 0.42), ryRing = Math.min((y1 - y0) * (ctx.portrait ? 0.34 : 0.36), y1 - cy - lab, cy - y0 - 60 * u);
    levels.forEach((L, li) => {
      const n = L.pts.length, ring = n >= 4;
      L.orbit = { rx, ry: ring ? ryRing : ryHalf, ring };
      L.nodes = L.pts.map((q, i) => { const ang = ring ? Math.PI + i / n * Math.PI * 2 : Math.PI + (i + 0.5) / n * Math.PI;
        const ry = ring ? ryRing : ryHalf; return { q, i, x: cx + Math.cos(ang) * rx, y: cy + Math.sin(ang) * ry, col: (q.data && q.data.color) || ACC[(i + li * 2) % ACC.length] }; });
      if (L.exit) { const nd = L.exit.idx != null ? L.nodes[L.exit.idx] : L.nodes.filter(z => z.q.at <= L.exit.at).pop() || L.nodes[L.nodes.length - 1];
        L.exit.node = nd; const N = levels[li + 1]; N.col = nd ? nd.col : ACC[0]; N.center = L.exit.q.text || (nd && nd.q.text) || '';
        N.style = styleFor(N.center, (L.exit.q.data && L.exit.q.data.style) || {}, N.col); N.col = N.style.color; }
      // this layer's camera: hold; at a highlight moment push into the node (about 30% in, with the target nudged toward the centrepiece so the centre isn't cropped too much),
      //   and when already pushed in, the next highlight trucks across at the same magnification to the new node; then hold. Durations follow data.camera
      const Z = ctx.portrait ? 1.28 : 1.32; L.events = []; let zoomed = false;
      for (const h of L.hls) {
        const nd = h.data && h.data.index != null ? L.nodes[h.data.index] : L.nodes.filter(z => z.q.at <= h.at).pop(); if (!nd) continue;
        const snap = (ctx.data && ctx.data.camera) === 'snap';
        L.events.push(zoomed ? { at: h.at, kind: snap ? 'pan' : 'glide', x: lerp(nd.x, cx, 0.35), y: lerp(nd.y, cy, 0.35) } : { at: h.at, kind: 'to', x: lerp(nd.x, cx, 0.35), y: lerp(nd.y, cy, 0.35), z: Z, ...(snap ? { dur: MO.PULSE.punch, ease: MO.cubicInOut } : {}) });
        zoomed = true; h.node = nd;
      }
    });
  },
  draw(c, t, ctx) {
    const { W, H, u } = ctx;
    // current layer: past the switch point it's the new layer; the two layers cross-dissolve ±0.05s around it (both sides are the same colour filling the screen, so the cut is invisible)
    let k = 0; levels.forEach((L, i) => { if (i > 0 && t >= L.start) k = i; });
    drawLevel(c, k, t, ctx);
    const L = levels[k], ex = L.exit;
    if (ex && t > ex.sw - 0.05 && t < ex.sw) { const buf = UI.scratch('clip_y1x', W, H), g = buf.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W, H);
      drawLevel(g, k + 1, t, ctx); c.save(); c.globalAlpha = (t - (ex.sw - 0.05)) / 0.1; c.drawImage(buf, 0, 0); c.restore(); }
    // title: floats up letter by letter (screen space, not attached to the camera); fades out on the first highlight / enter
    const qt = ctx.of('title')[0];
    if (qt) { const nx = ctx.of('highlight', 'enter')[0], out = nx ? 1 - MO.sineInOut(clamp((t - nx.at) / 0.5)) : 1;
      if (out > 0) { c.save(); c.globalAlpha = out; const fs = TY.fit(c, qt.text || '', W * 0.88, (ctx.portrait ? 84 : 76) * u, 'PuHui-Heavy', { maxLines: 2, balance: true });
        fs.lines.forEach((ln, i) => TY.charsIn(c, ln, W / 2, ctx.safe.top + (ctx.portrait ? 200 : 130) * u + i * fs.size * 1.2, ctx.lt(t, qt.at) - i * 0.2, { font: `${fs.size}px "PuHui-Heavy"`, color: P.title, dur: 0.5, stagger: 0.045, dy: 30 * u, align: 'center', shadow: PL && !ctx.alpha ? null : { color: 'rgba(0,0,0,.5)', y: 6 * u, blur: ctx.alpha ? 14 * u : 0 } }));
        c.restore(); } }
  },
};
// Camera: this layer's move table; diving out → push into that node until it fills the screen; just dived in → pull out from the full-screen centrepiece
function camAt(L, t, ctx) {
  const { W, H } = ctx;
  if (L.from && t < L.end0) {                                            // pull-out: z falls logarithmically from 'centrepiece fills the screen' to 1, and the centrepiece returns from the screen centre to its own position
    const e = MO.cubicInOut(clamp((t - L.start) / (L.end0 - L.start))), Z = CAM.coverZoom(S.R * 0.84) * 1.15;   // 0.84: a diamond's or hexagon's inscribed circle is smaller than R and still has to fill the screen
    return CAM.anchor(S.cx, S.cy, CAM.zlerp(Z, 1, e), lerp(W / 2, S.cx, e), lerp(H / 2, S.cy, e));
  }
  const ex = L.exit;
  if (ex && t >= ex.at && ex.node) {                                      // push-in: logarithmic zoom, the node glides to the frame centre, pushed until its circle fills the screen
    const base = CAM.track({}, L.events, ex.at), e = MO.cubicIn(clamp((t - ex.at) / (ex.sw - ex.at)) ) * 0.5 + MO.cubicInOut(clamp((t - ex.at) / (ex.sw - ex.at))) * 0.5;
    return CAM.pushTo(base, ex.node.x, ex.node.y, CAM.coverZoom(46 * ctx.u) * 1.2, e, e);
  }
  return CAM.track({}, L.events, t);
}
function drawLevel(c, k, t, ctx) {
  const { W, H, u } = ctx, L = levels[k], cam = camAt(L, t, ctx), { cx, cy, R } = S;
  if (!ctx.alpha) {
    c.fillStyle = P.sky.length > 1 ? TOON.vgrad(c, 0, H, P.sky) : P.sky[0]; c.fillRect(0, 0, W, H);
    const sa = PL ? 0.35 : 1;                                             // over a palette ground the twinkles are just a faint texture
    CAM.layer(c, cam, 0.12, g => { for (const b of S.bokeh) { const k = 0.75 + 0.25 * Math.sin(t * 0.5 + b.ph); const bx = b.x + Math.sin(t * 0.2 + b.ph) * 14 * u, a = b.a * k * (PL ? 0.9 : 1.6), rgb = (PL ? PAINT.hex(P.star) : [125, 211, 220]).slice(0, 3).map(Math.round).join(','), gr = g.createRadialGradient(bx, b.y, b.r * 0.15, bx, b.y, b.r); gr.addColorStop(0, `rgba(${rgb},${a * 0.35})`); gr.addColorStop(0.8, `rgba(${rgb},${a * 0.55})`); gr.addColorStop(1, `rgba(${rgb},0)`); g.fillStyle = gr; g.beginPath(); g.arc(bx, b.y, b.r, 0, 7); g.fill(); } });
    CAM.layer(c, cam, 0.05, g => { for (const s of S.stars) { g.globalAlpha = sa * (0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * s.sp + s.ph))); g.fillStyle = P.star; g.beginPath(); g.arc(s.x, s.y, s.r, 0, 7); g.fill(); } g.globalAlpha = 1; });
  }
  // while a highlight is live: the pushed-in node is bright, the other nodes and labels dim
  const hNow = [...L.hls].reverse().find(h => t >= h.at && h.node), dimK = hNow ? MO.smooth(clamp((t - hNow.at) / 0.6)) : 0;
  const col = L.col, st = L.style, pull = L.from && t < L.end0 ? MO.smooth(clamp(((t - L.start) / (L.end0 - L.start) - 0.45) / 0.45)) : 1;   // just dived in: first it is flat colour filling the screen; names and rings only appear in the second half of the pull-out
  CAM.layer(c, cam, 1, g => {
    // node orbit: a very faint dashed ellipse giving the points a 'wrapped around the centre' structure (more nodes read as a full ring, ≤3 as the upper arc)
    if (L.orbit && L.nodes.length) { const o = L.orbit, a0 = L.orbit.ring ? 0 : Math.PI, a1 = L.orbit.ring ? Math.PI * 2 : Math.PI * 2, show = MO.cubicOut(clamp(ctx.lt(t, L.nodes[0].q.at) / 0.8));
      g.save(); g.globalAlpha = 0.5 * show * (1 - 0.6 * dimK); g.strokeStyle = P.line; g.lineWidth = 2 * u; g.setLineDash([2 * u, 14 * u]); g.lineCap = 'round'; g.beginPath(); g.ellipse(cx, cy, o.rx, o.ry, 0, a0, a0 + (a1 - a0) * show); g.stroke(); g.restore(); }
    // connectors + signal pulses (flow: centre→1→2→3 chained, signal running through in turn)
    L.nodes.forEach((nd, i) => {
      const l = ctx.lt(t, nd.q.at); if (l <= 0) return;
      const from = flow && i > 0 ? L.nodes[i - 1] : { x: cx, y: cy }, p = MO.cubicOut(clamp(l / 0.4)), ex = lerp(from.x, nd.x, p), ey = lerp(from.y, nd.y, p);
      g.save(); g.globalAlpha = 1 - 0.6 * dimK * (hNow && hNow.node === nd ? 0 : 1);
      g.strokeStyle = P.line; g.lineWidth = 4 * u; g.beginPath(); g.moveTo(from.x, from.y); g.lineTo(ex, ey); g.stroke();
      if (flow && l > 0.4) { const ax = lerp(from.x, nd.x, 0.55), ay = lerp(from.y, nd.y, 0.55), a = Math.atan2(nd.y - from.y, nd.x - from.x); g.fillStyle = P.arrow; g.translate(ax, ay); g.rotate(a); g.beginPath(); g.moveTo(10 * u, 0); g.lineTo(-8 * u, -9 * u); g.lineTo(-8 * u, 9 * u); g.closePath(); g.fill(); }
      g.restore();
      for (let kk = 0; kk < 3; kk++) { if (l < 0.4) break; const q = flow ? ((t * 0.7 - i * 0.33 + kk / 3) % 1 + 1) % 1 : ((l * 0.8 + kk / 3) % 1); const x = lerp(from.x, nd.x, q), y = lerp(from.y, nd.y, q); if (!PL) TOON.glow(g, x, y, 20 * u, P.pulse, 0.6 * (1 - 0.7 * dimK)); g.fillStyle = PL ? P.pulse : P.pulseCore; g.beginPath(); g.arc(x, y, (PL ? 7 : 5) * u, 0, 7); g.fill(); }
    });
    // centrepiece: two-tone facets plus a soft glow (shape and colour from data.center_style or generated from the name); optional orbital ring; with data.image the image is cropped into the shape
    const breath = 1 + 0.018 * Math.sin(t * 1.7), shape = shapePath(st.shape, cx, cy, R * breath);
    if (!PL) TOON.glow(g, cx, cy, R * 2.4, light(col), 0.28);
    TOON.flat(g, shape, col, dark(col), light(col), [-18 * u, 14 * u], [-6 * u, 5 * u]);
    if (L.img) { g.save(); g.clip(shapePath(st.shape, cx, cy, R * 0.9)); MD.cover(g, L.img, { x: cx - R, y: cy - R, w: 2 * R, h: 2 * R }); g.restore(); }
    if (st.ring) { g.save(); g.globalAlpha = pull; g.strokeStyle = P.ring; g.lineWidth = 6 * u; g.beginPath(); g.ellipse(cx, cy, R * 1.55, R * 0.35, -0.25, Math.PI * 1.05, Math.PI * 1.95); g.stroke(); g.restore(); }
    if (L.center && !L.img) { const f = TY.fitFloor(g, L.center, R * 1.7, 56 * u, 'PuHui-Heavy', { maxLines: 3, floor: 30 * u, balance: true });   // name inside the centrepiece: shrink to the floor, then wrap, then truncate
      g.save(); g.globalAlpha = pull; g.font = `${f.size}px "PuHui-Heavy"`; g.fillStyle = PL ? PAL.on(col, [PL.surface, PL.ink, PL.bg]) : '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle';
      f.lines.forEach((ln, i) => g.fillText(ln, cx, cy + (i - (f.lines.length - 1) / 2) * f.size * 1.1)); g.restore(); }
    else if (L.center) { const f = TY.fit(g, L.center, R * 3, 44 * u, 'PuHui-Heavy', { maxLines: 1, min: 0.6 });   // with an image: the name goes into the white capsule below
      g.save(); g.globalAlpha = pull; g.font = `${f.size}px "PuHui-Heavy"`; const tw = g.measureText(f.lines[0] || '').width, bw = tw + 56 * u, bh = f.size * 1.6, by = cy + R * 1.12;
      g.fillStyle = P.pill; g.beginPath(); g.roundRect(cx - bw / 2, by, bw, bh, bh / 2); g.fill(); g.fillStyle = P.pillInk; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(f.lines[0] || '', cx, by + bh / 2 + 2 * u); g.restore(); }
    // node + label capsule (pops in over 0.5s, 108% overshoot)
    for (const nd of L.nodes) {
      const l = ctx.lt(t, nd.q.at); if (l <= 0) continue;
      const on = hNow && hNow.node === nd, a = 1 - 0.65 * dimK * (on ? 0 : 1);
      const pop = MO.backOut(clamp(l / 0.5), 1.1), fy = l > 0.5 ? MO.float(t, 7 * u, 3.4, nd.i * 1.9) * clamp((l - 0.5) / 0.6) : 0, nr = 46 * u * pop * (on ? 1 + 0.15 * dimK : 1);
      g.save(); g.globalAlpha = a;
      if (!PL) TOON.glow(g, nd.x, nd.y + fy, nr * (on ? 4.2 : 2.6), nd.col, on ? 0.7 : 0.45);
      TOON.flat(g, TOON.circle(nd.x, nd.y + fy, nr), nd.col, dark(nd.col), PL ? light(nd.col) : '#ffffff', [-8 * u, -8 * u], [-3 * u, -3 * u]);
      if (l < 1.0) { const rp = clamp(l / 0.9); g.save(); g.globalAlpha = (1 - rp) * 0.55 * a; g.strokeStyle = nd.col; g.lineWidth = 4 * u * (1 - rp); g.beginPath(); g.arc(nd.x, nd.y + fy, nr * (1.1 + rp * 1.5), 0, 7); g.stroke(); g.restore(); }
      if (flow) { g.font = `${30 * u * pop}px "PuHui-Heavy"`; g.fillStyle = PL ? PAL.on(nd.col, [PL.surface, PL.ink, PL.bg]) : P.pillInk; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(String(nd.i + 1), nd.x, nd.y + fy + 2 * u); }
      const gone = L.exit ? 1 - clamp((t - L.exit.at) / 0.2) : 1;   // when diving in: this layer's labels all retract as soon as the push starts (otherwise they get magnified into half-screen white blocks, and so do the neighbours')
      const lp = MO.backOut(clamp((l - 0.15) / 0.5), 1.1) * gone; if (lp > 0) {
        const sc = lp * (on ? 1 + 0.18 * dimK : 1);
        const lf = TY.fitFloor(g, nd.q.text || '', ctx.W * 0.44 - 56 * u, (ctx.portrait ? 44 : 38) * u, 'PuHui-Medium', { maxLines: 1, floor: 30 * u }), lab = lf.lines[0] || '';   // a long label shrinks to the floor, then truncates with '…' rather than shrinking past legibility
        g.font = `${lf.size}px "PuHui-Medium"`; const tw = g.measureText(lab).width, bw = tw + 56 * u, bh = 70 * u;
        const ly = nd.y + fy + (nd.y < cy - R * 0.5 && ctx.portrait ? -nr - 70 * u : nr + 70 * u);   // label below the node (above it on the upper arc in portrait)
        const z = cam.z || 1, vx0 = cam.x - ctx.W / 2 / z, vx1 = cam.x + ctx.W / 2 / z, hw = bw * sc / 2 + 20 * u / z;   // the world range visible in the current shot (a gentle push carries labels at the edges off frame)
        const lx = nd.x > vx0 && nd.x < vx1 ? (vx1 - vx0 > 2 * hw ? clamp(nd.x, vx0 + hw, vx1 - hw) : cam.x) : nd.x;   // node on screen → clamp its label back on screen
        g.translate(lx, ly); g.scale(sc, sc);
        g.fillStyle = P.shadow; g.beginPath(); g.roundRect(-bw / 2 + 6 * u, -bh / 2 + 8 * u, bw, bh, bh / 2); g.fill();
        g.fillStyle = P.pill; g.beginPath(); g.roundRect(-bw / 2, -bh / 2, bw, bh, bh / 2); g.fill();
        if (on) { g.strokeStyle = nd.col; g.lineWidth = 5 * u * dimK; g.stroke(); }
        g.fillStyle = P.pillInk; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(lab, 0, 2 * u);
      }
      g.restore();
    }
    // firefly specks
    for (const m of S.motes) { const x = m.x + Math.sin(t * 0.8 + m.ph) * 30 * u, y = m.y - ((t * 22 * u + m.ph * 40 * u) % (120 * u)); g.globalAlpha = (PL ? 0.3 : 1) * (0.4 + 0.4 * Math.sin(t * 2 + m.ph)); g.fillStyle = P.mote; g.beginPath(); g.arc(x, y, m.s, 0, 7); g.fill(); }
    g.globalAlpha = 1;
  });
}
})();
