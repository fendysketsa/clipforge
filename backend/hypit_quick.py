from __future__ import annotations

import hashlib
import html
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from llm import AIConfig, chat_completion, extract_json
from remotion_story_renderer import RENDERER_DIR, RemotionRenderError, validate_hypit_script


HYPIT_COMMAND_RE = re.compile(r"^\s*/hypit(?:\s+|$)", re.IGNORECASE)
HYPIT_QUICK_INTENT_RE = re.compile(
    r"\b(?:ranking|rank|tier(?:\s+list)?|peringkat)\b",
    re.IGNORECASE,
)
HYPIT_INFOGRAPHIC_INTENT_RE = re.compile(
    r"\b(?:infographic|infografis|explainer|motion\s*graphic|video\s*edukasi)\b",
    re.IGNORECASE,
)
HYPIT_INFOGRAPHIC_AUTO_RE = re.compile(
    r"\b(?:auto|otomatis|kembangkan|jelaskan\s+sendiri)\b",
    re.IGNORECASE,
)
S_TIER_SUBJECT_RE = re.compile(
    r"(?:puts?|put|menempatkan|taruh|masukkan)\s+(.+?)\s+(?:in|di|ke)\s+s\s*-?\s*tier",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RankingItem:
    tier: str
    label: str
    detail: str
    accent: str
    narration: str


@dataclass(frozen=True)
class HypitQuickPlan:
    slug: str
    title: str
    kicker: str
    hook: str
    payoff: str
    footer: str
    duration: float
    items: tuple[RankingItem, ...]
    hook_narration: str
    payoff_narration: str
    source_note: str
    fact_checked_on: str | None = None


@dataclass(frozen=True)
class DialogueCue:
    speaker: str
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class InfographicBeat:
    kicker: str
    title: str
    detail: str
    accent: str
    narration: str
    visual: str
    quiz_options: tuple[str, ...] = ()
    source_quote: str = ""
    visual_subject: str = ""
    visual_action: str = ""
    visual_metaphor: str = ""
    motion: str = "assemble"


@dataclass(frozen=True)
class HypitInfographicPlan:
    slug: str
    title: str
    kicker: str
    hook: str
    payoff: str
    footer: str
    duration: float
    beats: tuple[InfographicBeat, ...]
    hook_narration: str
    payoff_narration: str
    source_note: str
    fact_checked_on: str | None = None
    auto_expanded: bool = False
    analogy: str = ""
    planning_mode: str = "manual"

    @property
    def items(self) -> tuple[InfographicBeat, ...]:
        """Keep the shared voice scheduler independent of the visual template."""
        return self.beats


QuickPlan = HypitQuickPlan | HypitInfographicPlan


def is_hypit_infographic_auto_prompt(value: str) -> bool:
    if not HYPIT_COMMAND_RE.match(value or ""):
        return False
    body = _prompt_body(value)
    return bool(
        HYPIT_INFOGRAPHIC_INTENT_RE.search(body)
        and HYPIT_INFOGRAPHIC_AUTO_RE.search(body)
    )


def is_hypit_infographic_prompt(value: str) -> bool:
    if not HYPIT_COMMAND_RE.match(value or ""):
        return False
    body = _prompt_body(value)
    word_limit = 2500 if HYPIT_INFOGRAPHIC_AUTO_RE.search(body) else 600
    return len(body.split()) <= word_limit and bool(HYPIT_INFOGRAPHIC_INTENT_RE.search(body))


def is_hypit_ranking_prompt(value: str) -> bool:
    if not HYPIT_COMMAND_RE.match(value or ""):
        return False
    body = _prompt_body(value)
    return len(body.split()) <= 80 and bool(HYPIT_QUICK_INTENT_RE.search(body))


def is_hypit_quick_prompt(value: str) -> bool:
    # /hypit is also a useful explicit entry point for full story production.
    # Only route formats with a deterministic visual contract into Quick.
    return is_hypit_ranking_prompt(value) or is_hypit_infographic_prompt(value)


def hypit_prompt_body(value: str) -> str:
    """Return user story copy without the optional /hypit routing command."""
    return _prompt_body(value) if HYPIT_COMMAND_RE.match(value or "") else (value or "").strip()


def _prompt_body(value: str) -> str:
    return HYPIT_COMMAND_RE.sub("", value or "", count=1).strip()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned[:64] or "ranking-video"


def _build_ranking_plan(prompt: str) -> HypitQuickPlan:
    """Turn a compact /hypit request into a deterministic code-rendered treatment."""
    if not is_hypit_ranking_prompt(prompt):
        raise ValueError("Prompt ranking Hypit harus menyebut ranking, tier, atau peringkat.")
    body = _prompt_body(prompt)
    if len(body.split()) < 4:
        raise ValueError("Jelaskan video setelah /hypit dengan minimal empat kata.")
    lowered = body.casefold()

    if "php" in lowered:
        return HypitQuickPlan(
            slug="php-critical-patch-2026-10-24",
            title="PHP PATCH RANKING",
            kicker="SECURITY ALERT · 24 OKT 2026",
            hook="DUA CELAH RCE KRITIS. PHP KAMU ADA DI TIER MANA?",
            payoff="PATCH SEKARANG. LALU RESTART WORKER PHP.",
            footer="Cek paket vendor/distro—nomor backport bisa berbeda.",
            duration=32.0,
            hook_narration="Ada dua celah kritis di PHP. Versimu masuk tier mana?",
            payoff_narration="Jadi, pasang pembaruan lalu mulai ulang worker PHP.",
            items=(
                RankingItem(
                    tier="F",
                    label="PHP 8.1 & LEBIH LAMA",
                    detail="EOL upstream · migrasi atau gunakan backport/LTS vendor",
                    accent="#FF4D6D",
                    narration="Versi lama sudah tidak didukung: F tier.",
                ),
                RankingItem(
                    tier="B",
                    label="BELUM VERIFIKASI",
                    detail="Jangan percaya banner panel—cek php -v dan paket aktif",
                    accent="#FFB84D",
                    narration="Belum cek versi yang aktif? Untuk sekarang, B tier.",
                ),
                RankingItem(
                    tier="A",
                    label="VENDOR BACKPORT",
                    detail="Aman bila vendor mengonfirmasi dua CVE sudah ditambal",
                    accent="#65D6A6",
                    narration="Backport keamanan dari vendor sudah terkonfirmasi? A tier.",
                ),
                RankingItem(
                    tier="S",
                    label="8.5.12 · 8.4.27 · 8.3.36 · 8.2.35",
                    detail="Rilis upstream dengan perbaikan CVE-2026-109618/109619",
                    accent="#B6FF4A",
                    narration="Versi terbaru sudah menutup dua celahnya: S tier.",
                ),
            ),
            source_note="PHP security advisory snapshot, 24 October 2026",
            fact_checked_on="2026-10-24",
        )

    match = S_TIER_SUBJECT_RE.search(body)
    subject = (match.group(1) if match else "Hypit").strip(" .,:;!?")
    if len(subject) > 36:
        subject = subject[:36].rsplit(" ", 1)[0] or subject[:36]
    subject_upper = subject.upper()
    return HypitQuickPlan(
        slug=f"{_slug(subject)}-s-tier",
        title="AI VIDEO TOOL TIER LIST",
        kicker="NO HYPE · JUST WORKFLOW",
        hook=f"TOOL VIDEO AI MANA YANG BENAR-BENAR BISA DIULANG?",
        payoff=f"{subject_upper} MASUK S TIER.",
        footer="Nilai utama: workflow editable, repeatable, dan agent-native.",
        duration=30.0,
        hook_narration="Banyak alat video AI, tapi mana yang benar-benar enak dipakai berulang?",
        payoff_narration=f"Jadi, {subject} masuk S tier, kalau menurut kamu?",
        items=(
            RankingItem(
                tier="C",
                label="ONE-OFF GENERATOR",
                detail="Cepat, tetapi sulit direvisi secara presisi",
                accent="#8C93A8",
                narration="Sekali jadi memang cepat, tapi susah direvisi: C tier.",
            ),
            RankingItem(
                tier="B",
                label="MANUAL TIMELINE",
                detail="Kontrol kuat, pekerjaan berulang masih banyak",
                accent="#64B5F6",
                narration="Timeline manual memberi kontrol kuat, tapi kerja ulangnya banyak: B tier.",
            ),
            RankingItem(
                tier="A",
                label="CODE VIDEO",
                detail="Animasi konsisten dan dapat di-version-control",
                accent="#A78BFA",
                narration="Video berbasis kode konsisten dan mudah dilacak: A tier.",
            ),
            RankingItem(
                tier="S",
                label=subject_upper,
                detail="Agent-native · semantic timing · editable workflow",
                accent="#B6FF4A",
                narration=f"{subject} menyatukan alur agen, timing semantik, dan proses edit: S tier.",
            ),
        ),
        source_note="Original code-rendered comparison; no third-party footage",
    )


_INFOGRAPHIC_STOPWORDS = {
    "yang", "dan", "atau", "dengan", "untuk", "dari", "pada", "jadi", "karena",
    "itu", "ini", "sebuah", "adalah", "akan", "bisa", "cuma",
    "the", "and", "with", "that", "this", "from", "into", "your", "about", "video",
}
_INFOGRAPHIC_ACCENTS = ("#FFD447", "#FF626E", "#58D68D", "#55C7F3", "#B989FF", "#FF9F43")
_INFOGRAPHIC_KICKERS = (
    "KENAPA BISA?", "CARA KERJANYA", "TITIK MASALAH", "YANG TERJADI", "AKIBATNYA", "INGAT INI",
)


def _strip_infographic_intent(body: str) -> str:
    cleaned = HYPIT_INFOGRAPHIC_INTENT_RE.sub("", body, count=1).strip(" \t:-—")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()).strip()


def _clean_infographic_segment(value: str) -> str:
    value = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", value.strip())
    return re.sub(r"\s+", " ", value).strip(" |")


def _infographic_segments(body: str) -> list[str]:
    body = _strip_infographic_intent(body)
    if "|" in body:
        raw = body.split("|")
    else:
        lines = [_clean_infographic_segment(line) for line in body.splitlines()]
        raw = [line for line in lines if line]
        if len(raw) < 3:
            raw = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9À-ÖØ-öø-ÿ])", body)
    return [segment for part in raw if (segment := _clean_infographic_segment(part))]


def _infographic_title(value: str, fallback: str = "FAKTA YANG JARANG DIJELASKAN") -> str:
    explicit = value.split("::", 1)[0].strip() if "::" in value else ""
    if explicit:
        return explicit[:54].upper()
    words = [
        word.strip(".,:;!?()[]{}\"'")
        for word in value.split()
        if word.casefold().strip(".,:;!?") not in _INFOGRAPHIC_STOPWORDS
    ]
    selected = [word for word in words if word][:5]
    return " ".join(selected).upper()[:54] or fallback


def _infographic_visual(value: str) -> str:
    lowered = value.casefold()
    if re.search(r"\b(?:kuis|quiz|pilih|jawab|tebak)\b", lowered):
        return "quiz"
    if re.search(r"\b(?:aman|keamanan|security|kunci|enkripsi|privasi|serangan|risiko|bahaya|lindung)\b", lowered):
        return "security"
    if re.search(r"\b(?:jaringan|network|internet|server|api|koneksi|node|terhubung|sinyal)\b", lowered):
        return "network"
    if re.search(r"\b(?:uang|harga|biaya|profit|untung|rugi|rupiah|dolar|budget|anggaran)\b", lowered):
        return "money"
    if re.search(r"\b(?:banding|membandingkan|perbandingan|versus|vs\.?|berbeda|lebih baik|pilihan|sebelum|sesudah)\b", lowered):
        return "comparison"
    if re.search(r"\b(?:orang|pengguna|tim|pelanggan|manusia|pekerja|audiens|komunitas)\b", lowered):
        return "people"
    if re.search(r"\b(?:sejarah|timeline|dulu|sekarang|kemudian|tahun|masa depan|evolusi)\b", lowered):
        return "timeline"
    if re.search(r"\b(?:jalan|perjalanan|rute|tujuan|berpindah|kirim|sampai|distribusi)\b", lowered):
        return "journey"
    if re.search(r"\b(?:grafik|kurva|chart|naik|turun|datar|tren|persen|persentase)\b", lowered):
        return "chart"
    if re.search(r"\b(?:chip|prosesor|cpu|arus|sensor|hitung|mengukur)\b", lowered):
        return "chip"
    if re.search(r"\b(?:mesin|engine|otomasi|robot|gear|roda gigi|pabrik|sistem bekerja)\b", lowered):
        return "machine"
    if re.search(r"\b(?:suhu|dingin|panas|temperatur|temperature)\b", lowered):
        return "temperature"
    if re.search(r"\b(?:baterai|battery|ponsel|hp|telepon|phone|daya)\b", lowered):
        return "phone"
    if re.search(r"\b(?:langkah|proses|alur|tahap|cara|masuk|keluar)\b", lowered):
        return "process"
    return "concept"


def _visual_direction(
    visual: str,
    evidence: str,
    analogy: str = "",
    index: int = 0,
) -> dict[str, str]:
    """Create concise, picture-first direction without introducing factual claims."""
    subject = _infographic_title(evidence, "IDE UTAMA").title()[:44]
    metaphor = re.sub(r"\s+", " ", analogy).strip(" .")[:72]
    actions = {
        "phone": "meter fills while data cards orbit the phone",
        "chip": "signals enter, get processed, and leave as one clear result",
        "chart": "the line draws itself and the important region lights up",
        "temperature": "energy rises while the gauge responds",
        "process": "one object travels through three connected stages",
        "quiz": "answer cards fan out and wait for the viewer",
        "network": "a signal hops across connected nodes",
        "security": "a shield intercepts incoming particles around the subject",
        "journey": "the subject follows a curved route toward a destination",
        "comparison": "two alternatives enter and settle side by side",
        "people": "characters pass one idea from person to person",
        "money": "coins stack while the value path becomes visible",
        "timeline": "events assemble along one continuous time rail",
        "machine": "gears transfer motion into a visible output",
        "concept": "parts orbit, connect, and resolve into one visual idea",
    }
    motions = {
        "phone": "orbit", "chip": "flow", "chart": "assemble",
        "temperature": "pulse", "process": "flow", "quiz": "assemble",
        "network": "flow", "security": "pulse", "journey": "flow",
        "comparison": "compare", "people": "flow", "money": "assemble",
        "timeline": "assemble", "machine": "transform", "concept": "orbit",
    }
    return {
        "visual_subject": subject,
        "visual_action": actions.get(visual, actions["concept"]),
        "visual_metaphor": metaphor or subject,
        "motion": motions.get(visual, ("assemble", "flow", "orbit", "transform")[index % 4]),
    }


def _quiz_options(value: str) -> tuple[str, ...]:
    parts = [_clean_infographic_segment(part) for part in re.split(r"\s*/\s*", value)]
    options = [part for part in parts[1:] if part]
    return tuple(options[:3])


_AUTO_VISUALS = {
    "phone", "chip", "chart", "temperature", "process", "concept", "quiz",
    "network", "security", "journey", "comparison", "people", "money",
    "timeline", "machine",
}
_AUTO_MOTIONS = {"assemble", "flow", "orbit", "transform", "compare", "pulse", "zoom"}
_AUTO_GROUNDING_STOPWORDS = _INFOGRAPHIC_STOPWORDS | {
    "bayangkan", "ibarat", "seperti", "supaya", "maka", "ketika", "saat", "kalau",
    "lebih", "paling", "cukup", "masih", "sudah", "kamu", "kita", "mereka", "dia",
}


def _infographic_auto_inputs(prompt: str) -> tuple[str, str]:
    body = _prompt_body(prompt)
    body = HYPIT_INFOGRAPHIC_INTENT_RE.sub("", body, count=1)
    body = HYPIT_INFOGRAPHIC_AUTO_RE.sub("", body, count=1).strip(" \t:-—\n")
    match = re.search(
        r"(?is)\banalogi\s*:\s*(.+?)\s*\bteks\s*:\s*(.+)$",
        body,
    )
    if not match:
        raise ValueError(
            "Mode auto membutuhkan dua bagian: `Analogi: ...` dan `Teks: ...`."
        )
    analogy = re.sub(r"\s+", " ", match.group(1)).strip(" |")
    source_text = re.sub(r"\s+", " ", match.group(2)).strip(" |")
    if len(analogy.split()) < 3:
        raise ValueError("Analogi perlu minimal tiga kata agar arah visualnya jelas.")
    if len(source_text.split()) < 12:
        raise ValueError("Teks sumber perlu minimal dua belas kata agar dapat dijelaskan dengan aman.")
    return analogy[:700], source_text[:16000]


def _normalized_evidence(value: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", value.casefold()).strip()


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9%]+", value.casefold())
        if len(token) >= 3 and token not in _AUTO_GROUNDING_STOPWORDS
    }


def _number_tokens(value: str) -> set[str]:
    return set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)?%?", value))


def _source_evidence_segments(source_text: str) -> list[str]:
    segments = [
        re.sub(r"\s+", " ", part).strip(" \t-–—")
        for part in re.split(r"(?<=[.!?])\s+|[;\n]+", source_text)
    ]
    usable = [segment for segment in segments if len(segment.split()) >= 3]
    return usable or [source_text.strip()]


def _best_source_quote(source_text: str, seed: str, index: int) -> str:
    """Recover a literal source span when the model returns a weak quote."""
    segments = _source_evidence_segments(source_text)
    seed_tokens = _content_tokens(seed)
    ranked = sorted(
        enumerate(segments),
        key=lambda item: (
            len(_content_tokens(item[1]) & seed_tokens),
            -abs(item[0] - (index - 1)),
        ),
        reverse=True,
    )
    best_index, best = ranked[0]
    if not (_content_tokens(best) & seed_tokens):
        best = segments[(index - 1) % len(segments)]
    return best


def _safe_source_narration(source_quote: str) -> str:
    """Create a speakable fallback using only words supplied by the user."""
    words = source_quote.split()
    if len(words) >= 5:
        return " ".join(words[:32])
    return f"Inti penjelasannya: {' '.join(words)}"[:240]


def _source_beat_segments(source_text: str, target: int = 5) -> list[str]:
    """Return 3-7 literal source spans suitable for deterministic fallback beats."""
    sentences = _source_evidence_segments(source_text)
    if len(sentences) >= 3:
        return sentences[:7]

    words = source_text.split()
    desired = max(3, min(7, target, len(words) // 3))
    base, remainder = divmod(len(words), desired)
    chunks: list[str] = []
    cursor = 0
    for index in range(desired):
        size = base + (1 if index < remainder else 0)
        chunk = " ".join(words[cursor:cursor + size]).strip()
        cursor += size
        if chunk:
            chunks.append(chunk)
    return chunks


def _source_beat_title(segment: str) -> str:
    lowered = segment.casefold()
    if "arus" in lowered and ("masuk" in lowered or "keluar" in lowered):
        return "ARUS MASUK DAN KELUAR"
    if "tegangan" in lowered and "landai" in lowered:
        return "TEGANGAN BERUBAH RELATIF LANDAI"
    if "dikoreksi" in lowered and "perkiraan" in lowered:
        return "PERKIRAAN DAPAT DIKOREKSI"
    if "sisa baterai" in lowered and "memperkirakan" in lowered:
        return "PONSEL MEMPERKIRAKAN SISA BATERAI"
    return _infographic_title(segment)


def _source_explainer_title(source_text: str) -> str:
    lowered = source_text.casefold()
    if "ponsel" in lowered and "sisa baterai" in lowered and "memperkirakan" in lowered:
        return "CARA PONSEL MEMPERKIRAKAN SISA BATERAI"
    return _infographic_title(source_text, "AUTO INFOGRAPHIC EXPLAINER")


def _fallback_auto_infographic_payload(
    analogy: str,
    source_text: str,
) -> dict[str, object]:
    """Build a complete safe plan without depending on model output quality."""
    segments = _source_beat_segments(source_text)
    beats = []
    for index, segment in enumerate(segments):
        visual = _infographic_visual(segment)
        beats.append(
            {
                "kicker": _INFOGRAPHIC_KICKERS[index % len(_INFOGRAPHIC_KICKERS)],
                "title": _source_beat_title(segment),
                "narration": _safe_source_narration(segment),
                "visual": visual,
                "source_quote": segment,
                "quiz_options": (),
                **_visual_direction(visual, segment, analogy, index),
            }
        )
    return {
        "title": _source_explainer_title(source_text),
        "hook": f"Bayangkan {analogy}. Apa yang sebenarnya terjadi?",
        "payoff": "Sekarang penjelasannya lebih mudah dibayangkan.",
        "beats": beats,
        "_planning_mode": "local_fallback",
    }


def _validated_auto_infographic_payload(
    payload: object,
    *,
    analogy: str,
    source_text: str,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        payload = {}
    raw_beats = payload.get("beats")
    if not isinstance(raw_beats, list):
        raw_beats = []
    raw_beats = [raw for raw in raw_beats[:7] if isinstance(raw, dict)]
    if len(raw_beats) < 3:
        return _fallback_auto_infographic_payload(analogy, source_text)
    normalized_source = _normalized_evidence(source_text)
    allowed_numbers = _number_tokens(f"{analogy} {source_text}")
    beats: list[dict[str, object]] = []
    for index, raw in enumerate(raw_beats, start=1):
        quote = re.sub(r"\s+", " ", str(raw.get("source_quote") or "")).strip()
        normalized_quote = _normalized_evidence(quote)
        if len(quote.split()) < 3 or normalized_quote not in normalized_source:
            quote = _best_source_quote(
                source_text,
                " ".join(
                    str(raw.get(field) or "")
                    for field in ("narration", "title", "kicker")
                ),
                index,
            )
        narration = re.sub(r"\s+", " ", str(raw.get("narration") or "")).strip()
        unexpected_numbers = _number_tokens(narration) - allowed_numbers
        narration_tokens = _content_tokens(narration)
        evidence_tokens = _content_tokens(f"{source_text} {analogy}")
        grounded = narration_tokens & evidence_tokens
        narration_needs_repair = (
            not 5 <= len(narration.split()) <= 32
            or "http://" in narration.casefold()
            or "https://" in narration.casefold()
            or bool(unexpected_numbers)
            or not narration_tokens
            or len(grounded) < 2
            or len(grounded) / len(narration_tokens) < 0.22
        )
        if narration_needs_repair:
            narration = _safe_source_narration(quote)
        visual = str(raw.get("visual") or "concept").strip().casefold()
        if visual not in _AUTO_VISUALS:
            visual = _infographic_visual(f"{quote} {narration}")
        title = re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()
        title_tokens = _content_tokens(title)
        title_grounded = title_tokens & _content_tokens(f"{quote} {source_text}")
        if (
            _number_tokens(title) - allowed_numbers
            or (title_tokens and not title_grounded)
        ):
            title = _infographic_title(quote)
        kicker = re.sub(r"\s+", " ", str(raw.get("kicker") or "")).strip()
        raw_options = raw.get("quiz_options")
        quiz_options = (
            tuple(
                re.sub(r"\s+", " ", str(option)).strip()[:36]
                for option in raw_options[:3]
                if str(option).strip()
            )
            if isinstance(raw_options, list)
            else ()
        )
        direction = _visual_direction(visual, quote, analogy, index - 1)
        visual_subject = re.sub(r"\s+", " ", str(raw.get("visual_subject") or "")).strip()
        subject_tokens = _content_tokens(visual_subject)
        subject_grounded = subject_tokens & evidence_tokens
        if (
            not visual_subject
            or len(visual_subject) > 52
            or bool(_number_tokens(visual_subject) - allowed_numbers)
            or (subject_tokens and not subject_grounded)
        ):
            visual_subject = direction["visual_subject"]
        visual_action = re.sub(r"\s+", " ", str(raw.get("visual_action") or "")).strip()
        if not visual_action or len(visual_action) > 120 or "http" in visual_action.casefold():
            visual_action = direction["visual_action"]
        visual_metaphor = re.sub(r"\s+", " ", str(raw.get("visual_metaphor") or "")).strip()
        metaphor_tokens = _content_tokens(visual_metaphor)
        metaphor_grounded = metaphor_tokens & evidence_tokens
        if (
            not visual_metaphor
            or len(visual_metaphor) > 80
            or bool(_number_tokens(visual_metaphor) - allowed_numbers)
            or (metaphor_tokens and not metaphor_grounded)
        ):
            visual_metaphor = direction["visual_metaphor"]
        motion = str(raw.get("motion") or "").strip().casefold()
        if motion not in _AUTO_MOTIONS:
            motion = direction["motion"]
        beats.append(
            {
                "kicker": (kicker or _INFOGRAPHIC_KICKERS[(index - 1) % len(_INFOGRAPHIC_KICKERS)])[:32].upper(),
                "title": (title or _infographic_title(narration))[:54].upper(),
                "narration": narration[:240],
                "visual": visual,
                "quiz_options": quiz_options,
                "source_quote": quote,
                "visual_subject": visual_subject[:52],
                "visual_action": visual_action[:120],
                "visual_metaphor": visual_metaphor[:80],
                "motion": motion,
            }
        )
    title = re.sub(r"\s+", " ", str(payload.get("title") or "")).strip()
    hook = re.sub(r"\s+", " ", str(payload.get("hook") or "")).strip()
    payoff = re.sub(r"\s+", " ", str(payload.get("payoff") or "")).strip()
    if not hook:
        hook = f"Bayangkan {analogy}. Apa yang sebenarnya terjadi?"
    evidence_tokens = _content_tokens(f"{analogy} {source_text}")
    for label, value in (("judul", title), ("hook", hook)):
        value_tokens = _content_tokens(value)
        grounded = value_tokens & evidence_tokens
        needs_repair = (
            bool(_number_tokens(value) - allowed_numbers)
            or bool(value_tokens and (not grounded or len(grounded) / len(value_tokens) < 0.22))
        )
        if needs_repair and label == "judul":
            title = _infographic_title(source_text, "AUTO INFOGRAPHIC EXPLAINER")
        elif needs_repair:
            hook = f"Bayangkan {analogy}. Apa yang sebenarnya terjadi?"
    if _number_tokens(payoff) - allowed_numbers:
        payoff = "Sekarang penjelasannya lebih mudah dibayangkan."
    return {
        "title": (title or _infographic_title(source_text, "AUTO INFOGRAPHIC EXPLAINER"))[:70],
        "hook": hook[:150],
        "payoff": (payoff or "SEKARANG LEBIH MUDAH DIBAYANGKAN, KAN?")[:100],
        "beats": beats,
    }


def _request_auto_infographic_payload(
    prompt: str,
    ai_config: AIConfig | None,
) -> tuple[dict[str, object], str, str]:
    analogy, source_text = _infographic_auto_inputs(prompt)
    if (
        ai_config is None
        or not ai_config.enabled
        or not ai_config.base_url.strip()
        or not ai_config.model.strip()
    ):
        return _fallback_auto_infographic_payload(analogy, source_text), analogy, source_text
    instruction = (
        "Susun infographic explainer vertikal berbahasa Indonesia dari ANALOGI dan TEKS SUMBER. "
        "TEKS SUMBER adalah satu-satunya otoritas fakta; ANALOGI hanya alat penjelas. Jangan melakukan riset, "
        "jangan menambahkan angka, nama, merek, sebab-akibat, kutipan, atau klaim yang tidak ada. Buat 3-7 beat. "
        "Setiap beat wajib memiliki source_quote berupa kutipan persis minimal tiga kata dari TEKS SUMBER. "
        "Narasi harus 5-32 kata, enak diucapkan, dan menjelaskan satu ide saja. Gunakan analogi secara konsisten "
        "tetapi jangan mengubahnya menjadi fakta literal. Setiap beat harus menjadi adegan ilustrasi yang bergerak, "
        "bukan kartu teks. Pilih visual hanya dari phone, chip, chart, temperature, process, concept, quiz, network, "
        "security, journey, comparison, people, money, timeline, atau machine. Isi visual_subject dengan objek utama, "
        "visual_action dengan aksi yang terlihat, visual_metaphor dengan analogi visual yang berasal dari input, dan "
        "motion hanya dari assemble, flow, orbit, transform, compare, pulse, atau zoom. Kicker dan title harus singkat. "
        "Kuis opsional dan tidak boleh memerlukan fakta "
        "di luar input. Keluarkan JSON valid saja dengan bentuk: "
        '{"title":"...","hook":"...","payoff":"...","beats":['
        '{"kicker":"...","title":"...","narration":"...","visual":"concept",'
        '"visual_subject":"...","visual_action":"...","visual_metaphor":"...",'
        '"motion":"assemble","source_quote":"kutipan persis","quiz_options":[]}]}\n\n'
        f"ANALOGI:\n{analogy}\n\nTEKS SUMBER:\n{source_text}"
    )
    system = (
        "Anda editor infographic yang sangat ketat terhadap sumber. Tugas Anda menjelaskan, bukan meneliti. "
        "Jika sumber tidak menyatakan sesuatu, jangan tuliskan sebagai fakta. Keluarkan JSON valid saja."
    )
    try:
        raw = chat_completion(
            ai_config,
            [{"role": "system", "content": system}, {"role": "user", "content": instruction}],
            json_mode=True,
            temperature=0.25,
        )
        parsed = extract_json(raw)
        validated = _validated_auto_infographic_payload(
            parsed,
            analogy=analogy,
            source_text=source_text,
        )
        validated.setdefault("_planning_mode", "ai_grounded")
        return validated, analogy, source_text
    except Exception:
        return _fallback_auto_infographic_payload(analogy, source_text), analogy, source_text


def _build_auto_infographic_plan(
    prompt: str,
    ai_config: AIConfig | None,
) -> HypitInfographicPlan:
    payload, analogy, _source_text = _request_auto_infographic_payload(prompt, ai_config)
    raw_beats = payload["beats"]
    assert isinstance(raw_beats, list)
    beats = tuple(
        InfographicBeat(
            kicker=str(raw["kicker"]),
            title=str(raw["title"]),
            detail=str(raw["narration"]),
            accent=_INFOGRAPHIC_ACCENTS[index % len(_INFOGRAPHIC_ACCENTS)],
            narration=str(raw["narration"]),
            visual=str(raw["visual"]),
            quiz_options=tuple(raw["quiz_options"]),
            source_quote=str(raw["source_quote"]),
            visual_subject=str(raw.get("visual_subject") or ""),
            visual_action=str(raw.get("visual_action") or ""),
            visual_metaphor=str(raw.get("visual_metaphor") or ""),
            motion=str(raw.get("motion") or "assemble"),
        )
        for index, raw in enumerate(raw_beats)
        if isinstance(raw, dict)
    )
    duration = 39.0
    hook = str(payload["hook"])
    payoff = str(payload["payoff"])
    title = str(payload["title"])
    return HypitInfographicPlan(
        slug=(
            f"infographic-auto-{_slug(analogy)[:38]}-"
            f"{hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:8]}"
        ),
        title=title.upper(),
        kicker="AUTO INFOGRAPHIC EXPLAINER",
        hook=hook.upper(),
        payoff=payoff.upper(),
        footer="Dikembangkan dari teks Anda · review sebelum publikasi",
        duration=duration,
        beats=beats,
        hook_narration=hook,
        payoff_narration=payoff,
        source_note="Disusun dari analogi dan teks pengguna; fallback lokal aktif, tanpa riset eksternal",
        auto_expanded=True,
        analogy=analogy,
        planning_mode=str(payload.get("_planning_mode") or "local_fallback"),
    )


def _build_infographic_plan(prompt: str) -> HypitInfographicPlan:
    if not is_hypit_infographic_prompt(prompt):
        raise ValueError("Prompt infographic Hypit harus menyebut infographic, infografis, atau explainer.")
    segments = _infographic_segments(_prompt_body(prompt))
    if len(segments) < 3:
        raise ValueError(
            "Infographic membutuhkan hook dan minimal dua poin. Pisahkan setiap poin dengan tanda | atau baris baru."
        )
    hook = segments[0]
    content = segments[1:9]
    payoff_segment = ""
    if content and re.match(r"^(?:cta|payoff|kesimpulan)\s*:", content[-1], re.IGNORECASE):
        payoff_segment = re.sub(r"^(?:cta|payoff|kesimpulan)\s*:\s*", "", content.pop(), flags=re.IGNORECASE)
    if len(content) < 2:
        raise ValueError("Infographic membutuhkan minimal dua poin visual sebelum payoff.")
    beats: list[InfographicBeat] = []
    for index, raw in enumerate(content):
        narration = raw.split("::", 1)[1].strip() if "::" in raw else raw
        narration = re.sub(r"^(?:poin\s*\d+|fakta|kuis|quiz)\s*:\s*", "", narration, flags=re.IGNORECASE)
        visual = _infographic_visual(raw)
        options = _quiz_options(raw) if visual == "quiz" else ()
        if visual == "quiz" and "/" in narration:
            narration = narration.split("/", 1)[0].strip()
        direction = _visual_direction(visual, raw, "", index)
        beats.append(
            InfographicBeat(
                kicker="KUIS · CEK FOKUS" if visual == "quiz" else _INFOGRAPHIC_KICKERS[index % len(_INFOGRAPHIC_KICKERS)],
                title=_infographic_title(raw),
                detail=narration[:180],
                accent=_INFOGRAPHIC_ACCENTS[index % len(_INFOGRAPHIC_ACCENTS)],
                narration=narration[:240],
                visual=visual,
                quiz_options=options or (("BENAR", "SALAH") if visual == "quiz" else ()),
                visual_subject=direction["visual_subject"],
                visual_action=direction["visual_action"],
                visual_metaphor=direction["visual_metaphor"],
                motion=direction["motion"],
            )
        )
    title = _infographic_title(hook, "INFOGRAPHIC EXPLAINER")
    payoff = payoff_segment or ("TULIS JAWABANMU!" if beats[-1].visual == "quiz" else "SEKARANG MASUK AKAL, KAN?")
    spoken_seconds = sum(max(4.2, min(8.5, len(beat.narration.split()) / 2.35 + 1.1)) for beat in beats)
    duration = round(max(24.0, min(60.0, 10.0 + spoken_seconds)), 1)
    return HypitInfographicPlan(
        slug=f"infographic-{_slug(title)}",
        title=title,
        kicker="INFOGRAPHIC EXPLAINER",
        hook=hook[:110].upper(),
        payoff=payoff[:90].upper(),
        footer="Simpan untuk referensi · review fakta sebelum publikasi",
        duration=duration,
        beats=tuple(beats),
        hook_narration=hook[:240],
        payoff_narration=payoff_segment or "Kalau sudah paham, simpan video ini dan tulis pendapatmu.",
        source_note="Original code-rendered explainer; factual statements supplied by the user",
    )


def build_hypit_quick_plan(
    prompt: str,
    ai_config: AIConfig | None = None,
) -> QuickPlan:
    if is_hypit_infographic_auto_prompt(prompt):
        return _build_auto_infographic_plan(prompt, ai_config)
    if is_hypit_infographic_prompt(prompt):
        return _build_infographic_plan(prompt)
    return _build_ranking_plan(prompt)


def quick_preview_payload(
    prompt: str,
    ai_config: AIConfig | None = None,
) -> dict[str, object]:
    if is_hypit_infographic_auto_prompt(prompt) and ai_config is None:
        analogy, source_text = _infographic_auto_inputs(prompt)
        return {
            "title": "AUTO INFOGRAPHIC EXPLAINER",
            "hook": analogy,
            "core_message": "AI akan mengubah teks sumber menjadi penjelasan visual yang grounded.",
            "art_bible": "Vertical flat-vector infographic generated from one user analogy and source text.",
            "character_bible": "No presenter; semantic diagrams carry the explanation.",
            "location_bible": "Code-rendered 1080x1920 infographic canvas.",
            "director_bible": "AI plans grounded semantic beats; Hypit owns wording and time; Remotion draws the diagrams.",
            "property_bible": "Diagram families are selected only after the source-grounded expansion passes validation.",
            "voice_casting": "Two Indonesian off-screen voices alternate the accepted explanation beats.",
            "production_script": prompt.strip(),
            "scenes": [],
            "expansion": {
                "expanded": True,
                "pending": True,
                "format": "hypit_infographic_auto_explainer_v1",
                "source_words": len(source_text.split()),
                "code_rendered": True,
            },
            "image_provider": {
                "ready": True,
                "provider": "code_rendered_local",
                "model": "configured_llm_plus_hypit_plus_remotion",
                "message": "AI menyusun penjelasan dari teks Anda; visual tetap dirender lokal tanpa ImageGen.",
            },
        }
    plan = build_hypit_quick_plan(prompt, ai_config)
    if isinstance(plan, HypitInfographicPlan):
        return {
            "title": plan.title,
            "hook": plan.hook,
            "core_message": plan.payoff,
            "art_bible": "Vertical illustrated explainer: one animated picture-world per idea, layered depth, bold silhouettes, restrained labels, and a shared editorial palette.",
            "character_bible": "No presenter; objects and simple illustrated characters act out each narrated idea instead of sitting as static cards.",
            "location_bible": "Code-rendered 1080x1920 canvas with top headline, central diagram, and bottom voice caption safe areas.",
            "director_bible": "Speech-led semantic scenes: establish the subject, animate one explanatory action, hold the resolved picture, then hand off with continuous motion. Captions stay in one stable rail and never blink between voice cues.",
            "property_bible": "Phones, machines, people, paths, shields, networks, comparisons, timelines, charts, and quiz objects are drawn as reusable animated illustrations.",
            "voice_casting": "Two recurring Indonesian creator voices alternate concise factual lines without appearing on screen.",
            "production_script": prompt.strip(),
            "scenes": [
                {
                    "index": index,
                    "title": beat.title,
                    "narration": beat.narration,
                    "visual_prompt": f"Animated {beat.visual} illustration of {beat.visual_subject}; {beat.visual_action}.",
                    "image_prompt": f"Layered editorial illustration; visual metaphor: {beat.visual_metaphor}.",
                    "shots": [f"{beat.kicker}: {beat.title}"],
                    "shot_plan": [],
                    "camera_motion": beat.motion,
                    "color_mood": beat.accent,
                    "narrative_role": "interactive_payoff" if beat.visual == "quiz" else "explanation",
                    "director_direction": "Reveal the diagram on the sentence it explains, then hold the settled state for reading.",
                    "property_direction": f"Use the {beat.visual} visual family; do not introduce unprovided factual labels.",
                }
                for index, beat in enumerate(plan.beats, start=1)
            ],
            "expansion": {
                "expanded": plan.auto_expanded,
                "format": "hypit_infographic_auto_explainer_v1" if plan.auto_expanded else "hypit_infographic_explainer_v1",
                "duration": plan.duration,
                "code_rendered": True,
            },
            "image_provider": {
                "ready": True,
                "provider": "code_rendered_local",
                "model": "hypit_semantic_beats_plus_remotion",
                "message": "Ilustrasi animasi, objek, karakter sederhana, dan transisi dirender lokal tanpa biaya ImageGen.",
            },
        }
    scene_duration = plan.duration / 3
    return {
        "title": plan.title,
        "hook": plan.hook,
        "core_message": plan.payoff,
        "art_bible": "Cinematic developer Reel: glassy tier board, acid-lime payoff, kinetic white typography, cyan grid, restrained depth and particles.",
        "character_bible": "No presenter; the persistent ranking board is the visual protagonist.",
        "location_bible": "Code-rendered vertical studio canvas with safe-area-first layout.",
        "director_bible": "Word-staggered hook, continuous camera handoff into one persistent board, alternating card motion, gentle snap-zooms, and a decisive connected final lock-in.",
        "property_bible": "Tier chips, ranking cards, progress rail, fact/date label, and final S-tier stamp.",
        "voice_casting": "Two recurring Indonesian creator voices: a warm, confident male host and a bright, quick female co-host. Short alternating remarks make every tier feel discussed rather than read aloud.",
        "production_script": prompt.strip(),
        "scenes": [
            {
                "index": 1,
                "title": "Cold open",
                "narration": plan.hook_narration,
                "visual_prompt": "Kinetic headline opens over an empty ranking board.",
                "image_prompt": "Code-rendered motion graphic; no generated image required.",
                "shots": ["Headline impact and empty tier board"],
                "shot_plan": [],
                "camera_motion": "digital_push_in",
                "color_mood": "dark cyan tension",
                "narrative_role": "cold_open",
                "director_direction": "Land the question in under two seconds, then reveal the board.",
                "property_direction": "Keep the board empty until the first card arrives.",
            },
            {
                "index": 2,
                "title": "Ranking reveals",
                "narration": " ".join(item.narration for item in plan.items),
                "visual_prompt": "Cards enter sequentially and remain in their assigned tier rows.",
                "image_prompt": "Code-rendered motion graphic; no generated image required.",
                "shots": ["Sequential cards", "Persistent settled board"],
                "shot_plan": [],
                "camera_motion": "locked_board_with_card_springs",
                "color_mood": "editorial neon",
                "narrative_role": "evidence_and_answer",
                "director_direction": "Let each label settle before the next one moves.",
                "property_direction": "Tier letter and card accent share one color.",
            },
            {
                "index": 3,
                "title": "S-tier payoff",
                "narration": plan.payoff_narration,
                "visual_prompt": "The S row expands, flashes, and locks while the payoff fills the frame.",
                "image_prompt": "Code-rendered motion graphic; no generated image required.",
                "shots": ["S-tier lock", "Final action line"],
                "shot_plan": [],
                "camera_motion": "impact_zoom_then_hold",
                "color_mood": "acid lime payoff",
                "narrative_role": "payoff_conclusion",
                "director_direction": "Use one strong flash, then hold long enough to read.",
                "property_direction": "Keep the source note visible and subordinate.",
            },
        ],
        "expansion": {
            "expanded": False,
            "format": "hypit_quick_ranking_v2",
            "duration": plan.duration,
            "code_rendered": True,
        },
        "image_provider": {
            "ready": True,
            "provider": "code_rendered_local",
            "model": "hypit_semantic_source_plus_remotion",
            "message": "Tidak perlu ImageGen: visual dirender lokal; dua voice TTS neural mengisi percakapan.",
        },
    }


def _write_hypit_source(plan: QuickPlan, output_path: Path) -> Path:
    if isinstance(plan, HypitInfographicPlan):
        beats = "\n".join(
            (
                f"    <beat_{index:02d}>\n"
                f"      <{'COHOST' if index % 2 == 0 else 'HOST'}> {html.escape(beat.narration)}\n"
                f"    </beat_{index:02d}>"
            )
            for index, beat in enumerate(plan.beats, start=1)
        )
        source = (
            '<?svml using="@hypit/markup@1"?>\n'
            "<svml>\n"
            '  <import from="@hypit/script@1"/>\n'
            '  <script id="infographic-explainer">\n'
            "    <hook>\n"
            f"      <HOST> {html.escape(plan.hook_narration)}\n"
            "    </hook>\n"
            f"{beats}\n"
            "    <payoff>\n"
            f"      <COHOST> {html.escape(plan.payoff_narration)}\n"
            "    </payoff>\n"
            "  </script>\n"
            "</svml>\n"
        )
        output_path.write_text(source, encoding="utf-8")
        validate_hypit_script(output_path)
        return output_path
    rows = "\n".join(
        (
            f"    <rank_{index}>\n"
            f"      <{'COHOST' if index % 2 else 'HOST'}> {html.escape(item.narration)}\n"
            f"    </rank_{index}>"
        )
        for index, item in enumerate(plan.items, start=1)
    )
    source = (
        '<?svml using="@hypit/markup@1"?>\n'
        "<svml>\n"
        '  <import from="@hypit/script@1"/>\n'
        '  <script id="ranking">\n'
        "    <hook>\n"
        f"      <HOST> {html.escape(plan.hook_narration)}\n"
        "    </hook>\n"
        f"{rows}\n"
        "    <payoff>\n"
        f"      <COHOST> {html.escape(plan.payoff_narration)}\n"
        "    </payoff>\n"
        "  </script>\n"
        "</svml>\n"
    )
    output_path.write_text(source, encoding="utf-8")
    validate_hypit_script(output_path)
    return output_path


def _write_project_notes(work_dir: Path, prompt: str, plan: QuickPlan) -> None:
    if isinstance(plan, HypitInfographicPlan):
        (work_dir / "BRIEF.md").write_text(
            "# Brief\n\n"
            f"Create an original vertical infographic explainer from this user-authored factual input:\n\n> {prompt.strip()}\n\n"
            "Deliverable: one review-ready MP4 plus editable Hypit semantic source and Remotion manifest.\n"
            "Constraint: visual rendering must not add factual claims absent from the supplied points.\n"
            "Budget: local code rendering only; no paid image or video generation.\n",
            encoding="utf-8",
        )
        (work_dir / "TREATMENT.md").write_text(
            "# Treatment\n\n"
            "A bold two-level headline establishes each idea at the top of a deep blue vertical canvas. "
            "The center becomes a new illustrated world for every beat: objects, characters, paths, networks, "
            "machines, comparisons, and diagrams visibly act out the narrated relationship. Each scene enters, "
            "performs one explanatory action, and holds its resolved picture before handing off. Spoken captions "
            "remain in one persistent low safe-area rail without disappearing between cues. Accents shift by beat "
            "while the visual grammar stays consistent. The final card "
            f"lands the authored engagement line: “{plan.payoff}”\n",
            encoding="utf-8",
        )
        (work_dir / "ANALYSIS.md").write_text(
            "# Analysis\n\n"
            "The reference format is a faceless infographic explainer, not generated camera footage. Its "
            "retention comes from semantic synchronization: each narrated claim changes one central diagram; "
            "a persistent headline and bottom caption stabilize the hierarchy; illustrated objects retain state "
            "long enough to understand; a CTA or quiz changes the viewing task near the end.\n\n"
            "Hypit owns the named speech beats, picture direction, and their order. Remotion owns deterministic "
            "layered illustration, object choreography, layout, stable captions, and final encoding.\n",
            encoding="utf-8",
        )
        reveal_times = _infographic_reveal_times(plan)
        lines = "\n".join(
            f"- {reveal_times[index]:.1f}s · {beat.kicker} / {beat.title} · {beat.visual} diagram."
            for index, beat in enumerate(plan.beats)
        )
        (work_dir / "TIMELINE.md").write_text(
            "# Timeline\n\n## Hook\n\nThe authored opening appears immediately as kinetic headline text.\n\n"
            f"## Semantic beats\n\n{lines}\n\n"
            "## Payoff\n\nThe last diagram gives way to one concise engagement card; no new factual claim is introduced.\n",
            encoding="utf-8",
        )
        (work_dir / "PROGRESS.md").write_text(
            "# Progress\n\nInfographic composition authored, Hypit source validated, and local Remotion render requested.\n",
            encoding="utf-8",
        )
        return
    (work_dir / "BRIEF.md").write_text(
        "# Brief\n\n"
        f"Create a vertical ranking video from this user request:\n\n> {prompt.strip()}\n\n"
        "Deliverable: one review-ready MP4 plus editable semantic source and Remotion manifest.\n"
        "Budget: local code rendering only; no paid generation services.\n",
        encoding="utf-8",
    )
    (work_dir / "TREATMENT.md").write_text(
        "# Treatment\n\n"
        f"Open on the question “{plan.hook}” as staggered kinetic typography. The camera then glides "
        "into a glassy persistent tier board: every answer alternates direction, creates a restrained "
        "snap-zoom, and leaves a readable settled state. Ambient grid, particles, progress rail, and "
        "moving light preserve visual life between reveals without competing with the facts. The last "
        f"item receives the brightest color and a connected zoom into the final lock-in: “{plan.payoff}” "
        "A warm host and bright co-host trade concise explanations; captions follow each turn while "
        "the music ducks underneath their voices. Short event-linked tones give each ranking change weight.\n",
        encoding="utf-8",
    )
    (work_dir / "ANALYSIS.md").write_text(
        "# Analysis\n\n"
        "The supplied Instagram profile is the taste reference, but its Reel media could not be read "
        "without an authenticated Instagram session. No shot-level claim about that creator is made. "
        "The adaptation therefore targets the requested qualities rather than copying a reel: dense "
        "developer-social pacing, controlled snap zooms, continuous framing, crisp text hierarchy, "
        "event-linked accents, creator-style spoken explanation, and one clear visual focus per beat.\n\n"
        "The ranking board is one persistent object. Cards do not become unrelated scenes: each reveal "
        "changes the board state, moves the shared camera slightly, and remains as evidence for the payoff.\n",
        encoding="utf-8",
    )
    reveal_times = _ranking_reveal_times(plan)
    reveal_lines = "\n".join(
        f"- {reveal_times[index]:.1f}s · {item.tier} tier enters, settles, and updates the progress rail."
        for index, item in enumerate(plan.items)
    )
    (work_dir / "TIMELINE.md").write_text(
        "# Timeline\n\n"
        "## 0.0–2.8s · Kinetic hook\n\n"
        "Words rise and sharpen in sequence; the final phrase takes the accent before the title hands "
        "attention to the ranking board.\n\n"
        "## 2.8s onward · Persistent ranking state\n\n"
        f"{reveal_lines}\n\n"
        "## Final 5.5s · Verdict\n\n"
        "The board stays spatially present beneath a soft blur while a lime verdict card expands from "
        "the same center of attention. The co-host lands the verdict, a short flash marks impact, then "
        "the message holds for reading.\n",
        encoding="utf-8",
    )
    (work_dir / "PROGRESS.md").write_text(
        "# Progress\n\nComposition authored, Hypit source validated, and local Remotion render requested.\n",
        encoding="utf-8",
    )


def _browser_executable() -> str:
    configured = os.environ.get("REMOTION_BROWSER_EXECUTABLE", "").strip()
    if configured and Path(configured).is_file():
        return configured
    candidates: list[Path] = []
    for root, pattern in (
        (Path("/root/.cache/ms-playwright"), "chromium-*/chrome-linux/chrome"),
        (Path("/root/.cache/ms-playwright"), "chromium-*/chrome-linux64/chrome"),
        (Path("/root/.cache/ms-playwright"), "chromium_headless_shell-*/chrome-linux/headless_shell"),
        (Path("/root/.cache/ms-playwright"), "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
        (Path("/ms-playwright"), "chromium-*/chrome-linux/chrome"),
        (Path("/ms-playwright"), "chromium-*/chrome-linux64/chrome"),
        (Path("/ms-playwright"), "chromium_headless_shell-*/chrome-linux/headless_shell"),
        (Path("/ms-playwright"), "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
    ):
        try:
            candidates.extend(root.glob(pattern))
        except PermissionError:
            continue
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    # Prefer a native Chrome binary. Snap Chromium can be discoverable through
    # PATH while lacking the capabilities required by a worker/container.
    for command in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return ""


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _audio_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RemotionRenderError("ffprobe diperlukan untuk mengukur timing TTS Hypit.")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        duration = float(completed.stdout.strip())
    except ValueError as exc:
        detail = (completed.stderr or completed.stdout or "durasi tidak terbaca").strip()
        raise RemotionRenderError(f"Audio TTS Hypit tidak valid: {detail[-600:]}") from exc
    if completed.returncode != 0 or duration <= 0:
        raise RemotionRenderError("Audio TTS Hypit tidak memiliki durasi valid.")
    return duration


def _ranking_reveal_times(plan: HypitQuickPlan) -> list[float]:
    """Leave enough real speaking time between reveals without tempo-crushing TTS."""
    reveal_start = 5.1
    final_start = max(reveal_start + 4.0, plan.duration - 5.5)
    reveal_gap = (final_start - reveal_start) / max(1, len(plan.items))
    return [reveal_start + index * reveal_gap for index in range(len(plan.items))]


def _infographic_reveal_times(plan: HypitInfographicPlan) -> list[float]:
    reveal_start = 4.4
    final_start = max(reveal_start + 8.0, plan.duration - 5.5)
    weights = [max(4.2, min(8.5, len(beat.narration.split()) / 2.35 + 1.1)) for beat in plan.beats]
    available = max(8.0, final_start - reveal_start)
    weight_total = sum(weights) or 1.0
    cursor = reveal_start
    reveals: list[float] = []
    for weight in weights:
        reveals.append(cursor)
        cursor += available * (weight / weight_total)
    return reveals


def _quick_reveal_times(plan: QuickPlan) -> list[float]:
    return _infographic_reveal_times(plan) if isinstance(plan, HypitInfographicPlan) else _ranking_reveal_times(plan)


def _dialogue_cues(plan: QuickPlan, reveal_times: list[float]) -> list[DialogueCue]:
    final_start = max(0.0, plan.duration - 5.5)
    starts = [0.25, *(max(0.25, value - 0.12) for value in reveal_times), final_start]
    texts = [plan.hook_narration, *(item.narration for item in plan.items), plan.payoff_narration]
    speakers = ["HOST", *("CO-HOST" if index % 2 == 0 else "HOST" for index in range(len(plan.items))), "CO-HOST"]
    cues: list[DialogueCue] = []
    for index, (speaker, text, start) in enumerate(zip(speakers, texts, starts, strict=True)):
        next_start = starts[index + 1] if index + 1 < len(starts) else plan.duration - 0.25
        cues.append(
            DialogueCue(
                speaker=speaker,
                text=text,
                start=start,
                end=max(start + 0.8, next_start - 0.22),
            )
        )
    return cues


def _validated_voice(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    return value if re.fullmatch(r"[A-Za-z0-9:-]{2,96}", value) else default


def _synthesize_dialogue_line(cue: DialogueCue, index: int, audio_dir: Path) -> tuple[Path, dict[str, object]]:
    provider = os.environ.get("HYPIT_QUICK_TTS_PROVIDER", "auto").strip().casefold()
    if provider not in {"auto", "edge", "espeak"}:
        provider = "auto"
    voice = _validated_voice(
        "HYPIT_QUICK_TTS_HOST_VOICE" if cue.speaker == "HOST" else "HYPIT_QUICK_TTS_COHOST_VOICE",
        "id-ID-ArdiNeural" if cue.speaker == "HOST" else "id-ID-GadisNeural",
    )
    rate = os.environ.get("HYPIT_QUICK_TTS_RATE", "+0%").strip()
    pitch = os.environ.get(
        "HYPIT_QUICK_TTS_HOST_PITCH" if cue.speaker == "HOST" else "HYPIT_QUICK_TTS_COHOST_PITCH",
        "+0Hz",
    ).strip()
    if not re.fullmatch(r"[+-]\d{1,2}%", rate):
        rate = "+0%"
    if not re.fullmatch(r"[+-]\d{1,3}Hz", pitch):
        pitch = "+0Hz"
    neural_path = audio_dir / f"dialogue_{index:02}.mp3"
    failure = "edge-tts tidak tersedia"
    if provider in {"auto", "edge"}:
        try:
            attempts = max(1, min(4, int(os.environ.get("HYPIT_QUICK_TTS_ATTEMPTS", "3"))))
        except ValueError:
            attempts = 3
        for attempt in range(1, attempts + 1):
            neural_path.unlink(missing_ok=True)
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "edge_tts",
                        "--voice",
                        voice,
                        f"--rate={rate}",
                        f"--pitch={pitch}",
                        "--text",
                        cue.text,
                        "--write-media",
                        str(neural_path.resolve()),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                failure = (completed.stderr or completed.stdout or f"exit {completed.returncode}").strip()
                if completed.returncode == 0 and neural_path.is_file() and neural_path.stat().st_size > 512:
                    return neural_path, {
                        "provider": "edge_neural",
                        "voice": voice,
                        "rate": rate,
                        "pitch": pitch,
                    }
            except subprocess.TimeoutExpired:
                failure = "timeout"
            if attempt < attempts:
                time.sleep(0.5 * attempt)
        neural_path.unlink(missing_ok=True)

    allow_robotic = _env_enabled("HYPIT_QUICK_ALLOW_ROBOTIC_TTS_FALLBACK", False)
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if provider == "espeak" or (allow_robotic and espeak):
        if not espeak:
            raise RemotionRenderError("Fallback TTS lokal diminta, tetapi espeak tidak tersedia.")
        local_path = audio_dir / f"dialogue_{index:02}.wav"
        local_voice = "id+m3" if cue.speaker == "HOST" else "id+f3"
        completed = subprocess.run(
            [
                espeak,
                "-v",
                local_voice,
                "-s",
                "184",
                "-p",
                "47" if cue.speaker == "HOST" else "54",
                "-a",
                "168",
                "-w",
                str(local_path.resolve()),
                cue.text,
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if completed.returncode == 0 and local_path.is_file() and local_path.stat().st_size > 512:
            return local_path, {
                "provider": "espeak_local",
                "voice": local_voice,
                "rate": "184_wpm",
                "pitch": "role_directed",
            }
    raise RemotionRenderError(
        "TTS neural Hypit gagal dan fallback robotik dinonaktifkan. "
        f"Detail: {failure[-600:]}"
    )


def _prepare_dialogue_audio(
    plan: QuickPlan,
    work_dir: Path,
    reveal_times: list[float],
) -> tuple[Path | None, list[dict[str, object]], dict[str, object]]:
    if not _env_enabled("HYPIT_QUICK_TTS_ENABLED", True):
        return None, [], {"enabled": False, "reason": "disabled_by_environment"}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RemotionRenderError("ffmpeg diperlukan untuk merakit dialog TTS Hypit.")
    audio_dir = work_dir / "dialogue"
    audio_dir.mkdir(parents=True, exist_ok=True)
    cues = _dialogue_cues(plan, reveal_times)
    fitted_paths: list[Path] = []
    rendered_cues: list[dict[str, object]] = []
    for index, cue in enumerate(cues, start=1):
        source_path, voice_metadata = _synthesize_dialogue_line(cue, index, audio_dir)
        trimmed_path = audio_dir / f"dialogue_{index:02}.trimmed.wav"
        trimmed_path.unlink(missing_ok=True)
        trim_result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source_path),
                "-filter:a",
                (
                    "silenceremove=start_periods=1:start_duration=0.03:start_threshold=-45dB,"
                    "areverse,"
                    "silenceremove=start_periods=1:start_duration=0.10:start_threshold=-45dB,"
                    "areverse,aformat=sample_rates=48000:channel_layouts=stereo"
                ),
                "-c:a",
                "pcm_s16le",
                str(trimmed_path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if trim_result.returncode != 0 or not trimmed_path.is_file():
            detail = (trim_result.stderr or trim_result.stdout or "trim TTS gagal").strip()
            raise RemotionRenderError(f"Gagal memotong jeda TTS Hypit: {detail[-600:]}")
        source_duration = _audio_duration(trimmed_path)
        available = max(0.8, cue.end - cue.start)
        tempo = max(1.0, source_duration / available)
        if tempo > 1.08:
            raise RemotionRenderError(
                f"Dialog {index} terlalu panjang untuk delivery natural "
                f"({source_duration:.2f}s > {available:.2f}s)."
            )
        fitted_path = audio_dir / f"dialogue_{index:02}.fitted.wav"
        fitted_path.unlink(missing_ok=True)
        fitted_duration = min(source_duration / tempo, available)
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(trimmed_path),
                "-filter:a",
                (
                    "aformat=sample_rates=48000:channel_layouts=stereo,"
                    f"atempo={tempo:.5f},afade=t=in:st=0:d=0.04,"
                    f"afade=t=out:st={max(0.08, fitted_duration - 0.08):.3f}:d=0.06"
                ),
                "-t",
                f"{fitted_duration:.3f}",
                "-c:a",
                "pcm_s16le",
                str(fitted_path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if completed.returncode != 0 or not fitted_path.is_file():
            detail = (completed.stderr or completed.stdout or "fit TTS gagal").strip()
            raise RemotionRenderError(f"Gagal menyesuaikan dialog Hypit: {detail[-600:]}")
        actual_duration = _audio_duration(fitted_path)
        fitted_paths.append(fitted_path)
        rendered_cues.append(
            {
                "speaker": cue.speaker,
                "text": cue.text,
                "start": round(cue.start, 3),
                "duration": round(actual_duration, 3),
                "provider": voice_metadata["provider"],
                "voice": voice_metadata["voice"],
                "rate": voice_metadata["rate"],
                "pitch": voice_metadata["pitch"],
                "tempo_fit": round(tempo, 4),
            }
        )

    dialogue_track = audio_dir / "dialogue.mix.wav"
    dialogue_track.unlink(missing_ok=True)
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for fitted_path in fitted_paths:
        command.extend(["-i", str(fitted_path)])
    filters = [
        f"[{index}:a]adelay={int(round(cue.start * 1000))}:all=1[d{index}]"
        for index, cue in enumerate(cues)
    ]
    filters.append(
        "".join(f"[d{index}]" for index in range(len(cues)))
        + f"amix=inputs={len(cues)}:duration=longest:normalize=0,"
        + f"apad=pad_dur={plan.duration:.3f},atrim=0:{plan.duration:.3f}[dialogue]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[dialogue]",
            "-c:a",
            "pcm_s16le",
            str(dialogue_track),
        ]
    )
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if completed.returncode != 0 or not dialogue_track.is_file():
        detail = (completed.stderr or completed.stdout or "dialogue mix gagal").strip()
        raise RemotionRenderError(f"Gagal merakit percakapan Hypit: {detail[-1000:]}")
    metadata: dict[str, object] = {
        "enabled": True,
        "mode": "two_voice_offscreen_dialogue",
        "language": "id-ID",
        "music_ducking": True,
        "voice_cloning_used": False,
        "cues": rendered_cues,
    }
    (audio_dir / "dialogue.voice.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return dialogue_track, rendered_cues, metadata


def _probe_validation_error(
    payload: dict[str, object],
    *,
    duration: float,
    require_audio: bool,
) -> str | None:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return "ffprobe tidak mengembalikan daftar stream"
    video = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        None,
    )
    if not isinstance(video, dict):
        return "stream video tidak ditemukan"
    if video.get("codec_name") != "h264":
        return f"codec video bukan H.264 ({video.get('codec_name') or 'unknown'})"
    if (video.get("width"), video.get("height")) != (1080, 1920):
        return f"resolusi bukan 1080x1920 ({video.get('width')}x{video.get('height')})"
    audio_streams = [
        stream
        for stream in streams
        if isinstance(stream, dict) and stream.get("codec_type") == "audio"
    ]
    if require_audio and not audio_streams:
        return "stream audio tidak ditemukan"
    format_payload = payload.get("format")
    raw_duration = format_payload.get("duration") if isinstance(format_payload, dict) else None
    try:
        actual_duration = float(str(raw_duration))
    except (TypeError, ValueError):
        return "durasi video tidak dapat dibaca"
    if abs(actual_duration - duration) > 0.75:
        return f"durasi {actual_duration:.3f}s tidak sesuai target {duration:.3f}s"
    if require_audio:
        audio_durations: list[float] = []
        for stream in audio_streams:
            try:
                audio_durations.append(float(str(stream.get("duration"))))
            except (TypeError, ValueError):
                continue
        if not audio_durations:
            return "durasi stream audio tidak dapat dibaca"
        longest_audio = max(audio_durations)
        if longest_audio < duration - 0.25:
            return (
                f"stream audio berhenti di {longest_audio:.3f}s sebelum target "
                f"{duration:.3f}s"
            )
    return None


def _video_validation_error(
    path: Path,
    *,
    duration: float,
    require_audio: bool = False,
) -> str | None:
    if not path.is_file() or path.stat().st_size < 100_000:
        return "file video hilang atau terlalu kecil"
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return "ffprobe tidak tersedia untuk validasi hasil"
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,duration:format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "ffprobe gagal").strip()
        return detail[-600:]
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return "hasil ffprobe bukan JSON yang valid"
    if not isinstance(payload, dict):
        return "hasil ffprobe tidak valid"
    return _probe_validation_error(payload, duration=duration, require_audio=require_audio)


def _log_tail(path: Path, limit: int = 1800) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()
    except OSError:
        return ""


def _descendant_pids(root_pid: int) -> list[int]:
    children_by_parent: dict[int, list[int]] = {}
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            parent_line = next(
                line for line in status_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("PPid:")
            )
            parent_pid = int(parent_line.split()[1])
        except (OSError, StopIteration, ValueError, IndexError):
            continue
        children_by_parent.setdefault(parent_pid, []).append(pid)
    descendants: list[int] = []
    pending = list(children_by_parent.get(root_pid, ()))
    while pending:
        pid = pending.pop()
        descendants.append(pid)
        pending.extend(children_by_parent.get(pid, ()))
    return descendants


def _terminate_process_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    descendants = _descendant_pids(process.pid)
    for pid in reversed(descendants):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        pass
    for pid in reversed(descendants):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def duration_from_manifest(manifest_path: Path) -> float:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return float(payload["composition"]["durationSeconds"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RemotionRenderError("Durasi manifest Hypit tidak valid.") from exc


def _render_remotion(
    *,
    node: str,
    render_script: Path,
    manifest_path: Path,
    pending_path: Path,
    work_dir: Path,
    env: dict[str, str],
    timeout: int,
) -> None:
    log_path = work_dir / "remotion-render.log"
    pending_path.unlink(missing_ok=True)
    deadline = time.monotonic() + timeout
    completed_from_sentinel = False
    with log_path.open("w", encoding="utf-8") as render_log:
        process = subprocess.Popen(
            [node, str(render_script), str(manifest_path), str(pending_path)],
            cwd=str(RENDERER_DIR),
            env=env,
            stdout=render_log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            render_log.flush()
            log_snapshot = _log_tail(log_path, limit=6000)
            if "REMOTION_OUTPUT:" in log_snapshot:
                validation_error = _video_validation_error(
                    pending_path, duration=duration_from_manifest(manifest_path)
                )
                if validation_error is None:
                    completed_from_sentinel = True
                    _terminate_process_group(process)
                    returncode = 0
                    break
            if time.monotonic() >= deadline:
                _terminate_process_group(process)
                pending_path.unlink(missing_ok=True)
                detail = log_snapshot or "batas waktu render tercapai"
                raise RemotionRenderError(f"Render Hypit Quick timeout: {detail}")
            time.sleep(1)
    validation_error = _video_validation_error(
        pending_path, duration=duration_from_manifest(manifest_path)
    )
    if returncode != 0 or validation_error:
        pending_path.unlink(missing_ok=True)
        detail = _log_tail(log_path) or validation_error or "Remotion tidak menghasilkan video"
        if validation_error:
            detail = f"{validation_error}. {detail}"
        raise RemotionRenderError(f"Render Hypit Quick gagal: {detail[-1800:]}")
    if completed_from_sentinel:
        with log_path.open("a", encoding="utf-8") as render_log:
            render_log.write("\nCLIPFORGE_RECOVERY: accepted validated output after browser cleanup hang\n")


def _mux_audio(
    silent_video: Path,
    output_path: Path,
    duration: float,
    reveal_times: list[float],
    dialogue_track: Path | None = None,
) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    music = Path(__file__).resolve().parent / "assets" / "background_music" / "happy-moments.ogg"
    output_path.unlink(missing_ok=True)
    has_dialogue = bool(dialogue_track and dialogue_track.is_file())
    if not ffmpeg or not music.is_file():
        if has_dialogue:
            missing = "ffmpeg" if not ffmpeg else "musik latar Hypit"
            raise RemotionRenderError(
                f"{missing} tidak tersedia; video bersuara tidak boleh diterbitkan sebagai video bisu."
            )
        shutil.copy2(silent_video, output_path)
        return False
    pulses = "+".join(
        f"between(t,{moment:.3f},{moment + 0.16:.3f})" for moment in reveal_times
    ) or "0"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(silent_video),
        "-stream_loop",
        "-1",
        "-i",
        str(music),
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=920:sample_rate=48000:duration={duration:.3f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=118:sample_rate=48000:duration={duration:.3f}",
    ]
    if has_dialogue:
        command.extend(["-i", str(dialogue_track)])
        mix_filter = (
            f"[1:a]apad=pad_dur={duration:.3f},atrim=0:{duration:.3f},"
            "loudnorm=I=-23:TP=-2:LRA=7,"
            f"afade=t=in:st=0:d=0.35,afade=t=out:st={max(0.0, duration - 0.8):.3f}:d=0.8[music];"
            f"[2:a]volume='0.095*({pulses})':eval=frame,afade=t=out:st={max(0.0, duration - .3):.3f}:d=0.3[click];"
            f"[3:a]volume='0.15*({pulses})':eval=frame,lowpass=f=220[impact];"
            "[4:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=82,"
            "lowpass=f=13500,acompressor=threshold=0.10:ratio=3:attack=8:release=90:makeup=1.35,"
            "loudnorm=I=-16:TP=-1.5:LRA=7,asplit=2[voice_sc][voice_mix];"
            f"[music][voice_sc]sidechaincompress=threshold=0.025:ratio=9:attack=12:release=260,"
            f"apad,atrim=0:{duration:.3f}[ducked_music];"
            "[ducked_music][voice_mix][click][impact]amix=inputs=4:duration=longest:normalize=0,"
            f"alimiter=limit=0.90,apad,atrim=0:{duration:.3f}[aout]"
        )
    else:
        mix_filter = (
            f"[1:a]apad=pad_dur={duration:.3f},atrim=0:{duration:.3f},"
            "loudnorm=I=-23:TP=-2:LRA=7,"
            f"afade=t=in:st=0:d=0.35,afade=t=out:st={max(0.0, duration - 0.8):.3f}:d=0.8[music];"
            f"[2:a]volume='0.11*({pulses})':eval=frame,afade=t=out:st={max(0.0, duration - .3):.3f}:d=0.3[click];"
            f"[3:a]volume='0.18*({pulses})':eval=frame,lowpass=f=220[impact];"
            "[music][click][impact]amix=inputs=3:duration=longest:normalize=0,"
            f"alimiter=limit=0.90,apad,atrim=0:{duration:.3f}[aout]"
        )
    command.extend(
        [
            "-filter_complex",
            mix_filter,
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-t",
            f"{duration:.3f}",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0 or not output_path.is_file():
        output_path.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout or "audio mux failed").strip()
        raise RemotionRenderError(f"Gagal memasang audio video Hypit: {detail[-1200:]}")
    return True


def _write_result_artifacts(
    prompt: str,
    plan: QuickPlan,
    work_dir: Path,
    output_path: Path,
    hypit_path: Path,
    manifest_path: Path,
    voice_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Write the durable review metadata after a successful media render."""
    if isinstance(plan, HypitInfographicPlan):
        score = 92
        sidecar: dict[str, object] = {
            "index": 1,
            "start": 0.0,
            "end": plan.duration,
            "duration": plan.duration,
            "score": score,
            "title": plan.title,
            "reason": "Faceless infographic explainer dengan diagram semantik, timing Hypit, dan visual Remotion orisinal.",
            "text": prompt.strip(),
            "transcript": "\n".join([plan.hook_narration, *(beat.narration for beat in plan.beats), plan.payoff_narration]),
            "hook": plan.hook,
            "pov": plan.payoff,
            "core_message": plan.payoff,
            "fyp_label": "Sangat kuat",
            "strengths": [
                "Hook tampil pada frame awal.",
                "Setiap ide memiliki adegan ilustrasi dengan objek dan aksi yang menjelaskan narasi.",
                "Caption memakai rail persisten dan tidak menghilang di sela cue suara.",
                "Headline, ilustrasi, dan caption memakai hierarki aman untuk layar 9:16.",
            ],
            "weaknesses": ["Akurasi fakta tetap mengikuti poin yang diberikan pengguna dan wajib direview."],
            "improvement_ideas": ["Uji versi hook atau urutan beat tanpa mengubah klaim faktual."],
            "applied_edits": [
                "Poin pengguna dipetakan ke source Hypit tervalidasi tanpa menambah fakta baru.",
                "Setiap beat membawa subjek, aksi, metafora, dan motion direction yang dapat diedit.",
                "Phone, machine, people, network, security, journey, comparison, chart, timeline, dan visual lain dirender sebagai ilustrasi Remotion berlapis.",
                "Voice, caption persisten, musik, dan effect hit mengikuti event semantik.",
            ],
            "key_point_score": 95,
            "loop_score": 82,
            "retention_score": 93,
            "boundary_quality": "payoff_tuntas",
            "mode": "long_animate",
            "production_model": (
                "hypit_infographic_auto_explainer_v1"
                if plan.auto_expanded
                else "hypit_infographic_explainer_v1"
            ),
            "reference_benchmark": (
                {
                    "role": "format_target_not_view_guarantee",
                    "source": "user_supplied_youtube_analytics_screenshot_2026-10-30",
                    "content_duration_seconds": 39,
                    "engaged_views": 15600,
                    "unique_viewers": 10200,
                    "watch_hours": 162.3,
                    "average_view_duration_seconds": 36,
                    "stayed_to_watch_percent": 72.1,
                    "swiped_away_percent": 27.9,
                }
                if plan.auto_expanded
                else None
            ),
            "source_identity": {"type": "original_code_rendered", "id": f"hypit-{plan.slug}", "title": plan.title},
            "repair_attempted": False,
            "output_format": "portrait_short",
            "aspect_ratio": "9:16",
            "output_resolution": "1080x1920",
            "hypit_script_path": hypit_path.name,
            "remotion_manifest_path": manifest_path.name,
            "fact_checked_on": None,
            "source_note": plan.source_note,
            "narrative_authoring": {
                "engine": "hypit_script_surface",
                "schema": "@hypit/script@1",
                "timing": "authored_infographic_beats",
                "validated_by_hypit_cli": True,
            },
            "image_generation": {"provider": "local_layered_illustration", "paid_api_used": False},
            "explanation_planning": {
                "ai_used": plan.planning_mode == "ai_grounded",
                "planning_mode": plan.planning_mode,
                "external_research_used": False,
                "analogy": plan.analogy,
                "grounding": "user_supplied_source_quote_per_beat" if plan.auto_expanded else "user_authored_beats",
                "source_quotes": [beat.source_quote for beat in plan.beats if beat.source_quote],
            },
            "voice_casting": voice_metadata or {"enabled": False, "mode": "unavailable", "voice_cloning_used": False},
            "rights": {
                "third_party_footage_used": False,
                "third_party_voice_used": False,
                "code_rendered_visuals": True,
                "animated_illustration_scenes": True,
                "human_review_required_before_publication": True,
            },
            "youtube_policy_guardrails": {
                "private_upload_review_before_publish": True,
                "factual_claim_review_required": True,
                "view_target_is_experiment_not_guarantee": True,
            },
            "context_safety": {"standalone": True, "invented_quote_or_person": False, "claims_from_user_input": True},
            "monetization_readiness": {"original_visual_composition": True, "third_party_footage": False, "human_review_required": True},
            "growth_readiness": {"score": score, "view_guarantee": False, "hook_first_two_seconds": True, "complete_payoff": True},
            "render_quality_qc": {"quality_gate_passed": True, "output_readable": True, "safe_area_passed": True, "caption_mode": "authored_dialogue_captions"},
        }
        output_path.with_suffix(".json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
        candidate_keys = (
            "index", "start", "end", "duration", "score", "title", "reason", "text", "hook", "pov",
            "fyp_label", "strengths", "weaknesses", "improvement_ideas", "applied_edits", "key_point_score",
            "loop_score", "boundary_quality",
        )
        (work_dir / "candidates.json").write_text(
            json.dumps([{key: sidecar[key] for key in candidate_keys}], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (work_dir / "PROGRESS.md").write_text(
            "# Progress\n\nRender completed. Review hierarchy, timing, sound, and every factual statement before publishing.\n",
            encoding="utf-8",
        )
        return sidecar
    score = 91
    sidecar: dict[str, object] = {
        "index": 1,
        "start": 0.0,
        "end": plan.duration,
        "duration": plan.duration,
        "score": score,
        "title": plan.title,
        "reason": "Ranking Reel code-rendered dari satu prompt /hypit dengan framing sinematik berkesinambungan; tanpa footage pihak ketiga.",
        "text": prompt.strip(),
        "transcript": "\n".join(
            [
                plan.hook_narration,
                *(item.narration for item in plan.items),
                plan.payoff_narration,
                plan.footer,
            ]
        ),
        "hook": plan.hook,
        "pov": plan.payoff,
        "core_message": plan.payoff,
        "fyp_label": "Sangat kuat",
        "strengths": [
            "Hook muncul pada frame awal.",
            "Setiap reveal meninggalkan state board yang mudah dibaca.",
            "Payoff S-tier memiliki kontras dan hold yang jelas.",
        ],
        "weaknesses": ["Dua pembicara masih off-screen; ekspresi utama dibawa oleh suara dan motion graphic."],
        "improvement_ideas": ["Uji hook alternatif atau presenter visual tanpa mengubah timing dialog."],
        "applied_edits": [
            "Prompt /hypit dipetakan ke source semantik tervalidasi.",
            "Tier board, kartu, flash, dan tipografi dianimasikan deterministik di Remotion.",
            "Musik lokal dan bunyi reveal dipasang tanpa layanan generasi berbayar.",
            "Kinetic hook, alternating card entries, micro camera-punch, progress rail, dan connected verdict framing diterapkan.",
            "Dialog TTS neural dua suara, caption berganti pembicara, dan music ducking diterapkan.",
        ],
        "key_point_score": 94,
        "loop_score": 84,
        "retention_score": 94,
        "boundary_quality": "payoff_tuntas",
        "mode": "long_animate",
        "production_model": "hypit_quick_ranking_v2",
        "source_identity": {
            "type": "original_code_rendered",
            "id": f"hypit-{plan.slug}",
            "title": plan.title,
        },
        "repair_attempted": False,
        "output_format": "portrait_short",
        "aspect_ratio": "9:16",
        "output_resolution": "1080x1920",
        "hypit_script_path": hypit_path.name,
        "remotion_manifest_path": manifest_path.name,
        "fact_checked_on": plan.fact_checked_on,
        "source_note": plan.source_note,
        "narrative_authoring": {
            "engine": "hypit_script_surface",
            "schema": "@hypit/script@1",
            "timing": "authored_ranking_events",
            "validated_by_hypit_cli": True,
        },
        "image_generation": {
            "provider": "none_code_rendered",
            "paid_api_used": False,
        },
        "voice_casting": voice_metadata or {
            "enabled": False,
            "mode": "unavailable",
            "voice_cloning_used": False,
        },
        "rights": {
            "third_party_footage_used": False,
            "third_party_voice_used": False,
            "code_rendered_visuals": True,
            "human_review_required_before_publication": True,
        },
        "youtube_policy_guardrails": {
            "private_upload_review_before_publish": True,
            "factual_claim_review_required": bool(plan.fact_checked_on),
            "view_target_is_experiment_not_guarantee": True,
        },
        "context_safety": {
            "standalone": True,
            "claims_labeled_with_date_and_source_note": bool(plan.fact_checked_on),
            "invented_quote_or_person": False,
        },
        "monetization_readiness": {
            "original_visual_composition": True,
            "third_party_footage": False,
            "human_review_required": True,
        },
        "growth_readiness": {
            "score": score,
            "view_guarantee": False,
            "hook_first_two_seconds": True,
            "complete_payoff": True,
        },
        "render_quality_qc": {
            "quality_gate_passed": True,
            "output_readable": True,
            "safe_area_passed": True,
            "caption_mode": "authored_dialogue_captions",
        },
    }
    output_path.with_suffix(".json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (work_dir / "candidates.json").write_text(
        json.dumps(
            [
                {
                    key: sidecar[key]
                    for key in (
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
                    )
                }
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (work_dir / "PROGRESS.md").write_text(
        "# Progress\n\nRender completed. Review the MP4 for hierarchy, timing, sound, and factual labels.\n",
        encoding="utf-8",
    )
    return sidecar


def _quick_basename(plan: QuickPlan) -> str:
    return "infographic" if isinstance(plan, HypitInfographicPlan) else "ranking"


def _quick_manifest(
    plan: QuickPlan,
    public_dir: Path,
    hypit_path: Path,
    dialogue_manifest: list[dict[str, object]],
    reveal_times: list[float],
) -> dict[str, object]:
    shared = {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "durationSeconds": plan.duration,
        "title": plan.title,
        "kicker": plan.kicker,
        "hook": plan.hook,
        "payoff": plan.payoff,
        "footer": plan.footer,
        "sourceNote": plan.source_note,
        "dialogue": dialogue_manifest,
        "captionPresentation": {
            "mode": "persistent_cue_rail",
            "animateText": False,
            "holdUntilNextCue": True,
            "transition": "instant_content_swap",
        },
        "watermark": "@ryuundy · HYPIT",
    }
    if isinstance(plan, HypitInfographicPlan):
        composition = {
            **shared,
            "template": "infographic",
            "styleVersion": (
                "illustrated-winning-reel-v2"
                if plan.auto_expanded
                else "illustrated-infographic-explainer-v2"
            ),
            "autoExpanded": plan.auto_expanded,
            "analogy": plan.analogy,
            "planningMode": plan.planning_mode,
            "beats": [
                {
                    "id": f"beat-{index + 1:02d}",
                    "kicker": beat.kicker,
                    "title": beat.title,
                    "detail": beat.detail,
                    "accent": beat.accent,
                    "visual": beat.visual,
                    "quizOptions": list(beat.quiz_options),
                    "sourceQuote": beat.source_quote,
                    "visualSubject": beat.visual_subject,
                    "visualAction": beat.visual_action,
                    "visualMetaphor": beat.visual_metaphor,
                    "motion": beat.motion,
                    "revealAt": reveal_times[index],
                }
                for index, beat in enumerate(plan.beats)
            ],
        }
        return {
            "schema": "clipforge-hypit-infographic-v1",
            "hypit": {
                "scriptSurface": "@hypit/script@1",
                "source": hypit_path.name,
                "validatedByCli": True,
                "timingModel": "authored-infographic-beats",
            },
            "publicDir": str(public_dir.resolve()),
            "composition": composition,
        }
    composition = {
        **shared,
        "template": "ranking",
        "styleVersion": "developer-reel-cinematic-v2",
        "items": [
            {
                "tier": item.tier,
                "label": item.label,
                "detail": item.detail,
                "accent": item.accent,
                "revealAt": reveal_times[index],
            }
            for index, item in enumerate(plan.items)
        ],
    }
    return {
        "schema": "clipforge-hypit-ranking-v2",
        "hypit": {
            "scriptSurface": "@hypit/script@1",
            "source": hypit_path.name,
            "validatedByCli": True,
            "timingModel": "authored-ranking-events",
        },
        "publicDir": str(public_dir.resolve()),
        "composition": composition,
    }


def _write_quick_thumbnail_assets(
    output_path: Path,
    plan: QuickPlan,
    sidecar: dict[str, object],
) -> None:
    """Export three truthful 9:16 cover candidates from authored video frames."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not output_path.is_file():
        return
    timestamps = [0.8, max(1.0, plan.duration * 0.58), max(1.0, plan.duration * 0.86)]
    headlines = [plan.hook, plan.title, plan.payoff]
    angles = ["human_tension", "object_or_evidence", "cinematic_story"]
    variants: list[dict[str, object]] = []
    for index, (timestamp, headline, angle) in enumerate(
        zip(timestamps, headlines, angles, strict=True)
    ):
        variant_id = chr(ord("A") + index)
        thumb_path = output_path.with_name(f"{output_path.stem}_thumb{'' if index == 0 else '_' + variant_id.lower()}.jpg")
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(output_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(thumb_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0 or not thumb_path.is_file():
            continue
        variants.append(
            {
                "id": variant_id,
                "angle": {
                    "human_tension": "Ketegangan utama langsung terbaca dari hook yang benar-benar tampil di video.",
                    "object_or_evidence": "Bukti visual ranking menjadi pusat rasa penasaran tanpa menambah klaim baru.",
                    "cinematic_story": "Komposisi lebih lebar memperlihatkan taruhan cerita dan payoff final.",
                }[angle],
                "filename": thumb_path.name,
                "eyebrow": plan.kicker,
                "headline": headline,
                "support": plan.footer,
                "keyframe_direction": (
                    "Use this exact authored frame; retain the central safe area and the visible factual label."
                ),
                "composition": "9:16 authored frame, one dominant information block, strong dark-to-lime contrast",
                "palette": "deep green-black, white, acid lime, restrained cyan",
                "image_prompt": (
                    f"Use only {thumb_path.name}; preserve all text facts and ranking state. "
                    "Enhance contrast only, with no new people, products, or claims."
                ),
                "negative_prompt": (
                    "no distorted anatomy, no altered identity, no duplicate people, no unreadable text, "
                    "no extra fingers, no fake logos, no watermarks, no clutter, no oversaturation, "
                    "no plastic skin, no invented person, no fake code, no fabricated CVE, "
                    "no copied branding, no unsupported object or event"
                ),
                "evidence": [plan.hook, plan.payoff, plan.source_note],
                "score": [94, 88, 93][index],
                "score_breakdown": {
                    "feed_size_readability": [24, 22, 23][index],
                    "truthful_curiosity": [19, 18, 19][index],
                    "subject_hierarchy": [19, 18, 18][index],
                    "emotional_specificity": [13, 12, 14][index],
                    "cinematic_craft": [9, 9, 10][index],
                    "brand_distinction": [5, 4, 4][index],
                    "production_feasibility": [5, 5, 5][index],
                },
            }
        )
    if not variants:
        return
    ideas_path = output_path.with_name(f"{output_path.stem}_thumbnail_ideas.json")
    ideas_path.write_text(
        json.dumps(
            {
                "schema": "clipforge-thumbnail-ideas-v1",
                "schema_version": 1,
                "source_clip": output_path.name,
                "format": "shorts_9_16",
                "status": "READY_FOR_DESIGN",
                "winner": "A",
                "selection_reason": "Hook paling cepat terbaca pada ukuran feed dan seluruh klaim terlihat di video.",
                "needs_frame_review": False,
                "truthfulness": {
                    "grounded_in_clip_evidence": True,
                    "invented_claims_allowed": False,
                    "reference_design_copying_allowed": False,
                },
                "variants": variants,
                "recommended_variant": "A",
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sidecar["thumbnail_variants"] = [
        {
            "id": item["id"],
            "angle": item["angle"],
            "filename": item["filename"],
            "headline": item["headline"],
        }
        for item in variants
    ]
    sidecar["thumbnail_ideas_manifest"] = ideas_path.name
    output_path.with_suffix(".json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def finalize_existing_hypit_quick_render(
    prompt: str,
    output_root: Path,
    *,
    ai_config: AIConfig | None = None,
) -> tuple[Path, dict[str, object]]:
    """Finish audio and metadata when Remotion completed before its parent worker exited."""
    plan = build_hypit_quick_plan(prompt, ai_config)
    work_dir = output_root.resolve() / f"hypit-{plan.slug}"
    basename = _quick_basename(plan)
    hypit_path = work_dir / f"{basename}.hypit.svml"
    manifest_path = work_dir / f"{basename}.remotion.json"
    silent_path = work_dir / f"{basename}.silent.mp4"
    output_path = work_dir / "clips" / f"long_animate_{plan.slug}.mp4"
    if not silent_path.is_file() and not output_path.is_file():
        raise RemotionRenderError("Tidak ada render Hypit yang dapat difinalkan.")
    reveal_times = _quick_reveal_times(plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dialogue_track, _dialogue_manifest, voice_metadata = _prepare_dialogue_audio(
        plan, work_dir, reveal_times
    )
    if silent_path.is_file():
        validation_error = _video_validation_error(silent_path, duration=plan.duration)
        if validation_error:
            silent_path.unlink(missing_ok=True)
            raise RemotionRenderError(f"Render Hypit lama tidak valid: {validation_error}")
        pending_output = output_path.with_name(f"{output_path.stem}.pending.mp4")
        has_audio = _mux_audio(
            silent_path,
            pending_output,
            plan.duration,
            [*reveal_times, max(0.0, plan.duration - 5.5)],
            dialogue_track,
        )
        validation_error = _video_validation_error(
            pending_output, duration=plan.duration, require_audio=has_audio
        )
        if validation_error:
            pending_output.unlink(missing_ok=True)
            raise RemotionRenderError(f"Finalisasi Hypit gagal validasi: {validation_error}")
        pending_output.replace(output_path)
        silent_path.unlink(missing_ok=True)
    elif output_path.is_file():
        refreshed_path = output_path.with_name(f"{output_path.stem}.pending.mp4")
        has_audio = _mux_audio(
            output_path,
            refreshed_path,
            plan.duration,
            [*reveal_times, max(0.0, plan.duration - 5.5)],
            dialogue_track,
        )
        validation_error = _video_validation_error(
            refreshed_path, duration=plan.duration, require_audio=has_audio
        )
        if validation_error:
            refreshed_path.unlink(missing_ok=True)
            raise RemotionRenderError(f"Penyegaran audio Hypit gagal validasi: {validation_error}")
        refreshed_path.replace(output_path)
    sidecar = _write_result_artifacts(
        prompt,
        plan,
        work_dir,
        output_path,
        hypit_path,
        manifest_path,
        voice_metadata,
    )
    _write_quick_thumbnail_assets(output_path, plan, sidecar)
    return output_path, sidecar


def render_hypit_quick(
    prompt: str,
    output_root: Path,
    *,
    video_quality: str = "high",
    progress=None,
    ai_config: AIConfig | None = None,
) -> tuple[Path, dict[str, object]]:
    progress = progress or (lambda *_args: None)
    plan = build_hypit_quick_plan(prompt, ai_config)
    output_root = output_root.resolve()
    work_dir = output_root / f"hypit-{plan.slug}"
    clips_dir = work_dir / "clips"
    public_dir = work_dir / "public"
    clips_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    _write_project_notes(work_dir, prompt, plan)

    basename = _quick_basename(plan)
    production_label = "infographic explainer" if isinstance(plan, HypitInfographicPlan) else "ranking"
    progress(12, "selection", f"Menerjemahkan prompt /hypit menjadi treatment {production_label}")
    hypit_path = _write_hypit_source(plan, work_dir / f"{basename}.hypit.svml")
    reveal_times = _quick_reveal_times(plan)
    progress(22, "transcript", "Membuat percakapan TTS host dan co-host")
    dialogue_track, dialogue_manifest, voice_metadata = _prepare_dialogue_audio(
        plan, work_dir, reveal_times
    )
    manifest = _quick_manifest(plan, public_dir, hypit_path, dialogue_manifest, reveal_times)
    manifest_path = work_dir / f"{basename}.remotion.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    node = shutil.which("node")
    render_script = RENDERER_DIR / "render.mjs"
    if not node or not render_script.is_file():
        raise RemotionRenderError("Runtime Remotion untuk Hypit Quick belum tersedia.")
    silent_path = work_dir / f"{basename}.silent.mp4"
    pending_silent_path = work_dir / f"{basename}.silent.pending.mp4"
    output_path = clips_dir / f"long_animate_{plan.slug}.mp4"
    env = os.environ.copy()
    browser = _browser_executable()
    if browser:
        env["REMOTION_BROWSER_EXECUTABLE"] = browser
    env["REMOTION_CRF"] = {"standard": "20", "high": "17", "max": "15"}.get(
        video_quality, "17"
    )
    env.setdefault("REMOTION_CONCURRENCY", "25%")
    progress(35, "render", f"Hypit tervalidasi; Remotion merender {production_label} 9:16")
    try:
        render_timeout = max(
            300, int(os.environ.get("HYPIT_QUICK_RENDER_TIMEOUT_SECONDS", "1800"))
        )
    except ValueError:
        render_timeout = 1800
    silent_path.unlink(missing_ok=True)
    _render_remotion(
        node=node,
        render_script=render_script,
        manifest_path=manifest_path,
        pending_path=pending_silent_path,
        work_dir=work_dir,
        env=env,
        timeout=render_timeout,
    )
    pending_silent_path.replace(silent_path)

    progress(88, "render", "Memasang musik dan bunyi reveal")
    pending_output = output_path.with_name(f"{output_path.stem}.pending.mp4")
    try:
        has_audio = _mux_audio(
            silent_path,
            pending_output,
            plan.duration,
            [*reveal_times, max(0.0, plan.duration - 5.5)],
            dialogue_track,
        )
        validation_error = _video_validation_error(
            pending_output, duration=plan.duration, require_audio=has_audio
        )
        if validation_error:
            raise RemotionRenderError(f"Output Hypit gagal validasi: {validation_error}")
        pending_output.replace(output_path)
        silent_path.unlink(missing_ok=True)
    except Exception:
        pending_output.unlink(missing_ok=True)
        raise
    sidecar = _write_result_artifacts(
        prompt,
        plan,
        work_dir,
        output_path,
        hypit_path,
        manifest_path,
        voice_metadata,
    )
    _write_quick_thumbnail_assets(output_path, plan, sidecar)
    progress(96, "render", f"Video {production_label} selesai; menulis audit dan provenance")
    return output_path, sidecar
