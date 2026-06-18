from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
import uuid
from math import ceil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
JOBS_PATH = BASE_DIR / "jobs.json"
SECONDS_PER_TARGET_CLIP = 360
MIN_AUTO_CLIPS = 2
MAX_AUTO_CLIPS = 8
FULL_ANALYSIS_LIMIT_SECONDS = 30 * 60
LONG_VIDEO_ANALYSIS_RATIO = 0.55
MAX_AUTO_ANALYSIS_SECONDS = 60 * 60


class ClipJobRequest(BaseModel):
    url: str = Field(min_length=8)
    top: int | None = Field(default=None, ge=1, le=12)
    min_duration: float = Field(default=35, ge=5, le=600)
    max_duration: float = Field(default=180, ge=10, le=600)
    model: str = "Systran/faster-whisper-small"
    language: str = "id"
    analyze_seconds: float | None = Field(default=None, ge=10, le=7200)
    burn_subtitles: bool = True
    crop_mode: Literal["center", "person"] = "center"


class ClipCandidate(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    score: int
    title: str
    reason: str
    text: str


class ClipFile(BaseModel):
    name: str
    url: str
    size_bytes: int


class ClipJob(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    request: ClipJobRequest
    created_at: str
    updated_at: str
    logs: list[str] = []
    clips: list[ClipFile] = []
    candidates: list[ClipCandidate] = []
    error: str | None = None


app = FastAPI(title="ClipForge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jobs() -> dict[str, ClipJob]:
    if not JOBS_PATH.exists():
        return {}

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    loaded: dict[str, ClipJob] = {}
    for item in payload:
        job = ClipJob(**item)
        if job.status in {"queued", "running"}:
            data = job.model_dump()
            data["status"] = "failed"
            data["updated_at"] = now_iso()
            data["error"] = "Backend restarted before this job finished"
            job = ClipJob(**data)
        loaded[job.id] = job
    return loaded


def save_jobs_unlocked() -> None:
    jobs_list = sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)
    payload = [job.model_dump() for job in jobs_list]
    temp_path = JOBS_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(JOBS_PATH)


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


jobs: dict[str, ClipJob] = load_jobs()
jobs_lock = threading.Lock()


def clip_url(path: Path) -> str:
    relative = path.resolve().relative_to(OUTPUTS_DIR.resolve()).as_posix()
    return "/outputs/" + quote(relative)


def discover_clips(started_at: float) -> list[ClipFile]:
    clips: list[ClipFile] = []
    for path in OUTPUTS_DIR.rglob("clips/*.mp4"):
        if path.stat().st_mtime + 1 < started_at:
            continue
        clips.append(
            ClipFile(
                name=path.name,
                url=clip_url(path),
                size_bytes=path.stat().st_size,
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
        job = jobs[job_id]
        data = job.model_dump()
        data.update(updates)
        data["updated_at"] = now_iso()
        jobs[job_id] = ClipJob(**data)
        save_jobs_unlocked()


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def fetch_video_duration(url: str) -> float | None:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    duration = info.get("duration") if isinstance(info, dict) else None
    return float(duration) if duration else None


def choose_auto_top(duration: float | None) -> int:
    if not duration:
        return MIN_AUTO_CLIPS + 3
    return clamp(ceil(duration / SECONDS_PER_TARGET_CLIP), MIN_AUTO_CLIPS, MAX_AUTO_CLIPS)


def choose_auto_analyze_seconds(duration: float | None) -> float | None:
    if not duration or duration <= FULL_ANALYSIS_LIMIT_SECONDS:
        return None
    return min(MAX_AUTO_ANALYSIS_SECONDS, max(FULL_ANALYSIS_LIMIT_SECONDS, duration * LONG_VIDEO_ANALYSIS_RATIO))


def normalize_job_request(request: ClipJobRequest) -> ClipJobRequest:
    duration = fetch_video_duration(request.url)
    data = request.model_dump()

    if request.top is None:
        data["top"] = choose_auto_top(duration)
    if request.analyze_seconds is None:
        data["analyze_seconds"] = choose_auto_analyze_seconds(duration)

    return ClipJobRequest(**data)


def build_clipper_command(request: ClipJobRequest) -> list[str]:
    command = [
        sys.executable,
        "clipper.py",
        request.url,
        "--top",
        str(request.top or choose_auto_top(None)),
        "--min",
        str(request.min_duration),
        "--max",
        str(request.max_duration),
        "--model",
        request.model,
        "--language",
        request.language,
    ]

    if request.analyze_seconds:
        command.extend(["--analyze-seconds", str(request.analyze_seconds)])
    if not request.burn_subtitles:
        command.append("--no-burn-subtitles")
    command.extend(["--crop-mode", request.crop_mode])
    return command


def run_job(job_id: str) -> None:
    with jobs_lock:
        request = jobs[job_id].request

    started_at = time.time()
    set_job(job_id, status="running", error=None)
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

    logs: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        cleaned = line.rstrip()
        if cleaned:
            logs.append(cleaned)
            set_job(job_id, logs=logs[-120:])

    code = process.wait()
    clips = discover_clips(started_at)
    candidates = discover_candidates(started_at)
    if code == 0:
        updates = {"status": "completed", "logs": logs[-120:]}
        if clips:
            updates["clips"] = clips
        if candidates:
            updates["candidates"] = candidates
        set_job(job_id, **updates)
    else:
        set_job(
            job_id,
            status="failed",
            clips=clips,
            candidates=candidates,
            logs=logs[-120:],
            error=f"clipper.py exited with code {code}",
        )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs", response_model=ClipJob)
def create_job(request: ClipJobRequest) -> ClipJob:
    if request.max_duration <= request.min_duration:
        raise HTTPException(status_code=400, detail="max_duration must be greater than min_duration")

    request = normalize_job_request(request)
    job_id = uuid.uuid4().hex
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
        return sorted(jobs.values(), key=lambda job: job.created_at, reverse=True)


@app.delete("/api/jobs")
def delete_all_jobs() -> dict[str, str | int]:
    with jobs_lock:
        jobs.clear()
        save_jobs_unlocked()
        removed_outputs = clear_outputs_dir()
    return {"status": "ok", "removed_outputs": removed_outputs}


@app.get("/api/jobs/{job_id}", response_model=ClipJob)
def get_job(job_id: str) -> ClipJob:
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
