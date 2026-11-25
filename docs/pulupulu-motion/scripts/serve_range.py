"""Static file server with HTTP Range support, for handing a large finished film to a person.

`python -m http.server` answers a Range request with 200 and the entire file, so a browser player cannot
seek and a phone will not stream it. This answers 206 with the requested slice, so the file plays and scrubs
over a tunnel instead of only downloading. It also serves `index.html` at `/` and honours `?dl=1` with
`Content-Disposition: attachment`, which is the only way a phone gets a real save (see
`references/delivery-and-transfers.md` §2b).

Usage:
    python serve_range.py <dir> [port] [bind]        # default 8899 on 127.0.0.1

Then, for a public link:
    cloudflared tunnel --url http://127.0.0.1:8899 --no-autoupdate > tunnel.log 2>&1
    grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" tunnel.log | head -1

Verify what you are about to hand over (do not skip this):
    curl -sI -H "Range: bytes=0-1023" "$URL/film.mp4" | head -3      # expect 206, not 200
    curl -sI "$URL/film.mp4?dl=1" | grep -i content-disposition       # expect attachment
    curl -s -r 0-15 "$URL/film.mp4" | xxd | head -1                  # expect the 'ftyp' box
    curl -s -r 40000000-40001023 "$URL/film.mp4" | sha256sum        # must match the same slice on disk
    curl -s "$URL/" | grep -c 'download'                             # the button is really on the page
"""
import os
import pathlib
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8899
BIND = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"

MIME = {".mp4": "video/mp4", ".webm": "video/webm", ".wav": "audio/wav", ".mp3": "audio/mpeg",
        ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp",
        ".md": "text/markdown; charset=utf-8", ".html": "text/html; charset=utf-8",
        ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _resolve(self):
        rel = self.path.split("?")[0].lstrip("/")
        if rel == "":
            rel = "index.html"          # "/" must land on the hand-over page, not a 404
        p = (ROOT / rel).resolve()
        if not str(p).startswith(str(ROOT)):      # no escaping the served root
            return None
        return p if p.is_file() else None

    def do_HEAD(self):
        self._send(head_only=True)

    def do_GET(self):
        self._send(head_only=False)

    def _send(self, head_only=False):
        p = self._resolve()
        if p is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        size = p.stat().st_size
        ctype = MIME.get(p.suffix.lower(), "application/octet-stream")
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if m:
                a, b = m.group(1), m.group(2)
                if a:
                    start = int(a)
                    end = int(b) if b else size - 1
                elif b:                            # suffix range: the last N bytes
                    start = max(0, size - int(b))
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
        length = end - start + 1
        # A browser ignores the HTML `download` attribute for cross-origin media, so a phone offers
        # no way to save the file. `?dl=1` makes the server ask for the save instead.
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        force_dl = "dl=1" in query
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        if force_dl:
            self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only:
            return
        with p.open("rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(256 * 1024, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    os.chdir(ROOT)
    print(f"serving {ROOT} on http://{BIND}:{PORT}", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
