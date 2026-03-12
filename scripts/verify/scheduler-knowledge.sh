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

curl -sf "${BASE_URL}/health" >/dev/null

JOBS_JSON="$(curl -sf "${HEADERS[@]}" "${BASE_URL}/api/admin/scheduler/jobs")"
python3 - <<'PY' "$JOBS_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
jobs = payload.get("jobs", [])
if len(jobs) < 4:
    raise SystemExit(f"[FAIL] expected >=4 scheduler jobs, got {len(jobs)}")
print(f"[PASS] scheduler jobs listed: {len(jobs)}")
PY

RUN_JSON="$(curl -sf -X POST "${HEADERS[@]}" "${BASE_URL}/api/admin/scheduler/jobs/knowledge_harvest/run")"
python3 - <<'PY' "$RUN_JSON"
import json
import sys
payload = json.loads(sys.argv[1])
if not payload.get("taskId"):
    raise SystemExit("[FAIL] task dispatch missing taskId")
print(f"[PASS] knowledge_harvest dispatched: {payload['taskId']}")
PY

python3 - <<'PY' "${BASE_URL}" "${BACKEND_API_TOKEN}" "${SUPER_ADMIN_ID}"
import json
import subprocess
import sys
import time

base_url = sys.argv[1]
api_token = sys.argv[2]
user_id = sys.argv[3]

headers = [
    "-H",
    "X-User-Role: SUPER_ADMIN",
    "-H",
    f"X-User-Id: {user_id}",
    "-H",
    "Accept: application/json",
    "-H",
    f"X-API-Token: {api_token}",
]

for _ in range(10):
    cmd = ["curl", "-sf", *headers, f"{base_url}/api/admin/scheduler/runs?limit=20"]
    raw = subprocess.check_output(cmd, text=True)
    payload = json.loads(raw)
    runs = payload.get("runs", [])
    if runs:
        print(f"[PASS] scheduler runs fetched: {len(runs)}")
        break
    time.sleep(1)
else:
    raise SystemExit("[FAIL] scheduler run history is empty")
PY

echo "[PASS] scheduler and knowledge verification passed"
