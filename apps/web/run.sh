#!/usr/bin/env bash
set -euo pipefail
WEB_TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_REPO_ROOT="$(cd -- "$WEB_TASK_ROOT/../.." && pwd)"
WEB_LOCAL_NODE="$WEB_REPO_ROOT/.local/toolchains/node-v24.22.0-linux-x64/bin"
if [[ -x "$WEB_LOCAL_NODE/node" ]]; then
  export PATH="$WEB_LOCAL_NODE:$PATH"
fi
if ! command -v node >/dev/null 2>&1; then
  echo 'Node.js >=22.12 required; see apps/web/README.md.' >&2
  exit 1
fi
cd "$WEB_TASK_ROOT"
if [[ $# -eq 0 ]]; then set -- dev; fi
WEB_LOCAL_PNPM="$WEB_REPO_ROOT/.local/toolchains/pnpm/node_modules/pnpm/bin/pnpm.cjs"
if [[ -f "$WEB_LOCAL_PNPM" ]]; then
  exec node "$WEB_LOCAL_PNPM" "$@"
elif command -v pnpm >/dev/null 2>&1; then
  exec pnpm "$@"
else
  echo 'Install pnpm 10.34.0; see apps/web/README.md.' >&2
  exit 1
fi
