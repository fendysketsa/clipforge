from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


def import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - deployment dependency
        raise UploadError(
            "Playwright belum terpasang. Install requirements backend dan browser Chromium."
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


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


def validate_target_account(page, target_handle: str, target_email: str = "") -> None:
    expected = clean_handle(target_handle)
    if not expected:
        raise UploadError("Target handle TikTok belum dikonfigurasi.")
    goto(page, f"https://www.tiktok.com/@{expected}")
    page.wait_for_timeout(1800)
    if "/login" in page.url.casefold():
        raise UploadError("Sesi TikTok belum login. Buka TikTok di profile browser yang dikonfigurasi lalu login sekali.")

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
        raise UploadError(
            f"Akun browser bukan pemilik @{expected}{account_hint}, atau sesi sudah habis. "
            "Upload dihentikan sebelum file dipilih."
        )
    log(f"TARGET_ACCOUNT_CONFIRMED:@{expected}")


def login_and_capture(page, context, state_path: Path, target_handle: str, target_email: str, timeout: int) -> None:
    expected = clean_handle(target_handle)
    goto(page, "https://www.tiktok.com/login")
    log(
        f"LOGIN_REQUIRED: Selesaikan login TikTok {target_email or ''}, captcha bila muncul, "
        f"lalu pastikan profil @{expected} aktif."
    )
    deadline = time.monotonic() + max(30, timeout)
    last_check = 0.0
    while time.monotonic() < deadline:
        page.wait_for_timeout(1500)
        if time.monotonic() - last_check < 5:
            continue
        last_check = time.monotonic()
        try:
            goto(page, f"https://www.tiktok.com/@{expected}", timeout_ms=20_000)
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
                timeout_ms=1500,
            )
            if own_profile is not None:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(state_path))
                log(f"TARGET_ACCOUNT_CONFIRMED:@{expected}")
                log(f"SESSION_SAVED:{state_path}")
                return
        except Exception:
            pass
    save_debug(page, "login-timeout")
    raise UploadError(
        f"Login belum terverifikasi sebagai @{expected} dalam {timeout} detik. Tidak ada file yang diunggah."
    )


def set_caption(page, caption: str) -> None:
    editor = first_visible(
        page,
        [
            '[data-e2e="caption-editor"] [contenteditable="true"]',
            '[data-e2e="caption-editor"]',
            'div[contenteditable="true"][role="textbox"]',
            'textarea[placeholder*="caption" i]',
            'textarea[placeholder*="deskripsi" i]',
            'textarea',
        ],
        timeout_ms=15_000,
    )
    if editor is None:
        raise UploadError("Kolom caption TikTok tidak ditemukan setelah video dipilih.")
    try:
        editor.fill(caption[:2200])
    except Exception:
        editor.click()
        page.keyboard.press("Control+A")
        page.keyboard.type(caption[:2200], delay=2)
    log("Caption TikTok terisi.")


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


def upload_video(page, video_path: Path, caption: str, dry_run: bool, target_handle: str) -> None:
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
    file_input.set_input_files(str(video_path.resolve()))
    log(f"Video dipilih: {video_path.name}")
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

    confirmation = first_visible(
        page,
        [
            'text=/uploaded|posted|upload complete|berhasil diunggah|berhasil diposting/i',
            'a[href*="/tiktokstudio/content"]',
            'a[href*="/creator-center/content"]',
        ],
        timeout_ms=90_000,
    )
    if confirmation is None and "upload" in page.url.casefold():
        save_debug(page, "confirmation-missing")
        raise UploadError(
            "TikTok belum memberi konfirmasi selesai. Jangan upload ulang sebelum mengecek TikTok Studio agar tidak duplikat."
        )
    log("UPLOAD_CONFIRMED:private")
    log(f"VIDEO_URL:https://www.tiktok.com/@{clean_handle(target_handle)}")


def open_context(playwright, args):
    launch_args = {"headless": not args.no_headless}
    executable_path = os.environ.get("TIKTOK_CHROME_EXECUTABLE", "").strip()
    if executable_path:
        launch_args["executable_path"] = executable_path
    if env_bool("TIKTOK_USE_DESKTOP_KEYRING", False):
        launch_args["ignore_default_args"] = ["--password-store=basic", "--use-mock-keychain"]
    profile_dir = Path(args.chromium_user_data_dir).expanduser() if args.chromium_user_data_dir else None
    if profile_dir and profile_dir.is_dir():
        profile_args = []
        if args.chromium_profile_directory:
            profile_args.append(f"--profile-directory={args.chromium_profile_directory}")
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), args=profile_args, **launch_args
        )
        return context, None
    browser = playwright.chromium.launch(**launch_args)
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
            Path(args.state).parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(args.state))
            log(f"SESSION_SAVED:{args.state}")
            if args.command == "check-login":
                return 0
            video_path = Path(args.video).expanduser()
            if not video_path.is_file():
                raise UploadError(f"File video tidak ditemukan: {video_path}")
            upload_video(page, video_path, args.caption, args.dry_run, args.target_handle)
            context.storage_state(path=str(args.state))
            return 0
        finally:
            context.close()
            if browser is not None:
                browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Uploader TikTok private-first untuk ClipForge.")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--chromium-user-data-dir", default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--chromium-profile-directory", default=DEFAULT_PROFILE_NAME)
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
