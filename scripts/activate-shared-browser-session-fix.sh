#!/usr/bin/env bash
# Activate browser CLI fixes without stopping the API or an active renderer.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
log="$ROOT_DIR/reports/shared-browser-session-activation.log"
[[ ! -L "$log" ]] || exit 73
exec > >(tee -a "$log") 2>&1
trap 'code=$?; echo "Activation failed at line $LINENO (exit $code). See reports/shared-browser-session-activation.log." >&2' ERR
cli_only=false
if [[ "${1:-}" == "--cli-only" ]]; then cli_only=true; fi
if (( EUID != 0 )); then
  echo "Docker access requires root: sudo bash $ROOT_DIR/scripts/activate-shared-browser-session-fix.sh" >&2
  exit 77
fi
lock=/tmp/clipforge-recreate-compose-up.lock
[[ ! -L "$lock" ]] || exit 73
if [[ ! -e "$lock" ]]; then
  (set -o noclobber; umask 000; : >"$lock") 2>/dev/null || true
fi
exec 9<"$lock"
flock -n 9 || { echo "Another ClipForge deployment is active." >&2; exit 75; }

python - <<'PY'
import json, urllib.request
for platform in ('youtube', 'tiktok'):
    with urllib.request.urlopen(f'http://127.0.0.1:8010/api/{platform}/uploads', timeout=15) as response:
        rows = json.load(response)
    if any(row.get('status') in {'queued', 'running'} for row in rows):
        raise SystemExit('Activation postponed: an upload is active. Retry when the upload queue is idle.')
PY

python -m py_compile backend/youtube_uploader.py backend/tiktok_uploader.py
for module in youtube_uploader tiktok_uploader; do
  docker cp "backend/$module.py" "fendy-clipper-backend:/app/$module.py.session-fix"
done
# Compile both staged modules before atomically replacing either live file.
docker exec fendy-clipper-backend python -c 'import pathlib; [compile(pathlib.Path(f"/app/{name}.py.session-fix").read_text(), f"{name}.py", "exec") for name in ("youtube_uploader", "tiktok_uploader")]'
docker exec fendy-clipper-backend python -c 'import os; [os.replace(f"/app/{name}.py.session-fix", f"/app/{name}.py") for name in ("youtube_uploader", "tiktok_uploader")]'
for module in youtube_uploader tiktok_uploader; do
  expected="$(sha256sum "backend/$module.py")"
  actual="$(docker exec fendy-clipper-backend sha256sum "/app/$module.py")"
  [[ "${expected%% *}" == "${actual%% *}" ]] || { echo "Source verification failed: $module" >&2; exit 1; }
done
docker exec fendy-clipper-backend python -c 'import inspect, youtube_uploader, tiktok_uploader; assert not youtube_uploader.build_parser().parse_args(["capture-session"]).hydrate_storage_state; assert "webapp.app-context" in inspect.getsource(tiktok_uploader.current_profile_handle)'
# Stage the API and its new dependencies for the next ordinary container
# restart too. Do not reload the running API while it owns render workers.
for module in news_hot youtube_playlists api; do
  docker cp "backend/$module.py" "fendy-clipper-backend:/app/$module.py.session-fix"
done
docker exec fendy-clipper-backend python -c 'import pathlib; [compile(pathlib.Path(f"/app/{name}.py.session-fix").read_text(), f"{name}.py", "exec") for name in ("news_hot", "youtube_playlists", "api")]'
docker exec fendy-clipper-backend python -c 'import os; [os.replace(f"/app/{name}.py.session-fix", f"/app/{name}.py") for name in ("news_hot", "youtube_playlists", "api")]'
for module in news_hot youtube_playlists api; do
  expected="$(sha256sum "backend/$module.py")"
  actual="$(docker exec fendy-clipper-backend sha256sum "/app/$module.py")"
  [[ "${expected%% *}" == "${actual%% *}" ]] || { echo "Source verification failed: $module" >&2; exit 1; }
done
docker exec fendy-clipper-backend python -c 'import hashlib,json,os,pathlib,datetime; p=pathlib.Path("/app/data/shared-browser-session-fix-runtime.json"); data={"verified_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"sha256":{name:hashlib.sha256(pathlib.Path(f"/app/{name}.py").read_bytes()).hexdigest() for name in ("youtube_uploader","tiktok_uploader","news_hot","youtube_playlists","api")}}; p.write_text(json.dumps(data,indent=2)); os.chmod(p,0o644)'
echo "Both running uploader modules verified. Proof: backend/data/shared-browser-session-fix-runtime.json"

if [[ "$cli_only" == "true" ]]; then
  echo "CLI activation complete; API and active render workers were not restarted."
  exit 0
fi

if docker compose version >/dev/null 2>&1; then compose=(docker compose); else compose=(docker-compose); fi
"${compose[@]}" --env-file .env config --quiet
"${compose[@]}" --env-file .env build backend
echo "Browser CLI fixes verified in the running backend; image refreshed. Active render workers were not stopped. API-module changes load on the next safe backend recreation."
