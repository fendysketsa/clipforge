from __future__ import annotations

import os
import re
from typing import Any


SOURCE_RIGHTS_REUPLOAD_PATTERNS = (
    r"\bfans?\b",
    r"\bfanbase\b",
    r"\bsupport(?:er)?\b",
    r"\bre[ -]?upload\b",
    r"\b(?:video )?clips?\b",
    r"\bkompilasi\b",
    r"\bcompilation\b",
    r"\barsip\b",
    r"\barchive\b",
)
SOURCE_RIGHTS_PROTECTED_FORMAT_PATTERNS = (
    r"\bfull episode\b",
    r"\bepisode\s*\d*\b",
    r"\b(?:eps|ep)\.?\s*\d+\b",
    r"\btalk[ -]?show\b",
    r"\b(?:program|acara|tayangan)\s+(?:tv|televisi)\b",
    r"\b(?:tv|televisi)\s+(?:show|program|series|serial)\b",
    r"\bsinetron\b",
    r"\b(?:film|movie)\s+(?:penuh|full|scene|clip)\b",
    r"\bofficial trailer\b",
    r"\b(?:official )?(?:music video|video musik)\b",
)
SOURCE_RIGHTS_BROADCASTER_PATTERNS = (
    r"\b(?:tv|televisi)\b",
    r"\bbroadcast(?:ing)?\b",
    r"\bmedia\b",
    r"\bnetwork\b",
    r"\bstudios?\b",
)


def trusted_source_channel_ids() -> set[str]:
    """Return operator-approved channels with documented reuse rights."""
    return {
        value.strip()
        for value in os.environ.get("YOUTUBE_TRUSTED_SOURCE_CHANNEL_IDS", "").split(",")
        if value.strip()
    }


def source_channel_ids(info: dict[str, Any]) -> set[str]:
    return {
        str(info.get(key) or "").strip()
        for key in ("channel_id", "uploader_id")
        if str(info.get(key) or "").strip()
    }


def is_trusted_source_channel(info: dict[str, Any]) -> bool:
    """Match immutable Channel IDs exactly; mutable display names are unsafe."""
    configured = trusted_source_channel_ids()
    return bool(configured and source_channel_ids(info) & configured)


def source_rights_review_reasons(info: dict[str, Any]) -> list[str]:
    """Return soft signals that need review but are not proof of infringement."""
    if is_trusted_source_channel(info):
        return []
    uploader = re.sub(
        r"\s+",
        " ",
        str(info.get("uploader") or info.get("channel") or ""),
    ).strip().casefold()
    if any(
        re.search(pattern, uploader, re.I)
        for pattern in SOURCE_RIGHTS_BROADCASTER_PATTERNS
    ):
        return [
            "nama kanal terindikasi broadcaster/media/studio; lisensi dan kepemilikan seluruh elemen tetap perlu direview"
        ]
    return []


def source_rights_risk_reasons(info: dict[str, Any]) -> list[str]:
    """Flag URL sources whose CC label is not a reliable chain-of-title signal.

    A YouTube uploader can select a CC license even when the audiovisual work
    contains a broadcaster, film, music, or another creator's recording. These
    signals are conservative workflow gates, not a legal determination.
    """
    if is_trusted_source_channel(info):
        return []

    title = re.sub(r"\s+", " ", str(info.get("title") or "")).strip().casefold()
    uploader = re.sub(
        r"\s+",
        " ",
        str(info.get("uploader") or info.get("channel") or ""),
    ).strip().casefold()
    reasons: list[str] = []
    if any(re.search(pattern, uploader, re.I) for pattern in SOURCE_RIGHTS_REUPLOAD_PATTERNS):
        reasons.append("uploader terindikasi akun fan/support/reupload/arsip, bukan pemegang hak utama")
    if any(
        re.search(pattern, title, re.I)
        for pattern in SOURCE_RIGHTS_PROTECTED_FORMAT_PATTERNS
    ):
        reasons.append("judul terindikasi program TV/film/musik atau cuplikan karya audiovisual")
    configured_terms = [
        value.strip().casefold()
        for value in os.environ.get(
            "YOUTUBE_COPYRIGHT_HIGH_RISK_TERMS",
            "islam itu indah,transcorp,trans tv,trans7",
        ).split(",")
        if value.strip()
    ]
    combined = f"{title} {uploader}".strip()
    matched_terms = [term for term in configured_terms if term in combined]
    if matched_terms:
        reasons.append(
            "sumber cocok dengan daftar program/pemegang hak berisiko Content ID: "
            + ", ".join(matched_terms[:3])
        )
    return list(dict.fromkeys(reasons))
