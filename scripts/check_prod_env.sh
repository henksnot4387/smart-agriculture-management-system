#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[WARN] Deprecated: scripts/check_prod_env.sh -> scripts/ops.sh check-production-env" >&2
exec bash "${SCRIPT_DIR}/ops.sh" check-production-env "$@"
