#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[WARN] Deprecated: scripts/restart_dev.sh -> scripts/ops.sh restart-dev" >&2
exec bash "${SCRIPT_DIR}/ops.sh" restart-dev "$@"
