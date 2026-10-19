#!/usr/bin/env bash
set -euo pipefail
BACKEND_TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$BACKEND_TASK_ROOT/.venv/bin/python" || ! -f "${CAMPUS_ENV_FILE:-$BACKEND_TASK_ROOT/.env}" ]]; then
  echo 'First install dependencies and run scripts/init_local.py; see cloud/backend/README.md.' >&2
  exit 1
fi
cd "$BACKEND_TASK_ROOT"
unset PYTHONPATH PYTHONHOME
exec "$BACKEND_TASK_ROOT/.venv/bin/python" -m uvicorn app.main:app \
  --host 127.0.0.1 --port "${CAMPUS_API_PORT:-8000}" --workers 1
