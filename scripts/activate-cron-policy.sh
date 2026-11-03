#!/usr/bin/env bash
# Run as root after the backend image has been rebuilt from the current source.
# Existing YouTube schedules are not edited by this activation script.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
exec 9</tmp/clipforge-recreate-compose-up.lock
flock -n 9
if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
else
  compose=(docker-compose)
fi
python - <<'PY'
import json,urllib.request
base='http://127.0.0.1:8010/api'
for path in ['jobs','youtube/uploads','tiktok/uploads']:
 with urllib.request.urlopen(base+'/'+path,timeout=15) as response: items=json.load(response)
 if any(item['status'] in ['queued','running'] for item in items):
  raise SystemExit('Activation postponed: active work in '+path)
with urllib.request.urlopen(base+'/automation/viral-cc/schedule',timeout=15) as response: status=json.load(response)
if status.get('active_run_id'):
 raise SystemExit('Activation postponed: active cron campaign')
PY
for filename in api.py youtube_uploader.py youtube_playlists.py; do
  expected=$(sha256sum "backend/$filename")
  actual=$(docker run --rm --entrypoint sha256sum clipforge-backend:latest "/app/$filename")
  if [[ "${expected%% *}" != "${actual%% *}" ]]; then
    echo "Image is stale for $filename; rebuild backend first." >&2
    exit 1
  fi
done
"${compose[@]}" up -d --no-deps --no-build backend
python - "${1:-}" <<'PY'
import json,sys,time,urllib.request
base='http://127.0.0.1:8010/api'
for attempt in range(90):
 try:
  with urllib.request.urlopen(base+'/health',timeout=2) as response: json.load(response)
  break
 except Exception:
  if attempt==89: raise
  time.sleep(1)
with urllib.request.urlopen(base+'/youtube/config',timeout=15) as response: config=json.load(response)
expected={'public_daily_limit':7,'public_min_gap_hours':2.25,'cron_private_buffer_limit':5,'scheduled_backlog_limit':11}
for name,value in expected.items():
 if config.get(name)!=value: raise SystemExit(f'Unexpected {name}: {config.get(name)}')
if len(config.get('short_publish_slots',[]))!=7:
 raise SystemExit('Expected seven publishing slots')
if sys.argv[1] == '--keep-cron-paused':
 print(json.dumps({'policy':{name:config[name] for name in expected},'slots':config['short_publish_slots'],'cron_enabled':False}))
 raise SystemExit(0)
request=urllib.request.Request(base+'/automation/viral-cc/schedule',data=b'{"enabled":true}',headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request,timeout=20) as response: status=json.load(response)
if not status.get('enabled') or not status.get('scheduler_running'):
 raise SystemExit('Cron worker did not start')
print(json.dumps({'policy':{name:config[name] for name in expected},'slots':config['short_publish_slots'],'cron_enabled':status['enabled'],'scheduler_running':status['scheduler_running']}))
PY
