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

YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-9222}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME:-/tmp}/.config}"
YOUTUBE_LOGIN_PROFILE_DIR="${YOUTUBE_LOGIN_PROFILE_DIR:-$CONFIG_HOME/clipforge/youtube-chrome-profile}"
YOUTUBE_CHROME_LAUNCH_LOG="${YOUTUBE_CHROME_LAUNCH_LOG:-/tmp/clipforge-youtube-chrome-launcher.log}"
DOWN_FIRST=false
WATCH_CHROME=false
RESET_PROFILE=false

for arg in "$@"; do
  case "$arg" in
    --down-first)
      DOWN_FIRST=true
      ;;
    --watch-chrome)
      WATCH_CHROME=true
      ;;
    --reset-profile)
      RESET_PROFILE=true
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--down-first] [--watch-chrome] [--reset-profile]" >&2
      exit 2
      ;;
  esac
done

wait_for_cdp() {
  local deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    if python - "$YOUTUBE_CDP_PORT" >/dev/null 2>&1 <<'PY'
import json
import sys
import urllib.request

port = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if not payload.get("webSocketDebuggerUrl"):
    raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

compose_cmd=(docker compose)
if ! docker info >/dev/null 2>&1; then
  compose_cmd=(sudo docker compose)
fi

if [[ "$DOWN_FIRST" == "true" ]]; then
  "${compose_cmd[@]}" --env-file .env down
fi

if [[ "$RESET_PROFILE" == "true" ]]; then
  if [[ -z "$YOUTUBE_LOGIN_PROFILE_DIR" || "$YOUTUBE_LOGIN_PROFILE_DIR" == "/" || "$YOUTUBE_LOGIN_PROFILE_DIR" == "$HOME" ]]; then
    echo "Refusing to reset unsafe profile path: ${YOUTUBE_LOGIN_PROFILE_DIR}" >&2
    exit 2
  fi
  echo "Resetting YouTube Chrome CDP profile: ${YOUTUBE_LOGIN_PROFILE_DIR}"
  pkill -f "remote-debugging-port=${YOUTUBE_CDP_PORT}" || true
  sleep 2
  rm -rf "$YOUTUBE_LOGIN_PROFILE_DIR"
fi

existing_cdp="$(pgrep -af "remote-debugging-port=${YOUTUBE_CDP_PORT}" || true)"
if [[ -n "$existing_cdp" ]] && ! grep -F -- "$YOUTUBE_LOGIN_PROFILE_DIR" <<<"$existing_cdp" >/dev/null; then
  echo "Stopping old YouTube Chrome CDP on port ${YOUTUBE_CDP_PORT} because it uses a different profile..."
  pkill -f "remote-debugging-port=${YOUTUBE_CDP_PORT}" || true
  sleep 2
fi

if pgrep -af "remote-debugging-port=${YOUTUBE_CDP_PORT}.*${YOUTUBE_LOGIN_PROFILE_DIR}" >/dev/null 2>&1; then
  echo "YouTube login Chrome already running on CDP port ${YOUTUBE_CDP_PORT}."
else
  echo "Starting YouTube login Chrome in background..."
  nohup "$ROOT_DIR/scripts/open-youtube-login-chrome.sh" >>"$YOUTUBE_CHROME_LAUNCH_LOG" 2>&1 &
  echo "YouTube login Chrome launcher log: ${YOUTUBE_CHROME_LAUNCH_LOG}"
fi

if ! wait_for_cdp; then
  echo "Chrome remote debugging is not responding on http://127.0.0.1:${YOUTUBE_CDP_PORT}." >&2
  echo "Open the launcher log for the exact cause: ${YOUTUBE_CHROME_LAUNCH_LOG}" >&2
  echo "Last launcher log lines:" >&2
  tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
  exit 1
fi
echo "Chrome remote debugging ready on http://127.0.0.1:${YOUTUBE_CDP_PORT}."

"${compose_cmd[@]}" --env-file .env up -d --build --force-recreate backend telegram-bot frontend

if ! wait_for_cdp; then
  echo "Chrome remote debugging stopped after containers were recreated." >&2
  echo "Last launcher log lines:" >&2
  tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
  exit 1
fi
echo "Chrome remote debugging still ready after container recreate."

if [[ "$WATCH_CHROME" == "true" ]]; then
  echo "Watching Chrome remote debugging. Press Ctrl+C to stop watching; Chrome window stays open."
  while true; do
    if ! wait_for_cdp; then
      echo "Chrome remote debugging stopped responding on http://127.0.0.1:${YOUTUBE_CDP_PORT}." >&2
      tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
      exit 1
    fi
    sleep 10
  done
fi
