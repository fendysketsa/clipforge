"""Keep wide shots readable in a portrait export, with synchronous speaker views."""
from __future__ import annotations

import math


def _even(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def landscape_portrait_plan(source_size, *, speaker_profile=None, evidence_beats=None) -> dict:
    if not source_size or source_size[0] <= source_size[1]:
        return {"enabled": False}
    width, height = source_size
    beats = evidence_beats or []
    plan = {
        "enabled": True, "layout": "landscape_in_portrait",
        "source_width": width, "source_height": height,
        "canvas_width": 1080, "canvas_height": 1920,
        "preserve_source_aspect_ratio": True, "uses_other_timeline_clips": False,
        "all_panels_synchronized": True, "full_source_frame_visible": True,
        "panel_width": 1024, "panel_height": _even(1024 * height / width),
        "reason": "keep_complete_landscape_shot",
    }
    plan["panel_y"] = _even((1920 - plan["panel_height"]) / 2)
    # Evidence panels occupy the upper region. Keep a captured source image
    # above the moving landscape shot, and preserve a rail for captions below.
    if any(b.get("source", {}).get("image") for b in beats if b.get("source")):
        plan["panel_y"] = min(960, 1920 - plan["panel_height"])
    if speaker_profile is None or beats:
        return plan
    xs = speaker_profile.face_focus_xs
    ys = speaker_profile.face_focus_ys
    # Two steady, simultaneously visible faces can become two landscape
    # close-ups. Larger groups and uncertain detections retain the wide shot.
    if (speaker_profile.person_count != 2 or len(xs) != 2 or len(ys) != 2
            or speaker_profile.simultaneous_frame_ratio < .60
            or not all(math.isfinite(v) and 0 < v < 1 for v in [*xs, *ys])
            or xs[1] - xs[0] < .35
            or (speaker_profile.source_width, speaker_profile.source_height) != source_size):
        return plan
    crop_width = _even(min(width / 2, height * 16 / 9))
    crop_height = _even(crop_width * 9 / 16)
    crops = []
    for x, y in zip(xs, ys):
        crop_x = _even(max(0, min(width - crop_width, x * width - crop_width / 2)))
        crop_y = _even(max(0, min(height - crop_height, y * height - crop_height / 2)))
        # Zero is a valid crop origin; _even otherwise has a minimum of two.
        if x * width <= crop_width / 2:
            crop_x = 0
        if y * height <= crop_height / 2:
            crop_y = 0
        crops.append([crop_width, crop_height, crop_x, crop_y])
    # Never fill two panels with substantially the same crop.
    if crops[1][2] - crops[0][2] < crop_width * .65:
        return plan
    plan.update(layout="synchronized_conversation_split", speaker_crops=crops,
                panel_height=576, panel_ys=[330, 930], full_source_frame_visible=False,
                reason="two_people_visible_together_in_same_source_frames")
    return plan


def portrait_source_filter(plan: dict) -> str:
    """One video input and one original dialogue track; no time shifts."""
    if plan["layout"] == "landscape_in_portrait":
        return (
            f"scale=1024:{plan['panel_height']}:force_original_aspect_ratio=decrease:"
            "force_divisible_by=2:flags=lanczos,"
            f"pad=1080:1920:(ow-iw)/2:{plan['panel_y']}:color=0x050B0A,setsar=1"
        )
    crops = plan["speaker_crops"]
    branches = ["split=2[conversation_left][conversation_right]"]
    for index, (label, crop, y) in enumerate(zip(
        ["conversation_left", "conversation_right"], crops, plan["panel_ys"]
    )):
        crop_width, crop_height, crop_x, crop_y = crop
        tail = (f",pad=1080:1920:28:{y}:color=0x050B0A[conversation_canvas]"
                if index == 0 else "[conversation_panel]")
        branches.append(
            f"[{label}]crop={crop_width}:{crop_height}:{crop_x}:{crop_y},"
            "scale=1024:576:force_original_aspect_ratio=decrease:"
            "force_divisible_by=2:flags=lanczos,"
            "pad=1024:576:(ow-iw)/2:(oh-ih)/2:color=0x050B0A,setsar=1" + tail
        )
    branches.append("[conversation_canvas][conversation_panel]overlay=28:930:shortest=1")
    return ";".join(branches)
