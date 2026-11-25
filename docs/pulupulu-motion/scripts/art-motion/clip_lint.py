#!/usr/bin/env python3
"""Parameterized-clip spec validation: run it before rendering, so the traps that silently do nothing
instead of raising get said out loud up front.

uv run scripts/clip_lint.py spec.json [--strict]
Red (exit code 1): grammar does not exist, cue kind does not belong to that grammar, a required field is
missing, `at` is not a number, palette/finish is wrong, the image file does not exist, every cue falls
outside the duration.
Yellow: unknown fields (usually a typo or the wrong nesting level), camera written somewhere it has no
effect, a long blank head or tail, clip longer than 8s, cues crammed into the same frame.
--strict: yellow counts as failure too. The field tables live in engine/clip_schema.json; update them in
step when you change a grammar.
"""
import argparse, json, sys
from pathlib import Path

ENG = Path(__file__).resolve().parent / 'engine'


def get(item_object, target_path):
    for k in target_path.split('.'):
        if not isinstance(item_object, dict) or k not in item_object: return None
        item_object = item_object[k]
    return item_object


def run_cli():
    argument_parser = argparse.ArgumentParser(); argument_parser.add_argument('spec'); argument_parser.add_argument('--strict', action='store_true')
    a = argument_parser.parse_args()
    span_length = Path(a.spec).resolve(); red_value, yellow_level = [], []
    try: spec = json.loads(span_length.read_text())
    except Exception as e: sys.exit(f'🔴 Cannot read JSON: {e}')
    S = json.loads((ENG / 'clip_schema.json').read_text()); C = S['common']
    g = spec.get('grammar'); G = S['grammars'].get(g)
    if not G or not (ENG / 'clips' / f'{g}.js').exists():
        red_value.append(f'grammar "{g}" does not exist. Available: {" / ".join(S["grammars"])}'); report_text(red_value, yellow_level, a); return
    for k in spec:
        if k.startswith('_'): continue                      # comment keys such as _note
        if k not in C['spec']:
            hint = ' (camera belongs inside data: {"data": {"camera": "snap"}})' if k == 'camera' else ''
            yellow_level.append(f'spec top level "{k}" is not recognised and will be ignored{hint}')
    d = spec.get('duration')
    if not isinstance(d, (int, float)) or d <= 0: red_value.append('duration must be a number > 0 (seconds)'); d = 0
    elif d > 8: yellow_level.append(f'duration={d}s is over 8s: one clip stretched that long reads as a slide, split it into several shots')
    th = spec.get('theme')
    if isinstance(th, str) and th not in C['themes'] and g != 't3_finance_chart': red_value.append(f'theme "{th}" is not a palette name: {" / ".join(C["themes"])}')
    fn = spec.get('finish')
    if fn is not None and not (isinstance(fn, dict) or fn in C['finish']): red_value.append(f'finish "{fn}" is not a preset: {" / ".join(C["finish"])} (or write an object)')
    sd = spec.get('data') or {}
    if isinstance(sd, dict):
        for k in sd:
            if k not in G['specData']: yellow_level.append(f'spec.data "{k}" is not in the field table for {g} (typo, or wrong nesting level? recognised: {", ".join(G["specData"])})')
        for need in G.get('specNeeds', []):
            if get(spec, need) in (None, [], {}, ''): red_value.append(f'{g} requires {need}')
        if sd.get('camera') not in (None, 'smooth', 'snap'): red_value.append(f'data.camera only accepts smooth / snap, got "{sd.get("camera")}"')
    cues = spec.get('cues') or []
    if not cues: red_value.append('cues is empty')
    earlier_value = -1; seen_at_value = {}
    inside = 0
    for i, query_value in enumerate(cues):
        tag = f'cue[{i}]'
        if not isinstance(query_value, dict): red_value.append(f'{tag} is not an object'); continue
        at, kind = query_value.get('at'), query_value.get('kind')
        tag = f'cue[{i}] {kind}@{at}'
        if not isinstance(at, (int, float)): red_value.append(f'{tag}: at must be a number'); continue
        if kind not in G['kinds']: red_value.append(f'{tag}: {g} has no such kind. Available: {" / ".join(G["kinds"])}'); continue
        if at < earlier_value - 1e-9: yellow_level.append(f'{tag}: at is earlier than the previous cue (cues get re-sorted by time, make sure that is intended)')
        earlier_value = max(earlier_value, at)
        if d and at > d + 1e-9: yellow_level.append(f'{tag}: past the clip duration {d}s, never visible, will be dropped')
        else: inside += 1
        lookup_key = round(at, 3); seen_at_value[lookup_key] = seen_at_value.get(lookup_key, 0) + 1
        for k in query_value:
            if k not in C['cue']: yellow_level.append(f'{tag}: "{k}" in the cue is not recognised (recognised: {", ".join(C["cue"])})')
        qd_value = query_value.get('data') or {}
        if isinstance(qd_value, dict):
            for k in qd_value:
                if k == 'camera': yellow_level.append(f'{tag}: camera inside a cue\'s data has no effect; it belongs in the spec-level data')
                elif k not in G['cueData']: yellow_level.append(f'{tag}: data "{k}" is not in the field table for {g}/{kind} (typo? recognised: {", ".join(G["cueData"])})')
        for need in (G.get('needs', {}).get(kind) or []):
            success_flag = any(get(query_value, n) not in (None, '', [], {}) for n in need.split('|'))
            if not success_flag: red_value.append(f'{tag}: missing {need}')
        for im in ([query_value.get('image')] if query_value.get('image') else []) + (query_value['frames'] if isinstance(query_value.get('frames'), list) else []):
            if isinstance(im, str) and not im.startswith(('data:', 'http')) and not (span_length.parent / im).exists() and not Path(im).exists():
                red_value.append(f'{tag}: image not found {im} (relative to the spec file)')
    if cues and d and inside == 0: red_value.append('every cue falls outside the clip duration')
    if cues and d:
        ats = [query_value['at'] for query_value in cues if isinstance(query_value, dict) and isinstance(query_value.get('at'), (int, float)) and query_value['at'] <= d]
        if ats:
            if min(ats) > 1.2: yellow_level.append(f'first cue at {min(ats)}s: {min(ats)}s of blank head (may be intentional in a narration pipeline)')
            if d - max(ats) > 3.0: yellow_level.append(f'last cue at {max(ats)}s, then {d - max(ats):.1f}s with no new event, the picture will freeze')
    for k, n in seen_at_value.items():
        if n >= 3: yellow_level.append(f'{n} cues crammed into {k}s: only the last one stays legible')
    report_text(red_value, yellow_level, a)


def report_text(red_value, yellow_level, a):
    for red_channel in red_value: print('🔴', red_channel)
    for paired_value in yellow_level: print('🟡', paired_value)
    if not red_value and not yellow_level: print('✅ spec has no problems')
    sys.exit(1 if red_value or (a.strict and yellow_level) else 0)


run_cli()
