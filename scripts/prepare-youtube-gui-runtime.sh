#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_DISPLAY="${DISPLAY:-}"
HOST_XAUTHORITY="${XAUTHORITY:-}"
HOST_XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/load-dotenv.sh"
load_dotenv "$ROOT_DIR/.env"

GUI_BRIDGE_DIR="${YOUTUBE_GUI_BRIDGE_HOST_DIR:-$ROOT_DIR/backend/data/youtube-gui}"
if [[ "$GUI_BRIDGE_DIR" != /* ]]; then
  GUI_BRIDGE_DIR="$ROOT_DIR/${GUI_BRIDGE_DIR#./}"
fi
RUNTIME_DIR="${HOST_XDG_RUNTIME_DIR:-${YOUTUBE_HOST_RUNTIME_DIR:-/run/user/$(id -u)}}"
DISPLAY_VALUE="${HOST_DISPLAY:-${YOUTUBE_DISPLAY:-${DISPLAY:-}}}"
AUTHORITY_FILE="$HOST_XAUTHORITY"

if [[ -z "$AUTHORITY_FILE" || ! -r "$AUTHORITY_FILE" ]]; then
  shopt -s nullglob
  authority_files=("$RUNTIME_DIR"/.mutter-Xwaylandauth.*)
  shopt -u nullglob
  if (( ${#authority_files[@]} > 0 )); then
    AUTHORITY_FILE="${authority_files[0]}"
    for candidate in "${authority_files[@]:1}"; do
      [[ "$candidate" -nt "$AUTHORITY_FILE" ]] && AUTHORITY_FILE="$candidate"
    done
  fi
fi

if [[ -z "$DISPLAY_VALUE" ]]; then
  echo "DISPLAY sesi desktop tidak ditemukan. Jalankan script ini dari terminal desktop yang aktif." >&2
  exit 1
fi
if [[ -z "$AUTHORITY_FILE" || ! -r "$AUTHORITY_FILE" ]]; then
  echo "Xauthority sesi desktop tidak ditemukan di ${RUNTIME_DIR}." >&2
  exit 1
fi

mkdir -p "$GUI_BRIDGE_DIR"
cp "$AUTHORITY_FILE" "$GUI_BRIDGE_DIR/Xauthority.tmp"
chmod 0644 "$GUI_BRIDGE_DIR/Xauthority.tmp"
mv "$GUI_BRIDGE_DIR/Xauthority.tmp" "$GUI_BRIDGE_DIR/Xauthority"
printf '%s\n' "$DISPLAY_VALUE" >"$GUI_BRIDGE_DIR/display.tmp"
chmod 0644 "$GUI_BRIDGE_DIR/display.tmp"
mv "$GUI_BRIDGE_DIR/display.tmp" "$GUI_BRIDGE_DIR/display"

echo "YouTube GUI bridge siap."
echo "Display: $DISPLAY_VALUE"
echo "Xauthority bridge: $GUI_BRIDGE_DIR/Xauthority"
