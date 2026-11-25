#!/usr/bin/env python3
# /// script
# dependencies = ["pillow"]
# ///
"""动画语法通用性压力测试：同一份 spec 生成 竖屏／超长文字／英文／方屏 四个变体，各渲「全部 cue 都出现后」的一帧，拼成一张检查表。

uv run scripts/analyze/stress_clip.py scripts/engine/examples/y5_kinetic_type.json --out <目录> [--variants portrait,long,en,square] [--at 0.95]

看什么（每个变体对着原版问一遍）：
  long      文字溢出画面／被裁／缩到看不清／叠到别的元素上？超长应当换行或缩放到下限，仍可读，不许溢出
  en        拉丁文字比例不同：字重、断行、字距还对不对？
  portrait  版面是不是为窄高画布重排了（竖排堆叠、放大），而不是把 16:9 版面缩进窄画布？内容不许被裁
  square    1:1，同上
出表后人工逐格看；有问题的变体回到语法文件里修，别只修 spec。
"""
import argparse, copy, json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

LONG = " ——这是一段刻意加长的说明文字，用来测试自动换行、缩放与避让是不是稳定"
TEXT_KEYS = ("text", "sub", "label", "title", "caption", "word", "key")


def font(extent_count=16):
    for f in ('/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/Library/Fonts/Arial Unicode.ttf'):
        try:
            return ImageFont.truetype(f, extent_count)
        except Exception:
            pass
    return ImageFont.load_default()


def resolve_to_absolute(item_object, base: Path):
    if isinstance(item_object, dict):
        return {sort_key: resolve_to_absolute(v, base) for sort_key, v in item_object.items()}
    if isinstance(item_object, list):
        return [resolve_to_absolute(v, base) for v in item_object]
    if isinstance(item_object, str) and not item_object.startswith(('/', 'data:', 'http')) and (base / item_object).exists() and '.' in item_object.split('/')[-1]:
        return str((base / item_object).resolve())
    return item_object


def perform_map_text(item_object, fn_value, key=None):
    if isinstance(item_object, dict):
        return {sort_key: perform_map_text(v, fn_value, sort_key) for sort_key, v in item_object.items()}
    if isinstance(item_object, list):
        return [perform_map_text(v, fn_value, key) for v in item_object]
    if isinstance(item_object, str) and key in TEXT_KEYS and key != 'word':
        return fn_value(item_object)
    return item_object


EN_POOL = ["Gradient descent walks downhill", "One sentence turns into three thousand lines", "Revenue grew 7.8x in five years",
           "Two charts, both drawn by code", "Only one thing at a time", "A single drop holds billions of organisms"]


def perform_en_fn():
    cursor = [0]

    def f(s):
        cursor[0] += 1
        return EN_POOL[cursor[0] % len(EN_POOL)] if len(s) > 4 else "OK " + str(cursor[0])
    return f


def run_cli():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('spec'); argument_parser.add_argument('--out', required=True)
    argument_parser.add_argument('--variants', default='portrait,long,en,square'); argument_parser.add_argument('--at', type=float, default=0.95, help='取时长的这个比例处那一帧（默认 0.95＝cue 基本都出现）')
    a = argument_parser.parse_args()
    sp = Path(a.spec).resolve(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    eng_value = Path(__file__).resolve().parents[1] / 'engine'
    base = resolve_to_absolute(json.loads(sp.read_text()), sp.parent)
    span_seconds = base['duration']; t = round(span_seconds * a.at, 2)
    version_records = {'base': base}
    for v in a.variants.split(','):
        record_map = copy.deepcopy(base)
        if v == 'portrait': record_map['width'], record_map['height'] = 1080, 1920
        elif v == 'square': record_map['width'], record_map['height'] = 1080, 1080
        elif v == 'long': record_map = perform_map_text(record_map, lambda s: s + LONG)
        elif v == 'en': record_map = perform_map_text(record_map, perform_en_fn())
        else: sys.exit(f'未知变体 {v}')
        version_records[v] = record_map
    tile_images = []
    for name, record_map in version_records.items():
        f = out / f'{name}.json'; f.write_text(json.dumps(record_map, ensure_ascii=False))
        red_channel = subprocess.run(['uv', 'run', '--with', 'playwright', 'python', str(eng_value / 'render.py'), '--spec', str(f), '--stills', str(t), '--out', str(out / name)], capture_output=True, text=True)
        png_entries = sorted((out / name).glob('*.png'))
        if not png_entries:
            print(f'[{name}] 渲染失败：', (red_channel.stdout + red_channel.stderr).strip().splitlines()[-1:]); tile_images.append((name, None)); continue
        tile_images.append((name, Image.open(png_entries[-1]).convert('RGB')))
    H = 420; table_row = []
    for name, layer_image in tile_images:
        layer_image = layer_image.resize((int(layer_image.width * H / layer_image.height), H)) if layer_image else Image.new('RGB', (300, H), (110, 0, 0)); table_row.append((name, layer_image))
    W = sum(cursor.width for _ignored, cursor in table_row) + 8 * (len(table_row) + 1)
    sh_value = Image.new('RGB', (W, H + 30), (24, 24, 24)); dr_value = ImageDraw.Draw(sh_value); x = 8
    for name, layer_image in table_row:
        sh_value.paste(layer_image, (x, 26)); dr_value.text((x, 4), f'{sp.stem} · {name} @ {t}s', fill=(255, 220, 90), font=font(15)); x += layer_image.width + 8
    item_object = out / '检查表.jpg'; sh_value.save(item_object, quality=88); print('->', item_object)


run_cli()
