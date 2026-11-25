#!/usr/bin/env python3
"""Frame-by-frame render: start a local http server → headless Chromium opens index.html → call window.renderFrame(t) for each frame
→ read canvas pixels → pipe them to ffmpeg for a 60fps mp4, then mix in the audio track.

uv run --with playwright python render.py --out ../final-cut/replica_v1.mp4 [--audio ../audio/replica-soundtrack.wav] [--from 0 --to runtime] [--fps 60]
    [--film gallery] (reads eras_gallery.js) [--solo <id> --stills 0.2,0.6 --no-counter] [--width 1080 --height 1920] (full vertical film: passed to index.html?w=&h=,
    the engine, transitions, camera and all libraries compute against this canvas; if omitted, window.FILM_SIZE from eras.js is used, else 1920×1080)
uv run --with playwright python render.py --spec clip.json --out clip.mp4 [--alpha] [--stills 0.5,2]
    Parameterized clip (the "animation segment" of the voiceover pipeline; contract in references/09): duration is strictly = spec.duration (frame count round(duration×fps)),
    width/height/fps are read from the spec; by default silent H.264 yuv420p with one keyframe per second (GOP=fps, since the pipeline renderer seeks by the second); --alpha emits ProRes 4444 with alpha (.mov). Image paths inside the spec are relative to the spec file.
Any pageerror or console.error on the page (scene error, missing glyph) → non-zero exit after rendering.
"""
import argparse, base64, http.server, json, socketserver, subprocess, sys, threading, functools, time, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import spec_assets
from playwright.sync_api import sync_playwright

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--out', help='output file (optional with --audit)')
argument_parser.add_argument('--audio')
argument_parser.add_argument('--fps', type=int, default=60)
argument_parser.add_argument('--from', dest='t0', type=float, default=0)
argument_parser.add_argument('--to', dest='t1', type=float, default=None, help='default = total runtime computed from the segment table (window.__total)')
argument_parser.add_argument('--stills', help='comma-separated seconds: export a png at each of these times only, into the --out directory')
argument_parser.add_argument('--solo', help='render only one era (time is local to that segment); use with --stills or --from/--to')
argument_parser.add_argument('--film', default='', help='film name: reads eras_<name>.js (default eras.js)')
argument_parser.add_argument('--no-counter', action='store_true', help='do not draw the corner counter with --solo')
argument_parser.add_argument('--crf', type=int, default=14)
argument_parser.add_argument('--spec', help='parameterized clip spec.json (goes through clip.html, ignores the segment table)')
argument_parser.add_argument('--alpha', action='store_true', help='with --spec, write ProRes 4444 with alpha (background not drawn)')
argument_parser.add_argument('--width', type=int, help='canvas width for full-film mode (1080 for vertical); with --spec the width/height come from the spec, and setting this overrides it')
argument_parser.add_argument('--height', type=int, help='canvas height for full-film mode (1920 for vertical)')
argument_parser.add_argument('--audit', nargs='?', const='-', help='layout audit (only with --spec): no video; samples a frame every 0.25s and records the position/size/alpha of every fillText on the main canvas, flagging text running off-canvas, text that is too small, and text overlapping text; accepts an optional JSON output path')
a = argument_parser.parse_args()
if not a.out and not a.audit: argument_parser.error('--out is required (unless --audit is used)')

base_folder = Path(__file__).parent
spec, ALLOWED = None, set()
if a.spec:
    span_length = Path(a.spec).resolve(); spec = json.loads(span_length.read_text())
    try: spec_assets.localize_spec_paths(spec, span_length.parent, ALLOWED)   # local paths in image / frames / data.character → /__file__/<absolute path> (only files named in the spec are served)
    except FileNotFoundError as e: raise SystemExit(str(e))
    if a.alpha: spec['alpha'] = True
    if a.width or a.height: spec['width'], spec['height'] = a.width or spec.get('width', 1920), a.height or spec.get('height', 1080)
# One parameterized clip stretched too long reads like a slide deck (a single layout to the end, points piling up). Warn only, never fail: the pipeline contains legitimate long clips.
LONG_CLIP = None
if spec and float(spec.get('duration', 0)) > 8:
    LONG_CLIP = ('\n' + '!' * 72 + f'\n!! WARNING: this clip has duration = {spec["duration"]} seconds, over 8 seconds.\n'
                 '!! A single clip stretched this long reads like a slide deck: one layout to the end, bullet points piling up, a dead-still background throughout.\n'
                 '!! Split it into multiple shots: 2–6 seconds each, changing grammar or approach (scenes, real footage), then stitch them together (SKILL.md track file, steps 3–4).\n'
                 '!! If the voiceover pipeline genuinely needs one long clip, you can ignore this.\n' + '!' * 72 + '\n')
    print(LONG_CLIP, file=sys.stderr, flush=True)

AUDIT_JS = r"""
(() => {
  window.__AUDIT = []; window.__auditT = 0;
  const P = CanvasRenderingContext2D.prototype;
  for (const fn of ['fillText', 'strokeText']) {
    const orig = P[fn];
    P[fn] = function (text, x, y) {
      try {
        if (fn === 'fillText' && this.canvas === window.__canvas && String(text).trim()) {
          const m = this.measureText(String(text)), tf = this.getTransform(), l = m.actualBoundingBoxLeft, r = m.actualBoundingBoxRight, as = m.actualBoundingBoxAscent, ds = m.actualBoundingBoxDescent;
          const pts = [[x - l, y - as], [x + r, y - as], [x + r, y + ds], [x - l, y + ds]].map(q => [tf.a * q[0] + tf.c * q[1] + tf.e, tf.b * q[0] + tf.d * q[1] + tf.f]);
          const xs = pts.map(q => q[0]), ys = pts.map(q => q[1]), px = parseFloat(this.font) * Math.hypot(tf.a, tf.b);
          window.__AUDIT.push({ t: window.__auditT, text: String(text), x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys), px, a: this.globalAlpha });
        }
      } catch (e) {}
      return orig.apply(this, arguments);
    };
  }
})();
"""

class Q(http.server.SimpleHTTPRequestHandler):
    def note_message(self, *x): pass
    def translate_path(self, path):
        if path.startswith('/__file__/'):
            f = urllib.parse.unquote(path[len('/__file__/'):].split('?')[0])
            return f if spec and f in ALLOWED else '/nonexistent'
        return super().translate_path(path)
# Chromium may open idle connections while loading scripts in parallel.
class LocalServer(socketserver.ThreadingTCPServer):
    queue_depth = 128
    daemon_thread_flag = True

server_object = LocalServer(('127.0.0.1', 0), functools.partial(Q, directory=str(base_folder)))
port = server_object.server_address[1]
threading.Thread(target=server_object.serve_forever, daemon=True).start()

with sync_playwright() as input_path:
    b = input_path.chromium.launch(args=['--disable-web-security', '--enable-gpu-rasterization', '--ignore-gpu-blocklist'])
    page_record = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    errors = []
    def perform_on_console(m):
        if m.type in ('error', 'warning'): print('[page]', m.text)
        if m.type == 'error': errors.append(m.text)
    page_record.on('console', perform_on_console)
    page_record.on('pageerror', lambda e: (print('[pageerror]', e), errors.append(str(e))))
    if spec:
        page_record.set_viewport_size({'width': spec.get('width', 1920), 'height': spec.get('height', 1080)})
        page_record.add_init_script('window.CLIP_SPEC = ' + json.dumps(spec, ensure_ascii=False) + ';')
        if a.audit: page_record.add_init_script(AUDIT_JS)
        page_record.goto(f'http://127.0.0.1:{port}/clip.html?render=1')
    else:
        if a.width or a.height:
            if not (a.width and a.height): raise SystemExit('--width and --height must be given together')
            page_record.set_viewport_size({'width': a.width, 'height': a.height})
        page_record.goto(f'http://127.0.0.1:{port}/index.html?render=1' + (f'&film={a.film}' if a.film else '') + (f'&w={a.width}&h={a.height}' if a.width else ''))
    page_record.wait_for_function('window.__ready === true || !!window.__bootFailed', timeout=120000)
    before_frame = page_record.evaluate('window.__bootFailed || null')
    if before_frame: raise SystemExit('Scene failed to load, refusing to render:\n' + before_frame)
    if a.t1 is None: a.t1 = page_record.evaluate('window.__total')
    if spec: a.fps = spec.get('fps', 30); a.t0 = 0; a.t1 = spec['duration']
    capture_frame = '''async (t)=>{ await window.prepare(t); window.renderFrame(t); return window.__canvas.toDataURL('image/png').split(',')[1]; }'''

    if a.audit:
        if not spec: raise SystemExit('--audit can only be used with --spec')
        import audit_clip
        rep_value = audit_clip.run(page_record, spec, capture_frame)
        if a.audit != '-': Path(a.audit).write_text(json.dumps(rep_value, ensure_ascii=False, indent=1))
        b.close(); server_object.shutdown(); server_object.server_close()
        sys.exit(1 if rep_value['red'] else 0)
    if a.solo:
        capture_frame = '''async (t)=>{ window.renderSolo(%s, t, {counter: %s}); return window.__canvas.toDataURL('image/png').split(',')[1]; }''' % (repr(a.solo), 'false' if a.no_counter else 'true')
    if a.stills:
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        for s in a.stills.split(','):
            (out / f't{float(s):06.2f}.png').write_bytes(base64.b64decode(page_record.evaluate(capture_frame, float(s))))
        print('stills ->', out)
    else:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        vid_value = a.out if not a.audio else a.out + '.noaudio.mp4'
        enc_value = ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-alpha_bits', '16'] if (spec and a.alpha) else \
              ['-c:v', 'libx264', '-preset', 'slow', '-crf', str(a.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart'] + \
              (['-g', str(a.fps), '-keyint_min', str(a.fps), '-sc_threshold', '0'] if spec else [])   # the pipeline renderer seeks clips by the second: one keyframe per second, otherwise frames freeze
        if spec and a.alpha and not vid_value.endswith('.mov'): print('Note: ProRes 4444 usually uses a .mov container')
        ff_value = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'image2pipe', '-framerate', str(a.fps), '-c:v', 'png', '-i', '-'] + enc_value + [vid_value],
                              stdin=subprocess.PIPE)
        first_count, n1 = round(a.t0 * a.fps), round(a.t1 * a.fps)
        st = time.time()
        for i in range(first_count, n1):
            ff_value.stdin.write(base64.b64decode(page_record.evaluate(capture_frame, i / a.fps)))
            if (i - first_count) % 60 == 0:
                print(f'{i}/{n1}  {time.time()-st:.0f}s', flush=True)
        ff_value.stdin.close(); ff_value.wait()
        if a.audio:
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', vid_value, '-ss', str(a.t0), '-t', str(a.t1 - a.t0), '-i', a.audio,
                            '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', a.out], check=True)
            Path(vid_value).unlink()
        print('done ->', a.out)
    b.close()
server_object.shutdown()
server_object.server_close()
if LONG_CLIP: print(LONG_CLIP, file=sys.stderr)   # say it again after rendering so the progress lines do not bury it
if errors: raise SystemExit(f'❌ page reported {len(errors)} errors (see [page]/[pageerror] above)')
