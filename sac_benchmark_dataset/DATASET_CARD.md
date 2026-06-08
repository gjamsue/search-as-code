# Dataset Card: Search-as-Code Codegen Benchmark v2

## Summary

This dataset is a synthetic enterprise benchmark for evaluating Search-as-Code
code generation. It is designed to compare:

- fixed enriched retrieval
- multi-turn tool-calling agents
- one-shot generated retrieval code
- reflective generated retrieval code
- budget and oracle ablations

The dataset is intentionally not a generic retrieval benchmark. It targets the
cases where Search-as-Code should have a structural advantage: fanout, joins,
filters, exact identifiers, evidence sufficiency, negative evidence, and rerank
budget control.

## Current Size

- Documents: 2,499
- Core labeled or near-labeled documents: 57
- Structured hard distractors: 2,442
- Tasks: 36
- Splits: train 7, dev 7, test 22
- Tasks with hard negatives: 36
- Hard-negative labels: 200
- Reflection-required tasks: 7
- BEIR export: included; qrels contain positive evidence only
- Separate hard-negative export: included
- Content audit report: included

## Document Types

- Core / near-labeled evidence docs: 57
- Baseline structured distractors: 486
- Incident topic clusters: 360
- Customer activity clusters: 480
- Product knowledge clusters: 576
- Enterprise background clusters: 540
- Largest distractor types: release 264, guide 240, security advisory 168, meeting note 146, security ticket 132

Version 2 is intentionally a thicker enterprise index. A single topic can now
have dozens of similar artifacts: draft advisories, rollout notes, duplicate
tickets, meeting summaries, emails, approvals, postmortems, risk dashboards,
KB docs, policy drafts, and stale customer snapshots.

## Task Coverage

The task set includes:

- security fanout and joins
- customer renewal risk joins
- release-to-fix mapping
- exact identifier lookup
- regulated customer filtering
- negative evidence checks
- budget-control cases
- tool-calling vs. codegen comparison cases
- reflection-required cases
- wide fanout aggregation
- multi-hop reasoning
- comparative analysis

Operation coverage from validation:

- join: 26 tasks
- metadata_filter: 18 tasks
- bm25_exact: 16 tasks
- aggregate: 12 tasks
- entity_linking: 12 tasks
- fanout_search: 9 tasks
- negative_evidence_check: 5 tasks
- query_understanding: 4 tasks
- evidence_reflection: 3 tasks
- exact_version_compare: 3 tasks

## Example Tasks

### Fanout + Join

```text
For Riverline Logistics, identify every open security exception, its CVE,
fixed version, and owner.
```

Required behavior:

- find Riverline account and escalation docs
- identify two product blockers
- join AtlasSearch and Meridian Sync advisories
- map each CVE to fixed version and owner
- avoid nearby wrong releases

### Exact Identifier Search

```text
SEC-1899 is blocking which customers, which CVE does it track, and what release
should they use?
```

Required behavior:

- preserve exact ticket ID `SEC-1899`
- map to `CVE-2026-4520`
- find customer account docs
- map release to AtlasSearch 4.9.0

### Negative Evidence

```text
Does NovaFoods need any ForgeDeploy remediation for the June security rollout?
```

Required behavior:

- search product footprint
- verify NovaFoods has no ForgeDeploy deployment
- answer "no" with citation instead of continuing to search indefinitely

### Reflection Required

```text
If the first search only finds AtlasSearch SAML docs, what additional route
should recover Riverline's second blocker?
```

Required behavior:

- detect missing evidence
- generate a follow-up route for Meridian Sync / SEC-1775 / CVE-2026-2899
- merge the new evidence

## Quality Controls

The generator and validator enforce:

- unique document and task IDs
- all evidence docs exist
- hard negatives do not overlap evidence docs
- all tasks include hard negatives
- structured distractor docs cannot be used as positive evidence
- corpus contains at least 500 documents
- corpus contains at least 450 structured hard distractors
- required distractor types are present: releases, advisories, tickets, account
  briefs, escalation logs, meeting notes, and guides
- BEIR qrels contain only positive evidence rows
- hard negatives are exported separately and match task labels
- every task has at least two evidence docs
- every task has required operations
- every task has ideal search routes
- BEIR qrels are consistent with task evidence
- test split contains at least 18 tasks
- at least 8 task categories are represented
- key operations are covered: fanout, join, metadata filter, BM25 exact,
  reflection, negative evidence, and candidate pruning

The audit script additionally reports answer-field literal coverage, route-mode
coverage, evidence-count distribution, hard-negative-count distribution, and
qrels cleanliness. The current audit report has zero errors and zero warnings.

## Intended Use

Use this dataset to answer:

1. Does generated retrieval code outperform a strong fixed pipeline?
2. Does generated retrieval code outperform a multi-turn tool-calling agent with
   the same tools?
3. Does reflection improve only selected hard tasks, or does it add unnecessary
   cost?
4. Does Search-as-Code reduce token cost by moving intermediate control into a
   sandbox?
5. Which failures are due to planning, search recall, reranking, codegen errors,
   or evidence synthesis?

## Not Intended Use

Do not use this dataset as proof that a system is generally better at enterprise
search. It is a targeted stress test for Search-as-Code control behavior. It is
synthetic and should eventually be complemented with real internal tasks.

## Recommended Next Benchmark Step

Implement four runners over the same tools:

1. Fixed enriched retrieval.
2. Multi-turn tool-calling agent.
3. One-shot generated Search-as-Code.
4. Reflective Search-as-Code.

Report:

- answer field accuracy
- citation accuracy
- retrieval recall@k and nDCG@k
- latency including codegen
- token cost
- tool calls
- search calls
- rerank pairs
- invalid code rate
- timeout rate
- reflection trigger precision
