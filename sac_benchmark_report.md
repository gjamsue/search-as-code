# Search-as-Code Dataset Benchmark Report

Dataset: `sac-codegen-v3`
Split: `test`
Documents: `6010`
Tasks: `31`
Primary metric: `Recall@10`
Candidate opportunity: rerank systems retrieve up to `2400` candidates per query before final top-10 output.

## Recall@10 Leaderboard

| System | Recall@10 | Hard-neg hit@10 | Mean latency ms | Candidate pool | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|
| fixed_bm25 | 0.2304 | 0.1290 | 11.0 | 10.0 | 1.00 | 0.0 |
| fixed_hybrid | 0.2286 | 0.0645 | 20.1 | 10.0 | 1.00 | 0.0 |
| generated_reflective_search_as_code | 0.1857 | 0.2258 | 3893.1 | 3214.5 | 5.71 | 2397.5 |
| generated_search_as_code_force_budget | 0.1857 | 0.2258 | 3900.0 | 3278.9 | 5.81 | 2400.0 |
| fixed_hybrid_rerank | 0.1857 | 0.2258 | 4049.5 | 2400.0 | 1.00 | 2400.0 |
| generated_search_as_code | 0.1857 | 0.2258 | 4076.7 | 3214.5 | 5.71 | 2397.5 |
| fixed_understanding_rewrite_hybrid_rerank | 0.1857 | 0.2258 | 4077.7 | 3659.9 | 3.97 | 2400.0 |
| fixed_hybrid_rerank_small_budget | 0.1714 | 0.1935 | 794.6 | 400.0 | 1.00 | 400.0 |
| fixed_semantic_dense | 0.0932 | 0.0323 | 19.2 | 10.0 | 1.00 | 0.0 |

## Readout

Generated Search-as-Code vs fixed enriched at Recall@10: delta recall `0.0000`, delta hard-negative hit rate `0.0000`. Generated mean candidate pool is `3214.5` documents per query; fixed enriched mean candidate pool is `3659.9`.

## Key Findings

- Top Recall@10 system is `fixed_bm25`: Recall@10 `0.2304`.
- `generated_search_as_code` Recall@10 is `0.1857` vs fixed enriched `0.1857`.
- Generated Search-as-Code hard-negative hit rate is `0.2258` vs fixed enriched `0.2258`.
- The cost is higher: generated flow averages `4076.7` ms vs fixed enriched `4077.7` ms, with `5.71` search calls and `2397.5` rerank pairs per query.
- Candidate opportunity is now large: fixed enriched sees `3659.9` candidates/query and generated sees `3214.5` candidates/query before final top-10.
- BM25 remains a serious baseline because it scores the full corpus directly: Recall@10 `0.2304` at `11.0` ms; dense-only Recall@10 is `0.0932`.
- Forced budget expansion does not change hard-negative hit rate (`0.2258`) and leaves Recall@10 at `0.1857`; more retrieval is not automatically better after reranking.
- Reflective mode triggered second-pass code on `0` / `31` test tasks, so it currently adds no quality gain. The reflection policy should use missing-evidence checks, not only thin candidate pools.

## Selected Examples

### sac-042 - dynamic_flow_shape

Query: For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?

Why selected: generated program chose multiple route types and budgets on a high-recall query

Gold: For the CEO Search-as-Code readout, end-to-end latency including code generation is the primary number. Execution-only latency excluding code generation should be shown as a diagnostic. The same ledger also keeps token cost, search calls, rerank pairs, invalid code rate, and reflection trigger precision.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0614, v3-policy-decoy-0304, v3-policy-decoy-0684, v3-policy-decoy-0099 |
| hybrid | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0164, v3-policy-decoy-0664, v3-policy-decoy-0564, v3-policy-decoy-0264 |
| fixed_enriched | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144 |
| generated | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144 |
| generated_force_budget | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144 |
| reflective | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144 |

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "ceo search-as-code readout latency number is primary including code generation execution-only",
      "mode": "hybrid",
      "top_k": 45
    },
    {
      "query": "ceo search-as-code readout latency number is primary including code generation execution-only",
      "mode": "bm25",
      "top_k": 35
    },
    {
      "query": "For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?",
      "mode": "bm25",
      "top_k": 28
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "metric query preserves numeric lexical evidence"
  ]
}
```

### sac-016 - reflection_noop_limitation

Query: A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?

Why selected: reflection did not trigger because first-pass candidate pool was not thin enough

Gold: When the condition is candidate pool below 25, it should generate follow-up retrieval code with a larger route budget rather than force all rerank candidates. In this dataset, the policy is to reflect on thin evidence, add targeted hybrid/BM25/dense routes, merge new candidates, and rerank only if new evidence appears.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.0000 | 0 | rollout-riverline-second-blocker-ledger, v3-reflection-decoy-0260, v3-reflection-decoy-0265, v3-reflection-decoy-0270, v3-reflection-decoy-0085 |
| hybrid | 0.0000 | 0 | v3-reflection-decoy-0425, v3-reflection-decoy-0325, v3-reflection-decoy-0225, v3-reflection-decoy-0405, v3-reflection-decoy-0395 |
| fixed_enriched | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| generated | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| generated_force_budget | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| reflective | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |

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
