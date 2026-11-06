#!/usr/bin/env bash
# Deploy the independent Long review lane, then start today's production.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT_DIR/scripts/activate-youtube-quiet-check.sh" --recover-stalled-cron --ryuundy-learning "$@"
cd "$ROOT_DIR"
python - <<'PY'
import json
from pathlib import Path
import urllib.request
url = 'http://127.0.0.1:8010/api/automation/viral-cc/long-production'
request = urllib.request.Request(url, data=b'{"enabled":true,"daily_target":1}',
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=30) as response:
    state = json.load(response)
Path('reports/ryuundy-long-activation.json').write_text(json.dumps(state, indent=2) + '\n')
print(json.dumps(state, ensure_ascii=False, indent=2))
status = state['production']['status']
if status == 'queued':
    print('Long production STARTED: ' + state['production']['job_id'] + '; review required before publication.')
elif status == 'daily_target_reached':
    print('Today already has a completed Long; inspect the checkpoint and output before calling it ready.')
else:
    print('Long production enabled but not started yet: ' + status + '. Inspect live jobs/checkpoint.')
PY
