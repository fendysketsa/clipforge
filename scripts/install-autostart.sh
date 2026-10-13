#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="clipforge-autostart.service"
UNIT_SOURCE="$ROOT_DIR/deploy/$UNIT_NAME"
BROWSER_UNIT_NAME="clipforge-social-browser.service"
BROWSER_UNIT_SOURCE="$ROOT_DIR/deploy/$BROWSER_UNIT_NAME"
USER_HOME_DIR="$(getent passwd "$(id -u)" | cut -d: -f6)"
USER_CONFIG_DIR="${XDG_CONFIG_HOME:-$USER_HOME_DIR/.config}"
UNIT_DIR="$USER_CONFIG_DIR/systemd/user"
UNIT_TARGET="$UNIT_DIR/$UNIT_NAME"
BROWSER_UNIT_TARGET="$UNIT_DIR/$BROWSER_UNIT_NAME"

for source in "$UNIT_SOURCE" "$BROWSER_UNIT_SOURCE"; do
  if [[ ! -f "$source" ]]; then
    echo "Unit autostart tidak ditemukan: $source" >&2
    exit 1
  fi
done
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
install -m 0644 "$BROWSER_UNIT_SOURCE" "$BROWSER_UNIT_TARGET"
systemctl --user daemon-reload
systemctl --user enable "$BROWSER_UNIT_NAME" "$UNIT_NAME"
# Older versions launched Chrome as a detached child of the stack restore
# service. Stop that owner first so the dedicated browser supervisor can take
# over the same persistent profile without a startup race.
systemctl --user stop "$UNIT_NAME" || true
systemctl --user restart "$BROWSER_UNIT_NAME"
systemctl --user start "$UNIT_NAME"
for unit in "$BROWSER_UNIT_NAME" "$UNIT_NAME"; do
  if ! systemctl --user is-active --quiet "$unit"; then
    systemctl --user status "$unit" --no-pager -l || true
    echo "Service $unit sudah enabled tetapi start pertama belum berhasil. Periksa journal user." >&2
    exit 1
  fi
done

echo "ClipForge autostart aktif setelah login desktop."
echo "Chrome YouTube/TikTok akan dijaga tetap aktif dengan profile login yang sama."
echo "Status: systemctl --user status $BROWSER_UNIT_NAME $UNIT_NAME"
echo "Log browser: journalctl --user -u $BROWSER_UNIT_NAME -f"
