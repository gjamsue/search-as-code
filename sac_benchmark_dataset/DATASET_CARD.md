# Dataset Card: Search-as-Code Codegen Benchmark v3

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
filters, exact identifiers, alias resolution, source authority, evidence
sufficiency, negative evidence, and rerank budget control.

## Current Size

- Documents: 6,010
- Core/source-of-truth or near-labeled documents: 68
- Structured hard distractors: 5,942
- Tasks: 48
- Splits: train 8, dev 9, test 31
- Tasks with hard negatives: 48
- Hard-negative labels: 266
- Reflection-required tasks: 9
- BEIR export: included; qrels contain positive evidence only
- Separate hard-negative export: included
- Content audit report: included

## Document Types

- Core / source-of-truth / near-labeled evidence docs: 68
- Baseline structured distractors: 486
- Incident topic clusters: 360
- Customer activity clusters: 480
- Product knowledge clusters: 576
- Enterprise background clusters: 540
- v3 alias/code-name decoys: 480
- v3 policy/reflection decoys: 1,240
- v3 approval/war-room/namespace decoys: 1,780
- Largest distractor types: dashboard 920, meeting note 636, draft policy 530, Slack thread 470, review note 400

Version 3 is intentionally a thicker enterprise index. A single topic can now
have hundreds of similar artifacts: draft advisories, rollout notes, duplicate
tickets, meeting summaries, emails, approvals, postmortems, risk dashboards,
KB docs, policy drafts, stale customer snapshots, ambiguous aliases, approval-like
wrong-version ledgers, and policy near-duplicates.

## Task Coverage

The task set includes:

- security fanout and joins
- alias and code-name resolution
- source-authority disambiguation
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

- join: 32 tasks
- metadata_filter: 21 tasks
- bm25_exact: 20 tasks
- aggregate: 14 tasks
- entity_linking: 13 tasks
- fanout_search: 9 tasks
- alias_resolution: 8 tasks
- source_authority_filter: 7 tasks
- negative_evidence_check: 6 tasks
- query_understanding: 5 tasks
- evidence_reflection: 4 tasks
- exact_version_compare: 6 tasks

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
- corpus contains at least 5,000 documents
- corpus contains at least 4,500 structured hard distractors
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
