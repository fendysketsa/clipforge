#!/usr/bin/env bash
# Deploy the cron-only director and renderer after active jobs/uploads drain.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for argument in "$@"; do
  if [[ "$argument" == --help || "$argument" == -h ]]; then
    exec bash "$ROOT_DIR/scripts/activate-youtube-quiet-check.sh" --help
  fi
done
bash "$ROOT_DIR/scripts/activate-youtube-quiet-check.sh" --recover-stalled-cron --preserve-browser "$@"
python - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
    state = json.load(response)
assert state.get('cron_director_effects_required') is True
assert state.get('cron_director_effects_policy_version') == 2
assert state.get('cron_source_process_limit') == 2
assert state.get('cron_follow_cta_adaptive') is True
assert state.get('tiktok_automatic_retry_enabled') is True
assert state.get('tiktok_automatic_retry_limit') == 3
assert state.get('tiktok_strategy_version') == 3
print(json.dumps({key: state.get(key) for key in ('enabled', 'scheduler_running', 'cron_director_effects_required', 'cron_director_effects_policy_version', 'cron_source_process_limit', 'cron_follow_cta_adaptive')}, indent=2))
print('Director accents required for new cron renders. Check each result sidecar for rendered cues.')
PY
