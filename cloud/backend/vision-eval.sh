#!/usr/bin/env bash
set -euo pipefail
VISION_BACKEND_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
unset PYTHONPATH PYTHONHOME
export PYTHONPATH="$VISION_BACKEND_ROOT"
exec "$VISION_BACKEND_ROOT/.venv/bin/python" -m app.vision_eval "$@"
