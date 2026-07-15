#!/usr/bin/env bash
set -euo pipefail

CHROME_BIN="${CHROME_BIN:-google-chrome}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-9222}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME:-/tmp}/.config}"
DEFAULT_YOUTUBE_LOGIN_PROFILE_DIR="$CONFIG_HOME/clipforge/youtube-chrome-profile"
LEGACY_YOUTUBE_LOGIN_PROFILE_DIR="${LEGACY_YOUTUBE_LOGIN_PROFILE_DIR:-/tmp/clipforge-youtube-login}"
SOURCE_YOUTUBE_LOGIN_PROFILE_DIR="${YOUTUBE_LOGIN_SOURCE_PROFILE_DIR:-${YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR:-$LEGACY_YOUTUBE_LOGIN_PROFILE_DIR}}"
YOUTUBE_LOGIN_PROFILE_DIR="${YOUTUBE_LOGIN_PROFILE_DIR:-$DEFAULT_YOUTUBE_LOGIN_PROFILE_DIR}"
YOUTUBE_LOGIN_PROFILE_DIRECTORY="${YOUTUBE_LOGIN_PROFILE_DIRECTORY:-${YOUTUBE_CHROMIUM_PROFILE_DIRECTORY:-Default}}"
YOUTUBE_REFRESH_LOGIN_PROFILE="${YOUTUBE_REFRESH_LOGIN_PROFILE:-false}"
YOUTUBE_STUDIO_URL="${YOUTUBE_STUDIO_URL:-https://studio.youtube.com}"
YOUTUBE_CHROME_LOG="${YOUTUBE_CHROME_LOG:-/tmp/clipforge-youtube-chrome.log}"
YOUTUBE_CHROME_START_MINIMIZED="${YOUTUBE_CHROME_START_MINIMIZED:-false}"

if [[ "$YOUTUBE_LOGIN_PROFILE_DIR" == "$DEFAULT_YOUTUBE_LOGIN_PROFILE_DIR" \
  && -d "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" \
  && "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" != "$YOUTUBE_LOGIN_PROFILE_DIR" \
  && ( ! -d "$YOUTUBE_LOGIN_PROFILE_DIR" || "$YOUTUBE_REFRESH_LOGIN_PROFILE" == "true" ) ]]; then
  echo "Syncing YouTube Chrome profile from ${SOURCE_YOUTUBE_LOGIN_PROFILE_DIR} to ${YOUTUBE_LOGIN_PROFILE_DIR}..."
  mkdir -p "$(dirname "$YOUTUBE_LOGIN_PROFILE_DIR")"
  rm -rf "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"
  mkdir -p "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"
  rsync -a \
    --exclude='Singleton*' \
    --exclude='*/Singleton*' \
    --exclude='Crashpad/***' \
    --exclude='*/Cache/***' \
    --exclude='*/Code Cache/***' \
    --exclude='*/GPUCache/***' \
    --exclude='*/blob_storage/***' \
    --exclude='ShaderCache/***' \
    --exclude='GrShaderCache/***' \
    "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR"/ \
    "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/
  find "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp" -maxdepth 3 -name 'Singleton*' -delete 2>/dev/null || true
  rm -rf "$YOUTUBE_LOGIN_PROFILE_DIR"
  mv "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp" "$YOUTUBE_LOGIN_PROFILE_DIR"
fi

mkdir -p "$YOUTUBE_LOGIN_PROFILE_DIR" "$(dirname "$YOUTUBE_CHROME_LOG")"

echo "Opening Chrome for YouTube login/sync..."
echo "CDP: http://127.0.0.1:${YOUTUBE_CDP_PORT}"
echo "Profile: ${YOUTUBE_LOGIN_PROFILE_DIR}"
echo "Profile directory: ${YOUTUBE_LOGIN_PROFILE_DIRECTORY}"
echo "Chrome log: ${YOUTUBE_CHROME_LOG}"
chrome_args=(
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port="$YOUTUBE_CDP_PORT"
  --user-data-dir="$YOUTUBE_LOGIN_PROFILE_DIR"
  --profile-directory="$YOUTUBE_LOGIN_PROFILE_DIRECTORY"
  --no-first-run
  --no-default-browser-check
  --disable-dev-shm-usage
  --disable-gpu
  --disable-gpu-compositing
  --disable-features=Vulkan,UseSkiaRenderer,CanvasOopRasterization
  --log-level=3
)
if [[ "$YOUTUBE_CHROME_START_MINIMIZED" == "true" ]]; then
  chrome_args+=(--start-minimized)
fi
echo "Start minimized: ${YOUTUBE_CHROME_START_MINIMIZED}"
echo "Command: ${CHROME_BIN} ${chrome_args[*]} ${YOUTUBE_STUDIO_URL}"

exec "$CHROME_BIN" \
  "${chrome_args[@]}" \
  "$YOUTUBE_STUDIO_URL" \
  2>>"$YOUTUBE_CHROME_LOG"
