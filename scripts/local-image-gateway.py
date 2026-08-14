#!/usr/bin/env python3
"""Serialize local image requests and free Ollama VRAM before forwarding."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


IMAGE_LOCK = threading.Lock()
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def release_ollama(timeout: float = 30.0) -> None:
    root = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]

    def loaded_models() -> list[str]:
        with urllib.request.urlopen(f"{root}/api/ps", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models", []) if isinstance(payload, dict) else []
        return [
            str(item.get("name", "")).strip()
            for item in models
            if isinstance(item, dict) and item.get("name")
        ]

    names = loaded_models()
    for name in names:
        request = urllib.request.Request(
            f"{root}/api/generate",
            data=json.dumps({"model": name, "keep_alive": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()

    deadline = time.monotonic() + timeout
    while names and time.monotonic() < deadline:
        time.sleep(0.5)
        names = loaded_models()
    if names:
        raise RuntimeError("Ollama belum melepaskan VRAM setelah 30 detik")


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream_port = 7861

    def do_GET(self) -> None:  # noqa: N802
        self._forward()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/images/generations"):
            with IMAGE_LOCK:
                try:
                    release_ollama()
                except Exception as exc:
                    self._json_error(503, f"Gagal menyiapkan VRAM GPU: {exc}")
                    return
                self._forward()
            return
        self._forward()

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.casefold() not in HOP_HEADERS and name.casefold() != "host"
        }
        connection = http.client.HTTPConnection("127.0.0.1", self.upstream_port, timeout=1800)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.casefold() not in HOP_HEADERS and name.casefold() != "content-length":
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self._json_error(502, f"Generator gambar lokal tidak tersedia: {exc}")
        finally:
            connection.close()

    def _json_error(self, status: int, message: str) -> None:
        payload = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[local-image-gateway] {self.address_string()} {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-port", type=int, default=7860)
    parser.add_argument("--upstream-port", type=int, default=7861)
    args = parser.parse_args()
    GatewayHandler.upstream_port = args.upstream_port
    server = ThreadingHTTPServer(("127.0.0.1", args.listen_port), GatewayHandler)
    print(
        f"[local-image-gateway] listening on 127.0.0.1:{args.listen_port}, "
        f"upstream 127.0.0.1:{args.upstream_port}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
