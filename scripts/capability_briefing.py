#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""capability_briefing.py · M3 v1.6.2 · 首次运行 / 版本升级后的能力摘要

只显示一次。原则：
- 通过 `.workdir/.capability_briefing_shown` 文件锁存"最后一次展示的版本号"
- 版本号变更 → 重新展示一次
- 否则不显示，直接返回 None

摘要内容遵循用户明确要求（M3 收尾）：
1. 当前已启用能力（基础质检 / KB-A / KB-B）
2. 可选 PDF 视觉辅助识别的三态
3. doctor.py 入口

术语约束：**只用「PDF 视觉辅助识别」**，禁 Core / Cloud Enhanced / Local Vision。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKDIR = _REPO_ROOT / ".workdir"
_BRIEFING_LOCK = _WORKDIR / ".capability_briefing_shown"

# 当前版本（跟 arkclaw.yaml 保持一致，doctor 也用同一个）
CURRENT_VERSION = "v1.6.2"


def _read_last_shown_version() -> str | None:
    if not _BRIEFING_LOCK.exists():
        return None
    try:
        return _BRIEFING_LOCK.read_text(encoding="utf-8").strip() or None
    except Exception:
        return None


def _record_shown(version: str) -> None:
    try:
        _WORKDIR.mkdir(parents=True, exist_ok=True)
        _BRIEFING_LOCK.write_text(version, encoding="utf-8")
    except Exception:
        pass


def _check_vision_state() -> str:
    """轻量三态检查（不触发真实调用），返回 unconfigured / configured_unverified / verified"""
    vision_enabled = os.getenv("VISION_ENABLED", "").strip().lower() == "true"
    api_key_set = bool(os.getenv("ARK_API_KEY", "").strip())
    model_id_set = bool(os.getenv("ARK_VISION_MODEL_ID", "").strip())

    try:
        import openai  # noqa: F401
        sdk_ok = True
    except Exception:
        sdk_ok = False

    if not (vision_enabled and api_key_set and model_id_set and sdk_ok):
        return "unconfigured"

    # 30 天 checkpoint 复用 doctor 逻辑
    checkpoint = _WORKDIR / ".vision_last_verified"
    if checkpoint.exists():
        try:
            import time
            age = time.time() - float(checkpoint.read_text().strip())
            if age <= 30 * 86400:
                return "verified"
        except Exception:
            pass
    return "configured_unverified"


def build_briefing() -> str:
    """构建能力摘要字符串（不判断是否需要展示）"""
    vision_state = _check_vision_state()

    lines = []
    lines.append("━" * 58)
    lines.append(f"  论文质量审查 · {CURRENT_VERSION} · 能力摘要")
    lines.append("━" * 58)
    lines.append("")
    lines.append("  ✅ 已启用能力")
    lines.append("     · 基础论文质检（Word / 文本 PDF）")
    lines.append("     · 五大诊断域 · 红黄绿灰分级 · DOCX 报告")
    lines.append("     · KB-A 规范层（GB/T 7714 + 计量方法 · 共 18 条）")
    lines.append("     · KB-B 顶刊范例参照（20 篇 · 2198 chunks）")
    lines.append("")

    if vision_state == "verified":
        lines.append("  ✅ 可选：PDF 视觉辅助识别（已启用）")
        lines.append("     · PDF 图片型表格 / 公式 / 图表将走火山方舟视觉模型")
        lines.append("     · 未识别或识别失败的区域仍走「需人工复核」")
    elif vision_state == "configured_unverified":
        lines.append("  🟡 可选：PDF 视觉辅助识别（已配置，尚未验证）")
        lines.append("     · 首次实际调用前建议先跑一次 smoke_test：")
        lines.append("       python3 scripts/doctor.py --smoke-test")
    else:
        lines.append("  ⚪ 可选：PDF 视觉辅助识别（未配置）")
        lines.append("     · Word 和文本 PDF 质检不受此影响")
        lines.append("     · 开启后可增强：PDF 图片型表格 / 公式 / 图表的识别")
        lines.append("     · 快速开始见 README.md 的「路径 B」章节")

    lines.append("")
    lines.append("  📖 详情查看:  python3 scripts/doctor.py")
    lines.append("━" * 58)
    return "\n".join(lines)


def maybe_show(force: bool = False) -> str | None:
    """
    幂等入口：
    - 未展示过 → 展示 + 记录
    - 已展示过但版本变了 → 展示 + 更新记录
    - 已展示过且版本一致 → 返回 None
    - force=True → 强制展示（不记录）
    """
    if not force:
        last = _read_last_shown_version()
        if last == CURRENT_VERSION:
            return None
    briefing = build_briefing()
    if not force:
        _record_shown(CURRENT_VERSION)
    return briefing


def main():
    """CLI: `python3 scripts/capability_briefing.py [--force]`"""
    import argparse

    ap = argparse.ArgumentParser(description="论文质量审查 · 能力摘要")
    ap.add_argument("--force", action="store_true", help="强制显示，不消费幂等锁")
    ap.add_argument("--reset", action="store_true", help="重置锁，下次调用会再显示一次")
    args = ap.parse_args()

    if args.reset:
        if _BRIEFING_LOCK.exists():
            _BRIEFING_LOCK.unlink()
            print(f"已重置能力摘要锁: {_BRIEFING_LOCK}")
        else:
            print("锁不存在，无需重置")
        return

    briefing = maybe_show(force=args.force)
    if briefing:
        print(briefing)
    else:
        # 沉默：跟约定一致，只显示一次
        pass


if __name__ == "__main__":
    main()
