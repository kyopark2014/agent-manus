#!/bin/sh
set -e

if [ -n "$APP_CONFIG_JSON" ]; then
  mkdir -p /app/application
  printf '%s\n' "$APP_CONFIG_JSON" > /app/application/config.json
fi

exec "$@"
