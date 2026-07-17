#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.request
from pathlib import Path

import websocket


def cdp_request(socket: websocket.WebSocket, request_id: int, method: str) -> dict:
    socket.send(json.dumps({"id": request_id, "method": method}))
    while True:
        payload = json.loads(socket.recv())
        if payload.get("id") == request_id:
            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            return payload.get("result") or {}


def playwright_cookie(cookie: dict) -> dict:
    same_site = cookie.get("sameSite")
    if same_site not in {"Strict", "Lax", "None"}:
        same_site = "Lax"
    return {
        "name": str(cookie.get("name") or ""),
        "value": str(cookie.get("value") or ""),
        "domain": str(cookie.get("domain") or ""),
        "path": str(cookie.get("path") or "/"),
        "expires": float(cookie.get("expires") or -1),
        "httpOnly": bool(cookie.get("httpOnly")),
        "secure": bool(cookie.get("secure")),
        "sameSite": same_site,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Chrome CDP cookies as Playwright storage-state.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9333")
    parser.add_argument("--state", required=True)
    args = parser.parse_args()

    version_url = f"{args.cdp_url.rstrip('/')}/json/version"
    with urllib.request.urlopen(version_url, timeout=10) as response:
        version = json.load(response)
    web_socket_url = str(version.get("webSocketDebuggerUrl") or "")
    if not web_socket_url:
        raise RuntimeError(f"Chrome CDP tidak siap di {args.cdp_url}")

    socket = websocket.create_connection(web_socket_url, origin=args.cdp_url, timeout=15)
    try:
        cookies = cdp_request(socket, 1, "Storage.getCookies").get("cookies") or []
    finally:
        socket.close()

    youtube_cookies = [
        cookie
        for cookie in cookies
        if "youtube" in str(cookie.get("domain") or "").lower()
        or "google" in str(cookie.get("domain") or "").lower()
    ]
    if not youtube_cookies:
        raise RuntimeError("Chrome tidak memiliki cookie Google/YouTube; login belum selesai")

    state_path = Path(args.state).expanduser().resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {"cookies": [playwright_cookie(cookie) for cookie in cookies], "origins": []}
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{state_path.name}.", dir=state_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(state, temporary_file, ensure_ascii=True, separators=(",", ":"))
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

    print(
        f"Storage-state tersimpan: {state_path} "
        f"({len(youtube_cookies)} cookie Google/YouTube dari {len(cookies)} total)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
