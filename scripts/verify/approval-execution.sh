#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

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

IDS_JSON="$(
  cd "${REPO_ROOT}/backend"
  venv/bin/python - <<'PY'
import json
import psycopg
from app.core.config import settings

with psycopg.connect(settings.psycopg_database_url) as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id::text FROM users WHERE email = %s LIMIT 1", ("expert@example.local",))
        expert = cursor.fetchone()
        cursor.execute("SELECT id::text FROM users WHERE email = %s LIMIT 1", ("worker@example.local",))
        worker = cursor.fetchone()
if not expert or not worker:
    raise SystemExit("[FAIL] expert@example.local or worker@example.local missing.")
print(json.dumps({"expert": expert[0], "worker": worker[0]}))
PY
)"

EXPERT_ID="$(python3 - <<'PY' "$IDS_JSON"
import json,sys
print(json.loads(sys.argv[1])["expert"])
PY
)"
WORKER_ID="$(python3 - <<'PY' "$IDS_JSON"
import json,sys
print(json.loads(sys.argv[1])["worker"])
PY
)"

common_headers=(-H "Accept: application/json" -H "Content-Type: application/json" -H "X-API-Token: ${BACKEND_API_TOKEN}")

create_pending_task() {
  local user_id="$1"
  curl -sf -X POST \
    "${BASE_URL}/api/ai-insights/recommendations" \
    "${common_headers[@]}" \
    -H "X-User-Role: EXPERT" \
    -H "X-User-Id: ${user_id}" \
    -d '{"hours":24,"instruction":"用于审批与执行闭环联调：请输出 1 条可执行建议。","maxItems":1}'
}

extract_task_id() {
  python3 - <<'PY' "$1"
import json
import sys
payload = json.loads(sys.argv[1])
items = payload.get("recommendations", [])
if not items:
    raise SystemExit("[FAIL] no recommendation generated")
draft_id = items[0].get("draftId")
if not draft_id:
    raise SystemExit("[FAIL] recommendation missing draftId")
print(draft_id)
PY
}

PENDING_JSON="$(create_pending_task "$EXPERT_ID")"
DRAFT_ID="$(extract_task_id "$PENDING_JSON")"
echo "[PASS] created pending draft: ${DRAFT_ID}"

CONFIRM_JSON="$(
  curl -sf -X POST \
    "${BASE_URL}/api/ai-insights/recommendations/confirm" \
    "${common_headers[@]}" \
    -H "X-User-Role: EXPERT" \
    -H "X-User-Id: ${EXPERT_ID}" \
    -d "{\"draftIds\":[\"${DRAFT_ID}\"]}"
)"

TASK_ID="$(python3 - <<'PY' "$CONFIRM_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
tasks = payload.get("tasks", [])
if not tasks:
    raise SystemExit("[FAIL] no task created from draft confirm")
print(tasks[0]["taskId"])
PY
)"
echo "[PASS] confirmed draft to task: ${TASK_ID}"

WORKER_APPROVE_STATUS="$(
  curl -s -o /tmp/worker_approve_forbidden.json -w "%{http_code}" -X POST \
    "${BASE_URL}/api/tasks/${TASK_ID}/approve" \
    "${common_headers[@]}" \
    -H "X-User-Role: WORKER" \
    -H "X-User-Id: ${WORKER_ID}" \
    -d '{"assigneeId":null}'
)"
if [[ "$WORKER_APPROVE_STATUS" != "403" ]]; then
  echo "[FAIL] worker approve expected 403, got ${WORKER_APPROVE_STATUS}"
  cat /tmp/worker_approve_forbidden.json
  exit 30
fi
echo "[PASS] worker approve forbidden (403)"

APPROVE_JSON="$(
  curl -sf -X POST \
    "${BASE_URL}/api/tasks/${TASK_ID}/approve" \
    "${common_headers[@]}" \
    -H "X-User-Role: EXPERT" \
    -H "X-User-Id: ${EXPERT_ID}" \
    -d '{"assigneeId":null}'
)"
python3 - <<'PY' "$APPROVE_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
if payload.get("task", {}).get("status") != "APPROVED":
    raise SystemExit("[FAIL] task not transitioned to APPROVED")
print("[PASS] approved by expert")
PY

CLAIM_JSON="$(
  curl -sf -X POST \
    "${BASE_URL}/api/tasks/${TASK_ID}/claim" \
    "${common_headers[@]}" \
    -H "X-User-Role: WORKER" \
    -H "X-User-Id: ${WORKER_ID}" \
    -d '{}'
)"
python3 - <<'PY' "$CLAIM_JSON" "$WORKER_ID"
import json
import sys
payload = json.loads(sys.argv[1])
worker_id = sys.argv[2]
task = payload.get("task", {})
if task.get("assigneeId") != worker_id:
    raise SystemExit("[FAIL] task assignee mismatch after claim")
print("[PASS] worker claimed task")
PY

START_JSON="$(
  curl -sf -X POST \
    "${BASE_URL}/api/tasks/${TASK_ID}/start" \
    "${common_headers[@]}" \
    -H "X-User-Role: WORKER" \
    -H "X-User-Id: ${WORKER_ID}" \
    -d '{}'
)"
python3 - <<'PY' "$START_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
if payload.get("task", {}).get("status") != "IN_PROGRESS":
    raise SystemExit("[FAIL] task not transitioned to IN_PROGRESS")
print("[PASS] worker started task")
PY

COMPLETE_JSON="$(
  curl -sf -X POST \
    "${BASE_URL}/api/tasks/${TASK_ID}/complete" \
    "${common_headers[@]}" \
    -H "X-User-Role: WORKER" \
    -H "X-User-Id: ${WORKER_ID}" \
    -d '{
      "operationType":"INSPECTION",
      "executedActions":["巡检风机与滴灌阀组","复核异常分区读数"],
      "readingsBefore":{"temperature":24.2,"humidity":88.1,"ec":2.9,"ph":5.8},
      "readingsAfter":{"temperature":23.5,"humidity":82.0,"ec":2.6,"ph":5.9},
      "materials":[{"name":"叶面肥A","amount":2.5,"unit":"L"}],
      "anomalies":["2号温室南区湿度高于阈值"],
      "resultSummary":"完成执行后湿度回落，EC趋于稳定，建议持续跟踪夜间波动。",
      "attachments":["https://example.com/worker/report-1.jpg"]
    }'
)"
python3 - <<'PY' "$COMPLETE_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
if payload.get("task", {}).get("status") != "COMPLETED":
    raise SystemExit("[FAIL] task not transitioned to COMPLETED")
print("[PASS] worker completed task")
PY

DETAIL_JSON="$(
  curl -sf \
    "${BASE_URL}/api/tasks/${TASK_ID}" \
    "${common_headers[@]}" \
    -H "X-User-Role: EXPERT" \
    -H "X-User-Id: ${EXPERT_ID}"
)"
python3 - <<'PY' "$DETAIL_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
task = payload.get("task", {})
if task.get("status") != "COMPLETED":
    raise SystemExit("[FAIL] detail query status mismatch")
report = ((task.get("metadata") or {}).get("executionReport") or {})
if report.get("operationType") != "INSPECTION":
    raise SystemExit("[FAIL] executionReport missing operationType")
if not report.get("resultSummary"):
    raise SystemExit("[FAIL] executionReport missing resultSummary")
print("[PASS] detail contains structured executionReport")
PY

echo "[PASS] approval and execution verification passed"
