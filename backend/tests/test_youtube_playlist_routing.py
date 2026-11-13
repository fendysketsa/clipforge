import pytest

from youtube_playlists import classify_youtube_playlist


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Yuta dikejar hantu di Roblox sambil berkata ya Allah", "Gaming"),
        ("Momon menjadi monster Animal Hospital di MINECRAFT", "Gaming"),
        ("Ustadz menjelaskan hikmah sedekah", "Islam"),
        ("Pak Kasja menjelaskan agama di Baduy dan Nabi Adam", "Islam"),
        ("Legenda asal-usul Putri di istana angker", "Legenda"),
        ("Cerita rakyat tentang hantu penunggu desa", "Cerita Rakyat"),
        ("Penampakan pocong di rumah kosong", "Horor"),
        ("Eksperimen fisika sederhana", "Sains"),
        ("Tutorial cara membuat meja", "Tips"),
        ("Mengenal tradisi dan budaya Baduy", "Adat"),
        ("Percakapan lucu dengan punchline tak terduga", "Lucu"),
        ("Bangkit setelah kehilangan pekerjaan", "Inspiratif"),
        ("Renungan untuk diri sendiri", "Renungan"),
        ("Nasihat tentang keluarga", "Hikmah dan Nasihat"),
        ("Bagaimana Sulaiman mengubah permainan?", "Everythings"),
        ("Ia beriman pada kemampuannya", "Everythings"),
        ("Kabar terbaru sepak bola", "Everythings"),
        ("", "Everythings"),
        ("Review dracin: ustadz menasihati keluarga", "Drama China"),
        ("Ulasan drama Korea tentang pengkhianatan", "Drama Korea"),
        ("Yuta dikejar hantu di Sakura School Simulator", "Gaming"),
    ],
)
def test_topic_routing(text, expected):
    assert classify_youtube_playlist(text) == expected


@pytest.mark.parametrize("theme,expected", [
    ("chinese_drama_story", "Drama China"),
    ("korean_drama_story", "Drama Korea"),
    ("family_conflict", "Keluarga dan Rumah Tangga"),
    ("gaming_story", "Gaming"),
    ("podcast_conversation", "Podcast"),
    ("news_hot", "News"),
    ("history_geography_nusantara", "Sejarah, Geografi & Budaya Nusantara"),
])
def test_durable_cron_niche_does_not_depend_on_words_in_dialogue(theme, expected):
    assert classify_youtube_playlist("Ustadz menasihati tokoh", theme_key=theme) == expected


@pytest.fixture
def upload_context(monkeypatch, tmp_path):
    import api

    video = tmp_path / "clip_01.mp4"
    video.write_bytes(b"test video")
    clip = api.ClipFile(
        name=video.name, url="/outputs/test/clip_01.mp4", size_bytes=10,
        title="Boleh meminta kopi?", is_correct=True,
    )
    job = api.ClipJob(
        id="playlist-test", status="completed",
        request=api.ClipJobRequest(source_file="owned.mp4"),
        source_title="Momon menjadi monster di Minecraft",
        created_at="2026-11-03T00:00:00+00:00",
        updated_at="2026-11-03T00:00:00+00:00", clips=[clip],
    )
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "youtube_uploads", {})
    monkeypatch.setattr(api, "output_path_from_url", lambda url: video if url == clip.url else None)
    monkeypatch.setattr(api, "upload_media_duration_issue", lambda _path: None)
    monkeypatch.setattr(api, "prepare_limited_upload_file", lambda path, _limit: path)
    monkeypatch.setattr(api, "media_duration_seconds", lambda _path: 30.0)
    monkeypatch.setattr(api, "youtube_upload_prefers_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_profile_upload_allowed", lambda: False)
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *_args: None)
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: {"text": "Boleh meminta kopi?"})
    monkeypatch.setattr(api, "youtube_upload_metadata", lambda *_args: (
        {"title": "Boleh Meminta Kopi di Hospital?", "description": "Percakapan pemain. #Islam",
         "hashtags": ["Minecraft", "Gaming", "Shorts"]}, "test"
    ))
    monkeypatch.setenv("YOUTUBE_REQUIRE_AI_METADATA", "true")
    monkeypatch.delenv("YOUTUBE_AUTO_PLAYLIST", raising=False)
    return api, job, clip


@pytest.mark.parametrize("scheduled", [False, True])
def test_manual_and_cron_uploads_override_stale_islam_default(upload_context, scheduled):
    api, job, clip = upload_context
    job.request.scheduled_public_source_credit = scheduled
    upload = api.create_youtube_upload_record(
        job.id, api.YouTubeUploadRequest(clip_url=clip.url, playlist="Islam", visibility="private")
    )
    assert upload.playlist == "Gaming"
    assert any("Playlist dipilih otomatis" in line for line in upload.logs)
    command = api.build_youtube_upload_command(upload)
    assert command[command.index("--playlist") + 1] == "Gaming"
    assert "--playlist-resolved" in command


def test_can_use_requested_playlist_when_automatic_routing_is_disabled(upload_context, monkeypatch):
    api, job, clip = upload_context
    monkeypatch.setenv("YOUTUBE_AUTO_PLAYLIST", "false")
    upload = api.create_youtube_upload_record(
        job.id, api.YouTubeUploadRequest(clip_url=clip.url, playlist="Lucu", visibility="private")
    )
    assert upload.playlist == "Lucu"


@pytest.mark.parametrize("automatic", ["true", "false"])
def test_news_series_routes_to_news_even_with_stale_default(upload_context, monkeypatch, automatic):
    api, job, clip = upload_context
    job.request.scheduled_news_hot = True
    monkeypatch.setenv("YOUTUBE_AUTO_PLAYLIST", automatic)
    upload = api.create_youtube_upload_record(
        job.id, api.YouTubeUploadRequest(clip_url=clip.url, playlist="Islam", visibility="private")
    )
    assert upload.playlist == "News"
    assert "Seri: News Hot RYUUNDY" in upload.description


def test_long_video_uses_gaming_rather_than_folklore_default(upload_context):
    api, job, clip = upload_context
    job.request.clip_mode = "highlight_5m"
    assert api.automatic_long_form_playlist(job, clip, "Petualangan Momon", "#Islam") == "Gaming"


def test_short_and_long_use_persisted_niche_when_title_is_generic(upload_context):
    api, job, clip = upload_context
    job.request.scheduled_theme_key = "chinese_drama_story"
    job = api.ClipJob.model_validate(job.model_dump())
    assert api.automatic_youtube_playlist(job, clip) == "Drama China"
    assert api.automatic_long_form_playlist(job, clip, "Satu keputusan", "") == "Drama China"


def test_history_niche_survives_generic_short_and_long_titles(upload_context):
    api, job, clip = upload_context
    job.request.scheduled_theme_key = "history_geography_nusantara"
    assert api.automatic_youtube_playlist(job, clip) == "Sejarah, Geografi & Budaya Nusantara"
    assert api.automatic_long_form_playlist(job, clip, "Mengapa demikian?", "") == "Sejarah, Geografi & Budaya Nusantara"


@pytest.mark.parametrize("scheduled", [False, True])
def test_only_cron_persists_playlist_creation_permission_and_cli_flag(upload_context, scheduled):
    api, job, clip = upload_context
    job.request.scheduled_public_source_credit = scheduled
    upload = api.create_youtube_upload_record(job.id, api.YouTubeUploadRequest(clip_url=clip.url))
    restored = api.YouTubeUploadJob.model_validate(upload.model_dump())
    assert restored.cron_create_missing_playlist is scheduled
    assert ("--create-missing-playlist" in api.build_youtube_upload_command(restored)) is scheduled
    # A cleaned source job cannot remove the durable cron permission.
    api.jobs.clear()
    assert ("--create-missing-playlist" in api.build_youtube_upload_command(restored)) is scheduled


def test_old_cron_queue_record_inherits_permission_only_from_actual_cron_source(upload_context):
    api, job, clip = upload_context
    upload = api.create_youtube_upload_record(job.id, api.YouTubeUploadRequest(clip_url=clip.url))
    assert not upload.cron_create_missing_playlist
    job.request.scheduled_public_source_credit = True
    assert "--create-missing-playlist" in api.build_youtube_upload_command(upload)


def test_clip_transcript_routes_generic_title_without_caption_boilerplate(upload_context, monkeypatch):
    api, job, clip = upload_context
    job.source_title = "Percakapan sore"
    clip.title = "Satu hal yang perlu dipahami"
    clip.social_caption = "#Islam #Dakwah"
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _clip: {"text": "Eksperimen fisika dan sains."})
    assert api.automatic_youtube_playlist(job, clip) == "Sains"


def test_execution_routes_old_queue_records_from_source_folder(tmp_path, monkeypatch):
    from youtube_uploader import upload_playlist_for_video

    monkeypatch.delenv("YOUTUBE_AUTO_PLAYLIST", raising=False)
    video = tmp_path / "momon-di-minecraft" / "clips" / "clip_01_kopi.mp4"
    assert upload_playlist_for_video(video, "Boleh meminta kopi?", "Islam") == "Gaming"


def test_execution_uses_sidecar_and_ignores_malformed_sidecars(tmp_path, monkeypatch):
    import json
    from youtube_uploader import upload_playlist_for_video

    monkeypatch.delenv("YOUTUBE_AUTO_PLAYLIST", raising=False)
    video = tmp_path / "clip_01.mp4"
    video.with_suffix(".json").write_text(json.dumps({"text": "Ustadz menjelaskan sedekah."}))
    assert upload_playlist_for_video(video, "Pesan untuk kita", "") == "Islam"
    video.with_suffix(".json").write_text("[invalid")
    assert upload_playlist_for_video(video, "Pesan untuk kita", "") == "Everythings"


def test_execution_preserves_manual_choice_when_disabled(tmp_path, monkeypatch):
    from youtube_uploader import upload_playlist_for_video

    monkeypatch.setenv("YOUTUBE_AUTO_PLAYLIST", "false")
    assert upload_playlist_for_video(tmp_path / "minecraft.mp4", "Roblox", "Lucu") == "Lucu"


def test_cron_full_schedule_uses_private_reserve(upload_context, monkeypatch):
    api, job, clip = upload_context
    job.request.scheduled_public_source_credit = True
    monkeypatch.setenv("YOUTUBE_CRON_BUFFER_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", "true")
    monkeypatch.setattr(api, "youtube_scheduled_backlog_count", lambda **_kwargs: 11)
    monkeypatch.setattr(api, "youtube_schedule_backlog_limit", lambda: 11)
    monkeypatch.setattr(api, "youtube_cron_private_buffer_count", lambda: 4)
    upload = api.create_youtube_upload_record(
        job.id, api.YouTubeUploadRequest(clip_url=clip.url, visibility="public")
    )
    assert upload.visibility == "private"
    assert upload.publish_at is None
    assert upload.cron_private_buffer is True


def test_cron_full_private_and_schedule_waits_instead_of_uploading(upload_context, monkeypatch):
    api, job, clip = upload_context
    job.request.scheduled_public_source_credit = True
    monkeypatch.setenv("YOUTUBE_CRON_BUFFER_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", "true")
    monkeypatch.setattr(api, "youtube_scheduled_backlog_count", lambda **_kwargs: 11)
    monkeypatch.setattr(api, "youtube_schedule_backlog_limit", lambda: 11)
    monkeypatch.setattr(api, "youtube_cron_private_buffer_count", lambda: 5)
    with pytest.raises(api.YouTubeCronCapacityReached):
        api.create_youtube_upload_record(job.id, api.YouTubeUploadRequest(clip_url=clip.url, visibility="public"))
