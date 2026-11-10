#!/usr/bin/env bash
# Deploy the cron-only director and renderer after active jobs/uploads drain.
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
assert state.get('cron_director_effects_policy_version') == 3
assert state.get('cron_source_process_limit') == 2
assert state.get('cron_follow_cta_adaptive') is True
assert state.get('tiktok_automatic_retry_enabled') is True
assert state.get('tiktok_automatic_retry_limit') == 3
assert state.get('tiktok_strategy_version') == 3
print(json.dumps({key: state.get(key) for key in ('enabled', 'scheduler_running', 'cron_director_effects_required', 'cron_director_effects_policy_version', 'cron_source_process_limit', 'cron_follow_cta_adaptive')}, indent=2))
print('Director accents required for new cron renders. Check each result sidecar for rendered cues.')
PY
