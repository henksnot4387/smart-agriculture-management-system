#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[WARN] Deprecated: scripts/deploy_prod.sh -> scripts/ops.sh deploy-production" >&2
exec bash "${SCRIPT_DIR}/ops.sh" deploy-production "$@"
