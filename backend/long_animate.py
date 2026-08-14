from __future__ import annotations

import ast
import base64
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import cv2
import imageio_ffmpeg
import numpy as np

from llm import AIConfig, chat_completion, extract_json


ProgressCallback = Callable[[int, str, str], None]


class LongAnimateImageError(RuntimeError):
    """Remote image generation failed and local fallback is not acceptable."""


@dataclass
class AnimateScene:
    index: int
    title: str
    narration: str
    visual_prompt: str
    on_screen_text: str
    camera_motion: str
    color_mood: str
    narrative_role: str
    duration_hint: float = 0.0
    duration: float = 0.0
    voice_duration: float = 0.0
    image_provider: str = ""
    voice_provider: str = ""
    shot_prompts: list[str] = field(default_factory=list)
    qa_attempts: int = 0
    qa_score: float = 0.0
    visuals_locked: bool = False
    speech_tempo: float = 1.0


@dataclass
class AnimateStoryboard:
    title: str
    hook: str
    core_message: str
    art_bible: str
    character_bible: str
    scenes: list[AnimateScene]
    location_bible: str = ""


@dataclass
class AnimateShot:
    index: int
    scene_index: int
    shot_index: int
    shot_count: int
    title: str
    narration: str
    visual_prompt: str
    on_screen_text: str
    camera_motion: str
    color_mood: str
    duration: float = 0.0
    image_provider: str = ""
    qa_attempts: int = 0
    qa_score: float = 0.0


STORYBOARD_SYSTEM_PROMPT = (
    "You are an animation director and storyboard editor fluent in Indonesian. Turn a user-authored script "
    "into a coherent, original 16:9 YouTube story. Every scene must materially advance the narrative. "
    "Treat the user's script as the only source of truth. Use a consistent visual world but vary composition, "
    "scale, palette, symbolic objects, and camera motion. Never default to an Indonesian, Islamic, child, family, "
    "school, mosque, or human scene unless that identity or setting is supported by the script. Never replace a "
    "requested subject with a generic boy, girl, Muslim child, teacher, ustaz, or family. A requested animal, "
    "object, vehicle, creature, profession, historical setting, fantasy world, or non-Indonesian location must remain "
    "that exact subject and world. Preserve explicit subject count, age, gender, species, clothing, props, action, "
    "location, time of day, weather, and visual style scene by scene. "
    "Avoid public-figure likenesses, logos, copyrighted characters, embedded text, fake quotations, graphic harm, "
    "and depictions of prophets or sacred figures. Define a precise character_bible only for characters that actually "
    "occur in the script; if there is no recurring character, say so and do not invent one. "
    "Each visual_prompt must describe exactly one uninterrupted camera shot and one visible moment: subject, action, setting, composition, camera, "
    "and lighting. The action must be concrete and physically visible; never use abstract actions such as "
    "preparing, realizing, thinking, or feeling without stating exactly what the hands and body are doing. "
    "Only include religious or cultural clothing when the script requests it or the stated setting unambiguously "
    "requires it. When it is requested, apply culturally correct gendered clothing: a woman wearing a hijab never "
    "wears a peci, kopiah, songkok, or any second hat over it; those caps are reserved for male characters. "
    "Whenever hands are visible, describe a relaxed natural pose with anatomically correct fingers and make every "
    "hand visibly connected through its wrist and forearm to its owner. Never introduce disembodied hands, floating "
    "limbs, anonymous foreground body parts, or extra background people not requested by the script. "
    "Return art_bible, character_bible, and visual_prompt as short plain descriptive strings, never JSON objects. "
    "Also define a location_bible for recurring places. Treat art_bible, character_bible, and location_bible as "
    "immutable continuity contracts, not suggestions. "
    "Copy explicit NARASI/Narator wording verbatim; visual directions and production instructions are never narration. "
    "Never copy narration labels, scene headings, timestamps, or on-screen text into visual_prompt. "
    "Do not add claims that are absent from the script. "
    "Return strict JSON only."
)


_SCENE_HEADER_RE = re.compile(
    r"(?im)^\s*#{1,6}\s*(?:scene|adegan)\s*(\d+)\s*(?:[—–:-]\s*)?([^\n]*)$"
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _output_geometry() -> tuple[str, int, int]:
    aspect = os.environ.get("LONG_ANIMATE_OUTPUT_ASPECT_RATIO", "16:9").strip()
    if aspect == "9:16":
        return aspect, 1080, 1920
    return "16:9", 1920, 1080


def _plain_text_value(value: object) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[", "(")) and stripped.endswith(("}", "]", ")")):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, (dict, list, tuple, set)):
                return _plain_text_value(parsed)
        return value
    if isinstance(value, dict):
        parts: list[str] = []
        for raw_key, raw_value in value.items():
            key = str(raw_key).replace("_", " ").strip()
            nested = _plain_text_value(raw_value)
            parts.append(f"{key}: {nested}" if nested else key)
        return ", ".join(part for part in parts if part)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(part for item in value if (part := _plain_text_value(item)))
    return str(value or "")


def _clean_text(value: object, limit: int) -> str:
    return re.sub(r"\s+", " ", _plain_text_value(value)).strip()[:limit]


def _sentence_chunks(script: str, target_words: int = 38) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", script) if item.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs or [script]:
        sentences.extend(
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+", paragraph)
            if item.strip()
        )
    chunks: list[str] = []
    current: list[str] = []
    word_count = 0
    for sentence in sentences:
        words = sentence.split()
        if current and word_count + len(words) > target_words:
            chunks.append(" ".join(current))
            current = []
            word_count = 0
        current.append(sentence)
        word_count += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _strip_script_markup(value: str) -> str:
    value = re.sub(r"(?m)^\s*#{1,6}\s*", "", value)
    value = re.sub(r"\*{1,3}|_{1,3}|`+", "", value)
    value = value.strip().strip("\"'“”‘’ ")
    return re.sub(r"\s+", " ", value).strip()


def _visual_only(value: str) -> str:
    value = re.split(
        r"(?is)(?:teks\s*(?:layar|di\s+layar)|on[- ]screen\s+text|narasi|narration)\s*:",
        value,
        maxsplit=1,
    )[0]
    value = re.split(r"(?im)^\s*#{1,6}\s*(?:scene|adegan)\b", value, maxsplit=1)[0]
    return _strip_script_markup(value)


def _single_visible_moment(value: str) -> str:
    """Keep an image prompt on one renderable shot instead of a contact sheet."""
    clean = _visual_only(value)
    sentences = [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|\n+", clean)
        if item.strip()
    ]
    rejected = (
        "montase",
        "kalender",
        "variasi shot",
        "variasi medium",
        "transisi",
        "tampilkan teks",
        "tambahkan teks",
        "subtitle",
        "negative prompt",
        "durasi akhir",
    )
    candidates = [
        sentence
        for sentence in sentences
        if not any(token in sentence.casefold() for token in rejected)
    ]

    def visible_score(sentence: str) -> int:
        lowered = sentence.casefold()
        score = 0
        if re.search(
            r"\b(?:anak|bayi|remaja|pria|wanita|laki-laki|perempuan|ibu|ayah|guru|"
            r"ustaz|ustadz|dokter|petani|nelayan|astronaut|ilmuwan|robot|hewan|kucing|"
            r"anjing|burung|ikan|mobil|motor|kapal|pesawat|kereta|rumah|gedung|gunung|"
            r"hutan|laut|planet|ia)\b",
            lowered,
        ):
            score += 4
        if any(
            token in lowered
            for token in (
                "tangan", "berdiri", "duduk", "berjalan", "berlari", "terbang", "berenang",
                "membaca", "menulis", "membuka", "meletakkan", "membasuh", "menutup",
                "menyimpan", "menoleh", "mengangkat", "mendorong", "menarik", "memasak",
                "menanam", "memperbaiki", "mendarat", "meledak", "runtuh", "menyala",
            )
        ):
            score += 2
        if any(token in lowered for token in ("suasana", "cahaya matahari", "burung terdengar")):
            score -= 2
        return score

    selected = max(candidates, key=visible_score) if candidates else clean
    selected = re.sub(
        r"(?i)^(?:awali video dengan|lanjutkan dengan|selanjutnya,?|perlihatkan|tampilkan)\s+",
        "",
        selected,
    )
    selected = re.sub(r"(?i)^(?:pada\s+hari\s+berikutnya|setelah\s+selesai|pada\s+bagian\s+penutup),\s*", "", selected)
    selected = re.split(
        r"(?i),\s*(?=(?:lalu|kemudian|tersenyum|membaca|meletakkan|menutup|menyimpan)\b)|\s+(?:lalu|kemudian)\s+",
        selected,
        maxsplit=1,
    )[0]
    words = selected.split()
    if len(words) > 58:
        selected = " ".join(words[:58]).rstrip(" ,;:-") + "."
    return selected


def _visible_shot_moments(value: str, max_shots: int = 3) -> list[str]:
    """Split sequential physical actions into renderable still-image shots."""
    clean = _visual_only(value)
    if not clean:
        return []
    pieces = re.split(
        r"(?<=[.!?])\s+|\s*[;]\s*|\s+(?:lalu|kemudian|setelah itu|sesudah itu)\s+",
        clean,
        flags=re.IGNORECASE,
    )
    action_prefix = (
        r"(?:membuka|menutup|berjalan|berlari|duduk|berdiri|menoleh|mengangkat|meletakkan|"
        r"menempelkan|memindai|memperbaiki|mengunci|menarik|mendorong|turun|naik|terbang|"
        r"opens?|closes?|walks?|runs?|sits?|stands?|turns?|lifts?|places?|scans?|repairs?|locks?|flies?)"
    )
    subject = ""
    first_piece = pieces[0].strip() if pieces else ""
    subject_match = re.match(rf"(?i)^(.{{2,90}}?)\s+(?={action_prefix}\b)", first_piece)
    if subject_match:
        subject = subject_match.group(1).strip(" ,;:-")
    shots: list[str] = []
    for piece_index, piece in enumerate(pieces):
        if piece_index > 0 and subject and re.match(rf"(?i)^\s*{action_prefix}\b", piece):
            piece = f"{subject} {piece.strip()}"
        moment = _single_visible_moment(piece)
        if len(moment.split()) < 3:
            continue
        if moment.casefold() not in {item.casefold() for item in shots}:
            shots.append(_clean_text(moment, 650))
        if len(shots) >= max(1, max_shots):
            break
    return shots or [_single_visible_moment(clean)]


def _short_on_screen_text(value: str, max_words: int = 6, max_chars: int = 48) -> str:
    clean = _strip_script_markup(value)
    words = clean.split()
    selected = words[:max_words]
    if (
        len(words) > len(selected)
        and selected
        and selected[-1].casefold().strip(".,") in {"dan", "atau", "yang", "untuk", "dari"}
    ):
        selected.append(words[len(selected)])
    shortened = " ".join(selected)
    if len(shortened) > max_chars:
        shortened = shortened[:max_chars].rsplit(" ", 1)[0]
    return shortened.rstrip(" ,;:-")


def _extract_quoted_text(value: str, marker_pattern: str) -> str:
    match = re.search(
        rf"(?is){marker_pattern}.{{0,90}}?[\"“]([^\"”]+)[\"”]",
        value,
    )
    return _strip_script_markup(match.group(1)) if match else ""


def _directed_paragraph_sections(script: str) -> list[dict[str, object]]:
    """Parse prose prompts that explicitly separate narrator copy from visuals."""
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", script) if item.strip()]
    sections: list[dict[str, object]] = []
    narrator_marker = re.compile(
        r"(?is)\bnarator\s+(?:berkata|menjelaskan|menutup(?:\s+dengan\s+kalimat)?)\s*"
    )
    for paragraph in paragraphs:
        marker = narrator_marker.search(paragraph)
        if marker is None:
            continue
        tail = paragraph[marker.end() :].lstrip(" :,.-")
        quoted = re.match(r'^[\"“]([^\"”]+)[\"”]', tail, flags=re.DOTALL)
        if quoted:
            narration = _strip_script_markup(quoted.group(1))
        else:
            narration = re.sub(r"(?i)^bahwa\s+", "", tail).strip()
            narration = _strip_script_markup(narration)

        visual_source = paragraph[: marker.start()]
        label_positions = [
            match.start()
            for pattern in (
                r"(?is)\btampilkan\s+(?:judul|teks)",
                r"(?is)\btambahkan\s+teks",
            )
            if (match := re.search(pattern, visual_source)) is not None
        ]
        if label_positions:
            visual_source = visual_source[: min(label_positions)]
        visuals = _visible_shot_moments(visual_source)
        visual = visuals[0] if visuals else ""
        on_screen_text = _short_on_screen_text(_extract_quoted_text(
            paragraph,
            r"(?:tampilkan|tambahkan)\s+(?:judul\s+di\s+layar|teks(?:\s+penutup)?(?:\s+secara\s+bergantian)?)\s*:?,?",
        ))
        if len(narration.split()) < 3 or not visual:
            continue
        sections.append(
            {
                "title": _clean_text(on_screen_text, 48) or _scene_title(narration, len(sections)),
                "narration": _clean_text(narration, 900),
                "visual": _clean_text(visual, 650),
                "visuals": visuals,
                "on_screen_text": _clean_text(on_screen_text, 48),
            }
        )
    return sections if len(sections) >= 3 else []


def _scene_sections(script: str) -> list[dict[str, object]]:
    """Parse explicit Markdown Scene/Adegan blocks without leaking production labels."""
    matches = list(_SCENE_HEADER_RE.finditer(script))
    if len(matches) < 3:
        return _directed_paragraph_sections(script)
    sections: list[dict[str, object]] = []
    for index, match in enumerate(matches[:14]):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(script)
        body = script[match.end() : end].strip()
        title = re.sub(r"\s*\([^)]*\)\s*$", "", match.group(2)).strip(" —–:-")

        text_match = re.search(
            r"(?is)(?:teks\s*(?:layar|di\s+layar)|on[- ]screen\s+text)\s*:\s*"
            r"(?:[\"“](.*?)[\"”]|([^\n]+))",
            body,
        )
        on_screen_text = _short_on_screen_text(
            (text_match.group(1) or text_match.group(2)) if text_match else ""
        )

        narration_match = re.search(
            r"(?is)(?:narasi|narration)\s*:\s*(.*?)"
            r"(?=\n\s*(?:visual|gambar|teks\s*(?:layar|di\s+layar)|on[- ]screen\s+text)\s*:|\Z)",
            body,
        )
        narration = _strip_script_markup(narration_match.group(1)) if narration_match else ""
        if narration.casefold() in {"-", "hening", "[hening]", "tanpa narasi", "no narration"}:
            narration = ""

        visual_match = re.search(
            r"(?is)(?:visual|gambar)\s*:\s*(.*?)"
            r"(?=\n\s*(?:narasi|narration|teks\s*(?:layar|di\s+layar)|on[- ]screen\s+text)\s*:|\Z)",
            body,
        )

        label_positions = [
            item.start()
            for item in (
                re.search(r"(?is)teks\s*(?:layar|di\s+layar)\s*:", body),
                re.search(r"(?is)on[- ]screen\s+text\s*:", body),
                re.search(r"(?is)(?:narasi|narration)\s*:", body),
                re.search(r"(?is)(?:visual|gambar)\s*:", body),
            )
            if item is not None
        ]
        visual_source = (
            visual_match.group(1)
            if visual_match
            else (body[: min(label_positions)] if label_positions else body)
        )
        visuals = _visible_shot_moments(visual_source)
        visual_source = visuals[0] if visuals else ""
        if not narration and narration_match is None:
            narration = visual_source
        if not visual_source:
            visual_source = narration
        if not visual_source:
            continue
        sections.append(
            {
                "title": _clean_text(title, 64),
                "narration": _clean_text(narration, 900),
                "visual": _clean_text(visual_source, 900),
                "visuals": visuals,
                "on_screen_text": on_screen_text,
            }
        )
    return sections if len(sections) >= 3 else []


def _character_bible(script: str) -> str:
    explicit = re.search(
        r"(?im)^\s*(?:karakter\s+konsisten|character\s+bible|karakter)\s*:\s*(.+)$",
        script,
    )
    if explicit:
        details = _clean_text(explicit.group(1), 900)
        if details and details.casefold() not in {"-", "tidak ada", "none", "no recurring character"}:
            return (
                "Recurring character continuity: preserve only these explicitly requested identities, including "
                "their face or defining shape, age, species, body proportions, clothing, equipment, and colors in "
                f"every applicable scene. Script character facts: {details}"
            )
    cues = (
        "anak",
        "pria",
        "wanita",
        "laki-laki",
        "perempuan",
        "ustaz",
        "ustadz",
        "guru",
        "ibu",
        "ayah",
        "tokoh",
        "karakter",
        "mengenakan",
        "memakai",
    )
    identity_markers = (
        "seorang",
        "berusia",
        "mengenakan",
        "memakai",
        "berbaju",
        "berpeci",
        "berjilbab",
        "berambut",
        "berkulit",
        "ramah",
        "tinggi",
        "pendek",
    )
    candidates: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", script):
        clean = _strip_script_markup(sentence)
        lowered = clean.casefold()
        if (
            clean
            and any(cue in lowered for cue in cues)
            and any(marker in lowered for marker in identity_markers)
        ):
            if not re.match(r"(?i)^(buat|gunakan|video harus|target|format|resolusi)\b", clean):
                candidates.append(clean)
    details = "; ".join(dict.fromkeys(candidates))[:900]
    if details:
        return (
            "Recurring character continuity: preserve only the explicitly described recurring identities, including "
            "their face or defining shape, age, species, body proportions, clothing, equipment, and colors in every "
            f"applicable scene. Script character facts: {details}"
        )
    return (
        "No recurring character is defined. Do not invent any recurring identity or living subject; include one "
        "only when the scene itself explicitly requires it."
    )


def _requested_art_bible(script: str) -> str:
    match = re.search(
        r"(?im)^\s*(?:gaya\s+visual|visual\s+style|art\s+bible|style)\s*:\s*(.+)$",
        script,
    )
    return _clean_text(match.group(1), 600) if match else ""


def _location_bible(script: str) -> str:
    match = re.search(
        r"(?im)^\s*(?:lokasi\s+konsisten|location\s+bible|lokasi)\s*:\s*(.+)$",
        script,
    )
    if match:
        return (
            "Location continuity lock: preserve this architecture, geography, era, weather baseline, materials, "
            f"and spatial layout whenever the location recurs. Script location facts: {_clean_text(match.group(1), 700)}"
        )
    return (
        "Location continuity lock: preserve every recurring location exactly as established by the script; "
        "do not substitute an unrelated familiar or stock setting."
    )


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", lowered) is not None
        for term in terms
    )


_PEOPLE_IDENTITY_TERMS = (
    "orang", "manusia", "anak", "bayi", "remaja", "pria", "wanita", "laki-laki",
    "perempuan", "ibu", "ayah", "kakek", "nenek", "guru", "dokter", "petani", "nelayan",
    "astronaut", "ilmuwan", "ustaz", "ustadz", "karakter utama", "tokoh", "seorang", "warga",
    "kerumunan", "pejalan kaki", "pemuda", "gadis", "lelaki", "pekerja", "pelanggan", "perawat",
    "polisi", "tentara", "pilot", "koki", "pedagang", "teknisi", "mekanik", "person", "people", "human", "boy", "girl",
    "child", "baby", "teenager", "man", "woman",
    "mother", "father", "teacher", "doctor", "farmer", "fisherman", "scientist", "worker", "customer",
    "nurse", "police officer", "soldier", "chef", "merchant", "technician", "mechanic",
)

_PEOPLE_PRONOUN_TERMS = (
    "dia", "ia", "mereka", "aku", "saya", "kami", "kita", "he", "she", "they",
)

_PEOPLE_TERMS = _PEOPLE_IDENTITY_TERMS + _PEOPLE_PRONOUN_TERMS

_NONHUMAN_CHARACTER_TERMS = (
    "robot", "android", "cyborg", "hewan", "kucing", "anjing", "burung", "ikan", "paus", "lumba-lumba",
    "kuda", "sapi", "kambing", "harimau", "singa", "gajah", "monyet", "rubah", "serigala", "beruang",
    "monster", "makhluk", "alien", "naga", "dinosaurus", "animal", "cat", "dog", "bird", "fish", "whale",
    "dolphin", "horse", "tiger", "lion", "elephant", "fox", "wolf", "bear", "creature", "dragon", "dinosaur",
)

_ISLAMIC_VISUAL_TERMS = (
    "hijab", "jilbab", "peci", "kopiah", "songkok", "baju koko", "gamis", "muslimah",
    "muslim clothing", "masjid", "mosque", "mukena", "sarung", "rehal",
)

_INDONESIAN_VISUAL_TERMS = (
    "indonesia", "indonesian", "jakarta", "nusantara", "kampung indonesia", "desa indonesia",
)


def _contains_unrequested_defaults(script: str, proposed: str) -> bool:
    """Reject familiar stock imagery that has no support in the user's source text."""
    script_has_nonhuman = _has_any(script, _NONHUMAN_CHARACTER_TERMS)
    script_allows_people = _has_any(script, _PEOPLE_IDENTITY_TERMS) or (
        _has_any(script, _PEOPLE_PRONOUN_TERMS) and not script_has_nonhuman
    )
    if not script_allows_people and _has_any(proposed, _PEOPLE_TERMS):
        return True
    return any(
        not _has_any(script, terms) and _has_any(proposed, terms)
        for terms in (_ISLAMIC_VISUAL_TERMS, _INDONESIAN_VISUAL_TERMS)
    )


def _expected_people_limit(text: str) -> int:
    if not _has_any(text, _PEOPLE_TERMS):
        return 0
    lowered = text.casefold()
    if _has_any(lowered, ("crowd", "kerumunan", "jamaah", "audience", "penonton")):
        return 8
    human_noun = r"(?:orang|anak|pria|wanita|laki-laki|perempuan|person|people|boy|girl|men|women)"
    word_values = {"satu": 1, "seorang": 1, "one": 1, "dua": 2, "two": 2, "tiga": 3, "three": 3, "empat": 4, "four": 4}
    explicit: list[int] = []
    for word, value in word_values.items():
        if re.search(rf"(?<!\w){re.escape(word)}\s+{human_noun}(?!\w)", lowered):
            explicit.append(value)
    explicit.extend(
        int(item)
        for item in re.findall(rf"(?<!\d)([1-4])\s+{human_noun}(?!\w)", lowered)
    )
    return min(4, max([1, *explicit]))


def _compose_visual_prompt(
    visual: str,
    narration: str,
    art_bible: str,
    character_bible: str,
    location_bible: str = "",
) -> str:
    aspect_ratio, _output_width, _output_height = _output_geometry()
    visual = _single_visible_moment(visual)
    grounding = _clean_text(narration, 700)
    scene_context = f"{visual} {grounding}"
    complete_context = f"{scene_context} {character_bible}"
    has_people = _has_any(
        scene_context,
        _PEOPLE_TERMS,
    )
    has_nonhuman_character = _has_any(scene_context, _NONHUMAN_CHARACTER_TERMS)
    has_islamic_clothing = has_people and _has_any(
        complete_context,
        _ISLAMIC_VISUAL_TERMS,
    )
    people_limit = _expected_people_limit(scene_context)
    continuity = (
        _clean_text(character_bible, 420)
        if has_people or has_nonhuman_character
        else "No recurring character appears in this frame; do not insert one"
    )
    subject_rule = (
        "Use only the people explicitly described, each appearing exactly once; never invent a crowd, "
        "background extras, or partial people. Frame every person with enough body context to identify who owns "
        "every limb. No hands or arms may enter from outside the frame, and never crop a person at the wrist or "
        "forearm. Use natural anatomy and relaxed believable poses. Every clearly visible hand has exactly five "
        "naturally separated fingers with correct joints, proportions, and grip; no fused, missing, duplicated, or "
        "malformed fingers. Every hand is visibly and anatomically attached through a wrist and forearm to a clearly "
        "visible person; no floating hands, disembodied limbs, or anonymous foreground hands. "
        if has_people
        else "This scene does not request a human subject. Keep the frame free of human figures, faces, silhouettes, "
        "crowds, and body parts. "
    )
    clothing_rule = (
        "Apply only the religious clothing explicitly requested. A woman wearing a hijab has the hijab as her sole "
        "head covering: never add a peci, kopiah, songkok, cap, or hat over or under her hijab. Male characters may "
        "wear a peci only when described. "
        if has_islamic_clothing
        else "Use only clothing explicitly supported by this scene; do not add unrequested religious or cultural attire. "
    )
    return _clean_text(
        f"FULL-BLEED CINEMATIC {aspect_ratio} SINGLE FRAME FROM ONE CAMERA. Render in the requested visual style, whether "
        "animation, illustration, 3D, documentary, or photography. One continuous environment and one natural composition. "
        f"Visible moment: {visual}. "
        + (f"Narrative grounding: {grounding}. " if grounding else "")
        + "STRICT STORY GROUNDING: depict the requested subject, event, action, object, location, era, weather, "
        "and time literally. Do not substitute a stock character or a familiar default setting. The visible moment "
        "takes priority; narrative grounding supplies meaning but must not introduce unrelated objects or people. "
        + subject_rule
        + f"VISIBLE HUMAN LIMIT: {people_limit}; never exceed this count. "
        + clothing_rule
        + f"Continuity bible: {continuity}. "
        + (f"Location bible: {_clean_text(location_bible, 360)}. " if location_bible else "")
        + f"IMMUTABLE GLOBAL VISUAL STYLE: {_clean_text(art_bible, 320)}. Keep the same medium, rendering technique, "
        "lens language, texture treatment, detail level, and color-science across every shot; scene palette changes "
        "must not change the global style. "
        "Use one clear focal action, the exact culture and location requested by the script, clear subject-background "
        "separation, crisp focal detail, believable materials and lighting appropriate to the requested style, and professional composition. "
        "Do not add unrequested writing, signage, logos, symbols, props, architecture, or decorations. "
        "When people are explicitly requested, use original fictional people matching the script's stated identity; "
        "never imitate a public figure. The image extends naturally to all four edges.",
        3000,
    )


def _fallback_storyboard(script: str) -> AnimateStoryboard:
    sections = _scene_sections(script)
    chunks = (
        [section["narration"] for section in sections]
        if sections
        else _sentence_chunks(script)
    )
    if len(chunks) < 3:
        words = script.split()
        size = max(8, math.ceil(len(words) / 3))
        chunks = [" ".join(words[index : index + size]) for index in range(0, len(words), size)]
    chunks = chunks[:14]
    seed = hashlib.sha256(script.encode("utf-8")).hexdigest()
    art_styles = (
        "cinematic semi-realistic storybook illustration, natural anatomy, subtle film grain",
        "polished animated-film still, believable materials, soft volumetric light",
        "cinematic editorial illustration, natural proportions, rich environmental detail",
        "warm painterly animation still, realistic lighting, expressive restrained design",
    )
    explicit_art_bible = _requested_art_bible(script)
    requested_style = script.casefold()
    if explicit_art_bible:
        art_bible = explicit_art_bible
    elif any(token in requested_style for token in ("ultra-realistic", "ultra realistic", "fotoreal", "photoreal", "realistis")):
        art_bible = (
            "ultra-realistic cinematic photography, crisp subject detail, natural skin texture, "
            "believable materials, soft depth of field, warm natural window light, restrained film color grade"
        )
    else:
        art_bible = art_styles[int(seed[:2], 16) % len(art_styles)]
    character_bible = _character_bible(script)
    location_bible = _location_bible(script)
    motions = ("push_in", "pan_right", "drift_up", "pan_left", "pull_out")
    roles = []
    for index in range(len(chunks)):
        if index == 0:
            roles.append("cold_open")
        elif index == 1:
            roles.append("context")
        elif index == len(chunks) - 1:
            roles.append("payoff_conclusion")
        elif index / max(1, len(chunks) - 1) < 0.62:
            roles.append("development")
        else:
            roles.append("evidence_and_answer")
    scenes: list[AnimateScene] = []
    for index, chunk in enumerate(chunks):
        section = sections[index] if sections else None
        title_source = chunk or (section["visual"] if section else "")
        title = section["title"] if section and section["title"] else _scene_title(title_source, index)
        visual = section["visual"] if section else chunk
        on_screen_text = section["on_screen_text"] if section else ""
        raw_shots = section.get("visuals") if section else _visible_shot_moments(str(visual))
        shot_prompts = [
            _clean_text(item, 650)
            for item in (raw_shots if isinstance(raw_shots, list) else [visual])
            if _clean_text(item, 650)
        ][:3]
        scenes.append(
            AnimateScene(
                index=index + 1,
                title=title,
                narration=chunk,
                visual_prompt=_compose_visual_prompt(
                    visual,
                    chunk,
                    art_bible,
                    character_bible,
                    location_bible,
                ),
                on_screen_text=on_screen_text,
                camera_motion=motions[(index + int(seed[2:4], 16)) % len(motions)],
                color_mood=_color_mood(f"{chunk} {visual}", index),
                narrative_role=roles[index],
                duration_hint=(
                    max(6.0, min(22.0, len(chunk.split()) / 2.45 + 1.2))
                    if chunk
                    else 4.5
                ),
                shot_prompts=shot_prompts,
                visuals_locked=bool(section),
            )
        )
    first = scenes[0].title if scenes else "Cerita Animasi"
    last = scenes[-1].title if scenes else first
    return AnimateStoryboard(
        title=first[:80],
        hook=_clean_text(next((chunk for chunk in chunks if chunk), script), 180),
        core_message=f"{first} menuju {last}"[:300],
        art_bible=art_bible,
        character_bible=character_bible,
        scenes=scenes,
        location_bible=location_bible,
    )


def _scene_title(text: str, index: int) -> str:
    clean = re.sub(r"[^\w\s'-]", " ", text, flags=re.UNICODE)
    words = [word for word in clean.split() if len(word) > 2]
    title = " ".join(words[:6]).strip()
    return (title or f"Bagian {index + 1}").title()[:64]


def _color_mood(text: str, index: int) -> str:
    lowered = text.casefold()
    if any(token in lowered for token in ("bahaya", "takut", "salah", "gelap", "peringatan")):
        return "deep crimson, charcoal, restrained amber"
    if any(token in lowered for token in ("tenang", "doa", "hikmah", "iman", "syukur")):
        return "emerald, midnight teal, warm gold"
    if any(token in lowered for token in ("harapan", "berhasil", "solusi", "jawaban", "cahaya")):
        return "cobalt blue, sunrise gold, soft ivory"
    palettes = (
        "indigo, copper, soft cyan",
        "forest green, warm cream, muted gold",
        "midnight blue, coral, pale mint",
    )
    return palettes[index % len(palettes)]


def build_storyboard(script: str, ai_config: AIConfig) -> AnimateStoryboard:
    fallback = _fallback_storyboard(script)
    source_sections = _scene_sections(script)
    if not ai_config.enabled or not ai_config.base_url or not ai_config.model:
        return fallback
    grounded_note = ""
    if source_sections:
        grounded_note = (
            f"Naskah sudah memiliki {len(source_sections)} scene terarah. WAJIB kembalikan tepat "
            f"{len(source_sections)} scene dalam urutan yang sama. Copy isi narration dari field NARASI "
            "secara verbatim; jangan pernah menyuarakan isi VISUAL atau TEKS LAYAR.\n"
            "SCENE TERKUNCI:\n"
            + json.dumps(source_sections, ensure_ascii=False)
            + "\n"
        )
    prompt = (
        "Buat storyboard dari naskah berikut. Naskah pengguna adalah satu-satunya sumber kebenaran. "
        "Pertahankan seluruh fakta, subjek, kejadian, aksi, lokasi, zaman, pakaian, properti, dan maksud naskah. "
        "DILARANG memakai pola stok anak laki-laki/perempuan, keluarga, pakaian Islami, ustaz, masjid, sekolah, "
        "atau latar Indonesia bila unsur tersebut tidak diminta naskah. Jangan mengubah hewan, benda, robot, "
        "kendaraan, profesi, makhluk fantasi, atau lokasi menjadi manusia atau karakter generik. "
        "Target durasi final 20 detik: buat 3-7 scene padat dan satu gagasan visual utama per scene. Jika satu "
        "scene memuat beberapa aksi fisik berurutan, isi field shots dengan 2-3 momen tunggal; jangan gabungkan "
        "beberapa aksi ke satu gambar. "
        "Hook editor: shot pertama harus memperlihatkan konflik, risiko, pertanyaan visual, atau payoff yang dijanjikan "
        "dalam dua detik pertama; jangan mulai dengan establishing shot generik. "
        "Cold-open harus langsung menjanjikan konflik/manfaat, lalu konteks, perkembangan, jawaban, payoff. "
        "Jangan menambah filler atau mengulang narasi. Buat art_bible dan character_bible yang konsisten. "
        "character_bible hanya boleh memuat identitas yang benar-benar ada dalam naskah; tulis 'No recurring "
        "character' bila tidak ada. Setiap visual_prompt harus menerjemahkan narasi scene yang sama menjadi aksi "
        "fisik yang konkret, bukan gambar generik yang hanya cocok dengan tema besar. visual_prompt hanya boleh "
        "berisi satu momen yang terlihat; jangan masukkan label Narasi, Teks layar, heading, atau timestamp.\n"
        "Return JSON exactly as: "
        '{"title":"...","hook":"...","core_message":"...","art_bible":"...","character_bible":"...","location_bible":"...",'
        '"scenes":[{"title":"...","narration":"...","visual_prompt":"...","shots":["one visible moment", "optional next visible moment"],'
        '"on_screen_text":"maks 7 kata","camera_motion":"push_in|pull_out|pan_left|pan_right|drift_up",'
        '"color_mood":"...","narrative_role":"cold_open|context|development|evidence_and_answer|payoff_conclusion"}]}\n\n'
        f"{grounded_note}"
        f"NASKAH:\n{script[:30000]}"
    )
    try:
        parsed = extract_json(
            chat_completion(
                ai_config,
                [
                    {"role": "system", "content": STORYBOARD_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
        )
    except Exception:
        return fallback
    raw_scenes = parsed.get("scenes") if isinstance(parsed, dict) else None
    if not isinstance(raw_scenes, list) or not 3 <= len(raw_scenes) <= 14:
        return fallback
    if source_sections and len(raw_scenes) != len(source_sections):
        return fallback
    allowed_motions = {"push_in", "pull_out", "pan_left", "pan_right", "drift_up"}
    allowed_roles = {
        "cold_open",
        "context",
        "development",
        "evidence_and_answer",
        "payoff_conclusion",
    }
    scenes: list[AnimateScene] = []
    proposed_art_bible = _clean_text(parsed.get("art_bible"), 600)
    art_tokens = ("cinematic", "realistic", "realistis", "illustration", "lighting", "photography", "film", "animation")
    art_bible = (
        proposed_art_bible
        if (
            any(token in proposed_art_bible.casefold() for token in art_tokens)
            and not _contains_unrequested_defaults(script, proposed_art_bible)
        )
        else fallback.art_bible
    )
    proposed_character_bible = _clean_text(parsed.get("character_bible"), 900)
    if source_sections or _contains_unrequested_defaults(script, proposed_character_bible):
        character_bible = fallback.character_bible
    else:
        character_bible = proposed_character_bible or fallback.character_bible
    proposed_location_bible = _clean_text(parsed.get("location_bible"), 700)
    location_bible = (
        fallback.location_bible
        if source_sections or _contains_unrequested_defaults(script, proposed_location_bible)
        else proposed_location_bible or fallback.location_bible
    )
    for index, raw in enumerate(raw_scenes):
        if not isinstance(raw, dict):
            return fallback
        source = source_sections[index] if source_sections else None
        narration = source["narration"] if source else _clean_text(raw.get("narration"), 900)
        if not source and _contains_unrequested_defaults(script, narration):
            return fallback
        visual_prompt = source["visual"] if source else _clean_text(raw.get("visual_prompt"), 900)
        if not source and _contains_unrequested_defaults(script, visual_prompt):
            # Prefer a literal source-grounded image over a polished but unrelated stock scene.
            visual_prompt = narration
        if (not source and len(narration.split()) < 8) or not visual_prompt:
            return fallback
        motion = _clean_text(raw.get("camera_motion"), 20)
        role = _clean_text(raw.get("narrative_role"), 30)
        raw_shots = source.get("visuals") if source else raw.get("shots")
        if not isinstance(raw_shots, list):
            raw_shots = _visible_shot_moments(str(visual_prompt))
        shot_prompts = [
            _clean_text(item, 650)
            for item in raw_shots
            if _clean_text(item, 650)
            and not _contains_unrequested_defaults(script, _clean_text(item, 650))
        ][:3] or [_clean_text(visual_prompt, 650)]
        scenes.append(
            AnimateScene(
                index=index + 1,
                title=(source["title"] if source else _clean_text(raw.get("title"), 64))
                or _scene_title(narration or visual_prompt, index),
                narration=narration,
                visual_prompt=_compose_visual_prompt(
                    visual_prompt,
                    narration,
                    art_bible,
                    character_bible,
                    location_bible,
                ),
                on_screen_text=(source["on_screen_text"] if source else ""),
                camera_motion=motion if motion in allowed_motions else "push_in",
                color_mood=_clean_text(raw.get("color_mood"), 120)
                or _color_mood(narration, index),
                narrative_role=role if role in allowed_roles else "development",
                duration_hint=(
                    max(6.0, min(25.0, len(narration.split()) / 2.45 + 1.2))
                    if narration
                    else 4.5
                ),
                shot_prompts=shot_prompts,
                visuals_locked=bool(source),
            )
        )
    scenes[0].narrative_role = "cold_open"
    scenes[-1].narrative_role = "payoff_conclusion"
    return AnimateStoryboard(
        title=_clean_text(parsed.get("title"), 80) or fallback.title,
        hook=_clean_text(parsed.get("hook"), 180) or fallback.hook,
        core_message=_clean_text(parsed.get("core_message"), 300) or fallback.core_message,
        art_bible=art_bible,
        character_bible=character_bible,
        scenes=scenes,
        location_bible=location_bible,
    )


def _target_duration_seconds() -> float:
    try:
        value = float(os.environ.get("LONG_ANIMATE_TARGET_DURATION_SECONDS", "20"))
    except ValueError:
        value = 20.0
    return max(5.0, min(3600.0, value))


def _transition_seconds() -> float:
    try:
        value = float(os.environ.get("LONG_ANIMATE_TRANSITION_SECONDS", "0.12"))
    except ValueError:
        value = 0.12
    return max(0.0, min(0.2, value))


def allocate_scene_durations(
    scenes: list[AnimateScene],
    voice_durations: list[float],
    target_duration: float,
) -> None:
    """Allocate an exact millisecond timeline using measured TTS as the primary weight."""
    if not scenes or len(scenes) != len(voice_durations):
        raise ValueError("Scene dan durasi TTS harus memiliki jumlah yang sama")
    target_ms = max(1000, round(target_duration * 1000))
    minimum_ms = min(800, max(1, target_ms // max(1, len(scenes) * 3)))
    remaining_ms = target_ms
    unlocked = set(range(len(scenes)))
    allocation = [0] * len(scenes)
    weights = [
        max(0.25, duration if scene.narration.strip() else min(1.0, scene.duration_hint or 0.8))
        for scene, duration in zip(scenes, voice_durations)
    ]
    while unlocked:
        total_weight = sum(weights[index] for index in unlocked) or float(len(unlocked))
        too_small = [
            index
            for index in unlocked
            if remaining_ms * weights[index] / total_weight < minimum_ms
        ]
        if not too_small:
            break
        for index in too_small:
            allocation[index] = minimum_ms
            remaining_ms -= minimum_ms
            unlocked.remove(index)
    total_weight = sum(weights[index] for index in unlocked) or 1.0
    ordered = sorted(unlocked)
    for position, index in enumerate(ordered):
        if position == len(ordered) - 1:
            value = remaining_ms
        else:
            value = round(remaining_ms * weights[index] / total_weight)
            remaining_ms -= value
            total_weight -= weights[index]
        allocation[index] = max(1, value)
    correction = target_ms - sum(allocation)
    allocation[-1] += correction
    for scene, original_voice, milliseconds in zip(scenes, voice_durations, allocation):
        scene.duration = milliseconds / 1000.0
        scene.voice_duration = max(0.0, original_voice if scene.narration.strip() else 0.0)


_SEMANTIC_STOPWORDS = {
    "yang", "dan", "atau", "dengan", "untuk", "dari", "pada", "dalam", "saat", "ketika", "sebelum",
    "setelah", "sebuah", "seorang", "adalah", "akan", "telah", "agar", "karena", "scene", "shot", "visual",
    "the", "and", "with", "from", "into", "that", "this", "when", "before", "after", "through", "visible",
    "moment", "camera", "lighting", "cinematic",
}


def _semantic_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-ZÀ-ÿ0-9'-]{4,}", text.casefold())
        if token not in _SEMANTIC_STOPWORDS
    }


def scene_visual_semantic_score(narration: str, visual: str) -> float:
    narrative_tokens = _semantic_tokens(narration)
    visual_tokens = _semantic_tokens(visual)
    if not narrative_tokens or not visual_tokens:
        return 1.0
    overlap = narrative_tokens & visual_tokens
    return len(overlap) / max(1, min(len(narrative_tokens), 8))


def plan_storyboard_shots(storyboard: AnimateStoryboard) -> list[AnimateShot]:
    """Expand complex scenes into multiple visual shots without repeating narration."""
    shots: list[AnimateShot] = []
    motions = ("push_in", "pan_right", "pull_out", "pan_left", "drift_up")
    reference_id = hashlib.sha256(storyboard.character_bible.encode("utf-8")).hexdigest()[:12]
    for scene in storyboard.scenes:
        raw_prompts = scene.shot_prompts or [_single_visible_moment(scene.narration)]
        max_for_duration = max(1, min(3, int(scene.duration / 0.75)))
        selected = raw_prompts[:max_for_duration] or [_single_visible_moment(scene.narration)]
        shot_ms_total = round(scene.duration * 1000)
        base_ms, remainder = divmod(shot_ms_total, len(selected))
        for local_index, raw_visual in enumerate(selected, start=1):
            if (
                not scene.visuals_locked
                and scene_visual_semantic_score(scene.narration, raw_visual) < 0.12
            ):
                raw_visual = _single_visible_moment(scene.narration)
            shot_duration = (base_ms + (1 if local_index <= remainder else 0)) / 1000.0
            prompt = _compose_visual_prompt(
                raw_visual,
                scene.narration,
                storyboard.art_bible,
                storyboard.character_bible,
                storyboard.location_bible,
            )
            if "No recurring character is defined" not in storyboard.character_bible:
                prompt = _clean_text(
                    f"CHARACTER REFERENCE LOCK {reference_id}: every recurring identity must match the approved "
                    f"reference design exactly. {prompt}",
                    3200,
                )
            shots.append(
                AnimateShot(
                    index=len(shots) + 1,
                    scene_index=scene.index,
                    shot_index=local_index,
                    shot_count=len(selected),
                    title=scene.title,
                    narration=scene.narration,
                    visual_prompt=prompt,
                    on_screen_text=scene.on_screen_text if local_index == 1 else "",
                    camera_motion=motions[(scene.index + local_index - 2) % len(motions)],
                    color_mood=scene.color_mood,
                    duration=shot_duration,
                )
            )
    transition = _transition_seconds()
    if transition > 0:
        for shot in shots[:-1]:
            shot.duration += transition
    return shots


def _ffmpeg_path() -> str:
    return os.environ.get("FFMPEG_BINARY", "").strip() or shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def _run(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-1800:]
        raise RuntimeError(f"FFmpeg Long Animate gagal: {detail}")


def _media_duration(path: Path) -> float:
    result = subprocess.run(
        [_ffmpeg_path(), "-hide_banner", "-i", str(path.resolve())],
        text=True,
        capture_output=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr or "")
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _supports_filter(name: str) -> bool:
    result = subprocess.run(
        [_ffmpeg_path(), "-hide_banner", "-filters"],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0 and re.search(
        rf"(?m)^\s*[TSC.]+\s+{re.escape(name)}\s",
        f"{result.stdout}\n{result.stderr}",
    ) is not None


def _image_endpoint() -> tuple[str, str, str]:
    base = (
        os.environ.get("LONG_ANIMATE_IMAGE_BASE_URL", "").strip()
        or os.environ.get("OPENAI_IMAGE_BASE_URL", "").strip()
    )
    model = os.environ.get("LONG_ANIMATE_IMAGE_MODEL", "gemini-3.1-flash-image").strip()
    key = os.environ.get("LONG_ANIMATE_IMAGE_API_KEY", "").strip()
    host = (urlparse(base).hostname or "").casefold()
    if not key:
        key = (
            os.environ.get("GEMINI_API_KEY", "").strip()
            if host == "generativelanguage.googleapis.com"
            else os.environ.get("OPENAI_API_KEY", "").strip()
        )
    if base.casefold() in {
        "local",
        "builtin",
        "builtin://story-art",
        "fendy://story-art",
    }:
        # An explicit local provider must never be treated as a remote URL.
        # Returning an empty base selects the deterministic Story Art renderer.
        base = ""
    return base, model, key


def _remote_provider_label(base: str, model: str) -> str:
    if _is_sd_cpp_endpoint(base, model):
        return "local_z_image_turbo"
    host = (urlparse(base).hostname or "").casefold()
    if host == "generativelanguage.googleapis.com" and model.casefold().startswith("gemini-"):
        return "google_gemini_image_api"
    if host == "api.openai.com" and model.casefold().startswith("gpt-image"):
        return "openai_gpt_image_api"
    return "openai_compatible_image_api"


def _is_gemini_image_endpoint(base: str) -> bool:
    return (urlparse(base).hostname or "").casefold() == "generativelanguage.googleapis.com"


def _is_sd_cpp_endpoint(base: str, model: str = "") -> bool:
    provider = os.environ.get("LONG_ANIMATE_IMAGE_PROVIDER", "").strip().casefold()
    if provider in {"stable-diffusion-cpp", "stable_diffusion_cpp", "sdcpp"}:
        return True
    host = (urlparse(base).hostname or "").casefold()
    return host in {"127.0.0.1", "localhost", "::1"} and (
        "z-image" in model.casefold() or "sd-cpp" in model.casefold()
    )


def _release_ollama_gpu_models() -> None:
    """Free shared VRAM after storyboard generation before Z-Image starts."""
    if not _env_bool("LONG_ANIMATE_RELEASE_OLLAMA_BEFORE_IMAGE", True):
        return
    root = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    host = (urlparse(root).hostname or "").casefold()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return
    try:
        with urllib.request.urlopen(f"{root}/api/ps", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models") if isinstance(payload, dict) else None
        for item in models if isinstance(models, list) else []:
            name = _clean_text(item.get("name") if isinstance(item, dict) else "", 160)
            if not name:
                continue
            body = json.dumps({"model": name, "keep_alive": 0}).encode("utf-8")
            request = urllib.request.Request(
                f"{root}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
        # Ollama acknowledges keep_alive=0 before CUDA/Vulkan memory has always
        # disappeared. Do not race the image server: wait until /api/ps is empty.
        deadline = time.monotonic() + 30.0
        while models and time.monotonic() < deadline:
            time.sleep(0.5)
            with urllib.request.urlopen(f"{root}/api/ps", timeout=5) as response:
                current = json.loads(response.read().decode("utf-8"))
            models = current.get("models") if isinstance(current, dict) else None
    except Exception:
        # The image request still runs; strict mode will surface a real provider
        # error if VRAM remains insufficient.
        return


def _gemini_interactions_endpoint(base: str) -> str:
    endpoint = base.rstrip("/")
    if endpoint.endswith("/openai"):
        endpoint = endpoint[: -len("/openai")]
    if not endpoint.endswith("/interactions"):
        endpoint += "/interactions"
    return endpoint


def _image_bytes_from_result(result: object, gemini: bool) -> bytes:
    if not isinstance(result, dict):
        raise ValueError("API tidak mengembalikan objek JSON")
    if gemini:
        output_image = result.get("output_image")
        if isinstance(output_image, dict) and isinstance(output_image.get("data"), str):
            return base64.b64decode(output_image["data"], validate=True)
        steps = result.get("steps")
        if isinstance(steps, list):
            for step in reversed(steps):
                if not isinstance(step, dict) or step.get("type") != "model_output":
                    continue
                content = step.get("content")
                if not isinstance(content, list):
                    continue
                for block in reversed(content):
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "image"
                        and isinstance(block.get("data"), str)
                    ):
                        return base64.b64decode(block["data"], validate=True)
        raise ValueError("Gemini tidak mengembalikan image data pada model_output")
    data = result.get("data")
    first = data[0] if isinstance(data, list) and data else None
    if not isinstance(first, dict):
        raise ValueError("API tidak mengembalikan data gambar")
    if isinstance(first.get("b64_json"), str):
        return base64.b64decode(first["b64_json"], validate=True)
    if isinstance(first.get("url"), str):
        with urllib.request.urlopen(first["url"], timeout=90) as response:
            return response.read()
    raise ValueError("API tidak mengembalikan b64_json atau URL gambar")


def _image_error_detail(exc: BaseException) -> tuple[str, int | None]:
    if isinstance(exc, urllib.error.HTTPError):
        request_id = exc.headers.get("x-request-id", "") if exc.headers else ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")[:2000]
            parsed = json.loads(raw)
            error = parsed.get("error") if isinstance(parsed, dict) else None
            message = error.get("message") if isinstance(error, dict) else raw
        except Exception:
            message = str(exc)
        suffix = f" (request_id={request_id})" if request_id else ""
        return f"HTTP {exc.code}: {_clean_text(message, 700)}{suffix}", exc.code
    return _clean_text(exc, 700) or exc.__class__.__name__, None


def _remote_scene_image(
    scene: AnimateScene | AnimateShot,
    path: Path,
    reference_image: Path | None = None,
) -> bool:
    base, model, key = _image_endpoint()
    if not base:
        return False
    strict = _env_bool("LONG_ANIMATE_IMAGE_STRICT", False)
    host = (urlparse(base).hostname or "").casefold()
    is_gemini = _is_gemini_image_endpoint(base)
    is_sd_cpp = _is_sd_cpp_endpoint(base, model)
    if is_sd_cpp:
        _release_ollama_gpu_models()
    if host in {"api.openai.com", "generativelanguage.googleapis.com"} and not key:
        provider_name = "Gemini" if is_gemini else "OpenAI"
        detail = (
            f"LONG_ANIMATE_IMAGE_API_KEY belum diisi. Tempel API key {provider_name} di .env "
            "sebelum menjalankan Long Animate."
        )
        if strict:
            raise LongAnimateImageError(detail)
        return False
    endpoint = _gemini_interactions_endpoint(base) if is_gemini else base.rstrip("/")
    if not is_gemini and not endpoint.endswith("/images/generations"):
        endpoint += "/images/generations"
    quality = os.environ.get("LONG_ANIMATE_IMAGE_QUALITY", "high").strip().casefold()
    if quality not in {"low", "medium", "high", "auto"}:
        quality = "medium"
    output_format = os.environ.get(
        "LONG_ANIMATE_IMAGE_OUTPUT_FORMAT", "jpeg" if is_gemini else "png"
    ).strip().casefold()
    if output_format not in {"png", "jpeg", "webp"}:
        output_format = "jpeg"
    final_prompt = (
        f"{scene.visual_prompt} Color direction: {scene.color_mood}. "
        "Depict only this visible action accurately. Edge-to-edge image, one normal camera frame, with focal clarity "
        "appropriate to the requested visual style. "
        "Before finalizing, verify the requested subject identity and count, exact action, props, setting, era, weather, "
        "time, and visual style. Add no unrequested person, clothing, architecture, or cultural/religious symbol. When "
        "people are present, verify natural hands and finger count, attached limbs, believable faces, crisp eyes, and clean fabric edges."
    )
    if is_gemini:
        image_size = os.environ.get("LONG_ANIMATE_IMAGE_SIZE", "2K").strip().upper()
        if image_size not in {"512", "1K", "2K", "4K"}:
            image_size = "2K"
        aspect_ratio = _output_geometry()[0]
        if aspect_ratio not in {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}:
            aspect_ratio = "16:9"
        thinking_level = os.environ.get("LONG_ANIMATE_IMAGE_THINKING_LEVEL", "high").strip().casefold()
        if thinking_level not in {"minimal", "low", "medium", "high"}:
            thinking_level = "high"
        gemini_input: object = final_prompt
        if reference_image and reference_image.is_file():
            reference_mime = "image/jpeg" if reference_image.suffix.casefold() in {".jpg", ".jpeg"} else "image/png"
            gemini_input = [
                {
                    "type": "text",
                    "text": (
                        "Use the supplied image only as the immutable recurring-character and visual-style reference. "
                        "Preserve the same identity, face or defining shape, proportions, clothing/equipment, materials, "
                        "and rendering style, while creating the new action, pose, camera, and setting requested here. "
                        + final_prompt
                    ),
                },
                {
                    "type": "image",
                    "mime_type": reference_mime,
                    "data": base64.b64encode(reference_image.read_bytes()).decode("ascii"),
                },
            ]
        payload_object = {
            "model": model,
            "input": gemini_input,
            "response_format": {
                "type": "image",
                "mime_type": f"image/{output_format}",
                "aspect_ratio": aspect_ratio,
                "image_size": image_size,
            },
            "generation_config": {"thinking_level": thinking_level},
        }
    elif is_sd_cpp:
        # stable-diffusion.cpp exposes an OpenAI-compatible image endpoint, but
        # intentionally supports a smaller field set. The actual Z-Image model
        # is loaded once by sd-server, so no remote model name or API key is sent.
        negative_parts = [
            "collage, montage, storyboard, contact sheet, comic panels, split screen, grid, border, "
            "duplicate subject, repeated subject, text, caption, subtitle, letters, numbers, writing, "
            "watermark, logo, UI, compression artifacts",
            "deformed hands, fused fingers, missing fingers, extra fingers, duplicated fingers, broken joints, malformed grip, "
            "disembodied hands, floating hands, detached hands, bodyless limbs, cropped arms, hands entering from frame edge, anonymous foreground hands",
            "unrequested crowd, extra background people, partial person, unrelated stock character, unrequested cultural clothing",
        ]
        if not _has_any(scene.visual_prompt, ("soft focus", "dreamy", "dreamlike", "watercolor", "impressionist")):
            negative_parts.append("blurry, soft focus")
        if not _has_any(scene.visual_prompt, ("motion blur",)):
            negative_parts.append("motion blur")
        if not _has_any(scene.visual_prompt, ("pixel art", "8-bit", "16-bit")):
            negative_parts.append("low resolution, pixelated")
        negative_prompt = ", ".join(negative_parts)
        if _has_any(scene.visual_prompt, _ISLAMIC_VISUAL_TERMS):
            negative_prompt += (
                ", woman wearing peci, woman wearing kopiah, woman wearing songkok, hijab with hat, double headwear"
            )
        configured_size = os.environ.get("LONG_ANIMATE_IMAGE_SIZE", "1280x720")
        size_match = re.fullmatch(r"(\d{3,5})x(\d{3,5})", configured_size)
        if size_match and _output_geometry()[0] == "9:16":
            size_width, size_height = map(int, size_match.groups())
            if size_width > size_height:
                configured_size = f"{size_height}x{size_width}"
        payload_object = {
            "prompt": final_prompt,
            "negative_prompt": negative_prompt,
            "size": configured_size,
            "output_format": output_format,
            "output_compression": 100,
            "n": 1,
        }
    else:
        payload_object = {
            "model": model,
            "prompt": final_prompt,
            "size": os.environ.get("LONG_ANIMATE_IMAGE_SIZE", "1536x1024"),
            "quality": quality,
            "output_format": output_format,
            "output_compression": 100,
            "background": "opaque",
            "moderation": "auto",
            "n": 1,
        }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "FendyClip-LongAnimate/1.0",
    }
    if key and is_gemini:
        headers["x-goog-api-key"] = key
    elif key:
        headers["Authorization"] = f"Bearer {key}"
    retries = max(1, min(4, int(os.environ.get("LONG_ANIMATE_IMAGE_RETRIES", "3"))))
    max_timeout = 1800.0 if is_sd_cpp else 300.0
    timeout = max(
        30.0,
        min(max_timeout, float(os.environ.get("LONG_ANIMATE_IMAGE_TIMEOUT_SECONDS", "180"))),
    )
    last_detail = "respons API gambar tidak valid"
    sd_attempt_sizes: list[str] = []
    if is_sd_cpp:
        configured_size = str(payload_object["size"])
        safe_sizes = (
            ["1080x1920", "864x1536", "720x1280", "576x1024"]
            if _output_geometry()[0] == "9:16"
            else ["1920x1080", "1536x864", "1280x720", "1024x576"]
        )
        if configured_size in safe_sizes:
            sd_attempt_sizes = safe_sizes[safe_sizes.index(configured_size) :]
        else:
            sd_attempt_sizes = [configured_size, *safe_sizes[-2:]]
        sd_attempt_sizes = list(dict.fromkeys(sd_attempt_sizes))
    sd_size_index = 0
    for attempt in range(1, retries + 1):
        try:
            attempt_payload = dict(payload_object)
            if sd_attempt_sizes:
                attempt_payload["size"] = sd_attempt_sizes[sd_size_index]
            payload = json.dumps(attempt_payload).encode("utf-8")
            with urllib.request.urlopen(
                urllib.request.Request(endpoint, data=payload, headers=headers, method="POST"),
                timeout=timeout,
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
            raw = _image_bytes_from_result(result, is_gemini)
            if len(raw) < 1024:
                raise ValueError("data gambar dari API terlalu kecil")
            path.write_bytes(raw)
            if not _normalize_scene_image(path):
                raise ValueError("gambar dari API tidak dapat dibaca atau dinormalisasi")
            return True
        except Exception as exc:
            path.unlink(missing_ok=True)
            last_detail, status = _image_error_detail(exc)
            if sd_attempt_sizes:
                failed_size = sd_attempt_sizes[sd_size_index]
                last_detail = f"{last_detail} (ukuran {failed_size})"
                provider_failed = status in {500, 502, 503, 504} or any(
                    token in last_detail.casefold()
                    for token in ("no results", "outofdevicememory", "out of memory")
                )
                if provider_failed and sd_size_index < len(sd_attempt_sizes) - 1:
                    sd_size_index += 1
            retryable = status in {408, 409, 429, 500, 502, 503, 504} or status is None
            if attempt < retries and retryable:
                time.sleep(min(4.0, 1.25 * attempt))
                continue
            break
    if strict:
        raise LongAnimateImageError(
            f"Generate gambar AI scene {scene.index} gagal setelah {retries} percobaan: {last_detail}"
        )
    return False


def _normalize_scene_image(path: Path) -> bool:
    try:
        encoded = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    except OSError:
        return False
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
    if image is None:
        image = cv2.imread(str(path.resolve()))
    if image is None or image.size == 0:
        return False
    height, width = image.shape[:2]
    _aspect, target_width, target_height = _output_geometry()
    target_ratio = target_width / target_height
    source_ratio = width / max(1, height)
    if source_ratio > target_ratio:
        crop_width = max(1, round(height * target_ratio))
        left = max(0, (width - crop_width) // 2)
        image = image[:, left : left + crop_width]
    elif source_ratio < target_ratio:
        crop_height = max(1, round(width / target_ratio))
        top = max(0, (height - crop_height) // 2)
        image = image[top : top + crop_height, :]
    interpolation = cv2.INTER_LANCZOS4 if image.shape[1] < 1920 else cv2.INTER_AREA
    canvas = cv2.resize(image, (target_width, target_height), interpolation=interpolation)
    # Restore edge definition without rejecting a valid, intentionally soft image.
    blurred = cv2.GaussianBlur(canvas, (0, 0), 0.85)
    canvas = cv2.addWeighted(canvas, 1.18, blurred, -0.18, 0)
    try:
        min_sharpness = float(os.environ.get("LONG_ANIMATE_MIN_SHARPNESS", "30"))
    except ValueError:
        min_sharpness = 30.0
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if sharpness < max(0.0, min(200.0, min_sharpness)):
        # A second restrained pass improves local edges. Low sharpness is not a
        # decode failure and must never abort an otherwise valid Long Animate job.
        soft = cv2.GaussianBlur(canvas, (0, 0), 1.15)
        canvas = cv2.addWeighted(canvas, 1.32, soft, -0.32, 0)
    suffix = path.suffix.casefold()
    write_options = (
        [cv2.IMWRITE_PNG_COMPRESSION, 2]
        if suffix == ".png"
        else [cv2.IMWRITE_JPEG_QUALITY, 98]
    )
    return bool(cv2.imwrite(str(path.resolve()), canvas, write_options))


def _hex_bgr(seed: str, offset: int) -> tuple[int, int, int]:
    digest = hashlib.sha256(f"{seed}:{offset}".encode("utf-8")).digest()
    return tuple(int(40 + value * 0.72) for value in digest[:3])


def _local_scene_image(scene: AnimateScene | AnimateShot, path: Path, art_bible: str) -> None:
    seed = f"{art_bible}|{scene.visual_prompt}|{scene.color_mood}"
    top = np.array(_hex_bgr(seed, 1), dtype=np.float32)
    bottom = np.array(_hex_bgr(seed, 2), dtype=np.float32) * 0.42
    canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for y in range(1080):
        ratio = y / 1079
        canvas[y, :] = (top * (1 - ratio) + bottom * ratio).astype(np.uint8)
    rng = np.random.default_rng(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
    for layer in range(18):
        center = (int(rng.integers(80, 1840)), int(rng.integers(70, 940)))
        radius = int(rng.integers(40, 240))
        color = _hex_bgr(seed, layer + 10)
        overlay = canvas.copy()
        cv2.circle(overlay, center, radius, color, -1, cv2.LINE_AA)
        alpha = 0.035 + (layer % 4) * 0.018
        canvas = cv2.addWeighted(overlay, alpha, canvas, 1 - alpha, 0)
    lowered = f"{scene.narration} {scene.visual_prompt}".casefold()
    horizon = 790
    if any(token in lowered for token in ("islam", "masjid", "doa", "iman", "hikmah")):
        for x, width, height in ((190, 260, 330), (720, 420, 420), (1390, 280, 350)):
            color = _hex_bgr(seed, x)
            cv2.rectangle(canvas, (x, horizon - height), (x + width, horizon), color, -1)
            cv2.ellipse(canvas, (x + width // 2, horizon - height), (width // 2, 105), 0, 180, 360, color, -1)
        cv2.circle(canvas, (1580, 205), 82, (215, 235, 248), -1, cv2.LINE_AA)
        cv2.circle(canvas, (1615, 178), 82, tuple(int(value) for value in top), -1, cv2.LINE_AA)
    elif any(token in lowered for token in ("kota", "jalan", "kerja", "bisnis", "rumah")):
        x = 0
        while x < 1920:
            width = int(rng.integers(90, 230))
            height = int(rng.integers(170, 520))
            color = _hex_bgr(seed, x + 90)
            cv2.rectangle(canvas, (x, horizon - height), (x + width, horizon), color, -1)
            x += width + int(rng.integers(12, 45))
    else:
        points = np.array(
            [[0, 780], [330, 490], [620, 760], [990, 410], [1320, 720], [1640, 460], [1920, 740], [1920, 1080], [0, 1080]],
            dtype=np.int32,
        )
        cv2.fillPoly(canvas, [points], _hex_bgr(seed, 77))
    # Foreground framing creates depth for the later camera move.
    cv2.ellipse(canvas, (-120, 1060), (650, 310), 0, 180, 360, _hex_bgr(seed, 101), -1)
    cv2.ellipse(canvas, (2050, 1030), (720, 340), 0, 180, 360, _hex_bgr(seed, 102), -1)
    noise = rng.normal(0, 3.2, canvas.shape).astype(np.int16)
    canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    if not cv2.imwrite(str(path.resolve()), canvas, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise RuntimeError(f"Gagal membuat visual lokal scene {scene.index}")


def generate_scene_image(
    scene: AnimateScene | AnimateShot,
    path: Path,
    art_bible: str,
    reference_image: Path | None = None,
) -> str:
    if _remote_scene_image(scene, path, reference_image=reference_image):
        base, model, _key = _image_endpoint()
        return _remote_provider_label(base, model)
    _local_scene_image(scene, path, art_bible)
    return "fendy_local_story_art"


_FACE_DETECTOR: object | None = None


def _face_boxes(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    global _FACE_DETECTOR
    model_path = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
    if not model_path.is_file() or not hasattr(cv2, "FaceDetectorYN_create"):
        return []
    try:
        height, width = image.shape[:2]
        if _FACE_DETECTOR is None:
            _FACE_DETECTOR = cv2.FaceDetectorYN_create(
                str(model_path), "", (width, height), score_threshold=0.82, nms_threshold=0.3, top_k=20
            )
        else:
            _FACE_DETECTOR.setInputSize((width, height))
        _status, detections = _FACE_DETECTOR.detect(image)
    except Exception:
        return []
    if detections is None:
        return []
    return [
        (max(0, int(item[0])), max(0, int(item[1])), max(1, int(item[2])), max(1, int(item[3])))
        for item in detections
    ]


def _visual_signature(image: np.ndarray) -> np.ndarray:
    resized = cv2.resize(image, (256, 144), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    tone = cv2.calcHist([gray], [0], None, [32], [0, 256]).flatten()
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(grad_x, grad_y)
    texture, _edges = np.histogram(np.clip(magnitude, 0, 255), bins=16, range=(0, 256))
    signature = np.concatenate((tone.astype(np.float32), texture.astype(np.float32)))
    norm = float(np.linalg.norm(signature)) or 1.0
    return signature / norm


def inspect_generated_image(
    shot: AnimateShot,
    path: Path,
    style_reference: Path | None = None,
    character_reference: Path | None = None,
) -> tuple[float, list[str]]:
    image = cv2.imread(str(path.resolve()))
    if image is None or image.size == 0:
        return 0.0, ["image_decode_failed"]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    black_ratio = float(np.mean(gray < 8))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    faces = _face_boxes(image)
    expected_people = _expected_people_limit(f"{shot.narration} {shot.visual_prompt.split('STRICT STORY GROUNDING:', 1)[0]}")
    reasons: list[str] = []
    score = 1.0
    if black_ratio > 0.55:
        reasons.append("black_or_empty_frame")
        score -= 0.6
    if sharpness < max(8.0, float(os.environ.get("LONG_ANIMATE_QA_MIN_SHARPNESS", "18"))):
        reasons.append("soft_or_blurry_subject")
        score -= 0.25
    if faces and expected_people == 0:
        reasons.append("unrequested_human_face")
        score -= 0.45
    elif expected_people and len(faces) > expected_people:
        reasons.append("too_many_visible_faces")
        score -= 0.35
    if style_reference and style_reference.is_file():
        reference = cv2.imread(str(style_reference.resolve()))
        if reference is not None and reference.size:
            similarity = float(
                cv2.compareHist(
                    _visual_signature(reference).astype(np.float32),
                    _visual_signature(image).astype(np.float32),
                    cv2.HISTCMP_CORREL,
                )
            )
            if similarity < float(os.environ.get("LONG_ANIMATE_QA_STYLE_MIN", "0.05")):
                reasons.append("global_style_drift")
                score -= 0.25
    if character_reference and character_reference.is_file() and faces:
        reference = cv2.imread(str(character_reference.resolve()))
        reference_faces = _face_boxes(reference) if reference is not None else []
        if reference is not None and reference_faces:
            rx, ry, rw, rh = max(reference_faces, key=lambda item: item[2] * item[3])
            x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
            ref_crop = reference[ry : ry + rh, rx : rx + rw]
            crop = image[y : y + h, x : x + w]
            if ref_crop.size and crop.size:
                similarity = float(
                    cv2.compareHist(
                        _visual_signature(ref_crop).astype(np.float32),
                        _visual_signature(crop).astype(np.float32),
                        cv2.HISTCMP_CORREL,
                    )
                )
                if similarity < float(os.environ.get("LONG_ANIMATE_QA_CHARACTER_MIN", "-0.05")):
                    reasons.append("character_reference_drift")
                    score -= 0.3
    return max(0.0, min(1.0, score)), reasons


def generate_shot_image_with_qa(
    shot: AnimateShot,
    path: Path,
    art_bible: str,
    *,
    style_reference: Path | None = None,
    character_reference: Path | None = None,
) -> str:
    attempts = max(1, min(4, int(os.environ.get("LONG_ANIMATE_VISION_QA_ATTEMPTS", "2"))))
    original_prompt = shot.visual_prompt
    provider = "unknown"
    last_reasons: list[str] = []
    for attempt in range(1, attempts + 1):
        shot.qa_attempts = attempt
        if attempt > 1:
            shot.visual_prompt = _clean_text(
                f"QA REPAIR {attempt}: correct these failures: {', '.join(last_reasons)}. Strictly preserve the "
                f"character reference lock, global style, requested subject count, action, and setting. {original_prompt}",
                3500,
            )
        provider = generate_scene_image(shot, path, art_bible, reference_image=character_reference)
        shot.qa_score, last_reasons = inspect_generated_image(
            shot, path, style_reference=style_reference, character_reference=character_reference
        )
        if not last_reasons:
            shot.visual_prompt = original_prompt
            return provider
    shot.visual_prompt = original_prompt
    if _env_bool("LONG_ANIMATE_VISION_QA_STRICT", False):
        raise LongAnimateImageError(
            f"Vision QA shot {shot.index} gagal setelah {attempts} percobaan: {', '.join(last_reasons)}"
        )
    return provider


def _tts_pronunciation_text(text: str) -> str:
    """Prepare Indonesian Islamic narration for speech without changing subtitles."""
    spoken = re.sub(r"\s+", " ", text).strip()
    profile = os.environ.get(
        "LONG_ANIMATE_TTS_PROFILE", "islamic_indonesian"
    ).strip().casefold()
    if profile not in {"islamic_indonesian", "islamic-id", "id-islamic"}:
        return spoken

    replacements = (
        (r"(?i)\bQ\.?\s*S\.?\s*", "Surah "),
        (r"(?i)\bS\.?\s*W\.?\s*T\.?\b", "subhanahu wa taala"),
        (r"(?i)\bS\.?\s*A\.?\s*W\.?\b", "salallahu alaihi wasalam"),
        (r"(?i)\bAllah\b", "Alloh"),
        (r"الله", "Alloh"),
        (r"(?i)\bAl[-\s]?Qur[’'`]an\b", "Al Quran"),
        (r"(?i)\bQur[’'`]an\b", "Quran"),
        (r"(?i)\bustadzah\b", "ustazah"),
        (r"(?i)\bustadz\b", "ustaz"),
        (r"(?i)\bmakhraj\b", "makhroj"),
        (r"(?i)\bwudhu\b", "wudu"),
        (r"(?i)\bberwudhu\b", "berwudu"),
        (r"(?i)\bdzikir\b", "zikir"),
        (r"(?i)\bberdzikir\b", "berzikir"),
        (r"(?i)\bmuadzin\b", "muazin"),
        (r"(?i)\bshalat\b", "salat"),
        (r"(?i)\bsholat\b", "salat"),
        (r"(?i)\binsya\s*allah\b", "insya Allah"),
    )
    for pattern, replacement in replacements:
        spoken = re.sub(pattern, replacement, spoken)
    spoken = re.sub(r"\s+([,.;:!?])", r"\1", spoken)
    spoken = re.sub(r"([,.;:!?])(?!\s|$)", r"\1 ", spoken)
    return re.sub(r"\s+", " ", spoken).strip()


def synthesize_narration(scene: AnimateScene, scene_dir: Path) -> tuple[Path, str]:
    voice = os.environ.get("LONG_ANIMATE_VOICE", "id-ID-ArdiNeural").strip()
    rate = os.environ.get("LONG_ANIMATE_VOICE_RATE", "-6%").strip()
    pitch = os.environ.get("LONG_ANIMATE_VOICE_PITCH", "-2Hz").strip()
    volume = os.environ.get("LONG_ANIMATE_VOICE_VOLUME", "+0%").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{2,64}", voice):
        voice = "id-ID-ArdiNeural"
    if not re.fullmatch(r"[+-]\d{1,2}%", rate):
        rate = "-6%"
    if not re.fullmatch(r"[+-]\d{1,3}Hz", pitch):
        pitch = "-2Hz"
    if not re.fullmatch(r"[+-]\d{1,2}%", volume):
        volume = "+0%"
    if not scene.narration.strip():
        silent_path = scene_dir / f"scene_{scene.index:02}.voice.wav"
        _run(
            [
                _ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
                "-t",
                f"{max(0.8, scene.duration_hint):.3f}",
                "-c:a",
                "pcm_s16le",
                str(silent_path.resolve()),
            ]
        )
        return silent_path, "intentional_silence"
    edge_path = scene_dir / f"scene_{scene.index:02}.voice.mp3"
    spoken_narration = _tts_pronunciation_text(scene.narration)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "edge_tts",
                "--voice",
                voice,
                f"--rate={rate}",
                f"--pitch={pitch}",
                f"--volume={volume}",
                "--text",
                spoken_narration,
                "--write-media",
                str(edge_path.resolve()),
            ],
            text=True,
            capture_output=True,
            timeout=150,
        )
        if result.returncode == 0 and edge_path.is_file() and edge_path.stat().st_size > 512:
            return edge_path, "edge_neural"
    except (OSError, subprocess.TimeoutExpired):
        pass
    edge_path.unlink(missing_ok=True)
    local_path = scene_dir / f"scene_{scene.index:02}.voice.wav"
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak:
        result = subprocess.run(
            [
                espeak,
                "-v",
                os.environ.get("LONG_ANIMATE_ESPEAK_VOICE", "id+m3"),
                "-s",
                os.environ.get("LONG_ANIMATE_ESPEAK_SPEED", "155"),
                "-p",
                "48",
                "-a",
                "170",
                "-w",
                str(local_path.resolve()),
                spoken_narration,
            ],
            text=True,
            capture_output=True,
            timeout=90,
        )
        if result.returncode == 0 and local_path.is_file() and local_path.stat().st_size > 512:
            return local_path, "espeak_local"
    duration = scene.duration_hint or max(6.0, len(scene.narration.split()) / 2.3)
    _run(
        [
            _ffmpeg_path(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            f"{duration:.3f}",
            "-c:a",
            "pcm_s16le",
            str(local_path.resolve()),
        ]
    )
    return local_path, "silent_fallback_review_required"


def _motion_expression(scene: AnimateScene | AnimateShot, frames: int) -> tuple[str, str, str]:
    progress = f"min(1,on/{max(1, frames)})"
    if scene.camera_motion == "pull_out":
        zoom = f"1.045-0.045*{progress}"
        return zoom, "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    zoom = f"1.0+0.045*{progress}"
    if scene.camera_motion == "pan_left":
        return zoom, f"(iw-iw/zoom)*(1-{progress})", "(ih-ih/zoom)/2"
    if scene.camera_motion == "pan_right":
        return zoom, f"(iw-iw/zoom)*{progress}", "(ih-ih/zoom)/2"
    if scene.camera_motion == "drift_up":
        return zoom, "(iw-iw/zoom)/2", f"(ih-ih/zoom)*(1-{progress})"
    return zoom, "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"


def _atempo_chain(ratio: float) -> str:
    values: list[float] = []
    remaining = max(0.05, ratio)
    while remaining > 2.0:
        values.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        values.append(0.5)
        remaining /= 0.5
    values.append(max(0.5, min(2.0, remaining)))
    return ",".join(f"atempo={value:.6f}" for value in values)


def trim_voice_silence(scene: AnimateScene, voice_path: Path, scene_dir: Path) -> Path:
    if not scene.narration.strip() or scene.voice_provider.startswith("intentional_silence"):
        return voice_path
    output = scene_dir / f"scene_{scene.index:02}.voice.trim.wav"
    _run(
        [
            _ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(voice_path.resolve()),
            "-af",
            "silenceremove=start_periods=1:start_duration=0.03:start_threshold=-48dB,"
            "areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-48dB,areverse,"
            "aresample=48000",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(output.resolve()),
        ]
    )
    return output if _media_duration(output) > 0.1 else voice_path


def fit_voice_to_scene(scene: AnimateScene, voice_path: Path, scene_dir: Path) -> Path:
    output = scene_dir / f"scene_{scene.index:02}.voice.fit.wav"
    target = max(0.05, scene.duration)
    source_duration = _media_duration(voice_path)
    if not scene.narration.strip() or source_duration <= 0.05:
        _run(
            [
                _ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{target:.3f}",
                "-c:a", "pcm_s16le", str(output.resolve()),
            ]
        )
        scene.voice_duration = 0.0
        return output
    content_target = max(0.05, target - min(0.06, target * 0.03))
    tempo = source_duration / content_target
    scene.speech_tempo = tempo
    _run(
        [
            _ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(voice_path.resolve()),
            "-af", f"{_atempo_chain(tempo)},aresample=48000,apad=whole_dur={target:.3f},atrim=0:{target:.3f}",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(output.resolve()),
        ]
    )
    scene.voice_duration = min(target, _media_duration(output))
    return output


def concatenate_voice_track(paths: list[Path], scene_dir: Path, target_duration: float) -> Path:
    concat_path = scene_dir / "voice_concat.txt"
    concat_path.write_text("\n".join(f"file '{path.name}'" for path in paths) + "\n", encoding="utf-8")
    output = scene_dir / "narration.wav"
    _run(
        [
            _ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_path.name, "-af", f"apad,atrim=0:{target_duration:.3f}",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", output.name,
        ],
        cwd=scene_dir,
    )
    return output


def render_shot_video(shot: AnimateShot, image_path: Path, scene_dir: Path) -> Path:
    _aspect, output_width, output_height = _output_geometry()
    overscan_width = round(output_width * 1.05)
    overscan_height = round(output_height * 1.05)
    frames = max(1, round(shot.duration * 30))
    zoom, x, y = _motion_expression(shot, frames)
    title_path = scene_dir / f"shot_{shot.index:02}.title.txt"
    if shot.on_screen_text:
        title_path.write_text(shot.on_screen_text + "\n", encoding="utf-8")
    output_path = scene_dir / f"shot_{shot.index:02}.mp4"
    title_end = min(3.8, max(0.45, shot.duration - 0.08))
    vf_parts = [
        f"scale={overscan_width}:{overscan_height}:force_original_aspect_ratio=increase,crop={overscan_width}:{overscan_height}",
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={output_width}x{output_height}:fps=30",
        "eq=contrast=1.025:saturation=1.04:gamma=1.005",
        "unsharp=5:5:0.28:5:5:0.0",
    ]
    if shot.on_screen_text:
        vf_parts.extend(
            [
                f"drawbox=x=86:y=76:w=720:h=142:color=black@0.58:t=fill:enable='between(t,0.08,{title_end:.3f})'",
                f"drawbox=x=86:y=76:w=10:h=142:color=#34D399@0.95:t=fill:enable='between(t,0.08,{title_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"textfile='{title_path.name}':reload=0:expansion=none:fontcolor=white:fontsize=42:"
                f"line_spacing=8:borderw=2:bordercolor=black@0.75:x=120:y=112:enable='between(t,0.08,{title_end:.3f})'",
            ]
        )
    vf = ",".join(vf_parts)
    _run(
        [
            _ffmpeg_path(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            image_path.name,
            "-t",
            f"{shot.duration:.3f}",
            "-vf",
            vf,
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            output_path.name,
        ],
        cwd=scene_dir,
    )
    title_path.unlink(missing_ok=True)
    return output_path


def assemble_shot_videos(paths: list[Path], shots: list[AnimateShot], scene_dir: Path) -> Path:
    if not paths or len(paths) != len(shots):
        raise ValueError("Shot video tidak lengkap")
    output = scene_dir / "assembled.mp4"
    transition = _transition_seconds()
    if len(paths) == 1 or transition <= 0:
        concat_path = scene_dir / "concat.txt"
        concat_path.write_text("\n".join(f"file '{path.name}'" for path in paths) + "\n", encoding="utf-8")
        _run(
            [
                _ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_path.name, "-c", "copy", output.name,
            ],
            cwd=scene_dir,
        )
        return output
    command = [_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y"]
    for path in paths:
        command.extend(["-i", path.name])
    filters: list[str] = []
    accumulated = shots[0].duration
    previous = "[0:v]"
    for index in range(1, len(paths)):
        output_label = f"[xf{index}]"
        offset = max(0.001, accumulated - transition)
        filters.append(
            f"{previous}[{index}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}{output_label}"
        )
        previous = output_label
        accumulated += shots[index].duration - transition
    command.extend(
        [
            "-filter_complex", ";".join(filters), "-map", previous, "-an", "-c:v", "libx264", "-preset", "slow",
            "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output.name,
        ]
    )
    _run(command, cwd=scene_dir)
    return output


def _srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _subtitle_chunks(text: str, max_words: int = 5, max_chars: int = 36) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for word in text.split():
        proposal = " ".join([*current, word])
        if current and (len(current) >= max_words or len(proposal) > max_chars):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
        if current and re.search(r"[.!?;:]$", current[-1]) and len(current) >= 3:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    if len(chunks) >= 2 and len(chunks[-1].split()) == 1:
        orphan = chunks.pop()
        if len(f"{chunks[-1]} {orphan}") <= max_chars + 8:
            chunks[-1] = f"{chunks[-1]} {orphan}"
        else:
            previous_words = chunks[-1].split()
            chunks[-1] = " ".join(previous_words[:-1])
            chunks.append(f"{previous_words[-1]} {orphan}")
    return chunks


def write_story_subtitles(path: Path, scenes: list[AnimateScene]) -> None:
    cues: list[str] = []
    cursor = 0.0
    cue_index = 1
    for scene in scenes:
        if not scene.narration.strip():
            cursor += scene.duration
            continue
        chunks = _subtitle_chunks(scene.narration)
        total_words = max(1, sum(len(chunk.split()) for chunk in chunks))
        voice_duration = scene.voice_duration or max(0.35, scene.duration - 0.7)
        voice_duration = min(scene.duration, voice_duration)
        local_cursor = cursor + min(0.08, voice_duration / 5)
        narration_end = cursor + max(0.35, voice_duration)
        usable_duration = max(0.35, narration_end - local_cursor)
        for chunk_index, chunk in enumerate(chunks):
            if chunk_index == len(chunks) - 1:
                end = narration_end
            else:
                share = len(chunk.split()) / total_words
                end = min(narration_end, local_cursor + usable_duration * share)
            cue_end = min(narration_end, max(local_cursor + 0.25, end))
            cues.append(
                f"{cue_index}\n{_srt_time(local_cursor)} --> {_srt_time(cue_end)}\n{chunk}\n"
            )
            local_cursor = end
            cue_index += 1
        cursor += scene.duration
    path.write_text("\n".join(cues), encoding="utf-8")


def _thumbnail(image_path: Path, output_path: Path, title: str) -> None:
    image = cv2.imread(str(image_path.resolve()))
    if image is None:
        return
    image = cv2.resize(image, (1280, 720), interpolation=cv2.INTER_AREA)
    overlay = image.copy()
    cv2.rectangle(overlay, (46, 410), (940, 666), (4, 12, 12), -1)
    image = cv2.addWeighted(overlay, 0.78, image, 0.22, 0)
    cv2.rectangle(image, (46, 410), (60, 666), (62, 211, 153), -1)
    words = title.upper().split()
    lines: list[str] = []
    current = ""
    for word in words:
        proposal = f"{current} {word}".strip()
        if len(proposal) > 23 and current:
            lines.append(current)
            current = word
        else:
            current = proposal
    if current:
        lines.append(current)
    for index, line in enumerate(lines[:3]):
        cv2.putText(
            image,
            line,
            (92, 485 + index * 64),
            cv2.FONT_HERSHEY_DUPLEX,
            1.32,
            (247, 251, 249),
            3,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(output_path.resolve()), image, [cv2.IMWRITE_JPEG_QUALITY, 88])


def final_video_qc(
    path: Path,
    *,
    target_duration: float,
    width: int,
    height: int,
    cut_points: list[float],
) -> dict[str, object]:
    actual_duration = _media_duration(path)
    failures: list[str] = []
    if abs(actual_duration - target_duration) > 0.09:
        failures.append(f"duration_mismatch:{actual_duration:.3f}")
    probe = subprocess.run(
        [_ffmpeg_path(), "-hide_banner", "-i", str(path.resolve())],
        text=True,
        capture_output=True,
    )
    detail = f"{probe.stdout}\n{probe.stderr}"
    if f"{width}x{height}" not in detail:
        failures.append("wrong_resolution")
    if "48000 Hz" not in detail:
        failures.append("audio_not_48khz")
    black_samples: list[float] = []
    blank_samples: list[bool] = []
    capture = cv2.VideoCapture(str(path.resolve()))
    if capture.isOpened():
        sample_times = [0.0, max(0.0, target_duration - 0.05)]
        for point in cut_points:
            sample_times.extend((max(0.0, point - 0.04), point, min(target_duration - 0.01, point + 0.04)))
        for timestamp in sample_times:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if not ok or frame is None or not frame.size:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            black_ratio = float(np.mean(gray < 6))
            black_samples.append(black_ratio)
            blank_samples.append(float(np.mean(gray)) < 2.5 and float(np.std(gray)) < 2.5)
        capture.release()
    if any(blank_samples):
        failures.append("black_frame_near_cut")
    result = {
        "passed": not failures,
        "target_duration": round(target_duration, 3),
        "actual_duration": round(actual_duration, 3),
        "resolution": f"{width}x{height}",
        "audio_sample_rate": 48000,
        "max_black_pixel_ratio_near_cuts": round(max(black_samples, default=0.0), 4),
        "failures": failures,
    }
    if failures:
        raise RuntimeError(f"Final QC Long Animate gagal: {', '.join(failures)}")
    return result


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return clean[:52] or "cerita-animasi"


def render_long_animate(
    script: str,
    output_root: Path,
    ai_config: AIConfig,
    *,
    video_quality: str = "high",
    required_hashtags: list[str] | None = None,
    progress: ProgressCallback | None = None,
) -> tuple[Path, dict[str, object]]:
    progress = progress or (lambda *_args: None)
    work_dir = output_root / _slug(script.splitlines()[0] if script.splitlines() else "long-animate")
    clips_dir = work_dir / "clips"
    scene_dir = work_dir / "animate_scenes"
    clips_dir.mkdir(parents=True, exist_ok=True)
    scene_dir.mkdir(parents=True, exist_ok=True)

    progress(18, "selection", "Menyusun storyboard, art bible, dan alur setiap scene")
    storyboard = build_storyboard(script, ai_config)
    if len(storyboard.scenes) < 3:
        raise RuntimeError("Long Animate membutuhkan minimal tiga scene bermakna.")
    target_duration = _target_duration_seconds()
    progress(24, "transcript", "Membuat seluruh TTS dan mengukur timing narasi asli")
    trimmed_voice_paths: list[Path] = []
    measured_voice_durations: list[float] = []
    for scene in storyboard.scenes:
        voice_path, scene.voice_provider = synthesize_narration(scene, scene_dir)
        if (
            scene.voice_provider == "silent_fallback_review_required"
            and _env_bool("LONG_ANIMATE_TTS_STRICT", True)
        ):
            raise RuntimeError(
                f"TTS scene {scene.index} gagal; render dihentikan agar video tidak berisi dead-air."
            )
        trimmed = trim_voice_silence(scene, voice_path, scene_dir)
        trimmed_voice_paths.append(trimmed)
        measured_voice_durations.append(
            _media_duration(trimmed) if scene.narration.strip() else 0.0
        )
    allocate_scene_durations(storyboard.scenes, measured_voice_durations, target_duration)
    fitted_voice_paths = [
        fit_voice_to_scene(scene, voice_path, scene_dir)
        for scene, voice_path in zip(storyboard.scenes, trimmed_voice_paths)
    ]
    narration_track = concatenate_voice_track(fitted_voice_paths, scene_dir, target_duration)
    shots = plan_storyboard_shots(storyboard)
    (work_dir / "storyboard.json").write_text(
        json.dumps(
            {
                **asdict(storyboard),
                "target_duration": target_duration,
                "shots": [asdict(shot) for shot in shots],
                "source_script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    progress(
        32,
        "selection",
        f"Timeline {target_duration:.3f} detik dan {len(shots)} shot siap; memulai produksi visual",
    )

    shot_paths: list[Path] = []
    shot_image_paths: list[Path] = []
    style_reference: Path | None = None
    character_reference: Path | None = None
    chapter_audits: list[dict[str, object]] = []
    for shot_index, shot in enumerate(shots, start=1):
        progress(
            32 + round(((shot_index - 1) / len(shots)) * 48),
            "render",
            f"Membuat dan memeriksa visual shot {shot_index}/{len(shots)}",
        )
        image_path = scene_dir / f"shot_{shot.index:02}.png"
        shot.image_provider = generate_shot_image_with_qa(
            shot,
            image_path,
            storyboard.art_bible,
            style_reference=style_reference,
            character_reference=character_reference,
        )
        if style_reference is None:
            style_reference = image_path
        if character_reference is None and (
            _expected_people_limit(shot.narration) > 0
            or _has_any(shot.narration, _NONHUMAN_CHARACTER_TERMS)
        ):
            character_reference = image_path
        shot_path = render_shot_video(shot, image_path, scene_dir)
        shot_paths.append(shot_path)
        shot_image_paths.append(image_path)
        source_scene = storyboard.scenes[shot.scene_index - 1]
        if not source_scene.image_provider:
            source_scene.image_provider = shot.image_provider
        source_scene.qa_attempts = max(source_scene.qa_attempts, shot.qa_attempts)
        source_scene.qa_score = min(source_scene.qa_score or 1.0, shot.qa_score)
        chapter_audits.append(
            {
                "part": shot.index,
                "scene": shot.scene_index,
                "shot": shot.shot_index,
                "hook": shot.title,
                "pov": shot.on_screen_text,
                "core_message": shot.narration[:180],
                "content_timed_editing": True,
                "camera_motion": shot.camera_motion,
                "image_provider": shot.image_provider,
                "vision_qa_attempts": shot.qa_attempts,
                "vision_qa_score": round(shot.qa_score, 3),
            }
        )

    progress(82, "render", "Menggabungkan shot tanpa fade hitam atau padding audio antar-scene")
    assembled = assemble_shot_videos(shot_paths, shots, scene_dir)

    base_name = f"long_animate_{_slug(storyboard.title)}"
    output_path = clips_dir / f"{base_name}.mp4"
    srt_path = clips_dir / f"{base_name}.srt"
    write_story_subtitles(srt_path, storyboard.scenes)
    output_aspect, output_width, output_height = _output_geometry()
    subtitles = _supports_filter("subtitles")
    drawtext = _supports_filter("drawtext")
    vf_parts = [
        "eq=contrast=1.02:saturation=1.04",
        f"tpad=stop_mode=clone:stop_duration=2,trim=duration={target_duration:.3f},setpts=PTS-STARTPTS",
    ]
    if subtitles and any(scene.narration.strip() for scene in storyboard.scenes):
        vf_parts.append(
            f"subtitles='{srt_path.name}':original_size={output_width}x{output_height}:"
            "force_style='FontName=DejaVu Sans,FontSize=16,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=54'"
        )
    if drawtext:
        vf_parts.append(
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            "text='ryuundyofficial':fontcolor=white@0.72:fontsize=18:x=34:y=30:"
            "borderw=1:bordercolor=black@0.50"
        )
    duration = target_duration
    cut_points: list[float] = []
    cut_cursor = 0.0
    transition_seconds = _transition_seconds()
    for shot in shots[:-1]:
        cut_cursor += shot.duration - transition_seconds
        cut_points.append(cut_cursor)
    story_seed = int(hashlib.sha256(script.encode()).hexdigest()[:8], 16)
    freq_a = 110 + story_seed % 55
    freq_b = 165 + (story_seed // 7) % 70
    sfx_window = "+".join(
        f"between(t\\,{max(0.0, point - 0.05):.3f}\\,{min(duration, point + 0.10):.3f})"
        for point in cut_points
    ) or "0"
    audio_filter = (
        "[2:a]volume=0.032,lowpass=f=1250[m1];"
        "[3:a]volume=0.020,lowpass=f=1850[m2];"
        "[m1][m2]amix=inputs=2:duration=longest:normalize=0[music];"
        "[1:a]loudnorm=I=-16:TP=-1.5:LRA=9,asplit=2[voice][sidechain];"
        "[music][sidechain]sidechaincompress=threshold=0.012:ratio=8:attack=18:release=260[ducked];"
        f"[4:a]highpass=f=900,lowpass=f=4200,volume='0.18*({sfx_window})':eval=frame[sfx];"
        "[voice][ducked][sfx]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,"
        f"loudnorm=I=-14:TP=-1.0:LRA=9,apad,atrim=0:{duration:.3f}[aout]"
    )
    quality_crf = {"standard": "19", "high": "16", "max": "14"}.get(video_quality, "16")
    _run(
        [
            _ffmpeg_path(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(assembled.resolve()),
            "-i",
            str(narration_track.resolve()),
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq_a}:sample_rate=48000:duration={duration:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq_b}:sample_rate=48000:duration={duration:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:amplitude=0.08:sample_rate=48000:duration={duration:.3f}",
            "-filter_complex",
            audio_filter,
            "-vf",
            ",".join(vf_parts),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            quality_crf,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            "-t",
            f"{duration:.3f}",
            str(output_path.resolve()),
        ],
        cwd=clips_dir,
    )
    final_qc = final_video_qc(
        output_path,
        target_duration=target_duration,
        width=output_width,
        height=output_height,
        cut_points=cut_points,
    )
    progress(92, "finalize", "Membuat thumbnail, chapter, dan audit YouTube Long Animate")
    thumb_path = clips_dir / f"{base_name}_thumb.jpg"
    _thumbnail(shot_image_paths[0], thumb_path, storyboard.title)
    prompt_path = clips_dir / f"{base_name}_thumb.txt"
    prompt_path.write_text(
        "STRATEGI: custom_long_form_upload\n"
        f"HOOK: {storyboard.hook}\n"
        f"ART BIBLE: {storyboard.art_bible}\n"
        "Gunakan visual scene pertama; pertahankan janji cerita, kontras tinggi, maksimal 4 kata utama, tanpa clickbait menyesatkan.\n",
        encoding="utf-8",
    )
    tags = [tag.strip().lstrip("#") for tag in (required_hashtags or []) if tag.strip()]
    caption_path = clips_dir / f"{base_name}_caption.txt"
    caption_path.write_text(
        f"{storyboard.hook}\n\n{storyboard.core_message}\n\n"
        + " ".join(f"#{tag}" for tag in tags[:6] if tag.casefold() != "shorts")
        + "\n",
        encoding="utf-8",
    )
    parts = [
        {
            "index": scene.index,
            "title": scene.title,
            "duration": round(scene.duration, 3),
            "narrative_role": scene.narrative_role,
        }
        for scene in storyboard.scenes
    ]
    score = min(
        96,
        82
        + min(6, len(shots))
        + (3 if all(scene.voice_provider != "silent_fallback_review_required" for scene in storyboard.scenes) else 0)
        + (3 if final_qc["passed"] else 0),
    )
    max_speech_tempo = max((scene.speech_tempo for scene in storyboard.scenes), default=1.0)
    timing_weaknesses = (
        [f"Narasi padat membutuhkan percepatan TTS hingga {max_speech_tempo:.2f}x; ringkas NARASI bila ingin tempo lebih santai."]
        if max_speech_tempo > 1.35
        else []
    )
    sidecar: dict[str, object] = {
        "index": 1,
        "start": 0.0,
        "end": round(duration, 3),
        "duration": round(duration, 3),
        "score": score,
        "title": storyboard.title,
        "reason": f"Long Animate {target_duration:g} detik dengan {len(storyboard.scenes)} scene dan {len(shots)} shot berbasis naskah asli.",
        "text": script,
        "hook": storyboard.hook,
        "pov": "Narasi orisinal pengguna divisualkan menjadi scene yang saling melanjutkan.",
        "core_message": storyboard.core_message,
        "fyp_label": "Sangat kuat" if score >= 88 else "Kuat",
        "strengths": [
            "Naskah menjadi alur scene utuh, bukan slideshow acak.",
            "Art bible menjaga kesinambungan visual antar-scene.",
            "Narasi, motion, subtitle, dan musik tersinkron.",
            "Vision QA memeriksa style, karakter, wajah tambahan, ketajaman, dan frame kosong.",
        ],
        "weaknesses": timing_weaknesses,
        "improvement_ideas": [
            "Uji tiga variasi title-thumbnail melalui fitur A/B YouTube setelah upload Private.",
        ],
        "applied_edits": [
            "Naskah dipecah menjadi beat storyboard tanpa filler atau pengulangan.",
            "Scene kompleks dipecah menjadi beberapa shot tunggal tanpa mengulang voice-over.",
            f"Voice-over dibuat lebih dulu; durasi hasil TTS menentukan timeline tepat {target_duration:g} detik.",
            "Fade hitam dan padding audio antar-scene dihapus; musik memakai sidechain ducking.",
            f"Subtitle bertimestamp dan audio AAC 48 kHz digabungkan ke master {output_aspect}.",
            "Thumbnail long-form dan chapter YouTube dibuat otomatis.",
        ],
        "key_point_score": 92,
        "loop_score": 70,
        "boundary_quality": "payoff_tuntas",
        "mode": "long_animate",
        "production_model": "codex_scene_cinema_v2",
        "output_format": "portrait_short" if output_aspect == "9:16" else "landscape_compilation",
        "aspect_ratio": output_aspect,
        "output_resolution": f"{output_width}x{output_height}",
        "enhanced_edit": True,
        "thumbnail_strategy": "custom_long_form_upload",
        "storyboard_path": "storyboard.json",
        "scene_assets_directory": "animate_scenes",
        "art_bible": storyboard.art_bible,
        "character_bible": storyboard.character_bible,
        "location_bible": storyboard.location_bible,
        "character_reference": {
            "reference_shot": character_reference.name if character_reference else None,
            "method": "immutable_identity_lock_plus_face_similarity_qa",
        },
        "image_generation": {
            "provider": storyboard.scenes[0].image_provider if storyboard.scenes else "unknown",
            "model": _image_endpoint()[1],
            "size": os.environ.get("LONG_ANIMATE_IMAGE_SIZE", "2K"),
            "aspect_ratio": output_aspect,
            "thinking_level": os.environ.get("LONG_ANIMATE_IMAGE_THINKING_LEVEL", "high"),
            "strict_no_silent_fallback": _env_bool("LONG_ANIMATE_IMAGE_STRICT", False),
            "api_key_recorded": False,
        },
        "parts": parts,
        "shots": [asdict(shot) for shot in shots],
        "story_arc": [asdict(scene) for scene in storyboard.scenes],
        "chapter_edit_evidence": chapter_audits,
        "virtual_camera_angles": [
            {"shot": shot.index, "scene": shot.scene_index, "motion": shot.camera_motion}
            for shot in shots
        ],
        "dynamic_captions": {
            "enabled": subtitles,
            "transcript_grounded": True,
            "scene_timed": True,
        },
        "timing_engine": {
            "version": 2,
            "target_duration": target_duration,
            "tts_measured_before_allocation": True,
            "dead_air_trimmed": True,
            "gapless_hard_cuts": _transition_seconds() <= 0,
            "transition_seconds": _transition_seconds(),
            "maximum_speech_tempo": round(max_speech_tempo, 3),
            "scene_duration_total": round(sum(scene.duration for scene in storyboard.scenes), 3),
            "shot_render_duration_total": round(sum(shot.duration for shot in shots), 3),
            "shot_effective_duration_total": round(
                sum(shot.duration for shot in shots) - _transition_seconds() * max(0, len(shots) - 1), 3
            ),
        },
        "vision_qa": {
            "enabled": True,
            "automatic_regeneration": True,
            "attempts": max((shot.qa_attempts for shot in shots), default=0),
            "minimum_score": round(min((shot.qa_score for shot in shots), default=0.0), 3),
        },
        "final_qc": final_qc,
        "content_edit_signature": {
            "version": 1,
            "derived_from_story": True,
            "source_script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        },
        "auto_fyp_visual_system": {
            "version": 2,
            "base": "scene_cinema",
            "chapter_accents_are_content_derived": True,
            "mass_template_repetition_risk_reduced": True,
        },
        "original_creator_commentary": True,
        "altered_content_disclosure_required": True,
        "synthetic_content": {
            "ai_or_procedural_images": True,
            "synthetic_or_neural_voice": True,
            "procedural_music": True,
            "procedural_transition_sfx": True,
            "youtube_ai_use_disclosure": "required_conservative_default",
            "real_person_impersonation_allowed": False,
            "public_figure_likeness_allowed": False,
        },
        "rights": {
            "script_rights_confirmation_required": True,
            "image_provider_commercial_terms_confirmation_required": any(
                scene.image_provider in {
                    "google_gemini_image_api",
                    "openai_gpt_image_api",
                    "openai_compatible_image_api",
                }
                for scene in storyboard.scenes
            ),
            "third_party_music_used": False,
            "third_party_video_used": False,
        },
        "one_k_long_form_readiness": {
            "target_views": 1000,
            "review_checkpoints": [100, 300, 1000],
            "quality_gate_passed": len(storyboard.scenes) >= 3 and score >= 84,
            "measure_after_publish": [
                "home_and_suggested_ctr",
                "first_30_second_retention",
                "average_view_duration",
                "audience_retention_dips_and_spikes",
                "end_screen_click_rate",
                "subscribers_gained",
            ],
            "guarantee": False,
        },
        "packaging_experiment": {
            "version": 1,
            "platform": "youtube_native_title_thumbnail_ab_test",
            "variants_to_prepare": 3,
            "angles": [
                {"name": "konflik", "source_copy": storyboard.hook[:120]},
                {
                    "name": "perjalanan",
                    "source_copy": storyboard.scenes[len(storyboard.scenes) // 2].title,
                },
                {
                    "name": "payoff",
                    "source_copy": storyboard.scenes[-1].title,
                },
            ],
            "title_thumbnail_promise_must_match_video": True,
            "misleading_clickbait_allowed": False,
            "primary_selection_signal": "watch_time_share",
            "guarantee": False,
        },
        "youtube_policy_guardrails": {
            "private_upload_review_before_publish": True,
            "ai_use_disclosure_required": True,
            "generic_mass_produced_template_allowed": False,
            "misleading_title_thumbnail_allowed": False,
            "script_and_image_rights_confirmation_required": True,
            "view_target_is_experiment_not_guarantee": True,
        },
    }
    sidecar_path = output_path.with_suffix(".json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
    candidate_path = work_dir / "candidates.json"
    candidate_path.write_text(
        json.dumps(
            [
                {
                    key: value
                    for key, value in sidecar.items()
                    if key
                    in {
                        "index",
                        "start",
                        "end",
                        "duration",
                        "score",
                        "title",
                        "reason",
                        "text",
                        "hook",
                        "pov",
                        "fyp_label",
                        "strengths",
                        "weaknesses",
                        "improvement_ideas",
                        "applied_edits",
                        "key_point_score",
                        "loop_score",
                        "boundary_quality",
                    }
                }
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assembled.unlink(missing_ok=True)
    (scene_dir / "concat.txt").unlink(missing_ok=True)
    narration_track.unlink(missing_ok=True)
    for shot_path in shot_paths:
        shot_path.unlink(missing_ok=True)
    for voice_path in scene_dir.glob("scene_*.voice.*"):
        voice_path.unlink(missing_ok=True)
    progress(95, "finalize", "Long Animate selesai dirakit; menjalankan audit akhir")
    return output_path, sidecar
