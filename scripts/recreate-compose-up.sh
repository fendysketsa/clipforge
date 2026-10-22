#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FORCE_ACTIVE_REQUESTED=false
for arg in "$@"; do
  if [[ "$arg" == "--force-active" ]]; then
    FORCE_ACTIVE_REQUESTED=true
    break
  fi
done

# Only one rebuild may own BuildKit/containerd at a time. Parallel invocations
# can leave an image-export writer locked and produce the opaque
# "mount callback failed / failed to open writer" error.
RECREATE_LOCK_PATH="${RECREATE_LOCK_PATH:-/tmp/clipforge-recreate-compose-up.lock}"
if command -v flock >/dev/null 2>&1; then
  # Open the lock read-only. Linux fs.protected_regular can reject root's
  # write/truncate open on a user-owned file inside sticky /tmp (and the
  # inverse can happen after a sudo run), even when the mode bits look
  # writable. flock itself does not require a writable descriptor.
  if [[ -L "$RECREATE_LOCK_PATH" ]]; then
    echo "Refusing symlink recreate lock: ${RECREATE_LOCK_PATH}" >&2
    exit 73
  fi
  if [[ ! -e "$RECREATE_LOCK_PATH" ]]; then
    (
      set -o noclobber
      umask 000
      : >"$RECREATE_LOCK_PATH"
    ) 2>/dev/null || true
  fi
  if [[ ! -f "$RECREATE_LOCK_PATH" || ! -r "$RECREATE_LOCK_PATH" ]]; then
    echo "Lock recreate tidak aman/tidak dapat dibaca: ${RECREATE_LOCK_PATH}" >&2
    exit 73
  fi
  exec 9<"$RECREATE_LOCK_PATH"
  if ! flock -n 9; then
    if [[ "$FORCE_ACTIVE_REQUESTED" != "true" ]]; then
      echo "Rebuild ClipForge lain masih berjalan. Tunggu proses itu selesai; build kedua tidak dimulai." >&2
      exit 75
    fi
    if ! command -v fuser >/dev/null 2>&1; then
      echo "Mode paksa tidak dapat memverifikasi pemegang lock karena fuser tidak tersedia." >&2
      exit 75
    fi
    holder_pids="$(fuser "$RECREATE_LOCK_PATH" 2>/dev/null || true)"
    stopped_holder=false
    for holder_pid in $holder_pids; do
      if [[ ! "$holder_pid" =~ ^[0-9]+$ ]] || [[ ! -r "/proc/$holder_pid/cmdline" ]]; then
        continue
      fi
      holder_command="$(tr '\0' ' ' <"/proc/$holder_pid/cmdline")"
      if [[ "$holder_command" != *"$ROOT_DIR/scripts/recreate-compose-up.sh"* ]]; then
        echo "Menolak menghentikan PID $holder_pid karena bukan rebuild ClipForge: $holder_command" >&2
        continue
      fi
      echo "Mode paksa mengambil alih rebuild ClipForge lama (PID $holder_pid)."
      kill -TERM "$holder_pid"
      stopped_holder=true
    done
    if [[ "$stopped_holder" != "true" ]]; then
      echo "Pemegang lock tidak dapat diverifikasi sebagai rebuild ClipForge; pengambilalihan dibatalkan." >&2
      exit 75
    fi
    lock_acquired=false
    for _ in {1..20}; do
      if flock -n 9; then
        lock_acquired=true
        break
      fi
      sleep 0.5
    done
    if [[ "$lock_acquired" != "true" ]]; then
      echo "Rebuild lama belum melepas lock setelah dihentikan; pengambilalihan dibatalkan." >&2
      exit 75
    fi
  fi
fi

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/load-dotenv.sh"
load_dotenv "$ROOT_DIR/.env"

"$ROOT_DIR/scripts/prepare-youtube-gui-runtime.sh" --start-watcher

YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-}"
if [[ -z "$YOUTUBE_CDP_PORT" && "${YOUTUBE_CDP_URL:-}" =~ :([0-9]+)(/.*)?$ ]]; then
  YOUTUBE_CDP_PORT="${BASH_REMATCH[1]}"
fi
YOUTUBE_CDP_PORT="${YOUTUBE_CDP_PORT:-9222}"
TIKTOK_CDP_PORT="${TIKTOK_CDP_PORT:-}"
if [[ -z "$TIKTOK_CDP_PORT" && "${TIKTOK_CDP_URL:-}" =~ :([0-9]+)(/.*)?$ ]]; then
  TIKTOK_CDP_PORT="${BASH_REMATCH[1]}"
fi
TIKTOK_CDP_PORT="${TIKTOK_CDP_PORT:-9444}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME:-/tmp}/.config}"
YOUTUBE_LOGIN_PROFILE_DIR="${YOUTUBE_LOGIN_PROFILE_DIR:-$CONFIG_HOME/fendy-clipper/youtube-chrome-profile}"
if [[ "$YOUTUBE_LOGIN_PROFILE_DIR" == /app/data/* ]]; then
  YOUTUBE_LOGIN_PROFILE_DIR="$ROOT_DIR/backend/data/${YOUTUBE_LOGIN_PROFILE_DIR#/app/data/}"
fi
YOUTUBE_CHROME_LAUNCH_LOG="${YOUTUBE_CHROME_LAUNCH_LOG:-/tmp/fendy-clipper-youtube-chrome-launcher.log}"
TIKTOK_HOST_PROFILE_DIR="${TIKTOK_HOST_PROFILE_DIR:-$CONFIG_HOME/fendy-clipper/tiktok-chrome-profile}"
TIKTOK_HOST_CHROME_LAUNCH_LOG="${TIKTOK_HOST_CHROME_LAUNCH_LOG:-/tmp/fendy-clipper-tiktok-chrome-launcher.log}"
TIKTOK_UPLOAD_USE_CDP="${TIKTOK_UPLOAD_USE_CDP:-true}"
TIKTOK_CLOSE_CDP_AFTER_LOGIN="${TIKTOK_CLOSE_CDP_AFTER_LOGIN:-false}"
SOCIAL_BROWSER_SHARED="${SOCIAL_BROWSER_SHARED:-false}"
DOWN_FIRST=false
WATCH_CHROME=false
RESET_PROFILE=false
RESTORE_ONLY=false
FORCE_ACTIVE=false

for arg in "$@"; do
  case "$arg" in
    --down-first)
      DOWN_FIRST=true
      ;;
    --watch-chrome)
      WATCH_CHROME=true
      ;;
    --reset-profile)
      RESET_PROFILE=true
      ;;
    --restore)
      RESTORE_ONLY=true
      ;;
    --force-active)
      FORCE_ACTIVE=true
      DOWN_FIRST=true
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--down-first] [--force-active] [--watch-chrome] [--reset-profile] [--restore]" >&2
      exit 2
      ;;
  esac
done

wait_for_cdp() {
  local port="$1"
  local deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    if python - "$port" >/dev/null 2>&1 <<'PY'
import json
import sys
import urllib.request

port = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if not payload.get("webSocketDebuggerUrl"):
    raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_legacy_tiktok_cdp_proxy() {
  local legacy_port="${TIKTOK_LEGACY_CDP_PORT:-9444}"
  local proxy_log="${TIKTOK_LEGACY_CDP_PROXY_LOG:-/tmp/fendy-clipper-tiktok-cdp-proxy.log}"
  if [[ "$legacy_port" == "$YOUTUBE_CDP_PORT" ]]; then
    return 0
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:${legacy_port}/json/version" >/dev/null 2>&1; then
    echo "Endpoint kompatibilitas TikTok sudah siap di port ${legacy_port}."
    return 0
  fi
  if ! command -v socat >/dev/null 2>&1; then
    echo "Peringatan: socat tidak tersedia; backend lama perlu direcreate agar memakai browser bersama." >&2
    return 0
  fi
  nohup socat \
    "TCP-LISTEN:${legacy_port},bind=127.0.0.1,reuseaddr,fork" \
    "TCP:127.0.0.1:${YOUTUBE_CDP_PORT}" \
    >>"$proxy_log" 2>&1 &
  if ! wait_for_cdp "$legacy_port"; then
    echo "Peringatan: endpoint kompatibilitas TikTok gagal aktif; lihat ${proxy_log}." >&2
    return 0
  fi
  echo "Backend lama diarahkan ke browser bersama melalui port ${legacy_port}; tidak ada Chrome kedua."
}

wait_for_backend() {
  local deadline=$((SECONDS + 90))
  while (( SECONDS < deadline )); do
    if curl -fsS --max-time 2 http://127.0.0.1:8010/api/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_media_idle_before_recreate() {
  local timeout_seconds="${COMPOSE_IDLE_WAIT_SECONDS:-21600}"
  if [[ ! "$timeout_seconds" =~ ^[0-9]+$ ]] || (( timeout_seconds < 1 )); then
    timeout_seconds=21600
  fi
  local deadline=$((SECONDS + timeout_seconds))
  local state=""
  local check_status=0
  while true; do
    set +e
    state="$(python - <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8010/api/health", timeout=4):
        pass
except Exception:
    # A stopped/unreachable backend has no live worker to interrupt. Its
    # durable queued/running records are handled by startup recovery.
    raise SystemExit(0)

endpoints = (
    ("clip", "http://127.0.0.1:8010/api/jobs"),
    ("YouTube", "http://127.0.0.1:8010/api/youtube/uploads"),
    ("TikTok", "http://127.0.0.1:8010/api/tiktok/uploads"),
    ("automation", "http://127.0.0.1:8010/api/automation/viral-cc"),
)
active = []
for label, url in endpoints:
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            payload = json.load(response)
    except Exception as exc:
        print(f"Tidak dapat memeriksa {label}: {exc}", file=sys.stderr)
        raise SystemExit(11)
    for item in payload if isinstance(payload, list) else []:
        if item.get("status") in {"queued", "running"}:
            identity = str(item.get("id") or "unknown")[:10]
            stage = str(item.get("progress_stage") or item.get("status") or "-")
            active.append(f"{label}:{identity}:{stage}")

if active:
    print(", ".join(active))
    raise SystemExit(10)
PY
    )"
    check_status=$?
    set -e

    if (( check_status == 0 )); then
      echo "Tidak ada render/upload/automation aktif; container aman direcreate."
      return 0
    fi
    if (( check_status != 10 )); then
      echo "Pemeriksaan pekerjaan aktif gagal (status ${check_status}); rebuild dihentikan agar aman." >&2
      return 1
    fi
    if (( SECONDS >= deadline )); then
      echo "Batas tunggu pekerjaan aktif tercapai; rebuild tidak memotong proses: ${state}" >&2
      return 1
    fi
    echo "Menunggu pekerjaan media selesai sebelum recreate: ${state}"
    sleep 15
  done
}

cancel_active_clipforge_work() {
  python - <<'PY'
import json
import urllib.error
import urllib.request

base = "http://127.0.0.1:8010"

def load(path):
    with urllib.request.urlopen(base + path, timeout=8) as response:
        return json.load(response)

def post(path):
    request = urllib.request.Request(base + path, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

try:
    load("/api/health")
except Exception:
    print("Backend sudah berhenti; tidak ada worker API yang perlu dibatalkan.")
    raise SystemExit(0)

stopped = []
try:
    runs = load("/api/automation/viral-cc")
    for run in runs if isinstance(runs, list) else []:
        if run.get("status") not in {"queued", "running"}:
            continue
        run_id = str(run.get("id") or "")
        if run_id:
            post(f"/api/automation/viral-cc/{run_id}/cancel")
            stopped.append(f"automation:{run_id[:10]}")
except urllib.error.HTTPError as exc:
    # Older containers do not expose the automation cancel endpoint. Compose
    # down below still terminates the container and every child subprocess.
    if exc.code != 404:
        raise

jobs = load("/api/jobs")
for job in jobs if isinstance(jobs, list) else []:
    if job.get("status") not in {"queued", "running"}:
        continue
    job_id = str(job.get("id") or "")
    if job_id:
        post(f"/api/jobs/{job_id}/cancel")
        stopped.append(f"clip:{job_id[:10]}")

print(
    "Permintaan stop dikirim: " + ", ".join(stopped)
    if stopped
    else "Tidak ada render/automation aktif pada API."
)
PY
}

tiktok_saved_session_ready() {
  python - <<'PY' >/dev/null 2>&1
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8010/api/tiktok/config", timeout=5) as response:
    payload = json.load(response)
if not payload.get("auth_state_exists"):
    raise SystemExit(1)
PY
}

if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  # Some deployments still provide the standalone Compose binary. Selecting it
  # explicitly avoids `docker: unknown command: docker compose` during rebuild.
  compose_cmd=(docker-compose)
else
  echo "Docker Compose tidak ditemukan (plugin 'docker compose' atau binary 'docker-compose')." >&2
  exit 1
fi

compose_up_with_retry() {
  local max_attempts="${COMPOSE_BUILD_RETRY_ATTEMPTS:-4}"
  if [[ ! "$max_attempts" =~ ^[0-9]+$ ]] || (( max_attempts < 1 )); then
    max_attempts=4
  fi
  local attempt=1
  local status=1
  local log_file=""
  local delay_seconds=0
  while (( attempt <= max_attempts )); do
    log_file="$(mktemp /tmp/clipforge-compose-build.XXXXXX.log)"
    chmod 600 "$log_file"
    echo "Build/recreate ClipForge percobaan ${attempt}/${max_attempts}..."
    set +e
    "${compose_cmd[@]}" --env-file .env up -d --build --force-recreate \
      backend telegram-bot frontend 2>&1 | tee "$log_file"
    status=${PIPESTATUS[0]}
    set -e
    if (( status == 0 )); then
      rm -f "$log_file"
      return 0
    fi
    if (( attempt >= max_attempts )) || ! grep -Eqi \
      'mount callback failed|failed to open writer: ref .* locked|rpc error: code = Unavailable|failed to solve:.*unavailable' \
      "$log_file"; then
      echo "Build gagal permanen; log terakhir: ${log_file}" >&2
      return "$status"
    fi
    rm -f "$log_file"
    delay_seconds=$((attempt * 20))
    echo "Lock sementara BuildKit/containerd terdeteksi. Menunggu ${delay_seconds} detik lalu melanjutkan dari cache..." >&2
    sleep "$delay_seconds"
    attempt=$((attempt + 1))
  done
  return "$status"
}

privilege_cmd=()
if [[ "$RESTORE_ONLY" != "true" ]] && ! docker info >/dev/null 2>&1; then
  privilege_cmd=(sudo)
  compose_cmd=(sudo "${compose_cmd[@]}")
fi

if [[ "$RESTORE_ONLY" == "true" && "$DOWN_FIRST" == "true" ]]; then
  echo "--restore tidak dapat digabungkan dengan --down-first." >&2
  exit 2
fi

# Music is a build/setup asset, never a render-time dependency. The sync tool
# is hash-pinned and only contacts allowlisted CC0 source hosts for a file that
# is missing or invalid. A transient network failure must not break a rebuild;
# the runtime loader will simply reject any incomplete asset.
if [[ "$RESTORE_ONLY" != "true" && "${BACKGROUND_MUSIC_SYNC_ON_REBUILD:-true}" == "true" ]]; then
  music_sync_python=""
  if command -v python3 >/dev/null 2>&1; then
    music_sync_python="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    music_sync_python="$(command -v python)"
  fi
  if [[ -z "$music_sync_python" ]]; then
    echo "Peringatan: Python host tidak ada; verifikasi backsound lokal dilewati." >&2
  elif ! "$music_sync_python" "$ROOT_DIR/scripts/sync-background-music-library.py"; then
    echo "Peringatan: sinkronisasi backsound CC0 gagal; rebuild tetap jalan tanpa download saat render." >&2
  fi
fi

# Generator Cerita depends on a real image provider. Start and health-check the
# installed local Z-Image service before recreating the backend so a missing
# provider can never degrade into procedural rectangle art.
image_provider="${LONG_ANIMATE_IMAGE_PROVIDER:-}"
image_base_url="${LONG_ANIMATE_IMAGE_BASE_URL:-}"
if [[ "$image_provider" =~ ^(stable-diffusion-cpp|stable_diffusion_cpp|sdcpp)$ ]] \
  || [[ "$image_base_url" =~ ^http://(127\.0\.0\.1|localhost|\[::1\]):7860(/|$) ]]; then
  "$ROOT_DIR/scripts/start-local-image-model.sh"
fi

if [[ "$FORCE_ACTIVE" == "true" ]]; then
  echo "Mode paksa: membatalkan worker API lalu menghentikan seluruh container ClipForge."
  cancel_active_clipforge_work || echo "Peringatan: cancel API tidak lengkap; compose down tetap dilanjutkan." >&2
fi

if [[ "$DOWN_FIRST" == "true" ]]; then
  "${compose_cmd[@]}" --env-file .env down --remove-orphans
fi

if [[ "$RESET_PROFILE" == "true" ]]; then
  if [[ -z "$YOUTUBE_LOGIN_PROFILE_DIR" || "$YOUTUBE_LOGIN_PROFILE_DIR" == "/" || "$YOUTUBE_LOGIN_PROFILE_DIR" == "$HOME" ]]; then
    echo "Refusing to reset unsafe profile path: ${YOUTUBE_LOGIN_PROFILE_DIR}" >&2
    exit 2
  fi
  echo "Resetting YouTube Chrome CDP profile: ${YOUTUBE_LOGIN_PROFILE_DIR}"
  pkill -f "remote-debugging-port=${YOUTUBE_CDP_PORT}" || true
  sleep 2
  rm -rf "$YOUTUBE_LOGIN_PROFILE_DIR"
fi

existing_cdp="$(pgrep -af "remote-debugging-port=${YOUTUBE_CDP_PORT}" || true)"
if [[ -n "$existing_cdp" ]] && ! grep -F -- "$YOUTUBE_LOGIN_PROFILE_DIR" <<<"$existing_cdp" >/dev/null; then
  echo "Stopping old YouTube Chrome CDP on port ${YOUTUBE_CDP_PORT} because it uses a different profile..."
  pkill -f "remote-debugging-port=${YOUTUBE_CDP_PORT}" || true
  sleep 2
fi

if pgrep -af "remote-debugging-port=${YOUTUBE_CDP_PORT}.*${YOUTUBE_LOGIN_PROFILE_DIR}" >/dev/null 2>&1; then
  echo "YouTube login Chrome already running on CDP port ${YOUTUBE_CDP_PORT}."
else
  echo "Starting YouTube login Chrome in background..."
  nohup "$ROOT_DIR/scripts/open-youtube-login-chrome.sh" >>"$YOUTUBE_CHROME_LAUNCH_LOG" 2>&1 &
  echo "YouTube login Chrome launcher log: ${YOUTUBE_CHROME_LAUNCH_LOG}"
fi

if ! wait_for_cdp "$YOUTUBE_CDP_PORT"; then
  echo "Chrome remote debugging is not responding on http://127.0.0.1:${YOUTUBE_CDP_PORT}." >&2
  echo "Open the launcher log for the exact cause: ${YOUTUBE_CHROME_LAUNCH_LOG}" >&2
  echo "Last launcher log lines:" >&2
  tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
  exit 1
fi
echo "Chrome remote debugging ready on http://127.0.0.1:${YOUTUBE_CDP_PORT}."

if [[ "$SOCIAL_BROWSER_SHARED" == "true" ]]; then
  start_legacy_tiktok_cdp_proxy
fi

if [[ "$RESTORE_ONLY" == "true" ]]; then
  echo "Mode restore: menunggu container yang dipulihkan Docker restart policy..."
else
  wait_for_media_idle_before_recreate
  compose_up_with_retry
fi

if ! wait_for_cdp "$YOUTUBE_CDP_PORT"; then
  echo "Chrome remote debugging stopped after containers were recreated." >&2
  echo "Last launcher log lines:" >&2
  tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
  exit 1
fi
echo "Chrome remote debugging tetap siap setelah stack diperiksa."

if ! wait_for_backend; then
  echo "Backend ClipForge tidak siap di http://127.0.0.1:8010 setelah container dibuat ulang." >&2
  exit 1
fi
echo "Backend ClipForge ready on http://127.0.0.1:8010."

# The saved storage-state lives in ./backend/data, so it survives a container
# recreate. Reuse the already-authenticated host Chrome over CDP; never start
# the login flow again merely because containers were recreated. Shared mode
# keeps YouTube and TikTok in two tabs of that same browser.
if [[ "$SOCIAL_BROWSER_SHARED" == "true" ]]; then
  if [[ "$TIKTOK_CDP_PORT" != "$YOUTUBE_CDP_PORT" ]]; then
    echo "SOCIAL_BROWSER_SHARED=true membutuhkan TIKTOK_CDP_URL dan YOUTUBE_CDP_URL pada port yang sama." >&2
    exit 2
  fi
  echo "Browser bersama siap: tab YouTube Studio dan TikTok Studio memakai satu proses Chrome."
elif tiktok_saved_session_ready; then
  if [[ "$TIKTOK_UPLOAD_USE_CDP" == "true" ]] \
    && ! pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" >/dev/null 2>&1; then
    echo "Menjalankan kembali profile TikTok yang sudah login dalam keadaan minimized..."
    TIKTOK_CHROMIUM_USER_DATA_DIR="$TIKTOK_HOST_PROFILE_DIR" \
      TIKTOK_LOGIN_URL=https://www.tiktok.com/tiktokstudio/upload \
      TIKTOK_CHROME_BACKGROUND=false \
      TIKTOK_CHROME_MINIMIZED=true \
      nohup "$ROOT_DIR/scripts/open-tiktok-login-chrome.sh" \
      >>"$TIKTOK_HOST_CHROME_LAUNCH_LOG" 2>&1 &
    if ! wait_for_cdp "$TIKTOK_CDP_PORT"; then
      echo "Profile TikTok tersimpan ada, tetapi Chrome background gagal dimulai." >&2
      tail -40 "$TIKTOK_HOST_CHROME_LAUNCH_LOG" >&2 || true
      exit 1
    fi
  elif [[ "$TIKTOK_UPLOAD_USE_CDP" != "true" && "$TIKTOK_CLOSE_CDP_AFTER_LOGIN" == "true" ]] \
    && pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" >/dev/null 2>&1; then
    echo "Menutup Chrome login TikTok lama; session sudah tersimpan."
    pkill -f "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" || true
  fi
  echo "Session TikTok tersimpan ditemukan; tidak login ulang. Browser khusus tetap minimized di background."
else
  # TikTok login must use the user's regular host Chrome. Start it minimized so
  # the user only restores it when manual login/CAPTCHA is required.
  tiktok_host_cdp="$(pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}" || true)"
  if [[ -n "$tiktok_host_cdp" ]] && ! grep -F -- "$TIKTOK_HOST_PROFILE_DIR" <<<"$tiktok_host_cdp" >/dev/null; then
    echo "Stopping old container/foreign TikTok Chrome on CDP port ${TIKTOK_CDP_PORT}..."
    "${privilege_cmd[@]}" pkill -f "remote-debugging-port=${TIKTOK_CDP_PORT}" || true
    sleep 2
  fi

  if pgrep -af "remote-debugging-port=${TIKTOK_CDP_PORT}.*${TIKTOK_HOST_PROFILE_DIR}" >/dev/null 2>&1; then
    echo "TikTok host Chrome already running on CDP port ${TIKTOK_CDP_PORT}."
  else
    echo "Session TikTok belum tersedia; membuka Chrome login dalam keadaan minimized..."
    TIKTOK_CHROMIUM_USER_DATA_DIR="$TIKTOK_HOST_PROFILE_DIR" \
      TIKTOK_CHROME_BACKGROUND=false \
      TIKTOK_CHROME_MINIMIZED=true \
      nohup "$ROOT_DIR/scripts/open-tiktok-login-chrome.sh" \
      >>"$TIKTOK_HOST_CHROME_LAUNCH_LOG" 2>&1 &
    echo "TikTok host Chrome launcher log: ${TIKTOK_HOST_CHROME_LAUNCH_LOG}"
  fi

  if ! wait_for_cdp "$TIKTOK_CDP_PORT"; then
    echo "Chrome host TikTok tidak merespons di http://127.0.0.1:${TIKTOK_CDP_PORT}." >&2
    tail -40 "$TIKTOK_HOST_CHROME_LAUNCH_LOG" >&2 || true
    exit 1
  fi
  if ! curl -fsS --max-time 10 -X POST http://127.0.0.1:8010/api/tiktok/login/start >/dev/null; then
    echo "Backend gagal memulai browser TikTok login/Studio." >&2
    exit 1
  fi
  echo "Chrome login TikTok siap dalam keadaan minimized. Buka hanya jika login/CAPTCHA diperlukan."
fi

if [[ "$WATCH_CHROME" == "true" ]]; then
  echo "Watching Chrome remote debugging. Press Ctrl+C to stop watching; Chrome window stays open."
  while true; do
    if ! wait_for_cdp "$YOUTUBE_CDP_PORT"; then
      echo "Chrome remote debugging stopped responding on http://127.0.0.1:${YOUTUBE_CDP_PORT}." >&2
      tail -40 "$YOUTUBE_CHROME_LAUNCH_LOG" >&2 || true
      exit 1
    fi
    sleep 10
  done
fi
