# Search-as-Code Codegen Benchmark Dataset

This is a custom benchmark dataset for evaluating Search-as-Code systems against
fixed retrieval pipelines and multi-turn tool-calling agents.

The dataset is synthetic, but it is designed to look like realistic enterprise
search work: customer account notes, support escalations, release notes,
security advisories, internal tickets, runbooks, and evaluation policy docs.
The current generated corpus contains 2,499 documents: 57 core labeled or
near-labeled documents plus 2,442 structured hard distractors. Version 2 adds
same-topic incident, customer, product, and enterprise-background clusters so
one topic has many plausible but non-authoritative artifacts.

## Why This Dataset Exists

Generic retrieval benchmarks are useful, but they do not isolate the expected
advantage of Search-as-Code. Search-as-Code should win when the system needs to:

- fan out across many entities
- join evidence across sources
- preserve exact identifiers such as CVEs, ticket IDs, versions, and customer names
- filter by metadata such as date, severity, vertical, product, owner, and renewal date
- control rerank budget
- reflect when the first evidence pool is thin
- answer with negative evidence instead of over-claiming

This dataset is built around those behaviors.

## Files

Generated files:

- `data/corpus.jsonl`: rich document corpus
- `data/tasks.jsonl`: task records with gold answers, evidence, expected ops, and expected flow
- `data/hard_negatives.jsonl`: task-level hard-negative labels for intrusion metrics
- `data/manifest.json`: dataset summary
- `data/quality_report.json`: content-level audit report
- `data/beir/corpus.jsonl`: BEIR-style corpus export
- `data/beir/queries.jsonl`: BEIR-style query export
- `data/beir/qrels/train.tsv`
- `data/beir/qrels/dev.tsv`
- `data/beir/qrels/test.tsv`
- `data/beir/hard_negatives/train.tsv`
- `data/beir/hard_negatives/dev.tsv`
- `data/beir/hard_negatives/test.tsv`

Source files:

- `generate_dataset.py`: deterministic dataset generator
- `validate_dataset.py`: schema and consistency validator
- `audit_dataset.py`: content-level audit and quality-report generator

## Current Size

- Documents: 2,499
- Structured hard distractors: 2,442
- Tasks: 36
- Splits: train 7, dev 7, test 22
- Tasks with hard negatives: 36
- Hard-negative labels: 200
- Reflection-required tasks: 7
- BEIR export: included

The distractor corpus is intentionally larger than the labeled evidence set.
It includes nearby versions, close CVEs and ticket IDs, similar customer names,
similar renewal-risk records, and generic policy docs that reuse the same search
vocabulary without containing the gold answer. It also includes topic clusters:
draft advisories, duplicate tickets, stale renewal notes, customer emails,
risk dashboards, rollout notes, migration docs, KB articles, and policy drafts
that reuse the same customer/product/CVE vocabulary.

BEIR qrels contain positive evidence only. Hard negatives are exported
separately so standard retrieval metrics and hard-negative intrusion metrics do
not share one file with mixed semantics.

## Schema

Each document:

```json
{
  "doc_id": "acct-northwind",
  "title": "Northwind Health account brief",
  "text": "...",
  "metadata": {
    "dataset_version": "sac-codegen-v2",
    "source": "crm",
    "doc_type": "account_brief",
    "customer": "Northwind Health",
    "products": ["AtlasSearch", "Rovo Chat"],
    "risk": "red"
  }
}
```

Each task:

```json
{
  "task_id": "sac-001",
  "split": "test",
  "category": "security_fanout_join",
  "difficulty": "hard",
  "query": "For Northwind Health, which critical vulnerabilities affect products they run...",
  "gold_answer": "...",
  "answer_fields": {
    "customer": "Northwind Health",
    "cve": "CVE-2026-4102",
    "fixed_version": "4.8.2"
  },
  "evidence_doc_ids": ["acct-northwind", "adv-atlas-saml-4102"],
  "hard_negative_doc_ids": ["rel-atlas-4-8-1"],
  "required_operations": ["fanout_search", "metadata_filter", "join", "aggregate", "rerank"],
  "expected_flow": {
    "should_reflect": false,
    "ideal_search_routes": [
      {"query": "Northwind Health AtlasSearch CVE critical", "mode": "hybrid", "top_k": 12}
    ],
    "rerank_policy": "rerank only merged candidates that can support answer fields"
  }
}
```

## Task Categories

- `security_fanout_join`: connect customers, products, CVEs, tickets, releases, and owners
- `customer_risk_join`: aggregate renewal risks and next actions across accounts
- `release_fix_mapping`: map blocker to release, fix, owner, and performance note
- `exact_identifier_lookup`: preserve and search exact CVEs, tickets, versions, and IDs
- `regulated_customer_filter`: filter by vertical, renewal date, and severity
- `negative_evidence`: correctly answer "no" with supporting evidence
- `budget_control`: avoid brute-force reranking and choose focused routes
- `tool_calling_vs_codegen`: tasks intended to compare codegen with multi-turn tool calling
- `reflection_required`: thin-evidence or no-answer cases where follow-up planning is expected
- `wide_fanout`: broad search and aggregation across many entities
- `multi_hop`: infer answer through several linked evidence documents
- `comparative_analysis`: compare versions, customers, or blockers

## Recommended Baselines

The benchmark should compare at least:

1. Fixed enriched retrieval:

```text
query understanding -> entity linking -> query rewrite -> hybrid retrieval -> rerank
```

2. Multi-turn tool-calling agent:

```text
LLM -> tool call -> observe -> next tool call -> observe -> synthesize
```

3. One-shot Search-as-Code:

```text
LLM/codegen -> execute generated retrieval program -> compact evidence -> synthesize
```

4. Reflective Search-as-Code:

```text
one-shot generated program -> reflect on evidence -> optional follow-up generated program
```

5. Ablations:

```text
force fixed rerank budget
oracle route plan
no rewrite
no BM25 exact route
no reflection
```

## Metrics

Retrieval metrics:

- recall@k over `evidence_doc_ids`
- nDCG@k over BEIR qrels
- first relevant rank
- hard negative intrusion rate

Answer metrics:

- exact answer field match
- citation correctness
- answer completeness
- unsupported claim rate
- negative-answer correctness

Efficiency metrics:

- latency including codegen
- codegen latency
- token usage
- tool calls
- search calls
- rerank pairs
- candidate pool size
- reflection trigger rate and precision
- invalid code rate
- timeout rate

## Generate And Validate

```bash
python3 sac_benchmark_dataset/generate_dataset.py
python3 sac_benchmark_dataset/validate_dataset.py
python3 sac_benchmark_dataset/audit_dataset.py --write-report
```

## Design Notes

The dataset intentionally includes hard negatives:

- nearby but wrong release versions, such as AtlasSearch 4.8.1 vs. 4.8.2
- same product but wrong CVE
- same customer but wrong blocker
- customers with similar products but different renewal urgency
- negative evidence where the system should stop instead of continuing to search
- generated distractor clusters across releases, advisories, tickets, account
  briefs, escalation logs, meeting notes, and guides

This is important because Search-as-Code should not simply "search more." It
should search selectively, preserve exact identifiers, and stop when the
evidence is sufficient.
