from __future__ import annotations

import argparse
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
    "allah",
    "alquran",
    "dakwah",
    "doa",
    "hadis",
    "hadits",
    "hijrah",
    "hikmah",
    "ibadah",
    "iman",
    "islam",
    "kajian",
    "masjid",
    "muslim",
    "nabi",
    "neraka",
    "quran",
    "sedekah",
    "shalat",
    "surga",
    "ustadz",
}

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
VisualTheme = Literal["mystery", "islamic", "warning", "inspiring", "knowledge"]
YUNET_MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"

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
    },
    "high": {
        "label": "high quality",
        "crf": "17",
        "preset": "medium",
        "profile": "high",
        "level": "4.2",
        "audio_bitrate": "192k",
        "max_download_height": 2160,
        "sharpen": "unsharp=5:5:0.35:3:3:0.15",
    },
    "max": {
        "label": "maximum quality",
        "crf": "15",
        "preset": "slow",
        "profile": "high",
        "level": "4.2",
        "audio_bitrate": "256k",
        "max_download_height": 2160,
        "sharpen": "unsharp=5:5:0.45:3:3:0.20",
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
    r"\bhana kan\b": "menggunakan",
    r"\bpengatahuan\b": "pengetahuan",
    r"\bbarang-barang\b": "bareng-bareng",
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
                "veryfast",
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
    sharpen = str(quality_preset(video_quality)["sharpen"])
    return f"{vf},{sharpen}" if sharpen else vf


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


def remove_running_text_filter(crop_bottom: int = 160) -> str:
    """Crop a source footer/ticker and rescale without changing the 9:16 aspect ratio."""
    safe_crop = max(80, min(260, int(crop_bottom)))
    crop_height = 1920 - safe_crop
    crop_width = int(round(crop_height * 9 / 16))
    if crop_width % 2:
        crop_width += 1
    crop_x = max(0, (1080 - crop_width) // 2)
    return (
        f"crop={crop_width}:{crop_height}:{crop_x}:0,"
        "scale=1080:1920:flags=lanczos,setsar=1"
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
    existing = sorted(work_dir.glob("source.*"))
    if existing and info_path.exists() and not force:
        return existing[0], load_json(info_path)

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
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = Path(ydl.prepare_filename(info))
    except Exception as exc:
        raise UserFacingError(friendly_youtube_error(exc, "mengunduh video")) from exc

    if not file_path.exists():
        downloaded = sorted(work_dir.glob("source.*"))
        if not downloaded:
            raise FileNotFoundError("Downloaded video was not found.")
        file_path = downloaded[0]

    save_json(info_path, sanitize_metadata(info))
    return file_path, sanitize_metadata(info)


def sanitize_metadata(info: dict) -> dict:
    keys = ["id", "title", "uploader", "duration", "webpage_url", "ext", "license"]
    return {key: info.get(key) for key in keys}


def extract_audio(video_path: Path, audio_path: Path, force: bool = False, limit_seconds: float | None = None) -> Path:
    if audio_path.exists() and not force:
        return audio_path

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
        "-c:a",
        "pcm_s16le",
    ]
    if limit_seconds:
        command.extend(["-t", f"{limit_seconds:.3f}"])
    command.append(str(audio_path))
    run(command)
    return audio_path


def transcribe(audio_path: Path, transcript_path: Path, model_name: str, language: str, force: bool = False) -> list[TranscriptSegment]:
    if transcript_path.exists() and not force:
        return [
            TranscriptSegment(
                start=float(item["start"]),
                end=float(item["end"]),
                text=clean_transcript_text(item["text"]),
            )
            for item in load_json(transcript_path)
        ]

    from faster_whisper import WhisperModel

    console.print(f"[bold]Loading model:[/bold] {model_name}")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        beam_size=1,
        best_of=1,
    )

    rows: list[TranscriptSegment] = []
    for segment in segments:
        text = clean_transcript_text(segment.text)
        if text:
            rows.append(TranscriptSegment(float(segment.start), float(segment.end), text))

    save_json(transcript_path, [asdict(item) for item in rows])
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


def select_candidates(candidates: list[ClipCandidate], limit: int) -> list[ClipCandidate]:
    candidates = candidates[:]
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
    max_parts: int = 12,
) -> list[ClipCandidate]:
    """Pick strong, non-overlapping moments until a highlight reel is ~target_duration."""
    if target_duration <= 0:
        return []

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
        render_duration = best.end - best.start
        if render_duration > seconds_left >= 8:
            best = ClipCandidate(
                index=best.index,
                start=best.start,
                end=best.start + seconds_left,
                duration=seconds_left,
                score=best.score,
                title=best.title,
                reason=best.reason,
                text=best.text,
                hook=best.hook,
                pov=best.pov,
                fyp_label=best.fyp_label,
                strengths=list(best.strengths),
                weaknesses=list(best.weaknesses),
                improvement_ideas=list(best.improvement_ideas),
                applied_edits=list(best.applied_edits),
                key_point_score=best.key_point_score,
                loop_score=best.loop_score,
                boundary_quality=best.boundary_quality,
            )
        picked.append(best)
        total += best.end - best.start

    picked.sort(key=lambda item: item.start)
    for idx, candidate in enumerate(picked, start=1):
        candidate.index = idx
    return picked


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
    "moments. Reject source-channel intros, outros, credits, sponsor mentions, requests to subscribe/follow, "
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
        "This is for one five-minute 16:9 landscape long-form highlight compilation. Choose complementary "
        "key points that build a coherent narrative in chronological order; open with the strongest hook, "
        "avoid repeated ideas and low-value filler, and favor sections that benefit from full context."
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
    return [
        item
        for item in segments
        if item.end > clip.start
        and item.start < clip.end
        and not is_source_branding_segment(item)
    ]


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
                "Arahan visual diterapkan: poin utama diberi emphasis pulse dan aksen frame."
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


def hook_banner_text(clip: ClipCandidate) -> str:
    title = first_sentence(clip.hook or clip.title, max_words=8).upper()
    chunks = split_subtitle_text(title, max_chars=24, max_lines=2)
    return (chunks[0] if chunks else title)[:80]


def pov_banner_text(clip: ClipCandidate) -> str:
    pov = re.sub(r"^\s*pov\s*:\s*", "", clip.pov or fallback_pov_angle(clip.text), flags=re.I)
    short_pov = first_sentence(pov, max_words=12)
    chunks = split_subtitle_text(short_pov, max_chars=48, max_lines=2)
    return (chunks[0] if chunks else short_pov)[:110]


def payoff_banner_text(clip: ClipCandidate, clip_segments: list[TranscriptSegment]) -> str:
    """Use the actual closing transcript as the payoff card—never invented copy."""
    ending = clip_segments[-1].text if clip_segments else clip.text
    value = first_sentence(ending, max_words=10).upper()
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


def visual_theme_profile(clip: ClipCandidate) -> dict[str, str]:
    theme = detect_visual_theme(clip)
    has_islamic_context = bool(
        set(re.findall(r"[\w']+", f"{clip.title} {clip.text}".lower())).intersection(ISLAMIC_WORDS)
    )
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


def detect_reaction_cues(
    clip: ClipCandidate,
    clip_segments: list[TranscriptSegment],
    *,
    limit: int = 4,
    min_gap: float = 5.5,
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
    base_x = 828 if cue.side == "right" else 68
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
        f"movie='{escaped_path}',scale={size}:{size}:flags=lanczos,format=rgba[{sticker_label}];"
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


def contextual_audio_mix_filter(base_filter: str, cues: list[SoundEffectCue]) -> str:
    """Mix original synthetic micro-SFX under speech and cap peaks safely."""
    if not cues:
        return f"[0:a:0]{base_filter},aformat=sample_rates=48000:channel_layouts=stereo[audio_out]"

    chains = [
        f"[0:a:0]{base_filter},aformat=sample_rates=48000:channel_layouts=stereo[voice]"
    ]
    mix_inputs = ["[voice]"]
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


def landscape_compilation_frame_filter(
    accent: str,
    secondary: str,
    *,
    remove_running_text: bool = True,
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


def landscape_compilation_edit_filter(
    duration: float,
    hook_text_filename: str,
    *,
    section_number: int,
    section_count: int,
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
    """Build a restrained dual-tone glow around the inset sharp video panel."""
    return [
        f"drawbox=x=30:y=61:w=1020:h=1798:color={secondary}@0.20:t=12",
        f"drawbox=x=35:y=66:w=1010:h=1788:color={accent}@0.62:t=7",
        "drawbox=x=39:y=70:w=1002:h=1780:color=white@0.22:t=2",
        f"drawbox=x=35:y=66:w=505:h=7:color={secondary}@0.94:t=fill",
        f"drawbox=x=540:y=1847:w=505:h=7:color={secondary}@0.86:t=fill",
        f"drawbox=x=35:y=960:w=7:h=894:color={secondary}@0.78:t=fill",
        f"drawbox=x=1038:y=66:w=7:h=894:color={secondary}@0.78:t=fill",
    ]


def enhanced_edit_filter(
    duration: float,
    hook_text_filename: str,
    *,
    pov_text_filename: str = "",
    show_progress: bool = True,
    theme_profile: dict[str, str] | None = None,
    emphasis_times: list[float] | None = None,
    variation: int = 0,
    show_text_overlays: bool = True,
    reaction_cues: list[ReactionCue] | None = None,
    show_reactions: bool = True,
    codex_plan: CodexEditPlan | None = None,
    payoff_text_filename: str = "",
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
    motion_variant = max(0, variation) % 3
    scale_width = 1120 + motion_variant * 20
    scale_height = int(round(scale_width * 16 / 9))
    if scale_height % 2:
        scale_height += 1
    center_x = (scale_width - 1080) / 2
    center_y = (scale_height - 1920) / 2
    amp_x = min(12.0, max(4.0, center_x - 2))
    amp_y = min(16.0, max(6.0, center_y - 2))
    x_period = 7 - motion_variant
    y_period = 5 + motion_variant
    badge_width = min(430, max(250, len(badge) * 17 + 60))
    adaptive_plan = codex_plan or CodexEditPlan()
    filters = [
        grade,
        f"scale={scale_width}:{scale_height}:flags=lanczos",
        "crop=1080:1920:"
        f"x='{center_x:.1f}+{amp_x:.1f}*sin(2*PI*t/{x_period})':"
        f"y='{center_y:.1f}+{amp_y:.1f}*sin(2*PI*t/{y_period})'",
        "vignette=PI/9",
        "fade=t=in:st=0:d=0.18",
        modern_blurred_video_frame_filter(accent, accent_secondary),
    ]
    filters.extend(modern_gradient_border_filters(accent, accent_secondary))
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
        filters.extend(
            [
                f"drawbox=x=48:y=62:w={badge_width}:h=48:color={accent}@0.92:t=fill:"
                "enable='between(t,0.06,3.80)'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{badge}':expansion=none:fontcolor=white:fontsize=23:"
                "x=68:y=73:enable='between(t,0.06,3.80)'",
                "drawbox=x=48:y=120:w=984:h=250:color=black@0.62:t=fill:"
                "enable='between(t,0.10,3.80)'",
                f"drawbox=x=48:y=120:w=14:h=250:color={accent}@0.98:t=fill:"
                "enable='between(t,0.10,3.80)'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"textfile='{hook_text_filename}':reload=0:expansion=none:"
                "fontcolor=white:fontsize=48:line_spacing=10:borderw=2:bordercolor=black@0.85:"
                "x='if(lt(t,0.48),-text_w+(t-0.10)*(76+text_w)/0.38,76)':y=168:"
                "enable='between(t,0.10,3.80)'",
            ]
        )
        if pov_text_filename:
            pov_end = min(safe_duration, 9.2)
            if pov_end > 4.2:
                filters.extend(
                    [
                        "drawbox=x=78:y=126:w=924:h=116:color=black@0.68:t=fill:"
                        f"enable='between(t,4.20,{pov_end:.3f})'",
                        f"drawbox=x=78:y=126:w=9:h=116:color={accent_secondary}@0.96:t=fill:"
                        f"enable='between(t,4.20,{pov_end:.3f})'",
                        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                        f"text='POV':expansion=none:fontcolor={accent_secondary}:fontsize=20:"
                        f"x=108:y=144:enable='between(t,4.20,{pov_end:.3f})'",
                        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                        f"textfile='{pov_text_filename}':reload=0:expansion=none:"
                        "fontcolor=white:fontsize=27:line_spacing=5:borderw=1:bordercolor=black@0.82:"
                        f"x=108:y=176:enable='between(t,4.20,{pov_end:.3f})'",
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
                    "drawbox=x=594:y=382:w=438:h=108:color=black@0.74:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    f"drawbox=x=594:y=382:w=438:h=7:color={accent}@0.98:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    f"drawbox=x=612:y=408:w=58:h=58:color={accent}@0.98:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    "text='!':expansion=none:fontcolor=white:fontsize=38:"
                    f"x=634:y=411:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='NOTICE':expansion=none:fontcolor={accent_secondary}:fontsize=17:"
                    f"x=690:y=400:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='{emphasis_label}':expansion=none:fontcolor=white:fontsize=25:"
                    f"x=690:y=426:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    f"drawbox=x=594:y=484:w=438:h=3:color={accent_secondary}@0.74:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                ]
            )
    if show_text_overlays and payoff_text_filename and adaptive_plan.ending_boost:
        card_start = max(0.2, safe_duration - 3.35)
        card_end = max(card_start + 0.2, safe_duration - 1.28)
        filters.extend(
            [
                "drawbox=x=48:y=124:w=984:h=224:color=black@0.76:t=fill:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                f"drawbox=x=48:y=124:w=14:h=224:color={accent_secondary}@0.98:t=fill:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                f"drawbox=x=76:y=142:w=244:h=42:color={accent}@0.94:t=fill:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                "text='INTI / PAYOFF':expansion=none:fontcolor=white:fontsize=20:x=94:y=151:"
                f"enable='between(t,{card_start:.3f},{card_end:.3f})'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"textfile='{payoff_text_filename}':reload=0:expansion=none:"
                "fontcolor=white:fontsize=39:line_spacing=8:borderw=2:bordercolor=black@0.86:"
                f"x=82:y=210:enable='between(t,{card_start:.3f},{card_end:.3f})'",
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


def write_srt(path: Path, segments: list[TranscriptSegment], offset: float, clip_duration: float) -> None:
    lines: list[str] = []
    cue_index = 1
    for item in segments:
        start = max(0, item.start - offset)
        end = min(clip_duration, max(start + 0.2, item.end - offset))
        if start >= clip_duration or end - start < 0.45:
            continue

        chunks = split_subtitle_text(item.text)
        chunk_duration = (end - start) / max(1, len(chunks))
        for chunk_idx, chunk in enumerate(chunks):
            chunk_start = start + chunk_duration * chunk_idx
            chunk_end = end if chunk_idx == len(chunks) - 1 else start + chunk_duration * (chunk_idx + 1)
            lines.extend(
                [
                    str(cue_index),
                    f"{seconds_to_stamp(chunk_start, srt=True)} --> {seconds_to_stamp(chunk_end, srt=True)}",
                    chunk,
                    "",
                ]
            )
            cue_index += 1
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
SOFT_CAPTION_BACK_COLOR = "&HC8000000"
SOFT_CAPTION_SHADOW = 0.35


@dataclass
class CaptionStyle:
    font_size: int = 10
    position: CaptionPosition = "upper"
    color: str = "#FFFFFF"
    font_family: str = DEFAULT_FONT
    outline_width: float = 1.5
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
        margin_v = 24
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


def caption_gradient_blur_filter(position: CaptionPosition) -> str:
    """Return a soft blurred video band with a vertical alpha gradient behind captions."""
    band_height = 380
    if position == "bottom":
        band_y = 1450
    elif position == "center":
        band_y = 770
    else:
        band_y = 280
    alpha = "255*0.88*(1-pow(abs(Y-H/2)/(H/2),2))"
    return (
        "split=2[caption_base][caption_blur];"
        f"[caption_blur]crop=1080:{band_height}:0:{band_y},"
        "gblur=sigma=24,drawbox=color=black@0.24:t=fill,format=rgba,"
        f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[caption_band];"
        f"[caption_base][caption_band]overlay=0:{band_y}"
    )


def landscape_caption_gradient_blur_filter(position: CaptionPosition) -> str:
    """Add a restrained readable band sized for a 1920x1080 long-form canvas."""
    band_height = 250
    if position == "bottom":
        band_y = 760
    elif position == "center":
        band_y = 415
    else:
        band_y = 105
    alpha = "255*0.82*(1-pow(abs(Y-H/2)/(H/2),2))"
    return (
        "split=2[wide_caption_base][wide_caption_blur];"
        f"[wide_caption_blur]crop=1920:{band_height}:0:{band_y},"
        "gblur=sigma=28,drawbox=color=black@0.28:t=fill,format=rgba,"
        f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[wide_caption_band];"
        f"[wide_caption_base][wide_caption_band]overlay=0:{band_y}"
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
                f'Add a bold {format_name} thumbnail text overlay reading "{fallback_hook}" '
                "onto the provided screenshot. Keep the screenshot itself untouched as the background. "
                "Place large high-contrast bold text (white fill, thick dark outline) with strong 16:9 composition, "
                "do not cover faces, do not redraw or restyle the background image."
            ),
        }

    user_prompt = (
        f"Create a compelling {format_name} thumbnail text overlay plan for this clip. The user already has a screenshot "
        "(the best moment) and will feed it plus your prompt to an image generator that only writes text.\n"
        "Return JSON exactly like:\n"
        '{"hook_text": "<3-6 word punchy hook, ALL CAPS>", '
        '"prompt": "<instruction for the image generator: what text to write, where to place it, '
        'style (bold, high contrast, outline), and an explicit rule to keep the screenshot background '
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
    "Do not invent certainty. Never mention, thank, promote, credit, or ask viewers to follow the source "
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
    remove_running_text: bool = True,
    output_format: OutputFormat = "vertical_short",
    compilation_part_number: int = 1,
    compilation_part_count: int = 1,
) -> Path:
    clips_dir.mkdir(parents=True, exist_ok=True)
    base_name = base_name_override or f"clip_{clip.index:02}_{slugify(clip.title)[:72] or 'auto'}"
    srt_path = clips_dir / f"{base_name}.srt"
    json_path = clips_dir / f"{base_name}.json"
    out_path = clips_dir / f"{base_name}.mp4"
    temp_video_path = clips_dir / f"{base_name}.video_tmp.mp4"
    temp_audio_path = clips_dir / f"{base_name}.audio_tmp.wav"
    hook_text_path = clips_dir / f"{base_name}.hook.txt"
    pov_text_path = clips_dir / f"{base_name}.pov.txt"
    payoff_text_path = clips_dir / f"{base_name}.payoff.txt"
    json_path.unlink(missing_ok=True)

    duration = clip.end - clip.start
    adaptive_plan = codex_edit_plan(clip)
    theme_profile = visual_theme_profile(clip)
    emphasis_times = emphasis_timestamps(clip, clip_segments)
    reaction_cues = detect_reaction_cues(clip, clip_segments)
    sound_effect_cues = (
        contextual_sound_effect_cues(
            duration,
            reaction_cues,
            emphasis_times,
            limit=3 if output_format == "landscape_compilation" else 5,
            min_gap=7.0 if output_format == "landscape_compilation" else 3.0,
        )
        if enhanced_edit
        else []
    )
    if enhanced_edit:
        sound_effect_cues = apply_codex_audio_cues(sound_effect_cues, duration, adaptive_plan)
    drawtext_supported = ffmpeg_has_filter("drawtext")
    applied_edits = list(clip.applied_edits)
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
    reaction_overlays_supported = output_format == "vertical_short" and (
        ffmpeg_has_filter("movie")
        and ffmpeg_has_filter("overlay")
        and all((REACTION_ASSET_DIR / f"{cue.kind}.svg").is_file() for cue in reaction_cues)
    )
    write_srt(srt_path, clip_segments, clip.start, duration)
    sidecar_payload = {
        **asdict(clip),
        "enhanced_edit": enhanced_edit,
        "remove_running_text": remove_running_text,
        "visual_theme": theme_profile["theme"],
        "emphasis_times": emphasis_times,
        "reaction_cues": [asdict(cue) for cue in reaction_cues],
        "sound_effect_cues": [asdict(cue) for cue in sound_effect_cues],
        "drawtext_supported": drawtext_supported,
        "subtitles_supported": subtitles_supported,
        "reaction_overlays_supported": reaction_overlays_supported,
        "improvement_ideas": remaining_ideas,
        "applied_edits": applied_edits,
        "codex_ideas_resolved": len(clip.improvement_ideas) - len(remaining_ideas),
        "codex_edit_plan": asdict(adaptive_plan),
        "video_quality": video_quality,
        "output_format": output_format,
        "aspect_ratio": "16:9" if output_format == "landscape_compilation" else "9:16",
        "source_metadata_embedded": False,
    }

    if output_format == "landscape_compilation":
        vf = landscape_compilation_frame_filter(
            theme_profile["accent"],
            theme_profile.get("accent_secondary", "#22D3EE"),
            remove_running_text=remove_running_text,
        )
    elif crop_mode == "streamer":
        vf = streamer_crop_filter(video_path, clip, cam_corner)
    else:
        vf = vertical_crop_filter(video_path, clip, crop_mode)
    if remove_running_text and output_format == "vertical_short":
        vf = f"{vf},{remove_running_text_filter()}"
    vf = add_quality_sharpen(vf, video_quality)
    if enhanced_edit:
        if drawtext_supported:
            hook_text_path.write_text(hook_banner_text(clip) + "\n", encoding="utf-8")
            pov_text_path.write_text(pov_banner_text(clip) + "\n", encoding="utf-8")
            payoff_text_path.write_text(
                payoff_banner_text(clip, clip_segments) + "\n",
                encoding="utf-8",
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
                    theme_profile=theme_profile,
                    emphasis_times=emphasis_times,
                    show_text_overlays=drawtext_supported,
                )}"
            )
        else:
            vf = (
                f"{vf},"
                f"{enhanced_edit_filter(
                    duration,
                    hook_text_path.name,
                    pov_text_filename=pov_text_path.name if drawtext_supported else "",
                    show_progress=generate_assets,
                    theme_profile=theme_profile,
                    emphasis_times=emphasis_times,
                    variation=max(0, clip.index - 1),
                    show_text_overlays=drawtext_supported,
                    reaction_cues=reaction_cues,
                    show_reactions=reaction_overlays_supported,
                    codex_plan=adaptive_plan,
                    payoff_text_filename=payoff_text_path.name if drawtext_supported else "",
                )}"
            )
    if burn_subtitles and clip_segments and subtitles_supported:
        style = build_subtitle_style(caption or CaptionStyle())
        if output_format == "landscape_compilation":
            vf = (
                f"{vf},{landscape_caption_gradient_blur_filter((caption or CaptionStyle()).position)},"
                f"subtitles='{srt_path.name}'"
                ":original_size=1920x1080"
                f":force_style='{style}'"
            )
        else:
            vf = (
                f"{vf},{caption_gradient_blur_filter((caption or CaptionStyle()).position)},"
                f"subtitles='{srt_path.name}'"
                ":original_size=1080x1920"
                f":force_style='{style}'"
            )
    elif burn_subtitles and clip_segments:
        console.print(
            "[yellow]FFmpeg tidak memiliki filter subtitles; file SRT tetap dibuat "
            "dan export video dilanjutkan tanpa burn subtitle.[/yellow]"
        )

    common_input = [
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
                *common_input,
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
                "-crf",
                str(quality["crf"]),
                "-pix_fmt",
                "yuv420p",
                *ffmpeg_clean_metadata_args(),
                str(temp_video_path.name),
            ],
            cwd=clips_dir,
        )
    finally:
        hook_text_path.unlink(missing_ok=True)
        pov_text_path.unlink(missing_ok=True)
        payoff_text_path.unlink(missing_ok=True)
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
        *common_input,
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
    if sound_effect_cues:
        try:
            run(
                [
                    *common_input,
                    "-filter_complex",
                    contextual_audio_mix_filter(audio_filter, sound_effect_cues),
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
        except RuntimeError as exc:
            temp_audio_path.unlink(missing_ok=True)
            console.print(
                f"[yellow]Sound effect kontekstual dilewati; audio dialog tetap dipakai:[/yellow] {exc}"
            )
            run(plain_audio_command, cwd=clips_dir)
    else:
        run(plain_audio_command, cwd=clips_dir)
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
            str(temp_audio_path.name),
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
        if grab_best_frame(video_path, clip, thumb_path) is not None:
            thumb_prompt = generate_thumbnail_prompt(clip, ai_config or AIConfig())
            if thumb_prompt:
                prompt_path.write_text(
                    f"HOOK: {thumb_prompt['hook_text']}\n\n{thumb_prompt['prompt']}\n",
                    encoding="utf-8",
                )

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
    enhanced_edit: bool = True,
    remove_running_text: bool = True,
) -> Path:
    clips_dir.mkdir(parents=True, exist_ok=True)
    parts_dir = clips_dir / ".compilation_parts"
    shutil.rmtree(parts_dir, ignore_errors=True)
    parts_dir.mkdir(parents=True, exist_ok=True)

    strongest = max(candidates, key=lambda item: item.score)
    base_name = f"highlight_5menit_{slugify(strongest.title)[:60] or 'pilihan-terbaik'}"
    out_path = clips_dir / f"{base_name}.mp4"
    srt_path = clips_dir / f"{base_name}.srt"
    json_path = clips_dir / f"{base_name}.json"
    prompt_path = clips_dir / f"{base_name}_thumb.txt"
    thumb_path = clips_dir / f"{base_name}_thumb.jpg"

    part_paths: list[Path] = []
    try:
        for idx, candidate in enumerate(candidates, start=1):
            part_paths.append(
                export_clip(
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
                    output_format="landscape_compilation",
                    compilation_part_number=idx,
                    compilation_part_count=len(candidates),
                )
            )

        concat_path = parts_dir / "concat.txt"
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
    compilation = ClipCandidate(
        index=1,
        start=min(item.start for item in candidates),
        end=max(item.end for item in candidates),
        duration=total_duration,
        score=compilation_score,
        title=f"Highlight Terpenting: {strongest.title}"[:80],
        reason=f"Kompilasi {len(candidates)} poin penting, dipilih untuk hook, value, dan payoff.",
        text=" ".join(item.text for item in candidates),
        hook=strongest.hook or strongest.title,
        pov=strongest.pov or fallback_pov_angle(strongest.text),
        fyp_label=fyp_score_label(compilation_score),
        strengths=combined_strengths,
        weaknesses=combined_weaknesses,
        improvement_ideas=combined_ideas,
        applied_edits=combined_applied_edits,
    )
    save_json(
        json_path,
        {
            **asdict(compilation),
            "mode": "highlight_5m",
            "output_format": "landscape_compilation",
            "aspect_ratio": "16:9",
            "layout": "cinematic_blurred_frame_with_chapter_cards",
            "enhanced_edit": enhanced_edit,
            "remove_running_text": remove_running_text,
            "source_metadata_embedded": False,
            "parts": [asdict(item) for item in candidates],
            "video_quality": video_quality,
            "output_width": output_width,
            "output_height": output_height,
            "output_resolution": f"{output_width}x{output_height}",
        },
    )

    strongest_offset = sum(
        item.end - item.start
        for item in candidates[: candidates.index(strongest)]
    )
    strongest_timestamp = strongest_offset + (strongest.end - strongest.start) * 0.5
    if grab_frame_at(
        out_path,
        strongest_timestamp,
        thumb_path,
        label="kompilasi landscape",
    ) is not None:
        thumb_prompt = generate_thumbnail_prompt(compilation, ai_config, long_form=True)
        if thumb_prompt:
            prompt_path.write_text(
                f"HOOK: {thumb_prompt['hook_text']}\n\n{thumb_prompt['prompt']}\n",
                encoding="utf-8",
            )
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
        help="Export vertical shorts only, or one separate five-minute landscape compilation",
    )
    parser.add_argument(
        "--compilation-target",
        type=float,
        default=300,
        help="Target duration in seconds for highlight_5m mode",
    )
    parser.add_argument("--model", default="Systran/faster-whisper-small", help="faster-whisper model name")
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
        default="center",
        help="center, person-focused, or streamer (webcam stacked over gameplay)",
    )
    parser.add_argument(
        "--cam-corner",
        choices=["auto", "br", "bl", "tr", "tl"],
        default="auto",
        help="Webcam corner in the source for streamer mode (auto-detect by default)",
    )
    parser.add_argument("--force", action="store_true", help="Redo download, audio extraction, and transcription")
    parser.add_argument("--ai-enabled", action="store_true", help="Use an LLM agent to rescore clip candidates")
    parser.add_argument("--ai-base-url", default="", help="OpenAI-compatible base URL, e.g. http://localhost:20128/v1")
    parser.add_argument("--ai-model", default="", help="LLM model name for the clip agent")
    parser.add_argument("--ai-api-key", default="", help="API key for the LLM endpoint")
    parser.add_argument("--caption-font-size", type=int, default=10, help="Burned caption font size (6-120)")
    parser.add_argument(
        "--caption-position",
        choices=["upper", "center", "bottom"],
        default="upper",
        help="Burned caption vertical position",
    )
    parser.add_argument("--caption-color", default="#FFFFFF", help="Burned caption text color, hex e.g. #FFFFFF")
    parser.add_argument("--caption-font", default=DEFAULT_FONT, help="Burned caption font family")
    parser.add_argument("--caption-outline", type=float, default=1.5, help="Caption border/outline width (0-8)")
    parser.add_argument("--caption-outline-color", default="#000000", help="Caption border color, hex")
    parser.add_argument(
        "--no-enhanced-edit",
        action="store_true",
        help="Disable animated hook, motion, transitions, vignette, and progress graphics",
    )
    parser.add_argument(
        "--keep-running-text",
        action="store_true",
        help="Keep the source footer/running text instead of cropping it from vertical exports",
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Keep the downloaded source video and extracted audio after exporting clips",
    )
    parser.add_argument(
        "--required-hashtags",
        default="",
        help="Comma-separated hashtags always appended to generated captions, e.g. clipforge,viral",
    )
    parser.add_argument(
        "--require-creative-commons",
        action="store_true",
        help="Reject YouTube URLs whose metadata is not Creative Commons/reuse allowed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.clip_mode == "short" and args.max > 60:
        console.print("[yellow]Short clip maximum capped at 60 seconds.[/yellow]")
        args.max = 60.0

    if args.min <= 0 or args.max <= args.min:
        console.print("[red]Invalid duration range.[/red]")
        return 2

    if not args.url and not args.source_file:
        console.print("[red]Provide a YouTube URL or --source-file.[/red]")
        return 2

    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)

    if args.source_file:
        source_file = Path(args.source_file)
        title = source_file.stem or "uploaded-video"
        work_dir = root / slugify(title)[:80]
        console.print("[bold]Using uploaded video...[/bold]")
        final_video_path, metadata = prepare_uploaded_source(source_file, work_dir)
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
    save_json(work_dir / "metadata.json", metadata)

    cache_suffix = f"_{int(args.analyze_seconds)}s" if args.analyze_seconds else ""
    console.print("[bold]Extracting audio...[/bold]")
    audio_path = extract_audio(
        final_video_path,
        work_dir / f"audio{cache_suffix}.wav",
        force=args.force,
        limit_seconds=args.analyze_seconds,
    )
    transcript = transcribe(
        audio_path,
        work_dir / f"transcript{cache_suffix}.json",
        args.model,
        args.language,
        force=args.force,
    )

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
    if not candidates:
        console.print("[red]No clip candidates found. Try lowering --min or increasing --max.[/red]")
        return 1

    if not args.no_enhanced_edit:
        console.print("[bold]Applying Codex structural edits to hook and ending...[/bold]")
        candidates = apply_codex_edits_to_candidates(
            candidates,
            transcript,
            min_duration=args.min,
            max_duration=args.max,
        )
        if args.clip_mode == "highlight_5m":
            compilation_candidates = candidates

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
        console.print("[bold]Exporting 16:9 landscape cinematic highlight compilation...[/bold]")
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
                not args.no_enhanced_edit,
                not args.keep_running_text,
            )
        ]
    else:
        console.print("[bold]Exporting vertical short clips...[/bold]")
        exported = []
        for candidate in candidates:
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
                    remove_running_text=not args.keep_running_text,
                )
            )

    if not args.keep_intermediate:
        cleanup_intermediate(work_dir, final_video_path)

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
