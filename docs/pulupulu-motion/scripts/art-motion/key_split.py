#!/usr/bin/env python3
"""绿幕抠图＋按列空隙切成单个姿势：python3 key_split.py 图.png --out 前缀 [--pick 0]（只要第几个）"""
import argparse
import numpy as np
from PIL import Image
argument_parser = argparse.ArgumentParser(); argument_parser.add_argument('src'); argument_parser.add_argument('--out', required=True); argument_parser.add_argument('--pick', type=int); argument_parser.add_argument('--white', action='store_true', help='白底线稿：不抠，只裁')
a = argument_parser.parse_args()
layer_image = np.asarray(Image.open(a.src).convert('RGB')).astype(np.float32); red_channel, green_channel, blue_channel = layer_image[..., 0], layer_image[..., 1], layer_image[..., 2]
if a.white:
    opacity_value = 1 - np.clip((np.minimum(np.minimum(red_channel, green_channel), blue_channel) - 225) / 25, 0, 1); opacity_value = np.maximum(opacity_value, (np.max(layer_image, 2) - np.min(layer_image, 2) > 40))
    channel_values = np.dstack([red_channel, green_channel, blue_channel, np.full_like(red_channel, 255)])
    mask_array = opacity_value > 0.1
else:
    spill_amount = green_channel - np.maximum(red_channel, blue_channel); alpha_channel = 1 - np.clip((spill_amount - 30) / 70, 0, 1)
    green_channel_copy = np.where(spill_amount > 0, np.minimum(green_channel, np.maximum(red_channel, blue_channel) + 0.25 * np.clip(spill_amount, 0, 30)), green_channel)
    channel_values = np.dstack([red_channel, green_channel_copy, blue_channel, alpha_channel * 255]); mask_array = alpha_channel > 0.05
column_values = mask_array.any(0); run_records = []; sample_value = 0; W = len(column_values)
while sample_value < W:
    if column_values[sample_value]:
        left_edge = sample_value
        while sample_value < W and column_values[sample_value: sample_value + 12].any(): sample_value += 1
        if sample_value - left_edge > 40: run_records.append((left_edge, sample_value))
    sample_value += 1
for k, (left_edge, right_edge) in enumerate(run_records):
    if a.pick is not None and k != a.pick: continue
    table_rows = mask_array[:, left_edge:right_edge].any(1); y_samples = np.where(table_rows)[0]; top_edge, bottom_edge = y_samples.min(), y_samples.max() + 1
    out = channel_values[top_edge:bottom_edge, left_edge:right_edge].clip(0, 255).astype(np.uint8)
    Image.fromarray(out, 'RGBA' if out.shape[2] == 4 else 'RGB').save(f'{a.out}{"" if a.pick is not None else "_" + str(k)}.png'); print(k, left_edge, right_edge, top_edge, bottom_edge)
