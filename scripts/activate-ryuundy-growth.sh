#!/usr/bin/env bash
# Reuse the build/drain/recreate guard, then prove the growth policy is live.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
(( $# == 0 )) || { echo "No arguments expected." >&2; exit 2; }
bash scripts/activate-terminal-output-cleanup.sh
python3 - <<'PY'
import json, pathlib, time, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/growth', timeout=30) as response:
    growth = json.load(response)
assert growth['version'] == 1 and growth['learning_enabled'] is True
assert growth['configured_winner_share_percent'] == 75 and growth['lookback_days'] == 28
assert growth['minimum_age_hours'] >= 24 and growth['causal_claim'] is False
record = dict(verified=True, verified_at=time.time(), growth=growth)
pathlib.Path('reports/ryuundy-growth-activation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
print('RYUUNDY growth policy verified: 75% proven cohorts, 25% exploration; public mature Shorts only.')
PY
