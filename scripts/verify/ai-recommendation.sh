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
BASE_URL="http://127.0.0.1:${BACKEND_PORT}"
BACKEND_API_TOKEN="${BACKEND_API_TOKEN:-}"

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

EXPERT_ID="$(
  cd "${REPO_ROOT}/backend"
  venv/bin/python - <<'PY'
import psycopg
from app.core.config import settings

with psycopg.connect(settings.psycopg_database_url) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id::text FROM users WHERE email = %s LIMIT 1",
            ("expert@example.local",),
        )
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """
                SELECT id::text
                FROM users
                WHERE role IN ('EXPERT'::"UserRole", 'ADMIN'::"UserRole", 'SUPER_ADMIN'::"UserRole")
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
if not row:
    raise SystemExit("[FAIL] no EXPERT/ADMIN/SUPER_ADMIN user found in users table.")
print(row[0])
PY
)"

if [[ -z "${EXPERT_ID}" ]]; then
  echo "[FAIL] expert@example.local not found."
  exit 21
fi

HEADERS=(-H "Accept: application/json" -H "Content-Type: application/json" -H "X-User-Role: EXPERT" -H "X-User-Id: ${EXPERT_ID}" -H "X-API-Token: ${BACKEND_API_TOKEN}")

CREATE_JSON="$(
  curl -sf -X POST "${HEADERS[@]}" \
    "${BASE_URL}/api/ai-insights/recommendations" \
    -d '{"hours":24,"instruction":"关注番茄温室夜间湿度回落与灰霉风险，输出可执行建议。","maxItems":3}'
)"

DRAFT_IDS="$(python3 - <<'PY' "$CREATE_JSON"
import json
import sys

payload = json.loads(sys.argv[1])
items = payload.get("recommendations", [])
if not items:
    raise SystemExit("[FAIL] recommendation list is empty")

for item in items:
    if not item.get("draftId"):
        raise SystemExit("[FAIL] missing draftId in recommendation item")
    if item.get("status") != "PENDING":
        raise SystemExit(f"[FAIL] unexpected status: {item.get('status')}")

print("[PASS] recommendations generated:", len(items), file=sys.stderr)
print(",".join(item["draftId"] for item in items))
PY
)"

LIST_JSON="$(
  curl -sf -X GET "${HEADERS[@]}" \
    "${BASE_URL}/api/ai-insights/recommendations?limit=20&status=PENDING"
)"

python3 - <<'PY' "$LIST_JSON" "$DRAFT_IDS"
import json
import sys

payload = json.loads(sys.argv[1])
expected_ids = {item for item in sys.argv[2].split(",") if item}
history_ids = {item.get("draftId") for item in payload.get("items", [])}

if not expected_ids.issubset(history_ids):
    raise SystemExit("[FAIL] generated recommendations not found in history list")
print("[PASS] recommendations listed in history:", len(history_ids))
PY

CONFIRM_JSON="$(
  python3 - <<'PY' "$DRAFT_IDS" "$BASE_URL" "$BACKEND_API_TOKEN" "$EXPERT_ID"
import json
import subprocess
import sys

draft_ids = [item for item in sys.argv[1].split(",") if item]
base_url = sys.argv[2]
token = sys.argv[3]
expert_id = sys.argv[4]

payload = json.dumps({"draftIds": draft_ids})
cmd = [
    "curl", "-sf", "-X", "POST",
    f"{base_url}/api/ai-insights/recommendations/confirm",
    "-H", "Accept: application/json",
    "-H", "Content-Type: application/json",
    "-H", "X-User-Role: EXPERT",
    "-H", f"X-User-Id: {expert_id}",
    "-H", f"X-API-Token: {token}",
    "-d", payload,
]
print(subprocess.check_output(cmd, text=True).strip())
PY
)"

TASK_IDS="$(python3 - <<'PY' "$CONFIRM_JSON"
import json
import sys

payload = json.loads(sys.argv[1])
tasks = payload.get("tasks", [])
if not tasks:
    raise SystemExit("[FAIL] no tasks created during confirm")
print("[PASS] confirmed drafts into tasks:", len(tasks), file=sys.stderr)
print(",".join(item["taskId"] for item in tasks))
PY
)"

cd "${REPO_ROOT}/backend"
venv/bin/python - <<'PY' "$TASK_IDS"
import psycopg
import sys
from app.core.config import settings

task_ids = [item for item in sys.argv[1].split(",") if item]
if not task_ids:
    raise SystemExit("[FAIL] task id list is empty")

sql = """
SELECT id::text, status::text, source::text
FROM tasks
WHERE id = ANY(%s::uuid[])
"""
with psycopg.connect(settings.psycopg_database_url) as conn:
    with conn.cursor() as cursor:
        cursor.execute(sql, (task_ids,))
        rows = cursor.fetchall()

if len(rows) != len(task_ids):
    raise SystemExit("[FAIL] generated tasks missing in database")
for task_id, status, source in rows:
    if status != "PENDING" or source != "AI":
        raise SystemExit(f"[FAIL] task {task_id} invalid status/source: {status}/{source}")
print(f"[PASS] database tasks verified: {len(rows)}")
PY

echo "[PASS] AI recommendation draft/confirm verification passed"
