#!/usr/bin/env bash
set -euo pipefail

CHROME_BIN="${CHROME_BIN:-google-chrome}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-}"
ENV_YOUTUBE_CDP_URL="${YOUTUBE_CDP_URL:-}"
ENV_YOUTUBE_LOGIN_SOURCE_PROFILE_DIR="${YOUTUBE_LOGIN_SOURCE_PROFILE_DIR:-}"
ENV_YOUTUBE_LOGIN_PROFILE_DIR="${YOUTUBE_LOGIN_PROFILE_DIR:-}"
ENV_YOUTUBE_LOGIN_PROFILE_DIRECTORY="${YOUTUBE_LOGIN_PROFILE_DIRECTORY:-}"
ENV_YOUTUBE_REFRESH_LOGIN_PROFILE="${YOUTUBE_REFRESH_LOGIN_PROFILE:-}"
ENV_YOUTUBE_CHROME_HEADLESS="${YOUTUBE_CHROME_HEADLESS:-}"
ENV_YOUTUBE_CHROME_START_MINIMIZED="${YOUTUBE_CHROME_START_MINIMIZED:-}"
ENV_YOUTUBE_CHROME_BACKGROUND="${YOUTUBE_CHROME_BACKGROUND:-}"
CLI_YOUTUBE_CHROME_HEADLESS=""
CLI_YOUTUBE_CHROME_START_MINIMIZED=""
CLI_YOUTUBE_CHROME_BACKGROUND=""
CLI_YOUTUBE_USE_DESKTOP_PROFILE="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --headed)
      CLI_YOUTUBE_CHROME_HEADLESS="false"
      CLI_YOUTUBE_CHROME_START_MINIMIZED="false"
      ;;
    --headless)
      CLI_YOUTUBE_CHROME_HEADLESS="true"
      ;;
    --background)
      CLI_YOUTUBE_CHROME_BACKGROUND="true"
      ;;
    --foreground)
      CLI_YOUTUBE_CHROME_BACKGROUND="false"
      ;;
    --minimized)
      CLI_YOUTUBE_CHROME_START_MINIMIZED="true"
      ;;
    --no-minimized)
      CLI_YOUTUBE_CHROME_START_MINIMIZED="false"
      ;;
    --desktop-profile)
      CLI_YOUTUBE_USE_DESKTOP_PROFILE="true"
      CLI_YOUTUBE_CHROME_HEADLESS="false"
      CLI_YOUTUBE_CHROME_START_MINIMIZED="false"
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/open-youtube-login-chrome.sh [--headed|--headless] [--background|--foreground] [--minimized|--no-minimized] [--desktop-profile]

Examples:
  scripts/open-youtube-login-chrome.sh --headed --background
  scripts/open-youtube-login-chrome.sh --desktop-profile --background
  scripts/open-youtube-login-chrome.sh --headless --background
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
[[ -n "$ENV_YOUTUBE_CDP_PORT" ]] && YOUTUBE_CDP_PORT="$ENV_YOUTUBE_CDP_PORT"
[[ -n "$ENV_YOUTUBE_CDP_URL" ]] && YOUTUBE_CDP_URL="$ENV_YOUTUBE_CDP_URL"
[[ -n "$ENV_YOUTUBE_LOGIN_SOURCE_PROFILE_DIR" ]] && YOUTUBE_LOGIN_SOURCE_PROFILE_DIR="$ENV_YOUTUBE_LOGIN_SOURCE_PROFILE_DIR"
[[ -n "$ENV_YOUTUBE_LOGIN_PROFILE_DIR" ]] && YOUTUBE_LOGIN_PROFILE_DIR="$ENV_YOUTUBE_LOGIN_PROFILE_DIR"
[[ -n "$ENV_YOUTUBE_LOGIN_PROFILE_DIRECTORY" ]] && YOUTUBE_LOGIN_PROFILE_DIRECTORY="$ENV_YOUTUBE_LOGIN_PROFILE_DIRECTORY"
[[ -n "$ENV_YOUTUBE_REFRESH_LOGIN_PROFILE" ]] && YOUTUBE_REFRESH_LOGIN_PROFILE="$ENV_YOUTUBE_REFRESH_LOGIN_PROFILE"
[[ -n "$ENV_YOUTUBE_CHROME_HEADLESS" ]] && YOUTUBE_CHROME_HEADLESS="$ENV_YOUTUBE_CHROME_HEADLESS"
[[ -n "$ENV_YOUTUBE_CHROME_START_MINIMIZED" ]] && YOUTUBE_CHROME_START_MINIMIZED="$ENV_YOUTUBE_CHROME_START_MINIMIZED"
[[ -n "$ENV_YOUTUBE_CHROME_BACKGROUND" ]] && YOUTUBE_CHROME_BACKGROUND="$ENV_YOUTUBE_CHROME_BACKGROUND"
[[ -n "$CLI_YOUTUBE_CHROME_HEADLESS" ]] && YOUTUBE_CHROME_HEADLESS="$CLI_YOUTUBE_CHROME_HEADLESS"
[[ -n "$CLI_YOUTUBE_CHROME_START_MINIMIZED" ]] && YOUTUBE_CHROME_START_MINIMIZED="$CLI_YOUTUBE_CHROME_START_MINIMIZED"
[[ -n "$CLI_YOUTUBE_CHROME_BACKGROUND" ]] && YOUTUBE_CHROME_BACKGROUND="$CLI_YOUTUBE_CHROME_BACKGROUND"
YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-}"
if [[ -z "$YOUTUBE_CDP_PORT" && "${YOUTUBE_CDP_URL:-}" =~ :([0-9]+)(/.*)?$ ]]; then
  YOUTUBE_CDP_PORT="${BASH_REMATCH[1]}"
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
YOUTUBE_CHROME_HEADLESS="${YOUTUBE_CHROME_HEADLESS:-false}"
YOUTUBE_CHROME_BACKGROUND="${YOUTUBE_CHROME_BACKGROUND:-false}"

if [[ "${IN_DOCKER:-}" != "1" ]]; then
  if [[ "$YOUTUBE_LOGIN_PROFILE_DIR" == /app/data/* ]]; then
    YOUTUBE_LOGIN_PROFILE_DIR="$ROOT_DIR/backend/data/${YOUTUBE_LOGIN_PROFILE_DIR#/app/data/}"
  fi
  if [[ "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" == /app/data/chromium-youtube \
    && -n "${YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR:-}" \
    && -d "$YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR" ]]; then
    SOURCE_YOUTUBE_LOGIN_PROFILE_DIR="$YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR"
  elif [[ "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" == /app/data/* ]]; then
    SOURCE_YOUTUBE_LOGIN_PROFILE_DIR="$ROOT_DIR/backend/data/${SOURCE_YOUTUBE_LOGIN_PROFILE_DIR#/app/data/}"
  fi
fi

if [[ "$CLI_YOUTUBE_USE_DESKTOP_PROFILE" == "true" ]]; then
  if [[ ! -d "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" ]]; then
    echo "Desktop Chrome profile tidak ditemukan: ${SOURCE_YOUTUBE_LOGIN_PROFILE_DIR}" >&2
    echo "Set YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR ke profile Chrome desktop yang sudah login." >&2
    exit 1
  fi
  YOUTUBE_LOGIN_PROFILE_DIR="$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR"
  YOUTUBE_LOGIN_PROFILE_DIRECTORY="${YOUTUBE_LOGIN_PROFILE_DIRECTORY:-auto}"
  YOUTUBE_REFRESH_LOGIN_PROFILE="false"
fi

ensure_writable_log() {
  local requested="$1"
  local fallback="$ROOT_DIR/backend/data/youtube-chrome.log"
  mkdir -p "$(dirname "$requested")" 2>/dev/null || true
  if touch "$requested" 2>/dev/null && [[ -w "$requested" ]]; then
    printf '%s\n' "$requested"
    return 0
  fi
  mkdir -p "$(dirname "$fallback")"
  touch "$fallback"
  printf '%s\n' "$fallback"
}

resolve_chrome_bin() {
  if command -v "$CHROME_BIN" >/dev/null 2>&1; then
    command -v "$CHROME_BIN"
    return 0
  fi
  for candidate in google-chrome-stable google-chrome chromium chromium-browser; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  if command -v python >/dev/null 2>&1; then
    python - <<'PY' 2>/dev/null && return 0
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    print(playwright.chromium.executable_path)
PY
  fi
  return 1
}

normalize_profile_match_text() {
  tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]'
}

profile_matches_target() {
  local profile_path="$1"
  local target_email="${YOUTUBE_TARGET_EMAIL:-}"
  local target_channel="${YOUTUBE_TARGET_CHANNEL:-}"
  local target_channel_id="${YOUTUBE_TARGET_CHANNEL_ID:-}"
  local haystack=""
  local file
  for file in \
    "$profile_path/Preferences" \
    "$profile_path/AccountBookmarks" \
    "$profile_path/Bookmarks" \
    "$profile_path/Bookmarks.bak"; do
    if [[ -r "$file" ]]; then
      [[ -n "$target_email" && $(grep -aFio -- "$target_email" "$file" 2>/dev/null | head -n 1) ]] && return 0
      [[ -n "$target_channel" && $(grep -aFio -- "$target_channel" "$file" 2>/dev/null | head -n 1) ]] && return 0
      [[ -n "$target_channel_id" && $(grep -aFio -- "$target_channel_id" "$file" 2>/dev/null | head -n 1) ]] && return 0
      haystack+=" $(LC_ALL=C grep -aEio '([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|UC[A-Z0-9_-]{20,}|@[A-Z0-9._-]+|ryuundy[0-9]*)' "$file" 2>/dev/null || true)"
    fi
  done
  haystack="$(printf '%s' "$haystack" | normalize_profile_match_text)"
  [[ -n "$target_email" && "$haystack" == *"$(printf '%s' "$target_email" | normalize_profile_match_text)"* ]] && return 0
  [[ -n "$target_channel" && "$haystack" == *"$(printf '%s' "$target_channel" | normalize_profile_match_text)"* ]] && return 0
  [[ -n "$target_channel_id" && "$haystack" == *"$(printf '%s' "$target_channel_id" | normalize_profile_match_text)"* ]] && return 0
  return 1
}

detect_youtube_profile_directory() {
  local profile_root="$1"
  local requested="$2"
  if [[ "$requested" != "auto" ]]; then
    printf '%s\n' "$requested"
    return 0
  fi
  local candidate
  for candidate in "$profile_root"/Default "$profile_root"/Profile\ *; do
    [[ -d "$candidate" ]] || continue
    if profile_matches_target "$candidate"; then
      basename "$candidate"
      return 0
    fi
  done
  for candidate in "$profile_root"/Default "$profile_root"/Profile\ *; do
    [[ -d "$candidate" ]] || continue
    if [[ -f "$candidate/Cookies" ]]; then
      basename "$candidate"
      return 0
    fi
  done
  printf '%s\n' "Default"
}

if ! RESOLVED_CHROME_BIN="$(resolve_chrome_bin)"; then
  echo "Chrome/Chromium executable not found. Set CHROME_BIN to a valid browser path." >&2
  exit 127
fi
CHROME_BIN="$RESOLVED_CHROME_BIN"

if [[ -d "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" \
  && "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR" != "$YOUTUBE_LOGIN_PROFILE_DIR" \
  && ( ! -d "$YOUTUBE_LOGIN_PROFILE_DIR" || "$YOUTUBE_REFRESH_LOGIN_PROFILE" == "true" ) ]]; then
  echo "Syncing YouTube Chrome profile from ${SOURCE_YOUTUBE_LOGIN_PROFILE_DIR} to ${YOUTUBE_LOGIN_PROFILE_DIR}..."
  mkdir -p "$(dirname "$YOUTUBE_LOGIN_PROFILE_DIR")"
  rm -rf "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"
  mkdir -p "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"
  if command -v rsync >/dev/null 2>&1; then
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
  else
    cp -a "$SOURCE_YOUTUBE_LOGIN_PROFILE_DIR"/. "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/
    rm -rf \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/Crashpad \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/ShaderCache \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/GrShaderCache \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/*/Cache \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/*/"Code Cache" \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/*/GPUCache \
      "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp"/*/blob_storage 2>/dev/null || true
  fi
  find "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp" -maxdepth 3 -name 'Singleton*' -delete 2>/dev/null || true
  rm -rf "$YOUTUBE_LOGIN_PROFILE_DIR"
  mv "${YOUTUBE_LOGIN_PROFILE_DIR}.tmp" "$YOUTUBE_LOGIN_PROFILE_DIR"
fi

YOUTUBE_LOGIN_PROFILE_DIRECTORY="$(detect_youtube_profile_directory "$YOUTUBE_LOGIN_PROFILE_DIR" "$YOUTUBE_LOGIN_PROFILE_DIRECTORY")"
YOUTUBE_CHROME_LOG="$(ensure_writable_log "$YOUTUBE_CHROME_LOG")"
mkdir -p "$YOUTUBE_LOGIN_PROFILE_DIR" "$(dirname "$YOUTUBE_CHROME_LOG")"
if [[ "$CLI_YOUTUBE_USE_DESKTOP_PROFILE" != "true" ]]; then
  find "$YOUTUBE_LOGIN_PROFILE_DIR" -maxdepth 2 -name 'Singleton*' -delete 2>/dev/null || true
fi

echo "Opening Chrome for YouTube login/sync..."
echo "CDP: http://127.0.0.1:${YOUTUBE_CDP_PORT}"
echo "Profile: ${YOUTUBE_LOGIN_PROFILE_DIR}"
echo "Profile directory: ${YOUTUBE_LOGIN_PROFILE_DIRECTORY}"
echo "Chrome log: ${YOUTUBE_CHROME_LOG}"
if [[ "$CLI_YOUTUBE_USE_DESKTOP_PROFILE" == "true" && -e "$YOUTUBE_LOGIN_PROFILE_DIR/SingletonLock" ]]; then
  echo "Warning: desktop Chrome profile sedang dipakai. Jika CDP tidak aktif, tutup semua window Chrome dulu lalu jalankan command ini lagi."
fi
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
if [[ "$YOUTUBE_CHROME_HEADLESS" == "true" ]]; then
  chrome_args+=(--headless=new)
fi
if [[ "${EUID:-$(id -u)}" == "0" ]]; then
  chrome_args+=(--no-sandbox)
fi
echo "Start minimized: ${YOUTUBE_CHROME_START_MINIMIZED}"
echo "Headless: ${YOUTUBE_CHROME_HEADLESS}"
echo "Background: ${YOUTUBE_CHROME_BACKGROUND}"
if [[ "$YOUTUBE_CHROME_HEADLESS" == "true" ]]; then
  echo "Headless mode aktif: Chrome berjalan tanpa window. Untuk window login, jalankan: $0 --headed --background"
fi
echo "Command: ${CHROME_BIN} ${chrome_args[*]} ${YOUTUBE_STUDIO_URL}"

if [[ "$YOUTUBE_CHROME_BACKGROUND" == "true" ]]; then
  "$CHROME_BIN" \
    "${chrome_args[@]}" \
    "$YOUTUBE_STUDIO_URL" \
    >>"$YOUTUBE_CHROME_LOG" 2>&1 &
  echo "Chrome started in background. PID: $!"
  exit 0
fi

exec "$CHROME_BIN" \
  "${chrome_args[@]}" \
  "$YOUTUBE_STUDIO_URL" \
  2>>"$YOUTUBE_CHROME_LOG"
