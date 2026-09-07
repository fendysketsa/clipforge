from __future__ import annotations

import hashlib
import re
from typing import Any


TIKTOK_STRATEGY_VERSION = 1

_SERIES: dict[str, dict[str, Any]] = {
    "jawaban_ustadz_30_detik": {
        "label": "Jawaban Ustadz 30 Detik",
        "eyebrow": "JAWABAN USTADZ",
        "pillar": "tanya_jawab_agama",
        "cta": "Simpan video ini sebagai bahan belajar.",
        "hashtags": [
            "#JawabanUstadz",
            "#KajianIslam",
            "#BelajarIslam",
            "#Islam",
            "#MuslimIndonesia",
        ],
        "visuals": [
            "Buka dengan pertanyaan ringkas, lalu pertahankan close-up pembicara sampai inti jawaban.",
            "Gunakan kartu pertanyaan singkat dan reframe natural hanya pada kata kunci jawaban.",
            "Mulai dari potongan jawaban terkuat, kemudian beri konteks tanpa efek yang menutupi pembicara.",
        ],
    },
    "kesalahan_ibadah_sehari_hari": {
        "label": "Kesalahan Ibadah Sehari-hari",
        "eyebrow": "CEK IBADAH",
        "pillar": "koreksi_ibadah_berkonteks",
        "cta": "Simpan video ini sebagai pengingat untuk terus belajar.",
        "hashtags": [
            "#CekIbadah",
            "#FiqihHarian",
            "#KajianIslam",
            "#Islam",
            "#MuslimIndonesia",
        ],
        "visuals": [
            "Tampilkan satu istilah ibadah penting di awal; hindari ilustrasi yang tidak sesuai konteks.",
            "Pakai aksen peringatan yang tenang dan fokuskan frame pada penjelasan, bukan efek dramatis.",
            "Gunakan before/after hanya bila benar-benar dijelaskan sumber; selebihnya pertahankan wajah pembicara.",
        ],
    },
    "nasihat_sering_disalahpahami": {
        "label": "Nasihat yang Sering Disalahpahami",
        "eyebrow": "PAHAMI NASIHAT",
        "pillar": "nasihat_dan_hikmah",
        "cta": "Pelajaran apa yang paling mengena bagi Anda?",
        "hashtags": [
            "#NasihatIslam",
            "#HikmahIslam",
            "#DakwahIslam",
            "#Islam",
            "#MuslimIndonesia",
        ],
        "visuals": [
            "Gunakan close-up natural dan jeda visual tenang agar inti nasihat mudah dicerna.",
            "Tampilkan frasa kunci dari ucapan sumber; B-roll hanya muncul bila benar-benar memperjelas makna.",
            "Awali dengan konflik pemahaman, lalu jaga visual sederhana sampai payoff nasihat selesai.",
        ],
    },
}

_ERROR_MARKERS = (
    "batal", "haram", "dosa", "makruh",
)
_STRONG_ERROR_MARKERS = (
    "kesalahan", "salah", "keliru", "jangan lakukan", "tidak sah", "kurang tepat",
)
_MISUNDERSTANDING_MARKERS = (
    "nasihat", "hikmah", "sabar", "ikhlas", "tawakal", "rezeki", "ujian",
)
_STRONG_MISUNDERSTANDING_MARKERS = (
    "salah paham", "disalahpahami", "sering dianggap", "bukan berarti", "padahal",
)
_QUESTION_MARKERS = (
    "apa ", "apakah", "bagaimana", "kenapa", "mengapa", "bolehkah", "benarkah",
    "hukum", "ustadz", "ustad", "tanya",
)


def _clean(value: str, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" \t\r\n.,;:-")[:limit]


def _stable_variant(stable_key: str, series_id: str) -> int:
    digest = hashlib.sha256(f"{series_id}|{stable_key}".encode("utf-8")).digest()
    return digest[0] % 3


def _select_series(content: str) -> tuple[str, str]:
    lowered = f" {content.casefold()} "
    if any(marker in lowered for marker in _STRONG_MISUNDERSTANDING_MARKERS):
        return "nasihat_sering_disalahpahami", "Isi clip secara eksplisit meluruskan pemahaman nasihat."
    if any(marker in lowered for marker in _STRONG_ERROR_MARKERS):
        return "kesalahan_ibadah_sehari_hari", "Ada istilah koreksi atau praktik ibadah pada isi clip."
    if "?" in content or any(marker in lowered for marker in _QUESTION_MARKERS):
        return "jawaban_ustadz_30_detik", "Isi clip berbentuk pertanyaan atau jawaban agama."
    if any(marker in lowered for marker in _ERROR_MARKERS):
        return "kesalahan_ibadah_sehari_hari", "Ada istilah hukum atau peringatan pada isi clip."
    if any(marker in lowered for marker in _MISUNDERSTANDING_MARKERS):
        return "nasihat_sering_disalahpahami", "Isi clip berupa nasihat atau pelurusan pemahaman."
    return "nasihat_sering_disalahpahami", "Seri nasihat dipakai sebagai identitas aman untuk isi reflektif."


def build_tiktok_strategy(
    *,
    title: str = "",
    hook: str = "",
    text: str = "",
    stable_key: str = "",
) -> dict[str, Any]:
    """Create a stable, source-grounded TikTok package without inventing religious claims."""
    clean_title = _clean(title, 120)
    clean_hook = _clean(hook, 140)
    content = _clean(" ".join(part for part in (title, hook, text) if part), 4000)
    series_id, selection_reason = _select_series(content)
    profile = _SERIES[series_id]
    variant = _stable_variant(stable_key or content, series_id)
    source_hook = clean_hook or clean_title or "Simak penjelasan lengkapnya"
    if variant == 0:
        opening_hook = source_hook
    elif variant == 1:
        opening_hook = f"Jangan berhenti di potongan awal: {source_hook}"
    else:
        opening_hook = f"Poin penting dari penjelasan ini: {source_hook}"
    opening_hook = _clean(opening_hook, 150)
    experiment_id = hashlib.sha256(
        f"{series_id}|{stable_key}|{opening_hook}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "version": TIKTOK_STRATEGY_VERSION,
        "series_id": series_id,
        "series_label": profile["label"],
        "series_eyebrow": profile["eyebrow"],
        "content_pillar": profile["pillar"],
        "selection_reason": selection_reason,
        "hook_variant": variant + 1,
        "opening_hook": opening_hook,
        "hook_window_seconds": 3,
        "visual_recipe": profile["visuals"][variant],
        "cta": profile["cta"],
        "hashtags": list(profile["hashtags"]),
        "experiment_id": experiment_id,
        "measure": [
            "views",
            "watched_full_percentage",
            "average_watch_time_seconds",
            "shares",
            "saves",
            "comments",
            "followers_gained",
        ],
        "guardrails": [
            "Tidak menambah dalil, hukum, atau klaim yang tidak diucapkan sumber.",
            "Variasi visual harus memperjelas isi dan tidak menutupi pembicara.",
            "Performa adalah eksperimen terukur, bukan jaminan FYP atau monetisasi.",
        ],
    }


def tiktok_caption_from_strategy(base_caption: str, strategy: dict[str, Any]) -> str:
    generic_tags = {
        "#shorts", "#fyp", "#fypシ", "#viral", "#trending", "#viralindonesia",
        "#trendingindonesia", "#kontenpilihan",
    }
    engagement_prefixes = (
        "untuk direnungkan", "hikmah mana", "bagikan", "share", "simpan", "save",
        "tulis pertanyaan", "tulis di komentar", "komen", "komentar", "follow", "ikuti",
        "seri:",
    )

    casual_fillers = re.compile(
        r"(?i)(?:[.!?]\s+|^)(?:wah|eh|anu|nih|dong|wkwk|udah|gak|nggak)\b.*$"
    )

    def formalize(text: str) -> str:
        text = re.sub(
            r"(?i)^(?:poin penting dari penjelasan ini|jangan berhenti di potongan awal)\s*:\s*",
            "",
            text,
        ).strip()
        text = casual_fillers.sub(".", text).strip()
        text = re.sub(r"(?i)\borang islam\b", "orang Islam", text)
        text = re.sub(r"(?i)\bngena\b", "mengena", text)
        if re.fullmatch(
            r"kalau orang Islam seperti ini[,.]?\s*apa yang terjadi dengan mereka\?",
            text,
            flags=re.IGNORECASE,
        ):
            return "Apa yang terjadi ketika seorang Muslim berada dalam kondisi seperti ini?"
        return text

    def clean_public_copy(value: str) -> list[str]:
        original = value or ""
        without_tags = re.sub(r"#[\w\d_]+", " ", original, flags=re.UNICODE)
        paragraphs = re.split(r"\n\s*\n", without_tags)
        kept: list[str] = []
        for paragraph in paragraphs:
            text = formalize(
                re.sub(r"\s+", " ", paragraph).strip().strip("-–—|").strip()
            )
            if not text or text.casefold().startswith(engagement_prefixes):
                continue
            fingerprint = re.sub(r"\W+", "", text, flags=re.UNICODE).casefold()
            if fingerprint and fingerprint not in {
                re.sub(r"\W+", "", item, flags=re.UNICODE).casefold() for item in kept
            }:
                kept.append(text)
        return kept

    base_candidates = clean_public_copy(base_caption)
    opening_candidates = clean_public_copy(str(strategy.get("opening_hook") or ""))

    def lead_score(text: str) -> tuple[int, int]:
        score = 4 if text.endswith("?") else 0
        if 6 <= len(text.split()) <= 24:
            score += 2
        if re.search(r"(?i)\b(?:seperti ini|hal ini)\.$", text):
            score -= 3
        return score, -len(text)

    candidates = base_candidates or opening_candidates
    lead = max(candidates, key=lead_score) if candidates else "Simak penjelasan lengkapnya."
    lead = formalize(lead)

    series_id = str(strategy.get("series_id") or "")
    profile = _SERIES.get(series_id, {})
    context_by_series = {
        "jawaban_ustadz_30_detik": (
            "Penjelasan lengkapnya penting agar pertanyaan dan jawaban tidak dipahami "
            "di luar konteks."
        ),
        "kesalahan_ibadah_sehari_hari": (
            "Pahami penjelasan lengkapnya agar praktik ibadah tidak dinilai hanya dari "
            "potongan video."
        ),
        "nasihat_sering_disalahpahami": (
            "Pahami penjelasan lengkapnya agar pesan yang disampaikan tidak terlepas dari konteks."
        ),
    }
    context = context_by_series.get(
        series_id,
        "Pahami penjelasan lengkapnya agar pesan tidak terlepas dari konteks.",
    )

    tags: list[str] = []
    hashtag_source = profile.get("hashtags") or strategy.get("hashtags", [])
    for raw in hashtag_source:
        tag = str(raw).strip()
        normalized = tag.casefold()
        if not tag or normalized in generic_tags or normalized in {item.casefold() for item in tags}:
            continue
        tags.append(tag)

    # Prefer the canonical series CTA so stale clip metadata cannot restore an
    # older multi-action CTA during a retry.
    cta = re.sub(
        r"\s+",
        " ",
        str(profile.get("cta") or strategy.get("cta") or ""),
    ).strip()
    parts = [lead, context, cta, " ".join(tags[:5])]
    return "\n\n".join(part for part in parts if part).strip()[:600].rstrip()
