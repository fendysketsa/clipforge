import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from api import (
    ClipCandidate,
    ClipFile,
    ClipJob,
    ClipJobRequest,
    YouTubeUploadRequest,
    YouTubeUploadJob,
    best_youtube_clip_urls,
    build_youtube_upload_command,
    clip_requires_altered_content_disclosure,
    default_youtube_description,
    default_youtube_tags,
    default_youtube_title,
    delete_completed_youtube_upload_clip,
    generate_youtube_description,
    generate_youtube_metadata,
    completed_upload_cleanup_after,
    create_youtube_upload_record,
    monitor_youtube_upload_process,
    normalized_generated_metadata,
    youtube_monetization_preflight_issue,
    youtube_source_attribution,
    youtube_metadata_provider_configs,
    youtube_uploads_with_queue_positions,
    verified_duplicate_for_upload,
    delete_all_job_clips,
    start_youtube_cdp_refresh_process,
    sync_youtube_cdp,
    youtube_video_url_from_logs,
)
from youtube_uploader import normalized_upload_metadata, studio_start_url


@pytest.fixture(autouse=True)
def isolate_openrouter_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)


def make_clip(index: int) -> ClipFile:
    return ClipFile(
        name=f"clip_{index:02d}.mp4",
        url=f"/outputs/demo/clips/clip_{index:02d}.mp4",
        size_bytes=1,
    )


def make_candidate(index: int, score: int) -> ClipCandidate:
    return ClipCandidate(
        index=index,
        start=0,
        end=10,
        duration=10,
        score=score,
        title=f"Clip {index}",
        reason="test",
        text="test",
    )


def test_best_youtube_clip_urls_uses_candidate_scores():
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[make_clip(1), make_clip(2), make_clip(3), make_clip(4)],
        candidates=[
            make_candidate(1, 70),
            make_candidate(2, 98),
            make_candidate(3, 85),
            make_candidate(4, 92),
        ],
    )

    assert best_youtube_clip_urls(job, 3) == [
        "/outputs/demo/clips/clip_02.mp4",
        "/outputs/demo/clips/clip_04.mp4",
        "/outputs/demo/clips/clip_03.mp4",
    ]


@pytest.mark.parametrize(
    ("clip_name", "expected_type"),
    [
        ("clip_01.mp4", "shorts"),
        ("highlight_5menit_hikmah.mp4", "long-form"),
        ("resume_cerita_10menit_hikmah.mp4", "long-form"),
    ],
)
def test_upload_command_marks_thumbnail_content_type(
    monkeypatch,
    tmp_path,
    clip_name,
    expected_type,
):
    import api

    video_path = tmp_path / clip_name
    thumbnail_path = tmp_path / f"{video_path.stem}_thumb.jpg"
    video_path.write_bytes(b"video")
    thumbnail_path.write_bytes(b"thumbnail")

    def fake_output_path(url):
        return thumbnail_path if str(url).endswith("_thumb.jpg") else video_path

    monkeypatch.setattr(api, "output_path_from_url", fake_output_path)
    monkeypatch.setattr(api, "prepare_limited_upload_file", lambda path, _limit: path)
    monkeypatch.setattr(api, "youtube_upload_prefers_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_profile_upload_allowed", lambda: False)

    upload = YouTubeUploadJob(
        id="upload-thumb",
        source_job_id="job-thumb",
        clip_url=f"/outputs/demo/{clip_name}",
        clip_name=clip_name,
        status="queued",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        title="Judul",
        thumbnail_url=f"/outputs/demo/{video_path.stem}_thumb.jpg",
    )

    command = build_youtube_upload_command(upload)
    type_index = command.index("--thumbnail-content-type")

    assert command[type_index + 1] == expected_type


def test_upload_command_discloses_realistic_background_replacement(monkeypatch, tmp_path):
    import api

    video_path = tmp_path / "clip_01.mp4"
    video_path.write_bytes(b"video")
    monkeypatch.setattr(api, "output_path_from_url", lambda _url: video_path)
    monkeypatch.setattr(api, "prepare_limited_upload_file", lambda path, _limit: path)
    monkeypatch.setattr(api, "youtube_upload_prefers_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_profile_upload_allowed", lambda: False)
    upload = YouTubeUploadJob(
        id="upload-altered",
        source_job_id="job-altered",
        clip_url="/outputs/demo/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="queued",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        title="Judul",
        altered_content=True,
    )

    assert "--altered-content" in build_youtube_upload_command(upload)


def test_story_resume_upload_requires_automatic_thumbnail(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    video_path = outputs / "job-resume" / "clips" / "resume_cerita_5menit_inti.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")
    clip = ClipFile(
        name=video_path.name,
        url="/outputs/job-resume/clips/resume_cerita_5menit_inti.mp4",
        size_bytes=video_path.stat().st_size,
    )
    job = ClipJob(
        id="job-resume",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo", clip_mode="highlight_5m"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "youtube_uploads", {})

    with pytest.raises(HTTPException) as exc_info:
        create_youtube_upload_record(job.id, YouTubeUploadRequest(clip_url=clip.url))
    assert "Thumbnail otomatis" in str(exc_info.value.detail)


def test_best_youtube_clip_urls_falls_back_to_clip_order_without_scores():
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[make_clip(1), make_clip(2), make_clip(3), make_clip(4)],
    )

    assert best_youtube_clip_urls(job, 3) == [
        "/outputs/demo/clips/clip_01.mp4",
        "/outputs/demo/clips/clip_02.mp4",
        "/outputs/demo/clips/clip_03.mp4",
    ]


def test_queue_positions_follow_oldest_queued_first():
    uploads = [
        YouTubeUploadJob(
            id="queued-2",
            source_job_id="job-1",
            clip_url="/outputs/demo/clips/clip_02.mp4",
            clip_name="clip_02.mp4",
            status="queued",
            created_at="2026-01-01T00:00:02+00:00",
            updated_at="2026-01-01T00:00:02+00:00",
            title="Second",
        ),
        YouTubeUploadJob(
            id="running",
            source_job_id="job-1",
            clip_url="/outputs/demo/clips/clip_00.mp4",
            clip_name="clip_00.mp4",
            status="running",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
            title="Running",
        ),
        YouTubeUploadJob(
            id="queued-1",
            source_job_id="job-1",
            clip_url="/outputs/demo/clips/clip_01.mp4",
            clip_name="clip_01.mp4",
            status="queued",
            created_at="2026-01-01T00:00:01+00:00",
            updated_at="2026-01-01T00:00:01+00:00",
            title="First",
        ),
    ]

    positioned = {upload.id: upload for upload in youtube_uploads_with_queue_positions(uploads)}

    assert positioned["queued-1"].queue_position == 1
    assert positioned["queued-1"].queue_total == 2
    assert positioned["queued-2"].queue_position == 2
    assert positioned["queued-2"].queue_total == 2
    assert positioned["running"].queue_position is None


def test_youtube_cleanup_countdown_uses_backend_clock():
    now = datetime.now(timezone.utc)
    upload = YouTubeUploadJob(
        id="cleanup",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="completed",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        finished_at=now.isoformat(),
        title="Cleanup",
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
        clip_delete_after=(now + timedelta(seconds=30)).isoformat(),
    )

    positioned = youtube_uploads_with_queue_positions([upload])[0]

    assert positioned.backend_now is not None
    assert positioned.clip_delete_remaining_seconds is not None
    assert 29 <= positioned.clip_delete_remaining_seconds <= 30


def test_identical_completed_clip_is_not_uploaded_again(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    clip_path = outputs / "new-job" / "clips" / "clip_01.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"same-video-content")
    clip = ClipFile(
        name=clip_path.name,
        url="/outputs/new-job/clips/clip_01.mp4",
        size_bytes=clip_path.stat().st_size,
    )
    job = ClipJob(
        id="new-job",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/new"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    fingerprint = api.file_sha256(clip_path)
    completed = YouTubeUploadJob(
        id="already-uploaded",
        source_job_id="old-job",
        clip_url="/outputs/old-job/clips/clip_09.mp4",
        clip_name="clip_09.mp4",
        status="completed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:01:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        title="Already uploaded",
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
        clip_sha256=fingerprint,
    )
    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "youtube_uploads", {completed.id: completed})
    monkeypatch.setattr(
        api,
        "generate_youtube_metadata",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("metadata generation must be skipped for a verified duplicate")
        ),
    )

    reused = create_youtube_upload_record(
        job.id,
        YouTubeUploadRequest(clip_url=clip.url),
    )

    assert reused.status == "completed"
    assert reused.video_url == completed.video_url
    assert reused.source_job_id == job.id
    assert reused.clip_url == clip.url
    assert reused.clip_delete_after is not None
    assert "Upload dilewati" in reused.logs[0]


def test_worker_preflight_detects_duplicate_already_in_queue_history(monkeypatch):
    import api

    completed = YouTubeUploadJob(
        id="completed",
        source_job_id="job-old",
        clip_url="/outputs/old/clip.mp4",
        clip_name="clip.mp4",
        status="completed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:01:00+00:00",
        title="Uploaded",
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
        clip_sha256="abc123",
    )
    queued = YouTubeUploadJob(
        id="queued",
        source_job_id="job-new",
        clip_url="/outputs/new/clip.mp4",
        clip_name="clip.mp4",
        status="queued",
        created_at="2026-01-01T00:02:00+00:00",
        updated_at="2026-01-01T00:02:00+00:00",
        title="Duplicate",
        clip_sha256="abc123",
    )
    monkeypatch.setattr(api, "youtube_uploads", {completed.id: completed, queued.id: queued})

    duplicate = verified_duplicate_for_upload(queued, "abc123")

    assert duplicate is not None
    assert duplicate.id == completed.id
    assert duplicate.video_url == completed.video_url


def test_delete_all_job_clips_waits_for_active_youtube_upload(monkeypatch, tmp_path):
    import api
    import pytest
    from fastapi import HTTPException

    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[make_clip(1)],
    )
    upload = YouTubeUploadJob(
        id="upload-1",
        source_job_id=job.id,
        clip_url=job.clips[0].url,
        clip_name=job.clips[0].name,
        status="queued",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        title="Clip 1",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})
    monkeypatch.setattr(api, "job_processes", {})

    with pytest.raises(HTTPException) as error:
        delete_all_job_clips(job.id)

    assert error.value.status_code == 409
    assert "upload YouTube aktif" in str(error.value.detail)


def test_normalized_upload_metadata_recovers_when_title_is_description(tmp_path):
    video = tmp_path / "clip_01_tuh-sekarang-kalau-bapak-ya.mp4"
    video.write_bytes(b"x")
    video.with_suffix(".json").write_text(
        '{"title": "Tuh Sekarang Kalau Bapak Ya"}',
        encoding="utf-8",
    )

    title, description = normalized_upload_metadata(
        video,
        "Sumber: https://www.youtube.com/watch?v=demo\n\nChannel sumber: Titik Ilmu\n\n#islam #shorts #ryuundy",
        "",
    )

    assert title == "Tuh Sekarang Kalau Bapak Ya #Shorts"
    assert description.startswith("Sumber: https://www.youtube.com/watch?v=demo")


def test_normalized_upload_metadata_uses_filename_when_sidecar_missing(tmp_path):
    video = tmp_path / "clip_02_ini-judul-dari-file.mp4"
    video.write_bytes(b"x")

    title, description = normalized_upload_metadata(
        video,
        "Sumber: https://www.youtube.com/watch?v=demo #islam #shorts #ryuundy",
        "Deskripsi benar",
    )

    assert title == "Ini Judul Dari File #Shorts"
    assert description == "Deskripsi benar"


def test_studio_start_url_uses_channel_dashboard():
    assert studio_start_url(
        "https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ/videos/short?filter=%5B%5D"
    ) == "https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ"


def test_youtube_video_url_from_logs_accepts_shorts_links():
    assert youtube_video_url_from_logs(["VIDEO_URL: https://youtube.com/shorts/abcDEF12345?feature=share"]) == (
        "https://www.youtube.com/watch?v=abcDEF12345"
    )


def test_completed_upload_cleanup_delay_defaults_to_thirty_seconds(monkeypatch):
    monkeypatch.delenv("YOUTUBE_DELETE_UPLOADED_CLIP_DELAY_SECONDS", raising=False)

    delete_after = completed_upload_cleanup_after("2026-01-01T00:00:00+00:00")

    assert delete_after == "2026-01-01T00:00:30+00:00"


def test_completed_upload_cleanup_deletes_real_file_and_updates_job(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    clip_dir = outputs / "demo" / "clips"
    clip_dir.mkdir(parents=True)
    clip_one = make_clip(1)
    clip_two = make_clip(2)
    clip_one_path = clip_dir / clip_one.name
    clip_two_path = clip_dir / clip_two.name
    clip_one_path.write_bytes(b"video")
    clip_two_path.write_bytes(b"keep")
    clip_one_path.with_name("clip_01_thumb.jpg").write_bytes(b"thumbnail")
    clip_one_path.with_suffix(".json").write_text('{"title": "Uploaded"}', encoding="utf-8")
    clip_one_path.with_name("clip_01_caption.txt").write_text("caption", encoding="utf-8")
    clip_one_path.with_suffix(".srt").write_text("subtitle", encoding="utf-8")
    clip_one_path.with_name("clip_01.dynamic.ass").write_text("dynamic", encoding="utf-8")

    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip_one, clip_two],
    )
    upload = YouTubeUploadJob(
        id="upload-1",
        source_job_id=job.id,
        clip_url=clip_one.url,
        clip_name=clip_one.name,
        status="completed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:01:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        title="Uploaded",
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})
    cleanup_events = []
    original_set_cleanup_step = api.set_youtube_cleanup_step

    def record_cleanup_step(upload_id, step, completed_steps, step_details=None):
        cleanup_events.append((step, tuple(completed_steps)))
        original_set_cleanup_step(upload_id, step, completed_steps, step_details)

    monkeypatch.setattr(api, "set_youtube_cleanup_step", record_cleanup_step)

    removed, removed_job = delete_completed_youtube_upload_clip(
        upload.id,
        steps=("thumbnail",),
    )
    assert not clip_one_path.with_name("clip_01_thumb.jpg").exists()
    assert clip_one_path.exists()
    assert api.youtube_uploads[upload.id].clip_cleanup_completed_steps == ["thumbnail"]

    for step in ("metadata", "video", "workspace", "job_sync"):
        step_removed, removed_job = delete_completed_youtube_upload_clip(
            upload.id,
            steps=(step,),
        )
        removed += step_removed

    assert removed >= 6
    assert removed_job is False
    assert not clip_one_path.exists()
    assert not clip_one_path.with_suffix(".json").exists()
    assert not clip_one_path.with_name("clip_01_caption.txt").exists()
    assert not clip_one_path.with_suffix(".srt").exists()
    assert not clip_one_path.with_name("clip_01.dynamic.ass").exists()
    assert clip_two_path.exists()
    assert [clip.url for clip in api.jobs[job.id].clips] == [clip_two.url]
    assert [event[0] for event in cleanup_events if event[0]] == [
        "thumbnail",
        "metadata",
        "video",
        "workspace",
        "job_sync",
    ]
    assert api.youtube_uploads[upload.id].clip_cleanup_completed_steps == list(
        api.YOUTUBE_CLEANUP_STEPS
    )
    step_details = api.youtube_uploads[upload.id].clip_cleanup_step_details
    assert list(step_details) == list(api.YOUTUBE_CLEANUP_STEPS)
    assert all(item.completed_at for item in step_details.values())
    assert all(item.duration_ms is not None for item in step_details.values())


def test_completed_upload_cleanup_refuses_unverified_upload(monkeypatch):
    import api

    upload = YouTubeUploadJob(
        id="upload-1",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="completed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:01:00+00:00",
        title="No URL",
        video_url=None,
    )
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})

    with pytest.raises(RuntimeError, match="belum terkonfirmasi"):
        delete_completed_youtube_upload_clip(upload.id)


def test_upload_watchdog_terminates_silent_process():
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", "import time; print('started'); time.sleep(10)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    logs = []

    code, stalled = monitor_youtube_upload_process(
        process,
        logs.append,
        stall_timeout_seconds=0.1,
    )

    assert stalled is True
    assert code != 0
    assert logs == ["started"]


def test_upload_watchdog_treats_video_url_as_terminal_success():
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            (
                "import time; "
                "print('VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345'); "
                "time.sleep(10)"
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    logs = []

    code, stalled = monitor_youtube_upload_process(
        process,
        logs.append,
        stall_timeout_seconds=5,
        terminal_grace_seconds=0.05,
    )

    assert code == 0
    assert stalled is False
    assert logs == ["VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345"]
    assert process.poll() is not None


def test_running_upload_with_verified_url_recovers_as_completed(monkeypatch, tmp_path):
    import api

    upload = YouTubeUploadJob(
        id="recover-upload",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="running",
        created_at="2026-07-31T09:00:00+00:00",
        updated_at="2026-07-31T09:01:00+00:00",
        started_at="2026-07-31T09:00:01+00:00",
        title="Recovered",
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
        logs=["VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345"],
    )
    uploads_path = tmp_path / "youtube_uploads.json"
    uploads_path.write_text(
        json.dumps([upload.model_dump()]),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", uploads_path)

    recovered = api.load_youtube_uploads()[upload.id]

    assert recovered.status == "completed"
    assert recovered.video_url == upload.video_url
    assert recovered.clip_delete_after is not None
    assert recovered.error is None
    assert "tanpa upload ulang" in recovered.logs[-1]


def test_start_youtube_cdp_refresh_process_uses_configured_command(monkeypatch, tmp_path):
    import api

    calls = []

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

        def poll(self):
            return None

    monkeypatch.setenv("YOUTUBE_CDP_REFRESH_COMMAND", "/bin/echo refresh")
    monkeypatch.setattr(api, "YOUTUBE_CDP_REFRESH_LOG", tmp_path / "chrome-refresh.log")
    monkeypatch.setattr(api, "YOUTUBE_CDP_REFRESH_STARTUP_GRACE_SECONDS", 0)
    monkeypatch.setattr(api, "youtube_cdp_ready", lambda: True)
    monkeypatch.setattr(api.subprocess, "Popen", FakePopen)

    status = start_youtube_cdp_refresh_process()

    assert status.started is True
    assert status.cdp_ready is True
    assert status.command == ["/bin/echo", "refresh"]
    assert status.log_path == str(tmp_path / "chrome-refresh.log")
    assert calls[0][0] == ["/bin/echo", "refresh"]
    assert calls[0][1]["start_new_session"] is True


def test_sync_youtube_cdp_requires_existing_cdp(monkeypatch):
    import api

    capture_called = False

    def fake_capture():
        nonlocal capture_called
        capture_called = True
        return 0, [], None

    monkeypatch.setattr(api, "playwright_installed", lambda: True)
    monkeypatch.setattr(api, "youtube_cdp_ready", lambda: False)
    monkeypatch.setattr(api, "run_youtube_capture_once", fake_capture)

    status = sync_youtube_cdp()

    assert status.ok is False
    assert status.cdp_ready is False
    assert status.session_ready is False
    assert capture_called is False


def test_sync_youtube_cdp_validates_existing_cdp(monkeypatch):
    import api

    monkeypatch.setattr(api, "playwright_installed", lambda: True)
    monkeypatch.setattr(api, "youtube_cdp_ready", lambda: True)
    monkeypatch.setattr(
        api,
        "run_youtube_capture_once",
        lambda: (0, ["Storage-state YouTube dimasukkan ke Chrome CDP: /tmp/state.json"], None),
    )

    status = sync_youtube_cdp()

    assert status.ok is True
    assert status.cdp_ready is True
    assert status.session_ready is True
    assert status.hydrated is True


def test_profile_sync_opens_login_fallback_and_requests_automatic_reconnect(monkeypatch, tmp_path):
    import api

    reconnect_requests = []
    monkeypatch.setattr(api, "playwright_installed", lambda: True)
    monkeypatch.setattr(api, "youtube_login_source_profile_dir", lambda: str(tmp_path))
    monkeypatch.setattr(api, "youtube_login_source_profile_ready", lambda: True)
    monkeypatch.setattr(
        api,
        "repair_youtube_cdp",
        lambda profile_sync_requested=True: api.YouTubeCdpRepairStatus(
            ok=False,
            cdp_ready=False,
            session_ready=False,
            profile_sync_requested=profile_sync_requested,
            source_profile_ready=True,
            source_profile_path=str(tmp_path),
            started_at="2026-01-01T00:00:00+00:00",
            message="Refresh Chrome CDP gagal dari backend.",
            error="Launcher Chrome CDP exit code 1",
            logs=["launcher failed"],
        ),
    )

    def fake_start_login(*, reconnect_cdp=False):
        reconnect_requests.append(reconnect_cdp)
        return api.YouTubeLoginStatus(active=True, logs=["browser opened"])

    monkeypatch.setattr(api, "start_youtube_login_if_needed", fake_start_login)

    status = api.sync_youtube_cdp_from_profile()

    assert status.ok is False
    assert status.login_required is True
    assert status.error is None
    assert reconnect_requests == [True]
    assert "browser login YouTube dibuka" in status.message
    assert "browser opened" in status.logs


def test_completed_fallback_login_restarts_cdp_and_validates_session(monkeypatch):
    import api

    refresh_calls = []

    class FakeLoginProcess:
        stdout = iter(["Sesi YouTube tersimpan: /tmp/youtube-state.json\n"])

        def wait(self):
            return 0

    monkeypatch.setattr(api.subprocess, "Popen", lambda *args, **kwargs: FakeLoginProcess())
    monkeypatch.setattr(
        api,
        "start_youtube_cdp_refresh_process",
        lambda **kwargs: (
            refresh_calls.append(kwargs)
            or api.YouTubeCdpRefreshStatus(
                started=True,
                cdp_ready=True,
                started_at="2026-01-01T00:00:00+00:00",
                command=["chrome"],
                log_path="/tmp/chrome.log",
                message="CDP ready",
                logs=["launcher ready"],
            )
        ),
    )
    monkeypatch.setattr(api, "run_youtube_capture_once", lambda: (0, ["target valid"], None))
    monkeypatch.setattr(api, "youtube_login_process", None)
    monkeypatch.setattr(api, "youtube_login_reconnect_cdp", True)
    monkeypatch.setattr(api, "youtube_login_status", api.YouTubeLoginStatus(active=True))

    api.run_youtube_login_process()

    assert refresh_calls == [{"force_restart": True}]
    assert api.youtube_login_status.active is False
    assert api.youtube_login_status.error is None
    assert "RECONNECT_CDP_SUCCESS" in api.youtube_login_status.logs[-1]
    assert api.youtube_login_process is None
    assert api.youtube_login_reconnect_cdp is False


def test_default_youtube_description_uses_ai_caption_and_hashtags_only():
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Judul Clip",
        social_caption="Ini caption AI yang siap diposting.\n\n#islam #shorts",
    )
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        source_url="https://youtu.be/source",
        source_uploader="Channel Demo",
        clips=[clip],
    )

    description = default_youtube_description(job, clip)

    assert "Ini caption AI yang siap diposting." in description
    assert "#islam #shorts" in description
    assert "Sumber:" not in description
    assert "Channel sumber:" not in description


def test_verified_cc_source_gets_required_attribution(monkeypatch):
    import api

    job = ClipJob(
        id="job-cc",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(
        api,
        "metadata_for_job",
        lambda _job: {
            "title": "Ceramah Sumber",
            "uploader": "Kreator Asli",
            "webpage_url": "https://youtu.be/source",
            "license": "Creative Commons Attribution license",
        },
    )

    value = youtube_source_attribution(job)

    assert "Atribusi sumber (CC BY)" in value
    assert "Kreator: Kreator Asli" in value
    assert "Sumber: https://youtu.be/source" in value
    assert "Diolah secara editorial oleh @ryuundyofficial" in value


def test_monetization_preflight_requires_rights_and_substantive_edit(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-ready",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "metadata_for_job",
        lambda _job: {"license": "Creative Commons Attribution license"},
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "monetization_readiness": {"eligible_for_private_upload_review": True}
        },
    )

    assert youtube_monetization_preflight_issue(job, clip) is None

    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: {})
    assert "Render ulang" in (youtube_monetization_preflight_issue(job, clip) or "")


def test_monetization_preflight_blocks_short_outside_official_technical_limits(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-invalid-short",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "metadata_for_job",
        lambda _job: {"license": "Creative Commons Attribution license"},
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "output_format": "vertical_short",
            "aspect_ratio": "9:16",
            "duration": 181,
            "thumbnail_strategy": "embedded_shorts_cover_frame",
            "monetization_readiness": {"eligible_for_private_upload_review": True},
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""
    assert "181.0 detik" in issue
    assert "180 detik" in issue


def test_monetization_preflight_accepts_legacy_compilation_story_arc(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-legacy-compilation",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "metadata_for_job",
        lambda _job: {"license": "Creative Commons Attribution license"},
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "output_format": "landscape_compilation",
            "monetization_readiness": {
                "eligible_for_private_upload_review": False,
                "originality_score": 5,
                "minimum_originality_score": 4,
                "signals": {
                    "enhanced_edit": True,
                    "substantive_visual_edits": False,
                    "structured_story_arc": True,
                    "editorial_hook_and_context": True,
                    "original_core_message": True,
                    "custom_thumbnail_strategy": True,
                },
            },
        },
    )

    assert youtube_monetization_preflight_issue(job, clip) is None


def test_monetization_preflight_explains_when_enhanced_edit_is_actually_missing(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-no-enhanced-edit",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "metadata_for_job",
        lambda _job: {"license": "Creative Commons Attribution license"},
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "output_format": "vertical_short",
            "monetization_readiness": {
                "eligible_for_private_upload_review": False,
                "originality_score": 4,
                "minimum_originality_score": 3,
                "signals": {
                    "enhanced_edit": False,
                    "substantive_visual_edits": True,
                },
            },
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""
    assert "Enhanced Edit tidak aktif" in issue


def test_realistic_background_change_requires_disclosure(monkeypatch):
    import api

    clip = make_clip(1)
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {"adaptive_text_split": {"enabled": True}},
    )

    assert clip_requires_altered_content_disclosure(clip) is True


def test_combined_job_highlight_metadata_is_not_marked_as_short():
    clip = ClipFile(
        name="highlight_5menit_poin-penting.mp4",
        url="/outputs/demo/clips/highlight_5menit_poin-penting.mp4",
        size_bytes=1,
        title="Lima Poin Penting #Shorts",
        social_caption="Ringkasan poin paling penting.\n\n#islam #shorts",
    )
    job = ClipJob(
        id="job-highlight",
        status="completed",
        request=ClipJobRequest(
            url="https://youtu.be/demo",
            clip_mode="short",
        ),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )

    assert default_youtube_title(job, clip, 1) == "Lima Poin Penting"
    assert "shorts" not in {tag.lower() for tag in default_youtube_tags(job, clip)}


def test_uploader_preserves_long_form_highlight_title(tmp_path):
    video = tmp_path / "highlight_5menit_poin-penting.mp4"
    video.write_bytes(b"x")

    title, _description = normalized_upload_metadata(
        video,
        "Lima Poin Penting #Shorts",
        "Ringkasan video.",
    )

    assert title == "Lima Poin Penting"


def test_generate_youtube_description_uses_llm(monkeypatch):
    import api

    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Judul Clip",
        social_caption="Caption lama.",
    )
    monkeypatch.setenv("TELEGRAM_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("TELEGRAM_AI_MODEL", "deepseek-v4-flash:cloud")
    monkeypatch.delenv("YOUTUBE_DESCRIPTION_AI_BASE_URL", raising=False)
    monkeypatch.delenv("YOUTUBE_DESCRIPTION_AI_MODEL", raising=False)

    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(
            url="https://youtu.be/demo",
            ai_enabled=True,
        ),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
        candidates=[make_candidate(1, 90)],
    )

    def fake_chat_completion(config, messages):
        assert config.base_url == "http://127.0.0.1:11434/v1"
        assert config.model == "deepseek-v4-flash:cloud"
        assert "Judul kerja klip (hanya petunjuk, wajib ditulis ulang): Judul Clip" in messages[-1]["content"]
        return '{"title": "Nasihat Singkat Tentang Asef", "description": "Klip ini menjelaskan nasihat penting dengan konteks yang mudah dipahami. Simak poin utamanya agar pesan yang disampaikan dapat diterapkan dengan tepat.", "hashtags": ["#islam", "#nasihat", "#hikmah", "#shorts"]}'

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    assert generate_youtube_description(job, clip, ["islam", "shorts"]) == (
        "Klip ini menjelaskan nasihat penting dengan konteks yang mudah dipahami. Simak poin utamanya agar pesan yang disampaikan dapat diterapkan dengan tepat.\n\n#islam #nasihat #hikmah #shorts"
    )

    assert generate_youtube_metadata(job, clip, ["islam", "shorts"]) == {
        "title": "Nasihat Singkat Tentang Asef #Shorts",
        "description": "Klip ini menjelaskan nasihat penting dengan konteks yang mudah dipahami. Simak poin utamanya agar pesan yang disampaikan dapat diterapkan dengan tepat.\n\n#islam #nasihat #hikmah #shorts",
        "hashtags": ["islam", "nasihat", "hikmah", "shorts"],
    }


def test_generate_youtube_metadata_accepts_indonesian_ollama_keys(monkeypatch):
    import api

    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Judul Clip",
    )
    monkeypatch.setenv("TELEGRAM_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("TELEGRAM_AI_MODEL", "deepseek-v4-flash:cloud")
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo", ai_enabled=True),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )

    monkeypatch.setattr(
        api,
        "chat_completion",
        lambda config, messages: '{"judul": "Pelajaran Rezeki Hari Ini", "deskripsi": "Renungan ini membahas makna rezeki dan pentingnya rasa syukur dalam kehidupan. Pesannya mengajak kita melihat nikmat dengan hati yang lebih jernih.", "tagar": "#rezeki #syukur #islam #shorts"}',
    )

    assert generate_youtube_metadata(job, clip, ["islam", "shorts"]) == {
        "title": "Pelajaran Rezeki Hari Ini #Shorts",
        "description": "Renungan ini membahas makna rezeki dan pentingnya rasa syukur dalam kehidupan. Pesannya mengajak kita melihat nikmat dengan hati yang lebih jernih.\n\n#rezeki #syukur #islam #shorts",
        "hashtags": ["rezeki", "syukur", "islam", "shorts"],
    }


def test_generate_youtube_metadata_falls_back_when_primary_model_fails(monkeypatch):
    import api

    clip = ClipFile(name="clip_01.mp4", url="/outputs/demo/clips/clip_01.mp4", size_bytes=1, title="Judul Clip")
    monkeypatch.setenv("TELEGRAM_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("TELEGRAM_AI_MODEL", "deepseek-v4-flash:cloud")
    monkeypatch.setenv("TELEGRAM_AI_FALLBACK_MODELS", "llama3:latest")
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo", ai_enabled=True),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )

    def fake_chat_completion(config, messages):
        if config.model == "deepseek-v4-flash:cloud":
            raise ValueError("this model requires a subscription")
        assert config.model == "llama3:latest"
        return '{"title": "Nasihat Baru yang Layak Diperhatikan", "description": "Model fallback menjelaskan inti nasihat secara segar berdasarkan konteks klip. Deskripsi ini tetap ringkas, informatif, dan tidak mengambil metadata lama.", "hashtags": ["#nasihat", "#islam", "#hikmah", "#shorts"]}'

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    assert generate_youtube_metadata(job, clip, ["islam"]) == {
        "title": "Nasihat Baru yang Layak Diperhatikan #Shorts",
        "description": "Model fallback menjelaskan inti nasihat secara segar berdasarkan konteks klip. Deskripsi ini tetap ringkas, informatif, dan tidak mengambil metadata lama.\n\n#nasihat #islam #hikmah #shorts",
        "hashtags": ["nasihat", "islam", "hikmah", "shorts"],
    }


def test_generate_youtube_metadata_retries_incomplete_output_then_uses_fallback(monkeypatch):
    import api

    clip = ClipFile(name="clip_01.mp4", url="/outputs/demo/clips/clip_01.mp4", size_bytes=1, title="Judul Kerja")
    monkeypatch.setenv("TELEGRAM_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("TELEGRAM_AI_MODEL", "primary-model")
    monkeypatch.setenv("TELEGRAM_AI_FALLBACK_MODELS", "indonesian-local")
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo", ai_enabled=True),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    calls: list[str] = []

    def fake_chat_completion(config, messages):
        calls.append(config.model)
        if config.model == "primary-model":
            return '{"title": "Terlalu Pendek", "description": "Pendek.", "hashtags": []}'
        return (
            '{"title": "Hikmah Kesabaran Saat Ujian Terasa Berat", '
            '"description": "Klip ini mengajak kita memahami kesabaran ketika ujian terasa berat. '
            'Pesannya menunjukkan bahwa proses sulit tetap dapat menyimpan hikmah yang bermakna.", '
            '"hashtags": ["#Sabar", "#UjianHidup", "#Hikmah", "#Shorts"]}'
        )

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    result = generate_youtube_metadata(job, clip, [])

    assert calls[:2] == ["primary-model", "primary-model"]
    assert "indonesian-local" in calls
    assert result is not None
    assert result["hashtags"] == ["Sabar", "UjianHidup", "Hikmah", "Shorts"]


def test_openrouter_is_first_and_ollama_is_metadata_fallback(monkeypatch):
    import api

    clip = ClipFile(name="clip_01.mp4", url="/outputs/demo/clips/clip_01.mp4", size_bytes=1, title="Judul Kerja")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-test")
    monkeypatch.setenv("TELEGRAM_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("TELEGRAM_AI_MODEL", "llama-local")
    monkeypatch.setenv("TELEGRAM_AI_FALLBACK_MODELS", "llama-local")
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo", ai_enabled=True),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    calls: list[tuple[str, str]] = []

    def fake_chat_completion(config, messages):
        calls.append((config.base_url, config.model))
        if "openrouter.ai" in config.base_url:
            raise ValueError("OpenRouter temporary failure")
        return (
            '{"title": "Pelajaran Penting dari Konteks Klip Ini", '
            '"description": "AI lokal membaca konteks klip dan menuliskan kembali inti pesannya secara akurat. '
            'Hasil ini dipakai hanya setelah OpenRouter tidak dapat menyelesaikan permintaan.", '
            '"hashtags": ["#Pelajaran", "#KonteksVideo", "#Hikmah", "#Shorts"]}'
        )

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    providers = youtube_metadata_provider_configs(job)
    result = generate_youtube_metadata(job, clip, [])

    assert [name for name, _config, _models in providers] == ["OpenRouter", "Ollama"]
    assert calls[0] == ("https://openrouter.ai/api/v1", "google/gemini-test")
    assert calls[1] == ("http://127.0.0.1:11434/v1", "llama-local")
    assert result is not None
    assert result["hashtags"] == ["Pelajaran", "KonteksVideo", "Hikmah", "Shorts"]


def test_normalized_generated_metadata_accepts_nested_ollama_payload():
    payload = {
        "metadata": {
            "judul_video": "Sabar Saat Ujian Mengubah Cara Kita Melihat Hidup",
            "deskripsi_video": (
                "Klip ini membahas bagaimana kesabaran menjaga hati ketika ujian datang. "
                "Pesannya mengajak penonton memahami hikmah tanpa mengabaikan proses yang berat."
            ),
            "tags": ["#Sabar", "#UjianHidup", "#HikmahIslam", "#Shorts"],
        }
    }

    assert normalized_generated_metadata(payload, is_compilation=False) == {
        "title": "Sabar Saat Ujian Mengubah Cara Kita Melihat Hidup #Shorts",
        "description": (
            "Klip ini membahas bagaimana kesabaran menjaga hati ketika ujian datang. "
            "Pesannya mengajak penonton memahami hikmah tanpa mengabaikan proses yang berat."
            "\n\n#Sabar #UjianHidup #HikmahIslam #Shorts"
        ),
        "hashtags": ["Sabar", "UjianHidup", "HikmahIslam", "Shorts"],
    }
