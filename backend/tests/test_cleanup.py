import tempfile
import time
from pathlib import Path

import pytest

from api import (
    ClipCandidate,
    ClipFile,
    ClipJob,
    ClipJobRequest,
    cleanup_clip_files,
    cleanup_job_files,
    cleanup_orphan_output_roots,
    run_job,
)
from clipper import (
    UserFacingError,
    cleanup_intermediate,
    extract_audio,
    friendly_youtube_error,
    prepare_uploaded_source,
    select_usable_source_media,
    source_media_candidates,
    youtube_download_strategies,
)


def test_cleanup_removes_source_and_audio_keeps_clips():
    work = Path(tempfile.mkdtemp())
    (work / "source.mp4").write_bytes(b"x" * 100)
    (work / "audio_1800s.wav").write_bytes(b"y" * 100)
    (work / "transcript.json").write_text("[]")
    (work / "clips").mkdir()
    (work / "clips" / "clip_01.mp4").write_bytes(b"z" * 10)

    cleanup_intermediate(work, work / "source.mp4")

    names = {p.name for p in work.iterdir()}
    assert "source.mp4" not in names
    assert "audio_1800s.wav" not in names
    assert "transcript.json" in names
    assert "clips" in names
    assert (work / "clips" / "clip_01.mp4").exists()


def test_prepare_uploaded_source_does_not_copy():
    upload = Path(tempfile.mkdtemp()) / "video.mp4"
    upload.write_bytes(b"u" * 100)
    work = Path(tempfile.mkdtemp())

    returned, meta = prepare_uploaded_source(upload, work)

    # The upload is read in place, not duplicated into the work dir.
    assert returned == upload
    assert list(work.iterdir()) == []
    assert meta["ext"] == "mp4"


def test_cleanup_does_not_delete_external_upload():
    upload = Path(tempfile.mkdtemp()) / "video.mp4"
    upload.write_bytes(b"u" * 100)
    work = Path(tempfile.mkdtemp())

    # An uploaded source lives outside the work dir and must survive cleanup.
    cleanup_intermediate(work, upload)

    assert upload.exists()


class FinishedClipperProcess:
    def __init__(self, code: int, lines: list[str] | None = None):
        self.code = code
        self.stdout = iter(lines or [])

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code


@pytest.mark.parametrize("exit_code", [0, 7])
def test_failed_or_empty_job_removes_entire_partial_workspace(monkeypatch, tmp_path, exit_code):
    import api

    outputs = tmp_path / "outputs"
    job = ClipJob(
        id=f"failed-{exit_code}",
        status="queued",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    workspace = outputs / job.id
    workspace.mkdir(parents=True)
    (workspace / "source.mp4.part").write_bytes(b"partial")
    (workspace / "audio.wav").write_bytes(b"partial audio")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "job_secrets", {})
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "cancelled_job_ids", set())
    monkeypatch.setattr(api, "preserve_job_files_on_cancel", set())
    monkeypatch.setattr(api, "build_clipper_command", lambda *_args, **_kwargs: ["clipper"])
    monkeypatch.setattr(
        api.subprocess,
        "Popen",
        lambda *_args, **_kwargs: FinishedClipperProcess(
            exit_code,
            ["USER_ERROR: rate/quality kandidat kurang tinggi"] if exit_code else [],
        ),
    )

    run_job(job.id)

    failed = api.jobs[job.id]
    assert failed.status == "failed"
    assert failed.clips == []
    assert failed.candidates == []
    assert not workspace.exists()
    assert "telah dihapus" in failed.logs[-1]


def test_rendered_file_without_surviving_candidate_audit_is_deleted(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    job = ClipJob(
        id="missing-candidate-audit",
        status="queued",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    workspace = outputs / job.id
    clip_path = workspace / "clips" / "clip_01.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"rendered-but-unaudited")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "job_secrets", {})
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "cancelled_job_ids", set())
    monkeypatch.setattr(api, "preserve_job_files_on_cancel", set())
    monkeypatch.setattr(api, "build_clipper_command", lambda *_args, **_kwargs: ["clipper"])
    monkeypatch.setattr(api.subprocess, "Popen", lambda *_args, **_kwargs: FinishedClipperProcess(0))
    monkeypatch.setattr(
        api,
        "discover_clips",
        lambda *_args, **_kwargs: [
            ClipFile(name="clip_01.mp4", url="/outputs/demo/clips/clip_01.mp4", size_bytes=24)
        ],
    )
    monkeypatch.setattr(api, "discover_candidates", lambda *_args, **_kwargs: [])
    telegram_calls = []
    monkeypatch.setattr(api, "send_clip_success_telegram_alert", telegram_calls.append)

    run_job(job.id)

    failed = api.jobs[job.id]
    assert failed.status == "failed"
    assert not workspace.exists()
    assert telegram_calls == []


def test_completed_clip_job_sends_telegram_success_alert(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    job = ClipJob(
        id="successful-alert",
        status="queued",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    candidate = ClipCandidate(
        index=1,
        start=0,
        end=30,
        duration=30,
        score=88,
        title="Hikmah yang Baik",
        reason="pesan lengkap",
        text="Pelajarannya, kita harus saling menghormati.",
    )
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=24,
        title="Hikmah yang Baik",
        fyp_score=88,
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "job_secrets", {})
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "cancelled_job_ids", set())
    monkeypatch.setattr(api, "preserve_job_files_on_cancel", set())
    monkeypatch.setattr(api, "build_clipper_command", lambda *_args, **_kwargs: ["clipper"])
    monkeypatch.setattr(api.subprocess, "Popen", lambda *_args, **_kwargs: FinishedClipperProcess(0))
    monkeypatch.setattr(api, "discover_clips", lambda *_args, **_kwargs: [clip])
    monkeypatch.setattr(api, "discover_candidates", lambda *_args, **_kwargs: [candidate])
    monkeypatch.setattr(api, "remember_processed_source", lambda *_args, **_kwargs: None)
    telegram_calls = []
    monkeypatch.setattr(api, "send_clip_success_telegram_alert", telegram_calls.append)

    run_job(job.id)

    assert api.jobs[job.id].status == "completed"
    assert len(telegram_calls) == 1
    assert telegram_calls[0].id == job.id


def test_source_media_candidates_never_reuses_ytdlp_partials(tmp_path):
    (tmp_path / "source.f137.mp4.part").write_bytes(b"incomplete")
    final = tmp_path / "source.mp4"
    final.write_bytes(b"complete")

    assert source_media_candidates(tmp_path) == [final]


def test_select_usable_source_skips_video_only_and_uses_audio_video(monkeypatch, tmp_path):
    import clipper

    video_only = tmp_path / "source.mp4"
    fallback = tmp_path / "source_fallback.webm"
    video_only.write_bytes(b"x" * 2048)
    fallback.write_bytes(b"y" * 2048)
    monkeypatch.setattr(
        clipper,
        "probe_media_stream_types",
        lambda path: {"video"} if path == video_only else {"video", "audio"},
    )

    assert select_usable_source_media(tmp_path) == fallback


def test_extract_audio_rejects_missing_track_before_running_ffmpeg(monkeypatch, tmp_path):
    import pytest
    import clipper

    source = tmp_path / "source.mp4"
    source.write_bytes(b"x" * 2048)
    monkeypatch.setattr(clipper, "probe_media_stream_types", lambda _path: {"video"})

    with pytest.raises(UserFacingError, match="tidak memiliki track audio"):
        extract_audio(source, tmp_path / "audio.wav")


def test_friendly_youtube_error_explains_network_failure():
    message = friendly_youtube_error(RuntimeError("[Errno 101] Network is unreachable"), "membaca metadata")

    assert "Upload Video" in message
    assert "membaca metadata" in message


def test_friendly_youtube_error_explains_403_after_embedded_retry():
    message = friendly_youtube_error(
        RuntimeError("unable to download video data: HTTP Error 403: Forbidden"),
        "mengunduh video",
    )

    assert "retry embedded/EJS" in message
    assert "upload file MP4" in message
    assert "ERROR:" not in message


def test_youtube_download_strategies_isolate_partial_files_and_add_embedded_retry(tmp_path):
    strategies = youtube_download_strategies(2160, tmp_path)

    assert [item["name"] for item in strategies] == [
        "default",
        "web_embedded_ejs",
        "web_safari_hls",
    ]
    assert len({item["outtmpl"] for item in strategies}) == 3
    assert strategies[1]["extractor_args"]["youtube"]["player_client"] == ["web_embedded"]
    assert "protocol^=m3u8" in strategies[2]["format"]
    assert strategies[2]["extractor_args"]["youtube"]["player_client"] == ["web_safari"]


def test_cleanup_clip_files_removes_output_artifacts(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "work" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01.mp4"
    thumb_path = clip_dir / "clip_01_thumb.jpg"
    prompt_path = clip_dir / "clip_01_thumb.txt"
    caption_path = clip_dir / "clip_01_caption.txt"
    subtitle_path = clip_dir / "clip_01.srt"
    dynamic_caption_path = clip_dir / "clip_01.dynamic.ass"
    for path in (
        clip_path,
        thumb_path,
        prompt_path,
        caption_path,
        subtitle_path,
        dynamic_caption_path,
    ):
        path.write_bytes(b"x")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/work/clips/clip_01.mp4",
        size_bytes=1,
        thumbnail_url="/outputs/work/clips/clip_01_thumb.jpg",
    )

    assert cleanup_clip_files(clip) == 8
    assert not clip_path.exists()
    assert not thumb_path.exists()
    assert not prompt_path.exists()
    assert not caption_path.exists()
    assert not subtitle_path.exists()
    assert not dynamic_caption_path.exists()
    assert not clip_dir.exists()


def test_clip_sidecar_title_reads_full_title(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "work" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01_saya-tidak-condong-tidak-setuju-kepada-buy.mp4"
    clip_path.write_bytes(b"x")
    clip_path.with_suffix(".json").write_text(
        '{"title": "Saya Tidak Condong, Tidak Setuju Kepada Buyut Saya"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    clip = ClipFile(
        name=clip_path.name,
        url="/outputs/work/clips/clip_01_saya-tidak-condong-tidak-setuju-kepada-buy.mp4",
        size_bytes=1,
    )

    assert api.clip_sidecar_title(clip) == "Saya Tidak Condong, Tidak Setuju Kepada Buyut Saya"


def test_enrich_clip_title_from_candidate_index_when_sidecar_missing(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "work" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_09_saya-tidak-condong-tidak-setuju-kepada-buy.mp4"
    clip_path.write_bytes(b"x")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    clips = [
        ClipFile(
            name=clip_path.name,
            url="/outputs/work/clips/clip_09_saya-tidak-condong-tidak-setuju-kepada-buy.mp4",
            size_bytes=1,
        )
    ]
    candidates = [
        ClipCandidate(
            index=9,
            start=0,
            end=10,
            duration=10,
            score=90,
            title="Saya Tidak Condong Tidak Setuju Kepada Buya Arrazi",
            reason="test",
            text="test",
        )
    ]

    enriched = api.enrich_clips_with_candidate_titles(clips, candidates)

    assert enriched[0].title == "Saya Tidak Condong Tidak Setuju Kepada Buya Arrazi"


def test_enrich_job_source_metadata_from_output_metadata(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "video-title" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01.mp4"
    clip_path.write_bytes(b"x")
    (outputs / "video-title" / "metadata.json").write_text(
        '{"title": "Judul Video Asli", "webpage_url": "https://youtu.be/demo", "uploader": "Channel Demo"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/fallback"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[
            ClipFile(
                name="clip_01.mp4",
                url="/outputs/video-title/clips/clip_01.mp4",
                size_bytes=1,
            )
        ],
    )

    enriched = api.enrich_job_source_metadata(job)

    assert enriched.source_title == "Judul Video Asli"
    assert enriched.source_url == "https://youtu.be/demo"
    assert enriched.source_uploader == "Channel Demo"


def test_cleanup_job_files_removes_related_output_folder(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "video-title" / "clips"
    clip_dir.mkdir(parents=True)
    (outputs / "video-title" / "metadata.json").write_text("{}")
    (outputs / "video-title" / "candidates.json").write_text("[]")
    clip_path = clip_dir / "clip_01.mp4"
    clip_path.write_bytes(b"x")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {})

    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/x"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[
            ClipFile(
                name="clip_01.mp4",
                url="/outputs/video-title/clips/clip_01.mp4",
                size_bytes=1,
            )
        ],
    )

    cleanup_job_files(job)

    assert not (outputs / "video-title").exists()


def test_cleanup_job_files_also_prunes_empty_job_id_parent(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    clip_dir = outputs / "job-uuid" / "video-title" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01.mp4"
    clip_path.write_bytes(b"video")
    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {})
    job = ClipJob(
        id="job-uuid",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/x"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[
            ClipFile(
                name=clip_path.name,
                url="/outputs/job-uuid/video-title/clips/clip_01.mp4",
                size_bytes=1,
            )
        ],
    )

    cleanup_job_files(job)

    assert not (outputs / "job-uuid").exists()


def test_orphan_sweep_preserves_referenced_and_recent_nonempty_roots(monkeypatch, tmp_path):
    import api
    import os

    outputs = tmp_path / "outputs"
    protected_file = outputs / "job-live" / "video" / "clips" / "clip_01.mp4"
    protected_file.parent.mkdir(parents=True)
    protected_file.write_bytes(b"keep")
    orphan_file = outputs / "job-orphan-old" / "video" / "source.mp4"
    orphan_file.parent.mkdir(parents=True)
    orphan_file.write_bytes(b"remove")
    recent_file = outputs / "job-orphan-recent" / "video" / "source.mp4"
    recent_file.parent.mkdir(parents=True)
    recent_file.write_bytes(b"keep for grace")
    empty_orphan = outputs / "job-orphan-empty"
    empty_orphan.mkdir(parents=True)

    old_timestamp = time.time() - 7200
    for path in [orphan_file, orphan_file.parent, orphan_file.parent.parent]:
        os.utime(path, (old_timestamp, old_timestamp))

    live_clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/job-live/video/clips/clip_01.mp4",
        size_bytes=1,
    )
    live_job = ClipJob(
        id="job-live",
        status="running",
        request=ClipJobRequest(url="https://youtu.be/live"),
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
        clips=[live_clip],
    )
    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {live_job.id: live_job})
    monkeypatch.setattr(api, "youtube_uploads", {})

    removed = cleanup_orphan_output_roots(min_age_seconds=3600)

    assert removed == 2
    assert protected_file.exists()
    assert recent_file.exists()
    assert not orphan_file.parent.parent.exists()
    assert not empty_orphan.exists()
