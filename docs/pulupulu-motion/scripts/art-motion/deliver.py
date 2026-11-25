# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""deliver.py — one-command delivery: run the motion gate, red light ships nothing; green or yellow copies the master out and writes the delivery note, whose facts are all written by the script.

    uv run deliver.py <master.mp4> --out output/ [--spec clip.json | --project <code project>] [--qa <qa output dir>] [--root <project dir>]
                      [--sub-band 0.15] [--vertical auto|yes|no] [--allow-blue-purple "reason"]
    uv run deliver.py --verify output/delivery-note.md       # check whether the facts section was edited

Does three things:
  1. Runs film_gate.py from the same directory. Red light: no master copied, no note written; prints the
     reason and how to fix it, exit code 2.
  2. Green or yellow: copies the master to --out and writes --out/delivery-note.md. Every facts line is written
     by the script: duration, resolution, frame rate, audio track, file fingerprint; each gate metric and
     its light; the worst 30-second window; whether qa ran and how it came out (reads qa.json from the qa
     output directory, writes "not run" when absent); whether an independent review record exists
     (<project dir>/review/*.md — lists the filenames, writes "no review dispatched" when there are none).
  3. The facts section ends with a fingerprint. The maker only adds subjective prose in the "Production
     notes" section (which grammar was used, why each yellow item is acceptable, the six-ways-to-break-it
     self-check) and never touches the facts section; --verify reports any edit there.

Conventions:
  - qa output directory: --qa wins; otherwise the same default as qa.py — --spec → <directory of spec>/qa,
    --project → <parent of the code project>/qa.
  - Project directory: --root wins; otherwise the parent of --project; otherwise the directory of the spec;
    otherwise the directory of the master.
  - The reviewer (an agent or a person who did not make the film) writes their conclusion to
    <project dir>/review/<any name>.md. The script only checks whether the file exists, does not read it,
    and does not draw conclusions on the reviewer's behalf.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import film_gate  # noqa: E402

# Delivery-note filename: kept in Chinese so existing output directories and --verify paths keep working.
DOC = "delivery-note.md"
# Facts-section markers: kept verbatim so notes written by earlier versions still verify.
START = "<!-- deliver.py facts: begin. This section is generated; do not edit it. deliver.py --verify reports any change -->"
END_RE = re.compile(r"<!-- deliver\.py facts: end sha256=([0-9a-f]{64}) -->")
LIGHT_ZH = {"red": "Red", "yellow": "Yellow", "green": "Green", "--": ""}


def probe_result(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,codec_name,width,height,avg_frame_rate:format=duration",
                                   "-of", "json", str(path)])
    inner_cursor = json.loads(out)
    v = next(s for s in inner_cursor["streams"] if s.get("codec_type") == "video")
    a = [s for s in inner_cursor["streams"] if s.get("codec_type") == "audio"]
    quantity_value, _ignored, density_value = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(quantity_value) / float(density_value or 1) if float(density_value or 1) else 0.0
    return {"duration": float(inner_cursor["format"].get("duration") or 0), "width": v["width"], "height": v["height"],
            "fps": round(fps, 3), "vcodec": v.get("codec_name"), "audio": a[0].get("codec_name") if a else None}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def stamp(input_path):
    return datetime.datetime.fromtimestamp(input_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def collect_qa_facts(active_qa_dir, spec):
    """Read qa.py's output. Returns the facts lines (a list)."""
    if active_qa_dir is None:
        return ["- Not run (no --spec / --project / --qa given, so there is no way to know where qa output lives)"]
    f = active_qa_dir / "qa.json"
    if not f.is_file():
        return [f"- Not run (`{f}` does not exist)"]
    try:
        r = json.loads(f.read_text())
    except (ValueError, OSError) as e:
        return [f"- Cannot read qa.json: `{f}` ({type(e).__name__}); counted as not run"]
    segs = r.get("segments", [])
    det = sum(1 for s in segs if s.get("deterministic"))
    spikes = sum(len(s.get("spikes_at_lt", [])) for s in segs)
    cams = sum(len(s.get("camera_events_lt", [])) for s in segs)
    framing = sum(len(s.get("framing", [])) for s in segs)
    errs = r.get("page_errors", [])
    L = [f"- Ran: `{f}` (written {stamp(f)})",
         f"- Page errors: {len(errs)}" + (" (qa verdict: failed)" if errs else ""),
         f"- Determinism: {det}/{len(segs)} segments pixel-identical",
         f"- Jump cuts: {spikes}" + (f"; plus {cams} camera events (monotonic, smooth push/pull or pan under 2 seconds — not counted as jumps)" if "camera_events_lt" in (segs[0] if segs else {}) else ""),
         f"- Framing hints: {framing} (cut-off glyphs, overlapping text, text intruding into the subtitle band, near-blank frames; these mean \"go look at this frame\", they are not errors)"]
    for s in segs:
        L.append(f"  - {s.get('id')}: motion {s.get('motion_pct')}%, still pairs {s.get('still_pairs_pct')}%, "
                 f"jumps {len(s.get('spikes_at_lt', []))}, {s.get('ms_mean')}/{s.get('ms_max')} ms/frame")
    if spec is not None and r.get("spec") and Path(r["spec"]).resolve() != spec.resolve():
        L.append(f"- Note: this qa.json measured a different spec ({r['spec']}), not {spec}")
    if spec is not None and spec.is_file() and spec.stat().st_mtime > f.stat().st_mtime:
        L.append(f"- Note: the spec changed after qa ran (spec written {stamp(spec)}); these qa results may be stale")
    return L


def collect_review_facts(root):
    d = root / "review"
    files = sorted(input_path.name for input_path in d.glob("*.md")) if d.is_dir() else []
    if not files:
        return [f"- No review dispatched (no .md files under `{d}`)"]
    return [f"- {len(files)} review record(s) (`{d}`): " + ", ".join(files),
            "- The script only confirms the files exist and never reads them; the review conclusion is whatever the files themselves say"]


def perform_facts_block(src, dst, info, res, table_rows, qa_line_entries, rv_line_entries):
    ex = res["explain"]
    gl = res["gate_light"]
    L = ["## Facts (written by deliver.py)", "",
         f"- Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
         f"- Master: `{dst.name}` (sha256 {sha256(dst)[:16]}; source `{src}`)",
         f"- Duration {info['duration']:.2f}s  |  {info['width']}×{info['height']}  |  {info['fps']:g}fps  |  video {info['vcodec']}  |  "
         f"audio: {info['audio'] or 'none'}",
         "", "### Gate (film_gate)", "",
         f"- Verdict: {LIGHT_ZH[gl]}. Fast-motion frame ratio {res['fast_ratio']} (< 0.035 is red, < 0.06 is yellow)",
         f"- In one line: {ex['summary']}." + ("; ".join(ex["why"]) + "." if ex["why"] else "")]
    if res.get("allow_blue_purple"):
        L.append(f"- Maker declared the subject calls for blue/purple (blue-purple gate relaxed to yellow): {res['allow_blue_purple']}; blue/purple background share {res['blue_purple_share']:.0%}")
    if ex["worst_window"]:
        w = ex["worst_window"]
        L.append(f"- Worst {w['end_s'] - w['start_s']:.0f}-second window: {w['start_s']:.0f}–{w['end_s']:.0f}s, fast-motion frame ratio {w['fast_ratio']}")
    if ex["fix"]:
        L.append(f"- How to fix: {ex['fix']}")
    L += ["", "| Light | Type | Metric | Value |", "|---|---|---|---|"]
    for sort_key, name, v, lv, gate, unit in table_rows:
        vs = "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
        L.append(f"| {LIGHT_ZH[lv] or 'value only'} | {'gate' if gate else 'report'} | {name} | {vs}{unit} |")
    L += ["", "### qa", ""] + qa_line_entries + ["", "### Independent review", ""] + rv_line_entries
    return "\n".join(L) + "\n"


def emit_doc(out, dst, facts, res):
    h = hashlib.sha256(facts.encode()).hexdigest()
    look = [t for _ignored, t in res["explain"]["look"]]
    if res["lights"]["fast_ratio"] == "yellow":
        look.insert(0, f"Gate yellow: fast-motion frame ratio {res['fast_ratio']} (yellow line 0.06)")
    tail_text = ["## Production notes (written by the maker; write only in this section, leave the facts section alone)", "",
            "- Grammar / style used:",
            "- Self-check against the six ways to break it, one by one:",
            "- Yellow items, one by one (timecode + why this is acceptable):" + ("" if look else " no yellow items")]
    tail_text += [f"  - {t}:" for t in look]
    doc = f"# Delivery note: {dst.name}\n\n{START}\n{facts}<!-- deliver.py facts: end sha256={h} -->\n\n" + "\n".join(tail_text) + "\n"
    (out / DOC).write_text(doc)
    return out / DOC


def verify(path):
    t = Path(path).read_text()
    cursor = t.find(START)
    m = END_RE.search(t)
    if cursor < 0 or not m or m.start() < cursor:
        print(f"❌ {path}: cannot find the facts-section start/end markers (deleted, or not written by deliver.py)"); return 3
    facts = t[cursor + len(START) + 1: m.start()]
    if hashlib.sha256(facts.encode()).hexdigest() != m.group(1):
        print(f"❌ {path}: the facts section was edited and no longer matches what deliver.py wrote. Re-run deliver.py to regenerate it."); return 3
    print(f"✓ {path}: facts section matches what deliver.py wrote"); return 0


def run_cli():
    argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argument_parser.add_argument("mp4", nargs="?")
    argument_parser.add_argument("--out", help="delivery directory (e.g. output/)")
    argument_parser.add_argument("--spec", help="parameterized clip spec (used to find qa output: <directory of spec>/qa)")
    argument_parser.add_argument("--project", help="code project directory (used to find qa output: <parent of code project>/qa)")
    argument_parser.add_argument("--qa", help="qa output directory (for when qa.py --out wrote somewhere else)")
    argument_parser.add_argument("--root", help="project directory (looks for review/*.md under it)")
    argument_parser.add_argument("--sub-band", type=float, default=None, help="same as film_gate.py: fraction of the bottom subtitle band to mask")
    argument_parser.add_argument("--vertical", default="auto", choices=["auto", "yes", "no"])
    argument_parser.add_argument("--verify", metavar="delivery-note.md", help="only check whether the facts section was edited")
    argument_parser.add_argument("--allow-blue-purple", metavar="reason", default=None,
                    help="same as film_gate.py: when the subject itself calls for blue/purple, give the reason here and it is written into the delivery-note facts section")
    a = argument_parser.parse_args()
    if a.verify:
        sys.exit(verify(a.verify))
    if not a.mp4 or not a.out:
        argument_parser.error("a master and --out are required")
    src = Path(a.mp4).resolve()
    if not src.is_file():
        print(f"Master not found: {src}", file=sys.stderr); sys.exit(1)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe required", file=sys.stderr); sys.exit(1)
    spec = Path(a.spec).resolve() if a.spec else None
    project_folder = Path(a.project).resolve() if a.project else None
    active_qa_dir = Path(a.qa).resolve() if a.qa else spec.parent / "qa" if spec else project_folder.parent / "qa" if project_folder else None
    root = Path(a.root).resolve() if a.root else project_folder.parent if project_folder else spec.parent if spec else src.parent

    try:
        info = probe_result(src)
        res, table_rows = film_gate.measure(str(src), sub_band=a.sub_band, vertical=a.vertical, allow_blue_purple=a.allow_blue_purple)
    except (subprocess.CalledProcessError, StopIteration, KeyError, RuntimeError, ValueError) as e:
        print(f"Cannot read this master: {src} ({e})", file=sys.stderr); sys.exit(1)
    print("\n".join(film_gate.render_finding_report(res, table_rows)))
    ex = res["explain"]
    if res["verdict"] == "red":
        print(f"\n❌ Red light, not delivering: {ex['summary']}." + ("; ".join(ex["why"]) + "." if ex["why"] else ""))
        print("How to fix: " + ex["fix"])
        print(f"No master was copied and no {DOC} was written. Fix it, re-render, then run deliver.py again.")
        sys.exit(2)

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    dst = out / src.name
    if dst != src:
        shutil.copy2(src, dst)
    qa_line_entries, rv_line_entries = collect_qa_facts(active_qa_dir, spec), collect_review_facts(root)
    facts = perform_facts_block(src, dst, info, res, table_rows, qa_line_entries, rv_line_entries)
    doc = emit_doc(out, dst, facts, res)
    gl = res["gate_light"]
    print(f"\n{'✓ Green light' if gl == 'green' else '⚠ Yellow light'}, delivered: {dst}")
    print(f"Delivery note: {doc} (facts section written by the script; add subjective prose only in the Production notes section)")
    print("qa: " + qa_line_entries[0][2:])
    print("review: " + rv_line_entries[0][2:])
    if ex["look"]:
        print("Each yellow item needs a timecode and a reason in the delivery note: " + "; ".join(t for _ignored, t in ex["look"]))
    sys.exit(0)


if __name__ == "__main__":
    run_cli()
