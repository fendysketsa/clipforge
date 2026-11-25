#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""动画语法回归：对 engine/examples/*.json 逐个跑 spec 校验＋版面审计（原版／竖屏／英文），出一张通过表。改了任何语法、库或引擎之后先跑这个。

uv run scripts/analyze/regress_clips.py [--only y1_kurzgesagt,t3_finance_chart] [--variants base,portrait,en] [--out <目录>]
红灯＝版面审计红灯或 spec 校验红灯，退出码 1；黄灯只列出。需要素材才能渲的示例（y4 要角色帧库）自动跳过并说明。
"""
import argparse, copy, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; ENG = ROOT / 'engine'
EN = ["Gradient descent walks downhill", "One sentence turns into three thousand lines", "Revenue grew 7.8x in five years", "Two charts, both drawn by code", "Only one thing at a time"]
TK = ("text", "sub", "label", "title", "caption", "key")


def resolve_to_absolute(item_object, base: Path):
    if isinstance(item_object, dict): return {sort_key: resolve_to_absolute(v, base) for sort_key, v in item_object.items()}
    if isinstance(item_object, list): return [resolve_to_absolute(v, base) for v in item_object]
    if isinstance(item_object, str) and not item_object.startswith(('/', 'data:', 'http')) and '.' in item_object.split('/')[-1] and (base / item_object).exists(): return str((base / item_object).resolve())
    return item_object


def en(item_object, key=None, n=[0]):
    if isinstance(item_object, dict): return {sort_key: en(v, sort_key) for sort_key, v in item_object.items()}
    if isinstance(item_object, list): return [en(v, key) for v in item_object]
    if isinstance(item_object, str) and key in TK:
        n[0] += 1; return EN[n[0] % len(EN)] if len(item_object) > 4 else 'OK ' + str(n[0])
    return item_object


def execute_audit(spec: dict, scratch_dir: Path):
    f = scratch_dir / 'v.json'; f.write_text(json.dumps(spec, ensure_ascii=False))
    r = subprocess.run(['uv', 'run', '--with', 'playwright', 'python', str(ENG / 'render.py'), '--spec', str(f), '--audit'], capture_output=True, text=True)
    plain_text = r.stdout + r.stderr; matched_object = re.search(r'红灯 (\d+)\s+黄灯 (\d+)', plain_text)
    return (int(matched_object.group(1)), int(matched_object.group(2)), [l.strip() for l in plain_text.splitlines() if '🔴' in l or '🟡' in l]) if matched_object else (-1, 0, [plain_text.strip().splitlines()[-1] if plain_text.strip() else '没有输出'])


def run_cli():
    argument_parser = argparse.ArgumentParser(); argument_parser.add_argument('--only'); argument_parser.add_argument('--variants', default='base,portrait,en'); argument_parser.add_argument('--out')
    a = argument_parser.parse_args(); only = set(a.only.split(',')) if a.only else None; version_records = a.variants.split(',')
    table_rows, bad = [], 0
    with tempfile.TemporaryDirectory() as td_value:
        for ex_value in sorted((ENG / 'examples').glob('*.json')):
            name = ex_value.stem
            if only and name not in only: continue
            spec = resolve_to_absolute(json.loads(ex_value.read_text()), ex_value.parent)
            collect_lint_findings = subprocess.run([sys.executable, str(ROOT / 'clip_lint.py'), str(ex_value)], capture_output=True, text=True)
            lr = '🔴' if collect_lint_findings.returncode else ('🟡' if '🟡' in collect_lint_findings.stdout else '✅')
            cells = {}
            for v in version_records:
                d = copy.deepcopy(spec)
                if v == 'portrait': d['width'], d['height'] = 1080, 1920
                elif v == 'en': d = en(d)
                red, yel, lines = execute_audit(d, Path(td_value))
                if red < 0 and 'y4' in name: cells[v] = ('跳过', ['需要角色帧库']); continue
                cells[v] = (f'{"🔴" if red else "✅"}{red}/{yel}' if red >= 0 else '💥', lines)
                if red != 0: bad += 1
            if lr == '🔴': bad += 1
            table_rows.append((name, lr, cells))
    print(f'{"示例":28} 校验  ' + '  '.join(f'{v:>9}' for v in version_records))
    for name, lr, cells in table_rows:
        print(f'{name:28} {lr}    ' + '  '.join(f'{cells[v][0]:>9}' for v in version_records))
    for name, lr, cells in table_rows:
        for v, (st_value, lines) in cells.items():
            for l in lines:
                if '🔴' in l or st_value == '💥': print(f'  [{name} · {v}] {l}')
    print('\n格式：红灯数/黄灯数。' + ('通过。' if not bad else f'有 {bad} 项红灯，见上。'))
    if a.out: Path(a.out).write_text(json.dumps([(n, l, {sort_key: v[0] for sort_key, v in character_code.items()}) for n, l, character_code in table_rows], ensure_ascii=False, indent=1))
    sys.exit(1 if bad else 0)


run_cli()
