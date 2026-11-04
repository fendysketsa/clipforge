#!/usr/bin/env bash
# Build first, drain active work, then activate without interrupting a render.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if (( EUID != 0 )); then
  echo "Run: sudo bash $ROOT_DIR/scripts/activate-cron-health-fix.sh" >&2
  exit 77
fi
if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
else
  compose=(docker-compose)
fi

# Use the same lock as the normal deployment command.
lock=/tmp/clipforge-recreate-compose-up.lock
if [[ -L "$lock" ]]; then exit 73; fi
if [[ ! -e "$lock" ]]; then
  (set -o noclobber; umask 000; : >"$lock") 2>/dev/null || true
fi
exec 9<"$lock"
flock -n 9 || { echo "Another ClipForge deployment is active." >&2; exit 75; }

# Preserve the actual container settings: .env may differ from the running
# deployment (for example, paired Long production may currently be disabled).
# Never print the override; it contains the existing service credentials.
runtime_override="$(mktemp /tmp/clipforge-cron-runtime.XXXXXX.json)"
chmod 600 "$runtime_override"
trap 'rm -f "$runtime_override"' EXIT
python - "$runtime_override" <<'PY'
import json, subprocess, sys
services = {}
for service, container in [('backend', 'fendy-clipper-backend'), ('frontend', 'fendy-clipper-frontend')]:
    payload = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
    environment = dict(entry.split('=', 1) for entry in payload['Config']['Env'])
    services[service] = {'environment': environment}
with open(sys.argv[1], 'w') as stream:
    json.dump({'services': services}, stream)
PY
compose+=(-f "$ROOT_DIR/docker-compose.yml" -f "$runtime_override")

python -m py_compile backend/api.py
"${compose[@]}" --env-file .env config --quiet
"${compose[@]}" --env-file .env build backend frontend

# The durable override only prevents NEW campaigns. Existing workers finish.
# Restore the original switch on every exit, including failed activation.
schedule_was_enabled="$(python - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
    print('true' if json.load(response)['enabled'] else 'false')
PY
)"
restore_schedule() {
  python - "$schedule_was_enabled" <<'PY'
import sys, time, urllib.request
data = ('{"enabled":' + sys.argv[1] + '}').encode()
for attempt in range(30):
    try:
        req = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule', data=data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=5): pass
        break
    except Exception:
        if attempt == 29: raise
        time.sleep(2)
PY
}
trap 'restore_schedule || echo "Could not restore cron switch; check backend health." >&2; rm -f "$runtime_override"' EXIT
python - <<'PY'
import urllib.request
req = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule', data=b'{"enabled":false}', headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=15): pass
PY

python - <<'PY'
import json, time, urllib.request
base = 'http://127.0.0.1:8010/api/'
deadline = time.monotonic() + 21600
while True:
    active = []
    for endpoint in ('jobs', 'youtube/uploads', 'tiktok/uploads', 'automation/viral-cc'):
        with urllib.request.urlopen(base + endpoint, timeout=20) as response:
            rows = json.load(response)
        active.extend(f"{endpoint}:{r['id'][:10]}" for r in rows if r.get('status') in {'queued', 'running'})
    if not active:
        break
    if time.monotonic() >= deadline:
        raise SystemExit('Activation postponed: active work did not finish within six hours.')
    print('Waiting for active work: ' + ', '.join(active), flush=True)
    time.sleep(15)
PY

"${compose[@]}" --env-file .env up -d --no-deps --no-build backend frontend
python - <<'PY'
import time, urllib.request
for url in ('http://127.0.0.1:8010/api/health', 'http://127.0.0.1:3000/'):
    for attempt in range(90):
        try:
            with urllib.request.urlopen(url, timeout=3): pass
            break
        except Exception:
            if attempt == 89: raise
            time.sleep(1)
PY

expected="$(sha256sum backend/api.py)"
actual="$(docker exec fendy-clipper-backend sha256sum /app/api.py)"
[[ "${expected%% *}" == "${actual%% *}" ]] || { echo "Backend source verification failed." >&2; exit 1; }
restore_schedule
rm -f "$runtime_override"
trap - EXIT
python - "$schedule_was_enabled" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
    state = json.load(response)
assert state['enabled'] == (sys.argv[1] == 'true'), state
if state['enabled']:
    assert state['scheduler_running'], state
print(json.dumps(state, ensure_ascii=False))
PY
echo "Cron health fix activated; backend source hash and scheduler verified."
