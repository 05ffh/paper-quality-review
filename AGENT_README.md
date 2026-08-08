# Agent 学习指南

**读完本文件列出的内容后，立即停止探索仓库，直接进入执行流程。** 不要遍历整个目录树，不要读取未在本文列出的文件。

---

## 能力速览

完成学习后你应当具备以下能力：

| 能力 | 说明 |
|---|---|
| 论文解析 | Word / 文本 PDF → `paper_text.json`（执行 `parse_paper.py`） |
| 论文画像 | 识别论文类型、研究方法、数据结构（按 `paper_profile_schema.md`） |
| 条件触发 | 按规则注册表精确触发适用规则，未使用的方法不触发（68条规则） |
| 五大诊断 | 选题、文献综述、数据变量、方法模型、结构规范 |
| 红黄绿灰分级 | 红色必改（强证据+可定位）、黄色建议补充、绿色优化提升、灰色需人工确认 |
| 7 项强制交叉核对 | 中英文摘要一致性、结论与表格一致性、引用双向核对等 |
| 7 条红色硬伤 | 数据口径矛盾、结论超出证据、中英摘要不一致等，命中必须判红 |
| 证据门禁 | 无原文证据不输出；弱证据转灰色；location 必须三要素（章节名+位置+原文引用） |
| KB-A 规范查询 | GB/T 7714 引用规范（9条）+ 伍德里奇计量教材（9条），共18条规范依据 |
| KB-B 范例参照 | 20篇顶刊论文 2191 片段，仅作改进方向参照，不作错误判定唯一依据 |
| rule_id 门禁 | 每个 issue 的 rule_id 必须来自注册表，拒绝幻觉 ID |
| 报告渲染 | `render_report_html.py`（HTML 主交付）+ `render_report.py`（DOCX 存档） |
| Schema 校验 | 写出 `diagnostic_result.json` 后立即运行 `self_check.py --validate` |

---

## 第〇步：环境前置检查（首次必做）

```bash
bash scripts/preflight.sh
```

---

## 第一步：执行流程总览

```
解析论文 → 生成画像 → 条件触发 → 五大诊断 → 证据门禁 → Schema校验 → 渲染报告
    ↓           ↓           ↓           ↓           ↓           ↓           ↓
parse_paper  paper_     rule_       semantic_   evidence_  self_check  render_
  .py        profile    registry    check       req        --validate  report
             _schema    .yaml       _protocol   .md                    _html/.py
             .md                    .md
```

---

## 第二步：必读文件（按执行顺序）

### 1. 画像阶段
| 文件 | 用途 | 阅读后执行 |
|---|---|---|
| `references/paper_profile_schema.md` | 论文画像结构定义 | 生成 `paper_profile` |
| `references/diagnostic_domains.md` | 五大诊断域定义 | 了解诊断范围 |

### 2. 规则触发阶段
| 文件 | 用途 | 阅读后执行 |
|---|---|---|
| `rules/rule_registry.yaml` | 规则注册表（68条，含触发条件与不适用逻辑） | 生成 `trigger_plan` |
| `rules/non_model_rules.yaml` | 非模型规则（35条） | 条件触发执行 |
| `rules/model_rules.yaml` | 模型规则（33条，含ML 5条） | 条件触发执行 |

### 3. 语义判断阶段
| 文件 | 用途 | 阅读后执行 |
|---|---|---|
| `agent_instructions/semantic_check_protocol.md` | 语义判断协议 + 7项强制交叉核对 | 逐域诊断，逐项交叉核对 |
| `agent_instructions/evidence_requirement.md` | 证据要求 + 9bis红色硬伤清单 + §9quater三层判定 | 证据门禁，判级 |
| `agent_instructions/issue_writing_protocol.md` | 问题写作规范 + location三要素格式 + KB引用红线 | 撰写 issue |

### 4. 输出阶段
| 文件 | 用途 | 阅读后执行 |
|---|---|---|
| `references/issue_schema.md` | Issue 数据结构 + 数量控制 + 风险映射 | 写出 `diagnostic_result.json` |
| `references/report_structure.md` | 报告11章节结构 + 禁止内容 | 渲染前对照 |

### 5. 知识库（按需查询）
| 文件 | 用途 | 何时读 |
|---|---|---|
| `knowledge_base/norms/citation/gb_t_7714_2015.yaml` | GB/T 7714 引用规范 | 检出引用/参考文献问题时查询 |
| `knowledge_base/norms/methods/wooldridge_econometrics.yaml` | 伍德里奇计量教材规范 | 检出方法/数据问题时查询 |

### 6. 可选增强
| 文件 | 用途 | 何时读 |
|---|---|---|
| `agent_instructions/vision_protocol.md` | 视觉辅助证据协议 | 仅当启用视觉模块时 |

---

## 第三步：脚本速查（按需调用，无需阅读源码）

| 脚本 | 调用时机 |
|---|---|
| `bash scripts/preflight.sh` | 首次运行，检查依赖 |
| `python3 scripts/parse_paper.py <文件> --out <路径>` | 第一步：解析论文 |
| `python3 scripts/kb_query.py --prefer A --issue-type <类型> --query "<描述>"` | 第五步半：查询规范依据 |
| `python3 scripts/self_check.py --validate <diagnostic_result.json>` | 第六步半：Schema 门禁校验 |
| `python3 scripts/render_report_html.py <json> --out <html> --source <原名>` | 第七步：渲染 HTML 主交付 |
| `python3 scripts/render_report.py <json> --out <docx> --source <原名>` | 第七步：渲染 DOCX 存档 |

---

## 禁止阅读的文件

以下文件属于**开发者/评委**层面，agent **不得读取**：

```
CHANGELOG.md           ← 版本历史（开发者内参）
AGENT_README.md        ← 本文件（已读完，无需重读）
benchmarks/            ← 质量基准体系（开发者工具）
tests/                 ← 测试用例（开发者工具）
plans/                 ← 内部规划文档
docs/CHECK_CATALOG.md  ← 规则人类可读索引（评委用，agent 直接读注册表即可）
examples/examples_design.md ← 示例设计说明
templates/report_template_design.md ← 模板设计说明
scripts/vision/        ← 视觉辅助源码（无需读，直接调用脚本）
scripts/kb_ingest.py   ← KB 入库脚本（开发者工具）
scripts/kb_admin.py    ← KB 管理脚本（开发者工具）
scripts/capability_briefing.py ← 能力摘要（开发者工具）
scripts/build_end_to_end_report.py ← 端到端构建（开发者工具）
scripts/e2e_demo.py    ← 端到端演示（开发者工具）
config/                ← 视觉配置
requirements-*.txt     ← 依赖声明
.env.example           ← 环境变量模板
install.sh             ← 安装脚本
```

---

## 学习完成检查清单

在开始执行前确认：

- [ ] 已读 `paper_profile_schema.md` — 知道画像包含哪些字段
- [ ] 已读 `rule_registry.yaml` — 知道 68 条规则如何条件触发
- [ ] 已读 `semantic_check_protocol.md` — 知道 7 项交叉核对
- [ ] 已读 `evidence_requirement.md` — 知道红色硬伤清单 + 三层判定
- [ ] 已读 `issue_writing_protocol.md` — 知道 location 三要素格式
- [ ] 已读 `issue_schema.md` — 知道 diagnostic_result.json 结构
- [ ] 已读 `report_structure.md` — 知道 11 章节结构
- [ ] 已确认脚本调用方式（parse → kb_query → validate → render）
- [ ] **已停止探索，准备进入执行流程**

全部确认后，即可按 SKILL.md 第 5 节执行流程开始工作。
