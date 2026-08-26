from __future__ import annotations

import hashlib
import json
import importlib.util
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from math import ceil, exp, log10
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Literal
from urllib.parse import parse_qs, quote, urlencode, unquote, urlparse
from urllib.error import HTTPError, URLError
import urllib.request

import imageio_ffmpeg
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from yt_dlp import YoutubeDL

from llm import AIConfig, chat_completion, extract_json
from source_rights import source_rights_risk_reasons


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
SOURCE_USAGE_HISTORY_PATH = Path(
    os.environ.get(
        "SOURCE_USAGE_HISTORY_PATH",
        BASE_DIR / "data" / "source_usage_history.json",
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
YOUTUBE_SHORTS_MAX_SECONDS = 180
SHORT_UPLOAD_MIN_FYP_SCORE = 78
YOUTUBE_CLEANUP_STEPS = (
    "thumbnail",
    "metadata",
    "video",
    "workspace",
    "job_sync",
)
YOUTUBE_CLEANUP_STEP_RATIOS = {
    "thumbnail": 0.25,
    "metadata": 0.50,
    "video": 1.0,
    "workspace": 1.0,
    "job_sync": 1.0,
}
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
DEFAULT_AI_MODEL = os.environ.get("DEFAULT_AI_MODEL", "llama3.2-id:latest")
DEFAULT_REQUIRED_HASHTAGS = [
    tag.strip().lstrip("#")
    for tag in os.environ.get(
        "DEFAULT_REQUIRED_HASHTAGS",
        "viralindonesia,trendingindonesia,kontenpilihan",
    ).split(",")
    if tag.strip().lstrip("#")
]


def default_required_hashtags() -> list[str]:
    return list(DEFAULT_REQUIRED_HASHTAGS)


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
YOUTUBE_FINAL_VISIBILITY_PREFIX = "FINAL_VISIBILITY:"
DEFAULT_YOUTUBE_PLAYLIST = "Islam"
DEFAULT_YOUTUBE_TARGET_CHANNEL = "ryuundyofficial"
DEFAULT_YOUTUBE_TARGET_EMAIL = "fendysketsa@gmail.com"
DEFAULT_YOUTUBE_TARGET_CHANNEL_ID = "UCAOZF9Qzj6DYoXKtLnP4UUQ"
DEFAULT_YOUTUBE_AUTO_UPLOAD_COUNT = 3
DEFAULT_YOUTUBE_AI_FALLBACK_MODELS = ["llama3.2-id:latest", "llama3:latest"]
ROOT_DIR = BASE_DIR.parent
YOUTUBE_CDP_REFRESH_LOG = Path(
    os.environ.get("YOUTUBE_CDP_REFRESH_LOG", "/tmp/fendy-clipper-youtube-chrome-launcher.log")
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


def safe_youtube_visibility(
    requested: str | None = None,
) -> Literal["private", "unlisted", "public"]:
    value = (requested or os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "private")).strip().lower()
    visibility = value if value in {"private", "unlisted", "public"} else "private"
    if visibility == "public" and not env_bool("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", False):
        return "private"
    return visibility  # type: ignore[return-value]


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
    script_text: str = Field(default="", max_length=30000)
    top: int | None = Field(default=None, ge=1, le=50)
    min_duration: float = Field(default=15, ge=5, le=600)
    max_duration: float = Field(default=60, ge=10, le=600)
    clip_mode: Literal["short", "highlight_5m", "long_animate"] = "short"
    # Keep 240s readable for persisted legacy jobs; the current UI offers 300-600s.
    compilation_target_seconds: float = Field(default=300, ge=240, le=600)
    model: str = "Systran/faster-whisper-medium"
    language: str = "id"
    analyze_seconds: float | None = Field(default=None, ge=10, le=7200)
    video_quality: Literal["standard", "high", "max"] = "high"
    visual_mode: Literal["auto_fyp", "cinematic", "speaker_split", "animated_3d", "retro_tv"] = "auto_fyp"
    background_mode: Literal["auto_clean", "keep", "mosque"] = "keep"
    burn_subtitles: bool = True
    enhanced_edit: bool = True
    remove_running_text: bool = False
    auto_blur_watermarks: bool = True
    crop_mode: Literal["center", "person", "streamer"] = "person"
    cam_corner: Literal["auto", "br", "bl", "tr", "tl"] = "auto"
    caption_font_size: int = Field(default=8, ge=6, le=120)
    caption_position: Literal["upper", "center", "bottom"] = "bottom"
    caption_color: str = "#FFFFFF"
    caption_font: Literal[
        "DejaVu Sans", "DejaVu Serif", "Liberation Sans", "Liberation Serif", "Noto Sans"
    ] = "DejaVu Sans"
    caption_outline: float = Field(default=0.5, ge=0, le=8)
    caption_outline_color: str = "#000000"
    required_hashtags: list[str] = Field(default_factory=default_required_hashtags)
    require_creative_commons: bool = True
    confirm_source_rights: bool = False
    confirm_long_animate_rights: bool = False
    auto_upload_youtube: bool = False
    allow_reprocess_source: bool = False
    ai_enabled: bool = True
    ai_base_url: str = DEFAULT_AI_BASE_URL
    ai_model: str = DEFAULT_AI_MODEL
    ai_api_key: str = ""

    @field_validator("visual_mode", mode="before")
    @classmethod
    def _unify_visual_mode(cls, value: Any) -> str:
        # Legacy values remain readable in saved requests, but every new render
        # now runs through the single content-adaptive Auto FYP pipeline.
        return "auto_fyp"

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
    key_point_score: int = 0
    loop_score: int = 0
    boundary_quality: str = ""
    retention_score: int = 0


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
    core_message: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvement_ideas: list[str] = Field(default_factory=list)
    applied_edits: list[str] = Field(default_factory=list)
    key_point_score: int | None = None
    loop_score: int | None = None
    retention_score: int | None = None
    boundary_quality: str | None = None
    output_resolution: str | None = None
    auditor_name: str | None = None
    audit_id: str | None = None
    growth_series: str | None = None
    growth_target_views: int | None = None
    growth_target_subscribers: int | None = None
    subscriber_intent_score: int | None = None
    growth_status: str | None = None
    growth_quality_gate_passed: bool | None = None
    growth_next_action: str | None = None
    growth_checkpoints: list[int] = Field(default_factory=list)
    is_correct: bool = False

    @model_validator(mode="before")
    @classmethod
    def _canonical_growth_target(cls, value: Any) -> Any:
        """Migrate saved jobs/sidecars to the active per-format growth target."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        clip_name = str(data.get("name") or "").casefold()
        is_long_form = clip_name.startswith(
            ("highlight_5menit_", "resume_cerita_", "long_animate_")
        )
        data["growth_target_views"] = 5000 if is_long_form else 50000
        data["growth_target_subscribers"] = 20
        return data


class ClipJob(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    request: ClipJobRequest
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    progress_percent: int = 0
    progress_stage: str | None = None
    progress_detail: str | None = None
    progress_step: int = 0
    progress_total_steps: int = 5
    source_title: str | None = None
    source_url: str | None = None
    source_uploader: str | None = None
    logs: list[str] = []
    clips: list[ClipFile] = []
    candidates: list[ClipCandidate] = []
    error: str | None = None


class SourceHistoryJob(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    created_at: str
    source_title: str | None = None
    clip_mode: Literal["short", "highlight_5m"]
    clip_count: int = 0


class SourceHistoryCheck(BaseModel):
    input_url: str
    normalized_url: str | None = None
    valid_youtube_url: bool = False
    found: bool = False
    archived: bool = False
    has_short_clips: bool = False
    has_highlight_5m: bool = False
    attempted_modes: list[Literal["short", "highlight_5m"]] = Field(default_factory=list)
    matches: list[SourceHistoryJob] = Field(default_factory=list)


class SourceUsageLogEntry(BaseModel):
    job_id: str
    source_url: str
    source_title: str | None = None
    source_uploader: str | None = None
    clip_mode: Literal["short", "highlight_5m"]
    processed_at: str
    clip_count: int = 0
    output_names: list[str] = Field(default_factory=list)
    processing_duration_seconds: float | None = None
    compilation_target_seconds: float | None = None
    auto_upload_youtube: bool = False


class SourceUsageLogResponse(BaseModel):
    items: list[SourceUsageLogEntry] = Field(default_factory=list)
    total: int = 0
    unique_sources: int = 0


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
        default_factory=safe_youtube_visibility
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
        default_factory=safe_youtube_visibility
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


class YouTubeCleanupStepProgress(BaseModel):
    started_at: str
    completed_at: str | None = None
    duration_ms: int | None = None
    removed_items: int = 0


class YouTubePerformanceSnapshot(BaseModel):
    captured_at: str
    source: Literal["youtube_analytics", "youtube_public", "manual"]
    views: int = Field(default=0, ge=0)
    engaged_views: int | None = Field(default=None, ge=0)
    average_view_duration: float | None = Field(default=None, ge=0)
    average_view_percentage: float | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    subscribers_gained: int | None = Field(default=None, ge=0)
    subscribers_lost: int | None = Field(default=None, ge=0)


class YouTubePerformanceUpdateRequest(BaseModel):
    views: int = Field(default=0, ge=0)
    engaged_views: int | None = Field(default=None, ge=0)
    average_view_duration: float | None = Field(default=None, ge=0)
    average_view_percentage: float | None = Field(default=None, ge=0, le=1000)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    subscribers_gained: int | None = Field(default=None, ge=0)
    subscribers_lost: int | None = Field(default=None, ge=0)


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
    thumbnail_attached: bool = False
    visibility: Literal["private", "unlisted", "public"] = "private"
    made_for_kids: bool = False
    altered_content: bool = False
    tags: list[str] = Field(default_factory=list)
    playlist: str = ""
    playlist_confirmed: bool = False
    target_channel: str = ""
    dry_run: bool = False
    video_url: str | None = None
    clip_sha256: str | None = None
    queue_position: int | None = None
    queue_total: int | None = None
    clip_delete_after: str | None = None
    clip_deleted_at: str | None = None
    clip_delete_error: str | None = None
    clip_cleanup_started_at: str | None = None
    clip_cleanup_current_step: str | None = None
    clip_cleanup_completed_steps: list[str] = Field(default_factory=list)
    clip_cleanup_step_details: dict[str, YouTubeCleanupStepProgress] = Field(default_factory=dict)
    growth_series: str = ""
    growth_target_views: int = Field(default=50000, ge=1)
    growth_target_subscribers: int = Field(default=20, ge=1)
    performance_status: Literal[
        "not_measured", "learning", "views_target_met", "target_met"
    ] = "not_measured"
    performance_diagnosis: list[str] = Field(default_factory=list)
    performance_snapshots: list[YouTubePerformanceSnapshot] = Field(default_factory=list)
    backend_now: str | None = None
    clip_delete_remaining_seconds: float | None = None
    logs: list[str] = []
    error: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _canonical_growth_target(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        clip_name = str(data.get("clip_name") or "").casefold()
        is_long_form = clip_name.startswith(
            ("highlight_5menit_", "resume_cerita_", "long_animate_")
        )
        data["growth_target_views"] = 5000 if is_long_form else 50000
        data["growth_target_subscribers"] = 20
        return data


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

IslamicContentNiche = Literal[
    "auto",
    "islamic_current_viral",
    "islamic_mental_health",
    "halal_wealth",
    "fiqih_harian",
    "islamic_history",
]
ViralDurationFilter = Literal["any", "under_3", "between_3_20", "over_20"]
ViralUploadDateFilter = Literal["today", "this_week", "this_month", "this_year"]
ViralDefinitionFilter = Literal["any", "hd"]
ViralSortOrder = Literal["popularity", "relevance", "newest"]

ISLAMIC_EVERGREEN_NICHES: dict[str, dict[str, Any]] = {
    "islamic_current_viral": {
        "label": "Isu Muslim & Kajian Viral Terkini",
        "queries": [
            "isu muslim indonesia viral hari ini",
            "kajian islam viral terbaru indonesia",
            "berita umat islam indonesia terbaru",
            "podcast islam topik viral minggu ini",
            "fenomena sosial menurut islam terbaru",
            "ustaz indonesia bahas isu viral",
            "nasihat islam untuk masalah masa kini",
            "dakwah pendek viral indonesia terbaru",
            "kisah muslim inspiratif terbaru indonesia",
            "kajian anak muda islam yang sedang ramai",
            "pertanyaan islam paling ramai minggu ini",
            "ceramah islam trending indonesia",
        ],
        "keywords": [
            "islam", "muslim", "kajian", "ustaz", "ustadz", "ulama", "dakwah",
            "umat", "viral", "terbaru", "indonesia", "isu", "fenomena", "ramai",
            "nasihat", "ceramah", "hijrah", "quran", "hadis", "hadits",
        ],
        "hashtags": ["IslamTerkini", "KajianViral", "MuslimIndonesia"],
    },
    "islamic_mental_health": {
        "label": "Kesehatan Mental & Ketenangan Jiwa",
        "queries": [
            "kesehatan mental islam overthinking",
            "cara menenangkan hati menurut islam",
            "tawakal menghadapi kecemasan",
            "stress emosi dan sabar dalam islam",
            "tazkiyatun nafs ketenangan jiwa",
            "psikologi islam rasa takut gagal",
            "tadabbur quran untuk hati tenang",
            "kelelahan mental dan spiritual islam",
            "mengatasi insecure menurut islam",
            "kajian ketenangan hati terbaru",
            "podcast kesehatan mental islami",
            "self healing dalam islam",
        ],
        "keywords": [
            "overthinking", "cemas", "kecemasan", "tenang", "ketenangan", "tawakal",
            "mental", "stres", "stress", "emosi", "sabar", "takut", "gagal", "insecure",
            "tazkiyatun", "jiwa", "hati", "healing", "psikologi", "tadabbur",
        ],
        "hashtags": ["KesehatanMentalIslam", "KetenanganHati", "Tawakal"],
    },
    "halal_wealth": {
        "label": "Rezeki Halal, Karier & Keuangan",
        "queries": [
            "cara mencari rezeki halal berkah",
            "keuangan syariah untuk anak muda",
            "bahaya riba dan solusi praktis",
            "investasi halal pemula indonesia",
            "etika kerja dan karier dalam islam",
            "bisnis halal transparan",
            "mengatur keuangan keluarga islami",
            "rezeki bersih ketenangan keluarga",
            "akad syariah dijelaskan sederhana",
            "podcast pengusaha muslim indonesia",
            "sedekah rezeki dan keberkahan",
            "karier sukses sesuai syariah",
        ],
        "keywords": [
            "rezeki", "halal", "berkah", "keberkahan", "riba", "syariah", "investasi",
            "keuangan", "uang", "karier", "kerja", "bisnis", "usaha", "akad", "sedekah",
            "pengusaha", "profesi", "gaji",
        ],
        "hashtags": ["RezekiHalal", "KeuanganSyariah", "KarierMuslim"],
    },
    "fiqih_harian": {
        "label": "Fikih Harian & Perbaikan Salat",
        "queries": [
            "kesalahan shalat yang sering tidak disadari",
            "cara memperbaiki gerakan shalat",
            "posisi sujud yang benar",
            "kesalahan wudhu sehari hari",
            "fiqih shalat praktis singkat",
            "bacaan shalat yang benar",
            "cara shalat lebih khusyuk",
            "tata cara wudhu sesuai sunnah",
            "tanya jawab fiqih ibadah harian",
            "doa harian dan adab muslim",
            "micro learning fiqih islam",
            "kajian fiqih praktis terbaru",
        ],
        "keywords": [
            "fiqih", "fikih", "shalat", "salat", "wudhu", "sujud", "ruku", "tumit",
            "bacaan", "ibadah", "doa", "khusyuk", "sunnah", "makmum", "imam", "tayamum",
            "najis", "gerakan", "adab",
        ],
        "hashtags": ["FiqihHarian", "PerbaikiShalat", "BelajarIbadah"],
    },
    "islamic_history": {
        "label": "Sejarah Islam & Kisah Penuh Hikmah",
        "queries": [
            "kisah nabi penuh hikmah",
            "kisah sahabat nabi inspiratif",
            "sejarah peradaban islam dokumenter",
            "strategi perang badar sejarah islam",
            "kejayaan ilmuwan muslim",
            "kisah kepemimpinan khalifah islam",
            "sejarah islam yang jarang diketahui",
            "tokoh muslim pengubah dunia",
            "cerita epik peradaban muslim",
            "hikmah sejarah islam untuk masa kini",
            "dokumenter sejarah nabi indonesia",
            "podcast sejarah islam indonesia",
        ],
        "keywords": [
            "sejarah", "nabi", "rasul", "sahabat", "khalifah", "peradaban", "badar",
            "uhud", "hijrah", "ilmuwan", "tokoh", "pasukan", "kerajaan", "dinasti", "ulama",
            "kepemimpinan", "dokumenter", "kisah",
        ],
        "hashtags": ["SejarahIslam", "KisahSahabat", "HikmahSejarah"],
    },
}


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


def prioritized_niche_queries(niche: IslamicContentNiche, configured: list[str]) -> list[str]:
    """Put the selected evergreen niche ahead of every generic discovery query."""
    if niche == "auto":
        # Fast API mode combines the first six entries into one request. Give
        # every supported niche a seat in that request instead of letting a
        # single legacy theme dominate automatic discovery.
        profiles = list(ISLAMIC_EVERGREEN_NICHES.values())
        cross_niche_queries = [
            str(profile["queries"][0])
            for profile in profiles
            if isinstance(profile.get("queries"), list) and profile["queries"]
        ]
        current_profile = ISLAMIC_EVERGREEN_NICHES["islamic_current_viral"]
        cross_niche_queries.append(str(current_profile["queries"][1]))
        return merge_unique_queries(
            cross_niche_queries,
            prioritized_viral_queries(configured),
        )
    profile = ISLAMIC_EVERGREEN_NICHES[niche]
    current_year = datetime.now(timezone.utc).year
    current_variants: list[str] = []
    for query in list(profile["queries"]):
        current_variants.extend([query, f"{query} terbaru {current_year}"])
    return merge_unique_queries(
        current_variants,
        configured,
        BROAD_VIRAL_SEARCH_QUERIES,
        MYSTERY_ISLAMIC_SEARCH_QUERIES,
        HORROR_PODCAST_SEARCH_QUERIES,
    )


def default_auto_viral_queries() -> list[str]:
    configured = env_search_queries("AUTO_VIRAL_SEARCH_QUERIES", "AUTOPILOT_KEYWORDS")
    return prioritized_viral_queries(configured)


def default_viral_video_search_queries() -> list[str]:
    configured = env_search_queries("VIRAL_CC_SEARCH_QUERIES", "AUTOPILOT_KEYWORDS")
    return prioritized_viral_queries(configured)


class AutoViralRequest(BaseModel):
    niche: IslamicContentNiche = "auto"
    queries: list[str] = Field(default_factory=default_auto_viral_queries)
    video_count: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_VIDEO_COUNT", 5), ge=1, le=7)
    clips_per_video: int = Field(default_factory=youtube_auto_upload_count, ge=1, le=5)
    search_limit_per_query: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_SEARCH_LIMIT", 25), ge=3, le=50)
    min_source_duration: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_MIN_SOURCE_SECONDS", 60), ge=30, le=7200)
    max_source_duration: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_MAX_SOURCE_SECONDS", 7200), ge=60, le=14400)
    min_views: int = Field(default_factory=lambda: env_int("AUTO_VIRAL_MIN_VIEWS", 1000), ge=0)
    max_age_days: int = Field(default=FRESH_VIRAL_MAX_AGE_DAYS, ge=1, le=MAX_VIRAL_FALLBACK_AGE_DAYS)
    duration_filter: ViralDurationFilter = "over_20"
    upload_date_filter: ViralUploadDateFilter = "this_year"
    definition_filter: ViralDefinitionFilter = "hd"
    sort_order: ViralSortOrder = "popularity"
    top: int | None = Field(default=None, ge=1, le=MAX_REQUESTED_CLIPS)
    min_duration: float = Field(default=15, ge=5, le=600)
    max_duration: float = Field(default=60, ge=10, le=600)
    video_quality: Literal["standard", "high", "max"] = "high"
    visual_mode: Literal["auto_fyp", "cinematic", "speaker_split", "animated_3d", "retro_tv"] = "auto_fyp"
    background_mode: Literal["auto_clean", "keep", "mosque"] = "keep"
    crop_mode: Literal["center", "person", "streamer"] = "person"
    burn_subtitles: bool = True
    ai_enabled: bool = True
    ai_base_url: str = DEFAULT_AI_BASE_URL
    ai_model: str = DEFAULT_AI_MODEL
    ai_api_key: str = ""
    source_urls: list[str] = Field(default_factory=list)
    auto_upload_youtube: bool = True

    @field_validator("visual_mode", mode="before")
    @classmethod
    def _unify_visual_mode(cls, value: Any) -> str:
        return "auto_fyp"

    @field_validator("queries")
    @classmethod
    def _clean_queries(cls, value: list[str]) -> list[str]:
        cleaned = [re.sub(r"\s+", " ", item).strip() for item in value if item.strip()]
        return prioritized_viral_queries(cleaned)[:80]

    @field_validator("source_urls")
    @classmethod
    def _clean_source_urls(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = normalize_youtube_video_url(str(item))
            if normalized and normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)
        return cleaned[:7]

    @model_validator(mode="after")
    def _apply_niche_priority(self) -> "AutoViralRequest":
        self.queries = prioritized_niche_queries(self.niche, self.queries)[:80]
        if "max_age_days" not in self.model_fields_set:
            self.max_age_days = {
                "today": 1,
                "this_week": 7,
                "this_month": 31,
                "this_year": 365,
            }[self.upload_date_filter]
        if self.source_urls:
            self.video_count = min(self.video_count, len(self.source_urls))
        return self


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
    niche: IslamicContentNiche = "auto"
    queries: list[str] = Field(default_factory=default_viral_video_search_queries)
    video_count: int = Field(default=3, ge=1, le=7)
    search_limit_per_query: int = Field(default_factory=lambda: env_int("VIRAL_CC_SEARCH_LIMIT", 25), ge=3, le=50)
    min_source_duration: int = Field(default=30, ge=30, le=7200)
    max_source_duration: int = Field(
        default_factory=lambda: env_int("VIRAL_CC_MAX_SOURCE_SECONDS", 7200),
        ge=60,
        le=14400,
    )
    min_views: int = Field(default_factory=lambda: env_int("VIRAL_CC_MIN_VIEWS", 1000), ge=0)
    max_age_days: int = Field(default=FRESH_VIRAL_MAX_AGE_DAYS, ge=1, le=MAX_VIRAL_FALLBACK_AGE_DAYS)
    duration_filter: ViralDurationFilter = "over_20"
    upload_date_filter: ViralUploadDateFilter = "this_year"
    definition_filter: ViralDefinitionFilter = "hd"
    sort_order: ViralSortOrder = "popularity"
    max_metadata_checks: int = Field(default_factory=lambda: env_int("VIRAL_CC_MAX_METADATA_CHECKS", 24), ge=3, le=500)
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

    @model_validator(mode="after")
    def _apply_niche_priority(self) -> "ViralVideoSearchRequest":
        self.queries = prioritized_niche_queries(self.niche, self.queries)[:80]
        if "max_age_days" not in self.model_fields_set:
            self.max_age_days = {
                "today": 1,
                "this_week": 7,
                "this_month": 31,
                "this_year": 365,
            }[self.upload_date_filter]
        return self


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
SOURCE_USAGE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
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


def codex_idea_area(value: str) -> str:
    prefix = re.split(r"\s*(?:—|–|:|\s-\s)\s*", value.casefold(), maxsplit=1)[0][:48]
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


def unresolved_codex_ideas(sidecar: dict[str, Any], ideas: list[str]) -> list[str]:
    """Hide legacy ideas when the saved render plan already applied or reviewed them."""
    if not sidecar.get("enhanced_edit") or sidecar.get("output_format", "vertical_short") != "vertical_short":
        return ideas
    plan = sidecar.get("codex_edit_plan")
    if not isinstance(plan, dict):
        return ideas

    remaining: list[str] = []
    for idea in ideas:
        area = codex_idea_area(idea)
        resolved = (
            (area == "hook" and bool(plan.get("hook_boost")))
            or (area == "tempo" and bool(plan.get("tempo_boost")))
            or (area == "ending" and bool(plan.get("ending_boost")))
            or area in {"loop", "visual", "audio"}
        )
        if not resolved:
            remaining.append(idea)
    return remaining


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


def load_source_usage_history() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(SOURCE_USAGE_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(url): record
        for url, record in payload.items()
        if isinstance(url, str) and isinstance(record, dict)
    }


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
            if upload.video_url and not upload.dry_run:
                delete_after = (
                    datetime.fromisoformat(finished_at)
                    + timedelta(
                        seconds=max(
                            1,
                            env_int("YOUTUBE_DELETE_UPLOADED_CLIP_DELAY_SECONDS", 30),
                        )
                    )
                ).isoformat()
                upload = upload.model_copy(
                    update={
                        "status": "completed",
                        "updated_at": finished_at,
                        "finished_at": finished_at,
                        "duration_seconds": duration_between_iso(upload.started_at, finished_at),
                        "clip_delete_after": delete_after,
                        "clip_deleted_at": None,
                        "clip_delete_error": None,
                        "clip_cleanup_started_at": None,
                        "clip_cleanup_current_step": None,
                        "clip_cleanup_completed_steps": [],
                        "clip_cleanup_step_details": {},
                        "logs": [
                            *upload.logs,
                            "Recovery restart: URL YouTube sudah terverifikasi; upload dipulihkan sebagai completed tanpa upload ulang.",
                        ][-160:],
                        "error": None,
                    }
                )
            else:
                file_selection_started = any(
                    str(line).startswith("Video dipilih:")
                    for line in upload.logs
                )
                if not file_selection_started:
                    upload = upload.model_copy(
                        update={
                            "status": "queued",
                            "updated_at": finished_at,
                            "started_at": None,
                            "finished_at": None,
                            "duration_seconds": None,
                            "logs": [
                                *upload.logs,
                                "Recovery restart: file belum dipilih di YouTube; upload dikembalikan ke antrean dengan aman.",
                            ][-160:],
                            "error": None,
                        }
                    )
                else:
                    upload = upload.model_copy(
                        update={
                            "status": "failed",
                            "updated_at": finished_at,
                            "finished_at": finished_at,
                            "duration_seconds": duration_between_iso(upload.started_at, finished_at),
                            "error": (
                                "Backend restart setelah file dipilih; upload tidak diulang otomatis "
                                "untuk mencegah video duplikat."
                            ),
                        }
                    )
        if (
            upload.status == "failed"
            and upload.error == "Backend restarted before this YouTube upload finished"
            and not any(str(line).startswith("Video dipilih:") for line in upload.logs)
        ):
            recovered_at = now_iso()
            upload = upload.model_copy(
                update={
                    "status": "queued",
                    "updated_at": recovered_at,
                    "started_at": None,
                    "finished_at": None,
                    "duration_seconds": None,
                    "logs": [
                        *upload.logs,
                        "Recovery restart: upload lama belum memilih file dan dikembalikan ke antrean dengan aman.",
                    ][-160:],
                    "error": None,
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


def remove_empty_output_ancestors(directory: Path) -> int:
    """Remove an empty directory and its empty parents, stopping at outputs."""
    removed = 0
    root = OUTPUTS_DIR.resolve()
    current = directory.resolve()
    while current != root and root in current.parents:
        try:
            current.rmdir()
            removed += 1
        except FileNotFoundError:
            pass
        except OSError:
            break
        current = current.parent
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
    paths.add(clip_path.with_suffix(".srt"))
    paths.add(clip_path.with_name(f"{clip_path.stem}.dynamic.ass"))
    paths.add(clip_path.with_suffix(".json"))
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
        job.request.clip_mode in {"highlight_5m", "long_animate"}
        or clip.name.lower().startswith(
            ("highlight_5menit_", "resume_cerita_", "long_animate_")
        )
    )


def youtube_growth_targets(job: "ClipJob", clip: ClipFile) -> tuple[int, int]:
    """Return canonical per-upload targets without trusting stale sidecar values."""
    return (5000 if is_compilation_clip(job, clip) else 50000, 20)


def classify_long_form_playlist(*values: str) -> str:
    """Map long-form story metadata to one existing Studio playlist."""
    searchable = " ".join(value for value in values if isinstance(value, str)).casefold()
    searchable = re.sub(r"[^a-z0-9\s-]", " ", searchable)
    searchable = re.sub(r"\s+", " ", searchable).strip()

    # Explicit genre declarations beat incidental words inside the story.
    if any(marker in searchable for marker in ("cerita rakyat", "folklor", "folklore")):
        return "Cerita Rakyat"
    if any(marker in searchable for marker in ("legenda", "legend of", "asal usul")):
        return "Legenda"

    horror_markers = (
        "horor",
        "horror",
        "hantu",
        "gaib",
        "mistis",
        "angker",
        "kuntilanak",
        "pocong",
        "genderuwo",
        "setan",
        "iblis",
        "penampakan",
        "kerasukan",
        "bau anir",
        "darah",
        "misteri",
        "malam mencekam",
    )
    if any(marker in searchable for marker in horror_markers):
        return "Horor"

    legend_markers = (
        "kerajaan",
        "raja",
        "ratu",
        "putri",
        "pangeran",
        "kesultanan",
        "tokoh sakti",
        "prasasti",
    )
    if any(marker in searchable for marker in legend_markers):
        return "Legenda"

    return "Cerita Rakyat"


def automatic_long_form_playlist(
    job: "ClipJob",
    clip: ClipFile,
    title: str,
    description: str,
) -> str:
    sidecar = clip_sidecar_payload(clip)
    sidecar_values = [
        str(sidecar.get(key) or "")
        for key in (
            "title",
            "text",
            "hook",
            "core_message",
            "thumbnail_headline",
            "thumbnail_support",
        )
    ]
    return classify_long_form_playlist(
        title,
        description,
        clip.title or "",
        clip.social_caption or "",
        clip.hook or "",
        clip.core_message or "",
        job.source_title or "",
        job.request.script_text[:30000],
        *sidecar_values,
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


def enrich_job_codex_feedback(job: "ClipJob") -> "ClipJob":
    clips: list[ClipFile] = []
    changed = False
    for clip in job.clips:
        clip_path = output_path_from_url(clip.url)
        json_path = clip_path.with_suffix(".json") if clip_path is not None else None
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8")) if json_path and json_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            payload = {}
        sidecar = payload if isinstance(payload, dict) else {}
        remaining = unresolved_codex_ideas(sidecar, clip.improvement_ideas)
        raw_applied = sidecar.get("applied_edits")
        applied = (
            [str(item).strip() for item in raw_applied if isinstance(item, str) and item.strip()][:8]
            if isinstance(raw_applied, list)
            else clip.applied_edits
        )
        if remaining != clip.improvement_ideas or applied != clip.applied_edits:
            clip = clip.model_copy(
                update={"improvement_ideas": remaining, "applied_edits": applied}
            )
            changed = True
        clips.append(clip)
    return job.model_copy(update={"clips": clips}) if changed else job


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
    return enrich_job_source_metadata(
        enrich_job_codex_feedback(enrich_job_clip_titles(job))
    )


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


def cleanup_output_work_dirs(
    clips: list[ClipFile],
    protected_dirs: set[Path] | None = None,
    *,
    strict: bool = False,
) -> int:
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
        if work_dir.is_dir():
            try:
                shutil.rmtree(work_dir)
            except OSError as exc:
                if strict:
                    raise RuntimeError(
                        f"Workspace output belum dapat dihapus: {work_dir}: {exc}"
                    ) from exc
                continue
            removed += 1
            removed += remove_empty_output_ancestors(work_dir.parent)
    return removed


def output_top_level_dir_from_url(url: str | None) -> Path | None:
    path = output_path_from_url(url)
    if path is None:
        return None
    root = OUTPUTS_DIR.resolve()
    try:
        first_part = path.resolve().relative_to(root).parts[0]
    except (IndexError, ValueError):
        return None
    candidate = (root / first_part).resolve()
    return candidate if candidate.parent == root else None


def cleanup_orphan_output_roots(*, min_age_seconds: int | None = None) -> int:
    """Remove unreferenced output roots while protecting every known job/upload.

    Empty orphan directories are always safe to prune. Non-empty roots receive
    an age grace period so a newly spawned process cannot be mistaken for stale
    output before its job record becomes visible.
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    root = OUTPUTS_DIR.resolve()
    grace = max(
        60,
        min_age_seconds
        if min_age_seconds is not None
        else env_int("OUTPUT_ORPHAN_CLEANUP_MIN_AGE_SECONDS", 3600),
    )
    protected: set[Path] = set()
    for job in jobs.values():
        job_root = (root / job.id).resolve()
        if job_root.parent == root:
            protected.add(job_root)
        for clip in job.clips:
            if (clip_root := output_top_level_dir_from_url(clip.url)) is not None:
                protected.add(clip_root)
    for upload in youtube_uploads.values():
        if upload.clip_deleted_at:
            continue
        if (upload_root := output_top_level_dir_from_url(upload.clip_url)) is not None:
            protected.add(upload_root)

    now = time.time()
    removed = 0
    for item in list(OUTPUTS_DIR.iterdir()):
        try:
            resolved = item.resolve()
            if resolved.parent != root or resolved in protected or not item.is_dir():
                continue
            if not any(item.iterdir()):
                item.rmdir()
                removed += 1
                continue
            latest_mtime = max(
                [item.stat().st_mtime]
                + [
                    path.stat().st_mtime
                    for path in item.rglob("*")
                    if path.exists()
                ]
            )
            if now - latest_mtime < grace:
                continue
            shutil.rmtree(item)
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f"Cleanup orphan outputs dilewati untuk {item}: {exc}", flush=True)
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
source_usage_history: dict[str, dict[str, Any]] = load_source_usage_history()
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
source_usage_history_lock = threading.Lock()
youtube_uploads_lock = threading.Lock()
youtube_upload_creation_lock = threading.Lock()
job_secrets: dict[str, str] = {}
job_processes: dict[str, subprocess.Popen[str]] = {}
youtube_upload_processes: dict[str, subprocess.Popen[str]] = {}
youtube_login_process: subprocess.Popen[str] | None = None
youtube_login_status = YouTubeLoginStatus(active=False)
youtube_login_reconnect_cdp = False
cancelled_job_ids: set[str] = set()
preserve_job_files_on_cancel: set[str] = set()
process_lock = threading.Lock()
clip_job_slots = threading.BoundedSemaphore(max(1, env_int("FENDY_CLIPPER_MAX_CONCURRENT_JOBS", 3)))
youtube_worker_lock = threading.Lock()
youtube_worker_running = False
youtube_cleanup_lock = threading.Lock()
youtube_cleanup_scheduled: set[str] = set()
auto_viral_runs: dict[str, AutoViralRun] = {}
auto_viral_lock = threading.Lock()
auto_viral_active_run_id: str | None = None
youtube_data_api_cache: dict[str, tuple[float, dict[str, Any]]] = {}
youtube_data_api_cache_lock = threading.Lock()


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
    return safe_youtube_visibility()


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
        or "youtube studio gagal memuat aplikasi" in lowered
        or "refresh ulang profil chrome cdp" in lowered
        or "signintoyoutube" in lowered
        or "accounts.google.com" in lowered
    )


def youtube_navigation_retry_needed(error: str) -> bool:
    lowered = error.lower()
    return (
        "youtube studio gagal memulihkan halaman channel" in lowered
        or "youtube studio gagal membuka halaman konfirmasi akses browser" in lowered
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
    if source_path.name.lower().startswith(
        ("highlight_5menit_", "resume_cerita_", "long_animate_")
    ):
        return (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
    return (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )


def youtube_upload_clean_metadata_args() -> list[str]:
    """Do not copy source provenance tags into a size-limited upload render."""
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
        "comment=",
        "-metadata",
        "description=",
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
            *youtube_upload_clean_metadata_args(),
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

    parsed = urlparse(clean)
    host = parsed.netloc.casefold().split(":", 1)[0]
    video_id = ""
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }:
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        elif len(path_parts) >= 2 and path_parts[0].casefold() in {"shorts", "live", "embed"}:
            video_id = path_parts[1]
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id):
        return f"https://www.youtube.com/watch?v={video_id}"
    return None


def youtube_video_url_from_logs(logs: list[str]) -> str | None:
    for line in reversed(logs):
        if YOUTUBE_VIDEO_URL_PREFIX in line:
            value = line.split(YOUTUBE_VIDEO_URL_PREFIX, 1)[1].strip()
            video_url = normalize_youtube_video_url(value)
            if video_url:
                return video_url
    return None


def youtube_final_visibility_from_logs(logs: list[str]) -> str | None:
    for line in reversed(logs):
        if YOUTUBE_FINAL_VISIBILITY_PREFIX not in line:
            continue
        value = line.split(YOUTUBE_FINAL_VISIBILITY_PREFIX, 1)[1].strip().casefold()
        if value in {"private", "unlisted", "public"}:
            return value
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


_DESCRIPTION_ICON_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2190-\u21FF"
    "\u2600-\u27BF"
    "]"
)


def strip_description_icons(value: str) -> str:
    """Remove decorative icons from public descriptions without changing wording."""
    clean = _DESCRIPTION_ICON_RE.sub("", value)
    clean = clean.replace("\ufe0f", "").replace("\u200d", "")
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    return re.sub(r"(?m)^[ \t]+|[ \t]+$", "", clean).strip()


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
    max_length = 78
    if len(clean) + len(suffix) > max_length:
        clean = clean[: max_length - len(suffix)].rsplit(" ", 1)[0].rstrip() or clean[: max_length - len(suffix)].rstrip()
    return f"{clean}{suffix}"[:max_length] if clean else "Clip #Shorts"


def youtube_description_highlights(context: str, *, is_compilation: bool) -> list[str]:
    """Build topic-aware benefit bullets without relying on metadata AI output."""
    words = set(re.findall(r"[\w']+", context.casefold(), flags=re.UNICODE))
    if words.intersection({"waris", "warisan", "pewaris", "ahliwaris", "takziah"}):
        highlights = [
            "Siapa yang berhak atas harta dan kapan harta boleh digunakan.",
            "Batas tindakan sebelum pembagian atau penetapan hak selesai.",
            "Cara menjaga hak keluarga agar tidak memicu sengketa di kemudian hari.",
        ]
    elif words.intersection({"jin", "misteri", "mistis", "mitos", "horor", "hantu", "gaib"}):
        highlights = [
            "Konteks cerita tanpa langsung menganggap setiap klaim sebagai fakta.",
            "Perbedaan antara pengalaman, mitos, penafsiran, dan hal yang terverifikasi.",
            "Hikmah yang bisa dinilai kembali setelah mengikuti pembahasan.",
        ]
    elif words.intersection({"islam", "allah", "nabi", "iman", "doa", "shalat", "salat", "muslim"}):
        highlights = [
            "Konteks pembahasan agar pesan tidak berhenti pada satu potongan kalimat.",
            "Hikmah utama yang relevan dengan kehidupan sehari-hari.",
            "Sudut pandang yang bisa menjadi bahan belajar dan refleksi bersama.",
        ]
    elif words.intersection({"uang", "rezeki", "riba", "investasi", "bisnis", "keuangan"}):
        highlights = [
            "Gagasan utama dan konteks di balik pembahasan keuangan.",
            "Hal yang perlu diperiksa sebelum mengambil keputusan pribadi.",
            "Pelajaran praktis yang bisa dipertimbangkan secara bertanggung jawab.",
        ]
    elif words.intersection({"sejarah", "sahabat", "kerajaan", "peradaban", "tokoh"}):
        highlights = [
            "Urutan konteks yang membantu memahami peristiwa dan tokohnya.",
            "Poin penting di balik kejadian yang dibahas.",
            "Hikmah sejarah yang masih relevan untuk dipikirkan hari ini.",
        ]
    else:
        highlights = [
            "Konteks lengkap di balik poin utama video.",
            "Penjelasan inti tanpa berhenti pada hook pembuka.",
            "Pelajaran yang bisa dinilai dan didiskusikan bersama.",
        ]
    return highlights if is_compilation else highlights[:2]


def youtube_description_summary(value: str) -> str:
    """Extract the useful summary from current, legacy, or AI descriptions."""
    clean = strip_hashtag_lines(strip_description_icons(value)).strip()
    clean = re.sub(
        r"^\s*(?:📌\s*)?(?:TENTANG VIDEO INI|RINGKASAN)\s*[:\n]+",
        "",
        clean,
        count=1,
        flags=re.IGNORECASE,
    )
    clean = re.split(
        r"\n\s*\n(?:(?:✨\s*)?YANG AKAN KAMU DAPAT|(?:🔎\s*)?POIN PENTING|"
        r"(?:💬\s*)?(?:IKUT BERDISKUSI|MENURUT KAMU\?|UNTUK DIDISKUSIKAN)|"
        r"YANG DIBAHAS DALAM VIDEO INI|MARI DISKUSIKAN|COBA TELAAH|COBA BEDAKAN|"
        r"UNTUK DIRENUNGKAN|MENURUTMU|"
        r"(?:🔥\s*)?DUKUNG(?: CHANNEL INI)?|(?:📱\s*)?CHANNEL|"
        r"(?:⚠️?\s*)?CATATAN KONTEN|"
        r"Atribusi sumber \(CC BY\):|Audit & edit editorial otomatis:)",
        clean,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return polish_youtube_metadata_description(
        re.sub(r"\n{3,}", "\n\n", clean).strip()
    )


def complete_youtube_description(
    job: ClipJob,
    clip: ClipFile,
    summary: str,
    tags: list[str],
) -> str:
    """Format every Short and long-form upload as a complete readable description."""
    clean_summary = youtube_description_summary(summary)
    max_summary = 1500 if is_compilation_clip(job, clip) else 850
    if len(clean_summary) > max_summary:
        clean_summary = clean_summary[:max_summary].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    if not clean_summary:
        title = clip_sidecar_title(clip) or clip.title or job.source_title or "Cuplikan pilihan"
        clean_summary = f"{title.strip()}."

    is_compilation = is_compilation_clip(job, clip)
    context = " ".join(
        value
        for value in (
            clip.title or "",
            clip.hook or "",
            clip.core_message or "",
            clip_candidate_text(job, clip),
            clean_summary,
            " ".join(tags),
        )
        if value
    )
    lowered = context.casefold()
    has_mystery_context = any(
        term in lowered for term in ("misteri", "mitos", "mistis", "horor", "gaib", "setan", "jin")
    )
    has_islamic_context = any(
        term in lowered
        for term in ("islam", "allah", "al-quran", "alquran", "quran", "nabi", "iman", "doa", "shalat", "salat")
    )
    if any(term in lowered for term in ("waris", "warisan", "pewaris", "ahli waris", "takziah")):
        discussion_label = "Mari diskusikan:"
        question = "Bagian aturan warisan mana yang paling sering disalahpahami?"
        cta_options = [
            "Simpan video ini sebagai pengingat sebelum membahas hak keluarga.",
            "Bagikan pembahasan ini kepada keluarga yang mungkin membutuhkannya.",
            "Ikuti channel ini untuk pembahasan hukum keluarga dan hikmah Islam berikutnya.",
        ]
    elif has_mystery_context and has_islamic_context:
        discussion_label = "Coba telaah:"
        question = "Bagian mana yang bersumber dari dalil, penafsiran, atau cerita?"
        cta_options = [
            "Simpan video ini untuk menelaah kembali konteks pembahasannya.",
            "Bagikan jika pembahasan ini membantu memisahkan dalil, penafsiran, dan cerita.",
            "Ikuti channel ini untuk kajian kontekstual dan cek fakta berikutnya.",
        ]
    elif has_mystery_context:
        discussion_label = "Coba bedakan:"
        question = "Bagian mana yang merupakan fakta, pengalaman, atau penafsiran?"
        cta_options = [
            "Simpan video ini sebagai pengingat untuk memeriksa konteks sebelum percaya.",
            "Bagikan jika pembahasan ini membantu membedakan cerita, penafsiran, dan fakta.",
            "Ikuti channel ini untuk cerita kontekstual dan cek fakta berikutnya.",
        ]
    elif any(term in lowered for term in ("islam", "allah", "nabi", "iman", "doa", "shalat", "salat")):
        discussion_label = "Untuk direnungkan:"
        question = "Hikmah mana yang paling relevan dengan kehidupanmu?"
        cta_options = [
            "Simpan video ini jika ingin merenungkan kembali pesannya.",
            "Bagikan pembahasan ini kepada orang yang mungkin membutuhkannya.",
            "Ikuti channel ini untuk hikmah dan pembahasan kontekstual berikutnya.",
        ]
    else:
        discussion_label = "Menurutmu:"
        question = "Poin mana yang paling membuka sudut pandangmu?"
        cta_options = [
            "Simpan video ini jika ingin melihat kembali poin utamanya.",
            "Bagikan kepada orang yang mungkin mendapat manfaat dari pembahasan ini.",
            "Ikuti channel ini untuk pembahasan informatif berikutnya.",
        ]
    cta_seed = f"{clip.title or ''}|{clean_summary}".encode("utf-8")
    contextual_cta = cta_options[hashlib.sha256(cta_seed).digest()[0] % len(cta_options)]

    ordered_tags: list[str] = []
    seen: set[str] = set()
    candidates = [*tags]
    if not is_compilation:
        candidates.append("Shorts")
    for raw in candidates:
        tag = re.sub(r"[^\w\d_]", "", str(raw).strip().lstrip("#"), flags=re.UNICODE)[:30]
        if not tag or (is_compilation and tag.casefold() == "shorts") or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        ordered_tags.append(tag)

    display_tags = ordered_tags
    if not is_compilation:
        generic_tags = {
            "dakwah",
            "faktamenarik",
            "hikmah",
            "islam",
            "pelajaranhidup",
        }
        display_tags = sorted(
            (tag for tag in ordered_tags if tag.casefold() != "shorts"),
            key=lambda tag: tag.casefold() in generic_tags,
        )[:4]
        display_tags.append("Shorts")
    else:
        display_tags = display_tags[:5]

    sections = [clean_summary]
    if is_compilation:
        highlights = youtube_description_highlights(context, is_compilation=True)
        sections.append(
            "Yang dibahas dalam video ini:\n"
            + "\n".join(f"- {item}" for item in highlights)
        )
    sections.extend(
        [
            f"{discussion_label}\n{question}",
            contextual_cta,
        ]
    )
    if display_tags:
        sections.append(" ".join(f"#{tag}" for tag in display_tags))
    return "\n\n".join(sections)[:5000]


def default_youtube_description(job: ClipJob, clip: ClipFile) -> str:
    caption = sidecar_social_caption(clip)
    tags = default_youtube_tags(job, clip)
    description = complete_youtube_description(job, clip, caption, tags)
    description = append_youtube_chapters(description, clip)
    return append_youtube_source_attribution(description, job)


def clip_sidecar_payload(clip: ClipFile) -> dict[str, Any]:
    clip_path = output_path_from_url(clip.url)
    json_path = clip_path.with_suffix(".json") if clip_path is not None else None
    if json_path is None or not json_path.is_file():
        return {}
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def youtube_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def youtube_chapters_from_sidecar(clip: ClipFile) -> list[str]:
    """Build valid manual chapters from the rendered long-form editorial arc."""
    payload = clip_sidecar_payload(clip)
    if payload.get("output_format") != "landscape_compilation":
        return []
    raw_parts = payload.get("parts")
    if not isinstance(raw_parts, list):
        return []

    prepared: list[tuple[float, str]] = []
    cursor = 0.0
    for index, raw in enumerate(raw_parts, start=1):
        if not isinstance(raw, dict):
            continue
        try:
            duration = float(raw.get("duration") or 0.0)
            if duration <= 0:
                duration = float(raw.get("end") or 0.0) - float(raw.get("start") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0:
            continue
        raw_title = str(raw.get("title") or f"Bagian {index}")
        title = re.sub(r"\s+", " ", raw_title).strip(" -|:.")[:70] or f"Bagian {index}"
        prepared.append((cursor, title))
        cursor += duration

    # YouTube requires 00:00, at least three timestamps, and chapters of at
    # least ten seconds. Skip any boundary that would create a short chapter.
    chapters: list[tuple[float, str]] = []
    for timestamp, title in prepared:
        if chapters and timestamp - chapters[-1][0] < 10:
            continue
        if timestamp > 0 and cursor - timestamp < 10:
            continue
        chapters.append((timestamp, title))
    if len(chapters) < 3 or chapters[0][0] != 0:
        return []
    return [f"{youtube_timestamp(timestamp)} {title}" for timestamp, title in chapters]


def append_youtube_chapters(description: str, clip: ClipFile) -> str:
    chapters = youtube_chapters_from_sidecar(clip)
    clean = description.strip()
    if not chapters or "BAB VIDEO:" in clean:
        return clean[:5000]
    block = "BAB VIDEO:\n" + "\n".join(chapters)
    attribution_marker = "Atribusi sumber (CC BY):"
    if attribution_marker in clean:
        before, after = clean.split(attribution_marker, 1)
        return f"{before.rstrip()}\n\n{block}\n\n{attribution_marker}{after}"[:5000]
    return f"{clean}\n\n{block}".strip()[:5000]


def youtube_source_attribution(job: ClipJob) -> str:
    """Return required CC attribution without asking the metadata LLM to invent it."""
    if not job.request.url.strip():
        return ""
    metadata = metadata_for_job(job)
    if not is_creative_commons_info(metadata):
        return ""
    title = str(metadata.get("title") or job.source_title or "Video sumber").strip()
    creator = str(metadata.get("uploader") or job.source_uploader or "Kreator sumber").strip()
    source_url = str(metadata.get("webpage_url") or job.source_url or job.request.url).strip()
    license_name = str(metadata.get("license") or "Creative Commons Attribution").strip()
    return (
        "Atribusi sumber (CC BY):\n"
        f"Judul: {title[:180]}\n"
        f"Kreator: {creator[:120]}\n"
        f"Sumber: {source_url[:500]}\n"
        f"Lisensi: {license_name[:120]}\n"
        "Diolah secara editorial oleh @ryuundyofficial."
    )


def append_youtube_source_attribution(description: str, job: ClipJob) -> str:
    attribution = youtube_source_attribution(job)
    clean = description.strip()
    if not attribution or attribution in clean:
        return clean[:5000]
    available = max(0, 5000 - len(attribution) - 2)
    return f"{clean[:available].rstrip()}\n\n{attribution}".strip()[:5000]


def append_fendy_auditor_attribution(description: str, clip: ClipFile) -> str:
    """Keep the accountable Fendy audit identity on all newly rendered uploads."""
    sidecar = clip_sidecar_payload(clip)
    auditor = sidecar.get("auditor_identity") if isinstance(sidecar, dict) else None
    if not isinstance(auditor, dict):
        return description.strip()[:5000]
    name = re.sub(r"\s+", " ", str(auditor.get("name") or "")).strip()
    audit_id = re.sub(r"[^A-Za-z0-9-]", "", str(auditor.get("audit_id") or ""))[:24]
    if name.casefold() != "fendy" or not audit_id:
        return description.strip()[:5000]
    attribution = (
        f"Audit & edit editorial otomatis: Fendy Clipper · ID {audit_id}. "
        "Hak materi sumber tetap pada pemegang hak masing-masing."
    )
    clean = description.strip()
    if attribution in clean:
        return clean[:5000]
    available = max(0, 5000 - len(attribution) - 2)
    return f"{clean[:available].rstrip()}\n\n{attribution}".strip()[:5000]


def monetization_readiness_is_eligible(sidecar: dict[str, Any], readiness: dict[str, Any]) -> bool:
    """Accept current audits and safely reinterpret older compilation audits."""
    if readiness.get("eligible_for_private_upload_review"):
        return True
    try:
        audit_version = int(readiness.get("audit_version") or 1)
    except (TypeError, ValueError):
        audit_version = 1
    if audit_version >= 2:
        # Current audits are intentionally conservative; do not reinterpret a
        # failed story/authenticity signal using the looser legacy rules.
        return False

    signals = readiness.get("signals")
    if not isinstance(signals, dict):
        return False
    output_format = str(sidecar.get("output_format") or "")
    is_compilation = output_format == "landscape_compilation"
    substantive_transformation = bool(signals.get("substantive_visual_edits")) or bool(
        is_compilation
        and signals.get("structured_story_arc")
        and signals.get("editorial_hook_and_context")
        and signals.get("original_core_message")
    )
    try:
        originality_score = int(readiness.get("originality_score") or 0)
        minimum_score = int(
            readiness.get("minimum_originality_score") or (4 if is_compilation else 3)
        )
    except (TypeError, ValueError):
        return False
    return bool(
        signals.get("enhanced_edit")
        and substantive_transformation
        and originality_score >= minimum_score
    )


def monetization_preflight_transformation_message(
    sidecar: dict[str, Any],
    readiness: dict[str, Any],
) -> str:
    """Explain the actual failed audit signal instead of always blaming Enhanced Edit."""
    signals = readiness.get("signals")
    if not isinstance(signals, dict):
        return (
            "Upload diblokir: audit transformasi editorial belum lengkap. "
            "Render ulang clip dengan Fendy Clipper terbaru."
        )
    try:
        current_audit_version = int(readiness.get("audit_version") or 1)
    except (TypeError, ValueError):
        current_audit_version = 1
    if not signals.get("enhanced_edit"):
        return (
            "Upload diblokir: Enhanced Edit tidak aktif pada hasil render ini. "
            "Aktifkan Enhanced Edit lalu render ulang sebelum review private di YouTube Studio."
        )
    if current_audit_version >= 2 and not signals.get("cohesive_editorial_arc"):
        return (
            "Upload diblokir: clip belum membentuk alur editorial yang utuh dari hook ke pesan inti dan payoff. "
            "Pilih kandidat dengan point utama serta ending tuntas, lalu render ulang."
        )
    is_compilation = str(sidecar.get("output_format") or "") == "landscape_compilation"
    if (
        current_audit_version >= 5
        and is_compilation
        and not signals.get("chapter_specific_editorial_framing")
    ):
        return (
            "Upload diblokir: long-form baru memiliki susunan bab, tetapi belum ada framing editorial "
            "yang spesifik pada setiap bab. Render ulang agar hook, POV, dan beat edit tiap bagian "
            "tercatat berbeda dari template umum."
        )
    if current_audit_version >= 2 and not signals.get("content_timed_editing"):
        return (
            "Upload diblokir: perubahan masih terlihat seperti template umum dan belum mengikuti isi ucapan. "
            "Render ulang agar cut kamera, emphasis, atau audio cue mengikuti beat transcript."
        )
    if current_audit_version >= 4 and not signals.get("content_adaptive_visual_direction"):
        return (
            "Upload diblokir: gaya visual belum tercatat mengikuti isi cerita dan berisiko terlihat "
            "mass-produced. Render ulang dengan Auto FYP terbaru."
        )
    if is_compilation and not signals.get("structured_story_arc"):
        return (
            "Upload diblokir: kompilasi belum memiliki structured story arc yang cukup. "
            "Render ulang resume agar hook, perkembangan, dan payoff tersusun jelas."
    )
    try:
        score = int(readiness.get("originality_score") or 0)
        minimum = int(
            readiness.get("minimum_originality_score") or (4 if is_compilation else 3)
        )
    except (TypeError, ValueError):
        score, minimum = 0, 4 if is_compilation else 3
    if score < minimum:
        return (
            f"Upload diblokir: skor transformasi editorial {score}/{minimum}. "
            "Tambahkan konteks, pesan inti, dan penyuntingan substantif lalu render ulang."
        )
    return (
        "Upload diblokir: hasil render belum mencatat transformasi visual atau editorial substantif. "
        "Render ulang dengan perubahan yang membuat hasil jelas berbeda dari sumber."
    )


def youtube_monetization_preflight_issue(job: ClipJob, clip: ClipFile) -> str | None:
    """Block private upload when rights or substantive-edit evidence is missing."""
    metadata = metadata_for_job(job)
    if job.request.url.strip() and not is_creative_commons_info(metadata):
        return (
            "Upload diblokir: bukti lisensi Creative Commons sumber tidak ditemukan. "
            "Gunakan rekaman milik sendiri atau sumber dengan metadata CC dan izin komersial yang dapat dibuktikan."
        )
    if job.request.url.strip() and not job.request.confirm_source_rights:
        return (
            "Upload diblokir: lisensi Creative Commons pada metadata YouTube bukan bukti bahwa "
            "uploader memiliki seluruh hak audio dan visual. Proses ulang sumber setelah Anda "
            "mengonfirmasi kepemilikan atau izin komersial yang dapat dibuktikan."
        )
    if job.request.url.strip():
        rights_risks = source_rights_risk_reasons(metadata)
        if rights_risks:
            return (
                "Upload diblokir: sumber URL berisiko tinggi terkena Content ID ("
                + "; ".join(rights_risks[:2])
                + "). Label CC dan atribusi tidak menghapus hak broadcaster/pemilik rekaman. "
                "Gunakan rekaman milik sendiri atau materi dengan izin tertulis yang mencakup audio dan visual."
            )
    sidecar = clip_sidecar_payload(clip)
    if str(sidecar.get("production_model") or "") == "codex_long_story_director":
        story_director = sidecar.get("story_director")
        if not isinstance(story_director, dict) or not story_director.get(
            "quality_gate_passed"
        ):
            return (
                "Upload diblokir: quality gate Long Story belum lolos. "
                "Pilih materi dengan sedikitnya tiga beat unik dan render ulang tanpa filler."
            )
    production_model = str(sidecar.get("production_model") or "")
    if production_model.startswith("codex_scene_cinema_v"):
        readiness = sidecar.get("growth_readiness")
        if not isinstance(readiness, dict):
            readiness = sidecar.get("one_k_long_form_readiness")
        story_arc = sidecar.get("story_arc")
        final_qc = sidecar.get("final_qc")
        cold_open_contract = sidecar.get("cold_open_contract")
        requires_v2_contract = production_model != "codex_scene_cinema_v1"
        if (
            not job.request.confirm_long_animate_rights
            or not isinstance(readiness, dict)
            or not readiness.get("quality_gate_passed")
            or not isinstance(story_arc, list)
            or any(
                not isinstance(scene, dict)
                or scene.get("voice_provider") == "silent_fallback_review_required"
                for scene in story_arc
            )
            or (
                requires_v2_contract
                and (not isinstance(final_qc, dict) or not final_qc.get("passed"))
            )
            or (
                requires_v2_contract
                and (
                    not isinstance(cold_open_contract, dict)
                    or not cold_open_contract.get("quality_gate_passed")
                )
            )
        ):
            return (
                "Upload diblokir: Long Animate belum lolos pemeriksaan hak, narasi suara, "
                "atau quality gate scene. Periksa naskah/provider lalu render ulang."
            )
    if str(sidecar.get("output_format") or "") == "vertical_short":
        raw_fyp_score = sidecar.get("score")
        try:
            fyp_score = int(round(float(raw_fyp_score)))
        except (TypeError, ValueError):
            fyp_score = 0
        if fyp_score < SHORT_UPLOAD_MIN_FYP_SCORE:
            return (
                "Upload diblokir: skor FYP klip "
                f"{fyp_score}/{SHORT_UPLOAD_MIN_FYP_SCORE}. Render ulang dengan "
                "auto-repair terbaru atau pilih kandidat yang lebih kuat."
            )
        raw_retention_score = sidecar.get("retention_score")
        if isinstance(raw_retention_score, (int, float)) and not isinstance(
            raw_retention_score,
            bool,
        ):
            retention_score = max(0, min(100, int(round(raw_retention_score))))
            if 0 < retention_score < 58:
                return (
                    "Upload diblokir: kesiapan retention 30 detik "
                    f"{retention_score}/58. Pilih kandidat dengan hook, ritme, dan "
                    "perkembangan beat yang lebih konsisten."
                )
        try:
            duration = float(sidecar.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration > YOUTUBE_SHORTS_MAX_SECONDS:
            return (
                f"Upload diblokir: durasi {duration:.1f} detik melewati batas Shorts "
                f"{YOUTUBE_SHORTS_MAX_SECONDS} detik. Render ulang dengan durasi yang sesuai."
            )
        aspect_ratio = str(sidecar.get("aspect_ratio") or "").strip()
        if aspect_ratio and aspect_ratio not in {"9:16", "1:1"}:
            return (
                f"Upload diblokir: rasio {aspect_ratio} tidak memenuhi format vertikal/persegi Shorts. "
                "Render ulang dalam 9:16."
            )
        thumbnail_strategy = str(sidecar.get("thumbnail_strategy") or "").strip()
        if thumbnail_strategy and thumbnail_strategy != "embedded_shorts_cover_frame":
            return (
                "Upload diblokir: Short belum memiliki frame cover tertanam yang dapat dipilih. "
                "Render ulang dengan Fendy Clipper terbaru."
            )
        compliance = sidecar.get("shorts_policy_compliance")
        if isinstance(compliance, dict) and not compliance.get(
            "duration_within_official_limit", True
        ):
            return (
                "Upload diblokir: audit teknis Shorts menandai durasi di luar batas resmi. "
                "Render ulang clip."
            )
    readiness = sidecar.get("monetization_readiness") if isinstance(sidecar, dict) else None
    if not isinstance(readiness, dict):
        return (
            "Upload diblokir: output lama belum memiliki audit monetisasi. "
            "Render ulang clip dengan Fendy Clipper terbaru."
        )
    try:
        audit_version = int(readiness.get("audit_version") or 1)
    except (TypeError, ValueError):
        audit_version = 1
    if audit_version >= 6:
        auditor = sidecar.get("auditor_identity")
        if (
            not isinstance(auditor, dict)
            or str(auditor.get("name") or "").casefold() != "fendy"
            or str(auditor.get("display_signature") or "").upper() != "FENDY AUDIT"
            or not str(auditor.get("audit_id") or "").startswith("FND-")
        ):
            return (
                "Upload diblokir: identitas auditor Fendy tidak ditemukan pada output. "
                "Render ulang dengan Fendy Clipper terbaru."
            )
        if not auditor.get("visible_video_signature"):
            return (
                "Upload diblokir: watermark visual ryuundyofficial belum tertanam di video. "
                "Pastikan FFmpeg drawtext tersedia lalu render ulang."
            )
        growth_blueprint = sidecar.get("codex_growth_blueprint")
        if not isinstance(growth_blueprint, dict):
            return (
                "Upload diblokir: blueprint pertumbuhan Codex belum tercatat. "
                "Render ulang agar audit retention dan subscriber lengkap."
            )
    if not monetization_readiness_is_eligible(sidecar, readiness):
        return monetization_preflight_transformation_message(sidecar, readiness)
    return None


def clip_requires_altered_content_disclosure(clip: ClipFile) -> bool:
    sidecar = clip_sidecar_payload(clip)
    replacement = sidecar.get("background_replacement")
    adaptive_split = sidecar.get("adaptive_text_split")
    background_mode = str(sidecar.get("background_mode") or "")
    return bool(
        sidecar.get("altered_content_disclosure_required")
        or sidecar.get("background_replaced")
        or isinstance(replacement, dict)
        or (isinstance(adaptive_split, dict) and adaptive_split.get("enabled"))
        or background_mode == "mosque"
    )


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
    "is concise but substantial. Use fully natural Bahasa Indonesia with no untranslated English fragments. "
    "Preserve the exact subject and object of the transcript; do not merge related concepts into a broader claim. "
    "Treat religious word counts, quotations, verse references, and similar numeric claims carefully: only state "
    "them as facts when clearly supported by the supplied clip context; otherwise describe them as claims or as "
    "topics discussed by the speaker. "
    "Never state folklore, personal experiences, myths, "
    "or supernatural claims as verified religious facts. Do not invent source URLs, channels, uploaders, "
    "sponsors, licenses, or credits; verified CC attribution is appended separately by the application. "
    "Return strict JSON only."
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


def polish_youtube_metadata_title(value: str) -> str:
    """Remove generic tails that waste the most valuable mobile title space."""
    clean = re.sub(r"\s+", " ", value).strip(" -|:–—")
    generic_tail = (
        r"(?:\s*[-–—:|]\s*|\s+)(?:penjelasan lengkap|begini aturannya|"
        r"wajib tahu|simak sampai selesai|fakta mengejutkan|bikin kaget|ternyata)\s*[!?.]*$"
    )
    previous = ""
    while clean != previous:
        previous = clean
        clean = re.sub(generic_tail, "", clean, flags=re.I).strip(" -|:–—")
    return clean


def polish_youtube_metadata_description(value: str) -> str:
    """Repair small language leaks while preserving the model's factual wording."""
    clean = re.sub(
        r"^(?:video|klip|shorts?) ini\s+(?:menjelaskan|membahas|mengulas)\s+",
        "",
        value.strip(),
        flags=re.I,
    )
    clean = re.sub(
        r"^menurut ajaran\s*,\s*",
        "Menurut penjelasan pembicara, ",
        clean,
        flags=re.I,
    )
    replacements = {
        r"\bwithout restrictions?\b": "tanpa batasan",
        r"\btanpa restrictions?\b": "tanpa batasan",
        r"\bno restrictions?\b": "tanpa batasan",
        r"\brestrictions?\b": "batasan",
    }
    for pattern, replacement in replacements.items():
        clean = re.sub(pattern, replacement, clean, flags=re.I)
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return clean[:1].upper() + clean[1:] if clean else ""


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
    clean_title = polish_youtube_metadata_title(
        re.sub(r"https?://\S+", "", clean_title)
    )
    description_lines = [
        line.strip()
        for line in description.splitlines()
        if line.strip()
        and not re.search(r"https?://|^\s*(?:sumber|source|channel\s+sumber)\s*:", line, flags=re.I)
    ]
    description = polish_youtube_metadata_description(
        strip_hashtag_lines("\n".join(description_lines))
    )
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
    # compact for Shorts and a five-to-ten-minute story resume.
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
    sidecar = clip_sidecar_payload(clip)
    cover_headline = (
        str(sidecar.get("thumbnail_headline") or "").strip()
        if not is_compilation
        else ""
    )
    raw_story_arc = sidecar.get("story_arc") if is_compilation else None
    story_outline = ""
    if isinstance(raw_story_arc, list):
        story_lines: list[str] = []
        for raw_part in raw_story_arc[:8]:
            if not isinstance(raw_part, dict):
                continue
            role = re.sub(
                r"[^a-z_]",
                "",
                str(raw_part.get("narrative_role") or "development").lower(),
            )
            part_title = re.sub(r"\s+", " ", str(raw_part.get("title") or "")).strip()
            if part_title:
                story_lines.append(f"- {role}: {part_title[:100]}")
        if story_lines:
            story_outline = "Struktur cerita hasil render:\n" + "\n".join(story_lines) + "\n"
    format_name = (
        "video Long Story landscape berdurasi lima sampai sepuluh menit"
        if is_compilation
        else "YouTube Shorts"
    )
    system_prompt = (
        YOUTUBE_METADATA_SYSTEM_PROMPT.replace(
            "YouTube Shorts metadata writer",
            "YouTube long-form highlight metadata writer",
        ).replace(
            "short clips",
            "five-to-ten-minute story-resume videos",
        )
        if is_compilation
        else YOUTUBE_METADATA_SYSTEM_PROMPT
    )
    format_hashtag_rule = (
        "- Jangan gunakan hashtag #Shorts untuk video kompilasi.\n"
        if is_compilation
        else "- Sertakan #Shorts sebagai salah satu hashtag.\n"
    )
    long_form_packaging_rule = (
        "- Untuk long-form, bingkai judul sebagai satu masalah universal dan satu manfaat/jawaban "
        "yang benar-benar dibahas; taruh kata terpenting di bagian awal, dan jangan memakai kata "
        "'resume', 'rangkuman', 'highlight', atau durasi video. Janji judul harus terjawab oleh alur "
        "dan harus cocok dengan cold-open, tanpa membocorkan payoff secara menyesatkan.\n"
        if is_compilation
        else ""
    )
    shorts_cover_rule = (
        "- Selaraskan title dengan headline frame cover yang sudah tertanam: pertahankan topik dan janji utamanya, "
        "tetapi jangan menyalinnya secara kaku bila hasilnya tidak natural.\n"
        if cover_headline
        else ""
    )
    cover_context = (
        f"Headline frame cover yang sudah tertanam: {cover_headline}\n"
        if cover_headline
        else ""
    )
    user_prompt = (
        f"Buat metadata {format_name} untuk video ini.\n"
        "Aturan:\n"
        "- Pahami konteks transkrip klip ini saja; jangan memakai metadata video sumber.\n"
        "- Title baru harus kuat, natural, 35-68 karakter, maksimal 70 karakter, tanpa hashtag agar terbaca utuh di ponsel.\n"
        "- Title harus menyebut objek/topik yang tepat dari transkrip. Jangan mencampur uang takziah, harta waris, "
        "sedekah, atau objek terkait lain seolah semuanya sama.\n"
        "- Jangan memakai ekor generik seperti 'Penjelasan Lengkap', 'Begini Aturannya', 'Wajib Tahu', "
        "'Simak Sampai Selesai', atau 'Bikin Kaget'.\n"
        "- Perbaiki salah dengar transkrip yang jelas; jangan menyalin kata acak atau kalimat pembuka yang rusak.\n"
        "- Hindari ALL CAPS dan clickbait generik; tonjolkan manfaat, konflik, kejutan, atau hikmah yang benar-benar ada.\n"
        f"{long_form_packaging_rule}"
        f"{shorts_cover_rule}"
        "- Description baru 2-3 kalimat informatif, sekitar 180-450 karakter. Kalimat pertama harus langsung "
        "menyebut topik/kata kunci utama secara natural; kalimat berikutnya menjelaskan konflik, aturan, atau manfaat "
        "yang benar-benar dibahas tanpa menahan jawaban secara clickbait.\n"
        "- Jangan membuka dengan frasa datar 'Video ini membahas' atau 'Video ini menjelaskan'; mulai dari pertanyaan, "
        "masalah, atau jawaban inti yang konkret.\n"
        "- Gunakan Bahasa Indonesia sepenuhnya tanpa kata Inggris yang belum diterjemahkan. Untuk isu hukum/agama, "
        "atribusi jawaban sebagai isi penjelasan pembicara dan jangan memperluas klaim di luar transkrip.\n"
        "- Description hanya berisi ringkasan inti. Jangan tambahkan heading, CTA Like/Share/Subscribe, "
        "handle channel, catatan konten, chapter, atribusi, atau baris hashtag; aplikasi menatanya otomatis.\n"
        "- Jangan gunakan emoji, ikon, atau simbol dekoratif pada description.\n"
        "- Bahasa Indonesia.\n"
        "- Jangan tulis URL, nama channel, uploader, TV, sponsor, kredit, atau label 'Sumber'.\n"
        "- Buat 4-5 hashtag baru yang spesifik dan relevan dengan isi klip, bukan hashtag generik berulang.\n"
        f"{format_hashtag_rule}"
        "- Wajib isi semua field JSON: title, description, hashtags.\n"
        'Return JSON exactly like {"title": "...", "description": "...", "hashtags": ["#tag1", "#tag2"]}.\n\n'
        f"Judul kerja klip (hanya petunjuk, wajib ditulis ulang): {title}\n"
        f"{cover_context}"
        f"{story_outline}"
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
    scores_by_index = {
        candidate.index: (
            candidate.score
            + candidate.key_point_score * 0.10
            + candidate.loop_score * 0.05
            + candidate.retention_score * 0.12
        )
        for candidate in job.candidates
    }
    ranked: list[tuple[float, int, int, ClipFile]] = []
    for position, clip in enumerate(job.clips):
        clip_index = clip_index_from_name(clip.name)
        score = scores_by_index.get(clip_index, -1) if clip_index is not None else -1
        if clip.subscriber_intent_score is not None:
            score += clip.subscriber_intent_score * 0.08
        ranked.append((score, -position, clip_index or position + 1, clip))

    ranked.sort(reverse=True)
    return [clip.url for _, _, _, clip in ranked[: max(1, count)]]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reusable_youtube_upload(
    job_id: str,
    clip_url: str,
    clip_sha256: str,
) -> YouTubeUploadJob | None:
    with youtube_uploads_lock:
        uploads = sorted(youtube_uploads.values(), key=lambda item: item.created_at, reverse=True)
        for upload in uploads:
            exact_clip = upload.source_job_id == job_id and upload.clip_url == clip_url
            same_fingerprint = bool(
                clip_sha256
                and upload.clip_sha256
                and upload.clip_sha256 == clip_sha256
            )
            if exact_clip and upload.status in {"queued", "running"}:
                return upload
            if (
                upload.status == "completed"
                and upload.video_url
                and not upload.dry_run
                and (exact_clip or same_fingerprint)
            ):
                return upload
    return None


def verified_duplicate_for_upload(
    upload: YouTubeUploadJob,
    clip_sha256: str,
) -> YouTubeUploadJob | None:
    with youtube_uploads_lock:
        candidates = sorted(
            youtube_uploads.values(),
            key=lambda item: item.finished_at or item.updated_at,
            reverse=True,
        )
        for candidate in candidates:
            if candidate.id == upload.id:
                continue
            exact_clip = (
                candidate.source_job_id == upload.source_job_id
                and candidate.clip_url == upload.clip_url
            )
            same_fingerprint = bool(
                clip_sha256
                and candidate.clip_sha256
                and candidate.clip_sha256 == clip_sha256
            )
            if (
                candidate.status == "completed"
                and candidate.video_url
                and not candidate.dry_run
                and (exact_clip or same_fingerprint)
            ):
                return candidate
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


def youtube_uploads_with_queue_positions(
    uploads: list[YouTubeUploadJob],
) -> list[YouTubeUploadJob]:
    backend_time = datetime.now(timezone.utc)
    backend_now = backend_time.isoformat()
    queued = sorted(
        (upload for upload in uploads if upload.status == "queued"),
        key=lambda item: item.created_at,
    )
    positions = {upload.id: index for index, upload in enumerate(queued, start=1)}
    queue_total = len(queued)
    positioned: list[YouTubeUploadJob] = []
    for upload in uploads:
        remaining_seconds: float | None = None
        if upload.clip_delete_after and not upload.clip_deleted_at:
            try:
                delete_at = datetime.fromisoformat(upload.clip_delete_after)
                if delete_at.tzinfo is None:
                    delete_at = delete_at.replace(tzinfo=timezone.utc)
                remaining_seconds = max(0.0, (delete_at - backend_time).total_seconds())
            except ValueError:
                remaining_seconds = 0.0
        positioned.append(
            upload.model_copy(
                update={
                    "queue_position": positions.get(upload.id),
                    "queue_total": queue_total if upload.status == "queued" else None,
                    "backend_now": backend_now,
                    "clip_delete_remaining_seconds": remaining_seconds,
                }
            )
        )
    return positioned


def create_youtube_upload_record(job_id: str, request: YouTubeUploadRequest) -> YouTubeUploadJob:
    job, clip, index = find_job_clip(job_id, request.clip_url)
    growth_target_views, growth_target_subscribers = youtube_growth_targets(job, clip)
    clip_path = output_path_from_url(clip.url)
    if clip_path is None or not clip_path.is_file():
        raise HTTPException(status_code=404, detail="File clip tidak ditemukan di outputs")
    try:
        clip_fingerprint = file_sha256(clip_path)
    except OSError as exc:
        raise HTTPException(status_code=409, detail=f"File clip tidak dapat dibaca: {exc}") from exc
    existing = reusable_youtube_upload(job_id, clip.url, clip_fingerprint)
    if request.dry_run and existing is not None and existing.status == "completed":
        existing = None
    if existing is not None:
        exact_clip = existing.source_job_id == job_id and existing.clip_url == clip.url
        if exact_clip or existing.status in {"queued", "running"}:
            if (
                existing.growth_target_views != growth_target_views
                or existing.growth_target_subscribers != growth_target_subscribers
            ):
                set_youtube_upload(
                    existing.id,
                    growth_target_views=growth_target_views,
                    growth_target_subscribers=growth_target_subscribers,
                )
                with youtube_uploads_lock:
                    return youtube_uploads.get(existing.id, existing)
            return existing

        completed_at = now_iso()
        delete_after = completed_upload_cleanup_after(completed_at)
        return existing.model_copy(
            update={
                "id": uuid.uuid4().hex,
                "source_job_id": job_id,
                "clip_url": clip.url,
                "clip_name": clip.name,
                "created_at": completed_at,
                "updated_at": completed_at,
                "started_at": completed_at,
                "finished_at": completed_at,
                "duration_seconds": 0.0,
                "clip_sha256": clip_fingerprint,
                "queue_position": None,
                "queue_total": None,
                "clip_delete_after": delete_after,
                "clip_deleted_at": None,
                "clip_delete_error": None,
                "clip_cleanup_started_at": None,
                "clip_cleanup_current_step": None,
                "clip_cleanup_completed_steps": [],
                "clip_cleanup_step_details": {},
                "growth_target_views": growth_target_views,
                "growth_target_subscribers": growth_target_subscribers,
                "logs": [
                    "Upload dilewati: fingerprint file identik sudah terupload dan URL YouTube terverifikasi.",
                    f"File duplikat lokal akan dibersihkan otomatis setelah {max(1, env_int('YOUTUBE_DELETE_UPLOADED_CLIP_DELAY_SECONDS', 30))} detik.",
                ],
                "error": None,
            }
        )

    thumbnail_url = request.thumbnail_url or clip.thumbnail_url
    thumbnail_path = output_path_from_url(thumbnail_url) if thumbnail_url else None
    if (thumbnail_path is None or not thumbnail_path.is_file()) and is_compilation_clip(job, clip):
        fallback_thumbnail = clip_path.with_name(f"{clip_path.stem}_thumb.jpg")
        if fallback_thumbnail.is_file():
            thumbnail_path = fallback_thumbnail
            thumbnail_url = clip_url(fallback_thumbnail)
    safe_thumbnail_url = thumbnail_url if thumbnail_path is not None and thumbnail_path.is_file() else None
    if is_compilation_clip(job, clip):
        if thumbnail_path is None or not thumbnail_path.is_file():
            raise HTTPException(
                status_code=409,
                detail=(
                    "Thumbnail otomatis untuk Highlight/Resume landscape belum tersedia. "
                    "Render ulang video agar thumbnail 16:9 dibuat sebelum upload YouTube."
                ),
            )
        if thumbnail_path.suffix.casefold() not in {".jpg", ".jpeg", ".png"}:
            raise HTTPException(status_code=409, detail="Thumbnail YouTube harus berupa JPG atau PNG.")
        if thumbnail_path.stat().st_size > 2 * 1024 * 1024:
            raise HTTPException(status_code=409, detail="Thumbnail YouTube melebihi batas aman 2 MB.")
        try:
            import cv2

            image = cv2.imread(str(thumbnail_path.resolve()))
        except Exception:
            image = None
        if image is None:
            raise HTTPException(status_code=409, detail="Thumbnail otomatis tidak dapat dibaca sebagai gambar.")
        height, width = image.shape[:2]
        if width < 640 or height < 360 or abs((width / height) - (16 / 9)) > 0.03:
            raise HTTPException(
                status_code=409,
                detail=f"Thumbnail harus landscape 16:9; file saat ini {width}x{height}.",
            )
    monetization_issue = youtube_monetization_preflight_issue(job, clip)
    if monetization_issue:
        raise HTTPException(status_code=409, detail=monetization_issue)
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
    description = complete_youtube_description(job, clip, description, tags)
    description = append_youtube_chapters(description, clip)
    description = append_youtube_source_attribution(description, job)
    altered_content = clip_requires_altered_content_disclosure(clip)
    playlist = (
        automatic_long_form_playlist(job, clip, title, description)
        if is_compilation_clip(job, clip)
        else request.playlist
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
        thumbnail_attached=False,
        visibility=safe_youtube_visibility(request.visibility),
        made_for_kids=request.made_for_kids,
        altered_content=altered_content,
        tags=tags,
        playlist=playlist,
        target_channel=request.target_channel,
        dry_run=request.dry_run,
        clip_sha256=clip_fingerprint,
        growth_series=clip.growth_series or "",
        growth_target_views=growth_target_views,
        growth_target_subscribers=growth_target_subscribers,
        logs=(
            (
                [f"Thumbnail otomatis 16:9 siap dipasang: {thumbnail_path.name}"]
                if is_compilation_clip(job, clip) and thumbnail_path is not None
                else []
            )
            + [
                "Preflight monetisasi lolos untuk upload Private; keputusan akhir tetap mengikuti review video dan channel oleh YouTube."
            ]
            + (
                [f"Playlist long-form dipilih otomatis dari isi cerita: {playlist}."]
                if is_compilation_clip(job, clip)
                else []
            )
            + (
                ["Penggantian backdrop terdeteksi; disclosure altered content akan dipilih saat upload."]
                if altered_content
                else []
            )
        ),
    )


def create_youtube_upload_batch_records(job_id: str, request: YouTubeBatchUploadRequest) -> list[YouTubeUploadJob]:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Job belum selesai")

    if request.clip_urls:
        clip_urls = list(dict.fromkeys(request.clip_urls))
    else:
        # Rank the complete set first, then keep only clips that will pass the
        # same preflight used by single uploads. One rejected top-ranked clip
        # must not abort an otherwise valid automatic batch.
        clips_by_url = {clip.url: clip for clip in job.clips}
        ranked_urls = best_youtube_clip_urls(job, len(job.clips))
        clip_urls = [
            clip_url
            for clip_url in ranked_urls
            if (
                (clip := clips_by_url.get(clip_url)) is not None
                and youtube_monetization_preflight_issue(job, clip) is None
            )
        ][: request.best_count]
    if not clip_urls:
        raise HTTPException(
            status_code=409,
            detail=(
                "Tidak ada clip yang lolos audit upload. Render ulang agar kandidat "
                "memiliki point utama dan ending tuntas."
            ),
        )

    uploads = [
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
    return list({upload.id: upload for upload in uploads}.values())


def queue_youtube_upload_jobs(uploads: list[YouTubeUploadJob]) -> None:
    cleanup_ids: list[str] = []
    has_queued = False
    with youtube_uploads_lock:
        for upload in uploads:
            if upload.id not in youtube_uploads:
                youtube_uploads[upload.id] = upload
            has_queued = has_queued or upload.status == "queued"
            if (
                upload.status == "completed"
                and upload.video_url
                and upload.clip_delete_after
                and not upload.clip_deleted_at
            ):
                cleanup_ids.append(upload.id)
        save_youtube_uploads_unlocked()
    for upload_id in cleanup_ids:
        schedule_completed_upload_cleanup(upload_id)
    if has_queued:
        start_youtube_worker_if_needed()


def auto_queue_youtube_uploads_for_job(job_id: str, logs: list[str]) -> None:
    try:
        require_youtube_ready()
        with youtube_upload_creation_lock:
            uploads = create_youtube_upload_batch_records(job_id, YouTubeBatchUploadRequest())
            queue_youtube_upload_jobs(uploads)
        queued_count = sum(upload.status == "queued" for upload in uploads)
        skipped_count = sum(
            upload.status == "completed" and bool(upload.video_url)
            for upload in uploads
        )
        logs.append(
            f"Auto upload YouTube: {queued_count} clip masuk antrean"
            + (f", {skipped_count} duplikat terverifikasi dilewati." if skipped_count else ".")
        )
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


def youtube_video_id_from_url(value: str) -> str:
    normalized = normalize_youtube_video_url(value) or ""
    return (parse_qs(urlparse(normalized).query).get("v") or [""])[0]


def youtube_performance_status(
    snapshot: YouTubePerformanceSnapshot,
    *,
    target_views: int,
    target_subscribers: int,
) -> Literal["learning", "views_target_met", "target_met"]:
    subscribers = snapshot.subscribers_gained or 0
    if snapshot.views >= target_views and subscribers >= target_subscribers:
        return "target_met"
    if snapshot.views >= target_views:
        return "views_target_met"
    return "learning"


def latest_performance_snapshot(upload: YouTubeUploadJob) -> YouTubePerformanceSnapshot | None:
    return upload.performance_snapshots[-1] if upload.performance_snapshots else None


def comparable_performance_medians(
    upload: YouTubeUploadJob,
    uploads: list[YouTubeUploadJob],
) -> dict[str, float]:
    if not upload.growth_series:
        return {}
    peers = [
        latest
        for item in uploads
        if item.id != upload.id
        and item.status == "completed"
        and item.growth_series == upload.growth_series
        and item.growth_target_views == upload.growth_target_views
        and (latest := latest_performance_snapshot(item)) is not None
    ]
    if len(peers) < 3:
        return {}

    def values(name: str) -> list[float]:
        return [
            float(value)
            for item in peers
            if (value := getattr(item, name)) is not None
        ]

    medians: dict[str, float] = {}
    for field in ("views", "average_view_percentage"):
        field_values = values(field)
        if field_values:
            medians[field] = float(median(field_values))
    conversion_values = [
        (item.subscribers_gained or 0) * 1000 / item.views
        for item in peers
        if item.views > 0 and item.subscribers_gained is not None
    ]
    if conversion_values:
        medians["subscribers_per_1000_views"] = float(median(conversion_values))
    return medians


def youtube_performance_diagnosis(
    upload: YouTubeUploadJob,
    snapshot: YouTubePerformanceSnapshot,
    uploads: list[YouTubeUploadJob],
) -> list[str]:
    target_views = upload.growth_target_views
    target_subscribers = upload.growth_target_subscribers
    subscribers = snapshot.subscribers_gained
    if snapshot.views >= target_views and (subscribers or 0) >= target_subscribers:
        return [
            f"Target tercapai: {snapshot.views:,} views dan {subscribers or 0} subscriber.",
            "Pertahankan tema dan struktur; ubah hanya satu variabel packaging pada eksperimen berikutnya.",
        ]

    diagnosis: list[str] = []
    if snapshot.views >= target_views and subscribers is not None and subscribers < target_subscribers:
        diagnosis.append(
            "Reach sudah mencapai target, tetapi konversi subscriber belum; perkuat janji seri dan related video."
        )
    elif subscribers is not None and subscribers >= target_subscribers:
        diagnosis.append(
            "Konversi subscriber sudah mencapai target; fokus berikutnya memperluas reach dari hook dan packaging."
        )

    baselines = comparable_performance_medians(upload, uploads)
    if not baselines:
        diagnosis.append(
            "Baseline seri belum cukup; kumpulkan sedikitnya tiga upload sejenis sebelum mengubah bobot algoritma."
        )
    else:
        baseline_views = baselines.get("views", 0)
        if baseline_views and snapshot.views < baseline_views * 0.75:
            diagnosis.append(
                "Reach berada di bawah median seri; prioritaskan eksperimen first frame dan hook."
            )
        baseline_retention = baselines.get("average_view_percentage", 0)
        if (
            baseline_retention
            and snapshot.average_view_percentage is not None
            and snapshot.average_view_percentage < baseline_retention * 0.9
        ):
            diagnosis.append(
                "Persentase tonton berada di bawah median seri; majukan payoff dan pangkas bagian yang tidak menambah informasi."
            )
        baseline_conversion = baselines.get("subscribers_per_1000_views", 0)
        if snapshot.views and subscribers is not None and baseline_conversion:
            conversion = subscribers * 1000 / snapshot.views
            if conversion < baseline_conversion * 0.8:
                diagnosis.append(
                    "Konversi subscriber berada di bawah median seri; buat alasan mengikuti seri lebih spesifik."
                )
    if not diagnosis:
        diagnosis.append(
            "Performa masih dalam fase belajar dan tidak menunjukkan kelemahan relatif yang jelas."
        )
    return diagnosis[:4]


def record_youtube_performance(
    upload_id: str,
    snapshot: YouTubePerformanceSnapshot,
) -> YouTubeUploadJob:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
        if upload is None:
            raise HTTPException(status_code=404, detail="YouTube upload not found")
        if upload.status != "completed" or not upload.video_url:
            raise HTTPException(status_code=409, detail="Upload belum memiliki URL YouTube final")
        snapshots = [*upload.performance_snapshots, snapshot][-24:]
        provisional = upload.model_copy(update={"performance_snapshots": snapshots})
        status = youtube_performance_status(
            snapshot,
            target_views=upload.growth_target_views,
            target_subscribers=upload.growth_target_subscribers,
        )
        diagnosis = youtube_performance_diagnosis(
            provisional,
            snapshot,
            list(youtube_uploads.values()),
        )
        updated = provisional.model_copy(
            update={
                "updated_at": now_iso(),
                "performance_status": status,
                "performance_diagnosis": diagnosis,
            }
        )
        youtube_uploads[upload_id] = updated
        save_youtube_uploads_unlocked()
        return updated


def youtube_analytics_access_token() -> str:
    client_id = os.environ.get("YOUTUBE_ANALYTICS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_ANALYTICS_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_ANALYTICS_REFRESH_TOKEN", "").strip()
    if not all((client_id, client_secret, refresh_token)):
        return ""
    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"OAuth YouTube Analytics gagal: {exc}") from exc
    token = str(payload.get("access_token") or "") if isinstance(payload, dict) else ""
    if not token:
        raise RuntimeError("OAuth YouTube Analytics tidak mengembalikan access token")
    return token


def youtube_analytics_snapshot(upload: YouTubeUploadJob) -> YouTubePerformanceSnapshot | None:
    access_token = youtube_analytics_access_token()
    if not access_token:
        return None
    video_id = youtube_video_id_from_url(upload.video_url or "")
    if not video_id:
        raise RuntimeError("URL YouTube tidak memiliki video ID yang valid")
    start_value = upload.finished_at or upload.created_at
    try:
        start_date = datetime.fromisoformat(start_value).date().isoformat()
    except ValueError:
        start_date = datetime.now(timezone.utc).date().isoformat()
    metrics = (
        "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
        "averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost"
    )
    url = "https://youtubeanalytics.googleapis.com/v2/reports?" + urlencode(
        {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": datetime.now(timezone.utc).date().isoformat(),
            "metrics": metrics,
            "filters": f"video=={video_id}",
        }
    )
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Query YouTube Analytics gagal: {exc}") from exc
    headers = payload.get("columnHeaders") if isinstance(payload, dict) else []
    rows = payload.get("rows") if isinstance(payload, dict) else []
    if not isinstance(headers, list) or not isinstance(rows, list) or not rows:
        values: dict[str, Any] = {}
    else:
        names = [str(item.get("name") or "") for item in headers if isinstance(item, dict)]
        values = dict(zip(names, rows[0], strict=False)) if isinstance(rows[0], list) else {}
    return YouTubePerformanceSnapshot(
        captured_at=now_iso(),
        source="youtube_analytics",
        views=int(values.get("views") or 0),
        engaged_views=int(values["engagedViews"]) if values.get("engagedViews") is not None else None,
        average_view_duration=float(values["averageViewDuration"]) if values.get("averageViewDuration") is not None else None,
        average_view_percentage=float(values["averageViewPercentage"]) if values.get("averageViewPercentage") is not None else None,
        likes=int(values["likes"]) if values.get("likes") is not None else None,
        comments=int(values["comments"]) if values.get("comments") is not None else None,
        shares=int(values["shares"]) if values.get("shares") is not None else None,
        subscribers_gained=int(values["subscribersGained"]) if values.get("subscribersGained") is not None else None,
        subscribers_lost=int(values["subscribersLost"]) if values.get("subscribersLost") is not None else None,
    )


def youtube_public_snapshot(upload: YouTubeUploadJob) -> YouTubePerformanceSnapshot:
    video_id = youtube_video_id_from_url(upload.video_url or "")
    if not video_id:
        raise RuntimeError("URL YouTube tidak memiliki video ID yang valid")
    try:
        payload = youtube_data_api_get("videos", {"part": "statistics", "id": video_id})
        items = payload.get("items") if isinstance(payload, dict) else []
        item = items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}
        statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    except RuntimeError:
        statistics = {}
    if not statistics:
        try:
            with YoutubeDL(ytdlp_probe_options()) as ydl:
                info = ydl.extract_info(upload.video_url or "", download=False)
        except Exception as exc:
            raise RuntimeError(f"Statistik publik video gagal diambil: {exc}") from exc
        if isinstance(info, dict):
            statistics = {
                "viewCount": info.get("view_count"),
                "likeCount": info.get("like_count"),
                "commentCount": info.get("comment_count"),
            }
    if not statistics:
        raise RuntimeError("Statistik publik video belum tersedia")
    return YouTubePerformanceSnapshot(
        captured_at=now_iso(),
        source="youtube_public",
        views=int(statistics.get("viewCount") or 0),
        likes=int(statistics["likeCount"]) if statistics.get("likeCount") is not None else None,
        comments=int(statistics["commentCount"]) if statistics.get("commentCount") is not None else None,
    )


def refresh_youtube_performance(upload_id: str) -> YouTubeUploadJob:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="YouTube upload not found")
    if upload.status != "completed" or not upload.video_url:
        raise HTTPException(status_code=409, detail="Upload belum memiliki URL YouTube final")
    analytics_error = ""
    try:
        snapshot = youtube_analytics_snapshot(upload)
    except RuntimeError as exc:
        analytics_error = str(exc)
        snapshot = None
    if snapshot is None:
        try:
            snapshot = youtube_public_snapshot(upload)
        except RuntimeError as exc:
            detail = str(exc)
            if analytics_error:
                detail = f"{analytics_error}; fallback statistik publik gagal: {detail}"
            raise HTTPException(status_code=502, detail=detail) from exc
    return record_youtube_performance(upload_id, snapshot)


def terminate_youtube_upload_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=CANCEL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=CANCEL_GRACE_SECONDS)


def monitor_youtube_upload_process(
    process: subprocess.Popen[str],
    on_line,
    *,
    stall_timeout_seconds: float,
    terminal_success_prefix: str = "VIDEO_URL:",
    terminal_grace_seconds: float = 5.0,
) -> tuple[int, bool]:
    """Stream output without allowing a silent uploader subprocess to hang forever."""
    if process.stdout is None:
        raise RuntimeError("YouTube uploader stdout is unavailable")

    output_queue: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        try:
            for line in process.stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    last_progress = time.monotonic()
    timeout = max(0.1, float(stall_timeout_seconds))
    terminal_success_at: float | None = None

    while True:
        now = time.monotonic()
        if terminal_success_at is not None:
            terminal_remaining = max(0.0, terminal_grace_seconds - (now - terminal_success_at))
            if terminal_remaining <= 0:
                terminate_youtube_upload_process(process)
                return 0, False
        else:
            terminal_remaining = timeout
        remaining = min(timeout - (now - last_progress), terminal_remaining)
        if remaining <= 0:
            terminate_youtube_upload_process(process)
            return (0, False) if terminal_success_at is not None else (process.wait(), True)
        try:
            line = output_queue.get(timeout=min(1.0, remaining))
        except queue.Empty:
            continue
        if line is None:
            code = process.wait()
            return (0, False) if terminal_success_at is not None else (code, False)
        cleaned = line.rstrip()
        if cleaned:
            last_progress = time.monotonic()
            on_line(cleaned)
            if terminal_success_prefix and cleaned.startswith(terminal_success_prefix):
                terminal_success_at = time.monotonic()


def auto_sync_youtube_upload_session(use_cdp: bool) -> tuple[bool, list[str], str | None]:
    logs: list[str] = []
    try:
        if use_cdp:
            sync_status = sync_youtube_cdp()
            logs.extend(sync_status.logs[-40:])
            logs.append(sync_status.message)
            if sync_status.ok:
                return True, logs, None

            logs.append("Sinkronisasi ringan belum berhasil; menjalankan repair Chrome CDP.")
            repair_status = repair_youtube_cdp(profile_sync_requested=True)
            logs.extend(repair_status.logs[-40:])
            logs.append(repair_status.message)
            return repair_status.ok, logs, repair_status.error

        login_status = setup_youtube_one_time_login()
        logs.extend(login_status.logs[-40:])
        logs.append(login_status.message)
        return login_status.ok, logs, login_status.error
    except HTTPException as exc:
        return False, logs, str(exc.detail)
    except Exception as exc:
        return False, logs, str(exc)


def completed_upload_cleanup_after(completed_at: str) -> str:
    delay_seconds = max(1, env_int("YOUTUBE_DELETE_UPLOADED_CLIP_DELAY_SECONDS", 30))
    try:
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        completed = datetime.now(timezone.utc)
    return (completed + timedelta(seconds=delay_seconds)).isoformat()


def cleanup_youtube_staging_file(upload_path: Path, source_path: Path | None) -> bool:
    try:
        resolved = upload_path.resolve()
        staging_root = YOUTUBE_CDP_STAGING_DIR.resolve()
        if resolved == source_path or staging_root not in resolved.parents:
            return False
        resolved.unlink(missing_ok=True)
        return not resolved.exists()
    except OSError:
        return False


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
    is_long_form = upload.clip_name.casefold().startswith(
        ("highlight_5menit_", "resume_cerita_", "long_animate_")
    )
    if is_long_form and not upload.thumbnail_url:
        raise RuntimeError("Upload long-form dibatalkan karena thumbnail otomatis belum tersedia.")
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
    thumbnail_content_type = "long-form" if is_long_form else "shorts"
    command.extend(["--thumbnail-content-type", thumbnail_content_type])
    media_duration = media_duration_seconds(clip_path)
    if media_duration > 0:
        command.extend(["--media-duration-seconds", f"{media_duration:.3f}"])
    if upload.thumbnail_url:
        thumbnail_path = output_path_from_url(upload.thumbnail_url)
        if is_long_form and (thumbnail_path is None or not thumbnail_path.is_file()):
            raise RuntimeError("File thumbnail otomatis tidak ditemukan sebelum upload YouTube dimulai.")
        if thumbnail_path is not None and thumbnail_path.is_file():
            command.extend(
                [
                    "--thumbnail",
                    str(thumbnail_path),
                ]
            )
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
    if upload.altered_content:
        command.append("--altered-content")
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
    check_code, stalled = monitor_youtube_upload_process(
        process,
        check_logs.append,
        stall_timeout_seconds=max(
            30,
            env_int("YOUTUBE_SESSION_SYNC_STALL_TIMEOUT_SECONDS", 90),
        ),
    )
    check_error = (
        "Validasi session YouTube tersendat dan dihentikan otomatis."
        if stalled
        else youtube_upload_error_from_logs(check_logs) if check_code else None
    )
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
    capture_code, stalled = monitor_youtube_upload_process(
        process,
        capture_logs.append,
        stall_timeout_seconds=max(
            30,
            env_int("YOUTUBE_SESSION_SYNC_STALL_TIMEOUT_SECONDS", 90),
        ),
    )
    capture_error = (
        "Sinkronisasi session YouTube tersendat dan dihentikan otomatis."
        if stalled
        else youtube_upload_error_from_logs(capture_logs) if capture_code else None
    )
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


def youtube_graphical_process_env() -> dict[str, str]:
    """Return an environment connected to the host desktop when available."""
    process_env = os.environ.copy()
    bridge_dir = Path(process_env.get("YOUTUBE_GUI_BRIDGE_DIR", "/app/data/youtube-gui"))
    display_file = bridge_dir / "display"
    try:
        bridge_display = display_file.read_text(encoding="utf-8").strip().splitlines()[0]
    except (OSError, IndexError):
        bridge_display = ""
    if bridge_display:
        process_env["DISPLAY"] = bridge_display

    configured_authority = process_env.get("XAUTHORITY", "")
    authority_candidates = [Path(configured_authority)] if configured_authority else []
    authority_candidates.append(bridge_dir / "Xauthority")
    host_runtime_dir = Path(process_env.get("YOUTUBE_HOST_RUNTIME_DIR", "/run/fendy-clipper-host-user"))
    if host_runtime_dir.is_dir():
        try:
            authority_candidates.extend(
                sorted(
                    host_runtime_dir.glob(".mutter-Xwaylandauth.*"),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
            )
        except OSError:
            pass
    for authority_path in authority_candidates:
        if authority_path.is_file() and os.access(authority_path, os.R_OK):
            process_env["XAUTHORITY"] = str(authority_path)
            break

    if (host_runtime_dir / "bus").exists():
        process_env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={host_runtime_dir / 'bus'}")
    return process_env


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
    process_env = youtube_graphical_process_env()
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
        process_env = youtube_graphical_process_env()
        process_env["YOUTUBE_LOGIN_HEADLESS"] = "false"
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


def set_youtube_cleanup_step(
    upload_id: str,
    step: str | None,
    completed_steps: list[str],
    step_details: dict[str, YouTubeCleanupStepProgress] | None = None,
) -> None:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
        started_at = upload.clip_cleanup_started_at if upload else None
        persisted_details = upload.clip_cleanup_step_details if upload else {}
    set_youtube_upload(
        upload_id,
        clip_cleanup_started_at=started_at or now_iso(),
        clip_cleanup_current_step=step,
        clip_cleanup_completed_steps=[
            item for item in YOUTUBE_CLEANUP_STEPS if item in completed_steps
        ],
        clip_cleanup_step_details=step_details if step_details is not None else persisted_details,
    )


def delete_completed_youtube_upload_clip(
    upload_id: str,
    *,
    steps: tuple[str, ...] | None = None,
) -> tuple[int, bool]:
    """Delete one confirmed-uploaded clip and atomically remove it from its source job."""
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
    if upload is None:
        raise RuntimeError("Catatan upload YouTube tidak ditemukan")
    if upload.status != "completed" or not upload.video_url or upload.dry_run:
        raise RuntimeError("Upload YouTube belum terkonfirmasi selesai; file tidak dihapus")

    completed_steps = list(upload.clip_cleanup_completed_steps)
    step_details = dict(upload.clip_cleanup_step_details)
    selected_steps = set(steps or YOUTUBE_CLEANUP_STEPS)

    def complete_file_step(step: str, paths: set[Path]) -> int:
        started_perf = time.perf_counter()
        started_at = now_iso()
        step_details[step] = YouTubeCleanupStepProgress(started_at=started_at)
        set_youtube_cleanup_step(upload_id, step, completed_steps, step_details)
        removed_count = remove_output_paths(paths)
        remaining = sorted(str(path) for path in paths if path.exists())
        if remaining:
            raise RuntimeError(
                f"Tahap cleanup {step} belum tuntas: " + ", ".join(remaining[:3])
            )
        if step not in completed_steps:
            completed_steps.append(step)
        step_details[step] = YouTubeCleanupStepProgress(
            started_at=started_at,
            completed_at=now_iso(),
            duration_ms=max(0, round((time.perf_counter() - started_perf) * 1000)),
            removed_items=removed_count,
        )
        set_youtube_cleanup_step(upload_id, None, completed_steps, step_details)
        return removed_count

    with jobs_lock:
        job = jobs.get(upload.source_job_id)
        if job is None:
            if any(
                clip.url == upload.clip_url
                for known_job in jobs.values()
                for clip in known_job.clips
            ):
                raise RuntimeError(
                    "Workspace upload orphan masih direferensikan job lain; cleanup ditunda"
                )
            orphan_clip = ClipFile(
                name=upload.clip_name,
                url=upload.clip_url,
                size_bytes=0,
                thumbnail_url=upload.thumbnail_url,
            )
            protected_dirs = {
                work_dir
                for known_job in jobs.values()
                for clip in known_job.clips
                if (work_dir := clip_output_work_dir(clip)) is not None
            }
            removed = cleanup_clip_files(orphan_clip)
            removed += cleanup_output_work_dirs(
                [orphan_clip],
                protected_dirs,
                strict=True,
            )
            set_youtube_cleanup_step(upload_id, None, list(YOUTUBE_CLEANUP_STEPS))
            return removed, True

        target_clip = next((clip for clip in job.clips if clip.url == upload.clip_url), None)
        if target_clip is None:
            orphan_clip = ClipFile(
                name=upload.clip_name,
                url=upload.clip_url,
                size_bytes=0,
                thumbnail_url=upload.thumbnail_url,
            )
            protected_dirs = {
                work_dir
                for clip in job.clips
                if (work_dir := clip_output_work_dir(clip)) is not None
            }
            removed = cleanup_clip_files(orphan_clip)
            removed += cleanup_output_work_dirs(
                [orphan_clip],
                protected_dirs,
                strict=True,
            )
            removed_job = not job.clips
            if removed_job:
                jobs.pop(job.id, None)
                job_secrets.pop(job.id, None)
                cancelled_job_ids.discard(job.id)
                save_jobs_unlocked()
            set_youtube_cleanup_step(upload_id, None, list(YOUTUBE_CLEANUP_STEPS))
            return removed, removed_job

        active_uploads = active_youtube_uploads_for_job(job.id, {target_clip.url})
        if active_uploads:
            raise RuntimeError("Masih ada upload aktif untuk file klip yang sama")

        clip_path = output_path_from_url(target_clip.url)
        video_paths = {clip_path} if clip_path is not None else set()
        thumbnail_paths: set[Path] = set()
        metadata_paths: set[Path] = set()
        if clip_path is not None:
            thumbnail_paths.update(
                {
                    clip_path.with_name(f"{clip_path.stem}_thumb.jpg"),
                    clip_path.with_name(f"{clip_path.stem}_thumb.txt"),
                }
            )
            metadata_paths.update(
                {
                    clip_path.with_name(f"{clip_path.stem}_caption.txt"),
                    clip_path.with_suffix(".srt"),
                    clip_path.with_name(f"{clip_path.stem}.dynamic.ass"),
                    clip_path.with_suffix(".json"),
                }
            )
        if target_clip.thumbnail_url:
            thumbnail_path = output_path_from_url(target_clip.thumbnail_url)
            if thumbnail_path is not None:
                thumbnail_paths.add(thumbnail_path)

        removed = 0
        if "thumbnail" in selected_steps:
            removed += complete_file_step("thumbnail", thumbnail_paths)
        if "metadata" in selected_steps:
            removed += complete_file_step("metadata", metadata_paths)
        if "video" in selected_steps:
            removed += complete_file_step("video", video_paths)

        remaining_clips = [clip for clip in job.clips if clip.url != target_clip.url]
        if "workspace" in selected_steps:
            workspace_started_perf = time.perf_counter()
            workspace_started_at = now_iso()
            step_details["workspace"] = YouTubeCleanupStepProgress(started_at=workspace_started_at)
            set_youtube_cleanup_step(upload_id, "workspace", completed_steps, step_details)
            workspace_removed = 0
            if not remaining_clips:
                protected_dirs = {
                    work_dir
                    for other_job_id, other_job in jobs.items()
                    if other_job_id != job.id
                    for clip in other_job.clips
                    if (work_dir := clip_output_work_dir(clip)) is not None
                }
                workspace_removed = cleanup_output_work_dirs(
                    job.clips,
                    protected_dirs,
                    strict=True,
                )
                removed += workspace_removed
            if "workspace" not in completed_steps:
                completed_steps.append("workspace")
            step_details["workspace"] = YouTubeCleanupStepProgress(
                started_at=workspace_started_at,
                completed_at=now_iso(),
                duration_ms=max(0, round((time.perf_counter() - workspace_started_perf) * 1000)),
                removed_items=workspace_removed,
            )
            set_youtube_cleanup_step(upload_id, None, completed_steps, step_details)

        if "job_sync" not in selected_steps:
            return removed, False

        sync_started_perf = time.perf_counter()
        sync_started_at = now_iso()
        step_details["job_sync"] = YouTubeCleanupStepProgress(started_at=sync_started_at)
        set_youtube_cleanup_step(upload_id, "job_sync", completed_steps, step_details)
        if not remaining_clips:
            jobs.pop(job.id, None)
            job_secrets.pop(job.id, None)
            cancelled_job_ids.discard(job.id)
            save_jobs_unlocked()
            if "job_sync" not in completed_steps:
                completed_steps.append("job_sync")
            step_details["job_sync"] = YouTubeCleanupStepProgress(
                started_at=sync_started_at,
                completed_at=now_iso(),
                duration_ms=max(0, round((time.perf_counter() - sync_started_perf) * 1000)),
            )
            set_youtube_cleanup_step(upload_id, None, completed_steps, step_details)
            return removed, True

        data = job.model_dump()
        data["clips"] = remaining_clips
        data["updated_at"] = now_iso()
        jobs[job.id] = ClipJob(**data)
        save_jobs_unlocked()
        if "job_sync" not in completed_steps:
            completed_steps.append("job_sync")
        step_details["job_sync"] = YouTubeCleanupStepProgress(
            started_at=sync_started_at,
            completed_at=now_iso(),
            duration_ms=max(0, round((time.perf_counter() - sync_started_perf) * 1000)),
        )
        set_youtube_cleanup_step(upload_id, None, completed_steps, step_details)
        return removed, False


def schedule_completed_upload_cleanup(upload_id: str) -> None:
    with youtube_cleanup_lock:
        if upload_id in youtube_cleanup_scheduled:
            return
        youtube_cleanup_scheduled.add(upload_id)

    def cleanup_worker() -> None:
        retry_count = 0
        removed_job = False
        try:
            while True:
                with youtube_uploads_lock:
                    upload = youtube_uploads.get(upload_id)
                if (
                    upload is None
                    or upload.status != "completed"
                    or not upload.video_url
                    or upload.dry_run
                    or upload.clip_deleted_at
                    or not upload.clip_delete_after
                ):
                    return

                try:
                    delete_at = datetime.fromisoformat(upload.clip_delete_after)
                except ValueError:
                    delete_at = datetime.now(timezone.utc)
                if delete_at.tzinfo is None:
                    delete_at = delete_at.replace(tzinfo=timezone.utc)
                try:
                    cleanup_started_at = datetime.fromisoformat(
                        upload.finished_at or upload.updated_at
                    )
                except ValueError:
                    cleanup_started_at = delete_at - timedelta(
                        seconds=max(1, env_int("YOUTUBE_DELETE_UPLOADED_CLIP_DELAY_SECONDS", 30))
                    )
                if cleanup_started_at.tzinfo is None:
                    cleanup_started_at = cleanup_started_at.replace(tzinfo=timezone.utc)
                cleanup_window = max(
                    1.0,
                    (delete_at - cleanup_started_at).total_seconds(),
                )
                pending_steps = [
                    step
                    for step in YOUTUBE_CLEANUP_STEPS
                    if step not in upload.clip_cleanup_completed_steps
                ]
                if not pending_steps:
                    deleted_at = now_iso()
                    removed = sum(
                        detail.removed_items
                        for detail in upload.clip_cleanup_step_details.values()
                    )
                    message = (
                        f"File klip dan pendukungnya terhapus otomatis ({removed} item); "
                        + ("job sumber ikut dibersihkan." if removed_job else "job sumber diperbarui.")
                    )
                    set_youtube_upload(
                        upload_id,
                        clip_delete_after=None,
                        clip_deleted_at=deleted_at,
                        clip_delete_error=None,
                        clip_cleanup_current_step=None,
                        clip_cleanup_completed_steps=list(YOUTUBE_CLEANUP_STEPS),
                        logs=[*upload.logs, message][-160:],
                    )
                    return

                next_step = pending_steps[0]
                step_at = cleanup_started_at + timedelta(
                    seconds=cleanup_window * YOUTUBE_CLEANUP_STEP_RATIOS[next_step]
                )
                remaining = (step_at - datetime.now(timezone.utc)).total_seconds()
                if remaining > 0:
                    time.sleep(min(remaining, 60))
                    continue

                try:
                    _, step_removed_job = delete_completed_youtube_upload_clip(
                        upload_id,
                        steps=(next_step,),
                    )
                    removed_job = removed_job or step_removed_job
                except Exception as exc:
                    retry_count += 1
                    retry_delay = min(300, 30 * (2 ** min(retry_count - 1, 3)))
                    message = (
                        f"Tahap cleanup {next_step} belum berhasil, "
                        f"retry {retry_delay} detik: {exc}"
                    )
                    set_youtube_upload(
                        upload_id,
                        clip_delete_error=str(exc),
                        clip_cleanup_current_step=None,
                        logs=[*upload.logs, message][-160:],
                    )
                    time.sleep(retry_delay)
                    continue
                retry_count = 0
                set_youtube_upload(upload_id, clip_delete_error=None)
        finally:
            with youtube_cleanup_lock:
                youtube_cleanup_scheduled.discard(upload_id)

    threading.Thread(target=cleanup_worker, daemon=True).start()


def complete_youtube_upload_as_duplicate(
    upload_id: str,
    duplicate: YouTubeUploadJob,
    *,
    local_file_exists: bool,
) -> None:
    completed_at = now_iso()
    delete_after = completed_upload_cleanup_after(completed_at) if local_file_exists else None
    set_youtube_upload(
        upload_id,
        status="completed",
        started_at=completed_at,
        finished_at=completed_at,
        duration_seconds=0.0,
        video_url=duplicate.video_url,
        thumbnail_attached=duplicate.thumbnail_attached,
        playlist_confirmed=duplicate.playlist_confirmed,
        clip_delete_after=delete_after,
        clip_deleted_at=None if local_file_exists else completed_at,
        clip_delete_error=None,
        clip_cleanup_started_at=None if local_file_exists else completed_at,
        clip_cleanup_current_step=None,
        clip_cleanup_completed_steps=[] if local_file_exists else list(YOUTUBE_CLEANUP_STEPS),
        clip_cleanup_step_details={},
        logs=[
            "Upload dilewati oleh worker: fingerprint/file sudah memiliki upload YouTube terverifikasi.",
            f"Referensi upload: {duplicate.id[:10]} · {duplicate.video_url}",
            (
                "File lokal duplikat masuk jadwal auto-cleanup."
                if local_file_exists
                else "File lokal sudah tidak ada; tidak diperlukan cleanup tambahan."
            ),
        ],
        error=None,
    )
    if delete_after:
        schedule_completed_upload_cleanup(upload_id)


def run_youtube_upload(upload_id: str) -> None:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
    if upload is None:
        return

    clip_path = output_path_from_url(upload.clip_url)
    known_duplicate = verified_duplicate_for_upload(upload, upload.clip_sha256 or "")
    if known_duplicate is not None:
        complete_youtube_upload_as_duplicate(
            upload_id,
            known_duplicate,
            local_file_exists=bool(clip_path and clip_path.is_file()),
        )
        return
    if clip_path is None or not clip_path.is_file():
        set_youtube_upload(
            upload_id,
            status="failed",
            finished_at=now_iso(),
            error="File clip tidak ditemukan sebelum upload dimulai.",
        )
        return
    try:
        clip_fingerprint = upload.clip_sha256 or file_sha256(clip_path)
    except OSError as exc:
        set_youtube_upload(
            upload_id,
            status="failed",
            finished_at=now_iso(),
            error=f"File clip tidak dapat dibaca sebelum upload: {exc}",
        )
        return
    if upload.clip_sha256 != clip_fingerprint:
        set_youtube_upload(upload_id, clip_sha256=clip_fingerprint)
        upload = upload.model_copy(update={"clip_sha256": clip_fingerprint})

    duplicate = verified_duplicate_for_upload(upload, clip_fingerprint)
    if duplicate is not None:
        complete_youtube_upload_as_duplicate(
            upload_id,
            duplicate,
            local_file_exists=True,
        )
        return

    started_perf = time.perf_counter()
    set_youtube_upload(
        upload_id,
        status="running",
        thumbnail_attached=False,
        playlist_confirmed=False,
        started_at=now_iso(),
        finished_at=None,
        duration_seconds=None,
        error=None,
    )

    logs: list[str] = list(upload.logs[-20:])
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
                if youtube_upload_last_resort_fallback_allowed() and youtube_auth_state_exists():
                    logs.append(f"Launcher Chrome CDP gagal: {exc.detail}")
                    logs.append(
                        f"Upload dialihkan otomatis ke Playwright storage-state: {YOUTUBE_PLAYWRIGHT_STATE}"
                    )
                    fallback_to_storage_state = True
                    use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=None)
                elif (
                    youtube_upload_last_resort_fallback_allowed()
                    and youtube_profile_upload_allowed()
                    and youtube_chromium_profile_ready()
                ):
                    logs.append(f"Launcher Chrome CDP gagal: {exc.detail}")
                    logs.append("Upload dialihkan otomatis ke profile Chromium backend langsung.")
                    fallback_to_chromium_profile = True
                    force_chromium_profile_for_attempt = True
                    use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=None)
                else:
                    raise RuntimeError(str(exc.detail)) from exc
            else:
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
        stall_repair_attempts = 0
        max_cdp_repairs = max(1, env_int("YOUTUBE_CDP_UPLOAD_REPAIR_ATTEMPTS", 3))
        max_stall_repairs = max(1, env_int("YOUTUBE_UPLOAD_STALL_REPAIR_ATTEMPTS", 2))
        stall_timeout_seconds = max(30, env_int("YOUTUBE_UPLOAD_STALL_TIMEOUT_SECONDS", 180))
        default_max_attempts = 6 if (use_cdp_for_attempt or youtube_auth_state_exists() or youtube_chromium_profile_ready()) else 1
        max_attempts = max(1, env_int("YOUTUBE_CDP_UPLOAD_MAX_ATTEMPTS", default_max_attempts))
        for attempt in range(1, max_attempts + 1):
            thumbnail_attached_for_attempt = False
            thumbnail_requirement_waived_for_attempt = False
            playlist_confirmed_for_attempt = False
            set_youtube_upload(upload_id, thumbnail_attached=False, playlist_confirmed=False)
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

            def record_upload_log(cleaned: str) -> None:
                nonlocal playlist_confirmed_for_attempt
                nonlocal thumbnail_attached_for_attempt
                nonlocal thumbnail_requirement_waived_for_attempt
                if cleaned.startswith("THUMBNAIL_ATTACHED:"):
                    thumbnail_attached_for_attempt = True
                    thumbnail_requirement_waived_for_attempt = False
                elif cleaned.startswith("THUMBNAIL_SKIPPED_DAILY_LIMIT:"):
                    thumbnail_attached_for_attempt = False
                    thumbnail_requirement_waived_for_attempt = True
                elif cleaned.startswith("THUMBNAIL_SKIPPED:"):
                    # A final verification can discover that Studio discarded
                    # an earlier thumbnail selection during a form re-render.
                    # Do not leave a stale positive badge in the frontend.
                    thumbnail_attached_for_attempt = False
                if cleaned.startswith("PLAYLIST_CONFIRMED:"):
                    playlist_confirmed_for_attempt = True
                logs.append(cleaned)
                set_youtube_upload(
                    upload_id,
                    logs=logs[-160:],
                    video_url=youtube_video_url_from_logs(logs),
                    visibility=youtube_final_visibility_from_logs(logs) or upload.visibility,
                    thumbnail_attached=thumbnail_attached_for_attempt,
                    playlist_confirmed=playlist_confirmed_for_attempt,
                )

            code, stalled = monitor_youtube_upload_process(
                process,
                record_upload_log,
                stall_timeout_seconds=stall_timeout_seconds,
            )
            command_upload_path = Path(command[3]).resolve()
            source_clip_path = output_path_from_url(upload.clip_url)
            if cleanup_youtube_staging_file(command_upload_path, source_clip_path):
                logs.append("File staging upload sementara dibersihkan.")

            video_url = youtube_video_url_from_logs(logs)
            requires_thumbnail = bool(
                upload.thumbnail_url
                and upload.clip_name.casefold().startswith(
                    ("highlight_5menit_", "resume_cerita_", "long_animate_")
                )
            )
            thumbnail_confirmation_error = ""
            if (
                code == 0
                and requires_thumbnail
                and not thumbnail_attached_for_attempt
                and not thumbnail_requirement_waived_for_attempt
            ):
                code = 1
                thumbnail_confirmation_error = (
                    "Browser belum mengonfirmasi thumbnail otomatis terpasang; upload belum diselesaikan."
                )
                logs.append(thumbnail_confirmation_error)
            playlist_confirmation_error = ""
            if code == 0 and upload.playlist and not playlist_confirmed_for_attempt:
                code = 1
                playlist_confirmation_error = (
                    f"Browser belum mengonfirmasi playlist '{upload.playlist}' terpasang; "
                    "upload belum diselesaikan."
                )
                logs.append(playlist_confirmation_error)
            if (
                video_url
                and not upload.dry_run
                and code != 0
                and (
                    not requires_thumbnail
                    or thumbnail_attached_for_attempt
                    or thumbnail_requirement_waived_for_attempt
                )
                and (not upload.playlist or playlist_confirmed_for_attempt)
            ):
                logs.append(
                    "Uploader berhenti setelah URL final terverifikasi; status dipulihkan sebagai sukses tanpa retry upload."
                )
                code = 0
                stalled = False
            error = (
                f"Uploader tidak mengirim progres selama {stall_timeout_seconds} detik."
                if stalled
                else thumbnail_confirmation_error
                or playlist_confirmation_error
                or youtube_upload_error_from_logs(logs)
                or f"youtube_uploader.py exited with code {code}"
            )
            if code == 0:
                completed_at = now_iso()
                delete_after = None
                if video_url and not upload.dry_run:
                    delete_after = completed_upload_cleanup_after(completed_at)
                    logs.append(
                        "Upload dan URL YouTube terverifikasi; file lokal akan dihapus otomatis "
                        f"dalam {max(1, env_int('YOUTUBE_DELETE_UPLOADED_CLIP_DELAY_SECONDS', 30))} detik."
                    )
                elif upload.dry_run:
                    logs.append("Dry-run selesai; file lokal tidak dijadwalkan untuk dihapus.")
                else:
                    logs.append(
                        "Upload selesai tetapi URL YouTube belum terverifikasi; file lokal tidak dihapus."
                    )
                set_youtube_upload(
                    upload_id,
                    status="completed",
                    thumbnail_attached=thumbnail_attached_for_attempt,
                    playlist_confirmed=playlist_confirmed_for_attempt,
                    logs=logs[-160:],
                    video_url=video_url,
                    finished_at=completed_at,
                    duration_seconds=elapsed_seconds(started_perf),
                    clip_delete_after=delete_after,
                    clip_deleted_at=None,
                    clip_delete_error=None,
                    clip_cleanup_started_at=None,
                    clip_cleanup_current_step=None,
                    clip_cleanup_completed_steps=[],
                    clip_cleanup_step_details={},
                )
                if delete_after:
                    schedule_completed_upload_cleanup(upload_id)
                return
            if stalled and attempt < max_attempts and stall_repair_attempts < max_stall_repairs:
                stall_repair_attempts += 1
                logs.append(
                    "Watchdog mendeteksi upload tersendat; menjalankan sinkronisasi session otomatis "
                    f"{stall_repair_attempts}/{max_stall_repairs} sebelum retry."
                )
                set_youtube_upload(upload_id, logs=logs[-160:], error=error)
                sync_ok, sync_logs, sync_error = auto_sync_youtube_upload_session(use_cdp_for_attempt)
                logs.extend(sync_logs[-80:])
                if sync_ok:
                    logs.append("Auto-sync berhasil; upload dilanjutkan dengan percobaan baru.")
                    set_youtube_upload(upload_id, logs=logs[-160:], error=None)
                else:
                    logs.append(f"Auto-sync belum valid: {sync_error or 'session belum siap'}")
                    if use_cdp_for_attempt and youtube_auth_state_exists():
                        logs.append("Retry dialihkan ke Playwright storage-state agar antrean tetap berjalan.")
                        fallback_to_storage_state = True
                        force_chromium_profile_for_attempt = False
                        use_cdp_for_attempt = False
                    set_youtube_upload(upload_id, logs=logs[-160:], error=sync_error or error)
                continue
            if attempt < max_attempts and youtube_navigation_retry_needed(error):
                logs.append(
                    "Navigasi YouTube Studio terputus sebelum file dipilih; retry memakai session yang sama."
                )
                set_youtube_upload(upload_id, logs=logs[-160:], error=error)
                continue
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
        pending_cleanup_ids = [
            upload.id
            for upload in youtube_uploads.values()
            if upload.status == "completed"
            and upload.video_url
            and upload.clip_delete_after
            and not upload.clip_deleted_at
            and not upload.dry_run
        ]
    if has_queued:
        start_youtube_worker_if_needed()
    for upload_id in pending_cleanup_ids:
        schedule_completed_upload_cleanup(upload_id)
    removed_orphans = cleanup_orphan_output_roots()
    if removed_orphans:
        print(
            f"Startup cleanup outputs: {removed_orphans} folder orphan dihapus.",
            flush=True,
        )


def discover_clips(started_at: float, output_root: Path | None = None) -> list[ClipFile]:
    clips: list[ClipFile] = []
    search_root = output_root or OUTPUTS_DIR
    for path in search_root.rglob("clips/*.mp4"):
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
        def sidecar_list(key: str, limit: int = 4) -> list[str]:
            value = sidecar.get(key)
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if isinstance(item, str) and item.strip()][:limit]

        improvement_ideas = unresolved_codex_ideas(sidecar, sidecar_list("improvement_ideas"))
        auditor = sidecar.get("auditor_identity")
        auditor = auditor if isinstance(auditor, dict) else {}
        growth = sidecar.get("codex_growth_blueprint")
        growth = growth if isinstance(growth, dict) else {}
        series = growth.get("series")
        series = series if isinstance(series, dict) else {}
        subscriber_intent = growth.get("subscriber_intent")
        subscriber_intent = subscriber_intent if isinstance(subscriber_intent, dict) else {}
        growth_readiness = sidecar.get("growth_readiness")
        if not isinstance(growth_readiness, dict):
            growth_readiness = sidecar.get("five_k_experiment_readiness")
        if not isinstance(growth_readiness, dict):
            growth_readiness = sidecar.get("one_k_long_form_readiness")
        growth_readiness = growth_readiness if isinstance(growth_readiness, dict) else {}

        raw_score = sidecar.get("score")
        fyp_score = (
            max(1, min(100, int(round(raw_score))))
            if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool)
            else None
        )
        def sidecar_score(key: str) -> int | None:
            value = sidecar.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            return max(0, min(100, int(round(value))))

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
                core_message=(
                    str(sidecar.get("core_message")).strip()
                    if sidecar.get("core_message")
                    else None
                ),
                strengths=sidecar_list("strengths"),
                weaknesses=sidecar_list("weaknesses"),
                improvement_ideas=improvement_ideas,
                applied_edits=sidecar_list("applied_edits", limit=8),
                key_point_score=sidecar_score("key_point_score"),
                loop_score=sidecar_score("loop_score"),
                retention_score=sidecar_score("retention_score"),
                boundary_quality=(
                    str(sidecar.get("boundary_quality")).strip()
                    if sidecar.get("boundary_quality")
                    else None
                ),
                output_resolution=(
                    str(sidecar.get("output_resolution")).strip()
                    if sidecar.get("output_resolution")
                    else None
                ),
                auditor_name=(
                    str(auditor.get("name")).strip() if auditor.get("name") else None
                ),
                audit_id=(
                    str(auditor.get("audit_id")).strip() if auditor.get("audit_id") else None
                ),
                growth_series=(
                    str(series.get("name")).strip() if series.get("name") else None
                ),
                growth_target_views=(
                    int(growth_readiness["target_views"])
                    if isinstance(growth_readiness.get("target_views"), (int, float))
                    and not isinstance(growth_readiness.get("target_views"), bool)
                    else None
                ),
                growth_target_subscribers=(
                    int(growth_readiness["target_subscribers"])
                    if isinstance(growth_readiness.get("target_subscribers"), (int, float))
                    and not isinstance(growth_readiness.get("target_subscribers"), bool)
                    else None
                ),
                subscriber_intent_score=(
                    max(0, min(100, int(round(subscriber_intent["score"]))))
                    if isinstance(subscriber_intent.get("score"), (int, float))
                    and not isinstance(subscriber_intent.get("score"), bool)
                    else None
                ),
                growth_status=(
                    str(growth_readiness.get("status")).strip()
                    if growth_readiness.get("status")
                    else None
                ),
                growth_quality_gate_passed=(
                    bool(growth_readiness.get("quality_gate_passed"))
                    if "quality_gate_passed" in growth_readiness
                    else None
                ),
                growth_next_action=(
                    str(growth_readiness.get("next_action")).strip()
                    if growth_readiness.get("next_action")
                    else None
                ),
                growth_checkpoints=[
                    int(item)
                    for item in growth_readiness.get("review_checkpoints", [])
                    if isinstance(item, (int, float)) and not isinstance(item, bool)
                ][:6],
            )
        )
    clips.sort(key=lambda item: item.name)
    return clips


def discover_candidates(started_at: float, output_root: Path | None = None) -> list[ClipCandidate]:
    search_root = output_root or OUTPUTS_DIR
    candidate_files = [
        path
        for path in search_root.rglob("candidates*.json")
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
        "socket_timeout": max(5, min(30, env_int("VIRAL_CC_YTDLP_SOCKET_TIMEOUT", 8))),
        "retries": 1,
        "extractor_retries": 1,
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
    if (
        "output file does not contain any stream" in combined
        or "does not contain any stream" in combined
        or "matches no streams" in combined
    ):
        return (
            "Track audio sumber belum terunduh lengkap. Sistem tidak akan memakai file .part lagi; "
            "ulangi job untuk melanjutkan download audio secara otomatis."
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


def cleanup_job_artifacts(output_root: Path) -> int:
    root = OUTPUTS_DIR.resolve()
    resolved = output_root.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError(f"Refusing to clean unsafe job output path: {resolved}")
    if not resolved.exists():
        return 0
    try:
        shutil.rmtree(resolved)
        return 1
    except OSError:
        return 0


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
    if request.clip_mode == "long_animate":
        try:
            duration = float(os.environ.get("LONG_ANIMATE_TARGET_DURATION_SECONDS", "20"))
        except ValueError:
            duration = 20.0
        duration = max(5.0, min(3600.0, duration))
    elif request.source_file:
        duration = probe_media_duration(Path(request.source_file))
    else:
        duration = fetch_video_duration(request.url)
    data = request.model_dump()
    if request.clip_mode == "short":
        data["max_duration"] = min(60.0, request.max_duration)
    elif request.clip_mode == "long_animate":
        data["top"] = 1
        data["analyze_seconds"] = None
        data["require_creative_commons"] = False
        data["burn_subtitles"] = True
        data["enhanced_edit"] = True
        data["background_mode"] = "keep"

    if request.top is None:
        data["top"] = choose_auto_top(duration)

    # Enforce: min_duration * target_clips <= 80% of the video length.
    budget_cap = max_clips_for_duration(duration, request.min_duration)
    if budget_cap is not None and data["top"] is not None:
        data["top"] = max(1, min(int(data["top"]), MAX_REQUESTED_CLIPS, budget_cap))
    elif data["top"] is not None:
        data["top"] = max(1, min(int(data["top"]), MAX_REQUESTED_CLIPS))

    if request.clip_mode != "long_animate" and request.analyze_seconds is None:
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
                data["ai_model"] = (
                    DEFAULT_AI_MODEL
                    if DEFAULT_AI_MODEL and DEFAULT_AI_MODEL in models
                    else models[0]
                )

    return ClipJobRequest(**data)


def build_clipper_command(
    request: ClipJobRequest,
    output_root: Path | None = None,
    script_path: Path | None = None,
) -> list[str]:
    command = [sys.executable, "clipper.py"]
    if request.clip_mode == "long_animate":
        if script_path is None:
            raise ValueError("Long Animate command requires a script file")
        command.extend(["--script-file", str(script_path)])
    elif request.source_file:
        command.extend(["--source-file", request.source_file])
    else:
        command.append(request.url)
    if output_root is not None:
        command.extend(["--output", str(output_root)])
    command.extend(
        [
            "--top",
            str(request.top or choose_auto_top(None)),
            "--min",
            str(request.min_duration),
            "--max",
            str(min(60.0, request.max_duration) if request.clip_mode == "short" else request.max_duration),
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
    command.extend(["--visual-mode", request.visual_mode])
    command.extend(["--background-mode", request.background_mode])
    if not request.burn_subtitles:
        command.append("--no-burn-subtitles")
    if not request.enhanced_edit:
        command.append("--no-enhanced-edit")
    if request.remove_running_text:
        command.append("--remove-running-text")
    if request.auto_blur_watermarks:
        command.append("--auto-blur-watermarks")
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
        if request.confirm_source_rights:
            command.append("--confirm-source-rights")

    if request.ai_enabled:
        command.append("--ai-enabled")
        if request.ai_base_url:
            command.extend(["--ai-base-url", request.ai_base_url])
        if request.ai_model:
            command.extend(["--ai-model", request.ai_model])
        if request.ai_api_key:
            command.extend(["--ai-api-key", request.ai_api_key])
    return command


FENDY_CLIPPER_PROGRESS_PATTERN = re.compile(
    r"^FENDY_CLIPPER_PROGRESS:(\d{1,3})\|([^|]+)\|(.*)$"
)


def parse_clipper_progress(line: str) -> dict[str, int | str] | None:
    match = FENDY_CLIPPER_PROGRESS_PATTERN.match((line or "").strip())
    if not match:
        return None
    raw_percent, stage, detail = match.groups()
    percent = max(0, min(100, int(raw_percent)))
    stage_steps = {
        "source": 1,
        "transcript": 2,
        "selection": 3,
        "render": 4,
        "finalize": 5,
        "complete": 5,
    }
    normalized_stage = stage.strip().casefold()
    return {
        "progress_percent": percent,
        "progress_stage": normalized_stage,
        "progress_detail": re.sub(r"\s+", " ", detail).strip()[:180],
        "progress_step": stage_steps.get(normalized_stage, 0),
        "progress_total_steps": 5,
    }


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

    output_root = OUTPUTS_DIR / job_id
    queued_started_perf = time.perf_counter()
    queued_started_iso = now_iso()
    if job_id in cancelled_job_ids:
        set_job(
            job_id,
            status="cancelled",
            started_at=queued_started_iso,
            **finish_job_updates(queued_started_perf),
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
        progress_percent=0,
        progress_stage="queued",
        progress_detail="Menunggu slot worker paralel yang tersedia",
        progress_step=0,
        progress_total_steps=5,
    )
    clip_job_slots.acquire()
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
            error="Proses dibatalkan sebelum slot worker berjalan.",
        )
        cancelled_job_ids.discard(job_id)
        preserve_job_files_on_cancel.discard(job_id)
        job_secrets.pop(job_id, None)
        clip_job_slots.release()
        return

    set_job(
        job_id,
        status="running",
        started_at=started_at_iso,
        finished_at=None,
        duration_seconds=None,
        progress_percent=1,
        progress_stage="source",
        progress_detail="Menyiapkan worker pemrosesan",
        progress_step=1,
        progress_total_steps=5,
        error=None,
    )
    script_path: Path | None = None
    if request.clip_mode == "long_animate":
        output_root.mkdir(parents=True, exist_ok=True)
        script_path = output_root / "input_script.txt"
        script_path.write_text(request.script_text.strip() + "\n", encoding="utf-8")
    command = build_clipper_command(request, output_root, script_path)

    try:
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
    except Exception as exc:
        set_job(
            job_id,
            status="failed",
            **finish_job_updates(started_perf),
            error=f"Worker clipping gagal dimulai: {exc}",
        )
        job_secrets.pop(job_id, None)
        clip_job_slots.release()
        return
    with process_lock:
        job_processes[job_id] = process

    logs: list[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            cleaned = line.rstrip()
            if cleaned:
                progress_update = parse_clipper_progress(cleaned)
                if progress_update is not None:
                    set_job(job_id, **progress_update)
                    continue
                logs.append(cleaned)
                set_job(job_id, logs=logs[-120:])

        code = process.wait()
        if job_id in cancelled_job_ids:
            preserve_files = job_id in preserve_job_files_on_cancel
            removed = 0 if preserve_files else cleanup_job_artifacts(output_root)
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

        clips = discover_clips(started_at, output_root)
        candidates = discover_candidates(started_at, output_root)
        if clips and candidates:
            clips = enrich_clips_with_candidate_titles(clips, candidates)
        if code == 0:
            updates = {
                "status": "completed",
                "logs": logs[-120:],
                "progress_percent": 100,
                "progress_stage": "complete",
                "progress_detail": "Semua hasil siap direview dan diunduh",
                "progress_step": 5,
                "progress_total_steps": 5,
                **finish_job_updates(started_perf),
            }
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
            if request.clip_mode == "long_animate" and clips:
                updates["source_title"] = clips[0].title or "Long Animate"
            set_job(job_id, **updates)
            if request.clip_mode != "long_animate":
                remember_processed_source(
                    preview_job.source_url or request.url,
                    clip_mode=request.clip_mode,
                    job_id=job_id,
                    source_title=preview_job.source_title,
                    source_uploader=preview_job.source_uploader,
                    clip_count=len(clips),
                    output_names=[clip.name for clip in clips],
                    processing_duration_seconds=elapsed_seconds(started_perf),
                    compilation_target_seconds=(
                        request.compilation_target_seconds
                        if request.clip_mode == "highlight_5m"
                        else None
                    ),
                    auto_upload_youtube=request.auto_upload_youtube,
                    processed_at=str(updates["finished_at"]),
                )
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
        clip_job_slots.release()

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
    license_text = re.sub(r"\s+", " ", str(info.get("license") or "")).strip().casefold()
    return bool(
        "creative commons" in license_text
        or "creativecommon" in license_text
        or re.search(r"\bcc[\s-]?by(?:[\s-]\d(?:\.\d)?)?\b", license_text)
    )


def viral_source_rejection_reason(info: dict[str, Any]) -> str | None:
    """Reject risky/unavailable sources before they enter clipping automation."""
    if not is_creative_commons_info(info):
        return "metadata lisensi Creative Commons tidak terdeteksi"
    availability = str(info.get("availability") or "public").casefold()
    if availability not in {"", "public"}:
        return f"akses sumber bukan publik ({availability})"
    live_status = str(
        info.get("live_status")
        or info.get("liveBroadcastContent")
        or ""
    ).casefold()
    if info.get("is_live") or live_status in {"is_live", "live", "is_upcoming", "upcoming"}:
        return "video live/upcoming tidak dipakai"
    try:
        age_limit = int(info.get("age_limit") or 0)
    except (TypeError, ValueError):
        age_limit = 0
    if age_limit >= 18:
        return "video berusia terbatas tidak dipakai"
    rights_risks = source_rights_risk_reasons(info)
    if rights_risks:
        return rights_risks[0]
    return None


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


def source_max_height(info: dict[str, Any]) -> int:
    heights: list[int] = []
    for value in (info.get("height"), info.get("resolution_height")):
        try:
            heights.append(int(value or 0))
        except (TypeError, ValueError):
            pass
    formats = info.get("formats") if isinstance(info.get("formats"), list) else []
    for item in formats:
        if not isinstance(item, dict):
            continue
        try:
            heights.append(int(item.get("height") or 0))
        except (TypeError, ValueError):
            pass
    return max(heights, default=0)


def viral_search_filter_relaxation_reasons(
    info: dict[str, Any],
    request: AutoViralRequest | ViralVideoSearchRequest,
) -> list[str]:
    """Return every soft-filter mismatch for transparent adaptive results."""
    reasons: list[str] = []
    duration = float(info.get("duration") or 0)
    if request.duration_filter == "under_3" and not (0 < duration < 180):
        reasons.append("durasi bukan kurang dari 3 menit")
    if request.duration_filter == "between_3_20" and not (180 <= duration <= 1200):
        reasons.append("durasi bukan 3–20 menit")
    if request.duration_filter == "over_20" and duration <= 1200:
        reasons.append("durasi bukan lebih dari 20 menit")

    if not is_fresh_viral_upload(info, request.max_age_days):
        reasons.append(f"tanggal unggah di luar {request.max_age_days} hari terakhir")

    if request.definition_filter == "hd":
        definition = str(info.get("definition") or "").strip().casefold()
        height = source_max_height(info)
        if definition == "sd" or (definition != "hd" and height < 720):
            reasons.append("kualitas HD tidak terverifikasi")
    return reasons


def viral_search_filter_rejection_reason(
    info: dict[str, Any],
    request: AutoViralRequest | ViralVideoSearchRequest,
) -> str:
    """Keep the legacy single-reason interface for strict validation callers."""
    reasons = viral_search_filter_relaxation_reasons(info, request)
    return reasons[0] if reasons else ""


def auto_viral_candidate_score(info: dict[str, Any]) -> float:
    views = max(0, int(info.get("view_count") or 0))
    likes = max(0, int(info.get("like_count") or 0))
    duration = float(info.get("duration") or 0)
    age_days = upload_age_days(info)
    effective_age = max(1, age_days if age_days is not None else FRESH_VIRAL_MAX_AGE_DAYS)
    views_per_day = views / effective_age
    engagement_rate = likes / max(views, 1)
    view_score = log10(views + 1) * 22
    velocity_score = log10(views_per_day + 1) * 28
    like_score = log10(likes + 1) * 7
    engagement_score = min(24, engagement_rate * 420)
    recency_score = 36 * exp(-effective_age / 21)
    duration_score = 15 if 180 <= duration <= 1800 else 8 if 60 <= duration <= 3600 else 0
    return round(
        view_score
        + velocity_score
        + like_score
        + engagement_score
        + recency_score
        + duration_score,
        2,
    )


def niche_relevance_score(info: dict[str, Any], niche: IslamicContentNiche) -> float:
    """Score semantic fit using transparent niche terms from the evergreen brief."""
    if niche == "auto":
        return max(
            niche_relevance_score(info, candidate_niche)
            for candidate_niche in ISLAMIC_EVERGREEN_NICHES
        )
    profile = ISLAMIC_EVERGREEN_NICHES[niche]
    title = re.sub(r"\s+", " ", str(info.get("title") or "")).casefold()
    description = re.sub(r"\s+", " ", str(info.get("description") or "")).casefold()
    tags = info.get("tags") if isinstance(info.get("tags"), list) else []
    categories = info.get("categories") if isinstance(info.get("categories"), list) else []
    supporting = " ".join([description, *map(str, tags), *map(str, categories)]).casefold()
    matched: set[str] = set()
    score = 0.0
    for keyword in profile["keywords"]:
        clean = str(keyword).casefold()
        if clean in title:
            matched.add(clean)
            score += 9.0
        elif clean in supporting:
            matched.add(clean)
            score += 3.5
    # A result should contain at least two niche concepts to receive the full
    # bonus; one generic Islamic word cannot displace a genuinely relevant item.
    if len(matched) >= 4:
        score += 18
    elif len(matched) >= 2:
        score += 9
    elif len(matched) == 1:
        score += 1
    return round(min(100.0, score), 2)


def best_matching_niche(info: dict[str, Any]) -> tuple[str, float]:
    """Return the strongest supported niche and its transparent relevance score."""
    scored = [
        (candidate_niche, niche_relevance_score(info, candidate_niche))
        for candidate_niche in ISLAMIC_EVERGREEN_NICHES
    ]
    return max(scored, key=lambda item: item[1])


INDONESIAN_CONTENT_MARKERS = {
    "adalah", "agar", "atau", "bagaimana", "bahwa", "cara", "dalam", "dan",
    "dengan", "hari", "indonesia", "ini", "kajian", "karena", "kisah", "kita",
    "masalah", "menjadi", "menurut", "nasihat", "tidak", "untuk", "viral", "yang",
}


def indonesian_language_score(info: dict[str, Any]) -> float:
    """Estimate whether the source is genuinely Indonesian, preferring metadata."""
    declared_languages = {
        str(info.get(key) or "").strip().casefold().replace("_", "-")
        for key in ("language", "default_language", "default_audio_language")
        if str(info.get(key) or "").strip()
    }
    if any(value == "id" or value.startswith("id-") for value in declared_languages):
        return 100.0
    if declared_languages and all(
        not (value == "id" or value.startswith("id-"))
        for value in declared_languages
    ):
        return 0.0

    title = re.sub(r"[^a-z0-9]+", " ", str(info.get("title") or "").casefold())
    description = re.sub(
        r"[^a-z0-9]+", " ", str(info.get("description") or "").casefold()
    )
    title_tokens = set(title.split())
    description_tokens = set(description.split())
    title_hits = title_tokens & INDONESIAN_CONTENT_MARKERS
    supporting_hits = description_tokens & INDONESIAN_CONTENT_MARKERS
    score = min(75.0, len(title_hits) * 15.0)
    score += min(25.0, len(supporting_hits - title_hits) * 4.0)
    return round(min(100.0, score), 2)


def niche_candidate_rejection_reason(
    info: dict[str, Any],
    niche: IslamicContentNiche,
) -> str:
    """Reject unrelated or non-Indonesian results before momentum can rank them."""
    relevance_score = niche_relevance_score(info, niche)
    minimum_relevance = max(1, min(100, env_int("VIRAL_CC_MIN_NICHE_SCORE", 18)))
    if relevance_score < minimum_relevance:
        return (
            f"kecocokan tema {relevance_score:.0f}/100 di bawah minimum "
            f"{minimum_relevance}/100"
        )
    language_score = indonesian_language_score(info)
    minimum_language = max(1, min(100, env_int("VIRAL_CC_MIN_INDONESIAN_SCORE", 15)))
    if language_score < minimum_language:
        return (
            f"sinyal Bahasa Indonesia {language_score:.0f}/100 di bawah minimum "
            f"{minimum_language}/100"
        )
    return ""


def compact_source_payload(
    info: dict[str, Any],
    niche: IslamicContentNiche = "auto",
) -> dict[str, Any]:
    age_days = upload_age_days(info)
    views = int(info.get("view_count") or 0)
    viral_score = auto_viral_candidate_score(info)
    resolved_niche, relevance_score = (
        best_matching_niche(info)
        if niche == "auto"
        else (niche, niche_relevance_score(info, niche))
    )
    language_score = indonesian_language_score(info)
    ranking_score = viral_score + relevance_score * 1.85 + language_score * 0.25
    profile = ISLAMIC_EVERGREEN_NICHES.get(resolved_niche, {})
    source_height = source_max_height(info)
    definition = str(info.get("definition") or "").strip().casefold()
    if not definition and source_height >= 720:
        definition = "hd"
    return {
        "url": normalize_youtube_video_url(youtube_watch_url(info)) or youtube_watch_url(info),
        "title": str(info.get("title") or "Video tanpa judul")[:180],
        "uploader": str(info.get("uploader") or "")[:120],
        "duration": info.get("duration"),
        "definition": definition,
        "height": source_height or None,
        "views": views,
        "views_per_day": round(views / max(1, age_days or 1)),
        "engagement_rate": round(float(info.get("like_count") or 0) / max(views, 1), 5),
        "age_days": age_days,
        "likes": info.get("like_count"),
        "upload_date": info.get("upload_date"),
        "license": info.get("license"),
        "rights_verified": False,
        "license_metadata_verified": is_creative_commons_info(info),
        "score": round(ranking_score, 2),
        "viral_score": viral_score,
        "niche": resolved_niche,
        "niche_label": profile.get("label", "Auto Niche Terbaik"),
        "niche_score": relevance_score,
        "language_score": language_score,
        "ranking_reason": (
            f"Kecocokan tema {relevance_score:.0f}/100 • Bahasa Indonesia "
            f"{language_score:.0f}/100 • momentum {viral_score:.0f}"
            if niche != "auto"
            else (
                f"Auto memilih {profile.get('label', resolved_niche)} • kecocokan "
                f"{relevance_score:.0f}/100 • Bahasa Indonesia {language_score:.0f}/100 "
                f"• momentum {viral_score:.0f}"
            )
        ),
    }


def sort_viral_source_payloads(
    sources: list[dict[str, Any]],
    sort_order: ViralSortOrder,
) -> None:
    def exact_filter_score(item: dict[str, Any]) -> int:
        return 0 if item.get("filter_match") == "adaptive" else 1

    if sort_order == "newest":
        sources.sort(
            key=lambda item: (
                exact_filter_score(item),
                -(int(item.get("age_days")) if item.get("age_days") is not None else 999999),
                float(item.get("score") or 0),
            ),
            reverse=True,
        )
    elif sort_order == "relevance":
        sources.sort(
            key=lambda item: (
                exact_filter_score(item),
                float(item.get("niche_score") or 0),
                float(item.get("language_score") or 0),
                float(item.get("score") or 0),
            ),
            reverse=True,
        )
    else:
        sources.sort(
            key=lambda item: (
                exact_filter_score(item),
                float(
                    item.get("viral_score")
                    if item.get("viral_score") is not None
                    else item.get("score") or 0
                ),
                float(item.get("score") or 0),
            ),
            reverse=True,
        )


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
    key_fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:10]
    cache_key = hashlib.sha256(
        json.dumps(
            [key_fingerprint, path, sorted(clean_params.items())],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    cache_ttl = max(0, min(3600, env_int("YOUTUBE_DATA_API_CACHE_TTL_SECONDS", 600)))
    if cache_ttl:
        with youtube_data_api_cache_lock:
            cached = youtube_data_api_cache.get(cache_key)
        if cached is not None and time.monotonic() - cached[0] <= cache_ttl:
            return cached[1]
    clean_params["key"] = api_key
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urlencode(clean_params)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        timeout_seconds = max(
            3, min(30, env_int("YOUTUBE_DATA_API_TIMEOUT_SECONDS", 10))
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if cache_ttl and isinstance(payload, dict):
            with youtube_data_api_cache_lock:
                youtube_data_api_cache[cache_key] = (time.monotonic(), payload)
                if len(youtube_data_api_cache) > 160:
                    oldest = min(
                        youtube_data_api_cache,
                        key=lambda item: youtube_data_api_cache[item][0],
                    )
                    youtube_data_api_cache.pop(oldest, None)
        return payload
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
        raise RuntimeError(
            f"YouTube Data API HTTP {exc.code} [key-id {key_fingerprint}]: {detail}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"YouTube Data API request gagal [key-id {key_fingerprint}]: {exc}"
        ) from exc


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
        "description": snippet.get("description") or "",
        "tags": snippet.get("tags") if isinstance(snippet.get("tags"), list) else [],
        "default_language": snippet.get("defaultLanguage") or "",
        "default_audio_language": snippet.get("defaultAudioLanguage") or "",
        "uploader": snippet.get("channelTitle") or "",
        "duration": parse_youtube_iso_duration(str(content.get("duration") or "")),
        "definition": str(content.get("definition") or ""),
        "view_count": int(stats.get("viewCount") or 0),
        "like_count": int(stats.get("likeCount") or 0),
        "upload_date": upload_date if len(upload_date) == 8 else "",
        "license": "Creative Commons" if license_value == "creativeCommon" else license_value,
        "availability": "public",
        "live_status": snippet.get("liveBroadcastContent") or "none",
    }


def youtube_data_api_search_queries(request: AutoViralRequest) -> list[str]:
    """Use one broad OR query in fast mode to spend only one search.list call."""
    max_api_queries = max(1, min(20, env_int("VIRAL_CC_MAX_API_QUERIES", 1)))
    if env_bool("VIRAL_CC_FAST_API_ONLY", True):
        terms: list[str] = []
        for query in request.queries:
            clean = re.sub(r"\s+", " ", query).strip()[:72]
            if clean and clean.casefold() not in {item.casefold() for item in terms}:
                terms.append(clean)
            if len(terms) >= 6:
                break
        combined = "|".join(terms)
        return [combined[:480]] if combined else []
    return request.queries[:max_api_queries]


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
    relaxed_candidates: list[dict[str, Any]] = []
    adaptive_filters = env_bool("VIRAL_CC_ADAPTIVE_FILTERS", True)
    region_code = os.environ.get("VIRAL_CC_REGION_CODE", "ID").strip() or "ID"
    relevance_language = os.environ.get("VIRAL_CC_RELEVANCE_LANGUAGE", "id").strip() or "id"
    topic_id = os.environ.get("VIRAL_CC_TOPIC_ID", "").strip()
    api_error_count = 0
    api_query_count = 0
    last_api_error = ""
    search_deadline = time.monotonic() + max(
        8, min(90, env_int("VIRAL_CC_FAST_SEARCH_BUDGET_SECONDS", 25))
    )
    for query in youtube_data_api_search_queries(request):
        if stop_after is not None and len(candidates) >= stop_after:
            break
        if time.monotonic() >= search_deadline:
            append_auto_viral_log(
                run_id,
                "Batas waktu pencarian cepat tercapai; memakai kandidat API yang sudah lolos.",
            )
            break
        append_auto_viral_log(run_id, f"YouTube Data API search: {query}")
        api_order = {
            "popularity": "viewCount",
            "relevance": "relevance",
            "newest": "date",
        }[request.sort_order]
        search_params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoLicense": "creativeCommon",
            "order": api_order,
            "maxResults": (
                50
                if env_bool("VIRAL_CC_FAST_API_ONLY", True)
                else request.search_limit_per_query
            ),
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
            "safeSearch": "strict",
            "publishedAfter": youtube_published_after(request.max_age_days),
        }
        if request.duration_filter != "any" and not adaptive_filters:
            search_params["videoDuration"] = {
                "under_3": "short",
                "between_3_20": "medium",
                "over_20": "long",
            }[request.duration_filter]
        if request.definition_filter == "hd" and not adaptive_filters:
            search_params["videoDefinition"] = "high"
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
            if views < request.min_views and not adaptive_filters:
                continue
            if not is_fresh_viral_upload(payload, request.max_age_days):
                continue
            filter_reasons = viral_search_filter_relaxation_reasons(payload, request)
            filter_rejection = "; ".join(filter_reasons)
            if filter_rejection and not adaptive_filters:
                append_auto_viral_log(
                    run_id,
                    f"Skip karena filter ({filter_rejection}): {payload.get('title') or '-'}",
                )
                continue
            rejection_reason = viral_source_rejection_reason(payload)
            if rejection_reason:
                append_auto_viral_log(
                    run_id,
                    f"Skip sumber tidak aman ({rejection_reason}): {payload.get('title') or '-'}",
                )
                continue
            niche_rejection = niche_candidate_rejection_reason(payload, request.niche)
            if niche_rejection:
                append_auto_viral_log(
                    run_id,
                    f"Skip kandidat tidak relevan ({niche_rejection}): "
                    f"{payload.get('title') or '-'}",
                )
                continue
            source = compact_source_payload(payload, request.niche)
            source["search_provider"] = "youtube_data_api"
            relaxed_reasons: list[str] = []
            relaxed_reasons.extend(filter_reasons)
            if views < request.min_views:
                relaxed_reasons.append(
                    f"tayangan {views:,} di bawah preferensi {request.min_views:,}"
                )
            if relaxed_reasons:
                source["filter_match"] = "adaptive"
                source["relaxed_filters"] = relaxed_reasons
                source["score"] = round(
                    float(source.get("score") or 0) - 18 * len(relaxed_reasons), 2
                )
                relaxed_candidates.append(source)
            else:
                source["filter_match"] = "exact"
                source["relaxed_filters"] = []
                candidates.append(source)
            if stop_after is not None and len(candidates) >= stop_after:
                break
    if api_query_count == 0 and api_error_count > 0:
        raise RuntimeError(last_api_error or "Semua request YouTube Data API gagal")
    if stop_after is None or len(candidates) < stop_after:
        sort_viral_source_payloads(relaxed_candidates, request.sort_order)
        needed = len(relaxed_candidates) if stop_after is None else stop_after - len(candidates)
        candidates.extend(relaxed_candidates[:needed])
    sort_viral_source_payloads(candidates, request.sort_order)
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
    relaxed_candidates: list[dict[str, Any]] = []
    adaptive_filters = env_bool("VIRAL_CC_ADAPTIVE_FILTERS", True)
    metadata_checks = 0
    max_metadata_per_query = max(
        2,
        min(20, env_int("VIRAL_CC_METADATA_PER_QUERY", 6)),
    )
    default_search_mode = "ytsearchdate" if request.sort_order == "newest" else "ytsearch"
    search_mode = default_search_mode
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
            if views < request.min_views and not adaptive_filters:
                continue
            if not is_fresh_viral_upload(metadata, request.max_age_days):
                append_auto_viral_log(
                    run_id,
                    f"Skip tidak fresh (> {request.max_age_days} hari/tanggal tidak tersedia): "
                    f"{metadata.get('title') or url}",
                )
                continue
            filter_reasons = viral_search_filter_relaxation_reasons(metadata, request)
            filter_rejection = "; ".join(filter_reasons)
            if filter_rejection and not adaptive_filters:
                append_auto_viral_log(
                    run_id,
                    f"Skip karena filter ({filter_rejection}): {metadata.get('title') or url}",
                )
                continue
            rejection_reason = viral_source_rejection_reason(metadata)
            if rejection_reason:
                append_auto_viral_log(
                    run_id,
                    f"Skip sumber tidak aman ({rejection_reason}): {metadata.get('title') or url}",
                )
                continue
            niche_rejection = niche_candidate_rejection_reason(metadata, request.niche)
            if niche_rejection:
                append_auto_viral_log(
                    run_id,
                    f"Skip kandidat tidak relevan ({niche_rejection}): "
                    f"{metadata.get('title') or url}",
                )
                continue
            source = compact_source_payload(metadata, request.niche)
            source["search_provider"] = "yt_dlp_fallback"
            relaxed_reasons: list[str] = []
            relaxed_reasons.extend(filter_reasons)
            if views < request.min_views:
                relaxed_reasons.append(
                    f"tayangan {views:,} di bawah preferensi {request.min_views:,}"
                )
            if relaxed_reasons:
                source["filter_match"] = "adaptive"
                source["relaxed_filters"] = relaxed_reasons
                source["score"] = round(
                    float(source.get("score") or 0) - 18 * len(relaxed_reasons), 2
                )
                relaxed_candidates.append(source)
            else:
                source["filter_match"] = "exact"
                source["relaxed_filters"] = []
                candidates.append(source)
            if stop_after is not None and len(candidates) >= stop_after:
                break

    if stop_after is None or len(candidates) < stop_after:
        sort_viral_source_payloads(relaxed_candidates, request.sort_order)
        needed = len(relaxed_candidates) if stop_after is None else stop_after - len(candidates)
        candidates.extend(relaxed_candidates[:needed])
    sort_viral_source_payloads(candidates, request.sort_order)
    return candidates


def remember_source_usage(
    value: str,
    *,
    clip_mode: str,
    job_id: str,
    source_title: str | None = None,
    source_uploader: str | None = None,
    clip_count: int = 0,
    output_names: list[str] | None = None,
    processing_duration_seconds: float | None = None,
    compilation_target_seconds: float | None = None,
    auto_upload_youtube: bool = False,
    processed_at: str | None = None,
) -> None:
    normalized = normalize_youtube_video_url(value)
    if not normalized or clip_mode not in {"short", "highlight_5m"}:
        return
    with source_usage_history_lock:
        previous = source_usage_history.get(normalized, {})
        modes = {
            str(item)
            for item in previous.get("modes", [])
            if str(item) in {"short", "highlight_5m"}
        }
        modes.add(clip_mode)
        job_ids = [
            str(item)
            for item in previous.get("job_ids", [])
            if isinstance(item, str) and item and item != job_id
        ][-19:]
        job_ids.append(job_id)
        event_processed_at = processed_at or now_iso()
        events = [
            item
            for item in previous.get("events", [])
            if isinstance(item, dict) and str(item.get("job_id") or "") != job_id
        ][-49:]
        events.append(
            {
                "job_id": job_id,
                "source_url": normalized,
                "source_title": source_title or previous.get("source_title"),
                "source_uploader": source_uploader,
                "clip_mode": clip_mode,
                "processed_at": event_processed_at,
                "clip_count": max(0, int(clip_count)),
                "output_names": [str(name) for name in (output_names or []) if str(name).strip()][:30],
                "processing_duration_seconds": processing_duration_seconds,
                "compilation_target_seconds": compilation_target_seconds,
                "auto_upload_youtube": bool(auto_upload_youtube),
            }
        )
        source_usage_history[normalized] = {
            "modes": sorted(modes),
            "job_ids": job_ids,
            "source_title": source_title or previous.get("source_title"),
            "last_processed_at": event_processed_at,
            "events": events,
        }
        payload = dict(sorted(source_usage_history.items())[-5000:])
        source_usage_history.clear()
        source_usage_history.update(payload)
        try:
            temp_path = SOURCE_USAGE_HISTORY_PATH.with_suffix(".json.tmp")
            temp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_path.replace(SOURCE_USAGE_HISTORY_PATH)
        except OSError as exc:
            print(f"Gagal menyimpan detail riwayat sumber clipping: {exc}", flush=True)


def remember_processed_source(
    value: str,
    *,
    clip_mode: str = "",
    job_id: str = "",
    source_title: str | None = None,
    source_uploader: str | None = None,
    clip_count: int = 0,
    output_names: list[str] | None = None,
    processing_duration_seconds: float | None = None,
    compilation_target_seconds: float | None = None,
    auto_upload_youtube: bool = False,
    processed_at: str | None = None,
) -> None:
    normalized = normalize_youtube_video_url(value)
    if not normalized:
        return
    with processed_source_history_lock:
        if normalized not in processed_source_history:
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
    if clip_mode and job_id:
        remember_source_usage(
            normalized,
            clip_mode=clip_mode,
            job_id=job_id,
            source_title=source_title,
            source_uploader=source_uploader,
            clip_count=clip_count,
            output_names=output_names,
            processing_duration_seconds=processing_duration_seconds,
            compilation_target_seconds=compilation_target_seconds,
            auto_upload_youtube=auto_upload_youtube,
            processed_at=processed_at,
        )


def backfill_source_usage_from_completed_jobs() -> None:
    with source_usage_history_lock:
        recorded_job_ids = {
            str(event.get("job_id") or "")
            for record in source_usage_history.values()
            for event in record.get("events", [])
            if isinstance(event, dict)
        }
    with jobs_lock:
        completed_jobs = [job for job in jobs.values() if job.status == "completed"]

    for raw_job in completed_jobs:
        if raw_job.id in recorded_job_ids:
            continue
        job = enrich_job_for_display(raw_job)
        source_url = job.source_url or job.request.url
        if not normalize_youtube_video_url(source_url):
            continue
        remember_source_usage(
            source_url,
            clip_mode=job.request.clip_mode,
            job_id=job.id,
            source_title=job.source_title,
            source_uploader=job.source_uploader,
            clip_count=len(job.clips),
            output_names=[clip.name for clip in job.clips],
            processing_duration_seconds=job.duration_seconds,
            compilation_target_seconds=(
                job.request.compilation_target_seconds
                if job.request.clip_mode == "highlight_5m"
                else None
            ),
            auto_upload_youtube=job.request.auto_upload_youtube,
            processed_at=job.finished_at or job.updated_at,
        )


def list_source_usage_log() -> SourceUsageLogResponse:
    backfill_source_usage_from_completed_jobs()
    with source_usage_history_lock:
        snapshot = {
            source_url: dict(record)
            for source_url, record in source_usage_history.items()
        }

    entries: list[SourceUsageLogEntry] = []
    for source_url, record in snapshot.items():
        raw_events = record.get("events", [])
        if isinstance(raw_events, list) and raw_events:
            for event in raw_events:
                if not isinstance(event, dict):
                    continue
                try:
                    entries.append(SourceUsageLogEntry(**event))
                except (TypeError, ValueError):
                    continue
            continue

        # Backward-compatible entry for records written before per-run audit events existed.
        modes = [
            str(item)
            for item in record.get("modes", [])
            if str(item) in {"short", "highlight_5m"}
        ]
        processed_at = str(record.get("last_processed_at") or "")
        job_ids = [str(item) for item in record.get("job_ids", []) if str(item)]
        if not processed_at:
            continue
        for index, mode in enumerate(modes):
            entries.append(
                SourceUsageLogEntry(
                    job_id=job_ids[-1] if job_ids else f"legacy-{index}-{source_url.rsplit('=', 1)[-1]}",
                    source_url=source_url,
                    source_title=str(record.get("source_title") or "").strip() or None,
                    clip_mode=mode,
                    processed_at=processed_at,
                )
            )

    entries.sort(key=lambda item: item.processed_at, reverse=True)
    return SourceUsageLogResponse(
        items=entries,
        total=len(entries),
        unique_sources=len({item.source_url for item in entries}),
    )


def source_history_for_url(value: str) -> SourceHistoryCheck:
    normalized = normalize_youtube_video_url(value)
    if not normalized:
        return SourceHistoryCheck(input_url=value)

    with processed_source_history_lock:
        archived_urls = {
            candidate
            for item in processed_source_history
            if (candidate := normalize_youtube_video_url(item))
        }
    with source_usage_history_lock:
        archived_record = dict(source_usage_history.get(normalized, {}))
    with jobs_lock:
        job_snapshot = list(jobs.values())

    matching_jobs: list[ClipJob] = []
    for job in job_snapshot:
        source_urls = {
            candidate
            for item in (job.request.url, job.source_url)
            if (candidate := normalize_youtube_video_url(str(item or "")))
        }
        if normalized in source_urls:
            matching_jobs.append(enrich_job_for_display(job))

    matching_jobs.sort(key=lambda item: item.created_at, reverse=True)
    matches = [
        SourceHistoryJob(
            job_id=job.id,
            status=job.status,
            created_at=job.created_at,
            source_title=job.source_title,
            clip_mode=job.request.clip_mode,
            clip_count=len(job.clips),
        )
        for job in matching_jobs[:12]
    ]
    archived_modes = {
        str(item)
        for item in archived_record.get("modes", [])
        if str(item) in {"short", "highlight_5m"}
    }
    attempted_modes = archived_modes | {job.request.clip_mode for job in matching_jobs}

    def job_has_mode(job: ClipJob, mode: str) -> bool:
        long_form_outputs = any(
            clip.name.casefold().startswith(("highlight_5menit_", "resume_cerita_"))
            for clip in job.clips
        )
        if mode == "highlight_5m":
            return long_form_outputs or (job.status == "completed" and job.request.clip_mode == mode)
        return (bool(job.clips) and not long_form_outputs) or (
            job.status == "completed" and job.request.clip_mode == mode
        )

    archived = normalized in archived_urls or bool(archived_record)
    return SourceHistoryCheck(
        input_url=value,
        normalized_url=normalized,
        valid_youtube_url=True,
        found=archived or bool(matches),
        archived=archived,
        has_short_clips="short" in archived_modes
        or any(job_has_mode(job, "short") for job in matching_jobs),
        has_highlight_5m="highlight_5m" in archived_modes
        or any(job_has_mode(job, "highlight_5m") for job in matching_jobs),
        attempted_modes=sorted(attempted_modes),
        matches=matches,
    )


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
    search_started = time.perf_counter()
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
        min_duration=15,
        max_duration=60,
        video_quality="high",
        crop_mode="person",
        burn_subtitles=True,
        ai_enabled=True,
        niche=request.niche,
        duration_filter=request.duration_filter,
        upload_date_filter=request.upload_date_filter,
        definition_filter=request.definition_filter,
        sort_order=request.sort_order,
    )
    run = AutoViralRun(
        id=run_id,
        status="running",
        created_at=now_iso(),
        updated_at=now_iso(),
        request=search_request,
        message="Mencari kandidat CC sesuai filter durasi, tanggal, kualitas, dan prioritas",
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
        fast_api_only = env_bool("VIRAL_CC_FAST_API_ONLY", True)
        source_pool_target = (
            request.video_count
            if fast_api_only
            else max(request.video_count * 2, request.video_count)
        )
        prefer_youtube_api = env_bool("VIRAL_CC_REQUIRE_YOUTUBE_DATA_API", True)
        api_key_configured = bool(os.environ.get("YOUTUBE_DATA_API_KEY", "").strip())
        api_attempted = False
        quota_fallback = False
        if prefer_youtube_api and api_key_configured:
            api_attempted = True
            try:
                sources = search_youtube_data_api_viral_sources(
                    search_request,
                    run_id,
                    exclude_urls=excluded_urls,
                    stop_after=source_pool_target,
                )
            except Exception as exc:
                append_auto_viral_error(
                    run_id,
                    f"YouTube Data API gagal: {exc}",
                )
                quota_error = any(
                    marker in str(exc).casefold()
                    for marker in ("quotaexceeded", "dailylimitexceeded", "rate_limit")
                )
                quota_fallback = quota_error and env_bool(
                    "VIRAL_CC_QUOTA_FALLBACK_ENABLED", True
                )
                if quota_fallback:
                    append_auto_viral_log(
                        run_id,
                        "Quota Google habis; menjalankan fallback web terbatas dengan verifikasi CC tetap wajib.",
                    )
                elif fast_api_only:
                    raise RuntimeError(
                        "Google YouTube Data API tidak dapat dipakai. Periksa pembatasan key, "
                        f"quota, dan aktivasi YouTube Data API v3: {exc}"
                    ) from exc
        elif prefer_youtube_api:
            if fast_api_only:
                raise RuntimeError(
                    "YOUTUBE_DATA_API_KEY belum terpasang; pencarian cepat tidak menjalankan fallback lambat."
                )
            append_auto_viral_log(run_id, "YouTube Data API key kosong; memakai fallback yt-dlp.")
        else:
            append_auto_viral_log(run_id, "YouTube Data API dinonaktifkan; memakai pencarian yt-dlp terverifikasi.")

        if len(sources) < source_pool_target and not (
            fast_api_only and api_attempted and not quota_fallback
        ):
            fallback_age_days = request.max_age_days
            fallback_min_views = min(
                request.min_views,
                max(0, env_int("VIRAL_CC_FALLBACK_MIN_VIEWS", 100)),
            )
            fallback_queries = prioritized_niche_queries(
                request.niche,
                default_viral_video_search_queries(),
            )
            if quota_fallback:
                fallback_queries = fallback_queries[:2]
            fallback_request = search_request.model_copy(
                update={
                    "queries": fallback_queries,
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
                f"Hasil sesuai filter baru {len(sources)}/{request.video_count}; memperluas kata kunci "
                f"tanpa mengubah batas {fallback_age_days} hari, min. {fallback_min_views} views, "
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
                stop_after=source_pool_target - len(sources),
                max_metadata_checks=(
                    min(
                        request.max_metadata_checks,
                        max(3, env_int("VIRAL_CC_QUOTA_FALLBACK_METADATA_CHECKS", 8)),
                    )
                    if quota_fallback
                    else min(
                        request.max_metadata_checks,
                        max(3, env_int("VIRAL_CC_FAST_MAX_METADATA_CHECKS", 24)),
                    )
                ),
            )
            sources = [*sources, *fallback_sources]
        sort_viral_source_payloads(sources, request.sort_order)
        selected = sources[: request.video_count]
        elapsed_ms = max(0, round((time.perf_counter() - search_started) * 1000))
        for rank, source in enumerate(selected, start=1):
            source["rank"] = rank
            source["search_elapsed_ms"] = elapsed_ms
        update_auto_viral_run(
            run_id,
            status="completed",
            finished_at=now_iso(),
            selected_sources=selected,
            message=(
                f"Top {len(selected)} kandidat "
                f"{ISLAMIC_EVERGREEN_NICHES.get(request.niche, {}).get('label', 'Creative Commons')} "
                "siap dipilih"
                if selected
                else "Belum ditemukan konten CC terbaru yang relevan dan berbahasa Indonesia; tidak ada kandidat asing yang dipaksakan."
            ),
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


def resolve_selected_auto_viral_sources(
    request: AutoViralRequest,
    run_id: str,
) -> list[dict[str, Any]]:
    """Revalidate user-selected Top 3 sources before they enter the clipping queue."""
    sources: list[dict[str, Any]] = []
    for rank, url in enumerate(request.source_urls, start=1):
        append_auto_viral_log(run_id, f"Validasi pilihan #{rank}: {url}")
        metadata = fetch_youtube_metadata(url)
        rejection_reason = viral_source_rejection_reason(metadata)
        if rejection_reason:
            raise RuntimeError(f"Pilihan #{rank} tidak aman: {rejection_reason}")
        duration = float(metadata.get("duration") or 0)
        if duration < request.min_source_duration or duration > request.max_source_duration:
            raise RuntimeError(
                f"Pilihan #{rank} berdurasi {duration:.0f} detik, di luar batas sumber "
                f"{request.min_source_duration}-{request.max_source_duration} detik"
            )
        if not is_fresh_viral_upload(metadata, request.max_age_days):
            raise RuntimeError(
                f"Pilihan #{rank} tidak lagi masuk jendela freshness {request.max_age_days} hari"
            )
        filter_rejection = viral_search_filter_rejection_reason(metadata, request)
        if filter_rejection and not env_bool("VIRAL_CC_ADAPTIVE_FILTERS", True):
            raise RuntimeError(f"Pilihan #{rank} tidak lolos filter: {filter_rejection}")
        if filter_rejection:
            append_auto_viral_log(
                run_id,
                f"Pilihan #{rank} memakai perluasan filter ({filter_rejection}); metadata CC dan guard risiko hak tetap lolos.",
            )
        niche_rejection = niche_candidate_rejection_reason(metadata, request.niche)
        if niche_rejection:
            raise RuntimeError(f"Pilihan #{rank} tidak lolos tema: {niche_rejection}")
        source = compact_source_payload(metadata, request.niche)
        source["rank"] = rank
        sources.append(source)
    return sources


def create_auto_viral_clip_job(source: dict[str, Any], request: AutoViralRequest) -> ClipJob:
    wait_for_no_active_clipping_job()
    job_request = ClipJobRequest(
        url=str(source["url"]),
        top=request.top,
        min_duration=request.min_duration,
        max_duration=request.max_duration,
        video_quality=request.video_quality,
        visual_mode=request.visual_mode,
        background_mode=request.background_mode,
        burn_subtitles=request.burn_subtitles,
        crop_mode=request.crop_mode,
        require_creative_commons=True,
        auto_upload_youtube=False,
        ai_enabled=request.ai_enabled,
        ai_base_url=request.ai_base_url,
        ai_model=request.ai_model,
        ai_api_key=request.ai_api_key,
        required_hashtags=list(
            dict.fromkeys(
                DEFAULT_REQUIRED_HASHTAGS
                + list(ISLAMIC_EVERGREEN_NICHES.get(request.niche, {}).get("hashtags", []))
            )
        ),
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
            message=(
                "Memvalidasi pilihan dan menyiapkan antrean clipping"
                if run.request.source_urls
                else "Mencari video Creative Commons sesuai filter pencarian"
            ),
        )
        append_auto_viral_log(run_id, "Automation dimulai")
        if run.request.auto_upload_youtube:
            try:
                require_youtube_ready()
            except HTTPException as exc:
                raise RuntimeError(str(exc.detail)) from exc

        source_pool_target = max(run.request.video_count * 3, run.request.video_count)
        excluded_sources = processed_job_source_urls()
        if run.request.source_urls:
            selected_duplicates = excluded_sources.intersection(run.request.source_urls)
            if selected_duplicates:
                raise RuntimeError(
                    "Pilihan sudah pernah diproses: " + ", ".join(sorted(selected_duplicates))
                )
            sources = resolve_selected_auto_viral_sources(run.request, run_id)
            update_auto_viral_run(run_id, selected_sources=sources)
            append_auto_viral_log(run_id, f"{len(sources)} pilihan lolos dan masuk antrean clipping")
        else:
            append_auto_viral_log(
                run_id,
                f"Mengecualikan {len(excluded_sources)} sumber yang sudah pernah masuk proses clipping",
            )
            sources = search_auto_viral_sources(
                run.request,
                run_id,
                exclude_urls=excluded_sources,
                stop_after=source_pool_target,
                max_metadata_checks=env_int("VIRAL_CC_MAX_METADATA_CHECKS", 24),
            )
        if not run.request.source_urls and len(sources) < source_pool_target:
            fallback_age_days = run.request.max_age_days
            fallback_min_views = min(
                run.request.min_views,
                max(0, env_int("VIRAL_CC_FALLBACK_MIN_VIEWS", 100)),
            )
            fallback_request = run.request.model_copy(
                update={
                    "queries": prioritized_niche_queries(
                        run.request.niche,
                        default_auto_viral_queries(),
                    ),
                    "search_limit_per_query": max(run.request.search_limit_per_query, 25),
                    "min_views": fallback_min_views,
                    "max_age_days": fallback_age_days,
                }
            )
            append_auto_viral_log(
                run_id,
                f"Kandidat baru belum cukup; memperluas kata kunci tanpa mengubah filter "
                f"{fallback_age_days} hari, minimal {fallback_min_views} views",
            )
            update_auto_viral_run(
                run_id,
                message="Memperluas variasi kata kunci Creative Commons dengan filter tetap",
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
                    max_metadata_checks=env_int("VIRAL_CC_MAX_METADATA_CHECKS", 24),
                )
            )
            sort_viral_source_payloads(sources, run.request.sort_order)
        if not sources:
            raise RuntimeError(
                "Tidak menemukan kandidat Creative Commons setelah pencarian diperluas; "
                "semua sumber yang pernah diproses tetap dilewati"
            )
        if not run.request.source_urls:
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

                item["uploads"] = []
                if run.request.auto_upload_youtube:
                    with youtube_upload_creation_lock:
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
                else:
                    item["cleanup"] = "hasil clip disimpan untuk review"
                    append_auto_viral_log(
                        run_id,
                        f"Job {finished_job.id[:10]} selesai; {len(finished_job.clips)} clip siap direview",
                    )
                item["status"] = "completed"
                completed_count += 1
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = str(exc)
                append_auto_viral_error(run_id, f"{source.get('title')}: {exc}")
            processed.append(item)
            update_auto_viral_run(run_id, processed=processed, message=f"{completed_count}/{run.request.video_count} video sukses")

        if completed_count < run.request.video_count:
            suffix = "clip dan upload" if run.request.auto_upload_youtube else "masuk antrean clipping"
            raise RuntimeError(f"Hanya {completed_count}/{run.request.video_count} video yang berhasil {suffix}")

        with auto_viral_lock:
            run = auto_viral_runs[run_id]
        update_auto_viral_run(
            run_id,
            status="completed",
            finished_at=now_iso(),
            message=(
                "Clipping Top 3 selesai dan siap direview"
                if not run.request.auto_upload_youtube
                else "Automation selesai"
            ),
        )
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
    if request.min_duration >= 60:
        raise HTTPException(
            status_code=400,
            detail="Durasi minimum clip pendek harus di bawah 60 detik",
        )
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
        uploads = list(youtube_uploads.values())
    positioned = youtube_uploads_with_queue_positions(uploads)
    return sorted(positioned, key=lambda item: item.created_at, reverse=True)


@app.get("/api/youtube/uploads/{upload_id}", response_model=YouTubeUploadJob)
def get_youtube_upload(upload_id: str) -> YouTubeUploadJob:
    with youtube_uploads_lock:
        upload = youtube_uploads.get(upload_id)
        uploads = list(youtube_uploads.values())
    if not upload:
        raise HTTPException(status_code=404, detail="YouTube upload not found")
    return next(
        item
        for item in youtube_uploads_with_queue_positions(uploads)
        if item.id == upload_id
    )


@app.post(
    "/api/youtube/uploads/{upload_id}/performance/refresh",
    response_model=YouTubeUploadJob,
)
def refresh_youtube_upload_performance(upload_id: str) -> YouTubeUploadJob:
    return refresh_youtube_performance(upload_id)


@app.post(
    "/api/youtube/uploads/{upload_id}/performance",
    response_model=YouTubeUploadJob,
)
def update_youtube_upload_performance(
    upload_id: str,
    request: YouTubePerformanceUpdateRequest,
) -> YouTubeUploadJob:
    return record_youtube_performance(
        upload_id,
        YouTubePerformanceSnapshot(
            captured_at=now_iso(),
            source="manual",
            **request.model_dump(),
        ),
    )


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
    with youtube_upload_creation_lock:
        upload = create_youtube_upload_record(job_id, request)
        queue_youtube_upload_jobs([upload])
    return get_youtube_upload(upload.id)


@app.post("/api/jobs/{job_id}/youtube-uploads/batch", response_model=list[YouTubeUploadJob])
def create_youtube_upload_batch(job_id: str, request: YouTubeBatchUploadRequest) -> list[YouTubeUploadJob]:
    require_youtube_ready()
    with youtube_upload_creation_lock:
        uploads = create_youtube_upload_batch_records(job_id, request)
        queue_youtube_upload_jobs(uploads)
    positioned = {upload.id: upload for upload in list_youtube_uploads()}
    return [positioned[upload.id] for upload in uploads if upload.id in positioned]


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


@app.get("/api/source-history", response_model=SourceHistoryCheck)
def check_source_history(url: str) -> SourceHistoryCheck:
    return source_history_for_url(url)


@app.get("/api/source-usage-log", response_model=SourceUsageLogResponse)
def get_source_usage_log() -> SourceUsageLogResponse:
    return list_source_usage_log()


@app.post("/api/jobs", response_model=ClipJob)
def create_job(request: ClipJobRequest) -> ClipJob:
    if request.clip_mode != "long_animate" and request.max_duration <= request.min_duration:
        raise HTTPException(status_code=400, detail="max_duration must be greater than min_duration")
    if request.clip_mode == "short" and request.min_duration >= 60:
        raise HTTPException(
            status_code=400,
            detail="Durasi minimum clip pendek harus di bawah 60 detik",
        )

    if request.clip_mode == "long_animate":
        clean_script = request.script_text.strip()
        if len(clean_script) < 120 or len(clean_script.split()) < 30:
            raise HTTPException(
                status_code=400,
                detail="Naskah Long Animate minimal 120 karakter dan 30 kata.",
            )
        if not request.confirm_long_animate_rights:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Konfirmasi bahwa naskah milik Anda dan provider gambar/suara yang dikonfigurasi "
                    "mengizinkan penggunaan komersial YouTube."
                ),
            )
        request = request.model_copy(
            update={
                "url": "",
                "source_file": "",
                "script_text": clean_script,
                "require_creative_commons": False,
            }
        )
    elif not request.url and not request.source_file:
        raise HTTPException(status_code=400, detail="Provide a YouTube URL or upload a video first")

    if request.url.strip() and request.auto_upload_youtube and not request.confirm_source_rights:
        raise HTTPException(
            status_code=400,
            detail=(
                "Auto Upload diblokir: konfirmasikan kepemilikan atau izin komersial yang dapat "
                "dibuktikan untuk seluruh audio dan visual sumber. Metadata CC saja tidak cukup."
            ),
        )

    if request.clip_mode == "long_animate":
        pass
    elif request.source_file:
        upload_path = resolve_upload_path(request.source_file)
        if upload_path is None:
            raise HTTPException(status_code=400, detail="Uploaded video not found; upload it again")
        request = request.model_copy(update={"source_file": str(upload_path)})
    elif request.url:
        source_history = source_history_for_url(request.url)
        if source_history.found and not request.allow_reprocess_source:
            detected_formats: list[str] = []
            if source_history.has_short_clips or "short" in source_history.attempted_modes:
                detected_formats.append("clip pendek")
            if source_history.has_highlight_5m or "highlight_5m" in source_history.attempted_modes:
                detected_formats.append("Highlight/Resume 5–10 menit")
            format_copy = ", ".join(detected_formats) or "arsip proses lama"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Sumber YouTube ini sudah pernah diproses ({format_copy}). "
                    "Periksa peringatan riwayat dan centang persetujuan jika memang ingin memproses ulang."
                ),
            )
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
        jobs[job_id] = job
        save_jobs_unlocked()

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return job





@app.get("/api/jobs", response_model=list[ClipJob])
def list_jobs() -> list[ClipJob]:
    with jobs_lock:
        snapshot = list(jobs.values())
    return sorted(
        (enrich_job_for_display(job) for job in snapshot),
        key=lambda job: job.created_at,
        reverse=True,
    )


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
    return enrich_job_for_display(job)


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
