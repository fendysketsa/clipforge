"""Transfer editorial structures from references, never their claims or media."""
from __future__ import annotations

import math
import re
from typing import Any


# Marketing/link footers are especially common in clipping search results.
# They describe distribution, not what the video is actually about.
TREND_NOISE_WORDS = frozenset("""
    yang dan di ke dari untuk dengan ini itu pada dalam adalah sebagai karena
    juga bisa akan ada jadi agar atau tapi tidak bukan sudah belum lebih paling
    kita kamu kalian saya aku gua gue lu lo dia mereka nya jangan sampai hanya
    the and for with this that from your you are not how what why who when
    official video full terbaru viral trending indonesia hari episode part feat
    www http https com net org id watch shorts youtu youtube instagram tiktok
    subscribe subscribers like share follow followers link bio channel credit
""".split())

RYUUNDY_REFERENCE_EDITOR_BRIEF = (
    "RYUUNDY: satu momen, satu makna. Pilih pembuka yang menyebut masalah, pilihan, "
    "atau pertanyaan spesifik; setiap janji pembuka harus terjawab di klip yang sama. "
    "Untuk manfaat praktis, cari masalah -> langkah konkret -> hasil atau batasan yang "
    "benar-benar dijelaskan sumber. Untuk cerita/game, cari keputusan -> konsekuensi -> "
    "makna; jangan memaksakan tutorial atau hikmah agama. Efek, zoom, dan perubahan visual "
    "hanya membantu beat yang relevan; caption tetap terbaca stabil. Pelajari struktur "
    "referensi, buat sudut penjelasan sendiri, dan jangan menyalin judul, slogan, suara, "
    "logo, atau footage kreator referensi. Angka views publik bukan bukti retensi atau "
    "jaminan viral; uji satu perubahan terhadap baseline seri dan format yang sama."
)


def clean_topic_text(value: str) -> str:
    """Keep readable topic text while excluding links and promotional footers."""
    clean = re.sub(r"(?:https?://|www\.)\S+|\b\S+@\S+\.\S+|@[\w.]+", " ", value.casefold())
    lines = [line for line in clean.splitlines() if not re.match(
        r"\s*(?:subscribe|follow|business|contact|kontak|sosial media|social media"
        r"|jangan lupa (?:like|subscribe|follow))\b", line
    )]
    return " ".join(lines)


def meaningful_trend_tokens(value: str) -> set[str]:
    """Remove URL/handle/promotional noise before matching live topic demand."""
    return {
        token for token in re.findall(r"[a-z0-9]{3,}", clean_topic_text(value))
        if token not in TREND_NOISE_WORDS and not token.isdigit()
    }


def source_trend_matches(info: dict[str, Any], trend_tokens: set[str] | None) -> list[str]:
    # Normalize the incoming trend side too: stale caches can contain noise.
    demand = meaningful_trend_tokens(" ".join(sorted(trend_tokens or set())))
    source = meaningful_trend_tokens("\n".join(
        str(info.get(key) or "") for key in ("title", "description")
    ))
    return sorted(source & demand)


def practical_payoff_profile(text: str, duration: float) -> dict[str, object]:
    """A conservative transcript diagnostic for a useful problem/action/result arc.

    This does not verify demonstrations, claims, rights, or actual audience
    retention. It can only supply a small ranking preference after normal gates.
    Evidence is copied as exact source sentences; it never writes a new claim.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if s.strip()]
    duration_ok = (
        not isinstance(duration, bool)
        and isinstance(duration, (int, float))
        and math.isfinite(duration)
        and 18 <= duration <= 65
    )
    problem_re = re.compile(r"\b(?:kenapa|mengapa|gimana|bagaimana|masalah|kesalahan|susah|sulit|gagal|bingung|terlalu)\b", re.I)
    action_re = re.compile(r"\b(?:pilih|klik|tekan|atur|ubah|kurangi|tambahkan|potong|coba|periksa|bandingkan|matikan|aktifkan|pisahkan)\b", re.I)
    result_re = re.compile(r"\b(?:hasilnya|sehingga|setelah itu|dengan begitu|jadi lebih|sekarang|tetap perlu|namun tetap|batasannya)\b", re.I)
    hype_re = re.compile(r"\b(?:pasti viral|dijamin viral|auto kaya|pasti kaya|tanpa risiko|dijamin cuan)\b", re.I)
    problem = sentences[0] if sentences and problem_re.search(" ".join(sentences[0].split()[:28])) else ""
    action_index = next((i for i, sentence in enumerate(sentences[1:-1], 1)
                         if action_re.search(sentence) and len(meaningful_trend_tokens(sentence)) >= 3), None)
    result = sentences[-1] if len(sentences) >= 3 and result_re.search(sentences[-1]) else ""
    evidence = meaningful_trend_tokens(problem + " " + (sentences[action_index] if action_index is not None else ""))
    result_tokens = meaningful_trend_tokens(result)
    # "Hasilnya bagus, pasti viral" is a promise, not a resolved example.
    result_specific = len(result.split()) >= 7 and len(result_tokens) >= 4 and bool(evidence & result_tokens)
    qualified = bool(duration_ok and problem and action_index is not None
                     and result and result_specific and len(text.split()) >= 28
                     and not hype_re.search(text))
    return {
        "version": 1,
        "pattern": "problem_concrete_action_specific_result",
        "qualified": qualified,
        "evidence": {
            "problem": problem,
            "action": sentences[action_index] if action_index is not None else "",
            "result_or_boundary": result,
        },
        "rank_bonus": 3.0 if qualified else 0.0,
        "series_suggestion": "Satu Masalah, Satu Langkah" if qualified else None,
        "visual_demonstration_verified": False,
        "claims_verified": False,
        "actual_retention_prediction": False,
        "bypasses_quality_or_review_gates": False,
    }
