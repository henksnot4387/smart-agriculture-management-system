#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[WARN] Deprecated: scripts/apply_timeseries_policies.sh -> scripts/ops.sh apply-timeseries-policy" >&2
exec bash "${SCRIPT_DIR}/ops.sh" apply-timeseries-policy "$@"
