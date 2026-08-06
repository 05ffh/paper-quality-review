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


@dataclass(frozen=True)
class TextUnit:
    kind: str          # "paragraph" | "table"
    index: int
    text: str
    heading_level: Optional[int] = None
    table_rows: Optional[list[list[str]]] = None  # v1.7: 二维表格结构
    section_category: Optional[str] = None  # v1.9: 章节名归一化

    def to_dict(self) -> dict:
        return asdict(self)


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


# v1.9: 章节名归一化 — 将中文论文章节标题映射为标准类别
SECTION_CATEGORY_MAP = [
    (["摘要"], "abstract"),
    (["关键词"], "keywords"),
    (["abstract", "keywords"], "abstract_en"),
    (["目录", "目  录"], "toc"),
    (["引言", "绪论", "前言", "研究背景", "问题提出", "问题的提出"], "introduction"),
    (["文献综述", "相关研究", "国内外研究", "文献回顾", "研究回顾", "文献述评"], "literature_review"),
    (["理论基础", "理论分析", "理论框架", "概念界定", "相关概念", "理论机制"], "theoretical_basis"),
    (["研究假设", "假设提出", "研究假说", "理论分析与研究假设"], "hypotheses"),
    (["数据", "样本", "变量", "数据来源", "样本选择", "变量定义", "指标", "指标体系", "数据说明", "样本描述"], "data"),
    (["模型", "方法", "研究设计", "模型设定", "研究方法", "实证策略", "计量模型", "模型构建", "方法介绍"], "method"),
    (["实证", "结果", "回归结果", "实证分析", "基准回归", "结果分析", "实证检验", "实证结果"], "results"),
    (["机制", "中介", "传导", "影响机制", "作用机制", "机制检验", "中介效应"], "mechanism"),
    (["异质性", "异质性分析", "分组回归", "异质性检验", "调节效应"], "heterogeneity"),
    (["稳健性", "稳健性检验", "稳健性测试", "内生性", "内生性检验", "内生性处理", "安慰剂检验"], "robustness"),
    (["结论", "结论与建议", "研究结论", "总结", "总结与展望", "结论与展望", "研究总结", "政策建议", "对策建议", "启示"], "conclusion"),
    (["参考文献", "参考书目"], "references"),
    (["附录"], "appendix"),
    (["致谢", "致  谢"], "acknowledgments"),
]


def classify_section(text: str) -> Optional[str]:
    """将标题文本映射为标准章节类别。仅对短文本（≤35字）且被识别为标题的文本分类。"""
    t = text.strip()
    if len(t) > 35:  # 非标题段落误入时跳过
        return None
    for keywords, category in SECTION_CATEGORY_MAP:
        if any(k in t for k in keywords):
            return category
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
            category = classify_section(text) if level is not None else None
            units.append(TextUnit("paragraph", para_idx, text, level, section_category=category))
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
    categories = sorted({u.section_category for u in units if u.section_category})
    return {
        "file_name": path.name,
        "parse_warnings": warnings,
        "unit_count": len(units),
        "sections_detected": categories,
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
