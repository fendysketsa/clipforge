#!/usr/bin/env python3
# /// script
# dependencies = ["playwright", "numpy", "pillow"]
# ///
"""Acceptance-check a code animation project with one command: stability, efficiency, motion, smoothness — numbers plus a contact sheet. Must run before delivery; the numbers go into the delivery note.

    uv run qa.py --project <code project dir> [--film gallery] [--ids 01_cave,09_postimp] [--fps 30] [--out <dir>]
    uv run qa.py --spec <clip clip.json> [--out <dir>]      # parameterised clip (the animation segment of the narration pipeline): the whole run is measured as one segment, portrait is fine too; transitions aren't measured
                                                              # asset fields are the same set as render.py (engine/spec_assets.py): image, frames, data.image, data.character

Per segment (each id in eras.js) it does four things:
  1. Stability: a scene that fails to load exits immediately (the engine sets __bootErrors); the same moment is cold-rendered and hot-rendered twice and compared pixel by pixel (determinism).
  2. Efficiency: time per frame — the timing includes a getImageData(1×1) to force the GPU to finish (timing only the synchronous JS reports a fake 1ms; migration test B hit this).
  3. Motion: after skipping the 0.35s camera jolt that follows a transition, take frames continuously at --fps through the still stretch of the segment and report the mean motion area (share of pixels changing >12 between adjacent frames),
     plus the "still frame pair" ratio (adjacent frames nearly unchanged, <0.05% — migration test A found that comparing only first and last misses the stuttering).
  4. Smoothness: peak / median of the adjacent-frame difference. >6 with a peak >3% is recorded as a "spike" (the whole screen of strokes being rewashed at 8fps, a frame going wrong, flicker all show up).
     Camera moves (fast push 0.28s, glide 0.30s, slam 0.17s, slow push 0.9s, finding the next object 0.7s, pull back 1.1s) are not spikes; they are recorded separately as "camera events": from a spike frame expand both ways until the frame difference falls back,
     the run must be at least 2 frame pairs, no longer than 2s (+1 frame), and its last frame must be farthest from the first (it pushes in and stays there, rather than flashing in and back); runs longer than 0.35s must also be smooth the whole way,
     with no single-frame peak in the middle more than 2.5× its neighbours. Before 2026-10-12 only runs within 0.35s were accepted, so a slow push was recorded as one long spike, which effectively forced the model to make its camera moves faster.
     Isolated one or two frames (goofs, white flashes, whole-screen rewash), flash-and-return, and longer continuous drags are still recorded as spikes. Only pixels are read, not the camera action table,
     so a hand-written push is recognised like CAM.track; the cost is that a monotone, smooth large change (say the whole screen switching to another image and pushing right after) also counts as a camera event.
It also does a "transition smoke test": for each segment with a transition it renders whole frames at p=.25/.5/.75 (renderFrame) and counts errors as page errors — frames inside a segment come from renderSolo,
so transition code never runs and a broken transition can still be all green (hit while porting the all-styles demo reel).
The criteria are empirical thresholds, not rules: motion between 0.5–8% looks good for most segments; still frame pairs >40% reads as stutter; for spikes >0 look at the frames first and then judge (an intentional beat flash isn't a mistake).
  5. Framing:
     From page load it records the on-screen bounding box of every fillText/strokeText and reports it when it persists ≥0.3s while grabbing frames —
     clipped text (text partly cut off by the frame edge), overlapping text (two different strings pressing on each other), text entering the subtitle band (text landing in the subtitle band where burned-in subtitles would cover it);
     it also reports "near blank" (almost nothing on screen: full-screen white flash, black frame). These are "go look at this frame" clues, not errors, and never fail qa.
     Boxes follow the canvas: text drawn into an offscreen buffer / sprite cache (including caches pre-drawn at startup) and then drawImage'd up, and text under a bitmap push, are all measured.
     Subtitle band: whole films default to y>920/1080 (change with --sub-band, 0 disables); a --spec clip reads safe.bottom from the spec, and skips the check when it's absent.
     Blind spots: ① frame grabbing starts at max(--skip, transition duration) of each segment, so problems at the head of a segment and inside transitions are invisible; a "blank board at segment start" with a pen or hand left on it (>0.3% of the frame) doesn't count as near blank.
     ② text drawn inside a clip (rolling numbers, revealed stroke by stroke) is only checked for clipping and the subtitle band, not for overlap. ③ text hidden behind non-text objects (photos, paper clips, the presenter, cards that pop up later) can't be found,
     and when two strings are both covered it false-reports overlap. ④ shapes (flames, spaceships) entering the subtitle band can't be found; for light-ground styles use scripts/subzone_gate.py on the finished film.
     ⑤ hand-lettered text is reported one letter at a time, so you have to look at the frame to locate it; decorative large text deliberately placed on the subtitle band or off-frame (like y5's giant watermark numbers) will be reported — look and let it go.

Output: <out>/qa.json (all numbers), <out>/qa.md (table), <out>/<id>.jpg (4-frame contact sheet + motion heatmap).
"""
import argparse, base64, functools, http.server, io, json, socketserver, sys, threading, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'engine'))
import spec_assets
import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
argument_parser.add_argument('--project'); argument_parser.add_argument('--spec', help='parameterised clip spec (goes through clip.html, the same set as render.py --spec)'); argument_parser.add_argument('--ids'); argument_parser.add_argument('--fps', type=float, default=30)
argument_parser.add_argument('--out'); argument_parser.add_argument('--film', default='', help='film name: reads eras_<name>.js'); argument_parser.add_argument('--skip', type=float, default=0.35, help='seconds to skip at the start of each segment (camera jolt)')
argument_parser.add_argument('--sub-band', type=float, default=None, help='top edge of the subtitle band (fraction of frame height); whole films default to 0.852 (920/1080), a --spec clip reads safe.bottom; write 0 to disable the "enters subtitle band" check')
a = argument_parser.parse_args()
if not (a.project or a.spec): argument_parser.error('pass either --project or --spec')
spec, ALLOWED = None, set()
if a.spec:                                                 # same set as render.py: local assets (image / frames / character frame sets) only serve the files named in the spec
    span_length = Path(a.spec).resolve(); spec = json.loads(span_length.read_text())
    try: spec_assets.localize_spec_paths(spec, span_length.parent, ALLOWED)
    except FileNotFoundError as e: raise SystemExit(str(e))
root = Path(a.project).resolve() if a.project else Path(__file__).resolve().parent / 'engine'
out = Path(a.out) if a.out else (Path(a.spec).resolve().parent / 'qa' if a.spec else root.parent / 'qa'); out.mkdir(parents=True, exist_ok=True)
VW, VH = (spec.get('width', 1920), spec.get('height', 1080)) if spec else (1920, 1080)
if a.sub_band is None:   # a clip is for the pipeline: subtitle clearance is written as safe.bottom in the spec; absent means no burned-in subtitles
    sb_value = ((spec or {}).get('safe') or {}).get('bottom', 0) if spec else None
    a.sub_band = 0.852 if sb_value is None else (1 - sb_value / VH if sb_value else 0)

class Q(http.server.SimpleHTTPRequestHandler):
    def note_message(self, *x): pass
    def translate_path(self, path):
        if path.startswith('/__file__/'):
            f = urllib.parse.unquote(path[len('/__file__/'):].split('?')[0])
            return f if f in ALLOWED else '/nonexistent'
        return super().translate_path(path)
# Chromium may open idle connections while loading scripts in parallel.
class LocalServer(socketserver.ThreadingTCPServer):
    queue_depth = 128
    daemon_thread_flag = True

server_object = LocalServer(('127.0.0.1', 0), functools.partial(Q, directory=str(root))); port = server_object.server_address[1]
threading.Thread(target=server_object.serve_forever, daemon=True).start()

# framing check: wrap fillText/strokeText to record the on-screen box of text drawn on a full-screen-sized canvas (through the current transform)
TEXT_HOOK = '''(() => {
  // a text box is recorded against "the canvas it was drawn on"; when that canvas is drawImage'd somewhere else, the box is transformed along with it.
  // that way text drawn into an offscreen buffer and pushed as one bitmap (the presenter film's bitmap push), or drawn into a sprite cache and pasted on the desk (Vox's paper cut-outs), is measured too.
  const P = CanvasRenderingContext2D.prototype;
  const sv = P.save, rs = P.restore, cl = P.clip, di = P.drawImage, cr = P.clearRect, fr = P.fillRect;
  // remember "is there a clip right now": rolling numbers and stroke-by-stroke reveals are drawn inside a clip, so their boxes are bigger than what's visible and aren't used to judge overlap
  P.save = function () { (this.__cs || (this.__cs = [])).push(!!this.__clip); return sv.apply(this, arguments); };
  P.restore = function () { if (this.__cs && this.__cs.length) this.__clip = this.__cs.pop(); return rs.apply(this, arguments); };
  P.clip = function () { this.__clip = true; return cl.apply(this, arguments); };
  // when "the whole canvas gets covered", clear that canvas's text boxes, otherwise after a cache canvas is repainted the previous segment's text stays in the record (whiteboard s03's "rocket" was reported in s04)
  const full = (ctx, x, y, w, h) => {                        // does this rect cover the whole canvas after the current transform (rotation-free transforms only)
    const T = ctx.getTransform(); if (T.b !== 0 || T.c !== 0) return false;
    const xs = [T.a * x + T.e, T.a * (x + w) + T.e], ys = [T.d * y + T.f, T.d * (y + h) + T.f];
    return Math.min(...xs) <= 0 && Math.min(...ys) <= 0 && Math.max(...xs) >= ctx.canvas.width && Math.max(...ys) >= ctx.canvas.height;
  };
  const opaque = ctx => { const f = ctx.fillStyle; if (typeof f !== 'string') return false; const m = f.match(/^(rgba|hsla)\\(([^)]*)\\)/); return !m || +m[2].split(/[ ,\\/]+/).filter(Boolean)[3] >= 1; };
  P.clearRect = function (x, y, w, h) { if (full(this, x, y, w, h)) this.canvas.__tb = []; return cr.apply(this, arguments); };
  P.fillRect = function (x, y, w, h) { if (this.globalAlpha >= 1 && (this.globalCompositeOperation === 'copy' || (this.globalCompositeOperation === 'source-over' && opaque(this))) && full(this, x, y, w, h)) this.canvas.__tb = []; return fr.apply(this, arguments); };
  if (P.reset) { const rz = P.reset; P.reset = function () { this.canvas.__tb = []; this.__cs = []; this.__clip = false; return rz.apply(this, arguments); }; }
  const pid = P.putImageData;
  P.putImageData = function (im, x, y) { if (x <= 0 && y <= 0 && x + im.width >= this.canvas.width && y + im.height >= this.canvas.height) this.canvas.__tb = []; return pid.apply(this, arguments); };
  for (const k of ['width', 'height']) {                       // resizing a canvas clears it, so clear the boxes too
    const d = Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype, k);
    Object.defineProperty(HTMLCanvasElement.prototype, k, { get: d.get, set(v) { this.__tb = []; d.set.call(this, v); }, configurable: true });
  }
  const push = (ctx, rec) => { const L = ctx.canvas.__tb || (ctx.canvas.__tb = []); L.push(rec); if (L.length > 6000) L.splice(0, 3000); };   // a canvas that is only partly cleared and repainted keeps accumulating, so keep the most recent ones
  for (const fn of ['fillText', 'strokeText']) {
    const orig = P[fn];
    P[fn] = function (text, x, y, maxW) {
      if (this.globalAlpha > 0.15 && String(text).trim()) {     // record from load time on: text pre-drawn into a cache at startup (Vox's prewarm) needs a box too
        const m = this.measureText(text), T = this.getTransform();
        let x0 = x - m.actualBoundingBoxLeft, x1 = x + m.actualBoundingBoxRight;
        if (maxW && x1 - x0 > maxW) x1 = x0 + maxW;
        const y0 = y - m.actualBoundingBoxAscent, y1 = y + m.actualBoundingBoxDescent;
        const xs = [], ys = [];
        for (const [px, py] of [[x0, y0], [x1, y0], [x0, y1], [x1, y1]]) { xs.push(T.a * px + T.c * py + T.e); ys.push(T.b * px + T.d * py + T.f); }
        push(this, [String(text).slice(0, 24), xs, ys, !!this.__clip]);
      }
      return orig.apply(this, arguments);
    };
  }
  P.drawImage = function (src, ...a) {
    if (this.globalCompositeOperation === 'copy') this.canvas.__tb = [];
    const L = src && src.__tb;
    if (L && L.length && src !== this.canvas && this.globalAlpha > 0.5) {   // ≤0.5 is usually motion ghosting / a trailing overlay layer, don't pass it on (a whiteboard whip-pan ghost stacks into a screen full of fake overlaps)
      let sx = 0, sy = 0, sw = src.width, sh = src.height, dx, dy, dw = sw, dh = sh;
      if (a.length === 2) [dx, dy] = a; else if (a.length === 4) [dx, dy, dw, dh] = a; else [sx, sy, sw, sh, dx, dy, dw, dh] = a;
      const T = this.getTransform(), kx = dw / sw, ky = dh / sh, clip = !!this.__clip || a.length === 8;
      for (const [txt, xs, ys, c0] of L) {
        if (Math.max(...xs) < sx || Math.min(...xs) > sx + sw || Math.max(...ys) < sy || Math.min(...ys) > sy + sh) continue;
        const X = [], Y = [];
        for (let k = 0; k < 4; k++) { const u = dx + (xs[k] - sx) * kx, v = dy + (ys[k] - sy) * ky; X.push(T.a * u + T.c * v + T.e); Y.push(T.b * u + T.d * v + T.f); }
        push(this, [txt, X, Y, c0 || clip]);
      }
    }
    return di.call(this, src, ...a);
  };
})();'''
GRAB = '''async ([id, lt, full]) => {
  window.__tb = true; window.__canvas.__tb = [];
  const s = performance.now();
  if (full) { await window.prepare(lt); window.renderFrame(lt); } else window.renderSolo(id, lt);
  window.__canvas.getContext('2d').getImageData(0, 0, 1, 1);           // force the GPU to finish before stopping the clock
  const ms = performance.now() - s;
  const M = window.__canvas, tb = (M.__tb || []).map(([t, xs, ys, c]) => [t, xs.map(v => v / M.width), ys.map(v => v / M.height), c]); window.__tb = null;
  return [ms, window.__canvas.toDataURL('image/png').split(',')[1], tb];
}'''

def perform_frame_issues(tb, band):
    """Framing problems in one frame: [(kind, text)]. All coordinates are fractions of the frame."""
    out, vi_entries = [], []
    for txt, cx_entries, cy_entries, clipped in tb:
        x0, y0, x1, y1 = min(cx_entries), min(cy_entries), max(cx_entries), max(cy_entries)
        ang_value = float(np.arctan2((cy_entries[1] - cy_entries[0]) * VH, (cx_entries[1] - cx_entries[0]) * VW))
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0 or h < 0.008: continue                 # text that's too small (<9px): ignore
        ix0_value, iy0_value, ix1_value, iy1_value = max(x0, 0), max(y0, 0), min(x1, 1), min(y1, 1)
        if ix1_value <= ix0_value or iy1_value <= iy0_value: continue                      # entirely off-frame: the camera didn't catch it, don't count it
        frac_value = (ix1_value - ix0_value) * (iy1_value - iy0_value) / (w * h)
        if frac_value < 0.9 and frac_value > 0.1: out.append(('clipped text', txt))
        if band and iy1_value > band + 0.004 and frac_value > 0.1: out.append(('text in subtitle band', txt))
        if not clipped: vi_entries.append((txt, ang_value, cx_entries, cy_entries))
    def box(v, ang_value):                                                    # take the box in the ang coordinate system: two lines of a slanted label don't "overlap" just because their bounding rects grew
        c, s_value = np.cos(-ang_value), np.sin(-ang_value)
        u = [x * c - y * s_value * VH / VW for x, y in zip(v[2], v[3])]; w = [x * s_value * VW / VH + y * c for x, y in zip(v[2], v[3])]
        return min(u), min(w), max(u), max(w)
    for i in range(len(vi_entries)):
        for inner_cursor in range(i + 1, len(vi_entries)):
            a, b = vi_entries[i], vi_entries[inner_cursor]
            if a[0] == b[0]: continue                                   # the same string drawn twice (stroke + fill, drop shadow)
            same = abs(a[1] - b[1]) < 0.02; ang_value = a[1] if same else 0.0
            A, B = box(a, ang_value), box(b, ang_value)
            if not same:                                                # different angles (hand-lettered jitter): the bounding rect grows, so inset each by 12% before comparing
                A, B = [(r[0] + (r[2] - r[0]) * .12, r[1] + (r[3] - r[1]) * .12, r[2] - (r[2] - r[0]) * .12, r[3] - (r[3] - r[1]) * .12) for r in (A, B)]
            ow_value = min(A[2], B[2]) - max(A[0], B[0]); oh_value = min(A[3], B[3]) - max(A[1], B[1])
            if ow_value <= 0 or oh_value <= 0: continue
            small_value = min((A[2] - A[0]) * (A[3] - A[1]), (B[2] - B[0]) * (B[3] - B[1]))
            if ow_value * oh_value / small_value > 0.3: out.append(('overlapping text', a[0] + '｜' + b[0]))
    return out

def perform_persistent(moment_stamp, per_frame_value, min_s=0.3):
    """Report a problem only when it persists ≥min_s seconds without a break (the few frames of clipped text while the camera pans past are normal)."""
    runs, unsealed_flag = [], {}
    for k, t in enumerate(moment_stamp):
        current_item = set(per_frame_value[k])
        for key in list(unsealed_flag):
            if key not in current_item:
                t0, t1 = unsealed_flag.pop(key)
                if t1 - t0 >= min_s: runs.append((key, t0, t1))
        for key in current_item:
            if key in unsealed_flag: unsealed_flag[key] = (unsealed_flag[key][0], t)
            else: unsealed_flag[key] = (t, t)
    runs += [(key, t0, t1) for key, (t0, t1) in unsealed_flag.items() if t1 - t0 >= min_s]
    return sorted(runs, key=lambda r: r[1])

def combine_runs(runs):
    """Text typed letter by letter yields one entry per letter: merge same-kind runs that overlap in time into one and concatenate the text."""
    out = []
    for (kind, txt), t0, t1 in sorted(runs, key=lambda r: (r[0][0], r[1])):
        if out and out[-1][0] == kind and t0 <= out[-1][3] + 0.05:
            item_object = out[-1]; item_object[3] = max(item_object[3], t1)
            if txt and txt not in item_object[1].split('、') and len(item_object[1]) < 60: item_object[1] = (item_object[1] + '、' + txt).strip('、')
        else: out.append([kind, txt, t0, t1])
    return sorted(out, key=lambda r: r[2])

def perform_near_blank(f):
    """Share of pixels differing >24 from the frame's dominant colour <0.3% reads as "almost no content"."""
    median_value = np.median(f.reshape(-1, 3), axis=0)
    return float((np.abs(f - median_value).max(axis=2) > 24).mean()) < 0.003
def layer_image(b64_value, w=480): return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64_value))).convert('RGB').resize((w, round(w * VH / VW)))).astype(np.int16)   # scale by aspect ratio so portrait films aren't squashed

def perform_camera_events(frames, diff_entries, idx, fps, max__entries=2.0):
    """Pick the camera moves (push/pull, glide, slam) out of the spikes (criteria in item 4 of the file header). idx: indices of the frame pairs holding spikes. Returns (indices that are still spikes, camera events [(l, r)])."""
    keep, events = [], []
    for i in idx:
        if any(l <= i <= r for l, r in events): continue
        thr_value = max(0.5, 0.1 * diff_entries[i]); l = r = i
        while l > 0 and diff_entries[l - 1] > thr_value: l -= 1
        while r < len(diff_entries) - 1 and diff_entries[r + 1] > thr_value: r += 1
        n = r - l + 1
        far_value = [float(np.abs(frames[k] - frames[l]).mean()) for k in range(l + 1, r + 2)]   # how far each frame in the run is from the first
        smooth = n <= 0.35 * fps + 1 or all(diff_entries[k] <= 2.5 * max(diff_entries[k - 1], diff_entries[k + 1]) + 0.5 for k in range(l + 1, r))   # runs longer than 0.35s must be smooth all the way, no single-frame peak in the middle
        if 2 <= n <= max__entries * fps + 1 and far_value[-1] >= 0.8 * max(far_value) and smooth: events.append((l, r))
        else: keep.append(i)
    return [i for i in keep if not any(l <= i <= r for l, r in events)], events

report = {'project': str(root), 'spec': str(Path(a.spec).resolve()) if a.spec else None, 'segments': []}
errors = []
with sync_playwright() as p:
    border_radius_value = p.chromium.launch(args=['--enable-gpu-rasterization', '--ignore-gpu-blocklist'])
    page_record = border_radius_value.new_page(viewport={'width': VW, 'height': VH})
    page_record.on('pageerror', lambda e: errors.append(str(e)))
    page_record.on('console', lambda m: errors.append('console.error: ' + m.text) if m.type == 'error' else None)   # missing glyphs and the like come out as console.error
    page_record.add_init_script(TEXT_HOOK)
    if spec:
        page_record.add_init_script('window.CLIP_SPEC = ' + json.dumps(spec, ensure_ascii=False) + ';')
        page_record.goto(f'http://127.0.0.1:{port}/clip.html?render=1')
    else:
        page_record.goto(f'http://127.0.0.1:{port}/index.html?render=1' + (f'&film={a.film}' if a.film else ''))
    page_record.wait_for_function('window.__ready === true || !!window.__bootFailed', timeout=180000)
    before_frame = page_record.evaluate('window.__bootFailed || null')
    if before_frame: raise SystemExit('❌ scene failed to load:\n' + before_frame)
    seg_entries = [{'id': Path(a.spec).resolve().parent.name, 't0': 0, 't1': spec['duration'], 'tr': 0}] if spec else \
        page_record.evaluate('ERAS.map(e => ({id: e.id, t0: e.t0, t1: Math.min(e.t1, window.__total), tr: e.transition ? e.transition.dur + (e.transition.delay || 0) : 0}))')
    want_value = set(a.ids.split(',')) if a.ids else None
    for s in seg_entries:
        if want_value and s['id'] not in want_value: continue
        dur = s['t1'] - s['t0']; lt0_value = max(a.skip, s['tr']) if s['t0'] > 0 else 0.0
        lt1_value = max(lt0_value + 0.2, dur - 0.02)
        n = max(4, int((lt1_value - lt0_value) * a.fps))
        moment_stamp = [lt0_value + (lt1_value - lt0_value) * i / (n - 1) for i in range(n)]
        full = bool(spec)                                   # clips have no renderSolo, so render whole frames
        cold_m_entries, cold, _ignored = page_record.evaluate(GRAB, [s['id'], moment_stamp[-1], full])
        frames, ms, tb_entries = [], [], []
        for t in moment_stamp:
            m, b64_value, tb = page_record.evaluate(GRAB, [s['id'], t, full]); ms.append(m); frames.append(layer_image(b64_value)); tb_entries.append(tb or [])
        _ignored, again_value, _ignored = page_record.evaluate(GRAB, [s['id'], moment_stamp[-1], full])
        detail_value = int(np.abs(layer_image(again_value) - frames[-1]).max()); det_cold_value = int(np.abs(layer_image(cold) - frames[-1]).max())
        diff_entries = np.array([(np.abs(frames[i + 1] - frames[i]).max(axis=2) > 12).mean() * 100 for i in range(len(frames) - 1)])
        median_value = float(np.median(diff_entries)) if len(diff_entries) else 0
        if spec:   # a clip mostly "moves once, then holds": the whole-run median is ≈0, so a continuous push/glide would be recorded as one long spike. For clips only isolated spikes count: 6× the median of the 3 pairs before and after
            loc_value = lambda i: float(np.median(np.r_[diff_entries[max(0, i - 3):i], diff_entries[i + 1:i + 4]])) if len(diff_entries) > 1 else 0
            segment_index = [i for i, d in enumerate(diff_entries) if d > 3 and d > 6 * max(loc_value(i), 0.05)]
        else:
            segment_index = [i for i, d in enumerate(diff_entries) if d > 3 and d > 6 * max(median_value, 0.05)]
        segment_index, cams = perform_camera_events(frames, diff_entries, segment_index, a.fps)
        spikes = [round(moment_stamp[i + 1], 3) for i in segment_index]
        still = float((diff_entries < 0.05).mean() * 100)
        heat_level = np.zeros(frames[0].shape[:2]); [heat_level.__iadd__((np.abs(frames[i + 1] - frames[i]).max(axis=2) > 12)) for i in range(len(frames) - 1)]
        rec = {'id': s['id'], 'window_lt': [round(lt0_value, 3), round(lt1_value, 3)], 'frames': n,
               'ms_mean': round(float(np.mean(ms)), 1), 'ms_max': round(float(np.max(ms)), 1), 'ms_cold': round(cold_m_entries, 1),
               'deterministic': detail_value == 0 and det_cold_value == 0, 'det_maxdiff': max(detail_value, det_cold_value),
               'motion_pct': round(float(diff_entries.mean()), 2), 'motion_max': round(float(diff_entries.max()), 2), 'still_pairs_pct': round(still, 1),
               'spike_ratio': round(float(diff_entries.max() / max(median_value, 0.05)), 1), 'spikes_at_lt': spikes,
               'camera_events_lt': [[round(moment_stamp[l], 3), round(moment_stamp[r + 1], 3)] for l, r in cams]}
        frame_run_entries = combine_runs(perform_persistent(moment_stamp, [perform_frame_issues(tb, a.sub_band) for tb in tb_entries]) +
                                perform_persistent(moment_stamp, [[('near blank', '')] if perform_near_blank(f) else [] for f in frames]))
        rec['framing'] = [{'kind': k, 'text': txt, 'lt': [round(t0, 2), round(t1, 2)], 't': [round(s['t0'] + t0, 2), round(s['t0'] + t1, 2)]} for k, txt, t0, t1 in frame_run_entries]
        rec['text_tracked'] = sum(map(len, tb_entries))
        report['segments'].append(rec)
        # contact sheet: 4 frames + heatmap
        pick_value = [frames[int(k)] for k in np.linspace(0, n - 1, 4)]
        H_, W_ = frames[0].shape[:2]; S = Image.new('RGB', (W_ * 5, H_ + 20), 'white'); dr_value = ImageDraw.Draw(S)
        for k, f in enumerate(pick_value): S.paste(Image.fromarray(f.astype(np.uint8)), (k * W_, 20))
        header_map = np.clip(heat_level / max(1, heat_level.max()) * 255, 0, 255).astype(np.uint8)
        base_folder = Image.fromarray(pick_value[0].astype(np.uint8)).convert('L').convert('RGB'); red_value = np.zeros((H_, W_, 3), np.uint8); red_value[..., 0] = header_map
        S.paste(Image.blend(base_folder, Image.fromarray(red_value), 0.6), (4 * W_, 20))
        dr_value.text((4, 4), f"{s['id']}  motion {rec['motion_pct']}%  still pairs {rec['still_pairs_pct']}%  spikes {len(spikes)}  camera events {len(cams)}  {rec['ms_mean']}/{rec['ms_max']}ms  deterministic {'✓' if rec['deterministic'] else '✗'}", fill='black')
        S.save(out / f"{s['id']}.jpg", quality=85)
        print(f"{s['id']:<18} motion {rec['motion_pct']:>5}%  still pairs {rec['still_pairs_pct']:>5}%  spikes {len(spikes)}  camera events {len(cams)}  {rec['ms_mean']:>6}/{rec['ms_max']:>6}ms  deterministic {'✓' if rec['deterministic'] else '✗ ' + str(rec['det_maxdiff'])}  framing {len(rec['framing'])}")
        for r in rec['framing']: print(f"    {r['kind']}  {r['t'][0]:.2f}–{r['t'][1]:.2f}s  {r['text']}")
    # transition smoke test: only checks that it renders and how long it takes; doesn't feed the motion/smoothness criteria
    report['transitions'] = []
    for s in ([] if spec else page_record.evaluate('ERAS.map(e => ({id: e.id, t0: e.t0, tr: e.transition ? {type: e.transition.type, dur: e.transition.dur, delay: e.transition.delay || 0} : null}))')):
        if not s['tr'] or (want_value and s['id'] not in want_value): continue
        ms_tr_value = []
        for p in (0.25, 0.5, 0.75):
            t = s['t0'] + s['tr']['delay'] + s['tr']['dur'] * p
            try:
                m, *_ignored = page_record.evaluate(GRAB, [s['id'], t, True]); ms_tr_value.append(m)
            except Exception as ex:
                errors.append(f"transition {s['tr']['type']} (entering {s['id']}) p={p}: {str(ex).splitlines()[0]}")
        report['transitions'].append({'id': s['id'], 'type': s['tr']['type'], 'ms_max': round(max(ms_tr_value), 1) if ms_tr_value else None})
    if report['transitions']: print('transition smoke', len(report['transitions']), 'segments, slowest', max((r['ms_max'] or 0, r['type']) for r in report['transitions']))
    border_radius_value.close()
server_object.shutdown()
server_object.server_close()
report['page_errors'] = errors
json.dump(report, open(out / 'qa.json', 'w'), ensure_ascii=False, indent=1)
table_rows = ['| segment | motion% | still pairs% | spikes | camera events | mean/peak ms | cold ms | deterministic | framing |', '|---|---|---|---|---|---|---|---|---|']
for r in report['segments']:
    table_rows.append(f"| {r['id']} | {r['motion_pct']} | {r['still_pairs_pct']} | {len(r['spikes_at_lt'])} {r['spikes_at_lt'][:3]} | {len(r['camera_events_lt'])} | {r['ms_mean']}/{r['ms_max']} | {r['ms_cold']} | {'✓' if r['deterministic'] else '✗'} | {len(r['framing'])} |")
fr = [(r['id'], x) for r in report['segments'] for x in r['framing']]
if fr: table_rows += ['', 'Framing clues (whole-film seconds, persisting ≥0.3s; look at these frames before judging):'] + [f"- {x['kind']} {x['t'][0]:.2f}–{x['t'][1]:.2f}s ({i}) {x['text']}" for i, x in fr]
if report.get('transitions'): table_rows += ['', 'Transition smoke (whole frames, peak ms): ' + ', '.join(f"{r['type']}→{r['id']} {r['ms_max']}" for r in report['transitions'])]
(out / 'qa.md').write_text('\n'.join(table_rows) + ('\n\nPage errors:\n' + '\n'.join(errors) if errors else '') + '\n')
print('->', out / 'qa.md')
if not spec and root != Path(__file__).resolve().parent / 'engine':   # backflow fallback (§1 of the evolution protocol): qa must run before delivery, so remind here without failing qa
    import re, time
    draft = next((d / 'lessons-draft.md' for d in (root.parent, root.parent.parent) if (d / 'lessons-draft.md').exists()), None)
    if not draft: print(f'Backflow reminder: the project root ({root.parent.name}) has no lessons-draft.md yet. Append a few entries after each round of changes; the format is in section 4 of the skill\'s references/art-motion/12-whole-film-feedback.md.')
    else:
        txt = draft.read_text(); age = (time.time() - draft.stat().st_mtime) / 60
        tail_text = txt.rsplit('> watermark', 1)[-1] if '> watermark' in txt else txt     # below the watermark = not yet written back to the skill
        n = len(re.findall(r'^### \[', tail_text, re.M))
        print(f'Backflow reminder: lessons-draft.md was last written {age:.0f} minutes ago; {n} entries have not been written back to the skill (consolidate them per the destination table in §11 when wrapping up, then add a line "> watermark <time>" at the end of the draft).')
if errors: raise SystemExit('❌ %d page runtime errors, see qa.md' % len(errors))
