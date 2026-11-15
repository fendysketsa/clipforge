"""Facebook Reels in the existing desktop-owned social Chrome profile."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from browser_page_activity import start_background_page_activity, stop_background_page_activity


TARGET_EMAIL = 'fendysketsa@gmail.com'
CONTACT_URL = 'https://accountscenter.facebook.com/personal_info/contact_points/'
CREATE_URL = 'https://www.facebook.com/reels/create/'


def cdp_url() -> str:
    # Always attach to YouTube's social browser. Never launch another profile.
    return os.environ.get('YOUTUBE_CDP_URL', 'http://127.0.0.1:9333').rstrip('/')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url(), timeout=15000, no_defaults=True)
        if not browser.contexts:
            raise RuntimeError('Browser bersama belum mempunyai profil aktif.')
        # Exiting Playwright disconnects only the client; never browser.close().
        yield browser.contexts[0]


def facebook_page(context, *, create: bool = True):
    for page in context.pages:
        if urlparse(page.url).hostname in {'www.facebook.com', 'facebook.com'}:
            return page
    if create:
        return context.new_page()
    return None


def logged_user(context) -> str:
    return next((cookie['value'] for cookie in context.cookies('https://www.facebook.com/')
                 if cookie['name'] == 'c_user'), '')


def active_user(context) -> str:
    cookies = {cookie['name']: cookie['value'] for cookie in context.cookies('https://www.facebook.com/')}
    return cookies.get('i_user') or cookies.get('c_user', '')


def own_profile(context, profile_id: str) -> dict:
    page = context.new_page()
    try:
        page.goto('https://www.facebook.com/me/', wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(1500)
        text = page.locator('body').inner_text(timeout=5000)
        valid = (urlparse(page.url).hostname in {'www.facebook.com', 'facebook.com'}
                 and active_user(context) == profile_id and '/login' not in page.url)
        return {'profile_url': page.url if valid else None,
                'professional_mode': bool(valid and re.search(r'\b(Dasbor|Professional dashboard)\b', text, re.I))}
    finally:
        page.close()


def session(context, *, open_login: bool = False, expected_profile: str = '') -> dict:
    result = dict(status='login_required', logged_in=False, account_verified=False,
                  target_email=TARGET_EMAIL, profile_id=None, checked_at=now(),
                  message='Login Facebook diperlukan di browser bersama.')
    profile = logged_user(context)
    if profile and active_user(context) != profile:
        result.update(status='account_unverified', logged_in=True,
                      message='Facebook sedang memakai profil/Page lain. Kembali ke profil profesional akun target.')
        return result
    page = facebook_page(context)
    if not page.url.startswith('https://www.facebook.com') or open_login:
        page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=45000)
    if not profile:
        email_input = page.locator('input[name="email"]')
        if open_login and email_input.count():
            email_input.first.fill(TARGET_EMAIL)
        return result
    # Cookie presence is not identity proof. Check the live contact screen.
    contact = context.new_page()
    try:
        contact.goto(CONTACT_URL, wait_until='domcontentloaded', timeout=45000)
        contact.get_by_text(TARGET_EMAIL, exact=False).first.wait_for(state='visible', timeout=12000)
        text = contact.locator('body').inner_text(timeout=5000)
        verified = (urlparse(contact.url).hostname == 'accountscenter.facebook.com'
                    and TARGET_EMAIL.casefold() in text.casefold()
                    and logged_user(context) == profile)
    except Exception:
        verified = False
    finally:
        contact.close()
    if expected_profile and profile != expected_profile:
        verified = False
        result['message'] = 'Profil Facebook berubah; periksa akun sebelum upload.'
    elif not verified:
        result['message'] = 'Facebook mempunyai sesi, tetapi email akun target belum terverifikasi.'
    else:
        result['message'] = 'Akun Facebook target terverifikasi di browser bersama.'
    result.update(status='ready' if verified else 'account_unverified', logged_in=True,
                  account_verified=verified, profile_id=profile)
    if verified:
        try:
            result.update(own_profile(context, profile))
        except Exception:
            result.update(profile_url=None, professional_mode=None)
    return result


def check_session(*, open_login: bool = False, expected_profile: str = '') -> dict:
    try:
        with connection() as context:
            return session(context, open_login=open_login, expected_profile=expected_profile)
    except Exception:
        # Transport failure never invalidates or deletes saved credentials.
        return dict(status='browser_unavailable', logged_in=None, account_verified=False,
                    target_email=TARGET_EMAIL, profile_id=None, checked_at=now(),
                    message='Browser bersama belum dapat diperiksa. Sesi tersimpan tetap dipertahankan.')


def reel_url(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.facebook.com', 'facebook.com'}:
        return None
    match = re.fullmatch(r'/reel/(\d+)/?', parsed.path)
    return f'https://www.facebook.com/reel/{match.group(1)}/' if match else None


def exact_caption_visible(page, caption: str) -> bool:
    normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
    # Check the content region, not global text where navigation/sidebar can match.
    for region in page.locator('[role="article"], [role="main"]').all():
        try:
            if normalize(caption) in normalize(region.inner_text(timeout=3000)):
                return True
        except Exception:
            continue
    return False


def verify_remote(context, url: str, caption: str, profile_id: str) -> bool:
    canonical = reel_url(url)
    if not canonical or active_user(context) != profile_id:
        return False
    own = own_profile(context, profile_id).get('profile_url')
    own_path = urlparse(own).path.rstrip('/') if own else None
    page = context.new_page()
    try:
        page.goto(canonical, wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(3000)
        # Require a video, exact full copy, and the author link in the content.
        authors = page.locator('[role="main"] a[href], [role="article"] a[href]').evaluate_all(
            '(nodes) => nodes.map(node => node.href)')
        owner = any((own_path not in {None, '/profile.php', '/me', ''} and urlparse(link).path.rstrip('/') == own_path)
                    or urlparse(link).path.rstrip('/') == '/' + profile_id
                    or (urlparse(link).path == '/profile.php' and
                        re.search(r'(?:^|&)id=' + re.escape(profile_id) + r'(?:&|$)', urlparse(link).query))
                    for link in authors)
        return bool(owner and page.locator('video').count() and exact_caption_visible(page, caption))
    finally:
        page.close()


def upload(path: Path, caption: str, profile_id: str, checkpoint) -> dict:
    """One attempt only. Save the submission boundary before the Post click."""
    from playwright.sync_api import expect
    with connection() as context:
        status = session(context, expected_profile=profile_id)
        if not status['account_verified'] or status['profile_id'] != profile_id:
            raise RuntimeError(status['message'])
        page = context.new_page()
        submitted = False
        activity = start_background_page_activity(page)
        try:
            page.goto(CREATE_URL, wait_until='domcontentloaded', timeout=45000)
            page.locator('input[type="file"]').first.set_input_files(str(path), timeout=90000)
            editor = page.locator('[role="textbox"][contenteditable="true"], textarea').first
            for _ in range(4):
                if editor.count() and editor.is_visible():
                    break
                next_button = page.get_by_role('button', name=re.compile(r'^(Next|Berikutnya|Selanjutnya)$', re.I))
                next_button.first.wait_for(state='visible', timeout=30000)
                next_button.first.press('Enter')
                page.wait_for_timeout(1000)
            editor.wait_for(state='visible', timeout=30000)
            editor.fill(caption)
            post = page.get_by_role('button', name=re.compile(
                r'^(Publish|Post|Share now|Share|Bagikan|Bagikan sekarang|Terbitkan|Posting)$', re.I))
            for _ in range(4):
                if post.count() == 1 and post.first.is_visible():
                    break
                next_button = page.get_by_role('button', name=re.compile(r'^(Next|Berikutnya|Selanjutnya)$', re.I))
                next_button.first.wait_for(state='visible', timeout=30000)
                next_button.first.press('Enter')
                page.wait_for_timeout(1500)
            # Be explicit about audience; never change account-wide defaults.
            public = page.get_by_role('radio', name=re.compile(r'^(Public|Publik)$', re.I))
            if public.count() and public.first.is_visible():
                public.first.check()
            audience = page.get_by_role('button', name=re.compile(
                r'(?:Audiens postingan|Post audience)[\s\S]*(?:Publik|Public)', re.I))
            if audience.count() != 1 or not audience.first.is_visible():
                raise RuntimeError('Audiens publik Reel belum terbukti; upload ditahan sebelum Post.')
            if active_user(context) != profile_id:
                raise RuntimeError('Akun Facebook berubah sebelum Post.')
            if post.count() != 1:
                raise RuntimeError('Tombol publikasi Facebook belum dapat dikenali secara pasti.')
            post = post.first
            post.wait_for(state='visible', timeout=60000)
            expect(post).to_be_enabled(timeout=120000)
            checkpoint(submission_started=True, status='running', message='Mengirim Reel; menunggu identitas remote.')
            submitted = True
            post.press('Enter', timeout=15000)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                links = page.locator('a[href*="/reel/"]').evaluate_all('(nodes) => nodes.map(node => node.href)')
                candidates = [page.url, *links]
                for candidate in candidates:
                    canonical = reel_url(candidate)
                    if canonical and verify_remote(context, canonical, caption, profile_id):
                        return dict(status='completed', upload_confirmed=True, video_url=canonical,
                                    message='Reel terkonfirmasi pada akun target.')
                page.wait_for_timeout(3000)
            return dict(status='needs_review', upload_confirmed=False,
                        message='Post sudah dicoba; identitas Reel belum terkonfirmasi. Jangan upload ulang.')
        finally:
            stop_background_page_activity(activity)
            # Preserve ambiguous submitted composer for the operator to inspect.
            if not submitted:
                page.close()
