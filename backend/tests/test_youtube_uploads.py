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
    append_youtube_chapters,
    best_youtube_clip_urls,
    build_youtube_upload_command,
    classify_long_form_playlist,
    clip_requires_altered_content_disclosure,
    complete_youtube_description,
    default_youtube_description,
    default_youtube_tags,
    default_youtube_title,
    delete_completed_youtube_upload_clip,
    generate_youtube_description,
    generate_youtube_metadata,
    completed_upload_cleanup_after,
    create_youtube_upload_record,
    create_youtube_upload_batch_records,
    monitor_youtube_upload_process,
    normalized_generated_metadata,
    youtube_monetization_preflight_issue,
    youtube_source_attribution,
    youtube_growth_targets,
    youtube_metadata_provider_configs,
    youtube_uploads_with_queue_positions,
    verified_duplicate_for_upload,
    delete_all_job_clips,
    start_youtube_cdp_refresh_process,
    sync_youtube_cdp,
    youtube_final_visibility_from_logs,
    youtube_chapters_from_sidecar,
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


def test_automatic_upload_batch_skips_failed_preflight_instead_of_aborting(monkeypatch):
    import api

    job = ClipJob(
        id="job-filtered-batch",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[make_clip(1), make_clip(2), make_clip(3)],
        candidates=[
            make_candidate(1, 99),
            make_candidate(2, 95),
            make_candidate(3, 90),
        ],
    )
    monkeypatch.setitem(api.jobs, job.id, job)
    monkeypatch.setattr(
        api,
        "youtube_monetization_preflight_issue",
        lambda _job, clip: "ending menggantung" if clip.name == "clip_01.mp4" else None,
    )
    monkeypatch.setattr(
        api,
        "create_youtube_upload_record",
        lambda _job_id, request: YouTubeUploadJob(
            id=request.clip_url,
            source_job_id=job.id,
            clip_url=request.clip_url,
            clip_name=request.clip_url.rsplit("/", 1)[-1],
            status="queued",
            title="Test upload",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )

    uploads = create_youtube_upload_batch_records(
        job.id,
        api.YouTubeBatchUploadRequest(best_count=2),
    )

    assert [upload.clip_url for upload in uploads] == [
        "/outputs/demo/clips/clip_02.mp4",
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
    monkeypatch.setattr(api, "media_duration_seconds", lambda _path: 42.125)
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
    duration_index = command.index("--media-duration-seconds")
    assert command[duration_index + 1] == "42.125"
    assert command[command.index("--thumbnail") + 1] == str(thumbnail_path)


def test_upload_command_marks_shorts_type_even_without_thumbnail(monkeypatch, tmp_path):
    import api

    video_path = tmp_path / "clip_01.mp4"
    video_path.write_bytes(b"video")
    monkeypatch.setattr(api, "output_path_from_url", lambda _url: video_path)
    monkeypatch.setattr(api, "prepare_limited_upload_file", lambda path, _limit: path)
    monkeypatch.setattr(api, "media_duration_seconds", lambda _path: 59.9)
    monkeypatch.setattr(api, "youtube_upload_prefers_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_profile_upload_allowed", lambda: False)
    upload = YouTubeUploadJob(
        id="upload-no-thumb",
        source_job_id="job-no-thumb",
        clip_url="/outputs/demo/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="queued",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        title="Judul",
    )

    command = build_youtube_upload_command(upload)

    assert command[command.index("--thumbnail-content-type") + 1] == "shorts"
    assert command[command.index("--media-duration-seconds") + 1] == "59.900"


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


@pytest.mark.parametrize(
    ("story", "expected"),
    [
        ("Kisah horor sopir melihat penumpang gaib di Jalan Sumatera", "Horor"),
        ("Legenda asal usul Putri dari kerajaan lama", "Legenda"),
        ("Cerita rakyat tentang kancil yang diwariskan turun-temurun", "Cerita Rakyat"),
        ("Perjalanan seorang anak menemukan kampung kelahirannya", "Cerita Rakyat"),
    ],
)
def test_long_form_playlist_is_classified_without_user_ui(story, expected):
    assert classify_long_form_playlist(story) == expected


def test_youtube_growth_targets_ignore_stale_short_sidecar_target():
    clip = make_clip(1).model_copy(
        update={"growth_target_views": 5000, "growth_target_subscribers": 5}
    )
    job = ClipJob(
        id="job-short-target",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4", clip_mode="short"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )

    assert youtube_growth_targets(job, clip) == (50000, 20)


def test_youtube_growth_targets_keep_long_form_baseline_separate():
    clip = ClipFile(
        name="resume_cerita_5menit_inti.mp4",
        url="/outputs/demo/clips/resume_cerita_5menit_inti.mp4",
        size_bytes=1,
        growth_target_views=20000,
        growth_target_subscribers=99,
    )
    job = ClipJob(
        id="job-long-target",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4", clip_mode="highlight_5m"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )

    assert youtube_growth_targets(job, clip) == (5000, 20)


def test_saved_upload_model_migrates_stale_targets_by_format():
    short = YouTubeUploadJob(
        id="saved-short",
        source_job_id="job-short",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="completed",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        title="Short",
        growth_target_views=5000,
        growth_target_subscribers=5,
    )
    long_form = short.model_copy(
        update={
            "id": "saved-long",
            "clip_name": "resume_cerita_5menit_inti.mp4",
            "growth_target_views": 20000,
            "growth_target_subscribers": 99,
        }
    )
    # model_copy intentionally skips validation, mirroring a raw persisted payload below.
    long_form = YouTubeUploadJob(**long_form.model_dump())

    assert (short.growth_target_views, short.growth_target_subscribers) == (50000, 20)
    assert (long_form.growth_target_views, long_form.growth_target_subscribers) == (5000, 20)


def test_saved_clip_model_migrates_stale_targets_by_format():
    short = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        growth_target_views=20000,
        growth_target_subscribers=5,
    )
    long_form = ClipFile(
        name="resume_cerita_5menit_inti.mp4",
        url="/outputs/demo/clips/resume_cerita_5menit_inti.mp4",
        size_bytes=1,
        growth_target_views=50000,
        growth_target_subscribers=99,
    )

    assert (short.growth_target_views, short.growth_target_subscribers) == (50000, 20)
    assert (long_form.growth_target_views, long_form.growth_target_subscribers) == (5000, 20)


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


def test_youtube_final_visibility_from_logs_prefers_latest_verified_value():
    assert youtube_final_visibility_from_logs(
        ["FINAL_VISIBILITY: public", "FINAL_VISIBILITY: private"]
    ) == "private"


def test_long_form_description_gets_valid_manual_chapters(monkeypatch):
    import api

    clip = ClipFile(
        name="resume_cerita_5menit_inti.mp4",
        url="/outputs/demo/resume_cerita_5menit_inti.mp4",
        size_bytes=1,
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "output_format": "landscape_compilation",
            "parts": [
                {"duration": 42, "title": "Jawaban yang Paling Penting"},
                {"duration": 58, "title": "Mengapa Masalah Ini Terjadi"},
                {"duration": 55, "title": "Langkah Praktis Memperbaikinya"},
                {"duration": 50, "title": "Kesimpulan dan Hikmah"},
            ],
        },
    )

    chapters = youtube_chapters_from_sidecar(clip)
    description = append_youtube_chapters("Ringkasan video.", clip)

    assert chapters == [
        "00:00 Jawaban yang Paling Penting",
        "00:42 Mengapa Masalah Ini Terjadi",
        "01:40 Langkah Praktis Memperbaikinya",
        "02:35 Kesimpulan dan Hikmah",
    ]
    assert "BAB VIDEO:\n" in description
    assert description.endswith("02:35 Kesimpulan dan Hikmah")


def test_long_story_quality_gate_blocks_automatic_upload(monkeypatch):
    import api

    clip = ClipFile(
        name="resume_cerita_5menit_inti.mp4",
        url="/outputs/demo/resume_cerita_5menit_inti.mp4",
        size_bytes=1,
    )
    job = ClipJob(
        id="job-long-story-gate",
        status="completed",
        request=ClipJobRequest(source_file="/tmp/source.mp4", clip_mode="highlight_5m"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "production_model": "codex_long_story_director",
            "story_director": {"quality_gate_passed": False},
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""

    assert "quality gate Long Story" in issue
    assert "tiga beat unik" in issue


def test_long_animate_preflight_requires_rights_and_working_voice(monkeypatch):
    import api

    clip = ClipFile(
        name="long_animate_langkah-kecil.mp4",
        url="/outputs/demo/long_animate_langkah-kecil.mp4",
        size_bytes=1,
    )
    job = ClipJob(
        id="job-long-animate-gate",
        status="completed",
        request=ClipJobRequest(
            clip_mode="long_animate",
            script_text="Naskah orisinal yang cukup panjang untuk menghasilkan beberapa scene bermakna dan alur cerita yang utuh.",
            confirm_long_animate_rights=False,
        ),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "production_model": "codex_scene_cinema_v2",
            "one_k_long_form_readiness": {"quality_gate_passed": True},
            "story_arc": [
                {"voice_provider": "edge_neural"},
                {"voice_provider": "edge_neural"},
                {"voice_provider": "edge_neural"},
            ],
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""

    assert "pemeriksaan hak" in issue
    assert "quality gate scene" in issue


def test_long_animate_v2_preflight_requires_final_qc_and_cold_open_contract(monkeypatch):
    import api

    clip = ClipFile(
        name="long_animate_kontrak-hook.mp4",
        url="/outputs/demo/long_animate_kontrak-hook.mp4",
        size_bytes=1,
    )
    job = ClipJob(
        id="job-long-animate-v2-contract",
        status="completed",
        request=ClipJobRequest(
            clip_mode="long_animate",
            script_text="Naskah orisinal dengan cold-open, perkembangan, dan payoff yang lengkap untuk pengujian quality gate.",
            confirm_long_animate_rights=True,
        ),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    base_sidecar = {
        "production_model": "codex_scene_cinema_v2",
        "growth_readiness": {"quality_gate_passed": True},
        "story_arc": [
            {"voice_provider": "edge_neural"},
            {"voice_provider": "edge_neural"},
            {"voice_provider": "edge_neural"},
        ],
    }
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: base_sidecar)

    issue = youtube_monetization_preflight_issue(job, clip) or ""

    assert "quality gate scene" in issue

    complete_contract = {
        **base_sidecar,
        "final_qc": {"passed": True},
        "cold_open_contract": {"quality_gate_passed": True},
    }
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: complete_contract)

    issue_after_contract = youtube_monetization_preflight_issue(job, clip) or ""

    assert "quality gate scene" not in issue_after_contract


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


def test_completed_upload_cleanup_removes_orphan_workspace_when_job_is_missing(
    monkeypatch,
    tmp_path,
):
    import api

    outputs = tmp_path / "outputs"
    work_dir = outputs / "orphan-job" / "video-title"
    clip_dir = work_dir / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01.mp4"
    clip_path.write_bytes(b"video")
    clip_path.with_name("clip_01_caption.txt").write_text("caption", encoding="utf-8")
    (work_dir / "source_embedded.mp4").write_bytes(b"source")
    (work_dir / "audio_1200s.wav").write_bytes(b"audio")
    upload = YouTubeUploadJob(
        id="upload-orphan-workspace",
        source_job_id="missing-job",
        clip_url="/outputs/orphan-job/video-title/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="completed",
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:01:00+00:00",
        finished_at="2026-08-22T00:01:00+00:00",
        title="Uploaded",
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
    )
    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {})
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})

    removed, removed_job = delete_completed_youtube_upload_clip(upload.id)

    assert removed >= 3
    assert removed_job is True
    assert not (outputs / "orphan-job").exists()


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


def test_running_upload_before_file_selection_returns_to_queue(monkeypatch, tmp_path):
    import api

    upload = YouTubeUploadJob(
        id="recover-safe-upload",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="running",
        created_at="2026-08-11T01:00:00+00:00",
        updated_at="2026-08-11T01:01:00+00:00",
        started_at="2026-08-11T01:00:01+00:00",
        title="Safe recovery",
        logs=["Session YouTube belum login; menjalankan repair."],
        error="temporary error",
    )
    uploads_path = tmp_path / "youtube_uploads.json"
    uploads_path.write_text(json.dumps([upload.model_dump()]), encoding="utf-8")
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", uploads_path)

    recovered = api.load_youtube_uploads()[upload.id]

    assert recovered.status == "queued"
    assert recovered.started_at is None
    assert recovered.finished_at is None
    assert recovered.error is None
    assert "dikembalikan ke antrean" in recovered.logs[-1]


def test_legacy_restart_failure_before_file_selection_returns_to_queue(monkeypatch, tmp_path):
    import api

    upload = YouTubeUploadJob(
        id="recover-legacy-upload",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="failed",
        created_at="2026-08-11T01:00:00+00:00",
        updated_at="2026-08-11T01:01:00+00:00",
        started_at="2026-08-11T01:00:01+00:00",
        finished_at="2026-08-11T01:01:00+00:00",
        title="Legacy recovery",
        logs=["Session YouTube belum login; menjalankan repair."],
        error="Backend restarted before this YouTube upload finished",
    )
    uploads_path = tmp_path / "youtube_uploads.json"
    uploads_path.write_text(json.dumps([upload.model_dump()]), encoding="utf-8")
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", uploads_path)

    recovered = api.load_youtube_uploads()[upload.id]

    assert recovered.status == "queued"
    assert recovered.started_at is None
    assert recovered.finished_at is None
    assert recovered.error is None
    assert "upload lama" in recovered.logs[-1]


def test_running_upload_after_file_selection_is_not_retried(monkeypatch, tmp_path):
    import api

    upload = YouTubeUploadJob(
        id="recover-unsafe-upload",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="running",
        created_at="2026-08-11T01:00:00+00:00",
        updated_at="2026-08-11T01:01:00+00:00",
        started_at="2026-08-11T01:00:01+00:00",
        title="Unsafe recovery",
        logs=["Dialog upload siap.", "Video dipilih: clip_01.mp4"],
    )
    uploads_path = tmp_path / "youtube_uploads.json"
    uploads_path.write_text(json.dumps([upload.model_dump()]), encoding="utf-8")
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", uploads_path)

    recovered = api.load_youtube_uploads()[upload.id]

    assert recovered.status == "failed"
    assert recovered.finished_at is not None
    assert "mencegah video duplikat" in (recovered.error or "")


def test_upload_falls_back_to_storage_state_when_cdp_launcher_fails(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    clip_path = outputs / "demo" / "clips" / "clip_01.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"video")
    upload = YouTubeUploadJob(
        id="cdp-fallback-upload",
        source_job_id="job-1",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="queued",
        created_at="2026-08-11T01:00:00+00:00",
        updated_at="2026-08-11T01:00:00+00:00",
        title="CDP fallback",
    )
    command_modes = []

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", tmp_path / "youtube_uploads.json")
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})
    monkeypatch.setenv("YOUTUBE_UPLOAD_USE_CDP", "true")
    monkeypatch.setenv("YOUTUBE_UPLOAD_FORCE_CDP", "true")
    monkeypatch.setenv("YOUTUBE_UPLOAD_ALLOW_LAST_RESORT_FALLBACK", "true")
    monkeypatch.setattr(api, "youtube_cdp_ready", lambda: False)
    monkeypatch.setattr(api, "youtube_auth_state_exists", lambda: True)
    monkeypatch.setattr(
        api,
        "start_youtube_cdp_refresh_process",
        lambda: (_ for _ in ()).throw(HTTPException(status_code=409, detail="launcher failed")),
    )

    def fake_build_command(_upload, *, use_cdp_override=None, force_chromium_profile=False):
        command_modes.append((use_cdp_override, force_chromium_profile))
        return [sys.executable, "youtube_uploader.py", "upload", str(clip_path)]

    def fake_monitor(_process, on_line, **_kwargs):
        on_line("VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345")
        return 0, False

    monkeypatch.setattr(api, "build_youtube_upload_command", fake_build_command)
    monkeypatch.setattr(api.subprocess, "Popen", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(api, "monitor_youtube_upload_process", fake_monitor)
    monkeypatch.setattr(api, "cleanup_youtube_staging_file", lambda *_args: False)
    monkeypatch.setattr(api, "schedule_completed_upload_cleanup", lambda _upload_id: None)

    api.run_youtube_upload(upload.id)

    completed = api.youtube_uploads[upload.id]
    assert completed.status == "completed"
    assert command_modes == [(False, False)]
    assert any("dialihkan otomatis" in line for line in completed.logs)


@pytest.mark.parametrize(
    ("uploader_lines", "expected_status", "expected_confirmed"),
    [
        (
            [
                "PLAYLIST_CONFIRMED: Islam",
                "VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345",
            ],
            "completed",
            True,
        ),
        (
            ["VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345"],
            "failed",
            False,
        ),
    ],
)
def test_upload_requires_playlist_confirmation_marker(
    monkeypatch,
    tmp_path,
    uploader_lines,
    expected_status,
    expected_confirmed,
):
    import api

    clip_path = tmp_path / "outputs" / "demo" / "clip_01.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"video")
    upload = YouTubeUploadJob(
        id="playlist-confirmation-upload",
        source_job_id="job-playlist",
        clip_url="/outputs/demo/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="queued",
        created_at="2026-08-14T01:00:00+00:00",
        updated_at="2026-08-14T01:00:00+00:00",
        title="Playlist confirmation",
        playlist="Islam",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", tmp_path / "youtube_uploads.json")
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})
    monkeypatch.setattr(api, "youtube_upload_prefers_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_auth_state_exists", lambda: False)
    monkeypatch.setattr(api, "youtube_chromium_profile_ready", lambda: False)
    monkeypatch.setattr(
        api,
        "build_youtube_upload_command",
        lambda *_args, **_kwargs: [sys.executable, "youtube_uploader.py", "upload", str(clip_path)],
    )
    monkeypatch.setattr(api.subprocess, "Popen", lambda *_args, **_kwargs: object())

    def fake_monitor(_process, on_line, **_kwargs):
        for line in uploader_lines:
            on_line(line)
        return 0, False

    monkeypatch.setattr(api, "monitor_youtube_upload_process", fake_monitor)
    monkeypatch.setattr(api, "cleanup_youtube_staging_file", lambda *_args: False)
    monkeypatch.setattr(api, "schedule_completed_upload_cleanup", lambda _upload_id: None)

    api.run_youtube_upload(upload.id)

    result = api.youtube_uploads[upload.id]
    assert result.status == expected_status
    assert result.playlist_confirmed is expected_confirmed
    if expected_status == "failed":
        assert "belum mengonfirmasi playlist" in (result.error or "")


@pytest.mark.parametrize(
    ("thumbnail_line", "expected_status"),
    [
        ("THUMBNAIL_SKIPPED_DAILY_LIMIT: batas harian tercapai", "completed"),
        ("THUMBNAIL_SKIPPED: Studio tidak mengonfirmasi thumbnail", "failed"),
    ],
)
def test_long_upload_only_waives_thumbnail_requirement_for_verified_daily_limit(
    monkeypatch,
    tmp_path,
    thumbnail_line,
    expected_status,
):
    import api

    clip_path = tmp_path / "outputs" / "demo" / "resume_cerita_6menit_gaib.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"video")
    upload = YouTubeUploadJob(
        id="long-thumbnail-limit",
        source_job_id="job-long-thumbnail-limit",
        clip_url="/outputs/demo/resume_cerita_6menit_gaib.mp4",
        clip_name=clip_path.name,
        status="queued",
        created_at="2026-08-23T00:00:00+00:00",
        updated_at="2026-08-23T00:00:00+00:00",
        title="Wanita Tidak Ada di Jalan Sumatera",
        thumbnail_url="/outputs/demo/resume_cerita_6menit_gaib_thumb.jpg",
        visibility="private",
        playlist="Horor",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", tmp_path / "youtube_uploads.json")
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})
    monkeypatch.setattr(api, "youtube_upload_prefers_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_auth_state_exists", lambda: False)
    monkeypatch.setattr(api, "youtube_chromium_profile_ready", lambda: False)
    monkeypatch.setattr(
        api,
        "build_youtube_upload_command",
        lambda *_args, **_kwargs: [sys.executable, "youtube_uploader.py", "upload", str(clip_path)],
    )
    monkeypatch.setattr(api.subprocess, "Popen", lambda *_args, **_kwargs: object())

    def fake_monitor(_process, on_line, **_kwargs):
        for line in (
            thumbnail_line,
            "PLAYLIST_CONFIRMED: Horor",
            "FINAL_VISIBILITY: private",
            "VIDEO_URL: https://www.youtube.com/watch?v=abcDEF12345",
        ):
            on_line(line)
        return 0, False

    monkeypatch.setattr(api, "monitor_youtube_upload_process", fake_monitor)
    monkeypatch.setattr(api, "cleanup_youtube_staging_file", lambda *_args: False)
    monkeypatch.setattr(api, "schedule_completed_upload_cleanup", lambda _upload_id: None)

    api.run_youtube_upload(upload.id)

    result = api.youtube_uploads[upload.id]
    assert result.status == expected_status
    assert result.playlist_confirmed is True
    assert result.thumbnail_attached is False
    if expected_status == "completed":
        assert result.visibility == "private"
        assert result.error is None
    else:
        assert "thumbnail" in (result.error or "").casefold()


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


def test_youtube_graphical_process_env_uses_readable_bridge(monkeypatch, tmp_path):
    import api

    bridge_dir = tmp_path / "youtube-gui"
    bridge_dir.mkdir()
    authority_path = bridge_dir / "Xauthority"
    authority_path.write_bytes(b"desktop-cookie")
    (bridge_dir / "display").write_text(":2\n", encoding="utf-8")

    monkeypatch.setenv("YOUTUBE_GUI_BRIDGE_DIR", str(bridge_dir))
    monkeypatch.setenv("YOUTUBE_HOST_RUNTIME_DIR", str(tmp_path / "missing-runtime"))
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.setenv("XAUTHORITY", str(tmp_path / "missing-Xauthority"))

    process_env = api.youtube_graphical_process_env()

    assert process_env["DISPLAY"] == ":2"
    assert process_env["XAUTHORITY"] == str(authority_path)


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


def test_default_youtube_description_uses_natural_ai_caption_and_hashtags():
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
    assert "#islam #Shorts" in description
    assert "Untuk direnungkan:" in description
    assert "RINGKASAN" not in description
    assert "POIN PENTING" not in description
    assert "UNTUK DIDISKUSIKAN" not in description
    assert "DUKUNG CHANNEL INI" not in description
    assert not any(
        icon in description
        for icon in ("📌", "🔎", "💬", "🔥", "✅", "👍", "↗️", "🔔")
    )
    assert "📱 CHANNEL" not in description
    assert "⚠️ CATATAN KONTEN" not in description
    assert "Sumber:" not in description
    assert "Channel sumber:" not in description


def test_complete_short_description_is_concise_contextual_and_has_short_tag():
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Hikmah Menjaga Hati",
        core_message="Menjaga hati membutuhkan ilmu dan kebiasaan yang baik.",
    )
    job = ClipJob(
        id="job-short-description",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4"),
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
        clips=[clip],
    )

    description = complete_youtube_description(
        job,
        clip,
        "Pembahasan tentang cara menjaga hati dalam kehidupan sehari-hari.",
        ["Islam", "Hikmah"],
    )

    assert description.count("\n- ") == 0
    assert "Untuk direnungkan:" in description
    assert sum(
        phrase in description
        for phrase in ("Simpan video ini", "Bagikan pembahasan ini", "Ikuti channel ini")
    ) == 1
    assert "YouTube · @ryuundyofficial" not in description
    assert "#Islam #Hikmah #Shorts" in description


def test_complete_long_description_is_more_detailed_and_removes_short_tag():
    clip = ClipFile(
        name="resume_cerita_hikmah.mp4",
        url="/outputs/demo/clips/resume_cerita_hikmah.mp4",
        size_bytes=1,
        title="Perjalanan Memahami Hikmah",
    )
    job = ClipJob(
        id="job-long-description",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4", clip_mode="highlight_5m"),
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
        clips=[clip],
    )

    description = complete_youtube_description(
        job,
        clip,
        "Video panjang yang membahas konteks, proses, dan hikmah secara bertahap.",
        ["Islam", "Cerita", "Shorts"],
    )

    assert description.count("\n- ") == 3
    assert "Yang dibahas dalam video ini:" in description
    assert "#Islam #Cerita" in description
    assert "#Shorts" not in description


def test_youtube_description_keeps_fendy_audit_internal_not_public(monkeypatch):
    import api

    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Hikmah Sabar",
        social_caption="Satu pelajaran tentang sabar.\n\n#Islam #Shorts",
    )
    job = ClipJob(
        id="job-audited",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4"),
        created_at="2026-08-14T00:00:00+00:00",
        updated_at="2026-08-14T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {
            "auditor_identity": {"name": "Fendy", "audit_id": "FND-ABC123DEF456"}
        },
    )

    description = default_youtube_description(job, clip)

    assert "Audit & edit editorial otomatis" not in description
    assert "FND-ABC123DEF456" not in description


def test_legacy_crossed_sections_are_removed_when_description_is_rebuilt():
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Aturan Harta Warisan",
        core_message="Harta warisan dibagi setelah hak setiap ahli waris ditetapkan.",
    )
    job = ClipJob(
        id="job-clean-legacy-description",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4"),
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
        clips=[clip],
    )
    legacy = (
        "📌 TENTANG VIDEO INI\nRingkasan aturan pembagian harta warisan.\n\n"
        "✨ YANG AKAN KAMU DAPAT\n✅ Poin lama.\n\n"
        "📱 CHANNEL\nYouTube · @ryuundyofficial\n\n"
        "⚠️ CATATAN KONTEN\nCuplikan ini disusun ulang secara editorial.\n\n"
        "Audit & edit editorial otomatis: Fendy Clipper · ID FND-OLD."
    )

    description = complete_youtube_description(job, clip, legacy, ["HartaWaris"])

    assert "Ringkasan aturan pembagian harta warisan." in description
    assert "📱 CHANNEL" not in description
    assert "⚠️ CATATAN KONTEN" not in description
    assert "Audit & edit editorial otomatis" not in description
    assert "Bagian aturan warisan mana" in description


def test_current_plain_description_is_not_duplicated_when_rebuilt():
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Hikmah Menjaga Hati",
        core_message="Menjaga hati membutuhkan ilmu dan kebiasaan yang baik.",
    )
    job = ClipJob(
        id="job-clean-current-description",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4"),
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
        clips=[clip],
    )
    current = complete_youtube_description(
        job,
        clip,
        "Pelajaran tentang cara menjaga hati dalam kehidupan sehari-hari.",
        ["Islam", "Hikmah"],
    )

    rebuilt = complete_youtube_description(job, clip, current, ["Islam", "Hikmah"])

    assert "RINGKASAN" not in rebuilt
    assert "POIN PENTING" not in rebuilt
    assert rebuilt.count("Untuk direnungkan:") == 1
    assert rebuilt.count("Pelajaran tentang cara menjaga hati") == 1
    assert "Pelajaran tentang cara menjaga hati" in rebuilt


def test_complete_description_removes_icons_from_ai_summary():
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clips/clip_01.mp4",
        size_bytes=1,
        title="Hikmah Menjaga Hati",
    )
    job = ClipJob(
        id="job-icon-free-description",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4"),
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
        clips=[clip],
    )

    description = complete_youtube_description(
        job,
        clip,
        "💡 Pelajaran penting → menjaga hati dengan baik. 🤲",
        ["Islam", "Hikmah"],
    )

    assert "Pelajaran penting menjaga hati dengan baik." in description
    assert not any(icon in description for icon in ("💡", "→", "🤲"))


def test_performance_feedback_marks_50k_and_20_subscriber_target(monkeypatch, tmp_path):
    import api

    upload = YouTubeUploadJob(
        id="upload-growth-target",
        source_job_id="job-growth-target",
        clip_url="/outputs/demo/clips/clip_01.mp4",
        clip_name="clip_01.mp4",
        status="completed",
        created_at="2026-08-20T00:00:00+00:00",
        updated_at="2026-08-20T00:00:00+00:00",
        finished_at="2026-08-20T00:00:00+00:00",
        title="Hikmah Menjaga Hati",
        video_url="https://www.youtube.com/watch?v=demo12345",
        growth_series="Hikmah Praktis",
    )
    monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", tmp_path / "youtube_uploads.json")
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})

    updated = api.record_youtube_performance(
        upload.id,
        api.YouTubePerformanceSnapshot(
            captured_at="2026-08-22T00:00:00+00:00",
            source="youtube_analytics",
            views=50000,
            engaged_views=15000,
            average_view_duration=28.4,
            average_view_percentage=84.2,
            subscribers_gained=20,
        ),
    )

    assert updated.performance_status == "target_met"
    assert updated.performance_snapshots[-1].engaged_views == 15000
    assert "Target tercapai" in updated.performance_diagnosis[0]


def test_performance_feedback_diagnoses_conversion_gap():
    import api

    upload = YouTubeUploadJob(
        id="upload-growth-conversion",
        source_job_id="job-growth-conversion",
        clip_url="/outputs/demo/clips/clip_02.mp4",
        clip_name="clip_02.mp4",
        status="completed",
        created_at="2026-08-20T00:00:00+00:00",
        updated_at="2026-08-20T00:00:00+00:00",
        title="Hikmah Sabar",
        video_url="https://www.youtube.com/watch?v=demo67890",
        growth_series="Hikmah Praktis",
    )
    snapshot = api.YouTubePerformanceSnapshot(
        captured_at="2026-08-22T00:00:00+00:00",
        source="manual",
        views=24000,
        subscribers_gained=7,
    )

    diagnosis = api.youtube_performance_diagnosis(upload, snapshot, [upload])

    assert "konversi subscriber belum" in diagnosis[0]


def test_monetization_preflight_v6_requires_fendy_identity_and_growth_blueprint(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-audit-v6",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4"),
        created_at="2026-08-14T00:00:00+00:00",
        updated_at="2026-08-14T00:00:00+00:00",
        clips=[clip],
    )
    base_sidecar = {
        "monetization_readiness": {
            "audit_version": 6,
            "eligible_for_private_upload_review": True,
        },
    }

    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: base_sidecar)
    assert "auditor Fendy" in (youtube_monetization_preflight_issue(job, clip) or "")

    with_auditor = {
        **base_sidecar,
        "auditor_identity": {
            "name": "Fendy",
            "display_signature": "FENDY AUDIT",
            "audit_id": "FND-ABC123DEF456",
            "visible_video_signature": True,
        },
    }
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: with_auditor)
    assert "blueprint pertumbuhan Codex" in (youtube_monetization_preflight_issue(job, clip) or "")

    complete = {**with_auditor, "codex_growth_blueprint": {"version": 1}}
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: complete)
    assert youtube_monetization_preflight_issue(job, clip) is None


def test_verified_cc_source_gets_required_attribution(monkeypatch):
    import api

    job = ClipJob(
        id="job-cc",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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


def test_monetization_preflight_requires_explicit_url_rights_confirmation(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-unconfirmed-url-rights",
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

    issue = youtube_monetization_preflight_issue(job, clip) or ""

    assert "bukan bukti" in issue
    assert "hak audio dan visual" in issue


def test_monetization_preflight_blocks_high_risk_tv_reupload_even_when_confirmed(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-claimed-tv-source",
        status="completed",
        request=ClipJobRequest(
            url="https://youtu.be/source",
            confirm_source_rights=True,
        ),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[clip],
    )
    monkeypatch.setattr(
        api,
        "metadata_for_job",
        lambda _job: {
            "license": "Creative Commons Attribution license",
            "title": "Sintya Marisca - Islam Itu Indah 7 Feb 2k20",
            "uploader": "Sintya Marisca Support",
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""

    assert "berisiko tinggi terkena Content ID" in issue
    assert "Label CC" in issue


def test_monetization_preflight_blocks_short_outside_official_technical_limits(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-invalid-short",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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
            "score": 90,
            "aspect_ratio": "9:16",
            "duration": 181,
            "thumbnail_strategy": "embedded_shorts_cover_frame",
            "monetization_readiness": {"eligible_for_private_upload_review": True},
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""
    assert "181.0 detik" in issue
    assert "180 detik" in issue


def test_monetization_preflight_blocks_low_fyp_short(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-low-fyp-short",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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
            "score": 58,
            "monetization_readiness": {"eligible_for_private_upload_review": True},
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""
    assert "58/78" in issue
    assert "auto-repair" in issue


def test_monetization_preflight_blocks_short_with_low_retention_readiness(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-low-retention-short",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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
            "score": 91,
            "retention_score": 47,
            "monetization_readiness": {"eligible_for_private_upload_review": True},
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""
    assert "retention 30 detik 47/58" in issue
    assert "perkembangan beat" in issue


def test_monetization_preflight_accepts_legacy_compilation_story_arc(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-legacy-compilation",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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


def test_monetization_preflight_v5_requires_chapter_specific_framing(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-template-compilation",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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
                "audit_version": 5,
                "signals": {
                    "enhanced_edit": True,
                    "cohesive_editorial_arc": True,
                    "content_timed_editing": True,
                    "content_adaptive_visual_direction": True,
                    "structured_story_arc": True,
                    "chapter_specific_editorial_framing": False,
                },
            },
        },
    )

    issue = youtube_monetization_preflight_issue(job, clip) or ""
    assert "framing editorial" in issue
    assert "setiap bab" in issue


def test_monetization_preflight_explains_when_enhanced_edit_is_actually_missing(monkeypatch):
    import api

    clip = make_clip(1)
    job = ClipJob(
        id="job-no-enhanced-edit",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/source", confirm_source_rights=True),
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
            "score": 90,
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
    monkeypatch.setattr(
        api,
        "clip_sidecar_payload",
        lambda _clip: {"thumbnail_headline": "Salah Langkah, Salah Pandang"},
    )

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
        assert "Headline frame cover yang sudah tertanam: Salah Langkah, Salah Pandang" in messages[-1]["content"]
        assert "Selaraskan title dengan headline frame cover" in messages[-1]["content"]
        return '{"title": "Nasihat Singkat Tentang Asef", "description": "Klip ini menjelaskan nasihat penting dengan konteks yang mudah dipahami. Simak poin utamanya agar pesan yang disampaikan dapat diterapkan dengan tepat.", "hashtags": ["#islam", "#nasihat", "#hikmah", "#shorts"]}'

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    assert generate_youtube_description(job, clip, ["islam", "shorts"]) == (
        "Nasihat penting dengan konteks yang mudah dipahami. Simak poin utamanya agar pesan yang disampaikan dapat diterapkan dengan tepat.\n\n#islam #nasihat #hikmah #shorts"
    )

    assert generate_youtube_metadata(job, clip, ["islam", "shorts"]) == {
        "title": "Nasihat Singkat Tentang Asef #Shorts",
        "description": "Nasihat penting dengan konteks yang mudah dipahami. Simak poin utamanya agar pesan yang disampaikan dapat diterapkan dengan tepat.\n\n#islam #nasihat #hikmah #shorts",
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
            "Bagaimana kesabaran menjaga hati ketika ujian datang. "
            "Pesannya mengajak penonton memahami hikmah tanpa mengabaikan proses yang berat."
            "\n\n#Sabar #UjianHidup #HikmahIslam #Shorts"
        ),
        "hashtags": ["Sabar", "UjianHidup", "HikmahIslam", "Shorts"],
    }


def test_normalized_metadata_removes_generic_title_tail_and_english_leak():
    payload = {
        "title": (
            "Harta Waris Belum Dibagi, Bolehkah Disedekahkan? "
            "Penjelasan Lengkap"
        ),
        "description": (
            "Harta waris yang belum dibagi masih memuat hak para ahli waris. "
            "Setelah menerima bagiannya, setiap ahli waris dapat bersedekah tanpa restriction."
        ),
        "hashtags": ["#HartaWaris", "#HakAhliWaris", "#Sedekah", "#Shorts"],
    }

    result = normalized_generated_metadata(payload, is_compilation=False)

    assert result is not None
    assert result["title"] == "Harta Waris Belum Dibagi, Bolehkah Disedekahkan? #Shorts"
    assert len(str(result["title"])) <= 78
    assert "restriction" not in str(result["description"])
    assert "tanpa batasan" in str(result["description"])
