#!/usr/bin/env python3
"""Run named, recognizable search baselines on the custom SAC dataset.

This is a calibration benchmark, separate from Search-as-Code and agentic
variants. The goal is to compare the custom enterprise dataset against common
retrieval stacks that map to well-known search implementations:

- Okapi BM25 / Lucene-style sparse retrieval
- Sentence-Transformers MiniLM bi-encoder dense retrieval
- Weighted BM25+dense hybrid retrieval
- Reciprocal Rank Fusion (RRF) over BM25 and dense retrieval
- Retrieve-and-rerank with a MiniLM CrossEncoder
- Query-understanding + rewrite + hybrid retrieve-and-rerank
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time
from typing import Callable

from real_search_stack.apis import (
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryRewriteAPI,
    RealQueryUnderstandingAPI,
    RealRankingAPI,
    SearchCandidate,
)
from run_flow_comparison import FlowContext, QueryStats, summarize_stats
from run_sac_dataset_benchmark import (
    DATASET_DIR,
    candidate_to_row,
    evaluate_query_at_ks,
    evaluate_results,
    load_dataset,
    read_json,
    relevant_doc_ids,
)


BASELINE_DEFINITIONS = {
    "okapi_bm25_rank_bm25": {
        "label": "Okapi BM25",
        "reference": "Lucene / Elasticsearch / OpenSearch-style sparse lexical retrieval",
        "implementation": "rank_bm25 BM25Okapi over title + body text",
    },
    "minilm_biencoder_dense": {
        "label": "MiniLM bi-encoder dense",
        "reference": "Sentence-Transformers dense semantic retrieval",
        "implementation": "sentence-transformers/all-MiniLM-L6-v2 cosine retrieval",
    },
    "weighted_hybrid_bm25_minilm": {
        "label": "Weighted BM25 + dense hybrid",
        "reference": "Common OpenSearch/Elasticsearch-style hybrid lexical + vector retrieval",
        "implementation": "min-max normalized BM25 and MiniLM scores, weighted 0.55/0.45",
    },
    "rrf_hybrid_bm25_minilm": {
        "label": "RRF BM25 + dense hybrid",
        "reference": "Reciprocal Rank Fusion hybrid retrieval",
        "implementation": "RRF over separate BM25 and MiniLM rankings with k=60",
    },
    "bm25_cross_encoder_rerank": {
        "label": "BM25 + CrossEncoder rerank",
        "reference": "Two-stage sparse retrieve-and-rerank",
        "implementation": "BM25 first stage, cross-encoder/ms-marco-MiniLM-L-6-v2 reranker",
    },
    "dense_cross_encoder_rerank": {
        "label": "Dense + CrossEncoder rerank",
        "reference": "Two-stage dense retrieve-and-rerank",
        "implementation": "MiniLM dense first stage, cross-encoder/ms-marco-MiniLM-L-6-v2 reranker",
    },
    "hybrid_cross_encoder_rerank": {
        "label": "Hybrid + CrossEncoder rerank",
        "reference": "Two-stage hybrid retrieve-and-rerank",
        "implementation": "weighted BM25+dense first stage, cross-encoder/ms-marco-MiniLM-L-6-v2 reranker",
    },
    "query_rewrite_hybrid_cross_encoder": {
        "label": "Query rewrite + hybrid + CrossEncoder",
        "reference": "Production-style query understanding/rewrite + hybrid retrieve-and-rerank",
        "implementation": "spaCy query understanding, deterministic rewrite, hybrid fanout, CrossEncoder rerank",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run named search baselines on the SAC custom dataset.")
    parser.add_argument("--data-dir", default=str(DATASET_DIR))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-k", default="10")
    parser.add_argument("--candidate-k", type=int, default=2400)
    parser.add_argument("--systems", default=",".join(BASELINE_DEFINITIONS))
    parser.add_argument("--output", default="named_search_baselines_results.json")
    parser.add_argument("--report", default="named_search_baselines_report.md")
    parser.add_argument("--wikidata", action="store_true")
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if args.offline_models:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    selected = [item.strip() for item in args.systems.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(BASELINE_DEFINITIONS))
    if unknown:
        raise SystemExit(f"Unknown systems: {', '.join(unknown)}")

    data_dir = Path(args.data_dir)
    documents, tasks, qrels, hard_negatives = load_dataset(data_dir, split=args.split)
    metrics_k = sorted({int(item) for item in args.metrics_k.split(",") if item.strip()})
    queries = {task["task_id"]: task["query"] for task in tasks}
    task_by_id = {task["task_id"]: task for task in tasks}

    print(f"Dataset: {data_dir}")
    print(f"Split: {args.split}")
    print(f"Documents: {len(documents)}")
    print(f"Tasks: {len(tasks)}")
    print(f"Systems: {', '.join(selected)}")
    print("Loading tools...")
    query_understanding_api = RealQueryUnderstandingAPI()
    entity_linking_api = RealEntityLinkingAPI(wikidata_enabled=args.wikidata)
    query_rewrite_api = RealQueryRewriteAPI()
    search_api = RealHybridSearchAPI(documents, local_files_only=args.offline_models)
    ranking_api = RealRankingAPI(local_files_only=args.offline_models)

    executors = build_executors(candidate_k=args.candidate_k, top_k=args.top_k)
    systems = {}
    for name in selected:
        systems[name] = run_named_system(
            name,
            queries,
            task_by_id,
            qrels,
            hard_negatives,
            args.top_k,
            metrics_k,
            executors[name],
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
        )

    manifest = read_json(data_dir / "manifest.json")
    output = {
        "dataset": manifest.get("dataset_version", "unknown"),
        "split": args.split,
        "documents": len(documents),
        "tasks": len(tasks),
        "top_k": args.top_k,
        "metrics_k": metrics_k,
        "candidate_k": args.candidate_k,
        "definitions": BASELINE_DEFINITIONS,
        "systems": systems,
        "summary_rows": build_summary_rows(systems, metrics_k),
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    Path(args.report).write_text(render_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def build_executors(*, candidate_k: int, top_k: int) -> dict[str, Callable[[FlowContext], dict]]:
    return {
        "okapi_bm25_rank_bm25": lambda ctx: simple_search(ctx, mode="bm25", top_k=top_k),
        "minilm_biencoder_dense": lambda ctx: simple_search(ctx, mode="dense", top_k=top_k),
        "weighted_hybrid_bm25_minilm": lambda ctx: simple_search(ctx, mode="hybrid", top_k=top_k),
        "rrf_hybrid_bm25_minilm": lambda ctx: rrf_hybrid(ctx, candidate_k=candidate_k, top_k=top_k),
        "bm25_cross_encoder_rerank": lambda ctx: retrieve_rerank(ctx, mode="bm25", candidate_k=candidate_k, top_k=top_k),
        "dense_cross_encoder_rerank": lambda ctx: retrieve_rerank(ctx, mode="dense", candidate_k=candidate_k, top_k=top_k),
        "hybrid_cross_encoder_rerank": lambda ctx: retrieve_rerank(ctx, mode="hybrid", candidate_k=candidate_k, top_k=top_k),
        "query_rewrite_hybrid_cross_encoder": lambda ctx: query_rewrite_hybrid_rerank(
            ctx,
            candidate_k=candidate_k,
            top_k=top_k,
        ),
    }


def simple_search(ctx: FlowContext, *, mode: str, top_k: int) -> dict:
    hits = ctx.search.search(ctx.query, mode=mode, top_k=top_k)
    ctx.candidate_pool = len(hits)
    ctx.log("named_baseline", {"mode": mode, "top_k": top_k})
    return {"hits": hits, "candidates": hits}


def retrieve_rerank(ctx: FlowContext, *, mode: str, candidate_k: int, top_k: int) -> dict:
    candidates = ctx.search.search(ctx.query, mode=mode, top_k=candidate_k)
    ctx.candidate_pool = len(candidates)
    hits = ctx.ranking.rerank(ctx.query, candidates, top_k=top_k)
    ctx.log(
        "named_baseline",
        {"mode": mode, "candidate_k": candidate_k, "reranker": "cross-encoder/ms-marco-MiniLM-L-6-v2"},
    )
    return {"hits": hits, "candidates": candidates}


def rrf_hybrid(ctx: FlowContext, *, candidate_k: int, top_k: int, rrf_k: int = 60) -> dict:
    bm25_hits = ctx.search.search(ctx.query, mode="bm25", top_k=candidate_k)
    dense_hits = ctx.search.search(ctx.query, mode="dense", top_k=candidate_k)
    by_id: dict[str, SearchCandidate] = {}
    scores: dict[str, float] = {}
    for ranking in [bm25_hits, dense_hits]:
        for rank, hit in enumerate(ranking, start=1):
            by_id.setdefault(hit.doc_id, hit)
            scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + 1.0 / (rrf_k + rank)
    candidates = sorted(by_id.values(), key=lambda hit: scores[hit.doc_id], reverse=True)
    ctx.candidate_pool = len(candidates)
    ctx.log("named_baseline", {"mode": "rrf", "candidate_k": candidate_k, "rrf_k": rrf_k})
    return {"hits": candidates[:top_k], "candidates": candidates}


def query_rewrite_hybrid_rerank(ctx: FlowContext, *, candidate_k: int, top_k: int) -> dict:
    analysis = ctx.query_understanding.analyze(ctx.query)
    linked_entities = ctx.entity_linking.link(ctx.query) if analysis.get("entities") else []
    rewrite = ctx.query_rewrite.rewrite(ctx.query, analysis=analysis, linked_entities=linked_entities)
    candidate_by_id = {}
    for query in [ctx.query] + rewrite.get("rewrites", []) + analysis.get("subqueries", [])[1:4]:
        hits = ctx.search.search(query, mode="hybrid", top_k=candidate_k, bm25_weight=0.55)
        for hit in hits:
            previous = candidate_by_id.get(hit.doc_id)
            if previous is None or hit.score > previous.score:
                candidate_by_id[hit.doc_id] = hit
    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)[:candidate_k]
    ctx.candidate_pool = len(candidates)
    hits = ctx.ranking.rerank(ctx.query, candidates, top_k=top_k)
    ctx.log(
        "named_baseline",
        {
            "mode": "query_rewrite_hybrid_rerank",
            "rewrites": rewrite.get("rewrites", []),
            "candidate_k": candidate_k,
        },
    )
    return {"hits": hits, "candidates": candidates}


def run_named_system(
    name: str,
    queries: dict[str, str],
    task_by_id: dict[str, dict],
    qrels: dict,
    hard_negatives: dict[str, set[str]],
    top_k: int,
    metrics_k: list[int],
    executor: Callable[[FlowContext], dict],
    *,
    query_understanding_api: RealQueryUnderstandingAPI,
    entity_linking_api: RealEntityLinkingAPI,
    query_rewrite_api: RealQueryRewriteAPI,
    search_api: RealHybridSearchAPI,
    ranking_api: RealRankingAPI,
) -> dict:
    print(f"Running {name}...")
    results: dict[str, list[dict]] = {}
    stats: list[QueryStats] = []
    per_query = []

    for idx, (qid, query) in enumerate(queries.items(), start=1):
        start = time.perf_counter()
        ctx = FlowContext(
            query,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
        )
        result = executor(ctx)
        latency_ms = (time.perf_counter() - start) * 1000
        hits = result["hits"][:top_k]
        query_stats = ctx.stats(latency_ms=latency_ms, generation_ms=0.0, execution_ms=latency_ms)
        stats.append(query_stats)
        results[qid] = [candidate_to_row(hit, rank) for rank, hit in enumerate(hits, start=1)]
        per_query.append(
            {
                "qid": qid,
                "category": task_by_id[qid]["category"],
                "difficulty": task_by_id[qid]["difficulty"],
                "query": query,
                "top_doc_ids": [hit.doc_id for hit in hits],
                "relevant_doc_ids": relevant_doc_ids(qrels[qid]),
                "hard_negative_doc_ids": sorted(hard_negatives.get(qid, set())),
                "query_metrics": evaluate_query_at_ks(
                    qrels[qid],
                    hard_negatives.get(qid, set()),
                    [hit.doc_id for hit in hits],
                    metrics_k,
                ),
                "stats": asdict(query_stats),
                "trace": ctx.trace[:8],
            }
        )
        if idx % 20 == 0:
            print(f"  {idx}/{len(queries)}")

    metrics = evaluate_results(qrels, hard_negatives, results, metrics_k)
    latency = summarize_stats(stats)
    print(f"{name}: {metrics}, latency={latency}")
    return {"metrics": metrics, "latency": latency, "per_query": per_query}


def build_summary_rows(systems: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    rows = []
    for name, result in systems.items():
        definition = BASELINE_DEFINITIONS[name]
        row = {
            "system": name,
            "label": definition["label"],
            "reference": definition["reference"],
            "implementation": definition["implementation"],
            f"recall@{k}": result["metrics"][f"recall@{k}"],
            f"ndcg@{k}": result["metrics"][f"ndcg@{k}"],
            f"mrr@{k}": result["metrics"][f"mrr@{k}"],
        }
        row.update(result["latency"])
        rows.append(row)
    rows.sort(key=lambda item: (item[f"recall@{k}"], item[f"ndcg@{k}"]), reverse=True)
    return rows


def render_report(output: dict) -> str:
    k = max(output["metrics_k"])
    lines = [
        "# Named Search Baseline Calibration",
        "",
        "This report calibrates the custom enterprise dataset against recognizable retrieval stacks. It is not an agentic or codegen result.",
        "",
        f"- Dataset: `{output['dataset']}` / split `{output['split']}`",
        f"- Documents: `{output['documents']}`",
        f"- Tasks: `{output['tasks']}`",
        f"- Candidate budget for rerank/RRF systems: `{output['candidate_k']}`",
        f"- Metric: `Recall@{k}`",
        "",
        "| System | Recognizable reference | Recall@10 | nDCG@10 | MRR@10 | Total ms | Search calls | Rerank pairs |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in output["summary_rows"]:
        lines.append(
            f"| `{row['label']}` | {row['reference']} | {row[f'recall@{k}']:.4f} | "
            f"{row[f'ndcg@{k}']:.4f} | {row[f'mrr@{k}']:.4f} | {row['mean_latency_ms']:.1f} | "
            f"{row['mean_search_calls']:.2f} | {row['mean_rerank_pairs']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Readout",
            "",
            "- BM25 is expected to be strong when exact identifiers matter; dense-only retrieval should be weaker on CVEs, tickets, aliases, and version strings.",
            "- The generic MS MARCO CrossEncoder is a weak fit for this benchmark's multi-evidence Recall@10 objective; it often promotes semantically similar decoys over source-of-truth coverage.",
            "- The separate diagnostic report shows hybrid retrieval has much higher candidate-pool recall than top-10 recall, so the headroom is in final selection and evidence-aware follow-up, not just first-stage retrieval.",
            "- If agentic/codegen systems beat these baselines on the custom dataset, the lift should come from evidence coverage and controlled follow-up routes, not from a weak lexical baseline.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
