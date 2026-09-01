import json
import re

import pytest

import clipper
from clipper import (
    TranscriptSegment,
    UserFacingError,
    cleanup_intermediate,
    deterministic_original_rebuild_script,
    longest_verbatim_token_run,
    original_rebuild_script,
    original_rebuild_research_excerpt,
    parse_original_rebuild_response,
    require_creative_commons_metadata,
)
from llm import AIConfig


def source_segments():
    return [
        TranscriptSegment(
            start=0,
            end=20,
            text=(
                "Pembicara menjelaskan bahwa kebiasaan kecil perlu dilakukan secara konsisten. "
                "Ia memberi contoh mencatat pengeluaran harian, meninjau hasil setiap pekan, "
                "dan memperbaiki satu keputusan tanpa mengejar perubahan besar sekaligus."
            ),
        ),
        TranscriptSegment(
            start=20,
            end=40,
            text=(
                "Menurut pembicara, evaluasi rutin membantu seseorang melihat pola yang sebelumnya "
                "terlewat dan membuat langkah berikutnya menjadi lebih terukur."
            ),
        ),
    ]


def test_longest_verbatim_token_run_detects_only_contiguous_copy():
    source = "satu dua tiga empat lima enam tujuh delapan"

    assert longest_verbatim_token_run(source, "awal tiga empat lima akhir") == 3
    assert longest_verbatim_token_run(source, "delapan satu tujuh dua") == 1


def test_cleanup_removes_every_download_fallback_but_not_external_upload(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    external_upload = tmp_path / "upload.mp4"
    external_upload.write_bytes(b"caller-owned")
    for name in (
        "source.mp4",
        "source_embedded.webm",
        "source_hls.mp4",
        "source_fallback.mkv",
        "audio.wav",
    ):
        (work_dir / name).write_bytes(b"temporary")

    cleanup_intermediate(work_dir, external_upload)

    assert not list(work_dir.glob("source*"))
    assert not list(work_dir.glob("audio*.wav"))
    assert external_upload.read_bytes() == b"caller-owned"


def test_broadcaster_source_is_allowed_only_for_documented_research_rebuild():
    metadata = {
        "title": "Full Episode Program Televisi",
        "uploader": "Contoh TV Official",
        "license": "Standard YouTube License",
    }

    with pytest.raises(UserFacingError, match="Creative Commons"):
        require_creative_commons_metadata(metadata)

    require_creative_commons_metadata(
        metadata,
        research_only_original_rebuild=True,
    )


def test_original_rebuild_creates_audited_script_without_source_media(monkeypatch):
    # Keep this fixture focused on audit semantics; duration targeting has a
    # separate three-minute regression test in test_long_animate.py.
    monkeypatch.setenv("LONG_ANIMATE_TARGET_DURATION_SECONDS", "20")
    payload = {
        "title": "Kemajuan yang Bisa Diukur",
        "editorial_angle": "Mengubah nasihat umum menjadi eksperimen evaluasi mingguan.",
        "script": (
            "Perubahan terasa nyata ketika kita memperlakukannya seperti eksperimen kecil. "
            "Pilih satu tindakan yang bisa diamati, tentukan waktu pemeriksaan, lalu bandingkan "
            "hasilnya dengan kondisi awal. Catatan sederhana membantu menemukan pola, bukan sekadar "
            "mengandalkan ingatan. Dari sana, pertahankan langkah yang efektif dan ubah bagian yang "
            "belum bekerja. Kemajuan tidak harus dramatis; yang penting bukti perbaikannya terlihat."
        ),
        "source_claims_used": ["Evaluasi rutin membantu melihat pola."],
        "review_notes": ["Periksa kembali konteks contoh sebelum publikasi."],
    }
    monkeypatch.setattr(clipper, "chat_completion", lambda *_args, **_kwargs: json.dumps(payload))

    script, audit = original_rebuild_script(
        source_segments(),
        {
            "title": "Kebiasaan Kecil",
            "uploader": "Kreator Mandiri",
            "webpage_url": "https://www.youtube.com/watch?v=safe-source",
            "license": "Creative Commons",
        },
        AIConfig(enabled=True, base_url="http://local/v1", model="test-model"),
        "Saya ingin menunjukkan bahwa kemajuan harus dinilai melalui bukti kecil yang bisa diperiksa setiap minggu.",
    )

    assert script == payload["script"]
    assert audit["source_audio_in_output"] is False
    assert audit["source_video_in_output"] is False
    assert audit["source_voice_cloned"] is False
    assert audit["longest_verbatim_token_run"] <= audit["maximum_verbatim_token_run"]
    assert audit["source_transcript_sha256"] != audit["generated_script_sha256"]


def test_original_rebuild_never_falls_back_to_copied_transcript(monkeypatch):
    copied = " ".join(segment.text for segment in source_segments())
    calls = 0

    def copied_response(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return json.dumps(
            {
                "title": "Salinan",
                "editorial_angle": "Sudut palsu",
                "script": copied,
                "source_claims_used": [],
                "review_notes": [],
            }
        )

    monkeypatch.setattr(clipper, "chat_completion", copied_response)

    with pytest.raises(UserFacingError, match="output generik tidak dibuat"):
        original_rebuild_script(
            source_segments(),
            {"title": "Sumber"},
            AIConfig(enabled=True, base_url="http://local/v1", model="test-model"),
            "Saya ingin membahas kebiasaan sebagai eksperimen yang dapat diuji dan diperbaiki setiap minggu.",
        )

    assert calls == 6


def test_automatic_topic_rebuild_derives_angle_without_manual_form(monkeypatch):
    monkeypatch.setenv("LONG_ANIMATE_TARGET_DURATION_SECONDS", "20")
    payload = {
        "title": "Eksperimen Kecil",
        "editorial_angle": "Mengubah nasihat umum menjadi langkah yang dapat diuji.",
        "script": (
            "Nasihat berguna ketika bisa diuji dalam kehidupan sehari-hari. Mulailah dari satu "
            "tindakan kecil, catat kondisi awal, lalu tentukan waktu pemeriksaan. Catatan membantu "
            "memisahkan kemajuan nyata dari kesan sesaat. Jika hasilnya belum membaik, ubah satu "
            "bagian dan coba kembali. Perubahan akhirnya tumbuh dari bukti, bukan semangat sementara."
        ),
        "source_claims_used": ["Evaluasi rutin membantu melihat pola."],
        "review_notes": ["Periksa konteks sebelum publikasi."],
    }
    monkeypatch.setattr(clipper, "chat_completion", lambda *_args, **_kwargs: json.dumps(payload))

    script, audit = original_rebuild_script(
        source_segments(),
        {"title": "Kebiasaan Kecil", "uploader": "Sumber Riset"},
        AIConfig(enabled=True, base_url="http://local/v1", model="test-model"),
        "",
        automatic_topic_rebuild=True,
    )

    assert script == payload["script"]
    assert audit["human_creator_perspective_present"] is False
    assert audit["editorial_angle_generated_automatically"] is True
    assert audit["source_audio_in_output"] is False
    assert audit["source_video_in_output"] is False


def test_research_excerpt_samples_full_timeline_with_small_context():
    transcript = [
        TranscriptSegment(start=index, end=index + 1, text=f"Bagian unik nomor {index} membahas tema {index}.")
        for index in range(120)
    ]

    excerpt = original_rebuild_research_excerpt(transcript, max_chars=1200)

    assert len(excerpt) <= 1200
    assert "nomor 0" in excerpt
    assert "nomor 119" in excerpt
    sampled_numbers = [int(value) for value in re.findall(r"nomor (\d+)", excerpt)]
    assert any(45 <= value <= 75 for value in sampled_numbers)


def test_rebuild_response_accepts_indonesian_nested_fields_and_plain_text():
    nested = parse_original_rebuild_response(
        json.dumps(
            {
                "hasil": {
                    "naskah": "Ini naskah baru yang siap dibacakan.",
                    "sudut_editorial": "Menguji dampak praktis topik.",
                }
            }
        )
    )
    plain = parse_original_rebuild_response(
        "SUDUT: Pelajaran praktis\nNASKAH: Ini adalah voice-over baru tanpa format JSON."
    )

    assert nested["script"] == "Ini naskah baru yang siap dibacakan."
    assert nested["editorial_angle"] == "Menguji dampak praktis topik."
    assert plain["script"] == "Ini adalah voice-over baru tanpa format JSON."
    assert plain["editorial_angle"] == "Pelajaran praktis"


def test_automatic_rebuild_rejects_generic_fallback_when_model_is_malformed(monkeypatch):
    monkeypatch.setattr(clipper, "chat_completion", lambda *_args, **_kwargs: "{}")

    with pytest.raises(UserFacingError, match="output generik tidak dibuat"):
        original_rebuild_script(
            source_segments(),
            {"title": "Kebiasaan Kecil", "uploader": "Sumber Riset"},
            AIConfig(enabled=True, base_url="http://local/v1", model="test-model"),
            "",
            automatic_topic_rebuild=True,
        )


def test_automatic_rebuild_repairs_near_valid_draft_instead_of_using_generic_fallback(monkeypatch):
    monkeypatch.setenv("LONG_ANIMATE_TARGET_DURATION_SECONDS", "20")
    copied = " ".join(segment.text for segment in source_segments())
    repaired = (
        "Perubahan kecil lebih mudah dinilai ketika ukurannya jelas. Mulailah dengan mencatat satu keputusan "
        "harian dan kondisi yang menyertainya. Pada akhir pekan, baca kembali catatan itu untuk menemukan "
        "pola yang luput dari ingatan. Pilih satu bagian yang belum efektif, ubah langkahnya, lalu periksa "
        "hasil berikutnya. Evaluasi seperti ini menjadi alat belajar, bukan alasan menyalahkan diri. "
        "Keputusan selanjutnya pun berdiri di atas bukti, bukan kesan sesaat."
    )
    calls = 0

    def responses(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return copied if calls <= 4 else repaired

    monkeypatch.setattr(clipper, "chat_completion", responses)

    script, audit = original_rebuild_script(
        source_segments(),
        {"title": "Kebiasaan Kecil", "uploader": "Sumber Riset"},
        AIConfig(enabled=True, base_url="http://local/v1", model="test-model"),
        "",
        automatic_topic_rebuild=True,
    )

    assert script == repaired
    assert audit["generation_strategy"] == "targeted_quality_repair"
    assert audit["generated_word_count"] >= 33
    assert audit["longest_verbatim_token_run"] <= audit["maximum_verbatim_token_run"]


def test_deterministic_fallback_stays_inside_word_cap():
    script, angle = deterministic_original_rebuild_script(
        "Kebiasaan Kecil untuk Hidup Lebih Terukur",
        "evaluasi kebiasaan catatan perubahan konsisten keputusan",
        maximum_words=51,
    )

    assert 30 <= len(script.split()) <= 51
    assert angle
