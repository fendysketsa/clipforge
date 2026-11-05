from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

import youtube_blocked_cleanup as cleanup
import youtube_uploader


@pytest.mark.parametrize("label", ["Blocked", "Diblokir", "Blocked worldwide", "Diblokir di seluruh dunia"])
def test_only_explicit_block_status_authorizes_deletion(label):
    assert cleanup.fully_blocked({"video_id": "abcDEF12345", "visibility": label})


@pytest.mark.parametrize("row", [
    {"title": "Diblokir", "visibility": "Publik", "restrictions": "Hak cipta"},
    {"visibility": "Publik", "restrictions": "Potensi pembatasan penghasilan"},
    {"visibility": "Publik", "restrictions": "Copyright claim"},
    {"visibility": "Blocked", "restrictions": "Blocked in some countries"},
    {"visibility": "Diblokir", "restrictions": "Diblokir sebagian"},
    {"visibility": "Private", "restrictions": "Blocked"},
    {"visibility": "Pribadi", "restrictions": "Diblokir"},
    {"visibility": "Dijadwalkan", "restrictions": "Diblokir"},
    {"visibility": "Scheduled", "restrictions": "Blocked"},
    {"visibility": "Draft", "restrictions": "Blocked"},
    {"visibility": "Not blocked"},
    {"video_id": "wrong-id", "visibility": "Blocked"},
])
def test_unrelated_partial_and_protected_videos_are_preserved(row):
    assert not cleanup.fully_blocked(dict({"video_id": "abcDEF12345"}, **row))


def test_queue_check_fails_closed_if_api_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(cleanup.urllib.request, "urlopen", unavailable)
    with pytest.raises(OSError, match="offline"):
        cleanup.uploads_busy()


@pytest.mark.parametrize("exists,disabled", [(False, None), (True, None)])
def test_unknown_pagination_cannot_be_treated_as_last_page(exists, disabled):
    button = SimpleNamespace(count=lambda: int(exists), get_attribute=lambda name: disabled)
    button.first = button
    page = SimpleNamespace(locator=lambda selector: button)
    with pytest.raises(RuntimeError, match="incomplete"):
        cleanup.next_page(page, [{"video_id": "abcDEF12345"}])


def test_final_recheck_veto_prevents_irreversible_button(monkeypatch):
    page = SimpleNamespace(goto=lambda *a, **kw: None, wait_for_load_state=lambda *a, **kw: None)
    clicks = []
    monkeypatch.setattr(youtube_uploader, "ensure_logged_in", lambda page: None)
    monkeypatch.setattr(youtube_uploader, "deep_click", lambda *a, **kw: clicks.append(kw) or True)
    with pytest.raises(youtube_uploader.UploadError, match="dibatalkan"):
        youtube_uploader.discard_studio_video(
            page, "https://www.youtube.com/watch?v=abcDEF12345", before_confirm=lambda video_id: False
        )
    assert len(clicks) == 3  # menu, delete dialog, acknowledgement; no final delete


def test_remote_confirmation_reuses_the_open_playwright_context(monkeypatch):
    import playwright.sync_api as pw_api
    import youtube_remote_status
    monkeypatch.setattr(pw_api, "sync_playwright", lambda: pytest.fail("must not nest sync Playwright"))
    context = SimpleNamespace(new_page=lambda: pytest.fail("must not open a verification tab"))
    def fetch(existing_context, video_id):
        assert existing_context is context
        assert video_id == "abcDEF12345"
        return {"playabilityStatus": {"status": "ERROR", "errorScreen": {"reason": "This video has been removed by the uploader"}}}
    monkeypatch.setattr(youtube_remote_status, "_fetch_player_response", fetch)
    proof = youtube_remote_status.read_deleted_video_evidence(
        "abcDEF12345", "http://127.0.0.1:9333", context=context
    )
    assert proof["deleted_by_uploader"]


@pytest.mark.parametrize("changed_status,proof,expected,scan_fails", [
    (False, {"video_id": "abcDEF12345", "deleted_by_uploader": True}, "deleted_verified", False),
    (True, {"video_id": "abcDEF12345", "deleted_by_uploader": True}, "held", False),
    (False, None, "delete_confirmation_pending", False),
    (False, {"video_id": "wrongID1234", "deleted_by_uploader": True}, "delete_confirmation_pending", False),
    (False, None, "held", True),
])
def test_worker_revalidates_and_requires_exact_remote_deletion_proof(monkeypatch, tmp_path, changed_status, proof, expected, scan_fails):
    import playwright.sync_api as pw_api
    import youtube_remote_status

    class Page:
        url = "https://studio.youtube.com/video/abcDEF12345/edit"
        closed = False
        def evaluate(self, *args):
            return None
        def is_closed(self):
            return self.closed
        def close(self):
            self.closed = True
        def locator(self, *args):
            return SimpleNamespace(count=lambda: 1)

    original = Page()
    pages = [original]
    def new_page():
        page = Page()
        pages.append(page)
        return page
    # No browser/context.close method: closing a borrowed session fails the test.
    context = SimpleNamespace(pages=pages, new_page=new_page)
    browser = SimpleNamespace(contexts=[context])
    @contextmanager
    def playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=lambda *a, **kw: browser))
    monkeypatch.setattr(pw_api, "sync_playwright", playwright)
    monkeypatch.setattr(cleanup, "uploads_busy", lambda *a: False)
    monkeypatch.setattr(cleanup, "require_channel", lambda *a: None)
    monkeypatch.setattr(cleanup, "next_page", lambda *a: False)
    count = 0
    def rows(*args):
        nonlocal count
        count += 1
        if scan_fails and count == 3:
            raise RuntimeError("last bucket unavailable")
        return [{"video_id": "abcDEF12345", "title": "Video", "visibility": "Public",
                 "restrictions": "Copyright claim" if changed_status and count > 3 else "Blocked"}]
    monkeypatch.setattr(cleanup, "open_bucket", rows)
    deletions = []
    def discard(page, url, *, before_confirm, **kwargs):
        if not before_confirm("abcDEF12345"):
            raise youtube_uploader.UploadError("fresh evidence rejected")
        deletions.append(url)
        return True
    monkeypatch.setattr(youtube_uploader, "discard_studio_video", discard)
    monkeypatch.setattr(youtube_remote_status, "read_deleted_video_evidence", lambda *a, **kw: proof)
    report = cleanup.run({"YOUTUBE_TARGET_CHANNEL_ID": "UC" + "x" * 22, "YOUTUBE_CDP_URL": "http://127.0.0.1:9333"}, apply=True, force=True, data_dir=tmp_path)
    assert not original.closed
    assert all(p.closed for p in pages[1:])
    if scan_fails:
        assert report["status"] == "held"
        assert not report["scan_complete"]
        assert not report["actions"]
        assert not deletions
        return
    assert report["scan_complete"]
    assert report["actions"][0]["status"] == expected
    assert bool(deletions) is not changed_status
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["videos"]["abcDEF12345"]["status"] == expected
