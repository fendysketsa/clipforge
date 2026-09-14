from __future__ import annotations

import re


# High-confidence ASR corrections only. These are safe for subtitles and public
# metadata because they repair spelling without rewriting the speaker's claim.
_ISLAMIC_ASR_REPLACEMENTS = (
    (r"\bjamaat\b", "jamaah"),
    (r"\b(?:tablek|tableg|tablik|tabliq|tabligh)\b", "tablig"),
    (r"\bhadist\b", "hadis"),
    (r"\bal[\s-]+qur[’'`]an\b", "Al-Qur'an"),
)


def _case_aware_replacement(match: re.Match[str], replacement: str) -> str:
    if match.group(0)[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def repair_islamic_asr_text(value: str) -> str:
    """Repair confirmed Islamic-term ASR errors without changing meaning."""
    clean = value
    for pattern, replacement in _ISLAMIC_ASR_REPLACEMENTS:
        clean = re.sub(
            pattern,
            lambda match, replacement=replacement: _case_aware_replacement(
                match, replacement
            ),
            clean,
            flags=re.IGNORECASE,
        )
    return clean


def islamic_indonesian_tts_text(value: str) -> str:
    """Return pronunciation-oriented Indonesian text used only by TTS audio."""
    spoken = repair_islamic_asr_text(re.sub(r"\s+", " ", value).strip())
    replacements = (
        (r"(?i)\bQ\.?\s*S\.?\s*", "Surah "),
        (r"(?i)(?<!\w)S\.?\s*W\.?\s*T\.?(?!\w)|ﷻ", "subhaanahu wa ta'aalaa"),
        (r"(?i)(?<!\w)S\.?\s*A\.?\s*W\.?(?!\w)|ﷺ", "shallallaahu alaihi wasallam"),
        (r"(?i)\b(?:muhamad|mohamad|mohammad|muhammad)\b", "Muhammad"),
        (r"(?i)\bAl[-\s]?Qur[’'`]an\b", "Al Quran"),
        (r"(?i)\bQur[’'`]an\b", "Quran"),
        (r"(?i)\bustadzah\b", "ustazah"),
        (r"(?i)\bustad(?:z)?\b", "ustaz"),
        (r"(?i)\bmakhraj\b", "makhroj"),
        (r"(?i)\bberwudhu\b", "berwudu"),
        (r"(?i)\bwudhu\b", "wudu"),
        (r"(?i)\bberdzikir\b", "berzikir"),
        (r"(?i)\bdzikir\b", "zikir"),
        (r"(?i)\bmuadzin\b", "muazin"),
        (r"(?i)\badzan\b", "azan"),
        (r"(?i)\b(?:shalat|sholat)\b", "salat"),
        (r"(?i)\bsholawat\b", "salawat"),
        (r"(?i)\b(?:fiqh|fiqih)\b", "fikih"),
        (r"(?i)\baqidah\b", "akidah"),
        (r"(?i)\bakhlaq\b", "akhlak"),
        (r"(?i)\bsyari[’'`]?ah\b", "syariah"),
        (r"(?i)\bdhuha\b", "duha"),
        (r"(?i)\b(?:dzuhur|dhuhur)\b", "zuhur"),
        (r"(?i)\bashar\b", "asar"),
        (r"(?i)\bmaghrib\b", "magrib"),
        (r"(?i)\bRasulullah\b", "Rasululloh"),
        (r"(?i)\bAbdullah\b", "Abdulloh"),
        (r"(?i)\bAllah\b", "Alloh"),
        (r"الله", "Alloh"),
    )
    for pattern, replacement in replacements:
        spoken = re.sub(pattern, replacement, spoken)
    spoken = re.sub(r"\s+([,.;:!?])", r"\1", spoken)
    spoken = re.sub(r"([,.;:!?])(?!\s|$)", r"\1 ", spoken)
    return re.sub(r"\s+", " ", spoken).strip()
