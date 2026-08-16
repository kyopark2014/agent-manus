#!/usr/bin/env bash
# Local build + run: frontend (npm) then FastAPI (uvicorn) on :8501
# If port 8501 is already in use, the existing process is stopped first.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8501

cd "$ROOT"

echo "==> Frontend build (application/web)"
cd application/web
npm install
npm run build
cd "$ROOT"

echo "==> Freeing port ${PORT} if occupied"
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${PIDS}" ]]; then
    echo "    Port ${PORT} in use by PID(s): ${PIDS} — killing"
    # shellcheck disable=SC2086
    kill ${PIDS} 2>/dev/null || true
    sleep 1
    # Force-kill if still listening
    PIDS="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "${PIDS}" ]]; then
      # shellcheck disable=SC2086
      kill -9 ${PIDS} 2>/dev/null || true
      sleep 0.5
    fi
  else
    echo "    Port ${PORT} is free"
  fi
else
  echo "    lsof not found; skipping port check"
fi

echo "==> Starting uvicorn on 0.0.0.0:${PORT}"
echo "    Open http://localhost:${PORT}"
exec uvicorn application.server:app --host 0.0.0.0 --port "${PORT}"
