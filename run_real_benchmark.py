#!/usr/bin/env python3
"""Run a real public IR benchmark with real open-source search APIs.

Default benchmark: BEIR/SciFact.

Metrics:
- nDCG@10
- Recall@10
- MRR@10

Systems:
- BM25 only
- dense only
- hybrid BM25+dense
- hybrid + cross-encoder reranker
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

from beir import util
from beir.datasets.data_loader import GenericDataLoader

from real_search_stack.apis import IndexedDocument, RealHybridSearchAPI, RealRankingAPI


BEIR_DATASETS = {
    "fever": "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/fever.zip",
    "scifact": "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip",
    "fiqa": "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/fiqa.zip",
    "hotpotqa": "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/hotpotqa.zip",
    "nq": "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/nq.zip",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real Search-as-Code benchmark.")
    parser.add_argument("--dataset", default="scifact", choices=sorted(BEIR_DATASETS))
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit-queries", type=int, default=0, help="0 means all queries")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument("--data-dir", default="benchmarks")
    parser.add_argument("--output", default="real_benchmark_results.json")
    args = parser.parse_args()

    data_path = download_dataset(args.dataset, Path(args.data_dir))
    corpus, queries, qrels = GenericDataLoader(data_path).load(split=args.split)
    if args.limit_queries:
        selected_ids = list(queries)[: args.limit_queries]
        queries = {qid: queries[qid] for qid in selected_ids}
        qrels = {qid: qrels[qid] for qid in selected_ids if qid in qrels}

    documents = [
        IndexedDocument(
            doc_id=doc_id,
            title=doc.get("title", ""),
            text=doc.get("text", ""),
            metadata={"dataset": args.dataset},
        )
        for doc_id, doc in corpus.items()
    ]

    print(f"Dataset: {args.dataset}")
    print(f"Documents: {len(documents)}")
    print(f"Queries: {len(queries)}")

    search_api = RealHybridSearchAPI(documents)
    reranker = RealRankingAPI()

    systems = {
        "bm25": lambda q: search_api.search(q, mode="bm25", top_k=args.top_k),
        "dense": lambda q: search_api.search(q, mode="dense", top_k=args.top_k),
        "hybrid": lambda q: search_api.search(q, mode="hybrid", top_k=args.top_k),
        "hybrid_rerank": lambda q: reranker.rerank(
            q,
            search_api.search(q, mode="hybrid", top_k=args.candidate_k),
            top_k=args.top_k,
        ),
    }

    results = {}
    for name, fn in systems.items():
        print(f"Running {name}...")
        system_results = {}
        for qid, query in queries.items():
            hits = fn(query)
            system_results[qid] = {hit.doc_id: float(hit.score) for hit in hits}
        metrics = evaluate(qrels, system_results, k=args.top_k)
        results[name] = metrics
        print(f"{name}: {metrics}")

    output = {
        "dataset": args.dataset,
        "split": args.split,
        "documents": len(documents),
        "queries": len(queries),
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "metrics": results,
    }
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


def download_dataset(dataset: str, data_dir: Path) -> str:
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / dataset
    if target.exists():
        return str(target)
    url = BEIR_DATASETS[dataset]
    downloaded = util.download_and_unzip(url, str(data_dir))
    return downloaded


def evaluate(qrels: dict, results: dict, k: int = 10) -> dict:
    ndcg_values = []
    recall_values = []
    mrr_values = []

    for qid, rels in qrels.items():
        if qid not in results:
            continue
        relevant = {doc_id for doc_id, rel in rels.items() if rel > 0}
        if not relevant:
            continue
        ranked = sorted(results[qid].items(), key=lambda item: item[1], reverse=True)[:k]
        ranked_ids = [doc_id for doc_id, _score in ranked]

        dcg = 0.0
        for rank, doc_id in enumerate(ranked_ids, start=1):
            rel = rels.get(doc_id, 0)
            if rel > 0:
                dcg += (2**rel - 1) / math.log2(rank + 1)
        ideal_rels = sorted([rel for rel in rels.values() if rel > 0], reverse=True)[:k]
        idcg = sum((2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(ideal_rels, start=1))
        ndcg_values.append(dcg / idcg if idcg else 0.0)

        hits = len(set(ranked_ids) & relevant)
        recall_values.append(hits / len(relevant))

        mrr = 0.0
        for rank, doc_id in enumerate(ranked_ids, start=1):
            if doc_id in relevant:
                mrr = 1.0 / rank
                break
        mrr_values.append(mrr)

    return {
        f"ndcg@{k}": round(_mean(ndcg_values), 4),
        f"recall@{k}": round(_mean(recall_values), 4),
        f"mrr@{k}": round(_mean(mrr_values), 4),
        "evaluated_queries": len(ndcg_values),
    }


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    main()
