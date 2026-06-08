# Search-as-Code Benchmark Dataset 简介

## 一句话说明

这是一个自建的合成企业知识库 benchmark，用来评估 Search-as-Code / agentic search 是否比固定检索流程更擅长处理复杂企业搜索任务。它不是通用 IR benchmark，而是专门压力测试 fanout、join、精确 ID 检索、metadata filter、negative evidence、rerank budget control 和 reflection 等能力。

## 为什么要做这个数据集

现有公开 benchmark 通常适合评估标准 retrieval quality，但不容易隔离 Search-as-Code 的核心价值：让模型动态决定搜索路径、工具调用顺序、召回预算、rerank 候选集合和是否需要 follow-up search。

这个数据集模拟一个企业知识库场景：用户的问题往往不是简单找一篇文档，而是需要跨 customer notes、security advisories、Jira tickets、release notes、meeting notes 和 runbooks 做多跳关联，并且避免被大量相似但错误的文档干扰。

## 数据如何生成

数据由 [generate_dataset.py](sac_benchmark_dataset/generate_dataset.py) 确定性生成，每次运行会得到相同的数据集。

生成流程分四层：

1. Core enterprise knowledge

   先生成 57 篇核心文档或近核心文档，覆盖真实企业搜索里常见的信息源：

   - customer account brief
   - escalation log
   - renewal meeting note
   - security advisory
   - internal security ticket
   - release note
   - runbook / policy / roadmap / product footprint

2. Structured hard distractors

   再生成 2,442 篇 structured hard distractors。它们不是随机噪声，而是有意设计成“看起来很像答案但不是答案”的干扰文档：

   - 相近版本号：例如 `4.8.1` vs `4.8.2`
   - 相近 CVE / ticket ID
   - 同产品但错误漏洞
   - 相似客户名、行业、renewal date、risk level
   - 使用相同搜索术语但只提供泛化背景的 guide / policy docs

   v2 里额外加入了更接近企业知识库的 topic clusters：

   - 486 篇基础 hard distractors：附近版本、附近 CVE、相似客户、泛化 guide
   - 360 篇 incident clusters：6 个核心安全事件各 60 篇 draft、rollout、duplicate ticket、meeting、email、approval、postmortem、FAQ、dashboard
   - 480 篇 customer activity clusters：10 个核心客户各 48 篇 CRM snapshot、renewal note、escalation note、customer email、risk dashboard、implementation note、forecast note、audit packet
   - 576 篇 product knowledge clusters：6 个产品各 96 篇 release、migration、KB、runbook、advisory、rollback、compatibility、performance note
   - 540 篇 enterprise background clusters：war room、regulated renewal evidence、Search-as-Code eval、tool-calling comparison、rerank budget、reflection policy 等相似主题文档

3. Task labels

   生成 36 个任务，每个任务包含：

   - query
   - gold answer
   - structured answer fields
   - evidence document IDs
   - hard negative document IDs
   - required operations
   - expected ideal search routes
   - whether reflection is expected

4. Benchmark exports

   输出标准 JSONL 和 BEIR-style 文件：

   - `corpus.jsonl`
   - `tasks.jsonl`
   - `hard_negatives.jsonl`
   - `beir/corpus.jsonl`
   - `beir/queries.jsonl`
   - `beir/qrels/{train,dev,test}.tsv`
   - `beir/hard_negatives/{train,dev,test}.tsv`

BEIR qrels 只包含正相关 evidence。Hard negatives 单独导出，用于计算 hard-negative intrusion，而不是混在标准 relevance metrics 里。

## 企业场景设定

数据集围绕 6 个产品构造：

| Product | Corpus mentions |
|---|---:|
| AtlasSearch | 676 |
| Meridian Sync | 510 |
| Compass Analytics | 507 |
| Beacon CRM Connector | 459 |
| ForgeDeploy | 431 |
| Rovo Chat | 422 |

核心客户包括：

- Northwind Health
- Aster Bank
- Contoso Retail
- HelioGrid Energy
- BluePeak Insurance
- QuartzBio Labs
- Riverline Logistics
- UrbanNest
- NovaFoods
- Greenhouse University

这些客户被设计成有重叠产品、不同 renewal urgency、不同安全 blocker 和不同技术 owner，从而制造真实企业搜索里的 join 和 disambiguation 压力。

## 数据规模

| Item | Count |
|---|---:|
| Documents | 2,499 |
| Core / near-labeled documents | 57 |
| Structured hard distractors | 2,442 |
| Tasks | 36 |
| Train tasks | 7 |
| Dev tasks | 7 |
| Test tasks | 22 |
| Tasks with hard negatives | 36 |
| Hard-negative labels | 200 |
| Reflection-required tasks | 7 |
| Audit errors | 0 |
| Audit warnings | 0 |

Task difficulty:

| Difficulty | Count |
|---|---:|
| Hard | 20 |
| Medium | 16 |

## 文档类型

按生成目的分组：

| Group | Count |
|---|---:|
| Core / near-labeled evidence docs | 57 |
| Baseline structured distractors | 486 |
| Incident topic clusters | 360 |
| Customer activity clusters | 480 |
| Product knowledge clusters | 576 |
| Enterprise background clusters | 540 |

Top document types:

| Document Type | Count |
|---|---:|
| release_distractor | 264 |
| guide_distractor | 240 |
| security_advisory_distractor | 168 |
| meeting_note_distractor | 146 |
| security_ticket_distractor | 132 |
| account_brief_distractor | 110 |
| escalation_distractor | 110 |
| customer_email_distractor | 96 |
| risk_dashboard_distractor | 96 |
| memo / thread / review / dashboard / decision / draft distractors | 540 |
| runbook / compatibility / performance distractors | 216 |

## 任务类别

| Category | Count | What It Tests |
|---|---:|---|
| customer_patch_mapping | 7 | 从客户 blocker 映射到 ticket、CVE、fixed version、owner |
| wide_fanout | 4 | 跨多客户、多产品、多漏洞的大范围 fanout 和 aggregation |
| release_fix_mapping | 3 | 从 release notes 找修复版本、性能变化和相关 CVE |
| negative_evidence | 3 | 正确回答“不需要 / 不应包含”，并给出证据 |
| reflection_required | 3 | 当第一轮 evidence 不够时，是否应该生成 follow-up route |
| security_fanout_join | 2 | 客户、产品、漏洞、ticket、release、owner 的多源 join |
| exact_identifier_lookup | 2 | 精确保留并检索 `SEC-*`、`CVE-*`、版本号等 identifier |
| budget_control | 2 | 控制 rerank candidate budget，避免盲目扩大候选集 |
| tool_calling_vs_codegen | 2 | 比较多轮 tool calling 和一次性 codegen 的控制差异 |
| comparative_analysis | 2 | 比较版本、客户或 blocker 差异 |
| multi_hop | 2 | 通过多篇文档推断最终答案 |
| customer_risk_join | 1 | 汇总 customer renewal risk 和 next action |
| regulated_customer_filter | 1 | 按 regulated vertical、severity、renewal window 过滤 |
| policy_lookup | 1 | 查找 benchmark / policy 指标要求 |
| search_as_code_eval_design | 1 | 设计 Search-as-Code 评估表 |

## 覆盖的操作能力

| Operation | Task Count |
|---|---:|
| join | 26 |
| metadata_filter | 18 |
| bm25_exact | 16 |
| aggregate | 12 |
| entity_linking | 12 |
| fanout_search | 9 |
| negative_evidence_check | 5 |
| query_understanding | 4 |
| evidence_reflection | 3 |
| exact_version_compare | 3 |
| query_rewrite | 2 |
| candidate_pruning | 2 |
| dynamic_route_selection | 2 |
| semantic_search | 2 |

## 示例任务

### Fanout + Join

```text
For Riverline Logistics, identify every open security exception, its CVE, fixed version, and owner.
```

需要系统先找到 Riverline 的 account/escalation 文档，再识别两个 product blockers，并分别 join 到 AtlasSearch 和 Meridian Sync 的 advisory、ticket、release notes。

### Exact Identifier Lookup

```text
SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?
```

需要系统保留 `SEC-1899`，映射到 `CVE-2026-4520`，再找到相关客户和 `AtlasSearch 4.9.0`。

### Negative Evidence

```text
Does NovaFoods need any ForgeDeploy remediation for the June security rollout?
```

需要系统找到产品 footprint，确认 NovaFoods 没有 ForgeDeploy deployment，并用 negative evidence 回答“不需要”。

### Reflection

```text
If the first search only finds AtlasSearch SAML docs, what additional route should recover Riverline's second blocker?
```

需要系统发现 evidence pool 不完整，并生成 Meridian Sync / SEC-1775 / CVE-2026-2899 / 2.7.5 的 follow-up route。

## 质量控制

数据集通过两个脚本检查：

- [validate_dataset.py](sac_benchmark_dataset/validate_dataset.py)：schema、ID、qrels、hard negatives、split、coverage 检查
- [audit_dataset.py](sac_benchmark_dataset/audit_dataset.py)：内容级 audit，包括 answer field coverage、route modes、evidence distribution、hard-negative distribution、qrels cleanliness

当前质量报告见 [quality_report.json](sac_benchmark_dataset/data/quality_report.json)。

质量门槛包括：

- document 数至少 500
- structured distractors 至少 450
- 所有 task 都必须有 hard negatives
- structured distractor 不能作为 positive evidence
- evidence 和 hard negatives 不能重叠
- BEIR qrels 只能包含正相关 evidence
- hard negatives 单独导出，且必须和 task labels 一致
- test split 至少 18 个任务
- 至少 8 个 task categories
- 关键操作必须覆盖 fanout、join、metadata filter、BM25 exact、reflection、negative evidence、candidate pruning

## 适合用来评估什么

这个数据集适合比较：

- BM25 / dense / hybrid search
- fixed enriched retrieval
- hybrid + rerank
- tool-calling agent
- one-shot Search-as-Code
- reflective Search-as-Code
- forced budget / oracle route / no rewrite 等 ablation

建议报告指标：

- nDCG@k
- recall@k
- MRR@k
- all evidence recovered@k
- hard-negative hit rate@k
- hard-negative intrusion rate@k
- latency including codegen
- generation latency
- search calls
- rerank pairs
- candidate pool size
- reflection trigger precision

## 不适合用来证明什么

这个数据集是 targeted synthetic benchmark，不应用来单独证明某个系统“整体企业搜索能力更强”。它更适合回答一个具体问题：

> 在企业搜索中，当任务需要动态 route planning、exact ID preservation、multi-hop join、negative evidence 和 budget control 时，Search-as-Code 是否能比固定流程更好？

后续如果要增强外部可信度，应该补充真实内部 query logs、人工标注 citation correctness，以及人工评估 answer quality。
