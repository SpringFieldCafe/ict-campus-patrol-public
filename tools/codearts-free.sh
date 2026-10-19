#!/usr/bin/env bash
set -euo pipefail
CODEARTS_FREE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
unset PYTHONPATH PYTHONHOME
exec python3 "$CODEARTS_FREE_ROOT/tools/codearts_free.py" "$@"
