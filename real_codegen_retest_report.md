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

- Real agentic codegen improves Recall@10 by `+0.0400` vs real one-shot (`0.3086` vs `0.2686`), but costs `158504.5` ms total (`157409.1` ms codegen + `1093.9` ms execution).
- Real one-shot codegen matches the deterministic one-shot/fixed recall on this sample at `0.2686`, but takes `48775.0` ms total with `48328.6` ms spent generating code.
- Real agentic generated a reflection for every query and needed `4` runtime repairs; this is the main reliability and latency gap to close.
- Deterministic agentic codegen remains the upper-bound design target on this sample: Recall@10 `0.6114` at `353.4` ms total.
- The quality gap is not from the search stack itself; it is from the model's ability to write the right evidence-coverage program reliably.

## Summary

| System | Recall@10 | nDCG@10 | MRR@10 | Hard-neg hit@10 | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs | Repairs | Reflections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `generated_iterative_agentic_search_as_code` | 0.6114 | 0.5191 | 0.5833 | 0.2000 | 353.4 | 0.2 | 353.3 | 8.80 | 120.0 | 0 | 0 |
| `real_agentic_codegen_search_as_code` | 0.3086 | 0.4020 | 0.8667 | 0.4000 | 158504.5 | 157409.1 | 1093.9 | 41.40 | 173.2 | 4 | 5 |
| `fixed_understanding_rewrite_hybrid_rerank` | 0.2686 | 0.3681 | 0.8000 | 0.2000 | 298.5 | 0.0 | 298.4 | 4.00 | 120.0 | 0 | 0 |
| `generated_search_as_code` | 0.2686 | 0.3681 | 0.8000 | 0.2000 | 301.2 | 0.1 | 301.1 | 8.00 | 120.0 | 0 | 0 |
| `real_codegen_search_as_code` | 0.2686 | 0.3681 | 0.8000 | 0.4000 | 48775.0 | 48328.6 | 446.4 | 12.60 | 92.2 | 0 | 0 |

## Per-Query Recall

| Query | Category | `generated_iterative_agentic_search_as_code` | `real_agentic_codegen_search_as_code` | `fixed_understanding_rewrite_hybrid_rerank` | `generated_search_as_code` | `real_codegen_search_as_code` |
|---|---|---:|---:|---:|---:|---:|
| sac-005 | exact_identifier_lookup | 0.4000 | 0.2000 | 0.2000 | 0.2000 | 0.2000 |
| sac-028 | multi_hop | 0.8000 | 0.2000 | 0.0000 | 0.0000 | 0.0000 |
| sac-038 | authority_disambiguation | 0.8571 | 0.1429 | 0.1429 | 0.1429 | 0.1429 |
| sac-042 | policy_lookup | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| sac-043 | reflection_required | 0.5000 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |

## Real Codegen Behavior Notes

### sac-005 - exact_identifier_lookup

SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?

- Real agentic delta vs real one-shot: `+0.0000` Recall@10 (0.2000 vs 0.2000).
- Reflection codegen: `78584.0` ms; initial candidates `120`; initial top ids `cluster-atlas-rerank-4520-dashboard-040, cluster-atlas-rerank-4520-rollout-032, cluster-atlas-rerank-4520-email-056, cluster-atlas-rerank-4520-email-016, cluster-atlas-rerank-4520-postmortem-008`.
- One-shot top ids: `ticket-sec-1899, decoy-ticket-sec-1776, decoy-ticket-sec-1352, decoy-ticket-sec-1351, decoy-ticket-sec-1771`.
- Agentic top ids: `ticket-sec-1899, cluster-atlas-rerank-4520-ticket-013, cluster-atlas-rerank-4520-ticket-033, decoy-ticket-sec-1352, decoy-ticket-sec-1767`.

### sac-028 - multi_hop

A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

- Real agentic delta vs real one-shot: `+0.2000` Recall@10 (0.2000 vs 0.0000).
- Reflection codegen: `73039.3` ms; initial candidates `120`; initial top ids `v3-namespace-decoy-0035, v3-namespace-decoy-0020, v3-namespace-decoy-0040, v3-namespace-decoy-0015, v3-namespace-decoy-0005`.
- One-shot top ids: `approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0007, v3-namespace-decoy-0002, v3-namespace-decoy-0022`.
- Agentic top ids: `approval-quartzbio-namespace-proof, meet-quartzbio, esc-quartzbio, v3-namespace-decoy-0017, v3-namespace-decoy-0032`.

### sac-038 - authority_disambiguation

For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?

- Real agentic delta vs real one-shot: `+0.0000` Recall@10 (0.1429 vs 0.1429).
- Reflection codegen: `64217.0` ms; initial candidates `87`; initial top ids `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241`.
- One-shot top ids: `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241`.
- Agentic top ids: `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241`.

### sac-042 - policy_lookup

For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?

- Real agentic delta vs real one-shot: `+0.0000` Recall@10 (0.5000 vs 0.5000).
- Reflection codegen: `50956.6` ms; initial candidates `95`; initial top ids `policy-sac-latency-ledger-v3, v3-policy-decoy-0014, v3-policy-decoy-0019, v3-policy-decoy-0664, v3-policy-decoy-0654`.
- One-shot top ids: `policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144`.
- Agentic top ids: `policy-sac-latency-ledger-v3, v3-policy-decoy-0014, v3-policy-decoy-0019, v3-policy-decoy-0684, v3-policy-decoy-0184`.

### sac-043 - reflection_required

A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?

- Real agentic delta vs real one-shot: `+0.0000` Recall@10 (0.5000 vs 0.5000).
- Reflection codegen: `75035.6` ms; initial candidates `0`; initial top ids ``.
- One-shot top ids: `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007`.
- Agentic top ids: `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007`.

## Method Notes

- Real one-shot codegen performs one model code-generation call, then executes the generated program with one repair opportunity on runtime error.
- Real agentic codegen performs initial generation, executes it, builds an observation from trace/top hits/tool counts, then generates and executes a revised program.
- Ground-truth qrels and hard-negative labels are used only by the evaluator, not in the reflection prompt.
- Latency is split into total wall time, model codegen time, and execution time.
