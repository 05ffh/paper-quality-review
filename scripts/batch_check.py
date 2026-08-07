#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_check.py --- 论文质量审查 批量处理脚本（v1.7）

接受论文路径列表，自动执行解析→验证→汇总流水线。
（判断层仍由 agent 完成——本脚本只做 I/O + 模板生成 + 汇总）

用法：
    python scripts/batch_check.py paper1.docx paper2.docx ... --out ./batch_output
    python scripts/batch_check.py papers/*.docx --out ./batch_output

输出：
    batch_output/<论文名>/
        paper_text.json          解析产物
        diagnostic_template.json 待 agent 填充的诊断模板
        report.docx              最终报告（agent 填充后渲染）
    batch_output/batch_summary.csv  汇总表
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent

def parse_paper(input_path: Path, out_dir: Path) -> Path:
    out_json = out_dir / "paper_text.json"
    script = REPO_ROOT / "scripts" / "parse_paper.py"
    result = subprocess.run(
        [sys.executable, str(script), str(input_path), "--out", str(out_json)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"解析失败({input_path.name}): {result.stderr.strip()}")
    return out_json

def generate_template(parsed_json: Path, out_dir: Path) -> Path:
    data = json.loads(parsed_json.read_text(encoding="utf-8"))
    template = {
        "paper_profile": {
            "paper_type": "",
            "data_type": "",
            "sample_object": "",
            "sample_period": "",
            "detected_methods": [],
            "trigger_plan": {"triggered_rule_groups": [], "not_applicable_rule_groups": [], "manual_confirmation_items": []},
            "evidence_map": {},
        },
        "overall_risk_level": "",
        "summary_counts": {"pass": 0, "red": 0, "yellow": 0, "green": 0, "manual": 0, "na": 0},
        "pass_items": [],
        "issues": [],
        "not_applicable_items": [],
        "manual_confirmation_items": [],
        "priority_actions": [],
        "_parsed": {
            "file_name": data.get("file_name", ""),
            "unit_count": data.get("unit_count", 0),
            "parse_warnings": data.get("parse_warnings", []),
        },
    }
    out = out_dir / "diagnostic_template.json"
    out.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

def validate_json(json_path: Path) -> tuple[bool, str]:
    script = REPO_ROOT / "scripts" / "self_check.py"
    result = subprocess.run(
        [sys.executable, str(script), "--validate", str(json_path)],
        capture_output=True, text=True,
    )
    return result.returncode == 0, result.stdout.strip()

def render_report(json_path: Path, source_path: Path, out_dir: Path) -> Path:
    out_docx = out_dir / f"论文质量审查报告_{source_path.stem}.docx"
    script = REPO_ROOT / "scripts" / "render_report.py"
    result = subprocess.run(
        [sys.executable, str(script), str(json_path),
         "--out", str(out_docx), "--source", str(source_path.name)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"渲染失败({source_path.name}): {result.stderr.strip()}")
    return out_docx

def main() -> int:
    ap = argparse.ArgumentParser(description="批量论文质检 --- 解析+模板+验证+汇总")
    ap.add_argument("papers", nargs="+", help="论文 DOCX/PDF 路径（支持通配符）")
    ap.add_argument("--out", default="./batch_output", help="输出目录 (默认 ./batch_output)")
    ap.add_argument("--skip-validate", action="store_true", help="跳过 JSON 校验")
    args = ap.parse_args()

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows = []

    for i, paper_path in enumerate(args.papers, 1):
        paper = Path(paper_path).resolve()
        if not paper.exists():
            print(f"[{i}/{len(args.papers)}] ⏭️  跳过(不存在): {paper.name}")
            continue
        if paper.suffix.lower() not in (".docx", ".pdf"):
            print(f"[{i}/{len(args.papers)}] ⏭️  跳过(不支持的格式): {paper.name}")
            continue

        out_dir = out_root / paper.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{i}/{len(args.papers)}] 📄 {paper.name}")

        try:
            # Step 1: 解析
            parsed = parse_paper(paper, out_dir)
            print(f"     ✅ 解析: {parsed.name}")

            # Step 2: 生成模板
            tmpl = generate_template(parsed, out_dir)
            print(f"     ✅ 模板: {tmpl.name}（请 agent 填充诊断结果）")

            summary_rows.append({
                "序号": i, "文件名": paper.name,
                "阶段": "已解析+模板", "单元数": json.loads(parsed.read_text(encoding="utf-8")).get("unit_count", 0),
                "警告数": len(json.loads(parsed.read_text(encoding="utf-8")).get("parse_warnings", [])),
                "风险等级": "待判断", "红色": "-", "黄色": "-", "备注": "",
            })

        except Exception as e:
            print(f"     ❌ 失败: {e}")
            summary_rows.append({
                "序号": i, "文件名": paper.name,
                "阶段": f"失败: {e}", "单元数": 0, "警告数": 0,
                "风险等级": "错误", "红色": "-", "黄色": "-", "备注": str(e),
            })

    # 汇总 CSV
    csv_path = out_root / f"batch_summary_{timestamp}.csv"
    if summary_rows:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            w.writeheader()
            w.writerows(summary_rows)
        print(f"\n📊 汇总: {csv_path} ({len(summary_rows)} 篇)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
