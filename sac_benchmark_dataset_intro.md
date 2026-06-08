# Search-as-Code Benchmark Dataset 简介

## 一句话说明

这是一个自建的合成企业知识库 benchmark，用来评估 Search-as-Code / agentic search 是否比固定检索流程更擅长处理复杂企业搜索任务。它不是通用 IR benchmark，而是专门压力测试 fanout、join、精确 ID 检索、metadata filter、negative evidence、rerank budget control 和 reflection 等能力。

## 为什么要做这个数据集

现有公开 benchmark 通常适合评估标准 retrieval quality，但不容易隔离 Search-as-Code 的核心价值：让模型动态决定搜索路径、工具调用顺序、召回预算、rerank 候选集合和是否需要 follow-up search。

这个数据集模拟一个企业知识库场景：用户的问题往往不是简单找一篇文档，而是需要跨 customer notes、security advisories、Jira tickets、release notes、meeting notes 和 runbooks 做多跳关联，并且避免被大量相似但错误的文档干扰。

## 数据如何生成

数据由 [generate_dataset.py](sac_benchmark_dataset/generate_dataset.py) 确定性生成，每次运行会得到相同的数据集。

生成流程分五层：

1. Core enterprise knowledge

   先生成 68 篇核心文档、source-of-truth 文档或近核心文档，覆盖真实企业搜索里常见的信息源：

   - customer account brief
   - escalation log
   - renewal meeting note
   - security advisory
   - internal security ticket
   - release note
   - runbook / policy / roadmap / product footprint
   - alias registry / source authority matrix / final approval ledger / war-room roster

2. Structured hard distractors

   再生成 5,942 篇 structured hard distractors。它们不是随机噪声，而是有意设计成“看起来很像答案但不是答案”的干扰文档：

   - 相近版本号：例如 `4.8.1` vs `4.8.2`
   - 相近 CVE / ticket ID
   - 同产品但错误漏洞
   - 相似客户名、行业、renewal date、risk level
   - 使用相同搜索术语但只提供泛化背景的 guide / policy docs

   v3 里额外加入了更接近企业知识库的 topic clusters：

   - 486 篇基础 hard distractors：附近版本、附近 CVE、相似客户、泛化 guide
   - 360 篇 incident clusters：6 个核心安全事件各 60 篇 draft、rollout、duplicate ticket、meeting、email、approval、postmortem、FAQ、dashboard
   - 480 篇 customer activity clusters：10 个核心客户各 48 篇 CRM snapshot、renewal note、escalation note、customer email、risk dashboard、implementation note、forecast note、audit packet
   - 576 篇 product knowledge clusters：6 个产品各 96 篇 release、migration、KB、runbook、advisory、rollback、compatibility、performance note
   - 540 篇 enterprise background clusters：war room、regulated renewal evidence、Search-as-Code eval、tool-calling comparison、rerank budget、reflection policy 等相似主题文档
   - 480 篇 alias/code-name decoys：同一个缩写可能对应客户、项目、dashboard 或 sales note，逼迫系统先找 source-of-truth alias registry
   - 1,240 篇 policy/reflection decoys：大量 Search-as-Code policy draft、reflection scratchpad、latency readout，文字很像最终 policy 但指标或动作不完整
   - 1,780 篇 approval/war-room/namespace decoys：final approval、roster、namespace proof 的近重复文档，包含相同客户、CVE、版本号，但状态是 draft/stale/wrong-customer/non-authoritative

3. Authority and alias source docs

   v3 新增了一层正向 source-of-truth 文档，让任务不只是“搜 exact ID”，而是要先判断哪些证据更可信：

   - `alias-customer-codenames`：BPI、QBL、NF-17、RL-7、NW-H 等客户 alias 映射
   - `alias-owner-directory`：JBell、MP、PRao 等 owner alias 映射
   - `source-authority-matrix-v3`：final approval ledger / release note / Jira ticket 优先于 draft、Slack、dashboard
   - final approval ledgers：Contoso Beacon、Northwind AtlasSearch、QuartzBio namespace proof、Riverline second blocker
   - `warroom-r7-june-critical-roster`：June critical-patch war room 的最终 included/excluded alias roster

4. Task labels

   生成 48 个任务，每个任务包含：

   - query
   - gold answer
   - structured answer fields
   - evidence document IDs
   - hard negative document IDs
   - required operations
   - expected ideal search routes
   - whether reflection is expected

5. Benchmark exports

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
| AtlasSearch | 2,620 |
| ForgeDeploy | 1,262 |
| Meridian Sync | 1,212 |
| Beacon CRM Connector | 1,136 |
| Compass Analytics | 820 |
| Rovo Chat | 615 |

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
| Documents | 6,010 |
| Core / source-of-truth / near-labeled documents | 68 |
| Structured hard distractors | 5,942 |
| Tasks | 48 |
| Train tasks | 8 |
| Dev tasks | 9 |
| Test tasks | 31 |
| Tasks with hard negatives | 48 |
| Hard-negative labels | 266 |
| Reflection-required tasks | 9 |
| Audit errors | 0 |
| Audit warnings | 0 |

Task difficulty:

| Difficulty | Count |
|---|---:|
| Hard | 30 |
| Medium | 18 |

## 文档类型

按生成目的分组：

| Group | Count |
|---|---:|
| Core / source-of-truth / near-labeled evidence docs | 68 |
| Baseline structured distractors | 486 |
| Incident topic clusters | 360 |
| Customer activity clusters | 480 |
| Product knowledge clusters | 576 |
| Enterprise background clusters | 540 |
| v3 alias/code-name decoys | 480 |
| v3 policy/reflection decoys | 1,240 |
| v3 approval/war-room/namespace decoys | 1,780 |

Top document types:

| Document Type | Count |
|---|---:|
| dashboard_snapshot_distractor | 920 |
| meeting_note_distractor | 636 |
| draft_policy_distractor | 530 |
| slack_thread_distractor | 470 |
| review_note_distractor | 400 |
| memo_distractor | 390 |
| customer_email_distractor | 366 |
| guide_distractor | 330 |
| release_distractor | 264 |
| security_approval_distractor | 216 |
| security_advisory_distractor | 168 |
| implementation_note_distractor | 150 |

## 任务类别

| Category | Count | What It Tests |
|---|---:|---|
| customer_patch_mapping | 7 | 从客户 blocker 映射到 ticket、CVE、fixed version、owner |
| wide_fanout | 5 | 跨多客户、多产品、多漏洞的大范围 fanout 和 aggregation |
| release_fix_mapping | 3 | 从 release notes 找修复版本、性能变化和相关 CVE |
| negative_evidence | 4 | 正确回答“不需要 / 不应包含”，并给出证据 |
| reflection_required | 4 | 当第一轮 evidence 不够或缺少关键 evidence category 时，是否应该生成 follow-up route |
| authority_disambiguation | 3 | 在 final ledger、draft、Slack、dashboard 之间识别可引用来源 |
| alias_resolution | 2 | 先解析 BPI / QBL / NF-17 / JBell 等 alias，再做搜索和 join |
| policy_lookup | 3 | 查找 benchmark / policy / latency accounting 指标要求 |
| multi_hop | 3 | 通过多篇文档推断最终答案 |
| security_fanout_join | 2 | 客户、产品、漏洞、ticket、release、owner 的多源 join |
| exact_identifier_lookup | 2 | 精确保留并检索 `SEC-*`、`CVE-*`、版本号等 identifier |
| budget_control | 2 | 控制 rerank candidate budget，避免盲目扩大候选集 |
| tool_calling_vs_codegen | 2 | 比较多轮 tool calling 和一次性 codegen 的控制差异 |
| comparative_analysis | 2 | 比较版本、客户或 blocker 差异 |
| customer_risk_join | 1 | 汇总 customer renewal risk 和 next action |
| regulated_customer_filter | 1 | 按 regulated vertical、severity、renewal window 过滤 |
| temporal_authority | 1 | 使用 final roster / final approval，而不是 stale draft |
| search_as_code_eval_design | 1 | 设计 Search-as-Code 评估表 |

## 覆盖的操作能力

| Operation | Task Count |
|---|---:|
| join | 32 |
| rerank | 28 |
| metadata_filter | 21 |
| bm25_exact | 20 |
| aggregate | 14 |
| entity_linking | 13 |
| fanout_search | 9 |
| alias_resolution | 8 |
| source_authority_filter | 7 |
| negative_evidence_check | 6 |
| exact_version_compare | 6 |
| policy_lookup | 6 |
| query_understanding | 5 |
| evidence_reflection | 4 |
| query_rewrite | 2 |
| candidate_pruning | 2 |
| dynamic_route_selection | 2 |
| semantic_search | 3 |

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

- document 数至少 5,000
- structured distractors 至少 4,500
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
