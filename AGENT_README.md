# Agent 学习指南

> **先读本文，再精读列出的文件。读完即可开始工作，无需浏览仓库其他内容。**
>
> 本文是 `SKILL.md` 的补充——SKILL.md 定义执行流程，本文定义学习范围。两篇读完，下面的必读文件读完，就可以执行了。

---

## 环境准备

首次使用前，确认 Python 3.9+ 环境已安装以下依赖。**以下为必装项**，缺一不可：

```bash
pip install --break-system-packages -r requirements-core.txt
```

这条命令安装 10 个包，覆盖全部基础能力：

| 包 | 用途 |
|---|---|
| `python-docx` | DOCX 论文解析 |
| `pypdf` + `pdfplumber` | PDF 文本抽取 |
| `lxml` | XML/HTML 处理（python-docx 底层依赖） |
| `pyyaml` | 规则库与 KB-A 规范文件读取 |
| `jinja2` | 报告模板渲染 |
| `markdown` | Markdown 转 HTML |
| `pypdfium2` + `Pillow` | PDF 页面缩略图 |
| `jsonschema` | diagnostic_result.json 结构校验 |

装完后运行 `bash scripts/preflight.sh` 验证，或 `python3 scripts/doctor.py` 查看完整状态。

> **可选增强**：`requirements-kb.txt`（ChromaDB 语义搜索，JSONL 索引已覆盖基本检索，可不装）。视觉辅助见 `agent_instructions/vision_protocol.md`，未装不影响基础诊断。

---

## 能力速览

完成学习后你应当具备以下能力：

| 能力 | 说明 |
|---|---|
| 论文解析 | Word / 文本 PDF → `paper_text.json`（调用 `parse_paper.py`） |
| 论文画像 | 识别论文类型、研究方法、数据结构（按 `paper_profile_schema.md`） |
| 条件触发 | 按规则注册表精确触发适用规则，未使用的方法不触发（68条规则） |
| 五大诊断 | 选题、文献综述、数据变量、方法模型、结构规范 |
| 红黄绿灰分级 | 红色必改（强证据+可定位）、黄色建议补充、绿色优化提升、灰色需人工确认 |
| 7 项强制交叉核对 | 中英文摘要一致性、结论与表格一致性、引用双向核对等 |
| 7 条红色硬伤 | 数据口径矛盾、结论超出证据、中英摘要不一致等，命中必须判红 |
| 证据门禁 | 无原文证据不输出；弱证据转灰色；location 三要素（章节名+位置+原文引用） |
| KB-A 规范查询 | GB/T 7714 引用规范（9条）+ 伍德里奇计量教材（9条），共18条规范依据 |
| KB-B 范例参照 | 20篇顶刊论文 2191 片段，仅作改进方向参照，不作错误判定唯一依据 |
| rule_id 门禁 | 每个 issue 的 rule_id 必须来自注册表，拒绝幻觉 ID |
| 报告渲染 | `render_report_html.py`（HTML 主交付）+ `render_report.py`（DOCX 存档） |
| Schema 校验 | 写出 `diagnostic_result.json` 后运行 `self_check.py --validate` |

---

## 必读文件（按执行顺序）

### 入口
| 文件 | 用途 |
|---|---|
| `SKILL.md` | 完整执行流程、PDF 降级策略、写作风格、三层证据分离规则 |

### 1. 画像阶段
| 文件 | 用途 |
|---|---|
| `references/paper_profile_schema.md` | 论文画像结构定义 |
| `references/diagnostic_domains.md` | 五大诊断域定义 |

### 2. 规则触发阶段
| 文件 | 用途 |
|---|---|
| `rules/rule_registry.yaml` | 规则注册表（68条，含触发条件与不适用逻辑） |
| `rules/non_model_rules.yaml` | 非模型规则（35条） |
| `rules/model_rules.yaml` | 模型规则（33条，含ML 5条） |

### 3. 语义判断阶段
| 文件 | 用途 |
|---|---|
| `agent_instructions/semantic_check_protocol.md` | 语义判断协议 + 7项强制交叉核对 |
| `agent_instructions/evidence_requirement.md` | 证据要求 + 红色硬伤清单 + 三层判定 |
| `agent_instructions/issue_writing_protocol.md` | 问题写作规范 + location 三要素格式 |

### 4. 输出阶段
| 文件 | 用途 |
|---|---|
| `references/issue_schema.md` | Issue 数据结构 + 数量控制 + 风险映射 |
| `references/report_structure.md` | 报告 11 章节结构 + 禁止内容 |

### 5. 知识库（检出问题时按需查询，无需预读）
| 文件 | 何时查 |
|---|---|
| `knowledge_base/norms/citation/gb_t_7714_2015.yaml` | 检出引用/参考文献问题时 |
| `knowledge_base/norms/methods/wooldridge_econometrics.yaml` | 检出方法/数据问题时 |

### 6. 可选
| 文件 | 何时读 |
|---|---|
| `agent_instructions/vision_protocol.md` | 仅当启用视觉模块时 |

---

## 脚本速查（调用即可，无需阅读源码）

| 脚本 | 调用时机 |
|---|---|
| `bash scripts/preflight.sh` | 首次运行，检查依赖 |
| `python3 scripts/parse_paper.py <文件> --out <路径>` | 第一步：解析论文 |
| `python3 scripts/kb_query.py --prefer A --issue-type <类型> --query "<描述>"` | 第五步半：查询规范依据 |
| `python3 scripts/self_check.py --validate <diagnostic_result.json>` | 第六步半：Schema 门禁校验（阻塞性，不通过禁止渲染） |
| `python3 scripts/render_report_html.py <json> --out <html> --source <原名>` | 第七步：渲染 HTML 主交付 |
| `python3 scripts/render_report.py <json> --out <docx> --source <原名>` | 第七步：渲染 DOCX 存档 |

---

## 不需要读的

以下目录和文件属于开发者层面（版本历史、测试、基准、规划文档），与执行论文诊断无关，跳过即可：`CHANGELOG.md`、`benchmarks/`、`tests/`、`docs/CHECK_CATALOG.md`、`examples/examples_design.md`、`scripts/vision/`（源码）、`scripts/kb_ingest.py`、`scripts/kb_admin.py`、`config/`、`requirements-*.txt`、`.env.example`、`install.sh`、`templates/report_template_design.md`。

---

## 学习完成检查清单

- [ ] 已读 `SKILL.md` — 完整执行流程和 PDF 降级策略
- [ ] 已读 `references/paper_profile_schema.md` — 画像字段
- [ ] 已读 `references/diagnostic_domains.md` — 五大诊断域
- [ ] 已读 `rules/rule_registry.yaml` — 68 条规则的条件触发逻辑
- [ ] 已读 `rules/non_model_rules.yaml` + `rules/model_rules.yaml` — 每条规则的具体判定标准
- [ ] 已读 `agent_instructions/semantic_check_protocol.md` — 7 项交叉核对
- [ ] 已读 `agent_instructions/evidence_requirement.md` — 红色硬伤清单 + 三层判定
- [ ] 已读 `agent_instructions/issue_writing_protocol.md` — location 三要素格式
- [ ] 已读 `references/issue_schema.md` — diagnostic_result.json 结构
- [ ] 已读 `references/report_structure.md` — 11 章节结构
- [ ] 已确认脚本调用方式（`parse_paper.py` → `kb_query.py` → `self_check.py --validate` → `render_report_html.py`）
- [ ] 已确认学习完毕，可以开始执行

全部确认后，按 `SKILL.md` 第 5 节执行流程开始工作。

---

## 常见陷阱

### 1. 不要通过工具参数传递 diagnostic_result.json

`diagnostic_result.json` 是一个包含多条 issue、每条多层嵌套的大型 JSON（通常 5000—15000 字符）。**禁止**将其作为工具调用（tool call / function call）的字符串参数传递。

原因：
- 中文字符需要正确转义，嵌套层级深，模型在单次 tool call 参数中容易丢失引号、括号或逗号
- 一旦有一个字符出错，整个 JSON 解析失败
- 这是 LLM 通过 tool parameter 生成大型结构化数据的已知不可靠模式

正确做法：**直接将 JSON 写入文件**（`Write` 到工作目录的 `diagnostic_result.json`），不经过任何工具参数。写完后再调用 `self_check.py --validate` 校验。

如果使用的 agent 框架必须通过工具写入，建议分段操作：先写顶层结构（paper_profile + summary_counts），再逐条追加 issue。

### 2. 必须同时渲染 HTML 和 DOCX

HTML 是**主交付格式**，DOCX 是辅助存档。渲染时必须同时调用两个脚本，缺一不可：

```bash
python3 scripts/render_report_html.py <json> --out <路径>.html --source <原名>
python3 scripts/render_report.py <json> --out <路径>.docx --source <原名>
```

如果只封装了 DOCX 渲染工具而漏掉了 HTML，需在工具层补充 `render_report_html` 工具，参数与 DOCX 渲染一致。

### 3. location 字段必须是自然语言，禁止结构化对象

`location` 是**字符串字段**，内容是给学生看的中文自然语言。格式为三段式：

```
{章节名}第{N}段「{原文关键句开头15-20字}…」
```

**正确示例**：
- `4.1 变量描述第 2 段「最终构建了 4 个自变量…」`
- `5.1 研究主要结论第 2 条「本文基于公告内容预测债券违约风险…」`
- `中文摘要第 1 段「近年来，随着债券违约现象的加剧…」`

**禁止写法**（以下为真实踩坑记录）：
- `{'section':'全文'，'position':'论文整体结构'，'quote':'…'}` ← 禁止写成 dict/JSON 结构
- `段落#153` ← 禁止纯索引编号
- `全文` ← 禁止范围过宽

详见 `agent_instructions/issue_writing_protocol.md` §4「location 字段写作规范」。

### 4. issue_type 是问题描述，不是诊断域标签

`issue_type` 字段用于报告中的问题卡片标题，必须是学生能看懂的中文问题描述。

**正确示例**：
- `中英文摘要关键信息不一致`
- `核心变量口径前后不一致：自变量个数自相矛盾`
- `训练/测试集划分与防过拟合设计未披露`

**禁止写法**（以下为真实踩坑记录）：
- `methods` ← 这是诊断域，不是问题描述
- `writing` ← 同上
- `选题与研究问题` ← 这是 `domain` 字段的值，不是 `issue_type`

`domain` 和 `issue_type` 是两个不同的字段：
- `domain`：固定枚举值，如「选题与研究问题质检」「方法模型与实证结果质检」
- `issue_type`：自由文本，描述具体发现了什么问题

详见 `references/issue_schema.md` §3。

### 5. paper_profile 字段必须完整填充，不能留空

报告渲染依赖 `paper_profile` 中的字段来展示画像信息。以下字段缺失或为空时，报告会显示"未识别"或"无"：

- `paper_profile.detected_methods` — 论文使用的方法列表（如 `["固定效应模型", "中介效应"]`）
- `paper_profile.trigger_plan.triggered_rule_groups` — 触发的规则组
- `paper_profile.trigger_plan.not_applicable_rule_groups` — 不适用的规则组
- `paper_profile.trigger_plan.manual_confirmation_items` — 人工确认事项

**必须在写出 issues 之前填充这些字段**（参见 SKILL.md 第二、三步）。不要等写完 issues 再反推 trigger_plan——trigger_plan 是诊断的输入，不是输出。

### 6. 数组字段必须用列表格式，禁止用逗号分隔的字符串

`detected_methods`、`triggered_rule_groups`、`not_applicable_rule_groups` 等字段在 Schema 中定义为 `array`（列表）。

**正确**：`"detected_methods": ["固定效应模型", "中介效应"]`
**错误**：`"detected_methods": "固定效应模型, 中介效应"` ← 渲染时会按字符遍历，显示为「固、定、效、应、模、型、,、中、介、效、应」

写完 `diagnostic_result.json` 后运行 `self_check.py --validate` 可拦截此类错误。
