from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import imageio_ffmpeg


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path(os.environ.get("YOUTUBE_PLAYWRIGHT_STATE", BASE_DIR / "data" / "youtube_storage_state.json"))
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("YOUTUBE_UPLOAD_TIMEOUT_SECONDS", "5400"))
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
FENDY_CLIPPER_UPLOAD_PAGE_NAME = "fendy-clipper-youtube-upload"


class UploadError(RuntimeError):
    pass


class CopyrightClaimUploadError(UploadError):
    """A claim blocked publication, but the uploaded file can still be saved Private."""


class ThumbnailDailyLimitUploadError(UploadError):
    """Studio rejected a custom thumbnail because the channel hit its daily limit."""


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def safe_upload_visibility(requested: str) -> str:
    visibility = requested if requested in {"private", "unlisted", "public"} else "private"
    if visibility == "public" and not env_bool("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", False):
        return "private"
    return visibility


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
        if video_path.name.startswith(("highlight_5menit_", "resume_cerita_", "long_animate_"))
        else youtube_shorts_title(clean_title)
    )
    return normalized_title, clean_description[:5000]


def probe_upload_media_duration_seconds(video_path: Path) -> float:
    try:
        result = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(video_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception:
        return 0.0
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        f"{result.stderr}\n{result.stdout}",
    )
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


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


def open_advanced_upload_settings(page, timeout_ms: int = 8000) -> bool:
    """Open Studio's advanced metadata fields across its English/Indonesian labels."""
    selectors = (
        "ytcp-video-metadata-editor ytcp-button#toggle-button button",
        "ytcp-video-metadata-editor ytcp-button#toggle-button",
        'ytcp-video-metadata-editor button[aria-label*="advanced settings" i]',
        'ytcp-video-metadata-editor button[aria-label*="setelan lanjutan" i]',
    )
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() and locator.is_visible(timeout=250):
                    try:
                        toggle_copy = " ".join(
                            filter(
                                None,
                                (
                                    locator.inner_text(timeout=250),
                                    locator.get_attribute("aria-label", timeout=250),
                                ),
                            )
                        ).casefold()
                    except Exception:
                        toggle_copy = ""
                    if any(
                        marker in toggle_copy
                        for marker in (
                            "show less",
                            "hide advanced",
                            "tampilkan lebih sedikit",
                            "sembunyikan setelan",
                        )
                    ):
                        return True
                    locator.click(timeout=1500)
                    return True
            except Exception as exc:
                last_error = exc
        time.sleep(0.1)

    # The inner text is "Tampilkan lebih banyak", but Studio currently overrides
    # its accessible name with "Tampilkan setelan lanjutan". Keep both variants.
    if click_role_button(
        page,
        [
            r"show more",
            r"show advanced settings",
            r"advanced settings",
            r"tampilkan lebih banyak",
            r"tampilkan setelan lanjutan",
            r"setelan lanjutan",
            r"selengkapnya",
        ],
        timeout_ms=1500,
        optional=True,
    ):
        return True
    if click_text(
        page,
        [r"^show more$", r"^tampilkan lebih banyak$", r"^selengkapnya$"],
        timeout_ms=1500,
        optional=True,
    ):
        return True
    if last_error:
        log(f"Setelan lanjutan belum dapat dibuka lewat selector utama: {last_error}")
    return False


def altered_content_disclosure_result(page) -> dict[str, bool]:
    """Find, select, and report the verified state of Studio's disclosure field."""
    result = page.evaluate(
        r"""
        () => {
          const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim().toLowerCase();
          const anchors = [
            'altered content', 'altered or synthetic', 'synthetic content',
            'ai-generated content', 'ai generated content', 'ai use', 'use of ai',
            'konten yang diubah', 'konten diubah', 'konten sintetis',
            'konten buatan ai', 'penggunaan ai', 'pemakaian ai'
          ];
          const choiceSelector = [
            'tp-yt-paper-radio-button', 'ytcp-radio-button', '[role="radio"]',
            'input[type="radio"]', 'label'
          ].join(', ');
          const visible = (node) => {
            if (!(node instanceof Element)) return false;
            const style = window.getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden'
              && rect.width > 0 && rect.height > 0;
          };
          const choiceText = (choice) => normalize(
            choice.innerText || choice.textContent || choice.getAttribute('aria-label')
          );
          const isYes = (choice) => {
            const text = choiceText(choice);
            return /^(yes|ya)(\b|[,.])/.test(text)
              || text.includes('yes, it') || text.includes('ya, konten');
          };
          const isSelected = (choice) => {
            const candidates = [
              choice,
              choice.closest('tp-yt-paper-radio-button, ytcp-radio-button, [role="radio"], label'),
              choice.querySelector('input[type="radio"], [role="radio"]')
            ].filter(Boolean);
            return candidates.some((item) => item.checked === true
              || item.getAttribute('aria-checked') === 'true'
              || item.hasAttribute('checked'));
          };
          const domDistance = (left, right) => {
            const leftAncestors = new Map();
            let cursor = left;
            let distance = 0;
            while (cursor) {
              leftAncestors.set(cursor, distance);
              cursor = cursor.parentElement;
              distance += 1;
            }
            cursor = right;
            distance = 0;
            while (cursor) {
              if (leftAncestors.has(cursor)) return distance + leftAncestors.get(cursor);
              cursor = cursor.parentElement;
              distance += 1;
            }
            return Number.MAX_SAFE_INTEGER;
          };
          const nodes = [...document.querySelectorAll('body *')]
            .filter((node) => {
              const text = normalize(node.innerText || node.textContent);
              return visible(node) && text.length > 2 && text.length < 2600
                && anchors.some((item) => text.includes(item));
            })
            .sort((left, right) => normalize(left.innerText).length - normalize(right.innerText).length);

          const visited = new Set();
          for (const anchorNode of nodes) {
            let container = anchorNode;
            for (let depth = 0; container && container !== document.body && depth < 9; depth += 1) {
              if (visited.has(container)) {
                container = container.parentElement;
                continue;
              }
              visited.add(container);
              const sectionText = normalize(container.innerText || container.textContent);
              if (!anchors.some((item) => sectionText.includes(item))) {
                container = container.parentElement;
                continue;
              }
              const choices = [
                ...(container.matches(choiceSelector) ? [container] : []),
                ...container.querySelectorAll(choiceSelector)
              ].filter(visible);
              // If a broad Studio wrapper contains several radio groups, prefer
              // the Yes option nearest to this disclosure's own heading.
              const yes = choices
                .filter(isYes)
                .sort((left, right) => domDistance(anchorNode, left) - domDistance(anchorNode, right))[0];
              if (!yes) {
                container = container.parentElement;
                continue;
              }
              if (isSelected(yes)) return {found: true, clicked: false, selected: true};
              yes.scrollIntoView({block: 'center', inline: 'nearest'});
              yes.click();
              return {found: true, clicked: true, selected: isSelected(yes)};
            }
          }
          return {found: false, clicked: false, selected: false};
        }
        """
    )
    return {
        "found": bool(isinstance(result, dict) and result.get("found")),
        "clicked": bool(isinstance(result, dict) and result.get("clicked")),
        "selected": bool(isinstance(result, dict) and result.get("selected")),
    }


def set_altered_content_disclosure(page, required: bool) -> None:
    """Select and verify YouTube's disclosure when realistic scenery changed."""
    if not required:
        return
    advanced_opened = open_advanced_upload_settings(page)
    if advanced_opened:
        log("Setelan lanjutan YouTube Studio dibuka untuk disclosure AI/altered content.")

    deadline = time.monotonic() + 8000 / 1000
    found = False
    clicked = False
    try:
        while time.monotonic() < deadline:
            result = altered_content_disclosure_result(page)
            found = found or result["found"]
            clicked = clicked or result["clicked"]
            if result["selected"]:
                log("Disclosure altered content/AI use dipilih dan terverifikasi.")
                return
            time.sleep(0.2)
    except Exception as exc:
        save_debug_artifacts(page, "altered-content-disclosure-error")
        raise UploadError(f"Disclosure altered content/AI use gagal dipilih: {exc}") from exc

    save_debug_artifacts(
        page,
        "altered-content-disclosure-not-selected"
        if found or clicked
        else "altered-content-disclosure-not-found",
    )
    if found or clicked:
        raise UploadError(
            "Upload dihentikan: opsi Ya untuk disclosure Altered content/AI use ditemukan, "
            "tetapi YouTube Studio belum mengonfirmasi bahwa opsi tersebut terpilih."
        )
    raise UploadError(
        "Upload dihentikan: backdrop realistis telah diubah, tetapi pilihan disclosure "
        "Altered content/AI use tidak ditemukan setelah setelan lanjutan YouTube Studio dibuka."
    )


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


def active_upload_dialog_text(page, timeout_ms: int = 3000) -> str:
    """Read the visible upload dialog, ignoring stale hidden Studio dialogs."""
    script = r"""
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
      for (let index = 0; index < roots.length; index += 1) {
        const root = roots[index];
        const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const element of elements) {
          if (element.shadowRoot) addRoot(element.shadowRoot);
        }
      }
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        if (element.getAttribute?.('aria-hidden') === 'true') return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return Boolean(
          style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
        );
      };
      const candidates = [];
      for (const root of roots) {
        const dialogs = root.querySelectorAll
          ? Array.from(root.querySelectorAll('ytcp-uploads-dialog'))
          : [];
        for (const dialog of dialogs) {
          const surface = dialog.querySelector?.('tp-yt-paper-dialog#dialog, [role="dialog"]') || dialog;
          if (!isVisible(surface) && !isVisible(dialog)) continue;
          const rect = surface.getBoundingClientRect?.() || dialog.getBoundingClientRect();
          candidates.push({ dialog, score: (rect.width * rect.height) + rect.top + rect.left });
        }
      }
      candidates.sort((left, right) => right.score - left.score);
      const active = candidates[0]?.dialog;
      return active ? String(active.innerText || active.textContent || '') : '';
    }
    """
    try:
        body = str(page.evaluate(script) or "")
        if body.strip():
            return body
    except Exception:
        pass

    # Calling inner_text() on an unindexed collection throws in strict mode
    # when Studio keeps an old hidden upload dialog in the DOM.
    try:
        dialogs = page.locator("ytcp-uploads-dialog")
        for index in reversed(range(dialogs.count())):
            dialog = dialogs.nth(index)
            try:
                if dialog.is_visible(timeout=min(timeout_ms, 500)):
                    body = dialog.inner_text(timeout=timeout_ms)
                    if body.strip():
                        return body
            except Exception:
                continue
    except Exception:
        pass
    try:
        return page.locator("body").inner_text(timeout=timeout_ms)
    except Exception:
        return ""


def page_url_matches_channel_id(page, target_channel_id: str) -> bool:
    expected_channel_id = target_channel_id.strip().lower()
    if not expected_channel_id:
        return False
    try:
        return studio_channel_id_from_url(page.url).strip().lower() == expected_channel_id
    except Exception:
        return False


def studio_active_channel_id(page) -> str:
    try:
        return str(
            page.evaluate(
                """
                () => String(
                  window.ytcfg?.get?.('CHANNEL_ID')
                  || window.ytcfg?.data_?.CHANNEL_ID
                  || window.ytcfg?.d?.CHANNEL_ID
                  || window.yt?.config_?.CHANNEL_ID
                  || ''
                )
                """
            )
            or ""
        ).strip()
    except Exception:
        return ""


def page_matches_allowed_identity(page, target_channel: str, target_email: str, target_channel_id: str = "") -> bool:
    active_channel_id = studio_active_channel_id(page)
    if active_channel_id and target_channel_id:
        return active_channel_id == target_channel_id.strip()
    expected_channel = normalize_channel_text(target_channel)
    expected_email = normalize_channel_text(target_email)
    expected_channel_id = normalize_channel_text(target_channel_id)
    if not expected_channel and not expected_email and not expected_channel_id:
        return True
    if expected_channel_id:
        return False
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

    active_channel_id = studio_active_channel_id(page)
    if active_channel_id and target_channel_id:
        if active_channel_id == target_channel_id.strip():
            log(f"Channel aktif YouTube Studio terverifikasi: {target_channel_id}.")
            return
        raise UploadError(
            f"Sesi YouTube/Chromium aktif di channel '{active_channel_id}', bukan channel target "
            f"'{target_channel_id}'. Upload dibatalkan agar tidak salah akun."
        )

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
    if target_email and not target_channel_id and google_account_matches_target(page, target_email):
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
    normalized_label = label.strip().casefold()
    field_kind = "description" if normalized_label in {"description", "deskripsi"} else "title"
    pattern_list = list(patterns)
    script = """
    ({ value, patterns, rejectPatterns, fieldKind }) => {
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
        for (let current = element; current; current = current.parentElement) {
          const style = window.getComputedStyle(current);
          if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
          }
        }
        return true;
      };
      const activeDialogs = [];
      for (const root of roots) {
        const dialogs = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-uploads-dialog')) : [];
        for (const dialog of dialogs) {
          const surface = dialog.querySelector?.('tp-yt-paper-dialog#dialog') || dialog;
          if (isVisible(surface)) activeDialogs.push(dialog);
        }
      }
      const fieldId = fieldKind === 'description' ? 'description-textarea' : 'title-textarea';
      for (const dialog of activeDialogs.reverse()) {
        const exact = dialog.querySelector?.(
          `ytcp-social-suggestions-textbox#${fieldId} #textbox[contenteditable="true"]`
        );
        if (!exact || !isVisible(exact)) continue;
        exact.scrollIntoView?.({ block: 'center', inline: 'nearest' });
        exact.click();
        exact.focus();
        return true;
      }
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
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if page.evaluate(
                script,
                {
                    "value": value,
                    "patterns": pattern_list,
                    "rejectPatterns": list(reject_patterns),
                    "fieldKind": field_kind,
                },
            ):
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                # Insert the whole payload as text. Typing description
                # character-by-character lets Studio's @mention popup consume
                # following Enter/newline keystrokes and replace unrelated
                # lines with a mention chip.
                page.keyboard.insert_text(value)
                page.keyboard.press("Tab")
                if upload_text_field_contains(
                    page,
                    expected,
                    pattern_list,
                    reject_patterns=reject_patterns,
                    timeout_ms=3000,
                    field_kind=field_kind,
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
    field_kind: str | None = None,
) -> bool:
    pattern_list = list(patterns)
    script = """
    ({ expected, patterns, rejectPatterns, fieldKind }) => {
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
      const normalizeText = (value) => String(value ?? '')
        .normalize('NFKC')
        .replace(/[\\u200B-\\u200D\\u2066-\\u2069\\uFE00-\\uFE0F\\uFEFF]/g, '')
        .replace(/\\u00A0/g, ' ')
        .replace(/\\s+/g, ' ')
        .trim()
        .toLocaleLowerCase();
      const expectedText = normalizeText(expected);
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        for (let current = element; current; current = current.parentElement) {
          const style = window.getComputedStyle(current);
          if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
          }
        }
        return true;
      };
      if (fieldKind === 'title' || fieldKind === 'description') {
        const fieldId = fieldKind === 'description' ? 'description-textarea' : 'title-textarea';
        for (const root of roots) {
          const dialogs = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-uploads-dialog')) : [];
          for (const dialog of dialogs.reverse()) {
            const surface = dialog.querySelector?.('tp-yt-paper-dialog#dialog') || dialog;
            if (!isVisible(surface)) continue;
            const exact = dialog.querySelector?.(
              `ytcp-social-suggestions-textbox#${fieldId} #textbox[contenteditable="true"]`
            );
            if (!exact || !isVisible(exact)) continue;
            return normalizeText(textOf(exact)) === expectedText;
          }
        }
        return false;
      }
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
          if (!text || normalizeText(text) !== expectedText) continue;
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
                {
                    "expected": expected,
                    "patterns": pattern_list,
                    "rejectPatterns": list(reject_patterns),
                    "fieldKind": field_kind,
                },
            ):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def ensure_logged_in(page) -> None:
    ensure_supported_studio_browser(page)
    ensure_studio_page_healthy(page)
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


def studio_app_load_error(page, page_text: str | None = None) -> str:
    if page_text is None:
        try:
            page_text = normalize_channel_text(page.locator("body").inner_text(timeout=3000))
        except Exception:
            page_text = ""
    messages = (
        ("maafadayangtidakberes", "Maaf, ada yang tidak beres"),
        ("sorrysomethingwentwrong", "Sorry, something went wrong"),
    )
    for marker, message in messages:
        if marker in page_text:
            return message
    try:
        error_section = page.locator("ytcp-error-section").first
        if error_section.count() and error_section.is_visible(timeout=500):
            return "YouTube Studio app-load error"
    except Exception:
        pass
    return ""


def ensure_studio_page_healthy(page, page_text: str | None = None) -> None:
    app_error = studio_app_load_error(page, page_text)
    if not app_error:
        return
    save_debug_artifacts(page, "youtube-studio-app-load-error")
    raise UploadError(
        f"YouTube Studio gagal memuat aplikasi ({app_error}). "
        "Session atau channel aktif perlu disegarkan lewat Login Sekali."
    )


def _url_with_approve_param(url: str) -> str:
    """Inject ``approve_browser_access=true`` into a Studio URL so that
    YouTube does not re-show the unsupported-browser interstitial when
    navigating back after initial approval."""
    if not url or "approve_browser_access=true" in url.lower():
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}approve_browser_access=true"


def ensure_supported_studio_browser(page) -> None:
    unsupported_patterns = (
        "sempurnakanpengalamananda",
        "browseryangtidakdidukung",
        "versibrowserlama",
        "unsupportedbrowser",
        "updateyourbrowser",
    )
    page_text = normalized_page_text(page)
    if not any(pattern in page_text for pattern in unsupported_patterns):
        return

    current_url = str(getattr(page, "url", ""))
    if "approve_browser_access=true" not in current_url.lower():
        try:
            approval_url = str(
                page.evaluate(
                    """
                    () => document.querySelector('a[href*="approve_browser_access=true"]')?.href || ''
                    """
                )
                or ""
            ).strip()
        except Exception:
            approval_url = ""
        if not approval_url.startswith("https://studio.youtube.com/"):
            approval_url = "https://studio.youtube.com/upload?approve_browser_access=true"
        approval_completed = False
        try:
            log("YouTube meminta konfirmasi kompatibilitas browser; melanjutkan lewat akses resmi Studio.")
            page.goto(approval_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            page_text = normalized_page_text(page)
            if not any(pattern in page_text for pattern in unsupported_patterns):
                ensure_studio_page_healthy(page)
                approval_completed = True
                if current_url and current_url != approval_url:
                    # Navigate back with approve_browser_access=true so
                    # YouTube does not re-show the unsupported browser page.
                    return_url = _url_with_approve_param(current_url)
                    page.goto(return_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    page_text = normalized_page_text(page)
                    if any(pattern in page_text for pattern in unsupported_patterns):
                        # Retry: navigate directly to approval_url one more
                        # time, then skip returning to the original page — the
                        # caller (goto_studio / goto_upload_page) will handle
                        # the correct destination afterwards.
                        log(
                            "Halaman channel masih menolak browser; "
                            "retry langsung ke halaman approval."
                        )
                        page.goto(approval_url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                        page_text = normalized_page_text(page)
                        if any(pattern in page_text for pattern in unsupported_patterns):
                            save_debug_artifacts(page, "youtube-browser-unsupported-retry")
                            raise UploadError(
                                "YouTube Studio kembali menolak browser setelah halaman channel dipulihkan. "
                                "Coba update Playwright/backend atau Login Sekali ulang untuk menyegarkan session."
                            )
                        ensure_studio_page_healthy(page)
                    else:
                        ensure_studio_page_healthy(page)
                log("Konfirmasi akses browser YouTube Studio berhasil.")
                return
        except UploadError:
            raise
        except Exception as exc:
            log(f"Konfirmasi akses browser YouTube Studio gagal: {exc}")
            detail = str(exc).strip() or "navigasi Studio berhenti tanpa detail"
            raise UploadError(
                (
                    "YouTube Studio gagal memulihkan halaman channel setelah konfirmasi akses browser. "
                    if approval_completed
                    else "YouTube Studio gagal membuka halaman konfirmasi akses browser. "
                )
                + f"Detail: {detail}"
            ) from exc

    save_debug_artifacts(page, "youtube-browser-unsupported")
    raise UploadError(
        "YouTube Studio tetap menolak browser otomatis setelah konfirmasi akses resmi. "
        "Update image Playwright/backend, lalu Login Sekali untuk menyegarkan session."
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
            ensure_studio_page_healthy(page)
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
                ensure_studio_page_healthy(page)
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
                last_error = (
                    studio_app_load_error(page)
                    or f"URL {page.url}: permukaan upload dan input file tidak muncul."
                )
            except UploadError:
                raise
            except Exception as exc:
                last_error = str(exc)
                break
    save_debug_artifacts(page, "upload-page-input-not-found")
    raise UploadError(
        "Halaman upload YouTube Studio tidak bisa dibuka atau input file tidak ditemukan. "
        f"Detail: {last_error or 'Studio tidak menampilkan permukaan upload.'}"
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


def close_upload_tab(page, *, force: bool = False) -> None:
    if not force and not env_bool("YOUTUBE_CLOSE_UPLOAD_TAB", True):
        log("Tab upload YouTube dibiarkan terbuka agar tidak memicu prompt reload/leave.")
        return
    try:
        if not page.is_closed():
            page.close()
            log("Tab upload YouTube ditutup.")
    except Exception:
        log("Tab upload YouTube tidak dapat ditutup otomatis.")


def mark_fendy_clipper_upload_tab(page) -> None:
    try:
        page.evaluate(f"window.name = {json.dumps(FENDY_CLIPPER_UPLOAD_PAGE_NAME)}")
    except Exception:
        pass


def is_fendy_clipper_upload_tab(page) -> bool:
    try:
        return page.evaluate("window.name") == FENDY_CLIPPER_UPLOAD_PAGE_NAME
    except Exception:
        return False


def close_idle_fendy_clipper_upload_tabs(pages: Iterable) -> int:
    closed = 0
    for page in pages:
        if not is_fendy_clipper_upload_tab(page):
            continue
        try:
            if not page.is_closed():
                page.close()
                closed += 1
        except Exception:
            continue
    if closed:
        log(f"{closed} tab upload Fendy Clipper yang idle ditutup.")
    return closed


def close_duplicate_target_studio_tabs(pages: Iterable, keep_page, target_channel_id: str) -> int:
    """Close duplicate target-channel Studio tabs while preserving one primary tab."""
    closed = 0
    for page in pages:
        if page is keep_page:
            continue
        try:
            url = page.url.lower()
        except Exception:
            continue
        if "studio.youtube.com" not in url:
            continue
        if target_channel_id and not page_url_matches_channel_id(page, target_channel_id):
            continue
        try:
            if not page.is_closed():
                page.close()
                closed += 1
        except Exception:
            continue
    if closed:
        log(f"{closed} tab YouTube Studio target yang duplikat/idle ditutup.")
    return closed


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
        resolve_google_account_chooser(page, target_email, studio_url=studio_url)
        ensure_logged_in(page)
        ensure_target_identity(page, target_channel, target_email, target_channel_id)
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
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        if (element.getAttribute?.('aria-hidden') === 'true') return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(element);
        return Boolean(style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0');
      };
      let hiddenStep = '';
      for (const root of roots) {
        const dialogs = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-uploads-dialog')) : [];
        for (const dialog of dialogs) {
          const step = String(dialog.getAttribute?.('workflow-step') || '').toUpperCase();
          if (!step) continue;
          if (!hiddenStep) hiddenStep = step;
          const surface = dialog.querySelector?.('tp-yt-paper-dialog#dialog, [role="dialog"]') || dialog;
          if (isVisible(surface) || isVisible(dialog)) return step;
        }
      }
      return hiddenStep;
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
        if last_step in expected or any(
            upload_workflow_step_is_at_or_after(last_step, target)
            for target in expected
        ):
            log(f"Tab upload aktif: {last_step}.")
            return last_step
        time.sleep(0.4)
    save_debug_artifacts(page, "upload-step-not-changed")
    raise UploadError(
        "Tab upload belum berpindah sesuai alur. "
        f"Target: {', '.join(sorted(expected))}; terakhir: {last_step or 'tidak terbaca'}."
    )


UPLOAD_WORKFLOW_STEP_ORDER = {
    "DETAILS": 1,
    "VIDEO_ELEMENTS": 2,
    "CHECKS": 3,
    "REVIEW": 4,
}


def upload_workflow_step_is_at_or_after(current: str, expected: str) -> bool:
    current_order = UPLOAD_WORKFLOW_STEP_ORDER.get((current or "").upper(), 0)
    expected_order = UPLOAD_WORKFLOW_STEP_ORDER.get((expected or "").upper(), 0)
    return bool(current_order and expected_order and current_order >= expected_order)


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
        body = active_upload_dialog_text(page, timeout_ms=2000)
        last_body = re.sub(r"\s+", " ", body).strip()[:500]
        if any(re.search(pattern, body, re.I) for pattern in patterns):
            log("Tab Visibilitas siap.")
            return
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
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return Boolean(
          rect.width > 0 && rect.height > 0 && style &&
          style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
        );
      };
      const dialogs = Array.from(document.querySelectorAll('ytcp-uploads-dialog'));
      const dialog = dialogs.find((candidate) => {
        const surface = candidate.querySelector('tp-yt-paper-dialog#dialog, [role="dialog"]') || candidate;
        return isVisible(surface) || isVisible(candidate);
      });
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


def wait_for_review_checks_safe_before_publish(
    page,
    timeout_ms: int = 300000,
    *,
    visibility: str = "public",
    content_type: str = "auto",
    media_duration_seconds: float = 0.0,
    previously_verified_non_blocking_claim: bool = False,
) -> None:
    action_label = "Publikasikan" if visibility == "public" else "Simpan"
    log(
        "Memastikan ulang status hak cipta tetap aman dan tombol "
        f"{action_label} siap..."
    )
    deadline = time.monotonic() + timeout_ms / 1000
    last_body = ""
    consecutive_safe_observations = 0
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        body = active_upload_dialog_text(page, timeout_ms=3000)
        last_body = re.sub(r"\s+", " ", body).strip()[:700]
        if copyright_issue_blocks_upload(
            body,
            content_type=content_type,
            media_duration_seconds=media_duration_seconds,
            previously_verified_non_blocking_claim=previously_verified_non_blocking_claim,
        ):
            save_debug_artifacts(page, "copyright-claim-before-publish")
            raise CopyrightClaimUploadError(
                "Klaim Content ID/copyright muncul pada review akhir. "
                "Aksi Simpan/Publikasikan dibatalkan agar video berklaim tidak masuk channel."
            )
        if (
            get_upload_workflow_step(page) == "REVIEW"
            and visibility_is_selected(page, visibility)
            and final_action_button_is_ready(page, visibility)
        ):
            consecutive_safe_observations += 1
            if consecutive_safe_observations >= 3:
                log(
                    "Tidak ada klaim pada verifikasi akhir; "
                    f"{visibility.title()} tercentang dan tombol {action_label} aktif."
                )
                return
        else:
            consecutive_safe_observations = 0
        time.sleep(1)

    save_debug_artifacts(page, "publish-button-not-ready")
    raise UploadError(
        f"{visibility.title()} atau tombol {action_label} belum siap. "
        f"Cuplikan modal: {last_body}"
    )


def click_final_upload_action(
    page,
    visibility: str,
    timeout_ms: int = 30000,
    *,
    content_type: str = "auto",
    media_duration_seconds: float = 0.0,
    previously_verified_non_blocking_claim: bool = False,
) -> None:
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
    body = active_upload_dialog_text(page, timeout_ms=3000)
    claim_blocks_publication = copyright_issue_blocks_upload(
        body,
        content_type=content_type,
        media_duration_seconds=media_duration_seconds,
        previously_verified_non_blocking_claim=previously_verified_non_blocking_claim,
    )
    if claim_blocks_publication:
        save_debug_artifacts(page, "copyright-claim-at-final-action")
        raise CopyrightClaimUploadError(
            "Klaim Content ID/copyright terdeteksi tepat sebelum aksi final. "
            "Upload dibatalkan agar channel tetap aman."
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


def validate_thumbnail_file(
    thumbnail_path: Path,
    content_type: str = "long-form",
) -> tuple[int, int]:
    if not thumbnail_path.is_file():
        raise UploadError(f"File thumbnail tidak ditemukan: {thumbnail_path}")
    if thumbnail_path.suffix.casefold() not in {".jpg", ".jpeg", ".png"}:
        raise UploadError("Thumbnail YouTube harus berupa JPG atau PNG.")
    if thumbnail_path.stat().st_size > 2 * 1024 * 1024:
        raise UploadError("Thumbnail YouTube melebihi batas aman 2 MB.")
    try:
        import cv2

        image = cv2.imread(str(thumbnail_path))
    except Exception:
        image = None
    if image is None:
        raise UploadError("Thumbnail YouTube tidak dapat dibaca sebagai gambar.")
    height, width = image.shape[:2]
    normalized_type = (content_type or "long-form").strip().casefold()
    expected_ratio = 9 / 16 if normalized_type == "shorts" else 16 / 9
    minimum_width, minimum_height = (360, 640) if normalized_type == "shorts" else (640, 360)
    if (
        width < minimum_width
        or height < minimum_height
        or abs((width / height) - expected_ratio) > 0.03
    ):
        expected_label = "portrait 9:16" if normalized_type == "shorts" else "landscape 16:9"
        raise UploadError(
            f"Thumbnail {normalized_type} harus {expected_label}; file saat ini {width}x{height}."
        )
    return width, height


def custom_thumbnail_daily_limit_detected(page) -> bool:
    markers = (
        "batasthumbnailkustomhariantercapai",
        "batasharianthumbnailkustomtercapai",
        "dailycustomthumbnaillimitreached",
        "customthumbnaillimitreached",
        "waitupto24hourstocreatenewcustomthumbnails",
        "diperlukanwaktuhingga24jamuntukdapatmembuatthumbnailkustombaru",
    )
    script = r"""
    ({ markers }) => {
      const roots = [];
      const seen = new Set();
      const addRoot = (root) => {
        if (root && !seen.has(root)) {
          seen.add(root);
          roots.push(root);
        }
      };
      addRoot(document);
      for (let index = 0; index < roots.length; index += 1) {
        const root = roots[index];
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
        return Boolean(
          style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
        );
      };
      const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      for (const root of roots) {
        const dialogs = root.querySelectorAll
          ? Array.from(root.querySelectorAll('tp-yt-paper-dialog,[role="dialog"],ytcp-dialog'))
          : [];
        for (const dialog of dialogs) {
          if (!isVisible(dialog)) continue;
          const text = normalize(dialog.innerText || dialog.textContent || '');
          if (markers.some((marker) => text.includes(marker))) return true;
        }
      }
      return false;
    }
    """
    try:
        return bool(page.evaluate(script, {"markers": list(markers)}))
    except Exception:
        page_text = normalized_page_text(page)
        return any(marker in page_text for marker in markers)


def dismiss_custom_thumbnail_daily_limit(page) -> None:
    clicked = click_text(
        page,
        (r"^tutup$", r"^close$", r"^oke$", r"^ok$"),
        timeout_ms=2500,
        optional=True,
    )
    if not clicked:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not custom_thumbnail_daily_limit_detected(page):
            log(
                "Dialog batas harian thumbnail kustom ditutup; "
                "upload dapat dilanjutkan dengan thumbnail otomatis YouTube."
            )
            return
        time.sleep(0.2)
    save_debug_artifacts(page, "thumbnail-daily-limit-dialog-stuck")
    raise UploadError(
        "Dialog batas harian thumbnail kustom tidak berhasil ditutup; upload dihentikan agar alur tidak macet."
    )


def thumbnail_upload_state(page) -> dict[str, object]:
    """Read the custom-thumbnail transfer state without touching the file input."""
    script = r"""
    () => {
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        for (let current = element; current; current = current.parentElement) {
          const style = window.getComputedStyle(current);
          if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
          }
        }
        return true;
      };
      const dialogs = [...document.querySelectorAll('ytcp-uploads-dialog')]
        .filter((dialog) => isVisible(dialog.querySelector('tp-yt-paper-dialog#dialog') || dialog));
      const activeDialog = dialogs[dialogs.length - 1];
      if (!activeDialog) {
        return {found: false, selected: false, uploading: false, error: ''};
      }
      const uploaders = [...activeDialog.querySelectorAll(
        'ytcp-video-thumbnail-editor ytcp-thumbnail-uploader, ytcp-thumbnail-uploader'
      )];
      const uploader = uploaders.find((candidate) => candidate.querySelector(
        'input[type="file"][accept*="image"], input[type="file"][accept*=".jpg"], '
        + 'input[type="file"][accept*=".jpeg"], input[type="file"][accept*=".png"]'
      ));
      if (!uploader) {
        return {found: false, selected: false, uploading: false, error: ''};
      }
      const editor = uploader.closest('ytcp-video-custom-still-editor') || uploader;
      const errorTip = editor.querySelector(
        'ytcp-form-error-tip:not([hidden]), [role="alert"]:not([hidden])'
      );
      const error = errorTip
        ? (errorTip.innerText || errorTip.textContent || '').replace(/\s+/g, ' ').trim()
        : '';
      const preview = uploader.querySelector('.preview, #preview-button');
      return {
        found: true,
        selected: uploader.hasAttribute('selected') && isVisible(preview),
        uploading: uploader.hasAttribute('is-ongoing-transfer'),
        error,
      };
    }
    """
    fallback = {"found": False, "selected": False, "uploading": False, "error": ""}
    for frame in page.frames:
        try:
            result = frame.evaluate(script)
        except Exception:
            continue
        if not isinstance(result, dict) or not result.get("found"):
            continue
        return {
            "found": True,
            "selected": bool(result.get("selected")),
            "uploading": bool(result.get("uploading")),
            "error": str(result.get("error") or "").strip(),
        }
    return fallback


def set_thumbnail(
    page,
    thumbnail_path: Path,
    timeout_ms: int = 45000,
    *,
    content_type: str = "long-form",
    required: bool = True,
) -> bool:
    width, height = validate_thumbnail_file(thumbnail_path, content_type)
    log(f"Mengatur thumbnail otomatis {width}x{height}: {thumbnail_path.name}.")
    probe_timeout_ms = (
        timeout_ms
        if required
        else min(
            timeout_ms,
            max(
                1000,
                int(os.environ.get("YOUTUBE_SHORTS_THUMBNAIL_PROBE_TIMEOUT_SECONDS", "6"))
                * 1000,
            ),
        )
    )
    deadline = time.monotonic() + probe_timeout_ms / 1000
    selectors = (
        'ytcp-uploads-dialog ytcp-video-thumbnail-editor input[type="file"]',
        'ytcp-uploads-dialog ytcp-thumbnail-editor input[type="file"]',
        'ytcp-uploads-dialog ytcp-video-custom-thumbnail-editor input[type="file"]',
        'ytcp-uploads-dialog ytcp-video-metadata-editor input[type="file"][accept*="image"]',
        'ytcp-uploads-dialog input[type="file"][accept*="image"]',
        'ytcp-uploads-dialog input[type="file"][accept*=".jpg"]',
        'ytcp-uploads-dialog input[type="file"][accept*=".jpeg"]',
        'ytcp-uploads-dialog input[type="file"][accept*=".png"]',
    )
    clicked_upload = False
    upload_started = False
    completed_state_polls = 0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if upload_started:
            if custom_thumbnail_daily_limit_detected(page):
                dismiss_custom_thumbnail_daily_limit(page)
                raise ThumbnailDailyLimitUploadError(
                    "Batas harian thumbnail kustom YouTube tercapai; "
                    "YouTube meminta menunggu hingga 24 jam sebelum thumbnail kustom baru."
                )
            state = thumbnail_upload_state(page)
            state_error = str(state["error"])
            if state_error:
                save_debug_artifacts(page, "thumbnail-rejected")
                raise UploadError(f"YouTube menolak file thumbnail otomatis: {state_error}")
            if state["selected"] and not state["uploading"]:
                completed_state_polls += 1
                if completed_state_polls >= 2:
                    log(f"THUMBNAIL_ATTACHED: {thumbnail_path.name} ({width}x{height})")
                    return True
            else:
                completed_state_polls = 0

            page_text = normalized_page_text(page)
            rejection_terms = (
                "filetoobig",
                "filetoolarge",
                "filesterlalubesar",
                "invalidfile",
                "filetidakvalid",
                "cantuploadthumbnail",
                "tidakdapatmenguploadthumbnail",
            )
            if any(term in page_text for term in rejection_terms):
                save_debug_artifacts(page, "thumbnail-rejected")
                raise UploadError("YouTube menolak file thumbnail otomatis.")
            time.sleep(0.5)
            continue

        for selector in selectors:
            for frame in page.frames:
                try:
                    locator = frame.locator(selector).first
                    if locator.count():
                        locator.set_input_files(str(thumbnail_path), timeout=30000)
                        upload_started = True
                        # The capability probe is short for optional Shorts,
                        # but an upload that has started gets the full transfer
                        # window before the workflow continues.
                        deadline = time.monotonic() + timeout_ms / 1000
                        log(
                            f"Transfer thumbnail dimulai satu kali; menunggu konfirmasi YouTube Studio: "
                            f"{thumbnail_path.name}."
                        )
                        break
                except UploadError:
                    raise
                except Exception as exc:
                    last_error = exc
            if upload_started:
                break
        if upload_started:
            time.sleep(0.5)
            continue
        if required and not clicked_upload:
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
    if upload_started:
        if custom_thumbnail_daily_limit_detected(page):
            dismiss_custom_thumbnail_daily_limit(page)
            raise ThumbnailDailyLimitUploadError(
                "Batas harian thumbnail kustom YouTube tercapai; "
                "YouTube meminta menunggu hingga 24 jam sebelum thumbnail kustom baru."
            )
        save_debug_artifacts(page, "thumbnail-upload-timeout")
        raise UploadError(
            "Transfer thumbnail sudah dimulai, tetapi YouTube Studio belum mengonfirmasi selesai; "
            "file tidak dikirim ulang agar proses tidak berkedip atau terus mengulang."
        ) from last_error

    if not required:
        log(
            "THUMBNAIL_SKIPPED: kontrol upload thumbnail tidak tersedia untuk Short ini; "
            "upload video dilanjutkan tanpa mengubah alur lainnya."
        )
        return False

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


def should_upload_custom_thumbnail(video_path: Path, content_type: str = "auto") -> bool:
    """Attempt custom artwork; the live Studio UI decides capability."""
    normalized = (content_type or "auto").strip().casefold()
    if normalized in {"long-form", "shorts"}:
        return True
    return video_path.suffix.casefold() in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


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
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n').toLowerCase();
      const rowSelector =
        'li.row, label.ytcp-checkbox-label, ytcp-playlist-dialog-row, '
        + 'tp-yt-paper-item, [role="listitem"], [role="option"]';

      for (const root of roots) {
        const dialogs = root.querySelectorAll
          ? Array.from(root.querySelectorAll('ytcp-playlist-dialog'))
          : [];
        for (const dialog of dialogs) {
          const surface = dialog.querySelector('tp-yt-paper-dialog[role="dialog"], #dialog') || dialog;
          if (surface.getAttribute?.('aria-hidden') === 'true' || !isVisible(surface)) continue;
          const rows = Array.from(surface.querySelectorAll?.(rowSelector) || []);
          for (const row of rows) {
            if (!isVisible(row)) continue;
            const lines = labelOf(row).split(/\\n+/).map((line) => line.trim()).filter(Boolean);
            if (!lines.includes(target)) continue;
            const label = row.matches?.('label') ? row : row.querySelector?.('label');
            const clickable = label && isVisible(label) ? label : row;
            clickable.scrollIntoView?.({ block: 'center', inline: 'center' });
            clickable.click();
            return true;
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


def playlist_row_locator(page, playlist_name: str):
    """Return the visible Studio playlist row whose label exactly matches the name."""
    target = playlist_name.strip().casefold()
    if not target:
        return None
    try:
        rows = page.locator(
            "ytcp-playlist-dialog li.row, "
            "ytcp-playlist-dialog ytcp-playlist-dialog-row, "
            "ytcp-playlist-dialog tp-yt-paper-item, "
            'ytcp-playlist-dialog [role="listitem"], '
            'ytcp-playlist-dialog [role="option"]'
        )
        for index in range(rows.count()):
            row = rows.nth(index)
            try:
                if not row.is_visible(timeout=300):
                    continue
                labels = row.locator("span.label-text, .checkbox-label, [aria-label], [title]")
                values: list[str] = []
                for label_index in range(labels.count()):
                    label = labels.nth(label_index)
                    label_values: list[str | None] = []
                    try:
                        label_values.append(label.inner_text(timeout=300))
                    except Exception:
                        pass
                    for attribute in ("aria-label", "title"):
                        try:
                            label_values.append(label.get_attribute(attribute))
                        except Exception:
                            pass
                    for value in label_values:
                        if value:
                            values.extend(
                                line.strip().casefold()
                                for line in value.splitlines()
                                if line.strip()
                            )
                if not values:
                    values = [
                        line.strip().casefold()
                        for line in row.inner_text(timeout=500).splitlines()
                        if line.strip()
                    ]
                if target in values:
                    return row
            except Exception:
                continue
    except Exception:
        return None
    return None


def playlist_row_is_selected(row) -> bool:
    """Read both the Lit control and hidden native input used by Studio."""
    try:
        controls = row.locator(
            '[role="checkbox"], input[type="checkbox"], ytcp-checkbox-lit, tp-yt-paper-checkbox'
        )
        for index in range(controls.count()):
            control = controls.nth(index)
            try:
                aria_checked = (control.get_attribute("aria-checked") or "").strip().lower()
                raw_checked_attribute = control.get_attribute("checked")
                checked_attribute = (raw_checked_attribute or "").strip().lower()
                if aria_checked == "true" or (
                    raw_checked_attribute is not None
                    and checked_attribute in {"", "true", "checked"}
                ):
                    return True
                try:
                    if control.is_checked(timeout=300):
                        return True
                except Exception:
                    pass
            except Exception:
                continue
    except Exception:
        return False
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
      const checkboxSelector =
        'input[type="checkbox"], [role="checkbox"], ytcp-checkbox-lit, tp-yt-paper-checkbox, #checkbox';
      const rowSelector =
        'li.row, label.ytcp-checkbox-label, ytcp-playlist-dialog-row, '
        + 'tp-yt-paper-item, [role="listitem"], [role="option"]';
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n').toLowerCase();
      for (const root of roots) {
        const dialogs = root.querySelectorAll
          ? Array.from(root.querySelectorAll('ytcp-playlist-dialog'))
          : [];
        for (const dialog of dialogs) {
          const surface = dialog.querySelector('tp-yt-paper-dialog[role="dialog"], #dialog') || dialog;
          if (surface.getAttribute?.('aria-hidden') === 'true') continue;
          const rows = Array.from(surface.querySelectorAll?.(rowSelector) || []);
          for (const row of rows) {
            const lines = labelOf(row).split(/\\n+/).map((line) => line.trim()).filter(Boolean);
            if (!lines.includes(target)) continue;
            const checks = Array.from(row.querySelectorAll?.(checkboxSelector) || []);
            if (row.matches?.(checkboxSelector)) checks.unshift(row);
            if (checks.some(isChecked)) return true;
          }
        }
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        row = playlist_row_locator(page, playlist_name)
        if row is not None and playlist_row_is_selected(row):
            return True
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
    deadline = time.monotonic() + timeout_ms / 1000

    def wait_until_selected(row, seconds: float = 1.25) -> bool:
        state_deadline = min(deadline, time.monotonic() + seconds)
        while time.monotonic() < state_deadline:
            if playlist_row_is_selected(row):
                log(f"Checkbox playlist tercentang dan terverifikasi: {playlist_name}.")
                return True
            time.sleep(0.12)
        return False

    # Studio currently renders a focusable div[role=checkbox] plus a hidden
    # native input inside a label. Depending on the active Studio experiment,
    # either the Lit host, keyboard handler, or native input owns the state.
    # Try one interaction at a time and verify aria-checked/checked before the
    # next method so a second event can never toggle a successful choice off.
    while time.monotonic() < deadline:
        row = playlist_row_locator(page, playlist_name)
        if row is None:
            time.sleep(0.2)
            continue
        if playlist_row_is_selected(row):
            return True

        # Keyboard activation avoids the label/default-action double-toggle
        # seen in some ytcp-checkbox-lit revisions.
        try:
            role_checkbox = row.locator('div#checkbox[role="checkbox"], [role="checkbox"]').first
            if role_checkbox.count() and role_checkbox.is_visible(timeout=300):
                role_checkbox.scroll_into_view_if_needed(timeout=1000)
                role_checkbox.focus(timeout=1000)
                role_checkbox.press("Space", timeout=1500)
                if wait_until_selected(row):
                    return True
        except Exception:
            pass

        # Clicking the label text lets the browser activate the associated
        # hidden input once, without also targeting the Lit control itself.
        try:
            label_text = row.locator("span.checkbox-label, span.label-text").first
            if label_text.count() and label_text.is_visible(timeout=300):
                label_text.scroll_into_view_if_needed(timeout=1000)
                label_text.click(timeout=2000)
                if wait_until_selected(row):
                    return True
        except Exception:
            pass

        # Playwright's checked-state primitive is the most reliable fallback
        # when Studio delegates state to the hidden native input.
        try:
            native_input = row.locator('input[type="checkbox"]').first
            if native_input.count():
                native_input.set_checked(True, force=True, timeout=2000)
                if wait_until_selected(row):
                    return True
        except Exception:
            pass

        # Finish with trusted pointer input on each visible owner. This also
        # covers older Studio layouts without the keyboard/native-input path.
        for selector in (
            'div#checkbox[role="checkbox"]',
            "ytcp-checkbox-lit",
            "tp-yt-paper-checkbox",
            "label.ytcp-checkbox-label",
        ):
            try:
                control = row.locator(selector).first
                if not control.count() or not control.is_visible(timeout=300):
                    continue
                control.scroll_into_view_if_needed(timeout=1000)
                control.click(timeout=min(2500, max(500, int((deadline - time.monotonic()) * 1000))))
                if wait_until_selected(row):
                    return True
            except Exception:
                continue
        break

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
      const labelOf = (element) => [
        element.innerText,
        element.textContent,
        element.getAttribute?.('aria-label'),
        element.getAttribute?.('title'),
      ].filter(Boolean).join('\\n').toLowerCase();
      const checkboxSelectors = 'input[type="checkbox"], [role="checkbox"], ytcp-checkbox-lit, tp-yt-paper-checkbox, #checkbox';
      const rowSelector =
        'li.row, label.ytcp-checkbox-label, ytcp-playlist-dialog-row, '
        + 'tp-yt-paper-item, [role="listitem"], [role="option"]';
      const clickElement = (element) => {
        element.scrollIntoView?.({ block: 'center', inline: 'center' });
        element.click();
        return true;
      };

      for (const root of roots) {
        const dialogs = root.querySelectorAll
          ? Array.from(root.querySelectorAll('ytcp-playlist-dialog'))
          : [];
        for (const dialog of dialogs) {
          const surface = dialog.querySelector('tp-yt-paper-dialog[role="dialog"], #dialog') || dialog;
          if (surface.getAttribute?.('aria-hidden') === 'true' || !isVisible(surface)) continue;
          const rows = Array.from(surface.querySelectorAll?.(rowSelector) || []);
          for (const row of rows) {
            if (!isVisible(row)) continue;
            const lines = labelOf(row).split(/\\n+/).map((line) => line.trim()).filter(Boolean);
            if (!lines.includes(target)) continue;

            const checks = Array.from(row.querySelectorAll?.(checkboxSelectors) || []);
            if (row.matches?.(checkboxSelectors)) checks.unshift(row);
            if (checks.some(isChecked)) return true;

            // YouTube's current checkbox is a ytcp-checkbox-lit host containing
            // an interactive div[role=checkbox] plus a hidden input. Clicking
            // the host or text label no longer consistently changes its state.
            // Prefer the native input. HTMLElement.click() performs its real
            // checkbox default action and emits input/change exactly once.
            const nativeInput = checks.find((check) =>
              check.matches?.('input[type="checkbox"]') && !check.disabled
            );
            if (nativeInput) return clickElement(nativeInput);
            const interactive = checks.find((check) =>
              check.matches?.('[role="checkbox"]')
              && check.getAttribute?.('aria-disabled') !== 'true'
              && isVisible(check)
            );
            if (interactive) {
              interactive.focus?.();
              interactive.dispatchEvent(new KeyboardEvent('keydown', {
                key: ' ', code: 'Space', bubbles: true, composed: true,
              }));
              interactive.dispatchEvent(new KeyboardEvent('keyup', {
                key: ' ', code: 'Space', bubbles: true, composed: true,
              }));
              return true;
            }
            const host = checks.find((check) =>
              check.matches?.('ytcp-checkbox-lit, tp-yt-paper-checkbox') && isVisible(check)
            );
            if (host) return clickElement(host);
            const label = row.matches?.('label') ? row : row.querySelector?.('label');
            if (label && isVisible(label)) return clickElement(label);
          }
        }
      }
      return false;
    }
    """
    # Compatibility fallback for older Studio variants where locator-based
    # controls are not exposed in the light DOM.
    deadline = max(deadline, time.monotonic() + min(2.0, timeout_ms / 1000))
    while time.monotonic() < deadline:
        try:
            if page.evaluate(script, {"target": target}):
                row = playlist_row_locator(page, playlist_name)
                if row is not None and wait_until_selected(row, seconds=0.8):
                    return True
                if playlist_is_selected(
                    page,
                    playlist_name,
                    timeout_ms=min(800, max(100, timeout_ms)),
                ):
                    log(f"Checkbox playlist tercentang dan terverifikasi: {playlist_name}.")
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
                log(f"Search playlist: {playlist_name}.")
                time.sleep(1.2)
                return True
        except Exception:
            continue
    log("Kolom search playlist tidak ditemukan; memilih dari daftar yang tampil.")
    return False


def click_playlist_done(page, timeout_ms: int = 8000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    # Do not use a global role/text lookup here. The upload modal and thumbnail
    # editor can expose other buttons named "Selesai" at the same time. Studio's
    # playlist dialog has a stable, dedicated .done-button owner.
    while time.monotonic() < deadline:
        try:
            buttons = page.locator(
                "ytcp-playlist-dialog ytcp-button.done-button button, "
                "ytcp-playlist-dialog .done-button button, "
                "ytcp-playlist-dialog ytcp-button.done-button"
            )
            for index in range(buttons.count()):
                button = buttons.nth(index)
                if not button.is_visible(timeout=300):
                    continue
                if (button.get_attribute("aria-disabled") or "").lower() == "true":
                    continue
                button.scroll_into_view_if_needed(timeout=1000)
                button.click(timeout=2000)
                if not playlist_dialog_open(page, timeout_ms=1800):
                    log("Tombol Selesai milik dialog playlist diklik.")
                    return True
        except Exception:
            pass
        try:
            clicked = page.evaluate(
                """
                () => {
                  const dialogs = Array.from(document.querySelectorAll('ytcp-playlist-dialog'));
                  for (const dialog of dialogs) {
                    const surface = dialog.querySelector('tp-yt-paper-dialog#dialog');
                    if (!surface || surface.getAttribute('aria-hidden') === 'true') continue;
                    const button = dialog.querySelector(
                      'ytcp-button.done-button button, .done-button button, ytcp-button.done-button'
                    );
                    if (!button || button.getAttribute?.('aria-disabled') === 'true') continue;
                    button.scrollIntoView?.({ block: 'center', inline: 'center' });
                    button.click();
                    return true;
                  }
                  return false;
                }
                """
            )
            if clicked and not playlist_dialog_open(page, timeout_ms=1800):
                log("Tombol Selesai milik dialog playlist diklik.")
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


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
      for (const root of roots) {
        const dialogs = root.querySelectorAll ? Array.from(root.querySelectorAll('ytcp-playlist-dialog')) : [];
        for (const dialog of dialogs) {
          const surface = dialog.querySelector('tp-yt-paper-dialog[role="dialog"], #dialog') || dialog;
          if (surface.getAttribute?.('aria-hidden') !== 'true' && isVisible(surface)) return true;
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

    attempts = max(1, min(5, int(os.environ.get("YOUTUBE_PLAYLIST_SELECT_ATTEMPTS", "3"))))
    escaped = re.escape(playlist_name)
    last_error = ""
    for attempt in range(1, attempts + 1):
        dismiss_reload_prompt(page)
        log(f"Memilih playlist: {playlist_name} (verifikasi {attempt}/{attempts}).")

        # Always inspect the dialog. A collapsed summary can be stale when a
        # Studio tab is reused by consecutive jobs, so it is not sufficient as
        # proof that the requested checkbox is selected for this upload.
        opened = playlist_dialog_open(page, timeout_ms=800)
        if not opened:
            opened = open_playlist_dropdown(page, timeout_ms=8000)
        if not opened:
            last_error = "Dropdown playlist tidak terbuka."
            continue

        time.sleep(0.8)
        search_playlist(page, playlist_name)
        selected = playlist_is_selected(page, playlist_name, timeout_ms=1800)
        if not selected:
            click_playlist_checkbox(page, playlist_name, timeout_ms=4000)
            selected = playlist_is_selected(page, playlist_name, timeout_ms=2200)
        if not selected:
            try:
                checkbox = page.get_by_role("checkbox", name=re.compile(escaped, re.I)).first
                if checkbox.count():
                    try:
                        should_click = not checkbox.is_checked(timeout=1000)
                    except Exception:
                        should_click = True
                    if should_click:
                        checkbox.click(timeout=3000)
                    selected = playlist_is_selected(page, playlist_name, timeout_ms=2200)
            except Exception:
                pass
        if not selected and click_playlist_named(page, playlist_name, timeout_ms=3000):
            time.sleep(0.5)
            selected = playlist_is_selected(page, playlist_name, timeout_ms=2200)
        if not selected:
            last_error = f"Playlist '{playlist_name}' belum berhasil dicentang."
            continue

        # Let the Lit checkbox propagate its selected-playlist model before
        # confirming the dialog. A single immediate aria-checked read can race
        # the model update even though the checkmark is already painted.
        time.sleep(0.6)
        if not playlist_is_selected(page, playlist_name, timeout_ms=1400):
            last_error = f"Playlist '{playlist_name}' tidak stabil setelah dicentang."
            continue

        if not click_playlist_done(page, timeout_ms=8000):
            last_error = "Tombol Selesai playlist tidak ditemukan setelah playlist dicentang."
            continue
        time.sleep(0.5)
        dialog_closed = not playlist_dialog_open(page, timeout_ms=1000)
        summary_confirmed = playlist_dropdown_value_matches(page, playlist_name, timeout_ms=3500)
        if dialog_closed and summary_confirmed:
            log(f"PLAYLIST_CONFIRMED: {playlist_name}")
            return
        # Some Studio variants keep the collapsed trigger text as "Pilih".
        # Reopen once and verify the actual checkbox persisted; this is stronger
        # evidence than the trigger summary and leaves no silent false success.
        if dialog_closed and open_playlist_dropdown(page, timeout_ms=5000):
            time.sleep(0.5)
            search_playlist(page, playlist_name)
            persisted = playlist_is_selected(page, playlist_name, timeout_ms=2200)
            if persisted and click_playlist_done(page, timeout_ms=5000):
                log(f"PLAYLIST_CONFIRMED_BY_REOPEN: {playlist_name}")
                return
            if playlist_dialog_open(page, timeout_ms=500):
                click_playlist_done(page, timeout_ms=1500)
        last_error = (
            f"Playlist '{playlist_name}' belum terkonfirmasi pada ringkasan detail video "
            "setelah dialog ditutup."
        )

    save_debug_artifacts(page, "playlist-verification-failed")
    raise UploadError(f"{last_error} Upload tidak dilanjutkan agar playlist tidak terlewati.")


def click_next_upload_step(page, timeout_ms: int = 20000, expected_step=None) -> None:
    direct_script = """
    () => {
      const isVisible = (element) => {
        if (!element || !element.getBoundingClientRect) return false;
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return Boolean(
          rect.width > 0 && rect.height > 0 && style &&
          style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0'
        );
      };
      const dialogs = Array.from(document.querySelectorAll('ytcp-uploads-dialog'));
      const dialog = dialogs.find((candidate) => {
        const surface = candidate.querySelector('tp-yt-paper-dialog#dialog, [role="dialog"]') || candidate;
        return isVisible(surface) || isVisible(candidate);
      });
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
    next_progress_log_at = time.monotonic() + 30
    while time.monotonic() < deadline:
        dismiss_reload_prompt(page, timeout_ms=300)
        current_step = get_upload_workflow_step(page)
        if expected_step and upload_workflow_step_is_at_or_after(current_step, expected_step):
            log(f"Tab upload sudah aktif: {current_step}.")
            return
        try:
            # Playwright's locator click emits a trusted pointer action. This is
            # more reliable than HTMLElement.click() on the long-form wizard,
            # where Studio can ignore synthetic clicks while processing video.
            for selector in (
                "ytcp-uploads-dialog #next-button button",
                "ytcp-uploads-dialog ytcp-button#next-button button",
                "ytcp-uploads-dialog #next-button",
            ):
                try:
                    locator = page.locator(selector).first
                    if not locator.count() or not locator.is_visible(timeout=300):
                        continue
                    if locator.get_attribute("aria-disabled") == "true" or locator.is_disabled(timeout=300):
                        last_reason = "next-disabled"
                        continue
                    locator.scroll_into_view_if_needed(timeout=1500)
                    locator.click(timeout=3000)
                    if expected_step:
                        try:
                            wait_for_upload_workflow_step(
                                page,
                                [expected_step],
                                timeout_ms=min(timeout_ms, 15000),
                            )
                            return
                        except UploadError as exc:
                            last_reason = str(exc)
                            time.sleep(0.8)
                            break
                    time.sleep(0.8)
                    return
                except Exception:
                    continue

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
        if time.monotonic() >= next_progress_log_at:
            log(
                "Tombol Berikutnya masih disabled; menunggu upload/pemeriksaan awal "
                "YouTube selesai sebelum berpindah tahap."
            )
            next_progress_log_at = time.monotonic() + 30
        time.sleep(0.4)
    save_debug_artifacts(page, "next-upload-button-not-found")
    suffix = f" Terakhir: {last_reason}" if last_reason else ""
    raise UploadError(f"Tombol Berikutnya/Next modal upload tidak ditemukan atau masih disabled.{suffix}")


def next_upload_step_timeout_ms(total_timeout_ms: int, content_type: str = "auto") -> int:
    is_long_form = (content_type or "auto").strip().casefold() == "long-form"
    setting_name = (
        "YOUTUBE_LONG_FORM_NEXT_STEP_TIMEOUT_SECONDS"
        if is_long_form
        else "YOUTUBE_NEXT_STEP_TIMEOUT_SECONDS"
    )
    default_seconds = 3600 if is_long_form else 900
    try:
        configured_seconds = int(os.environ.get(setting_name, str(default_seconds)))
    except ValueError:
        configured_seconds = default_seconds
    return min(total_timeout_ms, max(60_000, configured_seconds * 1000))


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


def subtitle_editor_open(page) -> bool:
    script = """
    () => {
      const modal = document.querySelector('ytve-captions-editor-modal');
      if (!modal) return false;
      const dialog = modal.querySelector('tp-yt-paper-dialog[role="dialog"], ytcp-dialog');
      if (!dialog || dialog.getAttribute?.('aria-hidden') === 'true') return false;
      const rect = dialog.getBoundingClientRect?.();
      if (!rect || rect.width <= 0 || rect.height <= 0) return false;
      const style = window.getComputedStyle(dialog);
      return Boolean(style && style.display !== 'none' && style.visibility !== 'hidden');
    }
    """
    try:
        return bool(page.evaluate(script))
    except Exception:
        return False


def wait_for_subtitle_editor_closed(page, timeout_ms: int = 8000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if not subtitle_editor_open(page):
            return True
        time.sleep(0.2)
    return not subtitle_editor_open(page)


def click_subtitle_done(page, timeout_ms: int = 12000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    clicked = False
    # The captions editor has several header actions. Only #publish-button is
    # the white "Selesai" button shown at the top-right; global text matching
    # can hit the upload wizard or playlist dialog instead.
    selectors = (
        "ytve-captions-editor-modal ytcp-button#publish-button button",
        "ytve-captions-editor-modal #publish-button button",
        "ytve-captions-editor-modal ytcp-button#publish-button",
    )
    while time.monotonic() < deadline and not clicked:
        for selector in selectors:
            try:
                button = page.locator(selector).first
                if not button.count() or not button.is_visible(timeout=400):
                    continue
                if (button.get_attribute("aria-disabled") or "").lower() == "true":
                    continue
                button.scroll_into_view_if_needed(timeout=1000)
                button.click(timeout=2500)
                clicked = True
                break
            except Exception:
                continue
        if clicked:
            break
        try:
            clicked = bool(
                page.evaluate(
                    """
                    () => {
                      const modal = document.querySelector('ytve-captions-editor-modal');
                      if (!modal) return false;
                      const button = modal.querySelector(
                        'ytcp-button#publish-button button, #publish-button button, ytcp-button#publish-button'
                      );
                      if (!button || button.getAttribute?.('aria-disabled') === 'true') return false;
                      button.scrollIntoView?.({ block: 'center', inline: 'center' });
                      button.click();
                      return true;
                    }
                    """
                )
            )
        except Exception:
            clicked = False
        if not clicked:
            time.sleep(0.25)

    if not clicked:
        return False
    remaining_ms = max(500, int((deadline - time.monotonic()) * 1000))
    if not wait_for_subtitle_editor_closed(page, timeout_ms=remaining_ms):
        log("Tombol Selesai subtitle diklik, tetapi editor belum tertutup.")
        return False
    log("Subtitle manual disimpan dan editor subtitle sudah tertutup.")
    return True


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
        return subtitle_filled
    if subtitle_filled or subtitle_required:
        save_debug_artifacts(page, "subtitle-done-not-found")
        raise UploadError(
            "Tombol Selesai subtitle tidak berhasil menutup editor; "
            "upload dihentikan agar subtitle dan urutan step tidak terlewati."
        )
    if not close_subtitle_editor(page, timeout_ms=done_timeout_ms):
        save_debug_artifacts(page, "subtitle-done-not-found")
        message = "Tombol Selesai subtitle tidak ditemukan; subtitle dilewati agar upload tetap lanjut."
        if subtitle_required:
            raise UploadError(message)
        log(message)
        return False
    time.sleep(0.5)
    return subtitle_filled


COPYRIGHT_ISSUE_PATTERNS = (
    r"copyright claim",
    r"copyright issue",
    r"content id claim",
    r"claimed content",
    r"copyright(?:ed|-protected)? content (?:was )?found",
    r"restrictions? found",
    r"klaim hak cipta",
    r"masalah hak cipta",
    r"konten yang diklaim",
    r"konten berhak cipta (?:telah )?ditemukan",
    r"konten yang dilindungi hak cipta (?:telah )?ditemukan",
    r"klaim (?:telah )?ditemukan",
    r"pembatasan.*ditemukan",
    r"masalah ditemukan",
)

COPYRIGHT_ALL_CLEAR_PATTERNS = (
    (r"hak cipta\s+tidak ditemukan masalah", r"pedoman komunitas\s+tidak ditemukan masalah"),
    (r"copyright\s+no issues found", r"community guidelines\s+no issues found"),
)

COPYRIGHT_NON_BLOCKING_VIDEO_PATTERNS = (
    r"tidak ada dampak pada (?:jangkauan )?video",
    r"video (?:ini )?dapat dilihat sesuai dengan setelan anda",
    r"tidak memengaruhi (?:visibilitas|jangkauan)(?: atau fitur)? video anda",
    r"no impact on (?:your )?video",
    r"does not affect (?:your )?(?:video(?:'s)? )?(?:visibility|reach|features)",
    r"your video (?:can|will) remain (?:viewable|visible|on youtube)",
)

COPYRIGHT_NON_BLOCKING_CHANNEL_PATTERNS = (
    r"tidak ada dampak pada (?:channel|kanal)",
    r"(?:hal ini )?bukan (?:sebuah )?teguran hak cipta",
    r"no impact on (?:your )?channel",
    r"does not affect (?:your )?(?:channel|account)",
    r"(?:this is|it's|it is) not a copyright strike",
)

COPYRIGHT_BLOCKING_PATTERNS = (
    r"blocked (?:globally|worldwide|in some|in all|from being viewed)",
    r"(?:partially|fully) blocked",
    r"video (?:is|will be|has been) blocked",
    r"diblokir (?:secara global|di seluruh dunia|di beberapa|agar tidak dapat ditonton)",
    r"video (?:ini )?(?:akan |telah )?diblokir",
    r"(?:copyright )?removal request",
    r"takedown (?:notice|request)",
    r"permintaan penghapusan hak cipta",
    r"video (?:is|was|has been) removed",
    r"video (?:ini )?(?:telah |akan )?dihapus",
    r"(?:visibility|jangkauan) (?:is |will be |akan )?(?:affected|limited|restricted|dibatasi|terpengaruh)",
    r"(?:cannot|can't|tidak dapat|tidak bisa) (?:be )?(?:viewed|watched|ditonton|dilihat)",
    r"(?:channel|account|kanal) (?:warning|penalty|strike|teguran|sanksi)",
    r"restrictions? found",
    r"pembatasan.*ditemukan",
    r"masalah ditemukan",
)


def copyright_issue_detected(body: str) -> bool:
    normalized = re.sub(r"\s+", " ", body or "").casefold()
    return any(re.search(pattern, normalized, re.I) for pattern in COPYRIGHT_ISSUE_PATTERNS)


def copyright_claim_is_explicitly_non_blocking(body: str) -> bool:
    """Accept only YouTube's explicit two-part safe Content ID summary."""
    normalized = re.sub(r"\s+", " ", body or "").casefold()
    if not copyright_issue_detected(normalized):
        return False
    if any(re.search(pattern, normalized, re.I) for pattern in COPYRIGHT_BLOCKING_PATTERNS):
        return False
    video_is_safe = any(
        re.search(pattern, normalized, re.I)
        for pattern in COPYRIGHT_NON_BLOCKING_VIDEO_PATTERNS
    )
    channel_is_safe = any(
        re.search(pattern, normalized, re.I)
        for pattern in COPYRIGHT_NON_BLOCKING_CHANNEL_PATTERNS
    )
    return video_is_safe and channel_is_safe


def copyright_issue_blocks_upload(
    body: str,
    *,
    content_type: str = "auto",
    media_duration_seconds: float = 0.0,
    previously_verified_non_blocking_claim: bool = False,
) -> bool:
    """Apply Fendy Clipper's stricter zero-active-claim upload policy.

    YouTube may describe a claim as non-blocking for a particular territory or
    at a particular moment. That status can differ by country and can change
    later. For this channel, any active copyright/Content ID claim stops the
    upload before the final action, regardless of duration or current impact.
    The compatibility arguments remain so older callers can upgrade safely.
    """
    del content_type, media_duration_seconds, previously_verified_non_blocking_claim
    return copyright_issue_detected(body)


def copyright_checks_all_clear(body: str) -> bool:
    normalized = re.sub(r"\s+", " ", body or "").casefold()
    return any(
        all(re.search(pattern, normalized, re.I) for pattern in pattern_group)
        for pattern_group in COPYRIGHT_ALL_CLEAR_PATTERNS
    )


def copyright_check_is_clear(body: str) -> bool:
    """Return true once Studio explicitly clears the copyright check."""
    normalized = re.sub(r"\s+", " ", body or "").casefold()
    return any(
        re.search(pattern, normalized, re.I)
        for pattern in (
            r"hak cipta\s+tidak ditemukan masalah",
            r"copyright\s+no issues found",
        )
    )


def community_check_is_pending(body: str) -> bool:
    normalized = re.sub(r"\s+", " ", body or "").casefold()
    return any(
        re.search(pattern, normalized, re.I)
        for pattern in (
            r"pedoman komunitas.*(?:sedang memeriksa|masih memeriksa|memeriksa|perlu waktu lebih lama)",
            r"community guidelines.*(?:checking|still checking|in progress|taking longer|takes longer)",
        )
    )


def wait_for_copyright_checks(
    page,
    timeout_ms: int,
    require_checks: bool = True,
    *,
    content_type: str = "auto",
    media_duration_seconds: float = 0.0,
    allow_private_review_while_community_pending: bool = False,
    skip_pending_checks_for_private_review: bool = False,
) -> bool:
    log("Menunggu YouTube Studio Checks sampai semua pemeriksaan aman...")
    deadline = time.monotonic() + timeout_ms / 1000
    long_running_extension_seconds = max(
        0,
        int(os.environ.get("YOUTUBE_CHECKS_LONG_RUNNING_EXTENSION_SECONDS", "1800")),
    )
    progress_log_interval_seconds = max(
        15,
        int(os.environ.get("YOUTUBE_CHECKS_PROGRESS_LOG_INTERVAL_SECONDS", "60")),
    )
    long_running_extended = False
    next_progress_log_at = 0.0
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
        r"masih memeriksa",
        r"still checking",
        r"perlu waktu lebih lama",
        r"taking longer",
        r"takes longer",
    )
    long_running_patterns = (
        r"perlu waktu lebih lama",
        r"membutuhkan waktu lebih lama",
        r"taking longer",
        r"takes longer",
        r"still processing",
    )
    last_body = ""
    while True:
        now = time.monotonic()
        if now >= deadline:
            break
        dismiss_reload_prompt(page, timeout_ms=300)
        body = active_upload_dialog_text(page, timeout_ms=3000)
        if not body:
            time.sleep(1)
            continue
        lowered = body.lower()
        last_body = re.sub(r"\s+", " ", body).strip()[:500]
        has_checking = any(re.search(pattern, lowered, re.I) for pattern in checking_patterns)
        has_long_running = any(re.search(pattern, lowered, re.I) for pattern in long_running_patterns)
        has_all_clear = copyright_checks_all_clear(body)
        has_non_blocking_claim = copyright_claim_is_explicitly_non_blocking(body)
        if copyright_issue_blocks_upload(
            body,
            content_type=content_type,
            media_duration_seconds=media_duration_seconds,
        ):
            save_debug_artifacts(page, "copyright-claim-detected")
            impact_note = (
                " Studio saat ini menyebut klaim tidak berdampak, tetapi Fendy Clipper "
                "tetap menolaknya karena kebijakan klaim dapat berbeda per wilayah atau berubah kemudian."
                if has_non_blocking_claim
                else ""
            )
            raise CopyrightClaimUploadError(
                "YouTube Studio mendeteksi klaim Content ID/copyright pada clip ini. "
                "Upload dibatalkan sebelum aksi Simpan/Publikasikan agar channel tetap aman."
                f"{impact_note}"
            )
        if skip_pending_checks_for_private_review and has_checking:
            log(
                "Checks YouTube masih diproses tanpa klaim eksplisit. "
                "Upload Private dilanjutkan sekarang; hasil pemeriksaan tetap berjalan di YouTube Studio."
            )
            return True
        if (
            allow_private_review_while_community_pending
            and copyright_check_is_clear(body)
            and community_check_is_pending(body)
        ):
            log(
                "Copyright sudah aman; pemeriksaan Pedoman Komunitas masih berjalan. "
                "Upload Private disimpan untuk review tanpa menahan antrean."
            )
            return True
        if has_long_running and not long_running_extended and long_running_extension_seconds:
            deadline += long_running_extension_seconds
            long_running_extended = True
            log(
                "YouTube menyatakan Checks perlu waktu lebih lama; "
                f"batas tunggu ditambah {long_running_extension_seconds // 60} menit."
            )
        if has_checking:
            if now >= next_progress_log_at:
                remaining_minutes = max(1, math.ceil((deadline - now) / 60))
                log(
                    "Checks masih berjalan; menunggu sampai semua centang aman "
                    f"(maksimal sekitar {remaining_minutes} menit lagi)."
                )
                next_progress_log_at = now + progress_log_interval_seconds
            time.sleep(5)
            continue
        if has_all_clear:
            log("YouTube Studio Checks aman: hak cipta dan pedoman komunitas sudah centang.")
            return False
        time.sleep(2)

    if require_checks:
        if env_bool("YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK", False):
            log(
                "Checks belum terkonfirmasi sampai timeout, tetapi tidak ada issue eksplisit; "
                "lanjut ke Visibilitas sesuai konfigurasi."
            )
            return False
        save_debug_artifacts(page, "checks-not-complete")
        raise UploadError(
            "Step 3 Checks belum selesai/tercentang setelah waktu tunggu panjang; "
            "upload tidak dilanjutkan ke Visibilitas. "
            f"Upload dibatalkan demi keamanan. Cuplikan halaman: {last_body}"
        )
    log("Checks belum terkonfirmasi; melanjutkan karena require checks dinonaktifkan.")
    return False


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
    match = re.search(
        r"(?:https?://)?studio\.youtube\.com/(?:channel/[^/?#]+/)?video/([A-Za-z0-9_-]{6,})(?:/edit)?",
        clean,
        re.I,
    )
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return ""


def extract_video_url(page, expected_title: str = "") -> str:
    try:
        video_id = page.locator("ytcp-uploads-dialog").first.get_attribute("video-id", timeout=1000) or ""
        if re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id.strip()):
            return f"https://www.youtube.com/watch?v={video_id.strip()}"
    except Exception:
        pass
    candidates = (
        [
            'ytcp-uploads-dialog a[href*="studio.youtube.com/video/"]',
            'ytcp-uploads-dialog a[href*="/video/"][href*="/edit"]',
            'ytcp-uploads-dialog a[href*="youtu.be/"]',
            'ytcp-uploads-dialog a[href*="youtube.com/watch"]',
            'ytcp-uploads-dialog a[href*="youtube.com/shorts/"]',
            'ytcp-uploads-dialog a[href*="/watch?v="]',
            'ytcp-uploads-dialog a[href*="/shorts/"]',
            'ytcp-uploads-dialog ytcp-video-info a',
        ]
        if expected_title
        else [
            'a[href*="studio.youtube.com/video/"]',
            'a[href*="/video/"][href*="/edit"]',
            'a[href*="youtu.be/"]',
            'a[href*="youtube.com/watch"]',
            'a[href*="youtube.com/shorts/"]',
            'a[href*="/watch?v="]',
            'a[href*="/shorts/"]',
            'ytcp-video-info a',
        ]
    )
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
    if expected_title:
        try:
            href = page.evaluate(
                r"""
                ({ expectedTitle }) => {
                  const normalize = (value) => String(value || '')
                    .replace(/\s+/g, ' ').trim().toLocaleLowerCase();
                  const wanted = normalize(expectedTitle);
                  const roots = [];
                  const seen = new Set();
                  const addRoot = (root) => {
                    if (root && !seen.has(root)) {
                      seen.add(root);
                      roots.push(root);
                    }
                  };
                  addRoot(document);
                  for (let index = 0; index < roots.length; index += 1) {
                    const root = roots[index];
                    const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
                    for (const element of elements) {
                      if (element.shadowRoot) addRoot(element.shadowRoot);
                    }
                  }
                  const videoHref = (href) => /(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/|studio\.youtube\.com\/(?:channel\/[^/?#]+\/)?video\/|\/video\/[A-Za-z0-9_-]{6,}\/edit)/i.test(href || '');
                  const matchesExpectedRow = (anchor) => {
                    let node = anchor;
                    for (let depth = 0; node && depth < 10; depth += 1) {
                      const tag = String(node.tagName || '').toUpperCase();
                      if (['BODY', 'HTML', 'YTCP-APP', 'YTCP-MAIN'].includes(tag)) break;
                      const text = normalize(node.innerText || node.textContent || '');
                      if (text.includes(wanted)) return true;
                      const root = node.getRootNode?.();
                      node = node.parentElement || (root && root.host) || null;
                    }
                    return false;
                  };
                  for (const root of roots) {
                    const anchors = root.querySelectorAll ? Array.from(root.querySelectorAll('a[href]')) : [];
                    for (const anchor of anchors) {
                      const href = anchor.href || anchor.getAttribute('href') || '';
                      if (videoHref(href) && matchesExpectedRow(anchor)) return href;
                    }
                  }
                  return '';
                }
                """,
                {"expectedTitle": expected_title},
            )
            video_url = normalize_youtube_video_url(str(href or ""))
            if video_url:
                return video_url
        except Exception:
            pass
    return ""


def saved_video_row_snapshot(page, expected_title: str, visibility: str) -> dict[str, str]:
    """Find the exact saved upload row on Studio's Content page."""
    try:
        result = page.evaluate(
            r"""
            ({ expectedTitle, visibility }) => {
              const normalize = (value) => String(value || '')
                .replace(/\s+/g, ' ').trim().toLocaleLowerCase();
              const wanted = normalize(expectedTitle);
              const visibilityWords = visibility === 'private'
                ? ['private', 'pribadi']
                : visibility === 'unlisted'
                  ? ['unlisted', 'tidak publik']
                  : ['public', 'publik'];
              const roots = [];
              const seen = new Set();
              const addRoot = (root) => {
                if (root && !seen.has(root)) {
                  seen.add(root);
                  roots.push(root);
                }
              };
              addRoot(document);
              for (let index = 0; index < roots.length; index += 1) {
                const root = roots[index];
                const elements = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
                for (const element of elements) {
                  if (element.shadowRoot) addRoot(element.shadowRoot);
                }
              }
              const videoHref = (href) => /(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/|studio\.youtube\.com\/(?:channel\/[^/?#]+\/)?video\/|\/video\/[A-Za-z0-9_-]{6,}\/edit)/i.test(href || '');
              const ancestors = (anchor) => {
                const values = [];
                let node = anchor;
                for (let depth = 0; node && depth < 12; depth += 1) {
                  const tag = String(node.tagName || '').toUpperCase();
                  if (['BODY', 'HTML', 'YTCP-APP', 'YTCP-MAIN'].includes(tag)) break;
                  values.push(node);
                  const root = node.getRootNode?.();
                  node = node.parentElement || (root && root.host) || null;
                }
                return values;
              };
              for (const root of roots) {
                const anchors = root.querySelectorAll ? Array.from(root.querySelectorAll('a[href]')) : [];
                for (const anchor of anchors) {
                  const href = anchor.href || anchor.getAttribute('href') || '';
                  if (!videoHref(href)) continue;
                  for (const container of ancestors(anchor)) {
                    const text = normalize(container.innerText || container.textContent || '');
                    if (!text.includes(wanted)) continue;
                    const visibilityOk = visibilityWords.some((word) => text.includes(word));
                    const uploadFailed = /(?:upload|mengupload|mengunggah).{0,30}(?:failed|gagal)|(?:failed|gagal).{0,30}(?:upload|mengupload|mengunggah)/i.test(text);
                    const uploading = /(?:uploading|mengupload|mengunggah)\s*\d{1,3}\s*%/i.test(text);
                    return { href, text, visibilityOk, uploadFailed, uploading };
                  }
                }
              }
              return { href: '', text: '', visibilityOk: false, uploadFailed: false, uploading: false };
            }
            """,
            {"expectedTitle": expected_title, "visibility": visibility},
        )
    except Exception:
        return {}
    if not isinstance(result, dict):
        return {}
    return {str(key): str(value) for key, value in result.items()}


def verify_saved_video_in_studio(
    page,
    expected_title: str,
    visibility: str,
    *,
    timeout_ms: int = 30000,
) -> str:
    """Verify a just-saved video in a separate Studio Content tab."""
    if not expected_title.strip():
        return ""
    context = getattr(page, "context", None)
    if context is None:
        return ""
    verification_page = None
    try:
        verification_page = context.new_page()
        install_browser_dialog_guard(verification_page)
        channel_id = effective_channel_id(page)
        target_url = (
            f"https://studio.youtube.com/channel/{channel_id}/videos/upload"
            if channel_id
            else "https://studio.youtube.com/videos/upload"
        )
        verification_page.goto(target_url, wait_until="domcontentloaded", timeout=max(15000, timeout_ms))
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            snapshot = saved_video_row_snapshot(verification_page, expected_title, visibility)
            video_url = normalize_youtube_video_url(snapshot.get("href", ""))
            if snapshot.get("uploadFailed") == "True":
                raise UploadError("YouTube Studio menandai transfer video baru gagal.")
            if (
                video_url
                and snapshot.get("visibilityOk") == "True"
                and snapshot.get("uploading") != "True"
            ):
                return video_url
            time.sleep(2)
        return ""
    except UploadError:
        raise
    except Exception:
        return ""
    finally:
        if verification_page is not None:
            try:
                verification_page.close()
            except Exception:
                pass


def wait_for_final_upload_confirmation(
    page,
    timeout_ms: int,
    video_url: str = "",
    *,
    expected_title: str = "",
    visibility: str = "private",
) -> str:
    deadline = time.monotonic() + timeout_ms / 1000
    done_patterns = (
        r"video (published|uploaded)",
        r"upload complete",
        r"processing will begin shortly",
        r"checks? will begin shortly",
        r"video (berhasil )?(telah )?dipublikasikan",
        r"berhasil dipublikasikan",
        r"upload selesai",
        r"upload telah selesai",
        r"pemrosesan akan segera dimulai",
        r"pemeriksaan akan segera dimulai",
    )
    pending_patterns = (
        r"uploading\s*\d{1,3}\s*%",
        r"mengupload\s*\d{1,3}\s*%",
        r"mengunggah\s*\d{1,3}\s*%",
        r"upload(?:ing)? (?:is )?(?:still )?in progress",
        r"upload sedang berlangsung",
    )
    error_patterns = (
        r"upload failed",
        r"failed to upload",
        r"upload gagal",
        r"gagal mengupload",
        r"gagal mengunggah",
    )
    last_body = ""
    last_progress_percent = -1
    next_progress_log_at = 0.0
    closed_idle_checks = 0
    while True:
        now = time.monotonic()
        if now >= deadline:
            break
        dismiss_reload_prompt(page, timeout_ms=300)
        dialog_count: int | None = None
        try:
            dialog_count = page.locator("ytcp-uploads-dialog").count()
        except Exception:
            pass

        # Setelah tombol Simpan ditekan, Studio dapat menutup modal meskipun
        # transfer file masih berjalan di background. Karena itu, modal yang
        # hilang bukan lagi bukti sukses: baca juga status global Content page.
        dialog_body = active_upload_dialog_text(page, timeout_ms=3000)
        # Saat modal masih terbuka, jangan mencampur teks halaman di belakangnya:
        # daftar Content dapat berisi video lama berstatus "published" dan
        # menghasilkan sukses palsu. Status global hanya dipakai setelah modal
        # upload aktif benar-benar hilang.
        global_body = page_identity_text(page) if dialog_count == 0 else ""
        body = "\n".join(part for part in (dialog_body, global_body) if part)
        last_body = re.sub(r"\s+", " ", body).strip()[:500]
        if any(re.search(pattern, body, re.I) for pattern in error_patterns):
            save_debug_artifacts(page, "final-upload-failed")
            raise UploadError(
                "YouTube melaporkan transfer upload gagal. "
                f"File lokal dipertahankan. Cuplikan halaman: {last_body}"
            )
        pending = any(re.search(pattern, body, re.I) for pattern in pending_patterns)
        progress = re.search(
            r"(?:uploading|mengupload|mengunggah)\s*(\d{1,3})\s*%",
            body,
            re.I,
        )
        if progress:
            progress_percent = min(100, int(progress.group(1)))
            if progress_percent > last_progress_percent:
                last_progress_percent = progress_percent
                # File besar boleh melewati estimasi awal selama transfernya
                # nyata-nyata bergerak. Timeout menjadi batas tanpa progres,
                # bukan batas total yang memutus upload aktif.
                deadline = max(deadline, now + timeout_ms / 1000)
        # Jika halaman memuat beberapa video, teks upload lama yang selesai
        # dapat muncul bersamaan dengan upload aktif. Status pending selalu
        # menang agar upload saat ini tidak dianggap selesai terlalu dini.
        if not pending and any(re.search(pattern, body, re.I) for pattern in done_patterns):
            log("Konfirmasi final upload terdeteksi.")
            return video_url or extract_video_url(page, expected_title)
        if dialog_count == 0 and not pending:
            closed_idle_checks += 1
            if closed_idle_checks >= 5 and expected_title:
                verified_url = verify_saved_video_in_studio(
                    page,
                    expected_title,
                    visibility,
                    timeout_ms=min(30000, timeout_ms),
                )
                if verified_url:
                    log(
                        "Konfirmasi final dipulihkan dari halaman Content: "
                        "video baru terdaftar dengan visibilitas yang benar."
                    )
                    return verified_url
                closed_idle_checks = 0
        else:
            closed_idle_checks = 0
        if now >= next_progress_log_at:
            if progress:
                log(
                    f"Transfer video masih berjalan ({progress.group(1)}%); "
                    "uploader tetap menunggu dan file lokal tidak akan dihapus."
                )
            elif pending:
                log("Transfer video masih berjalan; menunggu konfirmasi selesai dari YouTube.")
            elif dialog_count == 0:
                log(
                    "Modal upload sudah tertutup, tetapi konfirmasi transfer selesai belum terlihat; "
                    "tetap menunggu."
                )
            else:
                log("Menunggu konfirmasi final transfer dari YouTube Studio.")
            next_progress_log_at = now + 30
        time.sleep(3)
    save_debug_artifacts(page, "final-upload-confirmation-timeout")
    raise UploadError(
        "Upload YouTube belum terkonfirmasi selesai sampai timeout. "
        "File lokal dipertahankan dan antrean tidak dilanjutkan sebagai sukses. "
        f"Cuplikan halaman: {last_body}"
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


def run_verify_upload(args: argparse.Namespace) -> None:
    """Recover a post-save upload without selecting the local file again."""
    sync_playwright, _ = import_playwright()
    state_path = Path(args.state).expanduser().resolve()
    if not state_path.is_file():
        raise UploadError(f"File sesi YouTube belum ada: {state_path}")

    headless = args.headless if args.headless is not None else env_bool("YOUTUBE_HEADLESS", True)
    slow_mo = int(os.environ.get("YOUTUBE_BROWSER_SLOW_MO_MS", "0"))
    timeout_ms = max(30, int(args.timeout)) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context(
            locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
            storage_state=str(state_path),
            viewport={"width": 1440, "height": 1000},
        )
        install_context_dialog_guard(context)
        page = context.new_page()
        install_browser_dialog_guard(page)
        try:
            goto_studio(page, studio_url=args.studio_url)
            ensure_logged_in(page)
            ensure_target_identity(
                page,
                args.target_channel,
                args.target_email,
                args.target_channel_id,
            )
            video_url = verify_saved_video_in_studio(
                page,
                args.title,
                args.visibility,
                timeout_ms=timeout_ms,
            )
            if not video_url:
                raise UploadError(
                    "Video yang sudah difinalkan belum ditemukan sebagai baris tersimpan "
                    "di halaman Content; file lokal dipertahankan."
                )
            log(f"FINAL_VISIBILITY: {args.visibility}")
            log("UPLOAD_CONFIRMED: video pasca-restart terverifikasi di halaman Content.")
            log(f"VIDEO_URL: {video_url}")
            context.storage_state(path=str(state_path))
        finally:
            context.close()
            browser.close()


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

    requested_visibility = args.visibility
    args.visibility = safe_upload_visibility(args.visibility)
    if requested_visibility != args.visibility:
        log(
            "Mode aman aktif: upload otomatis disimpan Private. "
            "Publikasikan manual hanya jika kolom Pembatasan benar-benar bebas "
            "klaim Content ID, blokir, dan strike."
        )

    if args.thumbnail_content_type == "auto":
        args.thumbnail_content_type = (
            "long-form" if should_upload_custom_thumbnail(video_path, "auto") else "shorts"
        )
    if args.media_duration_seconds <= 0:
        args.media_duration_seconds = probe_upload_media_duration_seconds(video_path)
    if args.media_duration_seconds > 0:
        log(
            f"Kebijakan upload memakai tipe {args.thumbnail_content_type} "
            f"dan durasi {args.media_duration_seconds:.2f} detik."
        )
    else:
        log(
            f"Durasi media tidak terbaca; klaim Content ID pada tipe {args.thumbnail_content_type} "
            "akan ditangani secara konservatif."
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
            existing_pages = [item for ctx in contexts for item in ctx.pages]
            close_idle_fendy_clipper_upload_tabs(existing_pages)
            existing_pages = [item for ctx in contexts for item in ctx.pages]
            studio_pages = [item for item in existing_pages if "studio.youtube.com" in item.url.lower()]
            target_pages = [item for item in studio_pages if page_url_matches_channel_id(item, args.target_channel_id)]
            primary_studio_page = target_pages[0] if target_pages else (studio_pages[0] if studio_pages else None)
            if primary_studio_page is not None:
                close_duplicate_target_studio_tabs(
                    studio_pages,
                    primary_studio_page,
                    args.target_channel_id,
                )
                context = primary_studio_page.context
            else:
                context = contexts[0]
            hydrated_page = hydrate_context_and_open_studio_page(context, state_path, args.studio_url)
            if hydrated_page is not None:
                page = hydrated_page
            else:
                page = context.new_page()
            mark_fendy_clipper_upload_tab(page)
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

            thumbnail_daily_limit_waived = False
            if args.thumbnail:
                thumbnail_path = Path(args.thumbnail).expanduser().resolve()
                if should_upload_custom_thumbnail(video_path, args.thumbnail_content_type):
                    if not thumbnail_path.is_file():
                        if args.thumbnail_content_type == "long-form":
                            raise UploadError(f"File thumbnail tidak ditemukan: {thumbnail_path}")
                        log(
                            "THUMBNAIL_SKIPPED: aset thumbnail Short tidak ditemukan; "
                            "upload video tetap dilanjutkan."
                        )
                    else:
                        thumbnail_required = args.thumbnail_content_type == "long-form"
                        try:
                            set_thumbnail(
                                page,
                                thumbnail_path,
                                content_type=args.thumbnail_content_type,
                                required=thumbnail_required,
                            )
                        except ThumbnailDailyLimitUploadError as exc:
                            thumbnail_daily_limit_waived = True
                            log(
                                "THUMBNAIL_SKIPPED_DAILY_LIMIT: "
                                f"{exc} Video tetap dilanjutkan dengan thumbnail otomatis YouTube."
                            )
                        except UploadError as exc:
                            if thumbnail_required:
                                raise
                            log(
                                "THUMBNAIL_SKIPPED: thumbnail Short belum dapat dipasang "
                                f"oleh Studio ({exc}); upload video tetap dilanjutkan."
                            )

            select_playlist(page, args.playlist)
            if args.made_for_kids:
                click_text(page, [r"yes,.*made for kids", r"ya,.*anak"], timeout_ms=8000)
            else:
                click_text(page, [r"no,.*not made for kids", r"tidak,.*anak"], timeout_ms=8000)
            log("Setelan audiens dipilih.")
            set_altered_content_disclosure(page, args.altered_content)
            if args.tags:
                log("Kolom Tags lanjutan dilewati; hashtag sudah dimasukkan ke deskripsi.")

            # Studio can re-render the Details form after thumbnail/playlist
            # changes. Verify the exact active fields immediately before we
            # leave this step and repair them once if their values disappeared.
            metadata_checks = (
                (
                    upload_title,
                    "judul",
                    "title",
                    (r"(^|\n)(title|judul)(\n|$)", r"add a title", r"tambahkan judul"),
                    (r"description", r"deskripsi"),
                ),
                (
                    upload_description,
                    "deskripsi",
                    "description",
                    (r"(^|\n)(description|deskripsi)(\n|$)", r"tell viewers", r"beri tahu penonton"),
                    (r"(^|\n)(title|judul)(\n|$)",),
                ),
            )
            for expected, metadata_label, field_kind, patterns, rejects in metadata_checks:
                if upload_text_field_contains(
                    page,
                    expected,
                    patterns,
                    reject_patterns=rejects,
                    timeout_ms=2500,
                    field_kind=field_kind,
                ):
                    continue
                log(f"{metadata_label.capitalize()} berubah/hilang setelah render ulang Studio; mengisi ulang.")
                set_upload_text_field(page, expected, metadata_label, patterns, reject_patterns=rejects)

            if args.thumbnail and thumbnail_path.is_file() and should_upload_custom_thumbnail(
                video_path, args.thumbnail_content_type
            ) and not thumbnail_daily_limit_waived:
                thumbnail_state = thumbnail_upload_state(page)
                if not thumbnail_state["selected"]:
                    log("Thumbnail belum melekat pada dialog aktif; mencoba pemasangan ulang satu kali.")
                    thumbnail_required = args.thumbnail_content_type == "long-form"
                    try:
                        set_thumbnail(
                            page,
                            thumbnail_path,
                            content_type=args.thumbnail_content_type,
                            required=thumbnail_required,
                        )
                    except ThumbnailDailyLimitUploadError as exc:
                        thumbnail_daily_limit_waived = True
                        log(
                            "THUMBNAIL_SKIPPED_DAILY_LIMIT: "
                            f"{exc} Video tetap dilanjutkan dengan thumbnail otomatis YouTube."
                        )
                    except UploadError as exc:
                        if thumbnail_required:
                            raise
                        log(
                            "THUMBNAIL_SKIPPED: thumbnail Short belum dapat dipasang "
                            f"setelah verifikasi akhir ({exc}); upload tetap dilanjutkan."
                        )

            # A thumbnail retry can also re-render metadata. This is the final
            # hard gate: never continue with YouTube's filename title or an
            # empty description when proper metadata was supplied.
            for expected, metadata_label, field_kind, patterns, rejects in metadata_checks:
                if not upload_text_field_contains(
                    page,
                    expected,
                    patterns,
                    reject_patterns=rejects,
                    timeout_ms=5000,
                    field_kind=field_kind,
                ):
                    save_debug_artifacts(page, f"{metadata_label}-missing-before-next")
                    raise UploadError(
                        f"{metadata_label.capitalize()} belum tersimpan pada dialog upload aktif; "
                        "proses dihentikan sebelum tab Visibilitas agar metadata kosong tidak terunggah."
                    )
            log("Judul dan deskripsi dialog aktif terverifikasi sebelum lanjut.")

            # Long-form must never leave Details until the custom thumbnail is
            # visibly selected and its transfer has finished. The only safe
            # exception is Studio's explicit daily-limit response: retrying the
            # same file cannot succeed until YouTube restores the channel quota.
            if args.thumbnail_content_type == "long-form" and not thumbnail_daily_limit_waived:
                if not args.thumbnail:
                    raise UploadError(
                        "Upload long-form dihentikan karena file thumbnail wajib belum diberikan."
                    )
                final_thumbnail_state = thumbnail_upload_state(page)
                final_thumbnail_error = str(final_thumbnail_state.get("error") or "").strip()
                if final_thumbnail_error:
                    save_debug_artifacts(page, "thumbnail-final-rejected")
                    raise UploadError(
                        f"YouTube menolak thumbnail long-form: {final_thumbnail_error}"
                    )
                if (
                    not final_thumbnail_state.get("selected")
                    or final_thumbnail_state.get("uploading")
                ):
                    save_debug_artifacts(page, "thumbnail-missing-before-next")
                    raise UploadError(
                        "Thumbnail long-form belum terpasang dan terverifikasi di YouTube Studio; "
                        "proses dihentikan sebelum Elemen video."
                    )
                log("THUMBNAIL_CONFIRMED_BEFORE_NEXT: thumbnail long-form terverifikasi di Detail.")
            elif args.thumbnail_content_type == "long-form":
                log(
                    "THUMBNAIL_DAILY_LIMIT_FALLBACK_CONFIRMED: batas harian terverifikasi; "
                    "lanjut tanpa mengulangi transfer thumbnail."
                )

            next_step_timeout_ms = next_upload_step_timeout_ms(
                timeout_ms,
                args.thumbnail_content_type,
            )
            click_next_upload_step(page, timeout_ms=next_step_timeout_ms, expected_step="VIDEO_ELEMENTS")
            log("Masuk ke tab Elemen video.")
            subtitle_text = os.environ.get("YOUTUBE_MANUAL_SUBTITLE_TEXT", "FCN").strip() or "FCN"
            subtitle_added = add_manual_subtitle(page, subtitle_text)
            if subtitle_added and subtitle_editor_open(page):
                save_debug_artifacts(page, "subtitle-editor-still-open")
                raise UploadError(
                    "Editor subtitle masih terbuka setelah tombol Selesai; "
                    "step berikutnya tidak dijalankan."
                )

            click_next_upload_step(page, timeout_ms=next_step_timeout_ms, expected_step="CHECKS")
            log("Step Elemen video sudah tercentang; masuk ke tab Pemeriksaan awal.")
            strict_zero_claim = env_bool("YOUTUBE_STRICT_ZERO_CLAIM", True)
            effective_require_copyright_checks = bool(
                args.require_copyright_checks or strict_zero_claim
            )
            private_review_checks_pending = wait_for_copyright_checks(
                page,
                min(timeout_ms, int(os.environ.get("YOUTUBE_CHECKS_TIMEOUT_SECONDS", "3600")) * 1000),
                effective_require_copyright_checks,
                content_type=args.thumbnail_content_type,
                media_duration_seconds=args.media_duration_seconds,
                allow_private_review_while_community_pending=(
                    args.visibility == "private"
                    and not effective_require_copyright_checks
                    and env_bool("YOUTUBE_PRIVATE_FAST_CHECKS", False)
                ),
                skip_pending_checks_for_private_review=(
                    args.visibility == "private"
                    and not effective_require_copyright_checks
                    and env_bool("YOUTUBE_PRIVATE_SKIP_PENDING_CHECKS", False)
                ),
            )
            if private_review_checks_pending:
                log("Checks masih diproses YouTube; lanjut ke Visibilitas Private tanpa menahan antrean.")
            else:
                log("Step 3 Checks sudah selesai dan aman; lanjut ke Visibilitas.")

            click_next_upload_step(page, timeout_ms=next_step_timeout_ms, expected_step="REVIEW")
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
            if effective_require_copyright_checks:
                review_timeout_ms = int(os.environ.get("YOUTUBE_PRE_PUBLISH_REVIEW_TIMEOUT_SECONDS", "900")) * 1000
                wait_for_review_checks_safe_before_publish(
                    page,
                    timeout_ms=review_timeout_ms,
                    visibility=args.visibility,
                    content_type=args.thumbnail_content_type,
                    media_duration_seconds=args.media_duration_seconds,
                )

            if args.dry_run:
                log("Dry-run aktif; proses berhenti sebelum publish/save final.")
                return

            uploaded_video_url = extract_video_url(page, upload_title)
            click_final_upload_action(
                page,
                args.visibility,
                timeout_ms=30000,
                content_type=args.thumbnail_content_type,
                media_duration_seconds=args.media_duration_seconds,
            )
            final_url = uploaded_video_url or extract_video_url(page, upload_title)
            log(f"FINAL_VISIBILITY: {args.visibility}")
            if final_url:
                # Persist the assigned video id before the potentially long
                # transfer-confirmation wait. This is a recovery checkpoint,
                # not a success marker; UPLOAD_CONFIRMED remains the hard gate.
                log(f"VIDEO_URL: {final_url}")
            final_url = wait_for_final_upload_confirmation(
                page,
                timeout_ms=timeout_ms,
                video_url=final_url,
                expected_title=upload_title,
                visibility=args.visibility,
            )
            log("UPLOAD_CONFIRMED: YouTube Studio mengonfirmasi transfer video selesai.")
            if final_url and final_url != uploaded_video_url:
                log(f"VIDEO_URL: {final_url}")
            reload_after_publish(page)
            context.storage_state(path=str(state_path))
        except CopyrightClaimUploadError as exc:
            log(f"Publikasi dihentikan: {exc}")
            log(
                "CLAIMED_UPLOAD_ABORTED: zero_active_claim_policy; "
                "video tidak disimpan sebagai Private dan tidak dipublikasikan."
            )
            context.storage_state(path=str(state_path))
            raise UploadError(
                "Upload dihentikan oleh kebijakan nol-klaim. Pilih sumber yang hak audio dan "
                "visualnya benar-benar Anda miliki/izinkan; klaim tidak disimpan sebagai Private."
            ) from exc
        finally:
            close_upload_tab(page, force=using_cdp)
            if not using_cdp:
                context.close()
            if browser is not None and not using_cdp:
                browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload Fendy Clipper outputs to YouTube Studio with Playwright.")
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

    verify_upload = subparsers.add_parser(
        "verify-upload",
        help="Verifikasi upload yang finalisasinya terputus tanpa memilih file lagi.",
    )
    verify_upload.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    verify_upload.add_argument("--title", required=True)
    verify_upload.add_argument(
        "--visibility",
        choices=["private", "unlisted", "public"],
        default="private",
    )
    verify_upload.add_argument("--target-channel", default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundyofficial"))
    verify_upload.add_argument("--target-email", default=DEFAULT_TARGET_EMAIL)
    verify_upload.add_argument("--target-channel-id", default=DEFAULT_TARGET_CHANNEL_ID)
    verify_upload.add_argument("--studio-url", default=DEFAULT_STUDIO_URL)
    verify_upload.add_argument("--timeout", type=int, default=120)
    verify_upload.add_argument("--headless", action=argparse.BooleanOptionalAction, default=None)

    upload = subparsers.add_parser("upload", help="Upload satu file video ke YouTube Studio.")
    upload.add_argument("video")
    upload.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    upload.add_argument("--title", required=True)
    upload.add_argument("--description", default="")
    upload.add_argument("--thumbnail", default="")
    upload.add_argument(
        "--thumbnail-content-type",
        choices=["auto", "shorts", "long-form"],
        default="auto",
        help="Pasang gambar custom untuk long-form; Shorts memakai cover frame di dalam video.",
    )
    upload.add_argument(
        "--media-duration-seconds",
        type=float,
        default=0.0,
        help="Durasi media untuk menerapkan aturan Content ID Shorts 1-3 menit.",
    )
    upload.add_argument("--visibility", choices=["private", "unlisted", "public"], default=os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "private"))
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
    upload.add_argument("--altered-content", action="store_true")
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
        elif args.command == "verify-upload":
            run_verify_upload(args)
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
