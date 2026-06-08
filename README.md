# Search-as-Code Codegen Benchmark

This repo contains the Search-as-Code prototype and benchmark artifacts for comparing generated retrieval programs against fixed enterprise search flows.

## What Is Included

- `sac_benchmark_dataset/`: synthetic enterprise knowledge-base dataset with 6,010 documents, 48 tasks, BEIR exports, hard-negative labels, generator, validator, and audit tooling.
- `real_search_stack/`: open-source search APIs built on BM25, sentence-transformers dense retrieval, spaCy query understanding/entity extraction, optional Wikidata linking, and cross-encoder reranking.
- `run_sac_dataset_benchmark.py`: main benchmark runner for fixed BM25, dense, hybrid, hybrid+rerank, fixed enriched, one-shot generated Search-as-Code, and reflective generated Search-as-Code flows.
- `sac_benchmark_results.json`: latest benchmark result payload.
- `sac_benchmark_report.md`: latest benchmark report, focused on Recall@10.
- `sac_benchmark_dataset_intro.md`: Chinese dataset intro with generation method, categories, statistics, and example tasks.
- `agentic_search_presentation.html`: mobile-friendly presentation for the final Search-as-Code story.

## Latest Result

Dataset: `sac-codegen-v3`

- Test split: 31 queries
- Corpus: 6,010 documents
- Primary metric: Recall@10
- Candidate opportunity: rerank systems retrieve up to 2,400 candidates before producing final top 10

| System | Recall@10 | Mean latency ms | Notes |
|---|---:|---:|---|
| `fixed_bm25` | 0.2304 | 11.0 | Strong lexical baseline across full corpus |
| `fixed_hybrid` | 0.2286 | 20.1 | No reranking |
| `generated_search_as_code` | 0.1857 | 4076.7 | Dynamic routes, search modes, budgets, and rerank set |
| `generated_reflective_search_as_code` | 0.1857 | 3893.1 | Reflection path currently does not trigger enough |
| `fixed_understanding_rewrite_hybrid_rerank` | 0.1857 | 4077.7 | Fixed enriched flow with understanding, entity linking, rewrite, hybrid, rerank |
| `fixed_hybrid_rerank` | 0.1857 | 4049.5 | 2,400-candidate rerank budget |
| `fixed_hybrid_rerank_small_budget` | 0.1714 | 794.6 | 400-candidate rerank budget |
| `fixed_semantic_dense` | 0.0932 | 19.2 | Dense-only |

v3 is deliberately harder than v2: it adds alias/code-name tasks, source-authority disambiguation, stale approval ledgers, policy near-duplicates, and thousands of same-topic distractors. The current conclusion is intentionally nuanced: Search-as-Code is useful for making retrieval control flow inspectable and dynamic, but it does not automatically beat a strong fixed enriched baseline without a better reflection policy and better rerank/evidence selection.

## Reproduce

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python sac_benchmark_dataset/validate_dataset.py
python sac_benchmark_dataset/audit_dataset.py --write-report
python run_sac_dataset_benchmark.py --split test
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
