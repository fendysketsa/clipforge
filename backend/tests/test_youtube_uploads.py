from api import (
    ClipCandidate,
    ClipFile,
    ClipJob,
    ClipJobRequest,
    YouTubeUploadJob,
    best_youtube_clip_urls,
    default_youtube_description,
    default_youtube_tags,
    default_youtube_title,
    generate_youtube_description,
    generate_youtube_metadata,
    delete_all_job_clips,
    start_youtube_cdp_refresh_process,
    sync_youtube_cdp,
    youtube_video_url_from_logs,
)
from youtube_uploader import normalized_upload_metadata, studio_start_url


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
        assert "Judul clip: Judul Clip" in messages[-1]["content"]
        return '{"title": "Nasihat Singkat Tentang Asef", "description": "Ini deskripsi baru dari AI.", "hashtags": ["#islam", "#shorts"]}'

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    assert generate_youtube_description(job, clip, ["islam", "shorts"]) == (
        "Ini deskripsi baru dari AI.\n\n#islam #shorts"
    )

    assert generate_youtube_metadata(job, clip, ["islam", "shorts"]) == {
        "title": "Nasihat Singkat Tentang Asef #Shorts",
        "description": "Ini deskripsi baru dari AI.\n\n#islam #shorts",
        "hashtags": ["islam", "shorts"],
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
        lambda config, messages: '{"judul": "Pelajaran Rezeki Hari Ini", "deskripsi": "Renungan singkat tentang rezeki dan rasa syukur.", "tagar": "#rezeki #syukur #islam"}',
    )

    assert generate_youtube_metadata(job, clip, ["islam", "shorts"]) == {
        "title": "Pelajaran Rezeki Hari Ini #Shorts",
        "description": "Renungan singkat tentang rezeki dan rasa syukur.\n\n#rezeki #syukur #islam",
        "hashtags": ["rezeki", "syukur", "islam"],
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
        return '{"title": "Nasihat Baru", "description": "Deskripsi baru dari fallback.", "hashtags": ["#nasihat", "#islam"]}'

    monkeypatch.setattr(api, "chat_completion", fake_chat_completion)

    assert generate_youtube_metadata(job, clip, ["islam"]) == {
        "title": "Nasihat Baru #Shorts",
        "description": "Deskripsi baru dari fallback.\n\n#nasihat #islam",
        "hashtags": ["nasihat", "islam"],
    }
