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
        "cta": "Simpan untuk dipelajari lagi. Tulis pertanyaan lanjutan dengan santun.",
        "hashtags": ["#JawabanUstadz", "#KajianIslam", "#BelajarIslam"],
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
        "cta": "Simpan sebagai pengingat dan periksa kembali rujukan lengkap sebelum mempraktikkannya.",
        "hashtags": ["#CekIbadah", "#FiqihHarian", "#KajianIslam"],
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
        "cta": "Apa pelajaran yang paling mengena? Tulis dengan santun dan simpan untuk direnungkan lagi.",
        "hashtags": ["#NasihatIslam", "#Hikmah", "#Dakwah"],
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
    base = re.sub(r"(?i)(?:^|\s)#shorts\b", " ", base_caption or "")
    base = re.sub(r"[ \t]+", " ", base)
    base = re.sub(r"\n{3,}", "\n\n", base).strip()
    existing = {tag.casefold() for tag in re.findall(r"#[\w\d_]+", base, flags=re.UNICODE)}
    tags: list[str] = []
    for raw in [*strategy.get("hashtags", []), "#Islam", "#Dakwah"]:
        tag = str(raw).strip()
        if tag and tag.casefold() not in existing and tag.casefold() not in {item.casefold() for item in tags}:
            tags.append(tag)
    parts = [
        f"Seri: {strategy.get('series_label', '')}",
        str(strategy.get("opening_hook") or "").strip(),
    ]
    if base and base.casefold() not in {part.casefold() for part in parts}:
        parts.append(base)
    parts.append(str(strategy.get("cta") or "").strip())
    parts.append(" ".join(tags[:5]))
    return "\n\n".join(part for part in parts if part).strip()[:2200].rstrip()
