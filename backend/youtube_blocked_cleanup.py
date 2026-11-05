"""Occasional Studio cleanup of explicitly fully blocked videos, using live CDP."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import uuid
import urllib.request

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "youtube-blocked-cleanup"
BUCKETS = ("upload", "short", "live")
ROW_SCRIPT = r"""() => [...document.querySelectorAll('ytcp-video-row,ytcp-video-row-v2')].map(row => {
  const links = [...row.querySelectorAll('a[href]')];
  const ids = [...new Set(links.map(a => a.getAttribute('href').match(/^\/video\/([\w-]{11})\/edit(?:[?#]|$)/)?.[1]).filter(Boolean))];
  const titles = links.filter(a=>a.getAttribute('href').includes('/edit')).map(a=>a.innerText.trim());
  return {video_id:ids.length===1?ids[0]:'', title:row.querySelector('#video-title')?.innerText?.trim() || titles.sort((a,b)=>b.length-a.length)[0] || '',
    visibility:row.querySelector('.tablecell-visibility')?.innerText || '',
    restrictions:row.querySelector('.tablecell-restrictions')?.innerText || ''};
})"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fully_blocked(row: dict) -> bool:
    """Only status cells count; titles, claims and limited ads never authorize delete."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(row.get("video_id") or "")):
        return False
    visibility = str(row.get("visibility") or "").casefold()
    if re.search(r"\b(private|pribadi|scheduled|dijadwalkan|terjadwal|draft|draf)\b", visibility):
        return False
    text = "\n".join(str(row.get(k) or "") for k in ("visibility", "restrictions")).casefold()
    if re.search(r"partially|some (?:countries|regions)|certain countries|sebagian|beberapa (?:negara|wilayah)", text):
        return False
    labels = {re.sub(r"\s+", " ", s).strip() for s in text.splitlines()}
    return bool(labels & {"blocked", "diblokir", "blocked worldwide", "globally blocked", "diblokir di seluruh dunia"})


def settings() -> dict:
    values = {}
    keys = {"YOUTUBE_CDP_URL", "YOUTUBE_TARGET_CHANNEL", "YOUTUBE_TARGET_EMAIL", "YOUTUBE_TARGET_CHANNEL_ID",
            "YOUTUBE_BLOCKED_CLEANUP_ENABLED", "YOUTUBE_BLOCKED_CLEANUP_INTERVAL_HOURS", "YOUTUBE_BLOCKED_CLEANUP_MAX_DELETIONS"}
    for line in (BASE.parent / ".env").read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() in keys:
            values[key.strip()] = value.strip().strip("\"'")
    values.update({k: os.environ[k] for k in keys if k in os.environ})
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", values.get("YOUTUBE_TARGET_CHANNEL_ID", "")):
        raise RuntimeError("An exact target channel ID is required")
    if not re.fullmatch(r"http://(?:localhost|127\.0\.0\.1):\d{4,5}", values.get("YOUTUBE_CDP_URL", "")):
        raise RuntimeError("Only the existing local Chrome CDP endpoint is supported")
    return values


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
    os.replace(temporary, path)


def uploads_busy(context=None, owned_pages=()) -> bool:
    # An unavailable API is not evidence of an idle queue.
    for platform in ("youtube", "tiktok"):
        with urllib.request.urlopen(f"http://127.0.0.1:8010/api/{platform}/uploads", timeout=10) as response:
            rows = json.load(response)
        if not isinstance(rows, list):
            raise RuntimeError("Upload queue returned an unexpected response")
        if any(row.get("status") in {"queued", "running"} for row in rows):
            return True
    if context:
        for page in context.pages:
            if page not in owned_pages and not page.is_closed() and "studio.youtube.com" in page.url:
                if page.locator("ytcp-uploads-dialog:visible").count():
                    return True
    return False


def wait_rows(page) -> list[dict]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    try:
        page.wait_for_function("""() => document.querySelector('ytcp-video-row,ytcp-video-row-v2') ||
          [...document.querySelectorAll('ytcp-blank-state')].some(e=>e.getBoundingClientRect().height) ||
          /no (matching )?(videos|content)|tidak ada (video|konten)|belum ada (video|konten)/i.test(document.body?.innerText||'')""", timeout=90_000)
    except PlaywrightTimeout as exc:
        raise RuntimeError("Studio list was not ready; no deletion is authorized") from exc
    return page.evaluate(ROW_SCRIPT)


def next_page(page, previous: list[dict]) -> bool:
    button = page.locator("ytcp-icon-button#navigate-after").first
    if not button.count():
        raise RuntimeError("Studio pagination is unavailable; scan is incomplete")
    disabled = button.get_attribute("aria-disabled")
    if disabled == "true" or button.get_attribute("disabled") is not None:
        return False
    if disabled != "false":
        raise RuntimeError("Studio next-page state is unknown; scan is incomplete")
    old = [x["video_id"] for x in previous]
    button.click(timeout=10_000)
    page.wait_for_function(r"""old => {
      const ids=[...document.querySelectorAll('ytcp-video-row,ytcp-video-row-v2')].map(r=>r.querySelector('a[href*="/edit"]')?.getAttribute('href')?.match(/\/video\/([\w-]{11})\/edit/)?.[1]||'');
      return ids.length && JSON.stringify(ids)!==JSON.stringify(old);
    }""", arg=old, timeout=120_000)
    wait_rows(page)
    return True


def open_bucket(page, channel: str, bucket: str) -> list[dict]:
    page.goto(f"https://studio.youtube.com/channel/{channel}/videos/{bucket}", wait_until="domcontentloaded", timeout=45_000)
    rows = wait_rows(page)
    if not re.match(rf"https://studio\.youtube\.com/channel/{re.escape(channel)}/videos/{re.escape(bucket)}(?:[?#]|$)", page.url):
        raise RuntimeError("Studio opened an unexpected content tab; scan is incomplete")
    return rows


def require_channel(page, config: dict) -> None:
    from youtube_uploader import ensure_logged_in, ensure_target_identity

    ensure_logged_in(page)
    # ytcfg is server-owned channel identity; do not trust the URL alone.
    page.wait_for_function("() => !!window.ytcfg?.get?.('CHANNEL_ID')", timeout=30_000)
    actual = page.evaluate("window.ytcfg.get('CHANNEL_ID')")
    if actual != config["YOUTUBE_TARGET_CHANNEL_ID"]:
        raise RuntimeError(f"Wrong channel: {actual}")
    ensure_target_identity(page, config.get("YOUTUBE_TARGET_CHANNEL", ""), config.get("YOUTUBE_TARGET_EMAIL", ""), actual)


def close_owned_page(page) -> None:
    try:
        if not page.is_closed():
            page.close()
    except Exception:
        pass


def run(config: dict, *, apply: bool, force: bool, data_dir: Path = DATA) -> dict:
    from playwright.sync_api import sync_playwright
    from youtube_remote_status import read_deleted_video_evidence
    from youtube_uploader import discard_studio_video

    data_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (data_dir / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "skipped_worker_busy"}
        state_path = data_dir / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {"videos": {}}
        interval = max(1, int(config.get("YOUTUBE_BLOCKED_CLEANUP_INTERVAL_HOURS", "12")))
        if not force:
            if config.get("YOUTUBE_BLOCKED_CLEANUP_ENABLED", "false").casefold() != "true":
                return {"status": "disabled"}
            if state.get("last_scan_at") and datetime.now(timezone.utc) < datetime.fromisoformat(state["last_scan_at"]) + timedelta(hours=interval):
                return {"status": "not_due"}
        report = {"run_id": uuid.uuid4().hex, "started_at": now(), "channel_id": config["YOUTUBE_TARGET_CHANNEL_ID"],
                  "apply": apply, "status": "scanning", "scan_complete": False, "scanned": 0,
                  "buckets": {}, "candidates": [], "actions": []}
        channel = config["YOUTUBE_TARGET_CHANNEL_ID"]
        owned = []
        try:
            if uploads_busy():
                report["status"] = "skipped_upload_active"
                return report
            with sync_playwright() as playwright, ExitStack() as pages:
                # Never launch another browser, load a persistent profile, or
                # inject saved cookies during this maintenance task.
                browser = playwright.chromium.connect_over_cdp(config["YOUTUBE_CDP_URL"], timeout=15_000)
                if not browser.contexts:
                    raise RuntimeError("The live browser has no authenticated context")
                context = browser.contexts[0]
                if uploads_busy(context):
                    report["status"] = "skipped_upload_active"
                    return report
                page = context.new_page()
                owned.append(page)
                pages.callback(close_owned_page, page)
                page.evaluate("window.name='clipforge-blocked-cleanup'")
                found = {}
                for bucket in BUCKETS:
                    rows = open_bucket(page, channel, bucket)
                    require_channel(page, config)
                    report["buckets"][bucket] = {"scanned": 0, "pages": 0, "complete": False}
                    seen_pages = set()
                    for index in range(100):
                        fingerprint = tuple(row["video_id"] for row in rows)
                        if fingerprint and fingerprint in seen_pages:
                            raise RuntimeError("Studio repeated a page; scan is incomplete")
                        seen_pages.add(fingerprint)
                        report["scanned"] += len(rows)
                        report["buckets"][bucket]["scanned"] += len(rows)
                        report["buckets"][bucket]["pages"] += 1
                        for row in rows:
                            if fully_blocked(row):
                                found[row["video_id"]] = dict(row, bucket=bucket, page_index=index)
                        report["candidates"] = list(found.values())
                        save(data_dir / "latest-scan.json", report)
                        if not rows or not next_page(page, rows):
                            break
                        rows = page.evaluate(ROW_SCRIPT)
                    else:
                        raise RuntimeError("Pagination limit reached; scan is incomplete")
                    report["buckets"][bucket]["complete"] = True
                    report["candidates"] = list(found.values())
                report["candidates"] = list(found.values())
                report["scan_complete"] = True
                save(data_dir / "latest-scan.json", report)
                if apply:
                    limit = max(1, min(20, int(config.get("YOUTUBE_BLOCKED_CLEANUP_MAX_DELETIONS", "5"))))
                    for candidate in report["candidates"][:limit]:
                        video_id = candidate["video_id"]
                        if state["videos"].get(video_id, {}).get("status") == "deleted_verified":
                            continue
                        edit = context.new_page()
                        owned.append(edit)
                        pages.callback(close_owned_page, edit)
                        action = {"video_id": video_id, "title": candidate["title"], "status": "pending_recheck"}
                        report["actions"].append(action)

                        def last_check(expected: str) -> bool:
                            if expected != video_id or uploads_busy(context, owned):
                                return False
                            if f"/video/{video_id}/edit" not in edit.url or not edit.locator("ytcp-video-delete-dialog:visible").count():
                                return False
                            fresh = open_bucket(page, channel, candidate["bucket"])
                            require_channel(page, config)
                            for _ in range(candidate["page_index"]):
                                if not next_page(page, fresh):
                                    return False
                                fresh = page.evaluate(ROW_SCRIPT)
                            match = next((r for r in fresh if r["video_id"] == video_id), None)
                            if not match or not fully_blocked(match) or uploads_busy(context, owned):
                                return False
                            action.update(status="deletion_requested", fresh_evidence=match, requested_at=now())
                            state["videos"][video_id] = dict(action)
                            save(state_path, state)
                            save(data_dir / "latest-scan.json", report)
                            return True

                        try:
                            require_channel(page, config)
                            url = f"https://www.youtube.com/watch?v={video_id}"
                            if discard_studio_video(edit, url, timeout_ms=60_000, before_confirm=last_check):
                                proof = read_deleted_video_evidence(video_id, config["YOUTUBE_CDP_URL"], context=context)
                                if proof and proof.get("deleted_by_uploader") and proof.get("video_id") == video_id:
                                    action.update(status="deleted_verified", deletion_evidence=proof, finished_at=now())
                                else:
                                    action.update(status="delete_confirmation_pending")
                            else:
                                # A late UI timeout cannot prove that a final
                                # confirmation did not reach YouTube.
                                action.update(status="delete_confirmation_pending" if action.get("requested_at") else "not_deleted")
                        except Exception as exc:
                            action.update(status="held", error=str(exc)[:800])
                        finally:
                            state["videos"][video_id] = dict(action)
                            save(state_path, state)
                            if not edit.is_closed():
                                edit.close()
                state["last_scan_at" if apply else "last_readonly_scan_at"] = now()
                save(state_path, state)
                report["status"] = "completed" if apply else "scan_only"
        except Exception as exc:
            report.update(status="held", error=str(exc)[:1200])
        finally:
            # Borrowed Chrome/context must remain alive, including its login.
            report["finished_at"] = now()
            save(data_dir / "latest-scan.json", report)
            save(data_dir / "runs" / (report["run_id"] + ".json"), report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete only fully blocked, freshly rechecked video IDs")
    parser.add_argument("--force", action="store_true", help="Run now, ignoring interval/enable switch")
    args = parser.parse_args()
    result = run(settings(), apply=args.apply, force=args.force)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 1 if result.get("status") == "held" else 0


if __name__ == "__main__":
    raise SystemExit(main())
