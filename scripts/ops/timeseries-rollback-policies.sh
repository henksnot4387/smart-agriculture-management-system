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

compose up -d db >/dev/null

compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" <<'SQL'
SELECT remove_continuous_aggregate_policy('sensor_samples_15m', if_exists => TRUE);
SELECT remove_continuous_aggregate_policy('sensor_samples_1d', if_exists => TRUE);
SELECT remove_retention_policy('sensor_samples_15m', if_exists => TRUE);
SELECT remove_retention_policy('sensor_data', if_exists => TRUE);

DROP MATERIALIZED VIEW IF EXISTS sensor_samples_1d;
DROP MATERIALIZED VIEW IF EXISTS sensor_samples_15m;
SQL

echo "[PASS] 时序策略已回滚"
