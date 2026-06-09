# Real LLM Search-as-Code Matrix

## Setup

- Dataset: `sac-codegen-v3` / split `test`
- Tasks: `sac-005, sac-028, sac-038, sac-042, sac-043`
- Candidate budget: `120`
- Provider: `codex-cli` / model `codex default`
- Metric: `Recall@10`

## Real LLM Results

| System | Recall@10 | Total ms | LLM ms | Exec ms | Search calls | QR calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|---:|
| `real_preset_flow_llm_router` | 0.4400 | 9370.0 | 9255.8 | 114.2 | 1.80 | 0.00 | 49.0 |
| `real_agentic_preset_flow_llm_reflection` | 0.3686 | 20311.6 | 20057.5 | 254.2 | 6.00 | 0.00 | 97.6 |
| `real_agentic_code_gen` | 0.3086 | 158909.7 | 158026.3 | 883.4 | 43.00 | 2.80 | 175.2 |
| `real_fixed_flow_llm_qr` | 0.2686 | 9544.9 | 9255.8 | 289.1 | 4.00 | 0.00 | 120.0 |
| `real_one_shot_code_gen` | 0.2686 | 48706.3 | 48327.9 | 378.4 | 12.60 | 1.00 | 92.2 |
| `real_agentic_fixed_flow_llm_reflection` | 0.2286 | 19996.4 | 18835.7 | 1160.7 | 4.80 | 0.00 | 655.8 |

## Compared With Existing Rule-Backed Matrix

This uses the already-completed `experiment_matrix_results.json`. The subset recall is recomputed on the same selected qids; full-run latency is from the full 31-query run.

| Rule-backed system | Subset Recall@10 | Full Recall@10 | Full total ms |
|---|---:|---:|---:|
| `agentic_code_gen_rule_reflection` | 0.6114 | 0.4712 | 3338.5 |
| `agentic_preset_flows_rule_reflection` | 0.6000 | 0.4655 | 1104.2 |
| `agentic_fixed_flow_rule_reflection` | 0.2686 | 0.2785 | 7775.8 |
| `fixed_flow_model_qr` | 0.2286 | 0.1857 | 3556.8 |
| `one_shot_code_gen_rule_policy` | 0.2286 | 0.1857 | 3238.0 |
| `preset_flow_model_router` | 0.1286 | 0.2083 | 1770.7 |

## Readout

- Real agentic codegen reaches Recall@10 `0.3086` with `158026.3` ms/query spent in LLM generation/reflection.
- Real agentic preset flow reaches Recall@10 `0.3686`; this tests whether model reflection can choose useful follow-up stacks without writing code.
- Existing rule-backed agentic codegen subset Recall@10 is `0.6114`. The gap to real LLM codegen is a direct reliability target.

## Per-Query

### sac-005

SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?

Relevant docs: `acct-bluepeak, acct-quartzbio, adv-atlas-rerank-4520, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.2000 | `cluster-atlas-rerank-4520-release-015, ticket-sec-1899, cluster-atlas-rerank-4520-ticket-053, cluster-atlas-rerank-4520-ticket-013, cluster-atlas-rerank-4520-dashboard-060` |
| `real_preset_flow_llm_router` | 0.2000 | `ticket-sec-1899, decoy-ticket-sec-1902, decoy-ticket-sec-1906, decoy-ticket-sec-1211, decoy-ticket-sec-1903` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0000 | `cluster-atlas-rerank-4520-email-056, cluster-atlas-rerank-4520-email-016, cluster-atlas-rerank-4520-postmortem-008, cluster-atlas-rerank-4520-meeting-024, cluster-atlas-rerank-4520-release-005` |
| `real_agentic_preset_flow_llm_reflection` | 0.2000 | `ticket-sec-1899, cluster-atlas-rerank-4520-release-035, cluster-atlas-rerank-4520-ticket-003, cluster-atlas-rerank-4520-ticket-043, cluster-atlas-rerank-4520-approval-027` |
| `real_one_shot_code_gen` | 0.2000 | `ticket-sec-1899, decoy-ticket-sec-1776, decoy-ticket-sec-1352, decoy-ticket-sec-1351, decoy-ticket-sec-1771` |
| `real_agentic_code_gen` | 0.2000 | `ticket-sec-1899, cluster-atlas-rerank-4520-ticket-013, cluster-atlas-rerank-4520-ticket-033, decoy-ticket-sec-1352, decoy-ticket-sec-1767` |

### sac-028

A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

Relevant docs: `acct-quartzbio, adv-atlas-rerank-4520, esc-quartzbio, rel-atlas-4-9-0, runbook-regulated-upgrade`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-namespace-decoy-0322, v3-namespace-decoy-0007, v3-namespace-decoy-0002, v3-namespace-decoy-0337, v3-namespace-decoy-0017` |
| `real_preset_flow_llm_router` | 0.0000 | `approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0198, v3-namespace-decoy-0178, v3-namespace-decoy-0278` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0000 | `v3-namespace-decoy-0308, v3-namespace-decoy-0088, v3-namespace-decoy-0068, v3-namespace-decoy-0108, v3-namespace-decoy-0208` |
| `real_agentic_preset_flow_llm_reflection` | 0.0000 | `approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0072, v3-namespace-decoy-0092, v3-namespace-decoy-0032` |
| `real_one_shot_code_gen` | 0.0000 | `approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0007, v3-namespace-decoy-0002, v3-namespace-decoy-0022` |
| `real_agentic_code_gen` | 0.2000 | `approval-quartzbio-namespace-proof, meet-quartzbio, esc-quartzbio, v3-namespace-decoy-0017, v3-namespace-decoy-0032` |

### sac-038

For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?

Relevant docs: `acct-contoso, adv-beacon-oauth-3771, alias-customer-codenames, approval-beacon-contoso-may06, esc-contoso, rel-beacon-3-14-0, rel-beacon-3-14-1`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `real_preset_flow_llm_router` | 0.0000 | `warroom-r7-june-critical-roster, approval-atlas-northwind-final, approval-quartzbio-namespace-proof, eval-sac-policy, rollout-riverline-second-blocker-ledger` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `real_agentic_preset_flow_llm_reflection` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0431, v3-approval-decoy-0401, v3-approval-decoy-0281, v3-approval-decoy-0461` |
| `real_one_shot_code_gen` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `real_agentic_code_gen` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |

### sac-042

For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?

Relevant docs: `eval-sac-policy, policy-sac-latency-ledger-v3`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.5000 | `policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144` |
| `real_preset_flow_llm_router` | 1.0000 | `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, source-authority-matrix-v3` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0244, v3-policy-decoy-0654, v3-policy-decoy-0459` |
| `real_agentic_preset_flow_llm_reflection` | 0.5000 | `policy-sac-latency-ledger-v3, v3-policy-decoy-0014, v3-policy-decoy-0164, v3-policy-decoy-0664, v3-policy-decoy-0064` |
| `real_one_shot_code_gen` | 0.5000 | `policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144` |
| `real_agentic_code_gen` | 0.5000 | `policy-sac-latency-ledger-v3, v3-policy-decoy-0684, v3-policy-decoy-0184, v3-policy-decoy-0014, v3-policy-decoy-0189` |

### sac-043

A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?

Relevant docs: `policy-reflection-missing-evidence-v3, source-authority-matrix-v3`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0095, v3-reflection-decoy-0495, v3-reflection-decoy-0295, v3-reflection-decoy-0195` |
| `real_preset_flow_llm_router` | 1.0000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, source-authority-matrix-v3, policy-sac-latency-ledger-v3` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0095, v3-reflection-decoy-0495, v3-reflection-decoy-0405, v3-reflection-decoy-0295` |
| `real_agentic_preset_flow_llm_reflection` | 1.0000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, source-authority-matrix-v3, rollout-riverline-second-blocker-ledger, approval-beacon-contoso-may06` |
| `real_one_shot_code_gen` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007` |
| `real_agentic_code_gen` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007` |

