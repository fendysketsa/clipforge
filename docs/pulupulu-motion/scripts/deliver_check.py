#!/usr/bin/env python3
"""Validate the file that is about to be delivered, not the renderer's latest output.

The renderer writes whatever the page says; the mux decides what the audience actually gets. Every error
this catches has shipped in a real film: a landscape render delivered as a Short, a file whose audio came
from the previous mix, a video that outran its narration, and a 70 MB master that a chat client refused.

    python scripts/deliver_check.py out/film.mp4
    python scripts/deliver_check.py out/film.mp4 --timeline timeline.json --max-mb 50
    python scripts/deliver_check.py out/film.mp4 --size 1080x1920 --fps 30 --json

Exit 1 = at least one hard check failed. Warnings never change the exit code.
"""

import argparse
import json
import os
import re
import subprocess
import sys


def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                          "-show_format", "-show_streams", path],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit(f"ffprobe failed on {path}: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def loudness(path):
    """EBU R128 integrated loudness and true peak, read from ffmpeg's own meter."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                          "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=600)
    text = out.stderr
    integrated = re.findall(r"I:\s*(-?\d+\.\d+) LUFS", text)
    peak = re.findall(r"True peak:\s*Peak:\s*(-?\d+\.\d+) dBFS", text)
    return (float(integrated[-1]) if integrated else None, float(peak[-1]) if peak else None)


def first_sound(path, threshold="-45dB"):
    """Seconds of silence before the first audible sample: a film that opens dead was mixed wrong."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                          f"silencedetect=n={threshold}:d=0.2", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=600)
    starts = [float(value) for value in re.findall(r"silence_end:\s*([\d.]+)", out.stderr)]
    return starts[0] if starts else None


def check(path, size, fps, timeline, max_mb, lufs_range, peak_max):
    hard, warn = [], []
    if not os.path.exists(path):
        return ["file does not exist"], []

    info = ffprobe(path)
    video = [s for s in info["streams"] if s.get("codec_type") == "video"]
    audio = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    duration = float(info["format"].get("duration", 0))
    megabytes = int(info["format"].get("size", 0)) / (1024 ** 2)

    if not video:
        hard.append("no video stream")
    else:
        v = video[0]
        want_w, want_h = (int(part) for part in size.lower().split("x"))
        if (v.get("width"), v.get("height")) != (want_w, want_h):
            hard.append(f"frame is {v.get('width')}x{v.get('height')}, must be {want_w}x{want_h}")
        if v.get("pix_fmt") != "yuv420p":
            warn.append(f"pix_fmt {v.get('pix_fmt')} — yuv420p plays everywhere")
        if v.get("codec_name") != "h264":
            warn.append(f"video codec {v.get('codec_name')} — h264 plays everywhere")
        rate = v.get("avg_frame_rate", "0/1")
        if rate not in (f"{fps}/1", str(fps)):
            numerator, _, denominator = rate.partition("/")
            got = float(numerator) / float(denominator or 1)
            (hard if abs(got - fps) > 0.5 else warn).append(f"frame rate {got:.2f}, target {fps}")

    if not audio:
        hard.append("no audio stream — the mux dropped the narration")
    else:
        a = audio[0]
        if a.get("codec_name") not in ("aac", "mp3"):
            warn.append(f"audio codec {a.get('codec_name')} — aac is the safe default")
        if duration and float(a.get("duration", duration)) < duration - 0.35:
            hard.append(f"audio ends at {float(a.get('duration')):.2f}s but picture runs {duration:.2f}s")

    if timeline:
        if not os.path.exists(timeline):
            hard.append(f"timeline not found: {timeline}")
        else:
            expected = json.load(open(timeline, encoding="utf-8")).get("duration")
            if expected:
                drift = abs(duration - float(expected))
                (hard if drift > 0.6 else warn).append(
                    f"duration {duration:.2f}s vs timeline {float(expected):.2f}s (drift {drift:.2f}s)")

    integrated, peak = loudness(path)
    if integrated is None:
        warn.append("loudness could not be measured")
    else:
        if not lufs_range[0] <= integrated <= lufs_range[1]:
            warn.append(f"integrated loudness {integrated} LUFS outside {lufs_range[0]}..{lufs_range[1]}")
        if peak is not None and peak > peak_max:
            hard.append(f"true peak {peak} dBFS exceeds {peak_max} dBFS — it will clip on phone speakers")

    opening = first_sound(path)
    if opening is not None and opening > 0.9:
        warn.append(f"{opening:.2f}s of silence before the first sound")

    if megabytes > max_mb:
        warn.append(f"{megabytes:.1f} MB exceeds the {max_mb} MB delivery cap — re-encode with crf 23")

    return hard, warn


def mux(video, audio, out, crf=23):
    """The one delivery command: explicit mapping, or the narrator disappears.

    `pulupulu render` already embeds the score, so a bare `-i render -i mix` picks the render's own
    music-only stream and silently drops the narration while every level check still looks healthy.
    """
    command = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", audio,
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    done = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if done.returncode != 0:
        raise SystemExit(f"mux failed: {done.stderr.strip()[:400]}")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", help="the mapped MP4 that will be delivered")
    parser.add_argument("--size", default="1080x1920")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--timeline", help="timeline.json written by deepseek_voice.py beats")
    parser.add_argument("--max-mb", type=float, default=50)
    parser.add_argument("--lufs", default="-18,-12", help="acceptable integrated loudness range")
    parser.add_argument("--peak-max", type=float, default=-1.0)
    parser.add_argument("--video", help="renderer output to mux (with --audio and --out)")
    parser.add_argument("--audio", help="the mix wav to mux in")
    parser.add_argument("--out", help="destination of the muxed, deliverable file")
    parser.add_argument("--crf", type=int, default=23)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.video and args.audio and args.out:
        mux(args.video, args.audio, args.out, args.crf)
        args.target = args.out
    if not args.target:
        parser.error("give a file to validate, or --video/--audio/--out to mux one")

    low, high = (float(part) for part in args.lufs.split(","))
    hard, warn = check(args.target, args.size, args.fps, args.timeline, args.max_mb, (low, high), args.peak_max)

    if args.json:
        print(json.dumps({"target": args.target, "ok": not hard, "failed": hard, "warnings": warn}, indent=1))
    else:
        for line in hard:
            print(f"  FAIL {line}")
        for line in warn:
            print(f"  warn {line}")
        print()
        print("deliverable is good" if not hard else f"{len(hard)} hard failure(s) — do not deliver")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
