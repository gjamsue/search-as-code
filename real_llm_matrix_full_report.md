# Real LLM Search-as-Code Matrix

## Setup

- Dataset: `sac-codegen-v3` / split `test`
- Tasks: `sac-001, sac-002, sac-004, sac-005, sac-007, sac-009, sac-011, sac-013, sac-014, sac-016, sac-018, sac-020, sac-022, sac-024, sac-025, sac-027, sac-028, sac-030, sac-032, sac-033, sac-035, sac-036, sac-037, sac-038, sac-039, sac-040, sac-041, sac-042, sac-043, sac-044, sac-045`
- Candidate budget: `120`
- Provider: `codex-cli` / model `codex default`
- Metric: `Recall@10`

## Real LLM Results

| System | Recall@10 | Total ms | LLM ms | Exec ms | Search calls | QR calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|---:|
| `real_agentic_code_gen` | 0.7081 | 159693.9 | 159078.5 | 615.5 | 32.81 | 2.00 | 76.1 |
| `real_agentic_preset_flow_llm_reflection` | 0.5809 | 35676.2 | 35349.2 | 327.0 | 7.58 | 0.00 | 114.8 |
| `real_one_shot_code_gen` | 0.5779 | 60593.7 | 60383.1 | 210.6 | 8.64 | 1.00 | 39.6 |
| `real_agentic_fixed_flow_llm_reflection` | 0.4307 | 40660.4 | 38583.4 | 2077.0 | 7.93 | 0.00 | 1072.3 |
| `real_preset_flow_llm_router` | 0.3689 | 13156.5 | 12991.1 | 165.4 | 1.90 | 0.00 | 67.9 |
| `real_fixed_flow_llm_qr` | 0.1837 | 13317.2 | 12991.1 | 326.1 | 4.00 | 0.00 | 120.0 |

## Compared With Existing Rule-Backed Matrix

This uses the already-completed `experiment_matrix_results.json`. The subset recall is recomputed on the same selected qids; full-run latency is from the full 31-query run.

| Rule-backed system | Subset Recall@10 | Full Recall@10 | Full total ms |
|---|---:|---:|---:|
| `agentic_preset_flows_rule_reflection` | 0.4627 | 0.4627 | 1104.2 |
| `agentic_code_gen_rule_reflection` | 0.4625 | 0.4625 | 3338.5 |
| `agentic_fixed_flow_rule_reflection` | 0.2852 | 0.2852 | 7775.8 |
| `preset_flow_model_router` | 0.2233 | 0.2233 | 1770.7 |
| `fixed_flow_model_qr` | 0.2018 | 0.2018 | 3556.8 |
| `one_shot_code_gen_rule_policy` | 0.2018 | 0.2018 | 3238.0 |

## Readout

- Real agentic codegen reaches Recall@10 `0.7081` with `159078.5` ms/query spent in LLM generation/reflection.
- Real agentic preset flow reaches Recall@10 `0.5809`; this tests whether model reflection can choose useful follow-up stacks without writing code.
- Real LLM agentic codegen now exceeds the existing rule-backed subset (`0.7081` vs `0.4625`), but at much higher LLM generation latency.

## Per-Query

### sac-001

For Northwind Health, which critical vulnerabilities affect products they run, what fixed versions are needed, and who owns the rollout?

Relevant docs: `acct-northwind, adv-atlas-saml-4102, approval-atlas-northwind-final, esc-northwind, rel-atlas-4-8-2, ticket-sec-1842`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.3333 | `adv-atlas-saml-4102, esc-northwind, cluster-customer-northwind-renewal-042, cluster-customer-northwind-renewal-018, cluster-customer-northwind-renewal-026` |
| `real_preset_flow_llm_router` | 0.1667 | `adv-atlas-saml-4102, cluster-customer-northwind-renewal-042, cluster-customer-northwind-renewal-018, cluster-customer-northwind-renewal-026, cluster-customer-northwind-renewal-034` |
| `real_agentic_fixed_flow_llm_reflection` | 0.6667 | `acct-northwind, adv-atlas-saml-4102, approval-atlas-northwind-final, esc-northwind, meet-northwind` |
| `real_agentic_preset_flow_llm_reflection` | 0.8333 | `acct-northwind, adv-atlas-saml-4102, ticket-sec-1842, approval-atlas-northwind-final, rel-compass-1-19-3` |
| `real_one_shot_code_gen` | 0.6667 | `alias-customer-codenames, adv-compass-csv-1440, adv-atlas-rerank-4520, adv-atlas-saml-4102, esc-northwind` |
| `real_agentic_code_gen` | 0.8333 | `adv-atlas-saml-4102, ticket-sec-1842, approval-atlas-northwind-final, acct-northwind, rel-rovo-5-3-0` |

### sac-002

Which red-risk customers renewing before July 1 have unresolved security or audit blockers, and what is the next action for each?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, esc-aster, esc-heliogrid, esc-northwind, esc-riverline, runbook-regulated-upgrade, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.4000 | `warroom-r7-june-critical-roster, esc-urbannest, meet-northwind, meet-heliogrid, meet-aster` |
| `real_preset_flow_llm_router` | 0.8000 | `warroom-r7-june-critical-roster, esc-urbannest, esc-riverline, esc-aster, acct-northwind` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `warroom-r7-june-critical-roster, ticket-sec-1604, ticket-sec-1899, ticket-sec-1842, esc-riverline` |
| `real_agentic_preset_flow_llm_reflection` | 0.2000 | `warroom-r7-june-critical-roster, ticket-sec-1842, ticket-sec-1811, ticket-sec-1899, esc-urbannest` |
| `real_one_shot_code_gen` | 0.5000 | `esc-urbannest, esc-riverline, esc-aster, esc-northwind, esc-heliogrid` |
| `real_agentic_code_gen` | 0.9000 | `acct-northwind, acct-aster, acct-heliogrid, acct-riverline, runbook-regulated-upgrade` |

### sac-004

For Riverline Logistics, identify every open security exception, its CVE, fixed version, and owner.

Relevant docs: `acct-riverline, adv-atlas-saml-4102, adv-meridian-path-2899, esc-riverline, rel-atlas-4-8-2, rel-meridian-2-7-5, rollout-riverline-second-blocker-ledger, ticket-sec-1775, ticket-sec-1842`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1111 | `esc-riverline, meet-riverline, v3-approval-decoy-0064, v3-approval-decoy-0544, v3-approval-decoy-0034` |
| `real_preset_flow_llm_router` | 0.1111 | `esc-riverline, meet-riverline, v3-approval-decoy-0059, v3-approval-decoy-0359, v3-approval-decoy-0449` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5556 | `esc-riverline, acct-riverline, meet-riverline, adv-atlas-saml-4102, adv-meridian-path-2899` |
| `real_agentic_preset_flow_llm_reflection` | 0.7778 | `esc-riverline, acct-riverline, ticket-sec-1775, ticket-sec-1842, adv-atlas-saml-4102` |
| `real_one_shot_code_gen` | 0.6667 | `adv-atlas-saml-4102, adv-meridian-path-2899, acct-riverline, ticket-sec-1775, ticket-sec-1842` |
| `real_agentic_code_gen` | 0.7778 | `esc-riverline, acct-riverline, adv-atlas-saml-4102, adv-meridian-path-2899, ticket-sec-1842` |

### sac-005

SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?

Relevant docs: `acct-bluepeak, acct-quartzbio, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1667 | `cluster-atlas-rerank-4520-release-005, cluster-atlas-rerank-4520-release-045, cluster-atlas-rerank-4520-release-015, cluster-atlas-rerank-4520-release-055, ticket-sec-1899` |
| `real_preset_flow_llm_router` | 0.1667 | `ticket-sec-1899, decoy-ticket-sec-1902, decoy-ticket-sec-1906, decoy-ticket-sec-1211, decoy-ticket-sec-1903` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1667 | `esc-greenhouse, esc-novafoods, ticket-sec-1899, ticket-sec-1690, cluster-atlas-rerank-4520-release-005` |
| `real_agentic_preset_flow_llm_reflection` | 0.6667 | `ticket-sec-1899, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, warroom-r7-june-critical-roster, acct-novafoods` |
| `real_one_shot_code_gen` | 0.3333 | `ticket-sec-1899, ticket-sec-1690, ticket-sec-1775, ticket-sec-1604, ticket-sec-1811` |
| `real_agentic_code_gen` | 1.0000 | `ticket-sec-1899, rel-atlas-4-9-0, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-bluepeak` |

### sac-007

Among regulated customers, which accounts need a critical security patch before a renewal call inside 30 days?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, adv-atlas-saml-4102, adv-forge-ssrf-1984, adv-meridian-path-2899, runbook-regulated-upgrade, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.2222 | `runbook-regulated-upgrade, warroom-r7-june-critical-roster, v3-warroom-decoy-0330, v3-warroom-decoy-0030, v3-warroom-decoy-0085` |
| `real_preset_flow_llm_router` | 0.2222 | `runbook-regulated-upgrade, warroom-r7-june-critical-roster, esc-riverline, v3-warroom-decoy-0098, v3-warroom-decoy-0078` |
| `real_agentic_fixed_flow_llm_reflection` | 0.2222 | `runbook-regulated-upgrade, warroom-r7-june-critical-roster, esc-riverline, esc-northwind, esc-novafoods` |
| `real_agentic_preset_flow_llm_reflection` | 0.2222 | `warroom-r7-june-critical-roster, ticket-sec-1775, ticket-sec-1690, ticket-sec-1899, esc-riverline` |
| `real_one_shot_code_gen` | 0.0000 | `esc-riverline, rel-atlas-4-8-2, rel-forge-6-2-0, rel-atlas-4-9-0, esc-novafoods` |
| `real_agentic_code_gen` | 0.0000 | `acct-contoso, acct-urbannest, acct-novafoods, acct-quartzbio, ticket-sec-1690` |

### sac-009

Which AtlasSearch customers are blocked by rerank cache evidence, and which ones need Evidence Ledger rather than Exact Token Guard?

Relevant docs: `acct-bluepeak, acct-quartzbio, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-bluepeak, esc-quartzbio, rel-atlas-4-8-2, rel-atlas-4-9-0`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.3750 | `meet-bluepeak, esc-bluepeak, decoy-guide-012, approval-quartzbio-namespace-proof, cluster-atlas-rerank-4520-approval-027` |
| `real_preset_flow_llm_router` | 0.5000 | `meet-bluepeak, esc-bluepeak, approval-quartzbio-namespace-proof, acct-bluepeak, rel-atlas-4-9-0` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `esc-bluepeak, ticket-sec-1899, acct-bluepeak, rel-atlas-4-9-0, meet-bluepeak` |
| `real_agentic_preset_flow_llm_reflection` | 0.7500 | `approval-atlas-northwind-final, approval-quartzbio-namespace-proof, warroom-r7-june-critical-roster, rel-atlas-4-9-0, esc-bluepeak` |
| `real_one_shot_code_gen` | 0.7500 | `esc-bluepeak, approval-quartzbio-namespace-proof, acct-bluepeak, rel-atlas-4-9-0, esc-quartzbio` |
| `real_agentic_code_gen` | 0.3750 | `approval-beacon-contoso-may06, ticket-sec-1842, rel-atlas-4-8-1, acct-quartzbio, source-authority-matrix-v3` |

### sac-011

For all customers using both AtlasSearch and Meridian Sync, summarize blockers and do not include customers using only one of those products.

Relevant docs: `acct-quartzbio, acct-riverline, adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-meridian-path-2899, esc-quartzbio, esc-riverline`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1429 | `esc-riverline, negative-forgedeploy-novafoods, rollout-riverline-second-blocker-ledger, cluster-product-meridian-sync-advisory-013, cluster-product-meridian-sync-advisory-053` |
| `real_preset_flow_llm_router` | 0.2857 | `esc-riverline, negative-forgedeploy-novafoods, rollout-riverline-second-blocker-ledger, acct-riverline, cluster-enterprise-thread-410` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1429 | `esc-riverline, rollout-riverline-second-blocker-ledger, ticket-sec-1842, ticket-sec-1775, esc-bluepeak` |
| `real_agentic_preset_flow_llm_reflection` | 0.2857 | `warroom-r7-june-critical-roster, approval-quartzbio-namespace-proof, approval-atlas-northwind-final, ticket-sec-1775, esc-riverline` |
| `real_one_shot_code_gen` | 0.5714 | `esc-riverline, negative-forgedeploy-novafoods, acct-riverline, rollout-riverline-second-blocker-ledger, acct-quartzbio` |
| `real_agentic_code_gen` | 0.5714 | `acct-riverline, acct-quartzbio, rollout-riverline-second-blocker-ledger, esc-riverline, esc-quartzbio` |

### sac-013

Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?

Relevant docs: `acct-contoso, adv-beacon-oauth-3771, approval-beacon-contoso-may06, esc-contoso, rel-beacon-3-14-0, rel-beacon-3-14-1`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1667 | `approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0496` |
| `real_preset_flow_llm_router` | 0.1667 | `approval-beacon-contoso-may06, v3-approval-decoy-0606, v3-approval-decoy-0081, v3-approval-decoy-0096, v3-approval-decoy-0681` |
| `real_agentic_fixed_flow_llm_reflection` | 0.6667 | `approval-beacon-contoso-may06, rel-beacon-3-14-1, rel-beacon-3-14-0, adv-beacon-oauth-3771, ticket-sec-1811` |
| `real_agentic_preset_flow_llm_reflection` | 0.8333 | `adv-beacon-oauth-3771, rel-beacon-3-14-0, ticket-sec-1811, rel-beacon-3-14-1, acct-contoso` |
| `real_one_shot_code_gen` | 0.6667 | `approval-beacon-contoso-may06, rel-beacon-3-14-0, adv-beacon-oauth-3771, ticket-sec-1811, rel-beacon-3-14-1` |
| `real_agentic_code_gen` | 1.0000 | `approval-beacon-contoso-may06, rel-beacon-3-14-1, rel-beacon-3-14-0, esc-contoso, adv-beacon-oauth-3771` |

### sac-014

Find every high or critical CVE disclosed in May 2026, then list exposed customers and fixed versions.

Relevant docs: `adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-beacon-oauth-3771, approval-atlas-northwind-final, approval-beacon-contoso-may06, approval-quartzbio-namespace-proof, rel-atlas-4-8-2, rel-atlas-4-9-0, rel-beacon-3-14-1, ticket-sec-1811, ticket-sec-1842, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.2500 | `adv-forge-ssrf-1984, adv-meridian-path-2899, adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-compass-csv-1440` |
| `real_preset_flow_llm_router` | 0.2500 | `adv-forge-ssrf-1984, adv-meridian-path-2899, adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-compass-csv-1440` |
| `real_agentic_fixed_flow_llm_reflection` | 0.2500 | `adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-beacon-oauth-3771, cluster-atlas-rerank-4520-release-035, adv-forge-ssrf-1984` |
| `real_agentic_preset_flow_llm_reflection` | 0.3333 | `adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-beacon-oauth-3771, approval-atlas-northwind-final, acct-novafoods` |
| `real_one_shot_code_gen` | 0.5000 | `adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-meridian-path-2899, adv-beacon-oauth-3771, adv-compass-csv-1440` |
| `real_agentic_code_gen` | 0.7500 | `adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-beacon-oauth-3771, ticket-sec-1811, ticket-sec-1842` |

### sac-016

A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?

Relevant docs: `eval-sac-policy, roadmap-rovo-sac`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-reflection-decoy-0405, v3-reflection-decoy-0118, v3-reflection-decoy-0422, v3-reflection-decoy-0518, v3-reflection-decoy-0418` |
| `real_preset_flow_llm_router` | 0.5000 | `policy-reflection-missing-evidence-v3, source-authority-matrix-v3, eval-sac-policy, policy-sac-latency-ledger-v3` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0025, v3-reflection-decoy-0225, v3-reflection-decoy-0020, v3-reflection-decoy-0220` |
| `real_agentic_preset_flow_llm_reflection` | 0.5000 | `policy-reflection-missing-evidence-v3, eval-sac-policy, policy-sac-latency-ledger-v3, source-authority-matrix-v3, approval-atlas-northwind-final` |
| `real_one_shot_code_gen` | 1.0000 | `policy-reflection-missing-evidence-v3, roadmap-rovo-sac, rollout-riverline-second-blocker-ledger, source-authority-matrix-v3, rel-atlas-4-9-0` |
| `real_agentic_code_gen` | 0.5000 | `policy-reflection-missing-evidence-v3, rollout-riverline-second-blocker-ledger, eval-sac-policy, source-authority-matrix-v3, policy-sac-latency-ledger-v3` |

### sac-018

For HelioGrid Energy, map the open blocker to ticket, CVE, fixed version, and technical owner.

Relevant docs: `acct-heliogrid, adv-forge-ssrf-1984, esc-heliogrid, rel-forge-6-2-0, ticket-sec-1690`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.8000 | `esc-heliogrid, cluster-forge-ssrf-1984-email-036, cluster-forge-ssrf-1984-digest-011, ticket-sec-1690, cluster-forge-ssrf-1984-digest-021` |
| `real_preset_flow_llm_router` | 0.8000 | `esc-heliogrid, ticket-sec-1690, adv-forge-ssrf-1984, acct-heliogrid, v3-alias-decoy-0187` |
| `real_agentic_fixed_flow_llm_reflection` | 1.0000 | `esc-heliogrid, acct-heliogrid, ticket-sec-1690, adv-forge-ssrf-1984, rel-forge-6-2-0` |
| `real_agentic_preset_flow_llm_reflection` | 0.8000 | `esc-heliogrid, acct-heliogrid, ticket-sec-1690, adv-forge-ssrf-1984, rel-compass-1-19-3` |
| `real_one_shot_code_gen` | 0.8000 | `adv-forge-ssrf-1984, ticket-sec-1690, warroom-r7-june-critical-roster, alias-owner-directory, rollout-riverline-second-blocker-ledger` |
| `real_agentic_code_gen` | 1.0000 | `esc-heliogrid, ticket-sec-1690, adv-forge-ssrf-1984, rel-forge-6-2-0, rollout-riverline-second-blocker-ledger` |

### sac-020

For Greenhouse University, map the open blocker to ticket, CVE, fixed version, and technical owner.

Relevant docs: `acct-greenhouse, adv-forge-ssrf-1984, esc-greenhouse, rel-forge-6-2-0, ticket-sec-1690`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.6000 | `esc-greenhouse, cluster-forge-ssrf-1984-rollout-052, cluster-forge-ssrf-1984-rollout-012, ticket-sec-1690, acct-greenhouse` |
| `real_preset_flow_llm_router` | 0.6000 | `esc-greenhouse, ticket-sec-1690, acct-greenhouse, v3-alias-decoy-0149, v3-alias-decoy-0059` |
| `real_agentic_fixed_flow_llm_reflection` | 1.0000 | `esc-greenhouse, ticket-sec-1690, acct-greenhouse, adv-forge-ssrf-1984, rel-forge-6-2-0` |
| `real_agentic_preset_flow_llm_reflection` | 0.8000 | `esc-greenhouse, ticket-sec-1690, adv-forge-ssrf-1984, acct-greenhouse, rel-compass-1-19-3` |
| `real_one_shot_code_gen` | 0.8000 | `esc-greenhouse, ticket-sec-1690, adv-forge-ssrf-1984, acct-greenhouse, esc-northwind` |
| `real_agentic_code_gen` | 0.8000 | `acct-greenhouse, esc-greenhouse, ticket-sec-1690, adv-forge-ssrf-1984, alias-owner-directory` |

### sac-022

For QuartzBio Labs, map the open blocker to ticket, CVE, fixed version, and technical owner.

Relevant docs: `acct-quartzbio, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-quartzbio, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1667 | `esc-quartzbio, cluster-atlas-rerank-4520-rollout-052, cluster-atlas-rerank-4520-rollout-012, v3-approval-decoy-0088, v3-approval-decoy-0058` |
| `real_preset_flow_llm_router` | 0.5000 | `esc-quartzbio, ticket-sec-1899, acct-quartzbio, decoy-ticket-sec-1207, decoy-ticket-sec-1206` |
| `real_agentic_fixed_flow_llm_reflection` | 0.6667 | `esc-quartzbio, ticket-sec-1899, adv-atlas-rerank-4520, acct-quartzbio, cluster-meridian-path-2899-ticket-053` |
| `real_agentic_preset_flow_llm_reflection` | 0.8333 | `esc-quartzbio, ticket-sec-1899, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, acct-quartzbio` |
| `real_one_shot_code_gen` | 0.8333 | `ticket-sec-1899, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-quartzbio, acct-quartzbio` |
| `real_agentic_code_gen` | 0.8333 | `esc-quartzbio, ticket-sec-1899, approval-quartzbio-namespace-proof, acct-quartzbio, adv-atlas-rerank-4520` |

### sac-024

Design the minimum comparison table for evaluating whether Search-as-Code is better than a normal agent.

Relevant docs: `eval-sac-policy, roadmap-rovo-sac`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-policy-decoy-0429, v3-policy-decoy-0129, v3-policy-decoy-0124, v3-policy-decoy-0029, v3-policy-decoy-0229` |
| `real_preset_flow_llm_router` | 0.5000 | `eval-sac-policy, v3-policy-decoy-0505, v3-policy-decoy-0705, v3-policy-decoy-0605, v3-policy-decoy-0500` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `eval-sac-policy, v3-policy-decoy-0124, v3-policy-decoy-0029, v3-policy-decoy-0019, v3-policy-decoy-0649` |
| `real_agentic_preset_flow_llm_reflection` | 0.5000 | `eval-sac-policy, policy-sac-latency-ledger-v3, policy-reflection-missing-evidence-v3, rel-rovo-5-3-0, esc-quartzbio` |
| `real_one_shot_code_gen` | 1.0000 | `eval-sac-policy, policy-reflection-missing-evidence-v3, roadmap-rovo-sac, policy-sac-latency-ledger-v3, rel-rovo-5-3-0` |
| `real_agentic_code_gen` | 1.0000 | `eval-sac-policy, policy-sac-latency-ledger-v3, policy-reflection-missing-evidence-v3, source-authority-matrix-v3, roadmap-rovo-sac` |

### sac-025

Should BluePeak Insurance be included in the SAML connector emergency rollout?

Relevant docs: `acct-bluepeak, adv-atlas-rerank-4520, adv-atlas-saml-4102, esc-bluepeak, ticket-sec-1842, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `cluster-atlas-saml-4102-postmortem-058, cluster-atlas-saml-4102-postmortem-018, cluster-atlas-saml-4102-ticket-023, cluster-atlas-saml-4102-ticket-033, cluster-atlas-saml-4102-ticket-003` |
| `real_preset_flow_llm_router` | 0.5000 | `rel-atlas-4-8-1, approval-atlas-northwind-final, adv-atlas-saml-4102, acct-bluepeak, rel-atlas-4-8-2` |
| `real_agentic_fixed_flow_llm_reflection` | 0.3333 | `cluster-atlas-saml-4102-ticket-053, cluster-atlas-saml-4102-ticket-013, cluster-atlas-saml-4102-ticket-043, cluster-atlas-saml-4102-ticket-003, ticket-sec-1842` |
| `real_agentic_preset_flow_llm_reflection` | 0.6667 | `acct-bluepeak, warroom-r7-june-critical-roster, ticket-sec-1842, adv-atlas-saml-4102, ticket-sec-1604` |
| `real_one_shot_code_gen` | 0.5000 | `approval-atlas-northwind-final, acct-bluepeak, alias-customer-codenames, esc-bluepeak, ticket-sec-1604` |
| `real_agentic_code_gen` | 0.5000 | `ticket-sec-1604, ticket-sec-1899, acct-bluepeak, alias-customer-codenames, esc-bluepeak` |

### sac-027

Across all red-risk accounts, which technical owners have more than one renewal blocker assigned?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, esc-aster, esc-northwind, esc-riverline`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `decoy-acct-citrine-logistics, decoy-acct-copper-health, decoy-acct-arbor-retail, decoy-acct-pinnacle-retail, decoy-acct-noble-foods` |
| `real_preset_flow_llm_router` | 0.1429 | `decoy-acct-solstice-manufacturing, decoy-acct-citrine-logistics, decoy-acct-copper-health, decoy-acct-arbor-retail, decoy-acct-pinnacle-retail` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5714 | `alias-owner-directory, esc-northwind, esc-heliogrid, esc-aster, acct-riverline` |
| `real_agentic_preset_flow_llm_reflection` | 0.4286 | `acct-northwind, acct-urbannest, acct-riverline, acct-aster, ticket-sec-1604` |
| `real_one_shot_code_gen` | 0.4286 | `warroom-r7-june-critical-roster, acct-novafoods, acct-greenhouse, acct-northwind, acct-heliogrid` |
| `real_agentic_code_gen` | 0.7143 | `acct-northwind, acct-heliogrid, acct-riverline, acct-aster, acct-urbannest` |

### sac-028

A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?

Relevant docs: `acct-quartzbio, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-quartzbio, rel-atlas-4-9-0, runbook-regulated-upgrade`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-namespace-decoy-0322, v3-namespace-decoy-0007, v3-namespace-decoy-0312, v3-namespace-decoy-0197, v3-namespace-decoy-0002` |
| `real_preset_flow_llm_router` | 0.1667 | `approval-quartzbio-namespace-proof, meet-quartzbio, v3-namespace-decoy-0198, v3-namespace-decoy-0178, v3-namespace-decoy-0278` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1667 | `approval-quartzbio-namespace-proof, v3-namespace-decoy-0005, v3-namespace-decoy-0085, v3-namespace-decoy-0035, v3-namespace-decoy-0075` |
| `real_agentic_preset_flow_llm_reflection` | 0.6667 | `approval-quartzbio-namespace-proof, esc-quartzbio, rel-atlas-4-9-0, ticket-sec-1899, acct-quartzbio` |
| `real_one_shot_code_gen` | 1.0000 | `approval-quartzbio-namespace-proof, esc-quartzbio, acct-quartzbio, runbook-regulated-upgrade, rel-atlas-4-9-0` |
| `real_agentic_code_gen` | 1.0000 | `approval-quartzbio-namespace-proof, ticket-sec-1899, rel-atlas-4-9-0, acct-quartzbio, alias-customer-codenames` |

### sac-030

Which customers have blockers that require exact identifier matching, and what identifiers should the generated code preserve?

Relevant docs: `acct-aster, acct-bluepeak, acct-contoso, acct-heliogrid, acct-northwind, acct-novafoods, acct-riverline, ticket-sec-1604, ticket-sec-1690, ticket-sec-1775, ticket-sec-1811, ticket-sec-1842, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `cluster-enterprise-review-117, cluster-enterprise-review-165, cluster-enterprise-review-177, cluster-enterprise-review-261, cluster-enterprise-review-417` |
| `real_preset_flow_llm_router` | 0.0000 | `cluster-enterprise-review-117, cluster-enterprise-review-165, cluster-enterprise-review-177, cluster-enterprise-review-261, cluster-enterprise-review-417` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0769 | `source-authority-matrix-v3, ticket-sec-1842, cluster-enterprise-review-117, cluster-enterprise-review-165, cluster-enterprise-review-177` |
| `real_agentic_preset_flow_llm_reflection` | 0.2308 | `warroom-r7-june-critical-roster, approval-atlas-northwind-final, approval-quartzbio-namespace-proof, ticket-sec-1842, acct-heliogrid` |
| `real_one_shot_code_gen` | 0.2308 | `alias-customer-codenames, eval-sac-policy, policy-reflection-missing-evidence-v3, alias-owner-directory, source-authority-matrix-v3` |
| `real_agentic_code_gen` | 0.2308 | `alias-customer-codenames, alias-owner-directory, rel-meridian-2-7-4, source-authority-matrix-v3, acct-riverline` |

### sac-032

Compare Northwind Health and Riverline Logistics: which one has a single AtlasSearch blocker and which one has two product blockers?

Relevant docs: `acct-northwind, acct-riverline, adv-atlas-saml-4102, adv-meridian-path-2899, approval-atlas-northwind-final, esc-northwind, esc-riverline, rollout-riverline-second-blocker-ledger`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.5000 | `rollout-riverline-second-blocker-ledger, esc-riverline, esc-northwind, cluster-customer-riverline-risk-021, cluster-customer-riverline-risk-005` |
| `real_preset_flow_llm_router` | 0.6250 | `esc-riverline, esc-northwind, acct-riverline, adv-atlas-saml-4102, acct-northwind` |
| `real_agentic_fixed_flow_llm_reflection` | 0.3750 | `esc-northwind, esc-riverline, acct-riverline, cluster-atlas-saml-4102-approval-027, cluster-customer-riverline-risk-021` |
| `real_agentic_preset_flow_llm_reflection` | 0.8750 | `approval-atlas-northwind-final, rollout-riverline-second-blocker-ledger, acct-riverline, warroom-r7-june-critical-roster, esc-riverline` |
| `real_one_shot_code_gen` | 0.5000 | `ticket-sec-1842, esc-riverline, esc-northwind, acct-northwind, acct-riverline` |
| `real_agentic_code_gen` | 0.8750 | `rollout-riverline-second-blocker-ledger, esc-riverline, esc-northwind, adv-atlas-saml-4102, acct-northwind` |

### sac-033

Which customers should be excluded from a June critical-patch war room, and why?

Relevant docs: `acct-bluepeak, acct-contoso, acct-greenhouse, acct-novafoods, acct-quartzbio, acct-urbannest, adv-atlas-rerank-4520, adv-beacon-oauth-3771, adv-compass-csv-1440, adv-forge-ssrf-1984, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0909 | `warroom-r7-june-critical-roster, v3-warroom-decoy-0078, v3-warroom-decoy-0088, v3-warroom-decoy-0068, v3-warroom-decoy-0098` |
| `real_preset_flow_llm_router` | 0.0909 | `warroom-r7-june-critical-roster, cluster-enterprise-memo-121, cluster-enterprise-memo-229, cluster-enterprise-memo-277, cluster-enterprise-memo-169` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0909 | `warroom-r7-june-critical-roster, ticket-sec-1775, ticket-sec-1842, v3-warroom-decoy-0087, v3-warroom-decoy-0067` |
| `real_agentic_preset_flow_llm_reflection` | 0.1818 | `warroom-r7-june-critical-roster, approval-atlas-northwind-final, approval-quartzbio-namespace-proof, ticket-sec-1775, acct-northwind` |
| `real_one_shot_code_gen` | 0.0909 | `warroom-r7-june-critical-roster, policy-reflection-missing-evidence-v3, alias-customer-codenames, approval-atlas-northwind-final, rollout-riverline-second-blocker-ledger` |
| `real_agentic_code_gen` | 0.0909 | `warroom-r7-june-critical-roster, alias-customer-codenames, approval-atlas-northwind-final, rollout-riverline-second-blocker-ledger, approval-quartzbio-namespace-proof` |

### sac-035

If generated code finds no ForgeDeploy documents for NovaFoods, should it keep searching or answer with negative evidence?

Relevant docs: `acct-novafoods, negative-forgedeploy-novafoods`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-approval-decoy-0185, v3-approval-decoy-0785, v3-approval-decoy-0665, v3-approval-decoy-0485, v3-approval-decoy-0635` |
| `real_preset_flow_llm_router` | 1.0000 | `sales-novafoods-forgedeploy-discovery, negative-forgedeploy-novafoods, acct-novafoods, adv-forge-ssrf-1984, rel-forge-6-2-0` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `negative-forgedeploy-novafoods, sales-novafoods-forgedeploy-discovery, policy-reflection-missing-evidence-v3, source-authority-matrix-v3, rel-forge-6-2-0` |
| `real_agentic_preset_flow_llm_reflection` | 0.5000 | `policy-reflection-missing-evidence-v3, negative-forgedeploy-novafoods, rel-forge-6-2-0, alias-customer-codenames, rel-atlas-4-9-0` |
| `real_one_shot_code_gen` | 1.0000 | `negative-forgedeploy-novafoods, acct-novafoods, sales-novafoods-forgedeploy-discovery, policy-reflection-missing-evidence-v3, meet-novafoods` |
| `real_agentic_code_gen` | 1.0000 | `negative-forgedeploy-novafoods, policy-reflection-missing-evidence-v3, eval-sac-policy, source-authority-matrix-v3, esc-novafoods` |

### sac-036

Which accounts have the same technical owner for different product blockers, and what does that imply for staffing?

Relevant docs: `acct-bluepeak, acct-contoso, acct-greenhouse, acct-heliogrid, acct-northwind, acct-quartzbio, acct-riverline, acct-urbannest`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `decoy-acct-union-manufacturing, decoy-acct-anchor-retail, decoy-acct-cobalt-logistics, decoy-acct-evergreen-manufacturing, decoy-acct-arbor-retail` |
| `real_preset_flow_llm_router` | 0.0000 | `decoy-acct-anchor-retail, decoy-acct-cobalt-logistics, decoy-acct-marble-logistics, decoy-acct-arbor-retail, decoy-acct-cascade-logistics` |
| `real_agentic_fixed_flow_llm_reflection` | 0.0000 | `esc-quartzbio, esc-bluepeak, esc-northwind, alias-owner-directory, esc-greenhouse` |
| `real_agentic_preset_flow_llm_reflection` | 0.0000 | `alias-owner-directory, warroom-r7-june-critical-roster, rollout-riverline-second-blocker-ledger, approval-atlas-northwind-final, esc-greenhouse` |
| `real_one_shot_code_gen` | 0.0000 | `esc-greenhouse, esc-bluepeak, esc-heliogrid, esc-aster, esc-quartzbio` |
| `real_agentic_code_gen` | 0.0000 | `esc-bluepeak, esc-greenhouse, esc-aster, esc-novafoods, esc-contoso` |

### sac-037

BPI asks for tenant isolation proof. Expand the alias, identify the blocker, and cite the release that provides the evidence.

Relevant docs: `acct-bluepeak, adv-atlas-rerank-4520, alias-customer-codenames, esc-bluepeak, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1667 | `meet-bluepeak, esc-bluepeak, approval-quartzbio-namespace-proof, v3-alias-decoy-0441, v3-alias-decoy-0231` |
| `real_preset_flow_llm_router` | 0.1667 | `meet-bluepeak, esc-bluepeak, v3-alias-decoy-0441, v3-alias-decoy-0231, v3-alias-decoy-0411` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5000 | `alias-customer-codenames, esc-bluepeak, acct-bluepeak, meet-bluepeak, approval-quartzbio-namespace-proof` |
| `real_agentic_preset_flow_llm_reflection` | 0.6667 | `alias-customer-codenames, esc-bluepeak, acct-bluepeak, ticket-sec-1690, ticket-sec-1775` |
| `real_one_shot_code_gen` | 0.6667 | `alias-customer-codenames, rel-meridian-2-7-4, source-authority-matrix-v3, rel-atlas-4-9-0, esc-bluepeak` |
| `real_agentic_code_gen` | 1.0000 | `esc-bluepeak, ticket-sec-1899, acct-bluepeak, rel-atlas-4-9-0, alias-customer-codenames` |

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

### sac-039

NF-17 has a sales discovery note mentioning ForgeDeploy. Does that create a ForgeDeploy remediation obligation?

Relevant docs: `acct-novafoods, alias-customer-codenames, negative-forgedeploy-novafoods, sales-novafoods-forgedeploy-discovery`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.2500 | `sales-novafoods-forgedeploy-discovery, v3-approval-decoy-0735, v3-approval-decoy-0435, v3-approval-decoy-0615, v3-approval-decoy-0525` |
| `real_preset_flow_llm_router` | 0.5000 | `sales-novafoods-forgedeploy-discovery, rel-forge-6-2-0, adv-forge-ssrf-1984, acct-greenhouse, negative-forgedeploy-novafoods` |
| `real_agentic_fixed_flow_llm_reflection` | 0.2500 | `sales-novafoods-forgedeploy-discovery, approval-atlas-northwind-final, v3-approval-decoy-0735, v3-approval-decoy-0435, v3-approval-decoy-0615` |
| `real_agentic_preset_flow_llm_reflection` | 0.7500 | `negative-forgedeploy-novafoods, alias-customer-codenames, adv-forge-ssrf-1984, rel-forge-6-2-0, esc-greenhouse` |
| `real_one_shot_code_gen` | 0.2500 | `ticket-sec-1690, alias-customer-codenames, approval-atlas-northwind-final, eval-sac-policy, policy-reflection-missing-evidence-v3` |
| `real_agentic_code_gen` | 0.5000 | `rel-forge-6-2-0, negative-forgedeploy-novafoods, esc-greenhouse, adv-forge-ssrf-1984, alias-customer-codenames` |

### sac-040

Use the R7 final roster, not drafts: which aliases are included in the June critical-patch war room and which are explicit exclusions?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, alias-customer-codenames, runbook-regulated-upgrade, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `v3-warroom-decoy-0078, v3-warroom-decoy-0378, v3-warroom-decoy-0478, v3-warroom-decoy-0178, v3-warroom-decoy-0278` |
| `real_preset_flow_llm_router` | 0.1429 | `warroom-r7-june-critical-roster, rollout-riverline-second-blocker-ledger, policy-reflection-missing-evidence-v3, approval-atlas-northwind-final, approval-quartzbio-namespace-proof` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1429 | `warroom-r7-june-critical-roster, v3-warroom-decoy-0017, v3-warroom-decoy-0377, v3-warroom-decoy-0477, v3-warroom-decoy-0277` |
| `real_agentic_preset_flow_llm_reflection` | 0.1429 | `warroom-r7-june-critical-roster, ticket-sec-1775, ticket-sec-1690, approval-atlas-northwind-final, v3-warroom-decoy-0017` |
| `real_one_shot_code_gen` | 0.2857 | `warroom-r7-june-critical-roster, alias-customer-codenames, alias-owner-directory, rollout-riverline-second-blocker-ledger, rel-atlas-4-8-1` |
| `real_agentic_code_gen` | 0.2857 | `warroom-r7-june-critical-roster, alias-customer-codenames, source-authority-matrix-v3, alias-owner-directory, rollout-riverline-second-blocker-ledger` |

### sac-041

NW-H has rollback-drill notes for AtlasSearch 4.8.3. What AtlasSearch version is actually approved for the SAML blocker?

Relevant docs: `acct-northwind, adv-atlas-saml-4102, alias-customer-codenames, approval-atlas-northwind-final, rel-atlas-4-8-2, ticket-sec-1842`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1667 | `approval-atlas-northwind-final, v3-approval-decoy-0572, v3-approval-decoy-0062, v3-approval-decoy-0482, v3-approval-decoy-0092` |
| `real_preset_flow_llm_router` | 0.1667 | `approval-atlas-northwind-final, approval-quartzbio-namespace-proof, rollout-riverline-second-blocker-ledger, warroom-r7-june-critical-roster, policy-reflection-missing-evidence-v3` |
| `real_agentic_fixed_flow_llm_reflection` | 0.6667 | `approval-atlas-northwind-final, esc-northwind, acct-northwind, adv-atlas-saml-4102, ticket-sec-1842` |
| `real_agentic_preset_flow_llm_reflection` | 0.8333 | `approval-atlas-northwind-final, warroom-r7-june-critical-roster, adv-atlas-saml-4102, rel-atlas-4-8-2, alias-customer-codenames` |
| `real_one_shot_code_gen` | 0.5000 | `approval-atlas-northwind-final, approval-quartzbio-namespace-proof, rollout-riverline-second-blocker-ledger, alias-customer-codenames, source-authority-matrix-v3` |
| `real_agentic_code_gen` | 0.6667 | `approval-atlas-northwind-final, ticket-sec-1842, rel-atlas-4-8-2, approval-quartzbio-namespace-proof, rel-atlas-4-9-0` |

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

### sac-044

The account asking for a namespace sample is QBL. Which release and feature should the response cite, and what nearby release is insufficient?

Relevant docs: `acct-quartzbio, adv-atlas-rerank-4520, alias-customer-codenames, approval-quartzbio-namespace-proof, esc-quartzbio, rel-atlas-4-8-2, rel-atlas-4-9-0`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.1429 | `approval-quartzbio-namespace-proof, v3-namespace-decoy-0360, v3-namespace-decoy-0005, v3-namespace-decoy-0345, v3-namespace-decoy-0125` |
| `real_preset_flow_llm_router` | 0.1429 | `approval-quartzbio-namespace-proof, v3-namespace-decoy-0040, v3-namespace-decoy-0035, v3-namespace-decoy-0005, v3-namespace-decoy-0025` |
| `real_agentic_fixed_flow_llm_reflection` | 0.1429 | `approval-quartzbio-namespace-proof, v3-namespace-decoy-0032, v3-namespace-decoy-0052, v3-namespace-decoy-0092, v3-namespace-decoy-0252` |
| `real_agentic_preset_flow_llm_reflection` | 0.4286 | `approval-quartzbio-namespace-proof, ticket-sec-1899, approval-atlas-northwind-final, esc-quartzbio, acct-quartzbio` |
| `real_one_shot_code_gen` | 0.5714 | `approval-quartzbio-namespace-proof, source-authority-matrix-v3, esc-quartzbio, alias-customer-codenames, acct-quartzbio` |
| `real_agentic_code_gen` | 0.8571 | `rel-atlas-4-8-1, approval-quartzbio-namespace-proof, esc-quartzbio, acct-quartzbio, ticket-sec-1899` |

### sac-045

For JBell's red renewals before July, which customers are in scope and which product blocker does each have?

Relevant docs: `acct-aster, acct-riverline, adv-meridian-path-2899, alias-owner-directory, esc-aster, esc-riverline, rel-meridian-2-7-5, rollout-riverline-second-blocker-ledger, ticket-sec-1775`

| System | Recall@10 | Top docs |
|---|---:|---|
| `real_fixed_flow_llm_qr` | 0.0000 | `warroom-r7-june-critical-roster, cluster-customer-aster-risk-005, cluster-customer-aster-risk-045, cluster-customer-aster-risk-021, cluster-customer-aster-risk-029` |
| `real_preset_flow_llm_router` | 0.2222 | `warroom-r7-june-critical-roster, esc-urbannest, acct-riverline, acct-aster, cluster-customer-northwind-risk-005` |
| `real_agentic_fixed_flow_llm_reflection` | 0.5556 | `rollout-riverline-second-blocker-ledger, esc-riverline, warroom-r7-june-critical-roster, cluster-customer-aster-crm-001, alias-owner-directory` |
| `real_agentic_preset_flow_llm_reflection` | 0.4444 | `alias-owner-directory, ticket-sec-1775, rollout-riverline-second-blocker-ledger, esc-urbannest, acct-riverline` |
| `real_one_shot_code_gen` | 0.4444 | `source-authority-matrix-v3, alias-owner-directory, alias-customer-codenames, policy-reflection-missing-evidence-v3, esc-urbannest` |
| `real_agentic_code_gen` | 0.8889 | `acct-aster, acct-riverline, esc-riverline, alias-owner-directory, ticket-sec-1775` |

