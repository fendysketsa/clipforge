#!/usr/bin/env python3
# /// script
# dependencies = ["pillow"]
# ///
"""原作锚定：从维基共享资源按关键词拉公版原作，存本地，并抽主色板、出接触表。

做新风格演示前先跑它：看原作、记签名特征、拿真实色值，不凭印象画「受启发的扁平插画」。

uv run fetch_reference.py --out 参考/ostia "Giotto Lamentation Scrovegni" "Giotto Meeting at the Golden Gate" [--n 1] [--colors 8]

每个查询取前 n 张（默认 1）宽 1600 的缩略图，存为 <out>/<序号>_<标题>.jpg，
同时写 <out>/参考.md（来源 URL、主色 hex）和 <out>/接触表.jpg。
只用公版作品（作者卒年 70 年以上的原作翻拍）；脚本不判断版权，调用者自己确认。
拉完必须看接触表，核对三件事：①是不是这位画家的作品（搜索会混入地图、现代照片、博物馆墙上的翻拍）②是不是三幅不同的作品（脚本只去掉近似图）③哪些是带框的翻拍（色板已取中央 80%，但构图判断仍要自己看）。
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

UA = {'User-Agent': 'art-motion-research/1.0 (https://github.com/alchaincyf/huashu-art-motion)'}


def get(url, timeout=60, attempt_count=4):
    # 维基共享资源偶尔 SSL EOF：重试几次再报错
    for sort_key in range(attempt_count):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as caught_error:
            if sort_key == attempt_count - 1:
                raise
            time.sleep(1.5 * (sort_key + 1))


def api(**extra_options):
    return json.loads(get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({**extra_options, 'format': 'json'})))


def search(q, n):
    d = api(action='query', generator='search', gsrsearch=f'{q} filetype:bitmap', gsrnamespace=6, gsrlimit=n + 4,
            prop='imageinfo', iiprop='url|size', iiurlwidth=1600)
    pages = sorted(d.get('query', {}).get('pages', {}).values(), key=lambda input_path: input_path.get('index', 0))
    out = []
    for input_path in pages:
        ii_value = (input_path.get('imageinfo') or [{}])[0]
        if ii_value.get('thumburl') and ii_value.get('width', 0) >= 900:
            out.append((input_path['title'].removeprefix('File:'), ii_value['thumburl'], ii_value.get('descriptionurl', '')))
        if len(out) >= n:
            break
    return out


def palette(im, sort_key):
    w, object_handle = im.size; im = im.crop((int(w * .1), int(object_handle * .1), int(w * .9), int(object_handle * .9)))   # 去掉画框、墙、页边：只在中央 80% 里抽色
    q = im.convert('RGB').resize((200, 200)).quantize(colors=sort_key, method=Image.Quantize.MEDIANCUT)
    pal_value = q.getpalette()[:sort_key * 3]
    counter_value = sorted(q.getcolors(), reverse=True)
    return ['#%02x%02x%02x' % tuple(pal_value[cursor * 3:cursor * 3 + 3]) + f' {c / 400:.0f}%' for c, cursor in counter_value]


def perform_ahash(im):
    from PIL import ImageOps
    green_channel = ImageOps.autocontrast(im.convert('L').resize((16, 16)), cutoff=2)       # 先拉对比：调色增强版和原图才会落到同一个哈希附近
    px_value = list(green_channel.tobytes()); matched_object = sum(px_value) / 256
    return sum((1 << cursor) for cursor, current_value in enumerate(px_value) if current_value > matched_object)


def run_cli():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('queries', nargs='+')
    argument_parser.add_argument('--out', required=True)
    argument_parser.add_argument('--n', type=int, default=1)
    argument_parser.add_argument('--colors', type=int, default=8)
    a = argument_parser.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows, md, visited_keys = [], ['# 原作参考\n'], []
    for q in a.queries:
        hit_entries = search(q, a.n)
        if not hit_entries:
            print(f'!! 没搜到：{q}', file=sys.stderr); continue
        for title, url, page in hit_entries:
            fn = out / (f'{len(rows) + 1:02d}_' + re.sub(r'[^\w]+', '_', title)[:50] + '.jpg')
            fn.write_bytes(get(url, 90))
            im = Image.open(fn)
            hv_value = perform_ahash(im)
            if any(bin(hv_value ^ h2_value).count('1') <= 40 for h2_value in visited_keys):                      # 同一幅的另一个翻拍/调色版：丢掉，不凑数
                fn.unlink(); print('dup  ', title, '（与已取的某幅近似，已丢弃）'); continue
            visited_keys.append(hv_value)
            rows.append((fn, im.copy()))
            md.append(f'- {fn.name}\n  - 来源：{page}\n  - 主色：{"、".join(palette(im, a.colors))}')
            print('ok', fn.name)
    if rows:
        W, H, column_values = 640, 400, 3
        contact_sheet = Image.new('RGB', (W * column_values, H * ((len(rows) + column_values - 1) // column_values)), 'white')
        for cursor, (fn, im) in enumerate(rows):
            elapsed_seconds = im.convert('RGB'); elapsed_seconds.thumbnail((W, H))
            contact_sheet.paste(elapsed_seconds, ((cursor % column_values) * W, (cursor // column_values) * H))
            ImageDraw.Draw(contact_sheet).text(((cursor % column_values) * W + 6, (cursor // column_values) * H + 6), fn.stem[:40], fill=(255, 0, 0))
        contact_sheet.save(out / '接触表.jpg', quality=88)
    (out / '参考.md').write_text('\n'.join(md) + '\n')


run_cli()
