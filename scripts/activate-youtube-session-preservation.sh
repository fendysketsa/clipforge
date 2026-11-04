#!/usr/bin/env bash
# Update only the uploader module atomically; keep active render workers alive.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if (( EUID != 0 )); then exit 77; fi
exec 9</tmp/clipforge-recreate-compose-up.lock
flock -n 9 || { echo "Another deployment is active." >&2; exit 75; }
python -m py_compile backend/youtube_uploader.py
docker cp backend/youtube_uploader.py fendy-clipper-backend:/app/youtube_uploader.py.session-fix
docker exec fendy-clipper-backend python -c 'import os; os.replace("/app/youtube_uploader.py.session-fix", "/app/youtube_uploader.py")'
expected="$(sha256sum backend/youtube_uploader.py)"
actual="$(docker exec fendy-clipper-backend sha256sum /app/youtube_uploader.py)"
[[ "${expected%% *}" == "${actual%% *}" ]]
docker exec fendy-clipper-backend python -c 'import youtube_uploader; assert not youtube_uploader.build_parser().parse_args(["capture-session"]).hydrate_storage_state'
if docker compose version >/dev/null 2>&1; then compose=(docker compose); else compose=(docker-compose); fi
"${compose[@]}" --env-file .env build backend
echo "Session-preserving uploader active; backend image refreshed without interrupting renders."
