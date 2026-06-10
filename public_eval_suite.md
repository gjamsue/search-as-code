# Public Eval Suite

This is the reusable public evaluation track for Search-as-Code / agentic search experiments. It is intentionally separate from the custom enterprise benchmark.

## Why This Exists

The custom enterprise set is designed to expose agentic search strengths: source authority, alias resolution, hard negatives, evidence coverage, and reflection. Public datasets are used for a different purpose:

- confirm the system does not regress on recognizable retrieval tasks;
- keep fixed-flow baselines honest;
- show where codegen/agentic search does **not** automatically win;
- provide a reusable eval environment for future agentic-search variants.

## Current Public Sets

| Dataset | Scope | Docs | Queries | Why included | Caveat |
|---|---:|---:|---:|---|---|
| BEIR/SciFact | Scientific claim retrieval | 5,183 | 300 | Standard public IR sanity check with stable corpus/qrels | Not enterprise-style source-control search |
| HotpotQA dev-distractor slice | Multi-hop QA evidence retrieval | 991 | 100 | Public multi-hop check using official supporting-fact labels | Pooled local distractor contexts, not HotpotQA fullwiki and not official Harness-1 HotpotQA-subset |

Next public additions are tracked in `harness1_reproduction_todo.md`: BrowseComp+, FRAMES, Seal0QA, LongSealQA, Web, Patents, and SEC.

## Systems Compared

| System | Meaning |
|---|---|
| `fixed_flow_model_qr` | LLM/query-rewrite style fixed flow: query understanding -> rewrite -> multi-query hybrid retrieval -> rerank |
| `preset_flow_model_router` | Router picks one preset search stack |
| `agentic_fixed_flow_rule_reflection` | Planner/reflection calls fixed flow multiple times |
| `agentic_preset_flows_rule_reflection` | Router/reflection picks one or more preset stacks |
| `one_shot_code_gen_rule_policy` | One generated retrieval program controls search modes, budgets, and rerank |
| `agentic_code_gen_rule_reflection` | Generated retrieval program plus reflection-driven follow-up logic |

## Reproduce

Canonical command:

```bash
python run_public_eval_suite.py
```

Equivalent explicit command:

```bash
python run_public_benchmarks.py \
  --benchmarks beir/scifact,hotpotqa/distractor \
  --hotpot-limit 100 \
  --candidate-k 40 \
  --fixed-small-candidate-k 40 \
  --generated-branch-top-k 20 \
  --generated-max-rerank-candidates 40 \
  --systems fixed_flow_model_qr,preset_flow_model_router,agentic_fixed_flow_rule_reflection,agentic_preset_flows_rule_reflection,one_shot_code_gen_rule_policy,agentic_code_gen_rule_reflection \
  --no-per-query \
  --sample-codes 0 \
  --output public_variant_matrix_results.json \
  --report public_variant_matrix_report.md
```

Artifacts:

- `public_variant_matrix_results.json`: machine-readable results and latency breakdowns.
- `public_variant_matrix_report.md`: human-readable summary table.

## Latest Results

| Dataset | Best system | Best Recall@10 | Fixed flow Recall@10 | Agentic codegen Recall@10 | Readout |
|---|---|---:|---:|---:|---|
| BEIR/SciFact | `agentic_code_gen_rule_reflection` | 0.8254 | 0.8251 | 0.8254 | Effectively tied; fixed retrieval is already strong |
| HotpotQA dev-distractor slice | `fixed_flow_model_qr` | 0.9550 | 0.9550 | 0.9300 | Fixed flow wins; this setting does not need enterprise-style control |

Latency readout:

| Dataset | Fixed flow ms | One-shot codegen ms | Agentic codegen ms |
|---|---:|---:|---:|
| BEIR/SciFact | 325.4 | 365.8 | 386.0 |
| HotpotQA dev-distractor slice | 235.5 | 245.8 | 229.3 |

## Conclusion From Public Sets

The public suite confirms the more conservative conclusion:

- Search-as-Code / agentic search is **not** universally better than a strong fixed retrieval flow.
- On normal public retrieval and small pooled multi-hop QA, fixed flow is already very competitive.
- The value of agentic/codegen search shows up most clearly when the task requires source authority, evidence-category coverage, alias/entity constraints, hard-negative avoidance, or iterative recovery.

This is why the final evaluation needs both tracks:

- Public suite: credibility, baseline sanity, regression guardrail.
- Custom enterprise suite: targeted measurement of agentic-search value.

## Extension Rules

When adding a new public set:

- Add a loader in `run_public_benchmarks.py`.
- Preserve `doc_id` alignment with qrels and validate missing qrel IDs before running.
- Record backend type: static corpus, Chroma export, or live web.
- Keep deterministic proxy runs separate from real model/codegen runs.
- Do not compare live-web and static-corpus numbers without a backend column.
