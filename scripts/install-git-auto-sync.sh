#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
manager_state="$(systemctl --user is-system-running 2>/dev/null || true)"
[[ "$manager_state" == running || "$manager_state" == degraded ]] || {
  echo "User systemd is unavailable. Run this installer from the logged-in desktop terminal." >&2
  exit 1
}
user_config_dir="${XDG_CONFIG_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)/.config}"
unit_dir="$user_config_dir/systemd/user"
mkdir -p "$unit_dir"
for suffix in service timer; do
  install -m 0644 "deploy/clipforge-git-auto-sync.$suffix" "$unit_dir/clipforge-git-auto-sync.$suffix"
done
systemctl --user daemon-reload
systemctl --user enable --now clipforge-git-auto-sync.timer
systemctl --user is-enabled clipforge-git-auto-sync.timer
systemctl --user is-active clipforge-git-auto-sync.timer
systemctl --user list-timers clipforge-git-auto-sync.timer --no-pager
