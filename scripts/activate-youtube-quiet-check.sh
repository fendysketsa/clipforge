#!/usr/bin/env bash
# Activate quiet status checks and cron upload recovery while actual work is idle.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
recover_stalled_cron=false
skip_build=false
wait_seconds=21600
while (( $# )); do
  case "$1" in
    --recover-stalled-cron) recover_stalled_cron=true ;;
    --skip-build) skip_build=true ;;
    --no-wait) wait_seconds=0 ;;
    --wait-seconds)
      [[ "${2:-}" =~ ^[0-9]+$ ]] || { echo "--wait-seconds requires a nonnegative integer." >&2; exit 2; }
      wait_seconds="$2"
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--recover-stalled-cron] [--skip-build] [--wait-seconds N | --no-wait]"
      echo "Waits up to six hours for active work; --skip-build verifies and reuses the built image."
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if (( EUID != 0 )); then
  echo "Run: sudo bash $ROOT_DIR/scripts/activate-youtube-quiet-check.sh" >&2
  exit 77
fi
lock=/tmp/clipforge-recreate-compose-up.lock
[[ ! -L "$lock" ]] || exit 73
if [[ ! -e "$lock" ]]; then
  (set -o noclobber; umask 000; : >"$lock") 2>/dev/null || true
fi
exec 9<"$lock"
flock -n 9 || { echo "Another ClipForge deployment is active." >&2; exit 75; }
python -m py_compile backend/api.py backend/youtube_remote_status.py
# Refresh the durable image first; restart the existing container to retain
# its exact environment, mounts, and network settings.
if [[ "$skip_build" != true ]]; then
  if docker compose version >/dev/null 2>&1; then compose=(docker compose); else compose=(docker-compose); fi
  "${compose[@]}" --env-file .env build backend
fi
image_id="$(docker image inspect clipforge-backend:latest --format '{{.Id}}')"
verify_image_sources() {
  python - "$image_id" <<'PY'
import hashlib, pathlib, subprocess, sys
lines = subprocess.check_output([
    'docker', 'run', '--rm', '--network', 'none', '--read-only',
    '--entrypoint', 'sha256sum', sys.argv[1], '/app/api.py', '/app/youtube_remote_status.py',
], text=True).splitlines()
actual = dict((line.split()[1], line.split()[0]) for line in lines)
for name in ('api', 'youtube_remote_status'):
    expected = hashlib.sha256(pathlib.Path('backend/' + name + '.py').read_bytes()).hexdigest()
    if actual.get('/app/' + name + '.py') != expected:
        raise SystemExit('Built image does not match backend/' + name + '.py; rerun without --skip-build.')
PY
}
verify_image_sources
schedule_was_enabled="$(python - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
    print('true' if json.load(response)['enabled'] else 'false')
PY
)"
activation_state="$(mktemp /tmp/clipforge-cron-upload-activation.XXXXXX.json)"
chmod 600 "$activation_state"
restore_schedule() {
  python - "$schedule_was_enabled" <<'PY'
import sys, time, urllib.request
data = ('{"enabled":' + sys.argv[1] + '}').encode()
for attempt in range(30):
    try:
        request = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule', data=data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=5): pass
        break
    except Exception:
        if attempt == 29: raise
        time.sleep(2)
PY
}
trap 'restore_schedule || echo "Check the cron switch: restoring it failed." >&2; rm -f "$activation_state"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python - <<'PY'
import urllib.request
request = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule', data=b'{"enabled":false}', headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=15): pass
PY
idle_args=(--state-file "$activation_state")
if [[ "$recover_stalled_cron" == true ]]; then idle_args+=(--recover-stalled-cron); fi
echo "Future cron launches paused; waiting for existing work to finish (limit ${wait_seconds}s)."
python scripts/wait-for-backend-idle.py "${idle_args[@]}" --wait-seconds "$wait_seconds"
# Source may have changed while draining jobs. Keep the durable image and the
# staged runtime modules consistent before touching the existing container.
verify_image_sources
for module in api youtube_remote_status; do
  docker cp "backend/$module.py" "fendy-clipper-backend:/app/$module.py.quiet-check"
done
docker exec fendy-clipper-backend python -c 'import pathlib; [compile(pathlib.Path(f"/app/{name}.py.quiet-check").read_text(), name, "exec") for name in ("api", "youtube_remote_status")]'
python scripts/wait-for-backend-idle.py "${idle_args[@]}" --wait-seconds 0
docker exec fendy-clipper-backend python -c 'import os; [os.replace(f"/app/{name}.py.quiet-check", f"/app/{name}.py") for name in ("api", "youtube_remote_status")]'
# The API imports this function at startup, so replacing the file alone does
# not stop the old in-memory checker. Restart only after the idle check above.
docker restart fendy-clipper-backend >/dev/null
python - <<'PY'
import time, urllib.request
for attempt in range(90):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=3): pass
        break
    except Exception:
        if attempt == 89: raise
        time.sleep(1)
PY
for module in api youtube_remote_status; do
  expected="$(sha256sum "backend/$module.py")"
  actual="$(docker exec fendy-clipper-backend sha256sum "/app/$module.py")"
  [[ "${expected%% *}" == "${actual%% *}" ]] || { echo "Runtime source verification failed: $module" >&2; exit 1; }
done
docker exec fendy-clipper-backend python -c 'import inspect,youtube_remote_status as m; assert "new_page" not in inspect.getsource(m)'
restore_schedule
trap 'rm -f "$activation_state"' EXIT
python - "$activation_state" "$schedule_was_enabled" <<'PY'
import hashlib, json, pathlib, sys, time, urllib.request
base = 'http://127.0.0.1:8010/api/'
state = json.loads(pathlib.Path(sys.argv[1]).read_text())
for attempt in range(90):
    with urllib.request.urlopen(base + 'automation/viral-cc/schedule', timeout=10) as response:
        schedule = json.load(response)
    if not schedule['enabled'] and sys.argv[2] == 'false':
        break
    with urllib.request.urlopen(base + 'automation/viral-cc', timeout=10) as response:
        runs = {row['id']: row for row in json.load(response)}
    recovered = all(runs.get(run_id, {}).get('status') in {'failed', 'completed', 'cancelled'} for run_id in state['stalled_run_ids'])
    if recovered and schedule['enabled'] and schedule['scheduler_running'] and (schedule['active_run_id'] not in state['stalled_run_ids']) and (schedule['active_run_id'] or schedule['next_run_at']):
        break
    if attempt == 89:
        raise SystemExit('Backend healthy, but cron recovery is not confirmed; inspect scheduler before declaring success.')
    time.sleep(1)
assert schedule['enabled'] == (sys.argv[2] == 'true')
state.update({'verified_at': time.time(), 'schedule': schedule, 'sha256': {
    name: hashlib.sha256(pathlib.Path('backend/' + name + '.py').read_bytes()).hexdigest()
    for name in ('api', 'youtube_remote_status')
}})
path = pathlib.Path('reports/cron-upload-recovery-activation.json')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(schedule, ensure_ascii=False))
PY
rm -f "$activation_state"
trap - EXIT
echo "Quiet YouTube checks and cron recovery activated; runtime hashes and scheduler verified."
