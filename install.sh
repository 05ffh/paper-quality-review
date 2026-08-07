#!/usr/bin/env bash
# 论文质量审查 Skill - 一键安装到 ArkClaw / Claude Code / OpenClaw
#
# 用法：
#   bash install.sh                    # 装到 ~/.agents/skills/paper-quality-review/
#   bash install.sh --plugin           # 装到 ~/.openclaw/plugin-skills/paper-quality-review/
#   bash install.sh --dest <path>      # 自定义目标目录
#
# 安装动作：
#   1. 运行 preflight.sh 检查 python 依赖
#   2. 把当前仓库整体 rsync 到目标 skill 目录
#   3. 打印如何在 agent 中触发这个 skill

set -eu

DEFAULT_DEST="$HOME/.agents/skills/paper-quality-review"
DEST=""
MODE="user"

while [ $# -gt 0 ]; do
  case "$1" in
    --plugin)
      DEST="$HOME/.openclaw/plugin-skills/paper-quality-review"
      MODE="plugin"
      shift
      ;;
    --dest)
      DEST="$2"
      MODE="custom"
      shift 2
      ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$DEST" ]; then
  DEST="$DEFAULT_DEST"
fi

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "[install] 源目录：$SRC_DIR"
echo "[install] 目标目录（$MODE）：$DEST"

echo "[install] 步骤 1/3：依赖前置检查"
bash "$SRC_DIR/scripts/preflight.sh"

echo "[install] 步骤 2/3：复制文件"
mkdir -p "$DEST"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    "$SRC_DIR/" "$DEST/"
else
  cp -R "$SRC_DIR/." "$DEST/"
  rm -rf "$DEST/.git" 2>/dev/null || true
fi

echo "[install] 步骤 3/3：完成"
cat <<EOF

✅ 已安装到：$DEST

在 ArkClaw / OpenClaw 中触发此 skill：
  直接在对话中说：
    "帮我用论文质量审查检查这篇论文" 并上传 .docx / .pdf

或在 Claude Code：
  Skill 会通过 SKILL.md frontmatter 的中文触发词自动匹配。

如需卸载：
  rm -rf "$DEST"
EOF
