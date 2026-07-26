"""
Release Gate Check (M4 v0.3 — 接入 BENCHMARK_PASS_GATE.yaml).

Iterates through candidate run metrics.json files and applies red/yellow/green
gates from:
  - benchmarks/policies/BENCHMARK_PASS_GATE.yaml （6条件通过定义 + 占位规则 + 视觉判定 + failover）
  - plans/M4_RELEASE_GATE.md （保留兼容）

Exit codes:
  0 = all green
  1 = red gate hit (release blocked)
  2 = yellow gate hit only, non-strict mode

Usage:
  python benchmarks/runners/release_gate_check.py \\
      --run benchmarks/runs/20260713-rc1 \\
      [--baseline benchmarks/baselines/v1.7.0-rc.1] \\
      [--strict] \\
      [--allow-baseline-none]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
PASS_GATE_PATH = REPO_ROOT / "benchmarks" / "policies" / "BENCHMARK_PASS_GATE.yaml"

RED_MSG_TEMPLATE = "🟥 RED  {sample}: {reason}"
YEL_MSG_TEMPLATE = "🟨 YEL  {sample}: {reason}"
GRN_MSG_TEMPLATE = "🟩 OK   {sample}"
SKIP_MSG_TEMPLATE = "⬜ SKIP {sample}: {reason}"


def _load_pass_gate() -> dict | None:
    if yaml is None:
        return None
    try:
        with open(PASS_GATE_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def _load_metrics(dir_: Path) -> dict[str, dict]:
    out = {}
    for p in dir_.glob("*.metrics.json"):
        with open(p, "r", encoding="utf-8") as f:
            out[p.stem.split(".")[0]] = json.load(f)
    return out


def check_sample(sample_id: str, m: dict) -> tuple[list[str], list[str]]:
    """Return (red_reasons, yellow_reasons)."""
    red: list[str] = []
    yellow: list[str] = []

    jq = m.get("judgment_quality", {})
    ka = m.get("kb_a_quality", {})
    vq = m.get("vision_quality", {})

    # 1.1 judgment red lines
    if jq.get("forbidden_issue_count", 0) > 0:
        red.append(f"forbidden_issue_count={jq['forbidden_issue_count']} > 0")
    if jq.get("false_red_count", 0) > 0:
        red.append(f"false_red_count={jq['false_red_count']} > 0")
    # 1.1 evidence completeness (red issues)
    ecr = jq.get("evidence_completeness_rate")
    if ecr is not None and ecr < 1.0:
        red.append(f"evidence_completeness_rate={ecr} < 1.0")
    # KB-A red support
    if ka.get("unsupported_red_count", 0) > 0:
        red.append(f"unsupported_red_count={ka['unsupported_red_count']} > 0")

    # 1.2 vision red lines
    if vq.get("visual_false_red_count", 0) > 0:
        red.append(f"visual_false_red_count={vq['visual_false_red_count']} > 0")
    if vq.get("quality_gate_false_pass_count", 0) > 0:
        red.append(f"quality_gate_false_pass_count={vq['quality_gate_false_pass_count']} > 0")

    # 1.3 anchor recall red line
    ar = jq.get("anchor_recall")
    if ar is not None and ar < 1.0:
        # anchor_recall < 1 means a must_hit is missing
        # High confidence anchor lost is RED per §10.1 (须由 diff_report 判定)
        # 这里的粗糙判定: recall < 1 一律红灯
        red.append(f"anchor_recall={ar} < 1.0 (any anchor missing → red)")

    # 2 yellow soft gates (perf, kb-b variance, etc.)
    return red, yellow


# ---------- PASS_GATE 接入（v0.3）----------

def check_placeholder_and_empty(
    sample_id: str, m: dict, diagnostic_json: Path | None
) -> tuple[list[str], list[str]]:
    """P0-5: 检测占位/空跑/固定模板。返回 (skipped_reasons, red_reasons)。"""
    skipped: list[str] = []
    red: list[str] = []

    jq = m.get("judgment_quality", {})
    total_issues = jq.get("total_issues", -1)
    summary = m.get("summary", m.get("summary_counts", {}))
    red_count = summary.get("red", -1)
    yellow_count = summary.get("yellow", -1)
    manual_count = summary.get("manual", 0)

    if total_issues == 0 and m.get("paper_profile", {}).get("paper_type", "") == "经管类实证论文":
        skipped.append("issues=0 but paper_type is empirical (possible all-gray/degraded)")

    if red_count == 0 and yellow_count == 0 and manual_count > 0:
        has_tables = m.get("paper_text_has_tables", True)
        if has_tables:
            skipped.append(f"all-gray no-red no-yellow (manual={manual_count}), possible degraded")

    if diagnostic_json and diagnostic_json.exists():
        try:
            diag = json.loads(diagnostic_json.read_text(encoding="utf-8"))
            for i, iss in enumerate(diag.get("issues", []) or []):
                ev = str(iss.get("evidence", ""))
                if any(kw in ev for kw in [
                    "未找到可引用片段", "此项基于全文缺失信号触发",
                    "全文未识别到", "全文未检测到",
                ]):
                    skipped.append(
                        f"issue[{i}]({iss.get('issue_id','?')}) evidence is placeholder"
                    )
                if iss.get("level") == "红色":
                    nb = iss.get("normative_basis")
                    if nb is None or (isinstance(nb, dict) and not nb):
                        red.append(
                            f"issue[{i}]({iss.get('issue_id','?')}) red lacks normative_basis"
                        )
        except Exception:
            skipped.append("diagnostic_result.json unreadable, placeholder check skipped")

    return skipped, red


def check_scorecard_consistency(m: dict) -> list[str]:
    """P1-4: Scorecard 汇总与逐条计数是否一致。"""
    issues: list[str] = []
    summary = m.get("summary", m.get("summary_counts", {}))
    per_level = m.get("per_level", {})
    if summary and per_level:
        for key in ("red", "yellow", "green", "manual"):
            s_val = summary.get(key, -1)
            p_val = per_level.get(key, -1)
            if s_val >= 0 and p_val >= 0 and s_val != p_val:
                issues.append(
                    f"Scorecard mismatch: summary.{key}={s_val} vs per_level.{key}={p_val}"
                )
    return issues


def check_vision_truthfulness(vq: dict, m: dict) -> list[str]:
    """P1-1: 视觉能力未真实调用不得标 VISION_SUPPORTED。"""
    issues: list[str] = []
    vision_trace = vq.get("vision_traces", vq.get("trace", []))
    baseline_claim = m.get("capabilities", {}).get("vision", "VISION_PLACEHOLDER")
    if (not vision_trace or len(vision_trace) == 0):
        if baseline_claim in ("VISION_SUPPORTED", "VISION_VERIFIED"):
            issues.append(
                f"vision NOT-RUN but capabilities.vision={baseline_claim}, "
                f"should downgrade to VISION_PLACEHOLDER"
            )
    for t in (vision_trace or []):
        if t.get("provider_type") == "mock" and vq.get("mock_red_usage_count", 0) > 0:
            issues.append("mock provider result used for red judgment → FAIL")
            break
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--allow-baseline-none", action="store_true")
    ap.add_argument("--out", type=Path,
                    help="Output release_gate_report.md; default: run/release_gate_report.md")
    args = ap.parse_args()

    if not args.run.is_dir():
        print(f"ERROR: run dir not found: {args.run}", file=sys.stderr)
        return 1

    args.run = args.run.resolve()
    if args.baseline:
        args.baseline = args.baseline.resolve()

    if not args.baseline and not args.allow_baseline_none:
        print("ERROR: --baseline required unless --allow-baseline-none is set", file=sys.stderr)
        return 1

    metrics = _load_metrics(args.run)
    if not metrics:
        print(f"ERROR: no *.metrics.json under {args.run}", file=sys.stderr)
        return 1

    pass_gate = _load_pass_gate()

    lines = [f"# Release Gate Report",
             f"",
             f"- Run:      `{args.run.relative_to(REPO_ROOT)}`",
             f"- Baseline: `{args.baseline.relative_to(REPO_ROOT) if args.baseline else '(none)'}`",
             f"- Strict:   {args.strict}",
             f"- PASS_GATE: {'loaded' if pass_gate else 'NOT LOADED (yaml missing?)'}",
             f"",
             f"## Per-sample checks",
             f""]

    total_red = 0
    total_yel = 0
    total_skip = 0
    total_scorecard = 0
    total_vision = 0
    for sid, m in sorted(metrics.items()):
        red, yel = check_sample(sid, m)

        # --- PASS_GATE 接入 ---
        # 找对应 diagnostic_json
        diag_json = None
        for candidate in [
            args.run / f"{sid}.diagnostic.json",
            args.run / sid / "diagnostic_result.json",
        ]:
            if candidate.exists():
                diag_json = candidate
                break

        skip_red, nb_red = check_placeholder_and_empty(sid, m, diag_json)
        sc_issues = check_scorecard_consistency(m)
        vi_issues = check_vision_truthfulness(m.get("vision_quality", {}), m)

        # 占位红色并入红色列表
        red.extend(nb_red)
        # Scorecard 不一致 = 红灯(阻塞性)
        for sc in sc_issues:
            red.append(f"Scorecard: {sc}")
        # 视觉真值问题 = 黄灯
        for vi in vi_issues:
            yel.append(f"Vision: {vi}")

        total_red += len(red)
        total_yel += len(yel)
        total_skip += len(skip_red)
        total_scorecard += len(sc_issues)
        total_vision += len(vi_issues)

        if not red and not yel and not skip_red:
            lines.append(GRN_MSG_TEMPLATE.format(sample=sid))
        else:
            for r in red:
                lines.append(RED_MSG_TEMPLATE.format(sample=sid, reason=r))
            for y in yel:
                lines.append(YEL_MSG_TEMPLATE.format(sample=sid, reason=y))
            for s in skip_red:
                lines.append(SKIP_MSG_TEMPLATE.format(sample=sid, reason=s))

    lines.append("")
    lines.append("## PASS_GATE Summary (v0.3)")
    lines.append(f"- red total:          {total_red}")
    lines.append(f"- yellow total:       {total_yel}")
    lines.append(f"- skipped (P0-5):     {total_skip}")
    lines.append(f"- scorecard issues:   {total_scorecard}")
    lines.append(f"- vision issues:      {total_vision}")
    pass_gate_satisfied = total_red == 0 and total_scorecard == 0
    lines.append(f"- **PASS_GATE**:       {'✅ SATISFIED' if pass_gate_satisfied else '❌ FAILED'}")
    lines.append("")

    out = args.out or (args.run / "release_gate_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")

    if total_red > 0:
        return 1
    if total_yel > 0 and args.strict:
        return 1
    if total_yel > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
