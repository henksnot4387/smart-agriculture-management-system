#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; }
info() { printf '[INFO] %s\n' "$*"; }

check_non_empty() {
  local var_name="$1"
  local value="${!var_name:-}"
  if [[ -z "${value}" ]]; then
    fail "Missing required env: ${var_name}"
    return 1
  fi
  pass "Env present: ${var_name}"
}

check_one_of() {
  local var_name="$1"
  local expected_a="$2"
  local expected_b="$3"
  local value="${!var_name:-}"
  if [[ "${value}" != "${expected_a}" && "${value}" != "${expected_b}" ]]; then
    fail "${var_name} must be '${expected_a}' or '${expected_b}', got '${value}'"
    return 1
  fi
  pass "Env valid: ${var_name}=${value}"
}

check_url_like() {
  local var_name="$1"
  local value="${!var_name:-}"
  if [[ -z "${value}" ]]; then
    fail "Missing required env: ${var_name}"
    return 1
  fi
  if [[ ! "${value}" =~ ^https?:// && ! "${value}" =~ ^postgresql:// && ! "${value}" =~ ^redis:// ]]; then
    fail "${var_name} should look like URL, got '${value}'"
    return 1
  fi
  pass "URL-like env valid: ${var_name}"
}

has_failure=0

run_check() {
  if ! "$@"; then
    has_failure=1
  fi
}

info "Checking production env requirements..."

run_check check_non_empty APP_ENV
if [[ "${APP_ENV:-}" != "production" && "${APP_ENV:-}" != "prod" ]]; then
  fail "APP_ENV should be 'production' (or 'prod') for production deployment, got '${APP_ENV:-}'"
  has_failure=1
else
  pass "APP_ENV is production-like (${APP_ENV})"
fi

run_check check_url_like DATABASE_URL
run_check check_url_like REDIS_URL
run_check check_url_like NEXTAUTH_URL
run_check check_non_empty NEXTAUTH_SECRET
run_check check_non_empty BACKEND_API_TOKEN
run_check check_url_like BACKEND_INTERNAL_BASE_URL
run_check check_url_like BACKEND_PUBLIC_BASE_URL

run_check check_non_empty FILE_STORAGE_BACKEND
if [[ "${FILE_STORAGE_BACKEND:-}" != "object" ]]; then
  fail "FILE_STORAGE_BACKEND must be 'object' in production, got '${FILE_STORAGE_BACKEND:-}'"
  has_failure=1
else
  pass "FILE_STORAGE_BACKEND is object"
fi

run_check check_url_like OBJECT_STORAGE_ENDPOINT
run_check check_non_empty OBJECT_STORAGE_REGION
run_check check_non_empty OBJECT_STORAGE_BUCKET
run_check check_non_empty OBJECT_STORAGE_ACCESS_KEY_ID
run_check check_non_empty OBJECT_STORAGE_SECRET_ACCESS_KEY
run_check check_url_like OBJECT_STORAGE_PUBLIC_BASE_URL

run_check check_one_of OBJECT_STORAGE_FORCE_PATH_STYLE true false

if [[ "${has_failure}" -ne 0 ]]; then
  printf '\n[FAIL] Production env validation failed.\n' >&2
  exit 1
fi

printf '\n[PASS] Production env validation passed.\n'
