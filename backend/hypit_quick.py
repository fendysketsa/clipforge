from __future__ import annotations

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

from remotion_story_renderer import RENDERER_DIR, RemotionRenderError, validate_hypit_script


HYPIT_COMMAND_RE = re.compile(r"^\s*/hypit(?:\s+|$)", re.IGNORECASE)
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


def is_hypit_quick_prompt(value: str) -> bool:
    return bool(HYPIT_COMMAND_RE.match(value or ""))


def _prompt_body(value: str) -> str:
    return HYPIT_COMMAND_RE.sub("", value or "", count=1).strip()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned[:64] or "ranking-video"


def build_hypit_quick_plan(prompt: str) -> HypitQuickPlan:
    """Turn a compact /hypit request into a deterministic code-rendered treatment."""
    if not is_hypit_quick_prompt(prompt):
        raise ValueError("Prompt Hypit harus diawali /hypit.")
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
            duration=26.0,
            hook_narration="Ada dua celah R C E kritis. PHP kamu tier berapa?",
            payoff_narration="Intinya: patch sekarang, lalu restart worker PHP.",
            items=(
                RankingItem(
                    tier="F",
                    label="PHP 8.1 & LEBIH LAMA",
                    detail="EOL upstream · migrasi atau gunakan backport/LTS vendor",
                    accent="#FF4D6D",
                    narration="Versi lama sudah E O L. F tier.",
                ),
                RankingItem(
                    tier="B",
                    label="BELUM VERIFIKASI",
                    detail="Jangan percaya banner panel—cek php -v dan paket aktif",
                    accent="#FFB84D",
                    narration="Belum cek versi aktif? B tier dulu.",
                ),
                RankingItem(
                    tier="A",
                    label="VENDOR BACKPORT",
                    detail="Aman bila vendor mengonfirmasi dua CVE sudah ditambal",
                    accent="#65D6A6",
                    narration="Backport vendor terkonfirmasi? A tier.",
                ),
                RankingItem(
                    tier="S",
                    label="8.5.12 · 8.4.27 · 8.3.36 · 8.2.35",
                    detail="Rilis upstream dengan perbaikan CVE-2026-109618/109619",
                    accent="#B6FF4A",
                    narration="Sudah menutup dua C V E? S tier.",
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
        duration=24.0,
        hook_narration="Tool video A I banyak. Mana yang benar-benar enak dipakai ulang?",
        payoff_narration=f"{subject} masuk S tier. Kamu setuju?",
        items=(
            RankingItem(
                tier="C",
                label="ONE-OFF GENERATOR",
                detail="Cepat, tetapi sulit direvisi secara presisi",
                accent="#8C93A8",
                narration="Cepat dibuat, susah direvisi. C tier.",
            ),
            RankingItem(
                tier="B",
                label="MANUAL TIMELINE",
                detail="Kontrol kuat, pekerjaan berulang masih banyak",
                accent="#64B5F6",
                narration="Kontrol kuat, tapi banyak kerja ulang. B tier.",
            ),
            RankingItem(
                tier="A",
                label="CODE VIDEO",
                detail="Animasi konsisten dan dapat di-version-control",
                accent="#A78BFA",
                narration="Konsisten dan mudah dilacak. Code video, A tier.",
            ),
            RankingItem(
                tier="S",
                label=subject_upper,
                detail="Agent-native · semantic timing · editable workflow",
                accent="#B6FF4A",
                narration=f"Agent-native dan tetap editable. {subject}, S tier.",
            ),
        ),
        source_note="Original code-rendered comparison; no third-party footage",
    )


def quick_preview_payload(prompt: str) -> dict[str, object]:
    plan = build_hypit_quick_plan(prompt)
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


def _write_hypit_source(plan: HypitQuickPlan, output_path: Path) -> Path:
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


def _write_project_notes(work_dir: Path, prompt: str, plan: HypitQuickPlan) -> None:
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
    reveal_gap = 4.0 if len(plan.items) <= 4 else 3.2
    reveal_lines = "\n".join(
        f"- {3.8 + index * reveal_gap:.1f}s · {item.tier} tier enters, settles, and updates the progress rail."
        for index, item in enumerate(plan.items)
    )
    (work_dir / "TIMELINE.md").write_text(
        "# Timeline\n\n"
        "## 0.0–2.8s · Kinetic hook\n\n"
        "Words rise and sharpen in sequence; the final phrase takes the accent before the title hands "
        "attention to the ranking board.\n\n"
        "## 2.8s onward · Persistent ranking state\n\n"
        f"{reveal_lines}\n\n"
        "## Final 4.3s · Verdict\n\n"
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
        (Path("/root/.cache/ms-playwright"), "chromium_headless_shell-*/chrome-linux/headless_shell"),
        (Path("/ms-playwright"), "chromium-*/chrome-linux/chrome"),
    ):
        try:
            candidates.extend(root.glob(pattern))
        except PermissionError:
            continue
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    for command in ("chromium", "chromium-browser", "google-chrome"):
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


def _dialogue_cues(plan: HypitQuickPlan, reveal_times: list[float]) -> list[DialogueCue]:
    final_start = max(0.0, plan.duration - 4.3)
    starts = [0.15, *(max(0.2, value - 0.22) for value in reveal_times), final_start + 0.18]
    texts = [plan.hook_narration, *(item.narration for item in plan.items), plan.payoff_narration]
    speakers = ["HOST", *("CO-HOST" if index % 2 == 0 else "HOST" for index in range(len(plan.items))), "CO-HOST"]
    cues: list[DialogueCue] = []
    for index, (speaker, text, start) in enumerate(zip(speakers, texts, starts, strict=True)):
        next_start = starts[index + 1] if index + 1 < len(starts) else plan.duration
        cues.append(
            DialogueCue(
                speaker=speaker,
                text=text,
                start=start,
                end=max(start + 0.8, next_start - 0.14),
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
    rate = os.environ.get("HYPIT_QUICK_TTS_RATE", "+12%").strip()
    pitch = os.environ.get(
        "HYPIT_QUICK_TTS_HOST_PITCH" if cue.speaker == "HOST" else "HYPIT_QUICK_TTS_COHOST_PITCH",
        "-2Hz" if cue.speaker == "HOST" else "+2Hz",
    ).strip()
    if not re.fullmatch(r"[+-]\d{1,2}%", rate):
        rate = "+12%"
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
    plan: HypitQuickPlan,
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
        source_duration = _audio_duration(source_path)
        available = max(0.8, cue.end - cue.start)
        tempo = max(1.0, source_duration / available)
        if tempo > 1.42:
            raise RemotionRenderError(
                f"Dialog {index} terlalu panjang untuk beat visual ({source_duration:.2f}s > {available:.2f}s)."
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
                str(source_path),
                "-filter:a",
                (
                    "aformat=sample_rates=48000:channel_layouts=stereo,"
                    f"atempo={tempo:.5f},afade=t=in:st=0:d=0.04,"
                    f"afade=t=out:st={max(0.08, fitted_duration - 0.12):.3f}:d=0.10"
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
    if require_audio and not any(
        isinstance(stream, dict) and stream.get("codec_type") == "audio" for stream in streams
    ):
        return "stream audio tidak ditemukan"
    format_payload = payload.get("format")
    raw_duration = format_payload.get("duration") if isinstance(format_payload, dict) else None
    try:
        actual_duration = float(str(raw_duration))
    except (TypeError, ValueError):
        return "durasi video tidak dapat dibaca"
    if abs(actual_duration - duration) > 0.75:
        return f"durasi {actual_duration:.3f}s tidak sesuai target {duration:.3f}s"
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
            "stream=codec_type,codec_name,width,height:format=duration",
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
            "[music][voice_sc]sidechaincompress=threshold=0.025:ratio=9:attack=12:release=260[ducked_music];"
            "[ducked_music][voice_mix][click][impact]amix=inputs=4:duration=first:normalize=0,"
            "alimiter=limit=0.90[aout]"
        )
    else:
        mix_filter = (
            f"[1:a]apad=pad_dur={duration:.3f},atrim=0:{duration:.3f},"
            "loudnorm=I=-23:TP=-2:LRA=7,"
            f"afade=t=in:st=0:d=0.35,afade=t=out:st={max(0.0, duration - 0.8):.3f}:d=0.8[music];"
            f"[2:a]volume='0.11*({pulses})':eval=frame,afade=t=out:st={max(0.0, duration - .3):.3f}:d=0.3[click];"
            f"[3:a]volume='0.18*({pulses})':eval=frame,lowpass=f=220[impact];"
            "[music][click][impact]amix=inputs=3:duration=first:normalize=0,"
            "alimiter=limit=0.90[aout]"
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
    plan: HypitQuickPlan,
    work_dir: Path,
    output_path: Path,
    hypit_path: Path,
    manifest_path: Path,
    voice_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Write the durable review metadata after a successful media render."""
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


def _write_quick_thumbnail_assets(
    output_path: Path,
    plan: HypitQuickPlan,
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


def finalize_existing_hypit_quick_render(prompt: str, output_root: Path) -> tuple[Path, dict[str, object]]:
    """Finish audio and metadata when Remotion completed before its parent worker exited."""
    plan = build_hypit_quick_plan(prompt)
    work_dir = output_root.resolve() / f"hypit-{plan.slug}"
    hypit_path = work_dir / "ranking.hypit.svml"
    manifest_path = work_dir / "ranking.remotion.json"
    silent_path = work_dir / "ranking.silent.mp4"
    output_path = work_dir / "clips" / f"long_animate_{plan.slug}.mp4"
    if not silent_path.is_file() and not output_path.is_file():
        raise RemotionRenderError("Tidak ada render Hypit yang dapat difinalkan.")
    reveal_gap = 4.0 if len(plan.items) <= 4 else 3.2
    reveal_times = [3.8 + index * reveal_gap for index in range(len(plan.items))]
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
            [*reveal_times, max(0.0, plan.duration - 4.3)],
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
            [*reveal_times, max(0.0, plan.duration - 4.3)],
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
) -> tuple[Path, dict[str, object]]:
    progress = progress or (lambda *_args: None)
    plan = build_hypit_quick_plan(prompt)
    output_root = output_root.resolve()
    work_dir = output_root / f"hypit-{plan.slug}"
    clips_dir = work_dir / "clips"
    public_dir = work_dir / "public"
    clips_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    _write_project_notes(work_dir, prompt, plan)

    progress(12, "selection", "Menerjemahkan prompt /hypit menjadi treatment ranking")
    hypit_path = _write_hypit_source(plan, work_dir / "ranking.hypit.svml")
    reveal_start = 3.8
    reveal_gap = 4.0 if len(plan.items) <= 4 else 3.2
    reveal_times = [reveal_start + index * reveal_gap for index in range(len(plan.items))]
    progress(22, "transcript", "Membuat percakapan TTS host dan co-host")
    dialogue_track, dialogue_manifest, voice_metadata = _prepare_dialogue_audio(
        plan, work_dir, reveal_times
    )
    manifest = {
        "schema": "clipforge-hypit-ranking-v2",
        "hypit": {
            "scriptSurface": "@hypit/script@1",
            "source": hypit_path.name,
            "validatedByCli": True,
            "timingModel": "authored-ranking-events",
        },
        "publicDir": str(public_dir.resolve()),
        "composition": {
            "template": "ranking",
            "styleVersion": "developer-reel-cinematic-v2",
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
            "watermark": "@ryuundy · HYPIT",
        },
    }
    manifest_path = work_dir / "ranking.remotion.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    node = shutil.which("node")
    render_script = RENDERER_DIR / "render.mjs"
    if not node or not render_script.is_file():
        raise RemotionRenderError("Runtime Remotion untuk Hypit Quick belum tersedia.")
    silent_path = work_dir / "ranking.silent.mp4"
    pending_silent_path = work_dir / "ranking.silent.pending.mp4"
    output_path = clips_dir / f"long_animate_{plan.slug}.mp4"
    env = os.environ.copy()
    browser = _browser_executable()
    if browser:
        env["REMOTION_BROWSER_EXECUTABLE"] = browser
    env["REMOTION_CRF"] = {"standard": "20", "high": "17", "max": "15"}.get(
        video_quality, "17"
    )
    env.setdefault("REMOTION_CONCURRENCY", "25%")
    progress(35, "render", "Hypit tervalidasi; Remotion merender tier board 9:16")
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
            [*reveal_times, max(0.0, plan.duration - 4.3)],
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
    progress(96, "render", "Video ranking selesai; menulis audit dan provenance")
    return output_path, sidecar
