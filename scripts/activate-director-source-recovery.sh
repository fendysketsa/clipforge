#!/usr/bin/env bash
# Install grounded source recovery and its History status together.
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
  echo "Builds/verifies backend source recovery and installs its built History UI."
  echo "Preserves cron checkpoints and waits up to ten minutes for actual render/upload workers."
  exit 0
fi
(( $# == 0 )) || { echo "Unknown arguments" >&2; exit 2; }
(( EUID == 0 )) || { echo "Docker activation requires sudo." >&2; exit 77; }
cd "$ROOT_DIR"
test -f frontend/.next-director-recovery/BUILD_ID
bash scripts/activate-youtube-quiet-check.sh --recover-stalled-cron --preserve-browser --allow-capacity-wait --wait-seconds 600
export CLIPFORGE_BUILD_DIR=.next-director-recovery
bash scripts/activate-history-card-layout.sh
python - <<'PY'
import hashlib, json, pathlib, re, runpy, time, urllib.request
Assets = runpy.run_path('scripts/verify-history-frontend.py')['Assets']
with urllib.request.urlopen('http://127.0.0.1:8010/openapi.json', timeout=15) as response:
    schemas = json.load(response)['components']['schemas']
assert 'director_recovery' in schemas['ClipJob']['properties'], 'Backend source recovery schema is missing.'
assert 'cron_upload_recovery' in schemas['AutoViralScheduleStatus']['properties'], 'Cron recovery hook is missing.'
for attempt in range(45):
    with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
        cron_recovery = json.load(response).get('cron_upload_recovery', {})
    if not cron_recovery.get('enabled') or cron_recovery.get('last_tick_at'):
        break
    time.sleep(1)
else:
    raise SystemExit('Backend updated, but the autonomous cron recovery tick is not yet verified.')
parser = Assets()
with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=15) as response:
    parser.feed(response.read().decode())
bodies = {'js': '', 'css': ''}
for path in parser.urls:
    kind = path.split('?', 1)[0].rsplit('.', 1)[-1]
    if kind in bodies:
        with urllib.request.urlopen('http://127.0.0.1:3000' + path, timeout=15) as response:
            bodies[kind] += response.read().decode()
assert 'jobDirectorRecovery' in bodies['js'] and 'history-four-columns' in bodies['js']
assert 'jobPlatformQueue' in bodies['js'] and '/reconcile' in bodies['js']
assert re.search(r'\.outputWorkspacePane\s+\.jobList\s*\{[^}]*grid-template-columns\s*:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)', bodies['css'])
record = dict(verified=True, verified_at=time.time(),
    module_sha256={name:hashlib.sha256(pathlib.Path('backend/'+name+'.py').read_bytes()).hexdigest()
        for name in ('api','clipper','llm','cron_short_director','automatic_retry','tiktok_uploader','youtube_uploader')},
    frontend_build_id=pathlib.Path('frontend/.next-director-recovery/BUILD_ID').read_text().strip(),
    desktop_columns=4, queue_positions_preserved=True, cron_checkpoints_preserved=True,
    cron_upload_recovery=cron_recovery,
    note='Runtime verified; creative render outcomes require per-job evidence.')
pathlib.Path('reports/director-source-recovery-activation.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
PY
