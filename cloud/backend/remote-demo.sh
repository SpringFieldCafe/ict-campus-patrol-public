#!/usr/bin/env bash
set -euo pipefail
REMOTE_SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_CONFIG_ROOT="$(cd -- "$REMOTE_SCRIPT_ROOT/../.." && pwd)/.local/remote-demo"
unset PYTHONPATH PYTHONHOME
cd "$REMOTE_SCRIPT_ROOT"
case "${1:-}" in
  init)
    exec "$REMOTE_SCRIPT_ROOT/.venv/bin/python" -m scripts.remote_demo
    ;;
  server)
    export CAMPUS_ENV_FILE="${CAMPUS_ENV_FILE:-$REMOTE_CONFIG_ROOT/server.env}"
    export CAMPUS_API_PORT="${CAMPUS_API_PORT:-8010}"
    exec bash "$REMOTE_SCRIPT_ROOT/run.sh"
    ;;
  executor)
    export CAMPUS_ENV_FILE="${CAMPUS_ENV_FILE:-$REMOTE_CONFIG_ROOT/executor.env}"
    if [[ ! -f "$CAMPUS_ENV_FILE" ]]; then
      echo 'Run remote-demo.sh init first.' >&2
      exit 1
    fi
    exec "$REMOTE_SCRIPT_ROOT/.venv/bin/python" -m app.remote_agent --enable-remote
    ;;
  *)
    echo 'Usage: remote-demo.sh init | server | executor' >&2
    exit 2
    ;;
esac
