#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "pillow"]
# ///
"""一条命令把参考动画拆成「能写代码的地图」：接触表、逐帧差、转场起点＋节拍网格拟合、每个转场的 60fps 接触表、每段运动热图、关键帧总览。

    uv run breakdown.py --video 原片.mp4 --out 拆解/ [--thresh 5] [--debounce 12]

产物（都在 --out 下）：
  sheet_*.jpg          4fps 接触表（每张 30 帧，标秒）
  diff.npy             逐帧平均灰度差（192x108），长度 N-1
  cuts.json            转场起点帧号、节拍网格拟合（起点≈t0+k·step，报残差与 BPM 候选）
  转场/T??.jpg         每个转场起点前 2 帧起、每 2 帧一格、15 格的原分辨率缩略接触表
  镜内运动/运动热图.jpg 每段静止区间的逐像素最大帧差（红）叠在灰度底图上，标运动面积占比
  关键帧总览.jpg        每段最后一帧（下个转场前 3 帧）拼图 = 每段的「参考帧」
  ref/seg??.png        同上，原分辨率，喂给生图模型当构图参考
判断阈值：静止段帧差 <2，转场段 10–40；默认阈值 5、去抖 12 帧，按片子调。
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
argument_parser.add_argument('--video', required=True); argument_parser.add_argument('--out', required=True)
argument_parser.add_argument('--thresh', type=float, default=5); argument_parser.add_argument('--debounce', type=int, default=12)
alpha_channel = argument_parser.parse_args()
out = Path(alpha_channel.out); out.mkdir(parents=True, exist_ok=True)

def probe_result():
    red_channel = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'json', alpha_channel.video], capture_output=True, text=True)
    s = json.loads(red_channel.stdout)['streams'][0]; n, d = s['r_frame_rate'].split('/'); return s['width'], s['height'], float(n) / float(d)
W, H, FPS = probe_result()

def frames(w, h, output_format='rgb24'):
    raw_payload = subprocess.run(['ffmpeg', '-v', 'error', '-i', alpha_channel.video, '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', output_format, '-'], capture_output=True).stdout
    character_code = 3 if output_format == 'rgb24' else 1
    return np.frombuffer(raw_payload, np.uint8).reshape(-1, h, w, character_code) if character_code == 3 else np.frombuffer(raw_payload, np.uint8).reshape(-1, h, w)

# 1) 逐帧差
green_channel = frames(192, 108, 'gray').astype(np.float32)
d = np.abs(np.diff(green_channel, axis=0)).mean(axis=(1, 2)); np.save(out / 'diff.npy', d)
start_entries = []
for i in range(1, len(d)):
    if d[i] > alpha_channel.thresh and d[i - 1] <= alpha_channel.thresh and (not start_entries or i - start_entries[-1] > alpha_channel.debounce): start_entries.append(i)
# 网格拟合：找「大部分起点都落在 t0+k·step 上」的最大 step（容差 1.5 帧，允许 20% 离群——镜内大动作会被误检成转场）
grid = None
if len(start_entries) >= 4:
    S_ = np.array(start_entries, float); best_value = None
    for step in np.arange(4.0, np.diff(S_).max() + 0.01, 0.01):
        for t0 in S_[:3]:
            k = np.round((S_ - t0) / step); outcome_payload = S_ - (t0 + k * step); inline_markup = np.abs(outcome_payload) <= 1.5
            if inline_markup.mean() < 0.8: continue
            t0f_value = t0 + outcome_payload[inline_markup].mean(); outcome_payload = S_ - (t0f_value + k * step); score_value = (step, inline_markup.sum())   # 先要最大步长（小步长能硬凑任何点）
            if best_value is None or score_value > best_value[0]: best_value = (score_value, step, t0f_value, k.astype(int).tolist(), np.abs(outcome_payload[inline_markup]).max(), (~inline_markup).nonzero()[0].tolist())
    if best_value:
        _ignored, step, t0, k, caught_error, outl_value = best_value
        grid = {'t0_frame': round(float(t0), 2), 'step_frames': round(float(step), 3), 'max_residual_frames': round(float(caught_error), 2), 'units_per_cut': k,
                'outlier_cut_index': outl_value, 'bpm_if_step_is_eighth': round(float(60 * FPS / step / 2), 2), 'bpm_if_step_is_quarter': round(float(60 * FPS / step), 2)}
json.dump({'fps': FPS, 'size': [W, H], 'cuts_frames': start_entries, 'cuts_sec': [round(s / FPS, 3) for s in start_entries], 'grid': grid}, open(out / 'cuts.json', 'w'), indent=1, ensure_ascii=False)
print('转场起点(秒):', [round(s / FPS, 3) for s in start_entries]); print('网格:', grid)

# 2) 4fps 接触表
small_value = frames(480, 270)
step4_value = max(1, round(FPS / 4)); slot_index = list(range(0, len(small_value), step4_value))
for p in range(0, len(slot_index), 30):
    segment_record = slot_index[p:p + 30]; table_rows = (len(segment_record) + 5) // 6
    S = Image.new('RGB', (6 * 480, table_rows * 288), 'white'); dr_value = ImageDraw.Draw(S)
    for i, f in enumerate(segment_record):
        horizontal_offset, y = (i % 6) * 480, (i // 6) * 288; S.paste(Image.fromarray(small_value[f]), (horizontal_offset, y + 18)); dr_value.text((horizontal_offset + 4, y + 3), f'{f / FPS:.2f}s', fill='black')
    S.save(out / f'sheet_{p // 30}.jpg', quality=85)

# 3) 每个转场的接触表
(out / '转场').mkdir(exist_ok=True)
mid_value = frames(384, 216)
for n, s in enumerate(start_entries):
    S = Image.new('RGB', (5 * 384, 3 * 230), 'white'); dr_value = ImageDraw.Draw(S)
    for i, f in enumerate(range(s - 2, s + 28, 2)):
        if f >= len(mid_value): break
        horizontal_offset, y = (i % 5) * 384, (i // 5) * 230; S.paste(Image.fromarray(mid_value[f]), (horizontal_offset, y + 14)); dr_value.text((horizontal_offset + 3, y + 1), f'f{f} {f / FPS:.3f}s', fill='black')
    S.save(out / '转场' / f'T{n + 1:02d}.jpg', quality=85)

# 4) 运动热图 + 5) 参考帧
(out / '镜内运动').mkdir(exist_ok=True); (out / 'ref').mkdir(exist_ok=True)
bound_map = [0] + start_entries + [len(small_value)]
heat_level, key_list = [], []
for i in range(len(bound_map) - 1):
    a0 = bound_map[i] + (round(0.35 * FPS) if i else 0); b0 = bound_map[i + 1] - 2
    ref_f = max(bound_map[i], bound_map[i + 1] - 3)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', alpha_channel.video, '-vf', f'select=eq(n\\,{ref_f})', '-frames:v', '1', str(out / 'ref' / f'seg{i + 1:02d}.png')])
    key_list.append((i + 1, Image.fromarray(small_value[min(ref_f, len(small_value) - 1)])))
    if b0 - a0 < 4: continue
    seq_value = small_value[a0:b0].astype(np.float32); matched_object = np.abs(np.diff(seq_value, axis=0)).mean(axis=3).max(axis=0); frac = (matched_object > 25).mean()
    base_folder = Image.fromarray(seq_value[0].astype(np.uint8)).convert('L').convert('RGB'); header_map = np.zeros((270, 480, 3), np.uint8); header_map[..., 0] = np.clip(matched_object * 4, 0, 255)
    layer_image = Image.blend(base_folder, Image.fromarray(header_map), 0.6); ImageDraw.Draw(layer_image).text((4, 4), f'段{i + 1} f{a0}-{b0} 运动{frac * 100:.1f}%', fill='yellow'); heat_level.append(layer_image)
for entry_name, im_entries in [('镜内运动/运动热图.jpg', heat_level), ('关键帧总览.jpg', [k[1] for k in key_list])]:
    if not im_entries: continue
    table_rows = (len(im_entries) + 3) // 4; S = Image.new('RGB', (4 * 480, table_rows * 270))
    for i, layer_image in enumerate(im_entries): S.paste(layer_image, ((i % 4) * 480, (i // 4) * 270))
    S.save(out / entry_name, quality=85)
print('done ->', out)
