# Search-as-Code Codegen Benchmark

This repo contains the Search-as-Code prototype and benchmark artifacts for comparing generated retrieval programs against fixed enterprise search flows.

## What Is Included

- `sac_benchmark_dataset/`: synthetic enterprise knowledge-base dataset with 6,010 documents, 48 tasks, BEIR exports, hard-negative labels, generator, validator, and audit tooling.
- `real_search_stack/`: open-source search APIs built on BM25, sentence-transformers dense retrieval, spaCy query understanding/entity extraction, optional Wikidata linking, and cross-encoder reranking.
- `run_sac_dataset_benchmark.py`: main benchmark runner for fixed BM25, dense, hybrid, hybrid+rerank, fixed enriched, one-shot generated Search-as-Code, agentic fixed-flow calls, naive reflective Search-as-Code, and iterative agentic Search-as-Code flows.
- `run_public_benchmarks.py`: public benchmark sanity-check runner for BEIR/SciFact and HotpotQA dev-distractor slices.
- `sac_benchmark_results.json`: latest benchmark result payload.
- `sac_benchmark_report.md`: latest benchmark report, focused on Recall@10.
- `public_benchmark_results.json`: latest public benchmark sanity-check payload.
- `public_benchmark_report.md`: latest public benchmark sanity-check report.
- `sac_benchmark_dataset_intro.md`: Chinese dataset intro with generation method, categories, statistics, and example tasks.
- `agentic_search_presentation.html`: mobile-friendly presentation for the final Search-as-Code story.

## Latest Result

Dataset: `sac-codegen-v3`

- Test split: 31 queries
- Corpus: 6,010 documents
- Primary metric: Recall@10
- Candidate opportunity: rerank systems retrieve up to 2,400 candidates before producing final top 10
- Quality score: weighted Recall@10, nDCG@10, MRR@10, all-evidence recovery, and hard-negative intrusion penalty

| Architecture | System | Quality | Recall@10 | Mean latency ms | Search calls | Notes |
|---|---|---:|---:|---:|---:|---|
| Fixed flow baseline | `fixed_understanding_rewrite_hybrid_rerank` | 23.2 | 0.1857 | 3231.2 | 3.97 | Fixed understanding + rewrite + hybrid retrieval + rerank |
| Generated flow | `generated_search_as_code` | 23.2 | 0.1857 | 3263.1 | 6.97 | One-shot generated route plan with exposed SDK parameters |
| Agentic fixed-flow calls | `agentic_fixed_flow_iterative` | 33.1 | 0.2694 | 3991.5 | 12.71 | Agent iteratively calls the same fixed flow with new queries |
| Agentic codegen | `generated_iterative_agentic_search_as_code` | 47.1 | 0.4712 | 3362.5 | 7.16 | Generated code iterates with evidence-coverage reflection |

v3 is deliberately harder than v2: it adds alias/code-name tasks, source-authority disambiguation, stale approval ledgers, policy near-duplicates, and thousands of same-topic distractors. The current conclusion is sharper: one-shot generated flow does not beat the fixed baseline even with richer SDK parameters. Agentic iteration helps when the agent can only call the fixed flow, but agentic codegen is materially better because it can reflect on missing evidence and directly control the search stack.

## Public Benchmark Sanity Check

These runs use known public benchmarks to check that the implementation behaves sensibly outside the custom enterprise dataset. They are not official leaderboard submissions.

| Benchmark | Setting | Generated SaC Recall@10 | Strong fixed Recall@10 | Readout |
|---|---|---:|---:|---|
| BEIR/SciFact | Full BEIR corpus, 5,183 docs, 300 queries | 0.8439 | 0.8278 | Small recall lift, higher search-call cost |
| HotpotQA dev-distractor | Official contexts pooled across 100 examples, 991 docs | 0.9550 | 0.9550 | Ties fixed enriched baseline, slightly higher cost |

The public check is useful for credibility, but it does not isolate enterprise-style control problems such as source authority, alias resolution, hard-negative intrusion, and evidence-category reflection. That is why the custom dataset remains the main decision benchmark.

## Reproduce

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python sac_benchmark_dataset/validate_dataset.py
python sac_benchmark_dataset/audit_dataset.py --write-report
python run_sac_dataset_benchmark.py --split test
python run_public_benchmarks.py --benchmarks beir/scifact,hotpotqa/distractor --hotpot-limit 100 --candidate-k 40 --generated-branch-top-k 20 --generated-max-rerank-candidates 40 --no-per-query
```

The benchmark uses local deterministic code generation for reproducibility. Hosted LLM code-generation latency is not included in the checked-in result, but generation time is tracked separately in the JSON so it can be replaced with a real model latency sensitivity analysis.

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
