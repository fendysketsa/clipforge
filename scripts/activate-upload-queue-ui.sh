#!/usr/bin/env bash
# Install the reviewed queue-order UI without restarting backend upload workers.
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
  echo "Activates the built queue UI and verifies its served assets; backend uploads keep running."
  exit 0
fi
(( $# == 0 )) || { echo "Unknown arguments" >&2; exit 2; }
export CLIPFORGE_BUILD_DIR=.next-queue
bash "$ROOT_DIR/scripts/activate-history-card-layout.sh"
cd "$ROOT_DIR"
python - <<'PY'
import json, pathlib, runpy, urllib.request
Assets = runpy.run_path('scripts/verify-history-frontend.py')['Assets']
parser = Assets()
with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=15) as response:
    parser.feed(response.read().decode())
javascript = ''
for path in sorted(parser.urls):
    if not path.split('?', 1)[0].endswith('.js'): continue
    with urllib.request.urlopen('http://127.0.0.1:3000' + path, timeout=15) as response:
        javascript += response.read().decode()
assert 'jobPlatformQueue' in javascript, 'Queue-order UI is not being served.'
assert 'clipforge:upload-request:' in javascript, 'Submission reconciliation guard is not being served.'
record = dict(verified=True, build_id=pathlib.Path('frontend/.next-queue/BUILD_ID').read_text().strip(),
              queue_positions=True, lost_response_reconciliation=True, backend_restarted=False)
pathlib.Path('reports/upload-queue-ui-activation.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
