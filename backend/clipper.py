from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

import imageio_ffmpeg
from rich.console import Console
from rich.table import Table
from slugify import slugify
from yt_dlp import YoutubeDL

from llm import AIConfig, chat_completion, extract_json, is_llm_unavailable_error


console = Console()
_AI_UNAVAILABLE_NOTICE_PRINTED = False


def emit_progress(percent: int, stage: str, detail: str) -> None:
    """Emit a machine-readable milestone consumed by the API progress tracker."""
    clean_detail = re.sub(r"[\r\n|]+", " ", detail).strip()
    console.print(
        f"FENDY_CLIPPER_PROGRESS:{max(0, min(100, int(percent)))}|{stage}|{clean_detail}",
        markup=False,
    )


def disable_unavailable_ai(config: AIConfig, exc: BaseException) -> bool:
    """Open the circuit once so one offline provider does not spam every generated asset."""
    global _AI_UNAVAILABLE_NOTICE_PRINTED
    if not is_llm_unavailable_error(exc):
        return False
    config.enabled = False
    if not _AI_UNAVAILABLE_NOTICE_PRINTED:
        console.print(
            "[yellow]AI service tidak tersedia; job dilanjutkan dengan scoring, "
            "thumbnail prompt, dan caption fallback lokal.[/yellow]"
        )
        _AI_UNAVAILABLE_NOTICE_PRINTED = True
    return True


class UserFacingError(RuntimeError):
    """Error message that is safe and useful to show in the UI."""


NETWORK_ERROR_PATTERNS = (
    "errno 101",
    "network is unreachable",
    "no route to host",
    "temporary failure in name resolution",
    "name or service not known",
    "failed to resolve",
    "connection timed out",
    "timed out",
    "connection refused",
    "cannot assign requested address",
)

YTDLP_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class ClipCandidate:
    index: int
    start: float
    end: float
    duration: float
    score: int
    title: str
    reason: str
    text: str
    hook: str = ""
    pov: str = ""
    fyp_label: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvement_ideas: list[str] = field(default_factory=list)
    applied_edits: list[str] = field(default_factory=list)
    key_point_score: int = 0
    loop_score: int = 0
    boundary_quality: str = ""


@dataclass
class CodexEditPlan:
    """Concrete export treatments derived from the clip analysis."""

    hook_boost: bool = False
    tempo_boost: bool = False
    ending_boost: bool = False
    loop_boost: bool = False


CameraAngleKind = Literal["medium", "close_left", "close_center", "close_right"]


@dataclass
class CameraAngleCue:
    """A transcript-timed virtual camera cut made from the same source shot."""

    kind: CameraAngleKind
    start: float
    end: float
    zoom_pixels: int
    x_offset: int
    y_offset: int
    trigger: str


ReactionKind = Literal["laugh", "shock", "think", "pray", "warning", "heart", "important"]


@dataclass
class ReactionCue:
    kind: ReactionKind
    start: float
    end: float
    side: Literal["left", "right"]
    trigger: str


SoundEffectKind = Literal[
    "laugh",
    "shock",
    "think",
    "pray",
    "warning",
    "heart",
    "important",
    "emphasis",
    "loop",
]


@dataclass
class SoundEffectCue:
    kind: SoundEffectKind
    start: float
    duration: float
    frequency: int
    volume: float
    trigger: str


@dataclass
class BackdropProfile:
    dominant_lab: tuple[float, float, float]
    color_threshold: float
    confidence: float
    dominant_ratio: float
    aligned_component_count: int


@dataclass
class EmbeddedSplitProfile:
    """Persistent source layout with a speaker panel above a text/media banner."""

    boundary_ratio: float
    confidence: float
    lower_text_component_count: int
    source_width: int
    source_height: int


@dataclass
class WatermarkRegion:
    """A persistent source overlay detected across several rendered frames."""

    x: int
    y: int
    width: int
    height: int
    source_width: int
    source_height: int
    confidence: float
    persistence: float


HOOK_WORDS = {
    "intinya",
    "ternyata",
    "masalahnya",
    "kenapa",
    "gimana",
    "bagaimana",
    "cara",
    "jangan",
    "harus",
    "penting",
    "rahasia",
    "bedanya",
    "salah",
    "benar",
    "tips",
    "trik",
    "jadi",
    "kalau",
    "misalnya",
    "fakta",
    "viral",
    "aneh",
    "gila",
    "wow",
    "kok",
    "bongkar",
    "bukti",
    "mungkin",
    "sebenarnya",
    "bayangin",
    "percuma",
    "wajib",
}

WEAK_STARTS = {
    "dan",
    "terus",
    "lalu",
    "nah",
    "jadi",
    "itu",
    "ini",
    "em",
    "eh",
    "ya",
}

PAYOFF_WORDS = {
    "hasilnya",
    "akhirnya",
    "solusinya",
    "jawabannya",
    "buktinya",
    "makanya",
    "itulah",
    "terbukti",
    "berubah",
    "berhasil",
    "gagal",
}

TENSION_WORDS = {
    "tapi",
    "namun",
    "padahal",
    "ternyata",
    "masalah",
    "risiko",
    "bahaya",
    "salah",
    "jangan",
    "bukan",
    "beda",
    "versus",
    "vs",
}

MYSTERY_WORDS = {
    "angker",
    "arwah",
    "gaib",
    "genderuwo",
    "hantu",
    "horor",
    "jin",
    "kerasukan",
    "kematian",
    "kuntilanak",
    "kubur",
    "leak",
    "mencekam",
    "merinding",
    "mistis",
    "misteri",
    "mitos",
    "paranormal",
    "penampakan",
    "pesugihan",
    "pocong",
    "ruqyah",
    "santet",
    "seram",
    "setan",
    "siluman",
    "supranatural",
    "teror",
    "tumbal",
    "urban",
}

ISLAMIC_WORDS = {
    "akhirat",
    "akhlak",
    "alhamdulillah",
    "allah",
    "alquran",
    "bismillah",
    "dakwah",
    "doa",
    "dosa",
    "dzikir",
    "hadis",
    "hadits",
    "haji",
    "halal",
    "haram",
    "hijrah",
    "hikmah",
    "ibadah",
    "iman",
    "insyaallah",
    "islam",
    "islami",
    "kajian",
    "kiai",
    "kyai",
    "masjid",
    "muhammad",
    "muslim",
    "muslimah",
    "nabi",
    "neraka",
    "pahala",
    "puasa",
    "quran",
    "qur'an",
    "ramadan",
    "ramadhan",
    "rasul",
    "rasulullah",
    "salat",
    "salawat",
    "sedekah",
    "shalat",
    "sholawat",
    "sholat",
    "subhanallah",
    "sunnah",
    "surga",
    "syariah",
    "syariat",
    "taubat",
    "ulama",
    "umrah",
    "ustad",
    "ustaz",
    "ustazah",
    "ustadz",
    "ustadzah",
    "zakat",
    "zikir",
}

ISLAMIC_BACKGROUND_MUSIC_TITLE = "Cahaya Hikmah (Fendy Clipper Original)"
ISLAMIC_BACKGROUND_MUSIC_LICENSE = "CC0-1.0"

INSPIRING_WORDS = {
    "bangkit",
    "bahagia",
    "berkah",
    "harapan",
    "inspirasi",
    "ikhlas",
    "memaafkan",
    "motivasi",
    "sabar",
    "semangat",
    "sukses",
    "syukur",
}

LAUGH_WORDS = {
    "becanda",
    "bercanda",
    "gokil",
    "jokes",
    "kocak",
    "ketawa",
    "lawak",
    "lucu",
    "ngakak",
}

SHOCK_WORDS = {
    "astaga",
    "gila",
    "horor",
    "kaget",
    "mencekam",
    "merinding",
    "mengejutkan",
    "parah",
    "serius",
    "seram",
    "teror",
    "ternyata",
    "wow",
}

PRAYER_WORDS = {
    "aamiin",
    "alhamdulillah",
    "allah",
    "amin",
    "berkah",
    "doa",
    "insyaallah",
    "masyaallah",
    "subhanallah",
    "syukur",
}

WARNING_WORDS = {
    "awas",
    "bahaya",
    "dilarang",
    "jangan",
    "risiko",
    "waspada",
}

HEART_WORDS = {
    "ayah",
    "bahagia",
    "cinta",
    "haru",
    "ibu",
    "ikhlas",
    "keluarga",
    "maaf",
    "sabar",
    "sayang",
    "sedih",
    "terharu",
}

IMPORTANT_WORDS = {
    "faktanya",
    "ingat",
    "inti",
    "intinya",
    "kunci",
    "kesimpulannya",
    "penting",
    "rahasia",
    "solusinya",
    "wajib",
}

LOOP_STOP_WORDS = {
    "ada",
    "adalah",
    "akan",
    "aku",
    "atau",
    "dan",
    "dari",
    "di",
    "dia",
    "dengan",
    "ini",
    "itu",
    "jadi",
    "juga",
    "kami",
    "karena",
    "ke",
    "kita",
    "mereka",
    "pada",
    "saya",
    "sebuah",
    "sudah",
    "tapi",
    "tidak",
    "untuk",
    "yang",
}

FILLER_PHRASES = (
    "seperti yang sudah dijelaskan",
    "kita akan membahas",
    "sebelum kita mulai",
    "pada kesempatan kali ini",
    "kurang lebih seperti itu",
    "dan lain sebagainya",
)

CropMode = Literal["center", "person", "streamer"]
VideoQuality = Literal["standard", "high", "max"]
ClipMode = Literal["short", "highlight_5m"]
OutputFormat = Literal["vertical_short", "landscape_compilation"]
VisualMode = Literal["auto_fyp", "cinematic", "speaker_split", "animated_3d", "retro_tv"]
BackgroundMode = Literal["auto_clean", "keep", "mosque"]
VisualTheme = Literal["mystery", "islamic", "warning", "inspiring", "knowledge"]
DEFAULT_TRANSCRIPTION_MODEL = "Systran/faster-whisper-medium"
TRANSCRIPTION_CACHE_VERSION = 2
YUNET_MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
MOSQUE_BACKGROUND_PATH = (
    Path(__file__).resolve().parent / "assets" / "backgrounds" / "grand_mosque_neutral.png"
)
MOSQUE_CONGREGATION_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "backgrounds"
    / "mosque-congregation-v1.png"
)
SOURCE_VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}

VIDEO_QUALITY_PRESETS = {
    "standard": {
        "label": "standard",
        "crf": "20",
        "preset": "veryfast",
        "profile": "high",
        "level": "4.2",
        "audio_bitrate": "160k",
        "max_download_height": 1080,
        "sharpen": "",
        "cas_strength": "",
    },
    "high": {
        "label": "high quality",
        "crf": "16",
        "preset": "medium",
        "profile": "high",
        "level": "4.2",
        "audio_bitrate": "192k",
        "max_download_height": 2160,
        "sharpen": "unsharp=5:5:0.22:3:3:0.08",
        "cas_strength": "0.18",
    },
    "max": {
        "label": "maximum quality",
        "crf": "14",
        "preset": "slow",
        "profile": "high",
        "level": "4.2",
        "audio_bitrate": "256k",
        "max_download_height": 2160,
        "sharpen": "unsharp=5:5:0.30:3:3:0.10",
        "cas_strength": "0.24",
    },
}
SCALE_QUALITY_FLAGS = "flags=lanczos"

TRANSCRIPT_REPLACEMENTS = {
    r"\binkam\b": "income",
    r"\bin kam\b": "income",
    r"\bcoin mass\b": "coin emas",
    r"\bkoin mass\b": "koin emas",
    r"\bfiat namis\b": "Vietnamese",
    r"\bfilipin\b": "Filipina",
    r"\bsilvernya\b": "silver-nya",
    r"\bdolarnya\b": "dolar-nya",
    r"\bsoftware- and wealth\b": "sovereign wealth",
    r"\bsoftware and wealth\b": "sovereign wealth",
    r"\bterperakap\b": "terperangkap",
    r"\bpengatahuan\b": "pengetahuan",
    r"\bdimasa\b": "di masa",
    r"\bribuk\b": "ribu",
    r"\bseraksud\b": "seratus",
    r"\bseris\b": "series",
    r"\bmelawangkan\b": "meluangkan",
    r"\bmenyerahanakan\b": "menyederhanakan",
}

SOURCE_BRANDING_PATTERNS = (
    r"\b(?:terima\s*kasih|makasih|thanks?)\s+(?:kepada|buat|untuk)\b",
    r"\b(?:jangan\s+lupa\s+)?(?:subscribe|subrek|follow)\b",
    r"\bikuti\s+(?:channel|kanal|akun|kami|kita|youtube|instagram|tiktok)\b",
    r"\b(?:like|komen|comment|share)\s+(?:dan\s+)?(?:subscribe|follow|video\s+ini)\b",
    r"\baktifkan\s+(?:tombol\s+)?lonceng\b",
    r"\b(?:selamat\s+datang|kembali\s+lagi)\s+(?:di|ke|bersama)\b",
    r"\b(?:channel|kanal)\s+(?:ini|kami|kita|youtube|resmi)\b",
    r"\b(?:youtube|instagram|tiktok)\s+(?:channel|kanal|kami|kita)\b",
    r"\b(?:saksikan|tonton)\s+(?:terus|selengkapnya|video\s+lain|kami)\b",
    r"\b(?:dipersembahkan|disponsori|didukung)\s+oleh\b",
    r"\b(?:supported|sponsored|presented)\s+by\b",
)


def run(command: list[str], cwd: Path | None = None) -> None:
    process = subprocess.run(command, cwd=cwd, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {process.returncode}: {' '.join(command)}")


_FFMPEG_PATH_CACHE: str | None = None
_FFMPEG_FILTER_CACHE: dict[tuple[str, str], bool] = {}


def ffmpeg_path() -> str:
    """Prefer a full system FFmpeg; imageio's minimal binary may lack text/libass filters."""
    global _FFMPEG_PATH_CACHE
    if _FFMPEG_PATH_CACHE:
        return _FFMPEG_PATH_CACHE

    configured = os.environ.get("FFMPEG_BINARY", "").strip()
    candidates = [
        configured,
        shutil.which("ffmpeg") or "",
        imageio_ffmpeg.get_ffmpeg_exe(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            _FFMPEG_PATH_CACHE = candidate
            return candidate
    raise RuntimeError("FFmpeg tidak ditemukan atau tidak dapat dijalankan.")


def ffmpeg_has_filter(name: str) -> bool:
    binary = ffmpeg_path()
    cache_key = (binary, name)
    if cache_key in _FFMPEG_FILTER_CACHE:
        return _FFMPEG_FILTER_CACHE[cache_key]
    try:
        result = subprocess.run(
            [binary, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        output = f"{result.stdout}\n{result.stderr}"
        supported = result.returncode == 0 and re.search(
            rf"(?m)^\s*[TSC.]+\s+{re.escape(name)}\s",
            output,
        ) is not None
    except (OSError, subprocess.TimeoutExpired):
        supported = False
    _FFMPEG_FILTER_CACHE[cache_key] = supported
    return supported


def configured_clip_max_bytes() -> int:
    raw = os.environ.get("CLIP_MAX_MB") or os.environ.get("YOUTUBE_MAX_UPLOAD_MB") or os.environ.get("YOUTUBE_CDP_MAX_UPLOAD_MB") or "45"
    try:
        mb = float(raw)
    except ValueError:
        mb = 45
    return max(1, int(mb * 1024 * 1024))


def enforce_clip_size_limit(path: Path, duration: float, max_bytes: int | None = None) -> Path:
    limit = max_bytes or configured_clip_max_bytes()
    if path.stat().st_size <= limit:
        return path
    if duration <= 0:
        raise RuntimeError(f"Clip {path.name} lebih dari {limit // 1024 // 1024} MB dan durasinya tidak valid.")

    temp_path = path.with_suffix(".size_tmp.mp4")
    target_total_bps = max(420_000, int((limit * 0.88 * 8) / duration))
    audio_bps = 96_000
    base_video_bps = max(260_000, target_total_bps - audio_bps)
    last_error = ""

    console.print(f"[yellow]Compressing[/yellow] {path.name} to stay under {limit // 1024 // 1024} MB.")
    for factor in (1.0, 0.82, 0.68, 0.55, 0.42):
        video_bps = max(220_000, int(base_video_bps * factor))
        temp_path.unlink(missing_ok=True)
        process = subprocess.run(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-tune",
                "film",
                "-x264-params",
                "aq-mode=3:aq-strength=0.85:deblock=-1,-1",
                "-b:v",
                str(video_bps),
                "-maxrate",
                str(video_bps),
                "-bufsize",
                str(video_bps * 2),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                f"{audio_bps // 1000}k",
                *ffmpeg_clean_metadata_args(),
                "-movflags",
                "+faststart",
                str(temp_path),
            ],
            text=True,
            capture_output=True,
        )
        if process.returncode != 0:
            last_error = (process.stderr or process.stdout or "").strip()[-1000:]
            continue
        if temp_path.is_file() and temp_path.stat().st_size <= limit:
            temp_path.replace(path)
            console.print(f"[green]Clip size OK[/green] {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB).")
            return path
        size_mb = temp_path.stat().st_size / 1024 / 1024 if temp_path.is_file() else 0
        last_error = f"hasil kompresi masih {size_mb:.1f} MB"

    temp_path.unlink(missing_ok=True)
    raise RuntimeError(f"Gagal membuat clip di bawah {limit // 1024 // 1024} MB: {last_error}")


def ytdlp_base_options(**overrides) -> dict:
    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 25,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "file_access_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "http_headers": YTDLP_HTTP_HEADERS,
        # Prefer IPv4 on hosts where IPv6 routes exist but cannot reach YouTube.
        "source_address": "0.0.0.0",
    }
    options.update(overrides)
    return options


def is_network_error(message: str) -> bool:
    lowered = message.lower()
    return any(pattern in lowered for pattern in NETWORK_ERROR_PATTERNS)


def friendly_youtube_error(exc: Exception, stage: str) -> str:
    message = str(exc).strip()
    if is_network_error(message):
        return (
            f"Koneksi server ke YouTube gagal saat {stage}. "
            "Pastikan server/container punya akses internet keluar. "
            "Kalau jaringan hosting memblokir YouTube, gunakan tab Upload Video sebagai fallback."
        )
    if "private video" in message.lower():
        return "Video YouTube bersifat privat, jadi tidak bisa diproses dari link publik."
    if "sign in" in message.lower() or "login" in message.lower():
        return (
            "YouTube meminta login atau verifikasi untuk video ini. "
            "Gunakan video publik lain atau upload file videonya langsung."
        )
    if "unsupported url" in message.lower():
        return "Link video tidak dikenali. Gunakan URL YouTube penuh atau link youtu.be yang valid."
    return f"Gagal mengambil video dari YouTube saat {stage}: {message}"


def make_even(value: float, minimum: int) -> int:
    rounded = max(minimum, int(round(value)))
    return rounded if rounded % 2 == 0 else rounded + 1


def clamp_even(value: float, minimum: int, maximum: int) -> int:
    bounded = max(minimum, min(maximum, int(round(value))))
    if bounded % 2:
        bounded -= 1
    return max(minimum, min(maximum, bounded))


def quality_preset(video_quality: VideoQuality) -> dict[str, str | int]:
    return VIDEO_QUALITY_PRESETS.get(video_quality, VIDEO_QUALITY_PRESETS["high"])


def scale_filter(width: int | str, height: int | str, *, force_increase: bool = False) -> str:
    force = ":force_original_aspect_ratio=increase" if force_increase else ""
    return f"scale={width}:{height}{force}:{SCALE_QUALITY_FLAGS}"


def add_quality_sharpen(vf: str, video_quality: VideoQuality) -> str:
    sharpen = quality_detail_filter(video_quality)
    return f"{vf},{sharpen}" if sharpen else vf


def quality_detail_filter(video_quality: VideoQuality) -> str:
    """Choose restrained adaptive clarity, with a widely supported fallback."""
    preset = quality_preset(video_quality)
    cas_strength = str(preset.get("cas_strength") or "")
    if cas_strength and ffmpeg_has_filter("cas"):
        return f"cas=strength={cas_strength}"
    return str(preset["sharpen"])


def ffmpeg_clean_metadata_args() -> list[str]:
    """Prevent source container tags/chapters from leaking into rendered deliverables."""
    return [
        "-map_metadata",
        "-1",
        "-map_metadata:s:v",
        "-1",
        "-map_metadata:s:a",
        "-1",
        "-map_chapters",
        "-1",
        "-metadata",
        "title=",
        "-metadata",
        "artist=",
        "-metadata",
        "album=",
        "-metadata",
        "comment=",
        "-metadata",
        "description=",
        "-metadata",
        "synopsis=",
        "-metadata",
        "copyright=",
        "-metadata",
        "license=",
        "-metadata",
        "encoder=",
        "-metadata:s:v",
        "handler_name=",
        "-metadata:s:v",
        "vendor_id=",
        "-metadata:s:a",
        "handler_name=",
        "-metadata:s:a",
        "vendor_id=",
    ]


def probe_video_resolution(path: Path) -> tuple[int, int]:
    ffmpeg_binary = Path(ffmpeg_path())
    ffprobe_candidates = [
        os.environ.get("FFPROBE_BINARY", "").strip(),
        shutil.which("ffprobe") or "",
        str(ffmpeg_binary.with_name("ffprobe")),
    ]
    for candidate in ffprobe_candidates:
        if not candidate:
            continue
        try:
            process = subprocess.run(
                [
                    candidate,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            payload = json.loads(process.stdout or "{}")
            streams = payload.get("streams")
            if process.returncode == 0 and isinstance(streams, list) and streams:
                width = int(streams[0].get("width") or 0)
                height = int(streams[0].get("height") or 0)
                if width > 0 and height > 0:
                    return width, height
        except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
            continue

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(f"Tidak dapat memverifikasi resolusi hasil clip: {path.name}") from exc

    capture = cv2.VideoCapture(str(path))
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Tidak dapat memverifikasi resolusi hasil clip: {path.name}")
    return width, height


def probe_media_stream_types(path: Path) -> set[str]:
    """Return available codec stream types without decoding the whole media file."""
    if not path.is_file() or path.stat().st_size <= 0:
        return set()
    ffmpeg_binary = Path(ffmpeg_path())
    ffprobe_candidates = [
        os.environ.get("FFPROBE_BINARY", "").strip(),
        shutil.which("ffprobe") or "",
        str(ffmpeg_binary.with_name("ffprobe")),
    ]
    for candidate in dict.fromkeys(value for value in ffprobe_candidates if value):
        try:
            process = subprocess.run(
                [
                    candidate,
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            payload = json.loads(process.stdout or "{}")
            streams = payload.get("streams")
            if process.returncode == 0 and isinstance(streams, list):
                return {
                    str(item.get("codec_type") or "").strip()
                    for item in streams
                    if isinstance(item, dict) and item.get("codec_type")
                }
        except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
            continue

    try:
        process = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    details = f"{process.stdout}\n{process.stderr}"
    streams: set[str] = set()
    if re.search(r"Stream #.*Video:", details):
        streams.add("video")
    if re.search(r"Stream #.*Audio:", details):
        streams.add("audio")
    return streams


def source_media_candidates(work_dir: Path) -> list[Path]:
    """List only finalized source video files; yt-dlp partials must never be reused."""
    candidates: list[Path] = []
    for path in work_dir.glob("source*"):
        lowered = path.name.casefold()
        if (
            not path.is_file()
            or path.suffix.casefold() not in SOURCE_VIDEO_EXTENSIONS
            or ".part" in lowered
            or lowered.endswith(".ytdl")
            or lowered.endswith(".tmp")
        ):
            continue
        candidates.append(path)
    return sorted(
        candidates,
        key=lambda item: (
            item.name.casefold() not in {"source.mp4", "source.mkv", "source.webm"},
            -item.stat().st_mtime,
        ),
    )


def select_usable_source_media(work_dir: Path) -> Path | None:
    for path in source_media_candidates(work_dir):
        if {"video", "audio"}.issubset(probe_media_stream_types(path)):
            return path
    return None


def ensure_minimum_hd_output(path: Path) -> tuple[int, int]:
    """Reject an export if its encoded frame is below vertical 720p."""
    width, height = probe_video_resolution(path)
    short_side, long_side = sorted((width, height))
    if short_side < 720 or long_side < 1280:
        raise RuntimeError(
            f"Hasil clip {path.name} hanya {width}x{height}; minimal HD 720x1280. "
            "Export dibatalkan agar video pecah tidak ikut dipakai."
        )
    return width, height


def remove_running_text_filter(crop_bottom: int = 280) -> str:
    """Obscure a source footer/ticker when cleanup is explicitly requested.

    This is intentionally opt-in. Any footer treatment necessarily modifies
    source pixels and can overlap a close-up speaker, so the normal render path
    keeps the original frame untouched.
    """
    # Keep the legacy argument name for callers that passed crop_bottom by keyword;
    # it now controls the height of the feathered blur instead of a destructive crop.
    safe_height = max(160, min(420, int(crop_bottom)))
    footer_y = 1920 - safe_height
    # The fourth-power alpha ramp makes the upper blur boundary feather in
    # quickly while leaving no hard horizontal seam over the source footage.
    alpha = "255*(1-pow(1-Y/H,4))"
    return (
        "split=2[footer_base][footer_blur_src];"
        f"[footer_blur_src]crop=1080:{safe_height}:0:{footer_y},"
        "gblur=sigma=44:sigmaV=20:steps=3,"
        "drawbox=color=black@0.07:t=fill,format=rgba,"
        f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[footer_blur];"
        f"[footer_base][footer_blur]overlay=0:{footer_y}:shortest=1:eof_action=pass,"
        "setsar=1"
    )


def localized_watermark_blur_filter(region: WatermarkRegion) -> str:
    """Blur one tightly bounded watermark with a feathered, seam-free edge."""
    x = max(0, int(region.x) // 2 * 2)
    y = max(0, int(region.y) // 2 * 2)
    width = max(16, int(region.width) // 2 * 2)
    height = max(12, int(region.height) // 2 * 2)
    if region.source_width > 0:
        width = min(width, max(16, (region.source_width - x) // 2 * 2))
    if region.source_height > 0:
        height = min(height, max(12, (region.source_height - y) // 2 * 2))
    sigma = max(8, min(20, round(width * 0.06)))
    sigma_vertical = max(6, min(14, round(height * 0.18)))
    feather = max(4, min(12, min(width, height) // 6))
    alpha = (
        f"255*clip(min(min(X,W-1-X),min(Y,H-1-Y))/{feather},0,1)"
    )
    return (
        "split=2[wm_base][wm_blur_src];"
        f"[wm_blur_src]crop={width}:{height}:{x}:{y},"
        f"gblur=sigma={sigma}:sigmaV={sigma_vertical}:steps=3,format=rgba,"
        f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[wm_patch];"
        f"[wm_base][wm_patch]overlay={x}:{y}:shortest=1:eof_action=pass,setsar=1"
    )


def detect_static_watermark_region(
    preview_path: Path,
    *,
    skip_edge_frames: int = 4,
) -> WatermarkRegion | None:
    """Find a compact text-like overlay that persists across a clip preview.

    Detection runs on the already-cropped preview, before Fendy Clipper captions,
    channel branding, and CTA are drawn. Requiring repeated edge strokes across
    many frames prevents ordinary speech captions from becoming blur targets.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return None

    capture = cv2.VideoCapture(str(preview_path.resolve()))
    if not capture.isOpened():
        return None
    frames = []
    try:
        while len(frames) < 90:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    if len(frames) < 7:
        return None

    trim = min(max(1, skip_edge_frames), max(1, (len(frames) - 5) // 2))
    analysis_frames = frames[trim : len(frames) - trim]
    if len(analysis_frames) < 5:
        return None
    height, width = analysis_frames[0].shape[:2]
    if width < 120 or height < 160:
        return None

    edge_stack = []
    gray_stack = []
    for frame in analysis_frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_stack.append(gray)
        edge_stack.append(cv2.Canny(gray, 42, 126) > 0)
    edge_frequency = np.mean(np.stack(edge_stack, axis=0), axis=0)
    persistent = (edge_frequency >= 0.58).astype(np.uint8) * 255

    # Ignore frame boundaries, progress bars, and player-safe bottom UI. A
    # watermark may still sit in any corner or in the centre-lower area.
    mask = np.zeros_like(persistent)
    mask[
        int(height * 0.06) : int(height * 0.88),
        int(width * 0.025) : int(width * 0.975),
    ] = 255
    persistent = cv2.bitwise_and(persistent, mask)
    joined = cv2.morphologyEx(
        persistent,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (13, 3)),
        iterations=1,
    )
    joined = cv2.dilate(
        joined,
        cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3)),
        iterations=1,
    )
    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        joined, 8
    )
    candidates: list[tuple[float, WatermarkRegion]] = []
    frame_area = float(width * height)
    edge_arrays = np.stack(edge_stack, axis=0)

    for index in range(1, component_count):
        x, y, component_width, component_height, _area = stats[index]
        width_ratio = component_width / width
        height_ratio = component_height / height
        aspect = component_width / max(1, component_height)
        if not (0.055 <= width_ratio <= 0.52):
            continue
        if not (0.008 <= height_ratio <= 0.13):
            continue
        if aspect < 1.80 or component_width * component_height > frame_area * 0.065:
            continue

        component_patch = persistent[y : y + component_height, x : x + component_width]
        if not component_patch.size:
            continue
        component_edge_y, component_edge_x = np.where(component_patch > 0)
        if len(component_edge_x) < 8:
            continue

        # Closing/dilation is only for grouping glyphs. Derive the actual blur
        # bounds from the raw persistent strokes and discard isolated outliers
        # so the final patch hugs the logo instead of the morphology halo.
        tight_left = x + int(np.floor(np.percentile(component_edge_x, 1.5)))
        tight_right = x + int(np.ceil(np.percentile(component_edge_x, 98.5))) + 1
        tight_top = y + int(np.floor(np.percentile(component_edge_y, 1.5)))
        tight_bottom = y + int(np.ceil(np.percentile(component_edge_y, 98.5))) + 1
        tight_width = tight_right - tight_left
        tight_height = tight_bottom - tight_top
        if tight_width < max(12, int(width * 0.04)) or tight_height < 4:
            continue
        raw_patch = persistent[tight_top:tight_bottom, tight_left:tight_right]
        edge_pixels = raw_patch > 0
        edge_density = float(np.count_nonzero(edge_pixels)) / float(raw_patch.size)
        if not (0.012 <= edge_density <= 0.42):
            continue
        glyph_count, _glyph_labels, glyph_stats, _glyph_centroids = (
            cv2.connectedComponentsWithStats(raw_patch, 8)
        )
        meaningful_glyphs = sum(
            1
            for glyph_index in range(1, glyph_count)
            if 2 <= glyph_stats[glyph_index, cv2.CC_STAT_AREA] <= raw_patch.size * 0.22
        )
        if meaningful_glyphs < 3:
            continue
        persistence = float(
            np.mean(
                edge_frequency[tight_top:tight_bottom, tight_left:tight_right][edge_pixels]
            )
        )
        # Changing subtitles often reuse the same lower-center baseline, but
        # their exact strokes are less stable than an overlaid channel mark.
        # Require a stronger per-pixel consensus before considering blur.
        if persistence < 0.78:
            continue
        consensus = edge_pixels.astype(np.uint8) * 255
        consensus = cv2.dilate(
            consensus,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
            iterations=1,
        )
        consensus_pixels = consensus > 0
        frame_overlaps = []
        for frame_edges in edge_arrays:
            frame_patch = frame_edges[
                tight_top:tight_bottom,
                tight_left:tight_right,
            ]
            frame_overlaps.append(
                float(np.count_nonzero(frame_patch & consensus_pixels))
                / max(1.0, float(np.count_nonzero(edge_pixels)))
            )
        temporal_support = float(np.mean(np.asarray(frame_overlaps) >= 0.48))
        if temporal_support < 0.68:
            continue

        text_score = min(1.0, meaningful_glyphs / 12.0)
        aspect_score = min(1.0, aspect / 5.0)
        center_x = (tight_left + tight_right) / 2.0
        center_y = (tight_top + tight_bottom) / 2.0
        caption_band_like = bool(
            center_y / height >= 0.70
            and 0.14 <= center_x / width <= 0.86
            and tight_width / width >= 0.16
        )
        if caption_band_like:
            continue
        nearest_edge = min(
            center_x / width,
            (width - center_x) / width,
            center_y / height,
            (height - center_y) / height,
        )
        edge_proximity = max(0.0, min(1.0, 1.0 - nearest_edge / 0.42))
        confidence = (
            persistence * 0.42
            + temporal_support * 0.24
            + text_score * 0.18
            + edge_proximity * 0.10
            + aspect_score * 0.06
        )
        if confidence < 0.66:
            continue

        # Padding follows glyph height rather than the whole canvas, keeping a
        # small safety margin at any preview/output resolution.
        padding_x = max(4, min(int(width * 0.012), round(tight_height * 0.26)))
        padding_y = max(4, min(int(height * 0.009), round(tight_height * 0.22)))
        padded_x = max(0, tight_left - padding_x)
        padded_y = max(0, tight_top - padding_y)
        padded_right = min(width, tight_right + padding_x)
        padded_bottom = min(height, tight_bottom + padding_y)
        region = WatermarkRegion(
            x=int(padded_x),
            y=int(padded_y),
            width=int(padded_right - padded_x),
            height=int(padded_bottom - padded_y),
            source_width=int(width),
            source_height=int(height),
            confidence=round(float(confidence), 3),
            persistence=round(float(persistence), 3),
        )
        candidates.append((confidence, region))

    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def scale_watermark_region(
    region: WatermarkRegion,
    output_width: int,
    output_height: int,
) -> WatermarkRegion:
    """Map preview coordinates back to the final render canvas."""
    scale_x = output_width / max(1, region.source_width)
    scale_y = output_height / max(1, region.source_height)
    x = max(0, min(output_width - 16, round(region.x * scale_x)))
    y = max(0, min(output_height - 12, round(region.y * scale_y)))
    width = min(output_width - x, max(16, round(region.width * scale_x)))
    height = min(output_height - y, max(12, round(region.height * scale_y)))
    return WatermarkRegion(
        x=x,
        y=y,
        width=width,
        height=height,
        source_width=output_width,
        source_height=output_height,
        confidence=region.confidence,
        persistence=region.persistence,
    )


def adaptive_text_backdrop_split_filter(
    duration: float,
    asset_path: Path = MOSQUE_CONGREGATION_PATH,
) -> str:
    """Blend a dominant speaker portrait over a restrained congregation panel.

    The complete composition is present from the first frame. Delaying it with
    an alpha fade made the opening frame look empty/black in video players and
    caused the mosque panel to pop in only after the hook had already started.
    """
    escaped_path = (
        str(asset_path.resolve())
        .replace("\\", "/")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )
    # Keep the speaker dominant and let the congregation enter only in the
    # lower 40%. Opposing alpha ramps overlap around y=1160..1320 so there is
    # no hard horizontal divider or abrupt half-and-half collage.
    return (
        "split=3[adaptive_original][adaptive_stage_base][adaptive_subject_src];"
        "[adaptive_subject_src]"
        "crop=1080:1320:0:0,"
        "scale=1080:1320:flags=lanczos,format=rgba,"
        "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        "a='255*min(1,max(0,(H-Y)/180))'[adaptive_subject];"
        f"movie='{escaped_path}':loop=0,"
        "scale=1320:820:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1320:820,"
        "zoompan=z='1.025+0.008*sin(on/92)':"
        "x='(iw-iw/zoom)/2+10*sin(on/84)':"
        "y='(ih-ih/zoom)/2+6*cos(on/105)':"
        "d=1:s=1080x760:fps=25,"
        "gblur=sigma=1.2:sigmaV=0.8:steps=1,"
        "eq=contrast=1.02:brightness=-0.045:saturation=0.88,"
        "vignette=PI/10,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=#03130E@0.12:t=fill,"
        "format=rgba,"
        "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        "a='255*min(1,max(0,Y/160))',"
        "setsar=1[adaptive_jamaah];"
        "[adaptive_jamaah]"
        "pad=1080:1920:0:1160:color=black@0[adaptive_jamaah_canvas];"
        "[adaptive_stage_base][adaptive_jamaah_canvas]"
        "overlay=0:0:shortest=1:eof_action=repeat[adaptive_stage];"
        "[adaptive_stage][adaptive_subject]"
        "overlay=0:0:shortest=1:eof_action=repeat,"
        "format=rgba"
        "[adaptive_split];"
        "[adaptive_original][adaptive_split]"
        "overlay=0:0:shortest=1:eof_action=repeat"
    )


def make_cv2_cascade(cv2_module, filename: str):
    if not hasattr(cv2_module, "CascadeClassifier"):
        return None

    cascade_dir = getattr(getattr(cv2_module, "data", None), "haarcascades", "")
    if not cascade_dir:
        return None

    cascade = cv2_module.CascadeClassifier(str(Path(cascade_dir) / filename))
    if hasattr(cascade, "empty") and cascade.empty():
        return None
    return cascade


def detect_person_focus_x(video_path: Path, clip: ClipCandidate) -> tuple[float, tuple[int, int]] | None:
    try:
        import cv2
    except Exception as exc:
        console.print(f"[yellow]Person crop unavailable:[/yellow] {exc}")
        return None

    capture = cv2.VideoCapture(str(video_path.resolve()))
    if not capture.isOpened():
        return None

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        capture.release()
        return None

    duration = max(0.1, clip.end - clip.start)
    sample_count = min(12, max(4, int(duration // 8)))
    if sample_count == 1:
        offsets = [duration / 2]
    else:
        step = duration / (sample_count + 1)
        offsets = [step * (index + 1) for index in range(sample_count)]

    hog = None
    if hasattr(cv2, "HOGDescriptor") and hasattr(cv2, "HOGDescriptor_getDefaultPeopleDetector"):
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    else:
        console.print("[yellow]OpenCV HOG people detector unavailable; using face detection only.[/yellow]")

    can_make_gray = hasattr(cv2, "cvtColor") and hasattr(cv2, "COLOR_BGR2GRAY")
    face_cascade = make_cv2_cascade(cv2, "haarcascade_frontalface_default.xml") if can_make_gray else None
    profile_cascade = make_cv2_cascade(cv2, "haarcascade_profileface.xml") if can_make_gray else None
    yunet = None
    if YUNET_MODEL_PATH.exists() and hasattr(cv2, "FaceDetectorYN_create"):
        yunet = cv2.FaceDetectorYN_create(
            str(YUNET_MODEL_PATH),
            "",
            (320, 320),
            0.35,
            0.3,
            5000,
        )

    if hog is None and face_cascade is None and profile_cascade is None and yunet is None:
        capture.release()
        console.print("[yellow]OpenCV object detectors unavailable; using center crop.[/yellow]")
        return None

    face_weighted_sum = 0.0
    face_total_weight = 0.0
    person_weighted_sum = 0.0
    person_total_weight = 0.0

    for offset in offsets:
        capture.set(cv2.CAP_PROP_POS_MSEC, (clip.start + offset) * 1000)
        ok, frame = capture.read()
        if not ok:
            continue

        resize_scale = min(1.0, 720 / max(frame.shape[:2]))
        if resize_scale < 1:
            resized = cv2.resize(frame, None, fx=resize_scale, fy=resize_scale, interpolation=cv2.INTER_AREA)
        else:
            resized = frame

        gray = (
            cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            if face_cascade is not None or profile_cascade is not None
            else None
        )
        face_detections: list[tuple[float, float, float]] = []
        person_detections: list[tuple[float, float, float]] = []

        if yunet is not None:
            resized_height, resized_width = resized.shape[:2]
            yunet.setInputSize((resized_width, resized_height))
            _, faces = yunet.detect(resized)
            if faces is not None:
                for face in faces:
                    x, _, w, h = face[:4]
                    confidence = float(face[-1])
                    center_x = (x + w / 2) / resize_scale
                    face_detections.append((center_x, max(w, h) / resize_scale, confidence * 3.0))

        if face_cascade is not None and gray is not None:
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(36, 36))
            for x, y, w, h in faces:
                center_x = (x + w / 2) / resize_scale
                face_detections.append((center_x, max(w, h) / resize_scale, 2.0))

        if profile_cascade is not None and gray is not None:
            profiles = profile_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(34, 34))
            for x, y, w, h in profiles:
                center_x = (x + w / 2) / resize_scale
                face_detections.append((center_x, max(w, h) / resize_scale, 1.8))

            if hasattr(cv2, "flip"):
                flipped_gray = cv2.flip(gray, 1)
                flipped_profiles = profile_cascade.detectMultiScale(
                    flipped_gray,
                    scaleFactor=1.08,
                    minNeighbors=4,
                    minSize=(34, 34),
                )
                resized_width = resized.shape[1]
                for x, y, w, h in flipped_profiles:
                    original_x = resized_width - x - w
                    center_x = (original_x + w / 2) / resize_scale
                    face_detections.append((center_x, max(w, h) / resize_scale, 1.8))

        if hog is not None:
            people, weights = hog.detectMultiScale(
                resized,
                winStride=(8, 8),
                padding=(16, 16),
                scale=1.05,
            )
            for index, (x, _, w, _) in enumerate(people):
                confidence = float(weights[index]) if len(weights) > index else 1.0
                center_x = (x + w / 2) / resize_scale
                person_detections.append((center_x, w / resize_scale, max(0.25, confidence)))

        if face_detections:
            center_x, box_width, confidence = max(face_detections, key=lambda item: item[1] * item[2])
            weight = box_width * confidence
            face_weighted_sum += (center_x / width) * weight
            face_total_weight += weight
        elif person_detections:
            center_x, box_width, confidence = max(person_detections, key=lambda item: item[1] * item[2])
            weight = box_width * confidence
            person_weighted_sum += (center_x / width) * weight
            person_total_weight += weight

    capture.release()
    if face_total_weight > 0:
        return face_weighted_sum / face_total_weight, (width, height)
    if person_total_weight > 0:
        return person_weighted_sum / person_total_weight, (width, height)
    if face_total_weight <= 0 and person_total_weight <= 0:
        return None


def detect_speaker_focus_points(
    video_path: Path,
    clip: ClipCandidate,
) -> tuple[tuple[float, float], tuple[int, int]] | None:
    """Find two consistently separated face positions for a speaker split-screen."""
    try:
        import cv2
    except Exception:
        return None

    capture = cv2.VideoCapture(str(video_path.resolve()))
    if not capture.isOpened():
        return None
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        capture.release()
        return None

    can_make_gray = hasattr(cv2, "cvtColor") and hasattr(cv2, "COLOR_BGR2GRAY")
    face_cascade = make_cv2_cascade(cv2, "haarcascade_frontalface_default.xml") if can_make_gray else None
    yunet = None
    if YUNET_MODEL_PATH.exists() and hasattr(cv2, "FaceDetectorYN_create"):
        yunet = cv2.FaceDetectorYN_create(
            str(YUNET_MODEL_PATH),
            "",
            (320, 320),
            0.35,
            0.3,
            5000,
        )
    if face_cascade is None and yunet is None:
        capture.release()
        return None

    duration = max(0.1, clip.end - clip.start)
    sample_count = min(14, max(6, int(duration // 6)))
    step = duration / (sample_count + 1)
    observations: list[tuple[float, float]] = []
    frames_with_pair = 0

    for index in range(sample_count):
        capture.set(cv2.CAP_PROP_POS_MSEC, (clip.start + step * (index + 1)) * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        resize_scale = min(1.0, 720 / max(frame.shape[:2]))
        resized = (
            cv2.resize(frame, None, fx=resize_scale, fy=resize_scale, interpolation=cv2.INTER_AREA)
            if resize_scale < 1
            else frame
        )
        detected: list[tuple[float, float]] = []
        if yunet is not None:
            resized_height, resized_width = resized.shape[:2]
            yunet.setInputSize((resized_width, resized_height))
            _, faces = yunet.detect(resized)
            if faces is not None:
                for face in faces:
                    x, _, face_width, face_height = face[:4]
                    confidence = float(face[-1])
                    center_x = (x + face_width / 2) / max(1.0, resized_width)
                    detected.append((center_x, max(1.0, face_width * face_height * confidence)))
        elif face_cascade is not None:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=5,
                minSize=(36, 36),
            )
            resized_width = resized.shape[1]
            for x, _, face_width, face_height in faces:
                detected.append(
                    ((x + face_width / 2) / max(1.0, resized_width), float(face_width * face_height))
                )

        strongest = sorted(detected, key=lambda item: item[1], reverse=True)[:3]
        if len(strongest) >= 2:
            ordered = sorted(strongest, key=lambda item: item[0])
            if ordered[-1][0] - ordered[0][0] >= 0.18:
                frames_with_pair += 1
        observations.extend(strongest)

    capture.release()
    if len(observations) < 4:
        return None

    left_center = min(item[0] for item in observations)
    right_center = max(item[0] for item in observations)
    if right_center - left_center < 0.18:
        return None
    left_group: list[tuple[float, float]] = []
    right_group: list[tuple[float, float]] = []
    for _ in range(6):
        left_group = []
        right_group = []
        for item in observations:
            target = left_group if abs(item[0] - left_center) <= abs(item[0] - right_center) else right_group
            target.append(item)
        if not left_group or not right_group:
            return None
        left_center = sum(x * weight for x, weight in left_group) / sum(weight for _, weight in left_group)
        right_center = sum(x * weight for x, weight in right_group) / sum(weight for _, weight in right_group)

    if right_center - left_center < 0.20:
        return None
    if frames_with_pair == 0 and (len(left_group) < 2 or len(right_group) < 2):
        return None
    return (left_center, right_center), (width, height)


def analyze_text_heavy_backdrop(frame, *, force: bool = False) -> BackdropProfile | None:
    """Detect a mostly uniform event banner with rows of contrasting text."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if frame is None or not getattr(frame, "size", 0):
        return None

    height, width = frame.shape[:2]
    scale = min(1.0, 480 / max(1, width))
    small = (
        cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else frame.copy()
    )
    small_height, small_width = small.shape[:2]
    upper_height = max(40, int(small_height * 0.72))
    upper = small[:upper_height]
    lab = cv2.cvtColor(upper, cv2.COLOR_BGR2LAB).astype(np.float32)

    strip_y = max(4, int(upper_height * 0.10))
    strip_x = max(4, int(small_width * 0.07))
    border_pixels = np.concatenate(
        [
            lab[:strip_y].reshape(-1, 3),
            lab[:, :strip_x].reshape(-1, 3),
            lab[:, -strip_x:].reshape(-1, 3),
        ],
        axis=0,
    )
    sample_step = max(1, len(border_pixels) // 12000)
    samples = border_pixels[::sample_step].astype(np.float32)
    if len(samples) < 20:
        return None

    cv2.setRNGSeed(17)
    _compactness, labels, centers = cv2.kmeans(
        samples,
        3,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5),
        3,
        cv2.KMEANS_PP_CENTERS,
    )
    counts = np.bincount(labels.ravel(), minlength=3)
    dominant_index = int(np.argmax(counts))
    dominant = centers[dominant_index]
    dominant_samples = samples[labels.ravel() == dominant_index]
    sample_distances = np.linalg.norm(dominant_samples - dominant, axis=1)
    threshold = float(np.clip(np.percentile(sample_distances, 90) + 10.0, 18.0, 38.0))

    distance = np.linalg.norm(lab - dominant.reshape(1, 1, 3), axis=2)
    background_mask = (distance <= threshold).astype(np.uint8) * 255
    background_mask = cv2.morphologyEx(
        background_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (7, 5)),
        iterations=1,
    )
    dominant_ratio = float(np.count_nonzero(background_mask)) / float(background_mask.size)

    foreground = cv2.bitwise_not(background_mask)
    component_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(foreground, 8)
    upper_area = upper_height * small_width
    row_bins: dict[int, int] = {}
    small_components = 0
    row_size = max(10, upper_height // 28)
    for index in range(1, component_count):
        x, y, component_width, component_height, area = stats[index]
        if not (10 <= area <= upper_area * 0.0045):
            continue
        if component_width < 3 or component_height < 3:
            continue
        aspect = component_width / max(1, component_height)
        if not 0.12 <= aspect <= 8.0:
            continue
        small_components += 1
        row = int(centroids[index][1] // row_size)
        row_bins[row] = row_bins.get(row, 0) + 1
    aligned_components = max(row_bins.values(), default=0)
    edges = cv2.Canny(cv2.cvtColor(upper, cv2.COLOR_BGR2GRAY), 70, 160)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)
    confidence = (
        dominant_ratio * 0.55
        + min(1.0, aligned_components / 12.0) * 0.25
        + min(1.0, edge_density / 0.08) * 0.20
    )
    if not force and (
        dominant_ratio < 0.30
        or aligned_components < 5
        or small_components < 8
        or confidence < 0.42
    ):
        return None
    if force and dominant_ratio < 0.18:
        threshold = min(48.0, threshold + 8.0)

    return BackdropProfile(
        dominant_lab=tuple(float(value) for value in dominant),
        color_threshold=threshold,
        confidence=round(confidence, 3),
        dominant_ratio=round(dominant_ratio, 3),
        aligned_component_count=aligned_components,
    )


def analyze_embedded_split_frame(frame) -> EmbeddedSplitProfile | None:
    """Detect a hard horizontal speaker/banner composition embedded in the source."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if frame is None or not getattr(frame, "size", 0):
        return None

    source_height, source_width = frame.shape[:2]
    if source_width < 160 or source_height < 120:
        return None
    scale = min(1.0, 640 / max(1, source_width))
    small = (
        cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else frame.copy()
    )
    height, width = small.shape[:2]
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    search_start = max(8, int(height * 0.34))
    search_end = min(height - 8, int(height * 0.76))
    if search_end <= search_start:
        return None

    # A precomposed banner changes most columns at one stable horizontal row.
    # Compare narrow strips instead of individual rows so camera noise and
    # clothing edges do not look like a layout boundary.
    strengths: list[float] = []
    for y in range(search_start, search_end):
        above = lab[max(0, y - 4) : y].mean(axis=0)
        below = lab[y : min(height, y + 4)].mean(axis=0)
        strengths.append(float(np.mean(np.linalg.norm(above - below, axis=1))))
    if not strengths:
        return None
    best_offset = int(np.argmax(strengths))
    boundary_y = search_start + best_offset
    boundary_strength = strengths[best_offset]
    baseline = float(np.percentile(strengths, 65))
    if boundary_strength < max(8.0, baseline * 1.75):
        return None

    lower = gray[boundary_y + 2 :]
    if lower.shape[0] < max(28, int(height * 0.18)):
        return None
    # Edge components capture bright or dark lettering without depending on
    # the banner's color or language. A tiny dilation joins both sides of each
    # glyph while keeping neighboring letters separate.
    strokes = cv2.Canny(lower, 55, 145)
    strokes = cv2.dilate(
        strokes,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        iterations=1,
    )
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(strokes, 8)
    lower_area = lower.shape[0] * lower.shape[1]
    row_size = max(8, lower.shape[0] // 14)
    row_bins: dict[int, int] = {}
    text_components = 0
    for index in range(1, count):
        _x, _y, component_width, component_height, area = stats[index]
        if not (6 <= area <= lower_area * 0.018):
            continue
        if not (2 <= component_width <= width * 0.24):
            continue
        if not (3 <= component_height <= lower.shape[0] * 0.36):
            continue
        aspect = component_width / max(1, component_height)
        if not 0.10 <= aspect <= 8.0:
            continue
        text_components += 1
        row = int(centroids[index][1] // row_size)
        row_bins[row] = row_bins.get(row, 0) + 1
    aligned_components = max(row_bins.values(), default=0)
    if text_components < 7 or aligned_components < 4:
        return None

    upper_mean = lab[max(0, boundary_y - max(8, height // 12)) : boundary_y].mean(axis=(0, 1))
    lower_mean = lab[
        boundary_y : min(height, boundary_y + max(8, height // 12))
    ].mean(axis=(0, 1))
    color_separation = float(np.linalg.norm(upper_mean - lower_mean))
    relative_strength = boundary_strength / max(1.0, baseline)
    confidence = min(
        1.0,
        0.38
        + min(0.26, max(0.0, relative_strength - 1.7) * 0.13)
        + min(0.20, aligned_components / 40.0)
        + min(0.16, color_separation / 160.0),
    )
    if confidence < 0.52:
        return None
    return EmbeddedSplitProfile(
        boundary_ratio=round(boundary_y / height, 4),
        confidence=round(confidence, 3),
        lower_text_component_count=text_components,
        source_width=source_width,
        source_height=source_height,
    )


def detect_embedded_split_layout(
    video_path: Path,
    clip: ClipCandidate,
    *,
    sample_count: int = 3,
) -> EmbeddedSplitProfile | None:
    """Require the same embedded split across multiple clip frames."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None

    capture = cv2.VideoCapture(str(video_path.resolve()))
    if not capture.isOpened():
        return None
    duration = max(0.1, clip.end - clip.start)
    profiles: list[EmbeddedSplitProfile] = []
    try:
        for index in range(max(2, sample_count)):
            fraction = (index + 1) / (max(2, sample_count) + 1)
            capture.set(cv2.CAP_PROP_POS_MSEC, (clip.start + duration * fraction) * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            profile = analyze_embedded_split_frame(frame)
            if profile is not None:
                profiles.append(profile)
    finally:
        capture.release()
    required = max(2, math.ceil(max(2, sample_count) * 0.6))
    if len(profiles) < required:
        return None
    ratios = [profile.boundary_ratio for profile in profiles]
    if max(ratios) - min(ratios) > 0.055:
        return None
    best = max(profiles, key=lambda item: item.confidence)
    return EmbeddedSplitProfile(
        boundary_ratio=round(float(np.median(ratios)), 4),
        confidence=round(sum(item.confidence for item in profiles) / len(profiles), 3),
        lower_text_component_count=max(
            item.lower_text_component_count for item in profiles
        ),
        source_width=best.source_width,
        source_height=best.source_height,
    )


def _cover_resize_background(image, width: int, height: int):
    import cv2

    source_height, source_width = image.shape[:2]
    scale = max(width / max(1, source_width), height / max(1, source_height))
    resized_width = max(width, int(round(source_width * scale)))
    resized_height = max(height, int(round(source_height * scale)))
    resized = cv2.resize(
        image,
        (resized_width, resized_height),
        interpolation=cv2.INTER_CUBIC,
    )
    x = max(0, (resized_width - width) // 2)
    y = max(0, (resized_height - height) // 2)
    plate = resized[y : y + height, x : x + width]
    return cv2.GaussianBlur(plate, (0, 0), sigmaX=1.4, sigmaY=1.4)


def _backdrop_replacement_mask(
    frame,
    profile: BackdropProfile,
    face_cascade,
    *,
    detect_face: bool,
    previous_face: tuple[int, int, int, int] | None,
):
    import cv2
    import numpy as np

    height, width = frame.shape[:2]
    scale = min(1.0, 480 / max(1, width))
    small = (
        cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else frame.copy()
    )
    small_height, small_width = small.shape[:2]
    upper_height = max(40, int(small_height * 0.74))
    upper = small[:upper_height]
    lab = cv2.cvtColor(upper, cv2.COLOR_BGR2LAB).astype(np.float32)
    dominant = np.asarray(profile.dominant_lab, dtype=np.float32).reshape(1, 1, 3)
    distance = np.linalg.norm(lab - dominant, axis=2)
    mask_upper = (distance <= profile.color_threshold).astype(np.uint8) * 255
    mask_upper = cv2.morphologyEx(
        mask_upper,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 7)),
        iterations=2,
    )

    inverse = cv2.bitwise_not(mask_upper)
    component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(inverse, 8)
    upper_area = upper_height * small_width
    for index in range(1, component_count):
        _x, _y, component_width, component_height, area = stats[index]
        aspect = max(component_width, component_height) / max(1, min(component_width, component_height))
        preserve_thin_object = aspect >= 7.0 and area >= upper_area * 0.00035
        if area <= upper_area * 0.006 and not preserve_thin_object:
            mask_upper[labels == index] = 255

    face = previous_face
    if detect_face and face_cascade is not None:
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(32, 32),
        )
        if len(faces):
            face = max(faces, key=lambda box: int(box[2]) * int(box[3]))
    if face is not None:
        x, y, face_width, face_height = (int(value) for value in face)
        center = (
            int(x + face_width * 0.5),
            int(y + face_height * 0.52),
        )
        axes = (
            max(12, int(face_width * 0.62)),
            max(14, int(face_height * 0.70)),
        )
        cv2.ellipse(mask_upper, center, axes, 0, 0, 360, 0, -1)

    mask_small = np.zeros((small_height, small_width), dtype=np.uint8)
    mask_small[:upper_height] = mask_upper
    fade_start = int(small_height * 0.57)
    fade_end = min(upper_height, int(small_height * 0.74))
    if fade_end > fade_start:
        gradient = np.linspace(1.0, 0.0, fade_end - fade_start, dtype=np.float32)
        mask_small[fade_start:fade_end] = (
            mask_small[fade_start:fade_end].astype(np.float32) * gradient[:, None]
        ).astype(np.uint8)
    mask_small[fade_end:] = 0
    mask_small = cv2.GaussianBlur(mask_small, (0, 0), sigmaX=3.2, sigmaY=3.2)
    mask = cv2.resize(mask_small, (width, height), interpolation=cv2.INTER_LINEAR)
    return mask, face


def render_clean_background_segment(
    video_path: Path,
    clip: ClipCandidate,
    output_path: Path,
    mode: BackgroundMode,
) -> tuple[Path | None, BackdropProfile | None]:
    """Replace a text-heavy static backdrop while preserving the foreground subject."""
    if mode == "keep" or not MOSQUE_BACKGROUND_PATH.is_file():
        return None, None
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        console.print(f"[yellow]Background cleanup unavailable:[/yellow] {exc}")
        return None, None

    capture = cv2.VideoCapture(str(video_path.resolve()))
    if not capture.isOpened():
        return None, None
    capture.set(cv2.CAP_PROP_POS_MSEC, clip.start * 1000)
    ok, first_frame = capture.read()
    if not ok:
        capture.release()
        return None, None

    profile = analyze_text_heavy_backdrop(first_frame, force=mode == "mosque")
    if profile is None:
        capture.release()
        console.print("[dim]Background bersih: backdrop tidak terdeteksi penuh tulisan; sumber dipertahankan.[/dim]")
        return None, None

    background = cv2.imread(str(MOSQUE_BACKGROUND_PATH), cv2.IMREAD_COLOR)
    if background is None:
        capture.release()
        return None, None
    height, width = first_frame.shape[:2]
    plate = _cover_resize_background(background, width, height)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    if not math.isfinite(fps) or fps <= 1:
        fps = 30.0
    max_frames = max(1, int(math.ceil((clip.end - clip.start) * fps)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "14",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    face_cascade = make_cv2_cascade(cv2, "haarcascade_frontalface_default.xml")
    previous_face: tuple[int, int, int, int] | None = None
    previous_mask = None
    frame = first_frame
    written = 0
    error_text = ""
    try:
        while written < max_frames and frame is not None:
            mask, previous_face = _backdrop_replacement_mask(
                frame,
                profile,
                face_cascade,
                detect_face=written % 8 == 0,
                previous_face=previous_face,
            )
            if previous_mask is not None:
                mask = cv2.addWeighted(previous_mask, 0.35, mask, 0.65, 0)
            previous_mask = mask
            alpha = mask.astype(np.float32)[:, :, None] / 255.0
            composited = np.clip(
                frame.astype(np.float32) * (1.0 - alpha)
                + plate.astype(np.float32) * alpha,
                0,
                255,
            ).astype(np.uint8)
            assert process.stdin is not None
            process.stdin.write(composited.tobytes())
            written += 1
            ok, next_frame = capture.read()
            frame = next_frame if ok else None
    except (BrokenPipeError, OSError) as exc:
        error_text = str(exc)
    finally:
        capture.release()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if process.stderr is not None:
            error_text = (process.stderr.read() or b"").decode("utf-8", errors="replace") or error_text
        return_code = process.wait()

    if return_code != 0 or written == 0 or not output_path.is_file():
        output_path.unlink(missing_ok=True)
        console.print(f"[yellow]Background cleanup dilewati:[/yellow] {error_text or 'render gagal'}")
        return None, None
    console.print(
        "[green]Background bersih aktif:[/green] "
        f"backdrop teks diganti masjid netral (confidence={profile.confidence:.2f})."
    )
    return output_path, profile


def vertical_crop_filter(video_path: Path, clip: ClipCandidate, crop_mode: CropMode) -> str:
    center_filter = f"{scale_filter(1080, 1920, force_increase=True)},crop=1080:1920,setsar=1"
    if crop_mode == "center":
        return center_filter

    focus = detect_person_focus_x(video_path, clip)
    if focus is None:
        console.print(f"[yellow]No person detected for clip {clip.index}; using center crop.[/yellow]")
        return center_filter

    focus_x, (source_width, source_height) = focus
    scale = max(1080 / source_width, 1920 / source_height)
    scaled_width = make_even(source_width * scale, 1080)
    scaled_height = make_even(source_height * scale, 1920)
    crop_x = clamp_even((focus_x * scaled_width) - 540, 0, scaled_width - 1080)
    crop_y = clamp_even((scaled_height - 1920) / 2, 0, scaled_height - 1920)
    console.print(f"[green]Person crop[/green] clip {clip.index}: focus x={focus_x:.2f}, crop x={crop_x}")
    return f"{scale_filter(scaled_width, scaled_height)},crop=1080:1920:{crop_x}:{crop_y},setsar=1"


def vertical_clean_detail_crop_filter(
    video_path: Path,
    clip: ClipCandidate,
    crop_mode: CropMode,
) -> tuple[str, dict[str, int | str | bool]]:
    """Avoid extreme 9:16 upscaling for low-resolution landscape sources."""
    source_size = get_video_size(video_path)
    if source_size is None:
        return vertical_crop_filter(video_path, clip, crop_mode), {
            "source_resolution_known": False,
            "layout": "full_height_fallback",
        }
    source_width, source_height = source_size
    source_aspect = source_width / max(1, source_height)
    if source_aspect <= 0.82 or source_height >= 1800:
        return vertical_crop_filter(video_path, clip, crop_mode), {
            "source_resolution_known": True,
            "source_width": source_width,
            "source_height": source_height,
            "layout": "full_height_native_detail",
        }

    if source_height < 720:
        panel_height = 1080
    elif source_height < 1080:
        panel_height = 1280
    elif source_height < 1440:
        panel_height = 1440
    else:
        panel_height = 1600
    clean_source_height = source_height if source_height % 2 == 0 else source_height - 1
    crop_width = clamp_even(
        clean_source_height * 1080 / panel_height,
        2,
        source_width,
    )
    focus = detect_person_focus_x(video_path, clip) if crop_mode == "person" else None
    focus_x = focus[0] if focus is not None else 0.5
    crop_x = clamp_even(
        focus_x * source_width - crop_width / 2,
        0,
        source_width - crop_width,
    )
    pad_y = (1920 - panel_height) // 2
    vf = (
        f"crop={crop_width}:{clean_source_height}:{crop_x}:0,"
        f"scale=1080:{panel_height}:flags=lanczos,"
        f"pad=1080:1920:0:{pad_y}:color=#050B0A,setsar=1"
    )
    return vf, {
        "source_resolution_known": True,
        "source_width": source_width,
        "source_height": source_height,
        "layout": "clean_solid_canvas",
        "panel_height": panel_height,
        "crop_width": crop_width,
        "crop_x": crop_x,
        "extreme_upscale_avoided": True,
    }


def embedded_split_subject_filter(
    video_path: Path,
    clip: ClipCandidate,
    profile: EmbeddedSplitProfile,
) -> str:
    """Remove the source banner without turning its speaker into an extreme close-up."""
    source_width = profile.source_width
    source_height = profile.source_height
    subject_height = clamp_even(
        source_height * profile.boundary_ratio,
        2,
        max(2, source_height - 2),
    )
    focus = detect_person_focus_x(video_path, clip)
    focus_x = focus[0] if focus is not None else 0.5
    panel_height = 1180
    scale = max(1080 / max(1, source_width), panel_height / max(1, subject_height))
    scaled_width = make_even(source_width * scale, 1080)
    scaled_height = make_even(subject_height * scale, panel_height)
    crop_x = clamp_even((focus_x * scaled_width) - 540, 0, scaled_width - 1080)
    crop_y = clamp_even((scaled_height - panel_height) / 2, 0, scaled_height - panel_height)
    return (
        f"crop={source_width}:{subject_height}:0:0,"
        "split=2[embedded_bg_src][embedded_fg_src];"
        "[embedded_bg_src]"
        "scale=1080:1320:force_original_aspect_ratio=increase:flags=lanczos,"
        "crop=1080:1320,"
        "gblur=sigma=36:sigmaV=24:steps=3,"
        "eq=brightness=-0.04:saturation=0.78[embedded_bg];"
        "[embedded_fg_src]"
        f"scale={scaled_width}:{scaled_height}:flags=lanczos,"
        f"crop=1080:{panel_height}:{crop_x}:{crop_y},"
        "format=rgba,"
        "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        "a='255*min(1,max(0,(H-Y)/140))',"
        "pad=1080:1320:0:0:color=black@0[embedded_fg];"
        "[embedded_bg][embedded_fg]"
        "overlay=0:0:shortest=1:eof_action=repeat,"
        "pad=1080:1920:0:0:color=#061512,setsar=1"
    )


CamCorner = Literal["br", "bl", "tr", "tl"]
# Vertical canvas is 1080x1920: webcam panel on top, gameplay panel below.
STREAMER_CAM_HEIGHT = 640
STREAMER_GAME_HEIGHT = 1920 - STREAMER_CAM_HEIGHT  # 1280


def get_video_size(video_path: Path) -> tuple[int, int] | None:
    try:
        import cv2
    except Exception:
        return None
    capture = cv2.VideoCapture(str(video_path.resolve()))
    if not capture.isOpened():
        return None
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if width <= 0 or height <= 0:
        return None
    return width, height


def detect_webcam_corner(video_path: Path, clip: ClipCandidate) -> CamCorner | None:
    try:
        import cv2
    except Exception:
        return None

    size = get_video_size(video_path)
    if size is None:
        return None
    width, height = size

    capture = cv2.VideoCapture(str(video_path.resolve()))
    if not capture.isOpened():
        return None
    if not (hasattr(cv2, "cvtColor") and hasattr(cv2, "COLOR_BGR2GRAY")):
        capture.release()
        return None

    face_cascade = make_cv2_cascade(cv2, "haarcascade_frontalface_default.xml")
    if face_cascade is None:
        capture.release()
        return None

    duration = max(0.1, clip.end - clip.start)
    offsets = [duration * frac for frac in (0.2, 0.4, 0.6, 0.8)]
    # Webcam usually occupies ~a third of a corner; weigh faces by which corner they fall in.
    scores: dict[CamCorner, float] = {"br": 0.0, "bl": 0.0, "tr": 0.0, "tl": 0.0}

    for offset in offsets:
        capture.set(cv2.CAP_PROP_POS_MSEC, (clip.start + offset) * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        for x, y, w, h in faces:
            cx = x + w / 2
            cy = y + h / 2
            vertical = "b" if cy > height / 2 else "t"
            horizontal = "r" if cx > width / 2 else "l"
            corner: CamCorner = f"{vertical}{horizontal}"  # type: ignore[assignment]
            scores[corner] += float(w * h)

    capture.release()
    best = max(scores, key=lambda key: scores[key])
    if scores[best] <= 0:
        return None
    return best


def streamer_stack_filter(source_width: int, source_height: int, corner: CamCorner) -> str:
    cam_aspect = 1080 / STREAMER_CAM_HEIGHT
    game_aspect = 1080 / STREAMER_GAME_HEIGHT

    # Webcam crop box from the chosen corner, matched to the top panel aspect.
    cam_w = min(source_width * 0.32, source_height * 0.5 * cam_aspect)
    cam_h = cam_w / cam_aspect
    if cam_h > source_height * 0.5:
        cam_h = source_height * 0.5
        cam_w = cam_h * cam_aspect
    cam_w = clamp_even(cam_w, 16, source_width)
    cam_h = clamp_even(cam_h, 16, source_height)
    cam_x = 0 if corner in ("bl", "tl") else source_width - cam_w
    cam_y = 0 if corner in ("tr", "tl") else source_height - cam_h

    # Gameplay crop centered, matched to the bottom panel aspect.
    game_h = source_height
    game_w = game_h * game_aspect
    if game_w > source_width:
        game_w = source_width
        game_h = game_w / game_aspect
    game_w = clamp_even(game_w, 16, source_width)
    game_h = clamp_even(game_h, 16, source_height)
    game_x = clamp_even((source_width - game_w) / 2, 0, source_width - game_w)
    game_y = clamp_even((source_height - game_h) / 2, 0, source_height - game_h)

    return (
        "split=2[cam][game];"
        f"[cam]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},"
        f"{scale_filter(1080, STREAMER_CAM_HEIGHT, force_increase=True)},"
        f"crop=1080:{STREAMER_CAM_HEIGHT},setsar=1[ctop];"
        f"[game]crop={game_w}:{game_h}:{game_x}:{game_y},"
        f"{scale_filter(1080, STREAMER_GAME_HEIGHT, force_increase=True)},"
        f"crop=1080:{STREAMER_GAME_HEIGHT},setsar=1[gbot];"
        "[ctop][gbot]vstack=inputs=2,setsar=1"
    )


def streamer_crop_filter(video_path: Path, clip: ClipCandidate, cam_corner: str) -> str:
    center_filter = f"{scale_filter(1080, 1920, force_increase=True)},crop=1080:1920,setsar=1"
    size = get_video_size(video_path)
    if size is None:
        console.print(f"[yellow]Streamer layout unavailable for clip {clip.index}; using center crop.[/yellow]")
        return center_filter

    corner: CamCorner | None
    if cam_corner == "auto":
        corner = detect_webcam_corner(video_path, clip)
        if corner is None:
            console.print(f"[yellow]No webcam detected for clip {clip.index}; defaulting to bottom-right.[/yellow]")
            corner = "br"
    else:
        corner = cam_corner  # type: ignore[assignment]

    assert corner is not None
    console.print(f"[green]Streamer stack[/green] clip {clip.index}: cam corner={corner}")
    return streamer_stack_filter(size[0], size[1], corner)


def seconds_to_stamp(seconds: float, srt: bool = False) -> str:
    seconds = max(0, seconds)
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    whole = int(math.floor(seconds))
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    sep = "," if srt else "."
    return f"{h:02}:{m:02}:{s:02}{sep}{millis:03}"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_transcript_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
    for pattern, replacement in TRANSCRIPT_REPLACEMENTS.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def source_branding_reason(text: str) -> str | None:
    """Detect source-channel promos without treating ordinary proper names as branding."""
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    for pattern in SOURCE_BRANDING_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return pattern
    return None


def is_source_branding_segment(segment: TranscriptSegment | str) -> bool:
    text = segment.text if isinstance(segment, TranscriptSegment) else str(segment)
    return source_branding_reason(text) is not None


def fetch_metadata(url: str) -> dict:
    ydl_opts = ytdlp_base_options(skip_download=True)
    try:
        with YoutubeDL(ydl_opts) as ydl:
            return sanitize_metadata(ydl.extract_info(url, download=False))
    except Exception as exc:
        raise UserFacingError(friendly_youtube_error(exc, "membaca metadata")) from exc


def is_creative_commons_metadata(metadata: dict) -> bool:
    license_text = re.sub(r"\s+", " ", str(metadata.get("license") or "")).strip().casefold()
    return bool(
        "creative commons" in license_text
        or "creativecommon" in license_text
        or re.search(r"\bcc[\s-]?by(?:[\s-]\d(?:\.\d)?)?\b", license_text)
    )


def require_creative_commons_metadata(metadata: dict) -> None:
    if is_creative_commons_metadata(metadata):
        return
    license_text = metadata.get("license") or "tidak tersedia"
    raise UserFacingError(
        "Video sumber tidak terdeteksi sebagai Creative Commons. "
        f"Lisensi terdeteksi: {license_text}. "
        "Gunakan video dengan filter Creative Commons agar clipping lebih aman untuk dimodifikasi."
    )


def download_video(
    url: str,
    work_dir: Path,
    force: bool = False,
    video_quality: VideoQuality = "high",
) -> tuple[Path, dict]:
    info_path = work_dir / "metadata.json"
    existing = select_usable_source_media(work_dir)
    if existing is not None and info_path.exists() and not force:
        console.print(f"[green]Reusing verified source:[/green] {existing.name}")
        return existing, load_json(info_path)

    max_height = int(quality_preset(video_quality)["max_download_height"])
    ydl_opts = ytdlp_base_options(
        format=(
            f"bestvideo[height<={max_height}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={max_height}][vcodec^=avc1]+bestaudio/"
            f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        ),
        outtmpl=str(work_dir / "source.%(ext)s"),
        merge_output_format="mp4",
        noprogress=True,
        ffmpeg_location=ffmpeg_path(),
    )

    work_dir.mkdir(parents=True, exist_ok=True)
    info: dict
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        raise UserFacingError(friendly_youtube_error(exc, "mengunduh video")) from exc

    file_path = select_usable_source_media(work_dir)
    if file_path is None:
        console.print(
            "[yellow]Hasil download utama belum memiliki audio lengkap; "
            "mencoba format audio-video kompatibel...[/yellow]"
        )
        fallback_opts = ytdlp_base_options(
            format=(
                f"best[height<={max_height}][vcodec!=none][acodec!=none]/"
                "best[vcodec!=none][acodec!=none]"
            ),
            outtmpl=str(work_dir / "source_fallback.%(ext)s"),
            noprogress=True,
            ffmpeg_location=ffmpeg_path(),
        )
        try:
            with YoutubeDL(fallback_opts) as ydl:
                fallback_info = ydl.extract_info(url, download=True)
                if isinstance(fallback_info, dict):
                    info = fallback_info
        except Exception as exc:
            console.print(f"[yellow]Fallback audio-video gagal:[/yellow] {exc}")
        file_path = select_usable_source_media(work_dir)

    if file_path is None:
        candidates = source_media_candidates(work_dir)
        stream_summary = ", ".join(
            f"{path.name}={'+'.join(sorted(probe_media_stream_types(path))) or 'tidak valid'}"
            for path in candidates
        )
        detail = f" File ditemukan: {stream_summary}." if stream_summary else ""
        raise UserFacingError(
            "Video berhasil diunduh tetapi track audio tidak tersedia atau download belum lengkap."
            f"{detail} Coba jalankan lagi untuk melanjutkan download, atau upload file MP4 yang memiliki audio."
        )

    save_json(info_path, sanitize_metadata(info))
    return file_path, sanitize_metadata(info)


def sanitize_metadata(info: dict) -> dict:
    keys = ["id", "title", "uploader", "duration", "webpage_url", "ext", "license"]
    return {key: info.get(key) for key in keys}


def attach_monetization_provenance(
    exported_paths: list[Path],
    metadata: dict,
    *,
    uploaded_source: bool,
) -> None:
    """Persist rights and originality evidence next to every final render.

    This is an audit aid, not a promise of YPP approval. YouTube evaluates the
    final video and the channel as a whole, while commercial-use rights remain
    the uploader's responsibility for locally supplied files.
    """
    rights_verified = bool(
        not uploaded_source and is_creative_commons_metadata(metadata)
    )
    rights_basis = (
        "user_supplied_file_requires_commercial_rights_confirmation"
        if uploaded_source
        else "creative_commons_attribution"
        if rights_verified
        else "unverified"
    )
    source = {
        "title": str(metadata.get("title") or "").strip(),
        "creator": str(metadata.get("uploader") or "").strip(),
        "url": str(metadata.get("webpage_url") or "").strip(),
        "license": str(metadata.get("license") or "").strip(),
        "rights_basis": rights_basis,
        "rights_verified": rights_verified,
        "attribution_required": rights_verified,
    }
    for video_path in exported_paths:
        sidecar_path = video_path.with_suffix(".json")
        if not sidecar_path.is_file():
            continue
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        applied_edits = payload.get("applied_edits")
        edit_count = len(applied_edits) if isinstance(applied_edits, list) else 0
        output_format = str(payload.get("output_format") or "")
        is_compilation = output_format == "landscape_compilation"
        story_arc = payload.get("story_arc")
        camera_angles = payload.get("virtual_camera_angles")
        emphasis_times = payload.get("emphasis_times")
        reaction_cues = payload.get("reaction_cues")
        sound_effect_cues = payload.get("sound_effect_cues")
        dynamic_captions = payload.get("dynamic_captions")
        edit_signature = payload.get("content_edit_signature")
        auto_visual_plan = payload.get("auto_fyp_visual_plan")
        auto_visual_system = payload.get("auto_fyp_visual_system")
        boundary_quality = str(payload.get("boundary_quality") or "")
        try:
            key_point_score = int(payload.get("key_point_score") or 0)
        except (TypeError, ValueError):
            key_point_score = 0
        content_timed_edits = bool(
            camera_angles or emphasis_times or reaction_cues or sound_effect_cues
        )
        cohesive_editorial_arc = bool(
            payload.get("hook")
            and payload.get("core_message")
            and (
                story_metrics_form_cohesive_editorial_arc(
                    key_point_score,
                    boundary_quality,
                )
                # Backward-compatible evidence for renders made just before the
                # story metrics were persisted into every sidecar.
                or (not boundary_quality and bool(camera_angles))
                or (is_compilation and isinstance(story_arc, list) and len(story_arc) >= 3)
            )
        )
        originality_signals = {
            "editorial_hook_and_context": bool(payload.get("hook") and payload.get("pov")),
            "original_core_message": bool(payload.get("core_message")),
            "cohesive_editorial_arc": cohesive_editorial_arc,
            "substantive_visual_edits": edit_count >= 3 and content_timed_edits,
            "transcript_timed_camera_direction": bool(camera_angles),
            "content_timed_editing": content_timed_edits,
            "dynamic_keyword_captions": bool(
                isinstance(dynamic_captions, dict) and dynamic_captions.get("enabled")
            ),
            "content_derived_visual_variation": bool(
                isinstance(edit_signature, dict)
                and edit_signature.get("derived_from_story")
            ),
            "content_adaptive_visual_direction": bool(
                (
                    isinstance(auto_visual_plan, dict)
                    and auto_visual_plan.get("content_derived")
                )
                or (
                    isinstance(auto_visual_system, dict)
                    and auto_visual_system.get("chapter_accents_are_content_derived")
                )
            ),
            "structured_story_arc": bool(
                is_compilation and isinstance(story_arc, list) and len(story_arc) >= 3
            ),
            "custom_thumbnail_strategy": bool(payload.get("thumbnail_strategy")),
            "enhanced_edit": bool(payload.get("enhanced_edit")),
        }
        originality_score = sum(bool(value) for value in originality_signals.values())
        minimum_score = 5 if is_compilation else 6
        substantive_transformation = originality_signals["substantive_visual_edits"] or bool(
            is_compilation
            and originality_signals["structured_story_arc"]
            and originality_signals["editorial_hook_and_context"]
            and originality_signals["original_core_message"]
        )
        transformation_ready = (
            originality_signals["enhanced_edit"]
            and originality_signals["editorial_hook_and_context"]
            and originality_signals["original_core_message"]
            and originality_signals["cohesive_editorial_arc"]
            and originality_signals["content_adaptive_visual_direction"]
            and substantive_transformation
            and originality_score >= minimum_score
        )
        commercial_rights_ready = rights_verified or uploaded_source
        payload["source_provenance"] = source
        payload["monetization_readiness"] = {
            "status": (
                "ready_for_private_upload_review"
                if commercial_rights_ready and transformation_ready
                else "needs_more_original_transformation"
                if commercial_rights_ready
                else "blocked_unverified_rights"
            ),
            "eligible_for_private_upload_review": bool(
                commercial_rights_ready and transformation_ready
            ),
            "commercial_rights_confirmation_required": uploaded_source,
            "originality_score": originality_score,
            "minimum_originality_score": minimum_score,
            "audit_version": 4,
            "signals": originality_signals,
            "substantive_transformation": substantive_transformation,
            "original_creator_commentary_present": bool(
                payload.get("original_creator_commentary")
            ),
            "note": (
                "Lolos audit teknis untuk review Private, bukan jaminan YPP. "
                "Komentar/kehadiran kreator asli tetap merupakan bukti transformasi terkuat."
            ),
            "channel_level_review_still_applies": True,
            "youtube_policy_reviewed_on": SHORTS_POLICY_REVIEW_DATE,
            "inauthentic_content_policy": {
                "mass_produced_or_repetitive_content_ineligible": True,
                "content_specific_story_and_visual_direction_required": True,
                "reused_content_policy_separately_applies": True,
                "channel_wide_manual_review_still_applies": True,
            },
            "guarantee": False,
        }
        save_json(sidecar_path, payload)


def extract_audio(video_path: Path, audio_path: Path, force: bool = False, limit_seconds: float | None = None) -> Path:
    if audio_path.exists() and not force and "audio" in probe_media_stream_types(audio_path):
        return audio_path
    if audio_path.exists():
        audio_path.unlink(missing_ok=True)
    if "audio" not in probe_media_stream_types(video_path):
        raise UserFacingError(
            f"Video sumber {video_path.name} tidak memiliki track audio yang dapat dibaca. "
            "Download otomatis sudah mencoba format cadangan; coba ulangi job atau upload video yang memiliki suara."
        )

    audio_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        "highpass=f=65,lowpass=f=7800,dynaudnorm=f=250:g=7:p=0.90:m=6",
        "-c:a",
        "pcm_s16le",
    ]
    if limit_seconds:
        command.extend(["-t", f"{limit_seconds:.3f}"])
    command.append(str(audio_path))
    try:
        run(command)
    except RuntimeError as exc:
        audio_path.unlink(missing_ok=True)
        raise UserFacingError(
            "Audio video tidak dapat diekstrak. Coba ulangi job agar sumber diunduh kembali, "
            "atau upload file MP4 dengan track audio AAC."
        ) from exc
    if "audio" not in probe_media_stream_types(audio_path):
        audio_path.unlink(missing_ok=True)
        raise UserFacingError("Hasil ekstraksi audio kosong atau rusak; proses dihentikan sebelum transkripsi.")
    return audio_path


def transcription_decode_options(language: str) -> dict:
    """Accuracy-first Whisper settings for clear Indonesian speech and names."""
    options: dict = {
        "language": language,
        "task": "transcribe",
        "vad_filter": True,
        "vad_parameters": {
            "threshold": 0.45,
            "min_speech_duration_ms": 250,
            "max_speech_duration_s": 30,
            "min_silence_duration_ms": 450,
            "speech_pad_ms": 250,
        },
        "beam_size": 5,
        "best_of": 5,
        "patience": 1.2,
        "temperature": 0.0,
        "word_timestamps": True,
        "condition_on_previous_text": True,
        "compression_ratio_threshold": 2.4,
        "no_speech_threshold": 0.55,
        "hallucination_silence_threshold": 1.5,
        "initial_prompt": (
            "Transkripsi percakapan bahasa Indonesia. Pertahankan nama orang, istilah asing, "
            "angka, dan istilah agama sesuai ucapan. Gunakan ejaan serta tanda baca baku; "
            "jangan menambah kata yang tidak diucapkan."
        ),
    }
    hotwords = os.environ.get("FENDY_CLIPPER_TRANSCRIPTION_HOTWORDS", "").strip()
    if hotwords:
        options["hotwords"] = hotwords
    return options


def configure_huggingface_environment() -> bool:
    """Normalize optional Hub auth and keep public-model downloads quiet.

    `huggingface_hub` reads authentication from the process environment. Older
    deployments may still use HUGGING_FACE_HUB_TOKEN, so mirror either name to
    both without ever printing the token. Public models remain usable when no
    token is configured; persistent HF_HOME is supplied by Docker Compose.
    """
    token = (
        os.environ.get("HF_TOKEN", "").strip()
        or os.environ.get("HUGGING_FACE_HUB_TOKEN", "").strip()
    )
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    return bool(token)


def transcript_cache_metadata_path(transcript_path: Path) -> Path:
    return transcript_path.with_name(f"{transcript_path.stem}.meta.json")


def transcript_cache_matches(transcript_path: Path, model_name: str, language: str) -> bool:
    meta_path = transcript_cache_metadata_path(transcript_path)
    if not transcript_path.exists() or not meta_path.exists():
        return False
    try:
        metadata = load_json(meta_path)
    except (OSError, ValueError, TypeError):
        return False
    return (
        metadata.get("version") == TRANSCRIPTION_CACHE_VERSION
        and metadata.get("model") == model_name
        and metadata.get("language") == language
    )


def transcribe(audio_path: Path, transcript_path: Path, model_name: str, language: str, force: bool = False) -> list[TranscriptSegment]:
    if not force and transcript_cache_matches(transcript_path, model_name, language):
        return [
            TranscriptSegment(
                start=float(item["start"]),
                end=float(item["end"]),
                text=clean_transcript_text(item["text"]),
            )
            for item in load_json(transcript_path)
        ]

    hub_authenticated = configure_huggingface_environment()
    from faster_whisper import WhisperModel

    console.print(f"[bold]Loading model:[/bold] {model_name}")
    console.print(
        "[dim]Hugging Face: token aktif + cache persisten.[/dim]"
        if hub_authenticated
        else "[dim]Hugging Face: model publik + cache persisten (HF_TOKEN opsional).[/dim]"
    )
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio_path), **transcription_decode_options(language))

    rows: list[TranscriptSegment] = []
    for segment in segments:
        text = clean_transcript_text(segment.text)
        if text:
            rows.append(TranscriptSegment(float(segment.start), float(segment.end), text))

    save_json(transcript_path, [asdict(item) for item in rows])
    save_json(
        transcript_cache_metadata_path(transcript_path),
        {
            "version": TRANSCRIPTION_CACHE_VERSION,
            "model": model_name,
            "language": language,
            "decode": "accuracy_first_beam_5",
        },
    )
    console.print(f"[green]Transcribed[/green] {len(rows)} segments. Detected language: {getattr(info, 'language', language)}")
    return rows


def first_sentence(text: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .,!?:;-")
    words = cleaned.split()
    return " ".join(words[:max_words]).capitalize() or "Auto clip"


def fyp_score_label(score: int) -> str:
    if score >= 88:
        return "Sangat kuat"
    if score >= 78:
        return "Kuat"
    if score >= 65:
        return "Menjanjikan"
    if score >= 50:
        return "Perlu dipoles"
    return "Lemah"


def fallback_pov_angle(text: str) -> str:
    lowered = text.lower()
    if set(re.findall(r"[\w']+", lowered)).intersection(MYSTERY_WORDS):
        return "Kamu ikut membongkar cerita ini sampai fakta dan hikmahnya terlihat."
    if set(re.findall(r"[\w']+", lowered)).intersection(ISLAMIC_WORDS):
        return "Kamu sedang diajak melihat masalah ini dari sisi hikmah dan kehati-hatian."
    if set(re.findall(r"[\w']+", lowered)).intersection(TENSION_WORDS):
        return "Kamu baru sadar ada risiko yang selama ini sering dianggap sepele."
    if "?" in text:
        return "Kamu punya pertanyaan yang sama dan ingin tahu jawaban akhirnya."
    return "Kamu menemukan satu sudut pandang yang bisa langsung dipakai atau direnungkan."


def strongest_advice_line(items: list[TranscriptSegment]) -> str:
    """Pick a compact transcript line that can anchor a concrete edit suggestion."""
    signal_words = HOOK_WORDS | TENSION_WORDS | MYSTERY_WORDS | PAYOFF_WORDS | IMPORTANT_WORDS

    def line_score(item: TranscriptSegment) -> tuple[int, int]:
        words = re.findall(r"[\w']+", item.text.lower())
        signals = len(set(words).intersection(signal_words))
        return signals * 5 + int("?" in item.text) * 3, min(len(words), 14)

    strongest = max(items, key=line_score, default=None)
    return first_sentence(strongest.text, max_words=10) if strongest else ""


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[\w']+", text.casefold())
        if len(word) >= 4 and word not in LOOP_STOP_WORDS
    }


def candidate_story_metrics(items: list[TranscriptSegment], duration: float) -> dict[str, int | bool | str]:
    """Measure whether a window contains one useful idea and a deliberate loop point."""
    if not items:
        return {
            "key_point_score": 0,
            "loop_score": 0,
            "boundary_quality": "lemah",
            "payoff_near_end": False,
            "complete_ending": False,
        }

    start = items[0].start
    end = items[-1].end
    text = " ".join(item.text for item in items).strip()
    opening = " ".join(item.text for item in items if item.start < start + 4.5).strip()
    closing_span = max(7.0, min(12.0, duration * 0.25))
    closing = " ".join(item.text for item in items if item.end > end - closing_span).strip()
    all_words = set(re.findall(r"[\w']+", text.casefold()))
    closing_words = set(re.findall(r"[\w']+", closing.casefold()))
    opening_words = set(re.findall(r"[\w']+", opening.casefold()))
    signal_words = HOOK_WORDS | TENSION_WORDS | PAYOFF_WORDS | IMPORTANT_WORDS
    signal_hits = all_words.intersection(signal_words)
    payoff_near_end = bool(closing_words.intersection(PAYOFF_WORDS | IMPORTANT_WORDS))
    complete_ending = text.rstrip().endswith((".", "!", "?"))
    opening_hook = bool(
        opening_words.intersection((HOOK_WORDS - WEAK_STARTS) | TENSION_WORDS)
        or "?" in opening
    )
    filler_hits = sum(phrase in text.casefold() for phrase in FILLER_PHRASES)
    word_count = len(re.findall(r"[\w']+", text))
    density = word_count / max(1.0, duration)

    key_point_score = 18
    key_point_score += min(30, len(signal_hits) * 5)
    key_point_score += 12 if opening_hook else 0
    key_point_score += 15 if payoff_near_end else 0
    key_point_score += 8 if re.search(r"\b\d+(?:[.,]\d+)?\b", text) else 0
    key_point_score += 7 if "?" in text else 0
    key_point_score += 8 if density >= 1.25 else 3 if density >= 0.9 else -8
    key_point_score -= filler_hits * 12
    if not complete_ending:
        key_point_score -= 10

    opening_concepts = _content_words(opening)
    closing_concepts = _content_words(closing)
    concept_overlap = opening_concepts.intersection(closing_concepts)
    question_to_payoff = "?" in opening and payoff_near_end
    hook_to_payoff = opening_hook and payoff_near_end
    loop_score = min(45, len(concept_overlap) * 15)
    loop_score += 35 if question_to_payoff else 20 if hook_to_payoff else 0
    loop_score += 12 if complete_ending else -12
    if not opening_concepts:
        loop_score -= 10

    boundary_quality = (
        "payoff_tuntas"
        if complete_ending and payoff_near_end
        else "kalimat_tuntas"
        if complete_ending
        else "menggantung"
    )
    return {
        "key_point_score": max(0, min(100, round(key_point_score))),
        "loop_score": max(0, min(100, round(loop_score))),
        "boundary_quality": boundary_quality,
        "payoff_near_end": payoff_near_end,
        "complete_ending": complete_ending,
    }


def is_meaningful_candidate_end(
    window: list[TranscriptSegment],
    *,
    end_idx: int,
    segments: list[TranscriptSegment],
    branding_flags: list[bool],
    max_duration: float,
) -> bool:
    """Avoid emitting arbitrary cuts in the middle of a thought."""
    last = window[-1]
    last_words = set(re.findall(r"[\w']+", last.text.casefold()))
    natural_sentence = last.text.rstrip().endswith((".", "!", "?"))
    explicit_resolution = bool(last_words.intersection(PAYOFF_WORDS | IMPORTANT_WORDS))
    is_last = end_idx + 1 >= len(segments)
    next_is_boundary = not is_last and branding_flags[end_idx + 1]
    next_exceeds_limit = (
        not is_last
        and segments[end_idx + 1].end - window[0].start > max_duration
    )
    return natural_sentence or explicit_resolution or is_last or next_is_boundary or next_exceeds_limit


def candidate_fyp_analysis(
    items: list[TranscriptSegment],
    duration: float,
    score: int,
) -> dict[str, str | list[str]]:
    """Explain the score using the opening hook, first 30 seconds, value, and payoff."""
    text = " ".join(item.text for item in items).strip()
    window_start = items[0].start if items else 0.0
    opening_text = " ".join(
        item.text for item in items if item.start < window_start + 3.5
    ).strip()
    first_30_text = " ".join(
        item.text for item in items if item.start < window_start + 30.0
    ).strip()
    opening_words = set(re.findall(r"[\w']+", opening_text.lower()))
    first_30_words = re.findall(r"[\w']+", first_30_text.lower())
    all_words = set(re.findall(r"[\w']+", text.lower()))
    strong_hook_words = HOOK_WORDS - WEAK_STARTS
    opening_has_hook = bool(
        opening_words.intersection(strong_hook_words | TENSION_WORDS | MYSTERY_WORDS)
        or "?" in opening_text
    )
    first_30_signals = {
        "hook": bool(set(first_30_words).intersection(strong_hook_words)),
        "tension": bool(set(first_30_words).intersection(TENSION_WORDS | MYSTERY_WORDS)),
        "payoff": bool(set(first_30_words).intersection(PAYOFF_WORDS)),
        "value": bool(set(first_30_words).intersection(IMPORTANT_WORDS)),
    }
    first_30_density = len(first_30_words) / max(1.0, min(duration, 30.0))
    has_payoff = bool(all_words.intersection(PAYOFF_WORDS))
    has_question = "?" in text
    complete_ending = text.rstrip().endswith((".", "!", "?"))
    story_metrics = candidate_story_metrics(items, duration)
    strongest_line = strongest_advice_line(items)
    hook_reference = first_sentence(opening_text or text, max_words=6)
    if not opening_has_hook and strongest_line:
        hook_reference = strongest_line

    strengths: list[str] = []
    weaknesses: list[str] = []
    ideas: list[str] = []

    if opening_has_hook:
        strengths.append("3 detik awal punya pemicu rasa penasaran")
    else:
        weaknesses.append("3 detik awal belum cukup menghentikan scroll")
        if strongest_line:
            ideas.append(
                f'Hook — pindahkan potongan terkuat “{strongest_line}” ke 3 detik pertama, '
                "baru beri konteks."
            )
        else:
            ideas.append("Hook — buka langsung dengan konflik atau fakta utama sebelum konteks.")

    active_first_30_signals = sum(first_30_signals.values())
    if active_first_30_signals >= 3:
        strengths.append("30 detik awal berisi hook, konflik/value, dan arah payoff")
    elif active_first_30_signals >= 2:
        strengths.append("30 detik awal cukup padat dan memiliki arah cerita")

    if first_30_density >= 1.6:
        strengths.append("tempo bicara padat untuk short-form")
    if active_first_30_signals < 2 and first_30_density < 0.9:
        weaknesses.append("alur 30 detik awal masih datar dan tempo informasinya lambat")
    elif active_first_30_signals < 2:
        weaknesses.append("alur 30 detik awal masih datar atau terlalu lama membangun konteks")
    elif first_30_density < 0.9:
        weaknesses.append("tempo informasi awal berisiko terasa lambat")
    if active_first_30_signals < 2 and first_30_density < 0.9:
        ideas.append(
            "Ritme — pangkas jeda dan konteks berulang; susun 30 detik awal menjadi "
            "hook → konflik → janji jawaban."
        )
    elif active_first_30_signals < 2:
        ideas.append(
            "Alur — ringkas konteks awal dan munculkan konflik serta janji jawaban "
            "sebelum detik ke-10."
        )
    elif first_30_density < 0.9:
        ideas.append(
            "Tempo — buang jeda dan pengulangan agar setiap 5–8 detik membawa satu informasi baru."
        )

    if has_payoff and complete_ending:
        strengths.append("memiliki payoff atau kesimpulan yang bisa ditunggu")
    elif not has_payoff and not complete_ending:
        weaknesses.append("payoff dan ending belum terasa tuntas")
    else:
        weaknesses.append(
            "payoff akhir belum terasa tegas"
            if not has_payoff
            else "ending terasa menggantung tanpa penutup yang disengaja"
        )

    if has_question:
        strengths.append("memancing penonton ikut menjawab")
    if not has_payoff or not complete_ending:
        callback = (
            f', lalu sebut kembali inti hook “{hook_reference}”'
            if hook_reference
            else ""
        )
        ideas.append(
            "Ending — sisakan jawaban atau pelajaran paling tegas sebagai kalimat terakhir"
            f"{callback}."
        )
    elif int(story_metrics["loop_score"]) >= 45:
        strengths.append("payoff terhubung kembali ke hook dan punya titik loop alami")
    else:
        ideas.append(
            f'Loop — akhiri pada jawaban yang kembali ke pertanyaan “{hook_reference}”; '
            "jangan paksa callback jika maknanya tidak nyambung."
        )

    if not ideas:
        visual_anchor = strongest_line or hook_reference
        ideas.append(
            f'Visual — pertahankan struktur; beri pattern interrupt saat “{visual_anchor}” '
            "agar poin utama lebih menempel."
        )

    return {
        "hook": first_sentence(opening_text or text, max_words=8),
        "pov": fallback_pov_angle(first_30_text or text),
        "fyp_label": fyp_score_label(score),
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:3],
        "improvement_ideas": ideas[:3],
    }


def score_window(items: list[TranscriptSegment], duration: float) -> tuple[int, list[str]]:
    text = " ".join(item.text for item in items)
    words = re.findall(r"[\w']+", text.lower())
    first_word = words[0] if words else ""
    window_start = items[0].start if items else 0.0
    opening_text = " ".join(
        item.text for item in items if item.start < window_start + 3.5
    )
    first_30_text = " ".join(
        item.text for item in items if item.start < window_start + 30.0
    )
    opening_words = set(re.findall(r"[\w']+", opening_text.lower()))
    first_30_words = re.findall(r"[\w']+", first_30_text.lower())
    hook_hits = sorted(HOOK_WORDS.intersection(words))
    payoff_hits = sorted(PAYOFF_WORDS.intersection(words))
    tension_hits = sorted(TENSION_WORDS.intersection(words))
    mystery_hits = sorted(MYSTERY_WORDS.intersection(words))
    islamic_hits = sorted(ISLAMIC_WORDS.intersection(words))
    laugh_hits = sorted(LAUGH_WORDS.intersection(words))
    has_laughter = bool(
        laugh_hits
        or re.search(r"(?:^|\W)(?:ha){2,}(?:\W|$)|w+k+w+k+|he(?:he)+", text.lower())
    )

    score = 24
    reasons: list[str] = []

    if 28 <= duration <= 60:
        score += 18
        reasons.append("durasi pas")
    elif 15 <= duration <= 75:
        score += 12
        reasons.append("durasi masih oke")

    if hook_hits:
        bump = min(18, len(hook_hits) * 5)
        score += bump
        reasons.append("ada keyword hook: " + ", ".join(hook_hits[:4]))

    if tension_hits:
        score += min(14, len(tension_hits) * 4)
        reasons.append("ada konflik/tension: " + ", ".join(tension_hits[:3]))

    if payoff_hits:
        score += min(12, len(payoff_hits) * 4)
        reasons.append("ada payoff: " + ", ".join(payoff_hits[:3]))

    if mystery_hits:
        score += min(10, len(mystery_hits) * 3)
        reasons.append("punya unsur misteri: " + ", ".join(mystery_hits[:3]))

    if islamic_hits:
        score += min(8, len(islamic_hits) * 2)
        reasons.append("punya konteks Islami: " + ", ".join(islamic_hits[:3]))

    if mystery_hits and islamic_hits:
        score += 5
        reasons.append("misteri tetap terhubung dengan hikmah Islami")

    if has_laughter:
        score += 10
        reasons.append("punya momen humor/tertawa yang natural")

    if "?" in text:
        score += 7
        reasons.append("memancing rasa penasaran")

    if re.search(r"\b\d+(?:[.,]\d+)?\b", text):
        score += 5
        reasons.append("ada angka konkret")

    word_count = len(words)
    density = word_count / max(duration, 1)
    if density >= 1.8:
        score += 12
        reasons.append("speech padat")
    elif density >= 1.1:
        score += 6
        reasons.append("speech cukup padat")

    if text.rstrip().endswith((".", "!", "?")):
        score += 5
        reasons.append("ending terasa selesai")

    if first_word in WEAK_STARTS:
        score -= 10
        reasons.append("awal agak menggantung")

    opening_has_hook = bool(
        opening_words.intersection((HOOK_WORDS - WEAK_STARTS) | TENSION_WORDS | MYSTERY_WORDS)
        or "?" in opening_text
    )
    if opening_has_hook:
        score += 12
        reasons.append("hook 3 detik awal kuat")
    else:
        score -= 8
        reasons.append("hook 3 detik awal perlu diperkuat")

    first_30_set = set(first_30_words)
    first_30_signal_count = sum(
        (
            bool(first_30_set.intersection(HOOK_WORDS - WEAK_STARTS)),
            bool(first_30_set.intersection(TENSION_WORDS | MYSTERY_WORDS)),
            bool(first_30_set.intersection(PAYOFF_WORDS)),
            bool(first_30_set.intersection(IMPORTANT_WORDS)),
        )
    )
    first_30_density = len(first_30_words) / max(1.0, min(duration, 30.0))
    if first_30_signal_count >= 3:
        score += 10
        reasons.append("alur 30 detik awal kuat")
    elif first_30_signal_count >= 2:
        score += 5
        reasons.append("alur 30 detik awal cukup")
    else:
        score -= 6
        reasons.append("30 detik awal masih datar")
    if first_30_density >= 1.6:
        score += 5
        reasons.append("tempo awal padat")
    elif first_30_density < 0.9:
        score -= 5
        reasons.append("tempo awal lambat")

    story_metrics = candidate_story_metrics(items, duration)
    key_point_score = int(story_metrics["key_point_score"])
    loop_score = int(story_metrics["loop_score"])
    if key_point_score >= 75:
        score += 8
        reasons.append("satu point penting terbentuk jelas")
    elif key_point_score < 40:
        score -= 14
        reasons.append("point utama belum cukup jelas")
    if story_metrics["payoff_near_end"]:
        score += 10
        reasons.append("payoff ditempatkan dekat ending")
    elif payoff_hits:
        score -= 4
        reasons.append("payoff muncul terlalu awal lalu melebar")
    if loop_score >= 45:
        score += 5
        reasons.append("hook dan payoff membentuk loop semantik")

    if word_count < 55:
        score -= 12
        reasons.append("terlalu sedikit konteks")

    return max(1, min(100, score)), reasons


def build_candidate_pool(
    segments: list[TranscriptSegment],
    min_duration: float,
    max_duration: float,
) -> list[ClipCandidate]:
    candidates: list[ClipCandidate] = []
    if not segments:
        return candidates

    branding_flags = [is_source_branding_segment(item) for item in segments]
    for start_idx, first in enumerate(segments):
        if branding_flags[start_idx]:
            continue
        window: list[TranscriptSegment] = []
        for end_idx in range(start_idx, len(segments)):
            if branding_flags[end_idx]:
                break
            item = segments[end_idx]
            window.append(item)
            duration = window[-1].end - first.start
            if duration < min_duration:
                continue
            if duration > max_duration:
                break
            if not is_meaningful_candidate_end(
                window,
                end_idx=end_idx,
                segments=segments,
                branding_flags=branding_flags,
                max_duration=max_duration,
            ):
                continue

            text = " ".join(part.text for part in window)
            score, reasons = score_window(window, duration)
            story_metrics = candidate_story_metrics(window, duration)
            fyp_analysis = candidate_fyp_analysis(window, duration, score)
            previous_is_branding = start_idx > 0 and branding_flags[start_idx - 1]
            next_is_branding = end_idx + 1 < len(segments) and branding_flags[end_idx + 1]
            # Whisper timestamps can bleed a few frames across segment edges.
            # Keep a small inward guard around removed promos so their audio tail
            # cannot leak into an otherwise clean export.
            safe_start = first.start + (0.45 if previous_is_branding else -0.35)
            safe_end = window[-1].end - (0.35 if next_is_branding else -0.25)
            safe_start = max(0, safe_start)
            safe_end = max(safe_start + 0.2, safe_end)
            safe_end = min(safe_end, safe_start + max_duration)
            candidates.append(
                ClipCandidate(
                    index=0,
                    start=safe_start,
                    end=safe_end,
                    duration=safe_end - safe_start,
                    score=score,
                    title=first_sentence(text),
                    reason=", ".join(reasons) or "segmen stabil",
                    text=text,
                    hook=str(fyp_analysis["hook"]),
                    pov=str(fyp_analysis["pov"]),
                    fyp_label=str(fyp_analysis["fyp_label"]),
                    strengths=list(fyp_analysis["strengths"]),
                    weaknesses=list(fyp_analysis["weaknesses"]),
                    improvement_ideas=list(fyp_analysis["improvement_ideas"]),
                    key_point_score=int(story_metrics["key_point_score"]),
                    loop_score=int(story_metrics["loop_score"]),
                    boundary_quality=str(story_metrics["boundary_quality"]),
                )
            )
    return candidates


def candidate_topic_similarity(left: ClipCandidate, right: ClipCandidate) -> float:
    left_words = _content_words(left.text)
    right_words = _content_words(right.text)
    if not left_words or not right_words:
        return 0.0
    return len(left_words.intersection(right_words)) / len(left_words.union(right_words))


def candidate_rank_score(candidate: ClipCandidate, target_duration: float = 38.0) -> float:
    return (
        candidate.score
        + candidate.key_point_score * 0.10
        + candidate.loop_score * 0.05
        - abs(candidate.duration - target_duration) * 0.05
    )


COHESIVE_EDITORIAL_MIN_KEY_POINT_SCORE = 55


def story_metrics_form_cohesive_editorial_arc(
    key_point_score: int,
    boundary_quality: str,
) -> bool:
    """Keep render selection and upload-readiness story rules in sync."""
    return bool(
        key_point_score >= COHESIVE_EDITORIAL_MIN_KEY_POINT_SCORE
        and boundary_quality != "menggantung"
    )


def candidate_has_cohesive_editorial_arc(candidate: ClipCandidate) -> bool:
    return story_metrics_form_cohesive_editorial_arc(
        candidate.key_point_score,
        candidate.boundary_quality,
    )


def select_candidates(candidates: list[ClipCandidate], limit: int) -> list[ClipCandidate]:
    # A rendered short is advertised as ready to post, so do not select a
    # candidate that the monetization preflight will inevitably reject later.
    candidates = [item for item in candidates if candidate_has_cohesive_editorial_arc(item)]
    target_duration = 38
    candidates.sort(
        key=lambda item: candidate_rank_score(item, target_duration),
        reverse=True,
    )
    picked: list[ClipCandidate] = []
    remaining = candidates[:]
    while remaining and len(picked) < limit:
        best: ClipCandidate | None = None
        best_adjusted = -1_000.0
        for candidate in remaining:
            overlaps = any(not (candidate.end <= item.start or candidate.start >= item.end) for item in picked)
            if overlaps:
                continue
            max_topic_similarity = max(
                (candidate_topic_similarity(candidate, item) for item in picked),
                default=0.0,
            )
            if max_topic_similarity >= 0.64:
                continue
            diversity_bonus = 5.0 if picked and max_topic_similarity < 0.22 else 0.0
            adjusted = candidate_rank_score(candidate, target_duration) + diversity_bonus
            if adjusted > best_adjusted:
                best = candidate
                best_adjusted = adjusted

        if best is None:
            # Diversity is preferred, but it must not silently reduce an
            # explicit clip target when enough non-overlapping moments exist.
            best = next(
                (
                    candidate
                    for candidate in remaining
                    if not any(
                        not (candidate.end <= item.start or candidate.start >= item.end)
                        for item in picked
                    )
                ),
                None,
            )
            if best is None:
                break
        best.index = len(picked) + 1
        picked.append(best)
        remaining.remove(best)

    picked.sort(key=lambda item: item.start)
    for idx, candidate in enumerate(picked, start=1):
        candidate.index = idx
    return picked


def select_compilation_candidates(
    candidates: list[ClipCandidate],
    target_duration: float = 300,
    max_parts: int | None = None,
) -> list[ClipCandidate]:
    """Build a dense chronological story resume with coverage across the source."""
    if target_duration <= 0:
        return []

    if max_parts is None:
        # A ten-minute resume may need more than twelve short story beats.
        max_parts = min(24, max(12, math.ceil(target_duration / 30)))

    remaining = candidates[:]
    remaining.sort(
        key=lambda item: (
            item.score - abs(item.duration - 60) * 0.05,
            -item.start,
        ),
        reverse=True,
    )
    picked: list[ClipCandidate] = []
    total = 0.0

    def fit_to_remaining(candidate: ClipCandidate, seconds_left: float) -> ClipCandidate:
        if candidate.end - candidate.start <= seconds_left:
            return candidate
        return ClipCandidate(
            index=candidate.index,
            start=candidate.start,
            end=candidate.start + seconds_left,
            duration=seconds_left,
            score=candidate.score,
            title=candidate.title,
            reason=candidate.reason,
            text=candidate.text,
            hook=candidate.hook,
            pov=candidate.pov,
            fyp_label=candidate.fyp_label,
            strengths=list(candidate.strengths),
            weaknesses=list(candidate.weaknesses),
            improvement_ideas=list(candidate.improvement_ideas),
            applied_edits=list(candidate.applied_edits),
            key_point_score=candidate.key_point_score,
            loop_score=candidate.loop_score,
            boundary_quality=candidate.boundary_quality,
        )

    # Seed the resume with a strong, non-overlapping beat from each source
    # phase. This keeps a whole-video resume from clustering in one chapter.
    if remaining:
        source_start = min(item.start for item in remaining)
        source_end = max(item.end for item in remaining)
        source_span = max(1.0, source_end - source_start)
        for phase_index in range(4):
            phase_start = source_start + source_span * phase_index / 4
            phase_end = source_start + source_span * (phase_index + 1) / 4
            phase = [
                item
                for item in remaining
                if phase_start <= (item.start + item.end) * 0.5 <= phase_end
                and not any(
                    not (item.end <= chosen.start or item.start >= chosen.end)
                    for chosen in picked
                )
            ]
            if not phase:
                continue
            best_phase = max(
                phase,
                key=lambda item: item.score - abs(item.duration - 60) * 0.05,
            )
            seconds_left = target_duration - total
            if seconds_left < 8:
                break
            picked.append(fit_to_remaining(best_phase, seconds_left))
            remaining.remove(best_phase)
            total += picked[-1].end - picked[-1].start
            if total >= target_duration or len(picked) >= max_parts:
                break

    while remaining and len(picked) < max_parts and total < target_duration:
        best: ClipCandidate | None = None
        best_adjusted = -1_000.0
        for candidate in remaining:
            if any(not (candidate.end <= item.start or candidate.start >= item.end) for item in picked):
                continue
            # Favor concise, high-scoring sections so the final five minutes stay dense.
            adjusted = candidate.score - abs(candidate.duration - 60) * 0.05
            if adjusted > best_adjusted:
                best = candidate
                best_adjusted = adjusted

        if best is None:
            break
        remaining.remove(best)

        seconds_left = target_duration - total
        if seconds_left < 8:
            break
        best = fit_to_remaining(best, seconds_left)
        picked.append(best)
        total += best.end - best.start

    picked.sort(key=lambda item: item.start)
    for idx, candidate in enumerate(picked, start=1):
        candidate.index = idx
    return picked


def order_compilation_for_retention(
    candidates: list[ClipCandidate],
) -> list[ClipCandidate]:
    """Lead with the strongest promise, then restore the remaining source arc."""
    if len(candidates) < 2:
        return list(candidates)
    strongest = max(
        candidates,
        key=lambda item: (
            item.score,
            item.key_point_score,
            item.boundary_quality,
            -item.start,
        ),
    )
    remaining = sorted(
        (item for item in candidates if item is not strongest),
        key=lambda item: item.start,
    )
    return [strongest, *remaining]


def select_output_candidates(
    candidates: list[ClipCandidate],
    *,
    clip_mode: Literal["short", "highlight_5m"],
    short_limit: int,
    compilation_target: float = 300,
) -> tuple[list[ClipCandidate], list[ClipCandidate]]:
    """Keep short and compilation renders mutually exclusive."""
    pool = [ClipCandidate(**asdict(item)) for item in candidates]
    if clip_mode == "highlight_5m":
        compilation = select_compilation_candidates(pool, compilation_target)
        return compilation, compilation
    return select_candidates(pool, short_limit), []


AI_RESCORE_POOL_LIMIT = 40
AI_SYSTEM_PROMPT = (
    "You are an expert Indonesian short-form video editor for TikTok FYP, Reels, and YouTube Shorts. "
    "Your job is to choose the strongest POV moments from transcript windows, not to divide the video evenly. "
    "Prioritize clips with a strong first-3-second hook, open loop, tension or controversy, practical value, "
    "surprising/emotional payoff, and self-contained meaning. A clip must contain one identifiable key point; "
    "its end must land after the answer/payoff on a complete sentence, not at an arbitrary duration. Only call "
    "something a loop when the ending semantically answers or reconnects to the opening. Penalize intros, outros, "
    "filler, repeated ideas, generic motivation, and clips that need earlier context. Islamic insight, mystery, myth-versus-fact, "
    "history, supernatural stories, and relevant horror are valuable niches when genuinely present in the "
    "transcript. Authentic humor, witty answers, and naturally funny reactions are also high-value retention "
    "moments. For evergreen Islamic content, apply these editorial lenses when the transcript supports them: "
    "mental-health clips must feel empathetic and calming, connect a relatable modern struggle to a practical "
    "Islamic principle, never diagnose the viewer, promise healing, or replace professional help; halal-wealth "
    "clips must explain riba, clean income, finance, or career ethics in plain language with one usable takeaway, "
    "without guaranteed returns or personalized financial claims; current-issue clips must distinguish verified "
    "events, speaker opinion, and unresolved claims without inventing accusations; daily-fiqh clips must isolate one correctable "
    "worship detail and preserve the speaker's evidence without inventing rulings; Islamic-history clips must "
    "build an accurate premise-conflict-payoff arc with an explicit lesson for life today. Prefer a specific "
    "problem, correction, contrast, or transformation over generic preaching. "
    "Reject source-channel intros, outros, credits, sponsor mentions, requests to subscribe/follow, "
    "and thanks addressed to another channel or media brand. Never put a source channel or media brand in "
    "the clip title. Never turn myths, folklore, or supernatural claims into established Islamic facts; "
    "frame them accurately as stories, claims, questions, or lessons. "
    "Return ONLY strict JSON, no markdown, no prose."
)


def ai_rescore_candidates(
    candidates: list[ClipCandidate],
    config: AIConfig,
    target_count: int | None = None,
    compilation: bool = False,
) -> list[ClipCandidate]:
    if not config.enabled or not candidates:
        return candidates
    if not config.base_url or not config.model:
        console.print("[yellow]AI agent skipped:[/yellow] base_url/model not set.")
        return candidates

    pool_limit = max(AI_RESCORE_POOL_LIMIT, min(len(candidates), (target_count or 0) * 12))
    pool = sorted(candidates, key=lambda item: item.score, reverse=True)[:pool_limit]
    items = [
        {
            "id": idx,
            "start": round(candidate.start, 1),
            "end": round(candidate.end, 1),
            "duration": round(candidate.duration, 1),
            "heuristic_score": candidate.score,
            "heuristic_strengths": candidate.strengths,
            "heuristic_weaknesses": candidate.weaknesses,
            "text": candidate.text[:1200],
        }
        for idx, candidate in enumerate(pool)
    ]
    count_instruction = (
        f"Pick and rank the best {target_count} candidates for export."
        if target_count
        else "Pick and rank only the candidates that deserve to become clips."
    )
    format_instruction = (
        "This is for one 5-10 minute 16:9 landscape story resume of the entire source. Choose complementary "
        "POV moments that form a coherent chronological arc: premise/context, conflict or development, core insight, "
        "and payoff/conclusion. Cover the source broadly, avoid repeated ideas and low-value filler, and never invent "
        "bridges that are not supported by the transcript."
        if compilation
        else "This is for Indonesian short-form FYP. Choose POV moments people would stop scrolling for, "
        "not merely complete transcript chunks."
    )
    user_prompt = (
        f"{count_instruction}\n"
        f"{format_instruction}\n"
        "For each chosen candidate, score 0-100 honestly on viewer-retention and FYP potential. "
        "Judge the first 3 seconds, the first 30-second hook arc, POV clarity, information density, "
        "pattern-interrupt opportunities, one clear key point, payoff placement, sentence-complete boundaries, "
        "and rewatch/share potential. Do not select two windows that communicate the same main idea.\n"
        "Every improvement idea must solve one stated weakness and be directly executable by an editor. "
        "Start each idea with exactly one supported area: Hook, Ritme, Ending, Loop, Visual, or Audio. "
        "Write every viewer-facing field in clear, natural Indonesian. "
        "Write it as '<area> — <specific action>', for example "
        "'Hook — pindahkan klaim terkuat ke detik 0'. "
        "When useful, quote a short phrase from the transcript as the exact edit anchor. Do not give generic "
        "advice, repeat the same fix in different words, or invent facts/dialogue not present in the transcript. "
        "Prefer trims, reorder suggestions, on-screen text, visual emphasis, and a precise ending treatment.\n"
        "Return clips sorted from strongest to weakest. Use fewer clips if the rest are weak.\n"
        "Respond with JSON shaped exactly like:\n"
        '{"clips": [{"id": <int>, "score": <int 0-100>, '
        '"title": "<catchy hook title, max 8 words>", '
        '"hook": "<scroll-stopping opening, max 8 words>", '
        '"reason": "<short why this has FYP potential>", '
        '"pov": "<short POV angle for viewers>", '
        '"strengths": ["<max 3 concrete strengths>"], '
        '"weaknesses": ["<max 3 concrete weaknesses>"], '
        '"improvement_ideas": ["<max 3 specific edit/content fixes>"]}]}\n\n'
        "Candidates:\n" + json.dumps(items, ensure_ascii=False)
    )

    try:
        console.print(f"[bold]AI agent scoring[/bold] {len(pool)} candidates via {config.model}...")
        content = chat_completion(
            config,
            [
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        parsed = extract_json(content)
    except Exception as exc:
        if not disable_unavailable_ai(config, exc):
            console.print(f"[yellow]AI agent failed, using heuristic scores:[/yellow] {exc}")
        return candidates

    scored = parsed.get("clips") if isinstance(parsed, dict) else None
    if not isinstance(scored, list):
        console.print("[yellow]AI agent returned no usable clips; keeping heuristic scores.[/yellow]")
        return candidates

    ranked_entries: list[tuple[int, dict]] = []
    seen_ids: set[int] = set()
    for entry in scored:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        if not isinstance(cid, int) or cid < 0 or cid >= len(pool):
            continue
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        ranked_entries.append((cid, entry))

    if not ranked_entries:
        console.print("[yellow]AI agent returned no valid candidate ids; keeping heuristic scores.[/yellow]")
        return candidates

    selected_candidate_ids = {id(pool[cid]) for cid, _ in ranked_entries}
    original_scores = {id(candidate): candidate.score for candidate in pool}
    for candidate in pool:
        if id(candidate) not in selected_candidate_ids:
            # Keep unchosen LLM-pool candidates available as fallback, but push
            # them below explicit AI picks so final export follows the AI ranking.
            candidate.score = max(1, min(70, int(round(candidate.score * 0.75))))

    applied = 0
    for rank, (cid, entry) in enumerate(ranked_entries):
        candidate = pool[cid]
        ai_score = entry.get("score")
        if isinstance(ai_score, (int, float)):
            normalized_ai_score = max(1, min(100, int(round(ai_score))))
            heuristic_score = original_scores[id(candidate)]
            candidate.score = max(
                1,
                min(100, int(round(normalized_ai_score * 0.75 + heuristic_score * 0.25))),
            )
        else:
            candidate.score = original_scores[id(candidate)]
        title = entry.get("title")
        if (
            isinstance(title, str)
            and title.strip()
            and not is_source_branding_segment(title)
        ):
            candidate.title = title.strip()[:80]
        hook = entry.get("hook")
        if (
            isinstance(hook, str)
            and hook.strip()
            and not is_source_branding_segment(hook)
        ):
            candidate.hook = first_sentence(hook, max_words=8)[:80]
        reason = entry.get("reason")
        pov = entry.get("pov")
        reason_parts: list[str] = []
        if isinstance(reason, str) and reason.strip():
            reason_parts.append(reason.strip())
        if isinstance(pov, str) and pov.strip():
            reason_parts.append("POV: " + pov.strip())
            candidate.pov = pov.strip()[:220]
        if reason_parts:
            candidate.reason = "AI FYP: " + " | ".join(reason_parts)[:180]
        for field_name in ("strengths", "weaknesses", "improvement_ideas"):
            raw_values = entry.get(field_name)
            if not isinstance(raw_values, list):
                continue
            clean_values = [
                re.sub(r"\s+", " ", str(value)).strip()[:180]
                for value in raw_values
                if isinstance(value, str) and value.strip()
            ][:3]
            if clean_values:
                setattr(candidate, field_name, clean_values)
        candidate.fyp_label = fyp_score_label(candidate.score)
        if not candidate.hook:
            candidate.hook = first_sentence(candidate.title, max_words=8)
        if not candidate.pov:
            candidate.pov = fallback_pov_angle(candidate.text)
        applied += 1

    if applied:
        for candidate in pool:
            candidate.fyp_label = fyp_score_label(candidate.score)
            if not candidate.hook:
                candidate.hook = first_sentence(candidate.title, max_words=8)
            if not candidate.pov:
                candidate.pov = fallback_pov_angle(candidate.text)
        console.print(f"[green]AI agent selected[/green] {applied} FYP-focused candidates.")
    else:
        for candidate in pool:
            candidate.score = original_scores[id(candidate)]
        console.print("[yellow]AI agent returned no usable clips; keeping heuristic scores.[/yellow]")
    return candidates


def segments_for_clip(segments: Iterable[TranscriptSegment], clip: ClipCandidate) -> list[TranscriptSegment]:
    selected: list[TranscriptSegment] = []
    for item in segments:
        overlap = min(item.end, clip.end) - max(item.start, clip.start)
        segment_duration = max(0.1, item.end - item.start)
        minimum_overlap = min(0.35, max(0.08, segment_duration * 0.12))
        if overlap < minimum_overlap or is_source_branding_segment(item):
            continue
        selected.append(item)
    return selected


def codex_edit_plan(clip: ClipCandidate) -> CodexEditPlan:
    """Translate analysis prose into deterministic editing behavior."""
    weaknesses = " ".join(clip.weaknesses).casefold()
    ideas = " ".join(clip.improvement_ideas).casefold()
    analysis = f"{weaknesses} {ideas}"
    loop_is_earned = clip.loop_score >= 45 or any(
        "loop alami" in strength.casefold() for strength in clip.strengths
    )
    return CodexEditPlan(
        hook_boost=True,
        tempo_boost=any(
            token in analysis
            for token in (
                "tempo",
                "ritme",
                "alur",
                "30 detik",
                "pangkas",
                "potong",
                "trim",
                "jeda",
                "pengulangan",
            )
        ),
        ending_boost=any(token in weaknesses for token in ("ending", "payoff"))
        or "ending —" in ideas
        or "ending -" in ideas
        or "penutup" in ideas
        or "payoff" in ideas
        or clip.boundary_quality in {"", "menggantung"},
        # A callback card without semantic continuity feels artificial. Only
        # enable the loop treatment when hook and payoff actually connect.
        loop_boost=loop_is_earned,
    )


def _codex_idea_area(idea: str) -> str:
    """Normalize an editor idea into one of the treatments supported by the renderer."""
    prefix = re.split(r"\s*(?:—|–|:|\s-\s)\s*", idea.casefold(), maxsplit=1)[0][:48]
    categories = (
        ("hook", ("hook", "pembuka", "opening")),
        ("tempo", ("tempo", "ritme", "alur", "cut", "potong", "pangkas", "trim")),
        ("ending", ("ending", "penutup", "payoff", "kesimpulan")),
        ("loop", ("loop", "callback")),
        ("visual", ("visual", "teks", "overlay", "b-roll", "frame", "emphasis")),
        ("audio", ("audio", "sfx", "suara", "sound")),
    )
    for category, tokens in categories:
        if any(token in prefix for token in tokens):
            return category
    return ""


def resolve_codex_ideas(
    ideas: list[str],
    plan: CodexEditPlan,
    *,
    enhanced_edit: bool,
    output_format: OutputFormat,
    drawtext_supported: bool,
) -> tuple[list[str], list[str]]:
    """Move executable Codex ideas to applied edits after their render treatment is active."""
    if not enhanced_edit or output_format != "vertical_short":
        return list(ideas), []

    remaining: list[str] = []
    applied: list[str] = []
    for idea in ideas:
        area = _codex_idea_area(idea)
        if area == "hook" and plan.hook_boost:
            applied.append(
                "Arahan hook diterapkan: opening dipertegas dengan hook card, impact pulse, dan accent audio."
            )
        elif area == "tempo" and plan.tempo_boost:
            applied.append(
                "Arahan ritme diterapkan: ritme visual dipadatkan dengan pattern interrupt yang lebih cepat."
            )
        elif area == "ending" and plan.ending_boost:
            applied.append(
                "Arahan ending diterapkan: kalimat penutup sumber dijadikan payoff terakhir"
                + (" dengan kartu teks dan accent audio." if drawtext_supported else " dengan accent audio.")
            )
        elif area == "loop":
            applied.append(
                "Arahan loop diterapkan pada titik payoff yang kembali ke hook."
                if plan.loop_boost
                else "Arahan loop ditinjau: callback tidak dipaksakan karena hook dan payoff belum terhubung secara alami."
            )
        elif area == "visual":
            applied.append(
                "Arahan visual diterapkan: poin utama diberi emphasis pulse, aksen frame, dan variasi angle virtual medium/close-up."
            )
        elif area == "audio":
            applied.append(
                "Arahan audio diterapkan: SFX kontekstual dipasang secara selektif tanpa menutup dialog."
            )
        else:
            remaining.append(idea)

    return remaining, list(dict.fromkeys(applied))


def _segment_hook_score(segment: TranscriptSegment) -> tuple[int, int]:
    words = re.findall(r"[\w']+", segment.text.lower())
    word_set = set(words)
    strong_signals = (HOOK_WORDS - WEAK_STARTS) | TENSION_WORDS | MYSTERY_WORDS | IMPORTANT_WORDS
    return (
        len(word_set.intersection(strong_signals)) * 5
        + int("?" in segment.text) * 4
        + int(bool(word_set.intersection(PAYOFF_WORDS))) * 2
        - int(bool(words and words[0] in WEAK_STARTS)) * 4,
        min(len(words), 16),
    )


def apply_codex_structural_edit(
    clip: ClipCandidate,
    transcript: list[TranscriptSegment],
    *,
    min_duration: float,
    max_duration: float,
    hard_end: float | None = None,
) -> ClipCandidate:
    """Trim a weak lead-in and extend an unfinished ending when the transcript allows it."""
    original_plan = codex_edit_plan(clip)
    original_start = clip.start
    original_end = clip.end
    min_safe_duration = max(5.0, min_duration)
    max_safe_end = clip.start + max(max_duration, min_safe_duration)
    if hard_end is not None:
        max_safe_end = min(max_safe_end, hard_end)

    current_segments = segments_for_clip(transcript, clip)
    if original_plan.hook_boost and current_segments:
        search_end = min(original_end, original_start + min(12.0, max(5.0, clip.duration * 0.25)))
        hook_options = [
            segment
            for segment in current_segments
            if segment.start < search_end and segment.start > original_start + 0.55
        ]
        if hook_options:
            strongest = max(hook_options, key=_segment_hook_score)
            proposed_start = max(original_start, strongest.start - 0.12)
            trim_seconds = proposed_start - original_start
            if (
                _segment_hook_score(strongest)[0] > 0
                and 0.65 <= trim_seconds <= 8.0
                and original_end - proposed_start >= min_safe_duration
            ):
                clip.start = proposed_start
                clip.applied_edits.append(
                    f"Pembuka lemah dipangkas {trim_seconds:.1f} detik; klip dimulai dari klaim terkuat."
                )

    # Trimming a weak intro creates an equal amount of room for a complete
    # answer at the end while the final clip still respects max_duration.
    max_safe_end = clip.start + max(max_duration, min_safe_duration)
    if hard_end is not None:
        max_safe_end = min(max_safe_end, hard_end)

    if original_plan.ending_boost and max_safe_end > original_end + 0.25:
        current_text = " ".join(segment.text for segment in current_segments).rstrip()
        needs_sentence_close = not current_text.endswith((".", "!", "?"))
        for segment in transcript:
            if segment.end <= original_end + 0.2:
                continue
            if segment.start >= max_safe_end:
                break
            if is_source_branding_segment(segment):
                break
            words = set(re.findall(r"[\w']+", segment.text.lower()))
            has_resolution = bool(words.intersection(PAYOFF_WORDS | IMPORTANT_WORDS))
            sentence_closed = segment.text.rstrip().endswith((".", "!", "?"))
            if (has_resolution and sentence_closed) or (needs_sentence_close and sentence_closed):
                proposed_end = min(max_safe_end, segment.end + 0.12)
                if proposed_end > original_end + 0.25:
                    clip.end = proposed_end
                    clip.applied_edits.append(
                        f"Ending diperpanjang {proposed_end - original_end:.1f} detik sampai kalimat tuntas."
                    )
                break
    if clip.start != original_start or clip.end != original_end:
        refreshed_segments = segments_for_clip(transcript, clip)
        clip.duration = clip.end - clip.start
        clip.text = " ".join(segment.text for segment in refreshed_segments).strip()
        heuristic_score, _ = score_window(refreshed_segments, clip.duration)
        clip.score = max(1, min(100, round(clip.score * 0.75 + heuristic_score * 0.25)))
        refreshed = candidate_fyp_analysis(refreshed_segments, clip.duration, clip.score)
        story_metrics = candidate_story_metrics(refreshed_segments, clip.duration)
        clip.hook = str(refreshed["hook"])
        clip.pov = str(refreshed["pov"])
        clip.fyp_label = fyp_score_label(clip.score)
        clip.strengths = list(refreshed["strengths"])
        clip.weaknesses = list(refreshed["weaknesses"])
        clip.improvement_ideas = list(refreshed["improvement_ideas"])
        clip.key_point_score = int(story_metrics["key_point_score"])
        clip.loop_score = int(story_metrics["loop_score"])
        clip.boundary_quality = str(story_metrics["boundary_quality"])
    return clip


def apply_codex_edits_to_candidates(
    candidates: list[ClipCandidate],
    transcript: list[TranscriptSegment],
    *,
    min_duration: float,
    max_duration: float,
) -> list[ClipCandidate]:
    """Apply structural edits without allowing neighboring selected clips to overlap."""
    ordered = sorted(candidates, key=lambda item: item.start)
    original_starts = [item.start for item in ordered]
    for index, clip in enumerate(ordered):
        next_start = original_starts[index + 1] if index + 1 < len(original_starts) else None
        hard_end = next_start - 0.05 if next_start is not None else None
        apply_codex_structural_edit(
            clip,
            transcript,
            min_duration=min_duration,
            max_duration=max_duration,
            hard_end=hard_end,
        )
        clip.index = index + 1
    return ordered


SUBTITLE_MAX_CHARS = 22
SUBTITLE_MAX_LINES = 2

# Important text stays clear of the Shorts action rail on the right and the
# title/channel chrome near the bottom. Decorative pixels may extend beyond it.
SHORTS_SAFE_LEFT = 56
SHORTS_SAFE_RIGHT = 900
SHORTS_SAFE_TOP = 220
SHORTS_SAFE_BOTTOM = 1560
SHORTS_OFFICIAL_MAX_SECONDS = 180
FENDY_CLIPPER_SHORTS_MAX_SECONDS = 60
SHORTS_POLICY_REVIEW_DATE = "2026-08-11"


def wrap_subtitle(text: str, max_chars: int = SUBTITLE_MAX_CHARS, max_lines: int = SUBTITLE_MAX_LINES) -> str:
    chunks = split_subtitle_text(text, max_chars=max_chars, max_lines=max_lines)
    return chunks[0] if chunks else ""


def split_subtitle_text(text: str, max_chars: int = SUBTITLE_MAX_CHARS, max_lines: int = SUBTITLE_MAX_LINES) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join([*current, word]).strip()
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) == max_lines:
                chunks.append("\n".join(lines))
                lines = []
        else:
            current.append(word)

    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    if lines:
        chunks.append("\n".join(lines))

    return chunks


def content_edit_variation(clip: ClipCandidate, variants: int = 6) -> int:
    """Choose a stable look from story content, not export order.

    Content-derived variation makes a channel less template-like while keeping
    rerenders deterministic and easy to audit.
    """
    safe_variants = max(1, variants)
    fingerprint = "|".join(
        (
            clip.title.strip().casefold(),
            clip.hook.strip().casefold(),
            clip.pov.strip().casefold(),
            first_sentence(clip.text, max_words=18).casefold(),
        )
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % safe_variants


ARCHIVAL_VISUAL_WORDS = {
    "arsip",
    "dahulu",
    "dinasti",
    "dokumenter",
    "jadul",
    "khalifah",
    "kerajaan",
    "masa lalu",
    "peradaban",
    "sejarah",
    "tempo dulu",
    "tokoh",
}

DEPTH_VISUAL_WORDS = {
    "berubah",
    "hikmah",
    "inspirasi",
    "kisah",
    "pelajaran",
    "perjalanan",
    "rahasia",
    "solusi",
    "transformasi",
}


def auto_fyp_visual_plan(
    clip: ClipCandidate,
    output_format: OutputFormat,
) -> dict[str, object]:
    """Choose one restrained accent on top of a consistent cinematic base.

    The decision is derived from the story rather than export order, providing
    visible variation without stacking every effect or producing a batch of
    near-identical templates.
    """
    searchable = re.sub(
        r"\s+",
        " ",
        f"{clip.title} {clip.hook} {clip.pov} {clip.text}".casefold(),
    )
    words = set(re.findall(r"[\w']+", searchable))
    variation = content_edit_variation(clip)
    archival_match = any(term in searchable for term in ARCHIVAL_VISUAL_WORDS)
    depth_match = bool(words.intersection(DEPTH_VISUAL_WORDS))

    if archival_match:
        accent = "retro_archive"
        reason = "historical_or_archival_story_signal"
    elif depth_match and variation in {1, 3, 5}:
        accent = "animated_depth"
        reason = "story_depth_signal"
    else:
        accent = "cinematic_clean"
        reason = "clarity_and_authenticity_priority"

    return {
        "version": 1,
        "base": "cinematic_clean_detail",
        "accent": accent,
        "reason": reason,
        "content_derived": True,
        "variation": variation,
        "speaker_split": (
            "detect_two_speakers" if output_format == "landscape_compilation" else "off"
        ),
        "stack_all_effects": False,
    }


def hook_banner_text(clip: ClipCandidate) -> str:
    title = first_sentence(clip.hook or clip.title, max_words=8).upper()
    chunks = split_subtitle_text(title, max_chars=24, max_lines=2)
    return (chunks[0] if chunks else title)[:80]


def pov_banner_text(clip: ClipCandidate) -> str:
    pov = re.sub(r"^\s*pov\s*:\s*", "", clip.pov or fallback_pov_angle(clip.text), flags=re.I)
    short_pov = first_sentence(pov, max_words=12)
    chunks = split_subtitle_text(short_pov, max_chars=48, max_lines=2)
    return (chunks[0] if chunks else short_pov)[:110]


def thumbnail_story_copy(
    clip: ClipCandidate,
    suggested_hook: str = "",
    *,
    long_form: bool = False,
) -> dict[str, str]:
    """Build compact, truthful cover copy from the analyzed story fields."""
    raw_pov = re.sub(
        r"^\s*pov\s*:\s*",
        "",
        clip.pov or fallback_pov_angle(clip.text),
        flags=re.I,
    )
    if is_source_branding_segment(raw_pov):
        raw_pov = fallback_pov_angle(clip.text)

    raw_hook = suggested_hook or clip.hook or clip.title
    if is_source_branding_segment(raw_hook):
        raw_hook = clip.title if not is_source_branding_segment(clip.title) else raw_pov

    if long_form:
        headline_source = raw_hook
        support_source = raw_pov
        eyebrow = "RESUME CERITA"
        headline_words = 8
        headline_chars = 18
        headline_lines = 2
        support_words = 10
    else:
        # Lead with the analyzed hook. A concrete promise/question is easier to
        # scan in a Shorts grid than a longer POV sentence; the POV remains as
        # truthful context underneath it.
        headline_source = raw_hook
        support_source = raw_pov
        eyebrow = "WAJIB TAHU"
        headline_words = 8
        headline_chars = 22
        headline_lines = 3
        support_words = 10

    headline = first_sentence(headline_source, max_words=headline_words).upper()
    headline_chunks = split_subtitle_text(
        headline,
        max_chars=headline_chars,
        max_lines=headline_lines,
    )
    headline = (headline_chunks[0] if headline_chunks else headline)[:120]

    support = first_sentence(support_source, max_words=support_words).upper()
    support_words_set = _content_words(support)
    headline_words_set = _content_words(headline)
    if support_words_set and support_words_set.issubset(headline_words_set):
        support = ""
    support_chunks = split_subtitle_text(
        support,
        max_chars=30 if long_form else 26,
        max_lines=2,
    )
    support = (support_chunks[0] if support_chunks else support)[:80]

    return {
        "eyebrow": eyebrow,
        "headline": headline,
        "support": support,
    }


def shorts_cover_frame_timestamp(duration: float) -> float:
    """Pick a stable, keyframe-friendly instant inside the opening cover moment."""
    return min(max(0.1, duration - 0.05), 0.78)


SHORTS_TITLE_OVERLAY_SECONDS = 3.2
SHORTS_CTA_OVERLAY_SECONDS = 2.35
DEFAULT_SHORTS_CTA_VOICEOVER_TEXT = "Subscribe dan follow untuk video berikutnya!"


def viral_title_overlay_filter(headline_filename: str, duration: float) -> str:
    """Render a transcript-grounded cover card like fast-scanning Shorts grids."""
    title_end = min(max(0.1, duration), SHORTS_TITLE_OVERLAY_SECONDS)
    active = f"enable='between(t,0,{title_end:.3f})'"
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ",".join(
        [
            # Two offset rectangles make a soft, rounded-looking card using
            # only filters available in the standard backend FFmpeg build.
            f"drawbox=x=70:y=1002:w=830:h=380:color=black@0.28:t=fill:{active}",
            f"drawbox=x=58:y=982:w=842:h=356:color=white@0.97:t=fill:{active}",
            f"drawbox=x=80:y=960:w=798:h=400:color=white@0.97:t=fill:{active}",
            f"drawbox=x=96:y=1012:w=254:h=48:color=#FFF200@1.0:t=fill:{active}",
            "drawtext="
            f"fontfile={font_bold}:text='WAJIB TAHU':expansion=none:"
            "fontcolor=black:fontsize=25:x=114:y=1021:"
            f"{active}",
            "drawtext="
            f"fontfile={font_bold}:textfile='{headline_filename}':reload=0:expansion=none:"
            "fontcolor=black:fontsize=49:line_spacing=4:"
            "x=96:y=1086:"
            f"{active}",
            f"drawbox=x=96:y=1298:w=684:h=3:color=black@0.16:t=fill:{active}",
            f"drawbox=x=96:y=1320:w=22:h=22:color=#FF1744@1.0:t=fill:{active}",
            "drawtext="
            f"fontfile={font_regular}:text='{CHANNEL_WATERMARK}':expansion=none:"
            "fontcolor=black@0.82:fontsize=22:x=132:y=1318:"
            f"{active}",
        ]
    )


def shorts_cta_overlay_filter(duration: float) -> str:
    """Add a compact end CTA over the live payoff instead of a retention-killing outro."""
    safe_duration = max(0.1, duration)
    cta_start = max(0.0, safe_duration - SHORTS_CTA_OVERLAY_SECONDS)
    cta_end = max(cta_start, safe_duration - 0.04)
    active = f"enable='between(t,{cta_start:.3f},{cta_end:.3f})'"
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ",".join(
        [
            f"drawbox=x=88:y=1016:w=784:h=196:color=black@0.28:t=fill:{active}",
            f"drawbox=x=74:y=1002:w=784:h=196:color=white@0.97:t=fill:{active}",
            f"drawbox=x=96:y=1018:w=206:h=4:color=#FFF200@1.0:t=fill:{active}",
            f"drawbox=x=96:y=1030:w=298:h=82:color=#FF1744@1.0:t=fill:{active}",
            "drawtext="
            f"fontfile={font_bold}:text='SUBSCRIBE':expansion=none:"
            "fontcolor=white:fontsize=34:x=124:y=1053:"
            f"{active}",
            "drawtext="
            f"fontfile={font_bold}:text='+ FOLLOW':expansion=none:"
            "fontcolor=black:fontsize=34:x=426:y=1053:"
            f"{active}",
            "drawtext="
            f"fontfile={font_regular}:text='JANGAN LEWATKAN VIDEO BERIKUTNYA':expansion=none:"
            "fontcolor=black@0.72:fontsize=22:x=98:y=1142:"
            f"{active}",
            f"drawbox=x=742:y=1138:w=92:h=5:color=#FFF200@1.0:t=fill:{active}",
        ]
    )


def env_enabled(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def shorts_cta_voiceover_text() -> str:
    """Return a short command-safe CTA copy; subprocess calls use argv, not a shell."""
    configured = os.environ.get(
        "CTA_VOICEOVER_TEXT", DEFAULT_SHORTS_CTA_VOICEOVER_TEXT
    )
    text = re.sub(r"\s+", " ", configured).strip()
    return (text or DEFAULT_SHORTS_CTA_VOICEOVER_TEXT)[:120]


def generate_shorts_cta_voiceover(
    clips_dir: Path,
    base_name: str,
) -> tuple[Path, dict[str, object]] | None:
    """Create an Indonesian CTA voice, preferring neural TTS with offline fallback."""
    if not env_enabled("CTA_VOICEOVER_ENABLED", True):
        return None

    requested_provider = os.environ.get("CTA_VOICEOVER_PROVIDER", "auto").strip().lower()
    if requested_provider not in {"auto", "edge", "espeak"}:
        requested_provider = "auto"
    text = shorts_cta_voiceover_text()
    voice = os.environ.get("CTA_VOICEOVER_VOICE", "id-ID-ArdiNeural").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{2,64}", voice):
        voice = "id-ID-ArdiNeural"
    rate = os.environ.get("CTA_VOICEOVER_RATE", "+12%").strip()
    if not re.fullmatch(r"[+-]\d{1,2}%", rate):
        rate = "+12%"
    neural_path = clips_dir / f"{base_name}.cta_voice_tmp.mp3"
    local_path = clips_dir / f"{base_name}.cta_voice_tmp.wav"

    if requested_provider in {"auto", "edge"}:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "edge_tts",
                    "--voice",
                    voice,
                    "--rate",
                    rate,
                    "--text",
                    text,
                    "--write-media",
                    str(neural_path.resolve()),
                ],
                cwd=clips_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=35,
            )
            if (
                result.returncode == 0
                and neural_path.is_file()
                and neural_path.stat().st_size > 512
            ):
                return neural_path, {
                    "provider": "edge_neural",
                    "voice": voice,
                    "text": text,
                    "rate": rate,
                }
        except (OSError, subprocess.TimeoutExpired):
            pass
        neural_path.unlink(missing_ok=True)
        console.print(
            "[yellow]Voice neural CTA tidak tersedia; mencoba voice lokal.[/yellow]"
        )

    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if requested_provider in {"auto", "edge", "espeak"} and espeak:
        local_voice = os.environ.get("CTA_VOICEOVER_ESPEAK_VOICE", "id+m3").strip()
        if not re.fullmatch(r"[A-Za-z0-9+_-]{1,32}", local_voice):
            local_voice = "id+m3"
        try:
            result = subprocess.run(
                [
                    espeak,
                    "-v",
                    local_voice,
                    "-s",
                    "178",
                    "-p",
                    "48",
                    "-a",
                    "165",
                    "-w",
                    str(local_path.resolve()),
                    text,
                ],
                cwd=clips_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
            )
            if result.returncode == 0 and local_path.is_file() and local_path.stat().st_size > 512:
                return local_path, {
                    "provider": "espeak_local",
                    "voice": local_voice,
                    "text": text,
                    "rate": "178_wpm",
                }
        except (OSError, subprocess.TimeoutExpired):
            pass
        local_path.unlink(missing_ok=True)
    return None


def shorts_cta_voiceover_mix_filter(duration: float) -> str:
    """Duck the final spoken beat and place the CTA voice inside its card window."""
    safe_duration = max(0.1, duration)
    cta_start = max(0.0, safe_duration - SHORTS_CTA_OVERLAY_SECONDS)
    voice_start = min(safe_duration - 0.05, cta_start + 0.12)
    voice_window = max(0.35, safe_duration - voice_start - 0.04)
    delay_ms = max(0, int(round(voice_start * 1000)))
    fade_out_start = max(0.1, voice_window - 0.18)
    return (
        "[0:a:0]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"volume='if(between(t,{cta_start:.3f},{safe_duration:.3f}),0.34,1)':eval=frame"
        "[cta_dialog];"
        f"[1:a:0]atrim=start=0:end={voice_window:.3f},asetpts=PTS-STARTPTS,"
        "highpass=f=95,lowpass=f=12500,acompressor=threshold=0.10:ratio=3.2:"
        "attack=8:release=100:makeup=1.45,loudnorm=I=-14:TP=-1.2:LRA=7,"
        "aformat=sample_rates=48000:channel_layouts=stereo,"
        "afade=t=in:st=0:d=0.055,"
        f"afade=t=out:st={fade_out_start:.3f}:d=0.180,"
        f"adelay=delays={delay_ms}:all=1[cta_voice];"
        "[cta_dialog][cta_voice]amix=inputs=2:duration=first:"
        "dropout_transition=0:normalize=0,alimiter=limit=0.95:attack=5:release=50"
        "[cta_audio_out]"
    )


def shorts_policy_compliance(duration: float, *, embedded_cover: bool) -> dict[str, object]:
    """Record the current technical Shorts guardrails beside each render.

    Policy compliance still depends on the actual source rights, claims, and
    channel-level review, so this deliberately records controls rather than a
    promise that YouTube will recommend or monetize the upload.
    """
    safe_duration = max(0.0, duration)
    return {
        "reviewed_on": SHORTS_POLICY_REVIEW_DATE,
        "official_max_seconds": SHORTS_OFFICIAL_MAX_SECONDS,
        "fendy_clipper_max_seconds": FENDY_CLIPPER_SHORTS_MAX_SECONDS,
        "duration_seconds": round(safe_duration, 3),
        "duration_within_official_limit": safe_duration <= SHORTS_OFFICIAL_MAX_SECONDS,
        "duration_within_fendy_clipper_limit": safe_duration <= FENDY_CLIPPER_SHORTS_MAX_SECONDS,
        "vertical_aspect_ratio": "9:16",
        "custom_thumbnail_upload_supported": False,
        "thumbnail_strategy": (
            "embedded_selectable_frame" if embedded_cover else "rendered_video_frame"
        ),
        "source_promos_removed_from_candidate_windows": True,
        "inauthentic_content_policy_reviewed": True,
        "mass_produced_or_repetitive_content_not_assumed_monetizable": True,
        "non_original_shorts_views_may_be_ineligible": True,
        "claimed_content_over_one_minute_block_risk": safe_duration > 60,
        "content_id_claim_check_required_before_publication": True,
        "rights_and_originality_review_required": True,
        "channel_level_review_still_applies": True,
        "recommendation_or_monetization_guarantee": False,
    }


def payoff_banner_text(clip: ClipCandidate, clip_segments: list[TranscriptSegment]) -> str:
    """Extract an explicit takeaway from the transcript without inventing copy."""
    key_markers = (
        "intinya",
        "kesimpulannya",
        "jadi",
        "artinya",
        "pelajarannya",
        "hikmahnya",
        "yang penting",
        "kuncinya",
        "jawabannya",
    )
    source_segments = clip_segments or [TranscriptSegment(0, 0, clip.text)]
    search_pool = source_segments[max(0, len(source_segments) // 3) :]
    marked = [
        segment.text
        for segment in search_pool
        if any(marker in segment.text.casefold() for marker in key_markers)
    ]
    takeaway = marked[-1] if marked else source_segments[-1].text
    value = first_sentence(takeaway, max_words=10).upper()
    chunks = split_subtitle_text(value, max_chars=30, max_lines=2)
    return (chunks[0] if chunks else value)[:100]


def detect_visual_theme(clip: ClipCandidate) -> VisualTheme:
    words = set(re.findall(r"[\w']+", f"{clip.title} {clip.text}".lower()))
    if words.intersection(MYSTERY_WORDS):
        return "mystery"
    if words.intersection(ISLAMIC_WORDS):
        return "islamic"
    if words.intersection(TENSION_WORDS):
        return "warning"
    if words.intersection(INSPIRING_WORDS):
        return "inspiring"
    return "knowledge"


def clip_has_islamic_context(clip: ClipCandidate) -> bool:
    """Detect Islamic subject matter independently from the dominant visual theme."""
    words = set(re.findall(r"[\w']+", f"{clip.title} {clip.text}".lower()))
    return bool(words.intersection(ISLAMIC_WORDS))


def visual_theme_profile(clip: ClipCandidate) -> dict[str, str]:
    theme = detect_visual_theme(clip)
    has_islamic_context = clip_has_islamic_context(clip)
    profiles: dict[VisualTheme, dict[str, str]] = {
        "mystery": {
            "accent": "#A855F7",
            "accent_secondary": "#22D3EE",
            "badge": "MISTERI / HIKMAH" if has_islamic_context else "KISAH / MISTERI",
            "emphasis_label": "CEK FAKTANYA",
            "grade": (
                "eq=contrast=1.08:brightness=-0.018:saturation=0.90:gamma=0.98,"
                "colorbalance=bs=.035:rs=-.018"
            ),
        },
        "islamic": {
            "accent": "#22C55E",
            "accent_secondary": "#FACC15",
            "badge": "RENUNGAN / HIKMAH",
            "emphasis_label": "AMBIL HIKMAH",
            "grade": (
                "eq=contrast=1.045:brightness=0.008:saturation=1.06:gamma=1.015,"
                "colorbalance=gs=.018:rs=.008"
            ),
        },
        "warning": {
            "accent": "#F97316",
            "accent_secondary": "#EF4444",
            "badge": "JANGAN ABAIKAN",
            "emphasis_label": "PERHATIKAN",
            "grade": "eq=contrast=1.07:brightness=-0.006:saturation=1.04:gamma=0.995",
        },
        "inspiring": {
            "accent": "#38BDF8",
            "accent_secondary": "#A78BFA",
            "badge": "PESAN PENTING",
            "emphasis_label": "INGAT INI",
            "grade": (
                "eq=contrast=1.04:brightness=0.012:saturation=1.08:gamma=1.02,"
                "colorbalance=bs=.012:rs=.008"
            ),
        },
        "knowledge": {
            "accent": "#FACC15",
            "accent_secondary": "#22D3EE",
            "badge": "FAKTA / PELAJARAN",
            "emphasis_label": "POIN PENTING",
            "grade": "eq=contrast=1.05:brightness=0.004:saturation=1.04:gamma=1.01",
        },
    }
    return {"theme": theme, **profiles[theme]}


def emphasis_timestamps(
    clip: ClipCandidate,
    clip_segments: list[TranscriptSegment],
    *,
    limit: int = 3,
) -> list[float]:
    """Find spaced transcript moments worth a restrained visual emphasis pulse."""
    interesting_words = HOOK_WORDS | PAYOFF_WORDS | TENSION_WORDS | MYSTERY_WORDS
    duration = max(0.1, clip.end - clip.start)
    timestamps: list[float] = []
    for segment in clip_segments:
        words = set(re.findall(r"[\w']+", segment.text.lower()))
        if not words.intersection(interesting_words):
            continue
        relative = max(0.0, segment.start - clip.start)
        if relative < 3.4 or relative > duration - 1.0:
            continue
        if timestamps and relative - timestamps[-1] < 4.0:
            continue
        timestamps.append(round(relative, 3))
        if len(timestamps) >= limit:
            break
    if not timestamps and duration >= 14:
        timestamps.append(round(min(duration - 1.0, max(5.0, duration * 0.42)), 3))
    return timestamps


def cinematic_pov_windows(
    clip: ClipCandidate,
    clip_segments: list[TranscriptSegment],
    *,
    limit: int = 3,
) -> list[tuple[float, float]]:
    """Find sparse direct-POV moments for a brief cinematic camera reframe."""
    direct_words = {
        "aku",
        "anda",
        "bayangkan",
        "coba",
        "cobalah",
        "kalian",
        "kamu",
        "pernahkah",
        "rasakan",
        "saya",
    }
    direct_phrases = (
        "kalau kita",
        "ketika kita",
        "menurut saya",
        "pernah tidak",
        "coba lihat",
        "coba pikir",
    )
    duration = max(0.1, clip.end - clip.start)
    windows: list[tuple[float, float]] = []
    for segment in clip_segments:
        text = segment.text.casefold()
        words = set(re.findall(r"[\w']+", text))
        if not words.intersection(direct_words) and not any(
            phrase in text for phrase in direct_phrases
        ):
            continue
        start = max(0.0, segment.start - clip.start)
        if start < 1.8 or start >= duration - 2.0:
            continue
        if windows and start - windows[-1][1] < 3.2:
            continue
        window_duration = max(0.9, min(1.55, segment.end - segment.start))
        end = min(duration - 0.25, start + window_duration)
        if end - start < 0.65:
            continue
        windows.append((round(start, 3), round(end, 3)))
        if len(windows) >= limit:
            break
    return windows


def virtual_camera_angle_cues(
    clip: ClipCandidate,
    clip_segments: list[TranscriptSegment],
    *,
    limit: int = 5,
    min_gap: float = 5.2,
) -> list[CameraAngleCue]:
    """Plan sparse face-safe medium/close cuts on meaningful speech boundaries.

    A single recording cannot provide a genuinely new physical viewpoint. These
    cues recreate a multi-camera rhythm with deliberate crop, zoom, and eyeline
    shifts instead of continuous random motion.
    """
    duration = max(0.1, clip.end - clip.start)
    if duration < 7.0 or not clip_segments or limit <= 0:
        return []

    signal_words = (
        (HOOK_WORDS - WEAK_STARTS)
        | PAYOFF_WORDS
        | TENSION_WORDS
        | IMPORTANT_WORDS
        | MYSTERY_WORDS
    )
    direct_words = {
        "aku",
        "anda",
        "bayangkan",
        "coba",
        "kalian",
        "kamu",
        "saya",
    }
    candidates: list[tuple[int, float, float, str]] = []
    for segment in clip_segments:
        relative_start = max(0.0, segment.start - clip.start)
        if relative_start < 1.65 or relative_start > duration - 1.15:
            continue
        words = set(re.findall(r"[\w']+", segment.text.casefold()))
        score = len(words.intersection(signal_words)) * 4
        score += len(words.intersection(direct_words)) * 2
        score += int("?" in segment.text) * 3
        score += int(segment.text.rstrip().endswith(("!", "?"))) * 2
        score += min(2, len(words) // 8)
        cue_duration = max(1.35, min(2.8, (segment.end - segment.start) + 0.45))
        end = min(duration - 0.35, relative_start + cue_duration)
        if end - relative_start < 1.0:
            continue
        trigger = " ".join(segment.text.split())[:96]
        candidates.append((score, relative_start, end, trigger))

    if not candidates:
        return []

    # Strong semantic beats get first refusal. Cadence candidates then fill
    # longer stretches so a 30–60 second Short never feels like one static crop.
    desired_count = min(limit, max(1, int(duration // 9.5)))
    selected: list[tuple[int, float, float, str]] = []
    for candidate in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if candidate[0] <= 1 and len(selected) >= max(1, desired_count // 2):
            continue
        if any(abs(candidate[1] - existing[1]) < min_gap for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) >= desired_count:
            break

    if len(selected) < desired_count:
        for candidate in sorted(candidates, key=lambda item: item[1]):
            if any(abs(candidate[1] - existing[1]) < min_gap for existing in selected):
                continue
            selected.append(candidate)
            if len(selected) >= desired_count:
                break

    angle_cycle: tuple[tuple[CameraAngleKind, int, int, int], ...] = (
        ("close_left", 42, -12, -6),
        ("medium", 28, 8, -2),
        ("close_center", 48, 0, -8),
        ("close_right", 40, 12, -5),
        ("medium", 30, -8, 2),
    )
    cues: list[CameraAngleCue] = []
    for index, (_, start, end, trigger) in enumerate(sorted(selected, key=lambda item: item[1])):
        kind, zoom_pixels, x_offset, y_offset = angle_cycle[
            (max(0, clip.index - 1) + index) % len(angle_cycle)
        ]
        cues.append(
            CameraAngleCue(
                kind=kind,
                start=round(start, 3),
                end=round(end, 3),
                zoom_pixels=zoom_pixels,
                x_offset=x_offset,
                y_offset=y_offset,
                trigger=trigger,
            )
        )
    return cues


def detect_reaction_cues(
    clip: ClipCandidate,
    clip_segments: list[TranscriptSegment],
    *,
    limit: int = 2,
    min_gap: float = 8.0,
) -> list[ReactionCue]:
    """Choose sparse, transcript-grounded reaction stickers instead of random emoji spam."""
    duration = max(0.1, clip.end - clip.start)
    cues: list[ReactionCue] = []
    for segment in clip_segments:
        text = segment.text.lower()
        words = set(re.findall(r"[\w']+", text))
        kind: ReactionKind | None = None
        trigger = ""
        laugh_pattern = re.search(r"(?:^|\W)(?:ha){2,}(?:\W|$)|w+k+w+k+|he(?:he)+", text)
        if words.intersection(LAUGH_WORDS) or laugh_pattern:
            kind = "laugh"
            trigger = next(iter(sorted(words.intersection(LAUGH_WORDS))), "tertawa")
        elif words.intersection(SHOCK_WORDS):
            kind = "shock"
            trigger = next(iter(sorted(words.intersection(SHOCK_WORDS))))
        elif words.intersection(WARNING_WORDS):
            kind = "warning"
            trigger = next(iter(sorted(words.intersection(WARNING_WORDS))))
        elif words.intersection(PRAYER_WORDS):
            kind = "pray"
            trigger = next(iter(sorted(words.intersection(PRAYER_WORDS))))
        elif words.intersection(IMPORTANT_WORDS):
            kind = "important"
            trigger = next(iter(sorted(words.intersection(IMPORTANT_WORDS))))
        elif "?" in segment.text or words.intersection(
            {"apa", "apakah", "bagaimana", "benarkah", "bukankah", "gimana", "kenapa", "kok", "masa"}
        ):
            kind = "think"
            trigger = "pertanyaan"
        elif words.intersection(HEART_WORDS):
            kind = "heart"
            trigger = next(iter(sorted(words.intersection(HEART_WORDS))))
        if kind is None:
            continue
        if any(existing.kind == kind for existing in cues):
            continue

        relative = max(0.0, segment.start - clip.start)
        relative += min(0.55, max(0.1, (segment.end - segment.start) * 0.25))
        if relative < 3.45 or relative > duration - 0.75:
            continue
        if cues and relative - cues[-1].start < min_gap:
            continue
        end = min(duration - 0.05, relative + 1.85)
        if end <= relative:
            continue
        cues.append(
            ReactionCue(
                kind=kind,
                start=round(relative, 3),
                end=round(end, 3),
                side="right" if len(cues) % 2 == 0 else "left",
                trigger=trigger[:40],
            )
        )
        if len(cues) >= limit:
            break
    return cues


REACTION_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "reactions"


def reaction_overlay_filter(cue: ReactionCue, index: int) -> str:
    asset_path = (REACTION_ASSET_DIR / f"{cue.kind}.svg").resolve()
    escaped_path = str(asset_path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    size = 184 if cue.kind in {"laugh", "shock"} else 176 if cue.kind == "important" else 166
    base_x = 704 if cue.side == "right" else 68
    direction = -1 if cue.side == "right" else 1
    base_label = f"reaction_base_{index}"
    sticker_label = f"reaction_sticker_{index}"
    slide_start = cue.start + 0.22
    x_expression = (
        f"if(lt(t,{slide_start:.3f}),"
        f"{base_x - direction * 120}+{direction * 545:.1f}*(t-{cue.start:.3f}),"
        f"{base_x}+10*sin(9*(t-{cue.start:.3f})))"
    )
    base_y = 1060 if cue.kind == "important" else 1190
    y_expression = f"{base_y}-32*abs(sin(5*(t-{cue.start:.3f})))"
    return (
        f"null[{base_label}];"
        f"movie='{escaped_path}',scale={size}:{size}:flags=lanczos,format=rgba,"
        f"rotate='0.075*sin(7*t+{index})':ow=rotw(iw):oh=roth(ih):c=none,"
        f"colorchannelmixer=aa=0.96[{sticker_label}];"
        f"[{base_label}][{sticker_label}]overlay="
        f"x='{x_expression}':y='{y_expression}':eof_action=repeat:"
        f"enable='between(t,{cue.start:.3f},{cue.end:.3f})'"
    )


SOUND_EFFECT_PROFILES: dict[SoundEffectKind, tuple[int, float, float]] = {
    # frequency (Hz), duration (seconds), mix volume
    "laugh": (920, 0.20, 0.10),
    "shock": (105, 0.34, 0.18),
    "think": (620, 0.18, 0.07),
    "pray": (840, 0.38, 0.065),
    "warning": (155, 0.28, 0.15),
    "heart": (740, 0.34, 0.065),
    "important": (560, 0.18, 0.085),
    "emphasis": (480, 0.13, 0.075),
    "loop": (720, 0.22, 0.075),
}


def contextual_sound_effect_cues(
    duration: float,
    reaction_cues: list[ReactionCue],
    emphasis_times: list[float],
    *,
    limit: int = 5,
    min_gap: float = 3.0,
) -> list[SoundEffectCue]:
    """Turn transcript-grounded reactions/emphasis into sparse, non-spammy sound cues."""
    safe_duration = max(0.1, duration)
    raw: list[tuple[float, SoundEffectKind, str]] = [
        (cue.start, cue.kind, cue.trigger)
        for cue in reaction_cues
        if 0.15 <= cue.start < safe_duration - 0.1
    ]
    for timestamp in emphasis_times:
        if not 0.15 <= timestamp < safe_duration - 0.1:
            continue
        if any(abs(timestamp - cue.start) < 1.5 for cue in reaction_cues):
            continue
        raw.append((timestamp, "emphasis", "kata penegas"))

    selected: list[SoundEffectCue] = []
    for start, kind, trigger in sorted(raw, key=lambda item: item[0]):
        if selected and start - selected[-1].start < min_gap:
            continue
        frequency, effect_duration, volume = SOUND_EFFECT_PROFILES[kind]
        selected.append(
            SoundEffectCue(
                kind=kind,
                start=round(start, 3),
                duration=effect_duration,
                frequency=frequency,
                volume=volume,
                trigger=trigger[:40],
            )
        )
        if len(selected) >= limit:
            break
    return selected


def apply_codex_audio_cues(
    cues: list[SoundEffectCue],
    duration: float,
    plan: CodexEditPlan,
) -> list[SoundEffectCue]:
    """Add restrained impact accents only where the analysis calls for them."""
    additions: list[SoundEffectCue] = []
    if plan.hook_boost and duration > 2.0:
        frequency, effect_duration, volume = SOUND_EFFECT_PROFILES["emphasis"]
        additions.append(
            SoundEffectCue(
                kind="emphasis",
                start=0.18,
                duration=effect_duration,
                frequency=frequency,
                volume=min(0.09, volume + 0.01),
                trigger="hook Codex",
            )
        )
    if plan.ending_boost and duration > 7.0:
        frequency, effect_duration, volume = SOUND_EFFECT_PROFILES["important"]
        additions.append(
            SoundEffectCue(
                kind="important",
                start=round(max(1.0, duration - 2.65), 3),
                duration=effect_duration,
                frequency=frequency,
                volume=min(0.09, volume),
                trigger="payoff Codex",
            )
        )
    if plan.loop_boost and duration > 4.0:
        frequency, effect_duration, volume = SOUND_EFFECT_PROFILES["loop"]
        additions.append(
            SoundEffectCue(
                kind="loop",
                start=round(max(1.0, duration - 0.42), 3),
                duration=effect_duration,
                frequency=frequency,
                volume=volume,
                trigger="loop Codex",
            )
        )

    merged: list[SoundEffectCue] = []
    for cue in sorted([*cues, *additions], key=lambda item: item.start):
        if merged and cue.start - merged[-1].start < 1.25:
            if cue.trigger.endswith("Codex"):
                merged[-1] = cue
            continue
        merged.append(cue)
    max_cues = 7
    if len(merged) <= max_cues:
        return merged
    mandatory = [cue for cue in merged if cue.trigger.endswith("Codex")]
    optional = [cue for cue in merged if not cue.trigger.endswith("Codex")]
    return sorted([*mandatory, *optional[: max_cues - len(mandatory)]], key=lambda item: item.start)


def contextual_audio_mix_filter(
    base_filter: str,
    cues: list[SoundEffectCue],
    *,
    background_music: bool = False,
    duration: float = 60.0,
    music_ducking: bool = True,
) -> str:
    """Mix speech, original micro-SFX, and an optional CC0 motivational music bed."""
    if not cues and not background_music:
        return f"[0:a:0]{base_filter},aformat=sample_rates=48000:channel_layouts=stereo[audio_out]"

    safe_duration = max(0.1, duration)
    voice_filter = (
        f"[0:a:0]{base_filter},"
        "aformat=sample_rates=48000:channel_layouts=stereo"
    )
    if background_music and music_ducking:
        voice_filter += ",asplit=2[voice][voice_sidechain]"
    else:
        voice_filter += "[voice]"
    chains = [voice_filter]
    mix_inputs = ["[voice]"]

    if background_music:
        # A warm A-major pad and a sparse four-note motif. It is synthesized
        # locally from simple oscillators, so exported videos never depend on a
        # third-party recording or a remote music service.
        pad_notes = ((220.00, 0.014), (277.18, 0.012), (329.63, 0.011))
        music_labels: list[str] = []
        for index, (frequency, volume) in enumerate(pad_notes, start=1):
            label = f"music_pad_{index}"
            chains.append(
                f"sine=frequency={frequency:.2f}:sample_rate=48000:duration={safe_duration:.3f},"
                f"volume='{volume:.3f}*(0.78+0.22*sin(2*PI*t/8))':eval=frame,"
                f"aformat=sample_rates=48000:channel_layouts=stereo[{label}]"
            )
            music_labels.append(f"[{label}]")

        motif_notes = (220.00, 277.18, 329.63, 246.94)
        for index, frequency in enumerate(motif_notes):
            label = f"music_motif_{index + 1}"
            offset = index * 2
            phase = f"mod(t,8)-{offset}"
            chains.append(
                f"sine=frequency={frequency:.2f}:sample_rate=48000:duration={safe_duration:.3f},"
                f"volume='0.040*between(mod(t,8),{offset},{offset + 1.8})"
                f"*pow(sin(PI*({phase})/1.8),2)':eval=frame,"
                "aformat=sample_rates=48000:channel_layouts=stereo,"
                f"aecho=0.8:0.35:95:0.16[{label}]"
            )
            music_labels.append(f"[{label}]")

        fade_out_start = max(0.0, safe_duration - min(1.2, safe_duration * 0.2))
        chains.append(
            "".join(music_labels)
            + f"amix=inputs={len(music_labels)}:duration=longest:dropout_transition=0:normalize=0,"
            "lowpass=f=6500,highpass=f=110,volume=0.72,"
            f"afade=t=in:st=0:d={min(0.8, safe_duration * 0.2):.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={safe_duration - fade_out_start:.3f}"
            "[music_bed_raw]"
        )
        if music_ducking:
            chains.append(
                "[music_bed_raw][voice_sidechain]"
                "sidechaincompress=threshold=0.025:ratio=10:attack=20:release=450"
                "[music_bed]"
            )
        else:
            chains.append("[music_bed_raw]anull[music_bed]")
        mix_inputs.append("[music_bed]")

    chime_kinds = {"laugh", "think", "pray", "heart", "important", "emphasis", "loop"}
    for index, cue in enumerate(cues, start=1):
        label = f"sfx_{index}"
        fade_in = min(0.018, cue.duration * 0.15)
        fade_out_start = max(fade_in, cue.duration * 0.28)
        fade_out_duration = max(0.04, cue.duration - fade_out_start)
        delay_ms = max(0, int(round(cue.start * 1000)))
        filters = (
            f"sine=frequency={cue.frequency}:sample_rate=48000:duration={cue.duration:.3f},"
            f"volume={cue.volume:.3f},"
            f"afade=t=in:st=0:d={fade_in:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out_duration:.3f}"
        )
        if cue.kind in chime_kinds:
            filters += ",aecho=0.8:0.22:35:0.18"
        filters += (
            ",aformat=sample_rates=48000:channel_layouts=stereo,"
            f"adelay=delays={delay_ms}:all=1[{label}]"
        )
        chains.append(filters)
        mix_inputs.append(f"[{label}]")

    chains.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95:attack=5:release=50[audio_out]"
    )
    return ";".join(chains)


def modern_blurred_video_frame_filter(accent: str, secondary: str) -> str:
    """Place the sharp clip over a moving blurred copy with a cinematic glow rim."""
    return (
        "split=2[modern_bg_src][modern_fg_src];"
        "[modern_bg_src]scale=360:640:flags=bilinear,gblur=sigma=18,"
        "scale=1080:1920:flags=lanczos,"
        "eq=brightness=-0.11:contrast=1.04:saturation=1.24,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.16:t=fill,"
        "drawbox=x=46:y=81:w=1000:h=1778:color=black@0.42:t=fill,"
        f"drawbox=x=30:y=61:w=1020:h=1798:color={secondary}@0.24:t=fill,"
        f"drawbox=x=35:y=66:w=1010:h=1788:color={accent}@0.34:t=fill[modern_bg];"
        "[modern_fg_src]scale=1000:1778:flags=lanczos[modern_fg];"
        "[modern_bg][modern_fg]overlay=40:71:shortest=1:eof_action=pass"
    )


def animated_3d_look_filter(
    *,
    with_outline: bool = True,
    with_adaptive_sharpen: bool = False,
) -> str:
    """Create a dimensional look while retaining fine facial detail."""
    color_grade = (
        "eq=contrast=1.06:brightness=0.012:saturation=1.24:gamma=0.985,"
        "curves=master='0/0 0.18/0.14 0.48/0.54 0.78/0.86 1/1',"
        "colorbalance=rs=0.028:gs=0.012:bs=-0.018:"
        "rm=0.014:gm=0.006:bm=-0.009,"
        "unsharp=5:5:0.30:3:3:0.10"
    )
    clarity = ",cas=strength=0.30" if with_adaptive_sharpen else ""
    if not with_outline:
        return (
            "hqdn3d=0:0:0.45:0.35,"
            f"{color_grade},"
            f"vignette=PI/16{clarity}"
        )
    return (
        "hqdn3d=0:0:0.45:0.35,"
        "split=2[animated_color_src][animated_edge_src];"
        f"[animated_color_src]{color_grade}[animated_color];"
        "[animated_edge_src]edgedetect=low=0.070:high=0.22,"
        "negate,eq=contrast=1.16:brightness=0.06:saturation=0[animated_ink];"
        "[animated_color][animated_ink]"
        "blend=all_mode=multiply:all_opacity=0.07,"
        f"vignette=PI/16{clarity}"
    )


def animated_3d_fallback_filter(*, with_adaptive_sharpen: bool = False) -> str:
    """Use only widely available filters when the full animated stack is unavailable."""
    clarity = ",cas=strength=0.26" if with_adaptive_sharpen else ""
    return (
        "eq=contrast=1.055:brightness=0.012:saturation=1.20:gamma=0.985,"
        "unsharp=5:5:0.30:3:3:0.10,"
        f"vignette=PI/16{clarity}"
    )


def retro_tv_look_filter(*, with_curves: bool = True) -> str:
    """Give the complete edit a restrained monochrome CRT/aged-tape finish."""
    faded_tones = (
        ",curves=master='0/0.025 0.18/0.13 0.50/0.53 0.82/0.88 1/0.975'"
        if with_curves
        else ""
    )
    return (
        "eq=contrast=1.12:brightness='-0.028+0.009*sin(2*PI*t*7)':"
        "saturation=0.08:gamma=0.96:eval=frame"
        f"{faded_tones},"
        "noise=alls=8:allf=t+u,"
        "drawgrid=x=0:y=0:w=iw:h=4:color=black@0.10:t=1,"
        "drawbox=x='iw*0.69':y=0:w=3:h=ih:color=black@0.16:t=fill:"
        "enable='lt(mod(t+0.35,5.10),1.05)',"
        "drawbox=x='iw*0.22':y=0:w=1:h=ih:color=white@0.12:t=fill:"
        "enable='lt(mod(t+2.10,7.30),0.72)',"
        "vignette=PI/4.8"
    )


def cinematic_smoke_overlay_filter(
    output_format: OutputFormat,
    *,
    variation: int = 0,
) -> str:
    """Add low-cost animated edge fog without covering the focal center.

    The alpha field is generated at quarter resolution and then enlarged. This
    keeps long-form exports practical while giving each story-derived variant
    a slightly different drift phase.
    """
    if output_format == "landscape_compilation":
        output_width, output_height = 1920, 1080
        fog_width, fog_height = 480, 270
        blur_sigma = 4
    else:
        output_width, output_height = 1080, 1920
        fog_width, fog_height = 270, 480
        blur_sigma = 5
    phase = (variation % 6) * 0.73
    alpha = (
        "clip("
        f"34*exp(-pow((Y-H*(0.88+0.025*sin(T*0.32+{phase:.2f})))/(H*0.12),2))"
        f"*(0.72+0.28*sin(X/W*8+T*0.38+{phase:.2f}))"
        f"+20*exp(-pow((X-W*(0.08+0.025*sin(T*0.19+{phase:.2f})))/(W*0.16),2)"
        "-pow((Y-H*0.60)/(H*0.34),2))"
        f"+22*exp(-pow((X-W*(0.92+0.02*sin(T*0.23+{phase:.2f})))/(W*0.17),2)"
        "-pow((Y-H*0.50)/(H*0.38),2))"
        f"+12*exp(-pow((Y-H*0.08)/(H*0.16),2))"
        f"*(0.75+0.25*sin(X/W*10-T*0.25+{phase:.2f})),0,52)"
    )
    return (
        "null[smoke_base];"
        f"nullsrc=size={fog_width}x{fog_height}:rate=15,format=rgba,"
        f"geq=r='255':g='255':b='255':a='{alpha}',"
        f"gblur=sigma={blur_sigma},"
        f"scale={output_width}:{output_height}:flags=bilinear,fps=30[smoke_layer];"
        "[smoke_base][smoke_layer]overlay=0:0:shortest=1:eof_action=pass"
    )


def landscape_compilation_frame_filter(
    accent: str,
    secondary: str,
    *,
    remove_running_text: bool = False,
) -> str:
    """Preserve the source framing inside a cinematic 1920x1080 long-form layout."""
    source_cleanup = "crop=iw:trunc(ih*0.92/2)*2:0:0," if remove_running_text else ""
    return (
        f"{source_cleanup}setsar=1,split=2[wide_bg_src][wide_fg_src];"
        "[wide_bg_src]scale=1920:1080:force_original_aspect_ratio=increase:"
        "force_divisible_by=2:flags=lanczos,crop=1920:1080,"
        "gblur=sigma=36,eq=brightness=-0.20:contrast=1.08:saturation=1.18,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.24:t=fill[wide_bg];"
        "[wide_fg_src]scale=1840:1000:force_original_aspect_ratio=decrease:"
        "force_divisible_by=2:flags=lanczos[wide_fg];"
        "[wide_bg]drawbox=x=28:y=18:w=1864:h=1044:color=black@0.54:t=fill,"
        f"drawbox=x=32:y=22:w=1856:h=1036:color={secondary}@0.24:t=fill,"
        f"drawbox=x=36:y=26:w=1848:h=1028:color={accent}@0.32:t=fill[wide_canvas];"
        "[wide_canvas][wide_fg]overlay=(W-w)/2:(H-h)/2:shortest=1:eof_action=pass,"
        f"drawbox=x=32:y=22:w=1856:h=1036:color={secondary}@0.42:t=5,"
        f"drawbox=x=37:y=27:w=1846:h=1026:color={accent}@0.68:t=3,"
        "drawbox=x=41:y=31:w=1838:h=1018:color=white@0.18:t=2"
    )


def landscape_speaker_split_filter(
    source_width: int,
    source_height: int,
    focus_points: tuple[float, float],
    accent: str,
    secondary: str,
    *,
    emphasis_times: list[float] | None = None,
    remove_running_text: bool = False,
) -> str:
    """Build two bordered close-up panels and pulse the active side on key speech beats."""
    clean_height = make_even(source_height * (0.92 if remove_running_text else 1.0), 2)
    panel_width = 850
    panel_height = 940
    panel_aspect = panel_width / panel_height
    crop_height = clean_height
    crop_width = make_even(crop_height * panel_aspect, 2)
    if crop_width > source_width:
        crop_width = make_even(source_width, 2)
        crop_height = make_even(crop_width / panel_aspect, 2)
    crop_y = max(0, (clean_height - crop_height) // 2)

    crop_positions: list[int] = []
    for focus_x in focus_points:
        center_x = focus_x * source_width
        crop_positions.append(
            int(clamp_even(center_x - crop_width / 2, 0, source_width - crop_width))
        )
    left_x, right_x = crop_positions
    filters = (
        f"crop={source_width}:{clean_height}:0:0,setsar=1,"
        "split=3[split_bg_src][split_left_src][split_right_src];"
        "[split_bg_src]scale=1920:1080:force_original_aspect_ratio=increase:"
        "force_divisible_by=2:flags=lanczos,crop=1920:1080,gblur=sigma=34,"
        "eq=brightness=-0.22:contrast=1.08:saturation=1.16,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.28:t=fill[split_bg];"
        f"[split_left_src]crop={crop_width}:{crop_height}:{left_x}:{crop_y},"
        f"scale={panel_width}:{panel_height}:flags=lanczos,setsar=1[split_left];"
        f"[split_right_src]crop={crop_width}:{crop_height}:{right_x}:{crop_y},"
        f"scale={panel_width}:{panel_height}:flags=lanczos,setsar=1[split_right];"
        "[split_bg][split_left]overlay=60:70:shortest=1:eof_action=pass[split_stage_1];"
        "[split_stage_1][split_right]overlay=1010:70:shortest=1:eof_action=pass,"
        "drawbox=x=52:y=62:w=866:h=956:color=black@0.68:t=8,"
        f"drawbox=x=55:y=65:w=860:h=950:color={accent}@0.82:t=5,"
        "drawbox=x=1002:y=62:w=866:h=956:color=black@0.68:t=8,"
        f"drawbox=x=1005:y=65:w=860:h=950:color={secondary}@0.82:t=5,"
        "drawbox=x=954:y=70:w=12:h=940:color=white@0.16:t=fill"
    )
    pulses: list[str] = []
    for index, timestamp in enumerate(sorted(emphasis_times or [])[:4]):
        end = timestamp + 0.72
        x = 55 if index % 2 == 0 else 1005
        color = accent if index % 2 == 0 else secondary
        pulses.append(
            f"drawbox=x={x}:y=65:w=860:h=950:color={color}@0.98:t=10:"
            f"enable='between(t,{timestamp:.3f},{end:.3f})'"
        )
    return ",".join([filters, *pulses])


def landscape_compilation_edit_filter(
    duration: float,
    hook_text_filename: str,
    *,
    section_number: int,
    section_count: int,
    editorial_text_filename: str = "",
    theme_profile: dict[str, str] | None = None,
    emphasis_times: list[float] | None = None,
    show_text_overlays: bool = True,
) -> str:
    """Long-form motion language: chapter cards, sparse emphasis, and cinematic grading."""
    safe_duration = max(0.1, duration)
    fade_out_start = max(0.0, safe_duration - 0.30)
    profile = theme_profile or {
        "accent": "#FACC15",
        "accent_secondary": "#22D3EE",
        "badge": "RANGKUMAN UTAMA",
        "emphasis_label": "POIN PENTING",
        "grade": "eq=contrast=1.05:brightness=0.004:saturation=1.04:gamma=1.01",
    }
    accent = profile["accent"]
    secondary = profile.get("accent_secondary", "#22D3EE")
    badge = "HOOK UTAMA" if section_number == 1 else f"POIN {section_number:02}"
    section_text = f"BAGIAN {section_number:02} / {section_count:02}"
    filters = [
        profile["grade"],
        "vignette=PI/12",
        "fade=t=in:st=0:d=0.28",
        f"fade=t=out:st={fade_out_start:.3f}:d=0.30",
    ]
    intro_end = min(safe_duration, 4.8)
    if show_text_overlays and intro_end > 0.6:
        filters.extend(
            [
                "drawbox=x=74:y=64:w=660:h=196:color=black@0.72:t=fill:"
                f"enable='between(t,0.10,{intro_end:.3f})'",
                f"drawbox=x=74:y=64:w=12:h=196:color={accent}@0.98:t=fill:"
                f"enable='between(t,0.10,{intro_end:.3f})'",
                f"drawbox=x=98:y=82:w=190:h=42:color={accent}@0.94:t=fill:"
                f"enable='between(t,0.10,{intro_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{badge}':expansion=none:fontcolor=white:fontsize=22:x=116:y=91:"
                f"enable='between(t,0.10,{intro_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                f"text='{section_text}':expansion=none:fontcolor={secondary}:fontsize=19:x=310:y=92:"
                f"enable='between(t,0.10,{intro_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"textfile='{hook_text_filename}':reload=0:expansion=none:"
                "fontcolor=white:fontsize=38:line_spacing=8:borderw=2:bordercolor=black@0.82:"
                f"x=108:y=145:enable='between(t,0.10,{intro_end:.3f})'",
            ]
        )

    editorial_start = min(safe_duration, 5.20)
    editorial_end = min(safe_duration, 9.40)
    if (
        show_text_overlays
        and editorial_text_filename
        and editorial_end - editorial_start >= 1.2
    ):
        filters.extend(
            [
                "drawbox=x=98:y=816:w=1030:h=170:color=black@0.68:t=fill:"
                f"enable='between(t,{editorial_start:.3f},{editorial_end:.3f})'",
                f"drawbox=x=98:y=816:w=10:h=170:color={secondary}@0.98:t=fill:"
                f"enable='between(t,{editorial_start:.3f},{editorial_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='CATATAN EDITOR':expansion=none:fontcolor={secondary}:fontsize=21:"
                f"x=132:y=838:enable='between(t,{editorial_start:.3f},{editorial_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                f"textfile='{editorial_text_filename}':reload=0:expansion=none:"
                "fontcolor=white:fontsize=29:line_spacing=6:borderw=1:bordercolor=black@0.78:"
                f"x=132:y=878:enable='between(t,{editorial_start:.3f},{editorial_end:.3f})'",
            ]
        )

    for timestamp in sorted(emphasis_times or [])[:3]:
        if timestamp >= safe_duration - 0.5:
            continue
        pulse_end = min(safe_duration, timestamp + 0.38)
        label_end = min(safe_duration, timestamp + 1.45)
        filters.extend(
            [
                f"drawbox=x=32:y=22:w=1856:h=1036:color={accent}@0.62:t=5:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
                "drawbox=x=1430:y=86:w=398:h=88:color=black@0.72:t=fill:"
                f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                f"drawbox=x=1430:y=86:w=8:h=88:color={accent}@0.98:t=fill:"
                f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
            ]
        )
        if show_text_overlays:
            filters.append(
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{profile['emphasis_label']}':expansion=none:fontcolor=white:fontsize=25:"
                f"x=1462:y=115:enable='between(t,{timestamp:.3f},{label_end:.3f})'"
            )

    filters.extend(
        [
            "drawbox=x=0:y=1072:w=iw:h=8:color=black@0.45:t=fill",
            f"drawbox=x=0:y=1072:w='max(2,iw*t/{safe_duration:.3f})':"
            f"h=8:color={accent}@0.94:t=fill",
        ]
    )
    return ",".join(filters)


def modern_gradient_border_filters(accent: str, secondary: str) -> list[str]:
    """Build a dual-tone frame with a light tracer that runs around its edge."""
    return [
        f"drawbox=x=30:y=61:w=1020:h=1798:color={secondary}@0.20:t=12",
        f"drawbox=x=35:y=66:w=1010:h=1788:color={accent}@0.62:t=7",
        "drawbox=x=39:y=70:w=1002:h=1780:color=white@0.22:t=2",
        (
            "drawbox=x='35+775*mod(t,4.8)/1.2':y=66:w=225:h=7:"
            f"color={secondary}@0.98:t=fill:enable='between(mod(t,4.8),0,1.2)'"
        ),
        (
            "drawbox=x=1038:y='66+1521*(mod(t,4.8)-1.2)/1.2':w=7:h=260:"
            f"color={accent}@0.98:t=fill:enable='between(mod(t,4.8),1.2,2.4)'"
        ),
        (
            "drawbox=x='810-775*(mod(t,4.8)-2.4)/1.2':y=1847:w=225:h=7:"
            f"color={secondary}@0.98:t=fill:enable='between(mod(t,4.8),2.4,3.6)'"
        ),
        (
            "drawbox=x=35:y='1587-1521*(mod(t,4.8)-3.6)/1.2':w=7:h=260:"
            f"color={accent}@0.98:t=fill:enable='between(mod(t,4.8),3.6,4.8)'"
        ),
    ]


def intro_particle_burst_filters(accent: str, secondary: str) -> list[str]:
    """Add a brief edge-safe sparkle burst during the opening zoom-out."""
    return [
        (
            "drawbox=x='86+150*t':y='92+105*t':w=9:h=9:"
            f"color={accent}@0.92:t=fill:enable='between(t,0.04,0.72)'"
        ),
        (
            "drawbox=x='246+70*t':y='76+178*t':w=5:h=5:"
            f"color={secondary}@0.88:t=fill:enable='between(t,0.10,0.64)'"
        ),
        (
            "drawbox=x='950-130*t':y='102+130*t':w=7:h=7:"
            "color=white@0.82:t=fill:enable='between(t,0.08,0.68)'"
        ),
        (
            "drawbox=x='1010-165*t':y='370+72*t':w=11:h=11:"
            f"color={accent}@0.86:t=fill:enable='between(t,0.16,0.78)'"
        ),
        (
            "drawbox=x='72+155*t':y='1480-95*t':w=6:h=6:"
            "color=white@0.78:t=fill:enable='between(t,0.12,0.66)'"
        ),
        (
            "drawbox=x='995-145*t':y='1600-120*t':w=8:h=8:"
            f"color={secondary}@0.90:t=fill:enable='between(t,0.18,0.82)'"
        ),
        (
            "drawbox=x='210+92*t':y='1810-155*t':w=10:h=10:"
            f"color={accent}@0.82:t=fill:enable='between(t,0.22,0.84)'"
        ),
        (
            "drawbox=x='828-76*t':y='1828-188*t':w=5:h=5:"
            f"color={secondary}@0.88:t=fill:enable='between(t,0.14,0.70)'"
        ),
    ]


def clean_detail_edit_filter(
    duration: float,
    hook_text_filename: str,
    *,
    cover_text_filename: str = "",
    show_progress: bool = True,
    theme_profile: dict[str, str] | None = None,
    emphasis_times: list[float] | None = None,
    show_text_overlays: bool = True,
    reaction_cues: list[ReactionCue] | None = None,
    show_reactions: bool = True,
    camera_angle_cues: list[CameraAngleCue] | None = None,
    detail_filter: str = "",
) -> str:
    """Keep source detail clean while adding sparse, story-timed visual rhythm."""
    safe_duration = max(0.1, duration)
    profile = theme_profile or {
        "theme": "knowledge",
        "accent": "#FACC15",
        "accent_secondary": "#22D3EE",
    }
    theme = profile.get("theme", "knowledge")
    accent = profile.get("accent", "#FACC15")
    clean_grades = {
        "mystery": "eq=contrast=1.025:brightness=-0.004:saturation=0.99:gamma=0.998",
        "islamic": "eq=contrast=1.020:brightness=0.003:saturation=1.025:gamma=1.004",
        "warning": "eq=contrast=1.025:brightness=0.001:saturation=1.02:gamma=1.0",
        "inspiring": "eq=contrast=1.018:brightness=0.004:saturation=1.03:gamma=1.005",
        "knowledge": "eq=contrast=1.020:brightness=0.002:saturation=1.02:gamma=1.002",
    }

    zoom_terms = ["16*max(0,1-t/0.55)"]
    x_terms: list[str] = []
    y_terms: list[str] = []
    for cue in camera_angle_cues or []:
        if cue.end <= cue.start:
            continue
        active = f"between(t,{cue.start:.3f},{cue.end:.3f})"
        cue_duration = cue.end - cue.start
        settle = f"sin(PI*(t-{cue.start:.3f})/{cue_duration:.3f})"
        zoom_terms.append(f"if({active},{cue.zoom_pixels}+3*{settle},0)")
        x_terms.append(f"{cue.x_offset}*{active}")
        y_terms.append(f"{cue.y_offset}*{active}")

    scale_expression = "1080+" + "+".join(zoom_terms)
    x_motion = "+".join(x_terms) or "0"
    y_motion = "+".join(y_terms) or "0"
    filters = [
        clean_grades.get(theme, clean_grades["knowledge"]),
        (
            "scale=w="
            f"'trunc(({scale_expression})/2)*2':"
            "h=-2:eval=frame:flags=lanczos"
        ),
        "crop=1080:1920:"
        f"x='(iw-ow)/2+{x_motion}':"
        f"y='(ih-oh)/2+{y_motion}'",
        "setsar=1",
    ]
    if detail_filter:
        filters.append(detail_filter)

    if show_text_overlays:
        title_filename = cover_text_filename or hook_text_filename
        if title_filename:
            filters.append(viral_title_overlay_filter(title_filename, safe_duration))

    # A short edge cue marks only the strongest transcript beats. It adds
    # rhythm without a card, vignette, gradient, or element over the face.
    for timestamp in sorted(emphasis_times or [])[:2]:
        pulse_end = min(safe_duration, timestamp + 0.24)
        filters.extend(
            [
                f"drawbox=x=40:y=70:w=1000:h=3:color={accent}@0.82:t=fill:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
                f"drawbox=x=40:y=1847:w=1000:h=3:color={accent}@0.72:t=fill:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
            ]
        )

    if show_reactions:
        strong_reactions = [
            cue
            for cue in (reaction_cues or [])
            if cue.kind in {"laugh", "shock", "pray", "warning"}
        ][:1]
        filters.extend(
            reaction_overlay_filter(cue, index)
            for index, cue in enumerate(strong_reactions, start=1)
        )

    if show_progress:
        filters.append(
            f"drawbox=x=0:y=1916:w='max(2,iw*t/{safe_duration:.3f})':"
            f"h=4:color={accent}@0.78:t=fill"
        )
    return ",".join(filters)


def enhanced_edit_filter(
    duration: float,
    hook_text_filename: str,
    *,
    pov_text_filename: str = "",
    cover_text_filename: str = "",
    show_progress: bool = True,
    theme_profile: dict[str, str] | None = None,
    emphasis_times: list[float] | None = None,
    variation: int = 0,
    show_text_overlays: bool = True,
    reaction_cues: list[ReactionCue] | None = None,
    show_reactions: bool = True,
    codex_plan: CodexEditPlan | None = None,
    payoff_text_filename: str = "",
    cinematic_pov_windows: list[tuple[float, float]] | None = None,
    camera_angle_cues: list[CameraAngleCue] | None = None,
) -> str:
    """Add context-aware motion graphics while keeping faces and captions readable."""
    safe_duration = max(0.1, duration)
    profile = theme_profile or {
        "theme": "knowledge",
        "accent": "#FACC15",
        "accent_secondary": "#22D3EE",
        "badge": "FAKTA / PELAJARAN",
        "emphasis_label": "POIN PENTING",
        "grade": "eq=contrast=1.05:brightness=0.004:saturation=1.04:gamma=1.01",
    }
    accent = profile["accent"]
    accent_secondary = profile.get("accent_secondary", "#22D3EE")
    badge = profile["badge"]
    emphasis_label = profile["emphasis_label"]
    grade = profile["grade"]
    motion_variant = max(0, variation) % 6
    scale_width = (1120, 1140, 1160, 1130, 1150, 1170)[motion_variant]
    scale_height = int(round(scale_width * 16 / 9))
    if scale_height % 2:
        scale_height += 1
    center_x = (scale_width - 1080) / 2
    center_y = (scale_height - 1920) / 2
    amp_x = min(12.0, max(4.0, center_x - 2))
    amp_y = min(16.0, max(6.0, center_y - 2))
    x_period, y_period = (
        (7, 5),
        (6, 6),
        (5, 7),
        (8, 5),
        (7, 7),
        (6, 8),
    )[motion_variant]
    intro_zoom_pixels = (70, 78, 86, 74, 82, 90)[motion_variant]
    pov_zoom_terms: list[str] = []
    pov_x_terms: list[str] = []
    pov_y_terms: list[str] = []
    camera_positions = (
        (12, -8),
        (-12, -6),
        (10, 12),
        (-10, 10),
        (14, 2),
        (-14, 4),
    )
    for index, (start, end) in enumerate(cinematic_pov_windows or []):
        if end <= start:
            continue
        duration_value = end - start
        phase = f"sin(PI*(t-{start:.3f})/{duration_value:.3f})"
        x_offset, y_offset = camera_positions[
            (motion_variant * 3 + index * 2) % len(camera_positions)
        ]
        zoom_pixels = 24 + ((motion_variant + index) % 3) * 4
        active = f"between(t,{start:.3f},{end:.3f})"
        pov_zoom_terms.append(f"if({active},{zoom_pixels}*{phase},0)")
        pov_x_terms.append(f"{x_offset}*{phase}*{active}")
        pov_y_terms.append(f"{y_offset}*{phase}*{active}")
    angle_zoom_terms: list[str] = []
    angle_x_terms: list[str] = []
    angle_y_terms: list[str] = []
    for cue in camera_angle_cues or []:
        if cue.end <= cue.start:
            continue
        active = f"between(t,{cue.start:.3f},{cue.end:.3f})"
        cue_duration = cue.end - cue.start
        settle = f"sin(PI*(t-{cue.start:.3f})/{cue_duration:.3f})"
        angle_zoom_terms.append(
            f"if({active},{cue.zoom_pixels}+6*{settle},0)"
        )
        angle_x_terms.append(f"{cue.x_offset}*{active}")
        angle_y_terms.append(f"{cue.y_offset}*{active}")
    scale_expression = (
        f"{scale_width}+{intro_zoom_pixels}*max(0,1-t/0.72)"
        + "".join(
            f"+{term}"
            for term in (
                angle_zoom_terms
                if camera_angle_cues is not None
                else pov_zoom_terms
            )
        )
    )
    if camera_angle_cues is not None:
        # Hard activation at a speech boundary reads like a second camera cut;
        # the tiny settle motion keeps the digital crop from feeling frozen.
        x_motion = "+".join(angle_x_terms) or "0"
        y_motion = "+".join(angle_y_terms) or "0"
    elif cinematic_pov_windows is None:
        x_motion = f"{amp_x:.1f}*sin(2*PI*t/{x_period})"
        y_motion = f"{amp_y:.1f}*sin(2*PI*t/{y_period})"
    else:
        x_motion = "+".join(pov_x_terms) or "0"
        y_motion = "+".join(pov_y_terms) or "0"
    badge_width = min(430, max(250, len(badge) * 17 + 60))
    adaptive_plan = codex_plan or CodexEditPlan()
    filters = [
        grade,
        (
            "scale=w="
            f"'trunc(({scale_expression})/2)*2':"
            "h=-2:eval=frame:flags=lanczos"
        ),
        "crop=1080:1920:"
        f"x='(iw-ow)/2+{x_motion}':"
        f"y='(ih-oh)/2+{y_motion}'",
        "setsar=1",
        "vignette=PI/9",
        modern_blurred_video_frame_filter(accent, accent_secondary),
    ]
    filters.extend(modern_gradient_border_filters(accent, accent_secondary))
    filters.extend(intro_particle_burst_filters(accent, accent_secondary))
    if adaptive_plan.hook_boost:
        filters.extend(
            [
                f"drawbox=x=24:y=55:w=1032:h=1810:color={accent}@0.88:t=10:"
                "enable='between(t,0.05,0.58)'",
                "drawbox=x=0:y=0:w=iw:h=ih:color=white@0.08:t=fill:"
                "enable='between(t,0.08,0.20)'",
            ]
        )
    if show_text_overlays:
        # Keep the source moving and put the truthful, transcript-derived title
        # in the face/UI-safe upper third. The strong black outline mirrors the
        # fast-scanning title style commonly used in Shorts grids.
        cover_end = min(safe_duration, SHORTS_TITLE_OVERLAY_SECONDS)
        if cover_text_filename and cover_end >= 0.4:
            filters.append(viral_title_overlay_filter(cover_text_filename, safe_duration))
        else:
            hook_start = 0.10
            filters.extend(
                [
                    f"drawbox=x=56:y=1092:w={badge_width}:h=48:color={accent}@0.92:t=fill:"
                    f"enable='between(t,{hook_start:.2f},3.80)'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='{badge}':expansion=none:fontcolor=white:fontsize=23:"
                    f"x=76:y=1103:enable='between(t,{hook_start:.2f},3.80)'",
                    "drawbox=x=56:y=1150:w=844:h=220:color=black@0.46:t=fill:"
                    f"enable='between(t,{hook_start:.2f},3.80)'",
                    f"drawbox=x=56:y=1150:w=14:h=220:color={accent}@0.98:t=fill:"
                    f"enable='between(t,{hook_start:.2f},3.80)'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"textfile='{hook_text_filename}':reload=0:expansion=none:"
                    "fontcolor=white:fontsize=48:line_spacing=10:borderw=2:bordercolor=black@0.85:"
                    f"x='if(lt(t,{hook_start + 0.38:.2f}),-text_w+(t-{hook_start:.2f})*"
                    "(84+text_w)/0.38,84)':y=1192:"
                    f"enable='between(t,{hook_start:.2f},3.80)'",
                ]
            )
        if pov_text_filename:
            pov_end = min(safe_duration, 9.2)
            if pov_end > 4.2:
                filters.extend(
                    [
                        "drawbox=x=70:y=1138:w=830:h=116:color=black@0.52:t=fill:"
                        f"enable='between(t,4.20,{pov_end:.3f})'",
                        f"drawbox=x=70:y=1138:w=9:h=116:color={accent_secondary}@0.96:t=fill:"
                        f"enable='between(t,4.20,{pov_end:.3f})'",
                        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                        f"text='POV':expansion=none:fontcolor={accent_secondary}:fontsize=20:"
                        f"x=100:y=1156:enable='between(t,4.20,{pov_end:.3f})'",
                        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                        f"textfile='{pov_text_filename}':reload=0:expansion=none:"
                        "fontcolor=white:fontsize=27:line_spacing=5:borderw=1:bordercolor=black@0.82:"
                        f"x=100:y=1188:enable='between(t,4.20,{pov_end:.3f})'",
                    ]
                )
        # Subtle pattern interrupts inside the first 30 seconds. These are
        # intentionally brief so the edit feels alive without covering speech.
        retention_times = (7.0, 14.0, 22.0) if adaptive_plan.tempo_boost else (12.0, 24.0)
        for retention_time in retention_times:
            if retention_time >= safe_duration - 1.0:
                continue
            retention_end = min(safe_duration, retention_time + 0.32)
            filters.extend(
                [
                    f"drawbox=x=35:y=66:w=1010:h=7:color={accent_secondary}@0.96:t=fill:"
                    f"enable='between(t,{retention_time:.3f},{retention_end:.3f})'",
                    f"drawbox=x=35:y=1847:w=1010:h=7:color={accent}@0.88:t=fill:"
                    f"enable='between(t,{retention_time:.3f},{retention_end:.3f})'",
                ]
            )
    visual_emphasis_times = list(emphasis_times or [])
    for cue in reaction_cues or []:
        if cue.kind == "important" and all(
            abs(cue.start - timestamp) >= 1.0
            for timestamp in visual_emphasis_times
        ):
            visual_emphasis_times.append(cue.start)
    visual_emphasis_times = sorted(visual_emphasis_times)[:4]

    for timestamp in visual_emphasis_times:
        pulse_end = min(safe_duration, timestamp + 0.42)
        label_end = min(safe_duration, timestamp + 1.35)
        filters.extend(
            [
                f"drawbox=x=30:y=61:w=1020:h=1798:color={accent}@0.68:t=7:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
                f"drawbox=x=39:y=70:w=1002:h=1780:color=white@0.26:t=3:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
            ]
        )
        if show_text_overlays:
            filters.extend(
                [
                    "drawbox=x=500:y=382:w=400:h=108:color=black@0.74:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    f"drawbox=x=500:y=382:w=400:h=7:color={accent}@0.98:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    f"drawbox=x=518:y=408:w=58:h=58:color={accent}@0.98:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    "text='!':expansion=none:fontcolor=white:fontsize=38:"
                    f"x=540:y=411:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='NOTICE':expansion=none:fontcolor={accent_secondary}:fontsize=17:"
                    f"x=596:y=400:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='{emphasis_label}':expansion=none:fontcolor=white:fontsize=25:"
                    f"x=596:y=426:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    f"drawbox=x=500:y=484:w=400:h=3:color={accent_secondary}@0.74:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                ]
            )
    if show_text_overlays and payoff_text_filename:
        card_start = max(0.2, safe_duration - 3.35)
        card_end = max(card_start + 0.2, safe_duration - 1.28)
        filters.extend(
            [
                "drawbox=x=56:y=1138:w=844:h=224:color=black@0.56:t=fill:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                f"drawbox=x=56:y=1138:w=14:h=224:color={accent_secondary}@0.98:t=fill:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                f"drawbox=x=76:y=1156:w=244:h=42:color={accent}@0.94:t=fill:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                "text='INTISARI':expansion=none:fontcolor=white:fontsize=20:x=94:y=1165:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"textfile='{payoff_text_filename}':reload=0:expansion=none:"
                "fontcolor=white:fontsize=39:line_spacing=8:borderw=2:bordercolor=black@0.86:"
                f"x=82:y=1224:enable='between(t,{card_start:.3f},{card_end:.3f})'",
            ]
        )
    if show_text_overlays and adaptive_plan.loop_boost:
        # Keep the payoff visible. A brief frame accent marks the semantic loop;
        # autoplay itself reveals the hook again without a forced callback card.
        loop_start = max(0.2, safe_duration - 0.28)
        loop_end = max(loop_start + 0.1, safe_duration - 0.03)
        filters.extend(
            [
                f"drawbox=x=30:y=61:w=1020:h=1798:color={accent}@0.72:t=7:"
                f"enable='between(t,{loop_start:.3f},{loop_end:.3f})'"
            ]
        )
    if show_reactions:
        filters.extend(
            reaction_overlay_filter(cue, index)
            for index, cue in enumerate(reaction_cues or [], start=1)
        )
    if show_progress:
        filters.extend(
            [
                "drawbox=x=0:y=1888:w=iw:h=12:color=black@0.45:t=fill",
                f"drawbox=x=0:y=1888:w='max(2,iw*t/{safe_duration:.3f})':"
                f"h=12:color={accent}@0.96:t=fill",
            ]
        )
    return ",".join(filters)


def subtitle_cues(
    segments: list[TranscriptSegment],
    offset: float,
    clip_duration: float,
) -> list[tuple[float, float, str]]:
    """Split speech into compact cues and distribute time by word count."""
    cues: list[tuple[float, float, str]] = []
    for item in segments:
        start = max(0, item.start - offset)
        end = min(clip_duration, max(start + 0.2, item.end - offset))
        if start >= clip_duration or end - start < 0.45:
            continue

        chunks = split_subtitle_text(item.text)
        weights = [max(1, len(re.findall(r"[\w']+", chunk))) for chunk in chunks]
        total_weight = max(1, sum(weights))
        elapsed_weight = 0
        for chunk_idx, chunk in enumerate(chunks):
            chunk_start = start + (end - start) * elapsed_weight / total_weight
            elapsed_weight += weights[chunk_idx]
            chunk_end = (
                end
                if chunk_idx == len(chunks) - 1
                else start + (end - start) * elapsed_weight / total_weight
            )
            cues.append((chunk_start, chunk_end, chunk))
    return cues


def write_srt(path: Path, segments: list[TranscriptSegment], offset: float, clip_duration: float) -> None:
    lines: list[str] = []
    for cue_index, (chunk_start, chunk_end, chunk) in enumerate(
        subtitle_cues(segments, offset, clip_duration),
        start=1,
    ):
        lines.extend(
            [
                str(cue_index),
                f"{seconds_to_stamp(chunk_start, srt=True)} --> {seconds_to_stamp(chunk_end, srt=True)}",
                chunk,
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


CaptionPosition = Literal["upper", "center", "bottom"]


# Fonts installed in the backend container (see Dockerfile). Map the FE choice
# to a real installed family name; anything else falls back to the default.
AVAILABLE_FONTS = {
    "DejaVu Sans": "DejaVu Sans",
    "DejaVu Serif": "DejaVu Serif",
    "Liberation Sans": "Liberation Sans",
    "Liberation Serif": "Liberation Serif",
    "Noto Sans": "Noto Sans",
}
DEFAULT_FONT = "DejaVu Sans"
CHANNEL_WATERMARK = "@ryuundyofficial"
SOFT_CAPTION_BACK_COLOR = "&HC8000000"
SOFT_CAPTION_SHADOW = 0.35


@dataclass
class CaptionStyle:
    font_size: int = 8
    position: CaptionPosition = "bottom"
    color: str = "#FFFFFF"
    font_family: str = DEFAULT_FONT
    outline_width: float = 0.5
    outline_color: str = "#000000"


def _hex_to_ass_color(hex_color: str) -> str:
    value = hex_color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return "&H00FFFFFF"
    red, green, blue = value[0:2], value[2:4], value[4:6]
    # ASS uses &HAABBGGRR (alpha first, then BGR).
    return f"&H00{blue}{green}{red}".upper()


def build_subtitle_style(caption: CaptionStyle) -> str:
    font_size = max(6, min(120, caption.font_size))
    primary = _hex_to_ass_color(caption.color)
    outline_color = _hex_to_ass_color(caption.outline_color)
    outline = max(0.0, min(8.0, caption.outline_width))
    font_name = AVAILABLE_FONTS.get(caption.font_family, DEFAULT_FONT)
    # libass margins use the default script resolution (PlayResY=288), so these
    # values are in ~288-unit space, not raw pixels of the 1920px frame.
    # FFmpeg's SRT-to-ASS bridge uses legacy SSA alignment codes:
    # 2 = bottom-center, 6 = top-center, 10 = middle-center.
    if caption.position == "bottom":
        alignment = 2
        margin_v = 50
    elif caption.position == "upper":
        alignment = 6
        margin_v = 70
    else:
        alignment = 10
        margin_v = 0
    return (
        f"FontName={font_name},FontSize={font_size},Bold=1,PrimaryColour={primary},"
        f"OutlineColour={outline_color},BackColour={SOFT_CAPTION_BACK_COLOR},"
        f"BorderStyle=1,Outline={outline},Shadow={SOFT_CAPTION_SHADOW},Blur=0.35,"
        f"Alignment={alignment},MarginL=36,MarginR=36,MarginV={margin_v},WrapStyle=0"
    )


def _ass_timestamp(seconds: float) -> str:
    total_centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(total_centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{whole_seconds:02}.{centiseconds:02}"


def _ass_escape(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", r"\N")
    )


def highlight_caption_keyword(text: str, accent: str = "#FACC15") -> str:
    """Highlight one transcript-grounded keyword without changing the quote."""
    signal_words = (
        (HOOK_WORDS - WEAK_STARTS)
        | PAYOFF_WORDS
        | TENSION_WORDS
        | IMPORTANT_WORDS
        | MYSTERY_WORDS
    )
    matches = list(re.finditer(r"[\w']+", text, flags=re.UNICODE))
    candidates = [
        match
        for match in matches
        if match.group(0).casefold() in signal_words
        or re.fullmatch(r"\d+(?:[.,]\d+)?", match.group(0))
    ]
    if not candidates:
        candidates = [match for match in matches if len(match.group(0)) >= 7]
    if not candidates:
        return _ass_escape(text)

    chosen = max(candidates, key=lambda match: (len(match.group(0)), -match.start()))
    primary = _hex_to_ass_color(accent)
    before = _ass_escape(text[: chosen.start()])
    keyword = _ass_escape(text[chosen.start() : chosen.end()])
    after = _ass_escape(text[chosen.end() :])
    return (
        before
        + "{" + rf"\c{primary}&\fscx108\fscy108" + "}"
        + keyword
        + r"{\rCaption}"
        + after
    )


def write_dynamic_ass(
    path: Path,
    segments: list[TranscriptSegment],
    offset: float,
    clip_duration: float,
    caption: CaptionStyle,
    *,
    accent: str = "#FACC15",
) -> int:
    """Write keyword-highlighted captions inside the Shorts UI-safe region."""
    font_name = AVAILABLE_FONTS.get(caption.font_family, DEFAULT_FONT)
    font_size = max(40, min(112, round(max(6, min(120, caption.font_size)) * 6.7)))
    primary = _hex_to_ass_color(caption.color)
    outline_color = _hex_to_ass_color(caption.outline_color)
    outline = max(2.0, min(12.0, caption.outline_width * 6.0))
    if caption.position == "upper":
        alignment, margin_v = 8, SHORTS_SAFE_TOP + 130
    elif caption.position == "center":
        alignment, margin_v = 5, 0
    else:
        alignment, margin_v = 2, 1920 - SHORTS_SAFE_BOTTOM + 5

    cues = subtitle_cues(segments, offset, clip_duration)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font_name},{font_size},{primary},&H0000D7FF,{outline_color},&H90000000,-1,0,0,0,100,100,0,0,1,{outline:.1f},1.2,{alignment},110,230,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = [
        "Dialogue: 0,"
        f"{_ass_timestamp(start)},{_ass_timestamp(end)},Caption,,0,0,0,,"
        f"{highlight_caption_keyword(text, accent)}"
        for start, end, text in cues
    ]
    path.write_text(header + "\n".join(events) + ("\n" if events else ""), encoding="utf-8")
    return len(events)


def channel_watermark_filter(output_format: str) -> str:
    """Render a small, readable channel signature away from captions and faces."""
    if output_format == "landscape_compilation":
        x_position = "w-text_w-42"
        y_position = "38"
        font_size = 22
    else:
        x_position = "62"
        y_position = "98"
        font_size = 24
    return (
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{CHANNEL_WATERMARK}':expansion=none:"
        f"fontcolor=white@0.90:fontsize={font_size}:"
        "borderw=1:bordercolor=black@0.82:"
        "box=1:boxcolor=black@0.38:boxborderw=9:"
        "shadowcolor=black@0.78:shadowx=2:shadowy=2:"
        f"x='{x_position}':y={y_position}"
    )


THUMBNAIL_SYSTEM_PROMPT = (
    "You write prompts for an AI image generator that will ONLY add a text overlay onto a "
    "provided screenshot. The screenshot is the thumbnail background and must NOT be redrawn, "
    "restyled, or replaced. Make the hook intriguing but faithful to the transcript. For mystery, "
    "myth, supernatural, or horror topics, never present an unverified claim as religious fact. "
    "Never mention, thank, credit, or promote the source channel, another channel, TV station, "
    "media brand, uploader, or sponsor in either the hook or prompt. "
    "Reply ONLY with strict JSON, no markdown."
)


def grab_frame_at(
    video_path: Path,
    timestamp: float,
    thumb_path: Path,
    *,
    label: str,
) -> Path | None:
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        run(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path.resolve()),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(thumb_path.name),
            ],
            cwd=thumb_path.parent,
        )
    except RuntimeError as exc:
        console.print(f"[yellow]Thumbnail frame failed for {label}:[/yellow] {exc}")
        return None
    return thumb_path if thumb_path.exists() else None


def grab_best_frame(video_path: Path, clip: ClipCandidate, thumb_path: Path) -> Path | None:
    # Best moment heuristic: sample the clip's middle, where the payoff usually lands.
    timestamp = clip.start + max(0.0, (clip.end - clip.start) * 0.5)
    return grab_frame_at(video_path, timestamp, thumb_path, label=f"clip {clip.index}")


def designed_thumbnail_filter(
    headline_filename: str,
    support_filename: str,
    *,
    long_form: bool,
    accent: str,
    accent_secondary: str,
) -> str:
    """Create a deterministic high-contrast cover without redrawing the subject."""
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if long_form:
        return ",".join(
            [
                "scale=1280:720:force_original_aspect_ratio=increase:flags=lanczos",
                "crop=1280:720",
                "eq=contrast=1.08:brightness=-0.015:saturation=1.10",
                "drawbox=x=0:y=0:w=760:h=720:color=black@0.56:t=fill",
                f"drawbox=x=0:y=0:w=18:h=720:color={accent}@0.98:t=fill",
                f"drawbox=x=66:y=72:w=282:h=54:color={accent}@0.96:t=fill",
                f"drawtext=fontfile={font_bold}:text='RESUME CERITA':expansion=none:"
                "fontcolor=white:fontsize=25:x=92:y=84",
                f"drawtext=fontfile={font_bold}:textfile='{headline_filename}':reload=0:"
                "expansion=none:fontcolor=white:fontsize=58:line_spacing=10:"
                "borderw=3:bordercolor=black@0.90:shadowcolor=black@0.82:"
                "shadowx=3:shadowy=3:x=68:y=170",
                f"drawbox=x=68:y=492:w=570:h=6:color={accent_secondary}@0.96:t=fill",
                f"drawtext=fontfile={font_regular}:textfile='{support_filename}':reload=0:"
                "expansion=none:fontcolor=white@0.94:fontsize=27:line_spacing=6:"
                "borderw=2:bordercolor=black@0.82:x=70:y=520",
                f"drawbox=x=38:y=34:w=1204:h=652:color={accent_secondary}@0.38:t=5",
            ]
        )
    return ",".join(
        [
            "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos",
            "crop=1080:1920",
            "eq=contrast=1.09:brightness=-0.018:saturation=1.11",
            viral_title_overlay_filter(headline_filename, SHORTS_TITLE_OVERLAY_SECONDS),
        ]
    )


def render_designed_thumbnail(
    video_path: Path,
    timestamp: float,
    thumb_path: Path,
    copy: dict[str, str],
    *,
    long_form: bool,
    theme_profile: dict[str, str] | None = None,
    label: str,
) -> Path | None:
    """Render the final upload-ready thumbnail from an actual video frame."""
    profile = theme_profile or {
        "accent": "#FACC15",
        "accent_secondary": "#22D3EE",
    }
    headline_path = thumb_path.with_suffix(".headline.txt")
    support_path = thumb_path.with_suffix(".support.txt")
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    thumb_path.unlink(missing_ok=True)
    headline_path.write_text(copy.get("headline", "") + "\n", encoding="utf-8")
    support_path.write_text(copy.get("support", "") + "\n", encoding="utf-8")
    vf = designed_thumbnail_filter(
        headline_path.name,
        support_path.name,
        long_form=long_form,
        accent=profile.get("accent", "#FACC15"),
        accent_secondary=profile.get("accent_secondary", "#22D3EE"),
    )
    try:
        run(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{max(0.0, timestamp):.3f}",
                "-i",
                str(video_path.resolve()),
                "-frames:v",
                "1",
                "-vf",
                vf,
                "-q:v",
                "3",
                str(thumb_path.name),
            ],
            cwd=thumb_path.parent,
        )
    except RuntimeError as exc:
        console.print(f"[yellow]Thumbnail final gagal untuk {label}:[/yellow] {exc}")
        return None
    finally:
        headline_path.unlink(missing_ok=True)
        support_path.unlink(missing_ok=True)
    return thumb_path if thumb_path.exists() else None


def generate_thumbnail_prompt(
    clip: ClipCandidate,
    config: AIConfig,
    *,
    long_form: bool = False,
) -> dict | None:
    fallback_hook = first_sentence(clip.title, max_words=6).upper()
    format_name = "16:9 long-form YouTube" if long_form else "short-form video"
    if not config.enabled or not config.base_url or not config.model:
        return {
            "hook_text": fallback_hook,
            "prompt": (
                f'Create an elegant cinematic, high-CTR {format_name} thumbnail text overlay reading "{fallback_hook}" '
                "onto the provided screenshot. Keep the screenshot itself untouched as the background. "
                "Use a premium editorial hierarchy, restrained accent colors, large high-contrast bold text, and strong 16:9 composition; "
                "do not cover faces, do not redraw or restyle the background image."
            ),
        }

    user_prompt = (
        f"Create a truthful, viral-feeling, elegant cinematic {format_name} thumbnail text overlay plan for this clip. The user already has a screenshot "
        "(the best moment) and will feed it plus your prompt to an image generator that only writes text.\n"
        "Return JSON exactly like:\n"
        '{"hook_text": "<3-6 word punchy hook, ALL CAPS>", '
        '"prompt": "<instruction for the image generator: what text to write, where to place it, '
        'style (premium editorial, bold, high contrast, restrained accent, outline), and an explicit rule to keep the screenshot background '
        'unchanged and not cover key subjects>"}\n\n'
        f"Clip title: {clip.title}\n"
        f"Clip transcript: {clip.text[:1000]}"
    )
    try:
        content = chat_completion(
            config,
            [
                {"role": "system", "content": THUMBNAIL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        parsed = extract_json(content)
    except Exception as exc:
        if not disable_unavailable_ai(config, exc):
            console.print(f"[yellow]Thumbnail prompt failed for clip {clip.index}, using fallback:[/yellow] {exc}")
        return {
            "hook_text": fallback_hook,
            "prompt": (
                f'Add a bold thumbnail text overlay reading "{fallback_hook}" onto the provided '
                "screenshot, keeping the screenshot background unchanged."
            ),
        }

    if not isinstance(parsed, dict):
        return None
    hook = parsed.get("hook_text")
    prompt = parsed.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    if is_source_branding_segment(prompt):
        return {
            "hook_text": fallback_hook,
            "prompt": (
                f'Add a bold thumbnail text overlay reading "{fallback_hook}" onto the provided '
                "screenshot, keeping the screenshot background unchanged."
            ),
        }
    safe_hook = (
        hook
        if isinstance(hook, str)
        and hook.strip()
        and not is_source_branding_segment(hook)
        else fallback_hook
    )
    return {
        "hook_text": safe_hook.strip()[:80],
        "prompt": prompt.strip()[:1500],
    }


SOCIAL_CAPTION_SYSTEM_PROMPT = (
    "You are a viral social media copywriter for TikTok, Instagram Reels, and YouTube Shorts. "
    "You write short, scroll-stopping captions in Indonesian that make people want to watch and read. "
    "Open with a strong hook, keep it punchy, add a soft call-to-action, a few relevant emojis, "
    "and 5-8 niche hashtags. For Islamic mystery, myth, supernatural, and horror content, keep the "
    "distinction between religious teaching, story, folklore, personal experience, and verified fact. "
    "Do not invent certainty, medical outcomes, guaranteed financial returns, or allegations about real people. "
    "Phrase unverified current-event statements as the speaker's claim, not an established fact. "
    "Never mention, thank, promote, credit, or ask viewers to follow the source "
    "channel, another channel, TV station, media brand, uploader, or sponsor. Reply ONLY with strict JSON, "
    "no markdown."
)


def _normalize_hashtag(tag: str) -> str:
    cleaned = tag.strip().lstrip("#").strip()
    return f"#{cleaned}" if cleaned else ""


def clip_topic_hashtags(clip: ClipCandidate) -> list[str]:
    words = set(re.findall(r"[\w']+", f"{clip.title} {clip.text}".lower()))
    tags: list[str] = []
    if words.intersection(ISLAMIC_WORDS):
        tags.extend(["#Islam", "#Hikmah"])
    if words.intersection(MYSTERY_WORDS):
        tags.extend(["#Misteri", "#KisahNyata"])
    if "mitos" in words:
        tags.append("#MitosAtauFakta")
    if words.intersection(
        {"angker", "genderuwo", "hantu", "horor", "kuntilanak", "leak", "mistis", "pocong", "seram"}
    ):
        tags.append("#HororIndonesia")
    if words.intersection(INSPIRING_WORDS):
        tags.append("#Inspirasi")
    if not tags:
        tags.extend(["#PelajaranHidup", "#FaktaMenarik"])
    return tags


def fallback_social_caption(
    clip: ClipCandidate,
    required_hashtags: list[str] | None = None,
    *,
    long_form: bool = False,
) -> str:
    theme = detect_visual_theme(clip)
    hook = first_sentence(clip.title, max_words=8).rstrip(" .!?")
    if theme == "mystery":
        body = (
            "Simak konteksnya sampai selesai. Bedakan kisah, mitos, pengalaman, dan fakta—"
            "lalu ambil hikmah tanpa langsung mempercayai klaim yang belum jelas."
        )
        emoji = "🌙"
    elif theme == "islamic":
        body = "Simak sampai selesai dan ambil hikmah yang paling relevan untuk kehidupan sehari-hari."
        emoji = "🤲"
    elif theme == "warning":
        body = "Jangan berhenti di bagian awal—poin terpentingnya ada pada penjelasan lengkapnya."
        emoji = "⚠️"
    else:
        body = "Tonton sampai selesai, lalu tulis bagian mana yang paling membuka sudut pandangmu."
        emoji = "💡"

    ordered: list[str] = []
    seen: set[str] = set()
    format_tags = [] if long_form else ["#Shorts"]
    requested_tags = [
        raw
        for raw in (required_hashtags or [])
        if not long_form or str(raw).strip().lstrip("#").casefold() != "shorts"
    ]
    for raw in [*requested_tags, *clip_topic_hashtags(clip), *format_tags]:
        tag = _normalize_hashtag(str(raw))
        if tag and tag.casefold() not in seen:
            ordered.append(tag)
            seen.add(tag.casefold())
    return f"{emoji} {hook}\n\n{body}\n\n{' '.join(ordered[:8])}"[:2000]


def generate_social_caption(
    clip: ClipCandidate,
    config: AIConfig,
    required_hashtags: list[str] | None = None,
    *,
    long_form: bool = False,
) -> str:
    if not config.enabled or not config.base_url or not config.model:
        return fallback_social_caption(clip, required_hashtags, long_form=long_form)

    format_name = "video kompilasi YouTube 16:9" if long_form else "short clip"
    system_prompt = (
        SOCIAL_CAPTION_SYSTEM_PROMPT.replace(
            "TikTok, Instagram Reels, and YouTube Shorts",
            "YouTube long-form landscape videos",
        ).replace(
            "short, scroll-stopping captions",
            "concise, compelling long-form video descriptions",
        )
        if long_form
        else SOCIAL_CAPTION_SYSTEM_PROMPT
    )
    user_prompt = (
        f"Write a social media post caption (Bahasa Indonesia) for this {format_name}. "
        "Make the first line a hook that stops the scroll and makes people curious to read more.\n"
        "Return JSON exactly like:\n"
        '{"caption": "<hook line\\n\\nbody 1-2 sentences with emojis\\n\\nsoft CTA>", '
        '"hashtags": ["#tag1", "#tag2", ...]}\n\n'
        f"Clip title: {clip.title}\n"
        f"Clip transcript: {clip.text[:1200]}"
    )
    try:
        content = chat_completion(
            config,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        parsed = extract_json(content)
    except Exception as exc:
        if not disable_unavailable_ai(config, exc):
            console.print(f"[yellow]Social caption failed for clip {clip.index}:[/yellow] {exc}")
        return fallback_social_caption(clip, required_hashtags, long_form=long_form)

    if not isinstance(parsed, dict):
        return fallback_social_caption(clip, required_hashtags, long_form=long_form)
    caption = parsed.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        return fallback_social_caption(clip, required_hashtags, long_form=long_form)
    text = caption.strip()
    clean_lines = [
        line
        for line in text.splitlines()
        if not is_source_branding_segment(line)
    ]
    text = "\n".join(clean_lines).strip()
    if not text:
        return fallback_social_caption(clip, required_hashtags, long_form=long_form)

    # Required hashtags always come first, then the AI-generated ones (deduped,
    # case-insensitive). Required tags are guaranteed to be present.
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in list(required_hashtags or []) + (
        parsed.get("hashtags") if isinstance(parsed.get("hashtags"), list) else []
    ):
        tag = _normalize_hashtag(str(raw))
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            ordered.append(tag)
    if ordered:
        if long_form:
            ordered = [tag for tag in ordered if tag.casefold() != "#shorts"]
        text = f"{text}\n\n{' '.join(ordered)}"
    return text[:2000]


def export_clip(
    video_path: Path,
    clip: ClipCandidate,
    clip_segments: list[TranscriptSegment],
    clips_dir: Path,
    burn_subtitles: bool,
    crop_mode: CropMode,
    caption: CaptionStyle | None = None,
    ai_config: AIConfig | None = None,
    cam_corner: str = "auto",
    required_hashtags: list[str] | None = None,
    video_quality: VideoQuality = "high",
    generate_assets: bool = True,
    enforce_size: bool = True,
    base_name_override: str = "",
    enhanced_edit: bool = True,
    remove_running_text: bool = False,
    auto_blur_watermarks: bool = False,
    output_format: OutputFormat = "vertical_short",
    visual_mode: VisualMode = "auto_fyp",
    background_mode: BackgroundMode = "keep",
    compilation_part_number: int = 1,
    compilation_part_count: int = 1,
) -> Path:
    clips_dir.mkdir(parents=True, exist_ok=True)
    base_name = base_name_override or f"clip_{clip.index:02}_{slugify(clip.title)[:72] or 'auto'}"
    srt_path = clips_dir / f"{base_name}.srt"
    ass_path = clips_dir / f"{base_name}.dynamic.ass"
    json_path = clips_dir / f"{base_name}.json"
    out_path = clips_dir / f"{base_name}.mp4"
    temp_video_path = clips_dir / f"{base_name}.video_tmp.mp4"
    temp_audio_path = clips_dir / f"{base_name}.audio_tmp.wav"
    temp_cta_audio_path = clips_dir / f"{base_name}.audio_cta_tmp.wav"
    hook_text_path = clips_dir / f"{base_name}.hook.txt"
    pov_text_path = clips_dir / f"{base_name}.pov.txt"
    cover_text_path = clips_dir / f"{base_name}.cover.txt"
    payoff_text_path = clips_dir / f"{base_name}.payoff.txt"
    clean_background_path = clips_dir / f"{base_name}.background_tmp.mp4"
    watermark_preview_path = clips_dir / f"{base_name}.watermark_preview_tmp.mp4"
    json_path.unlink(missing_ok=True)

    duration = clip.end - clip.start
    clean_detail_pipeline = output_format == "vertical_short" and visual_mode == "auto_fyp"
    edit_variation = content_edit_variation(clip)
    adaptive_plan = codex_edit_plan(clip)
    theme_profile = visual_theme_profile(clip)
    auto_visual_plan = (
        auto_fyp_visual_plan(clip, output_format)
        if visual_mode == "auto_fyp"
        else {
            "version": 1,
            "base": "legacy_manual_mode",
            "accent": visual_mode,
            "reason": "legacy_request",
            "content_derived": False,
            "variation": edit_variation,
            "speaker_split": "manual" if visual_mode == "speaker_split" else "off",
            "stack_all_effects": False,
        }
    )
    auto_visual_accent = str(auto_visual_plan["accent"])
    islamic_background_music = clip_has_islamic_context(clip)
    music_ducking_supported = islamic_background_music and ffmpeg_has_filter(
        "sidechaincompress"
    )
    emphasis_times = emphasis_timestamps(clip, clip_segments)
    pov_windows = (
        cinematic_pov_windows(clip, clip_segments)
        if (
            visual_mode == "animated_3d"
            or auto_visual_accent == "animated_depth"
        )
        and output_format == "vertical_short"
        else None
    )
    camera_angle_cues = (
        virtual_camera_angle_cues(clip, clip_segments)
        if enhanced_edit and output_format == "vertical_short"
        else []
    )
    core_message = payoff_banner_text(clip, clip_segments)
    cover_copy = thumbnail_story_copy(clip)
    reaction_cues = detect_reaction_cues(clip, clip_segments)
    sound_effect_cues = (
        contextual_sound_effect_cues(
            duration,
            reaction_cues,
            emphasis_times,
            limit=3,
            min_gap=7.0 if output_format == "landscape_compilation" else 5.5,
        )
        if enhanced_edit
        else []
    )
    if enhanced_edit:
        sound_effect_cues = apply_codex_audio_cues(sound_effect_cues, duration, adaptive_plan)
        if clean_detail_pipeline:
            sound_effect_cues = sound_effect_cues[:3]
    drawtext_supported = ffmpeg_has_filter("drawtext")
    automatic_short_title = output_format == "vertical_short" and drawtext_supported
    applied_edits = list(clip.applied_edits)
    if automatic_short_title:
        applied_edits.append(
            "Kartu hook putih-kuning otomatis ditanam di awal video sebagai frame cover Shorts yang bisa dipilih."
        )
    if enhanced_edit and output_format == "vertical_short":
        if adaptive_plan.hook_boost:
            applied_edits.append("Hook diberi impact pulse dan accent audio pada detik pertama.")
        if adaptive_plan.tempo_boost:
            applied_edits.append("Pattern interrupt dipercepat pada detik 7, 14, dan 22.")
        if adaptive_plan.ending_boost:
            applied_edits.append(
                "Penutup diberi kartu payoff dari kalimat asli dan accent audio."
                if drawtext_supported
                else "Penutup diberi accent audio untuk menegaskan payoff."
            )
        if adaptive_plan.loop_boost:
            applied_edits.append(
                "Titik akhir dipertahankan pada payoff yang terhubung ke hook, tanpa kartu callback atau fade hitam."
                if drawtext_supported
                else "Payoff dan hook terhubung secara semantik agar autoplay loop terasa natural."
            )
    remaining_ideas, resolved_idea_edits = resolve_codex_ideas(
        clip.improvement_ideas,
        adaptive_plan,
        enhanced_edit=enhanced_edit,
        output_format=output_format,
        drawtext_supported=drawtext_supported,
    )
    applied_edits.extend(resolved_idea_edits)
    applied_edits = list(dict.fromkeys(applied_edits))
    subtitles_supported = ffmpeg_has_filter("subtitles")
    reaction_overlays_supported = (
        visual_mode not in {"cinematic", "animated_3d", "retro_tv"}
        and auto_visual_accent != "retro_archive"
        and output_format == "vertical_short"
        and (
        ffmpeg_has_filter("movie")
        and ffmpeg_has_filter("overlay")
        and ffmpeg_has_filter("rotate")
        and ffmpeg_has_filter("colorchannelmixer")
        and all((REACTION_ASSET_DIR / f"{cue.kind}.svg").is_file() for cue in reaction_cues)
        )
    )
    write_srt(srt_path, clip_segments, clip.start, duration)
    dynamic_caption_cues = 0
    if enhanced_edit and output_format == "vertical_short":
        dynamic_caption_cues = write_dynamic_ass(
            ass_path,
            clip_segments,
            clip.start,
            duration,
            caption or CaptionStyle(),
            accent=theme_profile["accent"],
        )
        if dynamic_caption_cues:
            applied_edits.append(
                "Caption dinamis menyorot kata penting dan ditempatkan di safe area UI Shorts."
            )
    else:
        ass_path.unlink(missing_ok=True)
    sidecar_payload = {
        **asdict(clip),
        "enhanced_edit": enhanced_edit,
        "remove_running_text": remove_running_text,
        "auto_blur_watermarks": auto_blur_watermarks,
        "visual_theme": theme_profile["theme"],
        "emphasis_times": emphasis_times,
        "cinematic_pov_windows": [
            {"start": start, "end": end}
            for start, end in (pov_windows or [])
        ],
        "virtual_camera_angles": [asdict(cue) for cue in camera_angle_cues],
        "reaction_cues": [asdict(cue) for cue in reaction_cues],
        "sound_effect_cues": [asdict(cue) for cue in sound_effect_cues],
        "background_music": (
            {
                "enabled": False,
                "requested": True,
                "title": ISLAMIC_BACKGROUND_MUSIC_TITLE,
                "source": "locally_synthesized_fendy_clipper_original",
                "license": ISLAMIC_BACKGROUND_MUSIC_LICENSE,
                "third_party_recording": False,
                "ducking": music_ducking_supported,
            }
            if islamic_background_music
            else {
                "enabled": False,
                "requested": False,
                "reason": "non_islamic_clip",
            }
        ),
        "drawtext_supported": drawtext_supported,
        "subtitles_supported": subtitles_supported,
        "reaction_overlays_supported": reaction_overlays_supported,
        "dynamic_captions": {
            "enabled": bool(dynamic_caption_cues),
            "cue_count": dynamic_caption_cues,
            "keyword_highlight": bool(dynamic_caption_cues),
            "shorts_ui_safe_area": bool(dynamic_caption_cues),
        },
        "content_edit_signature": {
            "version": 1,
            "variation": edit_variation,
            "derived_from_story": True,
        },
        "improvement_ideas": remaining_ideas,
        "applied_edits": applied_edits,
        "codex_ideas_resolved": len(clip.improvement_ideas) - len(remaining_ideas),
        "codex_edit_plan": asdict(adaptive_plan),
        "video_quality": video_quality,
        "output_format": output_format,
        "visual_mode": visual_mode,
        "auto_fyp_visual_plan": auto_visual_plan,
        "background_mode": background_mode,
        "clean_detail_pipeline": clean_detail_pipeline,
        "detail_encoding": {
            "crf": int(quality_preset(video_quality)["crf"]),
            "preset": str(quality_preset(video_quality)["preset"]),
            "clarity_filter": quality_detail_filter(video_quality) or "none",
            "x264_tune": "film",
            "adaptive_quantization": "aq-mode=3:aq-strength=0.85",
        },
        "aspect_ratio": "16:9" if output_format == "landscape_compilation" else "9:16",
        "source_metadata_embedded": False,
        "core_message": core_message.replace("\n", " ").strip(),
        "thumbnail_strategy": (
            "embedded_shorts_cover_frame"
            if automatic_short_title
            else "rendered_video_frame"
        ),
        "thumbnail_eyebrow": cover_copy["eyebrow"],
        "thumbnail_headline": cover_copy["headline"].replace("\n", " "),
        "thumbnail_support": cover_copy["support"].replace("\n", " "),
        "embedded_cover_window_seconds": (
            round(min(duration, SHORTS_TITLE_OVERLAY_SECONDS), 3)
            if automatic_short_title
            else None
        ),
        "thumbnail_keyframe_seconds": (
            round(shorts_cover_frame_timestamp(duration), 3)
            if automatic_short_title
            else None
        ),
        "shorts_policy_compliance": (
            shorts_policy_compliance(duration, embedded_cover=automatic_short_title)
            if output_format == "vertical_short"
            else None
        ),
    }

    visual_source = video_path
    visual_start = clip.start
    embedded_split_profile = (
        detect_embedded_split_layout(video_path, clip)
        if output_format == "vertical_short" and background_mode == "auto_clean"
        else None
    )
    clean_source: Path | None = None
    backdrop_profile: BackdropProfile | None = None
    if embedded_split_profile is None:
        clean_source, backdrop_profile = render_clean_background_segment(
            video_path,
            clip,
            clean_background_path,
            background_mode,
        )
    if clean_source is not None and backdrop_profile is not None:
        visual_source = clean_source
        visual_start = 0.0
        sidecar_payload["background_replaced"] = True
        sidecar_payload["background_replacement"] = {
            "asset": MOSQUE_BACKGROUND_PATH.name,
            "confidence": backdrop_profile.confidence,
            "dominant_ratio": backdrop_profile.dominant_ratio,
            "aligned_component_count": backdrop_profile.aligned_component_count,
        }
        applied_edits.append(
            "Backdrop bertulisan/tanggal diganti interior masjid netral tanpa logo agar fokus tetap pada pembicara."
        )
    else:
        sidecar_payload["background_replaced"] = False

    split_filters_supported = all(
        ffmpeg_has_filter(name)
        for name in (
            "fade",
            "geq",
            "gblur",
            "movie",
            "overlay",
            "pad",
            "vignette",
            "zoompan",
        )
    )
    adaptive_text_split_enabled = (
        output_format == "vertical_short"
        and background_mode == "auto_clean"
        and visual_mode == "speaker_split"
        and (backdrop_profile is not None or embedded_split_profile is not None)
        and MOSQUE_CONGREGATION_PATH.is_file()
        and split_filters_supported
    )

    if output_format == "landscape_compilation":
        should_try_split = visual_mode == "speaker_split" or (
            visual_mode == "auto_fyp"
            and compilation_part_count >= 3
            and compilation_part_number % 3 == 0
        )
        split_focus = detect_speaker_focus_points(video_path, clip) if should_try_split else None
        if split_focus is not None:
            focus_points, (source_width, source_height) = split_focus
            vf = landscape_speaker_split_filter(
                source_width,
                source_height,
                focus_points,
                theme_profile["accent"],
                theme_profile.get("accent_secondary", "#22D3EE"),
                emphasis_times=emphasis_times,
                remove_running_text=remove_running_text,
            )
            sidecar_payload["layout"] = "speaker_aware_split"
            applied_edits.append(
                "Split-screen kanan–kiri diterapkan pada dua pembicara terdeteksi, dengan border aktif mengikuti beat percakapan."
            )
        else:
            vf = landscape_compilation_frame_filter(
                theme_profile["accent"],
                theme_profile.get("accent_secondary", "#22D3EE"),
                remove_running_text=remove_running_text,
            )
            sidecar_payload["layout"] = "cinematic_bordered_frame"
            if should_try_split:
                sidecar_payload["split_fallback_reason"] = "two_speakers_not_detected"
    elif embedded_split_profile is not None:
        vf = embedded_split_subject_filter(
            video_path,
            clip,
            embedded_split_profile,
        )
        sidecar_payload["source_embedded_split"] = {
            "detected": True,
            "boundary_ratio": embedded_split_profile.boundary_ratio,
            "confidence": embedded_split_profile.confidence,
            "lower_text_component_count": (
                embedded_split_profile.lower_text_component_count
            ),
        }
        applied_edits.append(
            "Panel judul bawaan sumber terdeteksi dan dibuang; wajah pembicara dipusatkan otomatis sebelum split."
        )
    elif crop_mode == "streamer":
        vf = streamer_crop_filter(video_path, clip, cam_corner)
    elif clean_detail_pipeline:
        vf, source_detail = vertical_clean_detail_crop_filter(
            video_path,
            clip,
            crop_mode,
        )
        sidecar_payload["source_detail_strategy"] = source_detail
        sidecar_payload["layout"] = str(source_detail["layout"])
        if source_detail.get("extreme_upscale_avoided"):
            applied_edits.append(
                "Upscale ekstrem 9:16 dihindari; sumber landscape ditempatkan pada kanvas solid tajam agar detail wajah tetap natural."
            )
    else:
        vf = vertical_crop_filter(video_path, clip, crop_mode)
    if (
        remove_running_text
        and output_format == "vertical_short"
        and embedded_split_profile is None
    ):
        vf = f"{vf},{remove_running_text_filter()}"
    if adaptive_text_split_enabled:
        vf = f"{vf},{adaptive_text_backdrop_split_filter(duration)}"
        sidecar_payload["layout"] = "adaptive_text_congregation_split"
        sidecar_payload["adaptive_text_split"] = {
            "enabled": True,
            "asset": MOSQUE_CONGREGATION_PATH.name,
            "trigger": (
                "embedded_speaker_banner"
                if embedded_split_profile is not None
                else "text_heavy_backdrop"
            ),
            "ratio": "64/36_speaker_dominant",
            "transition": "overlapping_gradient_cinematic_crossfade",
        }
        applied_edits.append(
            (
                "Frame dua panel dibenahi menjadi komposisi speaker-dominan: panel judul "
                "bawaan dibuang, pembicara dipusatkan, dan jamaah masjid hadir lembut di bawah."
                if embedded_split_profile is not None
                else "Backdrop penuh tulisan memicu komposisi speaker-dominan dengan "
                "jamaah masjid di panel bawah dan sambungan gradasi sinematik."
            )
        )
        console.print(
            "[green]Split adaptif aktif:[/green] pembicara dominan + jamaah masjid "
            "di panel bawah dengan overlapping gradient."
        )
    else:
        sidecar_payload["adaptive_text_split"] = {
            "enabled": False,
            "reason": (
                "not_text_heavy_or_embedded_split"
                if backdrop_profile is None and embedded_split_profile is None
                else "unsupported_output_or_filters"
            ),
        }
    if visual_mode == "animated_3d" or auto_visual_accent == "animated_depth":
        core_supported = all(
            ffmpeg_has_filter(name)
            for name in ("hqdn3d", "curves", "colorbalance")
        )
        outline_supported = core_supported and all(
            ffmpeg_has_filter(name) for name in ("edgedetect", "blend")
        )
        adaptive_sharpen_supported = ffmpeg_has_filter("cas")
        animated_filter = (
            animated_3d_look_filter(
                with_outline=outline_supported,
                with_adaptive_sharpen=adaptive_sharpen_supported,
            )
            if core_supported
            else animated_3d_fallback_filter(
                with_adaptive_sharpen=adaptive_sharpen_supported,
            )
        )
        vf = f"{vf},{animated_filter}"
        sidecar_payload["animated_3d"] = {
            "enabled": True,
            "selected_by_auto_fyp": auto_visual_accent == "animated_depth",
            "outline": outline_supported,
            "adaptive_sharpen": adaptive_sharpen_supported,
            "method": (
                "local_ffmpeg_stylization"
                if core_supported
                else "local_ffmpeg_basic_fallback"
            ),
        }
        applied_edits.append(
            "Look 3D animated jernih diterapkan: denoise ringan, warna hangat, detail adaptif, depth contrast, dan outline halus."
            if outline_supported
            else "Look 3D animated jernih diterapkan dengan denoise ringan, warna hangat, dan detail adaptif."
        )
    if not clean_detail_pipeline:
        vf = add_quality_sharpen(vf, video_quality)
    if automatic_short_title:
        cover_text_path.write_text(cover_copy["headline"] + "\n", encoding="utf-8")
    if enhanced_edit:
        if drawtext_supported:
            hook_text_path.write_text(hook_banner_text(clip) + "\n", encoding="utf-8")
            pov_text_path.write_text(pov_banner_text(clip) + "\n", encoding="utf-8")
            payoff_text_path.write_text(core_message + "\n", encoding="utf-8")
            if output_format == "vertical_short":
                if not clean_detail_pipeline:
                    applied_edits.append(
                        "Intisari ucapan asli ditampilkan menjelang akhir agar makna klip langsung terbaca."
                    )
                applied_edits.append(
                    "Judul hook bergaya Shorts ditampilkan otomatis pada 3,2 detik pertama dan ditandai keyframe untuk cover."
                )
        else:
            console.print(
                "[yellow]FFmpeg tidak memiliki drawtext; hook teks dilewati, "
                "motion/color/pulse tetap diterapkan.[/yellow]"
            )
        if (
            reaction_cues
            and output_format == "vertical_short"
            and not reaction_overlays_supported
        ):
            console.print(
                "[yellow]FFmpeg tidak mendukung movie/overlay SVG; reaction sticker dilewati "
                "agar export tetap berjalan.[/yellow]"
            )
        if output_format == "landscape_compilation":
            vf = (
                f"{vf},"
                f"{landscape_compilation_edit_filter(
                    duration,
                    hook_text_path.name,
                    section_number=compilation_part_number,
                    section_count=compilation_part_count,
                    editorial_text_filename=pov_text_path.name if drawtext_supported else "",
                    theme_profile=theme_profile,
                    emphasis_times=emphasis_times,
                    show_text_overlays=drawtext_supported,
                )}"
            )
            applied_edits.append(
                "Setiap bab diberi catatan editor berbasis POV dan konteks klip agar resume memiliki framing editorial yang jelas."
            )
        else:
            if clean_detail_pipeline:
                vf = (
                    f"{vf},"
                    f"{clean_detail_edit_filter(
                        duration,
                        hook_text_path.name,
                        cover_text_filename=(
                            cover_text_path.name if drawtext_supported else ""
                        ),
                        show_progress=generate_assets,
                        theme_profile=theme_profile,
                        emphasis_times=emphasis_times,
                        show_text_overlays=drawtext_supported,
                        reaction_cues=reaction_cues,
                        show_reactions=reaction_overlays_supported,
                        camera_angle_cues=camera_angle_cues,
                        detail_filter=quality_detail_filter(video_quality),
                    )}"
                )
                sidecar_payload["motion_impact"] = {
                    "style": "clean_detail",
                    "continuous_motion": False,
                    "blurred_frame": False,
                    "gradient_overlay": False,
                    "large_editorial_cards": False,
                    "story_timed_camera_cuts": len(camera_angle_cues),
                }
                applied_edits.append(
                    "Pipeline clean-detail menjaga frame tanpa blur/gradient, lalu memberi reframe singkat hanya pada beat ucapan penting."
                )
            else:
                vf = (
                    f"{vf},"
                    f"{enhanced_edit_filter(
                        duration,
                        hook_text_path.name,
                        pov_text_filename=pov_text_path.name if drawtext_supported else "",
                        cover_text_filename=(
                            cover_text_path.name
                            if drawtext_supported and output_format == "vertical_short"
                            else ""
                        ),
                        show_progress=generate_assets,
                        theme_profile=theme_profile,
                        emphasis_times=emphasis_times,
                        variation=edit_variation,
                        show_text_overlays=drawtext_supported,
                        reaction_cues=reaction_cues,
                        show_reactions=reaction_overlays_supported,
                        codex_plan=adaptive_plan,
                        payoff_text_filename=payoff_text_path.name if drawtext_supported else "",
                        cinematic_pov_windows=pov_windows,
                        camera_angle_cues=camera_angle_cues or None,
                    )}"
                )
                sidecar_payload["motion_impact"] = {
                    "animated_border": True,
                    "intro_zoom_out": True,
                    "intro_edge_particles": True,
                    "particle_duration_seconds": 0.84,
                }
                applied_edits.append(
                    "Border neon bergerak, zoom-out pembuka, dan bintik cahaya singkat ditambahkan untuk memperkuat hook."
                )
            if pov_windows:
                applied_edits.append(
                    f"Look 3D dipadukan dengan {len(pov_windows)} reframe sinematik pada momen POV terdeteksi."
                )
            if camera_angle_cues:
                applied_edits.append(
                    f"Virtual multi-camera menerapkan {len(camera_angle_cues)} cut medium/close-up pada beat ucapan, dengan framing wajah tetap aman."
                )
    elif automatic_short_title:
        vf = f"{vf},{viral_title_overlay_filter(cover_text_path.name, duration)}"
    if clean_detail_pipeline and not enhanced_edit:
        vf = add_quality_sharpen(vf, video_quality)
    if visual_mode == "retro_tv" or auto_visual_accent == "retro_archive":
        curves_supported = ffmpeg_has_filter("curves")
        vf = f"{vf},{retro_tv_look_filter(with_curves=curves_supported)}"
        sidecar_payload["retro_tv"] = {
            "enabled": True,
            "selected_by_auto_fyp": auto_visual_accent == "retro_archive",
            "monochrome": True,
            "animated_grain": True,
            "scanlines": True,
            "flicker": True,
            "vertical_tape_scratches": True,
            "vignette": True,
            "curves": curves_supported,
        }
        applied_edits.append(
            "Efek TV jadul diterapkan: hitam-putih pudar, grain bergerak, scanline, flicker halus, vignette, dan goresan pita vertikal."
        )
    watermark_region: WatermarkRegion | None = None
    watermark_filters_supported = all(
        ffmpeg_has_filter(name) for name in ("crop", "gblur", "overlay", "split")
    )
    if auto_blur_watermarks and watermark_filters_supported:
        preview_scale_width = 540 if output_format == "vertical_short" else 640
        try:
            run(
                [
                    ffmpeg_path(),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{visual_start:.3f}",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(visual_source.resolve()),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-vf",
                    f"{vf},fps=1,scale={preview_scale_width}:-2:flags=area",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "25",
                    "-pix_fmt",
                    "yuv420p",
                    str(watermark_preview_path.name),
                ],
                cwd=clips_dir,
            )
            preview_region = detect_static_watermark_region(watermark_preview_path)
            if preview_region is not None:
                output_width, output_height = (
                    (1080, 1920)
                    if output_format == "vertical_short"
                    else (1920, 1080)
                )
                watermark_region = scale_watermark_region(
                    preview_region, output_width, output_height
                )
                vf = f"{vf},{localized_watermark_blur_filter(watermark_region)}"
                applied_edits.append(
                    "Watermark sumber statis terdeteksi lintas frame dan ditutup dengan blur lokal yang terbatas pada area logo."
                )
                console.print(
                    "[green]Watermark sumber terdeteksi:[/green] blur lokal diterapkan "
                    f"pada {watermark_region.x},{watermark_region.y} "
                    f"{watermark_region.width}x{watermark_region.height}."
                )
            else:
                console.print(
                    "[dim]Tidak ada watermark statis yang cukup meyakinkan; frame sumber tidak diburamkan.[/dim]"
                )
        except RuntimeError as exc:
            console.print(
                "[yellow]Deteksi watermark dilewati agar export tetap berjalan:[/yellow] "
                f"{exc}"
            )
        finally:
            watermark_preview_path.unlink(missing_ok=True)
    sidecar_payload["source_watermark_blur"] = {
        "enabled": auto_blur_watermarks,
        "detected": watermark_region is not None,
        "method": "multi_frame_persistent_edge_feathered_local_blur_v2",
        "detector_version": 2,
        "region": asdict(watermark_region) if watermark_region is not None else None,
        "applied_before_fendy_clipper_overlays": True,
        "feathered_boundary": watermark_region is not None,
        "scope": "detected_region_only",
    }
    smoke_filters_supported = all(
        ffmpeg_has_filter(name)
        for name in ("format", "fps", "geq", "gblur", "nullsrc", "overlay", "scale")
    )
    if smoke_filters_supported:
        vf = (
            f"{vf},"
            f"{cinematic_smoke_overlay_filter(output_format, variation=edit_variation)}"
        )
        sidecar_payload["cinematic_smoke"] = {
            "enabled": True,
            "version": 1,
            "style": "soft_white_edge_fog",
            "placement": "lower_edge_and_corners",
            "subject_safe_center": True,
            "caption_rendered_above_effect": True,
            "procedural": True,
            "variation": edit_variation,
        }
        applied_edits.append(
            "Kabut asap putih bergerak ditambahkan halus di tepi bawah dan sudut, sementara wajah serta subtitle tetap jelas."
        )
    else:
        sidecar_payload["cinematic_smoke"] = {
            "enabled": False,
            "reason": "required_ffmpeg_filters_unavailable",
        }
    if drawtext_supported:
        vf = f"{vf},{channel_watermark_filter(output_format)}"
        sidecar_payload["channel_watermark"] = {
            "enabled": True,
            "text": CHANNEL_WATERMARK,
            "position": "top_left_safe",
        }
        applied_edits.append(
            f"Watermark channel {CHANNEL_WATERMARK} ditambahkan di safe area kiri atas."
        )
        if output_format == "vertical_short":
            vf = f"{vf},{shorts_cta_overlay_filter(duration)}"
            sidecar_payload["end_cta"] = {
                "enabled": True,
                "copy": "SUBSCRIBE + FOLLOW",
                "duration_seconds": SHORTS_CTA_OVERLAY_SECONDS,
                "placement": "center_lower_caption_safe",
                "extends_video_duration": False,
            }
            applied_edits.append(
                "CTA Subscribe + Follow tampil singkat di atas payoff hidup tanpa menambah outro kosong."
            )
    else:
        sidecar_payload["channel_watermark"] = {
            "enabled": False,
            "text": CHANNEL_WATERMARK,
            "reason": "ffmpeg_drawtext_unavailable",
        }
        if output_format == "vertical_short":
            sidecar_payload["end_cta"] = {
                "enabled": False,
                "reason": "ffmpeg_drawtext_unavailable",
            }
    if burn_subtitles and clip_segments and subtitles_supported:
        style = build_subtitle_style(caption or CaptionStyle())
        if output_format == "landscape_compilation":
            vf = (
                f"{vf},subtitles='{srt_path.name}'"
                ":original_size=1920x1080"
                f":force_style='{style}'"
            )
        else:
            subtitle_source = ass_path if dynamic_caption_cues else srt_path
            subtitle_options = (
                ""
                if dynamic_caption_cues
                else f":original_size=1080x1920:force_style='{style}'"
            )
            vf = (
                f"{vf},subtitles='{subtitle_source.name}'{subtitle_options}"
            )
        sidecar_payload["caption_backdrop"] = {
            "enabled": False,
            "reason": "preserve_clear_source_pixels_and_faces",
        }
    elif burn_subtitles and clip_segments:
        console.print(
            "[yellow]FFmpeg tidak memiliki filter subtitles; file SRT tetap dibuat "
            "dan export video dilanjutkan tanpa burn subtitle.[/yellow]"
        )

    video_input = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{visual_start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(visual_source.resolve()),
    ]
    audio_input = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{clip.start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(video_path.resolve()),
    ]
    quality = quality_preset(video_quality)

    try:
        run(
            [
                *video_input,
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-profile:v",
                str(quality["profile"]),
                "-level",
                str(quality["level"]),
                "-preset",
                str(quality["preset"]),
                "-tune",
                "film",
                "-x264-params",
                "aq-mode=3:aq-strength=0.85:deblock=-1,-1",
                "-crf",
                str(quality["crf"]),
                "-pix_fmt",
                "yuv420p",
                *(
                    [
                        "-force_key_frames",
                        "0,"
                        f"{shorts_cover_frame_timestamp(duration):.3f},"
                        f"{min(duration, SHORTS_TITLE_OVERLAY_SECONDS):.3f}",
                    ]
                    if automatic_short_title
                    else []
                ),
                *ffmpeg_clean_metadata_args(),
                str(temp_video_path.name),
            ],
            cwd=clips_dir,
        )
    finally:
        hook_text_path.unlink(missing_ok=True)
        pov_text_path.unlink(missing_ok=True)
        cover_text_path.unlink(missing_ok=True)
        payoff_text_path.unlink(missing_ok=True)
        clean_background_path.unlink(missing_ok=True)
        watermark_preview_path.unlink(missing_ok=True)
    audio_filter = (
        "highpass=f=70,lowpass=f=15000,"
        "acompressor=threshold=0.125:ratio=2.5:attack=20:release=250:makeup=1.35,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"
    )
    if enhanced_edit:
        # Keep the last spoken beat alive; the loop cue hands it back to the
        # opening hook without fading to silence.
        audio_filter += ",afade=t=in:st=0:d=0.10"
    plain_audio_command = [
        *audio_input,
        "-map",
        "0:a:0?",
        "-vn",
        "-af",
        audio_filter,
        "-ac",
        "2",
        "-ar",
        "48000",
        "-c:a",
        "pcm_s16le",
        str(temp_audio_path.name),
    ]
    if sound_effect_cues or islamic_background_music:
        try:
            run(
                [
                    *audio_input,
                    "-filter_complex",
                    contextual_audio_mix_filter(
                        audio_filter,
                        sound_effect_cues,
                        background_music=islamic_background_music,
                        duration=duration,
                        music_ducking=music_ducking_supported,
                    ),
                    "-map",
                    "[audio_out]",
                    "-vn",
                    "-ac",
                    "2",
                    "-ar",
                    "48000",
                    "-c:a",
                    "pcm_s16le",
                    str(temp_audio_path.name),
                ],
                cwd=clips_dir,
            )
            if islamic_background_music:
                sidecar_payload["background_music"]["enabled"] = True
                applied_edits.append(
                    "Backsong motivasional Islami orisinal berlisensi CC0 ditambahkan pelan di bawah dialog."
                )
        except RuntimeError as exc:
            temp_audio_path.unlink(missing_ok=True)
            console.print(
                f"[yellow]Audio pendukung dilewati; audio dialog tetap dipakai:[/yellow] {exc}"
            )
            if islamic_background_music:
                sidecar_payload["background_music"]["enabled"] = False
                sidecar_payload["background_music"]["reason"] = "ffmpeg_mix_failed"
            run(plain_audio_command, cwd=clips_dir)
    else:
        run(plain_audio_command, cwd=clips_dir)
    mux_audio_path = temp_audio_path
    cta_voice_path: Path | None = None
    cta_voiceover_enabled = (
        output_format == "vertical_short"
        and drawtext_supported
        and env_enabled("CTA_VOICEOVER_ENABLED", True)
    )
    if cta_voiceover_enabled:
        generated_voice = generate_shorts_cta_voiceover(clips_dir, base_name)
        if generated_voice is not None:
            cta_voice_path, voice_details = generated_voice
            try:
                run(
                    [
                        ffmpeg_path(),
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(temp_audio_path.name),
                        "-i",
                        str(cta_voice_path.name),
                        "-filter_complex",
                        shorts_cta_voiceover_mix_filter(duration),
                        "-map",
                        "[cta_audio_out]",
                        "-ac",
                        "2",
                        "-ar",
                        "48000",
                        "-c:a",
                        "pcm_s16le",
                        str(temp_cta_audio_path.name),
                    ],
                    cwd=clips_dir,
                )
                mux_audio_path = temp_cta_audio_path
                sidecar_payload["end_cta"]["voiceover"] = {
                    **voice_details,
                    "enabled": True,
                    "start_seconds": round(
                        max(0.0, duration - SHORTS_CTA_OVERLAY_SECONDS) + 0.12,
                        3,
                    ),
                    "dialog_ducking": True,
                    "generated_for_this_export": True,
                }
                applied_edits.append(
                    "Voice-over Indonesia mengucapkan CTA secara sinkron; dialog sumber diducking hanya selama kartu penutup."
                )
                console.print(
                    "[green]Voice-over CTA aktif:[/green] "
                    f"{voice_details['provider']} + dialog ducking."
                )
            except RuntimeError as exc:
                temp_cta_audio_path.unlink(missing_ok=True)
                sidecar_payload["end_cta"]["voiceover"] = {
                    "enabled": False,
                    "reason": "audio_mix_failed",
                }
                console.print(
                    "[yellow]Voice-over CTA gagal dicampur; audio utama tetap digunakan:[/yellow] "
                    f"{exc}"
                )
        else:
            sidecar_payload["end_cta"]["voiceover"] = {
                "enabled": False,
                "reason": "neural_and_local_tts_unavailable",
            }
            console.print(
                "[yellow]Voice-over CTA dilewati: provider neural dan lokal tidak tersedia.[/yellow]"
            )
    elif output_format == "vertical_short" and isinstance(
        sidecar_payload.get("end_cta"), dict
    ):
        sidecar_payload["end_cta"]["voiceover"] = {
            "enabled": False,
            "reason": (
                "disabled_by_environment"
                if not env_enabled("CTA_VOICEOVER_ENABLED", True)
                else "cta_card_unavailable"
            ),
        }
    run(
        [
            ffmpeg_path(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "+genpts",
            "-y",
            "-i",
            str(temp_video_path.name),
            "-i",
            str(mux_audio_path.name),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-b:a",
            str(quality["audio_bitrate"]),
            "-ar",
            "48000",
            "-ac",
            "2",
            "-disposition:a:0",
            "default",
            *ffmpeg_clean_metadata_args(),
            "-shortest",
            "-brand",
            "mp42",
            "-tag:v",
            "avc1",
            "-tag:a",
            "mp4a",
            "-movflags",
            "+faststart",
            str(out_path.name),
        ],
        cwd=clips_dir,
    )
    temp_video_path.unlink(missing_ok=True)
    temp_audio_path.unlink(missing_ok=True)
    temp_cta_audio_path.unlink(missing_ok=True)
    if cta_voice_path is not None:
        cta_voice_path.unlink(missing_ok=True)
    if enforce_size:
        enforce_clip_size_limit(out_path, duration)
    output_width, output_height = ensure_minimum_hd_output(out_path)
    sidecar_payload.update(
        {
            "output_width": output_width,
            "output_height": output_height,
            "output_resolution": f"{output_width}x{output_height}",
        }
    )
    save_json(json_path, sidecar_payload)

    if generate_assets:
        thumb_path = clips_dir / f"{base_name}_thumb.jpg"
        prompt_path = clips_dir / f"{base_name}_thumb.txt"
        thumb_prompt = generate_thumbnail_prompt(clip, ai_config or AIConfig())
        thumb_timestamp = (
            shorts_cover_frame_timestamp(duration)
            if output_format == "vertical_short"
            else max(0.0, duration * 0.5)
        )
        rendered_thumb = grab_frame_at(
            out_path,
            thumb_timestamp,
            thumb_path,
            label=f"thumbnail final clip {clip.index}",
        )
        if rendered_thumb is not None:
            sidecar_payload["thumbnail_frame_seconds"] = round(thumb_timestamp, 3)
        if thumb_prompt:
            prompt_path.write_text(
                f"POV: {cover_copy['headline'].replace(chr(10), ' ')}\n"
                f"HOOK: {thumb_prompt['hook_text']}\n"
                f"STRATEGI: {sidecar_payload['thumbnail_strategy']}\n\n"
                f"{thumb_prompt['prompt']}\n",
                encoding="utf-8",
            )

        save_json(json_path, sidecar_payload)

        social_caption = generate_social_caption(clip, ai_config or AIConfig(), required_hashtags)
        if social_caption:
            (clips_dir / f"{base_name}_caption.txt").write_text(social_caption + "\n", encoding="utf-8")

    return out_path


def write_compilation_srt(
    path: Path,
    transcript: list[TranscriptSegment],
    candidates: list[ClipCandidate],
) -> float:
    timeline: list[TranscriptSegment] = []
    cursor = 0.0
    for candidate in candidates:
        duration = candidate.end - candidate.start
        for item in segments_for_clip(transcript, candidate):
            start = cursor + max(0.0, item.start - candidate.start)
            end = cursor + min(duration, max(0.2, item.end - candidate.start))
            if start < cursor + duration:
                timeline.append(TranscriptSegment(start=start, end=end, text=item.text))
        cursor += duration
    write_srt(path, timeline, 0, cursor)
    return cursor


def export_compilation(
    video_path: Path,
    candidates: list[ClipCandidate],
    transcript: list[TranscriptSegment],
    clips_dir: Path,
    burn_subtitles: bool,
    crop_mode: CropMode,
    caption: CaptionStyle,
    ai_config: AIConfig,
    cam_corner: str,
    required_hashtags: list[str],
    video_quality: VideoQuality,
    visual_mode: VisualMode = "auto_fyp",
    background_mode: BackgroundMode = "keep",
    enhanced_edit: bool = True,
    remove_running_text: bool = False,
    auto_blur_watermarks: bool = False,
) -> Path:
    clips_dir.mkdir(parents=True, exist_ok=True)
    candidates = order_compilation_for_retention(candidates)
    parts_dir = clips_dir / ".compilation_parts"
    shutil.rmtree(parts_dir, ignore_errors=True)
    parts_dir.mkdir(parents=True, exist_ok=True)

    strongest = max(candidates, key=lambda item: item.score)
    target_minutes = max(5, min(10, round(sum(item.duration for item in candidates) / 60)))
    base_name = f"resume_cerita_{target_minutes}menit_{slugify(strongest.title)[:48] or 'inti-cerita'}"
    out_path = clips_dir / f"{base_name}.mp4"
    srt_path = clips_dir / f"{base_name}.srt"
    json_path = clips_dir / f"{base_name}.json"
    prompt_path = clips_dir / f"{base_name}_thumb.txt"
    thumb_path = clips_dir / f"{base_name}_thumb.jpg"

    part_paths: list[Path] = []
    altered_content_disclosure_required = False
    try:
        total_parts = len(candidates)
        for idx, candidate in enumerate(candidates, start=1):
            part_start = 70 + round(((idx - 1) / max(1, total_parts)) * 20)
            emit_progress(
                part_start,
                "render",
                f"Merender bagian cerita {idx} dari {total_parts}",
            )
            part_path = export_clip(
                video_path,
                candidate,
                segments_for_clip(transcript, candidate),
                parts_dir,
                burn_subtitles,
                crop_mode,
                caption,
                ai_config,
                cam_corner,
                required_hashtags,
                video_quality,
                generate_assets=False,
                enforce_size=False,
                base_name_override=f"part_{idx:02}",
                enhanced_edit=enhanced_edit,
                remove_running_text=remove_running_text,
                auto_blur_watermarks=auto_blur_watermarks,
                output_format="landscape_compilation",
                visual_mode=visual_mode,
                background_mode=background_mode,
                compilation_part_number=idx,
                compilation_part_count=len(candidates),
            )
            part_paths.append(part_path)
            part_done = 70 + round((idx / max(1, total_parts)) * 20)
            emit_progress(
                part_done,
                "render",
                f"Bagian cerita {idx} dari {total_parts} selesai",
            )
            try:
                part_payload = json.loads(
                    part_path.with_suffix(".json").read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                part_payload = {}
            adaptive_split = (
                part_payload.get("adaptive_text_split")
                if isinstance(part_payload, dict)
                else None
            )
            altered_content_disclosure_required = bool(
                altered_content_disclosure_required
                or (isinstance(part_payload, dict) and part_payload.get("background_replaced"))
                or (
                    isinstance(adaptive_split, dict)
                    and adaptive_split.get("enabled")
                )
                or background_mode == "mosque"
            )

        concat_path = parts_dir / "concat.txt"
        emit_progress(91, "render", "Menyatukan seluruh bagian video panjang")
        concat_path.write_text(
            "\n".join(f"file '{path.name}'" for path in part_paths) + "\n",
            encoding="utf-8",
        )
        run(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_path.name,
                "-c",
                "copy",
                *ffmpeg_clean_metadata_args(),
                "-movflags",
                "+faststart",
                str(out_path.resolve()),
            ],
            cwd=parts_dir,
        )
        emit_progress(92, "render", "Video panjang utuh selesai dirakit")
    finally:
        shutil.rmtree(parts_dir, ignore_errors=True)

    output_width, output_height = ensure_minimum_hd_output(out_path)
    total_duration = write_compilation_srt(srt_path, transcript, candidates)
    compilation_score = round(sum(item.score for item in candidates) / len(candidates))
    combined_strengths = list(
        dict.fromkeys(value for item in candidates for value in item.strengths)
    )[:4]
    combined_weaknesses = list(
        dict.fromkeys(value for item in candidates for value in item.weaknesses)
    )[:3]
    combined_ideas = list(
        dict.fromkeys(value for item in candidates for value in item.improvement_ideas)
    )[:3]
    combined_applied_edits = list(
        dict.fromkeys(value for item in candidates for value in item.applied_edits)
    )[:4]
    if visual_mode in {"auto_fyp", "speaker_split"}:
        combined_applied_edits.append(
            "Kompilasi memakai border sinematik dan split dua pembicara secara selektif saat deteksi wajah mendukung."
        )
    elif visual_mode == "animated_3d":
        combined_applied_edits.append(
            "Seluruh bagian memakai look 3D animated lokal yang lebih jernih dengan denoise ringan, detail adaptif, depth contrast, dan outline halus."
        )
    elif visual_mode == "retro_tv":
        combined_applied_edits.append(
            "Seluruh bagian memakai efek TV jadul hitam-putih dengan grain, scanline, flicker, vignette, dan goresan pita vertikal."
        )
    chronological_povs = list(
        dict.fromkeys(
            first_sentence(item.pov or fallback_pov_angle(item.text), max_words=14)
            for item in candidates
            if (item.pov or item.text).strip()
        )
    )
    story_beats = [
        first_sentence(item.title, max_words=8)
        for item in candidates
        if item.title.strip() and not is_source_branding_segment(item.title)
    ]
    representative_beats = (
        [
            story_beats[index]
            for index in sorted(
                {0, len(story_beats) // 3, (len(story_beats) * 2) // 3, len(story_beats) - 1}
            )
        ]
        if story_beats
        else [first_sentence(strongest.text, max_words=18)]
    )
    core_message = "Alur inti: " + " → ".join(representative_beats)
    resume_pov = chronological_povs[0] if chronological_povs else fallback_pov_angle(strongest.text)
    compilation = ClipCandidate(
        index=1,
        start=min(item.start for item in candidates),
        end=max(item.end for item in candidates),
        duration=total_duration,
        score=compilation_score,
        title=f"Resume Cerita: {strongest.title}"[:80],
        reason=f"Resume {len(candidates)} bagian inti yang merangkai konteks, POV, perkembangan, dan payoff secara kronologis.",
        text=" ".join(item.text for item in candidates),
        hook=strongest.hook or strongest.title,
        pov=resume_pov[:220],
        fyp_label=fyp_score_label(compilation_score),
        strengths=combined_strengths,
        weaknesses=combined_weaknesses,
        improvement_ideas=combined_ideas,
        applied_edits=combined_applied_edits,
    )
    compilation_sidecar = {
        **asdict(compilation),
        "mode": "highlight_5m",
        "resume_version": 1,
        "output_format": "landscape_compilation",
        "aspect_ratio": "16:9",
        "layout": (
            "adaptive_speaker_split_with_chapter_cards"
            if visual_mode in {"auto_fyp", "speaker_split"}
            else "animated_3d_cinematic_frame"
            if visual_mode == "animated_3d"
            else "retro_tv_cinematic_frame"
            if visual_mode == "retro_tv"
            else "cinematic_blurred_frame_with_chapter_cards"
        ),
        "visual_mode": visual_mode,
        "auto_fyp_visual_system": {
            "version": 1,
            "base": "cinematic_clean_detail",
            "chapter_accents_are_content_derived": visual_mode == "auto_fyp",
            "available_accents": [
                "cinematic_clean",
                "animated_depth",
                "retro_archive",
                "speaker_aware_split",
            ],
            "stack_all_effects": False,
            "mass_template_repetition_risk_reduced": visual_mode == "auto_fyp",
        },
        "background_mode": background_mode,
        "altered_content_disclosure_required": altered_content_disclosure_required,
        "enhanced_edit": enhanced_edit,
        "remove_running_text": remove_running_text,
        "source_metadata_embedded": False,
        "parts": [asdict(item) for item in candidates],
        "video_quality": video_quality,
        "output_width": output_width,
        "output_height": output_height,
        "output_resolution": f"{output_width}x{output_height}",
        "thumbnail_strategy": "custom_long_form_upload",
        "core_message": core_message[:600],
        "story_arc": [
            {
                **asdict(item),
                "narrative_role": (
                    "hook_context"
                    if index == 0
                    else "payoff_conclusion"
                    if index == len(candidates) - 1
                    else "development"
                ),
            }
            for index, item in enumerate(candidates)
        ],
        "retention_strategy": {
            "version": 1,
            "opening": "strongest_editorial_segment_first",
            "remaining_arc": "source_chronology_after_hook",
            "first_30_seconds_match_title_thumbnail_promise": True,
            "manual_youtube_chapters_ready": len(candidates) >= 3,
        },
    }

    strongest_offset = sum(
        item.end - item.start
        for item in candidates[: candidates.index(strongest)]
    )
    strongest_timestamp = strongest_offset + (strongest.end - strongest.start) * 0.5
    thumb_prompt = generate_thumbnail_prompt(compilation, ai_config, long_form=True)
    thumbnail_copy = thumbnail_story_copy(
        compilation,
        thumb_prompt.get("hook_text", "") if thumb_prompt else "",
        long_form=True,
    )
    if render_designed_thumbnail(
        out_path,
        strongest_timestamp,
        thumb_path,
        thumbnail_copy,
        long_form=True,
        theme_profile=visual_theme_profile(strongest),
        label="kompilasi landscape",
    ) is not None:
        compilation_sidecar["thumbnail_frame_seconds"] = round(strongest_timestamp, 3)
        compilation_sidecar["thumbnail_eyebrow"] = thumbnail_copy["eyebrow"]
        compilation_sidecar["thumbnail_headline"] = thumbnail_copy["headline"].replace("\n", " ")
        compilation_sidecar["thumbnail_support"] = thumbnail_copy["support"].replace("\n", " ")
    if thumb_prompt:
        prompt_path.write_text(
            f"HOOK: {thumb_prompt['hook_text']}\n"
            "STRATEGI: custom_long_form_upload\n\n"
            f"{thumb_prompt['prompt']}\n",
            encoding="utf-8",
        )
    save_json(json_path, compilation_sidecar)
    social_caption = generate_social_caption(
        compilation,
        ai_config,
        required_hashtags,
        long_form=True,
    )
    if social_caption:
        (clips_dir / f"{base_name}_caption.txt").write_text(social_caption + "\n", encoding="utf-8")
    return out_path


def print_candidates(candidates: list[ClipCandidate]) -> None:
    table = Table(title="Clip candidates · FYP potential")
    table.add_column("#", justify="right")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("FYP", justify="right")
    table.add_column("Potensi")
    table.add_column("Title")
    table.add_column("Kurang / Ide Codex")

    for item in candidates:
        table.add_row(
            str(item.index),
            seconds_to_stamp(item.start),
            seconds_to_stamp(item.end),
            str(item.score),
            item.fyp_label or fyp_score_label(item.score),
            item.title,
            " | ".join([*(item.weaknesses[:1] or ["siap diuji"]), *item.improvement_ideas[:1]]),
        )
    console.print(table)


def prepare_uploaded_source(source_file: Path, work_dir: Path) -> tuple[Path, dict]:
    if not source_file.exists():
        raise FileNotFoundError(f"Uploaded source not found: {source_file}")

    work_dir.mkdir(parents=True, exist_ok=True)
    # Read the upload in place instead of copying it into the work dir; a large
    # video would otherwise be stored twice (uploads/ and outputs/).
    suffix = source_file.suffix or ".mp4"
    metadata = {
        "id": source_file.stem,
        "title": source_file.stem,
        "uploader": None,
        "duration": None,
        "webpage_url": None,
        "ext": suffix.lstrip("."),
    }
    return source_file, metadata


def cleanup_intermediate(work_dir: Path, source_video: Path) -> None:
    # Once the clips are exported, the source video and the extracted audio are
    # dead weight. Delete them so a single job doesn't keep gigabytes around.
    # Only touch files inside work_dir (an uploaded source lives elsewhere).
    removed = 0
    for pattern in ("source.*", "audio*.wav"):
        for item in work_dir.glob(pattern):
            try:
                if item.resolve() == source_video.resolve() and source_video.parent != work_dir:
                    continue
                item.unlink()
                removed += 1
            except OSError:
                pass
    if removed:
        console.print(f"[green]Cleaned up[/green] {removed} intermediate file(s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local YouTube auto clipper for vertical Shorts and 16:9 landscape compilations."
    )
    parser.add_argument("url", nargs="?", default="", help="YouTube URL")
    parser.add_argument("--source-file", default="", help="Use a local video file instead of downloading from a URL")
    parser.add_argument("--top", type=int, default=5, help="Number of clips to export")
    parser.add_argument("--min", type=float, default=15, help="Minimum clip duration in seconds")
    parser.add_argument("--max", type=float, default=60, help="Maximum clip duration in seconds")
    parser.add_argument(
        "--clip-mode",
        choices=["short", "highlight_5m"],
        default="short",
        help="Export vertical shorts only, or one 5-10 minute landscape story resume",
    )
    parser.add_argument(
        "--compilation-target",
        type=float,
        default=300,
        help="Target duration (300-600 seconds) for story-resume mode",
    )
    parser.add_argument("--model", default=DEFAULT_TRANSCRIPTION_MODEL, help="faster-whisper model name")
    parser.add_argument("--language", default="id", help="Transcription language code")
    parser.add_argument("--output", default="outputs", help="Output directory")
    parser.add_argument("--analyze-seconds", type=float, help="Only transcribe the first N seconds; useful for quick tests")
    parser.add_argument(
        "--video-quality",
        choices=["standard", "high", "max"],
        default="high",
        help="Output clarity preset: standard is faster, high is the default, max is slower with larger files",
    )
    parser.add_argument("--review-only", action="store_true", help="Stop after generating clip candidates")
    parser.add_argument("--export-indexes", help="Comma-separated candidate indexes to export, e.g. 1,3,5")
    parser.add_argument("--no-burn-subtitles", action="store_true", help="Create SRT files but do not burn subtitles into MP4")
    parser.add_argument(
        "--crop-mode",
        choices=["center", "person", "streamer"],
        default="person",
        help="center, person-focused, or streamer (webcam stacked over gameplay)",
    )
    parser.add_argument(
        "--cam-corner",
        choices=["auto", "br", "bl", "tr", "tl"],
        default="auto",
        help="Webcam corner in the source for streamer mode (auto-detect by default)",
    )
    parser.add_argument(
        "--visual-mode",
        choices=["auto_fyp", "cinematic", "speaker_split", "animated_3d", "retro_tv"],
        default="auto_fyp",
        help="Auto FYP is the unified pipeline; legacy style names are accepted and migrated automatically",
    )
    parser.add_argument(
        "--background-mode",
        choices=["auto_clean", "keep", "mosque"],
        default="keep",
        help="Auto-clean text-heavy backdrops, keep the source, or force a neutral mosque background",
    )
    parser.add_argument("--force", action="store_true", help="Redo download, audio extraction, and transcription")
    parser.add_argument("--ai-enabled", action="store_true", help="Use an LLM agent to rescore clip candidates")
    parser.add_argument("--ai-base-url", default="", help="OpenAI-compatible base URL, e.g. http://localhost:20128/v1")
    parser.add_argument("--ai-model", default="", help="LLM model name for the clip agent")
    parser.add_argument("--ai-api-key", default="", help="API key for the LLM endpoint")
    parser.add_argument("--caption-font-size", type=int, default=8, help="Burned caption font size (6-120)")
    parser.add_argument(
        "--caption-position",
        choices=["upper", "center", "bottom"],
        default="bottom",
        help="Burned caption vertical position",
    )
    parser.add_argument("--caption-color", default="#FFFFFF", help="Burned caption text color, hex e.g. #FFFFFF")
    parser.add_argument("--caption-font", default=DEFAULT_FONT, help="Burned caption font family")
    parser.add_argument("--caption-outline", type=float, default=0.5, help="Caption border/outline width (0-8)")
    parser.add_argument("--caption-outline-color", default="#000000", help="Caption border color, hex")
    parser.add_argument(
        "--no-enhanced-edit",
        action="store_true",
        help="Disable animated hook, motion, transitions, vignette, and progress graphics",
    )
    parser.add_argument(
        "--keep-running-text",
        action="store_true",
        help="Deprecated compatibility flag; source pixels are preserved by default",
    )
    parser.add_argument(
        "--remove-running-text",
        action="store_true",
        help="Explicitly obscure the source footer/running text (may modify lower-frame pixels)",
    )
    parser.add_argument(
        "--auto-blur-watermarks",
        action="store_true",
        help="Detect persistent source watermarks across frames and blur only their local region",
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep the downloaded source video and extracted audio after exporting clips",
    )
    parser.add_argument(
        "--required-hashtags",
        default="",
        help="Comma-separated hashtags always appended to generated captions, e.g. fendyclipper,viral",
    )
    parser.add_argument(
        "--require-creative-commons",
        action="store_true",
        help="Reject YouTube URLs whose metadata is not Creative Commons/reuse allowed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.visual_mode != "auto_fyp":
        console.print(
            f"[yellow]Mode visual lama '{args.visual_mode}' dimigrasikan ke Auto FYP adaptif.[/yellow]"
        )
        args.visual_mode = "auto_fyp"

    if args.clip_mode == "short" and args.max > FENDY_CLIPPER_SHORTS_MAX_SECONDS:
        console.print(
            f"[yellow]Short clip maximum capped at {FENDY_CLIPPER_SHORTS_MAX_SECONDS} seconds "
            "to keep third-party claim risk below YouTube's stricter >1 minute Shorts rule.[/yellow]"
        )
        args.max = float(FENDY_CLIPPER_SHORTS_MAX_SECONDS)

    if args.min <= 0 or args.max <= args.min:
        console.print("[red]Invalid duration range.[/red]")
        return 2

    if not args.url and not args.source_file:
        console.print("[red]Provide a YouTube URL or --source-file.[/red]")
        return 2

    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)

    mode_label = "video panjang" if args.clip_mode == "highlight_5m" else "klip pendek"
    emit_progress(3, "source", f"Menyiapkan sumber untuk {mode_label}")

    if args.source_file:
        source_file = Path(args.source_file)
        title = source_file.stem or "uploaded-video"
        work_dir = root / slugify(title)[:80]
        console.print("[bold]Using uploaded video...[/bold]")
        final_video_path, metadata = prepare_uploaded_source(source_file, work_dir)
        emit_progress(16, "source", "Video upload lokal siap diproses")
    else:
        console.print("[bold]Fetching metadata...[/bold]")
        metadata = fetch_metadata(args.url)
        if args.require_creative_commons:
            require_creative_commons_metadata(metadata)
            console.print(f"[green]Creative Commons license detected:[/green] {metadata.get('license') or '-'}")
        title = metadata.get("title") or metadata.get("id") or "youtube-video"
        work_dir = root / slugify(title)[:80]
        work_dir.mkdir(parents=True, exist_ok=True)

        console.print("[bold]Fetching video...[/bold]")
        final_video_path, metadata = download_video(
            args.url,
            work_dir,
            force=args.force,
            video_quality=args.video_quality,
        )
        emit_progress(16, "source", "Video sumber berhasil disiapkan")
    save_json(work_dir / "metadata.json", metadata)

    cache_suffix = f"_{int(args.analyze_seconds)}s" if args.analyze_seconds else ""
    emit_progress(20, "transcript", "Mengekstrak audio dari video")
    console.print("[bold]Extracting audio...[/bold]")
    audio_path = extract_audio(
        final_video_path,
        work_dir / f"audio{cache_suffix}.wav",
        force=args.force,
        limit_seconds=args.analyze_seconds,
    )
    emit_progress(28, "transcript", "Mentranskripsi ucapan dan menyusun timestamp")
    transcript = transcribe(
        audio_path,
        work_dir / f"transcript{cache_suffix}.json",
        args.model,
        args.language,
        force=args.force,
    )

    emit_progress(46, "selection", "Menilai kandidat berdasarkan hook dan kelengkapan cerita")
    console.print("[bold]Scoring candidate clips...[/bold]")
    pool = build_candidate_pool(transcript, args.min, args.max)
    if not pool:
        console.print("[red]No clip candidates found. Try lowering --min or increasing --max.[/red]")
        return 1

    ai_config = AIConfig(
        enabled=args.ai_enabled,
        base_url=args.ai_base_url,
        model=args.ai_model,
        api_key=args.ai_api_key,
    )
    ai_target_count = (
        min(12, max(4, math.ceil(args.compilation_target / 60)))
        if args.clip_mode == "highlight_5m"
        else min(12, max(1, args.top))
    )
    pool = ai_rescore_candidates(
        pool,
        ai_config,
        target_count=ai_target_count,
        compilation=args.clip_mode == "highlight_5m",
    )
    candidates, compilation_candidates = select_output_candidates(
        pool,
        clip_mode=args.clip_mode,
        short_limit=args.top,
        compilation_target=args.compilation_target,
    )
    emit_progress(
        59,
        "selection",
        f"{len(candidates)} kandidat terbaik terpilih untuk {mode_label}",
    )
    if not candidates:
        console.print("[red]No clip candidates found. Try lowering --min or increasing --max.[/red]")
        return 1

    if not args.no_enhanced_edit:
        emit_progress(63, "selection", "Merapikan hook, alur, dan ending kandidat")
        console.print("[bold]Applying Codex structural edits to hook and ending...[/bold]")
        candidates = apply_codex_edits_to_candidates(
            candidates,
            transcript,
            min_duration=args.min,
            max_duration=args.max,
        )
        if args.clip_mode == "highlight_5m":
            compilation_candidates = candidates
        else:
            # Structural intro/ending edits recalculate story metrics. Guard
            # against exporting a candidate that became incomplete afterward.
            candidates = [
                item for item in candidates if candidate_has_cohesive_editorial_arc(item)
            ]
            if not candidates:
                console.print(
                    "[red]No upload-ready clip candidates remained after structural edits. "
                    "Try increasing --max or the analyzed duration.[/red]"
                )
                return 1

    save_json(work_dir / f"candidates{cache_suffix}.json", [asdict(item) for item in candidates])
    print_candidates(candidates)

    if args.review_only:
        console.print("[green]Review candidates ready.[/green]")
        return 0

    if args.export_indexes:
        selected_indexes = {
            int(part.strip())
            for part in args.export_indexes.split(",")
            if part.strip().isdigit()
        }
        candidates = [item for item in candidates if item.index in selected_indexes]
        if not candidates:
            console.print("[red]No matching candidate indexes to export.[/red]")
            return 1

    caption_style = CaptionStyle(
        font_size=args.caption_font_size,
        position=args.caption_position,
        color=args.caption_color,
        font_family=args.caption_font,
        outline_width=args.caption_outline,
        outline_color=args.caption_outline_color,
    )

    required_hashtags = [tag for tag in args.required_hashtags.split(",") if tag.strip()]

    clips_dir = work_dir / "clips"
    if not args.no_enhanced_edit:
        console.print("[bold]Applying enhanced motion graphics...[/bold]")
    if args.clip_mode == "highlight_5m":
        emit_progress(70, "render", "Merakit resume cerita landscape 16:9")
        console.print("[bold]Exporting 16:9 cinematic story resume with POV and core narrative...[/bold]")
        exported = [
            export_compilation(
                final_video_path,
                compilation_candidates,
                transcript,
                clips_dir,
                not args.no_burn_subtitles,
                args.crop_mode,
                caption_style,
                ai_config,
                args.cam_corner,
                required_hashtags,
                args.video_quality,
                args.visual_mode,
                args.background_mode,
                not args.no_enhanced_edit,
                args.remove_running_text and not args.keep_running_text,
                args.auto_blur_watermarks,
            )
        ]
        emit_progress(93, "render", "Render video panjang selesai")
    else:
        console.print("[bold]Exporting vertical short clips...[/bold]")
        exported = []
        total_candidates = len(candidates)
        for export_index, candidate in enumerate(candidates, start=1):
            render_start = 68 + round(((export_index - 1) / max(1, total_candidates)) * 25)
            emit_progress(
                render_start,
                "render",
                f"Merender klip pendek {export_index} dari {total_candidates}",
            )
            clip_segments = segments_for_clip(transcript, candidate)
            exported.append(
                export_clip(
                    final_video_path,
                    candidate,
                    clip_segments,
                    clips_dir,
                    not args.no_burn_subtitles,
                    args.crop_mode,
                    caption_style,
                    ai_config,
                    args.cam_corner,
                    required_hashtags,
                    args.video_quality,
                    enhanced_edit=not args.no_enhanced_edit,
                    remove_running_text=args.remove_running_text and not args.keep_running_text,
                    auto_blur_watermarks=args.auto_blur_watermarks,
                    visual_mode=args.visual_mode,
                    background_mode=args.background_mode,
                )
            )
            render_done = 68 + round((export_index / max(1, total_candidates)) * 25)
            emit_progress(
                render_done,
                "render",
                f"Klip pendek {export_index} dari {total_candidates} selesai",
            )

    emit_progress(95, "finalize", "Menyimpan audit, metadata, dan kesiapan monetisasi")
    attach_monetization_provenance(
        exported,
        metadata,
        uploaded_source=bool(args.source_file),
    )

    if not args.keep_intermediate:
        emit_progress(98, "finalize", "Membersihkan file sementara")
        cleanup_intermediate(work_dir, final_video_path)

    emit_progress(100, "complete", "Semua hasil siap direview dan diunduh")
    console.print("[green]Done.[/green] Exported:")
    for path in exported:
        console.print(f"  {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise SystemExit(130)
    except UserFacingError as exc:
        console.print(f"[red]USER_ERROR:[/red] {exc}")
        raise SystemExit(2)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)
