#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

log_pass() { printf '[PASS] %s\n' "$*"; }
FAILED=0
SEARCH_EXCLUDES=(
  ":(exclude)scripts/verify/open-source-privacy.sh"
  ":(exclude)scripts/verify/open-source-history.sh"
)
log_fail() {
  printf '[FAIL] %s\n' "$*" >&2
  FAILED=1
}

HISTORY_PATHS="$(git log --all --name-only --pretty=format: \
  | sed '/^$/d; s/^\"//; s/\"$//' \
  | sort -u)"

assert_no_history_path() {
  local pattern="$1"
  local label="$2"
  local matches
  matches="$(printf '%s\n' "$HISTORY_PATHS" | rg "$pattern" || true)"
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" >&2
    log_fail "${label}"
  fi
}

assert_no_history_string() {
  local pattern="$1"
  local label="$2"
  local matches
  matches="$(git log --all --oneline -G"$pattern" -- . "${SEARCH_EXCLUDES[@]}" || true)"
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" >&2
    log_fail "${label}"
  fi
}

assert_no_history_path '^\.env$|^backend/\.env$|^frontend/\.env\.local$' "Git 历史中发现过真实环境变量文件。公开前需要清理历史。"
assert_no_history_path '^docs/.*\.(docx|xlsx|pdf)$' "Git 历史中发现过 Office/PDF 私有文档。公开前需要清理历史。"
assert_no_history_path '^backend/data/.*\.private\.json$' "Git 历史中发现过私有数据文件。公开前需要清理历史。"
assert_no_history_path '\.(pem|key|crt|p12)$' "Git 历史中发现过证书或私钥文件。公开前需要清理历史。"

assert_no_history_string 'com~apple~CloudDocs' "Git 历史中发现过本地绝对路径。公开前需要清理历史。"
assert_no_history_string 'farm\.local' "Git 历史中发现过旧内部示例邮箱域名。公开前需要清理历史。"
assert_no_history_string 'SecretPassword123|SuperAdmin123|Expert123!?|Worker123!?' "Git 历史中发现过旧默认密码。公开前需要清理历史。"
assert_no_history_string 'HOOGENDOORN_SYSTEM_ID.?=.?.*7408' "Git 历史中发现过疑似真实系统 ID。公开前需要清理历史。"

if [[ ${FAILED} -ne 0 ]]; then
  exit 1
fi

log_pass "未发现 Git 历史中的常见隐私路径或敏感示例值。"
