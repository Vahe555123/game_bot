#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/deploy/apps/game_bot2}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
SKIP_GIT_UPDATE="${SKIP_GIT_UPDATE:-false}"
SKIP_FRONTEND_BUILD="${SKIP_FRONTEND_BUILD:-false}"

cd "$APP_DIR"

if [ "$SKIP_GIT_UPDATE" != "true" ]; then
  echo "==> Updating repository"
  git fetch origin "$DEPLOY_BRANCH"
  git checkout "$DEPLOY_BRANCH"
  git pull --ff-only origin "$DEPLOY_BRANCH"
fi

echo "==> Preparing Python environment"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ "$SKIP_FRONTEND_BUILD" != "true" ]; then
  echo "==> Building frontend"
  cd frontend
  npm ci
  npm run build
  cd "$APP_DIR"
else
  echo "==> Skipping frontend build on server"
  mkdir -p "$APP_DIR/frontend/dist"
  find "$APP_DIR/frontend/dist" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi

echo "==> Restarting application with PM2"
chmod +x start_pm2.sh
pm2 startOrReload ecosystem.config.cjs --only game_bot2 --update-env
pm2 save
pm2 show game_bot2

echo "==> Deploy completed"
