#!/usr/bin/env bash
set -u

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

pass() {
  printf '\033[1;32mPASS\033[0m  %s\n' "$1"
}

fail() {
  printf '\033[1;31mFAIL\033[0m  %s\n' "$1"
  failures=$((failures + 1))
}

failures=0

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  pass "GPU dan driver NVIDIA host"
else
  fail "nvidia-smi pada host"
fi

if command -v nvidia-ctk >/dev/null 2>&1; then
  pass "NVIDIA Container Toolkit ($(nvidia-ctk --version 2>/dev/null | head -n 1))"
else
  fail "NVIDIA Container Toolkit belum terpasang"
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q 'nvidia'; then
    pass "NVIDIA runtime terdaftar di Docker"
  else
    fail "NVIDIA runtime belum terdaftar di Docker"
  fi

  cd -- "${PROJECT_DIR}"
  if docker compose \
    -f docker-compose.yml \
    exec -T backend nvidia-smi >/dev/null 2>&1; then
    pass "nvidia-smi tersedia di backend ClipForge"
  else
    fail "Backend belum berjalan dengan akses NVIDIA GPU"
  fi
else
  fail "Docker daemon tidak dapat diakses oleh user ini (coba jalankan dengan sudo)"
fi

if [[ "${failures}" -gt 0 ]]; then
  printf '\n%d pemeriksaan gagal. Jalankan: sudo bash %s/setup-nvidia-container-runtime.sh\n' \
    "${failures}" "${SCRIPT_DIR}"
  exit 1
fi

printf '\nSemua jalur GPU siap.\n'
