# Public Benchmark Sanity Check

These runs complement the custom enterprise Search-as-Code benchmark. They are intended to test whether the implementation behaves sensibly on known public datasets, not to claim official leaderboard numbers.

- Top-k: `10`
- Rerank candidate budget: `40`
- Generated branch top-k: `20`
- Generated max rerank candidates: `40`

## Summary

| Benchmark | Setting | Docs | Queries | Best system by Recall@10 | Recall@10 | nDCG@10 | MRR@10 | Latency ms |
|---|---|---:|---:|---|---:|---:|---:|---:|
| BEIR/scifact | Full BEIR corpus loaded locally | 5183 | 300 | `generated_search_as_code` | 0.8439 | 0.7035 | 0.6691 | 369.7 |
| HotpotQA dev-distractor slice | Official dev-distractor contexts pooled across 100 examples | 991 | 100 | `fixed_understanding_rewrite_hybrid_rerank` | 0.9550 | 0.8704 | 0.9444 | 211.2 |

## Detailed Results

### BEIR/scifact

Source: https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip

Setting: Full BEIR corpus loaded locally

- This is a real BEIR dataset loaded through the BEIR GenericDataLoader.
- Metrics are local-system sanity-check numbers, not leaderboard submissions.

| System | Recall@10 | nDCG@10 | MRR@10 | Mean latency ms | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|
| `generated_search_as_code` | 0.8439 | 0.7035 | 0.6691 | 369.7 | 7.03 | 38.7 |
| `fixed_understanding_rewrite_hybrid_rerank` | 0.8278 | 0.6961 | 0.6637 | 318.6 | 3.26 | 40.0 |
| `fixed_hybrid_rerank` | 0.8211 | 0.6906 | 0.6588 | 275.5 | 1.00 | 40.0 |
| `fixed_bm25` | 0.7228 | 0.5925 | 0.5557 | 16.9 | 1.00 | 0.0 |

Interpretation:
- Generated Search-as-Code delta vs strongest fixed baseline on Recall@10: `+0.0161`.
- BEIR is mostly a retrieval-quality sanity check; it does not isolate enterprise-style tool control.

### HotpotQA dev-distractor slice

Source: http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json

Setting: Official dev-distractor contexts pooled across 100 examples

- Uses official HotpotQA dev-distractor examples and supporting-fact labels.
- Corpus is the pooled distractor context from selected examples, not HotpotQA fullwiki and not BEIR HotpotQA full corpus.
- Use this as a multi-hop public sanity check, not as a leaderboard number.

| System | Recall@10 | nDCG@10 | MRR@10 | Mean latency ms | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|
| `fixed_understanding_rewrite_hybrid_rerank` | 0.9550 | 0.8704 | 0.9444 | 211.2 | 3.78 | 40.0 |
| `generated_search_as_code` | 0.9550 | 0.8678 | 0.9444 | 252.8 | 9.80 | 39.1 |
| `fixed_hybrid_rerank` | 0.9500 | 0.8685 | 0.9444 | 205.0 | 1.00 | 40.0 |
| `fixed_bm25` | 0.8700 | 0.7385 | 0.8446 | 2.0 | 1.00 | 0.0 |

Interpretation:
- Generated Search-as-Code delta vs strongest fixed baseline on Recall@10: `+0.0000`.
- HotpotQA adds multi-hop pressure, but this slice uses pooled distractor contexts rather than fullwiki retrieval.
