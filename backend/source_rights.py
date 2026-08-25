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


def source_rights_risk_reasons(info: dict[str, Any]) -> list[str]:
    """Flag URL sources whose CC label is not a reliable chain-of-title signal.

    A YouTube uploader can select a CC license even when the audiovisual work
    contains a broadcaster, film, music, or another creator's recording. These
    signals are conservative workflow gates, not a legal determination.
    """
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
    if any(
        re.search(pattern, uploader, re.I)
        for pattern in SOURCE_RIGHTS_BROADCASTER_PATTERNS
    ):
        reasons.append("sumber terindikasi milik broadcaster/media/studio")

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
