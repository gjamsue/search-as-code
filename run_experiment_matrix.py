#!/usr/bin/env python3
"""Run the Search-as-Code experiment matrix.

This runner matches the presentation taxonomy:

- fixed flow
- agentic fixed flow
- preset flow
- agentic preset flow
- one-shot code generation
- agentic code generation

The full-dataset run uses deterministic rule-backed planner/router/reflection
policies so it is reproducible. Real LLM codegen is still covered by
run_real_codegen_retest.py for focused sample runs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import time
from typing import Iterable

from real_search_stack.apis import (
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
    merge_runtime_candidates,
    unique_runtime,
)
from run_sac_dataset_benchmark import (
    DATASET_DIR,
    IDENTIFIER_RE,
    PRODUCTS,
    build_iterative_agentic_strategy,
    compact_keywords,
    evaluate_query_at_ks,
    evaluate_results,
    generate_agentic_fixed_flow_program,
    generate_iterative_agentic_sac_program,
    generate_sac_program,
    load_dataset,
    read_json,
    relevant_doc_ids,
    summarize_stats,
)


DEFAULT_SYSTEMS = [
    "fixed_flow_model_qr",
    "agentic_fixed_flow_rule_reflection",
    "preset_flow_model_router",
    "agentic_preset_flows_rule_reflection",
    "one_shot_code_gen_rule_policy",
    "agentic_code_gen_rule_reflection",
]


FLOW_DEFINITIONS = {
    "fixed_flow_model_qr": {
        "family": "fixed flow",
        "target_setting": "query -> LLM QR -> multi-query hybrid retrieval -> reranker -> results",
        "implementation": "full run uses the query-rewrite API as a deterministic LLM-QR proxy",
    },
    "agentic_fixed_flow_rule_reflection": {
        "family": "agentic fixed flow",
        "target_setting": "query -> planner -> run fixed flow with decomposed queries -> reflection -> iterate",
        "implementation": "rule planner/reflection over repeated calls to the fixed flow",
    },
    "preset_flow_model_router": {
        "family": "preset flow",
        "target_setting": "query -> LLM router -> pick one preset search stack -> results",
        "implementation": "rule router chooses one preset stack for reproducible full-run comparison",
    },
    "agentic_preset_flows_rule_reflection": {
        "family": "agentic preset flow",
        "target_setting": "query -> router -> pick one/multiple preset stacks -> reflection -> iterate",
        "implementation": "rule router/reflection can choose additional preset stacks after evidence check",
    },
    "one_shot_code_gen_rule_policy": {
        "family": "one-shot code-gen",
        "target_setting": "query -> LLM Python code generation -> execute -> results",
        "implementation": "deterministic code generator emits Python; use run_real_codegen_retest.py for real LLM sample",
    },
    "agentic_code_gen_rule_reflection": {
        "family": "agentic code-gen",
        "target_setting": "query -> planner -> Python codegen -> execution -> reflection -> iterate",
        "implementation": "deterministic agentic code generator with evidence-goal reflection",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Search-as-Code experiment matrix.")
    parser.add_argument("--data-dir", default=str(DATASET_DIR))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-k", default="10")
    parser.add_argument("--candidate-k", type=int, default=2400)
    parser.add_argument("--fixed-tool-candidate-k", type=int, default=800)
    parser.add_argument("--generated-branch-top-k", type=int, default=2000)
    parser.add_argument("--generated-max-rerank-candidates", type=int, default=2400)
    parser.add_argument("--systems", default=",".join(DEFAULT_SYSTEMS))
    parser.add_argument("--output", default="experiment_matrix_results.json")
    parser.add_argument("--report", default="experiment_matrix_report.md")
    parser.add_argument("--sample-codes", type=int, default=3)
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

    selected = [item.strip() for item in args.systems.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(DEFAULT_SYSTEMS))
    if unknown:
        raise SystemExit(f"Unknown systems: {', '.join(unknown)}")

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

    task_queries = {task["task_id"]: task["query"] for task in tasks}
    task_by_id = {task["task_id"]: task for task in tasks}
    systems: dict[str, dict] = {}

    def maybe_run(name: str, code_generator, executor, *, sample_codes: int | None = None) -> None:
        if name not in selected:
            return
        systems[name] = run_matrix_system(
            name,
            task_queries,
            task_by_id,
            qrels,
            hard_negatives,
            args.top_k,
            metrics_k,
            code_generator,
            executor,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=args.sample_codes if sample_codes is None else sample_codes,
        )

    maybe_run(
        "fixed_flow_model_qr",
        lambda query: fixed_flow_model_qr_code(args.candidate_k),
        lambda _code, ctx: run_fixed_flow_model_qr(ctx, candidate_k=args.candidate_k, top_k=args.top_k),
        sample_codes=1,
    )
    maybe_run(
        "agentic_fixed_flow_rule_reflection",
        lambda query: generate_agentic_fixed_flow_program(
            query,
            top_k=args.top_k,
            candidate_k=args.fixed_tool_candidate_k,
        ),
        execute_generated_program,
    )
    maybe_run(
        "preset_flow_model_router",
        lambda query: preset_flow_code(query, allow_multiple=False, candidate_k=args.candidate_k),
        lambda _code, ctx: run_preset_flow(
            ctx,
            candidate_k=args.candidate_k,
            top_k=args.top_k,
            allow_multiple=False,
        ),
    )
    maybe_run(
        "agentic_preset_flows_rule_reflection",
        lambda query: preset_flow_code(query, allow_multiple=True, candidate_k=args.candidate_k),
        lambda _code, ctx: run_agentic_preset_flow(
            ctx,
            candidate_k=args.fixed_tool_candidate_k,
            final_candidate_k=args.candidate_k,
            top_k=args.top_k,
            max_rounds=2,
        ),
    )
    maybe_run(
        "one_shot_code_gen_rule_policy",
        lambda query: generate_sac_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
            min_rerank_candidates=0,
        ),
        execute_generated_program,
    )
    maybe_run(
        "agentic_code_gen_rule_reflection",
        lambda query: generate_iterative_agentic_sac_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
        ),
        execute_generated_program,
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
        "fixed_tool_candidate_k": args.fixed_tool_candidate_k,
        "generated_branch_top_k": args.generated_branch_top_k,
        "generated_max_rerank_candidates": args.generated_max_rerank_candidates,
        "decision_provider": "rule_proxy_for_full_dataset_reproducibility",
        "flow_definitions": {name: FLOW_DEFINITIONS[name] for name in selected},
        "systems": systems,
        "summary_rows": build_summary_rows(systems, metrics_k),
        "selected_examples": select_matrix_examples(systems, task_by_id, qrels, metrics_k),
    }
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    Path(args.report).write_text(render_matrix_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def run_matrix_system(
    name: str,
    queries: dict[str, str],
    task_by_id: dict[str, dict],
    qrels: dict,
    hard_negatives: dict[str, set[str]],
    top_k: int,
    metrics_k: list[int],
    code_generator,
    executor,
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
                "trace": ctx.trace[:16],
            }
        )
        if len(code_samples) < sample_codes:
            code_samples.append({"qid": qid, "query": query, "code": result.get("_executed_code", code), "trace": ctx.trace[:16]})
        if idx % 10 == 0:
            print(f"  {idx}/{len(queries)}")

    metrics = evaluate_results(qrels, hard_negatives, results, metrics_k)
    latency = summarize_stats(stats)
    print(f"{name}: recall@{max(metrics_k)}={metrics[f'recall@{max(metrics_k)}']}, latency={latency['mean_latency_ms']:.1f}ms")
    return {
        "definition": FLOW_DEFINITIONS[name],
        "metrics": metrics,
        "latency": latency,
        "code_samples": code_samples,
        "per_query": per_query,
    }


def run_fixed_flow_model_qr(ctx: FlowContext, *, candidate_k: int, top_k: int) -> dict:
    analysis = ctx.query_understanding.analyze(ctx.query)
    linked_entities = []
    if analysis.get("entities"):
        linked_entities = ctx.entity_linking.link(ctx.query)
    rewrite_result = ctx.query_rewrite.rewrite(
        ctx.query,
        analysis=analysis,
        linked_entities=linked_entities,
    )
    subqueries = unique_runtime([ctx.query] + rewrite_result.get("rewrites", [])[:3])
    candidate_by_id: dict[str, SearchCandidate] = {}
    for subquery in subqueries:
        hits = ctx.search.search(subquery, mode="hybrid", top_k=candidate_k, bm25_weight=0.55)
        merge_runtime_candidates(candidate_by_id, hits)
    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    ctx.candidate_pool = len(candidates)
    rerank_pool = candidates[:candidate_k]
    ranked = ctx.ranking.rerank(ctx.query, rerank_pool, top_k=top_k)
    ctx.log(
        "fixed_flow_model_qr",
        {
            "flow": "query -> model query rewrite -> multi-query hybrid retrieval -> rerank",
            "qr_provider": "rule_proxy",
            "rewrites": rewrite_result.get("rewrites", []),
            "subqueries": subqueries,
            "candidate_pool": len(candidates),
            "rerank_candidates": len(rerank_pool),
        },
    )
    return {"hits": ranked, "candidates": candidates}


def run_preset_flow(ctx: FlowContext, *, candidate_k: int, top_k: int, allow_multiple: bool) -> dict:
    plan_start = time.perf_counter()
    stacks = route_preset_stacks(ctx.query, allow_multiple=allow_multiple)
    planning_ms = (time.perf_counter() - plan_start) * 1000
    candidates = execute_preset_stacks(ctx, ctx.query, stacks, candidate_k=candidate_k)
    rerank_pool = candidates[:candidate_k]
    ranked = ctx.ranking.rerank(ctx.query, rerank_pool, top_k=top_k)
    ctx.candidate_pool = len(candidates)
    ctx.log(
        "preset_flow_router",
        {
            "router_provider": "rule_proxy",
            "allow_multiple": allow_multiple,
            "stacks": stacks,
            "candidate_pool": len(candidates),
            "rerank_candidates": len(rerank_pool),
        },
    )
    return {"hits": ranked, "candidates": candidates, "_additional_generation_ms": planning_ms}


def run_agentic_preset_flow(
    ctx: FlowContext,
    *,
    candidate_k: int,
    final_candidate_k: int,
    top_k: int,
    max_rounds: int,
) -> dict:
    planning_start = time.perf_counter()
    strategy = build_iterative_agentic_strategy(
        ctx.query,
        top_k=top_k,
        branch_top_k=candidate_k,
        max_rerank_candidates=final_candidate_k,
    )
    initial_stacks = route_preset_stacks(ctx.query, allow_multiple=True)
    planning_ms = (time.perf_counter() - planning_start) * 1000
    ctx.log(
        "agentic_preset_plan",
        {
            "router_provider": "rule_proxy",
            "reflection_provider": "rule_proxy",
            "initial_stacks": initial_stacks,
            "goals": [goal["name"] for goal in strategy["goals"]],
            "max_rounds": max_rounds,
        },
    )

    used_stacks = set()
    candidate_by_id: dict[str, SearchCandidate] = {}
    stack_calls = []

    for stack in initial_stacks:
        hits = execute_preset_stack(ctx, ctx.query, stack, candidate_k=candidate_k)
        used_stacks.add(stack)
        stack_calls.append({"stack": stack, "round": 0, "returned": len(hits)})
        merge_runtime_candidates(candidate_by_id, hits)

    reflection_rounds = []
    for round_index in range(max_rounds):
        reflect_start = time.perf_counter()
        candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
        missing_goals = missing_goals_for_candidates(candidates, strategy["goals"], inspect_top_n=120)
        followup_stacks = []
        for goal in missing_goals:
            followup_stacks.extend(stacks_for_goal(goal["name"]))
        followup_stacks = [stack for stack in unique_runtime(followup_stacks) if stack not in used_stacks]
        planning_ms += (time.perf_counter() - reflect_start) * 1000
        reflection_rounds.append(
            {
                "round": round_index + 1,
                "missing_goals": [goal["name"] for goal in missing_goals],
                "followup_stacks": followup_stacks,
                "candidate_pool_before": len(candidates),
            }
        )
        if not followup_stacks:
            break
        for stack in followup_stacks[:3]:
            hits = execute_preset_stack(ctx, ctx.query, stack, candidate_k=candidate_k)
            used_stacks.add(stack)
            stack_calls.append({"stack": stack, "round": round_index + 1, "returned": len(hits)})
            merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    preselected = preselect_goal_evidence(candidates, strategy["goals"], max_preselected=min(top_k, 8))
    preselected_ids = {hit.doc_id for hit in preselected}
    rerank_pool = preselected + [hit for hit in candidates if hit.doc_id not in preselected_ids]
    rerank_pool = rerank_pool[:final_candidate_k]
    ranked = ctx.ranking.rerank(ctx.query, rerank_pool, top_k=max(top_k * 5, 50))
    final_hits = authority_aware_topk(ranked, candidates, strategy["goals"], top_k)
    ctx.candidate_pool = len(candidates)
    ctx.log(
        "agentic_preset_reflection",
        {
            "stack_calls": stack_calls,
            "reflection_rounds": reflection_rounds,
            "candidate_pool": len(candidates),
            "preselected": [hit.doc_id for hit in preselected],
            "rerank_candidates": len(rerank_pool),
            "top_doc_ids": [hit.doc_id for hit in final_hits],
        },
    )
    return {"hits": final_hits, "candidates": candidates, "_additional_generation_ms": planning_ms}


def route_preset_stacks(query: str, *, allow_multiple: bool) -> list[str]:
    lower = query.lower()
    tokens = set(tokenize(query))
    exact_terms = IDENTIFIER_RE.findall(query)
    stacks = []

    if any(term in lower for term in ["alias", "bpi", "qbl", "nf-17", "rl-7", "nw-h", "ab-q3", "hg-e", "ct-r"]):
        stacks.append("alias_resolution")
    if exact_terms or any(term in lower for term in ["cve-", "sec-", "security", "vulnerability", "patch", "oauth", "saml"]):
        stacks.append("exact_security")
    if any(term in tokens for term in ["customer", "customers", "account", "renewal", "blocker", "blockers", "all", "across", "which"]) or "red-risk" in lower:
        stacks.append("wide_fanout")
    if any(term in tokens for term in ["no", "not", "exclude", "excluded", "should", "does"]):
        stacks.append("negative_evidence")
    if any(term in lower for term in ["approval", "approved", "customer-citable", "authority", "final", "source-of-truth", "roster"]):
        stacks.append("authority")
    if any(term in tokens for term in ["policy", "metrics", "latency", "token", "candidate", "codegen", "reflection"]):
        stacks.append("policy")
    if len(tokens) >= 12 or any(term in lower for term in ["semantic", "multi hop", "proof", "evidence ledger", "cache namespace"]):
        stacks.append("semantic_multihop")

    if not stacks:
        stacks.append("general_hybrid")
    stacks = unique_runtime(stacks)
    return stacks if allow_multiple else stacks[:1]


def stacks_for_goal(goal_name: str) -> list[str]:
    return {
        "alias_registry": ["alias_resolution", "authority"],
        "account_or_escalation": ["wide_fanout"],
        "ticket_or_advisory": ["exact_security"],
        "release_note": ["semantic_multihop", "exact_security"],
        "source_authority": ["authority"],
        "negative_evidence": ["negative_evidence"],
        "policy": ["policy"],
        "general_authoritative_evidence": ["semantic_multihop", "authority"],
    }.get(goal_name, ["general_hybrid"])


def execute_preset_stacks(ctx: FlowContext, query: str, stacks: list[str], *, candidate_k: int) -> list[SearchCandidate]:
    candidate_by_id: dict[str, SearchCandidate] = {}
    for stack in stacks:
        hits = execute_preset_stack(ctx, query, stack, candidate_k=candidate_k)
        merge_runtime_candidates(candidate_by_id, hits)
    return sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)


def execute_preset_stack(ctx: FlowContext, query: str, stack: str, *, candidate_k: int) -> list[SearchCandidate]:
    routes = preset_stack_routes(query, stack, candidate_k=candidate_k)
    candidate_by_id: dict[str, SearchCandidate] = {}
    for route in routes:
        route_query = route["query"]
        route_kwargs = {key: value for key, value in route.items() if key != "query"}
        hits = ctx.search.search(route_query, **route_kwargs)
        merge_runtime_candidates(candidate_by_id, hits)
    ctx.log("preset_stack_call", {"stack": stack, "routes": routes, "returned": len(candidate_by_id)})
    return sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)


def preset_stack_routes(query: str, stack: str, *, candidate_k: int) -> list[dict]:
    lower = query.lower()
    tokens = tokenize(query)
    exact_terms = IDENTIFIER_RE.findall(query)
    products = [product for product in PRODUCTS if product.lower() in lower]
    compact = compact_keywords(tokens, limit=14) or query
    half = max(40, candidate_k // 2)

    if stack == "alias_resolution":
        return [
            {"query": f"{query} alias registry source-of-truth", "mode": "bm25", "top_k": candidate_k, "include_doc_types": ["alias_registry"]},
            {"query": f"{compact} customer owner alias registry", "mode": "hybrid", "top_k": half, "bm25_weight": 0.7},
        ]
    if stack == "exact_security":
        exact_query = " ".join(exact_terms + products) or query
        return [
            {
                "query": exact_query,
                "mode": "bm25",
                "top_k": candidate_k,
                "must_terms": exact_terms[:3],
                "should_terms": products + ["fixed version", "vendor advisory", "internal ticket"],
            },
            {
                "query": f"{query} fixed version advisory ticket release notes",
                "mode": "hybrid",
                "top_k": half,
                "bm25_weight": 0.7,
                "include_doc_types": ["security_ticket", "security_advisory", "release", "approval_ledger"],
                "exclude_terms": ["draft", "stale"],
            },
        ]
    if stack == "wide_fanout":
        return [
            {
                "query": f"{compact} account escalation current blocker renewal owner",
                "mode": "hybrid",
                "top_k": candidate_k,
                "bm25_weight": 0.65,
                "include_doc_types": ["account_brief", "escalation", "war_room_roster", "security_ticket"],
                "should_terms": ["current blocker", "renewal", "owner", "products in production"],
            },
            {"query": compact, "mode": "bm25", "top_k": half, "should_terms": products},
        ]
    if stack == "negative_evidence":
        return [
            {
                "query": f"{query} negative evidence product footprint explicit exclusions",
                "mode": "bm25",
                "top_k": candidate_k,
                "include_doc_types": ["product_footprint", "account_brief", "sales_discovery", "security_advisory", "release", "approval_ledger"],
                "should_terms": ["no", "not", "explicit exclusions", "only active product", "rejected"],
            },
            {
                "query": f"{query} should not include rejected not sufficient",
                "mode": "hybrid",
                "top_k": half,
                "bm25_weight": 0.72,
                "include_doc_types": ["product_footprint", "account_brief", "sales_discovery"],
            },
        ]
    if stack == "authority":
        return [
            {
                "query": f"{query} final approval ledger source authority source-of-truth",
                "mode": "hybrid",
                "top_k": candidate_k,
                "bm25_weight": 0.72,
                "include_doc_types": ["approval_ledger", "authority_matrix", "war_room_roster", "policy"],
                "should_terms": ["final approval", "source-of-truth", "approved citation", "supersedes"],
                "exclude_terms": ["draft", "stale", "not final"],
            }
        ]
    if stack == "policy":
        return [
            {
                "query": f"{query} final policy latency accounting ledger required metrics",
                "mode": "bm25",
                "top_k": candidate_k,
                "include_doc_types": ["policy", "authority_matrix"],
                "should_terms": ["latency accounting", "required metrics", "token cost", "execution-only"],
            },
            {"query": query, "mode": "hybrid", "top_k": half, "bm25_weight": 0.68, "include_doc_types": ["policy", "authority_matrix"]},
        ]
    if stack == "semantic_multihop":
        return [
            {
                "query": query,
                "mode": "dense",
                "top_k": candidate_k,
                "include_doc_types": ["release", "approval_ledger", "meeting_note", "escalation", "security_ticket", "account_brief", "policy"],
            },
            {"query": f"{query} authoritative evidence source-of-truth", "mode": "hybrid", "top_k": half, "bm25_weight": 0.55},
        ]
    return [{"query": query, "mode": "hybrid", "top_k": candidate_k, "bm25_weight": 0.55}]


def missing_goals_for_candidates(candidates: list[SearchCandidate], goals: list[dict], *, inspect_top_n: int) -> list[dict]:
    return [goal for goal in goals if not goal_covered(candidates[:inspect_top_n], goal)]


def goal_covered(candidates: list[SearchCandidate], goal: dict) -> bool:
    for hit in candidates:
        if matches_goal(hit, goal) and authority_score(hit) >= goal["min_authority_score"]:
            return True
    return False


def preselect_goal_evidence(candidates: list[SearchCandidate], goals: list[dict], *, max_preselected: int) -> list[SearchCandidate]:
    selected = []
    selected_ids = set()
    for goal in goals:
        matches = [hit for hit in candidates if hit.doc_id not in selected_ids and matches_goal(hit, goal)]
        matches.sort(key=authority_score, reverse=True)
        for hit in matches[: goal["take"]]:
            selected.append(hit)
            selected_ids.add(hit.doc_id)
            if len(selected) >= max_preselected:
                return selected
    return selected


def authority_aware_topk(ranked: list[SearchCandidate], candidates: list[SearchCandidate], goals: list[dict], top_k: int) -> list[SearchCandidate]:
    final = []
    final_ids = set()
    ranked_by_id = {hit.doc_id: hit for hit in ranked}
    authority_order = sorted(candidates, key=authority_score, reverse=True)

    for goal in goals:
        goal_ranked = [hit for hit in ranked if hit.doc_id not in final_ids and matches_goal(hit, goal)]
        goal_ranked.sort(key=lambda hit: (authority_score(hit), hit.score), reverse=True)
        goal_candidates = [hit for hit in authority_order if hit.doc_id not in final_ids and matches_goal(hit, goal)]
        pool = goal_ranked + [hit for hit in goal_candidates if hit.doc_id not in {item.doc_id for item in goal_ranked}]
        for hit in pool[: goal["take"]]:
            final.append(ranked_by_id.get(hit.doc_id, hit))
            final_ids.add(hit.doc_id)
            if len(final) >= top_k:
                return final

    for hit in ranked:
        if hit.doc_id not in final_ids and not looks_non_authoritative(hit):
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


def matches_goal(hit: SearchCandidate, goal: dict) -> bool:
    text = candidate_text(hit)
    metadata = hit.metadata or {}
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
    if goal["avoid_non_authoritative"] and looks_non_authoritative(hit):
        return False
    return True


def authority_score(hit: SearchCandidate) -> float:
    text = candidate_text(hit)
    metadata = hit.metadata or {}
    source = str(metadata.get("source", "")).lower()
    doc_type = str(metadata.get("doc_type", "")).lower()
    score = float(hit.score)
    if source in {"source_of_truth", "governance", "vendor_advisory", "jira", "release_notes", "eval_policy", "runbook"}:
        score += 1.2
    if source in {"crm", "support"}:
        score += 0.65
    if doc_type in {
        "alias_registry",
        "authority_matrix",
        "approval_ledger",
        "war_room_roster",
        "policy",
        "release",
        "security_ticket",
        "security_advisory",
        "account_brief",
        "escalation",
        "product_footprint",
    }:
        score += 1.1
    if any(term in text for term in ["final approval", "source authority", "source-of-truth", "approved citation", "final roster", "latency accounting ledger"]):
        score += 0.8
    if looks_non_authoritative(hit):
        score -= 1.4
    return score


def looks_non_authoritative(hit: SearchCandidate) -> bool:
    text = candidate_text(hit)
    return any(
        term in text
        for term in [
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
        ]
    )


def candidate_text(hit: SearchCandidate) -> str:
    return (hit.title + " " + hit.text + " " + str(hit.metadata or {})).lower()


def fixed_flow_model_qr_code(candidate_k: int) -> str:
    return f"""def run(ctx):
    analysis = ctx.query_understanding.analyze(ctx.query)
    linked_entities = ctx.entity_linking.link(ctx.query) if analysis.get("entities") else []
    rewrite_result = ctx.query_rewrite.rewrite(ctx.query, analysis=analysis, linked_entities=linked_entities)
    subqueries = [ctx.query] + rewrite_result.get("rewrites", [])[:3]
    # For each query variant: hybrid retrieval(top_k={candidate_k}) -> merge -> rerank.
    ..."""


def preset_flow_code(query: str, *, allow_multiple: bool, candidate_k: int) -> str:
    stacks = route_preset_stacks(query, allow_multiple=allow_multiple)
    return f"""def run(ctx):
    stacks = {stacks!r}
    # Router-selected preset stacks. Each stack owns retrieval mode, filters, top_k={candidate_k}, and rerank.
    ..."""


def candidate_to_row(hit: SearchCandidate, rank: int) -> dict:
    return {
        "rank": rank,
        "doc_id": hit.doc_id,
        "title": hit.title,
        "score": round(float(hit.score), 4),
        "metadata": hit.metadata,
    }


def build_summary_rows(systems: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    rows = []
    for name, result in systems.items():
        metrics = result["metrics"]
        latency = result["latency"]
        rows.append(
            {
                "system": name,
                "family": result["definition"]["family"],
                f"recall@{k}": metrics[f"recall@{k}"],
                "mean_latency_ms": latency["mean_latency_ms"],
                "mean_generation_ms": latency["mean_generation_ms"],
                "mean_execution_ms": latency["mean_execution_ms"],
                "mean_search_calls": latency["mean_search_calls"],
                "mean_query_rewrite_calls": latency["mean_query_rewrite_calls"],
                "mean_rerank_pairs": latency["mean_rerank_pairs"],
                "mean_candidate_pool": latency["mean_candidate_pool"],
            }
        )
    return sorted(rows, key=lambda row: (row[f"recall@{k}"], -row["mean_latency_ms"]), reverse=True)


def select_matrix_examples(systems: dict, task_by_id: dict, qrels: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    per_system = {name: {row["qid"]: row for row in result["per_query"]} for name, result in systems.items()}
    examples = []

    def add(kind: str, qid: str, note: str) -> None:
        if qid in {item["qid"] for item in examples}:
            return
        examples.append(
            {
                "kind": kind,
                "qid": qid,
                "query": task_by_id[qid]["query"],
                "category": task_by_id[qid]["category"],
                "note": note,
                "systems": {
                    name: {
                        f"recall@{k}": rows[qid]["query_metrics"][f"recall@{k}"],
                        "top_doc_ids": rows[qid]["top_doc_ids"][:k],
                        "trace": rows[qid]["trace"][:4],
                    }
                    for name, rows in per_system.items()
                    if qid in rows
                },
                "relevant_doc_ids": relevant_doc_ids(qrels[qid]),
            }
        )

    if "agentic_code_gen_rule_reflection" in per_system and "one_shot_code_gen_rule_policy" in per_system:
        deltas = []
        for qid, row in per_system["agentic_code_gen_rule_reflection"].items():
            one = per_system["one_shot_code_gen_rule_policy"][qid]
            deltas.append((row["query_metrics"][f"recall@{k}"] - one["query_metrics"][f"recall@{k}"], qid))
        for delta, qid in sorted(deltas, reverse=True):
            if delta > 0:
                add("agentic_codegen_win", qid, "agentic codegen reflection recovered evidence one-shot codegen missed")
                break

    if "agentic_preset_flows_rule_reflection" in per_system and "preset_flow_model_router" in per_system:
        deltas = []
        for qid, row in per_system["agentic_preset_flows_rule_reflection"].items():
            preset = per_system["preset_flow_model_router"][qid]
            deltas.append((row["query_metrics"][f"recall@{k}"] - preset["query_metrics"][f"recall@{k}"], qid))
        for delta, qid in sorted(deltas, reverse=True):
            if delta > 0:
                add("agentic_preset_win", qid, "agentic preset flow added a missing preset stack after reflection")
                break

    if "fixed_flow_model_qr" in per_system and "preset_flow_model_router" in per_system:
        deltas = []
        for qid, row in per_system["fixed_flow_model_qr"].items():
            preset = per_system["preset_flow_model_router"][qid]
            deltas.append((row["query_metrics"][f"recall@{k}"] - preset["query_metrics"][f"recall@{k}"], qid))
        for delta, qid in sorted(deltas, reverse=True):
            if delta > 0:
                add("fixed_flow_vs_single_preset", qid, "multi-query hybrid baseline beat one routed preset stack")
                break

    for qid in task_by_id:
        if len(examples) >= 3:
            break
        add("representative", qid, "representative matrix example")
    return examples[:3]


def render_matrix_report(output: dict) -> str:
    k = max(output["metrics_k"])
    lines = [
        "# Search-as-Code Experiment Matrix",
        "",
        "## Setup",
        "",
        f"- Dataset: `{output['dataset']}` / split `{output['split']}`",
        f"- Documents: `{output['documents']}`",
        f"- Questions: `{output['tasks']}`",
        f"- Metric: `Recall@{k}`",
        f"- Latency: total wall-clock plus generation/planning and execution split",
        f"- Decision provider for this full run: `{output['decision_provider']}`",
        "",
        "## Flow Definitions",
        "",
        "| System | Family | Target setting | Full-run implementation |",
        "|---|---|---|---|",
    ]
    for name, definition in output["flow_definitions"].items():
        lines.append(
            f"| `{name}` | {definition['family']} | {definition['target_setting']} | {definition['implementation']} |"
        )

    lines.extend(
        [
            "",
            "## Results",
            "",
            f"| System | Family | Recall@{k} | Total ms | Planning/codegen ms | Execution ms | Search calls | QR calls | Rerank pairs |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in output["summary_rows"]:
        lines.append(
            f"| `{row['system']}` | {row['family']} | {row[f'recall@{k}']:.4f} | "
            f"{row['mean_latency_ms']:.1f} | {row['mean_generation_ms']:.1f} | {row['mean_execution_ms']:.1f} | "
            f"{row['mean_search_calls']:.2f} | {row['mean_query_rewrite_calls']:.2f} | {row['mean_rerank_pairs']:.1f} |"
        )

    lines.extend(["", "## Readout", ""])
    rows = {row["system"]: row for row in output["summary_rows"]}
    fixed = rows.get("fixed_flow_model_qr")
    preset = rows.get("preset_flow_model_router")
    agentic_preset = rows.get("agentic_preset_flows_rule_reflection")
    one_shot = rows.get("one_shot_code_gen_rule_policy")
    agentic_codegen = rows.get("agentic_code_gen_rule_reflection")
    if one_shot and agentic_codegen:
        lines.append(
            f"- Agentic codegen vs one-shot codegen: Recall@{k} `{agentic_codegen[f'recall@{k}']:.4f}` vs `{one_shot[f'recall@{k}']:.4f}`, "
            f"latency `{agentic_codegen['mean_latency_ms']:.1f}` ms vs `{one_shot['mean_latency_ms']:.1f}` ms."
        )
    if preset and agentic_preset:
        lines.append(
            f"- Agentic preset flows vs single preset router: Recall@{k} `{agentic_preset[f'recall@{k}']:.4f}` vs `{preset[f'recall@{k}']:.4f}`, "
            f"showing the value of reflection even when the agent can only choose preset stacks."
        )
    if fixed and one_shot:
        lines.append(
            f"- Fixed multi-query hybrid remains a strong baseline: Recall@{k} `{fixed[f'recall@{k}']:.4f}` at `{fixed['mean_latency_ms']:.1f}` ms. "
            f"Codegen only matters if route-level control or iterative evidence coverage changes the candidate set."
        )

    lines.extend(["", "## Examples", ""])
    for example in output["selected_examples"]:
        lines.extend(
            [
                f"### {example['qid']} - {example['kind']}",
                "",
                example["query"],
                "",
                example["note"],
                "",
                f"Relevant docs: `{', '.join(example['relevant_doc_ids'])}`",
                "",
                f"| System | Recall@{k} | Top docs |",
                "|---|---:|---|",
            ]
        )
        for name, row in example["systems"].items():
            lines.append(f"| `{name}` | {row[f'recall@{k}']:.4f} | `{', '.join(row['top_doc_ids'][:5])}` |")
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- The matrix now matches the proposed architecture taxonomy.",
            "- Full-dataset planner/router/reflection decisions are rule-backed for reproducibility; real LLM codegen is still measured separately on focused samples because full-dataset model calls are expensive and less repeatable.",
            "- A real LLM query-rewrite/planner/router/reflection provider can plug into the same boundaries later without changing the retrieval tools or metrics.",
        ]
    )
    return "\n".join(lines) + "\n"


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    main()
