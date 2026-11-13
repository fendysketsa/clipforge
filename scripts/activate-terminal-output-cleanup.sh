#!/usr/bin/env bash
# Build first, drain actual media work, then verify the new cleanup policy.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
(( EUID == 0 )) || { echo "Run: sudo bash $ROOT_DIR/scripts/activate-terminal-output-cleanup.sh" >&2; exit 77; }
(( $# == 0 )) || { echo "No arguments expected." >&2; exit 2; }
if docker compose version >/dev/null 2>&1; then compose=(docker compose); else compose=(docker-compose); fi
lock=/tmp/clipforge-recreate-compose-up.lock
[[ ! -L "$lock" ]] || exit 73
if [[ ! -e "$lock" ]]; then
  (set -o noclobber; umask 000; : >"$lock") 2>/dev/null || true
fi
exec 9<"$lock"
flock -n 9 || { echo "Another ClipForge deployment is active." >&2; exit 75; }
"${compose[@]}" --env-file .env config --quiet
"${compose[@]}" --env-file .env build backend telegram-bot
schedule_was_enabled="$(python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
    print('true' if json.load(response)['enabled'] else 'false')
PY
)"
activation_state="$(mktemp /tmp/clipforge-terminal-cleanup.XXXXXX.json)"
chmod 600 "$activation_state"
restore_schedule() {
  python3 - "$schedule_was_enabled" <<'PY'
import sys, time, urllib.request
data = ('{"enabled":' + sys.argv[1] + '}').encode()
for attempt in range(45):
    try:
        req = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule',
            data=data, headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=5): pass
        break
    except Exception:
        if attempt == 44: raise
        time.sleep(2)
PY
}
trap 'restore_schedule || echo "Cron switch could not be restored; check backend health." >&2; rm -f "$activation_state"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 - <<'PY'
import urllib.request
req = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule',
    data=b'{"enabled":false}', headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=15): pass
PY
python3 scripts/wait-for-backend-idle.py --state-file "$activation_state" \
  --recover-stalled-cron --allow-capacity-wait --wait-seconds 21600
"${compose[@]}" --env-file .env up -d --no-deps --no-build --force-recreate backend telegram-bot
python3 - <<'PY'
import json, pathlib, sys, time, urllib.request
sys.path.insert(0, str(pathlib.Path('backend').resolve()))
import deployment_runtime
expected = deployment_runtime.release_id(deployment_runtime.fingerprint(pathlib.Path('backend')))
for attempt in range(90):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=3) as response:
            assert json.load(response)['status'] == 'ok'
        with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/long-production', timeout=10) as response:
            cleanup = json.load(response)['terminal_output_cleanup']
        assert cleanup['enabled'] is True and cleanup['max_recovery_attempts'] == 3
        deployment = json.loads(pathlib.Path('backend/data/deployment/backend.json').read_text())
        assert deployment['release_id'] == expected and deployment['source_verified'] is True
        break
    except Exception:
        if attempt == 89: raise
        time.sleep(1)
record = dict(verified=True, verified_at=time.time(), backend_release=expected,
              terminal_output_cleanup=cleanup)
pathlib.Path('reports/terminal-output-cleanup-activation.json').write_text(json.dumps(record, indent=2)+'\n')
print('Backend release and automatic terminal-output cleanup verified.')
PY
restore_schedule
rm -f "$activation_state"
trap - EXIT
echo "Cron terminal-output cleanup activated; previous cron switch restored."
