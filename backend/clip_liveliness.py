"""Three opt-in liveliness accents for cron Shorts. Additive only: no retiming.

This module is deliberately separate from cron_director_effects. Its plan is
off by default, never blocks an export, and never changes source time, captions,
audio, or the already-existing accent vocabulary. A failed optional render is
reported in the plan and the main export continues.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess

from cron_director_effects import (
    PALETTES,
    REACTION_WORDS,
    SENSITIVE,
    _encode,
    _probe,
)

POLICY_VERSION = 1
KINDS = ('beat_pulse', 'comet_streak', 'edge_glow')

_ACTION = re.compile(
    r'\b(lari|kejar|cepat|lompat|loncat|hindari|menyerang|gerak|belok|dorong|tarik|jatuh|terbang)\b',
    re.I,
)
_PAYOFF = re.compile(
    r'\b(ternyata|rupanya|akhirnya|berhasil|menang|selamat|lolos|juara|selesai|selesai\w*)\b',
    re.I,
)
_SIGNALS = {
    'beat_pulse': REACTION_WORDS,
    'comet_streak': _ACTION,
    'edge_glow': _PAYOFF,
}


def _seed(seed: str, salt: str) -> int:
    return int.from_bytes(hashlib.sha256(f'{seed}:{salt}'.encode()).digest()[:8], 'big')


def build_plan(clip, segments, *, enabled=False, protected=False, layout=None, seed=''):
    """Pick at most two source-timed accents; default plan is completely inert."""
    plan = dict(
        version=POLICY_VERSION,
        enabled=False,
        rendered=False,
        required=False,
        cue_count=0,
        cues=[],
        source_clock_unchanged=True,
        captions_clock_unchanged=True,
        audio_unchanged=True,
        inserted_timeline_seconds=0,
        verification='not_enabled',
        reason='opt_in_disabled',
    )
    layout = layout or {}
    if not enabled:
        return plan
    if protected or SENSITIVE.search(str(clip.text)):
        plan['reason'] = 'protected_or_sensitive_context'
        return plan
    if any(layout.get(key) for key in ('evidence', 'social_card', 'reaction_avatar', 'multi_split')):
        # Do not stack on panels that already carry meaning.
        plan['reason'] = 'protected_complex_layout'
        return plan

    duration = float(clip.end - clip.start)
    if duration < 3.0:
        plan['reason'] = 'clip_too_short'
        return plan

    portrait = bool(layout.get('portrait', True))
    caption_upper = layout.get('caption_position') == 'upper'
    if portrait:
        boxes = ([.035, .22, .11, .11], [.855, .22, .11, .11]) if not caption_upper else ([.035, .55, .11, .11], [.855, .55, .11, .11])
    else:
        boxes = ([.025, .24, .09, .16], [.885, .24, .09, .16]) if not caption_upper else ([.025, .55, .09, .16], [.885, .55, .09, .16])

    cues = []
    for kind in KINDS:
        if len(cues) >= 2:
            break
        pattern = _SIGNALS[kind]
        matches = []
        for row in segments or ():
            quote = str(row.text).strip()
            if not pattern.search(quote):
                continue
            if not clip.start <= row.start < row.end <= clip.end:
                continue
            if (' ' + re.sub(r'\W+', ' ', quote.lower()).strip() + ' ') not in (
                ' ' + re.sub(r'\W+', ' ', str(clip.text).lower()).strip() + ' '
            ):
                continue
            start = max(.08, float(row.end) - clip.start - .20)
            end = min(duration - .35, start + .62)
            if end - start < .25:
                continue
            matches.append((start, end, quote))
        if not matches:
            continue
        start, end, quote = matches[_seed(seed, kind) % len(matches)]
        choice = _seed(seed, kind + ':box') % 2
        variation = _seed(seed, kind + ':variation') % 4
        palette = PALETTES[_seed(seed, kind + ':palette') % len(PALETTES)]
        cues.append(dict(
            kind=kind,
            quote=quote,
            start=round(start, 3),
            end=round(end, 3),
            box=[round(v, 6) for v in boxes[choice]],
            palette=list(palette),
            variation=variation,
            directed_by='timed_source_dialogue',
        ))

    if not cues:
        plan['reason'] = 'no_grounded_dialogue_cue'
        return plan
    plan.update(enabled=True, cue_count=len(cues), cues=cues, reason='grounded_liveliness_accents')
    return plan


def accent_frame(kind: str, side: int, progress: float, color, variation: int = 0):
    """One transparent RGBA frame; geometry is bounded and fully procedural."""
    import math
    from PIL import Image, ImageDraw

    image = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    r, g, b = color
    alpha = max(0, min(255, round(235 * (1.0 - progress) ** 0.7)))
    c = side / 2
    if kind == 'beat_pulse':
        radius = side * (.16 + .30 * progress)
        width = max(2, round(side * .035 * (1.0 - progress * .5)))
        draw.ellipse((c - radius, c - radius, c + radius, c + radius), outline=(r, g, b, alpha), width=width)
        for i in range(4 + variation % 2):
            angle = i * (2 * math.pi / (4 + variation % 2)) + variation * .4
            inner = radius * .92
            outer = radius * 1.16
            draw.line((c + inner * math.cos(angle), c + inner * math.sin(angle),
                       c + outer * math.cos(angle), c + outer * math.sin(angle)),
                      fill=(r, g, b, alpha), width=max(2, width // 2))
    elif kind == 'comet_streak':
        travel = side * (.10 + .62 * progress)
        head = (c - side * .26 + travel, c + side * .20 - travel * .45)
        draw.line((head[0] - side * .30, head[1] + side * .14, head[0], head[1]),
                  fill=(r, g, b, alpha), width=max(2, round(side * .05)))
        hr = side * .075
        draw.ellipse((head[0] - hr, head[1] - hr, head[0] + hr, head[1] + hr), fill=(r, g, b, alpha))
    else:  # edge_glow
        radius = side * (.20 + .22 * progress)
        for step in range(5, 0, -1):
            rr = radius * step / 5
            layer = max(0, round(alpha * (.10 + .05 * (5 - step))))
            draw.ellipse((c - rr, c - rr, c + rr, c + rr), fill=(r, g, b, layer))
    return image


def render_overlays(video, plan, *, ffmpeg='ffmpeg', crf=18, preset='fast', threads=2):
    """Replace the temp video atomically, only if the clock and geometry survive."""
    if not plan.get('enabled') or not plan.get('cues'):
        return plan
    video = Path(video).resolve()
    assets = video.parent / '.clip-liveliness'
    assets.mkdir(exist_ok=True)
    target = video.with_name(video.stem + '.liveliness_tmp.mp4')
    before = _probe(video)
    w, h = before['width'], before['height']
    movies = []
    try:
        graph = ['[0:v]setpts=PTS-STARTPTS[liveliness_base]']
        previous = 'liveliness_base'
        stem = re.sub(r'[^a-zA-Z0-9_-]', '_', video.stem)[:70]
        for i, cue in enumerate(plan['cues']):
            side = max(48, round(min(w * cue['box'][2], h * cue['box'][3])))
            span = cue['end'] - cue['start']
            count = max(3, min(30, round(span * 24)))
            prefix = assets / f'{stem}_{i}'
            frames = []
            try:
                for n in range(count):
                    path = Path(str(prefix) + f'_{n:03}.png')
                    frames.append(path)
                    accent_frame(cue['kind'], side, n / max(1, count - 1), cue['palette'], cue['variation']).save(path)
                movie = Path(str(prefix) + '.mkv')
                movies.append(movie)
                subprocess.run(
                    [ffmpeg, '-v', 'error', '-y', '-framerate', '24', '-i', str(prefix) + '_%03d.png',
                     '-c:v', 'ffv1', '-pix_fmt', 'bgra', '-threads', '1', str(movie)],
                    check=True, capture_output=True, timeout=60,
                )
                movie_path = str(movie).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
                graph.append(f"movie='{movie_path}',format=rgba,setpts=PTS-STARTPTS+{cue['start']}/TB[live_{i}]")
                graph.append(
                    f"[{previous}][live_{i}]overlay=x={round(w * cue['box'][0])}:y={round(h * cue['box'][1])}:"
                    f"eof_action=pass:repeatlast=0:enable='between(t,{cue['start']},{cue['end']})'[liveliness_{i}]"
                )
                previous = f'liveliness_{i}'
            finally:
                for path in frames:
                    path.unlink(missing_ok=True)
        graph.append(f'[{previous}]null[accent_out]')
        _encode(video, target, ';'.join(graph), ffmpeg=ffmpeg, crf=crf, preset=preset, threads=threads)
        plan['renderer'] = 'procedural_rgba_liveliness_accents'
    except (OSError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        # Optional accents never block a completed export.
        plan.update(rendered=False, cue_count=0, cues=[], renderer=None,
                    fallback_reason=type(exc).__name__)
        return plan
    finally:
        for movie in movies:
            movie.unlink(missing_ok=True)
    after = _probe(target)
    if (abs(after['duration'] - before['duration']) > max(.05, 1.1 / before['fps'])
            or (before['frames'] and after['frames'] != before['frames'])
            or (before['width'], before['height']) != (after['width'], after['height'])):
        target.unlink(missing_ok=True)
        plan.update(rendered=False, cue_count=0, cues=[], renderer=None,
                    fallback_reason='clock_or_geometry_changed')
        return plan
    target.replace(video)
    plan.update(rendered=True, cue_count=len(plan['cues']),
                verification='duration_frame_count_and_geometry_preserved')
    return plan
