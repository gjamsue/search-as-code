# Public Architecture Matrix / Sanity Check

These runs complement the custom enterprise Search-as-Code benchmark. They compare the selected architecture variants on known public datasets, not to claim official leaderboard numbers.

Note: deterministic codegen variants are proxies used for reproducible full-batch evaluation. Use `real_codegen_search_as_code` for true model-generated Python; see `real_codegen_demo_report.md` for the current smoke test.

- Top-k: `10`
- Rerank candidate budget: `40`
- Generated branch top-k: `20`
- Generated max rerank candidates: `40`

## Summary

| Benchmark | Setting | Docs | Queries | Best system by Recall@10 | Recall@10 | nDCG@10 | MRR@10 | Total ms | Codegen ms | Execution ms |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| BEIR/scifact | Full BEIR corpus loaded locally | 5183 | 300 | `agentic_code_gen_rule_reflection` | 0.8254 | 0.6961 | 0.6636 | 389.4 | 0.1 | 389.3 |
| HotpotQA dev-distractor slice | Official dev-distractor contexts pooled across 100 examples | 991 | 100 | `fixed_flow_model_qr` | 0.9550 | 0.8704 | 0.9444 | 237.6 | 0.0 | 237.6 |

## Detailed Results

### BEIR/scifact

Source: https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip

Setting: Full BEIR corpus loaded locally

- This is a real BEIR dataset loaded through the BEIR GenericDataLoader.
- Metrics are local-system sanity-check numbers, not leaderboard submissions.

| System | Recall@10 | nDCG@10 | MRR@10 | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `agentic_code_gen_rule_reflection` | 0.8254 | 0.6961 | 0.6636 | 389.4 | 0.1 | 389.3 | 5.40 | 40.0 |
| `fixed_flow_model_qr` | 0.8251 | 0.6954 | 0.6633 | 329.9 | 0.0 | 329.9 | 3.66 | 40.0 |
| `agentic_fixed_flow_rule_reflection` | 0.8234 | 0.6926 | 0.6598 | 963.3 | 0.1 | 963.2 | 5.01 | 133.3 |
| `one_shot_code_gen_rule_policy` | 0.8196 | 0.6935 | 0.6633 | 367.7 | 0.1 | 367.6 | 5.03 | 40.4 |
| `agentic_preset_flows_rule_reflection` | 0.7944 | 0.6682 | 0.6376 | 304.6 | 0.0 | 304.6 | 3.98 | 38.4 |
| `preset_flow_model_router` | 0.7478 | 0.6309 | 0.6032 | 249.3 | 0.0 | 249.2 | 1.54 | 36.4 |

Interpretation:
- BEIR is mostly a retrieval-quality sanity check; it does not isolate enterprise-style tool control.

### HotpotQA dev-distractor slice

Source: http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json

Setting: Official dev-distractor contexts pooled across 100 examples

- Uses official HotpotQA dev-distractor examples and supporting-fact labels.
- Corpus is the pooled distractor context from selected examples, not HotpotQA fullwiki and not BEIR HotpotQA full corpus.
- Use this as a multi-hop public sanity check, not as a leaderboard number.

| System | Recall@10 | nDCG@10 | MRR@10 | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fixed_flow_model_qr` | 0.9550 | 0.8704 | 0.9444 | 237.6 | 0.0 | 237.6 | 3.96 | 40.0 |
| `one_shot_code_gen_rule_policy` | 0.9450 | 0.8666 | 0.9444 | 245.9 | 0.1 | 245.8 | 5.28 | 46.4 |
| `preset_flow_model_router` | 0.9400 | 0.8600 | 0.9344 | 186.1 | 0.0 | 186.0 | 1.78 | 39.6 |
| `agentic_fixed_flow_rule_reflection` | 0.9350 | 0.8535 | 0.9294 | 689.3 | 0.1 | 689.1 | 5.21 | 134.5 |
| `agentic_code_gen_rule_reflection` | 0.9300 | 0.8512 | 0.9294 | 221.8 | 0.1 | 221.7 | 5.79 | 40.0 |
| `agentic_preset_flows_rule_reflection` | 0.9250 | 0.8451 | 0.9194 | 196.1 | 0.0 | 196.0 | 4.14 | 39.6 |

Interpretation:
- HotpotQA adds multi-hop pressure, but this slice uses pooled distractor contexts rather than fullwiki retrieval.
