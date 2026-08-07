#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文质量审查 - 统一解析入口。

根据输入文件扩展名自动派发到 parse_docx.py 或 parse_pdf.py，
保证上层 agent 只需要一条命令，不用关心格式判断细节。

用法：
    python scripts/parse_paper.py 论文.docx --out paper_text.json
    python scripts/parse_paper.py 论文.pdf  --out paper_text.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _print_pdf_warning(input_path: Path) -> None:
    """向 stderr 输出 PDF 解析局限提醒，供 agent 直接转发给用户。

    设计理由：
    - PDF 内部以字符坐标而非内容结构存储，导致 pdfplumber 对
      公式、复杂表格、多栏排版的抽取不稳定；
    - 扫描件 PDF 无文本层，无法抽取（本 Skill 不做真 OCR）；
    - 质检报告的可靠性直接依赖解析质量，因此必须主动提醒。

    输出到 stderr 而非 stdout，避免污染 --out 以外的下游管道。
    """
    banner = (
        "\n"
        "╔═════════════════════════════════════════════════════════════╗\n"
        "║      ⚠️  PDF 解析能力提示（请传递给用户）                       ║\n"
        "╚═════════════════════════════════════════════════════════════╝\n"
        f"当前输入：{input_path.name}\n"
        "\n"
        "本 Skill 对 PDF 使用 pdfplumber 做文本抽取，存在以下已知局限：\n"
        "  • 公式容易被打散为字符碎片\n"
        "  • 复杂表格列错位、跨页断裂\n"
        "  • 多栏排版 / 页眉页脚缠绕导致段落乱序\n"
        "  • 图片内嵌文字不可读\n"
        "  • 扫描件 PDF（无文本层）不可用\n"
        "\n"
        "建议：如论文原稿为 Word，请优先上传 .docx 格式（解析更稳定、质检更准确）。\n"
        "若仅有 PDF，将自动将整体证据强度下调一档，表格/公式相关问题优先列为需人工确认。\n"
        "\n"
    )
    print(banner, file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="论文质量审查：DOCX/PDF 统一解析入口")
    parser.add_argument("input", help="论文文件路径（.docx 或 .pdf）")
    parser.add_argument("--out", "-o", help="输出 JSON 路径")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"错误：输入文件不存在：{input_path}", file=sys.stderr)
        return 2

    suffix = input_path.suffix.lower()
    argv = [str(input_path)]
    if args.out:
        argv += ["--out", args.out]

    if suffix == ".docx":
        from parse_docx import main as docx_main
        return docx_main(argv)
    if suffix == ".pdf":
        # 给 agent 与终端强提醒：PDF 解析存在已知局限，建议优先 Word
        _print_pdf_warning(input_path)
        from parse_pdf import main as pdf_main
        return pdf_main(argv)

    print(
        f"错误：暂不支持的输入格式：{suffix}\n"
        "本 Skill 当前支持 .docx 与 .pdf；扫描件请先做 OCR 或另存为 Word。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
