"""Read-only evidence for releasing reservations of deleted remote videos."""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import Cookie, CookieJar
import json
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


class _PlayerResponseParser(HTMLParser):
    """Read inline player JSON without executing scripts or loading media."""

    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts.append(data)


def _player_response(html: str) -> dict | None:
    parser = _PlayerResponseParser()
    parser.feed(html)
    assignment = re.compile(
        r'''(?:\bytInitialPlayerResponse|\bwindow\s*\[\s*["']ytInitialPlayerResponse["']\s*\])\s*=\s*'''
    )
    for script in parser.scripts:
        for match in assignment.finditer(script):
            try:
                value, _ = json.JSONDecoder().raw_decode(script[match.end():])
            except ValueError:
                continue
            if isinstance(value, dict) and isinstance(value.get("playabilityStatus"), dict):
                return value
    return None


def _fetch_player_response(context, video_id: str) -> dict | None:
    url = f"https://www.youtube.com/watch?v={video_id}&autoplay=0"
    # Use an independent cookie jar. Set-Cookie responses must never change
    # the user's live Chrome login; domain/path scoping also survives redirects.
    jar = CookieJar()
    for cookie in context.cookies([url]):
        domain = cookie["domain"]
        expires = cookie.get("expires", -1)
        jar.set_cookie(Cookie(
            version=0, name=cookie["name"], value=cookie["value"],
            port=None, port_specified=False, domain=domain,
            domain_specified=domain.startswith("."), domain_initial_dot=domain.startswith("."),
            path=cookie.get("path", "/"), path_specified=True,
            secure=cookie.get("secure", False), expires=int(expires) if expires > 0 else None,
            discard=expires <= 0, comment=None, comment_url=None, rest={},
        ))
    opener = build_opener(HTTPCookieProcessor(jar))
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
    with opener.open(request, timeout=20) as result:
        final_url = urlparse(result.geturl())
        if (result.status != 200 or final_url.scheme != "https"
                or final_url.hostname != "www.youtube.com" or final_url.path != "/watch"
                or parse_qs(final_url.query).get("v") != [video_id]):
            return None
        # A changed/oversized HTML response is unknown, never deletion evidence.
        body = result.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            return None
        response = _player_response(body.decode("utf-8", errors="replace"))
        details = response.get("videoDetails", {}) if response else {}
        if details.get("videoId", video_id) != video_id:
            return None
        return response


def uploader_deleted_video(response: dict) -> str | None:
    status = response.get("playabilityStatus")
    if not isinstance(status, dict) or status.get("status") != "ERROR":
        return None

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    for value in strings(status.get("errorScreen", {})):
        if value.strip().casefold() in {
            "video ini telah dihapus oleh uploader",
            "this video has been removed by the uploader",
        }:
            return value.strip()
    return None


def read_deleted_video_evidence(video_id: str, cdp_url: str, *, context=None) -> dict | None:
    """Read playability over HTTP using a snapshot of Chrome's cookies.

    Private videos, unavailable videos, login failures, timeouts, and claims
    are not evidence of deletion. Never choose a file or edit Studio metadata.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None

    def read_from_context(existing_context):
        response = _fetch_player_response(existing_context, video_id)
        reason = uploader_deleted_video(response) if isinstance(response, dict) else None
        if not reason:
            return None
        return {
            "video_id": video_id, "deleted_by_uploader": True,
            "reason": reason, "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    if context is not None:
        return read_from_context(context)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, no_defaults=True, timeout=10_000)
        if not browser.contexts:
            return None
        return read_from_context(browser.contexts[0])
