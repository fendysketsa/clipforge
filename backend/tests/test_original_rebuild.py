import json

import pytest

import clipper
from clipper import (
    TranscriptSegment,
    UserFacingError,
    cleanup_intermediate,
    longest_verbatim_token_run,
    original_rebuild_script,
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

    with pytest.raises(UserFacingError, match="cukup orisinal"):
        original_rebuild_script(
            source_segments(),
            {"title": "Sumber"},
            AIConfig(enabled=True, base_url="http://local/v1", model="test-model"),
            "Saya ingin membahas kebiasaan sebagai eksperimen yang dapat diuji dan diperbaiki setiap minggu.",
        )

    assert calls == 2
