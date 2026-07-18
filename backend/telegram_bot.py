from __future__ import annotations

import json
import mimetypes
import os
import re
import signal
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = Path(os.environ.get("TELEGRAM_OUTPUTS_DIR", BASE_DIR / "outputs"))
STATE_PATH = Path(
    os.environ.get("TELEGRAM_STATE_PATH", BASE_DIR / "data" / "telegram_bot_state.json")
)
BACKEND_API_BASE = os.environ.get("BACKEND_API_BASE", "http://127.0.0.1:8010").rstrip("/")
PUBLIC_OUTPUT_BASE_URL = os.environ.get("TELEGRAM_PUBLIC_BASE_URL", "").rstrip("/")
YOUTUBE_STUDIO_URL = os.environ.get("YOUTUBE_STUDIO_URL", "https://studio.youtube.com")
DEFAULT_TELEGRAM_AI_BASE_URL = os.environ.get(
    "TELEGRAM_AI_BASE_URL",
    os.environ.get("DEFAULT_AI_BASE_URL", "http://127.0.0.1:11434/v1"),
).strip()
DEFAULT_TELEGRAM_AI_MODEL = os.environ.get("TELEGRAM_AI_MODEL", "llama3.2-id:latest").strip()
POLL_TIMEOUT_SECONDS = 3
YOUTUBE_UPLOAD_DISCOVERY_INTERVAL = 5.0
YOUTUBE_UPLOAD_RECENT_TERMINAL_SECONDS = 600.0
MAX_UPLOAD_BYTES = min(
    49 * 1024 * 1024,
    max(1, int(float(os.environ.get("TELEGRAM_MAX_UPLOAD_MB", "49")) * 1024 * 1024)),
)
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running"}
ALLOWED_QUALITY = {"standard", "high", "max"}
ALLOWED_CROP = {"center", "person", "streamer"}
ALLOWED_CLIP_MODES = {"short", "highlight_5m"}
TELEGRAM_COMPILATION_MAX_SECONDS = 300
ALLOWED_CAPTION_POSITIONS = {"upper", "center", "bottom"}
ALLOWED_CAPTION_FONT_SIZES = {7, 9, 10, 12, 14, 18, 20, 24}
ALLOWED_TOP = {None, 3, 5, 8, 10, 12}
ALLOWED_DURATION_PRESETS = {(15, 60), (30, 75), (35, 180), (60, 180)}
SETTINGS_SCHEMA_VERSION = 4


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def parse_battery_alert_levels(value: str) -> tuple[int, ...]:
    levels: set[int] = set()
    for item in value.split(","):
        try:
            level = int(item.strip())
        except ValueError:
            continue
        if 1 <= level <= 100:
            levels.add(level)
    return tuple(sorted(levels, reverse=True))


BATTERY_POWER_SUPPLY_PATH = Path(
    os.environ.get(
        "TELEGRAM_BATTERY_POWER_SUPPLY_PATH",
        (
            "/host/sys/class/power_supply"
            if Path("/host/sys/class/power_supply").is_dir()
            else "/sys/class/power_supply"
        ),
    )
)
BATTERY_ALERT_ENABLED = env_bool("TELEGRAM_BATTERY_ALERT_ENABLED", True)
BATTERY_ALERT_LEVELS = parse_battery_alert_levels(
    os.environ.get("TELEGRAM_BATTERY_ALERT_LEVELS", "20,10,5")
)
BATTERY_CHECK_INTERVAL = max(
    15.0,
    env_float("TELEGRAM_BATTERY_CHECK_INTERVAL_SECONDS", 60.0),
)


YOUTUBE_CDP_REFRESH_HTTP_TIMEOUT = max(
    45.0,
    env_float(
        "TELEGRAM_YOUTUBE_CDP_REFRESH_TIMEOUT_SECONDS",
        env_float("YOUTUBE_CDP_REFRESH_READY_TIMEOUT_SECONDS", 30.0) + 20.0,
    ),
)
YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT = max(
    90.0,
    env_float("TELEGRAM_YOUTUBE_SESSION_CAPTURE_TIMEOUT_SECONDS", YOUTUBE_CDP_REFRESH_HTTP_TIMEOUT + 60.0),
)
YOUTUBE_ONE_TIME_LOGIN_HTTP_TIMEOUT = max(
    YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
    env_float("TELEGRAM_YOUTUBE_ONE_TIME_LOGIN_TIMEOUT_SECONDS", 180.0),
)
VIRAL_CC_SEARCH_HTTP_TIMEOUT = max(600.0, env_float("VIRAL_CC_SEARCH_HTTP_TIMEOUT_SECONDS", 900.0))
VIRAL_CC_VIDEO_COUNT = max(1, min(7, int(env_float("VIRAL_CC_VIDEO_COUNT", 5))))
VIRAL_CC_MAX_SOURCE_SECONDS = max(
    60,
    min(14400, int(env_float("VIRAL_CC_MAX_SOURCE_SECONDS", 7200))),
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "clip_mode": "short",
    "top": None,
    "min_duration": 35,
    "max_duration": 180,
    "video_quality": "high",
    "crop_mode": "person",
    "burn_subtitles": True,
    "ai_enabled": True,
    "ai_base_url": DEFAULT_TELEGRAM_AI_BASE_URL,
    "ai_model": DEFAULT_TELEGRAM_AI_MODEL,
    "caption_position": "upper",
    "caption_font_size": 10,
}

CLIPPING_STAGE_ALERTS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("queued", "Menyiapkan antrean", "Job masuk antrean backend.", ()),
    ("metadata", "Membaca informasi video", "Backend sedang membaca metadata video sumber.", ("fetching metadata",)),
    (
        "creative_commons",
        "Lisensi Creative Commons terverifikasi",
        "Sumber terdeteksi Creative Commons/reuse allowed sebelum download dilanjutkan.",
        ("creative commons license detected",),
    ),
    ("download", "Mengunduh video sumber", "Video sumber mulai diunduh untuk diproses.", ("fetching video",)),
    ("audio", "Mengekstrak audio", "Audio sedang disiapkan untuk transkripsi.", ("extract", "audio")),
    ("transcribe", "Mentranskripsi percakapan", "Model transkripsi berjalan untuk membaca isi video.", ("loading model", "transcrib")),
    ("score", "Menyeleksi momen terbaik", "Transcript sedang dinilai untuk mencari kandidat clip terkuat.", ("scoring candidate",)),
    ("ai_score", "AI menilai kandidat", "AI agent sedang meranking kandidat clip.", ("agent scoring",)),
    (
        "effects",
        "Menambahkan edit dan reaction kontekstual",
        "Hook, gerakan kamera, reaction lucu/terkejut/hikmah, transisi, dan elemen penegas sedang diterapkan sesuai percakapan.",
        ("applying enhanced motion graphics",),
    ),
    (
        "export",
        "Mengekspor clip pendek",
        "Clip pendek dengan motion graphics sedang dirender ke format vertikal.",
        ("exporting vertical video", "exporting vertical clips", "exporting vertical short clips"),
    ),
    (
        "compilation",
        "Menyusun video kompilasi",
        "Momen terbaik sedang digabungkan menjadi satu video highlight agak panjang.",
        ("exporting vertical highlight compilation",),
    ),
    ("done", "Clipping selesai", "Render selesai. Bot akan menyiapkan pengiriman hasil.", ("done.", "exported:")),
    (
        "auto_youtube",
        "Auto upload YouTube",
        "3 clip terbaik masuk antrean upload YouTube dengan judul, deskripsi singkat, hashtag otomatis, dan playlist Islam.",
        ("auto upload youtube:",),
    ),
]

YOUTUBE_UPLOAD_STAGE_ALERTS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("queued", "Masuk antrean", "Clip menunggu giliran worker upload YouTube.", ()),
    ("running", "Worker upload dimulai", "Backend mulai menjalankan Playwright untuk upload clip.", ()),
    ("open_studio", "Membuka YouTube Studio", "Browser otomatis membuka halaman Studio channel target.", ("membuka youtube studio",)),
    (
        "identity",
        "Memastikan akun/channel",
        "Session dicek agar upload hanya berjalan di akun/channel target.",
        ("identitas youtube target terdeteksi", "email google target terdeteksi"),
    ),
    (
        "dialog",
        "Membuka modal upload",
        "Bot klik tombol Buat/Create lalu memilih menu Upload video.",
        ("membuka dialog upload", "tombol buat/create diklik", "menu upload video diklik"),
    ),
    (
        "file",
        "Memilih file video",
        "File clip dipasang ke input upload YouTube Studio.",
        ("dialog upload siap", "video dipilih:"),
    ),
    ("metadata", "Mengisi metadata", "Judul dan deskripsi otomatis sedang diisi.", ("judul diisi", "deskripsi diisi")),
    (
        "settings",
        "Mengatur audience, playlist, tags",
        "Audience, playlist Islam, dan hashtag/tag otomatis sedang dipasang.",
        ("setelan audiens dipilih", "memilih playlist", "playlist dipilih", "tags diisi"),
    ),
    (
        "checks",
        "Menunggu copyright checks",
        "YouTube Studio sedang memeriksa copyright/restriction sebelum publish.",
        ("menunggu youtube studio checks",),
    ),
    (
        "checks_done",
        "Checks aman",
        "YouTube Studio tidak mendeteksi masalah pada tahap checks.",
        ("checks selesai", "tidak ada masalah terdeteksi"),
    ),
    ("visibility", "Mengatur visibilitas", "Visibility video sedang dipilih sesuai konfigurasi.", ("mengatur visibilitas",)),
    ("finalizing", "Final publish/save", "Tombol final sudah ditekan dan menunggu konfirmasi YouTube.", ("menunggu konfirmasi upload",)),
    ("video_url", "URL video terdeteksi", "YouTube sudah mengembalikan URL video.", ("video_url:",)),
    ("close_tab", "Menutup tab upload", "Tab upload YouTube ditutup setelah proses selesai/gagal.", ("tab upload youtube ditutup",)),
]


class ServiceError(RuntimeError):
    pass


def format_duration(seconds: float | int | None) -> str:
    value = max(0, int(round(float(seconds or 0))))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}j {minutes}m {secs}d"
    if minutes:
        return f"{minutes}m {secs}d"
    return f"{secs}d"


def format_size(size_bytes: int | float | None) -> str:
    value = max(0.0, float(size_bytes or 0))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def read_battery_status(power_supply_path: Path = BATTERY_POWER_SUPPLY_PATH) -> dict[str, Any] | None:
    try:
        supplies = sorted(power_supply_path.iterdir(), key=lambda item: item.name)
    except OSError:
        return None

    batteries: list[dict[str, Any]] = []
    for supply in supplies:
        try:
            if (supply / "type").read_text(encoding="utf-8").strip().lower() != "battery":
                continue
            present_path = supply / "present"
            if present_path.is_file() and present_path.read_text(encoding="utf-8").strip() == "0":
                continue
            percent = int((supply / "capacity").read_text(encoding="utf-8").strip())
            status = (supply / "status").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            continue
        batteries.append(
            {
                "device": supply.name,
                "percent": max(0, min(100, percent)),
                "status": status or "Unknown",
            }
        )

    if not batteries:
        return None
    percent = round(sum(item["percent"] for item in batteries) / len(batteries))
    statuses = {str(item["status"]).lower() for item in batteries}
    if "discharging" in statuses:
        status = "Discharging"
    elif "charging" in statuses:
        status = "Charging"
    elif statuses == {"full"}:
        status = "Full"
    else:
        status = str(batteries[0]["status"])
    return {
        "percent": percent,
        "status": status,
        "device": ", ".join(str(item["device"]) for item in batteries),
        "batteries": batteries,
    }


def battery_status_text(battery: dict[str, Any]) -> str:
    percent = max(0, min(100, int(battery.get("percent") or 0)))
    status = str(battery.get("status") or "Unknown")
    status_label = {
        "charging": "Sedang diisi",
        "discharging": "Menggunakan baterai",
        "full": "Penuh",
        "not charging": "Terhubung, tidak mengisi",
        "unknown": "Tidak diketahui",
    }.get(status.lower(), status)
    filled = round(percent / 10)
    gauge = "█" * filled + "░" * (10 - filled)
    return (
        "Status baterai device\n\n"
        f"🔋 Sisa: {percent}%\n"
        f"[{gauge}]\n"
        f"⚡ Status: {status_label}\n"
        f"Device: {battery.get('device') or '-'}"
    )


def is_supported_video_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().removeprefix("www.")
    return host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def canonical_youtube_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
    if not video_id:
        return ""
    return f"https://www.youtube.com/watch?v={video_id}"


def normalize_settings(value: object) -> dict[str, Any]:
    settings = DEFAULT_SETTINGS.copy()
    if not isinstance(value, dict):
        return settings

    top = value.get("top")
    settings["top"] = top if top in ALLOWED_TOP else None

    # Telegram CTA always creates short clips plus one compilation. This also
    # migrates persisted state from the removed "highlight only" option.
    settings["clip_mode"] = "short"

    duration = (value.get("min_duration"), value.get("max_duration"))
    if duration in ALLOWED_DURATION_PRESETS:
        settings["min_duration"], settings["max_duration"] = duration

    quality = value.get("video_quality")
    if quality in ALLOWED_QUALITY:
        settings["video_quality"] = quality

    crop = value.get("crop_mode")
    if crop in ALLOWED_CROP:
        settings["crop_mode"] = crop

    if isinstance(value.get("burn_subtitles"), bool):
        settings["burn_subtitles"] = value["burn_subtitles"]
    if isinstance(value.get("ai_enabled"), bool):
        settings["ai_enabled"] = value["ai_enabled"]
    if isinstance(value.get("ai_base_url"), str) and value["ai_base_url"].strip():
        settings["ai_base_url"] = value["ai_base_url"].strip()
    if isinstance(value.get("ai_model"), str) and value["ai_model"].strip():
        settings["ai_model"] = value["ai_model"].strip()

    position = value.get("caption_position")
    if position in ALLOWED_CAPTION_POSITIONS:
        settings["caption_position"] = position

    font_size = value.get("caption_font_size")
    if font_size in ALLOWED_CAPTION_FONT_SIZES:
        settings["caption_font_size"] = font_size
    return settings


def default_state() -> dict[str, Any]:
    return {
        "update_offset": 0,
        "waiting_for_url": False,
        "pending_url": "",
        "active_job_id": None,
        "settings_schema_version": SETTINGS_SCHEMA_VERSION,
        "settings": DEFAULT_SETTINGS.copy(),
        "jobs": {},
        "youtube_uploads": {},
        "viral_video_suggestions": {},
        "viral_video_seen_urls": [],
        "battery_alerted_levels": [],
    }


def normalize_state(value: object) -> dict[str, Any]:
    state = default_state()
    if not isinstance(value, dict):
        return state
    if isinstance(value.get("update_offset"), int):
        state["update_offset"] = max(0, value["update_offset"])
    state["waiting_for_url"] = bool(value.get("waiting_for_url", False))
    if isinstance(value.get("pending_url"), str):
        state["pending_url"] = value["pending_url"]
    if isinstance(value.get("active_job_id"), str):
        state["active_job_id"] = value["active_job_id"]
    state["settings"] = normalize_settings(value.get("settings"))
    if int(value.get("settings_schema_version") or 1) < SETTINGS_SCHEMA_VERSION:
        raw_settings = value.get("settings") if isinstance(value.get("settings"), dict) else {}
        if raw_settings.get("caption_font_size") in {9, 12, 14, 18}:
            state["settings"]["caption_font_size"] = DEFAULT_SETTINGS["caption_font_size"]
        if raw_settings.get("ai_model") == "deepseek-v4-flash:cloud":
            # This cloud preset requires a paid Ollama subscription. Existing
            # installations are migrated to the available Indonesian local
            # model so clipping and upload metadata keep using AI.
            state["settings"]["ai_model"] = DEFAULT_TELEGRAM_AI_MODEL
    state["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    if isinstance(value.get("jobs"), dict):
        state["jobs"] = value["jobs"]
    if isinstance(value.get("youtube_uploads"), dict):
        state["youtube_uploads"] = value["youtube_uploads"]
    if isinstance(value.get("viral_video_suggestions"), dict):
        state["viral_video_suggestions"] = value["viral_video_suggestions"]
    if isinstance(value.get("viral_video_seen_urls"), list):
        seen_urls: list[str] = []
        seen_set: set[str] = set()
        for item in value["viral_video_seen_urls"]:
            normalized = canonical_youtube_url(item)
            if normalized and normalized not in seen_set:
                seen_urls.append(normalized)
                seen_set.add(normalized)
        state["viral_video_seen_urls"] = seen_urls[-5000:]
    if isinstance(value.get("battery_alerted_levels"), list):
        state["battery_alerted_levels"] = [
            level
            for level in BATTERY_ALERT_LEVELS
            if level in value["battery_alerted_levels"]
        ]
    return state


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        return normalize_state(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return default_state()


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(state, ensure_ascii=False, indent=2)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(data, encoding="utf-8")
    temp_path.replace(path)


def build_job_payload(url: str, settings: dict[str, Any]) -> dict[str, Any]:
    clean = normalize_settings(settings)
    return {
        "url": url.strip(),
        "top": clean["top"],
        "clip_mode": "short",
        "compilation_target_seconds": TELEGRAM_COMPILATION_MAX_SECONDS,
        "min_duration": clean["min_duration"],
        "max_duration": clean["max_duration"],
        "video_quality": clean["video_quality"],
        "burn_subtitles": clean["burn_subtitles"],
        "remove_running_text": True,
        "crop_mode": clean["crop_mode"],
        "require_creative_commons": True,
        "ai_enabled": clean["ai_enabled"],
        "ai_base_url": clean["ai_base_url"],
        "ai_model": clean["ai_model"],
        "caption_position": clean["caption_position"],
        "caption_font_size": clean["caption_font_size"],
    }


def output_path_from_url(url: str, outputs_dir: Path = OUTPUTS_DIR) -> Path | None:
    if not url.startswith("/outputs/"):
        return None
    relative = unquote(url.removeprefix("/outputs/").split("?", 1)[0])
    candidate = (outputs_dir / relative).resolve()
    root = outputs_dir.resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def split_text(text: str, limit: int = 3900) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    chunks: list[str] = []
    while len(clean) > limit:
        split_at = clean.rfind("\n", 0, limit + 1)
        if split_at < limit // 2:
            split_at = clean.rfind(" ", 0, limit + 1)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(clean[:split_at].rstrip())
        clean = clean[split_at:].lstrip()
    if clean:
        chunks.append(clean)
    return chunks


def elapsed_for_job(job: dict[str, Any]) -> float:
    stored = job.get("duration_seconds")
    if isinstance(stored, (int, float)):
        return max(0.0, float(stored))
    started_at = job.get("started_at")
    if not isinstance(started_at, str) or not started_at:
        return 0.0
    try:
        started = datetime.fromisoformat(started_at)
        now = datetime.now(started.tzinfo) if started.tzinfo else datetime.now()
        return max(0.0, (now - started).total_seconds())
    except ValueError:
        return 0.0


def seconds_since_iso(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        timestamp = datetime.fromisoformat(value)
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        return (now - timestamp).total_seconds()
    except ValueError:
        return None


def progress_stage(job: dict[str, Any]) -> str:
    logs = "\n".join(str(line) for line in job.get("logs", [])[-30:]).lower()
    if "exporting vertical clips" in logs or "person crop" in logs or "streamer stack" in logs:
        return "Mengekspor video vertikal"
    if "scoring candidate" in logs or "agent scoring" in logs:
        return "Menyeleksi momen terbaik"
    if "transcribed" in logs:
        return "Menyusun kandidat clip"
    if "loading model" in logs or "transcrib" in logs:
        return "Mentranskripsi percakapan"
    if "fetching video" in logs:
        return "Mengunduh video sumber"
    if "fetching metadata" in logs:
        return "Membaca informasi video"
    return "Menyiapkan proses clipping"


def clipping_stage_alerts(job: dict[str, Any], sent_stage_ids: set[str]) -> list[tuple[str, str, str]]:
    status = str(job.get("status") or "")
    logs = "\n".join(str(line) for line in job.get("logs", [])[-120:]).lower()
    alerts: list[tuple[str, str, str]] = []
    for stage_id, label, detail, patterns in CLIPPING_STAGE_ALERTS:
        if stage_id in sent_stage_ids:
            continue
        if stage_id == "queued":
            matched = status in ACTIVE_STATUSES
        else:
            matched = any(pattern in logs for pattern in patterns)
        if matched:
            alerts.append((stage_id, label, detail))
    return alerts


def youtube_upload_stage_alerts(upload: dict[str, Any], sent_stage_ids: set[str]) -> list[tuple[str, str, str]]:
    status = str(upload.get("status") or "")
    logs = "\n".join(str(line) for line in upload.get("logs", [])[-160:]).lower()
    alerts: list[tuple[str, str, str]] = []
    for stage_id, label, detail, patterns in YOUTUBE_UPLOAD_STAGE_ALERTS:
        if stage_id in sent_stage_ids:
            continue
        if stage_id == "queued":
            matched = status == "queued"
        elif stage_id == "running":
            matched = status == "running"
        else:
            matched = any(pattern in logs for pattern in patterns)
        if matched:
            alerts.append((stage_id, label, detail))
    return alerts


def youtube_upload_stage_label(upload: dict[str, Any]) -> str:
    status = str(upload.get("status") or "")
    if status == "completed":
        return "Selesai"
    if status == "failed":
        return "Gagal"
    if status == "cancelled":
        return "Dibatalkan"

    logs = "\n".join(str(line) for line in upload.get("logs", [])[-160:]).lower()
    latest = "Menunggu antrean" if status == "queued" else "Worker upload dimulai" if status == "running" else "-"
    for stage_id, label, _detail, patterns in YOUTUBE_UPLOAD_STAGE_ALERTS:
        if stage_id == "queued" and status == "queued":
            latest = label
        elif stage_id == "running" and status == "running":
            latest = label
        elif patterns and any(pattern in logs for pattern in patterns):
            latest = label
    return latest


def clip_title(clip: dict[str, Any], index: int) -> str:
    title = clip.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    name = str(clip.get("name") or f"clip_{index:02d}")
    stem = Path(name).stem
    stem = stem.split("_", 2)[-1] if stem.startswith("clip_") else stem
    return stem.replace("-", " ").replace("_", " ").strip().title() or f"Clip {index}"


def is_compilation_result(clip: dict[str, Any]) -> bool:
    name = str(clip.get("name") or "").lower()
    return name.startswith("highlight_5menit_")


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.reason
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            detail = error_payload.get("detail") or error_payload.get("description") or detail
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        raise ServiceError(str(detail)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ServiceError(str(exc)) from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ServiceError("Respons service bukan JSON yang valid") from exc


def _multipart_body(
    fields: dict[str, Any], file_field: str, file_path: Path
) -> tuple[bytes, str]:
    boundary = f"----ClipForge{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    safe_name = file_path.name.replace('"', "")
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{safe_name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


class BackendClient:
    def __init__(self, base_url: str = BACKEND_API_BASE):
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return _json_request(f"{self.base_url}/api/health", timeout=5)

    def list_jobs(self) -> list[dict[str, Any]]:
        result = _json_request(f"{self.base_url}/api/jobs", timeout=15)
        return result if isinstance(result, list) else []

    def get_job(self, job_id: str) -> dict[str, Any]:
        result = _json_request(f"{self.base_url}/api/jobs/{job_id}", timeout=15)
        if not isinstance(result, dict):
            raise ServiceError("Data job tidak valid")
        return result

    def create_job(self, url: str, settings: dict[str, Any]) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs",
            method="POST",
            payload=build_job_payload(url, settings),
            timeout=90,
        )
        if not isinstance(result, dict):
            raise ServiceError("Backend tidak mengembalikan job")
        return result

    def search_viral_cc_sources(self, exclude_urls: list[str] | None = None) -> list[dict[str, Any]]:
        result = _json_request(
            f"{self.base_url}/api/automation/viral-cc/sources",
            method="POST",
            payload={
                "video_count": VIRAL_CC_VIDEO_COUNT,
                "search_limit_per_query": max(25, int(env_float("VIRAL_CC_SEARCH_LIMIT", 25))),
                "min_source_duration": 60,
                "max_source_duration": VIRAL_CC_MAX_SOURCE_SECONDS,
                "min_views": int(env_float("VIRAL_CC_MIN_VIEWS", 1000)),
                "max_age_days": 30,
                "max_metadata_checks": max(
                    200,
                    int(env_float("VIRAL_CC_MAX_METADATA_CHECKS", 200)),
                ),
                "exclude_urls": exclude_urls or [],
            },
            timeout=VIRAL_CC_SEARCH_HTTP_TIMEOUT,
        )
        return result if isinstance(result, list) else []

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs/{job_id}/cancel",
            method="POST",
            payload={},
            timeout=20,
        )
        return result if isinstance(result, dict) else {}

    def delete_job(self, job_id: str) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs/{job_id}",
            method="DELETE",
            timeout=30,
        )
        return result if isinstance(result, dict) else {}

    def delete_failed_jobs(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs/failed",
            method="DELETE",
            timeout=30,
        )
        return result if isinstance(result, dict) else {}

    def youtube_config(self) -> dict[str, Any]:
        result = _json_request(f"{self.base_url}/api/youtube/config", timeout=15)
        return result if isinstance(result, dict) else {}

    def enable_youtube_direct_profile_upload(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/upload-mode/direct-profile",
            method="POST",
            payload={},
            timeout=15,
        )
        return result if isinstance(result, dict) else {}

    def setup_youtube_one_time_login(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/login/once",
            method="POST",
            payload={},
            timeout=YOUTUBE_ONE_TIME_LOGIN_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def get_youtube_upload(self, upload_id: str) -> dict[str, Any]:
        result = _json_request(f"{self.base_url}/api/youtube/uploads/{upload_id}", timeout=15)
        if not isinstance(result, dict):
            raise ServiceError("Data upload YouTube tidak valid")
        return result

    def list_youtube_uploads(self) -> list[dict[str, Any]]:
        result = _json_request(f"{self.base_url}/api/youtube/uploads", timeout=15)
        return result if isinstance(result, list) else []

    def create_youtube_upload(self, job_id: str, clip_url: str) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs/{job_id}/youtube-uploads",
            method="POST",
            payload={"clip_url": clip_url},
            timeout=30,
        )
        if not isinstance(result, dict):
            raise ServiceError("Backend tidak mengembalikan upload YouTube")
        return result

    def create_youtube_upload_batch(self, job_id: str, clip_urls: list[str] | None = None) -> list[dict[str, Any]]:
        result = _json_request(
            f"{self.base_url}/api/jobs/{job_id}/youtube-uploads/batch",
            method="POST",
            payload={"clip_urls": clip_urls or []},
            timeout=45,
        )
        return result if isinstance(result, list) else []

    def capture_youtube_session(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/session/capture",
            method="POST",
            payload={},
            timeout=YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def refresh_youtube_cdp(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/refresh",
            method="POST",
            payload={},
            timeout=YOUTUBE_CDP_REFRESH_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def repair_youtube_cdp(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/repair",
            method="POST",
            payload={},
            timeout=YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def auto_login_youtube_cdp(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/auto-login",
            method="POST",
            payload={},
            timeout=YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def import_youtube_cdp_cookies(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/import-cookies",
            method="POST",
            payload={},
            timeout=YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def sync_youtube_cdp_from_profile(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/profile-sync",
            method="POST",
            payload={},
            timeout=YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def sync_youtube_cdp(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/sync",
            method="POST",
            payload={},
            timeout=YOUTUBE_SESSION_CAPTURE_HTTP_TIMEOUT,
        )
        return result if isinstance(result, dict) else {}

    def stop_youtube_cdp(self) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/youtube/cdp/stop",
            method="POST",
            payload={},
            timeout=20,
        )
        return result if isinstance(result, dict) else {}


class TelegramApi:
    def __init__(self, token: str):
        self.base_url = f"https://api.telegram.org/bot{token}"

    def call(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
        file_field: str | None = None,
        file_path: Path | None = None,
    ) -> Any:
        url = f"{self.base_url}/{method}"
        if file_field and file_path:
            body, boundary = _multipart_body(payload or {}, file_field, file_path)
            request = Request(
                url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                try:
                    detail = json.loads(exc.read().decode("utf-8")).get("description", exc.reason)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    detail = exc.reason
                raise ServiceError(str(detail)) from exc
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                raise ServiceError(str(exc)) from exc
        else:
            result = _json_request(url, method="POST", payload=payload or {}, timeout=timeout)

        if not isinstance(result, dict) or not result.get("ok"):
            detail = result.get("description", "Telegram API gagal") if isinstance(result, dict) else "Telegram API gagal"
            raise ServiceError(str(detail))
        return result.get("result")


def button(text: str, callback_data: str) -> dict[str, str]:
    return {"text": text, "callback_data": callback_data}


def url_button(text: str, url: str) -> dict[str, str]:
    return {"text": text, "url": url}


def keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def main_menu_keyboard() -> dict[str, Any]:
    return keyboard(
        [
            [button("🎬 Buat Clip + Kompilasi", "menu:new")],
            [button("🔥 Cari Viral CC", "viral:refresh")],
            [button("📊 Status", "menu:status"), button("📚 Riwayat", "menu:history")],
            [button("🔋 Baterai Device", "menu:battery")],
            [button("⬆️ Status Upload YouTube", "menu:youtube"), button("🧪 Debug", "menu:debug")],
            [button("⚙️ Pengaturan", "menu:settings"), button("❓ Bantuan", "menu:help")],
        ]
    )


def settings_summary(settings: dict[str, Any]) -> str:
    clean = normalize_settings(settings)
    top = "Otomatis" if clean["top"] is None else str(clean["top"])
    quality = {"standard": "Standar", "high": "Jernih", "max": "Maksimal"}[clean["video_quality"]]
    crop = {"center": "Center", "person": "Follow Person", "streamer": "Streamer"}[clean["crop_mode"]]
    position = {"upper": "Atas", "center": "Tengah", "bottom": "Bawah"}[clean["caption_position"]]
    return (
        "Output: Clip pendek + 1 kompilasi otomatis\n"
        "Kompilasi panjang: maksimal 5 menit\n"
        f"Target clip: {top}\n"
        f"Durasi: {clean['min_duration']}–{clean['max_duration']} detik\n"
        f"Kualitas: {quality}\n"
        f"Mode crop: {crop}\n"
        f"Subtitle: {'Aktif' if clean['burn_subtitles'] else 'Nonaktif'}\n"
        f"AI: {'Aktif' if clean['ai_enabled'] else 'Nonaktif'}"
        f" · {clean['ai_model']} @ {clean['ai_base_url']}\n"
        f"Caption: {position}, {clean['caption_font_size']}px"
    )


def settings_keyboard(settings: dict[str, Any], *, has_pending_url: bool = False) -> dict[str, Any]:
    clean = normalize_settings(settings)
    top = "auto" if clean["top"] is None else clean["top"]
    rows = [
            [button("Output · Clip + Kompilasi ≤5m", "settings:output")],
            [button(f"Jumlah Clip · {top}", "settings:top")],
            [button(f"Durasi · {clean['min_duration']}–{clean['max_duration']}d", "settings:duration")],
            [button(f"Kualitas · {clean['video_quality']}", "settings:quality")],
            [button(f"Crop · {clean['crop_mode']}", "settings:crop")],
            [
                button(f"Subtitle · {'ON' if clean['burn_subtitles'] else 'OFF'}", "set:subtitles:toggle"),
                button(f"AI · {'ON' if clean['ai_enabled'] else 'OFF'}", "set:ai:toggle"),
            ],
            [button("Tampilan Caption", "settings:caption")],
        ]
    if has_pending_url:
        rows.append([button("✅ Kembali ke Konfirmasi", "pending:review")])
    rows.append([button("⬅️ Menu Utama", "menu:home")])
    return keyboard(rows)


def confirmation_keyboard() -> dict[str, Any]:
    return keyboard(
        [
            [button("🚀 Buat Clip + Kompilasi", "job:confirm")],
            [button("⚙️ Ubah Pengaturan", "menu:settings"), button("❌ Batal", "pending:cancel")],
        ]
    )


def viral_source_text(source: dict[str, Any], index: int) -> str:
    title = str(source.get("title") or "Video tanpa judul")[:140]
    uploader = str(source.get("uploader") or "-")[:80]
    duration = format_duration(source.get("duration"))
    views = source.get("views")
    views_text = f"{int(views):,}".replace(",", ".") if isinstance(views, (int, float)) else "-"
    views_per_day = source.get("views_per_day")
    velocity_text = (
        f"{int(views_per_day):,}".replace(",", ".")
        if isinstance(views_per_day, (int, float))
        else "-"
    )
    score = source.get("score")
    age_days = source.get("age_days")
    age_text = (
        f"{max(0, int(age_days))} hari lalu"
        if isinstance(age_days, (int, float)) and not isinstance(age_days, bool)
        else "umur tidak diketahui"
    )
    upload_date = re.sub(r"[^0-9]", "", str(source.get("upload_date") or ""))
    published = (
        f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[0:4]}"
        if len(upload_date) == 8
        else "-"
    )
    license_text = str(source.get("license") or "Creative Commons")[:80]
    return (
        f"{index}. {title}\n"
        f"Channel: {uploader}\n"
        f"Terbit: {published} · {age_text}\n"
        f"Durasi: {duration} · Views: {views_text} · {velocity_text}/hari · Score: {score or '-'}\n"
        f"Lisensi: {license_text}"
    )


def viral_sources_keyboard(sources: list[dict[str, Any]], suggestions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for index, source in enumerate(sources, start=1):
        suggestion_id = uuid.uuid4().hex[:10]
        suggestions[suggestion_id] = source
        rows.append([button(f"✅ Proses #{index}", f"viralpick:{suggestion_id}")])
    rows.append([button("🔄 Cari Lagi", "viral:refresh"), button("🏠 Menu", "menu:home")])
    return keyboard(rows)


class ClipForgeTelegramBot:
    def __init__(self, token: str, owner_id: int):
        self.telegram = TelegramApi(token)
        self.backend = BackendClient()
        self.owner_id = owner_id
        self.state = load_state()
        self.running = True
        self.last_backend_warning = 0.0
        self.last_persist_warning = 0.0
        self.last_youtube_upload_discovery = 0.0
        self.last_battery_check = 0.0
        self.last_battery_status: dict[str, Any] | None = None

    def persist(self) -> None:
        try:
            save_state(self.state)
        except OSError as exc:
            now = time.monotonic()
            if now - self.last_persist_warning > 30:
                print(f"Gagal menyimpan state Telegram, lanjut dengan state memory: {exc}", flush=True)
                self.last_persist_warning = now

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            result = self.telegram.call("sendMessage", payload)
        except ServiceError as exc:
            if not reply_markup:
                raise
            print(f"Gagal kirim pesan dengan keyboard, ulang tanpa keyboard: {exc}", flush=True)
            result = self.telegram.call("sendMessage", {"chat_id": chat_id, "text": text})
        return result if isinstance(result, dict) else {}

    def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            self.telegram.call("editMessageText", payload)
        except ServiceError as exc:
            if "message is not modified" not in str(exc).lower():
                self.send_message(chat_id, text, reply_markup)

    def answer_callback(self, callback_id: str, text: str = "", alert: bool = False) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_id, "show_alert": alert}
        if text:
            payload["text"] = text[:200]
        try:
            self.telegram.call("answerCallbackQuery", payload, timeout=10)
        except ServiceError:
            pass

    def send_long_message(self, chat_id: int, text: str) -> None:
        for chunk in split_text(text):
            self.send_message(chat_id, chunk)

    def viral_exclude_urls(self) -> list[str]:
        urls: list[str] = []
        for item in self.state.get("viral_video_seen_urls", []):
            urls.append(str(item))
        suggestions = self.state.get("viral_video_suggestions")
        if isinstance(suggestions, dict):
            for source in suggestions.values():
                if isinstance(source, dict):
                    urls.append(str(source.get("url") or ""))
        pending_url = canonical_youtube_url(self.state.get("pending_url"))
        if pending_url:
            urls.append(pending_url)
        jobs_state = self.state.get("jobs")
        if isinstance(jobs_state, dict):
            for record in jobs_state.values():
                if not isinstance(record, dict):
                    continue
                job = record.get("job") if isinstance(record.get("job"), dict) else record
                request = job.get("request") if isinstance(job, dict) else None
                if isinstance(request, dict):
                    urls.append(str(request.get("url") or ""))
                if isinstance(job, dict):
                    urls.append(str(job.get("source_url") or ""))
        normalized: list[str] = []
        seen: set[str] = set()
        for url in urls:
            candidate = canonical_youtube_url(url)
            if candidate and candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)
        return normalized[-5000:]

    def remember_viral_sources(self, sources: list[dict[str, Any]]) -> None:
        combined = [
            *(
                self.state.get("viral_video_seen_urls", [])
                if isinstance(self.state.get("viral_video_seen_urls"), list)
                else []
            ),
            *(source.get("url") for source in sources if isinstance(source, dict)),
        ]
        normalized: list[str] = []
        seen: set[str] = set()
        for value in combined:
            url = canonical_youtube_url(value)
            if url and url not in seen:
                normalized.append(url)
                seen.add(url)
        self.state["viral_video_seen_urls"] = normalized[-5000:]

    def show_home(self, chat_id: int, first_name: str = "") -> None:
        greeting = f"Halo {first_name}, " if first_name else "Halo, "
        self.send_message(
            chat_id,
            greeting
            + "Fendy Clipper siap digunakan.\n\n"
            "Kirim link YouTube langsung ke chat ini, atau gunakan tombol di bawah.",
            main_menu_keyboard(),
        )

    def show_settings(self, chat_id: int, message_id: int | None = None) -> None:
        text = "Pengaturan clipping saat ini\n\n" + settings_summary(self.state["settings"])
        markup = settings_keyboard(
            self.state["settings"],
            has_pending_url=is_supported_video_url(str(self.state.get("pending_url", ""))),
        )
        if message_id:
            self.edit_message(chat_id, message_id, text, markup)
        else:
            self.send_message(chat_id, text, markup)

    def show_pending(self, chat_id: int) -> None:
        url = self.state.get("pending_url", "")
        self.send_message(
            chat_id,
            "Link siap diproses\n\n"
            f"{url}\n\n"
            + settings_summary(self.state["settings"])
            + "\n\nSekali proses menghasilkan clip pendek dan satu kompilasi maksimal 5 menit.",
            confirmation_keyboard(),
        )

    def show_help(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Cara menggunakan Fendy Clipper\n\n"
            "1. Kirim link YouTube ke bot.\n"
            "2. Periksa pengaturan yang ditampilkan.\n"
            "3. Tekan Buat Clip + Kompilasi.\n"
            "4. Bot otomatis membuat clip pendek dan satu kompilasi maksimal lima menit.\n"
            "5. Bot akan mengirim seluruh hasil saat selesai.\n"
            "6. Tekan Upload ke YouTube pada video pilihan atau Upload 3 Terbaik.\n\n"
            "YouTube: /youtube untuk panel uploader, /loginsekali untuk simpan session Playwright sekali, "
            "/nocdp untuk upload tanpa CDP, /cookies untuk ambil cookies CDP opsional, /cdp untuk recovery CDP.\n\n"
            "Baterai: /battery untuk melihat sisa daya device. Alert otomatis dikirim saat baterai melewati ambang rendah.\n\n"
            "Perintah: /clip, /getvideosviral, /status, /battery, /settings, /history, /youtube, /cdp, "
            "/loginsekali, /cookies, /nocdp, /profilelogin, /syncsession, /capturesession, /hapusgagal, /debug, /ping, /cancel, /menu",
            main_menu_keyboard(),
        )

    def show_battery(self, chat_id: int) -> None:
        battery = read_battery_status()
        self.last_battery_status = battery
        if battery is None:
            self.send_message(
                chat_id,
                "Baterai tidak terdeteksi. Jika bot berjalan di Docker, pastikan `/sys` host dipasang read-only ke `/host/sys`.",
                main_menu_keyboard(),
            )
            return
        self.send_message(chat_id, battery_status_text(battery), main_menu_keyboard())

    def show_viral_video_suggestions(self, chat_id: int) -> None:
        exclude_urls = self.viral_exclude_urls()
        max_minutes = VIRAL_CC_MAX_SOURCE_SECONDS // 60
        self.send_message(
            chat_id,
            f"Mencari {VIRAL_CC_VIDEO_COUNT} video viral Creative Commons dengan keyword "
            f"podcast, kajian, inspirasi, misteri Islam, mitos/fakta, kisah gaib, horor, "
            f"sejarah, keluarga, bisnis halal, dan 70+ variasi tema. "
            f"Prioritas 30 hari terbaru; jika kurang, pencarian otomatis diperluas sampai 180 hari. "
            f"Durasi maksimal {max_minutes} menit..."
            + (f"\nSkip permanen sumber yang pernah ditampilkan/diproses: {len(exclude_urls)}" if exclude_urls else ""),
        )
        try:
            sources = self.backend.search_viral_cc_sources(exclude_urls)
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal mencari video viral Creative Commons: {exc}", main_menu_keyboard())
            return
        if not sources:
            self.send_message(
                chat_id,
                f"Belum menemukan kandidat baru setelah pencarian diperluas dan seluruh video lama dilewati. "
                f"Filter Creative Commons serta durasi maksimal {max_minutes} menit tetap dipertahankan.",
                main_menu_keyboard(),
            )
            return

        suggestions: dict[str, dict[str, Any]] = {}
        selected_sources = sources[:VIRAL_CC_VIDEO_COUNT]
        lines = [
            f"Top {len(selected_sources)} video viral Creative Commons",
            "Pencarian luas: 35+ variasi tema Indonesia",
            f"Filter: Creative Commons, prioritas ≤30 hari/fallback ≤180 hari, durasi maksimal {max_minutes} menit",
            "",
        ]
        for index, source in enumerate(selected_sources, start=1):
            lines.append(viral_source_text(source, index))
            url = source.get("url")
            if isinstance(url, str) and url:
                lines.append(url)
            lines.append("")
        markup = viral_sources_keyboard(selected_sources, suggestions)
        self.remember_viral_sources(selected_sources)
        self.state["viral_video_suggestions"] = suggestions
        self.persist()
        self.send_message(chat_id, "\n".join(lines).strip(), markup)

    def show_debug(self, chat_id: int) -> None:
        lines = [
            "Debug Telegram bot",
            f"Backend API: {BACKEND_API_BASE}",
            f"Owner ID: {self.owner_id}",
            f"Offset update: {self.state.get('update_offset')}",
            f"Pending URL: {'ada' if self.state.get('pending_url') else 'tidak ada'}",
            f"Active job state: {self.state.get('active_job_id') or '-'}",
            f"Job dipantau: {len(self.state.get('jobs', {}))}",
            f"Upload YouTube dipantau: {len(self.state.get('youtube_uploads', {}))}",
        ]
        battery = read_battery_status()
        self.last_battery_status = battery
        if battery:
            lines.append(
                f"Baterai: {battery['percent']}% ({battery['status']}, {battery['device']})"
            )
        else:
            lines.append(f"Baterai: tidak terdeteksi ({BATTERY_POWER_SUPPLY_PATH})")
        try:
            health = self.backend.health()
            lines.append(f"Backend health: OK ({health.get('status') or 'ready'})")
        except ServiceError as exc:
            lines.append(f"Backend health: ERROR ({exc})")
        try:
            config = self.backend.youtube_config()
            lines.append(f"YouTube enabled: {bool(config.get('enabled'))}")
            lines.append(f"YouTube session: {'ada' if config.get('auth_state_exists') else 'belum ada'}")
            if config.get("active_upload_id"):
                lines.append(f"Upload aktif: {str(config['active_upload_id'])[:10]}")
        except ServiceError as exc:
            lines.append(f"YouTube config: ERROR ({exc})")
        self.send_message(chat_id, "\n".join(lines), main_menu_keyboard())

    def job_status_text(self, job: dict[str, Any]) -> str:
        status = str(job.get("status", "unknown"))
        status_label = {
            "queued": "Menunggu worker",
            "running": "Sedang diproses",
            "completed": "Selesai",
            "failed": "Gagal",
            "cancelled": "Dibatalkan",
        }.get(status, status)
        title = str(job.get("source_title") or job.get("request", {}).get("url") or "Video")[:500]
        lines = [
            f"Status: {status_label}",
            f"Sumber: {title}",
            f"Job: {str(job.get('id', ''))[:10]}",
            "Output: clip pendek + kompilasi maks. 5 menit",
            f"Durasi proses: {format_duration(elapsed_for_job(job))}",
        ]
        if status in ACTIVE_STATUSES:
            lines.insert(2, f"Tahap: {progress_stage(job)}")
        if status == "completed":
            clips = job.get("clips", [])
            compilation_count = sum(1 for clip in clips if is_compilation_result(clip))
            lines.append(f"Hasil: {len(clips) - compilation_count} clip pendek + {compilation_count} kompilasi")
        if status in {"failed", "cancelled"} and job.get("error"):
            lines.append(f"Keterangan: {str(job['error'])[:2000]}")
        return "\n".join(lines)

    def job_keyboard(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("id", ""))
        status = str(job.get("status") or "")
        rows: list[list[dict[str, str]]] = []
        if status in ACTIVE_STATUSES:
            rows.append([button("🔄 Perbarui", f"refresh:{job_id}"), button("⏹ Batalkan", f"cancelask:{job_id}")])
        elif status == "completed" and job.get("clips"):
            rows.append([button("📤 Kirim Semua Hasil", f"deliver:{job_id}")])
            rows.append([button("⬆️ Upload 3 Terbaik ke YouTube", f"ytall:{job_id}")])
        if status in {"queued", "failed", "cancelled"}:
            rows.append([button("🗑 Hapus Job", f"deleteask:{job_id}")])
        rows.append([button("📚 Riwayat", "menu:history"), button("🏠 Menu", "menu:home")])
        return keyboard(rows)

    def show_job(self, chat_id: int, job: dict[str, Any], message_id: int | None = None) -> None:
        text = self.job_status_text(job)
        markup = self.job_keyboard(job)
        if message_id:
            self.edit_message(chat_id, message_id, text, markup)
        else:
            self.send_message(chat_id, text, markup)

    def current_active_job(self) -> dict[str, Any] | None:
        active_job_id = self.state.get("active_job_id")
        if isinstance(active_job_id, str) and active_job_id:
            try:
                job = self.backend.get_job(active_job_id)
                if job.get("status") in ACTIVE_STATUSES:
                    return job
                self.state["active_job_id"] = None
                self.persist()
            except ServiceError:
                pass
        for job in self.backend.list_jobs():
            if job.get("status") in ACTIVE_STATUSES:
                return job
        return None

    def show_status(self, chat_id: int) -> None:
        try:
            active = self.current_active_job()
        except ServiceError as exc:
            self.send_message(chat_id, f"Backend belum dapat dihubungi: {exc}", main_menu_keyboard())
            return
        except Exception as exc:
            self.send_message(chat_id, f"Gagal membaca status: {type(exc).__name__}: {exc}", main_menu_keyboard())
            return
        if active:
            self.show_job(chat_id, active)
            return
        self.send_message(chat_id, "Tidak ada proses clipping yang sedang berjalan.", main_menu_keyboard())

    def show_history(self, chat_id: int) -> None:
        try:
            jobs = self.backend.list_jobs()[:8]
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memuat riwayat: {exc}", main_menu_keyboard())
            return
        if not jobs:
            self.send_message(chat_id, "Riwayat clipping masih kosong.", main_menu_keyboard())
            return
        labels = {
            "queued": "Menunggu",
            "running": "Diproses",
            "completed": "Selesai",
            "failed": "Gagal",
            "cancelled": "Dibatalkan",
        }
        lines = ["Riwayat clipping terbaru"]
        rows: list[list[dict[str, str]]] = []
        for index, job in enumerate(jobs, start=1):
            title = job.get("source_title") or job.get("request", {}).get("url") or "Video"
            title = str(title).replace("\n", " ")[:60]
            raw_status = str(job.get("status") or "")
            status = labels.get(raw_status, raw_status)
            lines.append(f"\n{index}. {status} · {len(job.get('clips', []))} clip\n{title}")
            job_id = str(job.get("id") or "")
            if raw_status in {"queued", "failed", "cancelled"}:
                rows.append(
                    [
                        button(f"Lihat #{index} · {status}", f"view:{job_id}"),
                        button("🗑 Hapus", f"deleteask:{job_id}"),
                    ]
                )
            else:
                rows.append([button(f"Lihat #{index} · {status}", f"view:{job_id}")])
        if any(str(job.get("status") or "") in {"failed", "cancelled"} for job in jobs):
            rows.append([button("🧹 Hapus Gagal/Dibatalkan", "deletefailedask")])
        rows.append([button("🏠 Menu Utama", "menu:home")])
        self.send_message(chat_id, "\n".join(lines), keyboard(rows))

    def youtube_upload_status_text(self, upload: dict[str, Any]) -> str:
        status = str(upload.get("status", "unknown"))
        status_label = {
            "queued": "Menunggu antrean",
            "running": "Sedang upload",
            "completed": "Selesai",
            "failed": "Gagal",
            "cancelled": "Dibatalkan",
        }.get(status, status)
        lines = [
            f"Upload YouTube: {status_label}",
            f"Tahap terakhir: {youtube_upload_stage_label(upload)}",
            f"Clip: {upload.get('clip_name') or '-'}",
            f"Judul: {str(upload.get('title') or '-')[:160]}",
            f"Deskripsi: {str(upload.get('description') or '-')[:220]}",
            f"Playlist: {upload.get('playlist') or '-'}",
            f"Hashtag/Tags: {', '.join(upload.get('tags') or []) or '-'}",
            f"Visibilitas: {upload.get('visibility') or '-'}",
        ]
        if upload.get("video_url"):
            lines.append(f"URL: {upload['video_url']}")
        if upload.get("error"):
            lines.append(f"Keterangan: {str(upload['error'])[:1600]}")
        logs = upload.get("logs")
        if isinstance(logs, list) and logs:
            lines.append(f"Log terakhir: {str(logs[-1])[:1000]}")
        return "\n".join(lines)

    def youtube_upload_keyboard(self, upload: dict[str, Any]) -> dict[str, Any]:
        rows: list[list[dict[str, str]]] = []
        status = str(upload.get("status") or "")
        if upload.get("video_url"):
            rows.append([url_button("🔗 Buka Video YouTube", str(upload["video_url"]))])
        if status == "failed":
            upload_id = upload.get("id")
            if isinstance(upload_id, str) and upload_id:
                rows.append([button("🔁 Retry Upload", f"ytretry:{upload_id}")])
            rows.append([button("✅ Login Sekali", "ytoncelogin"), button("🍪 Ambil Cookies CDP", "ytcookies")])
            rows.append([button("🔐 CDP Opsional", "ytcdp")])
            rows.append([button("🔁 Sync/Repair CDP", "ytsync"), button("🪟 Mode Tanpa CDP", "ytnocdp")])
            rows.append([button("🔐 Sync dari Profile Login", "ytprofile")])
            rows.append([button("🔀 Merge Session", "ytsession")])
            rows.append([button("⏹ Stop CDP", "ytcdpstop")])
            rows.append([url_button("🔐 Buka Studio", YOUTUBE_STUDIO_URL)])
            rows.append([button("📊 Status Upload YouTube", "menu:youtube")])
        rows.append([button("📚 Riwayat", "menu:history"), button("🏠 Menu", "menu:home")])
        return keyboard(rows)

    def latest_retryable_youtube_upload_id(self) -> str | None:
        try:
            uploads = self.backend.list_youtube_uploads()
        except ServiceError:
            uploads = []
        retryable: list[dict[str, Any]] = []
        for upload in uploads:
            upload_id = upload.get("id")
            if (
                isinstance(upload_id, str)
                and upload_id
                and str(upload.get("status") or "") == "failed"
                and isinstance(upload.get("source_job_id"), str)
                and isinstance(upload.get("clip_url"), str)
            ):
                retryable.append(upload)
        retryable.sort(
            key=lambda item: str(item.get("finished_at") or item.get("updated_at") or item.get("created_at") or ""),
            reverse=True,
        )
        if retryable:
            return str(retryable[0]["id"])
        uploads_state = self.state.get("youtube_uploads")
        if isinstance(uploads_state, dict):
            for upload_id in reversed(list(uploads_state.keys())):
                if isinstance(upload_id, str) and upload_id:
                    return upload_id
        return None

    def youtube_cdp_result_lines(self, result: dict[str, Any], *, success_title: str, failure_title: str) -> list[str]:
        logs = result.get("logs") if isinstance(result, dict) else []
        visible_logs = [str(line) for line in logs[-5:]] if isinstance(logs, list) else []
        last_log = visible_logs[-1][:700] if visible_logs else ""
        cdp_ready = bool(result.get("cdp_ready"))
        session_ready = bool(result.get("session_ready"))
        hydrated = bool(result.get("hydrated"))
        ok = bool(result.get("ok"))
        lines = [
            success_title if ok else failure_title,
            "",
            f"Remote debugging: {'aktif' if cdp_ready else 'tidak aktif'}",
            f"Session target: {'valid' if session_ready else 'belum valid'}",
            f"Hydrate storage-state: {'terpakai' if hydrated else 'tidak'}",
        ]
        if result.get("cookies_imported") or result.get("cookie_count") is not None:
            lines.append(
                "Cookies tersimpan: "
                f"{int(result.get('youtube_cookie_count') or 0)} YouTube/Google "
                f"dari {int(result.get('cookie_count') or 0)} total"
            )
            storage_state_path = str(result.get("storage_state_path") or "").strip()
            if storage_state_path:
                lines.append(f"Storage-state: {storage_state_path[:700]}")
        if result.get("profile_sync_requested") or result.get("source_profile_path"):
            source_profile = str(result.get("source_profile_path") or "-")
            lines.append(f"Source profile: {'terdeteksi' if result.get('source_profile_ready') else 'belum ditemukan'}")
            lines.append(f"Path profile: {source_profile[:700]}")
        detail = str(result.get("error") or result.get("message") or "").strip()
        if detail:
            lines.append(f"{'Info' if ok else 'Alasan'}: {detail[:1200]}")
        if last_log:
            lines.append(f"Log terakhir: {last_log}")
        return lines

    def youtube_session_capture_lines(self, result: dict[str, Any]) -> list[str]:
        logs = result.get("logs") if isinstance(result, dict) else []
        visible_logs = [str(line) for line in logs[-5:]] if isinstance(logs, list) else []
        last_log = visible_logs[-1][:700] if visible_logs else ""
        error = str(result.get("error") or "").strip()
        lines = [
            "Merge session YouTube selesai." if not error else "Merge session YouTube belum berhasil.",
            "",
            f"Storage-state: {'tersimpan/terbarui' if not error else 'belum valid'}",
        ]
        if error:
            lines.append(f"Alasan: {error[:1200]}")
        else:
            lines.append("Session dari Chrome CDP sudah dicapture untuk dipakai upload otomatis.")
        if last_log:
            lines.append(f"Log terakhir: {last_log}")
        return lines

    def youtube_one_time_login_lines(self, result: dict[str, Any]) -> list[str]:
        logs = result.get("logs") if isinstance(result, dict) else []
        visible_logs = [str(line) for line in logs[-5:]] if isinstance(logs, list) else []
        last_log = visible_logs[-1][:700] if visible_logs else ""
        ok = bool(result.get("ok"))
        error = str(result.get("error") or result.get("message") or "").strip()
        login_required = bool(result.get("login_required"))
        lines = [
            (
                "Jendela login YouTube sudah dibuka."
                if login_required
                else "Login sekali aktif. Upload berikutnya otomatis."
                if ok
                else "Login sekali belum berhasil."
            ),
            "",
            "Mode: Playwright tanpa CDP",
            f"Session tersimpan: {'ya' if ok else 'belum'}",
            "Cookies tersimpan: "
            f"{int(result.get('youtube_cookie_count') or 0)} YouTube/Google "
            f"dari {int(result.get('cookie_count') or 0)} total",
        ]
        storage_state_path = str(result.get("storage_state_path") or "").strip()
        if storage_state_path:
            lines.append(f"Storage-state: {storage_state_path[:700]}")
        if error:
            lines.append(f"{'Info' if ok or login_required else 'Alasan'}: {error[:1200]}")
        if last_log:
            lines.append(f"Log terakhir: {last_log}")
        return lines

    def youtube_control_keyboard(self) -> dict[str, Any]:
        rows: list[list[dict[str, str]]] = [
            [button("✅ Login Sekali", "ytoncelogin"), button("🍪 Ambil Cookies CDP", "ytcookies")],
            [button("🔐 CDP Opsional", "ytcdp")],
            [button("🔁 Sync/Repair CDP", "ytsync"), button("🪟 Mode Tanpa CDP", "ytnocdp")],
            [button("🔐 Sync dari Profile Login", "ytprofile")],
            [button("🔀 Merge Session", "ytsession")],
        ]
        retry_upload_id = self.latest_retryable_youtube_upload_id()
        if retry_upload_id:
            rows.append([button("🔁 Retry Upload", f"ytretry:{retry_upload_id}")])
        rows.extend(
            [
                [button("⏹ Stop CDP", "ytcdpstop")],
                [button("📚 Riwayat", "menu:history"), button("🏠 Menu", "menu:home")],
            ]
        )
        return keyboard(rows)

    def show_youtube_status(self, chat_id: int) -> None:
        try:
            config = self.backend.youtube_config()
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memeriksa uploader YouTube: {exc}", main_menu_keyboard())
            return
        lines = [
            "Status uploader YouTube",
            f"Playwright: {'siap' if config.get('playwright_installed') else 'belum terpasang'}",
            f"Sesi login: {'ada' if config.get('auth_state_exists') else 'belum ada'}",
            f"Mode: {config.get('auth_status_message') or '-'}",
            f"Default visibility: {config.get('default_visibility') or 'private'}",
        ]
        if config.get("active_upload_id"):
            lines.append(f"Upload aktif: {str(config['active_upload_id'])[:10]}")
        if not config.get("enabled"):
            lines.append(
                "\nUploader belum siap. Tekan Login Sekali agar bot menyimpan session Playwright dari storage/profile."
            )
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())

    def youtube_record(self, upload_id: str, chat_id: int) -> dict[str, Any]:
        uploads = self.state.setdefault("youtube_uploads", {})
        record = uploads.setdefault(upload_id, {"chat_id": chat_id, "terminal_notified": False})
        record["chat_id"] = chat_id
        record.setdefault("stage_alerts", [])
        return record

    def announce_youtube_queued(self, chat_id: int, upload_id: str, upload: dict[str, Any], record: dict[str, Any]) -> None:
        sent_raw = record.setdefault("stage_alerts", [])
        sent = {str(item) for item in sent_raw if isinstance(item, str)}
        if "queued" in sent:
            return
        clip_name = str(upload.get("clip_name") or upload.get("title") or "Clip")[:120]
        self.send_message(
            chat_id,
            "Upload YouTube masuk antrean\n\n"
            f"Clip: {clip_name}\n"
            f"Judul: {str(upload.get('title') or '-')[:160]}\n"
            f"Playlist: {upload.get('playlist') or '-'}\n"
            f"Upload: {upload_id[:10]}",
        )
        sent.add("queued")
        record["stage_alerts"] = list(sent)

    def remember_youtube_uploads(
        self,
        chat_id: int,
        uploads: list[dict[str, Any]],
        *,
        announce_queued: bool = False,
    ) -> None:
        for upload in uploads:
            upload_id = upload.get("id")
            if isinstance(upload_id, str) and upload_id:
                record = self.youtube_record(upload_id, chat_id)
                if announce_queued and upload.get("status") == "queued":
                    self.announce_youtube_queued(chat_id, upload_id, upload, record)
        self.persist()

    def remember_job_youtube_uploads(self, job_id: str, chat_id: int) -> None:
        try:
            uploads = [
                upload
                for upload in self.backend.list_youtube_uploads()
                if upload.get("source_job_id") == job_id
            ]
        except ServiceError:
            return
        known = self.state.setdefault("youtube_uploads", {})
        new_uploads = [
            upload
            for upload in uploads
            if isinstance(upload.get("id"), str) and upload["id"] not in known
        ]
        if new_uploads:
            self.remember_youtube_uploads(chat_id, new_uploads, announce_queued=True)

    def discover_active_youtube_uploads(self) -> None:
        now = time.monotonic()
        if now - self.last_youtube_upload_discovery < YOUTUBE_UPLOAD_DISCOVERY_INTERVAL:
            return
        self.last_youtube_upload_discovery = now
        try:
            uploads = self.backend.list_youtube_uploads()
        except ServiceError as exc:
            if now - self.last_backend_warning > 60:
                print(f"Sinkronisasi upload YouTube tertunda: {exc}", flush=True)
                self.last_backend_warning = now
            return

        uploads_state = self.state.setdefault("youtube_uploads", {})
        changed = False
        for upload in uploads:
            upload_id = upload.get("id")
            status = str(upload.get("status") or "")
            age = seconds_since_iso(
                upload.get("updated_at") or upload.get("finished_at") or upload.get("created_at")
            )
            recent_terminal = (
                status in TERMINAL_STATUSES
                and age is not None
                and -60.0 <= age <= YOUTUBE_UPLOAD_RECENT_TERMINAL_SECONDS
            )
            if (
                not isinstance(upload_id, str)
                or not upload_id
                or upload_id in uploads_state
                or (status not in ACTIVE_STATUSES and not recent_terminal)
            ):
                continue
            uploads_state[upload_id] = {
                "chat_id": self.owner_id,
                "terminal_notified": False,
                "stage_alerts": [],
            }
            changed = True
        if changed:
            self.persist()

    def repair_youtube_cdp_session(self, chat_id: int, *, reason: str = "upload") -> bool:
        self.send_message(
            chat_id,
            f"Menyiapkan Chrome CDP untuk {reason}.\n\n"
            "Backend akan stop CDP lama, start CDP baru, hydrate session, lalu validasi Studio target.",
        )
        try:
            repair = self.backend.repair_youtube_cdp()
        except ServiceError as exc:
            self.send_message(
                chat_id,
                "Repair Chrome CDP gagal dari bot.\n\n"
                f"Alasan: {exc}\n"
                "Upload belum dilanjutkan agar tidak gagal berulang.",
                self.youtube_control_keyboard(),
            )
            return False

        if not repair.get("ok"):
            lines = self.youtube_cdp_result_lines(
                repair,
                success_title="Chrome CDP siap dipakai dari bot.",
                failure_title="Chrome CDP belum siap untuk upload.",
            )
            self.send_message(
                chat_id,
                "\n".join(lines),
                self.youtube_control_keyboard(),
            )
            return False

        lines = self.youtube_cdp_result_lines(
            repair,
            success_title="Chrome CDP siap dipakai dari bot.",
            failure_title="Chrome CDP belum siap untuk upload.",
        )
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
        return True

    def run_youtube_cdp_launcher(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Auto login Chrome CDP otomatis.\n\n"
            "Bot akan ambil session dari profile/storage-state, start CDP, hydrate login, lalu validasi YouTube Studio target.",
        )
        try:
            result = self.backend.auto_login_youtube_cdp()
        except ServiceError as exc:
            self.send_message(
                chat_id,
                f"Auto login CDP gagal dari bot.\n\nAlasan: {exc}\n\n"
                "Pastikan profile Chrome yang sudah login sudah di-mount/terdeteksi.",
                self.youtube_control_keyboard(),
            )
            return
        lines = self.youtube_cdp_result_lines(
            result,
            success_title="Chrome CDP otomatis login dan siap.",
            failure_title="Chrome CDP auto-login belum siap.",
        )
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())

    def import_youtube_cdp_cookies_from_bot(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Mengambil cookies dari Chrome CDP.\n\n"
            "Bot akan akses Chrome remote debugging yang sudah login, tanpa hydrate storage-state lama, lalu menyimpan cookies baru.",
        )
        try:
            result = self.backend.import_youtube_cdp_cookies()
        except ServiceError as exc:
            self.send_message(
                chat_id,
                f"Ambil cookies CDP gagal.\n\nAlasan: {exc}",
                self.youtube_control_keyboard(),
            )
            return
        lines = self.youtube_cdp_result_lines(
            result,
            success_title="Cookies Chrome CDP berhasil diambil.",
            failure_title="Cookies Chrome CDP belum berhasil diambil.",
        )
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())

    def setup_youtube_one_time_login_from_bot(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Menyiapkan login sekali YouTube.\n\n"
            "Bot akan ambil cookies/session dari Chrome/profile yang sudah login, simpan storage-state, lalu upload berikutnya jalan tanpa CDP.",
        )
        try:
            result = self.backend.setup_youtube_one_time_login()
        except ServiceError as exc:
            self.send_message(
                chat_id,
                f"Login sekali belum berhasil.\n\nAlasan: {exc}",
                self.youtube_control_keyboard(),
            )
            return
        lines = self.youtube_one_time_login_lines(result)
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())

    def sync_youtube_cdp_from_profile(self, chat_id: int) -> bool:
        self.send_message(
            chat_id,
            "Sync YouTube dari profile Chrome yang sudah login.\n\n"
            "Bot akan copy source profile ke profile CDP, start Chrome tanpa perlu window login, lalu capture session.",
        )
        try:
            result = self.backend.sync_youtube_cdp_from_profile()
        except ServiceError as exc:
            self.send_message(
                chat_id,
                f"Sync dari profile login gagal.\n\nAlasan: {exc}",
                self.youtube_control_keyboard(),
            )
            return False
        lines = self.youtube_cdp_result_lines(
            result,
            success_title="Session YouTube berhasil diambil dari profile login.",
            failure_title="Session dari profile login belum valid.",
        )
        if not result.get("ok") and not result.get("source_profile_ready"):
            lines.append(
                "Pastikan .env mengarah ke user-data-dir Chrome yang sudah login, bukan folder Profile saja."
            )
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
        return bool(result.get("ok"))

    def enable_youtube_direct_profile_mode(self, chat_id: int) -> bool:
        try:
            config = self.backend.enable_youtube_direct_profile_upload()
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal mengaktifkan mode tanpa CDP: {exc}", self.youtube_control_keyboard())
            return False
        lines = [
            "Mode upload tanpa CDP aktif.",
            "",
            "Backend akan launch browser/profile sendiri, buka tab YouTube Studio, lalu proses upload dari situ.",
            f"Profile: {config.get('chromium_profile_path') or config.get('auth_state_path') or '-'}",
            f"Profile terdeteksi: {'ya' if config.get('chromium_profile_ready') else 'tidak'}",
        ]
        if not config.get("enabled"):
            lines.append("Uploader belum siap. Pastikan path profile Chromium/Chrome yang sudah login sudah benar.")
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
        return bool(config.get("enabled"))

    def prepare_youtube_upload_session(self, chat_id: int, *, reason: str) -> bool:
        try:
            config = self.backend.youtube_config()
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memeriksa uploader YouTube: {exc}", self.youtube_control_keyboard())
            return False
        self.send_message(
            chat_id,
            f"Menyiapkan session Playwright untuk {reason}.\n\n"
            "Bot akan validasi Login Sekali dulu supaya storage-state tidak basi.",
            self.youtube_control_keyboard(),
        )
        try:
            result = self.backend.setup_youtube_one_time_login()
        except ServiceError as exc:
            self.send_message(chat_id, f"Login sekali belum berhasil.\n\nAlasan: {exc}", self.youtube_control_keyboard())
            return False
        if result.get("ok"):
            self.send_message(chat_id, "\n".join(self.youtube_one_time_login_lines(result)), self.youtube_control_keyboard())
            return True
        self.send_message(chat_id, "\n".join(self.youtube_one_time_login_lines(result)), self.youtube_control_keyboard())
        return False
        if config.get("upload_uses_cdp"):
            return False
        if config.get("enabled"):
            if config.get("direct_profile_upload"):
                self.send_message(chat_id, "Mode profile aktif, tapi Login Sekali belum valid. Upload dibatalkan dulu agar tidak salah akun/session.", self.youtube_control_keyboard())
                return False
            return True
        self.send_message(
            chat_id,
            "Uploader YouTube belum siap. Tekan Login Sekali untuk menyimpan session Playwright, atau Mode Tanpa CDP jika ingin memakai profile backend langsung.",
            self.youtube_control_keyboard(),
        )
        return False

    def sync_youtube_cdp_session(self, chat_id: int, *, reason: str = "manual", auto_repair: bool = True) -> bool:
        self.send_message(
            chat_id,
            f"Sync Chrome CDP untuk {reason}.\n\n"
            "Bot akan memakai CDP yang sudah aktif. Kalau belum aktif atau session belum valid, bot lanjut repair otomatis.",
        )
        try:
            result = self.backend.sync_youtube_cdp()
        except ServiceError as exc:
            if not auto_repair:
                self.send_message(
                    chat_id,
                    f"Sync CDP gagal dari bot.\n\nAlasan: {exc}",
                    self.youtube_control_keyboard(),
                )
                return False
            self.send_message(chat_id, "Sync biasa gagal. Bot lanjut repair CDP otomatis...")
            try:
                result = self.backend.repair_youtube_cdp()
            except ServiceError as repair_exc:
                self.send_message(
                    chat_id,
                    f"Repair CDP otomatis gagal.\n\nAlasan: {repair_exc}",
                    self.youtube_control_keyboard(),
                )
                return False

        if not result.get("ok") and auto_repair:
            self.send_message(chat_id, "Session belum valid. Bot lanjut start/restart CDP dan sync otomatis...")
            try:
                result = self.backend.repair_youtube_cdp()
            except ServiceError as repair_exc:
                self.send_message(
                    chat_id,
                    f"Repair CDP otomatis gagal.\n\nAlasan: {repair_exc}",
                    self.youtube_control_keyboard(),
                )
                return False

        if not result.get("ok"):
            lines = self.youtube_cdp_result_lines(
                result,
                success_title="Chrome CDP tersinkron dan aman untuk upload.",
                failure_title="Chrome CDP belum valid untuk upload.",
            )
            self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
            return False

        lines = self.youtube_cdp_result_lines(
            result,
            success_title="Chrome CDP tersinkron dan aman untuk upload.",
            failure_title="Chrome CDP belum valid untuk upload.",
        )
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
        return True

    def capture_youtube_session_from_bot(self, chat_id: int, *, auto_repair: bool = True) -> bool:
        self.send_message(
            chat_id,
            "Merge session YouTube dari bot.\n\n"
            "Bot akan mengambil session dari Chrome CDP yang aktif dan menyimpan storage-state untuk upload otomatis.",
        )
        try:
            result = self.backend.capture_youtube_session()
        except ServiceError as exc:
            if not auto_repair:
                self.send_message(
                    chat_id,
                    f"Merge session gagal dari bot.\n\nAlasan: {exc}",
                    self.youtube_control_keyboard(),
                )
                return False
            self.send_message(chat_id, "Merge session belum berhasil. Bot lanjut recovery CDP opsional...")
            return self.repair_youtube_cdp_session(chat_id, reason="merge session")

        lines = self.youtube_session_capture_lines(result)
        ok = not result.get("error")
        if not ok and auto_repair:
            self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
            self.send_message(chat_id, "Bot lanjut repair CDP otomatis supaya session bisa dipakai...")
            return self.repair_youtube_cdp_session(chat_id, reason="merge session")
        self.send_message(chat_id, "\n".join(lines), self.youtube_control_keyboard())
        return ok

    def start_youtube_upload_for_clip(self, chat_id: int, job_id: str, clip_index: int, *, preflight: bool = False) -> None:
        try:
            job = self.backend.get_job(job_id)
            clips = job.get("clips", [])
            if job.get("status") != "completed" or not isinstance(clips, list):
                self.send_message(chat_id, "Job belum selesai atau tidak punya clip.", self.job_keyboard(job))
                return
            if clip_index < 1 or clip_index > len(clips):
                self.send_message(chat_id, "Clip yang dipilih tidak ditemukan.", self.job_keyboard(job))
                return
            clip = clips[clip_index - 1]
            if preflight and not self.prepare_youtube_upload_session(chat_id, reason="upload clip"):
                return
            upload = self.backend.create_youtube_upload(job_id, str(clip.get("url", "")))
            self.remember_youtube_uploads(chat_id, [upload], announce_queued=True)
            self.send_message(chat_id, "Status awal upload YouTube\n\n" + self.youtube_upload_status_text(upload))
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal membuat upload YouTube: {exc}", main_menu_keyboard())

    def start_youtube_upload_for_url(self, chat_id: int, job_id: str, clip_url: str, *, preflight: bool = False) -> None:
        try:
            if preflight and not self.prepare_youtube_upload_session(chat_id, reason="retry upload"):
                return
            upload = self.backend.create_youtube_upload(job_id, clip_url)
            self.remember_youtube_uploads(chat_id, [upload], announce_queued=True)
            self.send_message(chat_id, "Status awal retry upload YouTube\n\n" + self.youtube_upload_status_text(upload))
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal retry upload YouTube: {exc}", main_menu_keyboard())

    def start_youtube_upload_all(self, chat_id: int, job_id: str, *, preflight: bool = False) -> None:
        try:
            if preflight and not self.prepare_youtube_upload_session(chat_id, reason="batch upload"):
                return
            uploads = self.backend.create_youtube_upload_batch(job_id)
            self.remember_youtube_uploads(chat_id, uploads, announce_queued=True)
            self.send_message(
                chat_id,
                f"{len(uploads)} clip terbaik dimasukkan ke antrean upload YouTube.",
                keyboard([[button("📊 Status Upload YouTube", "menu:youtube")], [button("🏠 Menu", "menu:home")]]),
            )
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal membuat batch upload YouTube: {exc}", main_menu_keyboard())

    def receive_url(self, chat_id: int, value: str) -> None:
        url = value.strip()
        if not is_supported_video_url(url):
            self.send_message(
                chat_id,
                "Link belum dikenali. Kirim link YouTube lengkap, misalnya https://youtu.be/...",
                main_menu_keyboard(),
            )
            return
        self.state["pending_url"] = url
        self.state["waiting_for_url"] = False
        self.persist()
        self.show_pending(chat_id)

    def start_job(self, chat_id: int) -> None:
        url = str(self.state.get("pending_url", ""))
        if not is_supported_video_url(url):
            self.send_message(chat_id, "Link belum tersedia. Kirim link YouTube terlebih dahulu.", main_menu_keyboard())
            return
        try:
            active = self.current_active_job()
            if active:
                self.send_message(
                    chat_id,
                    "Masih ada proses clipping aktif. Tunggu sampai selesai atau batalkan terlebih dahulu.",
                    self.job_keyboard(active),
                )
                return
            job = self.backend.create_job(url, self.state["settings"])
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memulai clipping: {exc}", main_menu_keyboard())
            return

        job_id = str(job["id"])
        self.state["active_job_id"] = job_id
        self.state["pending_url"] = ""
        self.state["waiting_for_url"] = False
        self.state["jobs"][job_id] = {
            "chat_id": chat_id,
            "terminal_notified": False,
            "delivery": {"summary": False, "clips": {}},
            "stage_alerts": ["queued"],
        }
        self.persist()
        status_message = self.send_message(
            chat_id,
            "Proses dimulai: bot membuat clip pendek sekaligus satu kompilasi maksimal 5 menit. "
            "Alert tahap demi tahap aktif dan semua hasil akan dikirim otomatis.",
            self.job_keyboard(job),
        )
        self.state["jobs"][job_id]["status_message_id"] = status_message.get("message_id")
        self.persist()

    def clip_metadata_text(self, clip: dict[str, Any], index: int, total: int) -> str:
        result_label = "Kompilasi Maks. 5 Menit" if is_compilation_result(clip) else "Clip Pendek"
        parts = [f"Detail {result_label}", f"Judul:\n{clip_title(clip, index)}"]
        social_caption = clip.get("social_caption")
        if isinstance(social_caption, str) and social_caption.strip():
            parts.append("Caption sosial:\n" + social_caption.strip())
        thumbnail_prompt = clip.get("thumbnail_prompt")
        if isinstance(thumbnail_prompt, str) and thumbnail_prompt.strip():
            parts.append("Prompt thumbnail:\n" + thumbnail_prompt.strip())
        return "\n\n".join(parts)

    def send_media_file(
        self,
        chat_id: int,
        method: str,
        field: str,
        path: Path,
        caption: str,
    ) -> None:
        if path.stat().st_size > MAX_UPLOAD_BYTES:
            public_url = ""
            try:
                relative = path.resolve().relative_to(OUTPUTS_DIR.resolve()).as_posix()
                if PUBLIC_OUTPUT_BASE_URL:
                    public_url = f"{PUBLIC_OUTPUT_BASE_URL}/outputs/{relative}"
            except ValueError:
                pass
            message = (
                f"{caption}\n\nFile {format_size(path.stat().st_size)} melebihi batas upload Telegram "
                f"{format_size(MAX_UPLOAD_BYTES)}."
            )
            if public_url:
                message += f"\nUnduh: {public_url}"
            else:
                message += "\nFile tetap tersedia di dashboard Fendy Clipper."
            self.send_message(chat_id, message)
            return
        self.telegram.call(
            "sendChatAction",
            {"chat_id": chat_id, "action": "upload_video" if method == "sendVideo" else "upload_photo"},
            timeout=10,
        )
        fields: dict[str, Any] = {"chat_id": chat_id, "caption": caption[:1024]}
        if method == "sendVideo":
            fields["supports_streaming"] = True
        try:
            self.telegram.call(
                method,
                fields,
                timeout=240,
                file_field=field,
                file_path=path,
            )
        except ServiceError:
            if method != "sendVideo":
                raise
            self.telegram.call(
                "sendDocument",
                {"chat_id": chat_id, "caption": caption[:1024]},
                timeout=240,
                file_field="document",
                file_path=path,
            )

    def delivery_record(self, job_id: str, chat_id: int) -> dict[str, Any]:
        record = self.state["jobs"].setdefault(
            job_id,
            {
                "chat_id": chat_id,
                "terminal_notified": False,
                "delivery": {"summary": False, "clips": {}},
            },
        )
        record["chat_id"] = chat_id
        record.setdefault("stage_alerts", [])
        delivery = record.setdefault("delivery", {"summary": False, "clips": {}})
        delivery.setdefault("summary", False)
        delivery.setdefault("clips", {})
        return record

    def deliver_job(self, chat_id: int, job: dict[str, Any], *, force: bool = False) -> None:
        job_id = str(job["id"])
        record = self.delivery_record(job_id, chat_id)
        if force:
            record["terminal_notified"] = False
            record["delivery"] = {"summary": False, "clips": {}}
            self.persist()
        delivery = record["delivery"]
        clips = job.get("clips", [])
        compilation_count = sum(1 for clip in clips if is_compilation_result(clip))
        short_count = len(clips) - compilation_count
        if not delivery["summary"]:
            source = job.get("source_title") or job.get("request", {}).get("url") or "Video"
            uploader = job.get("source_uploader")
            summary = (
                "Clipping selesai\n\n"
                f"Sumber: {source}\n"
                + (f"Channel: {uploader}\n" if uploader else "")
                + f"Clip pendek: {short_count}\n"
                + f"Kompilasi maksimal 5 menit: {compilation_count}\n"
                + f"Total hasil: {len(clips)} video\n"
                + f"Durasi proses: {format_duration(job.get('duration_seconds'))}\n\n"
                + "Bot mulai mengirim video dan materi pendukung satu per satu."
            )
            self.send_message(chat_id, summary)
            delivery["summary"] = True
            self.persist()

        short_position = 0
        for index, clip in enumerate(clips, start=1):
            clip_url = str(clip.get("url", ""))
            artifact = delivery["clips"].setdefault(
                clip_url, {"video": False, "thumbnail": False, "metadata": False}
            )
            path = output_path_from_url(clip_url)
            title = clip_title(clip, index)
            if is_compilation_result(clip):
                result_label = "Kompilasi Maks. 5 Menit"
            else:
                short_position += 1
                result_label = f"Clip Pendek {short_position}/{short_count}"
            if not artifact["video"]:
                if path is None or not path.is_file():
                    self.send_message(chat_id, f"Clip {index}/{len(clips)} tidak ditemukan di penyimpanan: {title}")
                else:
                    self.send_media_file(
                        chat_id,
                        "sendVideo",
                        "video",
                        path,
                        f"{result_label}\n{title}\n{format_size(path.stat().st_size)}",
                    )
                artifact["video"] = True
                self.persist()

            thumbnail_url = clip.get("thumbnail_url")
            if not artifact["thumbnail"]:
                thumb_path = output_path_from_url(str(thumbnail_url)) if thumbnail_url else None
                if thumb_path is not None and thumb_path.is_file():
                    self.send_media_file(
                        chat_id,
                        "sendPhoto",
                        "photo",
                        thumb_path,
                        f"Thumbnail {result_label} · {title}",
                    )
                artifact["thumbnail"] = True
                self.persist()

            if not artifact["metadata"]:
                self.send_long_message(chat_id, self.clip_metadata_text(clip, index, len(clips)))
                self.send_message(
                    chat_id,
                    f"Aksi untuk {result_label}",
                    keyboard([[button("⬆️ Upload Clip Ini ke YouTube", f"ytup:{job_id}:{index}")]]),
                )
                artifact["metadata"] = True
                self.persist()

        record["terminal_notified"] = True
        self.persist()
        self.send_message(
            chat_id,
            f"Semua hasil job {job_id[:10]} sudah dikirim.",
            keyboard(
                [
                    [button("⬆️ Upload 3 Terbaik ke YouTube", f"ytall:{job_id}")],
                    [button("🎬 Clipping Baru", "menu:new")],
                    [button("📚 Riwayat", "menu:history"), button("🏠 Menu", "menu:home")],
                ]
            ),
        )

    def notify_terminal_job(self, job_id: str, record: dict[str, Any], job: dict[str, Any]) -> None:
        if record.get("terminal_notified"):
            return
        chat_id = int(record.get("chat_id") or self.owner_id)
        status = job.get("status")
        status_message_id = record.get("status_message_id")
        if isinstance(status_message_id, int):
            try:
                self.show_job(chat_id, job, status_message_id)
            except ServiceError:
                pass
        if status == "completed":
            self.deliver_job(chat_id, job)
        else:
            self.send_message(chat_id, self.job_status_text(job), self.job_keyboard(job))
            record["terminal_notified"] = True
            self.persist()

    def notify_stage_alerts(self, job_id: str, record: dict[str, Any], job: dict[str, Any]) -> None:
        chat_id = int(record.get("chat_id") or self.owner_id)
        sent_raw = record.setdefault("stage_alerts", [])
        sent = {str(item) for item in sent_raw if isinstance(item, str)}
        alerts = clipping_stage_alerts(job, sent)
        if not alerts:
            return

        source = str(job.get("source_title") or job.get("request", {}).get("url") or "Video")[:120]
        for stage_id, label, detail in alerts:
            self.send_message(
                chat_id,
                f"Tahap clipping: {label}\n\n{detail}\n\nSumber: {source}\nJob: {job_id[:10]}",
            )
            sent.add(stage_id)
        record["stage_alerts"] = list(sent)
        self.persist()

    def monitor_jobs(self) -> None:
        for job_id, record in list(self.state.get("jobs", {}).items()):
            if not isinstance(record, dict):
                continue
            try:
                self.remember_job_youtube_uploads(job_id, int(record.get("chat_id") or self.owner_id))
            except Exception as exc:
                now = time.monotonic()
                if now - self.last_backend_warning > 60:
                    print(f"Sinkronisasi upload YouTube tertunda: {exc}", flush=True)
                    self.last_backend_warning = now
            if record.get("terminal_notified"):
                continue
            try:
                job = self.backend.get_job(job_id)
            except ServiceError:
                continue
            try:
                self.notify_stage_alerts(job_id, record, job)
            except ServiceError as exc:
                now = time.monotonic()
                if now - self.last_backend_warning > 60:
                    print(f"Pengiriman alert Telegram tertunda: {exc}", flush=True)
                    self.last_backend_warning = now
            if job.get("status") in ACTIVE_STATUSES:
                updated_at = float(record.get("last_status_update", 0) or 0)
                status_message_id = record.get("status_message_id")
                if isinstance(status_message_id, int) and time.time() - updated_at >= 30:
                    try:
                        self.show_job(int(record.get("chat_id") or self.owner_id), job, status_message_id)
                        record["last_status_update"] = time.time()
                        self.persist()
                    except ServiceError:
                        pass
                continue
            if job.get("status") in TERMINAL_STATUSES:
                if self.state.get("active_job_id") == job_id:
                    self.state["active_job_id"] = None
                    self.persist()
                try:
                    self.notify_terminal_job(job_id, record, job)
                except ServiceError as exc:
                    now = time.monotonic()
                    if now - self.last_backend_warning > 60:
                        print(f"Pengiriman hasil Telegram tertunda: {exc}", flush=True)
                        self.last_backend_warning = now

    def notify_youtube_stage_alerts(self, upload_id: str, record: dict[str, Any], upload: dict[str, Any]) -> None:
        chat_id = int(record.get("chat_id") or self.owner_id)
        sent_raw = record.setdefault("stage_alerts", [])
        sent = {str(item) for item in sent_raw if isinstance(item, str)}
        alerts = youtube_upload_stage_alerts(upload, sent)
        if not alerts:
            return

        clip_name = str(upload.get("clip_name") or upload.get("title") or "Clip")[:120]
        last_log = ""
        logs = upload.get("logs")
        if isinstance(logs, list) and logs:
            last_log = str(logs[-1])[:500]
        for stage_id, label, detail in alerts:
            lines = [
                f"Tahap upload YouTube: {label}",
                "",
                detail,
                "",
                f"Clip: {clip_name}",
                f"Upload: {upload_id[:10]}",
            ]
            if last_log and stage_id not in {"queued", "running"}:
                lines.append(f"Log: {last_log}")
            self.send_message(chat_id, "\n".join(lines))
            sent.add(stage_id)
        record["stage_alerts"] = list(sent)
        self.persist()

    def notify_youtube_terminal_alert(self, upload_id: str, record: dict[str, Any], upload: dict[str, Any]) -> None:
        chat_id = int(record.get("chat_id") or self.owner_id)
        status = str(upload.get("status") or "")
        clip_name = str(upload.get("clip_name") or upload.get("title") or "Clip")[:120]
        if status == "completed":
            lines = [
                "Upload YouTube berhasil",
                "",
                f"Clip: {clip_name}",
                f"Judul: {str(upload.get('title') or '-')[:160]}",
                f"Playlist: {upload.get('playlist') or '-'}",
                f"Upload: {upload_id[:10]}",
            ]
            if upload.get("video_url"):
                lines.append(f"URL: {upload['video_url']}")
            self.send_message(chat_id, "\n".join(lines), self.youtube_upload_keyboard(upload))
            return
        if status == "failed":
            lines = [
                "Upload YouTube gagal",
                "",
                f"Clip: {clip_name}",
                f"Upload: {upload_id[:10]}",
                f"Alasan: {str(upload.get('error') or '-')[:1200]}",
            ]
            logs = upload.get("logs")
            if isinstance(logs, list) and logs:
                lines.append(f"Log terakhir: {str(logs[-1])[:600]}")
            self.send_message(chat_id, "\n".join(lines), self.youtube_upload_keyboard(upload))
            return
        self.send_message(chat_id, self.youtube_upload_status_text(upload), self.youtube_upload_keyboard(upload))

    def monitor_youtube_uploads(self) -> None:
        self.discover_active_youtube_uploads()
        uploads_state = self.state.setdefault("youtube_uploads", {})
        for upload_id, record in list(uploads_state.items()):
            if not isinstance(record, dict) or record.get("terminal_notified"):
                continue
            try:
                upload = self.backend.get_youtube_upload(upload_id)
            except ServiceError:
                continue
            try:
                self.notify_youtube_stage_alerts(upload_id, record, upload)
            except ServiceError as exc:
                now = time.monotonic()
                if now - self.last_backend_warning > 60:
                    print(f"Pengiriman alert upload YouTube tertunda: {exc}", flush=True)
                    self.last_backend_warning = now
            if upload.get("status") in ACTIVE_STATUSES:
                continue
            if upload.get("status") in TERMINAL_STATUSES:
                try:
                    self.notify_youtube_terminal_alert(upload_id, record, upload)
                except ServiceError as exc:
                    now = time.monotonic()
                    if now - self.last_backend_warning > 60:
                        print(f"Pengiriman status akhir upload YouTube tertunda: {exc}", flush=True)
                        self.last_backend_warning = now
                record["terminal_notified"] = True
                self.persist()

    def handle_message(self, message: dict[str, Any]) -> None:
        sender_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        text = str(message.get("text") or "").strip()
        first_name = str(message.get("from", {}).get("first_name") or "")
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text.startswith("/") else ""
        if command:
            print(
                f"Telegram command diterima: {command} from={sender_id} chat={chat_id} type={chat_type}",
                flush=True,
            )
        if sender_id != self.owner_id or chat_type != "private" or not isinstance(chat_id, int):
            if command:
                print(
                    f"Telegram command ditolak: {command} owner={self.owner_id} from={sender_id} chat_type={chat_type}",
                    flush=True,
                )
            if isinstance(chat_id, int):
                try:
                    self.send_message(chat_id, "Bot ini bersifat privat dan hanya dapat digunakan oleh owner.")
                except ServiceError:
                    pass
            return

        if command in {"/start", "/menu"}:
            self.show_home(chat_id, first_name)
        elif command == "/clip":
            self.state["waiting_for_url"] = True
            self.persist()
            self.send_message(chat_id, "Kirim link YouTube yang ingin diproses.", keyboard([[button("❌ Batal", "pending:cancel")]]))
        elif command == "/settings":
            self.show_settings(chat_id)
        elif command == "/status":
            self.send_message(chat_id, "Mengecek status ClipForge...")
            self.show_status(chat_id)
        elif command in {"/battery", "/baterai"}:
            self.show_battery(chat_id)
        elif command == "/history":
            self.show_history(chat_id)
        elif command in {"/hapusgagal", "/cleanupjobs"}:
            self.request_delete_failed_jobs(chat_id)
        elif command == "/youtube":
            self.send_message(chat_id, "Mengecek status uploader YouTube...")
            self.show_youtube_status(chat_id)
        elif command in {"/cdp", "/youtubecdp"}:
            self.run_youtube_cdp_launcher(chat_id)
        elif command in {"/loginsekali", "/oncelogin", "/setlogin"}:
            self.setup_youtube_one_time_login_from_bot(chat_id)
        elif command in {"/cookies", "/cdpcookies", "/ambilcookies"}:
            self.import_youtube_cdp_cookies_from_bot(chat_id)
        elif command in {"/nocdp", "/directprofile"}:
            self.enable_youtube_direct_profile_mode(chat_id)
        elif command in {"/profilelogin", "/syncprofile"}:
            self.sync_youtube_cdp_from_profile(chat_id)
        elif command in {"/syncsession", "/ytsync"}:
            self.sync_youtube_cdp_session(chat_id, reason="command")
        elif command in {"/capturesession", "/mergesession"}:
            self.capture_youtube_session_from_bot(chat_id)
        elif command == "/getvideosviral":
            self.show_viral_video_suggestions(chat_id)
        elif command == "/debug":
            self.show_debug(chat_id)
        elif command == "/ping":
            self.send_message(chat_id, "pong - Telegram bot aktif.", main_menu_keyboard())
        elif command == "/help":
            self.show_help(chat_id)
        elif command == "/cancel":
            self.request_cancel(chat_id)
        elif is_supported_video_url(text):
            self.receive_url(chat_id, text)
        elif self.state.get("waiting_for_url"):
            self.receive_url(chat_id, text)
        elif text:
            self.send_message(chat_id, "Kirim link YouTube atau pilih salah satu menu di bawah.", main_menu_keyboard())

    def request_cancel(self, chat_id: int, job_id: str | None = None) -> None:
        try:
            job = self.backend.get_job(job_id) if job_id else self.current_active_job()
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memeriksa job: {exc}", main_menu_keyboard())
            return
        if not job or job.get("status") not in ACTIVE_STATUSES:
            self.send_message(chat_id, "Tidak ada proses aktif yang dapat dibatalkan.", main_menu_keyboard())
            return
        selected_id = str(job["id"])
        self.send_message(
            chat_id,
            "Batalkan proses clipping ini? Output sementara akan dibersihkan oleh backend.",
            keyboard(
                [
                    [button("Ya, Batalkan", f"cancel:{selected_id}")],
                    [button("Kembali", f"refresh:{selected_id}")],
                ]
            ),
        )

    def forget_job_state(self, job_id: str) -> None:
        if self.state.get("active_job_id") == job_id:
            self.state["active_job_id"] = None
        jobs_state = self.state.get("jobs")
        if isinstance(jobs_state, dict):
            jobs_state.pop(job_id, None)
        self.persist()

    def request_delete_job(self, chat_id: int, job_id: str) -> None:
        try:
            job = self.backend.get_job(job_id)
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memeriksa job: {exc}", main_menu_keyboard())
            return
        status = str(job.get("status") or "")
        if status == "running":
            self.send_message(chat_id, "Job sedang berjalan. Batalkan dulu sebelum menghapus.", self.job_keyboard(job))
            return
        if status not in {"queued", "failed", "cancelled"}:
            self.send_message(chat_id, "Job ini tidak termasuk failed/queued yang bisa dihapus dari bot.", self.job_keyboard(job))
            return
        label = {
            "queued": "menunggu antrean",
            "failed": "gagal",
            "cancelled": "dibatalkan",
        }.get(status, status)
        self.send_message(
            chat_id,
            f"Hapus job {label} ini dari riwayat?\n\nJob: {job_id[:10]}",
            keyboard(
                [
                    [button("Ya, Hapus Job", f"deletejob:{job_id}")],
                    [button("Kembali", f"refresh:{job_id}")],
                ]
            ),
        )

    def delete_job_from_bot(self, chat_id: int, job_id: str) -> None:
        try:
            result = self.backend.delete_job(job_id)
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal menghapus job: {exc}", main_menu_keyboard())
            return
        self.forget_job_state(job_id)
        removed_outputs = int(result.get("removed_outputs") or 0)
        extra = f"\nOutput terhapus: {removed_outputs}" if removed_outputs else ""
        self.send_message(chat_id, f"Job sudah dihapus dari riwayat.{extra}", main_menu_keyboard())

    def request_delete_failed_jobs(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Hapus semua job gagal/dibatalkan dari riwayat?\n\nJob completed dan running tidak ikut dihapus.",
            keyboard(
                [
                    [button("Ya, Hapus Gagal/Dibatalkan", "deletefailed")],
                    [button("Kembali", "menu:history")],
                ]
            ),
        )

    def delete_failed_jobs_from_bot(self, chat_id: int) -> None:
        try:
            result = self.backend.delete_failed_jobs()
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal menghapus job gagal/dibatalkan: {exc}", main_menu_keyboard())
            return
        removed = int(result.get("removed_jobs") or 0)
        if removed:
            try:
                remaining_ids = {str(job.get("id")) for job in self.backend.list_jobs() if job.get("id")}
            except ServiceError:
                remaining_ids = set()
            jobs_state = self.state.get("jobs")
            if isinstance(jobs_state, dict):
                for known_id in list(jobs_state):
                    if known_id not in remaining_ids:
                        jobs_state.pop(known_id, None)
            active_id = self.state.get("active_job_id")
            if isinstance(active_id, str) and active_id and active_id not in remaining_ids:
                self.state["active_job_id"] = None
            self.persist()
        self.send_message(chat_id, f"{removed} job gagal/dibatalkan sudah dihapus.", main_menu_keyboard())

    def apply_setting_callback(self, data: str) -> bool:
        parts = data.split(":")
        if len(parts) < 3 or parts[0] != "set":
            return False
        name, value = parts[1], parts[2]
        settings = self.state["settings"]
        if name == "top":
            if value == "auto":
                settings["top"] = None
            elif value.isdigit() and int(value) in ALLOWED_TOP:
                settings["top"] = int(value)
            else:
                return False
        elif name == "mode" and value in ALLOWED_CLIP_MODES:
            settings["clip_mode"] = "short"
            settings["top"] = None
            settings["min_duration"], settings["max_duration"] = 35, 180
        elif name == "duration" and len(parts) == 4:
            if not value.isdigit() or not parts[3].isdigit():
                return False
            duration = (int(value), int(parts[3]))
            if duration not in ALLOWED_DURATION_PRESETS:
                return False
            settings["min_duration"], settings["max_duration"] = duration
        elif name == "quality" and value in ALLOWED_QUALITY:
            settings["video_quality"] = value
        elif name == "crop" and value in ALLOWED_CROP:
            settings["crop_mode"] = value
        elif name == "subtitles" and value == "toggle":
            settings["burn_subtitles"] = not settings["burn_subtitles"]
        elif name == "ai" and value == "toggle":
            settings["ai_enabled"] = not settings["ai_enabled"]
        elif name == "position" and value in ALLOWED_CAPTION_POSITIONS:
            settings["caption_position"] = value
        elif name == "fontsize" and value.isdigit() and int(value) in ALLOWED_CAPTION_FONT_SIZES:
            settings["caption_font_size"] = int(value)
        else:
            return False
        self.state["settings"] = normalize_settings(settings)
        self.persist()
        return True

    def handle_callback(self, callback: dict[str, Any]) -> None:
        sender_id = callback.get("from", {}).get("id")
        callback_id = str(callback.get("id") or "")
        if sender_id != self.owner_id:
            self.answer_callback(callback_id, "Akses ditolak.", alert=True)
            return
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        message_id = message.get("message_id")
        if chat_type != "private" or not isinstance(chat_id, int):
            self.answer_callback(callback_id)
            return
        data = str(callback.get("data") or "")
        print(
            f"Telegram callback diterima: {data} from={sender_id} chat={chat_id} type={chat_type}",
            flush=True,
        )
        self.answer_callback(callback_id)

        def show_panel(text: str, reply_markup: dict[str, Any]) -> None:
            if isinstance(message_id, int):
                self.edit_message(chat_id, message_id, text, reply_markup)
            else:
                self.send_message(chat_id, text, reply_markup)

        if data == "menu:home":
            self.show_home(chat_id, str(callback.get("from", {}).get("first_name") or ""))
        elif data == "menu:new":
            self.state["waiting_for_url"] = True
            self.persist()
            self.send_message(chat_id, "Kirim link YouTube yang ingin diproses.", keyboard([[button("❌ Batal", "pending:cancel")]]))
        elif data == "menu:settings":
            self.show_settings(chat_id, message_id if isinstance(message_id, int) else None)
        elif data == "menu:status":
            self.send_message(chat_id, "Mengecek status ClipForge...")
            self.show_status(chat_id)
        elif data == "menu:battery":
            self.show_battery(chat_id)
        elif data == "menu:history":
            self.show_history(chat_id)
        elif data == "menu:youtube":
            self.send_message(chat_id, "Mengecek status uploader YouTube...")
            self.show_youtube_status(chat_id)
        elif data == "menu:debug":
            self.show_debug(chat_id)
        elif data == "menu:help":
            self.show_help(chat_id)
        elif data == "viral:refresh":
            self.show_viral_video_suggestions(chat_id)
        elif data.startswith("viralpick:"):
            suggestion_id = data.split(":", 1)[1]
            suggestions = self.state.get("viral_video_suggestions")
            source = suggestions.get(suggestion_id) if isinstance(suggestions, dict) else None
            url = source.get("url") if isinstance(source, dict) else None
            normalized_url = canonical_youtube_url(url)
            if normalized_url and is_supported_video_url(normalized_url):
                seen_urls = self.state.setdefault("viral_video_seen_urls", [])
                if isinstance(seen_urls, list) and normalized_url not in seen_urls:
                    seen_urls.append(normalized_url)
                    self.state["viral_video_seen_urls"] = seen_urls[-500:]
                self.state["pending_url"] = normalized_url
                self.state["waiting_for_url"] = False
                self.persist()
                self.show_pending(chat_id)
            else:
                self.send_message(chat_id, "Pilihan video sudah tidak tersedia. Tekan Cari Lagi.", keyboard([[button("🔄 Cari Lagi", "viral:refresh")], [button("🏠 Menu", "menu:home")]]))
        elif data == "pending:cancel":
            self.state["waiting_for_url"] = False
            self.state["pending_url"] = ""
            self.persist()
            self.send_message(chat_id, "Input link dibatalkan.", main_menu_keyboard())
        elif data == "pending:review":
            if is_supported_video_url(str(self.state.get("pending_url", ""))):
                self.show_pending(chat_id)
            else:
                self.send_message(chat_id, "Link belum tersedia. Kirim link YouTube terlebih dahulu.", main_menu_keyboard())
        elif data == "job:confirm":
            self.send_message(
                chat_id,
                "Perintah diterima. Backend menyiapkan clip pendek + kompilasi maksimal 5 menit...",
            )
            self.start_job(chat_id)
        elif data == "settings:top":
            show_panel(
                "Pilih target jumlah clip",
                keyboard(
                    [
                        [button("Otomatis", "set:top:auto"), button("3", "set:top:3"), button("5", "set:top:5")],
                        [button("8", "set:top:8"), button("10", "set:top:10"), button("12", "set:top:12")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:mode":
            show_panel(
                "Output Telegram dibuat otomatis dalam satu tahap.",
                keyboard(
                    [
                        [button("✅ Clip Pendek + Kompilasi Maks. 5 Menit", "set:mode:short")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:output":
            show_panel(
                "Output otomatis\n\n"
                "• Beberapa clip pendek terbaik\n"
                "• Satu kompilasi vertikal\n"
                "• Durasi kompilasi tidak lebih dari 5 menit\n"
                "• Semua dibuat dalam satu proses",
                keyboard([[button("⬅️ Kembali", "menu:settings")]]),
            )
        elif data == "settings:duration":
            show_panel(
                "Pilih rentang durasi setiap clip",
                keyboard(
                    [
                        [button("15–60 detik", "set:duration:15:60")],
                        [button("30–75 detik (bagian highlight)", "set:duration:30:75")],
                        [button("35–180 detik", "set:duration:35:180")],
                        [button("60–180 detik", "set:duration:60:180")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:quality":
            show_panel(
                "Pilih kualitas output",
                keyboard(
                    [
                        [button("Standar", "set:quality:standard")],
                        [button("Jernih", "set:quality:high")],
                        [button("Maksimal", "set:quality:max")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:crop":
            show_panel(
                "Pilih mode crop",
                keyboard(
                    [
                        [button("Center", "set:crop:center")],
                        [button("Follow Person", "set:crop:person")],
                        [button("Streamer", "set:crop:streamer")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:caption":
            show_panel(
                "Atur tampilan caption",
                keyboard(
                    [
                        [button("Atas", "set:position:upper"), button("Tengah", "set:position:center"), button("Bawah", "set:position:bottom")],
                        [button("7px", "set:fontsize:7"), button("9px", "set:fontsize:9"), button("10px", "set:fontsize:10"), button("12px", "set:fontsize:12")],
                        [button("14px", "set:fontsize:14"), button("18px", "set:fontsize:18"), button("20px", "set:fontsize:20"), button("24px", "set:fontsize:24")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif self.apply_setting_callback(data):
            self.show_settings(chat_id, message_id if isinstance(message_id, int) else None)
        elif data.startswith("view:") or data.startswith("refresh:"):
            job_id = data.split(":", 1)[1]
            try:
                job = self.backend.get_job(job_id)
                if isinstance(message_id, int) and data.startswith("refresh:"):
                    self.show_job(chat_id, job, message_id)
                else:
                    self.show_job(chat_id, job)
            except ServiceError as exc:
                self.send_message(chat_id, f"Gagal membuka job: {exc}", main_menu_keyboard())
        elif data.startswith("cancelask:"):
            self.request_cancel(chat_id, data.split(":", 1)[1])
        elif data.startswith("cancel:"):
            job_id = data.split(":", 1)[1]
            try:
                self.send_message(chat_id, "Mengirim permintaan pembatalan ke backend...")
                self.backend.cancel_job(job_id)
                self.send_message(chat_id, "Permintaan pembatalan sudah dikirim.", main_menu_keyboard())
            except ServiceError as exc:
                self.send_message(chat_id, f"Gagal membatalkan job: {exc}", main_menu_keyboard())
        elif data.startswith("deleteask:"):
            self.request_delete_job(chat_id, data.split(":", 1)[1])
        elif data.startswith("deletejob:"):
            self.delete_job_from_bot(chat_id, data.split(":", 1)[1])
        elif data == "deletefailedask":
            self.request_delete_failed_jobs(chat_id)
        elif data == "deletefailed":
            self.delete_failed_jobs_from_bot(chat_id)
        elif data.startswith("deliver:"):
            job_id = data.split(":", 1)[1]
            try:
                self.send_message(chat_id, "Permintaan kirim ulang hasil diterima. Bot mulai menyiapkan file...")
                job = self.backend.get_job(job_id)
                if job.get("status") != "completed":
                    self.send_message(chat_id, "Hasil belum siap dikirim.", self.job_keyboard(job))
                else:
                    self.deliver_job(chat_id, job, force=True)
            except ServiceError as exc:
                self.send_message(chat_id, f"Pengiriman hasil gagal: {exc}", main_menu_keyboard())
        elif data.startswith("ytup:"):
            parts = data.split(":")
            if len(parts) == 3 and parts[2].isdigit():
                self.send_message(chat_id, "Perintah upload clip ke YouTube diterima. Bot menyiapkan session Playwright...")
                self.start_youtube_upload_for_clip(chat_id, parts[1], int(parts[2]), preflight=True)
            else:
                self.send_message(chat_id, "Data upload YouTube tidak valid.", main_menu_keyboard())
        elif data.startswith("ytall:"):
            self.send_message(chat_id, "Perintah upload 3 terbaik ke YouTube diterima. Bot menyiapkan session Playwright...")
            self.start_youtube_upload_all(chat_id, data.split(":", 1)[1], preflight=True)
        elif data.startswith("ytretry:"):
            upload_id = data.split(":", 1)[1]
            try:
                self.send_message(chat_id, "Retry upload diterima. Membaca data upload lama...")
                upload = self.backend.get_youtube_upload(upload_id)
            except ServiceError as exc:
                self.send_message(chat_id, f"Gagal membuka data upload lama: {exc}", main_menu_keyboard())
                return
            source_job_id = upload.get("source_job_id")
            clip_url = upload.get("clip_url")
            if isinstance(source_job_id, str) and isinstance(clip_url, str):
                self.start_youtube_upload_for_url(chat_id, source_job_id, clip_url, preflight=True)
            else:
                self.send_message(chat_id, "Data retry upload YouTube tidak valid.", main_menu_keyboard())
        elif data == "ytsync":
            self.sync_youtube_cdp_session(chat_id, reason="manual")
        elif data == "ytcdp":
            self.run_youtube_cdp_launcher(chat_id)
        elif data == "ytoncelogin":
            self.setup_youtube_one_time_login_from_bot(chat_id)
        elif data == "ytcookies":
            self.import_youtube_cdp_cookies_from_bot(chat_id)
        elif data == "ytnocdp":
            self.enable_youtube_direct_profile_mode(chat_id)
        elif data == "ytprofile":
            self.sync_youtube_cdp_from_profile(chat_id)
        elif data == "ytsession":
            self.capture_youtube_session_from_bot(chat_id)
        elif data == "ytcdpstop":
            try:
                self.send_message(chat_id, "Mengirim perintah stop Chrome CDP ke backend...")
                result = self.backend.stop_youtube_cdp()
                self.send_message(
                    chat_id,
                    f"{result.get('message') or 'Perintah stop CDP selesai.'}\n\n"
                    f"Remote debugging aktif: {'ya' if result.get('cdp_ready') else 'tidak'}",
                    self.youtube_control_keyboard(),
                )
            except ServiceError as exc:
                self.send_message(chat_id, f"Gagal stop Chrome CDP: {exc}", self.youtube_control_keyboard())
        else:
            self.send_message(chat_id, f"Fungsi tombol belum dikenali: {data or '-'}", main_menu_keyboard())

    def handle_update(self, update: dict[str, Any]) -> None:
        try:
            if isinstance(update.get("callback_query"), dict):
                self.handle_callback(update["callback_query"])
            elif isinstance(update.get("message"), dict):
                self.handle_message(update["message"])
        except Exception as exc:
            print(f"Gagal menangani update Telegram: {type(exc).__name__}: {exc}", flush=True)
            chat_id: int | None = None
            if isinstance(update.get("message"), dict):
                raw_chat_id = update["message"].get("chat", {}).get("id")
                chat_id = raw_chat_id if isinstance(raw_chat_id, int) else None
            elif isinstance(update.get("callback_query"), dict):
                raw_chat_id = update["callback_query"].get("message", {}).get("chat", {}).get("id")
                chat_id = raw_chat_id if isinstance(raw_chat_id, int) else None
            if chat_id:
                try:
                    self.send_message(
                        chat_id,
                        f"Fungsi Telegram gagal dijalankan: {type(exc).__name__}: {exc}",
                        main_menu_keyboard(),
                    )
                except Exception:
                    pass

    def wait_for_backend(self) -> None:
        while self.running:
            try:
                self.backend.health()
                return
            except ServiceError as exc:
                print(f"Menunggu backend ClipForge: {exc}", flush=True)
                time.sleep(3)

    def monitor_battery(self, *, force: bool = False) -> None:
        if not BATTERY_ALERT_ENABLED or not BATTERY_ALERT_LEVELS:
            return
        now = time.monotonic()
        if not force and now - self.last_battery_check < BATTERY_CHECK_INTERVAL:
            return
        self.last_battery_check = now
        battery = read_battery_status()
        self.last_battery_status = battery
        if battery is None:
            return

        percent = int(battery["percent"])
        previous = {
            level
            for level in self.state.get("battery_alerted_levels", [])
            if level in BATTERY_ALERT_LEVELS
        }
        alerted = {level for level in previous if percent <= level}
        should_alert = str(battery.get("status") or "").lower() not in {"charging", "full"}
        crossed = [
            level
            for level in BATTERY_ALERT_LEVELS
            if percent <= level and level not in alerted
        ]
        if should_alert and crossed:
            severity = "KRITIS" if percent <= min(BATTERY_ALERT_LEVELS) else "RENDAH"
            self.send_message(
                self.owner_id,
                f"⚠️ BATERAI {severity}\n\n"
                + battery_status_text(battery)
                + "\n\nSegera hubungkan charger.",
                main_menu_keyboard(),
            )
            alerted.update(crossed)
        if alerted != previous:
            self.state["battery_alerted_levels"] = sorted(alerted, reverse=True)
            self.persist()

    def setup(self) -> None:
        while self.running:
            try:
                self.telegram.call("deleteWebhook", {"drop_pending_updates": False}, timeout=15)
                self.telegram.call(
                    "setMyCommands",
                    {
                        "commands": [
                            {"command": "clip", "description": "Mulai clipping dari link YouTube"},
                            {
                                "command": "getvideosviral",
                                "description": f"Cari {VIRAL_CC_VIDEO_COUNT} video viral CC dakwah/podcast",
                            },
                            {"command": "status", "description": "Lihat proses yang sedang berjalan"},
                            {"command": "battery", "description": "Cek sisa baterai device"},
                            {"command": "settings", "description": "Atur hasil clipping"},
                            {"command": "history", "description": "Lihat riwayat dan kirim ulang hasil"},
                            {"command": "hapusgagal", "description": "Hapus job gagal/dibatalkan"},
                            {"command": "youtube", "description": "Cek status uploader YouTube"},
                            {"command": "loginsekali", "description": "Simpan session Playwright YouTube"},
                            {"command": "nocdp", "description": "Aktifkan upload tanpa CDP"},
                            {"command": "cdp", "description": "Recovery Chrome CDP YouTube"},
                            {"command": "cookies", "description": "Ambil cookies dari Chrome CDP login"},
                            {"command": "profilelogin", "description": "Ambil session dari profile login"},
                            {"command": "syncsession", "description": "Sync/repair session YouTube CDP"},
                            {"command": "capturesession", "description": "Merge session browser YouTube"},
                            {"command": "debug", "description": "Diagnosis koneksi bot dan backend"},
                            {"command": "ping", "description": "Cek bot aktif"},
                            {"command": "cancel", "description": "Batalkan proses aktif"},
                            {"command": "menu", "description": "Buka menu utama"},
                        ]
                    },
                    timeout=15,
                )
                identity = self.telegram.call("getMe", timeout=15)
                username = identity.get("username", "unknown") if isinstance(identity, dict) else "unknown"
                print(f"Telegram bot @{username} aktif untuk owner {self.owner_id}.", flush=True)
                return
            except ServiceError as exc:
                print(f"Setup Telegram tertunda: {exc}", flush=True)
                time.sleep(5)

    def run(self) -> None:
        self.setup()
        try:
            self.backend.health()
        except ServiceError as exc:
            print(f"Backend ClipForge belum siap, bot tetap menerima command: {exc}", flush=True)
        while self.running:
            try:
                updates = self.telegram.call(
                    "getUpdates",
                    {
                        "offset": self.state["update_offset"],
                        "timeout": POLL_TIMEOUT_SECONDS,
                        "allowed_updates": ["message", "callback_query"],
                    },
                    timeout=POLL_TIMEOUT_SECONDS + 10,
                )
                for update in updates if isinstance(updates, list) else []:
                    if not isinstance(update, dict):
                        continue
                    try:
                        self.handle_update(update)
                    except Exception as exc:
                        print(f"Gagal menangani update Telegram: {exc}", flush=True)
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self.state["update_offset"] = update_id + 1
                        self.persist()
                self.monitor_jobs()
                self.monitor_youtube_uploads()
                self.monitor_battery()
            except ServiceError as exc:
                print(f"Koneksi Telegram tertunda: {exc}", flush=True)
                time.sleep(3)
            except Exception as exc:
                print(f"Loop Telegram error: {type(exc).__name__}: {exc}", flush=True)
                time.sleep(3)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    owner_raw = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN belum diatur")
    try:
        owner_id = int(owner_raw)
    except ValueError as exc:
        raise SystemExit("TELEGRAM_OWNER_ID harus berupa angka") from exc

    bot = ClipForgeTelegramBot(token, owner_id)

    def stop(_signum: int, _frame: object) -> None:
        bot.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    bot.run()


if __name__ == "__main__":
    main()
