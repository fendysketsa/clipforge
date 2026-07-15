#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Delegating to recreate-compose-up.sh --reset-profile."
echo "Chrome CDP will start minimized/background. Restore the window manually if YouTube asks for login."
export YOUTUBE_CHROME_START_MINIMIZED="${YOUTUBE_CHROME_START_MINIMIZED:-true}"
exec "$ROOT_DIR/scripts/recreate-compose-up.sh" --reset-profile --watch-chrome
