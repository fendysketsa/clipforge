"""Source-timed visual inserts; source playback, speech, and captions keep their clock."""
from __future__ import annotations

import base64
from html import escape
import json
import math
from pathlib import Path
import re
import subprocess
import textwrap
from typing import Callable

from ryuundy_reference_learning import practical_payoff_profile


KINDS = {"freeze_inset", "cutout_stop_motion", "step_diagram"}
PROTECTED_ACCENTS = {
    "reverent_focus", "restrained_authority", "context_briefing", "claim_rebuttal",
    "evidence_stage", "dialogue_focus", "banter_payoff",
}


def _words(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def quote_window(quote: str, segments: list, clip_start: float, clip_end: float):
    """Find an exact normalized phrase in the timed transcript, including across rows."""
    needle = _words(quote)
    if len(needle.split()) < 4:
        return None
    parts, ranges, offset = [], [], 0
    for row in segments:
        if not (math.isfinite(row.start) and math.isfinite(row.end)
                and clip_start <= row.start < row.end <= clip_end + .05):
            continue
        value = _words(row.text)
        parts.append(value)
        ranges.append((offset, offset + len(value), row))
        offset += len(value) + 1
    position = " ".join(parts).find(needle)
    if position < 0:
        return None
    matched = [row for left, right, row in ranges
               if left < position + len(needle) and right > position]
    if not matched:
        return None
    return matched[0].start - clip_start, matched[-1].end - clip_start


def build_motion_plan(clip, segments: list, visual_plan: dict, *, manifest: dict | None = None) -> dict:
    plan = {
        "version": 1, "enabled": False, "rendered": False, "cues": [],
        "reason": "no_supported_source_beat", "source_clock_unchanged": True,
        "captions_clock_unchanged": True, "source_audio_unchanged": True,
        "human_segmentation_claimed": False, "object_animation_fps": 12,
    }
    if (visual_plan.get("accent") in PROTECTED_ACCENTS
            or visual_plan.get("content_lane", "general_knowledge") != "general_knowledge"
            or visual_plan.get("evidence_direction", {}).get("beats")):
        plan["reason"] = "preserve_sensitive_context_and_evidence"
        return plan
    duration = clip.end - clip.start
    if not math.isfinite(duration) or duration < 10:
        return plan
    kind, quote, region = "", "", None
    if manifest is not None:
        # An LLM cannot supply arbitrary crop coordinates or mark its own ROI reviewed.
        if (manifest.get("review_status") != "source_checked"
                or not str(manifest.get("reviewed_by") or "").strip()
                or manifest.get("kind") not in KINDS
                or manifest.get("clip_start") != clip.start):
            plan["reason"] = "unreviewed_or_mismatched_manifest"
            return plan
        kind, quote = manifest["kind"], str(manifest.get("quote") or "")
        if kind == "cutout_stop_motion":
            raw = manifest.get("region")
            if (not isinstance(raw, list) or len(raw) != 4
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) for v in raw)
                    or not (0 <= raw[0] < 1 and 0 <= raw[1] < 1
                            and .05 <= raw[2] <= 1 - raw[0]
                            and .05 <= raw[3] <= 1 - raw[1])):
                plan["reason"] = "invalid_reviewed_source_region"
                return plan
            region = list(raw)
    else:
        practical = practical_payoff_profile(clip.text, duration)
        if practical["qualified"]:
            quote = str(practical["evidence"]["action"])
            kind = "step_diagram" if (
                re.search(r"\b(subtitle|caption)\b", clip.text, re.I)
                and re.search(r"\b(baris|kalimat)\b", quote, re.I)
                and re.search(r"\b(pisahkan|bagi|potong)\b", quote, re.I)
            ) else "freeze_inset"
        else:
            quote = next((row.text for row in segments if re.search(
                r"\b(ternyata|padahal|rupanya|akhirnya|pilihan)\b", row.text, re.I
            ) and row.start >= clip.start + 2), "")
            kind = "freeze_inset"
    window = quote_window(quote, segments, clip.start, clip.end)
    if not kind or window is None:
        return plan
    start = max(2.0, window[0])
    end = min(duration - .6, start + (3.6 if kind == "step_diagram" else 2.8))
    if end - start < 1.5 or window[0] < 1.5:
        return plan
    # A semantic drawing of subtitle wrapping requires the matching source statement,
    # even when a reviewed manifest explicitly requests this renderer.
    if kind == "step_diagram" and not (
        re.search(r"\b(subtitle|caption)\b", clip.text, re.I)
        and re.search(r"\b(baris|kalimat)\b", quote, re.I)
        and re.search(r"\b(pisahkan|bagi|potong)\b", quote, re.I)
    ):
        plan["reason"] = "diagram_not_supported_by_transcript"
        return plan
    plan.update(enabled=True, reason="source_timed_editorial_insert", cues=[{
        "kind": kind, "start": round(start, 3), "end": round(end, 3),
        "source_frame_at": round(clip.start + start, 3), "quote": quote,
        "region": region, "region_reviewed": region is not None,
        "source_grounded": True, "inserted_timeline_seconds": 0,
    }])
    return plan


def load_motion_manifest(path: Path, clip) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text())
        rows = payload.get("clips", [])
        return next((row for row in rows if isinstance(row, dict)
                     and row.get("clip_start") == clip.start), None)
    except (ValueError, OSError, AttributeError, TypeError):
        # A malformed authored request must not silently become an automatic treatment.
        return {}


def _quote_svg(quote: str) -> str:
    cleaned = re.sub(r"[\x00-\x1f]", " ", quote)
    lines = textwrap.wrap(" ".join(cleaned.split()[:24]), 43, break_long_words=True)[:3]
    return "".join(f'<text x="48" y="{510 + i * 37}" font-size="29" fill="#f4f0e7">'
                   f'{escape(line)}</text>' for i, line in enumerate(lines))


def motion_frame_svg(cue: dict, image_uri: str, progress: float, *, image_region=None, detail_uri=None) -> str:
    """Native vector scene; only the photo crop comes from the actual source frame."""
    p = min(1., max(0., progress))
    heading = "ILUSTRASI LANGKAH" if cue["kind"] == "step_diagram" else "BEDAH MOMEN"
    body = ''
    if cue["kind"] == "step_diagram":
        # One persistent sheet travels; its overlong line becomes two legible lines.
        move = min(1., max(0., (p - .12) / .62))
        eased = move * move * (3 - 2 * move)
        x = 190 + 490 * eased
        body = (
            '<path d="M205 290 H685" fill="none" stroke="#526967" stroke-width="4" stroke-dasharray="8 12"/>'
            '<path d="M664 271 L686 290 L664 309" fill="none" stroke="#f2cc72" stroke-width="5"/>'
            '<text x="102" y="432" fill="#afc6be" font-size="23">KALIMAT PANJANG</text>'
            '<text x="608" y="432" fill="#66e0c1" font-size="23">BARIS TERPISAH</text>'
            f'<g transform="translate({x:.2f} 258) rotate({-4 + 4 * eased:.2f})">'
            '<rect x="-80" y="-110" width="176" height="246" rx="12" fill="#000000" opacity=".25"/>'
            '<rect x="-88" y="-120" width="176" height="246" rx="12" fill="#f4ecda"/>'
            '<path d="M-55 -83 H38" stroke="#133c3d" stroke-width="7"/>'
            '<circle cx="59" cy="-83" r="6" fill="#d9a83c"/>'
            + ('<path d="M-54 -14 H110" stroke="#bb5849" stroke-width="12"/>' if p < .5 else
               '<path d="M-54 -24 H52 M-54 12 H35" stroke="#187c6c" stroke-width="12"/>')
            + '<path d="M-54 62 H48 M-54 88 H24" stroke="#b9baac" stroke-width="5"/></g>'
        )
    else:
        # Same source moment is retained as a separate analysis picture, never as fake live speech.
        body = (
            '<rect x="42" y="96" width="816" height="382" rx="12" fill="#d9dac7"/>'
            f'<image href="{image_uri}" x="52" y="106" width="796" height="362" preserveAspectRatio="xMidYMid meet"/>'
            '<rect x="62" y="116" width="224" height="32" rx="6" fill="#092627"/>'
            '<text x="78" y="139" fill="#f2cc72" font-size="18">FRAME SUMBER DITAHAN</text>'
        )
        if cue["kind"] == "cutout_stop_motion" and image_region:
            x, y, w, h = image_region
            lift = min(1., max(0., (p - .2) / .5))
            # The selected rectangular object stays a source crop, not claimed segmentation.
            factor = min(796 / 960, 362 / 540)
            ox = 52 + (796 - 960 * factor) / 2 + x * factor
            oy = 106 + (362 - 540 * factor) / 2 + y * factor
            ow, oh = w * factor, h * factor
            px, py = ox * (1 - lift) + 596 * lift, oy * (1 - lift) + 141 * lift
            size = min(1., ow / 238) * (1 - lift) + lift
            body += (f'<rect x="{ox:.3f}" y="{oy:.3f}" width="{ow:.3f}" height="{oh:.3f}" '
                     'fill="none" stroke="#efc86d" stroke-width="3"/>')
            body += (
                f'<g transform="translate({px:.2f} {py:.2f}) rotate({-5 * lift:.2f}) scale({size:.4f})">'
                '<rect x="-9" y="-9" width="256" height="256" fill="#f4ecda" stroke="#edc96f" stroke-width="3"/>'
                + (f'<image href="{detail_uri}" width="238" height="238" preserveAspectRatio="xMidYMid meet"/>'
                   if detail_uri else
                   f'<svg width="238" height="238" viewBox="{x:.3f} {y:.3f} {w:.3f} {h:.3f}" preserveAspectRatio="xMidYMid meet">'
                   f'<image href="{image_uri}" width="960" height="540"/></svg>') + '</g>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="640" viewBox="0 0 900 640">'
        '<rect x="2" y="2" width="896" height="636" rx="22" fill="#0a2425" stroke="#54736a" stroke-width="3"/>'
        '<path d="M34 32 H94" stroke="#efc86d" stroke-width="6"/>'
        '<g font-family="DejaVu Sans">'
        f'<text x="114" y="43" fill="#efc86d" font-size="24" font-weight="bold">{heading}</text>'
        '<text x="48" y="79" fill="#9dbab1" font-size="18">RYUUNDY / CATATAN VISUAL</text>'
        + body + _quote_svg(cue["quote"]) + '</g></svg>'
    )


def prepare_motion_assets(plan: dict, source: Path, output_dir: Path, stem: str, *,
                          source_size: tuple[int, int], ffmpeg: str = "ffmpeg",
                          run_command: Callable | None = None) -> list[Path]:
    """Render finite 12-pose/sec vector inserts to ordinary 30fps H.264 assets."""
    if not plan.get("enabled"):
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = output_dir / '.ryuundy-motion'
    asset_dir.mkdir(exist_ok=True)
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)[:85]
    def execute(args):
        if run_command:
            run_command(args)
        else:
            subprocess.run(args, cwd=output_dir, check=True, capture_output=True, timeout=60)
    assets = []
    for index, cue in enumerate(plan["cues"]):
        prefix = f"{stem}_motion_{index}"
        frame = asset_dir / f"{prefix}.jpg"
        output = asset_dir / f"{prefix}.mp4"
        execute([ffmpeg, '-v', 'error', '-y', '-threads', '1', '-ss', str(cue['source_frame_at']),
                 '-i', str(source.resolve()), '-an', '-frames:v', '1', '-vf',
                 'scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:color=0x0b181a',
                 '-q:v', '3', str(frame.resolve())])
        uri = 'data:image/jpeg;base64,' + base64.b64encode(frame.read_bytes()).decode()
        region = None
        detail_uri = None
        detail = asset_dir / f'{prefix}_detail.jpg'
        if cue.get('region'):
            iw, ih = source_size
            scale = min(960 / iw, 540 / ih)
            rx, ry, rw, rh = cue['region']
            region = ((960 - iw * scale) / 2 + rx * iw * scale,
                      (540 - ih * scale) / 2 + ry * ih * scale,
                      rw * iw * scale, rh * ih * scale)
            cw, ch = max(2, int(rw * iw) // 2 * 2), max(2, int(rh * ih) // 2 * 2)
            cx, cy = int(rx * iw) // 2 * 2, int(ry * ih) // 2 * 2
            # Decode the reviewed crop from the original, not the small context thumbnail.
            execute([ffmpeg, '-v', 'error', '-y', '-threads', '1', '-ss', str(cue['source_frame_at']),
                     '-i', str(source.resolve()), '-an', '-frames:v', '1', '-vf',
                     f'crop={cw}:{ch}:{cx}:{cy},scale=480:480:force_original_aspect_ratio=decrease',
                     '-q:v', '2', str(detail.resolve())])
            detail_uri = 'data:image/jpeg;base64,' + base64.b64encode(detail.read_bytes()).decode()
        seconds = cue['end'] - cue['start']
        count = max(2, math.ceil(seconds * 12))
        frames = []
        try:
            for number in range(count):
                path = asset_dir / f'{prefix}_{number:03}.svg'
                path.write_text(motion_frame_svg(cue, uri, number / (count - 1),
                                                 image_region=region, detail_uri=detail_uri))
                frames.append(path)
            execute([ffmpeg, '-v', 'error', '-y', '-threads', '1', '-filter_threads', '1',
                     '-framerate', '12', '-i', str((asset_dir / f'{prefix}_%03d.svg').resolve()),
                     '-an', '-vf', 'fps=30', '-t', f'{seconds:.3f}', '-c:v', 'libx264',
                     '-threads', '1', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                     str(output.resolve())])
        finally:
            for path in frames:
                path.unlink(missing_ok=True)
            frame.unlink(missing_ok=True)
            detail.unlink(missing_ok=True)
        cue['asset'] = output.relative_to(output_dir).as_posix()
        cue['asset_prepared'] = True
        assets.append(output)
    return assets


def motion_overlay_filter(plan: dict) -> str:
    filters = []
    placement = plan.get('placement', {})
    width = max(200, min(900, int(placement.get('width', 900))))
    y = max(0, min(900, int(placement.get('y', 240))))
    for index, cue in enumerate(plan.get('cues', [])):
        name = str(cue.get('asset') or '')
        if not re.fullmatch(r'(?:\.ryuundy-motion/)?[a-zA-Z0-9_-]+\.mp4', name):
            continue
        start, end = cue['start'], cue['end']
        filters.append(
            f"split[rm_base{index}][rm_clock{index}];[rm_clock{index}]nullsink;"
            f"movie=filename='{name}',scale={width}:-2,setpts=PTS-STARTPTS+{start:.3f}/TB[rm_asset{index}];"
            f"[rm_base{index}][rm_asset{index}]overlay=x='(W-w)/2':"
            f"y='{y}+40*pow(max(0,1-(t-{start:.3f})/0.22),2)':"
            f"eof_action=pass:repeatlast=0:enable='gte(t,{start:.3f})*lt(t,{end:.3f})'"
        )
    return ','.join(filters)
