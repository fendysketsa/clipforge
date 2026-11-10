#!/usr/bin/env bash
# Install the reviewed frontend and verify the assets served by port 3000.
set -euo pipefail
activation_script_path="$(realpath -- "${BASH_SOURCE[0]:-$0}")"
if [[ "${CLIPFORGE_ACTIVATION_SNAPSHOT:-}" != "$activation_script_path" ]]; then
  activation_script_text="$(< "$activation_script_path")"
  bash -n <<< "$activation_script_text"
  export CLIPFORGE_ACTIVATION_SNAPSHOT="$activation_script_path"
  exec bash -c "$activation_script_text" "$activation_script_path" "$@"
fi
unset CLIPFORGE_ACTIVATION_SNAPSHOT
SCRIPT_DIR="$(cd -- "$(dirname -- "$activation_script_path")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FRONTEND_CONTAINER="fendy-clipper-frontend"
BUILD_DIR="$PROJECT_DIR/frontend/${CLIPFORGE_BUILD_DIR:-.next-history}"
LOCAL_BUILD_ID="$BUILD_DIR/BUILD_ID"
trap 'status=$?; echo "Aktivasi gagal pada baris $LINENO (exit $status). UI baru belum terverifikasi." >&2; exit "$status"' ERR
if (( EUID != 0 )); then
  echo "Akses Docker memerlukan sudo: sudo bash $SCRIPT_DIR/activate-history-card-layout.sh" >&2
  exit 77
fi
printf '[1/4] Memeriksa artefak UI: %s\n' "$BUILD_DIR"
test -f "$LOCAL_BUILD_ID"
grep -Rqs 'jobCardPreview' "$BUILD_DIR/static"
grep -Rqs 'historyCardSweep' "$BUILD_DIR/static"

# Resolve the actual Next server's cwd/distDir instead of assuming /app/.next.
runtime_info="$(docker exec -i "$FRONTEND_CONTAINER" node < "$SCRIPT_DIR/frontend-runtime-target.cjs")"
runtime_dist="$(python -c 'import json,sys; print(json.loads(sys.stdin.read().split("CLIPFORGE_RUNTIME=")[-1])["dist"])' <<< "$runtime_info")"
printf '[2/4] Tujuan kontainer: %s:%s\n' "$FRONTEND_CONTAINER" "$runtime_dist"
docker exec "$FRONTEND_CONTAINER" test -f "$runtime_dist/BUILD_ID"
docker cp "$BUILD_DIR/." "$FRONTEND_CONTAINER:$runtime_dist/"
docker restart "$FRONTEND_CONTAINER" >/dev/null
printf '[3/4] Menunggu frontend dan memeriksa build ID...\n'
for _attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:3000/ >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:3000/ >/dev/null
local_build="$(tr -d '\r\n' < "$LOCAL_BUILD_ID")"
container_build="$(docker exec "$FRONTEND_CONTAINER" cat "$runtime_dist/BUILD_ID" | tr -d '\r\n')"
test "$local_build" = "$container_build"
printf '[4/4] Memeriksa aset yang benar-benar disajikan port 3000...\n'
python "$SCRIPT_DIR/verify-history-frontend.py"
printf 'UI tiga kolom aktif; build %s terverifikasi. Backend dan upload tetap berjalan.\n' "$local_build"
