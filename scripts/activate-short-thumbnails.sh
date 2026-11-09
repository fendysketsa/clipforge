#!/usr/bin/env bash
# Permanently integrate raw-frame curiosity covers after active work drains.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT_DIR/scripts/activate-youtube-quiet-check.sh" --recover-stalled-cron --ryuundy-learning --preserve-browser "$@"
