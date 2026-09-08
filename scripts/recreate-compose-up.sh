#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/load-dotenv.sh"
load_dotenv "$ROOT_DIR/.env"

"$ROOT_DIR/scripts/prepare-youtube-gui-runtime.sh" --start-watcher

YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-}"
if [[ -z "$YOUTUBE_CDP_PORT" && "${YOUTUBE_CDP_URL:-}" =~ :([0-9]+)(/.*)?$ ]]; then
  YOUTUBE_CDP_PORT="${BASH_REMATCH[1]}"
fi
YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-9222}"
TIKTOK_CDP_PORT="${TIKTOK_CDP_PORT:-}"
if [[ -z "$TIKTOK_CDP_PORT" && "${TIKTOK_CDP_URL:-}" =~ :([0-9]+)(/.*)?$ ]]; then
  TIKTOK_CDP_PORT="${BASH_REMATCH[1]}"
fi
TIKTOK_CDP_PORT="${TIKTOK_CDP_PORT:-9444}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME:-/tmp}/.config}"
YOUTUBE_LOGIN_PROFILE_DIR="${YOUTUBE_LOGIN_PROFILE_DIR:-$CONFIG_HOME/fendy-clipper/youtube-chrome-profile}"
YOUTUBE_CHROME_LAUNCH_LOG="${YOUTUBE_CHROME_LAUNCH_LOG:-/tmp/fendy-clipper-youtube-chrome-launcher.log}"
TIKTOK_HOST_PROFILE_DIR="${TIKTOK_HOST_PROFILE_DIR:-$CONFIG_HOME/fendy-clipper/tiktok-chrome-profile}"
TIKTOK_HOST_CHROME_LAUNCH_LOG="${TIKTOK_HOST_CHROME_LAUNCH_LOG:-/tmp/fendy-clipper-tiktok-chrome-launcher.log}"
TIKTOK_UPLOAD_USE_CDP="${TIKTOK_UPLOAD_USE_CDP:-true}"
TIKTOK_CLOSE_CDP_AFTER_LOGIN="${TIKTOK_CLOSE_CDP_AFTER_LOGIN:-false}"
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
  local port="$1"
  local deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    if python - "$port" >/dev/null 2>&1 <<'PY'
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

wait_for_backend() {
  local deadline=$((SECONDS + 90))
  while (( SECONDS < deadline )); do
    if curl -fsS --max-time 2 http://127.0.0.1:8010/api/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

tiktok_saved_session_ready() {
  python - <<'PY' >/dev/null 2>&1
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8010/api/tiktok/config", timeout=5) as response:
    payload = json.load(response)
if not payload.get("auth_state_exists"):
    raise SystemExit(1)
PY
}

if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  # Some deployments still provide the standalone Compose binary. Selecting it
  # explicitly avoids `docker: unknown command: docker compose` during rebuild.
  compose_cmd=(docker-compose)
else
  echo "Docker Compose tidak ditemukan (plugin 'docker compose' atau binary 'docker-compose')." >&2
  exit 1
fi

privilege_cmd=()
if ! docker info >/dev/null 2>&1; then
  privilege_cmd=(sudo)
  compose_cmd=(sudo "${compose_cmd[@]}")
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

if ! wait_for_cdp "$YOUTUBE_CDP_PORT"; then
  echo "Chrome remote debugging is not responding on http://127.0.0.1:${YOUTUBE_CDP_PORT}." >&2
  echo "Open the launcher log for the exact cause: ${YOUTUBE_CHROME_LAUNCH_LOG}" >&2
  echo "Last launcher log lines:" >&2
  tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
  exit 1
fi
echo "Chrome remote debugging ready on http://127.0.0.1:${YOUTUBE_CDP_PORT}."

"${compose_cmd[@]}" --env-file .env up -d --build --force-recreate backend telegram-bot frontend

if ! wait_for_cdp "$YOUTUBE_CDP_PORT"; then
  echo "Chrome remote debugging stopped after containers were recreated." >&2
  echo "Last launcher log lines:" >&2
  tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
  exit 1
fi
echo "Chrome remote debugging still ready after container recreate."

if ! wait_for_backend; then
  echo "Backend ClipForge tidak siap di http://127.0.0.1:8010 setelah container dibuat ulang." >&2
  exit 1
fi
echo "Backend ClipForge ready on http://127.0.0.1:8010."

# The saved storage-state lives in ./backend/data, so it survives a container
# recreate. Keep the already-authenticated dedicated host Chrome minimized and
# reuse it over CDP; never start the login flow again merely because containers
# were recreated.
if tiktok_saved_session_ready; then
  if [[ "$TIKTOK_UPLOAD_USE_CDP" == "true" ]] \
    && ! pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" >/dev/null 2>&1; then
    echo "Menjalankan kembali profile TikTok yang sudah login dalam keadaan minimized..."
    TIKTOK_CHROMIUM_USER_DATA_DIR="$TIKTOK_HOST_PROFILE_DIR" \
      TIKTOK_LOGIN_URL=https://www.tiktok.com/tiktokstudio/upload \
      TIKTOK_CHROME_BACKGROUND=false \
      TIKTOK_CHROME_MINIMIZED=true \
      nohup "$ROOT_DIR/scripts/open-tiktok-login-chrome.sh" \
      >>"$TIKTOK_HOST_CHROME_LAUNCH_LOG" 2>&1 &
    if ! wait_for_cdp "$TIKTOK_CDP_PORT"; then
      echo "Profile TikTok tersimpan ada, tetapi Chrome background gagal dimulai." >&2
      tail -40 "$TIKTOK_HOST_CHROME_LAUNCH_LOG" >&2 || true
      exit 1
    fi
  elif [[ "$TIKTOK_UPLOAD_USE_CDP" != "true" && "$TIKTOK_CLOSE_CDP_AFTER_LOGIN" == "true" ]] \
    && pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" >/dev/null 2>&1; then
    echo "Menutup Chrome login TikTok lama; session sudah tersimpan."
    pkill -f "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" || true
  fi
  echo "Session TikTok tersimpan ditemukan; tidak login ulang. Browser khusus tetap minimized di background."
else
  # TikTok login must use the user's regular host Chrome. Start it minimized so
  # the user only restores it when manual login/CAPTCHA is required.
  tiktok_host_cdp="$(pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}" || true)"
  if [[ -n "$tiktok_host_cdp" ]] && ! grep -F -- "$TIKTOK_HOST_PROFILE_DIR" <<<"$tiktok_host_cdp" >/dev/null; then
    echo "Stopping old container/foreign TikTok Chrome on CDP port ${TIKTOK_CDP_PORT}..."
    "${privilege_cmd[@]}" pkill -f "remote-debugging-port=${TIKTOK_CDP_PORT}" || true
    sleep 2
  fi

  if pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" >/dev/null 2>&1; then
    echo "TikTok host Chrome already running on CDP port ${TIKTOK_CDP_PORT}."
  else
    echo "Session TikTok belum tersedia; membuka Chrome login dalam keadaan minimized..."
    TIKTOK_CHROMIUM_USER_DATA_DIR="$TIKTOK_HOST_PROFILE_DIR" \
      TIKTOK_CHROME_BACKGROUND=false \
      TIKTOK_CHROME_MINIMIZED=true \
      nohup "$ROOT_DIR/scripts/open-tiktok-login-chrome.sh" \
      >>"$TIKTOK_HOST_CHROME_LAUNCH_LOG" 2>&1 &
    echo "TikTok host Chrome launcher log: ${TIKTOK_HOST_CHROME_LAUNCH_LOG}"
  fi

  if ! wait_for_cdp "$TIKTOK_CDP_PORT"; then
    echo "Chrome host TikTok tidak merespons di http://127.0.0.1:${TIKTOK_CDP_PORT}." >&2
    tail -40 "$TIKTOK_HOST_CHROME_LAUNCH_LOG" >&2 || true
    exit 1
  fi
  if ! curl -fsS --max-time 10 -X POST http://127.0.0.1:8010/api/tiktok/login/start >/dev/null; then
    echo "Backend gagal memulai browser TikTok login/Studio." >&2
    exit 1
  fi
  echo "Chrome login TikTok siap dalam keadaan minimized. Buka hanya jika login/CAPTCHA diperlukan."
fi

if [[ "$WATCH_CHROME" == "true" ]]; then
  echo "Watching Chrome remote debugging. Press Ctrl+C to stop watching; Chrome window stays open."
  while true; do
    if ! wait_for_cdp "$YOUTUBE_CDP_PORT"; then
      echo "Chrome remote debugging stopped responding on http://127.0.0.1:${YOUTUBE_CDP_PORT}." >&2
      tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
      exit 1
    fi
    sleep 10
  done
fi
