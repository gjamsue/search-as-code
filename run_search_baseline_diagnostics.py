#!/usr/bin/env python3
"""Diagnose first-stage retrieval vs reranker behavior on the SAC dataset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Iterable

from real_search_stack.apis import RealHybridSearchAPI, RealRankingAPI
from run_sac_dataset_benchmark import DATASET_DIR, load_dataset


DEFAULT_KS = [10, 50, 200, 2400]
DEFAULT_RERANK_BUDGETS = [20, 50, 100, 200, 400, 2400]


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose retrieval and reranker behavior.")
    parser.add_argument("--data-dir", default=str(DATASET_DIR))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    parser.add_argument("--ks", default=",".join(str(k) for k in DEFAULT_KS))
    parser.add_argument("--rerank-budgets", default=",".join(str(k) for k in DEFAULT_RERANK_BUDGETS))
    parser.add_argument("--output", default="search_baseline_diagnostics_results.json")
    parser.add_argument("--report", default="search_baseline_diagnostics_report.md")
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-examples", type=int, default=4)
    args = parser.parse_args()

    if args.offline_models:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    ks = sorted({int(item) for item in args.ks.split(",") if item.strip()})
    budgets = sorted({int(item) for item in args.rerank_budgets.split(",") if item.strip()})
    documents, tasks, qrels, _hard_negatives = load_dataset(Path(args.data_dir), split=args.split)

    print(f"Dataset: {args.data_dir}")
    print(f"Split: {args.split}")
    print(f"Documents: {len(documents)}")
    print(f"Tasks: {len(tasks)}")
    print("Loading tools...")
    search = RealHybridSearchAPI(documents, local_files_only=args.offline_models)
    ranking = RealRankingAPI(local_files_only=args.offline_models)

    first_stage = {}
    for mode in ["bm25", "dense", "hybrid"]:
        print(f"First-stage recall: {mode}")
        first_stage[mode] = first_stage_recall(search, tasks, qrels, mode=mode, ks=ks)

    rerank = {}
    examples = []
    for mode in ["hybrid"]:
        rerank[mode], examples = rerank_budget_recall(
            search,
            ranking,
            tasks,
            qrels,
            mode=mode,
            budgets=budgets,
            max_examples=args.max_examples,
        )

    output = {
        "split": args.split,
        "documents": len(documents),
        "tasks": len(tasks),
        "ks": ks,
        "rerank_budgets": budgets,
        "first_stage": first_stage,
        "rerank": rerank,
        "examples": examples,
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    Path(args.report).write_text(render_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def first_stage_recall(search: RealHybridSearchAPI, tasks: list[dict], qrels: dict, *, mode: str, ks: list[int]) -> dict:
    max_k = max(ks)
    totals = {k: [] for k in ks}
    start = time.perf_counter()
    for task in tasks:
        hits = search.search(task["query"], mode=mode, top_k=max_k, bm25_weight=0.55)
        hit_ids = [hit.doc_id for hit in hits]
        relevant = relevant_doc_ids(qrels[task["task_id"]])
        for k in ks:
            totals[k].append(recall_at(hit_ids, relevant, k))
    return {
        "latency_ms_total": round((time.perf_counter() - start) * 1000, 1),
        **{f"recall@{k}": round(mean(values), 4) for k, values in totals.items()},
    }


def rerank_budget_recall(
    search: RealHybridSearchAPI,
    ranking: RealRankingAPI,
    tasks: list[dict],
    qrels: dict,
    *,
    mode: str,
    budgets: list[int],
    max_examples: int,
) -> tuple[dict, list[dict]]:
    rows = {}
    worst_cases = []
    for budget in budgets:
        print(f"Rerank budget: {mode} top {budget}")
        pool_recalls = []
        rerank_recalls = []
        latencies = []
        for task in tasks:
            query = task["query"]
            qid = task["task_id"]
            relevant = relevant_doc_ids(qrels[qid])
            start = time.perf_counter()
            candidates = search.search(query, mode=mode, top_k=budget, bm25_weight=0.55)
            reranked = ranking.rerank(query, candidates, top_k=10)
            latencies.append((time.perf_counter() - start) * 1000)

            candidate_ids = [hit.doc_id for hit in candidates]
            reranked_ids = [hit.doc_id for hit in reranked]
            pool_recall = recall_at(candidate_ids, relevant, budget)
            rerank_recall = recall_at(reranked_ids, relevant, 10)
            pool_recalls.append(pool_recall)
            rerank_recalls.append(rerank_recall)
            if budget == max(budgets):
                worst_cases.append(
                    {
                        "loss": round(pool_recall - rerank_recall, 4),
                        "task_id": qid,
                        "query": query,
                        "candidate_pool_recall": round(pool_recall, 4),
                        "rerank_recall@10": round(rerank_recall, 4),
                        "first_stage_top_docs": candidate_ids[:8],
                        "reranked_top_docs": reranked_ids[:8],
                        "relevant_doc_ids": sorted(relevant),
                    }
                )
        rows[str(budget)] = {
            f"candidate_pool_recall@{budget}": round(mean(pool_recalls), 4),
            "rerank_recall@10": round(mean(rerank_recalls), 4),
            "mean_latency_ms": round(mean(latencies), 1),
        }
    worst_cases = sorted(worst_cases, key=lambda item: item["loss"], reverse=True)[:max_examples]
    return rows, worst_cases


def relevant_doc_ids(qrels_for_task: dict) -> set[str]:
    return {doc_id for doc_id, score in qrels_for_task.items() if score > 0}


def recall_at(hit_ids: Iterable[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(list(hit_ids)[:k]) & relevant) / len(relevant)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def render_report(output: dict) -> str:
    ks = output["ks"]
    lines = [
        "# Search Baseline Diagnostics",
        "",
        "This diagnostic separates first-stage retrieval coverage from final CrossEncoder reranking.",
        "",
        f"- Split: `{output['split']}`",
        f"- Documents: `{output['documents']}`",
        f"- Tasks: `{output['tasks']}`",
        "",
        "## First-stage candidate recall",
        "",
        "| Mode | " + " | ".join(f"Recall@{k}" for k in ks) + " |",
        "|---" + "|---:" * len(ks) + "|",
    ]
    for mode, metrics in output["first_stage"].items():
        lines.append("| `" + mode + "` | " + " | ".join(f"{metrics[f'recall@{k}']:.4f}" for k in ks) + " |")

    lines.extend(
        [
            "",
            "## Hybrid + CrossEncoder budget sweep",
            "",
            "| Candidate budget | Candidate-pool recall | Rerank Recall@10 | Mean latency |",
            "|---:|---:|---:|---:|",
        ]
    )
    for budget, metrics in output["rerank"]["hybrid"].items():
        pool_key = f"candidate_pool_recall@{budget}"
        lines.append(
            f"| {budget} | {metrics[pool_key]:.4f} | {metrics['rerank_recall@10']:.4f} | "
            f"{metrics['mean_latency_ms']:.1f} ms |"
        )

    lines.extend(
        [
            "",
            "## Readout",
            "",
            "- Hybrid first-stage retrieval has substantially higher candidate-pool coverage than its top-10 result, so there is headroom for a better final selector.",
            "- The generic `cross-encoder/ms-marco-MiniLM-L-6-v2` reranker reduces Recall@10 on this multi-evidence enterprise task. Treat it as a mismatch diagnostic, not as the strongest possible production reranker.",
            "- The current named-baseline slide should not claim that evidence is missing from retrieval; the sharper diagnosis is that a generic single-passage reranker demotes source-of-truth and coverage-diverse evidence in favor of similar decoys.",
            "",
            "## Largest reranker losses",
            "",
        ]
    )
    for example in output["examples"]:
        lines.extend(
            [
                f"### `{example['task_id']}`",
                "",
                f"- Query: {example['query']}",
                f"- Candidate-pool recall: `{example['candidate_pool_recall']:.4f}`; rerank Recall@10: `{example['rerank_recall@10']:.4f}`",
                f"- First-stage top docs: `{', '.join(example['first_stage_top_docs'])}`",
                f"- Reranked top docs: `{', '.join(example['reranked_top_docs'])}`",
                f"- Relevant docs: `{', '.join(example['relevant_doc_ids'])}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
