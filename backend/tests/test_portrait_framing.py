import json
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from portrait_framing import landscape_portrait_plan, portrait_source_filter


def speakers(**changes):
    values = dict(face_focus_xs=[.25, .75], face_focus_ys=[.5, .5],
                  person_count=2, simultaneous_frame_ratio=.8,
                  source_width=1920, source_height=1080)
    return SimpleNamespace(**{**values, **changes})


@pytest.mark.parametrize("size", [(1920, 1080), (3840, 2160), (1280, 720)])
def test_complete_landscape_is_preserved_at_any_resolution(size):
    plan = landscape_portrait_plan(size)
    assert plan["layout"] == "landscape_in_portrait"
    assert plan["full_source_frame_visible"]
    assert plan["panel_height"] == 576
    assert "crop=" not in portrait_source_filter(plan)


@pytest.mark.parametrize("profile", [
    speakers(simultaneous_frame_ratio=.2),
    speakers(person_count=3, face_focus_xs=[.2, .5, .8], face_focus_ys=[.5]*3),
    speakers(face_focus_xs=[.45, .55]),
    speakers(face_focus_xs=[float("nan"), .75]),
    speakers(source_width=1280),
])
def test_uncertain_or_large_group_retains_complete_wide_frame(profile):
    assert landscape_portrait_plan((1920, 1080), speaker_profile=profile)["full_source_frame_visible"]


def test_evidence_and_speakers_share_space_without_covering_each_other():
    plan = landscape_portrait_plan((1920, 1080), speaker_profile=speakers(),
                                  evidence_beats=[{"source": {"image": "article.png"}}])
    assert plan["layout"] == "landscape_in_portrait"
    assert plan["panel_y"] >= 930
    assert plan["panel_y"] + plan["panel_height"] <= 1920


def test_portrait_source_does_not_get_landscape_conversion():
    assert not landscape_portrait_plan((1080, 1920))["enabled"]


@pytest.mark.parametrize("split", [False, True])
def test_actual_render_keeps_both_people_and_simultaneous_time(split):
    source = (
        "color=red:s=1920x1080:r=4:d=1,"
        "drawbox=x=960:y=0:w=960:h=1080:color=blue:t=fill,"
        "drawbox=x=0:y=0:w=960:h=1080:color=lime:t=fill:enable='gte(t,0.5)',"
        "drawbox=x=960:y=0:w=960:h=1080:color=yellow:t=fill:enable='gte(t,0.5)'"
    )
    plan = landscape_portrait_plan((1920, 1080), speaker_profile=speakers() if split else None)
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-filter_threads", "1", "-f", "lavfi", "-i", source,
        "-vf", portrait_source_filter(plan), "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ], capture_output=True, check=True, timeout=20)
    frames = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 1920, 1080, 3)
    assert len(frames) == 4
    left, right = ((618, 540), (1218, 540)) if split else ((960, 50), (960, 1030))
    assert frames[0][left][0] > 180 and frames[0][left][1] < 50
    assert frames[0][right][2] > 180 and frames[0][right][0] < 50
    assert frames[3][left][1] > 180 and frames[3][left][0] < 50
    assert frames[3][right][0] > 180 and frames[3][right][1] > 180


def test_later_edit_effects_do_not_zoom_landscape_back_into_a_crop():
    from clipper import CameraAngleCue, clean_detail_edit_filter
    value = clean_detail_edit_filter(30, "hook.txt", preserve_source_geometry=True,
                                    camera_angle_cues=[CameraAngleCue("close_center", 5, 7, 50, 0, 0, "test")])
    assert "crop=1080:1920" not in value
    assert "scale=w=" not in value
    assert "y=140" in value
    assert "textfile='hook.txt'" in value


@pytest.mark.parametrize("split", [False, True])
def test_export_uses_one_source_even_when_legacy_companions_are_supplied(monkeypatch, tmp_path, split):
    import clipper
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=1920x1080:r=8:d=2",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "2",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-c:a", "aac", str(source),
    ], check=True, capture_output=True, timeout=15)
    for name in ["QURAN_OUTRO_ENABLED", "SHORTS_RENDER_QC_ENABLED", "SHORTS_ADAPTIVE_COLOR_ENABLED",
                 "SHORTS_CINEMATIC_FINISH_ENABLED", "SHORTS_CINEMATIC_SMOKE_ENABLED",
                 "SHORTS_EVIDENCE_RESEARCH_ENABLED", "CTA_VOICEOVER_ENABLED"]:
        monkeypatch.setenv(name, "false")
    monkeypatch.setattr(clipper, "detect_active_speaker_split_profile", lambda *_: speakers() if split else None)
    monkeypatch.setattr(clipper, "FENDY_CLIPPER_SHORTS_MIN_SECONDS", 1)
    clip = clipper.ClipCandidate(1, 0, 2, 2, 85, "Percakapan bersama", "test", "Selamat datang bersama kami.")
    companion = clipper.ClipCandidate(2, 100, 102, 2, 85, "Waktu lain", "test", "Klip lain.")
    output = clipper.export_clip(source, clip, [], tmp_path / "clips", False, "person",
                                 generate_assets=False, enforce_size=False, enhanced_edit=True,
                                 split_companion_clips=[companion, companion])
    data = json.loads(output.with_suffix(".json").read_text())
    assert data["layout"] == ("synchronized_conversation_split" if split else "landscape_in_portrait")
    assert data["portrait_framing"]["uses_other_timeline_clips"] is False
    assert data["portrait_framing"]["full_source_frame_visible"] is (not split)
    assert data["virtual_camera_angles"] == []
