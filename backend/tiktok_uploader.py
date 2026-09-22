from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path(
    os.environ.get("TIKTOK_PLAYWRIGHT_STATE", BASE_DIR / "data" / "tiktok_storage_state.json")
)
DEFAULT_PROFILE_DIR = os.environ.get("TIKTOK_CHROMIUM_USER_DATA_DIR", "").strip()
DEFAULT_PROFILE_NAME = os.environ.get("TIKTOK_CHROMIUM_PROFILE_DIRECTORY", "Default").strip()
DEFAULT_HANDLE = os.environ.get("TIKTOK_TARGET_HANDLE", "titikbalikislami").strip().lstrip("@")
DEFAULT_EMAIL = os.environ.get("TIKTOK_TARGET_EMAIL", "fendycn88@gmail.com").strip()
DEFAULT_LOGIN_METHOD = os.environ.get("TIKTOK_LOGIN_METHOD", "google").strip().casefold()
UPLOAD_URL = os.environ.get("TIKTOK_UPLOAD_URL", "https://www.tiktok.com/tiktokstudio/upload").strip()
DEBUG_DIR = Path(os.environ.get("TIKTOK_UPLOAD_DEBUG_DIR", BASE_DIR / "data" / "tiktok_debug"))
TIKTOK_AUTH_COOKIE_NAMES = frozenset({"sessionid", "sessionid_ss", "sid_tt", "sid_guard"})
DEFAULT_FILE_INPUT_TIMEOUT_MS = 300_000
DEFAULT_POST_READY_TIMEOUT_MS = 300_000
MIN_POST_READY_TIMEOUT_MS = 30_000
TIKTOK_CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"
# Playwright refuses remote-browser file transfers at 50 MiB. Leave enough
# headroom for container/browser protocol overhead after making a staging copy.
REMOTE_FILE_TRANSFER_LIMIT_BYTES = 50 * 1024 * 1024
DEFAULT_REMOTE_FILE_DIRECT_MAX_MB = 20
DEFAULT_REMOTE_FILE_TARGET_MB = 16


class UploadError(RuntimeError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def remote_file_staging_sizes() -> tuple[int, int]:
    """Return safe source/target limits for Playwright's slow CDP transfer."""
    direct_max_mb = min(
        48,
        env_int(
            "TIKTOK_CDP_DIRECT_UPLOAD_MAX_MB",
            DEFAULT_REMOTE_FILE_DIRECT_MAX_MB,
            minimum=2,
        ),
    )
    target_mb = min(
        direct_max_mb - 1,
        env_int(
            "TIKTOK_CDP_STAGING_TARGET_MB",
            DEFAULT_REMOTE_FILE_TARGET_MB,
            minimum=1,
        ),
    )
    return direct_max_mb * 1024 * 1024, target_mb * 1024 * 1024


def log(message: str) -> None:
    print(message, flush=True)


def clean_handle(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._]", "", value.strip().lstrip("@")).casefold()


def has_authenticated_tiktok_cookie(context) -> bool:
    try:
        cookies = context.cookies()
    except Exception:
        return False
    current_epoch = time.time()
    return any(
        str(cookie.get("name") or "").casefold() in TIKTOK_AUTH_COOKIE_NAMES
        and "tiktok.com" in str(cookie.get("domain") or "").casefold()
        and (
            not isinstance(cookie.get("expires"), (int, float))
            or float(cookie.get("expires") or -1) <= 0
            or float(cookie.get("expires")) > current_epoch
        )
        for cookie in cookies
        if isinstance(cookie, dict)
    )


def authenticated_tiktok_cookie_fingerprints(context) -> set[tuple[str, str, str]]:
    """Return opaque auth-cookie identities so login can detect a fresh session."""
    try:
        cookies = context.cookies()
    except Exception:
        return set()
    return {
        (
            str(cookie.get("name") or "").casefold(),
            str(cookie.get("domain") or "").casefold(),
            str(cookie.get("value") or ""),
        )
        for cookie in cookies
        if isinstance(cookie, dict)
        and str(cookie.get("name") or "").casefold() in TIKTOK_AUTH_COOKIE_NAMES
        and "tiktok.com" in str(cookie.get("domain") or "").casefold()
    }


def import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - deployment dependency
        raise UploadError(
            "Playwright belum terpasang. Install requirements backend dan browser Chromium."
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


def save_session_state(context, state_path: Path) -> None:
    """Persist the complete TikTok session without exposing a half-written file."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    # Cookies and localStorage carry the reusable TikTok login. Exporting
    # IndexedDB has caused native Chromium/Playwright crashes on some Linux
    # builds, so keep the portable storage-state format here.
    state = context.storage_state()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{state_path.name}.",
        dir=state_path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(state, temporary_file, ensure_ascii=False, separators=(",", ":"))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, state_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def save_debug(page, label: str) -> None:
    if not env_bool("TIKTOK_UPLOAD_DEBUG", True):
        return
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        page.screenshot(path=str(DEBUG_DIR / f"{stamp}-{label}.png"), full_page=True)
        (DEBUG_DIR / f"{stamp}-{label}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


def minimize_cdp_browser(context, page) -> bool:
    """Minimize the dedicated Chrome window without closing its login profile."""
    session = None
    try:
        session = context.new_cdp_session(page)
        window = session.send("Browser.getWindowForTarget")
        window_id = window.get("windowId") if isinstance(window, dict) else None
        if window_id is None:
            return False
        try:
            current = session.send("Browser.getWindowBounds", {"windowId": window_id})
        except Exception:
            current = {}
        bounds = current.get("bounds") if isinstance(current, dict) else None
        if isinstance(bounds, dict) and bounds.get("windowState") == "minimized":
            return True
        session.send(
            "Browser.setWindowBounds",
            {"windowId": window_id, "bounds": {"windowState": "minimized"}},
        )
        log("Chrome TikTok diminimalkan; automasi tetap berjalan di background.")
        return True
    except Exception as exc:
        log(f"Chrome TikTok belum dapat diminimalkan otomatis: {exc}")
        return False
    finally:
        if session is not None:
            try:
                session.detach()
            except Exception:
                pass


def first_visible(page, selectors: Sequence[str], timeout_ms: int = 1500):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except Exception:
            continue
    return None


def goto(page, url: str, timeout_ms: int = 45_000) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as exc:
        if not page.url or "tiktok.com" not in page.url:
            raise UploadError(f"TikTok tidak dapat dibuka: {exc}") from exc


def current_profile_handle(page) -> str:
    selectors = (
        '[data-e2e="nav-profile"]',
        'a[aria-label="Profile"]',
        'a[aria-label="Profil"]',
        'a[href^="/@"]:has([aria-label="Profile"])',
        'a[href^="/@"]:has([aria-label="Profil"])',
    )
    for selector in selectors:
        try:
            href = page.locator(selector).first.get_attribute("href", timeout=300) or ""
        except Exception:
            continue
        match = re.search(r"/@([^/?#]+)", href)
        if match:
            return clean_handle(match.group(1))
    return ""


def profile_owner_controls_visible(page) -> bool:
    """Detect controls that TikTok renders only on the signed-in user's profile."""
    try:
        if page.locator('[data-e2e="edit-profile-entrance"]').first.is_visible(timeout=500):
            return True
    except Exception:
        pass
    # TikTok has changed the button wrapper/data attributes several times. The
    # rendered body text is a safe fallback here: this check runs on the target
    # profile URL, and public visitors do not get an Edit profile control.
    try:
        body_text = page.locator("body").inner_text(timeout=750)
    except Exception:
        return False
    return bool(
        re.search(
            r"(?:^|\n)\s*(?:Edit profile|Edit profil|Sunting profil)\s*(?:\n|$)",
            body_text,
            re.I,
        )
    )


def validate_target_account(page, target_handle: str, target_email: str = "") -> None:
    expected = clean_handle(target_handle)
    if not expected:
        raise UploadError("Target handle TikTok belum dikonfigurasi.")
    if not has_authenticated_tiktok_cookie(page.context):
        raise UploadError("Sesi TikTok belum login. Klik Login TikTok lalu lanjutkan dengan Google di Chrome.")
    goto(page, f"https://www.tiktok.com/@{expected}")
    page.wait_for_timeout(1800)
    login_button = first_visible(
        page,
        ['[data-e2e="top-login-button"]', 'button:has-text("Log in")', 'button:has-text("Masuk")'],
        timeout_ms=1_000,
    )
    if "/login" in page.url.casefold() or login_button is not None:
        raise UploadError("Sesi TikTok belum login. Klik Login TikTok lalu lanjutkan dengan Google di Chrome.")

    # Profile hydration is often slower than DOMContentLoaded. Previously this
    # was checked only once; a valid @titikbalikislami page was consequently
    # classified as an account mismatch and its reusable session quarantined.
    signed_in_handle = ""
    for _attempt in range(8):
        observed_handle = current_profile_handle(page)
        if observed_handle:
            signed_in_handle = observed_handle
        if observed_handle == expected or profile_owner_controls_visible(page):
            log(f"TARGET_ACCOUNT_CONFIRMED:@{expected}")
            return
        page.wait_for_timeout(750)

    save_debug(page, "account-mismatch")
    account_hint = f" ({target_email})" if target_email else ""
    if signed_in_handle and signed_in_handle != expected:
        raise UploadError(
            f"Akun browser aktif @{signed_in_handle} bukan akun target @{expected}{account_hint}. "
            "Upload dihentikan sebelum file dipilih."
        )
    raise UploadError(
        f"Sesi TikTok terdeteksi, tetapi identitas akun @{expected}{account_hint} belum dapat "
        "diverifikasi karena halaman profil belum selesai dimuat. Session tetap disimpan; "
        "klik Cek sesi TikTok lalu ulangi upload."
    )


def select_google_login(page, timeout_ms: int = 2_500) -> bool:
    """Select TikTok's Google OAuth entry without handling user credentials."""
    if "/login" not in str(getattr(page, "url", "")).casefold():
        return False
    google_option = first_visible(
        page,
        (
            '[data-e2e="channel-item"]:has-text("Continue with Google")',
            '[data-e2e="channel-item"]:has-text("Lanjutkan dengan Google")',
            '[role="link"]:has-text("Continue with Google")',
            '[role="link"]:has-text("Lanjutkan dengan Google")',
            'button:has-text("Continue with Google")',
            'button:has-text("Lanjutkan dengan Google")',
        ),
        timeout_ms=timeout_ms,
    )
    if google_option is None:
        log("GOOGLE_LOGIN_OPTION_NOT_FOUND: Klik Continue with Google secara manual pada jendela TikTok.")
        return False
    try:
        google_option.click(timeout=10_000)
    except Exception as exc:
        log(f"GOOGLE_LOGIN_CLICK_FAILED: Klik Continue with Google secara manual ({exc}).")
        return False
    log("GOOGLE_LOGIN_SELECTED: Continue with Google dipilih; menunggu pemilihan akun/CAPTCHA oleh pengguna.")
    return True


def select_qr_login(page, timeout_ms: int = 2_500) -> bool:
    """Open TikTok's first-party QR login without spawning a Google OAuth popup."""
    if "/login" not in str(getattr(page, "url", "")).casefold():
        return False
    qr_option = first_visible(
        page,
        (
            '[data-e2e="channel-item"]:has-text("Use QR code")',
            '[data-e2e="channel-item"]:has-text("Gunakan kode QR")',
            '[role="link"]:has-text("Use QR code")',
            '[role="link"]:has-text("Gunakan kode QR")',
            'button:has-text("Use QR code")',
            'button:has-text("Gunakan kode QR")',
        ),
        timeout_ms=timeout_ms,
    )
    if qr_option is None:
        log("QR_LOGIN_OPTION_NOT_FOUND: Klik Use QR code secara manual pada jendela TikTok.")
        return False
    try:
        qr_option.click(timeout=10_000)
    except Exception as exc:
        log(f"QR_LOGIN_CLICK_FAILED: Klik Use QR code secara manual ({exc}).")
        return False
    log("QR_LOGIN_SELECTED: Scan QR dengan aplikasi TikTok di HP lalu konfirmasi login.")
    return True


def login_and_capture(page, context, state_path: Path, target_handle: str, target_email: str, timeout: int) -> None:
    expected = clean_handle(target_handle)
    if not expected:
        raise UploadError("Target handle TikTok belum dikonfigurasi.")
    if DEFAULT_LOGIN_METHOD == "qr":
        # A previous Google attempt can leave an unusable black OAuth popup in
        # Chrome for Testing. Remove only those external popup tabs, return to
        # TikTok, and keep the persistent browser/profile itself alive.
        for open_page in list(getattr(context, "pages", [])):
            if open_page is page:
                continue
            if "accounts.google.com" in str(getattr(open_page, "url", "")).casefold():
                try:
                    open_page.close()
                except Exception:
                    pass
        goto(page, "https://www.tiktok.com/login")
        try:
            page.bring_to_front()
        except Exception:
            pass
    elif "tiktok.com" not in page.url.casefold():
        goto(page, "https://www.tiktok.com/login")
    if DEFAULT_LOGIN_METHOD == "qr":
        select_qr_login(page)
    elif DEFAULT_LOGIN_METHOD == "google":
        select_google_login(page)
    if DEFAULT_LOGIN_METHOD == "qr":
        instruction = "Scan QR dengan aplikasi TikTok di HP dan konfirmasi login"
    elif DEFAULT_LOGIN_METHOD == "google":
        instruction = f"Pilih akun Google {target_email or ''} dan selesaikan captcha bila muncul"
    else:
        instruction = "Selesaikan login secara manual"
    log(
        f"LOGIN_REQUIRED: {instruction}, lalu pastikan akun @{expected} yang aktif. "
        "Session baru disimpan setelah akun target terverifikasi."
    )
    deadline = time.monotonic() + max(30, timeout)
    last_check = 0.0
    last_error = "Login TikTok belum selesai."
    last_reported_error = ""
    initial_auth_cookies = authenticated_tiktok_cookie_fingerprints(context)
    while time.monotonic() < deadline:
        page.wait_for_timeout(1500)
        if time.monotonic() - last_check < 5:
            continue
        last_check = time.monotonic()
        # A cookie alone is not proof of a reusable login: it can be stale or
        # belong to another account. Keep the login/CAPTCHA page untouched until
        # TikTok has an auth cookie, then perform the same target-identity guard
        # used immediately before upload.
        if not has_authenticated_tiktok_cookie(context):
            continue
        candidate_page = page
        for open_page in reversed(list(getattr(context, "pages", []))):
            open_url = str(getattr(open_page, "url", "")).casefold()
            if "tiktok.com" in open_url and "/login" not in open_url:
                candidate_page = open_page
                break
        verification_page = None
        # TikTok occasionally completes OAuth/CAPTCHA without redirecting the
        # original login tab. Only open a separate verification tab when an
        # auth cookie was newly created/changed, so stale cookies cannot make us
        # navigate away from an unfinished CAPTCHA.
        if "/login" in str(getattr(candidate_page, "url", "")).casefold():
            current_auth_cookies = authenticated_tiktok_cookie_fingerprints(context)
            if not current_auth_cookies or current_auth_cookies == initial_auth_cookies:
                continue
            try:
                verification_page = context.new_page()
                candidate_page = verification_page
            except Exception:
                continue
        try:
            validate_target_account(candidate_page, expected, target_email)
            save_session_state(context, state_path)
            log(f"SESSION_SAVED:{state_path}")
            # Leave the persistent browser on TikTok Studio, matching the
            # YouTube deploy/login experience instead of ending on /login or a
            # profile page after the session has been captured.
            goto(page, UPLOAD_URL)
            try:
                page.bring_to_front()
            except Exception:
                pass
            log("TIKTOK_STUDIO_READY")
            return
        except UploadError as exc:
            last_error = str(exc)
            if last_error != last_reported_error:
                if "bukan pemilik" in last_error.casefold():
                    log(
                        f"WRONG_ACCOUNT: {last_error} Keluar dari akun tersebut lalu login sebagai @{expected}; "
                        "session yang salah tidak akan disimpan."
                    )
                last_reported_error = last_error
        except Exception as exc:
            last_error = str(exc)
        finally:
            if verification_page is not None:
                try:
                    verification_page.close()
                except Exception:
                    pass
    save_debug(page, "login-timeout")
    raise UploadError(
        f"Login belum terverifikasi sebagai @{expected} dalam {timeout} detik. "
        f"Session tidak disimpan dan tidak ada file yang diunggah. Terakhir: {last_error}"
    )


def normalized_caption_text(value: str) -> str:
    """Normalize browser-only whitespace without hiding real caption prefixes."""
    return (
        value.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .strip()
    )


def caption_editor_text(editor) -> str:
    try:
        return str(editor.input_value(timeout=1_000) or "")
    except Exception:
        try:
            return str(editor.inner_text(timeout=1_000) or "")
        except Exception:
            return str(editor.text_content(timeout=1_000) or "")


def clear_caption_editor(page, editor) -> None:
    """Remove TikTok's filename-derived caption from the actual text control."""
    try:
        editor.click(timeout=5_000)
    except Exception as first_error:
        dismissed, modal_text = dismiss_blocking_modal(page)
        if not dismissed:
            save_debug(page, "caption-blocked-by-modal")
            detail = modal_text or "dialog tanpa keterangan"
            raise UploadError(
                f"Dialog TikTok menghalangi kolom caption: {detail}. "
                "Video belum diposting."
            ) from first_error
        try:
            editor.click(timeout=5_000)
        except Exception as retry_error:
            save_debug(page, "caption-click-failed")
            raise UploadError(
                "Kolom caption TikTok tetap tidak dapat diklik setelah dialog ditutup; "
                "video belum diposting."
            ) from retry_error
    try:
        editor.press("Control+A", timeout=2_000)
        editor.press("Backspace", timeout=2_000)
    except Exception:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")


def set_caption(page, caption: str) -> None:
    editor = first_visible(
        page,
        [
            '[data-e2e="caption-editor"] [contenteditable="true"]',
            '[data-e2e="caption-editor"][contenteditable="true"]',
            '[data-e2e="caption-editor"] textarea',
            '.public-DraftEditor-content[contenteditable="true"]',
            '[class*="caption-editor"] [contenteditable="true"]',
            'div[contenteditable="true"][role="combobox"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[contenteditable="true"]',
            'textarea[placeholder*="caption" i]',
            'textarea[placeholder*="deskripsi" i]',
            'textarea',
        ],
        timeout_ms=15_000,
    )
    if editor is None:
        save_debug(page, "caption-editor-missing")
        raise UploadError("Kolom caption TikTok tidak ditemukan setelah video dipilih.")
    expected = caption[:2200]
    last_value = ""
    for _attempt in range(2):
        clear_caption_editor(page, editor)
        try:
            editor.fill(expected, timeout=10_000)
        except Exception:
            # DraftJS variants do not always implement Playwright's fill(). The
            # failed call may have inserted partial text, so clear once more
            # before keyboard input as well.
            clear_caption_editor(page, editor)
            page.keyboard.type(expected, delay=2)
        page.wait_for_timeout(400)
        last_value = caption_editor_text(editor)
        if normalized_caption_text(last_value) == normalized_caption_text(expected):
            log("Caption TikTok terisi tanpa nama file.")
            return

    save_debug(page, "caption-not-replaced")
    preview = normalized_caption_text(last_value)[:80]
    raise UploadError(
        "Caption TikTok tidak dapat menggantikan judul otomatis dari nama file; "
        f"video tidak diposting. Isi editor terakhir: {preview!r}"
    )


def upload_editor_has_requested_file(page, video_path: Path) -> bool:
    """Return true only when the visible editor plausibly owns this job's file."""
    try:
        body_text = normalized_caption_text(page.locator("body").inner_text(timeout=5_000))
    except Exception:
        body_text = ""
    requested_names = {video_path.name.casefold(), video_path.stem.casefold()}
    filename_matches = any(name and name in body_text.casefold() for name in requested_names)
    editor_ready = first_visible(
        page,
        (
            *POST_BUTTON_SELECTORS,
            '[data-e2e="caption-editor"]',
            '[class*="caption-editor"]',
        ),
        timeout_ms=1_500,
    ) is not None
    empty_picker = first_visible(
        page,
        ('text="Select video to upload"', 'text="Pilih video untuk diunggah"'),
        timeout_ms=500,
    ) is not None
    return (filename_matches or editor_ready) and not empty_picker


def recover_interrupted_upload_draft(page, video_path: Path) -> bool:
    """Resume a browser draft when TikTok already received the requested file."""
    button = first_visible(
        page,
        [
            'button:has-text("Continue editing")',
            'button:has-text("Continue Editing")',
            'button:has-text("Lanjutkan mengedit")',
            'button:has-text("Lanjut mengedit")',
        ],
        timeout_ms=1_200,
    )
    if button is None:
        return False
    try:
        button.click(timeout=5_000)
        log("Draft TikTok ditemukan; melanjutkan editor tanpa membuang file yang sudah ditransfer.")
        page.wait_for_timeout(1_200)
    except Exception as exc:
        raise UploadError(
            "Draft TikTok ditemukan tetapi tombol Continue editing tidak dapat dibuka. "
            "File tidak dibuang dan upload baru tidak dimulai."
        ) from exc

    if upload_editor_has_requested_file(page, video_path):
        log(f"DRAFT_FILE_RECOVERED:{video_path.name}")
        return True

    save_debug(page, "draft-recovered-unverified")
    raise UploadError(
        "TikTok memulihkan draft yang belum dapat dicocokkan dengan file job ini. "
        "Draft tidak dibuang dan upload baru tidak dimulai; periksa editor TikTok agar tidak duplikat."
    )


BLOCKING_MODAL_SELECTORS = (
    '[role="dialog"]:has-text("Continue to post?")',
    '[role="dialog"]:has-text("Content may be restricted")',
    '[data-floating-ui-portal]:has(.TUXModal-overlay[data-transition-status="open"])',
    '[data-floating-ui-portal]:has(.TUXModal-overlay)',
    '[role="dialog"]',
)


def visible_blocking_modal(page, timeout_ms: int = 500):
    return first_visible(page, BLOCKING_MODAL_SELECTORS, timeout_ms=timeout_ms)


def dismiss_blocking_modal(page) -> tuple[bool, str]:
    """Dismiss a late TikTok Studio modal without enabling optional features."""
    modal = visible_blocking_modal(page)
    if modal is None:
        return True, ""
    try:
        modal_text = " ".join(str(modal.inner_text(timeout=1_500) or "").split())[:300]
    except Exception:
        modal_text = ""
    if modal_text:
        log(f"Dialog TikTok terdeteksi: {modal_text}")

    # Informational dialogs are commonly dismissible with Escape even when the
    # close icon has no stable aria label across Studio releases.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass
    if visible_blocking_modal(page) is None:
        log("Dialog TikTok ditutup sebelum pengisian caption.")
        return True, modal_text

    modal = visible_blocking_modal(page)
    if modal is None:
        return True, modal_text
    button = first_visible(
        modal,
        (
            'button[aria-label*="close" i]',
            'button:has-text("Not now")',
            'button:has-text("Nanti")',
            'button:has-text("Skip")',
            'button:has-text("Lewati")',
            'button:has-text("Cancel")',
            'button:has-text("Batal")',
            'button:has-text("Got it")',
            'button:has-text("Mengerti")',
            'button:has-text("Paham")',
            'button:has-text("OK")',
            'button:has-text("Close")',
            'button:has-text("Tutup")',
            'button:has-text("Continue")',
            'button:has-text("Lanjutkan")',
        ),
        timeout_ms=500,
    )
    if button is not None:
        try:
            button.click(timeout=5_000)
            page.wait_for_timeout(700)
        except Exception:
            pass
    dismissed = visible_blocking_modal(page) is None
    if dismissed:
        log("Dialog TikTok ditutup sebelum pengisian caption.")
    else:
        log(f"BLOCKING_TIKTOK_MODAL:{modal_text or 'isi dialog tidak terbaca'}")
    return dismissed, modal_text


def dismiss_upload_overlays(page) -> None:
    """Dismiss TikTok Studio onboarding without accepting optional checks."""
    page.wait_for_timeout(700)
    for selectors in (
        [
            'button:has-text("Cancel")',
            'button:has-text("Batal")',
            'button:has-text("Not now")',
            'button:has-text("Nanti")',
        ],
        [
            'button:has-text("Got it")',
            'button:has-text("Mengerti")',
            'button:has-text("Paham")',
        ],
    ):
        button = first_visible(page, selectors, timeout_ms=1200)
        if button is None:
            continue
        try:
            button.click(timeout=5_000)
            page.wait_for_timeout(400)
        except Exception:
            continue
    dismissed, modal_text = dismiss_blocking_modal(page)
    if not dismissed:
        save_debug(page, "blocking-upload-modal")
        detail = modal_text or "isi dialog tidak terbaca"
        raise UploadError(
            f"Dialog TikTok menghalangi form upload: {detail}. Video belum diposting."
        )


def set_only_you(page) -> None:
    trigger = first_visible(
        page,
        [
            '[data-e2e="privacy-level"]',
            'button:has-text("Everyone")',
            'button:has-text("Semua orang")',
            'button:has-text("Friends")',
            'button:has-text("Pengikut")',
            'div[role="combobox"]:has-text("Everyone")',
            'div[role="combobox"]:has-text("Semua orang")',
        ],
        timeout_ms=10_000,
    )
    if trigger is None:
        raise UploadError("Kontrol privasi TikTok tidak ditemukan; upload tidak diterbitkan.")
    trigger.click()
    option = first_visible(
        page,
        [
            '[role="option"]:has-text("Only you")',
            '[role="option"]:has-text("Hanya Anda")',
            '[role="option"]:has-text("Hanya kamu")',
            'div:has-text("Only you")',
            'div:has-text("Hanya Anda")',
            'div:has-text("Hanya kamu")',
        ],
        timeout_ms=7000,
    )
    if option is None:
        raise UploadError("Pilihan Only you/Hanya Anda tidak ditemukan; upload tidak diterbitkan.")
    option.click()
    page.wait_for_timeout(500)
    visible_text = page.locator("body").inner_text(timeout=5000)
    if not re.search(r"only you|hanya anda|hanya kamu", visible_text, re.I):
        raise UploadError("Privasi Only you tidak dapat diverifikasi; upload tidak diterbitkan.")
    log("FINAL_VISIBILITY:private")


POST_BUTTON_SELECTORS = (
    '[data-e2e="post_video_button"]',
    'button:has-text("Post")',
    'button:has-text("Posting")',
    'button:has-text("Publikasikan")',
)


def upload_progress_text(page) -> str:
    for selector in (
        ".info-progress-num",
        '[class*="progress-num"]',
        'text=/^\\s*\\d{1,3}%\\s*$/',
    ):
        try:
            value = page.locator(selector).first.inner_text(timeout=500).strip()
            if re.fullmatch(r"\d{1,3}%", value):
                return value
        except Exception:
            continue
    return ""


def post_button_is_enabled(button) -> bool:
    try:
        if not button.is_enabled(timeout=750):
            return False
        aria_disabled = (button.get_attribute("aria-disabled", timeout=500) or "").casefold()
        data_disabled = (button.get_attribute("data-disabled", timeout=500) or "").casefold()
        native_disabled = button.get_attribute("disabled", timeout=500)
    except Exception:
        return False
    return (
        aria_disabled != "true"
        and data_disabled != "true"
        and native_disabled is None
    )


def wait_for_post_button(
    page,
    timeout_ms: int,
    background_tick: Callable[[], bool] | None = None,
):
    """Wait for TikTok's async file processing to enable the Post button."""
    deadline = time.monotonic() + max(1_000, timeout_ms) / 1000
    last_progress = ""
    next_background_tick = 0.0
    while time.monotonic() < deadline:
        if background_tick is not None and time.monotonic() >= next_background_tick:
            background_tick()
            next_background_tick = time.monotonic() + 5
        remaining_ms = max(250, int((deadline - time.monotonic()) * 1000))
        button = first_visible(
            page,
            POST_BUTTON_SELECTORS,
            timeout_ms=min(1_000, remaining_ms),
        )
        if button is not None and post_button_is_enabled(button):
            return button
        progress = upload_progress_text(page)
        if progress and progress != last_progress:
            log(f"Pemrosesan video TikTok: {progress}")
            last_progress = progress
        page.wait_for_timeout(500)
    return None


def content_caption_key(caption: str) -> str:
    """Return the stable opening text TikTok Studio shows in its Posts table."""
    normalized = normalized_caption_text(caption)
    return normalized.split("\n", 1)[0].strip()[:160]


def content_caption_matches(body_text: str, caption: str) -> int:
    key = content_caption_key(caption)
    if not key:
        return 0
    return normalized_caption_text(body_text).count(key)


def tiktok_content_caption_count(page, caption: str) -> int:
    page.goto(TIKTOK_CONTENT_URL, wait_until="domcontentloaded", timeout=45_000)
    body_text = page.locator("body").inner_text(timeout=20_000)
    return content_caption_matches(body_text, caption)


def visible_tiktok_post_ids(page) -> set[str]:
    """Return the stable video IDs currently hydrated in Studio's Posts table."""
    try:
        links = page.locator('a[href*="/video/"]').all()
    except Exception:
        return set()
    post_ids: set[str] = set()
    for link in links:
        try:
            href = str(link.get_attribute("href", timeout=750) or "")
        except Exception:
            continue
        match = re.search(r"/video/(\d+)", href)
        if match:
            post_ids.add(match.group(1))
    return post_ids


def tiktok_content_snapshot(page, caption: str) -> tuple[int, set[str] | None]:
    """Capture both caption matches and post IDs before submitting a video."""
    page.goto(TIKTOK_CONTENT_URL, wait_until="domcontentloaded", timeout=45_000)
    body_text = page.locator("body").inner_text(timeout=20_000)
    post_ids = visible_tiktok_post_ids(page)
    # An empty baseline is only trustworthy for a genuinely empty account.
    # If links have not hydrated yet, treating them as an empty set would make
    # every old row look like a new post on the next page load.
    ids_available = bool(post_ids) or bool(
        re.search(r"\b(?:posts|postingan)\s*0\b", body_text, re.I)
    )
    return content_caption_matches(body_text, caption), post_ids if ids_available else None


POST_SUBMISSION_SUCCESS_PATTERNS = (
    r"your video has been uploaded",
    r"your video is being processed",
    r"your post is being processed",
    r"video (?:kamu|anda) (?:telah |sudah )?diunggah",
    r"berhasil (?:diunggah|diposting|dipublikasikan)",
)

POST_SUBMISSION_FAILURE_PATTERNS = (
    r"couldn['\u2019]?t post",
    r"could not post",
    r"failed to post",
    r"unable to post",
    r"post failed",
    r"couldn['\u2019]?t upload",
    r"could not upload",
    r"unable to upload",
    r"video (?:couldn['\u2019]?t|could not) be uploaded",
    r"upload failed",
    r"something went wrong(?: while (?:posting|uploading))?",
    r"gagal (?:memposting|mengunggah|diposting|diunggah)",
    r"tidak dapat (?:memposting|mengunggah)",
    r"terjadi kesalahan saat (?:memposting|mengunggah)",
)


def post_submission_failure(body_text: str) -> str | None:
    """Extract TikTok's visible rejection instead of reporting a generic timeout."""
    for line in normalized_caption_text(body_text).splitlines():
        compact = " ".join(line.split()).strip()
        if not compact:
            continue
        if any(re.search(pattern, compact, re.I) for pattern in POST_SUBMISSION_FAILURE_PATTERNS):
            return compact[:300]
    return None


def monitor_post_submission_response(page) -> tuple[dict[str, object], object | None]:
    """Observe TikTok's authoritative create-post response before clicking Post."""
    state: dict[str, object] = {
        "seen": False,
        "accepted": False,
        "error": "",
        "url": "",
    }

    def handle_response(response) -> None:
        try:
            request = response.request
            url = str(response.url or "")
            normalized_url = url.casefold()
            if str(request.method or "").upper() != "POST":
                return
            if "tiktok.com" not in normalized_url:
                return
            if not any(
                marker in normalized_url
                for marker in (
                    "/api/v1/web/project/post",
                    "/project/post",
                    "/item/create",
                    "/post/publish",
                )
            ):
                return
            state["seen"] = True
            state["url"] = url.split("?", 1)[0]
            http_status = int(response.status)
            try:
                payload = response.json()
            except Exception:
                payload = None
            status_code = payload.get("status_code") if isinstance(payload, dict) else None
            status_message = ""
            if isinstance(payload, dict):
                status_message = str(
                    payload.get("status_msg")
                    or payload.get("message")
                    or payload.get("status_message")
                    or ""
                ).strip()
            if 200 <= http_status < 300 and status_code in (0, "0"):
                state["accepted"] = True
                log(f"POST_API_ACCEPTED:{state['url']}")
                return
            if http_status >= 400 or status_code not in (None, 0, "0"):
                detail = status_message or f"HTTP {http_status}, status_code={status_code}"
                state["error"] = detail[:300]
                log(f"POST_API_REJECTED:{state['url']}:{state['error']}")
            else:
                log(f"POST_API_RESPONSE_UNCLEAR:{state['url']}:HTTP {http_status}")
        except Exception as exc:
            log(f"POST_API_MONITOR_ERROR:{str(exc).splitlines()[0][:180]}")

    try:
        page.on("response", handle_response)
    except Exception:
        return state, None
    return state, handle_response


def stop_post_submission_monitor(page, handler: object | None) -> None:
    if handler is None:
        return
    try:
        page.remove_listener("response", handler)
    except Exception:
        try:
            page.off("response", handler)
        except Exception:
            pass


def confirm_post_submission_modal(page) -> tuple[str, str]:
    """Handle a post-authorized TikTok dialog and describe the next action."""
    modal = visible_blocking_modal(page, timeout_ms=250)
    if modal is None:
        return "none", ""
    try:
        modal_text = " ".join(str(modal.inner_text(timeout=1_000) or "").split())[:300]
    except Exception:
        modal_text = ""
    normalized_text = modal_text.casefold()
    if "content may be restricted" in normalized_text and "you can still post" in normalized_text:
        close_control = first_visible(
            modal,
            (
                ".common-modal-close",
                ".common-modal-close-icon",
            ),
            timeout_ms=750,
        )
        if close_control is None:
            return "blocked", modal_text
        try:
            close_control.click(timeout=5_000)
            page.wait_for_timeout(700)
        except Exception:
            return "blocked", modal_text
        if visible_blocking_modal(page) is not None:
            return "blocked", modal_text
        log(
            "CONTENT_RESTRICTION_WARNING_ACKNOWLEDGED:"
            "TikTok mengizinkan tetap post; tombol Post akan diklik ulang sekali."
        )
        return "retry_post", modal_text
    button = first_visible(
        modal,
        (
            'button:has-text("Post now")',
            'button:has-text("Post anyway")',
            'button:has-text("Continue posting")',
            'button:has-text("Upload anyway")',
            'button:has-text("Publish")',
            'button:has-text("Publikasikan")',
            'button:has-text("Posting sekarang")',
            'button:has-text("Tetap posting")',
            'button:has-text("Confirm")',
            'button:has-text("Konfirmasi")',
            'button:has-text("Continue")',
            'button:has-text("Lanjutkan")',
            'button:has-text("Post")',
            'button:has-text("Posting")',
        ),
        timeout_ms=500,
    )
    if button is None:
        return "blocked", modal_text
    try:
        button.click(timeout=5_000)
        log(f"POST_CONFIRMATION_DIALOG_ACCEPTED:{modal_text or 'dialog konfirmasi'}")
        page.wait_for_timeout(700)
        return "confirmed", modal_text
    except Exception:
        return "blocked", modal_text


def wait_for_post_submission(
    page,
    timeout_ms: int = 45_000,
    background_tick: Callable[[], bool] | None = None,
    submission_state: dict[str, object] | None = None,
    post_button=None,
) -> None:
    """Let TikTok finish its submit request before leaving the upload page."""
    deadline = time.monotonic() + max(15_000, timeout_ms) / 1000
    next_background_tick = 0.0
    post_retried = False
    while time.monotonic() < deadline:
        if background_tick is not None and time.monotonic() >= next_background_tick:
            background_tick()
            next_background_tick = time.monotonic() + 5
        current_url = str(getattr(page, "url", ""))
        if "/tiktokstudio/content" in current_url.casefold():
            log("POST_SUBMISSION_SETTLED:TikTok membuka daftar Posts.")
            return
        try:
            body_text = page.locator("body").inner_text(timeout=2_000)
        except Exception:
            body_text = ""
        if submission_state is not None:
            api_error = str(submission_state.get("error") or "").strip()
            if api_error:
                save_debug(page, "post-api-rejected")
                raise UploadError(f"TikTok menolak permintaan posting: {api_error}")
            if bool(submission_state.get("accepted")):
                log("POST_SUBMISSION_SETTLED:API TikTok menerima posting.")
                page.wait_for_timeout(3_000)
                return
        failure = post_submission_failure(body_text)
        if failure:
            save_debug(page, "post-rejected")
            raise UploadError(f"TikTok menolak posting setelah tombol Post diklik: {failure}")
        modal_action, modal_text = confirm_post_submission_modal(page)
        if modal_action == "retry_post":
            if post_button is None or post_retried:
                save_debug(page, "content-restriction-warning-loop")
                raise UploadError(
                    "Peringatan pembatasan konten TikTok muncul berulang setelah dikonfirmasi; "
                    "video belum diposting."
                )
            post_button.click(timeout=10_000)
            post_retried = True
            log("Tombol Post diklik ulang setelah peringatan pembatasan konten ditutup.")
            page.wait_for_timeout(1_000)
            continue
        if modal_action == "confirmed":
            continue
        if modal_action == "blocked":
            save_debug(page, "unknown-post-confirmation-modal")
            raise UploadError(
                "TikTok menampilkan dialog setelah tombol Post, tetapi kontrol konfirmasinya "
                f"tidak dikenali: {modal_text or 'isi dialog tidak terbaca'}. Video belum diposting."
            )
        if any(re.search(pattern, body_text, re.I) for pattern in POST_SUBMISSION_SUCCESS_PATTERNS):
            log("POST_SUBMISSION_SETTLED:TikTok menerima proses posting.")
            # Keep the document alive briefly so a success toast cannot race a
            # still-running create request on slower or larger uploads.
            page.wait_for_timeout(3_000)
            return
        page.wait_for_timeout(1_000)
    if submission_state is not None and not bool(submission_state.get("seen")):
        save_debug(page, "post-request-missing")
        raise UploadError(
            "Tombol Post sudah diklik, tetapi TikTok tidak mengirim permintaan posting. "
            "Kemungkinan ada dialog atau validasi TikTok yang masih menahan form; "
            "video belum diposting."
        )
    # A response from a changed endpoint can be inconclusive. Continue with the
    # authoritative Posts list only when a plausible post request was observed.
    log("POST_SUBMISSION_ACK_UNAVAILABLE: memeriksa daftar Posts setelah masa tunggu aman.")


def wait_for_new_tiktok_post(
    page,
    caption: str,
    previous_matches: int | None,
    timeout_ms: int = 300_000,
    background_tick: Callable[[], bool] | None = None,
    previous_post_ids: set[str] | None = None,
) -> bool:
    """Confirm a new Studio row by ID or caption; transfer text is never proof."""
    deadline = time.monotonic() + max(5_000, timeout_ms) / 1000
    required_matches = (previous_matches + 1) if previous_matches is not None else 1
    baseline_ids = previous_post_ids
    if "/tiktokstudio/content" not in str(getattr(page, "url", "")).casefold():
        try:
            page.goto(TIKTOK_CONTENT_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception:
            pass
    if background_tick is not None:
        background_tick()
    next_refresh = time.monotonic() + 60
    next_background_tick = time.monotonic() + 5
    while time.monotonic() < deadline:
        if background_tick is not None and time.monotonic() >= next_background_tick:
            background_tick()
            next_background_tick = time.monotonic() + 5
        try:
            # The Posts table is hydrated after DOMContentLoaded. Keep polling
            # the settled document; navigating on every pass resets TikTok's
            # async table and can hide a row that was already accepted.
            body_text = page.locator("body").inner_text(timeout=20_000)
            matches = content_caption_matches(body_text, caption)
            current_ids = visible_tiktok_post_ids(page)
            new_ids = current_ids - baseline_ids if baseline_ids is not None else set()
            if new_ids:
                log(f"POST_CONFIRMED_BY_NEW_ID:{sorted(new_ids)[0]}")
                return True
            if matches >= required_matches:
                log(f"POST_CONFIRMED_IN_CONTENT_LIST:{content_caption_key(caption)}")
                return True
        except Exception:
            pass
        if time.monotonic() >= next_refresh:
            try:
                page.reload(wait_until="domcontentloaded", timeout=45_000)
            except Exception:
                pass
            if background_tick is not None:
                background_tick()
            next_refresh = time.monotonic() + 60
        page.wait_for_timeout(5_000)
    return False


def transcode_for_remote_upload(
    video_path: Path,
    destination: Path,
    target_bytes: int,
) -> Path:
    """Create a sub-50 MiB H.264 copy for Playwright's remote CDP transport."""
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        duration = float(probe.stdout.strip())
    except Exception as exc:
        raise UploadError(f"Durasi video besar tidak dapat dibaca untuk staging CDP: {exc}") from exc
    if duration <= 0:
        raise UploadError("Durasi video besar tidak valid untuk staging CDP.")

    audio_bitrate = 128_000
    total_bitrate = int((target_bytes * 8 / duration) * 0.94)
    video_bitrate = max(350_000, total_bitrate - audio_bitrate)
    passlog = destination.with_suffix("")
    common = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        str(video_bitrate),
        "-maxrate",
        str(video_bitrate),
        "-bufsize",
        str(video_bitrate * 2),
        "-pix_fmt",
        "yuv420p",
        "-passlogfile",
        str(passlog),
    ]
    try:
        subprocess.run(
            [*common, "-an", "-pass", "1", "-f", "mp4", os.devnull],
            capture_output=True,
            text=True,
            timeout=900,
            check=True,
        )
        subprocess.run(
            [
                *common,
                "-map",
                "0:a:0?",
                "-c:a",
                "aac",
                "-b:a",
                str(audio_bitrate),
                "-pass",
                "2",
                "-movflags",
                "+faststart",
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=900,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip().splitlines()[-1:]
        raise UploadError(
            "Video besar tidak dapat disiapkan untuk transfer CDP: "
            + (detail[0] if detail else str(exc))
        ) from exc
    if not destination.is_file() or destination.stat().st_size >= REMOTE_FILE_TRANSFER_LIMIT_BYTES:
        size_mb = destination.stat().st_size / (1024 * 1024) if destination.is_file() else 0
        raise UploadError(
            f"Hasil staging CDP masih terlalu besar ({size_mb:.2f} MiB; batas 50 MiB)."
        )
    return destination


def upload_video(
    page,
    video_path: Path,
    caption: str,
    dry_run: bool,
    target_handle: str,
    *,
    remote_browser: bool = False,
    background_tick: Callable[[], bool] | None = None,
) -> None:
    previous_content_matches: int | None = None
    previous_post_ids: set[str] | None = None
    try:
        previous_content_matches, previous_post_ids = tiktok_content_snapshot(page, caption)
        log(f"POST_BASELINE_MATCHES:{previous_content_matches}")
        if previous_post_ids is None:
            log("POST_BASELINE_VISIBLE_IDS:unavailable")
        else:
            log(f"POST_BASELINE_VISIBLE_IDS:{len(previous_post_ids)}")
    except Exception as exc:
        log(f"POST_BASELINE_UNAVAILABLE:{str(exc).splitlines()[0][:180]}")
    if (
        not dry_run
        and previous_content_matches
        and previous_content_matches > 0
        and previous_post_ids is not None
    ):
        # Recover after a worker/browser disconnect that happened after TikTok
        # accepted the post. Selecting the same file again would duplicate it.
        log(f"POST_ALREADY_PRESENT:{content_caption_key(caption)}")
        log("UPLOAD_CONFIRMED:private")
        log(f"VIDEO_URL:https://www.tiktok.com/@{clean_handle(target_handle)}")
        return
    goto(page, UPLOAD_URL)
    page.wait_for_timeout(1500)
    if background_tick is not None:
        background_tick()
    if "/login" in page.url.casefold():
        raise UploadError("TikTok meminta login ulang; file belum dipilih.")
    # Resume rather than discard: the browser may already hold the fully
    # transferred file from an interrupted worker.
    recovered_draft = recover_interrupted_upload_draft(page, video_path)
    dismiss_upload_overlays(page)
    file_input = None
    if not recovered_draft:
        file_input = page.locator('input[type="file"]').first
        try:
            file_input.wait_for(state="attached", timeout=20_000)
        except Exception as exc:
            save_debug(page, "upload-input-missing")
            raise UploadError("Input upload TikTok tidak ditemukan. Periksa sesi dan halaman TikTok Studio.") from exc
    staging_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        if remote_browser:
            # Let Playwright use its supported remote-file transfer. Payload
            # dictionaries bypass its 50 MiB guard and can freeze DraftJS/CDP.
            upload_path = video_path
            direct_max_bytes, target_bytes = remote_file_staging_sizes()
            if video_path.stat().st_size >= direct_max_bytes:
                staging_directory = tempfile.TemporaryDirectory(prefix="clipforge-tiktok-cdp-")
                upload_path = transcode_for_remote_upload(
                    video_path,
                    Path(staging_directory.name) / video_path.name,
                    target_bytes,
                )
                log(
                    f"Video {video_path.stat().st_size / (1024 * 1024):.2f} MiB "
                    f"disiapkan menjadi {upload_path.stat().st_size / (1024 * 1024):.2f} MiB untuk CDP."
                )
            upload_file: str = str(upload_path.resolve())
            log(f"Mengirim {video_path.name} ke Chrome TikTok melalui transfer file CDP...")
        else:
            upload_file = str(video_path.resolve())
        if file_input is not None:
            file_input.set_input_files(
                upload_file,
                timeout=env_int(
                    "TIKTOK_FILE_INPUT_TIMEOUT_MS",
                    DEFAULT_FILE_INPUT_TIMEOUT_MS,
                    minimum=60_000,
                ),
            )
    except Exception as exc:
        transfer_recovered = False
        if remote_browser:
            try:
                transfer_recovered = upload_editor_has_requested_file(page, video_path)
                if not transfer_recovered:
                    transfer_recovered = recover_interrupted_upload_draft(page, video_path)
            except UploadError:
                raise
        if transfer_recovered:
            recovered_draft = True
            log(
                "CDP_FILE_TRANSFER_RECOVERED: Playwright melaporkan error, tetapi file yang sama "
                "sudah siap di editor TikTok; proses dilanjutkan tanpa transfer ulang."
            )
        else:
            save_debug(page, "upload-file-select-failed")
            detail = str(exc).strip().splitlines()[0][:240] or type(exc).__name__
            if remote_browser:
                raise UploadError(
                    "Transfer file CDP TikTok gagal sebelum posting; "
                    f"tidak ada posting yang dibuat. Detail: {detail}"
                ) from exc
            raise UploadError(
                "TikTok tidak dapat menerima file video; "
                f"tidak ada posting yang dibuat. Detail: {detail}"
            ) from exc
    finally:
        if staging_directory is not None:
            staging_directory.cleanup()
    log(
        f"Video draft dilanjutkan: {video_path.name}"
        if recovered_draft
        else f"Video dipilih: {video_path.name}"
    )
    if background_tick is not None:
        background_tick()
    dismiss_upload_overlays(page)
    set_caption(page, caption)
    set_only_you(page)
    if background_tick is not None:
        background_tick()

    if dry_run:
        log("DRY_RUN: form siap dengan privasi Only you; tombol Post tidak diklik.")
        return

    log("Menunggu pemrosesan video selesai dan tombol Post aktif...")
    post_ready_timeout_ms = env_int(
        "TIKTOK_POST_READY_TIMEOUT_MS",
        DEFAULT_POST_READY_TIMEOUT_MS,
        minimum=MIN_POST_READY_TIMEOUT_MS,
    )
    post_button = wait_for_post_button(
        page,
        post_ready_timeout_ms,
        background_tick=background_tick,
    )
    if post_button is None:
        progress = upload_progress_text(page)
        save_debug(page, "post-button-not-ready")
        progress_hint = f" (pemrosesan terakhir {progress})" if progress else ""
        raise UploadError(
            f"Tombol Post TikTok belum aktif setelah {post_ready_timeout_ms // 1000} detik"
            f"{progress_hint}; video tidak diterbitkan."
        )
    # TikTok may restore its filename-derived draft while the video is being
    # processed. Replace and verify the caption again at the last safe moment,
    # after processing finishes but before Post is clicked.
    set_caption(page, caption)
    if not post_button_is_enabled(post_button):
        post_button = wait_for_post_button(
            page,
            MIN_POST_READY_TIMEOUT_MS,
            background_tick=background_tick,
        )
    if post_button is None:
        save_debug(page, "post-button-disabled-after-caption")
        raise UploadError(
            "Tombol Post TikTok menjadi tidak aktif setelah caption diverifikasi; "
            "video tidak diterbitkan."
        )
    submission_state, response_handler = monitor_post_submission_response(page)
    try:
        post_button.click(timeout=10_000)
        log("Tombol Post diklik setelah privasi Only you terverifikasi.")
        if background_tick is not None:
            background_tick()

        wait_for_post_submission(
            page,
            timeout_ms=env_int(
                "TIKTOK_POST_SUBMIT_SETTLE_MS",
                45_000,
                minimum=15_000,
            ),
            background_tick=background_tick,
            submission_state=submission_state,
            post_button=post_button,
        )
    finally:
        stop_post_submission_monitor(page, response_handler)

    confirmed = wait_for_new_tiktok_post(
        page,
        caption,
        previous_content_matches,
        timeout_ms=env_int(
            "TIKTOK_POST_CONFIRM_TIMEOUT_MS",
            300_000,
            minimum=90_000,
        ),
        background_tick=background_tick,
        previous_post_ids=previous_post_ids,
    )
    if not confirmed:
        save_debug(page, "confirmation-missing")
        raise UploadError(
            "TikTok tidak menampilkan video baru di Studio Posts setelah tombol Post diklik. "
            "Status tidak ditandai berhasil; periksa daftar Posts sebelum mencoba ulang."
        )
    log("UPLOAD_CONFIRMED:private")
    log(f"VIDEO_URL:https://www.tiktok.com/@{clean_handle(target_handle)}")


def _is_retryable_browser_launch_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(
        marker in message
        for marker in (
            "target page, context or browser has been closed",
            "browser has been closed",
            "browser closed",
            "process unexpectedly closed",
        )
    )


def _launch_with_retry(factory, description: str):
    attempts = env_int("TIKTOK_BROWSER_LAUNCH_ATTEMPTS", 3)
    for attempt in range(1, attempts + 1):
        try:
            return factory()
        except Exception as exc:
            if attempt >= attempts or not _is_retryable_browser_launch_error(exc):
                raise
            log(f"Browser TikTok tertutup saat {description}; mencoba ulang ({attempt + 1}/{attempts})...")
            time.sleep(min(2.0, 0.5 * attempt))
    raise AssertionError("unreachable")


def open_context(playwright, args):
    launch_args = {"headless": not args.no_headless}
    executable_path = os.environ.get("TIKTOK_CHROME_EXECUTABLE", "").strip()
    if executable_path:
        launch_args["executable_path"] = executable_path
    if env_bool("TIKTOK_USE_DESKTOP_KEYRING", False):
        launch_args["ignore_default_args"] = ["--password-store=basic", "--use-mock-keychain"]
    browser_args = ["--disable-dev-shm-usage"]
    if args.cdp_url:
        browser = _launch_with_retry(
            lambda: playwright.chromium.connect_over_cdp(args.cdp_url, timeout=15_000),
            "menghubungkan browser login GUI",
        )
        context = browser.contexts[0] if browser.contexts else browser.new_context(locale="id-ID")
        return context, browser
    profile_dir = Path(args.chromium_user_data_dir).expanduser() if args.chromium_user_data_dir else None
    if profile_dir and profile_dir.is_dir():
        profile_args = list(browser_args)
        if args.chromium_profile_directory:
            profile_args.append(f"--profile-directory={args.chromium_profile_directory}")
        context = _launch_with_retry(
            lambda: playwright.chromium.launch_persistent_context(
                str(profile_dir), args=profile_args, **launch_args
            ),
            "membuka profile login",
        )
        return context, None
    browser = _launch_with_retry(
        lambda: playwright.chromium.launch(args=browser_args, **launch_args),
        "memulai browser",
    )
    state = str(args.state) if Path(args.state).is_file() else None
    context = browser.new_context(storage_state=state, locale="id-ID")
    return context, browser


def run(args) -> int:
    sync_playwright, _ = import_playwright()
    with sync_playwright() as playwright:
        context, browser = open_context(playwright, args)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(20_000)
            if (
                args.cdp_url
                and args.command != "login"
                and env_bool("TIKTOK_MINIMIZE_CDP_BROWSER", True)
            ):
                minimize_cdp_browser(context, page)
            if args.command == "login":
                login_and_capture(
                    page,
                    context,
                    Path(args.state),
                    args.target_handle,
                    args.target_email,
                    args.timeout,
                )
                if args.cdp_url and env_bool("TIKTOK_CLOSE_CDP_AFTER_LOGIN", False):
                    try:
                        browser.close()
                        log("Chrome login TikTok ditutup setelah session tersimpan.")
                    except Exception as exc:
                        log(f"Chrome login TikTok belum dapat ditutup otomatis: {exc}")
                elif args.cdp_url and env_bool("TIKTOK_MINIMIZE_CDP_BROWSER", True):
                    minimize_cdp_browser(context, page)
                return 0
            validate_target_account(page, args.target_handle, args.target_email)
            save_session_state(context, Path(args.state))
            log(f"SESSION_SAVED:{args.state}")
            if args.command == "check-login":
                return 0
            video_path = Path(args.video).expanduser()
            if not video_path.is_file():
                raise UploadError(f"File video tidak ditemukan: {video_path}")
            background_tick = None
            if args.cdp_url and env_bool("TIKTOK_MINIMIZE_CDP_BROWSER", True):
                background_tick = lambda: minimize_cdp_browser(context, page)
            upload_video(
                page,
                video_path,
                args.caption,
                args.dry_run,
                args.target_handle,
                remote_browser=bool(args.cdp_url),
                background_tick=background_tick,
            )
            save_session_state(context, Path(args.state))
            return 0
        finally:
            # A CDP browser is the user's persistent TikTok login browser. Only
            # disconnect when Playwright exits; closing its default context or
            # Browser object here would kill the reusable Chrome session.
            if not args.cdp_url:
                try:
                    context.close()
                except Exception:
                    pass
                if browser is not None and browser.is_connected():
                    browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Uploader TikTok private-first untuk ClipForge.")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--chromium-user-data-dir", default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--chromium-profile-directory", default=DEFAULT_PROFILE_NAME)
    parser.add_argument("--cdp-url", default="")
    parser.add_argument("--target-handle", default=DEFAULT_HANDLE)
    parser.add_argument("--target-email", default=DEFAULT_EMAIL)
    parser.add_argument("--no-headless", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-login")
    login = subparsers.add_parser("login")
    login.add_argument("--timeout", type=int, default=300)
    upload = subparsers.add_parser("upload")
    upload.add_argument("video")
    upload.add_argument("--caption", default="")
    upload.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except UploadError as exc:
        log(f"USER_ERROR:{exc}")
        return 2
    except KeyboardInterrupt:
        log("USER_ERROR:Uploader TikTok dihentikan.")
        return 130
    except Exception as exc:
        log(f"USER_ERROR:Uploader TikTok gagal: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
