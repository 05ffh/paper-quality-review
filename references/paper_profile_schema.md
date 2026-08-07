# paper_profile_schema.md

# 论文质量审查：论文画像 Schema

## 1. 文件作用

本文件定义 paper_profile。Claude Code 必须先生成论文画像，再触发规则。不得跳过画像直接检查问题。

## 2. 顶层结构

paper_profile 至少包含以下字段：

- file_info
- basic_info
- paper_type
- structure_profile
- data_profile
- method_profile
- table_profile
- trigger_plan
- evidence_map

## 3. JSON 结构示例

{
  "file_info": {
    "file_name": "",
    "file_format": ".docx",
    "is_complete_paper": true,
    "parse_warnings": []
  },
  "basic_info": {
    "title": "",
    "chinese_abstract": "",
    "english_abstract": "",
    "keywords": [],
    "has_reference_section": true
  },
  "paper_type": {
    "primary_type": "经管类实证论文",
    "secondary_types": [],
    "confidence": "高",
    "evidence": []
  },
  "structure_profile": {
    "has_title": true,
    "has_chinese_abstract": true,
    "has_english_abstract": true,
    "has_introduction": true,
    "has_literature_review": true,
    "has_data_or_case_section": true,
    "has_method_section": true,
    "has_result_section": true,
    "has_conclusion": true,
    "has_references": true
  },
  "data_profile": {
    "data_type": "面板数据",
    "sample_object": "",
    "sample_period": "",
    "data_sources": [],
    "has_variable_table": true,
    "has_sample_selection_description": true,
    "has_composite_index": false
  },
  "method_profile": {
    "uses_empirical_model": true,
    "detected_methods": [],
    "has_model_formula": true,
    "has_causal_identification_design": false,
    "has_mediation_or_mechanism": false,
    "has_questionnaire_scale": false
  },
  "table_profile": {
    "has_tables": true,
    "has_regression_table": true,
    "has_table_notes": true,
    "unreadable_tables": []
  },
  "trigger_plan": {
    "triggered_rule_groups": [],
    "not_applicable_rule_groups": [],
    "manual_confirmation_items": []
  },
  "evidence_map": {
    "paper_type": [],
    "data_type": [],
    "detected_methods": [],
    "has_empirical_section": [],
    "has_reference_section": [],
    "has_chinese_abstract": [],
    "has_english_abstract": [],
    "has_tables": []
  }
}

## 4. 论文类型允许值

- 经管类实证论文
- 经管类课程论文
- 案例分析论文
- 问卷调查论文
- 调查数据库论文
- 理论综述型论文
- 非经管类论文
- 不确定

### 4bis. secondary_types 子类型细分（v1.8+）

课程论文和案例分析论文可通过 `secondary_types` 进一步细分，以便触发更精确的规则：

- **课程论文子类型**：
  - 政策研究型：以政策梳理/国际比较/制度分析为主，通常无独立文献综述章节
  - 理论综述型：以理论演进/概念辨析/机制梳理为主
  - 问题对策型：以"现状描述→问题分析→对策建议"三明治结构为主

- **案例分析论文子类型**：
  - 纯描述型案例：大量事实罗列但缺少分析框架
  - 框架分析型案例：有明确的分析维度/理论框架/比较视角
  - 模型应用型案例：应用 KMV/Z-score/Logit 等量化模型进行案例分析
  - 问题对策型案例：以"案例问题识别→原因分析→建议"为主线

**子类型判断依据**：正文中的章节标题结构、分析方法、理论框架使用情况。不确定时写入"不确定"。

## 5. 数据类型允许值

- 截面数据
- 面板数据
- 时间序列数据
- 问卷数据
- 调查数据库
- 案例材料
- 综合指标数据
- 不确定

## 6. 方法识别范围

可识别方法包括 OLS、多元线性回归、面板固定效应、随机效应、双向固定效应、Logit、Probit、中介效应、调节效应、DID、IV、2SLS、熵值法、TOPSIS、PCA、因子分析、问卷信度效度、案例分析、AHP（层次分析法）、KMV（KMV 信用风险度量模型）、蒙特卡洛模拟。

## 7. 画像证据要求

每个核心判断都应有 evidence_map。证据应来自题目、摘要、章节标题、数据来源、变量定义、模型设定、表格标题、结果解释或参考文献等可见内容。

若无法稳定判断，应写“不确定，需人工确认”，不得编造。
