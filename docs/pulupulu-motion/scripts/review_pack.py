#!/usr/bin/env python3
"""Build a review pack from a finished film so an outside model can judge colour AND motion.

A still proves nothing about easing, weight or colour in motion, and "nothing moves here" has to be a
measurement rather than an opinion. This emits three layers plus the numbers:

  frames/   one full frame every --every seconds (default 3)
  motion/   triptychs at each beat: frame t | frame t+0.4 | amplified absolute difference,
            with the changed-pixel count in the filename
  strips/   N consecutive frames at 8 fps inside a 0.75 s window, cropped to the action area and tiled
            left to right — the only one of the three that shows the SHAPE of a movement
  measured.json  frame size, per-moment changed pixels, and the share of frame

Usage:
    python review_pack.py --src out/film.mp4 [--timeline timeline.json] [--out review]
                          [--every 3] [--strips 11.4 17.0 21.0] [--crop 300 1500]

Feed the pack, not a description: `second-opinion-review/references/delegated-build.md` for the loop.
"""
import argparse
import json
import os
import subprocess

import numpy as np
from PIL import Image

CHANGE_THRESHOLD = 8   # per-channel difference that counts as "this pixel moved"
AMPLIFY = 4            # difference multiplier for the visible panel


def probe_duration(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", src], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def grab(src, t, path):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", src,
                    "-frames:v", "1", path], check=True)
    return Image.open(path).convert("RGB")


def changed(a, b):
    diff = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    return diff, int((diff > CHANGE_THRESHOLD).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--timeline", default="timeline.json")
    ap.add_argument("--out", default="review")
    ap.add_argument("--every", type=float, default=3.0)
    ap.add_argument("--strips", type=float, nargs="*", default=[])
    ap.add_argument("--crop", type=int, nargs=2, default=[300, 1500],
                    help="top and bottom of the strip crop, in source pixels")
    ap.add_argument("--triptychs", type=float, nargs="*", default=[],
                    help="explicit times; default is one per timeline beat")
    args = ap.parse_args()

    for sub in ("frames", "motion", "strips"):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
    tmp = os.path.join(args.out, "_tmp.png")
    duration = probe_duration(args.src)
    frame_px = None

    # 1. the whole film
    t, frames = 1.0, 0
    while t < duration - 0.5:
        image = grab(args.src, t, tmp)
        frame_px = image.size[0] * image.size[1]
        image.save(os.path.join(args.out, "frames", f"f_{t:05.1f}s.png"))
        frames += 1
        t += args.every

    # 2. triptychs — one per beat unless explicit times were given
    marks = list(args.triptychs)
    if not marks and os.path.exists(args.timeline):
        beats = json.load(open(args.timeline, encoding="utf-8"))["beats"]
        marks = [b["start"] + (b["end"] - b["start"]) * 0.55 for b in beats]
    rows = []
    for at in marks:
        a = grab(args.src, at, tmp)
        b = grab(args.src, at + 0.4, tmp)
        diff, count = changed(a, b)
        amp = np.clip(diff * AMPLIFY, 0, 255).astype(np.uint8)
        panel = Image.new("RGB", (a.size[0] * 3 + 40, a.size[1]), (24, 24, 24))
        panel.paste(a, (0, 0))
        panel.paste(b, (a.size[0] + 20, 0))
        panel.paste(Image.fromarray(np.stack([amp] * 3, axis=2)), (a.size[0] * 2 + 40, 0))
        panel.resize((1400, int(1400 * a.size[1] / panel.size[0])), Image.LANCZOS).save(
            os.path.join(args.out, "motion", f"t_{at:05.2f}s_{count:07d}px.png"))
        rows.append({"t": round(at, 2), "changed_px": count,
                     "pct": round(100 * count / frame_px, 2) if frame_px else None})

    # 3. strips — 6 frames at 8 fps, cropped and tiled, so easing and weight are visible
    top, bottom = args.crop
    for at in args.strips:
        cells = [grab(args.src, at + i / 8, tmp) for i in range(6)]
        cell = cells[0].crop((0, top, cells[0].size[0], bottom))
        thumb = cell.resize((300, int(300 * cell.size[1] / cell.size[0])), Image.LANCZOS)
        strip = Image.new("RGB", (thumb.size[0] * 6 + 30, thumb.size[1]), (24, 24, 24))
        for i, image in enumerate(cells):
            piece = image.crop((0, top, image.size[0], bottom))
            strip.paste(piece.resize(thumb.size, Image.LANCZOS), (i * (thumb.size[0] + 6), 0))
        _, count = changed(cells[0], cells[-1])
        strip.save(os.path.join(args.out, "strips", f"s_{at:05.1f}s_{count:07d}px.png"))

    with open(os.path.join(args.out, "measured.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": args.src, "duration": duration, "frame_px": frame_px,
                   "threshold": CHANGE_THRESHOLD, "triptychs": rows}, fh, indent=1)

    os.path.exists(tmp) and os.remove(tmp)
    print(f"{frames} frames, {len(rows)} triptychs, {len(args.strips)} strips -> {args.out}")
    for row in rows:
        print(f"  t={row['t']:6.2f}s  {row['changed_px']:7d} px  {row['pct']:5.2f}% of frame")


if __name__ == "__main__":
    main()
