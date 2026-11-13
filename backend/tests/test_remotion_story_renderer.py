import json
from pathlib import Path
from types import SimpleNamespace

import remotion_story_renderer as renderer


def _storyboard():
    return SimpleNamespace(
        scenes=[
            SimpleNamespace(
                index=1,
                duration=2.0,
                voice_duration=1.8,
                narration="Raka & Sari melihat tanda <aneh> di dinding @rumah.",
                narrative_role="cold_open",
                speech_words=[],
            ),
            SimpleNamespace(
                index=2,
                duration=3.0,
                voice_duration=2.7,
                narration="Mereka memilih memeriksa sumber suara bersama-sama.",
                narrative_role="payoff_conclusion",
                speech_words=[],
            ),
        ]
    )


def test_write_hypit_script_exports_semantic_scene_segments(tmp_path):
    output = renderer.write_hypit_script(_storyboard(), tmp_path / "story.svml")
    source = output.read_text(encoding="utf-8")

    assert '<import from="@hypit/script@1"/>' in source
    assert "<scene_01>" in source
    assert "<scene_02>" in source
    assert "<NARRATOR>" in source
    assert "Raka &amp; Sari" in source
    assert "&lt;aneh&gt;" in source
    assert r"\@rumah" in source


def test_remotion_manifest_projects_hypit_scenes_to_measured_timeline(
    tmp_path, monkeypatch
):
    renderer_dir = tmp_path / "renderer"
    (renderer_dir / "node_modules" / "remotion").mkdir(parents=True)
    (renderer_dir / "render.mjs").write_text("// test renderer\n", encoding="utf-8")
    monkeypatch.setattr(renderer, "RENDERER_DIR", renderer_dir)
    monkeypatch.setattr(renderer.shutil, "which", lambda command: "/usr/bin/node")
    monkeypatch.setattr(renderer, "_browser_executable", lambda: "")
    monkeypatch.setattr(renderer, "validate_hypit_script", lambda _path: None)

    image = tmp_path / "shot.png"
    video = tmp_path / "shot.mp4"
    image.write_bytes(b"image")
    video.write_bytes(b"video")
    output = tmp_path / "assembled.mp4"

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"rendered")
        return SimpleNamespace(returncode=0, stdout="REMOTION_PROGRESS:100", stderr="")

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    shots = [
        SimpleNamespace(
            duration=2.1,
            camera_motion="push_in",
            framing="close_up",
            on_screen_text="Tanda Aneh",
            title="Pembuka",
            narration="Narasi pembuka",
            color_mood="amber",
        ),
        SimpleNamespace(
            duration=3.0,
            camera_motion="pan_left",
            framing="wide",
            on_screen_text="",
            title="Jawaban",
            narration="Narasi jawaban",
            color_mood="blue",
        ),
    ]

    rendered, manifest_path = renderer.render_story_with_remotion(
        storyboard=_storyboard(),
        shots=shots,
        assets=[image, video],
        work_dir=tmp_path,
        scene_dir=tmp_path / "scenes",
        output_path=output,
        width=1080,
        height=1920,
        duration=5.0,
        transition_seconds=0.1,
        video_quality="high",
        burn_subtitles=True,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    composition = manifest["composition"]
    assert rendered == output
    assert manifest["hypit"]["scriptSurface"] == "@hypit/script@1"
    assert manifest["hypit"]["validatedByCli"] is True
    assert composition["captionsEnabled"] is True
    assert composition["watermarkAsset"].startswith("data:image/svg+xml;base64,")
    assert composition["watermarkBranding"]["style_version"] == 2
    assert composition["watermarkBranding"]["backplate_opacity"] == 0
    assert composition["shots"][0]["kind"] == "image"
    assert composition["shots"][1]["kind"] == "video"
    assert composition["shots"][1]["start"] == 2.0
    assert composition["shots"][1]["duration"] == 3.0
    assert composition["shots"][0]["narrativeRole"] == "cold_open"
    assert composition["shots"][0]["motionDesign"] == {
        "transition": "cut",
        "accentColor": "#F6C453",
        "titleStyle": "impact",
        "intensity": 1.12,
    }
    assert composition["shots"][1]["motionDesign"]["transition"] == "cross_dissolve"
    assert composition["shots"][0]["durationInFrames"] == 63
    assert composition["shots"][0]["bodyDurationInFrames"] == 60
    assert composition["shots"][1]["startFrame"] == 60
    assert composition["shots"][1]["transitionInFrames"] == 3
    assert composition["shots"][1]["motionDesign"]["accentColor"] == "#65B7FF"
    assert composition["shots"][0]["onScreenText"] == "Tanda Aneh"
    assert composition["shots"][1]["onScreenText"] == ""
    assert composition["scenes"][1]["role"] == "payoff_conclusion"
    assert composition["scenes"][0]["start"] == 0.0
    assert composition["scenes"][1]["start"] == 2.0
    assert composition["scenes"][0]["startFrame"] == 0
    assert composition["scenes"][1]["startFrame"] == 60
    assert composition["captionCues"]
    assert all(cue["endFrame"] > cue["startFrame"] for cue in composition["captionCues"])
    assert composition["motionDesign"]["deterministic"] is True
    assert composition["motionDesign"]["timelineSource"] == "measured-tts"
    assert composition["motionDesign"]["captionPresentation"] == "stable-phrase"


def test_caption_cues_use_measured_word_frames_without_one_frame_flicker():
    scene = SimpleNamespace(
        index=1,
        duration=4.0,
        voice_duration=3.2,
        narration="Satu aksi jelas lalu hasilnya terlihat nyata.",
        speech_words=[
            {"text": word, "start": index * 0.4, "end": (index + 1) * 0.4}
            for index, word in enumerate("Satu aksi jelas lalu hasilnya terlihat nyata.".split())
        ],
    )

    cues = renderer._caption_cues([scene], 30)

    assert cues[0]["startFrame"] == 0
    assert cues[-1]["endFrame"] <= 120
    assert all(cue["text"] for cue in cues)
    assert all(
        following["startFrame"] == current["endFrame"]
        for current, following in zip(cues, cues[1:])
    )


def test_motion_design_uses_a_small_role_aware_transition_grammar():
    brush = SimpleNamespace(transition="ink brush", shot_index=1)
    matched = SimpleNamespace(transition="match_action", shot_index=2)

    assert renderer._motion_transition(brush, "development", 2) == "cross_dissolve"
    assert renderer._motion_transition(matched, "development", 3) == "cut"
    assert renderer._motion_title_style("evidence_and_answer") == "proof"
    assert renderer._motion_accent("suasana hijau hutan", "seed") == "#63C995"


def test_viewer_overlay_never_falls_back_to_internal_scene_title():
    empty = SimpleNamespace(on_screen_text="", title="Adegan 3: Kegagalan Anjing Baik")
    leaked = SimpleNamespace(
        on_screen_text="Adegan 3: Kegagalan Anjing Baik",
        title="Kegagalan Anjing Baik",
    )
    authored = SimpleNamespace(on_screen_text="Kesetiaan Itu Diuji", title="Bagian 3")

    assert renderer._viewer_overlay_text(empty) == ""
    assert renderer._viewer_overlay_text(leaked) == ""
    assert renderer._viewer_overlay_text(authored) == "Kesetiaan Itu Diuji"


def test_picture_overlap_keeps_cut_boundary_and_short_insert_readable():
    shots = [
        {"startFrame": 0, "bodyDurationInFrames": 90, "motionDesign": {"transition": "cut"}},
        {"startFrame": 90, "bodyDurationInFrames": 5, "motionDesign": {"transition": "cross_dissolve"}},
        {"startFrame": 95, "bodyDurationInFrames": 60, "motionDesign": {"transition": "cross_dissolve"}},
        {"startFrame": 155, "bodyDurationInFrames": 45, "motionDesign": {"transition": "cut"}},
    ]
    renderer._apply_picture_overlaps(shots, 30, .4)

    assert [shot["startFrame"] for shot in shots] == [0, 90, 95, 155]
    assert shots[0]["durationInFrames"] == 92
    assert shots[1]["transitionInFrames"] == 2
    assert shots[1]["durationInFrames"] == 7
    assert shots[2]["durationInFrames"] == 60
    assert shots[3]["transitionInFrames"] == 0
    assert max(shot["startFrame"] + shot["durationInFrames"] for shot in shots) == 200


def test_long_film_captions_follow_cumulative_frames_without_drift():
    # Each duration rounds up individually. Summing those rounded durations
    # used to move captions by 18 frames over a 600-second film.
    scenes = [
        SimpleNamespace(index=index + 1, duration=16.65, voice_duration=16.4,
                        narration="Cahaya kecil memberi arah pulang.", speech_words=[])
        for index in range(36)
    ]
    cues = renderer._caption_cues(scenes, 30)
    assert cues[-1]["startFrame"] == round(35 * 16.65 * 30)
    assert cues[-1]["endFrame"] <= round(36 * 16.65 * 30)


def test_article_keeps_accepted_narration_and_ending_without_visual_directions(tmp_path):
    board = _storyboard()
    board.title = "Tanda di Dinding"
    path = renderer.write_story_article(board, tmp_path / "article.md")
    article = path.read_text()
    assert article.startswith("# Tanda di Dinding\n\n")
    assert board.scenes[-1].narration in article
    assert "<NARRATOR>" not in article
