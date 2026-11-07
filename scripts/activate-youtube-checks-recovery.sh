#!/usr/bin/env bash
# Repair the blocked CLI first, then deploy the automatic watchdog safely.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if (( EUID != 0 )); then
  echo "Run: sudo bash $ROOT_DIR/scripts/activate-youtube-checks-recovery.sh" >&2
  exit 77
fi
lock=/tmp/clipforge-recreate-compose-up.lock
[[ ! -L "$lock" ]] || exit 73
if [[ ! -e "$lock" ]]; then
  (set -o noclobber; umask 000; : >"$lock") 2>/dev/null || true
fi
exec 9<"$lock"
flock -n 9 || { echo "Another ClipForge deployment is active." >&2; exit 75; }
plan="$(docker exec fendy-clipper-backend python /app/scripts/recover-youtube-unknown-checks.py)"
echo "$plan"
if ! docker exec fendy-clipper-backend python -c 'import inspect; from playwright.sync_api import BrowserType; assert "no_defaults" in inspect.signature(BrowserType.connect_over_cdp).parameters'; then
  docker exec fendy-clipper-backend python -m pip install 'playwright>=1.64.1,<2.0.0'
fi
docker cp backend/youtube_uploader.py fendy-clipper-backend:/app/youtube_uploader.py.checks-recovery
docker exec fendy-clipper-backend python -c 'import pathlib,os; p=pathlib.Path("/app/youtube_uploader.py.checks-recovery"); compile(p.read_text(),str(p),"exec"); os.replace(p,"/app/youtube_uploader.py")'
expected="$(sha256sum backend/youtube_uploader.py)"
actual="$(docker exec fendy-clipper-backend sha256sum /app/youtube_uploader.py)"
[[ "${expected%% *}" == "${actual%% *}" ]] || exit 1
docker exec fendy-clipper-backend python -c 'import youtube_uploader as m; assert m.copyright_checks_all_clear("Pemeriksaan selesai. Tidak ditemukan masalah."); assert not m.copyright_checks_all_clear("Pemeriksaan selesai.")'
upload_id="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("upload_id", ""))' "$plan")"
if [[ -n "$upload_id" ]]; then
  docker exec fendy-clipper-backend python /app/scripts/recover-youtube-unknown-checks.py --upload-id "$upload_id" --apply | tee reports/youtube-checks-live-recovery.json
fi
flock -u 9
exec 9<&-
# Builds the durable image, pauses only new cron launches, drains active work,
# and verifies module hashes after restart. Existing work is allowed to finish.
exec bash scripts/activate-youtube-quiet-check.sh --preserve-browser
