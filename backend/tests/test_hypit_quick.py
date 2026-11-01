from __future__ import annotations

import json

import hypit_quick
from llm import AIConfig
from hypit_quick import (
    _dialogue_cues,
    _quick_manifest,
    _quick_reveal_times,
    _probe_validation_error,
    _ranking_reveal_times,
    build_hypit_quick_plan,
    hypit_prompt_body,
    is_hypit_infographic_auto_prompt,
    is_hypit_infographic_prompt,
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


def test_hypit_infographic_routes_explicit_visual_explainer_and_preserves_claims(tmp_path):
    prompt = (
        "/hypit infographic Baterai HP tidak bocor tiba-tiba | "
        "Persentase baterai adalah perkiraan dari arus dan tegangan | "
        "Chip fuel gauge menghitung arus masuk dan keluar | "
        "Kurva tegangan baterai lithium hampir datar | "
        "Kuis: Saat baterai hampir habis, tegangannya bagaimana? / DATAR / TURUN TAJAM"
    )

    assert is_hypit_infographic_prompt(prompt) is True
    assert is_hypit_quick_prompt(prompt) is True
    plan = build_hypit_quick_plan(prompt)

    assert plan.slug.startswith("infographic-")
    assert [beat.visual for beat in plan.beats] == ["chart", "chip", "chart", "quiz"]
    assert plan.beats[-1].quiz_options == ("DATAR", "TURUN TAJAM")
    assert "fuel gauge" in plan.beats[1].narration
    assert plan.source_note.endswith("supplied by the user")

    reveal_times = _quick_reveal_times(plan)
    manifest = _quick_manifest(
        plan,
        tmp_path,
        tmp_path / "infographic.hypit.svml",
        [],
        reveal_times,
    )
    assert manifest["schema"] == "clipforge-hypit-infographic-v1"
    assert manifest["composition"]["template"] == "infographic"
    assert manifest["composition"]["beats"][1]["visual"] == "chip"
    assert manifest["composition"]["beats"][-1]["quizOptions"] == ["DATAR", "TURUN TAJAM"]
    assert manifest["composition"]["beats"][1]["visualSubject"]
    assert manifest["composition"]["beats"][1]["visualAction"]
    assert manifest["composition"]["beats"][1]["motion"] == "flow"
    assert manifest["composition"]["captionPresentation"] == {
        "mode": "persistent_cue_rail",
        "animateText": False,
        "holdUntilNextCue": True,
        "transition": "instant_content_swap",
    }


def test_hypit_infographic_requires_user_supplied_points():
    prompt = "/hypit infographic Jelaskan baterai HP"

    assert is_hypit_infographic_prompt(prompt) is True
    try:
        build_hypit_quick_plan(prompt)
    except ValueError as exc:
        assert "minimal dua poin" in str(exc)
    else:
        raise AssertionError("Prompt tanpa poin tidak boleh menghasilkan klaim generik")


def test_hypit_infographic_preview_uses_local_code_rendered_visuals():
    preview = quick_preview_payload(
        "/hypit explainer Kenapa indikator bisa berubah? | Sensor membaca arus masuk dan keluar | "
        "Grafik dipakai untuk melihat perubahan | Kuis: Sudah paham? / YA / BELUM"
    )

    assert preview["expansion"]["format"] == "hypit_infographic_explainer_v1"
    assert preview["image_provider"]["provider"] == "code_rendered_local"
    assert preview["scenes"][-1]["narrative_role"] == "interactive_payoff"


def _auto_prompt() -> str:
    return (
        "/hypit infographic auto\n"
        "Analogi: indikator baterai seperti petugas yang memperkirakan isi tangki.\n"
        "Teks: Ponsel memperkirakan sisa baterai dari arus yang masuk dan keluar serta perubahan tegangan. "
        "Tegangan baterai lithium berubah relatif landai pada sebagian besar rentang pemakaian. "
        "Perkiraan dapat dikoreksi ketika kondisi baterai berubah."
    )


def _auto_response(*, narration: str | None = None) -> str:
    return json.dumps(
        {
            "title": "Mengapa indikator baterai bisa berubah",
            "hook": "Indikator baterai bekerja seperti petugas yang memperkirakan isi tangki.",
            "payoff": "Angkanya adalah hasil perkiraan yang terus dikoreksi.",
            "beats": [
                {
                    "kicker": "BUKAN MELIHAT LANGSUNG",
                    "title": "MEMPERKIRAKAN SISA DAYA",
                    "narration": narration or "Ponsel memperkirakan sisa baterai seperti petugas memperkirakan isi tangki.",
                    "visual": "phone",
                    "source_quote": "Ponsel memperkirakan sisa baterai",
                    "quiz_options": [],
                },
                {
                    "kicker": "DATA MASUK",
                    "title": "ARUS DAN TEGANGAN",
                    "narration": "Arus yang masuk dan keluar serta perubahan tegangan menjadi dasar perkiraan.",
                    "visual": "chip",
                    "source_quote": "arus yang masuk dan keluar serta perubahan tegangan",
                    "quiz_options": [],
                },
                {
                    "kicker": "TITIK SULIT",
                    "title": "KURVANYA RELATIF LANDAI",
                    "narration": "Tegangan yang relatif landai membuat isi tangki tidak mudah diperkirakan langsung.",
                    "visual": "chart",
                    "source_quote": "Tegangan baterai lithium berubah relatif landai",
                    "quiz_options": [],
                },
            ],
        },
        ensure_ascii=False,
    )


def test_hypit_auto_infographic_expands_analogy_and_text_with_grounded_ai(monkeypatch):
    monkeypatch.setattr(hypit_quick, "chat_completion", lambda *_args, **_kwargs: _auto_response())
    config = AIConfig(enabled=True, base_url="http://llm.test/v1", model="test-model")

    assert is_hypit_infographic_auto_prompt(_auto_prompt()) is True
    plan = build_hypit_quick_plan(_auto_prompt(), config)

    assert plan.auto_expanded is True
    assert plan.analogy.startswith("indikator baterai")
    assert plan.slug.startswith("infographic-auto-")
    assert [beat.visual for beat in plan.beats] == ["phone", "chip", "chart"]
    assert plan.beats[0].source_quote == "Ponsel memperkirakan sisa baterai"
    assert plan.beats[0].visual_subject
    assert plan.beats[0].visual_action
    assert plan.beats[0].motion == "orbit"
    assert "tanpa riset eksternal" in plan.source_note


def test_hypit_infographic_selects_picture_first_visual_families():
    prompt = (
        "/hypit explainer Kenapa data tetap aman? | "
        "Enkripsi melindungi data saat berpindah di jaringan | "
        "Server terhubung dan mengirim sinyal ke pengguna | "
        "Tim membandingkan pilihan sebelum menentukan tujuan"
    )

    plan = build_hypit_quick_plan(prompt)

    assert [beat.visual for beat in plan.beats] == ["security", "network", "comparison"]
    assert all(beat.visual_subject for beat in plan.beats)
    assert all(beat.visual_action for beat in plan.beats)
    assert all(beat.motion in {"assemble", "flow", "orbit", "transform", "compare", "pulse", "zoom"} for beat in plan.beats)


def test_hypit_auto_infographic_repairs_new_numbers_from_ai(monkeypatch):
    monkeypatch.setattr(
        hypit_quick,
        "chat_completion",
        lambda *_args, **_kwargs: _auto_response(
            narration="Ponsel langsung mengurangi perkiraan baterai sebanyak 50 persen."
        ),
    )
    config = AIConfig(enabled=True, base_url="http://llm.test/v1", model="test-model")

    plan = build_hypit_quick_plan(_auto_prompt(), config)

    assert "50" not in plan.beats[0].narration
    assert plan.beats[0].narration == "Inti penjelasannya: Ponsel memperkirakan sisa baterai"


def test_hypit_auto_infographic_repairs_weak_paraphrase_instead_of_failing(monkeypatch):
    weak = json.loads(_auto_response())
    weak["beats"][1]["narration"] = (
        "Mesin ajaib bekerja diam-diam dengan pendekatan misterius yang sulit ditebak siapa pun."
    )
    monkeypatch.setattr(
        hypit_quick,
        "chat_completion",
        lambda *_args, **_kwargs: json.dumps(weak, ensure_ascii=False),
    )
    config = AIConfig(enabled=True, base_url="http://llm.test/v1", model="test-model")

    plan = build_hypit_quick_plan(_auto_prompt(), config)

    assert plan.beats[1].narration == "arus yang masuk dan keluar serta perubahan tegangan"
    assert "misterius" not in plan.beats[1].narration


def test_hypit_auto_infographic_recovers_invalid_source_quote(monkeypatch):
    weak = json.loads(_auto_response())
    weak["beats"][1]["source_quote"] = "kutipan ini tidak ada"
    monkeypatch.setattr(
        hypit_quick,
        "chat_completion",
        lambda *_args, **_kwargs: json.dumps(weak, ensure_ascii=False),
    )
    config = AIConfig(enabled=True, base_url="http://llm.test/v1", model="test-model")

    plan = build_hypit_quick_plan(_auto_prompt(), config)

    assert plan.beats[1].source_quote in _auto_prompt()
    assert "arus yang masuk dan keluar" in plan.beats[1].source_quote


def test_hypit_auto_infographic_repairs_too_few_beats_locally(monkeypatch):
    short = json.loads(_auto_response())
    short["beats"] = short["beats"][:2]
    monkeypatch.setattr(
        hypit_quick,
        "chat_completion",
        lambda *_args, **_kwargs: json.dumps(short, ensure_ascii=False),
    )
    config = AIConfig(enabled=True, base_url="http://llm.test/v1", model="test-model")

    plan = build_hypit_quick_plan(_auto_prompt(), config)

    assert 3 <= len(plan.beats) <= 7
    assert plan.duration == 39.0
    assert plan.planning_mode == "local_fallback"
    assert plan.title == "CARA PONSEL MEMPERKIRAKAN SISA BATERAI"
    assert all(beat.source_quote in _auto_prompt() for beat in plan.beats)


def test_hypit_auto_infographic_falls_back_when_provider_returns_invalid_json(monkeypatch):
    monkeypatch.setattr(
        hypit_quick,
        "chat_completion",
        lambda *_args, **_kwargs: "bukan json",
    )
    config = AIConfig(enabled=True, base_url="http://llm.test/v1", model="test-model")

    plan = build_hypit_quick_plan(_auto_prompt(), config)

    assert len(plan.beats) >= 3
    assert plan.planning_mode == "local_fallback"


def test_hypit_auto_infographic_works_without_ai_configuration():
    plan = build_hypit_quick_plan(_auto_prompt())

    assert len(plan.beats) >= 3
    assert plan.duration == 39.0
    assert plan.planning_mode == "local_fallback"
    assert plan.beats[0].title == "ARUS MASUK DAN KELUAR"
    assert plan.beats[1].title == "TEGANGAN BERUBAH RELATIF LANDAI"
    assert plan.beats[2].title == "PERKIRAAN DAPAT DIKOREKSI"


def test_hypit_auto_infographic_preflight_does_not_call_ai(monkeypatch):
    monkeypatch.setattr(
        hypit_quick,
        "chat_completion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("AI tidak boleh dipanggil saat preflight")),
    )

    preview = quick_preview_payload(_auto_prompt())

    assert preview["expansion"]["format"] == "hypit_infographic_auto_explainer_v1"
    assert preview["expansion"]["pending"] is True
    assert preview["image_provider"]["provider"] == "code_rendered_local"


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
