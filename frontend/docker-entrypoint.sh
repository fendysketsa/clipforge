#!/bin/sh
set -eu
node /app/scripts/deployment-health.cjs prepare
exec "$@"
