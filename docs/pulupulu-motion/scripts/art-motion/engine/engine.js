// Engine: time t (seconds) → one frame of picture. Deterministic: the same t always draws the same frame (all randomness is seeded).
// The timeline is driven by a beat grid: 128 BPM, each era spans a number of eighth notes (see eighths in eras.js).
(() => {
// Canvas size: ?w=1080&h=1920 (passed by render.py --width/--height) > window.FILM_SIZE = [w, h] in eras.js > 1920×1080.
// One-shot U.setStage: transitions, camera and every library switch with it; portrait full-film scene code must lay out against window.STAGE (or the CAM/UI libraries), and the 35 art-style scenes have only ever been painted for landscape.
const qs = new URLSearchParams(location.search), qw = +qs.get('w'), qh = +qs.get('h');
const [W, H] = qw > 0 && qh > 0 ? [qw, qh] : Array.isArray(window.FILM_SIZE) ? window.FILM_SIZE.map(Number) : [1920, 1080];
window.U.setStage(W, H);
const cv = document.getElementById('c');
cv.width = W; cv.height = H; window.__size = [W, H];
const ctx = cv.getContext('2d');
window.__canvas = cv;

const EIGHTH = 60 / (window.BPM || 128) / 2;   // 0.234375s @128; a film can set window.BPM
// Era length: eighths (number of eighth notes, locked to the beat) or dur (seconds, for narration-cut explainer films). If dur is written it wins.
let acc = 0;
for (const e of ERAS) { e.t0 = acc; acc += e.dur != null ? e.dur : e.eighths * EIGHTH; e.t1 = acc; }
// Film length = t1 of the last era; window.FILM_DURATION takes priority. render.py / preview both read window.__total.
window.__total = window.FILM_DURATION || ERAS[ERAS.length - 1].t1;
ERAS[ERAS.length - 1].t1 = 1e9;

// Offscreen buffers: A = previous era, B = current era
const mk = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; return c; };
const bufA = mk(), bufB = mk(), bufT = mk();
window.__mk = mk;

// ---------- Assets ----------
const IMG = {};
function load(src) {
  return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => rej(src); im.src = src; });
}
async function boot() {
  if (window.__bootErrors && __bootErrors.length) { window.__bootFailed = __bootErrors.join('\n'); console.error('BOOT FAILED\n' + window.__bootFailed); return; }
  const list = new Set();
  for (const e of ERAS) (e.assets || []).concat(e.plate ? [e.plate] : []).forEach(s => list.add(s));
  (window.EXTRA_ASSETS || []).forEach(s => list.add(s));
  try { await Promise.all([...list].map(async s => { IMG[s] = await load(s); })); }
  catch (src) { window.__bootFailed = `Image load failed: ${src} (a file named in an era's assets / plate / window.EXTRA_ASSETS does not exist or is not an image)`; console.error('BOOT FAILED\n' + window.__bootFailed); return; }
  for (const f of (window.FONT_FACES || [])) { const ff = new FontFace(f.family, `url(${f.url})`, f.desc || {}); await ff.load(); document.fonts.add(ff); }
  await document.fonts.ready;
  await U.loadCmaps();                                  // for glyph checks (U.assertGlyphs)
  for (const e of ERAS) if (e.init) e.init(IMG);
  checkCounterGlyphs();
  await window.prepare(0);                              // the video frame for frame 0 loads first (a missing frame errors right here)
  window.__ready = true;
  renderFrame(0);
}
window.IMG = IMG;

const U = window.U;

// ---------- Corner badge (top right): pluggable ----------
// Each era's counter takes one of three forms:
//  1) Default: the year counter U.yearCounter — the value is determined only by global time (U.counterAt) and rolls continuously across eras; label holds the style name.
//  2) counter.draw(c, lt, t) (alias counter.custom(c, lt)): self-drawn. Use it when the years are not monotonic, or you want a seal / title cartouche / comic caption box.
//  3) counter.mode = 'tag': U.styleTag draws a static two-line plate of "year + style name" (no rolling when the years are out of order).
// During a transition: by default (window.COUNTER_IN_TRANSITION = 'cut') neither layer draws a badge, and once the transition is drawn the old/new badge is hard-cut on top by p<0.5 —
//   when eras have different badge layouts, partially revealing transitions (light-on, wipe, ripple) blur the two type sets into one mess (caught by the independent reviews of migration tests C and D).
//   'layers': the badge stays in its own layer and changes along with the transition (original-film replica: the year plate sits at a fixed position and the digits roll continuously, so the mix cannot be seen). A single transition can override this with transition.counter.
function drawCounter(c, e, t) {
  const ct = e.counter; if (!ct) return;
  const lt = t - e.t0;
  if (ct.draw) ct.draw(c, lt, t);
  else if (ct.custom) ct.custom(c, lt);
  else if (ct.mode === 'tag') U.styleTag(c, ct, lt);
  else { const cv = U.counterAt(t); U.yearCounter(c, ct, cv.v, cv.rolling, lt); }
}
// At boot, check the glyphs the badge uses (a missing glyph silently falling back to a system font is a pit both migration tests B and D fell into). For self-drawn badges call U.assertGlyphs yourself in scene.init.
function checkCounterGlyphs() {
  for (const e of ERAS) { const ct = e.counter; if (!ct || ct.draw || ct.custom) continue;
    if (ct.mode === 'tag') { if (ct.name) U.assertGlyphs(ct.nameFont || ct.font, ct.name, e.id + ' badge'); if (ct.sub) U.assertGlyphs(ct.subFont || ct.nameFont || ct.font, ct.sub, e.id + ' badge'); continue; }
    U.assertGlyphs(ct.font, '0123456789' + (Math.abs(ct.year) >= 10000 ? ',' : ''), e.id + ' year');
    if (ct.label) U.assertGlyphs(ct.label.font, ct.label.text, e.id + ' badge');
    if (ct.suffix) U.assertGlyphs(ct.suffix.font || ct.font, 'BCAD', e.id + ' badge suffix');
  }
}
// "year + style name" static plate: { year, name, sub?, x, y, font, size, color, nameFont, nameColor, subFont, subColor, box(c,lt), shadow, align }
U.styleTag = function (c, ct, lt) {
  if (ct.box) ct.box(c, lt);
  c.save(); c.textAlign = ct.align || 'right'; c.textBaseline = 'alphabetic';
  if (ct.shadow) { c.shadowColor = ct.shadow.color; c.shadowBlur = ct.shadow.blur || 0; c.shadowOffsetX = ct.shadow.x || 0; c.shadowOffsetY = ct.shadow.y || 0; }
  const x = ct.x ?? 1866, y = ct.y ?? 128;
  if (ct.year != null) { c.font = `${ct.size || 96}px "${U.fontFamily(ct.font)}"`; c.fillStyle = ct.color || '#fff'; c.fillText(ct.yearText || (ct.year < 0 ? U.fmtYear(ct.year) + ' BC' : String(ct.year)), x, y); }
  if (ct.name) { c.font = ct.nameFont || `34px "${U.fontFamily(ct.font)}"`; c.fillStyle = ct.nameColor || ct.color || '#fff'; c.fillText(ct.name, x, ct.ny ?? y + 52); }
  if (ct.sub) { c.font = ct.subFont || ct.nameFont; c.fillStyle = ct.subColor || ct.nameColor || ct.color; c.fillText(ct.sub, x, ct.sy ?? y + 92); }
  c.restore();
};

// ---------- Year counter (odometer, digit-by-digit roll) ----------
// from/to are numbers; fmt formats the number into a string; while rolling each digit rolls independently from the old character to the new one, low digits move first, offset by stagger.
U.odometer = function (c, opt, p) {
  const { x, y, size, font, color, fromStr, toStr, align = 'right', stagger = 0.12, spacing = 0, shadow } = opt;
  c.save();
  c.font = `${size}px ${font}`;
  c.textBaseline = 'alphabetic';
  c.fillStyle = color;
  const n = Math.max(fromStr.length, toStr.length);
  const a = fromStr.padStart(n, ' '), b = toStr.padStart(n, ' ');
  const widths = [...b].map(ch => c.measureText(ch === ' ' ? '0' : ch).width + spacing);
  const total = widths.reduce((s, w) => s + w, 0) - spacing;
  let cx = align === 'right' ? x - total : align === 'center' ? x - total / 2 : x;
  for (let i = 0; i < n; i++) {
    const order = n - 1 - i;                           // low digits roll first
    const pi = U.clamp((p - order * stagger) / Math.max(0.0001, 1 - (n - 1) * stagger));
    const e = U.ease.inOut(pi);
    const w = widths[i];
    c.save();
    c.beginPath(); c.rect(cx - 4, y - size * 1.05, w + 8, size * 1.35); c.clip();
    if (shadow) { c.shadowColor = shadow.color; c.shadowBlur = shadow.blur || 0; c.shadowOffsetX = shadow.x || 0; c.shadowOffsetY = shadow.y || 0; }
    if (a[i] === b[i]) c.fillText(b[i], cx, y);
    else {
      const dy = size * 1.1 * e;
      c.globalAlpha = 1 - e * 0.6; if (a[i] !== ' ') c.fillText(a[i], cx, y - dy);
      c.globalAlpha = 0.4 + e * 0.6; if (b[i] !== ' ') c.fillText(b[i], cx, y + size * 1.1 - dy);
    }
    c.restore();
    cx += w;
  }
  c.restore();
};

// ---------- Year counter: value interpolation (ease-out) + units-digit roll ghost ----------
// ct: {year, x, y, size, font, color, suffix:{font,size,color,dy,gap}, label:{text,font,color,x,y,spacing}, box(c), shadow, spacing}
U.fmtYear = (v) => { const a = Math.abs(Math.round(v)); return a >= 10000 ? a.toLocaleString('en-US') : String(a); };
// The counter value is determined only by global time: during a transition the old and new layers show the same number
U.counterAt = function (t) {
  let k = 0; for (let i = 0; i < ERAS.length; i++) if (t >= ERAS[i].t0) k = i;
  const cur = ERAS[k].counter, prv = k ? ERAS[k - 1].counter : cur;
  const p = cur.roll ? U.clamp((t - ERAS[k].t0 - 0.03) / cur.roll) : 1;
  return { v: prv.year + (cur.year - prv.year) * U.ease.inOut(p), rolling: p > 0 && p < 1 };
};
U.yearCounter = function (c, ct, v, rolling, lt) {
  if (ct.box) ct.box(c, lt);
  const vi = Math.round(v);
  const str = U.fmtYear(vi);
  const era = v < 0 ? 'BC' : 'AD';
  c.save();
  c.textBaseline = 'alphabetic';
  if (ct.shadow) { c.shadowColor = ct.shadow.color; c.shadowBlur = ct.shadow.blur || 0; c.shadowOffsetX = ct.shadow.x || 0; c.shadowOffsetY = ct.shadow.y || 0; }
  let x = ct.x;
  // Suffix (BC/AD)
  const sfx = ct.suffix && (ct.suffix.show === 'always' || (ct.suffix.show !== 'never')) ? ((ct.suffix.text === 'BC' || ct.suffix.text === 'AD') ? era : (ct.suffix.text || era)) : '';
  if (sfx) {
    c.font = `${ct.suffix.size}px "${ct.suffix.font || ct.font}"`; c.fillStyle = ct.suffix.color || ct.color; c.textAlign = 'right';
    c.fillText(sfx, x, ct.y + (ct.suffix.dy || 0));
    x -= c.measureText(sfx).width + (ct.suffix.gap || 12);
  }
  c.font = `${ct.size}px "${ct.font}"`; c.fillStyle = ct.color; c.textAlign = 'left';
  if (ct.spacing) c.letterSpacing = ct.spacing + 'px';
  const w = c.measureText(str).width - (ct.spacing || 0);
  const x0 = x - w;
  // While rolling: draw everything as usual except the units digit, which is drawn as a vertical roll
  if (rolling) {
    const head = str.slice(0, -1), last = str.slice(-1);
    c.fillText(head, x0, ct.y);
    const hw = head ? c.measureText(head).width : 0;
    const frac = (Math.abs(v) % 1);
    const lw = c.measureText(last).width;
    c.save(); c.beginPath(); c.rect(x0 + hw - 2, ct.y - ct.size * 1.0, lw + 30, ct.size * 1.25); c.clip();
    c.fillText(last, x0 + hw, ct.y - frac * ct.size * 0.3);
    c.globalAlpha = 0.35; c.fillText(String((+last + 1) % 10), x0 + hw, ct.y - ct.size * 0.85 - frac * ct.size * 0.3);
    c.restore();
  } else c.fillText(str, x0, ct.y);
  c.restore();
  if (ct.label) {
    const L = ct.label; c.save(); c.font = L.font; c.fillStyle = L.color; c.textAlign = L.align || 'right'; c.textBaseline = 'alphabetic';
    if (L.spacing) c.letterSpacing = L.spacing + 'px';
    if (L.shadow) { c.shadowColor = L.shadow.color; c.shadowBlur = L.shadow.blur || 0; c.shadowOffsetX = L.shadow.x || 0; c.shadowOffsetY = L.shadow.y || 0; }
    if (L.gradient) { const g = c.createLinearGradient(0, L.y - 30, 0, L.y); L.gradient.forEach((col, i) => g.addColorStop(i / (L.gradient.length - 1), col)); c.fillStyle = g; }
    c.fillText(L.text, (L.x || ct.x) + (L.spacing && (L.align || 'right') === 'right' ? L.spacing : 0), L.y); c.restore();
  }
};

// ---------- Steam (generic: several semi-transparent sine-curled strokes) ----------
U.steam = function (c, t, { x, y, h = 70, n = 3, w = 3, color = 'rgba(255,255,255,.8)', spread = 14, speed = 1, seed = 1, wobble = 8 }) {
  c.save(); c.strokeStyle = color; c.lineCap = 'round'; c.lineWidth = w;
  for (let k = 0; k < n; k++) {
    const ox = (k - (n - 1) / 2) * spread;
    const ph = t * 2.2 * speed + k * 1.7 + seed;
    c.beginPath();
    for (let s = 0; s <= 24; s++) {
      const q = s / 24, yy = y - q * h, xx = x + ox + Math.sin(ph + q * 5) * wobble * q;
      c.globalAlpha = 1;
      s ? c.lineTo(xx, yy) : c.moveTo(xx, yy);
    }
    const g = c.createLinearGradient(0, y, 0, y - h); g.addColorStop(0, color); g.addColorStop(1, 'rgba(255,255,255,0)');
    c.strokeStyle = g; c.stroke();
  }
  c.restore();
};

// ---------- Video layer: each era can host a frame sequence (clips/<id>/%04d.jpg), loaded asynchronously on demand ----------
// clip: {dir, fps, n, in, speed, loop}  era-local time lt → in-clip time in + lt*speed → frame index
const FRAMES = new Map();                 // url -> Image (already decoded)
function clipFrameUrl(e, lt) {
  const c = e.clip; let ct = (c.in || 0) + Math.max(0, lt) * (c.speed || 1);
  let i = Math.round(ct * c.fps);
  if (c.loop === 'pingpong') { const m = 2 * (c.n - 1); i = i % m; if (i >= c.n) i = m - i; } else i = Math.min(c.n - 1, i);
  return `${c.dir}/${String(i + 1).padStart(4, '0')}.jpg`;
}
async function need(url) {
  if (FRAMES.has(url)) return;
  const im = new Image(); im.src = url;
  try { await im.decode(); } catch (e) { const msg = `Video frame missing or undecodable: ${url} (clip.dir / n / in do not line up with the frame sequence)`; console.error(msg); throw new Error(msg); }
  FRAMES.set(url, im);
  if (FRAMES.size > 240) { const k = FRAMES.keys().next().value; FRAMES.delete(k); }
}
function layersAt(t) {
  let k = ERAS.findIndex(e => t >= e.t0 && t < e.t1); if (k < 0) k = ERAS.length - 1;
  const out = [k]; const e = ERAS[k];
  if (k > 0 && e.transition && t - e.t0 < e.transition.dur + (e.transition.delay || 0)) out.push(k - 1);
  return out;
}
window.prepare = async function (t) {
  await Promise.all(layersAt(t).map(k => ERAS[k].clip ? need(clipFrameUrl(ERAS[k], t - ERAS[k].t0)) : null));
};

// ---------- Draw one era (era-local time lt) ----------
function drawEra(c, e, t, prev, punchFrom, noCounter) {
  const lt = t - e.t0;
  c.save();
  c.clearRect(0, 0, W, H);
  // Beat-point camera punch (affects the scene layer only, the year plate does not scale): s(k)=1+0.03·(1-k/20)^1.5, k = frames since the transition started
  // The punch follows the transition start of "the era that is coming in": during a transition the old era scales too (in the original film the whole screen punches on the beat frame)
  const pe = punchFrom || e;
  // Amplitude: transition.punch (number; false/0 turns it off) > film-level window.PUNCH > 0.03. Explainer / launch / data films do not want this kick, write window.PUNCH = 0.
  const pa = pe.transition ? (pe.transition.punch ?? window.PUNCH ?? 0.03) : 0, amp = pa === true ? 0.03 : +pa || 0;
  const k60 = amp ? (t - pe.t0) * 60 : 99;
  const punch = k60 >= 0 && k60 < 20 ? 1 + amp * Math.pow(1 - k60 / 20, 1.5) : 1;
  c.save(); if (punch !== 1) { c.translate(W / 2, H / 2); c.scale(punch, punch); c.translate(-W / 2, -H / 2); }
  // Video frame: cover the screen (MD.cover, no stretching); an era can define clipDraw(c, frame, lt, t) to place it itself (push-in, focus, print). A frame that is not ready must not silently go blank — error out
  if (e.clip) { const url = clipFrameUrl(e, lt), im = FRAMES.get(url);
    if (!im) throw new Error(`Video frame not loaded: ${url} (await window.prepare(t) before rendering; render.py already does this, your own scripts must too)`);
    if (e.clipDraw) e.clipDraw(c, im, lt, t); else MD.cover(c, im); }
  else if (e.plate && !e.draw) c.drawImage(IMG[e.plate], 0, 0, W, H);
  if (e.draw) e.draw(c, lt, t, IMG, prev);
  c.restore();
  if (!noCounter) drawCounter(c, e, t);
  c.restore();
}

// ---------- Main render ----------
function renderFrame(t) {
  let k = ERAS.findIndex(e => t >= e.t0 && t < e.t1); if (k < 0) k = ERAS.length - 1;
  const e = ERAS[k], prev = ERAS[k - 1];
  const tr = e.transition;
  const trDur = tr ? tr.dur + (tr.delay || 0) : 0;
  const lt = t - e.t0;
  if (prev && tr && lt < trDur) {
    const cut = (tr.counter || window.COUNTER_IN_TRANSITION || 'cut') === 'cut';
    drawEra(bufA.getContext('2d'), prev, t, ERAS[k - 2], e, cut);
    drawEra(bufB.getContext('2d'), e, t, prev, undefined, cut);
    const p = U.clamp((lt - (tr.delay || 0)) / tr.dur);
    ctx.save(); ctx.clearRect(0, 0, W, H);
    // o.id / o.from = id of the entering era / leaving era: transitions that cache based on picture content must carry it (once(k, f, o) in transitions.js)
    TRANSITIONS[tr.type](ctx, bufA, bufB, p, { ...tr, id: e.id, from: prev.id, lt, t, W, H, tmp: bufT, IMG });
    ctx.restore();
    if (cut) drawCounter(ctx, p < 0.5 ? prev : e, t);
  } else {
    drawEra(ctx, e, t, prev);
  }
  if (window.GLOBAL_OVERLAY) window.GLOBAL_OVERLAY(ctx, t);
  return k;
}
window.renderFrame = renderFrame;
// Single-era preview: opt.counter = false skips the badge (when self-checking frame deltas the rolling counter inflates the numbers — migration test B)
window.renderSolo = function (id, lt, opt = {}) { const e = ERAS.find(x => x.id === id); if (!e) throw new Error('renderSolo: no such era ' + id); const k = ERAS.indexOf(e); drawEra(ctx, e, e.t0 + lt, ERAS[k - 1], undefined, opt.counter === false); };

// ---------- Preview UI ----------
if (location.search.includes('render=1')) document.body.classList.add('render');
const scrub = document.getElementById('scrub'), tt = document.getElementById('tt'); scrub.max = window.__total;
let playing = false, t0 = 0, base = 0;
scrub.oninput = () => { playing = false; renderFrame(+scrub.value); tt.textContent = (+scrub.value).toFixed(3); };
document.getElementById('play').onclick = () => { playing = !playing; t0 = performance.now(); base = +scrub.value; if (playing) loop(); };
function loop() { if (!playing) return; let t = base + (performance.now() - t0) / 1000; if (t > window.__total) { t = 0; base = 0; t0 = performance.now(); } scrub.value = t; tt.textContent = t.toFixed(3); renderFrame(t); requestAnimationFrame(loop); }
boot().catch(err => { window.__bootFailed = String(err && err.stack || err); console.error('BOOT FAILED\n' + window.__bootFailed); });
})();
