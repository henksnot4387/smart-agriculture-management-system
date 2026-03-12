#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.prod.yml"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}"
GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://127.0.0.1:${NGINX_HTTP_PORT}}"
VISION_WS_PATH="/api/ws/vision/tasks"

log() { printf '[INFO] %s\n' "$*"; }
pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; }

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    fail "Neither 'docker compose' nor 'docker-compose' is available."
    exit 20
  fi
}

wait_http_ok() {
  local url="$1"
  local retries="${2:-40}"
  local delay="${3:-2}"
  for _ in $(seq 1 "${retries}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${delay}"
  done
  return 1
}

assert_service_running() {
  local service="$1"
  local running_services
  running_services="$(compose -f "${COMPOSE_FILE}" ps --status running --services)"
  if ! printf '%s\n' "${running_services}" | grep -qx "${service}"; then
    fail "Service not running: ${service}"
    return 1
  fi
  pass "Service running: ${service}"
}

assert_service_healthy() {
  local service="$1"
  local container_id
  container_id="$(compose -f "${COMPOSE_FILE}" ps -q "${service}")"
  if [[ -z "${container_id}" ]]; then
    fail "Service has no container id: ${service}"
    return 1
  fi

  local health
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container_id}")"
  if [[ "${health}" != "healthy" ]]; then
    fail "Service not healthy: ${service} (health=${health})"
    return 1
  fi
  pass "Service healthy: ${service}"
}

probe_ws_path() {
  local ws_url="${GATEWAY_BASE_URL}${VISION_WS_PATH}"
  if [[ -n "${BACKEND_API_TOKEN:-}" ]]; then
    ws_url="${ws_url}?token=${BACKEND_API_TOKEN}"
  fi

  local status
  status="$(
    curl -sS -o /tmp/production_ws_probe.out -w '%{http_code}' \
      -H 'Connection: Upgrade' \
      -H 'Upgrade: websocket' \
      -H 'Sec-WebSocket-Version: 13' \
      -H 'Sec-WebSocket-Key: dG9rZW5wcm9iZTEyMw==' \
      "${ws_url}"
  )"

  case "${status}" in
    101|400|401|403|426)
      pass "Vision websocket path reachable via gateway (${status})"
      ;;
    *)
      fail "Vision websocket path probe failed (${status})"
      if [[ -f /tmp/production_ws_probe.out ]]; then
        cat /tmp/production_ws_probe.out >&2 || true
      fi
      return 1
      ;;
  esac
}

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  fail "Missing compose file: ${COMPOSE_FILE}"
  exit 21
fi

cd "${REPO_ROOT}"

log "Verifying production stack from ${COMPOSE_FILE}"
assert_service_running "nginx"
assert_service_running "frontend"
assert_service_running "backend"
assert_service_running "celery-worker"
assert_service_running "celery-beat"

assert_service_healthy "nginx"
assert_service_healthy "frontend"
assert_service_healthy "backend"

if ! wait_http_ok "${GATEWAY_BASE_URL}/"; then
  fail "Gateway homepage check failed: ${GATEWAY_BASE_URL}/"
  exit 1
fi
pass "Gateway homepage reachable"

if ! wait_http_ok "${GATEWAY_BASE_URL}/backend-health"; then
  fail "Backend health proxy check failed: ${GATEWAY_BASE_URL}/backend-health"
  exit 1
fi
pass "Backend health proxy reachable"

probe_ws_path

printf '\n[PASS] Production validation passed:\n'
printf '       - Containers running and core services healthy\n'
printf '       - Gateway reachable at %s/\n' "${GATEWAY_BASE_URL}"
printf '       - Backend health reachable at %s/backend-health\n' "${GATEWAY_BASE_URL}"
printf '       - Vision websocket route reachable at %s%s\n' "${GATEWAY_BASE_URL}" "${VISION_WS_PATH}"
