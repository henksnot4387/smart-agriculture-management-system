#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

log_pass() { printf '[PASS] %s\n' "$*"; }
log_fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

TRACKED_FILES="$(git ls-files | while IFS= read -r path; do
  if [[ -e "$path" ]]; then
    printf '%s\n' "$path"
  fi
done)"
CONTENT_SCAN_FILES="$(printf '%s\n' "$TRACKED_FILES" | rg -v '^scripts/verify/open-source-(privacy|history)\.sh$' || true)"

assert_no_tracked_path() {
  local pattern="$1"
  local label="$2"
  local matches
  matches="$(printf '%s\n' "$TRACKED_FILES" | rg "$pattern" || true)"
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" >&2
    log_fail "${label}"
  fi
}

assert_no_tracked_content() {
  local pattern="$1"
  local label="$2"
  local matches
  matches="$(printf '%s\n' "$CONTENT_SCAN_FILES" | xargs rg -n "$pattern" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" >&2
    log_fail "${label}"
  fi
}

assert_no_tracked_path '^\.env$|^backend/\.env$|^frontend/\.env\.local$' "发现被跟踪的真实环境变量文件。"
assert_no_tracked_path '^docs/.*\.(docx|xlsx|pdf)$' "发现被跟踪的 Office/PDF 私有文档。"
assert_no_tracked_path '^backend/data/.*\.private\.json$' "发现被跟踪的私有数据文件。"
assert_no_tracked_path '\.(pem|key|crt|p12)$' "发现被跟踪的证书或私钥文件。"

assert_no_tracked_content 'sk-[A-Za-z0-9]{20,}' "发现疑似 API Key。"
assert_no_tracked_content 'AKIA[0-9A-Z]{16}' "发现疑似云厂商 Access Key。"
assert_no_tracked_content 'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY' "发现私钥内容。"
assert_no_tracked_content 'HOOGENDOORN_SYSTEM_ID="?([0-9]{3,})"?' "发现公开模板中疑似真实系统 ID。"
assert_no_tracked_content 'SecretPassword123|SuperAdmin123|Expert123|Worker123' "发现公开文件中保留旧默认密码。"
assert_no_tracked_content 'farm\.local' "发现公开文件中保留旧内部示例邮箱域名。"

log_pass "未发现已跟踪的高风险隐私文件或常见明文密钥模式。"
