#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.prod.yml"
ENV_CHECK_SCRIPT="${REPO_ROOT}/scripts/ops/prod-check-env.sh"

log() { printf '[INFO] %s\n' "$*"; }
err() { printf '[ERROR] %s\n' "$*" >&2; }

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    err "Neither 'docker compose' nor 'docker-compose' is available."
    exit 20
  fi
}

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  err "Missing compose file: ${COMPOSE_FILE}"
  exit 21
fi

if [[ ! -x "${ENV_CHECK_SCRIPT}" ]]; then
  err "Missing executable env check script: ${ENV_CHECK_SCRIPT}"
  exit 22
fi

cd "${REPO_ROOT}"
log "Validating production environment variables..."
"${ENV_CHECK_SCRIPT}"

log "Starting production stack with ${COMPOSE_FILE}"
compose -f "${COMPOSE_FILE}" up -d --build

log "Production stack status:"
compose -f "${COMPOSE_FILE}" ps
