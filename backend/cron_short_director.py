"""Source-aware presentation for cron Shorts; no timeline or audio changes."""
from __future__ import annotations

import math
from pathlib import Path
import re


POLICY_VERSION = 1
GAMING = re.compile(r'\b(roblox|minecraft|gameplay|gaming|mabar)\b', re.I)
FILLER = re.compile(r'\b(sumpah|hehe\w*|haha\w*|wo+w|jebum|boskyu|anjay|guys)\b', re.I)
SPECIFIC = re.compile(r'\b(motor|mobil|pintu|uang|harga|beli|borong|jual|menang|kalah|misi|pilihan|masalah|jawaban|ternyata|akhirnya|kenapa|mengapa|berapa)\b', re.I)
UNFINISHED = {'yang','dan','atau','karena','kalau','jika','dengan','untuk','di','ke','dari','sama','berarti'}


def opening_lines(text: str) -> str:
    """Fit the complete phrase in the caption-safe width, without truncation."""
    try:
        from PIL import ImageFont
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 52)
        measure = font.getlength
    except (ImportError, OSError):
        measure = lambda value: len(value) * 52 * .72
    lines = ['']
    for word in text.upper().rstrip(' ,.!;:').split():
        if measure(word) > 800:
            return ''
        proposed = (lines[-1]+' '+word).strip()
        if measure(proposed) > 800:
            lines.append(word)
        else:
            lines[-1] = proposed
    return '\n'.join(lines) if len(lines) <= 2 else ''


def grounded_opening(clip, segments, *, enabled: bool, sensitive: bool = False) -> dict:
    """Pick a readable source sentence; never invent a hook or a numeric claim."""
    original = str(clip.hook or clip.title or '')
    result = dict(enabled=False, text=original, method='existing_hook', source_start=None,
                  source_end=None, source_words_only=True, audio_reordered=False)
    if not enabled or sensitive:
        return result
    source_words = ' '.join(re.findall(r"[\w']+", str(clip.text).casefold()))
    choices = []
    for row in segments:
        if row.start < clip.start - .05 or row.end > clip.end + .05:
            continue
        text = re.sub(r'\s+', ' ', str(row.text)).strip()
        words = re.findall(r"[\w']+", text)
        if ' '+' '.join(word.casefold() for word in words)+' ' not in ' '+source_words+' ':
            continue
        if not 4 <= len(words) <= 11 or words[-1].casefold() in UNFINISHED:
            continue
        if not opening_lines(text) or len(set(w.casefold() for w in words)) < 4:
            continue
        # An ASR monetary amount is not an independently verified fact. Leave
        # it in the dialogue/captions rather than promoting it as a title.
        if re.search(r'\d', text):
            continue
        specificity = len({word.casefold() for word in SPECIFIC.findall(text)})
        if specificity < 2:
            continue
        score = specificity * 3 + (2 if '?' in text else 0) - len(FILLER.findall(text)) * 3
        if score < 6:
            continue
        choices.append((score, -float(row.start), text, row))
    if not choices:
        return result
    _, _, text, row = max(choices, key=lambda item: item[:2])
    # Preserve qualifiers/negation by keeping the complete original sentence.
    result.update(enabled=True, text=text, method='source_sentence_preview',
                  display_text=opening_lines(text), font_size=52,
                  source_start=round(float(row.start), 3), source_end=round(float(row.end), 3))
    return result


def measure_focus(video_path: Path, start: float, duration: float) -> dict:
    """Choose one stable detail crop from five small source samples, or abstain."""
    result = dict(available=False, method='sampled_motion_and_detail', sample_count=0,
                  reason='insufficient_source_frames')
    capture = None
    try:
        import cv2
        import numpy as np
        capture = cv2.VideoCapture(str(video_path))
        frames = []
        for fraction in (.08, .25, .46, .69, .87):
            capture.set(cv2.CAP_PROP_POS_MSEC, (start + duration * fraction) * 1000)
            ok, frame = capture.read()
            if ok:
                frames.append(cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY).astype('float32'))
        result['sample_count'] = len(frames)
        if len(frames) < 3:
            return result
        edges = [np.abs(cv2.Sobel(frame, cv2.CV_32F, 1, 0)) +
                 np.abs(cv2.Sobel(frame, cv2.CV_32F, 0, 1)) for frame in frames]
        motions = [np.abs(right-left) for left, right in zip(frames, frames[1:])]
        if float(np.mean(edges)) < 8:
            result['reason'] = 'no_readable_detail'
            return result
        result['readable_detail'] = True
        maps = [edge * .24 + motions[min(i, len(motions)-1)] for i, edge in enumerate(edges)]
        # Avoid letting static top HUD/menu headers outvote the actual game
        # area. The complete context panel still retains every HUD element.
        windows = [(x, y) for y in (.46, .56, .66) for x in (.28, .50, .72)]
        scores = []
        for energy in maps:
            scores.append([float(energy[round((y-.26)*180):round((y+.26)*180),
                                      round((x-.26)*320):round((x+.26)*320)].mean())
                           for x, y in windows])
        aggregate = np.mean(scores, axis=0)
        winner = int(np.argmax(aggregate))
        def overlaps(left, right):
            intersection = max(0., .52-abs(left[0]-right[0])) * max(0., .52-abs(left[1]-right[1]))
            return intersection / (.52*.52*2-intersection) >= .5
        # Adjacent winning windows can cover the same subject. Measure their
        # actual crop overlap rather than treating grid-boundary jitter as a
        # completely different scene/focus.
        agreement = sum(overlaps(windows[int(np.argmax(row))], windows[winner]) for row in scores) / len(scores)
        contrast = float(aggregate[winner] / max(.01, float(np.mean(aggregate))))
        result.update(temporal_agreement=round(agreement, 3), detail_contrast=round(contrast, 3))
        if agreement < .6 or contrast < 1.08:
            result['reason'] = 'focus_not_stable'
            return result
        result.update(available=True, center=list(windows[winner]), width_ratio=.52,
                      temporal_agreement=round(agreement, 3), detail_contrast=round(contrast, 3),
                      temporal_agreement_method='crop_overlap_at_least_half',
                      reason='stable_source_detail')
    except Exception:
        result['reason'] = 'source_analysis_unavailable'
    finally:
        if capture is not None:
            capture.release()
    return result


def presentation_plan(base: dict, *, enabled: bool, genre: str, source_label: str = '',
                      sensitive: bool = False, focus: dict | None = None) -> dict:
    """Preserve the complete wide shot; detail is a same-time auxiliary view."""
    if not enabled or not base.get('enabled') or base.get('layout') != 'landscape_in_portrait':
        return base
    width, height = base['source_width'], base['source_height']
    if not 1.4 <= width / height <= 2.4:
        return base
    panel_height = int(1080 * height / width) // 2 * 2
    gaming = genre == 'gaming' or bool(GAMING.search(source_label))
    focus = focus or {}
    measured = focus.get('available') is True
    neutral_detail = bool(focus.get('readable_detail') is True and focus.get('sample_count', 0) >= 3
        and focus.get('reason') == 'focus_not_stable')
    detail = bool(gaming and not sensitive and (measured or neutral_detail) and width >= 960 and width/height >= 1.72)
    # Malformed coordinates never become filter expressions. The neutral
    # composition is a fixed editorial preset, not an object-tracking claim.
    center = focus.get('center') if measured else [.5, .56] if neutral_detail else None
    if detail and (not isinstance(center, (list, tuple)) or len(center) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) or not .26 <= v <= .74 for v in center)):
        detail = False
    plan = dict(base, policy_version=POLICY_VERSION, cron_only=True,
        layout='source_context_detail' if detail else 'source_context_stage',
        background='blurred_same_source_frame', full_source_frame_visible=True,
        all_panels_synchronized=True, uses_other_timeline_clips=False,
        source_clock_unchanged=True, audio_unchanged=True,
        panel_width=1080, panel_height=panel_height,
        panel_y=360 if detail else 600, hook_y=220 if detail else 440,
        caption_baseline=1550 if detail else min(1500, 600+panel_height+160),
        focus_analysis=focus, reason='cron_source_aware_presentation',
        focus_selection='measured_stable_detail' if detail and measured else
            'neutral_center_without_object_tracking' if detail else 'complete_context',
        reference_principles=['immediate_source_grounded_hook','source_aware_reframing','readable_phrase_captions'])
    if detail:
        crop_w = int(width * .52) // 2 * 2
        crop_h = int(crop_w * height / width) // 2 * 2
        crop_x = max(0, min(width-crop_w, int(center[0]*width-crop_w/2))) // 2 * 2
        crop_y = max(0, min(height-crop_h, int(center[1]*height-crop_h/2))) // 2 * 2
        detail_y = plan['panel_y'] + panel_height + 34
        detail_height = int(832*height/width)//2*2
        plan.update(detail_crop=[crop_w,crop_h,crop_x,crop_y], detail_x=64,
                    detail_y=detail_y, detail_width=832, detail_height=detail_height,
                    detail_label='LIHAT DETAILNYA',
                    caption_baseline=min(1550, detail_y+detail_height+114))
    return plan


def source_filter(plan: dict) -> str:
    detail = plan['layout'] == 'source_context_detail'
    filters = ['split=3[cron_background][cron_context][cron_detail]' if detail else
               'split=2[cron_background][cron_context]',
        '[cron_background]scale=270:480:force_original_aspect_ratio=increase:force_divisible_by=2,'
        'crop=270:480,gblur=sigma=16:steps=2,eq=brightness=-0.04:saturation=0.55,'
        'colorchannelmixer=rr=0.65:gg=0.65:bb=0.65,'
        'scale=1080:1920:flags=bilinear,setsar=1[cron_canvas]',
        f"[cron_context]scale={plan['panel_width']}:{plan['panel_height']}:flags=lanczos,setsar=1[cron_wide]",
        f"[cron_canvas][cron_wide]overlay={(1080-plan['panel_width'])//2}:{plan['panel_y']}:shortest=1" +
            ('[cron_with_context]' if detail else '')]
    if detail:
        w,h,x,y=plan['detail_crop']
        filters.extend([
            f"[cron_detail]crop={w}:{h}:{x}:{y},scale={plan['detail_width']}:{plan['detail_height']}:flags=lanczos,setsar=1[cron_zoom]",
            f"[cron_with_context][cron_zoom]overlay={plan['detail_x']}:{plan['detail_y']}:shortest=1",
        ])
    return ';'.join(filters)
