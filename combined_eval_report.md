# Combined Search-as-Code Evaluation

## Executive Readout

- Scope note: the main real-LLM result is now the full 31-query custom enterprise test; the older 5-query focused sample remains as a debugging artifact.
- Full real-LLM eval confirms the ordering: agentic codegen is highest quality, followed by one-shot codegen and agentic preset search.
- Agentic codegen beats one-shot codegen by `+0.1190` Recall@10.
- Agentic preset reflection beats single preset routing by `+0.1926` Recall@10.
- Agentic codegen reaches the highest quality, but costs `4.5x` the agentic preset latency.
- Custom named-search calibration: Okapi BM25 reaches `0.2350`, dense bi-encoder `0.0932`, and hybrid+CrossEncoder rerank `0.1857` Recall@10.
- Public SciFact check is effectively a tie: agentic codegen `0.8254` vs fixed flow `0.8251` Recall@10.
- Public HotpotQA check favors fixed flow: `0.9550` vs agentic codegen `0.9300` Recall@10.
- Recommended interpretation: use preset-stack agentic search as the practical product path; keep full codegen as an advanced/research path for hard cases.

## Main Results

| Scope | Benchmark | System | Recall@10 | Total ms | LLM/codegen ms | Exec ms | Search calls | Rerank pairs |
|---|---|---|---:|---:|---:|---:|---:|---:|
| full real LLM custom test | sac-codegen-v3/test-real-llm | `real_agentic_code_gen` | 0.7058 | 159693.9 | 159078.5 | 615.5 | 32.81 | 76.1 |
| full real LLM custom test | sac-codegen-v3/test-real-llm | `real_one_shot_code_gen` | 0.5868 | 60593.7 | 60383.1 | 210.6 | 8.64 | 39.6 |
| full real LLM custom test | sac-codegen-v3/test-real-llm | `real_agentic_preset_flow_llm_reflection` | 0.5610 | 35676.2 | 35349.2 | 327.0 | 7.58 | 114.8 |
| full real LLM custom test | sac-codegen-v3/test-real-llm | `real_agentic_fixed_flow_llm_reflection` | 0.4256 | 40660.4 | 38583.4 | 2077.0 | 7.93 | 1072.3 |
| full real LLM custom test | sac-codegen-v3/test-real-llm | `real_preset_flow_llm_router` | 0.3684 | 13156.5 | 12991.1 | 165.4 | 1.90 | 67.9 |
| full real LLM custom test | sac-codegen-v3/test-real-llm | `real_fixed_flow_llm_qr` | 0.1747 | 13317.2 | 12991.1 | 326.1 | 4.00 | 120.0 |
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
| custom named search baselines | sac-codegen-v3/test | `okapi_bm25_rank_bm25` | 0.2350 | 10.7 | 0.0 | 10.7 | 1.00 | 0.0 |
| custom named search baselines | sac-codegen-v3/test | `weighted_hybrid_bm25_minilm` | 0.2286 | 20.1 | 0.0 | 20.1 | 1.00 | 0.0 |
| custom named search baselines | sac-codegen-v3/test | `hybrid_cross_encoder_rerank` | 0.1857 | 3142.5 | 0.0 | 3142.5 | 1.00 | 2400.0 |
| custom named search baselines | sac-codegen-v3/test | `query_rewrite_hybrid_cross_encoder` | 0.1857 | 3209.6 | 0.0 | 3209.6 | 4.19 | 2400.0 |
| custom named search baselines | sac-codegen-v3/test | `bm25_cross_encoder_rerank` | 0.1857 | 3133.6 | 0.0 | 3133.6 | 1.00 | 2400.0 |
| custom named search baselines | sac-codegen-v3/test | `dense_cross_encoder_rerank` | 0.1821 | 3139.6 | 0.0 | 3139.6 | 1.00 | 2400.0 |
| custom named search baselines | sac-codegen-v3/test | `rrf_hybrid_bm25_minilm` | 0.1667 | 28.2 | 0.0 | 28.2 | 2.00 | 0.0 |
| custom named search baselines | sac-codegen-v3/test | `minilm_biencoder_dense` | 0.0932 | 15.9 | 0.0 | 15.9 | 1.00 | 0.0 |
| public architecture matrix | HotpotQA dev-distractor slice | `fixed_flow_model_qr` | 0.9550 | 237.6 | 0.0 | 237.6 | 3.96 | 40.0 |
| public architecture matrix | HotpotQA dev-distractor slice | `one_shot_code_gen_rule_policy` | 0.9450 | 245.9 | 0.1 | 245.8 | 5.28 | 46.4 |
| public architecture matrix | HotpotQA dev-distractor slice | `preset_flow_model_router` | 0.9400 | 186.1 | 0.0 | 186.0 | 1.78 | 39.6 |
| public architecture matrix | HotpotQA dev-distractor slice | `agentic_fixed_flow_rule_reflection` | 0.9350 | 689.3 | 0.1 | 689.1 | 5.21 | 134.5 |
| public architecture matrix | HotpotQA dev-distractor slice | `agentic_code_gen_rule_reflection` | 0.9300 | 221.8 | 0.1 | 221.7 | 5.79 | 40.0 |
| public architecture matrix | HotpotQA dev-distractor slice | `agentic_preset_flows_rule_reflection` | 0.9250 | 196.1 | 0.0 | 196.0 | 4.14 | 39.6 |
| public architecture matrix | BEIR/scifact | `agentic_code_gen_rule_reflection` | 0.8254 | 389.4 | 0.1 | 389.3 | 5.40 | 40.0 |
| public architecture matrix | BEIR/scifact | `fixed_flow_model_qr` | 0.8251 | 329.9 | 0.0 | 329.9 | 3.66 | 40.0 |
| public architecture matrix | BEIR/scifact | `agentic_fixed_flow_rule_reflection` | 0.8234 | 963.3 | 0.1 | 963.2 | 5.01 | 133.3 |
| public architecture matrix | BEIR/scifact | `one_shot_code_gen_rule_policy` | 0.8196 | 367.7 | 0.1 | 367.6 | 5.03 | 40.4 |
| public architecture matrix | BEIR/scifact | `agentic_preset_flows_rule_reflection` | 0.7944 | 304.6 | 0.0 | 304.6 | 3.98 | 38.4 |
| public architecture matrix | BEIR/scifact | `preset_flow_model_router` | 0.7478 | 249.3 | 0.0 | 249.2 | 1.54 | 36.4 |
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
- `real_llm_matrix_full_results.json`: full real LLM matrix; queries=31; documents=6010
- `real_codegen_retest_results.json`: focused real codegen retest; queries=5; documents=6010
- `named_search_baselines_results.json`: custom named search baseline calibration; queries=31; documents=6010
- `public_variant_matrix_results.json`: public architecture matrix; queries=400; documents=None
- `public_benchmark_results.json`: public benchmark sanity checks; queries=400; documents=None
- `sac_benchmark_results.json`: custom full extended variants; queries=31; documents=6010
