# Search-as-Code Dataset Benchmark Report

Dataset: `sac-codegen-v3`
Split: `test`
Documents: `6010`
Tasks: `31`
Primary metric: `Recall@10`
Candidate opportunity: rerank systems retrieve up to `2400` candidates per query before final top-10 output.
Quality score: `100 * (0.55*Recall@10 + 0.25*nDCG@10 + 0.15*MRR@10 + 0.05*AllEvidence@10 - 0.20*HardNegativeIntrusion@10)`.
Latency score: fastest architecture-system mean latency divided by system mean latency, scaled to 100.

## Readout

Iterative agentic Search-as-Code is the first flow that clearly separates from fixed search: Recall@10 `0.4712` vs one-shot generated `0.1857` and fixed enriched `0.1857` (delta vs fixed `0.2855`, delta vs one-shot `0.2855`, delta vs agentic fixed-flow `0.2018`). It pays modestly more search control cost: `7.16` search calls/query and `3362.5` ms mean latency. Hard-negative hit-rate delta is `0.0000` and intrusion-rate delta is `0.0033`, so the next quality gate is final context/answer selection.

## Architecture Comparison

| Architecture | System | Quality score | Latency score | Recall@10 | Hard-neg hit@10 | Mean latency | Search calls | Flow shape |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Fixed flow baseline | `fixed_understanding_rewrite_hybrid_rerank` | 23.2 | 100.0 | 0.1857 | 0.2258 | 3231.2 ms | 3.97 | Fixed query understanding + rewrite + hybrid retrieval + rerank |
| Generated flow | `generated_search_as_code` | 23.2 | 99.0 | 0.1857 | 0.2258 | 3263.1 ms | 6.97 | One-shot generated route plan with SDK parameters |
| Agentic fixed-flow calls | `agentic_fixed_flow_iterative` | 33.1 | 81.0 | 0.2694 | 0.1613 | 3991.5 ms | 12.71 | Agent iteratively calls the same fixed flow with new queries |
| Agentic codegen | `generated_iterative_agentic_search_as_code` | 47.1 | 96.1 | 0.4712 | 0.2258 | 3362.5 ms | 7.16 | Generated code iterates with evidence-coverage reflection |

## Recall@10 Leaderboard

| System | Recall@10 | Hard-neg hit@10 | Mean latency ms | Candidate pool | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|
| generated_iterative_agentic_search_as_code | 0.4712 | 0.2258 | 3362.5 | 3341.9 | 7.16 | 2400.0 |
| agentic_fixed_flow_iterative | 0.2694 | 0.1613 | 3991.5 | 57.9 | 12.71 | 2687.4 |
| fixed_bm25 | 0.2350 | 0.2258 | 13.3 | 10.0 | 1.00 | 0.0 |
| fixed_hybrid | 0.2286 | 0.0645 | 19.6 | 10.0 | 1.00 | 0.0 |
| fixed_hybrid_rerank | 0.1857 | 0.2258 | 3211.5 | 2400.0 | 1.00 | 2400.0 |
| fixed_understanding_rewrite_hybrid_rerank | 0.1857 | 0.2258 | 3231.2 | 3659.9 | 3.97 | 2400.0 |
| generated_reflective_search_as_code | 0.1857 | 0.2258 | 3256.6 | 3340.1 | 6.97 | 2400.0 |
| generated_search_as_code_force_budget | 0.1857 | 0.2258 | 3258.4 | 3340.1 | 6.97 | 2400.0 |
| generated_search_as_code | 0.1857 | 0.2258 | 3263.1 | 3340.1 | 6.97 | 2400.0 |
| fixed_hybrid_rerank_small_budget | 0.1714 | 0.1935 | 598.7 | 400.0 | 1.00 | 400.0 |
| fixed_semantic_dense | 0.0932 | 0.0323 | 16.6 | 10.0 | 1.00 | 0.0 |

## Key Findings

- Top Recall@10 system is `generated_iterative_agentic_search_as_code`: Recall@10 `0.4712`.
- Iterative agentic Search-as-Code improves Recall@10 to `0.4712` vs one-shot generated `0.1857` and fixed enriched `0.1857`.
- The gain comes from evidence-coverage reflection: it checks missing categories such as alias, account/escalation, ticket/advisory, release note, source authority, and policy before final top-10.
- Cost is only modestly higher than one-shot: `3362.5` ms vs `3263.1` ms, with `7.16` vs `6.97` search calls/query.
- Hard-negative hit rate is `0.2258` vs fixed enriched `0.2258`; intrusion rate is `0.0323` vs `0.0290`, so answer-level filtering still matters.
- Agentic fixed-flow calls reach Recall@10 `0.2694` with `12.71` search calls/query; this isolates the value of iteration when the agent cannot control the lower-level search stack.
- One-shot generated Search-as-Code exposes route-level SDK parameters, but still lacks evidence-coverage reflection; Recall@10 is `0.1857` vs fixed enriched `0.1857`.
- Candidate opportunity is large: fixed enriched sees `3659.9` candidates/query and generated sees `3340.1` candidates/query before final top-10.
- BM25 remains a serious baseline because it scores the full corpus directly: Recall@10 `0.2350` at `13.3` ms; dense-only Recall@10 is `0.0932`.
- Forced budget expansion does not change hard-negative hit rate (`0.2258`) and leaves Recall@10 at `0.1857`; more retrieval is not automatically better after reranking.
- Reflective mode triggered second-pass code on `0` / `31` tasks, so it currently adds no quality gain. The reflection policy should use missing-evidence checks, not only thin candidate pools.

## Selected Examples

### sac-028 - iterative_agentic_win

Query: A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

Why selected: iterative agentic Search-as-Code recovered evidence that one-shot and fixed flows missed

Gold: QuartzBio Labs is a regulated life sciences customer asking for rerank cache namespace proof. AtlasSearch 4.9.0 provides Evidence Ledger and tenant-scoped rerank cache.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.2000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, esc-quartzbio, decoy-guide-001, decoy-guide-041 |
| hybrid | 0.2000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0143, esc-quartzbio, v3-namespace-decoy-0243 |
| fixed_enriched | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| generated | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| agentic_fixed_flow | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| iterative_agentic | 0.8000 | 0 | esc-quartzbio, acct-quartzbio, ticket-sec-1899, adv-atlas-rerank-4520, rel-atlas-4-9-0 |
| generated_force_budget | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |
| reflective | 0.0000 | 0 | approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0307, v3-namespace-decoy-0087, v3-namespace-decoy-0067 |

Agentic fixed-flow plan:

```json
{
  "strategy": "agentic_fixed_flow_multi_call",
  "initial_queries": [
    "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
    "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
    "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence"
  ],
  "goals": [
    "account_or_escalation",
    "ticket_or_advisory",
    "release_note",
    "negative_evidence"
  ],
  "max_reflection_rounds": 2
}
```

Agentic fixed-flow reflection:

```json
{
  "tool_calls": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "returned": 20
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? account brief escalation current blocker",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? products in production renewal risk technical owner",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? vendor advisory internal security ticket CVE SEC",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? security owner fixed version advisory ticket",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? release notes fixed version fixes performance note",
      "returned": 20
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? release evidence feature approved",
      "returned": 20
    }
  ],
  "reflection_rounds": [
    {
      "round": 1,
      "missing_goals": [
        "account_or_escalation",
        "ticket_or_advisory",
        "release_note"
      ],
      "followup_queries": [
        "A regula
```

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "hybrid",
      "top_k": 140,
      "bm25_weight": 0.65,
      "include_doc_types": [
        "account_brief",
        "escalation",
        "war_room_roster",
        "security_ticket"
      ],
      "should_terms": [
        "current blocker",
        "renewal",
        "owner"
      ]
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "bm25",
      "top_k": 90
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "dense",
      "top_k": 90,
      "include_doc_types": [
        "release",
        "approval_ledger",
        "meeting_note",
        "escalation"
      ],
      "should_terms": [
        "tenant-scoped",
        "namespace",
        "evidence ledger",
        "proof"
      ]
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
    "negative/decision query constrains retrieval to footprint and exclusion evidence",
    "semantic e
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "hybrid",
      "top_k": 140,
      "bm25_weight": 0.65,
      "include_doc_types": [
        "account_brief",
        "escalation",
        "war_room_roster",
        "security_ticket"
      ],
      "should_terms": [
        "current blocker",
        "renewal",
        "owner"
      ]
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "bm25",
      "top_k": 90
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "dense",
      "top_k": 90,
      "include_doc_types": [
        "release",
        "approval_ledger",
        "meeting_note",
        "escalation"
      ],
      "should_terms": [
        "tenant-scoped",
        "namespace",
        "evidence ledger",
        "proof"
      ]
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
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer i
```

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "hybrid",
      "top_k": 140,
      "bm25_weight": 0.65,
      "include_doc_types": [
        "account_brief",
        "escalation",
        "war_room_roster",
        "security_ticket"
      ],
      "should_terms": [
        "current blocker",
        "renewal",
        "owner"
      ]
    },
    {
      "query": "regulated customer asks cache namespace proof. customer is most likely asking release gives evidence feature should cited",
      "mode": "bm25",
      "top_k": 90
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    },
    {
      "query": "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
      "mode": "dense",
      "top_k": 90,
      "include_doc_types": [
        "release",
        "approval_ledger",
        "meeting_note",
        "escalation"
      ],
      "should_terms": [
        "tenant-scoped",
        "namespace",
        "evidence ledger",
        "proof"
      ]
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "negative/decision query constrains retrieval to footprint and exclusion evidence",
    "semantic evidence query adds dense route"
  ]
}
```

### sac-038 - agentic_codegen_vs_fixed_tool

Query: For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?

Why selected: agentic codegen outperformed an agent that could only call the fixed flow repeatedly

Gold: CT-R means Contoso Retail. The customer-citable version after final approval is Beacon CRM Connector 3.14.1 because it fixes CVE-2026-3771 under SEC-1811. Beacon CRM Connector 3.14.0 must be rejected because it only added diagnostics and did not fix the OAuth refresh-token issue.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.2857 | 1 | approval-beacon-contoso-may06, meet-contoso, esc-contoso, v3-approval-decoy-0011, v3-approval-decoy-0041 |
| hybrid | 0.1429 | 0 | approval-beacon-contoso-may06, v3-approval-decoy-0791, v3-approval-decoy-0491, v3-approval-decoy-0431, v3-approval-decoy-0881 |
| fixed_enriched | 0.1429 | 1 | approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241 |
| generated | 0.1429 | 1 | approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241 |
| agentic_fixed_flow | 0.1429 | 1 | approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241 |
| iterative_agentic | 0.8571 | 0 | alias-customer-codenames, esc-contoso, esc-urbannest, adv-beacon-oauth-3771, ticket-sec-1811 |
| generated_force_budget | 0.1429 | 1 | approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241 |
| reflective | 0.1429 | 1 | approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241 |

Agentic fixed-flow plan:

```json
{
  "strategy": "agentic_fixed_flow_multi_call",
  "initial_queries": [
    "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
    "ct-r s oauth review beacon version is customer-citable after final approval version must rejected"
  ],
  "goals": [
    "alias_registry",
    "account_or_escalation",
    "ticket_or_advisory",
    "release_note",
    "source_authority"
  ],
  "max_reflection_rounds": 2
}
```

Agentic fixed-flow reflection:

```json
{
  "tool_calls": [
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "returned": 20
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "returned": 20
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? alias registry source-of-truth",
      "returned": 20
    },
    {
      "query": "ct-r customer owner alias registry",
      "returned": 20
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? account brief escalation current blocker",
      "returned": 20
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? products in production renewal risk technical owner",
      "returned": 20
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? vendor advisory internal security ticket CVE SEC",
      "returned": 20
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? security owner fixed version advisory ticket",
      "returned": 20
    }
  ],
  "reflection_rounds": [
    {
      "round": 1,
      "missing_goals": [
        "alias_registry",
        "account_or_escalation",
        "ticket_or_advisory",
        "release_note",
        "source_authority"
      ],
      "followup_queries": [
        "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? alias registry source-of-truth",
        "ct-r customer owner alias registry",
        "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? account brief escalation current blocker"
      ],
      "candidate_pool_before": 20
    },
    {
      "round": 2,
      "missing_goals": [
        "alias_registry",
        "account_or_escalation",
        "ticket_or_advisory",
        "release_note",
        "source
```

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "mode": "hybrid",
      "top_k": 140,
      "bm25_weight": 0.65,
      "include_doc_types": [
        "account_brief",
        "escalation",
        "war_room_roster",
        "security_ticket"
      ],
      "should_terms": [
        "current blocker",
        "renewal",
        "owner"
      ]
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "mode": "bm25",
      "top_k": 90
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 120,
      "bm25_weight": 0.72,
      "include_doc_types": [
        "approval_ledger",
        "authority_matrix",
        "war_room_roster",
        "policy"
      ],
      "should_terms": [
        "final approval",
        "source-of-truth",
        "approved citation",
        "supersedes"
      ],
      "exclude_terms": [
        "draft",
        "stale",
        "not final"
      ]
    }
  ],
  "goals": [
    "alias_registry",
    "account_or_escalation",
    "ticket_or_advisory",
    "release_note",
    "source_authority"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "authority query uses source-of-truth metadata filters",
    "alias/code-name queries require source-of-truth alias expansion",
    "authority-sensitive queries require final/source-of-truth evidence"
  ]
}
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "mode": "hybrid",
      "top_k": 140,
      "bm25_weight": 0.65,
      "include_doc_types": [
        "account_brief",
        "escalation",
        "war_room_roster",
        "security_ticket"
      ],
      "should_terms": [
        "current blocker",
        "renewal",
        "owner"
      ]
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "mode": "bm25",
      "top_k": 90
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 120,
      "bm25_weight": 0.72,
      "include_doc_types": [
        "approval_ledger",
        "authority_matrix",
        "war_room_roster",
        "policy"
      ],
      "should_terms": [
        "final approval",
        "source-of-truth",
        "approved citation",
        "supersedes"
      ],
      "exclude_terms": [
        "draft",
        "stale",
        "not final"
      ]
    },
    {
      "query": "Beacon",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "CT-R's OAuth review which Beacon version final approval",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 2000
    }
  ],
  "missing_goals": [
    "alias_registry"
  ],
  "followup_routes": [
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected? alias registry source-of-truth",
      "mode": "bm25",
      "top_k": 120
    },
    {
      "query": "ct-r customer owner alias registry",
      "mode": "hybrid",
      "top_k": 120
    }
  ],
  "candidate_pool": 3151,
  "preselected": [
    "alias-customer-codenames",
    "esc-contoso",
    "esc-urbannest",
    "adv-beacon-oauth-3771",
    "ticket-sec-1811",
    "rel-beacon-3-14-0",
    "rel-beacon-3-14-1",
    "warroom-r7-june-critical-roster"
  ],
  "rerank_candidates": 2400,
  "top_doc_ids": [
    "alias-customer-codenames",
    "esc-contoso",
    "esc-urbannest",
    "adv-beacon-oauth-3771",
    "ticket-sec-1811",
    "rel-beacon-3-14-0",
    "rel-beacon-3-14-1",
    "warroom-r7-june-critical-roster",
    "approval-beacon-contoso-may06",
    "v3-approval-decoy-0541"
  ],
  "rewrite_needed": true,
  "rewri
```

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "mode": "hybrid",
      "top_k": 140,
      "bm25_weight": 0.65,
      "include_doc_types": [
        "account_brief",
        "escalation",
        "war_room_roster",
        "security_ticket"
      ],
      "should_terms": [
        "current blocker",
        "renewal",
        "owner"
      ]
    },
    {
      "query": "ct-r s oauth review beacon version is customer-citable after final approval version must rejected",
      "mode": "bm25",
      "top_k": 90
    },
    {
      "query": "For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?",
      "mode": "hybrid",
      "top_k": 120,
      "bm25_weight": 0.72,
      "include_doc_types": [
        "approval_ledger",
        "authority_matrix",
        "war_room_roster",
        "policy"
      ],
      "should_terms": [
        "final approval",
        "source-of-truth",
        "approved citation",
        "supersedes"
      ],
      "exclude_terms": [
        "draft",
        "stale",
        "not final"
      ]
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "wide fanout query gets broader route budgets",
    "authority query uses source-of-truth metadata filters"
  ]
}
```

### sac-016 - missing_evidence_followup

Query: A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?

Why selected: missing-evidence reflection generated targeted follow-up routes before final selection

Gold: When the condition is candidate pool below 25, it should generate follow-up retrieval code with a larger route budget rather than force all rerank candidates. In this dataset, the policy is to reflect on thin evidence, add targeted hybrid/BM25/dense routes, merge new candidates, and rerank only if new evidence appears.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.0000 | 0 | rollout-riverline-second-blocker-ledger, v3-reflection-decoy-0005, v3-reflection-decoy-0010, v3-reflection-decoy-0015, v3-reflection-decoy-0020 |
| hybrid | 0.0000 | 0 | v3-reflection-decoy-0425, v3-reflection-decoy-0325, v3-reflection-decoy-0225, v3-reflection-decoy-0405, v3-reflection-decoy-0395 |
| fixed_enriched | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| generated | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| agentic_fixed_flow | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| iterative_agentic | 0.5000 | 0 | approval-atlas-northwind-final, policy-reflection-missing-evidence-v3, roadmap-rovo-sac, cluster-enterprise-memo-307, cluster-enterprise-memo-175 |
| generated_force_budget | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |
| reflective | 0.0000 | 0 | v3-reflection-decoy-0075, v3-reflection-decoy-0275, v3-reflection-decoy-0215, v3-reflection-decoy-0025, v3-reflection-decoy-0225 |

Agentic fixed-flow plan:

```json
{
  "strategy": "agentic_fixed_flow_multi_call",
  "initial_queries": [
    "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
    "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? product footprint negative evidence"
  ],
  "goals": [
    "negative_evidence",
    "policy"
  ],
  "max_reflection_rounds": 2
}
```

Agentic fixed-flow reflection:

```json
{
  "tool_calls": [
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "returned": 20
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? product footprint negative evidence",
      "returned": 20
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? negative evidence product footprint explicit exclusions",
      "returned": 20
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? should not include rejected not sufficient",
      "returned": 20
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? final policy latency accounting ledger required metrics",
      "returned": 20
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? reflection missing evidence categories follow-up retrieval code",
      "returned": 20
    }
  ],
  "reflection_rounds": [
    {
      "round": 1,
      "missing_goals": [
        "negative_evidence",
        "policy"
      ],
      "followup_queries": [
        "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? negative evidence product footprint explicit exclusions",
        "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? should not include rejected not sufficient",
        "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? final policy latency accounting ledger required metrics"
      ],
      "candidate_pool_before": 25
    },
    {
      "round": 2,
      "missing_goals": [
        "negative_evidence",
        "policy"
      ],
      "followup_queries": [
        "A generated flow for a thin-evid
```

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    }
  ],
  "goals": [
    "negative_evidence",
    "policy"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "negative/decision query constrains retrieval to footprint and exclusion evidence"
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
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
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
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
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
  "candidate_pool": 3632,
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
  "rewrites":
```

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "negative/decision query constrains retrieval to footprint and exclusion evidence"
  ]
}
```

### sac-043 - dynamic_flow_shape

Query: A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?

Why selected: generated program chose multiple route types and budgets on a high-recall query

Gold: It should generate follow-up retrieval code. The v3 reflection policy says missing required evidence categories, such as an approval ledger, should trigger targeted follow-up retrieval even when the raw candidate pool is 900 and therefore large.

| Method | Recall@10 | Hard-neg count@10 | Top docs |
|---|---:|---:|---|
| bm25 | 0.5000 | 1 | policy-reflection-missing-evidence-v3, negative-forgedeploy-novafoods, roadmap-rovo-sac, v3-reflection-decoy-0002, v3-reflection-decoy-0007 |
| hybrid | 0.5000 | 0 | policy-reflection-missing-evidence-v3, v3-reflection-decoy-0192, v3-reflection-decoy-0182, v3-reflection-decoy-0482, v3-reflection-decoy-0282 |
| fixed_enriched | 0.5000 | 1 | policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007 |
| generated | 0.5000 | 1 | policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007 |
| agentic_fixed_flow | 0.5000 | 1 | policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007 |
| iterative_agentic | 0.5000 | 1 | warroom-r7-june-critical-roster, approval-atlas-northwind-final, policy-sac-latency-ledger-v3, policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012 |
| generated_force_budget | 0.5000 | 1 | policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007 |
| reflective | 0.5000 | 1 | policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007 |

Agentic fixed-flow plan:

```json
{
  "strategy": "agentic_fixed_flow_multi_call",
  "initial_queries": [
    "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
    "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? product footprint negative evidence"
  ],
  "goals": [
    "source_authority",
    "negative_evidence",
    "policy"
  ],
  "max_reflection_rounds": 2
}
```

Agentic fixed-flow reflection:

```json
{
  "tool_calls": [
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? product footprint negative evidence",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? final approval ledger source authority source-of-truth",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? final roster approved citation supersedes draft",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? negative evidence product footprint explicit exclusions",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? should not include rejected not sufficient",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? final policy latency accounting ledger required metrics",
      "returned": 20
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? reflection missing evidence categories follow-up retrieval code",
      "returned": 20
    }
  ],
  "reflection_rounds": [
    {
      "round": 1,
      "missing_goals": [
        "source_authority",
        "negative_evidence",
        "policy"
      ],
      "followup_queries": [
        "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? final approval ledger source authority source-of-truth",
        "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-u
```

Iterative agentic plan:

```json
{
  "strategy": "iterative_agentic_evidence_coverage",
  "initial_routes": [
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 120,
      "bm25_weight": 0.72,
      "include_doc_types": [
        "approval_ledger",
        "authority_matrix",
        "war_room_roster",
        "policy"
      ],
      "should_terms": [
        "final approval",
        "source-of-truth",
        "approved citation",
        "supersedes"
      ],
      "exclude_terms": [
        "draft",
        "stale",
        "not final"
      ]
    }
  ],
  "goals": [
    "source_authority",
    "negative_evidence",
    "policy"
  ],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "negative/decision query constrains retrieval to footprint and exclusion evidence",
    "authority query uses source-of-truth metadata filters",
    "authority-sensitive queries require final/source-of-truth evidence"
  ]
}
```

Iterative evidence reflection:

```json
{
  "initial_routes": [
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 120,
      "bm25_weight": 0.72,
      "include_doc_types": [
        "approval_ledger",
        "authority_matrix",
        "war_room_roster",
        "policy"
      ],
      "should_terms": [
        "final approval",
        "source-of-truth",
        "approved citation",
        "supersedes"
      ],
      "exclude_terms": [
        "draft",
        "stale",
        "not final"
      ]
    },
    {
      "query": "A generated query 900 candidates no approval ledger policy",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "generated query already found 900 candidates but no approval ledger. according policy",
      "mode": "hybrid",
      "top_k": 2000
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 2000
    }
  ],
  "missing_goals": [],
  "followup_routes": [],
  "candidate_pool": 2887,
  "preselected": [
    "warroom-r7-june-critical-roster",
    "approval-atlas-northwind-final",
    "policy-sac-latency-ledger-v3"
  ],
  "rerank_candidates": 2400,
  "top_doc_ids": [
    "warroom-r7-june-critical-roster",
    "approval-atlas-northwind-final",
    "policy-sac-latency-ledger-v3",
    "policy-reflection-missing-evidence-v3",
    "v3-reflection-decoy-0012",
    "v3-reflection-decoy-0017",
    "v3-reflec
```

Generated plan:

```json
{
  "strategy": "sac_enterprise_dynamic_routes",
  "routes": [
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 2000,
      "bm25_weight": 0.55,
      "exclude_terms": [
        "scratchpad",
        "copied dashboard",
        "wrong-customer"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "bm25",
      "top_k": 90,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery",
        "security_advisory",
        "release",
        "approval_ledger"
      ],
      "should_terms": [
        "no",
        "not",
        "explicit exclusions",
        "only active product",
        "rejected"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code? product footprint negative evidence",
      "mode": "hybrid",
      "top_k": 90,
      "bm25_weight": 0.7,
      "include_doc_types": [
        "product_footprint",
        "account_brief",
        "sales_discovery"
      ],
      "should_terms": [
        "not",
        "no",
        "exclude",
        "does not"
      ]
    },
    {
      "query": "A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?",
      "mode": "hybrid",
      "top_k": 120,
      "bm25_weight": 0.72,
      "include_doc_types": [
        "approval_ledger",
        "authority_matrix",
        "war_room_roster",
        "policy"
      ],
      "should_terms": [
        "final approval",
        "source-of-truth",
        "approved citation",
        "supersedes"
      ],
      "exclude_terms": [
        "draft",
        "stale",
        "not final"
      ]
    }
  ],
  "exact_terms": [],
  "rationale": [
    "start with hybrid retrieval over the full query",
    "negative/decision query constrains retrieval to footprint and exclusion evidence",
    "authority query uses source-of-truth metadata filters"
  ]
}
```


## Method Notes

- Code generation latency here is local deterministic generation time, not a hosted LLM call.
- The benchmark still reports generation time separately in JSON, so a real model latency can be added as a sensitivity analysis.
- Dataset qrels contain positive evidence only; hard-negative labels are evaluated separately.
