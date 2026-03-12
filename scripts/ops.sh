#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/ops.sh list
  bash scripts/ops.sh restart-dev
  bash scripts/ops.sh check-production-env
  bash scripts/ops.sh deploy-production
  bash scripts/ops.sh apply-timeseries-policy
  bash scripts/ops.sh rollback-timeseries-policy
  bash scripts/ops.sh harvest-knowledge
USAGE
}

run() {
  local script_path="$1"
  shift || true
  bash "${script_path}" "$@"
}

command="${1:-list}"
shift || true

case "${command}" in
  list)
    usage
    ;;
  restart-dev)
    run "${REPO_ROOT}/scripts/ops/dev-restart.sh" "$@"
    ;;
  check-production-env)
    run "${REPO_ROOT}/scripts/ops/prod-check-env.sh" "$@"
    ;;
  deploy-production)
    run "${REPO_ROOT}/scripts/ops/prod-deploy.sh" "$@"
    ;;
  apply-timeseries-policy)
    run "${REPO_ROOT}/scripts/ops/timeseries-apply-policies.sh" "$@"
    ;;
  rollback-timeseries-policy)
    run "${REPO_ROOT}/scripts/ops/timeseries-rollback-policies.sh" "$@"
    ;;
  harvest-knowledge)
    if [[ -x "${REPO_ROOT}/backend/venv/bin/python" ]]; then
      "${REPO_ROOT}/backend/venv/bin/python" "${REPO_ROOT}/scripts/ops/kb-harvest.py" "$@"
    else
      python3 "${REPO_ROOT}/scripts/ops/kb-harvest.py" "$@"
    fi
    ;;
  *)
    echo "[FAIL] Unknown command: ${command}" >&2
    usage
    exit 2
    ;;
esac
