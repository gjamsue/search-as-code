# Combined Search-as-Code Evaluation

## Executive Readout

- Scope note: the real-LLM results are a focused 5-query hard sample; the full custom runs are 31-query deterministic/rule-backed evaluations.
- On the focused real-LLM sample, improved planning/reflection makes agentic methods clearly win on quality.
- Agentic preset flow beats one-shot preset routing by `+0.3714` Recall@10 with much lower latency than full agentic codegen.
- Agentic codegen reaches the highest quality, but costs `4.8x` the agentic preset latency.
- Recommended interpretation: use preset-stack agentic search as the practical product path; keep full codegen as an advanced/research path for hard cases.

## Main Results

| Scope | Benchmark | System | Recall@10 | Total ms | LLM/codegen ms | Exec ms | Search calls | Rerank pairs |
|---|---|---|---:|---:|---:|---:|---:|---:|
| focused real LLM sample | sac-codegen-v3/focused-5 | `real_agentic_code_gen` | 1.0000 | 136271.9 | 135929.4 | 342.5 | 21.20 | 69.2 |
| focused real LLM sample | sac-codegen-v3/focused-5 | `real_agentic_preset_flow_llm_reflection` | 0.8114 | 28692.8 | 28436.5 | 256.4 | 6.20 | 97.6 |
| focused real LLM sample | sac-codegen-v3/focused-5 | `real_one_shot_code_gen` | 0.7114 | 62041.8 | 61891.1 | 150.7 | 6.60 | 39.2 |
| focused real LLM sample | sac-codegen-v3/focused-5 | `real_agentic_fixed_flow_llm_reflection` | 0.4686 | 30620.5 | 29223.8 | 1396.7 | 6.00 | 840.0 |
| focused real LLM sample | sac-codegen-v3/focused-5 | `real_preset_flow_llm_router` | 0.4400 | 11638.1 | 11523.4 | 114.8 | 1.80 | 49.0 |
| focused real LLM sample | sac-codegen-v3/focused-5 | `real_fixed_flow_llm_qr` | 0.1686 | 11817.1 | 11523.4 | 293.7 | 4.00 | 120.0 |
| focused real codegen sample | sac-codegen-v3/focused-5 | `real_agentic_codegen_search_as_code` | 1.0000 | 136272.4 | 135929.5 | 342.9 | 21.20 | 69.2 |
| focused real codegen sample | sac-codegen-v3/focused-5 | `real_codegen_search_as_code` | 0.7114 | 62038.7 | 61891.3 | 147.4 | 6.60 | 39.2 |
| focused real codegen sample | sac-codegen-v3/focused-5 | `generated_iterative_agentic_search_as_code` | 0.6114 | 325.4 | 0.2 | 325.1 | 8.80 | 120.0 |
| focused real codegen sample | sac-codegen-v3/focused-5 | `fixed_understanding_rewrite_hybrid_rerank` | 0.2686 | 285.3 | 0.0 | 285.3 | 4.00 | 120.0 |
| focused real codegen sample | sac-codegen-v3/focused-5 | `generated_search_as_code` | 0.2686 | 277.5 | 0.1 | 277.4 | 8.00 | 120.0 |
| custom enterprise full test | sac-codegen-v3/test | `agentic_code_gen_rule_reflection` | 0.4712 | 3338.5 | 0.2 | 3338.2 | 7.16 | 2400.0 |
| custom enterprise full test | sac-codegen-v3/test | `agentic_preset_flows_rule_reflection` | 0.4655 | 1104.2 | 5.4 | 1098.8 | 6.10 | 733.5 |
| custom enterprise full test | sac-codegen-v3/test | `agentic_fixed_flow_rule_reflection` | 0.2785 | 7775.8 | 0.2 | 7775.5 | 12.39 | 5189.0 |
| custom enterprise full test | sac-codegen-v3/test | `preset_flow_model_router` | 0.2083 | 1770.7 | 0.0 | 1770.7 | 2.00 | 1251.5 |
| custom enterprise full test | sac-codegen-v3/test | `one_shot_code_gen_rule_policy` | 0.1857 | 3238.0 | 0.1 | 3237.8 | 6.97 | 2400.0 |
| custom enterprise full test | sac-codegen-v3/test | `fixed_flow_model_qr` | 0.1857 | 3556.8 | 0.0 | 3556.8 | 3.97 | 2400.0 |
| public sanity check | HotpotQA dev-distractor slice | `fixed_understanding_rewrite_hybrid_rerank` | 0.9550 | 211.2 | 0.0 | 211.1 | 3.78 | 40.0 |
| public sanity check | HotpotQA dev-distractor slice | `generated_search_as_code` | 0.9550 | 252.8 | 0.1 | 252.7 | 9.80 | 39.1 |
| public sanity check | HotpotQA dev-distractor slice | `fixed_hybrid_rerank` | 0.9500 | 205.0 | 0.0 | 205.0 | 1.00 | 40.0 |
| public sanity check | HotpotQA dev-distractor slice | `fixed_bm25` | 0.8700 | 2.0 | 0.0 | 2.0 | 1.00 | 0.0 |
| public sanity check | BEIR/scifact | `generated_search_as_code` | 0.8439 | 369.7 | 0.0 | 369.6 | 7.03 | 38.7 |
| public sanity check | BEIR/scifact | `fixed_understanding_rewrite_hybrid_rerank` | 0.8278 | 318.6 | 0.0 | 318.6 | 3.26 | 40.0 |
| public sanity check | BEIR/scifact | `fixed_hybrid_rerank` | 0.8211 | 275.5 | 0.0 | 275.5 | 1.00 | 40.0 |
| public sanity check | BEIR/scifact | `fixed_bm25` | 0.7228 | 16.9 | 0.0 | 16.9 | 1.00 | 0.0 |

## Full Custom Extended Variants

These are the additional full-dataset variants from `sac_benchmark_results.json` on the same 31-query test split.

| System | Recall@10 | nDCG@10 | MRR@10 | Total ms | Search calls | Rerank pairs | Note |
|---|---:|---:|---:|---:|---:|---:|---|
| `generated_iterative_agentic_search_as_code` | 0.4712 | 0.4634 | 0.6704 | 3362.5 | 7.16 | 2400.0 | Generated code iterates with evidence-coverage reflection |
| `agentic_fixed_flow_iterative` | 0.2694 | 0.3432 | 0.6801 | 3991.5 | 12.71 | 2687.4 | Agent iteratively calls the same fixed flow with new queries |
| `fixed_bm25` | 0.2350 | 0.2822 | 0.5930 | 13.3 | 1.00 | 0.0 | lexical BM25 baseline |
| `fixed_hybrid` | 0.2286 | 0.2891 | 0.5870 | 19.6 | 1.00 | 0.0 | hybrid BM25+dense baseline |
| `fixed_hybrid_rerank` | 0.1857 | 0.2288 | 0.5254 | 3211.5 | 1.00 | 2400.0 | hybrid + rerank with 2,400-candidate budget |
| `fixed_understanding_rewrite_hybrid_rerank` | 0.1857 | 0.2288 | 0.5254 | 3231.2 | 3.97 | 2400.0 | Fixed query understanding + rewrite + hybrid retrieval + rerank |
| `generated_search_as_code` | 0.1857 | 0.2288 | 0.5254 | 3263.1 | 6.97 | 2400.0 | One-shot generated route plan with SDK parameters |
| `generated_search_as_code_force_budget` | 0.1857 | 0.2288 | 0.5254 | 3258.4 | 6.97 | 2400.0 | one-shot generated route plan with forced budget |
| `generated_reflective_search_as_code` | 0.1857 | 0.2288 | 0.5254 | 3256.6 | 6.97 | 2400.0 | single-pass generated flow with reflection hooks |
| `fixed_hybrid_rerank_small_budget` | 0.1714 | 0.2113 | 0.4966 | 598.7 | 1.00 | 400.0 | hybrid + rerank with 400-candidate budget |
| `fixed_semantic_dense` | 0.0932 | 0.1260 | 0.3070 | 16.6 | 1.00 | 0.0 | dense semantic baseline |

## Artifacts

- `experiment_matrix_results.json`: custom full matrix; queries=31; documents=6010
- `real_llm_matrix_results.json`: focused real LLM matrix; queries=5; documents=6010
- `real_codegen_retest_results.json`: focused real codegen retest; queries=5; documents=6010
- `public_benchmark_results.json`: public benchmark sanity checks; queries=400; documents=None
- `sac_benchmark_results.json`: custom full extended variants; queries=31; documents=6010
