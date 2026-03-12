#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${REPO_ROOT}/.devlogs"
ENV_SOURCE=""

log() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
err() { printf '[ERROR] %s\n' "$*" >&2; }

ensure_brew_bin_path() {
  if [[ -d /opt/homebrew/bin ]]; then
    export PATH="/opt/homebrew/bin:${PATH}"
  elif [[ -d /usr/local/bin ]]; then
    export PATH="/usr/local/bin:${PATH}"
  fi
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    err "Neither 'docker compose' nor 'docker-compose' is available."
    exit 20
  fi
}

copy_if_missing() {
  local from="$1"
  local to="$2"
  if [[ -f "$from" && ! -f "$to" ]]; then
    cp "$from" "$to"
    warn "Created ${to} from ${from}. Update secrets before production usage."
  fi
}

load_env() {
  cd "$REPO_ROOT"
  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    ENV_SOURCE=".env"
  elif [[ -f .env.example ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env.example
    set +a
    ENV_SOURCE=".env.example"
    warn "Using .env.example because .env was not found."
  else
    err "No .env or .env.example found at repo root."
    exit 25
  fi
}

stop_pid_if_running() {
  local pid="$1"
  if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 0.5
    if ps -p "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
}

stop_by_pid_file() {
  local name="$1"
  local pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    return
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "${pid}" ]]; then
    log "Stopping ${name} by pid file (${pid})..."
    stop_pid_if_running "$pid"
  fi
  rm -f "$pid_file"
}

stop_by_port() {
  local name="$1"
  local port="$2"
  local pids
  pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return
  fi
  log "Stopping ${name} listeners on port ${port}..."
  for pid in $pids; do
    stop_pid_if_running "$pid"
  done
}

wait_for_port() {
  local port="$1"
  local retries="${2:-30}"
  local delay="${3:-0.2}"
  local i
  for ((i=0; i<retries; i++)); do
    if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

wait_for_http_health() {
  local url="$1"
  local retries="${2:-30}"
  local delay="${3:-0.5}"
  local i
  for ((i=0; i<retries; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

assert_pid_running() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  ps -p "$pid" >/dev/null 2>&1
}

ensure_deps() {
  ensure_brew_bin_path
  command -v node >/dev/null 2>&1 || { err "Missing node"; exit 21; }
  command -v python3.11 >/dev/null 2>&1 || { err "Missing python3.11"; exit 21; }
  command -v docker >/dev/null 2>&1 || { err "Missing docker"; exit 21; }
}

ensure_project_env_files() {
  copy_if_missing "frontend/.env.local.example" "frontend/.env.local"
  copy_if_missing "backend/.env.example" "backend/.env"
}

start_infra() {
  log "Ensuring db/redis are up..."
  compose up -d db redis
}

start_frontend() {
  if [[ ! -f "${REPO_ROOT}/frontend/package.json" ]]; then
    warn "frontend/package.json not found, skipping frontend."
    return
  fi

  log "Starting frontend on ${FRONTEND_PORT}..."
  (
    cd "${REPO_ROOT}/frontend"
    if [[ ! -d node_modules ]]; then
      npm install
    fi
    nohup npm run dev -- --port "${FRONTEND_PORT}" >"${LOG_DIR}/frontend.log" 2>&1 &
    echo $! >"${LOG_DIR}/frontend.pid"
  )

  if ! assert_pid_running "${LOG_DIR}/frontend.pid"; then
    err "Frontend failed to start. Check ${LOG_DIR}/frontend.log"
    return 1
  fi
  if ! wait_for_port "$FRONTEND_PORT" 60 0.5; then
    err "Frontend did not listen on port ${FRONTEND_PORT}. Check ${LOG_DIR}/frontend.log"
    return 1
  fi
}

start_backend() {
  if [[ ! -f "${REPO_ROOT}/backend/app/main.py" ]]; then
    warn "backend/app/main.py not found, skipping backend."
    return
  fi

  log "Starting backend on ${BACKEND_PORT}..."
  (
    cd "${REPO_ROOT}/backend"
    if [[ ! -d venv ]]; then
      python3.11 -m venv venv
    fi
    venv/bin/python -m pip install -r requirements.txt >/dev/null
    nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}" </dev/null >"${LOG_DIR}/backend.log" 2>&1 &
    echo $! >"${LOG_DIR}/backend.pid"
  )

  if ! assert_pid_running "${LOG_DIR}/backend.pid"; then
    err "Backend failed to start. Check ${LOG_DIR}/backend.log"
    return 1
  fi
  if ! wait_for_port "$BACKEND_PORT" 60 0.5; then
    err "Backend did not listen on port ${BACKEND_PORT}. Check ${LOG_DIR}/backend.log"
    return 1
  fi
  if ! wait_for_http_health "http://127.0.0.1:${BACKEND_PORT}/health" 40 0.5; then
    err "Backend health check failed on /health. Check ${LOG_DIR}/backend.log"
    return 1
  fi
  # Guard against short-lived backend process that exits right after startup.
  sleep 1
  if ! assert_pid_running "${LOG_DIR}/backend.pid"; then
    err "Backend exited shortly after startup. Check ${LOG_DIR}/backend.log"
    return 1
  fi
}

start_scheduler_worker() {
  if [[ ! -f "${REPO_ROOT}/backend/app/scheduler/celery_app.py" ]]; then
    warn "Scheduler app not found, skipping celery worker."
    return
  fi

  log "Starting Celery worker..."
  (
    cd "${REPO_ROOT}/backend"
    nohup venv/bin/python -m celery -A app.scheduler.celery_app:celery_app worker --loglevel=INFO >"${LOG_DIR}/celery-worker.log" 2>&1 &
    echo $! >"${LOG_DIR}/celery-worker.pid"
  )

  if ! assert_pid_running "${LOG_DIR}/celery-worker.pid"; then
    err "Celery worker failed to start. Check ${LOG_DIR}/celery-worker.log"
    return 1
  fi
}

start_scheduler_beat() {
  if [[ ! -f "${REPO_ROOT}/backend/app/scheduler/celery_app.py" ]]; then
    warn "Scheduler app not found, skipping celery beat."
    return
  fi

  log "Starting Celery beat..."
  (
    cd "${REPO_ROOT}/backend"
    nohup venv/bin/python -m celery -A app.scheduler.celery_app:celery_app beat --loglevel=INFO >"${LOG_DIR}/celery-beat.log" 2>&1 &
    echo $! >"${LOG_DIR}/celery-beat.pid"
  )

  if ! assert_pid_running "${LOG_DIR}/celery-beat.pid"; then
    err "Celery beat failed to start. Check ${LOG_DIR}/celery-beat.log"
    return 1
  fi
}

print_summary() {
  printf '\n=== Restart Summary ===\n'
  printf 'Frontend: http://127.0.0.1:%s\n' "$FRONTEND_PORT"
  printf 'Backend:  http://127.0.0.1:%s\n' "$BACKEND_PORT"
  printf 'Scheduler Worker Log: %s/celery-worker.log\n' "$LOG_DIR"
  printf 'Scheduler Beat Log:   %s/celery-beat.log\n' "$LOG_DIR"
  printf 'Logs:     %s\n' "$LOG_DIR"
  printf 'Env:      %s\n' "$ENV_SOURCE"
}

mkdir -p "$LOG_DIR"
load_env
ensure_deps
ensure_project_env_files

FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

stop_by_pid_file "frontend" "${LOG_DIR}/frontend.pid"
stop_by_pid_file "backend" "${LOG_DIR}/backend.pid"
stop_by_pid_file "celery-worker" "${LOG_DIR}/celery-worker.pid"
stop_by_pid_file "celery-beat" "${LOG_DIR}/celery-beat.pid"
stop_by_port "frontend" "$FRONTEND_PORT"
stop_by_port "backend" "$BACKEND_PORT"

start_infra
start_backend
start_scheduler_worker
start_scheduler_beat
start_frontend
print_summary
