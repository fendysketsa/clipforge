from __future__ import annotations

from hypit_quick import (
    _dialogue_cues,
    _probe_validation_error,
    _ranking_reveal_times,
    build_hypit_quick_plan,
    hypit_prompt_body,
    is_hypit_quick_prompt,
    quick_preview_payload,
)


def test_hypit_quick_recognizes_documented_ranking_prompt():
    prompt = "/hypit Make a ranking video that puts Hypit in S tier."

    assert is_hypit_quick_prompt(prompt) is True
    plan = build_hypit_quick_plan(prompt)

    assert plan.items[-1].tier == "S"
    assert plan.items[-1].label == "HYPIT"
    assert plan.duration == 30.0
    assert "HYPIT" in plan.payoff


def test_hypit_long_story_is_not_misrouted_to_ranking_template():
    story = (
        "/hypit HP Android 2026 makin canggih atau makin bikin pusing? "
        "Baterai cepat habis, perangkat panas, aplikasi berat, dan pengguna "
        "sebenarnya hanya menginginkan perangkat yang dapat diandalkan."
    )

    assert is_hypit_quick_prompt(story) is False
    assert hypit_prompt_body(story).startswith("HP Android 2026")
    assert "/hypit" not in hypit_prompt_body(story)


def test_hypit_quick_php_preset_is_dated_and_fact_scoped():
    plan = build_hypit_quick_plan(
        "/hypit Buat video ranking tentang patch kritis PHP yang menjadi isu hari ini."
    )

    assert plan.fact_checked_on == "2026-10-24"
    assert "8.5.12" in plan.items[-1].label
    assert "vendor" in plan.footer.casefold()
    assert any("8.1" in item.label for item in plan.items)


def test_hypit_quick_preview_needs_no_image_provider():
    preview = quick_preview_payload(
        "/hypit Make a ranking video that puts Hypit in S tier."
    )

    assert preview["image_provider"]["ready"] is True
    assert preview["image_provider"]["provider"] == "code_rendered_local"
    assert len(preview["scenes"]) == 3
    assert preview["production_script"].startswith("/hypit")
    assert preview["expansion"]["format"] == "hypit_quick_ranking_v2"
    assert "continuous camera handoff" in preview["director_bible"]


def test_hypit_quick_dialogue_alternates_two_indonesian_roles_inside_visual_beats():
    plan = build_hypit_quick_plan(
        "/hypit Make a ranking video that puts Hypit in S tier."
    )
    reveal_times = _ranking_reveal_times(plan)
    cues = _dialogue_cues(plan, reveal_times)

    assert [cue.speaker for cue in cues] == [
        "HOST",
        "CO-HOST",
        "HOST",
        "CO-HOST",
        "HOST",
        "CO-HOST",
    ]
    assert cues[0].text == plan.hook_narration
    assert cues[-1].text == plan.payoff_narration
    assert all(cue.end <= next_cue.start for cue, next_cue in zip(cues, cues[1:]))
    assert cues[-1].end <= plan.duration
    assert cues[-1].start == plan.duration - 5.5
    assert max(
        later - earlier for earlier, later in zip(reveal_times, reveal_times[1:])
    ) >= 4.8


def test_hypit_quick_probe_gate_rejects_partial_or_wrong_media():
    valid = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
            {"codec_type": "audio", "codec_name": "aac", "duration": "24.033"},
        ],
        "format": {"duration": "24.033"},
    }

    assert _probe_validation_error(valid, duration=24.0, require_audio=True) is None

    wrong_size = {**valid, "streams": [{**valid["streams"][0], "width": 720}]}
    assert "1080x1920" in _probe_validation_error(
        wrong_size, duration=24.0, require_audio=False
    )
    assert "audio" in _probe_validation_error(
        {**valid, "streams": [valid["streams"][0]]}, duration=24.0, require_audio=True
    )
    assert "berhenti" in _probe_validation_error(
        {
            **valid,
            "streams": [
                valid["streams"][0],
                {"codec_type": "audio", "codec_name": "aac", "duration": "21.1"},
            ],
        },
        duration=24.0,
        require_audio=True,
    )
    assert "durasi" in _probe_validation_error(
        {**valid, "format": {"duration": "8.0"}}, duration=24.0, require_audio=True
    )
