# issue_schema.md

# 论文质量审查：结构化诊断结果 Schema

> **权威来源说明：** 本节字段名以 `scripts/render_report.py` 的实际读取字段为准。
> 凡本节与 render_report.py 不一致处，以 render_report.py 为准。

## 1. 顶层结构

diagnostic_result.json 为**平铺结构**（无顶层 `diagnostic_result` 包装），应包含：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `paper_profile` | object | 是 | 论文画像（非 paper_profile_summary） |
| `overall_risk_level` | string | 是 | "低风险" / "中风险" / "高风险" / "需人工确认" |
| `summary_counts` | object | 是 | 问题计数。见 §2 |
| `pass_items` | list[object] | 是 | 通过项列表。每项含 `id`, `domain`, `text`, `evidence` |
| `issues` | list[object] | 是 | 问题列表（含红/黄/绿/灰各级）。每项字段见 §3 |
| `not_applicable_items` | list[object] | 是 | 不适用规则组。每项含 `id`, `rule_group`, `reason` |
| `manual_confirmation_items` | list[object] | 是 | 需人工确认项。每项含 `id`, `item`, `location`, `reason`, `how_to_check` |
| `priority_actions` | list[object] | 是 | 优先修改行动。每项含 `priority`, `action`, `issue_ref`, `expected` |

## 2. summary_counts 计数结构

```json
"summary_counts": {
  "pass": 6,
  "red": 2,
  "yellow": 5,
  "green": 3,
  "manual": 2,
  "na": 4
}
```

| 键 | 含义 | 对应 render_report.py 行 |
|---|---|---|
| `pass` | 通过项数量 | 225 |
| `red` | 红色必改问题数量（非 red_issues） | 226 |
| `yellow` | 黄色建议补充数量（非 yellow_issues） | 227 |
| `green` | 绿色优化提升数量（非 green_suggestions） | 228 |
| `manual` | 灰色需人工确认数量 | 229 |
| `na` | 不适用项数量 | 230 |

### 2bis. pass_items 条目结构

```json
{ "id": "PASS-01", "domain": "结构表达与学术规范质检", "text": "论文已呈现...", "evidence": "段落#1" }
```

### 2ter. manual_confirmation_items 条目结构

```json
{ "id": "MC-01", "item": "回归表可能为图片", "location": "表格#2", "reason": "无法稳定识别系数", "how_to_check": "请人工核对回归表内容" }
```

### 2quater. priority_actions 条目结构

```json
{ "priority": 1, "action": "补充变量定义表...", "issue_ref": "DV-VAR-001", "expected": "提升变量口径可复核性" }
```

—— priority_actions **必须是对象列表，不得为字符串列表**。render_report.py 按 `pa.get("priority")` 等字典方式读取，字符串列表将导致 AttributeError。

## 3. issue 字段

每个 issue 必须包含：

- issue_id
- rule_id
- domain
- status
- level
- issue_type
- location
- evidence
- evidence_strength
- explanation
- suggestion
- confidence
- need_manual_confirmation

### 3bis. evidence_items（红色问题结构化证据）

红色问题建议提供 `evidence_items` 数组，列出至少两条相互关联、可定位的原生文本证据。每条包含：

- `location`：定位信息，如 "段落#73" 或 "表格#3"
- `quote`：原文逐字引用
- `source_type`：证据来源类型，如 "DOCX原生文本" / "PDF原生文本" / "视觉解析"

`evidence` 字段仍保留为自由文本概述，`evidence_items` 提供逐字可回溯的结构化证据链。

### 3ter. contradiction_review（数值冲突反证）

涉及数值、显著性、方向或口径冲突的红色候选，应填写 `contradiction_review` 结构化反证：

| 字段 | 类型 | 说明 |
|---|---|---|
| `kind` | string | 冲突类型：数值 / 显著性 / 方向 / 口径 / 样本量 |
| `occurrence_count` | int | 该冲突在论文中出现次数 |
| `likely_typo` | bool | 是否为孤立可唯一解释的笔误 |
| `changes_substantive_conclusion` | bool | 修正后是否改变研究结论 |
| `alternative_explanation_checked` | bool | 是否已完成替代解释检查 |
| `evidence_readable` | bool | 证据是否可读（不可读→灰色） |
| `adjacent_level_consistent` | bool | 邻近文字中的显著性水平是否一致 |
| `table_marker_consistent` | bool | 表格星号标注是否一致 |
| `statistic_or_pvalue_consistent` | bool | t/z 统计量或 p 值是否支持 |
| `context_uniquely_supports_correction` | bool | 上下文是否唯一支持修正方向 |
| `table_claims_opposite` | bool | 表格是否支持相反的结论 |
| `final_severity_reason` | string | 最终判级理由简述 |

按 evidence_requirement.md §9quater 三层判定：
- **红色**：`likely_typo=false` 且 `changes_substantive_conclusion=true`
- **黄色**：`occurrence_count > 1` 或无法唯一解释
- **绿色**：`likely_typo=true` 且 `changes_substantive_conclusion=false`

## 4. 状态允许值

- 通过
- 发现问题
- 建议补充
- 不适用
- 需人工确认

## 5. 等级允许值

- 红色：必改问题
- 黄色：建议补充
- 绿色：优化提升
- 灰色：需人工确认

## 6. 证据强度

- 强
- 中
- 弱

红色问题必须有强证据。弱证据不得列为红色，应优先转为灰色需人工确认。

## 7. 置信度

- 高
- 中
- 低

低置信度判断不得直接列为红色。

## 8. issue_id 命名

推荐前缀：

- TQ：选题与研究问题
- LT：文献综述与理论链条
- DV：数据变量
- MM：方法模型
- SN：结构规范
- PASS：通过项
- NA：不适用项
- MC：需人工确认项

## 9. 数量控制

红色问题建议 3 到 8 项，黄色问题建议 5 到 12 项，绿色建议建议 3 到 8 项，灰色需人工确认建议 0 到 6 项，语言表达问题最多 20 条。

规范论文应减少问题数量并增加通过项，不得为了显得有用而强行挑错。红色问题数量不设人为下限：规范论文可以为 0 项红色，不得为凑够 3 项而把非硬伤升级为红色；反之，硬伤（见 evidence_requirement.md 第 9bis 节）无论多少都必须如实列为红色，不得为控制数量而漏报或降级。

## 9bis. 通过项与不适用项粒度（统一详略）

为消除“同一论文在不同智能体上通过项/不适用项详略差异过大”的问题，规定最小粒度：

**通过项 pass_items：**

- 每个诊断域（选题与研究问题、文献综述与理论链条、数据变量与口径、方法模型与实证结果、结构表达与学术规范）在该域确实达标时，**至少输出 1 项通过项**；实证类论文通过项总数应不少于 5 项。
- 每个通过项必须带 `evidence`（引用具体段落/表格定位），不得只写“结构完整”这类无定位的空泛表述。
- 通过项按诊断域归类，`id` 使用 PASS-01、PASS-02… 连续编号。

**不适用项 not_applicable_items：**

- 凡在 trigger_plan 中判定为 not_applicable 的模型规则组，**必须逐条列为独立的不适用项**，不得合并成一句“其余未使用方法均不适用”。
- 常见需逐条列出的规则组：DID、IV/2SLS、Logit/Probit、调节效应、问卷信度效度、案例分析、OLS 专项（面板论文）。
- 每个不适用项 `reason` 必须写明“当前论文未检测到 X，因此不触发 Y 规则，该项不构成论文问题”的句式，`id` 使用 NA-01、NA-02… 连续编号。

## 10. 总体风险等级

总体风险等级使用低风险、中风险、高风险、需人工确认。为保证不同智能体对同一论文得出一致的总体结论，按以下**强制映射规则**确定（取满足条件的最高档）：

- **高风险**：红色问题 ≥ 3 项，或存在任一涉及核心数据可复核性/结论可信度的红色硬伤（如描述性统计矛盾、结论方向与回归表矛盾）。
- **中风险**：红色问题 1 到 2 项，或红色为 0 但黄色问题 ≥ 6 项。
- **低风险**：红色问题 0 项，且黄色问题 ≤ 5 项，结构基本完整。
- **需人工确认**：论文无法解析、疑似片段，或核心表格/公式为图片导致关键判断无法完成时，总体等级标记为需人工确认，并说明原因。

灰色需人工确认项不计入红色数量，也不单独抬高总体风险等级；但若灰色事项涉及核心结论无法核对，应在总体评价中提示该不确定性。

映射优先级：先按红色数量定档，再看黄色数量与硬伤性质向上调整，不得因主观印象偏离上述阈值。
