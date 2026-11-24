"""Network recovery never replays file transfer or a possibly submitted Post."""
import pytest
import automatic_retry as retry
import tiktok_uploader as uploader

PROFILE = 'https://www.tiktok.com/@titikbalikislami'
ERROR = f'TikTok tidak dapat dibuka: Page.goto: net::ERR_ADDRESS_UNREACHABLE at {PROFILE}'


class Page:
    def __init__(self, failures, url='about:blank'):
        self.failures = failures
        self.url = url
        self.calls = []
        self.delays = []

    def goto(self, url, **kwargs):
        self.calls.append(url)
        if self.failures:
            self.failures -= 1
            raise RuntimeError(f'Page.goto: net::ERR_ADDRESS_UNREACHABLE at {url}')
        self.url = url

    def wait_for_timeout(self, delay):
        self.delays.append(delay)


def test_navigation_recovers_without_touching_file_or_post():
    page = Page(2)
    uploader.goto(page, PROFILE)
    assert page.calls == [PROFILE] * 3
    assert page.delays == [1000, 3000]
    assert page.url == PROFILE


def test_transport_failure_is_bounded_even_if_old_url_is_already_tiktok():
    page = Page(99, PROFILE)
    with pytest.raises(uploader.UploadError, match='ERR_ADDRESS_UNREACHABLE'):
        uploader.goto(page, PROFILE)
    assert len(page.calls) == 3


def test_navigation_budget_is_not_extended_by_retries(monkeypatch):
    # The first navigation spent nearly the whole 45-second budget.
    clock = iter([0, 0, 44.5])
    monkeypatch.setattr(uploader.time, 'monotonic', lambda: next(clock))
    page = Page(99)
    with pytest.raises(uploader.UploadError):
        uploader.goto(page, PROFILE)
    assert len(page.calls) == 1 and not page.delays


def test_non_transient_network_rejection_is_not_retried_or_hidden():
    page = Page(0, PROFILE)
    def rejected(*args, **kwargs):
        page.calls.append(PROFILE)
        raise RuntimeError('Page.goto: net::ERR_BLOCKED_BY_CLIENT')
    page.goto = rejected
    with pytest.raises(uploader.UploadError):
        uploader.goto(page, PROFILE)
    assert len(page.calls) == 1 and not page.delays


@pytest.mark.parametrize('code', retry.TIKTOK_TRANSIENT_NETWORK_ERRORS)
def test_exact_initial_profile_network_failure_is_automatically_retryable(code):
    assert retry.tiktok_retry_reason(ERROR.replace('ERR_ADDRESS_UNREACHABLE', code), []) == 'profile_network_before_file'


@pytest.mark.parametrize('marker', ['Video dipilih: clip.mp4', 'DRAFT_FILE_RECOVERED:clip.mp4',
    'CDP_FILE_TRANSFER_RECOVERED:clip.mp4', 'DRAFT_RESUME_ONLY:hash',
    'POST_SUBMIT_INTENT: started', 'POST_API_ACCEPTED: accepted', 'VIDEO_URL:https://example.test/post'])
def test_file_or_post_evidence_prevents_profile_network_retry(marker):
    assert retry.tiktok_retry_reason(ERROR, [marker]) == ''


@pytest.mark.parametrize('flags', [{'started': True}, {'accepted': True}])
def test_durable_submission_flags_prevent_retry(flags):
    assert retry.tiktok_retry_reason(ERROR, [], **flags) == ''


@pytest.mark.parametrize('error', [ERROR.replace('www.tiktok.com', 'www.tiktok.com.evil.test'), ERROR + '/video/1234567890123456789',
    ERROR + ' CAPTCHA', ERROR.replace('/@titikbalikislami', '/tiktokstudio/upload'),
    ERROR.replace('/@titikbalikislami', '/login'), ERROR.replace('ERR_ADDRESS_UNREACHABLE', 'ERR_BLOCKED_BY_CLIENT')])
def test_only_initial_profile_transient_transport_failure_qualifies(error):
    assert retry.tiktok_retry_reason(error, []) == ''
