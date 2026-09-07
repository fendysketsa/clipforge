#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_DISPLAY="${DISPLAY:-}"
HOST_XAUTHORITY="${XAUTHORITY:-}"
HOST_XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}"
MODE="once"

case "${1:-}" in
  "") ;;
  --watch) MODE="watch" ;;
  --start-watcher) MODE="start-watcher" ;;
  *)
    echo "Usage: $0 [--watch|--start-watcher]" >&2
    exit 2
    ;;
esac

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/load-dotenv.sh"
load_dotenv "$ROOT_DIR/.env"

GUI_BRIDGE_DIR="${YOUTUBE_GUI_BRIDGE_HOST_DIR:-$ROOT_DIR/backend/data/youtube-gui}"
if [[ "$GUI_BRIDGE_DIR" != /* ]]; then
  GUI_BRIDGE_DIR="$ROOT_DIR/${GUI_BRIDGE_DIR#./}"
fi
RUNTIME_DIR="${HOST_XDG_RUNTIME_DIR:-${YOUTUBE_HOST_RUNTIME_DIR:-/run/user/$(id -u)}}"
DISPLAY_VALUE="${HOST_DISPLAY:-${YOUTUBE_DISPLAY:-${DISPLAY:-}}}"
WATCH_INTERVAL_SECONDS="${YOUTUBE_GUI_BRIDGE_WATCH_INTERVAL_SECONDS:-2}"
WATCH_PID_FILE="$GUI_BRIDGE_DIR/watcher.pid"
WATCH_LOG_FILE="$GUI_BRIDGE_DIR/watcher.log"
WATCH_UNIT_NAME="clipforge-gui-bridge.service"

current_authority_file() {
  local authority_file="$HOST_XAUTHORITY"
  local candidate
  # Mutter replaces this file after a lock-screen/login transition. Always
  # prefer the newest live cookie instead of keeping the path captured when
  # this watcher started.
  shopt -s nullglob
  local authority_files=("$RUNTIME_DIR"/.mutter-Xwaylandauth.*)
  shopt -u nullglob
  if (( ${#authority_files[@]} > 0 )); then
    authority_file="${authority_files[0]}"
    for candidate in "${authority_files[@]:1}"; do
      [[ "$candidate" -nt "$authority_file" ]] && authority_file="$candidate"
    done
  fi
  if [[ -n "$authority_file" && -r "$authority_file" ]]; then
    printf '%s\n' "$authority_file"
    return 0
  fi
  return 1
}

refresh_bridge() {
  local authority_file
  if ! authority_file="$(current_authority_file)"; then
    echo "Xauthority sesi desktop tidak ditemukan atau tidak dapat dibaca di ${RUNTIME_DIR}." >&2
    return 1
  fi

  mkdir -p "$GUI_BRIDGE_DIR"
  if [[ ! -f "$GUI_BRIDGE_DIR/Xauthority" ]] || ! cmp -s "$authority_file" "$GUI_BRIDGE_DIR/Xauthority"; then
    cp "$authority_file" "$GUI_BRIDGE_DIR/Xauthority.tmp"
    chmod 0644 "$GUI_BRIDGE_DIR/Xauthority.tmp"
    mv "$GUI_BRIDGE_DIR/Xauthority.tmp" "$GUI_BRIDGE_DIR/Xauthority"
    echo "Xauthority bridge diperbarui dari $authority_file."
  fi
  if [[ ! -f "$GUI_BRIDGE_DIR/display" ]] || [[ "$(tr -d '\r\n' < "$GUI_BRIDGE_DIR/display")" != "$DISPLAY_VALUE" ]]; then
    printf '%s\n' "$DISPLAY_VALUE" >"$GUI_BRIDGE_DIR/display.tmp"
    chmod 0644 "$GUI_BRIDGE_DIR/display.tmp"
    mv "$GUI_BRIDGE_DIR/display.tmp" "$GUI_BRIDGE_DIR/display"
    echo "DISPLAY bridge diperbarui ke $DISPLAY_VALUE."
  fi
}

if [[ -z "$DISPLAY_VALUE" ]]; then
  echo "DISPLAY sesi desktop tidak ditemukan. Jalankan script ini dari terminal desktop yang aktif." >&2
  exit 1
fi
if ! current_authority_file >/dev/null; then
  echo "Xauthority sesi desktop tidak ditemukan atau tidak dapat dibaca di ${RUNTIME_DIR}." >&2
  exit 1
fi

refresh_bridge

if [[ "$MODE" == "start-watcher" ]]; then
  # A transient user service survives the terminal/deploy command that starts
  # it and is tied to the logged-in desktop user. Fall back to nohup on hosts
  # without a user systemd instance.
  if command -v systemd-run >/dev/null 2>&1 \
    && systemctl --user is-system-running >/dev/null 2>&1; then
    systemctl --user stop "$WATCH_UNIT_NAME" >/dev/null 2>&1 || true
    if systemd-run --user \
      --unit="$WATCH_UNIT_NAME" \
      --collect \
      --property=Restart=always \
      --property=RestartSec=2s \
      --setenv="DISPLAY=$DISPLAY_VALUE" \
      --setenv="XAUTHORITY=$(current_authority_file)" \
      --setenv="XDG_RUNTIME_DIR=$RUNTIME_DIR" \
      --setenv="YOUTUBE_GUI_BRIDGE_HOST_DIR=$GUI_BRIDGE_DIR" \
      --setenv="YOUTUBE_HOST_RUNTIME_DIR=$RUNTIME_DIR" \
      "$ROOT_DIR/scripts/prepare-youtube-gui-runtime.sh" --watch >/dev/null; then
      echo "GUI bridge watcher aktif sebagai user service $WATCH_UNIT_NAME."
      exit 0
    fi
  fi
  if [[ -r "$WATCH_PID_FILE" ]]; then
    existing_pid="$(tr -cd '0-9' < "$WATCH_PID_FILE")"
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null \
      && ps -p "$existing_pid" -o args= 2>/dev/null | grep -F -- "$0 --watch" >/dev/null; then
      kill "$existing_pid"
      wait "$existing_pid" 2>/dev/null || true
    fi
  fi
  nohup "$0" --watch >>"$WATCH_LOG_FILE" 2>&1 &
  watcher_pid=$!
  printf '%s\n' "$watcher_pid" >"$WATCH_PID_FILE"
  echo "GUI bridge watcher dimulai (PID $watcher_pid)."
  exit 0
fi

if [[ "$MODE" == "watch" ]]; then
  echo "Memantau perubahan Xauthority desktop setiap ${WATCH_INTERVAL_SECONDS} detik."
  while true; do
    refresh_bridge || true
    sleep "$WATCH_INTERVAL_SECONDS"
  done
fi

echo "YouTube GUI bridge siap."
echo "Display: $DISPLAY_VALUE"
echo "Xauthority bridge: $GUI_BRIDGE_DIR/Xauthority"
