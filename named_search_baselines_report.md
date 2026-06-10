# Named Search Baseline Calibration

This report calibrates the custom enterprise dataset against recognizable retrieval stacks. It is not an agentic or codegen result.

- Dataset: `sac-codegen-v3` / split `test`
- Documents: `6010`
- Tasks: `31`
- Candidate budget for rerank/RRF systems: `2400`
- Metric: `Recall@10`

| System | Recognizable reference | Recall@10 | nDCG@10 | MRR@10 | Total ms | Search calls | Rerank pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| `Okapi BM25` | Lucene / Elasticsearch / OpenSearch-style sparse lexical retrieval | 0.2387 | 0.3096 | 0.7006 | 12.7 | 1.00 | 0.0 |
| `Weighted BM25 + dense hybrid` | Common OpenSearch/Elasticsearch-style hybrid lexical + vector retrieval | 0.2375 | 0.3187 | 0.6973 | 19.7 | 1.00 | 0.0 |
| `Hybrid + CrossEncoder rerank` | Two-stage hybrid retrieve-and-rerank | 0.2018 | 0.2712 | 0.6659 | 3154.2 | 1.00 | 2400.0 |
| `Query rewrite + hybrid + CrossEncoder` | Production-style query understanding/rewrite + hybrid retrieve-and-rerank | 0.2018 | 0.2712 | 0.6659 | 3270.8 | 4.19 | 2400.0 |
| `BM25 + CrossEncoder rerank` | Two-stage sparse retrieve-and-rerank | 0.2018 | 0.2577 | 0.6377 | 5168.2 | 1.00 | 2400.0 |
| `Dense + CrossEncoder rerank` | Two-stage dense retrieve-and-rerank | 0.1986 | 0.2689 | 0.6659 | 4049.8 | 1.00 | 2400.0 |
| `RRF BM25 + dense hybrid` | Reciprocal Rank Fusion hybrid retrieval | 0.1731 | 0.2316 | 0.5233 | 28.1 | 2.00 | 0.0 |
| `MiniLM bi-encoder dense` | Sentence-Transformers dense semantic retrieval | 0.0949 | 0.1336 | 0.3393 | 18.7 | 1.00 | 0.0 |

## Readout

- BM25 is expected to be strong when exact identifiers matter; dense-only retrieval should be weaker on CVEs, tickets, aliases, and version strings.
- The generic MS MARCO CrossEncoder is a weak fit for this benchmark's multi-evidence Recall@10 objective; it often promotes semantically similar decoys over source-of-truth coverage.
- The separate diagnostic report shows hybrid retrieval has much higher candidate-pool recall than top-10 recall, so the headroom is in final selection and evidence-aware follow-up, not just first-stage retrieval.
- If agentic/codegen systems beat these baselines on the custom dataset, the lift should come from evidence coverage and controlled follow-up routes, not from a weak lexical baseline.
