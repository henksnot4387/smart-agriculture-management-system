#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIFY_DIR="${REPO_ROOT}/scripts/verify"
CORE_CASES=(
  vision-pipeline
  scheduler-knowledge
  ai-recommendation
  approval-execution
  timeseries-policy
  observability
  full-regression
)
PRIVACY_CASES=(
  open-source-privacy
  open-source-history
)
ALL_CASES=(
  open-source-privacy
  open-source-history
  vision-pipeline
  scheduler-knowledge
  ai-recommendation
  approval-execution
  timeseries-policy
  observability
  full-regression
  production-readiness
)

usage() {
  cat <<'USAGE'
Usage (推荐):
  bash scripts/verify.sh               # 交互选择菜单（终端模式）
  bash scripts/verify.sh menu          # 显式打开菜单

Usage (业务别名):
  bash scripts/verify.sh vision        # 病害识别链路
  bash scripts/verify.sh scheduler     # 调度与知识采集
  bash scripts/verify.sh insights      # AI 智能解析与建议入库
  bash scripts/verify.sh tasks         # 专家审批与工人执行闭环
  bash scripts/verify.sh timescale     # 时序聚合与保留策略
  bash scripts/verify.sh observability # 可观测性
  bash scripts/verify.sh privacy       # 开源隐私自检（当前文件 + Git历史）
  bash scripts/verify.sh privacy-current
  bash scripts/verify.sh privacy-history
  bash scripts/verify.sh regression    # 全链路回归
  bash scripts/verify.sh production    # 生产部署验收
  bash scripts/verify.sh core          # 核心验收合集
  bash scripts/verify.sh full          # 全量验收合集

Usage (兼容命令):
  bash scripts/verify.sh baseline|all
  bash scripts/verify.sh list|help
USAGE
}

run_case() {
  local id="$1"
  echo "[INFO] Running verify case: ${id}"
  bash "${VERIFY_DIR}/${id}.sh"
}

run_many() {
  local ids=("$@")
  local failed=0
  local id
  for id in "${ids[@]}"; do
    if ! run_case "${id}"; then
      failed=1
      echo "[FAIL] verify case failed: ${id}" >&2
    fi
  done
  if [[ ${failed} -ne 0 ]]; then
    exit 1
  fi
}

show_menu() {
  cat <<'MENU'
请选择验收项（输入编号）：
  1) 病害识别链路
  2) 调度与知识采集
  3) AI智能解析与建议入库
  4) 审批与执行闭环
  5) 时序聚合与保留策略
  6) 可观测性
  7) 开源隐私自检（当前文件 + Git历史）
  8) 当前文件隐私扫描
  9) Git历史隐私扫描
 10) 全链路回归
 11) 生产部署验收
 12) 核心验收合集
 13) 全量验收合集
  0) 退出
MENU
}

run_menu() {
  show_menu
  read -r -p "请输入编号: " choice
  case "${choice}" in
    1) run_case vision-pipeline ;;
    2) run_case scheduler-knowledge ;;
    3) run_case ai-recommendation ;;
    4) run_case approval-execution ;;
    5) run_case timeseries-policy ;;
    6) run_case observability ;;
    7) run_many "${PRIVACY_CASES[@]}" ;;
    8) run_case open-source-privacy ;;
    9) run_case open-source-history ;;
    10) run_case full-regression ;;
    11) run_case production-readiness ;;
    12) run_many "${CORE_CASES[@]}" ;;
    13) run_many "${ALL_CASES[@]}" ;;
    0) echo "[INFO] 已退出" ;;
    *)
      echo "[FAIL] 无效编号: ${choice}" >&2
      exit 2
      ;;
  esac
}

resolve_alias() {
  local cmd="$1"
  case "${cmd}" in
    vision) echo "vision-pipeline" ;;
    scheduler) echo "scheduler-knowledge" ;;
    copilot) echo "ai-recommendation" ;;
    insights) echo "ai-recommendation" ;;
    tasks) echo "approval-execution" ;;
    timescale) echo "timeseries-policy" ;;
    observability) echo "observability" ;;
    privacy) echo "privacy-all" ;;
    privacy-current) echo "open-source-privacy" ;;
    privacy-history) echo "open-source-history" ;;
    regression) echo "full-regression" ;;
    production) echo "production-readiness" ;;
    core) echo "baseline" ;;
    full) echo "all" ;;
    *) echo "${cmd}" ;;
  esac
}

if [[ $# -eq 0 ]]; then
  if [[ -t 0 ]]; then
    command="menu"
  else
    command="list"
  fi
else
  command="$1"
  shift || true
fi

command="$(resolve_alias "${command}")"

case "${command}" in
  list|help|--help|-h)
    usage
    ;;
  menu)
    run_menu
    ;;
  privacy-all)
    run_many "${PRIVACY_CASES[@]}"
    ;;
  open-source-privacy|open-source-history|vision-pipeline|scheduler-knowledge|ai-recommendation|approval-execution|timeseries-policy|observability|full-regression|production-readiness)
    run_case "${command}"
    ;;
  baseline)
    run_many "${CORE_CASES[@]}"
    ;;
  all)
    run_many "${ALL_CASES[@]}"
    ;;
  *)
    echo "[FAIL] Unknown verify command: ${command}" >&2
    usage
    exit 2
    ;;
esac
