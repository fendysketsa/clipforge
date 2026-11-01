#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BACKEND_CONTAINER="fendy-clipper-backend"
WAIT_SECONDS="${CLIPFORGE_DEPLOY_POLL_SECONDS:-15}"
TIMEOUT_SECONDS="${CLIPFORGE_DEPLOY_TIMEOUT_SECONDS:-86400}"

test -f "$PROJECT_DIR/.env"
test -f "$PROJECT_DIR/backend/api.py"
test -f "$PROJECT_DIR/backend/clipper.py"
test -x "$PROJECT_DIR/scripts/recreate-compose-up.sh"
command -v jq >/dev/null

if [[ ! "$WAIT_SECONDS" =~ ^[0-9]+$ ]] || (( WAIT_SECONDS < 5 )); then
  WAIT_SECONDS=15
fi
if [[ ! "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( TIMEOUT_SECONDS < 60 )); then
  TIMEOUT_SECONDS=86400
fi

if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose=(docker-compose)
else
  echo "Docker Compose tidak ditemukan." >&2
  exit 1
fi

cd "$PROJECT_DIR"

stack_stopped=false
restore_stack_on_error() {
  status=$?
  trap - EXIT INT TERM
  if (( status != 0 )) && [[ "$stack_stopped" == "true" ]]; then
    echo "Deployment gagal. Menyalakan kembali stack dari image terakhir yang tersedia..." >&2
    "${compose[@]}" --env-file .env up -d --no-build || true
  fi
  exit "$status"
}
trap restore_stack_on_error EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

read_backend_endpoint() {
  local path="$1"
  docker exec "$BACKEND_CONTAINER" curl -fsS --max-time 8 \
    "http://127.0.0.1:8010${path}"
}

wait_until_media_idle() {
  if ! docker inspect "$BACKEND_CONTAINER" >/dev/null 2>&1; then
    echo "Backend belum ada; tidak ada proses media yang perlu ditunggu."
    return 0
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$BACKEND_CONTAINER")" != "true" ]]; then
    echo "Backend sudah berhenti; aman melanjutkan deployment."
    return 0
  fi

  local started_at=$SECONDS
  local youtube_payload=""
  local tiktok_payload=""
  local jobs_payload=""
  local automation_payload=""
  local youtube_active=0
  local tiktok_active=0
  local jobs_active=0
  local automation_active=0
  local queued_total=0
  local state_detail=""

  echo "Mode otomatis aktif: skrip akan menunggu seluruh antrean/render/upload selesai sendiri."
  while true; do
    if ! youtube_payload="$(read_backend_endpoint /api/youtube/uploads)" \
      || ! tiktok_payload="$(read_backend_endpoint /api/tiktok/uploads)" \
      || ! jobs_payload="$(read_backend_endpoint /api/jobs)" \
      || ! automation_payload="$(read_backend_endpoint /api/automation/viral-cc)"; then
      echo "Gagal membaca status backend. Deployment dibatalkan agar tidak memotong proses yang belum diketahui." >&2
      return 1
    fi

    youtube_active="$(jq '[.[] | select(.status == "running")] | length' <<<"$youtube_payload")"
    tiktok_active="$(jq '[.[] | select(.status == "running")] | length' <<<"$tiktok_payload")"
    jobs_active="$(jq '[.[] | select(.status == "running")] | length' <<<"$jobs_payload")"
    automation_active="$(jq '[.[] | select(.status == "running")] | length' <<<"$automation_payload")"
    queued_total=$((
      $(jq '[.[] | select(.status == "queued")] | length' <<<"$youtube_payload")
      + $(jq '[.[] | select(.status == "queued")] | length' <<<"$tiktok_payload")
      + $(jq '[.[] | select(.status == "queued")] | length' <<<"$jobs_payload")
      + $(jq '[.[] | select(.status == "queued")] | length' <<<"$automation_payload")
    ))

    if (( youtube_active + tiktok_active + jobs_active + automation_active == 0 )); then
      echo "Tidak ada proses nyata berstatus running. Item queued=$queued_total akan dipulihkan otomatis setelah startup."
      return 0
    fi

    state_detail="$(jq -r '
      [.[] | select(.status == "running")
        | "\(.status):\(.progress_percent // 0)%:\(.progress_stage // "-")"]
      | join(", ")
    ' <<<"$jobs_payload")"
    printf '[%(%H:%M:%S)T] Menunggu otomatis — render=%s, automation=%s, YouTube=%s, TikTok=%s' \
      -1 "$jobs_active" "$automation_active" "$youtube_active" "$tiktok_active"
    if [[ -n "$state_detail" ]]; then
      printf ' (%s)' "$state_detail"
    fi
    printf '\n'

    if (( SECONDS - started_at >= TIMEOUT_SECONDS )); then
      echo "Batas tunggu ${TIMEOUT_SECONDS} detik tercapai. Stack tidak dihentikan karena pekerjaan belum selesai." >&2
      return 1
    fi
    sleep "$WAIT_SECONDS"
  done
}

wait_until_media_idle

echo "Menghentikan seluruh stack ClipForge sebelum rebuild..."
"${compose[@]}" --env-file .env stop
stack_stopped=true

echo "Seluruh container ClipForge sudah berhenti. Memulai rebuild backend, frontend, dan bot..."
"$PROJECT_DIR/scripts/recreate-compose-up.sh"

for _attempt in $(seq 1 45); do
  if docker exec "$BACKEND_CONTAINER" curl -fsS \
    http://127.0.0.1:8010/api/health >/dev/null 2>&1 \
    && curl -fsS http://127.0.0.1:3000/ >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker exec "$BACKEND_CONTAINER" curl -fsS http://127.0.0.1:8010/api/health >/dev/null
curl -fsS http://127.0.0.1:3000/ >/dev/null
docker exec "$BACKEND_CONTAINER" python -c \
  "import api; assert not api.DEFAULT_CRON_GAMING_SOURCE_CHANNEL_IDS; assert {'lecture_wisdom','famous_game_reaction','quirky_animation','reaction_clip_story'} <= set(api.RYUUNDY_CRON_THEME_PROFILES)"
docker exec "$BACKEND_CONTAINER" sh -eu -c \
  'test -z "${AUTO_VIRAL_SCHEDULE_GAMING_SOURCE_CHANNEL_IDS:-}"; test "${AUTO_VIRAL_SCHEDULE_RUN_KEY:-}" = "ryuundy-all-channel-daily-19s1l-v8"'

stack_stopped=false
trap - EXIT INT TERM
echo "SELESAI: seluruh stack sudah direbuild dan aktif. Cron RYUUNDY serta layout frontend terbaru sudah terpasang."
