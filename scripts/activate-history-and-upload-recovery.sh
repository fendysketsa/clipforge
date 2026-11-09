#!/usr/bin/env bash
# Deploy the reviewed UI, then activate backend recovery only after work drains.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if (( EUID != 0 )); then
  echo "Run: sudo bash $ROOT_DIR/scripts/activate-history-and-upload-recovery.sh" >&2
  exit 77
fi
bash "$ROOT_DIR/scripts/activate-history-card-layout.sh"
# The guarded activator pauses future cron launches, waits for real active
# renders/uploads, preserves the current browser, and restores cron afterwards.
exec bash "$ROOT_DIR/scripts/activate-youtube-quiet-check.sh" --recover-stalled-cron --preserve-browser "$@"
