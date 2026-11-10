#!/usr/bin/env bash
# Activate serialized lost-response recovery in backend and frontend together.
set -euo pipefail
activation_script_path="$(realpath -- "${BASH_SOURCE[0]:-$0}")"
if [[ "${CLIPFORGE_ACTIVATION_SNAPSHOT:-}" != "$activation_script_path" ]]; then
  activation_script_text="$(< "$activation_script_path")"
  bash -n <<< "$activation_script_text"
  export CLIPFORGE_ACTIVATION_SNAPSHOT="$activation_script_path"
  exec bash -c "$activation_script_text" "$activation_script_path" "$@"
fi
unset CLIPFORGE_ACTIVATION_SNAPSHOT
ROOT_DIR="$(cd -- "$(dirname -- "$activation_script_path")/.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  echo "Usage: sudo bash $activation_script_path"
  echo "Builds and verifies backend recovery, preserves waiting cron checkpoints, then installs the built frontend."
  echo "Active render/upload workers must finish; sleeping capacity waits do not impose a six-hour delay."
  exit 0
fi
(( $# == 0 )) || { echo "Unknown arguments" >&2; exit 2; }
(( EUID == 0 )) || { echo "Docker activation requires sudo." >&2; exit 77; }
cd "$ROOT_DIR"
test -f frontend/.next-submission/BUILD_ID
bash scripts/activate-youtube-quiet-check.sh --recover-stalled-cron --preserve-browser --allow-capacity-wait --wait-seconds 600
python - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/openapi.json', timeout=15) as response:
    paths = json.load(response)['paths']
for platform in ('youtube', 'tiktok'):
    assert 'post' in paths[f'/api/jobs/{{job_id}}/{platform}-uploads/reconcile'], platform
print('Backend serialized submission recovery endpoints verified.')
PY
export CLIPFORGE_BUILD_DIR=.next-submission
bash scripts/activate-history-card-layout.sh
python - <<'PY'
import hashlib, json, pathlib, runpy, time, urllib.request
Assets = runpy.run_path('scripts/verify-history-frontend.py')['Assets']
parser = Assets()
with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=15) as response:
    parser.feed(response.read().decode())
javascript = ''
for path in parser.urls:
    if path.split('?', 1)[0].endswith('.js'):
        with urllib.request.urlopen('http://127.0.0.1:3000' + path, timeout=15) as response:
            javascript += response.read().decode()
assert 'clipforge:upload-request:' in javascript and '/reconcile' in javascript
assert 'Hasil pengiriman sebelumnya belum pasti.' not in javascript
record = dict(verified_at=time.time(), verified=True,
    api_sha256=hashlib.sha256(pathlib.Path('backend/api.py').read_bytes()).hexdigest(),
    frontend_build_id=pathlib.Path('frontend/.next-submission/BUILD_ID').read_text().strip(),
    serialized_recovery=True, cron_checkpoints_preserved=True)
pathlib.Path('reports/upload-submission-recovery-activation.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
