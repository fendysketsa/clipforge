// Parametric clip runtime: one spec (JSON) → one animation whose duration is exactly spec.duration. Used as an "animation segment" by the narration-video pipeline.
// The contract is in references/09-animation-grammar.md under "clip contract". Difference from engine.js: no era table / transitions, one grammar per draw(c, t, ctx), and the canvas size is read from spec (portrait works too).
//
// spec.finish (optional): finished-film texture layer, preset soft / film / punch / clean or an object, see lib/finish.js; ignored in alpha mode.
// spec = { grammar, duration, fps=30, width=1920, height=1080, safe?: {top,bottom,left,right (px, reserved for subtitles / platform UI), fill? (paint the cleared edges with this color)}, theme?, alpha?, data?, cues: [{at, kind, text?, sub?, data?, image?, frames?, fps?, dur?}] }
// spec.theme: the palette shared by the whole film (lib/palettes.js) — a name (paper poster ink navy bauhaus snow wood chalk), {name, keys to override}, or a full 6-key {bg, surface, ink, sub, accent, accent2}.
//   Resolved into ctx.pal (the full 6 keys + name) and each grammar colors by it; a misspelled name / a missing key → boot failure. Omitted → ctx.pal = null and each grammar uses its own default colors.
//   A grammar can declare legacyTheme(theme) → true: this theme is its own old form (t3's 'light' / 'dark' / old theme object), do not resolve it as a palette, the grammar keeps reading ctx.theme.
// Asset paths (render.py checks existence with spec_assets.py and rewrites them): cue.image, cue.frames (frame sequence: a directory or an array of paths), data.image, data.character.frames (the y4 frame library).
// Any single one that fails to load → boot failure, refuse to render (never a blank frame). Taking assets inside a grammar: ctx.still(q) = the still image of this cue (the first frame when frames exist), ctx.frame(q, t) = the frame that should be drawn at time t.
// Grammar file clips/<grammar>.js registers CLIPS[grammar] = { init?(ctx), draw(c, t, ctx), safe?: true (write it only if you laid out against ctx.safe / ctx.box, otherwise spec.safe raises a warning) }.
// Alignment convention (CLIP.lt): the "reveal frame" of a cue = the frame that at falls on — an element first becomes visible on the frame t = at, and the animation's internal time starts from at − 1 frame.
(() => {
const cv = document.getElementById('c'), c = cv.getContext('2d');
window.__canvas = cv;
window.CLIPS = window.CLIPS || {};
const C = window.CLIP = {};
const fail = msg => { window.__bootFailed = msg; console.error('CLIP BOOT FAILED\n' + msg); };

// ---------- Small helpers for grammar files ----------
// in-clip time: the cue first becomes visible on the frame at
C.lt = (t, at, fps) => t - at + 1 / fps;
// progress: runs 0→1 over dur seconds starting at at (the at frame is already >0)
C.p = (t, at, dur, fps) => U.clamp(C.lt(t, at, fps) / dur);
// fit proportionally into the box (contain, no crop): returns {x, y, w, h}
C.fit = (iw, ih, bx, by, bw, bh) => { const s = Math.min(bw / iw, bh / ih); const w = iw * s, h = ih * s; return { x: bx + (bw - w) / 2, y: by + (bh - h) / 2, w, h, s }; };
// normalized rectangle [x,y,w,h] (0..1, relative to the image) → screen rectangle
C.sub = (r, box) => ({ x: box.x + r[0] * box.w, y: box.y + r[1] * box.h, w: r[2] * box.w, h: r[3] * box.h });
C.text = (cue, ...fallback) => (cue && (cue.text ?? cue.data?.text)) ?? fallback.find(v => v != null) ?? '';

async function boot() {
  let spec = window.CLIP_SPEC;
  if (!spec) {                                                           // preview: ?spec=<path relative to engine>
    const u = new URLSearchParams(location.search).get('spec');
    if (!u) return fail('no spec: render.py --spec injects window.CLIP_SPEC; for preview use clip.html?spec=examples/<name>.json');
    spec = await (await fetch(u)).json();
    const base = u.replace(/[^/]*$/, '');
    const fix = p => p && !/^(data:|https?:|\/)/.test(p) ? base + p : p;   // preview mode: frames must be written as an array of paths (a browser cannot list a directory), a frame library as {frames: {pose: path}}
    (spec.cues || []).forEach(q => { if (q.image) q.image = fix(q.image); if (Array.isArray(q.frames)) q.frames = q.frames.map(fix); });
    if (spec.data && spec.data.image) spec.data.image = fix(spec.data.image);
    const ch = spec.data && spec.data.character; if (ch && typeof ch === 'object' && ch.frames && typeof ch.frames === 'object') for (const k in ch.frames) ch.frames[k] = fix(ch.frames[k]);
  }
  if (location.search.includes('render=1')) document.body.classList.add('render');
  const W = spec.width || 1920, H = spec.height || 1080, FPS = spec.fps || 30;
  if (!spec.grammar) return fail('spec is missing grammar');
  if (!(spec.duration > 0)) return fail('spec.duration must be > 0');
  cv.width = W; cv.height = H; U.setStage(W, H);
  // grammar file (synchronous XHR + eval, with sourceURL so errors can be located)
  const x = new XMLHttpRequest(); x.open('GET', `clips/${spec.grammar}.js`, false);
  try { x.send(); } catch (e) { return fail('failed to request the grammar file ' + e); }
  if (x.status !== 200) return fail(`No such grammar: clips/${spec.grammar}.js (HTTP ${x.status})`);
  try { (0, eval)(x.responseText + `\n//# sourceURL=clips/${spec.grammar}.js`); } catch (e) { return fail(`clips/${spec.grammar}.js threw while executing ${e.stack || e}`); }
  const G = CLIPS[spec.grammar]; if (!G || typeof G.draw !== 'function') return fail(`clips/${spec.grammar}.js did not register CLIPS['${spec.grammar}'] = { draw }`);
  // theme palette: validate before loading assets, so a typo does not make you wait on images
  let pal = null;
  if (!(G.legacyTheme && G.legacyTheme(spec.theme))) { try { pal = PAL.resolve(spec.theme); } catch (e) { return fail(e.message); } }
  // finished-film texture layer (spec.finish): a wrong preset name should not make you wait on images either
  let fin = null; try { fin = FINISH.resolve(spec.finish); } catch (e) { return fail(e.message); }
  // images
  const IMG = {}, urls = new Set();
  for (const q of (spec.cues || [])) {
    if (q.image) urls.add(q.image);
    if (q.frames != null) { if (!Array.isArray(q.frames) || !q.frames.length) return fail(`frames of cue ${q.kind} at=${q.at} must be a non-empty array of paths (render.py expands a directory into an array; preview mode only accepts an array)`); q.frames.forEach(f => urls.add(f)); }
  }
  if (spec.data && spec.data.image) urls.add(spec.data.image);
  const chr = spec.data && spec.data.character;
  if (chr && typeof chr === 'object') { if (!chr.frames || typeof chr.frames !== 'object' || Array.isArray(chr.frames)) return fail('when data.character is an object it needs frames: {poseName: imagePath} (or pass a frame-library directory in render.py)');
    Object.values(chr.frames).forEach(f => urls.add(f)); }
  try { await Promise.all([...urls].map(u => new Promise((res, rej) => { const im = new Image(); im.onload = () => { IMG[u] = im; res(); }; im.onerror = () => rej(u); im.src = u; }))); }
  catch (u) { return fail('image load failed: ' + u); }
  // fonts + glyph check (a missing glyph for text in the spec is only a warning: falling back to a system font still renders, but it looks different on another machine)
  for (const f of (window.FONT_FACES || [])) { const ff = new FontFace(f.family, `url(${f.url})`, f.desc || {}); await ff.load(); document.fonts.add(ff); }
  await document.fonts.ready; await U.loadCmaps();
  const cues0 = (spec.cues || []).map((q, i) => ({ ...q, i, at: +q.at || 0 })).sort((a, b) => a.at - b.at || a.i - b.i);
  for (const q of cues0) if (q.at > spec.duration + 1e-9) console.warn(`cue ${q.kind} at=${q.at} is beyond the clip duration ${spec.duration}s, never visible, dropped (takes no layout space)`);
  const cues = cues0.filter(q => q.at <= spec.duration + 1e-9);   // invisible cues never reach the grammar: otherwise they still occupy layout slots and the progress track still counts them
  // grammars used to pick the caption field of a number cue each their own way (t2/t3 use text, y5 uses sub), and a typo never errored, it just drew nothing. Unified: text and sub are aliases of each other, and data.text counts too
  for (const q of cues) if (q.kind === 'number') { const cap = q.text ?? q.sub ?? (q.data && q.data.text); if (cap != null) { q.text = cap; q.sub = cap; } }
  const safe = { top: 0, bottom: 0, left: 0, right: 0, ...(spec.safe || {}) };   // cleared edges (px): the pipeline burns in subtitles and platform UI sits here, grammars that draw type must not lay out into them
  const box = { x: safe.left, y: safe.top, w: W - safe.left - safe.right, h: H - safe.top - safe.bottom };   // content box after clearing the edges, grammars lay out against it (ctx.box)
  const ctx = { spec, data: spec.data || {}, theme: spec.theme || {}, pal, cues, W, H, FPS, u: Math.min(W, H) / 1080, portrait: H > W, alpha: !!spec.alpha, IMG, dur: spec.duration, safe, box,
    of: (...kinds) => cues.filter(q => kinds.includes(q.kind)), lt: (t, at) => C.lt(t, at, FPS), p: (t, at, d) => C.p(t, at, d, FPS),
    // assets: still = the one used for the fixed layout (image, or the first frame of frames); frame = which frame to draw at time t (frames play from at at q.fps (default 30), stop on the last frame when done, q.loop loops)
    still: q => q && (q.image ? IMG[q.image] : q.frames ? IMG[q.frames[0]] : null),
    frame: (q, t) => !q ? null : q.frames ? MD.frameAt(q.frames.map(f => IMG[f]), t - q.at, q.fps || 30, !!q.loop) : q.image ? IMG[q.image] : null };
  if (G.fonts) { const txt = cues.map(q => [q.text, q.sub, q.data && q.data.text].filter(Boolean).join('')).join('') + JSON.stringify(spec.data || {});
    for (const fam of G.fonts) { const miss = U.missingGlyphs(fam, [...txt].filter(ch => ch.codePointAt(0) >= 0x2E80).join(''));   /* check CJK ideographs and full-width symbols only: Latin / Greek / math symbols have their own fonts per grammar */ if (miss.length) console.warn(`Font "${fam}" is missing glyphs: ${miss.join('')} (will fall back to a system font; common characters are already in the GB2312 subset, add rare ones with scripts/font_subset.py --text)`); } }
  if (spec.safe && (safe.top || safe.bottom || safe.left || safe.right) && !G.safe)
    console.warn(`grammar ${spec.grammar} has not wired up safe yet (no safe: true on the grammar object), spec.safe is ignored: the subtitle band may sit on top of the type`);
  if (G.init) G.init(ctx);
  window.CLIP_CTX = ctx;
  window.__total = spec.duration; window.__fps = FPS; window.__size = [W, H];
  // safe.fill: paint the cleared edges with this color (a portrait film makes the chart a "card" flush with the adjacent contain asset, with the film's background color outside); not painted in transparent mode
  const band = (safe.fill && !spec.alpha) ? (cc => { cc.fillStyle = safe.fill; const { top: t0, bottom: b0, left: l0, right: r0 } = safe;
    if (t0) cc.fillRect(0, 0, W, t0); if (b0) cc.fillRect(0, H - b0, W, b0); if (l0) cc.fillRect(0, 0, l0, H); if (r0) cc.fillRect(W - r0, 0, r0, H); }) : null;
  window.renderFrame = t => { c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, H); c.save(); G.draw(c, t, ctx); c.restore(); if (fin && !spec.alpha) FINISH.apply(c, t, fin, W, H, FPS); if (band) band(c); };
  window.prepare = async () => {};
  window.__ready = true;
  window.renderFrame(0);
  const sc = document.getElementById('scrub'), tt = document.getElementById('tt'); sc.max = spec.duration; sc.step = 1 / FPS;
  sc.oninput = () => { window.renderFrame(+sc.value); tt.textContent = (+sc.value).toFixed(3); };
}
boot().catch(e => fail(String(e && e.stack || e)));
})();
