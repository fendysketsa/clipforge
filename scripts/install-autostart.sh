#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="clipforge-autostart.service"
UNIT_SOURCE="$ROOT_DIR/deploy/$UNIT_NAME"
USER_HOME_DIR="$(getent passwd "$(id -u)" | cut -d: -f6)"
USER_CONFIG_DIR="${XDG_CONFIG_HOME:-$USER_HOME_DIR/.config}"
UNIT_DIR="$USER_CONFIG_DIR/systemd/user"
UNIT_TARGET="$UNIT_DIR/$UNIT_NAME"

if [[ ! -f "$UNIT_SOURCE" ]]; then
  echo "Unit autostart tidak ditemukan: $UNIT_SOURCE" >&2
  exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd tidak ditemukan; installer ini membutuhkan desktop Linux berbasis systemd." >&2
  exit 1
fi
if ! systemctl --user is-system-running >/dev/null 2>&1; then
  echo "User systemd belum siap. Jalankan installer setelah login ke desktop." >&2
  exit 1
fi

mkdir -p "$UNIT_DIR"
install -m 0644 "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl --user daemon-reload
systemctl --user enable --now "$UNIT_NAME"
if ! systemctl --user is-active --quiet "$UNIT_NAME"; then
  systemctl --user status "$UNIT_NAME" --no-pager -l || true
  echo "Service sudah enabled tetapi start pertama belum berhasil. Periksa journal user." >&2
  exit 1
fi

echo "ClipForge autostart aktif setelah login desktop."
echo "Status: systemctl --user status $UNIT_NAME"
echo "Log: journalctl --user -u $UNIT_NAME -f"
