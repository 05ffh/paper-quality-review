#!/usr/bin/env bash
# 论文质量审查 - 依赖前置检查
# 用法：bash scripts/preflight.sh
# 效果：
#   1. 检查 python3 是否可用
#   2. 检查 python-docx 与 pdfplumber 是否已安装
#   3. 缺失依赖时用 pip --user 尝试安装，失败则给出明确指引
#   4. 输出简明报告，供上层 skill 调度器决定是否继续

set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"

log()  { printf '[preflight] %s\n' "$*"; }
warn() { printf '[preflight][WARN] %s\n' "$*" >&2; }
err()  { printf '[preflight][ERROR] %s\n' "$*" >&2; }

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  err "未找到 $PYTHON_BIN，请先安装 Python 3.9+"
  exit 2
fi

PY_VER=$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
log "Python: $PYTHON_BIN ($PY_VER)"

check_pkg() {
  local pkg="$1"
  local import_name="$2"
  if "$PYTHON_BIN" -c "import $import_name" >/dev/null 2>&1; then
    log "已安装：$pkg"
    return 0
  fi

  warn "缺少 $pkg，尝试自动安装..."
  # PEP 668 环境（Debian/Ubuntu 新版）需要 --break-system-packages
  local pip_flags=("install" "--user" "--quiet")
  if "$PYTHON_BIN" -m pip install --help 2>&1 | grep -q -- '--break-system-packages'; then
    pip_flags+=("--break-system-packages")
  fi
  if "$PYTHON_BIN" -m pip "${pip_flags[@]}" "$pkg" >/dev/null 2>&1; then
    if "$PYTHON_BIN" -c "import $import_name" >/dev/null 2>&1; then
      log "已成功安装 $pkg"
      return 0
    fi
  fi

  err "无法自动安装 $pkg，请手动执行：$PYTHON_BIN -m pip install --user $pkg"
  err "（如遇 externally-managed 报错，追加 --break-system-packages）"
  return 1
}

MISSING=0
check_pkg "python-docx" "docx" || MISSING=1
check_pkg "pdfplumber" "pdfplumber" || MISSING=1

if [ "$MISSING" -ne 0 ]; then
  err "依赖检查未通过，请先手动安装缺失依赖后重试。"
  exit 1
fi

log "依赖检查通过。"
exit 0
