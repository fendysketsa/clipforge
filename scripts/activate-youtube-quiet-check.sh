#!/usr/bin/env bash
# Activate quiet status checks and cron upload recovery while actual work is idle.
set -euo pipefail
# Bash normally reads later commands from the file after a long-running wait.
# Execute a validated, in-memory copy so editing the source cannot corrupt a
# deployment already waiting for work to finish.
activation_script_path="$(realpath -- "${BASH_SOURCE[0]:-$0}")"
if [[ "${CLIPFORGE_ACTIVATION_SNAPSHOT:-}" != "$activation_script_path" ]]; then
  activation_script_text="$(< "$activation_script_path")"
  bash -n <<< "$activation_script_text"
  export CLIPFORGE_ACTIVATION_SNAPSHOT="$activation_script_path"
  exec bash -c "$activation_script_text" "$activation_script_path" "$@"
fi
unset CLIPFORGE_ACTIVATION_SNAPSHOT
ROOT_DIR="$(cd "$(dirname "$activation_script_path")/.." && pwd)"
cd "$ROOT_DIR"
recover_stalled_cron=false
ryuundy_learning=false
skip_build=false
preserve_browser=false
force_active=false
allow_capacity_wait=false
wait_seconds=21600
while (( $# )); do
  case "$1" in
    --recover-stalled-cron) recover_stalled_cron=true ;;
    --ryuundy-learning) ryuundy_learning=true ;;
    --skip-build) skip_build=true ;;
    --preserve-browser) preserve_browser=true ;;
    --force-active) force_active=true ;;
    --allow-capacity-wait) allow_capacity_wait=true ;;
    --no-wait) wait_seconds=0 ;;
    --wait-seconds)
      [[ "${2:-}" =~ ^[0-9]+$ ]] || { echo "--wait-seconds requires a nonnegative integer." >&2; exit 2; }
      wait_seconds="$2"
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--recover-stalled-cron] [--ryuundy-learning] [--preserve-browser] [--skip-build] [--force-active] [--wait-seconds N | --no-wait]"
      echo "Waits up to six hours for active work; --skip-build verifies and reuses the built image."
      echo "--force-active interrupts current work, preserves upload checkpoints, and restarts without waiting for idle."
      echo "--allow-capacity-wait preserves sleeping cron batches while still requiring idle render/upload queues."
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
modules=(api clipper llm cron_director_effects cron_short_director cron_source_policy automatic_retry tiktok_strategy youtube_remote_status ryuundy_reference_learning long_video_qc shorts_thumbnail)
activation_report=reports/cron-upload-recovery-activation.json
if [[ "$preserve_browser" == true ]]; then
  modules+=(youtube_uploader tiktok_uploader youtube_blocked_cleanup)
  activation_report=reports/youtube-browser-preservation-activation.json
fi
if [[ "$ryuundy_learning" == true ]]; then
  modules+=(ryuundy_motion)
  activation_report=reports/ryuundy-reference-learning-activation.json
fi
if (( EUID != 0 )); then
  echo "Run: sudo bash $ROOT_DIR/scripts/activate-youtube-quiet-check.sh" >&2
  exit 77
fi
lock=/tmp/clipforge-recreate-compose-up.lock
[[ ! -L "$lock" ]] || exit 73
if [[ ! -e "$lock" ]]; then
  (set -o noclobber; umask 000; : >"$lock") 2>/dev/null || true
fi
exec 9<"$lock"
flock -n 9 || { echo "Another ClipForge deployment is active." >&2; exit 75; }
module_paths=()
for module in "${modules[@]}"; do module_paths+=("backend/$module.py"); done
python -m py_compile "${module_paths[@]}"
# Refresh the durable image first; restart the existing container to retain
# its exact environment, mounts, and network settings.
if [[ "$skip_build" != true ]]; then
  python scripts/build-backend-image.py
fi
image_id="$(docker image inspect clipforge-backend:latest --format '{{.Id}}')"
verify_image_sources() {
  python - "$image_id" "${modules[@]}" <<'PY'
import hashlib, pathlib, subprocess, sys
lines = subprocess.check_output([
    'docker', 'run', '--rm', '--network', 'none', '--read-only',
    '--entrypoint', 'sha256sum', sys.argv[1],
] + ['/app/' + name + '.py' for name in sys.argv[2:]], text=True).splitlines()
actual = dict((line.split()[1], line.split()[0]) for line in lines)
for name in sys.argv[2:]:
    expected = hashlib.sha256(pathlib.Path('backend/' + name + '.py').read_bytes()).hexdigest()
    if actual.get('/app/' + name + '.py') != expected:
        raise SystemExit('Built image does not match backend/' + name + '.py; rerun without --skip-build.')
if 'ryuundy_motion' in sys.argv[2:]:
    decoders = subprocess.check_output([
        'docker', 'run', '--rm', '--network', 'none', '--read-only',
        '--entrypoint', 'ffmpeg', sys.argv[1], '-hide_banner', '-decoders',
    ], text=True, stderr=subprocess.STDOUT)
    if 'librsvg' not in decoders:
        raise SystemExit('Built backend lacks the SVG decoder required for motion inserts; cron was not paused.')
PY
}
verify_image_sources
schedule_was_enabled="$(python - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8010/api/automation/viral-cc/schedule', timeout=15) as response:
    print('true' if json.load(response)['enabled'] else 'false')
PY
)"
activation_state="$(mktemp /tmp/clipforge-cron-upload-activation.XXXXXX.json)"
chmod 600 "$activation_state"
restore_schedule() {
  python - "$schedule_was_enabled" <<'PY'
import sys, time, urllib.request
data = ('{"enabled":' + sys.argv[1] + '}').encode()
for attempt in range(30):
    try:
        request = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule', data=data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=5): pass
        break
    except Exception:
        if attempt == 29: raise
        time.sleep(2)
PY
}
trap 'restore_schedule || echo "Check the cron switch: restoring it failed." >&2; rm -f "$activation_state"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python - <<'PY'
import urllib.request
request = urllib.request.Request('http://127.0.0.1:8010/api/automation/viral-cc/schedule', data=b'{"enabled":false}', headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=15): pass
PY
idle_args=(--state-file "$activation_state")
if [[ "$recover_stalled_cron" == true ]]; then idle_args+=(--recover-stalled-cron); fi
if [[ "$allow_capacity_wait" == true ]]; then idle_args+=(--allow-capacity-wait); fi
if [[ "$force_active" != true ]]; then
  echo "Future cron launches paused; waiting for existing work to finish (limit ${wait_seconds}s)."
  python scripts/wait-for-backend-idle.py "${idle_args[@]}" --wait-seconds "$wait_seconds"
else
  echo "Future cron launches paused. Explicit force mode: interrupting active work after source verification; no idle wait."
fi
# Source may have changed while draining jobs. Keep the durable image and the
# staged runtime modules consistent before touching the existing container.
verify_image_sources
if ! docker exec fendy-clipper-backend python -c 'from PIL import Image, ImageDraw, ImageFont'; then
  docker exec fendy-clipper-backend python -m pip install 'Pillow>=10.2,<13'
fi
if [[ "$preserve_browser" == true ]]; then
  # no_defaults is needed even for cookie-only background CDP attaches.
  # Upgrade only after draining work, and keep the built image durable too.
  if ! docker exec fendy-clipper-backend python -c 'import inspect; from playwright.sync_api import BrowserType; assert "no_defaults" in inspect.signature(BrowserType.connect_over_cdp).parameters'; then
    docker exec fendy-clipper-backend python -m pip install 'playwright>=1.64.1,<2.0.0'
  fi
fi
for module in "${modules[@]}"; do
  docker cp "backend/$module.py" "fendy-clipper-backend:/app/$module.py.quiet-check"
done
docker exec fendy-clipper-backend python -c 'import pathlib,sys,subprocess; [compile(pathlib.Path(f"/app/{name}.py.quiet-check").read_text(), name, "exec") for name in sys.argv[1:]]; assert "ryuundy_motion" not in sys.argv[1:] or "librsvg" in subprocess.check_output(["ffmpeg", "-hide_banner", "-decoders"], text=True, stderr=subprocess.STDOUT), "Runtime FFmpeg lacks the SVG decoder"' "${modules[@]}"
if [[ "$force_active" == true ]]; then
  python scripts/force-backend-activation.py --state-file "$activation_state" "${modules[@]}"
else
  python scripts/wait-for-backend-idle.py "${idle_args[@]}" --wait-seconds 0
  docker exec fendy-clipper-backend python -c 'import os,sys; [os.replace(f"/app/{name}.py.quiet-check", f"/app/{name}.py") for name in sys.argv[1:]]' "${modules[@]}"
  docker restart fendy-clipper-backend >/dev/null
fi
python - <<'PY'
import time, urllib.request
for attempt in range(90):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=3): pass
        break
    except Exception:
        if attempt == 89: raise
        time.sleep(1)
PY
for module in "${modules[@]}"; do
  expected="$(sha256sum "backend/$module.py")"
  actual="$(docker exec fendy-clipper-backend sha256sum "/app/$module.py")"
  [[ "${expected%% *}" == "${actual%% *}" ]] || { echo "Runtime source verification failed: $module" >&2; exit 1; }
done
docker exec fendy-clipper-backend python -c 'import inspect,youtube_remote_status as m; assert "new_page" not in inspect.getsource(m)'
if [[ "$preserve_browser" == true ]]; then
  docker exec fendy-clipper-backend python -c 'import ast,inspect,pathlib; from playwright.sync_api import BrowserType; assert "no_defaults" in inspect.signature(BrowserType.connect_over_cdp).parameters; paths=[pathlib.Path("/app/"+n+".py") for n in ("youtube_uploader","tiktok_uploader","youtube_remote_status","youtube_blocked_cleanup")]; calls=[n for p in paths for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="connect_over_cdp"]; assert calls and all(any(k.arg=="no_defaults" and isinstance(k.value,ast.Constant) and k.value.value is True for k in n.keywords) for n in calls)'
fi
if [[ "$ryuundy_learning" == true ]]; then
  docker exec fendy-clipper-backend python -c 'from ryuundy_reference_learning import meaningful_trend_tokens; assert meaningful_trend_tokens("com www jangan roblox") == {"roblox"}'
  docker exec fendy-clipper-backend python -c 'from ryuundy_motion import KINDS; assert {"freeze_inset", "cutout_stop_motion", "step_diagram"} <= KINDS'
fi
restore_schedule
trap 'rm -f "$activation_state"' EXIT
python - "$activation_state" "$schedule_was_enabled" "$activation_report" "${modules[@]}" <<'PY'
import hashlib, json, pathlib, sys, time, urllib.request
base = 'http://127.0.0.1:8010/api/'
state = json.loads(pathlib.Path(sys.argv[1]).read_text())
for attempt in range(90):
    with urllib.request.urlopen(base + 'automation/viral-cc/schedule', timeout=10) as response:
        schedule = json.load(response)
    if not schedule['enabled'] and sys.argv[2] == 'false':
        break
    with urllib.request.urlopen(base + 'automation/viral-cc', timeout=10) as response:
        runs = {row['id']: row for row in json.load(response)}
    recovered = all(runs.get(run_id, {}).get('status') in {'failed', 'completed', 'cancelled'} for run_id in state['stalled_run_ids'])
    if recovered and schedule['enabled'] and schedule['scheduler_running'] and (schedule['active_run_id'] not in state['stalled_run_ids']) and (schedule['active_run_id'] or schedule['next_run_at']):
        break
    if attempt == 89:
        raise SystemExit('Backend healthy, but cron recovery is not confirmed; inspect scheduler before declaring success.')
    time.sleep(1)
assert schedule['enabled'] == (sys.argv[2] == 'true')
state.update({'verified_at': time.time(), 'schedule': schedule, 'sha256': {
    name: hashlib.sha256(pathlib.Path('backend/' + name + '.py').read_bytes()).hexdigest()
    for name in sys.argv[4:]
}})
path = pathlib.Path(sys.argv[3])
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(schedule, ensure_ascii=False))
PY
rm -f "$activation_state"
trap - EXIT
echo "Quiet YouTube checks and cron recovery activated; runtime hashes and scheduler verified."
if [[ "$preserve_browser" == true ]]; then
  echo "Browser preservation activated; CDP defaults, upload modules, and runtime hashes verified."
fi
if [[ "$ryuundy_learning" == true ]]; then
  echo "RYUUNDY learning, selection cooldown, and motion inserts activated; all runtime module hashes verified."
fi
