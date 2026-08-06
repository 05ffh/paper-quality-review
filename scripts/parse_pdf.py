#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经管论文智检 Skill - PDF 解析脚本（纯 I/O，无判断逻辑）。

用法：
    python scripts/parse_pdf.py 论文.pdf --out paper_text.json

产出与 parse_docx.py 完全一致的 paper_text.json schema，供大模型做语义判断。
关键差异：
  * source_format = "pdf"
  * confidence_downgrade = True，提示上层：整体证据强度默认下调一档，
    表格/公式相关规则默认转灰色需人工确认。
  * 扫描件（无可提取文本）会被识别为不可用输入并给出明确警告。

设计初衷：ArkClaw 生态默认走"脚本工具兜底 + LLM 语义判断"而不是让 LLM
直接啃 PDF 字节。本脚本用 pdfplumber 做确定性的文本/表格抽取，把 PDF
解析质量的锅明确放在脚本层，让 LLM 判断层保持稳定。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "缺少 pdfplumber，请先执行：pip install pdfplumber\n"
        "（或运行 scripts/preflight.sh 自动检测并安装依赖）"
    ) from exc


@dataclass(frozen=True)
class TextUnit:
    kind: str          # "paragraph" | "table"
    index: int
    text: str
    heading_level: Optional[int] = None
    page: Optional[int] = None
    section_category: Optional[str] = None  # v1.9: 章节名归一化

    def to_dict(self) -> dict:
        return asdict(self)


HEADING_KEYWORDS = [
    "摘要", "关键词", "引言", "绪论", "文献综述", "理论基础",
    "研究假设", "数据来源", "变量", "模型", "实证", "结果",
    "结论", "建议", "参考文献", "附录", "abstract", "keywords",
    "introduction", "references",
]


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
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
    lowered = t.lower()
    if len(t) <= 24 and any(k in lowered or k in t for k in HEADING_KEYWORDS):
        return 1
    return None


# v1.9: 章节名归一化 — 与 parse_docx.py 保持同步
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


def _split_paragraphs(page_text: str) -> List[str]:
    """PDF 文本按空行/较长的换行块切分为段落。

    PDF 的换行大多是排版硬换行，需要把明显同一段的文字重新合并。
    简单启发：连续两个换行 = 段落分隔；单个换行且前后都是中文 = 合并。
    """
    if not page_text:
        return []
    # 先按双换行切
    chunks = re.split(r"\n\s*\n", page_text)
    paragraphs: List[str] = []
    for chunk in chunks:
        # 单换行合并：中英文之间保留空格，中文之间去掉换行
        lines = [ln.strip() for ln in chunk.split("\n") if ln.strip()]
        if not lines:
            continue
        merged = ""
        for ln in lines:
            if not merged:
                merged = ln
                continue
            last_char = merged[-1]
            first_char = ln[0]
            # 中文之间直接拼
            if re.match(r"[\u4e00-\u9fff]", last_char) and re.match(r"[\u4e00-\u9fff]", first_char):
                merged += ln
            elif last_char in "。！？；.!?;":
                paragraphs.append(merged)
                merged = ln
            else:
                merged += " " + ln
        if merged:
            paragraphs.append(merged)
    return [normalize_text(p) for p in paragraphs if normalize_text(p)]


def _table_to_text(rows: List[List[Optional[str]]]) -> str:
    lines: List[str] = []
    for row in rows:
        cells = [normalize_text(str(c)) if c is not None else "" for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def read_pdf(path: Path) -> Tuple[List[TextUnit], List[str], dict]:
    units: List[TextUnit] = []
    warnings: List[str] = []
    para_idx = 0
    table_idx = 0

    total_pages = 0
    empty_pages = 0
    total_chars = 0
    total_tables = 0

    with pdfplumber.open(str(path)) as pdf:
        total_pages = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                empty_pages += 1

            # 段落
            for para_text in _split_paragraphs(page_text):
                total_chars += len(para_text)
                level = guess_heading_level(para_text)
                category = classify_section(para_text) if level is not None else None
                units.append(
                    TextUnit(
                        kind="paragraph",
                        index=para_idx,
                        text=para_text,
                        heading_level=level,
                        page=page_no,
                        section_category=category,
                    )
                )
                para_idx += 1

            # 表格
            try:
                page_tables = page.extract_tables() or []
            except Exception as exc:
                warnings.append(f"第 {page_no} 页表格抽取失败：{exc}；建议人工确认")
                page_tables = []

            for tbl in page_tables:
                total_tables += 1
                table_text = _table_to_text(tbl)
                if table_text:
                    units.append(
                        TextUnit(
                            kind="table",
                            index=table_idx,
                            text=table_text,
                            heading_level=None,
                            page=page_no,
                        )
                    )
                else:
                    warnings.append(
                        f"表格#{table_idx}（第 {page_no} 页）解析为空，可能为图片型表格或复杂嵌入对象，需人工确认"
                    )
                table_idx += 1

    # 扫描件识别
    if total_pages > 0 and empty_pages / total_pages >= 0.7:
        warnings.append(
            f"⚠️ 文档 {empty_pages}/{total_pages} 页无可提取文本，疑似扫描件/图片型 PDF。"
            "本 Skill 不做 OCR，建议先用 OCR 转文字或直接上传 .docx 版本。"
        )

    # PDF 默认降级说明
    warnings.insert(
        0,
        "ℹ️ PDF 输入：整体证据强度默认下调一档；"
        "表格、公式、图表相关问题一律优先转为灰色需人工确认，"
        "不得因为 PDF 解析噪声而误判红色。",
    )

    stats = {
        "total_pages": total_pages,
        "empty_pages": empty_pages,
        "total_chars": total_chars,
        "total_tables": total_tables,
    }
    return units, warnings, stats


def parse(path: Path) -> dict:
    units, warnings, stats = read_pdf(path)
    categories = sorted({u.section_category for u in units if u.section_category})
    return {
        "file_name": path.name,
        "source_format": "pdf",
        "confidence_downgrade": True,
        "parse_stats": stats,
        "parse_warnings": warnings,
        "unit_count": len(units),
        "sections_detected": categories,
        "units": [asdict(u) for u in units],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="解析 PDF 论文为结构化 JSON")
    parser.add_argument("input", help="输入论文 PDF 文件")
    parser.add_argument("--out", "-o", help="输出 JSON 路径（默认打印到 stdout）")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"错误：输入文件不存在：{input_path}", file=sys.stderr)
        return 2
    if input_path.suffix.lower() != ".pdf":
        print("错误：parse_pdf.py 仅接受 .pdf 输入。.docx 请使用 parse_docx.py。", file=sys.stderr)
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
