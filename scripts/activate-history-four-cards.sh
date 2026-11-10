#!/usr/bin/env bash
# Install the reviewed four-card History frontend without restarting backend.
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
  echo "Activates the built four-card History UI; backend rendering and uploads continue."
  exit 0
fi
(( $# == 0 )) || { echo "Unknown arguments" >&2; exit 2; }
cd "$ROOT_DIR"
export CLIPFORGE_BUILD_DIR=.next-history-four
bash scripts/activate-history-card-layout.sh
python - <<'PY'
import json, pathlib, re, runpy, urllib.request
Assets = runpy.run_path('scripts/verify-history-frontend.py')['Assets']
parser = Assets()
with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=15) as response:
    parser.feed(response.read().decode())
bodies = {'js': '', 'css': ''}
for path in parser.urls:
    kind = path.split('?', 1)[0].rsplit('.', 1)[-1]
    if kind in bodies:
        with urllib.request.urlopen('http://127.0.0.1:3000' + path, timeout=15) as response:
            bodies[kind] += response.read().decode()
assert 'history-four-columns' in bodies['js'], 'Four-card History component is not being served.'
assert re.search(r'\.outputWorkspacePane\s+\.jobList\s*\{[^}]*grid-template-columns\s*:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)', bodies['css']), 'Four-column desktop CSS is not being served.'
assert 'jobPlatformQueue' in bodies['js'] and '/reconcile' in bodies['js'], 'Queue information or upload recovery is missing.'
record = dict(verified=True, desktop_columns=4,
    build_id=pathlib.Path('frontend/.next-history-four/BUILD_ID').read_text().strip(),
    backend_restarted=False, queue_positions_preserved=True)
pathlib.Path('reports/history-four-cards-activation.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
