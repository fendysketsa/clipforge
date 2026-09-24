from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


# High-confidence ASR corrections only. These are safe for subtitles and public
# metadata because they repair spelling without rewriting the speaker's claim.
_ISLAMIC_ASR_REPLACEMENTS = (
    (r"\bjamaat\b", "jamaah"),
    (r"\b(?:tablek|tableg|tablik|tabliq|tabligh)\b", "tablig"),
    (r"\bhadist\b", "hadis"),
    (r"\bal[\s-]+qur[’'`]an\b", "Al-Qur'an"),
)

_INCOMPLETE_TITLE_ENDINGS = frozenset(
    {
        "adalah",
        "agar",
        "akan",
        "atau",
        "bahwa",
        "bisa",
        "dalam",
        "dan",
        "dari",
        "dengan",
        "karena",
        "ketika",
        "menjadi",
        "oleh",
        "pada",
        "saat",
        "sebagai",
        "sehingga",
        "tetapi",
        "tidak",
        "untuk",
        "yang",
    }
)


@dataclass(frozen=True)
class QuranOutroQuote:
    """A locked, human-reviewed Indonesian Qur'an excerpt for video outros."""

    text: str
    source: str
    keywords: tuple[str, ...] = ()
    source_url: str = ""


# Do not populate this catalogue with model-generated wording. Every entry must
# keep a concrete surah/ayah reference and be reviewed before release. Short
# excerpts are used so the card remains readable and does not imitate tafsir.
QURAN_OUTRO_QUOTES: tuple[QuranOutroQuote, ...] = (
    QuranOutroQuote(
        "Allah tidak membebani seseorang, kecuali menurut kesanggupannya.",
        "QS. Al-Baqarah [2]: 286",
        ("beban", "berat", "sanggup", "ujian", "masalah", "kesulitan"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/2?from=286&to=286",
    ),
    QuranOutroQuote(
        "Sesungguhnya beserta kesulitan ada kemudahan.",
        "QS. Al-Insyirah [94]: 5",
        ("sulit", "kesulitan", "mudah", "kemudahan", "ujian", "sabar"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/94?from=5&to=5",
    ),
    QuranOutroQuote(
        "Ingatlah, bahwa hanya dengan mengingat Allah hati akan selalu tenteram.",
        "QS. Ar-Ra'd [13]: 28",
        ("hati", "tenang", "tenteram", "zikir", "dzikir", "cemas", "gelisah"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/13?from=28&to=28",
    ),
    QuranOutroQuote(
        "Janganlah kamu berputus asa dari rahmat Allah.",
        "QS. Yusuf [12]: 87",
        ("putus asa", "rahmat", "ampun", "dosa", "taubat", "tobat", "harapan"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/12?from=87&to=87",
    ),
    QuranOutroQuote(
        "Siapa yang bertawakal kepada Allah, niscaya Allah akan mencukupkan (keperluan)-nya.",
        "QS. At-Talaq [65]: 3",
        ("tawakal", "rezeki", "cukup", "usaha", "ikhtiar", "percaya"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/65?from=3&to=3",
    ),
    QuranOutroQuote(
        "Janganlah kamu (merasa) lemah dan jangan (pula) bersedih hati.",
        "QS. Ali 'Imran [3]: 139",
        ("lemah", "sedih", "bangkit", "semangat", "gagal", "kecewa"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/3?from=139&to=139",
    ),
    QuranOutroQuote(
        "Sungguh, yang paling mulia di antara kamu di sisi Allah ialah orang yang paling bertakwa.",
        "QS. Al-Hujurat [49]: 13",
        ("mulia", "takwa", "suku", "bangsa", "manusia", "derajat"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/49?from=13&to=13",
    ),
    QuranOutroQuote(
        "Hendaklah berbuat baik kepada ibu bapak.",
        "QS. Al-Isra' [17]: 23",
        ("ibu", "bapak", "ayah", "orang tua", "berbakti", "keluarga"),
        source_url="https://quran.kemenag.go.id/quran/per-ayat/surah/17?from=23&to=23",
    ),
)


def select_quran_outro_quote(value: str, seed: str = "") -> QuranOutroQuote:
    """Select a relevant quote deterministically without asking AI to invent one."""
    normalized = re.sub(r"\s+", " ", value).casefold().strip()
    relevant = tuple(
        quote
        for quote in QURAN_OUTRO_QUOTES
        if any(keyword in normalized for keyword in quote.keywords)
    )
    pool = relevant or QURAN_OUTRO_QUOTES
    digest = hashlib.sha256(f"{seed}\n{normalized}".encode("utf-8")).digest()
    return pool[int.from_bytes(digest[:8], "big") % len(pool)]


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


def public_title_has_complete_ending(value: str) -> bool:
    """Reject metadata titles that visibly stop on an Indonesian connector."""
    clean = re.sub(r"(?:\s*#[\w\d_]+)+\s*$", "", value).strip()
    if not clean or clean.endswith((":", "-", "–", "—", ",", ";", "/")):
        return False
    words = re.findall(r"[\w']+", clean.casefold(), flags=re.UNICODE)
    return bool(words and words[-1] not in _INCOMPLETE_TITLE_ENDINGS)


def trim_public_title(value: str, max_chars: int) -> str:
    """Fit a title without leaving a dangling connector after truncation."""
    clean = re.sub(r"\s+", " ", value).strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars].rsplit(" ", 1)[0].rstrip() or clean[:max_chars].rstrip()
    while clean and not public_title_has_complete_ending(clean):
        shorter = clean.rsplit(" ", 1)[0].rstrip(" -|:–—,;/")
        if not shorter or shorter == clean:
            break
        clean = shorter
    return clean.rstrip(" -|:–—,;/")


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
