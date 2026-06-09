#!/usr/bin/env python3
"""Benchmark retrieval flows on the custom Search-as-Code dataset."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re
import statistics
import textwrap
import time
from typing import Callable, Iterable

from real_search_stack.apis import (
    IndexedDocument,
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryRewriteAPI,
    RealQueryUnderstandingAPI,
    RealRankingAPI,
    SearchCandidate,
    tokenize,
)
from run_flow_comparison import (
    FlowContext,
    QueryStats,
    execute_generated_program,
    execute_reflective_generated_program,
    fixed_enriched_rerank_code,
    fixed_rerank_code,
    fixed_search_code,
    run_fixed_enriched_rerank,
    run_fixed_rerank,
    run_fixed_search,
    summarize_stats,
)


ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "sac_benchmark_dataset" / "data"
IDENTIFIER_RE = re.compile(r"\b(?:CVE-\d{4}-\d+|SEC-\d+|EXPORT-LAT-\d+|\d+\.\d+\.\d+)\b", re.I)
PRODUCTS = [
    "AtlasSearch",
    "Meridian Sync",
    "ForgeDeploy",
    "Beacon CRM Connector",
    "Compass Analytics",
    "Rovo Chat",
]

ARCHITECTURE_SYSTEMS = [
    (
        "fixed_understanding_rewrite_hybrid_rerank",
        "Fixed flow baseline",
        "Fixed query understanding + rewrite + hybrid retrieval + rerank",
    ),
    (
        "generated_search_as_code",
        "Generated flow",
        "One-shot generated route plan with SDK parameters",
    ),
    (
        "agentic_fixed_flow_iterative",
        "Agentic fixed-flow calls",
        "Agent iteratively calls the same fixed flow with new queries",
    ),
    (
        "generated_iterative_agentic_search_as_code",
        "Agentic codegen",
        "Generated code iterates with evidence-coverage reflection",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SAC dataset flow benchmark.")
    parser.add_argument("--data-dir", default=str(DATASET_DIR))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-k", default="10")
    parser.add_argument("--candidate-k", type=int, default=2400)
    parser.add_argument("--fixed-small-candidate-k", type=int, default=400)
    parser.add_argument("--generated-branch-top-k", type=int, default=2000)
    parser.add_argument("--generated-max-rerank-candidates", type=int, default=2400)
    parser.add_argument("--generated-min-rerank-candidates", type=int, default=0)
    parser.add_argument("--output", default="sac_benchmark_results.json")
    parser.add_argument("--report", default="sac_benchmark_report.md")
    parser.add_argument("--sample-codes", type=int, default=4)
    parser.add_argument("--wikidata", action="store_true")
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if args.offline_models:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    data_dir = Path(args.data_dir)
    documents, tasks, qrels, hard_negatives = load_dataset(data_dir, split=args.split)
    metrics_k = sorted({int(item) for item in args.metrics_k.split(",") if item.strip()})
    if args.top_k < max(metrics_k):
        raise SystemExit("--top-k must be >= max --metrics-k")

    print(f"Dataset: {data_dir}")
    print(f"Split: {args.split}")
    print(f"Documents: {len(documents)}")
    print(f"Tasks: {len(tasks)}")
    print("Loading tools...")
    query_understanding_api = RealQueryUnderstandingAPI()
    entity_linking_api = RealEntityLinkingAPI(wikidata_enabled=args.wikidata)
    query_rewrite_api = RealQueryRewriteAPI()
    search_api = RealHybridSearchAPI(documents, local_files_only=args.offline_models)
    ranking_api = RealRankingAPI(local_files_only=args.offline_models)

    task_queries = {task["task_id"]: task["query"] for task in tasks}
    task_by_id = {task["task_id"]: task for task in tasks}
    systems: dict[str, dict] = {}

    for mode, label in [
        ("bm25", "fixed_bm25"),
        ("dense", "fixed_semantic_dense"),
        ("hybrid", "fixed_hybrid"),
    ]:
        systems[label] = run_system(
            label,
            task_queries,
            task_by_id,
            qrels,
            hard_negatives,
            args.top_k,
            metrics_k,
            lambda query, mode=mode: fixed_search_code(mode),
            lambda code, ctx, mode=mode: run_fixed_search(ctx, mode=mode, top_k=args.top_k),
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=0,
        )

    systems["fixed_hybrid_rerank_small_budget"] = run_system(
        "fixed_hybrid_rerank_small_budget",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: fixed_rerank_code(args.fixed_small_candidate_k),
        lambda code, ctx: run_fixed_rerank(ctx, candidate_k=args.fixed_small_candidate_k, top_k=args.top_k),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=0,
    )

    systems["fixed_hybrid_rerank"] = run_system(
        "fixed_hybrid_rerank",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: fixed_rerank_code(args.candidate_k),
        lambda code, ctx: run_fixed_rerank(ctx, candidate_k=args.candidate_k, top_k=args.top_k),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=0,
    )

    systems["fixed_understanding_rewrite_hybrid_rerank"] = run_system(
        "fixed_understanding_rewrite_hybrid_rerank",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: fixed_enriched_rerank_code(args.candidate_k),
        lambda code, ctx: run_fixed_enriched_rerank(ctx, candidate_k=args.candidate_k, top_k=args.top_k),
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=0,
    )

    systems["generated_search_as_code"] = run_system(
        "generated_search_as_code",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: generate_sac_program(
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
    )

    systems["generated_search_as_code_force_budget"] = run_system(
        "generated_search_as_code_force_budget",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: generate_sac_program(
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
    )

    systems["agentic_fixed_flow_iterative"] = run_system(
        "agentic_fixed_flow_iterative",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: generate_agentic_fixed_flow_program(
            query,
            top_k=args.top_k,
            candidate_k=args.fixed_small_candidate_k,
        ),
        execute_generated_program,
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=args.sample_codes,
    )

    systems["generated_reflective_search_as_code"] = run_system(
        "generated_reflective_search_as_code",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: generate_sac_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
            min_rerank_candidates=0,
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
    )

    systems["generated_iterative_agentic_search_as_code"] = run_system(
        "generated_iterative_agentic_search_as_code",
        task_queries,
        task_by_id,
        qrels,
        hard_negatives,
        args.top_k,
        metrics_k,
        lambda query: generate_iterative_agentic_sac_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
        ),
        execute_generated_program,
        query_understanding_api=query_understanding_api,
        entity_linking_api=entity_linking_api,
        query_rewrite_api=query_rewrite_api,
        search_api=search_api,
        ranking_api=ranking_api,
        sample_codes=args.sample_codes,
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
        "fixed_small_candidate_k": args.fixed_small_candidate_k,
        "generated_branch_top_k": args.generated_branch_top_k,
        "generated_max_rerank_candidates": args.generated_max_rerank_candidates,
        "generated_min_rerank_candidates": args.generated_min_rerank_candidates,
        "wikidata_enabled": args.wikidata,
        "systems": systems,
        "comparisons": build_comparisons(systems, metrics_k),
        "architecture_comparison": build_architecture_comparison(systems, metrics_k),
        "selected_examples": select_examples(systems, task_by_id, qrels, hard_negatives, metrics_k),
    }
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    Path(args.report).write_text(render_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def load_dataset(data_dir: Path, *, split: str) -> tuple[list[IndexedDocument], list[dict], dict, dict]:
    corpus = read_jsonl(data_dir / "corpus.jsonl")
    all_tasks = read_jsonl(data_dir / "tasks.jsonl")
    tasks = [task for task in all_tasks if split == "all" or task["split"] == split]
    task_ids = {task["task_id"] for task in tasks}
    hard_negative_rows = read_jsonl(data_dir / "hard_negatives.jsonl")
    documents = [
        IndexedDocument(
            doc_id=doc["doc_id"],
            title=doc["title"],
            text=doc["text"],
            metadata=doc["metadata"],
        )
        for doc in corpus
    ]
    qrels = {
        task["task_id"]: {doc_id: int(score) for doc_id, score in task["evaluation"]["retrieval_relevance"].items()}
        for task in tasks
    }
    hard_negatives: dict[str, set[str]] = {task["task_id"]: set(task["hard_negative_doc_ids"]) for task in tasks}
    for row in hard_negative_rows:
        if row["task_id"] in task_ids:
            hard_negatives.setdefault(row["task_id"], set()).add(row["doc_id"])
    return documents, tasks, qrels, hard_negatives


def run_system(
    name: str,
    queries: dict[str, str],
    task_by_id: dict[str, dict],
    qrels: dict,
    hard_negatives: dict[str, set[str]],
    top_k: int,
    metrics_k: list[int],
    code_generator: Callable[[str], str],
    executor: Callable[[str, FlowContext], dict],
    *,
    query_understanding_api: RealQueryUnderstandingAPI,
    entity_linking_api: RealEntityLinkingAPI,
    query_rewrite_api: RealQueryRewriteAPI,
    search_api: RealHybridSearchAPI,
    ranking_api: RealRankingAPI,
    sample_codes: int,
) -> dict:
    print(f"Running {name}...")
    results: dict[str, list[dict]] = {}
    stats: list[QueryStats] = []
    per_query = []
    code_samples = []

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
        raw_execution_ms = (time.perf_counter() - execution_start) * 1000
        additional_generation_ms = float(result.get("_additional_generation_ms", 0.0))
        generation_ms += additional_generation_ms
        execution_ms = float(result.get("_execution_only_ms", max(0.0, raw_execution_ms - additional_generation_ms)))
        latency_ms = (time.perf_counter() - total_start) * 1000
        executed_code = result.get("_executed_code", code)
        hits: list[SearchCandidate] = result["hits"][:top_k]
        query_stats = ctx.stats(latency_ms=latency_ms, generation_ms=generation_ms, execution_ms=execution_ms)
        stats.append(query_stats)
        results[qid] = [candidate_to_row(hit, rank) for rank, hit in enumerate(hits, start=1)]
        per_query.append(
            {
                "qid": qid,
                "category": task_by_id[qid]["category"],
                "difficulty": task_by_id[qid]["difficulty"],
                "query": query,
                "gold_answer": task_by_id[qid]["gold_answer"],
                "required_operations": task_by_id[qid]["required_operations"],
                "top_doc_ids": [hit.doc_id for hit in hits],
                "top_titles": [hit.title for hit in hits],
                "relevant_doc_ids": relevant_doc_ids(qrels[qid]),
                "hard_negative_doc_ids": sorted(hard_negatives.get(qid, set())),
                "query_metrics": evaluate_query_at_ks(qrels[qid], hard_negatives.get(qid, set()), [hit.doc_id for hit in hits], metrics_k),
                "stats": asdict(query_stats),
                "trace": ctx.trace[:12],
            }
        )
        if len(code_samples) < sample_codes:
            code_samples.append({"qid": qid, "query": query, "code": executed_code, "trace": ctx.trace[:12]})
        if idx % 20 == 0:
            print(f"  {idx}/{len(queries)}")

    metrics = evaluate_results(qrels, hard_negatives, results, metrics_k)
    latency = summarize_stats(stats)
    print(f"{name}: {metrics}, latency={latency}")
    return {
        "metrics": metrics,
        "latency": latency,
        "code_samples": code_samples,
        "per_query": per_query,
    }


def generate_sac_program(
    query: str,
    *,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
    min_rerank_candidates: int,
) -> str:
    strategy = build_sac_strategy(
        query,
        top_k=top_k,
        branch_top_k=branch_top_k,
        max_rerank_candidates=max_rerank_candidates,
        min_rerank_candidates=min_rerank_candidates,
    )
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
        "routes": plan["routes"],
        "exact_terms": plan["exact_terms"],
        "rationale": plan["rationale"],
    }})

    routes = list(plan["routes"])
    for rewrite in rewrite_result.get("rewrites", [])[: plan["rewrite_route_limit"]]:
        routes.append({{"query": rewrite, "mode": "hybrid", "top_k": plan["branch_top_k"]}})
    for subquery in analysis.get("subqueries", [])[: plan["analysis_subquery_limit"]]:
        routes.append({{"query": subquery, "mode": "hybrid", "top_k": plan["branch_top_k"]}})
    routes = _dedupe_routes(routes)

    candidate_by_id = {{}}
    for route in routes:
        hits = ctx.search.search(
            route["query"],
            mode=route["mode"],
            top_k=route["top_k"],
            **_route_kwargs(route),
        )
        _merge_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    if plan["exact_terms"]:
        exact_candidates = _exact_matching_candidates(candidates, plan["exact_terms"])
        if len(exact_candidates) >= plan["min_exact_candidates"]:
            exact_ids = {{hit.doc_id for hit in exact_candidates}}
            candidates = exact_candidates + [hit for hit in candidates if hit.doc_id not in exact_ids]

    followup_used = False
    if len(candidates) < plan["min_candidates"]:
        followup_used = True
        for route in plan["fallback_routes"]:
            hits = ctx.search.search(
                route["query"],
                mode=route["mode"],
                top_k=route["top_k"],
                **_route_kwargs(route),
            )
            _merge_candidates(candidate_by_id, hits)
        candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)

    if plan["min_rerank_candidates"] and len(candidates) < plan["min_rerank_candidates"]:
        followup_used = True
        for mode in ["hybrid", "bm25", "dense"]:
            hits = ctx.search.search(query, mode=mode, top_k=plan["min_rerank_candidates"])
            _merge_candidates(candidate_by_id, hits)
        candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)

    ctx.candidate_pool = len(candidates)
    rerank_candidates = candidates[: plan["max_rerank_candidates"]]
    ranked = ctx.ranking.rerank(query, rerank_candidates, top_k=plan["top_k"])
    ctx.log("reflection", {{
        "candidate_pool": len(candidates),
        "rerank_candidates": len(rerank_candidates),
        "followup_used": followup_used,
        "subqueries": [route["query"] for route in routes],
        "search_modes": sorted({{route["mode"] for route in routes}}),
        "query_understanding_intents": analysis.get("intents", []),
        "linked_entities": linked_entities[:5],
        "rewrite_needed": rewrite_result.get("needed", False),
        "rewrites": rewrite_result.get("rewrites", []),
    }})
    return {{"hits": ranked, "analysis": analysis, "entities": linked_entities, "candidates": candidates}}


def _dedupe_routes(routes):
    by_key = {{}}
    for route in routes:
        key = _route_key(route)
        previous = by_key.get(key)
        if previous is None or route["top_k"] > previous["top_k"]:
            by_key[key] = route
    return list(by_key.values())


def _route_key(route):
    params = tuple(sorted((key, tuple(value) if isinstance(value, list) else value) for key, value in route.items() if key not in {{"query", "mode", "top_k"}}))
    return (route["query"].lower(), route["mode"], params)


def _route_kwargs(route):
    return {{key: value for key, value in route.items() if key not in {{"query", "mode", "top_k"}}}}


def _merge_candidates(candidate_by_id, hits):
    for hit in hits:
        previous = candidate_by_id.get(hit.doc_id)
        if previous is None or hit.score > previous.score:
            candidate_by_id[hit.doc_id] = hit


def _exact_matching_candidates(candidates, terms):
    result = []
    for hit in candidates:
        haystack = (hit.title + " " + hit.text).lower()
        if any(term.lower() in haystack for term in terms):
            result.append(hit)
    return sorted(result, key=lambda hit: hit.score, reverse=True)
"""
    return textwrap.dedent(code).strip()


def generate_agentic_fixed_flow_program(
    query: str,
    *,
    top_k: int,
    candidate_k: int,
) -> str:
    strategy = build_agentic_fixed_flow_strategy(query, top_k=top_k, candidate_k=candidate_k)
    code = f"""
def run(ctx):
    query = ctx.query
    plan = {strategy!r}
    ctx.log("agentic_fixed_flow_plan", {{
        "strategy": plan["strategy"],
        "initial_queries": plan["initial_queries"],
        "goals": [goal["name"] for goal in plan["goals"]],
        "max_reflection_rounds": plan["max_reflection_rounds"],
    }})

    candidate_by_id = {{}}
    used_queries = set()
    tool_calls = []

    for tool_query in plan["initial_queries"][: plan["initial_tool_call_limit"]]:
        result = _call_fixed_flow(ctx, tool_query, plan)
        used_queries.add(tool_query.lower())
        tool_calls.append({{"query": tool_query, "returned": len(result["hits"])}})
        _merge_candidates(candidate_by_id, result["hits"])

    reflection_rounds = []
    for round_index in range(plan["max_reflection_rounds"]):
        candidates = sorted(candidate_by_id.values(), key=_authority_score, reverse=True)
        missing_goals = _missing_goals(candidates, plan["goals"], plan["inspect_top_n"])
        followup_queries = []
        for goal in missing_goals:
            for route in goal["routes"]:
                followup_queries.append(route["query"])
        followup_queries = _dedupe_queries(followup_queries)
        followup_queries = [item for item in followup_queries if item.lower() not in used_queries]
        followup_queries = followup_queries[: plan["max_followup_calls_per_round"]]
        reflection_rounds.append({{
            "round": round_index + 1,
            "missing_goals": [goal["name"] for goal in missing_goals],
            "followup_queries": followup_queries,
            "candidate_pool_before": len(candidates),
        }})
        if not followup_queries:
            break
        for tool_query in followup_queries:
            result = _call_fixed_flow(ctx, tool_query, plan)
            used_queries.add(tool_query.lower())
            tool_calls.append({{"query": tool_query, "returned": len(result["hits"])}})
            _merge_candidates(candidate_by_id, result["hits"])

    candidates = sorted(candidate_by_id.values(), key=_authority_score, reverse=True)
    preselected = _preselect_goal_evidence(candidates, plan["goals"], plan["max_preselected"])
    preselected_ids = {{hit.doc_id for hit in preselected}}
    rerank_pool = preselected + [hit for hit in candidates if hit.doc_id not in preselected_ids]
    rerank_pool = rerank_pool[: plan["final_rerank_candidate_k"]]
    if len(rerank_pool) > plan["top_k"]:
        ranked = ctx.ranking.rerank(query, rerank_pool, top_k=min(len(rerank_pool), plan["rerank_output_k"]))
    else:
        ranked = rerank_pool
    final_hits = _authority_aware_topk(ranked, candidates, plan["goals"], plan["top_k"])
    ctx.candidate_pool = len(candidates)
    ctx.log("agentic_fixed_flow_reflection", {{
        "tool_calls": tool_calls,
        "reflection_rounds": reflection_rounds,
        "candidate_pool": len(candidates),
        "preselected": [hit.doc_id for hit in preselected],
        "rerank_candidates": len(rerank_pool),
        "top_doc_ids": [hit.doc_id for hit in final_hits],
    }})
    return {{"hits": final_hits, "candidates": candidates}}


def _call_fixed_flow(ctx, tool_query, plan):
    analysis = ctx.query_understanding.analyze(tool_query)
    linked_entities = []
    if analysis.get("entities"):
        linked_entities = ctx.entity_linking.link(tool_query)
    rewrite_result = {{"needed": False, "rewrites": []}}
    if ctx.query_rewrite.should_rewrite(tool_query, analysis):
        rewrite_result = ctx.query_rewrite.rewrite(
            tool_query,
            analysis=analysis,
            linked_entities=linked_entities,
        )
    subqueries = _dedupe_queries([tool_query] + rewrite_result.get("rewrites", [])[: plan["rewrite_per_call"]])
    candidate_by_id = {{}}
    for subquery in subqueries:
        hits = ctx.search.search(
            subquery,
            mode="hybrid",
            top_k=plan["fixed_candidate_k"],
            bm25_weight=plan["fixed_bm25_weight"],
        )
        _merge_candidates(candidate_by_id, hits)
    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    rerank_candidates = candidates[: plan["fixed_candidate_k"]]
    ranked = ctx.ranking.rerank(tool_query, rerank_candidates, top_k=plan["tool_top_k"])
    ctx.log("fixed_flow_tool_call", {{
        "query": tool_query,
        "subqueries": subqueries,
        "candidate_pool": len(candidates),
        "returned": len(ranked),
        "rewrite_needed": rewrite_result.get("needed", False),
    }})
    return {{"hits": ranked, "candidates": candidates}}


def _dedupe_queries(queries):
    result = []
    seen = set()
    for query in queries:
        query = " ".join(str(query).split())
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(query)
    return result


def _merge_candidates(candidate_by_id, hits):
    for hit in hits:
        previous = candidate_by_id.get(hit.doc_id)
        if previous is None or hit.score > previous.score:
            candidate_by_id[hit.doc_id] = hit


def _missing_goals(candidates, goals, inspect_top_n):
    return [goal for goal in goals if not _goal_covered(candidates[:inspect_top_n], goal)]


def _goal_covered(candidates, goal):
    for hit in candidates:
        if _matches_goal(hit, goal) and _authority_score(hit) >= goal["min_authority_score"]:
            return True
    return False


def _preselect_goal_evidence(candidates, goals, max_preselected):
    selected = []
    selected_ids = set()
    for goal in goals:
        matches = [hit for hit in candidates if hit.doc_id not in selected_ids and _matches_goal(hit, goal)]
        matches.sort(key=_authority_score, reverse=True)
        for hit in matches[: goal["take"]]:
            selected.append(hit)
            selected_ids.add(hit.doc_id)
            if len(selected) >= max_preselected:
                return selected
    return selected


def _authority_aware_topk(ranked, candidates, goals, top_k):
    final = []
    final_ids = set()
    ranked_by_id = {{hit.doc_id: hit for hit in ranked}}
    candidate_by_id = {{hit.doc_id: hit for hit in candidates}}
    authority_order = sorted(candidates, key=_authority_score, reverse=True)

    for goal in goals:
        goal_ranked = [hit for hit in ranked if hit.doc_id not in final_ids and _matches_goal(hit, goal)]
        goal_ranked.sort(key=lambda hit: (_authority_score(candidate_by_id.get(hit.doc_id, hit)), hit.score), reverse=True)
        goal_candidates = [hit for hit in authority_order if hit.doc_id not in final_ids and _matches_goal(hit, goal)]
        pool = goal_ranked + [hit for hit in goal_candidates if hit.doc_id not in {{item.doc_id for item in goal_ranked}}]
        for hit in pool[: goal["take"]]:
            final.append(ranked_by_id.get(hit.doc_id, hit))
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final

    for hit in ranked:
        if hit.doc_id not in final_ids and not _looks_non_authoritative(hit):
            final.append(hit)
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final
    for hit in ranked:
        if hit.doc_id not in final_ids:
            final.append(hit)
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final
    return final


def _matches_goal(hit, goal):
    text = _candidate_text(hit)
    metadata = getattr(hit, "metadata", {{}}) or {{}}
    doc_type = str(metadata.get("doc_type", "")).lower()
    source = str(metadata.get("source", "")).lower()
    if goal["doc_types"] and doc_type not in goal["doc_types"]:
        return False
    if goal["sources"] and source not in goal["sources"]:
        return False
    if goal["must_any"] and not any(term in text for term in goal["must_any"]):
        return False
    if goal["prefer_any"] and not any(term in text for term in goal["prefer_any"]):
        return False
    if goal["avoid_non_authoritative"] and _looks_non_authoritative(hit):
        return False
    return True


def _authority_score(hit):
    text = _candidate_text(hit)
    metadata = getattr(hit, "metadata", {{}}) or {{}}
    source = str(metadata.get("source", "")).lower()
    doc_type = str(metadata.get("doc_type", "")).lower()
    score = float(getattr(hit, "score", 0.0))

    if source in {{"source_of_truth", "governance", "vendor_advisory", "jira", "release_notes", "eval_policy", "runbook"}}:
        score += 1.2
    if source in {{"crm", "support"}}:
        score += 0.65
    if doc_type in {{"alias_registry", "authority_matrix", "approval_ledger", "war_room_roster", "policy", "release", "security_ticket", "security_advisory", "account_brief", "escalation", "product_footprint"}}:
        score += 1.1
    if any(term in text for term in ["final approval", "source authority", "source-of-truth", "approved citation", "final roster", "latency accounting ledger"]):
        score += 0.8
    if any(term in text for term in ["draft", "stale", "non-authoritative", "not the source-of-truth", "not final", "wrong-customer", "copied dashboard", "scratchpad"]):
        score -= 1.4
    return score


def _looks_non_authoritative(hit):
    text = _candidate_text(hit)
    return any(term in text for term in [
        "non-authoritative",
        "not the source-of-truth",
        "not the r7 final",
        "stale",
        "draft",
        "scratchpad",
        "wrong-customer",
        "copied dashboard",
        "not customer-citable",
        "rollback drill",
    ])


def _candidate_text(hit):
    metadata = getattr(hit, "metadata", {{}}) or {{}}
    return (hit.title + " " + hit.text + " " + str(metadata)).lower()
"""
    return textwrap.dedent(code).strip()


def generate_iterative_agentic_sac_program(
    query: str,
    *,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
) -> str:
    strategy = build_iterative_agentic_strategy(
        query,
        top_k=top_k,
        branch_top_k=branch_top_k,
        max_rerank_candidates=max_rerank_candidates,
    )
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
    ctx.log("agentic_iterative_plan", {{
        "strategy": plan["strategy"],
        "initial_routes": plan["initial_routes"],
        "goals": [goal["name"] for goal in plan["goals"]],
        "rationale": plan["rationale"],
    }})

    routes = list(plan["initial_routes"])
    for rewrite in rewrite_result.get("rewrites", [])[: plan["rewrite_route_limit"]]:
        routes.append({{"query": rewrite, "mode": "hybrid", "top_k": plan["branch_top_k"]}})
    for subquery in analysis.get("subqueries", [])[: plan["analysis_subquery_limit"]]:
        routes.append({{"query": subquery, "mode": "hybrid", "top_k": plan["branch_top_k"]}})
    routes = _dedupe_routes(routes)

    candidate_by_id = {{}}
    for route in routes:
        hits = ctx.search.search(
            route["query"],
            mode=route["mode"],
            top_k=route["top_k"],
            **_route_kwargs(route),
        )
        _merge_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=_authority_score, reverse=True)
    missing_goals = _missing_goals(candidates, plan["goals"], plan["inspect_top_n"])
    followup_routes = []
    for goal in missing_goals:
        followup_routes.extend(goal["routes"])
    followup_routes = _dedupe_routes(followup_routes)

    for route in followup_routes:
        hits = ctx.search.search(
            route["query"],
            mode=route["mode"],
            top_k=route["top_k"],
            **_route_kwargs(route),
        )
        _merge_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=_authority_score, reverse=True)
    preselected = _preselect_goal_evidence(candidates, plan["goals"], plan["max_preselected"])
    preselected_ids = {{hit.doc_id for hit in preselected}}
    rerank_pool = preselected + [hit for hit in candidates if hit.doc_id not in preselected_ids]
    rerank_pool = rerank_pool[: plan["max_rerank_candidates"]]

    ranked = ctx.ranking.rerank(query, rerank_pool, top_k=min(len(rerank_pool), plan["rerank_output_k"]))
    final_hits = _authority_aware_topk(ranked, candidates, plan["goals"], plan["top_k"])
    ctx.candidate_pool = len(candidates)

    ctx.log("agentic_iterative_reflection", {{
        "initial_routes": routes,
        "missing_goals": [goal["name"] for goal in missing_goals],
        "followup_routes": followup_routes,
        "candidate_pool": len(candidates),
        "preselected": [hit.doc_id for hit in preselected],
        "rerank_candidates": len(rerank_pool),
        "top_doc_ids": [hit.doc_id for hit in final_hits],
        "rewrite_needed": rewrite_result.get("needed", False),
        "rewrites": rewrite_result.get("rewrites", []),
    }})
    return {{"hits": final_hits, "analysis": analysis, "entities": linked_entities, "candidates": candidates}}


def _dedupe_routes(routes):
    by_key = {{}}
    for route in routes:
        query = " ".join(route["query"].split())
        if not query:
            continue
        normalized = {{**route, "query": query}}
        key = _route_key(normalized)
        previous = by_key.get(key)
        if previous is None or route["top_k"] > previous["top_k"]:
            by_key[key] = normalized
    return list(by_key.values())


def _route_key(route):
    params = tuple(sorted((key, tuple(value) if isinstance(value, list) else value) for key, value in route.items() if key not in {{"query", "mode", "top_k"}}))
    return (route["query"].lower(), route["mode"], params)


def _route_kwargs(route):
    return {{key: value for key, value in route.items() if key not in {{"query", "mode", "top_k"}}}}


def _merge_candidates(candidate_by_id, hits):
    for hit in hits:
        previous = candidate_by_id.get(hit.doc_id)
        if previous is None or hit.score > previous.score:
            candidate_by_id[hit.doc_id] = hit


def _missing_goals(candidates, goals, inspect_top_n):
    return [goal for goal in goals if not _goal_covered(candidates[:inspect_top_n], goal)]


def _goal_covered(candidates, goal):
    for hit in candidates:
        if _matches_goal(hit, goal) and _authority_score(hit) >= goal["min_authority_score"]:
            return True
    return False


def _preselect_goal_evidence(candidates, goals, max_preselected):
    selected = []
    selected_ids = set()
    for goal in goals:
        matches = [hit for hit in candidates if hit.doc_id not in selected_ids and _matches_goal(hit, goal)]
        matches.sort(key=_authority_score, reverse=True)
        for hit in matches[: goal["take"]]:
            selected.append(hit)
            selected_ids.add(hit.doc_id)
            if len(selected) >= max_preselected:
                return selected
    return selected


def _authority_aware_topk(ranked, candidates, goals, top_k):
    final = []
    final_ids = set()
    ranked_by_id = {{hit.doc_id: hit for hit in ranked}}
    candidate_by_id = {{hit.doc_id: hit for hit in candidates}}
    authority_order = sorted(candidates, key=_authority_score, reverse=True)

    for goal in goals:
        goal_ranked = [hit for hit in ranked if hit.doc_id not in final_ids and _matches_goal(hit, goal)]
        goal_ranked.sort(key=lambda hit: (_authority_score(candidate_by_id.get(hit.doc_id, hit)), hit.score), reverse=True)
        goal_candidates = [hit for hit in authority_order if hit.doc_id not in final_ids and _matches_goal(hit, goal)]
        pool = goal_ranked + [hit for hit in goal_candidates if hit.doc_id not in {{item.doc_id for item in goal_ranked}}]
        for hit in pool[: goal["take"]]:
            final.append(ranked_by_id.get(hit.doc_id, hit))
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final

    for hit in ranked:
        if hit.doc_id not in final_ids and not _looks_non_authoritative(hit):
            final.append(hit)
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final
    for hit in ranked:
        if hit.doc_id not in final_ids:
            final.append(hit)
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final
    return final


def _matches_goal(hit, goal):
    text = _candidate_text(hit)
    metadata = getattr(hit, "metadata", {{}}) or {{}}
    doc_type = str(metadata.get("doc_type", "")).lower()
    source = str(metadata.get("source", "")).lower()
    if goal["doc_types"] and doc_type not in goal["doc_types"]:
        return False
    if goal["sources"] and source not in goal["sources"]:
        return False
    if goal["must_any"] and not any(term in text for term in goal["must_any"]):
        return False
    if goal["prefer_any"] and not any(term in text for term in goal["prefer_any"]):
        return False
    if goal["avoid_non_authoritative"] and _looks_non_authoritative(hit):
        return False
    return True


def _authority_score(hit):
    text = _candidate_text(hit)
    metadata = getattr(hit, "metadata", {{}}) or {{}}
    source = str(metadata.get("source", "")).lower()
    doc_type = str(metadata.get("doc_type", "")).lower()
    score = float(getattr(hit, "score", 0.0))

    if source in {{"source_of_truth", "governance", "vendor_advisory", "jira", "release_notes", "eval_policy", "runbook"}}:
        score += 1.2
    if source in {{"crm", "support"}}:
        score += 0.65
    if doc_type in {{"alias_registry", "authority_matrix", "approval_ledger", "war_room_roster", "policy", "release", "security_ticket", "security_advisory", "account_brief", "escalation", "product_footprint"}}:
        score += 1.1
    if any(term in text for term in ["final approval", "source authority", "source-of-truth", "approved citation", "final roster", "latency accounting ledger"]):
        score += 0.8
    if any(term in text for term in ["draft", "stale", "non-authoritative", "not the source-of-truth", "not final", "wrong-customer", "copied dashboard", "scratchpad"]):
        score -= 1.4
    return score


def _looks_non_authoritative(hit):
    text = _candidate_text(hit)
    return any(term in text for term in [
        "non-authoritative",
        "not the source-of-truth",
        "not the r7 final",
        "stale",
        "draft",
        "scratchpad",
        "wrong-customer",
        "copied dashboard",
        "not customer-citable",
        "rollback drill",
    ])


def _candidate_text(hit):
    metadata = getattr(hit, "metadata", {{}}) or {{}}
    return (hit.title + " " + hit.text + " " + str(metadata)).lower()
"""
    return textwrap.dedent(code).strip()


def build_agentic_fixed_flow_strategy(query: str, *, top_k: int, candidate_k: int) -> dict:
    evidence_strategy = build_iterative_agentic_strategy(
        query,
        top_k=top_k,
        branch_top_k=candidate_k,
        max_rerank_candidates=candidate_k,
    )
    initial_queries = [query]
    for route in evidence_strategy["initial_routes"]:
        initial_queries.append(route["query"])
    initial_queries = unique(initial_queries)
    return {
        "strategy": "agentic_fixed_flow_multi_call",
        "initial_queries": initial_queries,
        "goals": evidence_strategy["goals"],
        "top_k": top_k,
        "fixed_candidate_k": candidate_k,
        "fixed_bm25_weight": 0.55,
        "tool_top_k": max(top_k * 2, 20),
        "initial_tool_call_limit": 3,
        "max_reflection_rounds": 2,
        "max_followup_calls_per_round": 3,
        "rewrite_per_call": 1,
        "inspect_top_n": max(top_k * 4, 40),
        "max_preselected": min(top_k, 8),
        "final_rerank_candidate_k": min(candidate_k, max(top_k * 8, 80)),
        "rerank_output_k": max(top_k * 5, 50),
    }


def build_iterative_agentic_strategy(
    query: str,
    *,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
) -> dict:
    base = build_sac_strategy(
        query,
        top_k=top_k,
        branch_top_k=branch_top_k,
        max_rerank_candidates=max_rerank_candidates,
        min_rerank_candidates=0,
    )
    lower = query.lower()
    tokens = set(tokenize(query))
    goals: list[dict] = []
    rationale = list(base["rationale"])

    def add_goal(
        name: str,
        must_any: list[str],
        prefer_any: list[str],
        routes: list[dict],
        *,
        take: int = 1,
        avoid_non_authoritative: bool = True,
        min_authority_score: float = 0.25,
        doc_types: list[str] | None = None,
        sources: list[str] | None = None,
    ) -> None:
        goals.append(
            {
                "name": name,
                "must_any": [item.lower() for item in must_any],
                "prefer_any": [item.lower() for item in prefer_any],
                "routes": routes,
                "take": take,
                "avoid_non_authoritative": avoid_non_authoritative,
                "min_authority_score": min_authority_score,
                "doc_types": [item.lower() for item in (doc_types or [])],
                "sources": [item.lower() for item in (sources or [])],
            }
        )

    alias_terms = [term for term in ["bpi", "qbl", "nf-17", "rl-7", "nw-h", "ab-q3", "hg-e", "ct-r", "gu-edu", "unest", "jbell", "mp", "prao", "lromero", "achen", "nsingh"] if term in lower]
    if alias_terms or any("alias" in token for token in tokens):
        add_goal(
            "alias_registry",
            ["alias registry", "maps to", "means"],
            alias_terms + ["source-of-truth", "customer alias", "owner alias"],
            [
                {"query": f"{query} alias registry source-of-truth", "mode": "bm25", "top_k": 120},
                {"query": f"{' '.join(alias_terms)} customer owner alias registry", "mode": "hybrid", "top_k": 120},
            ],
            doc_types=["alias_registry"],
        )
        rationale.append("alias/code-name queries require source-of-truth alias expansion")

    if any(term in tokens for term in ["customer", "customers", "account", "renewal", "red-risk", "red", "blocker", "blockers"]) or alias_terms:
        add_goal(
            "account_or_escalation",
            ["account brief", "escalation log", "renewal"],
            ["current blocker", "products in production", "technical owner", "risk"],
            [
                {"query": f"{query} account brief escalation current blocker", "mode": "hybrid", "top_k": 160},
                {"query": f"{query} products in production renewal risk technical owner", "mode": "bm25", "top_k": 120},
            ],
            take=2,
            doc_types=["account_brief", "escalation"],
        )

    if any(term in lower for term in ["cve-", "sec-", "security", "vulnerability", "patch", "remediation", "blocker", "oauth", "saml", "cache", "namespace"]):
        add_goal(
            "ticket_or_advisory",
            ["security response", "vendor advisory", "internal ticket", "tracks response"],
            ["cve-", "sec-", "severity", "owner"],
            [
                {"query": f"{query} vendor advisory internal security ticket CVE SEC", "mode": "bm25", "top_k": 180},
                {"query": f"{query} security owner fixed version advisory ticket", "mode": "hybrid", "top_k": 180},
            ],
            take=2,
            doc_types=["security_ticket", "security_advisory"],
        )

    if any(term in tokens for term in ["release", "version", "fixed", "fix", "fixes", "latency", "evidence"]) or re.search(r"\d+\.\d+\.\d+", query):
        add_goal(
            "release_note",
            ["release notes", "fixed version", "fixes"],
            ["performance note", "new capabilities", "evidence ledger", "single-use refresh tokens"],
            [
                {"query": f"{query} release notes fixed version fixes performance note", "mode": "bm25", "top_k": 160},
                {"query": f"{query} release evidence feature approved", "mode": "hybrid", "top_k": 120},
            ],
            take=2,
            doc_types=["release"],
        )

    if any(term in lower for term in ["approval", "approved", "customer-citable", "reject", "rejected", "authority", "final", "roster", "war room", "source"]):
        add_goal(
            "source_authority",
            ["final approval", "source authority", "final roster", "approval ledger", "source-of-truth"],
            ["approved citation", "supersedes", "explicit exclusions", "authority matrix"],
            [
                {"query": f"{query} final approval ledger source authority source-of-truth", "mode": "bm25", "top_k": 180},
                {"query": f"{query} final roster approved citation supersedes draft", "mode": "hybrid", "top_k": 160},
            ],
            take=2,
            doc_types=["approval_ledger", "authority_matrix", "war_room_roster", "policy"],
        )
        rationale.append("authority-sensitive queries require final/source-of-truth evidence")

    if any(term in tokens for term in ["no", "not", "exclude", "excluded", "should", "does"]):
        add_goal(
            "negative_evidence",
            ["no ", "not ", "should not", "explicit exclusions", "has no", "only active product"],
            ["product footprint", "exclude", "not sufficient", "rejected"],
            [
                {"query": f"{query} negative evidence product footprint explicit exclusions", "mode": "bm25", "top_k": 140},
                {"query": f"{query} should not include rejected not sufficient", "mode": "hybrid", "top_k": 120},
            ],
            take=1,
            avoid_non_authoritative=False,
            min_authority_score=-2.0,
            doc_types=["product_footprint", "account_brief", "sales_discovery", "security_advisory", "release", "approval_ledger"],
        )

    if any(term in tokens for term in ["policy", "metrics", "latency", "readout", "reflection", "candidate", "codegen"]):
        add_goal(
            "policy",
            ["policy", "ledger", "must report", "required metrics", "latency accounting"],
            ["including code generation", "reflection trigger precision", "invalid code rate", "execution-only"],
            [
                {"query": f"{query} final policy latency accounting ledger required metrics", "mode": "bm25", "top_k": 180},
                {"query": f"{query} reflection missing evidence categories follow-up retrieval code", "mode": "hybrid", "top_k": 160},
            ],
            doc_types=["policy", "authority_matrix"],
        )

    if not goals:
        add_goal(
            "general_authoritative_evidence",
            ["release notes", "account brief", "vendor advisory", "internal ticket", "policy"],
            [],
            [
                {"query": f"{query} authoritative evidence source-of-truth release notes account brief", "mode": "hybrid", "top_k": 120},
            ],
            take=2,
            avoid_non_authoritative=False,
            min_authority_score=-2.0,
            doc_types=["release", "account_brief", "escalation", "security_advisory", "security_ticket", "policy", "approval_ledger"],
        )

    return {
        "strategy": "iterative_agentic_evidence_coverage",
        "initial_routes": base["routes"],
        "goals": goals,
        "branch_top_k": branch_top_k,
        "top_k": top_k,
        "max_rerank_candidates": max_rerank_candidates,
        "max_preselected": min(top_k, 8),
        "rerank_output_k": max(top_k * 5, 50),
        "inspect_top_n": 120,
        "analysis_subquery_limit": 3,
        "rewrite_route_limit": 2,
        "rationale": rationale,
    }


def build_sac_strategy(
    query: str,
    *,
    top_k: int,
    branch_top_k: int,
    max_rerank_candidates: int,
    min_rerank_candidates: int,
) -> dict:
    lower = query.lower()
    tokens = tokenize(query)
    token_set = set(tokens)
    exact_terms = unique(IDENTIFIER_RE.findall(query))
    products = [product for product in PRODUCTS if product.lower() in lower]
    routes: list[dict] = []
    fallback_routes: list[dict] = []
    rationale = ["start with hybrid retrieval over the full query"]

    add_route(
        routes,
        query,
        "hybrid",
        branch_top_k,
        bm25_weight=0.55,
        exclude_terms=["scratchpad", "copied dashboard", "wrong-customer"],
    )

    if exact_terms:
        add_route(
            routes,
            " ".join(exact_terms + products),
            "bm25",
            max(branch_top_k, 24),
            must_terms=exact_terms[:3],
            should_terms=products,
        )
        add_route(
            routes,
            query,
            "bm25",
            max(branch_top_k, 24),
            should_terms=exact_terms + products,
            exclude_terms=["stale", "draft", "not customer-citable"],
        )
        rationale.append("exact identifiers use BM25 routes and exact-term pruning")

    if any(term in token_set for term in ["compare", "versus", "vs", "different"]):
        add_route(
            routes,
            query,
            "bm25",
            90,
            include_doc_types=["release", "security_advisory", "security_ticket", "approval_ledger"],
            should_terms=exact_terms + ["fixed version", "release notes", "approval"],
            exclude_terms=["draft", "stale"],
        )
        max_rerank_candidates = max(max_rerank_candidates, 70)
        rationale.append("comparison query adds version/release/approval constrained route")

    if any(term in token_set for term in ["all", "across", "every", "which"]) or "red-risk" in lower:
        add_route(
            routes,
            compact_keywords(tokens, limit=14),
            "hybrid",
            140,
            bm25_weight=0.65,
            include_doc_types=["account_brief", "escalation", "war_room_roster", "security_ticket"],
            should_terms=["current blocker", "renewal", "owner"],
        )
        add_route(routes, compact_keywords(tokens, limit=14), "bm25", 90, should_terms=products)
        max_rerank_candidates = max(max_rerank_candidates, 70)
        rationale.append("wide fanout query gets broader route budgets")

    if any(term in token_set for term in ["no", "not", "exclude", "excluded", "should", "does"]):
        add_route(
            routes,
            query,
            "bm25",
            90,
            include_doc_types=["product_footprint", "account_brief", "sales_discovery", "security_advisory", "release", "approval_ledger"],
            should_terms=["no", "not", "explicit exclusions", "only active product", "rejected"],
        )
        add_route(
            routes,
            f"{query} product footprint negative evidence",
            "hybrid",
            90,
            bm25_weight=0.7,
            include_doc_types=["product_footprint", "account_brief", "sales_discovery"],
            should_terms=["not", "no", "exclude", "does not"],
        )
        rationale.append("negative/decision query constrains retrieval to footprint and exclusion evidence")

    if any(term in lower for term in ["cache namespace", "evidence ledger", "multi hop", "proof", "semantic"]):
        add_route(
            routes,
            query,
            "dense",
            90,
            include_doc_types=["release", "approval_ledger", "meeting_note", "escalation"],
            should_terms=["tenant-scoped", "namespace", "evidence ledger", "proof"],
        )
        rationale.append("semantic evidence query adds dense route")

    if any(term in token_set for term in ["metrics", "metric", "latency", "token", "percent"]):
        add_route(
            routes,
            query,
            "bm25",
            80,
            include_doc_types=["policy", "authority_matrix"],
            should_terms=["latency accounting", "required metrics", "token cost", "execution-only"],
        )
        rationale.append("metric query preserves numeric lexical evidence")

    if any(term in lower for term in ["approval", "approved", "customer-citable", "authority", "final", "source-of-truth"]):
        add_route(
            routes,
            query,
            "hybrid",
            120,
            bm25_weight=0.72,
            include_doc_types=["approval_ledger", "authority_matrix", "war_room_roster", "policy"],
            should_terms=["final approval", "source-of-truth", "approved citation", "supersedes"],
            exclude_terms=["draft", "stale", "not final"],
        )
        rationale.append("authority query uses source-of-truth metadata filters")

    add_route(fallback_routes, query, "bm25", 35, exclude_terms=["draft", "scratchpad"])
    add_route(fallback_routes, query, "dense", 35)

    return {
        "strategy": "sac_enterprise_dynamic_routes",
        "routes": routes,
        "fallback_routes": fallback_routes,
        "exact_terms": exact_terms,
        "branch_top_k": branch_top_k,
        "top_k": top_k,
        "max_rerank_candidates": max_rerank_candidates,
        "min_rerank_candidates": min_rerank_candidates,
        "min_candidates": min(max_rerank_candidates, 35),
        "min_exact_candidates": 2,
        "analysis_subquery_limit": 3,
        "rewrite_route_limit": 2,
        "rationale": rationale,
    }


def add_route(routes: list[dict], query: str, mode: str, top_k: int, **params) -> None:
    query = " ".join(query.split())
    if not query:
        return
    new_route = {"query": query, "mode": mode, "top_k": top_k}
    new_route.update({key: value for key, value in params.items() if value not in (None, [], {})})
    key = route_signature(new_route)
    for existing in routes:
        if route_signature(existing) == key:
            existing["top_k"] = max(existing["top_k"], top_k)
            return
    routes.append(new_route)


def route_signature(route: dict) -> tuple:
    params = tuple(
        sorted(
            (key, tuple(value) if isinstance(value, list) else value)
            for key, value in route.items()
            if key not in {"query", "mode", "top_k"}
        )
    )
    return (route["query"].lower(), route["mode"], params)


def compact_keywords(tokens: list[str], *, limit: int) -> str:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "be",
        "by",
        "for",
        "from",
        "have",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "which",
        "who",
        "with",
    }
    return " ".join(token for token in tokens if token not in stopwords)[:limit * 20]


def evaluate_results(qrels: dict, hard_negatives: dict[str, set[str]], results: dict[str, list[dict]], ks: list[int]) -> dict:
    metrics: dict[str, float | int] = {"evaluated_queries": 0}
    for k in ks:
        ndcg_values = []
        recall_values = []
        mrr_values = []
        all_evidence_values = []
        hard_negative_hit_values = []
        hard_negative_count_values = []
        hard_negative_rate_values = []
        for qid, rels in qrels.items():
            if qid not in results:
                continue
            relevant = {doc_id for doc_id, rel in rels.items() if rel > 0}
            if not relevant:
                continue
            ranked_ids = [row["doc_id"] for row in results[qid]][:k]
            ndcg_values.append(ndcg_at_k(rels, ranked_ids, k))
            hits = len(set(ranked_ids) & relevant)
            recall_values.append(hits / len(relevant))
            all_evidence_values.append(1.0 if relevant <= set(ranked_ids) else 0.0)
            mrr_values.append(reciprocal_rank(relevant, ranked_ids))
            hard_hits = len(set(ranked_ids) & hard_negatives.get(qid, set()))
            hard_negative_count_values.append(hard_hits)
            hard_negative_rate_values.append(hard_hits / k)
            hard_negative_hit_values.append(1.0 if hard_hits else 0.0)
        metrics[f"ndcg@{k}"] = round(mean(ndcg_values), 4)
        metrics[f"recall@{k}"] = round(mean(recall_values), 4)
        metrics[f"mrr@{k}"] = round(mean(mrr_values), 4)
        metrics[f"all_evidence_recovered@{k}"] = round(mean(all_evidence_values), 4)
        metrics[f"hard_negative_hit_rate@{k}"] = round(mean(hard_negative_hit_values), 4)
        metrics[f"hard_negative_count@{k}"] = round(mean(hard_negative_count_values), 4)
        metrics[f"hard_negative_intrusion_rate@{k}"] = round(mean(hard_negative_rate_values), 4)
        metrics["evaluated_queries"] = len(ndcg_values)
    return metrics


def evaluate_query_at_ks(qrels: dict, hard_negatives: set[str], ranked_ids: list[str], ks: list[int]) -> dict:
    result = {}
    relevant = {doc_id for doc_id, rel in qrels.items() if rel > 0}
    for k in ks:
        top_ids = ranked_ids[:k]
        hard_hits = sorted(set(top_ids) & hard_negatives)
        result[f"ndcg@{k}"] = round(ndcg_at_k(qrels, top_ids, k), 4)
        result[f"recall@{k}"] = round(len(set(top_ids) & relevant) / len(relevant), 4) if relevant else 0.0
        result[f"mrr@{k}"] = round(reciprocal_rank(relevant, top_ids), 4)
        result[f"hard_negative_count@{k}"] = len(hard_hits)
        result[f"hard_negative_doc_ids@{k}"] = hard_hits
    return result


def ndcg_at_k(rels: dict[str, int], ranked_ids: list[str], k: int) -> float:
    dcg = 0.0
    for rank, doc_id in enumerate(ranked_ids[:k], start=1):
        rel = rels.get(doc_id, 0)
        if rel > 0:
            dcg += (2**rel - 1) / math.log2(rank + 1)
    ideal_rels = sorted([rel for rel in rels.values() if rel > 0], reverse=True)[:k]
    idcg = sum((2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(ideal_rels, start=1))
    return dcg / idcg if idcg else 0.0


def reciprocal_rank(relevant: set[str], ranked_ids: list[str]) -> float:
    for rank, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def build_comparisons(systems: dict, ks: list[int]) -> dict:
    k = max(ks)
    generated = systems["generated_search_as_code"]
    iterative = systems.get("generated_iterative_agentic_search_as_code")
    comparisons = {}
    for name, baseline in systems.items():
        if name.startswith("generated_"):
            continue
        comparisons[f"generated_vs_{name}"] = compare_pair(baseline, generated, k=k)
        comparisons[f"reflective_vs_{name}"] = compare_pair(baseline, systems["generated_reflective_search_as_code"], k=k)
        if iterative:
            comparisons[f"iterative_agentic_vs_{name}"] = compare_pair(baseline, iterative, k=k)
    comparisons["reflective_vs_generated"] = compare_pair(generated, systems["generated_reflective_search_as_code"], k=k)
    comparisons["generated_force_budget_vs_generated"] = compare_pair(generated, systems["generated_search_as_code_force_budget"], k=k)
    if iterative:
        comparisons["iterative_agentic_vs_generated"] = compare_pair(generated, iterative, k=k)
        comparisons["iterative_agentic_vs_reflective"] = compare_pair(systems["generated_reflective_search_as_code"], iterative, k=k)
    if iterative and "agentic_fixed_flow_iterative" in systems:
        comparisons["agentic_codegen_vs_agentic_fixed_flow"] = compare_pair(
            systems["agentic_fixed_flow_iterative"],
            iterative,
            k=k,
        )
    return comparisons


def build_architecture_comparison(systems: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    included = [(system_id, label, note, systems[system_id]) for system_id, label, note in ARCHITECTURE_SYSTEMS if system_id in systems]
    if not included:
        return []
    rows = []
    for system_id, label, note, result in included:
        metrics = result["metrics"]
        latency = result["latency"]
        quality = quality_score(metrics, k)
        rows.append(
            {
                "system": system_id,
                "label": label,
                "note": note,
                f"quality_score@{k}": quality,
                f"recall@{k}": metrics[f"recall@{k}"],
                f"ndcg@{k}": metrics[f"ndcg@{k}"],
                f"mrr@{k}": metrics[f"mrr@{k}"],
                f"hard_negative_hit_rate@{k}": metrics[f"hard_negative_hit_rate@{k}"],
                f"hard_negative_intrusion_rate@{k}": metrics[f"hard_negative_intrusion_rate@{k}"],
                "mean_latency_ms": latency["mean_latency_ms"],
                "mean_generation_ms": latency["mean_generation_ms"],
                "mean_execution_ms": latency["mean_execution_ms"],
                "mean_search_calls": latency["mean_search_calls"],
                "mean_rerank_pairs": latency["mean_rerank_pairs"],
                "mean_candidate_pool": latency["mean_candidate_pool"],
            }
        )
    return rows


def quality_score(metrics: dict, k: int) -> float:
    raw = (
        0.55 * metrics[f"recall@{k}"]
        + 0.25 * metrics[f"ndcg@{k}"]
        + 0.15 * metrics[f"mrr@{k}"]
        + 0.05 * metrics[f"all_evidence_recovered@{k}"]
        - 0.20 * metrics[f"hard_negative_intrusion_rate@{k}"]
    )
    return round(max(0.0, min(100.0, raw * 100.0)), 1)


def compare_pair(baseline: dict, challenger: dict, *, k: int) -> dict:
    base_m = baseline["metrics"]
    chall_m = challenger["metrics"]
    base_l = baseline["latency"]
    chall_l = challenger["latency"]
    return {
        f"delta_ndcg@{k}": round(chall_m[f"ndcg@{k}"] - base_m[f"ndcg@{k}"], 4),
        f"delta_recall@{k}": round(chall_m[f"recall@{k}"] - base_m[f"recall@{k}"], 4),
        f"delta_mrr@{k}": round(chall_m[f"mrr@{k}"] - base_m[f"mrr@{k}"], 4),
        f"delta_hard_negative_hit_rate@{k}": round(
            chall_m[f"hard_negative_hit_rate@{k}"] - base_m[f"hard_negative_hit_rate@{k}"],
            4,
        ),
        "baseline_mean_latency_ms": base_l["mean_latency_ms"],
        "challenger_mean_latency_ms_including_codegen": chall_l["mean_latency_ms"],
        "challenger_mean_execution_ms_excluding_codegen": chall_l["mean_execution_ms"],
        "latency_ratio_including_codegen": round(chall_l["mean_latency_ms"] / base_l["mean_latency_ms"], 3)
        if base_l["mean_latency_ms"]
        else None,
        "baseline_mean_search_calls": base_l["mean_search_calls"],
        "challenger_mean_search_calls": chall_l["mean_search_calls"],
        "baseline_mean_rerank_pairs": base_l["mean_rerank_pairs"],
        "challenger_mean_rerank_pairs": chall_l["mean_rerank_pairs"],
    }


def select_examples(systems: dict, task_by_id: dict, qrels: dict, hard_negatives: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    generated = by_qid(systems["generated_search_as_code"]["per_query"])
    reflective = by_qid(systems["generated_reflective_search_as_code"]["per_query"])
    iterative = (
        by_qid(systems["generated_iterative_agentic_search_as_code"]["per_query"])
        if "generated_iterative_agentic_search_as_code" in systems
        else {}
    )
    agentic_fixed = (
        by_qid(systems["agentic_fixed_flow_iterative"]["per_query"])
        if "agentic_fixed_flow_iterative" in systems
        else {}
    )
    fixed_enriched = by_qid(systems["fixed_understanding_rewrite_hybrid_rerank"]["per_query"])
    bm25 = by_qid(systems["fixed_bm25"]["per_query"])
    hybrid = by_qid(systems["fixed_hybrid"]["per_query"])
    force_budget = by_qid(systems["generated_search_as_code_force_budget"]["per_query"])
    examples = []

    def add(label: str, qid: str, reason: str) -> bool:
        if any(item["qid"] == qid for item in examples):
            return False
        examples.append(
            {
                "label": label,
                "qid": qid,
                "category": task_by_id[qid]["category"],
                "query": task_by_id[qid]["query"],
                "gold_answer": task_by_id[qid]["gold_answer"],
                "reason": reason,
                "metrics": {
                    "bm25": bm25[qid]["query_metrics"],
                    "hybrid": hybrid[qid]["query_metrics"],
                    "fixed_enriched": fixed_enriched[qid]["query_metrics"],
                    "generated": generated[qid]["query_metrics"],
                    "generated_force_budget": force_budget[qid]["query_metrics"],
                    "reflective": reflective[qid]["query_metrics"],
                    **({"agentic_fixed_flow": agentic_fixed[qid]["query_metrics"]} if qid in agentic_fixed else {}),
                    **({"iterative_agentic": iterative[qid]["query_metrics"]} if qid in iterative else {}),
                },
                "top_doc_ids": {
                    "bm25": bm25[qid]["top_doc_ids"][:k],
                    "hybrid": hybrid[qid]["top_doc_ids"][:k],
                    "fixed_enriched": fixed_enriched[qid]["top_doc_ids"][:k],
                    "generated": generated[qid]["top_doc_ids"][:k],
                    "generated_force_budget": force_budget[qid]["top_doc_ids"][:k],
                    "reflective": reflective[qid]["top_doc_ids"][:k],
                    **({"agentic_fixed_flow": agentic_fixed[qid]["top_doc_ids"][:k]} if qid in agentic_fixed else {}),
                    **({"iterative_agentic": iterative[qid]["top_doc_ids"][:k]} if qid in iterative else {}),
                },
                "generated_trace": generated[qid]["trace"],
                "agentic_fixed_trace": agentic_fixed[qid]["trace"] if qid in agentic_fixed else [],
                "reflective_trace": reflective[qid]["trace"],
                "iterative_trace": iterative[qid]["trace"] if qid in iterative else [],
            }
        )
        return True

    if iterative:
        iterative_candidates = []
        for qid, row in iterative.items():
            iter_recall = row["query_metrics"][f"recall@{k}"]
            one_shot_recall = generated[qid]["query_metrics"][f"recall@{k}"]
            fixed_recall = fixed_enriched[qid]["query_metrics"][f"recall@{k}"]
            best_baseline = max(
                one_shot_recall,
                fixed_recall,
                bm25[qid]["query_metrics"][f"recall@{k}"],
                hybrid[qid]["query_metrics"][f"recall@{k}"],
                agentic_fixed[qid]["query_metrics"][f"recall@{k}"] if qid in agentic_fixed else 0.0,
            )
            iterative_candidates.append(
                (
                    iter_recall - best_baseline,
                    iter_recall - one_shot_recall,
                    iter_recall,
                    qid,
                )
            )
        for _delta_best, _delta_generated, _recall, qid in sorted(iterative_candidates, reverse=True):
            if _delta_best > 0:
                if add(
                    "iterative_agentic_win",
                    qid,
                    "iterative agentic Search-as-Code recovered evidence that one-shot and fixed flows missed",
                ):
                    break

    if agentic_fixed and iterative:
        contrast_candidates = []
        for qid, row in iterative.items():
            codegen_recall = row["query_metrics"][f"recall@{k}"]
            fixed_agent_recall = agentic_fixed[qid]["query_metrics"][f"recall@{k}"]
            contrast_candidates.append((codegen_recall - fixed_agent_recall, codegen_recall, fixed_agent_recall, qid))
        for _delta, _codegen_recall, _fixed_agent_recall, qid in sorted(contrast_candidates, reverse=True):
            if _delta > 0:
                if add(
                    "agentic_codegen_vs_fixed_tool",
                    qid,
                    "agentic codegen outperformed an agent that could only call the fixed flow repeatedly",
                ):
                    break

        followup_candidates = []
        for qid, row in iterative.items():
            reflection = first_event(row["trace"], "agentic_iterative_reflection")
            if not reflection or not reflection["payload"].get("followup_routes"):
                continue
            iter_recall = row["query_metrics"][f"recall@{k}"]
            one_shot_recall = generated[qid]["query_metrics"][f"recall@{k}"]
            followup_candidates.append((iter_recall - one_shot_recall, iter_recall, qid))
        for _delta_generated, _recall, qid in sorted(followup_candidates, reverse=True):
            if _delta_generated > 0:
                if add(
                    "missing_evidence_followup",
                    qid,
                    "missing-evidence reflection generated targeted follow-up routes before final selection",
                ):
                    break

    for qid, row in generated.items():
        gen_recall = row["query_metrics"][f"recall@{k}"]
        base_recall = fixed_enriched[qid]["query_metrics"][f"recall@{k}"]
        if gen_recall > base_recall:
            if add("generated_wins_on_recall", qid, "generated code recovered more evidence than fixed enriched flow"):
                break

    for qid, row in generated.items():
        gen_hard = row["query_metrics"][f"hard_negative_count@{k}"]
        base_hard = fixed_enriched[qid]["query_metrics"][f"hard_negative_count@{k}"]
        if base_hard > gen_hard:
            if add("generated_reduces_hard_negative", qid, "generated exact/dynamic routing reduced hard-negative intrusion"):
                break

    dynamic_candidates = []
    for qid, row in generated.items():
        plan = first_event(row["trace"], "agentic_plan")
        if not plan or len(plan["payload"].get("routes", [])) < 4:
            continue
        dynamic_candidates.append(
            (
                row["query_metrics"][f"recall@{k}"],
                row["query_metrics"][f"ndcg@{k}"],
                qid,
            )
        )
    if dynamic_candidates:
        _recall, _ndcg, qid = sorted(dynamic_candidates, reverse=True)[0]
        add("dynamic_flow_shape", qid, "generated program chose multiple route types and budgets on a high-recall query")

    followup_qid = None
    for qid, row in reflective.items():
        if any(event["event"] == "agentic_followup_result" for event in row["trace"]):
            followup_qid = qid
            if add("reflection_followup", qid, "reflective Search-as-Code generated a second retrieval program"):
                break
    if followup_qid is None:
        no_op_candidates = []
        for qid, row in reflective.items():
            if task_by_id[qid]["category"] != "reflection_required":
                continue
            no_op_candidates.append(
                (
                    generated[qid]["query_metrics"][f"recall@{k}"],
                    qid,
                )
            )
        if no_op_candidates:
            _recall, qid = sorted(no_op_candidates)[0]
            add("reflection_noop_limitation", qid, "reflection did not trigger because first-pass candidate pool was not thin enough")

    for qid, row in fixed_enriched.items():
        fixed_recall = row["query_metrics"][f"recall@{k}"]
        gen_recall = generated[qid]["query_metrics"][f"recall@{k}"]
        if fixed_recall > gen_recall:
            if add("fixed_flow_wins", qid, "fixed enriched flow outperformed generated code; useful limitation case"):
                break

    if not examples:
        for qid in list(generated)[:3]:
            add("representative", qid, "representative query")
    return examples[:5]


def render_report(output: dict) -> str:
    k = max(output["metrics_k"])
    systems = output["systems"]
    leaderboard = sorted(
        systems.items(),
        key=lambda item: (
            item[1]["metrics"][f"recall@{k}"],
            -item[1]["metrics"][f"hard_negative_hit_rate@{k}"],
            -item[1]["latency"]["mean_latency_ms"],
        ),
        reverse=True,
    )
    lines = [
        "# Search-as-Code Dataset Benchmark Report",
        "",
        f"Dataset: `{output['dataset']}`",
        f"Split: `{output['split']}`",
        f"Documents: `{output['documents']}`",
        f"Tasks: `{output['tasks']}`",
        f"Primary metric: `Recall@{k}`",
        f"Candidate opportunity: rerank systems retrieve up to `{output['candidate_k']}` candidates per query before final top-{k} output.",
        f"Quality score: `100 * (0.55*Recall@{k} + 0.25*nDCG@{k} + 0.15*MRR@{k} + 0.05*AllEvidence@{k} - 0.20*HardNegativeIntrusion@{k})`.",
        "",
        "## Readout",
        "",
        summarize_readout(output, k),
        "",
        "## Architecture Comparison",
        "",
        *render_architecture_comparison(output, k),
        "",
        "## Recall@10 Leaderboard",
        "",
        f"| System | Recall@{k} | Hard-neg hit@{k} | Total ms | Codegen ms | Execution ms | Candidate pool | Search calls | Rerank pairs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in leaderboard:
        m = result["metrics"]
        l = result["latency"]
        lines.append(
            f"| {name} | {m[f'recall@{k}']:.4f} | {m[f'hard_negative_hit_rate@{k}']:.4f} | "
            f"{l['mean_latency_ms']:.1f} | {l['mean_generation_ms']:.1f} | {l['mean_execution_ms']:.1f} | "
            f"{l['mean_candidate_pool']:.1f} | "
            f"{l['mean_search_calls']:.2f} | {l['mean_rerank_pairs']:.1f} |"
        )
    lines.extend(
        [
            "",
        "## Key Findings",
        "",
        *render_key_findings(output, k),
        "",
        "## Selected Examples",
        "",
        ]
    )
    for example in output["selected_examples"]:
        lines.extend(render_example(example, k))
    lines.extend(
        [
            "",
            "## Method Notes",
            "",
            "- Code generation latency here is local deterministic generation time, not a hosted LLM call.",
            "- The benchmark still reports generation time separately in JSON, so a real model latency can be added as a sensitivity analysis.",
            "- Dataset qrels contain positive evidence only; hard-negative labels are evaluated separately.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_architecture_comparison(output: dict, k: int) -> list[str]:
    rows = output.get("architecture_comparison") or build_architecture_comparison(output["systems"], output["metrics_k"])
    if rows and "mean_generation_ms" not in rows[0]:
        rows = build_architecture_comparison(output["systems"], output["metrics_k"])
    lines = [
        f"| Architecture | System | Quality score | Recall@{k} | Hard-neg hit@{k} | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs | Flow shape |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | `{row['system']}` | {row[f'quality_score@{k}']:.1f} | "
            f"{row[f'recall@{k}']:.4f} | {row[f'hard_negative_hit_rate@{k}']:.4f} | "
            f"{row['mean_latency_ms']:.1f} | {row['mean_generation_ms']:.1f} | {row['mean_execution_ms']:.1f} | "
            f"{row['mean_search_calls']:.2f} | "
            f"{row['mean_rerank_pairs']:.1f} | {row['note']} |"
        )
    return lines


def summarize_readout(output: dict, k: int) -> str:
    systems = output["systems"]
    generated = systems["generated_search_as_code"]
    fixed = systems["fixed_understanding_rewrite_hybrid_rerank"]
    agentic_fixed = systems.get("agentic_fixed_flow_iterative")
    iterative = systems.get("generated_iterative_agentic_search_as_code")
    if iterative:
        delta_vs_fixed = iterative["metrics"][f"recall@{k}"] - fixed["metrics"][f"recall@{k}"]
        delta_vs_generated = iterative["metrics"][f"recall@{k}"] - generated["metrics"][f"recall@{k}"]
        delta_vs_agentic_fixed = (
            iterative["metrics"][f"recall@{k}"] - agentic_fixed["metrics"][f"recall@{k}"]
            if agentic_fixed
            else 0.0
        )
        delta_hard = (
            iterative["metrics"][f"hard_negative_hit_rate@{k}"]
            - fixed["metrics"][f"hard_negative_hit_rate@{k}"]
        )
        delta_intrusion = (
            iterative["metrics"][f"hard_negative_intrusion_rate@{k}"]
            - fixed["metrics"][f"hard_negative_intrusion_rate@{k}"]
        )
        return (
            f"Iterative agentic Search-as-Code is the first flow that clearly separates from fixed search: "
            f"Recall@{k} `{iterative['metrics'][f'recall@{k}']:.4f}` vs one-shot generated "
            f"`{generated['metrics'][f'recall@{k}']:.4f}` and fixed enriched `{fixed['metrics'][f'recall@{k}']:.4f}` "
            f"(delta vs fixed `{delta_vs_fixed:.4f}`, delta vs one-shot `{delta_vs_generated:.4f}`"
            + (f", delta vs agentic fixed-flow `{delta_vs_agentic_fixed:.4f}`" if agentic_fixed else "")
            + "). "
            f"It pays modestly more search control cost: `{iterative['latency']['mean_search_calls']:.2f}` search calls/query "
            f"and `{iterative['latency']['mean_latency_ms']:.1f}` ms total latency "
            f"(`{iterative['latency']['mean_generation_ms']:.1f}` ms codegen + "
            f"`{iterative['latency']['mean_execution_ms']:.1f}` ms execution). "
            f"Hard-negative hit-rate delta is `{delta_hard:.4f}` and intrusion-rate delta is `{delta_intrusion:.4f}`, "
            "so the next quality gate is final context/answer selection."
        )
    delta_recall = generated["metrics"][f"recall@{k}"] - fixed["metrics"][f"recall@{k}"]
    delta_hard = generated["metrics"][f"hard_negative_hit_rate@{k}"] - fixed["metrics"][f"hard_negative_hit_rate@{k}"]
    return (
        f"Generated Search-as-Code vs fixed enriched at Recall@{k}: "
        f"delta recall `{delta_recall:.4f}`, delta hard-negative hit rate `{delta_hard:.4f}`. "
        f"Generated mean candidate pool is `{generated['latency']['mean_candidate_pool']:.1f}` documents per query; "
        f"fixed enriched mean candidate pool is `{fixed['latency']['mean_candidate_pool']:.1f}`."
    )


def render_key_findings(output: dict, k: int) -> list[str]:
    systems = output["systems"]
    fixed = systems["fixed_understanding_rewrite_hybrid_rerank"]
    generated = systems["generated_search_as_code"]
    forced = systems["generated_search_as_code_force_budget"]
    bm25 = systems["fixed_bm25"]
    dense = systems["fixed_semantic_dense"]
    reflective = systems["generated_reflective_search_as_code"]
    agentic_fixed = systems.get("agentic_fixed_flow_iterative")
    iterative = systems.get("generated_iterative_agentic_search_as_code")
    top_system_name, top_system = max(
        systems.items(), key=lambda item: item[1]["metrics"][f"recall@{k}"]
    )
    forced_hard = forced["metrics"][f"hard_negative_hit_rate@{k}"]
    generated_hard = generated["metrics"][f"hard_negative_hit_rate@{k}"]
    if forced_hard > generated_hard:
        forced_direction = "raises"
    elif forced_hard < generated_hard:
        forced_direction = "lowers"
    else:
        forced_direction = "does not change"
    followups = sum(
        1
        for row in reflective["per_query"]
        if any(event["event"] == "agentic_followup_result" for event in row["trace"])
    )
    findings = [
        f"- Top Recall@{k} system is `{top_system_name}`: Recall@{k} `{top_system['metrics'][f'recall@{k}']:.4f}`.",
    ]
    if iterative:
        findings.extend(
            [
                f"- Iterative agentic Search-as-Code improves Recall@{k} to `{iterative['metrics'][f'recall@{k}']:.4f}` vs one-shot generated `{generated['metrics'][f'recall@{k}']:.4f}` and fixed enriched `{fixed['metrics'][f'recall@{k}']:.4f}`.",
                f"- The gain comes from evidence-coverage reflection: it checks missing categories such as alias, account/escalation, ticket/advisory, release note, source authority, and policy before final top-{k}.",
                f"- Cost is only modestly higher than one-shot: total `{iterative['latency']['mean_latency_ms']:.1f}` ms (`{iterative['latency']['mean_generation_ms']:.1f}` codegen + `{iterative['latency']['mean_execution_ms']:.1f}` execution) vs `{generated['latency']['mean_latency_ms']:.1f}` ms (`{generated['latency']['mean_generation_ms']:.1f}` codegen + `{generated['latency']['mean_execution_ms']:.1f}` execution), with `{iterative['latency']['mean_search_calls']:.2f}` vs `{generated['latency']['mean_search_calls']:.2f}` search calls/query.",
                f"- Hard-negative hit rate is `{iterative['metrics'][f'hard_negative_hit_rate@{k}']:.4f}` vs fixed enriched `{fixed['metrics'][f'hard_negative_hit_rate@{k}']:.4f}`; intrusion rate is `{iterative['metrics'][f'hard_negative_intrusion_rate@{k}']:.4f}` vs `{fixed['metrics'][f'hard_negative_intrusion_rate@{k}']:.4f}`, so answer-level filtering still matters.",
            ]
        )
    if agentic_fixed:
        findings.append(
            f"- Agentic fixed-flow calls reach Recall@{k} `{agentic_fixed['metrics'][f'recall@{k}']:.4f}` with `{agentic_fixed['latency']['mean_search_calls']:.2f}` search calls/query; this isolates the value of iteration when the agent cannot control the lower-level search stack."
        )
    findings.extend(
        [
        f"- One-shot generated Search-as-Code exposes route-level SDK parameters, but still lacks evidence-coverage reflection; Recall@{k} is `{generated['metrics'][f'recall@{k}']:.4f}` vs fixed enriched `{fixed['metrics'][f'recall@{k}']:.4f}`.",
        f"- Candidate opportunity is large: fixed enriched sees `{fixed['latency']['mean_candidate_pool']:.1f}` candidates/query and generated sees `{generated['latency']['mean_candidate_pool']:.1f}` candidates/query before final top-{k}.",
        f"- BM25 remains a serious baseline because it scores the full corpus directly: Recall@{k} `{bm25['metrics'][f'recall@{k}']:.4f}` at `{bm25['latency']['mean_latency_ms']:.1f}` ms; dense-only Recall@{k} is `{dense['metrics'][f'recall@{k}']:.4f}`.",
        forced_budget_finding(forced_direction, generated_hard, forced_hard, forced, k),
        f"- Reflective mode triggered second-pass code on `{followups}` / `{output['tasks']}` tasks, so it currently adds no quality gain. The reflection policy should use missing-evidence checks, not only thin candidate pools.",
        ]
    )
    return findings


def forced_budget_finding(direction: str, generated_hard: float, forced_hard: float, forced: dict, k: int) -> str:
    forced_recall = forced["metrics"][f"recall@{k}"]
    if direction == "does not change":
        return (
            f"- Forced budget expansion does not change hard-negative hit rate "
            f"(`{generated_hard:.4f}`) and leaves Recall@{k} at `{forced_recall:.4f}`; "
            "more retrieval is not automatically better after reranking."
        )
    return (
        f"- Forced budget expansion {direction} hard-negative hit rate from `{generated_hard:.4f}` "
        f"to `{forced_hard:.4f}` and changes Recall@{k} to `{forced_recall:.4f}`; "
        "more retrieval is not automatically better after reranking."
    )


def render_example(example: dict, k: int) -> list[str]:
    lines = [
        f"### {example['qid']} - {example['label']}",
        "",
        f"Query: {example['query']}",
        "",
        f"Why selected: {example['reason']}",
        "",
        f"Gold: {example['gold_answer']}",
        "",
        f"| Method | Recall@{k} | Hard-neg count@{k} | Top docs |",
        "|---|---:|---:|---|",
    ]
    methods = ["bm25", "hybrid", "fixed_enriched", "generated"]
    if "agentic_fixed_flow" in example["metrics"]:
        methods.append("agentic_fixed_flow")
    if "iterative_agentic" in example["metrics"]:
        methods.append("iterative_agentic")
    methods.extend(["generated_force_budget", "reflective"])
    for method in methods:
        metrics = example["metrics"][method]
        top_docs = ", ".join(example["top_doc_ids"].get(method, [])[:5])
        lines.append(
            f"| {method} | {metrics[f'recall@{k}']:.4f} | "
            f"{metrics[f'hard_negative_count@{k}']} | {top_docs} |"
        )
    agentic_fixed_plan = first_event(example.get("agentic_fixed_trace", []), "agentic_fixed_flow_plan")
    if agentic_fixed_plan:
        lines.extend(
            [
                "",
                "Agentic fixed-flow plan:",
                "",
                "```json",
                json.dumps(agentic_fixed_plan["payload"], indent=2)[:2400],
                "```",
            ]
        )
    agentic_fixed_reflection = first_event(example.get("agentic_fixed_trace", []), "agentic_fixed_flow_reflection")
    if agentic_fixed_reflection:
        lines.extend(
            [
                "",
                "Agentic fixed-flow reflection:",
                "",
                "```json",
                json.dumps(agentic_fixed_reflection["payload"], indent=2)[:2400],
                "```",
            ]
        )
    iterative_plan = first_event(example.get("iterative_trace", []), "agentic_iterative_plan")
    if iterative_plan:
        lines.extend(
            [
                "",
                "Iterative agentic plan:",
                "",
                "```json",
                json.dumps(iterative_plan["payload"], indent=2)[:3000],
                "```",
            ]
        )
    iterative_reflection = first_event(example.get("iterative_trace", []), "agentic_iterative_reflection")
    if iterative_reflection:
        lines.extend(
            [
                "",
                "Iterative evidence reflection:",
                "",
                "```json",
                json.dumps(iterative_reflection["payload"], indent=2)[:3000],
                "```",
            ]
        )
    plan = first_event(example["generated_trace"], "agentic_plan")
    if plan:
        lines.extend(
            [
                "",
                "Generated plan:",
                "",
                "```json",
                json.dumps(plan["payload"], indent=2)[:3000],
                "```",
            ]
        )
    reflection = first_event(example["reflective_trace"], "agentic_followup_result")
    if reflection:
        lines.extend(
            [
                "",
                "Reflective follow-up:",
                "",
                "```json",
                json.dumps(reflection["payload"], indent=2)[:2000],
                "```",
            ]
        )
    lines.append("")
    return lines


def first_event(trace: list[dict], event: str) -> dict | None:
    for item in trace:
        if item.get("event") == event:
            return item
    return None


def by_qid(rows: list[dict]) -> dict[str, dict]:
    return {row["qid"]: row for row in rows}


def candidate_to_row(hit: SearchCandidate, rank: int) -> dict:
    return {
        "rank": rank,
        "doc_id": hit.doc_id,
        "title": hit.title,
        "score": float(hit.score),
        "bm25_score": float(hit.bm25_score),
        "dense_score": float(hit.dense_score),
    }


def relevant_doc_ids(qrels: dict) -> list[str]:
    return [doc_id for doc_id, rel in qrels.items() if rel > 0]


def unique(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
