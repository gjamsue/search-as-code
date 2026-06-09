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
| generated_iterative_agentic_search_as_code | 0.4579 | 0.2581 | 3318.9 | 3227.1 | 6.61 | 2397.5 |
| fixed_bm25 | 0.2304 | 0.1290 | 11.0 | 10.0 | 1.00 | 0.0 |
| fixed_hybrid | 0.2286 | 0.0645 | 17.6 | 10.0 | 1.00 | 0.0 |
| generated_search_as_code | 0.1857 | 0.2258 | 3199.6 | 3214.5 | 5.71 | 2397.5 |
| fixed_hybrid_rerank | 0.1857 | 0.2258 | 3204.0 | 2400.0 | 1.00 | 2400.0 |
| generated_reflective_search_as_code | 0.1857 | 0.2258 | 3205.1 | 3214.5 | 5.71 | 2397.5 |
| generated_search_as_code_force_budget | 0.1857 | 0.2258 | 3207.4 | 3278.9 | 5.81 | 2400.0 |
| fixed_understanding_rewrite_hybrid_rerank | 0.1857 | 0.2258 | 3220.5 | 3659.9 | 3.97 | 2400.0 |
| fixed_hybrid_rerank_small_budget | 0.1714 | 0.1935 | 609.1 | 400.0 | 1.00 | 400.0 |
| fixed_semantic_dense | 0.0932 | 0.0323 | 14.1 | 10.0 | 1.00 | 0.0 |

## Readout

Iterative agentic Search-as-Code is the first flow that clearly separates from fixed search: Recall@10 `0.4579` vs one-shot generated `0.1857` and fixed enriched `0.1857` (delta vs fixed `0.2722`, delta vs one-shot `0.2722`). It pays modestly more search control cost: `6.61` search calls/query and `3318.9` ms mean latency. Hard-negative hit rate rises by `0.0323`, so the next quality gate is final context/answer selection.

## Key Findings

- Top Recall@10 system is `generated_iterative_agentic_search_as_code`: Recall@10 `0.4579`.
- Iterative agentic Search-as-Code improves Recall@10 to `0.4579` vs one-shot generated `0.1857` and fixed enriched `0.1857`.
- The gain comes from evidence-coverage reflection: it checks missing categories such as alias, account/escalation, ticket/advisory, release note, source authority, and policy before final top-10.
- Cost is only modestly higher than one-shot: `3318.9` ms vs `3199.6` ms, with `6.61` vs `5.71` search calls/query.
- Hard-negative hit rate increases to `0.2581` vs fixed enriched `0.2258`; this is acceptable for recall-oriented retrieval but needs answer-level filtering.
- One-shot generated Search-as-Code remains tied with fixed enriched at Recall@10 `0.1857`; codegen needs reflection on evidence coverage, not just route generation.
- Candidate opportunity is large: fixed enriched sees `3659.9` candidates/query and generated sees `3214.5` candidates/query before final top-10.
- BM25 remains a serious baseline because it scores the full corpus directly: Recall@10 `0.2304` at `11.0` ms; dense-only Recall@10 is `0.0932`.
- Forced budget expansion does not change hard-negative hit rate (`0.2258`) and leaves Recall@10 at `0.1857`; more retrieval is not automatically better after reranking.
- Reflective mode triggered second-pass code on `0` / `31` test tasks, so it currently adds no quality gain. The reflection policy should use missing-evidence checks, not only thin candidate pools.

## Selected Examples

### sac-013 - iterative_agentic_win

Query: Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?

Why selected: iterative agentic Search-as-Code recovered evidence that one-shot and fixed flows missed

Gold: Beacon CRM Connector 3.14.1 is acceptable because it fixes CVE-2026-3771 with single-use refresh tokens. 3.14.0 only added diagnostics and did not fix the CVE.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.0000 | 1 | approval-beacon-contoso-may06, v3-approval-decoy-0151, v3-approval-decoy-0001, v3-approval-decoy-0451, v3-approval-decoy-0511 |
| hybrid | 0.0000 | 0 | approval-beacon-contoso-may06, v3-approval-decoy-0711, v3-approval-decoy-0501, v3-approval-decoy-0616, v3-approval-decoy-0826 |
| fixed_enriched | 0.0000 | 0 | approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071 |
| generated | 0.0000 | 0 | approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071 |
| iterative_agentic | 1.0000 | 0 | alias-customer-codenames, esc-contoso, acct-contoso, adv-beacon-oauth-3771, ticket-sec-1811 |
| generated_force_budget | 0.0000 | 0 | approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071 |
| reflective | 0.0000 | 0 | approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071 |

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
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
  "goals": [
    "alias_registry",
    "account_or_escalation",
    "ticket_or_advisory",
    "release_note"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "exact identifiers use BM25 routes and exact-term pruning",
    "comparison query keeps larger rerank budget",
    "wide fanout query gets broader route budgets",
    "alias/code-name queries require source-of-truth alias expansion"
  ]
}
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
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
    },
    {
      "query": "Compare Beacon CRM Connector 3.14.0 3.14.1 Contoso",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "Compare Beacon CRM Contoso's security review Which one",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "Beacon CRM Connector 3.14.0",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "3.14.1 for Contoso's security review. Which one is acceptable",
      "mode": "hybrid",
      "top_k": 2000
    }
  ],
  "missing_goals": [],
  "followup_routes": [],
  "candidate_pool": 4303,
  "preselected": [
    "alias-customer-codenames",
    "esc-contoso",
    "acct-contoso",
    "adv-beacon-oauth-3771",
    "ticket-sec-1811",
    "rel-beacon-3-14-0",
    "rel-beacon-3-14-1"
  ],
  "rerank_candidates": 2400,
  "top_doc_ids": [
    "alias-customer-codenames",
    "esc-contoso",
    "acct-contoso",
    "adv-beacon-oauth-3771",
    "ticket-sec-1811",
    "rel-beacon-3-14-0",
    "rel-beacon-3-14-1",
    "approval-beacon-contoso-may06",
    "v3-approval-decoy-0076",
    "v3-approval-decoy-0676"
  ],
  "rewrite_needed": true,
  "rewrites": [
    "Compare Beacon CRM Connector 3.14.0 3.14.1 Contoso",
    "Compare Beacon CRM Contoso's security review Which one",
    "compare beacon crm connector 3.14.0 3.14.1 contoso s security review. one acceptable"
  ]
}
```

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

### sac-028 - missing_evidence_followup

Query: A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

Why selected: missing-evidence reflection generated targeted follow-up routes before final selection

Gold: QuartzBio Labs is a regulated life sciences customer asking for rerank cache namespace proof. AtlasSearch 4.9.0 provides Evidence Ledger and tenant-scoped rerank cache.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.2000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, esc-quartzbio, decoy-guide-001, decoy-guide-041 |
| hybrid | 0.2000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0143, esc-quartzbio, v3-namespace-decoy-0243 |
| fixed_enriched | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| generated | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| iterative_agentic | 0.8000 | 0 | esc-quartzbio, acct-quartzbio, ticket-sec-1899, adv-atlas-rerank-4520, rel-atlas-4-9-0 |
| generated_force_budget | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| reflective | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "hybrid",
      "top_k": 45
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "bm25",
      "top_k": 35
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "bm25",
      "top_k": 30
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 30
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "dense",
      "top_k": 30
    }
  ],
  "goals": [
    "account_or_escalation",
    "ticket_or_advisory",
    "release_note",
    "negative_evidence"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "negative/decision query checks exact and product-footprint evidence",
    "semantic evidence query adds dense route"
  ]
}
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "hybrid",
      "top_k": 45
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "bm25",
      "top_k": 35
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "bm25",
      "top_k": 30
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 30
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "dense",
      "top_k": 30
    },
    {
      "query": "A regulated customer cache namespace proof Which customer what release",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "regulated customer asks cache namespace proof. customer most likely asking release gives",
      "mode": "hybrid",
      "top_k": 2000
    }
  ],
  "missing_goals": [
    "release_note"
  ],
  "followup_routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? release notes fixed version fixes performance note",
      "mode": "bm25",
      "top_k": 160
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? release evidence feature approved",
      "mode": "hybrid",
      "top_k": 120
    }
  ],
  "candidate_pool": 2766,
  "preselected": [
    "esc-quartzbio",
    "acct-quartzbio",
    "ticket-sec-1899",
    "adv-atlas-rerank-4520",
    "rel-atlas-4-9-0",
    "rel-compass-1-19-3",
    "approval-quartzbio-namespace-proof"
  ],
  "rerank_candidates": 2400,
  "top_doc_ids": [
    "esc-quartzbio",
    "acct-quartzbio",
    "ticket-sec-1899",
    "adv-atlas-rerank-4520",
    "rel-atlas-4-9-0",
    "rel-compass-1-19-3",
    "approval-quartzbio-namespace-proof",
    "meet-quartzbio",
    "v3-namespace-decoy-0307",
    "v3-namespace-decoy-0087"
  ],
  "rewrite_needed": true,
  "rewrites": [
    "A regulated customer cache namespace proof Which customer what release",
    "regulated cust
```

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "hybrid",
      "top_k": 45
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "bm25",
      "top_k": 35
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "bm25",
      "top_k": 30
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 30
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "dense",
      "top_k": 30
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "negative/decision query checks exact and product-footprint evidence",
    "semantic evidence query adds dense route"
  ]
}
```

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
| iterative_agentic | 0.5000 | 0 | rel-compass-1-19-3, rel-atlas-4-8-2, policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014 |
| generated_force_budget | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144 |
| reflective | 0.5000 | 0 | policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144 |

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
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
  "goals": [
    "release_note",
    "policy"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "metric query preserves numeric lexical evidence"
  ]
}
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
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
    },
    {
      "query": "Code which latency number code generation execution",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "ceo search-as-code readout latency number primary including code generation execution-only",
      "mode": "hybrid",
      "top_k": 2000
    }
  ],
  "missing_goals": [],
  "followup_routes": [],
  "candidate_pool": 2616,
  "preselected": [
    "rel-compass-1-19-3",
    "rel-atlas-4-8-2",
    "policy-sac-latency-ledger-v3"
  ],
  "rerank_candidates": 2400,
  "top_doc_ids": [
    "rel-compass-1-19-3",
    "rel-atlas-4-8-2",
    "policy-sac-latency-ledger-v3",
    "v3-policy-decoy-0019",
    "v3-policy-decoy-0014",
    "v3-policy-decoy-0044",
    "v3-policy-decoy-0144",
    "v3-policy-decoy-0164",
    "v3-policy-decoy-0444",
    "v3-policy-decoy-0664"
  ],
  "rewrite_needed": true,
  "rewrites": [
    "Code which latency number code generation execution",
    "ceo search-as-code readout latency number primary including code generation execution-only",
    "for the ceo search-as-code readout which latency number is primary"
  ]
}
```

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
| iterative_agentic | 0.5000 | 0 | approval-atlas-northwind-final, policy-reflection-missing-evidence-v3, roadmap-rovo-sac, cluster-enterprise-memo-307, cluster-enterprise-memo-175 |
| generated_force_budget | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| reflective | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
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
  "goals": [
    "negative_evidence",
    "policy"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "negative/decision query checks exact and product-footprint evidence"
  ]
}
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
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
    },
    {
      "query": "only 18 25",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "A generated flow a thin-evidence enterprise query only 18 candidates What",
      "mode": "hybrid",
      "top_k": 2000
    }
  ],
  "missing_goals": [
    "policy"
  ],
  "followup_routes": [
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? final policy latency accounting ledger required metrics",
      "mode": "bm25",
      "top_k": 180
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? reflection missing evidence categories follow-up retrieval code",
      "mode": "hybrid",
      "top_k": 160
    }
  ],
  "candidate_pool": 3246,
  "preselected": [
    "approval-atlas-northwind-final"
  ],
  "rerank_candidates": 2400,
  "top_doc_ids": [
    "approval-atlas-northwind-final",
    "policy-reflection-missing-evidence-v3",
    "roadmap-rovo-sac",
    "cluster-enterprise-memo-307",
    "cluster-enterprise-memo-175",
    "cluster-enterprise-memo-223",
    "cluster-enterprise-memo-475",
    "cluster-enterprise-memo-115",
    "cluster-enterprise-memo-259",
    "cluster-enterprise-memo-319"
  ],
  "rewrite_needed": true,
  "rewrites": [
    "only 18 25",
    "A generated flow a thin-evidence enterprise query only 18 candidates What",
    "generated flow thin-evidence enterprise query finds only 18 candidates. should agent do"
  ]
}
```

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
