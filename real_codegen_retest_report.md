# Real LLM Codegen Retest

This retest compares one-shot real LLM Search-as-Code with an agentic real-codegen variant that runs an initial generated program, reflects on the observed evidence, then generates and executes a revised program.

- Dataset: `sac-codegen-v3`
- Tasks: `5` selected enterprise queries
- Task ids: `sac-005, sac-028, sac-038, sac-042, sac-043`
- Corpus documents: `6010`
- Candidate budget: `120`
- Provider: `codex-cli`
- Codex reasoning effort: `low`

## Readout

- Real agentic codegen improves Recall@10 by `+0.2619` vs real one-shot (`1.0000` vs `0.7381`), but costs `136272.4` ms total (`135929.5` ms codegen + `342.9` ms execution).
- Real one-shot codegen matches the deterministic one-shot/fixed recall on this sample at `0.7381`, but takes `62038.7` ms total with `61891.3` ms spent generating code.
- Real agentic generated a reflection for every query and needed `0` runtime repairs; this is the main reliability and latency gap to close.
- Real agentic codegen now exceeds the deterministic proxy by `+0.3619` Recall@10, but costs `136272.4` ms vs `325.4` ms.

## Summary

| System | Recall@10 | nDCG@10 | MRR@10 | Hard-neg hit@10 | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs | Repairs | Reflections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `real_agentic_codegen_search_as_code` | 1.0000 | 0.9201 | 1.0000 | 0.2000 | 136272.4 | 135929.5 | 342.9 | 21.20 | 69.2 | 0 | 5 |
| `real_codegen_search_as_code` | 0.7381 | 0.7676 | 1.0000 | 0.4000 | 62038.7 | 61891.3 | 147.4 | 6.60 | 39.2 | 0 | 0 |
| `generated_iterative_agentic_search_as_code` | 0.6381 | 0.5351 | 0.5833 | 0.2000 | 325.4 | 0.2 | 325.1 | 8.80 | 120.0 | 0 | 0 |
| `generated_search_as_code` | 0.2952 | 0.4213 | 1.0000 | 0.2000 | 277.5 | 0.1 | 277.4 | 8.00 | 120.0 | 0 | 0 |
| `fixed_understanding_rewrite_hybrid_rerank` | 0.2619 | 0.3608 | 0.8000 | 0.2000 | 285.3 | 0.0 | 285.3 | 4.00 | 120.0 | 0 | 0 |

## Per-Query Recall

| Query | Category | `real_agentic_codegen_search_as_code` | `real_codegen_search_as_code` | `generated_iterative_agentic_search_as_code` | `generated_search_as_code` | `fixed_understanding_rewrite_hybrid_rerank` |
|---|---|---:|---:|---:|---:|---:|
| sac-005 | exact_identifier_lookup | 1.0000 | 0.3333 | 0.5000 | 0.1667 | 0.1667 |
| sac-028 | multi_hop | 1.0000 | 1.0000 | 0.8333 | 0.1667 | 0.0000 |
| sac-038 | authority_disambiguation | 1.0000 | 0.8571 | 0.8571 | 0.1429 | 0.1429 |
| sac-042 | policy_lookup | 1.0000 | 1.0000 | 0.5000 | 0.5000 | 0.5000 |
| sac-043 | reflection_required | 1.0000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |

## Real Codegen Behavior Notes

### sac-005 - exact_identifier_lookup

SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?

- Real agentic delta vs real one-shot: `+0.6667` Recall@10 (1.0000 vs 0.3333).
- Reflection codegen: `96781.9` ms; initial candidates `39`; initial top ids `ticket-sec-1899, approval-quartzbio-namespace-proof, acct-quartzbio, acct-bluepeak, rel-meridian-2-7-4`.
- One-shot top ids: `ticket-sec-1899, ticket-sec-1690, ticket-sec-1775, ticket-sec-1604, ticket-sec-1811`.
- Agentic top ids: `ticket-sec-1899, rel-atlas-4-9-0, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-bluepeak`.

### sac-028 - multi_hop

A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

- Real agentic delta vs real one-shot: `+0.0000` Recall@10 (1.0000 vs 1.0000).
- Reflection codegen: `79539.1` ms; initial candidates `35`; initial top ids `approval-quartzbio-namespace-proof, acct-quartzbio, rel-atlas-4-9-0, source-authority-matrix-v3, ticket-sec-1899`.
- One-shot top ids: `approval-quartzbio-namespace-proof, esc-quartzbio, acct-quartzbio, runbook-regulated-upgrade, rel-atlas-4-9-0`.
- Agentic top ids: `approval-quartzbio-namespace-proof, ticket-sec-1899, rel-atlas-4-9-0, acct-quartzbio, alias-customer-codenames`.

### sac-038 - authority_disambiguation

For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?

- Real agentic delta vs real one-shot: `+0.1429` Recall@10 (1.0000 vs 0.8571).
- Reflection codegen: `77592.4` ms; initial candidates `36`; initial top ids `approval-beacon-contoso-may06, acct-contoso, approval-atlas-northwind-final, rel-beacon-3-14-1, alias-customer-codenames`.
- One-shot top ids: `approval-beacon-contoso-may06, esc-contoso, warroom-r7-june-critical-roster, adv-beacon-oauth-3771, acct-contoso`.
- Agentic top ids: `rel-beacon-3-14-0, alias-owner-directory, acct-urbannest, approval-beacon-contoso-may06, esc-contoso`.

### sac-042 - policy_lookup

For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?

- Real agentic delta vs real one-shot: `+0.0000` Recall@10 (1.0000 vs 1.0000).
- Reflection codegen: `73780.6` ms; initial candidates `15`; initial top ids `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, rel-atlas-4-8-2, roadmap-rovo-sac`.
- One-shot top ids: `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, rel-atlas-4-8-2, roadmap-rovo-sac`.
- Agentic top ids: `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, rel-atlas-4-8-2, roadmap-rovo-sac`.

### sac-043 - reflection_required

A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?

- Real agentic delta vs real one-shot: `+0.5000` Recall@10 (1.0000 vs 0.5000).
- Reflection codegen: `79932.2` ms; initial candidates `17`; initial top ids `policy-reflection-missing-evidence-v3, approval-atlas-northwind-final, esc-novafoods, policy-sac-latency-ledger-v3, eval-sac-policy`.
- One-shot top ids: `policy-reflection-missing-evidence-v3, eval-sac-policy, rollout-riverline-second-blocker-ledger, approval-quartzbio-namespace-proof, policy-sac-latency-ledger-v3`.
- Agentic top ids: `policy-reflection-missing-evidence-v3, eval-sac-policy, policy-sac-latency-ledger-v3, source-authority-matrix-v3, rollout-riverline-second-blocker-ledger`.

## Method Notes

- Real one-shot codegen performs one model code-generation call, then executes the generated program with one repair opportunity on runtime error.
- Real agentic codegen performs initial generation, executes it, builds an observation from trace/top hits/tool counts, then generates and executes a revised program.
- Ground-truth qrels and hard-negative labels are used only by the evaluator, not in the reflection prompt.
- Latency is split into total wall time, model codegen time, and execution time.
