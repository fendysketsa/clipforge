import pytest

from source_rights import (
    is_reference_only_source_channel,
    source_media_reuse_rejection_reason,
    source_rights_review_reasons,
    source_rights_risk_reasons,
)


@pytest.mark.parametrize("identity", [
    {"channel_id": "UCY5eSpSrHUKeEAh7t4N81cQ"},
    {"channel": "  DW  Dokumenter "},
    {"uploader_id": "@DWdokumenter"},
    {"id": "SSU8Ko6wKm4"},
    {"webpage_url": "https://www.youtube.com/watch?v=SSU8Ko6wKm4&t=30"},
    {"original_url": "https://youtu.be/SSU8Ko6wKm4?si=example"},
    {"url": "https://youtube.com/shorts/SSU8Ko6wKm4"},
])
def test_dw_operator_refusal_survives_cc_and_old_trust(monkeypatch, identity):
    monkeypatch.setenv("YOUTUBE_TRUSTED_SOURCE_CHANNEL_IDS", "UCY5eSpSrHUKeEAh7t4N81cQ")
    source = {"title": "Pembahasan teknologi", "license": "Creative Commons", **identity}
    assert "operator melarang" in source_media_reuse_rejection_reason(source)
    assert any("operator melarang" in reason for reason in source_rights_risk_reasons(source))


def test_dw_refusal_does_not_match_mentions_or_unrelated_source():
    source = {"id": "abcdefghijk", "channel": "Kreator Mandiri", "title": "Membahas DW Dokumenter",
              "url": "https://unrelated.example/watch?v=SSU8Ko6wKm4"}
    assert source_media_reuse_rejection_reason(source) == ""


def test_claimed_tv_show_reupload_is_high_risk_even_when_metadata_says_cc():
    source = {
        "license": "Creative Commons Attribution license",
        "title": "Sintya Marisca - Islam Itu Indah 7 Feb 2k20",
        "uploader": "Sintya Marisca Support",
    }

    reasons = source_rights_risk_reasons(source)

    assert any("fan/support/reupload" in reason for reason in reasons)
    assert any("Content ID" in reason for reason in reasons)


def test_original_creator_style_metadata_is_not_blocked_without_risk_signals():
    source = {
        "license": "Creative Commons Attribution license",
        "title": "Kajian Akhlak Harian",
        "uploader": "Ustadz Pemilik Rekaman",
    }

    assert source_rights_risk_reasons(source) == []


def test_broadcaster_and_protected_audiovisual_formats_are_high_risk():
    source = {
        "title": "Full Episode Talk Show Inspirasi",
        "uploader": "Contoh TV Media Network",
    }

    reasons = source_rights_risk_reasons(source)

    assert any("program TV/film/musik" in reason for reason in reasons)
    assert any("broadcaster/media/studio" in reason for reason in source_rights_review_reasons(source))


def test_broadcaster_name_alone_is_review_not_automatic_block():
    source = {
        "license": "Creative Commons Attribution license",
        "title": "Diskusi Ekonomi Kreatif",
        "uploader": "Contoh Media Studio",
    }

    assert source_rights_risk_reasons(source) == []
    assert source_rights_review_reasons(source)


def test_explicit_english_commercial_reposting_prohibition_is_high_risk():
    source = {
        "title": "Extraordinary Happiness",
        "uploader": "Original Speaker Official",
        "description": (
            "Reposting our content or materials for commercial purposes or "
            "monetization is not permitted."
        ),
    }

    reasons = source_rights_risk_reasons(source)

    assert any("secara eksplisit melarang" in reason for reason in reasons)


def test_explicit_indonesian_monetized_reupload_prohibition_is_high_risk():
    source = {
        "title": "Kajian Harian",
        "uploader": "Kanal Resmi",
        "description": "Dilarang mengunggah ulang materi ini untuk tujuan monetisasi.",
    }

    reasons = source_rights_risk_reasons(source)

    assert any("komersial/monetisasi" in reason for reason in reasons)


def test_noncommercial_share_invitation_is_not_misread_as_a_prohibition():
    source = {
        "title": "Kajian Harian",
        "uploader": "Kanal Resmi",
        "description": "Silakan bagikan materi ini agar semakin bermanfaat.",
    }

    assert source_rights_risk_reasons(source) == []


def test_podcast_ploudrest_is_reference_only_not_a_production_source():
    source = {
        "title": "Klip percakapan artis",
        "uploader": "Podcast Ploudrest",
        "uploader_id": "@PodcastPloudrest",
    }

    assert is_reference_only_source_channel(source) is True
    assert any(
        "referensi editorial" in reason
        for reason in source_rights_risk_reasons(source)
    )


def test_sensasi_trends_recap_channel_is_reference_only_not_production_source():
    source = {
        "title": "Alur cerita film Korea - recap",
        "uploader": "Sensasi Trends",
        "uploader_id": "@sensasitrends9553",
        "channel_id": "UCb_er1PINGlJ_H6d9nfSjKA",
    }
    assert is_reference_only_source_channel(source) is True
    assert any("referensi editorial" in reason for reason in source_rights_risk_reasons(source))


def test_operator_can_add_reference_only_channel_by_immutable_id(monkeypatch):
    monkeypatch.setenv(
        "YOUTUBE_REFERENCE_ONLY_SOURCE_CHANNEL_IDS",
        "UC_REFERENCE_ONLY_EXAMPLE",
    )
    source = {
        "channel_id": "UC_REFERENCE_ONLY_EXAMPLE",
        "uploader": "Nama Kanal Bisa Berubah",
    }

    assert is_reference_only_source_channel(source) is True
    assert source_rights_risk_reasons(source)


def test_trusted_channel_override_requires_exact_channel_id(monkeypatch):
    monkeypatch.setenv("YOUTUBE_TRUSTED_SOURCE_CHANNEL_IDS", "UC_LICENSED_OWNER")
    source = {
        "channel_id": "UC_LICENSED_OWNER",
        "uploader": "Podcast Ploudrest",
        "uploader_id": "@PodcastPloudrest",
    }

    assert source_rights_risk_reasons(source) == []
