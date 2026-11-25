#!/usr/bin/env python3
"""Stamp "by Alucard0x1" onto a finished film without re-encoding the picture twice.

The mark is drawn from ffmpeg's drawtext filter, inside the same encode that produces the delivery copy, so a
film never gets a second generation of compression just for a credit. It sits bottom-right, white at 62% with a
dark shadow, small enough to survive a phone screen without becoming furniture.

    python add_watermark.py in.mp4 out.mp4 [--text "by Alucard0x1"] [--crf 24]
"""
import argparse
import os
import shutil
import subprocess
import sys

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def pick_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--text", default="by Alucard0x1")
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--size", type=int, default=22)
    parser.add_argument("--margin", type=int, default=26)
    args = parser.parse_args()

    font = pick_font()
    if not font:
        sys.exit("no usable font found")

    # ffmpeg on Windows needs the drive colon escaped inside the filter graph
    font_arg = font.replace(":", "\\:")
    # a space in the text has to be surviving single quotes inside the filter string
    draw = (
        f"drawtext=fontfile='{font_arg}'"
        f":text='{args.text}'"
        f":fontsize={args.size}"
        f":fontcolor=white@0.46"
        f":shadowcolor=black@0.60:shadowx=1:shadowy=1"
        f":x=w-tw-{args.margin}:y=h-th-{args.margin}"
    )

    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", args.source,
        "-vf", draw,
        "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart",
        args.target,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(result.stderr.decode("utf-8", "replace")[-800:])
        sys.exit(f"ffmpeg failed ({result.returncode})")

    size = os.path.getsize(args.target) / 1048576
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", args.target], capture_output=True)
    print(f"ok {args.target}  {size:.1f} MB  {probe.stdout.decode().strip()}s  mark={args.text!r}")


if __name__ == "__main__":
    main()
