"""Conservative claim detection shared by rendering and persisted-clip review."""
from __future__ import annotations

import hashlib
import re


RELIGIOUS_ATTRIBUTION_MARKERS = (
    "allah berfirman", "dalam alquran", "dalam al-quran", "dalam hadis",
    "dalam hadits", "menurut ulama", "nabi bersabda", "rasulullah bersabda", "surat ",
)
RELIGIOUS_RULING_WORDS = {
    "dosa", "halal", "haram", "hukum", "makruh", "pahala", "sunnah", "syariat", "wajib",
}
_CASUAL_HALAL_WISH = re.compile(r"\byang\s+penting\s+halal(?=\s*(?:[,.;!?]|$))")
_SPECIFIC_SUBJECT = re.compile(
    r"\b(?:riba|judi|bank|bunga|pinjaman|alkohol|babi|korupsi|suap|prostitusi)\b"
)


def religious_ruling_terms(text: str) -> set[str]:
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    # A general farewell about colleagues choosing where to work is not an
    # assertion that a particular practice is halal. Keep specific subjects,
    # attributions, and every other ruling term behind the existing review.
    casual_work_wish = bool(
        re.search(r"\bkerja\s+(?:ke\s*mana|di\s*mana)\b", normalized)
        and re.search(r"\b(?:silakan|silahkan)\b", normalized)
        and re.search(r"\byang\s+penting\s+sehat\b", normalized)
        and not _SPECIFIC_SUBJECT.search(normalized)
        and not any(marker in normalized for marker in RELIGIOUS_ATTRIBUTION_MARKERS)
    )
    if casual_work_wish:
        normalized = _CASUAL_HALAL_WISH.sub(" ", normalized)
    return set(re.findall(r"[\w']+", normalized)).intersection(RELIGIOUS_RULING_WORDS)


def reassess_casual_work_wish(sidecar: dict) -> dict:
    """Correct only a proven legacy keyword false positive; retain raw evidence.

    Missing hashes, damaged context, real quotations, and specific rulings keep
    their original hold. This does not mark a clip as reviewed by a person.
    """
    packet = sidecar.get("religious_claim_review")
    text = sidecar.get("text")
    integrity = sidecar.get("religious_context_integrity")
    if not (
        isinstance(packet, dict)
        and packet.get("review_required") is True
        and packet.get("recommended_decision") == "manual_review_before_private_upload"
        and isinstance(text, str)
        and text
        and hashlib.sha256(text.encode("utf-8")).hexdigest() == packet.get("clip_transcript_sha256")
        and isinstance(integrity, dict)
        and integrity.get("safe_for_automatic_export") is True
        and integrity.get("attribution_present") is False
        and not integrity.get("quoted_claim_incomplete")
        and not integrity.get("context_dependent_opening")
        and not integrity.get("dangling_connector")
        and not religious_ruling_terms(text)
        and not any(marker in text.casefold() for marker in RELIGIOUS_ATTRIBUTION_MARKERS)
    ):
        return sidecar
    claims = packet.get("claims")
    if not isinstance(claims, list) or not claims:
        return sidecar
    for claim in claims:
        if not (
            isinstance(claim, dict)
            and claim.get("types") == ["religious_ruling_or_consequence"]
            and claim.get("ruling_terms") == ["halal"]
            and isinstance(claim.get("text"), str)
            and claim["text"].strip() in text
            and _CASUAL_HALAL_WISH.search(claim["text"].casefold())
            and not religious_ruling_terms(claim["text"])
        ):
            return sidecar
    corrected_integrity = {
        **integrity, "ruling_present": False, "manual_source_and_claim_review_required": False,
    }
    corrected_packet = {
        **packet, "review_required": False, "risk_level": "low", "claims": [],
        "recommended_decision": "standard_editorial_review",
        "integrity": corrected_integrity,
        "required_checks": [check for check in packet.get("required_checks", []) if check not in {
            "verify_quran_or_hadith_reference_and_wording", "verify_ruling_scope_conditions_and_exceptions",
        }],
        "classification_correction": {
            "rule": "casual_work_wish_v1", "original_claims": claims,
            "previous_review_required": True,
        },
    }
    return {**sidecar, "religious_claim_review": corrected_packet,
            "religious_context_integrity": corrected_integrity}
