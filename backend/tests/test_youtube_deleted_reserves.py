from types import SimpleNamespace
import json
import sys
import types

import pytest

import api
import youtube_remote_status as remote
from youtube_remote_status import uploader_deleted_video, read_deleted_video_evidence


def response(message, status="ERROR"):
    return {"playabilityStatus": {"status": status, "errorScreen": {
        "playerInterstitialRenderer": {"content": {"interstitialViewModel": {
            "description": {"content": message},
        }}},
    }}}


@pytest.mark.parametrize("message", [
    "Video ini telah dihapus oleh uploader", "This video has been removed by the uploader",
])
def test_explicit_uploader_deletion_is_positive_evidence(message):
    assert uploader_deleted_video(response(message)) == message


@pytest.mark.parametrize("message", [
    "Video tidak tersedia", "This video is private", "Sign in to confirm your age",
    "This video contains content from a copyright owner", "Network timeout",
])
def test_unavailability_privacy_claims_and_timeouts_do_not_release_reserves(message):
    assert uploader_deleted_video(response(message)) is None


def test_successful_video_is_not_considered_deleted():
    assert uploader_deleted_video(response("This video has been removed by the uploader", "OK")) is None


@pytest.fixture
def reserve(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CRON_BUFFER_ENABLED", "true")
    monkeypatch.setenv("YOUTUBE_AUTO_SCHEDULE_ENABLED", "true")
    monkeypatch.setattr(api, "youtube_reserve_deletion_checks", {})
    upload = api.YouTubeUploadJob(
        id="old-reserve", source_job_id="old-job", clip_url="/outputs/old-job/clip.mp4",
        clip_name="clip.mp4", title="Existing video", status="failed",
        created_at="2026-11-03T00:00:00+00:00", updated_at="2026-11-04T00:00:00+00:00",
        video_url="https://www.youtube.com/watch?v=wGJD-V4ae_0",
        visibility="private", cron_private_buffer=True,
    )
    monkeypatch.setattr(api, "youtube_uploads", {upload.id: upload})
    return upload


def test_confirmed_deleted_reserve_releases_capacity_without_reupload(reserve, monkeypatch):
    monkeypatch.setattr(api, "read_deleted_video_evidence", lambda *_: {
        "video_id": "wGJD-V4ae_0", "deleted_by_uploader": True,
        "reason": "Video ini telah dihapus oleh uploader",
    })
    assert api.youtube_cron_private_buffer_count() == 1
    assert api.reconcile_deleted_youtube_reserves_once() == 1
    retired = api.youtube_uploads[reserve.id]
    assert retired.status == "cancelled"
    assert retired.video_url == reserve.video_url
    assert retired.cron_private_buffer is False
    assert api.youtube_cron_private_buffer_count() == 0
    assert retired.logs[-1].startswith("REMOTE_VIDEO_DELETED_CONFIRMED:")
    assert not api.completed_job_upload_retry_ready(
        [retired], retired.source_job_id, retired.clip_url,
        allow_released_youtube_verification=True,
    )


@pytest.mark.parametrize("proof", [None, {}, {"video_id": "different01", "deleted_by_uploader": True}, {"video_id": "wGJD-V4ae_0", "deleted_by_uploader": False}])
def test_unknown_or_wrong_video_proof_retains_capacity(reserve, monkeypatch, proof):
    monkeypatch.setattr(api, "read_deleted_video_evidence", lambda *_: proof)
    assert api.reconcile_deleted_youtube_reserves_once() == 0
    assert api.youtube_cron_private_buffer_count() == 1
    assert api.youtube_uploads[reserve.id].status == "failed"


def test_active_upload_prevents_background_browser_check(reserve, monkeypatch):
    active = reserve.model_copy(update={"id": "active", "status": "running"})
    api.youtube_uploads[active.id] = active
    monkeypatch.setattr(api, "read_deleted_video_evidence", lambda *_: pytest.fail("must not inspect during active upload"))
    assert api.reconcile_deleted_youtube_reserves_once() == 0


def test_unknown_reserve_check_has_cooldown(reserve, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "read_deleted_video_evidence", lambda *args: calls.append(args))
    api.reconcile_deleted_youtube_reserves_once()
    api.reconcile_deleted_youtube_reserves_once()
    assert len(calls) == 1


@pytest.fixture
def http_watch(monkeypatch):
    watch = SimpleNamespace(
        url="https://www.youtube.com/watch?v=wGJD-V4ae_0",
        status=200, body="", requests=[],
    )
    class Result:
        status = property(lambda self: watch.status)
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def geturl(self): return watch.url
        def read(self, size): return watch.body.encode()[:size]
    def build_opener(processor):
        watch.jar = processor.cookiejar
        def open_request(request, **kwargs):
            watch.requests.append(request)
            return Result()
        return SimpleNamespace(open=open_request)
    monkeypatch.setattr(remote, "build_opener", build_opener)
    watch.body = '<script>var ytInitialPlayerResponse = ' + json.dumps(response(
        "Video ini telah dihapus oleh uploader")) + ';</script>'
    return watch


def test_read_only_check_uses_cookie_snapshot_without_opening_or_closing_tabs(monkeypatch, http_watch):
    cookie = dict(name="SID", value="test-session", domain=".youtube.com", path="/", secure=True, expires=-1)
    context = SimpleNamespace(
        cookies=lambda urls: [cookie],
        new_page=lambda: pytest.fail("background checks must never create tabs"),
        close=lambda: pytest.fail("borrowed context must stay open"),
    )
    browser = SimpleNamespace(contexts=[context], close=lambda: pytest.fail("borrowed browser must stay open"))
    class Playwright:
        def __enter__(self): return SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=lambda *_args, **_kwargs: browser))
        def __exit__(self, *_args): pass
    parent = types.ModuleType("playwright")
    parent.__path__ = []
    child = types.ModuleType("playwright.sync_api")
    child.sync_playwright = Playwright
    monkeypatch.setitem(sys.modules, "playwright", parent)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", child)
    proof = read_deleted_video_evidence("wGJD-V4ae_0", "http://127.0.0.1:9333")
    assert proof["deleted_by_uploader"] is True
    assert len(http_watch.requests) == 1
    copied_cookie = next(iter(http_watch.jar))
    copied_cookie.value = "response-cookie-change"
    assert cookie["value"] == "test-session"


@pytest.mark.parametrize("url", [
    "https://accounts.google.com/ServiceLogin?v=wGJD-V4ae_0",
    "https://consent.youtube.com/watch?v=wGJD-V4ae_0",
    "https://www.youtube.com/watch?v=different01",
    "https://www.youtube.com/watch?v=wGJD-V4ae_0&v=different01",
])
def test_http_redirect_or_wrong_id_never_releases_reserve(http_watch, url):
    http_watch.url = url
    assert read_deleted_video_evidence("wGJD-V4ae_0", "unused", context=SimpleNamespace(cookies=lambda urls: [])) is None


@pytest.mark.parametrize("body", [
    '<script>var ytInitialPlayerResponse = {};</script>',
    '<script>var ytInitialPlayerResponse = invalid;</script>',
    '<p>This video has been removed by the uploader</p>',
    '<script>var ytInitialPlayerResponse = {"playabilityStatus":{"status":"OK"}};</script>',
    '<script>var ytInitialPlayerResponse = {"playabilityStatus":{"status":"ERROR","errorScreen":{"reason":"This video is private"}}};</script>',
])
def test_unknown_or_private_html_is_not_deletion_evidence(http_watch, body):
    http_watch.body = body
    assert read_deleted_video_evidence("wGJD-V4ae_0", "unused", context=SimpleNamespace(cookies=lambda urls: [])) is None


def test_player_id_mismatch_rejects_deletion_text(http_watch):
    data = response("This video has been removed by the uploader")
    data["videoDetails"] = {"videoId": "different01"}
    http_watch.body = '<script>window["ytInitialPlayerResponse"] = ' + json.dumps(data) + ';</script>'
    assert read_deleted_video_evidence("wGJD-V4ae_0", "unused", context=SimpleNamespace(cookies=lambda urls: [])) is None


def test_window_assignment_returns_exact_video_evidence(http_watch):
    http_watch.body = http_watch.body.replace('var ytInitialPlayerResponse', 'window["ytInitialPlayerResponse"]')
    proof = read_deleted_video_evidence("wGJD-V4ae_0", "unused", context=SimpleNamespace(cookies=lambda urls: []))
    assert proof["video_id"] == "wGJD-V4ae_0"


def test_network_failure_does_not_touch_tabs(monkeypatch):
    def unavailable(*args, **kwargs): raise TimeoutError("offline")
    monkeypatch.setattr(remote, "build_opener", lambda *args: SimpleNamespace(open=unavailable))
    with pytest.raises(TimeoutError):
        read_deleted_video_evidence("wGJD-V4ae_0", "unused", context=SimpleNamespace(cookies=lambda urls: []))


def test_upload_operator_survives_one_failed_cycle(monkeypatch):
    waits, attempts = [], []
    original_env_bool = api.env_bool
    monkeypatch.setattr(api, "env_bool", lambda key, default=False: len(waits) < 2 if key == "AUTO_UPLOAD_COMPLETED_JOBS" else original_env_bool(key, default))
    monkeypatch.setattr(api, "reconcile_deleted_youtube_reserves_once", lambda: 0)
    def process():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("temporary upload state failure")
    monkeypatch.setattr(api, "queue_completed_job_uploads_once", process)
    monkeypatch.setattr(api, "completed_job_upload_sweeper_wakeup", SimpleNamespace(wait=lambda **kwargs: waits.append(kwargs), clear=lambda: None))
    api.completed_job_upload_sweeper_loop()
    assert len(attempts) == 2
    assert len(waits) == 2
    assert api.completed_job_upload_sweeper_running is False
