#!/bin/sh
set -eu

stdlib_file="${PYTHON_SUBPROCESS_FILE:-/usr/local/lib/python3.12/subprocess.py}"
stdlib_backup="${PYTHON_SUBPROCESS_BACKUP:-/opt/python-stdlib-backup/subprocess.py}"

if [ ! -f "$stdlib_backup" ]; then
  echo "FATAL: backup stdlib Python tidak ditemukan: $stdlib_backup" >&2
  exit 70
fi

if ! cmp -s "$stdlib_backup" "$stdlib_file"; then
  echo "Memulihkan subprocess.py yang berubah/rusak dari image backup." >&2
  cp "$stdlib_backup" "$stdlib_file"
fi

# Fail at startup with a useful message instead of failing later inside a job.
python -m py_compile "$stdlib_file" /app/api.py /app/clipper.py

exec "$@"
