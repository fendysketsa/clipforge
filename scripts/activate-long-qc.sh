#!/usr/bin/env bash
# Deploy only after active work drains, then opt the Long lane into AI QC.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT_DIR/scripts/activate-youtube-quiet-check.sh" --recover-stalled-cron --preserve-browser "$@"
cd "$ROOT_DIR"
python - <<'PY'
import json
from pathlib import Path
import urllib.request
url = 'http://127.0.0.1:8010/api/automation/viral-cc/long-production'
with urllib.request.urlopen(url, timeout=15) as response:
    previous = json.load(response)
payload = {'enabled': previous['enabled'], 'daily_target': previous['daily_target'],
           'auto_qc_enabled': True, 'auto_qc_private_upload': True}
request = urllib.request.Request(url, data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=30) as response:
    state = json.load(response)
assert state['auto_qc_enabled'] and state['auto_qc_private_upload']
Path('reports/long-qc-activation.json').write_text(json.dumps(state, indent=2) + '\n')
print(json.dumps({k: state.get(k) for k in (
    'auto_qc_enabled', 'auto_qc_private_upload', 'qc_vision_configured', 'qc_reviews')}, indent=2))
print('QC enabled. PASS may enter Private upload; existing upload checks remain required.')
if not state.get('qc_vision_configured'):
    print('Vision provider missing: hard-gate failures are reviewed; remaining results stay on hold.')
PY
