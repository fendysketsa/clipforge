from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import tempfile
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path(
    os.environ.get("TIKTOK_PLAYWRIGHT_STATE", BASE_DIR / "data" / "tiktok_storage_state.json")
)
DEFAULT_PROFILE_DIR = os.environ.get("TIKTOK_CHROMIUM_USER_DATA_DIR", "").strip()
DEFAULT_PROFILE_NAME = os.environ.get("TIKTOK_CHROMIUM_PROFILE_DIRECTORY", "Default").strip()
DEFAULT_HANDLE = os.environ.get("TIKTOK_TARGET_HANDLE", "titikbalikislami").strip().lstrip("@")
DEFAULT_EMAIL = os.environ.get("TIKTOK_TARGET_EMAIL", "fendycn88@gmail.com").strip()
UPLOAD_URL = os.environ.get("TIKTOK_UPLOAD_URL", "https://www.tiktok.com/tiktokstudio/upload").strip()
DEBUG_DIR = Path(os.environ.get("TIKTOK_UPLOAD_DEBUG_DIR", BASE_DIR / "data" / "tiktok_debug"))
TIKTOK_AUTH_COOKIE_NAMES = frozenset({"sessionid", "sessionid_ss", "sid_tt", "sid_guard"})


class UploadError(RuntimeError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def first_visible(page, selectors: list[str], timeout_ms: int = 1500):
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
    try:
        href = page.locator('[data-e2e="nav-profile"]').first.get_attribute(
            "href", timeout=5_000
        ) or ""
    except Exception:
        href = ""
    match = re.search(r"/@([^/?#]+)", href)
    return clean_handle(match.group(1)) if match else ""


def validate_target_account(page, target_handle: str, target_email: str = "") -> None:
    expected = clean_handle(target_handle)
    if not expected:
        raise UploadError("Target handle TikTok belum dikonfigurasi.")
    if not has_authenticated_tiktok_cookie(page.context):
        raise UploadError("Sesi TikTok belum login. Klik Login TikTok lalu selesaikan CAPTCHA di Chrome.")
    goto(page, f"https://www.tiktok.com/@{expected}")
    page.wait_for_timeout(1800)
    login_button = first_visible(
        page,
        ['[data-e2e="top-login-button"]', 'button:has-text("Log in")', 'button:has-text("Masuk")'],
        timeout_ms=1_000,
    )
    if "/login" in page.url.casefold() or login_button is not None:
        raise UploadError("Sesi TikTok belum login. Klik Login TikTok lalu selesaikan CAPTCHA di Chrome.")

    signed_in_handle = current_profile_handle(page)
    if signed_in_handle == expected:
        log(f"TARGET_ACCOUNT_CONFIRMED:@{expected}")
        return

    own_profile = first_visible(
        page,
        [
            '[data-e2e="edit-profile-entrance"]',
            'button:has-text("Edit profile")',
            'button:has-text("Edit profil")',
            'button:has-text("Sunting profil")',
            'a:has-text("Edit profile")',
            'a:has-text("Edit profil")',
        ],
        timeout_ms=2200,
    )
    if own_profile is None:
        save_debug(page, "account-mismatch")
        account_hint = f" ({target_email})" if target_email else ""
        signed_in_hint = f" Browser sedang login sebagai @{signed_in_handle}." if signed_in_handle else ""
        raise UploadError(
            f"Akun browser bukan pemilik @{expected}{account_hint}, atau sesi sudah habis. "
            f"Upload dihentikan sebelum file dipilih.{signed_in_hint}"
        )
    log(f"TARGET_ACCOUNT_CONFIRMED:@{expected}")


def login_and_capture(page, context, state_path: Path, target_handle: str, target_email: str, timeout: int) -> None:
    expected = clean_handle(target_handle)
    if not expected:
        raise UploadError("Target handle TikTok belum dikonfigurasi.")
    if "tiktok.com" not in page.url.casefold():
        goto(page, "https://www.tiktok.com/login")
    log(
        f"LOGIN_REQUIRED: Selesaikan login TikTok {target_email or ''}, captcha bila muncul, "
        f"lalu pastikan akun @{expected} yang aktif. Session baru disimpan setelah akun target terverifikasi."
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


def set_caption(page, caption: str) -> None:
    editor = first_visible(
        page,
        [
            '[data-e2e="caption-editor"] [contenteditable="true"]',
            '[data-e2e="caption-editor"]',
            '.public-DraftEditor-content[contenteditable="true"]',
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
    try:
        editor.fill(caption[:2200])
    except Exception:
        editor.click()
        page.keyboard.press("Control+A")
        page.keyboard.type(caption[:2200], delay=2)
    log("Caption TikTok terisi.")


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


def upload_video(
    page,
    video_path: Path,
    caption: str,
    dry_run: bool,
    target_handle: str,
    *,
    remote_browser: bool = False,
) -> None:
    goto(page, UPLOAD_URL)
    page.wait_for_timeout(1500)
    if "/login" in page.url.casefold():
        raise UploadError("TikTok meminta login ulang; file belum dipilih.")
    file_input = page.locator('input[type="file"]').first
    try:
        file_input.wait_for(state="attached", timeout=20_000)
    except Exception as exc:
        save_debug(page, "upload-input-missing")
        raise UploadError("Input upload TikTok tidak ditemukan. Periksa sesi dan halaman TikTok Studio.") from exc
    try:
        if remote_browser:
            # The browser connected over CDP can run on the Docker host while
            # this uploader sees /app/outputs. Send bytes so Chrome does not
            # need to resolve a container-only filesystem path.
            upload_file: str | dict[str, object] = {
                "name": video_path.name,
                "mimeType": mimetypes.guess_type(video_path.name)[0] or "video/mp4",
                "buffer": video_path.read_bytes(),
            }
            log(f"Mengirim {video_path.name} ke Chrome TikTok melalui CDP...")
        else:
            upload_file = str(video_path.resolve())
        file_input.set_input_files(
            upload_file,
            timeout=max(60_000, int(os.environ.get("TIKTOK_FILE_INPUT_TIMEOUT_MS", "300000"))),
        )
    except Exception as exc:
        save_debug(page, "upload-file-select-failed")
        raise UploadError(
            "Chrome TikTok tidak dapat menerima file video. Koneksi CDP tetap aman; "
            "tidak ada posting yang dibuat."
        ) from exc
    log(f"Video dipilih: {video_path.name}")
    dismiss_upload_overlays(page)
    set_caption(page, caption)
    set_only_you(page)

    if dry_run:
        log("DRY_RUN: form siap dengan privasi Only you; tombol Post tidak diklik.")
        return

    post_button = first_visible(
        page,
        [
            '[data-e2e="post_video_button"]',
            'button:has-text("Post")',
            'button:has-text("Posting")',
            'button:has-text("Publikasikan")',
        ],
        timeout_ms=15_000,
    )
    if post_button is None or not post_button.is_enabled():
        save_debug(page, "post-button-not-ready")
        raise UploadError("Tombol Post TikTok belum siap; video tidak diterbitkan.")
    post_button.click()
    log("Tombol Post diklik setelah privasi Only you terverifikasi.")

    confirmed = False
    try:
        page.wait_for_url(
            re.compile(r"/(?:tiktokstudio|creator-center)/content(?:[/?#]|$)", re.I),
            timeout=90_000,
        )
        confirmed = True
    except Exception:
        confirmation = first_visible(
            page,
            ['text=/uploaded|posted|upload complete|berhasil diunggah|berhasil diposting/i'],
            timeout_ms=3_000,
        )
        confirmed = confirmation is not None
    if not confirmed:
        save_debug(page, "confirmation-missing")
        raise UploadError(
            "TikTok belum memberi konfirmasi selesai. Jangan upload ulang sebelum mengecek TikTok Studio agar tidak duplikat."
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
    try:
        attempts = max(1, int(os.environ.get("TIKTOK_BROWSER_LAUNCH_ATTEMPTS", "3")))
    except ValueError:
        attempts = 3
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
            if args.command == "login":
                login_and_capture(
                    page,
                    context,
                    Path(args.state),
                    args.target_handle,
                    args.target_email,
                    args.timeout,
                )
                return 0
            validate_target_account(page, args.target_handle, args.target_email)
            save_session_state(context, Path(args.state))
            log(f"SESSION_SAVED:{args.state}")
            if args.command == "check-login":
                return 0
            video_path = Path(args.video).expanduser()
            if not video_path.is_file():
                raise UploadError(f"File video tidak ditemukan: {video_path}")
            upload_video(
                page,
                video_path,
                args.caption,
                args.dry_run,
                args.target_handle,
                remote_browser=bool(args.cdp_url),
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
