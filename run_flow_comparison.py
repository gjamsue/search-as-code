#!/usr/bin/env python3
"""Compare generated Search-as-Code flow against a fixed retrieval flow.

The comparison is intentionally end-to-end:

- Fixed flow:
  query -> hybrid search -> cross-encoder rerank

- Generated Search-as-Code flow:
  query -> generate Python search program -> execute program that calls
  query-understanding, entity-linking, search, reflection/fallback, and rerank

Metrics include retrieval quality and wall-clock latency.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import statistics
import textwrap
import time
from typing import Callable

from beir.datasets.data_loader import GenericDataLoader

from real_search_stack.apis import (
    IndexedDocument,
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryUnderstandingAPI,
    RealQueryRewriteAPI,
    RealRankingAPI,
    SearchCandidate,
    tokenize,
)
from run_real_benchmark import BEIR_DATASETS, download_dataset, evaluate


@dataclass
class QueryStats:
    latency_ms: float
    generation_ms: float
    execution_ms: float
    query_understanding_calls: int
    entity_linking_calls: int
    query_rewrite_calls: int
    search_calls: int
    rerank_calls: int
    rerank_pairs: int
    candidate_pool: int


class QueryUnderstandingProxy:
    def __init__(self, ctx: FlowContext, api: RealQueryUnderstandingAPI) -> None:
        self.ctx = ctx
        self.api = api

    def analyze(self, query: str) -> dict:
        self.ctx.query_understanding_calls += 1
        return self.api.analyze(query)


class EntityLinkingProxy:
    def __init__(self, ctx: FlowContext, api: RealEntityLinkingAPI) -> None:
        self.ctx = ctx
        self.api = api

    def link(self, text: str) -> list[dict]:
        self.ctx.entity_linking_calls += 1
        return self.api.link(text)


class QueryRewriteProxy:
    def __init__(self, ctx: FlowContext, api: RealQueryRewriteAPI) -> None:
        self.ctx = ctx
        self.api = api

    def should_rewrite(self, query: str, analysis: dict) -> bool:
        return self.api.should_rewrite(query, analysis)

    def rewrite(self, query: str, *, analysis: dict | None = None, linked_entities: list[dict] | None = None) -> dict:
        self.ctx.query_rewrite_calls += 1
        return self.api.rewrite(query, analysis=analysis, linked_entities=linked_entities)


class SearchProxy:
    def __init__(self, ctx: FlowContext, api: RealHybridSearchAPI) -> None:
        self.ctx = ctx
        self.api = api

    def search(self, query: str, *, mode: str = "hybrid", top_k: int = 20, **kwargs) -> list[SearchCandidate]:
        self.ctx.search_calls += 1
        return self.api.search(query, mode=mode, top_k=top_k, **kwargs)


class RankingProxy:
    def __init__(self, ctx: FlowContext, api: RealRankingAPI) -> None:
        self.ctx = ctx
        self.api = api

    def rerank(
        self,
        query: str,
        candidates: list[SearchCandidate],
        *,
        top_k: int = 10,
    ) -> list[SearchCandidate]:
        self.ctx.rerank_calls += 1
        self.ctx.rerank_pairs += len(candidates)
        return self.api.rerank(query, candidates, top_k=top_k)


class FlowContext:
    def __init__(
        self,
        query: str,
        *,
        query_understanding_api: RealQueryUnderstandingAPI,
        entity_linking_api: RealEntityLinkingAPI,
        query_rewrite_api: RealQueryRewriteAPI,
        search_api: RealHybridSearchAPI,
        ranking_api: RealRankingAPI,
    ) -> None:
        self.query = query
        self.query_understanding_calls = 0
        self.entity_linking_calls = 0
        self.query_rewrite_calls = 0
        self.search_calls = 0
        self.rerank_calls = 0
        self.rerank_pairs = 0
        self.candidate_pool = 0
        self.trace: list[dict] = []
        self.query_understanding = QueryUnderstandingProxy(self, query_understanding_api)
        self.entity_linking = EntityLinkingProxy(self, entity_linking_api)
        self.query_rewrite = QueryRewriteProxy(self, query_rewrite_api)
        self.search = SearchProxy(self, search_api)
        self.ranking = RankingProxy(self, ranking_api)

    def log(self, event: str, payload: dict) -> None:
        self.trace.append({"event": event, "payload": payload})

    def stats(self, *, latency_ms: float, generation_ms: float, execution_ms: float) -> QueryStats:
        return QueryStats(
            latency_ms=latency_ms,
            generation_ms=generation_ms,
            execution_ms=execution_ms,
            query_understanding_calls=self.query_understanding_calls,
            entity_linking_calls=self.entity_linking_calls,
            query_rewrite_calls=self.query_rewrite_calls,
            search_calls=self.search_calls,
            rerank_calls=self.rerank_calls,
            rerank_pairs=self.rerank_pairs,
            candidate_pool=self.candidate_pool,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare generated Search-as-Code flow vs fixed flow.")
    parser.add_argument("--dataset", default="scifact", choices=sorted(BEIR_DATASETS))
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit-queries", type=int, default=0, help="0 means all queries")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--fixed-small-candidate-k", type=int, default=32)
    parser.add_argument("--generated-branch-top-k", type=int, default=15)
    parser.add_argument("--generated-max-rerank-candidates", type=int, default=50)
    parser.add_argument("--generated-min-rerank-candidates", type=int, default=0)
    parser.add_argument("--data-dir", default="benchmarks")
    parser.add_argument("--output", default="generated_vs_fixed_flow_results.json")
    parser.add_argument("--sample-codes", type=int, default=3)
    parser.add_argument("--per-query", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--wikidata", action="store_true", help="Enable live Wikidata linking in generated flow.")
    parser.add_argument(
        "--offline-models",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use locally cached HuggingFace models. Disable if models are not cached.",
    )
    args = parser.parse_args()

    if args.offline_models:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

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
    print("Loading tools...")
    query_understanding_api = RealQueryUnderstandingAPI()
    entity_linking_api = RealEntityLinkingAPI(wikidata_enabled=args.wikidata)
    query_rewrite_api = RealQueryRewriteAPI()
    search_api = RealHybridSearchAPI(documents, local_files_only=args.offline_models)
    ranking_api = RealRankingAPI(local_files_only=args.offline_models)

    systems = {}
    for mode, label in [
        ("bm25", "fixed_bm25"),
        ("dense", "fixed_semantic_dense"),
        ("hybrid", "fixed_hybrid"),
    ]:
        systems[label] = run_system(
            label,
            queries,
            qrels,
            args.top_k,
            lambda query, mode=mode: fixed_search_code(mode),
            lambda code, ctx, mode=mode: run_fixed_search(ctx, mode=mode, top_k=args.top_k),
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=0,
            include_per_query=args.per_query,
        )

    systems["fixed_hybrid_rerank_small_budget"] = run_system(
        "fixed_hybrid_rerank_small_budget",
        queries,
        qrels,
        args.top_k,
        lambda query: fixed_rerank_code(args.fixed_small_candidate_k),
        lambda code, ctx: run_fixed_rerank(ctx, candidate_k=args.fixed_small_candidate_k, top_k=args.top_k),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=0,
        include_per_query=args.per_query,
    )

    systems["fixed_hybrid_rerank"] = run_system(
        "fixed_hybrid_rerank",
        queries,
        qrels,
        args.top_k,
        lambda query: fixed_rerank_code(args.candidate_k),
        lambda code, ctx: run_fixed_rerank(ctx, candidate_k=args.candidate_k, top_k=args.top_k),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=0,
        include_per_query=args.per_query,
    )

    systems["fixed_understanding_rewrite_hybrid_rerank"] = run_system(
        "fixed_understanding_rewrite_hybrid_rerank",
        queries,
        qrels,
        args.top_k,
        lambda query: fixed_enriched_rerank_code(args.candidate_k),
        lambda code, ctx: run_fixed_enriched_rerank(ctx, candidate_k=args.candidate_k, top_k=args.top_k),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=0,
        include_per_query=args.per_query,
    )

    systems["generated_search_as_code"] = run_system(
        "generated_search_as_code",
        queries,
        qrels,
        args.top_k,
        lambda query: generate_search_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
            min_rerank_candidates=args.generated_min_rerank_candidates,
        ),
        execute_generated_program,
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=args.sample_codes,
        include_per_query=args.per_query,
    )

    systems["generated_search_as_code_force_budget"] = run_system(
        "generated_search_as_code_force_budget",
        queries,
        qrels,
        args.top_k,
        lambda query: generate_search_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
            min_rerank_candidates=args.candidate_k,
        ),
        execute_generated_program,
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=args.sample_codes,
        include_per_query=args.per_query,
    )

    systems["generated_reflective_search_as_code"] = run_system(
        "generated_reflective_search_as_code",
        queries,
        qrels,
        args.top_k,
        lambda query: generate_reflective_initial_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
        ),
        lambda code, ctx: execute_reflective_generated_program(
            code,
            ctx,
            top_k=args.top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
        ),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=args.sample_codes,
        include_per_query=args.per_query,
    )

    output = {
        "dataset": args.dataset,
        "split": args.split,
        "documents": len(documents),
        "queries": len(queries),
        "top_k": args.top_k,
        "fixed_candidate_k": args.candidate_k,
        "fixed_small_candidate_k": args.fixed_small_candidate_k,
        "generated_branch_top_k": args.generated_branch_top_k,
        "generated_max_rerank_candidates": args.generated_max_rerank_candidates,
        "generated_min_rerank_candidates": args.generated_min_rerank_candidates,
        "wikidata_enabled": args.wikidata,
        "systems": systems,
        "comparisons": build_comparisons(systems, k=args.top_k),
    }
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(json.dumps(output["comparisons"], indent=2))


def run_system(
    name: str,
    queries: dict,
    qrels: dict,
    top_k: int,
    code_generator: Callable[[str], str],
    executor: Callable[[str, FlowContext], dict],
    *,
    query_understanding_api: RealQueryUnderstandingAPI,
    entity_linking_api: RealEntityLinkingAPI,
    query_rewrite_api: RealQueryRewriteAPI,
    search_api: RealHybridSearchAPI,
    ranking_api: RealRankingAPI,
    sample_codes: int,
    include_per_query: bool,
) -> dict:
    print(f"Running {name}...")
    system_results = {}
    stats: list[QueryStats] = []
    code_samples = []
    per_query = []

    for idx, (qid, query) in enumerate(queries.items(), start=1):
        total_start = time.perf_counter()
        generation_start = time.perf_counter()
        code = code_generator(query)
        generation_ms = (time.perf_counter() - generation_start) * 1000

        ctx = FlowContext(
            query,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
        )
        execution_start = time.perf_counter()
        result = executor(code, ctx)
        execution_ms = (time.perf_counter() - execution_start) * 1000
        latency_ms = (time.perf_counter() - total_start) * 1000
        executed_code = result.get("_executed_code", code)

        hits = result["hits"]
        top_hits = hits[:top_k]
        system_results[qid] = {hit.doc_id: float(hit.score) for hit in top_hits}
        query_stats = ctx.stats(latency_ms=latency_ms, generation_ms=generation_ms, execution_ms=execution_ms)
        stats.append(query_stats)
        if include_per_query:
            ranked_ids = [hit.doc_id for hit in top_hits]
            per_query.append(
                {
                    "qid": qid,
                    "query": query,
                    "top_doc_ids": ranked_ids,
                    "top_titles": [hit.title for hit in top_hits],
                    "relevant_doc_ids": relevant_doc_ids(qrels.get(qid, {})),
                    "query_metrics": score_query(qrels.get(qid, {}), ranked_ids, k=top_k),
                    "stats": asdict(query_stats),
                    "trace": ctx.trace[:8],
                }
            )
        if len(code_samples) < sample_codes:
            code_samples.append({"qid": qid, "query": query, "code": executed_code, "trace": ctx.trace[:8]})
        if idx % 50 == 0:
            print(f"  {idx}/{len(queries)} queries")

    metrics = evaluate(qrels, system_results, k=top_k)
    latency = summarize_stats(stats)
    print(f"{name}: {metrics}, latency={latency}")
    return {
        "metrics": metrics,
        "latency": latency,
        "code_samples": code_samples,
        "per_query": per_query,
    }


def run_fixed_search(ctx: FlowContext, *, mode: str, top_k: int) -> dict:
    hits = ctx.search.search(ctx.query, mode=mode, top_k=top_k)
    ctx.candidate_pool = len(hits)
    ctx.log(
        "fixed_flow",
        {
            "flow": f"query -> {mode} search",
            "candidate_pool": len(hits),
            "top_hits": [hit.compact(120) for hit in hits[:3]],
        },
    )
    return {"hits": hits}


def run_fixed_rerank(ctx: FlowContext, *, candidate_k: int, top_k: int) -> dict:
    hits = ctx.search.search(ctx.query, mode="hybrid", top_k=candidate_k)
    ctx.candidate_pool = len(hits)
    ranked = ctx.ranking.rerank(ctx.query, hits, top_k=top_k)
    ctx.log(
        "fixed_flow",
        {
            "flow": "query -> hybrid search -> cross-encoder rerank",
            "candidate_pool": len(hits),
            "top_hits": [hit.compact(120) for hit in ranked[:3]],
        },
    )
    return {"hits": ranked}


def run_fixed_enriched_rerank(ctx: FlowContext, *, candidate_k: int, top_k: int) -> dict:
    analysis = ctx.query_understanding.analyze(ctx.query)
    linked_entities = []
    if analysis.get("entities"):
        linked_entities = ctx.entity_linking.link(ctx.query)

    rewrite_result = {"needed": False, "rewrites": []}
    if ctx.query_rewrite.should_rewrite(ctx.query, analysis):
        rewrite_result = ctx.query_rewrite.rewrite(
            ctx.query,
            analysis=analysis,
            linked_entities=linked_entities,
        )

    subqueries = [ctx.query] + rewrite_result.get("rewrites", [])
    subqueries = unique_runtime(subqueries)
    candidate_by_id: dict[str, SearchCandidate] = {}
    branch_top_k = candidate_k
    for subquery in subqueries:
        hits = ctx.search.search(subquery, mode="hybrid", top_k=branch_top_k)
        merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    ctx.candidate_pool = len(candidates)
    rerank_candidates = candidates[:candidate_k]
    ranked = ctx.ranking.rerank(ctx.query, rerank_candidates, top_k=top_k)
    ctx.log(
        "fixed_enriched_flow",
        {
            "flow": "query understanding -> optional entity linking -> optional query rewrite -> hybrid search -> rerank",
            "rewrite_needed": rewrite_result["needed"],
            "rewrites": rewrite_result.get("rewrites", []),
            "subqueries": subqueries,
            "linked_entities": linked_entities[:5],
            "candidate_pool": len(candidates),
            "rerank_candidates": len(rerank_candidates),
            "top_hits": [hit.compact(120) for hit in ranked[:3]],
        },
    )
    return {"hits": ranked}


def fixed_search_code(mode: str) -> str:
    return textwrap.dedent(
        f"""
        def run(ctx):
            hits = ctx.search.search(ctx.query, mode={mode!r}, top_k=TOP_K)
            return {{"hits": hits}}
        """
    ).strip()


def fixed_rerank_code(candidate_k: int) -> str:
    return textwrap.dedent(
        f"""
        def run(ctx):
            hits = ctx.search.search(ctx.query, mode="hybrid", top_k={candidate_k})
            ranked = ctx.ranking.rerank(ctx.query, hits, top_k=TOP_K)
            return {{"hits": ranked}}
        """
    ).strip()


def fixed_enriched_rerank_code(candidate_k: int) -> str:
    return textwrap.dedent(
        f"""
        def run(ctx):
            analysis = ctx.query_understanding.analyze(ctx.query)
            linked_entities = []
            if analysis.get("entities"):
                linked_entities = ctx.entity_linking.link(ctx.query)
            rewrite_result = {{"needed": False, "rewrites": []}}
            if ctx.query_rewrite.should_rewrite(ctx.query, analysis):
                rewrite_result = ctx.query_rewrite.rewrite(
                    ctx.query,
                    analysis=analysis,
                    linked_entities=linked_entities,
                )
            subqueries = [ctx.query] + rewrite_result.get("rewrites", [])
            # Retrieve from original query plus optional rewrites, then rerank.
            ...
        """
    ).strip()


def unique_runtime(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def merge_runtime_candidates(candidate_by_id: dict[str, SearchCandidate], hits: list[SearchCandidate]) -> None:
    for hit in hits:
        previous = candidate_by_id.get(hit.doc_id)
        if previous is None or hit.score > previous.score:
            candidate_by_id[hit.doc_id] = hit


def execute_generated_program(code: str, ctx: FlowContext) -> dict:
    namespace: dict = {}
    exec(code, namespace)
    return namespace["run"](ctx)


def execute_reflective_generated_program(
    code: str,
    ctx: FlowContext,
    *,
    top_k: int,
    max_rerank_candidates: int,
) -> dict:
    first = execute_generated_program(code, ctx)
    reflection = reflect_on_generated_result(ctx, first["hits"])
    ctx.log("agentic_reflection_decision", reflection)
    if not reflection["needs_followup"]:
        return first

    followup_code = generate_reflective_followup_program(
        ctx.query,
        reflection,
        top_k=top_k,
        max_rerank_candidates=max_rerank_candidates,
    )
    ctx.log(
        "agentic_followup_code",
        {
            "reason": reflection["reason"],
            "code": followup_code,
        },
    )
    namespace: dict = {}
    exec(followup_code, namespace)
    return namespace["run"](ctx, first)


def reflect_on_generated_result(ctx: FlowContext, hits: list[SearchCandidate]) -> dict:
    last_reflection = {}
    for item in reversed(ctx.trace):
        if item.get("event") == "reflection":
            last_reflection = item.get("payload", {})
            break

    query_tokens = tokenize(ctx.query)
    top_scores = [hit.score for hit in hits[:3]]
    top_gap = top_scores[0] - top_scores[1] if len(top_scores) >= 2 else 0.0
    long_or_multihop = len(query_tokens) >= 12 or any(
        token in set(query_tokens)
        for token in ["what", "which", "who", "when", "where", "compare", "year"]
    )
    exact_terms = any(token.isdigit() for token in query_tokens) or any(len(token) <= 4 and token.isupper() for token in ctx.query.split())
    candidate_pool = int(last_reflection.get("candidate_pool") or ctx.candidate_pool)
    search_modes = set(last_reflection.get("search_modes") or [])
    rerank_candidates = int(last_reflection.get("rerank_candidates") or len(hits))
    subqueries = last_reflection.get("subqueries") or [ctx.query]

    reasons = []
    routes = []
    if candidate_pool < 25:
        reasons.append("candidate_pool_below_25")
        routes.append({"query": ctx.query, "mode": "hybrid", "top_k": 30})
        if "bm25" not in search_modes:
            routes.append({"query": ctx.query, "mode": "bm25", "top_k": 25})
        if "dense" not in search_modes:
            routes.append({"query": ctx.query, "mode": "dense", "top_k": 25})
    thin_or_uncertain_pool = candidate_pool < 25 or (top_gap < 0.25 and rerank_candidates < 30)
    if long_or_multihop and "dense" not in search_modes and thin_or_uncertain_pool:
        reasons.append("missing_dense_for_multihop")
        routes.append({"query": ctx.query, "mode": "dense", "top_k": 30})
    if exact_terms and "bm25" not in search_modes and thin_or_uncertain_pool:
        reasons.append("missing_bm25_for_exact_terms")
        routes.append({"query": ctx.query, "mode": "bm25", "top_k": 30})

    # Only ask the agent to write a second retrieval program when the first
    # program has a genuinely thin evidence pool. A weak reranker margin alone
    # is too noisy and mostly adds cost.
    if top_gap < 0.25 and candidate_pool < 25 and rerank_candidates < 25:
        reasons.append("ambiguous_top_hits_with_thin_pool")
        for subquery in subqueries[:2]:
            if "hybrid" not in search_modes:
                routes.append({"query": subquery, "mode": "hybrid", "top_k": 20})

    routes = dedupe_routes(routes)
    return {
        "needs_followup": bool(routes),
        "reason": "; ".join(reasons) if routes else "enough_evidence",
        "candidate_pool": candidate_pool,
        "top_score_gap": round(float(top_gap), 4),
        "search_modes": sorted(search_modes),
        "rerank_candidates": rerank_candidates,
        "routes": routes,
    }


def dedupe_routes(routes: list[dict]) -> list[dict]:
    by_key = {}
    for route in routes:
        key = (route["query"].lower(), route["mode"])
        previous = by_key.get(key)
        if previous is None or route["top_k"] > previous["top_k"]:
            by_key[key] = route
    return list(by_key.values())


def generate_reflective_initial_program(
    query: str,
    *,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
) -> str:
    return generate_search_program(
        query,
        top_k=top_k,
        branch_top_k=branch_top_k,
        max_rerank_candidates=max_rerank_candidates,
        min_rerank_candidates=0,
    )


def generate_reflective_followup_program(
    query: str,
    reflection: dict,
    *,
    top_k: int,
    max_rerank_candidates: int,
) -> str:
    routes = reflection.get("routes", [])
    code = f"""
def run(ctx, previous):
    query = ctx.query
    routes = {routes!r}
    candidate_by_id = {{}}
    previous_ids = set()

    # Keep the first program's candidate pool, not only its final top-k hits.
    previous_candidates = previous.get("candidates", previous["hits"])
    for item in previous_candidates:
        candidate_by_id[item.doc_id] = item
        previous_ids.add(item.doc_id)

    # Reflection generated new retrieval code with route-level budgets.
    for route in routes:
        hits = ctx.search.search(
            route["query"],
            mode=route["mode"],
            top_k=route["top_k"],
        )
        for hit in hits:
            old = candidate_by_id.get(hit.doc_id)
            if old is None or hit.score > old.score:
                candidate_by_id[hit.doc_id] = hit

    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    new_doc_count = len(set(candidate_by_id) - previous_ids)

    # Decide whether reranking is worth the cost.
    if new_doc_count == 0:
        ranked = previous["hits"][:{top_k}]
        reranked = False
    elif len(candidates) <= {top_k}:
        ranked = candidates[:{top_k}]
        reranked = False
    else:
        ranked = ctx.ranking.rerank(
            query,
            candidates[:{max_rerank_candidates}],
            top_k={top_k},
        )
        reranked = True

    ctx.candidate_pool = len(candidates)
    ctx.log("agentic_followup_result", {{
        "routes": routes,
        "candidate_pool": len(candidates),
        "new_doc_count": new_doc_count,
        "reranked": reranked,
        "rerank_candidates": min(len(candidates), {max_rerank_candidates}) if reranked else 0,
    }})
    return {{"hits": ranked, "previous": previous, "candidates": candidates}}
"""
    return textwrap.dedent(code).strip()


def generate_search_program(
    query: str,
    *,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
    min_rerank_candidates: int,
) -> str:
    strategy = build_strategy(query, top_k, branch_top_k, max_rerank_candidates, min_rerank_candidates)
    code = f"""
def run(ctx):
    query = ctx.query
    analysis = ctx.query_understanding.analyze(query)
    linked_entities = []
    if analysis.get("entities"):
        linked_entities = ctx.entity_linking.link(query)
    rewrite_result = {{"needed": False, "rewrites": []}}
    if ctx.query_rewrite.should_rewrite(query, analysis):
        rewrite_result = ctx.query_rewrite.rewrite(
            query,
            analysis=analysis,
            linked_entities=linked_entities,
        )

    plan = {strategy!r}
    ctx.log("agentic_plan", {{
        "strategy": plan["strategy"],
        "initial_modes": plan["search_modes"],
        "seed_subqueries": plan["seed_subqueries"],
        "rationale": plan["rationale"],
    }})

    subqueries = _unique(
        [query]
        + plan["seed_subqueries"]
        + analysis.get("subqueries", [])[: plan["analysis_subquery_limit"]]
        + rewrite_result.get("rewrites", [])
    )
    modes = list(plan["search_modes"])
    if "metrics" in analysis.get("intents", []):
        modes.append("bm25")
    if len(query.split()) >= plan["long_query_tokens"]:
        modes.append("dense")
    modes = _unique(modes)

    candidate_by_id = {{}}
    for subquery in subqueries:
        for mode in modes:
            hits = ctx.search.search(subquery, mode=mode, top_k=plan["branch_top_k"])
            _merge_candidates(candidate_by_id, hits)

    followup_used = False
    if len(candidate_by_id) < plan["min_candidates"]:
        followup_used = True
        for mode in plan["fallback_modes"]:
            hits = ctx.search.search(query, mode=mode, top_k=plan["branch_top_k"])
            _merge_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    if plan["min_rerank_candidates"] and len(candidates) < plan["min_rerank_candidates"]:
        followup_used = True
        for subquery in _unique([query] + subqueries[:2]):
            for mode in plan["budget_fill_modes"]:
                hits = ctx.search.search(subquery, mode=mode, top_k=plan["min_rerank_candidates"])
                _merge_candidates(candidate_by_id, hits)
        candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)

    ctx.candidate_pool = len(candidates)
    rerank_candidates = candidates[: plan["max_rerank_candidates"]]
    ranked = ctx.ranking.rerank(query, rerank_candidates, top_k=plan["top_k"])

    ctx.log("reflection", {{
        "candidate_pool": len(candidates),
        "rerank_candidates": len(rerank_candidates),
        "followup_used": followup_used,
        "subqueries": subqueries,
        "search_modes": modes,
        "query_understanding_intents": analysis.get("intents", []),
        "linked_entities": linked_entities[:5],
        "rewrite_needed": rewrite_result.get("needed", False),
        "rewrites": rewrite_result.get("rewrites", []),
    }})
    return {{"hits": ranked, "analysis": analysis, "entities": linked_entities, "candidates": candidates}}


def _unique(items):
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _merge_candidates(candidate_by_id, hits):
    for hit in hits:
        previous = candidate_by_id.get(hit.doc_id)
        if previous is None or hit.score > previous.score:
            candidate_by_id[hit.doc_id] = hit
"""
    return textwrap.dedent(code).strip()


def build_strategy(
    query: str,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
    min_rerank_candidates: int,
) -> dict:
    tokens = tokenize(query)
    token_set = set(tokens)
    lower = query.lower()
    has_number = any(token.isdigit() for token in tokens)
    long_query = len(tokens) >= 12
    asks_comparison = any(term in token_set for term in ["compare", "contrast", "versus", "vs", "difference"])
    asks_metric = any(term in token_set for term in ["metric", "metrics", "latency", "token", "tokens", "percent", "score", "relevance"])
    asks_mechanism = any(term in token_set for term in ["how", "why", "mechanism", "pipeline", "flow"])

    search_modes = ["hybrid"]
    seed_subqueries = []
    rationale = ["start from hybrid retrieval"]

    if long_query or asks_mechanism:
        search_modes.append("dense")
        seed_subqueries.append(" ".join(tokens[: min(10, len(tokens))]))
        rationale.append("long/mechanistic queries get semantic expansion")

    if has_number or asks_metric or asks_comparison:
        search_modes.append("bm25")
        rationale.append("numeric/comparison queries get exact lexical matching")

    if asks_comparison:
        max_rerank_candidates = max(max_rerank_candidates, 60)
        rationale.append("comparison queries keep a larger candidate pool")

    return {
        "strategy": "generated_dynamic_tool_flow",
        "seed_subqueries": _strategy_unique(seed_subqueries),
        "search_modes": _strategy_unique(search_modes),
        "branch_top_k": branch_top_k,
        "top_k": top_k,
        "max_rerank_candidates": max_rerank_candidates,
        "min_rerank_candidates": min_rerank_candidates,
        "min_candidates": min(max_rerank_candidates, 35),
        "fallback_modes": ["bm25", "dense"],
        "budget_fill_modes": ["hybrid", "bm25", "dense"],
        "analysis_subquery_limit": 4,
        "long_query_tokens": 12,
        "rationale": rationale,
    }


def summarize_stats(stats: list[QueryStats]) -> dict:
    def values(attr: str) -> list[float]:
        return [float(getattr(item, attr)) for item in stats]

    return {
        "total_wall_seconds": round(sum(values("latency_ms")) / 1000, 4),
        "mean_latency_ms": round(statistics.mean(values("latency_ms")), 3),
        "p50_latency_ms": round(percentile(values("latency_ms"), 50), 3),
        "p95_latency_ms": round(percentile(values("latency_ms"), 95), 3),
        "mean_generation_ms": round(statistics.mean(values("generation_ms")), 3),
        "mean_execution_ms": round(statistics.mean(values("execution_ms")), 3),
        "mean_query_understanding_calls": round(statistics.mean(values("query_understanding_calls")), 3),
        "mean_entity_linking_calls": round(statistics.mean(values("entity_linking_calls")), 3),
        "mean_query_rewrite_calls": round(statistics.mean(values("query_rewrite_calls")), 3),
        "mean_search_calls": round(statistics.mean(values("search_calls")), 3),
        "mean_rerank_calls": round(statistics.mean(values("rerank_calls")), 3),
        "mean_rerank_pairs": round(statistics.mean(values("rerank_pairs")), 3),
        "mean_candidate_pool": round(statistics.mean(values("candidate_pool")), 3),
    }


def build_comparisons(systems: dict, *, k: int) -> dict:
    generated = systems["generated_search_as_code"]
    generated_force = systems["generated_search_as_code_force_budget"]
    generated_reflective = systems.get("generated_reflective_search_as_code")
    comparisons = {}
    for name, baseline in systems.items():
        if name.startswith("generated_"):
            continue
        comparisons[f"generated_vs_{name}"] = compare_pair(baseline, generated, k=k)
        comparisons[f"generated_force_budget_vs_{name}"] = compare_pair(baseline, generated_force, k=k)
        if generated_reflective:
            comparisons[f"generated_reflective_vs_{name}"] = compare_pair(baseline, generated_reflective, k=k)
    comparisons["generated_force_budget_vs_generated"] = compare_pair(generated, generated_force, k=k)
    if generated_reflective:
        comparisons["generated_reflective_vs_generated"] = compare_pair(generated, generated_reflective, k=k)
        comparisons["generated_reflective_vs_generated_force_budget"] = compare_pair(
            generated_force, generated_reflective, k=k
        )
    return comparisons


def compare_pair(baseline: dict, challenger: dict, *, k: int) -> dict:
    baseline_metrics = baseline["metrics"]
    challenger_metrics = challenger["metrics"]
    baseline_latency = baseline["latency"]
    challenger_latency = challenger["latency"]
    baseline_mean = baseline_latency["mean_latency_ms"]
    challenger_mean = challenger_latency["mean_latency_ms"]
    return {
        f"delta_ndcg@{k}": round(challenger_metrics[f"ndcg@{k}"] - baseline_metrics[f"ndcg@{k}"], 4),
        f"delta_recall@{k}": round(challenger_metrics[f"recall@{k}"] - baseline_metrics[f"recall@{k}"], 4),
        f"delta_mrr@{k}": round(challenger_metrics[f"mrr@{k}"] - baseline_metrics[f"mrr@{k}"], 4),
        "baseline_mean_latency_ms": baseline_mean,
        "challenger_mean_latency_ms_including_codegen": challenger_mean,
        "challenger_mean_execution_ms_excluding_codegen": challenger_latency["mean_execution_ms"],
        "latency_ratio_including_codegen": round(challenger_mean / baseline_mean, 3) if baseline_mean else None,
        "latency_ratio_excluding_codegen": (
            round(challenger_latency["mean_execution_ms"] / baseline_mean, 3) if baseline_mean else None
        ),
        "baseline_mean_search_calls": baseline_latency["mean_search_calls"],
        "challenger_mean_search_calls": challenger_latency["mean_search_calls"],
        "baseline_mean_query_rewrite_calls": baseline_latency["mean_query_rewrite_calls"],
        "challenger_mean_query_rewrite_calls": challenger_latency["mean_query_rewrite_calls"],
        "baseline_mean_rerank_pairs": baseline_latency["mean_rerank_pairs"],
        "challenger_mean_rerank_pairs": challenger_latency["mean_rerank_pairs"],
    }


def score_query(qrels: dict, ranked_ids: list[str], k: int) -> dict:
    relevant = set(relevant_doc_ids(qrels))
    ranked_ids = ranked_ids[:k]
    hits = len(set(ranked_ids) & relevant)
    first_relevant_rank = None
    for rank, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            first_relevant_rank = rank
            break
    return {
        "hits": hits,
        "recall": round(hits / len(relevant), 4) if relevant else 0.0,
        "first_relevant_rank": first_relevant_rank,
    }


def relevant_doc_ids(qrels: dict) -> list[str]:
    return [doc_id for doc_id, rel in qrels.items() if rel > 0]


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((pct / 100) * (len(ordered) - 1))
    return ordered[index]


def _strategy_unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


if __name__ == "__main__":
    main()
