# Benchmarks · 论文质量审查 可回归质量体系

**首版**：`v1.7.0-rc.1`（M4 交付）
**数据集版本**：见 `VERSION`
**主计划**：`../plans/M4_Benchmark_CHANGELOG_v0.2.md`
**Release Gate**：`../plans/M4_RELEASE_GATE.md`
**样本治理**：`../plans/M4_SAMPLE_GOVERNANCE.md`

---

## 一句话

**"不仅知道版本变了什么，还能证明：高风险问题没有漏、正确内容没有被误判、证据和规范可复核、视觉数字没有读错、性能与成本可控制、每次发布都有可审计依据。"**

---

## 四层数据

| 层 | 目录 | 首版下限 |
|---|---|---|
| 规则夹具 | `fixtures/rules/` | ≥ 10 |
| KB 查询夹具 | `fixtures/kb_queries/` | ≥ 10 |
| 视觉裁剪夹具 | `fixtures/vision_crops/` | ≥ 15 |
| 完整文档样本 | `documents/` | ≥ 2 |

---

## 目录

```
benchmarks/
├── VERSION                      # dataset 版本号
├── env/lock.txt                 # pip freeze 快照 + hash
├── fixtures/                    # 微型夹具（可入 Git）
├── documents/
│   ├── public_synthetic/        # 合成 / 半合成论文（可入 Git）
│   ├── private_local_manifest/  # 私有真实论文（只入 manifest+hash）
│   └── open_license/            # 开放许可样本
├── expected/                    # 完整文档 expected.yaml
├── schema/                      # 3 份 JSON Schema
├── runs/                        # 候选运行（可覆盖）
├── baselines/                   # 黄金基线（只读）
├── reports/                     # scorecard
├── lib/                         # fingerprint / schema_validator
└── runners/                     # run_single / compare / promote / …
```

---

## 快速开始

```bash
# 1. 生成 env lock (首次设置)
python benchmarks/runners/refresh_env_lock.py

# 2. 校验所有 schema (expected/metrics/manifest)
python benchmarks/lib/schema_validator.py --all

# 3. 单跑一个 fixture
python benchmarks/runners/run_single.py \
    --sample benchmarks/fixtures/rules/R001 \
    --run-id smoke-$(date +%Y%m%d%H%M)

# 4. 一键批跑所有 R/Q/V (不耗 Ark)
python benchmarks/runners/run_all.py \
    --run-id smoke-$(date +%Y%m%d%H%M) \
    --continue-on-error

# 5. 单 fixture 子集
python benchmarks/runners/run_all.py \
    --run-id smoke-R-only \
    --only R

# 6. R 路由真写入 fingerprint（需 diagnostic_result.json）
python benchmarks/runners/run_single.py \
    --sample benchmarks/fixtures/rules/R001 \
    --run-id my-real-run \
    --actual-json benchmarks/fixtures/rules/R001/mock_diagnostic_pass.json

# 7. 运行 Release Gate 汇总
python benchmarks/runners/release_gate_check.py \
    --run benchmarks/runs/smoke-XXXX \
    --allow-baseline-none

# 8. 视觉质量门 lint（离线，不耗 Ark）
python benchmarks/lib/vision_quality_gate_lint.py --all-in benchmarks/runs/

# 9. 升迁 baseline（需人工审批）
python benchmarks/runners/promote_baseline.py \
    --from-run 20260713-phaseD-perf \
    --target-version v1.7.0 \
    --source-tag v1.7.0-rc.1
```

---

## Fixture 三路由

### R · 规则夹具（rules/）
- **目的**：验证内核对特定规则（GB/T 7714 / 伍德里奇）的命中/不命中
- **输入**：`input.yaml` 含论文片段，少量额外元信息
- **预期**：`must_hit` fingerprint（rule_id|issue_type|location_anchor|evidence_key）+ `forbidden_issues`（不得误报项）
- **真写入 fingerprint** (Phase C+): 提供 `mock_diagnostic_*.json` 让 `run_single` 从内核输出抽取

### Q · KB 查询夹具（kb_queries/）
- **目的**：验证 KB-A 检索器命中、距离、拒绝
- **输入**：`input.yaml` 含 query（issue_type + 关键词）
- **预期**：`kb_a_expectations.{must_hit,must_not_hit}` → norm_precision/recall
- **真调**：`run_single` 直接 同进程调 `KBQuery.query_norms`

### V · 视觉裁剪夹具（vision_crops/）
- **目的**：验证 Ark 视觉表格/公式识别质量 + quality_gate
- **输入**：`input.yaml.image_path` → 本地图像
- **预期**：`vision_expectations.table_truths.critical_cells` 逐单元格真值
- **已对齐 S02** (Phase F): V001/V005/V007/V008 用 S02 Ark 真调输出作真值
- **待真图**：V002-V004/V006/V009-V015 骨架，v1.7.1 录入

---

## 反循环圣杯（Phase C 交付）

**问题**：预期与实际都从同一内核输出返算，验证无价值

**方案**：`benchmarks/lib/issue_to_fingerprint.py`
- 从 diagnostic_result.json 中抽稳定 fingerprint
- rule_id → issue_type 前缀映射白名单
- location 归一化（reference_N / section_N_M / table_N / figure_N / equation_N / abstract）
- evidence_key 优先取 `issue.evidence_tag`，兵底 `_RULE_DEFAULT_EVIDENCE_KEY`

**验证**：R001 `mock_diagnostic_pass.json` vs `mock_diagnostic_fail.json` 双场景
- pass: anchor_recall=1.0, forbidden=0 → 🟩
- fail: anchor_recall=0.0, forbidden=1 → 🟥 × 2 阻断


---

## 硬约束（拷贝自 §6 / §10 / Sample Governance）

- **runs/ 与 baselines/ 严格分离**，baseline 只读，晋升需人工审批
- **must_hit + forbidden_issues 双向锚点**
- 回归主键：**issue_fingerprint**（非 R-01）
- 视觉门禁：数值正确性（exact_match ≥ 0.95、sign = 1.0、visual_false_red = 0）
- 私有论文**不入 Git**，只入 manifest + sha256
- Ark 云调用需 `allowed_uses.cloud_vision: true`
- 硬门禁字段（须 = 0）：`forbidden_issue_count`, `false_red_count`, `unsupported_red_count`, `quality_gate_false_pass_count`, `visual_false_red_count`

---

## 状态

- Phase 0（Audit + Freeze）✅
- Phase A（Schema + 骨架）✅
- Phase B（10+10+15 夹具 + run_single）✅
- Phase C（反循环真接入 + S02 PDF baseline）✅
- Phase D（S02 3× 真调 Ark 采 p50/p95 + Scorecard）✅
- Phase E（CHANGELOG + tag v1.7.0-rc.1）✅
- Phase F（V 对齐 S02 + 批跑器 + baseline 升迁 + retrospective）✅
- **当前**：`v1.7.0-rc.1` 候选版观察期，待升 v1.7.0 正式版（需 S01 DOCX 到位 + 7 天无回归）
