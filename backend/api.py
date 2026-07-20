from __future__ import annotations

import hashlib
import json
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from math import ceil, log10
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlencode, unquote, urlparse
from urllib.error import HTTPError, URLError
import urllib.request

import imageio_ffmpeg
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from yt_dlp import YoutubeDL

from llm import AIConfig, chat_completion, extract_json


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR = BASE_DIR / "uploads"
_configured_jobs_path = Path(os.environ.get("JOBS_PATH", BASE_DIR / "jobs.json"))
JOBS_PATH = _configured_jobs_path / "jobs.json" if _configured_jobs_path.is_dir() else _configured_jobs_path
_configured_youtube_uploads_path = Path(os.environ.get("YOUTUBE_UPLOADS_PATH", BASE_DIR / "data" / "youtube_uploads.json"))
YOUTUBE_UPLOADS_PATH = (
    _configured_youtube_uploads_path / "youtube_uploads.json"
    if _configured_youtube_uploads_path.is_dir()
    else _configured_youtube_uploads_path
)
PROCESSED_SOURCE_HISTORY_PATH = Path(
    os.environ.get(
        "PROCESSED_SOURCE_HISTORY_PATH",
        BASE_DIR / "data" / "processed_source_urls.json",
    )
)
YOUTUBE_PLAYWRIGHT_STATE = Path(os.environ.get("YOUTUBE_PLAYWRIGHT_STATE", BASE_DIR / "data" / "youtube_storage_state.json"))
YOUTUBE_CHROMIUM_USER_DATA_DIR = os.environ.get("YOUTUBE_CHROMIUM_USER_DATA_DIR", "").strip()
if not YOUTUBE_CHROMIUM_USER_DATA_DIR and os.environ.get("IN_DOCKER", "").strip().lower() in {"1", "true", "yes", "on"}:
    YOUTUBE_CHROMIUM_USER_DATA_DIR = "/app/data/youtube-playwright-profile"
YOUTUBE_CHROMIUM_PROFILE_DIRECTORY = os.environ.get("YOUTUBE_CHROMIUM_PROFILE_DIRECTORY", "").strip()
YOUTUBE_LOGIN_PROFILE_DIR = os.environ.get(
    "YOUTUBE_LOGIN_PROFILE_DIR",
    YOUTUBE_CHROMIUM_USER_DATA_DIR or str(BASE_DIR / "data" / "youtube-playwright-profile"),
).strip()
YOUTUBE_LOGIN_PROFILE_DIRECTORY = os.environ.get(
    "YOUTUBE_LOGIN_PROFILE_DIRECTORY",
    YOUTUBE_CHROMIUM_PROFILE_DIRECTORY or "Default",
).strip()
YOUTUBE_CDP_URL = os.environ.get("YOUTUBE_CDP_URL", "http://127.0.0.1:9222").strip()
YOUTUBE_CDP_STAGING_DIR = Path(os.environ.get("YOUTUBE_CDP_STAGING_DIR", BASE_DIR / "data" / "youtube_cdp_uploads"))
DEFAULT_YOUTUBE_MAX_UPLOAD_MB = 45
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
SECONDS_PER_TARGET_CLIP = 360
MIN_AUTO_CLIPS = 2
MAX_AUTO_CLIPS = 8
MAX_REQUESTED_CLIPS = 12
FULL_ANALYSIS_LIMIT_SECONDS = 30 * 60
LONG_VIDEO_ANALYSIS_RATIO = 0.35
MAX_AUTO_ANALYSIS_SECONDS = 20 * 60
CLIP_BUDGET_RATIO = 0.8
FRESH_VIRAL_MAX_AGE_DAYS = 30
MAX_VIRAL_FALLBACK_AGE_DAYS = 365
CANCEL_GRACE_SECONDS = 8
LOCAL_LLM_PRESETS = [
    {"label": "Ollama", "base_url": "http://localhost:11434/v1"},
    {"label": "LM Studio", "base_url": "http://localhost:1234/v1"},
    {"label": "Jan", "base_url": "http://localhost:1337/v1"},
    {"label": "LocalAI", "base_url": "http://localhost:8080/v1"},
    {"label": "OpenAI-compatible", "base_url": "http://localhost:20128/v1"},
]
DEFAULT_AI_BASE_URL = os.environ.get("DEFAULT_AI_BASE_URL", "http://localhost:11434/v1")
DEFAULT_AI_MODEL = os.environ.get("DEFAULT_AI_MODEL", "")
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
CLI_USER_ERROR_PREFIX = "USER_ERROR:"
YOUTUBE_UPLOAD_ERROR_PREFIX = "USER_ERROR:"
YOUTUBE_VIDEO_URL_PREFIX = "VIDEO_URL:"
DEFAULT_YOUTUBE_PLAYLIST = "Islam"
DEFAULT_YOUTUBE_TARGET_CHANNEL = "ryuundyofficial"
DEFAULT_YOUTUBE_TARGET_EMAIL = "fendysketsa@gmail.com"
DEFAULT_YOUTUBE_TARGET_CHANNEL_ID = "UCAOZF9Qzj6DYoXKtLnP4UUQ"
DEFAULT_YOUTUBE_AUTO_UPLOAD_COUNT = 3
DEFAULT_YOUTUBE_AI_FALLBACK_MODELS = ["llama3.2-id:latest", "llama3:latest"]
ROOT_DIR = BASE_DIR.parent
YOUTUBE_CDP_REFRESH_LOG = Path(
    os.environ.get("YOUTUBE_CDP_REFRESH_LOG", "/tmp/clipforge-youtube-chrome-launcher.log")
)


def bounded_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


YOUTUBE_CDP_REFRESH_STARTUP_GRACE_SECONDS = bounded_float_env(
    "YOUTUBE_CDP_REFRESH_STARTUP_GRACE_SECONDS",
    1.5,
    0.0,
    5.0,
)
YOUTUBE_CDP_REFRESH_READY_TIMEOUT_SECONDS = bounded_float_env(
    "YOUTUBE_CDP_REFRESH_READY_TIMEOUT_SECONDS",
    30.0,
    1.0,
    120.0,
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name: str) -> list[str]:
    return [item.strip().lstrip("#") for item in os.environ.get(name, "").split(",") if item.strip()]


def env_search_queries(*names: str) -> list[str]:
    for name in names:
        raw_value = os.environ.get(name, "")
        if raw_value.strip():
            return [
                item.strip().lstrip("#")
                for item in re.split(r"[,|]", raw_value)
                if item.strip()
            ]
    return []


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def youtube_auto_upload_count() -> int:
    return max(1, min(MAX_REQUESTED_CLIPS, env_int("YOUTUBE_AUTO_UPLOAD_COUNT", DEFAULT_YOUTUBE_AUTO_UPLOAD_COUNT)))


class ClipJobRequest(BaseModel):
    url: str = ""
    source_file: str = ""
    top: int | None = Field(default=None, ge=1, le=50)
    min_duration: float = Field(default=35, ge=5, le=600)
    max_duration: float = Field(default=180, ge=10, le=600)
    clip_mode: Literal["short", "highlight_5m"] = "short"
    compilation_target_seconds: float = Field(default=300, ge=240, le=360)
    model: str = "Systran/faster-whisper-small"
    language: str = "id"
    analyze_seconds: float | None = Field(default=None, ge=10, le=7200)
    video_quality: Literal["standard", "high", "max"] = "high"
    burn_subtitles: bool = True
    enhanced_edit: bool = True
    remove_running_text: bool = True
    crop_mode: Literal["center", "person", "streamer"] = "center"
    cam_corner: Literal["auto", "br", "bl", "tr", "tl"] = "auto"
    caption_font_size: int = Field(default=10, ge=6, le=120)
    caption_position: Literal["upper", "center", "bottom"] = "upper"
    caption_color: str = "#FFFFFF"
    caption_font: Literal[
        "DejaVu Sans", "DejaVu Serif", "Liberation Sans", "Liberation Serif", "Noto Sans"
    ] = "DejaVu Sans"
    caption_outline: float = Field(default=1.5, ge=0, le=8)
    caption_outline_color: str = "#000000"
    required_hashtags: list[str] = Field(default_factory=list)
    require_creative_commons: bool = True
    auto_upload_youtube: bool = False
    ai_enabled: bool = True
    ai_base_url: str = DEFAULT_AI_BASE_URL
    ai_model: str = DEFAULT_AI_MODEL
    ai_api_key: str = ""

    @field_validator("caption_color", "caption_outline_color")
    @classmethod
    def _validate_hex_color(cls, value: str) -> str:
        candidate = value.strip()
        if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", candidate):
            raise ValueError("color must be a hex value like #FFFFFF")
        return candidate.upper()


class ClipCandidate(BaseModel):
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
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvement_ideas: list[str] = Field(default_factory=list)
    applied_edits: list[str] = Field(default_factory=list)


class ClipFile(BaseModel):
    name: str
    url: str
    size_bytes: int
    title: str | None = None
    thumbnail_url: str | None = None
    thumbnail_prompt: str | None = None
    social_caption: str | None = None
    fyp_score: int | None = None
    fyp_label: str | None = None
    fyp_reason: str | None = None
    hook: str | None = None
    pov: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvement_ideas: list[str] = Field(default_factory=list)
    applied_edits: list[str] = Field(default_factory=list)
    output_resolution: str | None = None
    is_correct: bool = False


class ClipJob(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    request: ClipJobRequest
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_uploader: str | None = None
    logs: list[str] = []
    clips: list[ClipFile] = []
    candidates: list[ClipCandidate] = []
    error: str | None = None


class ClipStatusUpdate(BaseModel):
    url: str
    is_correct: bool


class ClipSelectionDeleteRequest(BaseModel):
    urls: list[str]


class ClipDeleteResponse(BaseModel):
    job: ClipJob | None = None
    removed_job: bool = False
    removed_clips: int = 0


class YouTubeConfig(BaseModel):
    enabled: bool
    playwright_installed: bool
    auth_state_exists: bool
    auth_state_path: str
    auth_status_message: str | None = None
    upload_uses_cdp: bool = False
    direct_profile_upload: bool = False
    chromium_profile_ready: bool = False
    chromium_profile_path: str = ""
    default_visibility: Literal["private", "unlisted", "public"]
    default_made_for_kids: bool
    default_tags: list[str]
    default_playlist: str
    target_channel: str
    target_email: str
    auto_upload_count: int
    active_upload_id: str | None = None


class YouTubeUploadRequest(BaseModel):
    clip_url: str
    title: str = ""
    description: str = ""
    thumbnail_url: str | None = None
    visibility: Literal["private", "unlisted", "public"] = Field(
        default_factory=lambda: os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "public")
        if os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "public") in {"private", "unlisted", "public"}
        else "public"
    )
    made_for_kids: bool = Field(default_factory=lambda: env_bool("YOUTUBE_MADE_FOR_KIDS", False))
    tags: list[str] = Field(default_factory=lambda: env_csv("YOUTUBE_DEFAULT_TAGS"))
    playlist: str = Field(
        default_factory=lambda: os.environ.get("YOUTUBE_DEFAULT_PLAYLIST", DEFAULT_YOUTUBE_PLAYLIST)
    )
    target_channel: str = Field(
        default_factory=lambda: os.environ.get("YOUTUBE_TARGET_CHANNEL", DEFAULT_YOUTUBE_TARGET_CHANNEL)
    )
    dry_run: bool = Field(default_factory=lambda: env_bool("YOUTUBE_DRY_RUN", False))

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()[:100]

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str) -> str:
        return value.strip()[:5000]

    @field_validator("playlist", "target_channel")
    @classmethod
    def _clean_short_text(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()[:100]

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        tags: list[str] = []
        for tag in value:
            clean = re.sub(r"\s+", " ", tag.strip().lstrip("#"))[:30]
            if clean and clean.lower() not in {item.lower() for item in tags}:
                tags.append(clean)
        return tags[:15]


class YouTubeBatchUploadRequest(BaseModel):
    clip_urls: list[str] = Field(default_factory=list)
    visibility: Literal["private", "unlisted", "public"] = Field(
        default_factory=lambda: os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "public")
        if os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "public") in {"private", "unlisted", "public"}
        else "public"
    )
    made_for_kids: bool = Field(default_factory=lambda: env_bool("YOUTUBE_MADE_FOR_KIDS", False))
    tags: list[str] = Field(default_factory=lambda: env_csv("YOUTUBE_DEFAULT_TAGS"))
    playlist: str = Field(
        default_factory=lambda: os.environ.get("YOUTUBE_DEFAULT_PLAYLIST", DEFAULT_YOUTUBE_PLAYLIST)
    )
    target_channel: str = Field(
        default_factory=lambda: os.environ.get("YOUTUBE_TARGET_CHANNEL", DEFAULT_YOUTUBE_TARGET_CHANNEL)
    )
    best_count: int = Field(default_factory=youtube_auto_upload_count, ge=1, le=MAX_REQUESTED_CLIPS)
    dry_run: bool = Field(default_factory=lambda: env_bool("YOUTUBE_DRY_RUN", False))

    @field_validator("playlist", "target_channel")
    @classmethod
    def _clean_short_text(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()[:100]


class YouTubeUploadJob(BaseModel):
    id: str
    source_job_id: str
    clip_url: str
    clip_name: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    title: str
    description: str = ""
    thumbnail_url: str | None = None
    visibility: Literal["private", "unlisted", "public"] = "private"
    made_for_kids: bool = False
    tags: list[str] = Field(default_factory=list)
    playlist: str = ""
    target_channel: str = ""
    dry_run: bool = False
    video_url: str | None = None
    logs: list[str] = []
    error: str | None = None


class YouTubeLoginStatus(BaseModel):
    active: bool
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    logs: list[str] = Field(default_factory=list)


class YouTubeCdpRefreshStatus(BaseModel):
    started: bool
    cdp_ready: bool
    started_at: str
    command: list[str]
    log_path: str
    message: str
    logs: list[str] = Field(default_factory=list)


class YouTubeCdpRepairStatus(BaseModel):
    ok: bool
    cdp_ready: bool
    session_ready: bool
    hydrated: bool = False
    profile_sync_requested: bool = False
    source_profile_ready: bool = False
    source_profile_path: str = ""
    cookies_imported: bool = False
    cookie_count: int = 0
    youtube_cookie_count: int = 0
    storage_state_path: str = ""
    login_required: bool = False
    started_at: str
    message: str
    refresh: YouTubeCdpRefreshStatus | None = None
    error: str | None = None
    logs: list[str] = Field(default_factory=list)


class YouTubeLiveChromeRequest(BaseModel):
    cdp_url: str = "http://127.0.0.1:9333"

    @field_validator("cdp_url")
    @classmethod
    def validate_cdp_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("CDP URL harus memakai Chrome lokal http://127.0.0.1:<port>")
        if parsed.port is None or not 1024 <= parsed.port <= 65535:
            raise ValueError("Port CDP tidak valid")
        return f"http://127.0.0.1:{parsed.port}"


BROAD_VIRAL_SEARCH_QUERIES = [
    "podcast indonesia terbaru",
    "podcast islam indonesia",
    "podcast inspiratif indonesia",
    "podcast kehidupan indonesia",
    "obrolan tokoh indonesia",
    "wawancara inspiratif indonesia",
    "kajian islam terbaru",
    "ceramah terbaru indonesia",
    "tausiyah singkat indonesia",
    "khutbah jumat indonesia",
    "nasihat kehidupan islam",
    "kisah inspiratif muslim",
    "kisah hijrah indonesia",
    "kisah mualaf indonesia",
    "kisah nabi dan sahabat",
    "motivasi islami",
    "rezeki dan sedekah",
    "doa dan amalan harian",
    "keluarga parenting islam",
    "rumah tangga islami",
    "pendidikan anak muslim",
    "kesehatan mental islam",
    "psikologi islam indonesia",
    "bisnis halal",
    "usaha umkm muslim",
    "keuangan syariah indonesia",
    "hijrah indonesia",
    "pemuda muslim indonesia",
    "wanita muslimah indonesia",
    "quran dan hadits",
    "sejarah islam indonesia",
    "dakwah indonesia",
    "ngaji indonesia terbaru",
    "tanya jawab islam",
    "kajian ustadz indonesia",
    "inspirasi kehidupan indonesia",
    "self improvement indonesia",
    "pelajaran hidup podcast",
]

MYSTERY_ISLAMIC_SEARCH_QUERIES = [
    "misteri dalam islam",
    "kisah misteri islami",
    "mitos dan fakta menurut islam",
    "jin dalam islam",
    "alam gaib menurut islam",
    "kisah nyata horor islami",
    "pengalaman ruqyah nyata",
    "kisah ruqyah indonesia",
    "gangguan jin dan doa",
    "kisah pesantren misteri",
    "misteri sejarah islam",
    "tanda akhir zaman",
    "kisah akhirat dan kematian",
    "renungan kematian islam",
    "azab dan hikmah kehidupan",
    "misteri penciptaan dalam islam",
    "fakta unik sejarah islam",
    "kisah ulama penuh hikmah",
    "legenda nusantara menurut islam",
    "mitos jawa menurut islam",
    "cerita horor indonesia",
    "podcast horor indonesia",
    "kisah mistis indonesia",
    "pengalaman gaib nyata",
    "urban legend indonesia",
    "misteri nusantara",
    "fakta menyeramkan indonesia",
    "misteri gunung indonesia",
    "misteri laut indonesia",
    "sejarah kelam indonesia",
    "kisah nyata penuh misteri",
    "cerita rakyat misteri indonesia",
    "tempat angker dan sejarah indonesia",
    "fenomena aneh indonesia",
    "kisah survival menyeramkan",
    "podcast kisah nyata indonesia",
]

HORROR_PODCAST_SEARCH_QUERIES = [
    "podcast horor indonesia",
    "podcast cerita seram indonesia",
    "cerita seram podcast indonesia",
    "podcast horor kisah nyata",
    "podcast pengalaman mistis",
    "podcast misteri nusantara",
    "podcast urban legend indonesia",
    "podcast paranormal indonesia",
    "podcast investigasi tempat angker",
    "podcast cerita hantu indonesia",
    "cerita horor kisah nyata indonesia",
    "kisah nyata pengalaman gaib",
    "cerita seram narasi indonesia",
    "cerita horor malam indonesia",
    "cerita horor pendakian gunung",
    "pengalaman mistis pendakian",
    "cerita seram camping di hutan",
    "kisah horor tersesat di hutan",
    "misteri gunung dan jalur pendakian",
    "cerita horor kos angker",
    "cerita seram rumah kontrakan",
    "kisah rumah kosong angker",
    "cerita horor rumah sakit",
    "cerita seram sekolah angker",
    "cerita horor pabrik terbengkalai",
    "cerita horor hotel angker",
    "cerita seram kantor malam",
    "cerita horor perjalanan malam",
    "cerita mistis sopir malam",
    "cerita horor ojek online",
    "kisah seram penjaga malam",
    "kisah horor desa terpencil",
    "misteri kampung dan desa angker",
    "cerita seram pesantren",
    "kisah mistis makam dan kuburan",
    "cerita horor laut dan nelayan",
    "kisah misteri pantai selatan",
    "cerita misteri danau indonesia",
    "urban legend jawa",
    "urban legend sumatera",
    "urban legend kalimantan",
    "urban legend sulawesi",
    "urban legend bali",
    "legenda hantu nusantara",
    "kisah kuntilanak indonesia",
    "kisah pocong nyata",
    "misteri genderuwo jawa",
    "kisah leak bali",
    "cerita santet dan pesugihan",
    "cerita tumbal dan ritual misteri",
    "pengalaman kerasukan nyata",
    "penampakan hantu kisah nyata",
    "fenomena supranatural indonesia",
    "mitos horor dan fakta",
    "misteri sejarah tempat angker",
    "cerita rakyat seram indonesia",
    "audio drama horor indonesia",
    "radio cerita horor indonesia",
    "kompilasi cerita seram indonesia",
]


def merge_unique_queries(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            clean = re.sub(r"\s+", " ", item).strip()
            key = clean.casefold()
            if clean and key not in seen:
                merged.append(clean)
                seen.add(key)
    return merged


def prioritized_viral_queries(configured: list[str]) -> list[str]:
    # Keep the user's strongest custom themes first, then deliberately diversify
    # the first 12 API calls with Islamic mystery and horror-podcast formats.
    return merge_unique_queries(
        configured[:4],
        MYSTERY_ISLAMIC_SEARCH_QUERIES[:4],
        HORROR_PODCAST_SEARCH_QUERIES[:12],
        configured[4:],
        MYSTERY_ISLAMIC_SEARCH_QUERIES[4:],
        HORROR_PODCAST_SEARCH_QUERIES[12:],
        BROAD_VIRAL_SEARCH_QUERIES,
    )


def default_auto_viral_queries() -> list[str]:
    configured = env_search_queries("AUTO_VIRAL_SEARCH_QUERIES", "AUTOPILOT_KEYWORDS")
    return prioritized_viral_queries(configured)


def default_viral_video_search_queries() -> list[str]:
    configured = env_search_queries("VIRAL_CC_SEARCH_QUERIES", "AUTOPILOT_KEYWORDS")
    return prioritized_viral_queries(configured)


class AutoViralRequest(BaseModel):
    queries: list[str] = Field(default_factory=default_auto_viral_queries)
    video_count: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_VIDEO_COUNT", 5), ge=1, le=7)
    clips_per_video: int = Field(default_factory=youtube_auto_upload_count, ge=1, le=5)
    search_limit_per_query: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_SEARCH_LIMIT", 25), ge=3, le=50)
    min_source_duration: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_MIN_SOURCE_SECONDS", 60), ge=30, le=7200)
    max_source_duration: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_MAX_SOURCE_SECONDS", 7200), ge=60, le=14400)
    min_views: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_MIN_VIEWS", 1000), ge=0)
    max_age_days: int = Field(default=FRESH_VIRAL_MAX_AGE_DAYS, ge=1, le=MAX_VIRAL_FALLBACK_AGE_DAYS)
    top: int | None = Field(default=None, ge=1, le=MAX_REQUESTED_CLIPS)
    min_duration: float = Field(default=35, ge=5, le=600)
    max_duration: float = Field(default=180, ge=10, le=600)
    video_quality: Literal["standard", "high", "max"] = "high"
    crop_mode: Literal["center", "person", "streamer"] = "person"
    burn_subtitles: bool = True
    ai_enabled: bool = True
    ai_base_url: str = DEFAULT_AI_BASE_URL
    ai_model: str = DEFAULT_AI_MODEL
    ai_api_key: str = ""

    @field_validator("queries")
    @classmethod
    def _clean_queries(cls, value: list[str]) -> list[str]:
        cleaned = [re.sub(r"\s+", " ", item).strip() for item in value if item.strip()]
        return prioritized_viral_queries(cleaned)[:80]


class AutoViralRun(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: str
    updated_at: str
    finished_at: str | None = None
    request: AutoViralRequest
    message: str = ""
    selected_sources: list[dict[str, Any]] = Field(default_factory=list)
    processed: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


class ViralVideoSearchRequest(BaseModel):
    queries: list[str] = Field(default_factory=default_viral_video_search_queries)
    video_count: int = Field(default_factory=lambda: env_int("VIRAL_CC_VIDEO_COUNT", 5), ge=1, le=7)
    search_limit_per_query: int = Field(default_factory=lambda: env_int("VIRAL_CC_SEARCH_LIMIT", 25), ge=3, le=50)
    min_source_duration: int = Field(default=60, ge=30, le=7200)
    max_source_duration: int = Field(
        default_factory=lambda: env_int("VIRAL_CC_MAX_SOURCE_SECONDS", 7200),
        ge=60,
        le=14400,
    )
    min_views: int = Field(default_factory=lambda: env_int("VIRAL_CC_MIN_VIEWS", 1000), ge=0)
    max_age_days: int = Field(default=FRESH_VIRAL_MAX_AGE_DAYS, ge=1, le=MAX_VIRAL_FALLBACK_AGE_DAYS)
    max_metadata_checks: int = Field(default_factory=lambda: env_int("VIRAL_CC_MAX_METADATA_CHECKS", 200), ge=3, le=500)
    exclude_urls: list[str] = Field(default_factory=list)

    @field_validator("queries")
    @classmethod
    def _clean_queries(cls, value: list[str]) -> list[str]:
        cleaned = [re.sub(r"\s+", " ", item).strip() for item in value if item.strip()]
        return prioritized_viral_queries(cleaned)[:80]

    @field_validator("exclude_urls")
    @classmethod
    def _clean_exclude_urls(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = normalize_youtube_video_url(str(item))
            if normalized and normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)
        return cleaned[:5000]


app = FastAPI(title="Fendy Clipper API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
YOUTUBE_UPLOADS_PATH.parent.mkdir(parents=True, exist_ok=True)
PROCESSED_SOURCE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
YOUTUBE_PLAYWRIGHT_STATE.parent.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")


def resolve_upload_path(token: str) -> Path | None:
    # token is just the stored file name; keep it confined to UPLOADS_DIR.
    name = Path(token).name
    if not name:
        return None
    candidate = (UPLOADS_DIR / name).resolve()
    root = UPLOADS_DIR.resolve()
    if root != candidate.parent or not candidate.is_file():
        return None
    return candidate

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed_seconds(started_at: float) -> float:
    return round(max(0.0, time.perf_counter() - started_at), 2)


def duration_between_iso(started_at: str | None, finished_at: str) -> float:
    if not started_at:
        return 0.0
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0.0
    return round(max(0.0, (finished - started).total_seconds()), 2)


def load_jobs() -> dict[str, ClipJob]:
    if not JOBS_PATH.exists() or JOBS_PATH.is_dir():
        return {}

    try:
        raw_payload = JOBS_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not raw_payload:
        return {}

    payload = json.loads(raw_payload)
    loaded: dict[str, ClipJob] = {}
    for item in payload:
        job = ClipJob(**item)
        job = enrich_job_for_display(job)
        if job.status in {"queued", "running"}:
            finished_at = now_iso()
            data = job.model_dump()
            data["status"] = "failed"
            data["updated_at"] = finished_at
            data["finished_at"] = finished_at
            data["duration_seconds"] = duration_between_iso(job.started_at, finished_at)
            data["error"] = "Backend restarted before this job finished"
            job = ClipJob(**data)
            job = enrich_job_for_display(job)
        loaded[job.id] = job
    return loaded


def load_processed_source_history() -> set[str]:
    try:
        payload = json.loads(PROCESSED_SOURCE_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, list):
        return set()
    return {str(item).strip() for item in payload if isinstance(item, str) and item.strip()}


def save_jobs_unlocked() -> None:
    jobs_list = sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)
    payload = [job.model_dump() for job in jobs_list]
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        temp_path = JOBS_PATH.with_suffix(".json.tmp")
        temp_path.write_text(data, encoding="utf-8")
        temp_path.replace(JOBS_PATH)
    except OSError:
        # JOBS_PATH may be a bind-mounted file; atomic rename over it fails
        # with Errno 16. Fall back to in-place write (single writer under lock).
        JOBS_PATH.write_text(data, encoding="utf-8")


def load_youtube_uploads() -> dict[str, YouTubeUploadJob]:
    if not YOUTUBE_UPLOADS_PATH.exists() or YOUTUBE_UPLOADS_PATH.is_dir():
        return {}

    try:
        raw_payload = YOUTUBE_UPLOADS_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not raw_payload:
        return {}

    payload = json.loads(raw_payload)
    loaded: dict[str, YouTubeUploadJob] = {}
    for item in payload:
        upload = YouTubeUploadJob(**item)
        if upload.status == "running":
            finished_at = now_iso()
            upload = upload.model_copy(
                update={
                    "status": "failed",
                    "updated_at": finished_at,
                    "finished_at": finished_at,
                    "duration_seconds": duration_between_iso(upload.started_at, finished_at),
                    "error": "Backend restarted before this YouTube upload finished",
                }
            )
        loaded[upload.id] = upload
    return loaded


def save_youtube_uploads_unlocked() -> None:
    uploads_list = sorted(youtube_uploads.values(), key=lambda item: item.created_at, reverse=True)
    payload = [item.model_dump() for item in uploads_list]
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    YOUTUBE_UPLOADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        temp_path = YOUTUBE_UPLOADS_PATH.with_suffix(".json.tmp")
        temp_path.write_text(data, encoding="utf-8")
        temp_path.replace(YOUTUBE_UPLOADS_PATH)
    except OSError:
        YOUTUBE_UPLOADS_PATH.write_text(data, encoding="utf-8")


def clear_outputs_dir() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    root = OUTPUTS_DIR.resolve()
    removed = 0
    for item in OUTPUTS_DIR.iterdir():
        resolved = item.resolve()
        if root not in resolved.parents:
            raise RuntimeError(f"Refusing to delete path outside outputs: {resolved}")

        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        removed += 1
    return removed


def clear_uploads_dir() -> int:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for item in UPLOADS_DIR.iterdir():
        if item.is_file():
            item.unlink()
            removed += 1
    return removed


def output_path_from_url(url: str | None) -> Path | None:
    if not url or not url.startswith("/outputs/"):
        return None

    relative = unquote(url.removeprefix("/outputs/"))
    candidate = (OUTPUTS_DIR / relative).resolve()
    root = OUTPUTS_DIR.resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def remove_empty_output_parents(path: Path) -> int:
    removed = 0
    root = OUTPUTS_DIR.resolve()
    parent = path.parent
    while parent != root and root in parent.parents:
        try:
            parent.rmdir()
            removed += 1
        except OSError:
            break
        parent = parent.parent
    return removed


def clip_artifact_paths(clip: ClipFile) -> set[Path]:
    paths: set[Path] = set()
    clip_path = output_path_from_url(clip.url)
    if clip_path is None:
        return paths

    paths.add(clip_path)
    paths.add(clip_path.with_name(f"{clip_path.stem}_thumb.jpg"))
    paths.add(clip_path.with_name(f"{clip_path.stem}_thumb.txt"))
    paths.add(clip_path.with_name(f"{clip_path.stem}_caption.txt"))
    if clip.thumbnail_url:
        thumb_path = output_path_from_url(clip.thumbnail_url)
        if thumb_path is not None:
            paths.add(thumb_path)
    return paths


def clip_sidecar_title(clip: ClipFile) -> str | None:
    if clip.title and clip.title.strip():
        return clip.title.strip()

    clip_path = output_path_from_url(clip.url)
    if clip_path is None:
        return None

    json_path = clip_path.with_suffix(".json")
    if not json_path.is_file():
        return None

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    title = payload.get("title") if isinstance(payload, dict) else None
    return title.strip() if isinstance(title, str) and title.strip() else None


def clip_index_from_name(name: str) -> int | None:
    match = re.match(r"clip_(\d+)", name)
    return int(match.group(1)) if match else None


def is_compilation_clip(job: "ClipJob", clip: ClipFile) -> bool:
    return (
        job.request.clip_mode == "highlight_5m"
        or clip.name.lower().startswith("highlight_5menit_")
    )


def enrich_clips_with_candidate_titles(
    clips: list[ClipFile],
    candidates: list[ClipCandidate],
) -> list[ClipFile]:
    titles_by_index = {
        candidate.index: candidate.title.strip()
        for candidate in candidates
        if candidate.title.strip()
    }
    enriched: list[ClipFile] = []
    for clip in clips:
        title = clip_sidecar_title(clip)
        if not title:
            index = clip_index_from_name(clip.name)
            title = titles_by_index.get(index) if index is not None else None
        enriched.append(clip.model_copy(update={"title": title}) if title else clip)
    return enriched


def enrich_job_clip_titles(job: "ClipJob") -> "ClipJob":
    clips = enrich_clips_with_candidate_titles(job.clips, job.candidates)
    if clips == job.clips:
        return job
    return job.model_copy(update={"clips": clips})


def output_work_dirs_for_job(job: "ClipJob") -> list[Path]:
    dirs: list[Path] = []
    for clip in job.clips:
        work_dir = clip_output_work_dir(clip)
        if work_dir is not None and work_dir not in dirs:
            dirs.append(work_dir)
    return dirs


def metadata_for_job(job: "ClipJob") -> dict:
    for work_dir in output_work_dirs_for_job(job):
        metadata_path = work_dir / "metadata.json"
        if not metadata_path.is_file():
            continue
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def enrich_job_source_metadata(job: "ClipJob") -> "ClipJob":
    metadata = metadata_for_job(job)
    title = metadata.get("title")
    url = metadata.get("webpage_url")
    uploader = metadata.get("uploader")

    source_title = title.strip() if isinstance(title, str) and title.strip() else job.source_title
    source_url = url.strip() if isinstance(url, str) and url.strip() else job.source_url
    source_uploader = uploader.strip() if isinstance(uploader, str) and uploader.strip() else job.source_uploader

    if not source_url:
        source_url = job.request.url.strip() or None
    if not source_title and job.request.source_file:
        source_title = Path(job.request.source_file).stem

    updates = {
        "source_title": source_title,
        "source_url": source_url,
        "source_uploader": source_uploader,
    }
    if all(getattr(job, key) == value for key, value in updates.items()):
        return job
    return job.model_copy(update=updates)


def enrich_job_for_display(job: "ClipJob") -> "ClipJob":
    return enrich_job_source_metadata(enrich_job_clip_titles(job))


def clip_output_work_dir(clip: ClipFile) -> Path | None:
    clip_path = output_path_from_url(clip.url)
    if clip_path is None:
        return None

    root = OUTPUTS_DIR.resolve()
    candidate = clip_path.parent.parent if clip_path.parent.name == "clips" else clip_path.parent
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def remove_output_paths(paths: set[Path]) -> int:
    removed = 0

    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        try:
            if path.is_file():
                path.unlink()
                removed += 1
                removed += remove_empty_output_parents(path)
        except OSError:
            pass
    return removed


def cleanup_output_work_dirs(clips: list[ClipFile], protected_dirs: set[Path] | None = None) -> int:
    root = OUTPUTS_DIR.resolve()
    protected = {path.resolve() for path in (protected_dirs or set())}
    removed = 0
    dirs = {
        work_dir.resolve()
        for clip in clips
        if (work_dir := clip_output_work_dir(clip)) is not None
    }

    for work_dir in sorted(dirs, key=lambda item: len(item.parts), reverse=True):
        if work_dir in protected or work_dir == root or root not in work_dir.parents:
            continue
        try:
            if work_dir.is_dir():
                shutil.rmtree(work_dir)
                removed += 1
        except OSError:
            pass
    return removed


def cleanup_clip_files(clip: ClipFile) -> int:
    return remove_output_paths(clip_artifact_paths(clip))


def cleanup_job_files(job: "ClipJob") -> int:
    paths: set[Path] = set()
    for clip in job.clips:
        paths.update(clip_artifact_paths(clip))
    removed = remove_output_paths(paths)
    protected_dirs = {
        work_dir
        for other_job_id, other_job in jobs.items()
        if other_job_id != job.id
        for clip in other_job.clips
        if (work_dir := clip_output_work_dir(clip)) is not None
    }
    removed += cleanup_output_work_dirs(job.clips, protected_dirs)
    return removed


jobs: dict[str, ClipJob] = load_jobs()
processed_source_history: set[str] = load_processed_source_history()
processed_source_history.update(
    str(value)
    for job in jobs.values()
    if job.status == "completed"
    for value in (job.request.url, job.source_url)
    if value
)
youtube_uploads: dict[str, YouTubeUploadJob] = load_youtube_uploads()
jobs_lock = threading.Lock()
processed_source_history_lock = threading.Lock()
youtube_uploads_lock = threading.Lock()
job_secrets: dict[str, str] = {}
job_processes: dict[str, subprocess.Popen[str]] = {}
youtube_upload_processes: dict[str, subprocess.Popen[str]] = {}
youtube_login_process: subprocess.Popen[str] | None = None
youtube_login_status = YouTubeLoginStatus(active=False)
youtube_login_reconnect_cdp = False
cancelled_job_ids: set[str] = set()
preserve_job_files_on_cancel: set[str] = set()
process_lock = threading.Lock()
youtube_worker_lock = threading.Lock()
youtube_worker_running = False
auto_viral_runs: dict[str, AutoViralRun] = {}
auto_viral_lock = threading.Lock()
auto_viral_active_run_id: str | None = None


def clip_url(path: Path) -> str:
    relative = path.resolve().relative_to(OUTPUTS_DIR.resolve()).as_posix()
    return "/outputs/" + quote(relative)


def playwright_installed() -> bool:
    return importlib.util.find_spec("playwright") is not None


def youtube_auth_state_exists() -> bool:
    return YOUTUBE_PLAYWRIGHT_STATE.is_file() and YOUTUBE_PLAYWRIGHT_STATE.stat().st_size > 0


def youtube_storage_cookie_counts() -> tuple[int, int]:
    try:
        payload = json.loads(YOUTUBE_PLAYWRIGHT_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, 0
    cookies = payload.get("cookies") if isinstance(payload, dict) else None
    if not isinstance(cookies, list):
        return 0, 0
    youtube_cookie_count = 0
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        domain = str(cookie.get("domain") or "").lower()
        if "youtube.com" in domain or "google.com" in domain:
            youtube_cookie_count += 1
    return len(cookies), youtube_cookie_count


def youtube_chromium_profile_ready() -> bool:
    if not YOUTUBE_CHROMIUM_USER_DATA_DIR:
        return False
    return Path(YOUTUBE_CHROMIUM_USER_DATA_DIR).expanduser().is_dir()


def youtube_login_source_profile_dir() -> str:
    return (
        os.environ.get("YOUTUBE_LOGIN_SOURCE_PROFILE_DIR", "").strip()
        or YOUTUBE_CHROMIUM_USER_DATA_DIR
    )


def youtube_login_source_profile_ready() -> bool:
    source = youtube_login_source_profile_dir()
    return bool(source and Path(source).expanduser().is_dir())


def youtube_profile_upload_allowed() -> bool:
    return env_bool("YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD", False)


def youtube_upload_uses_cdp() -> bool:
    return env_bool("YOUTUBE_UPLOAD_USE_CDP", False)


def youtube_upload_force_cdp() -> bool:
    return env_bool("YOUTUBE_UPLOAD_FORCE_CDP", False)


def youtube_upload_last_resort_fallback_allowed() -> bool:
    return env_bool("YOUTUBE_UPLOAD_ALLOW_LAST_RESORT_FALLBACK", True)


def youtube_upload_storage_state_first() -> bool:
    return env_bool("YOUTUBE_UPLOAD_STORAGE_STATE_FIRST", True)


def youtube_upload_prefers_chromium_profile() -> bool:
    return env_bool("YOUTUBE_UPLOAD_PREFER_CHROMIUM_PROFILE", False)


def youtube_upload_prefers_cdp() -> bool:
    return youtube_upload_uses_cdp()


def youtube_upload_auth_ready() -> bool:
    return (
        youtube_auth_state_exists()
        or youtube_upload_uses_cdp()
        or (youtube_profile_upload_allowed() and youtube_chromium_profile_ready())
    )


def youtube_default_visibility() -> Literal["private", "unlisted", "public"]:
    value = os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "public").strip().lower()
    return value if value in {"private", "unlisted", "public"} else "public"  # type: ignore[return-value]


def active_youtube_upload_id() -> str | None:
    with youtube_uploads_lock:
        for upload in sorted(youtube_uploads.values(), key=lambda item: item.created_at):
            if upload.status in {"queued", "running"}:
                return upload.id
    return None


def youtube_config_payload() -> YouTubeConfig:
    has_state = youtube_auth_state_exists()
    has_chromium_profile = youtube_chromium_profile_ready()
    allow_profile_upload = youtube_profile_upload_allowed()
    use_cdp = youtube_upload_uses_cdp()
    direct_profile_upload = (
        not use_cdp
        and allow_profile_upload
        and has_chromium_profile
        and youtube_upload_prefers_chromium_profile()
    )
    auth_path = str(YOUTUBE_PLAYWRIGHT_STATE if has_state else YOUTUBE_CHROMIUM_USER_DATA_DIR)
    auth_status_message = None
    if use_cdp:
        auth_path = YOUTUBE_CDP_URL
        if has_state:
            auth_status_message = (
                f"Upload memakai Chrome CDP: {YOUTUBE_CDP_URL}. "
                f"Storage state tersedia untuk hydrate session CDP: {YOUTUBE_PLAYWRIGHT_STATE}"
            )
        else:
            auth_status_message = f"Upload memakai Chrome remote debugging: {YOUTUBE_CDP_URL}"
    elif direct_profile_upload:
        auth_path = YOUTUBE_CHROMIUM_USER_DATA_DIR
        auth_status_message = (
            "Upload tanpa CDP aktif. Backend akan membuka browser/profile Chromium sendiri "
            f"dan memproses tab YouTube Studio dari profile: {auth_path}"
        )
    elif has_state:
        auth_status_message = (
            f"Playwright storage state siap untuk upload: {auth_path}."
        )
    elif has_chromium_profile and allow_profile_upload:
        auth_status_message = f"Chromium profile siap untuk upload langsung: {auth_path}"
    elif has_chromium_profile:
        auth_status_message = (
            "Chromium profile terdeteksi, tetapi upload background menunggu Sync Session Browser "
            f"membuat storage state: {YOUTUBE_PLAYWRIGHT_STATE}"
        )
    elif YOUTUBE_CHROMIUM_USER_DATA_DIR:
        auth_status_message = f"Chromium profile belum ditemukan di container: {YOUTUBE_CHROMIUM_USER_DATA_DIR}"
    else:
        auth_status_message = f"Storage state belum ada: {YOUTUBE_PLAYWRIGHT_STATE}"
    return YouTubeConfig(
        enabled=playwright_installed() and youtube_upload_auth_ready(),
        playwright_installed=playwright_installed(),
        auth_state_exists=youtube_upload_auth_ready(),
        auth_state_path=auth_path,
        auth_status_message=auth_status_message,
        upload_uses_cdp=use_cdp,
        direct_profile_upload=direct_profile_upload,
        chromium_profile_ready=has_chromium_profile,
        chromium_profile_path=YOUTUBE_CHROMIUM_USER_DATA_DIR,
        default_visibility=youtube_default_visibility(),
        default_made_for_kids=env_bool("YOUTUBE_MADE_FOR_KIDS", False),
        default_tags=env_csv("YOUTUBE_DEFAULT_TAGS"),
        default_playlist=os.environ.get("YOUTUBE_DEFAULT_PLAYLIST", DEFAULT_YOUTUBE_PLAYLIST).strip(),
        target_channel=os.environ.get("YOUTUBE_TARGET_CHANNEL", DEFAULT_YOUTUBE_TARGET_CHANNEL).strip(),
        target_email=os.environ.get("YOUTUBE_TARGET_EMAIL", DEFAULT_YOUTUBE_TARGET_EMAIL).strip(),
        auto_upload_count=youtube_auto_upload_count(),
        active_upload_id=active_youtube_upload_id(),
    )


def require_youtube_ready() -> None:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    if not youtube_upload_auth_ready():
        raise HTTPException(
            status_code=409,
            detail=(
                "Uploader YouTube belum siap. Klik Login Sekali untuk menyimpan session Playwright, "
                "atau set YOUTUBE_CHROMIUM_USER_DATA_DIR ke profile Chromium/Chrome yang sudah login."
            ),
        )


def youtube_upload_error_from_logs(logs: list[str]) -> str | None:
    for line in reversed(logs):
        if YOUTUBE_UPLOAD_ERROR_PREFIX in line:
            return normalize_youtube_upload_error(line.split(YOUTUBE_UPLOAD_ERROR_PREFIX, 1)[1].strip())
    return None


def youtube_login_refresh_needed(error: str) -> bool:
    lowered = error.lower()
    return (
        "chrome cdp belum login" in lowered
        or "chrome studio di remote debugging belum login" in lowered
        or "belum login ke akun target" in lowered
        or "bukan channel atau akun target" in lowered
        or "upload dibatalkan agar tidak salah akun" in lowered
        or "sesi youtube belum login" in lowered
        or "sesi youtube belum login atau sudah kedaluwarsa" in lowered
        or "session youtube studio belum login" in lowered
        or "youtube studio meminta login" in lowered
        or "refresh ulang profil chrome cdp" in lowered
        or "signintoyoutube" in lowered
        or "accounts.google.com" in lowered
    )


def youtube_cdp_start_needed(error: str) -> bool:
    lowered = error.lower()
    return (
        "chrome remote debugging belum aktif" in lowered
        or "remote debugging belum aktif" in lowered
        or "connect_over_cdp" in lowered
        or "econnrefused" in lowered
        or "connection refused" in lowered
        or "cannot connect" in lowered
    )


def normalize_youtube_upload_error(error: str) -> str:
    clean = error.strip()
    lowered = clean.lower()
    if "connect_over_cdp" in lowered or "econnrefused" in lowered:
        return (
            "Chrome CDP belum aktif. Jalur utama sekarang Playwright storage-state; klik Login Sekali, "
            "atau pakai Ambil Cookies CDP hanya jika ingin mengambil session dari Chrome CDP."
        )
    if youtube_upload_uses_cdp() and (
        "sesi youtube belum login" in lowered
        or "chrome cdp belum login" in lowered
        or "bukan channel atau akun target" in lowered
        or "upload dibatalkan agar tidak salah akun" in lowered
        or "youtube studio meminta login" in lowered
        or "python youtube_uploader.py login" in lowered
    ):
        return (
            "Session YouTube belum valid. Klik Login Sekali agar Playwright menyimpan ulang storage-state."
        )
    if youtube_upload_uses_cdp() and "playlist" in lowered and (
        "tidak ditemukan" in lowered or "not found" in lowered
    ):
        return (
            "Studio belum siap membaca playlist. Klik Login Sekali untuk refresh session, lalu Retry YouTube."
        )
    return clean


def media_duration_seconds(path: Path) -> float:
    try:
        result = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception:
        return 0.0
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        f"{result.stderr}\n{result.stdout}",
    )
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def youtube_max_upload_bytes() -> int:
    max_mb = (
        os.environ.get("YOUTUBE_MAX_UPLOAD_MB", "").strip()
        or os.environ.get("YOUTUBE_CDP_MAX_UPLOAD_MB", "").strip()
        or str(DEFAULT_YOUTUBE_MAX_UPLOAD_MB)
    )
    try:
        mb = float(max_mb)
    except ValueError:
        mb = DEFAULT_YOUTUBE_MAX_UPLOAD_MB
    return max(1, int(mb * 1024 * 1024))


def youtube_upload_staging_filter(source_path: Path) -> str:
    """Keep long-form compilations landscape when upload-size compression is needed."""
    if source_path.name.lower().startswith("highlight_5menit_"):
        return (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
    return (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )


def prepare_limited_upload_file(source_path: Path, max_bytes: int) -> Path:
    if source_path.stat().st_size <= max_bytes:
        return source_path

    duration = media_duration_seconds(source_path)
    if duration <= 0:
        raise RuntimeError(
            f"File {source_path.name} melebihi limit upload {max_bytes // 1024 // 1024} MB "
            "dan durasinya tidak bisa dibaca untuk kompresi upload."
        )

    source_stat = source_path.stat()
    digest = hashlib.sha1(
        f"{source_path.resolve()}:{source_stat.st_mtime_ns}:{source_stat.st_size}:{max_bytes}".encode("utf-8")
    ).hexdigest()[:12]
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", source_path.stem)[:80].strip("-") or "clip"
    target_path = YOUTUBE_CDP_STAGING_DIR / f"{safe_stem}-{digest}.mp4"
    if target_path.is_file() and target_path.stat().st_size <= max_bytes:
        return target_path

    YOUTUBE_CDP_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp.mp4")
    target_total_bps = max(450_000, int((max_bytes * 0.88 * 8) / duration))
    audio_bps = 96_000
    base_video_bps = max(300_000, target_total_bps - audio_bps)
    vf = youtube_upload_staging_filter(source_path)

    last_error = ""
    for factor in (1.0, 0.82, 0.68, 0.55):
        video_bps = max(260_000, int(base_video_bps * factor))
        temp_path.unlink(missing_ok=True)
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-i",
            str(source_path),
            "-vf",
            vf,
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
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(180, int(duration * 5)),
                check=False,
            )
        except Exception as exc:
            last_error = str(exc)
            continue
        if result.returncode != 0:
            last_error = (result.stderr or result.stdout)[-1200:]
            continue
        if temp_path.is_file() and temp_path.stat().st_size <= max_bytes:
            temp_path.replace(target_path)
            return target_path
        size_mb = temp_path.stat().st_size / 1024 / 1024 if temp_path.is_file() else 0
        last_error = f"Hasil kompresi masih {size_mb:.1f} MB"

    temp_path.unlink(missing_ok=True)
    raise RuntimeError(
        f"Gagal menyiapkan file upload di bawah {max_bytes // 1024 // 1024} MB: {last_error}"
    )


def normalize_youtube_video_url(value: str) -> str | None:
    clean = (value or "").strip().strip(".,;)'\"<>")
    if not clean:
        return None
    if clean.startswith("//"):
        clean = f"https:{clean}"
    elif clean.startswith("/watch") or clean.startswith("/shorts/"):
        clean = f"https://www.youtube.com{clean}"
    elif clean.startswith("youtube.com/"):
        clean = f"https://{clean}"
    elif clean.startswith("www.youtube.com/"):
        clean = f"https://{clean}"
    elif clean.startswith("youtu.be/"):
        clean = f"https://{clean}"

    match = re.search(
        r"(?:https?://)?(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)([A-Za-z0-9_-]{6,})",
        clean,
        re.I,
    )
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    match = re.search(r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{6,})", clean, re.I)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return None


def youtube_video_url_from_logs(logs: list[str]) -> str | None:
    for line in reversed(logs):
        if YOUTUBE_VIDEO_URL_PREFIX in line:
            value = line.split(YOUTUBE_VIDEO_URL_PREFIX, 1)[1].strip()
            video_url = normalize_youtube_video_url(value)
            if video_url:
                return video_url
    return None


def sidecar_social_caption(clip: ClipFile) -> str:
    if clip.social_caption and clip.social_caption.strip():
        return clip.social_caption.strip()
    clip_path = output_path_from_url(clip.url)
    if clip_path is None:
        return ""
    caption_path = clip_path.with_name(f"{clip_path.stem}_caption.txt")
    if not caption_path.is_file():
        return ""
    try:
        return caption_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def hashtags_from_text(value: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"#([\w\d_]{2,30})", value, flags=re.UNICODE):
        tag = match.group(1).strip("_")
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tags[:15]


def strip_hashtag_lines(value: str) -> str:
    lines = []
    for line in value.splitlines():
        clean = line.strip()
        if clean and all(part.startswith("#") for part in clean.split()):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def default_youtube_title(job: ClipJob, clip: ClipFile, index: int) -> str:
    title = clip_sidecar_title(clip) or clip.title or job.source_title or f"Clip {index}"
    clean = re.sub(r"\s+", " ", title).strip()
    if is_compilation_clip(job, clip):
        return youtube_long_form_title(clean or f"Highlight {index}")
    return youtube_shorts_title(clean or f"Clip {index}")


def youtube_long_form_title(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    clean = re.sub(r"\s+#shorts\b", "", clean, flags=re.I).strip()
    return clean[:100].rstrip() or "Highlight Pilihan"


def youtube_shorts_title(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    clean = re.sub(r"\s+#shorts\b", "", clean, flags=re.I).strip()
    suffix = " #Shorts"
    if len(clean) + len(suffix) > 100:
        clean = clean[: 100 - len(suffix)].rsplit(" ", 1)[0].rstrip() or clean[: 100 - len(suffix)].rstrip()
    return f"{clean}{suffix}"[:100] if clean else "Clip #Shorts"


def default_youtube_description(job: ClipJob, clip: ClipFile) -> str:
    caption = sidecar_social_caption(clip)
    short_caption = strip_hashtag_lines(caption)
    if len(short_caption) > 650:
        short_caption = short_caption[:650].rsplit(" ", 1)[0].rstrip() + "..."
    if not short_caption:
        title = clip_sidecar_title(clip) or clip.title or job.source_title or "Cuplikan pilihan"
        short_caption = f"{title.strip()}."
    parts = [short_caption]
    tags = default_youtube_tags(job, clip)
    if tags:
        parts.append(" ".join(f"#{tag.replace(' ', '')}" for tag in tags[:3]))
    return "\n\n".join(parts)[:5000]


def default_youtube_tags(job: ClipJob, clip: ClipFile) -> list[str]:
    caption = sidecar_social_caption(clip)
    tags = [*env_csv("YOUTUBE_DEFAULT_TAGS"), *hashtags_from_text(caption)]
    is_compilation = is_compilation_clip(job, clip)
    if is_compilation:
        tags = [tag for tag in tags if tag.strip().lower().lstrip("#") != "shorts"]
    if not tags:
        tags = ["islam", "highlight"] if is_compilation else ["islam", "shorts"]
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean = re.sub(r"\s+", " ", tag.strip().lstrip("#"))[:30]
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            deduped.append(clean)
    return deduped[:15]


YOUTUBE_METADATA_SYSTEM_PROMPT = (
    "You are a creative Indonesian YouTube metadata editor. For EACH clip, infer its specific central idea "
    "from that clip's transcript and write fresh metadata—not a generic template and not copied old metadata. "
    "Make the title modern, emotionally engaging, natural, and honest. Write an informative description that "
    "is concise but substantial. Use Bahasa Indonesia and never state folklore, personal experiences, myths, "
    "or supernatural claims as verified religious facts. Never mention source URLs, source channels, other "
    "channels, uploaders, TV stations, sponsors, or credits. Return strict JSON only."
)


def clip_candidate_text(job: ClipJob, clip: ClipFile) -> str:
    clip_index = clip_index_from_name(clip.name)
    if clip_index is not None:
        for candidate in job.candidates:
            if candidate.index == clip_index and candidate.text.strip():
                return candidate.text.strip()

    clip_path = output_path_from_url(clip.url)
    json_path = clip_path.with_suffix(".json") if clip_path is not None else None
    if json_path is not None and json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            text = payload.get("text") if isinstance(payload, dict) else None
            if isinstance(text, str) and text.strip():
                return text.strip()
        except (OSError, json.JSONDecodeError):
            pass
    return ""


def youtube_description_ai_config(job: ClipJob) -> AIConfig:
    telegram_base_url = os.environ.get("TELEGRAM_AI_BASE_URL", "").strip()
    telegram_model = os.environ.get("TELEGRAM_AI_MODEL", "").strip()
    base_url = (
        os.environ.get("YOUTUBE_DESCRIPTION_AI_BASE_URL", "").strip()
        or telegram_base_url
        or (job.request.ai_base_url or DEFAULT_AI_BASE_URL).strip()
    )
    model = (
        os.environ.get("YOUTUBE_DESCRIPTION_AI_MODEL", "").strip()
        or telegram_model
        or (job.request.ai_model or DEFAULT_AI_MODEL).strip()
    )
    enabled_default = bool(base_url and model) or job.request.ai_enabled
    return AIConfig(
        enabled=env_bool("YOUTUBE_DESCRIPTION_AI_ENABLED", enabled_default),
        base_url=base_url,
        model=model,
        api_key=(
            os.environ.get("YOUTUBE_DESCRIPTION_AI_API_KEY", "").strip()
            or os.environ.get("TELEGRAM_AI_API_KEY", "").strip()
            or job.request.ai_api_key.strip()
        ),
        timeout=float(os.environ.get("YOUTUBE_DESCRIPTION_AI_TIMEOUT_SECONDS", "45")),
    )


def openrouter_youtube_metadata_config() -> AIConfig | None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.environ.get(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    ).strip()
    model = os.environ.get(
        "OPENROUTER_MODEL",
        "openrouter/free",
    ).strip()
    if not base_url or not model:
        return None
    return AIConfig(
        enabled=True,
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout=float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "60")),
    )


def youtube_metadata_provider_configs(job: ClipJob) -> list[tuple[str, AIConfig, list[str]]]:
    providers: list[tuple[str, AIConfig, list[str]]] = []
    openrouter = openrouter_youtube_metadata_config()
    if openrouter is not None:
        providers.append(("OpenRouter", openrouter, [openrouter.model]))

    ollama = youtube_description_ai_config(job)
    if ollama.enabled and ollama.base_url and ollama.model:
        providers.append(
            (
                "Ollama",
                ollama,
                youtube_metadata_model_candidates(ollama.model),
            )
        )
    return providers


def youtube_metadata_model_candidates(primary_model: str) -> list[str]:
    configured = [
        *env_csv("YOUTUBE_DESCRIPTION_AI_FALLBACK_MODELS"),
        *env_csv("TELEGRAM_AI_FALLBACK_MODELS"),
    ]
    candidates: list[str] = []
    for model in [primary_model, *configured, *DEFAULT_YOUTUBE_AI_FALLBACK_MODELS]:
        clean = model.strip()
        if clean and clean not in candidates:
            candidates.append(clean)
    return candidates


def clean_ai_hashtags(values: list[str]) -> list[str]:
    hashtags: list[str] = []
    seen: set[str] = set()
    for raw in values:
        tag = str(raw).strip().lstrip("#")
        tag = re.sub(r"\s+", "", tag)[:30]
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            hashtags.append(tag)
    return hashtags[:15]


def first_metadata_string(payload: dict, keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return re.sub(r"\s+", " ", value).strip()
    return ""


def metadata_hashtag_values(payload: dict) -> list[str]:
    for key in ("hashtags", "hashtag", "tagar", "tags", "tag"):
        value = payload.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str) and value.strip():
            matches = re.findall(r"#[\w\d_]+", value, flags=re.UNICODE)
            if matches:
                return matches
            return [item for item in re.split(r"[\s,;]+", value) if item.strip()]
    return []


def unwrap_metadata_payload(payload: dict) -> dict:
    for key in ("metadata", "youtube_metadata", "hasil", "result", "data"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def normalized_generated_metadata(payload: dict, *, is_compilation: bool) -> dict[str, str | list[str]] | None:
    payload = unwrap_metadata_payload(payload)
    clean_title = first_metadata_string(
        payload,
        ["title", "judul", "headline", "judul_video", "video_title"],
    )
    description = first_metadata_string(
        payload,
        ["description", "deskripsi", "caption", "keterangan", "deskripsi_video", "video_description"],
    )
    clean_title = re.sub(r"https?://\S+", "", clean_title).strip(" -|")
    description_lines = [
        line.strip()
        for line in description.splitlines()
        if line.strip()
        and not re.search(r"https?://|^\s*(?:sumber|source|channel\s+sumber)\s*:", line, flags=re.I)
    ]
    description = strip_hashtag_lines("\n".join(description_lines))
    if not clean_title or len(description) < 70:
        return None

    ai_hashtags = clean_ai_hashtags(metadata_hashtag_values(payload))
    if not ai_hashtags:
        ai_hashtags = clean_ai_hashtags(hashtags_from_text(f"{clean_title}\n{description}"))
    if is_compilation:
        ai_hashtags = [tag for tag in ai_hashtags if tag.lower() != "shorts"]
    if len(ai_hashtags) < 3:
        return None
    ai_hashtags = ai_hashtags[:6]

    # Keep the description readable: enough context to be useful, but still
    # compact for Shorts and a five-minute highlight.
    if len(description) > 650:
        description = description[:650].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    text = f"{description}\n\n{' '.join(f'#{tag}' for tag in ai_hashtags)}"
    return {
        "title": youtube_long_form_title(clean_title) if is_compilation else youtube_shorts_title(clean_title),
        "description": text[:5000],
        "hashtags": ai_hashtags,
    }


def generate_youtube_metadata(job: ClipJob, clip: ClipFile, tags: list[str]) -> dict[str, str | list[str]] | None:
    providers = youtube_metadata_provider_configs(job)
    if not providers:
        return None

    title = clip_sidecar_title(clip) or clip.title or job.source_title or "Cuplikan pilihan"
    caption = strip_hashtag_lines(sidecar_social_caption(clip))
    transcript = clip_candidate_text(job, clip)
    clip_context = transcript or caption or title
    is_compilation = is_compilation_clip(job, clip)
    format_name = "video kompilasi highlight sekitar lima menit" if is_compilation else "YouTube Shorts"
    system_prompt = (
        YOUTUBE_METADATA_SYSTEM_PROMPT.replace(
            "YouTube Shorts metadata writer",
            "YouTube long-form highlight metadata writer",
        ).replace(
            "short clips",
            "five-minute highlight videos",
        )
        if is_compilation
        else YOUTUBE_METADATA_SYSTEM_PROMPT
    )
    format_hashtag_rule = (
        "- Jangan gunakan hashtag #Shorts untuk video kompilasi.\n"
        if is_compilation
        else "- Sertakan #Shorts sebagai salah satu hashtag.\n"
    )
    user_prompt = (
        f"Buat metadata {format_name} untuk video ini.\n"
        "Aturan:\n"
        "- Pahami konteks transkrip klip ini saja; jangan memakai metadata video sumber.\n"
        "- Title baru harus kuat, modern, natural, 35-75 karakter, maksimal 85 karakter, tanpa hashtag.\n"
        "- Perbaiki salah dengar transkrip yang jelas; jangan menyalin kata acak atau kalimat pembuka yang rusak.\n"
        "- Hindari ALL CAPS dan clickbait generik; tonjolkan manfaat, konflik, kejutan, atau hikmah yang benar-benar ada.\n"
        "- Description baru 2-3 kalimat informatif, sekitar 180-450 karakter; bangun rasa penasaran tanpa menyesatkan.\n"
        "- Description boleh memakai maksimal 2 emoji yang benar-benar relevan.\n"
        "- Bahasa Indonesia.\n"
        "- Jangan tulis URL, nama channel, uploader, TV, sponsor, kredit, atau label 'Sumber'.\n"
        "- Buat 4-6 hashtag baru yang spesifik dan relevan dengan isi klip, bukan hashtag generik berulang.\n"
        f"{format_hashtag_rule}"
        "- Wajib isi semua field JSON: title, description, hashtags.\n"
        'Return JSON exactly like {"title": "...", "description": "...", "hashtags": ["#tag1", "#tag2"]}.\n\n'
        f"Judul kerja klip (hanya petunjuk, wajib ditulis ulang): {title}\n"
        f"Konteks/transkrip klip:\n{clip_context[:2400]}"
    )
    last_error = ""
    for provider_index, (provider_name, config, models) in enumerate(providers):
        for model in models:
            active_config = AIConfig(
                enabled=config.enabled,
                base_url=config.base_url,
                model=model,
                api_key=config.api_key,
                timeout=config.timeout,
            )
            previous_content = ""
            for attempt in range(2):
                repair_note = (
                    "\n\nRespons sebelumnya belum memenuhi format/panjang/konteks. "
                    "Perbaiki dan kembalikan satu objek JSON lengkap saja:\n"
                    + previous_content[:1200]
                    if attempt and previous_content
                    else ""
                )
                try:
                    content = chat_completion(
                        active_config,
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt + repair_note},
                        ],
                    )
                    previous_content = content
                    parsed = extract_json(content)
                except Exception as exc:
                    last_error = f"{provider_name}/{model}: {exc}"
                    print(
                        f"YouTube metadata AI {provider_name} gagal dengan model {model}: {exc}",
                        flush=True,
                    )
                    break

                metadata = (
                    normalized_generated_metadata(parsed, is_compilation=is_compilation)
                    if isinstance(parsed, dict)
                    else None
                )
                if metadata is not None:
                    if provider_name == "OpenRouter":
                        print(f"YouTube metadata AI dibuat oleh OpenRouter: {model}", flush=True)
                    elif provider_index > 0 or model != config.model:
                        print(f"YouTube metadata AI memakai fallback Ollama: {model}", flush=True)
                    return metadata
                keys = ", ".join(str(key) for key in parsed.keys()) if isinstance(parsed, dict) else "-"
                print(
                    f"YouTube metadata AI format belum lengkap "
                    f"({provider_name}/{model}, percobaan {attempt + 1}); keys: {keys}",
                    flush=True,
                )

    if last_error:
        print(f"YouTube metadata AI gagal semua model. Terakhir: {last_error}", flush=True)
    return None


def generate_youtube_description(job: ClipJob, clip: ClipFile, tags: list[str]) -> str | None:
    metadata = generate_youtube_metadata(job, clip, tags)
    description = metadata.get("description") if isinstance(metadata, dict) else None
    return description if isinstance(description, str) and description.strip() else None


def find_job_clip(job_id: str, clip_url: str) -> tuple[ClipJob, ClipFile, int]:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Job belum selesai")
    for index, clip in enumerate(job.clips, start=1):
        if clip.url == clip_url:
            return job, clip, index
    raise HTTPException(status_code=404, detail="Clip not found")


def best_youtube_clip_urls(job: ClipJob, count: int = DEFAULT_YOUTUBE_AUTO_UPLOAD_COUNT) -> list[str]:
    scores_by_index = {candidate.index: candidate.score for candidate in job.candidates}
    ranked: list[tuple[int, int, int, ClipFile]] = []
    for position, clip in enumerate(job.clips):
        clip_index = clip_index_from_name(clip.name)
        score = scores_by_index.get(clip_index, -1) if clip_index is not None else -1
        ranked.append((score, -position, clip_index or position + 1, clip))

    ranked.sort(reverse=True)
    return [clip.url for _, _, _, clip in ranked[: max(1, count)]]


def existing_active_youtube_upload(job_id: str, clip_url: str) -> YouTubeUploadJob | None:
    with youtube_uploads_lock:
        for upload in youtube_uploads.values():
            if (
                upload.source_job_id == job_id
                and upload.clip_url == clip_url
                and upload.status in {"queued", "running"}
            ):
                return upload
    return None


def active_youtube_uploads_for_job(job_id: str, clip_urls: set[str] | None = None) -> list[YouTubeUploadJob]:
    with youtube_uploads_lock:
        return [
            upload
            for upload in youtube_uploads.values()
            if upload.source_job_id == job_id
            and upload.status in {"queued", "running"}
            and (clip_urls is None or upload.clip_url in clip_urls)
        ]


def create_youtube_upload_record(job_id: str, request: YouTubeUploadRequest) -> YouTubeUploadJob:
    job, clip, index = find_job_clip(job_id, request.clip_url)
    existing = existing_active_youtube_upload(job_id, clip.url)
    if existing is not None:
        return existing

    clip_path = output_path_from_url(clip.url)
    if clip_path is None or not clip_path.is_file():
        raise HTTPException(status_code=404, detail="File clip tidak ditemukan di outputs")

    thumbnail_url = request.thumbnail_url or clip.thumbnail_url
    thumbnail_path = output_path_from_url(thumbnail_url) if thumbnail_url else None
    safe_thumbnail_url = thumbnail_url if thumbnail_path is not None and thumbnail_path.is_file() else None
    fallback_tags = request.tags or default_youtube_tags(job, clip)
    ai_metadata = generate_youtube_metadata(job, clip, fallback_tags)
    if env_bool("YOUTUBE_REQUIRE_AI_METADATA", True) and not isinstance(ai_metadata, dict):
        raise HTTPException(
            status_code=409,
            detail=(
                "AI belum berhasil membuat metadata baru setelah mencoba model utama dan model lokal. "
                "Pastikan Ollama aktif, lalu coba upload lagi; upload belum dimulai dan metadata lama tidak dipakai."
            ),
        )
    ai_title = ai_metadata.get("title") if isinstance(ai_metadata, dict) else None
    ai_description = ai_metadata.get("description") if isinstance(ai_metadata, dict) else None
    ai_hashtags = ai_metadata.get("hashtags") if isinstance(ai_metadata, dict) else None
    tags = clean_ai_hashtags(ai_hashtags if isinstance(ai_hashtags, list) else []) or fallback_tags
    if env_bool("YOUTUBE_REQUIRE_AI_METADATA", True) and not clean_ai_hashtags(
        ai_hashtags if isinstance(ai_hashtags, list) else []
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "AI belum menghasilkan minimal 3 hashtag kontekstual. "
                "Coba upload lagi; metadata lama tidak dipakai."
            ),
        )
    title = (ai_title if isinstance(ai_title, str) and ai_title.strip() else "") or request.title or default_youtube_title(job, clip, index)
    description = (
        (ai_description if isinstance(ai_description, str) and ai_description.strip() else "")
        or request.description
        or default_youtube_description(job, clip)
    )
    upload_id = uuid.uuid4().hex
    now = now_iso()
    return YouTubeUploadJob(
        id=upload_id,
        source_job_id=job_id,
        clip_url=clip.url,
        clip_name=clip.name,
        status="queued",
        created_at=now,
        updated_at=now,
        title=(
            youtube_long_form_title(title)
            if is_compilation_clip(job, clip)
            else youtube_shorts_title(title)
        ),
        description=description,
        thumbnail_url=safe_thumbnail_url,
        visibility=request.visibility,
        made_for_kids=request.made_for_kids,
        tags=tags,
        playlist=request.playlist,
        target_channel=request.target_channel,
        dry_run=request.dry_run,
    )


def create_youtube_upload_batch_records(job_id: str, request: YouTubeBatchUploadRequest) -> list[YouTubeUploadJob]:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Job belum selesai")

    clip_urls = request.clip_urls or best_youtube_clip_urls(job, request.best_count)
    if not clip_urls:
        raise HTTPException(status_code=400, detail="Tidak ada clip untuk diupload")

    return [
        create_youtube_upload_record(
            job_id,
            YouTubeUploadRequest(
                clip_url=clip_url,
                visibility=request.visibility,
                made_for_kids=request.made_for_kids,
                tags=request.tags,
                playlist=request.playlist,
                target_channel=request.target_channel,
                dry_run=request.dry_run,
            ),
        )
        for clip_url in clip_urls
    ]


def queue_youtube_upload_jobs(uploads: list[YouTubeUploadJob]) -> None:
    with youtube_uploads_lock:
        for upload in uploads:
            if upload.id not in youtube_uploads:
                youtube_uploads[upload.id] = upload
        save_youtube_uploads_unlocked()
    start_youtube_worker_if_needed()


def auto_queue_youtube_uploads_for_job(job_id: str, logs: list[str]) -> None:
    try:
        require_youtube_ready()
        uploads = create_youtube_upload_batch_records(job_id, YouTubeBatchUploadRequest())
        queue_youtube_upload_jobs(uploads)
        logs.append(f"Auto upload YouTube: {len(uploads)} clip terbaik masuk antrean.")
    except HTTPException as exc:
        logs.append(f"Auto upload YouTube gagal: {exc.detail}")
    except Exception as exc:
        logs.append(f"Auto upload YouTube gagal: {exc}")
    set_job(job_id, logs=logs[-120:])


def set_youtube_upload(upload_id: str, **updates) -> None:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
        if upload is None:
            return
        data = upload.model_dump()
        data.update(updates)
        data["updated_at"] = now_iso()
        youtube_uploads[upload_id] = YouTubeUploadJob(**data)
        save_youtube_uploads_unlocked()


def build_youtube_upload_command(
    upload: YouTubeUploadJob,
    *,
    use_cdp_override: bool | None = None,
    force_chromium_profile: bool = False,
) -> list[str]:
    clip_path = output_path_from_url(upload.clip_url)
    if clip_path is None:
        raise RuntimeError("Clip path is invalid")
    use_cdp = youtube_upload_prefers_cdp() if use_cdp_override is None else use_cdp_override
    max_upload_bytes = youtube_max_upload_bytes()
    upload_path = prepare_limited_upload_file(clip_path, max_upload_bytes)
    command = [
        sys.executable,
        "youtube_uploader.py",
        "upload",
        str(upload_path),
        "--state",
        str(YOUTUBE_PLAYWRIGHT_STATE),
        "--title",
        upload.title,
        "--description",
        upload.description,
        "--visibility",
        upload.visibility,
        "--timeout",
        os.environ.get("YOUTUBE_UPLOAD_TIMEOUT_SECONDS", "5400"),
    ]
    if upload.thumbnail_url:
        thumbnail_path = output_path_from_url(upload.thumbnail_url)
        if thumbnail_path is not None and thumbnail_path.is_file():
            command.extend(["--thumbnail", str(thumbnail_path)])
    if upload.tags:
        command.extend(["--tags", ",".join(upload.tags)])
    if upload.playlist:
        command.extend(["--playlist", upload.playlist])
    if upload.target_channel:
        command.extend(["--target-channel", upload.target_channel])
    target_email = os.environ.get("YOUTUBE_TARGET_EMAIL", DEFAULT_YOUTUBE_TARGET_EMAIL).strip()
    if target_email:
        command.extend(["--target-email", target_email])
    target_channel_id = os.environ.get("YOUTUBE_TARGET_CHANNEL_ID", DEFAULT_YOUTUBE_TARGET_CHANNEL_ID).strip()
    if target_channel_id:
        command.extend(["--target-channel-id", target_channel_id])
    studio_url = os.environ.get("YOUTUBE_STUDIO_URL", "").strip()
    if studio_url:
        command.extend(["--studio-url", studio_url])
    if use_cdp:
        command.extend(["--use-cdp", "--cdp-url", YOUTUBE_CDP_URL])
    use_chromium_profile = (
        not use_cdp
        and youtube_profile_upload_allowed()
        and bool(YOUTUBE_CHROMIUM_USER_DATA_DIR)
        and (force_chromium_profile or youtube_upload_prefers_chromium_profile() or not youtube_auth_state_exists())
    )
    if use_chromium_profile:
        command.extend(["--chromium-user-data-dir", YOUTUBE_CHROMIUM_USER_DATA_DIR])
        if YOUTUBE_CHROMIUM_PROFILE_DIRECTORY:
            command.extend(["--chromium-profile-directory", YOUTUBE_CHROMIUM_PROFILE_DIRECTORY])
    if upload.made_for_kids:
        command.append("--made-for-kids")
    if upload.dry_run:
        command.append("--dry-run")
    if not env_bool("YOUTUBE_HEADLESS", True):
        command.append("--no-headless")
    return command


def build_youtube_login_command(*, timeout_seconds: str | None = None) -> list[str]:
    command = [
        sys.executable,
        "youtube_uploader.py",
        "login",
        "--state",
        str(YOUTUBE_PLAYWRIGHT_STATE),
        "--auto-close",
        "--timeout",
        timeout_seconds or os.environ.get("YOUTUBE_LOGIN_TIMEOUT_SECONDS", "600"),
    ]
    if YOUTUBE_LOGIN_PROFILE_DIR:
        command.extend(["--chromium-user-data-dir", YOUTUBE_LOGIN_PROFILE_DIR])
        if YOUTUBE_LOGIN_PROFILE_DIRECTORY:
            command.extend(["--chromium-profile-directory", YOUTUBE_LOGIN_PROFILE_DIRECTORY])
    studio_url = os.environ.get("YOUTUBE_STUDIO_URL", "").strip()
    if studio_url:
        command.extend(["--studio-url", studio_url])
    return command


def build_youtube_check_login_command(*, use_chromium_profile: bool = False) -> list[str]:
    command = [
        sys.executable,
        "youtube_uploader.py",
        "check-login",
        "--state",
        str(YOUTUBE_PLAYWRIGHT_STATE),
        "--target-channel",
        os.environ.get("YOUTUBE_TARGET_CHANNEL", DEFAULT_YOUTUBE_TARGET_CHANNEL).strip(),
        "--target-email",
        os.environ.get("YOUTUBE_TARGET_EMAIL", DEFAULT_YOUTUBE_TARGET_EMAIL).strip(),
        "--target-channel-id",
        os.environ.get("YOUTUBE_TARGET_CHANNEL_ID", DEFAULT_YOUTUBE_TARGET_CHANNEL_ID).strip(),
    ]
    if use_chromium_profile and YOUTUBE_LOGIN_PROFILE_DIR:
        command.extend(["--chromium-user-data-dir", YOUTUBE_LOGIN_PROFILE_DIR])
        if YOUTUBE_LOGIN_PROFILE_DIRECTORY:
            command.extend(["--chromium-profile-directory", YOUTUBE_LOGIN_PROFILE_DIRECTORY])
    studio_url = os.environ.get("YOUTUBE_STUDIO_URL", "").strip()
    if studio_url:
        command.extend(["--studio-url", studio_url])
    return command


def build_youtube_capture_command(*, hydrate_storage_state: bool = True) -> list[str]:
    command = [
        sys.executable,
        "youtube_uploader.py",
        "capture-session",
        "--state",
        str(YOUTUBE_PLAYWRIGHT_STATE),
        "--cdp-url",
        YOUTUBE_CDP_URL,
        "--target-channel",
        os.environ.get("YOUTUBE_TARGET_CHANNEL", DEFAULT_YOUTUBE_TARGET_CHANNEL).strip(),
        "--target-email",
        os.environ.get("YOUTUBE_TARGET_EMAIL", DEFAULT_YOUTUBE_TARGET_EMAIL).strip(),
        "--target-channel-id",
        os.environ.get("YOUTUBE_TARGET_CHANNEL_ID", DEFAULT_YOUTUBE_TARGET_CHANNEL_ID).strip(),
    ]
    studio_url = os.environ.get("YOUTUBE_STUDIO_URL", "").strip()
    if studio_url:
        command.extend(["--studio-url", studio_url])
    if not hydrate_storage_state:
        command.append("--no-hydrate-storage-state")
    return command


def run_youtube_check_login_once(*, use_chromium_profile: bool = False) -> tuple[int, list[str], str | None]:
    check_logs: list[str] = []
    process_env = os.environ.copy()
    process_env["YOUTUBE_LOGIN_HEADLESS"] = os.environ.get("YOUTUBE_PROFILE_LOGIN_HEADLESS", "true")
    process = subprocess.Popen(
        build_youtube_check_login_command(use_chromium_profile=use_chromium_profile),
        cwd=BASE_DIR,
        env=process_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        cleaned = line.rstrip()
        if cleaned:
            check_logs.append(cleaned)
    check_code = process.wait()
    check_error = youtube_upload_error_from_logs(check_logs) if check_code else None
    return check_code, check_logs, check_error


def run_youtube_capture_once(*, hydrate_storage_state: bool = True) -> tuple[int, list[str], str | None]:
    capture_logs: list[str] = []
    process = subprocess.Popen(
        build_youtube_capture_command(hydrate_storage_state=hydrate_storage_state),
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        cleaned = line.rstrip()
        if cleaned:
            capture_logs.append(cleaned)
    capture_code = process.wait()
    capture_error = youtube_upload_error_from_logs(capture_logs) if capture_code else None
    return capture_code, capture_logs, capture_error


def run_youtube_profile_login_once(*, timeout_seconds: str | None = None) -> tuple[int, list[str], str | None]:
    login_logs: list[str] = []
    process_env = os.environ.copy()
    process_env["YOUTUBE_LOGIN_HEADLESS"] = os.environ.get("YOUTUBE_PROFILE_LOGIN_HEADLESS", "true")
    process = subprocess.Popen(
        build_youtube_login_command(timeout_seconds=timeout_seconds),
        cwd=BASE_DIR,
        env=process_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        cleaned = line.rstrip()
        if cleaned:
            login_logs.append(cleaned)
    login_code = process.wait()
    login_error = youtube_upload_error_from_logs(login_logs) if login_code else None
    return login_code, login_logs, login_error


def tail_text_file(path: Path, limit: int = 80) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []


def youtube_cdp_ready(cdp_url: str | None = None) -> bool:
    target_url = (cdp_url or YOUTUBE_CDP_URL).rstrip("/")
    try:
        with urllib.request.urlopen(f"{target_url}/json/version", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False
    return bool(payload.get("webSocketDebuggerUrl"))


def youtube_cdp_port() -> str:
    match = re.search(r":(\d+)(?:/|$)", YOUTUBE_CDP_URL)
    return match.group(1) if match else "9222"


def stop_youtube_cdp_processes() -> None:
    port = youtube_cdp_port()
    try:
        subprocess.run(
            ["pkill", "-f", f"remote-debugging-port={port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        time.sleep(1.5)
    except Exception:
        pass


def build_youtube_cdp_refresh_command() -> list[str]:
    configured = os.environ.get("YOUTUBE_CDP_REFRESH_COMMAND", "").strip()
    if configured:
        return shlex.split(configured)

    script_candidates = [
        ROOT_DIR / "scripts" / "open-youtube-login-chrome.sh",
        BASE_DIR / "scripts" / "open-youtube-login-chrome.sh",
    ]
    for script_path in script_candidates:
        if script_path.is_file():
            return [str(script_path)]

    searched = ", ".join(str(path) for path in script_candidates)
    detail = (
        "Script scripts/open-youtube-login-chrome.sh tidak ditemukan dari proses backend. "
        f"Path yang dicek: {searched}. "
    )
    if env_bool("IN_DOCKER", False):
        detail += (
            "Backend berjalan di Docker, jadi script host harus di-mount ke container "
            "atau set YOUTUBE_CDP_REFRESH_COMMAND ke command yang valid di dalam container."
        )
    else:
        detail += "Set YOUTUBE_CDP_REFRESH_COMMAND ke command launcher Chrome CDP."
    raise HTTPException(
        status_code=409,
        detail=detail,
    )


def start_youtube_cdp_refresh_process(
    *,
    force_profile_refresh: bool = False,
    force_restart: bool = False,
) -> YouTubeCdpRefreshStatus:
    command = build_youtube_cdp_refresh_command()
    started_at = now_iso()
    YOUTUBE_CDP_REFRESH_LOG.parent.mkdir(parents=True, exist_ok=True)
    process_env = os.environ.copy()
    if force_profile_refresh:
        process_env["YOUTUBE_REFRESH_LOGIN_PROFILE"] = "true"
    if force_restart:
        stop_youtube_cdp_processes()
    try:
        with YOUTUBE_CDP_REFRESH_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n[{started_at}] Starting YouTube CDP refresh: {shlex.join(command)}\n")
            if force_profile_refresh:
                log_file.write(f"[{started_at}] Force profile refresh enabled.\n")
            log_file.flush()
            process = subprocess.Popen(
                command,
                cwd=ROOT_DIR if ROOT_DIR.is_dir() else BASE_DIR,
                env=process_env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            deadline = time.monotonic() + YOUTUBE_CDP_REFRESH_READY_TIMEOUT_SECONDS
            if YOUTUBE_CDP_REFRESH_STARTUP_GRACE_SECONDS:
                time.sleep(min(YOUTUBE_CDP_REFRESH_STARTUP_GRACE_SECONDS, YOUTUBE_CDP_REFRESH_READY_TIMEOUT_SECONDS))
            while time.monotonic() < deadline:
                if youtube_cdp_ready():
                    time.sleep(1.0)
                    if not youtube_cdp_ready():
                        time.sleep(0.5)
                        continue
                    return YouTubeCdpRefreshStatus(
                        started=True,
                        cdp_ready=True,
                        started_at=started_at,
                        command=command,
                        log_path=str(YOUTUBE_CDP_REFRESH_LOG),
                        message=(
                            "Launcher Chrome CDP sudah dijalankan dari bot dan remote debugging sudah aktif. "
                            "Session bisa disinkronkan/diupload dari bot."
                        ),
                        logs=tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40),
                    )
                code = process.poll()
                if code is not None and code != 0:
                    logs = tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40)
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Launcher Chrome CDP berhenti sebelum remote debugging stabil (exit code {code}). "
                            f"Cek log {YOUTUBE_CDP_REFRESH_LOG}: "
                            + " | ".join(logs[-6:])
                        ),
                    )
                time.sleep(0.5)

            logs = tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Command refresh sudah dijalankan dari bot ({shlex.join(command)}), "
                    f"tetapi Chrome remote debugging belum aktif di {YOUTUBE_CDP_URL} "
                    f"setelah {YOUTUBE_CDP_REFRESH_READY_TIMEOUT_SECONDS:.0f} detik. "
                    f"Cek log {YOUTUBE_CDP_REFRESH_LOG}: "
                    + " | ".join(logs[-8:])
                ),
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=f"Command launcher Chrome CDP tidak ditemukan: {command[0]}") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Gagal menjalankan launcher Chrome CDP: {exc}") from exc

    return YouTubeCdpRefreshStatus(
        started=True,
        cdp_ready=youtube_cdp_ready(),
        started_at=started_at,
        command=command,
        log_path=str(YOUTUBE_CDP_REFRESH_LOG),
        message=(
            "Launcher Chrome CDP sudah dijalankan di background. "
            "Tunggu beberapa detik sampai remote debugging aktif."
        ),
        logs=tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40),
    )


def set_youtube_login_status(**updates) -> None:
    global youtube_login_status
    data = youtube_login_status.model_dump()
    data.update(updates)
    youtube_login_status = YouTubeLoginStatus(**data)


def run_youtube_login_process() -> None:
    global youtube_login_process, youtube_login_reconnect_cdp
    logs: list[str] = []
    try:
        process_env = os.environ.copy()
        process_env["YOUTUBE_LOGIN_HEADLESS"] = "false"
        host_runtime_dir = Path(process_env.get("YOUTUBE_HOST_RUNTIME_DIR", "/run/clipforge-host-user"))
        if host_runtime_dir.is_dir():
            authority_files = sorted(
                host_runtime_dir.glob(".mutter-Xwaylandauth.*"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if authority_files:
                process_env["XAUTHORITY"] = str(authority_files[0])
            if (host_runtime_dir / "bus").exists():
                process_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={host_runtime_dir / 'bus'}"
        process = subprocess.Popen(
            build_youtube_login_command(),
            cwd=BASE_DIR,
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        with process_lock:
            youtube_login_process = process
        assert process.stdout is not None
        for line in process.stdout:
            cleaned = line.rstrip()
            if cleaned:
                logs.append(cleaned)
                set_youtube_login_status(logs=logs[-80:])
        code = process.wait()
        error = youtube_upload_error_from_logs(logs) if code != 0 else None
        with process_lock:
            reconnect_cdp = youtube_login_reconnect_cdp
        if code == 0 and reconnect_cdp:
            logs.append("Login berhasil; mengaktifkan kembali Chrome remote debugging secara otomatis.")
            set_youtube_login_status(logs=logs[-80:])
            try:
                refresh_status = start_youtube_cdp_refresh_process(force_restart=True)
                logs.extend(refresh_status.logs[-20:])
                logs.append(refresh_status.message)
                capture_code, capture_logs, capture_error = run_youtube_capture_once()
                logs.extend(capture_logs[-40:])
                if capture_code != 0:
                    error = capture_error or f"capture-session exited with code {capture_code}"
                else:
                    logs.append("RECONNECT_CDP_SUCCESS: Login selesai, CDP aktif, dan session target valid.")
            except HTTPException as exc:
                error = f"Login tersimpan, tetapi koneksi ulang Chrome CDP gagal: {exc.detail}"
        set_youtube_login_status(
            active=False,
            finished_at=now_iso(),
            logs=logs[-80:],
            error=error or (f"youtube_uploader.py login exited with code {code}" if code else None),
        )
    except Exception as exc:
        set_youtube_login_status(active=False, finished_at=now_iso(), logs=logs[-80:], error=str(exc))
    finally:
        with process_lock:
            youtube_login_process = None
            youtube_login_reconnect_cdp = False


def start_youtube_login_if_needed(*, reconnect_cdp: bool = False) -> YouTubeLoginStatus:
    global youtube_login_process, youtube_login_reconnect_cdp
    with process_lock:
        if reconnect_cdp:
            youtube_login_reconnect_cdp = True
        if youtube_login_process is not None and youtube_login_process.poll() is None:
            return youtube_login_status
        started_at = now_iso()
        set_youtube_login_status(active=True, started_at=started_at, finished_at=None, error=None, logs=[])
    threading.Thread(target=run_youtube_login_process, daemon=True).start()
    return youtube_login_status


def run_youtube_upload(upload_id: str) -> None:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
    if upload is None:
        return
    started_perf = time.perf_counter()
    set_youtube_upload(
        upload_id,
        status="running",
        started_at=now_iso(),
        finished_at=None,
        duration_seconds=None,
        error=None,
    )

    logs: list[str] = []
    try:
        fallback_to_storage_state = False
        fallback_to_cdp = False
        fallback_to_chromium_profile = False
        one_time_login_refresh_attempted = False
        force_chromium_profile_for_attempt = False
        use_cdp_for_attempt = youtube_upload_prefers_cdp()
        if youtube_upload_storage_state_first() and not youtube_upload_force_cdp():
            if youtube_auth_state_exists():
                if use_cdp_for_attempt:
                    logs.append("Mode login sekali aktif: upload memakai storage-state dulu, bukan Chrome CDP.")
                use_cdp_for_attempt = False
            elif youtube_profile_upload_allowed() and youtube_chromium_profile_ready():
                if use_cdp_for_attempt:
                    logs.append("Mode login sekali aktif: upload memakai profile Chromium backend dulu, bukan Chrome CDP.")
                use_cdp_for_attempt = False
                force_chromium_profile_for_attempt = True
        if use_cdp_for_attempt and not youtube_cdp_ready():
            logs.append(
                f"Chrome remote debugging belum aktif di {YOUTUBE_CDP_URL}; menjalankan YOUTUBE_CDP_REFRESH_COMMAND..."
            )
            set_youtube_upload(upload_id, logs=logs[-160:])
            try:
                refresh_status = start_youtube_cdp_refresh_process()
            except HTTPException as exc:
                raise RuntimeError(str(exc.detail)) from exc
            logs.append(refresh_status.message)
            set_youtube_upload(upload_id, logs=logs[-160:])
            if not refresh_status.cdp_ready and not youtube_cdp_ready():
                raise RuntimeError(
                    f"Chrome remote debugging belum aktif di {YOUTUBE_CDP_URL} setelah refresh command."
                )
        if not use_cdp_for_attempt and youtube_auth_state_exists():
            logs.append(f"Upload memakai Playwright storage state: {YOUTUBE_PLAYWRIGHT_STATE}")
            set_youtube_upload(upload_id, logs=logs[-160:])
        cdp_repair_attempts = 0
        max_cdp_repairs = max(1, env_int("YOUTUBE_CDP_UPLOAD_REPAIR_ATTEMPTS", 3))
        default_max_attempts = 6 if (use_cdp_for_attempt or youtube_auth_state_exists() or youtube_chromium_profile_ready()) else 1
        max_attempts = max(1, env_int("YOUTUBE_CDP_UPLOAD_MAX_ATTEMPTS", default_max_attempts))
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                if use_cdp_for_attempt:
                    mode = "Chrome CDP"
                elif force_chromium_profile_for_attempt:
                    mode = "profile Chromium langsung"
                else:
                    mode = "storage state Playwright"
                logs.append(f"Retry upload attempt {attempt} memakai {mode}.")
                set_youtube_upload(upload_id, logs=logs[-160:])
            command = build_youtube_upload_command(
                upload,
                use_cdp_override=use_cdp_for_attempt,
                force_chromium_profile=force_chromium_profile_for_attempt,
            )
            process = subprocess.Popen(
                command,
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            with process_lock:
                youtube_upload_processes[upload_id] = process
            assert process.stdout is not None
            for line in process.stdout:
                cleaned = line.rstrip()
                if cleaned:
                    logs.append(cleaned)
                    set_youtube_upload(upload_id, logs=logs[-160:], video_url=youtube_video_url_from_logs(logs))
            code = process.wait()
            video_url = youtube_video_url_from_logs(logs)
            error = youtube_upload_error_from_logs(logs) or f"youtube_uploader.py exited with code {code}"
            if code == 0:
                set_youtube_upload(
                    upload_id,
                    status="completed",
                    logs=logs[-160:],
                    video_url=video_url,
                    finished_at=now_iso(),
                    duration_seconds=elapsed_seconds(started_perf),
                )
                return
            if attempt < max_attempts and youtube_login_refresh_needed(error):
                if not use_cdp_for_attempt and not one_time_login_refresh_attempted:
                    one_time_login_refresh_attempted = True
                    logs.append("Session storage-state belum valid; backend menjalankan Login Sekali otomatis lalu retry.")
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    try:
                        login_status = setup_youtube_one_time_login()
                    except HTTPException as exc:
                        logs.append(f"Login Sekali otomatis gagal: {exc.detail}")
                    else:
                        logs.extend(login_status.logs[-40:])
                        logs.append(login_status.message)
                        if login_status.error:
                            logs.append(f"Login Sekali otomatis belum valid: {login_status.error}")
                        if login_status.ok:
                            force_chromium_profile_for_attempt = False
                            use_cdp_for_attempt = False
                            set_youtube_upload(upload_id, logs=logs[-160:], error=None)
                            continue
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                if (
                    use_cdp_for_attempt
                    and youtube_auth_state_exists()
                    and not fallback_to_storage_state
                ):
                    logs.append(
                        f"CDP belum login; mode login sekali fallback ke Playwright storage state: "
                        f"{YOUTUBE_PLAYWRIGHT_STATE}"
                    )
                    fallback_to_storage_state = True
                    force_chromium_profile_for_attempt = False
                    use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    continue
                if (
                    use_cdp_for_attempt
                    and youtube_profile_upload_allowed()
                    and youtube_chromium_profile_ready()
                    and not fallback_to_chromium_profile
                ):
                    logs.append(
                        "CDP belum login; mode login sekali fallback ke profile Chromium backend langsung."
                    )
                    fallback_to_chromium_profile = True
                    force_chromium_profile_for_attempt = True
                    use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    continue
                if use_cdp_for_attempt and cdp_repair_attempts < max_cdp_repairs:
                    cdp_repair_attempts += 1
                    logs.append(
                        "CDP belum login ke akun target; backend menjalankan auto-login/repair "
                        f"{cdp_repair_attempts}/{max_cdp_repairs} dari profile/storage-state."
                    )
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    if youtube_chromium_profile_ready():
                        login_code, login_logs, login_error = run_youtube_profile_login_once()
                        logs.extend(login_logs[-40:])
                        if login_code == 0:
                            logs.append("Profile Chromium berhasil divalidasi ulang sebelum repair CDP.")
                        else:
                            login_failure = login_error or f"exit code {login_code}"
                            logs.append(
                                "Validasi profile Chromium sebelum repair CDP belum berhasil: "
                                f"{login_failure}"
                            )
                        set_youtube_upload(upload_id, logs=logs[-160:])
                    try:
                        repair_status = repair_youtube_cdp(profile_sync_requested=True)
                    except HTTPException as exc:
                        raise RuntimeError(str(exc.detail)) from exc
                    logs.extend(repair_status.logs[-40:])
                    logs.append(repair_status.message)
                    if repair_status.error:
                        logs.append(f"Repair CDP belum valid: {repair_status.error}")
                    set_youtube_upload(upload_id, logs=logs[-160:], error=repair_status.error)
                    continue
                if (
                    not use_cdp_for_attempt
                    and youtube_profile_upload_allowed()
                    and youtube_chromium_profile_ready()
                    and not fallback_to_chromium_profile
                ):
                    logs.append(
                        "Storage-state belum login; fallback ke profile Chromium backend langsung."
                    )
                    fallback_to_chromium_profile = True
                    force_chromium_profile_for_attempt = True
                    use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    continue
                if (
                    use_cdp_for_attempt
                    and youtube_auth_state_exists()
                    and not fallback_to_storage_state
                    and (not youtube_upload_force_cdp() or youtube_upload_last_resort_fallback_allowed())
                ):
                    logs.append(
                        f"CDP masih belum login pada attempt {attempt}; fallback ke Playwright storage state: "
                        f"{YOUTUBE_PLAYWRIGHT_STATE}"
                    )
                    fallback_to_storage_state = True
                    force_chromium_profile_for_attempt = False
                    use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    continue
                if (
                    not use_cdp_for_attempt
                    and youtube_upload_uses_cdp()
                    and not fallback_to_cdp
                    and youtube_upload_force_cdp()
                    and youtube_upload_last_resort_fallback_allowed()
                    and not force_chromium_profile_for_attempt
                ):
                    logs.append("Storage-state belum login; mencoba fallback paksa ke Chrome CDP.")
                    fallback_to_cdp = True
                    force_chromium_profile_for_attempt = False
                    use_cdp_for_attempt = True
                    set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
                    continue
                logs.append(
                    f"Session YouTube masih belum login pada attempt {attempt}. Jalankan Login Sekali untuk menyegarkan storage-state/profile."
                )
                set_youtube_upload(upload_id, logs=logs[-160:], error=normalize_youtube_upload_error(error))
            set_youtube_upload(
                upload_id,
                status="failed",
                logs=logs[-160:],
                video_url=video_url,
                error=error,
                finished_at=now_iso(),
                duration_seconds=elapsed_seconds(started_perf),
            )
            return
    except Exception as exc:
        set_youtube_upload(
            upload_id,
            status="failed",
            logs=logs[-160:],
            error=str(exc),
            finished_at=now_iso(),
            duration_seconds=elapsed_seconds(started_perf),
        )
    finally:
        with process_lock:
            youtube_upload_processes.pop(upload_id, None)


def youtube_upload_worker_loop() -> None:
    global youtube_worker_running
    while True:
        with youtube_uploads_lock:
            queued = [
                upload
                for upload in sorted(youtube_uploads.values(), key=lambda item: item.created_at)
                if upload.status == "queued"
            ]
        if queued:
            run_youtube_upload(queued[0].id)
            continue

        with youtube_worker_lock:
            with youtube_uploads_lock:
                still_queued = any(upload.status == "queued" for upload in youtube_uploads.values())
            if still_queued:
                continue
            youtube_worker_running = False
            return


def start_youtube_worker_if_needed() -> None:
    global youtube_worker_running
    with youtube_worker_lock:
        if youtube_worker_running:
            return
        youtube_worker_running = True
    threading.Thread(target=youtube_upload_worker_loop, daemon=True).start()


@app.on_event("startup")
def resume_queued_youtube_uploads() -> None:
    with youtube_uploads_lock:
        has_queued = any(upload.status == "queued" for upload in youtube_uploads.values())
    if has_queued:
        start_youtube_worker_if_needed()


def discover_clips(started_at: float) -> list[ClipFile]:
    clips: list[ClipFile] = []
    for path in OUTPUTS_DIR.rglob("clips/*.mp4"):
        if path.stat().st_mtime + 1 < started_at:
            continue
        thumb_path = path.with_name(f"{path.stem}_thumb.jpg")
        prompt_path = path.with_name(f"{path.stem}_thumb.txt")
        caption_path = path.with_name(f"{path.stem}_caption.txt")
        json_path = path.with_suffix(".json")
        title: str | None = None
        sidecar: dict[str, Any] = {}
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                sidecar = payload if isinstance(payload, dict) else {}
                candidate_title = payload.get("title") if isinstance(payload, dict) else None
                if isinstance(candidate_title, str) and candidate_title.strip():
                    title = candidate_title.strip()
            except (OSError, json.JSONDecodeError):
                title = None
                sidecar = {}
        def sidecar_list(key: str) -> list[str]:
            value = sidecar.get(key)
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if isinstance(item, str) and item.strip()][:4]

        raw_score = sidecar.get("score")
        fyp_score = (
            max(1, min(100, int(round(raw_score))))
            if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool)
            else None
        )
        clips.append(
            ClipFile(
                name=path.name,
                url=clip_url(path),
                size_bytes=path.stat().st_size,
                title=title,
                thumbnail_url=clip_url(thumb_path) if thumb_path.exists() else None,
                thumbnail_prompt=(
                    prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else None
                ),
                social_caption=(
                    caption_path.read_text(encoding="utf-8") if caption_path.exists() else None
                ),
                fyp_score=fyp_score,
                fyp_label=(
                    str(sidecar.get("fyp_label")).strip()
                    if sidecar.get("fyp_label")
                    else None
                ),
                fyp_reason=(
                    str(sidecar.get("reason")).strip()
                    if sidecar.get("reason")
                    else None
                ),
                hook=str(sidecar.get("hook")).strip() if sidecar.get("hook") else None,
                pov=str(sidecar.get("pov")).strip() if sidecar.get("pov") else None,
                strengths=sidecar_list("strengths"),
                weaknesses=sidecar_list("weaknesses"),
                improvement_ideas=sidecar_list("improvement_ideas"),
                applied_edits=sidecar_list("applied_edits"),
                output_resolution=(
                    str(sidecar.get("output_resolution")).strip()
                    if sidecar.get("output_resolution")
                    else None
                ),
            )
        )
    clips.sort(key=lambda item: item.name)
    return clips


def discover_candidates(started_at: float) -> list[ClipCandidate]:
    candidate_files = [
        path
        for path in OUTPUTS_DIR.rglob("candidates*.json")
        if path.stat().st_mtime + 1 >= started_at
    ]
    if not candidate_files:
        return []

    latest = max(candidate_files, key=lambda path: path.stat().st_mtime)
    payload = json.loads(latest.read_text(encoding="utf-8"))
    return [ClipCandidate(**item) for item in payload]


def set_job(job_id: str, **updates) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return
        data = job.model_dump()
        data.update(updates)
        data["updated_at"] = now_iso()
        jobs[job_id] = ClipJob(**data)
        save_jobs_unlocked()


def finish_job_updates(started_perf: float) -> dict[str, str | float]:
    return {
        "finished_at": now_iso(),
        "duration_seconds": elapsed_seconds(started_perf),
    }


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def ytdlp_probe_options() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 15,
        "retries": 2,
        "extractor_retries": 2,
        "http_headers": YTDLP_HTTP_HEADERS,
        "source_address": "0.0.0.0",
    }


def is_network_error(message: str) -> bool:
    lowered = message.lower()
    return any(pattern in lowered for pattern in NETWORK_ERROR_PATTERNS)


def friendly_network_error() -> str:
    return (
        "Koneksi server ke YouTube tidak tersedia. "
        "Pastikan server/container punya akses internet keluar, atau gunakan tab Upload Video."
    )


def user_error_from_logs(logs: list[str]) -> str | None:
    for line in reversed(logs):
        if CLI_USER_ERROR_PREFIX in line:
            return line.split(CLI_USER_ERROR_PREFIX, 1)[1].strip()
    for line in reversed(logs):
        if is_network_error(line):
            return friendly_network_error()
    combined = "\n".join(logs[-120:]).lower()
    if "no such filter: 'drawtext'" in combined or "no such filter: 'subtitles'" in combined:
        return (
            "FFmpeg backend belum memiliki filter teks/subtitle yang dibutuhkan. "
            "Build ulang container backend agar memakai FFmpeg sistem lengkap."
        )
    if "error initializing a simple filtergraph" in combined or "filter not found" in combined:
        return "Filter video FFmpeg tidak tersedia atau tidak kompatibel. Build ulang backend lalu coba lagi."
    return None


def fetch_video_duration(url: str) -> float | None:
    try:
        with YoutubeDL(ytdlp_probe_options()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    duration = info.get("duration") if isinstance(info, dict) else None
    return float(duration) if duration else None


def probe_media_duration(path: Path) -> float | None:
    try:
        import cv2
    except Exception:
        return None
    capture = cv2.VideoCapture(str(path.resolve()))
    if not capture.isOpened():
        return None
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    capture.release()
    if fps and frames and fps > 0:
        return float(frames) / float(fps)
    return None


def max_clips_for_duration(duration: float | None, min_duration: float) -> int | None:
    # Guarantee target clips can fit without overlap inside 80% of the video.
    if not duration or min_duration <= 0:
        return None
    return max(1, int((duration * CLIP_BUDGET_RATIO) // min_duration))


def choose_auto_top(duration: float | None) -> int:
    if not duration:
        return MIN_AUTO_CLIPS + 3
    return clamp(ceil(duration / SECONDS_PER_TARGET_CLIP), MIN_AUTO_CLIPS, MAX_AUTO_CLIPS)


def choose_auto_analyze_seconds(duration: float | None) -> float | None:
    if not duration or duration <= FULL_ANALYSIS_LIMIT_SECONDS:
        return None
    return min(MAX_AUTO_ANALYSIS_SECONDS, max(FULL_ANALYSIS_LIMIT_SECONDS, duration * LONG_VIDEO_ANALYSIS_RATIO))


def cleanup_job_artifacts(started_at: float) -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for item in OUTPUTS_DIR.iterdir():
        try:
            if item.stat().st_mtime + 2 < started_at:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def cancel_process(job_id: str) -> bool:
    cancelled_job_ids.add(job_id)
    with process_lock:
        process = job_processes.get(job_id)

    if process is None or process.poll() is not None:
        return False

    process.terminate()
    try:
        process.wait(timeout=CANCEL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=CANCEL_GRACE_SECONDS)
    return True


def normalize_job_request(request: ClipJobRequest) -> ClipJobRequest:
    if request.source_file:
        duration = probe_media_duration(Path(request.source_file))
    else:
        duration = fetch_video_duration(request.url)
    data = request.model_dump()

    if request.top is None:
        data["top"] = choose_auto_top(duration)

    # Enforce: min_duration * target_clips <= 80% of the video length.
    budget_cap = max_clips_for_duration(duration, request.min_duration)
    if budget_cap is not None and data["top"] is not None:
        data["top"] = max(1, min(int(data["top"]), MAX_REQUESTED_CLIPS, budget_cap))
    elif data["top"] is not None:
        data["top"] = max(1, min(int(data["top"]), MAX_REQUESTED_CLIPS))

    if request.analyze_seconds is None:
        data["analyze_seconds"] = choose_auto_analyze_seconds(duration)

    if request.ai_enabled:
        data["ai_base_url"] = (request.ai_base_url or DEFAULT_AI_BASE_URL).strip()
        if not request.ai_model.strip():
            models = load_models_from_base(
                data["ai_base_url"],
                api_key=request.ai_api_key,
                timeout=4,
            )
            if models:
                data["ai_model"] = models[0]

    return ClipJobRequest(**data)


def build_clipper_command(request: ClipJobRequest) -> list[str]:
    command = [sys.executable, "clipper.py"]
    if request.source_file:
        command.extend(["--source-file", request.source_file])
    else:
        command.append(request.url)
    command.extend(
        [
            "--top",
            str(request.top or choose_auto_top(None)),
            "--min",
            str(request.min_duration),
            "--max",
            str(request.max_duration),
            "--clip-mode",
            request.clip_mode,
            "--compilation-target",
            str(request.compilation_target_seconds),
            "--model",
            request.model,
            "--language",
            request.language,
        ]
    )

    if request.analyze_seconds:
        command.extend(["--analyze-seconds", str(request.analyze_seconds)])
    command.extend(["--video-quality", request.video_quality])
    if not request.burn_subtitles:
        command.append("--no-burn-subtitles")
    if not request.enhanced_edit:
        command.append("--no-enhanced-edit")
    if not request.remove_running_text:
        command.append("--keep-running-text")
    command.extend(["--crop-mode", request.crop_mode])
    command.extend(["--cam-corner", request.cam_corner])
    command.extend(["--caption-font-size", str(request.caption_font_size)])
    command.extend(["--caption-position", request.caption_position])
    command.extend(["--caption-color", request.caption_color])
    command.extend(["--caption-font", request.caption_font])
    command.extend(["--caption-outline", str(request.caption_outline)])
    command.extend(["--caption-outline-color", request.caption_outline_color])
    if request.required_hashtags:
        cleaned = [tag.strip().lstrip("#") for tag in request.required_hashtags if tag.strip()]
        if cleaned:
            command.extend(["--required-hashtags", ",".join(cleaned)])
    if request.url:
        command.append("--require-creative-commons")

    if request.ai_enabled:
        command.append("--ai-enabled")
        if request.ai_base_url:
            command.extend(["--ai-base-url", request.ai_base_url])
        if request.ai_model:
            command.extend(["--ai-model", request.ai_model])
        if request.ai_api_key:
            command.extend(["--ai-api-key", request.ai_api_key])
    return command


def run_job(job_id: str) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            cancelled_job_ids.discard(job_id)
            preserve_job_files_on_cancel.discard(job_id)
            job_secrets.pop(job_id, None)
            return
        request = job.request

    secret = job_secrets.get(job_id)
    if secret:
        request = request.model_copy(update={"ai_api_key": secret})

    started_at = time.time()
    started_perf = time.perf_counter()
    started_at_iso = now_iso()
    if job_id in cancelled_job_ids:
        set_job(
            job_id,
            status="cancelled",
            started_at=started_at_iso,
            **finish_job_updates(started_perf),
            clips=[],
            candidates=[],
            error="Proses dibatalkan sebelum worker berjalan.",
        )
        cancelled_job_ids.discard(job_id)
        preserve_job_files_on_cancel.discard(job_id)
        job_secrets.pop(job_id, None)
        return

    set_job(
        job_id,
        status="running",
        started_at=started_at_iso,
        finished_at=None,
        duration_seconds=None,
        error=None,
    )
    command = build_clipper_command(request)

    process = subprocess.Popen(
        command,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    with process_lock:
        job_processes[job_id] = process

    logs: list[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            cleaned = line.rstrip()
            if cleaned:
                logs.append(cleaned)
                set_job(job_id, logs=logs[-120:])

        code = process.wait()
        if job_id in cancelled_job_ids:
            preserve_files = job_id in preserve_job_files_on_cancel
            removed = 0 if preserve_files else cleanup_job_artifacts(started_at)
            error = (
                "Proses dibatalkan dan catatan job dihapus. File output tidak dihapus."
                if preserve_files
                else f"Proses dibatalkan. {removed} data output sementara dihapus."
            )
            set_job(
                job_id,
                status="cancelled",
                **finish_job_updates(started_perf),
                clips=[],
                candidates=[],
                logs=logs[-120:],
                error=error,
            )
            return

        clips = discover_clips(started_at)
        candidates = discover_candidates(started_at)
        if clips and candidates:
            clips = enrich_clips_with_candidate_titles(clips, candidates)
        if code == 0:
            updates = {"status": "completed", "logs": logs[-120:], **finish_job_updates(started_perf)}
            if clips:
                updates["clips"] = clips
            if candidates:
                updates["candidates"] = candidates
            preview_job = ClipJob(
                id=job_id,
                status="completed",
                request=request,
                created_at=now_iso(),
                updated_at=now_iso(),
                clips=clips,
                candidates=candidates,
            )
            preview_job = enrich_job_source_metadata(preview_job)
            if preview_job.source_title:
                updates["source_title"] = preview_job.source_title
            if preview_job.source_url:
                updates["source_url"] = preview_job.source_url
            if preview_job.source_uploader:
                updates["source_uploader"] = preview_job.source_uploader
            set_job(job_id, **updates)
            remember_processed_source(preview_job.source_url or request.url)
            if request.auto_upload_youtube:
                auto_queue_youtube_uploads_for_job(job_id, logs)
        else:
            friendly_error = user_error_from_logs(logs)
            set_job(
                job_id,
                status="failed",
                **finish_job_updates(started_perf),
                clips=clips,
                candidates=candidates,
                logs=logs[-120:],
                error=friendly_error or f"clipper.py exited with code {code}",
            )
    finally:
        with process_lock:
            job_processes.pop(job_id, None)
        job_secrets.pop(job_id, None)
        cancelled_job_ids.discard(job_id)
        preserve_job_files_on_cancel.discard(job_id)

        # An uploaded source is only needed during processing; remove it afterwards
        # so large videos don't accumulate in uploads/.
        if request.source_file:
            upload_path = resolve_upload_path(request.source_file)
            if upload_path is not None:
                try:
                    upload_path.unlink()
                except OSError:
                    pass


def update_auto_viral_run(run_id: str, **updates) -> None:
    with auto_viral_lock:
        current = auto_viral_runs.get(run_id)
        if current is None:
            return
        data = current.model_dump()
        data.update(updates)
        data["updated_at"] = now_iso()
        auto_viral_runs[run_id] = AutoViralRun(**data)


def append_auto_viral_log(run_id: str, message: str) -> None:
    with auto_viral_lock:
        current = auto_viral_runs.get(run_id)
        if current is None:
            return
        logs = [*current.logs, f"{datetime.now().strftime('%H:%M:%S')} {message}"][-160:]
        auto_viral_runs[run_id] = current.model_copy(update={"logs": logs, "updated_at": now_iso()})


def append_auto_viral_error(run_id: str, message: str) -> None:
    with auto_viral_lock:
        current = auto_viral_runs.get(run_id)
        if current is None:
            return
        errors = [*current.errors, message][-80:]
        logs = [*current.logs, f"{datetime.now().strftime('%H:%M:%S')} ERROR: {message}"][-160:]
        auto_viral_runs[run_id] = current.model_copy(update={"errors": errors, "logs": logs, "updated_at": now_iso()})


def youtube_watch_url(info: dict[str, Any]) -> str:
    webpage_url = info.get("webpage_url")
    if isinstance(webpage_url, str) and webpage_url.startswith("http"):
        return webpage_url
    url = info.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    video_id = str(info.get("id") or "").strip()
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else ""


def is_creative_commons_info(info: dict[str, Any]) -> bool:
    license_text = str(info.get("license") or "").lower()
    return "creative commons" in license_text or "cc-by" in license_text or "reuse allowed" in license_text


def upload_age_days(info: dict[str, Any]) -> int | None:
    raw = str(info.get("upload_date") or "")
    if not re.fullmatch(r"\d{8}", raw):
        return None
    try:
        uploaded = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - uploaded).days)


def is_fresh_viral_upload(info: dict[str, Any], max_age_days: int = FRESH_VIRAL_MAX_AGE_DAYS) -> bool:
    age_days = upload_age_days(info)
    return age_days is not None and age_days <= min(max_age_days, MAX_VIRAL_FALLBACK_AGE_DAYS)


def youtube_published_after(max_age_days: int = FRESH_VIRAL_MAX_AGE_DAYS) -> str:
    safe_days = min(max(1, max_age_days), MAX_VIRAL_FALLBACK_AGE_DAYS)
    threshold = datetime.now(timezone.utc) - timedelta(days=safe_days)
    return threshold.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def auto_viral_candidate_score(info: dict[str, Any]) -> float:
    views = max(0, int(info.get("view_count") or 0))
    likes = max(0, int(info.get("like_count") or 0))
    duration = float(info.get("duration") or 0)
    age_days = upload_age_days(info)
    effective_age = max(1, age_days if age_days is not None else FRESH_VIRAL_MAX_AGE_DAYS)
    views_per_day = views / effective_age
    view_score = log10(views + 1) * 22
    velocity_score = log10(views_per_day + 1) * 28
    like_score = log10(likes + 1) * 10
    recency_score = max(5, 35 - min(effective_age, FRESH_VIRAL_MAX_AGE_DAYS))
    duration_score = 15 if 180 <= duration <= 1800 else 8 if 60 <= duration <= 3600 else 0
    return round(view_score + velocity_score + like_score + recency_score + duration_score, 2)


def compact_source_payload(info: dict[str, Any]) -> dict[str, Any]:
    age_days = upload_age_days(info)
    views = int(info.get("view_count") or 0)
    return {
        "url": normalize_youtube_video_url(youtube_watch_url(info)) or youtube_watch_url(info),
        "title": str(info.get("title") or "Video tanpa judul")[:180],
        "uploader": str(info.get("uploader") or "")[:120],
        "duration": info.get("duration"),
        "views": views,
        "views_per_day": round(views / max(1, age_days or 1)),
        "age_days": age_days,
        "likes": info.get("like_count"),
        "upload_date": info.get("upload_date"),
        "license": info.get("license"),
        "score": auto_viral_candidate_score(info),
    }


def fetch_youtube_metadata(url: str) -> dict[str, Any]:
    with YoutubeDL(ytdlp_probe_options()) as ydl:
        result = ydl.extract_info(url, download=False)
    return result if isinstance(result, dict) else {}


def parse_youtube_iso_duration(value: str) -> int:
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value or "",
    )
    if not match:
        return 0
    return (
        int(match.group("days") or 0) * 86400
        + int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )


def youtube_data_api_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("YOUTUBE_DATA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("YOUTUBE_DATA_API_KEY belum diset")
    clean_params = {key: value for key, value in params.items() if value not in {None, ""}}
    clean_params["key"] = api_key
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urlencode(clean_params)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.reason
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                message = error.get("message")
                errors = error.get("errors")
                reason = ""
                if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                    reason = str(errors[0].get("reason") or "")
                detail = f"{message or detail}" + (f" ({reason})" if reason else "")
        except Exception:
            pass
        raise RuntimeError(f"YouTube Data API HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"YouTube Data API request gagal: {exc}") from exc


def youtube_data_api_video_payload(item: dict[str, Any]) -> dict[str, Any]:
    video_id = str(item.get("id") or "")
    snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
    stats = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    content = item.get("contentDetails") if isinstance(item.get("contentDetails"), dict) else {}
    status = item.get("status") if isinstance(item.get("status"), dict) else {}
    published_at = str(snippet.get("publishedAt") or "")
    upload_date = re.sub(r"[^0-9]", "", published_at[:10])
    license_value = str(status.get("license") or "")
    return {
        "id": video_id,
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "title": snippet.get("title") or "Video tanpa judul",
        "uploader": snippet.get("channelTitle") or "",
        "duration": parse_youtube_iso_duration(str(content.get("duration") or "")),
        "view_count": int(stats.get("viewCount") or 0),
        "like_count": int(stats.get("likeCount") or 0),
        "upload_date": upload_date if len(upload_date) == 8 else "",
        "license": "Creative Commons" if license_value == "creativeCommon" else license_value,
    }


def search_youtube_data_api_viral_sources(
    request: AutoViralRequest,
    run_id: str,
    *,
    exclude_urls: set[str] | None = None,
    stop_after: int | None = None,
) -> list[dict[str, Any]]:
    if not os.environ.get("YOUTUBE_DATA_API_KEY", "").strip():
        return []
    seen: set[str] = set(exclude_urls or set())
    candidates: list[dict[str, Any]] = []
    region_code = os.environ.get("VIRAL_CC_REGION_CODE", "ID").strip() or "ID"
    relevance_language = os.environ.get("VIRAL_CC_RELEVANCE_LANGUAGE", "id").strip() or "id"
    topic_id = os.environ.get("VIRAL_CC_TOPIC_ID", "").strip()
    api_error_count = 0
    api_query_count = 0
    last_api_error = ""
    max_api_queries = max(1, min(20, env_int("VIRAL_CC_MAX_API_QUERIES", 12)))
    for query in request.queries[:max_api_queries]:
        if stop_after is not None and len(candidates) >= stop_after:
            break
        append_auto_viral_log(run_id, f"YouTube Data API search: {query}")
        search_params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoLicense": "creativeCommon",
            "order": os.environ.get("VIRAL_CC_YOUTUBE_API_ORDER", "viewCount").strip() or "viewCount",
            "maxResults": request.search_limit_per_query,
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
            "safeSearch": "moderate",
            "publishedAfter": youtube_published_after(request.max_age_days),
        }
        if topic_id and env_bool("VIRAL_CC_ENFORCE_TOPIC_ID", False):
            search_params["topicId"] = topic_id
        try:
            search_result = youtube_data_api_get("search", search_params)
        except Exception as exc:
            api_error_count += 1
            last_api_error = str(exc)
            append_auto_viral_error(run_id, f"YouTube Data API search gagal untuk '{query}': {exc}")
            continue
        api_query_count += 1
        video_ids: list[str] = []
        for item in search_result.get("items", []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") if isinstance(item.get("id"), dict) else {}
            video_id = str(item_id.get("videoId") or "")
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            normalized_url = normalize_youtube_video_url(url) or url
            if video_id and normalized_url not in seen:
                seen.add(normalized_url)
                video_ids.append(video_id)
        if not video_ids:
            continue
        try:
            detail_result = youtube_data_api_get(
                "videos",
                {
                    "part": "snippet,statistics,contentDetails,status",
                    "id": ",".join(video_ids),
                },
            )
        except Exception as exc:
            api_error_count += 1
            last_api_error = str(exc)
            append_auto_viral_error(run_id, f"YouTube Data API videos.list gagal untuk '{query}': {exc}")
            continue
        for item in detail_result.get("items", []):
            if not isinstance(item, dict):
                continue
            payload = youtube_data_api_video_payload(item)
            duration = float(payload.get("duration") or 0)
            views = int(payload.get("view_count") or 0)
            if duration < request.min_source_duration or duration > request.max_source_duration:
                continue
            if views < request.min_views:
                continue
            if not is_fresh_viral_upload(payload, request.max_age_days):
                continue
            if not is_creative_commons_info(payload):
                continue
            candidates.append(compact_source_payload(payload))
            if stop_after is not None and len(candidates) >= stop_after:
                break
    if api_query_count == 0 and api_error_count > 0:
        raise RuntimeError(last_api_error or "Semua request YouTube Data API gagal")
    candidates.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    return candidates


def search_auto_viral_sources(
    request: AutoViralRequest,
    run_id: str,
    *,
    exclude_urls: set[str] | None = None,
    stop_after: int | None = None,
    max_metadata_checks: int | None = None,
) -> list[dict[str, Any]]:
    seen: set[str] = set(exclude_urls or set())
    candidates: list[dict[str, Any]] = []
    metadata_checks = 0
    max_metadata_per_query = max(
        2,
        min(20, env_int("VIRAL_CC_METADATA_PER_QUERY", 6)),
    )
    search_mode = os.environ.get("VIRAL_CC_YTDLP_SEARCH_MODE", "ytsearchdate").strip().lower()
    if search_mode not in {"ytsearch", "ytsearchdate"}:
        search_mode = "ytsearchdate"
    for query in request.queries:
        if stop_after is not None and len(candidates) >= stop_after:
            break
        if max_metadata_checks is not None and metadata_checks >= max_metadata_checks:
            break
        append_auto_viral_log(run_id, f"Mencari kandidat YouTube: {query}")
        try:
            with YoutubeDL(ytdlp_probe_options()) as ydl:
                result = ydl.extract_info(
                    f"{search_mode}{request.search_limit_per_query}:{query}",
                    download=False,
                )
        except Exception as exc:
            append_auto_viral_error(run_id, f"Search gagal untuk '{query}': {exc}")
            continue

        entries = result.get("entries", []) if isinstance(result, dict) else []
        query_metadata_checks = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = normalize_youtube_video_url(youtube_watch_url(entry)) or youtube_watch_url(entry)
            if not url or url in seen:
                continue
            seen.add(url)
            if max_metadata_checks is not None and metadata_checks >= max_metadata_checks:
                break
            if query_metadata_checks >= max_metadata_per_query:
                break
            metadata_checks += 1
            query_metadata_checks += 1
            try:
                metadata = fetch_youtube_metadata(url)
            except Exception as exc:
                append_auto_viral_error(run_id, f"Metadata gagal untuk {url}: {exc}")
                continue

            duration = float(metadata.get("duration") or 0)
            views = int(metadata.get("view_count") or 0)
            if duration < request.min_source_duration or duration > request.max_source_duration:
                continue
            if views < request.min_views:
                continue
            if not is_fresh_viral_upload(metadata, request.max_age_days):
                append_auto_viral_log(
                    run_id,
                    f"Skip tidak fresh (> {request.max_age_days} hari/tanggal tidak tersedia): "
                    f"{metadata.get('title') or url}",
                )
                continue
            if not is_creative_commons_info(metadata):
                append_auto_viral_log(run_id, f"Skip non-CC: {metadata.get('title') or url}")
                continue
            candidates.append(compact_source_payload(metadata))
            if stop_after is not None and len(candidates) >= stop_after:
                break

    candidates.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    return candidates


def remember_processed_source(value: str) -> None:
    normalized = normalize_youtube_video_url(value)
    if not normalized:
        return
    with processed_source_history_lock:
        if normalized in processed_source_history:
            return
        processed_source_history.add(normalized)
        payload = sorted(processed_source_history)[-5000:]
        processed_source_history.clear()
        processed_source_history.update(payload)
        try:
            temp_path = PROCESSED_SOURCE_HISTORY_PATH.with_suffix(".json.tmp")
            temp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_path.replace(PROCESSED_SOURCE_HISTORY_PATH)
        except OSError as exc:
            print(f"Gagal menyimpan riwayat sumber clipping: {exc}", flush=True)


def processed_job_source_urls() -> set[str]:
    with processed_source_history_lock:
        history = list(processed_source_history)
    excluded: set[str] = {
        normalized
        for value in history
        if (normalized := normalize_youtube_video_url(value))
    }
    with jobs_lock:
        existing_jobs = list(jobs.values())
    for job in existing_jobs:
        for value in (job.request.url, job.source_url):
            normalized = normalize_youtube_video_url(str(value or ""))
            if normalized:
                excluded.add(normalized)
    return excluded


def search_viral_video_sources(request: ViralVideoSearchRequest) -> list[dict[str, Any]]:
    run_id = f"search-{uuid.uuid4().hex}"
    search_request = AutoViralRequest(
        queries=request.queries,
        video_count=request.video_count,
        clips_per_video=1,
        search_limit_per_query=request.search_limit_per_query,
        min_source_duration=request.min_source_duration,
        max_source_duration=request.max_source_duration,
        min_views=request.min_views,
        max_age_days=request.max_age_days,
        top=3,
        min_duration=35,
        max_duration=180,
        video_quality="high",
        crop_mode="person",
        burn_subtitles=True,
        ai_enabled=True,
    )
    run = AutoViralRun(
        id=run_id,
        status="running",
        created_at=now_iso(),
        updated_at=now_iso(),
        request=search_request,
        message="Mencari kandidat CC baru; prioritas 30 hari lalu diperluas bila hasil kurang",
    )
    with auto_viral_lock:
        auto_viral_runs[run_id] = run
    try:
        excluded_urls = {*request.exclude_urls, *processed_job_source_urls()}
        append_auto_viral_log(
            run_id,
            f"Mengecualikan {len(excluded_urls)} sumber yang pernah ditampilkan/diproses.",
        )
        sources: list[dict[str, Any]] = []
        prefer_youtube_api = env_bool("VIRAL_CC_REQUIRE_YOUTUBE_DATA_API", True)
        if prefer_youtube_api and os.environ.get("YOUTUBE_DATA_API_KEY", "").strip():
            try:
                sources = search_youtube_data_api_viral_sources(
                    search_request,
                    run_id,
                    exclude_urls=excluded_urls,
                    stop_after=request.video_count,
                )
            except Exception as exc:
                append_auto_viral_error(
                    run_id,
                    f"YouTube Data API belum memberi hasil; lanjut pencarian yt-dlp: {exc}",
                )
        elif prefer_youtube_api:
            append_auto_viral_log(
                run_id,
                "YouTube Data API key kosong; langsung memakai pencarian yt-dlp terverifikasi.",
            )
        else:
            append_auto_viral_log(run_id, "YouTube Data API dinonaktifkan; memakai pencarian yt-dlp terverifikasi.")

        if len(sources) < request.video_count:
            fallback_age_days = max(
                request.max_age_days,
                min(
                    MAX_VIRAL_FALLBACK_AGE_DAYS,
                    env_int("VIRAL_CC_FALLBACK_MAX_AGE_DAYS", 180),
                ),
            )
            fallback_min_views = min(
                request.min_views,
                max(0, env_int("VIRAL_CC_FALLBACK_MIN_VIEWS", 100)),
            )
            fallback_request = search_request.model_copy(
                update={
                    "queries": default_viral_video_search_queries(),
                    "search_limit_per_query": max(
                        request.search_limit_per_query,
                        min(50, env_int("VIRAL_CC_SEARCH_LIMIT", 25)),
                    ),
                    "min_views": fallback_min_views,
                    "max_age_days": fallback_age_days,
                }
            )
            append_auto_viral_log(
                run_id,
                f"Hasil terbaru baru {len(sources)}/{request.video_count}; memperluas pencarian "
                f"hingga {fallback_age_days} hari, min. {fallback_min_views} views, "
                f"{len(fallback_request.queries)} variasi keyword.",
            )
            found_urls = {
                normalize_youtube_video_url(str(item.get("url") or ""))
                for item in sources
                if normalize_youtube_video_url(str(item.get("url") or ""))
            }
            fallback_sources = search_auto_viral_sources(
                fallback_request,
                run_id,
                exclude_urls={*excluded_urls, *found_urls},
                stop_after=request.video_count - len(sources),
                max_metadata_checks=request.max_metadata_checks,
            )
            sources = [*sources, *fallback_sources]
        selected = sources[: request.video_count]
        update_auto_viral_run(
            run_id,
            status="completed",
            finished_at=now_iso(),
            selected_sources=selected,
            message=f"Menemukan {len(selected)} kandidat video Creative Commons",
        )
        return selected
    except Exception as exc:
        append_auto_viral_error(run_id, str(exc))
        update_auto_viral_run(run_id, status="failed", finished_at=now_iso(), message=str(exc))
        raise


def wait_for_no_active_clipping_job(timeout_seconds: int = 3600) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with jobs_lock:
            has_active = any(job.status in {"queued", "running"} for job in jobs.values())
        if not has_active:
            return
        time.sleep(3)
    raise RuntimeError("Masih ada job clipping aktif terlalu lama")


def create_auto_viral_clip_job(source: dict[str, Any], request: AutoViralRequest) -> ClipJob:
    wait_for_no_active_clipping_job()
    job_request = ClipJobRequest(
        url=str(source["url"]),
        top=request.top,
        min_duration=request.min_duration,
        max_duration=request.max_duration,
        video_quality=request.video_quality,
        burn_subtitles=request.burn_subtitles,
        crop_mode=request.crop_mode,
        require_creative_commons=True,
        auto_upload_youtube=False,
        ai_enabled=request.ai_enabled,
        ai_base_url=request.ai_base_url,
        ai_model=request.ai_model,
        ai_api_key=request.ai_api_key,
    )
    if job_request.max_duration <= job_request.min_duration:
        raise RuntimeError("max_duration must be greater than min_duration")
    job_request = normalize_job_request(job_request)
    secret = job_request.ai_api_key
    job_id = uuid.uuid4().hex
    if secret:
        job_secrets[job_id] = secret
    job_request = job_request.model_copy(update={"ai_api_key": ""})
    job = ClipJob(
        id=job_id,
        status="queued",
        request=job_request,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    with jobs_lock:
        if any(item.status in {"queued", "running"} for item in jobs.values()):
            job_secrets.pop(job_id, None)
            raise RuntimeError("Proses clipping lain baru saja dimulai")
        jobs[job_id] = job
        save_jobs_unlocked()
    return job


def wait_for_uploads(upload_ids: list[str], timeout_seconds: int = 7200) -> list[YouTubeUploadJob]:
    terminal = {"completed", "failed", "cancelled"}
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with youtube_uploads_lock:
            uploads = [youtube_uploads[upload_id] for upload_id in upload_ids if upload_id in youtube_uploads]
        if len(uploads) == len(upload_ids) and all(upload.status in terminal for upload in uploads):
            return uploads
        time.sleep(5)
    raise RuntimeError("Upload YouTube belum selesai sampai batas waktu")


def send_telegram_alert(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("AUTO_VIRAL_TELEGRAM_CHAT_ID", os.environ.get("TELEGRAM_OWNER_ID", "")).strip()
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = [text[index:index + 3800] for index in range(0, len(text), 3800)] or [text]
    for chunk in chunks:
        payload = json.dumps({"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}).encode("utf-8")
        request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=15):
            pass


def auto_viral_summary(run: AutoViralRun) -> str:
    lines = [
        "Auto Viral Creative Commons selesai",
        f"Run: {run.id}",
        f"Status: {run.status}",
        f"Target: {run.request.video_count} video, {run.request.clips_per_video} clip/video",
        f"Sukses: {sum(1 for item in run.processed if item.get('status') == 'completed')}",
        "",
        "Sumber dipilih:",
    ]
    for index, source in enumerate(run.selected_sources[: run.request.video_count], start=1):
        lines.append(
            f"{index}. {source.get('title')} | score {source.get('score')} | views {source.get('views')} | {source.get('url')}"
        )
    lines.append("")
    lines.append("Hasil proses:")
    for index, item in enumerate(run.processed, start=1):
        uploads = item.get("uploads") if isinstance(item.get("uploads"), list) else []
        lines.append(
            f"{index}. {item.get('title')} | {item.get('status')} | clips {item.get('clip_count')} | uploaded {len(uploads)} | cleanup {item.get('cleanup') or '-'}"
        )
        for upload in uploads[:5]:
            lines.append(f"   - {upload.get('status')}: {upload.get('title')} {upload.get('video_url') or ''}")
        if item.get("error"):
            lines.append(f"   Error: {item.get('error')}")
    if run.errors:
        lines.append("")
        lines.append("Catatan error:")
        lines.extend(f"- {error}" for error in run.errors[-10:])
    return "\n".join(lines)[:12000]


def run_auto_viral_campaign(run_id: str) -> None:
    global auto_viral_active_run_id
    try:
        with auto_viral_lock:
            run = auto_viral_runs[run_id]
        update_auto_viral_run(
            run_id,
            status="running",
            message="Mencari video Creative Commons viral; prioritas 30 hari, lalu perluas hingga 180 hari",
        )
        append_auto_viral_log(run_id, "Automation dimulai")
        try:
            require_youtube_ready()
        except HTTPException as exc:
            raise RuntimeError(str(exc.detail)) from exc

        source_pool_target = max(run.request.video_count * 3, run.request.video_count)
        excluded_sources = processed_job_source_urls()
        append_auto_viral_log(
            run_id,
            f"Mengecualikan {len(excluded_sources)} sumber yang sudah pernah masuk proses clipping",
        )
        sources = search_auto_viral_sources(
            run.request,
            run_id,
            exclude_urls=excluded_sources,
            stop_after=source_pool_target,
            max_metadata_checks=env_int("VIRAL_CC_MAX_METADATA_CHECKS", 200),
        )
        if len(sources) < source_pool_target:
            fallback_age_days = max(
                run.request.max_age_days,
                min(
                    MAX_VIRAL_FALLBACK_AGE_DAYS,
                    env_int("VIRAL_CC_FALLBACK_MAX_AGE_DAYS", 180),
                ),
            )
            fallback_min_views = min(
                run.request.min_views,
                max(0, env_int("VIRAL_CC_FALLBACK_MIN_VIEWS", 100)),
            )
            fallback_request = run.request.model_copy(
                update={
                    "queries": default_auto_viral_queries(),
                    "search_limit_per_query": max(run.request.search_limit_per_query, 25),
                    "min_views": fallback_min_views,
                    "max_age_days": fallback_age_days,
                }
            )
            append_auto_viral_log(
                run_id,
                f"Kandidat baru belum cukup; memperluas pencarian hingga {fallback_age_days} hari "
                f"dengan minimal {fallback_min_views} views",
            )
            update_auto_viral_run(
                run_id,
                message=f"Memperluas pencarian Creative Commons hingga {fallback_age_days} hari",
            )
            sources.extend(
                search_auto_viral_sources(
                    fallback_request,
                    run_id,
                    exclude_urls=excluded_sources | {
                        normalized
                        for source in sources
                        if (normalized := normalize_youtube_video_url(str(source.get("url") or "")))
                    },
                    stop_after=source_pool_target - len(sources),
                    max_metadata_checks=env_int("VIRAL_CC_MAX_METADATA_CHECKS", 200),
                )
            )
            sources.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        if not sources:
            raise RuntimeError(
                "Tidak menemukan kandidat Creative Commons setelah pencarian diperluas; "
                "semua sumber yang pernah diproses tetap dilewati"
            )
        update_auto_viral_run(run_id, selected_sources=sources[: max(run.request.video_count, 1) * 3])

        completed_count = 0
        processed: list[dict[str, Any]] = []
        for source in sources:
            if completed_count >= run.request.video_count:
                break
            append_auto_viral_log(run_id, f"Mulai clipping: {source.get('title')}")
            item: dict[str, Any] = {
                "source": source,
                "title": source.get("title"),
                "url": source.get("url"),
                "status": "running",
            }
            try:
                job = create_auto_viral_clip_job(source, run.request)
                item["job_id"] = job.id
                run_job(job.id)
                with jobs_lock:
                    finished_job = jobs.get(job.id)
                if finished_job is None:
                    raise RuntimeError("Job hilang setelah clipping")
                item["job_status"] = finished_job.status
                item["clip_count"] = len(finished_job.clips)
                if finished_job.status != "completed" or not finished_job.clips:
                    raise RuntimeError(finished_job.error or f"Job selesai dengan status {finished_job.status}")

                uploads = create_youtube_upload_batch_records(
                    finished_job.id,
                    YouTubeBatchUploadRequest(best_count=run.request.clips_per_video),
                )
                queue_youtube_upload_jobs(uploads)
                append_auto_viral_log(run_id, f"{len(uploads)} upload YouTube masuk antrean untuk job {finished_job.id[:10]}")
                finished_uploads = wait_for_uploads([upload.id for upload in uploads])
                item["uploads"] = [
                    {
                        "id": upload.id,
                        "status": upload.status,
                        "title": upload.title,
                        "video_url": upload.video_url,
                        "error": upload.error,
                    }
                    for upload in finished_uploads
                ]
                if not finished_uploads or any(upload.status != "completed" for upload in finished_uploads):
                    failed = [upload.error or upload.status for upload in finished_uploads if upload.status != "completed"]
                    raise RuntimeError("Upload belum sukses semua: " + "; ".join(failed))

                cleanup = delete_all_job_clips(finished_job.id)
                item["cleanup"] = f"{cleanup.removed_clips} clip dihapus"
                item["status"] = "completed"
                completed_count += 1
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = str(exc)
                append_auto_viral_error(run_id, f"{source.get('title')}: {exc}")
            processed.append(item)
            update_auto_viral_run(run_id, processed=processed, message=f"{completed_count}/{run.request.video_count} video sukses")

        if completed_count < run.request.video_count:
            raise RuntimeError(f"Hanya {completed_count}/{run.request.video_count} video yang berhasil clip dan upload")

        with auto_viral_lock:
            run = auto_viral_runs[run_id]
        update_auto_viral_run(run_id, status="completed", finished_at=now_iso(), message="Automation selesai")
        with auto_viral_lock:
            final_run = auto_viral_runs[run_id]
        try:
            send_telegram_alert(auto_viral_summary(final_run))
        except Exception as telegram_exc:
            append_auto_viral_error(run_id, f"Telegram alert gagal: {telegram_exc}")
    except Exception as exc:
        append_auto_viral_error(run_id, str(exc))
        update_auto_viral_run(run_id, status="failed", finished_at=now_iso(), message=str(exc))
        with auto_viral_lock:
            failed_run = auto_viral_runs[run_id]
        try:
            send_telegram_alert(auto_viral_summary(failed_run))
        except Exception as telegram_exc:
            append_auto_viral_error(run_id, f"Telegram alert gagal: {telegram_exc}")
    finally:
        with auto_viral_lock:
            if auto_viral_active_run_id == run_id:
                auto_viral_active_run_id = None


@app.post("/api/automation/viral-cc", response_model=AutoViralRun)
def start_auto_viral_campaign(request: AutoViralRequest) -> AutoViralRun:
    global auto_viral_active_run_id
    if request.max_duration <= request.min_duration:
        raise HTTPException(status_code=400, detail="max_duration must be greater than min_duration")
    with auto_viral_lock:
        if auto_viral_active_run_id:
            active = auto_viral_runs.get(auto_viral_active_run_id)
            if active and active.status in {"queued", "running"}:
                raise HTTPException(status_code=409, detail=f"Automation masih berjalan: {active.id}")
        run_id = uuid.uuid4().hex
        run = AutoViralRun(
            id=run_id,
            status="queued",
            created_at=now_iso(),
            updated_at=now_iso(),
            request=request,
            message="Menunggu worker automation",
        )
        auto_viral_runs[run_id] = run
        auto_viral_active_run_id = run_id
    threading.Thread(target=run_auto_viral_campaign, args=(run_id,), daemon=True).start()
    return run


@app.get("/api/automation/viral-cc", response_model=list[AutoViralRun])
def list_auto_viral_campaigns() -> list[AutoViralRun]:
    with auto_viral_lock:
        return sorted(auto_viral_runs.values(), key=lambda item: item.created_at, reverse=True)


@app.post("/api/automation/viral-cc/sources")
def search_viral_cc_sources(request: ViralVideoSearchRequest) -> list[dict[str, Any]]:
    try:
        return search_viral_video_sources(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gagal mencari video viral Creative Commons: {exc}") from exc


@app.get("/api/automation/viral-cc/{run_id}", response_model=AutoViralRun)
def get_auto_viral_campaign(run_id: str) -> AutoViralRun:
    with auto_viral_lock:
        run = auto_viral_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Automation run not found")
    return run


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/youtube/config", response_model=YouTubeConfig)
def get_youtube_config() -> YouTubeConfig:
    return youtube_config_payload()


@app.post("/api/youtube/upload-mode/direct-profile", response_model=YouTubeConfig)
def enable_youtube_direct_profile_upload() -> YouTubeConfig:
    os.environ["YOUTUBE_UPLOAD_USE_CDP"] = "false"
    os.environ["YOUTUBE_UPLOAD_FORCE_CDP"] = "false"
    os.environ["YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD"] = "true"
    os.environ["YOUTUBE_UPLOAD_PREFER_CHROMIUM_PROFILE"] = "true"
    return youtube_config_payload()


@app.post("/api/youtube/upload-mode/live-chrome", response_model=YouTubeConfig)
def enable_youtube_live_chrome_upload(request: YouTubeLiveChromeRequest) -> YouTubeConfig:
    global YOUTUBE_CDP_URL
    if not youtube_cdp_ready(request.cdp_url):
        raise HTTPException(status_code=409, detail=f"Chrome login belum aktif di {request.cdp_url}")
    YOUTUBE_CDP_URL = request.cdp_url
    os.environ["YOUTUBE_CDP_URL"] = request.cdp_url
    os.environ["YOUTUBE_UPLOAD_USE_CDP"] = "true"
    os.environ["YOUTUBE_UPLOAD_FORCE_CDP"] = "true"
    os.environ["YOUTUBE_UPLOAD_PREFER_CHROMIUM_PROFILE"] = "false"
    return youtube_config_payload()


def enable_youtube_storage_state_upload_mode() -> None:
    os.environ["YOUTUBE_UPLOAD_USE_CDP"] = "false"
    os.environ["YOUTUBE_UPLOAD_FORCE_CDP"] = "false"
    os.environ["YOUTUBE_UPLOAD_PREFER_CHROMIUM_PROFILE"] = "false"


@app.get("/api/youtube/uploads", response_model=list[YouTubeUploadJob])
def list_youtube_uploads() -> list[YouTubeUploadJob]:
    with youtube_uploads_lock:
        return sorted(youtube_uploads.values(), key=lambda item: item.created_at, reverse=True)


@app.get("/api/youtube/uploads/{upload_id}", response_model=YouTubeUploadJob)
def get_youtube_upload(upload_id: str) -> YouTubeUploadJob:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="YouTube upload not found")
    return upload


@app.get("/api/youtube/login", response_model=YouTubeLoginStatus)
def get_youtube_login_status() -> YouTubeLoginStatus:
    return youtube_login_status


@app.post("/api/youtube/login/start", response_model=YouTubeLoginStatus)
def start_youtube_login() -> YouTubeLoginStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    return start_youtube_login_if_needed()


@app.post("/api/youtube/login/stop", response_model=YouTubeLoginStatus)
def stop_youtube_login() -> YouTubeLoginStatus:
    global youtube_login_process, youtube_login_reconnect_cdp
    with process_lock:
        process = youtube_login_process
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    with process_lock:
        youtube_login_process = None
        youtube_login_reconnect_cdp = False
    set_youtube_login_status(active=False, finished_at=now_iso(), error=None)
    return youtube_login_status


@app.post("/api/youtube/session/capture", response_model=YouTubeLoginStatus)
def capture_youtube_session() -> YouTubeLoginStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")

    code, logs, error = run_youtube_capture_once()
    if code != 0 and error and (youtube_cdp_start_needed(error) or youtube_login_refresh_needed(error)):
        try:
            force_restart = youtube_login_refresh_needed(error)
            refresh_status = start_youtube_cdp_refresh_process(
                force_profile_refresh=True,
                force_restart=force_restart,
            )
            logs = [
                *logs[-68:],
                (
                    "CDP belum aktif; backend menjalankan launcher Chrome otomatis di background."
                    if youtube_cdp_start_needed(error)
                    else "Session perlu refresh; backend menjalankan launcher Chrome otomatis di background."
                ),
                refresh_status.message,
            ]
            code, retry_logs, error = run_youtube_capture_once()
            logs = [*logs, *retry_logs]
        except HTTPException:
            raise
    status = YouTubeLoginStatus(
        active=False,
        started_at=now_iso(),
        finished_at=now_iso(),
        error=error or (f"capture-session exited with code {code}" if code else None),
        logs=logs[-80:],
    )
    if code != 0:
        if youtube_upload_uses_cdp() and youtube_auth_state_exists() and error and youtube_login_refresh_needed(error):
            hydrate_logs = [
                *logs[-77:],
                f"CDP belum membaca login akun target, tetapi storage-state tersedia: {YOUTUBE_PLAYWRIGHT_STATE}",
                "Upload tetap dapat dilanjutkan; backend akan hydrate cookie storage-state ke Chrome CDP saat upload.",
                "SYNC_READY_WITH_STORAGE_STATE_HYDRATE",
            ]
            return YouTubeLoginStatus(
                active=False,
                started_at=status.started_at,
                finished_at=status.finished_at,
                error=None,
                logs=hydrate_logs[-80:],
            )
        raise HTTPException(status_code=409, detail=status.error or "Gagal sync session browser")
    return status


@app.post("/api/youtube/cdp/refresh", response_model=YouTubeCdpRefreshStatus)
def refresh_youtube_cdp() -> YouTubeCdpRefreshStatus:
    return start_youtube_cdp_refresh_process()


@app.post("/api/youtube/cdp/sync", response_model=YouTubeCdpRepairStatus)
def sync_youtube_cdp() -> YouTubeCdpRepairStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    started_at = now_iso()
    source_profile_path = youtube_login_source_profile_dir()
    source_profile_ready = youtube_login_source_profile_ready()
    if not youtube_cdp_ready():
        return YouTubeCdpRepairStatus(
            ok=False,
            cdp_ready=False,
            session_ready=False,
            source_profile_ready=source_profile_ready,
            source_profile_path=source_profile_path,
            started_at=started_at,
            message=(
                f"Chrome CDP belum aktif di {YOUTUBE_CDP_URL}. "
                "Jalankan Run + Sync CDP dari bot/dashboard, atau start Chrome CDP dari luar lalu sync ulang."
            ),
            logs=tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40),
        )

    code, logs, error = run_youtube_capture_once()
    hydrated = any("Storage-state YouTube dimasukkan ke Chrome CDP" in str(line) for line in logs)
    if code == 0:
        return YouTubeCdpRepairStatus(
            ok=True,
            cdp_ready=youtube_cdp_ready(),
            session_ready=True,
            hydrated=hydrated,
            source_profile_ready=source_profile_ready,
            source_profile_path=source_profile_path,
            started_at=started_at,
            message="Chrome CDP aktif dan session YouTube target berhasil divalidasi.",
            logs=logs[-80:],
        )

    normalized_error = error or f"capture-session exited with code {code}"
    return YouTubeCdpRepairStatus(
        ok=False,
        cdp_ready=youtube_cdp_ready(),
        session_ready=False,
        hydrated=hydrated,
        source_profile_ready=source_profile_ready,
        source_profile_path=source_profile_path,
        started_at=started_at,
        message="Chrome CDP aktif tetapi session YouTube target belum valid.",
        error=normalized_error,
        logs=logs[-80:],
    )


@app.post("/api/youtube/cdp/import-cookies", response_model=YouTubeCdpRepairStatus)
def import_youtube_cdp_cookies() -> YouTubeCdpRepairStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    started_at = now_iso()
    logs: list[str] = []
    refresh_status: YouTubeCdpRefreshStatus | None = None
    source_profile_path = youtube_login_source_profile_dir()
    source_profile_ready = youtube_login_source_profile_ready()

    if not youtube_cdp_ready():
        try:
            refresh_status = start_youtube_cdp_refresh_process()
            logs.extend(refresh_status.logs[-30:])
            logs.append(refresh_status.message)
        except HTTPException as exc:
            return YouTubeCdpRepairStatus(
                ok=False,
                cdp_ready=youtube_cdp_ready(),
                session_ready=False,
                source_profile_ready=source_profile_ready,
                source_profile_path=source_profile_path,
                storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
                started_at=started_at,
                message="Chrome CDP belum aktif dan launcher gagal dijalankan.",
                refresh=refresh_status,
                error=str(exc.detail),
                logs=[*logs, *tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40)][-80:],
            )

    code, capture_logs, error = run_youtube_capture_once(hydrate_storage_state=False)
    logs.extend(capture_logs)

    if code != 0 and error and (youtube_cdp_start_needed(error) or youtube_login_refresh_needed(error)):
        try:
            refresh_status = start_youtube_cdp_refresh_process(
                force_profile_refresh=youtube_login_refresh_needed(error),
                force_restart=youtube_login_refresh_needed(error),
            )
            logs.append(
                "Import cookies CDP belum valid; backend refresh Chrome dari profile login lalu mencoba lagi."
                if youtube_login_refresh_needed(error)
                else "CDP belum aktif; backend menjalankan launcher lalu mencoba import cookies lagi."
            )
            logs.extend(refresh_status.logs[-30:])
            logs.append(refresh_status.message)
            code, retry_logs, error = run_youtube_capture_once(hydrate_storage_state=False)
            logs.extend(retry_logs)
        except HTTPException as exc:
            cookie_count, youtube_cookie_count = youtube_storage_cookie_counts()
            return YouTubeCdpRepairStatus(
                ok=False,
                cdp_ready=youtube_cdp_ready(),
                session_ready=False,
                source_profile_ready=source_profile_ready,
                source_profile_path=source_profile_path,
                cookie_count=cookie_count,
                youtube_cookie_count=youtube_cookie_count,
                storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
                started_at=started_at,
                message="Import cookies CDP belum berhasil.",
                refresh=refresh_status,
                error=str(exc.detail),
                logs=logs[-80:],
            )

    cookie_count, youtube_cookie_count = youtube_storage_cookie_counts()
    ok = code == 0 and youtube_cookie_count > 0
    normalized_error = None
    if not ok:
        normalized_error = error or (
            f"capture-session exited with code {code}"
            if code
            else "Cookies YouTube/Google tidak ditemukan"
        )
    return YouTubeCdpRepairStatus(
        ok=ok,
        cdp_ready=youtube_cdp_ready(),
        session_ready=code == 0,
        hydrated=False,
        source_profile_ready=source_profile_ready,
        source_profile_path=source_profile_path,
        cookies_imported=ok,
        cookie_count=cookie_count,
        youtube_cookie_count=youtube_cookie_count,
        storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
        started_at=started_at,
        message=(
            f"Cookies dari Chrome CDP berhasil diambil dan disimpan ke storage-state ({youtube_cookie_count} cookies YouTube/Google)."
            if ok
            else "Chrome CDP terbaca tetapi cookies YouTube/Google belum berhasil diambil."
        ),
        refresh=refresh_status,
        error=normalized_error,
        logs=logs[-80:],
    )


@app.post("/api/youtube/login/once", response_model=YouTubeCdpRepairStatus)
def setup_youtube_one_time_login() -> YouTubeCdpRepairStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")

    started_at = now_iso()
    logs: list[str] = []
    source_profile_path = YOUTUBE_LOGIN_PROFILE_DIR
    source_profile_ready = bool(source_profile_path and Path(source_profile_path).is_dir())

    if youtube_upload_prefers_cdp() and youtube_cdp_ready():
        code, capture_logs, capture_error = run_youtube_capture_once(hydrate_storage_state=False)
        logs.extend(capture_logs[-60:])
        cookie_count, youtube_cookie_count = youtube_storage_cookie_counts()
        if code == 0:
            return YouTubeCdpRepairStatus(
                ok=True,
                cdp_ready=True,
                session_ready=True,
                source_profile_ready=source_profile_ready,
                source_profile_path=source_profile_path,
                cookies_imported=True,
                cookie_count=cookie_count,
                youtube_cookie_count=youtube_cookie_count,
                storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
                started_at=started_at,
                message="Chrome login aktif dan akun YouTube target valid. Upload otomatis memakai browser ini.",
                logs=logs[-80:],
            )
        logs.append(f"Validasi Chrome login gagal: {capture_error or f'exit code {code}'}")

    cookie_count, youtube_cookie_count = youtube_storage_cookie_counts()
    if youtube_cookie_count > 0:
        logs.append(
            f"Storage-state punya {youtube_cookie_count} cookies YouTube/Google; memvalidasi login Studio dulu."
        )
        check_code, check_logs, check_error = run_youtube_check_login_once(use_chromium_profile=False)
        logs.extend(check_logs[-50:])
        cookie_count, youtube_cookie_count = youtube_storage_cookie_counts()
        if check_code == 0 and youtube_cookie_count > 0:
            enable_youtube_storage_state_upload_mode()
            return YouTubeCdpRepairStatus(
                ok=True,
                cdp_ready=youtube_cdp_ready(),
                session_ready=True,
                hydrated=False,
                source_profile_ready=source_profile_ready,
                source_profile_path=source_profile_path,
                cookies_imported=True,
                cookie_count=cookie_count,
                youtube_cookie_count=youtube_cookie_count,
                storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
                started_at=started_at,
                message=(
                    "Storage-state YouTube sudah divalidasi. Login sekali aktif; upload berikutnya memakai "
                    "session tersimpan tanpa CDP/supervisor."
                ),
                logs=logs[-80:],
            )
        check_failure = check_error or f"exit code {check_code}"
        logs.append(f"Storage-state lama tidak valid: {check_failure}")

    if youtube_login_status.active:
        logs.extend(youtube_login_status.logs[-20:])
        return YouTubeCdpRepairStatus(
            ok=False,
            cdp_ready=youtube_cdp_ready(),
            session_ready=False,
            source_profile_ready=source_profile_ready,
            source_profile_path=source_profile_path,
            cookie_count=cookie_count,
            youtube_cookie_count=youtube_cookie_count,
            storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
            login_required=True,
            started_at=started_at,
            message=(
                "Jendela login YouTube sedang terbuka. Selesaikan login sampai dashboard Studio tampil; "
                "session akan disimpan otomatis."
            ),
            logs=logs[-80:],
        )

    if source_profile_ready:
        logs.append("Memeriksa profile login Playwright khusus.")
        login_code, login_logs, login_error = run_youtube_check_login_once(use_chromium_profile=True)
        logs.extend(login_logs[-30:])
        cookie_count, youtube_cookie_count = youtube_storage_cookie_counts()
        if login_code == 0 and youtube_cookie_count > 0:
            enable_youtube_storage_state_upload_mode()
            return YouTubeCdpRepairStatus(
                ok=True,
                cdp_ready=youtube_cdp_ready(),
                session_ready=True,
                source_profile_ready=True,
                source_profile_path=source_profile_path,
                cookies_imported=True,
                cookie_count=cookie_count,
                youtube_cookie_count=youtube_cookie_count,
                storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
                started_at=started_at,
                message=(
                    "Profile login Playwright sudah valid. Session tersimpan dan upload berikutnya berjalan tanpa CDP."
                ),
                logs=logs[-80:],
            )
        logs.append(f"Profile belum login: {login_error or f'exit code {login_code}'}")

    login_status = start_youtube_login_if_needed()
    logs.extend(login_status.logs[-20:])
    return YouTubeCdpRepairStatus(
        ok=False,
        cdp_ready=youtube_cdp_ready(),
        session_ready=False,
        source_profile_ready=source_profile_ready,
        source_profile_path=source_profile_path,
        cookie_count=cookie_count,
        youtube_cookie_count=youtube_cookie_count,
        storage_state_path=str(YOUTUBE_PLAYWRIGHT_STATE),
        login_required=True,
        started_at=started_at,
        message=(
            "Jendela login YouTube sudah dibuka. Login sampai dashboard YouTube Studio tampil; "
            "session akan tersimpan otomatis dan jendela akan tertutup sendiri."
        ),
        logs=logs[-80:],
    )

@app.post("/api/youtube/cdp/repair", response_model=YouTubeCdpRepairStatus)
def repair_youtube_cdp(profile_sync_requested: bool = True) -> YouTubeCdpRepairStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    started_at = now_iso()
    logs: list[str] = []
    refresh_status: YouTubeCdpRefreshStatus | None = None
    source_profile_path = youtube_login_source_profile_dir()
    source_profile_ready = youtube_login_source_profile_ready()
    try:
        refresh_status = start_youtube_cdp_refresh_process(force_profile_refresh=True, force_restart=True)
        logs.extend(refresh_status.logs[-30:])
        logs.append(refresh_status.message)
    except HTTPException as exc:
        return YouTubeCdpRepairStatus(
            ok=False,
            cdp_ready=youtube_cdp_ready(),
            session_ready=False,
            profile_sync_requested=profile_sync_requested,
            source_profile_ready=source_profile_ready,
            source_profile_path=source_profile_path,
            started_at=started_at,
            message="Refresh Chrome CDP gagal dari backend.",
            error=str(exc.detail),
            logs=[*logs, *tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40)][-80:],
        )

    code, capture_logs, error = run_youtube_capture_once()
    logs.extend(capture_logs)
    hydrated = any("Storage-state YouTube dimasukkan ke Chrome CDP" in str(line) for line in logs)
    if code == 0:
        return YouTubeCdpRepairStatus(
            ok=True,
            cdp_ready=youtube_cdp_ready(),
            session_ready=True,
            hydrated=hydrated,
            profile_sync_requested=profile_sync_requested,
            source_profile_ready=source_profile_ready,
            source_profile_path=source_profile_path,
            started_at=started_at,
            message="Chrome CDP aktif dan session YouTube target berhasil divalidasi.",
            refresh=refresh_status,
            logs=logs[-80:],
        )

    normalized_error = error or f"capture-session exited with code {code}"
    return YouTubeCdpRepairStatus(
        ok=False,
        cdp_ready=youtube_cdp_ready(),
        session_ready=False,
        hydrated=hydrated,
        profile_sync_requested=profile_sync_requested,
        source_profile_ready=source_profile_ready,
        source_profile_path=source_profile_path,
        started_at=started_at,
        message=(
            "Chrome CDP aktif tetapi session YouTube target belum valid."
            if youtube_cdp_ready()
            else "Chrome CDP belum aktif setelah refresh."
        ),
        refresh=refresh_status,
        error=normalized_error,
        logs=logs[-80:],
    )


@app.post("/api/youtube/cdp/profile-sync", response_model=YouTubeCdpRepairStatus)
def sync_youtube_cdp_from_profile() -> YouTubeCdpRepairStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    started_at = now_iso()
    source_profile_path = youtube_login_source_profile_dir()
    source_profile_ready = youtube_login_source_profile_ready()
    if not source_profile_ready:
        return YouTubeCdpRepairStatus(
            ok=False,
            cdp_ready=youtube_cdp_ready(),
            session_ready=False,
            profile_sync_requested=True,
            source_profile_ready=False,
            source_profile_path=source_profile_path,
            started_at=started_at,
            message="Source profile Chrome yang sudah login belum ditemukan.",
            error=(
                "Set YOUTUBE_LOGIN_SOURCE_PROFILE_DIR atau YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR "
                "ke user-data-dir Chrome/Chromium yang sudah login YouTube."
            ),
            logs=tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40),
        )
    repair = repair_youtube_cdp(profile_sync_requested=True)
    if repair.ok:
        return repair

    original_error = repair.error or repair.message
    login_status = start_youtube_login_if_needed(reconnect_cdp=True)
    data = repair.model_dump()
    data.update(
        {
            "login_required": True,
            "message": (
                "Sync profile belum valid, jadi browser login YouTube dibuka sebagai fallback. "
                "Selesaikan login sampai dashboard Studio tampil. Browser akan tertutup, lalu backend "
                "mengaktifkan CDP dan memvalidasi ulang session secara otomatis."
            ),
            "error": None,
            "logs": [
                *repair.logs[-55:],
                f"Fallback browser login dijalankan karena: {original_error}",
                *login_status.logs[-20:],
            ][-80:],
        }
    )
    return YouTubeCdpRepairStatus(**data)


@app.post("/api/youtube/cdp/auto-login", response_model=YouTubeCdpRepairStatus)
def auto_login_youtube_cdp() -> YouTubeCdpRepairStatus:
    if not playwright_installed():
        raise HTTPException(status_code=503, detail="Playwright belum terpasang di backend")
    started_at = now_iso()
    source_profile_path = youtube_login_source_profile_dir()
    source_profile_ready = youtube_login_source_profile_ready() or youtube_chromium_profile_ready()
    if not source_profile_ready and not youtube_auth_state_exists():
        return YouTubeCdpRepairStatus(
            ok=False,
            cdp_ready=youtube_cdp_ready(),
            session_ready=False,
            profile_sync_requested=True,
            source_profile_ready=False,
            source_profile_path=source_profile_path,
            started_at=started_at,
            message="Auto login CDP belum bisa berjalan karena profile login belum ditemukan.",
            error=(
                "Set YOUTUBE_CHROMIUM_USER_DATA_DIR / YOUTUBE_LOGIN_SOURCE_PROFILE_DIR "
                "ke Chrome user-data-dir yang sudah login YouTube Studio."
            ),
            logs=tail_text_file(YOUTUBE_CDP_REFRESH_LOG, 40),
        )

    login_logs: list[str] = []
    if youtube_chromium_profile_ready():
        login_code, login_logs, login_error = run_youtube_profile_login_once()
        if login_code != 0:
            return YouTubeCdpRepairStatus(
                ok=False,
                cdp_ready=youtube_cdp_ready(),
                session_ready=False,
                profile_sync_requested=True,
                source_profile_ready=source_profile_ready,
                source_profile_path=source_profile_path,
                started_at=started_at,
                message="Auto login dari profile Chrome belum berhasil.",
                error=login_error or f"youtube_uploader.py login exited with code {login_code}",
                logs=login_logs[-80:],
            )

    repair = repair_youtube_cdp(profile_sync_requested=True)
    data = repair.model_dump()
    data["started_at"] = started_at
    data["logs"] = [*login_logs[-40:], *repair.logs][-80:]
    if repair.ok:
        data["message"] = "Chrome CDP otomatis login ke YouTube Studio dari profile/storage-state."
    return YouTubeCdpRepairStatus(**data)


@app.post("/api/youtube/cdp/stop")
def stop_youtube_cdp() -> dict[str, bool | str]:
    stop_youtube_cdp_processes()
    ready = youtube_cdp_ready()
    return {
        "stopped": not ready,
        "cdp_ready": ready,
        "message": "Chrome CDP dihentikan." if not ready else "Perintah stop dikirim, tetapi CDP masih terdeteksi aktif.",
    }


@app.post("/api/jobs/{job_id}/youtube-uploads", response_model=YouTubeUploadJob)
def create_youtube_upload(job_id: str, request: YouTubeUploadRequest) -> YouTubeUploadJob:
    require_youtube_ready()
    upload = create_youtube_upload_record(job_id, request)
    with youtube_uploads_lock:
        youtube_uploads[upload.id] = upload
        save_youtube_uploads_unlocked()
    start_youtube_worker_if_needed()
    return upload


@app.post("/api/jobs/{job_id}/youtube-uploads/batch", response_model=list[YouTubeUploadJob])
def create_youtube_upload_batch(job_id: str, request: YouTubeBatchUploadRequest) -> list[YouTubeUploadJob]:
    require_youtube_ready()
    uploads = create_youtube_upload_batch_records(job_id, request)
    queue_youtube_upload_jobs(uploads)
    return uploads


class ModelsQuery(BaseModel):
    base_url: str = ""
    api_key: str = ""


class LocalModelProvider(BaseModel):
    label: str
    base_url: str
    models: list[str]


def resolve_local_base_url(base_url: str) -> str:
    base = base_url.strip()
    if not base:
        return ""
    if os.environ.get("IN_DOCKER") == "1":
        base = base.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    return base


def candidate_local_base_urls(base_url: str) -> list[str]:
    base = base_url.strip().rstrip("/")
    if not base:
        return []

    candidates: list[str] = []
    for item in (
        resolve_local_base_url(base),
        base,
        base.replace("localhost", "127.0.0.1"),
        base.replace("127.0.0.1", "localhost"),
        base.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal"),
    ):
        cleaned = item.strip().rstrip("/")
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    return candidates


def _request_json(url: str, api_key: str = "", timeout: float = 4.0) -> object:
    request = urllib.request.Request(url, method="GET")
    request.add_header("Accept", "application/json")
    if api_key.strip():
        request.add_header("Authorization", f"Bearer {api_key.strip()}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _models_from_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        models = [
            item["id"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        return sorted(set(models))

    # Ollama native /api/tags shape.
    native_models = payload.get("models")
    if isinstance(native_models, list):
        models = [
            item["name"]
            for item in native_models
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        return sorted(set(models))

    return []


def _is_ollama_base_url(base_url: str) -> bool:
    return ":11434" in base_url


def _models_from_ollama_cli(timeout: float = 4.0) -> list[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []

    models: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("name "):
            continue
        name = line.split()[0]
        if name and name not in models:
            models.append(name)
    return models


def load_models_from_base(base_url: str, api_key: str = "", timeout: float = 4.0) -> list[str]:
    bases = candidate_local_base_urls(base_url)
    if not bases:
        return []

    urls: list[str] = []
    for base in bases:
        urls.append(base + "/models")
        if not base.endswith("/v1"):
            urls.append(base + "/v1/models")
            urls.append(base + "/api/tags")
        elif base.endswith(":11434/v1") or ":11434/" in base:
            urls.append(base.removesuffix("/v1") + "/api/tags")

    for url in urls:
        try:
            models = _models_from_payload(_request_json(url, api_key=api_key, timeout=min(timeout, 4.0)))
        except Exception:
            continue
        if models:
            return models
    if _is_ollama_base_url(base_url):
        return _models_from_ollama_cli(timeout=timeout)
    return []


@app.post("/api/models")
def list_models(query: ModelsQuery) -> dict[str, list[str]]:
    base = query.base_url.strip()
    if not base:
        raise HTTPException(status_code=400, detail="base_url is required")

    try:
        models = load_models_from_base(base, api_key=query.api_key, timeout=20)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach LLM endpoint: {exc}")
    if not models:
        raise HTTPException(status_code=502, detail="No models found at LLM endpoint")
    return {"models": models}


@app.get("/api/local-llm/discover", response_model=list[LocalModelProvider])
def discover_local_llms() -> list[LocalModelProvider]:
    providers: list[LocalModelProvider] = []
    for preset in LOCAL_LLM_PRESETS:
        base_url = preset["base_url"]
        models = load_models_from_base(base_url, timeout=2.5)
        if models:
            providers.append(
                LocalModelProvider(
                    label=preset["label"],
                    base_url=base_url,
                    models=models,
                )
            )
    return providers


@app.post("/api/uploads")
def upload_video(file: UploadFile = File(...)) -> dict[str, str | float | None]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOADS_DIR / stored_name
    try:
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()

    return {
        "source_file": stored_name,
        "original_name": file.filename or stored_name,
        "duration": probe_media_duration(target),
    }


@app.get("/api/probe")
def probe_url(url: str) -> dict[str, float | None]:
    return {"duration": fetch_video_duration(url)}


@app.post("/api/jobs", response_model=ClipJob)
def create_job(request: ClipJobRequest) -> ClipJob:
    if request.max_duration <= request.min_duration:
        raise HTTPException(status_code=400, detail="max_duration must be greater than min_duration")

    if not request.url and not request.source_file:
        raise HTTPException(status_code=400, detail="Provide a YouTube URL or upload a video first")

    with jobs_lock:
        if any(job.status in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(
                status_code=409,
                detail="Masih ada proses clipping aktif. Tunggu selesai atau batalkan terlebih dahulu.",
            )

    if request.source_file:
        upload_path = resolve_upload_path(request.source_file)
        if upload_path is None:
            raise HTTPException(status_code=400, detail="Uploaded video not found; upload it again")
        request = request.model_copy(update={"source_file": str(upload_path)})
    elif request.url:
        request = request.model_copy(update={"require_creative_commons": True})

    request = normalize_job_request(request)
    job_id = uuid.uuid4().hex

    # Keep the API key out of persisted state and API responses.
    secret = request.ai_api_key
    if secret:
        job_secrets[job_id] = secret
    request = request.model_copy(update={"ai_api_key": ""})

    job = ClipJob(
        id=job_id,
        status="queued",
        request=request,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    with jobs_lock:
        if any(item.status in {"queued", "running"} for item in jobs.values()):
            job_secrets.pop(job_id, None)
            raise HTTPException(
                status_code=409,
                detail="Proses clipping lain baru saja dimulai. Coba lagi setelah proses tersebut selesai.",
            )
        jobs[job_id] = job
        save_jobs_unlocked()

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return job





@app.get("/api/jobs", response_model=list[ClipJob])
def list_jobs() -> list[ClipJob]:
    with jobs_lock:
        return sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)


@app.delete("/api/jobs")
def delete_all_jobs() -> dict[str, str | int]:
    with jobs_lock:
        removable_ids = [
            job_id
            for job_id, job in jobs.items()
            if job.status in {"queued", "running", "failed", "cancelled"}
        ]
        active_job_ids = [
            job_id
            for job_id, job in jobs.items()
            if job.status in {"queued", "running"}
        ]
    with process_lock:
        active_job_ids = sorted(set(active_job_ids) | set(job_processes))
    preserve_job_files_on_cancel.update(active_job_ids)
    for job_id in active_job_ids:
        cancel_process(job_id)

    with jobs_lock:
        removed_jobs = 0
        for job_id in removable_ids:
            if jobs.pop(job_id, None) is not None:
                removed_jobs += 1
            job_secrets.pop(job_id, None)
            cancelled_job_ids.discard(job_id)
        save_jobs_unlocked()
    return {"status": "ok", "removed_jobs": removed_jobs, "removed_outputs": 0}


@app.delete("/api/jobs/failed")
def delete_failed_jobs() -> dict[str, str | int]:
    removed_jobs = 0
    with jobs_lock:
        removable_ids = [
            job_id
            for job_id, job in jobs.items()
            if job.status in {"failed", "cancelled"}
        ]
        for job_id in removable_ids:
            jobs.pop(job_id)
            job_secrets.pop(job_id, None)
            cancelled_job_ids.discard(job_id)
            removed_jobs += 1
        save_jobs_unlocked()
    return {"status": "ok", "removed_jobs": removed_jobs, "removed_outputs": 0}


@app.patch("/api/jobs/{job_id}/clips", response_model=ClipJob)
def update_job_clip_status(job_id: str, update: ClipStatusUpdate) -> ClipJob:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        clip_found = False
        clips: list[ClipFile] = []
        for clip in job.clips:
            if clip.url == update.url:
                clips.append(clip.model_copy(update={"is_correct": update.is_correct}))
                clip_found = True
            else:
                clips.append(clip)

        if not clip_found:
            raise HTTPException(status_code=404, detail="Clip not found")

        data = job.model_dump()
        data["clips"] = clips
        data["updated_at"] = now_iso()
        next_job = ClipJob(**data)
        jobs[job_id] = next_job
        save_jobs_unlocked()
        return next_job


def delete_job_clips_by_url(job_id: str, clip_urls: set[str]) -> ClipDeleteResponse:
    with process_lock:
        is_running = job_id in job_processes
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status in {"queued", "running"} or is_running:
            raise HTTPException(status_code=409, detail="Batalkan proses aktif sebelum menghapus output")
        active_uploads = active_youtube_uploads_for_job(job_id, clip_urls)
        if active_uploads:
            raise HTTPException(
                status_code=409,
                detail=f"Tunggu {len(active_uploads)} upload YouTube aktif selesai sebelum menghapus clip",
            )

        target_clips = [clip for clip in job.clips if clip.url in clip_urls]
        if not target_clips:
            raise HTTPException(status_code=404, detail="Clip not found")

        for clip in target_clips:
            cleanup_clip_files(clip)

        remaining_clips = [clip for clip in job.clips if clip.url not in clip_urls]
        if not remaining_clips:
            protected_dirs = {
                work_dir
                for other_job_id, other_job in jobs.items()
                if other_job_id != job.id
                for clip in other_job.clips
                if (work_dir := clip_output_work_dir(clip)) is not None
            }
            cleanup_output_work_dirs(job.clips, protected_dirs)
            jobs.pop(job_id, None)
            job_secrets.pop(job_id, None)
            cancelled_job_ids.discard(job_id)
            save_jobs_unlocked()
            return ClipDeleteResponse(job=None, removed_job=True, removed_clips=len(target_clips))

        data = job.model_dump()
        data["clips"] = remaining_clips
        data["updated_at"] = now_iso()
        next_job = ClipJob(**data)
        jobs[job_id] = next_job
        save_jobs_unlocked()
        return ClipDeleteResponse(job=next_job, removed_job=False, removed_clips=len(target_clips))


@app.delete("/api/jobs/{job_id}/clips", response_model=ClipDeleteResponse)
def delete_job_clip(job_id: str, clip_url: str) -> ClipDeleteResponse:
    return delete_job_clips_by_url(job_id, {clip_url})


@app.delete("/api/jobs/{job_id}/clips/selected", response_model=ClipDeleteResponse)
def delete_selected_job_clips(job_id: str, request: ClipSelectionDeleteRequest) -> ClipDeleteResponse:
    clip_urls = {url for url in request.urls if url}
    if not clip_urls:
        raise HTTPException(status_code=400, detail="Select at least one clip")
    return delete_job_clips_by_url(job_id, clip_urls)


@app.delete("/api/jobs/{job_id}/clips/all", response_model=ClipDeleteResponse)
def delete_all_job_clips(job_id: str) -> ClipDeleteResponse:
    with process_lock:
        is_running = job_id in job_processes
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status in {"queued", "running"} or is_running:
            raise HTTPException(status_code=409, detail="Batalkan proses aktif sebelum menghapus output")
        active_uploads = active_youtube_uploads_for_job(job_id)
        if active_uploads:
            raise HTTPException(
                status_code=409,
                detail=f"Tunggu {len(active_uploads)} upload YouTube aktif selesai sebelum menghapus semua clip",
            )

        removed_clips = len(job.clips)
        cleanup_job_files(job)
        jobs.pop(job_id, None)
        job_secrets.pop(job_id, None)
        cancelled_job_ids.discard(job_id)
        save_jobs_unlocked()
        return ClipDeleteResponse(job=None, removed_job=True, removed_clips=removed_clips)


@app.get("/api/jobs/{job_id}", response_model=ClipJob)
def get_job(job_id: str) -> ClipJob:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, str | int]:
    with process_lock:
        is_running = job_id in job_processes
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status == "running" or is_running:
            raise HTTPException(status_code=409, detail="Batalkan proses aktif sebelum menghapus riwayatnya")
        if job.status == "queued":
            cancelled_job_ids.add(job_id)
        active_uploads = active_youtube_uploads_for_job(job_id)
        if active_uploads:
            raise HTTPException(
                status_code=409,
                detail=f"Tunggu {len(active_uploads)} upload YouTube aktif selesai sebelum menghapus job",
            )

        removed_outputs = cleanup_job_files(job)
        jobs.pop(job_id, None)
        job_secrets.pop(job_id, None)
        cancelled_job_ids.discard(job_id)
        save_jobs_unlocked()
    return {"status": "ok", "removed_jobs": 1, "removed_outputs": removed_outputs}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, str | bool]:
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {"queued", "running"}:
        return {"status": job.status, "cancelled": False}

    stopped = cancel_process(job_id)
    if not stopped:
        finished_at = now_iso()
        set_job(
            job_id,
            status="cancelled",
            started_at=job.started_at or finished_at,
            finished_at=finished_at,
            duration_seconds=duration_between_iso(job.started_at, finished_at),
            clips=[],
            candidates=[],
            error="Proses dibatalkan sebelum worker berjalan.",
        )
    return {"status": "cancelled", "cancelled": True}
