# Search-as-Code Codegen Benchmark

This repo contains the Search-as-Code prototype and benchmark artifacts for comparing generated retrieval programs against fixed enterprise search flows.

## What Is Included

- `sac_benchmark_dataset/`: synthetic enterprise knowledge-base dataset with 6,010 documents, 48 tasks, BEIR exports, hard-negative labels, generator, validator, and audit tooling.
- `real_search_stack/`: open-source search APIs built on BM25, sentence-transformers dense retrieval, spaCy query understanding/entity extraction, optional Wikidata linking, and cross-encoder reranking.
- `run_sac_dataset_benchmark.py`: main benchmark runner for fixed BM25, dense, hybrid, hybrid+rerank, fixed enriched, one-shot generated Search-as-Code, agentic fixed-flow calls, naive reflective Search-as-Code, and iterative agentic Search-as-Code flows.
- `run_experiment_matrix.py`: presentation-aligned matrix runner for fixed flow, agentic fixed flow, preset flow, agentic preset flow, one-shot codegen, and agentic codegen.
- `run_real_llm_matrix.py`: focused real-LLM matrix runner that uses Codex CLI for QR/router/planner/reflection decisions and real codegen.
- `run_public_benchmarks.py`: public benchmark sanity-check runner for BEIR/SciFact and HotpotQA dev-distractor slices.
- `merge_eval_reports.py`: merges custom, real LLM, real codegen, public, and legacy eval outputs into one executive report.
- `llm_search_codegen.py`: real LLM-backed Search-as-Code generator with `codex-cli` and `openai` providers, AST validation, sandbox execution, and one-shot repair support.
- `skills/search-as-code-codegen/`: reusable Codex skill that defines the Search-as-Code runtime/tool contract for real code generation.
- `experiment_matrix_results.json`: latest presentation-aligned experiment matrix payload.
- `experiment_matrix_report.md`: latest presentation-aligned experiment matrix report.
- `sac_benchmark_results.json`: legacy broad benchmark result payload.
- `sac_benchmark_report.md`: legacy broad benchmark report, focused on Recall@10.
- `public_benchmark_results.json`: latest public benchmark sanity-check payload.
- `public_benchmark_report.md`: latest public benchmark sanity-check report.
- `real_codegen_demo_results.json` and `real_codegen_demo_report.md`: 1-query real LLM codegen smoke using the local Codex CLI login path.
- `real_codegen_retest_results.json` and `real_codegen_retest_report.md`: 5-query real LLM retest comparing one-shot codegen and agentic codegen.
- `real_llm_matrix_results.json` and `real_llm_matrix_report.md`: 5-query real LLM matrix for QR, router, planner/reflection, and codegen variants.
- `combined_eval_results.json` and `combined_eval_report.md`: merged view across custom full matrix, focused real LLM matrix, real codegen retest, public benchmark checks, and legacy runs.
- `sac_benchmark_dataset_intro.md`: Chinese dataset intro with generation method, categories, statistics, and example tasks.
- `agentic_search_presentation.html`: mobile-friendly presentation for the final Search-as-Code story.

## Latest Result

Dataset: `sac-codegen-v3`

- Test split: 31 queries
- Corpus: 6,010 documents
- Primary metric: Recall@10
- Candidate opportunity: rerank systems retrieve up to 2,400 candidates before producing final top 10
| Architecture | System | Recall@10 | Total ms | Plan/code ms | Execution ms | Search calls | Rerank pairs | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Fixed flow | `fixed_flow_model_qr` | 0.1857 | 3556.8 | 0.0 | 3556.8 | 3.97 | 2400 | Query rewrite + multi-query hybrid + rerank |
| Preset flow | `preset_flow_model_router` | 0.2083 | 1770.7 | 0.0 | 1770.7 | 2.00 | 1252 | Router picks one preset search stack |
| One-shot codegen | `one_shot_code_gen_rule_policy` | 0.1857 | 3238.0 | 0.1 | 3237.8 | 6.97 | 2400 | Python retrieval program, one execution |
| Agentic fixed flow | `agentic_fixed_flow_rule_reflection` | 0.2785 | 7775.8 | 0.2 | 7775.5 | 12.39 | 5189 | Repeated fixed-flow calls with reflection |
| Agentic preset flow | `agentic_preset_flows_rule_reflection` | 0.4655 | 1104.2 | 5.4 | 1098.8 | 6.10 | 733 | Reflection adds missing preset stacks |
| Agentic codegen | `agentic_code_gen_rule_reflection` | 0.4712 | 3338.5 | 0.2 | 3338.2 | 7.16 | 2400 | Generated code with evidence-goal reflection |

v3 is deliberately harder than v2: it adds alias/code-name tasks, source-authority disambiguation, stale approval ledgers, policy near-duplicates, and thousands of same-topic distractors. The current conclusion is sharper: one-shot codegen does not beat the fixed baseline. The lift comes from agentic evidence coverage: either selecting additional preset stacks after reflection, or generating retrieval code that can directly control routes, filters, and evidence preselection.

## Public Benchmark Sanity Check

These runs use known public benchmarks to check that the implementation behaves sensibly outside the custom enterprise dataset. They are not official leaderboard submissions.

| Benchmark | Setting | Generated SaC Recall@10 | Strong fixed Recall@10 | Readout |
|---|---|---:|---:|---|
| BEIR/SciFact | Full BEIR corpus, 5,183 docs, 300 queries | 0.8439 | 0.8278 | Small recall lift, higher search-call cost |
| HotpotQA dev-distractor | Official contexts pooled across 100 examples, 991 docs | 0.9550 | 0.9550 | Ties fixed enriched baseline, slightly higher cost |

The public check is useful for credibility, but it does not isolate enterprise-style control problems such as source authority, alias resolution, hard-negative intrusion, and evidence-category reflection. That is why the custom dataset remains the main decision benchmark.

## Real LLM Codegen Smoke

The full benchmark tables use deterministic Search-as-Code generators for
reproducibility. A separate smoke path now runs true model-generated code:

- `real_codegen_search_as_code` calls `LLMSearchCodeGenerator`.
- Default provider is `codex-cli`, which uses the local Codex app login and does not need `OPENAI_API_KEY`.
- Optional provider `openai` uses the Responses API and requires `OPENAI_API_KEY`.
- Generated code is AST-validated, executed in a restricted namespace, and can run one repair turn after a runtime error.

Latest smoke: BEIR/SciFact, 5,183 documents, 1 query. End-to-end latency was about 49.5s: 49.2s code generation plus 265.5ms execution. The generated program made 3 search calls and used 1 rerank call. This is proof of execution, not a quality benchmark.

## Real LLM Matrix

Focused enterprise sample: `sac-005, sac-028, sac-038, sac-042, sac-043`
with candidate budget `120`. This run replaces rule-backed QR/router/planner
and reflection with structured Codex CLI calls, then compares with real codegen.

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

- Focused real LLM sample: agentic codegen reaches `1.0000` Recall@10, agentic preset reaches `0.8114`, one-shot codegen reaches `0.7114`.
- Full custom deterministic test: agentic codegen `0.4712`, agentic preset `0.4655`, fixed flow `0.1857`.
- Public sanity checks remain strong: generated Search-as-Code reaches `0.8439` on BEIR/SciFact and ties fixed enriched retrieval at `0.9550` on HotpotQA dev-distractor.
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
python run_real_llm_matrix.py --candidate-k 120 --tool-candidate-k 120
python merge_eval_reports.py
python run_public_benchmarks.py --benchmarks beir/scifact,hotpotqa/distractor --hotpot-limit 100 --candidate-k 40 --generated-branch-top-k 20 --generated-max-rerank-candidates 40 --no-per-query
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
