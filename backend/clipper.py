from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
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


ReactionKind = Literal["laugh", "shock", "think", "pray", "warning", "heart"]


@dataclass
class ReactionCue:
    kind: ReactionKind
    start: float
    end: float
    side: Literal["left", "right"]
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
    "hantu",
    "horor",
    "jin",
    "kematian",
    "kubur",
    "merinding",
    "mistis",
    "misteri",
    "mitos",
    "ruqyah",
    "setan",
    "siluman",
    "tumbal",
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
    "merinding",
    "mengejutkan",
    "parah",
    "serius",
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

CropMode = Literal["center", "person", "streamer"]
VideoQuality = Literal["standard", "high", "max"]
ClipMode = Literal["short", "highlight_5m"]
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
    license_text = str(metadata.get("license") or "").lower()
    return "creative commons" in license_text or "cc-by" in license_text or "reuse allowed" in license_text


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


def score_window(items: list[TranscriptSegment], duration: float) -> tuple[int, list[str]]:
    text = " ".join(item.text for item in items)
    words = re.findall(r"[\w']+", text.lower())
    first_word = words[0] if words else ""
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

    score = 35
    reasons: list[str] = []

    if 45 <= duration <= 120:
        score += 18
        reasons.append("durasi pas")
    elif 35 <= duration <= 180:
        score += 12
        reasons.append("durasi masih oke")

    if hook_hits:
        bump = min(24, len(hook_hits) * 6)
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

            text = " ".join(part.text for part in window)
            score, reasons = score_window(window, duration)
            previous_is_branding = start_idx > 0 and branding_flags[start_idx - 1]
            next_is_branding = end_idx + 1 < len(segments) and branding_flags[end_idx + 1]
            # Whisper timestamps can bleed a few frames across segment edges.
            # Keep a small inward guard around removed promos so their audio tail
            # cannot leak into an otherwise clean export.
            safe_start = first.start + (0.45 if previous_is_branding else -0.35)
            safe_end = window[-1].end - (0.35 if next_is_branding else -0.25)
            safe_start = max(0, safe_start)
            safe_end = max(safe_start + 0.2, safe_end)
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
                )
            )
    return candidates


def select_candidates(candidates: list[ClipCandidate], limit: int) -> list[ClipCandidate]:
    candidates = candidates[:]
    candidates.sort(key=lambda item: (item.score - abs(item.duration - 85) * 0.04), reverse=True)
    picked: list[ClipCandidate] = []
    remaining = candidates[:]
    while remaining and len(picked) < limit:
        best: ClipCandidate | None = None
        best_adjusted = -1_000.0
        for candidate in remaining:
            overlaps = any(not (candidate.end < item.start or candidate.start > item.end) for item in picked)
            if overlaps:
                continue
            duration_similarity = min((abs(candidate.duration - item.duration) for item in picked), default=999)
            diversity_bonus = 8 if duration_similarity > 18 else 0
            adjusted = candidate.score - abs(candidate.duration - 85) * 0.04 + diversity_bonus
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
            )
        picked.append(best)
        total += best.end - best.start

    picked.sort(key=lambda item: item.start)
    for idx, candidate in enumerate(picked, start=1):
        candidate.index = idx
    return picked


def select_short_and_compilation_candidates(
    candidates: list[ClipCandidate],
    short_limit: int,
    compilation_target: float = 300,
) -> tuple[list[ClipCandidate], list[ClipCandidate]]:
    """Build independent short and compilation selections from one scored pool."""
    short_pool = [ClipCandidate(**asdict(item)) for item in candidates]
    compilation_pool = [ClipCandidate(**asdict(item)) for item in candidates]
    return (
        select_candidates(short_pool, short_limit),
        select_compilation_candidates(compilation_pool, compilation_target),
    )


AI_RESCORE_POOL_LIMIT = 40
AI_SYSTEM_PROMPT = (
    "You are an expert Indonesian short-form video editor for TikTok FYP, Reels, and YouTube Shorts. "
    "Your job is to choose the strongest POV moments from transcript windows, not to divide the video evenly. "
    "Prioritize clips with a strong first-3-second hook, open loop, tension or controversy, practical value, "
    "surprising/emotional payoff, and self-contained meaning. Penalize intros, outros, filler, repeated ideas, "
    "generic motivation, and clips that need earlier context. Islamic insight, mystery, myth-versus-fact, "
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
        "This is for one five-minute vertical highlight compilation. Choose complementary key points "
        "that remain engaging in chronological order; avoid repeated ideas and low-value filler."
        if compilation
        else "This is for Indonesian short-form FYP. Choose POV moments people would stop scrolling for, "
        "not merely complete transcript chunks."
    )
    user_prompt = (
        f"{count_instruction}\n"
        f"{format_instruction}\n"
        "For each chosen candidate, score 0-100 on viewer-retention and FYP potential.\n"
        "Return clips sorted from strongest to weakest. Use fewer clips if the rest are weak.\n"
        "Respond with JSON shaped exactly like:\n"
        '{"clips": [{"id": <int>, "score": <int 0-100>, '
        '"title": "<catchy hook title, max 8 words>", '
        '"reason": "<short why this has FYP potential>", '
        '"pov": "<short POV angle for viewers>"}]}\n\n'
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
    max_rank_score = 100
    for rank, (cid, entry) in enumerate(ranked_entries):
        candidate = pool[cid]
        ai_score = entry.get("score")
        if isinstance(ai_score, (int, float)):
            normalized_ai_score = max(1, min(100, int(round(ai_score))))
            rank_score = max_rank_score - rank
            candidate.score = max(1, min(100, max(normalized_ai_score, rank_score)))
        else:
            candidate.score = max(1, max_rank_score - rank)
        title = entry.get("title")
        if (
            isinstance(title, str)
            and title.strip()
            and not is_source_branding_segment(title)
        ):
            candidate.title = title.strip()[:80]
        reason = entry.get("reason")
        pov = entry.get("pov")
        reason_parts: list[str] = []
        if isinstance(reason, str) and reason.strip():
            reason_parts.append(reason.strip())
        if isinstance(pov, str) and pov.strip():
            reason_parts.append("POV: " + pov.strip())
        if reason_parts:
            candidate.reason = "AI FYP: " + " | ".join(reason_parts)[:180]
        applied += 1

    if applied:
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
    title = first_sentence(clip.title, max_words=8).upper()
    chunks = split_subtitle_text(title, max_chars=24, max_lines=2)
    return (chunks[0] if chunks else title)[:80]


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
    size = 184 if cue.kind in {"laugh", "shock"} else 166
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
    y_expression = f"1190-32*abs(sin(5*(t-{cue.start:.3f})))"
    return (
        f"null[{base_label}];"
        f"movie='{escaped_path}',scale={size}:{size}:flags=lanczos,format=rgba[{sticker_label}];"
        f"[{base_label}][{sticker_label}]overlay="
        f"x='{x_expression}':y='{y_expression}':eof_action=repeat:"
        f"enable='between(t,{cue.start:.3f},{cue.end:.3f})'"
    )


def modern_gradient_border_filters(accent: str, secondary: str) -> list[str]:
    """Build a restrained dual-tone inner border with a soft depth gradient."""
    return [
        f"drawbox=x=10:y=10:w=1060:h=1900:color={secondary}@0.16:t=14",
        f"drawbox=x=17:y=17:w=1046:h=1886:color={accent}@0.48:t=7",
        "drawbox=x=23:y=23:w=1034:h=1874:color=white@0.16:t=2",
        f"drawbox=x=17:y=17:w=520:h=7:color={secondary}@0.90:t=fill",
        f"drawbox=x=543:y=1896:w=520:h=7:color={secondary}@0.82:t=fill",
        f"drawbox=x=17:y=950:w=7:h=946:color={secondary}@0.74:t=fill",
        f"drawbox=x=1056:y=17:w=7:h=946:color={secondary}@0.74:t=fill",
    ]


def enhanced_edit_filter(
    duration: float,
    hook_text_filename: str,
    *,
    show_progress: bool = True,
    theme_profile: dict[str, str] | None = None,
    emphasis_times: list[float] | None = None,
    variation: int = 0,
    show_text_overlays: bool = True,
    reaction_cues: list[ReactionCue] | None = None,
    show_reactions: bool = True,
) -> str:
    """Add context-aware motion graphics while keeping faces and captions readable."""
    safe_duration = max(0.1, duration)
    fade_out_start = max(0.0, safe_duration - 0.24)
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
    filters = [
        grade,
        f"scale={scale_width}:{scale_height}:flags=lanczos",
        "crop=1080:1920:"
        f"x='{center_x:.1f}+{amp_x:.1f}*sin(2*PI*t/{x_period})':"
        f"y='{center_y:.1f}+{amp_y:.1f}*sin(2*PI*t/{y_period})'",
        "vignette=PI/9",
        "fade=t=in:st=0:d=0.18",
        f"fade=t=out:st={fade_out_start:.3f}:d=0.24",
    ]
    filters.extend(modern_gradient_border_filters(accent, accent_secondary))
    if show_text_overlays:
        filters.extend(
            [
                f"drawbox=x=48:y=62:w={badge_width}:h=48:color={accent}@0.92:t=fill:"
                "enable='between(t,0.06,3.20)'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{badge}':expansion=none:fontcolor=white:fontsize=23:"
                "x=68:y=73:enable='between(t,0.06,3.20)'",
                "drawbox=x=48:y=120:w=984:h=250:color=black@0.62:t=fill:"
                "enable='between(t,0.10,3.20)'",
                f"drawbox=x=48:y=120:w=14:h=250:color={accent}@0.98:t=fill:"
                "enable='between(t,0.10,3.20)'",
                "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"textfile='{hook_text_filename}':reload=0:expansion=none:"
                "fontcolor=white:fontsize=48:line_spacing=10:borderw=2:bordercolor=black@0.85:"
                "x='if(lt(t,0.48),-text_w+(t-0.10)*(76+text_w)/0.38,76)':y=168:"
                "enable='between(t,0.10,3.20)'",
            ]
        )
    for timestamp in emphasis_times or []:
        pulse_end = min(safe_duration, timestamp + 0.42)
        label_end = min(safe_duration, timestamp + 1.15)
        filters.extend(
            [
                f"drawbox=x=18:y=18:w=1044:h=1884:color={accent}@0.58:t=5:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
                f"drawbox=x=30:y=30:w=1020:h=1860:color=white@0.18:t=2:"
                f"enable='between(t,{timestamp:.3f},{pulse_end:.3f})'",
            ]
        )
        if show_text_overlays:
            filters.extend(
                [
                    f"drawbox=x=706:y=400:w=326:h=58:color={accent}@0.94:t=fill:"
                    f"enable='between(t,{timestamp:.3f},{label_end:.3f})'",
                    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='{emphasis_label}':expansion=none:fontcolor=white:fontsize=23:"
                    f"x='1008-text_w':y=415:enable='between(t,{timestamp:.3f},{label_end:.3f})'",
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


THUMBNAIL_SYSTEM_PROMPT = (
    "You write prompts for an AI image generator that will ONLY add a text overlay onto a "
    "provided screenshot. The screenshot is the thumbnail background and must NOT be redrawn, "
    "restyled, or replaced. Make the hook intriguing but faithful to the transcript. For mystery, "
    "myth, supernatural, or horror topics, never present an unverified claim as religious fact. "
    "Never mention, thank, credit, or promote the source channel, another channel, TV station, "
    "media brand, uploader, or sponsor in either the hook or prompt. "
    "Reply ONLY with strict JSON, no markdown."
)


def grab_best_frame(video_path: Path, clip: ClipCandidate, thumb_path: Path) -> Path | None:
    # Best moment heuristic: sample the clip's middle, where the payoff usually lands.
    timestamp = clip.start + max(0.0, (clip.end - clip.start) * 0.5)
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
        console.print(f"[yellow]Thumbnail frame failed for clip {clip.index}:[/yellow] {exc}")
        return None
    return thumb_path if thumb_path.exists() else None


def generate_thumbnail_prompt(clip: ClipCandidate, config: AIConfig) -> dict | None:
    fallback_hook = first_sentence(clip.title, max_words=6).upper()
    if not config.enabled or not config.base_url or not config.model:
        return {
            "hook_text": fallback_hook,
            "prompt": (
                f'Add a bold short-form video thumbnail text overlay reading "{fallback_hook}" '
                "onto the provided screenshot. Keep the screenshot itself untouched as the background. "
                "Place large high-contrast bold text (white fill, thick dark outline) in the upper third, "
                "do not cover faces, do not redraw or restyle the background image."
            ),
        }

    user_prompt = (
        "Create a viral thumbnail text overlay plan for this clip. The user already has a screenshot "
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
    if "horor" in words or "hantu" in words or "angker" in words:
        tags.append("#HororIndonesia")
    if words.intersection(INSPIRING_WORDS):
        tags.append("#Inspirasi")
    if not tags:
        tags.extend(["#PelajaranHidup", "#FaktaMenarik"])
    return tags


def fallback_social_caption(
    clip: ClipCandidate,
    required_hashtags: list[str] | None = None,
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
    for raw in [*(required_hashtags or []), *clip_topic_hashtags(clip), "#Shorts"]:
        tag = _normalize_hashtag(str(raw))
        if tag and tag.casefold() not in seen:
            ordered.append(tag)
            seen.add(tag.casefold())
    return f"{emoji} {hook}\n\n{body}\n\n{' '.join(ordered[:8])}"[:2000]


def generate_social_caption(
    clip: ClipCandidate, config: AIConfig, required_hashtags: list[str] | None = None
) -> str:
    if not config.enabled or not config.base_url or not config.model:
        return fallback_social_caption(clip, required_hashtags)

    user_prompt = (
        "Write a social media post caption (Bahasa Indonesia) for this short clip. "
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
                {"role": "system", "content": SOCIAL_CAPTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        parsed = extract_json(content)
    except Exception as exc:
        if not disable_unavailable_ai(config, exc):
            console.print(f"[yellow]Social caption failed for clip {clip.index}:[/yellow] {exc}")
        return fallback_social_caption(clip, required_hashtags)

    if not isinstance(parsed, dict):
        return fallback_social_caption(clip, required_hashtags)
    caption = parsed.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        return fallback_social_caption(clip, required_hashtags)
    text = caption.strip()
    clean_lines = [
        line
        for line in text.splitlines()
        if not is_source_branding_segment(line)
    ]
    text = "\n".join(clean_lines).strip()
    if not text:
        return fallback_social_caption(clip, required_hashtags)

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
) -> Path:
    clips_dir.mkdir(parents=True, exist_ok=True)
    base_name = base_name_override or f"clip_{clip.index:02}_{slugify(clip.title)[:72] or 'auto'}"
    srt_path = clips_dir / f"{base_name}.srt"
    json_path = clips_dir / f"{base_name}.json"
    out_path = clips_dir / f"{base_name}.mp4"
    temp_video_path = clips_dir / f"{base_name}.video_tmp.mp4"
    temp_audio_path = clips_dir / f"{base_name}.audio_tmp.wav"
    hook_text_path = clips_dir / f"{base_name}.hook.txt"

    duration = clip.end - clip.start
    theme_profile = visual_theme_profile(clip)
    emphasis_times = emphasis_timestamps(clip, clip_segments)
    reaction_cues = detect_reaction_cues(clip, clip_segments)
    drawtext_supported = ffmpeg_has_filter("drawtext")
    subtitles_supported = ffmpeg_has_filter("subtitles")
    reaction_overlays_supported = (
        ffmpeg_has_filter("movie")
        and ffmpeg_has_filter("overlay")
        and all((REACTION_ASSET_DIR / f"{cue.kind}.svg").is_file() for cue in reaction_cues)
    )
    write_srt(srt_path, clip_segments, clip.start, duration)
    save_json(
        json_path,
        {
            **asdict(clip),
            "enhanced_edit": enhanced_edit,
            "remove_running_text": remove_running_text,
            "visual_theme": theme_profile["theme"],
            "emphasis_times": emphasis_times,
            "reaction_cues": [asdict(cue) for cue in reaction_cues],
            "drawtext_supported": drawtext_supported,
            "subtitles_supported": subtitles_supported,
            "reaction_overlays_supported": reaction_overlays_supported,
        },
    )

    if crop_mode == "streamer":
        vf = streamer_crop_filter(video_path, clip, cam_corner)
    else:
        vf = vertical_crop_filter(video_path, clip, crop_mode)
    if remove_running_text:
        vf = f"{vf},{remove_running_text_filter()}"
    vf = add_quality_sharpen(vf, video_quality)
    if enhanced_edit:
        if drawtext_supported:
            hook_text_path.write_text(hook_banner_text(clip) + "\n", encoding="utf-8")
        else:
            console.print(
                "[yellow]FFmpeg tidak memiliki drawtext; hook teks dilewati, "
                "motion/color/pulse tetap diterapkan.[/yellow]"
            )
        if reaction_cues and not reaction_overlays_supported:
            console.print(
                "[yellow]FFmpeg tidak mendukung movie/overlay SVG; reaction sticker dilewati "
                "agar export tetap berjalan.[/yellow]"
            )
        vf = (
            f"{vf},"
            f"{enhanced_edit_filter(
                duration,
                hook_text_path.name,
                show_progress=generate_assets,
                theme_profile=theme_profile,
                emphasis_times=emphasis_times,
                variation=max(0, clip.index - 1),
                show_text_overlays=drawtext_supported,
                reaction_cues=reaction_cues,
                show_reactions=reaction_overlays_supported,
            )}"
        )
    if burn_subtitles and clip_segments and subtitles_supported:
        style = build_subtitle_style(caption or CaptionStyle())
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
                str(temp_video_path.name),
            ],
            cwd=clips_dir,
        )
    finally:
        hook_text_path.unlink(missing_ok=True)
    audio_filter = (
        "highpass=f=70,lowpass=f=15000,"
        "acompressor=threshold=0.125:ratio=2.5:attack=20:release=250:makeup=1.35,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"
    )
    if enhanced_edit:
        audio_fade_out_start = max(0.0, duration - 0.14)
        audio_filter += (
            ",afade=t=in:st=0:d=0.10"
            f",afade=t=out:st={audio_fade_out_start:.3f}:d=0.14"
        )
    run(
        [
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
        ],
        cwd=clips_dir,
    )
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
                "-movflags",
                "+faststart",
                str(out_path.resolve()),
            ],
            cwd=parts_dir,
        )
    finally:
        shutil.rmtree(parts_dir, ignore_errors=True)

    total_duration = write_compilation_srt(srt_path, transcript, candidates)
    compilation = ClipCandidate(
        index=1,
        start=min(item.start for item in candidates),
        end=max(item.end for item in candidates),
        duration=total_duration,
        score=round(sum(item.score for item in candidates) / len(candidates)),
        title=f"Highlight Terpenting: {strongest.title}"[:80],
        reason=f"Kompilasi {len(candidates)} poin penting, dipilih untuk hook, value, dan payoff.",
        text=" ".join(item.text for item in candidates),
    )
    save_json(
        json_path,
        {
            **asdict(compilation),
            "mode": "highlight_5m",
            "enhanced_edit": enhanced_edit,
            "remove_running_text": remove_running_text,
            "parts": [asdict(item) for item in candidates],
        },
    )

    if grab_best_frame(video_path, strongest, thumb_path) is not None:
        thumb_prompt = generate_thumbnail_prompt(compilation, ai_config)
        if thumb_prompt:
            prompt_path.write_text(
                f"HOOK: {thumb_prompt['hook_text']}\n\n{thumb_prompt['prompt']}\n",
                encoding="utf-8",
            )
    social_caption = generate_social_caption(compilation, ai_config, required_hashtags)
    if social_caption:
        (clips_dir / f"{base_name}_caption.txt").write_text(social_caption + "\n", encoding="utf-8")
    return out_path


def print_candidates(candidates: list[ClipCandidate]) -> None:
    table = Table(title="Clip candidates")
    table.add_column("#", justify="right")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Score", justify="right")
    table.add_column("Title")
    table.add_column("Reason")

    for item in candidates:
        table.add_row(
            str(item.index),
            seconds_to_stamp(item.start),
            seconds_to_stamp(item.end),
            str(item.score),
            item.title,
            item.reason,
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
    parser = argparse.ArgumentParser(description="Local YouTube auto clipper for vertical videos.")
    parser.add_argument("url", nargs="?", default="", help="YouTube URL")
    parser.add_argument("--source-file", default="", help="Use a local video file instead of downloading from a URL")
    parser.add_argument("--top", type=int, default=5, help="Number of clips to export")
    parser.add_argument("--min", type=float, default=35, help="Minimum clip duration in seconds")
    parser.add_argument("--max", type=float, default=180, help="Maximum clip duration in seconds")
    parser.add_argument(
        "--clip-mode",
        choices=["short", "highlight_5m"],
        default="short",
        help="Export short clips plus one compilation, or only one five-minute compilation",
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
        else min(12, max(args.top, math.ceil(args.compilation_target / 60)))
    )
    pool = ai_rescore_candidates(
        pool,
        ai_config,
        target_count=ai_target_count,
        compilation=args.clip_mode == "highlight_5m",
    )
    compilation_candidates: list[ClipCandidate]
    if args.clip_mode == "highlight_5m":
        candidates = select_compilation_candidates(pool, args.compilation_target)
        compilation_candidates = candidates
    else:
        candidates, compilation_candidates = select_short_and_compilation_candidates(
            pool,
            args.top,
            args.compilation_target,
        )
    if not candidates:
        console.print("[red]No clip candidates found. Try lowering --min or increasing --max.[/red]")
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
        console.print("[bold]Exporting vertical highlight compilation...[/bold]")
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
        if compilation_candidates:
            console.print("[bold]Exporting vertical highlight compilation...[/bold]")
            exported.append(
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
