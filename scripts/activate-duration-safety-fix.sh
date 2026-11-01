#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BACKEND_CONTAINER="fendy-clipper-backend"
FRONTEND_CONTAINER="fendy-clipper-frontend"

test -f "$PROJECT_DIR/backend/api.py"
test -f "$PROJECT_DIR/backend/clipper.py"
test -f "$PROJECT_DIR/frontend/.next/BUILD_ID"

docker cp "$PROJECT_DIR/backend/api.py" "$BACKEND_CONTAINER:/app/api.py"
docker cp "$PROJECT_DIR/backend/clipper.py" "$BACKEND_CONTAINER:/app/clipper.py"
docker cp "$PROJECT_DIR/frontend/.next/." "$FRONTEND_CONTAINER:/app/.next/"

docker restart "$BACKEND_CONTAINER" "$FRONTEND_CONTAINER" >/dev/null

for _attempt in $(seq 1 30); do
  if docker exec "$BACKEND_CONTAINER" curl -fsS \
    http://127.0.0.1:8010/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker exec "$BACKEND_CONTAINER" curl -fsS http://127.0.0.1:8010/api/health >/dev/null
docker exec "$BACKEND_CONTAINER" python -c \
  "from pathlib import Path; api=Path('/app/api.py').read_text(); clipper=Path('/app/clipper.py').read_text(); assert 'completed_clip_integrity_issue' in api; assert 'upload_media_duration_issue' in api; assert 'minimum_seconds=(' in clipper"

echo "Duration safety fix aktif. Job queued/running lama akan dipulihkan oleh startup recovery."
