from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse


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
SOURCE_RIGHTS_REPUBLISH_PATTERNS = (
    r"\bre[ -]?post(?:ing|ed)?\b",
    r"\bre[ -]?upload(?:ing|ed)?\b",
    r"\bupload ulang\b",
    r"\bunggah ulang\b",
    r"\bmengunggah ulang\b",
    r"\bmemublikasikan ulang\b",
)
SOURCE_RIGHTS_PROHIBITION_PATTERNS = (
    r"\bnot (?:allowed|permitted|authorized)\b",
    r"\bprohibited\b",
    r"\bforbidden\b",
    r"\bdilarang\b",
    r"\btidak (?:diizinkan|diperbolehkan|diperkenankan)\b",
)
SOURCE_RIGHTS_COMMERCIAL_PATTERNS = (
    r"\bcommercial(?:ly)?\b",
    r"\bkomersial\b",
    r"\bmoneti[sz](?:e|ed|ation|asi)\b",
)

# Channels in this registry are useful for editorial research, but are not
# accepted as production sources. Keep the exact public handle/name narrowly
# scoped; immutable Channel IDs supplied by the operator remain the preferred
# identifier once they are known.
BUILTIN_REFERENCE_ONLY_CHANNEL_IDS = {"UCb_er1PINGlJ_H6d9nfSjKA"}
BUILTIN_REFERENCE_ONLY_HANDLES = {"@podcastploudrest", "@sensasitrends9553"}
BUILTIN_REFERENCE_ONLY_NAMES = {"podcast ploudrest", "sensasi trends"}

# Operator instruction, 25 November 2026: the partially blocked DW Short must
# not seed more clips. This explicit refusal overrides older rights attestations
# and trusted-channel settings; it is not a claim about every broadcaster.
NO_MEDIA_REUSE_CHANNEL_IDS = {"UCY5eSpSrHUKeEAh7t4N81cQ"}
NO_MEDIA_REUSE_CHANNEL_NAMES = {"dw dokumenter"}
NO_MEDIA_REUSE_HANDLES = {"@dwdokumenter"}
NO_MEDIA_REUSE_VIDEO_IDS = {"SSU8Ko6wKm4"}


def source_media_reuse_rejection_reason(info: dict[str, Any]) -> str:
    """Enforce an explicit operator refusal even without CC enforcement."""
    ids = {str(info.get(key) or "").strip() for key in ("id", "video_id")}
    for key in ("url", "webpage_url", "original_url"):
        parsed = urlparse(str(info.get(key) or ""))
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
            ids.update(parse_qs(parsed.query).get("v", []))
            parts = parsed.path.strip("/").split("/")
            if host == "youtu.be" or (len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}):
                ids.add(parts[-1])
    names = {re.sub(r"\s+", " ", str(info.get(key) or "")).strip().casefold()
             for key in ("uploader", "channel")}
    handles = {str(info.get(key) or "").strip().casefold() for key in ("uploader_id", "channel_handle")}
    if (ids & NO_MEDIA_REUSE_VIDEO_IDS
            or source_channel_ids(info) & NO_MEDIA_REUSE_CHANNEL_IDS
            or names & NO_MEDIA_REUSE_CHANNEL_NAMES
            or handles & NO_MEDIA_REUSE_HANDLES):
        return ("operator melarang pemakaian rekaman DW Dokumenter untuk clip; "
                "gunakan topik sebagai riset saja dengan naskah, visual, dan audio orisinal")
    return ""


def trusted_source_channel_ids() -> set[str]:
    """Return operator-approved channels with documented reuse rights."""
    return {
        value.strip()
        for value in os.environ.get("YOUTUBE_TRUSTED_SOURCE_CHANNEL_IDS", "").split(",")
        if value.strip()
    }


def reference_only_source_channel_ids() -> set[str]:
    """Return channels explicitly approved for research, never media reuse."""
    configured = {
        value.strip()
        for value in os.environ.get(
            "YOUTUBE_REFERENCE_ONLY_SOURCE_CHANNEL_IDS", ""
        ).split(",")
        if value.strip()
    }
    return BUILTIN_REFERENCE_ONLY_CHANNEL_IDS | configured


def reference_only_source_handles() -> set[str]:
    configured = {
        value.strip().casefold()
        for value in os.environ.get(
            "YOUTUBE_REFERENCE_ONLY_SOURCE_HANDLES", ""
        ).split(",")
        if value.strip()
    }
    return BUILTIN_REFERENCE_ONLY_HANDLES | configured


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


def is_reference_only_source_channel(info: dict[str, Any]) -> bool:
    """Identify editorial-reference channels without treating them as owners."""
    configured_ids = reference_only_source_channel_ids()
    if configured_ids and source_channel_ids(info) & configured_ids:
        return True
    uploader_id = str(info.get("uploader_id") or "").strip().casefold()
    uploader_name = re.sub(
        r"\s+",
        " ",
        str(info.get("uploader") or info.get("channel") or ""),
    ).strip().casefold()
    return bool(
        uploader_id in reference_only_source_handles()
        or uploader_name in BUILTIN_REFERENCE_ONLY_NAMES
    )


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
    refusal = source_media_reuse_rejection_reason(info)
    if refusal:
        return [refusal]
    if is_trusted_source_channel(info):
        return []

    title = re.sub(r"\s+", " ", str(info.get("title") or "")).strip().casefold()
    uploader = re.sub(
        r"\s+",
        " ",
        str(info.get("uploader") or info.get("channel") or ""),
    ).strip().casefold()
    description = re.sub(
        r"\s+",
        " ",
        str(info.get("description") or ""),
    ).strip().casefold()
    reasons: list[str] = []
    if is_reference_only_source_channel(info):
        reasons.append(
            "kanal ditetapkan hanya sebagai referensi editorial; cari episode dan pemegang hak asli sebelum produksi"
        )
    explicitly_blocks_commercial_republishing = bool(
        description
        and any(re.search(pattern, description, re.I) for pattern in SOURCE_RIGHTS_REPUBLISH_PATTERNS)
        and any(re.search(pattern, description, re.I) for pattern in SOURCE_RIGHTS_PROHIBITION_PATTERNS)
        and any(re.search(pattern, description, re.I) for pattern in SOURCE_RIGHTS_COMMERCIAL_PATTERNS)
    )
    if explicitly_blocks_commercial_republishing:
        reasons.append(
            "deskripsi sumber secara eksplisit melarang upload ulang untuk tujuan komersial/monetisasi"
        )
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
