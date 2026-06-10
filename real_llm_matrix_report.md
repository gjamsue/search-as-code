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
| `real_agentic_preset_flow_llm_reflection` | 0.8381 | 28692.8 | 28436.5 | 256.4 | 6.20 | 0.00 | 97.6 |
| `real_one_shot_code_gen` | 0.7381 | 62041.8 | 61891.1 | 150.7 | 6.60 | 1.00 | 39.2 |
| `real_agentic_fixed_flow_llm_reflection` | 0.4952 | 30620.5 | 29223.8 | 1396.7 | 6.00 | 0.00 | 840.0 |
| `real_preset_flow_llm_router` | 0.4667 | 11638.1 | 11523.4 | 114.8 | 1.80 | 0.00 | 49.0 |
| `real_fixed_flow_llm_qr` | 0.1619 | 11817.1 | 11523.4 | 293.7 | 4.00 | 0.00 | 120.0 |

## Compared With Existing Rule-Backed Matrix

This uses the already-completed `experiment_matrix_results.json`. The subset recall is recomputed on the same selected qids; full-run latency is from the full 31-query run.

| Rule-backed system | Subset Recall@10 | Full Recall@10 | Full total ms |
|---|---:|---:|---:|
| `agentic_preset_flows_rule_reflection` | 0.6333 | 0.4627 | 1104.2 |
| `agentic_code_gen_rule_reflection` | 0.6047 | 0.4625 | 3338.5 |
| `agentic_fixed_flow_rule_reflection` | 0.2953 | 0.2852 | 7775.8 |
| `fixed_flow_model_qr` | 0.2619 | 0.2018 | 3556.8 |
| `one_shot_code_gen_rule_policy` | 0.2619 | 0.2018 | 3238.0 |
| `preset_flow_model_router` | 0.1619 | 0.2233 | 1770.7 |

## Readout

- Real agentic codegen reaches Recall@10 `1.0000` with `135929.4` ms/query spent in LLM generation/reflection.
- Real agentic preset flow reaches Recall@10 `0.8381`; this tests whether model reflection can choose useful follow-up stacks without writing code.
- Real LLM agentic codegen now exceeds the existing rule-backed subset (`1.0000` vs `0.6047`), but at much higher LLM generation latency.

## Per-Query

### sac-001

For Northwind Health, which critical vulnerabilities affect products they run, what fixed versions are needed, and who owns the rollout?

Relevant docs: `acct-northwind, adv-atlas-saml-4102, approval-atlas-northwind-final, esc-northwind, rel-atlas-4-8-2, ticket-sec-1842`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-002

Which red-risk customers renewing before July 1 have unresolved security or audit blockers, and what is the next action for each?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, esc-aster, esc-heliogrid, esc-northwind, esc-riverline, runbook-regulated-upgrade, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-004

For Riverline Logistics, identify every open security exception, its CVE, fixed version, and owner.

Relevant docs: `acct-riverline, adv-atlas-saml-4102, adv-meridian-path-2899, esc-riverline, rel-atlas-4-8-2, rel-meridian-2-7-5, rollout-riverline-second-blocker-ledger, ticket-sec-1775, ticket-sec-1842`

| System | Recall@10 | Top docs |
|---|---:|---|

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

### sac-009

Which AtlasSearch customers are blocked by rerank cache evidence, and which ones need Evidence Ledger rather than Exact Token Guard?

Relevant docs: `acct-bluepeak, acct-quartzbio, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-bluepeak, esc-quartzbio, rel-atlas-4-8-2, rel-atlas-4-9-0`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-011

For all customers using both AtlasSearch and Meridian Sync, summarize blockers and do not include customers using only one of those products.

Relevant docs: `acct-quartzbio, acct-riverline, adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-meridian-path-2899, esc-quartzbio, esc-riverline`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-013

Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?

Relevant docs: `acct-contoso, adv-beacon-oauth-3771, approval-beacon-contoso-may06, esc-contoso, rel-beacon-3-14-0, rel-beacon-3-14-1`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-014

Find every high or critical CVE disclosed in May 2026, then list exposed customers and fixed versions.

Relevant docs: `adv-atlas-rerank-4520, adv-atlas-saml-4102, adv-beacon-oauth-3771, approval-atlas-northwind-final, approval-beacon-contoso-may06, approval-quartzbio-namespace-proof, rel-atlas-4-8-2, rel-atlas-4-9-0, rel-beacon-3-14-1, ticket-sec-1811, ticket-sec-1842, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-016

A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?

Relevant docs: `eval-sac-policy, roadmap-rovo-sac`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-018

For HelioGrid Energy, map the open blocker to ticket, CVE, fixed version, and technical owner.

Relevant docs: `acct-heliogrid, adv-forge-ssrf-1984, esc-heliogrid, rel-forge-6-2-0, ticket-sec-1690`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-020

For Greenhouse University, map the open blocker to ticket, CVE, fixed version, and technical owner.

Relevant docs: `acct-greenhouse, adv-forge-ssrf-1984, esc-greenhouse, rel-forge-6-2-0, ticket-sec-1690`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-022

For QuartzBio Labs, map the open blocker to ticket, CVE, fixed version, and technical owner.

Relevant docs: `acct-quartzbio, adv-atlas-rerank-4520, approval-quartzbio-namespace-proof, esc-quartzbio, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-024

Design the minimum comparison table for evaluating whether Search-as-Code is better than a normal agent.

Relevant docs: `eval-sac-policy, roadmap-rovo-sac`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-025

Should BluePeak Insurance be included in the SAML connector emergency rollout?

Relevant docs: `acct-bluepeak, adv-atlas-rerank-4520, adv-atlas-saml-4102, esc-bluepeak, ticket-sec-1842, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-027

Across all red-risk accounts, which technical owners have more than one renewal blocker assigned?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, esc-aster, esc-northwind, esc-riverline`

| System | Recall@10 | Top docs |
|---|---:|---|

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

### sac-032

Compare Northwind Health and Riverline Logistics: which one has a single AtlasSearch blocker and which one has two product blockers?

Relevant docs: `acct-northwind, acct-riverline, adv-atlas-saml-4102, adv-meridian-path-2899, approval-atlas-northwind-final, esc-northwind, esc-riverline, rollout-riverline-second-blocker-ledger`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-033

Which customers should be excluded from a June critical-patch war room, and why?

Relevant docs: `acct-bluepeak, acct-contoso, acct-greenhouse, acct-novafoods, acct-quartzbio, acct-urbannest, adv-atlas-rerank-4520, adv-beacon-oauth-3771, adv-compass-csv-1440, adv-forge-ssrf-1984, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-035

If generated code finds no ForgeDeploy documents for NovaFoods, should it keep searching or answer with negative evidence?

Relevant docs: `acct-novafoods, negative-forgedeploy-novafoods`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-036

Which accounts have the same technical owner for different product blockers, and what does that imply for staffing?

Relevant docs: `acct-bluepeak, acct-contoso, acct-greenhouse, acct-heliogrid, acct-northwind, acct-quartzbio, acct-riverline, acct-urbannest`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-037

BPI asks for tenant isolation proof. Expand the alias, identify the blocker, and cite the release that provides the evidence.

Relevant docs: `acct-bluepeak, adv-atlas-rerank-4520, alias-customer-codenames, esc-bluepeak, rel-atlas-4-9-0, ticket-sec-1899`

| System | Recall@10 | Top docs |
|---|---:|---|

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

### sac-040

Use the R7 final roster, not drafts: which aliases are included in the June critical-patch war room and which are explicit exclusions?

Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, alias-customer-codenames, runbook-regulated-upgrade, warroom-r7-june-critical-roster`

| System | Recall@10 | Top docs |
|---|---:|---|

### sac-041

NW-H has rollback-drill notes for AtlasSearch 4.8.3. What AtlasSearch version is actually approved for the SAML blocker?

Relevant docs: `acct-northwind, adv-atlas-saml-4102, alias-customer-codenames, approval-atlas-northwind-final, rel-atlas-4-8-2, ticket-sec-1842`

| System | Recall@10 | Top docs |
|---|---:|---|

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

### sac-045

For JBell's red renewals before July, which customers are in scope and which product blocker does each have?

Relevant docs: `acct-aster, acct-riverline, adv-meridian-path-2899, alias-owner-directory, esc-aster, esc-riverline, rel-meridian-2-7-5, rollout-riverline-second-blocker-ledger, ticket-sec-1775`

| System | Recall@10 | Top docs |
|---|---:|---|

