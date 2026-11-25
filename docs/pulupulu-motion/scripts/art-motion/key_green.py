#!/usr/bin/env python3
"""绿幕抠图且保留原画面坐标：输出裁到主体的 RGBA png ＋ sprites.json 里记下它在 1920x1080 画面中的左上角。
gpt-image 用原片帧当参考图、只画角色铺 #00FF00 时，角色已经站在原片坐标上——裁剪时丢掉坐标就白对齐了。
用法：python3 key_green.py raw/*.png --out ../工程/sprites [--soft 40 --hard 110]"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image
argument_parser = argparse.ArgumentParser(); argument_parser.add_argument('files', nargs='+'); argument_parser.add_argument('--out', required=True)
argument_parser.add_argument('--soft', type=float, default=30); argument_parser.add_argument('--hard', type=float, default=100); argument_parser.add_argument('--pad', type=int, default=4)
alpha_channel = argument_parser.parse_args()
out = Path(alpha_channel.out); out.mkdir(parents=True, exist_ok=True)
meta_p_value = out / 'sprites.json'; metadata_map = json.loads(meta_p_value.read_text()) if meta_p_value.exists() else {}
for f in alpha_channel.files:
    layer_image = np.asarray(Image.open(f).convert('RGB')).astype(np.float32)
    red_channel, green_channel, blue_channel = layer_image[..., 0], layer_image[..., 1], layer_image[..., 2]
    spill_amount = green_channel - np.maximum(red_channel, blue_channel)                      # 绿色占优程度
    opacity_value = 1 - np.clip((spill_amount - alpha_channel.soft) / (alpha_channel.hard - alpha_channel.soft), 0, 1)
    # 去绿溢：半透明及边缘像素的绿通道压到 max(r,b)
    green_channel_copy = np.where(spill_amount > 0, np.minimum(green_channel, np.maximum(red_channel, blue_channel) + 0.25 * np.clip(spill_amount, 0, 30)), green_channel)
    channel_values = np.dstack([red_channel, green_channel_copy, blue_channel, opacity_value * 255]).clip(0, 255).astype(np.uint8)
    y_samples, x_samples = np.where(opacity_value > 0.05)
    if len(x_samples) == 0: print('empty', f); continue
    left_edge, top_edge = max(0, x_samples.min() - alpha_channel.pad), max(0, y_samples.min() - alpha_channel.pad)
    right_edge, bottom_edge = min(layer_image.shape[1], x_samples.max() + alpha_channel.pad + 1), min(layer_image.shape[0], y_samples.max() + alpha_channel.pad + 1)
    name = Path(f).stem
    Image.fromarray(channel_values[top_edge:bottom_edge, left_edge:right_edge]).save(out / f'{name}.png')
    metadata_map[name] = {'x': int(left_edge), 'y': int(top_edge), 'w': int(right_edge - left_edge), 'h': int(bottom_edge - top_edge)}
    print(name, metadata_map[name])
meta_p_value.write_text(json.dumps(metadata_map, indent=1))
