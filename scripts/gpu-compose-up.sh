#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

fail() {
  printf '\n\033[1;31m[clipforge:gpu-up:error]\033[0m %s\n' "$*" >&2
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  fail "Butuh hak root. Jalankan: sudo bash ${BASH_SOURCE[0]}"
fi

cd -- "${PROJECT_DIR}"
if [[ "${NVIDIA_RUNTIME_ALREADY_CONFIGURED:-0}" != "1" ]]; then
  bash "${SCRIPT_DIR}/setup-nvidia-container-runtime.sh" --configure-only
fi

if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
else
  fail "Docker Compose tidak ditemukan."
fi

printf '\n\033[1;36m[clipforge:gpu-up]\033[0m Membangun ulang stack dengan akses NVIDIA GPU\n'
"${compose_cmd[@]}" \
  -f docker-compose.yml \
  --env-file .env \
  up -d --build --force-recreate backend telegram-bot frontend

printf '\n\033[1;36m[clipforge:gpu-up]\033[0m Memverifikasi GPU di backend\n'
"${compose_cmd[@]}" \
  -f docker-compose.yml \
  --env-file .env \
  exec -T backend nvidia-smi

printf '\n\033[1;32m[clipforge:gpu-up:ready]\033[0m Stack aktif dan backend dapat mengakses NVIDIA GPU.\n'
