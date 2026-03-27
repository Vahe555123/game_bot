#!/usr/bin/env bash
set -euo pipefail

if [ -f ./.env ]; then
  set -a
  . ./.env
  set +a
fi

exec ./.venv/bin/uvicorn main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
