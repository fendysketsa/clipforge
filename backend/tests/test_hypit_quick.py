from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import hypit_quick
from llm import AIConfig
from hypit_quick import (
    _dialogue_cues,
    _final_dialogue_start,
    _hypit_render_timeout,
    _plan_measured_dialogue,
    _process_exit_detail,
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


def test_hypit_renderer_uses_safe_single_worker_default():
    root = Path(__file__).resolve().parents[2]
    renderer = (root / "backend" / "remotion" / "render.mjs").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "process.env.REMOTION_CONCURRENCY || '1'" in renderer
    assert "REMOTION_CONCURRENCY: ${REMOTION_CONCURRENCY:-1}" in compose


def test_hypit_render_timeout_scales_to_five_minute_video(monkeypatch):
    monkeypatch.delenv("HYPIT_QUICK_RENDER_TIMEOUT_SECONDS", raising=False)

    assert _hypit_render_timeout(54.8) == 2766
    assert _hypit_render_timeout(300.0) == 13800


def test_hypit_render_failure_reports_process_signal():
    assert _process_exit_detail(1) == "exit code 1"
    assert "SIGKILL" in _process_exit_detail(-9)


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
        "mode": "editorial_single_line",
        "animateText": False,
        "holdUntilNextCue": True,
        "transition": "instant_content_swap",
    }
    assert manifest["composition"]["styleVersion"] == "editorial-explainer-v3"
    assert manifest["composition"]["midCta"]["title"] == "LIKE + KOMEN DULU"


def test_long_infographic_gives_natural_dialogue_and_render_time():
    prompt = (
        "/hypit infographic Mengapa Tumbuhan Bernapas Melalui Daun? | "
        "Tumbuhan juga membutuhkan oksigen untuk tetap hidup | "
        "Pada permukaan daun terdapat pori-pori kecil bernama stomata | "
        "Stomata menjadi tempat pertukaran oksigen dan karbon dioksida | "
        "Saat fotosintesis, daun menyerap karbon dioksida dan menghasilkan oksigen | "
        "Saat respirasi, tumbuhan menggunakan oksigen untuk menghasilkan energi | "
        "Tumbuhan bernapas siang dan malam, bukan hanya saat ada matahari | "
        "Kuis: Apakah tumbuhan juga bernapas pada malam hari? / YA / TIDAK"
    )

    plan = build_hypit_quick_plan(prompt)
    cues = _dialogue_cues(plan, _quick_reveal_times(plan))

    assert [beat.visual for beat in plan.beats] == [
        "plant_respiration",
        "stomata",
        "stomata",
        "photosynthesis",
        "plant_respiration",
        "plant_day_night",
        "quiz",
    ]
    assert "sunlight" in plan.beats[3].visual_action
    assert "sun to moon" in plan.beats[5].visual_action
    assert plan.duration == 59.8
    assert plan.duration <= 300.0
    assert cues[5].end - cues[5].start >= 5.0
    assert cues[-1].end - cues[-1].start >= 6.0
    assert _hypit_render_timeout(plan.duration) >= 2991


def test_five_minute_preview_keeps_every_scene_and_dialogue_inside_video():
    long_line = " ".join(["di"] * 65)
    plan = build_hypit_quick_plan(
        "/hypit infographic " + long_line + " | " + " | ".join([long_line] * 8)
    )
    reveals = _quick_reveal_times(plan)
    cues = _dialogue_cues(plan, reveals)

    assert plan.duration == 300
    assert len(reveals) == 8
    assert all(0 < reveal < _final_dialogue_start(plan) for reveal in reveals)
    assert all(a.end <= b.start for a, b in zip(cues, cues[1:]))
    assert cues[-1].end <= plan.duration


def test_measured_dialogue_extends_scene_instead_of_failing_natural_delivery(tmp_path):
    plan = build_hypit_quick_plan(
        "/hypit infographic Kenapa daun hidup? | Daun membutuhkan oksigen | Daun memiliki stomata"
    )
    source_durations = [12.0, 5.05, 7.34, 9.0]
    measured = _plan_measured_dialogue(plan, source_durations)
    reveals = _quick_reveal_times(measured)
    cues = _dialogue_cues(measured, reveals)

    assert plan.duration < measured.duration <= 300
    assert all(cue.end - cue.start >= source for cue, source in zip(cues, source_durations))
    assert all(a.end <= b.start for a, b in zip(cues, cues[1:]))
    assert cues[-1].end < measured.duration
    manifest = _quick_manifest(measured, tmp_path, tmp_path / "script.svml", [], reveals)
    assert manifest["composition"]["finalStart"] == cues[-1].start
    assert manifest["composition"]["dialogueTimeline"][-1]["end"] == cues[-1].end


def test_measured_five_minute_timeline_reclaims_holds_and_limits_tempo():
    plan = build_hypit_quick_plan(
        "/hypit infographic Tumbuhan | " + " | ".join(["Daun tetap hidup"] * 8)
    )
    durations = [33.0] * 10
    measured = _plan_measured_dialogue(plan, durations)
    cues = _dialogue_cues(measured, _quick_reveal_times(measured))

    assert measured.duration == 300
    assert all(source / (cue.end - cue.start) <= 1.35 for source, cue in zip(durations, cues))
    assert all(a.end <= b.start for a, b in zip(cues, cues[1:]))
    assert cues[-1].end <= 300
    with pytest.raises(hypit_quick.RemotionRenderError, match="5 menit"):
        _plan_measured_dialogue(plan, [60.0] * 10)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="requires FFmpeg")
def test_audio_pipeline_retimes_slow_source_and_keeps_complete_audio(tmp_path, monkeypatch):
    source = tmp_path / "slow-source.wav"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=7.34", str(source),
    ], check=True)
    monkeypatch.setenv("HYPIT_QUICK_TTS_ENABLED", "true")
    monkeypatch.setattr(hypit_quick, "_synthesize_dialogue_line", lambda *_: (
        source, {"provider": "fixture", "voice": "fixture", "rate": "+0%", "pitch": "+0Hz"}
    ))
    plan = build_hypit_quick_plan(
        "/hypit infographic Kenapa daun hidup? | Daun membutuhkan oksigen | Daun memiliki stomata"
    )
    measured, audio, cues, metadata = hypit_quick._prepare_dialogue_audio(
        plan, tmp_path, _quick_reveal_times(plan)
    )

    assert measured.duration > plan.duration
    assert audio.is_file()
    assert abs(hypit_quick._audio_duration(audio) - measured.duration) < .05
    assert all(cue["duration"] >= 7.30 and cue["tempo_fit"] == 1 for cue in cues)
    assert cues[-1]["start"] + cues[-1]["duration"] < measured.duration
    assert metadata["timing_model"] == "measured-speech"


def test_plant_scene_preserves_night_weather_and_sunlight_meaning():
    plan = build_hypit_quick_plan(
        "/hypit infographic Kehidupan tumbuhan | "
        "Pada malam hari pohon menggunakan oksigen untuk menghasilkan energi | "
        "Daun di kebun bergerak saat hujan | "
        "Cahaya matahari membantu fotosintesis pada daun"
    )
    assert plan.beats[0].visual == "plant_respiration"
    assert plan.beats[0].scene_time == "night"
    assert plan.beats[1].visual == "plant_life"
    assert plan.beats[1].scene_weather == "rain"
    assert plan.beats[2].visual == "photosynthesis"
    assert plan.beats[2].scene_time == "day"


def test_resume_preserves_measured_timeline_and_updates_regenerated_captions(tmp_path, monkeypatch):
    prompt = "/hypit infographic Tumbuhan hidup | Daun membutuhkan oksigen | Daun memiliki stomata"
    plan = build_hypit_quick_plan(prompt)
    measured = _plan_measured_dialogue(plan, [12.0, 7.0, 8.0, 10.0])
    work = tmp_path / f"hypit-{plan.slug}"
    clips = work / "clips"
    clips.mkdir(parents=True)
    output = clips / f"long_animate_{plan.slug}.mp4"
    output.write_bytes(b"existing-video")
    manifest_path = work / "infographic.remotion.json"
    manifest = _quick_manifest(measured, work / "public", work / "infographic.hypit.svml", [], _quick_reveal_times(measured))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    new_captions = [{"start": 0, "duration": 11.9, "text": measured.hook_narration}]

    def prepare(restored, _work, reveals, *, retime):
        assert retime is False
        assert restored.duration == measured.duration
        assert restored.dialogue_timeline == measured.dialogue_timeline
        assert reveals == _quick_reveal_times(measured)
        return restored, work / "dialogue.wav", new_captions, {"enabled": True}

    def mux(_source, pending, duration, *_args):
        assert duration == measured.duration
        pending.write_bytes(b"refreshed-video")
        return True

    monkeypatch.setattr(hypit_quick, "_prepare_dialogue_audio", prepare)
    monkeypatch.setattr(hypit_quick, "_mux_audio", mux)
    monkeypatch.setattr(hypit_quick, "_video_validation_error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(hypit_quick, "_write_result_artifacts", lambda *_args: {})
    monkeypatch.setattr(hypit_quick, "_write_quick_thumbnail_assets", lambda *_args: None)
    rendered, _ = hypit_quick.finalize_existing_hypit_quick_render(prompt, tmp_path)
    saved = json.loads(manifest_path.read_text())["composition"]

    assert rendered == output
    assert output.read_bytes() == b"refreshed-video"
    assert saved["dialogue"] == new_captions
    assert saved["dialogueTimeline"] == manifest["composition"]["dialogueTimeline"]
    assert saved["durationSeconds"] == measured.duration


def test_plant_infographic_uses_a_directed_living_world_component():
    renderer = (
        Path(__file__).resolve().parents[1] / "remotion" / "src" / "index.jsx"
    ).read_text(encoding="utf-8")
    plant_component = renderer.split(
        "const PlantWorldGraphic", 1
    )[1].split("const ConceptGraphic", 1)[0]

    assert "mode === 'stomata'" in plant_component
    assert "mode === 'photosynthesis'" in plant_component
    assert "mode === 'plant_respiration'" in plant_component
    assert "mode === 'plant_day_night'" in plant_component
    assert "antTravel" in plant_component
    assert "CO₂" in plant_component
    assert "O₂" in plant_component


def test_semantic_director_turns_technology_sentences_into_situations(tmp_path):
    prompt = (
        "/hypit infographic Kenapa HP Android Semakin Lemot? | "
        "HP baru terasa cepat, tetapi lama-lama mulai tersendat | "
        "Penyimpanan hampir penuh membuat sistem kekurangan ruang kerja | "
        "Aplikasi latar belakang membebani RAM | "
        "Cache bermasalah dan suhu panas menurunkan performa | "
        "Kosongkan penyimpanan, hapus aplikasi tidak perlu, update software, restart, dan hindari panas"
    )

    plan = build_hypit_quick_plan(prompt)
    assert [beat.visual for beat in plan.beats] == [
        "phone", "phone", "chip", "temperature", "process",
    ]
    assert plan.beats[0].situation == "transformation"
    assert plan.beats[1].scene_setting == "desk"
    assert plan.beats[1].scene_mood == "pressure"
    assert "storage_blocks" in plan.beats[1].environment_details
    assert plan.beats[2].camera == "macro_cutaway"
    assert plan.beats[2].situation == "cause_effect"
    assert "notification_cards" in plan.beats[2].environment_details
    assert plan.beats[3].scene_weather == "hot"
    assert "heat_waves" in plan.beats[3].environment_details
    assert plan.beats[4].scene_mood == "relief"

    manifest = _quick_manifest(
        plan,
        tmp_path,
        tmp_path / "technology.hypit.svml",
        [],
        _quick_reveal_times(plan),
    )
    directed = manifest["composition"]["beats"][2]
    assert directed["sceneSetting"] == "device_cutaway"
    assert directed["camera"] == "macro_cutaway"
    assert directed["situation"] == "cause_effect"
    assert directed["environmentDetails"] == [
        "notification_cards", "data_particles",
    ]


def test_generic_visuals_are_wrapped_in_directed_scene_context():
    renderer = (
        Path(__file__).resolve().parents[1] / "remotion" / "src" / "index.jsx"
    ).read_text(encoding="utf-8")

    assert "const DirectedSceneContext" in renderer
    assert "beat.sceneSetting" in renderer
    assert "beat.sceneTime" in renderer
    assert "beat.sceneWeather" in renderer
    assert "beat.sceneMood" in renderer
    assert "beat.situation" in renderer
    assert "beat.environmentDetails" in renderer
    assert "notification_cards" in renderer
    assert "storage_blocks" in renderer
    assert "heat_waves" in renderer


def test_motor_infographic_keeps_quiz_options_and_uses_specific_illustrations():
    prompt = (
        "/hypit infographic\n"
        "Kenapa motor matic bergetar saat digas?\n"
        "Kampas kopling CVT kotor bisa menyebabkan getaran.\n"
        "V-belt aus juga dapat mengganggu penyaluran tenaga.\n"
        "Getaran berlebihan menandakan komponen perlu diperiksa.\n"
        "Solusinya, lakukan pemeriksaan CVT secara berkala.\n"
        "Kuis: Komponen apa yang menyalurkan tenaga pada CVT?\n"
        "A. V-belt\n"
        "B. Busi\n"
        "Jawab di komentar!"
    )

    plan = build_hypit_quick_plan(prompt)

    assert [beat.visual for beat in plan.beats] == [
        "cvt", "cvt", "motorcycle", "cvt", "quiz",
    ]
    assert plan.beats[-1].quiz_options == ("V-belt", "Busi")
    assert "A. V-belt" not in [beat.narration for beat in plan.beats]
    assert plan.payoff == "JAWAB DI KOMENTAR!"


def test_motor_oil_and_gaming_internet_use_topic_specific_visual_worlds():
    oil = build_hypit_quick_plan(
        "/hypit infographic\n"
        "Apa akibat motor jarang ganti oli?\n"
        "Kualitas oli menurun seiring pemakaian.\n"
        "Gesekan mesin bisa meningkat saat pelumasan memburuk.\n"
        "Komponen mesin berisiko mengalami keausan lebih cepat.\n"
        "Solusinya, ganti oli sesuai jadwal buku manual motor."
    )
    gaming = build_hypit_quick_plan(
        "/hypit infographic\n"
        "Kenapa internet putus saat bermain game?\n"
        "Sinyal WiFi lemah bisa menyebabkan packet loss.\n"
        "Jaringan padat dapat meningkatkan ping secara drastis.\n"
        "Akibatnya, game lag atau terputus dari server.\n"
        "Solusinya, gunakan kabel LAN atau WiFi yang stabil."
    )

    assert {beat.visual for beat in oil.beats} == {"engine_oil"}
    assert {beat.visual for beat in gaming.beats} == {"gaming_network"}


def test_dialogue_caption_avoids_chromium_backdrop_compositor_flicker():
    renderer = (
        Path(__file__).resolve().parents[1] / "remotion" / "src" / "index.jsx"
    ).read_text(encoding="utf-8")
    caption_component = renderer.split(
        "const StableDialogueCaption", 1
    )[1].split("const MidVideoEngagement", 1)[0]

    assert "backdropFilter" not in caption_component
    assert "zIndex: 60" in caption_component
    assert "editorial_single_line" not in caption_component
    assert "opacity: 1" in caption_component
    assert "textShadow: '0 4px 0 #17204C" in caption_component


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
    assert plan.duration == 39.9
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
    assert plan.duration == 39.9
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
