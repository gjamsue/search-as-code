# Harness-1 Benchmark Feasibility

This note maps the benchmarks from [Harness-1: Reinforcement Learning for Search Agents with State-Externalizing Harnesses](https://arxiv.org/abs/2606.02373) to this repo's Search-as-Code evaluation setup.

## Short Answer

Yes, we should use the Harness-1 benchmark family as an external reference, but only in tiers:

- **Run now / overlap:** HotpotQA is already included in our public matrix as a local dev-distractor sanity check.
- **Add next:** BrowseComp+ is the best Harness-1-aligned public add. The Harness-1 repo calls it the public ready-to-run path, but it still requires a matching retrieval corpus/index.
- **Add with setup:** FRAMES, Seal0QA, and LongSealQA can be added if we settle the corpus/retrieval backend and qrels format.
- **Do not claim direct reproduction yet:** Web, Patents, and SEC require reconstructed or private Chroma collections. Harness-1 does not bundle those large corpora/indexes.

## Benchmark Mapping

| Harness-1 benchmark | Domain pressure | Public reproducibility | Status in this repo | Recommended action |
|---|---|---|---|---|
| BrowseComp+ | hard web search, multi-constraint evidence | Public query/qrels path, but requires matching Chroma/corpus chunks | Loader added as `harness1/browsecompplus` when local files are provided | Build/export corpus JSONL with qrel-matching IDs, then run the same 6-variant matrix |
| HotpotQA subset | Wikipedia-style multi-hop retrieval | Public | Already covered as `hotpotqa/distractor`, but not the exact Harness-1 full setting | Keep as overlap sanity check; label carefully |
| FRAMES | multi-hop QA with evidence | Public dataset, retrieval setup needs normalization | Not added | Add after BrowseComp+ if we want another multi-hop public set |
| Seal0QA | open-web multi-hop retrieval | Publicness/retrieval backend needs confirmation | Not added | Treat as optional transfer benchmark |
| LongSealQA | long-context open-web retrieval | Needs dedicated corpus/index setup | Not added | Add only if it materially improves the CEO story |
| Web | in-domain web encyclopedic retrieval | Harness-1 release does not ship ready-made corpus/index | Not added | Do not claim until a compatible Chroma/corpus export exists |
| Patents | patent/legal/technical retrieval | Harness-1 release does not ship ready-made corpus/index | Not added | Defer unless patent retrieval becomes important |
| SEC | financial filing retrieval | Harness-1 release does not ship ready-made corpus/index | Not added | Defer or rebuild from SEC filings if finance use case matters |

## Repo Support Added

`run_public_benchmarks.py` now accepts:

```bash
python run_public_benchmarks.py \
  --benchmarks harness1/browsecompplus \
  --systems fixed_flow_model_qr,preset_flow_model_router,agentic_fixed_flow_rule_reflection,agentic_preset_flows_rule_reflection,one_shot_code_gen_rule_policy,agentic_code_gen_rule_reflection \
  --candidate-k 40 \
  --output harness1_browsecompplus_results.json \
  --report harness1_browsecompplus_report.md
```

Required local files:

```bash
export BROWSECOMPPLUS_QUERIES_PATH=external/BrowseComp-Plus/topics-qrels/queries.tsv
export BROWSECOMPPLUS_QRELS_GOLD_PATH=external/BrowseComp-Plus/topics-qrels/qrel_golds.txt
export BROWSECOMPPLUS_QRELS_EVIDENCE_PATH=external/BrowseComp-Plus/topics-qrels/qrel_evidence.txt
export BROWSECOMPPLUS_CORPUS_JSONL=benchmarks/harness1/browsecompplus_corpus.jsonl
```

The corpus JSONL must contain document IDs matching the qrels:

```jsonl
{"doc_id":"...", "title":"...", "text":"...", "metadata":{}}
```

The runner validates that qrel document IDs exist in the corpus before running, because a mismatched corpus would make the comparison meaningless.

## Message For The Presentation

Use this as one concise point:

> Harness-1 gives us a credible external benchmark direction. We already cover HotpotQA overlap, and we can add BrowseComp+ once the matching corpus/index is available. We should not claim full Harness-1 reproduction until the Web/Patents/SEC Chroma corpora are reconstructed or obtained.

## Sources

- [Harness-1 paper](https://arxiv.org/abs/2606.02373)
- [Harness-1 GitHub repo](https://github.com/pat-jj/harness-1)
- [Harness-1 dataset notes](https://github.com/pat-jj/harness-1/blob/main/datagen/README.md)
- [Harness-1 inference/evaluation notes](https://github.com/pat-jj/harness-1/blob/main/inference/README.md)
- [BrowseComp-Plus](https://github.com/texttron/BrowseComp-Plus)
