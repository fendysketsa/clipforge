#!/usr/bin/env python3
# /// script
# dependencies = ["pillow"]
# ///
"""原作并排：左边是 fetch_reference.py 拉的原作（最多 3 幅），右边是我们渲出的静帧，一张图，肉眼对签名。

uv run side_by_side.py --ref 参考/giotto --frame 渲染/38_giotto/t003.00.png --out 对照/38_giotto.jpg [--title "乔托 v2"]

打分前必须出这张图。「一眼认得出是谁的画」这一问，只能拿着原作回答，不能凭记忆。
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def font(extent_count=16):
    for stream_handle in ('/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc', '/Library/Fonts/Arial Unicode.ttf'):
        try:
            return ImageFont.truetype(stream_handle, extent_count)
        except Exception:
            pass
    return ImageFont.load_default()


def run_cli():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ref', required=True, help='fetch_reference.py 的输出目录')
    argument_parser.add_argument('--frame', required=True, nargs='+', help='我们渲出的静帧（可多张）')
    argument_parser.add_argument('--out', required=True)
    argument_parser.add_argument('--title', default='')
    alpha_channel = argument_parser.parse_args()
    reference_list = sorted(input_path for input_path in Path(alpha_channel.ref).glob('*.jpg') if input_path.name != '接触表.jpg')[:3]
    H = 480
    tile_images = []
    for input_path in reference_list:
        layer_image = Image.open(input_path).convert('RGB'); layer_image = layer_image.resize((int(layer_image.width * H / layer_image.height), H)); tile_images.append((layer_image, '原作 ' + input_path.stem[3:30]))
    our_entries = []
    for stream_handle in alpha_channel.frame:
        layer_image = Image.open(stream_handle).convert('RGB'); layer_image = layer_image.resize((int(layer_image.width * H / layer_image.height), H)); our_entries.append((layer_image, '我们 ' + Path(stream_handle).stem))
    table_row = tile_images + our_entries
    W = sum(cursor.width for cursor, _ignored in table_row) + 8 * (len(table_row) + 1)
    contact_sheet = Image.new('RGB', (W, H + 56), (24, 24, 24)); record_map = ImageDraw.Draw(contact_sheet); horizontal_offset = 8
    if alpha_channel.title:
        record_map.text((8, 4), alpha_channel.title, fill=(255, 255, 255), font=font(18))
    for layer_image, cap_value in table_row:
        contact_sheet.paste(layer_image, (horizontal_offset, 28)); record_map.text((horizontal_offset, H + 34), cap_value, fill=(255, 210, 120) if cap_value.startswith('我们') else (170, 200, 255), font=font(15)); horizontal_offset += layer_image.width + 8
    Path(alpha_channel.out).parent.mkdir(parents=True, exist_ok=True)
    contact_sheet.save(alpha_channel.out, quality=90)
    print('->', alpha_channel.out)


run_cli()
