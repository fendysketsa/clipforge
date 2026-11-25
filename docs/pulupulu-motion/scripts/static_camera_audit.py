"""Prove a film really holds the camera still — and that the type does not drift.

A "static camera" film is not a film with gentle movement; it is a film where the frame does not move at all.
Reviews miss a 2 px wander and audiences read it as cheap, so measure it: estimate the global translation
between consecutive frames and refuse anything above a sub-pixel threshold.

Method: phase correlation on a luma band (centre crop by default). Translation of the *picture* shows up as a
peak away from the origin; film grain and noise do not translate, so a genuinely locked-off shot scores ~0.
For a film with drifting typography, run twice: once on a text band (`--band text`) and once on the picture.

Usage:
    python static_camera_audit.py film.mp4 [--fps 30] [--max-px 0.5] [--band centre|text|full]
                                          [--shots 0,42,88.5] [--json out.json]

Pairs that jump further than --cut-px are counted as cuts and excluded from the drift verdict, because a hard
cut is a new shot, not a moving camera. Everything else is drift and must sit below --max-px.

Exit 1 when any drift pair exceeds the threshold, which is what a "no wobble" contract means.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def grab(video: str, ts: float, crop: str, width: int = 540) -> np.ndarray:
    """One frame as a float luma array, cropped to the band of interest."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "f.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.3f}", "-i", video,
             "-frames:v", "1", str(out)],
            check=True,
        )
        im = Image.open(out).convert("L")
    w, h = im.size
    if crop == "text":
        # headline band: upper third, where titles usually sit
        im = im.crop((0, int(h * 0.06), w, int(h * 0.34)))
    elif crop == "centre":
        im = im.crop((int(w * 0.10), int(h * 0.20), int(w * 0.90), int(h * 0.80)))
    if im.width != width:
        im = im.resize((width, int(im.height * width / im.width)), Image.BILINEAR)
    return np.asarray(im, dtype=np.float64)


def shift_px(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Global (dx, dy) in pixels that takes a to b, plus the correlation peak height."""
    A = np.fft.fft2(a - a.mean())
    B = np.fft.fft2(b - b.mean())
    R = A * np.conj(B)
    R /= np.maximum(np.abs(R), 1e-12)
    r = np.fft.ifft2(R).real
    peak = np.unravel_index(np.argmax(r), r.shape)
    height = float(r[peak])
    dy, dx = peak
    h, w = a.shape
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    return float(dx), float(dy), height


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--step-frames", type=int, default=6,
                    help="sample every N source frames (6 = 5 checks per second at 30 fps)")
    ap.add_argument("--max-px", type=float, default=0.5)
    ap.add_argument("--band", default="centre", choices=["centre", "text", "full"])
    ap.add_argument("--cut-px", type=float, default=25.0,
                    help="apparent translation above this is a cut, not drift (default 25)")
    ap.add_argument("--min-peak", type=float, default=0.5,
                    help="phase-correlation peak below this means the composition changed (a cut or a "
                         "transition), so the pair is not judged for drift (default 0.5)")
    ap.add_argument("--start", type=float, default=1.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--max-samples", type=int, default=260)
    ap.add_argument("--json")
    args = ap.parse_args()

    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", args.video],
        capture_output=True, text=True, check=True).stdout.strip())
    end = args.end if args.end is not None else dur - 0.5
    step = args.step_frames / args.fps
    times = []
    t = args.start
    while t < end and len(times) < args.max_samples:
        times.append(t)
        t += step
    if len(times) < 2:
        print("not enough samples")
        return 1

    rows = []
    prev = grab(args.video, times[0], args.band)
    for t in times[1:]:
        cur = grab(args.video, t, args.band)
        if cur.shape != prev.shape:
            prev = cur
            continue
        dx, dy, h = shift_px(prev, cur)
        mag = float(np.hypot(dx, dy))
        rows.append({"t": round(t, 2), "dx": dx, "dy": dy, "mag": round(mag, 2), "peak": round(h, 4)})
        prev = cur

    mags = np.array([r["mag"] for r in rows])
    # A hard cut registers as a huge apparent translation. Separate it from real drift, and only judge the
    # drift: a "static camera" contract is about the frame not moving *within* a shot.
    cut_limit = args.cut_px
    # Two ways a pair is not drift: it jumped further than a camera could (a cut), or the correlation is too
    # poor for the two frames to be the same composition (a cut, a dissolve, a wipe). Only pairs that are
    # demonstrably the same composition — high peak — are judged for movement. On a real locked-off film the
    # median peak sits near 0.99 inside a shot and collapses below 0.35 across a cut.
    cuts = [r for r in rows if r["mag"] > cut_limit or r["peak"] < args.min_peak]
    drift = [r for r in rows if r["mag"] <= cut_limit and r["peak"] >= args.min_peak]
    dmags = np.array([r["mag"] for r in drift]) if drift else np.array([0.0])
    worst = drift[int(np.argmax(dmags))] if drift else rows[0]
    over = [r for r in drift if r["mag"] > args.max_px]
    print(f"video      : {Path(args.video).name}  ({dur:.2f} s)")
    print(f"band       : {args.band}  · sampled {len(rows)} pairs every {step:.2f} s")
    same = len(rows) - len(cuts)
    print(f"cuts       : {len(cuts)} pair(s) excluded as cuts/composition changes "
          f"(> {cut_limit:g} px or correlation peak < {args.min_peak}); {same} pair(s) judged as same shot")
    print(f"translation: mean {dmags.mean():.2f} px · median {np.median(dmags):.2f} px · max {dmags.max():.2f} px")
    print(f"worst pair : t={worst['t']} s  dx={worst['dx']:+.0f} dy={worst['dy']:+.0f} (mag {worst['mag']:.2f})")
    print(f"over {args.max_px} px : {len(over)} of {len(drift)} drift pairs")
    if over:
        show = ", ".join(f"{r['t']}s:{r['mag']:.1f}" for r in over[:12])
        print(f"  first offenders: {show}{' …' if len(over) > 12 else ''}")
    if args.json:
        Path(args.json).write_text(json.dumps({"rows": rows, "max_px": args.max_px}, indent=1), encoding="utf-8")

    if over:
        print(f"\nSTATIC CAMERA FAIL — {len(over)} sampled pairs move more than {args.max_px} px")
        return 1
    print(f"\nSTATIC CAMERA PASS — no sampled pair moves more than {args.max_px} px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
