# 论文结构化质量诊断

> 广东金融学院火山杯智能体创新大赛 · 方向二（科研工具与代码开发类 · 论文校对）参赛作品

基于**多维规则引擎与证据门禁**的学术论文提交前质量审查系统。上传 `.docx` 或 `.pdf` 论文，系统自动识别论文类型与研究方法、条件触发检测规则、逐项语义判断问题，生成正式的 `.docx` 诊断报告（另附 `.html` 预览版）。

不是查重工具，不是论文代写工具。是一份帮助学生在提交前发现结构、数据、变量、模型与规范风险的诊断报告。

---

## 能力速览

| 能力 | 说明 |
|---|---|
| 基础诊断 | Word / 文本 PDF · 五大诊断域 · 红黄绿灰分级 · DOCX + HTML 双格式报告 · **68 条注册规则** + 7 项交叉核对 + 7 条红色硬伤边界 |
| 规则引擎 | 条件触发：先识别论文类型与已用方法，再精确激活适用规则；未用 DID 不查 DID，案例论文不硬套回归 |
| 证据门禁 | 无原文证据不输出；弱证据转"需人工确认"；红色必改问题必须有强证据且可定位；rule_id 注册表门禁防幻觉 |
| KB-A 规范知识库 | GB/T 7714 引用规范 + 伍德里奇计量教材 · 18 条权威依据 |
| KB-B 范例知识库 | 20 篇顶刊论文（脱敏）· 2191 片段 · 零依赖 JSONL 索引 |
| PDF 视觉辅助 | 可选。图片型表格/公式通过火山方舟视觉模型识别；未配置不影响 Word 和文本 PDF 诊断 |

---

## 快速开始

```bash
git clone https://github.com/05ffh/econ-paper-check-skill.git
cd econ-paper-check-skill
pip install --break-system-packages -r requirements-core.txt
python3 scripts/doctor.py
```

---

## 设计理念

**脚本做 I/O，大模型做判断。**

- 文档解析和报告渲染，交给确定性的 Python 脚本
- "研究问题是否清晰""中英文摘要是否一致""结论方向是否与回归表矛盾"——这类需要理解力的判断，交给大模型
- 规则库、证据门禁和语义判断协议严格约束大模型的输出

---

## 输出格式

报告标题为**《论文结构化质量诊断报告》**，副标题 **「基于多维规则引擎与证据门禁的提交前质量审查」**，包含 11 个章节：

1. 检测基本信息
2. 论文画像识别结果
3. 总体评价与修改优先级
4. 通过项概览
5. 红色必改问题
6. 黄色建议补充问题
7. 绿色优化提升建议
8. 灰色需人工确认事项
9. 五大诊断域详情
10. 优先修改行动清单
11. 免责声明

每项问题提供**问题等级、所属诊断域、所在位置、原文证据、证据强度、问题说明、修改建议**，location 字段采用三要素格式（章节名 + 精确位置 + 原文关键句引用），学生无需对照解析文件即可定位。

排版采用中国高校论文标准字体（正文宋体、标题黑体），Word/WPS 导航窗格完整展示文档结构。

---

## 五大诊断域

1. **选题与研究问题** — 研究问题清晰度、选题可行性、与方法的匹配
2. **文献综述与理论链条** — 文献覆盖度、理论框架完整性、假设推导逻辑
3. **数据、变量与口径** — 数据来源可追溯性、变量定义完整性、口径一致性
4. **方法模型与实证结果** — 模型选择合理性、结果报告规范性、结论与表格一致性
5. **结构表达与学术规范** — 中英文摘要一致性、参考文献规范、表格编号、语言表达

---

## 分级体系

| 等级 | 含义 | 门槛 |
|---|---|---|
| 🔴 红色 | 必改问题 | 强证据、可定位、影响核心质量。硬伤一律判红不得降级 |
| 🟡 黄色 | 建议补充 | 有基础但说明不充分 |
| 🟢 绿色 | 优化提升 | 不影响核心，仅提升可读性与规范性 |
| ⚪ 灰色 | 需人工确认 | 证据不足 / 图片表格公式 / 导师判断范围 |

---

## 环境自检

```bash
python3 scripts/doctor.py                  # 完整状态报告
python3 scripts/doctor.py --json           # 机器可读
python3 scripts/doctor.py --smoke-test     # 追加视觉模型验证
python3 scripts/self_check.py              # 安装自检
python3 scripts/self_check.py --audit-rules   # 规则一致性审计
python3 scripts/self_check.py --validate result.json   # 输出 Schema 校验（含 rule_id 门禁）
```

---

## 目录结构

```
econ-paper-check-skill/
├── SKILL.md                     Skill 入口
├── agent_instructions/          判断协议：证据要求、语义判断、写作规范、视觉协议
├── references/                  方法论 Schema：论文画像、诊断域、Issue 结构、报告结构
├── rules/                       规则库（68 条）：注册表 + 非模型规则 + 模型规则
├── schemas/                     输出契约：diagnostic_result JSON Schema
├── scripts/                     I/O 脚本：解析、渲染、KB 检索、自检、批量
│   ├── parse_paper.py           统一解析入口（自动派发 docx/pdf）
│   ├── render_report.py         diagnostic_result → DOCX 报告
│   ├── kb_query.py              KB-A/B 双路由检索
│   ├── doctor.py                环境自检
│   ├── self_check.py            安装自检 + Schema 校验 + 规则审计
│   └── vision/                  视觉辅助管线（可选）
├── knowledge_base/              知识库：KB-A 规范（18条）+ KB-B 范例（2191 cards）
├── templates/                   报告模板
├── examples/                    示例
├── docs/                        文档
├── benchmarks/                  质量基准（开发者用）
└── tests/                       测试
```

---

## PDF 支持策略

- **推荐 Word**：`.docx` 解析最稳定，诊断结论最可靠
- **文本 PDF 支持**：`pdfplumber` 解析，证据强度自动下调一档，表格/公式相关问题默认转灰色
- **扫描件保护**：若 `empty_pages / total_pages ≥ 0.7`，识别为扫描件并提示用户上传 Word 或先 OCR
- **不做 OCR**：本系统边界内不集成 OCR

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

### KB-B 语义搜索

如需更精准的范例检索（当前 JSONL 索引已覆盖基本场景）：

```bash
pip install --break-system-packages -r requirements-kb.txt
```

---

## 边界与免责

- 支持 `.docx` 与 `.pdf`（PDF 证据强度自动下调一档；不支持扫描件）
- **不做**：查重、论文代写、判断数据真实性、联网核验参考文献真伪
- **不替代**导师、答辩委员或学校正式评审
- 模型规则条件触发，不因论文未使用特定高级模型而判错
- 表述克制：只说"论文中未报告/未呈现/需人工确认"，不说"作者一定没有做"
- 无法可靠解析的表格、公式、图片一律标注"需人工确认"

---

## 已知限制

- 公式与图片仍是主要盲区：`python-docx` / `pdfplumber` 无法可靠解析公式对象与图片型表格
- PDF 解析噪声：中英文换行合并可能存在细小偏差，已通过证据降级 + 硬伤清单双闸门规避
- 判断质量依赖底层模型：需使用足够强的模型以保证交叉核对类问题不被漏检
