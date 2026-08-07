#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经管论文智检 Skill - HTML 预览版报告渲染脚本（webchat 友好）。

用法：
    python scripts/render_report_html.py diagnostic_result.json --out 报告.html --source 原论文.docx

产出自包含单文件 HTML（内联 CSS，不依赖外部资源），
用于 ArkClaw webchat / Control UI 渠道的 <file-list type="html" .../> 快速预览。
DOCX 仍然是主交付，HTML 是"扫一眼要点"的辅助预览。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

DISCLAIMER = (
    "本报告由论文结构化质量诊断系统基于用户上传的文档自动生成，仅用于学术论文提交前的写作规范与论证质量自查，"
    "不替代导师、答辩委员或学校正式评审意见。对于无法可靠解析的表格、公式、图片或主观方法选择，报告中已标注为"
    "“需人工确认”。本系统不进行查重，不判断数据真实性，不联网核验参考文献真伪，也不提供论文代写服务。"
)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_rule_group_names() -> dict[str, str]:
    try:
        import yaml
        registry = yaml.safe_load((_REPO_ROOT / "rules/rule_registry.yaml").read_text(encoding="utf-8")) or {}
        return {
            gid: g.get("group_name", gid)
            for gid, g in (registry.get("rule_groups") or {}).items()
            if isinstance(g, dict)
        }
    except Exception:
        return {}


RULE_GROUP_NAMES = _load_rule_group_names()

LEVEL_COLOR = {
    "红色": ("#c0392b", "#fce4e4", "🔴"),
    "黄色": ("#c78500", "#fff5da", "🟡"),
    "绿色": ("#27823b", "#e2f5e6", "🟢"),
    "灰色": ("#5f6a7d", "#eaeef4", "⚪"),
}


def e(s) -> str:
    return html.escape(str(s) if s is not None else "")


def kv_row(k: str, v: str) -> str:
    return f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>"


def render_issue_card(idx: int, f: dict) -> str:
    level = f.get("level", "灰色")
    color, bg, emoji = LEVEL_COLOR.get(level, LEVEL_COLOR["灰色"])

    # 视觉证据块（M3 v0.3.1）
    ve = f.get("vision_evidence") or {}
    vision_html = ""
    if ve:
        thumb = ve.get("thumbnail_ref")
        thumb_html = ""
        if thumb:
            import base64 as _b64, os as _os
            try:
                if _os.path.exists(thumb):
                    with open(thumb, "rb") as _fp:
                        b64 = _b64.b64encode(_fp.read()).decode("ascii")
                    thumb_html = f'<div class="vision-thumb"><img src="data:image/png;base64,{b64}" alt="page thumbnail" style="max-width:100%; border:1px solid #d0d7de; border-radius:6px;"/></div>'
            except Exception:
                pass

        tp = ve.get("table_preview") or {}
        table_html = ""
        if tp.get("cells"):
            # 构造 preview table
            n_rows = tp.get("n_rows") or (max((c.get("row", 0) for c in tp["cells"]), default=0) + 1)
            n_cols = tp.get("n_cols") or (max((c.get("col", 0) for c in tp["cells"]), default=0) + 1)
            grid = [["" for _ in range(n_cols)] for _ in range(n_rows)]
            for c in tp["cells"]:
                r, col = c.get("row", 0), c.get("col", 0)
                if 0 <= r < n_rows and 0 <= col < n_cols:
                    grid[r][col] = c.get("text", "")
            rows_html = ""
            for i_row, row in enumerate(grid):
                tag = "th" if i_row == 0 else "td"
                cells_html = "".join(f"<{tag}>{e(cell)}</{tag}>" for cell in row)
                rows_html += f"<tr>{cells_html}</tr>"
            caption = tp.get("caption", "")
            cap_html = f"<caption style='font-weight:600; text-align:left; padding:4px 0;'>{e(caption)}</caption>" if caption else ""
            table_html = f'<div class="vision-table"><table class="std vision">{cap_html}{rows_html}</table></div>'

        qp = ve.get("quality_profile") or {}
        kbe = ve.get("kb_eligibility") or {}
        meta_html = f"""
        <div class="vision-meta">
          <span class="vmeta">👁 视觉辅助识别</span>
          <span class="vmeta">model: {e(ve.get('model_id', 'ark_cloud'))}</span>
          <span class="vmeta">提取质量: {qp.get('extraction_quality_score', 0):.2f}</span>
          <span class="vmeta">硬门禁: {'✅' if qp.get('hard_gates_passed') else '❌'}</span>
          <span class="vmeta">KB-A 可用作依据: {'✅' if kbe.get('kb_a_evidence_eligible') else '❌'}</span>
        </div>
        """

        notice_html = ""
        if ve.get("review_notice"):
            notice_html = f'<div class="vision-notice">⚠️ {e(ve["review_notice"])}</div>'

        vision_html = f"""
        <div class="vision-block">
          <div class="vision-title">🔍 视觉辅助证据（仅供人工核对参考）</div>
          {meta_html}
          {thumb_html}
          {table_html}
          {notice_html}
        </div>
        """

    return f"""
<div class="card" style="border-left:6px solid {color}; background:{bg};">
  <div class="card-head">{emoji} <strong>{idx}. {e(f.get('issue_type', ''))}</strong> <span class="tag" style="background:{color}">{e(level)}</span></div>
  <table class="mini">
    {kv_row('所属诊断域', f.get('domain', ''))}
    {kv_row('所在位置', f.get('location', ''))}
    {kv_row('原文证据', f.get('evidence', ''))}
    {kv_row('证据强度', f.get('evidence_strength', ''))}
    {kv_row('问题说明', f.get('explanation', ''))}
    {kv_row('修改建议', f.get('suggestion', ''))}
    {kv_row('需人工确认', '是' if f.get('need_manual_confirmation') else '否')}
  </table>
  {vision_html}
</div>
"""


def write_html(result: Dict[str, object], source_name: str, output_path: Path) -> None:
    profile = result.get("paper_profile", {}) or {}
    # 兼容两种字段名：早期契约用 `summary_counts`，diagnostic 内核实际输出 `counts`。
    counts = result.get("summary_counts") or result.get("counts") or {}
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    tp = profile.get("trigger_plan", {}) or {}

    issues = result.get("issues", []) or []
    passes = result.get("pass_items", []) or []
    by_level: Dict[str, list] = {lv: [f for f in issues if f.get("level") == lv] for lv in ["红色", "黄色", "绿色", "灰色"]}
    manual_items = result.get("manual_confirmation_items", []) or []
    na_items = result.get("not_applicable_items", []) or []
    actions = result.get("priority_actions", []) or []

    counts_row = f"""
<div class="chips">
  <span class="chip pass">通过 {counts.get('pass', 0)}</span>
  <span class="chip red">红色 {counts.get('red', 0)}</span>
  <span class="chip yellow">黄色 {counts.get('yellow', 0)}</span>
  <span class="chip green">绿色 {counts.get('green', 0)}</span>
  <span class="chip gray">灰色 {counts.get('manual', 0)}</span>
  <span class="chip na">不适用 {counts.get('na', 0)}</span>
</div>
"""

    def render_group(title: str, items: List[dict], empty_msg: str) -> str:
        if not items:
            return f"<h2>{e(title)}</h2><p class='empty'>{e(empty_msg)}</p>"
        cards = "\n".join(render_issue_card(i + 1, f) for i, f in enumerate(items))
        return f"<h2>{e(title)}</h2>{cards}"

    passes_html = ""
    if passes:
        rows = "".join(
            f"<tr><td>{e(p.get('id', ''))}</td><td>{e(p.get('domain', ''))}</td>"
            f"<td>{e(p.get('text', ''))}</td><td>{e(p.get('evidence', ''))}</td></tr>"
            for p in passes
        )
        passes_html = f"""<table class="std"><thead><tr><th>编号</th><th>诊断域</th><th>通过项</th><th>证据</th></tr></thead><tbody>{rows}</tbody></table>"""
    else:
        passes_html = "<p class='empty'>本次检测未单独列出通过项。</p>"

    na_html = ""
    if na_items:
        rows = "".join(
            f"<tr><td>{e(n.get('id', ''))}</td><td>{e(RULE_GROUP_NAMES.get(n.get('rule_group', ''), n.get('rule_group', '')))}</td>"
            f"<td>{e(n.get('reason', ''))}</td></tr>"
            for n in na_items
        )
        na_html = f"""<table class="std"><thead><tr><th>编号</th><th>规则组</th><th>不适用原因</th></tr></thead><tbody>{rows}</tbody></table>"""

    manual_html = ""
    if manual_items:
        rows = "".join(
            f"<tr><td>{e(m.get('id', ''))}</td><td>{e(m.get('item', ''))}</td>"
            f"<td>{e(m.get('location', ''))}</td><td>{e(m.get('reason', ''))}</td>"
            f"<td>{e(m.get('how_to_check', ''))}</td></tr>"
            for m in manual_items
        )
        manual_html = f"""<h3>需人工确认清单</h3><table class="std"><thead><tr><th>编号</th><th>确认事项</th><th>所在位置</th><th>原因</th><th>如何复核</th></tr></thead><tbody>{rows}</tbody></table>"""

    actions_html = ""
    if actions:
        issue_map = {f.get("issue_id", ""): f for f in issues}
        def _friendly_ref(ref: str) -> str:
            parts = [r.strip() for r in ref.split(",") if r.strip()]
            resolved = []
            for r in parts:
                iss = issue_map.get(r, {})
                resolved.append(iss.get("issue_type", r) if iss else r)
            return "、".join(resolved) if resolved else ref
        rows = "".join(
            f"<tr><td>{e(a.get('priority', ''))}</td><td>{e(a.get('action', ''))}</td>"
            f"<td>{e(_friendly_ref(a.get('issue_ref', '')))}</td>"
            f"<td>{e(a.get('expected', ''))}</td></tr>"
            for a in actions
        )
        actions_html = f"""<table class="std"><thead><tr><th>优先级</th><th>修改行动</th><th>关联问题</th><th>预期效果</th></tr></thead><tbody>{rows}</tbody></table>"""
    else:
        actions_html = "<p class='empty'>本次检测未生成优先修改行动清单。</p>"

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<title>论文结构化质量诊断报告 · {e(source_name)}</title>
<style>
  :root {{ --border:#e2e6ee; --text:#1f2530; --muted:#6b7280; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:24px; font-family:-apple-system,"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif; color:var(--text); background:#f7f8fa; line-height:1.55; }}
  .wrap {{ max-width:960px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:12px; box-shadow:0 1px 6px rgba(0,0,0,0.04); }}
  h1 {{ margin-top:0; font-size:26px; text-align:center; }}
  h1 + .sub {{ text-align:center; color:var(--muted); margin-bottom:20px; }}
  h2 {{ font-size:19px; margin-top:32px; padding-bottom:6px; border-bottom:2px solid #eef1f6; }}
  h3 {{ font-size:15px; margin-top:20px; color:#374151; }}
  table.std {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:13px; }}
  table.std th, table.std td {{ border:1px solid var(--border); padding:8px 10px; text-align:left; vertical-align:top; }}
  table.std thead th {{ background:#f3f5f9; font-weight:600; }}
  table.mini {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }}
  table.mini th {{ width:110px; text-align:left; padding:6px 8px; background:transparent; color:var(--muted); font-weight:500; vertical-align:top; }}
  table.mini td {{ padding:6px 8px; }}
  .card {{ padding:12px 16px 4px; border-radius:8px; margin:10px 0; }}
  .card-head {{ font-size:15px; margin-bottom:4px; }}
  .tag {{ color:#fff; font-size:11px; padding:2px 8px; border-radius:10px; margin-left:8px; }}
  .chips {{ margin:12px 0 4px; display:flex; flex-wrap:wrap; gap:8px; }}
  .chip {{ padding:4px 12px; border-radius:14px; font-size:13px; }}
  .chip.pass {{ background:#e2f5e6; color:#27823b; }}
  .chip.red {{ background:#fce4e4; color:#c0392b; }}
  .chip.yellow {{ background:#fff5da; color:#c78500; }}
  .chip.green {{ background:#e2f5e6; color:#27823b; }}
  .chip.gray {{ background:#eaeef4; color:#5f6a7d; }}
  .chip.na {{ background:#eef1f6; color:#6b7280; }}
  .empty {{ color:var(--muted); font-style:italic; }}
  .risk {{ display:inline-block; padding:6px 14px; border-radius:6px; font-weight:600; font-size:14px; }}
  .risk.高风险 {{ background:#fce4e4; color:#c0392b; }}
  .risk.中风险 {{ background:#fff5da; color:#c78500; }}
  .risk.低风险 {{ background:#e2f5e6; color:#27823b; }}
  .risk.需人工确认 {{ background:#eaeef4; color:#5f6a7d; }}
  .disclaimer {{ margin-top:36px; padding:14px 16px; background:#f3f5f9; border-radius:8px; color:var(--muted); font-size:12.5px; }}
  .vision-block {{ margin-top:14px; padding:12px 14px; background:#f4f8fd; border-radius:6px; border:1px dashed #b6c9e3; }}
  .vision-title {{ font-weight:600; font-size:13.5px; color:#1e4485; margin-bottom:8px; }}
  .vision-meta {{ font-size:12px; color:#3a4a63; margin-bottom:10px; display:flex; flex-wrap:wrap; gap:8px; }}
  .vmeta {{ padding:2px 8px; background:#dae6f5; border-radius:10px; }}
  .vision-thumb {{ margin:8px 0; text-align:center; }}
  .vision-thumb img {{ max-height:400px; }}
  .vision-table {{ margin:8px 0; overflow-x:auto; }}
  table.std.vision {{ font-size:12px; }}
  table.std.vision th, table.std.vision td {{ padding:4px 6px; }}
  .vision-notice {{ margin-top:6px; padding:6px 10px; background:#fff7d9; border-left:3px solid #d4a800; color:#7a5900; font-size:12px; }}
</style>
</head><body><div class="wrap">
<h1>论文结构化质量诊断报告</h1>
<div class="sub">基于多维规则引擎与证据门禁的提交前质量审查</div>

<h2>一、检测基本信息</h2>
<table class="std"><tbody>
  {kv_row('原论文文件名', source_name)}
  {kv_row('检测日期', today)}
  {kv_row('论文类型', profile.get('paper_type', '不确定，需人工确认'))}
  {kv_row('数据类型', profile.get('data_type', '不确定，需人工确认'))}
  {kv_row('已识别方法', '、'.join(profile.get('detected_methods', []) or ['未识别']))}
  {kv_row('样本对象', profile.get('sample_object', '不确定，需人工确认'))}
  {kv_row('样本期间', profile.get('sample_period', '不确定，需人工确认'))}
  <tr><th>总体风险等级</th><td><span class="risk {e(result.get('overall_risk_level', '需人工确认'))}">{e(result.get('overall_risk_level', '需人工确认'))}</span></td></tr>
</tbody></table>

<h2>二、论文画像识别结果</h2>
<table class="std"><tbody>
  {kv_row('触发规则组', '、'.join(tp.get('triggered_rule_groups', []) or ['无']))}
  {kv_row('不适用规则组', '、'.join(tp.get('not_applicable_rule_groups', []) or ['无']))}
  {kv_row('需人工确认事项', '、'.join(tp.get('manual_confirmation_items', []) or ['无']))}
</tbody></table>

<h2>三、总体评价与修改优先级</h2>
{counts_row}

<h2>四、通过项概览</h2>
{passes_html}

{render_group('五、红色必改问题', by_level['红色'], '本次检测未发现明确的红色必改问题。仍建议结合导师意见进一步复核论文核心内容。')}

{render_group('六、黄色建议补充问题', by_level['黄色'], '本次检测未发现明显需要补充的黄色问题。')}

{render_group('七、绿色优化提升建议', by_level['绿色'], '本次检测暂未生成绿色优化提升建议。')}

<h2>八、灰色需人工确认事项</h2>
{''.join(render_issue_card(i + 1, f) for i, f in enumerate(by_level['灰色'])) if by_level['灰色'] else "<p class='empty'>本次检测未发现必须人工确认的解析事项。</p>"}
{manual_html}

<h2>九、优先修改行动清单</h2>
{actions_html}

<h2>十、不适用规则说明</h2>
{na_html if na_items else "<p class='empty'>本次检测未单独列出不适用规则。</p>"}

<div class="disclaimer">{e(DISCLAIMER)}</div>
</div></body></html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="将 diagnostic_result.json 渲染为 HTML 预览报告")
    parser.add_argument("result", help="diagnostic_result.json 路径")
    parser.add_argument("--out", "-o", help="输出 HTML 报告路径")
    parser.add_argument("--source", help="原论文文件名", default="未提供")
    args = parser.parse_args(argv)

    result_path = Path(args.result).expanduser().resolve()
    if not result_path.exists():
        print(f"错误：结果文件不存在：{result_path}", file=sys.stderr)
        return 2
    result = json.loads(result_path.read_text(encoding="utf-8"))

    source_name = Path(args.source).name if args.source != "未提供" else "未提供"
    today = _dt.datetime.now().strftime("%Y%m%d")
    if args.out:
        output_path = Path(args.out).expanduser().resolve()
    else:
        stem = Path(source_name).stem if source_name != "未提供" else "论文"
        output_path = result_path.with_name(f"经管论文智检报告_{stem}_{today}.html")

    write_html(result, source_name, output_path)
    print(f"已生成 HTML 预览报告：{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
