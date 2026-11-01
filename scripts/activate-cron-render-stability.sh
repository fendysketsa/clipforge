#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

wait_http() {
  local url="$1"
  local attempts="${2:-90}"
  local response=""
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if response="$(curl -fsS --max-time 10 "$url" 2>/dev/null)"; then
      printf '%s' "$response"
      return 0
    fi
    sleep 1
  done
  echo "Endpoint belum stabil setelah ${attempts} percobaan: ${url}" >&2
  return 1
}

python -m py_compile backend/api.py backend/clipper.py
(cd frontend && npm run typecheck && npm run build)
docker-compose --env-file .env config --quiet

echo "Menghentikan semua render/upload/automation aktif sebelum rebuild penuh..."
"$PROJECT_DIR/scripts/recreate-compose-up.sh" --force-active

wait_http http://127.0.0.1:8010/api/health >/dev/null
wait_http http://127.0.0.1:3000/ >/dev/null

schedule_payload="$(wait_http http://127.0.0.1:8010/api/automation/viral-cc/schedule)"
python - "$schedule_payload" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert isinstance(payload.get("enabled"), bool)
assert "scheduler_running" in payload
PY

echo "SELESAI: cron multi-clip aktif; upload menunggu render lengkap, hanya hasil lolos QC yang dikirim, dan cleanup hanya menyentuh upload terverifikasi."
