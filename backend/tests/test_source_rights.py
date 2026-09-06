from source_rights import source_rights_review_reasons, source_rights_risk_reasons


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
