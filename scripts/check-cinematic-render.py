#!/usr/bin/env python3
"""Render a real dissolve from two supplied images and check every encoded frame."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from remotion_story_renderer import render_story_with_remotion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    board = SimpleNamespace(scenes=[
        SimpleNamespace(index=1, duration=4, voice_duration=0, narration="Mercusuar memberi arah.",
                        narrative_role="cold_open", speech_words=[]),
        SimpleNamespace(index=2, duration=4, voice_duration=0, narration="Perjalanan dilanjutkan.",
                        narrative_role="development", speech_words=[]),
    ])
    shots = [SimpleNamespace(
        index=i, scene_index=i, shot_index=1, duration=4.4 if i == 1 else 4,
        camera_motion="push_in", framing="wide", subject_placement="center", camera_angle="eye_level",
        transition="hard_cut" if i == 1 else "cinematic_dissolve", on_screen_text="",
        narration="", color_mood="navy and amber", title="Dissolve check",
    ) for i in (1, 2)]
    movie, manifest = render_story_with_remotion(
        storyboard=board, shots=shots, assets=[args.first.resolve(), args.second.resolve()],
        work_dir=root, scene_dir=root, output_path=root / "dissolve-check.mp4",
        width=1280, height=720, duration=8, transition_seconds=.4,
        video_quality="high", burn_subtitles=False,
    )
    capture = cv2.VideoCapture(str(movie))
    luminance = []
    boundary = []
    count = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        luminance.append(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()))
        if count in (119, 120):
            boundary.append(frame.astype(np.float32))
        count += 1
    capture.release()
    if count != 240 or len(boundary) != 2:
        raise RuntimeError(f"Expected 240 decoded frames and both boundary frames, got {count}.")
    boundary_change = float(np.mean(np.abs(boundary[1] - boundary[0])))
    transition_luma = luminance[118:134]
    if min(luminance) < 3 or boundary_change > 10:
        raise RuntimeError("Black frame or an abrupt picture handoff in encoded dissolve.")
    manifest_value = json.loads(manifest.read_text())["composition"]
    if manifest_value["shots"][0]["durationInFrames"] != 132:
        raise RuntimeError("Outgoing picture lost its 12-frame overlap handle.")
    report = {"passed": True, "decoded_frames": count, "fps": 30, "duration_seconds": count / 30,
              "minimum_frame_luminance": min(luminance), "boundary_mean_absolute_difference": boundary_change,
              "transition_frame_luminance": transition_luma, "overlap_frames": 12,
              "audio_review": "not_applicable_silent_picture_test"}
    (root / "dissolve-qc.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
