#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly NVIDIA_KEYRING="/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
readonly NVIDIA_REPOSITORY="/etc/apt/sources.list.d/nvidia-container-toolkit.list"
readonly NVIDIA_TOOLKIT_VERSION="${NVIDIA_CONTAINER_TOOLKIT_VERSION:-1.20.0-1}"
readonly DOCKER_DAEMON_CONFIG="/etc/docker/daemon.json"

log() {
  printf '\n\033[1;36m[clipforge:nvidia]\033[0m %s\n' "$*"
}

fail() {
  printf '\n\033[1;31m[clipforge:nvidia:error]\033[0m %s\n' "$*" >&2
  exit 1
}

CONFIGURE_ONLY=false
for arg in "$@"; do
  case "${arg}" in
    --configure-only)
      CONFIGURE_ONLY=true
      ;;
    *)
      fail "Argumen tidak dikenal: ${arg}. Gunakan --configure-only atau tanpa argumen."
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  fail "Butuh hak root. Jalankan: sudo bash ${BASH_SOURCE[0]}"
fi

command -v apt-get >/dev/null 2>&1 || fail "Installer ini mendukung host Debian/Ubuntu (apt)."
command -v docker >/dev/null 2>&1 || fail "Docker belum terpasang di host."
command -v nvidia-smi >/dev/null 2>&1 || fail "Driver NVIDIA host belum menyediakan nvidia-smi."

log "Memvalidasi GPU dan driver NVIDIA pada host"
nvidia-smi >/dev/null || fail "Driver NVIDIA host belum sehat; nvidia-smi gagal dijalankan."

export DEBIAN_FRONTEND=noninteractive
setup_tmp_dir=""
cleanup() {
  [[ -n "${setup_tmp_dir:-}" && -d "${setup_tmp_dir}" ]] && rm -rf -- "${setup_tmp_dir}"
}
trap cleanup EXIT

if command -v nvidia-ctk >/dev/null 2>&1; then
  log "NVIDIA Container Toolkit sudah terpasang; instalasi paket dilewati"
else
  log "Memasang prasyarat repository NVIDIA"
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl gnupg2

  install -d -m 0755 /usr/share/keyrings /etc/apt/sources.list.d
  setup_tmp_dir="$(mktemp -d)"

  log "Mengaktifkan repository resmi NVIDIA Container Toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    -o "${setup_tmp_dir}/nvidia-container-toolkit.key"
  gpg --dearmor --yes \
    --output "${NVIDIA_KEYRING}" \
    "${setup_tmp_dir}/nvidia-container-toolkit.key"
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    -o "${setup_tmp_dir}/nvidia-container-toolkit.list"
  sed "s#deb https://#deb [signed-by=${NVIDIA_KEYRING}] https://#g" \
    "${setup_tmp_dir}/nvidia-container-toolkit.list" \
    > "${NVIDIA_REPOSITORY}"

  apt-get update
  if apt-cache madison nvidia-container-toolkit | awk '{print $3}' | grep -Fxq "${NVIDIA_TOOLKIT_VERSION}"; then
    log "Memasang NVIDIA Container Toolkit ${NVIDIA_TOOLKIT_VERSION}"
    apt-get install -y \
      "nvidia-container-toolkit=${NVIDIA_TOOLKIT_VERSION}" \
      "nvidia-container-toolkit-base=${NVIDIA_TOOLKIT_VERSION}" \
      "libnvidia-container-tools=${NVIDIA_TOOLKIT_VERSION}" \
      "libnvidia-container1=${NVIDIA_TOOLKIT_VERSION}"
  else
    log "Versi ${NVIDIA_TOOLKIT_VERSION} tidak ada di repository; memasang versi stabil terbaru"
    apt-get install -y nvidia-container-toolkit
  fi
fi

command -v nvidia-ctk >/dev/null 2>&1 || fail "nvidia-ctk tidak ditemukan setelah instalasi."

if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
  log "Runtime NVIDIA sudah terdaftar di Docker; konfigurasi dan restart daemon dilewati"
else
  log "Memeriksa konfigurasi Docker daemon"
  if [[ -e "${DOCKER_DAEMON_CONFIG}" ]] && ! grep -q '[^[:space:]]' "${DOCKER_DAEMON_CONFIG}"; then
    daemon_backup="${DOCKER_DAEMON_CONFIG}.empty.$(date +%Y%m%d-%H%M%S).bak"
    cp -a -- "${DOCKER_DAEMON_CONFIG}" "${daemon_backup}"
    printf '{}\n' > "${DOCKER_DAEMON_CONFIG}"
    chown root:root "${DOCKER_DAEMON_CONFIG}"
    chmod 0644 "${DOCKER_DAEMON_CONFIG}"
    log "daemon.json kosong diperbaiki; cadangan: ${daemon_backup}"
  elif [[ ! -e "${DOCKER_DAEMON_CONFIG}" ]]; then
    printf '{}\n' > "${DOCKER_DAEMON_CONFIG}"
    chmod 0644 "${DOCKER_DAEMON_CONFIG}"
  elif ! python3 -m json.tool "${DOCKER_DAEMON_CONFIG}" >/dev/null 2>&1; then
    fail "${DOCKER_DAEMON_CONFIG} berisi JSON tidak valid. File tidak diubah agar konfigurasi lama tetap aman."
  fi

  log "Mendaftarkan NVIDIA runtime ke Docker"
  nvidia-ctk runtime configure --runtime=docker
  python3 -m json.tool "${DOCKER_DAEMON_CONFIG}" >/dev/null \
    || fail "nvidia-ctk menghasilkan konfigurasi Docker yang tidak valid."
  systemctl restart docker

  log "Menunggu Docker daemon siap"
  docker_ready=0
  for _attempt in {1..30}; do
    if docker info >/dev/null 2>&1; then
      docker_ready=1
      break
    fi
    sleep 1
  done
  [[ "${docker_ready}" -eq 1 ]] || fail "Docker daemon tidak kembali aktif setelah 30 detik."
fi

if [[ "${CONFIGURE_ONLY}" == "true" ]]; then
  printf '\n\033[1;32m[clipforge:nvidia:configured]\033[0m NVIDIA runtime siap untuk Docker Compose.\n'
  exit 0
fi

log "Runtime siap; melanjutkan rebuild seluruh stack dengan GPU default"
NVIDIA_RUNTIME_ALREADY_CONFIGURED=1 bash "${SCRIPT_DIR}/gpu-compose-up.sh"
