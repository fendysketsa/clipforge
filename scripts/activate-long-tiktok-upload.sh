#!/usr/bin/env bash
# Enable independent, QC-approved Only-you intake for Long videos.
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
    exec bash "$ROOT_DIR/scripts/activate-cron-director-effects.sh" --help
  fi
done
bash "$ROOT_DIR/scripts/activate-cron-director-effects.sh" "$@"
cd "$ROOT_DIR"
python - <<'PY'
import hashlib, json, os, pathlib, tempfile, urllib.request
# Apply the reviewed timestamp carry correction to this exact existing Long.
# The encoded video and every other subtitle remain untouched.
repair_dir = pathlib.Path('reports/long-tiktok-subtitle-repair-20261110')
manifest = json.loads((repair_dir / 'preparation.json').read_text())
media = pathlib.Path(manifest['media'])
subtitle = pathlib.Path(manifest['subtitle'])
assert media.resolve().is_relative_to(pathlib.Path('backend/outputs').resolve())
assert subtitle == media.with_suffix('.srt')
if media.exists() and subtitle.exists():
    with media.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['media_sha256'], 'Long media changed; correction held.'
    current = hashlib.sha256(subtitle.read_bytes()).hexdigest()
    assert current in {manifest['before_sha256'], manifest['after_sha256']}, 'Subtitle changed; correction held.'
    if current == manifest['before_sha256']:
        replacement = (repair_dir / 'corrected.srt.txt').read_bytes()
        assert hashlib.sha256(replacement).hexdigest() == manifest['after_sha256']
        original = subtitle.stat()
        descriptor, name = tempfile.mkstemp(prefix='.subtitle-carry-', dir=subtitle.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(replacement)
            os.chmod(name, original.st_mode & 0o777)
            os.chown(name, original.st_uid, original.st_gid)
            os.replace(name, subtitle)
        finally:
            if os.path.exists(name): os.unlink(name)
    assert hashlib.sha256(subtitle.read_bytes()).hexdigest() == manifest['after_sha256']
    manifest['status'] = 'applied'
    (repair_dir / 'repair.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Exact Long subtitle timestamp corrected; encoded video unchanged. QC must review it again.')
url = 'http://127.0.0.1:8010/api/automation/viral-cc/long-production'
with urllib.request.urlopen(url, timeout=15) as response:
    old = json.load(response)
assert old.get('tiktok_qc_upload_supported') is True, 'New Long/TikTok worker is not active.'
payload = dict(enabled=old['enabled'], daily_target=old['daily_target'],
               auto_qc_enabled=True, auto_qc_private_upload=True, auto_qc_tiktok_upload=True)
request = urllib.request.Request(url, data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=90) as response:
    state = json.load(response)
assert state.get('auto_qc_tiktok_upload') is True and state.get('auto_qc_enabled') is True
summary = {key: state.get(key) for key in ('enabled', 'daily_target', 'auto_qc_enabled',
    'auto_qc_private_upload', 'auto_qc_tiktok_upload', 'tiktok_qc_upload_supported', 'production')}
pathlib.Path('reports/long-tiktok-activation.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
print('QC-approved Long videos enter TikTok Only you independently of YouTube. Rejected sources stay held.')
PY
# Install the already built status UI after backend verification.
bash "$ROOT_DIR/scripts/activate-history-card-layout.sh"
python - <<'PY'
import json, pathlib, runpy, urllib.request
assets = runpy.run_path('scripts/verify-history-frontend.py')['check_frontend']()
javascript = ''
for path in assets['js']:
    with urllib.request.urlopen('http://127.0.0.1:3000' + path, timeout=15) as response:
        javascript += response.read().decode()
assert 'tiktok_upload_issue' in javascript and 'jobPlatformHold' in javascript, 'Long/TikTok status UI is stale.'
report = pathlib.Path('reports/long-tiktok-activation.json')
state = json.loads(report.read_text())
state['frontend_long_tiktok_status_verified'] = True
report.write_text(json.dumps(state, indent=2) + '\n')
print('Long/TikTok status UI verified on port 3000.')
PY
