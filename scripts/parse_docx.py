#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经管论文智检 Skill - DOCX 解析脚本（纯 I/O，无判断逻辑）。

用法：
    python scripts/parse_docx.py 论文.docx --out paper_text.json

输出带定位信息的结构化文本，供大模型做语义判断。
非 .docx 输入直接报错退出，不生成任何伪结果。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少 python-docx，请先执行：pip install python-docx") from exc


@dataclass
class TextUnit:
    kind: str          # "paragraph" | "table"
    index: int
    text: str
    heading_level: Optional[int] = None
    table_rows: Optional[list[list[str]]] = None  # v1.7: 二维表格结构


def normalize_text(text: str) -> str:
    text = text.replace("　", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def guess_heading_level(text: str) -> Optional[int]:
    t = text.strip()
    if not t:
        return None
    patterns = [
        (1, r"^(第[一二三四五六七八九十]+章|[一二三四五六七八九十]+、|\d+\s+[^\d])"),
        (2, r"^(\d+\.\d+|（[一二三四五六七八九十]+）)"),
        (3, r"^(\d+\.\d+\.\d+|[（(]\d+[）)])"),
    ]
    for level, pat in patterns:
        if re.match(pat, t):
            return level
    keywords = ["摘要", "关键词", "引言", "绪论", "文献综述", "理论基础",
                "研究假设", "数据来源", "变量", "模型", "实证", "结果",
                "结论", "建议", "参考文献", "附录"]
    if len(t) <= 24 and any(k in t for k in keywords):
        return 1
    return None


def read_docx(path: Path) -> tuple[List[TextUnit], List[str]]:
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    units: List[TextUnit] = []
    warnings: List[str] = []
    para_idx = 0
    table_idx = 0
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            text = normalize_text(para.text)

            # P2-1: 检测段落内的图片和公式对象
            for run in child.findall(qn("w:r")):
                if run.find(qn("w:drawing")) is not None:
                    warnings.append(f"段落#{para_idx}含图片对象，图片内容未解析")
                if run.find(qn("m:oMath")) is not None or run.find(qn("m:oMathPara")) is not None:
                    warnings.append(f"段落#{para_idx}含公式对象，公式内容未解析")

            if not text:
                para_idx += 1
                continue
            style_name = (para.style.name or "") if para.style else ""
            if "Heading" in style_name or "标题" in style_name:
                m = re.search(r"(\d+)", style_name)
                level = int(m.group(1)) if m else 1
            else:
                level = guess_heading_level(text)
            units.append(TextUnit("paragraph", para_idx, text, level))
            para_idx += 1
        elif child.tag == qn("w:tbl"):
            table = Table(child, doc)
            rows_2d: list[list[str]] = []
            for row in table.rows:
                cells = [normalize_text(cell.text) for cell in row.cells]
                if any(cells):
                    rows_2d.append(cells)
            if rows_2d:
                flat_text = "\n".join(" | ".join(r) for r in rows_2d)
                units.append(TextUnit("table", table_idx, flat_text, None, table_rows=rows_2d))
            else:
                warnings.append(f"表格#{table_idx} 无可读取文本，可能为图片或复杂嵌入对象，需人工确认")
            table_idx += 1
    return units, warnings


def parse(path: Path) -> dict:
    units, warnings = read_docx(path)
    return {
        "file_name": path.name,
        "parse_warnings": warnings,
        "unit_count": len(units),
        "units": [asdict(u) for u in units],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="解析 DOCX 论文为结构化 JSON")
    parser.add_argument("input", help="输入论文 DOCX 文件")
    parser.add_argument("--out", "-o", help="输出 JSON 路径（默认打印到 stdout）")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"错误：输入文件不存在：{input_path}", file=sys.stderr)
        return 2
    if input_path.suffix.lower() != ".docx":
        print("错误：本 Skill 只支持 .docx 输入。请先转换为 Word 格式后再检测。", file=sys.stderr)
        return 2

    result = parse(input_path)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"已生成：{out_path}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
