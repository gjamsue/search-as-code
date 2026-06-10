# Search Baseline Diagnostics

This diagnostic separates first-stage retrieval coverage from final CrossEncoder reranking.

- Split: `test`
- Documents: `6010`
- Tasks: `31`

## First-stage candidate recall

| Mode | Recall@10 | Recall@50 | Recall@200 | Recall@2400 |
|---|---:|---:|---:|---:|
| `bm25` | 0.2387 | 0.3098 | 0.4507 | 0.6846 |
| `dense` | 0.0949 | 0.1186 | 0.2375 | 0.7024 |
| `hybrid` | 0.2375 | 0.2699 | 0.3611 | 0.7496 |

## Hybrid + CrossEncoder budget sweep

| Candidate budget | Candidate-pool recall | Rerank Recall@10 | Mean latency |
|---:|---:|---:|---:|
| 20 | 0.2488 | 0.1798 | 75.2 ms |
| 50 | 0.2699 | 0.1762 | 170.7 ms |
| 100 | 0.3153 | 0.1827 | 288.2 ms |
| 200 | 0.3611 | 0.1773 | 511.8 ms |
| 400 | 0.4491 | 0.1864 | 936.0 ms |
| 2400 | 0.7496 | 0.2018 | 5340.3 ms |

## Readout

- Hybrid first-stage retrieval has substantially higher candidate-pool coverage than its top-10 result, so there is headroom for a better final selector.
- The generic `cross-encoder/ms-marco-MiniLM-L-6-v2` reranker reduces Recall@10 on this multi-evidence enterprise task. Treat it as a mismatch diagnostic, not as the strongest possible production reranker.
- The current named-baseline slide should not claim that evidence is missing from retrieval; the sharper diagnosis is that a generic single-passage reranker demotes source-of-truth and coverage-diverse evidence in favor of similar decoys.

## Largest reranker losses

### `sac-025`

- Query: Should BluePeak Insurance be included in the SAML connector emergency rollout?
- Candidate-pool recall: `1.0000`; rerank Recall@10: `0.0000`
- First-stage top docs: `cluster-customer-bluepeak-email-044, cluster-customer-bluepeak-email-004, cluster-customer-bluepeak-email-028, cluster-customer-bluepeak-email-036, cluster-customer-bluepeak-email-020, cluster-customer-bluepeak-email-012, meet-bluepeak, cluster-customer-bluepeak-escalation-035`
- Reranked top docs: `cluster-atlas-saml-4102-postmortem-058, cluster-atlas-saml-4102-postmortem-018, cluster-atlas-saml-4102-postmortem-038, cluster-atlas-saml-4102-ticket-023, cluster-atlas-saml-4102-ticket-033, cluster-atlas-saml-4102-ticket-003, cluster-atlas-saml-4102-ticket-043, cluster-atlas-saml-4102-ticket-053`
- Relevant docs: `acct-bluepeak, adv-atlas-rerank-4520, adv-atlas-saml-4102, esc-bluepeak, ticket-sec-1842, warroom-r7-june-critical-roster`

### `sac-035`

- Query: If generated code finds no ForgeDeploy documents for NovaFoods, should it keep searching or answer with negative evidence?
- Candidate-pool recall: `1.0000`; rerank Recall@10: `0.0000`
- First-stage top docs: `negative-forgedeploy-novafoods, v3-approval-decoy-0060, v3-approval-decoy-0660, v3-approval-decoy-0600, v3-approval-decoy-0810, v3-approval-decoy-0510, v3-approval-decoy-0900, v3-approval-decoy-0090`
- Reranked top docs: `v3-approval-decoy-0185, v3-approval-decoy-0785, v3-approval-decoy-0665, v3-approval-decoy-0485, v3-approval-decoy-0635, v3-approval-decoy-0005, v3-approval-decoy-0215, v3-approval-decoy-0125`
- Relevant docs: `acct-novafoods, negative-forgedeploy-novafoods`

### `sac-036`

- Query: Which accounts have the same technical owner for different product blockers, and what does that imply for staffing?
- Candidate-pool recall: `1.0000`; rerank Recall@10: `0.0000`
- First-stage top docs: `alias-owner-directory, decoy-acct-union-manufacturing, decoy-acct-stonegate-retail, decoy-acct-anchor-retail, decoy-acct-bayside-foods, decoy-acct-apex-foods, decoy-acct-hearth-foods, decoy-acct-sierra-labs`
- Reranked top docs: `decoy-acct-union-manufacturing, decoy-acct-anchor-retail, decoy-acct-cobalt-logistics, decoy-acct-marble-logistics, decoy-acct-evergreen-manufacturing, decoy-acct-arbor-retail, decoy-acct-cascade-logistics, decoy-acct-solstice-manufacturing`
- Relevant docs: `acct-bluepeak, acct-contoso, acct-greenhouse, acct-heliogrid, acct-northwind, acct-quartzbio, acct-riverline, acct-urbannest`

### `sac-027`

- Query: Across all red-risk accounts, which technical owners have more than one renewal blocker assigned?
- Candidate-pool recall: `1.0000`; rerank Recall@10: `0.1429`
- First-stage top docs: `alias-owner-directory, acct-bluepeak, decoy-acct-copper-health, decoy-acct-pioneer-insurance, decoy-acct-stonegate-retail, decoy-acct-pacific-energy, decoy-acct-pinnacle-retail, decoy-acct-union-manufacturing`
- Reranked top docs: `decoy-acct-solstice-manufacturing, decoy-acct-citrine-logistics, decoy-acct-copper-health, decoy-acct-arbor-retail, decoy-acct-pinnacle-retail, decoy-acct-silver-labs, decoy-acct-sierra-labs, decoy-acct-noble-foods`
- Relevant docs: `acct-aster, acct-heliogrid, acct-northwind, acct-riverline, esc-aster, esc-northwind, esc-riverline`

