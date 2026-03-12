#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[WARN] Deprecated: scripts/rollback_timeseries_policies.sh -> scripts/ops.sh rollback-timeseries-policy" >&2
exec bash "${SCRIPT_DIR}/ops.sh" rollback-timeseries-policy "$@"
