"""
Regression tests for M4 Build Gate Addendum.

Ensures that:
- self_check.py exits 0 without benchmark deps
- kb_ingest.py refuses to ingest benchmark/fixture/internal paths
- production .py code does NOT hard-code sample_id or private sample names
- requirements-core.txt does NOT contain M4 test/dev deps
- benchmarks/ policies + failures + public_summary are wired
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------- §2: self_check works ----------

def test_self_check_exits_zero():
    """self_check.py 只依赖 core，必须 exit 0"""
    r = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "self_check.py"), "--json"],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert r.returncode == 0, f"self_check.py failed:\n{r.stdout}\n{r.stderr}"


# ---------- §3: data isolation ----------

def test_kb_ingest_refuses_benchmark_path():
    from scripts.kb_ingest import ingest_batch
    with pytest.raises(ValueError, match="Benchmark/fixture/internal"):
        ingest_batch("benchmarks/fixtures/rules/R001")
    with pytest.raises(ValueError, match="Benchmark/fixture/internal"):
        ingest_batch("internal_test")
    with pytest.raises(ValueError, match="Benchmark/fixture/internal"):
        ingest_batch("fixture_batch")


def test_production_py_no_sample_id_hardcode():
    """
    生产 .py 代码不得硬编码 sample_id 或私有样本名。
    仅扫描 .py（.md 历史文档不受约束）。
    """
    pattern = re.compile(r'(sample_id\s*==\s*"[SDRQV][0-9]{2,3}|_zhc_)')
    scan_dirs = ["scripts", "rules", "agent_instructions", "references"]
    offenders = []
    for d in scan_dirs:
        root = REPO_ROOT / d
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for m in pattern.finditer(text):
                offenders.append(f"{p.relative_to(REPO_ROOT)}: '{m.group(0)}'")
    assert not offenders, "生产代码含 sample_id 硬编码:\n" + "\n".join(offenders)


# ---------- §4: dependency isolation ----------

def test_core_requirements_has_no_test_deps():
    """requirements-core.txt 不得含 pytest/coverage/black/ruff/mypy"""
    core = (REPO_ROOT / "requirements-core.txt").read_text(encoding="utf-8")
    forbidden = ["pytest", "coverage", "black", "ruff", "mypy"]
    for f in forbidden:
        for line in core.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("#") or not stripped:
                continue
            pkg = re.split(r'[<>=!]', stripped, 1)[0]
            assert pkg != f, f"requirements-core.txt 含禁词 {f}\n行: {line}"


def test_benchmark_requirements_exists():
    p = REPO_ROOT / "benchmarks/requirements-benchmark.txt"
    assert p.exists(), "requirements-benchmark.txt 缺失（Addendum §4.1）"
    assert "pytest" in p.read_text(encoding="utf-8")


# ---------- §5-§9: files exist ----------

def test_governance_files_exist():
    required = [
        "plans/M4_BUILD_GATE_ADDENDUM.md",
        "benchmarks/policies/DATA_ISOLATION_POLICY.md",
        "benchmarks/policies/PUBLIC_CLAIMS_POLICY.md",
        "benchmarks/policies/FEEDBACK_TO_FIXTURE_POLICY.md",
        "benchmarks/failures/SCHEMA.md",
        "benchmarks/failures/TEMPLATE.yaml",
        "benchmarks/public_summary/README.md",
        "benchmarks/public_summary/SCORECARD.md",
        "benchmarks/internal/README.md",
        "scripts/self_check.py",
    ]
    missing = [p for p in required if not (REPO_ROOT / p).exists()]
    assert not missing, f"缺失文件: {missing}"
