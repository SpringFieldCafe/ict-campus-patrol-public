#!/usr/bin/env bash
set -euo pipefail
BACKEND_TEST_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$BACKEND_TEST_ROOT"
# The host sources ROS for Python 3.10. Its pytest plugins do not belong to this venv.
unset PYTHONPATH PYTHONHOME
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
exec "$BACKEND_TEST_ROOT/.venv/bin/python" -m pytest "$@"
