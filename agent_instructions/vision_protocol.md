# Vision Protocol · M3 v1.6.0 · Phase 4 完整版

> **状态**：v1.6.0 完整版 · 视觉链路端到端已跑通（张弘济初稿 p20 主回归表 30 cells 100% 识别 · 判断内核 diff = 0）
> **前置**：M1 三层证据（`student_evidence` / `normative_basis` / `example_reference`）保持不变
> **核心宣言**：视觉不改判级规则，只解决"看得见看不见"

---

## 1. 本文件范围

本文件规定视觉模块（M3）与论文质量审查 判断内核的**接口协议**。

### 硬约束 · 不改动清单

- `rules/*.yaml` 判定规则（0 改动）
- `agent_instructions/issue_writing_protocol.md`（0 改动）
- `agent_instructions/semantic_check_protocol.md`（0 改动）
- `references/*.md`（0 改动）
- `knowledge_base/` KB-A/KB-B 已录内容（0 改动）
- `scripts/kb_query.py` / `scripts/build_reference_card.py`（0 改动）

### 只新增

- 视觉证据在 `student_evidence` 中的**结构化表达**（§ 4）
- 视觉证据参与 KB-A / KB-B 的**门禁规则**（§ 5，走 `scripts/vision/knowledge_bridge.py`）
- 视觉结果参与判红/黄/灰的**门槛细则**（§ 6，落到 `evidence_requirement.md` § 9ter）

---

## 2. v0.3.1 · 单一运行流程（无模式概念）

v0.3.1 已**删除**三级模式（Core/Local/Cloud）。用户不感知模式，agent 通过 `doctor.py --smoke-test` 判断视觉辅助的三态：

| doctor 状态 | 环境条件 | Agent 行为 |
|---|---|---|
| ⚪ **未配置** | `VISION_ENABLED != true` 或 `ARK_API_KEY` / `ARK_VISION_MODEL_ID` 缺 或 openai SDK 未装 | PDF 表格/公式/图表**降灰**，走 `manual_confirmation_items` |
| 🟡 **已配置未验证** | 三变量齐 + SDK 装了，但 smoke_test 未跑 / `.workdir/.vision_last_verified` 超 30 天 | 首次调用前先跑 `doctor.py --smoke-test` |
| ✅ **已验证可用** | smoke_test 通过 · checkpoint 30 天窗口内 | 走视觉主链路 `scripts/vision_pipeline.py` |

### 环境变量清单（v0.3.1，仅 6 个）

- `VISION_ENABLED`：`true` 才启用视觉
- `ARK_API_KEY`：火山方舟 Key
- `ARK_VISION_MODEL_ID`：模型 ID 或 Endpoint ID（部署者配）
- `ARK_BASE_URL`：默认 `https://ark.cn-beijing.volces.com/api/v3`
- `MAX_VISION_REGIONS_PER_DOCUMENT`：单文档配额（默认 40）
- `VISION_REQUEST_TIMEOUT_SECONDS`：单次超时（默认 30）

---

## 3. PDF 输入礼仪（10 条）

Agent 首次收到 PDF 时必须遵守：

1. **Word 始终是推荐标准输入**——首次收到 PDF，Agent 主动礼貌提示：「PDF 部分场景可能判灰，建议优先上传 docx 版本」
2. **PDF 属于支持格式**——不因格式拒绝处理
3. **先分诊，再生成针对性提示**——走 `scripts/vision/document_triage.py`，识别文本层覆盖率
4. **提示说明能力边界后必须要求用户二选一**——**不得默认继续处理**：
   - **选项 A（推荐）**：重新上传 Word 版本 → 等新 `.docx` 到位后从 parse 重新走一次
   - **选项 B**：继续用当前 PDF → 进入 PDF 降级策略
   - 用户回复模糊（"好"/"ok"/"继续"/"知道了"等无法区分意图的词）：必须追问「请明确回复重新上传 Word 或继续用 PDF」，不得自行预设继续
5. **视觉分档说明**——按 § 2 三态告知实际可用能力
6. **无法可靠识别的视觉内容必须降灰**——不得强行判红（M3.1 硬约束）
7. **报告显示 PDF 覆盖率**——分诊结果 + 视觉配额使用情况 + 未覆盖内容清单
8. **Word + PDF 双份**：Word 用于内容解析，PDF 用于最终版视觉复核
9. **Word 与 PDF 冲突时不得静默选择**——必须提示用户确认
10. **礼貌提醒每任务原则上只出现一次**——多次上传同文件不重复告知

### 纯扫描 PDF 特殊处理

- 走 `scripts/vision/upload_policy.py::scan_recommendation()` 生成礼貌通知
- **不自动上传整页**——需 `full_page_upload_prompt()` 显式请求用户【确认上传】
- 若用户拒绝：全篇降灰，输出「本次为扫描件 PDF，视觉辅助未启用，全文表格/图表相关条目均需人工核对」

---

## 4. 视觉证据的结构化对象

### 4.1 `student_evidence.source_type`

原三层证据 `student_evidence` 的 `source_type` 枚举扩展：

- `"text"`（M1 原有）：来自 DOCX/PDF 文本层 units
- `"vision"`（v1.6+ 新增）：来自视觉识别通过质量门禁的结构化输出
- `"vision_failed"`（v1.6+ 新增）：视觉识别失败/未启用/触配额，视为降灰依据

### 4.2 `source_type="vision"` 完整结构

由 `scripts/vision/knowledge_bridge.py::build_vision_student_evidence()` 打包：

```json
{
  "source_type": "vision",
  "parsed_text": "变量 | 固定效应模型 | 随机效应模型\nLR | -0.0039** | -0.0092***\n...",
  "page_number": 20,
  "bbox": null,
  "artifact_ref": null,
  "provenance": {
    "provider_name": "ark_cloud",
    "model_id": "doubao-seed-2-0-mini-260428",
    "generated_at": "2026-07-12T20:01:04+08:00",
    "raw_response_hash": "ada020619822245e...",
    "runtime_mode": "basic"
  },
  "quality_profile": {
    "extraction_quality_score": 0.80,
    "critical_field_score": 1.00,
    "hard_gates_passed": true,
    "structural_issues": ["bbox 覆盖率 0.00 < 0.5"],
    "recognition_coverage": 1.00
  },
  "kb_eligibility": {
    "kb_a_query_eligible": true,
    "kb_a_evidence_eligible": true,
    "kb_b_eligible": false
  },
  "requires_visual_review": false,
  "review_notice": "视觉解析结果，请核对原图"
}
```

### 4.3 硬红线

- **禁止**在 `parsed_text` 或 evidence 正文硬编码警告语（如「本内容视觉识别，请核对」）
- 所有警告只通过 `review_notice` 字段承载，由报告渲染器统一显示
- **禁止**模型自报 `confidence` / `quality` / 判级词（`_SYSTEM_PROMPT_STRICT` 硬编码防护）

### 4.4 报告渲染

`render_report.py`（DOCX）和 `render_report_html.py`（HTML）**已支持**视觉证据卡：

- 视觉证据卡展示：模型 ID、`extraction_quality_score`、`hard_gates_passed`、`kb_a_evidence_eligible`
- 表格预览：从 `vision_evidence.table_preview.cells[]` 渲染成 HTML/DOCX 表格
- 缩略图：从 `vision_evidence.thumbnail_ref` 引用（HTML 版内嵌 base64，DOCX 版 `doc.add_picture()`）
- `review_notice` 独立显示，**不进** evidence 正文

---

## 5. KB-A / KB-B 门禁

走 `scripts/vision/knowledge_bridge.py::compute_kb_eligibility()`，`build_reference_card.py` **0 改动**。

### 5.1 三个门禁字段

```python
KB_A_EVIDENCE_MIN_SCORE = 0.75   # KB-A 作为 issue 依据的最低质量分
KB_B_MIN_SCORE = 0.85            # KB-B 挂载参照卡的最低质量分

def compute_kb_eligibility(unified):
    profile = unified["quality_profile"]
    extraction = profile["extraction_quality_score"]
    hard_gates = profile["hard_gates_passed"]

    kb_a_query_eligible = True                           # 所有视觉结果都能查 KB-A
    kb_a_evidence_eligible = hard_gates and extraction >= 0.75
    kb_b_eligible = hard_gates and extraction >= 0.85
```

### 5.2 判定表

| 场景 | `hard_gates_passed` | `extraction_score` | KB-A 查询 | KB-A 作依据 | KB-B 挂参照 |
|---|---|---|---|---|---|
| 高质量识别 | ✅ | ≥ 0.85 | ✅ | ✅ | ✅ |
| 中质量识别 | ✅ | 0.75-0.85 | ✅ | ✅ | ❌ |
| 低质量识别 | ✅ | < 0.75 | ✅ | ❌ | ❌ |
| 硬门禁未过 | ❌ | 任意 | ✅ | ❌ | ❌ |
| 视觉失败 | N/A | N/A | ❌ | ❌ | ❌ |

### 5.3 三层证据分离下的视觉证据

视觉证据仅作为 `student_evidence` 的一个来源。**不改变** M1 三层分离原则：

| 三层 | 视觉可否 |
|---|---|
| `student_evidence` | ✅ 可（`source_type="vision"`） |
| `normative_basis`（KB-A） | ❌ 视觉永远不作 normative_basis 内容 |
| `example_reference`（KB-B） | ❌ 视觉永远不作 example_reference 内容 |

---

## 6. 判级门槛（细则见 `evidence_requirement.md` § 9ter）

### 6.1 视觉证据的等级映射

| 学生论文证据 | 视觉证据条件 | 允许判级 |
|---|---|---|
| **两处独立可读**（至少一处 DOCX / PDF 原生文本） | `extraction_score ≥ 0.90` + `critical_field_score = 1.0` + `hard_gates_passed = true` | 红 · 黄 · 绿 · 灰 |
| **一处 DOCX / PDF 文本 + 一处 vision** | vision `extraction_score ≥ 0.75` | 黄 · 绿 · 灰 |
| **两处均为 vision** | 任意 | 灰（**不自动判红**）|
| vision 单独提示 | `hard_gates_passed = false` | 灰 |
| vision 识别失败 | `source_type = "vision_failed"` | 灰 + `manual_confirmation_items` |

### 6.2 M3.1 硬约束

**`pure_vision_evidence_can_be_red = false`**

即使视觉识别质量极高，只要证据全部来自视觉，也**不自动判红**。红色判决必须有至少一处 DOCX 原生文本或 PDF 文本层证据支撑。

原因：视觉识别再准也**存在幻觉可能**，红色是最严重判决，需 pdf 原生文本层作为交叉验证。

### 6.3 引用与规范类判定

规范类 issue（如缺卷号、格式错等）优先走：

1. student_evidence（学生论文原文）
2. normative_basis（KB-A 权威依据）

视觉证据在这里的作用是**辅助确认**（比如「参考文献是图片，需人工核对」），不作为规范判定的主证据。

---

## 7. 隐私授权

### 7.1 两级授权

- **部署者门禁**：`.env` 或 `.env.local` 需显式设置 `VISION_ENABLED=true`；未设 → 视觉全关
- **用户会话首次同意**：每个会话首次触发视觉调用前，agent 需简短告知：「本次质检将对第 X, Y, Z 页调用外部视觉模型（火山方舟 · 数据境内）以辅助识别表格/图表；不识别不改判级，但仅供人工参考」

### 7.2 上传策略

- **默认**：只上传 bbox 裁剪 + 少量上下文（走 `dispatcher.py` + `upload_policy.decide_upload()`）
- **整页上传**：需通过 `full_page_upload_prompt()` 显式请求用户【确认上传】
- **拒绝上传** → 该区域降灰

### 7.3 数据管理

- 正常模式：响应后原始返回（除 hash）不落盘
- Debug 模式（`VISION_DEBUG=true`）：raw response 落盘到 `.workdir/vision_debug/`，24 小时内清理
- 缩略图：落盘到 `.workdir/<session>/artifacts/thumb_pXX.png`，会话生命周期内保留

### 7.4 海外 Provider

**M3.1 不实现**。当前仅接入火山方舟（境内）。

---

## 8. 视觉主链路（生产接入指南）

### 8.1 端到端脚本

```bash
# Step 1 · 视觉识别
python3 scripts/vision_pipeline.py \
  <pdf_path> \
  --pages 13,14,15,20 \
  --workdir .workdir/<session>/ \
  --task TABLE_STRUCTURE

# Step 2 · 构建诊断结果（判断内核由 agent 走 rules/；此脚本仅演示挂载）
python3 scripts/build_end_to_end_report.py \
  --units .workdir/<session>/parsed/paper_text.json \
  --vision .workdir/<session>/vision_result.json \
  --source "论文.pdf" \
  --out .workdir/<session>/diagnostic_result.json

# Step 3 · 渲染
python3 scripts/render_report.py <diag>.json --out 报告.docx
python3 scripts/render_report_html.py <diag>.json --out 报告.html
```

### 8.2 主要函数入口

- `scripts.vision_pipeline.process_pdf(pdf, pages, workdir)` → dict
- `scripts.vision.dispatcher.VisionDispatcher(provider).recognize(req)` → DispatchResult
- `scripts.vision.providers.ark_provider.ArkCloudProvider().recognize(req)` → VisionResponse
- `scripts.vision.normalizer.normalize(resp)` + `scripts.vision.quality_scorer.score(unified)`
- `scripts.vision.knowledge_bridge.compute_kb_eligibility(unified)` + `build_vision_student_evidence(unified)`

### 8.3 张弘济初稿黄金样本

- PDF：`upload/张弘济初稿-1783849863542-17g1ta.pdf`（1.5 MB · 24 页）
- 关键页：p13/p14/p15（图1/图2/图3）· p17（表 1 变量指标）· p20（表 3 主回归）
- p20 主回归表识别成绩：10×3 · 30/30 cells · caption「表 3 主回归结果：LR对NIM的影响」· 15.3 s · 5316 tokens

---

## 9. 快照与回退

**关键 tag**：

| tag | 内容 |
|---|---|
| `v1.5.0-pre-m3` | M1 完成态，M3 build 起点 |
| `v1.6.0-rc.2-legacy-frozen` | v0.2 三级模式 + PaddleOCR 冻结点 |
| `v1.6.0-rc.3` | v0.3.1 Phase A 完成（单 Provider 轻量化）|
| `v1.6.0` | Phase B/C/D 端到端闭环 |

**回退命令**：

```bash
git reset --hard v1.5.0-pre-m3           # 回 M1 完成态
git reset --hard v1.6.0-rc.2-legacy-frozen  # 回 v0.2 三级模式
git reset --hard v1.6.0                  # 回 M3 收官
```

---

## 10. 测试与验证

### 10.1 pytest

```bash
python3 -m pytest tests/vision/ -v
```

**14 项测试**（v1.6.0 全过）：
- 10 项 pipeline smoke（MockProvider → normalizer → scorer → bridge 全链路 + Ark M3.1 收窄验证）
- 4 项提示注入对抗（系统提示锚定 + OCR bypass command / `<script>` in cell / caption asking for grade）

### 10.2 doctor smoke_test

```bash
python3 scripts/doctor.py --smoke-test
```

- 用 fixture `tests/vision/fixtures/smoke_synthetic_table.png` 走一次真实 Ark 调用
- 3×3 合成表 → 9/9 cells 完美（4.9 秒）
- checkpoint 写 `.workdir/.vision_last_verified`

### 10.3 判断内核 diff = 0 验证

```bash
# 分支 A：不带视觉
python3 scripts/build_end_to_end_report.py --units <units>.json --source ...
# 分支 B：带视觉
python3 scripts/build_end_to_end_report.py --units <units>.json --vision <vision>.json --source ...
# diff 应 = 0（去除 vision-only 灰色 issue 后完全一致）
```

---

## 11. 参考文档

- 主计划书：`plans/M3_v0.3.1_修订与BUILD_GATE.md`（v0.3.1 修订 + Build Gate 一体化，21.7 KB）
- 依赖：`requirements-vision.txt`（openai>=1.30, requests）
- Provider 抽象：`scripts/vision/providers/base.py`
- 系统提示：`scripts/vision/providers/ark_provider.py::_SYSTEM_PROMPT_STRICT`
- 判级细则：`agent_instructions/evidence_requirement.md` § 9ter

---

**当前状态**：v1.6.0 端到端闭环完成 · 张弘济初稿 p20 表 3 视觉识别 30 cells 100% 正确 · 判断内核 diff = 0 · pytest 14/14 全过
