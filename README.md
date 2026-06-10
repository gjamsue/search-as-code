# Search-as-Code Codegen Benchmark

This repo contains the Search-as-Code prototype and benchmark artifacts for comparing generated retrieval programs against fixed enterprise search flows.

## What Is Included

- `sac_benchmark_dataset/`: synthetic enterprise knowledge-base dataset with 6,010 documents, 48 tasks, BEIR exports, hard-negative labels, generator, validator, and audit tooling.
- `real_search_stack/`: open-source search APIs built on BM25, sentence-transformers dense retrieval, spaCy query understanding/entity extraction, optional Wikidata linking, and cross-encoder reranking.
- `run_sac_dataset_benchmark.py`: main benchmark runner for fixed BM25, dense, hybrid, hybrid+rerank, fixed enriched, one-shot generated Search-as-Code, agentic fixed-flow calls, naive reflective Search-as-Code, and iterative agentic Search-as-Code flows.
- `run_experiment_matrix.py`: presentation-aligned matrix runner for fixed flow, agentic fixed flow, preset flow, agentic preset flow, one-shot codegen, and agentic codegen.
- `run_real_llm_matrix.py`: real-LLM matrix runner that uses Codex CLI for QR/router/planner/reflection decisions and real codegen.
- `run_public_eval_suite.py`: canonical wrapper for the reusable public eval suite.
- `run_public_benchmarks.py`: public benchmark runner for the baseline+5 architecture variants on BEIR/SciFact, HotpotQA dev-distractor slices, and local Harness-1/BrowseComp+ exports.
- `run_named_search_baselines.py`: custom dataset calibration against recognizable search stacks such as BM25, dense bi-encoder, hybrid, RRF, and CrossEncoder rerank.
- `run_search_baseline_diagnostics.py`: separates first-stage candidate recall from CrossEncoder rerank recall to debug baseline validity.
- `recompute_cached_metrics.py`: re-scores cached custom-result files after qrels changes without rerunning search or LLM generation.
- `merge_eval_reports.py`: merges custom, real LLM, real codegen, public architecture matrix, public sanity, and legacy eval outputs into one executive report.
- `llm_search_codegen.py`: real LLM-backed Search-as-Code generator with `codex-cli` and `openai` providers, AST validation, sandbox execution, and one-shot repair support.
- `skills/search-as-code-codegen/`: reusable Codex skill that defines the Search-as-Code runtime/tool contract for real code generation.
- `experiment_matrix_results.json`: latest presentation-aligned experiment matrix payload.
- `experiment_matrix_report.md`: latest presentation-aligned experiment matrix report.
- `sac_benchmark_results.json`: legacy broad benchmark result payload.
- `sac_benchmark_report.md`: legacy broad benchmark report, focused on Recall@10.
- `named_search_baselines_results.json` and `named_search_baselines_report.md`: custom dataset calibration against named search baselines.
- `public_variant_matrix_results.json` and `public_variant_matrix_report.md`: baseline+5 architecture variant matrix on BEIR/SciFact and HotpotQA.
- `public_benchmark_results.json`: latest public benchmark sanity-check payload.
- `public_benchmark_report.md`: latest public benchmark sanity-check report.
- `real_codegen_demo_results.json` and `real_codegen_demo_report.md`: 1-query real LLM codegen smoke using the local Codex CLI login path.
- `real_codegen_retest_results.json` and `real_codegen_retest_report.md`: 5-query real LLM retest comparing one-shot codegen and agentic codegen.
- `real_llm_matrix_results.json` and `real_llm_matrix_report.md`: 5-query focused real LLM matrix for QR, router, planner/reflection, and codegen variants.
- `real_llm_matrix_full_results.json` and `real_llm_matrix_full_report.md`: 31-query full real LLM matrix across the same variants.
- `combined_eval_results.json` and `combined_eval_report.md`: merged view across custom full matrix, full/focused real LLM matrices, real codegen retest, public architecture matrix, public benchmark checks, and legacy runs.
- `sac_benchmark_dataset_intro.md`: Chinese dataset intro with generation method, categories, statistics, and example tasks.
- `public_eval_suite.md`: reusable public benchmark guide with dataset scope, systems, commands, results, and extension rules.
- `harness1_benchmark_feasibility.md`: mapping from the Harness-1 paper benchmarks to what this repo can run now, add next, or must defer until corpora/indexes exist.
- `harness1_reproduction_todo.md`: step-by-step backlog for reproducing Harness-1 datasets, baselines, harness ablations, and comparison methods.
- `agentic_search_presentation.html`: mobile-friendly presentation for the final Search-as-Code story.

## Latest Result

Dataset: `sac-codegen-v3`

- Test split: 31 queries
- Corpus: 6,010 documents
- Primary metric: Recall@10
- Candidate opportunity: rerank systems retrieve up to 2,400 candidates before producing final top 10

### Full Real LLM Matrix

This is the main quality readout. It uses Codex CLI for real QR/router/planner/reflection/codegen decisions on all 31 custom enterprise test queries, with candidate budget `120`.

| Architecture | System | Recall@10 | Total ms | LLM/codegen ms | Execution ms | Search calls | Rerank pairs | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Fixed flow | `real_fixed_flow_llm_qr` | 0.1837 | 13,317 | 12,991 | 326 | 4.00 | 120 | LLM QR + multi-query hybrid + rerank |
| Preset flow | `real_preset_flow_llm_router` | 0.3689 | 13,156 | 12,991 | 165 | 1.90 | 67.9 | LLM router picks one preset stack |
| Agentic fixed flow | `real_agentic_fixed_flow_llm_reflection` | 0.4307 | 40,660 | 38,583 | 2,077 | 7.93 | 1,072 | LLM planner/reflection over fixed-flow calls |
| Agentic preset flow | `real_agentic_preset_flow_llm_reflection` | 0.5809 | 35,676 | 35,349 | 327 | 7.58 | 114.8 | LLM router/reflection picks additional preset stacks |
| One-shot codegen | `real_one_shot_code_gen` | 0.5779 | 60,594 | 60,383 | 211 | 8.64 | 39.6 | LLM writes one Python retrieval program |
| Agentic codegen | `real_agentic_code_gen` | 0.7081 | 159,694 | 159,078 | 615 | 32.81 | 76.1 | LLM planner/codegen + reflection/codegen loop |

Readout: real agentic codegen wins quality, beating one-shot codegen by `+0.1302` Recall@10 and agentic preset search by `+0.1272`. The cost is high: about `4.5x` the agentic preset latency. The practical path is still agentic preset search first, with full codegen reserved for hard cases, offline analysis, or cached workflows.

### Deterministic / Rule-Backed Matrix

This run is the fast, repeatable proxy used for iteration and ablations.

| Architecture | System | Recall@10 | Total ms | Plan/code ms | Execution ms | Search calls | Rerank pairs | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Fixed flow | `fixed_flow_model_qr` | 0.2018 | 3556.8 | 0.0 | 3556.8 | 3.97 | 2400 | Query rewrite + multi-query hybrid + rerank |
| Preset flow | `preset_flow_model_router` | 0.2233 | 1770.7 | 0.0 | 1770.7 | 2.00 | 1252 | Router picks one preset search stack |
| One-shot codegen | `one_shot_code_gen_rule_policy` | 0.2018 | 3238.0 | 0.1 | 3237.8 | 6.97 | 2400 | Python retrieval program, one execution |
| Agentic fixed flow | `agentic_fixed_flow_rule_reflection` | 0.2852 | 7775.8 | 0.2 | 7775.5 | 12.39 | 5189 | Repeated fixed-flow calls with reflection |
| Agentic preset flow | `agentic_preset_flows_rule_reflection` | 0.4627 | 1104.2 | 5.4 | 1098.8 | 6.10 | 733 | Reflection adds missing preset stacks |
| Agentic codegen | `agentic_code_gen_rule_reflection` | 0.4625 | 3338.5 | 0.2 | 3338.2 | 7.16 | 2400 | Generated code with evidence-goal reflection |

v3 is deliberately harder than v2: it adds alias/code-name tasks, source-authority disambiguation, stale approval ledgers, policy near-duplicates, and thousands of same-topic distractors. The current conclusion is sharper: one-shot codegen does not beat the fixed baseline. The lift comes from agentic evidence coverage: either selecting additional preset stacks after reflection, or generating retrieval code that can directly control routes, filters, and evidence preselection.

## Public Architecture Matrix

These runs apply the same baseline+5 variant matrix to known public datasets. They are not official leaderboard submissions. The point is coverage and sanity, not proving Search-as-Code wins everywhere.

| Benchmark | Fixed flow | Preset flow | Agentic fixed | Agentic preset | One-shot codegen | Agentic codegen | Readout |
|---|---:|---:|---:|---:|---:|---:|---|
| BEIR/SciFact, 5,183 docs, 300 queries | 0.8251 | 0.7478 | 0.8234 | 0.7944 | 0.8196 | 0.8254 | Effectively a tie: agentic codegen is +0.0003 over fixed flow |
| HotpotQA dev-distractor, 991 docs, 100 queries | 0.9550 | 0.9400 | 0.9350 | 0.9250 | 0.9450 | 0.9300 | Fixed flow wins; public multi-hop does not need enterprise-style source control |

The public check is useful for credibility, but it changes the conclusion: codegen is not universally better. Its advantage shows up most clearly in the custom enterprise setting, where source authority, alias resolution, hard-negative intrusion, and evidence-category reflection are first-order problems.

`public_eval_suite.md` is the reusable public-set guide. Run the canonical suite with:

```bash
python run_public_eval_suite.py
```

### Harness-1 Compatibility

The [Harness-1](https://arxiv.org/abs/2606.02373) paper is a strong external benchmark direction because it focuses on stateful search agents across web, finance, patents, and multi-hop QA. It is not directly reproducible end-to-end from the public repo alone: the Harness-1 dataset notes say the release includes eval code but does not bundle the large retrieval corpora or private Chroma indexes, and identifies BrowseComp+ as the main public ready-to-run path once local qrels plus a matching Chroma/corpus collection are available.

Current status:

| Harness-1 benchmark | Repo status | Action |
|---|---|---|
| HotpotQA subset | Covered as `hotpotqa/distractor` public sanity check | Keep as overlap, not an official Harness-1 reproduction |
| BrowseComp+ | Supported as `harness1/browsecompplus` when local queries/qrels/corpus JSONL are provided | Add after building/exporting qrel-matching corpus chunks |
| FRAMES / Seal0QA / LongSealQA | Not added | Add only after corpus/retrieval backend is pinned |
| Web / Patents / SEC | Not directly reproducible from public release | Defer until compatible Chroma corpora/indexes are reconstructed or obtained |

See `harness1_benchmark_feasibility.md` for setup details and source links.

## Named Search Baseline Calibration

Because BEIR/SciFact and HotpotQA show fixed retrieval is already strong, the custom dataset is also calibrated against recognizable search stacks. This is not an agentic or codegen comparison; it checks whether the custom dataset is hard for standard retrieval in a plausible way.

| Search stack | Recall@10 | Total ms | Readout |
|---|---:|---:|---|
| Okapi BM25 / Lucene-style sparse retrieval | 0.2387 | 12.7 | Strongest simple baseline because exact IDs, CVEs, aliases, and versions matter |
| Weighted BM25 + MiniLM dense hybrid | 0.2375 | 19.7 | Similar to BM25; semantic signal does not solve authority/evidence coverage |
| Hybrid + CrossEncoder rerank | 0.2018 | 3154.2 | Generic MS MARCO reranker misranks multi-evidence enterprise queries |
| Query rewrite + hybrid + CrossEncoder | 0.2018 | 3270.8 | More fanout still lacks evidence-category reflection |
| RRF BM25 + dense hybrid | 0.1731 | 28.1 | Rank fusion is not enough on hard-negative/authority tasks |
| MiniLM dense bi-encoder | 0.0949 | 18.7 | Weakest because semantic similarity misses exact identifiers and source authority |

Calibration readout: the custom dataset is not just “hard because our fixed flow is weak.” BM25 and hybrid are serious baselines, and the diagnostic report shows hybrid candidate-pool Recall@2400 reaches `0.7496`. The gap is in final evidence selection and reflection: generic CrossEncoder reranking drops to `0.2018`, while real agentic codegen reaches `0.7081`.

## Real LLM Codegen Smoke

The full benchmark tables use deterministic Search-as-Code generators for
reproducibility. A separate smoke path now runs true model-generated code:

- `real_codegen_search_as_code` calls `LLMSearchCodeGenerator`.
- Default provider is `codex-cli`, which uses the local Codex app login and does not need `OPENAI_API_KEY`.
- Optional provider `openai` uses the Responses API and requires `OPENAI_API_KEY`.
- Generated code is AST-validated, executed in a restricted namespace, and can run one repair turn after a runtime error.

Latest smoke: BEIR/SciFact, 5,183 documents, 1 query. End-to-end latency was about 49.5s: 49.2s code generation plus 265.5ms execution. The generated program made 3 search calls and used 1 rerank call. This is proof of execution, not a quality benchmark.

## Focused Real LLM Matrix

Focused enterprise sample: `sac-005, sac-028, sac-038, sac-042, sac-043`
with candidate budget `120`. This run replaces rule-backed QR/router/planner
and reflection with structured Codex CLI calls, then compares with real codegen.
It is retained as a debugging sample; the full 31-query table above is the main result.

| System | Recall@10 | Total ms | LLM ms | Execution ms | Readout |
|---|---:|---:|---:|---:|---|
| Real agentic codegen | 1.0000 | 136271.9 | 135929.4 | 342.5 | Highest quality, but too slow for the main path |
| Real agentic preset | 0.8114 | 28692.8 | 28436.5 | 256.4 | Best practical path: strong quality without full code generation |
| Real one-shot codegen | 0.7114 | 62041.8 | 61891.1 | 150.7 | Good quality after prompt/API hardening, but slower than preset-agentic |
| Real agentic fixed flow | 0.4686 | 30620.5 | 29223.8 | 1396.7 | Reflection helps, but fixed-flow tools are too rigid |
| Real preset router | 0.4400 | 11638.1 | 11523.4 | 114.7 | Strong single-router baseline |
| Real fixed flow + LLM QR | 0.1686 | 11817.1 | 11523.4 | 293.7 | LLM rewrite alone is not enough on hard enterprise queries |

Compared with the prior real-LLM run, agentic preset improved from `0.3686` to
`0.8114`, and real agentic codegen improved from `0.3086` to `1.0000`. The
changes were stronger planning/reflection prompts, real metadata constraints,
immutable `SearchCandidate` handling, and evidence-aware final selection.

## Real LLM Codegen Retest

Focused enterprise sample: `sac-005, sac-028, sac-038, sac-042, sac-043`
with candidate budget `120`.

| System | Recall@10 | Total ms | Codegen ms | Execution ms | Repairs | Readout |
|---|---:|---:|---:|---:|---:|---|
| Real agentic codegen | 1.0000 | 136272.4 | 135929.5 | 342.9 | 0 | Full evidence recovery, but high generation cost |
| Real one-shot codegen | 0.7114 | 62038.7 | 61891.3 | 147.4 | 0 | Stronger after metadata/API prompt hardening |
| Deterministic agentic codegen | 0.6114 | 325.4 | 0.2 | 325.1 | 0 | Fast proxy, lower quality than real agentic on focused sample |

The current gap is now cost, not basic reliability: real codegen can produce
high-quality retrieval programs, but generation/reflection latency is too high
for the default search path.

## Combined Eval Readout

`combined_eval_report.md` merges all major eval artifacts. The current readout:

- Full real LLM custom test: agentic codegen reaches `0.7081` Recall@10, agentic preset reaches `0.5809`, one-shot codegen reaches `0.5779`, and fixed flow reaches `0.1837`.
- Focused real LLM sample: agentic codegen reaches `1.0000` Recall@10, agentic preset reaches `0.8114`, one-shot codegen reaches `0.7114`.
- Full custom deterministic test: agentic preset `0.4627`, agentic codegen `0.4625`, fixed flow `0.2018`.
- Named custom search baselines: Okapi BM25 `0.2387`, weighted hybrid `0.2375`, hybrid+CrossEncoder rerank `0.2018`, dense bi-encoder `0.0949`.
- Public architecture matrix: SciFact is effectively a tie between agentic codegen `0.8254` and fixed flow `0.8251`; HotpotQA favors fixed flow `0.9550` over agentic codegen `0.9300`.
- Full custom extended variants are also listed: BM25 `0.2387`, hybrid `0.2375`, dense `0.0949`, small-budget hybrid-rerank `0.1864`, reflective one-shot `0.2018`.
- Practical recommendation: productize preset-stack agentic search first; keep full Search-as-Code generation for hard cases or offline/research workflows.

## Reproduce

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python sac_benchmark_dataset/validate_dataset.py
python sac_benchmark_dataset/audit_dataset.py --write-report
python run_experiment_matrix.py --split test
python run_sac_dataset_benchmark.py --split test
python run_real_llm_matrix.py --task-ids all --candidate-k 120 --tool-candidate-k 120 --timeout 240 --output real_llm_matrix_full_results.json --report real_llm_matrix_full_report.md
python run_named_search_baselines.py --split test --candidate-k 2400 --output named_search_baselines_results.json --report named_search_baselines_report.md
python run_search_baseline_diagnostics.py
python run_public_eval_suite.py
python recompute_cached_metrics.py
python merge_eval_reports.py
```

Run a Harness-1/BrowseComp+ local comparison after providing qrel-matching local files:

```bash
export BROWSECOMPPLUS_QUERIES_PATH=external/BrowseComp-Plus/topics-qrels/queries.tsv
export BROWSECOMPPLUS_QRELS_GOLD_PATH=external/BrowseComp-Plus/topics-qrels/qrel_golds.txt
export BROWSECOMPPLUS_QRELS_EVIDENCE_PATH=external/BrowseComp-Plus/topics-qrels/qrel_evidence.txt
export BROWSECOMPPLUS_CORPUS_JSONL=benchmarks/harness1/browsecompplus_corpus.jsonl
python run_public_benchmarks.py --benchmarks harness1/browsecompplus --candidate-k 40 --systems fixed_flow_model_qr,preset_flow_model_router,agentic_fixed_flow_rule_reflection,agentic_preset_flows_rule_reflection,one_shot_code_gen_rule_policy,agentic_code_gen_rule_reflection --output harness1_browsecompplus_results.json --report harness1_browsecompplus_report.md
```

Run the real codegen smoke through the local Codex login path:

```bash
python run_public_benchmarks.py \
  --benchmarks beir/scifact \
  --beir-query-limit 1 \
  --systems fixed_understanding_rewrite_hybrid_rerank,real_codegen_search_as_code \
  --candidate-k 20 \
  --real-codegen-provider codex-cli \
  --codex-reasoning-effort low \
  --output real_codegen_demo_results.json \
  --report real_codegen_demo_report.md
```

The main benchmark uses local deterministic code generation for reproducibility.
Use `real_codegen_search_as_code` when measuring true model generation latency,
invalid-code rate, repair rate, and retrieval quality.

## Optional API Server

```bash
python -m real_search_stack.api_server
```

This exposes:

- `POST /query_understanding`
- `POST /entity_linking`
- `POST /search`
- `POST /rerank`

The server loads `sac_benchmark_dataset/data/corpus.jsonl` from this repo.
