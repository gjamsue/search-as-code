# Named Search Baseline Calibration

This report calibrates the custom enterprise dataset against recognizable retrieval stacks. It is not an agentic or codegen result.

- Dataset: `sac-codegen-v3` / split `test`
- Documents: `6010`
- Tasks: `31`
- Candidate budget for rerank/RRF systems: `2400`
- Metric: `Recall@10`

| System | Recognizable reference | Recall@10 | nDCG@10 | MRR@10 | Total ms | Search calls | Rerank pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| `Okapi BM25` | Lucene / Elasticsearch / OpenSearch-style sparse lexical retrieval | 0.2350 | 0.2822 | 0.5930 | 10.7 | 1.00 | 0.0 |
| `Weighted BM25 + dense hybrid` | Common OpenSearch/Elasticsearch-style hybrid lexical + vector retrieval | 0.2286 | 0.2891 | 0.5870 | 20.1 | 1.00 | 0.0 |
| `Hybrid + CrossEncoder rerank` | Two-stage hybrid retrieve-and-rerank | 0.1857 | 0.2288 | 0.5254 | 3142.5 | 1.00 | 2400.0 |
| `Query rewrite + hybrid + CrossEncoder` | Production-style query understanding/rewrite + hybrid retrieve-and-rerank | 0.1857 | 0.2288 | 0.5254 | 3209.6 | 4.19 | 2400.0 |
| `BM25 + CrossEncoder rerank` | Two-stage sparse retrieve-and-rerank | 0.1857 | 0.2153 | 0.4972 | 3133.6 | 1.00 | 2400.0 |
| `Dense + CrossEncoder rerank` | Two-stage dense retrieve-and-rerank | 0.1821 | 0.2263 | 0.5248 | 3139.6 | 1.00 | 2400.0 |
| `RRF BM25 + dense hybrid` | Reciprocal Rank Fusion hybrid retrieval | 0.1667 | 0.2166 | 0.4803 | 28.2 | 2.00 | 0.0 |
| `MiniLM bi-encoder dense` | Sentence-Transformers dense semantic retrieval | 0.0932 | 0.1260 | 0.3070 | 15.9 | 1.00 | 0.0 |

## Readout

- BM25 is expected to be strong when exact identifiers matter; dense-only retrieval should be weaker on CVEs, tickets, aliases, and version strings.
- CrossEncoder rerank can improve ordering, but it cannot recover evidence that the first-stage retriever failed to include.
- If agentic/codegen systems beat these baselines on the custom dataset, the lift should come from evidence coverage and controlled follow-up routes, not from a weak lexical baseline.
