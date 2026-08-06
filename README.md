# 经管论文智检 Skill

> 广东金融学院火山杯智能体创新大赛 · 方向二（科研工具与代码开发类 · 论文校对）参赛作品

面向**经管类本科论文提交前自检**的原生 Skill 包，深度适配 **ArkClaw** 生态，同时兼容 Claude Code / OpenClaw。学生上传 `.docx` 或 `.pdf` 论文，Skill 自动识别论文类型与研究方法、条件触发检测规则、逐项语义判断问题，并生成一份正式的 `.docx` 质检报告（webchat 场景另附 `.html` 预览版）。

它不是查重工具，也不是论文代写工具，而是一份帮助学生在提交前发现结构、数据、变量、模型与规范风险的“体检报告”。

---

## ⚡ 能力速览

| 能力 | 状态 | 说明 |
|---|---|---|
| ✅ **基础质检** | **默认可用** · 装好依赖即用 | Word / 文本 PDF · 五大诊断域 · 红黄绿灰分级 · 生成 DOCX 报告 · **82 项检测能力**（68 条注册规则 + 7 项强制交叉核对 + 7 条红色硬伤边界，口径见 `rules/rule_registry.yaml` §capability_breakdown）|
| ✅ **KB 双层知识库** | 默认启用 | KB-A 规范层（GB/T 7714 + 伍德里奇 · 18 条）+ KB-B 范例层（20 篇顶刊 · 2198 chunks）|
| 🟡 **PDF 视觉辅助识别** | **可选** · 需单独配置 | PDF 图片/表格通过火山方舟视觉模型辅助识别；**未配置也不影响** Word 和文本 PDF 质检 |

> **未配置视觉辅助 = 完全不影响** Word 质检和文本层 PDF 质检；仅在遇到 PDF 中的图片型表格/公式/图表时，这类内容会进入“需人工复核”清单，其余判定照常。

---

## 🚀 快速开始（两条路径，按需二选）

### 路径 A · 基础质检安装（推荐大多数用户从这里开始）

```bash
git clone https://github.com/05ffh/econ-paper-check-skill.git
cd econ-paper-check-skill

# 装基础依赖（Word/PDF 解析 + 报告渲染 + KB）
pip install --break-system-packages \
    -r requirements-core.txt \
    -r requirements-kb.txt

# 安装到 ArkClaw / OpenClaw skill 目录
bash install.sh                    # 装到 ~/.agents/skills/
# 或
bash install.sh --plugin           # 装到 ~/.openclaw/plugin-skills/

# 自检
python3 scripts/doctor.py
```

**至此已可用**：Word 全流程 + 文本 PDF 全流程 + KB 规范层/范例层挂载。

### 路径 B · 追加 PDF 视觉辅助识别（可选）

> 什么时候需要：论文有大量图片型表格 / 公式 / 图表，Word 里也没原生文本，需要 PDF 视觉模型辅助识别。

```bash
# 1. 装视觉依赖（openai SDK 走 OpenAI Compatible 接入火山方舟）
pip install --break-system-packages -r requirements-vision.txt

# 2. 配 .env.local（chmod 600 · gitignored）
cp .env.example .env.local
chmod 600 .env.local

# 用你的编辑器打开 .env.local，填 3 项：
#   VISION_ENABLED=true
#   ARK_API_KEY=<你的火山方舟 Key，去 https://console.volcengine.com/ark 领取>
#   ARK_VISION_MODEL_ID=<视觉模型 ID 或 Endpoint ID>

# 3. 冒烟测试（用 fixture 图片走一次真实 Ark 调用）
python3 scripts/doctor.py --smoke-test

# 4. 再看一次能力摘要
python3 scripts/doctor.py
```

**成功标志**：`doctor.py` 第 [4] 项从 ⚪（未配置）→ 🟡（已配置未验证）→ ✅（已验证可用）。

---

## 🩺 doctor.py · 环境自检入口

任何时候不确定当前能用什么，跑一次：

```bash
python3 scripts/doctor.py                # 常规检查
python3 scripts/doctor.py --smoke-test   # 追加视觉模型真实调用（约 5-10 s）
```

输出会告诉你：

- 基础质检是否可用（依赖 / 报告组件）
- KB-A / KB-B 是否可用
- PDF 视觉辅助识别处于三态哪一态（未配置 / 已配置未验证 / 已验证可用）
- 若未配置：会**同时给出**能启用哪些能力、`requirements-vision.txt` 安装命令、`.env` 配置步骤、`VISION_ENABLED` 启用方式

---

## 🎬 触发使用

在 ArkClaw / OpenClaw 对话中直接说，无需命令行：

> 请使用经管论文智检 Skill 检测这篇论文，并生成 DOCX 质检报告。

或更具体：

> 请基于经管论文智检 Skill，对这篇本科经管论文做提交前自检，重点检查选题、文献、数据变量、模型方法、结构表达和参考文献规范。

同时把 `.docx` 或 `.pdf` 论文一起上传。

### 视觉辅助的自动触发

**用户不需要主动说“请调用视觉模型”**。Skill 会：

1. 收到 PDF → 自动分诊（`scripts/vision/document_triage.py`）识别是否含图片型表格 / 公式 / 图表关键区域
2. **同时满足三个条件时自动调用**视觉 Provider：
   - PDF 中存在关键图片区域
   - `VISION_ENABLED=true` 且配置有效（Key / Model ID / SDK 就绪）
   - 用户在会话中已知情同意（首次调用前 Skill 会明确告知本次将上传第 X/Y/Z 页到火山方舟）
3. 上述任一未满足 → 该区域进入“需人工复核”清单，基础质检其余部分照常完成

**Word 或不含关键图片区域的 PDF**：视觉辅助不启动，也不反复宣传，直接跑基础质检。

---

## 核心设计理念

**脚本做 I/O，大模型做判断。** 这是本 Skill 与普通“关键词匹配脚本”的根本区别：

- 二进制 `.docx` / `.pdf` 的解析与报告渲染，交给确定性的 Python 脚本；
- “研究问题是否清晰”“中英文摘要是否一致”“结论方向是否与回归表矛盾”这类需要理解力的判断，交给大模型，并由规则库、证据门禁和语义判断协议严格约束。

配套三项方法论保证质量：

1. **先画像，后触发**：先识别论文类型与已用方法，再条件触发规则。未用 DID 不查 DID，案例论文不硬套回归。
2. **证据门禁**：无原文证据不输出；弱证据转“需人工确认”；红色必改问题必须有强证据且可定位。
3. **红黄绿灰分级 + 强制判定标准**：硬伤一律判红不得降级，总体风险按阈值映射，尽量保证不同智能体对同一论文得出一致结论。

| 类别 | 变更 |
|---|---|
| 📄 输入 | **默认支持 `.pdf`**，用 `pdfplumber` 解析；PDF 场景自动降级证据强度，表格/公式相关问题默认转灰色；扫描件明确提示不支持 |
| 🚚 交付 | SKILL.md 明确 ArkClaw 各渠道交付方式（webchat `<file-list>` / 飞书 lark-doc / 企微 wecom-doc / 钉钉 dws-cli / 兜底 `MEDIA:`） |
| 📁 工作目录 | 统一使用 `~/.openclaw/workspace/.econ-paper-check/<yyyymmdd_HHMMSS>/` 隔离工作区 |
| 🧪 Preflight | 新增 `scripts/preflight.sh`，自动检查并（尝试）安装 `python-docx` / `pdfplumber` |
| 📦 安装 | 新增 `install.sh`，一键装到 `~/.agents/skills/` 或 `~/.openclaw/plugin-skills/` |
| 🌐 HTML 预览 | 新增 `scripts/render_report_html.py`，webchat 渠道可同时投递彩色 HTML 预览 |
| 🔤 触发词 | SKILL.md frontmatter 补充完整中文触发词列表 |
| 🅰️ 字体 fallback | `render_report.py` 中文字体设置包容异常，避免 headless 环境崩溃 |
| 📊 元信息 | `metadata.json` 更新为 `arkclaw.yaml`，声明 ArkClaw 生态标识与依赖 |
| 🧑‍🤝‍🧑 团队模式 | 新增 `team_mode.md`，可用 `arkclaw-team-project-builder` 拆成 profiler / inspector / reporter 三 agent 协作 |
| 📚 知识库 | `knowledge_base/README.md` 对接 ArkClaw 生态方案（byted-knowledge-center-aisearch / lark-wiki / 离线 RAG） |
| ✅ 样例 | 新增真实 `examples/diagnostic_result.example.json` 与 `templates/报告_模板_示例.{docx,html}` |

方法论层（规则库、判断协议、五大诊断域、红黄绿灰分级、6 条硬伤清单、7 项强制交叉核对、总体风险映射公式）**完全保留不变**。

---

## v1.1 · ArkClaw 适配更新（历史版本）

---

## 一句话流程

```
用户上传 DOCX / PDF
  → parse_paper.py 自动派发到 parse_docx / parse_pdf
     → 生成带定位的 paper_text.json
  → 大模型（读 rules/ + references/ + agent_instructions/）
     生成论文画像 → 条件触发 → 五大诊断域语义判断 → diagnostic_result.json
  → render_report.py 渲染 11 章节 DOCX 报告
  → (可选) render_report_html.py 渲染 HTML 预览
  → 按当前渠道投递（webchat file-list / 飞书 / 企微 / 钉钉 / MEDIA 兜底）
```

## 五大诊断域

1. 选题与研究问题质检
2. 文献综述与理论链条质检
3. 数据、变量与口径质检
4. 方法模型与实证结果质检
5. 结构表达与学术规范质检

## 分级体系

| 等级 | 含义 | 门槛 |
|---|---|---|
| 🔴 红色 | 必改问题 | 强证据、可定位、影响核心质量 |
| 🟡 黄色 | 建议补充 | 有基础但说明不充分 |
| 🟢 绿色 | 优化提升 | 不影响核心，仅提升可读性/规范性 |
| ⚪ 灰色 | 需人工确认 | 证据不足 / 图片表格公式 / 导师判断范围 |

---

## 目录结构

```
econ-paper-check-skill/
├── SKILL.md                主入口：定位、边界、执行流程、渠道投递、PDF 降级策略
├── arkclaw.yaml            ArkClaw skill 元信息（供仓库/SkillHub 展示）
├── install.sh              一键安装脚本（--plugin / --dest 可选）
├── requirements.txt        依赖：python-docx + pdfplumber
├── team_mode.md            ArkClaw 团队模式三 agent 分工说明
├── references/             方法论 schema
│   ├── paper_profile_schema.md
│   ├── diagnostic_domains.md
│   ├── issue_schema.md
│   └── report_structure.md
├── rules/                  规则库（YAML）
│   ├── rule_registry.yaml
│   ├── non_model_rules.yaml
│   └── model_rules.yaml
├── agent_instructions/     判断协议
│   ├── evidence_requirement.md
│   ├── semantic_check_protocol.md
│   └── issue_writing_protocol.md
├── scripts/                纯 I/O 脚本
│   ├── preflight.sh              依赖前置检查
│   ├── parse_paper.py            统一解析入口（自动派发 docx/pdf）
│   ├── parse_docx.py             docx → paper_text.json
│   ├── parse_pdf.py              pdf → paper_text.json（自动降级）
│   ├── render_report.py          diagnostic_result → DOCX
│   └── render_report_html.py     diagnostic_result → HTML 预览
├── knowledge_base/         第二阶段知识库对接（byted-knowledge-center-aisearch 等）
├── templates/              报告模板设计规范 + 真实样例 docx/html
└── examples/               示例设计规范 + 真实 diagnostic_result.example.json
```

---

## 历史快速开始（v1.1 旧版，保留供参考）

### 一键安装

```bash
git clone https://github.com/05ffh/econ-paper-check-skill.git
cd econ-paper-check-skill
bash install.sh                    # 装到 ~/.agents/skills/
# 或
bash install.sh --plugin           # 装到 ~/.openclaw/plugin-skills/
```

### 触发使用（v1.1 旧文本）

在 ArkClaw / OpenClaw 对话中直接说，无需命令行：

> 请使用经管论文智检 Skill 检测这篇论文，并生成 DOCX 质检报告。

或更具体：

> 请基于经管论文智检 Skill，对这篇本科经管论文做提交前自检，重点检查选题、文献、数据变量、模型方法、结构表达和参考文献规范。

同时把 `.docx` 或 `.pdf` 论文一起上传。

### 手动跑通（本地调试）

```bash
# 0. 前置依赖检查
bash scripts/preflight.sh

# 1. 解析论文为结构化 JSON（自动识别 docx/pdf）
python3 scripts/parse_paper.py 论文.docx --out paper_text.json

# 2. 大模型据 paper_text.json + 规则库/协议，产出 diagnostic_result.json

# 3. 渲染 DOCX 报告
python3 scripts/render_report.py diagnostic_result.json \
  --out 报告.docx --source 论文.docx

# 4. (可选) 渲染 HTML 预览版
python3 scripts/render_report_html.py diagnostic_result.json \
  --out 报告.html --source 论文.docx
```

---

## PDF 支持策略

- **默认开启**：符合 ArkClaw "脚本工具兜底 + LLM 语义判断"的哲学，覆盖真实提交场景（学校终稿往往是 PDF）。
- **证据强度自动降级**：`source_format=pdf` 时 `confidence_downgrade=true`，整体证据下调一档，表格/公式相关问题默认转灰色。
- **扫描件保护**：若 `empty_pages / total_pages >= 0.7`，识别为扫描件并停止判断，提示用户 OCR 或上传 docx。
- **不做 OCR**：本 Skill 边界内不集成 OCR，如需 OCR 请用 ArkClaw 生态里的 `ocr-document-processor` skill 预处理。

---

## 边界与免责

- **支持 `.docx` 与 `.pdf`**（PDF 场景证据强度自动下调一档；不支持扫描件）
- **不做**：查重、论文代写、判断数据真实性、联网核验参考文献真伪
- **不替代**导师、答辩委员或学校正式评审
- 模型规则条件触发，**不因论文未使用 DID/IV/PSM 等高级模型而判错**
- 表述克制：只说"论文中未报告/未呈现/需人工确认"，不说"作者一定没有做"
- 无法可靠解析的表格、公式、图片一律标注为"需人工确认"，不直接判"缺失"

---

## 已知限制

- **公式与图片仍是主要盲区**：`python-docx` / `pdfplumber` 都无法可靠解析公式对象与图片型表格，这类内容会被标记为"需人工确认"。真实论文中大量核心方法（如熵值法公式、模型方程）常以公式对象呈现，是当前主要短板。
- **PDF 解析噪声**：PDF 段落切分依赖启发式规则，中英文换行合并可能存在细小偏差。已通过全局证据强度降级 + 硬伤清单双闸门规避大偏差风险。
- **判断质量依赖底层模型**：语义判断由大模型完成，需确保平台使用足够强的模型（如 Claude 系列 / doubao-1.5 pro）以保证交叉核对类问题不被漏检。

## 知识库（第二阶段）

`knowledge_base/` 目录预留了知识库接口。计划纳入论文写作规范、GB/T 7714 引用格式、经管实证方法要点、学院模板等规范源文件。详见 `knowledge_base/README.md`。

## 团队模式（可选）

大论文（> 3 万字）或想演示 ArkClaw 项目/团队 workflow 场景时，可用 `arkclaw-team-project-builder` skill 一键把智检流程拆成 profiler / inspector / reporter 三 agent 顺序执行。详见 `team_mode.md`。

---

## 团队协作说明

- 本仓库为团队共享的 Skill 源，成员通过 `git pull` 获取最新版本，无需每次重新打包 zip
- 修改规则库（`rules/`）或判断协议（`agent_instructions/`）后提交推送，其他成员拉取即可
- 建议在多个智能体（ArkClaw / Claude Code / OpenClaw）上交叉测试同一篇论文，用结论差异定位规则需收紧之处
