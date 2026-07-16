#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

YOUTUBE_CDP_URL="${YOUTUBE_CDP_URL:-http://127.0.0.1:9222}"
YOUTUBE_CHROME_LOG="${YOUTUBE_CHROME_LOG:-/tmp/clipforge-youtube-chrome.log}"
YOUTUBE_CHROME_LAUNCH_LOG="${YOUTUBE_CHROME_LAUNCH_LOG:-/tmp/clipforge-youtube-chrome-cli-launcher.log}"

mkdir -p "$(dirname "$YOUTUBE_CHROME_LOG")" "$(dirname "$YOUTUBE_CHROME_LAUNCH_LOG")"
touch "$YOUTUBE_CHROME_LOG" "$YOUTUBE_CHROME_LAUNCH_LOG"

cdp_ready() {
  python3 - "$YOUTUBE_CDP_URL" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

url = sys.argv[1].rstrip("/") + "/json/version"
with urllib.request.urlopen(url, timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if not payload.get("webSocketDebuggerUrl"):
    raise SystemExit(1)
PY
}

echo "Starting ClipForge YouTube Chrome CDP..."
echo "CDP URL      : $YOUTUBE_CDP_URL"
echo "Chrome log   : $YOUTUBE_CHROME_LOG"
echo "Launcher log : $YOUTUBE_CHROME_LAUNCH_LOG"
echo

"$ROOT_DIR/scripts/open-youtube-login-chrome.sh" --headed --background --no-minimized "$@" 2>&1 | tee -a "$YOUTUBE_CHROME_LAUNCH_LOG"

echo
echo "Waiting for Chrome CDP readiness..."
for attempt in $(seq 1 60); do
  if cdp_ready; then
    echo "Chrome CDP READY at $YOUTUBE_CDP_URL"
    break
  fi
  if [[ "$attempt" == "60" ]]; then
    echo "Chrome CDP is not ready yet after 60 seconds."
    echo "Keep this terminal open and check the logs below."
    break
  fi
  sleep 1
done

echo
echo "Keep this terminal open while uploading to YouTube."
echo "After the Studio window is logged in, click Sync CDP or Retry YouTube in the dashboard."
echo "Press Ctrl+C only when you want to stop watching logs. Chrome may keep running."
echo
tail -n 80 -F "$YOUTUBE_CHROME_LAUNCH_LOG" "$YOUTUBE_CHROME_LOG"
