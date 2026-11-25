#!/usr/bin/env python3
"""Composite a portrait and its licence credit onto a film's end card.

A photograph of a real person carries an obligation: the licence that makes the use lawful is the attribution,
so the credit line is part of the filter, not an afterthought. The portrait is masked to a circle with a thin
ring in the film's cream so it reads as a designed card rather than a pasted rectangle, and it only appears for
the last seconds of the film, where the brief reserved space for it.

    python add_creator_card.py in.mp4 out.mp4 portrait.jpg --at 0.90 --x 540 --y 1450 --size 380
"""
import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw

RING = (246, 239, 221)


def esc(text):
    """A colon separates options inside a filter graph, so any colon in display text must be escaped, along
    with the backslash, quote and percent that drawtext also treats specially."""
    return (text.replace("\\", "\\\\").replace(":", "\:")
                .replace("'", "\'").replace("%", "\%"))


def circle_portrait(source, size, ring=8):
    """Circle-masked portrait with a soft ring; returns a path to the prepared PNG."""
    image = Image.open(source).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    image.putalpha(mask)
    canvas = Image.new("RGBA", (size + ring * 2, size + ring * 2), (0, 0, 0, 0))
    ring_mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(ring_mask).ellipse((0, 0, canvas.size[0] - 1, canvas.size[1] - 1), fill=255)
    ring_layer = Image.new("RGBA", canvas.size, RING + (255,))
    canvas.paste(ring_layer, (0, 0), ring_mask)
    canvas.paste(image, (ring, ring), image)
    out = os.path.join(os.path.dirname(os.path.abspath(source)), "_portrait_circle.png")
    canvas.save(out)
    return out, canvas.size[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("portrait")
    parser.add_argument("--at", type=float, default=0.90, help="fraction of the film where the card appears")
    parser.add_argument("--x", type=int, default=540, help="centre x")
    parser.add_argument("--y", type=int, default=1450, help="centre y")
    parser.add_argument("--size", type=int, default=380)
    parser.add_argument("--tx", type=int, default=None, help="centre x for the text (defaults to --x)")
    parser.add_argument("--name", default="Taylor Otwell")
    parser.add_argument("--role", default="creator of Laravel")
    parser.add_argument("--credit", default="Photo: Bill Condo - CC BY 2.0")
    parser.add_argument("--dark", action="store_true", help="credit in ink instead of cream")
    parser.add_argument("--crf", type=int, default=24)
    args = parser.parse_args()

    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                     "-of", "default=nw=1:nk=1", args.source],
                                    capture_output=True).stdout.decode().strip())
    start = max(0.0, duration * args.at)

    prepared, box = circle_portrait(args.portrait, args.size)
    left, top = int(args.x - box / 2), int(args.y - box / 2)
    colour = "0x14120f" if args.dark else "0xf6efdd"
    shadow = "0xf6efdd@0.55" if args.dark else "black@0.55"

    tx = args.tx if args.tx is not None else args.x
    filters = [
        f"[1:v]format=rgba[card]",
        f"[0:v][card]overlay={left}:{top}:enable='gte(t,{start:.2f})'[base]",
        (f"[base]drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{esc(args.name)}'"
         f":fontsize=44:fontcolor={colour}:shadowcolor={shadow}:shadowx=2:shadowy=2"
         f":x={tx - 240}:y={top + box + 40}:enable='gte(t,{start:.2f})'[n1]"),
        (f"[n1]drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{esc(args.role)}'"
         f":fontsize=32:fontcolor={colour}:shadowcolor={shadow}:shadowx=2:shadowy=2"
         f":x={tx - 190}:y={top + box + 100}:enable='gte(t,{start:.2f})'[n2]"),
        (f"[n2]drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{esc(args.credit)}'"
         f":fontsize=20:fontcolor={colour}@0.6:x={tx - 150}:y={top + box + 152}"
         f":enable='gte(t,{start:.2f})'[out]"),
    ]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", args.source, "-i", prepared,
           "-filter_complex", ";".join(filters), "-map", "[out]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", args.target]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(result.stderr.decode("utf-8", "replace")[-900:])
        sys.exit(f"ffmpeg failed ({result.returncode})")
    print(f"ok {args.target}  card from {start:.1f}s  portrait {box}px at ({args.x},{args.y})")


if __name__ == "__main__":
    main()
