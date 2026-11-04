import copy
import hashlib

import pytest

from religious_review import religious_ruling_terms, reassess_casual_work_wish


WORK_WISH = "Mau kerja kemana pun silahkan, yang penting sehat, yang penting halal, ya."


def legacy_sidecar(text=WORK_WISH):
    integrity = {
        "safe_for_automatic_export": True, "attribution_present": False,
        "ruling_present": True, "manual_source_and_claim_review_required": True,
        "theological_accuracy_guaranteed": False,
    }
    return {
        "text": text, "is_correct": False, "religious_context_integrity": integrity,
        "religious_claim_review": {
            "review_required": True, "risk_level": "high",
            "recommended_decision": "manual_review_before_private_upload",
            "automatic_theological_approval": False,
            "clip_transcript_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "claims": [{"text": text, "types": ["religious_ruling_or_consequence"], "ruling_terms": ["halal"]}],
            "integrity": integrity,
            "required_checks": ["verify_quran_or_hadith_reference_and_wording", "verify_ruling_scope_conditions_and_exceptions", "confirm_audio_visual_and_music_rights"],
        },
    }


@pytest.mark.parametrize("text", [WORK_WISH, WORK_WISH.upper(), WORK_WISH.replace("kemana", "ke mana").replace("silahkan", "silakan")])
def test_general_work_wish_is_not_a_specific_halal_ruling(text):
    assert religious_ruling_terms(text) == set()


@pytest.mark.parametrize("text", [
    "Bunga bank itu halal.", "Judi itu halal.", "Halal bekerja di bank itu.",
    "Mau kerja kemana pun silahkan, yang penting halal.",
    WORK_WISH + " Menurut ulama, praktik ini halal.",
    WORK_WISH + " Tetapi riba itu halal.",
    WORK_WISH + " Menyuap itu halal.",
])
def test_actual_or_ambiguous_ruling_keeps_its_review(text):
    assert "halal" in religious_ruling_terms(text)


def test_reassessment_preserves_original_packet_and_human_review_flag():
    sidecar = legacy_sidecar()
    original = copy.deepcopy(sidecar)
    corrected = reassess_casual_work_wish(sidecar)
    assert sidecar == original
    assert corrected["is_correct"] is False
    packet = corrected["religious_claim_review"]
    assert packet["review_required"] is False
    assert packet["automatic_theological_approval"] is False
    assert packet["classification_correction"]["original_claims"] == original["religious_claim_review"]["claims"]
    assert packet["clip_transcript_sha256"] == original["religious_claim_review"]["clip_transcript_sha256"]
    assert packet["required_checks"] == ["confirm_audio_visual_and_music_rights"]


@pytest.mark.parametrize("fault", ["hash", "attribution", "unsafe", "recut", "missing_claims", "other_claim"])
def test_reassessment_cannot_clear_other_holds(fault):
    sidecar = legacy_sidecar()
    packet = sidecar["religious_claim_review"]
    if fault == "hash": packet["clip_transcript_sha256"] = "stale"
    if fault == "attribution": sidecar["religious_context_integrity"]["attribution_present"] = True
    if fault == "unsafe": sidecar["religious_context_integrity"]["safe_for_automatic_export"] = False
    if fault == "recut": packet["recommended_decision"] = "reject_and_recut"
    if fault == "missing_claims": packet["claims"] = []
    if fault == "other_claim": packet["claims"].append({"text": "Dalam hadits Nabi bersabda...", "types": ["hadith_attribution"], "ruling_terms": []})
    assert reassess_casual_work_wish(sidecar) is sidecar


def test_renderer_and_legacy_reassessment_agree():
    import clipper
    segment = clipper.TranscriptSegment(0, 30, WORK_WISH)
    clip = clipper.ClipCandidate(1, 0, 30, 30, 90, "Pilihan Kerja", "konteks utuh", WORK_WISH)
    packet = clipper.religious_claim_review_packet(clip, [segment], [segment])
    assert packet["review_required"] is False
    assert packet["integrity"]["ruling_present"] is False
    assert packet["automatic_theological_approval"] is False
