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
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

RUN_AT="$(date '+%Y%m%d-%H%M%S')"
RUN_DIR="${REPO_ROOT}/.devlogs/full-regression/${RUN_AT}"
REPORT_PATH="${RUN_DIR}/report.md"
mkdir -p "${RUN_DIR}"

OVERALL_FAIL=0
PASS_COUNT=0
FAIL_COUNT=0

log_info() { printf '[INFO] %s\n' "$*"; }
log_pass() { printf '[PASS] %s\n' "$*"; }
log_fail() { printf '[FAIL] %s\n' "$*" >&2; }

wait_for_url() {
  local url="$1"
  local retries="${2:-40}"
  local delay="${3:-1}"
  for _ in $(seq 1 "$retries"); do
    if curl -sf "$url" >/dev/null; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

append_report_line() {
  local line="$1"
  printf '%s\n' "$line" >>"${REPORT_PATH}"
}

run_case() {
  local case_id="$1"
  local description="$2"
  local command="$3"
  local log_file="${RUN_DIR}/${case_id}.log"

  log_info "Running ${case_id}: ${description}"
  local start_ts end_ts duration status
  start_ts="$(date +%s)"

  set +e
  bash -lc "$command" >"${log_file}" 2>&1
  local exit_code=$?
  set -e

  end_ts="$(date +%s)"
  duration="$((end_ts - start_ts))s"

  if [[ $exit_code -eq 0 ]]; then
    status="PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
    log_pass "${case_id} (${duration})"
  else
    status="FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    OVERALL_FAIL=1
    log_fail "${case_id} (${duration}) -> see ${log_file}"
  fi

  append_report_line "| ${case_id} | ${description} | ${status} | ${duration} | \`${log_file}\` |"
}

cat >"${REPORT_PATH}" <<EOF
# 全链路联调与回归测试报告

- 运行时间: ${RUN_AT}
- Backend: ${BACKEND_URL}
- Frontend: ${FRONTEND_URL}

| Case ID | 描述 | 结果 | 耗时 | 日志 |
|---|---|---|---|---|
EOF

log_info "Checking service readiness..."
if ! wait_for_url "${BACKEND_URL}/health" 40 1; then
  log_fail "Backend not ready: ${BACKEND_URL}/health"
  exit 20
fi
if ! wait_for_url "${FRONTEND_URL}/login" 40 1; then
  log_fail "Frontend not ready: ${FRONTEND_URL}/login"
  exit 21
fi

run_case "AUTH-UI" "前端登录/重定向/RBAC E2E smoke" "cd '${REPO_ROOT}/frontend' && FRONTEND_BASE_URL='${FRONTEND_URL}' npm run test:e2e-smoke"
run_case "BACKEND-UNIT" "后端 pytest 单元回归" "cd '${REPO_ROOT}/backend' && venv/bin/python -m pytest tests -q"
run_case "BACKEND-COMPILE" "后端编译检查" "python3.11 -m compileall '${REPO_ROOT}/backend/app'"
run_case "FRONTEND-LINT" "前端 lint" "cd '${REPO_ROOT}/frontend' && npm run lint"
run_case "FRONTEND-BUILD" "前端 build" "cd '${REPO_ROOT}/frontend' && npm run build"
run_case "VISION" "视觉链路（上传->受理->完成->实时回传）" "bash '${REPO_ROOT}/scripts/verify/vision-pipeline.sh'"
run_case "SCHEDULER" "调度与知识采集回归" "bash '${REPO_ROOT}/scripts/verify/scheduler-knowledge.sh'"
run_case "COPILOT" "AI 建议生成与入库回归" "bash '${REPO_ROOT}/scripts/verify/ai-recommendation.sh'"
run_case "TASKS" "专家审批与工人执行闭环回归" "bash '${REPO_ROOT}/scripts/verify/approval-execution.sh'"
run_case "TIMESERIES" "时序分层聚合与策略回归" "bash '${REPO_ROOT}/scripts/verify/timeseries-policy.sh'"
run_case "OBSERVE" "可观测性链路与一致性回归" "bash '${REPO_ROOT}/scripts/verify/observability.sh'"

append_report_line ""
append_report_line "- PASS: ${PASS_COUNT}"
append_report_line "- FAIL: ${FAIL_COUNT}"

printf '\n=== Full Regression Summary ===\n'
printf 'PASS: %s\n' "${PASS_COUNT}"
printf 'FAIL: %s\n' "${FAIL_COUNT}"
printf 'Report: %s\n' "${REPORT_PATH}"

if [[ "${OVERALL_FAIL}" -ne 0 ]]; then
  exit 1
fi
