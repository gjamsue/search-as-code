# Harness-1 Reproduction TODO

Goal: turn the Harness-1 paper into a reusable external evaluation track for Search-as-Code / agentic search, while keeping each comparison honest about data, retrieval backend, model, and metric compatibility.

## Evaluation Standard

- Primary retrieval metric: `Recall@10` for this repo's public matrix.
- Harness-1-compatible metrics to add: curated recall, trajectory recall, and final-answer recall.
- Latency split to preserve: total latency, planning/codegen latency, execution latency.
- Every run must record: dataset, corpus source, query count, document count, candidate budget, reranker, model/provider, search calls, rerank pairs, and whether results are official reproduction or local sanity check.

## Dataset Backlog

| Priority | Dataset | Paper backend | Current repo status | Next action | Done when |
|---:|---|---|---|---|---|
| P0 | BEIR/SciFact | Not a Harness-1 set; public IR sanity check | Running in `run_public_benchmarks.py` | Keep as canonical public baseline | `public_variant_matrix_report.md` has 6-variant results |
| P0 | HotpotQA dev-distractor | Harness-1 has HotpotQA-subset via Web backend | Running as local pooled distractor check | Keep as overlap only, not official Harness-1 | Report labels it as sanity check |
| P1 | BrowseComp+ | Chroma BC+ corpus | Loader added as `harness1/browsecompplus`, waiting on corpus JSONL | Build/export qrel-matching corpus chunks, then run 6 variants | Report includes query/doc counts and qrel validation passes |
| P1 | FRAMES | Serper + Jina web backend | Not added | Add loader and choose retrieval backend: static corpus if available, or web-search trajectory mode | Recall metrics run on fixed query subset |
| P2 | Seal0QA | Serper + Jina web backend | Not added | Add loader after FRAMES; decide whether live web is acceptable | Completed-query accounting is explicit |
| P2 | LongSealQA | Dedicated Chroma collection | Not added | Locate/download corpus; build JSONL/Chroma export | Local corpus IDs align with qrels |
| P3 | Web | Chroma web 1.17 | Not reproducible from public Harness-1 release | Reconstruct via Context-1 data-gen or obtain compatible index | Corpus provenance documented |
| P3 | Patents | Chroma USPTO 1.18 | Not reproducible from public Harness-1 release | Rebuild from USPTO open data if needed | Patent doc/chunk IDs stable |
| P3 | SEC | Chroma SEC 1.4 | Not reproducible from public Harness-1 release | Rebuild from SEC EDGAR if finance story matters | Filing family and qrels validation pass |

## Method Backlog

| Priority | Method | Paper role | Current repo status | Reproduction plan | Risk |
|---:|---|---|---|---|---|
| P0 | BM25 / dense / hybrid / hybrid+rerank | Classical search baselines | Implemented in `run_named_search_baselines.py` and public runner support systems | Keep in every public set as baseline floor | Low |
| P0 | Fixed flow with QR + hybrid + rerank | Strong non-agentic baseline | Implemented as `fixed_flow_model_qr` | Keep as main baseline for each public set | Low |
| P0 | Agentic preset flow | Practical agentic search baseline | Implemented as `agentic_preset_flows_rule_reflection` | Keep as recommended product path | Low |
| P0 | One-shot Search-as-Code | Codegen baseline | Implemented as `one_shot_code_gen_rule_policy` and real codegen smoke | Run deterministic full-batch plus real-codegen samples | Medium |
| P0 | Agentic Search-as-Code | Main experimental variant | Implemented as `agentic_code_gen_rule_reflection` and real agentic codegen | Run deterministic full-batch plus real-codegen samples | Medium |
| P1 | Naive Search-Add harness | Harness-1 harness ablation baseline | Not implemented | Add minimal loop: search -> append results -> stop/rerank; no curation, compression, dedup, or reflection | Low |
| P1 | Context-1-style harness | Closest open trained-agent baseline environment | Not implemented | Recreate context threshold, pruning cap, max turns, RRF fusion; run with our local tools first | Medium |
| P1 | Multi-rollout RRF fusion | Harness-1 3x evaluation | Not implemented | Add `--rollouts 3` and fuse final ranked sets with RRF k=60 | Low |
| P2 | Search-R1 | Open search RL baseline | Not implemented | Locate released harness/model; adapt final trajectory pool to our curated-set format | High |
| P2 | gpt-oss-20b / gpt-oss-120b | Open model retriever baselines | Not implemented | Use Context-1-style harness with local/hosted model endpoint if available | High |
| P2 | Qwen3 32B | Open base model baseline | Not implemented | Use same harness protocol; separate model latency from retrieval execution | High |
| P2 | Tongyi DeepResearch | Agent baseline | Not implemented | Check release/API availability; likely external-service comparison only | High |
| P3 | Frontier model retrievers | Frontier comparison | Not implemented | Only run if budget/access is approved; label as service-dependent | High |
| P3 | Qwen3-Reranker-8B | Paper reranker | Current reranker is MS MARCO MiniLM CrossEncoder | Add optional reranker adapter if weights/service available | Medium |

## Implementation TODO

- [x] Add Harness-1/BrowseComp+ local loader with qrel/corpus ID validation.
- [x] Document what can and cannot be reproduced from the Harness-1 public release.
- [x] Add `public_eval_suite.md` as the stable user-facing eval guide.
- [ ] Add JSON schema for benchmark result artifacts.
- [ ] Add `naive_search_add` baseline to the public runner.
- [ ] Add multi-rollout RRF fusion to the public runner.
- [ ] Add curated recall vs trajectory recall accounting where candidate trajectories are available.
- [ ] Add BrowseComp+ corpus build/export instructions after local data is available.
- [ ] Add FRAMES loader and decide static-corpus vs live-web protocol.
- [ ] Add Context-1-style harness baseline.
- [ ] Try Search-R1 released harness and document blockers.

## Guardrails

- Do not mix static-corpus and live-web results in one table without a backend column.
- Do not claim official Harness-1 reproduction unless the same query IDs, corpus/index, backend, reranker, and metric definitions are matched.
- Keep public sanity checks separate from the custom enterprise benchmark.
- Keep deterministic proxy runs separate from real LLM/codegen runs.
