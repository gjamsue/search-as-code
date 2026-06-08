# Search-as-Code Dataset Benchmark Report

Dataset: `sac-codegen-v2`
Split: `test`
Documents: `2499`
Tasks: `22`
Primary metric: `Recall@10`
Candidate opportunity: rerank systems retrieve up to `2400` candidates per query before final top-10 output.

## Recall@10 Leaderboard

| System | Recall@10 | Hard-neg hit@10 | Mean latency ms | Candidate pool | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|
| fixed_bm25 | 0.2959 | 0.2727 | 2.7 | 10.0 | 1.00 | 0.0 |
| fixed_hybrid_rerank_small_budget | 0.2938 | 0.2273 | 884.1 | 400.0 | 1.00 | 400.0 |
| fixed_hybrid_rerank | 0.2861 | 0.2273 | 4599.9 | 2400.0 | 1.00 | 2400.0 |
| generated_search_as_code | 0.2861 | 0.2273 | 4664.5 | 2348.9 | 5.73 | 2332.2 |
| generated_reflective_search_as_code | 0.2861 | 0.2273 | 4761.8 | 2348.9 | 5.73 | 2332.2 |
| fixed_understanding_rewrite_hybrid_rerank | 0.2861 | 0.2273 | 4783.7 | 2481.0 | 3.96 | 2400.0 |
| generated_search_as_code_force_budget | 0.2861 | 0.2273 | 4922.6 | 2469.9 | 7.64 | 2400.0 |
| fixed_hybrid | 0.2614 | 0.1364 | 8.0 | 10.0 | 1.00 | 0.0 |
| fixed_semantic_dense | 0.1604 | 0.0909 | 4.0 | 10.0 | 1.00 | 0.0 |

## Readout

Generated Search-as-Code vs fixed enriched at Recall@10: delta recall `0.0000`, delta hard-negative hit rate `0.0000`. Generated mean candidate pool is `2348.9` documents per query; fixed enriched mean candidate pool is `2481.0`.

## Key Findings

- Top Recall@10 system is `fixed_bm25`: Recall@10 `0.2959`.
- `generated_search_as_code` Recall@10 is `0.2861` vs fixed enriched `0.2861`.
- Generated Search-as-Code hard-negative hit rate is `0.2273` vs fixed enriched `0.2273`.
- The cost is higher: generated flow averages `4664.5` ms vs fixed enriched `4783.7` ms, with `5.73` search calls and `2332.2` rerank pairs per query.
- Candidate opportunity is now large: fixed enriched sees `2481.0` candidates/query and generated sees `2348.9` candidates/query before final top-10.
- BM25 remains a serious baseline because it scores the full corpus directly: Recall@10 `0.2959` at `2.7` ms; dense-only Recall@10 is `0.1604`.
- Forced budget expansion does not change hard-negative hit rate (`0.2273`) and leaves Recall@10 at `0.2861`; more retrieval is not automatically better after reranking.
- Reflective mode triggered second-pass code on `0` / `22` test tasks, so it currently adds no quality gain. The reflection policy should use missing-evidence checks, not only thin candidate pools.

## Selected Examples

### sac-013 - dynamic_flow_shape

Query: Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?

Why selected: generated program chose multiple route types and budgets on a high-recall query

Gold: Beacon CRM Connector 3.14.1 is acceptable because it fixes CVE-2026-3771 with single-use refresh tokens. 3.14.0 only added diagnostics and did not fix the CVE.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.4000 | 1 | esc-contoso, meet-contoso, rel-beacon-3-14-0, cluster-beacon-oauth-3771-digest-001, ticket-sec-1811 |
| hybrid | 0.4000 | 0 | meet-contoso, esc-contoso, rel-beacon-3-14-0, ticket-sec-1811, cluster-customer-contoso-crm-033 |
| fixed_enriched | 0.6000 | 1 | meet-contoso, cluster-beacon-oauth-3771-digest-031, esc-contoso, rel-beacon-3-14-0, adv-beacon-oauth-3771 |
| generated | 0.6000 | 1 | meet-contoso, cluster-beacon-oauth-3771-digest-031, esc-contoso, rel-beacon-3-14-0, adv-beacon-oauth-3771 |
| generated_force_budget | 0.6000 | 1 | meet-contoso, cluster-beacon-oauth-3771-digest-031, esc-contoso, rel-beacon-3-14-0, adv-beacon-oauth-3771 |
| reflective | 0.6000 | 1 | meet-contoso, cluster-beacon-oauth-3771-digest-031, esc-contoso, rel-beacon-3-14-0, adv-beacon-oauth-3771 |

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "3.14.0 3.14.1 Beacon CRM Connector",
      "mode": "bm25",
      "top_k": 2000
    },
    {
      "query": "Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?",
      "mode": "bm25",
      "top_k": 2000
    },
    {
      "query": "compare beacon crm connector 3.14.0 3.14.1 contoso s security review. one is acceptable",
      "mode": "hybrid",
      "top_k": 45
    },
    {
      "query": "compare beacon crm connector 3.14.0 3.14.1 contoso s security review. one is acceptable",
      "mode": "bm25",
      "top_k": 35
    }
  ],
  "exact_terms": [
    "3.14.0",
    "3.14.1"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "exact identifiers use BM25 routes and exact-term pruning",
    "comparison query keeps larger rerank budget",
    "wide fanout query gets broader route budgets"
  ]
}
```

### sac-016 - reflection_noop_limitation

Query: A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?

Why selected: reflection did not trigger because first-pass candidate pool was not thin enough

Gold: When the condition is candidate pool below 25, it should generate follow-up retrieval code with a larger route budget rather than force all rerank candidates. In this dataset, the policy is to reflect on thin evidence, add targeted hybrid/BM25/dense routes, merge new candidates, and rerank only if new evidence appears.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.0000 | 1 | decoy-guide-025, decoy-guide-005, decoy-guide-045, decoy-guide-060, decoy-guide-020 |
| hybrid | 0.0000 | 0 | decoy-guide-025, decoy-guide-005, decoy-guide-045, cluster-enterprise-memo-055, decoy-guide-053 |
| fixed_enriched | 0.5000 | 0 | roadmap-rovo-sac, cluster-enterprise-memo-307, cluster-enterprise-memo-175, cluster-enterprise-memo-223, cluster-enterprise-memo-475 |
| generated | 0.5000 | 0 | roadmap-rovo-sac, cluster-enterprise-memo-307, cluster-enterprise-memo-175, cluster-enterprise-memo-223, cluster-enterprise-memo-475 |
| generated_force_budget | 0.5000 | 0 | roadmap-rovo-sac, cluster-enterprise-memo-307, cluster-enterprise-memo-175, cluster-enterprise-memo-223, cluster-enterprise-memo-475 |
| reflective | 0.5000 | 0 | roadmap-rovo-sac, cluster-enterprise-memo-307, cluster-enterprise-memo-175, cluster-enterprise-memo-223, cluster-enterprise-memo-475 |

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "bm25",
      "top_k": 30
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 30
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "negative/decision query checks exact and product-footprint evidence"
  ]
}
```


## Method Notes

- Code generation latency here is local deterministic generation time, not a hosted LLM call.
- The benchmark still reports generation time separately in JSON, so a real model latency can be added as a sensitivity analysis.
- BEIR qrels contain positive evidence only; hard-negative labels are evaluated separately.
