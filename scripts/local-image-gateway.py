#!/usr/bin/env python3
"""Serialize local image requests and free Ollama VRAM before forwarding."""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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
    upscaler_binary = ""
    upscaler_model_dir = ""
    upscaler_scale = 4
    upscaler_tile_size = 128
    upscaler_gpu_id = 0

    @staticmethod
    def _upscale_preserves_layout(input_path: Path, output_path: Path, scale: int) -> tuple[bool, float]:
        """Reject tiled output whose patches no longer match the source layout."""
        from PIL import Image
        import numpy as np

        with Image.open(input_path) as source_image, Image.open(output_path) as output_image:
            expected_size = (source_image.width * scale, source_image.height * scale)
            if output_image.size != expected_size:
                return False, 0.0
            source = np.asarray(source_image.convert("L"), dtype=np.float32)
            reduced = np.asarray(
                output_image.convert("L").resize(source_image.size, Image.Resampling.LANCZOS),
                dtype=np.float32,
            )
        source_flat = source.ravel()
        reduced_flat = reduced.ravel()
        if float(source_flat.std()) < 1.0 or float(reduced_flat.std()) < 1.0:
            normalized_mae = float(np.mean(np.abs(source_flat - reduced_flat)) / 255.0)
            score = max(0.0, 1.0 - normalized_mae)
        else:
            score = float(np.corrcoef(source_flat, reduced_flat)[0, 1])
        return bool(np.isfinite(score) and score >= 0.82), score

    @staticmethod
    def _strengthen_generation_request(body: bytes | None) -> bytes | None:
        if not body:
            return body
        try:
            parsed = json.loads(body.decode("utf-8"))
            if not isinstance(parsed, dict):
                return body
            prompt = str(parsed.get("prompt") or "").strip()
            no_human_scene = "visible human limit: 0" in prompt.casefold()
            if no_human_scene:
                prompt_guard = (
                    " STRICT SUBJECT INTEGRITY: preserve the requested non-human subject, action, count, props, "
                    "location, and immutable global visual style. Keep the frame free of unrequested human figures "
                    "and body parts."
                )
                negative_guard = (
                    "unrequested human, human face, human silhouette, human body part, stock presenter, unrelated character"
                )
            else:
                prompt_guard = (
                    " STRICT SUBJECT INTEGRITY: show only explicitly requested people. Every visible hand must be "
                    "anatomically attached through a visible wrist and forearm to a clearly visible owner. Keep all "
                    "hands away from frame edges. Never add anonymous foreground hands, partial people, background "
                    "extras, floating limbs, or body parts entering from outside the frame."
                )
                negative_guard = (
                    "disembodied hands, floating hands, detached hands, bodyless limbs, cropped arms, cropped wrists, "
                    "hands entering from frame edge, anonymous foreground hands, partial person, unrequested crowd, "
                    "extra background people"
                )
            if prompt_guard.strip() not in prompt:
                parsed["prompt"] = f"{prompt}{prompt_guard}".strip()
            negative = str(parsed.get("negative_prompt") or "").strip(" ,")
            if negative_guard.split(",", 1)[0].casefold() not in negative.casefold():
                parsed["negative_prompt"] = f"{negative}, {negative_guard}".strip(" ,")
            return json.dumps(parsed, separators=(",", ":")).encode("utf-8")
        except Exception as exc:
            print(f"[local-image-gateway] Prompt guard dilewati: {exc}", flush=True)
            return body

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
                self._forward(enhance_images=True)
            return
        self._forward()

    @classmethod
    def _enhance_generation_payload(cls, payload: bytes) -> bytes:
        if not cls.upscaler_binary or not cls.upscaler_model_dir:
            return payload
        try:
            parsed = json.loads(payload.decode("utf-8"))
            images = parsed.get("data") if isinstance(parsed, dict) else None
            if not isinstance(images, list):
                return payload
            with tempfile.TemporaryDirectory(prefix="clipforge-upscale-") as tmp:
                work_dir = Path(tmp)
                for index, item in enumerate(images):
                    encoded = item.get("b64_json") if isinstance(item, dict) else None
                    if not isinstance(encoded, str) or not encoded:
                        continue
                    input_path = work_dir / f"input-{index}.png"
                    output_path = work_dir / f"output-{index}.png"
                    input_path.write_bytes(base64.b64decode(encoded, validate=True))
                    result = subprocess.run(
                        [
                            cls.upscaler_binary,
                            "-i",
                            str(input_path),
                            "-o",
                            str(output_path),
                            "-m",
                            cls.upscaler_model_dir,
                            "-n",
                            "realesrgan-x4plus",
                            "-s",
                            str(cls.upscaler_scale),
                            "-t",
                            str(cls.upscaler_tile_size),
                            "-g",
                            str(cls.upscaler_gpu_id),
                            "-j",
                            "1:2:2",
                            "-f",
                            "png",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=900,
                        check=False,
                    )
                    if result.returncode != 0 or not output_path.is_file():
                        detail = (result.stderr or result.stdout or "unknown error")[-1200:]
                        raise RuntimeError(f"Real-ESRGAN gagal: {detail}")
                    layout_ok, layout_score = cls._upscale_preserves_layout(
                        input_path, output_path, cls.upscaler_scale
                    )
                    if not layout_ok:
                        raise RuntimeError(
                            "Real-ESRGAN menghasilkan tile/puzzle tidak valid "
                            f"(layout score {layout_score:.3f})"
                        )
                    print(
                        f"[local-image-gateway] Real-ESRGAN x4 lolos layout gate "
                        f"(score {layout_score:.3f})",
                        flush=True,
                    )
                    item["b64_json"] = base64.b64encode(output_path.read_bytes()).decode("ascii")
            return json.dumps(parsed, separators=(",", ":")).encode("utf-8")
        except Exception as exc:
            # Upscaling is a quality enhancement. Preserve a valid generated
            # image instead of failing the entire Long Animate job.
            print(f"[local-image-gateway] Real-ESRGAN dilewati: {exc}", flush=True)
            return payload

    def _forward(self, enhance_images: bool = False) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        if enhance_images:
            body = self._strengthen_generation_request(body)
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.casefold() not in HOP_HEADERS and name.casefold() != "host"
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
        connection = http.client.HTTPConnection("127.0.0.1", self.upstream_port, timeout=1800)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            if enhance_images and 200 <= response.status < 300:
                payload = self._enhance_generation_payload(payload)
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
    parser.add_argument("--upscaler-binary", default="")
    parser.add_argument("--upscaler-model-dir", default="")
    parser.add_argument("--upscaler-scale", type=int, default=4)
    parser.add_argument("--upscaler-tile-size", type=int, default=128)
    parser.add_argument("--upscaler-gpu-id", type=int, default=0)
    args = parser.parse_args()
    GatewayHandler.upstream_port = args.upstream_port
    GatewayHandler.upscaler_binary = args.upscaler_binary
    GatewayHandler.upscaler_model_dir = args.upscaler_model_dir
    # realesrgan-x4plus must run at its native x4 scale. Forcing x2 causes
    # independently enlarged tiles to be stitched as a visible puzzle.
    GatewayHandler.upscaler_scale = 4
    if args.upscaler_scale != 4:
        print(
            f"[local-image-gateway] scale {args.upscaler_scale} ditolak; "
            "realesrgan-x4plus dikunci ke native x4",
            flush=True,
        )
    GatewayHandler.upscaler_tile_size = max(32, args.upscaler_tile_size)
    GatewayHandler.upscaler_gpu_id = max(0, args.upscaler_gpu_id)
    server = ThreadingHTTPServer(("127.0.0.1", args.listen_port), GatewayHandler)
    print(
        f"[local-image-gateway] listening on 127.0.0.1:{args.listen_port}, "
        f"upstream 127.0.0.1:{args.upstream_port}, "
        f"Real-ESRGAN={'aktif' if args.upscaler_binary else 'nonaktif'}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
