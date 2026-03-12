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

if [[ ! -f "${REPO_ROOT}/backend/venv/bin/python" ]]; then
  echo "[FAIL] backend venv not found."
  exit 20
fi

for _ in $(seq 1 30); do
  if curl -sf "${BASE_URL}/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "${BASE_URL}/health" >/dev/null

SUPER_ADMIN_ID="$(
  cd "${REPO_ROOT}/backend"
  venv/bin/python - <<'PY'
import psycopg
from app.core.config import settings

with psycopg.connect(settings.psycopg_database_url) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text
            FROM users
            WHERE role = 'SUPER_ADMIN'::"UserRole" AND is_active = TRUE
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
if not row:
    raise SystemExit("[FAIL] no active SUPER_ADMIN user found.")
print(row[0])
PY
)"

HEADERS=(
  -H "X-User-Role: SUPER_ADMIN"
  -H "X-User-Id: ${SUPER_ADMIN_ID}"
  -H "Accept: application/json"
  -H "X-API-Token: ${BACKEND_API_TOKEN}"
)

# 1) Controlled failed request (422) for observability error pipeline.
BAD_STATUS="$(
  curl -s -o /tmp/observability_bad_request.json -w "%{http_code}" -G \
    -H "Accept: application/json" \
    -H "X-API-Token: ${BACKEND_API_TOKEN}" \
    --data-urlencode "limit=50000" \
    "${BASE_URL}/api/sensor/raw"
)"
if [[ "${BAD_STATUS}" != "422" ]]; then
  echo "[FAIL] expected /api/sensor/raw invalid limit to return 422, got ${BAD_STATUS}"
  cat /tmp/observability_bad_request.json
  exit 30
fi
echo "[PASS] controlled API failure generated (422 /api/sensor/raw)"

# 2) Controlled slow request (> threshold).
SLOW_STATUS="$(
  curl -s -o /tmp/observability_slow_health.json -w "%{http_code}" \
    -H "X-Debug-Sleep-MS: 1300" \
    "${BASE_URL}/health"
)"
if [[ "${SLOW_STATUS}" != "200" ]]; then
  echo "[FAIL] expected slow /health to return 200, got ${SLOW_STATUS}"
  cat /tmp/observability_slow_health.json
  exit 31
fi
echo "[PASS] controlled slow request generated (/health)"

# 3) Controlled Celery failure record in scheduler_job_runs.
FAILURE_TAG="VERIFY_OBSERVABILITY_CONTROLLED_FAILURE_$(date +%s)"
TARGET_JOB_ID="vision_timeout_cleanup"
INJECTED_RUN_ID="$(
  cd "${REPO_ROOT}/backend"
  venv/bin/python - <<'PY' "${TARGET_JOB_ID}" "${FAILURE_TAG}"
import sys

from app.core.config import settings
from app.scheduler.repository import SchedulerRepository

job_id = sys.argv[1]
error_tag = sys.argv[2]
repo = SchedulerRepository(settings)
repo.ensure_schema()
run_id = repo.create_run(job_id=job_id, trigger="verify_observability")
repo.finish_run(
    run_id=run_id,
    status="FAILED",
    message="verify_observability injected failure",
    error=error_tag,
    duration_ms=1234,
)
print(run_id)
PY
)"
echo "[PASS] injected scheduler failure run: ${TARGET_JOB_ID}#${INJECTED_RUN_ID}"

# Give observability writes a brief settle window.
sleep 1

OVERVIEW_JSON="$(curl -sf "${HEADERS[@]}" "${BASE_URL}/api/admin/observability/overview?hours=24")"
ERRORS_JSON="$(curl -sf "${HEADERS[@]}" "${BASE_URL}/api/admin/observability/errors?hours=24&limit=200")"
SLOW_JSON="$(curl -sf "${HEADERS[@]}" "${BASE_URL}/api/admin/observability/slow-requests?hours=24&limit=200")"
TASK_FAILURES_JSON="$(curl -sf "${HEADERS[@]}" "${BASE_URL}/api/admin/observability/task-failures?hours=24&limit=100")"
SCHED_RUNS_JSON="$(curl -sf "${HEADERS[@]}" "${BASE_URL}/api/admin/scheduler/runs?limit=500&jobId=${TARGET_JOB_ID}")"

python3 - <<'PY' "$OVERVIEW_JSON" "$ERRORS_JSON" "$SLOW_JSON" "$TASK_FAILURES_JSON" "$SCHED_RUNS_JSON" "$TARGET_JOB_ID" "$FAILURE_TAG"
import json
import sys
from datetime import datetime, timedelta, timezone

overview = json.loads(sys.argv[1])
errors = json.loads(sys.argv[2])
slow = json.loads(sys.argv[3])
task_failures = json.loads(sys.argv[4])
scheduler_runs = json.loads(sys.argv[5])
target_job_id = sys.argv[6]
failure_tag = sys.argv[7]

if int(overview.get("totalRequests", 0)) <= 0:
    raise SystemExit("[FAIL] observability overview totalRequests should be > 0")
print(f"[PASS] overview totalRequests={overview.get('totalRequests')}")

error_items = errors.get("items", [])
if not any(item.get("route") == "/api/sensor/raw" and int(item.get("statusCode", 0)) == 422 for item in error_items):
    raise SystemExit("[FAIL] missing controlled /api/sensor/raw 422 event in observability errors")
print("[PASS] controlled API failure captured in observability errors")

slow_items = slow.get("items", [])
if not any(item.get("route") == "/health" and float(item.get("durationMs", 0)) >= 1000 for item in slow_items):
    raise SystemExit("[FAIL] missing controlled slow /health event in observability slow-requests")
print("[PASS] controlled slow request captured in observability slow-requests")

task_items = task_failures.get("items", [])
target_task = next((item for item in task_items if item.get("jobId") == target_job_id), None)
if not target_task:
    raise SystemExit(f"[FAIL] missing task failure aggregate for {target_job_id}")
if int(target_task.get("failedCount", 0)) <= 0:
    raise SystemExit(f"[FAIL] expected failedCount > 0 for {target_job_id}")
print(f"[PASS] task failure aggregate exists for {target_job_id}: {target_task.get('failedCount')}")

now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=24)
scheduler_failed_24h = 0
tag_seen = False
for run in scheduler_runs.get("runs", []):
    started_at = run.get("startedAt")
    status = str(run.get("status") or "").upper()
    if not started_at:
        continue
    dt = datetime.fromisoformat(started_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    if dt >= cutoff and status == "FAILED":
        scheduler_failed_24h += 1
        if failure_tag in str(run.get("error") or ""):
            tag_seen = True

if not tag_seen:
    raise SystemExit("[FAIL] controlled scheduler failure tag not found in scheduler runs")

obs_failed_count = int(target_task.get("failedCount", 0))
if obs_failed_count != scheduler_failed_24h:
    raise SystemExit(
        f"[FAIL] scheduler/observability failure mismatch: observability={obs_failed_count}, scheduler={scheduler_failed_24h}"
    )
print("[PASS] scheduler and observability failure counts are consistent")
PY

echo "[PASS] observability verification passed"
