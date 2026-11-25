#!/usr/bin/env python3
"""Subtitle-band gate: scan the "no-subtitles" master; when picture content (glyphs, outlines, rockets, flames)
shows up inside the subtitle band, report the timecodes.

    python3 subzone_gate.py <nosub-master.mp4> [--band 920] [--fps 10] [--thresh 150]

qa.py checks text boxes; this script adds a check for whether graphics drift into the subtitle band.
It counts dark pixels with gray level < 95, so it only suits clean styles on a light background (whiteboard,
off-white paper, light-coloured keynote stage). On textured backgrounds (the Vox kraft-paper desk) judging by
the band's dominant colour produces a pile of false positives: for those styles lean on qa.py's framing hints,
or — as the Vox version does — have the text API register which object each label belongs to and query the
occlusion instead.
The threshold is the value measured on that one film (> 150 pixels once the band is halved to 960×80).
Before switching styles, calibrate on a known-good and a known-bad frame.
"""
import argparse, subprocess, numpy as np
argument_parser = argparse.ArgumentParser(); argument_parser.add_argument('video'); argument_parser.add_argument('--band', type=int, default=920, help='top edge y of the subtitle band (on a 1080-high frame)')
argument_parser.add_argument('--fps', type=float, default=10); argument_parser.add_argument('--thresh', type=int, default=150)
a = argument_parser.parse_args()
h = 1080 - a.band; W, H = 960, h // 2
subcommand_name = ['ffmpeg', '-v', 'error', '-i', a.video, '-vf', f'fps={a.fps},scale=1920:1080,crop=1920:{h}:0:{a.band},scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
raw_payload = subprocess.run(subcommand_name, capture_output=True, check=True).stdout
fr = np.frombuffer(raw_payload, np.uint8).reshape(-1, H, W)
bad = []
for i, f in enumerate(fr):
    n = int((f < 95).sum())
    if n > a.thresh: bad.append((i / a.fps, n))
run_records = []
for elapsed_seconds, n in bad:
    if run_records and elapsed_seconds - run_records[-1][1] <= 1.5 / a.fps: run_records[-1][1] = elapsed_seconds; run_records[-1][2] = max(run_records[-1][2], n)
    else: run_records.append([elapsed_seconds, elapsed_seconds, n])
print(f'{len(fr)} frames, {len(bad)} hits')
for t0, t1, n in run_records: print(f'  {t0:7.2f}–{t1:7.2f}s  up to {n} pixels')
