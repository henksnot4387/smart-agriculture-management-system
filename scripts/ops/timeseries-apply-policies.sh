#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -f backend/app/db/policies/timeseries_policies.sql ]]; then
  echo "[FAIL] SQL file not found: backend/app/db/policies/timeseries_policies.sql"
  exit 20
fi

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "[FAIL] Neither 'docker compose' nor 'docker-compose' is available."
    exit 21
  fi
}

set -a
# shellcheck disable=SC1091
source .env
set +a

compose up -d db >/dev/null

cat backend/app/db/policies/timeseries_policies.sql | \
  compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c \
"SELECT view_name, materialized_only FROM timescaledb_information.continuous_aggregates WHERE view_name IN ('sensor_samples_15m','sensor_samples_1d') ORDER BY view_name;"

compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c \
"SELECT job_id, proc_name, schedule_interval FROM timescaledb_information.jobs WHERE proc_name IN ('policy_refresh_continuous_aggregate','policy_retention') ORDER BY job_id;"

echo "[PASS] 时序策略已应用"
