#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE="${APP_ENV_FILE:-/home/deploy/data/game_bot2/.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
elif [ -f ./.env ]; then
  set -a
  . ./.env
  set +a
fi

exec ./.venv/bin/uvicorn main:app \
  --host "${HOST:-127.0.0.1}" \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
