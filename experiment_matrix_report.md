# Search-as-Code Experiment Matrix

## Setup

- Dataset: `sac-codegen-v3` / split `test`
- Documents: `6010`
- Questions: `31`
- Metric: `Recall@10`
- Latency: total wall-clock plus generation/planning and execution split
- Decision provider for this full run: `rule_proxy_for_full_dataset_reproducibility`

## Flow Definitions

| System | Family | Target setting | Full-run implementation |
|---|---|---|---|
| `fixed_flow_model_qr` | fixed flow | query -> LLM QR -> multi-query hybrid retrieval -> reranker -> results | full run uses the query-rewrite API as a deterministic LLM-QR proxy |
| `agentic_fixed_flow_rule_reflection` | agentic fixed flow | query -> planner -> run fixed flow with decomposed queries -> reflection -> iterate | rule planner/reflection over repeated calls to the fixed flow |
| `preset_flow_model_router` | preset flow | query -> LLM router -> pick one preset search stack -> results | rule router chooses one preset stack for reproducible full-run comparison |
| `agentic_preset_flows_rule_reflection` | agentic preset flow | query -> router -> pick one/multiple preset stacks -> reflection -> iterate | rule router/reflection can choose additional preset stacks after evidence check |
| `one_shot_code_gen_rule_policy` | one-shot code-gen | query -> LLM Python code generation -> execute -> results | deterministic code generator emits Python; use run_real_codegen_retest.py for real LLM sample |
| `agentic_code_gen_rule_reflection` | agentic code-gen | query -> planner -> Python codegen -> execution -> reflection -> iterate | deterministic agentic code generator with evidence-goal reflection |

## Results

| System | Family | Recall@10 | Total ms | Planning/codegen ms | Execution ms | Search calls | QR calls | Rerank pairs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `agentic_preset_flows_rule_reflection` | agentic preset flow | 0.4627 | 1104.2 | 5.4 | 1098.8 | 6.10 | 0.00 | 733.5 |
| `agentic_code_gen_rule_reflection` | agentic code-gen | 0.4625 | 3338.5 | 0.2 | 3338.2 | 7.16 | 1.00 | 2400.0 |
| `agentic_fixed_flow_rule_reflection` | agentic fixed flow | 0.2852 | 7775.8 | 0.2 | 7775.5 | 12.39 | 5.97 | 5189.0 |
| `preset_flow_model_router` | preset flow | 0.2233 | 1770.7 | 0.0 | 1770.7 | 2.00 | 0.00 | 1251.5 |
| `one_shot_code_gen_rule_policy` | one-shot code-gen | 0.2018 | 3238.0 | 0.1 | 3237.8 | 6.97 | 1.00 | 2400.0 |
| `fixed_flow_model_qr` | fixed flow | 0.2018 | 3556.8 | 0.0 | 3556.8 | 3.97 | 1.00 | 2400.0 |

## Readout

- Agentic codegen vs one-shot codegen: Recall@10 `0.4625` vs `0.2018`, latency `3338.5` ms vs `3238.0` ms.
- Agentic preset flows vs single preset router: Recall@10 `0.4627` vs `0.2233`, showing the value of reflection even when the agent can only choose preset stacks.
- Fixed multi-query hybrid remains a strong baseline: Recall@10 `0.2018` at `3556.8` ms. Codegen only matters if route-level control or iterative evidence coverage changes the candidate set.

## Examples

### sac-013 - agentic_codegen_win

Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?

agentic codegen reflection recovered evidence one-shot codegen missed

Relevant docs: `acct-contoso, adv-beacon-oauth-3771, approval-beacon-contoso-may06, esc-contoso, rel-beacon-3-14-0, rel-beacon-3-14-1`

| System | Recall@10 | Top docs |
|---|---:|---|
| `fixed_flow_model_qr` | 0.1667 | `approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071` |
| `agentic_fixed_flow_rule_reflection` | 0.5000 | `alias-owner-directory, rel-beacon-3-14-0, rel-beacon-3-14-1, approval-beacon-contoso-may06, v3-approval-decoy-0076` |
| `preset_flow_model_router` | 0.1667 | `approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071` |
| `agentic_preset_flows_rule_reflection` | 1.0000 | `alias-customer-codenames, acct-contoso, esc-contoso, ticket-sec-1811, adv-beacon-oauth-3771` |
| `one_shot_code_gen_rule_policy` | 0.1667 | `approval-beacon-contoso-may06, v3-approval-decoy-0076, v3-approval-decoy-0676, v3-approval-decoy-0406, v3-approval-decoy-0071` |
| `agentic_code_gen_rule_reflection` | 1.0000 | `alias-customer-codenames, esc-contoso, acct-contoso, adv-beacon-oauth-3771, ticket-sec-1811` |

### sac-038 - agentic_preset_win

For CT-R's OAuth review, which Beacon version is customer-citable after final approval, and which version must be rejected?

agentic preset flow added a missing preset stack after reflection

Relevant docs: `acct-contoso, adv-beacon-oauth-3771, alias-customer-codenames, approval-beacon-contoso-may06, esc-contoso, rel-beacon-3-14-0, rel-beacon-3-14-1`

| System | Recall@10 | Top docs |
|---|---:|---|
| `fixed_flow_model_qr` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `agentic_fixed_flow_rule_reflection` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `preset_flow_model_router` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `agentic_preset_flows_rule_reflection` | 1.0000 | `alias-customer-codenames, esc-contoso, acct-contoso, adv-beacon-oauth-3771, ticket-sec-1811` |
| `one_shot_code_gen_rule_policy` | 0.1429 | `approval-beacon-contoso-may06, v3-approval-decoy-0541, v3-approval-decoy-0001, v3-approval-decoy-0511, v3-approval-decoy-0241` |
| `agentic_code_gen_rule_reflection` | 0.8571 | `alias-customer-codenames, esc-contoso, esc-urbannest, adv-beacon-oauth-3771, ticket-sec-1811` |

### sac-043 - fixed_flow_vs_single_preset

A generated query already found 900 candidates but no approval ledger. According to policy, should it stop or generate follow-up code?

multi-query hybrid baseline beat one routed preset stack

Relevant docs: `policy-reflection-missing-evidence-v3, source-authority-matrix-v3`

| System | Recall@10 | Top docs |
|---|---:|---|
| `fixed_flow_model_qr` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007` |
| `agentic_fixed_flow_rule_reflection` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007` |
| `preset_flow_model_router` | 0.0000 | `rollout-riverline-second-blocker-ledger, approval-beacon-contoso-may06, approval-quartzbio-namespace-proof, rel-atlas-4-8-2, rel-atlas-4-9-0` |
| `agentic_preset_flows_rule_reflection` | 0.5000 | `warroom-r7-june-critical-roster, approval-atlas-northwind-final, policy-sac-latency-ledger-v3, policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012` |
| `one_shot_code_gen_rule_policy` | 0.5000 | `policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012, v3-reflection-decoy-0017, v3-reflection-decoy-0002, v3-reflection-decoy-0007` |
| `agentic_code_gen_rule_reflection` | 0.5000 | `warroom-r7-june-critical-roster, approval-atlas-northwind-final, policy-sac-latency-ledger-v3, policy-reflection-missing-evidence-v3, v3-reflection-decoy-0012` |

## Notes

- The matrix now matches the proposed architecture taxonomy.
- Full-dataset planner/router/reflection decisions are rule-backed for reproducibility; real LLM codegen is still measured separately on focused samples because full-dataset model calls are expensive and less repeatable.
- A real LLM query-rewrite/planner/router/reflection provider can plug into the same boundaries later without changing the retrieval tools or metrics.
