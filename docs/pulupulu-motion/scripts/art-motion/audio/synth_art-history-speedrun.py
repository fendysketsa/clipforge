#!/usr/bin/env python3
"""速通片 15 秒配乐模板 —— 纯代码合成，不用任何采样。乐谱是一段原创示例（D 小调），换成你自己的即可。

运行：
  uv run --with numpy --with scipy --with soundfile python scripts/audio/synth_艺术史速通.py
输出：脚本同目录 示例配乐.wav（48k / 立体声 / 15.06s）

方法见 references/风格配方/_音轨_艺术史速通.md：128 BPM 严格网格（八分音符 0.23431s，网格零点 0.028s），
17 个时代按八分音符数 6,4,4,4,4,4,3,3,3,3,2,2,2,1,1,1,9 依次排布（这是独立配乐示例，换片子时按实际段落表重排），
每个时代换一套配器，一个三音动机换乐器、随和弦移调；13.155s 音乐停，接音效（拍杯叮、滑哨坠落、碎裂、猫叫、收尾拨弦）。
响度：逐段 K 加权响度对齐到 target 表，再整体对齐 -14 LUFS / 真峰 -1.5 dBFS。
"""
import numpy as np
import scipy.signal as ss
import soundfile as sf
from pathlib import Path

SR = 48000
N = 722944                       # 独立示例总长15.0613s
T0, E = 0.028, 0.23431           # 网格零点、八分音符时长（实测 128.04 BPM）
random_source = np.random.default_rng(7)
OUT = Path(__file__).with_name("示例配乐.wav")

L = np.zeros(N); R = np.zeros(N)


def perform_tt(total_count):                        # 第 n 个八分音符的绝对时间
    return T0 + total_count * E


NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def perform_hz(name):
    s = NOTE[name[0]]; cursor = 1
    while name[cursor] in "#b":
        s += 1 if name[cursor] == "#" else -1; cursor += 1
    midi_value = 12 * (int(name[cursor:]) + 1) + s
    return 440.0 * 2 ** ((midi_value - 69) / 12)


def append(sig_value, elapsed_seconds, gain_value=1.0, pan=0.0):
    """等功率声像放进总线。pan -1..1"""
    s = int(round(elapsed_seconds * SR))
    if s >= N or len(sig_value) == 0:
        return
    sig_value = sig_value[: N - s] * gain_value
    a = (pan + 1) * np.pi / 4
    L[s:s + len(sig_value)] += sig_value * np.cos(a)
    R[s:s + len(sig_value)] += sig_value * np.sin(a)


# ---------------------------------------------------------------- 基础构件
def perform_tvec(dur):
    return np.arange(int(dur * SR)) / SR


def perform_adsr(dur, a=0.01, d=0.05, s=0.8, r=0.1):
    """dur 为按住时长，返回长度 dur+r 的包络"""
    elapsed_seconds = perform_tvec(dur + r)
    caught_error = np.where(elapsed_seconds < a, elapsed_seconds / max(a, 1e-4), 0)
    matched_object = (elapsed_seconds >= a) & (elapsed_seconds < a + d); caught_error[matched_object] = 1 - (1 - s) * (elapsed_seconds[matched_object] - a) / max(d, 1e-4)
    matched_object = (elapsed_seconds >= a + d) & (elapsed_seconds < dur); caught_error[matched_object] = s
    lvl_value = s if dur > a + d else max(caught_error[elapsed_seconds < dur][-1] if (elapsed_seconds < dur).any() else 0, 0)
    matched_object = elapsed_seconds >= dur; caught_error[matched_object] = lvl_value * np.exp(-(elapsed_seconds[matched_object] - dur) / max(r / 4, 1e-4))
    return caught_error


def perform_additive(f, amps, dur, phase_jitter=True):
    """f 可以是常数或逐样本频率数组；amps[k] 是第 k+1 次谐波幅度。带限到 18k。"""
    total_count = int(dur * SR) if np.isscalar(f) else len(f)
    fa_value = np.full(total_count, f) if np.isscalar(f) else f
    ph_value = 2 * np.pi * np.cumsum(fa_value) / SR
    artifact_path = np.zeros(total_count); fmax_value = fa_value.max()
    for k, a in enumerate(amps, 1):
        if a == 0 or k * fmax_value > 18000:
            continue
        first_sample = random_source.uniform(0, 2 * np.pi) if phase_jitter else 0
        artifact_path += a * np.sin(k * ph_value + first_sample)
    return artifact_path


def perform_saw_amps(total_count=40):
    return [1 / k for k in range(1, total_count + 1)]


def perform_square_amps(total_count=40):
    return [1 / k if k % 2 else 0 for k in range(1, total_count + 1)]


ATT = 0.010                      # 起音软化：2ms 硬起音听起来太「点」，10ms 更连贯


def perform_pluck(f, dur, amps, d0=3.0, slope=0.6, B=0.0, noise=0.02, bend=0.0, att=None):
    """拨弦/击弦：各次谐波独立指数衰减，高次衰减更快；B 为弦的非谐性；bend 为起音音高回落（半音）。
    v2：基音 att 秒线性起音，高次谐波起音更慢（模拟滤波包络从闭到开），起音噪声减半。"""
    att = ATT if att is None else att
    elapsed_seconds = perform_tvec(dur); artifact_path = np.zeros_like(elapsed_seconds)
    fb_value = f * 2 ** (bend * np.exp(-elapsed_seconds / 0.03) / 12) if bend else np.full_like(elapsed_seconds, f)
    ph_value = 2 * np.pi * np.cumsum(fb_value) / SR
    for k, a in enumerate(amps, 1):
        fk_value = f * k * np.sqrt(1 + B * k * k)
        if fk_value > 18000 or a == 0:
            continue
        ak_value = min(att * (1 + 0.6 * (k - 1)), 0.035)          # 高次谐波晚开
        artifact_path += a * np.exp(-elapsed_seconds * d0 * (1 + slope * (k - 1))) * np.minimum(1, elapsed_seconds / ak_value) * np.sin(ph_value * fk_value / f + random_source.uniform(0, 6.28))
    if noise:
        neighbour_count = random_source.standard_normal(len(elapsed_seconds)) * np.exp(-elapsed_seconds / 0.006) * noise * 0.5
        artifact_path += perform_lp(perform_hp(neighbour_count, 2000), 7000)
    return artifact_path


def breakpoint_map(sample_value, lower_bound, upper_bound, order_value=2):
    return ss.sosfilt(ss.butter(order_value, [lower_bound, upper_bound], "band", fs=SR, output="sos"), sample_value)


def perform_hp(sample_value, fc_value, order_value=2):
    return ss.sosfilt(ss.butter(order_value, fc_value, "high", fs=SR, output="sos"), sample_value)


def perform_lp(sample_value, fc_value, order_value=2):
    return ss.sosfilt(ss.butter(order_value, fc_value, "low", fs=SR, output="sos"), sample_value)


def noise(dur):
    return random_source.standard_normal(int(dur * SR))


def perform_expdec(dur, tau_value):
    return np.exp(-perform_tvec(dur) / tau_value)


# ---------------------------------------------------------------- 乐器
def perform_bone_flute(total_count, dur):          # 洞穴：近纯正弦 + 气声，慢起音
    f = perform_hz(total_count); held_value = dur
    elapsed_seconds = perform_tvec(held_value + 0.3)
    vib_value = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * elapsed_seconds) * np.minimum(1, elapsed_seconds / 0.2)
    tone_value = perform_additive(f * vib_value, [1, 0.018, 0.022, 0.012], held_value + 0.3)
    breath_value = breakpoint_map(noise(held_value + 0.3), f * 0.8, f * 3.5) * 0.05
    return (tone_value + breath_value) * perform_adsr(held_value, a=0.07, d=0.1, s=0.9, r=0.3)[: len(elapsed_seconds)]


def perform_frame_drum():                # 洞穴：低沉手鼓，98→87Hz
    elapsed_seconds = perform_tvec(0.5); f = 87 + 14 * np.exp(-elapsed_seconds / 0.04)
    body_text = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-elapsed_seconds / 0.16)
    skin_value = perform_lp(noise(0.5), 900) * np.exp(-elapsed_seconds / 0.02) * 0.3
    return body_text + skin_value


def perform_stick_click(level_value=1.0):      # 敲击/摇奏的高频颗粒
    elapsed_seconds = perform_tvec(0.04)
    return breakpoint_map(noise(0.04), 4000, 11000) * np.exp(-elapsed_seconds / 0.006) * level_value


def perform_harp(total_count, dur=0.6, bright_value=1.0):     # 埃及竖琴：H2≈-11dB，0.2s 衰减约 15dB
    return perform_pluck(perform_hz(total_count), dur, [1, 0.3 * bright_value, 0.07, 0.12, 0.015, 0.015, 0.02], d0=6.0, slope=0.5, noise=0.03)


def perform_sistrum():                   # 埃及叉铃：带金属泛音的短噪声
    elapsed_seconds = perform_tvec(0.12)
    jing_value = sum(np.sin(2 * np.pi * f * elapsed_seconds + random_source.uniform(0, 6)) for f in (5120, 6890, 8230)) * 0.15
    return (breakpoint_map(noise(0.12), 6000, 12000) + jing_value) * np.exp(-elapsed_seconds / 0.025)


def perform_lyre(total_count, dur=0.8):            # 希腊里拉琴：较闷的拨弦
    return perform_pluck(perform_hz(total_count), dur, [1, 0.45, 0.3, 0.12, 0.05, 0.03], d0=3.5, slope=0.7, noise=0.02)


def perform_aulos(total_count, dur):               # 希腊双管：明亮簧音，H2/H3 强，持续
    f = perform_hz(total_count); elapsed_seconds = perform_tvec(dur + 0.06)
    vib_value = 1 + 0.006 * np.sin(2 * np.pi * 6 * elapsed_seconds) * np.minimum(1, elapsed_seconds / 0.15)
    tone_value = perform_additive(f * vib_value, [1, 0.4, 0.6, 0.35, 0.06, 0.035, 0.11, 0.06], dur + 0.06)
    tone_value += breakpoint_map(noise(dur + 0.06), f, f * 4) * 0.03
    return tone_value * perform_adsr(dur, a=0.05, d=0.05, s=0.9, r=0.06)


def perform_tambourine():
    elapsed_seconds = perform_tvec(0.35)
    return breakpoint_map(noise(0.35), 7000, 14000) * np.exp(-elapsed_seconds / 0.09) * (1 + 0.5 * np.sin(2 * np.pi * 28 * elapsed_seconds))


def perform_brass(total_count, dur):               # 罗马号角：锯齿 + 随包络变亮的低通
    f = perform_hz(total_count); aggregate_count = dur + 0.08
    raw_payload = perform_additive(f, perform_saw_amps(30), aggregate_count)
    env_value = perform_adsr(dur, a=0.03, d=0.12, s=0.6, r=0.08)
    elapsed_seconds = perform_tvec(aggregate_count)
    # 分两段低通近似"开口变亮再收"
    bright_value = perform_lp(raw_payload, min(f * 10, 12000)); dull_value = perform_lp(raw_payload, min(f * 4, 7000))
    width_extent = np.exp(-elapsed_seconds / 0.12)
    return (bright_value * width_extent + dull_value * (1 - width_extent)) * env_value


def perform_war_drum():                  # 罗马战鼓 ~87Hz
    elapsed_seconds = perform_tvec(0.45); f = 70 + 30 * np.exp(-elapsed_seconds / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-elapsed_seconds / 0.13) + perform_lp(noise(0.45), 1500) * np.exp(-elapsed_seconds / 0.015) * 0.5


def perform_organ(total_count, dur):               # 哥特管风琴：H1 + 奇次/高次音栓，几乎不衰减
    f = perform_hz(total_count); aggregate_count = dur + 0.15; elapsed_seconds = perform_tvec(aggregate_count)
    trem_value = 1 + 0.03 * np.sin(2 * np.pi * 5.5 * elapsed_seconds)
    tone_value = perform_additive(f, [1, 0.03, 0.05, 0.12, 0.18, 0.04, 0.0, 0.06, 0.03, 0.05, 0.02, 0.04, 0, 0.03, 0, 0.03], aggregate_count) * trem_value  # 末尾为混合音栓（高频）
    return tone_value * perform_adsr(dur, a=0.035, d=0.02, s=1.0, r=0.15)


def perform_harpsichord(total_count, dur=0.5):     # 文艺复兴羽管键琴：鼻音（H5 突出），衰减中等
    return perform_pluck(perform_hz(total_count), dur, [1, 0.12, 0.045, 0.06, 0.14, 0.02, 0.03, 0.025] + [0.02] * 10, d0=2.2, slope=0.12, noise=0.08)


def perform_viol(total_count, dur):                # 低音维奥尔：柔和弓弦
    f = perform_hz(total_count); aggregate_count = dur + 0.12
    raw_payload = perform_lp(perform_additive(f, perform_saw_amps(20), aggregate_count), 1200)
    return raw_payload * perform_adsr(dur, a=0.06, d=0.1, s=0.85, r=0.12)


def perform_koto(total_count, dur=0.35):           # 浮世绘：筝/三味线，快衰减 + 起音回落
    return perform_pluck(perform_hz(total_count), dur, [1, 0.55, 0.12, 0.13, 0.13, 0.06, 0.04], d0=14, slope=0.4, noise=0.06, bend=0.6)


def perform_taiko():
    elapsed_seconds = perform_tvec(0.6); f = 58 + 40 * np.exp(-elapsed_seconds / 0.05)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-elapsed_seconds / 0.2) + perform_lp(noise(0.6), 700) * np.exp(-elapsed_seconds / 0.03) * 0.4


def perform_hyoshigi():                  # 拍子木
    elapsed_seconds = perform_tvec(0.06)
    return (breakpoint_map(noise(0.06), 1800, 4200, 4) + np.sin(2 * np.pi * 2650 * elapsed_seconds) * 0.6) * np.exp(-elapsed_seconds / 0.012)


def perform_soft_piano(total_count, dur=0.9):      # 印象派：柔和钢琴/钢片琴，接近正弦
    return perform_pluck(perform_hz(total_count), dur, [1, 0.16, 0.08, 0.04, 0.025, 0.015, 0.012, 0.01, 0.008], d0=2.6, slope=0.45, B=0.0002, noise=0.03)


def perform_pizz(total_count, dur=0.3):            # 梵高：明亮拨弦（H2/H3 很强），快衰减
    return perform_pluck(perform_hz(total_count), dur, [1, 0.9, 0.6, 0.22, 0.35, 0.14, 0.09, 0.05], d0=18, slope=0.3, noise=0.04)


def perform_swirl(dur):                  # 梵高：上扬的风声
    sample_value = noise(dur); total_count = len(sample_value); artifact_path = np.zeros(total_count); segment_record = 2400
    for cursor in range(0, total_count, segment_record):
        fc_value = 2500 + 6000 * cursor / total_count
        artifact_path[cursor:cursor + segment_record] = breakpoint_map(sample_value[max(0, cursor - 400):cursor + segment_record], fc_value * 0.7, fc_value * 1.3)[-len(artifact_path[cursor:cursor + segment_record]):]
    return artifact_path * np.sin(np.pi * np.arange(total_count) / total_count)


def perform_celesta(total_count, dur=0.35):        # 新艺术：钢片琴/竖琴，快衰减
    return perform_pluck(perform_hz(total_count), dur, [1, 0.6, 0.12, 0.1, 0.12, 0.12, 0.2, 0.06], d0=11, slope=0.3, noise=0.02)


def perform_blip(total_count, dur=0.2):            # 包豪斯：几何感短音（马林巴式）
    return perform_pluck(perform_hz(total_count), dur, [1, 0.75, 0.2, 0.4], d0=22, slope=0.4, noise=0.0)


def perform_tick():
    elapsed_seconds = perform_tvec(0.015)
    return perform_hp(noise(0.015), 6000) * np.exp(-elapsed_seconds / 0.003)


def perform_kick(f0_value=150, f1_value=48, tau_value=0.18, dur=0.35):
    elapsed_seconds = perform_tvec(dur); f = f1_value + (f0_value - f1_value) * np.exp(-elapsed_seconds / 0.025)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-elapsed_seconds / tau_value) + perform_hp(noise(dur), 3000) * np.exp(-elapsed_seconds / 0.003) * 0.15


def perform_clap():
    elapsed_seconds = perform_tvec(0.18); env_value = np.zeros_like(elapsed_seconds)
    for d in (0, 0.009, 0.018):
        env_value += (elapsed_seconds >= d) * np.exp(-np.maximum(elapsed_seconds - d, 0) / (0.006 if d < 0.018 else 0.05))
    return breakpoint_map(noise(0.18), 1200, 6000) * env_value


def perform_hat(unsealed_flag=False):
    d = 0.09 if unsealed_flag else 0.03; elapsed_seconds = perform_tvec(d)
    return perform_hp(noise(d), 7500, 4) * np.exp(-elapsed_seconds / (d / 3))


def perform_chip(total_count, dur, duty_sq_value=True):  # 像素：方波（只有奇次谐波）
    f = perform_hz(total_count); aggregate_count = dur + 0.01
    return perform_additive(f, perform_square_amps(40), aggregate_count, phase_jitter=False) * perform_adsr(dur, a=0.006, d=0.0, s=1.0, r=0.01)


def perform_supersaw(total_count, dur):            # 光追：多层失谐锯齿，玻璃感
    f = perform_hz(total_count); aggregate_count = dur + 0.15; artifact_path = 0
    for detail_value in (-0.012, -0.005, 0, 0.006, 0.013):
        artifact_path = artifact_path + perform_additive(f * (1 + detail_value), perform_saw_amps(25), aggregate_count)
    artifact_path = perform_lp(artifact_path / 5, 7000)
    return artifact_path * perform_adsr(dur, a=0.04, d=0.1, s=0.7, r=0.15)


def perform_boing(t0_value=11.01, t1_value=11.165, f0_value=600, f1_value=985):   # 猫跳上桌：上滑音
    elapsed_seconds = perform_tvec(t1_value - t0_value); f = f0_value * (f1_value / f0_value) ** (elapsed_seconds / elapsed_seconds[-1])
    tone_value = perform_additive(f, [1, 0.5, 0.35, 0.2, 0.1], len(elapsed_seconds) / SR)
    return tone_value * np.sin(np.pi * elapsed_seconds / elapsed_seconds[-1]) ** 0.5


def perform_pluck2026(total_count, dur=0.22):      # 2026：方波系合成拨奏（H2 弱、H3 强）+ 包络低通
    f = perform_hz(total_count); aggregate_count = dur
    raw_payload = perform_additive(f, [1, 0.1, 0.38, 0.3, 0.22, 0.12, 0.14, 0.1, 0.08], aggregate_count)
    return raw_payload * np.exp(-perform_tvec(aggregate_count) / 0.1) * np.minimum(1, perform_tvec(aggregate_count) / 0.014)


def perform_sub_bass(total_count, dur):            # 2026：锯齿低音 + 下八度正弦
    f = perform_hz(total_count); aggregate_count = dur + 0.15
    raw_payload = perform_lp(perform_additive(f, perform_saw_amps(30), aggregate_count), 700, 4) + 0.6 * np.sin(2 * np.pi * f / 2 * perform_tvec(aggregate_count))
    return raw_payload * perform_adsr(dur, a=0.01, d=0.05, s=0.9, r=0.15)


def perform_pad(total_count, dur):
    f = perform_hz(total_count); aggregate_count = dur + 0.1
    return perform_lp(perform_additive(f, perform_saw_amps(15), aggregate_count), 2500) * perform_adsr(dur, a=0.05, d=0.1, s=0.7, r=0.1)


# ---------------------------------------------------------------- 音效
def perform_tink():                      # 13.16 猫爪碰杯：陶瓷高频非谐振铃
    elapsed_seconds = perform_tvec(0.35); artifact_path = 0
    for f, a, tau_value in ((5720, 1, 0.12), (6506, 0.6, 0.09), (6315, 0.25, 0.1), (5490, 0.35, 0.08), (1533, 0.1, 0.05)):
        artifact_path = artifact_path + a * np.sin(2 * np.pi * f * elapsed_seconds) * np.exp(-elapsed_seconds / tau_value)
    return artifact_path


def perform_swipe():                     # 爪子划过的嗖声
    d = 0.2; elapsed_seconds = perform_tvec(d)
    return breakpoint_map(noise(d), 2500, 9000) * np.sin(np.pi * elapsed_seconds / d) ** 2


def perform_slide_whistle(t0_value=13.29, t1_value=13.635, f0_value=1550, f1_value=325):   # 杯子坠落：指数下滑正弦
    elapsed_seconds = perform_tvec(t1_value - t0_value); f = f0_value * (f1_value / f0_value) ** (elapsed_seconds / elapsed_seconds[-1])
    tone_value = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env_value = np.minimum(1, elapsed_seconds / 0.015) * np.minimum(1, (elapsed_seconds[-1] - elapsed_seconds) / 0.01 + 0.0001)
    return tone_value * env_value


def perform_crash():                     # 13.624 碎裂：83Hz 闷响 + 高频碎屑 + 非谐振残响
    d = 0.6; elapsed_seconds = perform_tvec(d)
    f = 60 + 40 * np.exp(-elapsed_seconds / 0.02)
    thump_value = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-elapsed_seconds / 0.07)
    hiss_value = perform_hp(noise(d), 2500) * np.exp(-elapsed_seconds / 0.13)
    shard_entries = np.zeros_like(elapsed_seconds)
    for _ in range(14):                      # 若干碎片的二次小碰撞
        s = random_source.uniform(0.02, 0.4); cursor = int(s * SR); green_channel = random_source.uniform(0.2, 0.7) * np.exp(-s / 0.2)
        segment_record = perform_hp(noise(0.03), 4000) * np.exp(-perform_tvec(0.03) / 0.005) * green_channel
        shard_entries[cursor:cursor + len(segment_record)] += segment_record[: len(shard_entries) - cursor]
    ring_value = sum(a * np.sin(2 * np.pi * frame_image * elapsed_seconds) * np.exp(-elapsed_seconds / tau_value)
               for frame_image, a, tau_value in ((1669, .25, .15), (2302, .2, .1), (4462, .12, .08), (7320, .3, .12), (7921, .25, .1)))
    return thump_value * 1.2 + hiss_value * 0.6 + shard_entries + ring_value


def perform_meow(t0_value=14.12, tp_value=14.28, t1_value=14.65):   # 猫叫：574→797Hz 上行，再降到 486Hz；锯齿 + 共振峰
    total_count = int((t1_value - t0_value) * SR); elapsed_seconds = np.arange(total_count) / SR; ip_value = int((tp_value - t0_value) * SR)
    f = np.empty(total_count); f[:ip_value] = np.linspace(574, 797, ip_value); f[ip_value:] = np.linspace(797, 486, total_count - ip_value)
    raw_payload = perform_additive(f, perform_saw_amps(24), total_count / SR)
    vowel_value = 0.5 * breakpoint_map(raw_payload, 1300, 1900) + 1.0 * breakpoint_map(raw_payload, 2100, 2700) + 0.9 * breakpoint_map(raw_payload, f.mean() * 0.8, f.mean() * 1.3) + 0.15 * raw_payload
    env_value = np.minimum(1, elapsed_seconds / 0.04) * np.minimum(1, (elapsed_seconds[-1] - elapsed_seconds) / 0.12)
    return vowel_value * env_value


def perform_end_thump(f=90, sparkle_value=True):     # 签名出现时的轻"啵"
    d = 0.2; elapsed_seconds = perform_tvec(d)
    artifact_path = np.sin(2 * np.pi * f * elapsed_seconds) * np.exp(-elapsed_seconds / 0.05)
    if sparkle_value:
        artifact_path += sum(0.08 * np.sin(2 * np.pi * frame_image * elapsed_seconds) * np.exp(-elapsed_seconds / 0.06) for frame_image in (531, 852, 921, 965, 1058))
    return artifact_path


# ---------------------------------------------------------------- 编曲（时间单位：八分音符）
def perform_era(first_count, items):
    """items: (相对八分位置, 生成函数, 增益, 声像)"""
    for slot_index_x, fn_value, green_channel, pan in items:
        append(fn_value(), perform_tt(first_count + slot_index_x), green_channel, pan)


B8 = E                                            # 一个八分音符的秒数

# ---- 原创示例乐谱（D 小调 / F 大调，和声骨架 Dm–B♭–F–C）----
# 贯穿动机：♪♪♩「级进上行、再下跳」，每段换乐器、随当段和弦移调；洞穴段用它的下行扩大版先立住。
# 1 洞穴（6 个八分）：骨笛 A4–G4–D4（下行，附点四分起）+ 手鼓 + 弱拍敲击
perform_era(0, [(0, lambda: perform_bone_flute("A4", 3 * B8), 1.0, 0), (3, lambda: perform_bone_flute("G4", B8), 1.0, 0),
        (4, lambda: perform_bone_flute("D4", 2.4 * B8), 1.0, 0),
        (0, perform_frame_drum, 1.3, -0.1), (3, perform_frame_drum, 1.1, -0.1)]
    + [(k, lambda: perform_stick_click(0.25), 1.0, 0.25) for k in (1, 2, 4, 5)])

# 2 埃及（4）：竖琴 Dm→B♭ 分解 + 动机 F5–G5–D5 + 弱拍叉铃
perform_era(6, [(0, lambda: perform_harp("D3", 0.9), 0.55, -0.2), (0.06, lambda: perform_harp("F3", 0.6), 0.35, -0.15),
        (0.5, lambda: perform_harp("A3", 0.6), 0.45, -0.1), (1, lambda: perform_harp("D4", 0.5), 0.4, -0.2),
        (2, lambda: perform_harp("Bb2", 0.9), 0.5, -0.2), (2.06, lambda: perform_harp("D3", 0.6), 0.35, -0.15), (3, lambda: perform_harp("F3", 0.5), 0.4, -0.2),
        (0, lambda: perform_harp("F5", 0.5, 1.2), 0.8, 0.1), (1, lambda: perform_harp("G5", 0.5, 1.2), 0.8, 0.1),
        (2, lambda: perform_harp("D5", 0.6, 1.2), 0.8, 0.1)]
    + [(k + 0.5, perform_sistrum, 0.22, 0.3) for k in range(4)])

# 3 希腊（4）：里拉琴 B♭ 和弦 + 双管 D5（♪）→ F5（附点四分）
perform_era(10, [(0, lambda: perform_lyre("Bb2"), 0.4, -0.25), (0.04, lambda: perform_lyre("F3"), 0.45, -0.2), (0.08, lambda: perform_lyre("Bb3"), 0.35, -0.15),
         (2.5, lambda: perform_lyre("D4", 0.5), 0.35, -0.2), (3.5, lambda: perform_lyre("F2", 0.6), 0.5, -0.2),
         (0, lambda: perform_aulos("D5", B8), 0.55, 0.05), (1, lambda: perform_aulos("F5", 3 * B8), 0.5, 0.05),
         (1, lambda: perform_aulos("F6", 3 * B8), 0.15, 0.05), (0, perform_tambourine, 0.12, 0.3), (2, perform_tambourine, 0.08, 0.3)])

# 4 罗马（4）：号角动机 C5–D5–A4，和弦 F→C→Dm + 战鼓
perform_era(14, [(0, lambda: perform_brass("C5", B8 * 0.9), 0.45, 0.05), (0, lambda: perform_brass("F3", B8 * 0.9), 0.25, -0.15), (0, lambda: perform_brass("A3", B8 * 0.9), 0.25, 0.15),
         (1, lambda: perform_brass("D5", B8 * 1.4), 0.4, 0.05), (1, lambda: perform_brass("G3", B8 * 1.4), 0.25, -0.15), (1, lambda: perform_brass("C3", B8 * 1.8), 0.3, 0),
         (2.5, lambda: perform_brass("A4", B8 * 1.4), 0.4, 0.05), (2.5, lambda: perform_brass("F3", B8 * 1.4), 0.25, -0.15), (3, lambda: perform_brass("D3", B8), 0.3, 0),
         (0, perform_war_drum, 1.1, -0.05), (1.5, perform_war_drum, 0.9, -0.05), (2, perform_war_drum, 1.1, -0.05)])

# 5 哥特（4）：管风琴 Dm → Gm/D，D2 持续踏板
perform_era(18, [(0, lambda: perform_organ("D3", 2 * B8), 0.3, -0.1), (0, lambda: perform_organ("A3", 2 * B8), 0.25, 0.1), (0, lambda: perform_organ("D4", 2 * B8), 0.25, -0.05),
         (0, lambda: perform_organ("F4", 2 * B8), 0.3, 0.05), (0.5, lambda: perform_organ("A5", 1.5 * B8), 0.12, 0),
         (2, lambda: perform_organ("D3", 2 * B8), 0.3, -0.1), (2, lambda: perform_organ("G3", 2 * B8), 0.3, 0.1), (2, lambda: perform_organ("Bb3", 2 * B8), 0.3, -0.05),
         (2, lambda: perform_organ("D4", 2 * B8), 0.2, 0.05), (2.5, lambda: perform_organ("Bb4", 1.5 * B8), 0.15, 0), (0, lambda: perform_organ("D2", 4 * B8), 0.18, 0)])

# 6 文艺复兴（4）：羽管键琴动机 B♭5–C6–G5，伴奏 Gm→F + 低音维奥尔 G2
perform_era(22, [(0, lambda: perform_harpsichord("Bb5"), 0.6, 0.1), (1, lambda: perform_harpsichord("C6"), 0.6, 0.1), (2, lambda: perform_harpsichord("G5", 0.7), 0.6, 0.1),
         (0, lambda: perform_harpsichord("G3"), 0.3, -0.2), (0.04, lambda: perform_harpsichord("Bb3"), 0.28, -0.15), (1, lambda: perform_harpsichord("D4"), 0.25, -0.15),
         (2, lambda: perform_harpsichord("F3"), 0.3, -0.2), (3, lambda: perform_harpsichord("A3"), 0.28, -0.15), (3, lambda: perform_harpsichord("C4"), 0.25, -0.1),
         (0, lambda: perform_viol("G2", 3.6 * B8), 0.35, -0.05)])

# 7 浮世绘（3）：筝走 D 都节音阶（D–E♭–G–A–B♭）+ 太鼓 + 拍子木
perform_era(26, [(0, perform_taiko, 1.2, -0.05), (1.5, perform_taiko, 1.0, -0.05),
         (0, lambda: perform_koto("D5"), 0.55, 0.15), (0.5, lambda: perform_koto("A4"), 0.45, 0.15), (0.75, lambda: perform_koto("Bb4"), 0.5, 0.15),
         (1, lambda: perform_koto("G4"), 0.45, 0.15), (1.5, lambda: perform_koto("A4"), 0.4, 0.15), (2, lambda: perform_koto("Eb5"), 0.5, 0.15),
         (2.25, lambda: perform_koto("D5"), 0.45, 0.15), (2.5, lambda: perform_koto("A4"), 0.45, 0.15),
         (0.5, perform_hyoshigi, 0.25, 0.3), (2, perform_hyoshigi, 0.2, 0.3)])

# 8 印象派（3）：柔和钢琴 A5–C6–G5，Fmaj7 → B♭ 低音 → Dm9 色彩
perform_era(29, [(0, lambda: perform_soft_piano("A5"), 0.55, 0.1), (0, lambda: perform_soft_piano("F3"), 0.35, -0.15), (0, lambda: perform_soft_piano("E4"), 0.3, -0.1),
         (0.5, lambda: perform_soft_piano("C5"), 0.3, 0), (1, lambda: perform_soft_piano("C6"), 0.55, 0.1), (1, lambda: perform_soft_piano("D5"), 0.3, 0),
         (1, lambda: perform_soft_piano("F4"), 0.3, -0.1), (1, lambda: perform_soft_piano("Bb2", 1.5), 0.55, -0.05),
         (2, lambda: perform_soft_piano("G5"), 0.55, 0.1), (2, lambda: perform_soft_piano("D3"), 0.3, -0.1), (2.5, lambda: perform_soft_piano("E5"), 0.25, 0.1)])

# 9 梵高（3）：D2 低音拨弦律动 + 高处零散亮拨弦 + 上扬风声
perform_era(32, [(0, lambda: perform_pizz("D2", 0.3), 0.7, -0.05), (0.5, lambda: perform_pizz("A2"), 0.45, -0.1), (1, lambda: perform_pizz("D2"), 0.6, -0.05),
         (1.75, lambda: perform_pizz("C3"), 0.5, -0.05), (2, lambda: perform_pizz("D2"), 0.6, -0.05), (2.5, lambda: perform_pizz("A2", 0.4), 0.5, -0.05),
         (0.25, lambda: perform_pizz("A5"), 0.4, 0.15), (1, lambda: perform_pizz("F5"), 0.35, 0.1), (1.75, lambda: perform_pizz("D6"), 0.3, 0.15),
         (2.5, lambda: perform_pizz("E5"), 0.4, 0.15),
         (1.5, lambda: perform_swirl(0.4), 0.06, 0.2)])

# 10 新艺术（3）：钢片琴动机 D5–E5–A4，低音 B♭→C→Dm
perform_era(35, [(0, lambda: perform_celesta("D5"), 0.6, 0.1), (0.2, lambda: perform_celesta("D6"), 0.2, 0.15), (1, lambda: perform_celesta("E5"), 0.6, 0.1),
         (2, lambda: perform_celesta("A4"), 0.6, 0.1),
         (0, lambda: perform_pizz("Bb2", 0.5), 0.5, -0.05), (1, lambda: perform_pizz("C3", 0.5), 0.45, -0.05), (1, lambda: perform_celesta("E3", 0.5), 0.3, -0.15),
         (1, lambda: perform_celesta("G3", 0.5), 0.25, -0.1), (2, lambda: perform_pizz("D3", 0.5), 0.45, -0.05), (2, lambda: perform_celesta("D4"), 0.25, -0.1),
         (2, lambda: perform_celesta("F4"), 0.25, -0.15), (2, lambda: perform_celesta("A4"), 0.2, 0), (0, lambda: perform_tambourine(), 0.06, 0.3)])

# 11 立体主义（2）：刻意不协和的碎片和弦 D–G♯–C♯ → E♭–A–B♭–E
perform_era(38, [(0, lambda: perform_soft_piano("D2", 0.5), 0.5, -0.1), (0, lambda: perform_soft_piano("D3", 0.5), 0.45, -0.1), (0, lambda: perform_soft_piano("G#3", 0.5), 0.4, 0),
         (0, lambda: perform_soft_piano("C#5", 0.5), 0.45, 0.15),
         (1, lambda: perform_soft_piano("Eb4", 0.3), 0.4, -0.1), (1, lambda: perform_soft_piano("A4", 0.3), 0.45, 0.1), (1, lambda: perform_soft_piano("Bb4", 0.3), 0.35, 0),
         (1, lambda: perform_soft_piano("E5", 0.3), 0.5, 0.15)])

# 12 包豪斯（2）：D 八度叠置 → F/A → D，十六分机械滴答
perform_era(40, [(0, lambda sample_value=sample_value: perform_blip(sample_value), 0.3, input_path) for sample_value, input_path in (("D2", 0), ("D3", -0.1), ("D4", 0.1), ("D5", -0.05), ("D6", 0.05))]
    + [(1, lambda: perform_blip("F5"), 0.45, 0.1), (1, lambda: perform_blip("A5"), 0.3, 0.1), (1, lambda: perform_blip("A6"), 0.2, -0.1), (1.5, lambda: perform_blip("D5"), 0.45, 0)]
    + [(k * 0.5, perform_tick, 0.25, 0.3) for k in range(4)])

# 13 波普（2）：底鼓 + 反拍拍手 + 卡通短音
perform_era(42, [(0, lambda: perform_kick(140, 45), 1.1, 0), (0, lambda: perform_blip("D4", 0.2), 0.25, -0.1), (0, lambda: perform_blip("F4", 0.2), 0.25, 0.1),
         (1, perform_clap, 0.45, 0.1), (0.5, lambda: perform_chip("D4", 0.09), 0.18, -0.1), (0.5, lambda: perform_chip("F4", 0.09), 0.15, 0.1),
         (0.5, lambda: perform_chip("C5", 0.09), 0.12, 0), (1.5, lambda: perform_chip("D6", 0.05), 0.15, 0.2)]
    + [(k * 0.5, perform_hat, 0.3, 0.25) for k in range(4)])

# 14 像素（1）：方波 F 大三琶音（三十二分）+ 方波低音
perform_era(44, [(0, lambda: perform_chip("F3", 0.2), 0.3, 0), (0, lambda: perform_chip("F6", 0.055), 0.18, 0.1), (0.25, lambda: perform_chip("A6", 0.05), 0.15, 0.1),
         (0.5, lambda: perform_chip("C7", 0.055), 0.12, 0.1), (0.75, lambda: perform_chip("F6", 0.05), 0.15, 0.1), (0, lambda: perform_kick(120, 50, 0.08), 0.6, 0)])

# 15 光追（1）：超级锯齿 B♭ 和弦，玻璃感
perform_era(45, [(0, lambda sample_value=sample_value: perform_supersaw(sample_value, B8 * 1.1), 0.18, input_path) for sample_value, input_path in (("Bb3", -0.2), ("D4", 0.2), ("F4", -0.1), ("Bb4", 0.1))]
    + [(0.5, lambda: perform_supersaw("D5", B8 * 0.6), 0.15, 0.15), (0.5, lambda: perform_supersaw("F3", B8 * 0.8), 0.15, -0.1),
       (0, lambda: perform_kick(130, 50, 0.1), 0.7, 0)])

# 16 孟菲斯（1）：C 大三持续和弦挂过段尾 + C 低音 + 底鼓；猫跳上桌的上滑音
perform_era(46, [(0, lambda: perform_kick(150, 46), 1.0, 0), (0, lambda: perform_sub_bass("C2", 0.24), 0.35, 0)]
    + [(0, lambda sample_value=sample_value: perform_supersaw(sample_value, 0.42), green_channel, input_path) for sample_value, green_channel, input_path in (("C3", 0.12, -0.15), ("G3", 0.1, 0.15), ("C5", 0.16, -0.05), ("E5", 0.16, 0.1), ("G5", 0.1, 0))])
append(perform_boing(), 11.01, 0.35, 0.0)

# 17 2026（9）：128BPM 浩室——四拍底鼓、反拍开镲、D 锯齿低音、D 大调 add9 拨奏（结尾转到同名大调）
append(perform_sub_bass("D2", perform_tt(56) - perform_tt(47)), perform_tt(47), 0.4, 0)
for total_count in (48, 50, 52, 54):
    append(perform_kick(150, 46, 0.2), perform_tt(total_count), 1.0, 0)
for total_count in (49, 51, 53, 55):
    append(perform_hat(True), perform_tt(total_count), 0.3, 0.2)
lead_value = [(48, "F#5"), (49, "A5"), (50, "D6"), (51, "E6"), (52, "F#6"), (53, "E6"), (54, "D6"), (55, "B5"), (55.5, "A5")]
for total_count, sample_value in lead_value:
    append(perform_pluck2026(sample_value), perform_tt(total_count), 0.5, 0.1)
arp_value = ["A4", "D5", "F#4", "E5", "D4", "A4", "B4", "F#4"]
for k in range(18):
    total_count = 47 + k * 0.5
    if total_count >= 56:
        break
    append(perform_pluck2026(arp_value[k % len(arp_value)], 0.15), perform_tt(total_count), 0.22, -0.15)
for sample_value, a, b in (("F#3", 50.5, 53.5), ("A3", 50.5, 53.5), ("E4", 51.5, 53.5), ("D3", 53.5, 54.3), ("F#3", 54.5, 56), ("A3", 54.5, 56), ("B3", 54.5, 56)):
    append(perform_pad(sample_value, perform_tt(b) - perform_tt(a)), perform_tt(a), 0.07, -0.2 if sample_value < "C" else 0.2)

# 18 音效段
append(perform_tink(), 13.158, 0.12, 0.1)
append(perform_swipe(), 13.17, 0.05, 0.2)
append(perform_slide_whistle(), 13.29, 0.16, 0.0)
append(perform_crash(), 13.624, 0.55, 0.0)
append(perform_meow(), 14.12, 0.55, 0.0)
append(perform_end_thump(88), 14.561, 0.2, 0)
append(perform_end_thump(90), 14.796, 0.25, 0)
append(perform_pluck(perform_hz("D2"), 0.3, [1, 0.5, 0.35, 0.15, 0.08], d0=4, slope=0.5, noise=0.03), 14.92, 0.6, 0)   # 收在主音


# ---------------------------------------------------------------- 混音：小空间混响 → 逐段响度对齐 → 整体 LUFS/峰值
def perform_reverb(sample_value, seed_value):
    r = np.random.default_rng(seed_value); d = 0.5; elapsed_seconds = perform_tvec(d)
    inline_run = r.standard_normal(len(elapsed_seconds)) * np.exp(-elapsed_seconds / 0.09)
    inline_run = perform_lp(inline_run, 6000); inline_run[: int(0.012 * SR)] = 0      # 12ms 预延迟，起音更软
    return ss.fftconvolve(sample_value, inline_run)[: len(sample_value)] / np.sqrt((inline_run ** 2).sum())


wetL_value, wetR_value = perform_reverb(L, 1), perform_reverb(R, 2)
L = L + 0.09 * wetL_value; R = R + 0.09 * wetR_value


def perform_kweight(sample_value):
    b1_value = [1.53512485958697, -2.69169618940638, 1.19839281085285]; a1_value = [1, -1.69065929318241, 0.73248077421585]
    b2_value = [1.0, -2.0, 1.0]; a2_value = [1, -1.99004745483398, 0.99007225036621]
    return ss.lfilter(b2_value, a2_value, ss.lfilter(b1_value, a1_value, sample_value))


def perform_seg_loud(kl_value, kr_value, s, caught_error):
    return -0.691 + 10 * np.log10(np.mean(kl_value[s:caught_error] ** 2 + kr_value[s:caught_error] ** 2) + 1e-12)


def lufs(item_length, r):                  # BS.1770-4 积分响度（400ms 块，绝对+相对门限）
    kl_value, kr_value = perform_kweight(item_length), perform_kweight(r); blk_value, hop_value = int(0.4 * SR), int(0.1 * SR)
    depth_value = np.array([np.mean(kl_value[cursor:cursor + blk_value] ** 2 + kr_value[cursor:cursor + blk_value] ** 2) for cursor in range(0, len(item_length) - blk_value + 1, hop_value)])
    lk_value = -0.691 + 10 * np.log10(depth_value + 1e-12); depth_value = depth_value[lk_value > -70]
    rel_value = -0.691 + 10 * np.log10(depth_value.mean()) - 10
    depth_value = depth_value[-0.691 + 10 * np.log10(depth_value) > rel_value]
    return -0.691 + 10 * np.log10(depth_value.mean())


# 逐段目标响度（K 加权、不加门限）。有参考片时填它逐段量出来的值；这里是示例：音乐段统一 -14，音效段略低。
edge_entries = [0] + [perform_tt(total_count) for total_count in (6, 10, 14, 18, 22, 26, 29, 32, 35, 38, 40, 42, 44, 45, 46, 47)] + [13.155, 13.624, 14.1, N / SR]
target = [-14.0] * 17 + [-18.0, -17.5, -16.0]
slot_index = [int(round(sample_value * SR)) for sample_value in edge_entries]
# 低频暖底：按段的和弦根音铺柔和三角波 + 250Hz 低通，电平按「低频地板比段响度」的相对值自动定（这里示例统一低 18dB）。
BED_ROOT = ["D2", "D2", "A#1", "F2", "D2", "G2", "D2", "F2", "D2", "A#1", "D2", "D2", "D2", "F2", "A#1", "C2", "D2", None, None, None]
LOW_FLOOR_ORIG = [elapsed_seconds - 18 for elapsed_seconds in target[:17]] + [None, None, None]
_sos_low_value = ss.butter(4, [40, 220], "band", fs=SR, output="sos")


def _perform_floor(sample_value):                   # 50ms 窗 RMS 的最小值（只看持续部分，不看鼓的击头）
    width_extent = 2400
    return min(20 * np.log10(np.sqrt(np.mean(sample_value[k:k + width_extent] ** 2)) + 1e-12) for k in range(0, max(1, len(sample_value) - width_extent), 1200))


_kl_value, _kr_value = perform_kweight(L), perform_kweight(R)
_lower_bound = ss.sosfilt(_sos_low_value, (L + R) / 2)
for cursor in range(len(target)):
    if BED_ROOT[cursor] is None:
        continue
    first_span, s1_value = slot_index[cursor], slot_index[cursor + 1]
    want_value = perform_seg_loud(_kl_value, _kr_value, first_span, s1_value) + (LOW_FLOOR_ORIG[cursor] - target[cursor])
    have_value = _perform_floor(_lower_bound[first_span + 1200:s1_value])
    if want_value - have_value < 1.5:
        continue
    total_count = s1_value - first_span + int(0.04 * SR); f = perform_hz(BED_ROOT[cursor])
    tri_value = perform_additive(f, [1, 0, 1 / 9, 0, 1 / 25], total_count / SR) + 0.35 * np.sin(2 * np.pi * f / 2 * np.arange(total_count) / SR)
    tri_value = perform_lp(tri_value, 250)
    env_value = np.ones(total_count); stream_handle = int(0.02 * SR); env_value[:stream_handle] = np.linspace(0, 1, stream_handle); env_value[-stream_handle:] = np.linspace(1, 0, stream_handle)
    depth_value = tri_value * env_value; zl_value = ss.sosfilt(_sos_low_value, depth_value)
    amp_value = np.sqrt(max(10 ** (want_value / 10) - 10 ** (have_value / 10), 0)) / (np.sqrt(np.mean(zl_value[stream_handle:-stream_handle] ** 2)) + 1e-12)
    caught_error = min(N, first_span + total_count)
    L[first_span:caught_error] += depth_value[: caught_error - first_span] * amp_value * 0.707; R[first_span:caught_error] += depth_value[: caught_error - first_span] * amp_value * 0.707

# 中高频（2–6kHz）动态 EQ：把每段 2–6kHz 的相对电平推到目标值（上限 +12dB）。有参考片时填参考值；这里示例统一比段响度低 15dB
MID_ORIG = [elapsed_seconds - 15 for elapsed_seconds in target]
_sos_mid_value = ss.butter(2, [2000, 6000], "band", fs=SR, output="sos")
_kl_value, _kr_value = perform_kweight(L), perform_kweight(R)
_midL_value, _midR_value = ss.sosfiltfilt(_sos_mid_value, L), ss.sosfiltfilt(_sos_mid_value, R)
_green_channel = np.zeros(N)
for cursor in range(len(target)):
    first_span, s1_value = slot_index[cursor], slot_index[cursor + 1]
    want_value = perform_seg_loud(_kl_value, _kr_value, first_span, s1_value) + (MID_ORIG[cursor] - target[cursor])
    have_value = 20 * np.log10(np.sqrt(np.mean(((_midL_value + _midR_value) / 2)[first_span:s1_value] ** 2)) + 1e-12)
    _green_channel[first_span:s1_value] = 10 ** (np.clip(want_value - have_value, 0, 12) / 20) - 1
_green_channel = np.convolve(_green_channel, np.ones(960) / 960, mode="same")
L = L + _green_channel * _midL_value; R = R + _green_channel * _midR_value

# >6kHz 的「空气」（高次泛音 + 噪声颗粒）：按「高频比段响度」的相对值补一层高通噪声。示例统一低 24dB
HF_ORIG = [elapsed_seconds - 24 for elapsed_seconds in target]
_sos_hf_value = ss.butter(4, 6000, "high", fs=SR, output="sos")
_kl_value, _kr_value = perform_kweight(L), perform_kweight(R)
_hf_value = ss.sosfilt(_sos_hf_value, (L + R) / 2)
for cursor in range(len(target)):
    first_span, s1_value = slot_index[cursor], slot_index[cursor + 1]
    want_value = perform_seg_loud(_kl_value, _kr_value, first_span, s1_value) + (HF_ORIG[cursor] - target[cursor])
    have_value = 20 * np.log10(np.sqrt(np.mean(_hf_value[first_span:s1_value] ** 2)) + 1e-12)
    if want_value - have_value > 2:
        need_value = np.sqrt(max(10 ** (want_value / 10) - 10 ** (have_value / 10), 0))
        fade_value = int(0.01 * SR); total_count = s1_value - first_span
        env_value = np.ones(total_count); env_value[:fade_value] = np.linspace(0, 1, fade_value); env_value[-fade_value:] = np.linspace(1, 0, fade_value)
        for chapter_record, seed_value in ((L, 11 + cursor), (R, 41 + cursor)):
            depth_value = ss.sosfilt(_sos_hf_value, np.random.default_rng(seed_value).standard_normal(total_count + 2000))[2000:]
            chapter_record[first_span:s1_value] += depth_value / np.sqrt(np.mean(depth_value ** 2)) * need_value * env_value

gain_db_value = np.zeros(len(target))
for _ in range(4):               # 迭代：尾音跨段会互相影响
    green_channel = np.zeros(N)
    for cursor in range(len(target)):
        green_channel[slot_index[cursor]:slot_index[cursor + 1]] = gain_db_value[cursor]
    green_channel = np.convolve(green_channel, np.ones(480) / 480, mode="same")      # 10ms 平滑，避免拉链声
    glossary_map, gr_value = L * 10 ** (green_channel / 20), R * 10 ** (green_channel / 20)
    kl_value, kr_value = perform_kweight(glossary_map), perform_kweight(gr_value)
    for cursor in range(len(target)):
        gain_db_value[cursor] += target[cursor] - perform_seg_loud(kl_value, kr_value, slot_index[cursor], slot_index[cursor + 1])
L, R = glossary_map, gr_value
print("逐段增益(dB):", np.round(gain_db_value, 1))


def true_peak(item_length, r):
    return 20 * np.log10(max(np.abs(ss.resample_poly(item_length, 4, 1)).max(), np.abs(ss.resample_poly(r, 4, 1)).max()))


def perform_soft_limit(sample_value, ceil_value):         # 只压超过门限的瞬态（前视 1ms 的峰值包络）
    from scipy.ndimage import maximum_filter1d
    env_value = maximum_filter1d(np.abs(sample_value), 96)
    gr_value = np.minimum(1, ceil_value / np.maximum(env_value, 1e-9))
    gr_value = np.convolve(gr_value, np.ones(96) / 96, mode="same")
    return sample_value * gr_value


# 模拟流媒体 AAC 的 16kHz 截止（要和参考片质感一致时用，不需要可以删掉）
_sos16_value = ss.butter(10, 15800, "low", fs=SR, output="sos")
L, R = ss.sosfiltfilt(_sos16_value, L), ss.sosfiltfilt(_sos16_value, R)

TARGET_LUFS, TARGET_TP = -14.0, -1.5
for _ in range(3):
    current_item = lufs(L, R); k = 10 ** ((TARGET_LUFS - current_item) / 20); L *= k; R *= k
    ceil_value = 10 ** ((TARGET_TP - 0.05) / 20)
    L, R = perform_soft_limit(L, ceil_value), perform_soft_limit(R, ceil_value)

y = np.stack([L, R], 1)
sf.write(OUT, y, SR, subtype="PCM_24")
print(f"写出 {OUT.name}: {len(y)} 样本 = {len(y) / SR:.4f}s, 积分响度 {lufs(L, R):.2f} LUFS, 真峰 {true_peak(L, R):.2f} dBTP")
