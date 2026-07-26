#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 端到端演示：issue → 附改进参照卡片 → 报告片段

模拟一个真实场景：
学生论文有 3 个 issue（红/黄/绿各一），走一遍参照卡片生成，
输出一段可直接嵌入 Word/HTML 报告的 markdown 片段，
供人工验证 KB-B 接入效果。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_reference_card import build_cards_for_issues, build_norm_basis_md


# 模拟 3 个 issue（对应真实场景的 R-YY-Green 三色）
demo_issues = [
    {
        "issue_id": "R-01",
        "issue_type": "citation",
        "level": "red",
        "location": "参考文献第 12 条",
        "brief": "期刊文献缺少卷号、期号与起止页码",
    },
    {
        "issue_id": "R-02",
        "issue_type": "methods",
        "level": "red",
        "location": "第四章 DID 模型",
        "brief": "使用 DID 但未做平行趋势检验",
        "method_hint": "DID",
    },
    {
        "issue_id": "Y-04",
        "issue_type": "methods",
        "level": "yellow",
        "location": "第五章 稳健性检验",
        "brief": "稳健性检验只做了一种替换核心变量，建议再补充其他检验方法",
        "method_hint": "DID",
    },
    {
        "issue_id": "G-08",
        "issue_type": "figures_tables",
        "level": "green",
        "location": "全文回归表",
        "brief": "回归表注释可以更完整地说明显著性星号、聚类标准误处理",
    },
    {
        "issue_id": "R-05",  # 变量定义类，应跳过 KB-B（但 KB-A 不受约束）
        "issue_type": "variable_definition",
        "level": "red",
        "location": "第三章 变量定义",
        "brief": "核心解释变量缺公式",
    },
]

out = build_cards_for_issues(demo_issues)

# ---- 生成一段完整的报告片段 ----
report_frag = ["# 端到端演示 v2 · KB-A 规范依据 + KB-B 参照卡 双层挂载", ""]
report_frag.append(f"## 统计")
report_frag.append(f"- 总 issue: {out['stats']['total_issues']}")
report_frag.append(f"- 生成 KB-B 参照卡: {out['stats']['cards_generated']}")
report_frag.append(f"- KB-B 因类型跳过: {out['stats']['cards_skipped_by_type']}")
report_frag.append(f"- KB-B 因相似度跳过: {out['stats']['cards_skipped_by_similarity']}")
report_frag.append("")
report_frag.append("---")
report_frag.append("")

for issue in demo_issues:
    iid = issue["issue_id"]
    level_map = {"red": "🔴 红色", "yellow": "🟡 黄色", "green": "🟢 绿色", "gray": "⚪ 灰色"}
    report_frag.append(f"### {iid} · {level_map.get(issue['level'], issue['level'])}")
    report_frag.append(f"- 问题类型：{issue['issue_type']}")
    report_frag.append(f"- 所在位置：{issue['location']}")
    report_frag.append(f"- 问题说明：{issue['brief']}")

    # ---- KB-A 规范依据（适用于所有 issue_type） ----
    norm_md = build_norm_basis_md(issue['brief'], issue_type=issue['issue_type'])
    if norm_md:
        report_frag.append("")
        report_frag.append(norm_md)

    report_frag.append("")
    report_frag.append("- 修改建议：*（此处为 AI 生成的具体修改建议，占位）*")
    report_frag.append("")

    # ---- KB-B 改进参照（仅对白名单内 issue_type） ----
    card = out["cards"].get(iid)
    if card:
        report_frag.append(card)
    else:
        report_frag.append("> *（无 KB-B 参照卡片）*")
    report_frag.append("")
    report_frag.append("---")
    report_frag.append("")

report_md = "\n".join(report_frag)
out_path = ROOT / "knowledge_base/logs/e2e_demo_v2_20260711.md"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(report_md, encoding="utf-8")
print(report_md)
print(f"\n\n✅ 已落盘: {out_path}")
