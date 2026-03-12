#!/usr/bin/env bash
set -euo pipefail

FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://127.0.0.1:${FRONTEND_PORT:-3000}}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

SEED_SUPER_ADMIN_PASSWORD="${SEED_SUPER_ADMIN_PASSWORD:-change-me-superadmin-password}"
SEED_EXPERT_PASSWORD="${SEED_EXPERT_PASSWORD:-change-me-expert-password}"
SEED_WORKER_PASSWORD="${SEED_WORKER_PASSWORD:-change-me-worker-password}"

log_pass() { printf '[PASS] %s\n' "$*"; }
log_fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

wait_for_frontend() {
  local retries=30
  for _ in $(seq 1 "$retries"); do
    if curl -sf "${FRONTEND_BASE_URL}/login" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

extract_status_and_location() {
  local url="$1"
  local cookie_file="${2:-}"
  local headers_file="$TMP_DIR/headers.txt"
  if [[ -n "$cookie_file" ]]; then
    curl -s -D "$headers_file" -o /dev/null -b "$cookie_file" "$url" >/dev/null
  else
    curl -s -D "$headers_file" -o /dev/null "$url" >/dev/null
  fi
  local status location
  status="$(awk '/^HTTP\/[0-9.]+/ {print $2; exit}' "$headers_file" | tr -d '\r')"
  location="$(awk 'tolower($1)=="location:"{print $2; exit}' "$headers_file" | tr -d '\r')"
  printf '%s|%s' "$status" "$location"
}

login_with_credentials() {
  local email="$1"
  local password="$2"
  local cookie_file="$3"

  local csrf
  csrf="$(
    curl -s -c "$cookie_file" "${FRONTEND_BASE_URL}/api/auth/csrf" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("csrfToken",""))'
  )"
  [[ -n "$csrf" ]] || log_fail "获取 CSRF token 失败（${email}）"

  curl -s -b "$cookie_file" -c "$cookie_file" \
    -X POST "${FRONTEND_BASE_URL}/api/auth/callback/credentials?json=true" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "csrfToken=${csrf}" \
    --data-urlencode "email=${email}" \
    --data-urlencode "password=${password}" \
    --data-urlencode "callbackUrl=${FRONTEND_BASE_URL}/dashboard" \
    >/dev/null

  local session_email
  session_email="$(
    curl -s -b "$cookie_file" "${FRONTEND_BASE_URL}/api/auth/session" \
      | python3 -c 'import json,sys; print(((json.load(sys.stdin).get("user") or {}).get("email")) or "")'
  )"
  [[ "$session_email" == "$email" ]] || log_fail "登录后 session 校验失败，期望 ${email}，实际 ${session_email}"
}

check_auth_redirects() {
  local result status location
  result="$(extract_status_and_location "${FRONTEND_BASE_URL}/dashboard")"
  status="${result%%|*}"
  location="${result##*|}"
  [[ "$status" == "307" && "$location" == "/login" ]] \
    || log_fail "未登录访问 /dashboard 未正确重定向到 /login（status=${status}, location=${location}）"
  log_pass "AUTH-01 未登录访问受保护路由重定向正常"
}

check_expert_flow() {
  local cookie_file="$TMP_DIR/expert.cookie"
  login_with_credentials "expert@example.local" "$SEED_EXPERT_PASSWORD" "$cookie_file"

  local dashboard_status
  dashboard_status="$(curl -s -o /dev/null -w "%{http_code}" -b "$cookie_file" "${FRONTEND_BASE_URL}/dashboard")"
  [[ "$dashboard_status" == "200" ]] || log_fail "专家登录后访问 /dashboard 失败（status=${dashboard_status}）"

  local sensor_status
  sensor_status="$(
    curl -s -o /tmp/t19_sensor_proxy.json -w "%{http_code}" \
      -b "$cookie_file" \
      "${FRONTEND_BASE_URL}/api/dashboard/sensor?range=24h"
  )"
  [[ "$sensor_status" == "200" ]] || log_fail "专家调用 /api/dashboard/sensor 失败（status=${sensor_status}）"
  grep -q '"summary"' /tmp/t19_sensor_proxy.json || log_fail "/api/dashboard/sensor 返回缺少 summary 字段"

  local copilot_status
  copilot_status="$(
    curl -s -o /tmp/t19_copilot_proxy.json -w "%{http_code}" \
      -b "$cookie_file" \
      "${FRONTEND_BASE_URL}/api/copilot/recommendations?limit=5&status=PENDING"
  )"
  [[ "$copilot_status" == "200" ]] || log_fail "专家调用 /api/copilot/recommendations 失败（status=${copilot_status}）"
  log_pass "AUTH-02 专家登录后核心代理链路正常"
}

check_super_admin_flow() {
  local cookie_file="$TMP_DIR/superadmin.cookie"
  login_with_credentials "superadmin@example.local" "$SEED_SUPER_ADMIN_PASSWORD" "$cookie_file"

  local scheduler_status
  scheduler_status="$(curl -s -o /dev/null -w "%{http_code}" -b "$cookie_file" "${FRONTEND_BASE_URL}/scheduler")"
  [[ "$scheduler_status" == "200" ]] || log_fail "SUPER_ADMIN 访问 /scheduler 失败（status=${scheduler_status}）"

  local observability_status
  observability_status="$(curl -s -o /dev/null -w "%{http_code}" -b "$cookie_file" "${FRONTEND_BASE_URL}/observability")"
  [[ "$observability_status" == "200" ]] || log_fail "SUPER_ADMIN 访问 /observability 失败（status=${observability_status}）"

  local observability_api_status
  observability_api_status="$(
    curl -s -o /tmp/t19_obs_proxy.json -w "%{http_code}" \
      -b "$cookie_file" \
      "${FRONTEND_BASE_URL}/api/admin/observability/overview?hours=24"
  )"
  [[ "$observability_api_status" == "200" ]] \
    || log_fail "SUPER_ADMIN 调用 /api/admin/observability/overview 失败（status=${observability_api_status}）"
  grep -q '"totalRequests"' /tmp/t19_obs_proxy.json || log_fail "可观测 overview 返回缺少 totalRequests 字段"
  log_pass "SUPER_ADMIN 调度中心与可观测中心访问正常"
}

check_worker_rbac() {
  local cookie_file="$TMP_DIR/worker.cookie"
  login_with_credentials "worker@example.local" "$SEED_WORKER_PASSWORD" "$cookie_file"

  local result status location
  result="$(extract_status_and_location "${FRONTEND_BASE_URL}/scheduler" "$cookie_file")"
  status="${result%%|*}"
  location="${result##*|}"
  [[ "$status" == "307" && "$location" == "/dashboard" ]] \
    || log_fail "WORKER 访问 /scheduler 未被重定向（status=${status}, location=${location}）"

  local scheduler_api_status
  scheduler_api_status="$(
    curl -s -o /tmp/t19_worker_scheduler_api.json -w "%{http_code}" \
      -b "$cookie_file" \
      "${FRONTEND_BASE_URL}/api/admin/scheduler/jobs"
  )"
  [[ "$scheduler_api_status" == "403" ]] || log_fail "WORKER 调用 /api/admin/scheduler/jobs 期望 403，实际 ${scheduler_api_status}"
  log_pass "WORKER RBAC（调度中心）校验通过"
}

if ! wait_for_frontend; then
  log_fail "前端服务未就绪：${FRONTEND_BASE_URL}"
fi

check_auth_redirects
check_expert_flow
check_super_admin_flow
check_worker_rbac

log_pass "Frontend E2E smoke passed"
