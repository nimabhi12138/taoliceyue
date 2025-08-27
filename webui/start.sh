#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from example. Please review credentials and ports."
fi
docker compose up -d --build
echo "Web UI started: backend on ${BACKEND_PORT:-8000}, frontend on ${FRONTEND_PORT:-8501}"