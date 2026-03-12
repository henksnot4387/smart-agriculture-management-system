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

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_API_TOKEN="${BACKEND_API_TOKEN:-}"
BASE_URL="http://127.0.0.1:${BACKEND_PORT}"

if [[ -z "${BACKEND_API_TOKEN}" ]]; then
  echo "[FAIL] BACKEND_API_TOKEN is required. Please set it in .env."
  exit 22
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

for _ in $(seq 1 30); do
  if curl -sf "${BASE_URL}/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "${BASE_URL}/health" >/dev/null

CAGG_COUNT="$(
  compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT COUNT(*) FROM timescaledb_information.continuous_aggregates WHERE view_name IN ('sensor_samples_15m','sensor_samples_1d');"
)"
if [[ "${CAGG_COUNT}" -lt 2 ]]; then
  echo "[FAIL] expected 2 continuous aggregates, got ${CAGG_COUNT}"
  exit 30
fi
echo "[PASS] continuous aggregates ready: ${CAGG_COUNT}"

REFRESH_POLICY_COUNT="$(
  compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT COUNT(*) FROM timescaledb_information.jobs WHERE proc_name='policy_refresh_continuous_aggregate';"
)"
if [[ "${REFRESH_POLICY_COUNT}" -lt 2 ]]; then
  echo "[FAIL] expected >=2 refresh policies, got ${REFRESH_POLICY_COUNT}"
  exit 31
fi
echo "[PASS] refresh policies ready: ${REFRESH_POLICY_COUNT}"

RETENTION_POLICY_COUNT="$(
  compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT COUNT(*) FROM timescaledb_information.jobs WHERE proc_name='policy_retention';"
)"
if [[ "${RETENTION_POLICY_COUNT}" -lt 1 ]]; then
  echo "[FAIL] expected >=1 retention policy, got ${RETENTION_POLICY_COUNT}"
  exit 32
fi
echo "[PASS] retention policies ready: ${RETENTION_POLICY_COUNT}"

SERIES_7D="$(
  curl -sf -H "Accept: application/json" -H "X-API-Token: ${BACKEND_API_TOKEN}" \
    "${BASE_URL}/api/sensor/series?range=7d"
)"
python3 - <<'PY' "$SERIES_7D"
import json
import sys
payload = json.loads(sys.argv[1])
bucket = payload.get("bucket")
if bucket != "1h":
    raise SystemExit(f"[FAIL] 7d bucket mismatch: {bucket}")
print("[PASS] 7d series response valid")
PY

WINDOW_JSON="$(python3 - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
tz = ZoneInfo("Asia/Shanghai")
end = datetime.now(tz).replace(microsecond=0)
start = end - timedelta(days=40)
print(json.dumps({"start": start.isoformat(), "end": end.isoformat()}))
PY
)"
START="$(python3 - <<'PY' "$WINDOW_JSON"
import json,sys
print(json.loads(sys.argv[1])["start"])
PY
)"
END="$(python3 - <<'PY' "$WINDOW_JSON"
import json,sys
print(json.loads(sys.argv[1])["end"])
PY
)"

SERIES_40D="$(
  curl -sf -G -H "Accept: application/json" -H "X-API-Token: ${BACKEND_API_TOKEN}" \
    --data-urlencode "start=${START}" \
    --data-urlencode "end=${END}" \
    "${BASE_URL}/api/sensor/series"
)"
python3 - <<'PY' "$SERIES_40D"
import json
import sys
payload = json.loads(sys.argv[1])
bucket = payload.get("bucket")
if bucket != "1d":
    raise SystemExit(f"[FAIL] >30d auto bucket should be 1d, got {bucket}")
print("[PASS] >30d auto bucket downgraded to 1d")
PY

STATUS_CODE="$(
  curl -s -o /tmp/timeseries_bucket_invalid.json -w "%{http_code}" -G \
    -H "Accept: application/json" \
    -H "X-API-Token: ${BACKEND_API_TOKEN}" \
    --data-urlencode "start=${START}" \
    --data-urlencode "end=${END}" \
    --data-urlencode "bucket=6h" \
    "${BASE_URL}/api/sensor/series"
)"
if [[ "${STATUS_CODE}" != "422" ]]; then
  echo "[FAIL] expected 422 for >30d bucket=6h, got ${STATUS_CODE}"
  cat /tmp/timeseries_bucket_invalid.json
  exit 33
fi
echo "[PASS] >30d bucket guard works (422)"

echo "[PASS] timeseries policy verification passed"
