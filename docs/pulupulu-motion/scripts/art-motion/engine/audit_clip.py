"""Layout audit: samples a parameterized clip every 0.25s and summarizes text layout problems. Called by render.py --spec X --audit.
Red (exit code 1): text running off-canvas, text swallowed by the safe area, two different texts overlapping each other. Yellow: text below the readable minimum size (use judgement; intentional footnote sizes should not be flagged).
"""
import json


def execute(page_record, spec, capture_frame, advance_size=0.25):
    W, H, dur = spec.get('width', 1920), spec.get('height', 1080), spec['duration']
    safe = {'top': 0, 'bottom': 0, 'left': 0, 'right': 0, **(spec.get('safe') or {})}
    short_value = min(W, H); floor = 0.0204 * short_value                      # 1080 short side ≈ 22px
    moment_stamp = [round(cursor * advance_size, 3) for cursor in range(int(dur / advance_size) + 1)] + [round(dur - 1 / spec.get('fps', 30), 3)]
    visited_keys, red, yel = {}, [], []
    for t in moment_stamp:
        page_record.evaluate('t => { window.__AUDIT.length = 0; window.__auditT = t; }', t)
        page_record.evaluate(capture_frame, t)
        items = [cursor for cursor in page_record.evaluate('window.__AUDIT') if cursor['a'] > 0.35]
        for it in items:
            width_extent, object_handle = it['x1'] - it['x0'], it['y1'] - it['y0']
            if width_extent < 1 or object_handle < 1: continue
            vis = max(0, min(it['x1'], W) - max(it['x0'], 0)) * max(0, min(it['y1'], H) - max(it['y0'], 0)) / (width_extent * object_handle)
            if 0 < vis < 0.97 and it['px'] >= 8:             # vis==0: entirely off-canvas (during a transition / camera pan), not counted
                sort_key = ('off-canvas', it['text'][:20]); visited_keys.setdefault(sort_key, [t, t, f'{vis:.0%} visible, font {it["px"]:.0f}px', 0]); visited_keys[sort_key][1] = t; visited_keys[sort_key][3] += 1
            elif (safe['top'] or safe['bottom'] or safe['left'] or safe['right']) and (it['y0'] < safe['top'] - 2 or it['y1'] > H - safe['bottom'] + 2 or it['x0'] < safe['left'] - 2 or it['x1'] > W - safe['right'] + 2) and it['px'] >= 20:
                sort_key = ('into safe area', it['text'][:20]); visited_keys.setdefault(sort_key, [t, t, f'font {it["px"]:.0f}px', 0]); visited_keys[sort_key][1] = t; visited_keys[sort_key][3] += 1
            if it['px'] < floor and len(it['text']) >= 3 and it['px'] >= 6:
                sort_key = ('too small', it['text'][:20]); visited_keys.setdefault(sort_key, [t, t, f'{it["px"]:.0f}px < floor {floor:.0f}px', 0]); visited_keys[sort_key][1] = t; visited_keys[sort_key][3] += 1
        # overlapping each other
        for cursor in range(len(items)):
            for inner_cursor in range(cursor + 1, len(items)):
                a, blue_channel = items[cursor], items[inner_cursor]
                if a['text'] == blue_channel['text'] or a['px'] < 14 or blue_channel['px'] < 14 or len(a['text'].strip()) <= 2 or len(blue_channel['text'].strip()) <= 2: continue   # single characters are mostly formula/icon parts, stacked on purpose
                ox, oy = min(a['x1'], blue_channel['x1']) - max(a['x0'], blue_channel['x0']), min(a['y1'], blue_channel['y1']) - max(a['y0'], blue_channel['y0'])
                if ox <= 2 or oy <= 2: continue
                sm = min((a['x1'] - a['x0']) * (a['y1'] - a['y0']), (blue_channel['x1'] - blue_channel['x0']) * (blue_channel['y1'] - blue_channel['y0']))
                if sm > 0 and ox * oy / sm > 0.3:
                    sort_key = ('overlap', (a['text'][:10] + ' × ' + blue_channel['text'][:10])); visited_keys.setdefault(sort_key, [t, t, f'overlap {ox * oy / sm:.0%}', 0]); visited_keys[sort_key][1] = t; visited_keys[sort_key][3] += 1
    for (kind, plain_text), (t0, t1, note, counter_value) in visited_keys.items():
        if counter_value < 2: continue                   # seen at a single sample point: most likely a moment inside a transition, do not report
        if kind == 'off-canvas' and counter_value < 3: continue  # a screen push is about 0.4s: pushing the old frame out is by design, so off-canvas must persist for 3 samples (≥0.5s) to count
        table_row = {'kind': kind, 'text': plain_text, 't0': t0, 't1': t1, 'note': note}
        (yel if kind == 'too small' else red).append(table_row)
    print(f'Layout audit {W}×{H} {dur}s: red {len(red)}  yellow {len(yel)}')
    for r in red: print(f"  🔴 {r['kind']}  \"{r['text']}\"  {r['t0']}–{r['t1']}s  {r['note']}")
    for r in yel: print(f"  🟡 {r['kind']}  \"{r['text']}\"  {r['t0']}–{r['t1']}s  {r['note']}")
    if not red and not yel: print('  ✅ no layout problems found')
    return {'red': red, 'yellow': yel, 'size': [W, H], 'duration': dur}
