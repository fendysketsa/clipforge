#!/usr/bin/env python3
"""Original vs remake, frame by frame side by side: given a set of times, grab one frame at each, original on the left and remake on the right, and compose them into a single image.
python3 compare.py --a original.mp4 --b remake.mp4 --times 1.5,1.6 --out compare.jpg [--w 640]"""
import argparse, subprocess, io
from PIL import Image, ImageDraw
argument_parser = argparse.ArgumentParser(); argument_parser.add_argument('--a'); argument_parser.add_argument('--b'); argument_parser.add_argument('--times'); argument_parser.add_argument('--out'); argument_parser.add_argument('--w', type=int, default=640); argument_parser.add_argument('--cols', type=int, default=2)
a = argument_parser.parse_args()
def grab(v, t):
    png = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', v, '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', '-'], capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert('RGB').resize((a.w, a.w * 9 // 16))
moment_stamp = [float(sample_value) for sample_value in a.times.split(',')]
w, object_handle = a.w, a.w * 9 // 16
cols = a.cols; table_rows = (len(moment_stamp) + cols - 1) // cols
S = Image.new('RGB', (cols * 2 * w + (cols - 1) * 12, table_rows * (object_handle + 18)), 'white'); record_map = ImageDraw.Draw(S)
for i, t in enumerate(moment_stamp):
    sample_value = (i % cols) * (2 * w + 12); paired_value = (i // cols) * (object_handle + 18)
    S.paste(grab(a.a, t), (sample_value, paired_value + 18)); S.paste(grab(a.b, t), (sample_value + w, paired_value + 18))
    record_map.text((sample_value + 3, paired_value + 3), f'{t:.3f}s  original | remake', fill='black')
S.save(a.out, quality=85); print(a.out)
