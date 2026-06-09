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
| `real_agentic_code_gen` | 1.0000 | 136271.9 | 135929.4 | 342.5 | 21.20 | 2.00 | 69.2 |
| `real_agentic_preset_flow_llm_reflection` | 0.8114 | 28692.8 | 28436.5 | 256.4 | 6.20 | 0.00 | 97.6 |
| `real_one_shot_code_gen` | 0.7114 | 62041.8 | 61891.1 | 150.7 | 6.60 | 1.00 | 39.2 |
| `real_agentic_fixed_flow_llm_reflection` | 0.4686 | 30620.5 | 29223.8 | 1396.7 | 6.00 | 0.00 | 840.0 |
| `real_preset_flow_llm_router` | 0.4400 | 11638.1 | 11523.4 | 114.8 | 1.80 | 0.00 | 49.0 |
| `real_fixed_flow_llm_qr` | 0.1686 | 11817.1 | 11523.4 | 293.7 | 4.00 | 0.00 | 120.0 |

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

- Real agentic codegen reaches Recall@10 `1.0000` with `135929.4` ms/query spent in LLM generation/reflection.
- Real agentic preset flow reaches Recall@10 `0.8114`; this tests whether model reflection can choose useful follow-up stacks without writing code.
- Real LLM agentic codegen now exceeds the existing rule-backed subset (`1.0000` vs `0.6114`), but at much higher LLM generation latency.

## Per-Query

### sac-005

SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?

Relevant docs: `acct-bluepeak, acct-quartzbio, adv-atlas-rerank-4520, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.2000 | `cluster-atlas-rerank-4520-release-005, cluster-atlas-rerank-4520-release-045, cluster-atlas-rerank-4520-release-015, cluster-atlas-rerank-4520-release-055, ticket-sec-1899` |
| `real_preset_flow_llm_router` | 0.2000 | `ticket-sec-1899, decoy-ticket-sec-1902, decoy-ticket-sec-1906, decoy-ticket-sec-1211, decoy-ticket-sec-1903` |
| `real_agentic_fixed_flow_llm_reflection` | 0.2000 | `esc-greenhouse, esc-novafoods, ticket-sec-1899, ticket-sec-1690, cluster-atlas-rerank-4520-release-005` |
| `real_agentic_preset_flow_llm_reflection` | 0.6000 | `ticket-sec-1899, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, warroom-r7-june-critical-roster, acct-novafoods` |
| `real_one_shot_code_gen` | 0.2000 | `ticket-sec-1899, ticket-sec-1690, ticket-sec-1775, ticket-sec-1604, ticket-sec-1811` |
| `real_agentic_code_gen` | 1.0000 | `ticket-sec-1899, rel-atlas-4-9-0, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-bluepeak` |

### sac-028

A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

Relevant docs: `acct-quartzbio, adv-atlas-rerank-4520, esc-quartzbio, rel-atlas-4-9-0, runbook-regulated-upgrade`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-namespace-decoy-0322, v3-namespace-decoy-0007, v3-namespace-decoy-0312, v3-namespace-decoy-0197, v3-namespace-decoy-0002` |
| `real_preset_flow_llm_router` | 0.0000 | `approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0198, v3-namespace-decoy-0178, v3-namespace-decoy-0278` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0000 | `approval-quartzbio-namespace-proof, v3-namespace-decoy-0005, v3-namespace-decoy-0085, v3-namespace-decoy-0035, v3-namespace-decoy-0075` |
| `real_agentic_preset_flow_llm_reflection` | 0.6000 | `approval-quartzbio-namespace-proof, esc-quartzbio, rel-atlas-4-9-0, ticket-sec-1899, acct-quartzbio` |
| `real_one_shot_code_gen` | 1.0000 | `approval-quartzbio-namespace-proof, esc-quartzbio, acct-quartzbio, runbook-regulated-upgrade, rel-atlas-4-9-0` |
| `real_agentic_code_gen` | 1.0000 | `approval-quartzbio-namespace-proof, ticket-sec-1899, rel-atlas-4-9-0, acct-quartzbio, alias-customer-codenames` |

### sac-038

For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?

Relevant docs: `acct-contoso, adv-beacon-oauth-3771, alias-customer-codenames, approval-beacon-contoso-may06, esc-contoso, rel-beacon-3-14-0, rel-beacon-3-14-1`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `real_preset_flow_llm_router` | 0.0000 | `warroom-r7-june-critical-roster, approval-atlas-northwind-final, approval-quartzbio-namespace-proof, eval-sac-policy, rollout-riverline-second-blocker-ledger` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `real_agentic_preset_flow_llm_reflection` | 0.8571 | `approval-beacon-contoso-may06, adv-beacon-oauth-3771, alias-customer-codenames, esc-contoso, acct-contoso` |
| `real_one_shot_code_gen` | 0.8571 | `approval-beacon-contoso-may06, esc-contoso, warroom-r7-june-critical-roster, adv-beacon-oauth-3771, acct-contoso` |
| `real_agentic_code_gen` | 1.0000 | `rel-beacon-3-14-0, alias-owner-directory, acct-urbannest, approval-beacon-contoso-may06, esc-contoso` |

### sac-042

For the CEO Search-as-Code readout, which latency number is primary: including code generation or execution-only?

Relevant docs: `eval-sac-policy, policy-sac-latency-ledger-v3`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.5000 | `policy-sac-latency-ledger-v3, v3-policy-decoy-0019, v3-policy-decoy-0014, v3-policy-decoy-0044, v3-policy-decoy-0144` |
| `real_preset_flow_llm_router` | 1.0000 | `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, source-authority-matrix-v3` |
| `real_agentic_fixed_flow_llm_reflection` | 1.0000 | `policy-sac-latency-ledger-v3, eval-sac-policy, source-authority-matrix-v3, v3-policy-decoy-0144, v3-policy-decoy-0444` |
| `real_agentic_preset_flow_llm_reflection` | 1.0000 | `policy-sac-latency-ledger-v3, eval-sac-policy, source-authority-matrix-v3, rel-rovo-5-3-0, rel-atlas-4-8-2` |
| `real_one_shot_code_gen` | 1.0000 | `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, rel-atlas-4-8-2, roadmap-rovo-sac` |
| `real_agentic_code_gen` | 1.0000 | `policy-sac-latency-ledger-v3, eval-sac-policy, policy-reflection-missing-evidence-v3, rel-atlas-4-8-2, roadmap-rovo-sac` |

### sac-043

A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?

Relevant docs: `policy-reflection-missing-evidence-v3, source-authority-matrix-v3`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-reflection-decoy-0502, v3-reflection-decoy-0507, v3-reflection-decoy-0482, v3-reflection-decoy-0287, v3-reflection-decoy-0282` |
| `real_preset_flow_llm_router` | 1.0000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, source-authority-matrix-v3, policy-sac-latency-ledger-v3` |
| `real_agentic_fixed_flow_llm_reflection` | 1.0000 | `policy-reflection-missing-evidence-v3, source-authority-matrix-v3, negative-forgedeploy-novafoods, v3-reflection-decoy-0012, v3-reflection-decoy-0017` |
| `real_agentic_preset_flow_llm_reflection` | 1.0000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, policy-sac-latency-ledger-v3, source-authority-matrix-v3, warroom-r7-june-critical-roster` |
| `real_one_shot_code_gen` | 0.5000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, rollout-riverline-second-blocker-ledger, approval-quartzbio-namespace-proof, policy-sac-latency-ledger-v3` |
| `real_agentic_code_gen` | 1.0000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, policy-sac-latency-ledger-v3, source-authority-matrix-v3, rollout-riverline-second-blocker-ledger` |

