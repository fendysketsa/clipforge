#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FRONTEND_CONTAINER="fendy-clipper-frontend"
LOCAL_BUILD_ID="$PROJECT_DIR/frontend/.next/BUILD_ID"

test -f "$LOCAL_BUILD_ID"
grep -Rqs 'historyCardSweep' "$PROJECT_DIR/frontend/.next/static"
docker inspect "$FRONTEND_CONTAINER" >/dev/null

docker cp "$PROJECT_DIR/frontend/.next/." "$FRONTEND_CONTAINER:/app/.next/"
docker restart "$FRONTEND_CONTAINER" >/dev/null

for _attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:3000/ >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS http://127.0.0.1:3000/ >/dev/null
local_build="$(tr -d '\r\n' < "$LOCAL_BUILD_ID")"
container_build="$(docker exec "$FRONTEND_CONTAINER" sh -c 'tr -d "\r\n" < /app/.next/BUILD_ID')"
test "$local_build" = "$container_build"
docker exec "$FRONTEND_CONTAINER" sh -eu -c \
  'grep -Rqs "historyCardSweep" /app/.next/static'

echo "Layout media-queue 2-grid polished aktif. Backend, render, dan proses upload tidak direstart."
