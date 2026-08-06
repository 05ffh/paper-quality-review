# 经管论文智检 Skill

> 广东金融学院火山杯智能体创新大赛 · 方向二（科研工具与代码开发类 · 论文校对）参赛作品

面向**经管类本科论文提交前自检**的 AI Skill。学生上传 `.docx` 或 `.pdf` 论文，Skill 自动识别论文类型与研究方法、条件触发检测规则、逐项语义判断问题，生成正式的 `.docx` 质检报告（另附 `.html` 预览版）。

不是查重工具，不是论文代写工具。是一份帮助学生在提交前发现结构、数据、变量、模型与规范风险的"体检报告"。

---

## 能力速览

| 能力 | 说明 |
|---|---|
| 基础质检 | Word / 文本 PDF · 五大诊断域 · 红黄绿灰分级 · DOCX 报告 · **68 条注册规则** + 7 项强制交叉核对 + 7 条红色硬伤边界 |
| KB-A 规范知识库 | GB/T 7714 引用规范 + 伍德里奇计量教材 · 18 条权威依据 |
| KB-B 范例知识库 | 20 篇顶刊论文（脱敏）· 2191 片段 · 零依赖 JSONL 索引，装好即用 |
| PDF 视觉辅助 | 可选。图片型表格/公式通过火山方舟视觉模型识别；未配置不影响 Word 和文本 PDF 质检 |

---

## 快速开始

```bash
git clone https://github.com/05ffh/econ-paper-check-skill.git
cd econ-paper-check-skill

# 安装核心依赖（Word/PDF 解析 + 报告渲染 + KB）
pip install --break-system-packages -r requirements-core.txt

# 自检
python3 scripts/doctor.py
```

**可选**：启用 PDF 视觉辅助识别（图片型表格/公式提取）和 ChromaDB 语义搜索，见下方详细说明。

---

## 触发使用

在 AI 对话中上传论文并说：

> 请使用经管论文智检 Skill 检测这篇论文，并生成 DOCX 质检报告。

也可以更具体：

> 请基于经管论文智检 Skill，对这篇本科经管论文做提交前自检，重点检查选题、文献、数据变量、模型方法、结构表达和参考文献规范。

同时把 `.docx` 或 `.pdf` 论文一起上传。

---

## 设计理念

**脚本做 I/O，大模型做判断。**

- 二进制文档解析和报告渲染，交给确定性的 Python 脚本
- "研究问题是否清晰""中英文摘要是否一致""结论方向是否与回归表矛盾"这类需要理解力的判断，交给大模型
- 规则库、证据门禁和语义判断协议严格约束大模型的输出

三项核心方法论：

1. **先画像，后触发**：先识别论文类型与已用方法，再条件触发规则。未用 DID 不查 DID，案例论文不硬套回归
2. **证据门禁**：无原文证据不输出；弱证据转"需人工确认"；红色必改问题必须有强证据且可定位
3. **红黄绿灰分级**：硬伤一律判红不得降级，总体风险按阈值映射，尽量保证不同智能体对同一论文得出一致结论

---

## 五大诊断域

1. **选题与研究问题质检** — 研究问题清晰度、选题可行性、与方法的匹配
2. **文献综述与理论链条质检** — 文献覆盖度、理论框架完整性、假设推导逻辑
3. **数据、变量与口径质检** — 数据来源可追溯性、变量定义完整性、口径一致性
4. **方法模型与实证结果质检** — 模型选择合理性、结果报告规范性、结论与表格一致性
5. **结构表达与学术规范质检** — 中英文摘要一致性、参考文献规范、表格编号、语言表达

---

## 分级体系

| 等级 | 含义 | 门槛 |
|---|---|---|
| 🔴 红色 | 必改问题 | 强证据、可定位、影响核心质量 |
| 🟡 黄色 | 建议补充 | 有基础但说明不充分 |
| 🟢 绿色 | 优化提升 | 不影响核心，仅提升可读性/规范性 |
| ⚪ 灰色 | 需人工确认 | 证据不足 / 图片表格公式 / 导师判断范围 |

---

## 环境自检

任何时候不确定当前能用什么，运行：

```bash
python3 scripts/doctor.py                # 人类可读
python3 scripts/doctor.py --json         # 机器可读
python3 scripts/doctor.py --smoke-test   # 追加视觉模型验证（需先配 .env.local）
python3 scripts/self_check.py --audit-rules  # 规则一致性审计
```

---

## 目录结构

```
econ-paper-check-skill/
├── SKILL.md                     Skill 入口：定位、边界、执行流程、PDF 降级策略
├── README.md                    本文件
├── install.sh                   一键安装脚本
├── requirements-core.txt        核心依赖（必装）
├── requirements-kb.txt          KB 增强依赖（可选：ChromaDB 语义搜索）
├── requirements-vision.txt      视觉辅助依赖（可选：火山方舟 PDF 图片识别）
├── agent_instructions/          判断协议（大模型必读）
│   ├── evidence_requirement.md      证据要求、红色硬伤清单、三层判定
│   ├── semantic_check_protocol.md   语义判断协议与交叉核对
│   ├── issue_writing_protocol.md    问题写作规范与 KB 引用红线
│   └── vision_protocol.md           视觉证据协议
├── references/                  方法论 Schema
│   ├── paper_profile_schema.md      论文画像结构
│   ├── diagnostic_domains.md        五大诊断域定义
│   ├── issue_schema.md              Issue 数据结构与字段说明
│   └── report_structure.md          报告章节结构
├── rules/                       规则库（YAML）
│   ├── rule_registry.yaml           规则注册表（68 条）与能力口径
│   ├── non_model_rules.yaml         非模型规则（35 条）
│   └── model_rules.yaml             模型规则（33 条，含 5 条 ML）
├── schemas/                     输出契约
│   └── diagnostic_result.schema.json    JSON Schema 结构校验
├── scripts/                     纯 I/O 脚本
│   ├── doctor.py                    环境自检（4 分组：依赖/知识库/组件/视觉）
│   ├── self_check.py                安装自检 + Schema 校验 + 规则审计
│   ├── parse_paper.py               统一解析入口（自动派发 docx/pdf）
│   ├── parse_docx.py                docx → paper_text.json
│   ├── parse_pdf.py                 pdf → paper_text.json
│   ├── render_report.py             diagnostic_result → DOCX 报告
│   ├── render_report_html.py        diagnostic_result → HTML 预览
│   ├── kb_query.py                  KB-A/B 双路由检索（JSONL 优先）
│   ├── kb_common.py                 Token 化 / 隐私扫描 / 文本清洗
│   ├── kb_ingest.py                 KB-B 论文入库与 JSONL 索引构建
│   ├── kb_admin.py                  KB 快照 / 回滚 / 完整性自检
│   ├── batch_check.py               批量解析 + 模板生成 + CSV 汇总
│   └── vision/                      视觉辅助管线（dispatcher/provider/normalizer/scorer）
├── knowledge_base/              知识库
│   ├── norms/                       KB-A 规范层（GB/T 7714 + 伍德里奇，18 条）
│   └── examples/index/              KB-B 范例层（JSONL 索引，2191 cards，零依赖）
├── templates/                   报告模板
├── examples/                    示例文件
├── docs/                        文档
│   └── CHECK_CATALOG.md             68 条规则人类可读索引
├── benchmarks/                  质量基准体系（开发者用）
└── tests/                       测试
```

---

## PDF 支持策略

- **推荐 Word**：`.docx` 解析最稳定，质检结论最可靠
- **文本 PDF 支持**：`pdfplumber` 解析，证据强度自动下调一档，表格/公式相关问题默认转灰色
- **扫描件保护**：若 `empty_pages / total_pages ≥ 0.7`，识别为扫描件并提示用户上传 Word 或先 OCR
- **不做 OCR**：本 Skill 边界内不集成 OCR

---

## 可选增强

### PDF 视觉辅助识别

论文中有大量图片型表格/公式/图表时，可启用火山方舟视觉模型辅助识别：

```bash
pip install --break-system-packages -r requirements-vision.txt
cp .env.example .env.local && chmod 600 .env.local
# 编辑 .env.local 填入 ARK_API_KEY 和 ARK_VISION_MODEL_ID
python3 scripts/doctor.py --smoke-test
```

### KB-B 语义搜索（可选）

如果需要更精准的范例检索（当前 JSONL 索引已覆盖基本场景）：

```bash
pip install --break-system-packages -r requirements-kb.txt
```

---

## 边界与免责

- 支持 `.docx` 与 `.pdf`（PDF 证据强度自动下调一档；不支持扫描件）
- **不做**：查重、论文代写、判断数据真实性、联网核验参考文献真伪
- **不替代**导师、答辩委员或学校正式评审
- 模型规则条件触发，不因论文未使用 DID/IV/PSM 等高级模型而判错
- 表述克制：只说"论文中未报告/未呈现/需人工确认"，不说"作者一定没有做"
- 无法可靠解析的表格、公式、图片一律标注"需人工确认"，不直接判"缺失"

---

## 已知限制

- 公式与图片仍是主要盲区：`python-docx` / `pdfplumber` 无法可靠解析公式对象与图片型表格
- PDF 解析噪声：中英文换行合并可能存在细小偏差，已通过证据降级 + 硬伤清单双闸门规避
- 判断质量依赖底层模型：需使用足够强的模型以保证交叉核对类问题不被漏检
