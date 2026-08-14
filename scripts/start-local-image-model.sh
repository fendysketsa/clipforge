#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
state_dir="${LOCAL_IMAGE_INSTALL_DIR:-$project_dir/backend/data/local-image}"
pid_file="$state_dir/sd-server.pid"
log_file="$state_dir/sd-server.log"
port="${LOCAL_IMAGE_PORT:-7860}"

if systemctl --user cat fendy-clipper-local-image.service >/dev/null 2>&1; then
  systemctl --user start fendy-clipper-local-image.service
  for _attempt in $(seq 1 120); do
    if curl --fail --silent "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
      service_pid="$(systemctl --user show -p MainPID --value fendy-clipper-local-image.service)"
      echo "Image model lokal aktif di http://127.0.0.1:$port/v1 (PID $service_pid)."
      exit 0
    fi
    if ! systemctl --user is-active --quiet fendy-clipper-local-image.service; then
      echo "User service image model gagal dimulai." >&2
      journalctl --user -u fendy-clipper-local-image.service -n 80 --no-pager >&2 || true
      exit 1
    fi
    sleep 2
  done
  echo "Image model masih memuat bobot. Cek journal user service." >&2
  exit 1
fi

mkdir -p "$state_dir"
if [[ -s "$pid_file" ]]; then
  existing_pid="$(cat "$pid_file")"
  if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "Image model lokal sudah aktif (PID $existing_pid)."
    exit 0
  fi
fi

nohup "$script_dir/run-local-image-model.sh" >"$log_file" 2>&1 &
server_pid=$!
printf '%s\n' "$server_pid" >"$pid_file"

for _attempt in $(seq 1 120); do
  if curl --fail --silent "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
    echo "Image model lokal aktif di http://127.0.0.1:$port/v1 (PID $server_pid)."
    exit 0
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Image model lokal gagal dimulai. Log terakhir:" >&2
    tail -80 "$log_file" >&2 || true
    exit 1
  fi
  sleep 2
done

echo "Image model masih memuat bobot. Cek log: $log_file" >&2
exit 1
