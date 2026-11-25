// Clip · Vox-style collage (y2): one big desk = the world; material is laid out on the desk in appearance order and joined by red lines; the camera tracks across smoothly at 60fps,
// while things on the desk (slides, highlighter, red circle, typing) step at 12fps 'on twos'.
// cues: image | clip (screenshot / photo / clipping: an image path, or frames = a recorded frame sequence; a print (white border, aged paper, tape, MD.print); text optional = a black torn-edge label pressed into the bottom-left corner (typed at 12fps);
//              data.halftone:true converts to greyscale dots, original colour is kept by default; data.fit:'cover' crops to data.aspect (default 16:9 / portrait 4:5) around data.focus=[fx,fy] to fill the frame, by default it scales to fit without cropping; starts sliding in on this frame)
//       title (Borders-style white-on-black label strip, typing at 13 chars/sec) · point (index card with rules, typed)
//       highlight (data.rect=[x,y,w,h] (0..1, relative to the image) on the current image: from at the highlighter sweeps over → the red pen circles it → the camera pushes into that region)
// Photos and screenshots are the leads: while the camera rests on one it takes up eight or nine tenths of the frame (landscape width ≈90%, or height ≈86%). Landscape material runs left→right, portrait top→bottom;
// camera: move before the next item's at (the red line is drawn out first, then the camera follows), push into the region on a highlight, and hold the rest of the time.
//   spec-level data.camera 'smooth' (default — 0.7s to find the next item, 0.9s push, sineInOut, matching Vox's measured 0.5–1.5s) | 'snap' (accent: lateral truck 0.30s, fast push 0.28s).
// spec.theme (film-wide palette, ctx.pal): desk-paper ground in bg, index cards in surface with ink text, title strips ink ground with surface text, red lines / pins / red circles in accent,
//   index-card rules in a light accent2, the highlighter brightens with accent; a photo's print border and tape are physical props and stay as they are.
CLIPS.y2_vox = (() => {
const { clamp, lerp, rng } = U;
const C0 = { desk: '#e4ddcf', ink: '#171716', red: '#b8433f', paper: '#eeedeb', card: '#f6f4ee', fiber: [110, 95, 70], rule: 'rgba(80,140,200,.3)', margin: 'rgba(184,67,63,.5)', vig: '40,30,20', hi: undefined };
let C = C0;
const fromPal = p => ({ desk: p.bg, ink: p.ink, red: p.accent, paper: p.surface, card: p.surface, fiber: PAL.rgb(p.sub), rule: PAL.alpha(p.accent2, 0.3), margin: PAL.alpha(p.accent, 0.5),
  vig: PAL.rgb(PAL.dark(p) ? '#000000' : p.ink).join(','), hi: PAL.alpha(PAL.mix(p.accent, '#FFFFFF', 0.35), 0.85) });
const BOLD = '"PuHui-Heavy"', TXT = '"PuHui-Bold"';
let items, keys, strings;
// on-twos clip time: already >0 on this frame
const ls = (t, at) => MO.step(t - at + 1e-6, 12) + 1 / 12;
return {
  fonts: ['PuHui-Heavy', 'PuHui-Bold'],
  safe: true,
  init(ctx) {
    const { W, H, u, portrait } = ctx, r = rng(7), g = document.createElement('canvas').getContext('2d');
    C = ctx.pal ? fromPal(ctx.pal) : C0;
    items = []; let cur = 0, prev = null;
    for (const q of ctx.of('image', 'clip', 'title', 'point')) {
      let w, h, kind = q.kind === 'clip' ? 'image' : q.kind, lines = null, size = 0;
      if (kind === 'image') {
        const im = ctx.still(q); if (!im) continue;
        const [iw, ih] = MD.size(im), cov = q.data && q.data.fit === 'cover', ar = cov ? (q.data.aspect || (portrait ? 0.8 : 16 / 9)) : iw / ih;
        const bw = W * (portrait ? 0.86 : 0.78), bh = H * (portrait ? 0.5 : 0.76), f = CLIP.fit(ar, 1, 0, 0, bw, bh);
        w = f.w + 32 * u; h = f.h + 32 * u;
      } else {
        if (!String(q.text ?? '').trim()) { console.warn(`y2 ${q.kind} at=${q.at}: text is empty, skipping this card`); continue; }   // an empty card is −Infinity wide and the torn-edge point run would loop forever
        size = (kind === 'title' ? 64 : 48) * u;
        lines = TY.wrap(g, q.text || '', W * (portrait ? 0.74 : 0.5), `${size}px ${kind === 'title' ? BOLD : TXT}`);
        g.font = `${size}px ${kind === 'title' ? BOLD : TXT}`;
        w = Math.max(...lines.map(l => g.measureText(l).width)) + (kind === 'title' ? 80 : 110) * u; h = lines.length * size * 1.45 + (kind === 'title' ? 50 : 100) * u;
      }
      const gap = 260 * u, jitter = (r() - 0.5) * (portrait ? W * 0.12 : H * 0.12);
      const x = portrait ? W / 2 + jitter : (prev ? prev.x + prev.w / 2 + gap + w / 2 : W / 2);
      const y = portrait ? (prev ? prev.y + prev.h / 2 + gap + h / 2 : H / 2) : H / 2 + jitter;
      const it = { q, kind, x, y, w, h, rot: (r() - 0.5) * 0.07, lines, size, seed: 11 + items.length * 7 };
      items.push(it); prev = it; cur++;
    }
    // typing speed for text cards and the 'finished reading' moment: 13 chars/sec by default; if it's too close to the next item, speed up (40 chars/sec max) so it finishes typing before the camera moves, then holds 0.5s to let people read
    items.forEach((it, i) => {
      if (it.kind === 'image') { it.done = it.q.at + 0.6; return; }
      const nC = [...(it.q.text || '')].length, next = items[i + 1] ? items[i + 1].q.at : ctx.dur;
      it.cps = clamp(nC / Math.max(0.3, next - it.q.at - 0.95 - 0.5), 13, 40);
      it.done = it.q.at + nC / it.cps + 0.5;
    });
    // red line: pin the previous item's right edge (bottom edge in portrait) to the next item's left edge (top edge)
    strings = items.slice(1).map((b, i) => { const a = items[i];
      const pa = portrait ? [a.x + a.w * 0.2, a.y + a.h / 2 - 20 * u] : [a.x + a.w / 2 - 30 * u, a.y + a.h * 0.25];
      const pb = portrait ? [b.x - b.w * 0.2, b.y - b.h / 2 + 20 * u] : [b.x - b.w / 2 + 30 * u, b.y - b.h * 0.25];
      const pts = CL.stringPts(pa, pb, 0.06); return { a: pa, b: pb, pts, cum: DG.cum(pts), at: b.q.at }; });
    // camera keyframes: start tracking ≈0.9s before each item arrives (long tail), settle before its at; push into the region on a highlight
    const Hs = H - ctx.safe.top - ctx.safe.bottom;                           // usable height once the caption band is clear; the frame centre shifts with it (translated in draw)
    const zFor = it => it.kind === 'image' ? clamp(Math.min(W * 0.9 / it.w, Hs * 0.86 / it.h), 0.5, 2.4) : clamp(Math.min(W * 0.82 / it.w, Hs * 0.8 / it.h), 0.5, 1.6);   // photos fill the frame, text cards stay smaller
    keys = []; let last = null;
    const snap = (ctx.data && ctx.data.camera) === 'snap', MV = snap ? { next: MO.PULSE.pan, in: MO.PULSE.punch, ease: MO.cubicInOut } : { next: MO.PULSE.glide, in: MO.PULSE.push, ease: MO.sineInOut };
    const hls = ctx.of('highlight');
    const events = [...items.map(it => ({ at: it.q.at, it })), ...hls.map(h => ({ at: h.at, h }))].sort((a, b) => a.at - b.at);
    let curItem = null;
    for (const e of events) {
      if (e.it) {
        const tgt = { x: e.it.x, y: e.it.y, z: zFor(e.it) };
        if (!last) { keys.push({ t: 0, ...tgt }); }
        else { const P = MV.next, t0 = Math.max(last.t + 0.05, e.at - P - 1 / ctx.FPS), t1 = t0 + P;   // move to the next item, arriving one frame before at (if the previous move hasn't finished, keep going from there)
          keys.push({ t: t0, x: last.x, y: last.y, z: last.z }); keys.push({ t: t1, ...tgt, ease: MV.ease }); }
        last = keys[keys.length - 1]; curItem = e.it;
      } else if (curItem && curItem.kind === 'image' && e.h.data && e.h.data.rect) {
        const R = e.h.data.rect, ib = imgBox(curItem, u);
        const cx = curItem.x + (ib.x + (R[0] + R[2] / 2) * ib.w) - curItem.w / 2, cy = curItem.y + (ib.y + (R[1] + R[3] / 2) * ib.h) - curItem.h / 2;
        const rw = R[2] * ib.w, rh = R[3] * ib.h;
        let zFit = Math.min(W * 0.8 / (rw * 1.4 + 32 * u), Hs * 0.8 / (rh * 1.44 + 20 * u));   // the red circle (the ellipse in drawItem below) has to stay wholly on frame after the push, with a tenth of margin each side (review: at 0.9 a shaky circle and motion blur still ran off frame)
        if (R[2] >= 0.5) zFit = Math.min(zFit, Math.max(last.z, W * 0.96 / curItem.w));          // the region covers over half the image: pushing in would only cut off the text either side of it, so don't
        const z = Math.min(clamp(Math.min(W * (ctx.portrait ? 0.78 : 0.55) / rw, Hs * 0.55 / rh), last.z, last.z * 2.6), zFit);   // width is the bottleneck in portrait: the region pushes to about eight tenths of the frame width
        // the region's start (where the highlighter sweeps in from the left edge) is visible in the current shot: draw first, push at at+0.2; not visible (it went off frame after the last push):
        // move the camera there first and arrive one frame before at, then reveal — otherwise the reveal frame is off screen and the audience only sees it 0.2s or more late (measured 7 frames late in portrait, 2026-10)
        const x0 = cx - rw / 2, inView = Math.abs(x0 - last.x) * last.z < W / 2 - 20 * u && Math.abs(cy - last.y) * last.z < Hs / 2 - rh * last.z / 2;
        const P = MV.in, t0 = inView ? Math.max(last.t + 0.05, e.at + 0.2) : Math.max(last.t + 0.05, e.at - P - 1 / ctx.FPS), t1 = t0 + P;   // push in (gentle by default, fast for snap)
        keys.push({ t: t0, x: last.x, y: last.y, z: last.z }); keys.push({ t: t1, x: cx, y: cy, z, ease: MV.ease });
        last = keys[keys.length - 1];
      }
    }
    if (!keys.length) keys.push({ t: 0, x: W / 2, y: H / 2, z: 1 });
    const end = keys[keys.length - 1]; keys.push({ t: Math.max(end.t + 0.01, ctx.dur), x: end.x, y: end.y, z: end.z, ease: MO.linear });   // hold after the last move
  },
  draw(c, t, ctx) {
    const { W, H, u } = ctx, cam = CAM.at(keys, t);
    const buf = UI.scratch('clip_vox', W, H), g = buf.getContext('2d'); g.reset();
    g.save(); g.translate(0, (ctx.safe.top - ctx.safe.bottom) / 2); CAM.apply(g, cam);
    if (!ctx.alpha) { g.fillStyle = g.createPattern(CL.paperTile('clipdesk' + (C === C0 ? '' : '_' + C.desk), C.desk, { amt: 12, fibers: 320, fiberCol: C.fiber }), 'repeat'); const s = 4 / cam.z; g.fillRect(cam.x - W * s, cam.y - H * s, W * 2 * s, H * 2 * s); }
    // red line: drawn out as the next item arrives (12fps)
    for (const s of strings) { const q = MO.sineInOut(clamp(ls(t, s.at - 0.9) / 0.7)); if (t < s.at - 0.9) continue;
      CL.string(g, s.pts, s.cum, s.cum[s.cum.length - 1] * q, { col: C.red, lw: 5 * u }); CL.pin(g, s.a[0], s.a[1], C.red); if (q >= 1) CL.pin(g, s.b[0], s.b[1], C.red); }
    for (const it of items) {
      const q = it.q; if (t < q.at - 1e-6) continue;
      // on-twos counts from at (ls), not from an absolute 12fps grid: snapping to the grid makes material appear 1–2 frames before its cue (measured 2 frames early in portrait, 2026-10)
      CL.slideIn(g, q.at + ls(t, q.at), q.at, it.x, it.y, it.rot, gg => drawItem(gg, it, t, ctx), { from: ctx.portrait ? [120 * u, 360 * u] : [420 * u, -60 * u], tilt: 0.2, dur: 0.55, fps: 1e6 });
    }
    g.restore();
    const [vx, vy] = CAM.velocity(tt => CAM.at(keys, tt), t);
    if (Math.hypot(vx, vy) >= 1.5) c.drawImage(buf, 0, 0);   // lay down an undrifted copy first: motionBlur's first pass is already offset, leaving a translucent rim on all four edges (a grey border in the export)
    CAM.motionBlur(c, buf, vx * 0.6, vy * 0.6, 7);
    if (!ctx.alpha) {                                                   // vignette + static grain (the paper texture is pinned, it doesn't jitter frame to frame)
      const v = PAINT.cached('clip_vox_vig' + W + 'x' + H + C.vig, W, H, gg => { const r = gg.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.45, W / 2, H / 2, Math.max(W, H) * 0.62); r.addColorStop(0, `rgba(${C.vig},0)`); r.addColorStop(1, `rgba(${C.vig},${C === C0 ? .34 : .18})`); gg.fillStyle = r; gg.fillRect(0, 0, W, H); });
      c.drawImage(v, 0, 0);
    }
  },
};
function imgBox(it, u) { return { x: 16 * u, y: 16 * u, w: it.w - 32 * u, h: it.h - 32 * u }; }   // the image rect inside a print (relative to the print's top-left)
function drawItem(g, it, t, ctx) {
  const { u } = ctx, q = it.q, w = it.w, h = it.h;
  if (it.kind === 'image') {
    const f = imgBox(it, u), fr = ctx.frame(q, t), cov = q.data && q.data.fit === 'cover', fo = (q.data && q.data.focus) || [0.5, 0.5];
    let src = fr;
    if (q.data && q.data.halftone) { const hs = PAINT.canvas(Math.round(f.w), Math.round(f.h)); MD.cover(hs.getContext('2d'), fr, { x: 0, y: 0, w: hs.width, h: hs.height, fit: cov ? 'cover' : 'contain', fx: fo[0], fy: fo[1] }); src = CL.halftone('clipimg' + it.seed + (q.frames ? '_' + Math.floor((t - q.at) * (q.fps || 30)) : ''), hs, { cell: 5 * u, contrast: 1.25 }); }
    MD.print(g, src, f.w, f.h, { border: 16 * u, fx: fo[0], fy: fo[1], tape: true, key: q.frames ? null : 'y2print' + it.seed });   // print: white border, aged paper, drop shadow, tape
    if (q.text) { const fs = TY.fit(g, q.text, w * 0.8, 40 * u, 'PuHui-Heavy', { maxLines: 1, min: 0.5 });   // black torn-edge label pressed into the bottom-left corner, typed at 12fps
      MD.label(g, q.text, -w / 2 - 14 * u, h / 2 - 34 * u, { t, at: q.at + 0.25, size: fs.size, r: -0.02, bg: C.ink, fg: C.paper }); }
    // highlight: highlighter (multiply, swept on twos) → red pen circle
    for (const hq of ctx.of('highlight')) {
      if (!hq.data || !hq.data.rect || hq.at < q.at) continue;
      const own = ctx.of('image', 'clip').filter(z => z.at <= hq.at).pop(); if (own !== q) continue;
      const l = t - hq.at; if (l < -1e-6) continue;
      const R = hq.data.rect, x0 = -w / 2 + f.x + R[0] * f.w, y0 = -h / 2 + f.y + R[1] * f.h, rw = R[2] * f.w, rh = R[3] * f.h;
      CL.highlight(g, x0 - 6 * u, y0 - 4 * u, rw + 12 * u, rh + 8 * u, MO.sineInOut(clamp(ls(t, hq.at) / 0.6)), C.hi);
      const cq = MO.cubicOut(clamp((ls(t, hq.at) - 0.5) / 0.6));
      const newer = ctx.of('highlight').find(z => z.at > hq.at && z.at <= t + 1e-6 && z.data && z.data.rect && ctx.of('image', 'clip').filter(y => y.at <= z.at).pop() === q);
      const fa = newer ? 1 - 0.75 * clamp((t - newer.at) / 0.3) : 1;   // a second region circled on the same image: the old circle fades to a pale mark so two circles don't stack and the old one doesn't run off frame
      if (cq > 0) { const pts = DG.hand(DG.ellipsePts(x0 + rw / 2, y0 + rh / 2, rw * 0.7 + 16 * u, rh * 0.72 + 10 * u, -2.6, 1.08, 44), { amp: 2.2 * u, seed: it.seed }), L = DG.cum(pts);
        g.save(); g.globalAlpha *= fa; g.strokeStyle = C.red; g.lineWidth = 7 * u; g.lineCap = 'round'; g.lineJoin = 'round'; DG.drawPartial(g, pts, L, L[L.length - 1] * cq); g.restore(); }
    }
  } else {
    const n = Math.ceil(ls(t, q.at) * (it.cps || 13)), title = it.kind === 'title';
    CL.shadowed(g, () => { g.fillStyle = title ? C.ink : C.card; g.save(); g.translate(-w / 2, -h / 2); CL.tornRect(g, w, h, it.seed, 3 * u); g.fill(); g.restore(); }, { blur: 10 * u, x: 3 * u, y: 6 * u });
    if (!title) { g.strokeStyle = C.rule; g.lineWidth = 2 * u; for (let y = -h / 2 + 90 * u; y < h / 2; y += it.size * 1.45) { g.beginPath(); g.moveTo(-w / 2, y); g.lineTo(w / 2, y); g.stroke(); }
      g.strokeStyle = C.margin; g.beginPath(); g.moveTo(-w / 2, -h / 2 + 56 * u); g.lineTo(w / 2, -h / 2 + 56 * u); g.stroke(); }
    g.fillStyle = title ? C.paper : C.ink; g.font = `${it.size}px ${title ? BOLD : TXT}`; g.textBaseline = 'alphabetic';
    let k = 0; it.lines.forEach((ln, li) => { let x = -w / 2 + (title ? 40 : 55) * u; const y = -h / 2 + (title ? 25 * u : 70 * u) + (li + 1) * it.size * 1.3;
      for (const ch of ln) { if (k < n) g.fillText(ch, x, y); x += g.measureText(ch).width; k++; } });
  }
}
})();
