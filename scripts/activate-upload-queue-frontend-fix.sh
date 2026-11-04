#!/usr/bin/env bash
# Rebuild only the UI, retaining its existing bridge network and port mapping.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if (( EUID != 0 )); then exit 77; fi
exec 9</tmp/clipforge-recreate-compose-up.lock
flock -n 9 || { echo "Another deployment is active." >&2; exit 75; }
if docker compose version >/dev/null 2>&1; then compose=(docker compose); else compose=(docker-compose); fi
"${compose[@]}" --env-file .env config --quiet
"${compose[@]}" --env-file .env build frontend
"${compose[@]}" --env-file .env up -d --no-deps --no-build frontend
python - <<'PY'
import time, urllib.request
for attempt in range(45):
    try:
        with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=4) as response:
            assert response.status == 200
        print('Frontend healthy; existing bridge network retained.')
        break
    except Exception:
        if attempt == 44: raise
        time.sleep(1)
PY
