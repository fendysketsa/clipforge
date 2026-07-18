from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path(os.environ.get("YOUTUBE_PLAYWRIGHT_STATE", BASE_DIR / "data" / "youtube_storage_state.json"))
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("YOUTUBE_UPLOAD_TIMEOUT_SECONDS", "900"))
DEFAULT_CHROMIUM_USER_DATA_DIR = os.environ.get("YOUTUBE_CHROMIUM_USER_DATA_DIR", "").strip()
DEFAULT_CHROMIUM_PROFILE_DIRECTORY = os.environ.get("YOUTUBE_CHROMIUM_PROFILE_DIRECTORY", "").strip()
DEFAULT_TARGET_EMAIL = os.environ.get("YOUTUBE_TARGET_EMAIL", "fendysketsa@gmail.com").strip()
DEFAULT_TARGET_CHANNEL_ID = os.environ.get("YOUTUBE_TARGET_CHANNEL_ID", "UCAOZF9Qzj6DYoXKtLnP4UUQ").strip()
DEFAULT_STUDIO_URL = os.environ.get(
    "YOUTUBE_STUDIO_URL",
    f"https://studio.youtube.com/channel/{DEFAULT_TARGET_CHANNEL_ID}" if DEFAULT_TARGET_CHANNEL_ID else "https://studio.youtube.com",
).strip()
DEFAULT_CDP_URL = os.environ.get("YOUTUBE_CDP_URL", "http://127.0.0.1:9222").strip()
DEBUG_DIR = Path(os.environ.get("YOUTUBE_UPLOAD_DEBUG_DIR", BASE_DIR / "data" / "youtube_debug"))


class UploadError(RuntimeError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def log(message: str) -> None:
    print(message, flush=True)


def install_browser_dialog_guard(page) -> None:
    def dismiss_dialog(dialog) -> None:
        try:
            message = getattr(dialog, "message", "")
            log(f"Dialog browser ditutup: {message or 'tanpa pesan'}")
            dialog.dismiss()
        except Exception as exc:
            log(f"Dialog browser gagal ditutup otomatis: {exc}")

    try:
        page.on("dialog", dismiss_dialog)
    except Exception:
        pass


def install_context_dialog_guard(context) -> None:
    try:
        for page in context.pages:
            install_browser_dialog_guard(page)
        context.on("page", install_browser_dialog_guard)
    except Exception:
        pass


def filename_title(path: Path) -> str:
    stem = re.sub(r"^clip[_-]?\d+[_-]?", "", path.stem, flags=re.I)
    clean = re.sub(r"[_-]+", " ", stem)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean.title()[:100] if clean else path.stem[:100]


def sidecar_title(video_path: Path) -> str:
    json_path = video_path.with_suffix(".json")
    if not json_path.is_file():
        return ""
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    title = payload.get("title") if isinstance(payload, dict) else None
    return re.sub(r"\s+", " ", title).strip()[:100] if isinstance(title, str) and title.strip() else ""


def sidecar_caption(video_path: Path) -> str:
    caption_path = video_path.with_name(f"{video_path.stem}_caption.txt")
    if not caption_path.is_file():
        return ""
    try:
        return caption_path.read_text(encoding="utf-8").strip()[:5000]
    except OSError:
        return ""


def looks_like_description(value: str) -> bool:
    clean = value.strip()
    lowered = clean.lower()
    return bool(
        clean
        and (
            "\n" in clean
            or lowered.startswith("sumber:")
            or "channel sumber:" in lowered
            or len(clean) > 100
            or len(re.findall(r"#[\w\d_]+", clean)) >= 3
        )
    )


def normalized_upload_metadata(video_path: Path, title: str, description: str) -> tuple[str, str]:
    clean_title = re.sub(r"\s+", " ", title).strip()[:100]
    clean_description = description.strip()[:5000]
    if looks_like_description(clean_title):
        if not clean_description:
            clean_description = title.strip()[:5000]
        clean_title = sidecar_title(video_path) or filename_title(video_path)
        log("Judul dari antrean terlihat seperti deskripsi; memakai judul clip sebagai fallback.")
    if not clean_title:
        clean_title = sidecar_title(video_path) or filename_title(video_path)
    if not clean_description:
        clean_description = sidecar_caption(video_path)
    normalized_title = (
        youtube_long_form_title(clean_title)
        if video_path.name.startswith("highlight_5menit_")
        else youtube_shorts_title(clean_title)
    )
    return normalized_title, clean_description[:5000]


def youtube_long_form_title(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    clean = re.sub(r"\s+#shorts\b", "", clean, flags=re.I).strip()
    return clean[:100].rstrip() or "Highlight Pilihan"


def youtube_shorts_title(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    clean = re.sub(r"\s+#shorts\b", "", clean, flags=re.I).strip()
    suffix = " #Shorts"
    if len(clean) + len(suffix) > 100:
        clean = clean[: 100 - len(suffix)].rsplit(" ", 1)[0].rstrip() or clean[: 100 - len(suffix)].rstrip()
    return f"{clean}{suffix}"[:100] if clean else "Clip #Shorts"


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


def save_debug_artifacts(page, label: str) -> None:
    if not env_bool("YOUTUBE_UPLOAD_DEBUG", True):
        return
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-") or "debug"
        base = DEBUG_DIR / f"{stamp}-{safe_label}"
        try:
            page.screenshot(path=str(base.with_suffix(".png")), full_page=True, timeout=10000)
        except Exception as exc:
            log(f"Debug screenshot gagal: {exc}")
        try:
            base.with_suffix(".html").write_text(page.content(), encoding="utf-8")
        except Exception as exc:
            log(f"Debug HTML gagal: {exc}")
        try:
            base.with_suffix(".url.txt").write_text(page.url, encoding="utf-8")
        except Exception:
            pass
        log(f"Debug YouTube Studio disimpan: {base}")
    except Exception as exc:
        log(f"Gagal menyimpan debug YouTube Studio: {exc}")


def hydrate_context_from_storage_state(context, state_path: Path) -> bool:
    if not state_path.is_file():
        return False
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"Storage state YouTube tidak bisa dibaca untuk CDP: {exc}")
        return False
    cookies = payload.get("cookies") if isinstance(payload, dict) else None
    if not isinstance(cookies, list) or not cookies:
        return False
    origins = payload.get("origins") if isinstance(payload, dict) else []
    local_storage_by_origin = {}
    if isinstance(origins, list):
        for origin_entry in origins:
            if not isinstance(origin_entry, dict):
                continue
            origin = origin_entry.get("origin")
            local_storage = origin_entry.get("localStorage")
            if not isinstance(origin, str) or not isinstance(local_storage, list):
                continue
            values = {
                str(item.get("name")): str(item.get("value"))
                for item in local_storage
                if isinstance(item, dict) and item.get("name") is not None and item.get("value") is not None
            }
            if values:
                local_storage_by_origin[origin] = values
    try:
        if local_storage_by_origin:
            storage_json = json.dumps(local_storage_by_origin)
            context.add_init_script(
                """
                (() => {
                  const stores = __STORES__;
                  const values = stores[window.location.origin];
                  if (!values) return;
                  for (const [key, value] of Object.entries(values)) {
                    try {
                      window.localStorage.setItem(key, value);
                    } catch (_) {}
                  }
                })();
                """.replace("__STORES__", storage_json)
            )
        context.add_cookies(cookies)
        log(f"Storage-state YouTube dimasukkan ke Chrome CDP: {state_path}")
        return True
    except Exception as exc:
        log(f"Cookie storage-state gagal dimasukkan ke Chrome CDP: {exc}")
        return False


def hydrate_context_and_open_studio_page(context, state_path: Path, studio_url: str = ""):
    hydrated = hydrate_context_from_storage_state(context, state_path)
    if not hydrated:
        return None
    page = context.new_page()
    install_browser_dialog_guard(page)
    try:
        goto_studio(page, studio_url=studio_url)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        log("Tab baru YouTube Studio dibuka setelah hydrate storage-state ke Chrome CDP.")
    except Exception as exc:
        log(f"Buka tab Studio setelah hydrate storage-state gagal: {exc}")
    return page


def find_file_input(page, timeout_ms: int = 10000):
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            for frame in page.frames:
                locator = frame.locator('input[type="file"]').first
                if locator.count() > 0:
                    return locator
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    return None


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


def dismiss_reload_prompt(page, timeout_ms: int = 2000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.get_by_text(re.compile(r"reload site|changes you made may not be saved", re.I)).first.is_visible(
                timeout=300
            ):
                if click_role_button(page, [r"^cancel$|^batal$"], timeout_ms=1200, optional=True):
                    log("Prompt reload ditutup dengan Cancel.")
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def deep_click(
    page,
    *,
    selectors: Iterable[str] = (),
    text_patterns: Iterable[str] = (),
    timeout_ms: int = 8000,
    optional: bool = False,
) -> bool:
    selector_list = list(selectors)
    pattern_list = list(text_patterns)
    script = """
    ({ selectors, patterns }) => {
      const roots = [];
      const seenRoots = new Set();
      const addRoot = (root) => {
        if (root && !seenRoots.has(root)) {
          seenRoots.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }

      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
        element.getAttribute?.('alt'),
        element.id,
      ].filter(Boolean).join('\\n');
      const isHelpLink = (element) => {
        const label = labelOf(element).toLowerCase();
        const href = String(element.getAttribute?.('href') || element.closest?.('a')?.getAttribute?.('href') || '');
        return (
          label.includes('pelajari lebih lanjut') ||
          label.includes('learn more') ||
          href.includes('support.google.com') ||
          href.includes('/youtube/answer/')
        );
      };
      const clickableTarget = (element) =>
        element.closest?.(
          'button,[role="button"],[role="menuitem"],[role="option"],a,ytcp-button,ytcp-icon-button,tp-yt-paper-icon-button,tp-yt-paper-item,tp-yt-paper-icon-item,ytcp-ve'
        ) || element;
      const clickElement = (element) => {
        const target = clickableTarget(element);
        if (isHelpLink(element) || isHelpLink(target)) return false;
        target.scrollIntoView?.({ block: 'center', inline: 'center' });
        target.click();
        return true;
      };

      for (const selector of selectors) {
        for (const root of roots) {
          let matches = [];
          try {
            matches = Array.from(root.querySelectorAll(selector));
          } catch (_) {
            matches = [];
          }
          for (const element of matches) {
            const target = clickableTarget(element);
            if (isHelpLink(element) || isHelpLink(target)) continue;
            if (isVisible(element) || isVisible(target)) return clickElement(element);
          }
        }
      }

        const regexes = patterns.map((pattern) => new RegExp(pattern, 'i'));
      if (regexes.length) {
        for (const root of roots) {
          const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
          for (const element of elements) {
            const target = clickableTarget(element);
            if (isHelpLink(element) || isHelpLink(target)) continue;
            if (!isVisible(element) && !isVisible(target)) continue;
            const label = labelOf(element);
            if (label && regexes.some((regex) => regex.test(label))) return clickElement(element);
          }
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            clicked = page.evaluate(script, {"selectors": selector_list, "patterns": pattern_list})
            if clicked:
                return True
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    if optional:
        return False
    target = ", ".join([*selector_list, *pattern_list])
    raise UploadError(f"Tombol tidak ditemukan: {target}") from last_error


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


def page_url_matches_channel_id(page, target_channel_id: str) -> bool:
    expected_channel_id = target_channel_id.strip().lower()
    if not expected_channel_id:
        return False
    try:
        return studio_channel_id_from_url(page.url).strip().lower() == expected_channel_id
    except Exception:
        return False


def page_matches_allowed_identity(page, target_channel: str, target_email: str, target_channel_id: str = "") -> bool:
    if page_url_matches_channel_id(page, target_channel_id):
        return True
    expected_channel = normalize_channel_text(target_channel)
    expected_email = normalize_channel_text(target_email)
    expected_channel_id = normalize_channel_text(target_channel_id)
    if not expected_channel and not expected_email and not expected_channel_id:
        return True
    body = normalized_page_text(page)
    return bool(
        body
        and (
            (expected_channel and expected_channel in body)
            or (expected_email and expected_email in body)
            or (expected_channel_id and expected_channel_id in body)
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


def resolve_google_account_chooser(page, target_email: str, studio_url: str = "", timeout_ms: int = 15000) -> bool:
    if "accounts.google.com" not in page.url.lower():
        return False
    expected_email = target_email.strip()
    if not expected_email:
        return False
    log("Google account chooser terdeteksi; mencoba memilih akun target.")
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            locator = page.get_by_text(re.compile(re.escape(expected_email), re.I)).first
            if locator.count() and locator.is_visible(timeout=700):
                locator.click(timeout=2500)
                time.sleep(2)
                if studio_url and "studio.youtube.com" not in page.url.lower():
                    goto_studio(page, studio_url=studio_url)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                if "accounts.google.com" not in page.url.lower():
                    log("Akun target dipilih dari Google account chooser.")
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def identity_label(target_channel: str, target_email: str, target_channel_id: str = "") -> str:
    parts = [value for value in (target_channel.strip(), target_email.strip(), target_channel_id.strip()) if value]
    return " / ".join(parts) or "tidak dikonfigurasi"


def ensure_target_identity(page, target_channel: str, target_email: str, target_channel_id: str = "") -> None:
    label = identity_label(target_channel, target_email, target_channel_id)
    if label == "tidak dikonfigurasi":
        return

    if page_url_matches_channel_id(page, target_channel_id):
        log(f"URL YouTube Studio channel target terdeteksi: {target_channel_id}.")
        return

    if page_matches_allowed_identity(page, target_channel, target_email, target_channel_id):
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
                if page_matches_allowed_identity(page, target_channel, target_email, target_channel_id):
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
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(value)
        page.keyboard.press("Tab")
        log(f"{label} diisi.")
    except Exception as exc:
        raise UploadError(f"Gagal mengisi {label}. UI YouTube Studio mungkin berubah.") from exc


def set_upload_text_field(
    page,
    value: str,
    label: str,
    patterns: Iterable[str],
    reject_patterns: Iterable[str] = (),
    timeout_ms: int = 30000,
) -> None:
    if not value:
        return
    pattern_list = list(patterns)
    script = """
    ({ value, patterns, rejectPatterns }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }

      const regexes = patterns.map((pattern) => new RegExp(pattern, 'i'));
      const rejectRegexes = rejectPatterns.map((pattern) => new RegExp(pattern, 'i'));
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelsFor = (element) => {
        const chunks = [
          element.getAttribute?.('aria-label'),
          element.getAttribute?.('placeholder'),
          element.getAttribute?.('title'),
          element.getAttribute?.('aria-describedby'),
          element.getAttribute?.('id'),
        ];
        let current = element;
        for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {
          const tag = String(current.tagName || '').toLowerCase();
          chunks.push(current.getAttribute?.('aria-label'));
          chunks.push(current.getAttribute?.('label'));
          chunks.push(current.getAttribute?.('id'));
          chunks.push(current.innerText);
          if (
            tag.includes('ytcp-social-suggestions-textbox') ||
            tag.includes('ytcp-form-input-container') ||
            tag.includes('ytcp-mention-textbox')
          ) break;
        }
        return chunks.filter(Boolean).join('\\n');
      };
      const score = (element) => {
        if (!isVisible(element)) return -1;
        const label = labelsFor(element);
        const matched = regexes.some((regex) => regex.test(label));
        if (!matched) return -1;
        if (rejectRegexes.some((regex) => regex.test(label))) return -1;
        const rect = element.getBoundingClientRect();
        let current = element;
        let ancestorBonus = 0;
        for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {
          const tag = String(current.tagName || '').toLowerCase();
          if (tag.includes('ytcp-social-suggestions-textbox')) ancestorBonus += 30;
          if (tag.includes('ytcp-video-metadata-editor')) ancestorBonus += 20;
        }
        return ancestorBonus + Math.max(0, 1000 - Math.round(rect.top));
      };
      const candidates = [];
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll('#textbox, [contenteditable="true"], textarea, input[type="text"]'))
          : [];
        for (const element of elements) {
          const candidateScore = score(element);
          if (candidateScore >= 0) candidates.push({ element, candidateScore });
        }
      }
      candidates.sort((a, b) => b.candidateScore - a.candidateScore);
      const target = candidates[0]?.element;
      if (!target) return false;
      target.scrollIntoView?.({ block: 'center', inline: 'nearest' });
      target.click();
      target.focus();
      return true;
    }
    """
    expected = value.strip()
    type_delay_ms = max(0, int(os.environ.get("YOUTUBE_TYPE_DELAY_MS", "6")))
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if page.evaluate(
                script,
                {"value": value, "patterns": pattern_list, "rejectPatterns": list(reject_patterns)},
            ):
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(value, delay=type_delay_ms)
                page.keyboard.press("Tab")
                if upload_text_field_contains(
                    page,
                    expected,
                    pattern_list,
                    reject_patterns=reject_patterns,
                    timeout_ms=3000,
                ):
                    log(f"{label} diisi.")
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.4)
    save_debug_artifacts(page, f"{label}-field-not-filled")
    raise UploadError(f"Gagal mengisi {label} dengan benar di tab Detail YouTube Studio.") from last_error


def upload_text_field_contains(
    page,
    expected: str,
    patterns: Iterable[str],
    reject_patterns: Iterable[str] = (),
    timeout_ms: int = 3000,
) -> bool:
    pattern_list = list(patterns)
    script = """
    ({ expected, patterns, rejectPatterns }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const regexes = patterns.map((pattern) => new RegExp(pattern, 'i'));
      const rejectRegexes = rejectPatterns.map((pattern) => new RegExp(pattern, 'i'));
      const textOf = (element) => String(element.value ?? element.textContent ?? '').trim();
      const labelOf = (element) => {
        const chunks = [element.getAttribute?.('aria-label'), element.getAttribute?.('placeholder'), element.getAttribute?.('title')];
        let current = element;
        for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {
          const tag = String(current.tagName || '').toLowerCase();
          chunks.push(current.innerText);
          chunks.push(current.getAttribute?.('aria-label'));
          chunks.push(current.getAttribute?.('id'));
          if (
            tag.includes('ytcp-social-suggestions-textbox') ||
            tag.includes('ytcp-form-input-container') ||
            tag.includes('ytcp-mention-textbox')
          ) break;
        }
        return chunks.filter(Boolean).join('\\n');
      };
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll('#textbox, [contenteditable="true"], textarea, input[type="text"]'))
          : [];
        for (const element of elements) {
          const text = textOf(element);
          if (!text || !text.includes(expected)) continue;
          const label = labelOf(element);
          if (rejectRegexes.some((regex) => regex.test(label))) continue;
          if (regexes.some((regex) => regex.test(label))) return true;
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(
                script,
                {"expected": expected, "patterns": pattern_list, "rejectPatterns": list(reject_patterns)},
            ):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def ensure_logged_in(page) -> None:
    ensure_supported_studio_browser(page)
    url = page.url.lower()
    if "accounts.google.com" in url or "signin" in url:
        save_debug_artifacts(page, "youtube-login-required")
        raise UploadError(
            "Session YouTube Studio belum login. Jalankan Login Sekali untuk menyimpan ulang cookies/storage-state "
            "atau pakai Ambil Cookies CDP jika memang ingin mengambil session dari Chrome CDP."
        )
    text = normalized_page_text(page)
    login_page_patterns = (
        "signintoyoutube",
        "signinwithgoogle",
        "masukkeyoutube",
        "masukdengangoogle",
        "untukmelanjutkanlogin",
        "loginuntukmelanjutkan",
    )
    if any(pattern in text for pattern in login_page_patterns):
        save_debug_artifacts(page, "youtube-login-required")
        raise UploadError(
            "Session YouTube Studio belum login. Jalankan Login Sekali untuk menyimpan ulang cookies/storage-state "
            "atau pakai Ambil Cookies CDP jika memang ingin mengambil session dari Chrome CDP."
        )


def ensure_supported_studio_browser(page) -> None:
    text = normalized_page_text(page)
    unsupported_patterns = (
        "sempurnakanpengalamananda",
        "browseryangtidakdidukung",
        "versibrowserlama",
        "unsupportedbrowser",
        "updateyourbrowser",
    )
    if any(pattern in text for pattern in unsupported_patterns):
        raise UploadError(
            "YouTube Studio menolak browser otomatis backend sebagai browser lama/tidak didukung. "
            "Update browser Playwright/backend, atau pakai Ambil Cookies CDP sebagai fallback session."
        )


def studio_channel_id_from_url(value: str) -> str:
    match = re.search(r"studio\.youtube\.com/channel/([^/?#]+)", value)
    return match.group(1) if match else ""


def studio_dashboard_url(value: str = "") -> str:
    value = value.strip()
    channel_id = studio_channel_id_from_url(value) or DEFAULT_TARGET_CHANNEL_ID
    if channel_id:
        return f"https://studio.youtube.com/channel/{channel_id}"
    if value:
        return re.sub(r"([?#].*)$", "", value).rstrip("/") or "https://studio.youtube.com"
    return "https://studio.youtube.com"


def effective_channel_id(page=None, configured: str = "") -> str:
    configured = configured.strip()
    if configured:
        return configured
    if page is not None:
        current_id = studio_channel_id_from_url(page.url)
        if current_id:
            return current_id
    return DEFAULT_TARGET_CHANNEL_ID


def studio_start_url(configured_url: str = "") -> str:
    return studio_dashboard_url(configured_url or DEFAULT_STUDIO_URL)


def goto_studio(page, timeout_ms: int = 30000, studio_url: str = "") -> None:
    last_error = ""
    target_url = studio_start_url(studio_url)
    urls = [target_url]
    channel_id = studio_channel_id_from_url(target_url) or DEFAULT_TARGET_CHANNEL_ID
    if channel_id:
        urls.extend(
            [
                f"https://studio.youtube.com/channel/{channel_id}/videos",
                f"https://studio.youtube.com/channel/{channel_id}",
            ]
        )
    urls.append("https://studio.youtube.com")

    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    nav_timeout = max(timeout_ms, int(os.environ.get("YOUTUBE_STUDIO_NAV_TIMEOUT_MS", "60000")))
    for url in unique_urls:
        try:
            log(f"Membuka YouTube Studio: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)
            page.wait_for_load_state("domcontentloaded", timeout=min(nav_timeout, 15000))
            ensure_supported_studio_browser(page)
            return
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1.5)
    raise UploadError(
        f"Browser Playwright tidak bisa membuka YouTube Studio dari beberapa URL awal. "
        "Backend akan mencoba halaman upload langsung jika fallback diaktifkan. "
        f"Detail: {last_error}"
    )


def wait_for_file_input(page, timeout_ms: int = 10000) -> bool:
    return find_file_input(page, timeout_ms=timeout_ms) is not None


def wait_for_upload_surface(page, timeout_ms: int = 30000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    markers = (
        "selectfiles",
        "pilihfile",
        "pilihvideo",
        "uploadvideos",
        "uploadvideo",
        "unggahvideo",
        "draganddropvideofiles",
        "tarikdanlepaskanfilevideo",
    )
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=250)
        if wait_for_file_input(page, timeout_ms=600):
            return True
        try:
            if page.locator("ytcp-uploads-dialog").count() > 0:
                return True
        except Exception:
            pass
        text = normalized_page_text(page)
        if any(marker in text for marker in markers):
            return True
        time.sleep(0.5)
    return False


def upload_metadata_form_ready(page, timeout_ms: int = 1000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                boxes = frame.locator("#textbox")
                if boxes.count() and boxes.first.is_visible(timeout=250):
                    return True
            except Exception:
                pass
        time.sleep(0.15)
    return False


def upload_selection_has_started(page, timeout_ms: int = 3000) -> bool:
    if upload_metadata_form_ready(page, timeout_ms=timeout_ms):
        return True
    text = normalized_page_text(page)
    started_patterns = (
        "menguploadvideo",
        "uploadingvideo",
        "linkvideo",
        "namafile",
        "disimpansebagaipribadi",
        "savedasprivate",
    )
    return any(pattern in text for pattern in started_patterns)


def click_select_files_entry(page, timeout_ms: int = 5000) -> bool:
    clicked = deep_click(
        page,
        selectors=(
            'ytcp-button[dialog-confirm]',
            'ytcp-button#select-files-button',
            '#select-files-button',
            '[aria-label*="Select files"]',
            '[aria-label*="Pilih file"]',
            '[aria-label*="Pilih video"]',
        ),
        text_patterns=(r"select files?", r"pilih file", r"pilih video", r"upload files?"),
        timeout_ms=timeout_ms,
        optional=True,
    )
    if clicked:
        log("Tombol/area pilih file diklik.")
    return clicked


def set_video_input_files(page, file_input, video_path: Path) -> bool:
    timeout_ms = max(30000, int(os.environ.get("YOUTUBE_SET_INPUT_FILES_TIMEOUT_MS", "120000")))
    try:
        file_input.set_input_files(str(video_path), timeout=timeout_ms)
        log(f"Video dipilih: {video_path.name}")
        return True
    except Exception as exc:
        if upload_selection_has_started(page, timeout_ms=12000):
            log(
                "Pemilihan file timeout, tetapi YouTube Studio sudah mulai upload; "
                "lanjut mengisi metadata."
            )
            log(f"Detail timeout input file: {exc}")
            return True
        raise


def select_video_file(page, video_path: Path, timeout_ms: int = 30000) -> None:
    if upload_metadata_form_ready(page, timeout_ms=1500):
        log("Form detail upload sudah terbuka; tidak memilih file ulang.")
        return

    file_input = find_file_input(page, timeout_ms=timeout_ms)
    if file_input is not None:
        set_video_input_files(page, file_input, video_path)
        return

    for attempt in range(3):
        click_select_files_entry(page, timeout_ms=5000)
        file_input = find_file_input(page, timeout_ms=5000)
        if file_input is not None:
            set_video_input_files(page, file_input, video_path)
            return
        try:
            page.keyboard.press("Tab")
            page.keyboard.press("Enter")
            time.sleep(1)
        except Exception:
            pass

    save_debug_artifacts(page, "file-input-not-found")
    raise UploadError("Input file upload YouTube Studio tidak muncul setelah dialog dibuka.")


def goto_upload_page(page, channel_id: str = "", target_email: str = "", studio_url: str = "") -> None:
    last_error = ""
    resolved_channel_id = effective_channel_id(page, channel_id)
    channel_urls = (
        (
            f"https://studio.youtube.com/channel/{resolved_channel_id}/videos/upload",
            f"https://studio.youtube.com/channel/{resolved_channel_id}/upload",
            f"https://studio.youtube.com/channel/{resolved_channel_id}/videos",
        )
        if resolved_channel_id
        else ()
    )
    direct_timeout = max(8000, int(os.environ.get("YOUTUBE_DIRECT_UPLOAD_NAV_TIMEOUT_MS", "18000")))
    input_timeout = max(15000, int(os.environ.get("YOUTUBE_DIRECT_UPLOAD_INPUT_TIMEOUT_MS", "20000")))
    urls = (
        *channel_urls,
        "https://studio.youtube.com/upload",
    )
    for url in urls:
        for attempt in range(2):
            try:
                if attempt:
                    log("UI upload belum muncul; reload halaman upload langsung.")
                    page.reload(wait_until="domcontentloaded", timeout=direct_timeout)
                else:
                    log(f"Membuka halaman upload langsung: {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=direct_timeout)
                page.wait_for_load_state("domcontentloaded", timeout=min(direct_timeout, 10000))
                try:
                    page.wait_for_load_state("networkidle", timeout=min(direct_timeout, 20000))
                except Exception:
                    pass
                ensure_supported_studio_browser(page)
                if "accounts.google.com" in page.url.lower():
                    if resolve_google_account_chooser(page, target_email, studio_url=studio_url):
                        continue
                    last_error = "Google account chooser/login muncul saat membuka halaman upload langsung."
                    break
                if wait_for_upload_surface(page, timeout_ms=input_timeout):
                    if wait_for_file_input(page, timeout_ms=3000):
                        log("Dialog upload siap.")
                        return
                    if click_select_files_entry(page, timeout_ms=5000) and wait_for_file_input(
                        page, timeout_ms=input_timeout
                    ):
                        log("Dialog upload siap.")
                        return
                if click_select_files_entry(page, timeout_ms=5000) and wait_for_file_input(
                    page, timeout_ms=input_timeout
                ):
                    log("Dialog upload siap.")
                    return
                if click_create_upload_by_topbar_position(page) and wait_for_file_input(
                    page, timeout_ms=input_timeout
                ):
                    log("Dialog upload siap.")
                    return
            except UploadError:
                raise
            except Exception as exc:
                last_error = str(exc)
                break
    save_debug_artifacts(page, "upload-page-input-not-found")
    raise UploadError(
        "Halaman upload YouTube Studio tidak bisa dibuka atau input file tidak ditemukan. "
        f"Detail: {last_error}"
    )


def click_upload_menu_item(page, timeout_ms: int = 8000) -> bool:
    menu_clicked = deep_click(
        page,
        selectors=(
            '[test-id*="upload"]',
            '[id*="upload"]',
            '[aria-label*="Upload video"]',
            '[aria-label*="Unggah video"]',
            '[title*="Upload video"]',
            '[title*="Unggah video"]',
        ),
        text_patterns=(r"upload video", r"unggah video", r"upload videos?"),
        timeout_ms=timeout_ms,
        optional=True,
    )
    if menu_clicked:
        return True
    return click_text(page, [r"upload videos?", r"unggah video", r"upload video"], timeout_ms=timeout_ms, optional=True)


def click_create_upload_by_topbar_position(page) -> bool:
    viewport = page.viewport_size or {"width": 1440, "height": 1000}
    width = int(viewport.get("width") or 1440)
    y_positions = (44, 56, 68)
    x_positions = tuple(range(max(40, width - 260), max(41, width - 40), 55))
    for x in x_positions:
        for y in y_positions:
            try:
                page.mouse.click(x, y)
                time.sleep(0.35)
                if click_upload_menu_item(page, timeout_ms=900):
                    log("Menu Upload video diklik dari tombol Buat di topbar.")
                    return True
                page.keyboard.press("Escape")
            except Exception:
                continue
    return False


def click_dashboard_upload_entry(page, timeout_ms: int = 12000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        for selector in (
            '[aria-label*="Upload video" i]',
            '[aria-label*="Unggah video" i]',
            '[title*="Upload video" i]',
            '[title*="Unggah video" i]',
        ):
            try:
                locator = page.locator(selector).first
                if locator.count() and locator.is_visible(timeout=500):
                    locator.click(timeout=2000)
                    log("Tombol upload dashboard diklik.")
                    return True
            except Exception:
                pass

        if click_role_button(page, [r"^buat$|^create$"], timeout_ms=1200, optional=True) or deep_click(
            page,
            selectors=(
                'button[aria-label*="Buat"]',
                'button[aria-label*="Create"]',
                'ytcp-button[aria-label*="Buat"]',
                'ytcp-button[aria-label*="Create"]',
                '#create-icon',
                '#create',
            ),
            text_patterns=(r"^buat$", r"^create$"),
            timeout_ms=1200,
            optional=True,
        ):
            log("Tombol Buat/Create dashboard diklik.")
            if click_upload_menu_item(page, timeout_ms=4000):
                log("Menu Upload video diklik.")
                return True
        time.sleep(0.5)
    return False


def close_upload_tab(page) -> None:
    if not env_bool("YOUTUBE_CLOSE_UPLOAD_TAB", False):
        log("Tab upload YouTube dibiarkan terbuka agar tidak memicu prompt reload/leave.")
        return
    try:
        if not page.is_closed():
            page.close()
            log("Tab upload YouTube ditutup.")
    except Exception:
        log("Tab upload YouTube tidak dapat ditutup otomatis.")


def open_upload_dialog(
    page,
    target_channel: str = "",
    target_email: str = "",
    target_channel_id: str = "",
    studio_url: str = "",
) -> None:
    log("Memeriksa tab YouTube Studio...")
    if "studio.youtube.com" in page.url.lower():
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        if target_channel_id and not page_url_matches_channel_id(page, target_channel_id):
            log("Tab Studio belum berada di channel target; membuka Studio channel target.")
            goto_studio(page, studio_url=studio_url or f"https://studio.youtube.com/channel/{target_channel_id}")
    else:
        log("Membuka YouTube Studio...")
        try:
            goto_studio(page, studio_url=studio_url)
        except UploadError as exc:
            if env_bool("YOUTUBE_ALLOW_DIRECT_UPLOAD_PAGE_FALLBACK", True):
                log(f"Dashboard Studio tidak terbuka normal; mencoba halaman upload langsung. Detail: {exc}")
                goto_upload_page(page, target_channel_id, target_email, studio_url)
                resolve_google_account_chooser(page, target_email, studio_url=studio_url)
                ensure_logged_in(page)
                ensure_target_identity(page, target_channel, target_email, target_channel_id)
                return
            raise
    dismiss_reload_prompt(page)
    resolve_google_account_chooser(page, target_email, studio_url=studio_url)
    ensure_logged_in(page)
    ensure_target_identity(page, target_channel, target_email, target_channel_id)

    if upload_metadata_form_ready(page, timeout_ms=1500):
        log("Form detail upload sudah terbuka; lanjut dari tab ini tanpa reload.")
        return
    if wait_for_file_input(page, timeout_ms=1500):
        log("Dialog upload sudah siap; lanjut dari tab ini tanpa reload.")
        return

    log("Membuka dialog upload...")
    for attempt in range(3):
        if click_dashboard_upload_entry(page, timeout_ms=6000):
            if wait_for_file_input(page, timeout_ms=9000):
                log("Dialog upload siap.")
                return
            if click_select_files_entry(page, timeout_ms=3000) and wait_for_file_input(page, timeout_ms=5000):
                log("Dialog upload siap.")
                return
        log(f"Modal upload belum muncul dari dashboard; percobaan {attempt + 1}/3.")

    create_clicked = False
    create_selectors = (
        'ytcp-button#create-icon',
        'ytcp-button#create',
        'ytcp-icon-button#create-icon',
        'ytcp-icon-button#create',
        'tp-yt-paper-icon-button#create-icon',
        'tp-yt-paper-icon-button#create',
        'button#create-icon',
        'button#create',
        'button[aria-label*="Create"]',
        'button[aria-label*="Buat"]',
        '[aria-label*="Create"][role="button"]',
        '[aria-label*="Buat"][role="button"]',
        '[title*="Create"]',
        '[title*="Buat"]',
        '#create-icon',
        '#create',
    )
    create_clicked = deep_click(
        page,
        selectors=create_selectors,
        text_patterns=(r"^create$", r"^buat$"),
        timeout_ms=5000,
        optional=True,
    )
    if not create_clicked:
        create_clicked = click_role_button(page, [r"create|buat"], timeout_ms=3000, optional=True)

    if create_clicked:
        log("Tombol Buat/Create diklik.")
        menu_clicked = click_upload_menu_item(page, timeout_ms=5000)
        if menu_clicked:
            log("Menu Upload video diklik.")
            if wait_for_file_input(page, timeout_ms=6000):
                log("Dialog upload siap.")
                return
        if wait_for_file_input(page, timeout_ms=3000):
            log("Dialog upload siap.")
            return

    if click_create_upload_by_topbar_position(page):
        if wait_for_file_input(page, timeout_ms=6000):
            log("Dialog upload siap.")
            return

    if click_select_files_entry(page, timeout_ms=4000):
        if wait_for_file_input(page, timeout_ms=6000):
            log("Dialog upload siap.")
            return

    if env_bool("YOUTUBE_ALLOW_DIRECT_UPLOAD_PAGE_FALLBACK", False):
        log("Tombol Create/Buat tidak tersedia; memakai halaman upload langsung.")
        goto_upload_page(page, target_channel_id, target_email, studio_url)
        return

    save_debug_artifacts(page, "dashboard-upload-modal-not-open")
    raise UploadError(
        "Modal upload YouTube Studio tidak terbuka dari dashboard. "
        "Automation tidak melakukan reload/fallback halaman upload agar draft tidak kacau."
    )


def set_visibility(page, visibility: str) -> None:
    labels = {
        "private": [r"private", r"pribadi"],
        "unlisted": [r"unlisted", r"tidak publik"],
        "public": [r"public", r"publik"],
    }[visibility]
    radio_name = {
        "private": "PRIVATE",
        "unlisted": "UNLISTED",
        "public": "PUBLIC",
    }[visibility]
    log(f"Mengatur visibilitas: {visibility}.")
    script = """
    ({ patterns, radioName }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const regexes = patterns.map((pattern) => new RegExp(pattern, 'i'));
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('name'),
        element.getAttribute?.('title'),
        element.id,
      ].filter(Boolean).join('\\n').trim();
      const clickable = (element) =>
        element.closest?.('tp-yt-paper-radio-button, ytcp-radio-button, label, [role="radio"], button, [role="button"]') || element;
      const selected = (element) =>
        element.checked ||
        element.hasAttribute?.('checked') ||
        element.hasAttribute?.('active') ||
        element.classList?.contains('iron-selected') ||
        element.getAttribute?.('aria-checked') === 'true';
      const candidates = [];
      for (const root of roots) {
        const exactSelector = [
          `ytcp-uploads-dialog tp-yt-paper-radio-button[name="${radioName}"]`,
          `ytcp-uploads-dialog ytcp-radio-button[name="${radioName}"]`,
          `ytcp-uploads-dialog [role="radio"][name="${radioName}"]`,
          `ytcp-uploads-dialog input[type="radio"][value="${radioName}"]`,
          `ytcp-uploads-dialog input[type="radio"][name="${radioName}"]`,
        ].join(',');
        let exactMatches = [];
        try {
          exactMatches = Array.from(root.querySelectorAll(exactSelector));
        } catch (_) {
          exactMatches = [];
        }
        for (const element of exactMatches) {
          const target = clickable(element);
          if (!isVisible(element) && !isVisible(target)) continue;
          const rect = target.getBoundingClientRect();
          return {
            already: selected(element) || selected(target),
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            exact: true,
          };
        }

        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll(
              'ytcp-uploads-dialog tp-yt-paper-radio-button, ytcp-uploads-dialog ytcp-radio-button, ytcp-uploads-dialog [role="radio"], ytcp-uploads-dialog label'
            ))
          : [];
        for (const element of elements) {
          const target = clickable(element);
          if (!isVisible(element) && !isVisible(target)) continue;
          const label = labelOf(element) + '\\n' + labelOf(target);
          if (!regexes.some((regex) => regex.test(label))) continue;
          if (/learn more|pelajari lebih lanjut/i.test(label)) continue;
          const rect = target.getBoundingClientRect();
          candidates.push({
            already: selected(element) || selected(target),
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            score: rect.top,
          });
        }
      }
      candidates.sort((a, b) => a.score - b.score);
      return candidates[0] || null;
    }
    """
    deadline = time.monotonic() + 10000 / 1000
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        try:
            target = page.evaluate(script, {"patterns": labels, "radioName": radio_name})
            if isinstance(target, dict) and target.get("x") is not None and target.get("y") is not None:
                page.mouse.move(float(target["x"]), float(target["y"]))
                page.mouse.down()
                time.sleep(0.08)
                page.mouse.up()
                time.sleep(0.8)
                verify = page.evaluate(script, {"patterns": labels, "radioName": radio_name})
                if isinstance(verify, dict) and verify.get("already"):
                    log(f"Visibilitas diklik dan terverifikasi: {visibility}.")
                    return
        except Exception:
            pass
        time.sleep(0.4)
    save_debug_artifacts(page, "visibility-not-selected")
    raise UploadError(f"Opsi visibilitas '{visibility}' tidak berhasil dipilih.")


def get_upload_workflow_step(page) -> str:
    script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      for (const root of roots) {
        const dialog = root.querySelector?.('ytcp-uploads-dialog');
        const step = dialog?.getAttribute?.('workflow-step');
        if (step) return String(step).toUpperCase();
      }
      return '';
    }
    """
    try:
        return str(page.evaluate(script) or "").upper()
    except Exception:
        return ""


def wait_for_upload_workflow_step(page, expected_steps: Iterable[str], timeout_ms: int = 15000) -> str:
    expected = {step.upper() for step in expected_steps if step}
    deadline = time.monotonic() + timeout_ms / 1000
    last_step = ""
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        last_step = get_upload_workflow_step(page)
        if last_step in expected:
            log(f"Tab upload aktif: {last_step}.")
            return last_step
        time.sleep(0.4)
    save_debug_artifacts(page, "upload-step-not-changed")
    raise UploadError(
        "Tab upload belum berpindah sesuai alur. "
        f"Target: {', '.join(sorted(expected))}; terakhir: {last_step or 'tidak terbaca'}."
    )


def wait_for_visibility_step(page, timeout_ms: int = 20000) -> None:
    if get_upload_workflow_step(page) == "REVIEW":
        log("Tab Visibilitas siap.")
        return
    deadline = time.monotonic() + timeout_ms / 1000
    patterns = (
        r"visibilitas",
        r"visibility",
        r"publik",
        r"public",
        r"jadwalkan",
        r"schedule",
    )
    last_body = ""
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        try:
            body = page.locator("ytcp-uploads-dialog").inner_text(timeout=2000)
            last_body = re.sub(r"\s+", " ", body).strip()[:500]
            if any(re.search(pattern, body, re.I) for pattern in patterns):
                log("Tab Visibilitas siap.")
                return
        except Exception:
            pass
        time.sleep(0.5)
    save_debug_artifacts(page, "visibility-step-not-ready")
    raise UploadError(f"Tab Visibilitas belum siap sebelum publish. Cuplikan modal: {last_body}")


def visibility_is_selected(page, visibility: str) -> bool:
    radio_name = {
        "private": "PRIVATE",
        "unlisted": "UNLISTED",
        "public": "PUBLIC",
    }[visibility]
    script = """
    ({ radioName }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const selected = (element) =>
        !!element && (
          element.checked ||
          element.hasAttribute?.('checked') ||
          element.hasAttribute?.('active') ||
          element.classList?.contains('iron-selected') ||
          element.getAttribute?.('aria-checked') === 'true'
        );
      for (const root of roots) {
        const selector = [
          `ytcp-uploads-dialog tp-yt-paper-radio-button[name="${radioName}"]`,
          `ytcp-uploads-dialog ytcp-radio-button[name="${radioName}"]`,
          `ytcp-uploads-dialog [role="radio"][name="${radioName}"]`,
          `ytcp-uploads-dialog input[type="radio"][value="${radioName}"]`,
          `ytcp-uploads-dialog input[type="radio"][name="${radioName}"]`,
        ].join(',');
        let matches = [];
        try {
          matches = Array.from(root.querySelectorAll(selector));
        } catch (_) {
          matches = [];
        }
        if (matches.some(selected)) return true;
      }
      return false;
    }
    """
    try:
        return bool(page.evaluate(script, {"radioName": radio_name}))
    except Exception:
        return False


def final_action_button_is_ready(page, visibility: str) -> bool:
    patterns = [r"publish", r"publikasikan"] if visibility == "public" else [r"save", r"done", r"simpan", r"selesai"]
    script = """
    ({ patterns }) => {
      const dialog = document.querySelector('ytcp-uploads-dialog');
      if (!dialog || String(dialog.getAttribute('workflow-step') || '').toUpperCase() !== 'REVIEW') return false;
      const host = dialog.querySelector('#done-button');
      const button = host?.querySelector?.('button') || host;
      if (!host || !button) return false;
      const label = [
        host.innerText,
        host.textContent,
        host.getAttribute?.('aria-label'),
        button.innerText,
        button.textContent,
        button.getAttribute?.('aria-label'),
      ].filter(Boolean).join('\\n');
      const disabled =
        host.disabled ||
        button.disabled ||
        host.getAttribute?.('aria-disabled') === 'true' ||
        button.getAttribute?.('aria-disabled') === 'true';
      const rect = button.getBoundingClientRect();
      const style = window.getComputedStyle(button);
      const visible = rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
      return visible && !disabled && patterns.some((pattern) => new RegExp(pattern, 'i').test(label));
    }
    """
    try:
        return bool(page.evaluate(script, {"patterns": patterns}))
    except Exception:
        return False


def wait_for_review_checks_safe_before_publish(page, timeout_ms: int = 300000) -> None:
    log("Memastikan step Visibilitas dan tombol Publikasikan siap...")
    deadline = time.monotonic() + timeout_ms / 1000
    last_body = ""
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        if (
            get_upload_workflow_step(page) == "REVIEW"
            and visibility_is_selected(page, "public")
            and final_action_button_is_ready(page, "public")
        ):
            log("Public tercentang dan tombol Publikasikan aktif.")
            return
        try:
            body = page.locator("ytcp-uploads-dialog").inner_text(timeout=3000)
            last_body = re.sub(r"\s+", " ", body).strip()[:700]
        except Exception:
            pass
        time.sleep(1)

    save_debug_artifacts(page, "publish-button-not-ready")
    raise UploadError(f"Public atau tombol Publikasikan belum siap. Cuplikan modal: {last_body}")


def click_final_upload_action(page, visibility: str, timeout_ms: int = 30000) -> None:
    active_step = get_upload_workflow_step(page)
    if active_step != "REVIEW":
        save_debug_artifacts(page, "final-action-outside-visibility-step")
        raise UploadError(
            "Tombol final tidak boleh diklik sebelum step Visibilitas benar-benar aktif. "
            f"Step aktif: {active_step or 'tidak terbaca'}."
        )
    if not visibility_is_selected(page, visibility):
        save_debug_artifacts(page, "final-visibility-not-selected")
        raise UploadError(
            f"Visibilitas '{visibility}' belum benar-benar tercentang; upload tidak dipublikasikan."
        )
    if visibility == "public":
        patterns = [r"publish", r"publikasikan"]
        label = "Publish/Publikasikan"
    else:
        patterns = [r"save", r"done", r"simpan", r"selesai"]
        label = "Simpan/Selesai"
    script = """
    ({ patterns }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const regexes = patterns.map((pattern) => new RegExp(pattern, 'i'));
      const blocked = /(reload|muat ulang|cancel|batal|back|kembali|close|tutup|learn more|pelajari lebih lanjut)/i;
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
        element.id,
      ].filter(Boolean).join('\\n').trim();
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const isDisabled = (element) => {
        let current = element;
        for (let depth = 0; current && depth < 4; depth += 1, current = current.parentElement) {
          if (current.disabled || current.getAttribute?.('aria-disabled') === 'true') return true;
          const cls = String(current.className || '');
          if (/disabled/i.test(cls)) return true;
        }
        return false;
      };
      const clickable = (element) =>
        element.closest?.('button,ytcp-button,tp-yt-paper-button,[role="button"]') || element;
      const candidates = [];
      for (const root of roots) {
        const dialog = root.querySelector?.('ytcp-uploads-dialog');
        const reviewReady = dialog && String(dialog.getAttribute('workflow-step') || '').toUpperCase() === 'REVIEW';
        if (reviewReady) {
          const doneButton = root.querySelector?.('ytcp-uploads-dialog #done-button');
          const doneTarget = doneButton ? clickable(doneButton) : null;
          if (doneButton && doneTarget && (isVisible(doneButton) || isVisible(doneTarget)) && !isDisabled(doneButton) && !isDisabled(doneTarget)) {
            const label = labelOf(doneButton) + '\\n' + labelOf(doneTarget);
            if (!blocked.test(label) && regexes.some((regex) => regex.test(label))) {
              const rect = doneTarget.getBoundingClientRect();
              return {
                score: 100000,
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2,
                label,
              };
            }
          }
        }
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll(
              'ytcp-uploads-dialog #done-button, ytcp-uploads-dialog ytcp-button#done-button, ytcp-uploads-dialog button, ytcp-uploads-dialog ytcp-button, ytcp-uploads-dialog tp-yt-paper-button'
            ))
          : [];
        for (const element of elements) {
          const target = clickable(element);
          if (!isVisible(element) && !isVisible(target)) continue;
          if (isDisabled(element) || isDisabled(target)) continue;
          const label = labelOf(element) + '\\n' + labelOf(target);
          if (!regexes.some((regex) => regex.test(label))) continue;
          if (blocked.test(label)) continue;
          const rect = target.getBoundingClientRect();
          candidates.push({
            score:
              (String(target.id || element.id || '') === 'done-button' ? 10000 : 0) +
              (target.closest?.('ytcp-uploads-dialog') ? 5000 : 0) +
              rect.left + rect.top,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            label,
          });
        }
      }
      candidates.sort((a, b) => b.score - a.score);
      return candidates[0] || null;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        try:
            button = page.evaluate(script, {"patterns": patterns})
            if isinstance(button, dict) and button.get("x") is not None and button.get("y") is not None:
                page.mouse.move(float(button["x"]), float(button["y"]))
                page.mouse.down()
                time.sleep(0.08)
                page.mouse.up()
                accepted_deadline = time.monotonic() + 4
                while time.monotonic() < accepted_deadline:
                    if not final_action_button_is_ready(page, visibility):
                        log(f"Tombol final diklik dan diterima: {label}.")
                        return
                    time.sleep(0.4)
                log(f"Klik {label} belum diterima UI; mencoba klik ulang.")
        except Exception:
            pass
        time.sleep(0.4)
    save_debug_artifacts(page, "final-upload-button-not-found")
    raise UploadError(f"Tombol final '{label}' tidak ditemukan.")


def fill_tags(page, tags: str) -> None:
    if tags.strip():
        log("Kolom Tags lanjutan dilewati; hashtag sudah dimasukkan ke deskripsi.")


def set_thumbnail(page, thumbnail_path: Path, timeout_ms: int = 45000) -> None:
    log(f"Mengatur thumbnail: {thumbnail_path.name}.")
    deadline = time.monotonic() + timeout_ms / 1000
    selectors = (
        'ytcp-video-thumbnail-editor input[type="file"]',
        'ytcp-thumbnail-editor input[type="file"]',
        'ytcp-video-custom-thumbnail-editor input[type="file"]',
        'ytcp-video-metadata-editor input[type="file"][accept*="image"]',
        'input[type="file"][accept*="image"]',
        'input[type="file"][accept*=".jpg"]',
        'input[type="file"][accept*=".jpeg"]',
        'input[type="file"][accept*=".png"]',
    )
    clicked_upload = False
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for selector in selectors:
            for frame in page.frames:
                try:
                    locator = frame.locator(selector).first
                    if locator.count():
                        locator.set_input_files(str(thumbnail_path), timeout=30000)
                        log(f"Thumbnail dipilih: {thumbnail_path.name}")
                        return
                except Exception as exc:
                    last_error = exc
        if not clicked_upload:
            clicked_upload = deep_click(
                page,
                selectors=(
                    '[aria-label*="thumbnail" i]',
                    '[title*="thumbnail" i]',
                    '[aria-label*="thumbnail kustom" i]',
                    '[aria-label*="upload thumbnail" i]',
                ),
                text_patterns=(r"upload thumbnail", r"custom thumbnail", r"thumbnail kustom", r"upload.*thumbnail"),
                timeout_ms=2500,
                optional=True,
            )
        time.sleep(0.5)

    page_text = normalized_page_text(page)
    save_debug_artifacts(page, "thumbnail-input-not-found")
    if (
        "ubahthumbnaildiaplikasiseluleryoutube" in page_text
        or "changeyourthumbnailonyoutubemobile" in page_text
        or "changethethumbnailinyoutubemobile" in page_text
    ):
        raise UploadError(
            "Thumbnail tidak bisa dipasang dari YouTube Studio desktop untuk video Shorts ini. "
            "YouTube hanya menampilkan opsi ubah thumbnail lewat aplikasi seluler."
        )
    raise UploadError("Input thumbnail YouTube Studio tidak ditemukan; thumbnail belum terpasang.") from last_error


def click_playlist_named(page, playlist_name: str, timeout_ms: int = 8000) -> bool:
    target = playlist_name.strip().lower()
    if not target:
        return False
    script = """
    ({ target }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }

      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const normalizedLines = (value) =>
        String(value || '')
          .split(/\\n+/)
          .map((line) => line.trim().toLowerCase())
          .filter(Boolean);
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n');
      const containsExactLine = (element) => normalizedLines(labelOf(element)).includes(target);
      const findClickable = (element) => {
        let current = element;
        for (let depth = 0; current && depth < 8; depth += 1, current = current.parentElement) {
          const checkbox = current.querySelector?.(
            'input[type="checkbox"], [role="checkbox"], ytcp-checkbox-lit, tp-yt-paper-checkbox, #checkbox'
          );
          if (checkbox && isVisible(checkbox)) return checkbox;
          if (current.getAttribute?.('role') === 'checkbox') return current;
        }
        return element.closest?.('[role="checkbox"], tp-yt-paper-item, ytcp-playlist-dialog-row, ytcp-checkbox-lit') || element;
      };

      for (const root of roots) {
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (!isVisible(element) || !containsExactLine(element)) continue;
          const clickable = findClickable(element);
          clickable.scrollIntoView?.({ block: 'center', inline: 'center' });
          clickable.click();
          return true;
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(script, {"target": target}):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def playlist_is_selected(page, playlist_name: str, timeout_ms: int = 3000) -> bool:
    target = playlist_name.strip().lower()
    if not target:
        return False
    script = """
    ({ target }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isChecked = (element) =>
        element.checked === true ||
        element.getAttribute?.('checked') !== null ||
        element.getAttribute?.('aria-checked') === 'true';
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n').toLowerCase();
      for (const root of roots) {
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (!labelOf(element).split(/\\n+/).map((line) => line.trim()).includes(target)) continue;
          let current = element;
          for (let depth = 0; current && depth < 10; depth += 1, current = current.parentElement) {
            const checks = current.querySelectorAll?.(
              'input[type="checkbox"], [role="checkbox"], ytcp-checkbox-lit, tp-yt-paper-checkbox, #checkbox'
            );
            if (checks) {
              for (const check of checks) {
                if (isChecked(check)) return true;
              }
            }
            if (current.getAttribute?.('role') === 'checkbox' && isChecked(current)) return true;
          }
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(script, {"target": target}):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def playlist_dropdown_value_matches(page, playlist_name: str, timeout_ms: int = 1000) -> bool:
    target = playlist_name.strip().lower()
    if not target:
        return False
    script = """
    ({ target }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      for (const root of roots) {
        const playlists = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-video-metadata-playlists')) : [];
        for (const playlist of playlists) {
          if (!isVisible(playlist)) continue;
          const text = String(playlist.innerText || playlist.textContent || '').toLowerCase();
          const lines = text.split(/\\n+/).map((line) => line.trim()).filter(Boolean);
          if (lines.includes(target)) return true;
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(script, {"target": target}):
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def click_playlist_checkbox(page, playlist_name: str, timeout_ms: int = 8000) -> bool:
    target = playlist_name.strip().lower()
    if not target:
        return False
    script = """
    ({ target }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const isChecked = (element) =>
        element.checked === true ||
        element.getAttribute?.('checked') !== null ||
        element.getAttribute?.('aria-checked') === 'true';
      const normalizedLines = (value) =>
        String(value || '')
          .split(/\\n+/)
          .map((line) => line.trim().toLowerCase())
          .filter(Boolean);
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n');
      const exactLabel = (element) => normalizedLines(labelOf(element)).includes(target);
      const containsTargetWord = (element) => {
        const words = labelOf(element).toLowerCase().split(/[^a-z0-9_]+/).filter(Boolean);
        return words.includes(target);
      };
      const checkboxSelectors = 'input[type="checkbox"], [role="checkbox"], ytcp-checkbox-lit, tp-yt-paper-checkbox, #checkbox';
      const clickElement = (element) => {
        element.scrollIntoView?.({ block: 'center', inline: 'center' });
        element.click();
        return true;
      };
      const clickAtRowCheckboxSlot = (row) => {
        const rect = row.getBoundingClientRect?.();
        if (!rect || rect.width <= 0 || rect.height <= 0) return false;
        const x = Math.max(rect.left + 16, Math.min(rect.left + 34, rect.right - 8));
        const y = rect.top + rect.height / 2;
        const hit = document.elementFromPoint(x, y);
        const checkbox = hit?.closest?.(checkboxSelectors);
        if (checkbox && isVisible(checkbox)) return clickElement(checkbox);
        hit?.click?.();
        return true;
      };

      for (const root of roots) {
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (!isVisible(element) || (!exactLabel(element) && !containsTargetWord(element))) continue;
          let current = element;
          for (let depth = 0; current && depth < 10; depth += 1, current = current.parentElement) {
            const checks = current.querySelectorAll?.(checkboxSelectors);
            if (checks) {
              for (const check of checks) {
                if (!isVisible(check)) continue;
                if (isChecked(check)) return true;
                return clickElement(check);
              }
            }
            if (current.getAttribute?.('role') === 'checkbox') {
              if (isChecked(current)) return true;
              return clickElement(current);
            }
            const role = current.getAttribute?.('role') || '';
            const tag = String(current.tagName || '').toLowerCase();
            if (
              role === 'listitem' ||
              role === 'option' ||
              tag.includes('paper-item') ||
              tag.includes('playlist') ||
              current.className?.toString?.().toLowerCase?.().includes('row')
            ) {
              if (clickAtRowCheckboxSlot(current)) return true;
            }
          }
          if (clickAtRowCheckboxSlot(element)) return true;
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(script, {"target": target}):
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def search_playlist(page, playlist_name: str) -> bool:
    selectors = (
        'ytcp-playlist-dialog input',
        'tp-yt-paper-dialog.ytcp-playlist-dialog input',
        'tp-yt-iron-dropdown input[placeholder*="playlist" i]',
        'tp-yt-iron-dropdown input[aria-label*="playlist" i]',
        'tp-yt-iron-dropdown input[placeholder*="telusuri" i]',
        'tp-yt-iron-dropdown input[placeholder*="search" i]',
        'input[placeholder*="playlist" i]',
        'input[aria-label*="playlist" i]',
    )
    for selector in selectors:
        try:
            field = page.locator(selector).first
            if field.count() and field.is_visible(timeout=1000):
                field.click(timeout=2000)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(playlist_name, delay=max(0, int(os.environ.get("YOUTUBE_TYPE_DELAY_MS", "6"))))
                page.keyboard.press("Enter")
                log(f"Search playlist: {playlist_name}.")
                time.sleep(1.2)
                return True
        except Exception:
            continue
    log("Kolom search playlist tidak ditemukan; memilih dari daftar yang tampil.")
    return False


def click_playlist_done(page, timeout_ms: int = 8000) -> bool:
    if click_role_button(page, [r"^done$|^selesai$|^simpan$|^ok$"], timeout_ms=2000, optional=True):
        return True
    return deep_click(
        page,
        selectors=(
            'ytcp-button[dialog-confirm]',
            'tp-yt-paper-button[dialog-confirm]',
            'ytcp-playlist-dialog ytcp-button',
            'tp-yt-paper-dialog ytcp-button',
        ),
        text_patterns=(r"^done$", r"^selesai$", r"^simpan$", r"^ok$"),
        timeout_ms=timeout_ms,
        optional=True,
    )


def open_playlist_dropdown(page, timeout_ms: int = 8000) -> bool:
    selectors = (
        'ytcp-video-metadata-playlists ytcp-dropdown-trigger[aria-label*="playlist" i]',
        "ytcp-video-metadata-playlists ytcp-dropdown-trigger",
        'ytcp-video-metadata-playlists [role="button"][aria-label*="playlist" i]',
        'ytcp-video-metadata-playlists [role="button"]',
    )
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() and locator.is_visible(timeout=500):
                    locator.scroll_into_view_if_needed(timeout=1500)
                    locator.click(timeout=2500)
                    if playlist_dialog_open(page, timeout_ms=2500):
                        log("Dropdown playlist terbuka.")
                        return True
            except Exception:
                continue
        try:
            clicked = page.evaluate(
                """
                () => {
                  const roots = [];
                  const seen = new Set();
                  const addRoot = (root) => {
                    if (root && !seen.has(root)) {
                      seen.add(root);
                      roots.push(root);
                    }
                  };
                  addRoot(document);
                  for (let i = 0; i < roots.length; i += 1) {
                    const root = roots[i];
                    const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
                    for (const element of elements) {
                      if (element.shadowRoot) addRoot(element.shadowRoot);
                    }
                  }
                  const isVisible = (element) => {
                    if (!element || !element.getBoundingClientRect) return false;
                    const rect = element.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) return false;
                    const style = window.getComputedStyle(element);
                    return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                  };
                  const clickElement = (element) => {
                    element.scrollIntoView?.({ block: 'center', inline: 'center' });
                    const rect = element.getBoundingClientRect?.();
                    if (rect && rect.width > 0 && rect.height > 0) {
                      const x = rect.right - Math.min(22, Math.max(8, rect.width / 5));
                      const y = rect.top + rect.height / 2;
                      const hit = document.elementFromPoint(x, y);
                      (hit?.closest?.('[role="button"],ytcp-dropdown-trigger,ytcp-text-dropdown-trigger') || element).click();
                    } else {
                      element.click();
                    }
                    return true;
                  };

                  for (const root of roots) {
                    const playlists = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-video-metadata-playlists')) : [];
                    for (const playlist of playlists) {
                      if (!isVisible(playlist)) continue;
                      const trigger = playlist.querySelector(
                        'ytcp-dropdown-trigger,[role="button"][aria-label*="playlist" i],[role="button"]'
                      );
                      if (trigger && isVisible(trigger)) return clickElement(trigger);
                    }
                  }
                  return false;
                }
                """
            )
            if clicked and playlist_dialog_open(page, timeout_ms=2500):
                log("Dropdown playlist terbuka.")
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def playlist_dialog_open(page, timeout_ms: int = 1500) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('placeholder'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n').toLowerCase();
      for (const root of roots) {
        const dialogs = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-playlist-dialog')) : [];
        if (dialogs.some((dialog) => isVisible(dialog))) return true;
      }
      for (const root of roots) {
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (!isVisible(element)) continue;
          const label = labelOf(element);
          const tag = String(element.tagName || '').toLowerCase();
          if (
            tag === 'input' &&
            label.includes('playlist') &&
            (element.closest?.('ytcp-playlist-dialog,tp-yt-paper-dialog,tp-yt-iron-dropdown') || label.includes('telusuri'))
          ) {
            return true;
          }
          if (
            label.includes('playlist baru') &&
            label.includes('selesai') &&
            (label.includes('telusuri') || label.includes('search') || label.includes('islam'))
          ) {
            return true;
          }
        }
      }
      return false;
    }
    """
    while time.monotonic() < deadline:
        try:
            if page.evaluate(script):
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def select_playlist(page, playlist: str) -> None:
    playlist_name = playlist.strip()
    if not playlist_name:
        return

    dismiss_reload_prompt(page)
    log(f"Memilih playlist: {playlist_name}.")
    if playlist_dropdown_value_matches(page, playlist_name, timeout_ms=1000):
        log(f"Playlist sudah terpilih: {playlist_name}.")
        return
    opened = playlist_dialog_open(page, timeout_ms=800)
    if not opened:
        opened = open_playlist_dropdown(page, timeout_ms=8000)
    if not opened:
        save_debug_artifacts(page, "playlist-dropdown-not-open")
        raise UploadError("Dropdown playlist tidak terbuka; upload tidak dilanjutkan.")

    time.sleep(0.8)
    search_playlist(page, playlist_name)
    escaped = re.escape(playlist_name)
    clicked_checkbox = click_playlist_checkbox(page, playlist_name, timeout_ms=3000)
    try:
        if not playlist_is_selected(page, playlist_name, timeout_ms=1000):
            checkbox = page.get_by_role("checkbox", name=re.compile(escaped, re.I)).first
        else:
            checkbox = None
        if checkbox is not None and checkbox.count():
            try:
                should_click = not checkbox.is_checked(timeout=1000)
            except Exception:
                should_click = True
            if should_click:
                checkbox.click(timeout=3000)
                clicked_checkbox = True
    except Exception:
        pass

    if not playlist_is_selected(page, playlist_name, timeout_ms=2500):
        clicked_checkbox = click_playlist_checkbox(page, playlist_name, timeout_ms=5000)
    if not playlist_is_selected(page, playlist_name, timeout_ms=2500):
        if click_playlist_named(page, playlist_name, timeout_ms=3000):
            time.sleep(0.5)
    if not playlist_is_selected(page, playlist_name, timeout_ms=3000):
        save_debug_artifacts(page, "playlist-not-checked")
        raise UploadError(f"Playlist '{playlist_name}' belum berhasil dicentang; upload tidak dilanjutkan.")

    if clicked_checkbox or playlist_is_selected(page, playlist_name, timeout_ms=1200):
        if not click_playlist_done(page, timeout_ms=8000):
            save_debug_artifacts(page, "playlist-done-not-found")
            raise UploadError("Tombol Selesai playlist tidak ditemukan setelah playlist dicentang.")
        time.sleep(0.5)
        log(f"Playlist dipilih: {playlist_name}.")
        return

    save_debug_artifacts(page, "playlist-not-checked")
    raise UploadError(f"Playlist '{playlist_name}' belum berhasil dicentang; upload tidak dilanjutkan.")


def click_next_upload_step(page, timeout_ms: int = 20000, expected_step=None) -> None:
    direct_script = """
    () => {
      const dialog = document.querySelector('ytcp-uploads-dialog');
      if (!dialog) return { clicked: false, reason: 'dialog-not-found' };
      const host = dialog.querySelector('#next-button');
      const button = host?.querySelector?.('button') || host;
      if (!button) return { clicked: false, reason: 'next-not-found' };
      const disabled =
        host.getAttribute?.('aria-disabled') === 'true' ||
        button.getAttribute?.('aria-disabled') === 'true' ||
        host.disabled ||
        button.disabled;
      if (disabled) return { clicked: false, reason: 'next-disabled' };
      button.scrollIntoView?.({ block: 'center', inline: 'center' });
      button.click();
      return { clicked: true, step: String(dialog.getAttribute('workflow-step') || '').toUpperCase() };
    }
    """
    script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const isDisabled = (element) => {
        let current = element;
        for (let depth = 0; current && depth < 4; depth += 1, current = current.parentElement) {
          if (current.disabled || current.getAttribute?.('aria-disabled') === 'true') return true;
          if (/disabled/i.test(String(current.className || ''))) return true;
        }
        return false;
      };
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
        element.id,
      ].filter(Boolean).join('\\n').trim();
      const clickable = (element) => element.closest?.('button,ytcp-button,[role="button"]') || element;
      const candidates = [];
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll(
              'ytcp-uploads-dialog #next-button, ytcp-uploads-dialog ytcp-button#next-button, ytcp-uploads-dialog button, ytcp-uploads-dialog ytcp-button'
            ))
          : [];
        for (const element of elements) {
          const target = clickable(element);
          if (!isVisible(element) && !isVisible(target)) continue;
          if (isDisabled(element) || isDisabled(target)) continue;
          const label = labelOf(element) + '\\n' + labelOf(target);
          if (!/(^|\\n)\\s*(next|berikutnya)\\s*(\\n|$)/i.test(label)) continue;
          const rect = target.getBoundingClientRect();
          candidates.push({
            score: (String(target.id || element.id || '') === 'next-button' ? 10000 : 0) + rect.left + rect.top,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          });
        }
      }
      candidates.sort((a, b) => b.score - a.score);
      return candidates[0] || null;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    last_reason = ""
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        if expected_step and get_upload_workflow_step(page) == expected_step:
            log(f"Tab upload sudah aktif: {expected_step}.")
            return
        try:
            direct = page.evaluate(direct_script)
            if isinstance(direct, dict) and direct.get("clicked"):
                if expected_step:
                    try:
                        wait_for_upload_workflow_step(page, [expected_step], timeout_ms=min(timeout_ms, 12000))
                        return
                    except UploadError as exc:
                        last_reason = str(exc)
                        time.sleep(1)
                        continue
                time.sleep(0.8)
                return
            if isinstance(direct, dict):
                last_reason = str(direct.get("reason") or "")
            button = page.evaluate(script)
            if isinstance(button, dict) and button.get("x") is not None and button.get("y") is not None:
                page.mouse.move(float(button["x"]), float(button["y"]))
                page.mouse.down()
                time.sleep(0.08)
                page.mouse.up()
                if expected_step:
                    try:
                        wait_for_upload_workflow_step(page, [expected_step], timeout_ms=min(timeout_ms, 12000))
                        return
                    except UploadError as exc:
                        last_reason = str(exc)
                        time.sleep(1)
                        continue
                else:
                    time.sleep(0.8)
                    return
        except Exception:
            pass
        time.sleep(0.4)
    save_debug_artifacts(page, "next-upload-button-not-found")
    suffix = f" Terakhir: {last_reason}" if last_reason else ""
    raise UploadError(f"Tombol Berikutnya/Next modal upload tidak ditemukan atau masih disabled.{suffix}")


def click_add_subtitle(page, timeout_ms: int = 10000) -> bool:
    selector_patterns = (
        "ytcp-button#subtitles-button button",
        "ytcp-button#subtitles-button",
        "#subtitles-button button",
        "#subtitles-button",
    )
    rect_script = """
    () => {
      const candidates = [
        document.querySelector('ytcp-button#subtitles-button button'),
        document.querySelector('ytcp-button#subtitles-button'),
        document.querySelector('#subtitles-button button'),
        document.querySelector('#subtitles-button'),
      ].filter(Boolean);
      for (const element of candidates) {
        const rect = element.getBoundingClientRect?.();
        if (!rect || rect.width <= 0 || rect.height <= 0) continue;
        const style = window.getComputedStyle(element);
        if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        element.scrollIntoView?.({ block: 'center', inline: 'center' });
        const nextRect = element.getBoundingClientRect();
        return {
          x: nextRect.left + nextRect.width / 2,
          y: nextRect.top + nextRect.height / 2,
        };
      }
      return null;
    }
    """
    script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n').toLowerCase();
      const isAddButton = (element) => {
        const label = labelOf(element);
        return /(^|\\n|\\s)(tambahkan|add)(\\s|\\n|$)/i.test(label);
      };
      const clickElement = (element) => {
        element.scrollIntoView?.({ block: 'center', inline: 'center' });
        element.click();
        return true;
      };
      for (const root of roots) {
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (!isVisible(element)) continue;
          const label = labelOf(element);
          if (
            !label.includes('tambahkan subtitle') &&
            !label.includes('tambahkan subtitel') &&
            !label.includes('add subtitles') &&
            !label.includes('add subtitle')
          ) continue;
          let row = element;
          for (let depth = 0; row && depth < 8; depth += 1, row = row.parentElement) {
            const buttons = row.querySelectorAll?.('button,ytcp-button,tp-yt-paper-button,[role="button"]');
            if (!buttons) continue;
            for (const button of Array.from(buttons).reverse()) {
              if (isVisible(button) && isAddButton(button)) return clickElement(button);
            }
          }
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for selector in selector_patterns:
            try:
                button = page.locator(selector).first
                if button.count() and button.is_visible(timeout=500):
                    button.scroll_into_view_if_needed(timeout=1000)
                    button.click(timeout=2500)
                    log("Tombol Tambahkan subtitle diklik.")
                    return True
            except Exception:
                continue
        try:
            rect = page.evaluate(rect_script)
            if isinstance(rect, dict) and rect.get("x") is not None and rect.get("y") is not None:
                page.mouse.move(float(rect["x"]), float(rect["y"]))
                page.mouse.down()
                time.sleep(0.08)
                page.mouse.up()
                log("Tombol Tambahkan subtitle diklik.")
                return True
        except Exception:
            pass
        try:
            if page.evaluate(script):
                log("Tombol Tambahkan subtitle diklik.")
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def click_manual_subtitle_mode(page, timeout_ms: int = 10000) -> bool:
    selector_patterns = (
        "button#choose-type-manually",
        "#choose-type-manually",
    )
    rect_script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
        element.id,
      ].filter(Boolean).join('\\n').toLowerCase();
      const candidates = [];
      for (const root of roots) {
        const byId = root.querySelector?.('#choose-type-manually');
        if (byId && isVisible(byId)) candidates.push(byId);
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('button,[role="button"],li')) : [];
        for (const element of elements) {
          const label = labelOf(element);
          if ((label.includes('ketik manual') || label.includes('type manually')) && isVisible(element)) {
            candidates.push(element);
          }
        }
      }
      for (const element of candidates) {
        const help = element.querySelector?.('ytcp-icon-tooltip,yt-icon[aria-label]');
        const target = element.matches?.('button,[role="button"]') ? element : element.querySelector?.('button,[role="button"]') || element;
        const rect = target.getBoundingClientRect?.();
        if (!rect || rect.width <= 0 || rect.height <= 0) continue;
        target.scrollIntoView?.({ block: 'center', inline: 'center' });
        const nextRect = target.getBoundingClientRect();
        let x = nextRect.left + nextRect.width * 0.35;
        if (help?.getBoundingClientRect) {
          const helpRect = help.getBoundingClientRect();
          x = Math.min(x, helpRect.left - 24);
        }
        return {
          x,
          y: nextRect.top + nextRect.height / 2,
        };
      }
      return null;
    }
    """
    dispatch_script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      for (const root of roots) {
        const button = root.querySelector?.('#choose-type-manually');
        if (!button || !isVisible(button)) continue;
        button.scrollIntoView?.({ block: 'center', inline: 'center' });
        const rect = button.getBoundingClientRect();
        const x = rect.left + rect.width * 0.35;
        const y = rect.top + rect.height / 2;
        const options = { bubbles: true, cancelable: true, composed: true, clientX: x, clientY: y };
        button.dispatchEvent(new PointerEvent('pointerdown', options));
        button.dispatchEvent(new MouseEvent('mousedown', options));
        button.dispatchEvent(new PointerEvent('pointerup', options));
        button.dispatchEvent(new MouseEvent('mouseup', options));
        button.dispatchEvent(new MouseEvent('click', options));
        button.click();
        return true;
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for selector in selector_patterns:
            try:
                button = page.locator(selector).first
                if button.count() and button.is_visible(timeout=500):
                    button.scroll_into_view_if_needed(timeout=1000)
                    button.click(timeout=2500)
                    log("Mode subtitle manual dipilih.")
                    return True
            except Exception:
                continue
        try:
            rect = page.evaluate(rect_script)
            if isinstance(rect, dict) and rect.get("x") is not None and rect.get("y") is not None:
                page.mouse.move(float(rect["x"]), float(rect["y"]))
                page.mouse.down()
                time.sleep(0.08)
                page.mouse.up()
                log("Mode subtitle manual dipilih.")
                return True
        except Exception:
            pass
        try:
            if page.evaluate(dispatch_script):
                log("Mode subtitle manual dipilih.")
                return True
        except Exception:
            pass
        if deep_click(
            page,
            selectors=("button#choose-type-manually", "#choose-type-manually"),
            text_patterns=(r"^ketik manual$", r"^type manually$"),
            timeout_ms=700,
            optional=True,
        ):
            log("Mode subtitle manual dipilih.")
            return True
        time.sleep(0.25)
    return False


def subtitle_textbox_exists(page) -> bool:
    script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const badLabel = /(time|waktu|timestamp|menit|detik|frame|media-timestamp|search|cari|judul|deskripsi|description)/i;
      const timeValue = /^\\s*\\d{1,2}:\\d{2}(?::\\d{2})?(?:[.,]\\d+)?\\s*$/;
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll('textarea,input[type="text"],[contenteditable="true"],[role="textbox"]'))
          : [];
        for (const element of elements) {
          if (!isVisible(element) || element.disabled || element.readOnly) continue;
          const label = [
            element.getAttribute?.('aria-label'),
            element.getAttribute?.('placeholder'),
            element.getAttribute?.('title'),
            element.getAttribute?.('name'),
            element.id,
            element.className,
            element.value,
          ].filter(Boolean).join('\\n').toLowerCase();
          const value = String(element.value || element.textContent || '');
          const ancestorLabel = String(element.closest?.('ytcp-media-timestamp-input,ytve-toolbar')?.tagName || '').toLowerCase();
          if (badLabel.test(label) || ancestorLabel || timeValue.test(value)) continue;
          return true;
        }
      }
      return false;
    }
    """
    try:
        return bool(page.evaluate(script))
    except Exception:
        return False


def click_add_subtitle_segment(page, timeout_ms: int = 8000) -> bool:
    selector_patterns = (
        "ytcp-button#add-segment-button button",
        "ytcp-button#add-segment-button",
        "#add-segment-button button",
        "#add-segment-button",
    )
    rect_script = """
    () => {
      const candidates = [
        document.querySelector('ytcp-button#add-segment-button button'),
        document.querySelector('ytcp-button#add-segment-button'),
        document.querySelector('#add-segment-button button'),
        document.querySelector('#add-segment-button'),
      ].filter(Boolean);
      for (const element of candidates) {
        const rect = element.getBoundingClientRect?.();
        if (!rect || rect.width <= 0 || rect.height <= 0) continue;
        const style = window.getComputedStyle(element);
        if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        element.scrollIntoView?.({ block: 'center', inline: 'center' });
        const nextRect = element.getBoundingClientRect();
        return {
          x: nextRect.left + nextRect.width / 2,
          y: nextRect.top + nextRect.height / 2,
        };
      }
      return null;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for selector in selector_patterns:
            try:
                button = page.locator(selector).first
                if button.count() and button.is_visible(timeout=500):
                    button.scroll_into_view_if_needed(timeout=1000)
                    button.click(timeout=2500)
                    log("Tombol + Subtitel diklik untuk membuat kolom manual.")
                    return True
            except Exception:
                continue
        try:
            rect = page.evaluate(rect_script)
            if isinstance(rect, dict) and rect.get("x") is not None and rect.get("y") is not None:
                page.mouse.move(float(rect["x"]), float(rect["y"]))
                page.mouse.down()
                time.sleep(0.08)
                page.mouse.up()
                log("Tombol + Subtitel diklik untuk membuat kolom manual.")
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def human_type_text(page, text: str, delay_ms: int = 120) -> None:
    for char in text:
        if char == "\n":
            page.keyboard.press("Enter")
        elif char == "\t":
            page.keyboard.press("Tab")
        elif char == " ":
            page.keyboard.press("Space")
        elif "A" <= char <= "Z":
            page.keyboard.down("Shift")
            page.keyboard.press(char)
            page.keyboard.up("Shift")
        else:
            page.keyboard.type(char, delay=0)
        time.sleep(max(0, delay_ms) / 1000)


def focus_subtitle_textarea(page) -> bool:
    script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const candidates = [];
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll(
              'ytve-lightweight-textarea textarea, textarea[aria-label*="Subtitel" i], textarea[aria-label*="Subtitle" i], textarea[aria-label*="Caption" i]'
            ))
          : [];
        for (const element of elements) {
          if (!isVisible(element) || element.disabled || element.readOnly) continue;
          const rect = element.getBoundingClientRect();
          candidates.push({ element, score: (rect.width * rect.height) + (element.closest('ytve-captions-editor-caption-segment-line[selected]') ? 100000 : 0) });
        }
      }
      candidates.sort((a, b) => b.score - a.score);
      const target = candidates[0]?.element;
      if (!target) return false;
      target.scrollIntoView?.({ block: 'center', inline: 'center' });
      target.focus?.();
      target.click?.();
      return true;
    }
    """
    try:
        return bool(page.evaluate(script))
    except Exception:
        return False


def force_fill_subtitle_textarea(page, text: str) -> bool:
    script = """
    ({ text }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const candidates = [];
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll(
              'ytve-lightweight-textarea textarea, textarea[aria-label*="Subtitel" i], textarea[aria-label*="Subtitle" i], textarea[aria-label*="Caption" i]'
            ))
          : [];
        for (const element of elements) {
          if (!isVisible(element) || element.disabled || element.readOnly) continue;
          const rect = element.getBoundingClientRect();
          candidates.push({ element, score: (rect.width * rect.height) + (element.closest('ytve-captions-editor-caption-segment-line[selected]') ? 100000 : 0) });
        }
      }
      candidates.sort((a, b) => b.score - a.score);
      const target = candidates[0]?.element;
      if (!target) return false;
      target.scrollIntoView?.({ block: 'center', inline: 'center' });
      target.focus?.();
      target.click?.();

      try {
        target.select?.();
        document.execCommand?.('delete', false);
        document.execCommand?.('insertText', false, text);
      } catch (_) {}

      const setNativeValue = (element, value) => {
        const proto = element instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : element instanceof HTMLInputElement
            ? HTMLInputElement.prototype
            : null;
        const descriptor = proto ? Object.getOwnPropertyDescriptor(proto, 'value') : null;
        if (descriptor?.set) descriptor.set.call(element, value);
        else element.value = value;
      };
      setNativeValue(target, text);
      target.textContent = text;
      target.setAttribute('value', text);
      try {
        target.selectionStart = text.length;
        target.selectionEnd = text.length;
      } catch (_) {}

      const events = [
        new InputEvent('beforeinput', { bubbles: true, composed: true, cancelable: true, inputType: 'insertText', data: text }),
        new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: text }),
        new Event('change', { bubbles: true, composed: true }),
        new KeyboardEvent('keyup', { bubbles: true, composed: true, key: text.slice(-1) || ' ' }),
      ];
      for (const event of events) target.dispatchEvent(event);

      const wrapper = target.closest('ytve-lightweight-textarea');
      if (wrapper) {
        try { wrapper.value = text; } catch (_) {}
        wrapper.setAttribute('value', text);
        wrapper.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: text }));
        wrapper.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
      }

      return String(target.value || target.textContent || '').trim().includes(String(text).trim());
    }
    """
    try:
        return bool(page.evaluate(script, {"text": text}))
    except Exception:
        return False


def type_subtitle_text(page, subtitle_text: str, timeout_ms: int = 15000) -> bool:
    subtitle_text = os.environ.get("YOUTUBE_MANUAL_SUBTITLE_TEXT", subtitle_text).strip() or subtitle_text or "FCN"
    add_patterns = (r"^tambahkan teks$", r"^add text$", r"^tambahkan subtitle$", r"^add subtitle$")
    ready_delay_ms = max(0, int(os.environ.get("YOUTUBE_SUBTITLE_EDITOR_READY_DELAY_MS", "2500")))
    if ready_delay_ms:
        log(f"Menunggu editor subtitle siap {ready_delay_ms}ms sebelum isi dari env.")
        time.sleep(ready_delay_ms / 1000)
    if not subtitle_textbox_exists(page):
        if click_add_subtitle_segment(page, timeout_ms=8000):
            segment_delay_ms = max(0, int(os.environ.get("YOUTUBE_SUBTITLE_SEGMENT_READY_DELAY_MS", "5000")))
            if segment_delay_ms:
                log(f"Menunggu kolom subtitle muncul {segment_delay_ms}ms setelah klik + Subtitel.")
                time.sleep(segment_delay_ms / 1000)
        else:
            log("Tombol + Subtitel tidak ditemukan; mencoba deteksi kolom manual langsung.")
    focus_script = """
    () => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const labelOf = (element) => [
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('placeholder'),
        element.getAttribute?.('title'),
        element.getAttribute?.('name'),
        element.id,
        element.className,
        element.textContent,
        element.value,
      ].filter(Boolean).join('\\n').toLowerCase();
      const badLabel = /(time|waktu|timestamp|menit|detik|frame|media-timestamp|search|cari|judul|deskripsi|description)/i;
      const goodLabel = /(subtitle|caption|teks|text|transkrip|transcript)/i;
      const timeValue = /^\\s*\\d{1,2}:\\d{2}(?::\\d{2})?(?:[.,]\\d+)?\\s*$/;
      const candidates = [];
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll('textarea,input[type="text"],[contenteditable="true"],[role="textbox"]'))
          : [];
        for (const element of elements) {
          if (!isVisible(element) || element.disabled || element.readOnly) continue;
          const label = labelOf(element);
          const value = String(element.value || element.textContent || '');
          const ancestorLabel = String(element.closest?.('ytcp-media-timestamp-input,ytve-toolbar')?.tagName || '').toLowerCase();
          if (badLabel.test(label) || ancestorLabel || timeValue.test(value)) continue;
          const rect = element.getBoundingClientRect();
          const score = (goodLabel.test(label) ? 1000 : 0) + Math.min(500, rect.width + rect.height);
          candidates.push({ element, score });
        }
      }
      candidates.sort((a, b) => b.score - a.score);
      const best = candidates[0]?.element;
      if (!best) return false;
      best.scrollIntoView?.({ block: 'center', inline: 'center' });
      best.click();
      best.focus?.();
      return true;
    }
    """
    verify_script = """
    ({ text }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let i = 0; i < roots.length; i += 1) {
        const root = roots[i];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const needle = String(text || '').trim();
      if (!needle) return false;
      for (const root of roots) {
        const elements = root.querySelectorAll
          ? Array.from(root.querySelectorAll('textarea,input[type="text"],[contenteditable="true"],[role="textbox"]'))
          : [];
        for (const element of elements) {
          const value = String(element.value || element.innerText || element.textContent || '').trim();
          if (value.includes(needle)) return true;
        }
      }
      return false;
    }
    """
    field_selectors = (
        'ytve-lightweight-textarea textarea',
        'textarea[aria-label*="Subtitel" i]',
        'textarea[aria-label*="subtitle" i]',
        'textarea[aria-label*="caption" i]',
        'textarea[aria-label*="teks" i]',
        'textarea',
        '[contenteditable="true"]',
        '[role="textbox"]',
    )
    deadline = time.monotonic() + timeout_ms / 1000
    typed_once = False

    def fill_and_verify() -> bool:
        if not focus_subtitle_textarea():
            try:
                page.evaluate(focus_script)
            except Exception:
                pass
        time.sleep(0.3)
        if force_fill_subtitle_textarea(page, subtitle_text):
            time.sleep(1)
            try:
                if page.evaluate(verify_script, {"text": subtitle_text}):
                    log(f"Subtitle manual diisi dari env dan terverifikasi: {subtitle_text}.")
                    return True
            except Exception:
                pass
        try:
            if page.evaluate(verify_script, {"text": subtitle_text}):
                log(f"Subtitle manual diisi dari env dan terverifikasi: {subtitle_text}.")
                return True
        except Exception:
            pass
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass
        if focus_subtitle_textarea():
            force_fill_subtitle_textarea(page, subtitle_text)
            time.sleep(1)
            try:
                if page.evaluate(verify_script, {"text": subtitle_text}):
                    log(f"Subtitle manual diisi dari env dan terverifikasi: {subtitle_text}.")
                    return True
            except Exception:
                pass
        log("Subtitle manual belum terdeteksi setelah diisi dari env; mencoba ulang.")
        return False

    while time.monotonic() < deadline:
        try:
            if page.evaluate(focus_script):
                if fill_and_verify():
                    return True
        except Exception:
            pass
        for selector in field_selectors:
            try:
                field = page.locator(selector).first
                if field.count() and field.is_visible(timeout=500):
                    field.click(timeout=2000)
                    if fill_and_verify():
                        return True
            except Exception:
                continue
        if not typed_once:
            if not subtitle_textbox_exists(page) and click_add_subtitle_segment(page, timeout_ms=1200):
                typed_once = True
                time.sleep(max(0.8, int(os.environ.get("YOUTUBE_SUBTITLE_SEGMENT_READY_DELAY_MS", "5000")) / 1000))
                continue
            if click_role_button(page, add_patterns, timeout_ms=900, optional=True) or deep_click(
                page,
                text_patterns=add_patterns,
                timeout_ms=900,
                optional=True,
            ):
                typed_once = True
                time.sleep(0.7)
                continue
        time.sleep(0.3)
    return False


def click_subtitle_done(page, timeout_ms: int = 12000) -> bool:
    patterns = [r"^selesai$|^done$"]
    if click_role_button(page, patterns, timeout_ms=timeout_ms, optional=True):
        log("Subtitle manual disimpan.")
        return True
    if deep_click(page, text_patterns=patterns, timeout_ms=timeout_ms, optional=True):
        log("Subtitle manual disimpan.")
        return True
    return False


def close_subtitle_editor(page, timeout_ms: int = 5000) -> bool:
    if click_subtitle_done(page, timeout_ms=min(timeout_ms, 3000)):
        return True
    if deep_click(
        page,
        selectors=(
            'ytcp-dialog button[aria-label*="Close" i]',
            'ytcp-dialog button[aria-label*="Tutup" i]',
            'ytcp-dialog ytcp-icon-button[aria-label*="Close" i]',
            'ytcp-dialog ytcp-icon-button[aria-label*="Tutup" i]',
            'ytcp-dialog #close-button',
            'button[aria-label*="Close" i]',
            'button[aria-label*="Tutup" i]',
        ),
        text_patterns=(r"^close$", r"^tutup$"),
        timeout_ms=timeout_ms,
        optional=True,
    ):
        log("Editor subtitle ditutup agar upload bisa lanjut.")
        return True
    try:
        page.keyboard.press("Escape")
        time.sleep(1)
        log("Escape dikirim untuk keluar dari editor subtitle.")
        return True
    except Exception:
        return False


def add_manual_subtitle(page, subtitle_text: str = "FCN") -> bool:
    subtitle_text = os.environ.get("YOUTUBE_MANUAL_SUBTITLE_TEXT", subtitle_text).strip() or subtitle_text or "FCN"
    subtitle_required = env_bool("YOUTUBE_MANUAL_SUBTITLE_REQUIRED", False)
    subtitle_enabled = env_bool("YOUTUBE_ADD_MANUAL_SUBTITLE", subtitle_required)
    if not subtitle_enabled:
        log("Subtitle manual dilewati agar upload lebih cepat.")
        return False
    add_timeout_ms = int(os.environ.get("YOUTUBE_SUBTITLE_ADD_TIMEOUT_MS", "5000" if not subtitle_required else "10000"))
    mode_timeout_ms = int(os.environ.get("YOUTUBE_SUBTITLE_MODE_TIMEOUT_MS", "5000" if not subtitle_required else "10000"))
    type_timeout_ms = int(os.environ.get("YOUTUBE_SUBTITLE_TEXT_TIMEOUT_MS", "8000" if not subtitle_required else "15000"))
    done_timeout_ms = int(os.environ.get("YOUTUBE_SUBTITLE_DONE_TIMEOUT_MS", "5000" if not subtitle_required else "12000"))
    log(f"Menambahkan subtitle manual: {subtitle_text}.")
    if not click_add_subtitle(page, timeout_ms=add_timeout_ms):
        save_debug_artifacts(page, "subtitle-add-button-not-found")
        message = "Tombol Tambahkan subtitle tidak ditemukan; subtitle dilewati."
        if subtitle_required:
            raise UploadError(message)
        log(message)
        return False
    time.sleep(1)
    if not click_manual_subtitle_mode(page, timeout_ms=mode_timeout_ms):
        save_debug_artifacts(page, "subtitle-manual-mode-not-found")
        close_subtitle_editor(page, timeout_ms=4000)
        message = "Opsi Ketik manual subtitle tidak ditemukan; subtitle dilewati."
        if subtitle_required:
            raise UploadError(message)
        log(message)
        return False
    time.sleep(1)
    subtitle_filled = type_subtitle_text(page, subtitle_text, timeout_ms=type_timeout_ms)
    if not subtitle_filled:
        log(f"Subtitle '{subtitle_text}' belum terverifikasi; mencoba force-fill terakhir.")
        subtitle_filled = force_fill_subtitle_textarea(page, subtitle_text)
        if subtitle_filled:
            log(f"Subtitle force-fill terverifikasi: {subtitle_text}.")
            time.sleep(0.5)
    if not subtitle_filled:
        save_debug_artifacts(page, "subtitle-textbox-not-found")
        if subtitle_required:
            raise UploadError(
                f"Kolom subtitle ditemukan tetapi teks '{subtitle_text}' belum berhasil diisi dan diverifikasi."
            )
        log(f"Subtitle '{subtitle_text}' gagal diisi; subtitle akan dilewati.")
    after_type_delay_ms = max(0, int(os.environ.get("YOUTUBE_SUBTITLE_AFTER_TYPE_DELAY_MS", "2000")))
    if after_type_delay_ms:
        log(f"Menunggu {after_type_delay_ms}ms setelah subtitle selesai diisi.")
        time.sleep(after_type_delay_ms / 1000)
    if click_subtitle_done(page, timeout_ms=done_timeout_ms):
        time.sleep(0.5)
        return subtitle_filled
    if subtitle_required:
        save_debug_artifacts(page, "subtitle-done-not-found")
        raise UploadError("Tombol Selesai subtitle tidak ditemukan; upload dihentikan agar subtitle tidak terlewati.")
    if not close_subtitle_editor(page, timeout_ms=done_timeout_ms):
        save_debug_artifacts(page, "subtitle-done-not-found")
        message = "Tombol Selesai subtitle tidak ditemukan; subtitle dilewati agar upload tetap lanjut."
        if subtitle_required:
            raise UploadError(message)
        log(message)
        return False
    time.sleep(0.5)
    return subtitle_filled


def wait_for_copyright_checks(page, timeout_ms: int, require_checks: bool = True) -> None:
    log("Menunggu YouTube Studio Checks sampai semua pemeriksaan aman...")
    deadline = time.monotonic() + timeout_ms / 1000
    issue_patterns = (
        r"copyright claim",
        r"copyright issue",
        r"restrictions? found",
        r"klaim hak cipta",
        r"masalah hak cipta",
        r"pembatasan.*ditemukan",
        r"masalah ditemukan",
    )
    checking_patterns = (
        r"sedang memeriksa",
        r"checking",
        r"checks?.*(started|running|in progress)",
        r"memeriksa\s+\d+%",
        r"\d+\s+menit lagi",
        r"\d+\s+seconds? remaining",
        r"\d+\s+minutes? remaining",
        r"memeriksa masalah (hak cipta|pedoman komunitas|copyright|community)",
        r"memeriksa masalah dengan",
        r"(hak cipta|pedoman komunitas).*memeriksa masalah",
        r"pedoman komunitas.*sedang memeriksa",
        r"community guidelines.*checking",
    )
    complete_patterns = (
        r"checks complete",
        r"pemeriksaan selesai",
    )
    all_clear_patterns = (
        (r"hak cipta\s+tidak ditemukan masalah", r"pedoman komunitas\s+tidak ditemukan masalah"),
        (r"copyright\s+no issues found", r"community guidelines\s+no issues found"),
    )

    last_body = ""
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        try:
            dialog = page.locator("ytcp-uploads-dialog")
            body = dialog.inner_text(timeout=3000) if dialog.count() else page.locator("body").inner_text(timeout=3000)
        except Exception:
            time.sleep(1)
            continue
        lowered = body.lower()
        last_body = re.sub(r"\s+", " ", body).strip()[:500]
        has_checking = any(re.search(pattern, lowered, re.I) for pattern in checking_patterns)
        has_complete = any(re.search(pattern, lowered, re.I) for pattern in complete_patterns)
        has_all_clear = any(
            all(re.search(pattern, lowered, re.I) for pattern in pattern_group)
            for pattern_group in all_clear_patterns
        )
        if any(re.search(pattern, lowered, re.I) for pattern in issue_patterns):
            raise UploadError(
                "YouTube Studio mendeteksi potensi copyright/restriction pada clip ini. "
                "Upload dibatalkan sebelum publish agar channel tetap aman."
            )
        if has_checking:
            log("Checks masih berjalan; menunggu sampai semua centang aman.")
            time.sleep(5)
            continue
        if has_all_clear:
            log("YouTube Studio Checks aman: hak cipta dan pedoman komunitas sudah centang.")
            return
        if has_complete:
            log("YouTube Studio Checks selesai: tidak ada masalah terdeteksi.")
            return
        time.sleep(2)

    if require_checks:
        if env_bool("YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK", False):
            log(
                "Checks belum terkonfirmasi sampai timeout, tetapi tidak ada issue eksplisit; "
                "lanjut ke Visibilitas sesuai konfigurasi."
            )
            return
        save_debug_artifacts(page, "checks-not-complete")
        raise UploadError(
            "Step 3 Checks belum selesai/tercentang sebelum timeout; upload tidak dilanjutkan ke Visibilitas. "
            f"Upload dibatalkan demi keamanan. Cuplikan halaman: {last_body}"
        )
    log("Checks belum terkonfirmasi; melanjutkan karena require checks dinonaktifkan.")


def normalize_youtube_video_url(value: str) -> str:
    clean = (value or "").strip().strip(".,;)'\"<>")
    if not clean:
        return ""
    if clean.startswith("//"):
        clean = f"https:{clean}"
    elif clean.startswith("/watch") or clean.startswith("/shorts/"):
        clean = f"https://www.youtube.com{clean}"
    elif clean.startswith("youtube.com/"):
        clean = f"https://{clean}"
    elif clean.startswith("www.youtube.com/"):
        clean = f"https://{clean}"
    elif clean.startswith("youtu.be/"):
        clean = f"https://{clean}"

    match = re.search(
        r"(?:https?://)?(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)([A-Za-z0-9_-]{6,})",
        clean,
        re.I,
    )
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    match = re.search(r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{6,})", clean, re.I)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return ""


def extract_video_url(page) -> str:
    try:
        video_id = page.locator("ytcp-uploads-dialog").first.get_attribute("video-id", timeout=1000) or ""
        if re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id.strip()):
            return f"https://www.youtube.com/watch?v={video_id.strip()}"
    except Exception:
        pass
    candidates = [
        'a[href*="youtu.be/"]',
        'a[href*="youtube.com/watch"]',
        'a[href*="youtube.com/shorts/"]',
        'a[href*="/watch?v="]',
        'a[href*="/shorts/"]',
        'ytcp-video-info a',
    ]
    for selector in candidates:
        try:
            items = page.locator(selector)
            for index in range(min(items.count(), 8)):
                href = items.nth(index).get_attribute("href") or ""
                video_url = normalize_youtube_video_url(href)
                if video_url:
                    return video_url
        except Exception:
            continue
    return ""


def wait_for_final_upload_confirmation(page, timeout_ms: int, video_url: str = "") -> str:
    deadline = time.monotonic() + timeout_ms / 1000
    done_patterns = (
        r"video (published|uploaded)",
        r"upload complete",
        r"processing will begin shortly",
        r"video (berhasil )?(telah )?dipublikasikan",
        r"berhasil dipublikasikan",
        r"upload selesai",
    )
    last_body = ""
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        try:
            dialog_count = page.locator("ytcp-uploads-dialog").count()
            if dialog_count == 0:
                log("Modal upload sudah tertutup setelah publish.")
                return video_url or extract_video_url(page)
        except Exception:
            pass
        try:
            body = page.locator("ytcp-uploads-dialog").inner_text(timeout=3000)
            last_body = re.sub(r"\s+", " ", body).strip()[:500]
            if any(re.search(pattern, body, re.I) for pattern in done_patterns):
                log("Konfirmasi final upload terdeteksi.")
                return video_url or extract_video_url(page)
        except Exception:
            pass
        time.sleep(3)
    raise UploadError(
        "Upload YouTube belum terkonfirmasi selesai sampai timeout. "
        f"Tab Chrome dibiarkan terbuka untuk dicek manual. Cuplikan halaman: {last_body}"
    )


def reload_after_publish(page) -> None:
    if not env_bool("YOUTUBE_RELOAD_AFTER_PUBLISH", True):
        log("Reload otomatis setelah publish dinonaktifkan.")
        return
    try:
        delay_seconds = max(0, int(os.environ.get("YOUTUBE_RELOAD_AFTER_PUBLISH_DELAY_SECONDS", "10")))
        if delay_seconds:
            log(f"Publish sudah diterima; menunggu {delay_seconds} detik sebelum reload terakhir.")
            time.sleep(delay_seconds)

        def accept_once(dialog) -> None:
            try:
                dialog.accept()
            except Exception:
                pass

        try:
            page.once("dialog", accept_once)
        except Exception:
            pass
        page.reload(wait_until="domcontentloaded", timeout=30000)
        log("Page direload sekali; proses upload selesai.")
    except Exception as exc:
        save_debug_artifacts(page, "reload-after-publish-failed")
        raise UploadError(f"Publish sudah diklik, tetapi reload terakhir gagal: {exc}") from exc


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
        install_context_dialog_guard(context)
        page = context.new_page()
        install_browser_dialog_guard(page)
        goto_studio(page, studio_url=args.studio_url)
        log("Login ke akun YouTube di browser yang terbuka.")
        if args.auto_close:
            log("Setelah login berhasil dan dashboard YouTube Studio tampil, browser akan ditutup otomatis.")
            deadline = time.monotonic() + max(60, int(args.timeout)) 
            last_error = ""
            while time.monotonic() < deadline:
                try:
                    current_url = page.url.lower()
                    if "studio.youtube.com" not in current_url and "accounts.google.com" not in current_url:
                        goto_studio(page, studio_url=args.studio_url)
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
            goto_studio(page, studio_url=args.studio_url)
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
                "Chrome remote debugging belum aktif. Jalur utama upload memakai Playwright storage-state; "
                "pakai Login Sekali dulu, atau aktifkan CDP hanya untuk Ambil Cookies CDP."
            ) from exc
        contexts = browser.contexts or [browser.new_context()]
        for context in contexts:
            install_context_dialog_guard(context)
        pages = [item for context in contexts for item in context.pages]
        page = next((item for item in pages if "studio.youtube.com" in item.url.lower()), None)
        if page is None:
            context = contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
        hydrated_page = (
            hydrate_context_and_open_studio_page(page.context, state_path, args.studio_url)
            if args.hydrate_storage_state
            else None
        )
        hydrated = hydrated_page is not None
        if hydrated_page is not None:
            page = hydrated_page
        install_browser_dialog_guard(page)
        if not hydrated and "studio.youtube.com" not in page.url.lower():
            goto_studio(page, studio_url=args.studio_url)
        else:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            if args.target_channel_id and not page_url_matches_channel_id(page, args.target_channel_id):
                log("Tab Studio CDP belum berada di channel target; membuka Studio channel target.")
                goto_studio(page, studio_url=args.studio_url)
        resolve_google_account_chooser(page, args.target_email, studio_url=args.studio_url)
        ensure_logged_in(page)
        ensure_target_identity(page, args.target_channel, args.target_email, args.target_channel_id)
        page.context.storage_state(path=str(state_path))
        browser.close()
    log(f"Sesi YouTube dari browser tersimpan: {state_path}")


def run_check_login(args: argparse.Namespace) -> None:
    sync_playwright, _ = import_playwright()
    state_path = Path(args.state).expanduser().resolve()
    chromium_user_data_dir = Path(args.chromium_user_data_dir).expanduser().resolve() if args.chromium_user_data_dir else None
    if chromium_user_data_dir is not None and not chromium_user_data_dir.is_dir():
        raise UploadError(f"Folder profile Chromium tidak ditemukan: {chromium_user_data_dir}")
    if chromium_user_data_dir is None and not state_path.is_file():
        raise UploadError(f"File sesi YouTube belum ada: {state_path}")

    headless = env_bool("YOUTUBE_LOGIN_HEADLESS", True)
    slow_mo = int(os.environ.get("YOUTUBE_BROWSER_SLOW_MO_MS", "0"))
    launch_args = []
    if chromium_user_data_dir is not None and args.chromium_profile_directory:
        launch_args.append(f"--profile-directory={args.chromium_profile_directory}")
    with sync_playwright() as playwright:
        browser = None
        if chromium_user_data_dir is not None:
            log(f"Validasi login memakai profile Chromium: {chromium_user_data_dir}")
            context = playwright.chromium.launch_persistent_context(
                str(chromium_user_data_dir),
                headless=headless,
                slow_mo=slow_mo,
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                viewport={"width": 1440, "height": 1000},
                args=launch_args,
            )
            page = context.pages[0] if context.pages else context.new_page()
        else:
            log(f"Validasi login memakai Playwright storage-state: {state_path}")
            browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo, args=launch_args)
            context = browser.new_context(
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                storage_state=str(state_path),
                viewport={"width": 1440, "height": 1000},
            )
            page = context.new_page()
        install_context_dialog_guard(context)
        install_browser_dialog_guard(page)
        goto_studio(page, studio_url=args.studio_url)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        ensure_logged_in(page)
        ensure_target_identity(page, args.target_channel, args.target_email, args.target_channel_id)
        context.storage_state(path=str(state_path))
        context.close()
        if browser is not None:
            browser.close()
    log(f"Session YouTube valid dan tersimpan: {state_path}")


def run_upload(args: argparse.Namespace) -> None:
    sync_playwright, PlaywrightTimeoutError = import_playwright()
    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        raise UploadError(f"File video tidak ditemukan: {video_path}")

    state_path = Path(args.state).expanduser().resolve()
    chromium_user_data_dir = Path(args.chromium_user_data_dir).expanduser().resolve() if args.chromium_user_data_dir else None
    if chromium_user_data_dir is not None and not chromium_user_data_dir.is_dir():
        raise UploadError(f"Folder profile Chromium tidak ditemukan: {chromium_user_data_dir}")
    if not args.use_cdp and chromium_user_data_dir is None and not state_path.is_file():
        raise UploadError(
            f"File sesi YouTube belum ada: {state_path}. Jalankan `python youtube_uploader.py login` terlebih dahulu "
            "atau set YOUTUBE_CHROMIUM_USER_DATA_DIR ke profile Chromium yang sudah login."
        )

    upload_title, upload_description = normalized_upload_metadata(video_path, args.title, args.description)

    headless = args.headless if args.headless is not None else env_bool("YOUTUBE_HEADLESS", True)
    slow_mo = int(os.environ.get("YOUTUBE_BROWSER_SLOW_MO_MS", "0"))
    timeout_ms = max(60, int(args.timeout)) * 1000

    with sync_playwright() as playwright:
        browser = None
        context = None
        using_cdp = bool(args.use_cdp)
        launch_args = []
        if chromium_user_data_dir is not None and args.chromium_profile_directory:
            launch_args.append(f"--profile-directory={args.chromium_profile_directory}")
        if using_cdp:
            log(f"Menggunakan Chrome remote debugging: {args.cdp_url}")
            browser = playwright.chromium.connect_over_cdp(args.cdp_url, timeout=15000)
            contexts = browser.contexts or [browser.new_context()]
            for item in contexts:
                install_context_dialog_guard(item)
            context = contexts[0]
            studio_pages = [item for ctx in contexts for item in ctx.pages if "studio.youtube.com" in item.url.lower()]
            target_pages = [item for item in studio_pages if page_url_matches_channel_id(item, args.target_channel_id)]
            page = target_pages[0] if target_pages else (studio_pages[0] if studio_pages else context.new_page())
            hydrated_page = hydrate_context_and_open_studio_page(context, state_path, args.studio_url)
            if hydrated_page is not None:
                page = hydrated_page
        elif chromium_user_data_dir is not None:
            log(f"Menggunakan profile Chromium: {chromium_user_data_dir}")
            context = playwright.chromium.launch_persistent_context(
                str(chromium_user_data_dir),
                headless=headless,
                slow_mo=slow_mo,
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                viewport={"width": 1440, "height": 1000},
                args=launch_args,
            )
            install_context_dialog_guard(context)
            studio_pages = [item for item in context.pages if "studio.youtube.com" in item.url.lower()]
            page = studio_pages[0] if studio_pages else (context.pages[0] if context.pages else context.new_page())
        else:
            browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo, args=launch_args)
            context = browser.new_context(
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                storage_state=str(state_path),
                viewport={"width": 1440, "height": 1000},
            )
            install_context_dialog_guard(context)
            page = context.new_page()
        install_browser_dialog_guard(page)
        page.set_default_timeout(30000)

        try:
            open_upload_dialog(
                page,
                args.target_channel,
                args.target_email,
                args.target_channel_id,
                args.studio_url,
            )
            select_video_file(page, video_path, timeout_ms=30000)

            if not upload_metadata_form_ready(page, timeout_ms=60000):
                save_debug_artifacts(page, "upload-metadata-form-not-ready")
                raise UploadError("Form detail upload YouTube belum siap setelah file dipilih.")
            set_upload_text_field(
                page,
                upload_title,
                "judul",
                (r"(^|\n)(title|judul)(\n|$)", r"add a title", r"tambahkan judul"),
                reject_patterns=(r"description", r"deskripsi"),
            )
            set_upload_text_field(
                page,
                upload_description,
                "deskripsi",
                (r"(^|\n)(description|deskripsi)(\n|$)", r"tell viewers", r"beri tahu penonton"),
                reject_patterns=(r"(^|\n)(title|judul)(\n|$)",),
            )

            if args.thumbnail:
                log("Thumbnail dilewati sesuai konfigurasi; fokus ke judul, deskripsi, dan playlist.")

            select_playlist(page, args.playlist)
            if args.made_for_kids:
                click_text(page, [r"yes,.*made for kids", r"ya,.*anak"], timeout_ms=8000)
            else:
                click_text(page, [r"no,.*not made for kids", r"tidak,.*anak"], timeout_ms=8000)
            log("Setelan audiens dipilih.")
            if args.tags:
                log("Kolom Tags lanjutan dilewati; hashtag sudah dimasukkan ke deskripsi.")

            click_next_upload_step(page, timeout_ms=20000, expected_step="VIDEO_ELEMENTS")
            log("Masuk ke tab Elemen video.")
            subtitle_text = os.environ.get("YOUTUBE_MANUAL_SUBTITLE_TEXT", "FCN").strip() or "FCN"
            add_manual_subtitle(page, subtitle_text)

            click_next_upload_step(page, timeout_ms=20000, expected_step="CHECKS")
            log("Masuk ke tab Pemeriksaan awal.")
            wait_for_copyright_checks(
                page,
                min(timeout_ms, int(os.environ.get("YOUTUBE_CHECKS_TIMEOUT_SECONDS", "600")) * 1000),
                args.require_copyright_checks,
            )
            log("Step 3 Checks sudah selesai dan aman; lanjut ke Visibilitas.")

            click_next_upload_step(page, timeout_ms=20000, expected_step="REVIEW")
            log("Masuk ke tab Visibilitas.")
            wait_for_visibility_step(page, timeout_ms=20000)

            set_visibility(page, args.visibility)
            time.sleep(0.8)
            if not visibility_is_selected(page, args.visibility):
                save_debug_artifacts(page, "visibility-not-selected-before-final-action")
                raise UploadError(
                    f"Visibilitas '{args.visibility}' belum tercentang sebelum aksi final."
                )
            log(f"Step 4 Visibilitas terverifikasi: {args.visibility}.")
            if args.visibility == "public":
                review_timeout_ms = int(os.environ.get("YOUTUBE_PRE_PUBLISH_REVIEW_TIMEOUT_SECONDS", "300")) * 1000
                wait_for_review_checks_safe_before_publish(page, timeout_ms=review_timeout_ms)

            if args.dry_run:
                log("Dry-run aktif; proses berhenti sebelum publish/save final.")
                return

            uploaded_video_url = extract_video_url(page)
            click_final_upload_action(page, args.visibility, timeout_ms=30000)
            reload_after_publish(page)
            final_url = uploaded_video_url or extract_video_url(page)
            if final_url:
                log(f"VIDEO_URL: {final_url}")
            context.storage_state(path=str(state_path))
        finally:
            if using_cdp:
                log("Mode CDP aktif; tab Chrome manual dibiarkan terbuka.")
            else:
                close_upload_tab(page)
            if not using_cdp:
                context.close()
            if browser is not None and not using_cdp:
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
    login.add_argument("--studio-url", default=DEFAULT_STUDIO_URL)

    capture = subparsers.add_parser("capture-session", help="Ambil sesi dari Chrome remote debugging yang sudah login.")
    capture.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    capture.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    capture.add_argument("--target-channel", default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundyofficial"))
    capture.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL)
    capture.add_argument("--target-channel-id", default=DEFAULT_TARGET_CHANNEL_ID)
    capture.add_argument("--studio-url", default=DEFAULT_STUDIO_URL)
    capture.add_argument("--hydrate-storage-state", action=argparse.BooleanOptionalAction, default=True)

    check_login = subparsers.add_parser("check-login", help="Validasi sesi YouTube dan simpan ulang storage-state.")
    check_login.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    check_login.add_argument("--chromium-user-data-dir", default="")
    check_login.add_argument("--chromium-profile-directory", default=DEFAULT_CHROMIUM_PROFILE_DIRECTORY)
    check_login.add_argument("--target-channel", default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundyofficial"))
    check_login.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL)
    check_login.add_argument("--target-channel-id", default=DEFAULT_TARGET_CHANNEL_ID)
    check_login.add_argument("--studio-url", default=DEFAULT_STUDIO_URL)

    upload = subparsers.add_parser("upload", help="Upload satu file video ke YouTube Studio.")
    upload.add_argument("video")
    upload.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    upload.add_argument("--title", required=True)
    upload.add_argument("--description", default="")
    upload.add_argument("--thumbnail", default="")
    upload.add_argument("--visibility", choices=["private", "unlisted", "public"], default=os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "public"))
    upload.add_argument("--tags", default="")
    upload.add_argument("--playlist", default=os.environ.get("YOUTUBE_DEFAULT_PLAYLIST", "Islam"))
    upload.add_argument("--target-channel", default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundyofficial"))
    upload.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL)
    upload.add_argument("--target-channel-id", default=DEFAULT_TARGET_CHANNEL_ID)
    upload.add_argument("--studio-url", default=DEFAULT_STUDIO_URL)
    upload.add_argument("--use-cdp", action=argparse.BooleanOptionalAction, default=env_bool("YOUTUBE_UPLOAD_USE_CDP", False))
    upload.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
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
        elif args.command == "check-login":
            run_check_login(args)
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
