#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHROME_BIN="${TIKTOK_CHROME_EXECUTABLE:-${CHROME_BIN:-google-chrome}}"
TIKTOK_CDP_URL="${TIKTOK_CDP_URL:-http://127.0.0.1:9444}"
TIKTOK_CDP_PORT="${TIKTOK_CDP_PORT:-}"
TIKTOK_LOGIN_PROFILE_DIR="${TIKTOK_CHROMIUM_USER_DATA_DIR:-/app/data/tiktok-chrome-profile}"
TIKTOK_LOGIN_PROFILE_DIRECTORY="${TIKTOK_CHROMIUM_PROFILE_DIRECTORY:-Default}"
TIKTOK_LOGIN_URL="${TIKTOK_LOGIN_URL:-https://www.tiktok.com/login}"
TIKTOK_LOGIN_METHOD="${TIKTOK_LOGIN_METHOD:-google}"
TIKTOK_CHROME_BACKGROUND="${TIKTOK_CHROME_BACKGROUND:-true}"
if [[ "${IN_DOCKER:-}" == "1" ]]; then
  DEFAULT_TIKTOK_CHROME_LOG="/app/data/tiktok-chrome.log"
else
  DEFAULT_TIKTOK_CHROME_LOG="$ROOT_DIR/backend/data/tiktok-chrome.log"
fi
TIKTOK_CHROME_LOG="${TIKTOK_CHROME_LOG:-$DEFAULT_TIKTOK_CHROME_LOG}"
GUI_BRIDGE_DIR="${YOUTUBE_GUI_BRIDGE_DIR:-/app/data/youtube-gui}"
HOST_RUNTIME_DIR="${YOUTUBE_HOST_RUNTIME_DIR:-/run/fendy-clipper-host-user}"

if [[ -z "$TIKTOK_CDP_PORT" && "$TIKTOK_CDP_URL" =~ :([0-9]+)(/.*)?$ ]]; then
  TIKTOK_CDP_PORT="${BASH_REMATCH[1]}"
fi
TIKTOK_CDP_PORT="${TIKTOK_CDP_PORT:-9444}"

if [[ "${YOUTUBE_CDP_URL:-}" == "$TIKTOK_CDP_URL" ]]; then
  echo "Port Chrome TikTok bertabrakan dengan YouTube: $TIKTOK_CDP_URL" >&2
  echo "Gunakan port khusus TikTok, misalnya TIKTOK_CDP_URL=http://127.0.0.1:9444" >&2
  exit 2
fi

if [[ "${IN_DOCKER:-}" != "1" && "$TIKTOK_LOGIN_PROFILE_DIR" == /app/data/* ]]; then
  TIKTOK_LOGIN_PROFILE_DIR="$ROOT_DIR/backend/data/${TIKTOK_LOGIN_PROFILE_DIR#/app/data/}"
fi

resolve_chrome_bin() {
  if command -v "$CHROME_BIN" >/dev/null 2>&1; then
    command -v "$CHROME_BIN"
    return 0
  fi
  local candidate
  for candidate in google-chrome-stable google-chrome chromium chromium-browser; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  python - <<'PY' 2>/dev/null
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    print(playwright.chromium.executable_path)
PY
}

if curl -fsS --max-time 2 "$TIKTOK_CDP_URL/json/version" >/dev/null 2>&1; then
  echo "Chrome TikTok sudah terbuka dan CDP siap: $TIKTOK_CDP_URL"
  exit 0
fi

if ! CHROME_BIN="$(resolve_chrome_bin)" || [[ -z "$CHROME_BIN" ]]; then
  echo "Chrome/Chromium tidak ditemukan untuk login TikTok." >&2
  exit 127
fi

if [[ -r "$GUI_BRIDGE_DIR/display" ]]; then
  bridge_display="$(head -n 1 "$GUI_BRIDGE_DIR/display" | tr -d '\r\n')"
  [[ -z "$bridge_display" ]] || export DISPLAY="$bridge_display"
fi
if [[ -d "$HOST_RUNTIME_DIR" ]]; then
  shopt -s nullglob
  authority_files=("$HOST_RUNTIME_DIR"/.mutter-Xwaylandauth.*)
  shopt -u nullglob
  if (( ${#authority_files[@]} > 0 )); then
    newest_authority="${authority_files[0]}"
    for authority_file in "${authority_files[@]:1}"; do
      [[ "$authority_file" -nt "$newest_authority" ]] && newest_authority="$authority_file"
    done
    export XAUTHORITY="$newest_authority"
  fi
fi
if [[ -z "${XAUTHORITY:-}" || ! -r "${XAUTHORITY:-}" ]]; then
  if [[ -r "$GUI_BRIDGE_DIR/Xauthority" ]]; then
    export XAUTHORITY="$GUI_BRIDGE_DIR/Xauthority"
  fi
fi
if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -S "$HOST_RUNTIME_DIR/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=$HOST_RUNTIME_DIR/bus"
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "DISPLAY desktop tidak tersedia untuk Chrome TikTok." >&2
  exit 3
fi
display_number="${DISPLAY#:}"
display_number="${display_number%%.*}"
if [[ ! -S "/tmp/.X11-unix/X${display_number}" ]]; then
  echo "Socket X11 untuk DISPLAY=${DISPLAY} tidak ditemukan di /tmp/.X11-unix." >&2
  exit 3
fi
if [[ -z "${XAUTHORITY:-}" || ! -r "${XAUTHORITY:-}" ]]; then
  echo "Xauthority desktop aktif tidak dapat dibaca oleh Chrome TikTok." >&2
  exit 3
fi
# A Docker user-namespace may be able to stat Mutter's current authority file
# but not read it. Do not launch Chrome with an older bridge cookie in that
# state: X11 would reject it with the opaque "Invalid MIT-MAGIC-COOKIE-1".
shopt -s nullglob
live_authority_files=("$HOST_RUNTIME_DIR"/.mutter-Xwaylandauth.*)
shopt -u nullglob
if (( ${#live_authority_files[@]} > 0 )); then
  newest_live_authority="${live_authority_files[0]}"
  for authority_file in "${live_authority_files[@]:1}"; do
    [[ "$authority_file" -nt "$newest_live_authority" ]] && newest_live_authority="$authority_file"
  done
  if [[ "$XAUTHORITY" == "$GUI_BRIDGE_DIR/Xauthority" && "$newest_live_authority" -nt "$XAUTHORITY" ]]; then
    echo "Xauthority bridge kedaluwarsa; cookie desktop aktif berubah." >&2
    echo "Watcher GUI belum memperbarui $XAUTHORITY. Jalankan scripts/prepare-youtube-gui-runtime.sh dari host." >&2
    exit 3
  fi
fi

mkdir -p "$TIKTOK_LOGIN_PROFILE_DIR" "$(dirname "$TIKTOK_CHROME_LOG")"
find "$TIKTOK_LOGIN_PROFILE_DIR" -maxdepth 2 -name 'Singleton*' -delete 2>/dev/null || true

chrome_args=(
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port="$TIKTOK_CDP_PORT"
  --user-data-dir="$TIKTOK_LOGIN_PROFILE_DIR"
  --profile-directory="$TIKTOK_LOGIN_PROFILE_DIRECTORY"
  --no-first-run
  --no-default-browser-check
  --start-maximized
  --disable-dev-shm-usage
  # This browser is displayed through the X11 socket mounted by Docker. Force
  # that backend so Chrome does not probe an unavailable Wayland socket.
  --ozone-platform=x11
  # Do not disable GPU compositing, Skia, or rasterization here. Recent Chrome
  # versions can fall back to software rendering on their own; disabling the
  # whole rendering stack makes OAuth popup surfaces appear gray/blank under
  # GNOME/Xwayland and also makes scrolling and animations needlessly slow.
  --log-level=3
)
if [[ "${EUID:-$(id -u)}" == "0" ]]; then
  chrome_args+=(--no-sandbox)
fi

echo "Membuka Chrome GUI untuk login TikTok..."
echo "Display: ${DISPLAY:-tidak tersedia}"
echo "Xauthority: $XAUTHORITY"
echo "Profile: $TIKTOK_LOGIN_PROFILE_DIR"
echo "CDP: $TIKTOK_CDP_URL"
echo "Login method: $TIKTOK_LOGIN_METHOD (dipilih otomatis oleh uploader)"
echo "Chrome log: $TIKTOK_CHROME_LOG"
if [[ "$TIKTOK_CHROME_BACKGROUND" == "true" ]]; then
  "$CHROME_BIN" "${chrome_args[@]}" "$TIKTOK_LOGIN_URL" >>"$TIKTOK_CHROME_LOG" 2>&1 &
  echo "Chrome TikTok berjalan di background dengan PID $!"
  exit 0
fi
echo "Chrome TikTok dijalankan dalam mode supervised."
exec "$CHROME_BIN" "${chrome_args[@]}" "$TIKTOK_LOGIN_URL" >>"$TIKTOK_CHROME_LOG" 2>&1
