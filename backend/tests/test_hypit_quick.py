from __future__ import annotations

from hypit_quick import (
    _probe_validation_error,
    build_hypit_quick_plan,
    is_hypit_quick_prompt,
    quick_preview_payload,
)


def test_hypit_quick_recognizes_documented_ranking_prompt():
    prompt = "/hypit Make a ranking video that puts Hypit in S tier."

    assert is_hypit_quick_prompt(prompt) is True
    plan = build_hypit_quick_plan(prompt)

    assert plan.items[-1].tier == "S"
    assert plan.items[-1].label == "HYPIT"
    assert plan.duration == 24.0
    assert "HYPIT" in plan.payoff


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


def test_hypit_quick_probe_gate_rejects_partial_or_wrong_media():
    valid = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
            {"codec_type": "audio", "codec_name": "aac"},
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
    assert "durasi" in _probe_validation_error(
        {**valid, "format": {"duration": "8.0"}}, duration=24.0, require_audio=True
    )
