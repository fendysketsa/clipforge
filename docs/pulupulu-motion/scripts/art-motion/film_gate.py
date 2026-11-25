# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""film_gate.py — read a finished mp4 and measure the "page-flipping PPT" feel. deliver.py calls it before delivery, and it can also be run on its own.

Usage:
  uv run film_gate.py final.mp4 [--json] [--vertical auto|yes|no] [--sub-band 0.15]
                      [--template demo.mp4] [--no-template]

Exit codes: red 2; yellow and green 0; unreadable file 1.
Depends only on ffmpeg/ffprobe and opencv, not on the art-motion engine, so a finished cut from any source can be measured.

Two gates. First: share of fast-motion frames (share of adjacent frame pairs whose mean grayscale difference is >=9 within a shot, 12fps, 320 wide grayscale,
with the bottom subtitle band masked; cut-like frames and whole dissolve windows are excluded, so even a fast transition doesn't count). < 0.035 red, < 0.06 yellow.
Calibration (2026-10-09): 13 films the author himself rated (9 accepted, 4 rejected); it is the only metric that on its own separates the two groups cleanly with margin
on both sides of the threshold — the lowest accepted is 0.068, the highest rejected is 0.021; any frame-diff threshold between 6 and 13 separates them.
The sample is only 13 films, so read it as "no counterexample among these 13", not as proven.

The second gate is factual, not calibrated on taste: near-solid-colour empty screens mid-film. After dropping the first and last 0.5s and the transition windows (the frame
either side of a cut, whole dissolve spans), a frame where fewer than 0.2% of pixels have gradient >24 (the frame has essentially no edge or texture — also 12fps, 320 wide
grayscale, subtitle band masked) counts as blank; >=0.3s continuous is red, and the report gives the time code of every span. Judged by edges, not by colour: the fine lines and
formulas on a black 3b1b background and strokes on a whiteboard are edges and are not false-flagged; the "95% of the frame is one colour" colour-based test flags accepted
whiteboard films as 3-second blank screens in the calibration set, so it isn't used. None of the 32 films in the calibration data (including the 13 the author rated, 9 accepted)
ever showed 2 consecutive blank frames. The short-clip downgrade does not apply to this gate.

Third gate: share of screen time on a blue-purple ground (the author's words: "we need to avoid those blue/purple gradient junk palettes, that's very AI slop").
2fps, 160 wide RGB; a pixel is blue-purple if hue 225°–300°, saturation >=0.30, value 0.06–0.90; a frame with >=30% such pixels is a blue-purple frame.
Blue-purple frame share >=0.30 red, >=0.12 yellow. Calibration (2026-10-10): of 88 films, the 9 the author accepted top out at 0.10 (his journey-through-paintings one),
most are 0; the films he rejected or wanted neither of run 0.46–1.00 (the deep-purple starfield plus white-shell robot one is 0.94). Flat navy (hue around 210°) doesn't count.
When the subject itself calls for blue-purple (user-specified cyberpunk purple, a Van Gogh Starry Night style frame), use --allow-blue-purple "reason" to downgrade it to yellow;
the reason is written verbatim into the facts section of the delivery note.

The other metrics are report-only (yellow at most, never blocking). The stillness metrics (still-frame share, longest continuous still, longest event-free gap) invert good films
that go "hold -> burst -> hold", so they must never become gates; yellow just means "go look at that stretch".

What it can't catch: a PPT that forces one push-in per page ("push-in count" yellow tells you to look), front-loaded and back-loaded rhythm (watch the worst 30s window),
page frames with small images on a cream ground, and not being able to explain it. Fast frames don't distinguish fast from slow: a ~1s 20% slow push and a 0.28s fast push score
about the same number of fast frames (measured on three frames of the Nobel short on 2026-10-12), so you don't need to speed your camera moves up to pass. The "go look" yellow
items and the independent review still have to be done.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

FPS = 12            # analysis frame rate
WIDTH = 320         # analysis width (320 wide for vertical too)
SAMPLE_FPS = 2      # sampling rate for area-type metrics
# The all-styles demo reel ships with the Release, not in the repo; put it under assets/ to compare against a borrowed demo composition, and skip this item when it's absent
DEFAULT_TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "all-styles-sample.mp4")

# ---------------------------------------------------------------- threshold table
# Only gate=True metrics raise a red light and make the script exit non-zero; the rest are report-only (yellow at most, 'info' lights nothing).
# Direction 'high_bad': the bigger the more suspicious; 'low_bad': the smaller the more suspicious; 'info': just a number, no judgement.
# Calibration: 2026-10-09 on the 13 films the author rated himself (9 positive, 4 negative), see the file header. Don't casually change thresholds: if you do, recalibrate on new rated films.
# Only metrics that separate positives and negatives cleanly on their own with margin either side (fast_ratio), and factual hard faults that need no calibration (blank_run_s), become gates.
# Yellow lines are empirical lines read off the same films; the sample is too small to be a verdict, so they only say "go look at that stretch".
METRICS = {
    # key: (name, direction, yellow line, red line, is_gate, unit)
    "fast_ratio":         ("fast-motion frame share", "low_bad", 0.06, 0.035, True, ""),
    "blank_run_s":        ("near-solid-colour blank screens mid-film (longest run)", "high_bad", None, 0.3, True, "s"),
    "blue_purple_share":  ("blue-purple ground screen share", "high_bad", 0.12, 0.30, True, ""),
    "fast_ratio_worst_window": ("fast-motion share in the worst 30s window", "low_bad", 0.02, None, False, ""),
    "top10_share":        ("motion concentration (top 10% of frames' share of motion)", "info", None, None, False, ""),
    "drift_ratio":        ("drifting frame share", "high_bad", 0.65, None, False, ""),
    "still_ratio":        ("still frame share (stillness alone isn't bad)", "info", None, None, False, ""),
    "longest_still_s":    ("longest continuous still", "high_bad", 6.0, None, False, "s"),
    "event_rate":         ("visual event density", "low_bad", 2.0, None, False, "/10s"),
    "max_event_gap_s":    ("longest event-free gap", "high_bad", 15.0, None, False, "s"),
    "dead_bg":            ("dead background (unchanged within a shot after removing camera motion)", "high_bad", 0.80, None, False, ""),
    "dead_flat":          ("dead and flat empty ground", "high_bad", 0.50, None, False, ""),
    "flat_area":          ("flat ground/empty ground area", "info", None, None, False, ""),
    "flat_light":         ("light empty ground area (cream/white ground)", "high_bad", 0.35, None, False, ""),
    "page_frame_share":   ("fixed page-frame screen share", "high_bad", 0.30, None, False, ""),
    "slow_zoom_share":    ("uniform slow zoom shot screen share", "high_bad", 0.70, None, False, ""),
    "push_in_per_min":    ("push-in count (lower bound)", "high_bad", 8.0, None, False, "/min"),
    "fast_push_per_min":  ("of which pushes completed within 0.5s", "info", None, None, False, "/min"),
    "push_in_share":      ("push-ins as a share of push/pull events", "info", None, None, False, ""),
    "slow_cam_share":     ("slow drifting camera shot screen share", "info", None, None, False, ""),
    "dissolve_share":     ("dissolves as a share of transitions", "high_bad", 0.60, None, False, ""),
    "local_fade_ratio":   ("in-place fades as a share of changed frames", "info", None, None, False, ""),
    "subject_box":        ("largest subject block's share of the frame", "info", None, None, False, ""),
    "template_sim_share": ("screen share resembling the demo composition", "high_bad", 0.30, None, False, ""),
}


# ---------------------------------------------------------------- frame reading
def probe_result(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", path])
    inner_cursor = json.loads(out)
    s = inner_cursor["streams"][0]
    return int(s["width"]), int(s["height"]), float(inner_cursor["format"].get("duration", 0) or 0)


def decode_gray_frames(path, fps=FPS, width=WIDTH, limit=None):
    W, H, span_seconds = probe_result(path)
    h = int(round(H * width / W / 2) * 2)
    subcommand_name = ["ffmpeg", "-v", "error"] + (["-t", str(limit)] if limit else []) + ["-i", path, "-vf",
           f"fps={fps},scale={width}:{h}:flags=area", "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    raw_payload = subprocess.check_output(subcommand_name)
    n = len(raw_payload) // (width * h)
    F = np.frombuffer(raw_payload[: n * width * h], np.uint8).reshape(n, h, width)
    return F, (W, H, span_seconds)


# ---------------------------------------------------------------- global camera motion
def perform_pair_transform(a, b):
    """Similarity transform a->b (LK tracking + RANSAC). Returns (M 2x3, inlier count, inlier ratio) or (None,0,0)."""
    pt_entries = cv2.goodFeaturesToTrack(a, maxCorners=300, qualityLevel=0.01, minDistance=6, blockSize=5)
    if pt_entries is None or len(pt_entries) < 15:
        return None, 0, 0.0
    later_value, st_value, _ignored = cv2.calcOpticalFlowPyrLK(a, b, pt_entries, None, winSize=(21, 21), maxLevel=3)
    success_flag = st_value.ravel() == 1
    if success_flag.sum() < 12:
        return None, 0, 0.0
    first_sample, p1_value = pt_entries[success_flag].reshape(-1, 2), later_value[success_flag].reshape(-1, 2)
    M, inline_markup = cv2.estimateAffinePartial2D(first_sample, p1_value, method=cv2.RANSAC, ransacReprojThreshold=1.0)
    if M is None:
        return None, 0, 0.0
    ni_value = int(inline_markup.sum())
    return M, ni_value, ni_value / len(pt_entries)


def perform_cam_speed(M, w, h, fps):
    """Mean displacement of the transform over a grid of points, converted to "screen widths per second"."""
    if M is None:
        return 0.0
    x_samples, y_samples = np.meshgrid(np.linspace(0, w, 7), np.linspace(0, h, 7))
    P = np.stack([x_samples.ravel(), y_samples.ravel(), np.ones(x_samples.size)], 1)
    Q = P @ M.T
    return float(np.hypot(*(Q - P[:, :2]).T).mean() / w * fps)


def perform_to3(M):
    return np.vstack([M, [0, 0, 1]]) if M is not None else np.eye(3)


# ---------------------------------------------------------------- main analysis
def analyze(path, sub_band=None, vertical="auto", template=None, verbose_value=False):
    F, (W0, H0, span_seconds) = decode_gray_frames(path)
    vert_flag = (H0 > W0) if vertical == "auto" else (vertical == "yes")
    if sub_band is None:
        sub_band = 0.18 if vert_flag else 0.15
    n, h, w = F.shape
    hc_value = int(round(h * (1 - sub_band)))
    F = np.ascontiguousarray(F[:, :hc_value])          # mask the bottom subtitle band
    h = hc_value
    if n < 4:
        raise RuntimeError("too few frames to analyze")
    F16 = F.astype(np.int16)

    # --- per frame pair: frame diff, camera transform, residual after compensation, brightness histogram
    d = np.zeros(n - 1); loc = np.zeros(n - 1); spd = np.zeros(n - 1); zr = np.zeros(n - 1)
    fade_px = np.zeros(n - 1)
    M_entries = []
    for i in range(n - 1):
        a, b = F[i], F[i + 1]
        diff = np.abs(F16[i + 1] - F16[i])
        d[i] = diff.mean()
        moved_value, wa_value = False, None
        if d[i] < 0.05:                          # identical: skip the estimate
            M_entries.append(None); loc[i] = d[i]; fade_px[i] = -1; continue
        M, ni_value, inline_run = perform_pair_transform(a, b)
        if M is not None and ni_value >= 20 and inline_run >= 0.35:
            s = float(np.hypot(M[0, 0], M[1, 0]))
            moved_value = abs(np.log(s)) > 1e-4 or abs(M[0, 2]) > 0.05 or abs(M[1, 2]) > 0.05
            if moved_value:
                wa_value = cv2.warpAffine(a, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                loc[i] = np.abs(F16[i + 1] - wa_value.astype(np.int16)).mean()
            else:
                loc[i] = d[i]
            spd[i] = perform_cam_speed(M, w, h, FPS)
            zr[i] = np.log(s)
            M_entries.append(M)
        else:
            loc[i] = d[i]; M_entries.append(None)
        # in-place fade: of the pixels that still change after compensating the camera, the share whose optical flow is almost 0 (not moving, only brightness changing)
        if d[i] > 0.3 and spd[i] < 0.05:
            base_folder = wa_value if (M_entries[-1] is not None and moved_value) else a
            chapter_record = np.abs(F16[i + 1] - base_folder.astype(np.int16)) > 10
            if chapter_record.mean() > 0.003:
                fl_value = cv2.calcOpticalFlowFarneback(base_folder, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mag_value = np.hypot(fl_value[..., 0], fl_value[..., 1])
                fade_px[i] = float((mag_value[chapter_record] < 0.5).mean())
            else:
                fade_px[i] = -1
        else:
            fade_px[i] = -1
    # --- hard cuts
    # cut_like: every frame where the whole frame jumps and camera motion can't explain it (including multi-frame tile/pixel/whip transitions) — excluded entirely when counting motion
    # cut: from consecutive cut_like frames only the first is kept, used to count cuts and split shots
    cut_like_value = np.zeros(n - 1, bool)
    for i in range(n - 1):
        lower_bound, upper_bound = max(0, i - 6), min(n - 1, i + 7)
        neighbour_count = np.concatenate([d[lower_bound:i], d[i + 1:upper_bound]])
        median_value = np.median(neighbour_count) if len(neighbour_count) else 0
        cut_like_value[i] = d[i] >= max(8.0, 3 * median_value + 2) and loc[i] >= 0.6 * d[i]
    cut = cut_like_value & ~np.concatenate([[False], cut_like_value[:-1]])

    # --- dissolves: large difference between the ends, gentle change at every middle frame, middle frames are linear blends of the two ends
    diss_value = []                               # (a, b, center)
    in_diss = np.zeros(n - 1, bool)
    cand_value = []
    for window_half_width in (2, 3, 5, 8, 12):            # half window 0.17s–1s
        for t in range(window_half_width, n - window_half_width):
            window_first_frame, window_last_frame = t - window_half_width, t + window_half_width
            if cut_like_value[window_first_frame:window_last_frame].any():
                continue
            segment_record = d[window_first_frame:window_last_frame]
            if segment_record.max() > 0.75 * segment_record.sum() or segment_record.sum() < 10:
                continue
            Dab_value = np.abs(F16[window_last_frame] - F16[window_first_frame])
            if Dab_value.mean() < 10 or (Dab_value > 20).mean() < 0.20:   # frame-level fade; a local fade of a title usually covers only a few percent
                continue
            cand_value.append((t, window_half_width))
    cand_set_value = {}
    for t, window_half_width in cand_value:
        window_first_frame, window_last_frame = t - window_half_width, t + window_half_width
        A = F16[window_first_frame].astype(np.float32); B = F16[window_last_frame].astype(np.float32)
        D = A - B; nd_value = float((D * D).sum()) + 1e-6
        res, alpha_entries = [], []
        for sort_key in range(window_first_frame + 1, window_last_frame):
            X = F16[sort_key].astype(np.float32) - B
            alpha_channel = float((X * D).sum() / nd_value)
            r = np.abs(X - alpha_channel * D).mean() / (np.abs(D).mean() + 1e-6)
            res.append(r); alpha_entries.append(alpha_channel)
        res = np.array(res); alpha_entries = np.array(alpha_entries)
        mono_value = np.all(np.diff(alpha_entries) <= 0.08)
        mid = (alpha_entries > 0.15) & (alpha_entries < 0.85)        # middle frames that really are "two pictures stacked"
        if (mid.sum() >= 2 and res[mid].mean() < 0.22 and res.mean() < 0.25 and mono_value
                and alpha_entries[0] > 0.55 and alpha_entries[-1] < 0.45):
            k_entries = np.arange(window_first_frame + 1, window_last_frame)
            tc_value = int(k_entries[np.argmin(np.abs(alpha_entries - 0.5))])       # the frame where the blend coefficient crosses 0.5
            cand_set_value[(t, window_half_width)] = (window_first_frame, window_last_frame, res.mean(), float(np.abs(D).mean()), tc_value)
    # merge overlaps: take the one with the largest end-point difference first (the whole fade sits inside the window), then look at the residual
    for key in sorted(cand_set_value, key=lambda sort_key: (-round(cand_set_value[sort_key][3], 0), cand_set_value[sort_key][2])):
        window_first_frame, window_last_frame, _ignored, _ignored, tc_value = cand_set_value[key]
        if in_diss[window_first_frame:window_last_frame].any():
            continue
        in_diss[window_first_frame:window_last_frame] = True
        diss_value.append((window_first_frame, window_last_frame, tc_value))
    diss_value.sort()

    # --- shots
    bound_map = sorted(set([0] + [i + 1 for i in np.where(cut)[0]] + [character_code for _ignored, _ignored, character_code in diss_value] + [n]))
    shots = []
    for s, e in zip(bound_map[:-1], bound_map[1:]):
        if e - s >= 3:
            shots.append((s, e))
        elif shots:
            shots[-1] = (shots[-1][0], e)
    if not shots:
        shots = [(0, n)]
    tran_entries = cut_like_value | in_diss
    n_cut_value, n_diss_value = int(cut.sum()), len(diss_value)
    blank_runs = find_blank_frames(F, cut_like_value, in_diss)

    # --- motion distribution (transition frames excluded)
    mv_value = np.where(tran_entries, np.nan, d)
    good = ~np.isnan(mv_value)
    mvv_value = mv_value[good]
    # Frame-diff definition: mean absolute difference (0–255) at 12fps, 320 wide grayscale, subtitle band masked.
    # The fast threshold 9 comes from calibration (anything from 6 to 11 separates positives from negatives; 9 has the most margin);
    # the LK camera speed misses 0.3s-scale pushes and can't separate the groups on its own in the calibration, so it stays out of the "fast" definition.
    STILL, DRIFT_HI, FAST = 0.30, 3.0, 9.0
    still = mvv_value < STILL
    fast = mvv_value >= FAST
    drift_value = (~still) & (~fast) & (mvv_value < DRIFT_HI)
    srt_value = np.sort(mvv_value)[::-1]
    top10_value = srt_value[: max(1, len(srt_value) // 10)].sum() / max(srt_value.sum(), 1e-6)

    # longest continuous still (whole frame sequence, a transition breaks it)
    st_full_value = (d < STILL) & ~tran_entries
    longest = run = longest_at_value = 0
    for i, v in enumerate(st_full_value):
        run = run + 1 if v else 0
        if run > longest:
            longest, longest_at_value = run, i - run + 1

    # events: hard cuts, fades, fast-motion runs (consecutive fast frames count once)
    fast_full_value = np.zeros(n - 1, bool)
    fast_full_value[good] = fast
    ev_t_value = [i for i in np.where(cut)[0]] + [character_code for _ignored, _ignored, character_code in diss_value]
    earlier_value = False
    for i, v in enumerate(fast_full_value):
        if v and not earlier_value:
            ev_t_value.append(i)
        earlier_value = v
    ev_t_value = sorted(ev_t_value)
    sec_entries = n / FPS
    gap_entries = np.diff([0] + ev_t_value + [n - 1]) / FPS
    # merge events repeated within 0.3s
    ev_m_value = []
    for t in ev_t_value:
        if not ev_m_value or t - ev_m_value[-1] > 0.3 * FPS:
            ev_m_value.append(t)
    event_rate = len(ev_m_value) / sec_entries * 10

    # --- per shot: dead background, slow zoom curve
    dead_w_value, dead_flat_w_value, shot_w_value = [], [], []
    slow_zoom_dur_value, zoom_total_entries, slow_cam_dur_value = 0.0, [], 0.0
    for s, e in shots:
        L = e - s
        dur__entries = L / FPS
        # cumulative transform: A_k maps the shot's first frame into frame k
        A = [np.eye(3)]
        zc_value = [0.0]
        for sort_key in range(s, e - 1):
            A.append(perform_to3(M_entries[sort_key]) @ A[-1])
            zc_value.append(zc_value[-1] + (zr[sort_key] if M_entries[sort_key] is not None else 0.0))
        zc_value = np.array(zc_value)
        # slow zoom: 2%–25% total, monotone, spanning most of the shot, and no fast push
        if dur__entries >= 1.2:
            rate_entries = np.abs(zr[s:e - 1]) * FPS
            aggregate_count = abs(zc_value[-1] - zc_value[0])
            active_value = (rate_entries > 0.004).mean()
            sgn_value = np.sign(zr[s:e - 1]); sgn_value = sgn_value[sgn_value != 0]
            mono_value = abs(sgn_value.mean()) if len(sgn_value) else 0
            if 0.02 <= aggregate_count <= 0.25 and active_value >= 0.6 and mono_value >= 0.7 and np.percentile(rate_entries, 95) < 0.25:
                slow_zoom_dur_value += dur__entries
                zoom_total_entries.append(aggregate_count / dur__entries)
            span_length = spd[s:e - 1]
            if (span_length > 0.004).mean() >= 0.6 and np.percentile(span_length, 95) < 0.2:
                slow_cam_dur_value += dur__entries
        if dur__entries < 0.6:
            continue
        slot_index = np.unique(np.linspace(s, e - 1, min(L, 24)).astype(int))
        r = slot_index[len(slot_index) // 2]
        Ar_value = A[r - s]
        stack, valid_value = [], []
        ones = np.full((h, w), 255, np.uint8)
        for sort_key in slot_index:
            T = (Ar_value @ np.linalg.inv(A[sort_key - s]))[:2]
            stack.append(cv2.warpAffine(F[sort_key], T, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT))
            valid_value.append(cv2.warpAffine(ones, T, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 0)
        stack = np.array(stack, np.int16); valid_value = np.array(valid_value)
        vcount_value = valid_value.sum(0)
        success_flag = vcount_value >= 0.8 * len(slot_index)
        big = np.where(valid_value, stack, -1000).max(0); small = np.where(valid_value, stack, 1000).min(0)
        random_source = big - small
        dead = success_flag & (random_source <= 12)
        reference_value = F[r]
        gx_value = cv2.Sobel(reference_value, cv2.CV_32F, 1, 0); gy_value = cv2.Sobel(reference_value, cv2.CV_32F, 0, 1)
        flatpx_value = cv2.blur(np.hypot(gx_value, gy_value), (9, 9)) < FLAT_GRAD
        denom_value = max(success_flag.sum(), 1)
        dead_w_value.append(dead.sum() / denom_value); dead_flat_w_value.append((dead & flatpx_value).sum() / denom_value); shot_w_value.append(dur__entries)
    shot_w_value = np.array(shot_w_value)
    dead_bg = float(np.average(dead_w_value, weights=shot_w_value)) if len(shot_w_value) else 0.0
    dead_flat = float(np.average(dead_flat_w_value, weights=shot_w_value)) if len(shot_w_value) else 0.0
    slow_zoom_share = slow_zoom_dur_value / sec_entries

    # --- push-in events: continuous zoom-in within a shot (>0.4% per frame, 12fps, one dropped frame allowed) totalling >=3% counts once; one finished within 0.5s is a fast push.
    # Added on 2026-10-12 after the Nobel short (102s, about 48 pushes in code, all inward) was judged "too much, too fast, not smooth"; report-only, yellow tells you to look.
    # This is a lower bound: when live footage itself moves the camera transform can't be estimated and pushes go uncounted above (that film measured 20, about 12 per minute).
    def zoom_runs(mask, sign):
        ev_value, i = [], 0
        while i < len(mask):
            if mask[i]:
                inner_cursor = sort_key = i
                while sort_key + 1 < len(mask) and (mask[sort_key + 1] or (sort_key + 2 < len(mask) and mask[sort_key + 2])):
                    sort_key += 1
                    if mask[sort_key]:
                        inner_cursor = sort_key
                segment_record = zr[i:inner_cursor + 1] * sign
                if segment_record[segment_record > 0].sum() >= 0.03:
                    ev_value.append((i, inner_cursor))
                i = inner_cursor + 1
            else:
                i += 1
        return ev_value
    # only exclude the cut frame itself and dissolves: a fast push starting right after a cut gets swallowed whole by the "cut-like" window, and using trans would miss half of them
    zx_value = cut | in_diss
    push_in_value = zoom_runs((zr > 0.004) & ~zx_value, 1)
    pull_out_value = zoom_runs((zr < -0.004) & ~zx_value, -1)
    fast_push_value = sum(1 for a, b in push_in_value if (b - a + 1) / FPS <= 0.5)
    zoom_cv_value = float(np.std(zoom_total_entries) / (np.mean(zoom_total_entries) + 1e-9)) if len(zoom_total_entries) >= 3 else float("nan")

    # --- area-type metrics on sampled frames
    advance_size = max(1, FPS // SAMPLE_FPS)
    segment_index = np.arange(0, n, advance_size)
    if len(segment_index) > 240:
        segment_index = np.unique(np.linspace(0, n - 1, 240).astype(int))
    S = F[segment_index]
    flat_area, flat_light, subj_value = [], [], []
    BS = 8
    gh_value, gw_value = h // BS, w // BS
    cell_tex_value = np.zeros((len(segment_index), gh_value, gw_value), bool)
    for inner_cursor, fr in enumerate(S):
        gx_value = cv2.Sobel(fr, cv2.CV_32F, 1, 0); gy_value = cv2.Sobel(fr, cv2.CV_32F, 0, 1)
        g = np.hypot(gx_value, gy_value)[: gh_value * BS, : gw_value * BS].reshape(gh_value, BS, gw_value, BS).mean((1, 3))
        lum_value = fr[: gh_value * BS, : gw_value * BS].reshape(gh_value, BS, gw_value, BS).mean((1, 3))
        flat = (g < FLAT_GRAD).astype(np.uint8)
        nl_value, lab_value, stat_entries, _ignored = cv2.connectedComponentsWithStats(flat, connectivity=4)
        big = np.zeros_like(flat, bool)
        for character_code in range(1, nl_value):
            if stat_entries[character_code, cv2.CC_STAT_AREA] >= 0.03 * gh_value * gw_value:
                big |= lab_value == character_code
        flat_area.append(big.mean()); flat_light.append((big & (lum_value > 150)).mean())
        cell_tex_value[inner_cursor] = g >= PAGE_GRAD
        tex_value = (g >= TEX_GRAD).astype(np.uint8)
        if tex_value.sum() == 0:
            subj_value.append(0.0); continue
        cl_value = cv2.morphologyEx(tex_value, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        nl_value, lab_value, stat_entries, _ignored = cv2.connectedComponentsWithStats(cl_value, connectivity=8)
        sort_key = 1 + int(np.argmax(stat_entries[1:, cv2.CC_STAT_AREA]))
        comp_value = (lab_value == sort_key).astype(np.uint8)
        c_entries, _ignored = cv2.findContours(comp_value, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fill_value = np.zeros_like(comp_value); cv2.drawContours(fill_value, c_entries, -1, 1, -1)
        subj_value.append(float(fill_value.mean()))
    flat_area = np.array(flat_area)

    # --- fixed page frame: same screen position, textured (text/lines/logo), still appearing unchanged while the rest of the frame has changed a lot
    page_share_value = perform_page_frame(S, segment_index, cell_tex_value, BS, gh_value, gw_value, shots)

    # --- similarity to the demo composition
    tsim_share_value, tsim_max_value = float("nan"), float("nan")
    if template:
        tsim_share_value, tsim_max_value = perform_template_similarity(F, shots, template)

    # --- in-place fade share: of the changed frames, the mean share where local structure keeps its sign (brightness changes but nothing moves)
    chg_value = (~tran_entries) & (fade_px >= 0)
    lf_value = float(np.mean(fade_px[chg_value] > 0.7)) if chg_value.sum() > 5 else 0.0

    # front-loaded and back-loaded: fast-motion share in the worst 30 second window (half the length when the film is under 60s)
    win_value = int(min(30.0, sec_entries / 2) * FPS)
    fr_full_value = np.where(tran_entries, np.nan, fast_full_value.astype(float))
    worst, worst_t_value = float("nan"), None
    if win_value >= FPS * 4:
        for st0_value in range(0, n - 1 - win_value + 1, FPS):
            segment_record = fr_full_value[st0_value: st0_value + win_value]
            v = np.nanmean(segment_record) if np.isfinite(segment_record).any() else 0.0
            if not (worst == worst) or v < worst:
                worst, worst_t_value = float(v), st0_value / FPS
    by10_value = [round(float(np.nanmean(fr_full_value[sort_key: sort_key + 10 * FPS])), 3) if np.isfinite(fr_full_value[sort_key: sort_key + 10 * FPS]).any() else 0.0
            for sort_key in range(0, n - 1, 10 * FPS)]
    if os.environ.get("FILM_GATE_DUMP"):
        np.savez_compressed(os.environ["FILM_GATE_DUMP"], d=d, spd=spd, loc=loc, zr=zr, cut=cut, in_diss=in_diss, fade_px=fade_px)

    shot_len_value = np.array([(e - s) / FPS for s, e in shots])
    res = {
        "file": os.path.basename(path),
        "orientation": "vertical" if vert_flag else "horizontal",
        "duration_s": round(sec_entries, 2),
        "sub_band": sub_band,
        "shots": len(shots), "hard_cuts": n_cut_value, "dissolves": n_diss_value,
        "asl_s": round(float(shot_len_value.mean()), 2),
        "dissolve_share": round(n_diss_value / max(1, n_cut_value + n_diss_value), 3),
        "fast_ratio": round(float(fast.mean()), 4),
        "top10_share": round(float(top10_value), 3),
        "drift_ratio": round(float(drift_value.mean()), 3),
        "still_ratio": round(float(still.mean()), 3),
        "longest_still_s": round(longest / FPS, 2),
        "longest_still_start_s": round(longest_at_value / FPS, 2),
        "event_rate": round(event_rate, 2),
        "max_event_gap_s": round(float(gap_entries.max()), 2),
        "dead_bg": round(dead_bg, 3),
        "dead_flat": round(dead_flat, 3),
        "flat_area": round(float(flat_area.mean()), 3),
        "flat40_frames": round(float((flat_area > 0.4).mean()), 3),
        "page_frame_share": round(page_share_value, 3),
        "slow_zoom_share": round(float(slow_zoom_share), 3),
        "slow_cam_share": round(float(slow_cam_dur_value / sec_entries), 3),
        "zoom_curve_cv": round(zoom_cv_value, 3) if zoom_cv_value == zoom_cv_value else None,
        "push_in_per_min": round(len(push_in_value) / sec_entries * 60, 1),
        "fast_push_per_min": round(fast_push_value / sec_entries * 60, 1),
        "push_in_share": round(len(push_in_value) / max(1, len(push_in_value) + len(pull_out_value)), 2),
        "push_in_times_s": [round(a / FPS, 1) for a, _ignored in push_in_value],
        "subject_box": round(float(np.median(subj_value)), 3),
        "flat_light": round(float(np.mean(flat_light)), 3),
        "template_sim_share": round(tsim_share_value, 3) if tsim_share_value == tsim_share_value else None,
        "template_sim_max": round(tsim_max_value, 3) if tsim_max_value == tsim_max_value else None,
        "local_fade_ratio": round(lf_value, 3),
        "mean_diff": round(float(np.nanmean(mv_value)), 2),
        "fast_ratio_worst_window": round(worst, 4) if worst == worst else None,
        "worst_window_start_s": worst_t_value,
        "worst_window_len_s": round(win_value / FPS, 2),
        "fast_ratio_by_10s": by10_value,
        "blank_run_s": round(max((b - a for a, b in blank_runs), default=0.0), 2),
        "blank_runs_s": blank_runs,
        "cut_times_s": [round((i + 1) / FPS, 2) for i in np.where(cut)[0]],
        "dissolve_times_s": [round(character_code / FPS, 2) for _ignored, _ignored, character_code in diss_value],
    }
    return res


FLAT_GRAD = 6.0     # an 8x8 block average gradient below this counts as "flat" (320 wide grayscale)
BLANK_GRAD, BLANK_FRAC = 24.0, 0.002   # blank frame: fewer than 0.2% of pixels with gradient > 24 (the single-frame minimum of accepted films in the calibration set is 0.30%, and no two consecutive frames fall below it)
BLANK_EDGE_S, BLANK_MIN_S = 0.5, 0.3   # drop the first and last 0.5s; only runs of >=0.3s count


def find_blank_frames(F, cut_like_value, in_diss):
    """Near-solid-colour blank screens mid-film: [(start, end) seconds], only spans of >= BLANK_MIN_S.
    Judged by edges (almost no gradient across the frame), not by colour; frames either side of a cut and dissolve windows don't count, and a run crossing them is split."""
    n = len(F)
    blank = np.zeros(n, bool)
    for i, fr in enumerate(F):
        g = np.hypot(cv2.Sobel(fr, cv2.CV_32F, 1, 0), cv2.Sobel(fr, cv2.CV_32F, 0, 1))
        blank[i] = (g > BLANK_GRAD).mean() < BLANK_FRAC
    success_flag = np.ones(n, bool)
    e = int(round(BLANK_EDGE_S * FPS)); success_flag[:e] = False; success_flag[max(0, n - e):] = False
    for i in np.where(cut_like_value | in_diss)[0]:
        success_flag[i] = False; success_flag[i + 1] = False
    run_records, first_span = [], None
    for i, v in enumerate(list(blank & success_flag) + [False]):
        if v and first_span is None: first_span = i
        elif not v and first_span is not None:
            if (i - first_span) / FPS >= BLANK_MIN_S - 1e-9: run_records.append((round(first_span / FPS, 2), round(i / FPS, 2)))
            first_span = None
    return run_records
TEX_GRAD = 14.0     # above this counts as "textured"
PAGE_GRAD = 25.0    # the texture a page-frame cell needs (strong edges of text, thin lines, logos)


def perform_page_frame(S, segment_index, cell_tex_value, BS, gh_value, gw_value, shots):
    """Share of screen time held by a fixed page frame.
    A cell "recurs" in a frame = it is strongly textured and appears identically in the same place in >=3 frames that are >=3s apart and whose overall picture already differs clearly.
    Cells recurring in >=25% of the film count as "page-frame cells" (title bar, header, page number, logo, progress bar);
    a frame where page-frame cells (recurring in that frame) cover >=1.5% of the picture counts as framed by the page frame.
    Shots that only reuse the same footage or the same texture recur sporadically and don't clear the 25% bar."""
    N = len(S)
    if N < 6:
        return 0.0
    desc_value = np.array([cv2.resize(fr[: gh_value * BS, : gw_value * BS], (gw_value * 4, gh_value * 4), interpolation=cv2.INTER_AREA)
                     for fr in S]).astype(np.float32)
    desc_value = desc_value.reshape(N, gh_value, 4, gw_value, 4).transpose(0, 1, 3, 2, 4).reshape(N, gh_value, gw_value, 16)
    small = np.array([cv2.resize(fr, (32, 18), interpolation=cv2.INTER_AREA) for fr in S]).astype(np.float32)
    t = segment_index / FPS
    G = np.abs(small[:, None] - small[None]).mean((2, 3))
    far = (np.abs(t[:, None] - t[None]) >= 3.0) & (G > 12)
    persist_value = np.zeros((N, gh_value, gw_value), bool)
    for paired_value in range(gh_value):
        for sample_value in range(gw_value):
            tex_value = cell_tex_value[:, paired_value, sample_value]
            if tex_value.sum() < 3:
                continue
            v = desc_value[:, paired_value, sample_value]
            Dm_value = np.abs(v[:, None] - v[None]).mean(2)
            persist_value[:, paired_value, sample_value] = ((Dm_value < 6.0) & far & tex_value[:, None] & tex_value[None]).sum(1) >= 3
    chrome_value = persist_value.mean(0) >= 0.25
    framed = (persist_value & chrome_value).sum((1, 2)) / (gh_value * gw_value) >= 0.015
    return float(framed.mean())


def perform_layout_desc(fr):
    e = cv2.Canny(fr, 60, 160).astype(np.float32)
    g = cv2.resize(e, (12, 8), interpolation=cv2.INTER_AREA).ravel()
    t = cv2.resize(fr, (12, 8), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    g = (g - g.mean()) / (g.std() + 1e-6); t = (t - t.mean()) / (t.std() + 1e-6)
    return np.concatenate([g, t]) / np.sqrt(2 * g.size)


_TPL_CACHE = {}


def perform_template_similarity(F, shots, template):
    if template not in _TPL_CACHE:
        T, _ignored = decode_gray_frames(template, fps=2, limit=12)
        T = T[:24]                                       # first 12 seconds
        T = T[:, : int(T.shape[1] * 0.85)]
        _TPL_CACHE[template] = np.array([perform_layout_desc(sample_value) for sample_value in T])
    TD = _TPL_CACHE[template]
    sim_entries, dur_entries = [], []
    for s, e in shots:
        sort_key = (s + e) // 2
        v = perform_layout_desc(F[sort_key])
        sim_entries.append(float((TD @ v).max())); dur_entries.append(e - s)
    sim_entries, dur_entries = np.array(sim_entries), np.array(dur_entries, float)
    return float(dur_entries[sim_entries >= 0.70].sum() / dur_entries.sum()), float(sim_entries.max())


BP_HUE, BP_SAT, BP_VAL, BP_FRAME = (225, 300), 0.30, (0.06, 0.90), 0.30


def perform_blue_purple(path, fps=SAMPLE_FPS, width=160):
    """Blue-purple frame share and blue-purple span time codes. Pixels with hue 225°–300°, saturation >=0.30 and value 0.06–0.90 covering >=30% of a frame make it a blue-purple frame."""
    w, h = probe_result(path)[:2]
    hh = max(2, int(round(h * width / w / 2)) * 2)
    raw_payload = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={width}:{hh}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    F = np.frombuffer(raw_payload, np.uint8).reshape(-1, hh, width, 3).astype(np.float32) / 255
    if not len(F):
        return 0.0, []
    r, g, b = F[..., 0], F[..., 1], F[..., 2]
    maximum_value, minimum_value = F.max(-1), F.min(-1); d = maximum_value - minimum_value + 1e-6
    sat_value = d / (maximum_value + 1e-6)
    hue = np.where(maximum_value == r, ((g - b) / d) % 6, np.where(maximum_value == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    matched_object = (hue >= BP_HUE[0]) & (hue <= BP_HUE[1]) & (sat_value >= BP_SAT) & (maximum_value >= BP_VAL[0]) & (maximum_value <= BP_VAL[1])
    bad = matched_object.reshape(len(F), -1).mean(1) >= BP_FRAME
    spans, start = [], None
    for i, sample_value in enumerate(list(bad) + [False]):
        if sample_value and start is None: start = i
        if not sample_value and start is not None:
            if i - start >= 2: spans.append((round(start / fps, 1), round(i / fps, 1)))
            start = None
    return round(float(bad.mean()), 3), spans


# ---------------------------------------------------------------- grading
SHORT_S = float(os.environ.get("FILM_GATE_MIN_S", 20))  # every film in the calibration set is 45s or longer; readings from clips this short are noisy, so red becomes yellow (informational only)


FACT_GATES = {"blank_run_s", "blue_purple_share"}   # red even for short clips (the palette doesn't change with length)


def perform_grade(res):
    table_rows, red = [], False
    short = (res.get("duration_s") or 0) < SHORT_S
    for sort_key, (name, direc_value, paired_value, r, gate, unit) in METRICS.items():
        v = res.get(sort_key)
        if v is None or direc_value == "info":
            table_rows.append((sort_key, name, v, "--", gate, unit)); continue
        bad = (lambda t: v >= t) if direc_value == "high_bad" else (lambda t: v <= t)
        lv = "red" if (gate and r is not None and bad(r)) else "yellow" if (paired_value is not None and bad(paired_value)) else "green"
        if lv == "red" and sort_key == "blue_purple_share" and res.get("allow_blue_purple"):
            lv = "yellow"
        if lv == "red" and short and sort_key not in FACT_GATES:
            lv = "yellow"; res["short_clip_note"] = f"clip is {res.get('duration_s')}s, shorter than {SHORT_S}s, so the fast-motion gate only warns instead of blocking (blank screens still block); run it again on the finished film once this is cut in"
        red |= lv == "red"
        table_rows.append((sort_key, name, v, lv, gate, unit))
    return table_rows, red


# ---------------------------------------------------------------- read out to a human
FIX = ("Following references/camera-language.md (camera language), add in-shot movement where the viewer should be looking at this moment: slow push to read detail (0.6–1.5s, CAM.track's push), "
       "glide when moving between several things, pull back to show the whole picture; big actions by the objects themselves (growth, page turns, pouring, movement inside live footage) count too — and if the footage is moving on its own, hold still. "
       "Fast pushes and slams are accents: save them for reveals, reversals, key numbers. A few percent of uniform slow push per shot, fades and transitions don't count (however fast a transition is, it's excluded). "
       "A ~1s 20% slow push and a 0.28s fast push score about the same on this metric, so don't speed up camera moves just to pass. "
       "And don't stuff one push-in into every shot to pass: the 2026-10-12 film pushed every 2 seconds and was judged \"too much, too fast, not smooth\".")

BLANK_FIX = ("Keep the protagonist or main object in frame through the blank stretch: to change the beat, let it hold, pull back, or glide the camera off it to the next object; "
             "don't let a transition rest on a solid-colour ground (black frame, solid flash, gradient ground) for more than 0.3s. Whiteboards and black-ground films aren't blank as long as there are strokes, lines or text on screen.")

BP_FIX = ("Change the blue-purple ground: write the same \"theme\" in the clip spec (paper, poster, ink, navy, bauhaus, snow, wood, chalk from references/palette.md (palette), "
          "or define your own by its rules) and use that palette in the scenes too; don't paint deep-purple starfields, blue-purple gradients or neon cyan-purple light. "
          "Only when the subject itself needs blue-purple (user-specified cyberpunk purple, Van Gogh Starry Night) use --allow-blue-purple \"reason\"; the reason goes into the delivery note.")


# report-only yellow items: one sentence on "where to look"
LOOK = {
    "fast_ratio_worst_window": lambda r: f"{r['worst_window_start_s']:.0f}–{r['worst_window_start_s'] + r['worst_window_len_s']:.0f}s has almost no fast action (front-loaded, back-loaded)",
    "drift_ratio": lambda r: f"{r['drift_ratio']:.0%} of frames are slowly drifting",
    "longest_still_s": lambda r: f"from {r['longest_still_start_s']:.1f}s nothing moves for {r['longest_still_s']:.1f}s straight",
    "event_rate": lambda r: f"only {r['event_rate']:.1f} visual events per 10 seconds on average",
    "max_event_gap_s": lambda r: f"the longest {r['max_event_gap_s']:.1f}s with no cut or fast action at all",
    "dead_bg": lambda r: f"after removing camera motion, on average {r['dead_bg']:.0%} of the frame never changes within a shot",
    "dead_flat": lambda r: f"{r['dead_flat']:.0%} of the frame is a never-changing empty ground",
    "flat_light": lambda r: f"cream/white empty ground averages {r['flat_light']:.0%} of the frame (whiteboard and other light-ground styles can be like this; confirm it's the style and not emptiness)",
    "page_frame_share": lambda r: f"{r['page_frame_share']:.0%} of the duration is framed by fixed headers, page numbers, title bars, logos",
    "slow_zoom_share": lambda r: f"{r['slow_zoom_share']:.0%} of the duration is uniform slow push/pull shots",
    "push_in_per_min": lambda r: (f"at least {r['push_in_per_min']:g} push-ins per minute (of which {r['fast_push_per_min']:g} are fast, push-ins are {r['push_in_share']:.0%} of push/pull), "
                                  f"push-upon-push zoom-ins feel rushed and rough; watch it once at normal speed and check whether each push is answered by a pull-back or a glide (references/camera-language.md)"),
    "dissolve_share": lambda r: f"{r['dissolve_share']:.0%} of transitions are dissolves",
    "template_sim_share": lambda r: f"{r['template_sim_share']:.0%} of the duration has almost the same composition as the demo reel",
}


def explain(res):
    """One-line verdict + why + how to fix + where to look for yellow items. Uses only the numbers measured into res."""
    fr, lv = res["fast_ratio"], res["lights"]["fast_ratio"]
    if lv == "red":
        head_value = ("the film never once moves fast within a shot, so it reads like page flipping" if fr < 0.005 else
                f"only {fr:.1%} of frames move fast within a shot across the whole film (red line 3.5%), so it reads like page flipping")
    elif lv == "yellow":
        head_value = f"fast in-shot movement is thin ({fr:.1%}, yellow line 6%), not far from a page-flipping feel"
    else:
        head_value = f"there is enough fast in-shot movement ({fr:.1%})"
    if res.get("short_clip_note"):
        head_value += ". " + res["short_clip_note"]
    blank_red_value = res["lights"].get("blank_run_s") == "red"
    if blank_red_value:
        segs = ", ".join(f"{a:.2f}–{b:.2f}s" for a, b in res["blank_runs_s"])
        head_value = (f"there are {len(res['blank_runs_s'])} near-solid-colour blank stretch(es) mid-film ({segs}), the longest {res['blank_run_s']:.2f}s, "
                f"with almost no edge or texture anywhere in the frame and the subject out of frame") + ("; also " + head_value if lv != "green" else "")
    breakpoint_map = res["lights"].get("blue_purple_share")
    if breakpoint_map in ("red", "yellow") and not res.get("allow_blue_purple"):
        segs = ", ".join(f"{a:.1f}–{b:.1f}s" for a, b in res["blue_purple_spans_s"][:6])
        message_text = f"{res['blue_purple_share']:.0%} of the picture is on a blue-purple ground ({segs})"
        head_value = (message_text + ", the most typical AI palette" + ("; also " + head_value if lv != "green" or blank_red_value else "")) if breakpoint_map == "red" else head_value + "; " + message_text
    elif res.get("allow_blue_purple") and res["blue_purple_share"] >= METRICS["blue_purple_share"][2]:
        head_value += f"; blue-purple ground covers {res['blue_purple_share']:.0%}, declared as required by the subject: {res['allow_blue_purple']}"
    why = []
    if lv != "green":
        if res["slow_zoom_share"] >= 0.3:
            why.append(f"{res['slow_zoom_share']:.0%} of the duration is uniform slow push/pull")
        if res["still_ratio"] >= 0.5:
            why.append(f"{res['still_ratio']:.0%} of frames are completely still")
        elif res["drift_ratio"] >= 0.4:
            why.append(f"{res['drift_ratio']:.0%} of frames are only slowly drifting")
        if res["hard_cuts"] + res["dissolves"]:
            why.append(f"the picture changes mainly through transitions (hard cuts {res['hard_cuts']}, dissolves {res['dissolves']}), and transitions don't count as in-shot movement")
    look = [(sort_key, LOOK[sort_key](res)) for sort_key, item_length in res["lights"].items() if item_length == "yellow" and sort_key in LOOK]
    ww_value = None
    if res.get("worst_window_start_s") is not None:
        a = res["worst_window_start_s"]
        ww_value = {"start_s": a, "end_s": round(a + res["worst_window_len_s"], 2), "fast_ratio": res["fast_ratio_worst_window"]}
    fix = " ".join(sample_value for sample_value in (BP_FIX if breakpoint_map == "red" else None, BLANK_FIX if blank_red_value else None, FIX if lv != "green" else None) if sample_value) or None
    return {"summary": head_value, "why": why, "fix": fix, "look": look, "worst_window": ww_value, "blank_runs": res["blank_runs_s"]}


def measure(path, sub_band=None, vertical="auto", template=DEFAULT_TEMPLATE, allow_blue_purple=None):
    """Measure one finished cut; returns a result carrying lights / gate_light / verdict / explain. deliver.py calls this too.
    allow_blue_purple: the reason (a non-empty string) when the subject itself needs blue-purple; the blue-purple gate drops to yellow and the reason goes into the result."""
    tpl_value = template if template and os.path.exists(template) else None
    cv2.setNumThreads(max(1, (os.cpu_count() or 2) // 2))
    res = analyze(path, sub_band=sub_band, vertical=vertical, template=tpl_value)
    res["blue_purple_share"], res["blue_purple_spans_s"] = perform_blue_purple(path)
    if allow_blue_purple and allow_blue_purple.strip():
        res["allow_blue_purple"] = allow_blue_purple.strip()
    table_rows, red = perform_grade(res)
    res["lights"] = {sort_key: lv for sort_key, _ignored, _ignored, lv, _ignored, _ignored in table_rows}
    res["gate_metrics"] = [sort_key for sort_key, _ignored, _ignored, _ignored, gate, _ignored in table_rows if gate]
    glossary_map = [res["lights"][sort_key] for sort_key in res["gate_metrics"]]
    res["gate_light"] = "red" if "red" in glossary_map else "yellow" if "yellow" in glossary_map else "green"
    res["verdict"] = "red" if red else "pass"
    res["explain"] = explain(res)
    return res, table_rows


LIGHT = {"red": "[R]", "yellow": "[Y]", "green": "[G]", "--": "[ ]"}


def render_finding_report(res, table_rows):
    """Text report (shared by the terminal and the delivery note)."""
    L = [f"{res['file']}  {res['orientation']}  {res['duration_s']}s  "
         f"shots {res['shots']} (hard cuts {res['hard_cuts']}, dissolves {res['dissolves']})  average shot {res['asl_s']}s"]
    for sort_key, name, v, lv, gate, unit in table_rows:
        vs = "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
        L.append(f"  {LIGHT[lv]} {'gate' if gate else 'report'}  {name}: {vs}{unit}")
    ex = res["explain"]
    if res.get("blank_runs_s"):
        L.append("  blank screen time codes: " + ", ".join(f"{a:.2f}–{b:.2f}s" for a, b in res["blank_runs_s"]))
    if res.get("blue_purple_spans_s") and res["lights"].get("blue_purple_share") != "green":
        L.append("  blue-purple ground time codes: " + ", ".join(f"{a:.1f}–{b:.1f}s" for a, b in res["blue_purple_spans_s"]))
    if res.get("allow_blue_purple"):
        L.append(f"  subject-mandated blue-purple declared: {res['allow_blue_purple']}")
    if ex["worst_window"]:
        w = ex["worst_window"]
        L.append(f"  worst {w['end_s'] - w['start_s']:.0f} second window: {w['start_s']:.0f}–{w['end_s']:.0f}s, fast-motion frame share {w['fast_ratio']};"
                 f" fast-motion frame share every 10 seconds: {res['fast_ratio_by_10s']}")
    return L


def main():
    argument_parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argument_parser.add_argument("mp4")
    argument_parser.add_argument("--json", action="store_true")
    argument_parser.add_argument("--vertical", default="auto", choices=["auto", "yes", "no"],
                    help="landscape or portrait; auto decides from width and height. Only affects the subtitle band default")
    argument_parser.add_argument("--sub-band", type=float, default=None,
                    help="fraction of the bottom to mask as subtitle band; defaults to 0.15 landscape, 0.18 portrait; 0 disables masking")
    argument_parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="demo reel (the first 12 seconds are compared for composition)")
    argument_parser.add_argument("--no-template", action="store_true")
    argument_parser.add_argument("--allow-blue-purple", metavar="reason", default=None,
                    help="when the subject itself needs blue-purple (user-specified cyberpunk purple, Van Gogh Starry Night), pass the reason and the blue-purple gate drops to yellow")
    a = argument_parser.parse_args()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe are required", file=sys.stderr); sys.exit(1)
    try:
        res, table_rows = measure(a.mp4, sub_band=a.sub_band, vertical=a.vertical, template=None if a.no_template else a.template,
                            allow_blue_purple=a.allow_blue_purple)
    except (subprocess.CalledProcessError, KeyError, IndexError, RuntimeError, ValueError) as e:
        print(f"cannot read this film: {a.mp4} ({e})", file=sys.stderr); sys.exit(1)
    red = res["verdict"] == "red"
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("\n".join(render_finding_report(res, table_rows)))
        ex = res["explain"]
        tag = {"red": "red light, do not ship", "yellow": "yellow light, shippable but a human has to look", "green": "gates passed"}[res["gate_light"]]
        print(f"Verdict: {tag} — {ex['summary']}." + ("".join(f" {w}; " for w in ex["why"]).rstrip("; ") + "." if ex["why"] else ""))
        if ex["fix"]:
            print("How to fix: " + ex["fix"])
        if ex["look"]:
            print("Yellow items (report only, never blocking; go watch that stretch and say item by item in the delivery note why it's fine):")
            for _ignored, t in ex["look"]:
                print("  - " + t)
        if not red:
            print("Note: the gates only block three hard faults — \"almost no fast action in the whole film\", \"blank screens mid-film\" and \"blue-purple ground\"; the independent review still has to be done.")
    sys.exit(2 if red else 0)


if __name__ == "__main__":
    main()
