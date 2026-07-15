from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path(os.environ.get("YOUTUBE_PLAYWRIGHT_STATE", BASE_DIR / "data" / "youtube_storage_state.json"))
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("YOUTUBE_UPLOAD_TIMEOUT_SECONDS", "1800"))
DEFAULT_CHROMIUM_USER_DATA_DIR = os.environ.get("YOUTUBE_CHROMIUM_USER_DATA_DIR", "").strip()
DEFAULT_CHROMIUM_PROFILE_DIRECTORY = os.environ.get("YOUTUBE_CHROMIUM_PROFILE_DIRECTORY", "").strip()
DEFAULT_TARGET_EMAIL = os.environ.get("YOUTUBE_TARGET_EMAIL", "fendysketsa@gmail.com").strip()
DEFAULT_CDP_URL = os.environ.get("YOUTUBE_CDP_URL", "http://127.0.0.1:9222").strip()


class UploadError(RuntimeError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def log(message: str) -> None:
    print(message, flush=True)


def import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only in deployed runtime.
        raise UploadError(
            "Playwright belum terpasang. Jalankan `python -m pip install -r requirements.txt` "
            "dan `python -m playwright install chromium`."
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


def first_visible(page, selectors: Iterable[str], timeout_ms: int = 2500):
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() and locator.is_visible(timeout=250):
                    return locator
            except Exception as exc:
                last_error = exc
        time.sleep(0.1)
    raise UploadError(f"Elemen YouTube Studio tidak ditemukan: {', '.join(selectors)}") from last_error


def click_text(page, patterns: Iterable[str], *, timeout_ms: int = 8000, optional: bool = False) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for pattern in patterns:
            try:
                locator = page.get_by_text(re.compile(pattern, re.I)).first
                if locator.count() and locator.is_visible(timeout=300):
                    locator.click(timeout=1500)
                    return True
            except Exception as exc:
                last_error = exc
        time.sleep(0.15)
    if optional:
        return False
    raise UploadError(f"Tombol/teks tidak ditemukan: {', '.join(patterns)}") from last_error


def click_role_button(page, patterns: Iterable[str], *, timeout_ms: int = 8000, optional: bool = False) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for pattern in patterns:
            try:
                locator = page.get_by_role("button", name=re.compile(pattern, re.I)).first
                if locator.count() and locator.is_visible(timeout=300):
                    locator.click(timeout=1500)
                    return True
            except Exception as exc:
                last_error = exc
        time.sleep(0.15)
    if optional:
        return False
    raise UploadError(f"Tombol tidak ditemukan: {', '.join(patterns)}") from last_error


def normalize_channel_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower().lstrip("@"))


def page_identity_text(page) -> str:
    script = """
    () => {
      const chunks = [];
      const add = (value) => {
        if (typeof value === 'string' && value.trim()) chunks.push(value.trim());
      };
      const walk = (root, depth = 0) => {
        if (!root || depth > 8) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
        let count = 0;
        while (count < 6000) {
          const node = walker.nextNode();
          if (!node) break;
          count += 1;
          if (node.nodeType === Node.TEXT_NODE) {
            add(node.textContent);
            continue;
          }
          if (node.nodeType === Node.ELEMENT_NODE) {
            add(node.getAttribute('aria-label'));
            add(node.getAttribute('title'));
            add(node.getAttribute('alt'));
            if (node.shadowRoot) walk(node.shadowRoot, depth + 1);
          }
        }
      };
      add(document.title);
      add(document.body?.innerText);
      walk(document);
      return chunks.join('\\n').slice(0, 200000);
    }
    """
    try:
        return str(page.evaluate(script) or "")
    except Exception:
        try:
            return page.locator("body").inner_text(timeout=3000)
        except Exception:
            return ""


def normalized_page_text(page) -> str:
    return normalize_channel_text(page_identity_text(page))


def page_matches_allowed_identity(page, target_channel: str, target_email: str) -> bool:
    expected_channel = normalize_channel_text(target_channel)
    expected_email = normalize_channel_text(target_email)
    if not expected_channel and not expected_email:
        return True
    body = normalized_page_text(page)
    return bool(
        body
        and (
            (expected_channel and expected_channel in body)
            or (expected_email and expected_email in body)
        )
    )


def google_account_matches_target(page, target_email: str) -> bool:
    expected_email = normalize_channel_text(target_email)
    if not expected_email:
        return False

    account_page = None
    try:
        account_page = page.context.new_page()
        account_page.goto("https://myaccount.google.com/email", wait_until="domcontentloaded", timeout=45000)
        account_page.wait_for_load_state("domcontentloaded", timeout=10000)
        text = normalized_page_text(account_page)
        return bool(text and expected_email in text)
    except Exception:
        return False
    finally:
        if account_page is not None:
            try:
                account_page.close()
            except Exception:
                pass


def identity_label(target_channel: str, target_email: str) -> str:
    parts = [value for value in (target_channel.strip(), target_email.strip()) if value]
    return " / ".join(parts) or "tidak dikonfigurasi"


def ensure_target_identity(page, target_channel: str, target_email: str) -> None:
    label = identity_label(target_channel, target_email)
    if label == "tidak dikonfigurasi":
        return

    if page_matches_allowed_identity(page, target_channel, target_email):
        log(f"Identitas YouTube target terdeteksi: {label}.")
        return

    clicked_menu = False
    for selector in (
        "#avatar-btn",
        'button[aria-label*="Account"]',
        'button[aria-label*="Akun"]',
        'ytcp-topbar-menu-button-renderer button',
    ):
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=1000):
                locator.click(timeout=2500)
                clicked_menu = True
                time.sleep(0.8)
                if page_matches_allowed_identity(page, target_channel, target_email):
                    log(f"Identitas YouTube target terdeteksi: {label}.")
                    page.keyboard.press("Escape")
                    return
        except Exception:
            continue
    if target_email and google_account_matches_target(page, target_email):
        log(f"Email Google target terdeteksi: {target_email}.")
        if clicked_menu:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
        return
    if clicked_menu:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    raise UploadError(
        f"Sesi YouTube/Chromium bukan channel atau akun target '{label}'. "
        "Upload dibatalkan agar tidak salah akun."
    )


def page_contains_channel(page, target_channel: str) -> bool:
    expected = normalize_channel_text(target_channel)
    if not expected:
        return True
    try:
        body = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False
    return expected in normalize_channel_text(body)


def fill_textbox(page, index: int, value: str, label: str) -> None:
    if not value:
        return
    boxes = page.locator("#textbox")
    try:
        box = boxes.nth(index)
        box.click(timeout=8000)
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(value)
        log(f"{label} diisi.")
    except Exception as exc:
        raise UploadError(f"Gagal mengisi {label}. UI YouTube Studio mungkin berubah.") from exc


def ensure_logged_in(page) -> None:
    url = page.url.lower()
    if "accounts.google.com" in url or "signin" in url:
        raise UploadError(
            "Sesi YouTube belum login atau sudah kedaluwarsa. Jalankan "
            "`python youtube_uploader.py login` di environment yang sama."
        )
    if page.get_by_text(re.compile(r"sign in|login|masuk", re.I)).first.count():
        raise UploadError("YouTube Studio meminta login ulang. Jalankan mode login manual.")


def goto_studio(page, timeout_ms: int = 60000) -> None:
    last_error = ""
    for attempt in range(2):
        try:
            page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 15000))
            return
        except Exception as exc:
            last_error = str(exc)
            if attempt == 0:
                time.sleep(2)
    raise UploadError(
        "Browser Playwright tidak bisa membuka https://studio.youtube.com. "
        "Coba tekan Sync Session Browser setelah Chrome login terbuka, lalu Retry. "
        f"Detail: {last_error}"
    )


def open_upload_dialog(page, target_channel: str = "", target_email: str = "") -> None:
    log("Membuka YouTube Studio...")
    goto_studio(page)
    ensure_logged_in(page)
    ensure_target_identity(page, target_channel, target_email)

    log("Membuka dialog upload...")
    create_clicked = False
    for selector in (
        'ytcp-button#create-icon',
        'tp-yt-paper-icon-button[aria-label*="Create"]',
        'tp-yt-paper-icon-button[aria-label*="Buat"]',
        'button[aria-label*="Create"]',
        'button[aria-label*="Buat"]',
    ):
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=1000):
                locator.click(timeout=3000)
                create_clicked = True
                break
        except Exception:
            continue
    if not create_clicked:
        click_role_button(page, [r"create|buat"], timeout_ms=6000)

    if not click_text(page, [r"upload videos?", r"unggah video", r"upload video"], timeout_ms=8000, optional=True):
        page.goto("https://studio.youtube.com/channel/UC/videos/upload", wait_until="domcontentloaded", timeout=60000)


def set_visibility(page, visibility: str) -> None:
    labels = {
        "private": [r"private", r"pribadi"],
        "unlisted": [r"unlisted", r"tidak publik"],
        "public": [r"public", r"publik"],
    }[visibility]
    log(f"Mengatur visibilitas: {visibility}.")
    for label in labels:
        try:
            page.get_by_label(re.compile(label, re.I)).first.click(timeout=2500)
            return
        except Exception:
            pass
    click_text(page, labels, timeout_ms=5000)


def fill_tags(page, tags: str) -> None:
    clean_tags = ", ".join(tag.strip().lstrip("#") for tag in tags.split(",") if tag.strip())
    if not clean_tags:
        return
    if click_text(page, [r"show more", r"tampilkan lebih banyak"], timeout_ms=4000, optional=True):
        log("Membuka pengaturan lanjutan.")
    for pattern in (r"tags", r"tag"):
        try:
            field = page.get_by_label(re.compile(pattern, re.I)).first
            if field.count() and field.is_visible(timeout=1000):
                field.fill(clean_tags, timeout=3000)
                log("Tags diisi.")
                return
        except Exception:
            pass
    log("Kolom tags tidak ditemukan; upload dilanjutkan tanpa tags UI.")


def select_playlist(page, playlist: str) -> None:
    playlist_name = playlist.strip()
    if not playlist_name:
        return

    log(f"Memilih playlist: {playlist_name}.")
    opened = False
    for selector in (
        "ytcp-video-metadata-playlists ytcp-dropdown-trigger",
        "ytcp-video-metadata-playlists #dropdown-trigger",
        'ytcp-dropdown-trigger[aria-label*="Playlist"]',
        'button[aria-label*="Playlist"]',
    ):
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=1000):
                locator.click(timeout=2500)
                opened = True
                break
        except Exception:
            continue

    if not opened:
        opened = click_role_button(page, [r"select|pilih|playlist"], timeout_ms=5000, optional=True)
    if not opened:
        raise UploadError("Dropdown playlist tidak ditemukan di YouTube Studio.")

    time.sleep(0.8)
    escaped = re.escape(playlist_name)
    try:
        checkbox = page.get_by_role("checkbox", name=re.compile(escaped, re.I)).first
        if checkbox.count():
            if not checkbox.is_checked(timeout=1000):
                checkbox.click(timeout=3000)
            click_role_button(page, [r"done|selesai|simpan|ok"], timeout_ms=8000, optional=True)
            log(f"Playlist dipilih: {playlist_name}.")
            return
    except Exception:
        pass

    if not click_text(page, [escaped], timeout_ms=5000, optional=True):
        raise UploadError(f"Playlist '{playlist_name}' tidak ditemukan di YouTube Studio.")
    click_role_button(page, [r"done|selesai|simpan|ok"], timeout_ms=8000, optional=True)
    log(f"Playlist dipilih: {playlist_name}.")


def wait_for_copyright_checks(page, timeout_ms: int, require_checks: bool = True) -> None:
    log("Menunggu YouTube Studio Checks untuk copyright/restriction...")
    deadline = time.monotonic() + timeout_ms / 1000
    issue_patterns = (
        r"copyright claim",
        r"copyright issue",
        r"copyright.*found",
        r"restrictions? found",
        r"checks? found",
        r"klaim hak cipta",
        r"masalah hak cipta",
        r"hak cipta.*ditemukan",
        r"pembatasan.*ditemukan",
    )
    clean_patterns = (
        r"no issues found",
        r"no copyright issues? found",
        r"tidak ada masalah",
    )
    complete_patterns = (
        r"checks complete",
        r"pemeriksaan selesai",
    )

    last_body = ""
    while time.monotonic() < deadline:
        try:
            body = page.locator("body").inner_text(timeout=3000)
        except Exception:
            time.sleep(1)
            continue
        lowered = body.lower()
        last_body = re.sub(r"\s+", " ", body).strip()[:500]
        if any(re.search(pattern, lowered, re.I) for pattern in clean_patterns):
            log("YouTube Studio Checks selesai: tidak ada masalah terdeteksi.")
            return
        if any(re.search(pattern, lowered, re.I) for pattern in issue_patterns):
            raise UploadError(
                "YouTube Studio mendeteksi potensi copyright/restriction pada clip ini. "
                "Upload dibatalkan sebelum publish agar channel tetap aman."
            )
        if any(re.search(pattern, lowered, re.I) for pattern in complete_patterns):
            log("YouTube Studio Checks selesai: tidak ada masalah terdeteksi.")
            return
        time.sleep(2)

    if require_checks:
        raise UploadError(
            "YouTube Studio Checks tidak dapat dikonfirmasi sebelum timeout. "
            f"Upload dibatalkan demi keamanan. Cuplikan halaman: {last_body}"
        )
    log("Checks belum terkonfirmasi; melanjutkan karena require checks dinonaktifkan.")


def extract_video_url(page) -> str:
    candidates = [
        'a[href*="youtu.be/"]',
        'a[href*="youtube.com/watch"]',
        'ytcp-video-info a',
    ]
    for selector in candidates:
        try:
            items = page.locator(selector)
            for index in range(min(items.count(), 8)):
                href = items.nth(index).get_attribute("href") or ""
                if "youtu.be/" in href or "watch?v=" in href:
                    return href
        except Exception:
            continue
    body = page.locator("body").inner_text(timeout=3000)
    match = re.search(r"https?://(?:youtu\.be/|www\.youtube\.com/watch\?v=)[^\s)]+", body)
    return match.group(0) if match else ""


def run_login(args: argparse.Namespace) -> None:
    sync_playwright, _ = import_playwright()
    state_path = Path(args.state).expanduser().resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    headless = env_bool("YOUTUBE_LOGIN_HEADLESS", False)
    chromium_user_data_dir = Path(args.chromium_user_data_dir).expanduser().resolve() if args.chromium_user_data_dir else None
    with sync_playwright() as playwright:
        browser = None
        launch_args = []
        if chromium_user_data_dir is not None and args.chromium_profile_directory:
            launch_args.append(f"--profile-directory={args.chromium_profile_directory}")
        if chromium_user_data_dir is not None:
            chromium_user_data_dir.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                str(chromium_user_data_dir),
                headless=headless,
                slow_mo=int(os.environ.get("YOUTUBE_BROWSER_SLOW_MO_MS", "60")),
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                viewport={"width": 1440, "height": 1000},
                args=launch_args,
            )
            log(f"Login memakai profile Chromium: {chromium_user_data_dir}")
        else:
            browser = playwright.chromium.launch(
                headless=headless,
                slow_mo=int(os.environ.get("YOUTUBE_BROWSER_SLOW_MO_MS", "60")),
                args=launch_args,
            )
            context = browser.new_context(locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"))
        page = context.new_page()
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)
        log("Login ke akun YouTube di browser yang terbuka.")
        if args.auto_close:
            log("Setelah login berhasil dan dashboard YouTube Studio tampil, browser akan ditutup otomatis.")
            deadline = time.monotonic() + max(60, int(args.timeout)) 
            last_error = ""
            while time.monotonic() < deadline:
                try:
                    current_url = page.url.lower()
                    if "studio.youtube.com" not in current_url and "accounts.google.com" not in current_url:
                        page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    ensure_logged_in(page)
                    break
                except Exception as exc:
                    last_error = str(exc)
                    time.sleep(3)
            else:
                raise UploadError(f"Login YouTube belum berhasil sebelum timeout. Terakhir: {last_error}")
        else:
            log("Setelah dashboard YouTube Studio tampil, kembali ke terminal lalu tekan Enter.")
            input()
            page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            ensure_logged_in(page)
        context.storage_state(path=str(state_path))
        context.close()
        if browser is not None:
            browser.close()
    log(f"Sesi YouTube tersimpan: {state_path}")


def run_capture_session(args: argparse.Namespace) -> None:
    sync_playwright, _ = import_playwright()
    state_path = Path(args.state).expanduser().resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        log(f"Menghubungkan ke Chrome remote debugging: {args.cdp_url}")
        try:
            browser = playwright.chromium.connect_over_cdp(args.cdp_url, timeout=15000)
        except Exception as exc:
            raise UploadError(
                "Chrome remote debugging belum aktif. Jalankan Chrome dengan "
                "`google-chrome --remote-debugging-port=9222 --user-data-dir=/home/fcn88/.config/google-chrome` "
                "lalu login ke YouTube Studio."
            ) from exc
        contexts = browser.contexts or [browser.new_context()]
        pages = [item for context in contexts for item in context.pages]
        page = next((item for item in pages if "studio.youtube.com" in item.url.lower()), None)
        if page is None:
            context = contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
        if "studio.youtube.com" not in page.url.lower():
            goto_studio(page)
        else:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
        ensure_logged_in(page)
        ensure_target_identity(page, args.target_channel, args.target_email)
        page.context.storage_state(path=str(state_path))
        browser.close()
    log(f"Sesi YouTube dari browser tersimpan: {state_path}")


def run_upload(args: argparse.Namespace) -> None:
    sync_playwright, PlaywrightTimeoutError = import_playwright()
    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        raise UploadError(f"File video tidak ditemukan: {video_path}")

    state_path = Path(args.state).expanduser().resolve()
    chromium_user_data_dir = Path(args.chromium_user_data_dir).expanduser().resolve() if args.chromium_user_data_dir else None
    if chromium_user_data_dir is not None and not chromium_user_data_dir.is_dir():
        raise UploadError(f"Folder profile Chromium tidak ditemukan: {chromium_user_data_dir}")
    if chromium_user_data_dir is None and not state_path.is_file():
        raise UploadError(
            f"File sesi YouTube belum ada: {state_path}. Jalankan `python youtube_uploader.py login` terlebih dahulu "
            "atau set YOUTUBE_CHROMIUM_USER_DATA_DIR ke profile Chromium yang sudah login."
        )

    thumbnail_path = Path(args.thumbnail).expanduser().resolve() if args.thumbnail else None
    if thumbnail_path is not None and not thumbnail_path.is_file():
        raise UploadError(f"File thumbnail tidak ditemukan: {thumbnail_path}")

    headless = args.headless if args.headless is not None else env_bool("YOUTUBE_HEADLESS", True)
    slow_mo = int(os.environ.get("YOUTUBE_BROWSER_SLOW_MO_MS", "0"))
    timeout_ms = max(60, int(args.timeout)) * 1000

    with sync_playwright() as playwright:
        browser = None
        context = None
        launch_args = []
        if chromium_user_data_dir is not None and args.chromium_profile_directory:
            launch_args.append(f"--profile-directory={args.chromium_profile_directory}")
        if chromium_user_data_dir is not None:
            log(f"Menggunakan profile Chromium: {chromium_user_data_dir}")
            context = playwright.chromium.launch_persistent_context(
                str(chromium_user_data_dir),
                headless=headless,
                slow_mo=slow_mo,
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                viewport={"width": 1440, "height": 1000},
                args=launch_args,
            )
        else:
            browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo, args=launch_args)
            context = browser.new_context(
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                storage_state=str(state_path),
                viewport={"width": 1440, "height": 1000},
            )
        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            open_upload_dialog(page, args.target_channel, args.target_email)
            file_input = page.locator('input[type="file"]').first
            file_input.set_input_files(str(video_path), timeout=30000)
            log(f"Video dipilih: {video_path.name}")

            first_visible(page, ['ytcp-uploads-dialog', '#textbox'], timeout_ms=60000)
            fill_textbox(page, 0, args.title[:100], "judul")
            fill_textbox(page, 1, args.description[:5000], "deskripsi")

            if thumbnail_path is not None:
                try:
                    inputs = page.locator('input[type="file"]')
                    if inputs.count() > 1:
                        inputs.nth(1).set_input_files(str(thumbnail_path), timeout=30000)
                        log(f"Thumbnail dipilih: {thumbnail_path.name}")
                    else:
                        log("Input thumbnail tidak ditemukan; upload dilanjutkan tanpa thumbnail.")
                except Exception:
                    log("Thumbnail tidak dapat dipasang otomatis; upload video tetap dilanjutkan.")

            if args.made_for_kids:
                click_text(page, [r"yes,.*made for kids", r"ya,.*anak"], timeout_ms=8000)
            else:
                click_text(page, [r"no,.*not made for kids", r"tidak,.*anak"], timeout_ms=8000)
            log("Setelan audiens dipilih.")
            select_playlist(page, args.playlist)
            fill_tags(page, args.tags)

            for step in range(3):
                click_role_button(page, [r"next|berikutnya"], timeout_ms=20000)
                log(f"Langkah upload {step + 1}/3 dilewati.")
                if step == 1:
                    wait_for_copyright_checks(
                        page,
                        min(timeout_ms, int(os.environ.get("YOUTUBE_CHECKS_TIMEOUT_SECONDS", "300")) * 1000),
                        args.require_copyright_checks,
                    )

            set_visibility(page, args.visibility)
            video_url = extract_video_url(page)
            if video_url:
                log(f"VIDEO_URL: {video_url}")

            if args.dry_run:
                log("Dry-run aktif; proses berhenti sebelum publish/save final.")
                return

            click_role_button(page, [r"publish|save|done|publikasikan|simpan|selesai"], timeout_ms=30000)
            log("Menunggu konfirmasi upload...")
            try:
                page.get_by_text(re.compile(r"video (published|uploaded|saved)|selesai|dipublikasikan|disimpan", re.I)).first.wait_for(
                    timeout=min(timeout_ms, 180000)
                )
            except PlaywrightTimeoutError:
                log("Konfirmasi final tidak ditemukan, tetapi tombol final sudah ditekan.")

            final_url = video_url or extract_video_url(page)
            if final_url:
                log(f"VIDEO_URL: {final_url}")
            context.storage_state(path=str(state_path))
        finally:
            context.close()
            if browser is not None:
                browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload ClipForge outputs to YouTube Studio with Playwright.")
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH), help="Path storage_state Playwright untuk sesi YouTube.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="Buka browser untuk login YouTube manual dan simpan sesi.")
    login.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    login.add_argument("--auto-close", action="store_true")
    login.add_argument("--timeout", type=int, default=600)
    login.add_argument("--chromium-user-data-dir", default=DEFAULT_CHROMIUM_USER_DATA_DIR)
    login.add_argument("--chromium-profile-directory", default=DEFAULT_CHROMIUM_PROFILE_DIRECTORY)

    capture = subparsers.add_parser("capture-session", help="Ambil sesi dari Chrome remote debugging yang sudah login.")
    capture.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    capture.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    capture.add_argument("--target-channel", default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundy8812"))
    capture.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL)

    upload = subparsers.add_parser("upload", help="Upload satu file video ke YouTube Studio.")
    upload.add_argument("video")
    upload.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    upload.add_argument("--title", required=True)
    upload.add_argument("--description", default="")
    upload.add_argument("--thumbnail", default="")
    upload.add_argument("--visibility", choices=["private", "unlisted", "public"], default=os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "private"))
    upload.add_argument("--tags", default="")
    upload.add_argument("--playlist", default=os.environ.get("YOUTUBE_DEFAULT_PLAYLIST", "Islam"))
    upload.add_argument("--target-channel", default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundy8812"))
    upload.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL)
    upload.add_argument("--chromium-user-data-dir", default="")
    upload.add_argument("--chromium-profile-directory", default=DEFAULT_CHROMIUM_PROFILE_DIRECTORY)
    upload.add_argument(
        "--require-copyright-checks",
        action=argparse.BooleanOptionalAction,
        default=env_bool("YOUTUBE_REQUIRE_COPYRIGHT_CHECKS", True),
    )
    upload.add_argument("--made-for-kids", action="store_true")
    upload.add_argument("--dry-run", action="store_true")
    upload.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    upload.add_argument("--headless", action=argparse.BooleanOptionalAction, default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "login":
            run_login(args)
        elif args.command == "capture-session":
            run_capture_session(args)
        elif args.command == "upload":
            run_upload(args)
        else:  # pragma: no cover
            parser.error("Unknown command")
    except UploadError as exc:
        log(f"USER_ERROR: {exc}")
        return 2
    except KeyboardInterrupt:
        log("Upload dibatalkan.")
        return 130
    except Exception as exc:
        log(f"USER_ERROR: Upload YouTube gagal: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
